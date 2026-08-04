"""Phân bổ số lượng cần xuất qua các nguồn cho chức năng Xử lý hóa đơn.

Khác với ``src/source_lookup.py`` (chỉ tra cứu và chọn đúng một dòng nguồn),
module này chia ``SL`` của từng sản phẩm ra nhiều nguồn dựa trên cột
``TỒN CÓ THỂ NHÁP`` (hiển thị là ``TỒN CÒN NHÁP``):

* Tổng tồn của tất cả nguồn phải >= SL thì sản phẩm mới hợp lệ.
* Nếu có nguồn tự nó đủ SL: chỉ dùng một nguồn, ưu tiên nguồn xuất hiện
  nhiều nhất trong dữ liệu hóa đơn hiện tại.
* Nếu không nguồn nào đủ: lấy tối đa từ nguồn xuất hiện nhiều nhất, phần
  còn thiếu lấy tiếp theo thứ tự tồn còn giảm dần cho tới khi đủ đúng SL.
* Nếu tổng tồn vẫn nhỏ hơn SL: sản phẩm được tách xuống nhóm không hợp lệ.

Toàn bộ deterministic, không trừ tồn mô phỏng giữa các dòng hóa đơn (giữ
nguyên hành vi hiện tại của trang Xử lý hóa đơn).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.config import AppConfig
from src.models import MappingRow, StockRow
from src.name_matching import calculate_accounting_name_score
from src.normalization import normalize_code, normalize_code_for_match, to_float_or_none
from src.source_lookup import SourceLookupInput, SourceLookupIssue

# Sai số cho phép khi so sánh số thực (SL và tồn có thể là số lẻ).
TOLERANCE = 1e-9


@dataclass
class InvoiceAllocationLine:
    """Một dòng kết quả: một nguồn thực sự được dùng cho một sản phẩm."""

    query_order: int
    ma_sp: str
    ten_sp: str
    sl_yeu_cau: float
    sl_phan_bo: float
    gia_ban: Any
    ma_vat: str
    ten_vat: str
    ma_ke_toan: str
    ten_ke_toan: str
    dvt: str
    nguon: str
    ton_con_nhap: float
    phan_tram_vat: float | None
    gia_nhap: float | None
    ghi_chu_hang_hoa: str = ""
    ma_hoa_don: str = ""
    thanh_tien: Any = None


@dataclass
class InvoiceShortage:
    """Một sản phẩm không đủ tổng tồn để đáp ứng SL."""

    query_order: int
    ma_sp: str
    ten_sp: str
    sl_yeu_cau: float
    tong_ton: float
    thieu: float
    ghi_chu: str


@dataclass
class InvoiceAllocationResult:
    lines: list[InvoiceAllocationLine] = field(default_factory=list)
    shortages: list[InvoiceShortage] = field(default_factory=list)
    issues: list[SourceLookupIssue] = field(default_factory=list)
    skipped_non_positive_stock_count: int = 0


@dataclass
class _Candidate:
    """Một dòng tồn ứng viên kèm điểm khớp tên kế toán."""

    stock: StockRow
    score: float = 0.0


@dataclass
class _ResolvedQuery:
    query: SourceLookupInput
    mapping: MappingRow
    ma_sp: str
    ten_sp: str
    sl: float
    candidates: list[_Candidate]


def allocate_invoice_sources(
    queries: list[SourceLookupInput],
    mapping_rows: list[MappingRow],
    stock_rows: list[StockRow],
    config: AppConfig | None = None,
) -> InvoiceAllocationResult:
    """Phân bổ SL của từng dòng hóa đơn ra các nguồn theo tồn còn nháp."""

    config = config or AppConfig()
    result = InvoiceAllocationResult()

    mappings_by_code, mappings_by_name = _build_mapping_indexes(mapping_rows)
    _add_gop_vat_mapping_fallbacks(mappings_by_code, stock_rows)
    stock_by_vat = _build_stock_index(stock_rows, result)

    resolved: list[_ResolvedQuery] = []
    for query in queries or []:
        item = _resolve_query(
            query, mappings_by_code, mappings_by_name, stock_by_vat, config, result
        )
        if item is not None:
            resolved.append(item)

    # Số lần xuất hiện của mỗi nguồn còn tồn dương trong dữ liệu hóa đơn hiện tại:
    # đếm theo số sản phẩm có nguồn đó, không đếm trùng nhiều dòng tồn của cùng
    # sản phẩm. Dòng tồn <= 0 vẫn được giữ để phân biệt "đã hết tồn" với
    # "Mã VAT không tồn tại", nhưng không được ảnh hưởng thứ tự chọn nguồn.
    appearance_count: dict[str, int] = {}
    for item in resolved:
        for nguon in {
            c.stock.nguon for c in item.candidates if c.stock.ton_co_the_nhap > 0
        }:
            appearance_count[nguon] = appearance_count.get(nguon, 0) + 1

    priority_list = [normalize_code_for_match(s) for s in config.source_tiebreak_priority]

    def source_key(nguon: str) -> tuple:
        nguon_norm = normalize_code_for_match(nguon)
        try:
            priority_index = priority_list.index(nguon_norm)
        except ValueError:
            priority_index = len(priority_list)
        return (-appearance_count.get(nguon, 0), priority_index, nguon_norm)

    for item in resolved:
        _allocate_one_product(item, source_key, config, result)

    return result


def _allocate_one_product(
    item: _ResolvedQuery,
    source_key,
    config: AppConfig,
    result: InvoiceAllocationResult,
) -> None:
    need = item.sl
    usable = [c for c in item.candidates if c.stock.ton_co_the_nhap > 0]
    total_ton = sum(c.stock.ton_co_the_nhap for c in usable)

    if need > total_ton + TOLERANCE:
        thieu = need - total_ton
        result.shortages.append(
            InvoiceShortage(
                query_order=item.query.order_index,
                ma_sp=item.ma_sp,
                ten_sp=item.ten_sp,
                sl_yeu_cau=need,
                tong_ton=total_ton,
                thieu=thieu,
                ghi_chu=f"Không đủ số lượng tồn — thiếu {_format_qty(thieu)}",
            )
        )
        return

    by_source: dict[str, list[_Candidate]] = {}
    for c in usable:
        by_source.setdefault(c.stock.nguon, []).append(c)
    total_by_source = {
        nguon: sum(c.stock.ton_co_the_nhap for c in rows) for nguon, rows in by_source.items()
    }

    plan: list[tuple[str, float]] = []
    full_sources = [n for n, total in total_by_source.items() if total >= need - TOLERANCE]

    if full_sources:
        # Chỉ dùng một nguồn khi một nguồn đã đủ; ưu tiên nguồn xuất hiện nhiều nhất.
        plan.append((sorted(full_sources, key=source_key)[0], need))
    else:
        # Lấy tối đa từ nguồn xuất hiện nhiều nhất, phần còn thiếu lấy tiếp
        # theo tồn còn giảm dần.
        first = sorted(total_by_source, key=source_key)[0]
        rest = sorted(
            (n for n in total_by_source if n != first),
            key=lambda n: (-total_by_source[n],) + source_key(n),
        )
        remaining = need
        for nguon in [first, *rest]:
            if remaining <= TOLERANCE:
                break
            take = min(total_by_source[nguon], remaining)
            if take <= TOLERANCE:
                continue
            plan.append((nguon, take))
            remaining -= take

    for nguon, take in plan:
        for candidate, qty in _allocate_within_source(by_source[nguon], take):
            result.lines.append(_build_line(item, candidate.stock, qty, config))


def _allocate_within_source(
    candidates: list[_Candidate], need: float
) -> list[tuple[_Candidate, float]]:
    """Chia `need` trong phạm vi các dòng tồn của MỘT nguồn.

    Ưu tiên một dòng tồn duy nhất đủ cả `need` (điểm khớp tên cao nhất, tồn
    thấp nhất trong số các dòng đủ); nếu không có, lấy dần từ dòng tồn lớn
    nhất để số dòng kết quả là ít nhất.
    """

    single = [c for c in candidates if c.stock.ton_co_the_nhap >= need - TOLERANCE]
    if single:
        best = sorted(
            single, key=lambda c: (-c.score, c.stock.ton_co_the_nhap, c.stock.row_index)
        )[0]
        return [(best, need)]

    taken: list[tuple[_Candidate, float]] = []
    remaining = need
    for candidate in sorted(
        candidates, key=lambda c: (-c.stock.ton_co_the_nhap, -c.score, c.stock.row_index)
    ):
        if remaining <= TOLERANCE:
            break
        qty = min(candidate.stock.ton_co_the_nhap, remaining)
        if qty <= TOLERANCE:
            continue
        taken.append((candidate, qty))
        remaining -= qty
    return taken


def _build_line(
    item: _ResolvedQuery, stock: StockRow, qty: float, config: AppConfig
) -> InvoiceAllocationLine:
    gia_ban = to_float_or_none(item.query.gia_ban)
    phan_tram_vat = stock.thue_vat
    gia_nhap = None
    if gia_ban is not None and phan_tram_vat is not None and (1 + phan_tram_vat) != 0:
        gia_nhap = round(gia_ban / (1 + phan_tram_vat), config.gia_nhap_decimal_places)

    return InvoiceAllocationLine(
        query_order=item.query.order_index,
        ma_sp=item.ma_sp,
        ten_sp=item.ten_sp,
        sl_yeu_cau=item.sl,
        sl_phan_bo=qty,
        gia_ban=item.query.gia_ban,
        ma_vat=item.mapping.ma_vat_kiot,
        ten_vat=item.mapping.ten_truoc_vat or stock.ten_vat_kiot,
        ma_ke_toan=stock.ma_ke_toan,
        ten_ke_toan=stock.ten_ke_toan,
        dvt=stock.don_vi_tinh,
        nguon=stock.nguon,
        ton_con_nhap=stock.ton_co_the_nhap,
        phan_tram_vat=phan_tram_vat,
        gia_nhap=gia_nhap,
        ghi_chu_hang_hoa=str(item.query.ghi_chu_hang_hoa).strip() if item.query.ghi_chu_hang_hoa else "",
        ma_hoa_don=str(item.query.ma_hoa_don).strip() if item.query.ma_hoa_don else "",
        thanh_tien=to_float_or_none(item.query.thanh_tien),
    )


# ---------------------------------------------------------------------------
# Tra cứu mã sản phẩm -> mã VAT -> các dòng tồn
# ---------------------------------------------------------------------------


def _build_mapping_indexes(
    mapping_rows: list[MappingRow],
) -> tuple[dict[str, list[MappingRow]], dict[str, list[MappingRow]]]:
    by_code: dict[str, list[MappingRow]] = {}
    by_name: dict[str, list[MappingRow]] = {}
    for mapping in mapping_rows or []:
        if mapping.ma_sp_norm:
            by_code.setdefault(mapping.ma_sp_norm, []).append(mapping)
        name_norm = normalize_code_for_match(mapping.ten_sp)
        if name_norm:
            by_name.setdefault(name_norm, []).append(mapping)
    return by_code, by_name


def _add_gop_vat_mapping_fallbacks(
    mappings_by_code: dict[str, list[MappingRow]],
    stock_rows: list[StockRow],
) -> None:
    """Bổ sung Mã SP chỉ có trong cột ``Mã kiot đại diện`` của Gộp VAT.

    ``Khớp mã`` vẫn là nguồn ưu tiên: nếu mã đã tồn tại ở sheet đó thì không
    trộn thêm các dòng Gộp VAT, tránh làm thay đổi mapping được khai báo rõ ràng.
    Với mã chưa có trong Khớp mã, giữ mọi Mã VAT tìm thấy trong Gộp VAT để bước
    resolve hiện hữu vẫn phát hiện được trường hợp một Mã SP trỏ nhiều Mã VAT.
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


def _build_stock_index(
    stock_rows: list[StockRow], result: InvoiceAllocationResult
) -> dict[str, list[StockRow]]:
    stock_by_vat: dict[str, list[StockRow]] = {}
    for stock in stock_rows or []:
        if not stock.ma_vat_kiot_norm:
            continue
        # Tồn không phải số đã bị loại từ excel_reader. Không loại dòng tồn <= 0
        # khỏi chỉ mục tại đây: bước resolve cần nhìn thấy chúng để phân biệt một
        # Mã VAT có trong Gộp VAT nhưng đã hết tồn với một Mã VAT hoàn toàn không
        # tồn tại. Việc loại khỏi ứng viên phân bổ nằm ở _allocate_one_product.
        if stock.ton_co_the_nhap is None or stock.ton_co_the_nhap <= 0:
            result.skipped_non_positive_stock_count += 1
        stock_by_vat.setdefault(stock.ma_vat_kiot_norm, []).append(stock)
    return stock_by_vat


def _resolve_query(
    query: SourceLookupInput,
    mappings_by_code: dict[str, list[MappingRow]],
    mappings_by_name: dict[str, list[MappingRow]],
    stock_by_vat: dict[str, list[StockRow]],
    config: AppConfig,
    result: InvoiceAllocationResult,
) -> _ResolvedQuery | None:
    ma_sp = normalize_code(query.ma_sp)
    ten_sp = normalize_code(query.ten_sp)

    if ma_sp:
        mappings = mappings_by_code.get(normalize_code_for_match(ma_sp), [])
        if not mappings:
            _add_issue(
                result, query, ma_sp, ten_sp, "khong_tim_thay_ma", f"Không tìm thấy Mã SP '{ma_sp}'."
            )
            return None
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
            return None
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
            return None
    else:
        _add_issue(
            result,
            query,
            ma_sp,
            ten_sp,
            "thieu_dieu_kien",
            "Cần nhập ít nhất Mã SP hoặc Tên SP.",
        )
        return None

    distinct_vat = {m.ma_vat_kiot_norm for m in mappings if m.ma_vat_kiot_norm}
    if len(distinct_vat) != 1:
        vat_labels = sorted({m.ma_vat_kiot for m in mappings if m.ma_vat_kiot})
        detail = (
            f"Sản phẩm đang trỏ tới nhiều Mã VAT: {', '.join(vat_labels)}."
            if vat_labels
            else "Sản phẩm chưa có Mã VAT trong sheet Khớp mã."
        )
        _add_issue(result, query, ma_sp, ten_sp, "ma_vat_khong_duy_nhat", detail)
        return None

    mapping = mappings[0]

    sl = to_float_or_none(query.sl)
    if query.sl is None or str(query.sl).strip() == "":
        _add_issue(result, query, mapping.ma_sp, mapping.ten_sp, "sl_trong", "SL để trống.")
        return None
    if sl is None:
        _add_issue(
            result,
            query,
            mapping.ma_sp,
            mapping.ten_sp,
            "sl_khong_phai_so",
            f"SL='{query.sl}' không phải số.",
        )
        return None
    if sl <= 0:
        _add_issue(
            result,
            query,
            mapping.ma_sp,
            mapping.ten_sp,
            "sl_khong_duong",
            f"SL={_format_qty(sl)} phải lớn hơn 0.",
        )
        return None

    stocks = stock_by_vat.get(next(iter(distinct_vat)), [])
    if not stocks:
        _add_issue(
            result,
            query,
            mapping.ma_sp,
            mapping.ten_sp,
            "khong_con_ton_duong",
            f"Mã VAT '{mapping.ma_vat_kiot}' không còn nguồn nào có tồn nháp dương.",
        )
        return None

    candidates = [
        _Candidate(
            stock=stock,
            score=calculate_accounting_name_score(
                ten_ke_toan=stock.ten_ke_toan,
                user_ten_sp=ten_sp or mapping.ten_sp,
                khop_ma_ten_sp=mapping.ten_sp,
                ten_vat_kiot=stock.ten_vat_kiot,
                ten_truoc_vat_raw=mapping.ten_truoc_vat,
                weights=config.name_match,
            ).score,
        )
        for stock in stocks
    ]

    return _ResolvedQuery(
        query=query,
        mapping=mapping,
        ma_sp=mapping.ma_sp,
        ten_sp=mapping.ten_sp,
        sl=sl,
        candidates=candidates,
    )


def _add_issue(
    result: InvoiceAllocationResult,
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


def _format_qty(value: float) -> str:
    """Hiển thị số lượng gọn: số nguyên không có phần thập phân thừa."""

    if float(value).is_integer():
        return f"{int(value):,}".replace(",", ".")
    return f"{value:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


# ---------------------------------------------------------------------------
# Bảng hiển thị
# ---------------------------------------------------------------------------


def build_allocation_display_rows(lines: list[InvoiceAllocationLine]) -> list[dict[str, Any]]:
    """Bảng kết quả giữ đúng bộ cột nghiệp vụ; cột SL là số đã phân bổ."""

    return [
        {
            "MÃ SP": line.ma_sp,
            "TÊN SP": line.ten_sp,
            "SL": line.sl_phan_bo,
            "Giá bán": to_float_or_none(line.gia_ban),
            "Mã VAT": line.ma_vat,
            "TÊN VAT": line.ten_vat,
            "MÃ KT": line.ma_ke_toan,
            "TÊN KẾ TOÁN": line.ten_ke_toan,
            "ĐVT": line.dvt,
            "NGUỒN": line.nguon,
            "TỒN CÒN NHÁP": line.ton_con_nhap,
            "%VAT": line.phan_tram_vat * 100 if line.phan_tram_vat is not None else None,
            "GIÁ NHÁP\n(Giá bán/(1+%VAT))": line.gia_nhap,
            "Ghi chú hàng hóa": line.ghi_chu_hang_hoa,
            "Mã hóa đơn": line.ma_hoa_don,
            "Thành tiền": line.thanh_tien,
        }
        for line in lines
    ]


def build_shortage_display_rows(shortages: list[InvoiceShortage]) -> list[dict[str, Any]]:
    """Bảng sản phẩm không hợp lệ, hiển thị riêng phía dưới kết quả hợp lệ."""

    return [
        {
            "Dòng nhập": shortage.query_order,
            "MÃ SP": shortage.ma_sp,
            "TÊN SP": shortage.ten_sp,
            "SL yêu cầu": shortage.sl_yeu_cau,
            "Tổng tồn hiện có": shortage.tong_ton,
            "Còn thiếu": shortage.thieu,
            "Ghi chú": shortage.ghi_chu,
        }
        for shortage in shortages
    ]


def build_unavailable_display_rows(
    issues: list[SourceLookupIssue],
    mapping_rows: list[MappingRow],
    stock_rows: list[StockRow],
) -> list[dict[str, Any]]:
    """Tạo bảng lỗi kèm trạng thái tồn tại của sản phẩm trong từng sheet."""

    mapping_vats_by_code: dict[str, set[str]] = {}
    for mapping in mapping_rows or []:
        if mapping.ma_sp_norm:
            mapping_vats_by_code.setdefault(mapping.ma_sp_norm, set()).add(
                mapping.ma_vat_kiot_norm
            )

    stock_vats = {stock.ma_vat_kiot_norm for stock in stock_rows or [] if stock.ma_vat_kiot_norm}
    direct_gop_codes = {
        normalize_code_for_match(stock.ma_kiot_dai_dien)
        for stock in stock_rows or []
        if normalize_code_for_match(stock.ma_kiot_dai_dien)
    }

    rows: list[dict[str, Any]] = []
    for issue in issues or []:
        code_norm = normalize_code_for_match(issue.ma_sp)
        in_khop_ma = bool(code_norm and code_norm in mapping_vats_by_code)
        mapped_vats = mapping_vats_by_code.get(code_norm, set())
        in_gop_vat = bool(
            code_norm
            and (
                code_norm in direct_gop_codes
                or any(vat and vat in stock_vats for vat in mapped_vats)
            )
        )

        if not code_norm:
            sheet_status = "Không xác định được Mã SP"
            presence_detail = "Không có Mã SP để kiểm tra trong hai sheet."
        elif in_gop_vat and in_khop_ma:
            sheet_status = "Có trong cả 2 sheet"
            presence_detail = (
                "Sản phẩm có trong cả Gộp VAT và Khớp mã nhưng chưa thỏa điều kiện xử lý."
            )
        elif in_gop_vat:
            sheet_status = "Chỉ có trong Gộp VAT"
            presence_detail = "Không tìm thấy sản phẩm trong sheet Khớp mã."
        elif in_khop_ma:
            sheet_status = "Chỉ có trong Khớp mã"
            presence_detail = "Không tìm thấy sản phẩm hoặc Mã VAT tương ứng trong sheet Gộp VAT."
        else:
            sheet_status = "Không có trong cả 2 sheet"
            presence_detail = "Không tìm thấy sản phẩm trong cả Gộp VAT và Khớp mã."

        rows.append(
            {
                "Dòng nhập": issue.query_order,
                "Mã SP": issue.ma_sp,
                "Tên SP": issue.ten_sp,
                "Trạng thái trong file": sheet_status,
                "Nội dung": f"{presence_detail} {issue.detail}".strip(),
            }
        )

    return rows
