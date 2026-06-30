from __future__ import annotations

import math
from typing import Any

from .types import TaskPlan
from world.state import WorldState


def extract_align_edge_features(
    world: WorldState,
    object_id: str,
    slot_id: str,
    slots: dict[str, tuple[float, float, float]],
    object_order_index: int = 0,
    remaining_unplaced_count: int = 0,
) -> dict[str, Any]:
    obj = world.object_by_id(object_id)
    if obj is None:
        return {"error": f"unknown object {object_id!r}"}
    slot_pos = slots.get(slot_id)
    if slot_pos is None:
        return {"error": f"unknown slot {slot_id!r}"}
    obj_xy = obj.pose[:2]
    slot_xy = slot_pos[:2]
    robot_xy = world.robot_base_xy
    obstacles = world.obstacles
    object_to_slot_distance = math.dist(obj_xy, slot_xy)
    robot_to_object_distance = math.dist(robot_xy, obj_xy)
    robot_to_slot_distance = math.dist(robot_xy, slot_xy)
    object_near_obstacle = _near_obstacle(obj.pose, obstacles, threshold=0.15)
    slot_near_obstacle = _near_obstacle(slot_pos, obstacles, threshold=0.15)
    line_crosses_obstacle = _line_segment_crosses_obstacle(
        obj_xy, slot_xy, obstacles
    )
    object_reachability_margin = _reachability_margin(obj.pose, world)
    slot_reachability_margin = _reachability_margin(slot_pos, world)
    slot_index = _slot_index(slot_id)
    placed_objects_density = _placed_objects_density(
        object_order_index, len(world.target_objects)
    )
    estimated_transfer_distance = robot_to_object_distance + object_to_slot_distance

    return {
        "object_to_slot_distance": round(object_to_slot_distance, 6),
        "robot_to_object_distance": round(robot_to_object_distance, 6),
        "robot_to_slot_distance": round(robot_to_slot_distance, 6),
        "object_near_obstacle": object_near_obstacle,
        "slot_near_obstacle": slot_near_obstacle,
        "line_crosses_obstacle": line_crosses_obstacle,
        "object_reachability_margin": round(object_reachability_margin, 6),
        "slot_reachability_margin": round(slot_reachability_margin, 6),
        "slot_index": slot_index,
        "object_order_index": object_order_index,
        "remaining_unplaced_count": remaining_unplaced_count,
        "placed_objects_density": round(placed_objects_density, 6),
        "estimated_transfer_distance": round(estimated_transfer_distance, 6),
    }


def extract_align_plan_features(
    world: WorldState,
    plan: TaskPlan,
    slots: dict[str, tuple[float, float, float]],
) -> dict[str, Any]:
    edge_features_list: list[dict[str, Any]] = []
    total_distance = 0.0
    total_obstacle_risk = 0
    total_reachability_penalty = 0.0
    pick_place_pairs = _extract_pick_place_pairs(plan)
    total_objects = len(pick_place_pairs)
    for idx, (object_id, slot_id) in enumerate(pick_place_pairs):
        remaining = total_objects - idx - 1
        features = extract_align_edge_features(
            world, object_id, slot_id, slots,
            object_order_index=idx,
            remaining_unplaced_count=remaining,
        )
        edge_features_list.append(features)
        total_distance += features.get("estimated_transfer_distance", 0.0)
        if features.get("object_near_obstacle"):
            total_obstacle_risk += 1
        if features.get("slot_near_obstacle"):
            total_obstacle_risk += 1
        if features.get("line_crosses_obstacle"):
            total_obstacle_risk += 2
        total_reachability_penalty += max(
            0.0, 0.3 - features.get("object_reachability_margin", 0.3)
        )
        total_reachability_penalty += max(
            0.0, 0.3 - features.get("slot_reachability_margin", 0.3)
        )

    return {
        "edge_count": len(edge_features_list),
        "edge_features": edge_features_list,
        "total_distance": round(total_distance, 6),
        "total_obstacle_risk": total_obstacle_risk,
        "total_reachability_penalty": round(total_reachability_penalty, 6),
        "mean_edge_distance": (
            round(total_distance / len(edge_features_list), 6)
            if edge_features_list else 0.0
        ),
    }


def bucketize_align_features(
    features: dict[str, Any],
    granularity: str = "medium",
) -> dict[str, Any]:
    if "error" in features:
        return {"error": features["error"]}
    buckets = _GRANULARITY_BUCKETS.get(granularity, _GRANULARITY_BUCKETS["medium"])
    return {
        "dist_bucket": _bucketize(
            features.get("object_to_slot_distance", 0.0),
            buckets["distance"],
        ),
        "robot_obj_bucket": _bucketize(
            features.get("robot_to_object_distance", 0.0),
            buckets["robot_object"],
        ),
        "robot_slot_bucket": _bucketize(
            features.get("robot_to_slot_distance", 0.0),
            buckets["robot_slot"],
        ),
        "obj_near_obs": bool(features.get("object_near_obstacle", False)),
        "slot_near_obs": bool(features.get("slot_near_obstacle", False)),
        "line_crosses_obs": bool(features.get("line_crosses_obstacle", False)),
        "obj_reach_margin_bucket": _bucketize(
            features.get("object_reachability_margin", 0.0),
            buckets["reachability"],
        ),
        "slot_reach_margin_bucket": _bucketize(
            features.get("slot_reachability_margin", 0.0),
            buckets["reachability"],
        ),
        "slot_index": int(features.get("slot_index", 0)),
        "remaining_count_bucket": _bucketize(
            features.get("remaining_unplaced_count", 0),
            buckets["remaining"],
        ),
    }


def make_align_cache_key(
    features: dict[str, Any],
    granularity: str = "medium",
) -> str:
    bucketed = bucketize_align_features(features, granularity)
    if "error" in bucketed:
        return "error"
    parts = [
        f"d{bucketed['dist_bucket']}",
        f"ro{bucketed['robot_obj_bucket']}",
        f"rs{bucketed['robot_slot_bucket']}",
        f"on{int(bucketed['obj_near_obs'])}",
        f"sn{int(bucketed['slot_near_obs'])}",
        f"lc{int(bucketed['line_crosses_obs'])}",
        f"orm{bucketed['obj_reach_margin_bucket']}",
        f"srm{bucketed['slot_reach_margin_bucket']}",
        f"si{bucketed['slot_index']}",
        f"rc{bucketed['remaining_count_bucket']}",
    ]
    return "|".join(parts)


_GRANULARITY_BUCKETS: dict[str, dict[str, list[float]]] = {
    "fine": {
        "distance": [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40],
        "robot_object": [0.35, 0.45, 0.55, 0.65, 0.75],
        "robot_slot": [0.35, 0.45, 0.55, 0.65, 0.75],
        "reachability": [0.01, 0.03, 0.05, 0.10],
        "remaining": [1.0, 2.0, 3.0, 4.0, 5.0],
    },
    "medium": {
        "distance": [0.10, 0.20, 0.30],
        "robot_object": [0.40, 0.60, 0.75],
        "robot_slot": [0.40, 0.60, 0.75],
        "reachability": [0.02, 0.05, 0.10],
        "remaining": [2.0, 4.0],
    },
    "coarse": {
        "distance": [0.15, 0.30],
        "robot_object": [0.50, 0.70],
        "robot_slot": [0.50, 0.70],
        "reachability": [0.05],
        "remaining": [3.0],
    },
}


def _bucketize(value: float, thresholds: list[float]) -> int:
    for i, t in enumerate(thresholds):
        if value < t:
            return i
    return len(thresholds)


def _extract_pick_place_pairs(
    plan: TaskPlan,
) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    i = 0
    while i < len(plan.steps) - 1:
        if plan.steps[i].action == "pick" and plan.steps[i + 1].action == "place":
            pairs.append((plan.steps[i].object, plan.steps[i + 1].slot or ""))
            i += 2
        else:
            i += 1
    return pairs


def _near_obstacle(
    pos: tuple[float, float, float],
    obstacles: tuple,
    threshold: float = 0.15,
) -> bool:
    for obs in obstacles:
        dist = math.dist(pos[:2], obs.pose[:2])
        if dist < obs.radius + threshold:
            return True
    return False


def _line_segment_crosses_obstacle(
    start_xy: tuple[float, float],
    end_xy: tuple[float, float],
    obstacles: tuple,
    buffer: float = 0.06,
) -> bool:
    for obs in obstacles:
        obs_xy = obs.pose[:2]
        obs_r = obs.radius + buffer
        dist = _point_to_segment_distance(obs_xy, start_xy, end_xy)
        if dist < obs_r:
            return True
    return False


def _point_to_segment_distance(
    point: tuple[float, float],
    seg_start: tuple[float, float],
    seg_end: tuple[float, float],
) -> float:
    px, py = point
    ax, ay = seg_start
    bx, by = seg_end
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.dist(point, seg_start)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    proj_x = ax + t * dx
    proj_y = ay + t * dy
    return math.dist(point, (proj_x, proj_y))


def _reachability_margin(
    pose: tuple[float, float, float],
    world: WorldState,
) -> float:
    dist = math.dist(pose[:2], world.robot_base_xy)
    if dist < world.robot_reach_min:
        return world.robot_reach_min - dist
    if dist > world.robot_reach_max:
        return dist - world.robot_reach_max
    return 0.0


def _slot_index(slot_id: str) -> int:
    if slot_id.startswith("align_slot_"):
        try:
            return int(slot_id.split("_")[-1])
        except (ValueError, IndexError):
            pass
    return 0


def _placed_objects_density(
    object_order_index: int,
    total_objects: int,
) -> float:
    if total_objects <= 1:
        return 0.0
    return object_order_index / (total_objects - 1)
