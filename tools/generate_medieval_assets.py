import argparse
import json
import math
import os
import random
from typing import Dict, List, Optional, Sequence, Tuple

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame


Color = Tuple[int, int, int]


def shade(color: Color, delta: int) -> Color:
    return (
        max(0, min(255, color[0] + delta)),
        max(0, min(255, color[1] + delta)),
        max(0, min(255, color[2] + delta)),
    )


def outline(surface: pygame.Surface, color: Color = (18, 18, 22)) -> None:
    w, h = surface.get_size()
    pygame.draw.rect(surface, color, (0, 0, w, h), 1)


def dither(surface: pygame.Surface, color_a: Color, color_b: Color, step: int = 2, offset: int = 0) -> None:
    w, h = surface.get_size()
    surface.fill(color_a)
    for y in range(h):
        for x in range(w):
            if ((x + y + offset) // step) % 2 == 0:
                surface.set_at((x, y), color_b)


def export_png(surface: pygame.Surface, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    pygame.image.save(surface, path)


def _crop_alpha(surface: pygame.Surface, pad: int = 2) -> pygame.Surface:
    bounds = surface.get_bounding_rect()
    if bounds.width <= 0 or bounds.height <= 0:
        return surface.copy()
    bounds = bounds.inflate(pad * 2, pad * 2)
    bounds.clamp_ip(surface.get_rect())
    cropped = pygame.Surface((bounds.width, bounds.height), pygame.SRCALPHA)
    cropped.blit(surface, (0, 0), bounds)
    return cropped


def pack_atlas(entries: Sequence[Dict[str, object]], out_dir: str) -> Dict[str, object]:
    atlas_dir = os.path.join(out_dir, "atlas")
    os.makedirs(atlas_dir, exist_ok=True)
    margin = 2
    max_w = 1024
    placements: Dict[str, Dict[str, int]] = {}
    x = margin
    y = margin
    row_h = 0
    atlas_h = margin
    prepared: List[Tuple[str, pygame.Surface]] = []
    for entry in entries:
        source = entry.get("_surface")
        rel_path = str(entry.get("path", ""))
        if not isinstance(source, pygame.Surface) or not rel_path:
            continue
        prepared.append((rel_path.replace("\\", "/"), source))
        if x + source.get_width() + margin > max_w:
            x = margin
            y += row_h + margin
            row_h = 0
        placements[rel_path.replace("\\", "/")] = {
            "x": x,
            "y": y,
            "w": source.get_width(),
            "h": source.get_height(),
        }
        x += source.get_width() + margin
        row_h = max(row_h, source.get_height())
        atlas_h = max(atlas_h, y + source.get_height() + margin)
    atlas = pygame.Surface((max_w, max(64, atlas_h)), pygame.SRCALPHA)
    atlas.fill((0, 0, 0, 0))
    for rel_path, surface in prepared:
        rect = placements[rel_path]
        atlas.blit(surface, (rect["x"], rect["y"]))
    atlas_path = os.path.join(atlas_dir, "atlas.png")
    export_png(atlas, atlas_path)
    atlas_json = {
        "image": "atlas/atlas.png",
        "sprites": placements,
    }
    with open(os.path.join(atlas_dir, "atlas.json"), "w", encoding="utf-8") as handle:
        json.dump(atlas_json, handle, indent=2)
    return atlas_json


def _add_noise(surface: pygame.Surface, rng: random.Random, colors: Sequence[Color], count: int) -> None:
    w, h = surface.get_size()
    for _ in range(count):
        color = colors[rng.randrange(0, len(colors))]
        x = rng.randrange(0, w)
        y = rng.randrange(0, h)
        surface.set_at((x, y), color)


def _tile_surface(size: int, base: Color, highlight: int, shadow: int, rng: random.Random) -> pygame.Surface:
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    dither(surf, base, shade(base, -4), step=2, offset=rng.randrange(0, 2))
    _add_noise(surf, rng, [shade(base, highlight), shade(base, shadow)], size * 2)
    return surf


def _draw_top_left_light(surface: pygame.Surface, alpha: int = 24) -> None:
    glow = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    pygame.draw.polygon(
        glow,
        (255, 255, 255, alpha),
        [(0, 0), (surface.get_width(), 0), (0, surface.get_height())],
    )
    surface.blit(glow, (0, 0))


def _make_terrain_tile(size: int, kind: str, variant: int, rng: random.Random) -> pygame.Surface:
    base_map: Dict[str, Color] = {
        "grass": (74, 118, 64),
        "dirt": (108, 82, 56),
        "mud": (82, 66, 56),
        "cobble": (104, 104, 110),
        "wood_floor": (122, 86, 54),
    }
    base = base_map[kind]
    surf = _tile_surface(size, shade(base, variant * 4 - 2), 14, -16, rng)
    if kind == "grass":
        for _ in range(18):
            x = rng.randrange(0, size)
            y = rng.randrange(4, size)
            pygame.draw.line(surf, shade(base, 22), (x, y), (x + rng.randrange(-1, 2), max(0, y - rng.randrange(2, 5))), 1)
    elif kind == "cobble":
        for gy in range(0, size, 8):
            offset = 0 if (gy // 8) % 2 == 0 else 4
            for gx in range(-offset, size, 8):
                stone = pygame.Rect(gx + 1, gy + 1, 6, 6)
                pygame.draw.rect(surf, shade(base, rng.randrange(-8, 10)), stone)
                pygame.draw.rect(surf, shade(base, -24), stone, 1)
    elif kind == "wood_floor":
        for gx in range(0, size, 8):
            plank = pygame.Rect(gx, 0, 8, size)
            pygame.draw.rect(surf, shade(base, (gx // 8) % 2 * 8 - 4), plank)
            pygame.draw.line(surf, shade(base, -20), (gx, 0), (gx, size), 1)
    else:
        for _ in range(12):
            px = rng.randrange(0, size)
            py = rng.randrange(0, size)
            pygame.draw.circle(surf, shade(base, rng.randrange(-14, 10)), (px, py), rng.randrange(1, 3))
    _draw_top_left_light(surf, alpha=18)
    outline(surf)
    return surf


def _road_tile(size: int, mask_name: str, base: pygame.Surface) -> pygame.Surface:
    surf = base.copy()
    path_color = (126, 100, 70)
    edge_color = (80, 62, 44)
    cx = size // 2
    cy = size // 2
    w = 12
    rects: List[pygame.Rect] = [pygame.Rect(cx - w // 2, cy - w // 2, w, w)]
    if "n" in mask_name:
        rects.append(pygame.Rect(cx - w // 2, 0, w, cy))
    if "s" in mask_name:
        rects.append(pygame.Rect(cx - w // 2, cy, w, size - cy))
    if "w" in mask_name:
        rects.append(pygame.Rect(0, cy - w // 2, cx, w))
    if "e" in mask_name:
        rects.append(pygame.Rect(cx, cy - w // 2, size - cx, w))
    for rect in rects:
        pygame.draw.rect(surf, path_color, rect)
        pygame.draw.rect(surf, edge_color, rect, 1)
    outline(surf)
    return surf


def _water_frame(size: int, frame: int) -> pygame.Surface:
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    surf.fill((34, 74, 126))
    for y in range(size):
        wave = int(math.sin((y + frame * 2) * 0.45) * 10)
        for x in range(size):
            delta = int(math.sin((x + wave) * 0.28 + frame * 0.8) * 8)
            surf.set_at((x, y), shade((38, 84, 146), delta))
    _draw_top_left_light(surf, alpha=14)
    outline(surf)
    return surf


def _shore_tile(size: int, kind: str) -> pygame.Surface:
    surf = _water_frame(size, 0)
    sand = (156, 140, 98)
    dark = (108, 96, 72)
    def draw_band(rect: pygame.Rect) -> None:
        pygame.draw.rect(surf, sand, rect)
        pygame.draw.line(surf, dark, rect.bottomleft, rect.bottomright, 1)
    if kind == "north":
        draw_band(pygame.Rect(0, 0, size, 8))
    elif kind == "south":
        rect = pygame.Rect(0, size - 8, size, 8)
        pygame.draw.rect(surf, sand, rect)
        pygame.draw.line(surf, dark, rect.topleft, rect.topright, 1)
    elif kind == "west":
        rect = pygame.Rect(0, 0, 8, size)
        pygame.draw.rect(surf, sand, rect)
        pygame.draw.line(surf, dark, rect.topright, rect.bottomright, 1)
    elif kind == "east":
        rect = pygame.Rect(size - 8, 0, 8, size)
        pygame.draw.rect(surf, sand, rect)
        pygame.draw.line(surf, dark, rect.topleft, rect.bottomleft, 1)
    elif kind == "nw":
        pygame.draw.circle(surf, sand, (0, 0), 14)
    elif kind == "ne":
        pygame.draw.circle(surf, sand, (size - 1, 0), 14)
    elif kind == "sw":
        pygame.draw.circle(surf, sand, (0, size - 1), 14)
    else:
        pygame.draw.circle(surf, sand, (size - 1, size - 1), 14)
    outline(surf)
    return surf


def _prop_barrel() -> pygame.Surface:
    surf = pygame.Surface((48, 64), pygame.SRCALPHA)
    pygame.draw.ellipse(surf, (18, 18, 18, 70), (6, 52, 36, 10))
    for i in range(6):
        rect = pygame.Rect(8 + i * 5, 10, 6, 42)
        color = shade((108, 74, 48), -abs(3 - i) * 7)
        pygame.draw.rect(surf, color, rect)
    for y in (20, 40):
        hoop = pygame.Rect(6, y, 36, 6)
        pygame.draw.rect(surf, (86, 90, 96), hoop, border_radius=2)
        pygame.draw.line(surf, (130, 134, 140), (hoop.left + 2, hoop.top + 1), (hoop.right - 2, hoop.top + 1), 1)
    pygame.draw.ellipse(surf, (84, 54, 34), (8, 6, 32, 10))
    outline(_crop_alpha(surf, 0))
    return _crop_alpha(surf, 0)


def _prop_crate() -> pygame.Surface:
    surf = pygame.Surface((44, 40), pygame.SRCALPHA)
    pygame.draw.ellipse(surf, (18, 18, 18, 70), (4, 30, 34, 8))
    box = pygame.Rect(6, 8, 32, 24)
    pygame.draw.rect(surf, (116, 82, 52), box)
    pygame.draw.rect(surf, (58, 40, 26), box, 2)
    for x in (14, 24):
        pygame.draw.line(surf, (72, 50, 32), (x, 8), (x, 32), 1)
    pygame.draw.line(surf, (72, 50, 32), (6, 18), (38, 18), 1)
    return _crop_alpha(surf, 0)


def _prop_sack() -> pygame.Surface:
    surf = pygame.Surface((40, 42), pygame.SRCALPHA)
    pygame.draw.ellipse(surf, (18, 18, 18, 70), (6, 30, 28, 8))
    body = [(10, 34), (28, 34), (32, 18), (24, 8), (14, 8), (8, 18)]
    pygame.draw.polygon(surf, (168, 146, 104), body)
    pygame.draw.polygon(surf, (96, 82, 58), body, 1)
    pygame.draw.line(surf, (118, 96, 66), (14, 12), (24, 12), 2)
    return _crop_alpha(surf, 0)


def _prop_chest(opened: bool = False) -> pygame.Surface:
    surf = pygame.Surface((52, 42), pygame.SRCALPHA)
    pygame.draw.ellipse(surf, (18, 18, 18, 70), (6, 32, 40, 8))
    base = pygame.Rect(8, 18, 36, 16)
    pygame.draw.rect(surf, (96, 64, 34), base, border_radius=2)
    pygame.draw.rect(surf, (48, 30, 16), base, 2, border_radius=2)
    if opened:
        lid = [(8, 18), (44, 18), (40, 4), (12, 4)]
    else:
        lid = [(8, 18), (44, 18), (40, 8), (12, 8)]
    pygame.draw.polygon(surf, (118, 82, 40), lid)
    pygame.draw.polygon(surf, (52, 34, 18), lid, 2)
    pygame.draw.rect(surf, (194, 154, 62), (24, 20, 4, 7))
    return _crop_alpha(surf, 0)


def _prop_table() -> pygame.Surface:
    surf = pygame.Surface((74, 52), pygame.SRCALPHA)
    pygame.draw.ellipse(surf, (18, 18, 18, 70), (8, 40, 58, 8))
    top = pygame.Rect(8, 14, 58, 10)
    pygame.draw.rect(surf, (112, 78, 48), top)
    pygame.draw.rect(surf, (56, 38, 24), top, 2)
    for x in (14, 56):
        pygame.draw.rect(surf, (88, 60, 38), (x, 22, 4, 20))
    return _crop_alpha(surf, 0)


def _prop_chair() -> pygame.Surface:
    surf = pygame.Surface((34, 46), pygame.SRCALPHA)
    pygame.draw.ellipse(surf, (18, 18, 18, 70), (4, 36, 24, 6))
    pygame.draw.rect(surf, (106, 74, 46), (8, 18, 18, 6))
    pygame.draw.rect(surf, (106, 74, 46), (10, 4, 4, 14))
    pygame.draw.rect(surf, (106, 74, 46), (8, 24, 3, 14))
    pygame.draw.rect(surf, (106, 74, 46), (23, 24, 3, 14))
    return _crop_alpha(surf, 0)


def _prop_bed() -> pygame.Surface:
    surf = pygame.Surface((92, 48), pygame.SRCALPHA)
    pygame.draw.ellipse(surf, (18, 18, 18, 70), (8, 36, 76, 8))
    frame = pygame.Rect(8, 16, 76, 16)
    pygame.draw.rect(surf, (98, 68, 44), frame)
    pygame.draw.rect(surf, (48, 32, 20), frame, 2)
    mattress = pygame.Rect(14, 18, 64, 12)
    pygame.draw.rect(surf, (142, 64, 62), mattress)
    pillow = pygame.Rect(16, 18, 14, 8)
    pygame.draw.rect(surf, (226, 220, 204), pillow)
    return _crop_alpha(surf, 0)


def _prop_bookshelf() -> pygame.Surface:
    surf = pygame.Surface((60, 84), pygame.SRCALPHA)
    pygame.draw.ellipse(surf, (18, 18, 18, 70), (10, 72, 40, 8))
    frame = pygame.Rect(12, 8, 36, 66)
    pygame.draw.rect(surf, (92, 62, 38), frame)
    pygame.draw.rect(surf, (42, 28, 18), frame, 2)
    for y in (24, 40, 56):
        pygame.draw.line(surf, (52, 34, 22), (14, y), (46, y), 2)
    colors = [(144, 42, 40), (54, 98, 122), (108, 88, 36)]
    for row, y in enumerate((12, 28, 44, 60)):
        for col in range(4):
            pygame.draw.rect(surf, colors[(row + col) % len(colors)], (16 + col * 7, y, 5, 10))
    return _crop_alpha(surf, 0)


def _prop_rug() -> pygame.Surface:
    surf = pygame.Surface((80, 56), pygame.SRCALPHA)
    rug = pygame.Rect(6, 8, 68, 40)
    pygame.draw.rect(surf, (132, 32, 34), rug, border_radius=4)
    pygame.draw.rect(surf, (214, 184, 104), rug.inflate(-8, -8), 2, border_radius=4)
    for x in range(10, 74, 8):
        pygame.draw.line(surf, (206, 164, 88), (x, 48), (x, 52), 1)
    return _crop_alpha(surf, 0)


def _tree_surface() -> pygame.Surface:
    surf = pygame.Surface((64, 96), pygame.SRCALPHA)
    pygame.draw.ellipse(surf, (18, 18, 18, 70), (14, 84, 36, 8))
    pygame.draw.rect(surf, (84, 58, 36), (28, 48, 8, 38))
    for center, radius, color in [
        ((24, 40), 16, (48, 112, 56)),
        ((40, 36), 18, (58, 128, 64)),
        ((32, 24), 20, (66, 140, 72)),
    ]:
        pygame.draw.circle(surf, color, center, radius)
        pygame.draw.circle(surf, shade(color, -28), center, radius, 1)
    return _crop_alpha(surf, 0)


def _bush_surface() -> pygame.Surface:
    surf = pygame.Surface((56, 40), pygame.SRCALPHA)
    pygame.draw.ellipse(surf, (18, 18, 18, 70), (6, 30, 44, 8))
    for center, radius, color in [
        ((18, 22), 10, (56, 116, 62)),
        ((30, 18), 12, (64, 128, 70)),
        ((40, 24), 9, (48, 104, 58)),
    ]:
        pygame.draw.circle(surf, color, center, radius)
        pygame.draw.circle(surf, shade(color, -24), center, radius, 1)
    return _crop_alpha(surf, 0)


def _tree_shadow_surface() -> pygame.Surface:
    surf = pygame.Surface((58, 20), pygame.SRCALPHA)
    pygame.draw.ellipse(surf, (0, 0, 0, 76), (0, 4, 58, 12))
    return surf


def _house_prefab(style: int) -> pygame.Surface:
    surf = pygame.Surface((128, 128), pygame.SRCALPHA)
    wall_colors = [(174, 162, 142), (142, 118, 92), (124, 128, 140)]
    roof_colors = [(122, 64, 52), (78, 70, 64), (94, 50, 34)]
    wall = wall_colors[style % len(wall_colors)]
    roof = roof_colors[style % len(roof_colors)]
    pygame.draw.ellipse(surf, (18, 18, 18, 70), (18, 108, 92, 12))
    body = pygame.Rect(24, 48, 80, 60)
    pygame.draw.rect(surf, wall, body)
    pygame.draw.rect(surf, shade(wall, -30), body, 2)
    roof_pts = [(18, 50), (110, 50), (64, 14)]
    pygame.draw.polygon(surf, roof, roof_pts)
    pygame.draw.polygon(surf, shade(roof, -30), roof_pts, 2)
    pygame.draw.rect(surf, (76, 42, 22), (56, 72, 16, 36))
    for x in (34, 78):
        pygame.draw.rect(surf, (198, 182, 104), (x, 64, 14, 16))
        pygame.draw.rect(surf, (58, 42, 28), (x, 64, 14, 16), 1)
    return _crop_alpha(surf, 0)


def _wall_piece(kind: str) -> pygame.Surface:
    surf = pygame.Surface((32, 32), pygame.SRCALPHA)
    surf.fill((164, 152, 132))
    for y in range(0, 32, 8):
        offset = 0 if (y // 8) % 2 == 0 else 4
        for x in range(-offset, 32, 8):
            pygame.draw.rect(surf, shade((164, 152, 132), (x + y) % 7 - 3), (x + 1, y + 1, 6, 6))
    if kind == "door":
        pygame.draw.rect(surf, (72, 42, 22), (10, 10, 12, 22))
    elif kind == "window":
        pygame.draw.rect(surf, (198, 188, 112), (9, 10, 14, 12))
        pygame.draw.rect(surf, (48, 34, 22), (9, 10, 14, 12), 1)
    elif kind == "roof":
        surf.fill((110, 60, 48))
        for y in range(0, 32, 6):
            pygame.draw.line(surf, (82, 42, 32), (0, y), (31, y), 2)
    elif kind == "corner":
        pygame.draw.line(surf, (62, 52, 38), (16, 0), (16, 31), 2)
    outline(surf)
    return surf


def _ring_frame(size: int, radius: int, tick: int, total: int, color: Color) -> pygame.Surface:
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    alpha = 90 + int(120 * (tick / max(1, total - 1)))
    pygame.draw.circle(surf, (*color, alpha), (size // 2, size // 2), radius + tick * 2, 2)
    return surf


def _bolt_cast_frame(frame: int) -> pygame.Surface:
    surf = pygame.Surface((48, 48), pygame.SRCALPHA)
    for radius in (6 + frame * 3, 12 + frame * 4):
        pygame.draw.circle(surf, (196, 230, 255, 70), (24, 24), radius)
    pygame.draw.line(surf, (226, 244, 255), (24, 8), (24, 40), 3)
    pygame.draw.line(surf, (226, 244, 255), (8, 24), (40, 24), 3)
    return _crop_alpha(surf, 0)


def _bolt_projectile_frame(frame: int) -> pygame.Surface:
    surf = pygame.Surface((40, 24), pygame.SRCALPHA)
    body = [(2 + frame * 2, 12), (18 + frame * 2, 4), (34 + frame * 2, 12), (18 + frame * 2, 20)]
    pygame.draw.polygon(surf, (144, 216, 255), body)
    pygame.draw.polygon(surf, (228, 248, 255), body, 1)
    return _crop_alpha(surf, 0)


def _bolt_impact_frame(frame: int) -> pygame.Surface:
    surf = pygame.Surface((64, 64), pygame.SRCALPHA)
    for ang in range(0, 360, 45):
        rad = math.radians(ang + frame * 6)
        inner = (32 + math.cos(rad) * (6 + frame), 32 + math.sin(rad) * (6 + frame))
        outer = (32 + math.cos(rad) * (14 + frame * 2), 32 + math.sin(rad) * (14 + frame * 2))
        pygame.draw.line(surf, (180, 228, 255), inner, outer, 2)
    pygame.draw.circle(surf, (236, 250, 255, 110), (32, 32), 6 + frame)
    return _crop_alpha(surf, 0)


def _summon_rune_frame(frame: int) -> pygame.Surface:
    surf = pygame.Surface((72, 72), pygame.SRCALPHA)
    radius = 18 + frame
    pygame.draw.circle(surf, (150, 86, 228, 110), (36, 36), radius, 2)
    for idx in range(6):
        ang = math.radians(idx * 60 + frame * 8)
        x = 36 + math.cos(ang) * (radius + 6)
        y = 36 + math.sin(ang) * (radius + 6)
        pygame.draw.circle(surf, (206, 168, 255, 150), (int(x), int(y)), 2)
    return _crop_alpha(surf, 0)


def _fire_frame(frame: int) -> pygame.Surface:
    surf = pygame.Surface((48, 64), pygame.SRCALPHA)
    flick = math.sin(frame * 0.8) * 3.0
    pts = [(24, 8 + flick), (12, 28), (18, 56), (24, 42), (30, 56), (36, 28)]
    pygame.draw.polygon(surf, (255, 150, 46), [(int(x), int(y)) for x, y in pts])
    pygame.draw.polygon(surf, (255, 214, 92), [(24, 18), (18, 34), (24, 46), (30, 34)])
    pygame.draw.ellipse(surf, (0, 0, 0, 80), (10, 54, 28, 8))
    return _crop_alpha(surf, 0)


def _smoke_frame(frame: int) -> pygame.Surface:
    surf = pygame.Surface((56, 56), pygame.SRCALPHA)
    alpha = max(24, 120 - frame * 14)
    for center, radius in [((20, 30), 10 + frame), ((30, 22), 9 + frame), ((38, 32), 8 + frame)]:
        pygame.draw.circle(surf, (126, 126, 136, alpha), center, radius)
    return _crop_alpha(surf, 0)


# ─── ICE BIOME DRAWING HELPERS ────────────────────────────────────────────────

def _clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))


def _make_ice_terrain(size: int, kind: str, variant: int, rng: random.Random) -> pygame.Surface:
    base_map: Dict[str, Color] = {
        "snow":          (218, 228, 240),
        "ice":           (158, 198, 228),
        "permafrost":    (76,  86, 104),
        "tundra_rock":   (116, 120, 128),
        "frozen_ground": (96,  108, 124),
    }
    base = base_map[kind]
    surf = _tile_surface(size, shade(base, variant * 5 - 2), 10, -16, rng)
    if kind == "snow":
        for _ in range(22):
            x = rng.randrange(0, size)
            y = rng.randrange(0, size)
            pygame.draw.circle(surf, (255, 255, 255), (x, y), 1)
        for _ in range(3):
            x0 = rng.randrange(0, size - 8)
            y0 = rng.randrange(0, size)
            pygame.draw.line(surf, shade(base, 20), (x0, y0), (x0 + rng.randrange(4, 10), y0 + rng.randrange(-1, 2)), 1)
    elif kind == "ice":
        for _ in range(5):
            x0 = rng.randrange(2, size - 2)
            y0 = rng.randrange(2, size - 2)
            x1 = _clamp(x0 + rng.randrange(-8, 8), 0, size - 1)
            y1 = _clamp(y0 + rng.randrange(-8, 8), 0, size - 1)
            pygame.draw.line(surf, (196, 224, 246), (x0, y0), (x1, y1), 1)
        glow = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.polygon(glow, (240, 250, 255, 36), [(0, 0), (size // 2, 0), (0, size // 3)])
        surf.blit(glow, (0, 0))
    elif kind == "permafrost":
        for _ in range(7):
            x0 = rng.randrange(0, size)
            y0 = rng.randrange(0, size)
            x1 = _clamp(x0 + rng.randrange(-10, 10), 0, size - 1)
            y1 = _clamp(y0 + rng.randrange(-10, 10), 0, size - 1)
            pygame.draw.line(surf, (128, 158, 184), (x0, y0), (x1, y1), 1)
        for _ in range(6):
            px = rng.randrange(0, size)
            py = rng.randrange(0, size)
            pygame.draw.circle(surf, (200, 218, 232), (px, py), 1)
    elif kind == "tundra_rock":
        for gy in range(0, size, 10):
            off = 0 if (gy // 10) % 2 == 0 else 5
            for gx in range(-off, size, 10):
                pygame.draw.rect(surf, shade(base, rng.randrange(-14, 14)), (gx + 1, gy + 1, 8, 8))
                pygame.draw.rect(surf, shade(base, -26), (gx + 1, gy + 1, 8, 8), 1)
        for _ in range(4):
            sx = rng.randrange(0, size - 5)
            sy = rng.randrange(0, size - 3)
            pygame.draw.ellipse(surf, (228, 234, 242), (sx, sy, rng.randrange(4, 10), rng.randrange(2, 5)))
    elif kind == "frozen_ground":
        for _ in range(18):
            px = rng.randrange(0, size)
            py = rng.randrange(0, size)
            pygame.draw.circle(surf, shade(base, rng.randrange(-18, 14)), (px, py), rng.randrange(1, 3))
        for _ in range(9):
            fx = rng.randrange(0, size)
            fy = rng.randrange(0, size)
            pygame.draw.circle(surf, (208, 222, 238), (fx, fy), 1)
    _draw_top_left_light(surf, alpha=20)
    outline(surf)
    return surf


def _frozen_road_tile(size: int, mask_name: str, base: pygame.Surface) -> pygame.Surface:
    surf = base.copy()
    path_color = (136, 158, 186)
    edge_color  = (98,  118, 148)
    hi_color    = (172, 192, 214)
    cx = size // 2
    cy = size // 2
    w  = 12
    rects: List[pygame.Rect] = [pygame.Rect(cx - w // 2, cy - w // 2, w, w)]
    if "n" in mask_name: rects.append(pygame.Rect(cx - w // 2, 0, w, cy))
    if "s" in mask_name: rects.append(pygame.Rect(cx - w // 2, cy, w, size - cy))
    if "w" in mask_name: rects.append(pygame.Rect(0, cy - w // 2, cx, w))
    if "e" in mask_name: rects.append(pygame.Rect(cx, cy - w // 2, size - cx, w))
    for rect in rects:
        pygame.draw.rect(surf, path_color, rect)
        for gx in range(rect.left + 2, rect.right - 2, 5):
            pygame.draw.line(surf, hi_color, (gx, rect.top + 1), (gx + 2, rect.top + 1), 1)
        pygame.draw.rect(surf, edge_color, rect, 1)
    outline(surf)
    return surf


def _ice_pine_snowy() -> pygame.Surface:
    surf = pygame.Surface((80, 118), pygame.SRCALPHA)
    pygame.draw.ellipse(surf, (0, 0, 0, 55), (20, 108, 40, 9))
    pygame.draw.rect(surf, (70, 50, 36), (36, 72, 8, 36))
    pygame.draw.rect(surf, (50, 34, 22), (37, 72, 3, 36))
    for pts, snow, dk in [
        ([(12, 90), (68, 90), (40, 62)], [(14, 88), (66, 88), (62, 84), (40, 72), (18, 84)], (40, 80, 54)),
        ([(18, 72), (62, 72), (40, 48)], [(20, 70), (60, 70), (56, 66), (40, 56), (24, 66)], (46, 90, 60)),
        ([(24, 54), (56, 54), (40, 34)], [(26, 52), (54, 52), (50, 48), (40, 38), (30, 48)], (52, 100, 66)),
    ]:
        pygame.draw.polygon(surf, dk, pts)
        pygame.draw.polygon(surf, shade(dk, -22), pts, 1)
        pygame.draw.polygon(surf, (220, 230, 242), snow)
    pygame.draw.circle(surf, (228, 236, 246), (40, 32), 6)
    return _crop_alpha(surf, 0)


def _ice_pine_bent() -> pygame.Surface:
    surf = pygame.Surface((66, 96), pygame.SRCALPHA)
    pygame.draw.ellipse(surf, (0, 0, 0, 50), (14, 86, 38, 8))
    pygame.draw.line(surf, (68, 48, 32), (30, 88), (36, 44), 5)
    pygame.draw.line(surf, (48, 30, 18), (31, 88), (37, 44), 2)
    for pts, snow, dk in [
        ([(10, 74), (56, 74), (38, 52)], [(12, 72), (54, 72), (50, 68), (38, 58), (16, 68)], (38, 76, 50)),
        ([(18, 56), (54, 56), (40, 38)], [(20, 54), (52, 54), (48, 50), (40, 42), (24, 50)], (44, 86, 58)),
    ]:
        pygame.draw.polygon(surf, dk, pts)
        pygame.draw.polygon(surf, shade(dk, -20), pts, 1)
        pygame.draw.polygon(surf, (218, 228, 240), snow)
    pygame.draw.circle(surf, (224, 234, 244), (40, 36), 5)
    return _crop_alpha(surf, 0)


def _ice_dead_tree() -> pygame.Surface:
    surf = pygame.Surface((64, 108), pygame.SRCALPHA)
    pygame.draw.ellipse(surf, (0, 0, 0, 50), (16, 98, 32, 9))
    tc = (60, 48, 40)
    dk = (42, 32, 26)
    pygame.draw.line(surf, tc, (32, 98), (32, 34), 5)
    pygame.draw.line(surf, dk, (31, 98), (31, 34), 2)
    pygame.draw.line(surf, tc, (32, 58), (13, 34), 3)
    pygame.draw.line(surf, tc, (32, 58), (51, 30), 3)
    pygame.draw.line(surf, tc, (32, 72), (11, 52), 2)
    pygame.draw.line(surf, tc, (32, 72), (53, 48), 2)
    pygame.draw.line(surf, tc, (13, 34), (7, 26), 2)
    pygame.draw.line(surf, tc, (13, 34), (19, 24), 2)
    pygame.draw.line(surf, tc, (51, 30), (45, 20), 2)
    pygame.draw.line(surf, tc, (51, 30), (57, 22), 2)
    sc = (216, 226, 238)
    for poly in [[(7,26),(14,34),(21,32),(13,28)], [(44,20),(52,30),(57,28),(48,22)], [(9,52),(14,50),(20,34),(12,36)]]:
        pygame.draw.polygon(surf, sc, poly)
    return _crop_alpha(surf, 0)


def _ice_dead_tree_small() -> pygame.Surface:
    surf = pygame.Surface((46, 76), pygame.SRCALPHA)
    pygame.draw.ellipse(surf, (0, 0, 0, 46), (12, 68, 22, 7))
    tc = (58, 46, 38)
    pygame.draw.line(surf, tc, (23, 68), (23, 28), 4)
    pygame.draw.line(surf, tc, (23, 46), (10, 28), 2)
    pygame.draw.line(surf, tc, (23, 46), (36, 24), 2)
    pygame.draw.line(surf, tc, (23, 58), (10, 44), 2)
    pygame.draw.line(surf, tc, (23, 58), (36, 42), 2)
    pygame.draw.line(surf, tc, (10, 28), (6, 20), 2)
    pygame.draw.line(surf, tc, (36, 24), (40, 16), 2)
    sc = (214, 224, 236)
    for poly in [[(5,20),(10,28),(16,26),(9,22)], [(35,16),(38,24),(42,22),(37,18)]]:
        pygame.draw.polygon(surf, sc, poly)
    return _crop_alpha(surf, 0)


def _ice_crystal_large() -> pygame.Surface:
    surf = pygame.Surface((36, 72), pygame.SRCALPHA)
    pygame.draw.ellipse(surf, (0, 0, 0, 46), (8, 64, 20, 7))
    base_c = (158, 210, 238)
    hi_c   = (210, 238, 252)
    dk_c   = (108, 158, 196)
    pts = [(18, 4), (28, 22), (30, 50), (22, 62), (14, 62), (6, 50), (8, 22)]
    pygame.draw.polygon(surf, base_c, pts)
    pygame.draw.polygon(surf, dk_c, pts, 1)
    pygame.draw.polygon(surf, hi_c, [(18, 4), (28, 22), (22, 22), (18, 10)])
    glow = pygame.Surface((36, 72), pygame.SRCALPHA)
    pygame.draw.polygon(glow, (220, 244, 255, 50), pts)
    surf.blit(glow, (0, 0))
    return _crop_alpha(surf, 0)


def _ice_crystal_cluster() -> pygame.Surface:
    surf = pygame.Surface((64, 54), pygame.SRCALPHA)
    pygame.draw.ellipse(surf, (0, 0, 0, 46), (8, 46, 48, 7))
    data = [
        (12, 44, 8, 4), (22, 44, 10, 6), (32, 44, 9, 8),
        (42, 44, 8, 5), (52, 44, 7, 3),
    ]
    base_c = (154, 206, 234)
    hi_c   = (208, 238, 252)
    for bx, by, bw, dep in data:
        top_x = bx + bw // 2
        top_y = by - dep * 4
        pts = [(top_x - 1, top_y), (top_x + bw // 2, by - dep), (top_x + bw // 2, by), (top_x - bw // 2, by), (top_x - bw // 2, by - dep)]
        pygame.draw.polygon(surf, base_c, pts)
        pygame.draw.polygon(surf, shade(base_c, -22), pts, 1)
        pygame.draw.line(surf, hi_c, (top_x - 1, top_y + 2), (top_x + 1, top_y + dep * 2), 1)
    return _crop_alpha(surf, 0)


def _ice_snowdrift_large() -> pygame.Surface:
    surf = pygame.Surface((96, 42), pygame.SRCALPHA)
    pygame.draw.ellipse(surf, (0, 0, 0, 46), (8, 34, 80, 8))
    pygame.draw.ellipse(surf, (212, 222, 234), (6, 18, 84, 22))
    pygame.draw.ellipse(surf, (228, 236, 246), (14, 12, 68, 18))
    pygame.draw.ellipse(surf, (240, 246, 252), (22, 8, 52, 14))
    pygame.draw.line(surf, (198, 210, 226), (20, 24), (76, 24), 1)
    return _crop_alpha(surf, 0)


def _ice_snowdrift_small() -> pygame.Surface:
    surf = pygame.Surface((64, 28), pygame.SRCALPHA)
    pygame.draw.ellipse(surf, (0, 0, 0, 42), (6, 22, 52, 6))
    pygame.draw.ellipse(surf, (212, 222, 234), (4, 12, 56, 14))
    pygame.draw.ellipse(surf, (228, 236, 246), (10, 8, 44, 12))
    pygame.draw.ellipse(surf, (240, 246, 252), (18, 6, 28, 10))
    return _crop_alpha(surf, 0)


def _ice_icicle_group() -> pygame.Surface:
    surf = pygame.Surface((52, 44), pygame.SRCALPHA)
    for ix, ih, iw in [(6, 28, 6), (15, 36, 7), (25, 32, 7), (35, 40, 8), (45, 26, 6)]:
        pts = [(ix, 0), (ix + iw, 0), (ix + iw // 2, ih)]
        pygame.draw.polygon(surf, (188, 220, 242), pts)
        pygame.draw.polygon(surf, (140, 188, 218), pts, 1)
        pygame.draw.line(surf, (220, 240, 252), (ix + 1, 2), (ix + iw // 2, ih // 2), 1)
    return _crop_alpha(surf, 0)


def _ice_frozen_log() -> pygame.Surface:
    surf = pygame.Surface((100, 34), pygame.SRCALPHA)
    pygame.draw.ellipse(surf, (0, 0, 0, 46), (8, 26, 84, 8))
    pygame.draw.rect(surf, (78, 54, 38), (8, 14, 84, 14), border_radius=6)
    pygame.draw.rect(surf, (56, 38, 24), (8, 14, 84, 14), 2, border_radius=6)
    for x in range(16, 88, 14):
        pygame.draw.line(surf, (62, 42, 28), (x, 14), (x, 28), 1)
    snow_pts = [(8, 14), (92, 14), (88, 8), (12, 8)]
    pygame.draw.polygon(surf, (218, 228, 240), snow_pts)
    return _crop_alpha(surf, 0)


def _ice_frost_bush() -> pygame.Surface:
    surf = pygame.Surface((52, 36), pygame.SRCALPHA)
    pygame.draw.ellipse(surf, (0, 0, 0, 42), (6, 28, 40, 7))
    for cx2, cy2, r, c in [(16, 22, 9, (48, 86, 58)), (26, 18, 11, (54, 96, 64)), (38, 22, 8, (44, 80, 54))]:
        pygame.draw.circle(surf, c, (cx2, cy2), r)
        pygame.draw.circle(surf, shade(c, -22), (cx2, cy2), r, 1)
    for cx2, cy2, r in [(14, 20, 5), (26, 15, 6), (38, 20, 5)]:
        pygame.draw.circle(surf, (214, 226, 238), (cx2, cy2), r)
        pygame.draw.circle(surf, (190, 208, 224), (cx2, cy2), r, 1)
    return _crop_alpha(surf, 0)


def _ice_tundra_grass() -> pygame.Surface:
    surf = pygame.Surface((30, 22), pygame.SRCALPHA)
    gc = (134, 122, 96)
    pygame.draw.line(surf, gc, (10, 20), (8, 10), 2)
    pygame.draw.line(surf, gc, (14, 20), (12, 6), 1)
    pygame.draw.line(surf, gc, (18, 20), (22, 8), 2)
    pygame.draw.line(surf, gc, (22, 20), (26, 12), 1)
    pygame.draw.line(surf, gc, (6, 20), (4, 14), 1)
    pygame.draw.line(surf, shade(gc, 14), (14, 20), (10, 4), 1)
    return _crop_alpha(surf, 0)


def _ice_frost_flower() -> pygame.Surface:
    surf = pygame.Surface((24, 24), pygame.SRCALPHA)
    c = (190, 220, 240)
    hc = (224, 240, 252)
    cx2, cy2 = 12, 12
    for ang in range(0, 360, 45):
        rad = math.radians(ang)
        ex = int(cx2 + math.cos(rad) * 9)
        ey = int(cy2 + math.sin(rad) * 9)
        pygame.draw.line(surf, c, (cx2, cy2), (ex, ey), 1)
        pygame.draw.circle(surf, hc, (ex, ey), 2)
    pygame.draw.circle(surf, hc, (cx2, cy2), 3)
    pygame.draw.circle(surf, (240, 248, 255), (cx2, cy2), 2)
    return _crop_alpha(surf, 0)


def _ice_snow_boulder_large() -> pygame.Surface:
    surf = pygame.Surface((60, 46), pygame.SRCALPHA)
    pygame.draw.ellipse(surf, (0, 0, 0, 50), (8, 38, 44, 8))
    pygame.draw.ellipse(surf, (110, 114, 122), (6, 18, 48, 26))
    pygame.draw.ellipse(surf, (130, 136, 144), (8, 20, 44, 22))
    pygame.draw.ellipse(surf, (220, 228, 238), (8, 12, 44, 18))
    pygame.draw.ellipse(surf, (236, 242, 248), (14, 8, 32, 14))
    return _crop_alpha(surf, 0)


def _ice_snow_boulder_small() -> pygame.Surface:
    surf = pygame.Surface((38, 30), pygame.SRCALPHA)
    pygame.draw.ellipse(surf, (0, 0, 0, 46), (6, 24, 26, 6))
    pygame.draw.ellipse(surf, (108, 112, 120), (4, 12, 30, 16))
    pygame.draw.ellipse(surf, (126, 132, 140), (6, 14, 26, 14))
    pygame.draw.ellipse(surf, (216, 224, 236), (6, 8, 26, 12))
    pygame.draw.ellipse(surf, (232, 240, 248), (10, 6, 18, 10))
    return _crop_alpha(surf, 0)


def _ice_hunter_hut() -> pygame.Surface:
    surf = pygame.Surface((128, 120), pygame.SRCALPHA)
    pygame.draw.ellipse(surf, (0, 0, 0, 60), (14, 106, 100, 12))
    wall = (138, 102, 72)
    dk   = (98, 70, 48)
    for y_row in range(52, 100, 10):
        for x_col in range(22, 106, 10):
            pygame.draw.rect(surf, shade(wall, (x_col + y_row) % 5 * 2 - 4), (x_col, y_row, 9, 9))
            pygame.draw.rect(surf, dk, (x_col, y_row, 9, 9), 1)
    pygame.draw.rect(surf, dk, (22, 52, 84, 48), 2)
    roof_pts = [(16, 54), (112, 54), (64, 18)]
    pygame.draw.polygon(surf, (88, 90, 96), roof_pts)
    pygame.draw.polygon(surf, (222, 228, 238), [(18, 52), (110, 52), (106, 46), (64, 18), (22, 46)])
    pygame.draw.polygon(surf, shade((88, 90, 96), -28), roof_pts, 2)
    pygame.draw.rect(surf, (58, 38, 22), (56, 72, 16, 28))
    pygame.draw.rect(surf, dk, (56, 72, 16, 28), 1)
    for wx in (32, 80):
        pygame.draw.rect(surf, (188, 182, 108), (wx, 62, 14, 14))
        pygame.draw.rect(surf, dk, (wx, 62, 14, 14), 1)
        pygame.draw.line(surf, dk, (wx + 7, 62), (wx + 7, 76), 1)
        pygame.draw.line(surf, dk, (wx, 69), (wx + 14, 69), 1)
    pygame.draw.rect(surf, (72, 52, 34), (46, 98, 36, 6))
    return _crop_alpha(surf, 0)


def _ice_frost_shrine() -> pygame.Surface:
    surf = pygame.Surface((52, 96), pygame.SRCALPHA)
    pygame.draw.ellipse(surf, (0, 0, 0, 54), (12, 88, 28, 8))
    sc = (116, 122, 136)
    dk = (78, 84, 96)
    for y_row in range(28, 84, 8):
        w2 = 32 - abs(y_row - 56) // 4
        x0 = 26 - w2 // 2
        pygame.draw.rect(surf, shade(sc, (y_row // 8) % 2 * 6 - 3), (x0, y_row, w2, 8))
        pygame.draw.rect(surf, dk, (x0, y_row, w2, 8), 1)
    pygame.draw.polygon(surf, (138, 144, 160), [(14, 28), (38, 28), (26, 8)])
    pygame.draw.polygon(surf, dk, [(14, 28), (38, 28), (26, 8)], 1)
    pygame.draw.rect(surf, shade(sc, 4), (18, 30, 4, 16), border_radius=1)
    pygame.draw.rect(surf, shade(sc, 4), (30, 30, 4, 16), border_radius=1)
    for cx2, cy2, r, c in [
        (18, 84, 6, (148, 200, 228)), (34, 80, 5, (148, 200, 228)),
        (26, 88, 7, (168, 214, 238)), (14, 86, 4, (128, 188, 218)),
    ]:
        pygame.draw.circle(surf, c, (cx2, cy2), r)
        pygame.draw.circle(surf, shade(c, -30), (cx2, cy2), r, 1)
    glow = pygame.Surface((52, 96), pygame.SRCALPHA)
    pygame.draw.circle(glow, (180, 220, 255, 30), (26, 80), 18)
    surf.blit(glow, (0, 0))
    return _crop_alpha(surf, 0)


def _ice_stone_pillar_frozen() -> pygame.Surface:
    surf = pygame.Surface((28, 84), pygame.SRCALPHA)
    pygame.draw.ellipse(surf, (0, 0, 0, 50), (4, 76, 20, 8))
    sc = (118, 124, 138)
    dk = (80, 86, 98)
    for y_row in range(20, 72, 8):
        w2 = 20 - abs(y_row - 46) // 6
        x0 = 14 - w2 // 2
        pygame.draw.rect(surf, shade(sc, (y_row // 8) % 2 * 5 - 2), (x0, y_row, w2, 8))
        pygame.draw.rect(surf, dk, (x0, y_row, w2, 8), 1)
    pygame.draw.rect(surf, (138, 144, 158), (4, 16, 20, 6))
    pygame.draw.rect(surf, (4, 72, 16, 6))
    ic = (158, 208, 232)
    for ix, iy, ir in [(8, 72, 5), (16, 68, 4), (22, 74, 6), (6, 78, 4)]:
        pygame.draw.circle(surf, ic, (ix, iy), ir)
        pygame.draw.circle(surf, shade(ic, -24), (ix, iy), ir, 1)
    return _crop_alpha(surf, 0)


def _ice_cave_entrance() -> pygame.Surface:
    surf = pygame.Surface((128, 80), pygame.SRCALPHA)
    cliff = (86, 90, 100)
    dk_c  = (52, 56, 64)
    snow_c = (218, 226, 238)
    pts = [(0, 80), (0, 28), (20, 8), (64, 0), (108, 10), (128, 30), (128, 80)]
    pygame.draw.polygon(surf, cliff, pts)
    pygame.draw.polygon(surf, dk_c, pts, 2)
    for y_row in range(8, 80, 9):
        for x_col in range(0, 128, 9):
            if y_row > 30 - abs(x_col - 64) // 4:
                pygame.draw.rect(surf, shade(cliff, (x_col + y_row) % 3 * 4 - 4), (x_col, y_row, 8, 8))
    opening_pts = [(38, 80), (38, 42), (50, 28), (64, 24), (78, 28), (90, 42), (90, 80)]
    pygame.draw.polygon(surf, (14, 16, 22), opening_pts)
    pygame.draw.polygon(surf, (36, 40, 50), opening_pts, 2)
    for ix, ilen in [(42, 14), (50, 20), (60, 16), (70, 22), (80, 14), (88, 10)]:
        pts2 = [(ix, 28), (ix + 4, 28), (ix + 2, 28 + ilen)]
        pygame.draw.polygon(surf, (188, 218, 238), pts2)
        pygame.draw.polygon(surf, (148, 188, 214), pts2, 1)
    pygame.draw.polygon(surf, snow_c, [(2, 28), (126, 30), (122, 22), (64, 6), (6, 24)])
    return _crop_alpha(surf, 0)


def _ice_broken_watchtower() -> pygame.Surface:
    surf = pygame.Surface((88, 160), pygame.SRCALPHA)
    pygame.draw.ellipse(surf, (0, 0, 0, 58), (10, 148, 68, 12))
    sc = (108, 114, 128)
    dk = (72, 76, 88)
    for y_row in range(60, 144, 8):
        for x_col in range(18, 70, 8):
            pygame.draw.rect(surf, shade(sc, (x_col + y_row) % 3 * 5 - 4), (x_col, y_row, 7, 7))
            pygame.draw.rect(surf, dk, (x_col, y_row, 7, 7), 1)
    pygame.draw.rect(surf, (88, 92, 104), (14, 140, 60, 6))
    pygame.draw.rect(surf, dk, (14, 140, 60, 6), 1)
    jagged = [(18, 60), (22, 50), (28, 58), (34, 44), (40, 54), (46, 40), (52, 52), (58, 46), (64, 56), (68, 60)]
    pygame.draw.polygon(surf, sc, jagged + [(68, 70), (18, 70)])
    pygame.draw.lines(surf, dk, False, jagged, 2)
    plat = [(12, 72), (76, 72), (76, 80), (12, 80)]
    pygame.draw.polygon(surf, (94, 68, 44), plat)
    pygame.draw.polygon(surf, (62, 44, 28), plat, 1)
    for ic_x, ic_y, ic_r in [(24, 58), (44, 48), (62, 54)]:
        pygame.draw.circle(surf, (158, 206, 230), (ic_x, ic_y), 5)
    return _crop_alpha(surf, 0)


def _ice_frozen_wagon() -> pygame.Surface:
    surf = pygame.Surface((118, 68), pygame.SRCALPHA)
    pygame.draw.ellipse(surf, (0, 0, 0, 52), (10, 58, 98, 10))
    wc = (116, 82, 52)
    dk = (72, 48, 28)
    body = pygame.Rect(14, 22, 90, 28)
    pygame.draw.rect(surf, wc, body)
    pygame.draw.rect(surf, dk, body, 2)
    for x_col in range(22, 100, 8):
        pygame.draw.line(surf, dk, (x_col, 22), (x_col, 50), 1)
    for wx, wy in [(22, 46), (96, 46)]:
        pygame.draw.circle(surf, (78, 82, 90), (wx, wy), 16, 3)
        pygame.draw.circle(surf, (104, 108, 116), (wx, wy), 8, 2)
    snow_pts = [(14, 22), (104, 22), (100, 14), (18, 14)]
    pygame.draw.polygon(surf, (220, 228, 240), snow_pts)
    for sx in range(16, 104, 10):
        pygame.draw.ellipse(surf, (208, 218, 232), (sx, 10, 8, 6))
    ic = (158, 206, 228)
    for ix, iy, ir in [(30, 22, 6), (70, 24, 5), (100, 20, 7), (50, 22, 4)]:
        pygame.draw.circle(surf, ic, (ix, iy), ir)
    return _crop_alpha(surf, 0)


def _ice_stone_cairn() -> pygame.Surface:
    surf = pygame.Surface((38, 52), pygame.SRCALPHA)
    pygame.draw.ellipse(surf, (0, 0, 0, 50), (6, 44, 26, 8))
    for stone_y, stone_w, stone_h in [(42, 30, 10), (36, 26, 8), (30, 22, 8), (24, 18, 8), (18, 14, 8), (14, 10, 6)]:
        x0 = 19 - stone_w // 2
        c = shade((116, 122, 132), (stone_y % 3) * 6 - 6)
        pygame.draw.ellipse(surf, c, (x0, stone_y, stone_w, stone_h))
        pygame.draw.ellipse(surf, shade(c, -28), (x0, stone_y, stone_w, stone_h), 1)
    pygame.draw.ellipse(surf, (220, 226, 236), (11, 14, 14, 5))
    return _crop_alpha(surf, 0)


def _ice_frozen_barrel() -> pygame.Surface:
    surf = pygame.Surface((48, 64), pygame.SRCALPHA)
    pygame.draw.ellipse(surf, (0, 0, 0, 56), (6, 54, 36, 8))
    for i in range(6):
        rect = pygame.Rect(8 + i * 5, 12, 6, 40)
        pygame.draw.rect(surf, shade((96, 68, 44), -abs(3 - i) * 6), rect)
    for y_row in (22, 40):
        pygame.draw.rect(surf, (82, 86, 94), pygame.Rect(6, y_row, 36, 5), border_radius=2)
    pygame.draw.ellipse(surf, (80, 54, 34), (8, 8, 32, 10))
    ic = (158, 210, 234)
    for ix2, iy2, ir2 in [(14, 18, 8), (30, 22, 7), (10, 38, 6), (36, 36, 7), (22, 48, 5)]:
        pygame.draw.circle(surf, ic, (ix2, iy2), ir2)
        pygame.draw.circle(surf, shade(ic, -20), (ix2, iy2), ir2, 1)
    outline(_crop_alpha(surf, 0))
    return _crop_alpha(surf, 0)


def _ice_supply_cache() -> pygame.Surface:
    surf = pygame.Surface((52, 38), pygame.SRCALPHA)
    pygame.draw.ellipse(surf, (0, 0, 0, 50), (4, 30, 44, 8))
    box = pygame.Rect(6, 10, 40, 22)
    pygame.draw.rect(surf, (108, 78, 50), box)
    pygame.draw.rect(surf, (66, 46, 28), box, 2)
    for y_row in range(14, 32, 6):
        pygame.draw.line(surf, (82, 58, 36), (6, y_row), (46, y_row), 1)
    snow_pts = [(6, 10), (46, 10), (42, 4), (10, 4)]
    pygame.draw.polygon(surf, (218, 228, 240), snow_pts)
    return _crop_alpha(surf, 0)


def _ice_dead_campfire() -> pygame.Surface:
    surf = pygame.Surface((44, 28), pygame.SRCALPHA)
    pygame.draw.ellipse(surf, (0, 0, 0, 44), (6, 22, 32, 6))
    pygame.draw.ellipse(surf, (62, 58, 52), (8, 16, 28, 10))
    for ax, ay, bx, by in [(16, 20, 12, 10), (22, 20, 22, 8), (28, 20, 32, 10), (22, 20, 18, 12), (22, 20, 26, 12)]:
        pygame.draw.line(surf, (72, 54, 36), (ax, ay), (bx, by), 2)
    pygame.draw.ellipse(surf, (44, 40, 36), (12, 16, 20, 8))
    pygame.draw.ellipse(surf, (218, 228, 240), (6, 20, 32, 6))
    return _crop_alpha(surf, 0)


def _ice_mammoth_bones() -> pygame.Surface:
    surf = pygame.Surface((156, 78), pygame.SRCALPHA)
    pygame.draw.ellipse(surf, (0, 0, 0, 46), (8, 68, 140, 10))
    bc = (216, 208, 192)
    dk2 = (168, 160, 144)
    pygame.draw.ellipse(surf, bc, (8, 48, 44, 18))
    pygame.draw.ellipse(surf, dk2, (8, 48, 44, 18), 1)
    pygame.draw.ellipse(surf, bc, (104, 44, 44, 20))
    pygame.draw.ellipse(surf, dk2, (104, 44, 44, 20), 1)
    for bx2, by2, blen, bang in [(20, 56, 50, -28), (90, 56, 46, 210), (46, 62, 38, 15), (108, 60, 34, 165)]:
        rad = math.radians(bang)
        ex2 = int(bx2 + math.cos(rad) * blen)
        ey2 = int(by2 + math.sin(rad) * blen // 3)
        pygame.draw.line(surf, bc, (bx2, by2), (ex2, ey2), 5)
        pygame.draw.line(surf, dk2, (bx2, by2), (ex2, ey2), 2)
    tusk_pts = [(10, 52), (26, 44), (60, 40), (90, 46), (104, 56)]
    pygame.draw.lines(surf, bc, False, tusk_pts, 5)
    pygame.draw.lines(surf, dk2, False, tusk_pts, 2)
    snow_c2 = (218, 226, 238)
    for sx2, sy2, sw2, sh2 in [(10, 56, 36, 8), (100, 52, 40, 8), (50, 62, 30, 6)]:
        pygame.draw.ellipse(surf, snow_c2, (sx2, sy2, sw2, sh2))
    return _crop_alpha(surf, 0)


def _ice_skull_pole() -> pygame.Surface:
    surf = pygame.Surface((20, 68), pygame.SRCALPHA)
    pygame.draw.ellipse(surf, (0, 0, 0, 46), (4, 62, 12, 6))
    pygame.draw.line(surf, (78, 58, 42), (10, 62), (10, 18), 3)
    pygame.draw.line(surf, (56, 40, 26), (9, 62), (9, 18), 1)
    pygame.draw.ellipse(surf, (198, 192, 178), (4, 8, 12, 10))
    pygame.draw.ellipse(surf, (160, 154, 140), (4, 8, 12, 10), 1)
    pygame.draw.ellipse(surf, (68, 60, 54), (6, 10, 3, 3))
    pygame.draw.ellipse(surf, (68, 60, 54), (11, 10, 3, 3))
    pygame.draw.line(surf, (160, 154, 140), (6, 14), (14, 14), 1)
    for hx, hy, hr in [(6, 4), (14, 6), (4, 8)]:
        pygame.draw.circle(surf, (214, 208, 194), (hx, hy + hr), 2)
    return _crop_alpha(surf, 0)


def _ice_frost_lantern() -> pygame.Surface:
    surf = pygame.Surface((22, 48), pygame.SRCALPHA)
    pygame.draw.ellipse(surf, (0, 0, 0, 46), (4, 42, 14, 6))
    pygame.draw.line(surf, (88, 88, 98), (11, 42), (11, 8), 2)
    pygame.draw.rect(surf, (80, 84, 94), (5, 8, 12, 16), border_radius=2)
    pygame.draw.rect(surf, (48, 52, 62), (5, 8, 12, 16), 1, border_radius=2)
    glow = pygame.Surface((22, 48), pygame.SRCALPHA)
    pygame.draw.ellipse(glow, (160, 220, 255, 110), (6, 9, 10, 14))
    surf.blit(glow, (0, 0))
    pygame.draw.ellipse(surf, (200, 234, 255), (7, 10, 6, 10))
    pygame.draw.circle(surf, (220, 242, 255), (11, 8), 5)
    cap_pts = [(4, 8), (18, 8), (16, 4), (6, 4)]
    pygame.draw.polygon(surf, (86, 90, 100), cap_pts)
    outer_glow = pygame.Surface((22, 48), pygame.SRCALPHA)
    pygame.draw.circle(outer_glow, (180, 220, 255, 40), (11, 15), 14)
    surf.blit(outer_glow, (0, 0))
    return _crop_alpha(surf, 0)


def _ice_bone_totem() -> pygame.Surface:
    surf = pygame.Surface((30, 74), pygame.SRCALPHA)
    pygame.draw.ellipse(surf, (0, 0, 0, 48), (6, 66, 18, 8))
    pygame.draw.line(surf, (80, 60, 44), (15, 66), (15, 10), 3)
    pygame.draw.line(surf, (58, 42, 28), (14, 66), (14, 10), 1)
    for hy, blen in [(24, 12), (36, 10), (48, 8)]:
        pygame.draw.line(surf, (186, 180, 166), (15, hy), (15 - blen, hy - 4), 2)
        pygame.draw.line(surf, (186, 180, 166), (15, hy), (15 + blen, hy - 4), 2)
        pygame.draw.circle(surf, (196, 190, 176), (15 - blen, hy - 4), 2)
        pygame.draw.circle(surf, (196, 190, 176), (15 + blen, hy - 4), 2)
    pygame.draw.ellipse(surf, (200, 194, 180), (9, 6, 12, 10))
    pygame.draw.ellipse(surf, (162, 156, 142), (9, 6, 12, 10), 1)
    pygame.draw.ellipse(surf, (64, 58, 52), (11, 8, 3, 3))
    pygame.draw.ellipse(surf, (64, 58, 52), (16, 8, 3, 3))
    return _crop_alpha(surf, 0)


def _ice_fish_rack() -> pygame.Surface:
    surf = pygame.Surface((82, 60), pygame.SRCALPHA)
    pygame.draw.ellipse(surf, (0, 0, 0, 46), (4, 52, 74, 8))
    wc2 = (98, 70, 46)
    pygame.draw.line(surf, wc2, (10, 52), (10, 12), 4)
    pygame.draw.line(surf, wc2, (72, 52), (72, 12), 4)
    pygame.draw.line(surf, wc2, (10, 14), (72, 14), 3)
    for fx in range(18, 66, 12):
        pygame.draw.polygon(surf, (168, 124, 84), [(fx, 14), (fx + 6, 14), (fx + 4, 34), (fx + 2, 34)])
        pygame.draw.polygon(surf, (136, 96, 60), [(fx, 14), (fx + 6, 14), (fx + 4, 34), (fx + 2, 34)], 1)
        pygame.draw.circle(surf, (200, 196, 182), (fx + 3, 14), 2)
    return _crop_alpha(surf, 0)


def _ice_sled() -> pygame.Surface:
    surf = pygame.Surface((104, 38), pygame.SRCALPHA)
    pygame.draw.ellipse(surf, (0, 0, 0, 48), (8, 30, 88, 8))
    wc3 = (108, 76, 48)
    dk3 = (70, 46, 26)
    pygame.draw.rect(surf, wc3, (10, 12, 84, 14), border_radius=4)
    pygame.draw.rect(surf, dk3, (10, 12, 84, 14), 2, border_radius=4)
    for rx in range(18, 90, 12):
        pygame.draw.line(surf, dk3, (rx, 12), (rx, 26), 1)
    pygame.draw.rect(surf, (136, 96, 60), (10, 26, 84, 6), border_radius=2)
    pygame.draw.line(surf, (150, 112, 72), (14, 29), (90, 29), 1)
    pygame.draw.ellipse(surf, shade(wc3, -8), (8, 24, 12, 8))
    pygame.draw.ellipse(surf, shade(wc3, -8), (84, 24, 12, 8))
    pygame.draw.line(surf, (168, 130, 90), (8, 12), (14, 4), 2)
    pygame.draw.circle(surf, (168, 130, 90), (14, 4), 3)
    return _crop_alpha(surf, 0)


def _ice_hunter_trap() -> pygame.Surface:
    surf = pygame.Surface((34, 24), pygame.SRCALPHA)
    pygame.draw.ellipse(surf, (0, 0, 0, 42), (4, 18, 26, 6))
    mc = (108, 112, 122)
    pygame.draw.ellipse(surf, mc, (4, 8, 26, 14))
    pygame.draw.ellipse(surf, shade(mc, -20), (4, 8, 26, 14), 2)
    for tx, ty in [(4, 8), (7, 6), (10, 5), (13, 4), (16, 4), (19, 5), (22, 6), (25, 8), (28, 9)]:
        pygame.draw.line(surf, shade(mc, -14), (tx, ty), (tx + 1, ty - 2), 1)
    pygame.draw.line(surf, (138, 142, 152), (4, 14), (30, 14), 2)
    pygame.draw.line(surf, (170, 174, 184), (4, 12), (30, 12), 1)
    pygame.draw.rect(surf, (86, 90, 100), (15, 10, 4, 8))
    return _crop_alpha(surf, 0)


def _origin(mode: str) -> Dict[str, object]:
    if mode == "bottom_center":
        return {"mode": "bottom_center", "x": 0.5, "y": 1.0}
    return {"mode": "center", "x": 0.5, "y": 0.5}


def _collision(x: int, y: int, w: int, h: int) -> Dict[str, int]:
    return {"x": x, "y": y, "w": w, "h": h}


def generate_medieval_pack(seed: int, out_dir: str) -> Dict[str, object]:
    rng = random.Random(int(seed))
    pygame.init()
    os.makedirs(out_dir, exist_ok=True)
    records: List[Dict[str, object]] = []
    catalog: List[Dict[str, object]] = []
    tile_size = 32

    def add_asset(
        asset_id: str,
        category: str,
        folder: str,
        base_name: str,
        surface: Optional[pygame.Surface] = None,
        frames: Optional[List[pygame.Surface]] = None,
        origin_mode: str = "center",
        layer: str = "GROUND",
        tags: Optional[List[str]] = None,
        collision: Optional[Dict[str, int]] = None,
        variants: Optional[List[str]] = None,
        variant_index: Optional[int] = None,
        fps: Optional[int] = None,
        extra: Optional[Dict[str, object]] = None,
    ) -> None:
        rel_dir = folder.replace("/", os.sep)
        if frames:
            frame_paths: List[str] = []
            for index, frame_surface in enumerate(frames):
                rel_path = os.path.join(rel_dir, f"{base_name}_{index:02d}.png")
                export_png(frame_surface, os.path.join(out_dir, rel_path))
                records.append({"path": rel_path.replace("\\", "/"), "_surface": frame_surface})
                frame_paths.append(rel_path.replace("\\", "/"))
            first_surface = frames[0]
            path = frame_paths[0]
            animation = {"frames": frame_paths, "fps": int(fps or 6)}
        else:
            assert isinstance(surface, pygame.Surface)
            rel_path = os.path.join(rel_dir, f"{base_name}.png")
            export_png(surface, os.path.join(out_dir, rel_path))
            records.append({"path": rel_path.replace("\\", "/"), "_surface": surface})
            first_surface = surface
            path = rel_path.replace("\\", "/")
            animation = None
        entry: Dict[str, object] = {
            "id": asset_id,
            "category": category,
            "path": path,
            "w": int(first_surface.get_width()),
            "h": int(first_surface.get_height()),
            "origin": _origin(origin_mode),
            "layer": layer,
            "collision": collision,
            "tags": list(tags or []),
            "variants": list(variants or []),
            "variant_index": variant_index,
            "animation": animation,
        }
        if extra:
            entry.update(extra)
        catalog.append(entry)

    terrain_ids: Dict[str, List[str]] = {}
    for terrain_kind in ("grass", "dirt", "mud", "cobble", "wood_floor"):
        terrain_ids[terrain_kind] = []
        for variant in range(2):
            asset_id = f"terrain_{terrain_kind}_{variant + 1}"
            terrain_ids[terrain_kind].append(asset_id)
            add_asset(
                asset_id,
                "Terrain",
                "tiles/terrain",
                asset_id,
                surface=_make_terrain_tile(tile_size, terrain_kind, variant, rng),
                origin_mode="center",
                layer="GROUND",
                tags=["tile", "terrain", terrain_kind],
                variants=terrain_ids[terrain_kind][:],
                variant_index=variant,
            )
    for terrain_kind, ids in terrain_ids.items():
        for asset_id in ids:
            for entry in catalog:
                if entry["id"] == asset_id:
                    entry["variants"] = ids

    road_base = _make_terrain_tile(tile_size, "dirt", 0, random.Random(seed + 900))
    road_variants = {
        "road_end_n": "n",
        "road_end_s": "s",
        "road_end_w": "w",
        "road_end_e": "e",
        "road_straight_ns": "ns",
        "road_straight_we": "we",
        "road_corner_ne": "ne",
        "road_corner_nw": "nw",
        "road_corner_se": "se",
        "road_corner_sw": "sw",
        "road_t_nwe": "nwe",
        "road_t_nse": "nse",
        "road_t_nsw": "nsw",
        "road_t_swe": "swe",
        "road_cross": "nswe",
    }
    road_ids = list(road_variants.keys())
    for index, (asset_id, mask) in enumerate(road_variants.items()):
        add_asset(
            asset_id,
            "Roads",
            "tiles/roads",
            asset_id,
            surface=_road_tile(tile_size, mask, road_base),
            origin_mode="center",
            layer="GROUND",
            tags=["tile", "road", "autotile"],
            variants=road_ids,
            variant_index=index,
            extra={"autotile_group": "dirt_road", "autotile_mask": mask},
        )

    water_frames = [_water_frame(tile_size, frame) for frame in range(6)]
    add_asset(
        "water_deep",
        "Water",
        "tiles/water",
        "water_deep",
        frames=water_frames,
        origin_mode="center",
        layer="GROUND",
        tags=["tile", "water", "animated"],
        fps=6,
    )
    shore_ids = ["shore_north", "shore_south", "shore_west", "shore_east", "shore_nw", "shore_ne", "shore_sw", "shore_se"]
    for index, edge in enumerate(("north", "south", "west", "east", "nw", "ne", "sw", "se")):
        add_asset(
            shore_ids[index],
            "Water",
            "tiles/water",
            shore_ids[index],
            surface=_shore_tile(tile_size, edge),
            origin_mode="center",
            layer="GROUND",
            tags=["tile", "water", "shore"],
            variants=shore_ids,
            variant_index=index,
        )

    add_asset("nature_grass_tuft", "Nature", "props/nature", "grass_tuft", surface=_make_terrain_tile(18, "grass", 0, rng), origin_mode="bottom_center", layer="DECOR", tags=["prop", "nature", "grass"])
    add_asset("nature_flowers", "Nature", "props/nature", "flowers", surface=_make_terrain_tile(20, "grass", 1, rng), origin_mode="bottom_center", layer="DECOR", tags=["prop", "nature", "flowers"])
    add_asset("nature_rocks", "Nature", "props/nature", "rocks", surface=_crop_alpha(_prop_crate(), 0), origin_mode="bottom_center", layer="DECOR", tags=["prop", "nature", "rocks"])
    add_asset("nature_bush", "Nature", "props/nature", "bush", surface=_bush_surface(), origin_mode="bottom_center", layer="OBJECT", tags=["prop", "nature", "bush"])
    add_asset("nature_tree", "Nature", "props/nature", "tree", surface=_tree_surface(), origin_mode="bottom_center", layer="OBJECT", tags=["prop", "nature", "tree"], collision=_collision(20, 72, 24, 14))
    add_asset("nature_tree_shadow", "Nature", "props/nature", "tree_shadow", surface=_tree_shadow_surface(), origin_mode="center", layer="GROUND", tags=["shadow", "nature"])

    add_asset("container_barrel", "Containers", "props/containers", "barrel", surface=_prop_barrel(), origin_mode="bottom_center", layer="OBJECT", tags=["prop", "container", "lootable"], collision=_collision(8, 34, 32, 18))
    add_asset("container_crate", "Containers", "props/containers", "crate", surface=_prop_crate(), origin_mode="bottom_center", layer="OBJECT", tags=["prop", "container", "lootable"], collision=_collision(6, 18, 32, 16))
    add_asset("container_sack", "Containers", "props/containers", "sack", surface=_prop_sack(), origin_mode="bottom_center", layer="OBJECT", tags=["prop", "container"])
    add_asset("container_chest_closed", "Containers", "props/containers", "chest_closed", surface=_prop_chest(False), origin_mode="bottom_center", layer="OBJECT", tags=["prop", "container", "lootable"], collision=_collision(8, 18, 36, 16))
    add_asset("container_chest_open", "Containers", "props/containers", "chest_open", surface=_prop_chest(True), origin_mode="bottom_center", layer="OBJECT", tags=["prop", "container", "lootable"])

    add_asset("furniture_table", "Furniture", "props/furniture", "table", surface=_prop_table(), origin_mode="bottom_center", layer="OBJECT", tags=["prop", "furniture"], collision=_collision(8, 16, 58, 24))
    add_asset("furniture_chair", "Furniture", "props/furniture", "chair", surface=_prop_chair(), origin_mode="bottom_center", layer="OBJECT", tags=["prop", "furniture"], collision=_collision(8, 18, 18, 18))
    add_asset("furniture_bed", "Furniture", "props/furniture", "bed", surface=_prop_bed(), origin_mode="bottom_center", layer="OBJECT", tags=["prop", "furniture"], collision=_collision(8, 18, 76, 16))
    add_asset("furniture_bookshelf", "Furniture", "props/furniture", "bookshelf", surface=_prop_bookshelf(), origin_mode="bottom_center", layer="OBJECT", tags=["prop", "furniture"], collision=_collision(12, 20, 36, 54))
    add_asset("furniture_rug", "Furniture", "props/furniture", "rug", surface=_prop_rug(), origin_mode="center", layer="DECOR", tags=["prop", "furniture", "rug"])

    house_ids = ["house_prefab_stone", "house_prefab_timber", "house_prefab_forge"]
    for index, house_id in enumerate(house_ids):
        add_asset(
            house_id,
            "Houses",
            "structures/houses",
            house_id,
            surface=_house_prefab(index),
            origin_mode="bottom_center",
            layer="OBJECT",
            tags=["structure", "house"],
            variants=house_ids,
            variant_index=index,
            collision=_collision(24, 76, 80, 32),
        )
    for modular_kind in ("wall", "corner", "door", "window", "roof"):
        add_asset(
            f"house_mod_{modular_kind}",
            "Houses",
            "structures/houses",
            f"house_mod_{modular_kind}",
            surface=_wall_piece(modular_kind),
            origin_mode="center",
            layer="OBJECT" if modular_kind in ("wall", "corner", "door", "window") else "OVERLAY",
            tags=["structure", "house", "modular", modular_kind],
        )

    add_asset("vfx_bolt_cast_flash", "VFX", "vfx/spells", "bolt_cast_flash", frames=[_bolt_cast_frame(i) for i in range(3)], origin_mode="center", layer="VFX", tags=["vfx", "spell", "bolt"], fps=10)
    add_asset("vfx_bolt_projectile", "VFX", "vfx/spells", "bolt_projectile", frames=[_bolt_projectile_frame(i) for i in range(4)], origin_mode="center", layer="VFX", tags=["vfx", "spell", "bolt"], fps=12)
    add_asset("vfx_bolt_impact", "VFX", "vfx/spells", "bolt_impact", frames=[_bolt_impact_frame(i) for i in range(6)], origin_mode="center", layer="VFX", tags=["vfx", "spell", "bolt"], fps=12)
    add_asset("vfx_summon_rune", "VFX", "vfx/spells", "summon_rune", frames=[_summon_rune_frame(i) for i in range(6)], origin_mode="center", layer="VFX", tags=["vfx", "spell", "summon"], fps=8)
    add_asset("ambient_fire_small", "VFX", "vfx/ambient", "fire_small", frames=[_fire_frame(i) for i in range(8)], origin_mode="bottom_center", layer="VFX", tags=["vfx", "ambient", "fire"], fps=10)
    add_asset("ambient_smoke_puff", "VFX", "vfx/ambient", "smoke_puff", frames=[_smoke_frame(i) for i in range(6)], origin_mode="center", layer="VFX", tags=["vfx", "ambient", "smoke"], fps=9)

    # ── Frozen Tundra: Terrain ────────────────────────────────────────────────
    ice_terrain_kinds = ("snow", "ice", "permafrost", "tundra_rock", "frozen_ground")
    ice_terrain_ids: Dict[str, List[str]] = {}
    for kind in ice_terrain_kinds:
        ice_terrain_ids[kind] = []
        for variant in range(2):
            asset_id = f"ice_terrain_{kind}_{variant + 1}"
            ice_terrain_ids[kind].append(asset_id)
            add_asset(
                asset_id, "Frozen Terrain", f"tiles/ice_terrain", asset_id,
                surface=_make_ice_terrain(tile_size, kind, variant, rng),
                origin_mode="center", layer="GROUND",
                tags=["tile", "terrain", "ice", kind],
                variants=ice_terrain_ids[kind][:], variant_index=variant,
            )
    for kind, ids in ice_terrain_ids.items():
        for a_id in ids:
            for entry in catalog:
                if entry["id"] == a_id:
                    entry["variants"] = ids

    # ── Frozen Tundra: Frozen Road (autotile) ─────────────────────────────────
    frozen_road_base = _make_ice_terrain(tile_size, "tundra_rock", 0, random.Random(seed + 777))
    frozen_road_variants = {
        "frozen_road_end_n":      "n",
        "frozen_road_end_s":      "s",
        "frozen_road_end_w":      "w",
        "frozen_road_end_e":      "e",
        "frozen_road_straight_ns":"ns",
        "frozen_road_straight_we":"we",
        "frozen_road_corner_ne":  "ne",
        "frozen_road_corner_nw":  "nw",
        "frozen_road_corner_se":  "se",
        "frozen_road_corner_sw":  "sw",
        "frozen_road_t_nwe":      "nwe",
        "frozen_road_t_nse":      "nse",
        "frozen_road_t_nsw":      "nsw",
        "frozen_road_t_swe":      "swe",
        "frozen_road_cross":      "nswe",
    }
    frozen_road_ids = list(frozen_road_variants.keys())
    for idx2, (asset_id, mask) in enumerate(frozen_road_variants.items()):
        add_asset(
            asset_id, "Frozen Roads", "tiles/frozen_roads", asset_id,
            surface=_frozen_road_tile(tile_size, mask, frozen_road_base),
            origin_mode="center", layer="GROUND",
            tags=["tile", "road", "autotile", "ice"],
            variants=frozen_road_ids, variant_index=idx2,
            extra={"autotile_group": "frozen_road", "autotile_mask": mask},
        )

    # ── Frozen Tundra: Nature ─────────────────────────────────────────────────
    add_asset("ice_pine_snowy",       "Ice Nature", "props/ice/nature", "ice_pine_snowy",       surface=_ice_pine_snowy(),       origin_mode="bottom_center", layer="OBJECT", tags=["prop", "nature", "ice", "tree"],   collision=_collision(28, 80, 24, 20))
    add_asset("ice_pine_bent",        "Ice Nature", "props/ice/nature", "ice_pine_bent",        surface=_ice_pine_bent(),        origin_mode="bottom_center", layer="OBJECT", tags=["prop", "nature", "ice", "tree"],   collision=_collision(22, 64, 22, 18))
    add_asset("ice_dead_tree",        "Ice Nature", "props/ice/nature", "ice_dead_tree",        surface=_ice_dead_tree(),        origin_mode="bottom_center", layer="OBJECT", tags=["prop", "nature", "ice", "tree"],   collision=_collision(20, 70, 24, 16))
    add_asset("ice_dead_tree_small",  "Ice Nature", "props/ice/nature", "ice_dead_tree_small",  surface=_ice_dead_tree_small(),  origin_mode="bottom_center", layer="OBJECT", tags=["prop", "nature", "ice", "tree"],   collision=_collision(14, 50, 18, 14))
    add_asset("ice_crystal_large",    "Ice Nature", "props/ice/nature", "ice_crystal_large",    surface=_ice_crystal_large(),    origin_mode="bottom_center", layer="OBJECT", tags=["prop", "nature", "ice", "crystal"], collision=_collision(10, 30, 16, 30))
    add_asset("ice_crystal_cluster",  "Ice Nature", "props/ice/nature", "ice_crystal_cluster",  surface=_ice_crystal_cluster(),  origin_mode="bottom_center", layer="OBJECT", tags=["prop", "nature", "ice", "crystal"])
    add_asset("ice_snowdrift_large",  "Ice Nature", "props/ice/nature", "ice_snowdrift_large",  surface=_ice_snowdrift_large(),  origin_mode="bottom_center", layer="DECOR",  tags=["prop", "nature", "ice", "snow"])
    add_asset("ice_snowdrift_small",  "Ice Nature", "props/ice/nature", "ice_snowdrift_small",  surface=_ice_snowdrift_small(),  origin_mode="bottom_center", layer="DECOR",  tags=["prop", "nature", "ice", "snow"])
    add_asset("ice_icicle_group",     "Ice Nature", "props/ice/nature", "ice_icicle_group",     surface=_ice_icicle_group(),     origin_mode="bottom_center", layer="OBJECT", tags=["prop", "nature", "ice", "icicle"])
    add_asset("ice_frozen_log",       "Ice Nature", "props/ice/nature", "ice_frozen_log",       surface=_ice_frozen_log(),       origin_mode="bottom_center", layer="DECOR",  tags=["prop", "nature", "ice", "log"])
    add_asset("ice_frost_bush",       "Ice Nature", "props/ice/nature", "ice_frost_bush",       surface=_ice_frost_bush(),       origin_mode="bottom_center", layer="OBJECT", tags=["prop", "nature", "ice", "bush"])
    add_asset("ice_tundra_grass",     "Ice Nature", "props/ice/nature", "ice_tundra_grass",     surface=_ice_tundra_grass(),     origin_mode="bottom_center", layer="DECOR",  tags=["prop", "nature", "ice", "grass"])
    add_asset("ice_frost_flower",     "Ice Nature", "props/ice/nature", "ice_frost_flower",     surface=_ice_frost_flower(),     origin_mode="center",        layer="DECOR",  tags=["prop", "nature", "ice", "flower"])
    add_asset("ice_snow_boulder_large","Ice Nature", "props/ice/nature", "ice_snow_boulder_large", surface=_ice_snow_boulder_large(), origin_mode="bottom_center", layer="OBJECT", tags=["prop", "nature", "ice", "boulder"], collision=_collision(8, 18, 44, 20))
    add_asset("ice_snow_boulder_small","Ice Nature", "props/ice/nature", "ice_snow_boulder_small", surface=_ice_snow_boulder_small(), origin_mode="bottom_center", layer="OBJECT", tags=["prop", "nature", "ice", "boulder"], collision=_collision(4, 12, 30, 14))

    # ── Frozen Tundra: Structures ─────────────────────────────────────────────
    add_asset("ice_hunter_hut",         "Ice Structures", "structures/ice", "ice_hunter_hut",         surface=_ice_hunter_hut(),         origin_mode="bottom_center", layer="OBJECT", tags=["structure", "ice", "building"], collision=_collision(22, 64, 84, 34))
    add_asset("ice_frost_shrine",       "Ice Structures", "structures/ice", "ice_frost_shrine",       surface=_ice_frost_shrine(),       origin_mode="bottom_center", layer="OBJECT", tags=["structure", "ice", "shrine"],   collision=_collision(16, 36, 20, 48))
    add_asset("ice_stone_pillar_frozen","Ice Structures", "structures/ice", "ice_stone_pillar_frozen", surface=_ice_stone_pillar_frozen(), origin_mode="bottom_center", layer="OBJECT", tags=["structure", "ice", "pillar"],  collision=_collision(4, 24, 20, 48))
    add_asset("ice_cave_entrance",      "Ice Structures", "structures/ice", "ice_cave_entrance",      surface=_ice_cave_entrance(),      origin_mode="bottom_center", layer="OBJECT", tags=["structure", "ice", "cave"],     collision=_collision(34, 24, 60, 40))
    add_asset("ice_broken_watchtower",  "Ice Structures", "structures/ice", "ice_broken_watchtower",  surface=_ice_broken_watchtower(),  origin_mode="bottom_center", layer="OBJECT", tags=["structure", "ice", "ruin"],    collision=_collision(14, 80, 60, 60))
    add_asset("ice_frozen_wagon",       "Ice Structures", "structures/ice", "ice_frozen_wagon",       surface=_ice_frozen_wagon(),       origin_mode="bottom_center", layer="OBJECT", tags=["structure", "ice", "vehicle"], collision=_collision(14, 30, 90, 22))
    add_asset("ice_stone_cairn",        "Ice Structures", "structures/ice", "ice_stone_cairn",        surface=_ice_stone_cairn(),        origin_mode="bottom_center", layer="OBJECT", tags=["structure", "ice", "cairn"])

    # ── Frozen Tundra: Props ──────────────────────────────────────────────────
    add_asset("ice_frozen_barrel",  "Ice Props", "props/ice/props", "ice_frozen_barrel",  surface=_ice_frozen_barrel(),  origin_mode="bottom_center", layer="OBJECT", tags=["prop", "ice", "container"], collision=_collision(8, 20, 32, 28))
    add_asset("ice_supply_cache",   "Ice Props", "props/ice/props", "ice_supply_cache",   surface=_ice_supply_cache(),   origin_mode="bottom_center", layer="OBJECT", tags=["prop", "ice", "container"], collision=_collision(6, 12, 40, 18))
    add_asset("ice_dead_campfire",  "Ice Props", "props/ice/props", "ice_dead_campfire",  surface=_ice_dead_campfire(),  origin_mode="bottom_center", layer="DECOR",  tags=["prop", "ice", "campfire"])
    add_asset("ice_mammoth_bones",  "Ice Props", "props/ice/props", "ice_mammoth_bones",  surface=_ice_mammoth_bones(),  origin_mode="bottom_center", layer="DECOR",  tags=["prop", "ice", "bones"])
    add_asset("ice_skull_pole",     "Ice Props", "props/ice/props", "ice_skull_pole",     surface=_ice_skull_pole(),     origin_mode="bottom_center", layer="OBJECT", tags=["prop", "ice", "marker"],    collision=_collision(4, 20, 12, 42))
    add_asset("ice_frost_lantern",  "Ice Props", "props/ice/props", "ice_frost_lantern",  surface=_ice_frost_lantern(),  origin_mode="bottom_center", layer="OBJECT", tags=["prop", "ice", "light"],     collision=_collision(4, 12, 14, 24))
    add_asset("ice_bone_totem",     "Ice Props", "props/ice/props", "ice_bone_totem",     surface=_ice_bone_totem(),     origin_mode="bottom_center", layer="OBJECT", tags=["prop", "ice", "totem"],     collision=_collision(6, 20, 18, 44))
    add_asset("ice_fish_rack",      "Ice Props", "props/ice/props", "ice_fish_rack",      surface=_ice_fish_rack(),      origin_mode="bottom_center", layer="OBJECT", tags=["prop", "ice", "rack"],      collision=_collision(8, 14, 66, 36))
    add_asset("ice_sled",           "Ice Props", "props/ice/props", "ice_sled",           surface=_ice_sled(),           origin_mode="bottom_center", layer="DECOR",  tags=["prop", "ice", "vehicle"])
    add_asset("ice_hunter_trap",    "Ice Props", "props/ice/props", "ice_hunter_trap",    surface=_ice_hunter_trap(),    origin_mode="bottom_center", layer="DECOR",  tags=["prop", "ice", "trap"])

    atlas_json = pack_atlas(records, out_dir)
    with open(os.path.join(out_dir, "catalog.json"), "w", encoding="utf-8") as handle:
        json.dump({"seed": int(seed), "assets": catalog}, handle, indent=2)
    overrides_path = os.path.join(out_dir, "catalog_overrides.json")
    if not os.path.exists(overrides_path):
        with open(overrides_path, "w", encoding="utf-8") as handle:
            json.dump({}, handle, indent=2)
    manifest = {
        "seed": int(seed),
        "catalog": "catalog.json",
        "overrides": "catalog_overrides.json",
        "atlas": atlas_json["image"],
        "atlas_json": "atlas/atlas.json",
        "asset_count": len(catalog),
    }
    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)
    pygame.quit()
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a procedural medieval RPG asset pack.")
    parser.add_argument("--seed", type=int, default=123, help="Deterministic generation seed.")
    parser.add_argument("--out", type=str, default=os.path.join("assets_generated", "medieval_rpg"), help="Output directory.")
    args = parser.parse_args()
    manifest = generate_medieval_pack(args.seed, args.out)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
