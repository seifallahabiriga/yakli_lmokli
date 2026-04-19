from __future__ import annotations

import logging

from backend.core.enums import OpportunityDomain, OpportunityLevel, OpportunityLocationType, OpportunityType
from backend.workers.worker_app.scrapers.base_scraper import BaseScraper
from backend.workers.worker_app.utils import clean_text

logger = logging.getLogger(__name__)


class PostdocScraper(BaseScraper):

    SOURCE_NAME = "postdoc_scraper"
    DEFAULT_SCRAPER_TYPE = "dynamic"

    def run(self) -> list[dict]:
        items: list[dict] = []

        with self._browser() as ctx:
            items.extend(self._scrape_euraxess(ctx))
            self._polite_sleep(2.0)
            items.extend(self._scrape_nature_careers(ctx))
            self._polite_sleep(2.0)
            items.extend(self._scrape_academicpositions(ctx))
            self._polite_sleep(2.0)
            items.extend(self._scrape_academic_transfer(ctx))

        return self._cap(self._dedup(items))

    # ------------------------------------------------------------------

    def _scrape_euraxess(self, ctx) -> list[dict]:
        url = "https://euraxess.ec.europa.eu/jobs/search?q=postdoc+artificial+intelligence+machine+learning"
        soup = self._fetch_page(
            ctx, url,
            wait_selector="div.views-row, article.job",
            extra_wait_ms=2000,
        )
        if soup is None:
            return []

        items = []
        for card in soup.select("div.views-row, article.job, div.job-item"):
            try:
                title_el = card.select_one("h3 a, h2 a, .job-title a, .views-field-title a")
                org_el = card.select_one(".organisation, .institution, .field-name-field-organisation")
                country_el = card.select_one(".country, .location, .field-name-field-country")
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
                    tags=["postdoc", "research", "europe", "ai"],
                ))
            except Exception as exc:
                logger.debug("Euraxess postdoc error: %s", exc)

        logger.info("Euraxess postdocs: %d found", len(items))
        return items

    def _scrape_nature_careers(self, ctx) -> list[dict]:
        url = "https://www.nature.com/naturecareers/jobs#q=postdoc%20AI%20machine%20learning&p=1"
        soup = self._fetch_page(
            ctx, url,
            wait_selector="article.c-card, ul.c-listing",
            extra_wait_ms=3000,
            scroll=True,
        )
        if soup is None:
            return []

        items = []
        for card in soup.select("article.c-card, li.c-listing__item"):
            try:
                title_el = card.select_one("h3 a, h2 a, .c-card__title a")
                org_el = card.select_one(".c-card__institution, .employer")
                if not title_el:
                    continue
                href = title_el.get("href", "")
                full_url = href if href.startswith("http") else f"https://www.nature.com{href}"

                items.append(self._build_item(
                    title=clean_text(title_el.text, 512),
                    organization=clean_text(org_el.text, 255) if org_el else None,
                    url=full_url,
                    type=OpportunityType.POSTDOC,
                    domain=OpportunityDomain.AI,
                    level=OpportunityLevel.POSTDOC,
                    location_type=OpportunityLocationType.UNKNOWN,
                    tags=["postdoc", "nature-careers", "ai"],
                ))
            except Exception as exc:
                logger.debug("Nature careers postdoc error: %s", exc)

        logger.info("Nature Careers postdocs: %d found", len(items))
        return items

    def _scrape_academicpositions(self, ctx) -> list[dict]:
        url = "https://academicpositions.com/jobs?keywords=postdoc+machine+learning+AI&type=postdoc"
        soup = self._fetch_page(
            ctx, url,
            wait_selector="article.job, div.job-item",
            extra_wait_ms=2500,
            scroll=True,
        )
        if soup is None:
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
                    tags=["postdoc", "academic", "machine-learning"],
                ))
            except Exception as exc:
                logger.debug("academicpositions error: %s", exc)

        logger.info("academicpositions postdocs: %d found", len(items))
        return items

    def _scrape_academic_transfer(self, ctx) -> list[dict]:
        url = "https://www.academictransfer.com/en/jobs/?q=postdoc+artificial+intelligence"
        soup = self._fetch_page(
            ctx, url,
            wait_selector="li.vacancy, article.vacancy, div.vacancy-item",
            extra_wait_ms=2000,
            scroll=True,
        )
        if soup is None:
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
                    country=clean_text(country_el.text, 100) if country_el else None,
                    location_type=OpportunityLocationType.ONSITE,
                    tags=["postdoc", "netherlands", "europe", "ai"],
                ))
            except Exception as exc:
                logger.debug("academictransfer error: %s", exc)

        logger.info("AcademicTransfer postdocs: %d found", len(items))
        return items