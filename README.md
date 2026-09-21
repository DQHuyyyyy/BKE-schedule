# BKE Weekend Notifier

Tự động kiểm tra lịch học của **BKE** (đứng sau trang
https://bke.edu.vn/lich/), phát hiện khóa học **Offline tổ chức tại Hà
Nội** rơi vào **thứ Bảy/Chủ Nhật**, và gửi thông báo qua **Zalo Bot** khi
phát hiện lịch mới.

## Nguồn dữ liệu

Trang `bke.edu.vn/lich/` hiển thị lịch bằng cách nhúng một trang phụ
(`myluuu190103.github.io/DuPhongCode`), và trang phụ đó load dữ liệu trực
tiếp từ một **Google Sheet công khai** dạng CSV. Script này đọc thẳng CSV
đó — đây chính là nguồn "thật", cập nhật ngay khi BKE sửa lịch, không cần
qua trình duyệt/JS.

Nếu sau này BKE đổi cách hiển thị lịch, chỉ cần cập nhật lại
`SHEET_CSV_URL` trong `check_bke_weekend.py` cho đúng nguồn mới.

## Cách hoạt động

1. Mỗi ngày (theo lịch cron trong GitHub Actions), script tải CSV lịch học.
2. Lọc các dòng có **Địa điểm chứa "Hà Nội"** và **Hình thức khác "Zoom"**
   thuần (tức có phần Offline).
3. Với mỗi khóa, kiểm tra khoảng ngày (Từ ngày → Đến ngày) có rơi vào thứ
   Bảy/Chủ Nhật không.
4. Nếu có khóa mới thoả điều kiện (theo `ID record` trong Sheet, chưa từng
   thông báo trước đó, lưu trong `state.json`), gửi tin nhắn qua Zalo Bot.

## Cài đặt (một lần)

### 1. Đưa code này lên GitHub

Tạo 1 repo mới (có thể để **Private**), đẩy toàn bộ các file này lên.

### 2. Thêm Secrets cho repo

Vào repo trên GitHub → **Settings → Secrets and variables → Actions →
New repository secret**, thêm 2 secret:

| Tên | Giá trị |
|---|---|
| `ZALO_BOT_TOKEN` | Token bot của anh (dạng `số:chuỗi`) |
| `ZALO_CHAT_ID` | chat_id lấy được từ `getUpdates` |

**Không** để token/chat_id trực tiếp trong code hay commit lên GitHub.

### 3. Bật Actions

Vào tab **Actions** của repo, bật workflow "Kiem tra lich BKE cuoi tuan
(Ha Noi)" nếu GitHub hỏi. Có thể bấm **Run workflow** để chạy thử ngay,
không cần chờ tới giờ cron.

### 4. (Tuỳ chọn) Đổi giờ chạy

M��c định chạy 08:00 sáng giờ Việt Nam mỗi ngày. Muốn đổi giờ, sửa dòng
`cron` trong file `.github/workflows/check-bke.yml` (giờ ghi theo UTC,
Việt Nam = UTC+7).

## Chạy thử trên máy cá nhân (không bắt buộc)

```bash
pip install -r requirements.txt

# Chạy thử, chỉ in ra console, không gửi Zalo:
DRY_RUN=1 python3 check_bke_weekend.py

# Chạy thật (cần có token + chat_id):
ZALO_BOT_TOKEN="xxx" ZALO_CHAT_ID="xxx" python3 check_bke_weekend.py
```

## Cấu trúc file

```
check_bke_weekend.py        # Script chính: đọc CSV + gửi thông báo
requirements.txt            # Thư viện Python cần cài
state.json                  # Lưu các sự kiện đã thông báo (tránh trùng lặp)
.github/workflows/check-bke.yml   # Lịch chạy tự động hằng ngày
```
