"""Smoke test để phát hiện lỗi import/render ở từng trang Streamlit."""

from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from src.config import load_config
from src.excel_reader import WorkbookCheckResult

APP_ROOT = Path(__file__).resolve().parent.parent
PAGE_FILES = [
    "app.py",
    "pages/01_xu_ly_hoa_don.py",
    "pages/02_tra_cuu_nguon.py",
    "pages/02_quan_ly_du_lieu.py",
    "pages/03_kiem_tra_du_lieu.py",
    "pages/04_cau_hinh.py",
]


@pytest.mark.parametrize("relative_path", PAGE_FILES)
def test_streamlit_page_renders_without_exception(monkeypatch, tmp_path, relative_path):
    monkeypatch.setenv("LOCAL_STORAGE_ROOT", str(tmp_path / "local_storage"))
    # AppTest chạy từng page như một script độc lập nên không có multipage
    # registry để st.page_link tra url_pathname. Điều hướng thật được kiểm tra
    # riêng qua app đang chạy trong browser smoke test.
    monkeypatch.setattr(st, "page_link", lambda *args, **kwargs: None)
    load_config.cache_clear()

    app = AppTest.from_file(str(APP_ROOT / relative_path), default_timeout=30).run()

    messages = [exception.message for exception in app.exception]
    assert not messages, messages


def test_data_management_renders_invalid_upload_state(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCAL_STORAGE_ROOT", str(tmp_path / "local_storage"))
    monkeypatch.setattr(st, "page_link", lambda *args, **kwargs: None)
    load_config.cache_clear()

    app = AppTest.from_file(
        str(APP_ROOT / "pages/02_quan_ly_du_lieu.py"), default_timeout=30
    )
    app.session_state["pending_check"] = WorkbookCheckResult(
        is_valid=False,
        file_name="file_loi.xlsx",
        file_size_bytes=0,
        sha256="",
        errors=["Thiếu sheet bắt buộc: Gộp VAT"],
    )
    app.run()

    messages = [exception.message for exception in app.exception]
    assert not messages, messages
    assert any("File có lỗi" in element.value for element in app.error)
