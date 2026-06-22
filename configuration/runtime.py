from __future__ import annotations

from .loader import load_runtime_config
from .types import RuntimeConfig


_active_config: RuntimeConfig | None = None


def activate_runtime_config(config: RuntimeConfig) -> RuntimeConfig:
    global _active_config
    _active_config = config.validate()
    return _active_config


def get_active_runtime_config() -> RuntimeConfig:
    global _active_config
    if _active_config is None:
        _active_config = load_runtime_config()
    return _active_config


def clear_runtime_config() -> None:
    global _active_config
    _active_config = None

