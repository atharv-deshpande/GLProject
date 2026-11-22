
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.modules.ingestion.processing.normalizer import normalize_text
from app.modules.ingestion.processing.chunker import (
    SourceBlock,
    DocumentChunk,
    chunk_document,
)

from app.modules.ingestion.parsers.pdf_parser import ParsedDocument
from app.modules.ingestion.parsers.docx_parser import ParsedDocx
from app.modules.ingestion.parsers.html_parser import ParsedHTML


@dataclass
class IngestionResult:
    document_name: str
    file_type: str
    chunks: list[DocumentChunk]
    total_chunks: int
    total_tokens: int
    metadata: dict[str, Any] = field(default_factory=dict)


def prepare_source_blocks(
    blocks: list[SourceBlock],
) -> list[SourceBlock]:

    prepared = []

    for block in blocks:
        normalized = normalize_text(block.text)

        if not normalized:
            continue

        prepared.append(
            SourceBlock(
                text=normalized,
                block_index=block.block_index,
                section_title=block.section_title,
                page_number=block.page_number,
                block_type=block.block_type,
            )
        )

    return prepared


def pdf_to_source_blocks(
    document: ParsedDocument,
) -> list[SourceBlock]:

    return [
        SourceBlock(
            text=page.text,
            block_index=page.page_number - 1,
            page_number=page.page_number,
            block_type="page",
        )
        for page in document.pages
        if not page.is_empty
    ]


def docx_to_source_blocks(
    document: ParsedDocx,
) -> list[SourceBlock]:

    return [
        SourceBlock(
            text=block.text,
            block_index=block.block_index,
            section_title=block.section_title,
            block_type=block.block_type,
        )
        for block in document.blocks
    ]


def html_to_source_blocks(
    document: ParsedHTML,
) -> list[SourceBlock]:

    return [
        SourceBlock(
            text=block.text,
            block_index=block.block_index,
            section_title=block.section_title,
            block_type=block.block_type,
        )
        for block in document.blocks
    ]


def process_source_blocks(
    document_name: str,
    file_type: str,
    blocks: list[SourceBlock],
    metadata: dict[str, Any] | None = None,
) -> IngestionResult:

    prepared_blocks = prepare_source_blocks(blocks)

    chunks = chunk_document(
        blocks=prepared_blocks,
        max_tokens=500,
        overlap_tokens=75,
    )

    return IngestionResult(
        document_name=Path(document_name).name,
        file_type=file_type.lower().lstrip("."),
        chunks=chunks,
        total_chunks=len(chunks),
        total_tokens=sum(chunk.token_count for chunk in chunks),
        metadata=metadata or {},
    )


def process_parsed_document(
    document: ParsedDocument | ParsedDocx | ParsedHTML,
) -> IngestionResult:
    """
    Convert the output of an existing parser into source blocks,
    normalize the text and generate searchable chunks.
    """

    if isinstance(document, ParsedDocument):
        blocks = pdf_to_source_blocks(document)

    elif isinstance(document, ParsedDocx):
        blocks = docx_to_source_blocks(document)

    elif isinstance(document, ParsedHTML):
        blocks = html_to_source_blocks(document)

    else:
        raise TypeError(
            f"Unsupported parsed document type: {type(document).__name__}"
        )

    metadata = dict(document.metadata)

    if isinstance(document, ParsedHTML) and document.title:
        metadata["title"] = document.title

    return process_source_blocks(
        document_name=document.document_name,
        file_type=document.file_type,
        blocks=blocks,
        metadata=metadata,
    )
