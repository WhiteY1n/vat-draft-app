"""Test phân bổ nguồn cho chức năng Xử lý hóa đơn."""

from pathlib import Path

import streamlit as st
from streamlit.testing.v1 import AppTest

from src.config import AppConfig
from src.excel_reader import WorkbookCheckResult
from src.invoice_allocation import (
    allocate_invoice_sources,
    build_allocation_display_rows,
    build_shortage_display_rows,
    build_unavailable_display_rows,
    build_unified_display_rows,
)
from src.source_lookup import SourceLookupInput, SourceLookupIssue

from tests.factories import make_mapping_row, make_stock_row


def _config():
    return AppConfig(source_tiebreak_priority=["Vận chuyển", "MAY", "CAO"])


def _mappings():
    return [make_mapping_row(2, "SP01", "Sản phẩm 1", "VAT01", "Tên VAT 1")]


def _run(queries, mappings, stocks):
    return allocate_invoice_sources(queries, mappings, stocks, config=_config())


def _plan(result):
    """Danh sách (nguồn, SL phân bổ) theo đúng thứ tự dòng kết quả."""

    return [(line.nguon, line.sl_phan_bo) for line in result.lines]


# 1. Một nguồn duy nhất và đủ tồn -------------------------------------------


def test_single_source_with_enough_stock():
    stocks = [make_stock_row(2, "MAY", "VAT01", "KT1", "Cái", 500)]

    result = _run([SourceLookupInput(1, ma_sp="SP01", sl=100, gia_ban=11500)], _mappings(), stocks)

    assert not result.issues and not result.shortages
    assert _plan(result) == [("MAY", 100)]
    assert result.lines[0].sl_yeu_cau == 100
    assert result.lines[0].ton_con_nhap == 500


# 2. Nhiều nguồn đều đủ -> chọn nguồn xuất hiện nhiều nhất -------------------


def test_prefers_most_frequent_source_when_several_are_enough():
    mappings = _mappings() + [
        make_mapping_row(3, "SP02", "Sản phẩm 2", "VAT02"),
        make_mapping_row(4, "SP03", "Sản phẩm 3", "VAT03"),
    ]
    stocks = [
        make_stock_row(2, "Vận chuyển", "VAT01", "KT1", "Cái", 200),
        make_stock_row(3, "MAY", "VAT01", "KT2", "Cái", 150),
        make_stock_row(4, "CAO", "VAT01", "KT3", "Cái", 120),
        # Vận chuyển xuất hiện ở cả 3 sản phẩm -> nguồn xuất hiện nhiều nhất
        make_stock_row(5, "Vận chuyển", "VAT02", "KT4", "Cái", 10),
        make_stock_row(6, "Vận chuyển", "VAT03", "KT5", "Cái", 10),
    ]

    result = _run(
        [
            SourceLookupInput(1, ma_sp="SP01", sl=100),
            SourceLookupInput(2, ma_sp="SP02", sl=5),
            SourceLookupInput(3, ma_sp="SP03", sl=5),
        ],
        mappings,
        stocks,
    )

    assert not result.shortages
    assert _plan(result)[0] == ("Vận chuyển", 100)


def test_most_frequent_source_wins_over_config_priority():
    mappings = _mappings() + [make_mapping_row(3, "SP02", "Sản phẩm 2", "VAT02")]
    stocks = [
        make_stock_row(2, "Vận chuyển", "VAT01", "KT1", "Cái", 200),
        make_stock_row(3, "CAO", "VAT01", "KT2", "Cái", 200),
        make_stock_row(4, "CAO", "VAT02", "KT3", "Cái", 200),
    ]

    result = _run(
        [SourceLookupInput(1, ma_sp="SP01", sl=100), SourceLookupInput(2, ma_sp="SP02", sl=1)],
        mappings,
        stocks,
    )

    # CAO xuất hiện 2 lần, Vận chuyển 1 lần -> CAO thắng dù ưu tiên cấu hình thấp hơn.
    assert _plan(result)[0] == ("CAO", 100)


# 3. Không nguồn nào đủ -> gộp hai nguồn -------------------------------------


def test_merges_two_sources_starting_from_most_frequent():
    stocks = [
        make_stock_row(2, "MAY", "VAT01", "KT1", "Cái", 150),
        make_stock_row(3, "CAO", "VAT01", "KT2", "Cái", 100),
    ]

    result = _run([SourceLookupInput(1, ma_sp="SP01", sl=200)], _mappings(), stocks)

    assert not result.shortages
    assert _plan(result) == [("MAY", 150), ("CAO", 50)]


def test_single_capable_source_wins_over_more_frequent_but_smaller_source():
    """Quyết định nghiệp vụ: quy tắc 'một nguồn đủ thì chỉ dùng một nguồn'
    được ưu tiên hơn quy tắc 'nguồn xuất hiện nhiều nhất' (xác nhận 2026-08-01).
    """

    mappings = _mappings() + [make_mapping_row(3, "SP02", "Sản phẩm 2", "VAT02")]
    stocks = [
        make_stock_row(2, "MAY", "VAT01", "KT1", "Cái", 100),
        make_stock_row(3, "CAO", "VAT01", "KT2", "Cái", 300),
        make_stock_row(4, "MAY", "VAT02", "KT3", "Cái", 10),
    ]

    result = _run(
        [SourceLookupInput(1, ma_sp="SP01", sl=200), SourceLookupInput(2, ma_sp="SP02", sl=1)],
        mappings,
        stocks,
    )

    # MAY xuất hiện nhiều hơn nhưng không tự đủ 200 -> chỉ dùng CAO, một dòng.
    assert _plan(result)[:2] == [("CAO", 200), ("MAY", 1)]


# 4. Gộp từ ba nguồn trở lên -------------------------------------------------


def test_merges_three_sources_in_descending_stock_order():
    mappings = _mappings() + [make_mapping_row(3, "SP02", "Sản phẩm 2", "VAT02")]
    stocks = [
        make_stock_row(2, "MAY", "VAT01", "KT1", "Cái", 50),
        make_stock_row(3, "CAO", "VAT01", "KT2", "Cái", 120),
        make_stock_row(4, "Vận chuyển", "VAT01", "KT3", "Cái", 80),
        make_stock_row(5, "MAY", "VAT02", "KT4", "Cái", 1),
    ]

    result = _run(
        [SourceLookupInput(1, ma_sp="SP01", sl=220), SourceLookupInput(2, ma_sp="SP02", sl=1)],
        mappings,
        stocks,
    )

    assert _plan(result)[:3] == [("MAY", 50), ("CAO", 120), ("Vận chuyển", 50)]
    assert sum(line.sl_phan_bo for line in result.lines if line.ma_sp == "SP01") == 220


def test_multiple_stock_rows_inside_one_source_are_split():
    stocks = [
        make_stock_row(2, "MAY", "VAT01", "KT1", "Cái", 60),
        make_stock_row(3, "MAY", "VAT01", "KT2", "Cái", 90),
    ]

    result = _run([SourceLookupInput(1, ma_sp="SP01", sl=120)], _mappings(), stocks)

    assert not result.shortages
    assert [(line.ten_ke_toan, line.sl_phan_bo) for line in result.lines] == [
        ("KT2", 90),
        ("KT1", 30),
    ]


# 5. Tổng tồn vừa đúng SL ----------------------------------------------------


def test_total_stock_exactly_equals_requested_quantity():
    stocks = [
        make_stock_row(2, "MAY", "VAT01", "KT1", "Cái", 70),
        make_stock_row(3, "CAO", "VAT01", "KT2", "Cái", 30),
    ]

    result = _run([SourceLookupInput(1, ma_sp="SP01", sl=100)], _mappings(), stocks)

    assert not result.shortages
    assert _plan(result) == [("MAY", 70), ("CAO", 30)]
    assert sum(line.sl_phan_bo for line in result.lines) == 100


# 6. Tổng tồn nhỏ hơn SL -----------------------------------------------------


def test_shortage_when_total_stock_is_not_enough():
    stocks = [
        make_stock_row(2, "MAY", "VAT01", "KT1", "Cái", 100),
        make_stock_row(3, "CAO", "VAT01", "KT2", "Cái", 70),
    ]

    result = _run([SourceLookupInput(1, ma_sp="SP01", sl=200)], _mappings(), stocks)

    assert not result.lines
    assert len(result.shortages) == 2
    assert result.shortage_product_count == 1
    shortage = result.shortages[0]
    assert (shortage.sl_yeu_cau, shortage.tong_ton, shortage.thieu) == (200, 170, 30)
    assert (shortage.nguon, shortage.ton_con_nhap) == ("MAY", 100)
    assert "," not in shortage.nguon
    assert shortage.ghi_chu == "Không đủ số lượng tồn"
    assert [(row.nguon, row.ton_con_nhap) for row in result.shortages] == [
        ("MAY", 100),
        ("CAO", 70),
    ]
    assert all((row.tong_ton, row.thieu) == (170, 30) for row in result.shortages)
    assert len(build_shortage_display_rows(result.shortages)) == 2
    assert len(build_unified_display_rows([], result.shortages, [])) == 2


def test_shortage_representative_uses_largest_total_stock_from_one_source():
    stocks = [
        make_stock_row(2, "MAY", "VAT01", "KT1", "Unit", 60),
        make_stock_row(3, "MAY", "VAT01", "KT2", "Unit", 50),
        make_stock_row(4, "CAO", "VAT01", "KT3", "Unit", 100),
    ]

    result = _run([SourceLookupInput(1, ma_sp="SP01", sl=250)], _mappings(), stocks)

    shortage = result.shortages[0]
    assert (shortage.tong_ton, shortage.thieu) == (210, 40)
    assert (shortage.nguon, shortage.ton_con_nhap) == ("MAY", 110)
    assert result.shortage_product_count == 1
    assert [(row.nguon, row.ton_con_nhap) for row in result.shortages] == [
        ("MAY", 110),
        ("CAO", 100),
    ]
    assert all((row.tong_ton, row.thieu) == (210, 40) for row in result.shortages)
    assert result.shortages[1].ten_ke_toan == "KT3"
    assert shortage.ten_ke_toan in {"KT1", "KT2"}


def test_shortage_representative_uses_existing_priority_when_stock_is_equal():
    stocks = [
        make_stock_row(2, "CAO", "VAT01", "KT1", "Unit", 60),
        make_stock_row(3, "MAY", "VAT01", "KT2", "Unit", 60),
    ]

    result = _run([SourceLookupInput(1, ma_sp="SP01", sl=150)], _mappings(), stocks)

    shortage = result.shortages[0]
    assert (shortage.nguon, shortage.ton_con_nhap) == ("MAY", 60)
    assert [(row.nguon, row.ton_con_nhap) for row in result.shortages] == [
        ("MAY", 60),
        ("CAO", 60),
    ]
    assert [row.ten_ke_toan for row in result.shortages] == ["KT2", "KT1"]
    assert shortage.ten_ke_toan == "KT2"


def test_shortage_with_multiple_zero_stock_sources_uses_priority():
    stocks = [
        make_stock_row(2, "CAO", "VAT01", "KT1", "Unit", 0),
        make_stock_row(3, "MAY", "VAT01", "KT2", "Unit", 0),
    ]

    result = _run([SourceLookupInput(1, ma_sp="SP01", sl=10)], _mappings(), stocks)

    shortage = result.shortages[0]
    assert (shortage.tong_ton, shortage.thieu) == (0, 10)
    assert (shortage.nguon, shortage.ton_con_nhap) == ("MAY", 0)
    assert shortage.ten_ke_toan == "KT2"
    assert result.skipped_non_positive_stock_count == 2


# 7. Mã hàng không tồn tại ---------------------------------------------------


def test_unknown_product_code_becomes_issue():
    result = _run([SourceLookupInput(1, ma_sp="KHONGCO", sl=10)], _mappings(), [])

    assert not result.lines and not result.shortages
    assert result.issues[0].issue_type == "khong_tim_thay_ma"


def test_code_missing_from_khop_ma_falls_back_to_gop_vat_representative_code():
    stocks = [make_stock_row(2, "MAY", "VAT01", "KT1", "Cái", 100)]
    stocks[0].ma_kiot_dai_dien = "SP-GOP"
    stocks[0].ten_kiot_dai_dien = "Sản phẩm chỉ có trong Gộp VAT"

    result = _run([SourceLookupInput(1, ma_sp=" sp-gop ", sl=25)], [], stocks)

    assert not result.issues and not result.shortages
    assert _plan(result) == [("MAY", 25)]
    assert result.lines[0].ma_sp == "SP-GOP"
    assert result.lines[0].ma_vat == "VAT01"


def test_khop_ma_mapping_wins_over_gop_vat_fallback():
    mappings = [make_mapping_row(2, "SP01", "Sản phẩm 1", "VAT-KHOP")]
    stocks = [
        make_stock_row(2, "MAY", "VAT-GOP", "KT Gộp", "Cái", 100),
        make_stock_row(3, "CAO", "VAT-KHOP", "KT Khớp", "Cái", 100),
    ]
    stocks[0].ma_kiot_dai_dien = "SP01"
    stocks[0].ten_kiot_dai_dien = "Tên từ Gộp VAT"

    result = _run([SourceLookupInput(1, ma_sp="SP01", sl=25)], mappings, stocks)

    assert not result.issues and not result.shortages
    assert _plan(result) == [("CAO", 25)]
    assert result.lines[0].ma_vat == "VAT-KHOP"


# 8. SL rỗng, bằng 0, âm hoặc không phải số ----------------------------------


def test_invalid_quantities_are_reported_without_allocation():
    stocks = [make_stock_row(2, "MAY", "VAT01", "KT1", "Cái", 100)]

    result = _run(
        [
            SourceLookupInput(1, ma_sp="SP01", sl=""),
            SourceLookupInput(2, ma_sp="SP01", sl=0),
            SourceLookupInput(3, ma_sp="SP01", sl=-5),
            SourceLookupInput(4, ma_sp="SP01", sl="abc"),
            SourceLookupInput(5, ma_sp="SP01", sl=None),
        ],
        _mappings(),
        stocks,
    )

    assert not result.lines and not result.shortages
    assert [issue.issue_type for issue in result.issues] == [
        "sl_trong",
        "sl_khong_duong",
        "sl_khong_duong",
        "sl_khong_phai_so",
        "sl_trong",
    ]


def test_empty_input_is_safe():
    result = allocate_invoice_sources([], [], [], config=_config())

    assert not result.lines and not result.issues and not result.shortages


# 9. Nguồn có tồn bằng 0 hoặc trống ------------------------------------------


def test_zero_and_empty_stock_rows_are_skipped():
    stocks = [
        make_stock_row(2, "MAY", "VAT01", "KT1", "Cái", 0),
        make_stock_row(3, "CAO", "VAT01", "KT2", "Cái", -3),
        make_stock_row(4, "Vận chuyển", "VAT01", "KT3", "Cái", 80),
    ]

    result = _run([SourceLookupInput(1, ma_sp="SP01", sl=80)], _mappings(), stocks)

    assert _plan(result) == [("Vận chuyển", 80)]
    assert result.skipped_non_positive_stock_count == 2


def test_product_with_only_zero_stock_is_recognized_then_reported_as_shortage():
    stocks = [make_stock_row(2, "MAY", "VAT01", "KT1", "Cái", 0)]

    result = _run([SourceLookupInput(1, ma_sp="SP01", sl=10)], _mappings(), stocks)

    assert not result.lines
    assert not result.issues
    assert len(result.shortages) == 1
    assert result.shortages[0].ma_sp == "SP01"
    assert result.shortages[0].tong_ton == 0
    assert result.shortages[0].thieu == 10
    assert result.skipped_non_positive_stock_count == 1


def test_non_positive_stock_does_not_bias_source_frequency():
    mappings = _mappings() + [make_mapping_row(3, "SP02", "Sản phẩm 2", "VAT02")]
    stocks = [
        make_stock_row(2, "MAY", "VAT01", "KT1", "Cái", 100),
        make_stock_row(3, "CAO", "VAT01", "KT2", "Cái", 100),
        make_stock_row(4, "CAO", "VAT02", "KT3", "Cái", 0),
    ]

    result = _run(
        [
            SourceLookupInput(1, ma_sp="SP01", sl=50),
            SourceLookupInput(2, ma_sp="SP02", sl=1),
        ],
        mappings,
        stocks,
    )

    # SP02 hết tồn không được làm CAO trông như nguồn xuất hiện thường xuyên hơn.
    assert _plan(result) == [("MAY", 50)]
    assert [shortage.ma_sp for shortage in result.shortages] == ["SP02"]


# 10. Nhiều sản phẩm cùng lúc, có hợp lệ và không hợp lệ ---------------------


def test_valid_and_invalid_products_are_separated_and_keep_input_order():
    mappings = [
        make_mapping_row(2, "SP01", "Sản phẩm 1", "VAT01"),
        make_mapping_row(3, "SP02", "Sản phẩm 2", "VAT02"),
        make_mapping_row(4, "SP03", "Sản phẩm 3", "VAT03"),
    ]
    stocks = [
        make_stock_row(2, "MAY", "VAT01", "KT1", "Cái", 100),
        make_stock_row(3, "CAO", "VAT02", "KT2", "Cái", 10),
        make_stock_row(4, "MAY", "VAT03", "KT3", "Cái", 40),
        make_stock_row(5, "CAO", "VAT03", "KT4", "Cái", 40),
    ]

    result = _run(
        [
            SourceLookupInput(1, ma_sp="SP01", sl=60),
            SourceLookupInput(2, ma_sp="SP02", sl=50),  # thiếu tồn
            SourceLookupInput(3, ma_sp="SP03", sl=70),
        ],
        mappings,
        stocks,
    )

    assert [line.ma_sp for line in result.lines] == ["SP01", "SP03", "SP03"]
    assert [line.query_order for line in result.lines] == [1, 3, 3]
    assert [shortage.ma_sp for shortage in result.shortages] == ["SP02"]
    assert _plan(result) == [("MAY", 60), ("MAY", 40), ("CAO", 30)]


# Bất biến chung -------------------------------------------------------------


def test_allocation_never_exceeds_request_or_stock():
    stocks = [
        make_stock_row(2, "MAY", "VAT01", "KT1", "Cái", 33),
        make_stock_row(3, "CAO", "VAT01", "KT2", "Cái", 44),
        make_stock_row(4, "Vận chuyển", "VAT01", "KT3", "Cái", 55),
    ]

    result = _run([SourceLookupInput(1, ma_sp="SP01", sl=100)], _mappings(), stocks)

    ton_by_row = {2: 33, 3: 44, 4: 55}
    assert sum(line.sl_phan_bo for line in result.lines) == 100
    assert all(line.sl_phan_bo > 0 for line in result.lines)
    for line in result.lines:
        assert line.sl_phan_bo <= line.ton_con_nhap
    assert sum(ton_by_row.values()) >= 100


def test_display_rows_keep_business_columns():
    stocks = [make_stock_row(2, "MAY", "VAT01", "KT1", "Cái", 150, thue_vat=0.08)]

    result = _run(
        [SourceLookupInput(1, ma_sp="SP01", sl="100", gia_ban="11,500")], _mappings(), stocks
    )
    rows = build_allocation_display_rows(result.lines)

    assert list(rows[0]) == [
        "MÃ SP",
        "TÊN SP",
        "SL",
        "Giá bán",
        "Mã VAT",
        "TÊN VAT",
        "TÊN KẾ TOÁN",
        "ĐVT",
        "NGUỒN",
        "TỒN CÒN NHÁP",
        "%VAT",
        "GIÁ NHÁP (Giá bán/(1+%VAT))",
    ]
    assert rows[0]["SL"] == 100
    assert rows[0]["Giá bán"] == 11500
    assert rows[0]["GIÁ NHÁP (Giá bán/(1+%VAT))"] == 10648.15


def test_invoice_page_renders_allocation_and_shortage_tables(monkeypatch):
    """Trang Xử lý hóa đơn chạy được toàn bộ luồng dán -> phân bổ -> hiển thị."""

    monkeypatch.setattr(st, "page_link", lambda *args, **kwargs: None)

    page = Path(__file__).resolve().parent.parent / "pages" / "01_xu_ly_hoa_don.py"
    app = AppTest.from_file(str(page), default_timeout=30)
    app.session_state["current_workbook"] = WorkbookCheckResult(
        is_valid=True,
        file_name="test.xlsx",
        file_size_bytes=0,
        sha256="",
        stock_rows=[
            make_stock_row(2, "MAY", "VAT01", "KT1", "Cái", 150),
            make_stock_row(3, "CAO", "VAT01", "KT2", "Cái", 100),
            make_stock_row(4, "MAY", "VAT02", "KT3", "Cái", 5),
        ],
        mapping_rows=[
            make_mapping_row(2, "SP01", "Sản phẩm 1", "VAT01"),
            make_mapping_row(3, "SP02", "Sản phẩm 2", "VAT02"),
        ],
    )
    app.session_state["sheets_timestamp"] = "03/08/2026 10:00:00"
    app.run()

    app.text_area(key="paste_area").set_value(
        "SP01\tSản phẩm 1\t200\t10000\n"
        "SP02\tSản phẩm 2\t50\t9000\n"
        "KHONGCO\tSản phẩm không có\t10\t8000"
    )
    app.button(key="paste-read-btn").click().run()

    assert not [exception.message for exception in app.exception]

    result = app.session_state["check_result"]
    assert _plan(result) == [("MAY", 150), ("CAO", 50)]
    assert [shortage.ma_sp for shortage in result.shortages] == ["SP02"]
    assert [issue.ma_sp for issue in result.issues] == ["KHONGCO"]

    tables = [dataframe.value for dataframe in app.dataframe]
    unified_table = next(table for table in tables if "Trạng thái" in table.columns)
    assert "NGUỒN" in unified_table.columns
    assert "Ghi chú" not in unified_table.columns
    assert set(unified_table["Trạng thái"]) == {"OK", "Thiếu tồn", "Không có mã"}
    assert list(unified_table.loc[unified_table["MÃ SP"] == "SP02", "Trạng thái"]) == ["Thiếu tồn"]
    assert list(unified_table.loc[unified_table["MÃ SP"] == "KHONGCO", "Trạng thái"]) == ["Không có mã"]

    subheaders = [subheader.value for subheader in app.subheader]
    assert "Danh sách sản phẩm" in subheaders


def test_shortage_display_rows():
    stocks = [make_stock_row(2, "MAY", "VAT01", "KT1", "Cái", 10)]

    result = _run([SourceLookupInput(1, ma_sp="SP01", sl=25)], _mappings(), stocks)
    rows = build_shortage_display_rows(result.shortages)

    assert rows[0]["MÃ SP"] == "SP01"
    assert rows[0]["SL"] == 25
    assert rows[0]["TỒN CÒN NHÁP"] == 10
    assert rows[0]["NGUỒN"] == "MAY"
    assert rows[0]["Ghi chú"] == "Không đủ số lượng tồn"


def test_unified_rows_keep_same_invoice_code_adjacent():
    """Gộp 3 nhóm kết quả; các dòng cùng Mã hóa đơn phải luôn liền kề nhau."""

    stocks = [
        make_stock_row(2, "MAY", "VAT01", "KT1", "Cái", 150),
        make_stock_row(3, "MAY", "VAT03", "KT3", "Cái", 5),
    ]
    mappings = [
        make_mapping_row(2, "SP01", "Sản phẩm 1", "VAT01"),
        make_mapping_row(4, "SP03", "Sản phẩm 3", "VAT03"),
    ]

    queries = [
        SourceLookupInput(1, ma_sp="SP01", sl=50, ma_hoa_don="HD1"),  # OK, HD1
        SourceLookupInput(2, ma_sp="SP02", sl=5, ma_hoa_don="HD2"),  # không có mã, HD2
        SourceLookupInput(3, ma_sp="SP03", sl=50, ma_hoa_don="HD1"),  # thiếu tồn, HD1
    ]

    result = _run(queries, mappings, stocks)
    rows = build_unified_display_rows(result.lines, result.shortages, result.issues)

    assert [row["Mã hóa đơn"] for row in rows] == ["HD1", "HD1", "HD2"]
    assert [row["MÃ SP"] for row in rows] == ["SP01", "SP03", "SP02"]
    assert [row["Trạng thái"] for row in rows] == ["OK", "Thiếu tồn", "Không có mã"]
    # Trạng thái đã hiện "Thiếu tồn" nên cột Ghi chú không lặp lại lý do này.
    assert rows[1]["Ghi chú"] == ""
    assert "Không tìm thấy" in rows[2]["Ghi chú"]


def test_unavailable_rows_explain_presence_in_each_sheet():
    mappings = [make_mapping_row(2, "ONLY-KHOP", "Chỉ Khớp", "VAT-MISSING")]
    stocks = [make_stock_row(2, "MAY", "VAT-GOP", "KT", "Cái", 10)]
    stocks[0].ma_kiot_dai_dien = "ONLY-GOP"
    issues = [
        SourceLookupIssue(1, "NOWHERE", "Không đâu", "khong_tim_thay_ma", "Không tìm thấy mã."),
        SourceLookupIssue(2, "ONLY-KHOP", "Chỉ Khớp", "khong_con_ton_duong", "Không có nguồn."),
        SourceLookupIssue(3, "ONLY-GOP", "Chỉ Gộp", "ma_vat_khong_duy_nhat", "Cần kiểm tra VAT."),
    ]

    rows = build_unavailable_display_rows(issues, mappings, stocks)

    assert [row["Trạng thái trong file"] for row in rows] == [
        "Không có trong cả 2 sheet",
        "Chỉ có trong Khớp mã",
        "Chỉ có trong Gộp VAT",
    ]
    assert "cả Gộp VAT và Khớp mã" in rows[0]["Nội dung"]
    assert "sheet Gộp VAT" in rows[1]["Nội dung"]
    assert "sheet Khớp mã" in rows[2]["Nội dung"]
