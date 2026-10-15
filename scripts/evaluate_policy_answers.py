"""Evaluate retrieved policy evidence; --live also records Gemini drafts and audits.

Live mode sends fixture questions/history and retrieved policy or injected test text
to Gemini. Default mode makes no hosted model calls.
SQLite and Chroma are temporary: existing user conversations are never touched.
Pattern checks are regression signals, not proof of semantic correctness. Read the
printed answers against the rubrics in the selected case file.
"""

import argparse
import json
import logging
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
    ChatMessage,
    ChatProvider,
    ChatProviderError,
    ChatProviderRateLimitError,
    GeminiChatProvider,
    GeminiClaimVerifier,
    InvalidModelResponseError,
    ModelAnswer,
)
from app.providers.vector_store import ChromaVectorStore
from app.services.chat import ChatService
from app.services.claim_verification import VERIFICATION_PROMPT_PATH
from app.services.conversation_context import (
    EXPANDED_CONTEXT_TOP_K, build_retrieval_question,
    needs_expanded_context, resolve_question_context,
)
from app.services.chunker import TextChunk
from app.services.ingestion import IngestionService
from app.services.prompt_builder import HistoryMessage, SYSTEM_PROMPT_PATH
from app.services.retrieval import RetrievalService


DEFAULT_CASE_PATH = Path("evaluation/policy_answer_cases.json")
RETIRED_CASE_IDS = frozenset(
    json.loads(Path("evaluation/retired_case_ids.json").read_text(encoding="utf-8"))
)
POLICY_DIRECTORY = Path("data/sampleset_policies/sampleset_policies")
CONVERSATION_ID = "isolated-policy-evaluation"


class RecordingChatProvider:
    """Keep generated evaluation answers so failed semantic checks are reviewable."""

    def __init__(self, delegate: ChatProvider) -> None:
        self._delegate = delegate
        self.answers: list[ModelAnswer] = []
        self.events: list[dict[str, object]] = []

    def generate(self, messages: list[ChatMessage]) -> ModelAnswer:
        """Delegate generation and record its answer, timing and available token usage."""

        started = time.monotonic()
        event: dict[str, object] = {"stage": "generation"}
        self.events.append(event)
        try:
            answer = self._delegate.generate(messages)
        except ChatProviderError as exc:
            event.update(error=str(exc), seconds=round(time.monotonic() - started, 2))
            raise
        event.update(answer=answer.model_dump(), seconds=round(time.monotonic() - started, 2), usage=getattr(self._delegate, "last_usage", {}))
        self.answers.append(answer)
        return answer


class RecordingVerifier:
    """Record evaluation-only evidence and independent verdicts for manual diagnosis."""

    def __init__(self, delegate: GeminiClaimVerifier) -> None:
        self._delegate = delegate
        self.events: list[dict[str, object]] = []

    def verify(self, messages: list[ChatMessage]):
        """Record the supplied audit evidence and response for evaluation-only review."""

        started = time.monotonic()
        event: dict[str, object] = {
            "stage": "verification",
            "input": json.loads(messages[-1].content.split("\n", 1)[1]),
        }
        self.events.append(event)
        try:
            result = self._delegate.verify(messages)
        except ChatProviderError as exc:
            event.update(error=str(exc), seconds=round(time.monotonic() - started, 2))
            raise
        event.update(verdict=result.model_dump(), seconds=round(time.monotonic() - started, 2), usage=self._delegate.last_usage)
        return result


class RecordingCorrections(logging.Handler):
    """Capture the existing validation/retry logs only inside this live runner."""

    def __init__(self) -> None:
        super().__init__()
        self.events: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.events.append(record.getMessage())


def _safe_provider_failure(exc: ChatProviderError) -> str:
    """Report exception type/status without printing provider payloads or secrets."""

    cause = exc.__cause__
    if cause is None:
        return type(exc).__name__
    status = getattr(cause, "code", None) or getattr(cause, "status_code", None)
    provider_status = getattr(cause, "status", None)
    details = [type(exc).__name__, str(exc), type(cause).__name__]
    if status is not None:
        details.append(f"status={status}")
    if provider_status is not None:
        details.append(f"provider_status={provider_status}")
    return "/".join(details)


def main() -> None:
    """Run selected fixtures in temporary storage, saving/resuming reports if requested.

    Default mode checks evidence locally. --live calls Gemini and checks answer
    patterns/citations; manual rubric review remains necessary for semantic quality.
    """

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument(
        "--case-file",
        type=Path,
        action="append",
        help="JSON case set to evaluate; repeat to include additional live suites",
    )
    parser.add_argument("--case", action="append", help="Run only these case IDs")
    parser.add_argument("--output", type=Path, help="Save live evidence, attempts and verdicts as JSON")
    parser.add_argument("--resume", action="store_true", help="Resume a matching report without repeating completed cases")
    parser.add_argument(
        "--delay-seconds", type=float, default=12,
        help="Space live scenarios to reduce quota bursts",
    )
    args = parser.parse_args()
    if args.delay_seconds < 0:
        parser.error("--delay-seconds must not be negative")
    case_paths = args.case_file or [DEFAULT_CASE_PATH]
    cases = []
    for case_path in case_paths:
        if not case_path.is_file():
            parser.error(f"Case file does not exist: {case_path}")
        cases.extend(json.loads(case_path.read_text(encoding="utf-8")))
    if len({case["id"] for case in cases}) != len(cases):
        parser.error("Case IDs must be unique across selected files")
    retired = {case["id"] for case in cases if case["id"] in RETIRED_CASE_IDS}
    cases = [case for case in cases if case["id"] not in RETIRED_CASE_IDS]
    if retired:
        print(f"Retired cases excluded: {sorted(retired)}", flush=True)
    if set(args.case or []) & RETIRED_CASE_IDS:
        parser.error("Requested case is retired and will not be run")
    case_hashes = {str(path): sha256(path.read_bytes()).hexdigest() for path in case_paths}
    cases_digest = sha256(json.dumps(case_hashes, sort_keys=True).encode()).hexdigest()
    if args.resume and (not args.output or not args.output.is_file()):
        parser.error("--resume needs an existing --output report")
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
        verification_prompt_digest = sha256(
            VERIFICATION_PROMPT_PATH.read_bytes()
        ).hexdigest()
        print(
            f"Draft model: {settings.chat_model}; "
            f"verification model: {settings.verification_model}; live={args.live}",
            flush=True,
        )
        print(f"Prompt SHA256: {prompt_digest}", flush=True)
        print(
            f"Verification prompt SHA256: {verification_prompt_digest}",
            flush=True,
        )
        print(f"Case files: {[str(path) for path in case_paths]}", flush=True)
        print(f"Cases SHA256: {cases_digest}", flush=True)
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
            thinking_level=settings.chat_thinking_level,
        )
        verifier = GeminiClaimVerifier(
            api_key=settings.gemini_api_key.get_secret_value() if args.live else None,
            model=settings.verification_model,
            max_tokens=settings.verification_max_output_tokens,
            timeout_seconds=settings.chat_timeout_seconds,
            thinking_level=settings.verification_thinking_level,
        )
        recording_provider = RecordingChatProvider(provider)
        recording_verifier = RecordingVerifier(verifier)
        recording_corrections = RecordingCorrections()
        chat_logger = logging.getLogger("app.services.chat")
        chat_logger.addHandler(recording_corrections)
        chat = ChatService(
            database=database,
            retrieval_service=retrieval,
            chat_provider=recording_provider,
            claim_verifier=recording_verifier,
        )
        report = {
            "started_at": datetime.now(UTC).isoformat(),
            "draft_model": settings.chat_model,
            "draft_thinking": settings.chat_thinking_level,
            "verification_model": settings.verification_model,
            "draft_max_tokens": settings.chat_max_output_tokens,
            "verification_max_tokens": settings.verification_max_output_tokens,
            "thinking": settings.verification_thinking_level,
            "prompt_sha256": prompt_digest,
            "verification_prompt_sha256": verification_prompt_digest,
            "cases_sha256": cases_digest,
            "case_file_hashes": case_hashes,
            "case_ids": [case["id"] for case in cases],
            "implementation_sha256": {
                path: sha256(Path(path).read_bytes()).hexdigest()
                for path in (
                    "app/providers/llm.py", "app/services/chat.py",
                    "app/services/answer_validation.py", "app/services/claim_verification.py",
                    "app/services/conversation_context.py", "app/services/prompt_builder.py",
                    "app/services/retrieval.py",
                )
            },
            "cases": [],
        }

        def save_report() -> None:
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        completed_ids = set()
        if args.resume:
            previous = json.loads(args.output.read_text(encoding="utf-8"))
            for key in (
                "draft_model", "draft_thinking", "verification_model", "draft_max_tokens", "verification_max_tokens",
                "thinking", "prompt_sha256", "verification_prompt_sha256", "cases_sha256", "implementation_sha256", "case_ids",
            ):
                if previous.get(key) != report[key]:
                    parser.error(f"Cannot resume: {key} changed")
            report["cases"] = [
                case for case in previous["cases"]
                if "final_answer" in case or (case.get("error") and not case.get("provider_error"))
            ]
            completed_ids = {case["id"] for case in report["cases"]}
            report["started_at"] = previous["started_at"]
            report["interruptions"] = previous.get("interruptions", []) + [
                case for case in previous["cases"] if case.get("provider_error")
            ]
            print(f"Resuming: {len(completed_ids)} completed cases retained", flush=True)
        evidence_passed = 0
        answers_passed = 0
        provider_unavailable = False
        provider_failure = ""
        answers_attempted = len(completed_ids)
        evidence_passed = sum(not case["evidence_missing"] for case in report["cases"])
        answers_passed = sum("final_answer" in case and not case["automated_failures"] for case in report["cases"])
        for case in cases:
            if case["id"] in completed_ids:
                continue
            recording_provider.answers.clear()
            recording_provider.events = []
            recording_verifier.events = []
            recording_corrections.events = []
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
            resolved_question = resolve_question_context(question=case["question"], history=history)
            expanded_context = needs_expanded_context(resolved_question)
            results = retrieval.retrieve(
                conversation_id=CONVERSATION_ID, question=question,
                top_k=EXPANDED_CONTEXT_TOP_K if expanded_context else None,
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
            case_report = {
                "id": case["id"], "question": case["question"], "rubric": case.get("rubric"),
                "evidence_missing": missing,
                "retrieved": [
                    {"source_id": f"S{index}", "filename": chunk.filename, "page": chunk.page_number, "text": chunk.text}
                    for index, chunk in enumerate(results, start=1)
                ],
                "generation": recording_provider.events,
                "verification": recording_verifier.events,
                "corrections": recording_corrections.events,
            }
            # Each case owns its lists; resetting the recorder cannot erase earlier traces.
            report["cases"].append(case_report)
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
                case_report["skipped"] = True
                save_report()
                continue
            time.sleep(args.delay_seconds)
            current_digest = sha256(SYSTEM_PROMPT_PATH.read_bytes()).hexdigest()
            current_verification_digest = sha256(
                VERIFICATION_PROMPT_PATH.read_bytes()
            ).hexdigest()
            if (
                current_digest != prompt_digest
                or current_verification_digest != verification_prompt_digest
            ):
                raise RuntimeError("Prompt changed during evaluation; rerun for reproducible results.")

            # Reset messages per scenario, then seed only that fixture's supplied history.
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
                started = time.monotonic()
                answer = chat.chat(conversation_id=CONVERSATION_ID, question=case["question"])
            except InvalidModelResponseError as exc:
                answers_attempted += 1
                cause = str(exc.__cause__) if exc.__cause__ is not None else str(exc)
                case_report.update(error=cause, seconds=round(time.monotonic() - started, 2))
                case_report["generation"] = list(recording_provider.events)
                case_report["verification"] = list(recording_verifier.events)
                save_report()
                print(
                    "  answer checks: ['invalid model response after bounded correction: "
                    + cause.replace("'", "")
                    + "']",
                    flush=True,
                )
                for attempt, invalid_answer in enumerate(
                    recording_provider.answers,
                    start=1,
                ):
                    print(
                        f"  attempt {attempt}: {invalid_answer.status}: "
                        f"{invalid_answer.answer}",
                        flush=True,
                    )
                continue
            except ChatProviderRateLimitError:
                case_report.update(error="rate limited", provider_error=True, seconds=round(time.monotonic() - started, 2))
                case_report["generation"] = list(recording_provider.events)
                case_report["verification"] = list(recording_verifier.events)
                save_report()
                provider_unavailable = True
                provider_failure = "rate limited"
                print(
                    "  RATE LIMITED: this and remaining live scenarios skipped; "
                    "evidence checks continue.",
                    flush=True,
                )
                continue
            except ChatProviderError as exc:
                case_report.update(error=_safe_provider_failure(exc), provider_error=True, seconds=round(time.monotonic() - started, 2))
                case_report["generation"] = list(recording_provider.events)
                case_report["verification"] = list(recording_verifier.events)
                save_report()
                provider_unavailable = True
                provider_failure = _safe_provider_failure(exc)
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
            case_report.update(
                final_answer={"status": answer.status, "answer": answer.answer, "citations": [item.model_dump() for item in answer.citations]},
                automated_failures=failures, seconds=round(time.monotonic() - started, 2),
            )
            case_report["generation"] = list(recording_provider.events)
            case_report["verification"] = list(recording_verifier.events)
            save_report()
            print(f"  answer checks: {failures or 'PASS'}", flush=True)
            print(f"  {answer.status}: {answer.answer}", flush=True)
            print(f"  sources: {sorted(cited_files)}", flush=True)
        chat_logger.removeHandler(recording_corrections)
        report["summary"] = {
            "evidence_passed": evidence_passed, "total_cases": len(cases),
            "answers_completed": answers_attempted, "automated_passed": answers_passed,
            "skipped": len(cases) - answers_attempted,
            "provider_failure": provider_failure,
        }
        save_report()
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
