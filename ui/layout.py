"""Bố cục và điều hướng dùng chung giữa các trang.

Điều hướng chính giữa các chức năng (Xử lý hóa đơn / Tra cứu nguồn / Tạo QR)
nằm trong sidebar bên trái; thanh trên cùng chỉ còn tiêu đề + trạng thái dữ
liệu + lối tắt quản trị.
"""

from __future__ import annotations

from html import escape
import streamlit as st

FEATURE_PAGES: dict[str, tuple[str, str, str]] = {
    "xu_ly_hoa_don": ("pages/01_xu_ly_hoa_don.py", "Xử lý hóa đơn", "🧾"),
    "tra_cuu_nguon": ("pages/02_tra_cuu_nguon.py", "Tra cứu nguồn", "🔎"),
    "tao_qr": ("pages/05_tao_qr.py", "Tạo QR", "💳"),
}

ADMIN_PAGES: list[tuple[str, str, str]] = [
    ("pages/03_kiem_tra_du_lieu.py", "Kiểm tra dữ liệu", "✅"),
    ("pages/04_cau_hinh.py", "Cấu hình", "⚙️"),
]


def render_sidebar_nav() -> None:
    """Sidebar điều hướng chính, dùng chung cho mọi trang.

    Streamlit tự làm nổi bật (bold) trang hiện tại trong ``st.page_link``,
    nên không cần truyền tham số ``active``.
    """

    with st.sidebar:
        st.markdown("### 🧾 Nháp VAT")
        for _key, (page, label, icon) in FEATURE_PAGES.items():
            st.page_link(page, label=label, icon=icon)


def _render_admin_popover(*, key: str) -> None:
    with st.popover("⚙️", help="Quản trị", key=key):
        st.caption("QUẢN TRỊ")
        for page, label, icon in ADMIN_PAGES:
            st.page_link(page, label=label, icon=icon)


def render_feature_top_bar(
    *,
    active: str,
    meta=None,
    config,
    user,
) -> bool:
    """Thanh trên cùng cho các trang chính. Trả về True nếu người dùng bấm nút Cập nhật."""

    render_sidebar_nav()

    _page, title, icon = FEATURE_PAGES[active]

    timestamp = st.session_state.get("sheets_timestamp")

    title_col, status_col, admin_col = st.columns([3.0, 6.0, 0.5], gap="small")
    with title_col:
        st.markdown(f"## {icon} {title}")
    with status_col:
        # Status text + nút refresh cùng 1 hàng trong status_col
        txt_col, btn_col = st.columns([1, 0.13], gap="small")
        with txt_col:
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
                    "⚪ Chưa có dữ liệu — đang tải...</div>",
                    unsafe_allow_html=True,
                )
        with btn_col:
            refresh_clicked = st.button(
                "🔄",
                key=f"refresh-btn-{active}",
                help="Cập nhật dữ liệu từ Google Sheets",
            )
    with admin_col:
        _render_admin_popover(key=f"admin-popover-{active}")
    st.divider()
    return refresh_clicked


def render_admin_top_bar(
    *,
    title: str,
    icon: str,
    description: str | None = None,
    meta=None,  # không dùng nữa, giữ tham số để không phá API cũ
) -> None:
    """Thanh trên cùng gọn cho các trang quản trị (Kiểm tra dữ liệu, Cấu hình)."""

    render_sidebar_nav()

    title_col, nav_col = st.columns([3.0, 3.2], gap="small")
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
