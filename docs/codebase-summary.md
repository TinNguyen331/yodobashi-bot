# Codebase Summary

## Files Overview

| File | Lines | Mô tả |
|------|-------|--------|
| `main.py` | ~390 | Entry point, CLI, 24/7 orchestrator, purchase tracking |
| `bot/http_session.py` | 135 | HTTP client với Chrome TLS fingerprint |
| `bot/product_handler.py` | 264 | Tìm kiếm & kiểm tra availability sản phẩm |
| `bot/checkout_handler.py` | 486 | Full checkout flow qua Playwright |
| `bot/login_handler.py` | 221 | Đăng nhập HTTP (main site + checkout) |
| `bot/utils.py` | 64 | Config loader, logging setup, helpers |
| `config.example.yaml` | 50 | Config mẫu với giải thích |
| **Total Python** | **1,507** | |

## Dependencies

| Package | Version | Vai trò |
|---------|---------|---------|
| curl_cffi | >=0.7.0 | HTTP client giả lập Chrome TLS fingerprint |
| beautifulsoup4 | >=4.12.0 | HTML parser cho product pages |
| pyyaml | 6.0.1 | Đọc YAML config |
| apscheduler | 3.10.4 | Installed nhưng chưa sử dụng |
| loguru | 0.7.2 | Structured logging (console + file) |
| lxml | >=5.0.0 | Backend parser cho BeautifulSoup |
| playwright | >=1.49.0 | Browser automation cho checkout |

## Key Classes & Functions

### main.py
- `watch_product(product, config, index)` — 24/7 watcher loop (never returns)
- `run_all_products(config)` — Orchestrator, runs forever
- `_wait_until_start_time(time_str, tag)` — Wait for daily start
- `_wait_until_next_month(tag)` — Pause until monthly limit reset
- `_navigate_to_product(handler, url, name, tag)` — Navigate helper
- `test_login(config)` — Test login qua Playwright
- `test_search(config)` — Test HTTP product search
- `test_checkout(config)` — Test full checkout (dry run)

### HttpSession
- `get(url)` / `post(url, data)` — HTTP requests với Chrome impersonation
- `get_soup(url)` — GET + parse BeautifulSoup
- `navigate_to_home()` — Load homepage (establish session)
- `save_session()` / `load_session()` — Cookie persistence

### ProductHandler
- `navigate_to_product(url)` — Load product page by URL
- `search_product(name)` — Search by name, return first result URL
- `is_product_available(soup)` — Check availability via HTML parsing
- `reload_product_page()` — Re-fetch current product (polling)

### CheckoutHandler
- `purchase(product)` — Full checkout flow in Playwright
- `_handle_checkout_flow(page, dry_run)` — Login + payment + confirm
- `_click_proceed(page)` — Click proceed button (multiple fallbacks)
- `_login_at_checkout(page)` — Fill credentials during checkout
- `_enter_payment(page)` — Fill card details
- `_confirm_order(page, dry_run)` — Final confirmation or dry-run stop

### LoginHandler
- `is_logged_in(soup)` — Check login state via HTML
- `login()` — Login qua HTTP POST
- `login_at_checkout(url, html)` — Handle checkout login page

### Utils
- `load_config(path)` — Load YAML config
- `setup_logging(log_dir)` — Configure loguru
- `get_project_root()` — Get project directory
- `wait_until_time(time_str)` — Sleep until target time

## Configuration Schema

```yaml
account:
  username: string      # Email đăng nhập Yodobashi
  password: string      # Mật khẩu

products:               # Danh sách sản phẩm (chạy song song)
  - name: string        # Tên sản phẩm
    url: string         # URL sản phẩm
    quantity: int        # Số lượng mua
    mode: string        # "scheduled" | "listening"
    start_time: string  # HH:MM — chỉ dùng cho scheduled mode
    sale_time: string   # HH:MM — giờ mở bán (info only)
    check_interval: int # Giây giữa mỗi lần check
    max_per_day: int    # Giới hạn mua/ngày, 0 = unlimited (scheduled)
    max_per_month: int  # Giới hạn mua/tháng, 0 = unlimited (listening)

payment:
  card_number: string
  expiry_month: string
  expiry_year: string
  cvv: string
  card_holder_name: string

shipping:
  full_name: string
  postal_code: string
  prefecture: string
  city: string
  address_line1: string
  address_line2: string
  phone: string

coupon_code: string     # Mã giảm giá (optional)

settings:
  max_retries: int      # Số lần retry login (default: 3)
  dry_run: bool         # true = không mua thật
  headless: bool        # true = không hiện browser
  timeout: int          # Timeout request/page load (giây)
  screenshot_on_error: bool
  require_confirmation: bool  # true = hỏi trước khi confirm
```
