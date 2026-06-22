from __future__ import annotations

import pytest

from task_planning.types import SlotConfig
from world.slot_allocator import allocate_slots


def test_align_four_cube_coordinates():
    slots = allocate_slots(
        SlotConfig(
            type="line",
            spacing_m=0.125,
            center_x=0.22,
            row_y=-0.06,
            base_z=0.83,
        ),
        4,
    )
    assert [slots[f"slot_{i}"][0] for i in range(4)] == pytest.approx(
        [0.0325, 0.1575, 0.2825, 0.4075]
    )


def test_stack_four_cube_coordinates():
    slots = allocate_slots(
        SlotConfig(
            type="tower",
            base_xy=(0.22, -0.06),
            base_z=0.83,
            layer_height_m=0.06,
        ),
        4,
    )
    assert [slots[label][2] for label in ("tower_base", "level_1", "level_2", "level_3")] == pytest.approx(
        [0.83, 0.89, 0.95, 1.01]
    )
