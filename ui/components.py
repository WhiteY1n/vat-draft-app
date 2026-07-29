"""Các component trình bày thuần UI, không thay đổi dữ liệu nghiệp vụ."""

from __future__ import annotations

from collections.abc import Sequence

import streamlit as st

from src.storage.base import FileVersionMetadata


def render_page_header(title: str, description: str, icon: str | None = None) -> None:
    heading = f"{icon} {title}" if icon else title
    st.title(heading)
    if description:
        st.caption(description)


def render_section_header(title: str, description: str | None = None) -> None:
    st.subheader(title)
    if description:
        st.caption(description)


def render_data_version_banner(
    metadata: FileVersionMetadata | None,
    *,
    valid: bool | None = None,
) -> None:
    if metadata is None:
        st.info("Chưa có dữ liệu hiện tại. Hãy tải lên và xác nhận một file Excel hợp lệ.")
        return

    detail = (
        f"**{metadata.original_file_name}** · "
        f"{metadata.gop_vat_row_count:,} dòng Gộp VAT · "
        f"{metadata.khop_ma_row_count:,} dòng Khớp mã"
    )
    if valid is False:
        st.error(f"Dữ liệu hiện tại không hợp lệ · {detail}")
    elif valid is True:
        st.success(f"Dữ liệu sẵn sàng · {detail}")
    else:
        st.info(f"Đang dùng dữ liệu · {detail}")


def render_compact_data_status(metadata: FileVersionMetadata) -> None:
    """Hiển thị trạng thái và tên file trong một card nhỏ, không lộ chi tiết kỹ thuật."""

    with st.container(border=True):
        st.caption("Dữ liệu sẵn sàng")
        st.markdown(f":green[**{metadata.original_file_name}**]")


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
