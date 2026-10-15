"""Check document-derived metadata and explicit replacement/interim relationship resolution."""

from pathlib import Path

from app.services.pdf_parser import ParsedPage, parse_pdf
from app.services.policy_metadata import (
    extract_policy_authority,
    resolve_policy_authority,
)


POLICY_DIRECTORY = Path("data/sampleset_policies/sampleset_policies")


def _metadata(filename: str):
    parsed = parse_pdf((POLICY_DIRECTORY / filename).read_bytes())
    return extract_policy_authority(parsed.pages)


def _synthetic(text: str):
    return extract_policy_authority([ParsedPage(page_number=1, text=text)])


def test_extracts_policy_identity_and_supersession_signals() -> None:
    current = _metadata("reimbursement_2025.pdf")

    assert current.policy_id == "FIN-T&E-001"
    assert current.version == "3.2"
    assert current.effective_date == "2025-01-01"
    assert current.supersedes_prior_versions is True
    assert {"travel", "expense", "reimbursement"} <= set(current.subject_terms)


def test_subject_terms_are_derived_from_identity_without_fixed_policy_categories() -> None:
    metadata = _synthetic(
        "Orbital Greenhouse Access Manual\n"
        "Reference: AST-BOT-77\n"
        "Effective Date: 2026-04-12"
    )

    assert {"orbital", "greenhouse", "access", "ast-bot-77"} <= set(
        metadata.subject_terms
    )
    assert metadata.document_type == "manual"


def test_resolves_same_policy_versions_only_with_identity_and_explicit_supersession() -> None:
    old = _synthetic(
        "Polar Field Allowance Policy\nPolicy ID: OPS-POLAR-9\n"
        "Version: 1.0\nEffective Date: 2025-01-01"
    )
    current = _synthetic(
        "Polar Field Allowance Policy\nPolicy ID: OPS-POLAR-9\n"
        "Version: 2.0\nEffective Date: 2026-01-01\n"
        "This policy supersedes all prior versions."
    )

    resolved = resolve_policy_authority({"old": old, "current": current})

    assert resolved["old"].authority_state == "historical_explicitly_superseded"
    assert resolved["current"].authority_state == "governing_explicit_supersession"
    assert "explicitly supersedes" in (resolved["old"].authority_reason or "")


def test_newer_date_without_explicit_relationship_does_not_establish_authority() -> None:
    old = _synthetic(
        "Coastal Sensor Policy\nPolicy ID: LAB-2\nEffective Date: 2025-01-01"
    )
    newer = _synthetic(
        "Coastal Sensor Policy\nPolicy ID: LAB-2\nEffective Date: 2026-01-01"
    )

    resolved = resolve_policy_authority({"old": old, "newer": newer})

    assert resolved["old"].authority_state == "unspecified"
    assert resolved["newer"].authority_state == "unspecified"


def test_resolves_unfamiliar_interim_lifecycle_from_named_target() -> None:
    interim = _synthetic(
        "Temporary Observatory Access Guidance\n"
        "Effective Date: 1 March 2024\n"
        "This is interim guidance pending the release of a comprehensive "
        "observatory safety policy."
    )
    governing = _synthetic(
        "Observatory Safety Policy\nPolicy ID: OBS-SAFE-1\n"
        "Effective Date: 2025-06-01"
    )

    resolved = resolve_policy_authority(
        {"interim": interim, "governing": governing}
    )

    assert interim.relationship_target == "observatory safety policy"
    assert resolved["interim"].authority_state == "historical_interim"
    assert resolved["governing"].authority_state == "governing_lifecycle_successor"
    assert "supersed" not in (resolved["interim"].authority_reason or "").casefold()


def test_interim_does_not_match_unrelated_later_policy() -> None:
    interim = _synthetic(
        "Temporary Observatory Access Guidance\n"
        "Effective Date: 1 March 2024\n"
        "Interim guidance pending the release of a comprehensive observatory "
        "safety policy."
    )
    unrelated = _synthetic(
        "Marine Catering Policy\nEffective Date: 2026-01-01"
    )

    resolved = resolve_policy_authority(
        {"interim": interim, "unrelated": unrelated}
    )

    assert resolved["interim"].authority_state == "unspecified"
    assert resolved["unrelated"].authority_state == "unspecified"
