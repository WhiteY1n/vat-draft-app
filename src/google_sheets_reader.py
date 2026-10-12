"""Fetch và parse CSV từ Google Sheets công khai, trả về WorkbookCheckResult.

Module này thay thế hoàn toàn việc upload file Excel thủ công.
Dữ liệu được fetch từ Google Sheets qua URL export CSV, sau đó parse
thành các domain model (StockRow, MappingRow) giống như excel_reader.py.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime
from io import StringIO
from typing import Tuple

import pandas as pd
import requests

from src.config import DEFAULT_GOP_VAT_COLUMNS, DEFAULT_KHOP_MA_COLUMNS
from src.excel_reader import SheetCheckSummary, WorkbookCheckResult
from src.models import DataWarning, MappingRow, StockRow
from src.normalization import (
    normalize_code,
    normalize_code_for_match,
    to_float_or_none,
)

logger = logging.getLogger(__name__)

_EXPORT_URL = (
    "https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
)


# ---------------------------------------------------------------------------
# Lớp đọc dữ liệu từ Google Sheets
# ---------------------------------------------------------------------------


class GoogleSheetsReader:
    """Đọc dữ liệu từ Google Sheets công khai qua CSV export."""

    def __init__(self, sheet_id: str, gid_gop_vat: int, gid_khop_ma: int) -> None:
        self.sheet_id = sheet_id
        self.gid_gop_vat = gid_gop_vat
        self.gid_khop_ma = gid_khop_ma

    def _build_url(self, gid: int) -> str:
        return _EXPORT_URL.format(sheet_id=self.sheet_id, gid=gid)

    def _fetch_csv(self, gid: int, sheet_name: str, skiprows: int = 0) -> pd.DataFrame:
        """Fetch một sheet, trả về DataFrame KHÔNG có header (cột đánh số 0,1,2...,
        tương ứng A,B,C,...). `skiprows` là số dòng đầu (tiêu đề) cần bỏ qua.
        Raise Exception nếu thất bại."""
        url = self._build_url(gid)
        try:
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
        except requests.exceptions.Timeout:
            raise Exception(
                f"❌ Fetch '{sheet_name}' bị timeout (quá 15 giây). "
                "Kiểm tra kết nối mạng hoặc thử lại."
            )
        except requests.exceptions.RequestException as exc:
            raise Exception(
                f"❌ Lỗi mạng khi fetch '{sheet_name}': {exc}"
            )

        try:
            df = pd.read_csv(StringIO(resp.text), header=None, skiprows=skiprows)
        except pd.errors.ParserError as exc:
            raise Exception(f"❌ Lỗi parse CSV '{sheet_name}': {exc}")

        logger.info("✅ Fetch '%s' thành công: %d dòng", sheet_name, len(df))
        return df

    def fetch_all(self) -> Tuple[pd.DataFrame, pd.DataFrame, str]:
        """Fetch cả 2 sheets. Trả về (df_gop_vat, df_khop_ma, timestamp)."""
        # Gộp VAT: dòng 1 là header. Khớp mã: dòng 1 là tiêu đề tổng
        # 'CHECK TỒN BÊN SHEET VAT', dòng 2 mới là header thực -> dữ liệu từ dòng 3.
        df_gop_vat = self._fetch_csv(self.gid_gop_vat, "Gộp VAT", skiprows=1)
        df_khop_ma = self._fetch_csv(self.gid_khop_ma, "Khớp mã", skiprows=2)
        timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        return df_gop_vat, df_khop_ma, timestamp


# ---------------------------------------------------------------------------
# Parse DataFrame → domain models (tái sử dụng logic từ excel_reader)
# ---------------------------------------------------------------------------


def column_letter_to_index(letter: str) -> int:
    """'A' -> 0, 'B' -> 1, ..., 'Z' -> 25, 'AA' -> 26."""
    text = str(letter).strip().upper()
    if not text.isalpha():
        raise ValueError(f"Tên cột Excel không hợp lệ: '{letter}'")
    index = 0
    for ch in text:
        index = index * 26 + (ord(ch) - ord("A") + 1)
    return index - 1


def _build_col_map(
    df: pd.DataFrame, letters: dict[str, str]
) -> tuple[dict[str, int], list[str]]:
    """Tên chuẩn -> chỉ số cột (0-based). Trả thêm danh sách cột nằm ngoài sheet."""
    col_map: dict[str, int] = {}
    missing: list[str] = []
    for canonical, letter in letters.items():
        idx = column_letter_to_index(letter)
        if idx < df.shape[1]:
            col_map[canonical] = idx
        else:
            missing.append(f"{canonical} (cột {str(letter).strip().upper()})")
    return col_map, missing


def _parse_gop_vat(df: pd.DataFrame, letters: dict[str, str]):
    """Parse DataFrame Gộp VAT → (stock_rows, summary, errors, warnings)."""
    col_map, missing = _build_col_map(df, letters)
    errors: list[str] = []
    if missing:
        errors.append(f"Sheet 'Gộp VAT' thiếu cột (ngoài phạm vi sheet): {', '.join(missing)}")
        return [], SheetCheckSummary(sheet_name="Gộp VAT"), errors, []

    summary = SheetCheckSummary(sheet_name="Gộp VAT")
    stock_rows: list[StockRow] = []
    warnings: list[DataWarning] = []

    for row_idx, (_, row) in enumerate(df.iterrows(), start=2):
        # Bỏ qua dòng trống hoàn toàn
        if row.isna().all():
            continue

        def gcol(canonical: str):
            actual = col_map.get(canonical)
            return row.iloc[actual] if actual is not None else None

        summary.total_data_rows += 1

        ma_vat_kiot = normalize_code(gcol("MÃ VAT KIOT"))
        ten_ke_toan = normalize_code(gcol("TÊN KẾ TOÁN"))
        don_vi_tinh = normalize_code(gcol("Đơn vị tính"))

        if not ma_vat_kiot:
            summary.blank_ma_vat_count += 1

        ton_co_the_nhap_raw = gcol("TỒN CÓ THỂ NHÁP")
        ton_co_the_nhap = to_float_or_none(ton_co_the_nhap_raw)

        if ton_co_the_nhap_raw is not None and str(ton_co_the_nhap_raw).strip() != "" and ton_co_the_nhap is None:
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
            continue

        ton_final = ton_co_the_nhap if ton_co_the_nhap is not None else 0.0
        if ton_final <= 0:
            summary.zero_or_negative_ton_count += 1

        tong_dang_nhap = to_float_or_none(gcol("TỔNG ĐANG NHÁP")) or 0.0

        stock_rows.append(
            StockRow(
                row_index=row_idx,
                nguon=normalize_code(gcol("NGUỒN")),
                ma_kiot_dai_dien=normalize_code(gcol("Mã kiot đại diện")),
                ten_kiot_dai_dien=normalize_code(gcol("Tên kiot đại diện")),
                ma_vat_kiot=ma_vat_kiot,
                ten_vat_kiot=normalize_code(gcol("TÊN VAT KIOT")),
                ten_ke_toan=ten_ke_toan,
                don_vi_tinh=don_vi_tinh,
                ton_dau_ngay=to_float_or_none(gcol("TỒN ĐẦU NGÀY")),
                gia_ban=to_float_or_none(gcol("GIÁ BÁN")),
                thue_vat=to_float_or_none(gcol("THUẾ VAT")),
                thue_nk=to_float_or_none(gcol("THUẾ NK")),
                tong_thue_mat=to_float_or_none(gcol("TỔNG THUẾ MẤT")),
                tong_dang_nhap=tong_dang_nhap,
                ton_co_the_nhap=ton_final,
                ma_vat_kiot_norm=normalize_code_for_match(ma_vat_kiot),
                ten_ke_toan_norm=normalize_code_for_match(ten_ke_toan),
                don_vi_tinh_norm=normalize_code_for_match(don_vi_tinh),
            )
        )

    return stock_rows, summary, errors, warnings


def _parse_khop_ma(df: pd.DataFrame, letters: dict[str, str]):
    """Parse DataFrame Khớp mã → (mapping_rows, summary, errors)."""
    col_map, missing = _build_col_map(df, letters)
    errors: list[str] = []
    if missing:
        errors.append(f"Sheet 'Khớp mã' thiếu cột (ngoài phạm vi sheet): {', '.join(missing)}")
        return [], SheetCheckSummary(sheet_name="Khớp mã"), errors

    summary = SheetCheckSummary(sheet_name="Khớp mã")
    mapping_rows: list[MappingRow] = []

    for row_idx, (_, row) in enumerate(df.iterrows(), start=2):
        if row.isna().all():
            continue

        def gcol(canonical: str):
            actual = col_map.get(canonical)
            return row.iloc[actual] if actual is not None else None

        summary.total_data_rows += 1

        ma_sp = normalize_code(gcol("Mã SP"))
        ma_vat_kiot = normalize_code(gcol("Mã vat kiot"))

        if not ma_sp:
            summary.blank_ma_count += 1
        if not ma_vat_kiot:
            summary.blank_ma_vat_count += 1

        mapping_rows.append(
            MappingRow(
                row_index=row_idx,
                ma_sp=ma_sp,
                ten_sp=normalize_code(gcol("Tên SP")),
                ma_vat_kiot=ma_vat_kiot,
                ten_truoc_vat=normalize_code(
                    gcol("Tên trước (Giá đầu  - Giá cuối) (VAT)")
                ),
                ma_sp_norm=normalize_code_for_match(ma_sp),
                ma_vat_kiot_norm=normalize_code_for_match(ma_vat_kiot),
            )
        )

    # Đếm Mã SP trỏ nhiều Mã VAT
    vat_by_ma_sp: dict[str, set] = defaultdict(set)
    for m in mapping_rows:
        if m.ma_sp_norm:
            vat_by_ma_sp[m.ma_sp_norm].add(m.ma_vat_kiot_norm)
    summary.duplicate_ma_sp_multi_vat_count = sum(
        1 for v in vat_by_ma_sp.values() if len(v) > 1
    )

    return mapping_rows, summary, errors


# ---------------------------------------------------------------------------
# Hàm tiện ích cấp cao: fetch + parse → WorkbookCheckResult
# ---------------------------------------------------------------------------


def fetch_workbook_from_sheets(
    sheet_id: str,
    gid_gop_vat: int,
    gid_khop_ma: int,
    gop_vat_columns: dict[str, str] | None = None,
    khop_ma_columns: dict[str, str] | None = None,
) -> tuple[WorkbookCheckResult, str]:
    """Fetch 2 sheets từ Google Sheets, parse thành WorkbookCheckResult.

    Returns:
        (workbook, timestamp)

    Raises:
        Exception: Nếu fetch hoặc parse thất bại.
    """
    gop_vat_columns = gop_vat_columns or DEFAULT_GOP_VAT_COLUMNS
    khop_ma_columns = khop_ma_columns or DEFAULT_KHOP_MA_COLUMNS
    reader = GoogleSheetsReader(
        sheet_id=sheet_id,
        gid_gop_vat=gid_gop_vat,
        gid_khop_ma=gid_khop_ma,
    )
    df_gop_vat, df_khop_ma, timestamp = reader.fetch_all()

    stock_rows, gop_vat_summary, gop_vat_errors, warnings = _parse_gop_vat(df_gop_vat, gop_vat_columns)
    mapping_rows, khop_ma_summary, khop_ma_errors = _parse_khop_ma(df_khop_ma, khop_ma_columns)

    all_errors = gop_vat_errors + khop_ma_errors

    workbook = WorkbookCheckResult(
        is_valid=len(all_errors) == 0,
        file_name=f"Google Sheets (gid_gop_vat={gid_gop_vat}, gid_khop_ma={gid_khop_ma})",
        file_size_bytes=0,
        sha256="",
        errors=all_errors,
        gop_vat_summary=gop_vat_summary,
        khop_ma_summary=khop_ma_summary,
        stock_rows=stock_rows,
        mapping_rows=mapping_rows,
        warnings=warnings,
    )
    return workbook, timestamp
