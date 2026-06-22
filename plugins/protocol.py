from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from configuration import RuntimeConfig
    from execution.verifier import ObservedPredicateVerifier
    from task_planning.types import SlotConfig, TaskPlan
    from world.state import WorldState


@dataclass(frozen=True)
class TaskProgress:
    stable_objects: tuple[str, ...]
    invalid_objects: tuple[str, ...]
    first_invalid_level: int | None = None
    reason: str | None = None

    @property
    def valid(self) -> bool:
        return not self.invalid_objects


class TaskPlugin(Protocol):
    api_version: str
    name: str
    supported_actions: set[str]

    def validate_plan(self, plan: "TaskPlan", world: "WorldState") -> None: ...

    def make_slot_config(
        self,
        plan: "TaskPlan",
        world: "WorldState",
    ) -> "SlotConfig": ...

    def configure_runtime(
        self,
        plan: "TaskPlan",
        world: "WorldState",
        config: "RuntimeConfig",
    ) -> "RuntimeConfig": ...

    def assess_progress(
        self,
        plan: "TaskPlan",
        verifier: "ObservedPredicateVerifier",
        slots: dict[str, tuple[float, float, float]],
        completed_objects: set[str],
    ) -> TaskProgress: ...

    def verify_goal(
        self,
        plan: "TaskPlan",
        world: "WorldState",
        verifier: "ObservedPredicateVerifier",
        slots: dict[str, tuple[float, float, float]],
    ) -> bool: ...
