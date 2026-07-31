"""Điểm vào chính — không có trang Tổng quan riêng, chuyển thẳng sang Xử lý hóa đơn."""

from __future__ import annotations

import streamlit as st

from src.auth import get_current_user
from src.session import get_config

st.set_page_config(page_title="Nháp VAT", page_icon="🧾", layout="wide")

config = get_config()
user = get_current_user(config, session_email=st.session_state.get("user_email"))
st.session_state["current_user"] = user

if config.auth_mode == "google" and not user.is_authenticated:
    st.warning(
        "AUTH_MODE=google nhưng chưa đăng nhập. Phần đăng nhập Google OpenID Connect "
        "chưa được triển khai đầy đủ trong phiên bản này (dự kiến Milestone 5). "
        "Có thể đặt AUTH_MODE=none để phát triển/kiểm thử ở local."
    )
else:
    st.switch_page("pages/01_xu_ly_hoa_don.py")
