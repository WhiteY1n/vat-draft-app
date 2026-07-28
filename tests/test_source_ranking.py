from src.accounting_group import select_accounting_group_for_row
from src.config import AppConfig
from src.mapping import MappingLookup
from src.source_ranking import rank_sources_in_invoice
from src.validation import validate_invoice_rows
from tests.factories import make_input_row, make_mapping_row, make_stock_row


def _selections(rows, stock, mapping, config):
    lookup = MappingLookup.build(mapping, stock)
    validation = validate_invoice_rows(rows, lookup, config)
    assert not validation.has_blocking_errors, validation.errors
    return [select_accounting_group_for_row(r, config) for r in validation.resolved_rows]


def test_source_appearing_in_more_lines_ranks_higher():
    config = AppConfig()
    mapping = [
        make_mapping_row(2, "A1", "SP A", "VAT1"),
        make_mapping_row(3, "A2", "SP B", "VAT2"),
    ]
    stock = [
        make_stock_row(2, "MAY", "VAT1", "Ten KT A", "Cái", 100),
        make_stock_row(3, "CAO", "VAT1", "Ten KT A", "Cái", 100),
        make_stock_row(4, "MAY", "VAT2", "Ten KT B", "Cái", 100),
    ]
    rows = [
        make_input_row(1, "A1", "SP A", 10, 1000),
        make_input_row(2, "A2", "SP B", 10, 1000),
    ]
    selections = _selections(rows, stock, mapping, config)
    ranks = rank_sources_in_invoice(selections, config)
    ranked_names = [r.nguon for r in ranks]
    assert ranked_names[0] == "MAY"  # đủ toàn bộ SL ở cả 2 dòng hóa đơn


def test_tiebreak_priority_used_when_counts_equal():
    config = AppConfig(source_tiebreak_priority=["Vận chuyển", "CAO"])
    mapping = [make_mapping_row(2, "A1", "SP A", "VAT1")]
    stock = [
        make_stock_row(2, "CAO", "VAT1", "Ten KT A", "Cái", 100),
        make_stock_row(3, "Vận chuyển", "VAT1", "Ten KT A", "Cái", 100),
    ]
    rows = [make_input_row(1, "A1", "SP A", 10, 1000)]
    selections = _selections(rows, stock, mapping, config)
    ranks = rank_sources_in_invoice(selections, config)
    assert ranks[0].nguon == "Vận chuyển"
