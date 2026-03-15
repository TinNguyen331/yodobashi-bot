"""
HTTP session manager for Yodobashi Bot - replaces Playwright browser.
Uses curl_cffi to impersonate Chrome's TLS fingerprint, bypassing
Yodobashi's blocking of raw requests/urllib connections.
"""
import json
from pathlib import Path

from curl_cffi import requests as cffi_requests
from bs4 import BeautifulSoup
from loguru import logger

from .utils import get_project_root


class HttpSession:
    """
    Manages HTTP session with persistent cookies for Yodobashi.com
    Uses curl_cffi with Chrome impersonation to bypass TLS fingerprint blocking.
    Replaces BrowserManager - no browser needed, runs in background.
    """

    BASE_URL = "https://www.yodobashi.com"
    ORDER_URL = "https://order.yodobashi.com"

    def __init__(self, config: dict):
        self.config = config
        self.settings = config.get('settings', {})
        self.session = cffi_requests.Session(impersonate="chrome")
        self.session.headers.update({
            'Accept-Language': 'ja-JP,ja;q=0.9,en;q=0.8',
        })
        self.session_path = get_project_root() / "session"
        self.session_path.mkdir(exist_ok=True)
        self.timeout = self.settings.get('timeout', 30)

    def get(self, url: str, **kwargs):
        """GET request with Chrome TLS fingerprint"""
        kwargs.setdefault('timeout', self.timeout)
        kwargs.setdefault('allow_redirects', True)
        logger.debug(f"GET {url}")
        resp = self.session.get(url, **kwargs)
        logger.debug(f"  -> {resp.status_code} ({len(resp.content)} bytes)")
        return resp

    def post(self, url: str, **kwargs):
        """POST request with Chrome TLS fingerprint"""
        kwargs.setdefault('timeout', self.timeout)
        kwargs.setdefault('allow_redirects', True)
        logger.debug(f"POST {url}")
        resp = self.session.post(url, **kwargs)
        logger.debug(f"  -> {resp.status_code} ({len(resp.content)} bytes)")
        return resp

    def get_soup(self, url: str, **kwargs) -> BeautifulSoup:
        """GET request and return parsed BeautifulSoup"""
        resp = self.get(url, **kwargs)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, 'lxml')

    def navigate_to_home(self) -> BeautifulSoup:
        """Navigate to Yodobashi homepage (establishes session cookies)"""
        logger.info(f"Navigating to {self.BASE_URL}")
        soup = self.get_soup(self.BASE_URL)
        logger.info("Homepage loaded")
        return soup

    def save_session(self):
        """Save cookies to file. Uses internal jar to handle duplicate names across domains."""
        cookie_file = self.session_path / "cookies.json"
        cookies = []
        try:
            for cookie in self.session.cookies.jar:
                cookies.append({
                    'name': cookie.name,
                    'value': cookie.value,
                    'domain': cookie.domain,
                    'path': cookie.path,
                })
        except Exception:
            # Fallback: just save what we can
            pass
        with open(cookie_file, 'w') as f:
            json.dump(cookies, f, indent=2)
        logger.info("Session cookies saved")

    def load_session(self) -> bool:
        """Load cookies from file"""
        cookie_file = self.session_path / "cookies.json"
        if not cookie_file.exists():
            return False
        try:
            with open(cookie_file, 'r') as f:
                cookies = json.load(f)
            for c in cookies:
                if isinstance(c, dict):
                    self.session.cookies.set(
                        c['name'], c['value'],
                        domain=c.get('domain', ''),
                        path=c.get('path', '/')
                    )
                else:
                    # Legacy format: {name: value}
                    self.session.cookies.set(c, cookies[c])
            logger.info("Session cookies loaded")
            return True
        except Exception as e:
            logger.warning(f"Failed to load session: {e}")
            return False

    def save_page(self, html: str, name: str = "page"):
        """Save HTML response to logs for debugging"""
        log_dir = get_project_root() / "logs"
        log_dir.mkdir(exist_ok=True)
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = log_dir / f"{name}_{timestamp}.html"
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html)
        logger.debug(f"Page saved: {filepath}")

    def close(self):
        """Close session and save cookies"""
        self.save_session()
        self.session.close()
        logger.info("HTTP session closed")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            logger.error(f"Exception occurred: {exc_val}")
        self.close()
        return False
