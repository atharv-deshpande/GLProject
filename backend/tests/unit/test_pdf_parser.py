
from io import BytesIO

import pytest
from pypdf import PdfWriter

from app.modules.ingestion.parsers.pdf_parser import (
    PDFParserError,
    parse_pdf,
)


def create_pdf(
    pages: list[str],
    title: str = "EKIP Test Document",
) -> bytes:
    writer = PdfWriter()
    writer.add_metadata({"/Title": title})

    for page_text in pages:
        page = writer.add_blank_page(width=612, height=792)

        if page_text:
            page.merge_page(
                create_text_page(page_text)
            )

    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def create_text_page(text: str):
    from reportlab.pdfgen import canvas

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.drawString(50, 750, text)
    pdf.save()

    buffer.seek(0)
    from pypdf import PdfReader

    return PdfReader(buffer).pages[0]


def test_parse_single_page_pdf():
    pdf_bytes = create_pdf(["Retail banking introduction"])

    result = parse_pdf(pdf_bytes, "retail.pdf")

    assert result.document_name == "retail.pdf"
    assert result.file_type == "pdf"
    assert result.total_pages == 1
    assert result.pages[0].page_number == 1
    assert "Retail banking introduction" in result.pages[0].text
    assert result.pages[0].is_empty is False


def test_parse_multiple_pages():
    pdf_bytes = create_pdf([
        "Account opening",
        "Payment processing",
        "Risk management",
    ])

    result = parse_pdf(pdf_bytes)

    assert result.total_pages == 3
    assert [p.page_number for p in result.pages] == [1, 2, 3]
    assert "Account opening" in result.pages[0].text
    assert "Payment processing" in result.pages[1].text
    assert "Risk management" in result.pages[2].text


def test_preserve_empty_page():
    pdf_bytes = create_pdf([
        "First page",
        "",
        "Third page",
    ])

    result = parse_pdf(pdf_bytes)

    assert result.total_pages == 3
    assert result.pages[1].page_number == 2
    assert result.pages[1].is_empty is True
    assert result.pages[1].text == ""


def test_extract_pdf_metadata():
    pdf_bytes = create_pdf(
        ["Sample content"],
        title="Retail Banking Policy",
    )

    result = parse_pdf(pdf_bytes)

    assert result.metadata["title"] == "Retail Banking Policy"


def test_reject_empty_pdf():
    with pytest.raises(PDFParserError):
        parse_pdf(b"")


def test_reject_malformed_pdf():
    with pytest.raises(PDFParserError):
        parse_pdf(b"This is not a PDF")
