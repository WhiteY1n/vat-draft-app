"""Các hàm chuẩn hóa dùng chung: mã sản phẩm, mã VAT, tên, số liệu.

Toàn bộ deterministic, không dùng AI.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Bảng alias cột (mục 4.2 CLAUDE.md): cho phép khác biệt hoa/thường, khoảng
# trắng trong tên cột mà không phải sửa nhiều nơi trong code.
# ---------------------------------------------------------------------------

GOP_VAT_COLUMN_ALIASES: dict[str, list[str]] = {
    "NGUỒN": ["nguồn", "nguon"],
    "Mã kiot đại diện": ["mã kiot đại diện", "ma kiot dai dien"],
    "Tên kiot đại diện": ["tên kiot đại diện", "ten kiot dai dien"],
    "MÃ VAT KIOT": ["mã vat kiot", "ma vat kiot"],
    "TÊN VAT KIOT": ["tên vat kiot", "ten vat kiot"],
    "MÃ KT": ["mã kt", "ma kt"],
    "TÊN KẾ TOÁN": ["tên kế toán", "ten ke toan", "tên hàng", "tên kt", "ten kt"],
    "Đơn vị tính": ["đơn vị tính", "don vi tinh", "đvt"],
    "TỒN ĐẦU NGÀY": ["tồn đầu ngày", "ton dau ngay"],
    "GIÁ BÁN": ["giá bán", "gia ban"],
    "THUẾ VAT": ["thuế vat", "thue vat"],
    "THUẾ NK": ["thuế nk", "thue nk"],
    "TỔNG THUẾ MẤT": ["tổng thuế mất", "tong thue mat"],
    "TỔNG ĐANG NHÁP": ["tổng đang nháp", "tong dang nhap"],
    "TỒN CÓ THỂ NHÁP": ["tồn có thể nháp", "ton co the nhap"],
}

KHOP_MA_COLUMN_ALIASES: dict[str, list[str]] = {
    "Mã SP": ["mã sp", "ma sp"],
    "Tên SP": ["tên sp", "ten sp"],
    "Mã vat kiot": ["mã vat kiot", "ma vat kiot"],
    "Tên trước (Giá đầu  - Giá cuối) (VAT)": [
        "tên trước (giá đầu  - giá cuối) (vat)",
        "tên trước (giá đầu - giá cuối) (vat)",
        "ten truoc (gia dau - gia cuoi) (vat)",
    ],
}


def _fold_header(value: str) -> str:
    return re.sub(r"\s+", " ", str(value).strip().lower())


def resolve_column_name(header_row: list, aliases: dict[str, list[str]]) -> dict[str, int]:
    """Tìm vị trí cột thực tế trong file dựa trên bảng alias.

    Trả về dict: tên cột chuẩn -> chỉ số cột (0-based). Cột không tìm thấy sẽ
    không có trong dict trả về (để caller báo lỗi thiếu cột).
    """

    folded_headers = {_fold_header(h): idx for idx, h in enumerate(header_row) if h is not None}
    result: dict[str, int] = {}
    for canonical, alias_list in aliases.items():
        candidates = [_fold_header(canonical)] + [_fold_header(a) for a in alias_list]
        for cand in candidates:
            if cand in folded_headers:
                result[canonical] = folded_headers[cand]
                break
    return result


# ---------------------------------------------------------------------------
# Chuẩn hóa mã (Mã SP, Mã VAT kiot...)
# ---------------------------------------------------------------------------


def normalize_code(value) -> str:
    """Chuẩn hóa mã: chuỗi, strip, chuẩn hóa unicode, không phân biệt hoa/thường
    khi so khớp (trả về dạng upper để so sánh, giữ bản gốc ở nơi khác nếu cần).
    """

    if value is None:
        return ""
    text = str(value)
    text = unicodedata.normalize("NFC", text)
    text = text.strip()
    return text


def normalize_code_for_match(value) -> str:
    """Dạng dùng để SO KHỚP: không phân biệt hoa/thường, gộp khoảng trắng."""

    text = normalize_code(value)
    text = re.sub(r"\s+", " ", text)
    return text.casefold()


# ---------------------------------------------------------------------------
# Chuẩn hóa số
# ---------------------------------------------------------------------------


def to_float_or_none(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            if value != value:  # NaN
                return None
        except TypeError:
            pass
        return float(value)
    text = str(value).strip()
    if text == "":
        return None
    text = text.replace(",", "").replace(" ", "")
    is_percent = text.endswith("%")
    if is_percent:
        text = text[:-1]
    try:
        val = float(text)
        return val / 100.0 if is_percent else val
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Chuẩn hóa tên để so khớp (mục 10.1 CLAUDE.md)
# ---------------------------------------------------------------------------

_VN_DIACRITICS_MAP = None


def _strip_diacritics(text: str) -> str:
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = text.replace("đ", "d").replace("Đ", "D")
    return unicodedata.normalize("NFC", text)


_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_MULTI_SPACE_RE = re.compile(r"\s+")
# token dạng số + đơn vị, ví dụ: 1l, 1.5l, 10cm, 220v, 02, 500ml
_NUMBER_UNIT_TOKEN_RE = re.compile(
    r"^(\d+(?:[.,]\d+)?)\s*(ml|l|cm|mm|m|kg|g|w|v|hz|inch|cai|bo)?$"
)


@dataclass
class NormalizedName:
    raw: str
    cleaned_text: str  # đã bỏ dấu, chữ thường, bỏ dấu câu, gộp khoảng trắng
    word_tokens: list[str]
    number_tokens: list[str]  # token số/kích thước/đơn vị (giữ nguyên dạng chuẩn hóa)


def _normalize_leading_zero(token: str) -> str:
    """Chuẩn hóa '02' và '2' khi phù hợp: bỏ số 0 ở đầu (nếu còn số) để so khớp."""

    m = re.match(r"^0+(\d+)$", token)
    if m:
        return m.group(1)
    return token


def normalize_name_for_matching(value) -> NormalizedName:
    raw = "" if value is None else str(value)
    text = raw.strip()
    text = _strip_diacritics(text)
    text = text.lower()
    text = _PUNCT_RE.sub(" ", text)
    text = _MULTI_SPACE_RE.sub(" ", text).strip()

    tokens = text.split(" ") if text else []
    word_tokens: list[str] = []
    number_tokens: list[str] = []
    for tok in tokens:
        if not tok:
            continue
        m = _NUMBER_UNIT_TOKEN_RE.match(tok)
        if m:
            num = _normalize_leading_zero(m.group(1).replace(",", "."))
            unit = m.group(2) or ""
            number_tokens.append(f"{num}{unit}")
        elif re.match(r"^\d+$", tok):
            number_tokens.append(_normalize_leading_zero(tok))
        else:
            word_tokens.append(tok)

    return NormalizedName(
        raw=raw,
        cleaned_text=" ".join(word_tokens),
        word_tokens=word_tokens,
        number_tokens=number_tokens,
    )


def strip_price_and_vat_suffix(ten_truoc_vat: str) -> str:
    """Bỏ phần giá (trong ngoặc) và chữ 'VAT' khỏi
    `Tên trước (Giá đầu - Giá cuối) (VAT)` để dùng cho so khớp tên.

    Ví dụ: "Ấm giữ nhiệt 1000ML (72,100 - 78,500) (VAT)" -> "Ấm giữ nhiệt 1000ML"
    """

    if not ten_truoc_vat:
        return ""
    text = re.sub(r"\([^)]*\)", "", str(ten_truoc_vat))
    text = re.sub(r"\bVAT\b", "", text, flags=re.IGNORECASE)
    return _MULTI_SPACE_RE.sub(" ", text).strip()
