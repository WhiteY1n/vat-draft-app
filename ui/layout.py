"""Bố cục và điều hướng dùng chung giữa các trang."""

from __future__ import annotations

import streamlit as st

from src.storage.base import FileVersionMetadata


def _format_updated_at(value: str) -> str:
    if not value:
        return "Chưa xác định"
    try:
        from datetime import datetime

        return datetime.fromisoformat(value).strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return value


def render_sidebar(metadata: FileVersionMetadata | None = None) -> None:
    """Hiển thị menu tiếng Việt và thông tin phiên bản dữ liệu ngắn gọn."""

    with st.sidebar:
        st.markdown("### Nháp VAT")
        st.caption("Công cụ nội bộ")

        st.page_link("app.py", label="Tổng quan", icon="🏠")
        st.page_link("pages/01_xu_ly_hoa_don.py", label="Xử lý hóa đơn", icon="🧾")
        st.page_link("pages/02_tra_cuu_nguon.py", label="Tra cứu nguồn", icon="🔎")
        st.page_link("pages/02_quan_ly_du_lieu.py", label="Quản lý dữ liệu", icon="🗂️")
        st.page_link("pages/03_kiem_tra_du_lieu.py", label="Kiểm tra dữ liệu", icon="✅")
        st.page_link("pages/04_cau_hinh.py", label="Cấu hình", icon="⚙️")

        st.divider()
        st.caption("DỮ LIỆU ĐANG DÙNG")
        if metadata is None:
            st.caption("Chưa có dữ liệu hiện tại")
        else:
            st.markdown(f"**{metadata.original_file_name}**")
            st.caption(f"Cập nhật: {_format_updated_at(metadata.uploaded_at)}")
