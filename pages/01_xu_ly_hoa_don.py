"""Trang 1: Xử lý hóa đơn — dán dữ liệu, kiểm tra, tạo kết quả, xuất Excel, in."""

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

st.set_page_config(page_title="Xử lý hóa đơn", page_icon="🧾", layout="wide")

st.title("Xử lý hóa đơn")

config = get_config()
workbook = get_current_workbook()
meta = get_current_version_metadata()

if workbook is None or not workbook.is_valid:
    st.error(
        "Chưa có dữ liệu hiện tại hợp lệ. Vào trang Quản lý dữ liệu để upload và xác nhận "
        "file Excel trước."
    )
    st.stop()

st.info(
    f"Đang dùng dữ liệu: **{meta.original_file_name}** "
    f"({meta.gop_vat_row_count:,} dòng Gộp VAT, {meta.khop_ma_row_count:,} dòng Khớp mã)."
)

if "invoice_df" not in st.session_state:
    st.session_state["invoice_df"] = pd.DataFrame(
        columns=["Mã SP", "Tên SP", "SL", "Giá bán"]
    )

st.subheader("1. Dán dữ liệu hóa đơn")
st.caption(
    "Sao chép nhiều dòng từ Excel gồm 4 cột: Mã SP, Tên SP, SL, Giá bán (dạng tab-separated) "
    "rồi dán vào ô bên dưới."
)

pasted_text = st.text_area("Khu vực dán dữ liệu", height=150, key="paste_area")

col_read, col_clear = st.columns([1, 1])
with col_read:
    read_clicked = st.button("📥 Đọc dữ liệu", type="primary")
with col_clear:
    clear_clicked = st.button("🗑️ Xóa toàn bộ")

if clear_clicked:
    st.session_state["invoice_df"] = pd.DataFrame(columns=["Mã SP", "Tên SP", "SL", "Giá bán"])
    st.session_state.pop("process_result", None)
    st.rerun()

if read_clicked and pasted_text.strip():
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
    st.session_state.pop("process_result", None)
    st.rerun()

st.subheader("2. Bảng xem trước — có thể sửa trực tiếp")
edited_df = st.data_editor(
    st.session_state["invoice_df"],
    num_rows="dynamic",
    use_container_width=True,
    key="invoice_editor",
)
st.session_state["invoice_df"] = edited_df

col_check, _ = st.columns([1, 3])
with col_check:
    check_clicked = st.button("✅ Kiểm tra dữ liệu")

result = st.session_state.get("process_result")

if check_clicked or result is not None:
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
    st.subheader("3. Kết quả kiểm tra")
    if not result.is_valid:
        st.error(f"Có {len(result.errors)} lỗi chặn. Không thể tạo kết quả cho đến khi sửa xong.")
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
        st.dataframe(err_df, use_container_width=True)
    else:
        st.success(
            f"Hợp lệ: {len(st.session_state.get('last_invoice_rows', []))} dòng hóa đơn, "
            f"tổng SL yêu cầu = {result.total_sl_yeu_cau:,.0f}, "
            f"tổng SL phân bổ = {result.total_sl_phan_bo:,.0f}."
        )

        st.subheader("4. Bảng kết quả")
        result_df = pd.DataFrame(
            [
                {
                    "STT hóa đơn": l.stt_hoa_don,
                    "Dòng phân bổ": l.dong_phan_bo,
                    "MÃ SP": l.ma_sp,
                    "TÊN SP": l.ten_sp,
                    "SL yêu cầu": l.sl_yeu_cau,
                    "SL phân bổ": l.sl_phan_bo,
                    "Giá bán": l.gia_ban,
                    "Mã VAT": l.ma_vat,
                    "TÊN VAT": l.ten_vat,
                    "TÊN KẾ TOÁN": l.ten_ke_toan,
                    "ĐVT": l.dvt,
                    "NGUỒN": l.nguon,
                    "TỒN CÒN NHÁP TRƯỚC": l.ton_con_nhap_truoc,
                    "TỒN CÒN MÔ PHỎNG SAU": l.ton_con_mo_phong_sau,
                    "%VAT": f"{l.phan_tram_vat * 100:.1f}%" if l.phan_tram_vat is not None else "",
                    "GIÁ NHÁP": l.gia_nhap,
                    "Điểm khớp tên": l.diem_khop_ten,
                    "Lý do chọn": l.ly_do_chon,
                }
                for l in result.result_lines
            ]
        )
        st.dataframe(result_df, use_container_width=True)

        st.subheader("5. Sao chép, xuất Excel và in")
        tsv_text = result_lines_to_tsv(result.result_lines)

        col_a, col_b, col_c = st.columns(3)
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
            with open(export_path, "rb") as f:
                st.download_button(
                    "📊 Xuất Excel (.xlsx)",
                    data=f.read(),
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
