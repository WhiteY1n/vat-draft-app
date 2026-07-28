"""Thuật toán phân bổ số lượng qua các nguồn (mục 12 CLAUDE.md).

Nguyên tắc quan trọng nhất: `remaining_stock_in_current_run` được theo dõi
trong bộ nhớ suốt một lần chạy (một lần "Tạo kết quả"), để không phân bổ
vượt quá tồn của một dòng nguồn khi cùng dòng tồn được nhiều dòng hóa đơn
sử dụng. Việc giảm tồn này KHÔNG được ghi vào file nguồn.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field

from src.accounting_group import GroupSelection
from src.config import AppConfig
from src.models import RowError, SourceAllocationDetail
from src.source_ranking import SourceRank, source_rank_order


@dataclass
class RowAllocation:
    selection: GroupSelection
    details: list[SourceAllocationDetail] = field(default_factory=list)
    ly_do_chon: str = ""
    error: RowError | None = None

    @property
    def total_allocated(self) -> float:
        return sum(d.sl_phan_bo for d in self.details)


class RunState:
    """Trạng thái tồn mô phỏng trong bộ nhớ cho một lần chạy duy nhất."""

    def __init__(self):
        self._remaining: dict[int, float] = {}

    def get_remaining(self, stock_row) -> float:
        if stock_row.row_index not in self._remaining:
            self._remaining[stock_row.row_index] = stock_row.ton_co_the_nhap
        return self._remaining[stock_row.row_index]

    def consume(self, stock_row, amount: float) -> None:
        current = self.get_remaining(stock_row)
        self._remaining[stock_row.row_index] = current - amount


def _rows_by_source(stock_rows, run_state: RunState) -> dict[str, list]:
    by_source: dict[str, list] = {}
    for s in stock_rows:
        by_source.setdefault(s.nguon, []).append(s)
    return by_source


def _source_total_remaining(rows, run_state: RunState) -> float:
    return sum(max(0.0, run_state.get_remaining(r)) for r in rows)


def _allocate_within_source(rows, need: float, run_state: RunState) -> list[SourceAllocationDetail]:
    """Phân bổ `need` đơn vị trong phạm vi các dòng tồn của MỘT nguồn.

    Sắp tồn còn lại tăng dần, ưu tiên xuất hết các dòng tồn thấp trước
    (mục 12.1 bước 3-4, mục 12.3).
    """

    details: list[SourceAllocationDetail] = []
    remaining_need = need

    sorted_rows = sorted(rows, key=lambda r: (run_state.get_remaining(r), r.row_index))

    # Nếu có một dòng riêng lẻ đủ toàn bộ `need`, ưu tiên dòng tồn thấp nhất
    # nhưng vẫn đủ (mục 12.1 bước 3), thay vì luôn dùng dòng tồn thấp nhất
    # tuyệt đối nếu nó không đủ một mình trong khi có dòng khác đủ.
    single_capable = [r for r in sorted_rows if run_state.get_remaining(r) >= need]
    if single_capable:
        row = single_capable[0]  # đã sort tăng dần -> tồn thấp nhất mà vẫn đủ
        ton_truoc = run_state.get_remaining(row)
        run_state.consume(row, need)
        details.append(
            SourceAllocationDetail(
                stock_row=row, sl_phan_bo=need, ton_truoc=ton_truoc, ton_sau=ton_truoc - need
            )
        )
        return details

    for row in sorted_rows:
        if remaining_need <= 0:
            break
        available = max(0.0, run_state.get_remaining(row))
        if available <= 0:
            continue
        take = min(available, remaining_need)
        ton_truoc = run_state.get_remaining(row)
        run_state.consume(row, take)
        details.append(
            SourceAllocationDetail(
                stock_row=row, sl_phan_bo=take, ton_truoc=ton_truoc, ton_sau=ton_truoc - take
            )
        )
        remaining_need -= take

    return details


def _best_combo(
    sources: list[str],
    remaining_by_source: dict[str, float],
    need: float,
    rank_order: dict[str, int],
) -> list[str]:
    """Tìm tổ hợp nguồn với số nguồn ít nhất có tổng tồn đủ `need`, theo
    thứ tự ưu tiên: tổng thứ hạng nguồn tốt hơn -> tổng tồn gần need hơn ->
    thứ tự tên nguồn ổn định (mục 12.2 bước 1-2).
    """

    sources_sorted = sorted(sources)  # thứ tự ổn định làm nền cho tie-break cuối

    for size in range(1, len(sources_sorted) + 1):
        combos = []
        for combo in itertools.combinations(sources_sorted, size):
            total = sum(remaining_by_source[s] for s in combo)
            if total >= need:
                rank_sum = sum(rank_order.get(s, len(rank_order)) for s in combo)
                distance = total - need
                combos.append((rank_sum, distance, combo))
        if combos:
            combos.sort(key=lambda c: (c[0], c[1], c[2]))
            return list(combos[0][2])

    return list(sources_sorted)  # không đủ tổng hợp lệ (sẽ báo lỗi ở tầng trên)


def _split_evenly(need: float, sources: list[str], remaining_by_source: dict[str, float]) -> dict[str, float]:
    """Chia `need` gần bằng nhau giữa các nguồn đã chọn (mục 12.2 bước 3-4).

    Nếu một nguồn không đủ phần chia đều, lấy tối đa tồn của nguồn đó và
    chia phần còn lại cho các nguồn còn khả năng, deterministic.
    """

    allocation: dict[str, float] = {s: 0.0 for s in sources}
    remaining_need = need
    active = list(sources)

    while remaining_need > 1e-9 and active:
        share = remaining_need / len(active)
        newly_saturated = []
        for s in active:
            cap = remaining_by_source[s] - allocation[s]
            if cap <= share + 1e-9:
                give = max(0.0, cap)
                allocation[s] += give
                remaining_need -= give
                newly_saturated.append(s)
        if newly_saturated:
            for s in newly_saturated:
                active.remove(s)
            continue

        # Không nguồn nào bị giới hạn ở vòng này -> chia đều phần còn lại.
        # Xử lý phần dư (do làm tròn) bằng cách gán vào nguồn đầu tiên (deterministic).
        base = int(remaining_need // len(active)) if remaining_need == int(remaining_need) else None
        if base is None:
            per = remaining_need / len(active)
            for s in active:
                allocation[s] += per
            remaining_need = 0.0
        else:
            per = remaining_need // len(active)
            leftover = remaining_need - per * len(active)
            for i, s in enumerate(active):
                allocation[s] += per + (1 if i < leftover else 0)
            remaining_need = 0.0
        break

    return allocation


def allocate_invoice(
    selections: list[GroupSelection],
    source_ranks: list[SourceRank],
    config: AppConfig,
) -> list[RowAllocation]:
    run_state = RunState()
    rank_order = source_rank_order(source_ranks)
    results: list[RowAllocation] = []

    # Xử lý theo đúng thứ tự hóa đơn để đảm bảo deterministic khi tranh chấp tồn.
    ordered = sorted(selections, key=lambda s: s.resolved_row.order_index)

    for sel in ordered:
        if sel.chosen_group is None:
            results.append(RowAllocation(selection=sel, error=sel.error))
            continue

        need = sel.resolved_row.sl
        rows_by_source = _rows_by_source(sel.chosen_group.stock_rows, run_state)
        remaining_by_source = {
            s: _source_total_remaining(rows, run_state) for s, rows in rows_by_source.items()
        }

        full_sources = [s for s, total in remaining_by_source.items() if total >= need]

        if full_sources:
            full_sources_sorted = sorted(full_sources, key=lambda s: rank_order.get(s, 1_000_000))
            chosen_source = full_sources_sorted[0]
            details = _allocate_within_source(rows_by_source[chosen_source], need, run_state)
            reason = (
                f"Nguồn '{chosen_source}' đủ toàn bộ SL ({need}); được chọn vì có thứ hạng "
                "nguồn cao nhất trong hóa đơn (mục 12.1)."
            )
            results.append(RowAllocation(selection=sel, details=details, ly_do_chon=reason))
            continue

        available_sources = [s for s, total in remaining_by_source.items() if total > 0]
        total_available = sum(remaining_by_source.get(s, 0.0) for s in available_sources)

        if total_available < need - 1e-9:
            error = RowError(
                input_row_id=sel.resolved_row.input_row_id,
                order_index=sel.resolved_row.order_index,
                ma_sp=sel.resolved_row.ma_sp,
                ten_sp=sel.resolved_row.ten_sp,
                error_type="tong_ton_khong_du_trong_lan_chay",
                detail=(
                    f"Tổng tồn khả dụng trong lần chạy này ({total_available}) không đủ SL "
                    f"yêu cầu ({need}), có thể do các dòng hóa đơn khác đã dùng trước."
                ),
                suggestion="Giảm SL hoặc kiểm tra lại các dòng hóa đơn dùng chung tồn.",
            )
            results.append(RowAllocation(selection=sel, error=error))
            continue

        combo = _best_combo(available_sources, remaining_by_source, need, rank_order)

        if len(combo) == 1:
            details = _allocate_within_source(rows_by_source[combo[0]], need, run_state)
            reason = f"Chỉ nguồn '{combo[0]}' đủ khả dụng cho phần còn thiếu (mục 12.2)."
            results.append(RowAllocation(selection=sel, details=details, ly_do_chon=reason))
            continue

        split = _split_evenly(need, combo, remaining_by_source)
        details: list[SourceAllocationDetail] = []
        for s in combo:
            take = split.get(s, 0.0)
            if take <= 0:
                continue
            details.extend(_allocate_within_source(rows_by_source[s], take, run_state))

        reason = (
            f"Không nguồn nào đủ toàn bộ SL; dùng {len(combo)} nguồn ít nhất có thể "
            f"({', '.join(combo)}), chia gần đều theo mục 12.2."
        )
        results.append(RowAllocation(selection=sel, details=details, ly_do_chon=reason))

    return results
