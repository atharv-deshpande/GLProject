from app.modules.ingestion.processing.normalizer import normalize_text


def test_normalize_whitespace():
    assert normalize_text("  Banking   Policy  ") == "Banking Policy"


def test_normalize_line_endings():
    assert normalize_text("Account\r\nOpening") == "Account\nOpening"


def test_remove_excessive_blank_lines():
    result = normalize_text("Section A\n\n\n\nSection B")
    assert result == "Section A\n\nSection B"


def test_preserve_banking_values():
    text = "Transaction ID: TXN-2026-001 | Amount: ₹50,000"
    assert normalize_text(text) == text


def test_normalize_unicode():
    assert normalize_text("ＡＢＣ") == "ABC"


def test_empty_input():
    assert normalize_text("") == ""