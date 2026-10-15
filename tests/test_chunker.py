"""Check deterministic chunk IDs, page boundaries and token windows using a fake counter."""

from app.services.chunker import create_chunks
from app.services.pdf_parser import ParsedPage
from tests.conftest import FakeEmbeddingProvider


def test_chunks_are_page_local_stable_and_within_token_limit() -> None:
    counter = FakeEmbeddingProvider()
    pages = [
        ParsedPage(1, " ".join(f"alpha{i}" for i in range(18))),
        ParsedPage(2, " ".join(f"beta{i}" for i in range(9))),
    ]

    chunks = create_chunks(
        pages,
        document_id="doc-1",
        conversation_id="conversation-1",
        filename="policy.pdf",
        counter=counter,
        target_tokens=10,
        max_tokens=13,
        overlap_tokens=3,
    )

    assert [chunk.page_number for chunk in chunks] == [1, 1, 1, 2, 2]
    assert chunks[0].id == "doc-1:p0001:c0000"
    assert chunks[-1].id == "doc-1:p0002:c0001"
    assert all(counter.count_tokens(chunk.text) <= 13 for chunk in chunks)
    assert all("alpha" not in chunk.text for chunk in chunks if chunk.page_number == 2)
    assert all("beta" not in chunk.text for chunk in chunks if chunk.page_number == 1)
    for source_token in pages[0].text.split():
        assert any(source_token in chunk.text.split() for chunk in chunks)
    for source_token in pages[1].text.split():
        assert any(source_token in chunk.text.split() for chunk in chunks)


def test_invalid_chunk_settings_are_rejected() -> None:
    counter = FakeEmbeddingProvider()

    try:
        create_chunks(
            [ParsedPage(1, "text")],
            document_id="doc",
            conversation_id="conversation",
            filename="policy.pdf",
            counter=counter,
            target_tokens=10,
            max_tokens=10,
            overlap_tokens=10,
        )
    except ValueError as exc:
        assert "overlap < target <= max" in str(exc)
    else:
        raise AssertionError("Expected invalid chunk settings to fail")
