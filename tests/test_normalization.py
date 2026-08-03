from src.normalization import (
    normalize_code,
    normalize_code_for_match,
    normalize_name_for_matching,
    resolve_column_name,
    strip_price_and_vat_suffix,
    to_float_or_none,
    GOP_VAT_COLUMN_ALIASES,
)


def test_normalize_code_keeps_leading_zero():
    assert normalize_code("00123") == "00123"


def test_normalize_code_strips_whitespace():
    assert normalize_code("  ABC123  ") == "ABC123"


def test_normalize_code_for_match_case_insensitive():
    assert normalize_code_for_match("Vat001") == normalize_code_for_match("VAT001 ")


def test_to_float_or_none_handles_text_number():
    assert to_float_or_none("1,234") == 1234.0
    assert to_float_or_none("") is None
    assert to_float_or_none(None) is None
    assert to_float_or_none("abc") is None


def test_resolve_column_name_case_and_space_tolerant():
    header = ["nguồn", " Mã kiot đại diện ", "Tên kiot đại diện", "MÃ VAT KIOT",
              "TÊN VAT KIOT", "MÃ KT", "TÊN KẾ TOÁN", "đơn vị tính", "TỒN ĐẦU NGÀY",
              "GIÁ BÁN", "THUẾ VAT", "THUẾ NK", "TỔNG THUẾ MẤT",
              "TỔNG ĐANG NHÁP", "TỒN CÓ THỂ NHÁP"]
    mapping = resolve_column_name(header, GOP_VAT_COLUMN_ALIASES)
    assert set(mapping.keys()) == set(GOP_VAT_COLUMN_ALIASES.keys())


def test_normalize_name_strips_diacritics_and_extracts_numbers():
    n = normalize_name_for_matching("Ấm giữ nhiệt 1000ML Hoa")
    assert "1000ml" in n.number_tokens
    assert "am" in n.word_tokens
    assert "giu" in n.word_tokens


def test_normalize_name_leading_zero():
    n1 = normalize_name_for_matching("Kích thước 02")
    n2 = normalize_name_for_matching("Kích thước 2")
    assert n1.number_tokens == n2.number_tokens


def test_strip_price_and_vat_suffix():
    text = "Ấm giữ nhiệt 1000ML (72,100 - 78,500) (VAT)"
    assert strip_price_and_vat_suffix(text) == "Ấm giữ nhiệt 1000ML"
