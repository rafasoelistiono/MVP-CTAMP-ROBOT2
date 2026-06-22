from __future__ import annotations

import csv
import json
import time
from collections import Counter
from pathlib import Path

from configuration.defaults import ROOT_DIR
from scene import obstacle_mode_for_scene


def write_summary_csv(
    task_name: str,
    scene_key: str,
    summary: dict,
    log_dir: str | Path = "logs",
) -> Path:
    out_dir = Path(log_dir)
    if not out_dir.is_absolute():
        out_dir = ROOT_DIR / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"{task_name}_{scene_key}_{timestamp}.csv"
    failed = list(summary.get("failed", []))
    objects_moved = int(summary.get("objects_moved") or 0)
    objects_total = int(summary.get("objects_total") or objects_moved + len(failed))
    success_rate = objects_moved / objects_total if objects_total else 0.0
    completion_percent = round(success_rate * 100.0, 2)
    overall_success = bool(summary.get("success"))
    benchmark_role = str(summary.get("benchmark_role") or "candidate")
    reference_100_percent = (
        benchmark_role == "reference"
        and overall_success
        and completion_percent == 100.0
    )
    obstacle_mode = summary.get("obstacle_mode") or obstacle_mode_for_scene(scene_key)
    scenario_type = summary.get("scenario_type") or "static"
    failure_counts = Counter(_failure_reason(item) for item in failed)
    row = {
        "task": task_name,
        "scene": scene_key,
        "scenario_type": scenario_type,
        "obstacle_mode": obstacle_mode,
        "success": overall_success,
        "success_count": objects_moved,
        "failure_count": len(failed),
        "objects_moved": objects_moved,
        "objects_total": objects_total,
        "object_success_rate": round(success_rate, 4),
        "completion_percent": completion_percent,
        "plan_source": summary.get("plan_source", "unspecified"),
        "benchmark_role": benchmark_role,
        "benchmark_label": summary.get("benchmark_label", ""),
        "reference_100_percent": str(reference_100_percent).lower(),
        "failed_json": json.dumps(failed, ensure_ascii=False),
        "failure_reason_counts_json": json.dumps(
            dict(sorted(failure_counts.items())), ensure_ascii=False
        ),
        "duration_ms": summary.get("duration_ms"),
        "llm_used": str(bool(summary.get("llm_used", False))).lower(),
        "plan_file": summary.get("plan_file", ""),
        "runtime_profile": summary.get("runtime_profile", ""),
        "runtime_config_file": summary.get("runtime_config_file", ""),
        "run_manifest": summary.get("run_manifest", ""),
    }
    with out_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)
    return out_path


def _failure_reason(item) -> str:
    if isinstance(item, dict):
        return str(item.get("failure_reason") or item.get("stage") or "unknown")
    return "unknown"
