from __future__ import annotations

import logging

from backend.core.enums import OpportunityDomain, OpportunityLevel, OpportunityLocationType, OpportunityType
from backend.workers.worker_app.scrapers.base_scraper import BaseScraper
from backend.workers.worker_app.utils import clean_text

logger = logging.getLogger(__name__)


class ScholarshipScraper(BaseScraper):

    SOURCE_NAME = "scholarship_scraper"
    DEFAULT_SCRAPER_TYPE = "dynamic"

    def run(self) -> list[dict]:
        items: list[dict] = []

        with self._browser() as ctx:
            items.extend(self._scrape_scholars4dev(ctx))
            self._polite_sleep(2.0)
            items.extend(self._scrape_euraxess_fellowships(ctx))
            self._polite_sleep(2.0)
            items.extend(self._scrape_findaphd(ctx))

        return self._cap(self._dedup(items))

    # ------------------------------------------------------------------

    def _scrape_scholars4dev(self, ctx) -> list[dict]:
        url = "https://www.scholars4dev.com/category/scholarships-by-field/science-technology-scholarships/"
        soup = self._fetch_page(
            ctx, url,
            wait_selector="article, div.post",
            extra_wait_ms=1500,
        )
        if soup is None:
            return []

        items = []
        for article in soup.select("article, div.post, h2.entry-title"):
            try:
                title_el = article.select_one("h2 a, h1 a, .entry-title a")
                excerpt_el = article.select_one(".entry-summary, .excerpt, p")
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
                    tags=["scholarship", "stem", "funding"],
                ))
            except Exception as exc:
                logger.debug("scholars4dev error: %s", exc)

        logger.info("scholars4dev scholarships: %d found", len(items))
        return items

    def _scrape_euraxess_fellowships(self, ctx) -> list[dict]:
        url = "https://euraxess.ec.europa.eu/jobs/search?q=fellowship+scholarship+data+science+AI"
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
                org_el = card.select_one(".organisation, .institution")
                country_el = card.select_one(".country, .location")
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
                    tags=["fellowship", "research", "europe"],
                ))
            except Exception as exc:
                logger.debug("Euraxess fellowship error: %s", exc)

        logger.info("Euraxess fellowships: %d found", len(items))
        return items

    def _scrape_findaphd(self, ctx) -> list[dict]:
        url = "https://www.findaphd.com/phds/scholarship/?Keywords=artificial+intelligence+machine+learning"
        soup = self._fetch_page(
            ctx, url,
            wait_selector="div.phd-result, article.result",
            extra_wait_ms=2000,
            scroll=True,
        )
        if soup is None:
            return []

        items = []
        for card in soup.select("div.phd-result, article.result, div.g-mb-20"):
            try:
                title_el = card.select_one("h3 a, h2 a, .title a, a.h4")
                org_el = card.select_one(".institution, .uni-link, .phd-result__dept")
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
                    tags=["phd", "scholarship", "ai", "machine-learning"],
                ))
            except Exception as exc:
                logger.debug("findaphd error: %s", exc)

        logger.info("findaphd scholarships: %d found", len(items))
        return items