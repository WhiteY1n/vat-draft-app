"""Đăng nhập và phân quyền (mục 6 CLAUDE.md).

`AUTH_MODE=none`: dùng cho phát triển, mọi người đều là Admin (không có
đăng nhập thật). `AUTH_MODE=google`: dự kiến dùng Google OpenID Connect khi
triển khai thật (Milestone 5) — phần xác thực Google chưa triển khai đầy đủ
trong MVP này; module chỉ cung cấp khung để cắm vào sau, cùng với việc phân
quyền Admin/User theo danh sách email trong cấu hình/biến môi trường.

Không hard-code email trong code.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from src.config import AppConfig


class Role(str, Enum):
    USER = "user"
    ADMIN = "admin"


@dataclass
class CurrentUser:
    email: str | None
    role: Role
    is_authenticated: bool


def resolve_role(email: str | None, config: AppConfig) -> Role:
    if email and email.strip().lower() in {e.lower() for e in config.admin_emails}:
        return Role.ADMIN
    return Role.USER


def get_current_user(config: AppConfig, session_email: str | None = None) -> CurrentUser:
    """Trả về người dùng hiện tại theo AUTH_MODE.

    - `none`: không yêu cầu đăng nhập; coi như Admin để thuận tiện phát triển.
    - `google`: yêu cầu `session_email` (đã xác thực OIDC ở lớp trên) nằm
      trong danh sách `allowed_emails`; nếu chưa đăng nhập, trả về user chưa
      xác thực.
    """

    if config.auth_mode == "none":
        return CurrentUser(email=session_email, role=Role.ADMIN, is_authenticated=True)

    if config.auth_mode == "google":
        if not session_email:
            return CurrentUser(email=None, role=Role.USER, is_authenticated=False)
        allowed = {e.lower() for e in config.allowed_emails} | {
            e.lower() for e in config.admin_emails
        }
        if allowed and session_email.strip().lower() not in allowed:
            return CurrentUser(email=session_email, role=Role.USER, is_authenticated=False)
        return CurrentUser(
            email=session_email,
            role=resolve_role(session_email, config),
            is_authenticated=True,
        )

    raise ValueError(f"AUTH_MODE không hợp lệ: {config.auth_mode}")
