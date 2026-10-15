"""Check supplied-PDF extraction and rejection of malformed, encrypted or textless input."""

from pathlib import Path
from io import BytesIO

import pytest
from pypdf import PdfWriter

from app.services.pdf_parser import PdfParseError, parse_pdf


POLICIES = Path("data/sampleset_policies/sampleset_policies")


def test_all_supplied_policies_have_page_numbered_extractable_text() -> None:
    policy_paths = sorted(POLICIES.glob("*.pdf"))

    assert len(policy_paths) == 8
    for policy_path in policy_paths:
        parsed = parse_pdf(policy_path.read_bytes())
        assert parsed.page_count >= 1
        assert parsed.pages
        assert all(page.page_number >= 1 and page.text for page in parsed.pages)


def test_malformed_pdf_is_rejected() -> None:
    with pytest.raises(PdfParseError, match="unreadable or malformed"):
        parse_pdf(b"%PDF-this-is-not-a-real-pdf")


def _blank_pdf(*, encrypted: bool = False) -> bytes:
    output = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    if encrypted:
        writer.encrypt("secret")
    writer.write(output)
    return output.getvalue()


def test_empty_text_pdf_is_rejected() -> None:
    with pytest.raises(PdfParseError, match="no extractable text"):
        parse_pdf(_blank_pdf())


def test_encrypted_pdf_is_rejected() -> None:
    with pytest.raises(PdfParseError, match="Encrypted PDFs"):
        parse_pdf(_blank_pdf(encrypted=True))
