"""Đọc hóa đơn GTGT điện tử dạng PDF (bản thể hiện, có lớp text — không phải
ảnh scan) để tự động điền số tiền và gợi ý tài khoản nhận tiền trên trang Tạo
QR, thay vì người dùng phải gõ tay số tiền và lọc thủ công giữa nhiều tài
khoản.

Chỉ hỗ trợ PDF có lớp text (loại xuất trực tiếp từ phần mềm hóa đơn điện tử,
như mẫu "Bản thể hiện của hóa đơn điện tử"). PDF là ảnh scan/chụp thuần túy
không có lớp text sẽ báo lỗi để người dùng nhập tay.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass

from src.vietqr import parse_amount_input

# Các nhãn trên hóa đơn mẫu (Thông tư/mẫu hóa đơn điện tử phổ biến) đều có dạng
# "Tên nhãn tiếng Việt(Tên nhãn tiếng Anh): giá trị" trên một dòng.
_SELLER_RE = re.compile(r"Đơn vị bán hàng\s*\(Seller\)\s*:\s*(.+)")
_TOTAL_PAYMENT_RE = re.compile(r"Tổng cộng tiền thanh toán\s*\(Total payment\)\s*:\s*([\d.,]+)")
_TOTAL_BEFORE_VAT_RE = re.compile(r"Cộng tiền hàng\s*\(Total amount\)\s*:\s*([\d.,]+)")
_VAT_AMOUNT_RE = re.compile(r"Tiền thuế GTGT\s*\(VAT amount\)\s*:\s*([\d.,]+)")
_SERIAL_RE = re.compile(r"Ký hiệu\s*\(Serial No\)\s*:\s*(\S+)")


@dataclass
class ParsedInvoice:
    """Kết quả trích xuất từ một file hóa đơn PDF."""

    seller_name: str = ""
    total_payment: int | None = None
    total_before_vat: int | None = None
    vat_amount: int | None = None
    serial_no: str = ""
    raw_text: str = ""
    error: str | None = None


def _extract_text(file_bytes: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(file_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def parse_invoice_text(text: str) -> ParsedInvoice:
    """Trích thông tin từ text đã đọc được của hóa đơn (tách riêng để test không
    cần file PDF thật)."""

    if not text or not text.strip():
        return ParsedInvoice(
            raw_text=text or "",
            error=(
                "Không tìm thấy lớp text trong PDF (có thể là ảnh scan/chụp) — "
                "vui lòng nhập số tiền và chọn tài khoản thủ công."
            ),
        )

    seller_match = _SELLER_RE.search(text)
    total_match = _TOTAL_PAYMENT_RE.search(text)
    before_vat_match = _TOTAL_BEFORE_VAT_RE.search(text)
    vat_match = _VAT_AMOUNT_RE.search(text)
    serial_match = _SERIAL_RE.search(text)

    seller_name = seller_match.group(1).strip() if seller_match else ""
    # Phòng trường hợp PDF không xuống dòng đúng chỗ và dính vào nhãn tiếp theo.
    seller_name = re.split(r"Mã số thuế", seller_name)[0].strip()

    parsed = ParsedInvoice(
        seller_name=seller_name,
        total_payment=parse_amount_input(total_match.group(1)) if total_match else None,
        total_before_vat=parse_amount_input(before_vat_match.group(1)) if before_vat_match else None,
        vat_amount=parse_amount_input(vat_match.group(1)) if vat_match else None,
        serial_no=serial_match.group(1).strip() if serial_match else "",
        raw_text=text,
    )
    if not parsed.seller_name and parsed.total_payment is None:
        parsed.error = (
            "Không nhận diện được nội dung hóa đơn (không đúng mẫu hóa đơn GTGT "
            "điện tử) — vui lòng nhập số tiền và chọn tài khoản thủ công."
        )
    return parsed


def parse_invoice_pdf(file_bytes: bytes) -> ParsedInvoice:
    """Đọc file PDF hóa đơn (bytes) và trích thông tin cần thiết cho trang Tạo QR."""

    try:
        text = _extract_text(file_bytes)
    except Exception as exc:  # noqa: BLE001 - lỗi đọc file bất thường, hiển thị cho người dùng
        return ParsedInvoice(error=f"Không đọc được file PDF: {exc}")
    return parse_invoice_text(text)
