import logging
from typing import TYPE_CHECKING
from backend.core.config import get_settings

if TYPE_CHECKING:
    from redis import Redis
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
settings = get_settings()

class BaseAgent:
    def __init__(self, db: Session, cache: Redis):
        self.db = db
        self.cache = cache

    def run(self, *args, **kwargs) -> dict:
        raise NotImplementedError("Each agent must implement its own run method")
