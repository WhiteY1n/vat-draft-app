"""Đọc file hóa đơn chi tiết (.xlsx) xuất từ phần mềm bán hàng.

Trích các cột Mã hàng/Tên hàng/Số lượng/Giá bán thành danh sách dòng theo
đúng hợp đồng 4 cột (Mã SP, Tên SP, SL, Giá bán) mà luồng dán tay đang dùng,
để hai luồng nhập liệu (dán tay và tải file) có thể tái dùng cùng logic xử lý
phía sau. Không ghi hoặc sửa file nguồn, chỉ đọc.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field

import openpyxl

HEADER_ALIASES: dict[str, set[str]] = {
    "ma_hang": {"mã hàng", "ma hang", "mã sp", "ma sp"},
    "ten_hang": {"tên hàng", "ten hang", "tên sp", "ten sp"},
    "so_luong": {"số lượng", "so luong", "sl"},
    "gia_ban": {"giá bán", "gia ban"},
}

MAX_HEADER_SCAN_ROWS = 5


@dataclass
class InvoiceFileParseResult:
    file_name: str
    rows: list[list[str]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _find_header(ws) -> tuple[int | None, dict[str, int]]:
    for row_idx, row in enumerate(
        ws.iter_rows(min_row=1, max_row=MAX_HEADER_SCAN_ROWS, values_only=True), start=1
    ):
        if row is None:
            continue
        normalized = [str(v).strip().casefold() if v is not None else "" for v in row]
        col_map: dict[str, int] = {}
        for key, aliases in HEADER_ALIASES.items():
            for i, val in enumerate(normalized):
                if val in aliases:
                    col_map[key] = i
                    break
        if "ma_hang" in col_map and "ten_hang" in col_map:
            return row_idx, col_map
    return None, {}


def parse_invoice_file_bytes(file_bytes: bytes, file_name: str) -> InvoiceFileParseResult:
    """Đọc một file hóa đơn .xlsx trong bộ nhớ, trả về danh sách dòng đã chuẩn hóa."""

    result = InvoiceFileParseResult(file_name=file_name)

    if not file_name.lower().endswith(".xlsx"):
        result.errors.append(f"{file_name}: chỉ hỗ trợ định dạng .xlsx.")
        return result

    try:
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True, read_only=True)
    except Exception as exc:  # noqa: BLE001 - báo lỗi cụ thể cho người dùng
        result.errors.append(f"{file_name}: không đọc được file ({exc}).")
        return result

    if not wb.worksheets:
        result.errors.append(f"{file_name}: file không có sheet dữ liệu.")
        return result

    ws = wb.worksheets[0]
    header_row_idx, col_map = _find_header(ws)
    if header_row_idx is None:
        result.errors.append(
            f"{file_name}: không tìm thấy cột 'Mã hàng'/'Tên hàng' trong file."
        )
        return result

    for row in ws.iter_rows(min_row=header_row_idx + 1, values_only=True):
        if row is None:
            continue

        ma_idx = col_map["ma_hang"]
        ten_idx = col_map["ten_hang"]
        ma_hang = row[ma_idx] if ma_idx < len(row) else None
        if ma_hang is None or str(ma_hang).strip() == "":
            # Dòng tổng ("Tổng số lượng", "Tổng cộng"...) hoặc dòng trống cuối file:
            # các dòng này luôn để trống cột Mã hàng nên bỏ qua an toàn.
            continue

        ten_hang = row[ten_idx] if ten_idx < len(row) else None

        so_luong = None
        if "so_luong" in col_map and col_map["so_luong"] < len(row):
            so_luong = row[col_map["so_luong"]]

        gia_ban = None
        if "gia_ban" in col_map and col_map["gia_ban"] < len(row):
            gia_ban = row[col_map["gia_ban"]]

        result.rows.append(
            [
                str(ma_hang).strip(),
                str(ten_hang).strip() if ten_hang is not None else "",
                "" if so_luong is None else str(so_luong).strip(),
                "" if gia_ban is None else str(gia_ban).strip(),
            ]
        )

    if not result.rows:
        result.errors.append(f"{file_name}: không có dòng sản phẩm nào hợp lệ.")

    return result


def parse_invoice_files(files: list[tuple[bytes, str]]) -> tuple[list[list[str]], list[str]]:
    """Đọc nhiều file hóa đơn, gộp toàn bộ dòng sản phẩm lại thành một danh sách."""

    all_rows: list[list[str]] = []
    all_errors: list[str] = []
    for file_bytes, file_name in files:
        parsed = parse_invoice_file_bytes(file_bytes, file_name)
        all_rows.extend(parsed.rows)
        all_errors.extend(parsed.errors)
    return all_rows, all_errors
