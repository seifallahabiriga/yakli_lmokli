from __future__ import annotations

import logging

from backend.core.enums import OpportunityDomain, OpportunityLevel, OpportunityLocationType, OpportunityType
from backend.workers.worker_app.scrapers.base_scraper import BaseScraper
from backend.workers.worker_app.utils import clean_text

logger = logging.getLogger(__name__)


class InternshipScraper(BaseScraper):

    SOURCE_NAME = "internship_scraper"
    DEFAULT_SCRAPER_TYPE = "dynamic"

    def run(self) -> list[dict]:
        items: list[dict] = []

        with self._browser() as ctx:
            items.extend(self._scrape_linkedin(ctx))
            self._polite_sleep(3.0)
            items.extend(self._scrape_euraxess(ctx))
            self._polite_sleep(2.0)
            items.extend(self._scrape_indeed(ctx))

        return self._cap(self._dedup(items))

    # ------------------------------------------------------------------

    def _scrape_linkedin(self, ctx) -> list[dict]:
        url = (
            "https://www.linkedin.com/jobs/search/"
            "?keywords=AI+data+science+internship&f_E=1&f_JT=I"
        )
        soup = self._fetch_page(
            ctx, url,
            wait_selector="ul.jobs-search__results-list, div.job-search-card",
            scroll=True,
        )
        if soup is None:
            return []

        items = []
        for card in soup.select("div.job-search-card, li.jobs-search-results__list-item"):
            try:
                title_el = card.select_one(
                    "h3.base-search-card__title, "
                    "h3.job-card-list__title, "
                    "a.base-card__full-link"
                )
                org_el = card.select_one(
                    "h4.base-search-card__subtitle, "
                    "span.job-card-container__company-name"
                )
                loc_el = card.select_one(
                    "span.job-search-card__location, "
                    "span.job-card-container__metadata-item"
                )
                link_el = card.select_one("a.base-card__full-link, a[href*='/jobs/view/']")
                if not title_el or not link_el:
                    continue

                raw_url = link_el.get("href", "").split("?")[0]
                if not raw_url.startswith("http"):
                    continue

                location_text = loc_el.text.strip() if loc_el else ""
                loc_type = (
                    OpportunityLocationType.REMOTE
                    if "remote" in location_text.lower()
                    else OpportunityLocationType.ONSITE
                )

                items.append(self._build_item(
                    title=clean_text(title_el.text, 512),
                    organization=clean_text(org_el.text, 255) if org_el else None,
                    url=raw_url,
                    type=OpportunityType.INTERNSHIP,
                    domain=OpportunityDomain.AI,
                    level=OpportunityLevel.MASTER,
                    location=location_text,
                    location_type=loc_type,
                    tags=["internship", "ai", "data-science", "linkedin"],
                ))
            except Exception as exc:
                logger.debug("LinkedIn card error: %s", exc)

        logger.info("LinkedIn internships: %d found", len(items))
        return items

    def _scrape_euraxess(self, ctx) -> list[dict]:
        url = "https://euraxess.ec.europa.eu/jobs/search?q=internship+artificial+intelligence&f%5B0%5D=type%3Ajobs"
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
                    type=OpportunityType.INTERNSHIP,
                    domain=OpportunityDomain.AI,
                    level=OpportunityLevel.MASTER,
                    country=clean_text(country_el.text, 100) if country_el else None,
                    location_type=OpportunityLocationType.ONSITE,
                    tags=["internship", "research", "europe", "euraxess"],
                ))
            except Exception as exc:
                logger.debug("Euraxess internship error: %s", exc)

        logger.info("Euraxess internships: %d found", len(items))
        return items

    def _scrape_indeed(self, ctx) -> list[dict]:
        url = "https://www.indeed.com/jobs?q=AI+data+science+internship&jt=internship"
        soup = self._fetch_page(
            ctx, url,
            wait_selector="div.job_seen_beacon, td.resultContent",
            extra_wait_ms=2000,
            scroll=True,
        )
        if soup is None:
            return []

        items = []
        for card in soup.select("div.job_seen_beacon, div.jobsearch-ResultsList > li"):
            try:
                title_el = card.select_one("h2.jobTitle a, a.jcs-JobTitle")
                org_el = card.select_one("span.companyName, [data-testid='company-name']")
                loc_el = card.select_one("div.companyLocation, [data-testid='text-location']")
                if not title_el:
                    continue
                href = title_el.get("href", "")
                full_url = href if href.startswith("http") else f"https://www.indeed.com{href}"

                location_text = loc_el.text.strip() if loc_el else ""
                loc_type = (
                    OpportunityLocationType.REMOTE
                    if "remote" in location_text.lower()
                    else OpportunityLocationType.ONSITE
                )

                items.append(self._build_item(
                    title=clean_text(title_el.text, 512),
                    organization=clean_text(org_el.text, 255) if org_el else None,
                    url=full_url,
                    type=OpportunityType.INTERNSHIP,
                    domain=OpportunityDomain.AI,
                    level=OpportunityLevel.BACHELOR,
                    location=location_text,
                    location_type=loc_type,
                    tags=["internship", "ai", "indeed"],
                ))
            except Exception as exc:
                logger.debug("Indeed card error: %s", exc)

        logger.info("Indeed internships: %d found", len(items))
        return items