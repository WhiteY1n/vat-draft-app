"""Interface storage để hỗ trợ nhiều backend (mục 3, 5.4 CLAUDE.md).

`LocalStorageAdapter` dùng khi phát triển/kiểm thử.
`SupabaseStorageAdapter` dùng khi triển khai web (Milestone 5, chưa triển khai đầy đủ).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FileVersionMetadata:
    version_id: str
    original_file_name: str
    uploaded_at: str  # ISO 8601
    uploaded_by: str | None
    sha256: str
    gop_vat_row_count: int
    khop_ma_row_count: int
    check_status: str  # "valid" | "invalid"
    is_current: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


class StorageAdapter(ABC):
    """Interface tối thiểu để lưu file Excel và metadata phiên bản."""

    @abstractmethod
    def save_version_file(self, version_id: str, file_bytes: bytes, file_name: str) -> str:
        """Lưu nội dung file của một phiên bản. Trả về path/khóa lưu trữ."""

    @abstractmethod
    def load_version_file(self, version_id: str) -> bytes:
        """Đọc lại nội dung file nhị phân của một phiên bản."""

    @abstractmethod
    def get_version_file_path(self, version_id: str) -> str:
        """Trả về đường dẫn cục bộ (hoặc URL) để mở file bằng openpyxl."""

    @abstractmethod
    def save_metadata(self, metadata: FileVersionMetadata) -> None:
        ...

    @abstractmethod
    def list_versions(self) -> list[FileVersionMetadata]:
        ...

    @abstractmethod
    def get_current_version_id(self) -> str | None:
        ...

    @abstractmethod
    def set_current_version_id(self, version_id: str) -> None:
        ...

    @abstractmethod
    def delete_version(self, version_id: str) -> None:
        ...
