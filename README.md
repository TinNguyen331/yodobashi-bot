# Yodobashi Auto Purchase Bot (Fast/Hybrid)

Bot tự động mua hàng trên Yodobashi.com. Mỗi instance theo dõi 1 sản phẩm.

## Tính năng

- **1 sản phẩm = 1 instance** — chạy nhiều instance với config riêng cho nhiều sản phẩm
- **Bot chạy 24/7** — tự động mua khi có hàng, dừng khi Ctrl+C
- **2 chế độ mua hàng:**
  - `scheduled` — Sản phẩm mở bán cố định theo giờ
  - `listening` — Sản phẩm mở bán ngẫu nhiên, canh 24/7
- **Giới hạn mua** — `max_per_day` (scheduled) và `max_per_month` (listening)
- **Xóa giỏ hàng khi lỗi** — tự động clear cart khi mua thất bại
- **HTTP + Browser** — HTTP polling nhanh, Playwright checkout chính xác
- **Chế độ thử** — `dry_run: true` để test mà không mua thật

## Cài đặt

```bash
# 1. Tạo virtual environment
python -m venv venv

# 2. Activate
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# 3. Cài dependencies
pip install -r requirements.txt

# 4. Cài Playwright browser
playwright install chromium

# 5. Tạo config
cp config.example.yaml config.yaml
# Sửa config.yaml với thông tin tài khoản và sản phẩm
```

## Cấu hình

Sửa file `config.yaml`:

```yaml
product:
  name: "Tên sản phẩm"
  url: "https://www.yodobashi.com/product/XXXXXXXXXX"
  quantity: 1
  mode: "listening"        # scheduled | listening
  check_interval: 60       # Kiểm tra mỗi N giây
  max_per_month: 1         # Giới hạn/tháng (0 = không giới hạn)
```

Xem `config.example.yaml` để biết đầy đủ các trường.

## Sử dụng

```bash
# Chạy bot (1 sản phẩm theo config.yaml)
python main.py

# Chạy nhiều sản phẩm = nhiều instance (mỗi terminal 1 sản phẩm)
python main.py --config config-sanpham1.yaml
python main.py --config config-sanpham2.yaml

# Chạy ngay (bỏ qua chờ giờ scheduled)
python main.py --run-now

# Test checkout (chế độ thử, không mua thật)
python main.py --test-checkout

# Test tìm sản phẩm
python main.py --test-search

# Test đăng nhập
python main.py --test-login
```

## Cài đặt quan trọng

| Cài đặt | Mô tả |
|---------|--------|
| `dry_run: true` | Dừng trước bước xác nhận, không mua thật |
| `headless: true` | Không hiện browser khi checkout |
| `require_confirmation: true` | Hỏi xác nhận trước khi đặt hàng |
| `screenshot_on_error: true` | Chụp ảnh khi lỗi để debug |
| `max_per_day: N` | Giới hạn mua/ngày cho scheduled (0 = không giới hạn) |
| `max_per_month: N` | Giới hạn mua/tháng cho listening (0 = không giới hạn) |

## Cấu trúc dự án

```
yodobashi-bot/
├── main.py                  # Điểm vào, vòng lặp chính
├── bot/
│   ├── http_session.py      # HTTP session (curl_cffi)
│   ├── product_handler.py   # Tìm kiếm & kiểm tra sản phẩm
│   ├── checkout_handler.py  # Checkout qua Playwright
│   ├── login_handler.py     # Đăng nhập HTTP
│   └── utils.py             # Config, logging, helpers
├── config.yaml              # Config thật (không commit)
├── config.example.yaml      # Config mẫu
├── logs/                    # Log files & screenshots
└── session/                 # Cookie persistence
```

## Kiến trúc

```
┌──────────────────────────────────────────────────┐
│           main.py (Vòng lặp 1 sản phẩm)           │
│  run_single_product():                            │
│    while True:                                    │
│      - Kiểm tra còn hàng qua HTTP                 │
│      - Nếu có: mua qua Playwright                 │
│      - Nếu lỗi: xóa giỏ hàng                      │
│      - Chờ → lặp lại                              │
└──────────┬───────────────────────────────────────┘
           │
    ┌──────┴──────┐
    │ HTTP Polling │  ← curl_cffi (nhanh, ko cần browser)
    │ (curl_cffi)  │  ← Kiểm tra mỗi N giây
    └──────┬──────┘
           │ Khi có hàng
    ┌──────┴──────┐
    │  Playwright  │  ← Browser checkout
    │  (Checkout)  │  ← Thêm giỏ → Login → Thanh toán → Xác nhận
    └──────┬──────┘
           │ Thành công / Thất bại
           │ → Xóa giỏ hàng nếu lỗi
           │ → Tiếp tục theo dõi
           └──→ CHẠY 24/7 (dừng bằng Ctrl+C)
```

## Logs & Debug

- Console: hiển thị INFO trở lên
- File: `logs/bot_YYYYMMDD.log` (DEBUG, xoay vòng hàng ngày, giữ 7 ngày)
- Screenshots: `logs/*.png` khi lỗi checkout
- HTML: `logs/*.html` khi cần debug response
