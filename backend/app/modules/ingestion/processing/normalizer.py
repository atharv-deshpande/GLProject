import re
import unicodedata


def normalize_text(text: str) -> str:
    """
    Normalize extracted document text while preserving
    meaningful banking terminology, numbers and punctuation.
    """

    if not text:
        return ""

    # Normalize Unicode characters.
    text = unicodedata.normalize("NFKC", text)

    # Normalize line endings.
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Remove null and unwanted control characters.
    text = "".join(
        char for char in text
        if char in "\n\t" or unicodedata.category(char)[0] != "C"
    )

    # Normalize horizontal whitespace.
    text = re.sub(r"[ \t]+", " ", text)

    # Remove whitespace around line breaks.
    text = re.sub(r" *\n *", "\n", text)

    # Collapse excessive blank lines.
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()