"""game/render/glyphs.py — small tool/item glyph icon draw helpers."""
import math
from typing import Tuple, Optional, List

import pygame

__all__ = [
    '_draw_sword_icon',
    '_draw_shield_icon',
    '_draw_hammer_icon',
    '_draw_tongs_icon',
    '_draw_pliers_icon',
    '_draw_wrench_icon',
    '_draw_gear_icon',
    '_draw_potion_icon',
    '_draw_cloth_roll',
    '_draw_hide',
    '_draw_bread',
    '_draw_herb',
    '_draw_fish',
    '_draw_sack',
    '_draw_barrel_icon',
]


def _draw_sword_icon(surface: pygame.Surface, x: int, y: int, scale: float = 1.0) -> None:
    blade_h = int(18 * scale)
    blade_w = max(2, int(3 * scale))
    pygame.draw.rect(surface, (200, 200, 210), (x - blade_w // 2, y - blade_h, blade_w, blade_h))
    pygame.draw.rect(surface, (140, 140, 150), (x - blade_w // 2, y - blade_h, blade_w, blade_h), 1)
    pygame.draw.rect(surface, (140, 110, 70), (x - int(6 * scale), y - int(4 * scale), int(12 * scale), int(3 * scale)))
    pygame.draw.rect(surface, (120, 90, 60), (x - int(1.5 * scale), y - int(2 * scale), int(3 * scale), int(6 * scale)))


def _draw_shield_icon(surface: pygame.Surface, x: int, y: int, scale: float = 1.0) -> None:
    w = int(16 * scale)
    h = int(20 * scale)
    pts = [(x, y - h), (x + w // 2, y - h + 4), (x + w // 2, y - 2), (x, y + 6), (x - w // 2, y - 2), (x - w // 2, y - h + 4)]
    pygame.draw.polygon(surface, (120, 150, 170), pts)
    pygame.draw.polygon(surface, (70, 90, 110), pts, 1)
    pygame.draw.line(surface, (200, 210, 220), (x, y - h + 4), (x, y + 4), 1)


def _draw_hammer_icon(surface: pygame.Surface, x: int, y: int, scale: float = 1.0) -> None:
    head_w = int(14 * scale)
    head_h = int(6 * scale)
    pygame.draw.rect(surface, (140, 150, 160), (x - head_w // 2, y - head_h - 8, head_w, head_h), border_radius=2)
    pygame.draw.rect(surface, (70, 80, 90), (x - head_w // 2, y - head_h - 8, head_w, head_h), 1, border_radius=2)
    handle = pygame.Rect(x - int(2 * scale), y - 8, int(4 * scale), int(16 * scale))
    pygame.draw.rect(surface, (120, 90, 60), handle, border_radius=2)
    pygame.draw.rect(surface, (80, 60, 40), handle, 1, border_radius=2)


def _draw_tongs_icon(surface: pygame.Surface, x: int, y: int, scale: float = 1.0) -> None:
    stem_w = int(2 * scale)
    stem_h = int(16 * scale)
    pygame.draw.rect(surface, (120, 120, 130), (x - 5, y - stem_h, stem_w, stem_h))
    pygame.draw.rect(surface, (120, 120, 130), (x + 3, y - stem_h, stem_w, stem_h))
    pygame.draw.line(surface, (140, 140, 150), (x - 5, y - stem_h), (x - 10, y - stem_h - 4), 2)
    pygame.draw.line(surface, (140, 140, 150), (x + 5, y - stem_h), (x + 10, y - stem_h - 4), 2)


def _draw_pliers_icon(surface: pygame.Surface, x: int, y: int, scale: float = 1.0) -> None:
    pygame.draw.line(surface, (120, 120, 130), (x, y - int(14 * scale)), (x - int(8 * scale), y + int(2 * scale)), 2)
    pygame.draw.line(surface, (120, 120, 130), (x, y - int(14 * scale)), (x + int(8 * scale), y + int(2 * scale)), 2)
    pygame.draw.circle(surface, (80, 80, 90), (x, y - int(14 * scale)), int(2 * scale))


def _draw_wrench_icon(surface: pygame.Surface, x: int, y: int, scale: float = 1.0) -> None:
    pygame.draw.line(surface, (130, 130, 140), (x - int(10 * scale), y - int(10 * scale)), (x + int(8 * scale), y + int(8 * scale)), 3)
    pygame.draw.circle(surface, (150, 150, 160), (x - int(12 * scale), y - int(12 * scale)), int(4 * scale), 1)


def _draw_gear_icon(surface: pygame.Surface, x: int, y: int, scale: float = 1.0) -> None:
    r = int(6 * scale)
    pygame.draw.circle(surface, (120, 120, 130), (x, y), r, 2)
    for ang in range(0, 360, 60):
        rad = math.radians(ang)
        gx = x + int(math.cos(rad) * (r + 3))
        gy = y + int(math.sin(rad) * (r + 3))
        pygame.draw.circle(surface, (140, 140, 150), (gx, gy), max(1, int(2 * scale)))


def _draw_potion_icon(surface: pygame.Surface, x: int, y: int, color: Tuple[int, int, int]) -> None:
    pygame.draw.rect(surface, (40, 40, 50), (x - 4, y - 12, 8, 12), border_radius=2)
    pygame.draw.rect(surface, (200, 200, 210), (x - 2, y - 16, 4, 4))
    pygame.draw.rect(surface, color, (x - 3, y - 8, 6, 6), border_radius=2)


def _draw_cloth_roll(surface: pygame.Surface, x: int, y: int, color: Tuple[int, int, int]) -> None:
    pygame.draw.rect(surface, color, (x - 10, y - 6, 20, 12), border_radius=6)
    pygame.draw.line(surface, (220, 210, 200), (x - 6, y - 6), (x - 6, y + 6), 1)


def _draw_hide(surface: pygame.Surface, x: int, y: int, color: Tuple[int, int, int]) -> None:
    pts = [(x - 12, y - 6), (x - 6, y - 12), (x + 6, y - 12), (x + 12, y - 6), (x + 10, y + 8), (x, y + 12), (x - 10, y + 8)]
    pygame.draw.polygon(surface, color, pts)
    pygame.draw.polygon(surface, (60, 45, 30), pts, 1)


def _draw_bread(surface: pygame.Surface, x: int, y: int) -> None:
    pygame.draw.rect(surface, (190, 150, 90), (x - 10, y - 6, 20, 12), border_radius=6)
    pygame.draw.line(surface, (230, 210, 160), (x - 6, y - 2), (x + 6, y - 2), 1)


def _draw_herb(surface: pygame.Surface, x: int, y: int) -> None:
    pygame.draw.line(surface, (80, 140, 80), (x, y + 6), (x, y - 8), 2)
    pygame.draw.circle(surface, (120, 190, 120), (x - 4, y - 6), 3)
    pygame.draw.circle(surface, (120, 190, 120), (x + 4, y - 4), 3)


def _draw_fish(surface: pygame.Surface, x: int, y: int) -> None:
    pygame.draw.ellipse(surface, (120, 160, 190), (x - 10, y - 4, 18, 8))
    pygame.draw.polygon(surface, (100, 130, 160), [(x + 8, y), (x + 14, y - 4), (x + 14, y + 4)])
    pygame.draw.circle(surface, (20, 20, 30), (x - 4, y - 1), 1)


def _draw_sack(surface: pygame.Surface, x: int, y: int) -> None:
    pygame.draw.rect(surface, (170, 140, 100), (x - 8, y - 10, 16, 16), border_radius=4)
    pygame.draw.line(surface, (120, 90, 60), (x - 6, y - 2), (x + 6, y - 2), 1)


def _draw_barrel_icon(surface: pygame.Surface, x: int, y: int) -> None:
    pygame.draw.rect(surface, (110, 80, 50), (x - 8, y - 12, 16, 20), border_radius=4)
    pygame.draw.rect(surface, (70, 50, 30), (x - 8, y - 12, 16, 20), 1, border_radius=4)
    pygame.draw.line(surface, (160, 130, 90), (x - 8, y - 4), (x + 8, y - 4), 1)
    pygame.draw.line(surface, (160, 130, 90), (x - 8, y + 4), (x + 8, y + 4), 1)
