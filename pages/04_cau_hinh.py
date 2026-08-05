"""Trang hiển thị cấu hình chỉ đọc từ config/settings.yaml."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.session import get_config, get_current_version_metadata
from ui import apply_global_styles, render_admin_top_bar

st.set_page_config(
    page_title="Cấu hình", page_icon="⚙️", layout="wide", initial_sidebar_state="expanded"
)
apply_global_styles()

metadata = get_current_version_metadata()
render_admin_top_bar(
    title="Cấu hình",
    icon="⚙️",
    description="Giải thích các quy tắc đang được ứng dụng sử dụng. Trang này chỉ đọc và không ghi file cấu hình.",
    meta=metadata,
)

st.info(
    "Cấu hình hiện được đọc từ `config/settings.yaml`. Muốn thay đổi cần sửa file trên máy chủ "
    "và khởi động lại ứng dụng; trang này không có chức năng lưu."
)

config = get_config()
name_match = config.name_match

with st.expander("So khớp tên sản phẩm", expanded=True):
    st.caption(
        "Điểm so khớp được tính deterministic từ bốn nguồn tên, sau đó cộng hoặc trừ các hệ số token."
    )
    name_match_df = pd.DataFrame(
        [
            ("Tên SP người dùng nhập", name_match.weight_user_ten_sp, "Trọng số của tên trong hóa đơn."),
            ("Tên SP trong Khớp mã", name_match.weight_khopma_ten_sp, "Trọng số của tên từ bảng mapping."),
            ("TÊN VAT KIOT", name_match.weight_ten_vat_kiot, "Trọng số tên VAT từ dữ liệu tồn."),
            ("Tên trước VAT đã làm sạch", name_match.weight_ten_truoc_vat, "Tên đã bỏ phần giá và hậu tố VAT."),
            ("Thưởng token số/kích thước", name_match.number_token_bonus, "Cộng điểm khi token số hoặc kích thước trùng."),
            ("Thưởng kích thước trùng", name_match.size_token_bonus, "Hệ số thưởng kích thước theo cấu hình hiện tại."),
            ("Phạt token số mâu thuẫn", name_match.number_conflict_penalty, "Trừ điểm khi hai tên có số không tương thích."),
            ("Phạt khác biến thể", name_match.variant_conflict_penalty, "Trừ điểm cho khác biệt biến thể rõ ràng."),
            ("Ngưỡng cần kiểm tra thủ công", name_match.review_threshold, "Điểm thấp hơn ngưỡng sẽ được đánh dấu rà soát."),
        ],
        columns=["Tham số", "Giá trị", "Ý nghĩa"],
    )
    st.dataframe(
        name_match_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Tham số": st.column_config.TextColumn(width="large"),
            "Giá trị": st.column_config.NumberColumn(width="small", format="%.2f"),
            "Ý nghĩa": st.column_config.TextColumn(width="large"),
        },
    )

with st.expander("Ưu tiên nguồn"):
    st.caption(
        "Danh sách này chỉ được dùng làm tie-break khi các nguồn có cùng mức coverage; "
        "không thay thế thuật toán xếp hạng hiện tại."
    )
    if config.source_tiebreak_priority:
        priority_df = pd.DataFrame(
            [
                {"Thứ tự": index, "Nguồn": source}
                for index, source in enumerate(config.source_tiebreak_priority, start=1)
            ]
        )
        st.dataframe(
            priority_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Thứ tự": st.column_config.NumberColumn(width="small", format="%d"),
                "Nguồn": st.column_config.TextColumn(width="large"),
            },
        )
    else:
        st.caption("Chưa cấu hình; hệ thống dùng thứ tự tên nguồn tăng dần khi cần tie-break.")

with st.expander("Quy tắc số lượng và tồn kho"):
    quantity_columns = st.columns(2, gap="medium")
    with quantity_columns[0]:
        st.markdown("**Số lượng lẻ**")
        st.write("Cho phép" if config.allow_fractional_sl else "Không cho phép")
        st.caption("Khi tắt, SL hóa đơn phải là số nguyên dương.")
    with quantity_columns[1]:
        st.markdown("**Số chữ số thập phân của GIÁ NHÁP**")
        st.write(config.gia_nhap_decimal_places)
        st.caption("Chỉ ảnh hưởng bước làm tròn giá nhập trong kết quả.")
    st.warning(
        "Dòng có tồn không dương vẫn bị loại khỏi danh sách ứng viên theo logic hiện tại. "
        "Trang này không thay đổi quy tắc đó."
    )

with st.expander("Lưu trữ phiên bản"):
    st.write(f"**Số phiên bản giữ lại tối đa:** {config.max_versions_kept}")
    st.caption(
        "Các phiên bản chỉ được giữ trong bộ nhớ của phiên trình duyệt hiện tại và sẽ mất khi phiên kết thúc. "
        "Người dùng khác không thể truy cập dữ liệu này."
    )

with st.expander("Thanh toán QR (VietQR)"):
    st.caption(
        "Mỗi nguồn được gán một tài khoản ngân hàng để tạo mã QR ở trang Xử lý hóa đơn. "
        "Sửa mapping trong `config/settings.yaml` (mục `vietqr`)."
    )
    if config.vietqr.source_account_map:
        vietqr_rows = []
        for source_name, account_key in config.vietqr.source_account_map.items():
            account = config.vietqr.accounts.get(account_key)
            vietqr_rows.append(
                {
                    "Nguồn": source_name,
                    "Tài khoản": account_key,
                    "Ngân hàng": account.bank_id if account else "—",
                    "Số tài khoản": account.account_no if account else "—",
                }
            )
        st.dataframe(
            pd.DataFrame(vietqr_rows),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Nguồn": st.column_config.TextColumn(width="medium"),
                "Tài khoản": st.column_config.TextColumn(width="small"),
                "Ngân hàng": st.column_config.TextColumn(width="small"),
                "Số tài khoản": st.column_config.TextColumn(width="medium"),
            },
        )
    else:
        st.caption("Chưa cấu hình mapping nguồn → tài khoản.")

with st.expander("Cấu hình kỹ thuật"):
    st.write(f"**Chế độ đăng nhập:** `{config.auth_mode}`")
    st.write("**Backend lưu trữ hiện tại:** SessionMemoryStorageAdapter")
    st.write("**Vị trí lưu trữ:** Bộ nhớ riêng của phiên người dùng (không ghi file upload lên server)")
    st.write("**Nguồn cấu hình:** `config/settings.yaml` và các biến môi trường được hỗ trợ")
    st.caption("Không hiển thị secret, khóa truy cập hoặc danh sách email trên giao diện này.")
