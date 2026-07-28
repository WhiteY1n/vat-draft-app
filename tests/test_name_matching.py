from src.config import NameMatchWeights
from src.name_matching import calculate_accounting_name_score


def _weights():
    return NameMatchWeights()


def test_higher_similarity_scores_higher():
    w = _weights()
    good = calculate_accounting_name_score(
        ten_ke_toan="Bông tẩy trang 222 miếng",
        user_ten_sp="Bông tẩy trang VÀNG 222 miếng",
        khop_ma_ten_sp="Bông tẩy trang VÀNG 222 miếng",
        ten_vat_kiot="Bông tẩy trang",
        ten_truoc_vat_raw="Bông tẩy trang (11,200 - 12,100) (VAT)",
        weights=w,
    )
    bad = calculate_accounting_name_score(
        ten_ke_toan="Bàn chải đánh răng",
        user_ten_sp="Bông tẩy trang VÀNG 222 miếng",
        khop_ma_ten_sp="Bông tẩy trang VÀNG 222 miếng",
        ten_vat_kiot="Bông tẩy trang",
        ten_truoc_vat_raw="Bông tẩy trang (11,200 - 12,100) (VAT)",
        weights=w,
    )
    assert good.score > bad.score


def test_number_conflict_penalizes_score():
    w = _weights()
    matching_size = calculate_accounting_name_score(
        ten_ke_toan="Ấm giữ nhiệt 1000ml",
        user_ten_sp="Ấm giữ nhiệt 1000ml Hoa",
        khop_ma_ten_sp="Ấm giữ nhiệt Hoa 1L",
        ten_vat_kiot="Ấm giữ nhiệt",
        ten_truoc_vat_raw="Ấm giữ nhiệt 1000ML (1-2) (VAT)",
        weights=w,
    )
    conflicting_size = calculate_accounting_name_score(
        ten_ke_toan="Ấm giữ nhiệt 500ml",
        user_ten_sp="Ấm giữ nhiệt 1000ml Hoa",
        khop_ma_ten_sp="Ấm giữ nhiệt Hoa 1L",
        ten_vat_kiot="Ấm giữ nhiệt",
        ten_truoc_vat_raw="Ấm giữ nhiệt 1000ML (1-2) (VAT)",
        weights=w,
    )
    assert matching_size.score > conflicting_size.score


def test_score_is_deterministic():
    w = _weights()
    args = dict(
        ten_ke_toan="Móc dán tường đa năng",
        user_ten_sp="Móc dán tường dùng để treo đồ đa năng",
        khop_ma_ten_sp="Móc dán tường đa năng 1 mặt",
        ten_vat_kiot="Móc dán tường",
        ten_truoc_vat_raw="Móc dán tường (1-2) (VAT)",
        weights=w,
    )
    r1 = calculate_accounting_name_score(**args)
    r2 = calculate_accounting_name_score(**args)
    assert r1.score == r2.score
