"""
Checkout module for Yodobashi Bot (Hybrid approach)

Since Yodobashi's cart is session-bound (Akamai cookies), we can't transfer
cart state between HTTP and browser sessions. Instead:
- curl_cffi: Fast product availability polling (no browser needed)
- Playwright: Add-to-cart + full checkout (needs browser for JS)

Playwright runs headless so it's still background-compatible.
"""
import time
from loguru import logger


class CheckoutHandler:
    """
    Handles the full purchase flow in Playwright browser.
    Called after curl_cffi confirms product is available.
    """

    def __init__(self, config: dict):
        self.config = config
        self.settings = config.get('settings', {})
        self.payment = config.get('payment', {})
        self.account = config.get('account', {})

    def purchase(self, product: dict) -> bool:
        """
        Full purchase flow in Playwright: navigate to product, add to cart, checkout.

        Args:
            product: Product dict with 'url', 'name', 'quantity'

        Returns:
            bool: True if purchase completed successfully
        """
        logger.info("=" * 50)
        logger.info("Starting purchase flow (Playwright browser)...")
        logger.info("=" * 50)

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.error("Playwright not installed! Run: pip install playwright && playwright install chromium")
            return False

        dry_run = self.settings.get('dry_run', True)
        product_url = product.get('url', '').strip()
        product_name = product.get('name', '').strip()
        quantity = product.get('quantity', 1)

        success = False

        with sync_playwright() as pw:
            headless = self.settings.get('headless', True)
            browser = pw.chromium.launch(
                headless=headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-infobars',
                    '--no-sandbox',
                ],
            )

            context = browser.new_context(
                viewport={'width': 1280, 'height': 800},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                           'AppleWebKit/537.36 (KHTML, like Gecko) '
                           'Chrome/120.0.0.0 Safari/537.36',
                locale='ja-JP',
                timezone_id='Asia/Tokyo',
            )

            timeout_ms = self.settings.get('timeout', 30) * 1000
            context.set_default_timeout(timeout_ms)
            page = context.new_page()

            try:
                # Step 1: Navigate to product page
                logger.info("Step 1: Navigating to product...")
                if product_url:
                    page.goto(product_url, wait_until='domcontentloaded')
                else:
                    # Search by name
                    page.goto('https://www.yodobashi.com/', wait_until='domcontentloaded')
                    search = page.locator('#js_searchWord, input[name="word"]').first
                    search.fill(product_name)
                    search.press('Enter')
                    page.wait_for_load_state('domcontentloaded')
                    page.locator('a[href*="/product/"]').first.click()
                    page.wait_for_load_state('domcontentloaded')

                # Step 2: Set quantity and add to cart
                logger.info(f"Step 2: Adding to cart (qty: {quantity})...")
                if quantity > 1:
                    try:
                        qty_sel = page.locator('select#qtySel').first
                        if qty_sel.is_visible(timeout=1000):
                            qty_sel.select_option(str(quantity))
                    except:
                        pass

                add_btn = page.locator(
                    'a#js_m_submitRelated, '
                    'li.yBtnPrimary a:has-text("ショッピングカートに入れる")'
                ).first
                add_btn.wait_for(state='visible', timeout=5000)
                add_btn.click(no_wait_after=True)
                page.wait_for_load_state('domcontentloaded')
                logger.success("Added to cart!")

                # Step 3: On recommend/add page, click proceed to checkout
                # This navigates to: shoppingcart/index.html -> login or payment
                logger.info("Step 3: Looking for proceed button...")
                self._screenshot(page, "after_add_to_cart")

                # Try clicking 購入手続きに進む on recommend page
                proceed_clicked = False
                try:
                    proceed = page.locator('a:has-text("購入手続きに進む")').first
                    if proceed.is_visible(timeout=5000):
                        proceed.click(no_wait_after=True)
                        page.wait_for_load_state('domcontentloaded')
                        proceed_clicked = True
                        logger.info("Clicked proceed on recommend page")
                except:
                    pass

                # If no proceed button, try going to cart page
                if not proceed_clicked:
                    # Try the cart page link from recommend page
                    try:
                        cart_link = page.locator('a:has-text("ショッピングカートページへ")').first
                        if cart_link.is_visible(timeout=2000):
                            cart_link.click()
                            page.wait_for_load_state('domcontentloaded')
                    except:
                        pass

                # Step 4-5: Now we should be heading to checkout flow
                current_url = page.url
                logger.info(f"Step 4-5: Current URL: {current_url}")

                # If still on recommend page, go to cart
                if 'recommend.html' in current_url or ('shoppingcart/add' in current_url):
                    try:
                        cart_link = page.locator('a[href*="shoppingcart/index"]').first
                        if cart_link.is_visible(timeout=2000):
                            cart_link.click()
                            page.wait_for_load_state('domcontentloaded')
                            current_url = page.url
                    except:
                        pass

                # If on cart index page, click proceed
                if 'shoppingcart/index' in current_url:
                    logger.info("On cart page, clicking proceed...")
                    if not self._click_proceed(page):
                        logger.error("Could not proceed from cart")
                        self._screenshot(page, "cart_proceed_failed")
                        return False

                # Step 6: Handle login + payment
                success = self._handle_checkout_flow(page, dry_run)

            except Exception as e:
                logger.error(f"Purchase error: {e}")
                self._screenshot(page, "purchase_error")
            finally:
                context.close()
                browser.close()

        return success

    def _handle_checkout_flow(self, page, dry_run: bool) -> bool:
        """Handle login, payment, and confirmation steps"""
        current_url = page.url
        logger.info(f"Step 6: After proceed, URL: {current_url}")

        # Keep clicking proceed until we leave the cart pages
        max_cart_attempts = 3
        for _ in range(max_cart_attempts):
            current_url = page.url
            if 'shoppingcart' in current_url and '/add/' not in current_url:
                logger.info(f"On cart page: {current_url}, clicking proceed...")
                time.sleep(2)
                if not self._click_proceed(page):
                    logger.warning("Could not click proceed, trying to continue...")
                    break
                current_url = page.url
                logger.info(f"After proceed: {current_url}")
            else:
                break

        # Step 6.1: Login if needed
        current_url = page.url
        logger.info(f"Step 6.1: Checking for login... URL: {current_url}")
        if self._is_login_page(page):
            logger.info("Login page detected, logging in...")
            if not self._login_at_checkout(page):
                return False

            # May need to proceed again after login
            current_url = page.url
            if 'shoppingcart' in current_url:
                if not self._click_proceed(page):
                    return False

        # Check for delayed login
        if self._is_login_page(page):
            if not self._login_at_checkout(page):
                return False
            if 'shoppingcart' in page.url:
                if not self._click_proceed(page):
                    return False

        # Step 6.2: Payment
        current_url = page.url
        logger.info(f"Step 6.2: URL: {current_url}")

        if 'payment' in current_url or self._is_payment_page(page):
            logger.info("On payment page...")
            self._enter_payment(page)
            self._click_next(page)

        # Step 7: Confirm
        return self._confirm_order(page, dry_run)

    def _click_proceed(self, page) -> bool:
        """Click proceed/checkout button"""
        try:
            time.sleep(2)  # Wait for JS to render

            btn = page.locator('a:has-text("購入手続きに進む")').first
            if not btn.is_visible(timeout=10000):
                btn = page.locator(
                    'a.yBtnPrimary:has-text("購入手続き"), '
                    '.orderBox a:has-text("購入")'
                ).first

            if btn.is_visible(timeout=5000):
                btn.click(no_wait_after=True)
                page.wait_for_load_state('domcontentloaded')
                logger.success("Clicked proceed")
                return True

            # Fallback
            btn = page.locator('a:has-text("次へ進む")').first
            if btn.is_visible(timeout=3000):
                btn.click(no_wait_after=True)
                page.wait_for_load_state('domcontentloaded')
                return True

            logger.error("No proceed button found")
            self._screenshot(page, "no_proceed_btn")
            return False
        except Exception as e:
            logger.error(f"Click proceed error: {e}")
            return False

    def _is_login_page(self, page) -> bool:
        """Check if on login page"""
        url = page.url
        if any(kw in url.lower() for kw in ['/login/', '/yc/login/']):
            return True
        try:
            # Yodobashi checkout login has 会員ID field + password
            m = page.locator('input[name="memberId"]').first
            if not m.is_visible(timeout=300):
                # Also check for text "ログインして購入する"
                login_text = page.locator('text=ログインして購入する').first
                if login_text.is_visible(timeout=300):
                    return True
                return False
            p = page.locator('input[type="password"]').first
            return p.is_visible(timeout=300)
        except:
            return False

    def _login_at_checkout(self, page) -> bool:
        """Login during checkout. Handles the ご注文手続き login page."""
        username = self.account.get('username', '')
        password = self.account.get('password', '')
        if not username or not password:
            logger.error("No credentials!")
            return False

        try:
            self._screenshot(page, "before_login")

            # Select "ログインして購入する" radio if present
            try:
                radio = page.locator('input[type="radio"][value*="login"]').first
                if radio.is_visible(timeout=300):
                    radio.click()
            except:
                pass

            # Fill username (会員ID) - try multiple selectors
            username_field = page.locator('input[name="memberId"]').first
            if not username_field.is_visible(timeout=500):
                username_field = page.locator('input[type="email"], input[type="text"]').first
            username_field.fill(username)

            # Fill password
            page.locator('input[type="password"]').first.fill(password)

            # Click proceed button
            btn = page.locator('a:has-text("購入手続きへ進む")').first
            if not btn.is_visible(timeout=500):
                btn = page.locator(
                    'a:has-text("ログイン"), button:has-text("ログイン"), #js_i_login0, .btnRed'
                ).first

            logger.info("Clicking login button...")
            btn.click(no_wait_after=True)

            # Wait for redirect away from login page
            old_url = page.url
            for _ in range(75):
                time.sleep(0.2)
                new_url = page.url
                if new_url != old_url and '/login/' not in new_url.lower():
                    try:
                        page.wait_for_load_state('domcontentloaded', timeout=5000)
                    except:
                        pass
                    logger.success("Login successful!")
                    return True

                # Also check if page content changed (login form disappeared)
                try:
                    if not page.locator('text=ログインして購入する').first.is_visible(timeout=100):
                        page.wait_for_load_state('domcontentloaded', timeout=5000)
                        logger.success("Login successful!")
                        return True
                except:
                    pass

            logger.error("Login timeout")
            self._screenshot(page, "login_timeout")
            return False
        except Exception as e:
            logger.error(f"Login error: {e}")
            self._screenshot(page, "login_error")
            return False

    def _is_payment_page(self, page) -> bool:
        """Check if on payment page"""
        if '/order/payment/' in page.url:
            return True
        try:
            for txt in ['お支払い方法', '新しいクレジットカード']:
                if page.locator(f'text={txt}').first.is_visible(timeout=500):
                    return True
        except:
            pass
        return False

    def _enter_payment(self, page):
        """Fill payment info"""
        try:
            # Select new credit card
            try:
                nc = page.locator('.entrySelector.js_c_paymentSelect.js_c_newcard').first
                if nc.is_visible(timeout=500):
                    nc.click()
                else:
                    nc = page.locator('label:has-text("新しいクレジットカード")').first
                    if nc.is_visible(timeout=500):
                        nc.click()
            except:
                pass

            card = self.payment.get('card_number', '')
            if card:
                inp = page.locator('input[name*="cardNumber"], input[name*="cardNo"]').first
                if inp.is_visible(timeout=1000):
                    inp.fill(card)

            month = self.payment.get('expiry_month', '')
            year = self.payment.get('expiry_year', '')
            if month and year:
                try:
                    sels = page.locator('select').all()
                    if len(sels) >= 2:
                        for v in [month, str(int(month)), month.zfill(2)]:
                            try:
                                sels[0].select_option(value=v, timeout=300)
                                break
                            except:
                                try:
                                    sels[0].select_option(label=v, timeout=300)
                                    break
                                except:
                                    continue
                        sy = year[-2:] if len(year) == 4 else year
                        for v in [year, sy, f"20{sy}"]:
                            try:
                                sels[1].select_option(value=v, timeout=300)
                                break
                            except:
                                try:
                                    sels[1].select_option(label=v, timeout=300)
                                    break
                                except:
                                    continue
                except:
                    pass

            logger.info("Payment info entered")
        except Exception as e:
            logger.error(f"Payment error: {e}")

    def _click_next(self, page):
        """Click next button"""
        try:
            btn = page.locator(
                'a:has-text("次へ進む"), button:has-text("次へ進む"), .yBtnPrimary a'
            ).first
            if btn.is_visible(timeout=3000):
                btn.click(no_wait_after=True)
                page.wait_for_load_state('domcontentloaded')
        except:
            pass

    def _confirm_order(self, page, dry_run: bool) -> bool:
        """Confirm order (Step 7)"""
        logger.info("Step 7: Confirm order page...")

        cvv = self.payment.get('cvv', '')
        if cvv:
            try:
                inp = page.locator('input.uiInput.fs11.js_c_securityCode').first
                if inp.is_visible(timeout=500):
                    inp.fill(cvv)
                else:
                    inp = page.locator('input[maxlength="3"], input[maxlength="4"]').first
                    if inp.is_visible(timeout=300):
                        inp.fill(cvv)
                logger.info("Filled CVV")
            except:
                pass

        if dry_run:
            logger.warning("=== DRY RUN MODE - Order NOT placed ===")
            self._screenshot(page, "dry_run_confirm")
            return True

        if self.settings.get('require_confirmation', False):
            ui = input("Type 'yes' to confirm: ")
            if ui.lower().strip() != 'yes':
                logger.info("Cancelled by user")
                return False

        try:
            btn = page.locator(
                'a:has-text("注文を確定する"), button:has-text("注文を確定する")'
            ).first
            if btn.is_visible(timeout=2000):
                btn.click()
                page.wait_for_load_state('domcontentloaded')
                if 'complete' in page.url.lower():
                    logger.success("Order completed!")
                    return True
                return True

            logger.error("No confirm button")
            return False
        except Exception as e:
            logger.error(f"Confirm error: {e}")
            return False

    def clear_cart(self) -> bool:
        """
        Navigate to cart page and remove all items.
        Called after purchase failure to prevent cart conflicts with next product.
        Returns True if cart is empty after cleanup.
        """
        logger.info("Clearing shopping cart...")

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.error("Playwright not installed!")
            return False

        try:
            with sync_playwright() as pw:
                headless = self.settings.get('headless', True)
                browser = pw.chromium.launch(
                    headless=headless,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--disable-infobars',
                        '--no-sandbox',
                    ],
                )
                context = browser.new_context(
                    viewport={'width': 1280, 'height': 800},
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                               'AppleWebKit/537.36 (KHTML, like Gecko) '
                               'Chrome/120.0.0.0 Safari/537.36',
                    locale='ja-JP',
                    timezone_id='Asia/Tokyo',
                )
                timeout_ms = self.settings.get('timeout', 30) * 1000
                context.set_default_timeout(timeout_ms)
                page = context.new_page()

                try:
                    page.goto('https://order.yodobashi.com/shoppingcart/index.html',
                              wait_until='domcontentloaded')

                    # Handle login redirect if needed
                    if self._is_login_page(page):
                        logger.info("Login required to access cart, logging in...")
                        if not self._login_at_checkout(page):
                            logger.error("Cannot login to clear cart")
                            return False
                        page.goto('https://order.yodobashi.com/shoppingcart/index.html',
                                  wait_until='domcontentloaded')

                    # Check if cart is already empty
                    empty_texts = ['ショッピングカートに商品はありません',
                                   'カートに商品がありません',
                                   '商品が入っていません']
                    for txt in empty_texts:
                        try:
                            if page.locator(f'text={txt}').first.is_visible(timeout=1000):
                                logger.info("Cart is already empty")
                                return True
                        except:
                            pass

                    # Remove items: click delete buttons until cart is empty
                    max_attempts = 20  # safety limit
                    for attempt in range(max_attempts):
                        # Look for delete button (削除)
                        delete_btn = None
                        for selector in [
                            'a:has-text("削除")',
                            'button:has-text("削除")',
                            'a.delete',
                            '.deleteBtn a',
                            'a[href*="delete"]',
                        ]:
                            try:
                                btn = page.locator(selector).first
                                if btn.is_visible(timeout=1000):
                                    delete_btn = btn
                                    break
                            except:
                                continue

                        if not delete_btn:
                            # No more delete buttons — cart should be empty
                            logger.info("No more items to delete")
                            break

                        logger.info(f"Removing cart item (attempt {attempt + 1})...")
                        delete_btn.click()
                        time.sleep(1)

                        # Handle confirmation dialog if any
                        try:
                            confirm = page.locator('a:has-text("はい"), button:has-text("はい"), '
                                                   'a:has-text("OK"), button:has-text("OK")').first
                            if confirm.is_visible(timeout=2000):
                                confirm.click()
                        except:
                            pass

                        page.wait_for_load_state('domcontentloaded')

                    logger.success("Cart cleared")
                    return True

                except Exception as e:
                    logger.error(f"Cart cleanup error: {e}")
                    self._screenshot(page, "cart_cleanup_error")
                    return False
                finally:
                    context.close()
                    browser.close()

        except Exception as e:
            logger.error(f"Cart cleanup failed: {e}")
            return False

    def _screenshot(self, page, name: str):
        """Save screenshot for debugging"""
        if not self.settings.get('screenshot_on_error', True):
            return
        try:
            from .utils import get_project_root
            from datetime import datetime
            log_dir = get_project_root() / "logs"
            log_dir.mkdir(exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            page.screenshot(path=str(log_dir / f"{name}_{ts}.png"))
        except:
            pass
