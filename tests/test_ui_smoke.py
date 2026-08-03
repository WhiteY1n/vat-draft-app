"""Smoke test để phát hiện lỗi import/render ở từng trang Streamlit."""

from pathlib import Path
from unittest.mock import patch

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from src.config import load_config
from src.excel_reader import WorkbookCheckResult

APP_ROOT = Path(__file__).resolve().parent.parent
PAGE_FILES = [
    "pages/01_xu_ly_hoa_don.py",
    "pages/02_tra_cuu_nguon.py",
    "pages/03_kiem_tra_du_lieu.py",
    "pages/04_cau_hinh.py",
]


def _make_empty_workbook() -> WorkbookCheckResult:
    return WorkbookCheckResult(
        is_valid=True,
        file_name="Google Sheets",
        file_size_bytes=0,
        sha256="",
        stock_rows=[],
        mapping_rows=[],
    )


@pytest.mark.parametrize("relative_path", PAGE_FILES)
def test_streamlit_page_renders_without_exception(monkeypatch, relative_path):
    # Cung cấp workbook giả để trang không cần fetch Google Sheets thật
    monkeypatch.setattr(st, "page_link", lambda *args, **kwargs: None)
    load_config.cache_clear()

    app = AppTest.from_file(str(APP_ROOT / relative_path), default_timeout=30)
    app.session_state["current_workbook"] = _make_empty_workbook()
    app.session_state["sheets_timestamp"] = "03/08/2026 10:00:00"
    app.run()

    messages = [exception.message for exception in app.exception]
    assert not messages, messages


def test_app_py_renders_without_exception(monkeypatch):
    """app.py sẽ tự động fetch Google Sheets — mock hàm fetch để test không gọi mạng thật."""
    monkeypatch.setattr(st, "page_link", lambda *args, **kwargs: None)
    monkeypatch.setattr(st, "switch_page", lambda *args, **kwargs: None)
    load_config.cache_clear()

    app = AppTest.from_file(str(APP_ROOT / "app.py"), default_timeout=30)
    # Cung cấp workbook sẵn để bỏ qua bước fetch
    app.session_state["current_workbook"] = _make_empty_workbook()
    app.session_state["sheets_timestamp"] = "03/08/2026 10:00:00"
    app.run()

    messages = [exception.message for exception in app.exception]
    assert not messages, messages
