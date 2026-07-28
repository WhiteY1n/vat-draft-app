"""Test runner tối giản dùng khi môi trường không cài được pytest (offline).

Chỉ dùng nội bộ để kiểm thử trong sandbox phát triển không có mạng.
Khi triển khai thật, dùng `pytest` qua scripts/test.ps1 như bình thường.
"""

from __future__ import annotations

import importlib
import inspect
import sys
import tempfile
import traceback
from pathlib import Path

TEST_MODULES = [
    "tests.test_normalization",
    "tests.test_validation",
    "tests.test_name_matching",
    "tests.test_source_ranking",
    "tests.test_allocation",
    "tests.test_excel_reader",
    "tests.test_end_to_end",
]


def run() -> int:
    total = 0
    failed = 0
    for mod_name in TEST_MODULES:
        mod = importlib.import_module(mod_name)
        test_funcs = [
            (name, obj)
            for name, obj in inspect.getmembers(mod, inspect.isfunction)
            if name.startswith("test_")
        ]
        for name, func in test_funcs:
            total += 1
            sig = inspect.signature(func)
            kwargs = {}
            tmpdir_ctx = None
            if "tmp_path" in sig.parameters:
                tmpdir_ctx = tempfile.TemporaryDirectory()
                kwargs["tmp_path"] = Path(tmpdir_ctx.name)
            try:
                func(**kwargs)
                print(f"PASS  {mod_name}.{name}")
            except Exception:  # noqa: BLE001
                failed += 1
                print(f"FAIL  {mod_name}.{name}")
                traceback.print_exc()
            finally:
                if tmpdir_ctx is not None:
                    tmpdir_ctx.cleanup()

    print(f"\n{total - failed}/{total} test PASS, {failed} FAIL")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(run())
