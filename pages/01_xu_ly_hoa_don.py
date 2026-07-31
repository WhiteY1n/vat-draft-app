"""Trang xử lý hóa đơn — dán dữ liệu, kiểm tra, tạo kết quả và xuất file."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.auth import get_current_user
from src.result_builder import CHECK_RESULT_COLUMNS
from src.session import get_config, get_current_version_metadata, get_current_workbook
from src.source_lookup import SourceLookupInput, build_grouped_display_rows, lookup_sources
from ui import (
    apply_global_styles,
    render_action_bar,
    render_data_version_banner,
    render_feature_top_bar,
    render_metric_card,
    render_section_header,
)

st.set_page_config(
    page_title="Xử lý hóa đơn", page_icon="🧾", layout="wide", initial_sidebar_state="collapsed"
)
apply_global_styles()

config = get_config()
user = get_current_user(config, session_email=st.session_state.get("user_email"))
meta = get_current_version_metadata()
workbook = get_current_workbook()

render_feature_top_bar(active="xu_ly_hoa_don", meta=meta, config=config, user=user)

if workbook is None or not workbook.is_valid:
    render_data_version_banner(meta, valid=False)
    st.error(
        "Chưa có dữ liệu hiện tại hợp lệ. Vào trang Quản lý dữ liệu để upload và xác nhận "
        "file Excel trước."
    )
    st.stop()

if "invoice_df" not in st.session_state:
    st.session_state["invoice_df"] = pd.DataFrame(
        columns=["Mã SP", "Tên SP", "SL", "Giá bán"]
    )

render_section_header(
    "1. Nhập dữ liệu",
    "Sao chép 4 cột từ Excel theo thứ tự Mã SP, Tên SP, SL, Giá bán rồi dán vào vùng bên dưới.",
)
with st.container(border=True):
    pasted_text = st.text_area("Khu vực dán dữ liệu", height=150, key="paste_area")

    col_read, col_clear, _ = render_action_bar([1.7, 1, 3])
    with col_read:
        read_and_check_clicked = st.button("📥 Đọc và kiểm tra dữ liệu", type="primary")
    with col_clear:
        clear_clicked = st.button("🗑️ Xóa toàn bộ", type="secondary")

if clear_clicked:
    st.session_state["invoice_df"] = pd.DataFrame(columns=["Mã SP", "Tên SP", "SL", "Giá bán"])
    st.session_state.pop("check_result", None)
    st.rerun()

result = st.session_state.get("check_result")

if read_and_check_clicked:
    result = None
    st.session_state.pop("check_result", None)

if read_and_check_clicked and not pasted_text.strip():
    st.warning("Hãy dán dữ liệu hóa đơn trước khi kiểm tra.")

if read_and_check_clicked and pasted_text.strip():
    lines = [ln for ln in pasted_text.strip("\n").split("\n") if ln.strip() != ""]
    parsed_rows = []
    for ln in lines:
        cols = ln.split("\t")
        cols = (cols + ["", "", "", ""])[:4]
        # bỏ qua dòng header nếu người dùng lỡ dán kèm header
        if cols[0].strip().lower() in ("mã sp", "ma sp") and cols[2].strip().lower() in ("sl",):
            continue
        parsed_rows.append(cols)

    new_df = pd.DataFrame(parsed_rows, columns=["Mã SP", "Tên SP", "SL", "Giá bán"])
    st.session_state["invoice_df"] = new_df

    df = st.session_state["invoice_df"].reset_index(drop=True)
    lookup_rows: list[SourceLookupInput] = []
    for idx, row in df.iterrows():
        ma_sp = row.get("Mã SP", "")
        ten_sp = row.get("Tên SP", "")
        sl = row.get("SL", "")
        gia_ban = row.get("Giá bán", "")
        if str(ma_sp).strip() == "" and str(ten_sp).strip() == "":
            continue  # bỏ qua dòng trống hoàn toàn
        lookup_rows.append(
            SourceLookupInput(
                order_index=idx + 1,
                ma_sp=ma_sp,
                ten_sp=ten_sp,
                sl=sl,
                gia_ban=gia_ban,
            )
        )

    if not lookup_rows:
        st.warning("Chưa có dòng hóa đơn nào để kiểm tra.")
        st.session_state.pop("check_result", None)
    else:
        result = lookup_sources(
            lookup_rows,
            workbook.mapping_rows,
            workbook.stock_rows,
            config=config,
        )
        st.session_state["check_result"] = result
        st.session_state["last_input_count"] = len(lookup_rows)

if result is not None:
    render_section_header(
        "Kết quả xử lý",
        "Mỗi dòng được tra cứu độc lập; tồn còn nháp chỉ dùng để kiểm tra và không bị trừ mô phỏng.",
    )

    input_count = st.session_state.get("last_input_count", 0)
    output_count = len(result.lines)
    issue_count = len(result.issues)
    summary_columns = st.columns(3, gap="small")
    with summary_columns[0]:
        render_metric_card("Tổng dòng đã kiểm tra", f"{input_count:,}")
    with summary_columns[1]:
        render_metric_card("Dòng đã trả kết quả", f"{output_count:,}")
    with summary_columns[2]:
        render_metric_card("Dòng cần kiểm tra", f"{issue_count:,}")

    if result.issues:
        st.warning(
            f"Đã trả kết quả cho {output_count}/{input_count} dòng; "
            f"còn {issue_count} dòng cần kiểm tra thông tin mã hoặc mapping."
        )
        issue_df = pd.DataFrame(
            [
                {
                    "Dòng nhập": issue.query_order,
                    "Mã SP": issue.ma_sp,
                    "Tên SP": issue.ten_sp,
                    "Loại kiểm tra": issue.issue_type,
                    "Nội dung": issue.detail,
                }
                for issue in result.issues
            ]
        )
        st.dataframe(
            issue_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Dòng nhập": st.column_config.NumberColumn(width="small", format="%d"),
                "Mã SP": st.column_config.TextColumn(width="medium"),
                "Tên SP": st.column_config.TextColumn(width="large"),
                "Loại kiểm tra": st.column_config.TextColumn(width="medium"),
                "Nội dung": st.column_config.TextColumn(width="large"),
            },
        )
    else:
        st.success(
            f"Đã trả đủ {output_count}/{input_count} dòng. "
            "Các dòng tồn bằng 0 vẫn được giữ trong bảng để người dùng kiểm tra."
        )

    if result.lines:
        render_section_header(
            "Kết quả kiểm tra",
            "Hiển thị đầy đủ thông tin sản phẩm, VAT, kế toán, nguồn và tồn còn nháp theo mẫu nghiệp vụ.",
        )
        result_df = pd.DataFrame(build_grouped_display_rows(result.lines)).rename(
            columns={
                "GIÁ NHÁP (Giá bán/(1+%VAT))": "GIÁ NHÁP\n(Giá bán/(1+%VAT))"
            }
        )
        result_df = result_df[CHECK_RESULT_COLUMNS]
        with st.container(key="result-highlight"):
            st.dataframe(
                result_df,
                use_container_width=True,
                height=440,
                hide_index=True,
                column_config={
                    "MÃ SP": st.column_config.TextColumn(width="medium"),
                    "TÊN SP": st.column_config.TextColumn(width="large"),
                    "SL": st.column_config.NumberColumn(width="small", format="%.0f"),
                    "Giá bán": st.column_config.NumberColumn(width="small", format="%.0f"),
                    "Mã VAT": st.column_config.TextColumn(width="medium"),
                    "TÊN VAT": st.column_config.TextColumn(width="large"),
                    "TÊN KẾ TOÁN": st.column_config.TextColumn(width="large"),
                    "ĐVT": st.column_config.TextColumn(width="small"),
                    "NGUỒN": st.column_config.TextColumn(width="medium"),
                    "TỒN CÒN NHÁP": st.column_config.NumberColumn(width="medium", format="%.0f"),
                    "%VAT": st.column_config.NumberColumn(width="small", format="%.0f%%"),
                    "GIÁ NHÁP\n(Giá bán/(1+%VAT))": st.column_config.NumberColumn(
                        width="medium", format="%.0f"
                    ),
                },
            )
