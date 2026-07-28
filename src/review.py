"""Xây bảng để người dùng tải và đưa cho AI kiểm tra tên thủ công BÊN NGOÀI app
(mục 16 CLAUDE.md). Bản thân app không gọi AI ở đây — chỉ tính điểm
deterministic và đánh dấu các trường hợp cần chú ý.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.config import AppConfig
from src.models import MappingRow, StockRow
from src.name_matching import calculate_accounting_name_score
from src.normalization import normalize_name_for_matching


@dataclass
class ManualReviewRow:
    ma_sp: str
    ten_sp: str
    ma_vat: str
    ten_vat: str
    ten_ke_toan: str
    diem_khop: float
    ly_do_danh_dau: str
    trang_thai: str  # "can_kiem_tra" | "ok"


def build_manual_review_report(
    mapping_rows: list[MappingRow], stock_rows: list[StockRow], config: AppConfig
) -> list[ManualReviewRow]:
    stock_by_vat: dict[str, list[StockRow]] = {}
    for s in stock_rows:
        if s.ma_vat_kiot_norm:
            stock_by_vat.setdefault(s.ma_vat_kiot_norm, []).append(s)

    report: list[ManualReviewRow] = []
    threshold = config.name_match.review_threshold

    seen_ma_sp_vat: dict[str, set[str]] = {}
    for m in mapping_rows:
        if m.ma_sp_norm:
            seen_ma_sp_vat.setdefault(m.ma_sp_norm, set()).add(m.ma_vat_kiot_norm)

    for m in mapping_rows:
        if not m.ma_sp:
            continue

        multi_vat = len(seen_ma_sp_vat.get(m.ma_sp_norm, set())) > 1

        candidates = stock_by_vat.get(m.ma_vat_kiot_norm, [])
        if not candidates:
            report.append(
                ManualReviewRow(
                    ma_sp=m.ma_sp,
                    ten_sp=m.ten_sp,
                    ma_vat=m.ma_vat_kiot,
                    ten_vat="",
                    ten_ke_toan="",
                    diem_khop=0.0,
                    ly_do_danh_dau="Mã VAT không tồn tại trong Gộp VAT hoặc không còn tồn dương.",
                    trang_thai="can_kiem_tra",
                )
            )
            continue

        best = None
        for stock in candidates:
            score_result = calculate_accounting_name_score(
                ten_ke_toan=stock.ten_ke_toan,
                user_ten_sp=m.ten_sp,
                khop_ma_ten_sp=m.ten_sp,
                ten_vat_kiot=stock.ten_vat_kiot,
                ten_truoc_vat_raw=m.ten_truoc_vat,
                weights=config.name_match,
            )
            if best is None or score_result.score > best[1].score:
                best = (stock, score_result)

        stock, score_result = best
        reasons = []
        if score_result.score < threshold:
            reasons.append(f"Điểm tên dưới ngưỡng ({score_result.score:.1f} < {threshold}).")
        if multi_vat:
            reasons.append("Một Mã SP trỏ tới nhiều Mã VAT.")

        n_ten_sp = normalize_name_for_matching(m.ten_sp)
        n_ten_vat = normalize_name_for_matching(stock.ten_vat_kiot)
        if n_ten_sp.word_tokens and n_ten_vat.word_tokens:
            common = set(n_ten_sp.word_tokens) & set(n_ten_vat.word_tokens)
            if not common:
                reasons.append("Tên SP và Tên VAT gần như không có từ chung.")

        report.append(
            ManualReviewRow(
                ma_sp=m.ma_sp,
                ten_sp=m.ten_sp,
                ma_vat=m.ma_vat_kiot,
                ten_vat=stock.ten_vat_kiot,
                ten_ke_toan=stock.ten_ke_toan,
                diem_khop=round(score_result.score, 1),
                ly_do_danh_dau="; ".join(reasons),
                trang_thai="can_kiem_tra" if reasons else "ok",
            )
        )

    return report
