"""
Product search and cart module for Yodobashi Bot (HTTP version)
Handles product navigation, availability check, and add-to-cart via HTTP
"""
import re
from typing import Optional, Tuple

from bs4 import BeautifulSoup
from loguru import logger


class ProductHandler:
    """
    Handles product search and cart operations via HTTP requests
    """

    SEARCH_URL = "https://www.yodobashi.com/category/81001/"

    def __init__(self, http_session, config: dict):
        self.http = http_session
        self.config = config
        self.settings = config.get('settings', {})
        # Store last fetched product page for reuse
        self._last_product_soup = None
        self._last_product_url = None

    def navigate_to_product(self, url: str) -> Tuple[bool, Optional[BeautifulSoup]]:
        """
        Navigate directly to product page by URL

        Returns:
            Tuple of (success, BeautifulSoup of product page)
        """
        logger.info(f"Navigating to product URL: {url[:80]}...")
        try:
            soup = self.http.get_soup(url)
            self._last_product_soup = soup
            self._last_product_url = url
            return True, soup
        except Exception as e:
            logger.error(f"Navigation failed: {e}")
            return False, None

    def search_product(self, product_name: str) -> Tuple[bool, Optional[str]]:
        """
        Search for a product by name and return first result URL

        Returns:
            Tuple of (success, product_url or None)
        """
        logger.info(f"Searching for product: {product_name[:50]}...")
        try:
            resp = self.http.get(
                self.http.BASE_URL,
                params={'word': product_name}
            )
            soup = BeautifulSoup(resp.text, 'lxml')

            # Find first product link in search results
            product_link = soup.find('a', href=re.compile(r'/product/\d+'))
            if product_link:
                href = product_link.get('href', '')
                if not href.startswith('http'):
                    href = f"{self.http.BASE_URL}{href}"
                logger.info(f"Found product: {href[:80]}")
                return True, href

            logger.error("No products found in search results")
            return False, None

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return False, None

    def is_product_available(self, soup: Optional[BeautifulSoup] = None) -> bool:
        """
        Check if product page shows item as available.

        Product is available if there's a <div class="quantityInfo numIpt">
        inside <div id="js_buyBoxMain">

        Returns:
            bool: True if product is available for purchase
        """
        if soup is None:
            soup = self._last_product_soup
        if soup is None:
            logger.error("No product page to check")
            return False

        try:
            # Primary check: Look for buyBoxMain with quantityInfo
            buy_box = soup.find('div', id='js_buyBoxMain')
            if buy_box:
                quantity_div = buy_box.find('div', class_=re.compile(r'quantityInfo.*numIpt'))
                if quantity_div:
                    logger.info("Product is available (found quantity selector in buyBoxMain)")
                    return True

            # Fallback: Check for add to cart button
            if buy_box:
                add_btn = buy_box.find('a', id='js_m_submitRelated')
                if add_btn:
                    logger.info("Product is available (found add to cart button)")
                    return True

            # Check for out of stock text
            page_text = soup.get_text()
            out_of_stock_texts = ['在庫なし', '売り切れ', '販売終了']
            for text in out_of_stock_texts:
                if text in page_text:
                    logger.info(f"Product is out of stock (found: {text})")
                    return False

            logger.warning("Could not determine availability - assuming out of stock")
            return False

        except Exception as e:
            logger.error(f"Availability check error: {e}")
            return False

    def reload_product_page(self) -> Optional[BeautifulSoup]:
        """Reload the last product page (for availability polling)"""
        if not self._last_product_url:
            return None
        try:
            soup = self.http.get_soup(self._last_product_url)
            self._last_product_soup = soup
            return soup
        except Exception as e:
            logger.error(f"Failed to reload product page: {e}")
            return None

    def add_to_cart(self, quantity: int = 1,
                    soup: Optional[BeautifulSoup] = None) -> Tuple[bool, Optional[str]]:
        """
        Add product to cart via HTTP POST.
        Extracts the add-to-cart form/URL from the product page and submits it.

        Returns:
            Tuple of (success, redirect_url after adding)
        """
        if soup is None:
            soup = self._last_product_soup
        if soup is None:
            logger.error("No product page loaded")
            return False, None

        logger.info(f"Adding product to cart (quantity: {quantity})...")

        try:
            # Find the add-to-cart form or link
            # Yodobashi uses a form or JS-triggered POST for cart addition
            add_btn = soup.find('a', id='js_m_submitRelated')
            if not add_btn:
                add_btn = soup.find('a', string=re.compile(r'ショッピングカートに入れる'))

            if not add_btn:
                logger.error("Could not find add-to-cart button/link")
                return False, None

            # Extract the cart URL from the button's href or onclick
            cart_url = add_btn.get('href', '')
            onclick = add_btn.get('onclick', '')

            # Try to find a form that wraps the cart functionality
            cart_form = soup.find('form', id=re.compile(r'cart|buy|submit', re.I))
            if not cart_form:
                # Look for form containing the add button
                cart_form = add_btn.find_parent('form')

            form_data = {}
            form_action = ''

            if cart_form:
                form_action = cart_form.get('action', '')
                if form_action and not form_action.startswith('http'):
                    if form_action.startswith('/'):
                        form_action = f"{self.http.BASE_URL}{form_action}"
                    else:
                        form_action = f"{self.http.BASE_URL}/{form_action}"

                # Collect all form fields
                for inp in cart_form.find_all('input'):
                    name = inp.get('name')
                    if name:
                        form_data[name] = inp.get('value', '')

                # Handle select elements (quantity)
                for sel in cart_form.find_all('select'):
                    name = sel.get('name')
                    if name:
                        selected = sel.find('option', selected=True)
                        form_data[name] = selected.get('value', '1') if selected else '1'

            # Override quantity
            qty_keys = [k for k in form_data if 'qty' in k.lower() or 'quantity' in k.lower()]
            for k in qty_keys:
                form_data[k] = str(quantity)

            # If no form found, try direct link approach
            if not form_action and cart_url:
                if not cart_url.startswith('http'):
                    cart_url = f"{self.http.BASE_URL}{cart_url}"
                logger.info("Using direct cart link...")
                resp = self.http.get(cart_url, allow_redirects=True)
            elif form_action:
                logger.info("Submitting cart form...")
                # Set Referer header to current product page
                headers = {'Referer': self._last_product_url or self.http.BASE_URL}
                resp = self.http.post(form_action, data=form_data,
                                      allow_redirects=True, headers=headers)
            else:
                # Last resort: try common Yodobashi cart API endpoint
                product_id = self._extract_product_id()
                if product_id:
                    cart_api = f"{self.http.ORDER_URL}/yc/shoppingcart/add.html"
                    form_data = {'productId': product_id, 'quantity': str(quantity)}
                    headers = {'Referer': self._last_product_url or self.http.BASE_URL}
                    resp = self.http.post(cart_api, data=form_data,
                                          allow_redirects=True, headers=headers)
                else:
                    logger.error("No cart form or URL found")
                    return False, None

            final_url = resp.url
            logger.success(f"Product added to cart! Redirected to: {final_url[:80]}")
            return True, final_url

        except Exception as e:
            logger.error(f"Failed to add to cart: {e}")
            return False, None

    def _extract_product_id(self) -> Optional[str]:
        """Extract product ID from the last product URL"""
        if not self._last_product_url:
            return None
        match = re.search(r'/product/(\d+)', self._last_product_url)
        return match.group(1) if match else None

    def go_to_checkout(self) -> Tuple[bool, str, BeautifulSoup]:
        """
        Navigate to shopping cart page

        Returns:
            Tuple of (success, final_url, soup)
        """
        logger.info("Navigating to shopping cart page...")
        try:
            cart_url = f"{self.http.ORDER_URL}/yc/shoppingcart/index.html"
            resp = self.http.get(cart_url, allow_redirects=True)
            soup = BeautifulSoup(resp.text, 'lxml')
            final_url = resp.url

            if 'shoppingcart' in final_url:
                logger.info("Navigated to shopping cart")
                return True, final_url, soup

            logger.error(f"Unexpected URL: {final_url}")
            return False, final_url, soup

        except Exception as e:
            logger.error(f"Failed to go to checkout: {e}")
            return False, "", BeautifulSoup("", 'lxml')
