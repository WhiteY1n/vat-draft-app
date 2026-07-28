"""Các model dữ liệu nghiệp vụ dùng chung giữa các module.

Không đặt logic UI ở đây. Đây là các cấu trúc dữ liệu thuần (dataclass).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class StockRow:
    """Một dòng trong sheet `Gộp VAT` (đã được chuẩn hóa)."""

    row_index: int  # số dòng gốc trong Excel (1-based, kể cả header) để truy vết lỗi
    nguon: str
    ma_kiot_dai_dien: str
    ten_kiot_dai_dien: str
    ma_vat_kiot: str
    ten_vat_kiot: str
    ten_ke_toan: str
    don_vi_tinh: str
    ton_dau_ngay: Optional[float]
    gia_ban: Optional[float]
    thue_vat: Optional[float]
    thue_nk: Optional[float]
    tong_thue_mat: Optional[float]
    tong_dang_nhap: float
    ton_co_the_nhap: float

    # Khóa chuẩn hóa dùng để so khớp, không phân biệt hoa/thường và khoảng trắng.
    ma_vat_kiot_norm: str = ""
    ten_ke_toan_norm: str = ""
    don_vi_tinh_norm: str = ""


@dataclass
class MappingRow:
    """Một dòng trong sheet `Khớp mã` (đã được chuẩn hóa)."""

    row_index: int
    ma_sp: str
    ten_sp: str
    ma_vat_kiot: str
    ten_truoc_vat: str

    ma_sp_norm: str = ""
    ma_vat_kiot_norm: str = ""


@dataclass
class InvoiceInputRow:
    """Một dòng hóa đơn người dùng dán vào app."""

    input_row_id: str
    order_index: int  # thứ tự xuất hiện trong hóa đơn, phải được giữ nguyên
    ma_sp: str
    ten_sp: str
    sl: Any  # giữ nguyên dạng thô để hiển thị trước khi ép kiểu
    gia_ban: Any


@dataclass
class RowError:
    input_row_id: str
    order_index: int
    ma_sp: str
    ten_sp: str
    error_type: str
    detail: str
    suggestion: str = ""


@dataclass
class DataWarning:
    """Cảnh báo không chặn (dùng cho báo cáo kiểm tra dữ liệu nguồn)."""

    row_index: int
    warning_type: str
    detail: str


@dataclass
class AccountingGroupCandidate:
    """Một nhóm (TÊN KẾ TOÁN, Đơn vị tính) ứng viên cho một dòng hóa đơn."""

    ten_ke_toan: str
    don_vi_tinh: str
    stock_rows: list[StockRow]
    name_score: float
    total_ton: float
    score_reasons: list[str] = field(default_factory=list)


@dataclass
class SourceAllocationDetail:
    """Chi tiết phân bổ tại một dòng tồn cụ thể."""

    stock_row: StockRow
    sl_phan_bo: float
    ton_truoc: float
    ton_sau: float


@dataclass
class AllocationResultLine:
    """Một dòng trong kết quả xuất ra (mục 13 CLAUDE.md)."""

    stt_hoa_don: int
    dong_phan_bo: int
    ma_sp: str
    ten_sp: str
    sl_yeu_cau: float
    sl_phan_bo: float
    gia_ban: float
    ma_vat: str
    ten_vat: str
    ten_ke_toan: str
    dvt: str
    nguon: str
    ton_con_nhap_truoc: float
    ton_con_mo_phong_sau: float
    phan_tram_vat: Optional[float]
    gia_nhap: Optional[float]
    diem_khop_ten: float
    ly_do_chon: str
