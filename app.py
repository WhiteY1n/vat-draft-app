"""Điểm vào chính và trang Tổng quan của web app tối ưu nháp VAT."""

from __future__ import annotations

from datetime import datetime

import streamlit as st

from src.auth import Role, get_current_user
from src.session import get_config, get_current_version_metadata, get_current_workbook
from ui import (
    apply_global_styles,
    render_alert_summary,
    render_data_version_banner,
    render_metric_card,
    render_page_header,
    render_section_header,
    render_sidebar,
)

st.set_page_config(page_title="Tổng quan · Tối ưu nháp VAT", page_icon="🏠", layout="wide")
apply_global_styles()


def _format_updated_at(value: str | None) -> str:
    if not value:
        return "Chưa có"
    try:
        return datetime.fromisoformat(value).strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return value


def main() -> None:
    config = get_config()
    user = get_current_user(config, session_email=st.session_state.get("user_email"))
    st.session_state["current_user"] = user

    meta = get_current_version_metadata() if user.is_authenticated else None
    render_sidebar(meta)

    render_page_header(
        "Tổng quan",
        "Theo dõi dữ liệu đang dùng và đi nhanh đến công việc cần thực hiện.",
        icon="🏠",
    )

    if config.auth_mode == "google" and not user.is_authenticated:
        st.warning(
            "AUTH_MODE=google nhưng chưa đăng nhập. Phần đăng nhập Google OpenID Connect "
            "chưa được triển khai đầy đủ trong phiên bản này (dự kiến Milestone 5). "
            "Có thể đặt AUTH_MODE=none để phát triển/kiểm thử ở local."
        )
        return

    render_data_version_banner(meta, valid=None if meta is None else meta.check_status == "valid")

    render_section_header("Chỉ số dữ liệu")
    metric_columns = st.columns(4, gap="small")
    with metric_columns[0]:
        render_metric_card("Số dòng Gộp VAT", f"{meta.gop_vat_row_count:,}" if meta else "—")
    with metric_columns[1]:
        render_metric_card("Số dòng Khớp mã", f"{meta.khop_ma_row_count:,}" if meta else "—")
    with metric_columns[2]:
        render_metric_card("Thời gian cập nhật", _format_updated_at(meta.uploaded_at if meta else None))
    with metric_columns[3]:
        data_label = "Sẵn sàng" if meta and meta.check_status == "valid" else "Chưa sẵn sàng"
        render_metric_card("Trạng thái dữ liệu", data_label)

    render_section_header(
        "Thao tác nhanh",
        "Chọn công việc cần làm. Dữ liệu và kết quả đang nhập được giữ theo session hiện tại.",
    )
    quick_columns = st.columns(3, gap="medium")
    quick_actions = [
        (
            quick_columns[0],
            "Xử lý hóa đơn",
            "Dán dữ liệu, kiểm tra và xuất kết quả phân bổ.",
            "pages/01_xu_ly_hoa_don.py",
            "🧾",
        ),
        (
            quick_columns[1],
            "Tra cứu nguồn",
            "Tra nhiều mã sản phẩm và xem nguồn còn tồn dương.",
            "pages/02_tra_cuu_nguon.py",
            "🔎",
        ),
        (
            quick_columns[2],
            "Kiểm tra dữ liệu",
            "Xem các chỉ báo cần xử lý hoặc rà soát.",
            "pages/03_kiem_tra_du_lieu.py",
            "✅",
        ),
    ]
    for column, title, description, page, icon in quick_actions:
        with column:
            with st.container(border=True):
                st.markdown(f"**{title}**")
                st.caption(description)
                st.page_link(page, label=f"Mở {title.lower()}", icon=icon)

    render_section_header("Tóm tắt cảnh báo dữ liệu")
    if meta is None:
        st.info("Chưa có dữ liệu để tổng hợp cảnh báo.")
    else:
        with st.status("Đang đọc các chỉ báo từ dữ liệu hiện tại...", expanded=False) as status:
            workbook = get_current_workbook()
            status.update(label="Đã cập nhật chỉ báo dữ liệu", state="complete")

        alert_items: list[tuple[str, int, str]] = []
        if workbook and workbook.gop_vat_summary:
            summary = workbook.gop_vat_summary
            alert_items.extend(
                [
                    ("Mã VAT trống", summary.blank_ma_vat_count, "Cần xử lý trong sheet Gộp VAT."),
                    (
                        "Tồn không dương",
                        summary.zero_or_negative_ton_count,
                        "Được loại khỏi danh sách nguồn khả dụng.",
                    ),
                    (
                        "Tồn không hợp lệ",
                        summary.invalid_ton_count,
                        "Cần rà soát giá trị không chuyển được thành số.",
                    ),
                ]
            )
        if workbook and workbook.khop_ma_summary:
            summary = workbook.khop_ma_summary
            alert_items.append(
                (
                    "Mã SP nhiều Mã VAT",
                    summary.duplicate_ma_sp_multi_vat_count,
                    "Có thể chặn tra cứu hoặc xử lý hóa đơn.",
                )
            )
        render_alert_summary(alert_items)

    with st.expander("Thông tin kỹ thuật"):
        role_label = "Admin" if user.role == Role.ADMIN else "User"
        st.write(f"**Vai trò:** {role_label}")
        st.write(f"**Chế độ đăng nhập:** `{config.auth_mode}`")
        if meta is not None:
            st.write(f"**ID phiên bản:** `{meta.version_id}`")
            st.write(f"**SHA-256:** `{meta.sha256}`")
        st.caption(
            "Ứng dụng không ghi kết quả vào file nguồn và không trừ tồn thật. "
            "Các phép tính so khớp, xếp hạng và phân bổ đều deterministic."
        )


if __name__ == "__main__":
    main()
