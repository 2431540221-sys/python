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

- **Backend:** Python 3.12, Django, REST API JSON, JWT.
- **Dữ liệu:** SQLite khi chạy local; PostgreSQL trên Render.
- **Giao diện:** Django Templates, JavaScript, Plotly.
- **Bảo mật:** PBKDF2, mã hóa journal bằng Fernet.
- **Triển khai & tác vụ:** Gunicorn, WhiteNoise, APScheduler.
- **Tích hợp tùy chọn:** Gemini cho AI coach; SMTP và Web Push cho thông báo.

## Chạy project local

Yêu cầu: Python 3.12 trở lên.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Mở [http://127.0.0.1:8000/](http://127.0.0.1:8000/). Tạo tài khoản tại `/accounts/register/`; có thể tạo tài khoản quản trị bằng `python manage.py createsuperuser`.

Tùy chọn:

- Nạp dữ liệu demo: `python manage.py load_demo_data`. Tài khoản mẫu: `usera`, `userb`, `userc` / `Demo@12345`; quản trị viên: `admin` / `Admin@12345`.
- Chạy kiểm thử: `python manage.py test`.

Chỉ nạp dữ liệu demo ở môi trường thử nghiệm; không dùng các mật khẩu mẫu trên hệ thống thật.

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

## Triển khai trên Render

Project có sẵn [Blueprint cấu hình](render.yaml) và script [build.sh](build.sh). Để triển khai:

1. Đẩy mã nguồn lên GitHub.
2. Mở [Render Blueprint](https://dashboard.render.com/blueprints/new), kết nối repository và xác nhận tạo dịch vụ. Blueprint cấu hình web service `mam-wellbeing` và PostgreSQL.
3. Chờ build và migrate hoàn tất. URL dự kiến theo tên service là [https://mam-wellbeing.onrender.com](https://mam-wellbeing.onrender.com); dùng URL thực tế trong Render Dashboard nếu tên này đã được sử dụng hoặc ứng dụng chưa được deploy.
4. Trong **Environment**, bổ sung các biến tùy chọn nếu cần:
   - `GEMINI_API_KEY`: bật Gemini; nếu không cấu hình, coach dùng bộ luật dự phòng.
   - `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL`: cấu hình SMTP để gửi email.
   - `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_CLAIMS_EMAIL`: cấu hình Web Push. Có thể tạo khóa bằng `python manage.py generate_vapid_keys`.
   - `LOAD_DEMO=1`: nạp tài khoản và dữ liệu demo; tắt hoặc xóa sau khi trình diễn.

`SECRET_KEY`, `JOURNAL_ENCRYPTION_KEY`, `DATABASE_URL` và các thiết lập cơ bản đã được khai báo trong Blueprint. Kiểm tra gói dịch vụ Render hiện hành trước khi triển khai vì chính sách/gói miễn phí có thể thay đổi.

## Lưu ý

- Không đưa secret/API key vào Git. Giữ cố định `JOURNAL_ENCRYPTION_KEY`; thay khóa có thể khiến journal đã mã hóa không đọc được.
- Render gói miễn phí có thể đưa service vào trạng thái ngủ khi ít truy cập; lần mở đầu có thể chậm và scheduler chỉ chạy khi service hoạt động.
- Email và Web Push cần cấu hình riêng; Web Push yêu cầu HTTPS và người dùng cấp quyền trên trình duyệt.
- AI coach chỉ hỗ trợ tự theo dõi, không chẩn đoán hay thay thế tư vấn y tế. Tránh nhập thông tin định danh vào câu hỏi gửi cho AI.
- Đăng nhập sai nhiều lần sẽ bị giới hạn tạm thời. API chỉ trả dữ liệu thuộc tài khoản đang đăng nhập; truy cập dữ liệu người khác trả về `404`.
