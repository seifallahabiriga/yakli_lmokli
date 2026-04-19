from __future__ import annotations

import logging

from backend.core.enums import OpportunityDomain, OpportunityLevel, OpportunityLocationType, OpportunityType
from backend.workers.worker_app.scrapers.base_scraper import BaseScraper
from backend.workers.worker_app.utils import clean_text

logger = logging.getLogger(__name__)


class ProjectScraper(BaseScraper):

    SOURCE_NAME = "project_scraper"
    DEFAULT_SCRAPER_TYPE = "dynamic"

    def run(self) -> list[dict]:
        items: list[dict] = []

        with self._browser() as ctx:
            items.extend(self._scrape_euraxess(ctx))
            self._polite_sleep(2.0)
            items.extend(self._scrape_nature_careers(ctx))
            self._polite_sleep(2.0)
            items.extend(self._scrape_h2020(ctx))

        return self._cap(self._dedup(items))

    # ------------------------------------------------------------------

    def _scrape_euraxess(self, ctx) -> list[dict]:
        url = "https://euraxess.ec.europa.eu/jobs/search?q=research+project+artificial+intelligence+machine+learning"
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
                    type=OpportunityType.RESEARCH_PROJECT,
                    domain=OpportunityDomain.AI,
                    level=OpportunityLevel.PHD,
                    country=clean_text(country_el.text, 100) if country_el else None,
                    location_type=OpportunityLocationType.ONSITE,
                    tags=["research", "project", "europe", "ai"],
                ))
            except Exception as exc:
                logger.debug("Euraxess project error: %s", exc)

        logger.info("Euraxess projects: %d found", len(items))
        return items

    def _scrape_nature_careers(self, ctx) -> list[dict]:
        url = "https://www.nature.com/naturecareers/jobs#q=AI%20machine%20learning%20research&p=1"
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
                org_el = card.select_one(".c-card__institution, .employer, .c-card__section")
                if not title_el:
                    continue
                href = title_el.get("href", "")
                full_url = href if href.startswith("http") else f"https://www.nature.com{href}"

                items.append(self._build_item(
                    title=clean_text(title_el.text, 512),
                    organization=clean_text(org_el.text, 255) if org_el else None,
                    url=full_url,
                    type=OpportunityType.RESEARCH_PROJECT,
                    domain=OpportunityDomain.AI,
                    level=OpportunityLevel.PHD,
                    location_type=OpportunityLocationType.UNKNOWN,
                    tags=["research", "nature-careers", "ai"],
                ))
            except Exception as exc:
                logger.debug("Nature careers project error: %s", exc)

        logger.info("Nature Careers projects: %d found", len(items))
        return items

    def _scrape_h2020(self, ctx) -> list[dict]:
        """Scrapes open research calls from the EU Funding & Tenders portal."""
        url = "https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/topic-search;callCode=null;freeTextSearchKeyword=artificial+intelligence"
        soup = self._fetch_page(
            ctx, url,
            wait_selector="eui-card, .eui-u-mt-m",
            wait_state="networkidle",
            extra_wait_ms=4000,
        )
        if soup is None:
            return []

        items = []
        for card in soup.select("eui-card, div.card-container, div.topic-item"):
            try:
                title_el = card.select_one("h3, h2, .topic-title, strong")
                link_el = card.select_one("a[href]")
                if not title_el or not link_el:
                    continue
                href = link_el.get("href", "")
                full_url = href if href.startswith("http") else f"https://ec.europa.eu{href}"

                items.append(self._build_item(
                    title=clean_text(title_el.text, 512),
                    organization="European Commission",
                    url=full_url,
                    type=OpportunityType.RESEARCH_PROJECT,
                    domain=OpportunityDomain.AI,
                    level=OpportunityLevel.PHD,
                    location_type=OpportunityLocationType.ONSITE,
                    tags=["eu-funding", "horizon", "research", "ai"],
                ))
            except Exception as exc:
                logger.debug("H2020 portal error: %s", exc)

        logger.info("EU Funding portal: %d found", len(items))
        return items