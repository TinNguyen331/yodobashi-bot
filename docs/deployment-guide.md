# Deployment Guide

## Yêu cầu hệ thống

- Python 3.8+
- Chromium browser (cài qua Playwright)
- RAM: ~200MB (HTTP polling) + ~300MB per Playwright instance
- Network: Kết nối ổn định đến yodobashi.com
- OS: Windows, macOS, hoặc Linux

## Cài đặt

### 1. Clone project

```bash
git clone <repo_url>
cd yodobashi-bot-fast
```

### 2. Tạo virtual environment

```bash
python -m venv venv

# Activate
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate
```

### 3. Cài dependencies

```bash
pip install -r requirements.txt
```

### 4. Cài Playwright browser

```bash
playwright install chromium
```

### 5. Cấu hình

```bash
cp config.example.yaml config.yaml
```

Sửa `config.yaml` với thông tin thật:
- `account` — Email + password Yodobashi
- `products` — Danh sách sản phẩm cần mua
- `payment` — Thông tin thẻ
- `shipping` — Địa chỉ giao hàng
- `settings` — Cài đặt bot

### 6. Kiểm tra trước khi chạy

```bash
# Test đăng nhập (mở browser để xác nhận)
python main.py --test-login

# Test tìm sản phẩm qua HTTP
python main.py --test-search

# Test full checkout (dry run, không mua thật)
python main.py --test-checkout
```

## Chạy bot

### Chạy bình thường (theo config)

```bash
python main.py
```

Bot chạy 24/7, không bao giờ tự dừng. Ctrl+C để tắt.

- `scheduled`: Chờ đến `start_time` mỗi ngày → poll → mua → chờ ngày mai
- `listening`: Poll liên tục → mua → tiếp tục poll
- Đạt giới hạn (`max_per_day`/`max_per_month`) → tự pause đến khi reset

### Chạy ngay (skip chờ giờ)

```bash
python main.py --run-now
```

Override tất cả products sang `listening` mode, polling ngay.

### Chạy background (Linux/macOS)

```bash
nohup python main.py > /dev/null 2>&1 &
```

### Chạy background (Windows)

```bash
start /B python main.py
```

Bot đã chạy 24/7 tự động, không cần Task Scheduler.

## Cấu hình chi tiết

### Scheduled mode (flash sale hàng ngày)

```yaml
- name: "FUJIFILM Instax Film"
  url: "https://www.yodobashi.com/product/100000001006011748"
  quantity: 5
  mode: "scheduled"
  start_time: "09:25"     # 5 phút trước giờ sale
  sale_time: "09:30"      # Giờ sale chính thức
  check_interval: 5       # Poll mỗi 5 giây khi đến giờ
  max_per_day: 5          # Tối đa 5 cái/ngày (0 = không giới hạn)
```

**Lưu ý:**
- `start_time` nên sớm hơn `sale_time` 3-5 phút
- `check_interval: 3-5` giây cho scheduled mode
- Bot tự lặp lại hàng ngày, chờ `start_time` ngày mai sau khi mua xong
- `max_per_day`: khi đạt limit → tự pause, reset khi qua ngày mới

### Listening mode (canh mở bán random)

```yaml
- name: "Nintendo Switch"
  url: "https://www.yodobashi.com/product/YYYYYYYYYY"
  quantity: 1
  mode: "listening"
  check_interval: 60      # Poll mỗi 60 giây
  max_per_month: 1        # Tối đa 1 cái/tháng (0 = không giới hạn)
```

**Lưu ý:**
- `check_interval: 60` giây để tránh bị rate limit
- Bot chạy 24/7, tiếp tục poll sau khi mua thành công/thất bại
- `max_per_month`: khi đạt limit → tự pause đến ngày 1 tháng sau
- Có thể set `check_interval: 30` nếu muốn nhanh hơn (rủi ro bị block)

## Troubleshooting

### Bot bị block/timeout
- Tăng `check_interval` (ít request hơn)
- Xoá `session/cookies.json` để reset session
- Check log file `logs/bot_YYYYMMDD.log` cho chi tiết

### Login thất bại
- Kiểm tra username/password trong `config.yaml`
- Chạy `python main.py --test-login` (hiện browser để debug)
- Check nếu Yodobashi yêu cầu CAPTCHA

### Sản phẩm available nhưng checkout fail
- Check screenshots trong `logs/*.png`
- Check HTML debug pages trong `logs/*.html`
- Thử `python main.py --test-checkout` với `headless: false`
- Yodobashi có thể thay đổi HTML structure → cần update selectors

### Playwright errors
- Reinstall: `playwright install chromium`
- Update: `pip install --upgrade playwright`

## Giám sát

- **Logs realtime**: `tail -f logs/bot_YYYYMMDD.log`
- **Screenshots**: Check `logs/*.png` sau mỗi lần chạy
- **Session**: `session/cookies.json` — xoá nếu cần reset

## Bảo mật

- **KHÔNG** commit `config.yaml` (chứa credentials)
- **KHÔNG** share `session/cookies.json`
- `config.yaml` đã được gitignore
- Cân nhắc encrypt config nếu chạy trên shared server
