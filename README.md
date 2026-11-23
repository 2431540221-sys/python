# Mầm Wellbeing — Nhóm 1, Đề tài WEB 10

Ứng dụng theo dõi thói quen và wellbeing có AI coach nhẹ. Đây là **một web Django duy nhất** gộp công việc của cả 5 thành viên, dùng chung một giao diện (màu xanh thông, chữ Be Vietnam Pro, cây "Mầm" lớn dần theo chuỗi thói quen).

## Chức năng theo từng task (đối chiếu với yêu cầu của thầy)

| Task | Yêu cầu của thầy | Có trong web | Nằm ở đâu |
|---|---|---|---|
| **1** Auth, phân quyền, bảo vệ dữ liệu | Đăng ký/đăng nhập **JWT** | `/accounts/register/`, `/accounts/login/` (JWT trong cookie HttpOnly) và `POST /api/auth/register`, `login`, `refresh` (Bearer token) | `accounts/tokens.py`, `middleware.py`, `views.py`, `api.py` |
| | Băm mật khẩu | PBKDF2-SHA256 của Django; đổi mật khẩu thì token cũ vô hiệu | `config/settings.py`, `accounts/tokens.py` |
| | Role user/admin | Trường `role`; admin có trang `/admin-stats/` | `accounts/models.py` |
| | Mã hóa nội dung journal | Fernet (AES) trong `EncryptedTextField`; trong database chỉ là chuỗi mã hóa | `accounts/crypto.py` |
| | API xóa/xuất dữ liệu cá nhân | `GET /api/me/export/`, `DELETE /api/me/data/`, `DELETE /api/me/`; có cả trang `/privacy/` | `accounts/api.py`, `services.py` |
| | Demo: A không đọc được dữ liệu B; admin chỉ xem thống kê ẩn danh | Dữ liệu của người khác trả **404**; `/api/admin/stats/` chỉ có số tổng hợp (không tên, email, journal) | mọi view lọc theo `request.user` |
| **2** Habit tracker | Bảng habit/log, CRUD | `/habits/` (thêm, sửa, xóa, chi tiết, lịch 5 tuần bấm để tick bù) | `habits/` |
| | Hàm streak hiện tại và dài nhất | `calculate_streaks()` | `habits/services.py` |
| | Job nhắc nhở theo giờ | APScheduler chạy mỗi phút + lệnh `send_reminders` | `habits/scheduler.py`, `services.py` |
| | Demo: tick 7 ngày liên tiếp, bỏ 1 ngày thì streak về 0 | Xem "Kịch bản demo" bên dưới | `habits/tests.py` |
| **3** Mood check-in, journal riêng tư | Form check-in (mood 1–5, giờ ngủ, hoạt động), lưu log theo ngày | `/checkin/` (mỗi ngày một bản ghi, check-in lại thì cập nhật), lịch sử `/history/` | `tracking/` |
| | Journal chỉ chủ sở hữu xem | `/journal/` (CRUD + tìm kiếm) | `tracking/views.py` |
| | Demo: 14 ngày dữ liệu mẫu và xem lại lịch sử | Nút "Nạp dữ liệu mẫu" ở `/privacy/` hoặc lệnh `load_demo_data` | `accounts/demo.py` |
| **4** Dashboard xu hướng, notification | API tổng hợp theo tuần/tháng | `GET /api/stats/?period=week` hoặc `month` | `insights/services.py`, `api.py` |
| | Biểu đồ đường/cột mood–giấc ngủ–habit (Plotly) | Dashboard `/dashboard/`, chuyển 7/30 ngày và theo ngày/theo tuần | `static/js/dashboard.js` |
| | Thông báo khi sắp mất streak | Từ 18h, thói quen có chuỗi mà chưa làm sẽ có thông báo (1 lần/ngày) + chuông trên menu | `insights/services.py` |
| | Gửi thông báo qua email và push | Nhắc nhở, cảnh báo và báo cáo được lưu trong app, gửi email nếu có SMTP, và gửi Web Push tới trình duyệt đã đăng ký | `habits/services.py`, `insights/views.py`, `static/js/service-worker.js` |
| | Chỉ số wellbeing tham khảo | Dashboard lưu index 0-100 theo ngày; đây là xu hướng tự theo dõi, chưa được kiểm chứng y tế. Giảm ít nhất 15 điểm so với 7 ngày trước, với tối thiểu 3 check-in mỗi giai đoạn, có thể kích hoạt lời nhắc hỗ trợ hàng tuần | `insights/models.py`, `insights/services.py` |
| | Demo: dashboard cá nhân với dữ liệu 30 ngày | Nạp dữ liệu mẫu 30 ngày rồi mở `/dashboard/` | |
| **5** AI coach nhẹ, deploy | Prompt tóm tắt tuần từ log, gợi ý mục tiêu nhỏ | `/coach/` và `POST /api/coach/weekly/` | `coach/prompts.py`, `service.py` |
| | Bộ lọc từ khóa nhạy cảm kèm câu từ chối chẩn đoán y tế | Chặn **trước** khi gửi cho AI và lọc **đầu ra** của AI | `coach/safety.py` |
| | Deploy Render/Railway | `render.yaml`, `build.sh`, gunicorn, whitenoise | mục Deploy |
| | Demo: link online, AI trả bản tóm tắt có disclaimer | Disclaimer luôn kèm trong trang và trong JSON | |

## Chạy trên máy (PyCharm / Windows)

1. Mở thư mục `mam_wellbeing` bằng PyCharm, tạo môi trường ảo (Virtualenv).
2. Mở Terminal của PyCharm và gõ lần lượt:
   ```
   pip install -r requirements.txt
   python manage.py migrate
   python manage.py runserver
   ```
3. Mở http://127.0.0.1:8000/

Nếu chỉ muốn dữ liệu minh họa, chạy riêng `python manage.py load_demo_data` trên môi trường demo. Không nạp dữ liệu giả vào tài khoản người dùng thật.

Tài khoản demo (do `load_demo_data` tạo):

| Tài khoản | Mật khẩu | Vai trò |
|---|---|---|
| `usera`, `userb`, `userc` | `Demo@12345` | người dùng (đều có sẵn 30 ngày dữ liệu) |
| `admin` | `Admin@12345` | quản trị viên |

Chạy bộ kiểm thử: `python manage.py test`. Dữ liệu mô phỏng được tạo trong test database tạm và không ghi vào database người dùng.

## Kịch bản demo cho thầy

**Task 1, phân quyền:** đăng nhập `usera`, vào `/journal/` thấy bài của A. Mở thẳng link bài của B (ví dụ `/journal/<id của B>/`) sẽ ra "Không tìm thấy". Đăng nhập `admin`, mở "Thống kê ẩn danh": chỉ có con số.
Bằng API:
```
curl -X POST http://127.0.0.1:8000/api/auth/login/ -H "Content-Type: application/json" -d "{\"username\":\"userb\",\"password\":\"Demo@12345\"}"
curl http://127.0.0.1:8000/api/journals/<id_của_A>/ -H "Authorization: Bearer <access_của_B>"     # -> 404
```
Mã hóa: mở `db.sqlite3`, bảng `tracking_journalentry`, cột `content` là chuỗi dạng `gAAAA...`.

**Task 2, streak:** tạo thói quen mới, vào trang chi tiết. Bấm **hôm nay**, rồi bấm lùi dần các ngày trước trên lịch: chuỗi tăng 1, 2, … 7. Bỏ cả hôm qua lẫn hôm nay thì chuỗi hiện tại về 0 (chuỗi dài nhất vẫn được giữ). Dữ liệu mẫu có sẵn ba tình huống: "Đi bộ 20 phút" (chuỗi 10), "Uống đủ 2 lít nước" (sắp mất chuỗi), "Đọc sách 15 phút" (đã mất chuỗi, hiện 0). Nhắc nhở theo giờ: đặt giờ nhắc sau hiện tại 1–2 phút rồi chờ, scheduler sẽ tạo thông báo (chuông trên menu).

**Task 3, check-in:** `/checkin/` rồi `/history/`. Thử nhập mood 6, giờ ngủ 25 hoặc ngày tương lai: form báo lỗi.

**Task 4, dashboard:** `/dashboard/` với 30 ngày dữ liệu. Thông báo sắp mất chuỗi xuất hiện từ 18h; muốn thử ngay thì đặt biến môi trường `STREAK_RISK_FROM_HOUR=0`.

**Task 5, AI coach:** `/coach/` rồi "Tạo tóm tắt tuần này". Hỏi thử "Mình có bị trầm cảm không?" sẽ nhận câu từ chối chẩn đoán, câu hỏi này không được gửi cho AI. Đầu ra nào chứa chẩn đoán/thuốc cũng bị loại.

## API (JSON, xác thực `Authorization: Bearer <access_token>`)

| Phương thức | Đường dẫn | Mô tả |
|---|---|---|
| POST | `/api/auth/register/`, `/api/auth/login/`, `/api/auth/refresh/` | đăng ký, đăng nhập, làm mới token |
| GET, DELETE | `/api/me/` | thông tin của tôi / xóa tài khoản (gửi `{"password": "..."}`) |
| GET | `/api/me/export/` | xuất toàn bộ dữ liệu của tôi |
| DELETE | `/api/me/data/` | xóa dữ liệu, giữ tài khoản |
| GET | `/api/admin/stats/` | thống kê ẩn danh (chỉ role admin) |
| GET, POST | `/api/habits/` | danh sách / tạo thói quen |
| GET, PUT, DELETE | `/api/habits/<id>/` | chi tiết, sửa, xóa |
| POST | `/api/habits/<id>/check/` | tick / bỏ tick một ngày |
| GET, POST | `/api/checkins/` | check-in theo ngày |
| GET, POST | `/api/journals/` | danh sách / tạo journal |
| GET, PUT, DELETE | `/api/journals/<id>/` | chi tiết, sửa, xóa journal |
| GET | `/api/stats/?period=week` hoặc `month` | tổng hợp xu hướng |
| GET | `/api/notifications/` | thông báo |
| GET, POST | `/api/coach/weekly/` | xem / tạo tóm tắt tuần của AI coach |

## Deploy lên Render

1. Đẩy project lên GitHub (`.gitignore` đã loại `db.sqlite3`).
2. Render → **New → Blueprint** → chọn repo. Render đọc `render.yaml`, tạo web service và database Postgres.
3. Biến môi trường (đã khai báo trong `render.yaml`): `SECRET_KEY` và `JOURNAL_ENCRYPTION_KEY` tự sinh; `DEBUG=0`; `DATABASE_URL` tự nối với database. Trong Render → service → **Environment**, điền các biến `sync: false`:
   - `LOAD_DEMO=1` nếu muốn có sẵn tài khoản demo. **Nhớ tắt hoặc xóa các tài khoản này sau khi demo**, vì mật khẩu được ghi công khai ở trên.
   - Email SMTP (ví dụ Gmail): `EMAIL_HOST=smtp.gmail.com`, `EMAIL_PORT=587`, `EMAIL_USE_TLS=1`, `EMAIL_USE_SSL=0`, `EMAIL_HOST_USER` là địa chỉ Gmail, `EMAIL_HOST_PASSWORD` là **Google App Password** (không phải mật khẩu đăng nhập), và `DEFAULT_FROM_EMAIL` là địa chỉ gửi. Bật xác minh 2 bước rồi tạo App Password trong tài khoản Google. Nhà cung cấp khác cần dùng host/port/TLS tương ứng.
   - AI coach: đặt `GEMINI_API_KEY` bằng API key từ Google AI Studio; `GEMINI_MODEL` mặc định `gemini-3.8-flash`. Key được đọc bởi `coach/llm.py`, không ghi key vào repository. Không cấu hình key thì dùng bộ luật dự phòng.
   - Web Push: chạy `python manage.py generate_vapid_keys` trong môi trường local, nhập hai giá trị tương ứng vào `VAPID_PUBLIC_KEY` và `VAPID_PRIVATE_KEY` trên Render, rồi đặt `VAPID_CLAIMS_EMAIL=mailto:email-của-bạn`. Giữ private key kín và ổn định. Web Push cần HTTPS và mỗi người dùng phải cấp quyền trên trình duyệt của họ.
   - `WELLBEING_NUDGE_FROM_HOUR` mặc định `20` theo múi giờ ứng dụng; `WELLBEING_NUDGE_DROP_POINTS` mặc định `15`. Đây là ngưỡng nhắc nhở hỗ trợ, không phải ngưỡng sức khỏe.
4. Build xong, Render cung cấp URL service dạng `https://<service-name>.onrender.com`; dùng URL thực tế của service để kiểm tra và chia sẻ.

Lưu ý: kiểm tra lại tên gói (plan) free của web service và database trong tài liệu Render trước khi deploy, vì gói free có thể thay đổi. Web service gói free sẽ "ngủ" khi không có truy cập nên lần mở đầu chậm, và scheduler nhắc nhở chỉ chạy khi service đang thức.

## Ghi chú kỹ thuật

- **Không dùng `django.contrib.admin`** để quản trị viên không thể mở bảng dữ liệu cá nhân. Tạo admin bằng `python manage.py createsuperuser` (tự có role admin).
- Cookie JWT chỉ đọc được API bằng GET (để biểu đồ gọi API); các API ghi dữ liệu bắt buộc header Bearer nên không bị tấn công CSRF.
- Đăng nhập sai 5 lần sẽ bị khóa 15 phút.
- Thống kê ẩn danh chỉ hiển thị khi có từ 3 người dùng trở lên (`MIN_USERS_FOR_ADMIN_STATS`).
- **Giữ cố định `JOURNAL_ENCRYPTION_KEY`** (hoặc `SECRET_KEY` nếu không đặt riêng). Đổi khóa thì journal cũ không giải mã được.
- Khi có Gemini và người dùng đồng ý, AI coach nhận số liệu check-in, trạng thái thói quen và câu hỏi người dùng chủ động gửi; không tự động gửi journal, tên thói quen, username hay email. Câu hỏi được gửi nguyên văn nên tránh nhập thông tin nhận dạng. Bộ lọc cục bộ có thêm mẫu diễn đạt gián tiếp và phản hồi thận trọng, nhưng không thể bảo đảm nhận diện mọi cách diễn đạt hoặc thay thế hỗ trợ chuyên môn.
- Phần gọi Gemini (`coach/llm.py`) chưa được kiểm thử với API key thật; mọi lỗi sẽ tự quay về bộ luật dự phòng. Tên mô hình đặt qua `GEMINI_MODEL`; kiểm tra model đang được hỗ trợ trước khi đổi cấu hình.
