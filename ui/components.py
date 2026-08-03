"""Các component trình bày thuần UI, không thay đổi dữ liệu nghiệp vụ."""

from __future__ import annotations

from collections.abc import Sequence

import streamlit as st


def render_section_header(title: str, description: str | None = None) -> None:
    st.subheader(title)
    if description:
        st.caption(description)




def render_metric_card(
    label: str,
    value: str | int | float,
    *,
    help_text: str | None = None,
) -> None:
    st.metric(label, value, help=help_text)


def render_empty_state(title: str, description: str) -> None:
    with st.container(border=True):
        st.markdown(f"**{title}**")
        st.caption(description)


def render_action_bar(widths: Sequence[int | float], *, gap: str = "small"):
    """Tạo hàng hành động; widget vẫn được khai báo tại page để giữ key và thứ tự."""

    return st.columns(list(widths), gap=gap)


def render_alert_summary(items: Sequence[tuple[str, int, str]]) -> None:
    """Hiển thị các chỉ báo đã được tính sẵn, không áp dụng ngưỡng mới."""

    if not items:
        st.success("Không có cảnh báo dữ liệu cần hiển thị.")
        return

    columns = st.columns(len(items), gap="small")
    for column, (label, count, description) in zip(columns, items):
        with column:
            with st.container(border=True):
                st.metric(label, f"{count:,}")
                st.caption(description)
