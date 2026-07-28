"""Đọc và cung cấp cấu hình tập trung cho toàn bộ app.

Mọi tham số có khả năng thay đổi (trọng số so khớp tên, tie-break nguồn,
số phiên bản lưu trữ, số chữ số thập phân...) phải được đọc từ đây,
không hard-code rải rác trong code nghiệp vụ.
"""

from __future__ import annotations

import functools
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "settings.yaml"


@dataclass
class NameMatchWeights:
    """Trọng số so khớp tên kế toán (mục 10.1 CLAUDE.md)."""

    weight_user_ten_sp: float = 0.45
    weight_khopma_ten_sp: float = 0.25
    weight_ten_vat_kiot: float = 0.20
    weight_ten_truoc_vat: float = 0.10

    number_token_bonus: float = 8.0
    size_token_bonus: float = 6.0
    number_conflict_penalty: float = 25.0
    variant_conflict_penalty: float = 15.0

    review_threshold: float = 55.0


@dataclass
class AppConfig:
    auth_mode: str = "none"
    allowed_emails: list[str] = field(default_factory=list)
    admin_emails: list[str] = field(default_factory=list)

    max_versions_kept: int = 14
    gia_nhap_decimal_places: int = 2
    allow_fractional_sl: bool = False

    source_tiebreak_priority: list[str] = field(default_factory=list)

    name_match: NameMatchWeights = field(default_factory=NameMatchWeights)

    local_storage_root: str = "data/local_storage"

    raw: dict[str, Any] = field(default_factory=dict)


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@functools.lru_cache(maxsize=1)
def load_config(config_path: str | None = None) -> AppConfig:
    """Nạp cấu hình từ config/settings.yaml (có thể override bằng biến môi trường).

    Kết quả được cache; gọi ``load_config.cache_clear()`` nếu cần nạp lại
    (ví dụ sau khi người dùng sửa file cấu hình trong trang Cấu hình).
    """

    path = Path(config_path) if config_path else _DEFAULT_CONFIG_PATH
    raw = _read_yaml(path)

    nm_raw = raw.get("name_match_weights", {})
    name_match = NameMatchWeights(
        weight_user_ten_sp=nm_raw.get("weight_user_ten_sp", 0.45),
        weight_khopma_ten_sp=nm_raw.get("weight_khopma_ten_sp", 0.25),
        weight_ten_vat_kiot=nm_raw.get("weight_ten_vat_kiot", 0.20),
        weight_ten_truoc_vat=nm_raw.get("weight_ten_truoc_vat", 0.10),
        number_token_bonus=nm_raw.get("number_token_bonus", 8.0),
        size_token_bonus=nm_raw.get("size_token_bonus", 6.0),
        number_conflict_penalty=nm_raw.get("number_conflict_penalty", 25.0),
        variant_conflict_penalty=nm_raw.get("variant_conflict_penalty", 15.0),
        review_threshold=nm_raw.get("review_threshold", 55.0),
    )

    auth_mode = os.environ.get("AUTH_MODE", raw.get("auth_mode", "none"))
    allowed_emails_env = os.environ.get("ALLOWED_EMAILS")
    admin_emails_env = os.environ.get("ADMIN_EMAILS")

    allowed_emails = (
        [e.strip() for e in allowed_emails_env.split(",") if e.strip()]
        if allowed_emails_env
        else raw.get("allowed_emails", [])
    )
    admin_emails = (
        [e.strip() for e in admin_emails_env.split(",") if e.strip()]
        if admin_emails_env
        else raw.get("admin_emails", [])
    )

    return AppConfig(
        auth_mode=auth_mode,
        allowed_emails=allowed_emails,
        admin_emails=admin_emails,
        max_versions_kept=raw.get("max_versions_kept", 14),
        gia_nhap_decimal_places=raw.get("gia_nhap_decimal_places", 2),
        allow_fractional_sl=raw.get("allow_fractional_sl", False),
        source_tiebreak_priority=raw.get("source_tiebreak_priority", []),
        name_match=name_match,
        local_storage_root=os.environ.get(
            "LOCAL_STORAGE_ROOT", raw.get("local_storage_root", "data/local_storage")
        ),
        raw=raw,
    )
