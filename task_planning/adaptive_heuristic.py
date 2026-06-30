from __future__ import annotations

from typing import Any

from backends.adaptive.hint_cache import AlignCacheEntry, HintCache
from .feature_extractor import (
    extract_align_edge_features,
    extract_align_plan_features,
    make_align_cache_key,
)
from .cost_model import (
    INFEASIBLE_PENALTY,
    estimate_align_edge_cost,
    estimate_align_plan_cost,
)
from .types import ScoredPlan, TaskPlan
from world.state import WorldState


def predict_align_edge_cost(
    cache: HintCache,
    world: WorldState,
    object_id: str,
    slot_id: str,
    slots: dict[str, tuple[float, float, float]],
    granularity: str = "medium",
    min_samples: int = 3,
    cache_weight: float = 0.5,
    failure_penalty: float = 2.0,
) -> tuple[float, bool]:
    features = extract_align_edge_features(world, object_id, slot_id, slots)
    if "error" in features:
        return INFEASIBLE_PENALTY, False
    static_cost = estimate_align_edge_cost(features)
    cache_key = make_align_cache_key(features, granularity)
    entry = cache.get_align_edge_entry(cache_key)
    if entry is None or entry.total_samples < min_samples:
        return static_cost, False
    cached_cost = entry.ema_cost
    confidence = min(1.0, entry.total_samples / (min_samples * 3))
    combined = combine_static_and_cached_cost(
        static_cost, cached_cost, confidence, cache_weight
    )
    failure_rate = entry.failure_rate
    if failure_rate > 0.0:
        combined *= (1.0 + failure_penalty * failure_rate)
    ik_pattern_penalty = _ik_ompl_pattern_penalty(entry)
    combined *= (1.0 + ik_pattern_penalty)
    return round(combined, 6), True


def predict_align_plan_cost(
    cache: HintCache,
    world: WorldState,
    plan: TaskPlan,
    slots: dict[str, tuple[float, float, float]],
    granularity: str = "medium",
    min_samples: int = 3,
    cache_weight: float = 0.5,
    failure_penalty: float = 2.0,
) -> tuple[float, list[float], bool]:
    plan_features = extract_align_plan_features(world, plan, slots)
    edge_costs: list[float] = []
    any_cached = False
    for edge_features in plan_features.get("edge_features", []):
        if "error" in edge_features:
            edge_costs.append(INFEASIBLE_PENALTY)
            continue
        static_cost = estimate_align_edge_cost(edge_features)
        cache_key = make_align_cache_key(edge_features, granularity)
        entry = cache.get_align_edge_entry(cache_key)
        if entry is None or entry.total_samples < min_samples:
            edge_costs.append(static_cost)
            continue
        any_cached = True
        cached_cost = entry.ema_cost
        confidence = min(1.0, entry.total_samples / (min_samples * 3))
        combined = combine_static_and_cached_cost(
            static_cost, cached_cost, confidence, cache_weight
        )
        failure_rate = entry.failure_rate
        if failure_rate > 0.0:
            combined *= (1.0 + failure_penalty * failure_rate)
        ik_pattern_penalty = _ik_ompl_pattern_penalty(entry)
        combined *= (1.0 + ik_pattern_penalty)
        edge_costs.append(round(combined, 6))
    total = sum(edge_costs)
    return round(total, 6), edge_costs, any_cached


def rank_align_candidates_with_cache(
    cache: HintCache,
    world: WorldState,
    candidates: list[TaskPlan],
    slots: dict[str, tuple[float, float, float]],
    granularity: str = "medium",
    min_samples: int = 3,
    cache_weight: float = 0.5,
    failure_penalty: float = 2.0,
) -> list[ScoredPlan]:
    scored: list[ScoredPlan] = []
    for idx, plan in enumerate(candidates):
        cost, edge_costs, used_cache = predict_align_plan_cost(
            cache, world, plan, slots, granularity, min_samples, cache_weight, failure_penalty
        )
        method = plan.constraints.get("generation_method", f"candidate_{idx}")
        if used_cache:
            method = f"{method}+cache"
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


def combine_static_and_cached_cost(
    static_cost: float,
    cached_cost: float,
    cache_confidence: float,
    cache_weight: float = 0.5,
) -> float:
    effective_weight = cache_weight * cache_confidence
    return (1.0 - effective_weight) * static_cost + effective_weight * cached_cost


def _ik_ompl_pattern_penalty(entry: AlignCacheEntry) -> float:
    total = entry.total_samples
    if total == 0:
        return 0.0
    ik_rate = entry.ik_failure_count / total
    ompl_rate = entry.ompl_failure_count / total
    penalty = 0.0
    if ik_rate > 0.3:
        penalty += 0.3 * (ik_rate - 0.3)
    if ompl_rate > 0.3:
        penalty += 0.2 * (ompl_rate - 0.3)
    return min(penalty, 1.0)


def record_probe_result_to_cache(
    cache: HintCache,
    world: WorldState,
    object_id: str,
    slot_id: str,
    slots: dict[str, tuple[float, float, float]],
    success: bool,
    actual_cost: float,
    planning_time: float = 0.0,
    ik_failures: int = 0,
    ompl_failures: int = 0,
    collisions: int = 0,
    failure_reason: str = "",
    run_id: str = "",
    granularity: str = "medium",
    alpha: float = 0.3,
) -> str:
    features = extract_align_edge_features(world, object_id, slot_id, slots)
    cache_key = make_align_cache_key(features, granularity)
    cache.record_align_edge_result(
        feature_key=cache_key,
        success=success,
        actual_cost=actual_cost,
        planning_time=planning_time,
        ik_failures=ik_failures,
        ompl_failures=ompl_failures,
        collisions=collisions,
        failure_reason=failure_reason,
        run_id=run_id,
        alpha=alpha,
    )
    return cache_key


def record_plan_result_to_cache(
    cache: HintCache,
    world: WorldState,
    plan: TaskPlan,
    slots: dict[str, tuple[float, float, float]],
    success: bool,
    actual_cost: float,
    planning_time: float = 0.0,
    ik_failures: int = 0,
    ompl_failures: int = 0,
    collisions: int = 0,
    failure_reason: str = "",
    run_id: str = "",
    granularity: str = "medium",
    alpha: float = 0.3,
) -> str:
    plan_features = extract_align_plan_features(world, plan, slots)
    plan_key = f"plan|{plan.scene_id}|{len(plan.steps)}|{hash(tuple(s.object for s in plan.steps if s.action == 'pick'))}"
    cache.record_align_plan_result(
        feature_key=plan_key,
        success=success,
        actual_cost=actual_cost,
        planning_time=planning_time,
        ik_failures=ik_failures,
        ompl_failures=ompl_failures,
        collisions=collisions,
        failure_reason=failure_reason,
        run_id=run_id,
        alpha=alpha,
    )
    return plan_key
