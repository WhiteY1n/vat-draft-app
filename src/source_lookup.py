"""Tra cứu nguồn theo Mã SP hoặc Tên SP (yêu cầu 2-4).

Chức năng này chỉ tra cứu và sắp xếp dữ liệu hiện có. Nó không phân bổ,
không mô phỏng trừ tồn và không dùng AI/fuzzy matching.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.config import AppConfig
from src.models import MappingRow, StockRow
from src.name_matching import calculate_accounting_name_score
from src.normalization import normalize_code, normalize_code_for_match, to_float_or_none


@dataclass
class SourceLookupInput:
    order_index: int
    ma_sp: Any = ""
    ten_sp: Any = ""
    sl: Any = ""
    gia_ban: Any = ""
    ghi_chu_hang_hoa: Any = ""
    ma_hoa_don: Any = ""
    thanh_tien: Any = ""


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
    gia_nhap: float | None


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


@dataclass
class _ResolvedLookup:
    query: SourceLookupInput
    mapping: MappingRow
    ma_sp: str
    ten_sp: str
    candidates: list[StockRow]


def lookup_sources(
    queries: list[SourceLookupInput],
    mapping_rows: list[MappingRow],
    stock_rows: list[StockRow],
    config: AppConfig | None = None,
) -> SourceLookupResult:
    """Tra cứu từng sản phẩm và chọn đúng một dòng nguồn/kế toán để đề xuất.

    Nguồn đủ SL được ưu tiên theo số dòng hóa đơn mà nguồn đó có thể đáp ứng.
    Nếu không nguồn nào đủ SL, chọn dòng có tồn lớn nhất; dòng tồn 0 vẫn được
    giữ làm phương án cuối khi không còn lựa chọn tốt hơn.
    """

    config = config or AppConfig()
    result = SourceLookupResult()
    mappings_by_code: dict[str, list[MappingRow]] = {}
    mappings_by_name: dict[str, list[MappingRow]] = {}
    stock_by_vat: dict[str, list[StockRow]] = {}
    resolved_lookups: list[_ResolvedLookup] = []

    for mapping in mapping_rows:
        if mapping.ma_sp_norm:
            mappings_by_code.setdefault(mapping.ma_sp_norm, []).append(mapping)
        name_norm = normalize_code_for_match(mapping.ten_sp)
        if name_norm:
            mappings_by_name.setdefault(name_norm, []).append(mapping)

    for stock in stock_rows:
        if not stock.ma_vat_kiot_norm:
            continue
        if stock.ton_co_the_nhap < 0:
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
        candidates = stock_by_vat.get(next(iter(distinct_vat)), [])
        if not candidates:
            _add_issue(
                result,
                query,
                mapping.ma_sp,
                mapping.ten_sp,
                "khong_co_nguon_khong_am",
                f"Mã VAT '{mapping.ma_vat_kiot}' không có nguồn nào với tồn nháp từ 0 trở lên.",
            )
            continue

        resolved_lookups.append(
            _ResolvedLookup(
                query=query,
                mapping=mapping,
                ma_sp=mapping.ma_sp,
                ten_sp=mapping.ten_sp,
                candidates=list(candidates),
            )
        )

    full_coverage_count: dict[str, int] = {}
    appearance_count: dict[str, int] = {}

    for resolved in resolved_lookups:
        required_qty = to_float_or_none(resolved.query.sl)
        max_stock_by_source: dict[str, float] = {}
        for stock in resolved.candidates:
            max_stock_by_source[stock.nguon] = max(
                max_stock_by_source.get(stock.nguon, float("-inf")), stock.ton_co_the_nhap
            )
        for source, max_stock in max_stock_by_source.items():
            appearance_count[source] = appearance_count.get(source, 0) + 1
            has_coverage = (
                max_stock >= required_qty
                if required_qty is not None and required_qty > 0
                else max_stock > 0
            )
            if has_coverage:
                full_coverage_count[source] = full_coverage_count.get(source, 0) + 1

    priority_list = [normalize_code_for_match(source) for source in config.source_tiebreak_priority]

    def source_rank(source: str) -> tuple:
        source_norm = normalize_code_for_match(source)
        try:
            priority_index = priority_list.index(source_norm)
        except ValueError:
            priority_index = len(priority_list)
        return (
            -full_coverage_count.get(source, 0),
            -appearance_count.get(source, 0),
            priority_index,
            source_norm,
        )

    for resolved in resolved_lookups:
        required_qty = to_float_or_none(resolved.query.sl)
        required_qty = required_qty if required_qty is not None and required_qty > 0 else None

        scored_candidates: list[tuple[StockRow, float]] = []
        for stock in resolved.candidates:
            score = calculate_accounting_name_score(
                ten_ke_toan=stock.ten_ke_toan,
                user_ten_sp=normalize_code(resolved.query.ten_sp) or resolved.ten_sp,
                khop_ma_ten_sp=resolved.mapping.ten_sp,
                ten_vat_kiot=stock.ten_vat_kiot,
                ten_truoc_vat_raw=resolved.mapping.ten_truoc_vat,
                weights=config.name_match,
            ).score
            scored_candidates.append((stock, score))

        adequate = [
            item
            for item in scored_candidates
            if (
                item[0].ton_co_the_nhap >= required_qty
                if required_qty is not None
                else item[0].ton_co_the_nhap > 0
            )
        ]

        if adequate:
            adequate.sort(
                key=lambda item: (
                    source_rank(item[0].nguon),
                    -item[1],
                    item[0].ton_co_the_nhap,
                    item[0].row_index,
                )
            )
            chosen_stock = adequate[0][0]
        else:
            scored_candidates.sort(
                key=lambda item: (
                    -item[0].ton_co_the_nhap,
                    source_rank(item[0].nguon),
                    -item[1],
                    item[0].row_index,
                )
            )
            chosen_stock = scored_candidates[0][0]

        gia_ban = to_float_or_none(resolved.query.gia_ban)
        phan_tram_vat = chosen_stock.thue_vat
        gia_nhap = None
        if gia_ban is not None and phan_tram_vat is not None and (1 + phan_tram_vat) != 0:
            gia_nhap = round(
                gia_ban / (1 + phan_tram_vat), config.gia_nhap_decimal_places
            )

        result.lines.append(
            SourceLookupLine(
                query_order=resolved.query.order_index,
                ma_sp=resolved.ma_sp,
                ten_sp=resolved.ten_sp,
                sl=resolved.query.sl,
                gia_ban=resolved.query.gia_ban,
                ma_vat=resolved.mapping.ma_vat_kiot,
                ten_vat=resolved.mapping.ten_truoc_vat or chosen_stock.ten_vat_kiot,
                ten_ke_toan=chosen_stock.ten_ke_toan,
                dvt=chosen_stock.don_vi_tinh,
                nguon=chosen_stock.nguon,
                ton_con_nhap=chosen_stock.ton_co_the_nhap,
                phan_tram_vat=chosen_stock.thue_vat,
                gia_nhap=gia_nhap,
            )
        )

    return result


def _add_gop_vat_mapping_fallbacks(
    mappings_by_code: dict[str, list[MappingRow]],
    stock_rows: list[StockRow],
) -> None:
    """Bổ sung Mã SP chỉ có trong cột ``Mã kiot đại diện`` của Gộp VAT.

    Mapping khai báo trong Khớp mã luôn được ưu tiên. Chỉ khi mã chưa có ở
    Khớp mã mới dựng mapping dự phòng từ chính dòng Gộp VAT.
    """

    fallback_by_code: dict[str, list[MappingRow]] = {}
    for stock in stock_rows or []:
        ma_sp_norm = normalize_code_for_match(stock.ma_kiot_dai_dien)
        if not ma_sp_norm or ma_sp_norm in mappings_by_code:
            continue
        fallback_by_code.setdefault(ma_sp_norm, []).append(
            MappingRow(
                row_index=stock.row_index,
                ma_sp=stock.ma_kiot_dai_dien,
                ten_sp=stock.ten_kiot_dai_dien,
                ma_vat_kiot=stock.ma_vat_kiot,
                ten_truoc_vat=stock.ten_vat_kiot,
                ma_sp_norm=ma_sp_norm,
                ma_vat_kiot_norm=stock.ma_vat_kiot_norm,
            )
        )

    mappings_by_code.update(fallback_by_code)


def lookup_all_sources(
    queries: list[SourceLookupInput],
    mapping_rows: list[MappingRow],
    stock_rows: list[StockRow],
    config: AppConfig | None = None,
) -> SourceLookupResult:
    """Trả toàn bộ nguồn có trong file cho từng input.

    Hàm này dành riêng cho trang Tra cứu nguồn. Khác với ``lookup_sources``
    dùng ở trang Xử lý hóa đơn, hàm không chọn một nguồn đại diện. Nguồn còn
    tồn dương được xếp trước (tồn ít đứng trước), sau đó mới đến nguồn hết/âm
    tồn để người dùng vẫn tra thấy sản phẩm thực sự có trong file.
    """

    config = config or AppConfig()
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

    _add_gop_vat_mapping_fallbacks(mappings_by_code, stock_rows)

    for stock in stock_rows:
        if not stock.ma_vat_kiot_norm:
            continue
        stock_by_vat.setdefault(stock.ma_vat_kiot_norm, []).append(stock)

    for query in queries:
        ma_sp = normalize_code(query.ma_sp)
        ten_sp = normalize_code(query.ten_sp)

        if ma_sp:
            mappings = mappings_by_code.get(normalize_code_for_match(ma_sp), [])
            if not mappings:
                _add_issue(
                    result,
                    query,
                    ma_sp,
                    ten_sp,
                    "khong_tim_thay_ma",
                    f"Không tìm thấy Mã SP '{ma_sp}'.",
                )
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
                    f"Tên SP khớp nhiều mã: {', '.join(distinct_codes)}. "
                    "Hãy nhập Mã SP để chọn chính xác.",
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
            key=lambda stock: (
                stock.ton_co_the_nhap <= 0,
                stock.ton_co_the_nhap
                if stock.ton_co_the_nhap > 0
                else -stock.ton_co_the_nhap,
                normalize_code_for_match(stock.nguon),
                stock.row_index,
            ),
        )
        if not candidates:
            _add_issue(
                result,
                query,
                mapping.ma_sp,
                mapping.ten_sp,
                "khong_co_nguon",
                f"Mã VAT '{mapping.ma_vat_kiot}' không có dòng nguồn trong sheet Gộp VAT.",
            )
            continue

        gia_ban = to_float_or_none(query.gia_ban)
        for stock in candidates:
            phan_tram_vat = stock.thue_vat
            gia_nhap = None
            if gia_ban is not None and phan_tram_vat is not None and (1 + phan_tram_vat) != 0:
                gia_nhap = round(
                    gia_ban / (1 + phan_tram_vat),
                    config.gia_nhap_decimal_places,
                )
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
                    gia_nhap=gia_nhap,
                )
            )

    return result


def build_grouped_display_rows(lines: list[SourceLookupLine]) -> list[dict[str, Any]]:
    """Tạo bảng kết quả hóa đơn với đúng một dòng cho mỗi mã sản phẩm."""

    rows: list[dict[str, Any]] = []
    for line in lines:
        rows.append(
            {
                "MÃ SP": line.ma_sp,
                "TÊN SP": line.ten_sp,
                "SL": to_float_or_none(line.sl),
                "Giá bán": to_float_or_none(line.gia_ban),
                "Mã VAT": line.ma_vat,
                "TÊN VAT": line.ten_vat,
                "TÊN KẾ TOÁN": line.ten_ke_toan,
                "ĐVT": line.dvt,
                "NGUỒN": line.nguon,
                "TỒN CÒN NHÁP": line.ton_con_nhap,
                "%VAT": line.phan_tram_vat * 100 if line.phan_tram_vat is not None else None,
                "GIÁ NHÁP (Giá bán/(1+%VAT))": line.gia_nhap,
            }
        )
    return rows


def build_all_sources_display_rows(lines: list[SourceLookupLine]) -> list[dict[str, Any]]:
    """Tạo bảng nhiều nguồn, chỉ hiện thông tin input ở dòng đầu mỗi sản phẩm."""

    rows: list[dict[str, Any]] = []
    seen_queries: set[int] = set()
    for line in lines:
        is_first = line.query_order not in seen_queries
        seen_queries.add(line.query_order)
        rows.append(
            {
                "Mã kiot": line.ma_sp if is_first else "",
                "Tên kiot": line.ten_sp if is_first else "",
                "SL": to_float_or_none(line.sl) if is_first else "",
                "Giá bán": to_float_or_none(line.gia_ban) if is_first else "",
                "Mã VAT": line.ma_vat,
                "Tên VAT": line.ten_vat,
                "Mã kế toán": line.ten_ke_toan,
                "ĐVT": line.dvt,
                "Nguồn": line.nguon,
                "Tồn nháp được": line.ton_con_nhap,
                "%VAT": line.phan_tram_vat * 100 if line.phan_tram_vat is not None else None,
            }
        )
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
