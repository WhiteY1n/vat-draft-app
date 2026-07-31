"""Trang quản lý dữ liệu — upload, xác nhận, lịch sử và khôi phục phiên bản."""

from __future__ import annotations

from datetime import datetime
import io
import os
import tempfile

import pandas as pd
import streamlit as st

from src.auth import Role, get_current_user
from src.excel_reader import read_and_validate_workbook
from src.session import (
    confirm_new_current_file,
    get_config,
    get_current_version_metadata,
    get_storage,
)
from ui import (
    apply_global_styles,
    render_admin_top_bar,
    render_empty_state,
    render_section_header,
)

st.set_page_config(
    page_title="Quản lý dữ liệu", page_icon="🗂️", layout="wide", initial_sidebar_state="collapsed"
)
apply_global_styles()

metadata = get_current_version_metadata()
render_admin_top_bar(
    title="Quản lý dữ liệu",
    icon="🗂️",
    description="Theo dõi file đang dùng, kiểm tra phiên bản mới trước khi xác nhận và khôi phục khi cần.",
    meta=metadata,
)

config = get_config()
user = get_current_user(config, session_email=st.session_state.get("user_email"))

if user.role != Role.ADMIN:
    st.error("Trang này chỉ dành cho Admin.")
    st.stop()

storage = get_storage()

render_section_header("1. Dữ liệu hiện tại")
if metadata is None:
    render_empty_state(
        "Chưa có file dữ liệu hiện tại",
        "Hãy tải lên một file Excel hợp lệ ở khu vực bên dưới và xác nhận trước khi sử dụng.",
    )
else:
    with st.container(border=True):
        try:
            updated_at = datetime.fromisoformat(metadata.uploaded_at).strftime("%d/%m/%Y %H:%M")
        except ValueError:
            updated_at = metadata.uploaded_at
        status_label = "Hợp lệ" if metadata.check_status == "valid" else "Không hợp lệ"
        st.markdown(f"**📄 {metadata.original_file_name}** · :green[**{status_label}**]")
        st.caption(
            f"{metadata.gop_vat_row_count:,} dòng Gộp VAT · "
            f"{metadata.khop_ma_row_count:,} dòng Khớp mã · "
            f"Cập nhật {updated_at}"
        )

render_section_header(
    "2. Upload phiên bản mới",
    "File chỉ trở thành dữ liệu hiện tại sau khi kiểm tra hợp lệ và bạn bấm xác nhận.",
)
with st.container(border=True):
    st.markdown("**Chọn file dữ liệu Excel mới**")
    st.caption("Kéo thả file vào vùng bên dưới hoặc bấm nút để chọn file từ máy tính.")
    uploaded_file = st.file_uploader("Upload file .xlsx", type=["xlsx"], label_visibility="collapsed")

    if uploaded_file is not None:
        file_bytes = uploaded_file.getvalue()
        file_columns = st.columns(2)
        file_columns[0].write(f"**Tên file:** {uploaded_file.name}")
        file_columns[1].write(f"**Dung lượng:** {len(file_bytes):,} bytes")

        tmp_path = os.path.join(tempfile.gettempdir(), f"upload_check_{uploaded_file.name}")
        with open(tmp_path, "wb") as file_handle:
            file_handle.write(file_bytes)

        check = read_and_validate_workbook(tmp_path, file_name=uploaded_file.name)
        st.session_state["pending_check"] = check
        st.session_state["pending_file_bytes"] = file_bytes
        st.session_state["pending_file_name"] = uploaded_file.name

check = st.session_state.get("pending_check")
if check is not None:
    render_section_header("Kết quả kiểm tra file")
    if check.is_valid:
        st.success("File hợp lệ và có thể dùng làm dữ liệu hiện tại.")
    else:
        st.error("File có lỗi. Không thể dùng làm dữ liệu hiện tại cho đến khi sửa xong.")
        for error in check.errors:
            st.write(f"- {error}")

    sheet_columns = st.columns(2, gap="medium")
    with sheet_columns[0]:
        if check.gop_vat_summary:
            summary = check.gop_vat_summary
            with st.container(border=True):
                st.markdown("**Sheet `Gộp VAT`**")
                st.write(f"Số dòng: **{summary.total_data_rows:,}**")
                st.write(f"Mã VAT trống: **{summary.blank_ma_vat_count:,}**")
                st.write(f"Tồn không hợp lệ: **{summary.invalid_ton_count:,}**")
                st.write(f"Tồn không dương: **{summary.zero_or_negative_ton_count:,}**")
    with sheet_columns[1]:
        if check.khop_ma_summary:
            summary = check.khop_ma_summary
            with st.container(border=True):
                st.markdown("**Sheet `Khớp mã`**")
                st.write(f"Số dòng: **{summary.total_data_rows:,}**")
                st.write(f"Mã SP trống: **{summary.blank_ma_count:,}**")
                st.write(f"Mã VAT trống: **{summary.blank_ma_vat_count:,}**")
                st.write(f"Mã SP trỏ nhiều Mã VAT: **{summary.duplicate_ma_sp_multi_vat_count:,}**")

    if check.warnings:
        with st.expander(f"Cảnh báo dữ liệu ({len(check.warnings)})"):
            warn_df = pd.DataFrame(
                [
                    {"Dòng": warning.row_index, "Loại": warning.warning_type, "Chi tiết": warning.detail}
                    for warning in check.warnings
                ]
            )
            st.dataframe(
                warn_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Dòng": st.column_config.NumberColumn(width="small", format="%d"),
                    "Loại": st.column_config.TextColumn(width="medium"),
                    "Chi tiết": st.column_config.TextColumn(width="large"),
                },
            )

    if not check.is_valid:
        error_report = pd.DataFrame({"Lỗi": check.errors})
        buffer = io.StringIO()
        error_report.to_csv(buffer, index=False)
        st.download_button(
            "⬇️ Tải báo cáo lỗi (CSV)",
            data=buffer.getvalue(),
            file_name="bao_cao_loi_file.csv",
        )
    else:
        st.info("Xác nhận bên dưới sẽ tạo một phiên bản mới; file hiện tại chỉ đổi sau khi lưu thành công.")
        if st.button("✅ Dùng làm dữ liệu hiện tại", type="primary"):
            version_id = confirm_new_current_file(
                st.session_state["pending_file_bytes"],
                st.session_state["pending_file_name"],
                check,
                uploaded_by=user.email,
            )
            st.success(f"Đã cập nhật dữ liệu hiện tại (phiên bản {version_id}).")
            for key in ("pending_check", "pending_file_bytes", "pending_file_name"):
                st.session_state.pop(key, None)
            st.rerun()

render_section_header(
    "3. Lịch sử phiên bản",
    "Bảng chỉ hiển thị thông tin cần thiết. ID và SHA-256 nằm trong phần chi tiết.",
)
versions = storage.list_versions()
if not versions:
    render_empty_state("Chưa có lịch sử phiên bản", "Phiên bản đầu tiên sẽ xuất hiện sau khi upload thành công.")
else:
    current_id = storage.get_current_version_id()
    version_df = pd.DataFrame(
        [
            {
                "Hiện tại": "✓" if version.version_id == current_id else "",
                "Tên file": version.original_file_name,
                "Thời điểm upload": version.uploaded_at,
                "Người upload": version.uploaded_by or "—",
                "Trạng thái": "Hợp lệ" if version.check_status == "valid" else "Không hợp lệ",
                "Dòng Gộp VAT": version.gop_vat_row_count,
                "Dòng Khớp mã": version.khop_ma_row_count,
            }
            for version in versions
        ]
    )
    st.dataframe(
        version_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Hiện tại": st.column_config.TextColumn(width="small"),
            "Tên file": st.column_config.TextColumn(width="large"),
            "Thời điểm upload": st.column_config.DatetimeColumn(format="DD/MM/YYYY HH:mm"),
            "Người upload": st.column_config.TextColumn(width="medium"),
            "Trạng thái": st.column_config.TextColumn(width="small"),
            "Dòng Gộp VAT": st.column_config.NumberColumn(format="%d"),
            "Dòng Khớp mã": st.column_config.NumberColumn(format="%d"),
        },
    )

    with st.expander("Chi tiết kỹ thuật các phiên bản"):
        for version in versions:
            marker = " · Đang dùng" if version.version_id == current_id else ""
            st.markdown(f"**{version.original_file_name}{marker}**")
            st.code(f"ID: {version.version_id}\nSHA-256: {version.sha256}", language=None)

    restore_options = [version.version_id for version in versions if version.version_id != current_id]
    if restore_options:
        version_by_id = {version.version_id: version for version in versions}
        with st.container(border=True):
            st.markdown("**Khôi phục phiên bản**")
            st.caption("Thao tác này đổi con trỏ dữ liệu hiện tại nhưng không xóa các phiên bản khác.")
            selected = st.selectbox(
                "Chọn phiên bản để khôi phục",
                restore_options,
                format_func=lambda version_id: (
                    f"{version_by_id[version_id].original_file_name} · "
                    f"{version_by_id[version_id].uploaded_at}"
                ),
            )
            if st.button("↩️ Khôi phục phiên bản này"):
                storage.set_current_version_id(selected)
                st.session_state.pop("current_workbook_cache", None)
                st.session_state.pop("current_workbook_cache_id", None)
                st.success(f"Đã khôi phục phiên bản {selected} thành dữ liệu hiện tại.")
                st.rerun()
