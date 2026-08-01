from pathlib import Path

from src.excel_reader import read_and_validate_workbook_bytes
from src.storage.base import FileVersionMetadata
from src.storage.session_memory import SessionMemoryStorageAdapter


SAMPLE_PATH = Path(__file__).resolve().parent.parent / "data/sample/Toi_uu_nhap_VAT_mau.xlsx"


def _metadata(version_id: str, file_name: str) -> FileVersionMetadata:
    return FileVersionMetadata(
        version_id=version_id,
        original_file_name=file_name,
        uploaded_at="2026-07-31T10:00:00",
        uploaded_by=None,
        sha256="hash",
        gop_vat_row_count=1,
        khop_ma_row_count=1,
        check_status="valid",
    )


def test_two_session_stores_cannot_see_each_others_files():
    first_session = SessionMemoryStorageAdapter()
    second_session = SessionMemoryStorageAdapter()

    first_session.save_version_file("v1", b"private workbook", "private.xlsx")
    first_session.save_metadata(_metadata("v1", "private.xlsx"))
    first_session.set_current_version_id("v1")

    assert first_session.load_version_file("v1") == b"private workbook"
    assert second_session.list_versions() == []
    assert second_session.get_current_version_id() is None


def test_uploaded_workbook_is_validated_directly_from_memory():
    file_bytes = SAMPLE_PATH.read_bytes()

    result = read_and_validate_workbook_bytes(file_bytes, SAMPLE_PATH.name)

    assert result.is_valid, result.errors
    assert result.file_size_bytes == len(file_bytes)
