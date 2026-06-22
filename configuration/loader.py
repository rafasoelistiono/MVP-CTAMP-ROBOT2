from __future__ import annotations

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib
from dataclasses import fields, is_dataclass, replace
from pathlib import Path
from typing import Any

from .defaults import DEFAULT_PROFILE_REGISTRY, ROOT_DIR, RuntimeProfileRegistry
from .types import RuntimeConfig


class RuntimeConfigError(ValueError):
    pass


def load_runtime_config(
    profile: str = "conservative",
    *,
    config_file: str | Path | None = None,
    model_file: str | Path | None = None,
    enable_viewer: bool | None = None,
    registry: RuntimeProfileRegistry = DEFAULT_PROFILE_REGISTRY,
) -> RuntimeConfig:
    selected = registry.get(profile)
    if config_file is not None:
        path = Path(config_file).resolve()
        try:
            with path.open("rb") as stream:
                payload = tomllib.load(stream)
        except FileNotFoundError as exc:
            raise RuntimeConfigError(f"runtime config file does not exist: {path}") from exc
        if not isinstance(payload, dict):
            raise RuntimeConfigError("runtime config root must be a TOML table")
        extends = str(payload.pop("extends", profile))
        selected = registry.get(extends)
        selected = _overlay(selected, payload, path)
    if model_file is not None:
        model_path = Path(model_file)
        if not model_path.is_absolute():
            model_path = ROOT_DIR / model_path
        selected = replace(selected, model=replace(selected.model, xml_path=model_path))
    if enable_viewer is not None:
        selected = replace(selected, enable_viewer=bool(enable_viewer))
    return selected.validate()


def _overlay(config: RuntimeConfig, payload: dict[str, Any], source: Path) -> RuntimeConfig:
    allowed = {field.name for field in fields(config)}
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise RuntimeConfigError(
            f"{source}: unsupported root fields: {', '.join(unknown)}"
        )
    updates: dict[str, Any] = {}
    for key, value in payload.items():
        current = getattr(config, key)
        if is_dataclass(current):
            if not isinstance(value, dict):
                raise RuntimeConfigError(f"{source}: [{key}] must be a TOML table")
            updates[key] = _overlay_dataclass(current, value, f"{source} [{key}]")
        elif key == "name":
            updates[key] = str(value)
        elif key == "enable_viewer":
            if not isinstance(value, bool):
                raise RuntimeConfigError(f"{source}: enable_viewer must be boolean")
            updates[key] = value
    return replace(config, **updates)


def _overlay_dataclass(current, payload: dict[str, Any], path: str):
    allowed = {field.name for field in fields(current)}
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise RuntimeConfigError(f"{path}: unsupported fields: {', '.join(unknown)}")
    updates: dict[str, Any] = {}
    for key, value in payload.items():
        previous = getattr(current, key)
        if isinstance(previous, Path):
            candidate = Path(str(value))
            updates[key] = candidate if candidate.is_absolute() else ROOT_DIR / candidate
        elif isinstance(previous, tuple):
            if not isinstance(value, list):
                raise RuntimeConfigError(f"{path}.{key} must be a TOML array")
            updates[key] = tuple(value)
        elif isinstance(previous, bool):
            if not isinstance(value, bool):
                raise RuntimeConfigError(f"{path}.{key} must be boolean")
            updates[key] = value
        elif isinstance(previous, int):
            if not isinstance(value, int):
                raise RuntimeConfigError(f"{path}.{key} must be integer")
            updates[key] = value
        elif isinstance(previous, float):
            if not isinstance(value, (int, float)):
                raise RuntimeConfigError(f"{path}.{key} must be numeric")
            updates[key] = float(value)
        else:
            updates[key] = str(value)
    return replace(current, **updates)
