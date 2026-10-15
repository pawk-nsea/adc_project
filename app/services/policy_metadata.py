"""Extract policy identity/lifecycle signals and resolve retrieved-document relationships."""

import re
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from typing import Any

from app.services.pdf_parser import ParsedPage


AUTHORITY_METADATA_VERSION = "authority-v4"

_IDENTITY_STOPWORDS = {
    "a",
    "an",
    "and",
    "code",
    "comprehensive",
    "document",
    "for",
    "guidance",
    "guideline",
    "guidelines",
    "interim",
    "manual",
    "memo",
    "memorandum",
    "of",
    "policy",
    "procedure",
    "standard",
    "standards",
    "temporary",
    "the",
}


@dataclass(frozen=True)
class PolicyAuthorityMetadata:
    """Document identity and lifecycle facts; relationships are resolved later."""

    title: str
    document_type: str
    policy_id: str | None
    version: str | None
    effective_date: str | None
    lifecycle_signal: str
    supersedes_prior_versions: bool
    pending_comprehensive_policy: bool
    relationship_target: str | None
    subject_terms: tuple[str, ...]
    authority_state: str = "unspecified"
    authority_reason: str | None = None
    metadata_version: str = AUTHORITY_METADATA_VERSION

    def to_dict(self) -> dict[str, Any]:
        """Convert immutable metadata into a JSON-compatible database/prompt record."""

        value = asdict(self)
        value["subject_terms"] = list(self.subject_terms)
        return value

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "PolicyAuthorityMetadata":
        """Read stored metadata, accepting legacy fields until the PDF is refreshed."""

        # `topics` is accepted only to keep older stored metadata readable until
        # a retained PDF can be lazily re-extracted with the current format.
        legacy_terms = value.get("topics") or []
        return cls(
            title=str(value.get("title") or "Untitled policy document"),
            document_type=str(value.get("document_type") or "unknown"),
            policy_id=_optional_string(value.get("policy_id")),
            version=_optional_string(value.get("version")),
            effective_date=_optional_string(value.get("effective_date")),
            lifecycle_signal=str(value.get("lifecycle_signal") or "unspecified"),
            supersedes_prior_versions=bool(value.get("supersedes_prior_versions")),
            pending_comprehensive_policy=bool(value.get("pending_comprehensive_policy")),
            relationship_target=_optional_string(value.get("relationship_target")),
            subject_terms=tuple(
                str(term) for term in value.get("subject_terms") or legacy_terms
            ),
            authority_state=str(value.get("authority_state") or "unspecified"),
            authority_reason=_optional_string(value.get("authority_reason")),
            metadata_version=str(value.get("metadata_version") or "authority-v1"),
        )


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _field(text: str, labels: tuple[str, ...]) -> str | None:
    label_pattern = "|".join(re.escape(label) for label in labels)
    match = re.search(rf"^(?:{label_pattern})\s*:\s*([^\n]+)$", text, re.I | re.M)
    return match.group(1).strip() if match else None


def _normalized_date(value: str | None) -> str | None:
    """Normalize recognized dates; keep unknown formats as text, with no date ordering."""

    if value is None:
        return None
    cleaned = value.strip()
    for pattern in (
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d %B %Y",
        "%B %d, %Y",
        "%B %Y",
        "%d %b %Y",
        "%b %d, %Y",
        "%b %Y",
    ):
        try:
            parsed = datetime.strptime(cleaned, pattern)
            if "%d" not in pattern:
                # Month-only dates use day one for sorting; this is not an exact date.
                parsed = parsed.replace(day=1)
            return parsed.date().isoformat()
        except ValueError:
            continue
    return cleaned


def _subject_terms(text: str) -> tuple[str, ...]:
    """Derive relationship vocabulary from document text, not a fixed taxonomy."""

    terms = {
        token
        for token in re.findall(r"[a-z][a-z0-9-]{2,}", text.casefold())
        if token not in _IDENTITY_STOPWORDS
    }
    return tuple(sorted(terms))


def _has_sortable_date(metadata: PolicyAuthorityMetadata) -> bool:
    return bool(
        metadata.effective_date
        and re.fullmatch(r"\d{4}-\d{2}-\d{2}", metadata.effective_date)
    )


def _relationship_target(text: str) -> str | None:
    """Extract the named destination of an interim/temporary lifecycle."""

    patterns = (
        r"\bpending\b.{0,100}?\bcomprehensive\s+"
        r"([a-z][a-z0-9 &/\-]{1,80}?(?:policy|standard|code|manual|guidelines?))\b",
        r"\b(?:until|pending)\b.{0,100}?\b(?:release|issuance|publication|"
        r"adoption|approval)\s+of\s+(?:a|the)\s+"
        r"([a-z][a-z0-9 &/\-]{1,80}?(?:policy|standard|code|manual|guidelines?))\b",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.I | re.S)
        if match:
            return re.sub(r"\s+", " ", match.group(1)).strip(" .")
    return None


def extract_policy_authority(pages: list[ParsedPage]) -> PolicyAuthorityMetadata:
    """Read title, labeled identity/date fields and lifecycle wording from PDF text.

    Missing fields stay unset. Scope/geography are left in policy text for the
    models to interpret; extraction does not establish a document's authority.
    """

    text = "\n".join(page.text for page in pages)
    title = next(
        (line.strip() for line in text.splitlines() if line.strip()),
        "Untitled policy document",
    )
    lower_title = title.casefold()
    policy_id = _field(text, ("Policy ID", "Policy Number", "Reference", "Ref"))
    version = _field(text, ("Version", "Revision"))
    effective_date = _normalized_date(
        _field(text, ("Effective Date", "Effective", "Date"))
    )

    if "memo" in lower_title or "memorandum" in lower_title:
        document_type = "memo"
    elif "guideline" in lower_title or "guidance" in lower_title:
        document_type = "guideline"
    elif "policy" in lower_title or "code" in lower_title:
        document_type = "policy"
    elif "standard" in lower_title:
        document_type = "standard"
    elif "manual" in lower_title:
        document_type = "manual"
    else:
        document_type = "unknown"

    relationship_target = _relationship_target(text)
    pending_comprehensive = bool(
        relationship_target
        or re.search(
            r"\b(?:interim|temporary)\b.{0,180}\bpending\b.{0,180}"
            r"\b(?:policy|standard|code|manual|guidelines?)\b",
            text,
            re.I | re.S,
        )
    )
    if pending_comprehensive or re.search(r"\btemporary measures?\b", text, re.I):
        lifecycle_signal = "interim"
    elif re.search(r"\b(?:historical|obsolete|withdrawn|expired)\b", text, re.I):
        lifecycle_signal = "historical_signal"
    else:
        lifecycle_signal = "unspecified"

    supersedes_prior = bool(
        re.search(
            r"\b(?:supersedes?|replaces?)\b.{0,80}"
            r"\b(?:all\s+)?(?:prior|previous|earlier|older)\b|"
            r"\b(?:prior|previous|earlier|older)\b.{0,80}"
            r"\b(?:versions?|editions?|polic(?:y|ies)|documents?)\b.{0,40}"
            r"\b(?:are\s+)?(?:superseded|replaced)\b",
            text,
            re.I | re.S,
        )
    )
    identity_text = " ".join(item for item in (title, policy_id or "") if item)
    return PolicyAuthorityMetadata(
        title=title,
        document_type=document_type,
        policy_id=policy_id,
        version=version,
        effective_date=effective_date,
        lifecycle_signal=lifecycle_signal,
        supersedes_prior_versions=supersedes_prior,
        pending_comprehensive_policy=pending_comprehensive,
        relationship_target=relationship_target,
        subject_terms=_subject_terms(identity_text),
    )


def _matches_interim_target(
    interim: PolicyAuthorityMetadata,
    candidate: PolicyAuthorityMetadata,
) -> bool:
    """Use shared title/ID words as a heuristic match for an interim successor."""

    target_terms = set(_subject_terms(interim.relationship_target or ""))
    if not target_terms:
        target_terms = set(interim.subject_terms)
    return bool(target_terms.intersection(candidate.subject_terms))


def resolve_policy_authority(
    metadata_by_document: dict[str, PolicyAuthorityMetadata],
) -> dict[str, PolicyAuthorityMetadata]:
    """Return annotated copies using only the supplied documents' metadata.

    Same-ID replacement needs sortable dates and explicit supersession wording.
    Interim succession uses a dated title/ID-word match; it can match too broadly.
    This does not check every uploaded policy, future dates or employee scope.
    """

    resolved = dict(metadata_by_document)
    groups: dict[str, list[tuple[str, PolicyAuthorityMetadata]]] = {}
    for document_id, metadata in metadata_by_document.items():
        if metadata.policy_id:
            groups.setdefault(metadata.policy_id.casefold(), []).append(
                (document_id, metadata)
            )

    for group in groups.values():
        dated = [item for item in group if _has_sortable_date(item[1])]
        if len(dated) < 2:
            continue
        dated.sort(key=lambda item: item[1].effective_date or "")
        current_id, current = dated[-1]
        if not current.supersedes_prior_versions:
            # A later date alone does not establish that older rules were replaced.
            continue
        resolved[current_id] = replace(
            current,
            authority_state="governing_explicit_supersession",
            authority_reason=(
                f"Latest retrieved version of policy ID {current.policy_id}; "
                "the document explicitly supersedes prior versions."
            ),
        )
        for historical_id, historical in dated[:-1]:
            resolved[historical_id] = replace(
                historical,
                authority_state="historical_explicitly_superseded",
                authority_reason=(
                    f"A later retrieved version of policy ID {current.policy_id} "
                    "explicitly supersedes prior versions."
                ),
            )

    for interim_id, interim in metadata_by_document.items():
        # This is a lifecycle hint for both readers, not a rule-by-rule conflict test.
        if not interim.pending_comprehensive_policy:
            continue
        candidates = [
            (document_id, metadata)
            for document_id, metadata in metadata_by_document.items()
            if document_id != interim_id
            and metadata.document_type in {"policy", "standard", "code", "manual"}
            and _matches_interim_target(interim, metadata)
            and _has_sortable_date(metadata)
            and (
                not interim.effective_date
                or metadata.effective_date > interim.effective_date
            )
        ]
        if not candidates:
            continue
        current_id, current = max(
            candidates,
            key=lambda item: item[1].effective_date or "",
        )
        resolved[interim_id] = replace(
            resolved[interim_id],
            authority_state="historical_interim",
            authority_reason=(
                "The document says it is interim pending "
                f"{interim.relationship_target or 'a later governing document'}, and "
                f"the retrieved evidence includes {current.title}."
            ),
        )
        if resolved[current_id].authority_state == "unspecified":
            resolved[current_id] = replace(
                current,
                authority_state="governing_lifecycle_successor",
                authority_reason=(
                    f"This document matches the lifecycle target named by {interim.title}."
                ),
            )

    return resolved
