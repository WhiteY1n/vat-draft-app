"""Storage isolated to one Streamlit user session.

The adapter never writes uploaded workbooks or metadata to disk.  Its instance is
kept in ``st.session_state``, which Streamlit creates separately for each browser
session and discards when that session ends.
"""

from __future__ import annotations

from dataclasses import replace

from src.storage.base import FileVersionMetadata, StorageAdapter


class SessionMemoryStorageAdapter(StorageAdapter):
    def __init__(self) -> None:
        self._files: dict[str, bytes] = {}
        self._file_names: dict[str, str] = {}
        self._metadata: dict[str, FileVersionMetadata] = {}
        self._current_version_id: str | None = None

    def save_version_file(self, version_id: str, file_bytes: bytes, file_name: str) -> str:
        self._files[version_id] = bytes(file_bytes)
        self._file_names[version_id] = file_name
        return f"session://{version_id}/{file_name}"

    def load_version_file(self, version_id: str) -> bytes:
        try:
            return self._files[version_id]
        except KeyError as exc:
            raise FileNotFoundError(f"Không tìm thấy file cho phiên bản {version_id}") from exc

    def get_version_file_path(self, version_id: str) -> str:
        if version_id not in self._files:
            raise FileNotFoundError(f"Không tìm thấy file cho phiên bản {version_id}")
        return f"session://{version_id}/{self._file_names[version_id]}"

    def save_metadata(self, metadata: FileVersionMetadata) -> None:
        self._metadata[metadata.version_id] = replace(metadata)

    def list_versions(self) -> list[FileVersionMetadata]:
        result = [replace(metadata) for metadata in self._metadata.values()]
        result.sort(key=lambda metadata: metadata.uploaded_at, reverse=True)
        return result

    def get_current_version_id(self) -> str | None:
        return self._current_version_id

    def set_current_version_id(self, version_id: str) -> None:
        if version_id not in self._files or version_id not in self._metadata:
            raise FileNotFoundError(f"Không tìm thấy phiên bản {version_id}")
        self._current_version_id = version_id
        for stored_id, metadata in self._metadata.items():
            metadata.is_current = stored_id == version_id

    def delete_version(self, version_id: str) -> None:
        self._files.pop(version_id, None)
        self._file_names.pop(version_id, None)
        self._metadata.pop(version_id, None)
        if self._current_version_id == version_id:
            self._current_version_id = None

    def enforce_retention(self, max_versions_kept: int) -> None:
        versions = self.list_versions()
        non_current = [
            version for version in versions if version.version_id != self._current_version_id
        ]
        for version in non_current[max(0, max_versions_kept - 1) :]:
            self.delete_version(version.version_id)
