from ui.layout import _format_uploaded_at


def test_format_uploaded_at_uses_vietnamese_day_month_order():
    assert _format_uploaded_at("2026-07-31T12:44:32") == "31/07/2026 12:44"


def test_format_uploaded_at_preserves_unrecognized_value():
    assert _format_uploaded_at("khong-ro-thoi-gian") == "khong-ro-thoi-gian"
