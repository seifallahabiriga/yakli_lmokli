from __future__ import annotations

import logging

from backend.core.enums import OpportunityDomain, OpportunityLevel, OpportunityLocationType, OpportunityType
from backend.workers.worker_app.scrapers.base_scraper import BaseScraper
from backend.workers.worker_app.utils import clean_text

logger = logging.getLogger(__name__)


class ProjectScraper(BaseScraper):
    """
    Sources:
      - Nature Careers RSS (research positions)
      - Euraxess research projects
      - EU Funding & Tenders portal (open calls)
      - AcademicTransfer research positions
    """

    SOURCE_NAME = "project_scraper"
    DEFAULT_SCRAPER_TYPE = "dynamic"

    def run(self) -> list[dict]:
        items: list[dict] = []

        items.extend(self._scrape_nature_rss())
        self._polite_sleep(1.0)

        with self._browser() as ctx:
            items.extend(self._scrape_euraxess(ctx))
            self._polite_sleep(2.0)
            items.extend(self._scrape_academic_transfer(ctx))

        return self._cap(self._dedup(items))

    def _scrape_nature_rss(self) -> list[dict]:
        entries = self._fetch_rss("https://www.nature.com/naturecareers/rss/jobs?type=research")
        items = []
        for e in entries:
            if not e["link"] or not e["title"]:
                continue
            items.append(self._build_item(
                title=clean_text(e["title"], 512),
                description=clean_text(e["summary"], 1000),
                url=e["link"],
                type=OpportunityType.RESEARCH_PROJECT,
                domain=OpportunityDomain.AI,
                level=OpportunityLevel.PHD,
                location_type=OpportunityLocationType.UNKNOWN,
                tags=["research", "nature-careers"],
                source="nature_careers_rss",
                scraper_type="static",
            ))
        logger.info("Nature RSS projects: %d", len(items))
        return items

    def _scrape_euraxess(self, ctx) -> list[dict]:
        pages = [
            "https://euraxess.ec.europa.eu/jobs/search?q=research+project+AI+machine+learning",
            "https://euraxess.ec.europa.eu/jobs/search?q=research+position+data+science+neural",
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
                        type=OpportunityType.RESEARCH_PROJECT,
                        domain=OpportunityDomain.AI,
                        level=OpportunityLevel.PHD,
                        country=clean_text(country_el.text, 100) if country_el else None,
                        location_type=OpportunityLocationType.ONSITE,
                        tags=["research", "project", "europe", "ai", "euraxess"],
                    ))
                except Exception as exc:
                    logger.debug("Euraxess project error: %s", exc)
            self._polite_sleep(1.5)
        logger.info("Euraxess projects: %d", len(items))
        return items

    def _scrape_academic_transfer(self, ctx) -> list[dict]:
        url = "https://www.academictransfer.com/en/jobs/?q=AI+machine+learning+research+project"
        soup = self._fetch_page(ctx, url,
            wait_selector="li.vacancy, article.vacancy",
            extra_wait_ms=2000, scroll=True)
        if not soup:
            return []
        items = []
        for card in soup.select("li.vacancy, article.vacancy, div.vacancy-item"):
            try:
                title_el = card.select_one("h3 a, h2 a, .vacancy-title a")
                org_el = card.select_one(".organisation, .employer")
                country_el = card.select_one(".location, .country")
                if not title_el:
                    continue
                href = title_el.get("href", "")
                full_url = href if href.startswith("http") else f"https://www.academictransfer.com{href}"
                items.append(self._build_item(
                    title=clean_text(title_el.text, 512),
                    organization=clean_text(org_el.text, 255) if org_el else None,
                    url=full_url,
                    type=OpportunityType.RESEARCH_PROJECT,
                    domain=OpportunityDomain.AI,
                    level=OpportunityLevel.PHD,
                    country=clean_text(country_el.text, 100) if country_el else "Netherlands",
                    location_type=OpportunityLocationType.ONSITE,
                    tags=["research", "project", "netherlands", "ai"],
                ))
            except Exception as exc:
                logger.debug("AcademicTransfer project error: %s", exc)
        logger.info("AcademicTransfer projects: %d", len(items))
        return items