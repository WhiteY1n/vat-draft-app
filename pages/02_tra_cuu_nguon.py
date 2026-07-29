"""Trang tra cứu nguồn độc lập theo Mã SP hoặc Tên SP."""

from __future__ import annotations

import io

import pandas as pd
import streamlit as st

from src.session import get_current_version_metadata, get_current_workbook
from src.source_lookup import SourceLookupInput, build_grouped_display_rows, lookup_sources
from ui import (
    apply_global_styles,
    render_action_bar,
    render_compact_data_status,
    render_data_version_banner,
    render_page_header,
    render_section_header,
    render_sidebar,
)

st.set_page_config(page_title="Tra cứu nguồn", page_icon="🔎", layout="wide")
apply_global_styles()

meta = get_current_version_metadata()
render_sidebar(meta)

workbook = get_current_workbook()
header_column, status_column = st.columns([4, 1.35], gap="large")
with header_column:
    render_page_header("Tra cứu nguồn", "", icon="🔎")
with status_column:
    if workbook is not None and workbook.is_valid and meta is not None:
        render_compact_data_status(meta)

if workbook is None or not workbook.is_valid:
    render_data_version_banner(meta, valid=False)
    st.error("Chưa có dữ liệu hiện tại hợp lệ. Hãy upload và xác nhận file Excel ở trang Quản lý dữ liệu.")
    st.stop()

if "source_lookup_df" not in st.session_state:
    st.session_state["source_lookup_df"] = pd.DataFrame(
        columns=["Mã SP", "Tên SP", "SL", "Giá bán"]
    )

render_section_header(
    "1. Nhập danh sách cần tra",
    "Dán các cột cách nhau bằng phím Tab. Chỉ cần Mã SP hoặc Tên SP; SL và Giá bán là tùy chọn.",
)
with st.container(border=True):
    pasted = st.text_area(
        "Dán dữ liệu (các cột cách nhau bằng phím Tab)",
        height=120,
        key="source_lookup_paste_area",
    )
    col_read, col_clear, _ = render_action_bar([1, 1, 3])
    with col_read:
        lookup_clicked = st.button("🔎 Tra cứu nguồn", type="primary")
    with col_clear:
        clear_clicked = st.button("🗑️ Xóa toàn bộ", type="secondary")

if clear_clicked:
    st.session_state["source_lookup_df"] = pd.DataFrame(
        columns=["Mã SP", "Tên SP", "SL", "Giá bán"]
    )
    st.session_state.pop("source_lookup_result", None)
    st.rerun()

result = st.session_state.get("source_lookup_result")

if lookup_clicked:
    result = None
    st.session_state.pop("source_lookup_result", None)
    rows = []
    for line in pasted.splitlines():
        if not line.strip():
            continue
        cols = (line.split("\t") + ["", "", "", ""])[:4]
        if cols[0].strip().casefold() in {"mã sp", "ma sp", "mã kiot", "ma kiot"}:
            continue
        rows.append(cols)
    if rows:
        lookup_df = pd.DataFrame(
            rows, columns=["Mã SP", "Tên SP", "SL", "Giá bán"]
        )
        st.session_state["source_lookup_df"] = lookup_df

        queries = []
        for index, row in lookup_df.reset_index(drop=True).iterrows():
            ma_sp = row.get("Mã SP", "")
            ten_sp = row.get("Tên SP", "")
            if not str(ma_sp).strip() and not str(ten_sp).strip():
                continue
            queries.append(
                SourceLookupInput(
                    order_index=index + 1,
                    ma_sp=ma_sp,
                    ten_sp=ten_sp,
                    sl=row.get("SL", ""),
                    gia_ban=row.get("Giá bán", ""),
                )
            )

        if queries:
            result = lookup_sources(queries, workbook.mapping_rows, workbook.stock_rows)
            st.session_state["source_lookup_result"] = result
        else:
            st.warning("Hãy nhập ít nhất một Mã SP hoặc Tên SP.")
    else:
        st.warning("Không đọc được dòng dữ liệu nào từ vùng dán.")
        st.session_state.pop("source_lookup_result", None)

if result is not None:
    render_section_header("Kết quả tra cứu nguồn")

    if result.issues:
        render_section_header("Các dòng cần kiểm tra")
        issue_df = pd.DataFrame(
            [
                {
                    "Dòng nhập": issue.query_order,
                    "Mã SP": issue.ma_sp,
                    "Tên SP": issue.ten_sp,
                    "Nội dung": issue.detail,
                }
                for issue in result.issues
            ]
        )
        st.warning(f"Có {len(result.issues)} dòng chưa tra cứu được.")
        st.dataframe(
            issue_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Dòng nhập": st.column_config.NumberColumn(width="small", format="%d"),
                "Mã SP": st.column_config.TextColumn(width="medium"),
                "Tên SP": st.column_config.TextColumn(width="large"),
                "Nội dung": st.column_config.TextColumn(width="large"),
            },
        )

    if result.lines:
        lines_by_order = {}
        for line in result.lines:
            lines_by_order.setdefault(line.query_order, []).append(line)

        for query_order, product_lines in lines_by_order.items():
            first_line = product_lines[0]
            with st.container(border=True):
                st.markdown(
                    f"### {first_line.ma_sp or 'Không có mã'} · {first_line.ten_sp or 'Không có tên'}"
                )
                st.success(
                    f"Đề xuất: **{first_line.nguon}** · "
                    f"Tồn nháp được {first_line.ton_con_nhap:,.2f}"
                )
                product_df = pd.DataFrame(build_grouped_display_rows(product_lines))
                st.dataframe(
                    product_df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Mã kiot": st.column_config.TextColumn(width="medium"),
                        "Tên kiot": st.column_config.TextColumn(width="large"),
                        "Tên VAT": st.column_config.TextColumn(width="large"),
                        "Mã kế toán": st.column_config.TextColumn(width="large"),
                        "Nguồn": st.column_config.TextColumn(width="medium"),
                        "Tồn nháp được": st.column_config.NumberColumn(format="%.2f"),
                        "%VAT": st.column_config.NumberColumn(format="%.1f%%"),
                    },
                )

        result_df = pd.DataFrame(build_grouped_display_rows(result.lines))
        csv_buffer = io.StringIO()
        result_df.to_csv(csv_buffer, index=False, encoding="utf-8-sig")
        st.download_button(
            "⬇️ Tải kết quả CSV",
            data=csv_buffer.getvalue().encode("utf-8-sig"),
            file_name="tra_cuu_nguon.csv",
            mime="text/csv",
        )
    elif not result.issues:
        st.info("Không có nguồn còn tồn nháp dương để hiển thị.")
