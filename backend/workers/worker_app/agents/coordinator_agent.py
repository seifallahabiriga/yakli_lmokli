from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from mesa import Model
from mesa.time import BaseScheduler

from backend.workers.worker_app.agents.advisor_agent import AdvisorAgent
from backend.workers.worker_app.agents.classifier_agent import ClassifierAgent
from backend.workers.worker_app.agents.cluster_agent import ClusterAgent

if TYPE_CHECKING:
    from redis import Redis
    from sqlalchemy.orm import Session

AgentMode = Literal["classify", "cluster", "recommend"]


class ObservatoryModel(Model):
    """
    Mesa Model that owns the agent scheduler.
    Instantiated with a mode — only the relevant agent is added.
    Calling model.step() runs that agent's step() exactly once.
    """

    def __init__(
        self,
        db: "Session",
        cache: "Redis",
        mode: AgentMode,
        user_id: int | None = None,
    ) -> None:
        super().__init__()
        self.schedule = BaseScheduler(self)

        if mode == "classify":
            self.schedule.add(ClassifierAgent(self, db, cache))
        elif mode == "cluster":
            self.schedule.add(ClusterAgent(self, db, cache))
        elif mode == "recommend":
            self.schedule.add(AdvisorAgent(self, db, cache, user_id=user_id))
        else:
            raise ValueError(f"Unknown mode: {mode!r}")

    def step(self) -> None:
        self.schedule.step()

    @property
    def result(self) -> dict:
        """Returns last_result from the single agent that ran."""
        agents = self.schedule.agents
        if not agents:
            return {}
        return agents[0].last_result