"""
Login module for Yodobashi Bot (HTTP version)
Handles login via direct HTTP POST instead of browser automation
"""
import re
from typing import Optional

from bs4 import BeautifulSoup
from loguru import logger


class LoginHandler:
    """
    Handles login to Yodobashi via HTTP requests
    """

    LOGIN_PAGE_URL = "https://www.yodobashi.com/ec/member/login/"
    CHECKOUT_LOGIN_URL = "https://order.yodobashi.com/yc/login/order/index.html"

    def __init__(self, http_session, config: dict):
        self.http = http_session
        self.config = config
        self.account = config.get('account', {})
        self.settings = config.get('settings', {})

    def is_logged_in(self, soup: Optional[BeautifulSoup] = None) -> bool:
        """Check if user is logged in by looking for logout/mypage links"""
        if soup is None:
            soup = self.http.get_soup(self.http.BASE_URL)

        # Check for logout link or mypage link (indicates logged in)
        logout_link = soup.find('a', string=re.compile(r'ログアウト'))
        mypage_link = soup.find('a', string=re.compile(r'マイページ'))

        if logout_link or mypage_link:
            logger.info("Already logged in")
            return True

        # Check if login link exists (indicates NOT logged in)
        login_link = soup.find('a', string=re.compile(r'ログイン'))
        if login_link:
            return False

        return False

    def login(self) -> bool:
        """
        Login to Yodobashi via HTTP POST

        Returns:
            bool: True if login successful
        """
        logger.info("Starting login process...")

        # Check if already logged in
        home_soup = self.http.navigate_to_home()
        if self.is_logged_in(home_soup):
            return True

        username = self.account.get('username', '')
        password = self.account.get('password', '')
        if not username or not password:
            logger.error("Username or password not configured!")
            return False

        max_retries = self.settings.get('max_retries', 3)

        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"Login attempt {attempt}/{max_retries}")

                # Step 1: GET login page to get any hidden form fields/tokens
                login_soup = self.http.get_soup(self.LOGIN_PAGE_URL)

                # Step 2: Extract form action URL and hidden fields
                form = login_soup.find('form', attrs={'id': re.compile(r'login', re.I)})
                if not form:
                    # Try finding any form with memberId field
                    form = login_soup.find('form', attrs={
                        'action': re.compile(r'login', re.I)
                    })
                if not form:
                    # Fallback: find form containing memberId input
                    member_input = login_soup.find('input', {'name': 'memberId'})
                    if member_input:
                        form = member_input.find_parent('form')

                form_action = self.LOGIN_PAGE_URL
                hidden_fields = {}

                if form:
                    action = form.get('action', '')
                    if action:
                        if action.startswith('http'):
                            form_action = action
                        elif action.startswith('/'):
                            form_action = f"{self.http.BASE_URL}{action}"

                    # Collect all hidden input fields (CSRF tokens, etc.)
                    for hidden in form.find_all('input', {'type': 'hidden'}):
                        name = hidden.get('name')
                        value = hidden.get('value', '')
                        if name:
                            hidden_fields[name] = value

                # Step 3: POST login credentials
                login_data = {
                    **hidden_fields,
                    'memberId': username,
                    'password': password,
                }

                resp = self.http.post(
                    form_action,
                    data=login_data,
                    allow_redirects=True,
                )

                # Step 4: Check if login was successful
                result_soup = BeautifulSoup(resp.text, 'lxml')
                if self.is_logged_in(result_soup):
                    logger.success("Login successful!")
                    return True

                # Check for error messages
                error_el = result_soup.find(class_=re.compile(r'error|alert'))
                if error_el:
                    logger.error(f"Login error: {error_el.get_text(strip=True)}")

                logger.warning(f"Login attempt {attempt} failed")

            except Exception as e:
                logger.error(f"Error during login attempt {attempt}: {e}")

        logger.error("All login attempts failed!")
        return False

    def login_at_checkout(self, current_url: str = "", html: str = "") -> bool:
        """
        Handle login page that appears during checkout process

        Args:
            current_url: Current page URL to check if it's a login page
            html: Current page HTML content

        Returns:
            bool: True if login successful or not on login page
        """
        # Check if we're on a login page
        is_login_page = any([
            '/login/' in current_url.lower(),
            '/yc/login/' in current_url.lower(),
            'login/order' in current_url.lower(),
        ])

        if not is_login_page and html:
            soup = BeautifulSoup(html, 'lxml')
            member_field = soup.find('input', {'name': 'memberId'})
            if member_field:
                is_login_page = True

        if not is_login_page:
            logger.debug("Not on checkout login page, skipping")
            return True

        logger.info("Detected checkout login page, logging in...")

        username = self.account.get('username', '')
        password = self.account.get('password', '')
        if not username or not password:
            logger.error("Username or password not configured!")
            return False

        try:
            # GET the login page to extract form fields
            if not html:
                resp = self.http.get(current_url or self.CHECKOUT_LOGIN_URL)
                html = resp.text

            soup = BeautifulSoup(html, 'lxml')

            # Find the login form
            form = soup.find('form')
            form_action = current_url or self.CHECKOUT_LOGIN_URL
            hidden_fields = {}

            if form:
                action = form.get('action', '')
                if action:
                    if action.startswith('http'):
                        form_action = action
                    elif action.startswith('/'):
                        form_action = f"{self.http.ORDER_URL}{action}"

                for hidden in form.find_all('input', {'type': 'hidden'}):
                    name = hidden.get('name')
                    value = hidden.get('value', '')
                    if name:
                        hidden_fields[name] = value

            login_data = {
                **hidden_fields,
                'memberId': username,
                'password': password,
            }

            resp = self.http.post(form_action, data=login_data, allow_redirects=True)

            # Check if we got redirected away from login page
            final_url = resp.url
            if '/login/' not in final_url.lower():
                logger.success("Logged in at checkout successfully!")
                return True

            logger.warning("Checkout login may have failed")
            self.http.save_page(resp.text, "checkout_login_result")
            return False

        except Exception as e:
            logger.error(f"Error during checkout login: {e}")
            return False
