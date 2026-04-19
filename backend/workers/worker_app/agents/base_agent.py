from __future__ import annotations

import logging
from abc import abstractmethod
from typing import TYPE_CHECKING

from mesa import Agent

if TYPE_CHECKING:
    from redis import Redis
    from sqlalchemy.orm import Session
    from backend.workers.worker_app.agents.coordinator_agent import ObservatoryModel


class ObservatoryAgent(Agent):

    def __init__(
        self,
        model: "ObservatoryModel",
        db: "Session",
        cache: "Redis",
    ) -> None:
        super().__init__(model)
        self.db = db
        self.cache = cache
        self.logger = logging.getLogger(self.__class__.__name__)
        self.last_result: dict = {}

    @abstractmethod
    def step(self) -> None: 
        ...