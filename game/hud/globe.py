"""Ornate HUD globe renderer (HP/MP gemstone orbs).

Extracted from main.py. Public surface:
  - HUD_ORB_R, HUD_GLOBE_STYLES
  - build_hud_globe_frame(style)       — cached static brass bezel
  - build_hud_gem_fill(style, orb_r)   — cached radial gemstone gradient
  - get_globe_value_font()             — cached compact value font
  - get_potion_keybind_font()          — cached small potion keybind font
  - draw_hud_globe(...)                — per-frame draw of one globe
"""
from __future__ import annotations

import math
from typing import Dict, Optional, Tuple

import pygame

from game.utils import clamp


HUD_ORB_R = 38

HUD_GLOBE_STYLES: Dict[str, Dict[str, Tuple[int, int, int]]] = {
    "hp": {
        "top":    (255, 124,  96),
        "mid":    (198,  32,  32),
        "bot":    ( 70,   8,  12),
        "aura":   (230,  50,  40),
        "jewel":  (255,  80,  60),
        "jewelD": (120,  10,  10),
        "text":   (252, 232, 212),
    },
    "mp": {
        "top":    (180, 226, 255),
        "mid":    ( 60, 130, 230),
        "bot":    ( 10,  22,  78),
        "aura":   ( 60, 120, 240),
        "jewel":  ( 90, 180, 255),
        "jewelD": ( 20,  40, 120),
        "text":   (222, 238, 255),
    },
}

_FRAME_CACHE: Dict[str, pygame.Surface] = {}
_GEM_CACHE: Dict[str, pygame.Surface] = {}
_AURA_CACHE: Dict[str, pygame.Surface] = {}
_GLOW_CACHE: Dict[int, pygame.Surface] = {}
_DOME_CACHE: Dict[int, pygame.Surface] = {}
_CIRC_MASK_CACHE: Dict[int, pygame.Surface] = {}
_VALUE_FONT: Optional[pygame.font.Font] = None
_POTION_KEY_FONT: Optional[pygame.font.Font] = None

_AURA_MAX_PULSE = 2.2


def _build_aura(style: str) -> pygame.Surface:
    cached = _AURA_CACHE.get(style)
    if cached is not None:
        return cached
    palette = HUD_GLOBE_STYLES[style]
    aura_col = palette["aura"]
    orb_r = HUD_ORB_R
    _scale = orb_r / 60.0
    aura_outer = orb_r + max(8, int(22 * _scale))
    size = aura_outer * 2 + 4
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    c = size // 2
    base_a = int(55 * _AURA_MAX_PULSE)
    for _rr in range(aura_outer, orb_r - 2, -1):
        _falloff = (_rr - (orb_r - 2)) / max(1, aura_outer - (orb_r - 2))
        _a = int(((1.0 - _falloff) ** 2.1) * base_a)
        if _a > 0:
            pygame.draw.circle(surf, (*aura_col, _a), (c, c), _rr)
    _AURA_CACHE[style] = surf.convert_alpha()
    return _AURA_CACHE[style]


def _build_glow(orb_r: int) -> pygame.Surface:
    cached = _GLOW_CACHE.get(orb_r)
    if cached is not None:
        return cached
    size = orb_r * 2 + 2
    half = size // 2
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    gcx, gcy = half - int(orb_r * 0.12), half - int(orb_r * 0.18)
    glow_r = int(orb_r * 0.45)
    for _rr in range(glow_r, 0, -1):
        _t = 1.0 - (_rr / glow_r)
        _a = int(65 * _t * _t)
        if _a > 0:
            pygame.draw.circle(surf, (255, 255, 255, _a), (gcx, gcy), _rr)
    _GLOW_CACHE[orb_r] = surf.convert_alpha()
    return _GLOW_CACHE[orb_r]


def _build_dome_static(orb_r: int) -> pygame.Surface:
    cached = _DOME_CACHE.get(orb_r)
    if cached is not None:
        return cached
    size = orb_r * 2 + 2
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.ellipse(surf, (255, 255, 255, 38),
        pygame.Rect(orb_r - int(orb_r * 0.72), orb_r - int(orb_r * 0.88),
                    int(orb_r * 1.44), int(orb_r * 0.88)))
    pygame.draw.ellipse(surf, (255, 255, 255, 80),
        pygame.Rect(orb_r - int(orb_r * 0.38), orb_r - int(orb_r * 0.72),
                    int(orb_r * 0.76), int(orb_r * 0.44)))
    pygame.draw.ellipse(surf, (255, 255, 255, 160),
        pygame.Rect(orb_r - int(orb_r * 0.15), orb_r - int(orb_r * 0.62),
                    int(orb_r * 0.30), int(orb_r * 0.16)))
    pygame.draw.ellipse(surf, (0, 0, 0, 45),
        pygame.Rect(3, orb_r + int(orb_r * 0.5), size - 6, int(orb_r * 0.7)))
    surf.blit(_build_circle_mask(orb_r), (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    _DOME_CACHE[orb_r] = surf.convert_alpha()
    return _DOME_CACHE[orb_r]


def _build_circle_mask(orb_r: int) -> pygame.Surface:
    cached = _CIRC_MASK_CACHE.get(orb_r)
    if cached is not None:
        return cached
    size = orb_r * 2 + 2
    half = size // 2
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.circle(surf, (255, 255, 255, 255), (half, half), orb_r - 1)
    _CIRC_MASK_CACHE[orb_r] = surf.convert_alpha()
    return _CIRC_MASK_CACHE[orb_r]


def build_hud_globe_frame(style: str) -> pygame.Surface:
    """Build the static multi-ring bronze/gold bezel for one globe style (cached)."""
    cached = _FRAME_CACHE.get(style)
    if cached is not None:
        return cached
    r = HUD_ORB_R
    _s = r / 60.0
    margin = int(30 * _s)
    size = r * 2 + margin * 2
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    cx = cy = size // 2
    palette = HUD_GLOBE_STYLES[style]

    pygame.draw.circle(surf, (  4,   2,   2), (cx, cy), r + int(10 * _s), 1)
    pygame.draw.circle(surf, ( 22,  16,  10), (cx, cy), r + int( 9 * _s), max(1, int(2 * _s)))
    pygame.draw.circle(surf, ( 50,  36,  20), (cx, cy), r + int( 8 * _s), max(1, int(3 * _s)))
    pygame.draw.circle(surf, ( 94,  70,  32), (cx, cy), r + int( 6 * _s), max(1, int(1.5 * _s)))
    pygame.draw.circle(surf, (168, 126,  54), (cx, cy), r + int( 5 * _s), 1)
    pygame.draw.circle(surf, (226, 184,  94), (cx, cy), r + int( 4 * _s), 1)
    pygame.draw.circle(surf, ( 76,  54,  26), (cx, cy), r + int( 2 * _s), max(1, int(1.5 * _s)))
    pygame.draw.circle(surf, (  8,   6,   4), (cx, cy), r + 1, max(1, int(1.5 * _s)))

    _rivet_count = max(8, int(16 * _s))
    _rivet_orbit = r + int(6 * _s)
    _rivet_r = max(1, int(2 * _s))
    for i in range(_rivet_count):
        ang = (i / _rivet_count) * 2 * math.pi - math.pi / 2
        rx = cx + int(_rivet_orbit * math.cos(ang))
        ry = cy + int(_rivet_orbit * math.sin(ang))
        pygame.draw.circle(surf, (  8,   6,   4), (rx, ry), _rivet_r + 1)
        pygame.draw.circle(surf, (178, 136,  60), (rx, ry), _rivet_r)
        if _rivet_r >= 2:
            pygame.draw.circle(surf, (254, 224, 150), (rx - 1, ry - 1), 1)

    jewel_col  = palette["jewel"]
    jewel_dark = palette["jewelD"]
    _jewel_orbit = r + int(8 * _s)
    _jewel_r = max(2, int(5 * _s))
    for ang in (-math.pi / 2, 0.0, math.pi / 2, math.pi):
        jx = cx + int(_jewel_orbit * math.cos(ang))
        jy = cy + int(_jewel_orbit * math.sin(ang))
        pygame.draw.circle(surf, (  4,   2,   2), (jx, jy), _jewel_r + 2)
        pygame.draw.circle(surf, ( 26,  18,  10), (jx, jy), _jewel_r + 1)
        pygame.draw.circle(surf, (158, 118,  52), (jx, jy), _jewel_r + 1, 1)
        pygame.draw.circle(surf, jewel_dark,      (jx, jy), _jewel_r)
        pygame.draw.circle(surf, jewel_col,       (jx, jy), max(1, _jewel_r - 1))
        pygame.draw.circle(surf, (255, 255, 255), (jx - 1, jy - 1), 1)

    _FRAME_CACHE[style] = surf.convert_alpha()
    return _FRAME_CACHE[style]


def build_hud_gem_fill(style: str, orb_r: int) -> pygame.Surface:
    """Pre-rendered radial gemstone gradient for a globe style. Cached forever."""
    key = f"{style}:{orb_r}"
    cached = _GEM_CACHE.get(key)
    if isinstance(cached, pygame.Surface):
        return cached
    palette = HUD_GLOBE_STYLES[style]
    fill_top = palette["top"]
    fill_mid = palette["mid"]
    fill_bot = palette["bot"]
    size = orb_r * 2 + 2
    half = size // 2
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    gcx, gcy = half - int(orb_r * 0.12), half - int(orb_r * 0.18)
    max_dist = orb_r * 1.15
    for yy in range(size):
        for xx in range(size):
            dx = xx - gcx
            dy = yy - gcy
            dist = math.sqrt(dx * dx + dy * dy)
            t = min(1.0, dist / max_dist)
            t3 = t * t
            if t3 < 0.35:
                u = t3 / 0.35
                c = (
                    int(fill_top[0] + (fill_mid[0] - fill_top[0]) * u),
                    int(fill_top[1] + (fill_mid[1] - fill_top[1]) * u),
                    int(fill_top[2] + (fill_mid[2] - fill_top[2]) * u),
                )
            else:
                u = min(1.0, (t3 - 0.35) / 0.65)
                c = (
                    int(fill_mid[0] + (fill_bot[0] - fill_mid[0]) * u),
                    int(fill_mid[1] + (fill_bot[1] - fill_mid[1]) * u),
                    int(fill_mid[2] + (fill_bot[2] - fill_mid[2]) * u),
                )
            surf.set_at((xx, yy), (*c, 255))
    _GEM_CACHE[key] = surf.convert_alpha()
    return _GEM_CACHE[key]


def get_globe_value_font() -> pygame.font.Font:
    global _VALUE_FONT
    if _VALUE_FONT is None:
        _VALUE_FONT = pygame.font.SysFont("consolas", 13, bold=True)
    return _VALUE_FONT


def get_potion_keybind_font() -> pygame.font.Font:
    global _POTION_KEY_FONT
    if _POTION_KEY_FONT is None:
        _POTION_KEY_FONT = pygame.font.SysFont("consolas", 10, bold=False)
    return _POTION_KEY_FONT


def draw_hud_globe(
    screen: pygame.Surface,
    center: Tuple[int, int],
    ratio: float,
    style: str,
    value_text: str,
    seed: int,
    tiny_font: pygame.font.Font,
    extra_pulse: float = 0.0,
    flash: float = 0.0,
) -> None:
    """Render one ornate gemstone-style globe at `center`.

    The gemstone fill drains from the top down as `ratio` drops, with a
    shimmering meniscus where the liquid meets the air. Dome highlights,
    pulsing aura, sparkles and the cached ornate bezel sit on top.
    """
    ticks = pygame.time.get_ticks()
    t_sec = ticks / 1000.0
    orb_r = HUD_ORB_R
    cx, cy = center
    size = orb_r * 2 + 2
    half = size // 2
    palette = HUD_GLOBE_STYLES[style]
    fill_top = palette["top"]
    aura_col = palette["aura"]
    text_col = palette["text"]

    ratio = clamp(float(ratio), 0.0, 1.0)
    fill_sway = math.sin(t_sec * 1.8 + seed * 0.7) * (orb_r * 0.02)
    fill_y = int((half - orb_r) + (1.0 - ratio) * (orb_r * 2) + fill_sway)

    # Pulsing outer aura (cached base, dynamic alpha)
    _aura_surf = _build_aura(style)
    _aw = _aura_surf.get_width()
    _breath = 0.55 + 0.45 * (0.5 + 0.5 * math.sin(t_sec * 1.3 + seed))
    _pulse = min(_AURA_MAX_PULSE, _breath + extra_pulse * 1.3 + flash * 0.9)
    _aura_surf.set_alpha(int(255 * _pulse / _AURA_MAX_PULSE))
    screen.blit(_aura_surf, (cx - _aw // 2, cy - _aw // 2))

    # Dark socket
    pygame.draw.circle(screen, (6, 3, 5), (cx, cy), orb_r)
    pygame.draw.circle(screen, (14, 8, 12), (cx, cy), orb_r - 2)

    # Gemstone fill (cached)
    orb_surf = build_hud_gem_fill(style, orb_r).copy()

    # Inner pulsing glow (cached base, alpha modulated)
    glow_base = _build_glow(orb_r)
    glow_pulse = 0.7 + 0.3 * math.sin(t_sec * 2.0 + seed * 0.5)
    glow_base.set_alpha(int(255 * glow_pulse))
    orb_surf.blit(glow_base, (0, 0))

    # Energy swirl
    swirl_surf = pygame.Surface((size, size), pygame.SRCALPHA)
    for i in range(2):
        angle = t_sec * (0.8 + i * 0.3) + seed + i * math.pi
        arc_r = int(orb_r * (0.5 + 0.15 * i))
        arc_cx = half + int(math.cos(angle) * arc_r * 0.35)
        arc_cy = half + int(math.sin(angle) * arc_r * 0.35)
        arc_w = int(orb_r * 0.55)
        arc_h = int(orb_r * 0.25)
        a_alpha = int(32 + 18 * math.sin(t_sec * 1.5 + i * 1.7))
        rect = pygame.Rect(arc_cx - arc_w // 2, arc_cy - arc_h // 2, arc_w, arc_h)
        pygame.draw.ellipse(swirl_surf, (*fill_top, a_alpha), rect)
    orb_surf.blit(swirl_surf, (0, 0))

    # Drifting sparkles
    for si in range(4):
        sp_angle = t_sec * 0.4 + si * (math.pi / 2) + seed * 0.3
        sp_r = orb_r * (0.3 + 0.25 * math.sin(t_sec * 0.7 + si * 1.1))
        sp_x = int(half + math.cos(sp_angle) * sp_r)
        sp_y = int(half + math.sin(sp_angle) * sp_r)
        sp_bright = 0.5 + 0.5 * math.sin(t_sec * 3.0 + si * 2.5)
        sp_a = int(140 * sp_bright)
        if 2 <= sp_x < size - 2 and 2 <= sp_y < size - 2:
            pygame.draw.circle(orb_surf, (255, 255, 255, sp_a), (sp_x, sp_y), 1)
            if sp_a > 90:
                orb_surf.set_at((sp_x - 1, sp_y), (255, 255, 255, sp_a // 3))
                orb_surf.set_at((sp_x + 1, sp_y), (255, 255, 255, sp_a // 3))
                orb_surf.set_at((sp_x, sp_y - 1), (255, 255, 255, sp_a // 3))
                orb_surf.set_at((sp_x, sp_y + 1), (255, 255, 255, sp_a // 3))

    # Mask to circle, clipped at liquid level (copy of cached circle mask)
    _mask = _build_circle_mask(orb_r).copy()
    if ratio < 1.0:
        _clip_h = max(0, fill_y)
        if _clip_h > 0:
            pygame.draw.rect(_mask, (0, 0, 0, 0), pygame.Rect(0, 0, size, _clip_h))
    orb_surf.blit(_mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    screen.blit(orb_surf, (cx - half, cy - half))

    # Meniscus highlight at the liquid surface
    if 0.02 < ratio < 0.99:
        _surf_mask = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.ellipse(_surf_mask, (*fill_top, 210),
            pygame.Rect(4, fill_y - 3, size - 8, 6))
        pygame.draw.ellipse(_surf_mask, (255, 255, 255, 120),
            pygame.Rect(8, fill_y - 2, size - 16, 3))
        _surf_mask.blit(_build_circle_mask(orb_r), (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        screen.blit(_surf_mask, (cx - half, cy - half))

    # Glass dome highlights (cached static shapes + dynamic rim arc)
    dome_base = _build_dome_static(orb_r)
    screen.blit(dome_base, (cx - half, cy - half))
    rim_a = int(28 + 12 * math.sin(t_sec * 1.8 + seed))
    if rim_a > 0:
        pygame.draw.arc(screen, (*fill_top, rim_a),
            pygame.Rect(cx - half + 4, cy - half + 4, size - 8, size - 8),
            -0.8, 0.8, 2)

    # Ornate static frame
    frame = build_hud_globe_frame(style)
    fw, fh = frame.get_size()
    screen.blit(frame, (cx - fw // 2, cy - fh // 2))

    # Value text (above the globe)
    _globe_font = get_globe_value_font()
    _vs = _globe_font.render(value_text, True, text_col)
    _vs_sh = _globe_font.render(value_text, True, (0, 0, 0))
    _vw, _vh = _vs.get_size()
    _vx = cx - _vw // 2
    _vy = cy - orb_r - _vh - 4
    screen.blit(_vs_sh, (_vx + 1, _vy + 1))
    screen.blit(_vs, (_vx, _vy))
