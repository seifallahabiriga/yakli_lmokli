from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from mesa import Model

from backend.workers.worker_app.agents.advisor_agent import AdvisorAgent
from backend.workers.worker_app.agents.classifier_agent import ClassifierAgent
from backend.workers.worker_app.agents.cluster_agent import ClusterAgent

if TYPE_CHECKING:
    from redis import Redis
    from sqlalchemy.orm import Session

AgentMode = Literal["classify", "cluster", "recommend"]


class ObservatoryModel(Model):
    """
    Mesa 3.5 Model — agents register themselves on the model at instantiation.
    Calling model.step() runs step() on every registered agent via AgentSet.
    """

    def __init__(
        self,
        db: "Session",
        cache: "Redis",
        mode: AgentMode,
        user_id: int | None = None,
    ) -> None:
        super().__init__()

        # In Mesa 3.5, Agent.__init__(model) auto-registers the agent on
        # model.agents — no schedule.add() needed.
        if mode == "classify":
            ClassifierAgent(self, db, cache)
        elif mode == "cluster":
            ClusterAgent(self, db, cache)
        elif mode == "recommend":
            AdvisorAgent(self, db, cache, user_id=user_id)
        else:
            raise ValueError(f"Unknown mode: {mode!r}")

    def step(self) -> None:
        # Mesa 3.5: AgentSet.do() calls the named method on every agent
        self.agents.do("step")

    @property
    def result(self) -> dict:
        """Returns last_result from the single agent that ran."""
        agents = list(self.agents)
        if not agents:
            return {}
        return agents[0].last_result