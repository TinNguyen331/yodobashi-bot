# System Architecture

## Tổng quan

```
┌─────────────────────────────────────────────────────────────────┐
│                        main.py                                  │
│                   (CLI + Orchestrator)                          │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Thread 1   │  │   Thread 2   │  │   Thread N   │          │
│  │  Product A   │  │  Product B   │  │  Product N   │          │
│  │  (scheduled) │  │  (listening) │  │  (any mode)  │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
└─────────┼─────────────────┼─────────────────┼──────────────────┘
          │                 │                 │
          ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                    watch_product()                               │
│                                                                  │
│  0. 24/7 Outer Loop (never exits):                              │
│     - Reset daily/monthly counters on date change               │
│     - Check limits: skip if max_per_day/max_per_month reached   │
│     [scheduled] Wait until start_time, repeat daily             │
│     [listening] Start immediately                               │
│                                                                  │
│  1. Polling Loop (every check_interval seconds):                │
│     ┌──────────────────────────────────────┐                    │
│     │  HttpSession.reload_product_page()   │ ← curl_cffi       │
│     │  ProductHandler.is_product_available()│ ← BeautifulSoup   │
│     └──────────────┬───────────────────────┘                    │
│                    │ Available?                                   │
│               No ──┤── Yes                                      │
│               │    │                                             │
│           sleep()  ▼                                             │
│               │  ┌───────────────────────────┐                  │
│               │  │ CheckoutHandler.purchase() │ ← Playwright    │
│               │  │ (Add → Login → Pay → Confirm)│               │
│               │  └───────────────────────────┘                  │
│               │    │  Success → daily_count++ / monthly_count++  │
│               │    │  Limit reached? → pause until reset         │
│               │                                                  │
│               └──── continue loop (24/7, never exits) ────────  │
└─────────────────────────────────────────────────────────────────┘
```

## Components

### 1. main.py — 24/7 Orchestrator

**Responsibilities:**
- CLI argument parsing
- Config loading
- Thread management (1 thread per product)
- Test utilities (login, search, checkout)

**Key Functions:**
- `watch_product()` — Per-product 24/7 watcher loop (never returns)
- `run_all_products()` — Multi-thread orchestrator (runs forever)
- `_wait_until_start_time()` — Wait for daily scheduled start
- `_wait_until_next_month()` — Pause until monthly limit resets
- `test_login()` / `test_search()` / `test_checkout()` — Test helpers

### 2. bot/http_session.py — HTTP Session (135 lines)

**Responsibilities:**
- HTTP requests với Chrome TLS fingerprint (curl_cffi)
- Cookie persistence (save/load từ `session/cookies.json`)
- HTML page fetching & debug saving

**Key Details:**
- Impersonate Chrome để bypass Akamai WAF
- Base URLs: `yodobashi.com` (main) + `order.yodobashi.com` (checkout)
- Context manager support (`with HttpSession() as http`)

### 3. bot/product_handler.py — Product Operations (264 lines)

**Responsibilities:**
- Navigate to product page (by URL or search)
- Check product availability (HTML parsing)
- Add to cart via HTTP (legacy, không dùng trong flow chính)

**Availability Detection:**
1. Primary: `<div id="js_buyBoxMain">` chứa `<div class="quantityInfo numIpt">`
2. Fallback: Button `id="js_m_submitRelated"`
3. Out-of-stock: Text "在庫なし", "売り切れ", "販売終了"

### 4. bot/checkout_handler.py — Purchase Flow (486 lines)

**Responsibilities:**
- Full checkout qua Playwright browser
- Add to cart → Proceed → Login → Payment → Confirm
- Dry run mode (dừng trước confirm)
- Screenshot on errors

**Checkout Steps:**
1. Navigate to product URL
2. Set quantity + click "ショッピングカートに入れる"
3. Click "購入手続きに進む" (proceed)
4. Handle recommend/cart pages
5. Login if required (会員ID + password)
6. Enter payment (card, expiry, CVV)
7. Confirm order or dry-run stop

### 5. bot/login_handler.py — Authentication (221 lines)

**Responsibilities:**
- Login qua HTTP POST (main site)
- Login during checkout (order site)
- Login state detection

**Login Detection:**
- "ログアウト" link → logged in
- "マイページ" link → logged in
- "ログイン" link → not logged in

### 6. bot/utils.py — Utilities (64 lines)

**Responsibilities:**
- YAML config loading
- Loguru setup (console + rotating file)
- Project root path resolution
- Time-based waiting

## Data Flow

```
config.yaml
    │
    ▼
┌─────────┐    ┌──────────────┐    ┌─────────────────┐
│ main.py │───▶│ HttpSession  │───▶│ ProductHandler   │
│         │    │ (curl_cffi)  │    │ (availability)   │
│         │    └──────────────┘    └────────┬──────────┘
│         │                                │ available
│         │    ┌──────────────────┐         │
│         │───▶│ CheckoutHandler  │◀────────┘
│         │    │ (Playwright)     │
│         │    └────────┬─────────┘
│         │             │
└─────────┘             ▼
                  ┌─────────────┐
                  │ Order Done  │
                  │ or Dry Run  │
                  └─────────────┘
```

## Persistence

| Data | Location | Format | Lifetime |
|------|----------|--------|----------|
| Config | `config.yaml` | YAML | Permanent |
| Cookies | `session/cookies.json` | JSON | Between runs |
| Logs | `logs/bot_YYYYMMDD.log` | Text | 7 days (rotation) |
| Screenshots | `logs/*.png` | PNG | Manual cleanup |
| Debug HTML | `logs/*.html` | HTML | Manual cleanup |

## Threading Model

- **Single product**: Chạy trong main thread (chạy mãi)
- **Multiple products**: Mỗi product 1 daemon thread (chạy mãi)
- **Không shared state**: Mỗi thread có HttpSession, ProductHandler, CheckoutHandler riêng
- **Main thread**: Sleep vĩnh viễn (1h intervals), Ctrl+C để dừng
- **Purchase tracking**: Mỗi thread tự track daily_count/monthly_count, auto-reset

## Purchase Limits

| Config | Mode | Hành vi |
|--------|------|---------|
| `max_per_day: 5` | scheduled | Mua tối đa 5/ngày, reset khi qua ngày mới |
| `max_per_month: 1` | listening | Mua tối đa 1/tháng, pause đến ngày 1 tháng sau |
| `0` hoặc không set | cả 2 | Không giới hạn |

## Security Considerations

- `config.yaml` chứa credentials → trong `.gitignore`
- Akamai WAF bypass qua Chrome TLS impersonation
- Session cookies lưu local, không encrypt
- Playwright chạy với anti-detection flags
- Rate limiting qua `check_interval` config
