# Codebase Summary

## Overview

Yodobashi Auto Purchase Bot — Python 3.x bot for automated purchasing on yodobashi.com. Supports multiple products processed sequentially in round-robin order. Each product runs 24/7 with independent purchase limit tracking (daily/monthly).

**Total Python code:** ~1,594 lines (excluding config & docs)

## File Structure

```
yodobashi-bot/
├── main.py              # Entry point, CLI parser, sequential loop orchestrator
├── bot/
│   ├── __init__.py      # Module init
│   ├── http_session.py  # HTTP client (curl_cffi + Chrome TLS)
│   ├── product_handler.py  # Product search, availability checking
│   ├── checkout_handler.py # Playwright checkout automation
│   ├── login_handler.py    # HTTP & checkout authentication
│   └── utils.py            # Config loader, logging setup, helpers
├── config.yaml          # User config (gitignored, credentials)
├── config.example.yaml  # Config template with comments
├── requirements.txt     # 7 dependencies (pinned versions)
├── logs/                # Runtime logs + screenshots (auto-created)
├── session/             # Persistent session cookies (auto-created)
└── docs/                # Project documentation
```

## Key Modules

### main.py (423 lines)
**Role:** Entry point, CLI orchestration, sequential loop management

**Key Exports:**
- `run_sequential(config)` — Main loop that processes all products sequentially (never returns)
- `_is_in_scheduled_window(product)` — Check if current time is within scheduled window
- `_wait_until_start_time(start_time_str, tag)` — Sleep until target time (daily for scheduled)
- `_wait_until_next_month(tag)` — Pause until monthly purchase limit resets
- `_navigate_to_product(handler, url, name, tag)` — URL navigation helper
- `test_login(config)` — Interactive login test via Playwright
- `test_search(config)` — Test HTTP product search, print first result
- `test_checkout(config)` — Full checkout test (dry-run, no purchase)
- `_run_tests(config)` — Dispatch test CLI commands

**Design:**
- Single loop processes all products round-robin (no threading)
- Cart cleared on purchase failure before next product
- Purchase counters (daily/monthly) stored per product, auto-reset on date/month change
- All output via loguru (console INFO+, file DEBUG+)

### bot/http_session.py (135 lines)
**Role:** HTTP layer with Chrome TLS fingerprint impersonation

**Key Class:** `HttpSession`
- `get(url)` → Response object (curl_cffi)
- `post(url, data)` → Response object
- `get_soup(url)` → BeautifulSoup parsed HTML
- `navigate_to_home()` → Load homepage (establish session)
- `save_session() / load_session()` → Cookie persistence to JSON
- Context manager: `with HttpSession() as http: ...`

**Details:**
- Base URL: `https://www.yodobashi.com/` (product pages) + `https://order.yodobashi.com/` (checkout)
- Chrome User-Agent + TLS fingerprint via curl_cffi (bypass Akamai WAF)
- Cookies persisted to `session/cookies.json`
- Follows redirects, 10s timeout (configurable)
- No proxy rotation; single session per bot instance

### bot/product_handler.py (264 lines)
**Role:** Product navigation and availability detection

**Key Class:** `ProductHandler`
- `navigate_to_product(url)` → Fetch product page, store as `current_soup`
- `search_product(name)` → HTTP search, return first result URL
- `is_product_available(soup)` → Check DOM for availability signals
- `reload_product_page()` → Re-fetch current product (polling)

**Availability Detection Logic:**
1. **Primary:** Check for `<div id="js_buyBoxMain">` → contains `<div class="quantityInfo numIpt">`
2. **Fallback:** Look for button `id="js_m_submitRelated"` (add to cart)
3. **Out-of-stock text:** "在庫なし" / "売り切れ" / "販売終了" → unavailable
4. Return: `True` (available) or `False` (out of stock)

**Note:** HTML structure may change; selector fallbacks included.

### bot/checkout_handler.py (486 lines)
**Role:** Browser automation for full checkout via Playwright

**Key Class:** `CheckoutHandler`
- `purchase(product)` → Main entry point; runs full checkout flow, returns `bool`
- `_handle_checkout_flow(page, dry_run)` → Add cart → Proceed → Login → Payment → Confirm
- `_click_proceed(page)` → Click "購入手続きに進む" (proceed button) with retries
- `_login_at_checkout(page)` → Fill 会員ID (username) + password at checkout
- `_enter_payment(page)` → Fill card details (number, expiry, CVV, holder name)
- `_confirm_order(page, dry_run)` → Click confirm or stop before confirm (dry-run)

**Checkout Flow (Step-by-step):**
1. Navigate to product URL
2. Set quantity via input field
3. Click "ショッピングカートに入れる" (add to cart button)
4. Click "購入手続きに進む" (proceed to checkout)
5. Skip recommend pages (if shown)
6. Check if logged in; if not, fill login form
7. Fill payment info (card, expiry, CVV, name)
8. Click confirm or pause (dry-run)

**Anti-Detection:**
- Playwright launched with flags: `--disable-blink-features=AutomationControlled`, ja-JP locale, Asia/Tokyo timezone
- Headless mode configurable (false = visible, true = headless)
- Screenshots saved on error to `logs/*.png`
- HTML page dumps to `logs/*.html` for debug

### bot/login_handler.py (221 lines)
**Role:** Authentication for HTTP and checkout flows

**Key Class:** `LoginHandler`
- `is_logged_in(soup)` → Check HTML for "ログアウト" or "マイページ" links
- `login()` → HTTP POST login (main site)
- `login_at_checkout(url, html)` → Handle login page during checkout

**Login Detection:**
- Presence of "ログアウト" (logout link) → logged in
- Presence of "マイページ" (my page link) → logged in
- Presence of "ログイン" (login link) → not logged in

**HTTP Login POST:**
- Endpoint: `/servlet/web/login/login_request.html`
- Form fields: `j_username`, `j_password`
- Cookies saved after successful POST

### bot/utils.py (64 lines)
**Role:** Shared utilities and initialization

**Key Functions:**
- `load_config(path)` → Load YAML config, validate required fields
- `setup_logging(log_dir)` → Configure loguru (console + rotating file)
- `get_project_root()` → Get project directory via `Path(__file__).parent`
- `wait_until_time(time_str)` → Sleep until target time (e.g., "09:30")

## Configuration Schema

**File:** `config.yaml` (not in repo; copy from `config.example.yaml`)

### Structure:
```yaml
account:
  username: string      # Yodobashi email/ID
  password: string      # Password

products:              # List of products to monitor
  - name: string        # Display name
    url: string         # Full product URL
    quantity: int       # Qty per purchase (usually 1)
    mode: string        # "scheduled" | "listening"
    start_time: string  # HH:MM (scheduled only)
    sale_time: string   # HH:MM (info only, for reference)
    check_interval: int # Seconds between polls
    max_per_day: int    # Daily limit (scheduled, 0=unlimited)
    max_per_month: int  # Monthly limit (listening, 0=unlimited)

payment:
  card_number: string
  expiry_month: string  # MM (01-12)
  expiry_year: string   # YY (24-99)
  cvv: string
  card_holder_name: string

shipping:
  full_name: string
  postal_code: string   # XXX-XXXX
  prefecture: string    # Prefecture name (Japanese)
  city: string          # City name (Japanese)
  address_line1: string # Address
  address_line2: string # Apt/building (optional)
  phone: string         # Phone number

coupon_code: string     # Optional promo code

settings:
  max_retries: int      # Login retry count (default: 3)
  dry_run: bool         # false = purchase, true = stop before confirm
  headless: bool        # true = hidden browser, false = visible
  timeout: int          # Request/page timeout (seconds, default: 30)
  screenshot_on_error: bool  # true = save PNG on checkout error
  require_confirmation: bool # true = prompt before confirm
```

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| curl_cffi | >=0.7.0 | HTTP client w/ Chrome TLS fingerprint |
| beautifulsoup4 | >=4.12.0 | HTML parsing (product pages) |
| pyyaml | 6.0.1 | YAML config loading |
| apscheduler | 3.10.4 | (Installed but not currently used) |
| loguru | 0.7.2 | Structured logging (console + file) |
| lxml | >=5.0.0 | XML/HTML backend for BeautifulSoup |
| playwright | >=1.49.0 | Browser automation (checkout) |

## Purchase Flow (Overview)

### Mode: Scheduled (Daily Flash Sale)
1. Wait until `start_time` each day
2. Poll product every `check_interval` seconds
3. When available → start checkout
4. After purchase → wait for `start_time` next day
5. Stop if `max_per_day` reached (auto-resume after midnight reset)

### Mode: Listening (Random Restock)
1. Poll product immediately every `check_interval` seconds
2. When available → start checkout
3. After purchase/failure → continue polling
4. Stop if `max_per_month` reached (auto-resume on 1st of next month)

## Logging & Debug

| Type | Location | Rotation | Retention |
|------|----------|----------|-----------|
| Console | stdout | None | N/A |
| File logs | `logs/bot_YYYYMMDD.log` | Daily | 7 days |
| Screenshots | `logs/*.png` | Manual | Manual cleanup |
| Debug HTML | `logs/*.html` | Manual | Manual cleanup |

**Log Levels:**
- `DEBUG` — HTTP requests/responses, full context (file only)
- `INFO` — Status, step progress
- `SUCCESS` — Key milestones (login, add to cart, purchase)
- `WARNING` — Non-critical issues, dry-run stops
- `ERROR` — Flow failures, exceptions

**Tag Format:** `[P0]`, `[P1]`, etc. per product thread

## Execution Model

- **Main loop:** Single sequential loop, processes all products round-robin, runs forever
- **No threading:** Products processed sequentially, not in parallel
- **Shared HTTP session:** Single HttpSession instance reused for all products
- **Cart cleanup:** Cleared on purchase failure before moving to next product
- **Purchase tracking:** Per-product counters (daily_count, monthly_count), auto-reset on date/month change
- **Synchronization:** None required (single-threaded execution)

## Anti-Detection Strategy

### HTTP Layer (curl_cffi)
- Chrome User-Agent impersonation
- TLS fingerprint matching Chrome (bypass Akamai WAF)
- Session cookies persisted between runs
- No proxy rotation

### Browser Layer (Playwright)
- Chrome launch flags: `--disable-blink-features=AutomationControlled`
- Locale: ja-JP (Japan)
- Timezone: Asia/Tokyo
- Headless mode (default) or visible (for debugging)
- No stealth plugin (native Playwright anti-detection)

## Testing Utilities

### CLI Commands
```bash
python main.py                      # Run normally
python main.py --run-now            # Skip wait, start immediately
python main.py --test-login         # Test Playwright login
python main.py --test-search        # Test HTTP search (first product)
python main.py --test-checkout      # Test full checkout (dry-run)
python main.py --config custom.yaml # Use custom config
```

### How Tests Work
- `--test-login`: Spawns Playwright, navigates to Yodobashi, prompts manual login
- `--test-search`: Makes HTTP request, parses product page, prints availability
- `--test-checkout`: Runs full checkout flow with `dry_run: true` (stops before confirm)

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Hybrid HTTP + Browser** | HTTP polling is fast (~1s), Playwright checkout handles complex JS flows. Akamai WAF blocks HTTP requests post-cart; requires browser for checkout. |
| **curl_cffi over requests** | TLS fingerprint impersonation bypasses Akamai detection; `requests` library easily detected. |
| **Sequential over parallel** | Avoids cart conflicts; sequential loop processes all products round-robin, cart cleared on failure. |
| **No unit tests** | Manual CLI testing sufficient; integration tests via --test-* commands. |
| **Cookie persistence** | Avoids repeated logins; session reusable across runs. |
| **Dry-run mode** | Test full flow without committing purchase; safety mechanism. |

## Known Limitations

1. **HTML structure changes** — Yodobashi may update selectors; fallbacks included but may need manual updates
2. **CAPTCHA** — Not currently handled; may require manual intervention
3. **Rate limiting** — Akamai may block if `check_interval` too low; recommend 5s for scheduled, 60s for listening
4. **Single account** — Config supports one account per bot instance
5. **No proxy** — All requests from single IP; risk of detection/blocking on heavy load
6. **Payment limitations** — Only credit card supported; no convenience store payment, Apple Pay, etc.

## Security Notes

- `config.yaml` contains credentials → **MUST be gitignored and never committed**
- Session cookies stored locally unencrypted in `session/cookies.json` → treat as sensitive
- Yodobashi IP-blocks aggressive scrapers → respect `check_interval` to avoid detection
- Playwright browser runs locally; no remote browser needed
