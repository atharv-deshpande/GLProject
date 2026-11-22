
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, FeatureNotFound


@dataclass
class ParsedHTMLBlock:
    block_index: int
    block_type: str
    text: str
    section_title: str | None = None
    heading_level: int | None = None


@dataclass
class ParsedHTML:
    document_name: str
    file_type: str
    title: str | None
    blocks: list[ParsedHTMLBlock]
    metadata: dict[str, Any] = field(default_factory=dict)


class HTMLParserError(Exception):
    """Raised when HTML content cannot be parsed."""


# Elements that should not contribute to extracted document content.
EXCLUDED_ELEMENTS = [
    "script",
    "style",
    "noscript",
    "template",
    "svg",
    "canvas",
    "iframe",
    "object",
    "embed",
    "nav",
    "footer",
    "aside",
    "form",
    "button",
]


CONTENT_TAGS = {
    "p": "paragraph",
    "li": "list_item",
    "blockquote": "blockquote",
    "pre": "code",
    "td": "table_cell",
    "th": "table_header",
}


def parse_html(
    file_content: bytes,
    document_name: str = "document.html",
) -> ParsedHTML:
    """
    Parse HTML bytes into ordered text blocks.

    Heading and section context is preserved.
    Scripts and non-content elements are excluded.
    HTML is never executed or rendered.
    """

    if not file_content:
        raise HTMLParserError("HTML document is empty.")

    try:
        decoded = file_content.decode("utf-8-sig")

        soup = BeautifulSoup(decoded, "lxml")

        # Extract title before removing non-content elements.
        title_tag = soup.find("title")
        title = (
            title_tag.get_text(" ", strip=True)
            if title_tag
            else None
        )

        # Extract metadata.
        metadata = {}

        for meta in soup.find_all("meta"):
            name = (
                meta.get("name")
                or meta.get("property")
            )
            content = meta.get("content")

            if name and content:
                metadata[name] = content.strip()

        # Remove elements that should not enter the LLM pipeline.
        for tag_name in EXCLUDED_ELEMENTS:
            for element in soup.find_all(tag_name):
                element.decompose()

        # Remove elements explicitly hidden from display.
        for element in soup.find_all(True):
            style = (element.get("style") or "").lower()
            if (
                element.has_attr("hidden")
                or element.get("aria-hidden") == "true"
                or "display:none" in style.replace(" ", "")
            ):
                element.decompose()

        root = soup.body or soup

        blocks = []
        current_section = None
        block_index = 0

        # Walk document elements in source order.
        for element in root.find_all(
            ["h1", "h2", "h3", "h4", "h5", "h6",
             "p", "li", "blockquote", "pre",
             "td", "th"]
        ):

            # Avoid duplicate text from nested content blocks.
            if element.find(
                ["p", "li", "blockquote", "pre",
                 "td", "th", "h1", "h2", "h3",
                 "h4", "h5", "h6"]
            ):
                continue

            text = element.get_text(" ", strip=True)

            if not text:
                continue

            tag_name = element.name

            if tag_name in {
                "h1", "h2", "h3", "h4", "h5", "h6"
            }:
                current_section = text

                blocks.append(
                    ParsedHTMLBlock(
                        block_index=block_index,
                        block_type="heading",
                        text=text,
                        section_title=current_section,
                        heading_level=int(tag_name[1]),
                    )
                )

            else:
                blocks.append(
                    ParsedHTMLBlock(
                        block_index=block_index,
                        block_type=CONTENT_TAGS[tag_name],
                        text=text,
                        section_title=current_section,
                    )
                )

            block_index += 1

        if not blocks:
            raise HTMLParserError(
                "No readable HTML content was found."
            )

        return ParsedHTML(
            document_name=Path(document_name).name,
            file_type="html",
            title=title,
            blocks=blocks,
            metadata=metadata,
        )

    except HTMLParserError:
        raise

    except UnicodeDecodeError as exc:
        raise HTMLParserError(
            "HTML document must use UTF-8 encoding."
        ) from exc

    except Exception as exc:
        raise HTMLParserError(
            f"Unable to parse HTML: {type(exc).__name__}: {exc}"
        ) from exc
