from __future__ import annotations

import logging

from backend.core.enums import OpportunityDomain, OpportunityLevel, OpportunityLocationType, OpportunityType
from backend.workers.worker_app.scrapers.base_scraper import BaseScraper
from backend.workers.worker_app.utils import clean_text

logger = logging.getLogger(__name__)


class PostdocScraper(BaseScraper):
    """
    Sources:
      - Nature Careers RSS (postdoc positions)
      - Euraxess postdoc positions
      - AcademicTransfer postdoc
      - Academic Positions
      - FindAPhD postdoc listings
    """

    SOURCE_NAME = "postdoc_scraper"
    DEFAULT_SCRAPER_TYPE = "dynamic"

    def run(self) -> list[dict]:
        items: list[dict] = []

        items.extend(self._scrape_nature_rss())
        self._polite_sleep(1.0)

        with self._browser() as ctx:
            items.extend(self._scrape_euraxess(ctx))
            self._polite_sleep(2.0)
            items.extend(self._scrape_academic_transfer(ctx))
            self._polite_sleep(2.0)
            items.extend(self._scrape_academic_positions(ctx))
            self._polite_sleep(2.0)
            items.extend(self._scrape_findaphd(ctx))

        return self._cap(self._dedup(items))

    def _scrape_nature_rss(self) -> list[dict]:
        entries = self._fetch_rss(
            "https://www.nature.com/naturecareers/rss/jobs?type=postdoc"
        )
        items = []
        for e in entries:
            if not e["link"] or not e["title"]:
                continue
            items.append(self._build_item(
                title=clean_text(e["title"], 512),
                description=clean_text(e["summary"], 1000),
                url=e["link"],
                type=OpportunityType.POSTDOC,
                domain=OpportunityDomain.AI,
                level=OpportunityLevel.POSTDOC,
                location_type=OpportunityLocationType.UNKNOWN,
                tags=["postdoc", "research", "nature-careers"],
                source="nature_careers_rss",
                scraper_type="static",
            ))
        logger.info("Nature RSS postdocs: %d", len(items))
        return items

    def _scrape_euraxess(self, ctx) -> list[dict]:
        pages = [
            "https://euraxess.ec.europa.eu/jobs/search?q=postdoc+artificial+intelligence",
            "https://euraxess.ec.europa.eu/jobs/search?q=postdoctoral+machine+learning",
            "https://euraxess.ec.europa.eu/jobs/search?q=postdoc+deep+learning+data+science",
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
                        type=OpportunityType.POSTDOC,
                        domain=OpportunityDomain.AI,
                        level=OpportunityLevel.POSTDOC,
                        country=clean_text(country_el.text, 100) if country_el else None,
                        location_type=OpportunityLocationType.ONSITE,
                        tags=["postdoc", "research", "europe", "euraxess", "ai"],
                    ))
                except Exception as exc:
                    logger.debug("Euraxess postdoc error: %s", exc)
            self._polite_sleep(1.5)
        logger.info("Euraxess postdocs: %d", len(items))
        return items

    def _scrape_academic_transfer(self, ctx) -> list[dict]:
        url = "https://www.academictransfer.com/en/jobs/?q=postdoc+artificial+intelligence+machine+learning"
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
                    type=OpportunityType.POSTDOC,
                    domain=OpportunityDomain.AI,
                    level=OpportunityLevel.POSTDOC,
                    country=clean_text(country_el.text, 100) if country_el else "Netherlands",
                    location_type=OpportunityLocationType.ONSITE,
                    tags=["postdoc", "netherlands", "academic", "ai"],
                ))
            except Exception as exc:
                logger.debug("AcademicTransfer postdoc error: %s", exc)
        logger.info("AcademicTransfer postdocs: %d", len(items))
        return items

    def _scrape_academic_positions(self, ctx) -> list[dict]:
        url = "https://academicpositions.com/jobs?keywords=postdoc+AI+machine+learning&type=postdoc"
        soup = self._fetch_page(ctx, url,
            wait_selector="article.job, div.job-item, ul.jobs-list",
            extra_wait_ms=2500, scroll=True)
        if not soup:
            return []
        items = []
        for card in soup.select("article.job, div.job-item, li.job"):
            try:
                title_el = card.select_one("h2 a, h3 a, .job-title a")
                org_el = card.select_one(".employer, .university, .institution")
                country_el = card.select_one(".country, .location, .job-location")
                if not title_el:
                    continue
                href = title_el.get("href", "")
                full_url = href if href.startswith("http") else f"https://academicpositions.com{href}"
                items.append(self._build_item(
                    title=clean_text(title_el.text, 512),
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
        logger.info("Academic Positions postdocs: %d", len(items))
        return items

    def _scrape_findaphd(self, ctx) -> list[dict]:
        url = "https://www.findaphd.com/phds/non-phd-positions/?Keywords=postdoc+artificial+intelligence"
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
                    type=OpportunityType.POSTDOC,
                    domain=OpportunityDomain.AI,
                    level=OpportunityLevel.POSTDOC,
                    location_type=OpportunityLocationType.ONSITE,
                    tags=["postdoc", "findaphd", "ai", "research"],
                ))
            except Exception as exc:
                logger.debug("FindAPhD postdoc error: %s", exc)
        logger.info("FindAPhD postdocs: %d", len(items))
        return items