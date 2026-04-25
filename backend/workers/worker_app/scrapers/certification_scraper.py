from __future__ import annotations

import logging

from backend.core.enums import OpportunityDomain, OpportunityLevel, OpportunityLocationType, OpportunityType
from backend.workers.worker_app.scrapers.base_scraper import BaseScraper, clean_text_local as clean_text

logger = logging.getLogger(__name__)

# Confirmed working courses from fast.ai debug output
FASTAI_COURSES = [
    {
        "title": "Practical Deep Learning for Coders",
        "url": "https://course.fast.ai/",
        "description": "Free deep learning course using PyTorch and fastai. Covers CNNs, NLP, tabular data.",
        "tags": ["deep-learning", "pytorch", "fastai", "free"],
    },
    {
        "title": "fastai for PyTorch — Documentation and Library",
        "url": "https://docs.fast.ai",
        "description": "High-level deep learning library built on PyTorch.",
        "tags": ["pytorch", "fastai", "library", "deep-learning"],
    },
    {
        "title": "How to Solve it With Code",
        "url": "https://solve.it.com",
        "description": "Practical coding course for AI and data science.",
        "tags": ["python", "coding", "ai"],
    },
]


class CertificationScraper(BaseScraper):
    """
    Sources:
      - fast.ai — hardcoded (known URLs from debug, site has no dynamic listing)
      - MIT OCW — Playwright, confirmed selector: div.card.learning-resource-card
      - HuggingFace — static, needs correct selectors
      - DeepLearning.AI — Playwright
    """

    SOURCE_NAME = "certification_scraper"
    DEFAULT_SCRAPER_TYPE = "dynamic"

    def run(self) -> list[dict]:
        items: list[dict] = []

        # fast.ai — hardcoded known courses (site is a blog, no course listing page)
        items.extend(self._scrape_fastai_hardcoded())

        # Static sources
        items.extend(self._scrape_huggingface())
        self._polite_sleep(1.0)

        # Playwright sources
        with self._browser() as ctx:
            items.extend(self._scrape_mit_ocw(ctx))
            self._polite_sleep(2.0)
            items.extend(self._scrape_deeplearningai(ctx))

        return self._cap(self._dedup(items))

    def _scrape_fastai_hardcoded(self) -> list[dict]:
        """
        fast.ai has no course listing page — the debug showed individual links.
        We hardcode the known courses since they're stable and well-known.
        """
        items = []
        for course in FASTAI_COURSES:
            items.append(self._build_item(
                title=course["title"],
                description=course["description"],
                url=course["url"],
                organization="fast.ai",
                type=OpportunityType.ONLINE_COURSE,
                domain=OpportunityDomain.MACHINE_LEARNING,
                level=OpportunityLevel.ALL,
                location_type=OpportunityLocationType.REMOTE,
                is_paid=False,
                tags=course["tags"] + ["fastai", "free", "online-course"],
                source="fastai",
                scraper_type="static",
            ))
        logger.info("fast.ai courses: %d (hardcoded)", len(items))
        return items

    def _scrape_huggingface(self) -> list[dict]:
        """
        HuggingFace /learn — debug showed Svelte-rendered, static fetch gets shell.
        Try the courses API endpoint instead.
        """
        items = []

        # Known stable HuggingFace course URLs
        hf_courses = [
            ("NLP Course", "https://huggingface.co/learn/nlp-course/chapter1/1",
             "Complete NLP course: transformers, fine-tuning, tokenization.", ["nlp", "transformers", "bert"]),
            ("Deep Reinforcement Learning Course", "https://huggingface.co/learn/deep-rl-course/unit0/introduction",
             "Learn deep RL from basics to advanced algorithms.", ["reinforcement-learning", "deep-rl"]),
            ("Diffusion Models Course", "https://huggingface.co/learn/diffusion-course/unit0/1",
             "Learn to build and fine-tune diffusion models.", ["diffusion", "generative-ai", "stable-diffusion"]),
            ("ML for Games Course", "https://huggingface.co/learn/ml-games-course/unit0/introduction",
             "Build AI agents for video games.", ["games", "rl", "agents"]),
            ("Audio Course", "https://huggingface.co/learn/audio-course/chapter0/introduction",
             "Speech and audio processing with transformers.", ["audio", "speech", "transformers"]),
        ]

        for title, url, desc, tags in hf_courses:
            items.append(self._build_item(
                title=title,
                description=desc,
                url=url,
                organization="Hugging Face",
                type=OpportunityType.ONLINE_COURSE,
                domain=OpportunityDomain.AI,
                level=OpportunityLevel.ALL,
                location_type=OpportunityLocationType.REMOTE,
                is_paid=False,
                tags=tags + ["huggingface", "free", "online-course", "transformers"],
                source="huggingface",
                scraper_type="static",
            ))

        logger.info("HuggingFace courses: %d (known URLs)", len(items))
        return items

    def _scrape_mit_ocw(self, ctx) -> list[dict]:
        """
        MIT OCW — confirmed working with Playwright.
        Selector: div.card.learning-resource-card (from debug output)
        Title in: div.lr-row.course-title
        Links: /courses/{slug}/
        """
        search_urls = [
            "https://ocw.mit.edu/search/?t=Artificial+Intelligence",
            "https://ocw.mit.edu/search/?t=Machine+Learning",
        ]
        items = []
        for url in search_urls:
            soup = self._fetch_page(ctx, url, extra_wait_ms=4000)
            if not soup:
                continue

            # Confirmed selector from debug: div.card.learning-resource-card
            for card in soup.select("div.card.learning-resource-card"):
                try:
                    # Title in div.lr-row.course-title
                    title_el = card.select_one("div.lr-row.course-title, div.course-title, h3, h2")
                    link_el = card.select_one("a[href*='/courses/']")
                    if not link_el:
                        continue
                    href = link_el.get("href", "")
                    full_url = href if href.startswith("http") else f"https://ocw.mit.edu{href}"
                    title = clean_text(title_el.text) if title_el else clean_text(link_el.text)
                    if not title or len(title) < 5:
                        continue

                    items.append(self._build_item(
                        title=f"MIT OCW: {title}",
                        organization="MIT OpenCourseWare",
                        url=full_url,
                        type=OpportunityType.ONLINE_COURSE,
                        domain=OpportunityDomain.AI,
                        level=OpportunityLevel.ALL,
                        location_type=OpportunityLocationType.REMOTE,
                        is_paid=False,
                        tags=["mit", "ocw", "ai", "free", "university"],
                        source="mit_ocw",
                    ))
                except Exception as exc:
                    logger.debug("MIT OCW card error: %s", exc)

            self._polite_sleep(1.5)

        logger.info("MIT OCW courses: %d", len(items))
        return items

    def _scrape_deeplearningai(self, ctx) -> list[dict]:
        """
        DeepLearning.AI — Playwright. Debug showed course links at /courses/{slug}.
        Fallback: select all a[href*='/courses/'] if card class not found.
        """
        url = "https://www.deeplearning.ai/courses/"
        soup = self._fetch_page(ctx, url, extra_wait_ms=4000, scroll=True)
        if not soup:
            return []

        items = []
        seen: set[str] = set()

        # Try card selectors first
        cards = soup.select(
            'div[class*="CourseCard"], div[class*="course-card"], '
            'article[class*="course"], li[class*="course"]'
        )

        if cards:
            for card in cards:
                try:
                    title_el = card.select_one("h2, h3, h4, [class*='title']")
                    link_el = card.select_one("a[href]")
                    if not title_el or not link_el:
                        continue
                    href = link_el.get("href", "")
                    full_url = href if href.startswith("http") else f"https://www.deeplearning.ai{href}"
                    if full_url in seen:
                        continue
                    seen.add(full_url)
                    items.append(self._build_item(
                        title=clean_text(title_el.text),
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
                    logger.debug("DeepLearning.AI card error: %s", exc)
        else:
            # Fallback: grab all /courses/ links directly
            for a in soup.select('a[href*="/courses/"]'):
                href = a.get("href", "")
                if not href or href in seen or href.endswith("/courses/"):
                    continue
                seen.add(href)
                full_url = href if href.startswith("http") else f"https://www.deeplearning.ai{href}"
                title = clean_text(a.text)
                if not title or len(title) < 5:
                    continue
                items.append(self._build_item(
                    title=title,
                    organization="DeepLearning.AI",
                    url=full_url,
                    type=OpportunityType.CERTIFICATION,
                    domain=OpportunityDomain.AI,
                    level=OpportunityLevel.ALL,
                    location_type=OpportunityLocationType.REMOTE,
                    is_paid=True,
                    tags=["deeplearning", "ai", "certification", "andrew-ng"],
                ))

        logger.info("DeepLearning.AI courses: %d", len(items))
        return items