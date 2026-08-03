"""Bố cục và điều hướng dùng chung giữa các trang.

Không dùng sidebar để tối đa chiều ngang hiển thị kết quả (giống xem trên
Excel). Điều hướng và trạng thái dữ liệu gói gọn trong một thanh trên cùng.
"""

from __future__ import annotations

from html import escape
import streamlit as st

FEATURE_PAGES: dict[str, tuple[str, str, str]] = {
    "xu_ly_hoa_don": ("pages/01_xu_ly_hoa_don.py", "Xử lý hóa đơn", "🧾"),
    "tra_cuu_nguon": ("pages/02_tra_cuu_nguon.py", "Tra cứu nguồn", "🔎"),
}

ADMIN_PAGES: list[tuple[str, str, str]] = [
    ("pages/03_kiem_tra_du_lieu.py", "Kiểm tra dữ liệu", "✅"),
    ("pages/04_cau_hinh.py", "Cấu hình", "⚙️"),
]


def _render_admin_popover(*, key: str) -> None:
    with st.popover("⚙️", help="Quản trị", key=key):
        st.caption("QUẢN TRỊ")
        for page, label, icon in ADMIN_PAGES:
            st.page_link(page, label=label, icon=icon)


def render_feature_top_bar(
    *,
    active: str,
    meta=None,  # không dùng nữa, giữ tham số để không phá API cũ
    config,
    user,
) -> None:
    """Thanh trên cùng cho 2 trang chính: tiêu đề, nút chuyển chức năng, trạng thái dữ liệu."""

    _page, title, icon = FEATURE_PAGES[active]
    other_key = "tra_cuu_nguon" if active == "xu_ly_hoa_don" else "xu_ly_hoa_don"
    other_page, other_title, other_icon = FEATURE_PAGES[other_key]

    timestamp = st.session_state.get("sheets_timestamp")

    title_col, switch_col, status_col, admin_col = st.columns(
        [2.8, 1.95, 3.5, 0.4], gap="small"
    )
    with title_col:
        st.markdown(f"## {icon} {title}")
    with switch_col:
        with st.container(key=f"switch-to-{other_key}"):
            st.page_link(other_page, label=f"Chuyển sang {other_title}", icon=other_icon)
    with status_col:
        if timestamp:
            st.markdown(
                "<div class='data-status-inline'>"
                "<span aria-hidden='true'>🟢</span>"
                "<b class='data-status-inline__file'>Google Sheets</b>"
                f"<span class='data-status-inline__updated'>Cập nhật {escape(timestamp)}</span>"
                "</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                "<div class='data-status-inline data-status-inline--missing'>"
                "⚪ Chưa có dữ liệu</div>",
                unsafe_allow_html=True,
            )
    with admin_col:
        _render_admin_popover(key=f"admin-popover-{active}")
    st.divider()


def render_admin_top_bar(
    *,
    title: str,
    icon: str,
    description: str | None = None,
    meta=None,  # không dùng nữa, giữ tham số để không phá API cũ
) -> None:
    """Thanh trên cùng gọn cho các trang quản trị (Kiểm tra dữ liệu, Cấu hình)."""

    back_col, title_col, nav_col = st.columns([1.3, 3.0, 3.2], gap="small")
    with back_col:
        st.page_link("pages/01_xu_ly_hoa_don.py", label="← Về trang chính")
    with title_col:
        st.markdown(f"## {icon} {title}")
    with nav_col:
        nav_columns = st.columns(len(ADMIN_PAGES), gap="small")
        for column, (page, label, page_icon) in zip(nav_columns, ADMIN_PAGES):
            with column:
                st.page_link(page, label=label, icon=page_icon)
    if description:
        st.caption(description)
    st.divider()
