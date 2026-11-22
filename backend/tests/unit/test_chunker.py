
from app.modules.ingestion.processing.chunker import (
    SourceBlock,
    chunk_document,
)


def test_empty_document():
    assert chunk_document([]) == []


def test_single_block():
    blocks = [
        SourceBlock(
            text="Payment processing follows the bank policy.",
            block_index=0,
            section_title="Payments",
        )
    ]

    chunks = chunk_document(blocks)

    assert len(chunks) == 1
    assert "Payment processing" in chunks[0].content
    assert chunks[0].section_title == "Payments"


def test_preserves_page_number():
    blocks = [
        SourceBlock(
            text="This is page one.",
            block_index=0,
            page_number=1,
        )
    ]

    chunks = chunk_document(blocks)

    assert chunks[0].page_number == 1


def test_does_not_mix_pages():
    blocks = [
        SourceBlock("First page content.", 0, page_number=1),
        SourceBlock("Second page content.", 1, page_number=2),
    ]

    chunks = chunk_document(blocks)

    assert len(chunks) == 2
    assert chunks[0].page_number == 1
    assert chunks[1].page_number == 2


def test_does_not_mix_sections():
    blocks = [
        SourceBlock("Retail banking content.", 0, section_title="Retail"),
        SourceBlock("Cards content.", 1, section_title="Cards"),
    ]

    chunks = chunk_document(blocks)

    assert len(chunks) == 2
    assert chunks[0].section_title == "Retail"
    assert chunks[1].section_title == "Cards"


def test_chunk_size_limit():
    blocks = [
        SourceBlock(
            text=" ".join(["banking"] * 1200),
            block_index=0,
        )
    ]

    chunks = chunk_document(blocks, max_tokens=100, overlap_tokens=10)

    assert len(chunks) > 1
    assert all(chunk.token_count <= 100 for chunk in chunks)


def test_chunk_indexes_are_sequential():
    blocks = [
        SourceBlock(
            text=" ".join(["payment"] * 1000),
            block_index=0,
        )
    ]

    chunks = chunk_document(blocks, max_tokens=100)

    assert [chunk.chunk_index for chunk in chunks] == list(
        range(len(chunks))
    )


def test_invalid_chunk_configuration():
    blocks = []

    try:
        chunk_document(blocks, max_tokens=100, overlap_tokens=100)
        assert False, "Expected ValueError"
    except ValueError:
        pass
