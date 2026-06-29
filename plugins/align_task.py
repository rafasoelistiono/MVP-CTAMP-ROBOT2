from __future__ import annotations

from dataclasses import replace

from configuration import RuntimeConfig
from task_planning.types import SlotConfig, TaskPlan
from task_planning.validator import PlanValidationError
from world.state import WorldState

from .protocol import TaskProgress


class AlignTaskPlugin:
    api_version = "ctamp-task/v2"
    name = "align"
    supported_actions = {"pick", "place"}

    def validate_plan(self, plan: TaskPlan, world: WorldState) -> None:
        if plan.task != self.name:
            raise PlanValidationError(
                f"align plugin cannot execute task {plan.task!r}"
            )
        if plan.slot_config.type != "line":
            raise PlanValidationError("align task requires line slot_config")
        if plan.target_objects != world.target_objects:
            raise PlanValidationError(
                "align plan target_objects must exactly match context task targets"
            )
        if plan.constraints.get("preserve_obstacles", True) is not True:
            raise PlanValidationError("align plan cannot disable obstacle preservation")
        unsupported = sorted(
            {step.action for step in plan.steps} - self.supported_actions
        )
        if unsupported:
            raise PlanValidationError(
                f"align task does not support actions: {unsupported}"
            )
        missing_capabilities = sorted(
            {step.action for step in plan.steps} - set(world.robot_capabilities)
        )
        if missing_capabilities:
            raise PlanValidationError(
                f"robot lacks capabilities required by align plan: {missing_capabilities}"
            )
        non_cubes = [
            object_id
            for object_id in plan.target_objects
            if world.object_by_id(object_id).cls != "cube"
        ]
        if non_cubes:
            raise PlanValidationError(
                "align task accepts cube objects only: " + ", ".join(non_cubes)
            )
        unreachable = [
            object_id
            for object_id in plan.target_objects
            if not world.object_by_id(object_id).reachable
        ]
        if unreachable:
            raise PlanValidationError(
                "align target objects are unreachable: " + ", ".join(unreachable)
            )
        expected = list(plan.target_objects)
        if len(plan.steps) != len(expected) * 2:
            raise PlanValidationError(
                "align plan must contain exactly one pick/place pair per cube"
            )
        used_slots: set[str] = set()
        for index, object_id in enumerate(expected):
            pick_step = plan.steps[index * 2]
            place_step = plan.steps[index * 2 + 1]
            if pick_step.action != "pick" or pick_step.object != object_id:
                raise PlanValidationError(
                    "align plan must pick cubes in target_objects order"
                )
            if (
                place_step.action != "place"
                or place_step.object != object_id
                or not place_step.slot
            ):
                raise PlanValidationError(
                    "align plan must place each cube immediately after picking it"
                )
            if place_step.slot in used_slots:
                raise PlanValidationError(
                    f"align plan assigns duplicate slot {place_step.slot!r}"
                )
            used_slots.add(place_step.slot)

    def make_slot_config(
        self,
        plan: TaskPlan,
        world: WorldState,
    ) -> SlotConfig:
        return plan.slot_config

    def configure_runtime(
        self,
        plan: TaskPlan,
        world: WorldState,
        config: RuntimeConfig,
    ) -> RuntimeConfig:
        if world.obstacles:
            return replace(
                config,
                model=replace(config.model, grasp_ready_q=config.model.home_q),
            ).validate()
        return config.validate()

    def assess_progress(self, plan, verifier, slots, completed_objects):
        stable = tuple(
            object_id
            for object_id in plan.target_objects
            if object_id in completed_objects
        )
        return TaskProgress(stable_objects=stable, invalid_objects=())

    def verify_goal(self, plan, world, verifier, slots) -> bool:
        at_predicates = [
            predicate
            for predicate in plan.goal_predicates
            if predicate.get("name") == "at"
        ]
        if at_predicates:
            if not all(
                verifier.evaluate(predicate, slots) for predicate in at_predicates
            ):
                return False
        else:
            for index, object_id in enumerate(plan.target_objects):
                slot_id = f"align_slot_{index}"
                if slot_id not in slots:
                    return False
                if not verifier.check_at(object_id, slots[slot_id]):
                    return False
        if not all(
            verifier.check_stable(object_id, include_velocity=True)
            for object_id in plan.target_objects
        ):
            return False
        if not verifier.check_handempty():
            return False
        return True


PLUGIN = AlignTaskPlugin()
