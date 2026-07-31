"""Bố cục và điều hướng dùng chung giữa các trang.

Không dùng sidebar để tối đa chiều ngang hiển thị kết quả (giống xem trên
Excel). Điều hướng và trạng thái dữ liệu gói gọn trong một thanh trên cùng.
"""

from __future__ import annotations

import os
import tempfile

import streamlit as st

from src.auth import Role
from src.excel_reader import read_and_validate_workbook
from src.session import confirm_new_current_file
from src.storage.base import FileVersionMetadata

FEATURE_PAGES: dict[str, tuple[str, str, str]] = {
    "xu_ly_hoa_don": ("pages/01_xu_ly_hoa_don.py", "Xử lý hóa đơn", "🧾"),
    "tra_cuu_nguon": ("pages/02_tra_cuu_nguon.py", "Tra cứu nguồn", "🔎"),
}

ADMIN_PAGES: list[tuple[str, str, str]] = [
    ("pages/02_quan_ly_du_lieu.py", "Quản lý dữ liệu", "🗂️"),
    ("pages/03_kiem_tra_du_lieu.py", "Kiểm tra dữ liệu", "✅"),
    ("pages/04_cau_hinh.py", "Cấu hình", "⚙️"),
]


def _render_admin_popover(*, key: str) -> None:
    with st.popover("⚙️", help="Quản trị", key=key):
        st.caption("QUẢN TRỊ")
        for page, label, icon in ADMIN_PAGES:
            st.page_link(page, label=label, icon=icon)


def _render_upload_popover(*, config, user, key: str) -> None:
    with st.popover("📤", help="Cập nhật dữ liệu", key=key):
        st.markdown("**Cập nhật dữ liệu hiện tại**")
        if user is None or user.role != Role.ADMIN:
            st.caption(
                "Chỉ Admin mới có thể cập nhật dữ liệu. Vào mục Quản trị › "
                "Quản lý dữ liệu để biết thêm."
            )
            return

        st.caption("Upload file Excel mới; chỉ áp dụng sau khi kiểm tra hợp lệ và xác nhận.")
        uploaded_file = st.file_uploader(
            "Upload file .xlsx",
            type=["xlsx"],
            label_visibility="collapsed",
            key=f"{key}-file",
        )
        if uploaded_file is None:
            return

        file_bytes = uploaded_file.getvalue()
        tmp_path = os.path.join(tempfile.gettempdir(), f"quick_upload_{uploaded_file.name}")
        with open(tmp_path, "wb") as file_handle:
            file_handle.write(file_bytes)
        check = read_and_validate_workbook(tmp_path, file_name=uploaded_file.name)

        if not check.is_valid:
            st.error("File có lỗi, chưa thể dùng làm dữ liệu hiện tại:")
            for error in check.errors:
                st.write(f"- {error}")
            return

        st.success("File hợp lệ và có thể dùng làm dữ liệu hiện tại.")
        if st.button("✅ Dùng làm dữ liệu hiện tại", key=f"{key}-confirm"):
            version_id = confirm_new_current_file(
                file_bytes, uploaded_file.name, check, uploaded_by=user.email
            )
            st.success(f"Đã cập nhật dữ liệu hiện tại (phiên bản {version_id}).")
            st.rerun()


def render_feature_top_bar(
    *,
    active: str,
    meta: FileVersionMetadata | None,
    config,
    user,
) -> None:
    """Thanh trên cùng cho 2 trang chính: tiêu đề, nút chuyển chức năng, trạng thái dữ liệu."""

    _page, title, icon = FEATURE_PAGES[active]
    other_key = "tra_cuu_nguon" if active == "xu_ly_hoa_don" else "xu_ly_hoa_don"
    other_page, other_title, other_icon = FEATURE_PAGES[other_key]

    title_col, switch_col, status_col, upload_col, admin_col = st.columns(
        [3.2, 1.7, 2.4, 0.4, 0.4], gap="small"
    )
    with title_col:
        st.markdown(f"## {icon} {title}")
    with switch_col:
        with st.container(key=f"switch-to-{other_key}"):
            st.page_link(other_page, label=f"Chuyển sang {other_title}", icon=other_icon)
    with status_col:
        if meta is not None:
            st.markdown(
                f"<div class='data-status-inline'>🟢 <b>{meta.original_file_name}</b></div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                "<div class='data-status-inline data-status-inline--missing'>"
                "⚪ Chưa có dữ liệu</div>",
                unsafe_allow_html=True,
            )
    with upload_col:
        _render_upload_popover(config=config, user=user, key=f"upload-popover-{active}")
    with admin_col:
        _render_admin_popover(key=f"admin-popover-{active}")
    st.divider()


def render_admin_top_bar(
    *,
    title: str,
    icon: str,
    description: str | None = None,
    meta: FileVersionMetadata | None = None,
) -> None:
    """Thanh trên cùng gọn cho các trang quản trị (Quản lý dữ liệu, Kiểm tra dữ liệu, Cấu hình)."""

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
    if meta is not None:
        st.caption(f"Dữ liệu hiện tại: {meta.original_file_name}")
    st.divider()
