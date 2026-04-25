from __future__ import annotations

import logging
import re

from backend.core.enums import OpportunityDomain, OpportunityLevel, OpportunityLocationType, OpportunityType
from backend.workers.worker_app.scrapers.base_scraper import BaseScraper, clean_text_local as clean_text

logger = logging.getLogger(__name__)


class InternshipScraper(BaseScraper):

    SOURCE_NAME = "internship_scraper"
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
            "internship+artificial+intelligence",
            "internship+machine+learning",
            "trainee+data+science+AI",
        ]
        items = []
        for q in queries:
            url = f"https://euraxess.ec.europa.eu/jobs/search?q={q}"
            soup = self._fetch_page(ctx, url, extra_wait_ms=4000)
            if not soup:
                continue

            # Confirmed: job links contain /jobs/{id} but NOT /jobs/search or /jobs/filter
            seen: set[str] = set()
            for a in soup.select('a[href*="/jobs/"]'):
                href = a.get("href", "")
                if not href or "/jobs/search" in href or "/jobs/filter" in href:
                    continue
                # Must be a job detail path: /jobs/{digits} or /jobs/{slug}
                if not re.search(r"/jobs/\d", href) and not re.search(r"/jobs/[a-z]", href):
                    continue
                if href in seen:
                    continue
                seen.add(href)

                full_url = href if href.startswith("http") else f"https://euraxess.ec.europa.eu{href}"
                title = clean_text(a.text)
                if not title or len(title) < 8:
                    continue

                parent = a.find_parent("article") or a.find_parent("li") or a.find_parent("div")
                org = country = None
                if parent:
                    for sel in ['[class*="organisation"]', '[class*="org"]', '[class*="employer"]']:
                        el = parent.select_one(sel)
                        if el:
                            org = clean_text(el.text, 255)
                            break
                    for sel in ['[class*="country"]', '[class*="location"]']:
                        el = parent.select_one(sel)
                        if el:
                            country = clean_text(el.text, 100)
                            break

                items.append(self._build_item(
                    title=title,
                    organization=org,
                    url=full_url,
                    type=OpportunityType.INTERNSHIP,
                    domain=OpportunityDomain.AI,
                    level=OpportunityLevel.MASTER,
                    country=country,
                    location_type=OpportunityLocationType.ONSITE,
                    tags=["internship", "research", "europe", "euraxess"],
                ))
            self._polite_sleep(1.5)

        logger.info("Euraxess internships: %d", len(items))
        return items

    def _scrape_academic_transfer(self, ctx) -> list[dict]:
        """
        Confirmed from debug: job links match /en/jobs/{digits}/{slug}/
        74 jobs found for 'artificial intelligence' query.
        """
        queries = [
            "artificial+intelligence",
            "machine+learning+data+science",
            "deep+learning+nlp",
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
                    type=OpportunityType.INTERNSHIP,
                    domain=OpportunityDomain.AI,
                    level=OpportunityLevel.MASTER,
                    country="Netherlands",
                    location_type=OpportunityLocationType.ONSITE,
                    tags=["internship", "netherlands", "academic", "ai"],
                ))
            self._polite_sleep(1.5)

        logger.info("AcademicTransfer internships: %d", len(items))
        return items