# Project Overview — Yodobashi Auto Purchase Bot

## Objectives

Automated purchasing bot for yodobashi.com supporting:
- **Multiple products** — Up to N products monitored concurrently (each in separate thread)
- **Two purchase modes:**
  - **Scheduled** — Fixed-time daily flash sales (e.g., 9:30 AM every day)
  - **Listening** — Random restock monitoring (24/7 continuous polling)
- **24/7 operation** — Never stops, auto-resumes after purchase/failure
- **Purchase limits** — Daily caps (scheduled) and monthly caps (listening) with auto-reset

## Problem Statement

- Limited-quantity products on Yodobashi sell out in seconds
- Manual purchasing is impractical; need full automation: check → add cart → checkout
- Multiple products have different sale times; need concurrent monitoring
- Yodobashi uses Akamai WAF + TLS fingerprinting to block bots
- Session management complex; HTTP cookies don't work for checkout (Akamai WAF)

## Solution: Hybrid HTTP + Browser Architecture

### Why Hybrid?

| Task | HTTP (curl_cffi) | Browser (Playwright) |
|------|-------------------|----------------------|
| Check availability | Fast (~1s), lightweight | Slow (~5s), resource-intensive |
| Add to cart | **Not possible** (*) | Works |
| Checkout | **Not possible** (*) | Works |
| Session management | Limited (cookies only) | Full browser context, Akamai WAF compatible |

(*) Yodobashi uses Akamai WAF — session cookies tied to specific browser context. Cannot transfer HTTP session to browser for checkout without losing auth.

### Flow Diagram

```
1. HTTP Polling (curl_cffi)
   ├─ Check product availability every check_interval seconds
   ├─ Fast, lightweight, Chrome TLS fingerprint (bypass Akamai)
   └─ If available → trigger Playwright
       │
       └─→ 2. Playwright Browser Checkout
           ├─ Launch browser instance
           ├─ Add to cart
           ├─ Login (if not logged in)
           ├─ Enter payment info
           ├─ Confirm order (or dry-run stop)
           └─ Result logged to console + file
               ├─ On success → wait for next cycle
               └─ On failure → continue polling (listening) or retry
```

## Scope

### In Scope
- Concurrent multi-product purchasing (up to N products)
- Two modes: scheduled (daily flash) + listening (random restock)
- HTTP polling with Chrome TLS fingerprint (Akamai bypass)
- Browser checkout automation via Playwright
- Dry-run mode (test without purchase)
- Session persistence (cookies saved to JSON)
- Error handling with screenshots & logging
- CLI testing utilities (`--test-login`, `--test-search`, `--test-checkout`)
- YAML configuration management
- Purchase limit enforcement (daily/monthly caps)

### Out of Scope
- GUI or web interface
- Proxy rotation or pool management
- CAPTCHA solving (requires manual intervention)
- Mobile app automation
- Multi-account support (one account per bot instance)
- Payment method variety (credit card only)
- Convenience store payment, Apple Pay, bank transfer
- Advanced anti-bot evasion (e.g., rotating User-Agents, request replay)

## Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Language** | Python 3.x | Core implementation |
| **HTTP Client** | curl_cffi >=0.7.0 | TLS fingerprint impersonation (Akamai bypass) |
| **HTML Parser** | BeautifulSoup4 + lxml | Parse product pages, detect availability |
| **Browser** | Playwright >=1.49.0 (Chromium) | Checkout automation, JavaScript handling |
| **Config Format** | PyYAML 6.0.1 | YAML config parsing |
| **Logging** | loguru 0.7.2 | Structured logging (console + rotating file) |
| **Concurrency** | Threading (built-in) | One daemon thread per product |
| **Scheduling** | Manual (no APScheduler used) | `--run-now` flag, time-based waiting |

## Stakeholders

- **Primary User** — Consumer wanting to buy limited-quantity products on Yodobashi
- **Secondary User** — Bot operator (can monitor logs, adjust config, run tests)
- **Target Platform** — yodobashi.com (Japanese e-commerce site)

## Risks & Mitigations

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Yodobashi HTML structure changes | Medium | Selector fallbacks, log HTML debug output, manual updates |
| Akamai WAF IP block | High | Chrome TLS impersonation via curl_cffi, session persistence, respect rate limits |
| Race condition during checkout | Low | Each product thread independent, no shared checkout state |
| Account ban due to bot detection | Medium | `check_interval` rate limiting, random-like polling, anti-detection flags in Playwright |
| Login failure / CAPTCHA | Medium | Manual intervention required, screenshot on error, dry-run mode for testing |
| Payment failure (declined card) | Low | Handled gracefully, logs error, continues polling |
| Session expiry / cookie loss | Low | Session persistence to JSON; auto-reload on next run |
