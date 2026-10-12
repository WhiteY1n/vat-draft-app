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


def load_workbook_from_sheets(config: AppConfig) -> tuple[WorkbookCheckResult, str]:
    """Fetch và parse dữ liệu từ Google Sheets, lưu vào session_state.

    Returns:
        (workbook, timestamp)

    Raises:
        Exception: Nếu fetch hoặc parse thất bại.
    """
    workbook, timestamp = fetch_workbook_from_sheets(
        sheet_id=config.sheet_id,
        gid_gop_vat=config.gid_gop_vat,
        gid_khop_ma=config.gid_khop_ma,
        gop_vat_columns=config.gop_vat_columns,
        khop_ma_columns=config.khop_ma_columns,
    )
    st.session_state["current_workbook"] = workbook
    st.session_state["sheets_timestamp"] = timestamp
    return workbook, timestamp
