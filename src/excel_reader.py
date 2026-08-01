"""Đọc và kiểm tra cấu trúc file Excel nguồn (sheet `Gộp VAT` và `Khớp mã`).

Không được ghi hoặc sửa file nguồn. Module này chỉ đọc.
"""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass, field
from pathlib import Path

import openpyxl

from src.models import DataWarning, MappingRow, StockRow
from src.normalization import (
    GOP_VAT_COLUMN_ALIASES,
    KHOP_MA_COLUMN_ALIASES,
    normalize_code,
    normalize_code_for_match,
    resolve_column_name,
    to_float_or_none,
)

REQUIRED_SHEET_GOP_VAT = "Gộp VAT"
REQUIRED_SHEET_KHOP_MA = "Khớp mã"
OPTIONAL_SHEET_YEU_CAU = "Yêu cầu"


@dataclass
class SheetCheckSummary:
    sheet_name: str
    total_data_rows: int = 0
    blank_ma_count: int = 0
    blank_ma_vat_count: int = 0
    invalid_ton_count: int = 0
    zero_or_negative_ton_count: int = 0
    duplicate_ma_sp_multi_vat_count: int = 0


@dataclass
class WorkbookCheckResult:
    is_valid: bool
    file_name: str
    file_size_bytes: int
    sha256: str
    errors: list[str] = field(default_factory=list)
    gop_vat_summary: SheetCheckSummary | None = None
    khop_ma_summary: SheetCheckSummary | None = None
    stock_rows: list[StockRow] = field(default_factory=list)
    mapping_rows: list[MappingRow] = field(default_factory=list)
    warnings: list[DataWarning] = field(default_factory=list)


def compute_sha256(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _iter_rows(ws, header_map: dict[str, int]):
    # Dùng iter_rows(values_only=True) thay vì truy cập từng cell riêng lẻ:
    # nhanh hơn nhiều lần trên worksheet read_only với hàng nghìn dòng.
    row_idx = 1
    for row in ws.iter_rows(min_row=2, values_only=True):
        row_idx += 1
        if row is None or all(v is None or str(v).strip() == "" for v in row):
            continue
        yield row_idx, list(row)


def _get(row: list, header_map: dict[str, int], key: str):
    idx = header_map.get(key)
    if idx is None or idx >= len(row):
        return None
    return row[idx]


def read_and_validate_workbook(path: str | Path, file_name: str | None = None) -> WorkbookCheckResult:
    """Đọc và kiểm tra toàn bộ workbook. Không ném exception cho lỗi nghiệp vụ
    (mã trống, tồn âm...) — các lỗi này được đưa vào `errors`/`warnings` để
    hiển thị cho người dùng. Chỉ ném exception nếu file không mở được.
    """

    path = Path(path)
    file_name = file_name or path.name
    file_size = path.stat().st_size
    sha256 = compute_sha256(path)

    errors: list[str] = []

    if path.suffix.lower() != ".xlsx":
        errors.append("File không phải định dạng .xlsx.")
        return WorkbookCheckResult(
            is_valid=False,
            file_name=file_name,
            file_size_bytes=file_size,
            sha256=sha256,
            errors=errors,
        )

    return _read_and_validate_workbook_source(
        path, file_name=file_name, file_size=file_size, sha256=sha256
    )


def read_and_validate_workbook_bytes(
    file_bytes: bytes, file_name: str
) -> WorkbookCheckResult:
    """Validate an uploaded workbook entirely in memory, without a temporary file."""

    return _read_and_validate_workbook_source(
        io.BytesIO(file_bytes),
        file_name=file_name,
        file_size=len(file_bytes),
        sha256=hashlib.sha256(file_bytes).hexdigest(),
    )


def _read_and_validate_workbook_source(
    source, *, file_name: str, file_size: int, sha256: str
) -> WorkbookCheckResult:
    errors: list[str] = []
    if Path(file_name).suffix.lower() != ".xlsx":
        errors.append("File không phải định dạng .xlsx.")
        return WorkbookCheckResult(
            is_valid=False,
            file_name=file_name,
            file_size_bytes=file_size,
            sha256=sha256,
            errors=errors,
        )

    try:
        wb = openpyxl.load_workbook(source, data_only=True, read_only=True)
    except Exception as exc:  # noqa: BLE001 - báo lỗi cụ thể cho người dùng
        errors.append(f"Không đọc được workbook: {exc}")
        return WorkbookCheckResult(
            is_valid=False,
            file_name=file_name,
            file_size_bytes=file_size,
            sha256=sha256,
            errors=errors,
        )

    if REQUIRED_SHEET_GOP_VAT not in wb.sheetnames:
        errors.append(f"Thiếu sheet bắt buộc: {REQUIRED_SHEET_GOP_VAT}")
    if REQUIRED_SHEET_KHOP_MA not in wb.sheetnames:
        errors.append(f"Thiếu sheet bắt buộc: {REQUIRED_SHEET_KHOP_MA}")

    if errors:
        return WorkbookCheckResult(
            is_valid=False,
            file_name=file_name,
            file_size_bytes=file_size,
            sha256=sha256,
            errors=errors,
        )

    stock_rows, gop_vat_summary, gop_vat_errors, warnings = _read_gop_vat(wb[REQUIRED_SHEET_GOP_VAT])
    mapping_rows, khop_ma_summary, khop_ma_errors = _read_khop_ma(wb[REQUIRED_SHEET_KHOP_MA])

    errors.extend(gop_vat_errors)
    errors.extend(khop_ma_errors)

    return WorkbookCheckResult(
        is_valid=len(errors) == 0,
        file_name=file_name,
        file_size_bytes=file_size,
        sha256=sha256,
        errors=errors,
        gop_vat_summary=gop_vat_summary,
        khop_ma_summary=khop_ma_summary,
        stock_rows=stock_rows,
        mapping_rows=mapping_rows,
        warnings=warnings,
    )


def _read_gop_vat(ws):
    header_row = [c.value for c in next(ws.iter_rows(min_row=1, max_row=1))]
    header_map = resolve_column_name(header_row, GOP_VAT_COLUMN_ALIASES)

    missing = [c for c in GOP_VAT_COLUMN_ALIASES if c not in header_map]
    errors = []
    if missing:
        errors.append(
            f"Sheet '{REQUIRED_SHEET_GOP_VAT}' thiếu cột bắt buộc: {', '.join(missing)}"
        )
        return [], SheetCheckSummary(sheet_name=REQUIRED_SHEET_GOP_VAT), errors, []

    summary = SheetCheckSummary(sheet_name=REQUIRED_SHEET_GOP_VAT)
    stock_rows: list[StockRow] = []
    warnings: list[DataWarning] = []

    from collections import defaultdict

    vat_to_groups: dict[str, set] = defaultdict(set)

    for row_idx, row in _iter_rows(ws, header_map):
        summary.total_data_rows += 1

        ma_vat_kiot = normalize_code(_get(row, header_map, "MÃ VAT KIOT"))
        ten_ke_toan = normalize_code(_get(row, header_map, "TÊN KẾ TOÁN"))
        don_vi_tinh = normalize_code(_get(row, header_map, "Đơn vị tính"))

        if not ma_vat_kiot:
            summary.blank_ma_vat_count += 1

        ton_co_the_nhap_raw = _get(row, header_map, "TỒN CÓ THỂ NHÁP")
        ton_co_the_nhap = to_float_or_none(ton_co_the_nhap_raw)
        if ton_co_the_nhap_raw not in (None, "") and ton_co_the_nhap is None:
            summary.invalid_ton_count += 1
            warnings.append(
                DataWarning(
                    row_index=row_idx,
                    warning_type="ton_khong_hop_le",
                    detail=(
                        f"Dòng {row_idx}: TỒN CÓ THỂ NHÁP='{ton_co_the_nhap_raw}' "
                        "không chuyển được thành số."
                    ),
                )
            )
            continue  # không đưa dòng lỗi số liệu vào danh sách ứng viên

        ton_final = ton_co_the_nhap if ton_co_the_nhap is not None else 0.0
        if ton_final <= 0:
            summary.zero_or_negative_ton_count += 1

        tong_dang_nhap = to_float_or_none(_get(row, header_map, "TỔNG ĐANG NHÁP"))
        tong_dang_nhap = tong_dang_nhap if tong_dang_nhap is not None else 0.0

        stock_row = StockRow(
            row_index=row_idx,
            nguon=normalize_code(_get(row, header_map, "NGUỒN")),
            ma_kiot_dai_dien=normalize_code(_get(row, header_map, "Mã kiot đại diện")),
            ten_kiot_dai_dien=normalize_code(_get(row, header_map, "Tên kiot đại diện")),
            ma_vat_kiot=ma_vat_kiot,
            ten_vat_kiot=normalize_code(_get(row, header_map, "TÊN VAT KIOT")),
            ten_ke_toan=ten_ke_toan,
            don_vi_tinh=don_vi_tinh,
            ton_dau_ngay=to_float_or_none(_get(row, header_map, "TỒN ĐẦU NGÀY")),
            gia_ban=to_float_or_none(_get(row, header_map, "GIÁ BÁN")),
            thue_vat=to_float_or_none(_get(row, header_map, "THUẾ VAT")),
            thue_nk=to_float_or_none(_get(row, header_map, "THUẾ NK")),
            tong_thue_mat=to_float_or_none(_get(row, header_map, "TỔNG THUẾ MẤT")),
            tong_dang_nhap=tong_dang_nhap,
            ton_co_the_nhap=ton_final,
            ma_vat_kiot_norm=normalize_code_for_match(ma_vat_kiot),
            ten_ke_toan_norm=normalize_code_for_match(ten_ke_toan),
            don_vi_tinh_norm=normalize_code_for_match(don_vi_tinh),
        )
        stock_rows.append(stock_row)

        if ma_vat_kiot:
            vat_to_groups[stock_row.ma_vat_kiot_norm].add((ten_ke_toan.strip(), don_vi_tinh.strip()))

    return stock_rows, summary, errors, warnings


def _read_khop_ma(ws):
    header_row = [c.value for c in next(ws.iter_rows(min_row=1, max_row=1))]
    header_map = resolve_column_name(header_row, KHOP_MA_COLUMN_ALIASES)

    missing = [c for c in KHOP_MA_COLUMN_ALIASES if c not in header_map]
    errors = []
    if missing:
        errors.append(
            f"Sheet '{REQUIRED_SHEET_KHOP_MA}' thiếu cột bắt buộc: {', '.join(missing)}"
        )
        return [], SheetCheckSummary(sheet_name=REQUIRED_SHEET_KHOP_MA), errors

    summary = SheetCheckSummary(sheet_name=REQUIRED_SHEET_KHOP_MA)
    mapping_rows: list[MappingRow] = []

    for row_idx, row in _iter_rows(ws, header_map):
        summary.total_data_rows += 1

        ma_sp = normalize_code(_get(row, header_map, "Mã SP"))
        ma_vat_kiot = normalize_code(_get(row, header_map, "Mã vat kiot"))

        if not ma_sp:
            summary.blank_ma_count += 1
        if not ma_vat_kiot:
            summary.blank_ma_vat_count += 1

        mapping_rows.append(
            MappingRow(
                row_index=row_idx,
                ma_sp=ma_sp,
                ten_sp=normalize_code(_get(row, header_map, "Tên SP")),
                ma_vat_kiot=ma_vat_kiot,
                ten_truoc_vat=normalize_code(
                    _get(row, header_map, "Tên trước (Giá đầu  - Giá cuối) (VAT)")
                ),
                ma_sp_norm=normalize_code_for_match(ma_sp),
                ma_vat_kiot_norm=normalize_code_for_match(ma_vat_kiot),
            )
        )

    from collections import defaultdict

    vat_by_ma_sp: dict[str, set] = defaultdict(set)
    for m in mapping_rows:
        if m.ma_sp_norm:
            vat_by_ma_sp[m.ma_sp_norm].add(m.ma_vat_kiot_norm)
    summary.duplicate_ma_sp_multi_vat_count = sum(1 for v in vat_by_ma_sp.values() if len(v) > 1)

    return mapping_rows, summary, errors
