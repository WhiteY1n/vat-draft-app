from src.config import AppConfig
from src.mapping import MappingLookup
from src.validation import validate_invoice_rows
from tests.factories import make_input_row, make_mapping_row, make_stock_row


def _config():
    return AppConfig()


def test_ma_sp_not_found_blocks():
    lookup = MappingLookup.build([], [])
    rows = [make_input_row(1, "ABC", "Ten", 1, 1000)]
    result = validate_invoice_rows(rows, lookup, _config())
    assert result.has_blocking_errors
    assert result.errors[0].error_type == "ma_sp_khong_ton_tai"


def test_ma_sp_multi_vat_blocks():
    mapping = [
        make_mapping_row(2, "ABC", "Ten A", "VAT1"),
        make_mapping_row(3, "ABC", "Ten A", "VAT2"),
    ]
    lookup = MappingLookup.build(mapping, [])
    rows = [make_input_row(1, "ABC", "Ten A", 1, 1000)]
    result = validate_invoice_rows(rows, lookup, _config())
    assert result.has_blocking_errors
    assert result.errors[0].error_type == "ma_sp_da_vat"


def test_zero_or_negative_ton_excluded_from_candidates():
    stock = [
        make_stock_row(2, "MAY", "VAT1", "Ten KT", "Cái", 0),
        make_stock_row(3, "MAY", "VAT1", "Ten KT", "Cái", -5),
        make_stock_row(4, "MAY", "VAT1", "Ten KT", "Cái", 10),
    ]
    mapping = [make_mapping_row(2, "ABC", "Ten A", "VAT1")]
    lookup = MappingLookup.build(mapping, stock)
    rows = [make_input_row(1, "ABC", "Ten A", 5, 1000)]
    result = validate_invoice_rows(rows, lookup, _config())
    assert not result.has_blocking_errors
    assert len(result.resolved_rows[0].stock_candidates) == 1


def test_existing_vat_with_no_positive_stock_reports_out_of_stock():
    stock = [
        make_stock_row(2, "MAY", "VAT10176", "Chậu nhựa", "Cái", 0),
        make_stock_row(3, "MAY", "VAT10176", "Chậu nhựa", "Cái", -5),
    ]
    mapping = [make_mapping_row(2, "CGGHV", "Chậu gấp gọn hình voi", "VAT10176")]
    rows = [make_input_row(15, "CGGHV", "Chậu gấp gọn hình voi", 900, 2826)]

    result = validate_invoice_rows(rows, MappingLookup.build(mapping, stock), _config())

    assert result.has_blocking_errors
    assert result.errors[0].error_type == "mavat_het_ton_nhap"
    assert "có trong sheet Gộp VAT" in result.errors[0].detail
    assert "cao nhất 0" in result.errors[0].detail


def test_missing_vat_still_reports_missing_vat():
    mapping = [make_mapping_row(2, "ABC", "Tên A", "VAT404")]
    rows = [make_input_row(1, "ABC", "Tên A", 1, 1000)]

    result = validate_invoice_rows(rows, MappingLookup.build(mapping, []), _config())

    assert result.has_blocking_errors
    assert result.errors[0].error_type == "mavat_khong_ton_tai"
    assert "không tồn tại trong sheet Gộp VAT" in result.errors[0].detail


def test_sl_must_be_positive_integer():
    mapping = [make_mapping_row(2, "ABC", "Ten A", "VAT1")]
    stock = [make_stock_row(2, "MAY", "VAT1", "Ten KT", "Cái", 10)]
    lookup = MappingLookup.build(mapping, stock)

    rows = [make_input_row(1, "ABC", "Ten A", -1, 1000)]
    result = validate_invoice_rows(rows, lookup, _config())
    assert any(e.error_type == "sl_khong_duong" for e in result.errors)

    rows = [make_input_row(1, "ABC", "Ten A", 1.5, 1000)]
    result = validate_invoice_rows(rows, lookup, _config())
    assert any(e.error_type == "sl_khong_nguyen" for e in result.errors)


def test_gia_ban_negative_blocks():
    mapping = [make_mapping_row(2, "ABC", "Ten A", "VAT1")]
    stock = [make_stock_row(2, "MAY", "VAT1", "Ten KT", "Cái", 10)]
    lookup = MappingLookup.build(mapping, stock)
    rows = [make_input_row(1, "ABC", "Ten A", 1, -100)]
    result = validate_invoice_rows(rows, lookup, _config())
    assert any(e.error_type == "gia_ban_am" for e in result.errors)


def test_valid_row_resolves_correctly():
    mapping = [make_mapping_row(2, "ABC", "Ten A", "VAT1")]
    stock = [make_stock_row(2, "MAY", "VAT1", "Ten KT", "Cái", 10)]
    lookup = MappingLookup.build(mapping, stock)
    rows = [make_input_row(1, "ABC", "Ten A", 5, 1000)]
    result = validate_invoice_rows(rows, lookup, _config())
    assert not result.has_blocking_errors
    assert result.valid_count == 1
