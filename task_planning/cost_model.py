from __future__ import annotations

from dataclasses import dataclass, field

from .feature_extractor import (
    extract_align_edge_features,
    extract_align_plan_features,
)
from .types import ScoredPlan, TaskPlan
from world.state import WorldState


DISTANCE_WEIGHT = 1.0
OBSTACLE_RISK_WEIGHT = 5.0
REACHABILITY_WEIGHT = 8.0
CROSSING_WEIGHT = 10.0
DENSITY_WEIGHT = 0.5
INFEASIBLE_PENALTY = 1e6


def estimate_align_edge_cost(features: dict) -> float:
    distance = features.get("object_to_slot_distance", 0.0)
    robot_to_object = features.get("robot_to_object_distance", 0.0)
    transfer = features.get("estimated_transfer_distance", distance + robot_to_object)
    cost = DISTANCE_WEIGHT * transfer
    if features.get("object_near_obstacle"):
        cost += OBSTACLE_RISK_WEIGHT
    if features.get("slot_near_obstacle"):
        cost += OBSTACLE_RISK_WEIGHT
    if features.get("line_crosses_obstacle"):
        cost += CROSSING_WEIGHT
    obj_margin = features.get("object_reachability_margin", 0.0)
    slot_margin = features.get("slot_reachability_margin", 0.0)
    cost += REACHABILITY_WEIGHT * (obj_margin + slot_margin)
    density = features.get("placed_objects_density", 0.0)
    cost += DENSITY_WEIGHT * density
    return round(cost, 6)


def estimate_align_plan_cost(
    plan: TaskPlan,
    world: WorldState,
    slots: dict[str, tuple[float, float, float]],
) -> tuple[float, list[float]]:
    plan_features = extract_align_plan_features(world, plan, slots)
    edge_costs: list[float] = []
    for edge_features in plan_features.get("edge_features", []):
        if "error" in edge_features:
            edge_costs.append(INFEASIBLE_PENALTY)
        else:
            edge_costs.append(estimate_align_edge_cost(edge_features))
    total = sum(edge_costs)
    return round(total, 6), edge_costs


def rank_candidate_plans(
    candidates: list[TaskPlan],
    world: WorldState,
    slots: dict[str, tuple[float, float, float]],
    hint_cache: object | None = None,
    use_adaptive_cache: bool = False,
    cache_config: dict | None = None,
) -> list[ScoredPlan]:
    if use_adaptive_cache and hint_cache is not None:
        from .adaptive_heuristic import rank_align_candidates_with_cache
        cfg = cache_config or {}
        return rank_align_candidates_with_cache(
            cache=hint_cache,
            world=world,
            candidates=candidates,
            slots=slots,
            granularity=cfg.get("granularity", "medium"),
            min_samples=cfg.get("min_samples", 3),
            cache_weight=cfg.get("cache_weight", 0.5),
            failure_penalty=cfg.get("failure_penalty", 2.0),
        )
    scored: list[ScoredPlan] = []
    for idx, plan in enumerate(candidates):
        cost, edge_costs = estimate_align_plan_cost(plan, world, slots)
        method = plan.constraints.get("generation_method", f"candidate_{idx}")
        scored.append(
            ScoredPlan(
                plan_id=f"candidate_{idx}",
                plan=plan,
                estimated_cost=cost,
                generation_method=method,
                edge_costs=tuple(edge_costs),
            )
        )
    scored.sort(key=lambda s: s.estimated_cost)
    return scored


def compute_actual_edge_cost(motion_report: dict) -> float:
    if not motion_report.get("success", False):
        return INFEASIBLE_PENALTY
    path_length = motion_report.get("path_length", 0.0)
    clearance = motion_report.get("min_clearance", 0.0)
    planning_time = motion_report.get("planning_time", 0.0)
    cost = DISTANCE_WEIGHT * path_length
    if clearance < 0.02:
        cost += OBSTACLE_RISK_WEIGHT * (0.02 - clearance) / 0.02
    cost += 0.1 * planning_time
    return round(cost, 6)
