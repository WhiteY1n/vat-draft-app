"""Trang xử lý hóa đơn — dán dữ liệu, kiểm tra, tạo kết quả và xuất file."""

from __future__ import annotations

import io

import pandas as pd
import streamlit as st

from src.auth import get_current_user
from src.invoice_allocation import (
    InvoiceAllocationResult,
    allocate_invoice_sources,
    build_unified_display_rows,
)
from src.invoice_file_reader import parse_invoice_files
from src.result_builder import build_unified_columns
from src.session import get_config, get_current_version_metadata, load_workbook_from_sheets
from src.source_lookup import SourceLookupInput
from src.vietqr import (
    build_vietqr_image_url,
    compute_source_amounts,
    compute_total_amount,
    extract_invoice_codes,
    format_amount_input,
    get_account_for_source,
    parse_amount_input,
)
from ui import (
    apply_global_styles,
    render_action_bar,
    render_feature_top_bar,
    render_metric_card,
    render_section_header,
)

st.set_page_config(
    page_title="Xử lý hóa đơn", page_icon="🧾", layout="wide", initial_sidebar_state="expanded"
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
            load_workbook_from_sheets(config, force=True)
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
        columns=["Mã SP", "Tên SP", "SL", "Giá bán", "Ghi chú hàng hóa"]
    )

render_section_header(
    "1. Nhập dữ liệu",
    "Dán 4 cột từ Excel theo thứ tự Mã SP, Tên SP, SL, Giá bán, hoặc tải trực tiếp file hóa đơn (.xlsx).",
)
with st.container(border=True):
    tab_file, tab_paste = st.tabs(["📁 Tải file hóa đơn", "📋 Dán dữ liệu"])

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

    with tab_paste:
        pasted_text = st.text_area("Khu vực dán dữ liệu", height=150, key="paste_area")

        col_read, col_clear, _ = render_action_bar([1.7, 1, 3])
        with col_read:
            read_and_check_clicked = st.button(
                "📥 Đọc và kiểm tra dữ liệu", type="primary", key="paste-read-btn"
            )
        with col_clear:
            clear_clicked = st.button("🗑️ Xóa toàn bộ", type="secondary", key="paste-clear-btn")

def _clear_vietqr_widget_state() -> None:
    """Xóa các giá trị QR (số tiền/tài khoản đã chọn) của kết quả cũ để tránh hiển thị lệch."""

    for key in [
        k
        for k in st.session_state
        if k.startswith(("vietqr_amount_", "vietqr_account_", "vietqr_total_account"))
    ]:
        st.session_state.pop(key, None)


if clear_clicked:
    st.session_state["invoice_df"] = pd.DataFrame(columns=["Mã SP", "Tên SP", "SL", "Giá bán", "Ghi chú hàng hóa"])
    st.session_state.pop("check_result", None)
    st.session_state.pop("invoice_codes", None)
    st.session_state["invoice_has_meta"] = False
    _clear_vietqr_widget_state()
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
    st.session_state.pop("invoice_codes", None)
    st.session_state["invoice_has_meta"] = False
    _clear_vietqr_widget_state()
    if not pasted_text.strip():
        st.warning("Hãy dán dữ liệu hóa đơn trước khi kiểm tra.")
    else:
        lines = [ln for ln in pasted_text.strip("\n").split("\n") if ln.strip() != ""]
        parsed_rows = []
        for ln in lines:
            cols = ln.split("\t")
            cols = (cols + ["", "", "", "", ""])[:5]
            # bỏ qua dòng header nếu người dùng lỡ dán kèm header
            if cols[0].strip().lower() in ("mã sp", "ma sp") and cols[2].strip().lower() in ("sl",):
                continue
            parsed_rows.append(cols)

if file_read_clicked:
    result = None
    st.session_state.pop("check_result", None)
    st.session_state.pop("invoice_codes", None)
    _clear_vietqr_widget_state()
    if not uploaded_invoice_files:
        st.warning("Hãy chọn ít nhất một file hóa đơn (.xlsx).")
    else:
        files = [(f.getvalue(), f.name) for f in uploaded_invoice_files]
        parsed_rows, parse_errors, has_invoice_meta = parse_invoice_files(files)
        for err in parse_errors:
            st.warning(err)
        st.session_state["invoice_has_meta"] = has_invoice_meta
        st.session_state["invoice_codes"] = extract_invoice_codes(
            [f.name for f in uploaded_invoice_files]
        )

if parsed_rows is not None:
    df_columns = ["Mã SP", "Tên SP", "SL", "Giá bán", "Ghi chú hàng hóa"]
    row_width = len(parsed_rows[0]) if parsed_rows else len(df_columns)
    if row_width >= 7:
        df_columns = df_columns + ["Mã hóa đơn", "Thành tiền"]
    new_df = pd.DataFrame(parsed_rows, columns=df_columns)
    st.session_state["invoice_df"] = new_df

    df = st.session_state["invoice_df"].reset_index(drop=True)
    lookup_rows: list[SourceLookupInput] = []
    for idx, row in df.iterrows():
        ma_sp = row.get("Mã SP", "")
        ten_sp = row.get("Tên SP", "")
        sl = row.get("SL", "")
        gia_ban = row.get("Giá bán", "")
        ghi_chu = row.get("Ghi chú hàng hóa", "")
        ma_hoa_don = row.get("Mã hóa đơn", "")
        thanh_tien = row.get("Thành tiền", "")
        if str(ma_sp).strip() == "" and str(ten_sp).strip() == "":
            continue  # bỏ qua dòng trống hoàn toàn
        lookup_rows.append(
            SourceLookupInput(
                order_index=idx + 1,
                ma_sp=ma_sp,
                ten_sp=ten_sp,
                sl=sl,
                gia_ban=gia_ban,
                ghi_chu_hang_hoa=ghi_chu,
                ma_hoa_don=ma_hoa_don,
                thanh_tien=thanh_tien,
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
    shortage_count = result.shortage_product_count
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
        "Danh sách sản phẩm",
        "Gộp cả 3 nhóm sản phẩm vào một bảng, phân biệt bằng cột Trạng thái (OK / Thiếu tồn / "
        "Không có mã). Các dòng cùng Mã hóa đơn luôn được xếp cạnh nhau.",
    )
    has_any_row = bool(result.lines or result.shortages or result.issues)
    if has_any_row:
        status_parts = [f"{output_count} OK"]
        if shortage_count:
            status_parts.append(f"{shortage_count} thiếu tồn")
        if unavailable_count:
            status_parts.append(f"{unavailable_count} không có mã")
        if shortage_count or unavailable_count:
            st.warning(" · ".join(status_parts))
        else:
            st.success(" · ".join(status_parts))

        result_df = pd.DataFrame(
            build_unified_display_rows(result.lines, result.shortages, result.issues)
        )
        display_columns = build_unified_columns(st.session_state.get("invoice_has_meta", False))
        result_df = result_df[display_columns]

        NO_SORT = "(Không sắp xếp)"
        sort_option_columns = [NO_SORT] + display_columns
        sort_row = st.columns([2, 1.2, 2, 1.2], gap="small")
        with sort_row[0]:
            primary_sort_col = st.selectbox(
                "Sắp xếp chính theo cột", sort_option_columns, key="result_sort_primary_col"
            )
        with sort_row[1]:
            primary_sort_dir = st.selectbox(
                "Thứ tự", ["Tăng dần", "Giảm dần"], key="result_sort_primary_dir"
            )
        with sort_row[2]:
            secondary_sort_col = st.selectbox(
                "Sau đó theo cột", sort_option_columns, key="result_sort_secondary_col"
            )
        with sort_row[3]:
            secondary_sort_dir = st.selectbox(
                "Thứ tự", ["Tăng dần", "Giảm dần"], key="result_sort_secondary_dir"
            )

        sort_by: list[str] = []
        ascending: list[bool] = []
        if primary_sort_col != NO_SORT:
            sort_by.append(primary_sort_col)
            ascending.append(primary_sort_dir == "Tăng dần")
            if secondary_sort_col != NO_SORT and secondary_sort_col != primary_sort_col:
                sort_by.append(secondary_sort_col)
                ascending.append(secondary_sort_dir == "Tăng dần")
        elif secondary_sort_col != NO_SORT:
            st.caption("⚠️ Chọn cột sắp xếp chính trước khi chọn cột sắp xếp phụ.")

        if sort_by:
            # Sắp xếp theo lựa chọn của người dùng sẽ phá vỡ việc gộp nhóm theo
            # Mã hóa đơn — báo rõ để người dùng biết đang xem theo thứ tự nào.
            result_df = result_df.sort_values(
                by=sort_by, ascending=ascending, kind="stable"
            ).reset_index(drop=True)
            st.caption("ℹ️ Đang sắp xếp theo cột đã chọn — các dòng cùng Mã hóa đơn có thể không còn liền kề.")

        def _status_color(value: str) -> str:
            if value == "OK":
                return "color: #2e7d32; font-weight: 600;"
            if value == "Thiếu tồn":
                return "color: #e65100; font-weight: 600;"
            if value == "Không có mã":
                return "color: #d32f2f; font-weight: 600;"
            return ""

        with st.container(key="result-highlight"):
            st.dataframe(
                result_df.style.map(_status_color, subset=["Trạng thái"]),
                width="stretch",
                height=440,
                hide_index=True,
                column_config={
                    "Trạng thái": st.column_config.TextColumn(width=90),
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
                    "Ghi chú hàng hóa": st.column_config.TextColumn(width=150),
                    "Mã hóa đơn": st.column_config.TextColumn(width=90),
                    "Thành tiền": st.column_config.NumberColumn(width=100, format="%,d"),
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
        st.info("Chưa có sản phẩm nào để hiển thị.")

    # -----------------------------------------------------------------------
    # Thanh toán qua QR — chỉ hiện sau khi có sản phẩm thỏa mãn để xuất.
    # -----------------------------------------------------------------------
    if result.lines:
        render_section_header(
            "Thanh toán qua QR",
            "Chọn loại hóa đơn trước: có VAT sẽ tách QR theo từng nguồn, không VAT sẽ gộp tất cả nguồn "
            "thành 1 QR duy nhất.",
        )
        with st.container(border=True):
            default_content = " ".join(st.session_state.get("invoice_codes") or [])
            transfer_content = st.text_input(
                "Nội dung chuyển khoản",
                value=default_content,
                help="Mặc định lấy từ mã hóa đơn trong tên file đã tải lên; có thể sửa lại trước khi tạo QR.",
                key="vietqr_transfer_content",
            )
            if not transfer_content.strip():
                st.caption(
                    "⚠️ Chưa có mã hóa đơn (thường lấy từ tên file .xlsx đã tải lên). "
                    "Hãy nhập nội dung chuyển khoản thủ công."
                )

            if "vietqr_invoice_mode" not in st.session_state:
                st.session_state["vietqr_invoice_mode"] = "co_vat"

            mode_cols = st.columns(2, gap="small")
            with mode_cols[0]:
                if st.button(
                    "🧾 Hóa đơn có VAT",
                    type="primary" if st.session_state["vietqr_invoice_mode"] == "co_vat" else "secondary",
                    key="vietqr-mode-co-vat",
                ):
                    st.session_state["vietqr_invoice_mode"] = "co_vat"
                    st.rerun()
            with mode_cols[1]:
                if st.button(
                    "🧾 Hóa đơn không VAT",
                    type="primary" if st.session_state["vietqr_invoice_mode"] == "khong_vat" else "secondary",
                    key="vietqr-mode-khong-vat",
                ):
                    st.session_state["vietqr_invoice_mode"] = "khong_vat"
                    st.rerun()

            invoice_mode = st.session_state["vietqr_invoice_mode"]
            st.divider()

            account_keys = list(config.vietqr.accounts.keys())

            def _format_account(key: str) -> str:
                acc = config.vietqr.accounts[key]
                base = acc.label or f"{acc.bank_id} - {acc.account_no}"
                label = f"{base} — {acc.bank_id} {acc.account_no}" if acc.label else base
                return f"{label} ({acc.account_name})" if acc.account_name else label

            def _reformat_amount(key: str) -> None:
                st.session_state[key] = format_amount_input(parse_amount_input(st.session_state[key]))

            def _amount_input(key: str, default_value: float) -> int:
                if key not in st.session_state:
                    st.session_state[key] = format_amount_input(int(round(default_value)))
                st.text_input(
                    "Số tiền",
                    key=key,
                    on_change=_reformat_amount,
                    args=(key,),
                )
                return parse_amount_input(st.session_state[key])

            if invoice_mode == "co_vat":
                st.caption(
                    "Mỗi nguồn dùng một mã QR riêng, số tiền tính theo Giá nhập (trước VAT). "
                    "Chọn tài khoản nhận tiền cho từng nguồn bên dưới."
                )
                if not account_keys:
                    st.warning("Chưa cấu hình tài khoản ngân hàng nào trong config/settings.yaml.")
                else:
                    source_amounts = compute_source_amounts(result.lines)
                    for nguon, amount in source_amounts.items():
                        st.markdown(f"**Nguồn: {nguon}**")
                        if amount.thieu_don_gia:
                            st.caption(
                                "⚠️ Một số dòng thiếu Giá bán/Giá nhập, số tiền QR có thể chưa đầy đủ."
                            )
                        default_account = get_account_for_source(nguon, config)
                        default_index = (
                            account_keys.index(default_account.key)
                            if default_account is not None and default_account.key in account_keys
                            else 0
                        )
                        selected_account_key = st.selectbox(
                            "Tài khoản nhận tiền",
                            account_keys,
                            index=default_index,
                            format_func=_format_account,
                            key=f"vietqr_account_{nguon}",
                        )
                        account = config.vietqr.accounts[selected_account_key]
                        qr_amount = _amount_input(
                            f"vietqr_amount_co_vat_{nguon}", amount.tong_gia_nhap
                        )
                        if st.button(
                            f"🔲 Tạo mã QR — {qr_amount:,.0f}đ",
                            key=f"vietqr-co-vat-{nguon}",
                        ):
                            url = build_vietqr_image_url(
                                account,
                                amount=qr_amount,
                                add_info=transfer_content.strip(),
                                template=config.vietqr.template,
                            )
                            st.image(url, caption=f"{nguon} — {qr_amount:,.0f}đ")
            else:
                st.caption(
                    "Gộp toàn bộ các nguồn thành 1 QR duy nhất, số tiền tính theo Giá bán (đã gồm VAT)."
                )
                total_amount = compute_total_amount(result.lines)
                if total_amount.thieu_don_gia:
                    st.caption("⚠️ Một số dòng thiếu Giá bán/Giá nhập, số tiền QR có thể chưa đầy đủ.")

                if not account_keys:
                    st.warning("Chưa cấu hình tài khoản ngân hàng nào trong config/settings.yaml.")
                else:
                    selected_account_key = st.selectbox(
                        "Tài khoản nhận tiền",
                        account_keys,
                        format_func=_format_account,
                        key="vietqr_total_account",
                    )
                    account = config.vietqr.accounts[selected_account_key]
                    qr_amount = _amount_input(
                        "vietqr_amount_khong_vat_total", total_amount.tong_gia_ban
                    )
                    if st.button(
                        f"🔲 Tạo mã QR — {qr_amount:,.0f}đ",
                        key="vietqr-khong-vat-total",
                    ):
                        url = build_vietqr_image_url(
                            account,
                            amount=qr_amount,
                            add_info=transfer_content.strip(),
                            template=config.vietqr.template,
                        )
                        st.image(url, caption=f"Tất cả nguồn — {qr_amount:,.0f}đ")
