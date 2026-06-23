from __future__ import annotations

import re
from pathlib import Path


def normalize_experiment_label(value: str | None) -> str:
    """Return a filesystem-safe, stable experiment label."""
    if not value:
        return ""
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", str(value).strip())
    return normalized.strip("_").lower()


def infer_experiment_label(
    path: str | Path | None,
    *,
    scene_id: str,
    task: str,
) -> str:
    """Infer the model/experiment suffix from a conventionally named plan."""
    if path is None:
        return ""
    stem = Path(path).stem
    prefixes = (f"{scene_id}_{task}_", f"{scene_id}_")
    for prefix in prefixes:
        if stem.startswith(prefix):
            return normalize_experiment_label(stem[len(prefix) :])
    return ""


def with_experiment_label(base: str, label: str | None) -> str:
    safe_label = normalize_experiment_label(label)
    return f"{base}_{safe_label}" if safe_label else base
