#!/usr/bin/env python3
"""
Yodobashi Auto Purchase Bot (Fast/Hybrid version)
==================================================

Processes products sequentially (one at a time) to avoid cart conflicts.
Round-robin checks all products, purchases first available, clears cart on failure.

Two buy modes per product:
  scheduled  - Fixed sale time daily. Only checked during time window.
  listening  - Random restock. Checked every round, 24/7.

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

def run_sequential(config: dict):
    """
    Run all products sequentially in a single loop, 24/7.
    Round-robin checks each product, purchases first available,
    clears cart on failure, then restarts from product #1.

    Only one product is purchased at a time to avoid cart conflicts.
    """
    products = config.get('products', [])
    if not products:
        logger.error("No products configured!")
        return False

    # Per-product purchase counters
    counters = {}
    for i in range(len(products)):
        counters[i] = {
            'daily_count': 0, 'daily_date': None,
            'monthly_count': 0, 'monthly_key': None,
        }

    # Use smallest check_interval across all products as the round delay
    default_interval = min(
        p.get('check_interval', 60 if p.get('mode', 'scheduled') == 'listening' else 5)
        for p in products
    )

    logger.info("=" * 60)
    logger.info(f"Starting Yodobashi Bot 24/7 — {len(products)} product(s) [SEQUENTIAL]")
    logger.info("=" * 60)
    for i, p in enumerate(products):
        mode = p.get('mode', 'scheduled')
        display = (p.get('name', '') or p.get('url', ''))[:50]
        logger.info(f"  [P{i+1}] {display} ({mode})")
    logger.info(f"  Round interval: {default_interval}s")
    logger.info("=" * 60)

    round_num = 0

    # --- 24/7 outer loop: never exits ---
    while True:
        try:
            round_num += 1
            now = datetime.now()
            purchased_this_round = False

            for i, product in enumerate(products):
                tag = f"[P{i+1}]"
                mode = product.get('mode', 'scheduled')
                url = product.get('url', '').strip()
                name = product.get('name', '').strip()
                max_per_day = product.get('max_per_day', 0)
                max_per_month = product.get('max_per_month', 0)
                c = counters[i]

                # --- Reset counters on day/month change ---
                today = now.date()
                if c['daily_date'] != today:
                    c['daily_count'] = 0
                    c['daily_date'] = today

                this_month = (now.year, now.month)
                if c['monthly_key'] != this_month:
                    c['monthly_count'] = 0
                    c['monthly_key'] = this_month

                # --- Skip if daily limit reached (scheduled) ---
                if mode == 'scheduled' and max_per_day > 0 and c['daily_count'] >= max_per_day:
                    continue

                # --- Skip if monthly limit reached (listening) ---
                if mode == 'listening' and max_per_month > 0 and c['monthly_count'] >= max_per_month:
                    continue

                # --- Scheduled: skip if not in time window ---
                if mode == 'scheduled' and not _is_in_scheduled_window(product):
                    continue

                # --- Check availability via HTTP (fast) ---
                try:
                    with HttpSession(config) as http:
                        http.navigate_to_home()
                        handler = ProductHandler(http, config)

                        if not _navigate_to_product(handler, url, name, tag):
                            continue

                        soup = handler.reload_product_page()
                        if not soup or not handler.is_product_available(soup):
                            if round_num % 10 == 1:
                                now_str = datetime.now().strftime('%H:%M:%S')
                                logger.info(f"{tag} [{now_str}] Not available")
                            continue

                except Exception as e:
                    logger.error(f"{tag} Check error: {e}")
                    continue

                # --- Product is available! Purchase it ---
                now_str = datetime.now().strftime('%H:%M:%S')
                logger.success(f"{tag} [{now_str}] AVAILABLE! Launching purchase...")

                checkout = CheckoutHandler(config)
                if checkout.purchase(product):
                    logger.success(f"{tag} Purchase completed!")
                    c['daily_count'] += 1
                    c['monthly_count'] += 1
                    logger.info(f"{tag} Today: {c['daily_count']}"
                                f"{f'/{max_per_day}' if max_per_day else ''} | "
                                f"Month: {c['monthly_count']}"
                                f"{f'/{max_per_month}' if max_per_month else ''}")
                else:
                    logger.error(f"{tag} Purchase failed, clearing cart...")
                    checkout.clear_cart()

                purchased_this_round = True
                break  # Restart round-robin from product #1

            # Sleep between rounds
            time.sleep(default_interval)

        except KeyboardInterrupt:
            logger.info("Shutting down...")
            return True
        except Exception as e:
            logger.error(f"Round error: {e}, restarting in 60s...")
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
        # Override all products to skip scheduled wait
        for p in config.get('products', []):
            p['mode'] = 'listening'
            p.setdefault('check_interval', 5)
        run_sequential(config)  # Runs forever
    else:
        # Default: run all products 24/7
        run_sequential(config)  # Runs forever


if __name__ == '__main__':
    main()
