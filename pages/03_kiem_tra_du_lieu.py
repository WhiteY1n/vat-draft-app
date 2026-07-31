"""Trang kiểm tra dữ liệu nguồn và báo cáo rà soát tên thủ công."""

from __future__ import annotations

import io

import pandas as pd
import streamlit as st

from src.review import build_manual_review_report
from src.session import get_config, get_current_version_metadata, get_current_workbook
from ui import (
    apply_global_styles,
    render_admin_top_bar,
    render_data_version_banner,
    render_metric_card,
    render_section_header,
)

st.set_page_config(
    page_title="Kiểm tra dữ liệu", page_icon="✅", layout="wide", initial_sidebar_state="collapsed"
)
apply_global_styles()

meta = get_current_version_metadata()
render_admin_top_bar(
    title="Kiểm tra dữ liệu",
    icon="✅",
    description="Theo dõi lỗi, cảnh báo và các trường hợp cần rà soát tên. Trang này không gọi AI.",
    meta=meta,
)

config = get_config()
workbook = get_current_workbook()

if workbook is None:
    render_data_version_banner(meta, valid=False)
    st.error("Chưa có dữ liệu hiện tại.")
    st.stop()

if not workbook.is_valid:
    render_data_version_banner(meta, valid=False)
    st.error("Dữ liệu hiện tại không hợp lệ nên chưa thể lập báo cáo kiểm tra.")
    if workbook.errors:
        with st.expander("Xem lỗi nghiêm trọng", expanded=True):
            for error in workbook.errors:
                st.write(f"- {error}")
    st.stop()

render_data_version_banner(meta, valid=True)

gop_summary = workbook.gop_vat_summary
khop_summary = workbook.khop_ma_summary

critical_count = len(workbook.errors)
needs_action_count = 0
review_count = 0
if gop_summary:
    needs_action_count += gop_summary.blank_ma_vat_count + gop_summary.invalid_ton_count
    review_count += gop_summary.zero_or_negative_ton_count
if khop_summary:
    needs_action_count += (
        khop_summary.blank_ma_count
        + khop_summary.blank_ma_vat_count
        + khop_summary.duplicate_ma_sp_multi_vat_count
    )

render_section_header(
    "Phân loại chỉ báo",
    "Các số liệu bên dưới chỉ tổng hợp những trường đã được workbook hiện tại tính sẵn.",
)
severity_columns = st.columns(3, gap="small")
with severity_columns[0]:
    render_metric_card("Nghiêm trọng", f"{critical_count:,}", help_text="Lỗi làm workbook không hợp lệ.")
with severity_columns[1]:
    render_metric_card("Cần xử lý", f"{needs_action_count:,}", help_text="Mã trống, tồn sai kiểu hoặc mapping không duy nhất.")
with severity_columns[2]:
    render_metric_card("Cần rà soát", f"{review_count:,}", help_text="Dòng tồn không dương bị loại khỏi ứng viên.")

render_section_header("Chi tiết theo sheet")
sheet_columns = st.columns(2, gap="medium")
with sheet_columns[0]:
    with st.container(border=True):
        st.markdown("**Gộp VAT**")
        if gop_summary:
            st.metric("Tổng số dòng", f"{gop_summary.total_data_rows:,}")
            detail_columns = st.columns(3)
            detail_columns[0].metric("Mã VAT trống", f"{gop_summary.blank_ma_vat_count:,}")
            detail_columns[1].metric("Tồn sai kiểu", f"{gop_summary.invalid_ton_count:,}")
            detail_columns[2].metric("Tồn ≤ 0", f"{gop_summary.zero_or_negative_ton_count:,}")
with sheet_columns[1]:
    with st.container(border=True):
        st.markdown("**Khớp mã**")
        if khop_summary:
            st.metric("Tổng số dòng", f"{khop_summary.total_data_rows:,}")
            detail_columns = st.columns(3)
            detail_columns[0].metric("Mã SP trống", f"{khop_summary.blank_ma_count:,}")
            detail_columns[1].metric("Mã VAT trống", f"{khop_summary.blank_ma_vat_count:,}")
            detail_columns[2].metric("Nhiều Mã VAT", f"{khop_summary.duplicate_ma_sp_multi_vat_count:,}")

if workbook.warnings:
    render_section_header("Cảnh báo dữ liệu nguồn")
    warning_df = pd.DataFrame(
        [
            {"Dòng": warning.row_index, "Loại": warning.warning_type, "Chi tiết": warning.detail}
            for warning in workbook.warnings
        ]
    )
    warning_types = sorted(warning_df["Loại"].dropna().unique().tolist())
    selected_warning_type = st.selectbox(
        "Lọc loại cảnh báo",
        ["Tất cả", *warning_types],
        key="warning_filter",
    )
    filtered_warning_df = warning_df
    if selected_warning_type != "Tất cả":
        filtered_warning_df = warning_df[warning_df["Loại"] == selected_warning_type]
    st.dataframe(
        filtered_warning_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Dòng": st.column_config.NumberColumn(width="small", format="%d"),
            "Loại": st.column_config.TextColumn(width="medium"),
            "Chi tiết": st.column_config.TextColumn(width="large"),
        },
    )
    with st.expander("Xem đầy đủ nội dung cảnh báo"):
        for warning in workbook.warnings:
            st.write(f"**Dòng {warning.row_index} · {warning.warning_type}**")
            st.write(warning.detail)

render_section_header(
    "Rà soát tên sản phẩm",
    "Tính điểm deterministic theo cấu hình hiện tại và xuất danh sách để kiểm tra thủ công bên ngoài app.",
)
if st.button("⚙️ Tính bảng kiểm tra tên"):
    with st.spinner("Đang tính điểm khớp tên deterministic..."):
        report = build_manual_review_report(workbook.mapping_rows, workbook.stock_rows, config)
    st.session_state["review_report"] = report

report = st.session_state.get("review_report")
if report is not None:
    report_df = pd.DataFrame(
        [
            {
                "Mã SP": row.ma_sp,
                "Tên SP": row.ten_sp,
                "Mã VAT": row.ma_vat,
                "Tên VAT": row.ten_vat,
                "Tên kế toán": row.ten_ke_toan,
                "Điểm khớp": row.diem_khop,
                "Lý do bị đánh dấu": row.ly_do_danh_dau,
                "Trạng thái": row.trang_thai,
            }
            for row in report
        ]
    )
    need_review = report_df[report_df["Trạng thái"] == "can_kiem_tra"]

    report_columns = st.columns(2, gap="small")
    with report_columns[0]:
        render_metric_card("Tổng dòng đã tính", f"{len(report_df):,}")
    with report_columns[1]:
        render_metric_card("Cần kiểm tra tên", f"{len(need_review):,}")

    status_filter = st.selectbox(
        "Lọc trạng thái",
        ["Tất cả", "Cần kiểm tra", "Ổn"],
        key="review_status_filter",
    )
    filtered_report_df = report_df
    if status_filter == "Cần kiểm tra":
        filtered_report_df = report_df[report_df["Trạng thái"] == "can_kiem_tra"]
    elif status_filter == "Ổn":
        filtered_report_df = report_df[report_df["Trạng thái"] == "ok"]

    display_report_df = filtered_report_df.copy()
    display_report_df["Trạng thái"] = display_report_df["Trạng thái"].map(
        {"can_kiem_tra": "Cần kiểm tra", "ok": "Ổn"}
    )
    st.dataframe(
        display_report_df,
        use_container_width=True,
        hide_index=True,
        height=480,
        column_config={
            "Mã SP": st.column_config.TextColumn(width="medium"),
            "Tên SP": st.column_config.TextColumn(width="large"),
            "Mã VAT": st.column_config.TextColumn(width="medium"),
            "Tên VAT": st.column_config.TextColumn(width="large"),
            "Tên kế toán": st.column_config.TextColumn(width="large"),
            "Điểm khớp": st.column_config.NumberColumn(width="small", format="%.1f"),
            "Lý do bị đánh dấu": st.column_config.TextColumn(width="large"),
            "Trạng thái": st.column_config.TextColumn(width="small"),
        },
    )

    with st.expander("Xem đầy đủ lý do cần kiểm tra"):
        if need_review.empty:
            st.caption("Không có dòng nào cần kiểm tra tên.")
        else:
            for _, row in need_review.iterrows():
                st.write(f"**{row['Mã SP']} · {row['Tên SP']}**")
                st.write(row["Lý do bị đánh dấu"] or "Không có mô tả bổ sung.")

    buffer = io.StringIO()
    report_df.to_csv(buffer, index=False)
    st.download_button(
        "⬇️ Tải bảng kiểm tra tên (CSV) — để kiểm tra thủ công bên ngoài",
        data=buffer.getvalue(),
        file_name="bang_kiem_tra_ten.csv",
    )
