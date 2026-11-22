
from dataclasses import dataclass
from typing import Callable
import re


@dataclass
class SourceBlock:
    text: str
    block_index: int
    section_title: str | None = None
    page_number: int | None = None
    block_type: str = "paragraph"


@dataclass
class DocumentChunk:
    chunk_index: int
    content: str
    token_count: int
    page_number: int | None
    section_title: str | None
    source_block_start: int
    source_block_end: int


def default_token_counter(text: str) -> int:
    """
    Conservative baseline estimate.
    Replace with the tokenizer for the selected embedding model
    before tuning production chunk sizes.
    """
    if not text.strip():
        return 0

    return len(re.findall(r"\w+|[^\w\s]", text))


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [part.strip() for part in parts if part.strip()]


def chunk_document(
    blocks: list[SourceBlock],
    max_tokens: int = 500,
    overlap_tokens: int = 75,
    min_tokens: int = 50,
    token_counter: Callable[[str], int] = default_token_counter,
) -> list[DocumentChunk]:

    if max_tokens <= 0:
        raise ValueError("max_tokens must be greater than zero")

    if overlap_tokens < 0 or overlap_tokens >= max_tokens:
        raise ValueError("overlap_tokens must be between 0 and max_tokens")

    chunks: list[DocumentChunk] = []
    current_parts: list[str] = []
    current_tokens = 0
    current_page = None
    current_section = None
    source_start = None
    source_end = None

    def flush():
        nonlocal current_parts, current_tokens
        nonlocal current_page, current_section
        nonlocal source_start, source_end

        if not current_parts:
            return

        content = "\n\n".join(current_parts).strip()

        chunks.append(
            DocumentChunk(
                chunk_index=len(chunks),
                content=content,
                token_count=token_counter(content),
                page_number=current_page,
                section_title=current_section,
                source_block_start=source_start,
                source_block_end=source_end,
            )
        )

        current_parts = []
        current_tokens = 0
        current_page = None
        current_section = None
        source_start = None
        source_end = None

    for block in blocks:
        text = block.text.strip()

        if not text:
            continue

        # Do not combine content across section or page boundaries.
        boundary_changed = (
            current_parts
            and (
                block.page_number != current_page
                or block.section_title != current_section
            )
        )

        if boundary_changed:
            flush()

        if not current_parts:
            current_page = block.page_number
            current_section = block.section_title
            source_start = block.block_index

        sentences = split_sentences(text) or [text]

        for sentence in sentences:
            sentence_tokens = token_counter(sentence)

            # A single oversized sentence must be split as a fallback.
            if sentence_tokens > max_tokens:
                flush()
                words = sentence.split()
                part = []

                for word in words:
                    candidate = " ".join(part + [word])

                    if part and token_counter(candidate) > max_tokens:
                        oversized_part = " ".join(part)
                        current_parts = [oversized_part]
                        current_page = block.page_number
                        current_section = block.section_title
                        source_start = block.block_index
                        source_end = block.block_index
                        flush()
                        part = [word]
                    else:
                        part.append(word)

                if part:
                    current_parts = [" ".join(part)]
                    current_page = block.page_number
                    current_section = block.section_title
                    source_start = block.block_index
                    source_end = block.block_index
                    flush()

                continue

            candidate_parts = current_parts + [sentence]
            candidate = "\n\n".join(candidate_parts)

            if current_parts and token_counter(candidate) > max_tokens:
                previous_text = "\n\n".join(current_parts)
                previous_sentences = split_sentences(previous_text)

                flush()

                # Carry forward a small overlap from the previous chunk.
                overlap = []
                overlap_count = 0

                for previous_sentence in reversed(previous_sentences):
                    count = token_counter(previous_sentence)

                    if overlap_count + count > overlap_tokens:
                        break

                    overlap.insert(0, previous_sentence)
                    overlap_count += count

                current_parts = overlap
                current_tokens = overlap_count
                current_page = block.page_number
                current_section = block.section_title
                source_start = block.block_index

            if not current_parts:
                current_page = block.page_number
                current_section = block.section_title
                source_start = block.block_index

            current_parts.append(sentence)
            current_tokens = token_counter("\n\n".join(current_parts))
            source_end = block.block_index

    flush()

    # min_tokens is retained as a tuning parameter.
    # Small final chunks are not discarded because that would lose evidence.
    return chunks
