# Deployment Guide

## System Requirements

- **Python** 3.8 or higher
- **Chromium browser** (installed via Playwright)
- **RAM** — ~200MB (HTTP polling) + ~300MB per Playwright instance
- **Disk** — ~100MB for venv + dependencies, ~50MB for logs + session
- **Network** — Stable connection to yodobashi.com, no VPN needed (but OK to use)
- **OS** — Windows, macOS, or Linux (supports all platforms)

## Installation

### 1. Clone repository

```bash
git clone <repo_url>
cd yodobashi-bot
```

### 2. Create virtual environment

```bash
python -m venv venv

# Activate
# Windows:
venv\Scripts\activate
# macOS / Linux:
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Install Playwright browser

```bash
playwright install chromium
```

### 5. Create configuration

```bash
cp config.example.yaml config.yaml
```

Edit `config.yaml` with your real data:
- `account.username` — Yodobashi email/ID
- `account.password` — Yodobashi password
- `products[]` — List of products to monitor
- `payment` — Credit card details
- `shipping` — Delivery address
- `settings` — Bot preferences (dry_run, headless, timeouts, etc.)

**⚠️ Security:** `config.yaml` is gitignored; never commit it. Contains credentials.

### 6. Test before running

```bash
# Test login (opens browser, manual confirmation)
python main.py --test-login

# Test HTTP product search (prints first result)
python main.py --test-search

# Test full checkout (dry-run, does NOT purchase)
python main.py --test-checkout
```

All tests log to console and `logs/bot_YYYYMMDD.log`.

## Running the Bot

### Normal operation (respect config)

```bash
python main.py
```

Bot runs 24/7, never stops on its own. Press **Ctrl+C** to shutdown.

**Behavior per mode:**
- **scheduled** — Waits until `start_time` each day → polls → purchases → waits for next day
- **listening** — Polls continuously every `check_interval` → purchases → continues polling
- **Limit reached** — Auto-pauses until reset (daily at midnight for scheduled, monthly on 1st for listening)

### Run now (skip time wait)

```bash
python main.py --run-now
```

Overrides all `scheduled` products to `listening` mode; starts polling immediately (no wait for `start_time`).

### Run in background (Linux/macOS)

```bash
nohup python main.py > bot.log 2>&1 &
# Or with output to loguru's rotating log:
nohup python main.py > /dev/null 2>&1 &
```

Bot logs to `logs/bot_YYYYMMDD.log` automatically.

### Run in background (Windows)

```bash
start /B python main.py
```

Or use Task Scheduler to run at startup:
1. Open Task Scheduler
2. Create Basic Task
3. Trigger: At startup
4. Action: Start program `python.exe` with arguments `main.py` in project directory

## Configuration Details

### Scheduled Mode (Daily Flash Sale)

```yaml
- name: "FUJIFILM Instax Film"
  url: "https://www.yodobashi.com/product/100000001006011748"
  quantity: 5
  mode: "scheduled"
  start_time: "09:25"     # Start polling 5 min before sale time
  sale_time: "09:30"      # Official sale time (info only)
  check_interval: 5       # Poll every 5 seconds
  max_per_day: 5          # Max 5 purchases per day (0 = unlimited)
```

**Notes:**
- `start_time` should be 3-5 minutes before `sale_time`
- `check_interval: 5-10` seconds recommended for scheduled mode
- Bot repeats daily; waits for next day's `start_time` after purchase
- `max_per_day` counter resets at midnight automatically

### Listening Mode (Random Restock)

```yaml
- name: "Nintendo Switch"
  url: "https://www.yodobashi.com/product/YYYYYYYYYY"
  quantity: 1
  mode: "listening"
  check_interval: 60      # Poll every 60 seconds
  max_per_month: 1        # Max 1 purchase per month (0 = unlimited)
```

**Notes:**
- `check_interval: 60` seconds recommended to avoid rate limiting
- Bot runs 24/7; continues polling after purchase success/failure
- `max_per_month` counter resets on 1st of next month automatically
- Can reduce to `check_interval: 30` for faster response (higher risk of block)

## Troubleshooting

### Bot blocked / timeout errors

**Symptoms:** Repeated 403/429 errors, connection timeouts

**Solutions:**
- Increase `check_interval` (fewer requests per minute)
- Delete `session/cookies.json` to reset session
- Check `logs/bot_YYYYMMDD.log` for details
- Check if IP is flagged by Akamai; wait 24 hours or use different network

### Login fails

**Symptoms:** "Login failed" in logs, "ログイン" link still visible

**Solutions:**
- Verify `account.username` and `account.password` in config
- Run `python main.py --test-login` to see browser and debug manually
- Check if Yodobashi requires CAPTCHA (requires manual intervention)
- Ensure account is not locked or 2FA enabled

### Product available but checkout fails

**Symptoms:** Availability detected but purchase doesn't complete

**Solutions:**
- Check screenshots: `logs/*.png` (saved on error)
- Check HTML debug: `logs/*.html` (page snapshots)
- Run `python main.py --test-checkout` with `headless: false` (see browser)
- Yodobashi may have changed HTML structure; update selectors in code or report issue
- Check if payment card is valid / not declined

### Playwright errors (browser crashes)

**Symptoms:** "Playwright crashed", "Page closed"

**Solutions:**
- Reinstall Chromium: `playwright install chromium`
- Update Playwright: `pip install --upgrade playwright`
- Check available disk space (Chromium needs ~300MB)
- Check system RAM (may OOM if multiple products checkout simultaneously)

### Session expires / cookies lost

**Symptoms:** Requires re-login every run, "認証が必要" (authentication required)

**Solutions:**
- Check `session/cookies.json` exists and is not empty
- Delete `session/cookies.json` to force fresh login
- Ensure bot runs regularly so session doesn't expire

## Monitoring

### View logs in real-time

```bash
# Linux/macOS:
tail -f logs/bot_YYYYMMDD.log

# Windows (PowerShell):
Get-Content logs/bot_YYYYMMDD.log -Wait
```

### Check for errors

```bash
grep ERROR logs/bot_YYYYMMDD.log
grep -A5 "purchase failed" logs/bot_YYYYMMDD.log
```

### Screenshots & debug files

```bash
ls -lah logs/*.png      # Error screenshots
ls -lah logs/*.html     # Debug HTML pages
```

## Security Best Practices

- **Never commit** `config.yaml` (contains credentials)
- **Never share** `session/cookies.json` (session tokens)
- `config.yaml` is already in `.gitignore`
- **Encrypt config** if running on shared server (consider using environment variables or secrets manager)
- **Rotate credentials** periodically (change Yodobashi password)
- **Monitor account** for suspicious activity (check Yodobashi order history)
- **Use strong password** on Yodobashi account
