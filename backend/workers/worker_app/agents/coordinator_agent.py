import logging
from backend.core.enums import OpportunityStatus, OpportunityType, ScraperType
from backend.models.opportunity import Opportunity
from backend.workers.worker_app.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

class CoordinatorAgent(BaseAgent):
    def run_scraper(self, agent_type: str) -> dict:
        agent_map = {
            "internship": self._scrape_internships,
            "scholarship": self._scrape_scholarships,
            "project": self._scrape_projects,
            "certification": self._scrape_certifications,
            "postdoc": self._scrape_postdocs,
        }

        scrape_fn = agent_map.get(agent_type)
        if scrape_fn is None:
            raise ValueError(f"Unknown agent type: {agent_type}")

        logger.info(f"Scraper agent starting: {agent_type}")
        raw_items = scrape_fn()
        logger.info(f"Scraper agent {agent_type} collected {len(raw_items)} raw items")

        inserted = 0
        skipped = 0

        for item in raw_items:
            url = item.get("url", "").strip()
            if not url:
                skipped += 1
                continue

            existing = self.db.execute(
                __import__("sqlalchemy").select(Opportunity.id).where(
                    Opportunity.url == url
                )
            ).scalar_one_or_none()

            if existing is not None:
                skipped += 1
                continue

            opportunity = Opportunity(
                title=item.get("title", "Untitled")[:512],
                description=item.get("description"),
                organization=item.get("organization"),
                source=item.get("source", agent_type),
                url=url,
                type=item.get("type", OpportunityType.INTERNSHIP),
                domain=item.get("domain", "other"),
                level=item.get("level", "all"),
                location_type=item.get("location_type", "unknown"),
                location=item.get("location"),
                country=item.get("country"),
                eligibility=item.get("eligibility", {}),
                required_skills=item.get("required_skills", []),
                tags=item.get("tags", []),
                deadline=item.get("deadline"),
                start_date=item.get("start_date"),
                duration_months=item.get("duration_months"),
                is_paid=item.get("is_paid"),
                stipend_amount=item.get("stipend_amount"),
                stipend_currency=item.get("stipend_currency"),
                status=OpportunityStatus.DRAFT,
                scraper_type=item.get("scraper_type", ScraperType.STATIC),
                raw_data=item,
            )
            self.db.add(opportunity)
            inserted += 1

        logger.info(f"Scraper agent {agent_type} done — inserted: {inserted}, skipped: {skipped}")
        return {"agent": agent_type, "inserted": inserted, "skipped": skipped}

    def _scrape_internships(self) -> list[dict]:
        from backend.workers.worker_app.scrapers.internship_scraper import InternshipScraper
        return InternshipScraper().run()

    def _scrape_scholarships(self) -> list[dict]:
        from backend.workers.worker_app.scrapers.scholarship_scraper import ScholarshipScraper
        return ScholarshipScraper().run()

    def _scrape_projects(self) -> list[dict]:
        from backend.workers.worker_app.scrapers.project_scraper import ProjectScraper
        return ProjectScraper().run()

    def _scrape_certifications(self) -> list[dict]:
        from backend.workers.worker_app.scrapers.certification_scraper import CertificationScraper
        return CertificationScraper().run()

    def _scrape_postdocs(self) -> list[dict]:
        from backend.workers.worker_app.scrapers.postdoc_scraper import PostdocScraper
        return PostdocScraper().run()
