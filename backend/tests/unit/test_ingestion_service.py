
from app.modules.ingestion.processing.ingestion_service import (
    process_source_blocks,
    prepare_source_blocks,
)
from app.modules.ingestion.processing.chunker import SourceBlock


def test_normalizes_source_blocks():
    blocks = [
        SourceBlock(
            text="  Payment   processing  ",
            block_index=0,
            section_title="Payments",
        )
    ]

    result = prepare_source_blocks(blocks)

    assert result[0].text == "Payment processing"


def test_skips_empty_blocks():
    blocks = [
        SourceBlock(text="   ", block_index=0),
        SourceBlock(text="Valid content.", block_index=1),
    ]

    result = prepare_source_blocks(blocks)

    assert len(result) == 1
    assert result[0].block_index == 1


def test_processes_document():
    blocks = [
        SourceBlock(
            text="Banking payment policy.",
            block_index=0,
            section_title="Payments",
            page_number=1,
        )
    ]

    result = process_source_blocks(
        document_name="payments.pdf",
        file_type="pdf",
        blocks=blocks,
    )

    assert result.document_name == "payments.pdf"
    assert result.file_type == "pdf"
    assert result.total_chunks == 1
    assert result.total_tokens > 0


def test_preserves_source_metadata():
    blocks = [
        SourceBlock(
            text="Card transaction policy.",
            block_index=4,
            section_title="Card Operations",
            page_number=3,
        )
    ]

    result = process_source_blocks(
        "cards.pdf",
        "pdf",
        blocks,
    )

    chunk = result.chunks[0]

    assert chunk.page_number == 3
    assert chunk.section_title == "Card Operations"
    assert chunk.source_block_start == 4
    assert chunk.source_block_end == 4
