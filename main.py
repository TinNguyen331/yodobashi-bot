#!/usr/bin/env python3
"""
Yodobashi Auto Purchase Bot (Fast/Hybrid version)
==================================================

Single product per instance. Run multiple instances with different configs
for multiple products.

Two buy modes:
  scheduled  - Fixed sale time daily. Only checked during time window.
  listening  - Random restock. Checked 24/7.

Usage:
    python main.py                  # Run with config.yaml
    python main.py --config p1.yaml # Run with custom config
    python main.py --run-now        # Skip scheduled wait
    python main.py --test-checkout  # Dry-run
    python main.py --test-search    # Test HTTP search
    python main.py --test-login     # Test login
"""

import sys
import time
import argparse
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from loguru import logger

from bot.utils import load_config, setup_logging, get_project_root
from bot.http_session import HttpSession
from bot.product_handler import ProductHandler
from bot.checkout_handler import CheckoutHandler


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_in_scheduled_window(product: dict) -> bool:
    """Check if current time is within a scheduled product's active window.
    Active from start_time until end of day."""
    start_time_str = product.get('start_time', '09:25')
    h, m = map(int, start_time_str.split(':'))
    now = datetime.now()
    start = now.replace(hour=h, minute=m, second=0, microsecond=0)
    return now >= start


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


# ---------------------------------------------------------------------------
# Sequential orchestrator (replaces parallel threading)
# ---------------------------------------------------------------------------

def run_single_product(config: dict):
    """
    Run single product monitor 24/7.
    Check availability, purchase when ready, clear cart on failure.
    Stops on Ctrl+C or when limits reached.
    """
    product = config.get('product')
    if not product:
        logger.error("No product configured! Add 'product:' to config.yaml")
        return False

    mode = product.get('mode', 'listening')
    url = product.get('url', '').strip()
    name = product.get('name', '').strip()
    check_interval = product.get('check_interval', 60 if mode == 'listening' else 5)
    max_per_day = product.get('max_per_day', 0)
    max_per_month = product.get('max_per_month', 0)

    # Purchase counters
    daily_count, daily_date = 0, None
    monthly_count, monthly_key = 0, None

    display = (name or url)[:60]
    logger.info("=" * 60)
    logger.info(f"Yodobashi Bot — Single Product Mode")
    logger.info(f"  Product: {display}")
    logger.info(f"  Mode: {mode} | Interval: {check_interval}s")
    if mode == 'scheduled':
        logger.info(f"  Start: {product.get('start_time', '09:25')} | Max/day: {max_per_day or 'unlimited'}")
    else:
        logger.info(f"  Max/month: {max_per_month or 'unlimited'}")
    logger.info("=" * 60)

    check_num = 0

    while True:
        try:
            check_num += 1
            now = datetime.now()

            # Reset counters on day/month change
            today = now.date()
            if daily_date != today:
                daily_count = 0
                daily_date = today

            this_month = (now.year, now.month)
            if monthly_key != this_month:
                monthly_count = 0
                monthly_key = this_month

            # Check limits
            if mode == 'scheduled' and max_per_day > 0 and daily_count >= max_per_day:
                logger.info(f"Daily limit reached ({daily_count}/{max_per_day}), waiting for next day...")
                time.sleep(60)
                continue

            if mode == 'listening' and max_per_month > 0 and monthly_count >= max_per_month:
                logger.info(f"Monthly limit reached ({monthly_count}/{max_per_month}), waiting...")
                time.sleep(3600)
                continue

            # Scheduled: skip if not in time window
            if mode == 'scheduled' and not _is_in_scheduled_window(product):
                time.sleep(check_interval)
                continue

            # Check availability via HTTP
            try:
                with HttpSession(config) as http:
                    http.navigate_to_home()
                    handler = ProductHandler(http, config)

                    if not _navigate_to_product(handler, url, name, ""):
                        time.sleep(check_interval)
                        continue

                    soup = handler.reload_product_page()
                    if not soup or not handler.is_product_available(soup):
                        if check_num % 10 == 1:
                            now_str = now.strftime('%H:%M:%S')
                            logger.info(f"[{now_str}] Not available (check #{check_num})")
                        time.sleep(check_interval)
                        continue

            except Exception as e:
                logger.error(f"Check error: {e}")
                time.sleep(check_interval)
                continue

            # Product available! Purchase it
            now_str = datetime.now().strftime('%H:%M:%S')
            logger.success(f"[{now_str}] AVAILABLE! Launching purchase...")

            checkout = CheckoutHandler(config)
            if checkout.purchase(product):
                logger.success("Purchase completed!")
                daily_count += 1
                monthly_count += 1
                logger.info(f"Today: {daily_count}{f'/{max_per_day}' if max_per_day else ''} | "
                            f"Month: {monthly_count}{f'/{max_per_month}' if max_per_month else ''}")
            else:
                logger.error("Purchase failed, clearing cart...")
                checkout.clear_cart()

            time.sleep(check_interval)

        except KeyboardInterrupt:
            logger.info("Shutting down...")
            return True
        except Exception as e:
            logger.error(f"Error: {e}, retrying in 60s...")
            time.sleep(60)


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
    product = config.get('product')
    if not product:
        logger.error("No product configured!")
        return False

    with HttpSession(config) as http:
        http.navigate_to_home()
        handler = ProductHandler(http, config)

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
    """Test full checkout (dry-run)"""
    logger.info("=" * 60)
    logger.info("=== Testing Checkout Flow - Dry Run ===")
    logger.info("=" * 60)

    if 'settings' not in config:
        config['settings'] = {}
    config['settings']['dry_run'] = True

    product = config.get('product')
    if not product:
        logger.error("No product configured!")
        return False

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
        description='Yodobashi Bot — Sequential product purchasing',
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
        # Override to skip scheduled wait
        if config.get('product'):
            config['product']['mode'] = 'listening'
            config['product'].setdefault('check_interval', 5)
        run_single_product(config)
    else:
        run_single_product(config)


if __name__ == '__main__':
    main()
