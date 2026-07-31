from src.models import AllocationResultLine
from src.result_builder import CHECK_RESULT_COLUMNS, build_check_result_rows


def test_check_result_rows_match_business_table_columns():
    line = AllocationResultLine(
        stt_hoa_don=1,
        dong_phan_bo=1,
        ma_sp="DCGSM",
        ten_sp="Đai chống gù size M",
        sl_yeu_cau=2200,
        sl_phan_bo=2200,
        gia_ban=6908,
        ma_vat="VAT10655",
        ten_vat="Đai chống gù (13,100 - 14,200) (VAT)",
        ten_ke_toan="Đai đeo lưng chống gù",
        dvt="Cái",
        nguon="Vận chuyển",
        ton_con_nhap_truoc=2200,
        ton_con_mo_phong_sau=0,
        phan_tram_vat=0.08,
        gia_nhap=6396.3,
        diem_khop_ten=90,
        ly_do_chon="",
    )

    rows = build_check_result_rows([line])

    assert list(rows[0]) == CHECK_RESULT_COLUMNS
    assert rows[0]["SL"] == 2200
    assert rows[0]["TỒN CÒN NHÁP"] == 2200
    assert rows[0]["%VAT"] == 8
    assert "SL phân bổ" not in rows[0]
    assert "TỒN CÒN MÔ PHỎNG SAU" not in rows[0]
