from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ExtractedEntity:
    entity_type: str
    value: str


_PATTERNS = {
    "currency": re.compile(r"(?i)(?:INR|Rs\.?|₹)\s?\d[\d,]*(?:\.\d{1,2})?"),
    "percentage": re.compile(r"\b\d+(?:\.\d+)?\s?%"),
    "date": re.compile(r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b"),
    "reference": re.compile(r"(?i)\b(?:account|acct|reference|txn|transaction)\s*(?:no|number|id|ref)?\s*[:#-]?\s*[A-Z0-9-]{6,24}\b"),
}


def extract_entities(text: str) -> list[ExtractedEntity]:
    """Conservative candidate extraction; extracted values are not verified facts."""
    found: set[tuple[str, str]] = set()
    for kind, pattern in _PATTERNS.items():
        for match in pattern.finditer(text):
            found.add((kind, " ".join(match.group(0).split())))
    return [ExtractedEntity(kind, value) for kind, value in sorted(found)]
