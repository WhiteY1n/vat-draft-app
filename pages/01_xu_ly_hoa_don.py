"""Trang xử lý hóa đơn — dán dữ liệu, kiểm tra, tạo kết quả và xuất file."""

from __future__ import annotations

import io
import os
import tempfile
import uuid

import pandas as pd
import streamlit as st

from src.excel_export import export_result_workbook, result_lines_to_tsv
from src.models import InvoiceInputRow
from src.pipeline import process_invoice
from src.session import get_config, get_current_version_metadata, get_current_workbook
from ui import (
    apply_global_styles,
    render_action_bar,
    render_compact_data_status,
    render_data_version_banner,
    render_metric_card,
    render_page_header,
    render_section_header,
    render_sidebar,
)

st.set_page_config(page_title="Xử lý hóa đơn", page_icon="🧾", layout="wide")
apply_global_styles()

meta = get_current_version_metadata()
render_sidebar(meta)

config = get_config()
workbook = get_current_workbook()

header_column, status_column = st.columns([4, 1.35], gap="large")
with header_column:
    render_page_header("Xử lý hóa đơn", "", icon="🧾")
with status_column:
    if workbook is not None and workbook.is_valid and meta is not None:
        render_compact_data_status(meta)

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
    st.session_state.pop("process_result", None)
    st.rerun()

result = st.session_state.get("process_result")

if read_and_check_clicked:
    result = None
    st.session_state.pop("process_result", None)

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
    invoice_rows: list[InvoiceInputRow] = []
    for idx, row in df.iterrows():
        ma_sp = row.get("Mã SP", "")
        ten_sp = row.get("Tên SP", "")
        sl = row.get("SL", "")
        gia_ban = row.get("Giá bán", "")
        if str(ma_sp).strip() == "" and str(ten_sp).strip() == "":
            continue  # bỏ qua dòng trống hoàn toàn
        invoice_rows.append(
            InvoiceInputRow(
                input_row_id=str(uuid.uuid4()),
                order_index=idx + 1,
                ma_sp=ma_sp,
                ten_sp=ten_sp,
                sl=sl,
                gia_ban=gia_ban,
            )
        )

    if not invoice_rows:
        st.warning("Chưa có dòng hóa đơn nào để kiểm tra.")
        st.session_state.pop("process_result", None)
    else:
        result = process_invoice(invoice_rows, workbook.stock_rows, workbook.mapping_rows, config)
        st.session_state["process_result"] = result
        st.session_state["last_invoice_rows"] = invoice_rows

if result is not None:
    render_section_header(
        "Kết quả xử lý",
        "Dữ liệu đã được đọc, kiểm tra và phân bổ theo các quy tắc hiện tại.",
    )

    input_count = len(st.session_state.get("last_invoice_rows", []))
    error_row_count = len({error.input_row_id for error in result.errors})
    valid_row_count = input_count if result.is_valid else max(0, input_count - error_row_count)
    summary_columns = st.columns(3, gap="small")
    with summary_columns[0]:
        render_metric_card("Tổng dòng đã kiểm tra", f"{input_count:,}")
    with summary_columns[1]:
        render_metric_card("Dòng không có lỗi chặn", f"{valid_row_count:,}")
    with summary_columns[2]:
        render_metric_card("Dòng có lỗi", f"{error_row_count:,}")

    if not result.is_valid:
        st.error(f"Có {len(result.errors)} lỗi chặn. Hãy sửa các dòng bên dưới rồi kiểm tra lại.")
        err_df = pd.DataFrame(
            [
                {
                    "Dòng hóa đơn": e.order_index,
                    "Mã SP": e.ma_sp,
                    "Tên SP": e.ten_sp,
                    "Loại lỗi": e.error_type,
                    "Nội dung chi tiết": e.detail,
                    "Hướng xử lý đề xuất": e.suggestion,
                }
                for e in result.errors
            ]
        )
        st.dataframe(
            err_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Dòng hóa đơn": st.column_config.NumberColumn(width="small", format="%d"),
                "Mã SP": st.column_config.TextColumn(width="medium"),
                "Tên SP": st.column_config.TextColumn(width="large"),
                "Loại lỗi": st.column_config.TextColumn(width="medium"),
                "Nội dung chi tiết": st.column_config.TextColumn(width="large"),
                "Hướng xử lý đề xuất": st.column_config.TextColumn(width="large"),
            },
        )
    else:
        st.success(
            f"Dữ liệu hợp lệ. Tổng SL yêu cầu = {result.total_sl_yeu_cau:,.0f}; "
            f"tổng SL phân bổ = {result.total_sl_phan_bo:,.0f}."
        )

        render_section_header("Kết quả phân bổ")
        result_df = pd.DataFrame(
            [
                {
                    "STT hóa đơn": line.stt_hoa_don,
                    "Dòng phân bổ": line.dong_phan_bo,
                    "MÃ SP": line.ma_sp,
                    "TÊN SP": line.ten_sp,
                    "SL yêu cầu": line.sl_yeu_cau,
                    "SL phân bổ": line.sl_phan_bo,
                    "Giá bán": line.gia_ban,
                    "Mã VAT": line.ma_vat,
                    "TÊN VAT": line.ten_vat,
                    "TÊN KẾ TOÁN": line.ten_ke_toan,
                    "ĐVT": line.dvt,
                    "NGUỒN": line.nguon,
                    "TỒN CÒN NHÁP TRƯỚC": line.ton_con_nhap_truoc,
                    "TỒN CÒN MÔ PHỎNG SAU": line.ton_con_mo_phong_sau,
                    "%VAT": f"{line.phan_tram_vat * 100:.1f}%" if line.phan_tram_vat is not None else "",
                    "GIÁ NHÁP": line.gia_nhap,
                    "Điểm khớp tên": line.diem_khop_ten,
                    "Lý do chọn": line.ly_do_chon,
                }
                for line in result.result_lines
            ]
        )
        st.dataframe(
            result_df,
            use_container_width=True,
            height=440,
            column_config={
                "STT hóa đơn": st.column_config.NumberColumn(width="small", format="%d"),
                "Dòng phân bổ": st.column_config.NumberColumn(width="small", format="%d"),
                "MÃ SP": st.column_config.TextColumn(width="medium"),
                "TÊN SP": st.column_config.TextColumn(width="large"),
                "Mã VAT": st.column_config.TextColumn(width="medium"),
                "TÊN VAT": st.column_config.TextColumn(width="large"),
                "TÊN KẾ TOÁN": st.column_config.TextColumn(width="large"),
                "Lý do chọn": st.column_config.TextColumn(width="large"),
            },
        )

        render_section_header(
            "Xuất kết quả",
            "Có thể tải TSV để dán vào Excel, xuất workbook đầy đủ hoặc mở chế độ xem in.",
        )
        tsv_text = result_lines_to_tsv(result.result_lines)

        with st.container(border=True):
            col_a, col_b, col_c = st.columns(3, gap="small")
            with col_a:
                st.download_button(
                    "📋 Tải TSV (dán vào Excel)",
                    data=tsv_text,
                    file_name="ket_qua_nhap_vat.tsv",
                    mime="text/tab-separated-values",
                )
            with col_b:
                buf = io.BytesIO()
                export_path = export_result_workbook(
                    os.path.join(tempfile.gettempdir(), "vat_export_tmp.xlsx"),
                    result.result_lines,
                    st.session_state.get("last_invoice_rows", []),
                    source_file_name=meta.original_file_name,
                    source_file_hash=meta.sha256,
                    config_summary={
                        "gia_nhap_decimal_places": config.gia_nhap_decimal_places,
                        "allow_fractional_sl": config.allow_fractional_sl,
                        "source_tiebreak_priority": config.source_tiebreak_priority,
                    },
                    decimal_places=config.gia_nhap_decimal_places,
                )
                with open(export_path, "rb") as file_handle:
                    st.download_button(
                        "📊 Xuất Excel (.xlsx)",
                        data=file_handle.read(),
                        file_name="ket_qua_nhap_vat.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
            with col_c:
                if st.button("🖨️ Chế độ xem in"):
                    st.session_state["show_print_view"] = True

        if st.session_state.get("show_print_view"):
            st.divider()
            st.markdown("### Chế độ xem in")
            st.caption(
                f"Dữ liệu nguồn: {meta.original_file_name} — "
                f"Thời gian: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}"
            )
            st.dataframe(result_df, use_container_width=True, hide_index=True)
            st.caption(
                "Dùng Ctrl+P / Cmd+P của trình duyệt để in trang này "
                "(gợi ý: chọn khổ ngang / Landscape)."
            )
