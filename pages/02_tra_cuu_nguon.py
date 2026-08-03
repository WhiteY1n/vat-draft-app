"""Trang tra cứu nguồn độc lập theo Mã SP hoặc Tên SP."""

from __future__ import annotations

import io

import pandas as pd
import streamlit as st

from src.auth import get_current_user
from src.session import get_config, get_current_version_metadata, get_current_workbook
from src.source_lookup import (
    SourceLookupInput,
    build_all_sources_display_rows,
    lookup_all_sources,
)
from ui import (
    apply_global_styles,
    render_action_bar,
    render_data_version_banner,
    render_feature_top_bar,
    render_section_header,
)

st.set_page_config(
    page_title="Tra cứu nguồn", page_icon="🔎", layout="wide", initial_sidebar_state="collapsed"
)
apply_global_styles()

config = get_config()
user = get_current_user(config, session_email=st.session_state.get("user_email"))
meta = get_current_version_metadata()
workbook = get_current_workbook()

render_feature_top_bar(active="tra_cuu_nguon", meta=meta, config=config, user=user)

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
            result = lookup_all_sources(
                queries, workbook.mapping_rows, workbook.stock_rows, config=config
            )
            st.session_state["source_lookup_result"] = result
        else:
            st.warning("Hãy nhập ít nhất một Mã SP hoặc Tên SP.")
    else:
        st.warning("Không đọc được dòng dữ liệu nào từ vùng dán.")
        st.session_state.pop("source_lookup_result", None)

if result is not None:
    render_section_header(
        "Kết quả tra cứu nguồn",
        "Hiển thị mọi nguồn có trong file; nguồn còn tồn dương được xếp trước, sau đó đến nguồn hết/âm tồn.",
    )

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
        result_df = pd.DataFrame(build_all_sources_display_rows(result.lines)).fillna("")
        with st.container(key="result-highlight"):
            st.dataframe(
                result_df,
                width="stretch",
                height=440,
                hide_index=True,
                column_config={
                    "Mã kiot": st.column_config.TextColumn(width=74),
                    "Tên kiot": st.column_config.TextColumn(width=190),
                    "SL": st.column_config.NumberColumn(width=48, format="%.0f"),
                    "Giá bán": st.column_config.NumberColumn(width=64, format="%.0f"),
                    "Mã VAT": st.column_config.TextColumn(width=72),
                    "Tên VAT": st.column_config.TextColumn(width=185),
                    "Mã kế toán": st.column_config.TextColumn(width=170),
                    "ĐVT": st.column_config.TextColumn(width=48),
                    "Nguồn": st.column_config.TextColumn(width=62),
                    "Tồn nháp được": st.column_config.NumberColumn(width=72, format="%.0f"),
                    "%VAT": st.column_config.NumberColumn(width=48, format="%.0f%%"),
                },
            )

        csv_buffer = io.StringIO()
        result_df.to_csv(csv_buffer, index=False, encoding="utf-8-sig")
        st.download_button(
            "⬇️ Tải kết quả CSV",
            data=csv_buffer.getvalue().encode("utf-8-sig"),
            file_name="tra_cuu_nguon.csv",
            mime="text/csv",
        )
    elif not result.issues:
        st.info("Không có nguồn phù hợp để hiển thị.")
