from enum import Enum


# =============================================================================
# Opportunity
# =============================================================================

class OpportunityType(str, Enum):
    INTERNSHIP = "internship"
    RESEARCH_PROJECT = "research_project"
    SCHOLARSHIP = "scholarship"
    FELLOWSHIP = "fellowship"
    CERTIFICATION = "certification"
    WEBINAR = "webinar"
    ONLINE_COURSE = "online_course"
    POSTDOC = "postdoc"
    VISITING_PROFESSOR = "visiting_professor"


class OpportunityLevel(str, Enum):
    BACHELOR = "bachelor"
    MASTER = "master"
    PHD = "phd"
    POSTDOC = "postdoc"
    PROFESSOR = "professor"
    ALL = "all"


class OpportunityStatus(str, Enum):
    ACTIVE = "active"           # visible to users, within deadline
    EXPIRED = "expired"         # past deadline
    DRAFT = "draft"             # scraped but not yet validated
    ARCHIVED = "archived"       # manually hidden by admin


class OpportunityDomain(str, Enum):
    AI = "ai"
    DATA_SCIENCE = "data_science"
    MACHINE_LEARNING = "machine_learning"
    COMPUTER_VISION = "computer_vision"
    NLP = "nlp"
    ROBOTICS = "robotics"
    CYBERSECURITY = "cybersecurity"
    SOFTWARE_ENGINEERING = "software_engineering"
    DATA_ENGINEERING = "data_engineering"
    BIOINFORMATICS = "bioinformatics"
    OTHER = "other"


class OpportunityLocationType(str, Enum):
    REMOTE = "remote"
    ONSITE = "onsite"
    HYBRID = "hybrid"
    UNKNOWN = "unknown"


# =============================================================================
# User
# =============================================================================

class UserRole(str, Enum):
    STUDENT = "student"
    RESEARCHER = "researcher"
    ADMIN = "admin"


class AcademicLevel(str, Enum):
    BACHELOR = "bachelor"
    MASTER = "master"
    PHD = "phd"
    POSTDOC = "postdoc"
    PROFESSOR = "professor"


# =============================================================================
# Scraping
# =============================================================================

class ScraperType(str, Enum):
    """Which HTTP strategy an observer agent should use for a given source."""
    STATIC = "static"           # httpx + BeautifulSoup
    DYNAMIC = "dynamic"         # Playwright (JS-rendered pages)


class ScraperStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    RATE_LIMITED = "rate_limited"


# =============================================================================
# Recommendation
# =============================================================================

class RecommendationStatus(str, Enum):
    PENDING = "pending"         # queued for scoring
    SCORED = "scored"           # score computed, available to user
    DISMISSED = "dismissed"     # user explicitly dismissed it
    APPLIED = "applied"         # user marked as applied


# =============================================================================
# Notification
# =============================================================================

class NotificationStatus(str, Enum):
    UNREAD = "unread"
    READ = "read"
    ARCHIVED = "archived"


class NotificationType(str, Enum):
    NEW_OPPORTUNITY = "new_opportunity"
    DEADLINE_REMINDER = "deadline_reminder"
    NEW_RECOMMENDATION = "new_recommendation"
    CLUSTER_UPDATE = "cluster_update"
    SYSTEM = "system"


# =============================================================================
# ML / Agent
# =============================================================================

class LLMProvider(str, Enum):
    GEMINI = "gemini"
    GROQ = "groq"


class AgentType(str, Enum):
    INTERNSHIP_SCRAPER = "internship_scraper"
    PROJECT_SCRAPER = "project_scraper"
    SCHOLARSHIP_SCRAPER = "scholarship_scraper"
    CERTIFICATION_SCRAPER = "certification_scraper"
    POSTDOC_SCRAPER = "postdoc_scraper"
    CLASSIFIER = "classifier"
    CLUSTER = "cluster"
    RELEVANCE_MATCHER = "relevance_matcher"
    ADVISOR = "advisor"
    NOTIFICATION = "notification"
    COORDINATOR = "coordinator"


class TaskStatus(str, Enum):
    """Mirrors Celery task states for internal tracking."""
    PENDING = "pending"
    STARTED = "started"
    SUCCESS = "success"
    FAILURE = "failure"
    RETRY = "retry"
    REVOKED = "revoked"