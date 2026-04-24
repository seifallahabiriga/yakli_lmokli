from __future__ import annotations

import logging

from backend.core.enums import OpportunityDomain, OpportunityLevel, OpportunityLocationType, OpportunityType
from backend.workers.worker_app.scrapers.base_scraper import BaseScraper
from backend.workers.worker_app.utils import clean_text

logger = logging.getLogger(__name__)


class CertificationScraper(BaseScraper):
    """
    Sources:
      - DeepLearning.AI (Playwright — relatively scraper-friendly)
      - fast.ai (static — open course listings)
      - MIT OpenCourseWare (static)
      - Hugging Face courses (static)

    Removed: Coursera, edX — heavy bot detection, returns empty shells.
    """

    SOURCE_NAME = "certification_scraper"
    DEFAULT_SCRAPER_TYPE = "dynamic"

    def run(self) -> list[dict]:
        items: list[dict] = []

        # Tier 1 — static
        items.extend(self._scrape_fastai())
        self._polite_sleep(1.0)
        items.extend(self._scrape_huggingface())
        self._polite_sleep(1.0)
        items.extend(self._scrape_mit_ocw())
        self._polite_sleep(1.0)

        # Tier 2 — Playwright
        with self._browser() as ctx:
            items.extend(self._scrape_deeplearningai(ctx))

        return self._cap(self._dedup(items))

    def _scrape_fastai(self) -> list[dict]:
        """fast.ai — free deep learning courses, fully static HTML."""
        soup = self._fetch_static("https://www.fast.ai/")
        if not soup:
            return []
        items = []
        for card in soup.select("div.course, article, div.post-preview"):
            try:
                title_el = card.select_one("h2 a, h3 a, h1 a")
                link_el = card.select_one("a[href]")
                if not title_el or not link_el:
                    continue
                href = link_el.get("href", "")
                full_url = href if href.startswith("http") else f"https://www.fast.ai{href}"
                items.append(self._build_item(
                    title=clean_text(title_el.text, 512),
                    organization="fast.ai",
                    url=full_url,
                    type=OpportunityType.ONLINE_COURSE,
                    domain=OpportunityDomain.MACHINE_LEARNING,
                    level=OpportunityLevel.ALL,
                    location_type=OpportunityLocationType.REMOTE,
                    is_paid=False,
                    tags=["deep-learning", "fastai", "free", "online-course"],
                    source="fastai",
                    scraper_type="static",
                ))
            except Exception as exc:
                logger.debug("fast.ai error: %s", exc)
        logger.info("fast.ai courses: %d", len(items))
        return items

    def _scrape_huggingface(self) -> list[dict]:
        """Hugging Face course listings — static page."""
        soup = self._fetch_static("https://huggingface.co/learn")
        if not soup:
            return []
        items = []
        for card in soup.select("div.course-card, article, div[class*='course']"):
            try:
                title_el = card.select_one("h2, h3, h4")
                link_el = card.select_one("a[href]")
                if not title_el or not link_el:
                    continue
                href = link_el.get("href", "")
                full_url = href if href.startswith("http") else f"https://huggingface.co{href}"
                items.append(self._build_item(
                    title=clean_text(title_el.text, 512),
                    organization="Hugging Face",
                    url=full_url,
                    type=OpportunityType.ONLINE_COURSE,
                    domain=OpportunityDomain.NLP,
                    level=OpportunityLevel.ALL,
                    location_type=OpportunityLocationType.REMOTE,
                    is_paid=False,
                    tags=["nlp", "transformers", "huggingface", "free", "online-course"],
                    source="huggingface",
                    scraper_type="static",
                ))
            except Exception as exc:
                logger.debug("HuggingFace error: %s", exc)
        logger.info("HuggingFace courses: %d", len(items))
        return items

    def _scrape_mit_ocw(self) -> list[dict]:
        """MIT OpenCourseWare AI/ML courses — static HTML."""
        urls = [
            "https://ocw.mit.edu/search/?t=Artificial+Intelligence",
            "https://ocw.mit.edu/search/?t=Machine+Learning",
        ]
        items = []
        for url in urls:
            soup = self._fetch_static(url)
            if not soup:
                continue
            for card in soup.select("div.course-card, div.lr-tile, li.course-result"):
                try:
                    title_el = card.select_one("h2 a, h3 a, .lr-tile--title a, a")
                    if not title_el:
                        continue
                    href = title_el.get("href", "")
                    full_url = href if href.startswith("http") else f"https://ocw.mit.edu{href}"
                    items.append(self._build_item(
                        title=clean_text(title_el.text, 512),
                        organization="MIT OpenCourseWare",
                        url=full_url,
                        type=OpportunityType.ONLINE_COURSE,
                        domain=OpportunityDomain.AI,
                        level=OpportunityLevel.ALL,
                        location_type=OpportunityLocationType.REMOTE,
                        is_paid=False,
                        tags=["mit", "ocw", "ai", "free", "certification"],
                        source="mit_ocw",
                        scraper_type="static",
                    ))
                except Exception as exc:
                    logger.debug("MIT OCW error: %s", exc)
            self._polite_sleep(1.0)
        logger.info("MIT OCW courses: %d", len(items))
        return items

    def _scrape_deeplearningai(self, ctx) -> list[dict]:
        """DeepLearning.AI course list — Playwright needed for React-rendered content."""
        url = "https://www.deeplearning.ai/courses/"
        soup = self._fetch_page(ctx, url,
            wait_selector="div[class*='course'], article, section",
            extra_wait_ms=3000, scroll=True)
        if not soup:
            return []
        items = []
        for card in soup.select(
            "div[class*='CourseCard'], div[class*='course-card'], "
            "article[class*='course'], li[class*='course']"
        ):
            try:
                title_el = card.select_one("h2, h3, h4, [class*='title']")
                link_el = card.select_one("a[href]")
                if not title_el or not link_el:
                    continue
                href = link_el.get("href", "")
                full_url = href if href.startswith("http") else f"https://www.deeplearning.ai{href}"
                items.append(self._build_item(
                    title=clean_text(title_el.text, 512),
                    organization="DeepLearning.AI",
                    url=full_url,
                    type=OpportunityType.CERTIFICATION,
                    domain=OpportunityDomain.AI,
                    level=OpportunityLevel.ALL,
                    location_type=OpportunityLocationType.REMOTE,
                    is_paid=True,
                    tags=["deeplearning", "ai", "certification", "andrew-ng"],
                ))
            except Exception as exc:
                logger.debug("DeepLearning.AI error: %s", exc)
        logger.info("DeepLearning.AI courses: %d", len(items))
        return items