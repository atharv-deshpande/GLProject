
from io import BytesIO

import pytest
from docx import Document

from app.modules.ingestion.parsers.docx_parser import (
    DOCXParserError,
    parse_docx,
)


def create_docx() -> bytes:
    doc = Document()

    doc.core_properties.title = "Retail Banking Policy"

    doc.add_heading("Account Opening", level=1)
    doc.add_paragraph("Customer identity must be verified.")

    doc.add_heading("Verification", level=2)
    doc.add_paragraph("Supporting documents must be reviewed.")

    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Document"
    table.cell(0, 1).text = "Required"
    table.cell(1, 0).text = "Identity proof"
    table.cell(1, 1).text = "Yes"

    output = BytesIO()
    doc.save(output)

    return output.getvalue()


def test_parse_docx():
    result = parse_docx(
        create_docx(),
        "retail_policy.docx",
    )

    assert result.file_type == "docx"
    assert result.document_name == "retail_policy.docx"
    assert len(result.blocks) == 5


def test_extract_heading_hierarchy():
    result = parse_docx(create_docx())

    headings = [
        block for block in result.blocks
        if block.block_type == "heading"
    ]

    assert headings[0].heading_level == 1
    assert headings[1].heading_level == 2


def test_preserve_section_context():
    result = parse_docx(create_docx())

    paragraphs = [
        block for block in result.blocks
        if block.block_type == "paragraph"
    ]

    assert paragraphs[0].section_title == "Account Opening"
    assert paragraphs[1].section_title == "Verification"


def test_extract_tables():
    result = parse_docx(create_docx())

    tables = [
        block for block in result.blocks
        if block.block_type == "table"
    ]

    assert len(tables) == 1
    assert "Identity proof" in tables[0].text


def test_extract_metadata():
    result = parse_docx(create_docx())

    assert result.metadata["title"] == "Retail Banking Policy"


def test_reject_empty_docx():
    with pytest.raises(DOCXParserError):
        parse_docx(b"")


def test_reject_invalid_docx():
    with pytest.raises(DOCXParserError):
        parse_docx(b"not a valid DOCX")
