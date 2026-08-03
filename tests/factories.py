"""Helper để tạo nhanh dữ liệu test (StockRow, MappingRow, InvoiceInputRow)."""

from __future__ import annotations

from src.models import InvoiceInputRow, MappingRow, StockRow


def make_stock_row(
    row_index: int,
    nguon: str,
    ma_vat: str,
    ten_kt: str,
    dvt: str,
    ton: float,
    ten_vat: str = "TEN VAT MAU",
    gia_ban: float = 10000,
    thue_vat: float = 0.08,
    tong_dang_nhap: float = 0,
) -> StockRow:
    return StockRow(
        row_index=row_index,
        nguon=nguon,
        ma_kiot_dai_dien="",
        ten_kiot_dai_dien="",
        ma_vat_kiot=ma_vat,
        ten_vat_kiot=ten_vat,
        ma_ke_toan="MA_KT_MAU",
        ten_ke_toan=ten_kt,
        don_vi_tinh=dvt,
        ton_dau_ngay=ton,
        gia_ban=gia_ban,
        thue_vat=thue_vat,
        thue_nk=None,
        tong_thue_mat=None,
        tong_dang_nhap=tong_dang_nhap,
        ton_co_the_nhap=ton,
        ma_vat_kiot_norm=ma_vat.strip().lower(),
        ten_ke_toan_norm=ten_kt.strip().lower(),
        don_vi_tinh_norm=dvt.strip().lower(),
    )


def make_mapping_row(
    row_index: int, ma_sp: str, ten_sp: str, ma_vat: str, ten_truoc_vat: str = ""
) -> MappingRow:
    return MappingRow(
        row_index=row_index,
        ma_sp=ma_sp,
        ten_sp=ten_sp,
        ma_vat_kiot=ma_vat,
        ten_truoc_vat=ten_truoc_vat,
        ma_sp_norm=ma_sp.strip().lower(),
        ma_vat_kiot_norm=ma_vat.strip().lower(),
    )


def make_input_row(order_index: int, ma_sp: str, ten_sp: str, sl, gia_ban) -> InvoiceInputRow:
    return InvoiceInputRow(
        input_row_id=f"row-{order_index}",
        order_index=order_index,
        ma_sp=ma_sp,
        ten_sp=ten_sp,
        sl=sl,
        gia_ban=gia_ban,
    )
