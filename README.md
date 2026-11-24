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

## Chạy local và khởi tạo tài khoản

Yêu cầu: Python 3.12 trở lên.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate

$env:ACCOUNT_USER_PASSWORD = Read-Host "Nhập mật khẩu user"
$env:ACCOUNT_ADMIN_PASSWORD = Read-Host "Nhập mật khẩu admin"
python manage.py reset_accounts --confirm
```

Để chạy giao diện và các API qua FastAPI + Django ASGI khi không bật AI:

```powershell
uvicorn config.asgi:application --reload --host 127.0.0.1 --port 8000
```

Để bật AI coach, chạy service FastAPI riêng ở terminal thứ nhất:

```powershell
$env:INTERNAL_SERVICE_TOKEN = "chuoi-bi-mat-dung-chung"
$env:CLOUDFLARE_ACCOUNT_ID = "Cloudflare-Account-ID"
$env:CLOUDFLARE_API_TOKEN = "Cloudflare-Workers-AI-API-token"
$env:CLOUDFLARE_AI_MODEL = "@cf/meta/llama-3.1-8b-instruct"
uvicorn coach_service.main:app --host 127.0.0.1 --port 8001
```

Trong terminal thứ hai, cấu hình cùng token và URL AI service rồi chạy ứng dụng web/API ASGI:

```powershell
$env:INTERNAL_SERVICE_TOKEN = "chuoi-bi-mat-dung-chung"
$env:COACH_SERVICE_URL = "http://127.0.0.1:8001"
uvicorn config.asgi:application --reload --host 127.0.0.1 --port 8000
```

Lệnh `reset_accounts --confirm` xóa toàn bộ tài khoản hiện có cùng dữ liệu liên quan, rồi tạo một tài khoản user và một admin. Chỉ chạy khi chủ động muốn làm sạch database. Mật khẩu nhập trong terminal, không lưu vào file hay Git.

Mở [http://127.0.0.1:8000/accounts/login/](http://127.0.0.1:8000/accounts/login/) để đăng nhập. Chạy kiểm thử bằng `python manage.py test`.

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
2. Mở [Render Blueprint](https://dashboard.render.com/blueprints/new), kết nối repository và xác nhận tạo dịch vụ. Blueprint cấu hình web service ứng dụng, service AI coach, một nhóm biến môi trường có token dùng chung và PostgreSQL.
3. Chờ build và migrate hoàn tất. URL dự kiến theo tên service là [https://mam-wellbeing.onrender.com](https://mam-wellbeing.onrender.com); dùng URL thực tế trong Render Dashboard nếu tên này đã được sử dụng hoặc ứng dụng chưa được deploy.
4. Build chỉ cài dependencies và migrate database; không tự tạo hay xóa tài khoản. Để khởi tạo lại tài khoản trên Render:
   - Trong **Environment**, đặt `ACCOUNT_USER_PASSWORD` và `ACCOUNT_ADMIN_PASSWORD` với các mật khẩu riêng tư.
   - Mở **Shell** của service và chạy `python manage.py reset_accounts --confirm`. Lệnh này xóa toàn bộ tài khoản hiện có cùng dữ liệu liên quan trên database Render, rồi tạo user và admin.
   - Sau khi chạy thành công, xóa hai biến mật khẩu khỏi **Environment**.
5. Các tích hợp tùy chọn:
   - Đặt `CLOUDFLARE_ACCOUNT_ID` và `CLOUDFLARE_API_TOKEN` trong service `mam-coach`; model mặc định là `@cf/meta/llama-3.1-8b-instruct`. Nếu thiếu credentials hoặc provider lỗi, coach dùng bộ luật dự phòng.
   - `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL`: cấu hình SMTP để gửi email.
   - `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_CLAIMS_EMAIL`: cấu hình Web Push. Có thể tạo khóa bằng `python manage.py generate_vapid_keys`.

`SECRET_KEY`, `JOURNAL_ENCRYPTION_KEY`, `DATABASE_URL` và các thiết lập cơ bản đã được khai báo trong Blueprint. Kiểm tra gói dịch vụ Render hiện hành trước khi triển khai vì chính sách/gói miễn phí có thể thay đổi.

## Lưu ý

- Không đưa secret/API key vào Git. Giữ cố định `JOURNAL_ENCRYPTION_KEY`; thay khóa có thể khiến journal đã mã hóa không đọc được.
- Render gói miễn phí có thể đưa service vào trạng thái ngủ khi ít truy cập; lần mở đầu có thể chậm và scheduler chỉ chạy khi service hoạt động.
- Email và Web Push cần cấu hình riêng; Web Push yêu cầu HTTPS và người dùng cấp quyền trên trình duyệt.
- AI coach chỉ hỗ trợ tự theo dõi, không chẩn đoán hay thay thế tư vấn y tế. Tránh nhập thông tin định danh vào câu hỏi gửi cho AI.
- Đăng nhập sai nhiều lần sẽ bị giới hạn tạm thời. API chỉ trả dữ liệu thuộc tài khoản đang đăng nhập; truy cập dữ liệu người khác trả về `404`.
