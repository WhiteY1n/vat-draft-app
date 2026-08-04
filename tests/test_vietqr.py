"""Test tạo mã QR VietQR cho hóa đơn."""

from src.config import AppConfig, VietQrAccount, VietQrConfig
from src.invoice_allocation import InvoiceAllocationLine
from src.vietqr import (
    build_vietqr_image_url,
    compute_source_amounts,
    compute_total_amount,
    extract_invoice_code,
    extract_invoice_codes,
    format_amount_input,
    get_account_for_source,
    parse_amount_input,
)


def test_format_amount_input_adds_thousand_separators_and_suffix():
    assert format_amount_input(37037) == "37,037 đ"
    assert format_amount_input(0) == "0 đ"


def test_parse_amount_input_strips_formatting():
    assert parse_amount_input("37,037 đ") == 37037
    assert parse_amount_input("99000") == 99000
    assert parse_amount_input("") == 0
    assert parse_amount_input("   ") == 0


def test_format_then_parse_amount_input_roundtrips():
    assert parse_amount_input(format_amount_input(1500000)) == 1500000


def _line(nguon, gia_ban, gia_nhap, sl_phan_bo=1):
    return InvoiceAllocationLine(
        query_order=1,
        ma_sp="SP01",
        ten_sp="Sản phẩm 1",
        sl_yeu_cau=sl_phan_bo,
        sl_phan_bo=sl_phan_bo,
        gia_ban=gia_ban,
        ma_vat="VAT01",
        ten_vat="Tên VAT 1",
        ma_ke_toan="KT1",
        ten_ke_toan="Kế toán 1",
        dvt="Cái",
        nguon=nguon,
        ton_con_nhap=100,
        phan_tram_vat=0.1,
        gia_nhap=gia_nhap,
    )


def _config():
    return AppConfig(
        vietqr=VietQrConfig(
            template="compact2",
            accounts={
                "mbbank": VietQrAccount(key="mbbank", bank_id="MB", account_no="0389040222"),
                "vietinbank": VietQrAccount(key="vietinbank", bank_id="ICB", account_no="102875264435"),
            },
            source_account_map={"MAY": "mbbank", "CAO": "vietinbank"},
        )
    )


def test_extract_invoice_code_from_typical_file_name():
    assert (
        extract_invoice_code("ChiTietHoaDon_HD018699_KV01082026-162300-154.xlsx")
        == "HD018699"
    )


def test_extract_invoice_code_returns_none_when_missing():
    assert extract_invoice_code("bao_cao_thang.xlsx") is None


def test_extract_invoice_codes_dedupes_and_keeps_order():
    codes = extract_invoice_codes(
        [
            "ChiTietHoaDon_HD018700_KV01082026-162253-478.xlsx",
            "ChiTietHoaDon_HD018699_KV01082026-162300-154.xlsx",
            "ChiTietHoaDon_HD018700_ban_sao.xlsx",
        ]
    )
    assert codes == ["HD018700", "HD018699"]


def test_get_account_for_source_matches_regardless_of_accent_case():
    config = _config()
    account = get_account_for_source("may", config)
    assert account is not None
    assert account.account_no == "0389040222"


def test_get_account_for_source_returns_none_when_unmapped():
    config = _config()
    assert get_account_for_source("SAIGONHANOI", config) is None


def test_compute_source_amounts_sums_gia_ban_and_gia_nhap_per_source():
    lines = [
        _line("MAY", gia_ban=11000, gia_nhap=10000, sl_phan_bo=2),
        _line("MAY", gia_ban=5500, gia_nhap=5000, sl_phan_bo=1),
        _line("CAO", gia_ban=2200, gia_nhap=2000, sl_phan_bo=3),
    ]

    totals = compute_source_amounts(lines)

    assert totals["MAY"].tong_gia_ban == 11000 * 2 + 5500 * 1
    assert totals["MAY"].tong_gia_nhap == 10000 * 2 + 5000 * 1
    assert totals["MAY"].so_dong == 2
    assert totals["CAO"].tong_gia_ban == 2200 * 3
    assert totals["CAO"].thieu_don_gia is False


def test_compute_source_amounts_flags_missing_price():
    lines = [_line("MAY", gia_ban=None, gia_nhap=None)]

    totals = compute_source_amounts(lines)

    assert totals["MAY"].thieu_don_gia is True
    assert totals["MAY"].tong_gia_ban == 0
    assert totals["MAY"].tong_gia_nhap == 0


def test_compute_total_amount_sums_across_all_sources():
    lines = [
        _line("MAY", gia_ban=11000, gia_nhap=10000, sl_phan_bo=2),
        _line("CAO", gia_ban=2200, gia_nhap=2000, sl_phan_bo=3),
    ]

    total = compute_total_amount(lines)

    assert total.tong_gia_ban == 11000 * 2 + 2200 * 3
    assert total.tong_gia_nhap == 10000 * 2 + 2000 * 3
    assert total.so_dong == 2
    assert total.thieu_don_gia is False


def test_compute_total_amount_flags_missing_price():
    lines = [_line("MAY", gia_ban=None, gia_nhap=None)]

    total = compute_total_amount(lines)

    assert total.thieu_don_gia is True


def test_build_vietqr_image_url_contains_bank_account_and_query():
    account = VietQrAccount(key="mbbank", bank_id="MB", account_no="0389040222")

    url = build_vietqr_image_url(account, amount=1500000, add_info="HD018699", template="compact2")

    assert url.startswith("https://img.vietqr.io/image/MB-0389040222-compact2.png?")
    assert "amount=1500000" in url
    assert "addInfo=HD018699" in url


def test_build_vietqr_image_url_encodes_add_info_with_spaces():
    account = VietQrAccount(key="mbbank", bank_id="MB", account_no="0389040222")

    url = build_vietqr_image_url(account, amount=0, add_info="HD1 HD2", template="compact2")

    assert "addInfo=HD1%20HD2" in url
    assert "amount=&" in url
