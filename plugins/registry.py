from __future__ import annotations

import importlib
import pkgutil

from plugins.protocol import TaskPlugin


TASK_PLUGIN_API_VERSION = "ctamp-task/v2"


class PluginRegistry:
    def __init__(self):
        self._plugins: dict[str, TaskPlugin] = {}

    def register(self, plugin: TaskPlugin) -> None:
        if getattr(plugin, "api_version", None) != TASK_PLUGIN_API_VERSION:
            raise ValueError(
                f"task plugin {getattr(plugin, 'name', '<unknown>')!r} uses "
                f"unsupported API {getattr(plugin, 'api_version', None)!r}; "
                f"expected {TASK_PLUGIN_API_VERSION!r}"
            )
        if not getattr(plugin, "name", ""):
            raise ValueError("task plugin name must not be empty")
        required_methods = (
            "validate_plan",
            "make_slot_config",
            "configure_runtime",
            "assess_progress",
            "verify_goal",
        )
        missing = [name for name in required_methods if not callable(getattr(plugin, name, None))]
        if missing:
            raise ValueError(
                f"task plugin {plugin.name!r} is missing methods: {', '.join(missing)}"
            )
        if plugin.name in self._plugins:
            raise ValueError(f"task plugin {plugin.name!r} is already registered")
        self._plugins[plugin.name] = plugin

    def get(self, task_name: str) -> TaskPlugin:
        if task_name not in self._plugins:
            raise ValueError(
                f"Task {task_name!r} tidak terdaftar. "
                f"Tersedia: {sorted(self._plugins)}. "
                "Tambahkan modul '*_task.py' dengan export PLUGIN yang "
                "mengimplementasikan TaskPlugin."
            )
        return self._plugins[task_name]

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._plugins))

    @classmethod
    def discover(cls, package_name: str = "plugins") -> "PluginRegistry":
        """Discover trusted built-in task modules in deterministic name order."""
        package = importlib.import_module(package_name)
        package_paths = getattr(package, "__path__", None)
        if package_paths is None:
            raise ValueError(f"plugin package {package_name!r} has no package path")
        registry = cls()
        module_names = sorted(
            info.name
            for info in pkgutil.iter_modules(package_paths)
            if info.name.endswith("_task")
        )
        for module_name in module_names:
            module = importlib.import_module(f"{package_name}.{module_name}")
            plugin = getattr(module, "PLUGIN", None)
            if plugin is None:
                raise ValueError(
                    f"plugin module {module.__name__!r} must export PLUGIN"
                )
            registry.register(plugin)
        return registry


DEFAULT_REGISTRY = PluginRegistry.discover()
