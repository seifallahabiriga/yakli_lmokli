from __future__ import annotations

import logging

from backend.core.enums import OpportunityDomain, OpportunityLevel, OpportunityLocationType, OpportunityType
from backend.workers.worker_app.scrapers.base_scraper import BaseScraper
from backend.workers.worker_app.utils import clean_text

logger = logging.getLogger(__name__)


class ScholarshipScraper(BaseScraper):
    """
    Sources:
      - DAAD scholarships (static HTML, German exchange service)
      - Scholars4Dev (static WordPress)
      - Euraxess fellowships (Playwright)
      - FindAPhD scholarships (Playwright)
    """

    SOURCE_NAME = "scholarship_scraper"
    DEFAULT_SCRAPER_TYPE = "dynamic"

    def run(self) -> list[dict]:
        items: list[dict] = []

        # Tier 1 — static/RSS
        items.extend(self._scrape_daad())
        self._polite_sleep(1.5)
        items.extend(self._scrape_scholars4dev())
        self._polite_sleep(1.5)

        # Tier 2 — Playwright
        with self._browser() as ctx:
            items.extend(self._scrape_euraxess_fellowships(ctx))
            self._polite_sleep(2.0)
            items.extend(self._scrape_findaphd(ctx))

        return self._cap(self._dedup(items))

    def _scrape_daad(self) -> list[dict]:
        """DAAD scholarship database — German academic exchange, very scraper-friendly."""
        urls = [
            "https://www.daad.de/en/studying-in-germany/scholarships/daad-scholarships/",
            "https://www.daad.de/en/the-daad/what-we-do/funding-information-database/",
        ]
        items = []
        for url in urls:
            soup = self._fetch_static(url)
            if not soup:
                continue
            for card in soup.select(
                "article, div.scholarship-item, div.c-teaser, "
                "li.scholarship, div.funding-item"
            ):
                try:
                    title_el = card.select_one("h3 a, h2 a, h4 a, .c-teaser__title a, a")
                    if not title_el:
                        continue
                    href = title_el.get("href", "")
                    if not href:
                        continue
                    full_url = href if href.startswith("http") else f"https://www.daad.de{href}"
                    items.append(self._build_item(
                        title=clean_text(title_el.text, 512),
                        organization="DAAD",
                        url=full_url,
                        type=OpportunityType.SCHOLARSHIP,
                        domain=OpportunityDomain.AI,
                        level=OpportunityLevel.MASTER,
                        country="Germany",
                        location_type=OpportunityLocationType.ONSITE,
                        tags=["scholarship", "daad", "germany", "funding"],
                        source="daad",
                        scraper_type="static",
                    ))
                except Exception as exc:
                    logger.debug("DAAD card error: %s", exc)
        logger.info("DAAD scholarships: %d", len(items))
        return items

    def _scrape_scholars4dev(self) -> list[dict]:
        """Scholars4Dev — WordPress blog, fully static, lists international scholarships."""
        urls = [
            "https://www.scholars4dev.com/category/scholarships-by-field/science-technology-scholarships/",
            "https://www.scholars4dev.com/category/scholarships-by-field/computer-science-scholarships/",
        ]
        items = []
        for url in urls:
            soup = self._fetch_static(url)
            if not soup:
                continue
            for article in soup.select("article, h2.entry-title, div.post"):
                try:
                    title_el = article.select_one("h2 a, h1 a, .entry-title a")
                    excerpt_el = article.select_one(".entry-summary p, .excerpt p")
                    if not title_el:
                        continue
                    href = title_el.get("href", "")
                    if not href.startswith("http"):
                        continue
                    items.append(self._build_item(
                        title=clean_text(title_el.text, 512),
                        description=clean_text(excerpt_el.text, 500) if excerpt_el else None,
                        url=href,
                        type=OpportunityType.SCHOLARSHIP,
                        domain=OpportunityDomain.AI,
                        level=OpportunityLevel.MASTER,
                        location_type=OpportunityLocationType.UNKNOWN,
                        tags=["scholarship", "international", "stem", "funding"],
                        source="scholars4dev",
                        scraper_type="static",
                    ))
                except Exception as exc:
                    logger.debug("scholars4dev error: %s", exc)
            self._polite_sleep(1.0)
        logger.info("Scholars4Dev scholarships: %d", len(items))
        return items

    def _scrape_euraxess_fellowships(self, ctx) -> list[dict]:
        pages = [
            "https://euraxess.ec.europa.eu/jobs/search?q=fellowship+scholarship+AI+data+science",
            "https://euraxess.ec.europa.eu/jobs/search?q=scholarship+machine+learning",
        ]
        items = []
        for url in pages:
            soup = self._fetch_page(ctx, url,
                wait_selector="div.views-row, .view-content",
                extra_wait_ms=2000)
            if not soup:
                continue
            for card in soup.select("div.views-row, article.job"):
                try:
                    title_el = card.select_one("h3 a, h2 a, .views-field-title a")
                    org_el = card.select_one(".field-name-field-org, .organisation")
                    country_el = card.select_one(".field-name-field-country, .country")
                    if not title_el:
                        continue
                    href = title_el.get("href", "")
                    full_url = href if href.startswith("http") else f"https://euraxess.ec.europa.eu{href}"
                    items.append(self._build_item(
                        title=clean_text(title_el.text, 512),
                        organization=clean_text(org_el.text, 255) if org_el else None,
                        url=full_url,
                        type=OpportunityType.FELLOWSHIP,
                        domain=OpportunityDomain.AI,
                        level=OpportunityLevel.PHD,
                        country=clean_text(country_el.text, 100) if country_el else None,
                        location_type=OpportunityLocationType.ONSITE,
                        tags=["fellowship", "research", "europe", "euraxess"],
                    ))
                except Exception as exc:
                    logger.debug("Euraxess fellowship error: %s", exc)
            self._polite_sleep(1.5)
        logger.info("Euraxess fellowships: %d", len(items))
        return items

    def _scrape_findaphd(self, ctx) -> list[dict]:
        url = "https://www.findaphd.com/phds/scholarship/?Keywords=artificial+intelligence+machine+learning"
        soup = self._fetch_page(ctx, url,
            wait_selector="div.phd-result, div.g-mb-20",
            extra_wait_ms=2000, scroll=True)
        if not soup:
            return []
        items = []
        for card in soup.select("div.phd-result, div.g-mb-20"):
            try:
                title_el = card.select_one("h3 a, h2 a, a.h4")
                org_el = card.select_one(".institution, .uni-link")
                if not title_el:
                    continue
                href = title_el.get("href", "")
                full_url = href if href.startswith("http") else f"https://www.findaphd.com{href}"
                items.append(self._build_item(
                    title=clean_text(title_el.text, 512),
                    organization=clean_text(org_el.text, 255) if org_el else None,
                    url=full_url,
                    type=OpportunityType.SCHOLARSHIP,
                    domain=OpportunityDomain.AI,
                    level=OpportunityLevel.PHD,
                    location_type=OpportunityLocationType.ONSITE,
                    tags=["phd", "scholarship", "ai", "findaphd"],
                ))
            except Exception as exc:
                logger.debug("FindAPhD scholarship error: %s", exc)
        logger.info("FindAPhD scholarships: %d", len(items))
        return items