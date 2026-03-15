#!/usr/bin/env python3
"""
Yodobashi Auto Purchase Bot (Fast/Hybrid version)
==================================================

Supports multiple products running concurrently, each in its own thread.

Two buy modes per product:
  scheduled  - Fixed sale time daily. Waits until start_time, then polls fast.
  listening  - Random restock. Polls continuously every check_interval seconds.

Usage:
    python main.py                  # Run all products (default)
    python main.py --run-now        # Skip wait, check all immediately
    python main.py --test-checkout  # Dry-run first product
    python main.py --test-search    # Test HTTP search
    python main.py --test-login     # Test login
"""

import sys
import time
import argparse
import threading
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from loguru import logger

from bot.utils import load_config, setup_logging, get_project_root
from bot.http_session import HttpSession
from bot.product_handler import ProductHandler
from bot.checkout_handler import CheckoutHandler


# ---------------------------------------------------------------------------
# Per-product watcher (runs in its own thread)
# ---------------------------------------------------------------------------

def _wait_until_start_time(start_time_str: str, tag: str):
    """
    Wait until the next occurrence of start_time (today or tomorrow).
    """
    h, m = map(int, start_time_str.split(':'))
    now = datetime.now()
    target = now.replace(hour=h, minute=m, second=0, microsecond=0)

    if now >= target:
        target += timedelta(days=1)

    wait_secs = (target - now).total_seconds()
    logger.info(f"{tag} Waiting {wait_secs:.0f}s until {target.strftime('%Y-%m-%d %H:%M')}...")
    time.sleep(wait_secs)


def _wait_until_next_month(tag: str):
    """Wait until the 1st of next month 00:00."""
    now = datetime.now()
    if now.month == 12:
        next_month = now.replace(year=now.year + 1, month=1, day=1,
                                 hour=0, minute=0, second=0, microsecond=0)
    else:
        next_month = now.replace(month=now.month + 1, day=1,
                                 hour=0, minute=0, second=0, microsecond=0)
    wait_secs = (next_month - now).total_seconds()
    logger.info(f"{tag} Waiting {wait_secs:.0f}s until {next_month.strftime('%Y-%m-%d')} (next month)...")
    time.sleep(wait_secs)


def _navigate_to_product(handler, url: str, name: str, tag: str):
    """Navigate to product page by URL or name search. Returns success bool."""
    if url:
        ok, _ = handler.navigate_to_product(url)
    elif name:
        ok, found_url = handler.search_product(name)
        if ok and found_url:
            ok, _ = handler.navigate_to_product(found_url)
        else:
            ok = False
    else:
        ok = False

    if not ok:
        logger.error(f"{tag} Failed to navigate to product")
    return ok


def watch_product(product: dict, config: dict, product_index: int):
    """
    Watch a single product and purchase when available.
    Runs 24/7 in its own thread, never stops.

    scheduled: Each day waits until start_time, polls until purchase or
               daily limit reached, then waits for next day.
    listening: Polls continuously. Pauses when monthly limit reached.

    Purchase limits:
      max_per_day   - max purchases per day (scheduled), 0 = unlimited
      max_per_month - max purchases per month (listening), 0 = unlimited
    """
    mode = product.get('mode', 'scheduled')
    url = product.get('url', '').strip()
    name = product.get('name', '').strip()
    check_interval = product.get('check_interval', 60 if mode == 'listening' else 5)
    display = name[:40] if name else url[:40]
    tag = f"[P{product_index}]"

    start_time_str = product.get('start_time', '09:25') if mode == 'scheduled' else None
    max_per_day = product.get('max_per_day', 0)
    max_per_month = product.get('max_per_month', 0)

    # Purchase tracking
    daily_count = 0
    daily_date = None
    monthly_count = 0
    monthly_key = None  # (year, month)

    logger.info(f"{tag} Starting 24/7 watcher: {display}")
    logger.info(f"{tag} Mode: {mode} | Interval: {check_interval}s")
    if mode == 'scheduled':
        logger.info(f"{tag} Start: {start_time_str} | Max/day: {max_per_day or 'unlimited'}")
    if mode == 'listening':
        logger.info(f"{tag} Max/month: {max_per_month or 'unlimited'}")

    # --- 24/7 outer loop: never exits ---
    while True:
        try:
            now = datetime.now()

            # --- Reset counters on day/month change ---
            today = now.date()
            if daily_date != today:
                daily_count = 0
                daily_date = today

            this_month = (now.year, now.month)
            if monthly_key != this_month:
                monthly_count = 0
                monthly_key = this_month

            # --- Check daily limit (scheduled) ---
            if mode == 'scheduled' and max_per_day > 0 and daily_count >= max_per_day:
                logger.info(f"{tag} Daily limit reached ({daily_count}/{max_per_day}), "
                            f"waiting for next day...")
                _wait_until_start_time(start_time_str, tag)
                continue

            # --- Check monthly limit (listening) ---
            if mode == 'listening' and max_per_month > 0 and monthly_count >= max_per_month:
                logger.info(f"{tag} Monthly limit reached ({monthly_count}/{max_per_month}), "
                            f"pausing until next month...")
                _wait_until_next_month(tag)
                continue

            # --- Scheduled: wait until today's/tomorrow's start_time ---
            if mode == 'scheduled':
                _wait_until_start_time(start_time_str, tag)
                logger.info(f"{tag} Start time reached, beginning polling...")

            # Create fresh HTTP session for each cycle
            with HttpSession(config) as http:
                http.navigate_to_home()
                handler = ProductHandler(http, config)

                if not _navigate_to_product(handler, url, name, tag):
                    logger.warning(f"{tag} Retrying navigation in 60s...")
                    time.sleep(60)
                    continue

                # Polling loop
                attempt = 0
                while True:
                    attempt += 1
                    now_str = datetime.now().strftime('%H:%M:%S')

                    try:
                        soup = handler.reload_product_page()
                        if soup and handler.is_product_available(soup):
                            logger.success(f"{tag} [{now_str}] AVAILABLE! Launching purchase...")

                            checkout = CheckoutHandler(config)
                            if checkout.purchase(product):
                                logger.success(f"{tag} Purchase completed!")
                                daily_count += 1
                                monthly_count += 1
                                logger.info(f"{tag} Today: {daily_count}"
                                            f"{f'/{max_per_day}' if max_per_day else ''} | "
                                            f"Month: {monthly_count}"
                                            f"{f'/{max_per_month}' if max_per_month else ''}")
                            else:
                                logger.error(f"{tag} Purchase failed, will retry...")

                            # Scheduled: done for today, wait for next day
                            if mode == 'scheduled':
                                break

                            # Listening: check monthly limit before continuing
                            if max_per_month > 0 and monthly_count >= max_per_month:
                                logger.info(f"{tag} Monthly limit reached, pausing...")
                                break  # Outer loop will handle wait
                        else:
                            if attempt % 10 == 1:
                                logger.info(f"{tag} [{now_str}] Attempt {attempt}: Not available")

                    except Exception as e:
                        logger.error(f"{tag} Check error: {e}")

                    time.sleep(check_interval)

        except Exception as e:
            logger.error(f"{tag} Watcher error: {e}, restarting in 60s...")
            time.sleep(60)


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def run_all_products(config: dict):
    """
    Run all configured products concurrently, 24/7.
    Each product gets its own thread that runs forever.
    """
    products = config.get('products', [])
    if not products:
        logger.error("No products configured!")
        return False

    logger.info("=" * 60)
    logger.info(f"Starting Yodobashi Bot 24/7 — {len(products)} product(s)")
    logger.info("=" * 60)

    if len(products) == 1:
        # Single product: run in main thread
        watch_product(products[0], config, 1)
        return True  # Never reached (watch_product runs forever)

    # Multiple products: run each in its own thread
    for i, product in enumerate(products, 1):
        t = threading.Thread(
            target=watch_product,
            args=(product, config, i),
            name=f"product-{i}",
            daemon=True,
        )
        t.start()
        logger.info(f"Launched thread for product {i}")

    # Main thread stays alive forever (daemon threads die if main exits)
    logger.info("All product watchers running. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(3600)  # Sleep 1 hour, repeat forever
    except KeyboardInterrupt:
        logger.info("Shutting down...")

    return True


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def test_login(config: dict):
    """Test login via Playwright"""
    logger.info("=== Testing Login ===")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error("Playwright not installed!")
        return False

    account = config.get('account', {})
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        context = browser.new_context(locale='ja-JP', timezone_id='Asia/Tokyo')
        page = context.new_page()

        page.goto('https://www.yodobashi.com/', wait_until='domcontentloaded')
        page.locator('a:has-text("ログイン")').first.click()
        page.wait_for_load_state('domcontentloaded')
        page.locator('input[name="memberId"]').first.fill(account.get('username', ''))
        page.locator('input[name="password"]').first.fill(account.get('password', ''))
        page.locator('#js_i_login0').first.click()

        for _ in range(50):
            time.sleep(0.2)
            if page.locator('a:has-text("ログアウト")').count() > 0:
                logger.success("Login test PASSED!")
                context.close()
                browser.close()
                return True

        logger.error("Login test FAILED!")
        context.close()
        browser.close()
        return False


def test_search(config: dict):
    """Test product search via HTTP"""
    logger.info("=== Testing Product Search (HTTP) ===")
    products = config.get('products', [])
    if not products:
        logger.error("No products to test!")
        return False

    with HttpSession(config) as http:
        http.navigate_to_home()
        handler = ProductHandler(http, config)
        product = products[0]

        url = product.get('url', '').strip()
        name = product.get('name', '').strip()

        if url:
            ok, soup = handler.navigate_to_product(url)
        elif name:
            ok, found_url = handler.search_product(name)
            if ok and found_url:
                ok, soup = handler.navigate_to_product(found_url)

        if ok:
            available = handler.is_product_available()
            logger.info(f"Product available: {available}")
            logger.success("Search test PASSED!")
            return True

    logger.error("Search test FAILED!")
    return False


def test_checkout(config: dict):
    """Test full checkout (dry-run) on first product"""
    logger.info("=" * 60)
    logger.info("=== Testing Checkout Flow - Dry Run ===")
    logger.info("=" * 60)

    if 'settings' not in config:
        config['settings'] = {}
    config['settings']['dry_run'] = True

    products = config.get('products', [])
    if not products:
        logger.error("No products!")
        return False

    # Check availability then purchase (dry-run)
    product = products[0]
    with HttpSession(config) as http:
        http.navigate_to_home()
        handler = ProductHandler(http, config)
        url = product.get('url', '').strip()
        if url:
            ok, soup = handler.navigate_to_product(url)
        else:
            ok = False

        if not ok or not handler.is_product_available():
            logger.error("Product not available for test")
            return False

    checkout = CheckoutHandler(config)
    return checkout.purchase(product)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description='Yodobashi Bot — Multi-product concurrent purchasing',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument('--run-now', action='store_true',
                        help='Skip scheduled wait, check all products immediately')
    parser.add_argument('--test-login', action='store_true', help='Test login')
    parser.add_argument('--test-search', action='store_true', help='Test product search')
    parser.add_argument('--test-checkout', action='store_true', help='Test checkout (dry-run)')
    parser.add_argument('--config', type=str, default='config.yaml', help='Config file path')

    args = parser.parse_args()
    setup_logging()

    try:
        config_path = Path(args.config)
        if not config_path.is_absolute():
            config_path = get_project_root() / args.config
        config = load_config(str(config_path))
        logger.info(f"Config loaded from {config_path}")
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        sys.exit(1)

    if args.test_login:
        success = test_login(config)
        sys.exit(0 if success else 1)
    elif args.test_search:
        success = test_search(config)
        sys.exit(0 if success else 1)
    elif args.test_checkout:
        success = test_checkout(config)
        sys.exit(0 if success else 1)
    elif args.run_now:
        # Override all products to skip scheduled wait
        for p in config.get('products', []):
            p['mode'] = 'listening'
            p.setdefault('check_interval', 5)
        run_all_products(config)  # Runs forever
    else:
        # Default: run all products 24/7
        run_all_products(config)  # Runs forever


if __name__ == '__main__':
    main()
