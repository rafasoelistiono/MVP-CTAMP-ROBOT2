from __future__ import annotations

import math

from task_planning.types import SlotConfig

from .state import WorldState


class SlotAllocationError(ValueError):
    pass


def allocate_slots(
    config: SlotConfig,
    n: int,
) -> dict[str, tuple[float, float, float]]:
    if n <= 0:
        raise SlotAllocationError("slot count must be positive")
    if config.type == "line":
        return _allocate_line(config, n)
    if config.type == "tower":
        return _allocate_tower(config, n)
    raise SlotAllocationError(f"unknown slot type: {config.type}")


def _allocate_line(
    config: SlotConfig,
    n: int,
) -> dict[str, tuple[float, float, float]]:
    if config.axis != "x":
        raise SlotAllocationError("only line axis 'x' is currently supported")
    total_width = (n - 1) * config.spacing_m
    start_x = config.center_x - total_width / 2.0
    return {
        f"slot_{index}": (
            start_x + index * config.spacing_m,
            config.row_y,
            config.base_z,
        )
        for index in range(n)
    }


def _allocate_tower(
    config: SlotConfig,
    n: int,
) -> dict[str, tuple[float, float, float]]:
    bx, by = config.base_xy
    slots: dict[str, tuple[float, float, float]] = {}
    for index in range(n):
        label = "tower_base" if index == 0 else f"level_{index}"
        slots[label] = (
            bx,
            by,
            config.base_z + index * config.layer_height_m,
        )
    return slots


def validate_slots(
    slots: dict[str, tuple[float, float, float]],
    world: WorldState,
    obstacle_buffer_m: float = 0.13,
) -> None:
    for slot_id, pose in slots.items():
        x, y, z = pose
        if not (world.table_x_range[0] < x < world.table_x_range[1]):
            raise SlotAllocationError(f"{slot_id} x={x:.4f} is outside table bounds")
        if not (world.table_y_range[0] < y < world.table_y_range[1]):
            raise SlotAllocationError(f"{slot_id} y={y:.4f} is outside table bounds")
        distance = math.dist((x, y), world.robot_base_xy)
        if not world.robot_reach_min <= distance <= world.robot_reach_max:
            raise SlotAllocationError(
                f"{slot_id} is outside robot reach: distance={distance:.4f}"
            )
        if z < world.table_z_top:
            raise SlotAllocationError(
                f"{slot_id} z={z:.4f} is below table top {world.table_z_top:.4f}"
            )
        for obstacle in world.obstacles:
            clearance = math.dist((x, y), obstacle.pose[:2])
            if clearance < obstacle.radius + obstacle_buffer_m:
                raise SlotAllocationError(
                    f"{slot_id} violates inflated obstacle region for {obstacle.id}: "
                    f"clearance={clearance:.4f}"
                )
