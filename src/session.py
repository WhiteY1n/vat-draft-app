"""Tiện ích dùng chung cho các trang Streamlit: nạp cấu hình, storage, dữ liệu
hiện tại vào `st.session_state`. Không đặt business logic ở đây — chỉ điều
phối gọi các module trong `src/`.
"""

from __future__ import annotations

import datetime as _dt
import uuid
import streamlit as st

from src.config import AppConfig, load_config
from src.excel_reader import WorkbookCheckResult, read_and_validate_workbook_bytes
from src.storage.base import FileVersionMetadata
from src.storage.session_memory import SessionMemoryStorageAdapter


def get_config() -> AppConfig:
    return load_config()


def get_storage() -> SessionMemoryStorageAdapter:
    # Replace an adapter left in an already-open session after a hot deploy.  This
    # also guarantees that the old shared-disk backend is never reused.
    if not isinstance(st.session_state.get("storage"), SessionMemoryStorageAdapter):
        st.session_state["storage"] = SessionMemoryStorageAdapter()
    return st.session_state["storage"]


def _load_current_workbook(storage: SessionMemoryStorageAdapter) -> WorkbookCheckResult | None:
    current_id = storage.get_current_version_id()
    if not current_id:
        return None
    metadata = next(
        (item for item in storage.list_versions() if item.version_id == current_id), None
    )
    if metadata is None:
        return None
    return read_and_validate_workbook_bytes(
        storage.load_version_file(current_id), metadata.original_file_name
    )


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
