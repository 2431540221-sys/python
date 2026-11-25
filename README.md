# Mầm Wellbeing

Ứng dụng web theo dõi thói quen và wellbeing, tích hợp AI coach tùy chọn.

## Chức năng theo task

| Task | Chức năng |
|---|---|
| **1. Tài khoản & quyền riêng tư** | Đăng ký/đăng nhập JWT; phân quyền user/admin; mật khẩu được băm, journal được mã hóa; xuất hoặc xóa dữ liệu cá nhân. Admin chỉ xem thống kê ẩn danh. |
| **2. Theo dõi thói quen** | Tạo, sửa, xóa thói quen; đánh dấu hoàn thành theo ngày; theo dõi streak và đặt giờ nhắc. |
| **3. Check-in & journal** | Ghi nhận mood, giấc ngủ và hoạt động; xem lịch sử; viết và tìm kiếm journal riêng tư. |
| **4. Dashboard & thông báo** | Xem xu hướng mood, giấc ngủ và thói quen theo tuần/tháng; nhận cảnh báo streak, thông báo trong ứng dụng, email hoặc Web Push. |
| **5. AI coach & triển khai** | Tạo tóm tắt tuần và gợi ý mục tiêu nhỏ; có bộ lọc an toàn, yêu cầu đồng ý trước khi dùng AI và luôn kèm disclaimer. Hỗ trợ triển khai trên Render. |

## Công nghệ

- **Backend:** Python 3.12, Django 5.x cho web/auth/ORM; FastAPI tiếp nhận toàn bộ `/api/*` và service AI coach.
- **Dữ liệu:** SQLite khi chạy local; PostgreSQL trên Render.
- **Giao diện:** Django Templates, Bootstrap 5, JavaScript, Plotly.
- **Bảo mật:** PBKDF2, mã hóa journal bằng Fernet.
- **Triển khai & tác vụ:** Uvicorn/ASGI, WhiteNoise, APScheduler.
- **AI coach:** Django chỉ gửi prompt đã loại thông tin định danh và journal sang FastAPI; FastAPI gọi Cloudflare Workers AI bằng REST API. Nếu thiếu cấu hình hoặc provider lỗi, coach dùng bộ luật dự phòng.
- **Tích hợp tùy chọn:** SMTP và Web Push cho thông báo.

## Chạy local trong PyCharm và khởi tạo tài khoản

Yêu cầu: Python 3.12 trở lên. Trong PyCharm, mở thư mục project và chọn interpreter `.venv` của project.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
Copy-Item .env.example .env
```

Mở `.env` và điền `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN` có quyền gọi Workers AI, cùng một giá trị riêng tư cho `INTERNAL_SERVICE_TOKEN`. Khi chạy hai terminal, đặt `COACH_SERVICE_URL=http://127.0.0.1:8001`. Không commit `.env`.

Để bật Web Push trên máy local, chạy lệnh sau một lần:

```powershell
.\.venv\Scripts\python.exe manage.py generate_vapid_keys
```

Chép hai dòng `VAPID_PUBLIC_KEY` và `VAPID_PRIVATE_KEY` được in ra vào `.env`, đặt `VAPID_CLAIMS_EMAIL` thành địa chỉ email của bạn rồi khởi động lại ứng dụng. Giữ kín khóa private và giữ nguyên cùng một cặp khóa sau này. Đăng nhập, mở `/notifications/`, bấm **Bật thông báo trên trình duyệt** và cho phép thông báo khi trình duyệt hỏi.

Trên một website public, Web Push yêu cầu HTTPS và người dùng phải cấp quyền lại trên domain public; đăng ký trên `localhost` không dùng chung với domain đó. Cấu hình cả ba biến VAPID trong Environment của service `mam-wellbeing` trên Render trước khi bật push ở website.

Chạy AI coach và website trong hai terminal riêng của PyCharm (cả hai terminal phải ở thư mục gốc project):

Terminal 1 - service AI coach và Cloudflare:

```powershell
.\.venv\Scripts\python.exe -m uvicorn coach_service.main:app --reload --host 127.0.0.1 --port 8001
```

Terminal 2 - website Django và API FastAPI:

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe -m uvicorn config.asgi:application --reload --host 127.0.0.1 --port 8000
```

Kiểm tra AI service trong terminal thứ hai:

```powershell
$headers = @{ "X-Internal-Service-Token" = (Get-Content .env | Where-Object { $_ -match '^INTERNAL_SERVICE_TOKEN=' } | Select-Object -First 1).Split('=', 2)[1] }
$body = @{ prompt = 'Trả về JSON hợp lệ với summary là "Cloudflare đã kết nối".' } | ConvertTo-Json
Invoke-RestMethod -Uri "http://127.0.0.1:8001/generate" -Method Post -Headers $headers -ContentType "application/json" -Body $body
```

Endpoint `/health` của service AI báo `provider_configured: true` khi đã nạp được hai biến Cloudflare. Lệnh POST `/generate` phải trả object `result`; nếu lỗi, xem terminal 1 để biết lỗi Cloudflare. Terminal 2 sẽ hiển thị câu trả lời từ Cloudflare hay bộ luật dự phòng. Mở [http://127.0.0.1:8000/accounts/login/](http://127.0.0.1:8000/accounts/login/), API docs ở [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs). Sau khi đăng nhập và bật đồng ý AI trong Quyền riêng tư, trang AI coach hỗ trợ hỏi đáp nhiều lượt. Nội dung journal không được gửi cho Cloudflare.

Trên trang `/notifications/`, nhập email và bật lựa chọn nhận email để lưu tùy chọn. Muốn email được gửi thật, thêm các biến SMTP trong `.env` (Gmail cần App Password) rồi khởi động lại ứng dụng; nếu chưa cấu hình SMTP, email chỉ được ghi ra terminal theo mặc định.

Khởi tạo tài khoản nếu cần:

```powershell
$env:ACCOUNT_USER_PASSWORD = Read-Host "Nhập mật khẩu user"
$env:ACCOUNT_ADMIN_PASSWORD = Read-Host "Nhập mật khẩu admin"
python manage.py reset_accounts --confirm
```

Lệnh `reset_accounts --confirm` xóa toàn bộ tài khoản hiện có cùng dữ liệu liên quan, rồi tạo một tài khoản user và một admin. Chỉ chạy khi chủ động muốn làm sạch database. Mật khẩu nhập trong terminal, không lưu vào file hay Git. Chạy kiểm thử bằng `python manage.py test`.

## Tổng hợp API

Các API nằm dưới `/api/`. Trừ đăng ký, đăng nhập và làm mới token, yêu cầu xác thực bằng `Authorization: Bearer <access_token>`.

| Phương thức | Endpoint | Chức năng |
|---|---|---|
| `POST` | `/api/auth/register/`, `/api/auth/login/`, `/api/auth/refresh/` | Đăng ký, đăng nhập, làm mới access token |
| `GET`, `DELETE` | `/api/me/` | Xem thông tin; xóa tài khoản (cần mật khẩu) |
| `GET` | `/api/me/export/` | Xuất dữ liệu cá nhân |
| `DELETE` | `/api/me/data/` | Xóa dữ liệu nhưng giữ tài khoản |
| `GET` | `/api/admin/stats/` | Thống kê ẩn danh dành cho admin |
| `GET`, `POST` | `/api/habits/`, `/api/checkins/`, `/api/journals/` | Liệt kê hoặc tạo dữ liệu |
| `GET`, `PUT`, `DELETE` | `/api/habits/<id>/`, `/api/journals/<id>/` | Xem, sửa, xóa thói quen hoặc journal |
| `POST` | `/api/habits/<id>/check/` | Đánh dấu hoặc bỏ đánh dấu hoàn thành |
| `GET` | `/api/stats/?period=week` hoặc `month` | Thống kê theo tuần hoặc tháng |
| `GET` | `/api/notifications/` | Danh sách thông báo |
| `GET`, `POST` | `/api/coach/weekly/` | Xem hoặc tạo tóm tắt tuần |

Các endpoint `/api/*` được khai báo và xử lý trong `coach_service/api.py` bằng FastAPI. Chúng dùng lại Django forms, service và ORM cho xác thực/dữ liệu, nên giao diện và API cùng truy cập một database; SQLite không bị sao chép sang FastAPI. Trong ASGI app, FastAPI nhận API trước rồi Django phục vụ các trang templates. Tài liệu OpenAPI có tại `/docs`.

## Triển khai trên Render

Project có sẵn [Blueprint cấu hình](render.yaml) và script [build.sh](build.sh). Service Django + FastAPI (`mam-wellbeing`) dùng chung một tiến trình ASGI và cùng Django ORM/database; service FastAPI riêng (`mam-coach`) cung cấp AI coach. Để triển khai:

1. Đẩy mã nguồn lên GitHub.
2. Mở [Render Blueprint](https://dashboard.render.com/blueprints/new), kết nối repository và xác nhận tạo dịch vụ. Blueprint cấu hình web service ứng dụng, service AI coach, một nhóm biến môi trường có token dùng chung, PostgreSQL và tự deploy mỗi khi có commit mới trên nhánh được liên kết.
3. Chờ build và migrate hoàn tất. URL dự kiến theo tên service là [https://mam-wellbeing.onrender.com](https://mam-wellbeing.onrender.com); dùng URL thực tế trong Render Dashboard nếu tên này đã được sử dụng hoặc ứng dụng chưa được deploy.
4. Build chỉ cài dependencies và migrate database; không tự tạo hay xóa tài khoản. Để khởi tạo lại tài khoản trên Render:
   - Trong **Environment**, đặt `ACCOUNT_USER_PASSWORD` và `ACCOUNT_ADMIN_PASSWORD` với các mật khẩu riêng tư.
   - Mở **Shell** của service và chạy `python manage.py reset_accounts --confirm`. Lệnh này xóa toàn bộ tài khoản hiện có cùng dữ liệu liên quan trên database Render, rồi tạo user và admin.
   - Sau khi chạy thành công, xóa hai biến mật khẩu khỏi **Environment**.
5. Các tích hợp tùy chọn:
   - Đặt `CLOUDFLARE_ACCOUNT_ID` và `CLOUDFLARE_API_TOKEN` trong service `mam-coach`; model mặc định là `@cf/meta/llama-3.1-8b-instruct`. Nếu thiếu credentials hoặc provider lỗi, coach dùng bộ luật dự phòng.
   - `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL`: cấu hình SMTP để gửi email.
   - `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_CLAIMS_EMAIL`: cấu hình Web Push. Có thể tạo khóa bằng `python manage.py generate_vapid_keys`.

Nếu Render không tự deploy sau khi push/merge, mở **Settings** của từng service và kiểm tra **Auto-Deploy = On Commit**. Chọn **Manual Deploy → Deploy a specific commit** có thể tắt auto-deploy; bật lại trong Settings hoặc đồng bộ Blueprint có `autoDeployTrigger: commit`.

`SECRET_KEY`, `JOURNAL_ENCRYPTION_KEY`, `DATABASE_URL` và các thiết lập cơ bản đã được khai báo trong Blueprint. Kiểm tra gói dịch vụ Render hiện hành trước khi triển khai vì chính sách/gói miễn phí có thể thay đổi.

## Đồng bộ dữ liệu SQLite local với Render

Đây là đồng bộ hai chiều theo kiểu bản cập nhật mới nhất thắng; worker chỉ chạy khi ứng dụng local được mở. Render lưu các thay đổi cho đến lần local kết nối tiếp theo. Tài khoản và password hash được đồng bộ; journal được mã hóa khi truyền và cần dùng cùng một `JOURNAL_ENCRYPTION_KEY` ở cả hai nơi.

1. Tạo backup database Render trước khi bắt đầu. Trong **Environment** của `mam-wellbeing`, đặt `DATABASE_SYNC_SHARED_SECRET` thành một chuỗi ngẫu nhiên dài và giữ `DATABASE_SYNC_ENABLED=0`.
2. Trong `.env` local, bật `DATABASE_SYNC_ENABLED=1`, đặt `DATABASE_SYNC_REMOTE_URL` thành URL HTTPS của `mam-wellbeing` (không thêm `/` cuối), và đặt `DATABASE_SYNC_SHARED_SECRET` giống hệt Render.
3. Đặt `JOURNAL_ENCRYPTION_KEY` local giống hệt giá trị của Render. Không thay khóa hiện tại, không gửi khóa vào Git/chat và không dùng `.env.example` như khóa thật.
4. Chạy bootstrap **một lần** để dữ liệu local thay thế dữ liệu ứng dụng hiện tại trên Render. Xác nhận rõ trước khi chạy:

   ```powershell
   .\.venv\Scripts\python.exe manage.py sync_bootstrap_render --confirm-render-replacement
   ```

   Lệnh từ chối database local rỗng; dữ liệu Render chỉ bị thay thế khi bước commit cuối thành công. Nếu lệnh dừng giữa lúc tải, dữ liệu Render chưa bị thay thế.
5. Khởi động ứng dụng local bằng Uvicorn như thường lệ. Worker sẽ đồng bộ định kỳ; dừng ứng dụng local thì việc đồng bộ tạm dừng. Không bật `DATABASE_SYNC_ENABLED` trên Render.

Không chạy bootstrap lần nữa nếu không chủ động muốn thay toàn bộ dữ liệu Render bằng bản local. Việc đồng bộ không thể gộp hai tài khoản riêng có cùng tên đăng nhập; sau bootstrap, mỗi tài khoản dùng chung password hash giữa hai môi trường.

### Đổi khóa mã hóa journal an toàn

Không đổi `JOURNAL_ENCRYPTION_KEY` trực tiếp khi database đã có journal: nội dung hiện có sẽ không giải mã được. Để đổi khóa, cần chạy lệnh xoay khóa trên từng database, dùng khóa hiện tại làm khóa cũ và cùng một khóa mới cho cả local lẫn Render.

1. Sao lưu cả hai database, dừng ứng dụng local và tạm ngưng thao tác ghi journal trên Render. Giữ `DATABASE_SYNC_ENABLED=0` trên Render.
2. Tạo khóa mới riêng tư bằng `.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(32))"`. Thêm cùng giá trị đó vào `JOURNAL_ENCRYPTION_KEY_NEXT` trong `.env` và Environment của Render; trong khi xoay, để `JOURNAL_ENCRYPTION_KEY` hiện tại chưa đổi.
3. Trên cả local và Render, chạy `python manage.py rotate_journal_encryption_key --check-only`. Chỉ tiếp tục nếu cả hai lệnh báo kiểm tra thành công.
4. Chạy `python manage.py rotate_journal_encryption_key --confirm` trên local và Render. Lệnh dùng transaction riêng cho từng database; không bật ứng dụng hoặc đồng bộ giữa hai lần chạy.
5. Sau khi cả hai chạy thành công, đặt `JOURNAL_ENCRYPTION_KEY` bằng khóa mới trên cả hai nơi, xóa `JOURNAL_ENCRYPTION_KEY_NEXT`, khởi động lại ứng dụng, rồi chạy `--check-only` trên cả hai database lần nữa.

Nếu một bước lỗi, không khởi động worker hay chạy bootstrap; giữ bản sao lưu và các khóa hiện có, rồi xử lý trạng thái trước khi tiếp tục. Không gửi khóa vào Git/chat.

## Lưu ý

- Không đưa secret/API key vào Git. Không dùng `SECRET_KEY` mẫu từ môi trường phát triển làm khóa production; việc đổi `SECRET_KEY` và `JOURNAL_ENCRYPTION_KEY` là hai thao tác riêng.
- Render gói miễn phí có thể đưa service vào trạng thái ngủ khi ít truy cập; lần mở đầu có thể chậm và scheduler chỉ chạy khi service hoạt động.
- Email và Web Push cần cấu hình riêng; Web Push yêu cầu HTTPS và người dùng cấp quyền trên trình duyệt.
- AI coach chỉ hỗ trợ tự theo dõi, không chẩn đoán hay thay thế tư vấn y tế. Tránh nhập thông tin định danh vào câu hỏi gửi cho AI.
- Đăng nhập sai nhiều lần sẽ bị giới hạn tạm thời. API chỉ trả dữ liệu thuộc tài khoản đang đăng nhập; truy cập dữ liệu người khác trả về `404`.
