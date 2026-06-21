"""game/gameplay_math.py — small gameplay math/geometry helpers + spell VFX theme data."""
import math
from typing import Dict, List, Optional, Tuple, Any, Union

from pygame import Vector2

__all__ = [
    'quadratic_bezier',
    'solve_two_bone',
    'facing_to_direction',
    'xp_required_for_level',
    'level_progression_bonus',
    'CLASS_SPELL_VFX_THEMES',
    'spell_class_id',
]


def facing_to_direction(facing: int, default: str = "right") -> str:
    if int(facing) > 0:
        return "right"
    if int(facing) < 0:
        return "left"
    return default


def xp_required_for_level(level: int) -> int:
    lvl = max(1, int(level))
    step = lvl - 1
    return int(90 + step * 55 + (step * step) * 12)


def level_progression_bonus(level: int) -> Tuple[float, float, float]:
    lvl = max(1, int(level))
    hp_bonus = 0.0
    mana_bonus = 0.0
    regen_bonus = 0.0
    for lv in range(2, lvl + 1):
        hp_bonus += 9.0 + (lv // 3)
        mana_bonus += 6.0 + (lv // 4)
        regen_bonus += 0.14
    return hp_bonus, mana_bonus, regen_bonus


# rotate_vec is imported from game.utils (see top of file).


CLASS_SPELL_VFX_THEMES: Dict[str, Dict[str, Tuple[int, int, int]]] = {
    "mage": {"core": (108, 196, 252), "accent": (214, 238, 255), "shadow": (84, 126, 214)},
    "ranger": {"core": (138, 196, 118), "accent": (220, 244, 178), "shadow": (74, 114, 56)},
    "necromancer": {"core": (176, 140, 224), "accent": (234, 208, 255), "shadow": (102, 74, 146)},
    "warrior": {"core": (232, 150, 92), "accent": (255, 214, 158), "shadow": (138, 84, 46)},
    "paladin": {"core": (246, 220, 134), "accent": (255, 246, 188), "shadow": (182, 144, 72)},
}


def spell_class_id(spell_id: str) -> str:
    sid = str(spell_id).strip().lower()
    if sid.startswith("necro_"):
        return "necromancer"
    for prefix in ("mage", "rogue", "ranger", "warrior", "paladin", "necromancer"):
        if sid.startswith(f"{prefix}_"):
            return prefix
    return ""


def quadratic_bezier(p0: Vector2, p1: Vector2, p2: Vector2, t: float) -> Vector2:
    u = 1.0 - t
    return p0 * (u * u) + p1 * (2.0 * u * t) + p2 * (t * t)


def solve_two_bone(
    root: Vector2,
    target: Vector2,
    length_a: float,
    length_b: float,
    bend_dir: float = 1.0,
) -> Vector2:
    delta = target - root
    dist = delta.length()
    if dist <= 1e-6:
        return root + Vector2(0.0, length_a)

    min_reach = abs(length_a - length_b) + 1e-3
    max_reach = (length_a + length_b) - 1e-3
    clamped_dist = clamp(dist, min_reach, max_reach)
    direction = delta / dist

    a = (length_a * length_a - length_b * length_b + clamped_dist * clamped_dist) / (2.0 * clamped_dist)
    h_sq = max(length_a * length_a - a * a, 0.0)
    h = math.sqrt(h_sq)

    mid = root + direction * a
    perp = Vector2(-direction.y, direction.x) * bend_dir
    return mid + perp * h
