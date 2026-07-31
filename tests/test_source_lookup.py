from src.config import AppConfig
from src.source_lookup import (
    SourceLookupInput,
    build_all_sources_display_rows,
    build_grouped_display_rows,
    lookup_all_sources,
    lookup_sources,
)

from tests.factories import make_mapping_row, make_stock_row


def _config():
    return AppConfig(source_tiebreak_priority=["Vận chuyển", "MAY", "CAO"])


def test_lookup_returns_one_line_and_uses_source_priority_when_all_are_enough():
    mappings = [make_mapping_row(2, "SP01", "Sản phẩm 1", "VAT01", "Tên VAT 1")]
    stocks = [
        make_stock_row(2, "CAO", "VAT01", "Tên KT A", "Cái", 100),
        make_stock_row(3, "MAY", "VAT01", "Tên KT B", "Gói", 0),
        make_stock_row(4, "Vận chuyển", "VAT01", "Tên KT C", "Cái", 12),
        make_stock_row(5, "MAY", "VAT01", "Tên KT D", "Túi", -5),
        make_stock_row(6, "MAY", "VAT01", "Tên KT E", "Gói", 50),
    ]

    result = lookup_sources(
        [SourceLookupInput(1, ma_sp=" sp01 ", sl=10, gia_ban=12000)],
        mappings,
        stocks,
        config=_config(),
    )

    assert not result.issues
    assert len(result.lines) == 1
    assert result.lines[0].nguon == "Vận chuyển"
    assert result.lines[0].ton_con_nhap == 12
    assert result.skipped_non_positive_stock_count == 1


def test_lookup_many_products_prefers_source_appearing_most_often():
    mappings = [
        make_mapping_row(2, "SP01", "Sản phẩm 1", "VAT01"),
        make_mapping_row(3, "SP02", "Sản phẩm 2", "VAT02"),
        make_mapping_row(4, "SP03", "Sản phẩm 3", "VAT03"),
        make_mapping_row(5, "SP04", "Sản phẩm 4", "VAT04"),
    ]
    stocks = [
        make_stock_row(2, "Vận chuyển", "VAT01", "KT1", "Cái", 20),
        make_stock_row(3, "MAY", "VAT01", "KT1 khác", "Cái", 20),
        make_stock_row(4, "Vận chuyển", "VAT02", "KT2", "Cái", 20),
        make_stock_row(5, "CAO", "VAT02", "KT2 khác", "Cái", 20),
        make_stock_row(6, "Vận chuyển", "VAT03", "KT3", "Cái", 20),
        make_stock_row(7, "MAY", "VAT04", "KT4", "Cái", 20),
    ]

    result = lookup_sources(
        [
            SourceLookupInput(1, ma_sp="SP01", sl=10),
            SourceLookupInput(2, ma_sp="SP02", sl=10),
            SourceLookupInput(3, ma_sp="SP03", sl=10),
            SourceLookupInput(4, ma_sp="SP04", sl=10),
        ],
        mappings,
        stocks,
        config=_config(),
    )

    assert len(result.lines) == 4
    assert [line.nguon for line in result.lines] == ["Vận chuyển", "Vận chuyển", "Vận chuyển", "MAY"]
    assert len({line.query_order for line in result.lines}) == 4


def test_when_no_source_is_enough_returns_largest_remaining_stock():
    mappings = [make_mapping_row(2, "SP01", "Sản phẩm 1", "VAT01")]
    stocks = [
        make_stock_row(2, "Vận chuyển", "VAT01", "KT vận chuyển", "Cái", 20),
        make_stock_row(3, "CAO", "VAT01", "KT cao", "Cái", 40),
    ]

    result = lookup_sources(
        [SourceLookupInput(1, ma_sp="SP01", sl=100)],
        mappings,
        stocks,
        config=_config(),
    )

    assert not result.issues
    assert len(result.lines) == 1
    assert result.lines[0].nguon == "CAO"
    assert result.lines[0].ton_con_nhap == 40


def test_zero_stock_is_returned_when_there_is_no_other_choice():
    mappings = [make_mapping_row(2, "SP01", "Sản phẩm 1", "VAT01")]
    stocks = [
        make_stock_row(2, "MAY", "VAT01", "KT1", "Cái", 0),
        make_stock_row(3, "CAO", "VAT01", "KT2", "Cái", -1),
    ]

    result = lookup_sources(
        [SourceLookupInput(1, ma_sp="SP01", sl=10)], mappings, stocks, config=_config()
    )

    assert not result.issues
    assert len(result.lines) == 1
    assert result.lines[0].nguon == "MAY"
    assert result.lines[0].ton_con_nhap == 0


def test_multiple_inputs_always_returned_without_shared_stock_deduction():
    mappings = [
        make_mapping_row(2, "DCGSM", "Đai chống gù size M", "VAT10655"),
        make_mapping_row(3, "DCGSL", "Đai chống gù size L", "VAT10655"),
        make_mapping_row(4, "CGGHV", "Chậu gấp gọn hình voi", "VAT10176"),
    ]
    stocks = [
        make_stock_row(2, "Vận chuyển", "VAT10655", "Đai chống gù", "Cái", 2200),
        make_stock_row(3, "Vận chuyển", "VAT10176", "Chậu nhựa", "Cái", 0),
    ]

    result = lookup_sources(
        [
            SourceLookupInput(1, ma_sp="DCGSM", sl=2200),
            SourceLookupInput(2, ma_sp="DCGSL", sl=1400),
            SourceLookupInput(3, ma_sp="CGGHV", sl=900),
        ],
        mappings,
        stocks,
        config=_config(),
    )

    assert not result.issues
    assert [line.ma_sp for line in result.lines] == ["DCGSM", "DCGSL", "CGGHV"]
    assert [line.ton_con_nhap for line in result.lines] == [2200, 2200, 0]


def test_each_product_returns_only_one_best_matching_accounting_name():
    mappings = [
        make_mapping_row(
            2,
            "SP01",
            "Bình nước 1 lít",
            "VAT01",
            "Bình nước 1 lít (VAT)",
        )
    ]
    stocks = [
        make_stock_row(2, "MAY", "VAT01", "Khăn lau nhà", "Cái", 100),
        make_stock_row(3, "MAY", "VAT01", "Bình nước 1 lít", "Cái", 100),
    ]

    result = lookup_sources(
        [SourceLookupInput(1, ma_sp="SP01", ten_sp="Bình nước 1 lít", sl=10)],
        mappings,
        stocks,
        config=_config(),
    )

    assert len(result.lines) == 1
    assert result.lines[0].ten_ke_toan == "Bình nước 1 lít"


def test_lookup_by_exact_product_name():
    mappings = [make_mapping_row(2, "SP01", "Sản phẩm 1", "VAT01")]
    stocks = [make_stock_row(2, "A", "VAT01", "KT1", "Cái", 20)]

    result = lookup_sources([SourceLookupInput(1, ten_sp=" sản phẩm 1 ")], mappings, stocks)

    assert not result.issues
    assert len(result.lines) == 1
    assert result.lines[0].ma_sp == "SP01"


def test_duplicate_product_name_requires_code():
    mappings = [
        make_mapping_row(2, "SP01", "Tên trùng", "VAT01"),
        make_mapping_row(3, "SP02", "Tên trùng", "VAT02"),
    ]

    result = lookup_sources([SourceLookupInput(1, ten_sp="Tên trùng")], mappings, [])

    assert not result.lines
    assert result.issues[0].issue_type == "ten_trung_nhieu_ma"


def test_display_rows_have_exact_invoice_columns_and_calculated_draft_price():
    mappings = [make_mapping_row(2, "SP01", "Sản phẩm 1", "VAT01", "Tên VAT 1")]
    stocks = [make_stock_row(2, "MAY", "VAT01", "KT1", "Cái", 5, thue_vat=0.08)]
    result = lookup_sources(
        [SourceLookupInput(1, ma_sp="SP01", sl="100", gia_ban="11,500")],
        mappings,
        stocks,
        config=_config(),
    )

    rows = build_grouped_display_rows(result.lines)

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


def test_all_sources_excludes_non_positive_and_sorts_low_stock_first():
    mappings = [make_mapping_row(2, "BTT8422", "Bông tẩy trang", "VAT10636")]
    stocks = [
        make_stock_row(2, "CAO", "VAT10636", "Bông tẩy trang", "Túi", 11403),
        make_stock_row(3, "MAY", "VAT10636", "Bông tẩy trang Hatsu", "Gói", 50),
        make_stock_row(4, "MAY", "VAT10636", "Bông tẩy trang", "Cái", 1),
        make_stock_row(5, "MAY", "VAT10636", "Hết tồn", "Gói", 0),
        make_stock_row(6, "CAO", "VAT10636", "Âm tồn", "Gói", -2),
    ]

    result = lookup_all_sources(
        [SourceLookupInput(1, ma_sp="BTT8422", sl=100, gia_ban=11500)],
        mappings,
        stocks,
        config=_config(),
    )

    assert not result.issues
    assert [line.ton_con_nhap for line in result.lines] == [1, 50, 11403]
    assert result.skipped_non_positive_stock_count == 2


def test_all_sources_display_blanks_repeated_input_columns():
    mappings = [make_mapping_row(2, "SP01", "Sản phẩm 1", "VAT01")]
    stocks = [
        make_stock_row(2, "MAY", "VAT01", "KT1", "Cái", 5),
        make_stock_row(3, "CAO", "VAT01", "KT2", "Gói", 10),
    ]
    result = lookup_all_sources(
        [SourceLookupInput(1, ma_sp="SP01", sl=3, gia_ban=1000)],
        mappings,
        stocks,
    )

    rows = build_all_sources_display_rows(result.lines)

    assert list(rows[0]) == [
        "Mã kiot",
        "Tên kiot",
        "SL",
        "Giá bán",
        "Mã VAT",
        "Tên VAT",
        "Mã kế toán",
        "ĐVT",
        "Nguồn",
        "Tồn nháp được",
        "%VAT",
    ]
    assert rows[0]["Mã kiot"] == "SP01"
    assert rows[1]["Mã kiot"] == ""
    assert rows[1]["Tên kiot"] == ""
    assert rows[1]["SL"] == ""
    assert rows[1]["Giá bán"] == ""
