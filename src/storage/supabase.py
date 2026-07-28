"""SupabaseStorageAdapter: dự kiến dùng khi triển khai web (Milestone 5).

Chưa triển khai đầy đủ trong phiên bản MVP này (theo CLAUDE.md: "Không bắt
đầu Supabase hoặc Google login cho đến khi phiên bản local đã chạy ổn").
Giữ lại interface để không phải viết lại logic nghiệp vụ khi chuyển sang
Supabase — chỉ cần cài đặt các phương thức bên dưới.
"""

from __future__ import annotations

from src.storage.base import FileVersionMetadata, StorageAdapter


class SupabaseStorageAdapter(StorageAdapter):
    def __init__(self, supabase_url: str, supabase_key: str, bucket: str = "vat-draft-versions"):
        self.supabase_url = supabase_url
        self.supabase_key = supabase_key
        self.bucket = bucket
        raise NotImplementedError(
            "SupabaseStorageAdapter chưa được triển khai (dự kiến Milestone 5). "
            "Dùng LocalStorageAdapter cho môi trường local."
        )

    def save_version_file(self, version_id: str, file_bytes: bytes, file_name: str) -> str:
        raise NotImplementedError

    def load_version_file(self, version_id: str) -> bytes:
        raise NotImplementedError

    def get_version_file_path(self, version_id: str) -> str:
        raise NotImplementedError

    def save_metadata(self, metadata: FileVersionMetadata) -> None:
        raise NotImplementedError

    def list_versions(self) -> list[FileVersionMetadata]:
        raise NotImplementedError

    def get_current_version_id(self) -> str | None:
        raise NotImplementedError

    def set_current_version_id(self, version_id: str) -> None:
        raise NotImplementedError

    def delete_version(self, version_id: str) -> None:
        raise NotImplementedError
