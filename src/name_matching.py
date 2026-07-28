"""Xếp hạng TÊN KẾ TOÁN theo thuật toán deterministic (mục 10.1 CLAUDE.md).

Không dùng AI. Dùng RapidFuzz để so điểm chuỗi khi có sẵn; nếu môi trường
không cài được RapidFuzz (ví dụ sandbox không có mạng), dùng phần fallback
thuần Python dựa trên `difflib` với cùng thang điểm 0-100, để thuật toán vẫn
deterministic và không phụ thuộc AI. Trong triển khai thật (có `pip install`),
RapidFuzz sẽ được dùng như spec yêu cầu.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.config import NameMatchWeights
from src.normalization import (
    NormalizedName,
    normalize_name_for_matching,
    strip_price_and_vat_suffix,
)

try:  # pragma: no cover - phụ thuộc môi trường cài đặt
    from rapidfuzz import fuzz as _rf_fuzz

    def _token_sort_ratio(a: str, b: str) -> float:
        return _rf_fuzz.token_sort_ratio(a, b)

    FUZZY_BACKEND = "rapidfuzz"
except ImportError:  # pragma: no cover
    import difflib

    def _token_sort_ratio(a: str, b: str) -> float:
        """Xấp xỉ RapidFuzz.token_sort_ratio bằng difflib (thuần Python).

        Sắp xếp token rồi so bằng SequenceMatcher, quy về thang 0-100 giống
        RapidFuzz để phần còn lại của thuật toán không phải phân biệt backend.
        """

        ta = " ".join(sorted(a.split()))
        tb = " ".join(sorted(b.split()))
        if not ta and not tb:
            return 100.0
        if not ta or not tb:
            return 0.0
        ratio = difflib.SequenceMatcher(None, ta, tb).ratio()
        return ratio * 100.0

    FUZZY_BACKEND = "difflib_fallback"


@dataclass
class NameScoreResult:
    score: float
    reasons: list[str]


def _string_score(cleaned_a: str, cleaned_b: str) -> float:
    if not cleaned_a or not cleaned_b:
        return 0.0
    return _token_sort_ratio(cleaned_a, cleaned_b)


def _number_token_bonus_penalty(
    a: NormalizedName, b: NormalizedName, weights: NameMatchWeights
) -> tuple[float, list[str]]:
    reasons: list[str] = []
    if not a.number_tokens and not b.number_tokens:
        return 0.0, reasons

    set_a = set(a.number_tokens)
    set_b = set(b.number_tokens)

    if set_a and set_b:
        common = set_a & set_b
        if common:
            return weights.number_token_bonus, [f"Trùng token số/kích thước: {sorted(common)}"]
        # cả hai đều có token số nhưng không trùng -> mâu thuẫn
        return -weights.number_conflict_penalty, [
            f"Token số mâu thuẫn: {sorted(set_a)} vs {sorted(set_b)}"
        ]
    return 0.0, reasons


def calculate_accounting_name_score(
    ten_ke_toan: str,
    user_ten_sp: str,
    khop_ma_ten_sp: str,
    ten_vat_kiot: str,
    ten_truoc_vat_raw: str,
    weights: NameMatchWeights,
) -> NameScoreResult:
    """Tính điểm khớp giữa TÊN KẾ TOÁN và các nguồn tên tham chiếu.

    Trả về điểm trên thang khoảng 0-100 (có thể vượt nhẹ do bonus/penalty)
    kèm danh sách lý do để hiển thị trong phần giải thích kết quả.
    """

    n_ten_ke_toan = normalize_name_for_matching(ten_ke_toan)
    n_user_ten_sp = normalize_name_for_matching(user_ten_sp)
    n_khop_ma_ten_sp = normalize_name_for_matching(khop_ma_ten_sp)
    n_ten_vat_kiot = normalize_name_for_matching(ten_vat_kiot)
    n_ten_truoc_vat = normalize_name_for_matching(strip_price_and_vat_suffix(ten_truoc_vat_raw))

    s_user = _string_score(n_ten_ke_toan.cleaned_text, n_user_ten_sp.cleaned_text)
    s_khop_ma = _string_score(n_ten_ke_toan.cleaned_text, n_khop_ma_ten_sp.cleaned_text)
    s_vat_kiot = _string_score(n_ten_ke_toan.cleaned_text, n_ten_vat_kiot.cleaned_text)
    s_truoc_vat = _string_score(n_ten_ke_toan.cleaned_text, n_ten_truoc_vat.cleaned_text)

    base_score = (
        weights.weight_user_ten_sp * s_user
        + weights.weight_khopma_ten_sp * s_khop_ma
        + weights.weight_ten_vat_kiot * s_vat_kiot
        + weights.weight_ten_truoc_vat * s_truoc_vat
    )

    reasons = [
        f"So với Tên SP người dùng nhập: {s_user:.1f}",
        f"So với Tên SP trong Khớp mã: {s_khop_ma:.1f}",
        f"So với TÊN VAT KIOT: {s_vat_kiot:.1f}",
        f"So với Tên trước VAT (đã làm sạch): {s_truoc_vat:.1f}",
    ]

    # Thưởng/phạt token số & kích thước — so với nguồn tham chiếu mạnh nhất
    # (ưu tiên Tên SP người dùng nhập, vì đây là nguồn thực tế của hóa đơn).
    reference = n_user_ten_sp if n_user_ten_sp.number_tokens else n_khop_ma_ten_sp
    bonus, bonus_reasons = _number_token_bonus_penalty(n_ten_ke_toan, reference, weights)
    base_score += bonus
    reasons.extend(bonus_reasons)

    score = max(0.0, min(100.0, base_score))
    return NameScoreResult(score=score, reasons=reasons)
