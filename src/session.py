"""Tiện ích dùng chung cho các trang Streamlit: nạp cấu hình, storage, dữ liệu
hiện tại vào `st.session_state`. Không đặt business logic ở đây — chỉ điều
phối gọi các module trong `src/`.
"""

from __future__ import annotations

import datetime as _dt
import uuid
from pathlib import Path

import streamlit as st

from src.config import AppConfig, load_config
from src.excel_reader import WorkbookCheckResult, read_and_validate_workbook
from src.storage.base import FileVersionMetadata
from src.storage.local import LocalStorageAdapter


def get_config() -> AppConfig:
    return load_config()


def get_storage() -> LocalStorageAdapter:
    if "storage" not in st.session_state:
        config = get_config()
        root = Path(config.local_storage_root)
        root.mkdir(parents=True, exist_ok=True)
        st.session_state["storage"] = LocalStorageAdapter(root)
    return st.session_state["storage"]


def _load_current_workbook(storage: LocalStorageAdapter) -> WorkbookCheckResult | None:
    current_id = storage.get_current_version_id()
    if not current_id:
        return None
    path = storage.get_version_file_path(current_id)
    return read_and_validate_workbook(path)


def get_current_workbook() -> WorkbookCheckResult | None:
    """Trả về dữ liệu hiện tại (cache trong session_state, xóa cache khi đổi phiên bản)."""

    storage = get_storage()
    current_id = storage.get_current_version_id()

    cache_key = "current_workbook_cache"
    cache_id_key = "current_workbook_cache_id"

    if st.session_state.get(cache_id_key) != current_id:
        st.session_state[cache_key] = _load_current_workbook(storage) if current_id else None
        st.session_state[cache_id_key] = current_id

    return st.session_state.get(cache_key)


def get_current_version_metadata() -> FileVersionMetadata | None:
    storage = get_storage()
    current_id = storage.get_current_version_id()
    if not current_id:
        return None
    for m in storage.list_versions():
        if m.version_id == current_id:
            return m
    return None


def confirm_new_current_file(
    file_bytes: bytes,
    file_name: str,
    check_result: WorkbookCheckResult,
    uploaded_by: str | None,
) -> str:
    """Lưu phiên bản mới và cập nhật con trỏ hiện tại một cách atomic (mục 5.3)."""

    storage = get_storage()
    config = get_config()

    version_id = _dt.datetime.now().strftime("%Y%m%d%H%M%S") + "-" + uuid.uuid4().hex[:8]

    # 1) Lưu file mới thành công trước.
    storage.save_version_file(version_id, file_bytes, file_name)

    metadata = FileVersionMetadata(
        version_id=version_id,
        original_file_name=file_name,
        uploaded_at=_dt.datetime.now().isoformat(timespec="seconds"),
        uploaded_by=uploaded_by,
        sha256=check_result.sha256,
        gop_vat_row_count=check_result.gop_vat_summary.total_data_rows
        if check_result.gop_vat_summary
        else 0,
        khop_ma_row_count=check_result.khop_ma_summary.total_data_rows
        if check_result.khop_ma_summary
        else 0,
        check_status="valid" if check_result.is_valid else "invalid",
        is_current=False,
    )
    storage.save_metadata(metadata)

    # 2) Sau đó mới cập nhật con trỏ hiện tại (atomic).
    storage.set_current_version_id(version_id)
    storage.enforce_retention(config.max_versions_kept)

    # Xóa cache để nạp lại dữ liệu mới.
    st.session_state.pop("current_workbook_cache", None)
    st.session_state.pop("current_workbook_cache_id", None)

    return version_id
