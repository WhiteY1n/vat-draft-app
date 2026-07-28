# Chạy web app tối ưu nháp VAT trên Windows (PowerShell).
# Cách dùng: mở PowerShell tại thư mục gốc project rồi chạy: .\scripts\run.ps1

$ErrorActionPreference = "Stop"

$venvPath = ".venv"

if (-not (Test-Path $venvPath)) {
    Write-Host "Đang tạo virtual environment..."
    python -m venv $venvPath
}

Write-Host "Kích hoạt virtual environment..."
& "$venvPath\Scripts\Activate.ps1"

Write-Host "Cài đặt dependency..."
pip install -r requirements.txt

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Đã tạo .env từ .env.example. Chỉnh sửa nếu cần trước khi chạy lại."
}

Write-Host "Khởi động Streamlit..."
streamlit run app.py
