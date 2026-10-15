"""Evaluate the live semantic verifier against fixed good and bad candidates.

The default calibration set is synthetic; --case-file also accepts saved drafts.
Fixed evidence and candidates isolate auditing from retrieval and draft generation.
"""

import argparse
import json
import time
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from app.config import Settings
from app.providers.llm import (
    ChatProviderError,
    GeminiClaimVerifier,
    InvalidModelResponseError,
    ModelAnswer,
)
from app.providers.vector_store import RetrievedChunk
from app.services.answer_validation import validate_citations
from app.services.claim_verification import (
    VERIFICATION_PROMPT_PATH,
    build_verification_messages,
    require_verified_answer,
)
from app.services.prompt_builder import HistoryMessage


DEFAULT_CASE_PATH = Path("evaluation/verifier_calibration_cases.json")
RETIRED_CASE_IDS = frozenset(
    json.loads(Path("evaluation/retired_case_ids.json").read_text(encoding="utf-8"))
)


def _safe_provider_failure(exc: ChatProviderError) -> str:
    """Summarize exception types/statuses without exposing the provider payload."""

    cause = exc.__cause__
    if cause is None:
        return type(exc).__name__
    status = getattr(cause, "code", None) or getattr(cause, "status_code", None)
    provider_status = getattr(cause, "status", None)
    details = [type(exc).__name__, type(cause).__name__]
    if status is not None:
        details.append(f"status={status}")
    if provider_status is not None:
        details.append(f"provider_status={provider_status}")
    return "/".join(details)


def _evidence(case_id: str, sources: list[dict[str, object]]) -> list[RetrievedChunk]:
    """Adapt fixed fixture passages to retrieval records without searching a corpus."""

    return [
        RetrievedChunk(
            id=f"{case_id}-chunk-{index}",
            text=str(source["text"]),
            conversation_id="verifier-calibration",
            document_id=f"{case_id}-document-{index}",
            filename=str(source["filename"]),
            page_number=int(source.get("page", 1)),
            chunk_index=0,
            distance=0.0,
            similarity=1.0,
        )
        for index, source in enumerate(sources, start=1)
    ]


def _authority(
    case_id: str,
    sources: list[dict[str, object]],
) -> dict[str, dict[str, object]]:
    """Map optional fixture authority records to the same IDs used by _evidence."""

    return {
        f"{case_id}-document-{index}": dict(source["authority"])
        for index, source in enumerate(sources, start=1)
        if source.get("authority")
    }


def main() -> None:
    """Validate fixture citations locally, or use --live to compare Gemini audit gates.

    Optional reports retain verdicts and token usage; fixed evidence isolates the
    verifier from retrieval and draft generation, not from its own reasoning errors.
    """

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--case-file", type=Path, default=DEFAULT_CASE_PATH)
    parser.add_argument("--case", action="append", help="Run only these case IDs")
    parser.add_argument("--output", type=Path, help="Save live verdicts for manual review")
    parser.add_argument(
        "--delay-seconds",
        type=float,
        default=12,
        help="Space live verifier calls to reduce quota bursts",
    )
    args = parser.parse_args()
    if args.delay_seconds < 0:
        parser.error("--delay-seconds must not be negative")
    if not args.case_file.is_file():
        parser.error(f"Case file does not exist: {args.case_file}")

    cases = json.loads(args.case_file.read_text(encoding="utf-8"))
    retired = {case["id"] for case in cases if case["id"] in RETIRED_CASE_IDS}
    cases = [case for case in cases if case["id"] not in RETIRED_CASE_IDS]
    if retired:
        print(f"Retired cases excluded: {sorted(retired)}", flush=True)
    if set(args.case or []) & RETIRED_CASE_IDS:
        parser.error("Requested case is retired and will not be run")
    if args.case:
        requested = set(args.case)
        known = {case["id"] for case in cases}
        unknown = requested - known
        if unknown:
            parser.error(f"Unknown cases: {sorted(unknown)}")
        cases = [case for case in cases if case["id"] in requested]

    settings = Settings()
    if args.live and not settings.gemini_api_key:
        parser.error("Live checks require ADC_GEMINI_API_KEY in .env.")
    verifier = GeminiClaimVerifier(
        api_key=(
            settings.gemini_api_key.get_secret_value()
            if args.live and settings.gemini_api_key
            else None
        ),
        model=settings.verification_model,
        max_tokens=settings.verification_max_output_tokens,
        timeout_seconds=settings.chat_timeout_seconds,
        thinking_level=settings.verification_thinking_level,
    )

    prompt_digest = sha256(VERIFICATION_PROMPT_PATH.read_bytes()).hexdigest()
    case_digest = sha256(args.case_file.read_bytes()).hexdigest()
    print(
        f"Verification model: {settings.verification_model}; "
        f"thinking={settings.verification_thinking_level}; live={args.live}",
        flush=True,
    )
    print(f"Verification prompt SHA256: {prompt_digest}", flush=True)
    print(f"Cases SHA256: {case_digest}", flush=True)

    passed = 0
    completed = 0
    report = {
        "started_at": datetime.now(UTC).isoformat(),
        "model": settings.verification_model, "thinking": settings.verification_thinking_level,
        "max_output_tokens": settings.verification_max_output_tokens,
        "provider_sha256": sha256(Path("app/providers/llm.py").read_bytes()).hexdigest(),
        "prompt_sha256": prompt_digest, "cases_sha256": case_digest, "cases": [],
    }

    def save_report() -> None:
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    for case in cases:
        answer = ModelAnswer.model_validate({
            key: case["candidate_answer"][key] for key in ("status", "answer")
        })
        evidence = _evidence(case["id"], case["sources"])
        # Keep this a verifier-only calibration. Bad semantic candidates must reach
        # the verifier, while their citation markers must still reference fixture sources.
        validate_citations(answer, evidence)
        if not args.live:
            print(f"[{case['id']}] VALID", flush=True)
            continue

        time.sleep(args.delay_seconds)
        started = time.monotonic()
        case_report = {"id": case["id"], "expected": case["expected_verdict"]}
        report["cases"].append(case_report)
        try:
            verification = verifier.verify(
                build_verification_messages(
                    question=case["question"],
                    answer=answer,
                    evidence=evidence,
                    authority_by_document=_authority(case["id"], case["sources"]),
                    history=[HistoryMessage(**message) for message in case.get("history", [])],
                )
            )
            raw_verdict = verification.verdict
            try:
                require_verified_answer(verification, answer=answer)
                gate_result = "pass"
            except InvalidModelResponseError:
                gate_result = "revise"
        except InvalidModelResponseError as exc:
            case_report.update(error=str(exc), seconds=round(time.monotonic() - started, 2))
            save_report()
            completed += 1
            elapsed = time.monotonic() - started
            print(
                f"[{case['id']}] FAIL: expected={case['expected_verdict']}; "
                f"result=invalid_output; seconds={elapsed:.2f}; {exc}",
                flush=True,
            )
            continue
        except ChatProviderError as exc:
            case_report.update(error=_safe_provider_failure(exc), seconds=round(time.monotonic() - started, 2))
            save_report()
            print(
                f"[{case['id']}] PROVIDER ERROR: {_safe_provider_failure(exc)}",
                flush=True,
            )
            break

        completed += 1
        expected = case["expected_verdict"]
        case_passed = gate_result == expected
        passed += case_passed
        elapsed = time.monotonic() - started
        case_report.update(verdict=verification.model_dump(), gate=gate_result, passed=case_passed, seconds=round(elapsed, 2), usage=verifier.last_usage)
        save_report()
        print(
            f"[{case['id']}] {'PASS' if case_passed else 'FAIL'}: "
            f"expected={expected}; raw={raw_verdict}; gate={gate_result}; "
            f"seconds={elapsed:.2f}",
            flush=True,
        )
        if verification.issues:
            print(
                "  issues: "
                + "; ".join(
                    f"{issue.category}: {issue.description}"
                    for issue in verification.issues
                ),
                flush=True,
            )

    if args.live:
        report["summary"] = {
            "completed": completed, "passed": passed, "total_cases": len(cases),
            "not_completed": len(cases) - completed,
        }
        save_report()
        print(f"Verifier calibration: {passed}/{completed} completed", flush=True)
        if completed != len(cases) or passed != completed:
            raise SystemExit(1)
    else:
        print(f"Validated calibration cases: {len(cases)}/{len(cases)}", flush=True)


if __name__ == "__main__":
    main()
