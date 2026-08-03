"""Trang xử lý hóa đơn — dán dữ liệu, kiểm tra, tạo kết quả và xuất file."""

from __future__ import annotations

import io

import pandas as pd
import streamlit as st

from src.auth import get_current_user
from src.invoice_allocation import (
    InvoiceAllocationResult,
    allocate_invoice_sources,
    build_allocation_display_rows,
    build_shortage_display_rows,
    build_unavailable_display_rows,
)
from src.invoice_file_reader import parse_invoice_files
from src.result_builder import CHECK_RESULT_COLUMNS
from src.session import get_config, get_current_version_metadata, load_workbook_from_sheets
from src.source_lookup import SourceLookupInput
from ui import (
    apply_global_styles,
    render_action_bar,
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

# ---------------------------------------------------------------------------
# Auto-fetch khi vào trang lần đầu (hoặc sau khi server restart)
# ---------------------------------------------------------------------------
if st.session_state.get("current_workbook") is None:
    with st.spinner("⏳ Đang tải dữ liệu từ Google Sheets..."):
        try:
            load_workbook_from_sheets(config)
            st.rerun()
        except Exception as e:
            st.error(f"❌ Không thể tải dữ liệu: {e}")
            st.stop()

# ---------------------------------------------------------------------------
# Render top bar + xử lý nút Cập nhật thủ công
# ---------------------------------------------------------------------------
refresh_clicked = render_feature_top_bar(active="xu_ly_hoa_don", meta=meta, config=config, user=user)

if refresh_clicked:
    with st.spinner("⏳ Đang tải dữ liệu từ Google Sheets..."):
        try:
            load_workbook_from_sheets(config)
            st.rerun()
        except Exception as e:
            st.error(f"❌ Lỗi cập nhật: {e}")

# ---------------------------------------------------------------------------
# Lấy workbook hiện tại từ session_state
# ---------------------------------------------------------------------------
workbook = st.session_state.get("current_workbook")

if workbook is None or not workbook.is_valid:
    st.error("Dữ liệu không hợp lệ. Bấm **🔄** để thử tải lại.")
    if workbook is not None and workbook.errors:
        with st.expander("Chi tiết lỗi dữ liệu"):
            for err in workbook.errors:
                st.write(f"- {err}")
    st.stop()

# ---------------------------------------------------------------------------
# Nhập dữ liệu hóa đơn
# ---------------------------------------------------------------------------
if "invoice_df" not in st.session_state:
    st.session_state["invoice_df"] = pd.DataFrame(
        columns=["Mã SP", "Tên SP", "SL", "Giá bán"]
    )

render_section_header(
    "1. Nhập dữ liệu",
    "Dán 4 cột từ Excel theo thứ tự Mã SP, Tên SP, SL, Giá bán, hoặc tải trực tiếp file hóa đơn (.xlsx).",
)
with st.container(border=True):
    tab_paste, tab_file = st.tabs(["📋 Dán dữ liệu", "📁 Tải file hóa đơn"])

    with tab_paste:
        pasted_text = st.text_area("Khu vực dán dữ liệu", height=150, key="paste_area")

        col_read, col_clear, _ = render_action_bar([1.7, 1, 3])
        with col_read:
            read_and_check_clicked = st.button(
                "📥 Đọc và kiểm tra dữ liệu", type="primary", key="paste-read-btn"
            )
        with col_clear:
            clear_clicked = st.button("🗑️ Xóa toàn bộ", type="secondary", key="paste-clear-btn")

    with tab_file:
        st.caption(
            "Chọn một hoặc nhiều file 'Chi tiết hóa đơn' (.xlsx) xuất từ phần mềm bán hàng. "
            "Hệ thống tự nhận diện các cột Mã hàng, Tên hàng, Số lượng, Giá bán."
        )
        uploaded_invoice_files = st.file_uploader(
            "Tải file hóa đơn (.xlsx)",
            type=["xlsx"],
            accept_multiple_files=True,
            key="invoice_file_uploader",
        )
        file_read_clicked = st.button(
            "📥 Đọc từ file đã tải lên",
            type="primary",
            key="file-read-btn",
            disabled=not uploaded_invoice_files,
        )

if clear_clicked:
    st.session_state["invoice_df"] = pd.DataFrame(columns=["Mã SP", "Tên SP", "SL", "Giá bán"])
    st.session_state.pop("check_result", None)
    st.rerun()

result = st.session_state.get("check_result")
if result is not None and not isinstance(result, InvoiceAllocationResult):
    # Kết quả cũ còn sót lại từ phiên trước khi đổi sang phân bổ nguồn.
    result = None
    st.session_state.pop("check_result", None)

parsed_rows: list[list[str]] | None = None

if read_and_check_clicked:
    result = None
    st.session_state.pop("check_result", None)
    if not pasted_text.strip():
        st.warning("Hãy dán dữ liệu hóa đơn trước khi kiểm tra.")
    else:
        lines = [ln for ln in pasted_text.strip("\n").split("\n") if ln.strip() != ""]
        parsed_rows = []
        for ln in lines:
            cols = ln.split("\t")
            cols = (cols + ["", "", "", ""])[:4]
            # bỏ qua dòng header nếu người dùng lỡ dán kèm header
            if cols[0].strip().lower() in ("mã sp", "ma sp") and cols[2].strip().lower() in ("sl",):
                continue
            parsed_rows.append(cols)

if file_read_clicked:
    result = None
    st.session_state.pop("check_result", None)
    if not uploaded_invoice_files:
        st.warning("Hãy chọn ít nhất một file hóa đơn (.xlsx).")
    else:
        files = [(f.getvalue(), f.name) for f in uploaded_invoice_files]
        parsed_rows, parse_errors = parse_invoice_files(files)
        for err in parse_errors:
            st.warning(err)

if parsed_rows is not None:
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
        result = allocate_invoice_sources(
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
        "Mỗi sản phẩm được phân bổ độc lập theo tồn còn nháp; tồn không bị trừ mô phỏng "
        "giữa các dòng hóa đơn.",
    )

    input_count = st.session_state.get("last_input_count", 0)
    output_count = len({line.query_order for line in result.lines})
    shortage_count = len(result.shortages)
    unavailable_count = len(result.issues)
    summary_columns = st.columns(4, gap="small")
    with summary_columns[0]:
        render_metric_card("Tổng dòng đã kiểm tra", f"{input_count:,}")
    with summary_columns[1]:
        render_metric_card("Sản phẩm thỏa mãn", f"{output_count:,}")
    with summary_columns[2]:
        render_metric_card("Không đủ tồn", f"{shortage_count:,}")
    with summary_columns[3]:
        render_metric_card("Không tồn tại", f"{unavailable_count:,}")

    render_section_header(
        "Sản phẩm thỏa mãn",
        "Các sản phẩm tồn tại trong dữ liệu, đủ số lượng và có thể xuất. Mỗi nguồn được dùng hiển thị thành một dòng riêng.",
    )
    if result.lines:
        st.success(f"Có {output_count} sản phẩm thỏa mãn điều kiện và có thể xuất.")
        result_df = pd.DataFrame(build_allocation_display_rows(result.lines)).rename(
            columns={
                "GIÁ NHÁP (Giá bán/(1+%VAT))": "GIÁ NHÁP\n(Giá bán/(1+%VAT))"
            }
        )
        result_df = result_df[CHECK_RESULT_COLUMNS]
        with st.container(key="result-highlight"):
            st.dataframe(
                result_df,
                width="stretch",
                height=440,
                hide_index=True,
                column_config={
                    "MÃ SP": st.column_config.TextColumn(width=68),
                    "TÊN SP": st.column_config.TextColumn(width=175),
                    "SL": st.column_config.NumberColumn(width=48, format="%.0f"),
                    "Giá bán": st.column_config.NumberColumn(width=62, format="%.0f"),
                    "Mã VAT": st.column_config.TextColumn(width=70),
                    "TÊN VAT": st.column_config.TextColumn(width=175),
                    "TÊN KẾ TOÁN": st.column_config.TextColumn(width=165),
                    "ĐVT": st.column_config.TextColumn(width=46),
                    "NGUỒN": st.column_config.TextColumn(width=62),
                    "TỒN CÒN NHÁP": st.column_config.NumberColumn(width=68, format="%.0f"),
                    "%VAT": st.column_config.NumberColumn(width=46, format="%.0f%%"),
                    "GIÁ NHÁP\n(Giá bán/(1+%VAT))": st.column_config.NumberColumn(
                        width=130, format="%.0f"
                    ),
                },
            )

        csv_buffer = io.StringIO()
        result_df.to_csv(csv_buffer, index=False)
        st.download_button(
            "⬇️ Tải kết quả CSV",
            data=csv_buffer.getvalue().encode("utf-8-sig"),
            file_name="ket_qua_xu_ly_hoa_don.csv",
            mime="text/csv",
        )
    else:
        st.info("Không có sản phẩm nào thỏa mãn đầy đủ điều kiện để xuất.")

    render_section_header(
        "Sản phẩm không đủ tồn",
        "Các sản phẩm đã đối chiếu được mã nhưng tổng tồn còn nháp nhỏ hơn số lượng yêu cầu.",
    )
    if result.shortages:
        st.warning(f"Có {len(result.shortages)} sản phẩm không đủ số lượng tồn.")
        shortage_df = pd.DataFrame(build_shortage_display_rows(result.shortages))
        st.dataframe(
            shortage_df,
            width="stretch",
            hide_index=True,
            column_config={
                "Dòng nhập": st.column_config.NumberColumn(width="small", format="%d"),
                "MÃ SP": st.column_config.TextColumn(width=80),
                "TÊN SP": st.column_config.TextColumn(width="large"),
                "SL yêu cầu": st.column_config.NumberColumn(width=90, format="%.0f"),
                "Tổng tồn hiện có": st.column_config.NumberColumn(width=120, format="%.0f"),
                "Còn thiếu": st.column_config.NumberColumn(width=90, format="%.0f"),
                "Ghi chú": st.column_config.TextColumn(width="large"),
            },
        )
    else:
        st.success("Không có sản phẩm nào bị thiếu tồn.")

    render_section_header(
        "Sản phẩm không tồn tại",
        "Hiển thị rõ sản phẩm không có trong Gộp VAT, Khớp mã hoặc cả hai sheet để dễ cập nhật dữ liệu nguồn.",
    )
    if result.issues:
        st.error(f"Có {len(result.issues)} sản phẩm không tồn tại hoặc chưa thể đối chiếu.")
        unavailable_df = pd.DataFrame(
            build_unavailable_display_rows(
                result.issues,
                workbook.mapping_rows,
                workbook.stock_rows,
            )
        )
        st.dataframe(
            unavailable_df,
            width="stretch",
            hide_index=True,
            column_config={
                "Dòng nhập": st.column_config.NumberColumn(width="small", format="%d"),
                "Mã SP": st.column_config.TextColumn(width="medium"),
                "Tên SP": st.column_config.TextColumn(width="large"),
                "Trạng thái trong file": st.column_config.TextColumn(width="medium"),
                "Nội dung": st.column_config.TextColumn(width="large"),
            },
        )
    else:
        st.success("Không có sản phẩm nào thiếu dữ liệu ở Gộp VAT hoặc Khớp mã.")
