"""Test đọc hóa đơn GTGT điện tử PDF (trang Tạo QR)."""

from src.invoice_pdf_reader import parse_invoice_text

# Text thật trích từ pypdf cho 2 hóa đơn mẫu (mẹ và bé VC.pdf, mẹ và bé SHC.pdf).
_VC_INVOICE_TEXT = (
    "Ký hiệu(Serial No):1C26TVC\nSố(No.):\n"
    "Đơn vị bán hàng(Seller): CÔNG TY CỔ PHẦN THƯƠNG MẠI VC EXPRESS\n"
    "Mã số thuế/Mã đơn vị quan hệ ngân sách(Tax code):0111302750\n"
    "Địa chỉ(Address):Tầng 15 tháp B tòa nhà Sông Đà\n"
    "Họ tên người mua hàng(Buyer's fullname):\n"
    "Tên đơn vị(Company's name):HỘ KINH DOANH MẸ VÀ BÉ NGUYỄN TÙNG\n"
    "Cộng tiền hàng(Total amount): 4.490.800\n"
    "Thuế suất GTGT(VAT Rate): 8% Tiền thuế GTGT(VAT amount): 359.264\n"
    "Tổng cộng tiền thanh toán(Total payment): 4.850.064"
)

_SHC_INVOICE_TEXT = (
    "Ký hiệu(Serial No):1C26THC\nSố(No.):\n"
    "Đơn vị bán hàng(Seller): CÔNG TY CỔ PHẦN THƯƠNG MẠI TỔNG HỢP SHC GROUP\n"
    "Mã số thuế/Mã đơn vị quan hệ ngân sách(Tax code):0319502477\n"
    "Cộng tiền hàng(Total amount): 1.050.000\n"
    "Thuế suất GTGT(VAT Rate): 8% Tiền thuế GTGT(VAT amount): 84.000\n"
    "Tổng cộng tiền thanh toán(Total payment): 1.134.000"
)


def test_parse_invoice_text_extracts_seller_and_total_payment_vc():
    parsed = parse_invoice_text(_VC_INVOICE_TEXT)

    assert parsed.error is None
    assert parsed.seller_name == "CÔNG TY CỔ PHẦN THƯƠNG MẠI VC EXPRESS"
    assert parsed.total_payment == 4_850_064
    assert parsed.total_before_vat == 4_490_800
    assert parsed.vat_amount == 359_264
    assert parsed.serial_no == "1C26TVC"


def test_parse_invoice_text_extracts_seller_and_total_payment_shc():
    parsed = parse_invoice_text(_SHC_INVOICE_TEXT)

    assert parsed.error is None
    assert parsed.seller_name == "CÔNG TY CỔ PHẦN THƯƠNG MẠI TỔNG HỢP SHC GROUP"
    assert parsed.total_payment == 1_134_000


def test_parse_invoice_text_empty_text_returns_error():
    parsed = parse_invoice_text("")

    assert parsed.error is not None
    assert parsed.total_payment is None


def test_parse_invoice_text_unrecognized_content_returns_error():
    parsed = parse_invoice_text("Đây là một văn bản bất kỳ không phải hóa đơn.")

    assert parsed.error is not None
