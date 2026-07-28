"""Xếp hạng NGUỒN trong phạm vi hóa đơn hiện tại (mục 11 CLAUDE.md).

Việc ưu tiên nguồn được tính trong phạm vi hóa đơn hiện tại, không tính
trên toàn bộ file dữ liệu.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.accounting_group import GroupSelection
from src.config import AppConfig


@dataclass
class SourceRank:
    nguon: str
    full_coverage_count: int
    partial_coverage_count: int
    tiebreak_priority_index: int
    rank_key: tuple = field(default_factory=tuple)


def rank_sources_in_invoice(
    selections: list[GroupSelection], config: AppConfig
) -> list[SourceRank]:
    """Tính full/partial coverage cho mỗi NGUỒN xuất hiện trong hóa đơn,
    dựa trên accounting_identity_group đã chọn cho từng dòng hóa đơn.
    """

    full_coverage: dict[str, int] = {}
    partial_coverage: dict[str, int] = {}
    all_sources: set[str] = set()

    priority_list = [p.strip().lower() for p in config.source_tiebreak_priority]

    for sel in selections:
        if sel.chosen_group is None:
            continue
        sl_yeu_cau = sel.resolved_row.sl

        ton_by_source: dict[str, float] = {}
        for stock_row in sel.chosen_group.stock_rows:
            ton_by_source[stock_row.nguon] = ton_by_source.get(stock_row.nguon, 0.0) + (
                stock_row.ton_co_the_nhap
            )

        for nguon, ton in ton_by_source.items():
            all_sources.add(nguon)
            if ton >= sl_yeu_cau:
                full_coverage[nguon] = full_coverage.get(nguon, 0) + 1
            elif ton > 0:
                partial_coverage[nguon] = partial_coverage.get(nguon, 0) + 1

    ranks: list[SourceRank] = []
    for nguon in all_sources:
        try:
            tb_idx = priority_list.index(nguon.strip().lower())
        except ValueError:
            tb_idx = len(priority_list)  # nguồn không có trong danh sách -> xếp sau

        ranks.append(
            SourceRank(
                nguon=nguon,
                full_coverage_count=full_coverage.get(nguon, 0),
                partial_coverage_count=partial_coverage.get(nguon, 0),
                tiebreak_priority_index=tb_idx,
            )
        )

    ranks.sort(
        key=lambda r: (
            -r.full_coverage_count,
            -r.partial_coverage_count,
            r.tiebreak_priority_index,
            r.nguon,
        )
    )
    return ranks


def source_rank_order(ranks: list[SourceRank]) -> dict[str, int]:
    """Trả về dict: tên nguồn -> thứ hạng (0 = cao nhất)."""

    return {r.nguon: idx for idx, r in enumerate(ranks)}
