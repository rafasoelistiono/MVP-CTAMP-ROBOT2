from __future__ import annotations

from task_planning.types import ConfirmationResult, ScoredPlan, TaskPlan
from world.state import WorldState

from .motion_probe import MotionProbe


def confirm_align_plan(
    world: WorldState,
    plan: TaskPlan,
    slots: dict[str, tuple[float, float, float]],
    motion_probe: MotionProbe,
) -> ConfirmationResult:
    probe_result = motion_probe.probe_align_plan_feasibility(world, plan, slots)
    ik_failures = sum(
        1 for r in probe_result.edge_results if not r.ik_success
    )
    ompl_failures = sum(
        1 for r in probe_result.edge_results if r.ik_success and not r.ompl_success
    )
    return ConfirmationResult(
        confirmed=probe_result.feasible,
        selected_plan_id="single_plan" if probe_result.feasible else None,
        plan=plan if probe_result.feasible else None,
        total_probes=len(probe_result.edge_results),
        total_ik_failures=ik_failures,
        total_ompl_failures=ompl_failures,
        total_planning_time=probe_result.total_planning_time,
        failure_reasons=probe_result.failure_reasons,
    )


def confirm_ranked_align_candidates(
    world: WorldState,
    ranked_candidates: list[ScoredPlan],
    slots: dict[str, tuple[float, float, float]],
    motion_probe: MotionProbe,
) -> ConfirmationResult:
    failed_plan_ids: list[str] = []
    all_failure_reasons: list[str] = []
    total_probes = 0
    total_ik_failures = 0
    total_ompl_failures = 0
    total_planning_time = 0.0

    for scored in ranked_candidates:
        probe_result = motion_probe.probe_align_plan_feasibility(
            world, scored.plan, slots
        )
        total_probes += len(probe_result.edge_results)
        total_ik_failures += sum(
            1 for r in probe_result.edge_results if not r.ik_success
        )
        total_ompl_failures += sum(
            1 for r in probe_result.edge_results
            if r.ik_success and not r.ompl_success
        )
        total_planning_time += probe_result.total_planning_time

        if probe_result.feasible:
            return ConfirmationResult(
                confirmed=True,
                selected_plan_id=scored.plan_id,
                plan=scored.plan,
                total_probes=total_probes,
                total_ik_failures=total_ik_failures,
                total_ompl_failures=total_ompl_failures,
                total_planning_time=round(total_planning_time, 4),
                failed_plan_ids=tuple(failed_plan_ids),
                failure_reasons=tuple(all_failure_reasons),
            )

        failed_plan_ids.append(scored.plan_id)
        for reason in probe_result.failure_reasons:
            all_failure_reasons.append(f"{scored.plan_id}: {reason}")

    return ConfirmationResult(
        confirmed=False,
        total_probes=total_probes,
        total_ik_failures=total_ik_failures,
        total_ompl_failures=total_ompl_failures,
        total_planning_time=round(total_planning_time, 4),
        failed_plan_ids=tuple(failed_plan_ids),
        failure_reasons=tuple(all_failure_reasons),
    )
