from __future__ import annotations

import logging

from backend.core.enums import OpportunityDomain, OpportunityLevel, OpportunityLocationType, OpportunityType
from backend.workers.worker_app.scrapers.base_scraper import BaseScraper, clean_text_local as clean_text

logger = logging.getLogger(__name__)


class ScholarshipScraper(BaseScraper):
    """Already returning 12 items. Keep working sources, add AcademicTransfer scholarships."""

    SOURCE_NAME = "scholarship_scraper"
    DEFAULT_SCRAPER_TYPE = "dynamic"

    def run(self) -> list[dict]:
        items: list[dict] = []

        # Static — confirmed working
        items.extend(self._scrape_daad())
        self._polite_sleep(1.5)
        items.extend(self._scrape_scholars4dev())
        self._polite_sleep(1.5)

        # Playwright
        with self._browser() as ctx:
            items.extend(self._scrape_euraxess_fellowships(ctx))
            self._polite_sleep(2.0)
            items.extend(self._scrape_academic_transfer(ctx))

        return self._cap(self._dedup(items))

    def _scrape_daad(self) -> list[dict]:
        items = []
        soup = self._fetch_static(
            "https://www.daad.de/en/studying-in-germany/scholarships/daad-scholarships/"
        )
        if not soup:
            return []
        for a in soup.select('a[href*="stipendium"], a[href*="scholarship"], a[href*="funding"]'):
            href = a.get("href", "")
            title = clean_text(a.text)
            if not href or not title or len(title) < 8:
                continue
            full_url = href if href.startswith("http") else f"https://www.daad.de{href}"
            items.append(self._build_item(
                title=title,
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
        logger.info("DAAD scholarships: %d", len(items))
        return items

    def _scrape_scholars4dev(self) -> list[dict]:
        items = []
        urls = [
            "https://www.scholars4dev.com/category/scholarships-by-field/science-technology-scholarships/",
            "https://www.scholars4dev.com/category/scholarships-by-field/computer-science-scholarships/",
        ]
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
                        title=clean_text(title_el.text),
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
        import re
        queries = [
            "fellowship+scholarship+AI+data+science",
            "scholarship+machine+learning",
        ]
        items = []
        for q in queries:
            url = f"https://euraxess.ec.europa.eu/jobs/search?q={q}"
            soup = self._fetch_page(ctx, url, extra_wait_ms=4000)
            if not soup:
                continue
            seen: set[str] = set()
            for a in soup.select('a[href*="/jobs/"]'):
                href = a.get("href", "")
                if not href or "/jobs/search" in href or "/jobs/filter" in href:
                    continue
                if not re.search(r"/jobs/\d", href):
                    continue
                if href in seen:
                    continue
                seen.add(href)
                full_url = href if href.startswith("http") else f"https://euraxess.ec.europa.eu{href}"
                title = clean_text(a.text)
                if not title or len(title) < 8:
                    continue
                items.append(self._build_item(
                    title=title,
                    url=full_url,
                    type=OpportunityType.FELLOWSHIP,
                    domain=OpportunityDomain.AI,
                    level=OpportunityLevel.PHD,
                    location_type=OpportunityLocationType.ONSITE,
                    tags=["fellowship", "research", "europe", "euraxess"],
                ))
            self._polite_sleep(1.5)
        logger.info("Euraxess fellowships: %d", len(items))
        return items

    def _scrape_academic_transfer(self, ctx) -> list[dict]:
        items = []
        queries = ["scholarship+AI", "fellowship+machine+learning", "grant+data+science"]
        for q in queries:
            url = f"https://www.academictransfer.com/en/jobs/?q={q}"
            soup = self._fetch_page(ctx, url, extra_wait_ms=3000, scroll=True)
            if not soup:
                continue
            for link in self._extract_at_links(soup):
                items.append(self._build_item(
                    title=link["title"],
                    url=link["url"],
                    type=OpportunityType.SCHOLARSHIP,
                    domain=OpportunityDomain.AI,
                    level=OpportunityLevel.PHD,
                    country="Netherlands",
                    location_type=OpportunityLocationType.ONSITE,
                    tags=["scholarship", "netherlands", "academic"],
                ))
            self._polite_sleep(1.5)
        logger.info("AcademicTransfer scholarships: %d", len(items))
        return items