"""Nạp CSS dùng chung; không chứa logic nghiệp vụ hoặc JavaScript."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

_STYLES_PATH = Path(__file__).with_name("styles.css")


def apply_global_styles() -> None:
    """Áp dụng stylesheet tập trung cho trang Streamlit hiện tại."""

    css = _STYLES_PATH.read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
