# Chạy toàn bộ test cho web app tối ưu nháp VAT trên Windows (PowerShell).
# Cách dùng: mở PowerShell tại thư mục gốc project rồi chạy: .\scripts\test.ps1

$ErrorActionPreference = "Stop"

$venvPath = ".venv"

if (-not (Test-Path $venvPath)) {
    Write-Host "Đang tạo virtual environment..."
    python -m venv $venvPath
}

& "$venvPath\Scripts\Activate.ps1"
pip install -r requirements.txt

Write-Host "Chạy pytest..."
pytest -v
