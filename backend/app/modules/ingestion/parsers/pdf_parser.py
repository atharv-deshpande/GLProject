
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any

from pypdf import PdfReader
from pypdf.errors import PdfReadError


@dataclass
class ParsedPage:
    page_number: int
    text: str
    is_empty: bool


@dataclass
class ParsedDocument:
    document_name: str
    file_type: str
    total_pages: int
    pages: list[ParsedPage]
    metadata: dict[str, Any] = field(default_factory=dict)


class PDFParserError(Exception):
    """Raised when a PDF cannot be parsed."""


def parse_pdf(
    file_content: bytes,
    document_name: str = "document.pdf",
) -> ParsedDocument:

    if not file_content:
        raise PDFParserError("PDF file is empty.")

    try:
        # IMPORTANT: PdfReader needs a file-like object.
        pdf_stream = BytesIO(file_content)

        reader = PdfReader(
            pdf_stream,
            strict=False,
        )

        if reader.is_encrypted:
            raise PDFParserError(
                "Encrypted PDFs are not supported."
            )

        pages: list[ParsedPage] = []

        for page_number, page in enumerate(reader.pages, start=1):

            try:
                extracted_text = page.extract_text() or ""

            except Exception as exc:
                raise PDFParserError(
                    f"Failed to extract text from page {page_number}: {exc}"
                ) from exc

            text = extracted_text.strip()

            pages.append(
                ParsedPage(
                    page_number=page_number,
                    text=text,
                    is_empty=not bool(text),
                )
            )

        raw_metadata = reader.metadata or {}

        metadata = {
            "title": raw_metadata.title,
            "author": raw_metadata.author,
            "subject": raw_metadata.subject,
            "creator": raw_metadata.creator,
            "producer": raw_metadata.producer,
        }

        metadata = {
            key: value
            for key, value in metadata.items()
            if value is not None
        }

        return ParsedDocument(
            document_name=Path(document_name).name,
            file_type="pdf",
            total_pages=len(pages),
            pages=pages,
            metadata=metadata,
        )

    except PDFParserError:
        raise

    except Exception as exc:
        # Preserve the original exception for debugging.
        raise PDFParserError(
            f"Unable to parse PDF '{document_name}': "
            f"{type(exc).__name__}: {exc}"
        ) from exc
