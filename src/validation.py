"""Kiểm tra dữ liệu hóa đơn người dùng nhập (mục 7, 8 CLAUDE.md).

Không tạo kết quả nếu tồn tại bất kỳ lỗi chặn nào.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.config import AppConfig
from src.mapping import MappingLookup
from src.models import InvoiceInputRow, MappingRow, RowError, StockRow
from src.normalization import normalize_code, to_float_or_none


@dataclass
class ResolvedInvoiceRow:
    """Một dòng hóa đơn đã qua kiểm tra và mapping thành công."""

    input_row_id: str
    order_index: int
    ma_sp: str
    ten_sp: str
    sl: float
    gia_ban: float
    mapping_row: MappingRow
    stock_candidates: list[StockRow]  # ứng viên có TỒN CÓ THỂ NHÁP > 0


@dataclass
class ValidationResult:
    resolved_rows: list[ResolvedInvoiceRow] = field(default_factory=list)
    errors: list[RowError] = field(default_factory=list)

    @property
    def has_blocking_errors(self) -> bool:
        return len(self.errors) > 0

    @property
    def valid_count(self) -> int:
        return len(self.resolved_rows)

    @property
    def error_row_count(self) -> int:
        return len({e.input_row_id for e in self.errors})


def validate_invoice_rows(
    rows: list[InvoiceInputRow],
    lookup: MappingLookup,
    config: AppConfig,
) -> ValidationResult:
    result = ValidationResult()

    for row in rows:
        row_errors: list[RowError] = []

        ma_sp = normalize_code(row.ma_sp)
        ten_sp = normalize_code(row.ten_sp)

        if not ma_sp:
            row_errors.append(
                _err(row, "ma_sp_trong", "Mã SP để trống.", "Nhập Mã SP cho dòng này.")
            )
        if not ten_sp:
            row_errors.append(
                _err(row, "ten_sp_trong", "Tên SP để trống.", "Nhập Tên SP cho dòng này.")
            )

        sl_value = to_float_or_none(row.sl)
        if row.sl in (None, "") or str(row.sl).strip() == "":
            row_errors.append(_err(row, "sl_trong", "SL để trống.", "Nhập số lượng."))
        elif sl_value is None:
            row_errors.append(
                _err(row, "sl_khong_phai_so", f"SL='{row.sl}' không phải số.", "Sửa lại SL.")
            )
        else:
            if sl_value <= 0:
                row_errors.append(
                    _err(row, "sl_khong_duong", f"SL={sl_value} <= 0.", "SL phải lớn hơn 0.")
                )
            if not config.allow_fractional_sl and sl_value != int(sl_value):
                row_errors.append(
                    _err(
                        row,
                        "sl_khong_nguyen",
                        f"SL={sl_value} không phải số nguyên.",
                        "Nghiệp vụ hiện không cho phép SL lẻ.",
                    )
                )

        gia_ban_value = to_float_or_none(row.gia_ban)
        if row.gia_ban in (None, "") or str(row.gia_ban).strip() == "":
            row_errors.append(_err(row, "gia_ban_trong", "Giá bán để trống.", "Nhập giá bán."))
        elif gia_ban_value is None:
            row_errors.append(
                _err(
                    row,
                    "gia_ban_khong_phai_so",
                    f"Giá bán='{row.gia_ban}' không phải số.",
                    "Sửa lại giá bán.",
                )
            )
        elif gia_ban_value < 0:
            row_errors.append(
                _err(row, "gia_ban_am", f"Giá bán={gia_ban_value} < 0.", "Giá bán không được âm.")
            )

        mapping_row: MappingRow | None = None
        stock_candidates: list[StockRow] = []

        if ma_sp:
            mappings = lookup.find_mapping(ma_sp)
            if not mappings:
                row_errors.append(
                    _err(
                        row,
                        "ma_sp_khong_ton_tai",
                        f"Không tìm thấy Mã SP '{ma_sp}' trong sheet Khớp mã.",
                        "Kiểm tra lại Mã SP hoặc cập nhật sheet Khớp mã.",
                    )
                )
            else:
                distinct_vat = {m.ma_vat_kiot_norm for m in mappings if m.ma_vat_kiot_norm}
                if len(distinct_vat) > 1:
                    row_errors.append(
                        _err(
                            row,
                            "ma_sp_da_vat",
                            f"Mã SP '{ma_sp}' trỏ tới nhiều Mã VAT khác nhau: "
                            f"{sorted({m.ma_vat_kiot for m in mappings})}.",
                            "Cần rà soát lại sheet Khớp mã để đảm bảo 1 Mã SP chỉ trỏ 1 Mã VAT.",
                        )
                    )
                else:
                    mapping_row = mappings[0]
                    if not mapping_row.ma_vat_kiot_norm:
                        row_errors.append(
                            _err(
                                row,
                                "mavat_trong_khop_ma",
                                f"Mã SP '{ma_sp}' có Mã vat kiot để trống trong sheet Khớp mã.",
                                "Bổ sung Mã vat kiot trong sheet Khớp mã.",
                            )
                        )
                    else:
                        stock_candidates = lookup.find_stock_candidates(mapping_row.ma_vat_kiot_norm)
                        if not stock_candidates:
                            all_stock_rows = lookup.find_all_stock_rows(
                                mapping_row.ma_vat_kiot_norm
                            )
                            if all_stock_rows:
                                max_stock = max(s.ton_co_the_nhap for s in all_stock_rows)
                                row_errors.append(
                                    _err(
                                        row,
                                        "mavat_het_ton_nhap",
                                        f"Mã VAT '{mapping_row.ma_vat_kiot}' có trong sheet Gộp VAT "
                                        f"nhưng không còn tồn có thể nháp dương (cao nhất {max_stock:g}).",
                                        "Cập nhật cột TỒN CÓ THỂ NHÁP trong sheet Gộp VAT "
                                        "hoặc chọn sản phẩm còn tồn.",
                                    )
                                )
                            else:
                                row_errors.append(
                                    _err(
                                        row,
                                        "mavat_khong_ton_tai",
                                        f"Mã VAT '{mapping_row.ma_vat_kiot}' không tồn tại trong "
                                        "sheet Gộp VAT.",
                                        "Kiểm tra Mã VAT ở sheet Khớp mã và sheet Gộp VAT.",
                                    )
                                )

        if row_errors:
            result.errors.extend(row_errors)
            continue

        assert mapping_row is not None
        result.resolved_rows.append(
            ResolvedInvoiceRow(
                input_row_id=row.input_row_id,
                order_index=row.order_index,
                ma_sp=ma_sp,
                ten_sp=ten_sp,
                sl=sl_value,
                gia_ban=gia_ban_value,
                mapping_row=mapping_row,
                stock_candidates=stock_candidates,
            )
        )

    return result


def _err(row: InvoiceInputRow, error_type: str, detail: str, suggestion: str) -> RowError:
    return RowError(
        input_row_id=row.input_row_id,
        order_index=row.order_index,
        ma_sp=normalize_code(row.ma_sp),
        ten_sp=normalize_code(row.ten_sp),
        error_type=error_type,
        detail=detail,
        suggestion=suggestion,
    )
