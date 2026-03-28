# System Architecture

## Tổng quan

```
┌─────────────────────────────────────────────────────────────────┐
│                        main.py                                  │
│                   (CLI + Sequential Loop)                       │
│                                                                 │
│  run_sequential():                                              │
│    for each product in config (round-robin):                    │
│      - Check scheduled window if mode="scheduled"               │
│      - Check daily/monthly limits                               │
│      - Poll until available                                     │
│      - Purchase via Playwright                                  │
│      - Clear cart on failure                                    │
│      - Loop to next product                                     │
└──────────┬────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    round-robin processing                        │
│                                                                  │
│  For each product N (repeating round-robin):                    │
│     - Check if now is within start_time window (scheduled)       │
│     - Check daily/monthly limits, skip if reached               │
│     - Poll until available (every check_interval seconds):                │
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
│               │    │  Failure → CheckoutHandler.clear_cart()     │
│               │                                                  │
│               └──── Move to next product in round-robin ────────  │
└─────────────────────────────────────────────────────────────────┘
```

## Components

### 1. main.py — Sequential Loop Orchestrator

**Responsibilities:**
- CLI argument parsing
- Config loading
- Sequential product loop (round-robin processing)
- Test utilities (login, search, checkout)

**Key Functions:**
- `run_sequential()` — Main loop that processes all products sequentially (never returns)
- `_is_in_scheduled_window()` — Check if current time is within product's scheduled window
- `_wait_until_start_time()` — Wait until scheduled window begins
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

## Execution Model

- **Sequential processing** — Single main loop processes all products in round-robin order
- **No threading** — Products processed sequentially, not in parallel
- **Per-product session** — Single HttpSession instance reused for all products
- **Cart lifecycle** — Cleared on purchase failure before moving to next product
- **Purchase tracking** — Counters per product, stored in memory, auto-reset on date/month change
- **Main loop** — Runs forever (24/7), Ctrl+C to exit

## Purchase Limits

| Config | Mode | Behavior |
|--------|------|----------|
| `max_per_day: 5` | scheduled | Max 5 purchases/day, auto-reset at midnight |
| `max_per_month: 1` | listening | Max 1 purchase/month, auto-resume on 1st of next month |
| `0` or omitted | both | Unlimited (no limit enforced) |

## Security Considerations

- **config.yaml** contains credentials → MUST be in `.gitignore`, never commit
- **Akamai WAF bypass** — curl_cffi Chrome TLS impersonation
- **Session persistence** — Cookies stored locally in JSON, unencrypted (treat as sensitive)
- **Browser anti-detection** — Playwright launched with `--disable-blink-features=AutomationControlled`, ja-JP locale, Asia/Tokyo timezone
- **Rate limiting** — Respect `check_interval` to avoid IP blocks; recommend 5s (scheduled), 60s (listening)
- **No proxy** — All requests from single IP; risk of detection on heavy load
- **Credential scope** — Single account per bot instance; multi-account requires multiple config files
