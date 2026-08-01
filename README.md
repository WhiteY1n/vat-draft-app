# Web app tối ưu nháp VAT

App nội bộ để tra cứu Mã SP → Mã VAT → Tên kế toán → Nguồn, phân bổ số lượng
qua nhiều nguồn theo quy tắc cố định (không dùng AI), và xuất kết quả ra
Excel/TSV/in. App **không** trừ tồn thật, **không** ghi vào file nguồn.

Tài liệu đặc tả đầy đủ: xem `CLAUDE.md` (được cấp kèm yêu cầu ban đầu, không
copy lại trong README này).

## 1. Trạng thái hiện tại

Đã hoàn thành **Milestone 1–4** ở mức chạy được từ đầu đến cuối tại local:

- Đọc & kiểm tra cấu trúc file Excel (`Gộp VAT`, `Khớp mã`).
- Upload, xác nhận và xử lý trong bộ nhớ riêng của từng phiên người dùng
  (`SessionMemoryStorageAdapter`); không ghi file upload lên ổ đĩa server.
- Dán hóa đơn nhiều dòng, sửa trực tiếp trên bảng, kiểm tra lỗi chặn.
- Mapping Mã SP → Mã VAT → Tên kế toán (chọn 1 nhóm Tên kế toán + ĐVT cho mỗi dòng).
- Xếp hạng nguồn trong phạm vi hóa đơn, phân bổ số lượng (ưu tiên 1 nguồn nếu đủ, chia gần đều nếu phải dùng nhiều nguồn, không vượt tồn trong 1 lần chạy).
- Bảng kết quả, xuất Excel (3+ sheet), sao chép TSV, chế độ xem in.
- Trang Kiểm tra dữ liệu (thống kê lỗi nguồn + bảng kiểm tra tên thủ công để tải và đưa AI **bên ngoài** app).
- Trang Cấu hình (đọc từ YAML).

**Chưa làm (Milestone 5, chủ động chưa bắt đầu theo đúng CLAUDE.md):**
Supabase Storage, Google OAuth thật, sửa cấu hình trực tiếp trên UI.

## 2. File đầu vào đã nhận được trong phiên làm việc này

- ✅ `Tối ưu nháp VAT.xlsx` — đã đọc và dùng làm dữ liệu mẫu (`data/sample/Toi_uu_nhap_VAT_mau.xlsx`).
- ❌ `app cho a hưng.txt` — **không tìm thấy** trong file đính kèm của phiên làm việc
  (chỉ có file Excel). Nếu file này có thông tin nghiệp vụ bổ sung, vui lòng cung cấp lại
  để rà soát và cập nhật code/README cho phù hợp.

## 3. Khác biệt giữa dữ liệu thật và CLAUDE.md (đã ưu tiên dữ liệu thật, không tự đổi quy tắc)

- **Tên cột khớp hoàn toàn** với đặc tả ở cả hai sheet `Gộp VAT` và `Khớp mã` — không cần
  alias đặc biệt ngoài bảng alias đã có sẵn (hoa/thường/khoảng trắng).
- **Dữ liệu thật trong file mẫu rất ít**: sheet `Gộp VAT` chỉ có 49 dòng dữ liệu thật (dòng
  2–50); phần còn lại tới dòng 6227 là các dòng trống đã định dạng sẵn (app đã tự động bỏ
  qua các dòng trống này khi đọc). Sheet `Khớp mã` có 48 dòng dữ liệu thật.
- **Mã VAT giữa hai sheet trong file mẫu không khớp nhau**: toàn bộ 49 dòng `Gộp VAT` có
  `MÃ VAT KIOT` = chuỗi cố định `"XUẤT THẤP"`, trong khi 48 mã VAT trong `Khớp mã` đều có
  dạng `VAT100xx`. Nghĩa là **không có Mã SP nào trong file mẫu ánh xạ được sang một dòng
  tồn thực tế** — đây là hạn chế của bộ dữ liệu mẫu, không phải lỗi của app. Vì vậy:
  - Test đọc file mẫu thật (`tests/test_excel_reader.py`) chỉ kiểm tra việc đọc & kiểm tra
    cấu trúc thành công, không kiểm tra mapping/allocation trên dữ liệu mẫu này.
  - Test end-to-end đầy đủ (`tests/test_end_to_end.py`) dùng một workbook giả lập nhỏ, xây
    dựng đúng theo cấu trúc cột thật, để có thể kiểm chứng toàn bộ luồng mapping → phân bổ
    → xuất Excel.
  - Khi có file dữ liệu thật đầy đủ hơn (nhiều nguồn, mã VAT khớp giữa 2 sheet), nên chạy
    lại `tests/test_end_to_end.py` với file đó để xác nhận thêm.

## 4. Giả định an toàn đã áp dụng (do CLAUDE.md không nêu chi tiết)

Tất cả đặt trong `config/settings.yaml`, có thể sửa mà không cần sửa code:

- `allow_fractional_sl: false` — SL phải là số nguyên dương (có thể bật lại nếu nghiệp vụ
  cho phép số lẻ).
- `source_tiebreak_priority` — thứ tự mẫu ban đầu theo đúng ví dụ trong CLAUDE.md
  (`Vận chuyển, MAY, SAIGONHANOI, CAO, Thấp`); chỉnh sửa tùy nghiệp vụ thật.
- `name_match_weights.review_threshold: 55.0` — ngưỡng để đánh dấu "cần kiểm tra tên thủ
  công" ở trang Kiểm tra dữ liệu (CLAUDE.md không nêu con số cụ thể).
- **RapidFuzz**: môi trường phát triển dùng để tạo phiên bản này không có kết nối mạng nên
  không `pip install` được `rapidfuzz`. Code (`src/name_matching.py`) tự động dùng
  `rapidfuzz.fuzz.token_sort_ratio` khi thư viện có sẵn (đúng như CLAUDE.md yêu cầu — đã
  khai báo trong `requirements.txt`), và **chỉ fallback** sang một hàm xấp xỉ thuần Python
  dựa trên `difflib` (cùng thang điểm 0–100, vẫn deterministic, không dùng AI) khi
  `rapidfuzz` không cài được. Khi chạy `pip install -r requirements.txt` bình thường (có
  mạng), app sẽ dùng RapidFuzz thật. Nên chạy lại `pytest tests/test_name_matching.py` sau
  khi cài rapidfuzz thật để xác nhận điểm số không đổi đáng kể.
- Trang Cấu hình (mục 15.4) hiện chỉ **đọc** cấu hình, chưa hỗ trợ sửa trực tiếp trên UI —
  đúng như CLAUDE.md cho phép ("Trong MVP có thể đọc cấu hình từ YAML thay vì cho phép sửa
  trực tiếp trên UI").
- `AUTH_MODE=none` mặc định coi người dùng là Admin để thuận tiện phát triển/kiểm thử local;
  khi triển khai thật, đặt `AUTH_MODE=google` (phần xác thực Google OIDC thật cần triển khai
  thêm ở Milestone 5 — hiện tại `src/auth.py` đã có khung nhưng sẽ hiện cảnh báo và không cho
  vào app nếu bật `google` mà chưa có tích hợp OIDC thật).

## 5. Cấu trúc project

Xem `CLAUDE.md` mục 17 — cấu trúc thực tế bám sát đề xuất đó, bổ sung thêm:

- `src/pipeline.py` — hàm điều phối `process_invoice()` duy nhất, dùng chung bởi UI và test
  end-to-end, để tránh lặp logic nghiệp vụ trong callback UI.
- `src/accounting_group.py` — tách riêng logic chọn nhóm (Tên kế toán, ĐVT) khỏi mapping.
- `src/session.py` — tiện ích Streamlit (nạp storage/config/dữ liệu hiện tại vào
  `st.session_state`), không chứa business logic.
- `src/review.py` — xây bảng kiểm tra tên thủ công (mục 16).
- `scripts/dev_run_tests_manual.py` — test runner thủ công **chỉ dùng nội bộ** cho sandbox
  không có mạng (không cài được `pytest`). Khi có mạng, luôn dùng `pytest` qua
  `scripts/test.ps1` như bình thường.

## 6. Chạy trên Windows (PowerShell)

Yêu cầu: Python 3.12+ đã cài và có trong PATH.

```powershell
# Lần đầu (hoặc mỗi khi muốn cài lại dependency)
.\scripts\run.ps1
```

Script sẽ tự tạo virtual environment `.venv`, cài `requirements.txt`, tạo `.env` từ
`.env.example` nếu chưa có, rồi khởi động Streamlit tại `http://localhost:8501`.

Chạy test:

```powershell
.\scripts\test.ps1
```

Chạy thủ công (không qua script):

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

## 7. Hướng dẫn triển khai web (tóm tắt)

App hiện dùng `SessionMemoryStorageAdapter`: mỗi kết nối trình duyệt có kho dữ liệu riêng
trong `st.session_state`. File upload, metadata và lịch sử phiên bản không được ghi lên ổ
đĩa server, không được chia sẻ với người truy cập khác và sẽ bị giải phóng khi Streamlit kết
thúc phiên. Vì vậy lịch sử cũng không còn sau khi đóng phiên hoặc app khởi động lại.

Để triển khai:

1. **Container hóa**: dùng `Dockerfile` có sẵn.
   ```bash
   docker build -t vat-draft-app .
   docker run -p 8501:8501 -e AUTH_MODE=none vat-draft-app
   ```
2. **Supabase Storage** chỉ nên dùng nếu sau này thực sự cần lưu dữ liệu lâu dài và đã có
   phân quyền theo từng người dùng. Khi đó cài đặt các phương thức còn để trống trong
   `src/storage/supabase.py`, dùng Supabase Storage bucket cho file Excel và một bảng nhỏ
   (hoặc JSON trong bucket) cho metadata phiên bản — interface `StorageAdapter` đã được thiết
   kế để không phải sửa lại `src/session.py` hay logic nghiệp vụ.
3. **Google OpenID Connect**: cắm một thư viện OIDC (ví dụ `streamlit-oauth` hoặc middleware
   phía trước Streamlit) để lấy `session_email` đã xác thực, gán vào
   `st.session_state["user_email"]` trước khi gọi `get_current_user()`. Danh sách
   `ALLOWED_EMAILS`/`ADMIN_EMAILS` đọc từ biến môi trường/secret, không hard-code.
4. Đặt `AUTH_MODE=google`, `ALLOWED_EMAILS`, `ADMIN_EMAILS` qua biến môi trường hoặc secrets
   của nền tảng triển khai (không commit `.env` thật).

## 8. Kiểm thử

- 35 test (unit + end-to-end) bao phủ: đọc/kiểm tra Excel, mapping, validation, so khớp tên,
  xếp hạng nguồn, thuật toán phân bổ (đủ các tình huống bắt buộc trong CLAUDE.md mục 19), và
  một luồng end-to-end đầy đủ dùng workbook giả lập theo đúng cấu trúc cột thật.
- Chạy bằng `pytest` (khi có mạng để cài dependency) hoặc
  `python scripts/dev_run_tests_manual.py` (không cần pytest, dùng trong sandbox phát triển
  không có mạng — đã chạy và **PASS 35/35** trong phiên làm việc này).

## 9. Hạn chế còn lại / việc cho milestone tiếp theo

- Trang Cấu hình chưa cho sửa trực tiếp trên UI (chỉ đọc YAML).
- Chưa có Supabase Storage / Google OAuth thật (Milestone 5, chủ động chưa làm).
- Chưa nhận được nội dung file `app cho a hưng.txt` — cần bổ sung nếu có yêu cầu nghiệp vụ
  khác biệt.
- Nên chạy lại toàn bộ test với `rapidfuzz` thật (có mạng) để xác nhận điểm số so khớp tên
  không đổi đáng kể so với bản fallback `difflib` dùng trong phiên phát triển này.
- Nên thử với một file dữ liệu thật có nhiều nguồn và Mã VAT khớp giữa hai sheet để kiểm
  chứng thêm luồng phân bổ nhiều nguồn trên dữ liệu thật (file mẫu hiện tại chỉ có 1 nguồn
  "Thấp" và không khớp mã VAT với sheet Khớp mã, như đã nêu ở mục 3).
