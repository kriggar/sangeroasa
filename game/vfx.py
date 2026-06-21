"""game/vfx.py — particle & floating-damage-number spawn/update/draw helpers.
Pure: the particle/damage buckets are passed in as parameters; no global game state."""
import math
import random
from typing import Dict, List, Optional, Tuple, Any

import pygame
from pygame import Vector2

from game.utils import clamp, rotate_vec, color_lerp


def spawn_particle_burst(
    bucket: List[Dict[str, object]],
    pos: Vector2,
    core_color: Tuple[int, int, int],
    accent_color: Tuple[int, int, int],
    count: int,
    speed_min: float,
    speed_max: float,
    life_min: float,
    life_max: float,
    size_start: float,
    size_end: float,
    spread: float = math.tau,
    direction: Optional[Vector2] = None,
    gravity: float = 0.0,
    drag: float = 0.0,
    vfx_scale: float = 1.0,
) -> None:
    scaled = int(round(count * clamp(vfx_scale, 0.5, 3.8)))
    scaled = max(1, min(64, scaled))
    use_dir = Vector2(direction) if isinstance(direction, Vector2) and direction.length_squared() > 1e-6 else None
    if isinstance(use_dir, Vector2):
        use_dir = use_dir.normalize()
    for _ in range(scaled):
        if isinstance(use_dir, Vector2):
            off = (random.random() - 0.5) * spread
            dir_vec = rotate_vec(use_dir, off)
        else:
            ang = random.random() * math.tau
            dir_vec = Vector2(math.cos(ang), math.sin(ang))
        spd = random.uniform(speed_min, speed_max)
        life = random.uniform(life_min, life_max)
        hue_mix = random.random()
        col = color_lerp(core_color, accent_color, hue_mix)
        bucket.append(
            {
                "kind": "particle",
                "pos": Vector2(pos),
                "vel": dir_vec * spd,
                "life": life,
                "duration": life,
                "size0": max(0.8, size_start * random.uniform(0.85, 1.25)),
                "size1": max(0.2, size_end * random.uniform(0.8, 1.2)),
                "color": col,
                "glow": accent_color,
                "gravity": gravity,
                "drag": drag,
                "alpha": random.randint(170, 255),
            }
        )


def spawn_blood_splatter(
    bucket: List[Dict[str, object]],
    pos: Vector2,
    intensity: float = 1.0,
) -> None:
    strength = clamp(intensity, 0.5, 2.4)
    drop_count = max(4, min(12, int(round(5 + strength * 3.2))))
    drops: List[Tuple[float, float, float]] = []
    spread_x = 24.0 * strength
    spread_y = 12.0 * strength
    for _ in range(drop_count):
        ox = random.uniform(-spread_x, spread_x)
        oy = random.uniform(-spread_y, spread_y)
        r = random.uniform(2.0, 5.8) * (0.8 + strength * 0.28)
        drops.append((ox, oy, r))
    bucket.append(
        {
            "kind": "blood_splatter",
            "pos": Vector2(pos.x, pos.y + 3.0),
            "life": random.uniform(7.0, 12.0),
            "duration": random.uniform(7.0, 12.0),
            "drops": drops,
        }
    )


def spawn_damage_number(
    damage_numbers: List[Dict[str, object]],
    pos: Vector2,
    amount: float,
    kind: str = "outgoing",
) -> None:
    value = max(0, int(round(float(amount))))
    if value <= 0:
        return
    if str(kind) == "incoming":
        color = (236, 112, 104)
        outline = (78, 22, 18)
        text = f"-{value}"
        life = 0.88
        spread = 8.0
        rise = 68.0
    else:
        color = (246, 220, 126)
        outline = (74, 54, 16)
        text = str(value)
        life = 0.84
        spread = 14.0
        rise = 78.0
    damage_numbers.append(
        {
            "pos": Vector2(pos.x + random.uniform(-spread, spread), pos.y - random.uniform(24.0, 34.0)),
            "vel": Vector2(random.uniform(-18.0, 18.0), -rise - random.uniform(0.0, 14.0)),
            "life": life,
            "duration": life,
            "text": text,
            "color": color,
            "outline": outline,
        }
    )


def update_damage_numbers(damage_numbers: List[Dict[str, object]], dt: float) -> None:
    if dt <= 0.0 or not damage_numbers:
        return
    keep: List[Dict[str, object]] = []
    for entry in damage_numbers:
        life = float(entry.get("life", 0.0)) - dt
        if life <= 0.0:
            continue
        entry["life"] = life
        pos = entry.get("pos")
        vel = entry.get("vel")
        if isinstance(pos, Vector2) and isinstance(vel, Vector2):
            vel.y += 92.0 * dt
            vel.x *= max(0.0, 1.0 - dt * 2.3)
            entry["vel"] = vel
            entry["pos"] = pos + vel * dt
        keep.append(entry)
    damage_numbers[:] = keep


def draw_damage_numbers(
    surface: pygame.Surface,
    damage_numbers: List[Dict[str, object]],
    camera: Vector2,
    font: pygame.font.Font,
) -> None:
    for entry in damage_numbers:
        text = str(entry.get("text", ""))
        pos = entry.get("pos")
        if not text or not isinstance(pos, Vector2):
            continue
        life = float(entry.get("life", 0.0))
        duration = max(0.001, float(entry.get("duration", 1.0)))
        fade = clamp(life / duration, 0.0, 1.0)
        alpha = int(255 * (fade ** 0.75))
        if alpha <= 1:
            continue
        color = entry.get("color", (236, 224, 196))
        outline = entry.get("outline", (24, 16, 12))
        if not (isinstance(color, tuple) and len(color) == 3):
            color = (236, 224, 196)
        if not (isinstance(outline, tuple) and len(outline) == 3):
            outline = (24, 16, 12)
        sx = int(pos.x - camera.x)
        sy = int(pos.y - camera.y)
        if "surf_shadow" not in entry:
            entry["surf_shadow"] = font.render(text, True, outline)
            entry["surf_label"] = font.render(text, True, color)
        shadow = entry["surf_shadow"]
        label = entry["surf_label"]
        shadow.set_alpha(alpha)
        label.set_alpha(alpha)
        surface.blit(shadow, (sx - shadow.get_width() // 2 + 1, sy - shadow.get_height() // 2 + 1))
        surface.blit(label, (sx - label.get_width() // 2, sy - label.get_height() // 2))
