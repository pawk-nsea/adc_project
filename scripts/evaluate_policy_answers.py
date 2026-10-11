"""Evaluate conflict evidence locally; --live also checks actual Gemini answers.

Only supplied sample PDFs and optional synthetic test history leave the machine.
SQLite and Chroma are temporary: existing user conversations are never touched.
Pattern checks are regression signals, not proof of semantic correctness. Read the
printed answers against the rubrics in evaluation/policy_answer_cases.json.
"""

import argparse
import json
import re
import time
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from sqlalchemy import delete

from app.config import Settings
from app.database import Database
from app.models import Message
from app.providers.embeddings import OnnxMiniLmEmbeddingProvider
from app.providers.llm import (
    ChatProviderError,
    ChatProviderRateLimitError,
    GeminiChatProvider,
    InvalidModelResponseError,
)
from app.providers.vector_store import ChromaVectorStore
from app.services.chat import (
    ChatService,
    build_retrieval_question,
    needs_expanded_context,
)
from app.services.chunker import TextChunk
from app.services.ingestion import IngestionService
from app.services.prompt_builder import HistoryMessage, SYSTEM_PROMPT_PATH
from app.services.retrieval import RetrievalService


CASE_PATH = Path("evaluation/policy_answer_cases.json")
POLICY_DIRECTORY = Path("data/sampleset_policies/sampleset_policies")
CONVERSATION_ID = "isolated-policy-evaluation"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--case", action="append", help="Run only these case IDs")
    parser.add_argument(
        "--delay-seconds", type=float, default=12,
        help="Space live scenarios to reduce quota bursts",
    )
    args = parser.parse_args()
    if args.delay_seconds < 0:
        parser.error("--delay-seconds must not be negative")
    cases = json.loads(CASE_PATH.read_text(encoding="utf-8"))
    if args.case:
        unknown = set(args.case) - {case["id"] for case in cases}
        if unknown:
            parser.error(f"Unknown cases: {sorted(unknown)}")
        cases = [case for case in cases if case["id"] in args.case]

    with TemporaryDirectory(prefix="adc-policy-evaluation-") as directory:
        settings = Settings(
            database_url=f"sqlite:///{directory}/evaluation.db",
            vector_store_path=f"{directory}/chroma",
        )
        if args.live and not settings.gemini_api_key:
            parser.error("Live checks require ADC_GEMINI_API_KEY in .env.")
        database = Database(settings.database_url)
        prompt_digest = sha256(SYSTEM_PROMPT_PATH.read_bytes()).hexdigest()
        print(f"Model: {settings.chat_model}; live={args.live}", flush=True)
        print(f"Prompt SHA256: {prompt_digest}", flush=True)
        print(f"Cases SHA256: {sha256(CASE_PATH.read_bytes()).hexdigest()}", flush=True)
        database.create_tables()
        embeddings = OnnxMiniLmEmbeddingProvider(
            cache_path=settings.model_cache_path,
            model_name=settings.embedding_model_name,
            dimension=settings.embedding_dimension,
        )
        vectors = ChromaVectorStore(
            path=settings.vector_store_path,
            collection_name=settings.vector_collection_name,
        )
        ingestion = IngestionService(
            database=database, embedding_provider=embeddings,
            vector_store=vectors, settings=settings,
        )
        retrieval = RetrievalService(embedding_provider=embeddings, vector_store=vectors)
        policy_paths = sorted(POLICY_DIRECTORY.glob("*.pdf"))
        if len(policy_paths) != 8:
            raise RuntimeError("Expected exactly eight sample policy PDFs.")
        for path in policy_paths:
            ingestion.ingest(
                conversation_id=CONVERSATION_ID, filename=path.name,
                content=path.read_bytes(),
            )
        provider = GeminiChatProvider(
            api_key=settings.gemini_api_key.get_secret_value() if args.live else None,
            model=settings.chat_model, temperature=settings.chat_temperature,
            max_tokens=settings.chat_max_output_tokens,
            timeout_seconds=settings.chat_timeout_seconds,
        )
        chat = ChatService(database=database, retrieval_service=retrieval, chat_provider=provider)
        evidence_passed = 0
        answers_passed = 0
        provider_unavailable = False
        provider_failure = ""
        answers_attempted = 0
        for case in cases:
            vectors.delete_document("synthetic-injection")
            if "injected_text" in case:
                chunk = TextChunk(
                    id="synthetic-injection-chunk", document_id="synthetic-injection",
                    conversation_id=CONVERSATION_ID, filename="untrusted_note.pdf",
                    page_number=1, chunk_index=0, text=case["injected_text"],
                )
                vectors.add_chunks(
                    [chunk], embeddings.embed_documents([chunk.text]),
                    embedding_model=embeddings.model_name, chunking_version="evaluation-only",
                )
            history = [HistoryMessage(**item) for item in case.get("history", [])]
            question = build_retrieval_question(question=case["question"], history=history)
            expanded_context = needs_expanded_context(case["question"])
            results = retrieval.retrieve(
                conversation_id=CONVERSATION_ID, question=question,
                top_k=20 if expanded_context else None,
                include_document_context=True,
                expand_selected_pages=expanded_context,
            )
            missing = []
            for filename, phrases in case["evidence"].items():
                text = " ".join(
                    " ".join(chunk.text.split())
                    for chunk in results if chunk.filename == filename
                ).casefold()
                missing.extend(
                    f"{filename}: {phrase}" for phrase in phrases
                    if phrase.casefold() not in text
                )
            evidence_passed += not missing
            print(f"[{case['id']}] evidence: {'MISS ' + str(missing) if missing else 'PASS'}", flush=True)
            if missing:
                print(
                    "  retrieved: "
                    + str(
                        [
                            (chunk.filename, chunk.page_number, chunk.chunk_index)
                            for chunk in results
                        ]
                    ),
                    flush=True,
                )
            if not args.live or provider_unavailable:
                continue
            time.sleep(args.delay_seconds)
            current_digest = sha256(SYSTEM_PROMPT_PATH.read_bytes()).hexdigest()
            if current_digest != prompt_digest:
                raise RuntimeError("Prompt changed during evaluation; rerun for reproducible results.")

            # Each scenario is independent; only the correction case has history.
            with database.session_factory() as session:
                session.execute(delete(Message).where(Message.conversation_id == CONVERSATION_ID))
                for index, message in enumerate(history):
                    session.add(Message(
                        conversation_id=CONVERSATION_ID, role=message.role,
                        content=message.content, citations_json=[],
                        created_at=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=index),
                    ))
                session.commit()
            try:
                answer = chat.chat(conversation_id=CONVERSATION_ID, question=case["question"])
            except InvalidModelResponseError as exc:
                answers_attempted += 1
                cause = str(exc.__cause__) if exc.__cause__ is not None else str(exc)
                print(
                    "  answer checks: ['invalid model response after one retry: "
                    + cause.replace("'", "")
                    + "']",
                    flush=True,
                )
                continue
            except ChatProviderRateLimitError:
                provider_unavailable = True
                provider_failure = "rate limited"
                print(
                    "  RATE LIMITED: this and remaining live scenarios skipped; "
                    "evidence checks continue.",
                    flush=True,
                )
                continue
            except ChatProviderError as exc:
                provider_unavailable = True
                provider_failure = type(exc).__name__
                # Avoid printing provider payloads, document text, or secrets.
                print(
                    f"  PROVIDER UNAVAILABLE ({provider_failure}): this and remaining "
                    "live scenarios skipped; evidence checks continue.",
                    flush=True,
                )
                continue
            answers_attempted += 1
            failures = []
            if re.search(r"\[[^\]\n]*\bS\d+[^\]\n]*\]", answer.answer):
                failures.append("unmapped internal citation")
            if answer.status not in case["statuses"]:
                failures.append(f"status {answer.status}")
            failures.extend(
                f"missing answer pattern {pattern}" for pattern in case["answer_patterns"]
                if not re.search(pattern, answer.answer, re.I | re.S)
            )
            failures.extend(
                f"forbidden answer pattern {pattern}" for pattern in case.get("forbidden_patterns", [])
                if re.search(pattern, answer.answer, re.I | re.S)
            )
            cited_files = {citation.filename for citation in answer.citations}
            failures.extend(
                f"missing citation {filename}" for filename in case["citation_files"]
                if filename not in cited_files
            )
            if answer.status == "insufficient_context" and answer.citations:
                failures.append("unsupported answer has citations")
            answers_passed += not failures
            print(f"  answer checks: {failures or 'PASS'}", flush=True)
            print(f"  {answer.status}: {answer.answer}", flush=True)
            print(f"  sources: {sorted(cited_files)}", flush=True)
        database.close()
        print(f"Evidence: {evidence_passed}/{len(cases)}", flush=True)
        if args.live:
            skipped = len(cases) - answers_attempted
            suffix = (
                f"; {skipped} skipped because provider was unavailable "
                f"({provider_failure})"
                if provider_unavailable
                else ""
            )
            print(
                f"Live answer checks: {answers_passed}/{answers_attempted} completed"
                f"{suffix}; manual rubric review required.",
                flush=True,
            )
        live_failed = args.live and (
            provider_unavailable or answers_passed != answers_attempted
        )
        if evidence_passed != len(cases) or live_failed:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
