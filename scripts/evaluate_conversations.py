"""Record real multi-turn answer regressions for manual semantic review.

Without --live, validate fixtures only. Live runs use sample PDFs and temporary
storage, preserving actual prior answers rather than synthetic assistant history.
"""

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

# Direct script execution puts scripts/ on sys.path, so expose the repository root
# before reusing the existing evaluation recorders below.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import Settings
from app.database import Database
from app.providers.embeddings import OnnxMiniLmEmbeddingProvider
from app.providers.llm import ChatProviderError, GeminiChatProvider, GeminiClaimVerifier
from app.providers.vector_store import ChromaVectorStore
from app.services.chat import ChatService
from app.services.ingestion import IngestionService
from app.services.retrieval import RetrievalService
from scripts.evaluate_policy_answers import RecordingChatProvider, RecordingVerifier


CASE_PATH = Path("evaluation/conversation_answer_cases.json")
POLICY_DIRECTORY = Path("data/sampleset_policies/sampleset_policies")


def main() -> None:
    """Run selected conversations; record errors, drafts and audits without auto-grading."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--case", action="append")
    parser.add_argument("--case-file", type=Path, default=CASE_PATH)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--delay-seconds", type=float, default=2)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.repeat < 1 or args.delay_seconds < 0:
        parser.error("Repeat must be positive and delay nonnegative.")
    if not args.case_file.is_file():
        parser.error(f"Case file does not exist: {args.case_file}")
    cases = json.loads(args.case_file.read_text(encoding="utf-8"))
    known = {case["id"] for case in cases}
    if len(known) != len(cases) or set(args.case or []) - known:
        parser.error("Case IDs must be unique and requested IDs must exist.")
    cases = [c for c in cases if not args.case or c["id"] in args.case]
    if any(
        not case["turns"] or any(
            not turn["question"].strip() or not turn["rubric"].strip()
            for turn in case["turns"]
        )
        for case in cases
    ):
        parser.error("Each conversation needs nonempty questions and review rubrics.")
    if not args.live:
        print(f"Validated {len(cases)} conversation fixtures; no model calls.")
        return

    settings = Settings()
    if not settings.gemini_api_key:
        parser.error("Live runs require ADC_GEMINI_API_KEY.")
    provider = RecordingChatProvider(GeminiChatProvider(
        api_key=settings.gemini_api_key.get_secret_value(), model=settings.chat_model,
        temperature=settings.chat_temperature, max_tokens=settings.chat_max_output_tokens,
        timeout_seconds=settings.chat_timeout_seconds,
        thinking_level=settings.chat_thinking_level,
    ))
    verifier = RecordingVerifier(GeminiClaimVerifier(
        api_key=settings.gemini_api_key.get_secret_value(), model=settings.verification_model,
        max_tokens=settings.verification_max_output_tokens,
        timeout_seconds=settings.chat_timeout_seconds, thinking_level=settings.verification_thinking_level,
    ))
    report = {
        "started_at": datetime.now(UTC).isoformat(),
        "generation_model": settings.chat_model,
        "generation_thinking": settings.chat_thinking_level,
        "verification_model": settings.verification_model,
        "thinking": settings.verification_thinking_level,
        "cases_sha256": sha256(args.case_file.read_bytes()).hexdigest(),
        "source_sha256": {
            str(path): sha256(path.read_bytes()).hexdigest()
            for path in sorted(Path("app").rglob("*"))
            if path.suffix in {".py", ".txt"}
        },
        "episodes": [],
    }

    def save_report() -> None:
        """Write the current episode results when an output path was requested."""

        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    with TemporaryDirectory(prefix="adc-conversation-answers-") as directory:
        database = Database(f"sqlite:///{directory}/app.db")
        database.create_tables()
        embeddings = OnnxMiniLmEmbeddingProvider(
            settings.model_cache_path, settings.embedding_model_name,
            settings.embedding_dimension,
        )
        vectors = ChromaVectorStore(f"{directory}/chroma", settings.vector_collection_name)
        ingestion = IngestionService(
            database=database, embedding_provider=embeddings,
            vector_store=vectors, settings=settings,
        )
        retrieval = RetrievalService(
            embedding_provider=embeddings, vector_store=vectors,
            default_top_k=settings.retrieval_top_k,
        )
        chat = ChatService(
            database=database, retrieval_service=retrieval,
            chat_provider=provider, claim_verifier=verifier,
        )
        try:
            for repeat in range(args.repeat):
                for case in cases:
                    workspace = f"{case['id']}-{repeat}"
                    for policy in sorted(POLICY_DIRECTORY.glob("*.pdf")):
                        ingestion.ingest(
                            conversation_id=workspace, filename=policy.name,
                            content=policy.read_bytes(),
                        )
                    episode = {"id": case["id"], "repeat": repeat + 1, "turns": []}
                    report["episodes"].append(episode)
                    for turn in case["turns"]:
                        provider.events = []
                        verifier.events = []
                        record = {**turn, "generation": provider.events, "verification": verifier.events}
                        episode["turns"].append(record)
                        time.sleep(args.delay_seconds)
                        started = time.monotonic()
                        try:
                            answer = chat.chat(conversation_id=workspace, question=turn["question"])
                            record["answer"] = {"status": answer.status, "answer": answer.answer,
                                                "citations": [c.model_dump() for c in answer.citations]}
                            print(f"[{workspace}] {answer.status}: {answer.answer}", flush=True)
                        except ChatProviderError as exc:
                            record["error"] = str(exc)
                            print(f"[{workspace}] {type(exc).__name__}: {exc}", flush=True)
                        record["seconds"] = round(time.monotonic() - started, 3)
                        save_report()
        finally:
            database.close()
    print("Conversations recorded; review every answer and audit against its rubric.")


if __name__ == "__main__":
    main()
