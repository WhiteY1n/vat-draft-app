"""Điểm vào chính của web app tối ưu nháp VAT."""

from __future__ import annotations

import streamlit as st

from src.auth import Role, get_current_user
from src.session import get_config, get_current_version_metadata

st.set_page_config(page_title="Tối ưu nháp VAT", page_icon="🧾", layout="wide")


def main() -> None:
    config = get_config()
    user = get_current_user(config, session_email=st.session_state.get("user_email"))

    st.session_state["current_user"] = user

    st.title("🧾 Tối ưu nháp VAT")
    st.caption("App tra cứu và đề xuất phân bổ nháp VAT — không dùng AI, không trừ tồn thật.")

    if config.auth_mode == "google" and not user.is_authenticated:
        st.warning(
            "AUTH_MODE=google nhưng chưa đăng nhập. Phần đăng nhập Google OpenID Connect "
            "chưa được triển khai đầy đủ trong phiên bản này (dự kiến Milestone 5). "
            "Có thể đặt AUTH_MODE=none để phát triển/kiểm thử ở local."
        )
        return

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Thông tin dữ liệu hiện tại")
        meta = get_current_version_metadata()
        if meta is None:
            st.info(
                "Chưa có dữ liệu hiện tại. Vào trang **Quản lý dữ liệu** (dành cho Admin) "
                "để upload file Excel đầu tiên."
            )
        else:
            st.write(f"**Tên file gốc:** {meta.original_file_name}")
            st.write(f"**Thời điểm upload:** {meta.uploaded_at}")
            st.write(f"**Số dòng Gộp VAT:** {meta.gop_vat_row_count:,}")
            st.write(f"**Số dòng Khớp mã:** {meta.khop_ma_row_count:,}")
            st.write(f"**Hash (SHA-256):** `{meta.sha256[:16]}...`")

    with col2:
        st.subheader("Vai trò hiện tại")
        role_label = "Admin" if user.role == Role.ADMIN else "User"
        st.write(f"**Vai trò:** {role_label}")
        st.write(f"**Chế độ đăng nhập:** `{config.auth_mode}`")
        st.markdown(
            "- Trang **Xử lý hóa đơn**: dán hóa đơn, tạo kết quả, xuất Excel, in.\n"
            "- Trang **Tra cứu nguồn**: tra một hoặc nhiều mã/tên sản phẩm, xem mọi nguồn còn tồn dương theo tồn tăng dần.\n"
            "- Trang **Quản lý dữ liệu** *(Admin)*: upload, xác nhận, khôi phục phiên bản.\n"
            "- Trang **Kiểm tra dữ liệu**: thống kê lỗi/cảnh báo dữ liệu nguồn.\n"
            "- Trang **Cấu hình**: xem trọng số so khớp tên, tie-break nguồn..."
        )

    st.divider()
    st.caption(
        "Dùng thanh điều hướng bên trái để chuyển trang. "
        "App không thay đổi sheet 'Gộp VAT'/'Khớp mã' và không ghi kết quả vào file nguồn."
    )


if __name__ == "__main__":
    main()
