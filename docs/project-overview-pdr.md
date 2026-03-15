# Project Overview — Yodobashi Auto Purchase Bot

## Mục tiêu

Bot tự động mua hàng trên Yodobashi.com, hỗ trợ mua nhiều sản phẩm đồng thời với 2 chế độ:
1. **Scheduled** — Sản phẩm flash sale cố định theo giờ hàng ngày
2. **Listening** — Sản phẩm mở bán ngẫu nhiên, giới hạn số lượng theo tháng

## Vấn đề cần giải quyết

- Sản phẩm giới hạn trên Yodobashi bán hết rất nhanh (vài giây)
- Cần tự động hoá quy trình: check availability → add to cart → checkout
- Cần hỗ trợ nhiều sản phẩm cùng lúc với các lịch mở bán khác nhau
- Yodobashi có hệ thống chống bot (Akamai WAF, TLS fingerprinting)

## Giải pháp: Hybrid HTTP + Browser

### Tại sao Hybrid?

| Tác vụ | HTTP (curl_cffi) | Browser (Playwright) |
|--------|-------------------|----------------------|
| Check availability | Nhanh (~1s), nhẹ | Chậm (~5s), nặng |
| Add to cart | Không khả thi (*) | Hoạt động |
| Checkout | Không khả thi (*) | Hoạt động |

(*) Yodobashi dùng Akamai WAF — session cookies gắn với browser context cụ thể, không thể transfer giữa HTTP và browser.

### Flow

1. **HTTP polling** (curl_cffi) — check sản phẩm available mỗi N giây
2. Khi available → khởi động **Playwright browser**
3. Playwright thực hiện toàn bộ checkout flow
4. Kết quả log ra console + file

## Phạm vi

### Trong phạm vi
- Multi-product concurrent purchasing
- 2 purchase modes (scheduled, listening)
- HTTP-based availability polling
- Browser-based checkout automation
- Dry run testing
- Session persistence (cookies)
- Error logging & screenshots

### Ngoài phạm vi
- GUI/web interface
- Proxy rotation
- CAPTCHA solving
- Mobile app automation
- Multi-account support

## Tech Stack

| Component | Technology | Vai trò |
|-----------|-----------|---------|
| Language | Python 3.x | - |
| HTTP Client | curl_cffi | TLS fingerprint impersonation |
| HTML Parser | BeautifulSoup + lxml | Parse product pages |
| Browser | Playwright (Chromium) | Checkout automation |
| Config | PyYAML | YAML configuration |
| Logging | Loguru | Structured logging |
| Scheduling | Threading (built-in) | Concurrent product watching |

## Stakeholders

- **User**: Người muốn mua sản phẩm giới hạn trên Yodobashi
- **Target**: Yodobashi.com (Japanese e-commerce)

## Rủi ro

| Rủi ro | Mức độ | Giảm thiểu |
|--------|--------|------------|
| Yodobashi thay đổi HTML structure | Trung bình | Selector fallbacks, log HTML debug |
| Akamai block request | Cao | Chrome TLS impersonation, session persistence |
| Race condition khi checkout | Thấp | Mỗi product thread độc lập |
| Tài khoản bị ban | Trung bình | Rate limiting qua check_interval |
