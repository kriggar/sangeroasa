"""
game/utils.py
Pure math / geometry utility functions for Sangeroasa.
No pygame, no game state — safe to import anywhere.
"""
from __future__ import annotations
import math
from typing import Tuple


def clamp(value: float, lo: float, hi: float) -> float:
    """Clamp value into [lo, hi]."""
    return max(lo, min(hi, value))


def lerp(a: float, b: float, t: float) -> float:
    """Linear interpolation between a and b by t in [0, 1]."""
    return a + (b - a) * clamp(t, 0.0, 1.0)


def exp_smooth(current: float, target: float, sharpness: float, dt: float) -> float:
    """Framerate-independent exponential approach of current toward target."""
    if dt <= 0.0:
        return float(current)
    weight = 1.0 - math.exp(-max(0.0, float(sharpness)) * dt)
    return float(current) + (float(target) - float(current)) * weight


def rotate_vec(v: "pygame.Vector2", angle_rad: float) -> "pygame.Vector2":  # type: ignore[name-defined]
    """Rotate a Vector2 by angle_rad radians."""
    from pygame import Vector2  # local import to keep this module lightweight
    c, s = math.cos(angle_rad), math.sin(angle_rad)
    return Vector2(v.x * c - v.y * s, v.x * s + v.y * c)


def hsv_to_rgb(h: float, s: float, v: float) -> Tuple[int, int, int]:
    """Convert HSV (0-1 each) to RGB (0-255 each)."""
    import colorsys
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return int(r * 255), int(g * 255), int(b * 255)


def point_in_rect(px: float, py: float, rx: float, ry: float, rw: float, rh: float) -> bool:
    return rx <= px < rx + rw and ry <= py < ry + rh
