"""Tra cứu nguồn theo Mã SP hoặc Tên SP (yêu cầu 2-4).

Chức năng này chỉ tra cứu và sắp xếp dữ liệu hiện có. Nó không phân bổ,
không mô phỏng trừ tồn và không dùng AI/fuzzy matching.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.models import MappingRow, StockRow
from src.normalization import normalize_code, normalize_code_for_match


@dataclass
class SourceLookupInput:
    order_index: int
    ma_sp: Any = ""
    ten_sp: Any = ""
    sl: Any = ""
    gia_ban: Any = ""


@dataclass
class SourceLookupLine:
    query_order: int
    ma_sp: str
    ten_sp: str
    sl: Any
    gia_ban: Any
    ma_vat: str
    ten_vat: str
    ten_ke_toan: str
    dvt: str
    nguon: str
    ton_con_nhap: float
    phan_tram_vat: float | None


@dataclass
class SourceLookupIssue:
    query_order: int
    ma_sp: str
    ten_sp: str
    issue_type: str
    detail: str


@dataclass
class SourceLookupResult:
    lines: list[SourceLookupLine] = field(default_factory=list)
    issues: list[SourceLookupIssue] = field(default_factory=list)
    skipped_non_positive_stock_count: int = 0


def lookup_sources(
    queries: list[SourceLookupInput],
    mapping_rows: list[MappingRow],
    stock_rows: list[StockRow],
) -> SourceLookupResult:
    """Tra cứu từng sản phẩm và trả mọi dòng nguồn còn tồn dương.

    Mã SP được so khớp chính xác sau chuẩn hóa. Nếu không nhập Mã SP, Tên SP
    cũng được so khớp chính xác sau chuẩn hóa; tên trùng nhiều mã sẽ được báo
    rõ để người dùng chọn bằng Mã SP.
    """

    result = SourceLookupResult()
    mappings_by_code: dict[str, list[MappingRow]] = {}
    mappings_by_name: dict[str, list[MappingRow]] = {}
    stock_by_vat: dict[str, list[StockRow]] = {}

    for mapping in mapping_rows:
        if mapping.ma_sp_norm:
            mappings_by_code.setdefault(mapping.ma_sp_norm, []).append(mapping)
        name_norm = normalize_code_for_match(mapping.ten_sp)
        if name_norm:
            mappings_by_name.setdefault(name_norm, []).append(mapping)

    for stock in stock_rows:
        if not stock.ma_vat_kiot_norm:
            continue
        if stock.ton_co_the_nhap <= 0:
            result.skipped_non_positive_stock_count += 1
            continue
        stock_by_vat.setdefault(stock.ma_vat_kiot_norm, []).append(stock)

    for query in queries:
        ma_sp = normalize_code(query.ma_sp)
        ten_sp = normalize_code(query.ten_sp)
        mappings: list[MappingRow]

        if ma_sp:
            mappings = mappings_by_code.get(normalize_code_for_match(ma_sp), [])
            if not mappings:
                _add_issue(result, query, ma_sp, ten_sp, "khong_tim_thay_ma", f"Không tìm thấy Mã SP '{ma_sp}'.")
                continue
        elif ten_sp:
            mappings = mappings_by_name.get(normalize_code_for_match(ten_sp), [])
            if not mappings:
                _add_issue(
                    result,
                    query,
                    ma_sp,
                    ten_sp,
                    "khong_tim_thay_ten",
                    f"Không tìm thấy chính xác Tên SP '{ten_sp}'.",
                )
                continue
            distinct_codes = sorted({m.ma_sp for m in mappings if m.ma_sp})
            if len(distinct_codes) > 1:
                _add_issue(
                    result,
                    query,
                    ma_sp,
                    ten_sp,
                    "ten_trung_nhieu_ma",
                    f"Tên SP khớp nhiều mã: {', '.join(distinct_codes)}. Hãy nhập Mã SP để chọn chính xác.",
                )
                continue
        else:
            _add_issue(
                result,
                query,
                ma_sp,
                ten_sp,
                "thieu_dieu_kien",
                "Cần nhập ít nhất Mã SP hoặc Tên SP.",
            )
            continue

        distinct_vat = {m.ma_vat_kiot_norm for m in mappings if m.ma_vat_kiot_norm}
        if len(distinct_vat) != 1:
            vat_labels = sorted({m.ma_vat_kiot for m in mappings if m.ma_vat_kiot})
            detail = (
                f"Sản phẩm đang trỏ tới nhiều Mã VAT: {', '.join(vat_labels)}."
                if vat_labels
                else "Sản phẩm chưa có Mã VAT trong sheet Khớp mã."
            )
            _add_issue(result, query, ma_sp, ten_sp, "ma_vat_khong_duy_nhat", detail)
            continue

        mapping = mappings[0]
        candidates = sorted(
            stock_by_vat.get(next(iter(distinct_vat)), []),
            key=lambda row: (
                row.ton_co_the_nhap,
                normalize_code_for_match(row.nguon),
                normalize_code_for_match(row.ten_ke_toan),
                row.row_index,
            ),
        )
        if not candidates:
            _add_issue(
                result,
                query,
                mapping.ma_sp,
                mapping.ten_sp,
                "khong_con_ton_duong",
                f"Mã VAT '{mapping.ma_vat_kiot}' không có nguồn nào còn tồn nháp dương.",
            )
            continue

        for stock in candidates:
            result.lines.append(
                SourceLookupLine(
                    query_order=query.order_index,
                    ma_sp=mapping.ma_sp,
                    ten_sp=mapping.ten_sp,
                    sl=query.sl,
                    gia_ban=query.gia_ban,
                    ma_vat=mapping.ma_vat_kiot,
                    ten_vat=mapping.ten_truoc_vat or stock.ten_vat_kiot,
                    ten_ke_toan=stock.ten_ke_toan,
                    dvt=stock.don_vi_tinh,
                    nguon=stock.nguon,
                    ton_con_nhap=stock.ton_co_the_nhap,
                    phan_tram_vat=stock.thue_vat,
                )
            )

    return result


def build_grouped_display_rows(lines: list[SourceLookupLine]) -> list[dict[str, Any]]:
    """Tạo bảng hiển thị gọn: thông tin Kiot chỉ lặp ở đầu mỗi sản phẩm."""

    rows: list[dict[str, Any]] = []
    previous_query_order: int | None = None
    for line in lines:
        is_first_source = line.query_order != previous_query_order
        rows.append(
            {
                "Mã kiot": line.ma_sp if is_first_source else "",
                "Tên kiot": line.ten_sp if is_first_source else "",
                "SL": line.sl if is_first_source else "",
                "Giá bán": line.gia_ban if is_first_source else "",
                "Mã VAT": line.ma_vat,
                "Tên VAT": line.ten_vat,
                "Mã kế toán": line.ten_ke_toan,
                "ĐVT": line.dvt,
                "Nguồn": line.nguon,
                "Tồn nháp được": line.ton_con_nhap,
                "%VAT": line.phan_tram_vat * 100 if line.phan_tram_vat is not None else None,
            }
        )
        previous_query_order = line.query_order
    return rows


def _add_issue(
    result: SourceLookupResult,
    query: SourceLookupInput,
    ma_sp: str,
    ten_sp: str,
    issue_type: str,
    detail: str,
) -> None:
    result.issues.append(
        SourceLookupIssue(
            query_order=query.order_index,
            ma_sp=ma_sp,
            ten_sp=ten_sp,
            issue_type=issue_type,
            detail=detail,
        )
    )
