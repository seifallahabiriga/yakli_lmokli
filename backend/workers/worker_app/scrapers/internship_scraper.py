from __future__ import annotations

import logging

from backend.core.enums import OpportunityDomain, OpportunityLevel, OpportunityLocationType, OpportunityType
from backend.workers.worker_app.scrapers.base_scraper import BaseScraper
from backend.workers.worker_app.utils import clean_text

logger = logging.getLogger(__name__)


class InternshipScraper(BaseScraper):
    """
    Sources:
      - Nature Careers RSS (reliable, no bot detection)
      - Euraxess (Playwright, scraper-friendly EU portal)
      - AcademicTransfer (Playwright, Dutch academic portal)

    Removed: LinkedIn, Indeed — aggressive bot detection, returns empty pages.
    """

    SOURCE_NAME = "internship_scraper"
    DEFAULT_SCRAPER_TYPE = "dynamic"

    def run(self) -> list[dict]:
        items: list[dict] = []

        # Tier 1 — RSS, no browser needed
        items.extend(self._scrape_nature_rss())
        self._polite_sleep(1.0)

        # Tier 2 — Playwright
        with self._browser() as ctx:
            items.extend(self._scrape_euraxess(ctx))
            self._polite_sleep(2.0)
            items.extend(self._scrape_academic_transfer(ctx))
            self._polite_sleep(2.0)
            items.extend(self._scrape_findaphd_internships(ctx))

        return self._cap(self._dedup(items))

    def _scrape_nature_rss(self) -> list[dict]:
        """Nature Careers RSS — returns structured XML, 100% reliable."""
        entries = self._fetch_rss(
            "https://www.nature.com/naturecareers/rss/jobs?type=internship"
        )
        items = []
        for e in entries:
            if not e["link"] or not e["title"]:
                continue
            title = clean_text(e["title"], 512)
            if not any(kw in title.lower() for kw in ("intern", "trainee", "student")):
                continue
            items.append(self._build_item(
                title=title,
                description=clean_text(e["summary"], 1000),
                url=e["link"],
                type=OpportunityType.INTERNSHIP,
                domain=OpportunityDomain.AI,
                level=OpportunityLevel.MASTER,
                location_type=OpportunityLocationType.UNKNOWN,
                tags=["internship", "nature-careers", "research"],
                source="nature_careers_rss",
                scraper_type="static",
            ))
        logger.info("Nature RSS internships: %d", len(items))
        return items

    def _scrape_euraxess(self, ctx) -> list[dict]:
        pages = [
            "https://euraxess.ec.europa.eu/jobs/search?q=internship+artificial+intelligence",
            "https://euraxess.ec.europa.eu/jobs/search?q=internship+machine+learning",
            "https://euraxess.ec.europa.eu/jobs/search?q=student+AI+data+science",
        ]
        items = []
        for url in pages:
            soup = self._fetch_page(ctx, url,
                wait_selector="div.views-row, .view-content",
                extra_wait_ms=2000)
            if not soup:
                continue
            for card in soup.select("div.views-row, article.job, li.views-row"):
                try:
                    title_el = card.select_one("h3 a, h2 a, .views-field-title a, .job-title a")
                    org_el = card.select_one(".field-name-field-org, .organisation, .institution")
                    country_el = card.select_one(".field-name-field-country, .country")
                    if not title_el:
                        continue
                    href = title_el.get("href", "")
                    full_url = href if href.startswith("http") else f"https://euraxess.ec.europa.eu{href}"
                    items.append(self._build_item(
                        title=clean_text(title_el.text, 512),
                        organization=clean_text(org_el.text, 255) if org_el else None,
                        url=full_url,
                        type=OpportunityType.INTERNSHIP,
                        domain=OpportunityDomain.AI,
                        level=OpportunityLevel.MASTER,
                        country=clean_text(country_el.text, 100) if country_el else None,
                        location_type=OpportunityLocationType.ONSITE,
                        tags=["internship", "research", "europe", "euraxess"],
                    ))
                except Exception as exc:
                    logger.debug("Euraxess internship card error: %s", exc)
            self._polite_sleep(1.5)
        logger.info("Euraxess internships: %d", len(items))
        return items

    def _scrape_academic_transfer(self, ctx) -> list[dict]:
        url = "https://www.academictransfer.com/en/jobs/?q=internship+artificial+intelligence+data+science"
        soup = self._fetch_page(ctx, url,
            wait_selector="li.vacancy, article.vacancy",
            extra_wait_ms=2000, scroll=True)
        if not soup:
            return []
        items = []
        for card in soup.select("li.vacancy, article.vacancy, div.vacancy-item"):
            try:
                title_el = card.select_one("h3 a, h2 a, .vacancy-title a")
                org_el = card.select_one(".organisation, .employer, .vacancy-organisation")
                country_el = card.select_one(".location, .country")
                if not title_el:
                    continue
                href = title_el.get("href", "")
                full_url = href if href.startswith("http") else f"https://www.academictransfer.com{href}"
                items.append(self._build_item(
                    title=clean_text(title_el.text, 512),
                    organization=clean_text(org_el.text, 255) if org_el else None,
                    url=full_url,
                    type=OpportunityType.INTERNSHIP,
                    domain=OpportunityDomain.AI,
                    level=OpportunityLevel.MASTER,
                    country=clean_text(country_el.text, 100) if country_el else "Netherlands",
                    location_type=OpportunityLocationType.ONSITE,
                    tags=["internship", "netherlands", "academic", "ai"],
                ))
            except Exception as exc:
                logger.debug("AcademicTransfer error: %s", exc)
        logger.info("AcademicTransfer internships: %d", len(items))
        return items

    def _scrape_findaphd_internships(self, ctx) -> list[dict]:
        url = "https://www.findaphd.com/phds/non-phd-positions/?Keywords=artificial+intelligence+internship"
        soup = self._fetch_page(ctx, url,
            wait_selector="div.phd-result, div.g-mb-20",
            extra_wait_ms=2000)
        if not soup:
            return []
        items = []
        for card in soup.select("div.phd-result, div.g-mb-20"):
            try:
                title_el = card.select_one("h3 a, h2 a, a.h4, .title a")
                org_el = card.select_one(".institution, .uni-link, .phd-result__dept")
                if not title_el:
                    continue
                href = title_el.get("href", "")
                full_url = href if href.startswith("http") else f"https://www.findaphd.com{href}"
                items.append(self._build_item(
                    title=clean_text(title_el.text, 512),
                    organization=clean_text(org_el.text, 255) if org_el else None,
                    url=full_url,
                    type=OpportunityType.INTERNSHIP,
                    domain=OpportunityDomain.AI,
                    level=OpportunityLevel.MASTER,
                    location_type=OpportunityLocationType.ONSITE,
                    tags=["internship", "findaphd", "ai"],
                ))
            except Exception as exc:
                logger.debug("FindAPhD internship error: %s", exc)
        logger.info("FindAPhD internships: %d", len(items))
        return items