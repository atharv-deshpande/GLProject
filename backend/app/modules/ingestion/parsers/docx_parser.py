
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any

from docx import Document
from docx.opc.exceptions import PackageNotFoundError


@dataclass
class ParsedBlock:
    block_index: int
    block_type: str
    text: str
    section_title: str | None = None
    heading_level: int | None = None


@dataclass
class ParsedDocx:
    document_name: str
    file_type: str
    blocks: list[ParsedBlock]
    metadata: dict[str, Any] = field(default_factory=dict)


class DOCXParserError(Exception):
    pass


def parse_docx(
    file_content: bytes,
    document_name: str = "document.docx",
) -> ParsedDocx:

    if not file_content:
        raise DOCXParserError("DOCX file is empty.")

    try:
        document = Document(BytesIO(file_content))

        blocks = []
        current_section = None
        block_index = 0

        # Preserve the order of paragraphs and tables.
        from docx.oxml.text.paragraph import CT_P
        from docx.oxml.table import CT_Tbl
        from docx.text.paragraph import Paragraph
        from docx.table import Table

        for element in document.element.body.iterchildren():

            if isinstance(element, CT_P):
                paragraph = Paragraph(element, document)
                text = paragraph.text.strip()

                if not text:
                    continue

                style_name = paragraph.style.name or "Normal"

                if style_name.startswith("Heading"):
                    current_section = text

                    try:
                        level = int(style_name.split()[-1])
                    except ValueError:
                        level = None

                    blocks.append(
                        ParsedBlock(
                            block_index=block_index,
                            block_type="heading",
                            text=text,
                            section_title=current_section,
                            heading_level=level,
                        )
                    )
                else:
                    blocks.append(
                        ParsedBlock(
                            block_index=block_index,
                            block_type="paragraph",
                            text=text,
                            section_title=current_section,
                        )
                    )

                block_index += 1

            elif isinstance(element, CT_Tbl):
                table = Table(element, document)

                rows = []
                for row in table.rows:
                    cells = [
                        cell.text.strip()
                        for cell in row.cells
                    ]
                    rows.append(" | ".join(cells))

                table_text = "\n".join(rows).strip()

                if table_text:
                    blocks.append(
                        ParsedBlock(
                            block_index=block_index,
                            block_type="table",
                            text=table_text,
                            section_title=current_section,
                        )
                    )
                    block_index += 1

        props = document.core_properties

        metadata = {
            "title": props.title or None,
            "author": props.author or None,
            "subject": props.subject or None,
            "created": props.created.isoformat()
            if props.created else None,
            "modified": props.modified.isoformat()
            if props.modified else None,
        }

        metadata = {
            key: value
            for key, value in metadata.items()
            if value is not None
        }

        return ParsedDocx(
            document_name=Path(document_name).name,
            file_type="docx",
            blocks=blocks,
            metadata=metadata,
        )

    except DOCXParserError:
        raise

    except Exception as exc:
        raise DOCXParserError(
            f"Unable to parse DOCX: {type(exc).__name__}: {exc}"
        ) from exc
