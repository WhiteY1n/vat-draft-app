"""Xây bảng kết quả cuối cùng từ kết quả phân bổ (mục 13 CLAUDE.md)."""

from __future__ import annotations

from src.allocation import RowAllocation
from src.config import AppConfig
from src.models import AllocationResultLine


def build_result_lines(
    allocations: list[RowAllocation], config: AppConfig
) -> list[AllocationResultLine]:
    lines: list[AllocationResultLine] = []

    ordered = sorted(allocations, key=lambda a: a.selection.resolved_row.order_index)

    for stt, alloc in enumerate(ordered, start=1):
        if alloc.error is not None or not alloc.details:
            continue  # dòng lỗi không được đưa vào kết quả (đã hiện ở bảng lỗi)

        resolved_row = alloc.selection.resolved_row
        group = alloc.selection.chosen_group
        mapping_row = resolved_row.mapping_row

        for dong_idx, detail in enumerate(alloc.details, start=1):
            stock_row = detail.stock_row
            gia_ban = resolved_row.gia_ban
            phan_tram_vat = stock_row.thue_vat
            gia_nhap = None
            if phan_tram_vat is not None and (1 + phan_tram_vat) != 0:
                gia_nhap = round(
                    gia_ban / (1 + phan_tram_vat), config.gia_nhap_decimal_places
                )

            lines.append(
                AllocationResultLine(
                    stt_hoa_don=stt,
                    dong_phan_bo=dong_idx,
                    ma_sp=resolved_row.ma_sp,
                    ten_sp=resolved_row.ten_sp,
                    sl_yeu_cau=resolved_row.sl,
                    sl_phan_bo=detail.sl_phan_bo,
                    gia_ban=gia_ban,
                    ma_vat=mapping_row.ma_vat_kiot,
                    ten_vat=stock_row.ten_vat_kiot,
                    ten_ke_toan=group.ten_ke_toan,
                    dvt=group.don_vi_tinh,
                    nguon=stock_row.nguon,
                    ton_con_nhap_truoc=detail.ton_truoc,
                    ton_con_mo_phong_sau=detail.ton_sau,
                    phan_tram_vat=phan_tram_vat,
                    gia_nhap=gia_nhap,
                    diem_khop_ten=round(group.name_score, 1),
                    ly_do_chon=alloc.ly_do_chon,
                )
            )

    return lines
