
import pytest

from app.modules.ingestion.parsers.html_parser import (
    HTMLParserError,
    parse_html,
)


def test_parse_html_title():
    html = b"""
    <html>
      <head><title>Retail Banking Policy</title></head>
      <body><p>Account opening rules.</p></body>
    </html>
    """

    result = parse_html(html, "retail.html")

    assert result.title == "Retail Banking Policy"
    assert result.document_name == "retail.html"
    assert result.file_type == "html"


def test_extract_headings_and_paragraphs():
    html = b"""
    <html>
      <body>
        <h1>Account Opening</h1>
        <p>Verify customer identity.</p>
        <h2>Required Documents</h2>
        <p>Collect identity proof.</p>
      </body>
    </html>
    """

    result = parse_html(html)

    assert len(result.blocks) == 4
    assert result.blocks[0].heading_level == 1
    assert result.blocks[2].heading_level == 2
    assert result.blocks[1].section_title == "Account Opening"
    assert result.blocks[3].section_title == "Required Documents"


def test_remove_scripts_and_styles():
    html = b"""
    <html>
      <head>
        <style>.secret { display:none; }</style>
        <script>alert('do not execute');</script>
      </head>
      <body>
        <p>Visible banking policy.</p>
      </body>
    </html>
    """

    result = parse_html(html)

    extracted = " ".join(
        block.text for block in result.blocks
    )

    assert "Visible banking policy" in extracted
    assert "alert" not in extracted
    assert "secret" not in extracted


def test_extract_lists():
    html = b"""
    <html><body>
      <h1>Payment Controls</h1>
      <ul>
        <li>Verify beneficiary</li>
        <li>Validate transaction amount</li>
      </ul>
    </body></html>
    """

    result = parse_html(html)

    list_items = [
        block for block in result.blocks
        if block.block_type == "list_item"
    ]

    assert len(list_items) == 2
    assert list_items[0].section_title == "Payment Controls"


def test_extract_metadata():
    html = b"""
    <html>
      <head>
        <title>Policy</title>
        <meta name="author" content="EKIP Test">
        <meta name="description" content="Banking policy sample">
      </head>
      <body><p>Policy content.</p></body>
    </html>
    """

    result = parse_html(html)

    assert result.metadata["author"] == "EKIP Test"
    assert result.metadata["description"] == "Banking policy sample"


def test_reject_empty_html():
    with pytest.raises(HTMLParserError):
        parse_html(b"")


def test_reject_html_without_readable_content():
    html = b"""
    <html>
      <head><script>var x = 1;</script></head>
      <body></body>
    </html>
    """

    with pytest.raises(HTMLParserError):
        parse_html(html)


def test_reject_invalid_utf8():
    with pytest.raises(HTMLParserError):
        parse_html(b"\xff\xfe\xfa")
