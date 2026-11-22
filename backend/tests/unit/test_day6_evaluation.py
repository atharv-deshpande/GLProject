from app.modules.evaluation.golden_set import GoldenCase, evaluate_answer, evaluate_batch
from app.modules.enrichment.entities import extract_entities


def test_golden_answer_evaluation():
    case = GoldenCase("payments-1", "settlement window", ("NEFT", "T+1"), "PAYMENTS")
    result = evaluate_answer(case, "NEFT settlement completes on T+1.")
    assert result.passed
    assert result.missing_terms == ()


def test_missing_terms_are_reported():
    case = GoldenCase("payments-2", "settlement", ("NEFT", "T+1"), "PAYMENTS")
    result = evaluate_answer(case, "NEFT settlement")
    assert not result.passed
    assert result.missing_terms == ("T+1",)


def test_empty_batch_has_zero_rate():
    assert evaluate_batch([], {})["pass_rate"] == 0.0


def test_entity_extraction_finds_currency_and_percentage():
    result = {(item.entity_type, item.value) for item in extract_entities("Fee INR 1,250; rate 2.5%.")}
    assert ("currency", "INR 1,250") in result
    assert ("percentage", "2.5%") in result
