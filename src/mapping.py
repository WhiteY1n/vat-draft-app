"""Tra cứu Mã SP -> Mã VAT -> danh sách ứng viên tồn (mục 9 CLAUDE.md).

Không dùng fuzzy matching cho mã sản phẩm hoặc mã VAT — chỉ so khớp chính xác
(sau khi chuẩn hóa: strip, unicode NFC, không phân biệt hoa/thường).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.models import MappingRow, StockRow
from src.normalization import normalize_code_for_match


@dataclass
class MappingLookup:
    mapping_by_ma_sp: dict[str, list[MappingRow]] = field(default_factory=dict)
    stock_by_ma_vat: dict[str, list[StockRow]] = field(default_factory=dict)
    all_stock_by_ma_vat: dict[str, list[StockRow]] = field(default_factory=dict)

    @classmethod
    def build(cls, mapping_rows: list[MappingRow], stock_rows: list[StockRow]) -> "MappingLookup":
        mapping_by_ma_sp: dict[str, list[MappingRow]] = {}
        for m in mapping_rows:
            if not m.ma_sp_norm:
                continue
            mapping_by_ma_sp.setdefault(m.ma_sp_norm, []).append(m)

        stock_by_ma_vat: dict[str, list[StockRow]] = {}
        all_stock_by_ma_vat: dict[str, list[StockRow]] = {}
        for s in stock_rows:
            if not s.ma_vat_kiot_norm:
                continue
            all_stock_by_ma_vat.setdefault(s.ma_vat_kiot_norm, []).append(s)
            if s.ton_co_the_nhap <= 0:
                continue  # loại ứng viên có tồn <= 0 (mục 9 bước 6)
            stock_by_ma_vat.setdefault(s.ma_vat_kiot_norm, []).append(s)

        return cls(
            mapping_by_ma_sp=mapping_by_ma_sp,
            stock_by_ma_vat=stock_by_ma_vat,
            all_stock_by_ma_vat=all_stock_by_ma_vat,
        )

    def find_mapping(self, ma_sp: str) -> list[MappingRow]:
        return self.mapping_by_ma_sp.get(normalize_code_for_match(ma_sp), [])

    def find_stock_candidates(self, ma_vat_kiot_norm: str) -> list[StockRow]:
        return self.stock_by_ma_vat.get(ma_vat_kiot_norm, [])

    def find_all_stock_rows(self, ma_vat_kiot_norm: str) -> list[StockRow]:
        """Trả về cả các dòng tồn 0/âm để phân biệt hết tồn với sai Mã VAT."""

        return self.all_stock_by_ma_vat.get(ma_vat_kiot_norm, [])

    def distinct_ma_vat_for(self, ma_sp: str) -> set[str]:
        return {m.ma_vat_kiot_norm for m in self.find_mapping(ma_sp) if m.ma_vat_kiot_norm}
