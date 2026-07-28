"""Trang 2: Quản lý dữ liệu — chỉ dành cho Admin (mục 5, 6, 15 CLAUDE.md)."""

from __future__ import annotations

import io
import os
import tempfile

import pandas as pd
import streamlit as st

from src.auth import Role, get_current_user
from src.excel_reader import read_and_validate_workbook
from src.session import confirm_new_current_file, get_config, get_storage

st.set_page_config(page_title="Quản lý dữ liệu", page_icon="🗂️", layout="wide")
st.title("Quản lý dữ liệu")

config = get_config()
user = get_current_user(config, session_email=st.session_state.get("user_email"))

if user.role != Role.ADMIN:
    st.error("Trang này chỉ dành cho Admin.")
    st.stop()

storage = get_storage()

st.subheader("1. Upload file Excel mới")
uploaded_file = st.file_uploader("Kéo thả hoặc chọn file .xlsx", type=["xlsx"])

if uploaded_file is not None:
    file_bytes = uploaded_file.getvalue()
    st.write(f"**Tên file:** {uploaded_file.name}")
    st.write(f"**Dung lượng:** {len(file_bytes):,} bytes")

    tmp_path = os.path.join(tempfile.gettempdir(), f"upload_check_{uploaded_file.name}")
    with open(tmp_path, "wb") as f:
        f.write(file_bytes)

    check = read_and_validate_workbook(tmp_path, file_name=uploaded_file.name)
    st.session_state["pending_check"] = check
    st.session_state["pending_file_bytes"] = file_bytes
    st.session_state["pending_file_name"] = uploaded_file.name

check = st.session_state.get("pending_check")
if check is not None:
    st.subheader("2. Kiểm tra file")
    if check.is_valid:
        st.success("File hợp lệ.")
    else:
        st.error("File có lỗi. Không thể dùng làm dữ liệu hiện tại cho đến khi sửa xong.")
        for e in check.errors:
            st.write(f"- {e}")

    col1, col2 = st.columns(2)
    with col1:
        if check.gop_vat_summary:
            s = check.gop_vat_summary
            st.markdown("**Sheet `Gộp VAT`**")
            st.write(f"- Số dòng: {s.total_data_rows:,}")
            st.write(f"- Mã VAT trống: {s.blank_ma_vat_count:,}")
            st.write(f"- Tồn không hợp lệ: {s.invalid_ton_count:,}")
            st.write(f"- Tồn <= 0: {s.zero_or_negative_ton_count:,}")
    with col2:
        if check.khop_ma_summary:
            s = check.khop_ma_summary
            st.markdown("**Sheet `Khớp mã`**")
            st.write(f"- Số dòng: {s.total_data_rows:,}")
            st.write(f"- Mã SP trống: {s.blank_ma_count:,}")
            st.write(f"- Mã VAT trống: {s.blank_ma_vat_count:,}")
            st.write(f"- Mã SP trỏ nhiều Mã VAT: {s.duplicate_ma_sp_multi_vat_count:,}")

    if check.warnings:
        with st.expander(f"Cảnh báo dữ liệu ({len(check.warnings)})"):
            warn_df = pd.DataFrame(
                [{"Dòng": w.row_index, "Loại": w.warning_type, "Chi tiết": w.detail} for w in check.warnings]
            )
            st.dataframe(warn_df, use_container_width=True)

    if not check.is_valid:
        error_report = pd.DataFrame({"Lỗi": check.errors})
        buf = io.StringIO()
        error_report.to_csv(buf, index=False)
        st.download_button(
            "⬇️ Tải báo cáo lỗi (CSV)", data=buf.getvalue(), file_name="bao_cao_loi_file.csv"
        )
    else:
        st.subheader("3. Xác nhận dữ liệu")
        if st.button("✅ Dùng làm dữ liệu hiện tại", type="primary"):
            version_id = confirm_new_current_file(
                st.session_state["pending_file_bytes"],
                st.session_state["pending_file_name"],
                check,
                uploaded_by=user.email,
            )
            st.success(f"Đã cập nhật dữ liệu hiện tại (phiên bản {version_id}).")
            for k in ("pending_check", "pending_file_bytes", "pending_file_name"):
                st.session_state.pop(k, None)
            st.rerun()

st.divider()
st.subheader("4. Lịch sử phiên bản")
versions = storage.list_versions()
if not versions:
    st.info("Chưa có phiên bản nào.")
else:
    current_id = storage.get_current_version_id()
    ver_df = pd.DataFrame(
        [
            {
                "Hiện tại": "✅" if v.version_id == current_id else "",
                "ID phiên bản": v.version_id,
                "Tên file gốc": v.original_file_name,
                "Thời điểm upload": v.uploaded_at,
                "Người upload": v.uploaded_by or "-",
                "Trạng thái kiểm tra": v.check_status,
                "Số dòng Gộp VAT": v.gop_vat_row_count,
                "Số dòng Khớp mã": v.khop_ma_row_count,
            }
            for v in versions
        ]
    )
    st.dataframe(ver_df, use_container_width=True)

    restore_options = [v.version_id for v in versions if v.version_id != current_id]
    if restore_options:
        selected = st.selectbox("Chọn phiên bản để khôi phục", restore_options)
        if st.button("↩️ Khôi phục phiên bản này"):
            storage.set_current_version_id(selected)
            st.session_state.pop("current_workbook_cache", None)
            st.session_state.pop("current_workbook_cache_id", None)
            st.success(f"Đã khôi phục phiên bản {selected} thành dữ liệu hiện tại.")
            st.rerun()
