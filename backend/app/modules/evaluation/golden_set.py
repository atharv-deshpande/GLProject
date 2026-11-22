from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


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
