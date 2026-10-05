"""Tiện ích dùng chung cho các trang Streamlit: nạp cấu hình và dữ liệu
hiện tại vào `st.session_state`.

Không đặt business logic ở đây — chỉ điều phối gọi các module trong `src/`.
Dữ liệu được load tự động từ Google Sheets khi app khởi động và có thể
refresh thủ công qua nút trên sidebar.
"""

from __future__ import annotations

import streamlit as st

from src.config import AppConfig, load_config
from src.excel_reader import WorkbookCheckResult
from src.google_sheets_reader import fetch_workbook_from_sheets


_SHEETS_CACHE_TTL_SECONDS = 600


def get_config() -> AppConfig:
    return load_config()


def get_current_workbook() -> WorkbookCheckResult | None:
    """Trả về workbook hiện tại từ session_state (đã được load từ Google Sheets)."""
    return st.session_state.get("current_workbook")


def get_current_version_metadata():
    """Trả về None — không còn hệ thống versioning. Giữ API tương thích."""
    return None


def get_sheets_timestamp() -> str | None:
    """Trả về timestamp lần fetch Google Sheets gần nhất."""
    return st.session_state.get("sheets_timestamp")


@st.cache_resource(ttl=_SHEETS_CACHE_TTL_SECONDS, show_spinner=False)
def _fetch_workbook_shared(
    sheet_id: str, gid_gop_vat: int, gid_khop_ma: int
) -> tuple[WorkbookCheckResult, str]:
    """Fetch + parse một lần, dùng chung cho mọi phiên (tránh mỗi phiên tải lại và giữ 1 bản ~66MB).

    Workbook chỉ được đọc, không sửa. Exception không bị cache nên lần sau tự thử lại.
    """
    return fetch_workbook_from_sheets(
        sheet_id=sheet_id, gid_gop_vat=gid_gop_vat, gid_khop_ma=gid_khop_ma
    )


def load_workbook_from_sheets(
    config: AppConfig, force: bool = False
) -> tuple[WorkbookCheckResult, str]:
    """Lấy dữ liệu Google Sheets (cache dùng chung), lưu vào session_state.

    `force=True` (nút cập nhật thủ công) bỏ cache và tải lại.

    Returns:
        (workbook, timestamp)

    Raises:
        Exception: Nếu fetch hoặc parse thất bại.
    """
    if force:
        _fetch_workbook_shared.clear()
    workbook, timestamp = _fetch_workbook_shared(
        config.sheet_id, config.gid_gop_vat, config.gid_khop_ma
    )
    st.session_state["current_workbook"] = workbook
    st.session_state["sheets_timestamp"] = timestamp
    return workbook, timestamp
