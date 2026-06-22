from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]

from task_planning.generator import (
    LLMSettings,
    PlanGenerationError,
    parse_llm_json,
    request_task_plan,
)
from task_planning.loader import parse_plan
from task_planning.validator import validate
from plugins.registry import DEFAULT_REGISTRY, PluginRegistry
from world.builder import build_world_state


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate one validated CTAMP TaskPlan JSON before simulation."
    )
    parser.add_argument("--context", required=True, type=Path)
    parser.add_argument("--task", required=True)
    parser.add_argument("--output", default=ROOT_DIR / "task_plans", type=Path)
    parser.add_argument(
        "--response-file",
        type=Path,
        help="Offline/testing mode: validate an existing raw LLM JSON response.",
    )
    parser.add_argument(
        "--plugin-package",
        default="plugins",
        help="Trusted package containing deterministic *_task.py plugins.",
    )
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    world = build_world_state(args.context)
    if args.task != world.task_name:
        raise PlanGenerationError(
            f"--task {args.task!r} does not match context task {world.task_name!r}"
        )
    context_text = args.context.read_text(encoding="utf-8")
    if args.response_file:
        payload = parse_llm_json(args.response_file.read_text(encoding="utf-8"))
    else:
        payload = request_task_plan(context_text, LLMSettings.from_env())

    status = payload.get("status")
    if status in {"UNSAT", "NEEDS_CLARIFICATION"}:
        args.output.mkdir(parents=True, exist_ok=True)
        status_path = args.output / f"{world.scene_id}_{args.task}_{status.lower()}.json"
        status_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"Planner returned {status}: {status_path}")
        return 2

    plan = parse_plan(payload)
    if plan.scene_id != world.scene_id:
        raise PlanGenerationError(
            f"plan scene_id {plan.scene_id!r} does not match context {world.scene_id!r}"
        )
    if plan.task != world.task_name:
        raise PlanGenerationError(
            f"plan task {plan.task!r} does not match context {world.task_name!r}"
        )
    validate(plan, world.all_object_ids(), world.allowed_predicates)
    registry = (
        DEFAULT_REGISTRY
        if args.plugin_package == "plugins"
        else PluginRegistry.discover(args.plugin_package)
    )
    registry.get(plan.task).validate_plan(plan, world)

    args.output.mkdir(parents=True, exist_ok=True)
    output_path = args.output / f"{world.scene_id}_{plan.task}.json"
    output_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"TaskPlan valid: {output_path} | steps={len(plan.steps)} "
        f"objects={','.join(plan.target_objects)}"
    )
    return 0


def cli() -> None:
    try:
        raise SystemExit(main())
    except (OSError, ValueError, PlanGenerationError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    cli()
