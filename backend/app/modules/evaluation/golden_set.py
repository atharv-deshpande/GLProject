from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


_CITATION_PATTERN = re.compile(r"\[(S[0-9]+)\]")


@dataclass(frozen=True)
class GoldenCase:
    case_id: str
    question: str
    expected_terms: tuple[str, ...]
    department_code: str


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    passed: bool
    matched_terms: tuple[str, ...]
    missing_terms: tuple[str, ...]


def evaluate_answer(case: GoldenCase, answer: str) -> CaseResult:
    normalized = answer.casefold()
    matched = tuple(term for term in case.expected_terms if term.casefold() in normalized)
    missing = tuple(term for term in case.expected_terms if term.casefold() not in normalized)
    return CaseResult(case.case_id, not missing, matched, missing)


def evaluate_citations(answer: str, authorized_source_ids: Iterable[str]) -> dict:
    """Deterministically measure citation-ID validity; not semantic entailment."""
    allowed = set(authorized_source_ids)
    cited = _CITATION_PATTERN.findall(answer)
    invalid = [source_id for source_id in cited if source_id not in allowed]
    valid = [source_id for source_id in cited if source_id in allowed]
    return {
        "citation_count": len(cited),
        "valid_citation_count": len(valid),
        "invalid_citation_count": len(invalid),
        "invalid_source_ids": invalid,
        "citation_id_precision": len(valid) / len(cited) if cited else 1.0,
    }


def evaluate_batch(cases: Iterable[GoldenCase], answers: dict[str, str]) -> dict:
    results = [evaluate_answer(case, answers.get(case.case_id, "")) for case in cases]
    total = len(results)
    passed = sum(item.passed for item in results)
    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": passed / total if total else 0.0,
        "results": [
            {"case_id": item.case_id, "passed": item.passed,
             "matched_terms": list(item.matched_terms),
             "missing_terms": list(item.missing_terms)}
            for item in results
        ],
    }
