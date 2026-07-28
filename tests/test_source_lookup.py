from src.source_lookup import SourceLookupInput, build_grouped_display_rows, lookup_sources

from tests.factories import make_mapping_row, make_stock_row


def test_lookup_by_code_returns_all_positive_sources_sorted_by_lowest_stock():
    mappings = [make_mapping_row(2, "SP01", "Sản phẩm 1", "VAT01", "Tên VAT 1")]
    stocks = [
        make_stock_row(2, "CAO", "VAT01", "Tên KT A", "Cái", 100),
        make_stock_row(3, "MAY", "VAT01", "Tên KT B", "Gói", 0),
        make_stock_row(4, "Vận chuyển", "VAT01", "Tên KT C", "Cái", 12),
        make_stock_row(5, "MAY", "VAT01", "Tên KT D", "Túi", -5),
        make_stock_row(6, "MAY", "VAT01", "Tên KT E", "Gói", 50),
    ]

    result = lookup_sources(
        [SourceLookupInput(1, ma_sp=" sp01 ", sl=10, gia_ban=12000)], mappings, stocks
    )

    assert not result.issues
    assert [line.ton_con_nhap for line in result.lines] == [12, 50, 100]
    assert [line.nguon for line in result.lines] == ["Vận chuyển", "MAY", "CAO"]
    assert all(line.ma_sp == "SP01" for line in result.lines)
    assert result.skipped_non_positive_stock_count == 2


def test_lookup_many_products_keeps_input_groups_and_sorts_each_group():
    mappings = [
        make_mapping_row(2, "SP01", "Sản phẩm 1", "VAT01"),
        make_mapping_row(3, "SP02", "Sản phẩm 2", "VAT02"),
    ]
    stocks = [
        make_stock_row(2, "A", "VAT01", "KT1", "Cái", 20),
        make_stock_row(3, "B", "VAT01", "KT1", "Cái", 5),
        make_stock_row(4, "C", "VAT02", "KT2", "Cái", 8),
        make_stock_row(5, "D", "VAT02", "KT2", "Cái", 2),
    ]

    result = lookup_sources(
        [SourceLookupInput(1, ma_sp="SP02"), SourceLookupInput(2, ma_sp="SP01")],
        mappings,
        stocks,
    )

    assert [(line.query_order, line.ton_con_nhap) for line in result.lines] == [
        (1, 2),
        (1, 8),
        (2, 5),
        (2, 20),
    ]


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


def test_product_with_only_zero_or_negative_stock_is_reported():
    mappings = [make_mapping_row(2, "SP01", "Sản phẩm 1", "VAT01")]
    stocks = [
        make_stock_row(2, "A", "VAT01", "KT1", "Cái", 0),
        make_stock_row(3, "B", "VAT01", "KT1", "Cái", -1),
    ]

    result = lookup_sources([SourceLookupInput(1, ma_sp="SP01")], mappings, stocks)

    assert not result.lines
    assert result.issues[0].issue_type == "khong_con_ton_duong"


def test_grouped_display_only_shows_kiot_fields_on_first_source_row():
    mappings = [
        make_mapping_row(2, "SP01", "Sản phẩm 1", "VAT01"),
        make_mapping_row(3, "SP02", "Sản phẩm 2", "VAT02"),
    ]
    stocks = [
        make_stock_row(2, "A", "VAT01", "KT1", "Cái", 5),
        make_stock_row(3, "B", "VAT01", "KT2", "Gói", 10),
        make_stock_row(4, "C", "VAT02", "KT3", "Bộ", 20),
    ]
    result = lookup_sources(
        [
            SourceLookupInput(1, ma_sp="SP01", sl=100, gia_ban=11500),
            SourceLookupInput(2, ma_sp="SP02", sl=200, gia_ban=2800),
        ],
        mappings,
        stocks,
    )

    rows = build_grouped_display_rows(result.lines)

    assert "Thứ tự nhập" not in rows[0]
    assert [rows[0]["Mã kiot"], rows[0]["Tên kiot"], rows[0]["SL"], rows[0]["Giá bán"]] == [
        "SP01",
        "Sản phẩm 1",
        100,
        11500,
    ]
    assert [rows[1]["Mã kiot"], rows[1]["Tên kiot"], rows[1]["SL"], rows[1]["Giá bán"]] == [
        "",
        "",
        "",
        "",
    ]
    assert rows[2]["Mã kiot"] == "SP02"
