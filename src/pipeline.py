"""Điều phối toàn bộ luồng xử lý một hóa đơn, từ dữ liệu dán vào đến kết quả.

Đây là điểm vào duy nhất mà UI (Streamlit) và test end-to-end nên gọi, để
logic nghiệp vụ không bị lặp lại hoặc đặt trong callback UI.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.accounting_group import GroupSelection, select_accounting_group_for_row
from src.allocation import allocate_invoice
from src.config import AppConfig
from src.mapping import MappingLookup
from src.models import AllocationResultLine, InvoiceInputRow, MappingRow, RowError, StockRow
from src.result_builder import build_result_lines
from src.source_ranking import SourceRank, rank_sources_in_invoice
from src.validation import ValidationResult, validate_invoice_rows


@dataclass
class ProcessInvoiceResult:
    is_valid: bool
    errors: list[RowError] = field(default_factory=list)
    result_lines: list[AllocationResultLine] = field(default_factory=list)
    source_ranks: list[SourceRank] = field(default_factory=list)
    selections: list[GroupSelection] = field(default_factory=list)

    @property
    def total_sl_yeu_cau(self) -> float:
        seen = set()
        total = 0.0
        for line in self.result_lines:
            if line.stt_hoa_don in seen:
                continue
            seen.add(line.stt_hoa_don)
            total += line.sl_yeu_cau
        return total

    @property
    def total_sl_phan_bo(self) -> float:
        return sum(line.sl_phan_bo for line in self.result_lines)


def process_invoice(
    rows: list[InvoiceInputRow],
    stock_rows: list[StockRow],
    mapping_rows: list[MappingRow],
    config: AppConfig,
) -> ProcessInvoiceResult:
    lookup = MappingLookup.build(mapping_rows, stock_rows)

    validation: ValidationResult = validate_invoice_rows(rows, lookup, config)
    if validation.has_blocking_errors:
        return ProcessInvoiceResult(is_valid=False, errors=validation.errors)

    if not validation.resolved_rows:
        return ProcessInvoiceResult(is_valid=False, errors=[])

    selections: list[GroupSelection] = [
        select_accounting_group_for_row(r, config) for r in validation.resolved_rows
    ]

    group_errors = [s.error for s in selections if s.error is not None]
    if group_errors:
        return ProcessInvoiceResult(is_valid=False, errors=group_errors, selections=selections)

    source_ranks = rank_sources_in_invoice(selections, config)
    allocations = allocate_invoice(selections, source_ranks, config)

    allocation_errors = [a.error for a in allocations if a.error is not None]
    if allocation_errors:
        return ProcessInvoiceResult(
            is_valid=False, errors=allocation_errors, selections=selections, source_ranks=source_ranks
        )

    result_lines = build_result_lines(allocations, config)

    return ProcessInvoiceResult(
        is_valid=True,
        result_lines=result_lines,
        source_ranks=source_ranks,
        selections=selections,
    )
