#!/usr/bin/env python3
"""Compare align planning strategies: LLM-only, heuristics, and robust candidate planner.

Usage:
    python experiments/run_align_baselines.py --context contexts/align_basic_5_cubes.md
    python experiments/run_align_baselines.py --context contexts/align_obstacle_5_cubes.md
    python experiments/run_align_baselines.py --context contexts/align_dense_6_cubes.md
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from task_planning.candidate_generator import generate_align_candidates
from task_planning.cost_model import rank_candidate_plans
from task_planning.feature_extractor import extract_align_plan_features
from task_planning.loader import parse_plan
from task_planning.validator import validate
from plugins.registry import DEFAULT_REGISTRY
from world.builder import build_world_state
from world.slot_allocator import allocate_slots


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare align planning strategies without MuJoCo execution."
    )
    parser.add_argument("--context", required=True, type=Path)
    parser.add_argument("--plan", type=Path, help="Optional LLM-generated plan to include.")
    parser.add_argument("--output", type=Path, default=ROOT_DIR / "logs" / "baseline_comparison.csv")
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def _run_comparison(context_path: Path, plan_path: Path | None, seed: int) -> list[dict]:
    world = build_world_state(context_path)
    plugin = DEFAULT_REGISTRY.get("align")
    slot_config = plugin.make_slot_config(
        parse_plan({
            "schema_version": "ctamp-plan/v1",
            "task": "align",
            "scene_id": world.scene_id,
            "target_objects": list(world.target_objects),
            "goal_predicates": [],
            "slot_config": {"type": "line", "center_x": 0.22, "row_y": -0.06, "base_z": 0.833},
            "steps": [],
        }),
        world,
    )
    slots = allocate_slots(slot_config, len(world.target_objects))

    llm_plan = None
    if plan_path is not None:
        llm_plan = parse_plan(plan_path.read_text(encoding="utf-8"))

    start_gen = time.perf_counter()
    candidates = generate_align_candidates(world, slots, llm_plan=llm_plan)
    gen_time = time.perf_counter() - start_gen

    start_rank = time.perf_counter()
    ranked = rank_candidate_plans(candidates, world, slots)
    rank_time = time.perf_counter() - start_rank

    results = []
    for idx, scored in enumerate(ranked):
        features = extract_align_plan_features(world, scored.plan, slots)
        order = [s.object for s in scored.plan.steps if s.action == "pick"]
        results.append({
            "strategy": scored.generation_method,
            "plan_id": scored.plan_id,
            "rank": idx + 1,
            "estimated_cost": scored.estimated_cost,
            "total_distance": features.get("total_distance", 0.0),
            "total_obstacle_risk": features.get("total_obstacle_risk", 0),
            "total_reachability_penalty": features.get("total_reachability_penalty", 0.0),
            "object_order": json.dumps(order),
            "generation_time_s": round(gen_time / len(candidates), 4) if candidates else 0.0,
            "ranking_time_s": round(rank_time, 4),
            "candidate_count": len(candidates),
        })
    return results


def main() -> int:
    args = _arguments()
    results = _run_comparison(args.context, args.plan, args.seed)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    if results:
        fieldnames = list(results[0].keys())
        with args.output.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
        print(f"Wrote {len(results)} rows to {args.output}")

    print(f"\n{'Strategy':<25} {'Cost':>10} {'Distance':>10} {'Obstacle':>10}")
    print("-" * 60)
    for r in results:
        print(
            f"{r['strategy']:<25} {r['estimated_cost']:>10.4f} "
            f"{r['total_distance']:>10.4f} {r['total_obstacle_risk']:>10}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
