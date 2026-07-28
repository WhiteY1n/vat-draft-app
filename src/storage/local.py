"""LocalStorageAdapter: lưu file và metadata trên đĩa cục bộ (mục 5, 5.4).

Metadata lưu dưới dạng JSON, không cần database ở MVP.
Việc thay đổi con trỏ `current` mang tính atomic: ghi file tạm rồi
`os.replace` để không bao giờ có trạng thái file hỏng giữa chừng.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from src.storage.base import FileVersionMetadata, StorageAdapter


class LocalStorageAdapter(StorageAdapter):
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.versions_dir = self.root / "versions"
        self.metadata_dir = self.root / "metadata"
        self.results_dir = self.root / "results"
        for d in (self.versions_dir, self.metadata_dir, self.results_dir):
            d.mkdir(parents=True, exist_ok=True)
        self.current_pointer_path = self.root / "current.json"

    # -- file content -------------------------------------------------
    def save_version_file(self, version_id: str, file_bytes: bytes, file_name: str) -> str:
        ext = Path(file_name).suffix or ".xlsx"
        dest = self.versions_dir / f"{version_id}{ext}"
        tmp = dest.with_suffix(dest.suffix + ".tmp")
        tmp.write_bytes(file_bytes)
        os.replace(tmp, dest)  # atomic trên cùng filesystem
        return str(dest)

    def load_version_file(self, version_id: str) -> bytes:
        path = self.get_version_file_path(version_id)
        return Path(path).read_bytes()

    def get_version_file_path(self, version_id: str) -> str:
        matches = list(self.versions_dir.glob(f"{version_id}.*"))
        if not matches:
            raise FileNotFoundError(f"Không tìm thấy file cho phiên bản {version_id}")
        return str(matches[0])

    # -- metadata -------------------------------------------------------
    def save_metadata(self, metadata: FileVersionMetadata) -> None:
        path = self.metadata_dir / f"{metadata.version_id}.json"
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(metadata.__dict__, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        os.replace(tmp, path)

    def list_versions(self) -> list[FileVersionMetadata]:
        result = []
        for p in sorted(self.metadata_dir.glob("*.json")):
            data = json.loads(p.read_text(encoding="utf-8"))
            result.append(FileVersionMetadata(**data))
        result.sort(key=lambda m: m.uploaded_at, reverse=True)
        return result

    def get_current_version_id(self) -> str | None:
        if not self.current_pointer_path.exists():
            return None
        data = json.loads(self.current_pointer_path.read_text(encoding="utf-8"))
        return data.get("current_version_id")

    def set_current_version_id(self, version_id: str) -> None:
        tmp = self.current_pointer_path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps({"current_version_id": version_id}, ensure_ascii=False), encoding="utf-8"
        )
        os.replace(tmp, self.current_pointer_path)  # atomic: đổi con trỏ sau cùng

        # cập nhật is_current cho toàn bộ metadata
        for meta in self.list_versions():
            changed = meta.is_current != (meta.version_id == version_id)
            meta.is_current = meta.version_id == version_id
            if changed:
                self.save_metadata(meta)

    def delete_version(self, version_id: str) -> None:
        for p in self.versions_dir.glob(f"{version_id}.*"):
            p.unlink(missing_ok=True)
        meta_path = self.metadata_dir / f"{version_id}.json"
        meta_path.unlink(missing_ok=True)

    def enforce_retention(self, max_versions_kept: int) -> None:
        versions = self.list_versions()
        current_id = self.get_current_version_id()
        non_current = [v for v in versions if v.version_id != current_id]
        # giữ lại current + (max-1) phiên bản gần nhất khác
        to_delete = non_current[max(0, max_versions_kept - 1):]
        for v in to_delete:
            self.delete_version(v.version_id)
