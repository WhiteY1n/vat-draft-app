"""Trang 4: Cấu hình. Trong MVP đọc từ config/settings.yaml, chưa cho sửa
trực tiếp trên UI (theo mục 15.4 CLAUDE.md — giả định an toàn được ghi ở README)."""

from __future__ import annotations

import streamlit as st

from src.session import get_config

st.set_page_config(page_title="Cấu hình", page_icon="⚙️", layout="wide")
st.title("Cấu hình")
st.caption(
    "Phiên bản MVP đọc cấu hình từ `config/settings.yaml`. Sửa file này rồi khởi động lại "
    "app (hoặc bổ sung tính năng sửa trực tiếp trên UI ở milestone sau)."
)

config = get_config()

st.subheader("Trọng số so khớp tên kế toán")
nm = config.name_match
st.table(
    {
        "Tham số": [
            "Tên SP người dùng nhập",
            "Tên SP trong Khớp mã",
            "TÊN VAT KIOT",
            "Tên trước VAT đã làm sạch",
            "Thưởng token số/kích thước trùng",
            "Thưởng kích thước trùng",
            "Phạt token số mâu thuẫn",
            "Phạt khác biến thể rõ ràng",
            "Ngưỡng cần kiểm tra thủ công",
        ],
        "Giá trị": [
            nm.weight_user_ten_sp,
            nm.weight_khopma_ten_sp,
            nm.weight_ten_vat_kiot,
            nm.weight_ten_truoc_vat,
            nm.number_token_bonus,
            nm.size_token_bonus,
            nm.number_conflict_penalty,
            nm.variant_conflict_penalty,
            nm.review_threshold,
        ],
    }
)

st.subheader("Thứ tự ưu tiên nguồn (tie-break)")
if config.source_tiebreak_priority:
    st.write(" → ".join(config.source_tiebreak_priority))
else:
    st.write("(chưa cấu hình — chỉ dùng thứ tự tên nguồn tăng dần)")

st.subheader("Khác")
st.write(f"- Số phiên bản file giữ lại tối đa: **{config.max_versions_kept}**")
st.write(f"- Số chữ số thập phân của GIÁ NHÁP: **{config.gia_nhap_decimal_places}**")
st.write(f"- Cho phép SL lẻ: **{'Có' if config.allow_fractional_sl else 'Không'}**")
st.write(f"- Chế độ đăng nhập (AUTH_MODE): **{config.auth_mode}**")
