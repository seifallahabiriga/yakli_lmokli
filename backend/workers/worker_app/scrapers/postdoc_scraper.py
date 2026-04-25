from __future__ import annotations

import logging
import re

from backend.core.enums import OpportunityDomain, OpportunityLevel, OpportunityLocationType, OpportunityType
from backend.workers.worker_app.scrapers.base_scraper import BaseScraper, clean_text_local as clean_text

logger = logging.getLogger(__name__)


class PostdocScraper(BaseScraper):

    SOURCE_NAME = "postdoc_scraper"
    DEFAULT_SCRAPER_TYPE = "dynamic"

    def run(self) -> list[dict]:
        items: list[dict] = []
        with self._browser() as ctx:
            items.extend(self._scrape_euraxess(ctx))
            self._polite_sleep(2.0)
            items.extend(self._scrape_academic_transfer(ctx))
            self._polite_sleep(2.0)
            items.extend(self._scrape_academic_positions(ctx))
        return self._cap(self._dedup(items))

    def _scrape_euraxess(self, ctx) -> list[dict]:
        queries = [
            "postdoc+artificial+intelligence",
            "postdoctoral+machine+learning",
            "postdoc+deep+learning+data+science",
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
                    type=OpportunityType.POSTDOC,
                    domain=OpportunityDomain.AI,
                    level=OpportunityLevel.POSTDOC,
                    country=country,
                    location_type=OpportunityLocationType.ONSITE,
                    tags=["postdoc", "research", "europe", "euraxess", "ai"],
                ))
            self._polite_sleep(1.5)

        logger.info("Euraxess postdocs: %d", len(items))
        return items

    def _scrape_academic_transfer(self, ctx) -> list[dict]:
        """
        Confirmed from debug: /en/jobs/{digits}/{slug}/ pattern.
        Found postdoc and PhD positions for AI queries.
        """
        queries = [
            "postdoc+artificial+intelligence",
            "postdoctoral+machine+learning",
            "postdoc+computer+vision+nlp",
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
                    type=OpportunityType.POSTDOC,
                    domain=OpportunityDomain.AI,
                    level=OpportunityLevel.POSTDOC,
                    country="Netherlands",
                    location_type=OpportunityLocationType.ONSITE,
                    tags=["postdoc", "netherlands", "academic", "ai"],
                ))
            self._polite_sleep(1.5)

        logger.info("AcademicTransfer postdocs: %d", len(items))
        return items

    def _scrape_academic_positions(self, ctx) -> list[dict]:
        """Academic Positions — European academic job board."""
        queries = [
            "postdoc+AI+machine+learning",
            "postdoctoral+deep+learning",
        ]
        items = []
        for q in queries:
            url = f"https://academicpositions.com/jobs?keywords={q}&type=postdoc"
            soup = self._fetch_page(
                ctx, url,
                wait_selector="article.job, div.job-item, ul.jobs-list",
                extra_wait_ms=3000,
                scroll=True,
            )
            if not soup:
                continue

            for card in soup.select("article.job, div.job-item, li.job, div[class*='job-card']"):
                try:
                    title_el = card.select_one("h2 a, h3 a, .job-title a, a[href*='/jobs/']")
                    org_el = card.select_one(".employer, .university, .institution")
                    country_el = card.select_one(".country, .location, .job-location")
                    if not title_el:
                        continue
                    href = title_el.get("href", "")
                    full_url = href if href.startswith("http") else f"https://academicpositions.com{href}"
                    title = clean_text(title_el.text)
                    if not title or len(title) < 8:
                        continue

                    items.append(self._build_item(
                        title=title,
                        organization=clean_text(org_el.text, 255) if org_el else None,
                        url=full_url,
                        type=OpportunityType.POSTDOC,
                        domain=OpportunityDomain.AI,
                        level=OpportunityLevel.POSTDOC,
                        country=clean_text(country_el.text, 100) if country_el else None,
                        location_type=OpportunityLocationType.ONSITE,
                        tags=["postdoc", "academic", "machine-learning", "ai"],
                    ))
                except Exception as exc:
                    logger.debug("academicpositions error: %s", exc)

            self._polite_sleep(1.5)

        logger.info("Academic Positions postdocs: %d", len(items))
        return items