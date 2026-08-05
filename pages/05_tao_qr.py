"""Trang tạo mã QR VietQR thủ công — chọn tài khoản có sẵn, nhập số tiền và
nội dung chuyển khoản (có thể để trống), rồi tạo QR."""

from __future__ import annotations

import streamlit as st

from src.auth import get_current_user
from src.session import get_config
from src.vietqr import build_vietqr_image_url, format_amount_input, parse_amount_input
from ui import apply_global_styles, render_feature_top_bar, render_section_header

st.set_page_config(
    page_title="Tạo QR", page_icon="💳", layout="wide", initial_sidebar_state="expanded"
)
apply_global_styles()

config = get_config()
user = get_current_user(config, session_email=st.session_state.get("user_email"))

# Trang này không cần dữ liệu Google Sheets; bỏ qua giá trị trả về (nút Cập nhật).
render_feature_top_bar(active="tao_qr", config=config, user=user)

account_keys = list(config.vietqr.accounts.keys())

if not account_keys:
    st.warning("Chưa cấu hình tài khoản ngân hàng nào trong config/settings.yaml (mục vietqr.accounts).")
    st.stop()


def _format_account(key: str) -> str:
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
        account_keys,
        format_func=_format_account,
        key="manual_qr_account",
    )
    st.text_input(
        "Số tiền",
        key="manual_qr_amount",
        on_change=_reformat_amount,
    )
    transfer_content = st.text_input(
        "Nội dung chuyển khoản (để trống cũng được)",
        key="manual_qr_content",
    )
    generate_clicked = st.button("🔲 Tạo mã QR", type="primary", key="manual-qr-generate-btn")

if generate_clicked:
    amount = parse_amount_input(st.session_state["manual_qr_amount"])
    account = config.vietqr.accounts[selected_account_key]
    url = build_vietqr_image_url(
        account,
        amount=amount,
        add_info=transfer_content.strip(),
        template=config.vietqr.template,
    )
    render_section_header("Kết quả")
    caption = f"{_format_account(selected_account_key)} — {amount:,.0f}đ"
    if transfer_content.strip():
        caption += f" — {transfer_content.strip()}"
    st.image(url, caption=caption)
