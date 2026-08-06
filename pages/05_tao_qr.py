"""Trang tạo mã QR VietQR thủ công — chọn tài khoản có sẵn, nhập số tiền và
nội dung chuyển khoản (có thể để trống), rồi tạo QR."""

from __future__ import annotations

import streamlit as st

from src.auth import get_current_user
from src.config import VietQrAccount
from src.session import get_config
from src.vietqr import build_vietqr_image_url, format_amount_input, parse_amount_input
from ui import apply_global_styles, render_feature_top_bar, render_section_header

# Mã ngân hàng VietQR phổ biến, chỉ để gợi ý khi nhập tài khoản thủ công
# (danh sách đầy đủ: https://api.vietqr.io/v2/banks).
_COMMON_BANK_CODES = (
    "VCB (Vietcombank), MB (MBBank), ACB, TPB (TPBank), VIB, SHB, "
    "VPB (VPBank), MSB, OCB, BIDV, TCB (Techcombank), AGRIBANK, "
    "STB (Sacombank), VBA, ICB (VietinBank)"
)

st.set_page_config(
    page_title="Tạo QR", page_icon="💳", layout="wide", initial_sidebar_state="expanded"
)
apply_global_styles()

config = get_config()
user = get_current_user(config, session_email=st.session_state.get("user_email"))

# Trang này không cần dữ liệu Google Sheets; bỏ qua giá trị trả về (nút Cập nhật).
render_feature_top_bar(active="tao_qr", config=config, user=user)

account_keys = list(config.vietqr.accounts.keys())
_MANUAL_OPTION = "__manual__"


def _format_account(key: str) -> str:
    if key == _MANUAL_OPTION:
        return "✏️ Nhập tài khoản khác..."
    acc = config.vietqr.accounts[key]
    base = acc.label or f"{acc.bank_id} - {acc.account_no}"
    label = f"{base} — {acc.bank_id} {acc.account_no}" if acc.label else base
    return f"{label} ({acc.account_name})" if acc.account_name else label


def _reformat_amount() -> None:
    st.session_state["manual_qr_amount"] = format_amount_input(
        parse_amount_input(st.session_state["manual_qr_amount"])
    )


if "manual_qr_amount" not in st.session_state:
    st.session_state["manual_qr_amount"] = format_amount_input(0)

render_section_header("1. Thông tin QR", "Chọn tài khoản nhận tiền, nhập số tiền và nội dung chuyển khoản.")

with st.container(border=True):
    selected_account_key = st.selectbox(
        "Tài khoản nhận tiền",
        [_MANUAL_OPTION] + account_keys,
        format_func=_format_account,
        key="manual_qr_account",
    )

    manual_bank_id = manual_account_no = manual_account_name = ""
    if selected_account_key == _MANUAL_OPTION:
        st.caption(f"Mã ngân hàng VietQR thường gặp: {_COMMON_BANK_CODES}.")
        manual_col1, manual_col2 = st.columns([1, 2])
        with manual_col1:
            manual_bank_id = st.text_input(
                "Mã ngân hàng (VD: VCB, MB, ACB...)", key="manual_qr_bank_id"
            ).strip()
        with manual_col2:
            manual_account_no = st.text_input(
                "Số tài khoản", key="manual_qr_account_no"
            ).strip()
        manual_account_name = st.text_input(
            "Tên chủ tài khoản (tùy chọn)", key="manual_qr_account_name"
        ).strip()

    st.text_input(
        "Số tiền",
        key="manual_qr_amount",
        on_change=_reformat_amount,
    )
    transfer_content = st.text_input(
        "Nội dung chuyển khoản (để trống cũng được)",
        key="manual_qr_content",
    )

    manual_invalid = selected_account_key == _MANUAL_OPTION and not (
        manual_bank_id and manual_account_no
    )
    generate_clicked = st.button(
        "🔲 Tạo mã QR",
        type="primary",
        key="manual-qr-generate-btn",
        disabled=manual_invalid,
    )
    if manual_invalid:
        st.caption("⚠️ Nhập đủ Mã ngân hàng và Số tài khoản để tạo QR.")

if generate_clicked:
    amount = parse_amount_input(st.session_state["manual_qr_amount"])
    if selected_account_key == _MANUAL_OPTION:
        account = VietQrAccount(
            key=_MANUAL_OPTION,
            bank_id=manual_bank_id,
            account_no=manual_account_no,
            account_name=manual_account_name,
        )
        account_label = f"{manual_bank_id} - {manual_account_no}"
        if manual_account_name:
            account_label += f" ({manual_account_name})"
    else:
        account = config.vietqr.accounts[selected_account_key]
        account_label = _format_account(selected_account_key)

    url = build_vietqr_image_url(
        account,
        amount=amount,
        add_info=transfer_content.strip(),
        template=config.vietqr.template,
    )
    render_section_header("Kết quả")
    caption = f"{account_label} — {amount:,.0f}đ"
    if transfer_content.strip():
        caption += f" — {transfer_content.strip()}"
    st.image(url, caption=caption)
