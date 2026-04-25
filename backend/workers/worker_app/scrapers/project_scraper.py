from __future__ import annotations

import logging
import re

from backend.core.enums import OpportunityDomain, OpportunityLevel, OpportunityLocationType, OpportunityType
from backend.workers.worker_app.scrapers.base_scraper import BaseScraper, clean_text_local as clean_text

logger = logging.getLogger(__name__)


class ProjectScraper(BaseScraper):

    SOURCE_NAME = "project_scraper"
    DEFAULT_SCRAPER_TYPE = "dynamic"

    def run(self) -> list[dict]:
        items: list[dict] = []
        with self._browser() as ctx:
            items.extend(self._scrape_euraxess(ctx))
            self._polite_sleep(2.0)
            items.extend(self._scrape_academic_transfer(ctx))
        return self._cap(self._dedup(items))

    def _scrape_euraxess(self, ctx) -> list[dict]:
        queries = [
            "research+project+AI+machine+learning",
            "research+position+data+science+neural+network",
            "research+fellow+deep+learning",
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
                    type=OpportunityType.RESEARCH_PROJECT,
                    domain=OpportunityDomain.AI,
                    level=OpportunityLevel.PHD,
                    location_type=OpportunityLocationType.ONSITE,
                    tags=["research", "project", "europe", "ai", "euraxess"],
                ))
            self._polite_sleep(1.5)
        logger.info("Euraxess projects: %d", len(items))
        return items

    def _scrape_academic_transfer(self, ctx) -> list[dict]:
        queries = [
            "AI+research+project",
            "machine+learning+research",
            "computer+vision+research",
        ]
        items = []
        for q in queries:
            url = f"https://www.academictransfer.com/en/jobs/?q={q}"
            soup = self._fetch_page(ctx, url, extra_wait_ms=3000, scroll=True)
            if not soup:
                continue
            for link in self._extract_at_links(soup):
                items.append(self._build_item(
                    title=link["title"],
                    url=link["url"],
                    type=OpportunityType.RESEARCH_PROJECT,
                    domain=OpportunityDomain.AI,
                    level=OpportunityLevel.PHD,
                    country="Netherlands",
                    location_type=OpportunityLocationType.ONSITE,
                    tags=["research", "project", "netherlands", "ai"],
                ))
            self._polite_sleep(1.5)
        logger.info("AcademicTransfer projects: %d", len(items))
        return items