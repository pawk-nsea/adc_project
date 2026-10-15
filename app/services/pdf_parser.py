"""Extract readable PDF text for ingestion while retaining original page numbers."""

import re
from dataclasses import dataclass
from io import BytesIO

from pypdf import PdfReader
from pypdf.errors import PdfReadError


class PdfParseError(ValueError):
    """Raised when a PDF cannot safely produce usable text."""


@dataclass(frozen=True)
class ParsedPage:
    """Pair extracted text with its original one-based PDF page number."""

    page_number: int
    text: str


@dataclass(frozen=True)
class ParsedPdf:
    """Total PDF page count plus only the pages containing extractable text."""

    page_count: int
    pages: list[ParsedPage]


def _normalize_page_text(text: str) -> str:
    """Normalize extraction noise while retaining lines and paragraphs."""

    normalized_lines = [
        re.sub(r"[\t ]+", " ", line).strip()
        for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    ]
    text_with_breaks = "\n".join(normalized_lines)
    return re.sub(r"\n{3,}", "\n\n", text_with_breaks).strip()


def parse_pdf(content: bytes) -> ParsedPdf:
    """Read PDF bytes without OCR, skipping empty pages but keeping their numbering.

    Raise PdfParseError for encryption, unreadable input or no extractable text.
    Text extraction does not reconstruct table or column layout.
    """

    try:
        reader = PdfReader(BytesIO(content))
        if reader.is_encrypted:
            raise PdfParseError("Encrypted PDFs are not supported.")

        pages = []
        for page_number, page in enumerate(reader.pages, start=1):
            text = _normalize_page_text(page.extract_text() or "")
            if text:
                pages.append(ParsedPage(page_number=page_number, text=text))
    except PdfParseError:
        raise
    except (PdfReadError, OSError, ValueError) as exc:
        raise PdfParseError("The PDF is unreadable or malformed.") from exc

    if not pages:
        raise PdfParseError("The PDF contains no extractable text; OCR is not enabled.")
    return ParsedPdf(page_count=len(reader.pages), pages=pages)
