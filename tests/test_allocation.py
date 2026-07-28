from src.config import AppConfig
from src.pipeline import process_invoice
from tests.factories import make_input_row, make_mapping_row, make_stock_row


def _config():
    return AppConfig(source_tiebreak_priority=["Vận chuyển", "MAY", "SAIGONHANOI", "CAO", "Thấp"])


def _single_product_mapping():
    return [make_mapping_row(2, "SP1", "San pham 1", "VAT1")]


def test_single_source_enough_no_split():
    stock = [
        make_stock_row(2, "MAY", "VAT1", "KT1", "Cái", 200),
        make_stock_row(3, "CAO", "VAT1", "KT1", "Cái", 200),
    ]
    rows = [make_input_row(1, "SP1", "San pham 1", 50, 1000)]
    res = process_invoice(rows, stock, _single_product_mapping(), _config())
    assert res.is_valid
    sources_used = {l.nguon for l in res.result_lines}
    assert len(sources_used) == 1


def test_may_150_cao_100_need_200_splits_100_100():
    stock = [
        make_stock_row(2, "MAY", "VAT1", "KT1", "Cái", 150),
        make_stock_row(3, "CAO", "VAT1", "KT1", "Cái", 100),
    ]
    rows = [make_input_row(1, "SP1", "San pham 1", 200, 1000)]
    res = process_invoice(rows, stock, _single_product_mapping(), _config())
    assert res.is_valid
    by_source = {l.nguon: l.sl_phan_bo for l in res.result_lines}
    assert by_source == {"MAY": 100.0, "CAO": 100.0}


def test_one_source_500_others_100_need_300_uses_single_source():
    stock = [
        make_stock_row(2, "MAY", "VAT1", "KT1", "Cái", 100),
        make_stock_row(3, "CAO", "VAT1", "KT1", "Cái", 100),
        make_stock_row(4, "Vận chuyển", "VAT1", "KT1", "Cái", 500),
    ]
    rows = [make_input_row(1, "SP1", "San pham 1", 300, 1000)]
    res = process_invoice(rows, stock, _single_product_mapping(), _config())
    assert res.is_valid
    sources_used = {l.nguon for l in res.result_lines}
    assert sources_used == {"Vận chuyển"}
    assert sum(l.sl_phan_bo for l in res.result_lines) == 300


def test_total_stock_not_enough_blocks():
    stock = [make_stock_row(2, "MAY", "VAT1", "KT1", "Cái", 10)]
    rows = [make_input_row(1, "SP1", "San pham 1", 100, 1000)]
    res = process_invoice(rows, stock, _single_product_mapping(), _config())
    assert not res.is_valid
    assert res.errors


def test_min_number_of_sources_preferred():
    stock = [
        make_stock_row(2, "MAY", "VAT1", "KT1", "Cái", 60),
        make_stock_row(3, "CAO", "VAT1", "KT1", "Cái", 60),
        make_stock_row(4, "Thấp", "VAT1", "KT1", "Cái", 60),
    ]
    rows = [make_input_row(1, "SP1", "San pham 1", 100, 1000)]
    res = process_invoice(rows, stock, _single_product_mapping(), _config())
    assert res.is_valid
    sources_used = {l.nguon for l in res.result_lines}
    assert len(sources_used) == 2  # ít nguồn nhất đủ 100, không cần cả 3


def test_low_stock_line_prioritized_within_source():
    stock = [
        make_stock_row(2, "MAY", "VAT1", "KT1", "Cái", 100),
        make_stock_row(3, "MAY", "VAT1", "KT1", "Cái", 10),
    ]
    rows = [make_input_row(1, "SP1", "San pham 1", 10, 1000)]
    res = process_invoice(rows, stock, _single_product_mapping(), _config())
    assert res.is_valid
    assert len(res.result_lines) == 1
    assert res.result_lines[0].ton_con_nhap_truoc == 10  # dùng dòng tồn thấp trước


def test_same_ma_sp_twice_does_not_exceed_stock():
    stock = [make_stock_row(2, "MAY", "VAT1", "KT1", "Cái", 150)]
    rows = [
        make_input_row(1, "SP1", "San pham 1", 100, 1000),
        make_input_row(2, "SP1", "San pham 1", 100, 1000),
    ]
    res = process_invoice(rows, stock, _single_product_mapping(), _config())
    assert not res.is_valid  # 200 cần > 150 tồn thực -> dòng thứ 2 phải báo lỗi


def test_total_allocated_equals_requested():
    stock = [
        make_stock_row(2, "MAY", "VAT1", "KT1", "Cái", 83),
        make_stock_row(3, "CAO", "VAT1", "KT1", "Cái", 83),
        make_stock_row(4, "Vận chuyển", "VAT1", "KT1", "Cái", 84),
    ]
    rows = [make_input_row(1, "SP1", "San pham 1", 250, 1000)]
    res = process_invoice(rows, stock, _single_product_mapping(), _config())
    assert res.is_valid
    assert sum(l.sl_phan_bo for l in res.result_lines) == 250


def test_does_not_mix_accounting_names_when_splitting():
    stock = [
        make_stock_row(2, "MAY", "VAT1", "KT A", "Cái", 30),
        make_stock_row(3, "CAO", "VAT1", "KT B", "Cái", 200),
    ]
    rows = [make_input_row(1, "SP1", "San pham 1", 50, 1000)]
    res = process_invoice(rows, stock, _single_product_mapping(), _config())
    assert res.is_valid
    ten_ke_toans = {l.ten_ke_toan for l in res.result_lines}
    assert len(ten_ke_toans) == 1  # chỉ 1 nhóm KT B (đủ tồn), không trộn KT A
