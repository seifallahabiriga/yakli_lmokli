from functools import lru_cache
from typing import Literal

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # -------------------------------------------------------------------------
    # App
    # -------------------------------------------------------------------------
    APP_NAME: str = "University Observatory"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = True
    API_PREFIX: str = "/api/v1"

    # -------------------------------------------------------------------------
    # Security / JWT
    # -------------------------------------------------------------------------
    SECRET_KEY: str = Field(..., min_length=32)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24        # 1 day
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # -------------------------------------------------------------------------
    # PostgreSQL — base credentials
    # -------------------------------------------------------------------------
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str = Field(...)
    POSTGRES_DB: str

    # -------------------------------------------------------------------------
    # Database URLs — computed from credentials
    #
    # Async URL  → used by FastAPI (asyncpg driver)
    # Sync URL   → used by Celery workers and Alembic (psycopg2 driver)
    # -------------------------------------------------------------------------
    @computed_field
    @property
    def ASYNC_DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @computed_field
    @property
    def SYNC_DATABASE_URL(self) -> str:
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # SQLAlchemy pool tuning
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30          # seconds before giving up on a connection
    DB_POOL_RECYCLE: int = 1800        # recycle connections after 30 min
    DB_ECHO: bool = False              # set True to log all SQL (dev only)

    # -------------------------------------------------------------------------
    # Redis
    # -------------------------------------------------------------------------
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str
    REDIS_DB_BROKER: int = 0           # Celery broker
    REDIS_DB_BACKEND: int = 1          # Celery result backend
    REDIS_DB_CACHE: int = 2            # application cache (recommendations, sessions)

    @computed_field
    @property
    def REDIS_BROKER_URL(self) -> str:
        auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB_BROKER}"

    @computed_field
    @property
    def REDIS_BACKEND_URL(self) -> str:
        auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB_BACKEND}"

    @computed_field
    @property
    def REDIS_CACHE_URL(self) -> str:
        auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB_CACHE}"

    # Cache TTLs (seconds)
    CACHE_TTL_OPPORTUNITIES: int = 60 * 30     # 30 min — opportunity lists
    CACHE_TTL_RECOMMENDATIONS: int = 60 * 60   # 1 h   — user recommendations
    CACHE_TTL_CLUSTERS: int = 60 * 60 * 6      # 6 h   — cluster assignments

    # -------------------------------------------------------------------------
    # Celery
    # -------------------------------------------------------------------------
    CELERY_TASK_SERIALIZER: str = "json"
    CELERY_RESULT_SERIALIZER: str = "json"
    CELERY_ACCEPT_CONTENT: list[str] = ["json"]
    CELERY_TIMEZONE: str = "UTC"
    CELERY_ENABLE_UTC: bool = True
    CELERY_TASK_TRACK_STARTED: bool = True
    CELERY_TASK_TIME_LIMIT: int = 60 * 30      # hard kill after 30 min
    CELERY_TASK_SOFT_TIME_LIMIT: int = 60 * 25 # soft warning at 25 min

    # Beat schedule intervals (seconds) — used in celery_app.py
    SCRAPE_INTERVAL_INTERNSHIPS: int = 60 * 60 * 6    # every 6 h
    SCRAPE_INTERVAL_SCHOLARSHIPS: int = 60 * 60 * 24  # every 24 h
    SCRAPE_INTERVAL_PROJECTS: int = 60 * 60 * 12      # every 12 h
    SCRAPE_INTERVAL_CERTS: int = 60 * 60 * 24          # every 24 h
    CLUSTER_RECOMPUTE_INTERVAL: int = 60 * 60 * 12     # every 12 h
    RECOMMENDATION_RECOMPUTE_INTERVAL: int = 60 * 60 * 6

    # -------------------------------------------------------------------------
    # ML — local models
    # -------------------------------------------------------------------------
    # sentence-transformers model used for semantic embeddings
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"

    # spaCy model for NER / keyword extraction
    SPACY_MODEL: str = "en_core_web_sm"

    # FAISS index persistence path
    FAISS_INDEX_PATH: str = "data/faiss_index"

    # Clustering
    CLUSTER_N_CLUSTERS: int = 10          # KMeans k — tune after first data load
    CLUSTER_MIN_SAMPLES: int = 5          # DBSCAN min_samples fallback

    # -------------------------------------------------------------------------
    # ML — cloud LLM providers
    # -------------------------------------------------------------------------
    # Gemini (summarization)
    GEMINI_API_KEY: str = Field(default="")
    GEMINI_MODEL: str = "gemini-1.5-flash"      # free-tier fast model
    GEMINI_MAX_TOKENS: int = 1024
    GEMINI_TEMPERATURE: float = 0.3

    # Groq (chatbot — Llama 3 / Mixtral, very fast inference)
    GROQ_API_KEY: str = Field(default="")
    GROQ_MODEL: str = "llama3-8b-8192"
    GROQ_MAX_TOKENS: int = 2048
    GROQ_TEMPERATURE: float = 0.7

    # LLM router behaviour
    LLM_FALLBACK_ENABLED: bool = True     # fall back to Groq if Gemini fails
    LLM_TIMEOUT_SECONDS: int = 30

    # -------------------------------------------------------------------------
    # Scraping
    # -------------------------------------------------------------------------
    SCRAPER_REQUEST_TIMEOUT: int = 30      # seconds, for httpx / BS4 requests
    SCRAPER_MAX_RETRIES: int = 3
    SCRAPER_RETRY_BACKOFF: float = 2.0     # exponential backoff multiplier
    SCRAPER_PLAYWRIGHT_HEADLESS: bool = True
    SCRAPER_USER_AGENT: str = (
        "Mozilla/5.0 (compatible; UniversityObservatory/1.0; "
        "+https://github.com/your-repo)"
    )
    # Max opportunities to store per scrape run (safety cap)
    SCRAPER_MAX_RESULTS_PER_RUN: int = 200

    # -------------------------------------------------------------------------
    # CORS 
    # -------------------------------------------------------------------------
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]
    CORS_ALLOW_CREDENTIALS: bool = True

    # -------------------------------------------------------------------------
    # Rate limiting 
    # -------------------------------------------------------------------------
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    # -------------------------------------------------------------------------
    # Monitoring
    # -------------------------------------------------------------------------
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"               # "json" | "text"
    METRICS_ENABLED: bool = True
    HEALTH_CHECK_PATH: str = "/health"


@lru_cache
def get_settings() -> Settings:
    """
    Returns a cached Settings singleton.
    Import and call this everywhere — never instantiate Settings() directly.
    """
    return Settings()