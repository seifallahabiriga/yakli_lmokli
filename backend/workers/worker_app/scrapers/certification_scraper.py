from __future__ import annotations

import logging

from backend.core.enums import OpportunityDomain, OpportunityLevel, OpportunityLocationType, OpportunityType
from backend.workers.worker_app.scrapers.base_scraper import BaseScraper
from backend.workers.worker_app.utils import clean_text

logger = logging.getLogger(__name__)


class CertificationScraper(BaseScraper):

    SOURCE_NAME = "certification_scraper"
    DEFAULT_SCRAPER_TYPE = "dynamic"

    def run(self) -> list[dict]:
        items: list[dict] = []

        with self._browser() as ctx:
            items.extend(self._scrape_coursera(ctx))
            self._polite_sleep(3.0)
            items.extend(self._scrape_edx(ctx))
            self._polite_sleep(3.0)
            items.extend(self._scrape_deeplearningai(ctx))

        return self._cap(self._dedup(items))

    # ------------------------------------------------------------------

    def _scrape_coursera(self, ctx) -> list[dict]:
        url = "https://www.coursera.org/search?query=artificial+intelligence&productTypeDescription=Professional+Certificates&productTypeDescription=Specializations"
        soup = self._fetch_page(
            ctx, url,
            wait_selector="li.cds-ProductCard-base, ul.css-1d5ofe6",
            extra_wait_ms=3000,
            scroll=True,
        )
        if soup is None:
            return []

        items = []
        for card in soup.select(
            "li.cds-ProductCard-base, "
            "div[data-e2e='product-card'], "
            "div.css-0 > a[href*='/learn/'], "
            "div.css-0 > a[href*='/specializations/']"
        ):
            try:
                title_el = card.select_one(
                    "h3.cds-CommonCard-title, "
                    "h2, "
                    "[data-e2e='product-card-title'], "
                    "p.cds-ProductCard-title"
                )
                org_el = card.select_one(
                    "p.cds-ProductCard-partnerNames, "
                    ".partner-name, "
                    "span.cds-CommonCard-metadata"
                )
                link_el = card.select_one("a[href]")
                if not title_el or not link_el:
                    continue
                href = link_el.get("href", "")
                full_url = href if href.startswith("http") else f"https://www.coursera.org{href}"

                items.append(self._build_item(
                    title=clean_text(title_el.text, 512),
                    organization=clean_text(org_el.text, 255) if org_el else "Coursera",
                    url=full_url,
                    type=OpportunityType.CERTIFICATION,
                    domain=OpportunityDomain.AI,
                    level=OpportunityLevel.ALL,
                    location_type=OpportunityLocationType.REMOTE,
                    is_paid=True,
                    tags=["certification", "coursera", "online", "ai"],
                ))
            except Exception as exc:
                logger.debug("Coursera card error: %s", exc)

        logger.info("Coursera certifications: %d found", len(items))
        return items

    def _scrape_edx(self, ctx) -> list[dict]:
        url = "https://www.edx.org/search?q=artificial+intelligence&tab=program&product_types=Professional+Certificate"
        soup = self._fetch_page(
            ctx, url,
            wait_selector="div.discovery-card, div[class*='ProductCard']",
            extra_wait_ms=4000,
            scroll=True,
        )
        if soup is None:
            return []

        items = []
        for card in soup.select(
            "div.discovery-card, "
            "div[class*='ProductCard'], "
            "article[class*='card']"
        ):
            try:
                title_el = card.select_one(
                    "h3 a, h2 a, "
                    ".course-title, "
                    ".program-title, "
                    "p[class*='Title']"
                )
                org_el = card.select_one(".org, .school, .partner, span[class*='Org']")
                link_el = card.select_one("a[href]")
                if not title_el or not link_el:
                    continue
                href = link_el.get("href", "")
                full_url = href if href.startswith("http") else f"https://www.edx.org{href}"

                items.append(self._build_item(
                    title=clean_text(title_el.text, 512),
                    organization=clean_text(org_el.text, 255) if org_el else "edX",
                    url=full_url,
                    type=OpportunityType.CERTIFICATION,
                    domain=OpportunityDomain.AI,
                    level=OpportunityLevel.ALL,
                    location_type=OpportunityLocationType.REMOTE,
                    is_paid=True,
                    tags=["certification", "edx", "online", "ai"],
                ))
            except Exception as exc:
                logger.debug("edX card error: %s", exc)

        logger.info("edX certifications: %d found", len(items))
        return items

    def _scrape_deeplearningai(self, ctx) -> list[dict]:
        """DeepLearning.AI courses — static HTML, but uses _fetch_page for consistency."""
        url = "https://www.deeplearning.ai/courses/"
        soup = self._fetch_page(
            ctx, url,
            wait_selector="div.course-card, article, div[class*='course']",
            extra_wait_ms=2000,
        )
        if soup is None:
            return []

        items = []
        for card in soup.select(
            "div.course-card, "
            "article.course, "
            "div[class*='CourseCard'], "
            "li[class*='course']"
        ):
            try:
                title_el = card.select_one("h3, h2, h4, [class*='title']")
                link_el = card.select_one("a[href]")
                if not title_el or not link_el:
                    continue
                href = link_el.get("href", "")
                full_url = href if href.startswith("http") else f"https://www.deeplearning.ai{href}"

                items.append(self._build_item(
                    title=clean_text(title_el.text, 512),
                    organization="DeepLearning.AI",
                    url=full_url,
                    type=OpportunityType.ONLINE_COURSE,
                    domain=OpportunityDomain.AI,
                    level=OpportunityLevel.ALL,
                    location_type=OpportunityLocationType.REMOTE,
                    is_paid=True,
                    tags=["deeplearning", "ai", "online-course", "coursera"],
                ))
            except Exception as exc:
                logger.debug("DeepLearning.AI card error: %s", exc)

        logger.info("DeepLearning.AI courses: %d found", len(items))
        return items