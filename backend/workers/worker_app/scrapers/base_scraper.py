from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from contextlib import contextmanager

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from backend.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class BaseScraper(ABC):

    SOURCE_NAME: str = "base"
    DEFAULT_SCRAPER_TYPE: str = "dynamic"

    def __init__(self) -> None:
        self._session = self._build_session()

    @abstractmethod
    def run(self) -> list[dict]:
        """Return raw opportunity dicts matching OpportunityCreate fields."""

    # ------------------------------------------------------------------
    # Session — for static pages only
    # ------------------------------------------------------------------

    def _build_session(self) -> requests.Session:
        session = requests.Session()
        retry = Retry(
            total=settings.SCRAPER_MAX_RETRIES,
            backoff_factor=settings.SCRAPER_RETRY_BACKOFF,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        session.headers.update({"User-Agent": settings.SCRAPER_USER_AGENT})
        return session

    # ------------------------------------------------------------------
    # Playwright context — shared browser per run()
    # ------------------------------------------------------------------

    @contextmanager
    def _browser(self):
        """
        Yields a Playwright BrowserContext.
        Use inside run() so one Chromium process serves all URLs.
        """
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=settings.SCRAPER_PLAYWRIGHT_HEADLESS,
                args=[
                    "--no-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                ],
            )
            context = browser.new_context(
                user_agent=settings.SCRAPER_USER_AGENT,
                viewport={"width": 1280, "height": 800},
                java_script_enabled=True,
            )
            try:
                yield context
            finally:
                context.close()
                browser.close()

    def _fetch_page(
        self,
        context,
        url: str,
        wait_selector: str | None = None,
        wait_state: str = "networkidle",
        extra_wait_ms: int = 0,
        scroll: bool = False,
    ) -> BeautifulSoup | None:
        """
        Fetches a JS-rendered page via Playwright.
        Blocks images/media/fonts to reduce bandwidth and latency.
        """
        page = None
        try:
            page = context.new_page()
            page.route(
                "**/*",
                lambda route: route.abort()
                if route.request.resource_type in ("image", "media", "font")
                else route.continue_(),
            )
            page.goto(
                url,
                timeout=settings.SCRAPER_REQUEST_TIMEOUT * 1000,
                wait_until=wait_state,
            )
            if wait_selector:
                try:
                    page.wait_for_selector(wait_selector, timeout=10000, state="visible")
                except Exception:
                    logger.debug("Selector '%s' not found on %s", wait_selector, url)
            if extra_wait_ms:
                page.wait_for_timeout(extra_wait_ms)
            if scroll:
                self._scroll_to_bottom(page)

            return BeautifulSoup(page.content(), "lxml")

        except Exception as exc:
            logger.warning("Playwright fetch failed %s: %s", url, exc)
            return None
        finally:
            if page:
                try:
                    page.close()
                except Exception:
                    pass

    def _scroll_to_bottom(self, page, steps: int = 5, delay_ms: int = 800) -> None:
        for i in range(1, steps + 1):
            page.evaluate(f"window.scrollTo(0, document.body.scrollHeight * {i / steps})")
            page.wait_for_timeout(delay_ms)

    # ------------------------------------------------------------------
    # Static fallback
    # ------------------------------------------------------------------

    def _fetch_static(self, url: str) -> BeautifulSoup | None:
        try:
            resp = self._session.get(url, timeout=settings.SCRAPER_REQUEST_TIMEOUT)
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "lxml")
        except Exception as exc:
            logger.warning("Static fetch failed %s: %s", url, exc)
            return None

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def _polite_sleep(self, seconds: float = 2.0) -> None:
        time.sleep(seconds)

    def _build_item(self, **kwargs) -> dict:
        base = {
            "source": self.SOURCE_NAME,
            "scraper_type": self.DEFAULT_SCRAPER_TYPE,
            "raw_data": {},
            "eligibility": {},
            "required_skills": [],
            "tags": [],
        }
        base.update({k: v for k, v in kwargs.items() if v is not None})
        return base

    def _dedup(self, items: list[dict]) -> list[dict]:
        seen: set[str] = set()
        result = []
        for item in items:
            url = item.get("url", "")
            if url and url not in seen:
                seen.add(url)
                result.append(item)
        return result

    def _cap(self, items: list[dict]) -> list[dict]:
        return items[: settings.SCRAPER_MAX_RESULTS_PER_RUN]