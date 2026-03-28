# Yodobashi Auto Purchase Bot (Fast/Hybrid)

Bot tự động mua hàng trên Yodobashi.com, hỗ trợ mua nhiều sản phẩm cùng lúc với 2 chế độ mua hàng.

## Tính năng

- **Mua nhiều sản phẩm** — xử lý tuần tự round-robin, tránh xung đột cart
- **Bot chạy 24/7** — không bao giờ dừng, tự chạy tiếp sau mua thành công/thất bại
- **2 chế độ mua hàng:**
  - `scheduled` — Sản phẩm mở bán cố định theo giờ, lặp lại hàng ngày
  - `listening` — Sản phẩm mở bán ngẫu nhiên, canh liên tục 24/7
- **Giới hạn mua** — `max_per_day` (scheduled) và `max_per_month` (listening), tự reset
- **Hybrid HTTP + Browser** — HTTP polling nhanh, Playwright checkout chính xác
- **Dry Run** — Test toàn bộ flow mà không mua thật
- **Anti-detection** — Chrome TLS fingerprint qua curl_cffi

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
products:
  # Chế độ 1: Flash sale cố định theo giờ
  - name: "Tên sản phẩm"
    url: "https://www.yodobashi.com/product/XXXXXXXXXX"
    quantity: 1
    mode: "scheduled"
    start_time: "09:25"    # Bắt đầu check trước giờ sale
    sale_time: "09:30"     # Giờ mở bán chính thức
    check_interval: 5      # Check mỗi 5 giây
    max_per_day: 5         # Tối đa 5 cái/ngày (0 = không giới hạn)

  # Chế độ 2: Canh mở bán ngẫu nhiên
  - name: "Sản phẩm random"
    url: "https://www.yodobashi.com/product/YYYYYYYYYY"
    quantity: 1
    mode: "listening"
    check_interval: 60     # Check mỗi 60 giây (24/7)
    max_per_month: 1       # Tối đa 1 cái/tháng (0 = không giới hạn)
```

Xem `config.example.yaml` để biết đầy đủ các trường cấu hình.

## Sử dụng

```bash
# Chạy bot (tất cả sản phẩm theo config)
python main.py

# Chạy ngay, bỏ qua chờ giờ (scheduled -> listening)
python main.py --run-now

# Test checkout (dry run, không mua thật)
python main.py --test-checkout

# Test tìm sản phẩm qua HTTP
python main.py --test-search

# Test đăng nhập
python main.py --test-login

# Dùng config file khác
python main.py --config path/to/config.yaml
```

## Cài đặt quan trọng

| Setting | Mô tả |
|---------|--------|
| `dry_run: true` | Dừng trước bước xác nhận, không mua thật |
| `headless: true` | Không hiện browser khi checkout |
| `require_confirmation: true` | Hỏi xác nhận trước khi đặt hàng |
| `screenshot_on_error: true` | Chụp ảnh khi lỗi để debug |
| `max_per_day: N` | Giới hạn mua/ngày cho scheduled (0 = unlimited) |
| `max_per_month: N` | Giới hạn mua/tháng cho listening (0 = unlimited) |

## Cấu trúc dự án

```
yodobashi-bot-fast/
├── main.py                  # Entry point, sequential loop orchestrator
├── bot/
│   ├── http_session.py      # HTTP session (curl_cffi, Chrome TLS)
│   ├── product_handler.py   # Tìm kiếm & kiểm tra sản phẩm
│   ├── checkout_handler.py  # Checkout qua Playwright
│   ├── login_handler.py     # Đăng nhập HTTP
│   └── utils.py             # Config, logging, helpers
├── config.yaml              # Config thật (không commit)
├── config.example.yaml      # Config mẫu
├── logs/                    # Log files & screenshots
├── session/                 # Cookie persistence
└── docs/                    # Documentation
```

## Kiến trúc

```
┌──────────────────────────────────────────────────┐
│           main.py (Sequential Loop)               │
│  run_sequential():                                │
│    for each product (round-robin):                │
│      - Check availability via HTTP                │
│      - If available: purchase via Playwright      │
│      - On failure: clear cart before next product │
│      - Repeat forever                             │
└──────────┬───────────────────────────────────────┘
           │
    ┌──────┴──────┐
    │ HTTP Polling │  ← curl_cffi (nhanh, không cần browser)
    │ (curl_cffi)  │  ← Check availability mỗi N giây
    └──────┬──────┘
           │ Khi sản phẩm available
    ┌──────┴──────┐
    │  Playwright  │  ← Browser automation (checkout)
    │  (Checkout)  │  ← Add to cart → Login → Payment → Confirm
    └──────┬──────┘
           │ Mua xong / thất bại
           │ → Clear cart on failure (tránh xung đột)
           │ → Move to next product in round-robin
           │ → Repeat forever
           └──→ LOOP FOREVER
```

## Logs & Debug

- Console: log INFO trở lên
- File: `logs/bot_YYYYMMDD.log` (DEBUG, rotate hàng ngày, giữ 7 ngày)
- Screenshots: `logs/*.png` khi lỗi checkout
- HTML pages: `logs/*.html` khi cần debug response
