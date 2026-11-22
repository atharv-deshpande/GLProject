
from app.modules.ingestion.processing.ingestion_service import (
    pdf_to_source_blocks,
    docx_to_source_blocks,
    html_to_source_blocks,
    process_parsed_document,
)

from app.modules.ingestion.parsers.pdf_parser import (
    ParsedDocument,
    ParsedPage,
)

from app.modules.ingestion.parsers.docx_parser import (
    ParsedDocx,
    ParsedBlock,
)

from app.modules.ingestion.parsers.html_parser import (
    ParsedHTML,
    ParsedHTMLBlock,
)


def test_pdf_adapter_preserves_page_numbers():
    document = ParsedDocument(
        document_name="policy.pdf",
        file_type="pdf",
        total_pages=2,
        pages=[
            ParsedPage(1, "First page content.", False),
            ParsedPage(2, "Second page content.", False),
        ],
    )

    blocks = pdf_to_source_blocks(document)

    assert len(blocks) == 2
    assert blocks[0].page_number == 1
    assert blocks[1].page_number == 2


def test_docx_adapter_preserves_section_and_block():
    document = ParsedDocx(
        document_name="policy.docx",
        file_type="docx",
        blocks=[
            ParsedBlock(
                block_index=3,
                block_type="paragraph",
                text="Payment policy.",
                section_title="Payments",
            )
        ],
    )

    blocks = docx_to_source_blocks(document)

    assert blocks[0].block_index == 3
    assert blocks[0].section_title == "Payments"
    assert blocks[0].page_number is None


def test_html_adapter_preserves_heading_context():
    document = ParsedHTML(
        document_name="policy.html",
        file_type="html",
        title="Bank Policy",
        blocks=[
            ParsedHTMLBlock(
                block_index=2,
                block_type="paragraph",
                text="Card operations policy.",
                section_title="Cards",
            )
        ],
    )

    blocks = html_to_source_blocks(document)

    assert blocks[0].block_index == 2
    assert blocks[0].section_title == "Cards"


def test_pdf_end_to_end_processing():
    document = ParsedDocument(
        document_name="policy.pdf",
        file_type="pdf",
        total_pages=1,
        pages=[
            ParsedPage(1, "Payment processing policy.", False)
        ],
        metadata={"author": "EKIP"},
    )

    result = process_parsed_document(document)

    assert result.document_name == "policy.pdf"
    assert result.file_type == "pdf"
    assert result.total_chunks == 1
    assert result.chunks[0].page_number == 1
    assert result.metadata["author"] == "EKIP"


def test_docx_end_to_end_processing():
    document = ParsedDocx(
        document_name="policy.docx",
        file_type="docx",
        blocks=[
            ParsedBlock(
                block_index=0,
                block_type="heading",
                text="Payments",
                section_title="Payments",
            ),
            ParsedBlock(
                block_index=1,
                block_type="paragraph",
                text="Payment settlement policy.",
                section_title="Payments",
            ),
        ],
    )

    result = process_parsed_document(document)

    assert result.total_chunks >= 1
    assert result.chunks[0].section_title == "Payments"


def test_html_end_to_end_processing():
    document = ParsedHTML(
        document_name="policy.html",
        file_type="html",
        title="Banking Policy",
        blocks=[
            ParsedHTMLBlock(
                block_index=0,
                block_type="paragraph",
                text="Customer onboarding policy.",
                section_title="Retail Banking",
            )
        ],
    )

    result = process_parsed_document(document)

    assert result.total_chunks == 1
    assert result.metadata["title"] == "Banking Policy"
    assert result.chunks[0].section_title == "Retail Banking"
