"""Trang tra cứu nguồn độc lập cho yêu cầu 2-4."""

from __future__ import annotations

import io

import pandas as pd
import streamlit as st

from src.session import get_current_version_metadata, get_current_workbook
from src.source_lookup import SourceLookupInput, build_grouped_display_rows, lookup_sources

st.set_page_config(page_title="Tra cứu nguồn", page_icon="🔎", layout="wide")
st.title("🔎 Tra cứu nguồn")
st.caption(
    "Tra từ Mã SP hoặc Tên SP để xem tất cả nguồn còn tồn nháp dương. "
    "Kết quả của từng sản phẩm được xếp từ tồn thấp nhất đến cao nhất."
)

workbook = get_current_workbook()
meta = get_current_version_metadata()
if workbook is None or not workbook.is_valid:
    st.error("Chưa có dữ liệu hiện tại hợp lệ. Hãy upload và xác nhận file Excel ở trang Quản lý dữ liệu.")
    st.stop()

st.info(
    f"Đang dùng dữ liệu: **{meta.original_file_name}** "
    f"({meta.gop_vat_row_count:,} dòng Gộp VAT, {meta.khop_ma_row_count:,} dòng Khớp mã)."
)

if "source_lookup_df" not in st.session_state:
    st.session_state["source_lookup_df"] = pd.DataFrame(
        columns=["Mã SP", "Tên SP", "SL", "Giá bán"]
    )

st.subheader("1. Nhập danh sách cần tra")
st.caption(
    "Có thể dán nhiều dòng từ Excel (Mã SP, Tên SP, SL, Giá bán) hoặc nhập trực tiếp. "
    "Chỉ cần có Mã SP hoặc Tên SP; SL và Giá bán là tùy chọn."
)

pasted = st.text_area(
    "Dán dữ liệu (các cột cách nhau bằng phím Tab)",
    height=120,
    key="source_lookup_paste_area",
)
col_read, col_clear, _ = st.columns([1, 1, 3])
with col_read:
    read_clicked = st.button("📥 Đọc dữ liệu", type="primary")
with col_clear:
    clear_clicked = st.button("🗑️ Xóa toàn bộ")

if clear_clicked:
    st.session_state["source_lookup_df"] = pd.DataFrame(
        columns=["Mã SP", "Tên SP", "SL", "Giá bán"]
    )
    st.session_state.pop("source_lookup_result", None)
    st.rerun()

if read_clicked:
    rows = []
    for line in pasted.splitlines():
        if not line.strip():
            continue
        cols = (line.split("\t") + ["", "", "", ""])[:4]
        if cols[0].strip().casefold() in {"mã sp", "ma sp", "mã kiot", "ma kiot"}:
            continue
        rows.append(cols)
    if rows:
        st.session_state["source_lookup_df"] = pd.DataFrame(
            rows, columns=["Mã SP", "Tên SP", "SL", "Giá bán"]
        )
        st.session_state.pop("source_lookup_result", None)
        st.rerun()
    else:
        st.warning("Không đọc được dòng dữ liệu nào từ vùng dán.")

edited_df = st.data_editor(
    st.session_state["source_lookup_df"],
    num_rows="dynamic",
    use_container_width=True,
    hide_index=True,
    key="source_lookup_editor",
)
st.session_state["source_lookup_df"] = edited_df

lookup_clicked = st.button("🔎 Tra cứu nguồn", type="primary")
if lookup_clicked:
    queries = []
    for index, row in edited_df.reset_index(drop=True).iterrows():
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
    if not queries:
        st.warning("Hãy nhập ít nhất một Mã SP hoặc Tên SP.")
        st.session_state.pop("source_lookup_result", None)
    else:
        st.session_state["source_lookup_result"] = lookup_sources(
            queries, workbook.mapping_rows, workbook.stock_rows
        )

result = st.session_state.get("source_lookup_result")
if result is not None:
    if result.issues:
        st.subheader("Các dòng cần kiểm tra")
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
        st.dataframe(issue_df, use_container_width=True, hide_index=True)

    if result.lines:
        st.subheader("2. Kết quả tra cứu nguồn")
        result_df = pd.DataFrame(build_grouped_display_rows(result.lines))
        product_count = len({line.query_order for line in result.lines})
        st.success(
            f"Tìm thấy {len(result.lines)} nguồn còn tồn dương cho "
            f"{product_count} sản phẩm."
        )
        st.dataframe(
            result_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Tồn nháp được": st.column_config.NumberColumn(format="%.2f"),
                "%VAT": st.column_config.NumberColumn(format="%.1f%%"),
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
        st.info("Không có nguồn còn tồn nháp dương để hiển thị.")
