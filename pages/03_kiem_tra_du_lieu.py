"""Trang 3: Kiểm tra dữ liệu — thống kê lỗi nguồn, danh sách cần kiểm tra tên
thủ công (mục 15.3, 16 CLAUDE.md). Trang này KHÔNG gọi AI."""

from __future__ import annotations

import io

import pandas as pd
import streamlit as st

from src.review import build_manual_review_report
from src.session import get_config, get_current_version_metadata, get_current_workbook

st.set_page_config(page_title="Kiểm tra dữ liệu", page_icon="🔎", layout="wide")
st.title("Kiểm tra dữ liệu")
st.caption("Trang này chỉ tính toán deterministic, không gọi AI.")

config = get_config()
workbook = get_current_workbook()
meta = get_current_version_metadata()

if workbook is None or not workbook.is_valid:
    st.error("Chưa có dữ liệu hiện tại hợp lệ.")
    st.stop()

st.subheader("1. Thống kê lỗi/cảnh báo dữ liệu nguồn")
col1, col2 = st.columns(2)
with col1:
    if workbook.gop_vat_summary:
        s = workbook.gop_vat_summary
        st.metric("Số dòng Gộp VAT", f"{s.total_data_rows:,}")
        st.metric("Mã VAT trống", f"{s.blank_ma_vat_count:,}")
        st.metric("Tồn không hợp lệ (không phải số)", f"{s.invalid_ton_count:,}")
        st.metric("Tồn <= 0 (sẽ bị loại khỏi ứng viên)", f"{s.zero_or_negative_ton_count:,}")
with col2:
    if workbook.khop_ma_summary:
        s = workbook.khop_ma_summary
        st.metric("Số dòng Khớp mã", f"{s.total_data_rows:,}")
        st.metric("Mã SP trống", f"{s.blank_ma_count:,}")
        st.metric("Mã SP trỏ nhiều Mã VAT", f"{s.duplicate_ma_sp_multi_vat_count:,}")

if workbook.warnings:
    st.subheader("2. Danh sách dòng có tồn không hợp lệ")
    warn_df = pd.DataFrame(
        [{"Dòng": w.row_index, "Loại": w.warning_type, "Chi tiết": w.detail} for w in workbook.warnings]
    )
    st.dataframe(warn_df, use_container_width=True)

st.subheader("3. Danh sách cần kiểm tra tên thủ công (xuất ra để đưa AI bên ngoài)")
if st.button("⚙️ Tính bảng kiểm tra tên"):
    with st.spinner("Đang tính điểm khớp tên deterministic..."):
        report = build_manual_review_report(workbook.mapping_rows, workbook.stock_rows, config)
    st.session_state["review_report"] = report

report = st.session_state.get("review_report")
if report is not None:
    report_df = pd.DataFrame(
        [
            {
                "Mã SP": r.ma_sp,
                "Tên SP": r.ten_sp,
                "Mã VAT": r.ma_vat,
                "Tên VAT": r.ten_vat,
                "Tên kế toán": r.ten_ke_toan,
                "Điểm khớp": r.diem_khop,
                "Lý do bị đánh dấu": r.ly_do_danh_dau,
                "Trạng thái": r.trang_thai,
            }
            for r in report
        ]
    )
    need_review = report_df[report_df["Trạng thái"] == "can_kiem_tra"]
    st.write(f"Tổng: {len(report_df)} dòng, cần kiểm tra: {len(need_review)} dòng.")
    st.dataframe(report_df, use_container_width=True)

    buf = io.StringIO()
    report_df.to_csv(buf, index=False)
    st.download_button(
        "⬇️ Tải bảng kiểm tra tên (CSV) — để đưa AI kiểm tra thủ công bên ngoài",
        data=buf.getvalue(),
        file_name="bang_kiem_tra_ten.csv",
    )
