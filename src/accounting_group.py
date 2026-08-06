"""Chọn một nhóm (TÊN KẾ TOÁN, Đơn vị tính) cho mỗi dòng hóa đơn (mục 10).

Một dòng hàng chỉ được chọn một TÊN KẾ TOÁN; có thể chia số lượng qua nhiều
nguồn miễn là giữ cùng TÊN KẾ TOÁN và Đơn vị tính.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.config import AppConfig
from src.models import AccountingGroupCandidate, RowError, StockRow
from src.name_matching import calculate_accounting_name_score
from src.validation import ResolvedInvoiceRow


@dataclass
class GroupSelection:
    resolved_row: ResolvedInvoiceRow
    chosen_group: AccountingGroupCandidate | None
    all_candidate_groups: list[AccountingGroupCandidate]
    error: RowError | None = None


def _group_stock_candidates(stock_candidates: list[StockRow]) -> dict[tuple[str, str], list[StockRow]]:
    groups: dict[tuple[str, str], list[StockRow]] = {}
    for s in stock_candidates:
        key = (s.ten_ke_toan_norm, s.don_vi_tinh_norm)
        groups.setdefault(key, []).append(s)
    return groups


def select_accounting_group_for_row(
    resolved_row: ResolvedInvoiceRow, config: AppConfig
) -> GroupSelection:
    groups_by_key = _group_stock_candidates(resolved_row.stock_candidates)

    candidates: list[AccountingGroupCandidate] = []
    for (ten_kt_norm, dvt_norm), stock_rows in groups_by_key.items():
        total_ton = sum(s.ton_co_the_nhap for s in stock_rows)
        # dùng tên gốc (chưa chuẩn hóa) của dòng đầu tiên để hiển thị/so điểm
        display_ten_kt = stock_rows[0].ten_ke_toan
        display_dvt = stock_rows[0].don_vi_tinh

        score_result = calculate_accounting_name_score(
            ten_ke_toan=display_ten_kt,
            user_ten_sp=resolved_row.ten_sp,
            khop_ma_ten_sp=resolved_row.mapping_row.ten_sp,
            ten_vat_kiot=stock_rows[0].ten_vat_kiot,
            ten_truoc_vat_raw=resolved_row.mapping_row.ten_truoc_vat,
            weights=config.name_match,
        )

        candidates.append(
            AccountingGroupCandidate(
                ten_ke_toan=display_ten_kt,
                don_vi_tinh=display_dvt,
                stock_rows=stock_rows,
                name_score=score_result.score,
                total_ton=total_ton,
                score_reasons=score_result.reasons,
            )
        )

    eligible = [c for c in candidates if c.total_ton >= resolved_row.sl]

    if not eligible:
        error = RowError(
            input_row_id=resolved_row.input_row_id,
            order_index=resolved_row.order_index,
            ma_sp=resolved_row.ma_sp,
            ten_sp=resolved_row.ten_sp,
            error_type="khong_du_ton_cung_ten_ke_toan",
            detail=(
                "Không đủ tồn cho cùng một Tên kế toán và Đơn vị tính "
                f"(cần {resolved_row.sl}, nhóm cao nhất có "
                f"{max((c.total_ton for c in candidates), default=0)})."
            ),
            suggestion="Kiểm tra lại tồn trong Gộp VAT hoặc giảm số lượng yêu cầu.",
        )
        return GroupSelection(
            resolved_row=resolved_row,
            chosen_group=None,
            all_candidate_groups=candidates,
            error=error,
        )

    def min_sources_needed(group: AccountingGroupCandidate) -> int:
        remaining = resolved_row.sl
        count = 0
        for s in sorted(group.stock_rows, key=lambda r: -r.ton_co_the_nhap):
            if remaining <= 0:
                break
            remaining -= s.ton_co_the_nhap
            count += 1
        return count

    eligible.sort(
        key=lambda g: (
            -g.name_score,
            min_sources_needed(g),
            g.total_ton,
            g.ten_ke_toan,
            g.don_vi_tinh,
        )
    )

    chosen = eligible[0]
    return GroupSelection(
        resolved_row=resolved_row,
        chosen_group=chosen,
        all_candidate_groups=candidates,
    )
