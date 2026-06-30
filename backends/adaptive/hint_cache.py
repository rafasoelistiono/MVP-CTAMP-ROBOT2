from __future__ import annotations

import csv
import json
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ExecutionHints:
    ik_backend: str
    ik_position_tolerance: float
    grasp_profile: str


@dataclass
class AlignCacheEntry:
    feature_key: str
    success_count: int = 0
    failure_count: int = 0
    ema_cost: float = 0.0
    avg_planning_time: float = 0.0
    ik_failure_count: int = 0
    ompl_failure_count: int = 0
    collision_count: int = 0
    last_failure_reason: str = ""
    last_updated_run_id: str = ""
    last_updated_timestamp: float = 0.0

    @property
    def total_samples(self) -> int:
        return self.success_count + self.failure_count

    @property
    def failure_rate(self) -> float:
        total = self.total_samples
        return self.failure_count / total if total > 0 else 0.0

    def update(
        self,
        success: bool,
        actual_cost: float,
        planning_time: float = 0.0,
        ik_failures: int = 0,
        ompl_failures: int = 0,
        collisions: int = 0,
        failure_reason: str = "",
        run_id: str = "",
        alpha: float = 0.3,
    ) -> None:
        if success:
            self.success_count += 1
        else:
            self.failure_count += 1
        if self.total_samples == 1:
            self.ema_cost = actual_cost
        else:
            self.ema_cost = alpha * actual_cost + (1.0 - alpha) * self.ema_cost
        n = self.total_samples
        self.avg_planning_time = (
            (self.avg_planning_time * (n - 1) + planning_time) / n
        )
        self.ik_failure_count += ik_failures
        self.ompl_failure_count += ompl_failures
        self.collision_count += collisions
        if not success and failure_reason:
            self.last_failure_reason = failure_reason
        self.last_updated_run_id = run_id
        self.last_updated_timestamp = time.time()

    def to_dict(self) -> dict:
        return {
            "feature_key": self.feature_key,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "ema_cost": self.ema_cost,
            "avg_planning_time": self.avg_planning_time,
            "ik_failure_count": self.ik_failure_count,
            "ompl_failure_count": self.ompl_failure_count,
            "collision_count": self.collision_count,
            "last_failure_reason": self.last_failure_reason,
            "last_updated_run_id": self.last_updated_run_id,
            "last_updated_timestamp": self.last_updated_timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AlignCacheEntry":
        return cls(
            feature_key=data.get("feature_key", ""),
            success_count=int(data.get("success_count", 0)),
            failure_count=int(data.get("failure_count", 0)),
            ema_cost=float(data.get("ema_cost", 0.0)),
            avg_planning_time=float(data.get("avg_planning_time", 0.0)),
            ik_failure_count=int(data.get("ik_failure_count", 0)),
            ompl_failure_count=int(data.get("ompl_failure_count", 0)),
            collision_count=int(data.get("collision_count", 0)),
            last_failure_reason=data.get("last_failure_reason", ""),
            last_updated_run_id=data.get("last_updated_run_id", ""),
            last_updated_timestamp=float(data.get("last_updated_timestamp", 0.0)),
        )


class HintCache:
    """
    Read historical events without changing goals, verifier tolerances, or safety.

    Hints are efficiency preferences only. The hard cap of 0.030 m prevents
    historical data from progressively weakening IK acceptance.
    """

    DEFAULT_IK_TOLERANCE = 0.020
    MAX_IK_TOLERANCE = 0.030

    def __init__(
        self,
        log_dir: str | Path,
        *,
        min_samples: int = 3,
        fallback_threshold: float = 0.70,
    ):
        self.log_dir = Path(log_dir)
        self.min_samples = int(min_samples)
        self.fallback_threshold = float(fallback_threshold)
        self._rows = self._load(self.log_dir)
        self._align_edge_cache: dict[str, AlignCacheEntry] = {}
        self._align_plan_cache: dict[str, AlignCacheEntry] = {}
        self._align_failure_patterns: dict[str, AlignCacheEntry] = {}
        self._load_align_caches(self.log_dir)

    @staticmethod
    def reach_bucket(distance: float) -> str:
        if distance > 0.78:
            return "borderline"
        if distance > 0.70:
            return "far"
        return "normal"

    def hints_for(self, obj_id: str, cls: str, reach_distance: float) -> ExecutionHints:
        bucket = self.reach_bucket(reach_distance)
        return ExecutionHints(
            ik_backend=self.get_ik_backend(obj_id, bucket),
            ik_position_tolerance=self.get_ik_tolerance(obj_id, bucket),
            grasp_profile=self.get_grasp_profile(obj_id, cls),
        )

    def get_ik_backend(self, obj_id: str, reach_bucket: str) -> str:
        relevant = [
            row
            for row in self._rows
            if row.get("stage") in {"IK_SOLVE", "IK_CANDIDATE"}
            and self._row_matches_object(row, obj_id)
        ]
        fallback = [
            row
            for row in relevant
            if row.get("status") == "BACKEND_FALLBACK"
            or row.get("failure_reason") == "pinocchio_fk_validation_failed"
        ]
        candidate_count = sum(
            1 for row in relevant if row.get("stage") == "IK_CANDIDATE"
        )
        denominator = candidate_count or len(relevant)
        if denominator >= self.min_samples and len(fallback) / denominator >= self.fallback_threshold:
            return "mujoco_dls"
        return "pinocchio"

    def get_ik_tolerance(self, obj_id: str, reach_bucket: str) -> float:
        near_misses: list[float] = []
        for row in self._rows:
            if row.get("stage") != "IK_CANDIDATE":
                continue
            if row.get("failure_reason") != "ik_error_above_limit":
                continue
            if not self._row_matches_object(row, obj_id):
                continue
            try:
                error = float(row.get("pos_err", "nan"))
            except (TypeError, ValueError):
                continue
            if self.DEFAULT_IK_TOLERANCE < error <= self.MAX_IK_TOLERANCE:
                near_misses.append(error)
        if len(near_misses) < self.min_samples:
            return self.DEFAULT_IK_TOLERANCE
        near_misses.sort()
        median = near_misses[len(near_misses) // 2]
        return min(max(median, self.DEFAULT_IK_TOLERANCE), self.MAX_IK_TOLERANCE)

    def get_grasp_profile(self, obj_id: str, cls: str) -> str:
        scores: dict[str, list[bool]] = {}
        for row in self._rows:
            if row.get("stage") != "GRASP_PROFILE_RESULT":
                continue
            if row.get("object_id") != obj_id:
                continue
            profile = row.get("grasp_profile", "")
            if not profile:
                try:
                    profile = json.loads(row.get("extra_json", "{}")).get(
                        "grasp_profile", ""
                    )
                except (TypeError, json.JSONDecodeError):
                    profile = ""
            if profile:
                scores.setdefault(profile, []).append(row.get("status") == "OK")
        ranked = [
            (sum(outcomes) / len(outcomes), profile)
            for profile, outcomes in scores.items()
            if len(outcomes) >= self.min_samples
        ]
        if ranked:
            return max(ranked)[1]
        return "side_cylinder" if cls == "cylinder" else "default_cube"

    def get_align_edge_entry(self, feature_key: str) -> AlignCacheEntry | None:
        return self._align_edge_cache.get(feature_key)

    def get_align_plan_entry(self, feature_key: str) -> AlignCacheEntry | None:
        return self._align_plan_cache.get(feature_key)

    def get_align_failure_entry(self, feature_key: str) -> AlignCacheEntry | None:
        return self._align_failure_patterns.get(feature_key)

    def record_align_edge_result(
        self,
        feature_key: str,
        success: bool,
        actual_cost: float,
        planning_time: float = 0.0,
        ik_failures: int = 0,
        ompl_failures: int = 0,
        collisions: int = 0,
        failure_reason: str = "",
        run_id: str = "",
        alpha: float = 0.3,
    ) -> AlignCacheEntry:
        entry = self._align_edge_cache.get(feature_key)
        if entry is None:
            entry = AlignCacheEntry(feature_key=feature_key)
            self._align_edge_cache[feature_key] = entry
        entry.update(
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
        if not success and failure_reason:
            pattern_key = f"{feature_key}:{failure_reason}"
            pattern = self._align_failure_patterns.get(pattern_key)
            if pattern is None:
                pattern = AlignCacheEntry(feature_key=pattern_key)
                self._align_failure_patterns[pattern_key] = pattern
            pattern.update(
                success=False,
                actual_cost=actual_cost,
                failure_reason=failure_reason,
                run_id=run_id,
                alpha=alpha,
            )
        return entry

    def record_align_plan_result(
        self,
        feature_key: str,
        success: bool,
        actual_cost: float,
        planning_time: float = 0.0,
        ik_failures: int = 0,
        ompl_failures: int = 0,
        collisions: int = 0,
        failure_reason: str = "",
        run_id: str = "",
        alpha: float = 0.3,
    ) -> AlignCacheEntry:
        entry = self._align_plan_cache.get(feature_key)
        if entry is None:
            entry = AlignCacheEntry(feature_key=feature_key)
            self._align_plan_cache[feature_key] = entry
        entry.update(
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
        return entry

    def save_align_caches(self) -> None:
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._save_cache_json(
            self.log_dir / "align_edge_cache.json",
            self._align_edge_cache,
        )
        self._save_cache_json(
            self.log_dir / "align_plan_cache.json",
            self._align_plan_cache,
        )
        self._save_cache_json(
            self.log_dir / "align_failure_patterns.json",
            self._align_failure_patterns,
        )

    def _save_cache_json(self, path: Path, cache: dict[str, AlignCacheEntry]) -> None:
        data = {key: entry.to_dict() for key, entry in cache.items()}
        path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")

    def _load_align_caches(self, log_dir: Path) -> None:
        self._align_edge_cache = self._load_cache_json(
            log_dir / "align_edge_cache.json"
        )
        self._align_plan_cache = self._load_cache_json(
            log_dir / "align_plan_cache.json"
        )
        self._align_failure_patterns = self._load_cache_json(
            log_dir / "align_failure_patterns.json"
        )

    @staticmethod
    def _load_cache_json(path: Path) -> dict[str, AlignCacheEntry]:
        if not path.exists():
            return {}
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            return {key: AlignCacheEntry.from_dict(val) for key, val in raw.items()}
        except (json.JSONDecodeError, OSError):
            return {}

    @staticmethod
    def _row_matches_object(row: dict[str, str], obj_id: str) -> bool:
        direct = row.get("object_id")
        if direct:
            return direct == obj_id
        return obj_id in row.get("phase", "")

    @staticmethod
    def _load(log_dir: Path) -> list[dict[str, str]]:
        if not log_dir.exists():
            return []
        rows: list[dict[str, str]] = []
        for path in sorted(log_dir.glob("*_events.csv")) + sorted(
            log_dir.glob("events_*.csv")
        ):
            try:
                with path.open(newline="", encoding="utf-8") as stream:
                    rows.extend(dict(row) for row in csv.DictReader(stream))
            except (OSError, csv.Error):
                continue
        return rows

