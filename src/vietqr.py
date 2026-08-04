"""Tạo mã QR thanh toán VietQR cho hóa đơn.

Dùng VietQR Quick Link API (``img.vietqr.io``) — không cần đăng ký hay API key,
chỉ cần build đúng URL ảnh QR. Mỗi nguồn (NGUỒN) được cấu hình trỏ tới một tài
khoản ngân hàng khác nhau qua ``config.vietqr.source_account_map``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import quote

from src.config import AppConfig, VietQrAccount
from src.invoice_allocation import InvoiceAllocationLine
from src.normalization import normalize_code_for_match, to_float_or_none

_VIETQR_IMAGE_BASE = "https://img.vietqr.io/image"

# Tên file hóa đơn xuất từ phần mềm bán hàng luôn chứa "HD" theo sau là số,
# ví dụ: ChiTietHoaDon_HD018699_KV01082026-162300-154.xlsx -> "HD018699".
_INVOICE_CODE_PATTERN = re.compile(r"HD\d+", re.IGNORECASE)


@dataclass
class SourceAmount:
    """Tổng tiền theo Giá bán và Giá nhập của một nguồn (hoặc gộp tất cả nguồn).

    - ``tong_gia_ban``: tổng theo Giá bán (đã gồm VAT) — dùng cho QR hóa đơn KHÔNG VAT.
    - ``tong_gia_nhap``: tổng theo Giá nhập (Giá bán/(1+%VAT), trước VAT) — dùng cho QR hóa đơn CÓ VAT.
    """

    nguon: str
    so_dong: int
    tong_gia_ban: float
    tong_gia_nhap: float
    thieu_don_gia: bool = False


def extract_invoice_code(file_name: str) -> str | None:
    """Trích mã hóa đơn (dạng HD + số) từ tên file hóa đơn."""

    if not file_name:
        return None
    match = _INVOICE_CODE_PATTERN.search(file_name)
    return match.group(0).upper() if match else None


def extract_invoice_codes(file_names: list[str]) -> list[str]:
    """Trích mã hóa đơn từ nhiều tên file, giữ thứ tự và loại trùng."""

    codes: list[str] = []
    for name in file_names or []:
        code = extract_invoice_code(name)
        if code and code not in codes:
            codes.append(code)
    return codes


def get_account_for_source(nguon: str, config: AppConfig) -> VietQrAccount | None:
    """Tìm tài khoản ngân hàng được cấu hình cho một nguồn (không phân biệt hoa/thường, dấu)."""

    target = normalize_code_for_match(nguon)
    for source_name, account_key in (config.vietqr.source_account_map or {}).items():
        if normalize_code_for_match(source_name) == target:
            return config.vietqr.accounts.get(account_key)
    return None


def compute_source_amounts(lines: list[InvoiceAllocationLine]) -> dict[str, SourceAmount]:
    """Gộp các dòng kết quả theo NGUỒN, tính tổng theo Giá bán và Giá nhập của từng nguồn."""

    totals: dict[str, SourceAmount] = {}
    for line in lines or []:
        amount = totals.setdefault(
            line.nguon, SourceAmount(nguon=line.nguon, so_dong=0, tong_gia_ban=0.0, tong_gia_nhap=0.0)
        )
        gia_ban = to_float_or_none(line.gia_ban)
        amount.so_dong += 1
        if gia_ban is None or line.gia_nhap is None:
            amount.thieu_don_gia = True
            continue
        amount.tong_gia_ban += gia_ban * line.sl_phan_bo
        amount.tong_gia_nhap += line.gia_nhap * line.sl_phan_bo
    return totals


def compute_total_amount(lines: list[InvoiceAllocationLine]) -> SourceAmount:
    """Gộp toàn bộ dòng kết quả bất kể nguồn, dùng cho QR hóa đơn KHÔNG VAT (1 QR duy nhất)."""

    total = SourceAmount(nguon="TẤT CẢ NGUỒN", so_dong=0, tong_gia_ban=0.0, tong_gia_nhap=0.0)
    for line in lines or []:
        gia_ban = to_float_or_none(line.gia_ban)
        total.so_dong += 1
        if gia_ban is None or line.gia_nhap is None:
            total.thieu_don_gia = True
            continue
        total.tong_gia_ban += gia_ban * line.sl_phan_bo
        total.tong_gia_nhap += line.gia_nhap * line.sl_phan_bo
    return total


def build_vietqr_image_url(
    account: VietQrAccount,
    *,
    amount: float,
    add_info: str,
    template: str = "compact2",
) -> str:
    """Build URL ảnh QR theo VietQR Quick Link API (không cần API key)."""

    amount_str = str(int(round(amount))) if amount and amount > 0 else ""
    query = f"amount={amount_str}&addInfo={quote(add_info or '')}"
    if account.account_name:
        query += f"&accountName={quote(account.account_name)}"
    return f"{_VIETQR_IMAGE_BASE}/{account.bank_id}-{account.account_no}-{template}.png?{query}"
