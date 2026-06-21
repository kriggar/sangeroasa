"""game/render/props.py — decorative prop, building, scenery & town-piece draw helpers.
Pure draw functions (surface + params in); depend only on constants/utils/vfx."""
import os
import math
import random
import colorsys
from typing import Dict, List, Optional, Tuple, Any, Union, Set

import pygame
from pygame import Vector2

from game.constants import HORIZON_Y, MEDIEVAL_PACK_ROOT, SCREEN_HEIGHT, SCREEN_WIDTH
from game.utils import clamp, lerp, exp_smooth, rotate_vec, color_lerp, hsv_to_rgb, point_in_rect
from game.vfx import spawn_particle_burst, spawn_blood_splatter

__all__ = [
    'draw_poly_aa',
    'draw_round_segment',
    'draw_vertical_gradient',
    'draw_cobblestones',
    'draw_cloud',
    'draw_dead_tree',
    'draw_pine_tree',
    'draw_boulder',
    'draw_spell_anim',
    'draw_lamppost',
    'draw_market_stall',
    '_house_hash',
    '_draw_wall_weathering',
    '_draw_house_lantern',
    '_draw_house_extras',
    '_draw_house_variations',
    '_draw_house_shadow',
    '_draw_house_stone_foundation',
    '_draw_house_window',
    '_draw_house_door',
    '_draw_house_chimney',
    '_draw_house_tudor',
    '_draw_house_stone',
    '_draw_house_cottage',
    '_draw_house_merchant',
    '_draw_house_rowhouse',
    '_draw_house_workshop',
    '_house_chimney_top',
    'draw_house',
    'draw_church',
    'draw_well',
    'draw_grass_patch',
    'draw_brazier',
    'draw_barrel',
    'draw_cauldron',
    'draw_wood_crate',
    'draw_hay_bale',
    'draw_lumber_stack',
    'draw_banner_post',
    'draw_market_cart',
    'draw_fence_segment',
    'draw_fence_segment_vertical',
    'draw_wattle_fence_segment',
    'draw_wattle_fence_segment_vertical',
    'draw_low_stone_wall_segment',
    'draw_low_stone_wall_segment_vertical',
    'draw_cubic_stone_road',
    'draw_stocks',
    'draw_gallows',
    'draw_weapon_rack',
    'draw_fountain',
    'draw_laundry_line',
    'draw_wooden_bench',
    'draw_water_trough',
    'draw_notice_board',
    'draw_woodpile',
    'draw_flower_box',
    'draw_rain_barrel',
    'draw_sack_pile',
    'draw_stone_planter',
    'draw_horse_hitch',
    'draw_well_bucket',
    'draw_hanging_sign',
    'draw_meat_rack',
    'draw_training_dummy',
    'draw_grave_stone',
    'draw_forge_prop',
    'draw_hd_forge_prop',
    'draw_anvil',
    'draw_hd_anvil',
    'draw_gladiator_arena',
    'draw_market_awning',
    'draw_wine_rack',
    'draw_potted_tree',
    'draw_signpost',
    'draw_water_pump',
    'draw_torch_stand',
    'draw_wall_torch',
    'draw_pottery_stack',
    'draw_fire_pit',
    'draw_stone_arch',
    'draw_district_ground',
    'draw_canal_water',
    'draw_stone_bridge',
    'draw_gothic_spire',
    'draw_fortified_wall',
    'draw_district_house',
    '_district_house_chimney_top',
    'collect_district_chimney_tops',
    'draw_cathedral_v2',
    'draw_hd_barrel',
    'draw_hd_hay',
    'draw_hd_cart',
    'draw_transylvanian_asset',
    'draw_paved_road',
    'draw_dirt_road',
    '_pen_soft_shadow',
    '_pen_plank_wall',
    '_pen_shake_roof',
    '_pen_straw_pile',
    'draw_chicken_coop',
    '_draw_round_post',
    '_draw_perimeter_rail',
    '_draw_yard_fence',
    'draw_pig_pen',
    'draw_sheep_pen',
    'draw_dock',
    'draw_small_boat',
    'draw_sailing_ship',
    'draw_cemetery_gate',
    'draw_iron_fence',
    'draw_iron_fence_vertical',
    'draw_cemetery_mausoleum',
    'draw_harbour_water',
    '_TOWN_CHIMNEY_TOPS',
    '_TOWN_LANDMARK_RECTS',
    '_draw_pennant_string',
    '_draw_bunting_span',
    '_draw_small_bird',
    'draw_stone_curtain_wall',
    '_draw_palisade_watchpost',
    'draw_palisade_v',
    'draw_town_hall',
    'draw_windmill',
    'draw_granary',
    'draw_washhouse',
    'draw_wayside_shrine',
    '_draw_town_wilderness_gate',
    '_draw_gate_vfx',
    '_draw_giant_fire_pit',
    '_draw_fire_pit_vfx',
]


def draw_poly_aa(
    surface: pygame.Surface,
    color: tuple[int, int, int],
    points: List[Tuple[float, float]],
    outline: Optional[Tuple[int, int, int]] = None,
) -> None:
    if len(points) < 3:
        return
    int_points = [(int(round(px)), int(round(py))) for px, py in points]
    pygame.gfxdraw.filled_polygon(surface, int_points, color)
    pygame.gfxdraw.aapolygon(surface, int_points, color)
    if outline is not None:
        pygame.draw.polygon(surface, outline, int_points, 1)


def draw_round_segment(
    surface: pygame.Surface,
    a: Tuple[float, float],
    b: Tuple[float, float],
    width: int,
    color: Tuple[int, int, int],
    outline: Optional[Tuple[int, int, int]] = None,
) -> None:
    ax = int(round(a[0]))
    ay = int(round(a[1]))
    bx = int(round(b[0]))
    by = int(round(b[1]))
    pygame.draw.line(surface, color, (ax, ay), (bx, by), width)
    radius = max(1, width // 2)
    pygame.gfxdraw.filled_circle(surface, ax, ay, radius, color)
    pygame.gfxdraw.filled_circle(surface, bx, by, radius, color)
    pygame.gfxdraw.aacircle(surface, ax, ay, radius, color)
    pygame.gfxdraw.aacircle(surface, bx, by, radius, color)
    if outline is not None:
        pygame.draw.line(surface, outline, (ax, ay), (bx, by), 1)


def draw_vertical_gradient(
    surface: pygame.Surface,
    rect: pygame.Rect,
    top_color: Tuple[int, int, int],
    bottom_color: Tuple[int, int, int],
) -> None:
    if rect.height <= 1:
        return
    for i in range(rect.height):
        t = i / (rect.height - 1)
        color = (
            int(top_color[0] + (bottom_color[0] - top_color[0]) * t),
            int(top_color[1] + (bottom_color[1] - top_color[1]) * t),
            int(top_color[2] + (bottom_color[2] - top_color[2]) * t),
        )
        pygame.draw.line(
            surface,
            color,
            (rect.left, rect.top + i),
            (rect.right, rect.top + i),
        )


def draw_cobblestones(surface: pygame.Surface, area: pygame.Rect, seed: int = 7) -> None:
    rng = random.Random(seed)
    y = area.top
    row = 0
    while y < area.bottom:
        x = area.left - 40 + (row % 2) * 18
        while x < area.right + 40:
            width = rng.randint(20, 34)
            height = rng.randint(10, 16)
            points = [
                (x + rng.randint(-2, 2), y + rng.randint(-1, 1)),
                (x + width + rng.randint(-2, 2), y + rng.randint(-1, 1)),
                (x + width + rng.randint(-2, 2), y + height + rng.randint(-1, 1)),
                (x + rng.randint(-2, 2), y + height + rng.randint(-1, 1)),
            ]
            shade = 72 + rng.randint(-8, 8)
            pygame.draw.polygon(surface, (shade, shade, shade + 4), points)
            pygame.draw.polygon(surface, (40, 40, 42), points, 1)
            x += width - rng.randint(2, 5)
        y += rng.randint(11, 15)
        row += 1


def draw_cloud(
    surface: pygame.Surface, pos: Tuple[int, int], size: int, alpha: int
) -> None:
    cloud = pygame.Surface((size * 3, size * 2), pygame.SRCALPHA)
    color = (180, 188, 200, alpha)
    pygame.draw.ellipse(cloud, color, (0, size // 3, size, size // 2))
    pygame.draw.ellipse(cloud, color, (size // 2, 0, size + size // 2, size))
    pygame.draw.ellipse(cloud, color, (size + size // 3, size // 3, size, size // 2))
    surface.blit(cloud, (pos[0] - cloud.get_width() // 2, pos[1] - cloud.get_height() // 2))


def draw_dead_tree(surface: pygame.Surface, x: int, y: int, scale: float = 1.0) -> None:
    rng = random.Random(x * 53 + y * 17)
    s = scale
    trunk_w = max(8, int(14 * s))
    trunk_h = max(50, int(80 * s))
    base_y = y
    top_y = y - trunk_h
    # Shadow on ground
    sh_surf = pygame.Surface((int(80 * s), int(16 * s)), pygame.SRCALPHA)
    pygame.draw.ellipse(sh_surf, (0, 0, 0, 28), sh_surf.get_rect())
    surface.blit(sh_surf, (x - int(40 * s), base_y - int(4 * s)))
    # Gnarled trunk with bark texture — draw tapered
    for row in range(trunk_h):
        t = row / max(1, trunk_h - 1)
        # Trunk tapers from bottom to top
        hw = int(trunk_w * 0.5 * (1.0 - 0.35 * (1.0 - t)))  # wider at base
        wobble = int(math.sin(row * 0.4) * 1.6 * s)
        base_shade = 52 - int(12 * t)
        # Bark grain variation per row
        grain = rng.randint(-6, 6)
        c = (max(0, min(255, base_shade + grain)),
             max(0, min(255, base_shade - 8 + grain)),
             max(0, min(255, base_shade - 14 + grain)))
        ry = base_y - row
        pygame.draw.line(surface, c, (x - hw + wobble, ry), (x + hw + wobble, ry))
    # Trunk cracks / deep fissures
    for _ in range(rng.randint(3, 5)):
        cy = base_y - rng.randint(int(trunk_h * 0.15), int(trunk_h * 0.85))
        ch = rng.randint(int(8 * s), int(18 * s))
        cx_off = rng.randint(-trunk_w // 3, trunk_w // 3)
        for ci in range(ch):
            px = x + cx_off + int(math.sin(ci * 0.6) * 1.2)
            pygame.draw.line(surface, (28, 22, 18), (px, cy + ci), (px, cy + ci))
    # Hollow knothole
    kh_y = base_y - int(trunk_h * (0.3 + rng.random() * 0.3))
    kh_w, kh_h = int(6 * s), int(10 * s)
    pygame.draw.ellipse(surface, (18, 14, 12), (x - kh_w // 2, kh_y - kh_h // 2, kh_w, kh_h))
    pygame.draw.ellipse(surface, (32, 26, 22), (x - kh_w // 2, kh_y - kh_h // 2, kh_w, kh_h), 1)
    # Exposed root system at base
    for ri in range(rng.randint(3, 5)):
        angle = math.pi * 0.6 + ri * math.pi * 0.2 / 4 + rng.uniform(-0.2, 0.2)
        rlen = int((18 + rng.randint(0, 14)) * s)
        end_x = x + int(math.cos(angle) * rlen)
        end_y = base_y + int(math.sin(angle) * rlen * 0.4)
        rc = (54 + rng.randint(-8, 8), 42 + rng.randint(-6, 6), 34 + rng.randint(-4, 4))
        pygame.draw.line(surface, rc, (x + rng.randint(-2, 2), base_y - 2), (end_x, end_y), max(2, int(3 * s)))
        # Sub-root
        if rng.random() > 0.4:
            sub_len = int(rlen * 0.5)
            sub_ang = angle + rng.uniform(-0.4, 0.4)
            sx2 = end_x + int(math.cos(sub_ang) * sub_len)
            sy2 = end_y + int(math.sin(sub_ang) * sub_len * 0.3)
            pygame.draw.line(surface, (48, 38, 30), (end_x, end_y), (sx2, sy2), max(1, int(2 * s)))
    # Main branches — gnarled, multi-segment
    def _dead_branch(start_x, start_y, angle, length, thickness, depth):
        if depth > 4 or length < 3:
            return
        segments = rng.randint(2, 4)
        cx, cy = start_x, start_y
        for si in range(segments):
            seg_len = length / segments
            ang_wobble = angle + rng.uniform(-0.3, 0.3)
            nx = cx + int(math.cos(ang_wobble) * seg_len)
            ny = cy + int(math.sin(ang_wobble) * seg_len)
            bc = (58 + rng.randint(-10, 10), 46 + rng.randint(-8, 8), 38 + rng.randint(-6, 6))
            pygame.draw.line(surface, bc, (int(cx), int(cy)), (nx, ny), max(1, thickness))
            # Bark dots along branch
            if thickness >= 2:
                pygame.draw.circle(surface, (38, 30, 26), (int((cx + nx) // 2), int((cy + ny) // 2)), max(1, thickness // 2))
            cx, cy = nx, ny
        # Broken tip — jagged end
        if depth >= 2 and rng.random() > 0.5:
            for _ in range(2):
                tx = int(cx) + rng.randint(-3, 3)
                ty = int(cy) + rng.randint(-4, 0)
                pygame.draw.line(surface, (46, 36, 30), (int(cx), int(cy)), (tx, ty), 1)
            return
        # Sub-branches
        for _ in range(rng.randint(1, 3)):
            sub_ang = angle + rng.uniform(-0.8, 0.8)
            sub_len = length * rng.uniform(0.4, 0.7)
            _dead_branch(cx, cy, sub_ang, sub_len, max(1, thickness - 1), depth + 1)

    # 4-6 major branches radiating from top of trunk
    for bi in range(rng.randint(4, 6)):
        b_ang = -math.pi / 2 + (bi - 2.5) * 0.45 + rng.uniform(-0.15, 0.15)
        b_len = int((35 + rng.randint(0, 30)) * s)
        b_thick = max(2, int((4 - bi * 0.4) * s))
        b_start_y = top_y + int(rng.randint(0, int(trunk_h * 0.15)))
        _dead_branch(x, b_start_y, b_ang, b_len, b_thick, 0)
    # Moss / lichen patches on trunk
    for _ in range(rng.randint(2, 5)):
        my = base_y - rng.randint(int(trunk_h * 0.1), int(trunk_h * 0.7))
        mx = x + rng.randint(-trunk_w // 2, trunk_w // 2)
        mr = rng.randint(2, max(3, int(5 * s)))
        mc = rng.choice([(56, 78, 42, 90), (62, 82, 48, 80), (48, 68, 38, 70)])
        ms = pygame.Surface((mr * 2, mr * 2), pygame.SRCALPHA)
        pygame.draw.circle(ms, mc, (mr, mr), mr)
        surface.blit(ms, (mx - mr, my - mr))
    # Shelf fungus
    if rng.random() > 0.4:
        fy = base_y - rng.randint(int(trunk_h * 0.2), int(trunk_h * 0.5))
        side = rng.choice([-1, 1])
        fw, fh = int(8 * s), int(4 * s)
        fx = x + side * trunk_w // 2
        pygame.draw.ellipse(surface, (92, 78, 58), (fx, fy, fw * side, fh))
        pygame.draw.ellipse(surface, (72, 60, 42), (fx, fy, fw * side, fh), 1)
        pygame.draw.ellipse(surface, (108, 94, 72), (fx + side, fy + 1, max(1, (fw - 2) * side), max(1, fh - 2)))



def draw_pine_tree(surface: pygame.Surface, x: int, y: int, scale: float = 1.0) -> pygame.Rect:
    rng = random.Random(x * 41 + y * 13)
    s = scale
    trunk_w = max(8, int(16 * s))
    trunk_h = max(24, int(32 * s))
    crown_h = max(60, int(110 * s))
    crown_w = max(48, int(90 * s))
    base_y = y
    # Ground shadow
    sh_w, sh_h = int(crown_w * 0.7), max(10, int(16 * s))
    sh_surf = pygame.Surface((sh_w, sh_h), pygame.SRCALPHA)
    pygame.draw.ellipse(sh_surf, (0, 0, 0, 32), sh_surf.get_rect())
    surface.blit(sh_surf, (x - sh_w // 2, base_y - sh_h // 2))
    # Visible roots
    for ri in range(rng.randint(2, 4)):
        ang = math.pi * 0.55 + ri * 0.3 + rng.uniform(-0.15, 0.15)
        rlen = int((10 + rng.randint(0, 8)) * s)
        rx = x + int(math.cos(ang) * rlen)
        ry = base_y + int(math.sin(ang) * rlen * 0.35)
        pygame.draw.line(surface, (62 + rng.randint(-6, 6), 46 + rng.randint(-4, 4), 32), (x, base_y - 2), (rx, ry), max(2, int(3 * s)))
    # Trunk with bark texture
    for row in range(trunk_h):
        t = row / max(1, trunk_h - 1)
        hw = int(trunk_w * 0.5 * (1.0 - 0.25 * (1.0 - t)))
        base_c = 64 - int(10 * t)
        grain = rng.randint(-5, 5)
        c = (max(0, base_c + grain), max(0, base_c - 12 + grain), max(0, base_c - 20 + grain))
        pygame.draw.line(surface, c, (x - hw, base_y - row), (x + hw, base_y - row))
    # Bark detail lines
    for _ in range(rng.randint(3, 6)):
        by = base_y - rng.randint(2, trunk_h - 2)
        blen = rng.randint(int(3 * s), int(8 * s))
        pygame.draw.line(surface, (38, 28, 20), (x - trunk_w // 4, by), (x - trunk_w // 4, by + blen), 1)
    # Crown layers — 6 overlapping tiers with depth
    top_y = base_y - trunk_h - crown_h
    layers = 6
    for i in range(layers):
        t = i / max(1, layers - 1)
        layer_w = int(crown_w * (0.28 + 0.72 * (i + 1) / layers))
        layer_h = int(crown_h * (0.16 + 0.06 * i))
        cy = int(top_y + crown_h * (0.12 + t * 0.72))
        # Back dark layer
        pts_back = [(x, cy - layer_h - int(4 * s)),
                     (x - layer_w // 2 - int(3 * s), cy + layer_h // 2 + int(2 * s)),
                     (x + layer_w // 2 + int(3 * s), cy + layer_h // 2 + int(2 * s))]
        pygame.draw.polygon(surface, (18, 48, 22), pts_back)
        # Main foliage triangle
        pts = [(x + rng.randint(-2, 2), cy - layer_h),
               (x - layer_w // 2, cy + layer_h // 2),
               (x + layer_w // 2, cy + layer_h // 2)]
        base_g = 28 + i * 8
        gc = (base_g + rng.randint(-4, 4), base_g + 40 + rng.randint(-6, 6), base_g + 6 + rng.randint(-3, 3))
        pygame.draw.polygon(surface, gc, pts)
        # Inner highlight — lighter patch on sunny side
        inner_w = int(layer_w * 0.55)
        inner_h = int(layer_h * 0.65)
        inner = [(x - int(2 * s), cy - inner_h),
                 (x - inner_w // 2 - int(2 * s), cy + int(inner_h * 0.3)),
                 (x + int(inner_w * 0.3), cy + int(inner_h * 0.2))]
        hc = (gc[0] + 14, min(255, gc[1] + 18), gc[2] + 10)
        pygame.draw.polygon(surface, hc, inner)
        # Needle cluster bumps along edges
        bump_count = rng.randint(4, 8)
        for bi in range(bump_count):
            bt = bi / max(1, bump_count - 1)
            side = rng.choice([-1, 1])
            bx = int(x + side * layer_w * 0.5 * bt)
            by = int(cy - layer_h * (1.0 - bt) + layer_h // 2 * bt)
            br = rng.randint(max(2, int(3 * s)), max(3, int(7 * s)))
            bc = (gc[0] + rng.randint(-8, 8), gc[1] + rng.randint(-10, 10), gc[2] + rng.randint(-4, 4))
            pygame.draw.circle(surface, bc, (bx, by), br)
        # Edge outline
        pygame.draw.polygon(surface, (14, 26, 16), pts, 1)
        # Snow / frost on top edges (subtle white highlights)
        if i < layers - 1:
            mid_x = (pts[0][0] + pts[1][0]) // 2
            mid_y = (pts[0][1] + pts[1][1]) // 2
            pygame.draw.line(surface, (gc[0] + 28, min(255, gc[1] + 30), gc[2] + 24),
                             (int(mid_x), int(mid_y)),
                             (pts[0][0], pts[0][1]), 1)
    # Individual needle clusters scattered on surface
    for _ in range(rng.randint(12, 20)):
        nx = x + rng.randint(-crown_w // 2 + 4, crown_w // 2 - 4)
        ny_min = top_y + int(crown_h * 0.15)
        ny_max = base_y - trunk_h - int(4 * s)
        if ny_max <= ny_min:
            continue
        ny = rng.randint(ny_min, ny_max)
        nc = (34 + rng.randint(0, 18), 68 + rng.randint(0, 24), 30 + rng.randint(0, 12))
        # Small cluster of 3-5 tiny lines radiating out
        for _ in range(rng.randint(3, 5)):
            na = rng.uniform(0, math.tau)
            nl = rng.randint(2, max(3, int(5 * s)))
            pygame.draw.line(surface, nc, (nx, ny),
                             (nx + int(math.cos(na) * nl), ny + int(math.sin(na) * nl)), 1)
    # Pinecones hanging from lower layers
    for _ in range(rng.randint(1, 3)):
        px = x + rng.randint(-crown_w // 3, crown_w // 3)
        py = base_y - trunk_h - rng.randint(int(6 * s), int(20 * s))
        pw, ph = max(3, int(4 * s)), max(5, int(8 * s))
        pygame.draw.ellipse(surface, (86, 62, 38), (px - pw // 2, py, pw, ph))
        pygame.draw.ellipse(surface, (68, 48, 28), (px - pw // 2, py, pw, ph), 1)
        # Cross-hatch pattern on pinecone
        for ci in range(1, ph - 1, 2):
            pygame.draw.line(surface, (72, 52, 32), (px - pw // 3, py + ci), (px + pw // 3, py + ci), 1)
    # Tree top — pointed tip with slight asymmetry
    tip_x = x + rng.randint(-2, 2)
    tip_y = top_y + int(crown_h * 0.05)
    pygame.draw.line(surface, (22, 56, 26), (tip_x, tip_y), (tip_x, tip_y - int(6 * s)), max(1, int(2 * s)))
    return pygame.Rect(x - int(crown_w * 0.18), base_y - int(18 * s), int(crown_w * 0.36), int(20 * s))


def draw_boulder(surface: pygame.Surface, x: int, y: int, scale: float = 1.0) -> pygame.Rect:
    w = max(24, int(54 * scale))
    h = max(16, int(34 * scale))
    rect = pygame.Rect(x - w // 2, y - h, w, h)
    pts = [
        (rect.left + 3, rect.bottom - 2),
        (rect.left + w * 0.18, rect.top + h * 0.28),
        (rect.left + w * 0.46, rect.top + 1),
        (rect.left + w * 0.78, rect.top + h * 0.18),
        (rect.right - 2, rect.top + h * 0.54),
        (rect.right - 6, rect.bottom - 2),
        (rect.left + w * 0.58, rect.bottom - 1),
        (rect.left + w * 0.26, rect.bottom - 1),
    ]
    pts = [(int(px), int(py)) for px, py in pts]
    pygame.draw.polygon(surface, (82, 86, 92), pts)
    pygame.draw.polygon(surface, (44, 46, 52), pts, 2)
    hi = [
        (int(rect.left + w*0.2), int(rect.top + h*0.45)),
        (int(rect.left + w*0.42), int(rect.top + h*0.18)),
        (int(rect.left + w*0.62), int(rect.top + h*0.34)),
    ]
    pygame.draw.lines(surface, (112, 116, 122), False, hi, 2)
    return rect.inflate(-int(w * 0.22), -int(h * 0.28))


def draw_spell_anim(surface: pygame.Surface, effect: dict, pos: Tuple[int, int], t: float, loop: bool = False) -> None:
    x, y = int(pos[0]), int(pos[1])
    kind = str(effect.get('type', effect.get('kind', 'spell')))
    if loop:
        t = t % 1.0
    alpha = max(30, min(220, int(220 * (1.0 - min(1.0, t)))))
    glow = pygame.Surface((120, 120), pygame.SRCALPHA)
    cx, cy = 60, 60
    if 'heal' in kind:
        pygame.draw.circle(glow, (90, 230, 130, alpha // 2), (cx, cy), 20 + int(10 * t), 3)
        pygame.draw.circle(glow, (120, 255, 160, alpha // 3), (cx, cy), 34 + int(14 * t), 2)
        for i in range(5):
            ang = (i / 5.0) * math.tau + t * 4
            px = int(cx + math.cos(ang) * (16 + 10 * t))
            py = int(cy + math.sin(ang) * (16 + 10 * t))
            pygame.draw.circle(glow, (180, 255, 200, alpha), (px, py), 2)
    elif 'fire' in kind:
        for r, a in [(14 + int(18 * t), alpha), (28 + int(14 * t), alpha // 2)]:
            pygame.draw.circle(glow, (255, 150, 50, a), (cx, cy), r)
        pygame.draw.circle(glow, (255, 230, 120, alpha), (cx, cy), max(4, 10 - int(4 * t)))
    else:
        pygame.draw.circle(glow, (90, 170, 255, alpha // 2), (cx, cy), 18 + int(18 * t), 3)
        for i in range(6):
            ang = (i / 6.0) * math.tau + t * 6
            px = int(cx + math.cos(ang) * (14 + 18 * t))
            py = int(cy + math.sin(ang) * (14 + 18 * t))
            pygame.draw.circle(glow, (150, 210, 255, alpha), (px, py), 2)
    surface.blit(glow, (x - cx, y - cy))

def draw_lamppost(surface: pygame.Surface, x: int, y: int, lit: bool = True) -> None:
    """Ornate wrought-iron lamppost with decorative scrollwork and glass lantern."""
    iron = (38, 40, 46)
    iron_h = (52, 54, 60)
    iron_d = (26, 28, 32)

    # ── Ground base — ornate octagonal stone plinth ──
    # Shadow
    pygame.draw.ellipse(surface, (14, 14, 16), (x - 22, y - 4, 44, 14))
    # Stone base (stepped)
    pygame.draw.rect(surface, (72, 70, 66), (x - 14, y - 10, 28, 10))
    pygame.draw.rect(surface, (54, 52, 48), (x - 14, y - 10, 28, 10), 1)
    pygame.draw.rect(surface, (66, 64, 60), (x - 10, y - 16, 20, 8))
    pygame.draw.rect(surface, (48, 46, 42), (x - 10, y - 16, 20, 8), 1)

    # ── Main pole — tapered iron shaft with decorative elements ──
    pole_h = 90
    pole_top = y - 16 - pole_h
    # Pole body (slightly tapered — 5px at base, 4px at top)
    for row in range(pole_h):
        t = row / float(pole_h)
        pw = int(5 - t * 1.5)
        shade = int(38 + 8 * t)
        pygame.draw.line(surface, (shade, shade + 2, shade + 6),
                         (x - pw, y - 16 - row), (x + pw, y - 16 - row))
    # Decorative ring bands (3 along the pole)
    for ring_y in [y - 30, y - 55, y - 80]:
        pygame.draw.rect(surface, iron_h, (x - 6, ring_y - 2, 12, 4))
        pygame.draw.rect(surface, iron_d, (x - 6, ring_y - 2, 12, 4), 1)
    # Scrollwork bracket at mid-height
    _sw_y = y - 50
    for side in [-1, 1]:
        # S-curve scroll
        pts = []
        for si in range(8):
            st = si / 7.0
            sx2 = x + side * int(4 + 10 * math.sin(st * math.pi))
            sy2 = _sw_y - int(st * 16)
            pts.append((sx2, sy2))
        if len(pts) >= 2:
            pygame.draw.lines(surface, iron_h, False, pts, 2)
            # Scroll terminal (small circle)
            pygame.draw.circle(surface, iron_h, pts[-1], 2)

    # ── Lantern housing — four-sided glass lantern with iron frame ──
    lan_w, lan_h2 = 14, 20
    lan_y = pole_top - 4
    # Iron frame (4 corner posts + top cap + bottom ring)
    pygame.draw.rect(surface, iron, (x - lan_w // 2, lan_y - lan_h2, lan_w, lan_h2))
    # Glass panels (warm amber when lit, dark when not)
    if lit:
        glass_col = (200, 160, 80)
    else:
        glass_col = (30, 30, 34)
    pygame.draw.rect(surface, glass_col, (x - lan_w // 2 + 2, lan_y - lan_h2 + 2, lan_w - 4, lan_h2 - 4))
    # Frame lines
    pygame.draw.rect(surface, iron_d, (x - lan_w // 2, lan_y - lan_h2, lan_w, lan_h2), 1)
    # Vertical frame bars
    pygame.draw.line(surface, iron, (x, lan_y - lan_h2), (x, lan_y), 1)
    # Horizontal midbar
    pygame.draw.line(surface, iron, (x - lan_w // 2, lan_y - lan_h2 // 2),
                     (x + lan_w // 2, lan_y - lan_h2 // 2), 1)
    # Top cap — decorative pointed finial
    cap_y = lan_y - lan_h2
    pygame.draw.rect(surface, iron, (x - lan_w // 2 - 2, cap_y - 2, lan_w + 4, 4))
    pygame.draw.rect(surface, iron_d, (x - lan_w // 2 - 2, cap_y - 2, lan_w + 4, 4), 1)
    # Spire
    pygame.draw.polygon(surface, iron_h, [(x - 3, cap_y - 2), (x + 3, cap_y - 2), (x, cap_y - 12)])
    pygame.draw.polygon(surface, iron_d, [(x - 3, cap_y - 2), (x + 3, cap_y - 2), (x, cap_y - 12)], 1)
    # Finial ball
    pygame.draw.circle(surface, iron_h, (x, cap_y - 13), 3)
    pygame.draw.circle(surface, iron_d, (x, cap_y - 13), 3, 1)
    # Bottom ring
    pygame.draw.rect(surface, iron, (x - lan_w // 2 - 1, lan_y - 1, lan_w + 2, 3))

    # ── Crossbar arms (two small decorative arms extending from pole below lantern) ──
    arm_y = lan_y + 4
    for side in [-1, 1]:
        ax1, ax2 = x, x + side * 12
        pygame.draw.line(surface, iron, (ax1, arm_y), (ax2, arm_y - 6), 2)
        pygame.draw.circle(surface, iron_h, (ax2, arm_y - 6), 2)

    # ── Light glow (when lit) ──
    if lit:
        glow = pygame.Surface((160, 160), pygame.SRCALPHA)
        pygame.draw.circle(glow, (255, 196, 92, 55), (80, 80), 40)
        pygame.draw.circle(glow, (255, 210, 110, 28), (80, 80), 64)
        pygame.draw.circle(glow, (255, 220, 130, 12), (80, 80), 78)
        surface.blit(glow, (x - 80, lan_y - lan_h2 // 2 - 80))


def draw_market_stall(surface: pygame.Surface, x: int, y: int, scale: float = 1.0) -> pygame.Rect:
    table_w = int(92 * scale)
    table_h = int(20 * scale)
    post_h = int(62 * scale)
    awning_h = int(22 * scale)

    shadow = pygame.Rect(x - table_w // 2 - 10, y - 2, table_w + 20, 14)
    pygame.draw.ellipse(surface, (16, 16, 18), shadow)

    table = pygame.Rect(x - table_w // 2, y - table_h, table_w, table_h)
    pygame.draw.rect(surface, (78, 58, 42), table)
    pygame.draw.rect(surface, (34, 24, 18), table, 2)

    left_post = pygame.Rect(table.left + 6, table.top - post_h, 8, post_h)
    right_post = pygame.Rect(table.right - 14, table.top - post_h, 8, post_h)
    pygame.draw.rect(surface, (82, 62, 44), left_post)
    pygame.draw.rect(surface, (82, 62, 44), right_post)
    pygame.draw.rect(surface, (30, 22, 16), left_post, 1)
    pygame.draw.rect(surface, (30, 22, 16), right_post, 1)

    awning = pygame.Rect(table.left - 8, table.top - post_h - awning_h, table.width + 16, awning_h)
    pygame.draw.rect(surface, (116, 22, 20), awning)
    stripe_w = max(8, awning.width // 7)
    for i in range(0, awning.width, stripe_w * 2):
        stripe = pygame.Rect(awning.left + i, awning.top, stripe_w, awning.height)
        pygame.draw.rect(surface, (224, 192, 104), stripe)
    pygame.draw.rect(surface, (32, 12, 12), awning, 2)

    for i in range(4):
        crate = pygame.Rect(table.left + 10 + i * int(18 * scale), table.top + 4, int(14 * scale), int(10 * scale))
        pygame.draw.rect(surface, (96, 70, 48), crate)
        pygame.draw.rect(surface, (42, 30, 20), crate, 1)

    return table


def _house_hash(v: int, s: int = 0) -> int:
    return ((v * 2654435761 + s) >> 4) & 0xFFFF


def _draw_wall_weathering(surface: pygame.Surface, rect: pygame.Rect, seed: int, intensity: float = 0.5) -> None:
    """Add subtle stains, damp patches, and moss to a wall area."""
    ws = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    # Damp stains
    for i in range(3 + seed % 3):
        dx = _house_hash(i * 37, seed) % max(1, rect.width - 8)
        dy = _house_hash(i * 53, seed) % max(1, rect.height - 6)
        dw = 6 + _house_hash(i * 19, seed) % 12
        dh = 4 + _house_hash(i * 29, seed) % 10
        a = int(20 * intensity)
        pygame.draw.ellipse(ws, (30, 28, 24, a), (dx, dy, dw, dh))
    # Moss/lichen at base
    moss_h = max(4, int(rect.height * 0.12 * intensity))
    for mx in range(0, rect.width, 4):
        mh = moss_h - _house_hash(mx * 7 + seed, seed) % max(1, moss_h)
        a = int(40 * intensity)
        pygame.draw.rect(ws, (48, 72, 36, a), (mx, rect.height - mh, 4, mh))
    surface.blit(ws, rect.topleft)


def _draw_house_lantern(surface: pygame.Surface, lx: int, ly: int, s: float) -> None:
    """Draw a small wall-mounted iron lantern with warm glow."""
    size = max(4, int(8 * s))
    # Bracket
    pygame.draw.line(surface, (48, 42, 36), (lx, ly), (lx + int(10 * s), ly), 2)
    # Lantern body
    lr = pygame.Rect(lx + int(8 * s), ly - size // 2, size, size + 2)
    pygame.draw.rect(surface, (52, 46, 38), lr, border_radius=1)
    # Glass (lit)
    inner = lr.inflate(-4, -4)
    pygame.draw.rect(surface, (240, 200, 110), inner)
    pygame.draw.rect(surface, (42, 36, 28), lr, 1, border_radius=1)
    # Glow
    gs = pygame.Surface((size * 5, size * 5), pygame.SRCALPHA)
    pygame.draw.ellipse(gs, (255, 200, 100, 22), gs.get_rect())
    surface.blit(gs, (lr.centerx - size * 5 // 2, lr.centery - size * 5 // 2))
    # Cap
    pygame.draw.polygon(surface, (48, 42, 36),
                        [(lr.left - 1, lr.top), (lr.right + 1, lr.top), (lr.centerx, lr.top - max(3, int(5 * s)))])


def _draw_house_extras(surface: pygame.Surface, x: int, y: int, w: int, h: int, s: float, seed: int) -> None:
    """Stamp unique medieval decorative details onto a house based on seed."""
    _hh = _house_hash
    rng = random.Random(seed * 31 + 7)
    detail_set = seed % 8  # 8 distinct decoration combos

    # ── Ivy / climbing vines on walls (30% chance) ──
    if detail_set in (0, 3, 5):
        vine_side = -1 if seed % 2 else 1
        vx = x + vine_side * (w // 2 - int(8 * s))
        for vi in range(int(h * 0.6 / (6 * s))):
            vy = y - int(vi * 6 * s) - int(10 * s)
            sway = int(3 * math.sin(vi * 0.8 + seed))
            gc = (28 + rng.randint(0, 24), 52 + rng.randint(0, 30), 18 + rng.randint(0, 14))
            pygame.draw.circle(surface, gc, (vx + sway, vy), max(2, int(3 * s)))
            if vi > 0:
                pygame.draw.line(surface, (22, 40, 14), (vx + sway, vy), (vx + int(3 * math.sin((vi - 1) * 0.8 + seed)), vy + int(6 * s)), 1)

    # ── Hanging trade sign (merchants / workshops, 25% chance) ──
    if detail_set in (1, 4, 7):
        sign_side = 1 if seed % 3 else -1
        sx = x + sign_side * (w // 2 + int(4 * s))
        sy = y - int(h * 0.5)
        # Iron bracket
        pygame.draw.line(surface, (50, 48, 44), (x + sign_side * (w // 2 - 2), sy), (sx + sign_side * int(12 * s), sy), 2)
        # Sign board
        sb_w, sb_h = int(20 * s), int(14 * s)
        sb_x = sx + sign_side * int(12 * s) - sb_w // 2
        pygame.draw.rect(surface, (56, 40, 24), (sb_x, sy + 2, sb_w, sb_h), border_radius=2)
        pygame.draw.rect(surface, (90, 72, 48), (sb_x, sy + 2, sb_w, sb_h), 1, border_radius=2)
        # Symbol on sign (varies)
        sym = seed % 5
        sc_x, sc_y = sb_x + sb_w // 2, sy + 2 + sb_h // 2
        if sym == 0:  # hammer (smith)
            pygame.draw.line(surface, (160, 150, 130), (sc_x - 3, sc_y + 3), (sc_x + 3, sc_y - 3), 2)
            pygame.draw.rect(surface, (140, 130, 110), (sc_x + 1, sc_y - 5, 4, 3))
        elif sym == 1:  # bottle (alch)
            pygame.draw.rect(surface, (100, 140, 100), (sc_x - 2, sc_y - 2, 4, 6))
            pygame.draw.rect(surface, (80, 120, 80), (sc_x - 1, sc_y - 4, 2, 3))
        elif sym == 2:  # bread (baker)
            pygame.draw.ellipse(surface, (180, 150, 80), (sc_x - 4, sc_y - 2, 8, 5))
        elif sym == 3:  # scissors (tailor)
            pygame.draw.line(surface, (150, 150, 160), (sc_x - 3, sc_y - 3), (sc_x + 3, sc_y + 2), 1)
            pygame.draw.line(surface, (150, 150, 160), (sc_x + 3, sc_y - 3), (sc_x - 3, sc_y + 2), 1)
        else:  # tankard (tavern)
            pygame.draw.rect(surface, (140, 120, 80), (sc_x - 2, sc_y - 3, 5, 6))
            pygame.draw.arc(surface, (120, 100, 60), (sc_x + 2, sc_y - 2, 4, 4), -1.5, 1.5, 1)

    # ── Window shutters (painted wood, 35% chance) ──
    if detail_set in (2, 5, 6):
        shutter_cols = [(68, 82, 54), (82, 46, 36), (46, 58, 78), (78, 64, 44)]
        sc2 = shutter_cols[seed % 4]
        # Draw shutters beside the main windows (approximate positions)
        for wi in range(2):
            wx = x - w // 4 + wi * (w // 2)
            wy = y - int(h * 0.65)
            sw2, sh2 = int(5 * s), int(16 * s)
            # Left shutter
            pygame.draw.rect(surface, sc2, (wx - int(10 * s), wy, sw2, sh2))
            pygame.draw.rect(surface, (sc2[0] - 16, sc2[1] - 14, sc2[2] - 12), (wx - int(10 * s), wy, sw2, sh2), 1)
            # Hinge dots
            pygame.draw.circle(surface, (40, 38, 34), (wx - int(10 * s) + 2, wy + 3), 1)
            pygame.draw.circle(surface, (40, 38, 34), (wx - int(10 * s) + 2, wy + sh2 - 3), 1)
            # Right shutter
            pygame.draw.rect(surface, sc2, (wx + int(5 * s), wy, sw2, sh2))
            pygame.draw.rect(surface, (sc2[0] - 16, sc2[1] - 14, sc2[2] - 12), (wx + int(5 * s), wy, sw2, sh2), 1)

    # ── Coat of arms / shield on wall (noble houses, 20% chance) ──
    if detail_set in (0, 7):
        coa_y = y - int(h * 0.45)
        coa_sz = max(6, int(10 * s))
        # Shield shape
        pts = [(x - coa_sz, coa_y - coa_sz), (x + coa_sz, coa_y - coa_sz),
               (x + coa_sz, coa_y + coa_sz // 2), (x, coa_y + coa_sz),
               (x - coa_sz, coa_y + coa_sz // 2)]
        shield_cols = [(120, 28, 28), (28, 48, 120), (120, 100, 28), (28, 100, 48)]
        pygame.draw.polygon(surface, shield_cols[seed % 4], pts)
        pygame.draw.polygon(surface, (180, 170, 140), pts, 1)
        # Cross or stripe
        if seed % 3 == 0:
            pygame.draw.line(surface, (180, 170, 140), (x, coa_y - coa_sz), (x, coa_y + coa_sz), 1)
            pygame.draw.line(surface, (180, 170, 140), (x - coa_sz, coa_y), (x + coa_sz, coa_y), 1)
        else:
            pygame.draw.line(surface, (180, 170, 140), (x - coa_sz, coa_y - coa_sz + 2),
                             (x + coa_sz, coa_y - coa_sz + 2), 2)

    # ── Doorstep items: barrel, sack, or crate (40% chance) ──
    if detail_set in (1, 2, 3, 6):
        item_side = -1 if (seed // 2) % 2 else 1
        ix = x + item_side * (w // 2 - int(6 * s))
        iy = y - int(4 * s)
        item = seed % 4
        if item == 0:  # small barrel
            pygame.draw.ellipse(surface, (72, 56, 34), (ix - int(6 * s), iy - int(12 * s), int(12 * s), int(12 * s)))
            pygame.draw.ellipse(surface, (52, 40, 22), (ix - int(6 * s), iy - int(12 * s), int(12 * s), int(12 * s)), 1)
            pygame.draw.line(surface, (62, 58, 50), (ix - int(6 * s), iy - int(6 * s)), (ix + int(6 * s), iy - int(6 * s)), 1)
        elif item == 1:  # sack
            pygame.draw.ellipse(surface, (128, 116, 80), (ix - int(5 * s), iy - int(10 * s), int(10 * s), int(10 * s)))
            pygame.draw.line(surface, (100, 90, 60), (ix, iy - int(10 * s)), (ix, iy - int(12 * s)), 1)
        elif item == 2:  # wooden crate
            cr = int(8 * s)
            pygame.draw.rect(surface, (82, 66, 40), (ix - cr, iy - cr * 2, cr * 2, cr * 2))
            pygame.draw.rect(surface, (56, 44, 26), (ix - cr, iy - cr * 2, cr * 2, cr * 2), 1)
            pygame.draw.line(surface, (56, 44, 26), (ix - cr, iy - cr), (ix + cr, iy - cr), 1)
        else:  # potted plant
            pot_w = int(8 * s)
            pygame.draw.rect(surface, (140, 70, 40), (ix - pot_w // 2, iy - int(8 * s), pot_w, int(8 * s)))
            for _ in range(3):
                lx = ix + rng.randint(-3, 3)
                pygame.draw.line(surface, (36 + rng.randint(0, 20), 60 + rng.randint(0, 24), 20),
                                 (lx, iy - int(8 * s)), (lx + rng.randint(-4, 4), iy - int(16 * s)), 1)


def _draw_house_variations(surface: pygame.Surface, x: int, y: int, s: float, seed: int,
                           district: str, style_idx: int, fnd: pygame.Rect) -> pygame.Rect:
    """Phase-3 uniqueness layer: structural add-ons stamped over a finished
    district house so no two houses read alike — lean-to annexes (L-shaped
    footprints), roof dormers, window flower boxes, laundry lines, gable
    hoists, stacked woodpiles and ridge pennants/crows. All seed-driven and
    gated by district so each quarter keeps its character.

    Returns the collision rect (widened when an annex extends the footprint).
    Lateral extensions are capped at ~36px beyond the facade so they always
    fit inside the house overlay surface padding.
    """
    rng = random.Random(seed * 1303 + style_idx * 17)
    # per-style facade geometry: (facade_w, eave_offset, roof_h, roof_overhang) in units of s
    _geo = {
        0: (128, 128, 78, 12),   # tudor
        1: (90, 134, 70, 8),     # stone townhouse
        2: (120, 72, 68, 18),    # thatched cottage
        3: (156, 138, 74, 14),   # merchant
        4: (72, 108, 56, 6),     # rowhouse
        5: (126, 126, 66, 10),   # workshop
    }
    fw_f, eave_f, roof_f, rov_f = _geo[style_idx]
    fw = int(fw_f * s)
    eave_y = y - int(eave_f * s)
    roof_h = int(roof_f * s)
    rov = int(rov_f * s)
    rustic = district in ("shanty", "harbor", "ember", "rook", "artisan")
    posh = district in ("noble", "saint")
    out_fnd = pygame.Rect(fnd)
    annex_side = 0

    # ── lean-to annex: mono-pitch shed against one side wall ──
    if style_idx in (0, 2, 3, 5) and rng.random() < 0.30 or (style_idx == 1 and rng.random() < 0.14):
        annex_side = -1 if rng.random() < 0.5 else 1
        aw = max(22, min(36, int(30 * s)))
        ah = max(20, int(eave_f * s * 0.40))
        rise = max(8, int(13 * s))
        wall_x = x + annex_side * (fw // 2)
        outer_x = wall_x + annex_side * aw
        base_y = y - 2
        # contact shadow
        ash = pygame.Surface((aw + 14, 12), pygame.SRCALPHA)
        pygame.draw.ellipse(ash, (10, 8, 6, 64), (0, 0, aw + 14, 12))
        surface.blit(ash, (min(wall_x, outer_x) - 4, base_y - 5))
        # plank wall, per-column tone
        for ci in range(aw):
            px2 = wall_x + annex_side * ci
            tone = 96 + _house_hash(px2 * 7 + seed, 19) % 18 - (14 if annex_side > 0 else 0)
            pygame.draw.line(surface, (tone, int(tone * 0.78), int(tone * 0.52)),
                             (px2, base_y - ah), (px2, base_y))
        for gx2 in range(3, aw - 2, 6):                              # board seams
            px2 = wall_x + annex_side * gx2
            pygame.draw.line(surface, (52, 39, 24), (px2, base_y - ah + 1), (px2, base_y - 1), 1)
        pygame.draw.rect(surface, (44, 33, 20),
                         (min(wall_x, outer_x), base_y - ah, aw, ah), 1)
        # small window or stacked log-store in the gable
        if rng.random() < 0.45:
            wx2 = (wall_x + outer_x) // 2
            pygame.draw.rect(surface, (26, 19, 12), (wx2 - 4, base_y - ah + 5, 8, 9))
            pygame.draw.rect(surface, (60, 46, 28), (wx2 - 5, base_y - ah + 4, 10, 11), 1)
        else:
            for li in range(3):
                for lj in range(3 - (li % 2)):
                    lx2 = min(wall_x, outer_x) + 6 + lj * 7 + (li % 2) * 3
                    pygame.draw.circle(surface, (108, 84, 54), (lx2, base_y - 5 - li * 6), 3)
                    pygame.draw.circle(surface, (58, 42, 26), (lx2, base_y - 5 - li * 6), 3, 1)
                    pygame.draw.circle(surface, (76, 58, 36), (lx2, base_y - 5 - li * 6), 1)
        # mono-pitch roof sloping away from the house wall
        iy = base_y - ah - rise
        oy = base_y - ah - max(3, int(4 * s))
        rt = max(4, int(6 * s))
        rpts2 = [(wall_x, iy), (outer_x + annex_side * 3, oy),
                 (outer_x + annex_side * 3, oy + rt), (wall_x, iy + rt)]
        pygame.draw.polygon(surface, (94, 74, 48), rpts2)
        pygame.draw.line(surface, (124, 100, 66), (wall_x, iy), (outer_x + annex_side * 3, oy), 2)
        for pi in range(1, 4):                                       # roof plank courses
            t = pi / 4
            pygame.draw.line(surface, (66, 51, 32),
                             (wall_x, iy + int(rt * t)), (outer_x + annex_side * 3, oy + int(rt * t)), 1)
        pygame.draw.polygon(surface, (40, 30, 18), rpts2, 1)
        # widen the collision footprint to cover the annex
        if annex_side < 0:
            out_fnd.x -= aw
        out_fnd.w += aw

    # ── roof dormer(s) on plain gable roofs ──
    if style_idx in (0, 1, 4) and rng.random() < 0.42:
        u = 0.42                       # mid-roof, clear of the eave line
        dh2 = max(12, int(15 * s))
        dw2 = max(14, int(18 * s))
        droof = max(7, int(11 * s))
        base_half = fw // 2 + rov
        top_frac = u + (dh2 + droof + 2) / max(1, roof_h)
        avail = int(base_half * max(0.0, 1.0 - top_frac)) - dw2 // 2 - 2
        if avail > 4:
            n_d = 1 if (style_idx == 4 or avail < dw2) else rng.choice((1, 2))
            offs = [rng.uniform(-0.7, 0.7)] if n_d == 1 else [-0.9, 0.9]
            dy2 = eave_y - int(roof_h * u) - dh2
            for od in offs:
                dx2 = x + int(od * avail)
                # gable face + window (lit 3 times out of 4 — pops on dark roofs)
                pygame.draw.rect(surface, (204, 196, 178), (dx2 - dw2 // 2, dy2, dw2, dh2))
                lit_d = (seed + int(od * 10)) % 4 != 1
                pygame.draw.rect(surface, (228, 182, 102) if lit_d else (42, 48, 60),
                                 (dx2 - dw2 // 2 + 2, dy2 + 2, dw2 - 4, dh2 - 4))
                if lit_d:
                    pygame.draw.rect(surface, (252, 226, 156),
                                     (dx2 - dw2 // 2 + 3, dy2 + 3, max(2, dw2 // 3), max(2, dh2 // 3)))
                pygame.draw.line(surface, (54, 42, 28), (dx2, dy2 + 2), (dx2, dy2 + dh2 - 2), 1)
                pygame.draw.line(surface, (54, 42, 28), (dx2 - dw2 // 2 + 2, dy2 + dh2 // 2),
                                 (dx2 + dw2 // 2 - 2, dy2 + dh2 // 2), 1)
                pygame.draw.rect(surface, (40, 33, 26), (dx2 - dw2 // 2, dy2, dw2, dh2), 2)
                # little gable roof with a sun-caught left slope
                dpts = [(dx2 - dw2 // 2 - 4, dy2 + 1), (dx2 + dw2 // 2 + 4, dy2 + 1), (dx2, dy2 - droof)]
                pygame.draw.polygon(surface, (64, 56, 48), dpts)
                pygame.draw.polygon(surface, (98, 88, 78),
                                    [(dx2 - dw2 // 2 - 4, dy2 + 1), (dx2, dy2 - droof), (dx2 + 3, dy2 - droof + 4),
                                     (dx2 - dw2 // 2 + 2, dy2)])
                pygame.draw.polygon(surface, (26, 22, 18), dpts, 2)

    # ── window flower boxes under the upper-floor windows ──
    if style_idx in (0, 1, 4, 5) and (posh or rng.random() < 0.18) and rng.random() < 0.55:
        sill_off = {0: 40, 1: 38, 4: 32, 5: 38}[style_idx]
        sill_y = eave_y + int(sill_off * s)
        bw2 = max(14, int(20 * s))
        for wxf in (-0.25, 0.25):
            bx2 = x + int(fw * wxf)
            pygame.draw.rect(surface, (74, 52, 30), (bx2 - bw2 // 2, sill_y, bw2, max(4, int(5 * s))), border_radius=1)
            pygame.draw.rect(surface, (46, 32, 18), (bx2 - bw2 // 2, sill_y, bw2, max(4, int(5 * s))), 1, border_radius=1)
            frng = random.Random(seed * 7 + int(wxf * 100))
            for fi in range(4):
                fx2 = bx2 - bw2 // 2 + 2 + fi * (bw2 - 4) // 3
                pygame.draw.circle(surface, (52, 84, 40), (fx2, sill_y - 1), 2)
                pygame.draw.circle(surface, frng.choice([(196, 74, 70), (224, 188, 76), (188, 96, 160), (226, 222, 210)]),
                                   (fx2, sill_y - 3), 2)

    # ── laundry line to a yard pole ──
    if rustic and rng.random() < 0.24:
        l_side = -annex_side if annex_side else (-1 if rng.random() < 0.5 else 1)
        ax2 = x + l_side * (fw // 2 - 2)
        # anchor at head height on the wall (NOT the eave — tall houses made
        # the line read as a zip-line), pole slightly lower so the line sags
        ay2 = y - max(30, min(int(46 * s), 62))
        pole_x = x + l_side * (fw // 2 + min(int(30 * s), 34))
        pole_top = y - max(26, min(int(38 * s), 52))
        pygame.draw.line(surface, (40, 30, 19), (pole_x + 1, pole_top + 2), (pole_x + 1, y - 1), 3)
        pygame.draw.line(surface, (86, 66, 42), (pole_x, pole_top + 1), (pole_x, y - 2), 2)
        pygame.draw.line(surface, (60, 46, 28), (pole_x - 4, pole_top + 5), (pole_x + 4, pole_top + 5), 2)
        mid_x = (ax2 + pole_x) // 2
        mid_y = max(ay2, pole_top) + 7
        pygame.draw.lines(surface, (172, 166, 154), False,
                          [(ax2, ay2), (mid_x, mid_y), (pole_x, pole_top + 4)], 1)
        crng = random.Random(seed * 13 + 5)
        for ti, t in enumerate((0.22, 0.5, 0.78)):
            if crng.random() < 0.2:
                continue
            seg_a, seg_b = ((ax2, ay2), (mid_x, mid_y)) if t < 0.5 else ((mid_x, mid_y), (pole_x, pole_top + 4))
            tt = t * 2 if t < 0.5 else (t - 0.5) * 2
            cx3 = int(seg_a[0] + (seg_b[0] - seg_a[0]) * tt)
            cy3 = int(seg_a[1] + (seg_b[1] - seg_a[1]) * tt)
            cw3 = max(6, int((9 if ti % 2 else 12) * s * 0.8))
            ch3 = max(8, int((13 if ti % 2 else 10) * s * 0.8))
            ccol = crng.choice([(226, 222, 212), (192, 168, 122), (124, 136, 160), (212, 206, 196)])
            pygame.draw.rect(surface, ccol, (cx3 - cw3 // 2, cy3, cw3, ch3))
            pygame.draw.line(surface, (max(0, ccol[0] - 38), max(0, ccol[1] - 38), max(0, ccol[2] - 34)),
                             (cx3 - cw3 // 2 + 2, cy3 + 2), (cx3 - cw3 // 2 + 2, cy3 + ch3 - 2), 1)
            for pgx in (cx3 - cw3 // 2 + 1, cx3 + cw3 // 2 - 1):
                pygame.draw.line(surface, (90, 72, 48), (pgx, cy3 - 2), (pgx, cy3 + 1), 1)

    # ── gable hoist beam with hanging sack (merchants, workshops, harbour) ──
    if (style_idx in (3, 5) or district == "harbor") and rng.random() < 0.22:
        h_side = -annex_side if annex_side else (1 if seed % 2 else -1)
        apex_y = eave_y - roof_h + max(6, int(9 * s))
        beam_len = max(12, int(16 * s))
        pygame.draw.line(surface, (52, 40, 26), (x, apex_y), (x + h_side * beam_len, apex_y), 3)
        pygame.draw.line(surface, (84, 66, 42), (x, apex_y - 1), (x + h_side * beam_len, apex_y - 1), 1)
        hx2 = x + h_side * (beam_len - 3)
        pygame.draw.circle(surface, (70, 68, 64), (hx2, apex_y + 3), 3, 1)
        rope_len = max(10, int(15 * s))
        pygame.draw.line(surface, (140, 124, 96), (hx2, apex_y + 5), (hx2, apex_y + 5 + rope_len), 1)
        if seed % 3:
            pygame.draw.ellipse(surface, (148, 124, 86), (hx2 - 5, apex_y + 4 + rope_len, 11, 13))
            pygame.draw.ellipse(surface, (176, 152, 110), (hx2 - 4, apex_y + 4 + rope_len, 7, 8))
            pygame.draw.line(surface, (94, 76, 50), (hx2 - 3, apex_y + 5 + rope_len), (hx2 + 3, apex_y + 5 + rope_len), 2)
        else:
            cr2 = max(4, int(5 * s))
            pygame.draw.rect(surface, (88, 70, 44), (hx2 - cr2, apex_y + 4 + rope_len, cr2 * 2, cr2 * 2))
            pygame.draw.rect(surface, (52, 40, 24), (hx2 - cr2, apex_y + 4 + rope_len, cr2 * 2, cr2 * 2), 1)

    # ── stacked woodpile against a side wall ──
    if style_idx in (0, 2, 5) and rustic and rng.random() < 0.30:
        w_side = -annex_side if annex_side else (-1 if rng.random() < 0.5 else 1)
        wp_cx = x + w_side * (fw // 2 + 10)
        lr = max(3, min(5, int(4 * s)))
        wrng = random.Random(seed * 23 + 3)
        for li in range(3):
            cols = 4 - li
            for lj in range(cols):
                lx2 = wp_cx - (cols - 1) * lr + lj * lr * 2
                ly2 = y - 4 - lr - li * (lr * 2 - 1)
                tone = wrng.randint(-12, 10)
                pygame.draw.circle(surface, (112 + tone, 88 + tone, 56 + tone), (lx2, ly2), lr)
                pygame.draw.circle(surface, (58, 42, 26), (lx2, ly2), lr, 1)
                pygame.draw.circle(surface, (80 + tone, 62 + tone, 38 + tone), (lx2, ly2), max(1, lr - 2), 1)

    # ── ridge-top character: pennant for the wealthy, a crow for the poor ──
    apex = (x, eave_y - roof_h)
    if posh and style_idx != 2 and rng.random() < 0.16:
        ph = max(10, int(14 * s))
        pygame.draw.line(surface, (60, 56, 50), (apex[0], apex[1]), (apex[0], apex[1] - ph), 2)
        fcol = rng.choice([(168, 40, 36), (44, 70, 140), (196, 158, 60)])
        pygame.draw.polygon(surface, fcol, [(apex[0] + 1, apex[1] - ph), (apex[0] + max(8, int(12 * s)), apex[1] - ph + 3),
                                            (apex[0] + 1, apex[1] - ph + 6)])
        pygame.draw.circle(surface, (196, 168, 84), (apex[0], apex[1] - ph), 2)
    elif district in ("shanty", "rook") and rng.random() < 0.14:
        bx3, by3 = apex[0] + rng.randint(-6, 6), apex[1] + 1
        pygame.draw.ellipse(surface, (22, 20, 24), (bx3 - 3, by3 - 5, 7, 5))
        pygame.draw.circle(surface, (22, 20, 24), (bx3 + 3, by3 - 6), 2)
        pygame.draw.line(surface, (90, 74, 40), (bx3 + 5, by3 - 6), (bx3 + 7, by3 - 5), 1)
        pygame.draw.line(surface, (22, 20, 24), (bx3 - 3, by3 - 3), (bx3 - 6, by3 - 1), 1)

    return out_fnd


def _draw_house_shadow(surface: pygame.Surface, x: int, y: int, w: int) -> None:
    shadow = pygame.Rect(x - w // 2 - 16, y - 8, w + 32, 18)
    sh = pygame.Surface((shadow.width, shadow.height), pygame.SRCALPHA)
    pygame.draw.ellipse(sh, (10, 10, 14, 90), sh.get_rect())
    inner = sh.get_rect().inflate(-8, -6)
    pygame.draw.ellipse(sh, (6, 6, 10, 60), inner)
    surface.blit(sh, shadow.topleft)


def _draw_house_stone_foundation(surface: pygame.Surface, rect: pygame.Rect, seed: int) -> None:
    pygame.draw.rect(surface, (86, 82, 76), rect)
    for row in range(max(1, rect.height // 10)):
        ry = rect.top + 2 + row * 10
        off = 14 if row % 2 else 0
        for sx in range(rect.left + 2 + off, rect.right - 6, 28):
            sc = 78 + _house_hash(sx * 7 + row * 13, seed) % 20
            sw = 24 + _house_hash(sx * 3 + row, seed) % 6
            pygame.draw.rect(surface, (sc, sc - 4, sc - 10), (sx, ry, min(sw, rect.right - sx - 2), 8), border_radius=1)
            pygame.draw.rect(surface, (48, 44, 38), (sx, ry, min(sw, rect.right - sx - 2), 8), 1, border_radius=1)
    pygame.draw.rect(surface, (48, 44, 38), rect, 1)


def _draw_house_window(surface: pygame.Surface, wx: int, wy: int, ww: int, wh: int,
                        frame_col: tuple, lit: bool = True, shutters: bool = True) -> None:
    wr = pygame.Rect(wx, wy, ww, wh)
    # Stone/wood sill beneath window
    sill_h = max(2, wh // 8)
    sill = pygame.Rect(wx - 3, wy + wh, ww + 6, sill_h)
    pygame.draw.rect(surface, (frame_col[0] + 20, frame_col[1] + 18, frame_col[2] + 14), sill, border_radius=1)
    pygame.draw.rect(surface, frame_col, sill, 1, border_radius=1)
    # Lintel above window
    lintel = pygame.Rect(wx - 2, wy - 3, ww + 4, 4)
    pygame.draw.rect(surface, (frame_col[0] + 14, frame_col[1] + 12, frame_col[2] + 8), lintel, border_radius=1)
    # Glass panes
    if lit:
        # Warm interior gradient
        top_c = (235, 200, 110)
        bot_c = (200, 165, 80)
        for row in range(max(1, wh)):
            t = row / max(1, wh - 1)
            c = (int(top_c[0] + (bot_c[0] - top_c[0]) * t),
                 int(top_c[1] + (bot_c[1] - top_c[1]) * t),
                 int(top_c[2] + (bot_c[2] - top_c[2]) * t))
            pygame.draw.line(surface, c, (wr.left + 1, wr.top + row), (wr.right - 1, wr.top + row))
    else:
        pygame.draw.rect(surface, (30, 36, 50), wr)
        # Faint reflection
        ref = pygame.Rect(wr.left + 2, wr.top + 2, max(1, ww // 3), max(1, wh // 3))
        pygame.draw.rect(surface, (48, 56, 72), ref)
    # Cross mullions
    pygame.draw.line(surface, frame_col, (wr.centerx, wr.top), (wr.centerx, wr.bottom), 2)
    pygame.draw.line(surface, frame_col, (wr.left, wr.centery), (wr.right, wr.centery), 2)
    pygame.draw.rect(surface, frame_col, wr, 2)
    # Shutters
    if shutters and ww >= 10:
        sh_w = max(3, ww // 3)
        sh_col = (frame_col[0] + 30, frame_col[1] + 20, frame_col[2] + 10)
        sh_dark = (frame_col[0] + 10, frame_col[1] + 5, frame_col[2])
        for sx, side in [(wx - sh_w - 1, -1), (wx + ww + 1, 1)]:
            sr = pygame.Rect(sx, wy, sh_w, wh)
            pygame.draw.rect(surface, sh_col, sr, border_radius=1)
            # Plank lines
            for pl in range(1, max(2, sh_w // 4)):
                plx = sr.left + pl * (sh_w // max(2, sh_w // 4))
                pygame.draw.line(surface, sh_dark, (plx, sr.top + 1), (plx, sr.bottom - 1), 1)
            pygame.draw.rect(surface, frame_col, sr, 1, border_radius=1)
    # Warm glow halo for lit windows
    if lit:
        gs = pygame.Surface((ww + 24, wh + 24), pygame.SRCALPHA)
        pygame.draw.ellipse(gs, (255, 200, 100, 28), gs.get_rect())
        inner = gs.get_rect().inflate(-8, -8)
        pygame.draw.ellipse(gs, (255, 210, 120, 18), inner)
        surface.blit(gs, (wx - 12, wy - 12))


def _draw_house_door(surface: pygame.Surface, dx: int, dy: int, dw: int, dh: int,
                      wood_col: tuple, frame_col: tuple, seed: int) -> None:
    dr = pygame.Rect(dx, dy, dw, dh)
    # Doorframe recess
    recess = dr.inflate(4, 2)
    recess.bottom = dr.bottom
    pygame.draw.rect(surface, (frame_col[0] - 8, frame_col[1] - 6, frame_col[2] - 4), recess, border_radius=2)
    # Door body — wood grain gradient
    for row in range(dh):
        t = row / max(1, dh - 1)
        c = (int(wood_col[0] - 8 * t), int(wood_col[1] - 6 * t), int(wood_col[2] - 4 * t))
        pygame.draw.line(surface, c, (dr.left + 1, dr.top + row), (dr.right - 1, dr.top + row))
    # Plank lines
    n_planks = max(2, dw // 8)
    for i in range(1, n_planks):
        px = dr.left + i * (dw // n_planks)
        pygame.draw.line(surface, frame_col, (px, dr.top + 2), (px, dr.bottom - 2), 1)
    # Iron strap hinges with studs
    for hy in (dr.top + dh // 4, dr.bottom - dh // 4):
        hw = min(14, dw // 2)
        pygame.draw.rect(surface, (52, 48, 42), (dr.left - 1, hy, hw, 4), border_radius=1)
        pygame.draw.rect(surface, (38, 34, 28), (dr.left - 1, hy, hw, 4), 1, border_radius=1)
        # Rivet studs
        for ri in range(0, hw, max(4, hw // 3)):
            pygame.draw.circle(surface, (72, 66, 56), (dr.left + ri + 2, hy + 2), 1)
    # Iron ring handle
    handle_x = dr.right - max(6, dw // 4) if seed % 2 == 0 else dr.left + max(6, dw // 4)
    handle_y = dr.centery
    r = max(3, dw // 10)
    pygame.draw.circle(surface, (148, 124, 68), (handle_x, handle_y), r, 2)
    pygame.draw.circle(surface, (108, 90, 50), (handle_x, handle_y - r), 2)  # mount
    # Door frame outline
    pygame.draw.rect(surface, frame_col, dr, 2, border_radius=2)
    # Threshold step
    step = pygame.Rect(dx - 3, dy + dh, dw + 6, max(3, dh // 10))
    pygame.draw.rect(surface, (72, 68, 60), step, border_radius=1)
    pygame.draw.rect(surface, (50, 46, 38), step, 1, border_radius=1)


def _draw_house_chimney(surface: pygame.Surface, cx: int, cy: int, cw: int, ch: int, seed: int) -> None:
    cr = pygame.Rect(cx - cw // 2, cy, cw, ch)
    # Brick rows with mortar
    for row in range(max(1, ch // 7)):
        ry = cr.top + row * 7
        off = 4 if row % 2 else 0
        for bx in range(cr.left, cr.right - 3, 10):
            bc = 74 + _house_hash(bx * 9 + row * 5, seed) % 18
            brick_c = (bc, bc // 2 + 12, bc // 3 + 8)
            pygame.draw.rect(surface, brick_c, (bx + off, ry, 9, 6))
            pygame.draw.rect(surface, (38, 26, 16), (bx + off, ry, 9, 6), 1)
    pygame.draw.rect(surface, (38, 26, 16), cr, 1)
    # Soot staining at the top
    soot = pygame.Surface((cw + 4, min(14, ch // 2)), pygame.SRCALPHA)
    for sy in range(soot.get_height()):
        a = int(60 * (1.0 - sy / max(1, soot.get_height() - 1)))
        pygame.draw.line(soot, (20, 18, 16, a), (0, sy), (soot.get_width(), sy))
    surface.blit(soot, (cr.left - 2, cr.top))
    # Decorative cap with crown
    cap = pygame.Rect(cr.left - 4, cr.top - 4, cr.width + 8, 7)
    pygame.draw.rect(surface, (72, 64, 56), cap, border_radius=1)
    pygame.draw.rect(surface, (42, 34, 26), cap, 1, border_radius=1)
    # Chimney pot / crown
    pot = pygame.Rect(cr.centerx - cw // 3, cr.top - 8, cw * 2 // 3, 5)
    pygame.draw.rect(surface, (62, 54, 44), pot, border_radius=1)
    pygame.draw.rect(surface, (36, 28, 20), pot, 1, border_radius=1)


# ── Style 0: Tudor half-timber (classic, jetty overhang) ────────────────────
def _draw_house_tudor(surface: pygame.Surface, x: int, y: int, s: float, seed: int) -> pygame.Rect:
    rng = random.Random(seed)
    w_g = int(110 * s); h_g = int(60 * s)
    w_u = int(128 * s); h_u = int(68 * s)
    fnd_h = int(18 * s)
    gr = pygame.Rect(x - w_g // 2, y - h_g, w_g, h_g)
    ur = pygame.Rect(x - w_u // 2, gr.top - h_u, w_u, h_u)
    wall_cols = [(208, 202, 186), (192, 186, 172), (200, 192, 178), (182, 176, 164),
                 (214, 198, 156), (190, 198, 178)]
    roof_cols = [(118, 48, 38), (98, 44, 34), (58, 62, 68), (48, 54, 60),
                 (96, 74, 52), (74, 84, 70)]
    wc = wall_cols[seed % len(wall_cols)]; rc = roof_cols[(seed // 3) % len(roof_cols)]
    tc = (48, 34, 24); td = (30, 20, 14)
    bw = max(3, int(5 * s))
    _draw_house_shadow(surface, x, y, w_u)
    # foundation
    fnd = pygame.Rect(gr.left, gr.bottom - fnd_h, gr.width, fnd_h)
    _draw_house_stone_foundation(surface, fnd, seed)
    # ground wall
    gw = pygame.Rect(gr.left, gr.top, gr.width, gr.height - fnd_h)
    pygame.draw.rect(surface, wc, gw); pygame.draw.rect(surface, (148, 142, 128), gw, 1)
    # upper wall
    pygame.draw.rect(surface, wc, ur); pygame.draw.rect(surface, (148, 142, 128), ur, 1)
    # jetty corbels
    for cx2 in range(gr.left, gr.right + 1, max(1, gr.width // 3)):
        cw2 = int(7 * s)
        pygame.draw.polygon(surface, tc, [(cx2 - cw2, gr.top), (cx2 + cw2, gr.top),
                                           (cx2 + cw2, gr.top + int(10 * s)), (cx2 - cw2, gr.top + int(8 * s))])
        pygame.draw.polygon(surface, td, [(cx2 - cw2, gr.top), (cx2 + cw2, gr.top),
                                           (cx2 + cw2, gr.top + int(10 * s)), (cx2 - cw2, gr.top + int(8 * s))], 1)
    # timber framing
    for rect in (gw, ur):
        pygame.draw.rect(surface, tc, (rect.left, rect.top, bw, rect.height))
        pygame.draw.rect(surface, tc, (rect.right - bw, rect.top, bw, rect.height))
        pygame.draw.rect(surface, tc, (rect.left, rect.top, rect.width, bw))
        pygame.draw.rect(surface, tc, (rect.left, rect.bottom - bw, rect.width, bw))
        mid_x = rect.left + rect.width // 2 - bw // 2
        pygame.draw.rect(surface, tc, (mid_x, rect.top, bw, rect.height))
        # diagonal braces
        if rng.random() > 0.3:
            pygame.draw.line(surface, tc, (rect.left + bw, rect.top + bw),
                             (mid_x, rect.bottom - bw), bw)
        if rng.random() > 0.3:
            pygame.draw.line(surface, tc, (rect.right - bw, rect.top + bw),
                             (mid_x + bw, rect.bottom - bw), bw)
    # roof
    rh = int(78 * s); rov = int(12 * s)
    rpts = [(ur.left - rov, ur.top), (ur.right + rov, ur.top), (x, ur.top - rh)]
    pygame.draw.polygon(surface, rc, rpts)
    for i in range(1, 9):
        yl = ur.top - int(rh * i / 9)
        hw = int((ur.width // 2 + rov) * (1.0 - i / 9))
        pygame.draw.line(surface, (rc[0] - 20, rc[1] - 10, rc[2] - 8), (x - hw, yl), (x + hw, yl), 1)
    pygame.draw.polygon(surface, (28, 24, 20), rpts, 2)
    # chimney
    if rng.random() < 0.85:
        ch_side = -1 if rng.random() < 0.5 else 1
        _draw_house_chimney(surface, x + int(w_u * 0.28 * ch_side), ur.top - rh + int(18 * s),
                            max(10, int(14 * s)), max(28, int(42 * s)), seed)
    # windows
    ww = max(12, int(16 * s)); wh = max(16, int(22 * s))
    lit = seed % 3 != 0
    _draw_house_window(surface, ur.left + ur.width // 4 - ww // 2, ur.top + int(18 * s), ww, wh, td, lit)
    _draw_house_window(surface, ur.right - ur.width // 4 - ww // 2, ur.top + int(18 * s), ww, wh, td, lit)
    ds = -1 if rng.random() < 0.5 else 1
    _draw_house_window(surface, gr.centerx - ds * gr.width // 4 - ww // 2, gw.top + int(12 * s), ww, wh, td, lit)
    # door
    dw2 = max(36, int(38 * s)); dh2 = max(50, int(56 * s))
    dx2 = gr.centerx + ds * gr.width // 4 - dw2 // 2
    _draw_house_door(surface, dx2, gr.bottom - fnd_h - dh2, dw2, dh2, (58, 40, 24), td, seed)
    # Wall weathering
    _draw_wall_weathering(surface, gw, seed, 0.4)
    _draw_wall_weathering(surface, ur, seed + 1, 0.3)
    # Lantern by door
    _draw_house_lantern(surface, dx2 + dw2 + 2, gr.bottom - fnd_h - dh2 + int(6 * s), s)
    _draw_house_extras(surface, x, y, w_u, h_g + h_u, s, seed)
    return fnd


# ── Style 1: Stone townhouse (tall, narrow, grey stone) ─────────────────────
def _draw_house_stone(surface: pygame.Surface, x: int, y: int, s: float, seed: int) -> pygame.Rect:
    w = int(90 * s); h1 = int(70 * s); h2 = int(64 * s)
    fnd_h = int(16 * s)
    r1 = pygame.Rect(x - w // 2, y - h1, w, h1)
    r2 = pygame.Rect(x - w // 2, r1.top - h2, w, h2)
    stone_cols = [(96, 92, 86), (88, 84, 78), (82, 78, 72), (92, 88, 80),
                  (104, 98, 86), (84, 86, 90)]
    sc = stone_cols[seed % len(stone_cols)]
    sd = (sc[0] - 20, sc[1] - 18, sc[2] - 16)
    _draw_house_shadow(surface, x, y, w)
    # two floors — stone masonry
    for rect in (r1, r2):
        pygame.draw.rect(surface, sc, rect)
        for row in range(max(1, rect.height // 12)):
            ry = rect.top + 2 + row * 12
            off = 16 if row % 2 else 0
            for sx in range(rect.left + 2 + off, rect.right - 8, 32):
                sv = sc[0] - 6 + _house_hash(sx * 7 + row * 11, seed) % 14
                sw = 28 + _house_hash(sx * 3 + row, seed) % 6
                pygame.draw.rect(surface, (sv, sv - 4, sv - 10), (sx, ry, min(sw, rect.right - sx - 2), 10))
                pygame.draw.rect(surface, sd, (sx, ry, min(sw, rect.right - sx - 2), 10), 1)
        pygame.draw.rect(surface, sd, rect, 2)
    # string course between floors
    pygame.draw.rect(surface, (sc[0] + 14, sc[1] + 12, sc[2] + 10), (x - w // 2 - 4, r1.top - 3, w + 8, 6))
    pygame.draw.rect(surface, sd, (x - w // 2 - 4, r1.top - 3, w + 8, 6), 1)
    # steep slate roof
    rh = int(70 * s); rov = int(8 * s)
    rpts = [(r2.left - rov, r2.top), (r2.right + rov, r2.top), (x, r2.top - rh)]
    pygame.draw.polygon(surface, (44, 48, 52), rpts)
    for i in range(1, 10):
        yl = r2.top - int(rh * i / 10)
        hw = int((r2.width // 2 + rov) * (1.0 - i / 10))
        off2 = 5 if i % 2 else 0
        for tx in range(x - hw + off2, x + hw - 4, 10):
            tv = 40 + _house_hash(tx * 5 + i * 9, seed) % 14
            pygame.draw.rect(surface, (tv, tv + 4, tv + 6), (tx, yl, 9, 8), border_radius=1)
            pygame.draw.rect(surface, (24, 26, 28), (tx, yl, 9, 8), 1, border_radius=1)
    pygame.draw.polygon(surface, (28, 30, 34), rpts, 2)
    # chimney
    _draw_house_chimney(surface, x + int(w * 0.25 * (1 if seed % 2 else -1)),
                        r2.top - rh + int(16 * s), max(10, int(12 * s)), max(32, int(46 * s)), seed)
    # windows — arched stone lintels
    ww = max(10, int(14 * s)); wh = max(18, int(24 * s))
    lit = seed % 4 != 2
    for floor_rect in (r1, r2):
        nw = 2 if floor_rect.width > int(70 * s) else 1
        for wi in range(nw):
            wx = floor_rect.left + (wi + 1) * floor_rect.width // (nw + 1) - ww // 2
            wy = floor_rect.top + int(14 * s)
            pygame.draw.ellipse(surface, (sc[0] + 8, sc[1] + 6, sc[2] + 4),
                                (wx - 2, wy - 4, ww + 4, 10))
            _draw_house_window(surface, wx, wy, ww, wh, sd, lit)
    # door — arched
    dw2 = max(36, int(38 * s)); dh2 = max(52, int(58 * s))
    dx = x - dw2 // 2
    dy = r1.bottom - fnd_h - dh2
    pygame.draw.ellipse(surface, (sc[0] + 8, sc[1] + 6, sc[2] + 4), (dx - 4, dy - 8, dw2 + 8, 18))
    _draw_house_door(surface, dx, dy, dw2, dh2, (52, 38, 22), sd, seed)
    # Wall weathering
    for wr in (r1, r2):
        _draw_wall_weathering(surface, wr, seed + wr.top, 0.5)
    _draw_house_lantern(surface, dx + dw2 + 2, dy + int(4 * s), s)
    _draw_house_extras(surface, x, y, w, h1 + h2, s, seed)
    fnd = pygame.Rect(r1.left, r1.bottom - fnd_h, w, fnd_h)
    return fnd


# ── Style 2: Thatched cottage (small, round-ish, warm) ─────────────────────
def _draw_house_cottage(surface: pygame.Surface, x: int, y: int, s: float, seed: int) -> pygame.Rect:
    w = int(120 * s); h = int(72 * s)
    fnd_h = int(14 * s)
    wr = pygame.Rect(x - w // 2, y - h, w, h)
    wall_cols = [(196, 178, 142), (186, 168, 132), (204, 186, 148), (178, 162, 128),
                 (210, 198, 170), (168, 156, 122)]
    wc = wall_cols[seed % len(wall_cols)]
    wd = (wc[0] - 24, wc[1] - 20, wc[2] - 16)
    _draw_house_shadow(surface, x, y, w + 10)
    # foundation — rough fieldstone
    fnd = pygame.Rect(wr.left - 4, wr.bottom - fnd_h, w + 8, fnd_h)
    for fx in range(fnd.left, fnd.right - 6, 14):
        fc = 72 + _house_hash(fx * 9, seed) % 20
        fw = 10 + _house_hash(fx * 5, seed) % 6
        fh2 = fnd_h - 4 + _house_hash(fx * 3, seed) % 4
        pygame.draw.ellipse(surface, (fc, fc - 4, fc - 8), (fx, fnd.top + 2, fw, fh2))
        pygame.draw.ellipse(surface, (48, 44, 38), (fx, fnd.top + 2, fw, fh2), 1)
    # whitewashed wall (slightly uneven)
    pygame.draw.rect(surface, wc, (wr.left, wr.top, wr.width, wr.height - fnd_h))
    # plaster cracks
    for ci in range(6):
        cx2 = wr.left + 8 + _house_hash(ci * 41, seed) % (wr.width - 16)
        cy2 = wr.top + 6 + _house_hash(ci * 23, seed) % (wr.height - fnd_h - 12)
        cl = 6 + _house_hash(ci * 13, seed) % 12
        pygame.draw.line(surface, wd, (cx2, cy2), (cx2 + cl, cy2 + _house_hash(ci * 7, seed) % 5 - 2), 1)
    pygame.draw.rect(surface, wd, (wr.left, wr.top, wr.width, wr.height - fnd_h), 1)
    # thick thatch roof — rounded, overhanging
    th_h = int(68 * s); th_ov = int(18 * s)
    th_l, th_r = wr.left - th_ov, wr.right + th_ov
    th_top = wr.top - th_h
    # base shape
    th_pts = [(th_l, wr.top + 4), (th_l + 8, th_top + th_h // 3),
              (x, th_top), (th_r - 8, th_top + th_h // 3), (th_r, wr.top + 4)]
    pygame.draw.polygon(surface, (148, 128, 72), th_pts)
    # thatch texture rows
    for row in range(12):
        frac = row / 11
        ry = int(th_top + frac * (wr.top + 4 - th_top))
        rw = int(frac * (th_r - th_l) * 0.92)
        rx = x - rw // 2
        off2 = 4 if row % 2 else 0
        for ti in range(max(1, rw // 10)):
            tx = rx + ti * 10 + off2
            tv = 138 + _house_hash(tx * 5 + row * 7, seed) % 22
            pygame.draw.rect(surface, (tv, tv - 16, tv - 54), (tx, ry, 9, 8), border_radius=1)
    # thatch edge (ragged)
    for ei in range(th_l, th_r, 6):
        eh = 2 + _house_hash(ei * 3, seed) % 5
        pygame.draw.line(surface, (128, 108, 56), (ei, wr.top + 2), (ei, wr.top + 2 + eh), 1)
    pygame.draw.polygon(surface, (108, 88, 44), th_pts, 2)
    # chimney (fat, stubby, whitewashed)
    ch_x = x + int(w * 0.3 * (1 if seed % 2 else -1))
    ch_w2 = max(12, int(16 * s)); ch_h2 = max(24, int(32 * s))
    ch_r = pygame.Rect(ch_x - ch_w2 // 2, th_top + th_h // 4, ch_w2, ch_h2)
    pygame.draw.rect(surface, wc, ch_r)
    pygame.draw.rect(surface, wd, ch_r, 1)
    pygame.draw.rect(surface, (wc[0] + 8, wc[1] + 6, wc[2] + 4), (ch_r.left - 2, ch_r.top - 2, ch_r.width + 4, 5))
    # window — small, round-topped
    ww = max(12, int(16 * s)); wh = max(14, int(20 * s))
    lit = seed % 3 != 1
    for wi in range(2):
        wx = wr.left + (wi + 1) * wr.width // 3 - ww // 2
        wy = wr.top + int(16 * s)
        _draw_house_window(surface, wx, wy, ww, wh, wd, lit)
        # flower box
        pygame.draw.rect(surface, (56, 44, 28), (wx - 2, wy + wh, ww + 4, int(6 * s)), border_radius=1)
        for fi in range(3):
            fc = [(180, 60, 60), (220, 180, 60), (180, 80, 160)][fi % 3]
            pygame.draw.circle(surface, fc, (wx + 3 + fi * (ww // 3), wy + wh - 2), max(2, int(3 * s)))
    # door — rounded top, warm wood
    dw2 = max(36, int(38 * s)); dh2 = max(50, int(56 * s))
    dx = x - dw2 // 2; dy = wr.bottom - fnd_h - dh2
    pygame.draw.ellipse(surface, (66, 48, 28), (dx - 2, dy - 6, dw2 + 4, 14))
    _draw_house_door(surface, dx, dy, dw2, dh2, (66, 48, 28), wd, seed)
    # doorstep
    pygame.draw.rect(surface, (78, 74, 68), (dx - 4, dy + dh2, dw2 + 8, int(5 * s)), border_radius=1)
    # Cottage weathering — heavier for rustic feel
    _draw_wall_weathering(surface, pygame.Rect(wr.left, wr.top, wr.width, wr.height - fnd_h), seed, 0.6)
    # Lantern by door
    _draw_house_lantern(surface, dx - int(12 * s), dy + int(4 * s), s)
    _draw_house_extras(surface, x, y, w, h, s, seed)
    return fnd


# ── Style 3: Merchant's house (wide, wealthy, bay window) ──────────────────
def _draw_house_merchant(surface: pygame.Surface, x: int, y: int, s: float, seed: int) -> pygame.Rect:
    w = int(140 * s); h1 = int(66 * s); h2 = int(72 * s)
    fnd_h = int(18 * s)
    r1 = pygame.Rect(x - w // 2, y - h1, w, h1)
    r2 = pygame.Rect(x - w // 2 - int(8 * s), r1.top - h2, w + int(16 * s), h2)
    wall_cols = [(212, 206, 188), (198, 192, 174), (218, 212, 194),
                 (226, 218, 198), (204, 198, 182)]
    wc = wall_cols[seed % len(wall_cols)]
    tc = (44, 32, 20); td = (28, 18, 10)
    roof_cols = [(112, 44, 34), (52, 56, 62), (72, 42, 30),
                 (92, 54, 40), (62, 68, 76)]
    rc = roof_cols[(seed // 2) % len(roof_cols)]
    bw = max(3, int(5 * s))
    _draw_house_shadow(surface, x, y, w + 20)
    # foundation
    fnd = pygame.Rect(r1.left, r1.bottom - fnd_h, w, fnd_h)
    _draw_house_stone_foundation(surface, fnd, seed)
    # ground floor
    gw = pygame.Rect(r1.left, r1.top, r1.width, r1.height - fnd_h)
    pygame.draw.rect(surface, wc, gw); pygame.draw.rect(surface, (146, 140, 126), gw, 1)
    # upper floor (wider — jetty)
    pygame.draw.rect(surface, wc, r2); pygame.draw.rect(surface, (146, 140, 126), r2, 1)
    # heavy timber framing
    for rect in (gw, r2):
        pygame.draw.rect(surface, tc, (rect.left, rect.top, bw, rect.height))
        pygame.draw.rect(surface, tc, (rect.right - bw, rect.top, bw, rect.height))
        pygame.draw.rect(surface, tc, (rect.left, rect.top, rect.width, bw))
        pygame.draw.rect(surface, tc, (rect.left, rect.bottom - bw, rect.width, bw))
        # thirds
        for div in range(1, 3):
            vx = rect.left + div * rect.width // 3
            pygame.draw.rect(surface, tc, (vx - bw // 2, rect.top, bw, rect.height))
        # herringbone/diamond pattern in center panel
        cx2 = rect.left + rect.width // 2
        cy2 = rect.top + rect.height // 2
        dsize = min(rect.width // 4, rect.height // 2) - bw
        if dsize > 8:
            pygame.draw.line(surface, tc, (cx2, cy2 - dsize), (cx2 + dsize, cy2), bw - 1)
            pygame.draw.line(surface, tc, (cx2 + dsize, cy2), (cx2, cy2 + dsize), bw - 1)
            pygame.draw.line(surface, tc, (cx2, cy2 + dsize), (cx2 - dsize, cy2), bw - 1)
            pygame.draw.line(surface, tc, (cx2 - dsize, cy2), (cx2, cy2 - dsize), bw - 1)
    # jetty beam
    jetty_h = int(8 * s)
    pygame.draw.rect(surface, tc, (r2.left - 2, r2.bottom - jetty_h, r2.width + 4, jetty_h))
    pygame.draw.rect(surface, td, (r2.left - 2, r2.bottom - jetty_h, r2.width + 4, jetty_h), 1)
    # bay window (protruding box window on upper floor)
    bay_w = int(36 * s); bay_d = int(12 * s); bay_h = int(40 * s)
    bay_side = 1 if seed % 2 else -1
    bay_x = r2.left + r2.width // 4 if bay_side < 0 else r2.right - r2.width // 4 - bay_w
    bay_y = r2.top + int(12 * s)
    bay_r = pygame.Rect(bay_x, bay_y, bay_w, bay_h)
    pygame.draw.rect(surface, wc, bay_r)
    # bay window panes (3 panels)
    pw = bay_w // 3
    for pi in range(3):
        pr = pygame.Rect(bay_r.left + pi * pw + 1, bay_r.top + 2, pw - 2, bay_h - 4)
        lit = seed % 5 != 3
        glow_c = (218, 186, 92) if lit else (36, 42, 54)
        pygame.draw.rect(surface, glow_c, pr)
        pygame.draw.rect(surface, td, pr, 1)
    pygame.draw.rect(surface, tc, bay_r, 2)
    # bay window sill and small roof
    pygame.draw.rect(surface, tc, (bay_r.left - 3, bay_r.bottom, bay_r.width + 6, int(4 * s)))
    pygame.draw.polygon(surface, rc, [(bay_r.left - 4, bay_r.top),
                                       (bay_r.right + 4, bay_r.top),
                                       (bay_r.centerx, bay_r.top - int(10 * s))])
    # main roof (hipped)
    rh = int(74 * s); rov = int(14 * s)
    rpts = [(r2.left - rov, r2.top), (r2.right + rov, r2.top), (x, r2.top - rh)]
    pygame.draw.polygon(surface, rc, rpts)
    for i in range(1, 10):
        yl = r2.top - int(rh * i / 10)
        hw = int((r2.width // 2 + rov) * (1.0 - i / 10))
        pygame.draw.line(surface, (rc[0] - 16, rc[1] - 8, rc[2] - 6), (x - hw, yl), (x + hw, yl), 1)
    pygame.draw.polygon(surface, (24, 20, 16), rpts, 2)
    # dormer window
    dm_x = x + int(20 * s * bay_side * -1)
    dm_w = int(20 * s); dm_h = int(18 * s)
    dm_roof_h = int(14 * s)
    dm_y = r2.top - rh // 2
    pygame.draw.rect(surface, wc, (dm_x - dm_w // 2, dm_y, dm_w, dm_h))
    pygame.draw.polygon(surface, rc, [(dm_x - dm_w // 2 - 3, dm_y),
                                       (dm_x + dm_w // 2 + 3, dm_y),
                                       (dm_x, dm_y - dm_roof_h)])
    _draw_house_window(surface, dm_x - int(6 * s), dm_y + 2, int(12 * s), dm_h - 4, td, True)
    # chimney
    _draw_house_chimney(surface, x + int(w * 0.32 * bay_side), r2.top - rh + int(14 * s),
                        max(12, int(15 * s)), max(34, int(48 * s)), seed)
    # ground floor windows
    ww = max(12, int(16 * s)); wh = max(16, int(22 * s))
    for wi in range(3):
        wx = gw.left + (wi + 1) * gw.width // 4 - ww // 2
        _draw_house_window(surface, wx, gw.top + int(10 * s), ww, wh, td, seed % 3 != 1)
    # door (central, with canopy)
    dw2 = max(36, int(38 * s)); dh2 = max(50, int(56 * s))
    dx = x - dw2 // 2; dy = r1.bottom - fnd_h - dh2
    _draw_house_door(surface, dx, dy, dw2, dh2, (52, 36, 20), td, seed)
    # small canopy over door
    can_w = dw2 + int(16 * s)
    pygame.draw.polygon(surface, rc, [(dx - int(8 * s), dy), (dx + dw2 + int(8 * s), dy),
                                       (x, dy - int(14 * s))])
    pygame.draw.polygon(surface, td, [(dx - int(8 * s), dy), (dx + dw2 + int(8 * s), dy),
                                       (x, dy - int(14 * s))], 1)
    # Light weathering (wealthy house, well-maintained)
    _draw_wall_weathering(surface, gw, seed, 0.25)
    _draw_wall_weathering(surface, r2, seed + 1, 0.2)
    # Twin lanterns flanking door
    _draw_house_lantern(surface, dx - int(12 * s), dy + int(2 * s), s)
    _draw_house_lantern(surface, dx + dw2 + 2, dy + int(2 * s), s)
    _draw_house_extras(surface, x, y, w, h1 + h2, s, seed)
    return fnd


# ── Style 4: Tall narrow row house (cramped, 2 stories) ────────────────────
def _draw_house_rowhouse(surface: pygame.Surface, x: int, y: int, s: float, seed: int) -> pygame.Rect:
    w = int(72 * s); fh = int(54 * s)
    fnd_h = int(14 * s)
    floors = []
    cy = y
    for fi in range(2):
        fr = pygame.Rect(x - w // 2, cy - fh, w, fh)
        floors.append(fr)
        cy = fr.top
    wall_cols = [(188, 164, 128), (172, 152, 118), (196, 176, 140), (164, 148, 116),
                 (204, 178, 134), (154, 142, 114)]
    wc = wall_cols[seed % len(wall_cols)]
    wd = (wc[0] - 28, wc[1] - 24, wc[2] - 20)
    tc = (46, 34, 22); td = (28, 18, 10)
    _draw_house_shadow(surface, x, y, w)
    # all floors
    for fi, fr in enumerate(floors):
        fh_adj = fr.height - (fnd_h if fi == 0 else 0)
        fy = fr.top
        pygame.draw.rect(surface, wc, (fr.left, fy, fr.width, fh_adj))
        # timber frame
        bw = max(2, int(4 * s))
        pygame.draw.rect(surface, tc, (fr.left, fy, bw, fh_adj))
        pygame.draw.rect(surface, tc, (fr.right - bw, fy, bw, fh_adj))
        pygame.draw.rect(surface, tc, (fr.left, fy, fr.width, bw))
        pygame.draw.rect(surface, tc, (fr.left, fy + fh_adj - bw, fr.width, bw))
        # mid stud
        pygame.draw.rect(surface, tc, (fr.centerx - bw // 2, fy, bw, fh_adj))
        pygame.draw.rect(surface, wd, (fr.left, fy, fr.width, fh_adj), 1)
    # foundation
    fnd = pygame.Rect(floors[0].left, floors[0].bottom - fnd_h, w, fnd_h)
    _draw_house_stone_foundation(surface, fnd, seed)
    # steep roof
    top_fl = floors[-1]
    rh = int(56 * s); rov = int(6 * s)
    roof_cols = [(66, 42, 30), (48, 52, 58), (56, 38, 26),
                 (76, 58, 42), (40, 44, 50)]
    rc = roof_cols[seed % len(roof_cols)]
    rpts = [(top_fl.left - rov, top_fl.top), (top_fl.right + rov, top_fl.top), (x, top_fl.top - rh)]
    pygame.draw.polygon(surface, rc, rpts)
    for i in range(1, 8):
        yl = top_fl.top - int(rh * i / 8)
        hw = int((w // 2 + rov) * (1.0 - i / 8))
        pygame.draw.line(surface, (rc[0] - 12, rc[1] - 8, rc[2] - 6), (x - hw, yl), (x + hw, yl), 1)
    pygame.draw.polygon(surface, (22, 18, 14), rpts, 2)
    # chimney
    _draw_house_chimney(surface, x + int(w * 0.2 * (1 if seed % 2 else -1)),
                        top_fl.top - rh + int(12 * s), max(8, int(10 * s)), max(26, int(38 * s)), seed)
    # windows on each floor
    ww = max(10, int(12 * s)); wh = max(14, int(18 * s))
    lit = seed % 3 != 2
    for fi, fr in enumerate(floors):
        wy = fr.top + int(14 * s)
        if fi == 0:
            # door on ground floor
            dw2 = max(36, int(36 * s)); dh2 = max(50, int(54 * s))
            dx = x - dw2 // 2
            _draw_house_door(surface, dx, fr.bottom - fnd_h - dh2, dw2, dh2, (56, 40, 24), td, seed)
        else:
            _draw_house_window(surface, fr.left + fr.width // 4 - ww // 2, wy, ww, wh, td, lit)
        _draw_house_window(surface, fr.right - fr.width // 4 - ww // 2, wy, ww, wh, td, lit if fi > 0 else (seed % 2 == 0))
    # Weathering on each floor
    for fr in floors:
        _draw_wall_weathering(surface, fr, seed + fr.top, 0.45)
    # Lantern by door
    _draw_house_lantern(surface, x + dw2 // 2 + 3, floors[0].bottom - fnd_h - int(24 * s), s)
    _draw_house_extras(surface, x, y, w, fh * 2, s, seed)
    return fnd


# ── Style 5: Workshop house (open ground floor, living above) ──────────────
def _draw_house_workshop(surface: pygame.Surface, x: int, y: int, s: float, seed: int) -> pygame.Rect:
    w = int(126 * s); h_g = int(64 * s); h_u = int(62 * s)
    fnd_h = int(16 * s)
    gr = pygame.Rect(x - w // 2, y - h_g, w, h_g)
    ur = pygame.Rect(x - w // 2, gr.top - h_u, w, h_u)
    wall_cols = [(194, 178, 148), (182, 168, 138), (202, 186, 156),
                 (212, 194, 160), (174, 162, 136)]
    wc = wall_cols[seed % len(wall_cols)]
    wd = (wc[0] - 24, wc[1] - 22, wc[2] - 18)
    tc = (50, 36, 22); td = (30, 20, 12)
    bw = max(3, int(5 * s))
    _draw_house_shadow(surface, x, y, w + 8)
    # foundation
    fnd = pygame.Rect(gr.left, gr.bottom - fnd_h, w, fnd_h)
    _draw_house_stone_foundation(surface, fnd, seed)
    # ground floor — open front (pillared arcade)
    gw_h = gr.height - fnd_h
    # back wall (dark interior)
    pygame.draw.rect(surface, (28, 24, 18), (gr.left, gr.top, gr.width, gw_h))
    # wooden pillars
    n_pillars = 4
    for pi in range(n_pillars):
        px = gr.left + (pi + 1) * gr.width // (n_pillars + 1)
        pygame.draw.rect(surface, tc, (px - bw, gr.top, bw * 2, gw_h))
        pygame.draw.rect(surface, td, (px - bw, gr.top, bw * 2, gw_h), 1)
        # bracket at top
        pygame.draw.polygon(surface, tc, [(px - bw * 2, gr.top), (px + bw * 2, gr.top),
                                           (px + bw, gr.top + int(8 * s)), (px - bw, gr.top + int(8 * s))])
    # lintel beam
    pygame.draw.rect(surface, tc, (gr.left, gr.top - bw, gr.width, bw * 2))
    pygame.draw.rect(surface, td, (gr.left, gr.top - bw, gr.width, bw * 2), 1)
    # interior details — workbench
    wb_y = gr.bottom - fnd_h - int(16 * s)
    pygame.draw.rect(surface, (54, 40, 24), (gr.left + int(10 * s), wb_y, int(40 * s), int(14 * s)))
    # hanging items inside
    for hi in range(4):
        hix = gr.left + int(20 * s) + hi * int(24 * s)
        pygame.draw.line(surface, (78, 62, 38), (hix, gr.top + int(6 * s)), (hix, gr.top + int(20 * s)), 1)
        pygame.draw.circle(surface, (96, 76, 48), (hix, gr.top + int(20 * s)), max(2, int(3 * s)))
    # upper floor (living quarters — timber framed)
    pygame.draw.rect(surface, wc, ur); pygame.draw.rect(surface, wd, ur, 1)
    # timber frame
    pygame.draw.rect(surface, tc, (ur.left, ur.top, bw, ur.height))
    pygame.draw.rect(surface, tc, (ur.right - bw, ur.top, bw, ur.height))
    pygame.draw.rect(surface, tc, (ur.left, ur.top, ur.width, bw))
    pygame.draw.rect(surface, tc, (ur.left, ur.bottom - bw, ur.width, bw))
    mid_x = ur.centerx - bw // 2
    pygame.draw.rect(surface, tc, (mid_x, ur.top, bw, ur.height))
    # cross braces
    pygame.draw.line(surface, tc, (ur.left + bw, ur.top + bw), (mid_x, ur.bottom - bw), bw)
    pygame.draw.line(surface, tc, (mid_x + bw, ur.top + bw), (ur.right - bw, ur.bottom - bw), bw)
    # windows
    ww = max(12, int(16 * s)); wh = max(16, int(22 * s))
    lit = seed % 3 != 0
    _draw_house_window(surface, ur.left + ur.width // 4 - ww // 2, ur.top + int(16 * s), ww, wh, td, lit)
    _draw_house_window(surface, ur.right - ur.width // 4 - ww // 2, ur.top + int(16 * s), ww, wh, td, lit)
    # roof — gambrel
    rh = int(66 * s); rov = int(10 * s)
    roof_cols = [(108, 42, 32), (54, 58, 64), (68, 44, 30),
                 (94, 58, 38), (60, 50, 40)]
    rc = roof_cols[(seed // 2) % len(roof_cols)]
    # lower slopes (steeper)
    mid_rh = rh * 2 // 3
    lsl = (ur.left - rov, ur.top)
    lsr = (ur.right + rov, ur.top)
    lml = (ur.left + int(8 * s), ur.top - mid_rh)
    lmr = (ur.right - int(8 * s), ur.top - mid_rh)
    pygame.draw.polygon(surface, rc, [lsl, lsr, lmr, lml])
    # upper slopes (gentler)
    pygame.draw.polygon(surface, (rc[0] + 6, rc[1] + 4, rc[2] + 2), [lml, lmr, (x, ur.top - rh)])
    # tile lines
    for i in range(1, 10):
        frac = i / 10
        if frac < 0.67:
            yl = int(ur.top - frac * rh * 1.5)
            hw = int((ur.width // 2 + rov) * (1.0 - frac * 0.3))
        else:
            yl = int(ur.top - mid_rh - (frac - 0.67) * rh)
            hw = int((ur.width // 2 - int(8 * s)) * (1.0 - (frac - 0.67) * 3))
        hw = max(0, hw)
        pygame.draw.line(surface, (rc[0] - 14, rc[1] - 8, rc[2] - 6), (x - hw, yl), (x + hw, yl), 1)
    pygame.draw.polygon(surface, (22, 18, 14), [lsl, lsr, lmr, lml], 2)
    pygame.draw.polygon(surface, (22, 18, 14), [lml, lmr, (x, ur.top - rh)], 2)
    # chimney
    _draw_house_chimney(surface, x + int(w * 0.28 * (1 if seed % 2 else -1)),
                        ur.top - rh + int(10 * s), max(10, int(13 * s)), max(30, int(44 * s)), seed)
    # trade sign hanging from bracket
    sign_x = gr.right + int(4 * s)
    sign_y = gr.top + int(10 * s)
    pygame.draw.line(surface, (58, 46, 28), (gr.right, sign_y), (sign_x + int(18 * s), sign_y), 2)
    sb = pygame.Rect(sign_x, sign_y + 4, int(22 * s), int(16 * s))
    pygame.draw.rect(surface, (62, 48, 28), sb, border_radius=2)
    pygame.draw.rect(surface, (88, 68, 40), sb, 1, border_radius=2)
    # Workshop weathering — heavier on the open ground floor
    _draw_wall_weathering(surface, pygame.Rect(gr.left, gr.top, gr.width, gr.height - fnd_h), seed, 0.55)
    _draw_wall_weathering(surface, ur, seed + 1, 0.35)
    # Lantern on pillar
    _draw_house_lantern(surface, gr.left + int(12 * s), gr.top + int(6 * s), s)
    # Medieval extras (ivy, signs, shutters, etc.)
    _draw_house_extras(surface, x, y, w, h_g + h_u, s, seed)
    return fnd


def _house_chimney_top(x: int, y: int, scale: float, seed: int) -> Optional[Tuple[int, int]]:
    """Return the world (x, y) of the chimney top for a house, or None if no chimney."""
    s = scale
    style = seed % 6
    rng = random.Random(seed)
    if style == 0:  # Tudor
        if rng.random() >= 0.85:
            return None
        ch_side = -1 if rng.random() < 0.5 else 1
        w_u = int(128 * s); h_u = int(68 * s); h_g = int(60 * s)
        rh = int(78 * s)
        ur_top = y - h_g - h_u
        cx = x + int(w_u * 0.28 * ch_side)
        cy = ur_top - rh + int(18 * s) - 8
        return (cx, cy)
    elif style == 1:  # Stone
        w = int(90 * s); h1 = int(70 * s); h2 = int(64 * s)
        rh = int(70 * s)
        r2_top = y - h1 - h2
        cx = x + int(w * 0.25 * (1 if seed % 2 else -1))
        cy = r2_top - rh + int(16 * s) - 8
        return (cx, cy)
    elif style == 2:  # Cottage
        w = int(120 * s); h = int(72 * s); th_h = int(68 * s)
        wr_top = y - h
        th_top = wr_top - th_h
        cx = x + int(w * 0.3 * (1 if seed % 2 else -1))
        cy = th_top + th_h // 4 - 8
        return (cx, cy)
    elif style == 3:  # Merchant
        w = int(140 * s); h1 = int(66 * s); h2 = int(72 * s)
        rh = int(74 * s)
        r2_top = y - h1 - h2
        bay_side = 1 if seed % 2 else -1
        cx = x + int(w * 0.32 * bay_side)
        cy = r2_top - rh + int(14 * s) - 8
        return (cx, cy)
    elif style == 4:  # Rowhouse
        w = int(72 * s); fh = int(54 * s)
        rh = int(56 * s)
        top_fl_top = y - fh * 2
        cx = x + int(w * 0.2 * (1 if seed % 2 else -1))
        cy = top_fl_top - rh + int(12 * s) - 8
        return (cx, cy)
    else:  # Workshop
        w = int(126 * s); h_g = int(64 * s); h_u = int(62 * s)
        rh = int(66 * s)
        ur_top = y - h_g - h_u
        cx = x + int(w * 0.28 * (1 if seed % 2 else -1))
        cy = ur_top - rh + int(10 * s) - 8
        return (cx, cy)


def draw_house(surface: pygame.Surface, x: int, y: int, scale: float, seed: int) -> pygame.Rect:
    """Dispatch to one of 6 house styles based on seed for variety."""
    style = seed % 6
    if style == 0:
        return _draw_house_tudor(surface, x, y, scale, seed)
    elif style == 1:
        return _draw_house_stone(surface, x, y, scale, seed)
    elif style == 2:
        return _draw_house_cottage(surface, x, y, scale, seed)
    elif style == 3:
        return _draw_house_merchant(surface, x, y, scale, seed)
    elif style == 4:
        return _draw_house_rowhouse(surface, x, y, scale, seed)
    else:
        return _draw_house_workshop(surface, x, y, scale, seed)

def draw_church(surface: pygame.Surface, center_x: int, base_y: int) -> pygame.Rect:  # noqa: C901
    # ══════════════════════════════════════════════════════════════════════════
    # GOTHIC CATHEDRAL — Sangeroasa
    # ══════════════════════════════════════════════════════════════════════════
    cx = center_x

    # ── palette ───────────────────────────────────────────────────────────────
    # Stone — warm-grey limestone, weathered
    S0 = (92, 88, 82)       # base wall
    S1 = (78, 74, 68)       # shadow / recessed
    S2 = (106, 102, 94)     # highlight / trim
    S3 = (62, 58, 54)       # deep shadow
    S4 = (118, 114, 106)    # light trim / capstones
    MO = (48, 44, 40)       # mortar
    # Roof
    R0 = (38, 34, 30)       # slate base
    R1 = (28, 24, 20)       # slate dark
    R2 = (54, 50, 44)       # slate highlight
    RE = (18, 16, 14)       # edge
    # Wood & Iron
    W0 = (44, 34, 26)       # dark wood
    W1 = (66, 52, 38)       # mid wood
    W2 = (82, 66, 48)       # light wood
    IR = (62, 60, 58)       # iron
    IH = (96, 94, 90)       # iron highlight
    # Gold accents
    G0 = (192, 160, 72)     # gold
    G1 = (148, 122, 52)     # dark gold
    G2 = (220, 192, 108)    # light gold
    # Stained glass
    GR = (158, 36, 28)      # red
    GB = (42, 68, 162)      # blue
    GG = (188, 152, 56)     # gold-glass
    GE = (40, 116, 60)      # green
    GP = (98, 46, 142)      # purple
    GW = (180, 170, 148)    # white/light
    GK = (22, 20, 26)       # glass background (near-black)
    # Weathering
    WE = (56, 68, 52)       # moss/lichen green
    WS = (72, 68, 62)       # water stain

    # ── dimensions ────────────────────────────────────────────────────────────
    nave_w, nave_h = 360, 220
    nave_top = base_y - nave_h
    nave = pygame.Rect(cx - nave_w // 2, nave_top, nave_w, nave_h)

    # Transept wings
    trans_w = 56
    trans_ext = 48  # how far they extend past the aisles
    trans_y = nave_top + 60
    trans_h = nave_h - 60

    aisle_w = 54
    aisle_top = nave_top + 38
    aisle_h = nave_h - 38
    aisle_l = pygame.Rect(nave.left - aisle_w, aisle_top, aisle_w, aisle_h)
    aisle_r = pygame.Rect(nave.right, aisle_top, aisle_w, aisle_h)

    trans_l = pygame.Rect(aisle_l.left - trans_ext, trans_y, trans_ext, trans_h)
    trans_r = pygame.Rect(aisle_r.right, trans_y, trans_ext, trans_h)

    tower_w, tower_h = 126, 178
    tower_top = nave_top - tower_h
    tower = pygame.Rect(cx - tower_w // 2, tower_top, tower_w, tower_h)

    spire_h = 130
    spire_tip = tower_top - spire_h
    cross_h = 32

    # Apse (semicircular chancel behind nave — drawn as visible top arc)
    apse_r_x = 80
    apse_cy = nave_top + 28

    # total bbox
    total = pygame.Rect(
        trans_l.left - 16, spire_tip - cross_h - 6,
        (trans_r.right - trans_l.left) + 32,
        base_y - (spire_tip - cross_h - 6) + 28,
    )

    # ── helpers ───────────────────────────────────────────────────────────────
    def _clr(base: tuple, dv: int) -> tuple:
        return tuple(max(0, min(255, base[i] + dv)) for i in range(3))

    def _stone_fill(rect: pygame.Rect, base: tuple, rh: int = 13, bw: int = 26, weather: bool = True) -> None:
        pygame.draw.rect(surface, base, rect)
        row = 0
        for ry in range(rect.top, rect.bottom, rh):
            off = (bw // 2) if row % 2 else 0
            for bx_i in range(rect.left + off, rect.right, bw):
                bww = min(bw - 1, rect.right - bx_i - 1)
                bhh = min(rh - 1, rect.bottom - ry - 1)
                if bww < 3 or bhh < 3:
                    continue
                v = ((bx_i * 7 + ry * 13) % 13) - 6
                c = _clr(base, v)
                pygame.draw.rect(surface, c, (bx_i, ry, bww, bhh))
                pygame.draw.rect(surface, MO, (bx_i, ry, bww, bhh), 1)
            row += 1
        if weather:
            # Subtle vertical water stains
            for ws_x in range(rect.left + 14, rect.right - 8, 37):
                ws_x2 = ws_x + ((ws_x * 3 + rect.top * 7) % 5)
                ws_len = 18 + (ws_x * 11 + rect.top) % 28
                ws_y = rect.top + (ws_x * 3) % 20
                for dy in range(min(ws_len, rect.bottom - ws_y)):
                    a = max(0, 40 - dy * 2)
                    if a > 0:
                        pygame.draw.line(surface, _clr(WS, -(dy % 4)), (ws_x2, ws_y + dy), (ws_x2, ws_y + dy), 1)

    def _lancet(cx_a: int, top_y: int, hw: int, h: int, fill: tuple, outline: tuple, lw: int = 1) -> list:
        """Gothic pointed lancet arch — returns outline points for reuse."""
        body_top = top_y + int(hw * 0.7)
        bot_y = top_y + h
        # straight rect body
        pygame.draw.rect(surface, fill, (cx_a - hw, body_top, hw * 2, bot_y - body_top))
        # pointed arch via smooth curve
        pts = []
        seg = 18
        for i in range(seg + 1):
            t = i / seg
            a = math.pi * t
            # two offset circles meeting at a point
            if t <= 0.5:
                ax = cx_a - hw + hw * (1 - math.cos(a * 1.0))
                ay = body_top - hw * 0.92 * math.sin(a * 1.0)
            else:
                ax = cx_a + hw - hw * (1 + math.cos(a * 1.0))
                ay = body_top - hw * 0.92 * math.sin(a * 1.0)
            pts.append((int(ax), int(ay)))
        pts.append((cx_a - hw, body_top))
        if len(pts) >= 3:
            pygame.draw.polygon(surface, fill, pts)
            pygame.draw.polygon(surface, outline, pts, lw)
        # side lines
        pygame.draw.line(surface, outline, (cx_a - hw, body_top), (cx_a - hw, bot_y), lw)
        pygame.draw.line(surface, outline, (cx_a + hw, body_top), (cx_a + hw, bot_y), lw)
        pygame.draw.line(surface, outline, (cx_a - hw, bot_y), (cx_a + hw, bot_y), lw)
        return pts

    def _tracery_circle(cx_t: int, cy_t: int, r: int, col: tuple) -> None:
        pygame.draw.circle(surface, col, (cx_t, cy_t), r)
        pygame.draw.circle(surface, MO, (cx_t, cy_t), r, 1)
        # inner quatrefoil hint
        for a_off in range(4):
            aa = math.pi / 4 + math.pi / 2 * a_off
            px = cx_t + int(math.cos(aa) * r * 0.5)
            py = cy_t + int(math.sin(aa) * r * 0.5)
            pygame.draw.circle(surface, _clr(col, 18), (px, py), max(1, r // 3))
            pygame.draw.circle(surface, MO, (px, py), max(1, r // 3), 1)

    def _gargoyle(gx: int, gy: int, facing: int) -> None:
        """Small gargoyle/grotesque. facing: -1=left, 1=right."""
        d = facing
        # body
        body_pts = [
            (gx, gy), (gx + d * 18, gy - 3),
            (gx + d * 24, gy - 8), (gx + d * 22, gy + 2),
            (gx + d * 16, gy + 6), (gx, gy + 4),
        ]
        pygame.draw.polygon(surface, S1, body_pts)
        pygame.draw.polygon(surface, S3, body_pts, 1)
        # head
        hx, hy = gx + d * 24, gy - 6
        pygame.draw.circle(surface, S1, (hx, hy), 5)
        pygame.draw.circle(surface, S3, (hx, hy), 5, 1)
        # jaw / open mouth
        pygame.draw.line(surface, S3, (hx + d * 3, hy), (hx + d * 8, hy + 2), 2)
        pygame.draw.line(surface, S3, (hx + d * 3, hy + 2), (hx + d * 8, hy + 2), 1)
        # eye
        pygame.draw.circle(surface, (30, 28, 26), (hx + d * 1, hy - 2), 1)
        # wing stub
        wing = [(gx + d * 6, gy - 2), (gx + d * 10, gy - 14), (gx + d * 16, gy - 6)]
        pygame.draw.polygon(surface, _clr(S1, -8), wing)
        pygame.draw.polygon(surface, S3, wing, 1)

    def _pinnacle(px: int, py: int, w: int = 10, h: int = 28) -> None:
        """Small ornate pinnacle with crockets."""
        hw = w // 2
        # shaft
        pygame.draw.rect(surface, S2, (px - hw, py, w, h))
        pygame.draw.rect(surface, MO, (px - hw, py, w, h), 1)
        # cap / pyramid
        pygame.draw.polygon(surface, S4, [(px - hw - 2, py), (px + hw + 2, py), (px, py - h // 2)])
        pygame.draw.polygon(surface, MO, [(px - hw - 2, py), (px + hw + 2, py), (px, py - h // 2)], 1)
        # crockets (little knobs on edges)
        for cr in range(3):
            ct = (cr + 1) / 4
            cy_c = py - int(h // 2 * ct)
            for side in (-1, 1):
                crx = px + side * int((hw + 2) * (1 - ct))
                pygame.draw.circle(surface, S4, (crx, cy_c), 2)

    def _stained_glass_window(wx: int, wy: int, hw: int, h: int, colors: list, divisions: int = 3) -> None:
        """Ornate stained-glass lancet window with tracery."""
        _lancet(wx, wy, hw, h, GK, S3, 1)
        # Glass panels
        panel_h = (h - hw) // divisions
        glass_top = wy + int(hw * 0.8)
        for d in range(divisions):
            py_g = glass_top + d * panel_h
            ph = min(panel_h - 1, wy + h - py_g - 1)
            if ph < 3:
                continue
            gc = colors[d % len(colors)]
            pygame.draw.rect(surface, gc, (wx - hw + 3, py_g, hw * 2 - 6, ph))
            # Diamond leading pattern
            for ly in range(py_g + 4, py_g + ph - 2, 8):
                for lx_off in range(-hw + 6, hw - 4, 8):
                    lx = wx + lx_off
                    diamond = [(lx, ly - 3), (lx + 3, ly), (lx, ly + 3), (lx - 3, ly)]
                    pygame.draw.polygon(surface, _clr(gc, 16), diamond)
                    pygame.draw.polygon(surface, (20, 18, 16), diamond, 1)
        # Mullion
        pygame.draw.line(surface, S3, (wx, wy + int(hw * 0.5)), (wx, wy + h - 2), 1)
        # Tracery at top
        _tracery_circle(wx, wy + int(hw * 0.55), max(3, hw // 3), colors[0])
        # Stone surround
        _lancet(wx, wy, hw + 2, h + 2, None, S2, 2)  # outer frame line only
        # Sill
        pygame.draw.rect(surface, S4, (wx - hw - 2, wy + h, hw * 2 + 4, 3))

    # Override _lancet for outline-only mode
    _lancet_orig = _lancet
    def _lancet(cx_a, top_y, hw, h, fill, outline, lw=1):
        if fill is None:
            # outline only
            body_top = top_y + int(hw * 0.7)
            bot_y = top_y + h
            pts = []
            seg = 18
            for i in range(seg + 1):
                t = i / seg
                a = math.pi * t
                if t <= 0.5:
                    ax = cx_a - hw + hw * (1 - math.cos(a * 1.0))
                    ay = body_top - hw * 0.92 * math.sin(a * 1.0)
                else:
                    ax = cx_a + hw - hw * (1 + math.cos(a * 1.0))
                    ay = body_top - hw * 0.92 * math.sin(a * 1.0)
                pts.append((int(ax), int(ay)))
            pts.append((cx_a - hw, body_top))
            if len(pts) >= 3:
                pygame.draw.polygon(surface, outline, pts, lw)
            pygame.draw.line(surface, outline, (cx_a - hw, body_top), (cx_a - hw, bot_y), lw)
            pygame.draw.line(surface, outline, (cx_a + hw, body_top), (cx_a + hw, bot_y), lw)
            pygame.draw.line(surface, outline, (cx_a - hw, bot_y), (cx_a + hw, bot_y), lw)
            return pts
        return _lancet_orig(cx_a, top_y, hw, h, fill, outline, lw)

    # ══════════════════════════════════════════════════════════════════════════
    # GROUND SHADOW
    # ══════════════════════════════════════════════════════════════════════════
    sh_surf = pygame.Surface((500, 30), pygame.SRCALPHA)
    pygame.draw.ellipse(sh_surf, (0, 0, 0, 50), (0, 0, 500, 30))
    surface.blit(sh_surf, (cx - 250, base_y - 6))

    # ══════════════════════════════════════════════════════════════════════════
    # APSE (rear chancel, partially visible behind nave roof)
    # ══════════════════════════════════════════════════════════════════════════
    apse_rect = pygame.Rect(cx - apse_r_x, apse_cy - 16, apse_r_x * 2, 44)
    _stone_fill(apse_rect, _clr(S0, -6), rh=10, bw=20, weather=False)
    # rounded top
    pygame.draw.ellipse(surface, _clr(S0, -6), (cx - apse_r_x, apse_cy - 32, apse_r_x * 2, 36))
    pygame.draw.ellipse(surface, MO, (cx - apse_r_x, apse_cy - 32, apse_r_x * 2, 36), 2)
    # conical roof on apse
    apse_roof = [(cx - apse_r_x - 6, apse_cy - 14), (cx + apse_r_x + 6, apse_cy - 14), (cx, apse_cy - 52)]
    pygame.draw.polygon(surface, R0, apse_roof)
    pygame.draw.polygon(surface, RE, apse_roof, 2)
    # apse windows (3 small lancets)
    for i in range(3):
        awx = cx - 36 + i * 36
        _stained_glass_window(awx, apse_cy - 6, 8, 30, [GR, GB, GG][i:] + [GR, GB, GG][:i], divisions=2)

    # ══════════════════════════════════════════════════════════════════════════
    # BELL TOWER
    # ══════════════════════════════════════════════════════════════════════════
    _stone_fill(tower, S0, rh=11, bw=22)
    # Corner pilasters
    pil_w = 8
    for tx in (tower.left, tower.right - pil_w):
        r = pygame.Rect(tx, tower.top, pil_w, tower.height)
        pygame.draw.rect(surface, S1, r)
        pygame.draw.rect(surface, MO, r, 1)
    # String courses (4 bands)
    for frac in (0.0, 0.28, 0.58, 1.0):
        ty = tower.top + int(tower.height * frac)
        pygame.draw.rect(surface, S4, (tower.left - 4, ty - 1, tower.width + 8, 5))
        pygame.draw.line(surface, MO, (tower.left - 4, ty + 4), (tower.right + 4, ty + 4), 1)
    # Clock face
    clock_cy = tower.top + int(tower.height * 0.42)
    pygame.draw.circle(surface, (26, 24, 22), (cx, clock_cy), 18)
    pygame.draw.circle(surface, G0, (cx, clock_cy), 18, 2)
    pygame.draw.circle(surface, G1, (cx, clock_cy), 16, 1)
    # hour markers
    for h_i in range(12):
        ha = math.pi * 2 * h_i / 12 - math.pi / 2
        mx = cx + int(math.cos(ha) * 14)
        my = clock_cy + int(math.sin(ha) * 14)
        pygame.draw.circle(surface, G2, (mx, my), 1)
    # clock hands
    pygame.draw.line(surface, G0, (cx, clock_cy), (cx - 4, clock_cy - 10), 2)
    pygame.draw.line(surface, G2, (cx, clock_cy), (cx + 8, clock_cy + 2), 1)
    pygame.draw.circle(surface, G0, (cx, clock_cy), 2)

    # Belfry openings — twin lancets with dividing column
    belfry_y = tower.top + 14
    for b_side in (-1, 1):
        bx = cx + b_side * 22
        _lancet_orig(bx, belfry_y, 12, 42, GK, S3, 1)
        # Louver slats (angled wooden boards)
        for ly in range(belfry_y + 14, belfry_y + 40, 4):
            pygame.draw.line(surface, W1, (bx - 10, ly), (bx + 10, ly + 2), 2)
            pygame.draw.line(surface, W0, (bx - 10, ly + 2), (bx + 10, ly + 4), 1)
    # Center column between belfry arches
    pygame.draw.rect(surface, S4, (cx - 3, belfry_y + 8, 6, 36))
    pygame.draw.rect(surface, MO, (cx - 3, belfry_y + 8, 6, 36), 1)
    # Column capital
    pygame.draw.rect(surface, S4, (cx - 5, belfry_y + 6, 10, 4))

    # ── bell (visible through openings) ───────────────────────────────────────
    bell_y = belfry_y + 18
    pygame.draw.polygon(surface, (142, 118, 62), [(cx - 8, bell_y), (cx + 8, bell_y), (cx + 12, bell_y + 16), (cx - 12, bell_y + 16)])
    pygame.draw.ellipse(surface, (128, 106, 52), (cx - 12, bell_y + 13, 24, 6))
    pygame.draw.line(surface, G1, (cx, bell_y - 4), (cx, bell_y + 2), 2)
    # clapper
    pygame.draw.line(surface, (80, 72, 56), (cx, bell_y + 10), (cx + 1, bell_y + 18), 2)

    # ══════════════════════════════════════════════════════════════════════════
    # SPIRE with crockets & dormers
    # ══════════════════════════════════════════════════════════════════════════
    sp_l = tower.left - 10
    sp_r = tower.right + 10
    sp_pts = [(sp_l, tower.top + 6), (sp_r, tower.top + 6), (cx, spire_tip)]
    pygame.draw.polygon(surface, R0, sp_pts)
    # Slate tile rows with offset pattern
    for sy in range(spire_tip + 6, tower.top + 4, 5):
        t = (sy - spire_tip) / max(1, tower.top + 4 - spire_tip)
        hw = int((sp_r - sp_l) / 2 * t)
        row_n = (sy - spire_tip) // 5
        off = 4 if row_n % 2 else 0
        for sx in range(cx - hw + off, cx + hw - 2, 8):
            sw = min(7, cx + hw - sx)
            v = 30 + ((sx * 3 + sy * 7) % 14)
            pygame.draw.rect(surface, (v, v - 2, v - 4), (sx, sy, sw, 5))
    pygame.draw.polygon(surface, RE, sp_pts, 2)
    # Ridge lines (4 edges to simulate octagonal spire)
    for ridge_off in (-0.3, 0.3):
        rx = cx + int((sp_r - sp_l) / 2 * ridge_off)
        rx_top = cx + int(2 * ridge_off)
        pygame.draw.line(surface, R2, (rx, tower.top + 6), (rx_top, spire_tip), 1)
    # Crockets along ridges
    for ci in range(1, 8):
        ct = ci / 8
        cry = spire_tip + int((tower.top + 4 - spire_tip) * ct)
        chw = int((sp_r - sp_l) / 2 * ct)
        for side in (-1, 1):
            crx = cx + side * chw
            pygame.draw.circle(surface, S4, (crx, cry), 3)
            pygame.draw.circle(surface, MO, (crx, cry), 3, 1)
    # Spire dormers (2 small triangular windows)
    for d_side in (-1, 1):
        dt = 0.45
        dy = spire_tip + int((tower.top + 4 - spire_tip) * dt)
        dhw = int((sp_r - sp_l) / 2 * dt)
        dx = cx + d_side * int(dhw * 0.5)
        dm_pts = [(dx - 8, dy + 10), (dx + 8, dy + 10), (dx, dy - 4)]
        pygame.draw.polygon(surface, R0, dm_pts)
        pygame.draw.polygon(surface, RE, dm_pts, 1)
        # tiny window in dormer
        pygame.draw.rect(surface, GK, (dx - 3, dy + 1, 6, 8))
        pygame.draw.rect(surface, GG, (dx - 2, dy + 2, 4, 6))
        pygame.draw.rect(surface, S3, (dx - 3, dy + 1, 6, 8), 1)

    # ── cross finial ──────────────────────────────────────────────────────────
    # Orb
    pygame.draw.circle(surface, G0, (cx, spire_tip), 5)
    pygame.draw.circle(surface, G1, (cx, spire_tip), 5, 1)
    pygame.draw.circle(surface, G2, (cx - 1, spire_tip - 2), 2)
    # Cross
    pygame.draw.rect(surface, G0, (cx - 2, spire_tip - cross_h, 4, cross_h - 4))
    pygame.draw.rect(surface, G0, (cx - 11, spire_tip - cross_h + 8, 22, 3))
    # Flared cross ends
    for end_x in (cx - 11, cx + 9):
        pygame.draw.rect(surface, G2, (end_x, spire_tip - cross_h + 6, 3, 7))
    pygame.draw.rect(surface, G2, (cx - 1, spire_tip - cross_h - 2, 2, 5))
    # subtle gold gleam
    pygame.draw.line(surface, G2, (cx - 1, spire_tip - cross_h + 1), (cx - 1, spire_tip - 6), 1)

    # ══════════════════════════════════════════════════════════════════════════
    # TRANSEPT WINGS
    # ══════════════════════════════════════════════════════════════════════════
    for tr_rect, side in ((trans_l, -1), (trans_r, 1)):
        _stone_fill(tr_rect, _clr(S0, -4), rh=11, bw=22)
        pygame.draw.rect(surface, MO, tr_rect, 2)
        # Gable roof on transept
        gable_peak = tr_rect.top - 30
        if side == -1:
            gbl = [(tr_rect.left - 4, tr_rect.top + 4), (tr_rect.right + 4, tr_rect.top + 4), (tr_rect.left + tr_rect.width // 2, gable_peak)]
        else:
            gbl = [(tr_rect.left - 4, tr_rect.top + 4), (tr_rect.right + 4, tr_rect.top + 4), (tr_rect.left + tr_rect.width // 2, gable_peak)]
        pygame.draw.polygon(surface, R0, gbl)
        pygame.draw.polygon(surface, RE, gbl, 2)
        # Transept rose window (small)
        tr_cx = tr_rect.left + tr_rect.width // 2
        tr_cy = tr_rect.top + 28
        tr_rr = 14
        pygame.draw.circle(surface, GK, (tr_cx, tr_cy), tr_rr)
        for pi in range(6):
            pa = math.pi * 2 * pi / 6
            pa2 = math.pi * 2 * (pi + 0.5) / 6
            pc = [GR, GB, GG, GP, GE, GW][pi]
            pp1 = (tr_cx + int(math.cos(pa) * 4), tr_cy + int(math.sin(pa) * 4))
            pp2 = (tr_cx + int(math.cos(pa) * (tr_rr - 2)), tr_cy + int(math.sin(pa) * (tr_rr - 2)))
            pp3 = (tr_cx + int(math.cos(pa2) * (tr_rr - 2)), tr_cy + int(math.sin(pa2) * (tr_rr - 2)))
            pp4 = (tr_cx + int(math.cos(pa2) * 4), tr_cy + int(math.sin(pa2) * 4))
            pygame.draw.polygon(surface, pc, [pp1, pp2, pp3, pp4])
        pygame.draw.circle(surface, S2, (tr_cx, tr_cy), tr_rr, 2)
        pygame.draw.circle(surface, GG, (tr_cx, tr_cy), 4)
        for pi in range(6):
            pa = math.pi * 2 * pi / 6
            pygame.draw.line(surface, S3, (tr_cx + int(math.cos(pa) * 3), tr_cy + int(math.sin(pa) * 3)),
                             (tr_cx + int(math.cos(pa) * (tr_rr - 1)), tr_cy + int(math.sin(pa) * (tr_rr - 1))), 1)
        # Transept lancet window below rose
        _stained_glass_window(tr_cx, tr_cy + 22, 9, 36, [GR, GB, GP], divisions=2)
        # Small pinnacle on transept gable
        _pinnacle(tr_cx, gable_peak - 2, 8, 20)

    # ══════════════════════════════════════════════════════════════════════════
    # SIDE AISLES
    # ══════════════════════════════════════════════════════════════════════════
    for aisle, side in ((aisle_l, -1), (aisle_r, 1)):
        _stone_fill(aisle, _clr(S0, -8), rh=11, bw=20)
        pygame.draw.rect(surface, MO, aisle, 2)
        # Lean-to roof
        if side == -1:
            rp = [(aisle.left - 6, aisle.top + 8), (aisle.right + 6, aisle.top - 12), (aisle.right + 6, aisle.top + 8)]
        else:
            rp = [(aisle.left - 6, aisle.top - 12), (aisle.right + 6, aisle.top + 8), (aisle.left - 6, aisle.top + 8)]
        pygame.draw.polygon(surface, R0, rp)
        # tile rows on lean-to
        for ry in range(aisle.top - 8, aisle.top + 8, 4):
            pygame.draw.line(surface, _clr(R0, ((ry * 3) % 8)), (aisle.left - 4, ry), (aisle.right + 4, ry), 1)
        pygame.draw.polygon(surface, RE, rp, 2)
        # Aisle windows (4 small lancets)
        aw_n = 4
        for i in range(aw_n):
            awy = aisle.top + 18 + i * ((aisle.height - 30) // aw_n)
            awx = aisle.left + aisle.width // 2
            colors_a = [[GR, GG], [GB, GE], [GP, GR], [GG, GB]][i % 4]
            _stained_glass_window(awx, awy, 7, 28, colors_a, divisions=2)
        # Moss on lower walls
        for mx in range(aisle.left + 4, aisle.right - 4, 9):
            my = aisle.bottom - 3 - (mx * 3) % 8
            mw = 4 + (mx * 7) % 5
            pygame.draw.rect(surface, WE, (mx, my, mw, aisle.bottom - my))

    # ══════════════════════════════════════════════════════════════════════════
    # FLYING BUTTRESSES (behind nave facade)
    # ══════════════════════════════════════════════════════════════════════════
    for side in (-1, 1):
        for i in range(4):
            bx_outer = cx + side * (nave_w // 2 + aisle_w + 6)
            bx_inner = cx + side * (nave_w // 2 + 6)
            by = nave_top + 36 + i * 48
            arc_pts = []
            for ai in range(9):
                at = ai / 8
                ax = bx_outer + (bx_inner - bx_outer) * at
                ay = by + 4 - math.sin(at * math.pi) * 18
                arc_pts.append((int(ax), int(ay)))
            for ai in range(8, -1, -1):
                at = ai / 8
                ax = bx_outer + (bx_inner - bx_outer) * at
                ay = by + 10 - math.sin(at * math.pi) * 14
                arc_pts.append((int(ax), int(ay)))
            if len(arc_pts) >= 3:
                pygame.draw.polygon(surface, S1, arc_pts)
                pygame.draw.polygon(surface, MO, arc_pts, 1)
            pier_x = bx_outer - 5 if side == -1 else bx_outer - 3
            pier_r = pygame.Rect(pier_x, by + 4, 8, base_y - by - 4)
            _stone_fill(pier_r, S1, rh=8, bw=8, weather=False)
            pygame.draw.rect(surface, MO, pier_r, 1)
            _pinnacle(pier_r.centerx, by - 6, 8, 22)
            if i % 2 == 0:
                _gargoyle(bx_outer + side * 2, by - 8, side)

    # ══════════════════════════════════════════════════════════════════════════
    # MAIN ROOF (drawn BEHIND the facade gable)
    # ══════════════════════════════════════════════════════════════════════════
    overhang = 18
    peak_y = nave_top - 82
    # Roof slopes visible on left and right edges only (the body is behind the gable wall)
    for side in (-1, 1):
        edge_x = cx + side * (nave_w // 2 + overhang)
        inner_x = cx + side * (nave_w // 2 - 6)
        slope_pts = [(edge_x, nave_top + 10), (inner_x, nave_top + 10), (cx + side * 10, peak_y + 8)]
        pygame.draw.polygon(surface, R0, slope_pts)
        for ry in range(peak_y + 8, nave_top + 8, 5):
            t = (ry - peak_y) / max(1, nave_top + 8 - peak_y)
            x1 = int(edge_x + (cx + side * 10 - edge_x) * (1 - t))
            x2 = int(inner_x + (cx + side * 10 - inner_x) * (1 - t))
            if side == -1:
                x1, x2 = min(x1, x2), max(x1, x2)
            else:
                x1, x2 = min(x1, x2), max(x1, x2)
            v = 32 + ((ry * 7) % 10)
            pygame.draw.line(surface, (v, v - 2, v - 4), (x1, ry), (x2, ry), 1)
        pygame.draw.polygon(surface, RE, slope_pts, 2)

    # ══════════════════════════════════════════════════════════════════════════
    # FACADE GABLE WALL (the grand front face — on top of everything)
    # ══════════════════════════════════════════════════════════════════════════
    # The gable = rectangular nave + triangular pediment above
    gable_hw = nave_w // 2 - 4
    gable_top = peak_y + 6  # the tip of the gable triangle

    # Triangular pediment
    pediment = [(cx - gable_hw, nave_top + 6), (cx + gable_hw, nave_top + 6), (cx, gable_top)]
    _stone_fill(nave, S0)  # nave rectangle
    pygame.draw.polygon(surface, S0, pediment)  # pediment triangle
    # Stone texture on pediment
    for ry in range(gable_top + 4, nave_top + 6, 13):
        t = (ry - gable_top) / max(1, nave_top + 6 - gable_top)
        hw_r = int(gable_hw * t)
        for bx in range(cx - hw_r + ((ry // 13 % 2) * 13), cx + hw_r - 2, 26):
            bww = min(25, cx + hw_r - bx)
            if bww < 3:
                continue
            v = ((bx * 7 + ry * 13) % 13) - 6
            c = _clr(S0, v)
            pygame.draw.rect(surface, c, (bx, ry, bww, 12))
            pygame.draw.rect(surface, MO, (bx, ry, bww, 12), 1)

    # Pediment outline
    pygame.draw.polygon(surface, MO, pediment, 2)
    # Rake moulding (decorative edge along gable slope)
    pygame.draw.line(surface, S4, (cx - gable_hw - 2, nave_top + 6), (cx, gable_top - 2), 3)
    pygame.draw.line(surface, S4, (cx + gable_hw + 2, nave_top + 6), (cx, gable_top - 2), 3)
    # Apex cross on pediment
    pygame.draw.rect(surface, G0, (cx - 2, gable_top - 18, 4, 16))
    pygame.draw.rect(surface, G0, (cx - 8, gable_top - 14, 16, 3))

    # Nave rect outline
    pygame.draw.rect(surface, MO, nave, 2)

    # ── wall buttresses on facade ─────────────────────────────────────────────
    for boff in (-148, -74, 74, 148):
        bx = cx + boff
        br = pygame.Rect(bx - 8, nave_top + 16, 16, nave_h - 16)
        pygame.draw.rect(surface, S1, br)
        pygame.draw.rect(surface, MO, br, 1)
        for sb in range(3):
            sy_sb = nave_top + 16 + sb * 24
            pygame.draw.rect(surface, S2, (bx - 9 + sb * 2, sy_sb, 18 - sb * 4, 3))
        _pinnacle(bx, nave_top - 2, 10, 26)

    # ── eave moulding + corbel table ─────────────────────────────────────────
    pygame.draw.rect(surface, S4, (nave.left - overhang, nave_top + 8, nave_w + 2 * overhang, 4))
    pygame.draw.line(surface, MO, (nave.left - overhang, nave_top + 12), (nave.right + overhang, nave_top + 12), 1)
    for cb_x in range(nave.left - overhang + 6, nave.right + overhang - 4, 14):
        pygame.draw.rect(surface, S2, (cb_x, nave_top + 12, 6, 5))
        pygame.draw.arc(surface, MO, (cb_x - 1, nave_top + 14, 8, 6), 0, math.pi, 1)

    # ══════════════════════════════════════════════════════════════════════════
    # ROSE WINDOW — Grand 12-petal (larger, centered on facade)
    # ══════════════════════════════════════════════════════════════════════════
    rose_cx, rose_cy = cx, nave_top + 62
    rose_r = 52
    # Deep stone recess
    pygame.draw.circle(surface, S3, (rose_cx, rose_cy), rose_r + 6)
    pygame.draw.circle(surface, S1, (rose_cx, rose_cy), rose_r + 3)
    pygame.draw.circle(surface, GK, (rose_cx, rose_cy), rose_r)
    # 12 petals — outer ring
    petal_cols = [GR, GB, GG, GE, GP, GW, GR, GB, GG, GE, GP, GW]
    for ring_r_inner, ring_r_outer, bright in ((22, rose_r - 5, 0), (10, 20, 14)):
        for i in range(12):
            a1 = math.pi * 2 * i / 12
            a2 = math.pi * 2 * (i + 1) / 12
            amid = (a1 + a2) / 2
            p_pts = [
                (rose_cx + int(math.cos(a1) * ring_r_inner), rose_cy + int(math.sin(a1) * ring_r_inner)),
                (rose_cx + int(math.cos(a1) * ring_r_outer), rose_cy + int(math.sin(a1) * ring_r_outer)),
                (rose_cx + int(math.cos(amid) * (ring_r_outer + 2)), rose_cy + int(math.sin(amid) * (ring_r_outer + 2))),
                (rose_cx + int(math.cos(a2) * ring_r_outer), rose_cy + int(math.sin(a2) * ring_r_outer)),
                (rose_cx + int(math.cos(a2) * ring_r_inner), rose_cy + int(math.sin(a2) * ring_r_inner)),
            ]
            c = _clr(petal_cols[i], bright)
            pygame.draw.polygon(surface, c, p_pts)
            pygame.draw.polygon(surface, (16, 14, 12), p_pts, 1)
    # Tracery spokes
    for i in range(12):
        a = math.pi * 2 * i / 12
        pygame.draw.line(surface, S2,
                         (rose_cx + int(math.cos(a) * 8), rose_cy + int(math.sin(a) * 8)),
                         (rose_cx + int(math.cos(a) * (rose_r - 2)), rose_cy + int(math.sin(a) * (rose_r - 2))), 2)
    # Tracery circles
    for i in range(12):
        a = math.pi * 2 * (i + 0.5) / 12
        tcx = rose_cx + int(math.cos(a) * (rose_r * 0.7))
        tcy = rose_cy + int(math.sin(a) * (rose_r * 0.7))
        _tracery_circle(tcx, tcy, 5, petal_cols[i])
    # Stone rings
    pygame.draw.circle(surface, S4, (rose_cx, rose_cy), rose_r, 5)
    pygame.draw.circle(surface, MO, (rose_cx, rose_cy), rose_r + 1, 1)
    pygame.draw.circle(surface, S2, (rose_cx, rose_cy), 21, 2)
    # Center medallion
    pygame.draw.circle(surface, GG, (rose_cx, rose_cy), 9)
    pygame.draw.circle(surface, G0, (rose_cx, rose_cy), 9, 2)
    pygame.draw.line(surface, G1, (rose_cx, rose_cy - 5), (rose_cx, rose_cy + 5), 1)
    pygame.draw.line(surface, G1, (rose_cx - 5, rose_cy), (rose_cx + 5, rose_cy), 1)

    # ══════════════════════════════════════════════════════════════════════════
    # FACADE WINDOWS — Large stained glass lancets flanking rose window
    # ══════════════════════════════════════════════════════════════════════════
    # Upper tier: tall lancets between buttresses
    glass_cycle = [GR, GB, GG, GP, GE, GW]
    upper_positions = []
    for boff in (-148, -74, 74, 148):
        upper_positions.append(cx + boff)
    # Pairs of lancets flanking each buttress
    for i, bx in enumerate(upper_positions):
        for side_off in (-30, 18):
            wx = bx + side_off
            if abs(wx - cx) < 58:
                continue
            if wx < nave.left + 14 or wx > nave.right - 14:
                continue
            wy = nave_top + 22
            ci = (i + (1 if side_off > 0 else 0)) % 6
            _stained_glass_window(wx, wy, 11, 68, [glass_cycle[ci], glass_cycle[(ci + 2) % 6], glass_cycle[(ci + 4) % 6]], divisions=3)

    # Lower tier: shorter windows below the string course
    mid_y = nave_top + nave_h // 2
    for i, bx in enumerate(upper_positions):
        for side_off in (-30, 18):
            wx = bx + side_off
            if abs(wx - cx) < 62:
                continue
            if wx < nave.left + 14 or wx > nave.right - 14:
                continue
            wy = nave_top + 112
            ci = (i + 1 + (1 if side_off > 0 else 0)) % 6
            _stained_glass_window(wx, wy, 10, 52, [glass_cycle[ci], glass_cycle[(ci + 3) % 6]], divisions=2)

    # ── horizontal string course at mid-height ────────────────────────────────
    pygame.draw.rect(surface, S2, (nave.left - 2, nave_top + 104, nave_w + 4, 3))
    pygame.draw.line(surface, MO, (nave.left - 2, nave_top + 107), (nave.right + 2, nave_top + 107), 1)

    # ── decorative blind arcading on lower wall (below windows) ───────────────
    arcade_y = nave_top + 170
    for ax in range(nave.left + 16, nave.right - 16, 32):
        if abs(ax + 16 - cx) < 50:
            continue  # skip behind door
        # Small blind arch
        _lancet_orig(ax + 16, arcade_y, 12, 28, S1, MO, 1)
        # Tiny column
        pygame.draw.rect(surface, S2, (ax + 14, arcade_y + 12, 4, 18))
        pygame.draw.circle(surface, S4, (ax + 16, arcade_y + 12), 3)  # capital

    # ══════════════════════════════════════════════════════════════════════════
    # ENTRANCE PORTAL — Triple archivolt with tympanum
    # ══════════════════════════════════════════════════════════════════════════
    door_w, door_h = 80, 118
    door_top = base_y - door_h
    door_r = pygame.Rect(cx - door_w // 2, door_top, door_w, door_h)

    # Recessed archivolt mouldings (5 layers)
    for depth in range(5):
        d = depth * 6
        phw = door_w // 2 + 28 - d
        pt = door_top - 38 + d * 3
        ph = door_h + 38 - d * 3
        shade = S4[0] - depth * 10
        c = (max(30, shade), max(28, shade - 4), max(26, shade - 8))
        _lancet_orig(cx, pt, phw, ph, c, MO, 2 if depth == 0 else 1)

    # Tympanum (carved relief area above door)
    tymp_y = door_top - 10
    tymp_hw = door_w // 2 + 4
    _lancet_orig(cx, tymp_y - 16, tymp_hw, 24, (48, 42, 38), S3, 1)
    # Carved scene in tympanum — cross with rays
    pygame.draw.rect(surface, G0, (cx - 2, tymp_y - 12, 4, 14))
    pygame.draw.rect(surface, G0, (cx - 8, tymp_y - 8, 16, 3))
    # Radiant lines
    for ri in range(8):
        ra = math.pi * 2 * ri / 8
        rx1 = cx + int(math.cos(ra) * 6)
        ry1 = tymp_y - 5 + int(math.sin(ra) * 6)
        rx2 = cx + int(math.cos(ra) * 12)
        ry2 = tymp_y - 5 + int(math.sin(ra) * 9)
        pygame.draw.line(surface, G1, (rx1, ry1), (rx2, ry2), 1)

    # Door panels — heavy oak double doors
    pygame.draw.rect(surface, W0, door_r)
    # Plank texture
    for px in range(door_r.left + 2, door_r.right - 2, 10):
        v = ((px * 7) % 9)
        plank_c = _clr(W0, v - 4)
        pw = min(9, door_r.right - px - 2)
        pygame.draw.rect(surface, plank_c, (px, door_r.top + 2, pw, door_h - 4))
        pygame.draw.line(surface, _clr(W0, -10), (px, door_r.top + 2), (px, door_r.bottom - 2), 1)
        # Wood grain
        for gy in range(door_r.top + 8, door_r.bottom - 4, 11):
            gl = 3 + (px + gy) % 6
            pygame.draw.line(surface, _clr(W0, -6), (px + 2, gy), (px + 2 + gl, gy), 1)
    # Center split
    pygame.draw.line(surface, (16, 12, 8), (cx, door_r.top), (cx, door_r.bottom), 3)
    pygame.draw.line(surface, W1, (cx - 2, door_r.top), (cx - 2, door_r.bottom), 1)
    pygame.draw.line(surface, W1, (cx + 2, door_r.top), (cx + 2, door_r.bottom), 1)

    # Iron strap hinges (decorative, fleur-de-lis style)
    for hy_frac in (0.2, 0.5, 0.8):
        hy = door_top + int(door_h * hy_frac)
        for side in (-1, 1):
            hx = cx + side * (door_w // 2 - 1)
            # Main strap
            pygame.draw.line(surface, IR, (hx, hy), (hx - side * 24, hy), 3)
            # Decorative curls
            pygame.draw.line(surface, IR, (hx - side * 16, hy), (hx - side * 20, hy - 6), 2)
            pygame.draw.line(surface, IR, (hx - side * 16, hy), (hx - side * 20, hy + 6), 2)
            pygame.draw.line(surface, IR, (hx - side * 22, hy), (hx - side * 24, hy - 4), 1)
            pygame.draw.line(surface, IR, (hx - side * 22, hy), (hx - side * 24, hy + 4), 1)
            # Bolt heads
            pygame.draw.circle(surface, IH, (hx - side * 4, hy), 2)
            pygame.draw.circle(surface, IH, (hx - side * 12, hy), 2)

    # Door ring knockers (large iron rings)
    for side in (-1, 1):
        kx = cx + side * 16
        ky = door_top + door_h // 2 + 4
        # Backplate
        pygame.draw.circle(surface, IR, (kx, ky), 6)
        pygame.draw.circle(surface, IH, (kx, ky), 6, 1)
        # Ring
        pygame.draw.circle(surface, G0, (kx, ky + 4), 7, 3)
        pygame.draw.circle(surface, G1, (kx, ky + 4), 7, 1)
        # Highlight on ring
        pygame.draw.arc(surface, G2, (kx - 7, ky + 4 - 7, 14, 14), math.pi * 0.8, math.pi * 1.3, 1)

    # Door frame
    pygame.draw.rect(surface, S3, door_r, 2)

    # ── stone steps (5 with depth shading) ────────────────────────────────────
    for s in range(5):
        sw = door_w + 36 + s * 20
        sh = 5
        sy = base_y - 1 + s * sh
        sr = pygame.Rect(cx - sw // 2, sy, sw, sh)
        v = 82 - s * 7
        pygame.draw.rect(surface, (v, v - 2, v - 4), sr)
        # Step edge highlight
        pygame.draw.line(surface, _clr((v, v, v), 12), (sr.left + 1, sr.top), (sr.right - 1, sr.top), 1)
        pygame.draw.rect(surface, MO, sr, 1)
    # Worn groove in center steps
    for s in range(3):
        sy = base_y + s * 5
        pygame.draw.line(surface, _clr(MO, -4), (cx - 18, sy + 2), (cx + 18, sy + 2), 1)

    # ── flanking statues (saints in niches) ───────────────────────────────────
    for side in (-1, 1):
        nx = cx + side * (door_w // 2 + 22)
        ny = base_y - 80
        # Niche (recessed pointed arch)
        _lancet_orig(nx, ny - 30, 11, 56, S3, MO, 1)
        # Figure (simplified robed saint)
        # Head
        pygame.draw.circle(surface, _clr(S0, 14), (nx, ny - 14), 5)
        # Halo
        pygame.draw.circle(surface, G0, (nx, ny - 16), 8, 1)
        # Body (robe)
        robe = [(nx - 6, ny - 8), (nx + 6, ny - 8), (nx + 8, ny + 22), (nx - 8, ny + 22)]
        pygame.draw.polygon(surface, S2, robe)
        pygame.draw.polygon(surface, MO, robe, 1)
        # Hands (holding object)
        pygame.draw.circle(surface, _clr(S0, 14), (nx - 3, ny + 2), 2)
        pygame.draw.circle(surface, _clr(S0, 14), (nx + 3, ny + 2), 2)
        # Pedestal
        pygame.draw.rect(surface, S4, (nx - 8, ny + 22, 16, 6))
        pygame.draw.rect(surface, MO, (nx - 8, ny + 22, 16, 6), 1)

    # ── horizontal string courses ─────────────────────────────────────────────
    # Base course
    pygame.draw.rect(surface, S4, (nave.left - 6, base_y - 6, nave_w + 12, 6))
    pygame.draw.line(surface, MO, (nave.left - 6, base_y), (nave.right + 6, base_y), 1)
    # Mid course
    mid_y = nave_top + nave_h // 2
    pygame.draw.rect(surface, S2, (nave.left - 2, mid_y, nave_w + 4, 3))
    pygame.draw.line(surface, MO, (nave.left - 2, mid_y + 3), (nave.right + 2, mid_y + 3), 1)

    # ── weathering: moss at base, stains ──────────────────────────────────────
    for mx in range(nave.left + 2, nave.right - 2, 7):
        mh = 3 + (mx * 11) % 8
        my = base_y - 6 - mh
        mw = 3 + (mx * 3) % 4
        # Only sparse patches
        if (mx * 7 + base_y) % 5 < 2:
            pygame.draw.rect(surface, WE, (mx, my, mw, mh))

    return total


def draw_well(surface: pygame.Surface, center_x: int, center_y: int) -> pygame.Rect:
    base_shadow = pygame.Rect(center_x - 92, center_y + 20, 184, 28)
    pygame.draw.ellipse(surface, (22, 22, 24), base_shadow)

    outer = pygame.Rect(center_x - 72, center_y - 24, 144, 66)
    inner = pygame.Rect(center_x - 55, center_y - 12, 110, 38)
    pygame.draw.ellipse(surface, (88, 90, 95), outer)
    pygame.draw.ellipse(surface, (46, 48, 52), inner)
    pygame.draw.ellipse(surface, (122, 124, 130), outer, 3)

    for i in range(8):
        angle = (math.pi * 2 / 8) * i
        px = center_x + int(math.cos(angle) * 63)
        py = center_y + int(math.sin(angle) * 23)
        pygame.draw.circle(surface, (108, 110, 115), (px, py), 8)
        pygame.draw.circle(surface, (56, 58, 62), (px, py), 8, 1)

    post_left = pygame.Rect(center_x - 64, center_y - 128, 14, 108)
    post_right = pygame.Rect(center_x + 50, center_y - 128, 14, 108)
    pygame.draw.rect(surface, (76, 60, 42), post_left)
    pygame.draw.rect(surface, (76, 60, 42), post_right)
    pygame.draw.rect(surface, (36, 30, 22), post_left, 2)
    pygame.draw.rect(surface, (36, 30, 22), post_right, 2)

    roof = [(center_x - 96, center_y - 130), (center_x + 96, center_y - 130), (center_x, center_y - 198)]
    pygame.draw.polygon(surface, (38, 34, 36), roof)
    pygame.draw.polygon(surface, (18, 16, 18), roof, 2)
    pygame.draw.line(surface, (100, 92, 82), (center_x - 82, center_y - 132), (center_x + 82, center_y - 132), 2)

    axle = pygame.Rect(center_x - 56, center_y - 112, 112, 8)
    pygame.draw.rect(surface, (66, 52, 38), axle)
    pygame.draw.rect(surface, (30, 24, 18), axle, 2)

    rope_color = (84, 70, 54)
    pygame.draw.line(surface, rope_color, (center_x, center_y - 104), (center_x, center_y - 36), 2)
    bucket = pygame.Rect(center_x - 14, center_y - 36, 28, 28)
    pygame.draw.rect(surface, (62, 46, 34), bucket)
    pygame.draw.rect(surface, (24, 20, 16), bucket, 2)
    pygame.draw.arc(surface, (88, 74, 56), (center_x - 16, center_y - 46, 32, 24), math.pi, math.tau, 2)

    return pygame.Rect(center_x - 72, center_y - 24, 144, 66)


def draw_grass_patch(
    surface: pygame.Surface,
    cx: int,
    cy: int,
    w: int = 128,
    h: int = 64,
    *,
    seed: Optional[int] = None,
    outline: bool = False,
) -> None:
    rng = random.Random((cx * 31 + cy * 7) if seed is None else int(seed))
    rect = pygame.Rect(cx - w // 2, cy - h // 2, w, h)

    # New style: stamp real grass tiles into an irregular blob so "green patches"
    # look like vegetation rather than a clean green ellipse.
    outer = rect.inflate(18, 10)
    _tiles = getattr(draw_grass_patch, "_tiles", None)
    if _tiles is None:
        _tiles = []
        for _p in [
            os.path.join(MEDIEVAL_PACK_ROOT, "tiles", "terrain", "terrain_grass_1.png"),
            os.path.join(MEDIEVAL_PACK_ROOT, "tiles", "terrain", "terrain_grass_2.png"),
        ]:
            try:
                if os.path.exists(_p):
                    _t = pygame.image.load(_p)
                    if pygame.display.get_surface():
                        _t = _t.convert_alpha()
                    _tiles.append(_t)
            except (pygame.error, OSError):
                pass
        setattr(draw_grass_patch, "_tiles", _tiles)

    patch = pygame.Surface((outer.w, outer.h), pygame.SRCALPHA)
    mask = pygame.Surface((outer.w, outer.h), pygame.SRCALPHA)
    mask_rect = pygame.Rect(rect.x - outer.x, rect.y - outer.y, rect.w, rect.h)

    # Tile stamp base
    if _tiles:
        tw, th = _tiles[0].get_size()
        ox = rng.randint(0, max(1, tw - 1))
        oy = rng.randint(0, max(1, th - 1))
        for ty in range(-oy, patch.get_height(), th):
            for tx in range(-ox, patch.get_width(), tw):
                patch.blit(_tiles[(tx // tw + ty // th) % len(_tiles)], (tx, ty))
    else:
        patch.fill((44, 72, 46, 255))

    # Subtle tonal breakup (pre-mask) to avoid visible tiling.
    for _ in range(rng.randint(10, 16)):
        bw = rng.randint(max(10, w // 8), max(18, w // 4))
        bh = rng.randint(max(8, h // 8), max(14, h // 4))
        bx = mask_rect.centerx + rng.randint(-w // 2, w // 2) - bw // 2
        by = mask_rect.centery + rng.randint(-h // 2, h // 2) - bh // 2
        tint = rng.choice([(18, 32, 18, 40), (10, 20, 10, 35), (30, 46, 26, 35), (24, 38, 18, 30)])
        b = pygame.Surface((bw, bh), pygame.SRCALPHA)
        pygame.draw.ellipse(b, tint, b.get_rect())
        patch.blit(b, (bx, by))

    # Mask: irregular grassy blob (ellipse + bumps + nicks)
    pygame.draw.ellipse(mask, (255, 255, 255, 210), mask_rect.inflate(14, 8))
    pygame.draw.ellipse(mask, (255, 255, 255, 255), mask_rect)
    for _ in range(rng.randint(18, 26)):
        ang = rng.random() * math.tau
        rr = 0.48 + rng.random() * 0.08
        ex = mask_rect.centerx + int(math.cos(ang) * mask_rect.w * rr)
        ey = mask_rect.centery + int(math.sin(ang) * mask_rect.h * rr)
        pygame.draw.circle(mask, (255, 255, 255, 255), (ex, ey), rng.randint(3, 7))
    for _ in range(rng.randint(6, 10)):
        ang = rng.random() * math.tau
        rr = 0.50 + rng.random() * 0.06
        ex = mask_rect.centerx + int(math.cos(ang) * mask_rect.w * rr)
        ey = mask_rect.centery + int(math.sin(ang) * mask_rect.h * rr)
        pygame.draw.circle(mask, (0, 0, 0, 0), (ex, ey), rng.randint(2, 4))

    patch.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

    # Dirt peeks + extra pixel blades + tiny flowers
    for _ in range(rng.randint(3, 6)):
        sx = mask_rect.centerx + rng.randint(-w // 3, w // 3)
        sy = mask_rect.centery + rng.randint(-h // 4, h // 4)
        sr = rng.randint(2, 6)
        pygame.draw.circle(patch, (44, 38, 28, 190), (sx, sy), sr)

    blade_count = rng.randint(14, 26)
    for _ in range(blade_count):
        bx = mask_rect.centerx + rng.randint(-w // 2 + 8, w // 2 - 8)
        by = mask_rect.centery + rng.randint(-h // 3 + 6, h // 3 + 2)
        dx = (bx - mask_rect.centerx) / max(1, w * 0.5)
        dy = (by - mask_rect.centery) / max(1, h * 0.5)
        if dx * dx + dy * dy > 0.90:
            continue
        blade_h = rng.randint(6, 14)
        curve = rng.uniform(-3.5, 3.5)
        gc = (34 + rng.randint(0, 26), 62 + rng.randint(0, 34), 24 + rng.randint(0, 14), 230)
        mid_x = bx + int(curve * 0.6)
        mid_y = by - blade_h // 2
        tip_x = bx + int(curve)
        tip_y = by - blade_h
        pygame.draw.line(patch, gc, (bx, by), (mid_x, mid_y), rng.choice([1, 1, 2]))
        tip_c = (min(255, gc[0] + 18), min(255, gc[1] + 22), min(255, gc[2] + 10), 245)
        pygame.draw.line(patch, tip_c, (mid_x, mid_y), (tip_x, tip_y), 1)

    for _ in range(rng.randint(2, 5)):
        fx = mask_rect.centerx + rng.randint(-w // 3, w // 3)
        fy = mask_rect.centery + rng.randint(-h // 4, h // 4)
        fc = rng.choice([(230, 230, 92), (210, 92, 92), (190, 132, 210), (248, 248, 248)])
        pygame.draw.circle(patch, (*fc, 220), (fx, fy - rng.randint(3, 6)), rng.randint(1, 2))

    if outline:
        pygame.draw.ellipse(patch, (28, 46, 30, 150), mask_rect, 2)

    surface.blit(patch, outer.topleft)
    return
    # Soft outer glow / feathered edge
    outer = rect.inflate(12, 6)
    pygame.draw.ellipse(surface, (38, 58, 38, 80), outer)
    # Main grass base — multi-tone
    pygame.draw.ellipse(surface, (44, 72, 46, 140), rect)
    # Inner lighter patches for variation
    for _ in range(rng.randint(4, 7)):
        pw = rng.randint(w // 6, w // 3)
        ph = rng.randint(h // 6, h // 3)
        px = cx + rng.randint(-w // 3, w // 3) - pw // 2
        py = cy + rng.randint(-h // 4, h // 4) - ph // 2
        pg = 48 + rng.randint(0, 16)
        pygame.draw.ellipse(surface, (pg, pg + 28, pg + 2, 150), (px, py, pw, ph))
    # Dark soil peeks
    for _ in range(rng.randint(2, 4)):
        sx = cx + rng.randint(-w // 3, w // 3)
        sy = cy + rng.randint(-h // 4, h // 4)
        sr = rng.randint(2, 5)
        pygame.draw.circle(surface, (42, 36, 28, 210), (sx, sy), sr)
    # Edge outline (optional; park stamps look more natural without it)
    if outline:
        pygame.draw.ellipse(surface, (28, 46, 30, 150), rect, 2)
    # Dense grass blade clusters — 30-50 blades with curves
    blade_count = rng.randint(30, 50)
    for _ in range(blade_count):
        bx = cx + rng.randint(-w // 2 + 6, w // 2 - 6)
        by = cy + rng.randint(-h // 3 + 4, h // 3)
        # Check roughly inside ellipse
        dx = (bx - cx) / max(1, w * 0.5)
        dy = (by - cy) / max(1, h * 0.5)
        if dx * dx + dy * dy > 0.85:
            continue
        blade_h = rng.randint(6, 16)
        curve = rng.uniform(-4, 4)
        thickness = rng.choice([1, 1, 1, 2])
        gc = (40 + rng.randint(0, 30), 68 + rng.randint(0, 36), 28 + rng.randint(0, 16), 220)
        # Draw curved blade via 3 points
        mid_x = bx + int(curve * 0.6)
        mid_y = by - blade_h // 2
        tip_x = bx + int(curve)
        tip_y = by - blade_h
        pygame.draw.line(surface, gc, (bx, by), (mid_x, mid_y), thickness)
        # Lighter tip
        tip_c = (min(255, gc[0] + 20), min(255, gc[1] + 24), min(255, gc[2] + 12), 245)
        pygame.draw.line(surface, tip_c, (mid_x, mid_y), (tip_x, tip_y), 1)
    # Clover / small leaf clusters
    for _ in range(rng.randint(3, 8)):
        lx = cx + rng.randint(-w // 3, w // 3)
        ly = cy + rng.randint(-h // 4, h // 4)
        leaf_c = (36 + rng.randint(0, 12), 66 + rng.randint(0, 18), 30 + rng.randint(0, 8), 200)
        for li in range(3):
            la = li * (math.tau / 3) + rng.uniform(-0.3, 0.3)
            ldist = rng.randint(2, 4)
            lxp = lx + int(math.cos(la) * ldist)
            lyp = ly + int(math.sin(la) * ldist)
            pygame.draw.circle(surface, leaf_c, (lxp, lyp), 2)
    # Tiny wildflowers scattered
    for _ in range(rng.randint(2, 5)):
        fx = cx + rng.randint(-w // 3, w // 3)
        fy = cy + rng.randint(-h // 4, h // 4)
        fc = rng.choice([(220, 220, 80), (200, 80, 80), (180, 120, 200), (255, 255, 255)])
        pygame.draw.circle(surface, (*fc, 210), (fx, fy - rng.randint(3, 6)), rng.randint(1, 2))
    # Seed heads on a few blades
    for _ in range(rng.randint(1, 4)):
        sx = cx + rng.randint(-w // 3, w // 3)
        sy = cy + rng.randint(-h // 4, h // 4)
        sh = rng.randint(10, 18)
        pygame.draw.line(surface, (58, 82, 44, 200), (sx, sy), (sx + rng.randint(-2, 2), sy - sh), 1)
        # Seed cluster at top
        for _ in range(rng.randint(3, 6)):
            sa = rng.uniform(0, math.tau)
            sd = rng.randint(1, 3)
            pygame.draw.circle(surface, (120, 110, 70, 210),
                               (sx + int(math.cos(sa) * sd), sy - sh + int(math.sin(sa) * sd)), 1)


def draw_brazier(surface: pygame.Surface, x: int, y: int) -> None:
    pygame.draw.ellipse(surface, (16, 14, 18), (x - 18, y - 4, 36, 14))
    for dx in (-12, 0, 12):
        pygame.draw.line(surface, (54, 54, 60), (x, y - 34), (x + dx, y - 2), 3)
    pygame.draw.arc(surface, (66, 62, 70), (x - 18, y - 50, 36, 24), 0, math.pi, 5)
    pygame.draw.arc(surface, (48, 46, 52), (x - 18, y - 48, 36, 20), 0, math.pi, 2)
    glow = pygame.Surface((80, 80), pygame.SRCALPHA)
    pygame.draw.circle(glow, (255, 140, 40, 55), (40, 40), 28)
    pygame.draw.circle(glow, (255, 200, 80, 30), (40, 40), 16)
    surface.blit(glow, (x - 40, y - 78))
    flame_pts = [(x - 7, y - 40), (x - 3, y - 58), (x, y - 40)]
    pygame.draw.polygon(surface, (220, 90, 20), flame_pts)
    flame_pts2 = [(x, y - 40), (x + 4, y - 62), (x + 8, y - 40)]
    pygame.draw.polygon(surface, (240, 110, 30), flame_pts2)
    pygame.draw.polygon(surface, (255, 210, 80), [(x - 3, y - 42), (x, y - 54), (x + 3, y - 42)])


def draw_barrel(surface: pygame.Surface, x: int, y: int, h: int = 38) -> None:
    rng = random.Random(x * 19 + y + h)
    bw = 28
    # Shadow
    shad = pygame.Surface((bw + 12, 14), pygame.SRCALPHA)
    pygame.draw.ellipse(shad, (0, 0, 0, 30), shad.get_rect())
    surface.blit(shad, (x - bw // 2 - 6, y - 5))
    # Staved body — vertical planks with curvature
    stave_count = 6
    sw = bw // stave_count
    for si in range(stave_count):
        sx_s = x - bw // 2 + si * sw
        base = 86 + rng.randint(-8, 8)
        for col_off in range(sw):
            cx_s = sx_s + col_off
            if cx_s >= x + bw // 2:
                break
            curve = abs(col_off - sw // 2) / max(1, sw // 2)
            s = max(0, int(base - curve * 14))
            pygame.draw.line(surface, (s, int(s * 0.68), int(s * 0.42)),
                             (cx_s, y - h + 2), (cx_s, y - 2))
    pygame.draw.rect(surface, (38, 28, 18), (x - bw // 2, y - h, bw, h), 1)
    # Iron bands with rivets
    for hy_off in (3, h // 2, h - 4):
        hy_b = y - h + hy_off
        pygame.draw.line(surface, (72, 70, 66), (x - bw // 2 + 1, hy_b), (x + bw // 2 - 1, hy_b), 2)
        pygame.draw.line(surface, (92, 90, 84), (x - bw // 2 + 1, hy_b - 1), (x + bw // 2 - 1, hy_b - 1), 1)
        pygame.draw.circle(surface, (88, 86, 82), (x - bw // 2 + 2, hy_b), 1)
        pygame.draw.circle(surface, (88, 86, 82), (x + bw // 2 - 2, hy_b), 1)
    # Top rim ellipse
    pygame.draw.ellipse(surface, (72, 52, 34), (x - bw // 2, y - h - 4, bw, 10))
    pygame.draw.ellipse(surface, (38, 28, 18), (x - bw // 2, y - h - 4, bw, 10), 1)
    # Bottom rim
    pygame.draw.ellipse(surface, (62, 44, 28), (x - bw // 2, y - 5, bw, 10))
    pygame.draw.ellipse(surface, (38, 28, 18), (x - bw // 2, y - 5, bw, 10), 1)


def draw_cauldron(surface: pygame.Surface, x: int, y: int) -> None:
    rng = random.Random(x * 29 + y)
    # Shadow
    shad = pygame.Surface((50, 14), pygame.SRCALPHA)
    pygame.draw.ellipse(shad, (0, 0, 0, 28), shad.get_rect())
    surface.blit(shad, (x - 25, y - 4))
    # Tripod legs — gradient iron
    for dx, lean in [(-16, -2), (16, 2), (0, 0)]:
        for row in range(18):
            t = row / 17.0
            shade = int(56 - 14 * t)
            pygame.draw.line(surface, (shade, shade + 2, shade + 4),
                             (x + dx + int(lean * t), y - 2 - row), (x + dx + int(lean * t) + 2, y - 2 - row))
    # Cauldron body — gradient cast iron hemisphere
    cw, ch = 40, 32
    for row in range(ch):
        t = row / max(1, ch - 1)
        half_w = int(cw * 0.5 * math.sin(t * math.pi * 0.85 + 0.2))
        shade = int(52 + 16 * math.sin(t * math.pi))
        pygame.draw.line(surface, (shade, shade + 2, shade + 4),
                         (x - half_w, y - 38 + row), (x + half_w, y - 38 + row))
    # Rim — thick iron lip
    pygame.draw.ellipse(surface, (62, 64, 68), (x - cw // 2, y - 40, cw, 8))
    pygame.draw.ellipse(surface, (38, 40, 44), (x - cw // 2, y - 40, cw, 8), 1)
    pygame.draw.ellipse(surface, (68, 70, 74), (x - cw // 2 + 1, y - 41, cw - 2, 6))
    # Brew surface — bubbling green liquid
    brew_w, brew_h = cw - 8, 6
    brew_s = pygame.Surface((brew_w, brew_h), pygame.SRCALPHA)
    pygame.draw.ellipse(brew_s, (34, 62, 40, 200), brew_s.get_rect())
    surface.blit(brew_s, (x - brew_w // 2, y - 39))
    # Bubble highlights
    for _ in range(4):
        bx = x + rng.randint(-12, 12)
        by = y - 37 + rng.randint(-2, 2)
        pygame.draw.circle(surface, (60, 100, 68), (bx, by), rng.randint(1, 2))
    # Steam/vapour glow
    glow = pygame.Surface((60, 50), pygame.SRCALPHA)
    pygame.draw.ellipse(glow, (50, 180, 70, 35), (5, 5, 50, 38))
    surface.blit(glow, (x - 30, y - 56))
    # Steam wisps
    for i in range(3):
        sx_w = x + (-8 + i * 8)
        for seg in range(6):
            t = seg / 5.0
            wy = y - 40 - int(t * 16)
            wx_off = int(math.sin(t * 3.0 + i) * 3)
            alpha = max(0, int(80 * (1.0 - t)))
            ws = pygame.Surface((4, 4), pygame.SRCALPHA)
            pygame.draw.circle(ws, (70, 200, 90, alpha), (2, 2), 2)
            surface.blit(ws, (sx_w + wx_off - 2, wy - 2))
    # Iron handles on sides
    pygame.draw.arc(surface, (66, 68, 72), (x - cw // 2 - 6, y - 32, 8, 10), math.pi * 0.5, math.pi * 1.5, 2)
    pygame.draw.arc(surface, (66, 68, 72), (x + cw // 2 - 2, y - 32, 8, 10), -math.pi * 0.5, math.pi * 0.5, 2)


def draw_wood_crate(surface: pygame.Surface, x: int, y: int, size: int = 34) -> pygame.Rect:
    rng = random.Random(x * 17 + y + size)
    # Alpha shadow
    shad = pygame.Surface((size + 8, 14), pygame.SRCALPHA)
    pygame.draw.ellipse(shad, (0, 0, 0, 34), shad.get_rect())
    surface.blit(shad, (x - size // 2 - 4, y - 5))
    body = pygame.Rect(x - size // 2, y - size, size, size)
    # Planked sides — 4 vertical planks with curvature shading
    pw = size // 4
    for pi in range(4):
        px_p = body.left + pi * pw
        base = 92 + rng.randint(-8, 8)
        for col_off in range(pw):
            cx_p = px_p + col_off
            if cx_p >= body.right:
                break
            curve = abs(col_off - pw // 2) / max(1, pw // 2)
            s = max(0, int(base - curve * 16))
            pygame.draw.line(surface, (s, int(s * 0.70), int(s * 0.46)),
                             (cx_p, body.top + 2), (cx_p, body.bottom - 1))
        # Grain line
        gy = body.top + rng.randint(6, size - 8)
        pygame.draw.line(surface, (base - 16, int((base - 16) * 0.68), int((base - 16) * 0.44)),
                         (px_p + 1, gy), (px_p + pw - 1, gy), 1)
    # Iron corner brackets
    for cx_b, cy_b in [(body.left + 1, body.top + 1), (body.right - 6, body.top + 1),
                       (body.left + 1, body.bottom - 6), (body.right - 6, body.bottom - 6)]:
        pygame.draw.rect(surface, (66, 64, 60), (cx_b, cy_b, 5, 5))
        pygame.draw.circle(surface, (88, 86, 82), (cx_b + 2, cy_b + 2), 1)
    # Cross braces
    pygame.draw.line(surface, (110, 78, 48), (body.left + 4, body.top + 4), (body.right - 4, body.bottom - 4), 2)
    pygame.draw.line(surface, (110, 78, 48), (body.right - 4, body.top + 4), (body.left + 4, body.bottom - 4), 2)
    # Center rivet
    pygame.draw.circle(surface, (78, 76, 72), (body.centerx, body.centery), 2)
    pygame.draw.circle(surface, (96, 94, 88), (body.centerx, body.centery - 1), 1)
    # Frame outline
    pygame.draw.rect(surface, (38, 28, 18), body, 2, border_radius=2)
    # Top highlight
    pygame.draw.line(surface, (116, 84, 54), (body.left + 2, body.top + 1), (body.right - 2, body.top + 1), 1)
    return body


def draw_hay_bale(surface: pygame.Surface, x: int, y: int, w: int = 46, h: int = 28) -> pygame.Rect:
    rng = random.Random(x * 13 + y + w)
    # Shadow
    shad = pygame.Surface((w + 8, 14), pygame.SRCALPHA)
    pygame.draw.ellipse(shad, (0, 0, 0, 26), shad.get_rect())
    surface.blit(shad, (x - w // 2 - 4, y - 5))
    bale = pygame.Rect(x - w // 2, y - h, w, h)
    # Straw texture — individual strands
    for row in range(h):
        t = row / max(1, h - 1)
        base = int(168 - 22 * t)
        for col in range(w):
            noise = rng.randint(-8, 8)
            s = max(0, min(255, base + noise))
            surface.set_at((bale.left + col, bale.top + row),
                           (s, int(s * 0.86), int(s * 0.44)))
    # Binding twine — 3 horizontal straps
    for sx in (bale.left + 12, bale.centerx, bale.right - 12):
        for row in range(h - 4):
            shade = 88 + int(math.sin(row * 0.6) * 8)
            pygame.draw.line(surface, (shade, int(shade * 0.80), int(shade * 0.28)),
                             (sx - 1, bale.top + 2 + row), (sx + 1, bale.top + 2 + row))
    # Loose straw wisps
    for _ in range(6):
        wx = rng.randint(bale.left - 4, bale.right + 4)
        wy = rng.randint(bale.top - 2, bale.bottom + 2)
        wl = rng.randint(5, 10)
        wa = rng.uniform(-0.4, 0.4)
        pygame.draw.line(surface, (188, 166, 86),
                         (wx, wy), (wx + int(wl * math.cos(wa)), wy + int(wl * math.sin(wa))), 1)
    # Outline
    pygame.draw.rect(surface, (94, 78, 32), bale, 1, border_radius=4)
    # Top highlight
    pygame.draw.line(surface, (192, 172, 96), (bale.left + 3, bale.top + 1), (bale.right - 3, bale.top + 1), 1)
    return bale


def draw_lumber_stack(surface: pygame.Surface, x: int, y: int, w: int = 72, h: int = 28) -> pygame.Rect:
    rng = random.Random(x * 11 + y)
    # Shadow
    shad = pygame.Surface((w + 8, 14), pygame.SRCALPHA)
    pygame.draw.ellipse(shad, (0, 0, 0, 30), shad.get_rect())
    surface.blit(shad, (x - w // 2 - 4, y - 5))
    stack = pygame.Rect(x - w // 2, y - h, w, h)
    # Individual planks/beams — horizontal with grain per plank
    plank_h = 6
    num_planks = h // plank_h
    for pi in range(num_planks):
        py_p = stack.top + pi * plank_h
        base = 86 + rng.randint(-10, 10)
        # Gradient per plank (lighter top edge)
        for row in range(plank_h):
            t = row / max(1, plank_h - 1)
            s = max(0, int(base + 8 - 16 * t))
            pygame.draw.line(surface, (s, int(s * 0.68), int(s * 0.44)),
                             (stack.left + 1, py_p + row), (stack.right - 1, py_p + row))
        # Grain lines
        for _ in range(rng.randint(1, 3)):
            gx = stack.left + rng.randint(4, w - 8)
            pygame.draw.line(surface, (base - 14, int((base - 14) * 0.66), int((base - 14) * 0.42)),
                             (gx, py_p + 1), (gx + rng.randint(8, 20), py_p + 1), 1)
        # End-grain circle visible on right side
        pygame.draw.circle(surface, (base + 12, int((base + 12) * 0.72), int((base + 12) * 0.48)),
                           (stack.right - 3, py_p + plank_h // 2), 2)
        pygame.draw.circle(surface, (base - 8, int((base - 8) * 0.66), int((base - 8) * 0.42)),
                           (stack.right - 3, py_p + plank_h // 2), 2, 1)
    # Outline
    pygame.draw.rect(surface, (36, 26, 18), stack, 1, border_radius=2)
    # Highlight on top edge
    pygame.draw.line(surface, (112, 80, 52), (stack.left + 2, stack.top + 1), (stack.right - 2, stack.top + 1), 1)
    return stack


def draw_banner_post(
    surface: pygame.Surface,
    x: int,
    y: int,
    primary: tuple[int, int, int] = (130, 28, 24),
    secondary: tuple[int, int, int] = (212, 184, 112),
) -> pygame.Rect:
    rng = random.Random(x * 13 + y)
    # Shadow
    shad = pygame.Surface((24, 10), pygame.SRCALPHA)
    pygame.draw.ellipse(shad, (0, 0, 0, 30), shad.get_rect())
    surface.blit(shad, (x - 12, y - 3))
    # Post — gradient wood with grain
    pw, ph = 8, 66
    px_p = x - pw // 2
    for row in range(ph):
        t = row / max(1, ph - 1)
        shade = int(78 - 20 * t)
        pygame.draw.line(surface, (shade, int(shade * 0.74), int(shade * 0.52)),
                         (px_p, y - ph + row), (px_p + pw, y - ph + row))
    pygame.draw.rect(surface, (34, 24, 16), (px_p, y - ph, pw, ph), 1)
    # Grain
    for gy in range(y - ph + 6, y - 6, 10):
        pygame.draw.line(surface, (56, 42, 28), (px_p + 1, gy), (px_p + pw - 1, gy), 1)
    # Carved finial top
    pygame.draw.polygon(surface, (86, 66, 46), [
        (px_p - 1, y - ph), (px_p + pw + 1, y - ph), (x, y - ph - 8)])
    pygame.draw.polygon(surface, (40, 30, 20), [
        (px_p - 1, y - ph), (px_p + pw + 1, y - ph), (x, y - ph - 8)], 1)
    # Iron crossbar bracket
    pygame.draw.rect(surface, (66, 64, 60), (x + 2, y - ph + 4, 6, 3))
    # Cloth banner — gradient fill with fold simulation
    cw, ch = 36, 30
    cx_c = x + 4
    cy_c = y - ph + 6
    for row in range(ch):
        t = row / max(1, ch - 1)
        # Sine wave for fold effect
        fold = math.sin(row * 0.4) * 8
        r = max(0, min(255, int(primary[0] + fold - 10 * t)))
        g = max(0, min(255, int(primary[1] + fold * 0.3 - 6 * t)))
        b = max(0, min(255, int(primary[2] + fold * 0.2 - 4 * t)))
        pygame.draw.line(surface, (r, g, b), (cx_c, cy_c + row), (cx_c + cw, cy_c + row))
    # Banner border trim
    pygame.draw.rect(surface, secondary, (cx_c, cy_c, cw, ch), 2, border_radius=2)
    # Decorative stripe
    pygame.draw.line(surface, secondary, (cx_c + 4, cy_c + 8), (cx_c + cw - 4, cy_c + 8), 2)
    pygame.draw.line(surface, secondary, (cx_c + 4, cy_c + ch - 8), (cx_c + cw - 4, cy_c + ch - 8), 1)
    # Central emblem (diamond)
    emx, emy = cx_c + cw // 2, cy_c + ch // 2
    pygame.draw.polygon(surface, secondary, [(emx, emy - 5), (emx - 4, emy), (emx, emy + 5), (emx + 4, emy)])
    # Banner bottom fringe (torn/tattered edge)
    for fx in range(cx_c + 2, cx_c + cw - 2, 4):
        depth = rng.randint(0, 4)
        pygame.draw.line(surface, primary, (fx, cy_c + ch - 1), (fx, cy_c + ch + depth), 1)
    return pygame.Rect(x - 6, y - ph - 8, cw + 10, ph + 8)


def draw_market_cart(surface: pygame.Surface, x: int, y: int, scale: float = 1.0) -> pygame.Rect:
    rng = random.Random(x * 23 + y)
    w = int(132 * scale)
    h = int(56 * scale)
    # Shadow
    shad = pygame.Surface((w + 12, 16), pygame.SRCALPHA)
    pygame.draw.ellipse(shad, (0, 0, 0, 26), shad.get_rect())
    surface.blit(shad, (x - w // 2 - 6, y - 6))
    bed = pygame.Rect(x - w // 2, y - h, w, h)
    # Planked bed — horizontal planks with grain
    plank_h = max(1, h // 6)
    for pi in range(6):
        py_p = bed.top + pi * plank_h
        base = 88 + rng.randint(-8, 8)
        for row in range(plank_h):
            t = row / max(1, plank_h - 1)
            shade = int(base - 8 * t)
            pygame.draw.line(surface, (shade, int(shade * 0.72), int(shade * 0.48)),
                             (bed.left + 1, py_p + row), (bed.right - 1, py_p + row))
        # Grain lines
        for _ in range(rng.randint(1, 2)):
            gx = bed.left + rng.randint(6, w - 10)
            pygame.draw.line(surface, (base - 14, int((base - 14) * 0.66), int((base - 14) * 0.42)),
                             (gx, py_p + 1), (gx + rng.randint(10, 24), py_p + 1), 1)
    # Side rail boards (raised edges)
    rail_h = max(6, int(12 * scale))
    for row in range(rail_h):
        t = row / max(1, rail_h - 1)
        shade = int(96 - 14 * t)
        pygame.draw.line(surface, (shade, int(shade * 0.72), int(shade * 0.50)),
                         (bed.left, bed.top + row), (bed.left + 3, bed.top + row))
        pygame.draw.line(surface, (shade, int(shade * 0.72), int(shade * 0.50)),
                         (bed.right - 3, bed.top + row), (bed.right, bed.top + row))
    # Iron corner brackets
    for cx_b, cy_b in [(bed.left, bed.top), (bed.right - 5, bed.top),
                       (bed.left, bed.bottom - 5), (bed.right - 5, bed.bottom - 5)]:
        pygame.draw.rect(surface, (66, 64, 60), (cx_b, cy_b, 5, 5))
        pygame.draw.circle(surface, (86, 84, 80), (cx_b + 2, cy_b + 2), 1)
    # Frame outline
    pygame.draw.rect(surface, (38, 28, 18), bed, 1, border_radius=3)
    # Wheels — detailed with spokes
    wheel_r = int(18 * scale)
    for wx in (x - w // 2 + int(20 * scale), x + w // 2 - int(20 * scale)):
        wy = y - 6
        # Wheel rim gradient
        for ring in range(wheel_r, wheel_r - 3, -1):
            t = (wheel_r - ring) / 3.0
            shade = int(62 + 16 * t)
            pygame.draw.circle(surface, (shade, int(shade * 0.82), int(shade * 0.66)), (wx, wy), ring)
        # Inner hub area
        pygame.draw.circle(surface, (42, 34, 26), (wx, wy), wheel_r - 3)
        # Spokes
        for si in range(8):
            ang = (si / 8.0) * math.tau
            sx = wx + int(math.cos(ang) * (wheel_r - 4))
            sy = wy + int(math.sin(ang) * (wheel_r - 4))
            pygame.draw.line(surface, (76, 60, 42), (wx, wy), (sx, sy), 1)
        # Hub
        pygame.draw.circle(surface, (86, 72, 54), (wx, wy), max(3, wheel_r // 4))
        pygame.draw.circle(surface, (106, 90, 68), (wx, wy), max(2, wheel_r // 5))
        # Rim outline
        pygame.draw.circle(surface, (28, 22, 18), (wx, wy), wheel_r, 2)
    # Pull handle (front)
    pygame.draw.line(surface, (72, 56, 38), (bed.left - int(16 * scale), y - h // 2),
                     (bed.left, y - h // 2), 2)
    pygame.draw.line(surface, (72, 56, 38), (bed.left - int(16 * scale), y - h // 2 - 4),
                     (bed.left - int(16 * scale), y - h // 2 + 4), 2)
    return pygame.Rect(x - w // 2 - int(16 * scale), y - h, w + int(16 * scale), h + 14)


def draw_fence_segment(surface: pygame.Surface, x: int, y: int, length: int = 128) -> pygame.Rect:
    rng = random.Random(x * 7 + y + length)
    h = 38
    # Shadow
    shad = pygame.Surface((length + 8, 12), pygame.SRCALPHA)
    pygame.draw.ellipse(shad, (0, 0, 0, 26), shad.get_rect())
    surface.blit(shad, (x - length // 2 - 4, y - 4))
    # Posts — gradient with pointed tops and grain
    post_spacing = 22
    for px in range(x - length // 2, x + length // 2 + 1, post_spacing):
        pw_p = 7
        for row in range(h):
            t = row / max(1, h - 1)
            shade = int(78 - 20 * t)
            pygame.draw.line(surface, (shade, int(shade * 0.72), int(shade * 0.50)),
                             (px - pw_p // 2, y - h + row), (px + pw_p // 2, y - h + row))
        pygame.draw.rect(surface, (34, 24, 16), (px - pw_p // 2, y - h, pw_p, h), 1)
        # Pointed top
        pygame.draw.polygon(surface, (82, 62, 42), [
            (px - pw_p // 2, y - h), (px + pw_p // 2, y - h), (px, y - h - 6)])
        pygame.draw.polygon(surface, (36, 26, 18), [
            (px - pw_p // 2, y - h), (px + pw_p // 2, y - h), (px, y - h - 6)], 1)
        # Grain
        for gy_f in range(y - h + 8, y - 6, 8):
            pygame.draw.line(surface, (52, 38, 26), (px - 2, gy_f), (px + 2, gy_f), 1)
    # Horizontal rails — gradient planks
    for ry in (y - h + 10, y - h + 24):
        for row in range(5):
            t = row / 4.0
            shade = int(90 - 12 * t)
            pygame.draw.line(surface, (shade, int(shade * 0.72), int(shade * 0.50)),
                             (x - length // 2 + 1, ry + row), (x + length // 2 - 1, ry + row))
        pygame.draw.rect(surface, (34, 26, 18), (x - length // 2, ry, length, 5), 1, border_radius=1)
        # Nail heads at each post junction
        for px in range(x - length // 2, x + length // 2 + 1, post_spacing):
            pygame.draw.circle(surface, (72, 70, 66), (px, ry + 2), 1)
    return pygame.Rect(x - length // 2, y - h, length, h)


def draw_fence_segment_vertical(surface: pygame.Surface, x: int, y: int, length: int = 128) -> pygame.Rect:
    """Rotate `draw_fence_segment` into a vertical fence section."""
    tmp_w = max(32, int(length) + 16)
    tmp_h = 64
    tmp = pygame.Surface((tmp_w, tmp_h), pygame.SRCALPHA)
    _r = draw_fence_segment(tmp, tmp_w // 2, tmp_h - 8, length)
    rot = pygame.transform.rotate(tmp, 90)
    surface.blit(rot, (x - rot.get_width() // 2, y - rot.get_height() // 2))
    # Approximate collision rect (not used by default; decorative)
    return pygame.Rect(x - 20, y - length // 2, 40, length)


def draw_wattle_fence_segment(surface: pygame.Surface, x: int, y: int, length: int = 128, seed: int = 0) -> pygame.Rect:
    """Poor-town woven wattle fence (decorative)."""
    rng = random.Random(seed + x * 5 + y * 11 + length)
    h = 30
    # Shadow
    shad = pygame.Surface((length + 10, 10), pygame.SRCALPHA)
    pygame.draw.ellipse(shad, (0, 0, 0, 22), shad.get_rect())
    surface.blit(shad, (x - length // 2 - 5, y - 3))
    # Posts
    post_spacing = 26
    for px in range(x - length // 2, x + length // 2 + 1, post_spacing):
        for row in range(h + 6):
            t = row / max(1, h + 5)
            shade = int(74 - 16 * t) + rng.randint(-2, 2)
            pygame.draw.line(surface, (shade, int(shade * 0.72), int(shade * 0.52)),
                             (px - 2, y - h + row), (px + 2, y - h + row))
        pygame.draw.rect(surface, (34, 24, 16), (px - 2, y - h, 5, h + 6), 1)
    # Woven bands (alternating over/under)
    band_top = y - h + 8
    band_bot = y - 8
    for bi, by in enumerate(range(band_top, band_bot, 6)):
        c = 92 + rng.randint(-6, 8)
        col = (c, c - 18, c - 42)
        off = 10 if bi % 2 else 0
        for bx in range(x - length // 2 + off, x + length // 2 - 10, 20):
            pygame.draw.line(surface, col, (bx, by), (bx + 20, by), 3)
            pygame.draw.line(surface, (col[0] - 26, col[1] - 22, col[2] - 18), (bx, by + 1), (bx + 20, by + 1), 1)
    pygame.draw.rect(surface, (34, 24, 16), (x - length // 2, y - h, length, h), 1)
    return pygame.Rect(x - length // 2, y - h, length, h)


def draw_wattle_fence_segment_vertical(surface: pygame.Surface, x: int, y: int, length: int = 128, seed: int = 0) -> pygame.Rect:
    tmp_w = max(32, int(length) + 16)
    tmp_h = 56
    tmp = pygame.Surface((tmp_w, tmp_h), pygame.SRCALPHA)
    draw_wattle_fence_segment(tmp, tmp_w // 2, tmp_h - 8, length, seed=seed)
    rot = pygame.transform.rotate(tmp, 90)
    surface.blit(rot, (x - rot.get_width() // 2, y - rot.get_height() // 2))
    return pygame.Rect(x - 18, y - length // 2, 36, length)


def draw_low_stone_wall_segment(surface: pygame.Surface, x: int, y: int, length: int = 128, seed: int = 0) -> pygame.Rect:
    """Low dry-stone wall segment (decorative)."""
    rng = random.Random(seed + x * 7 + y * 13 + length)
    h = 22
    wall = pygame.Rect(x - length // 2, y - h, length, h)
    pygame.draw.rect(surface, (72, 70, 66), wall, border_radius=3)
    # Stone blocks
    for by in range(wall.top + 2, wall.bottom - 2, 9):
        off = 10 if ((by - wall.top) // 9) % 2 else 0
        for bx in range(wall.left + 2 + off, wall.right - 8, 20):
            bw = min(18, wall.right - bx - 2)
            sv = 74 + rng.randint(-10, 10)
            pygame.draw.rect(surface, (sv, sv - 2, sv - 6), (bx, by, bw, 7), border_radius=2)
            pygame.draw.rect(surface, (42, 40, 36), (bx, by, bw, 7), 1, border_radius=2)
    pygame.draw.rect(surface, (38, 36, 32), wall, 2, border_radius=3)
    return wall


def draw_low_stone_wall_segment_vertical(surface: pygame.Surface, x: int, y: int, length: int = 128, seed: int = 0) -> pygame.Rect:
    tmp_w = max(32, int(length) + 16)
    tmp_h = 54
    tmp = pygame.Surface((tmp_w, tmp_h), pygame.SRCALPHA)
    draw_low_stone_wall_segment(tmp, tmp_w // 2, tmp_h - 8, length, seed=seed)
    rot = pygame.transform.rotate(tmp, 90)
    surface.blit(rot, (x - rot.get_width() // 2, y - rot.get_height() // 2))
    return pygame.Rect(x - 14, y - length // 2, 28, length)

def draw_cubic_stone_road(surface: pygame.Surface, rect: pygame.Rect, seed: int = 0) -> None:
    rng = random.Random(seed)
    # Base grout/dirt
    pygame.draw.rect(surface, (38, 36, 34), rect, border_radius=16)
    
    stone_size = 14
    gap = 2
    
    rows = rect.height // (stone_size + gap)
    cols = rect.width // (stone_size + gap)
    
    start_x = rect.left + (rect.width - (cols * (stone_size + gap))) // 2
    start_y = rect.top + (rect.height - (rows * (stone_size + gap))) // 2
    
    for r in range(rows):
        row_y = start_y + r * (stone_size + gap)
        # Offset every other row for running bond pattern
        x_offset = (stone_size // 2) if r % 2 == 1 else 0
        
        for c in range(cols):
            stone_x = start_x + c * (stone_size + gap) + x_offset
            if stone_x + stone_size > rect.right: continue
            if stone_x < rect.left: continue
            
            # Color variation for cubic stones
            shade = rng.randint(60, 85)
            color = (shade, shade + 2, shade + 5)
            
            s_rect = pygame.Rect(stone_x, row_y, stone_size, stone_size)
            pygame.draw.rect(surface, color, s_rect, border_radius=2)
            # Highlight top-left
            pygame.draw.line(surface, (shade+30, shade+32, shade+35), (s_rect.left+1, s_rect.top+1), (s_rect.right-1, s_rect.top+1))
            pygame.draw.line(surface, (shade+30, shade+32, shade+35), (s_rect.left+1, s_rect.top+1), (s_rect.left+1, s_rect.bottom-1))

    # Border
    pygame.draw.rect(surface, (26, 24, 22), rect, 2, border_radius=16)

def draw_stocks(surface: pygame.Surface, x: int, y: int) -> pygame.Rect:
    rng = random.Random(x + y * 19)
    # Shadow
    shad = pygame.Surface((80, 12), pygame.SRCALPHA)
    pygame.draw.ellipse(shad, (0, 0, 0, 30), shad.get_rect())
    surface.blit(shad, (x - 40, y - 3))
    # Posts — gradient with grain
    for px_off in (-35, 30):
        for row in range(44):
            t = row / 43.0
            shade = int(72 - 18 * t)
            pygame.draw.line(surface, (shade, int(shade * 0.70), int(shade * 0.48)),
                             (x + px_off, y - 44 + row), (x + px_off + 6, y - 44 + row))
        pygame.draw.rect(surface, (34, 22, 14), (x + px_off, y - 44, 6, 44), 1)
    # Top board — planked
    for row in range(8):
        t = row / 7.0
        shade = int(76 - 14 * t)
        pygame.draw.line(surface, (shade, int(shade * 0.72), int(shade * 0.50)),
                         (x - 34, y - 42 + row), (x + 34, y - 42 + row))
    pygame.draw.rect(surface, (34, 22, 14), (x - 34, y - 42, 68, 8), 1, border_radius=1)
    # Bottom board
    for row in range(8):
        t = row / 7.0
        shade = int(72 - 14 * t)
        pygame.draw.line(surface, (shade, int(shade * 0.70), int(shade * 0.48)),
                         (x - 34, y - 22 + row), (x + 34, y - 22 + row))
    pygame.draw.rect(surface, (34, 22, 14), (x - 34, y - 22, 68, 8), 1, border_radius=1)
    # Holes (semicircles cut from each board)
    for hx in (x - 15, x, x + 15):
        pygame.draw.circle(surface, (16, 10, 8), (hx, y - 34), 7)
        pygame.draw.circle(surface, (8, 4, 2), (hx, y - 34), 7, 1)
        # Wear marks around holes
        pygame.draw.circle(surface, (52, 38, 26), (hx, y - 34), 8, 1)
    # Iron hinges
    pygame.draw.rect(surface, (66, 64, 60), (x - 34, y - 36, 8, 4))
    pygame.draw.rect(surface, (66, 64, 60), (x + 26, y - 36, 8, 4))
    pygame.draw.circle(surface, (86, 84, 80), (x - 30, y - 34), 1)
    pygame.draw.circle(surface, (86, 84, 80), (x + 30, y - 34), 1)
    # Iron lock on right side
    pygame.draw.rect(surface, (58, 56, 52), (x + 34, y - 38, 6, 8))
    pygame.draw.circle(surface, (78, 76, 72), (x + 37, y - 34), 2)
    return pygame.Rect(x - 38, y - 8, 76, 10)

def draw_gallows(surface: pygame.Surface, x: int, y: int) -> pygame.Rect:
    rng = random.Random(x * 43 + y)
    # Shadow
    shad = pygame.Surface((92, 14), pygame.SRCALPHA)
    pygame.draw.ellipse(shad, (0, 0, 0, 28), shad.get_rect())
    surface.blit(shad, (x - 46, y - 4))
    # Wooden platform — planked with grain
    pw, ph = 80, 20
    for row in range(ph):
        t = row / max(1, ph - 1)
        shade = int(74 - 18 * t)
        pygame.draw.line(surface, (shade, int(shade * 0.72), int(shade * 0.50)),
                         (x - pw // 2, y - ph + row), (x + pw // 2, y - ph + row))
    # Plank seams
    for px_off in range(-pw // 2 + 16, pw // 2, 16):
        pygame.draw.line(surface, (38, 28, 18), (x + px_off, y - ph + 1), (x + px_off, y - 1), 1)
    pygame.draw.rect(surface, (36, 26, 18), (x - pw // 2, y - ph, pw, ph), 1)
    # Upright post — gradient with grain
    post_w, post_h = 8, 64
    for row in range(post_h):
        t = row / max(1, post_h - 1)
        shade = int(68 - 18 * t)
        pygame.draw.line(surface, (shade, int(shade * 0.70), int(shade * 0.44)),
                         (x + 20, y - ph - row), (x + 20 + post_w, y - ph - row))
    pygame.draw.rect(surface, (32, 24, 16), (x + 20, y - ph - post_h, post_w, post_h), 1)
    # Grain on post
    for gy_g in range(y - ph - post_h + 6, y - ph - 4, 8):
        pygame.draw.line(surface, (46, 34, 22), (x + 21, gy_g), (x + 20 + post_w - 1, gy_g), 1)
    # Cross beam — gradient
    beam_w, beam_h = 48, 7
    for row in range(beam_h):
        t = row / max(1, beam_h - 1)
        shade = int(66 - 14 * t)
        pygame.draw.line(surface, (shade, int(shade * 0.70), int(shade * 0.44)),
                         (x - 22, y - ph - post_h + row), (x + 22, y - ph - post_h + row))
    pygame.draw.rect(surface, (32, 24, 16), (x - 22, y - ph - post_h, beam_w, beam_h), 1)
    # Brace strut — diagonal support
    pygame.draw.line(surface, (58, 42, 28), (x + 20, y - ph - post_h + 16), (x + 4, y - ph - post_h + 2), 2)
    # Rope — braided texture
    rope_top = y - ph - post_h + 4
    rope_bot = y - ph - 18
    for ry_r in range(rope_top, rope_bot):
        t = (ry_r - rope_top) / max(1.0, rope_bot - rope_top)
        rx_off = int(math.sin(ry_r * 0.8) * 1)
        shade = 172 + int(math.sin(ry_r * 1.2) * 12)
        pygame.draw.line(surface, (shade, shade - 8, shade - 24),
                         (x - 18 + rx_off, ry_r), (x - 16 + rx_off, ry_r))
    # Noose loop
    pygame.draw.circle(surface, (168, 160, 140), (x - 17, rope_bot + 4), 5, 2)
    pygame.draw.circle(surface, (148, 140, 120), (x - 17, rope_bot + 4), 5, 1)
    return pygame.Rect(x - pw // 2, y - 6, pw, 8)

def draw_weapon_rack(surface: pygame.Surface, x: int, y: int) -> pygame.Rect:
    rng = random.Random(x * 23 + y)
    # Shadow
    shad = pygame.Surface((50, 10), pygame.SRCALPHA)
    pygame.draw.ellipse(shad, (0, 0, 0, 28), shad.get_rect())
    surface.blit(shad, (x - 25, y - 3))
    # Back board — gradient wood
    bw, bh = 46, 34
    for row in range(bh):
        t = row / max(1, bh - 1)
        shade = int(78 - 18 * t)
        pygame.draw.line(surface, (shade, int(shade * 0.72), int(shade * 0.50)),
                         (x - bw // 2, y - bh + row), (x + bw // 2, y - bh + row))
    pygame.draw.rect(surface, (36, 26, 18), (x - bw // 2, y - bh, bw, bh), 1, border_radius=1)
    # Pegs for holding weapons
    for peg_x in (x - 14, x, x + 14):
        pygame.draw.rect(surface, (68, 52, 36), (peg_x - 1, y - bh + 6, 3, 6))
        pygame.draw.rect(surface, (68, 52, 36), (peg_x - 1, y - bh + 20, 3, 6))
    # Weapons — sword, spear, axe
    weapons = [(x - 14, "sword"), (x, "spear"), (x + 14, "axe")]
    for wx, wtype in weapons:
        if wtype == "sword":
            # Blade — gradient steel
            for row in range(30):
                t = row / 29.0
                s = int(148 + 20 * math.sin(t * math.pi))
                pygame.draw.line(surface, (s, s, s + 8), (wx - 1, y - bh - 4 + row), (wx + 1, y - bh - 4 + row))
            # Guard
            pygame.draw.rect(surface, (72, 70, 66), (wx - 4, y - bh + 24, 8, 3))
            # Grip
            pygame.draw.rect(surface, (82, 54, 32), (wx - 1, y - bh + 27, 3, 8))
        elif wtype == "spear":
            # Shaft
            pygame.draw.line(surface, (88, 66, 44), (wx, y - bh - 8), (wx, y - 2), 2)
            pygame.draw.line(surface, (72, 52, 34), (wx + 1, y - bh - 8), (wx + 1, y - 2), 1)
            # Spear head — leaf-shaped
            pygame.draw.polygon(surface, (158, 158, 166), [
                (wx, y - bh - 16), (wx - 3, y - bh - 6), (wx + 3, y - bh - 6)])
            pygame.draw.polygon(surface, (118, 118, 126), [
                (wx, y - bh - 16), (wx - 3, y - bh - 6), (wx + 3, y - bh - 6)], 1)
        else:  # axe
            # Handle
            pygame.draw.line(surface, (82, 60, 38), (wx, y - bh - 2), (wx, y - 2), 2)
            # Axe head — curved blade
            pygame.draw.polygon(surface, (142, 140, 148), [
                (wx + 1, y - bh - 2), (wx + 8, y - bh + 2), (wx + 8, y - bh + 10), (wx + 1, y - bh + 8)])
            pygame.draw.polygon(surface, (102, 100, 108), [
                (wx + 1, y - bh - 2), (wx + 8, y - bh + 2), (wx + 8, y - bh + 10), (wx + 1, y - bh + 8)], 1)
            # Edge highlight
            pygame.draw.line(surface, (178, 176, 182), (wx + 8, y - bh + 3), (wx + 8, y - bh + 9), 1)
    return pygame.Rect(x - bw // 2, y - 6, bw, 8)

def draw_fountain(surface: pygame.Surface, x: int, y: int) -> pygame.Rect:
    rng = random.Random(x * 47 + y)
    w, h = 80, 40
    rect = pygame.Rect(x - w // 2, y - h, w, h)
    # Shadow
    shad = pygame.Surface((w + 16, 18), pygame.SRCALPHA)
    pygame.draw.ellipse(shad, (0, 0, 0, 24), shad.get_rect())
    surface.blit(shad, (x - w // 2 - 8, y - 6))
    # Basin — gradient stone with mortar lines
    for ring in range(4):
        t = ring / 3.0
        shade = int(80 - 12 * t)
        r = rect.inflate(-ring * 2, -ring * 2)
        pygame.draw.ellipse(surface, (shade, shade + 2, shade + 4), r)
    # Stone block detail on rim
    for i in range(12):
        ang = (i / 12.0) * math.tau
        sx_f = x + int(math.cos(ang) * (w // 2 - 2))
        sy_f = y - h // 2 + int(math.sin(ang) * (h // 2 - 2))
        shade = 76 + rng.randint(-6, 6)
        pygame.draw.circle(surface, (shade, shade + 2, shade + 4), (sx_f, sy_f), 4)
    pygame.draw.ellipse(surface, (42, 44, 48), rect, 2)
    # Water surface — rippled blue
    water_rect = rect.inflate(-12, -12)
    for row in range(water_rect.height):
        t = row / max(1, water_rect.height - 1)
        ripple = math.sin(row * 0.8) * 6
        r_w = int(36 + ripple)
        g_w = int(76 + 12 * math.sin(t * math.pi) + ripple)
        b_w = int(116 + 14 * math.sin(t * math.pi * 0.5))
        pygame.draw.line(surface, (r_w, g_w, b_w),
                         (water_rect.left + 2, water_rect.top + row),
                         (water_rect.right - 2, water_rect.top + row))
    # Water highlight specks
    for _ in range(5):
        hx = x + rng.randint(-w // 4, w // 4)
        hy = y - h // 2 + rng.randint(-h // 4, h // 4)
        pygame.draw.circle(surface, (120, 160, 200), (hx, hy), 1)
    # Central column — gradient stone
    col_w, col_h = 18, 42
    for row in range(col_h):
        t = row / max(1, col_h - 1)
        shade = int(76 - 14 * t)
        half = int(col_w * 0.5 * (0.7 + 0.3 * math.sin(t * math.pi)))
        pygame.draw.line(surface, (shade, shade + 2, shade + 4),
                         (x - half, y - h - row), (x + half, y - h - row))
    # Column mortar lines
    for my in range(y - h - col_h + 8, y - h - 4, 8):
        pygame.draw.line(surface, (56, 58, 62), (x - 6, my), (x + 6, my), 1)
    # Top basin — smaller stone bowl
    top_rect = pygame.Rect(x - 20, y - h - col_h - 4, 40, 16)
    for ring in range(3):
        shade = 78 - ring * 4
        r_t = top_rect.inflate(-ring * 2, -ring * 2)
        pygame.draw.ellipse(surface, (shade, shade + 2, shade + 4), r_t)
    pygame.draw.ellipse(surface, (42, 44, 48), top_rect, 1)
    # Water in top basin
    pygame.draw.ellipse(surface, (42, 82, 126), top_rect.inflate(-6, -6))
    # Water spout streams (falling water)
    for spout_x in (x - 8, x + 8):
        for drop in range(8):
            dy = y - h - col_h + 10 + drop * 4
            alpha = max(0, 120 - drop * 14)
            ds = pygame.Surface((4, 3), pygame.SRCALPHA)
            pygame.draw.ellipse(ds, (80, 140, 200, alpha), ds.get_rect())
            surface.blit(ds, (spout_x - 2, dy))
    return rect

def draw_laundry_line(surface: pygame.Surface, x: int, y: int, width: int = 100) -> None:
    rng = random.Random(x * 31 + y)
    h = 52
    # Poles — gradient with grain
    for pole_x in (x, x + width):
        for row in range(h):
            t = row / max(1, h - 1)
            shade = int(92 - 22 * t)
            pygame.draw.line(surface, (shade, int(shade * 0.76), int(shade * 0.56)),
                             (pole_x, y - h + row), (pole_x + 4, y - h + row))
        pygame.draw.rect(surface, (42, 32, 22), (pole_x, y - h, 5, h), 1)
        # Pole cap
        pygame.draw.rect(surface, (80, 64, 46), (pole_x - 1, y - h - 2, 7, 3))
    # Rope — smooth catenary
    num_seg = 16
    points = []
    for i in range(num_seg + 1):
        t = i / float(num_seg)
        rx = x + 2 + t * width
        sag_amt = 12.0 * math.sin(t * math.pi)
        ry = y - h + 5 + sag_amt
        points.append((int(rx), int(ry)))
    for i in range(len(points) - 1):
        pygame.draw.line(surface, (186, 178, 160), points[i], points[i + 1], 2)
    # Clothes — varied garments with folds
    garment_defs = [
        {"w": 16, "h": 22, "col": (188, 186, 210), "kind": "shirt"},
        {"w": 20, "h": 18, "col": (172, 148, 124), "kind": "cloth"},
        {"w": 14, "h": 26, "col": (134, 130, 158), "kind": "tunic"},
        {"w": 18, "h": 16, "col": (164, 152, 136), "kind": "rag"},
    ]
    spacing = max(1, width // (len(garment_defs) + 1))
    for gi, gdef in enumerate(garment_defs):
        if spacing * (gi + 1) > width - 10:
            break
        t_g = (gi + 1) / float(len(garment_defs) + 1)
        gx = x + 2 + int(t_g * width)
        sag_g = 12.0 * math.sin(t_g * math.pi)
        gy = int(y - h + 5 + sag_g)
        gw, gh = gdef["w"], gdef["h"]
        col = gdef["col"]
        # Garment body with fold gradient
        for row in range(gh):
            fold = math.sin(row * 0.6 + gi) * 6
            r = max(0, min(255, int(col[0] + fold)))
            g = max(0, min(255, int(col[1] + fold)))
            b = max(0, min(255, int(col[2] + fold)))
            pygame.draw.line(surface, (r, g, b), (gx, gy + row), (gx + gw, gy + row))
        pygame.draw.rect(surface, (max(0, col[0] - 26), max(0, col[1] - 26), max(0, col[2] - 26)),
                         (gx, gy, gw, gh), 1)
        # Clothespin
        pygame.draw.rect(surface, (148, 126, 88), (gx + gw // 2 - 1, gy - 3, 3, 5))

def draw_wooden_bench(surface: pygame.Surface, x: int, y: int, flip: bool = False) -> pygame.Rect:
    """HD wooden bench — planked seat with wood grain and iron bolts."""
    rng = random.Random(x * 31 + y)
    # Shadow
    shad = pygame.Surface((56, 14), pygame.SRCALPHA)
    pygame.draw.ellipse(shad, (0, 0, 0, 36), shad.get_rect())
    surface.blit(shad, (x - 28, y - 5))
    # Legs — tapered with gradient shading
    for lx_off in (-20, 16):
        lx = x + lx_off
        for row in range(22):
            t = row / 21.0
            shade = int(72 - 18 * t)
            pygame.draw.line(surface, (shade, int(shade * 0.72), int(shade * 0.52)),
                             (lx, y - 22 + row), (lx + 5, y - 22 + row))
        pygame.draw.rect(surface, (36, 26, 18), (lx, y - 22, 6, 22), 1)
        # Iron bolt on leg
        pygame.draw.circle(surface, (92, 90, 86), (lx + 3, y - 14), 2)
        pygame.draw.circle(surface, (62, 60, 56), (lx + 3, y - 14), 2, 1)
    # Cross brace between legs
    pygame.draw.line(surface, (68, 48, 32), (x - 17, y - 6), (x + 19, y - 6), 2)
    pygame.draw.line(surface, (52, 36, 24), (x - 17, y - 5), (x + 19, y - 5), 1)
    # Seat — 3 planks with individual grain
    seat_y = y - 24
    for pi, pw in enumerate([16, 14, 16]):
        plank_x = x - 24 + pi * 16
        base = 100 + rng.randint(-8, 8)
        for col_off in range(pw):
            cx = plank_x + col_off
            curve = abs(col_off - pw // 2) / max(1, pw // 2)
            s = max(0, int(base - curve * 18))
            pygame.draw.line(surface, (s, int(s * 0.72), int(s * 0.48)),
                             (cx, seat_y), (cx, seat_y + 6))
        # Grain lines
        for _ in range(2):
            gy = seat_y + rng.randint(1, 4)
            pygame.draw.line(surface, (base - 20, int((base - 20) * 0.7), int((base - 20) * 0.46)),
                             (plank_x + 1, gy), (plank_x + pw - 2, gy), 1)
    pygame.draw.rect(surface, (38, 28, 18), (x - 24, seat_y, 48, 7), 1, border_radius=1)
    # Backrest (optional)
    if not flip:
        for lx_off in (-22, 18):
            pygame.draw.rect(surface, (82, 58, 38), (x + lx_off, y - 42, 5, 20))
            pygame.draw.rect(surface, (38, 28, 18), (x + lx_off, y - 42, 5, 20), 1)
        # Two back planks
        for bi, by_off in enumerate([-44, -38]):
            base = 96 + bi * 6
            pygame.draw.rect(surface, (base, int(base * 0.72), int(base * 0.48)),
                             (x - 22, y + by_off, 45, 5), border_radius=1)
            pygame.draw.rect(surface, (38, 28, 18), (x - 22, y + by_off, 45, 5), 1, border_radius=1)
            # Grain
            pygame.draw.line(surface, (base - 14, int((base - 14) * 0.7), int((base - 14) * 0.46)),
                             (x - 18, y + by_off + 2), (x + 18, y + by_off + 2), 1)
    return pygame.Rect(x - 24, y - 6, 48, 8)


def draw_water_trough(surface: pygame.Surface, x: int, y: int) -> pygame.Rect:
    """HD stone water trough — chiselled stone with water reflections."""
    rng = random.Random(x + y * 17)
    # Shadow
    shad = pygame.Surface((68, 16), pygame.SRCALPHA)
    pygame.draw.ellipse(shad, (0, 0, 0, 32), shad.get_rect())
    surface.blit(shad, (x - 34, y - 4))
    # Stone body — gradient fill with chisel marks
    bw, bh = 62, 22
    for row in range(bh):
        t = row / max(1, bh - 1)
        shade = int(86 - 20 * t)
        pygame.draw.line(surface, (shade, shade - 4, shade - 8),
                         (x - bw // 2, y - bh + row), (x + bw // 2, y - bh + row))
    # Chisel/crack lines
    for _ in range(6):
        cx = x + rng.randint(-bw // 2 + 4, bw // 2 - 4)
        cy = y - bh + rng.randint(4, bh - 4)
        pygame.draw.line(surface, (56, 52, 48), (cx, cy), (cx + rng.randint(-6, 6), cy + rng.randint(-2, 2)), 1)
    pygame.draw.rect(surface, (44, 40, 36), (x - bw // 2, y - bh, bw, bh), 2, border_radius=2)
    # Stone feet with bevelled top
    for fx in (x - 26, x + 20):
        pygame.draw.rect(surface, (72, 68, 64), (fx, y - 4, 10, 6))
        pygame.draw.line(surface, (92, 88, 84), (fx, y - 4), (fx + 10, y - 4), 1)
        pygame.draw.rect(surface, (44, 40, 36), (fx, y - 4, 10, 6), 1)
    # Water surface — layered blue with reflections
    water_r = pygame.Rect(x - bw // 2 + 6, y - bh + 4, bw - 12, bh - 8)
    for wy in range(water_r.height):
        t = wy / max(1, water_r.height - 1)
        b = int(68 + 30 * t)
        pygame.draw.line(surface, (24 + int(8 * t), 42 + int(12 * t), b),
                         (water_r.left, water_r.top + wy), (water_r.right, water_r.top + wy))
    # Ripple highlights
    for _ in range(3):
        rx = water_r.left + rng.randint(4, water_r.width - 8)
        ry = water_r.top + rng.randint(2, water_r.height - 4)
        pygame.draw.line(surface, (58, 82, 118), (rx, ry), (rx + rng.randint(4, 12), ry), 1)
    # Rim highlight
    pygame.draw.line(surface, (98, 94, 88), (x - bw // 2 + 2, y - bh + 1), (x + bw // 2 - 2, y - bh + 1), 1)
    return pygame.Rect(x - bw // 2, y - 6, bw, 8)


def draw_notice_board(surface: pygame.Surface, x: int, y: int) -> pygame.Rect:
    """HD town notice board — weathered wood with pinned parchments."""
    rng = random.Random(x * 7 + y)
    # Shadow
    shad = pygame.Surface((48, 12), pygame.SRCALPHA)
    pygame.draw.ellipse(shad, (0, 0, 0, 32), shad.get_rect())
    surface.blit(shad, (x - 24, y - 4))
    # Posts — gradient wood with knots
    for px_off in (-16, 14):
        px = x + px_off
        for row in range(58):
            t = row / 57.0
            shade = int(74 - 20 * t)
            pygame.draw.line(surface, (shade, int(shade * 0.74), int(shade * 0.52)),
                             (px, y - 58 + row), (px + 5, y - 58 + row))
        pygame.draw.rect(surface, (34, 24, 16), (px, y - 58, 6, 58), 1)
        # Knot
        ky = y - 58 + rng.randint(20, 40)
        pygame.draw.circle(surface, (52, 36, 24), (px + 3, ky), 2)
    # Board — planked with grain
    bw, bh = 42, 34
    bx, by = x - bw // 2, y - 56
    for pi in range(3):
        pw = bw // 3
        plank_x = bx + pi * pw
        base = 88 + rng.randint(-6, 6)
        for col_off in range(pw):
            cx_p = plank_x + col_off
            curve = abs(col_off - pw // 2) / max(1, pw // 2)
            s = max(0, int(base - curve * 14))
            pygame.draw.line(surface, (s, int(s * 0.74), int(s * 0.50)),
                             (cx_p, by), (cx_p, by + bh))
        # Grain
        for _ in range(2):
            gy = by + rng.randint(3, bh - 4)
            pygame.draw.line(surface, (base - 18, int((base - 18) * 0.72), int((base - 18) * 0.48)),
                             (plank_x + 1, gy), (plank_x + pw - 2, gy), 1)
    pygame.draw.rect(surface, (38, 28, 18), (bx, by, bw, bh), 2, border_radius=1)
    # Iron corner brackets
    for cx_b, cy_b in [(bx + 1, by + 1), (bx + bw - 5, by + 1), (bx + 1, by + bh - 5), (bx + bw - 5, by + bh - 5)]:
        pygame.draw.rect(surface, (72, 70, 66), (cx_b, cy_b, 4, 4))
        pygame.draw.circle(surface, (92, 90, 86), (cx_b + 2, cy_b + 2), 1)
    # Pinned parchments with wax seals and text
    papers = [(bx + 4, by + 4, 12, 14, (196, 186, 162)), (bx + 18, by + 6, 14, 12, (206, 194, 168)),
              (bx + 8, by + 18, 10, 12, (188, 178, 154)), (bx + 22, by + 20, 12, 10, (200, 188, 162))]
    for ppx, ppy, ppw, pph, pc in papers:
        pygame.draw.rect(surface, pc, (ppx, ppy, ppw, pph))
        pygame.draw.rect(surface, (pc[0] - 30, pc[1] - 30, pc[2] - 30), (ppx, ppy, ppw, pph), 1)
        # Text lines
        for ty in range(ppy + 3, ppy + pph - 3, 3):
            lw = rng.randint(ppw // 2, ppw - 4)
            pygame.draw.line(surface, (82, 76, 64), (ppx + 2, ty), (ppx + 2 + lw, ty), 1)
        # Pin/nail
        pygame.draw.circle(surface, (72, 70, 66), (ppx + ppw // 2, ppy + 1), 1)
    # Wax seal on one
    pygame.draw.circle(surface, (148, 32, 28), (bx + 24, by + 12), 3)
    pygame.draw.circle(surface, (180, 48, 42), (bx + 24, by + 12), 2)
    return pygame.Rect(x - bw // 2, y - 8, bw, 10)


def draw_woodpile(surface: pygame.Surface, x: int, y: int) -> pygame.Rect:
    """HD stacked firewood — bark texture, heartwood rings, axe marks."""
    rng = random.Random(x * 13 + y)
    # Shadow
    shad = pygame.Surface((52, 12), pygame.SRCALPHA)
    pygame.draw.ellipse(shad, (0, 0, 0, 30), shad.get_rect())
    surface.blit(shad, (x - 26, y - 4))
    # Log rows: bottom 6, middle 5, top 4
    rows = [(6, 0), (5, -12), (4, -23)]
    for count, y_off in rows:
        for i in range(count):
            lx = x - (count * 9) // 2 + i * 9
            ly = y + y_off - 6
            bark = rng.randint(56, 78)
            # Bark circle (outer)
            pygame.draw.circle(surface, (bark, int(bark * 0.72), int(bark * 0.50)), (lx, ly), 6)
            # Heartwood (inner rings)
            hw = bark + 18
            pygame.draw.circle(surface, (hw, int(hw * 0.76), int(hw * 0.54)), (lx, ly), 4)
            pygame.draw.circle(surface, (hw + 10, int((hw + 10) * 0.78), int((hw + 10) * 0.56)), (lx, ly), 2)
            # Ring lines
            pygame.draw.circle(surface, (bark - 10, int((bark - 10) * 0.7), int((bark - 10) * 0.48)), (lx, ly), 5, 1)
            pygame.draw.circle(surface, (bark - 10, int((bark - 10) * 0.7), int((bark - 10) * 0.48)), (lx, ly), 3, 1)
            # Bark outline
            pygame.draw.circle(surface, (bark - 20, int((bark - 20) * 0.68), int((bark - 20) * 0.46)), (lx, ly), 6, 1)
            # Axe mark (occasional)
            if rng.random() < 0.3:
                pygame.draw.line(surface, (bark - 16, int((bark - 16) * 0.7), int((bark - 16) * 0.48)),
                                 (lx - 2, ly - 4), (lx + 1, ly - 1), 1)
    return pygame.Rect(x - 28, y - 6, 56, 8)


def draw_flower_box(surface: pygame.Surface, x: int, y: int, seed: int = 0) -> pygame.Rect:
    """HD planter box — wood grain box, soil texture, detailed flowers with leaves."""
    rng = random.Random(seed)
    # Box — planked sides with grain
    bw, bh = 38, 14
    bx, by = x - bw // 2, y - bh
    for pi in range(3):
        pw = bw // 3 + (1 if pi < bw % 3 else 0)
        plank_x = bx + pi * (bw // 3)
        base = 78 + rng.randint(-6, 6)
        for col_off in range(pw):
            cx_p = plank_x + col_off
            if cx_p >= bx + bw:
                break
            curve = abs(col_off - pw // 2) / max(1, pw // 2)
            s = max(0, int(base - curve * 12))
            pygame.draw.line(surface, (s, int(s * 0.72), int(s * 0.50)),
                             (cx_p, by), (cx_p, by + bh))
    pygame.draw.rect(surface, (38, 28, 18), (bx, by, bw, bh), 1, border_radius=1)
    # Soil — dark with texture specks
    soil_r = pygame.Rect(bx + 2, by + 2, bw - 4, 5)
    pygame.draw.rect(surface, (44, 36, 28), soil_r)
    for _ in range(8):
        pygame.draw.circle(surface, (38 + rng.randint(-6, 6), 30 + rng.randint(-4, 4), 22 + rng.randint(-4, 4)),
                           (soil_r.left + rng.randint(2, soil_r.width - 2), soil_r.top + rng.randint(1, 3)), 1)
    # Flowers — 5 with leaves and multi-petal detail
    flower_cols = [(186, 52, 56), (208, 184, 54), (156, 72, 164), (224, 136, 52), (112, 164, 206), (196, 88, 142)]
    for i in range(5):
        fx = bx + 4 + i * 7
        fy = by - rng.randint(6, 16)
        # Stem with curve
        mid_y = by + 1
        pygame.draw.line(surface, (42, 78, 34), (fx, mid_y), (fx + rng.randint(-2, 2), fy + 3), 2)
        # Leaf on stem
        if rng.random() < 0.6:
            ly = (mid_y + fy) // 2
            ldir = rng.choice([-1, 1])
            pygame.draw.polygon(surface, (52, 88, 40), [
                (fx, ly), (fx + ldir * 5, ly - 2), (fx + ldir * 4, ly + 2)])
        # Multi-petal flower
        col = flower_cols[rng.randint(0, len(flower_cols) - 1)]
        for pang in range(0, 360, 72):
            rad = math.radians(pang + rng.randint(-10, 10))
            px_f = fx + int(math.cos(rad) * 3)
            py_f = fy + int(math.sin(rad) * 2)
            pygame.draw.circle(surface, col, (px_f, py_f), 2)
        # Center
        pygame.draw.circle(surface, (min(col[0] + 50, 255), min(col[1] + 50, 255), min(col[2] + 30, 255)), (fx, fy), 1)
    return pygame.Rect(bx, y - 4, bw, 6)


def draw_rain_barrel(surface: pygame.Surface, x: int, y: int) -> pygame.Rect:
    """HD rain barrel — planked construction, metal hoops with rivets, water surface."""
    rng = random.Random(x * 11 + y)
    # Shadow
    shad = pygame.Surface((36, 12), pygame.SRCALPHA)
    pygame.draw.ellipse(shad, (0, 0, 0, 32), shad.get_rect())
    surface.blit(shad, (x - 18, y - 4))
    # Barrel body — 5 vertical planks with curvature shading
    bw, bh = 28, 36
    bx, by = x - bw // 2, y - bh
    plank_w = bw // 5
    for pi in range(5):
        px_p = bx + pi * plank_w
        base = 82 + rng.randint(-8, 8)
        for col_off in range(plank_w):
            cx_p = px_p + col_off
            curve = abs(col_off - plank_w // 2) / max(1, plank_w // 2)
            s = max(0, int(base - curve * 16))
            pygame.draw.line(surface, (s, int(s * 0.70), int(s * 0.48)),
                             (cx_p, by + 3), (cx_p, by + bh - 2))
        # Grain line
        gy = by + rng.randint(8, bh - 8)
        pygame.draw.line(surface, (base - 14, int((base - 14) * 0.68), int((base - 14) * 0.44)),
                         (px_p + 1, gy), (px_p + plank_w - 1, gy), 1)
    pygame.draw.rect(surface, (38, 28, 18), (bx, by + 2, bw, bh - 3), 1, border_radius=2)
    # Metal hoops — 3 with rivets
    for hy_off in (6, bh // 2, bh - 8):
        hy = by + hy_off
        pygame.draw.line(surface, (78, 76, 72), (bx + 1, hy), (bx + bw - 1, hy), 2)
        pygame.draw.line(surface, (98, 96, 92), (bx + 1, hy - 1), (bx + bw - 1, hy - 1), 1)  # Highlight
        # Rivets
        for ri in range(0, bw, plank_w):
            pygame.draw.circle(surface, (92, 90, 86), (bx + ri + plank_w // 2, hy), 1)
    # Open top — water visible
    pygame.draw.ellipse(surface, (38, 28, 18), (bx + 1, by, bw - 2, 8))  # Rim
    pygame.draw.ellipse(surface, (28, 48, 72), (bx + 3, by + 1, bw - 6, 6))  # Water
    # Water reflection highlight
    pygame.draw.line(surface, (42, 66, 98), (bx + 6, by + 3), (bx + bw - 8, by + 3), 1)
    return pygame.Rect(bx, y - 6, bw, 8)


def draw_sack_pile(surface: pygame.Surface, x: int, y: int) -> pygame.Rect:
    """HD grain sack pile — burlap texture, rope ties, spilled grain."""
    rng = random.Random(x * 23 + y)
    # Shadow
    shad = pygame.Surface((44, 12), pygame.SRCALPHA)
    pygame.draw.ellipse(shad, (0, 0, 0, 28), shad.get_rect())
    surface.blit(shad, (x - 22, y - 4))
    # Bottom sacks (2) — with burlap texture
    for sx_off, rot in [(-11, 0), (9, 1)]:
        sx_s = x + sx_off
        col_base = 148 + rng.randint(-10, 10)
        col = (col_base, int(col_base * 0.88), int(col_base * 0.66))
        dark = (col[0] - 30, col[1] - 30, col[2] - 30)
        pygame.draw.ellipse(surface, col, (sx_s - 12, y - 22, 22, 20))
        pygame.draw.ellipse(surface, dark, (sx_s - 12, y - 22, 22, 20), 1)
        # Burlap weave texture
        for _ in range(6):
            tx = sx_s + rng.randint(-8, 8)
            ty = y - 22 + rng.randint(4, 16)
            pygame.draw.line(surface, (col[0] - 12, col[1] - 12, col[2] - 10),
                             (tx, ty), (tx + rng.choice([-3, 3]), ty + rng.choice([-2, 2])), 1)
        # Rope tie
        neck_y = y - 22 + 4
        pygame.draw.line(surface, (110, 96, 68), (sx_s - 4, neck_y), (sx_s + 4, neck_y), 2)
        pygame.draw.line(surface, (126, 110, 78), (sx_s - 4, neck_y - 1), (sx_s + 4, neck_y - 1), 1)
    # Top sack — slightly tilted
    col_base = 144 + rng.randint(-6, 6)
    col = (col_base, int(col_base * 0.88), int(col_base * 0.66))
    pygame.draw.ellipse(surface, col, (x - 10, y - 34, 18, 16))
    pygame.draw.ellipse(surface, (col[0] - 28, col[1] - 28, col[2] - 28), (x - 10, y - 34, 18, 16), 1)
    # Burlap on top
    for _ in range(4):
        tx = x + rng.randint(-6, 6)
        ty = y - 34 + rng.randint(3, 12)
        pygame.draw.line(surface, (col[0] - 10, col[1] - 10, col[2] - 8),
                         (tx, ty), (tx + rng.choice([-2, 2]), ty + rng.choice([-2, 2])), 1)
    # Tie
    pygame.draw.line(surface, (110, 96, 68), (x - 3, y - 34), (x + 3, y - 33), 2)
    # Spilled grain on ground
    for _ in range(5):
        gx = x + rng.randint(-14, 14)
        gy = y - rng.randint(1, 5)
        pygame.draw.circle(surface, (168, 152, 98), (gx, gy), 1)
    return pygame.Rect(x - 22, y - 6, 44, 8)


def draw_stone_planter(surface: pygame.Surface, x: int, y: int, seed: int = 0) -> pygame.Rect:
    """HD stone planter — chiseled stone wall, soil, layered shrub with berries."""
    rng = random.Random(seed)
    # Shadow
    shad = pygame.Surface((44, 12), pygame.SRCALPHA)
    pygame.draw.ellipse(shad, (0, 0, 0, 28), shad.get_rect())
    surface.blit(shad, (x - 22, y - 4))
    # Stone ring — gradient with mortar lines
    ring_rx, ring_ry = 20, 10
    # Ring sides (3D depth)
    for h_off in range(6, 0, -1):
        shade = max(0, 62 - h_off * 3)
        pygame.draw.ellipse(surface, (shade, shade - 2, shade - 4),
                            (x - ring_rx, y - ring_ry + h_off, ring_rx * 2, ring_ry * 2))
    # Ring top
    pygame.draw.ellipse(surface, (86, 82, 78), (x - ring_rx, y - ring_ry, ring_rx * 2, ring_ry * 2))
    pygame.draw.ellipse(surface, (52, 48, 44), (x - ring_rx, y - ring_ry, ring_rx * 2, ring_ry * 2), 2)
    # Stone block detail
    for _ in range(4):
        ang = rng.uniform(0, math.tau)
        sr = ring_rx - 2
        sx_s = x + int(math.cos(ang) * sr * 0.8)
        sy_s = y - ring_ry // 2 + int(math.sin(ang) * ring_ry * 0.6)
        pygame.draw.line(surface, (56, 52, 48), (sx_s, sy_s), (sx_s + rng.randint(-4, 4), sy_s), 1)
    # Inner rim highlight
    pygame.draw.ellipse(surface, (96, 92, 86), (x - ring_rx + 2, y - ring_ry + 1, (ring_rx - 2) * 2, (ring_ry - 1) * 2), 1)
    # Soil
    pygame.draw.ellipse(surface, (48, 38, 30), (x - ring_rx + 4, y - ring_ry + 2, (ring_rx - 4) * 2, (ring_ry - 2) * 2))
    # Soil specks
    for _ in range(6):
        pygame.draw.circle(surface, (42 + rng.randint(-4, 4), 32 + rng.randint(-4, 4), 24 + rng.randint(-4, 4)),
                           (x + rng.randint(-10, 10), y - ring_ry // 2 + rng.randint(-3, 3)), 1)
    # Layered shrub — dark core, medium middle, bright outer
    layers = [(8, (30, 52, 28)), (6, (42, 68, 36)), (4, (54, 84, 44))]
    for radius, col in layers:
        for _ in range(5):
            bx = x + rng.randint(-8, 8)
            by_s = y - ring_ry - rng.randint(2, 12)
            r = rng.randint(radius - 1, radius + 1)
            pygame.draw.circle(surface, (col[0] + rng.randint(-8, 8), col[1] + rng.randint(-6, 6), col[2] + rng.randint(-6, 6)),
                               (bx, by_s), r)
    # Berries (occasional)
    for _ in range(rng.randint(0, 3)):
        bx = x + rng.randint(-6, 6)
        by_s = y - ring_ry - rng.randint(4, 10)
        pygame.draw.circle(surface, (168, 42, 38), (bx, by_s), 2)
        pygame.draw.circle(surface, (200, 68, 62), (bx - 1, by_s - 1), 1)
    return pygame.Rect(x - ring_rx, y - 6, ring_rx * 2, 8)


def draw_horse_hitch(surface: pygame.Surface, x: int, y: int) -> pygame.Rect:
    """HD hitching post — carved wood, iron ring, rope with knot."""
    rng = random.Random(x * 19 + y)
    # Shadow
    shad = pygame.Surface((50, 10), pygame.SRCALPHA)
    pygame.draw.ellipse(shad, (0, 0, 0, 28), shad.get_rect())
    surface.blit(shad, (x - 25, y - 3))
    # Main post — gradient with grain
    pw, ph = 8, 48
    px_p = x - pw // 2
    for row in range(ph):
        t = row / max(1, ph - 1)
        shade = int(82 - 22 * t)
        pygame.draw.line(surface, (shade, int(shade * 0.74), int(shade * 0.52)),
                         (px_p, y - ph + row), (px_p + pw, y - ph + row))
    pygame.draw.rect(surface, (36, 26, 18), (px_p, y - ph, pw, ph), 1)
    # Grain lines
    for gy in range(y - ph + 5, y - 5, 8):
        pygame.draw.line(surface, (62, 44, 30), (px_p + 1, gy), (px_p + pw - 1, gy), 1)
    # Carved top (bevelled/chamfered)
    pygame.draw.polygon(surface, (88, 66, 46), [
        (px_p - 1, y - ph), (px_p + pw + 1, y - ph), (px_p + pw // 2, y - ph - 6)])
    pygame.draw.polygon(surface, (42, 32, 22), [
        (px_p - 1, y - ph), (px_p + pw + 1, y - ph), (px_p + pw // 2, y - ph - 6)], 1)
    # Cross bar — gradient with grain
    cbw = 48
    for row in range(6):
        t = row / 5.0
        shade = int(86 - 14 * t)
        pygame.draw.line(surface, (shade, int(shade * 0.74), int(shade * 0.52)),
                         (x - cbw // 2, y - 38 + row), (x + cbw // 2, y - 38 + row))
    pygame.draw.rect(surface, (38, 28, 18), (x - cbw // 2, y - 38, cbw, 6), 1, border_radius=1)
    # Iron ring — thick with highlight
    pygame.draw.circle(surface, (64, 62, 58), (x, y - 28), 6, 3)
    pygame.draw.circle(surface, (96, 94, 88), (x - 1, y - 30), 2, 1)  # Highlight
    # Rope through ring — braided look
    rope_pts = [(x, y - 24), (x + 4, y - 18), (x + 8, y - 12), (x + 6, y - 6), (x + 4, y)]
    for i in range(len(rope_pts) - 1):
        pygame.draw.line(surface, (148, 132, 98), rope_pts[i], rope_pts[i + 1], 2)
        # Braid detail
        mid_x_r = (rope_pts[i][0] + rope_pts[i + 1][0]) // 2
        mid_y_r = (rope_pts[i][1] + rope_pts[i + 1][1]) // 2
        pygame.draw.line(surface, (132, 118, 86), (mid_x_r - 1, mid_y_r), (mid_x_r + 1, mid_y_r), 1)
    # Rope end knot
    pygame.draw.circle(surface, (142, 126, 92), (rope_pts[-1][0], rope_pts[-1][1]), 3)
    pygame.draw.circle(surface, (118, 104, 74), (rope_pts[-1][0], rope_pts[-1][1]), 3, 1)
    return pygame.Rect(x - cbw // 2, y - 6, cbw, 8)


def draw_well_bucket(surface: pygame.Surface, x: int, y: int) -> pygame.Rect:
    """HD wooden bucket — staved construction, iron bands, handle."""
    rng = random.Random(x * 7 + y)
    # Shadow
    shad = pygame.Surface((20, 8), pygame.SRCALPHA)
    pygame.draw.ellipse(shad, (0, 0, 0, 30), shad.get_rect())
    surface.blit(shad, (x - 10, y - 3))
    # Bucket body — 4 staves
    bw, bh = 16, 16
    bx = x - bw // 2
    by_b = y - bh
    stave_w = bw // 4
    for si in range(4):
        sx_s = bx + si * stave_w
        base = 78 + rng.randint(-8, 8)
        for col_off in range(stave_w):
            cx_p = sx_s + col_off
            curve = abs(col_off - stave_w // 2) / max(1, stave_w // 2)
            s = max(0, int(base - curve * 14))
            pygame.draw.line(surface, (s, int(s * 0.70), int(s * 0.48)),
                             (cx_p, by_b + 2), (cx_p, by_b + bh - 1))
    pygame.draw.rect(surface, (36, 26, 18), (bx, by_b + 1, bw, bh - 1), 1, border_radius=1)
    # Iron bands — 2 with rivets
    for hy_off in (4, bh - 5):
        hy_b = by_b + hy_off
        pygame.draw.line(surface, (76, 74, 70), (bx + 1, hy_b), (bx + bw - 1, hy_b), 2)
        pygame.draw.line(surface, (96, 94, 88), (bx + 1, hy_b - 1), (bx + bw - 1, hy_b - 1), 1)
        # Rivets
        pygame.draw.circle(surface, (88, 86, 82), (bx + 2, hy_b), 1)
        pygame.draw.circle(surface, (88, 86, 82), (bx + bw - 2, hy_b), 1)
    # Handle — iron arc with grip
    pygame.draw.arc(surface, (72, 70, 66), (x - 6, by_b - 8, 12, 12), 0, math.pi, 2)
    pygame.draw.arc(surface, (96, 94, 88), (x - 6, by_b - 9, 12, 12), 0.3, 2.5, 1)  # Highlight
    # Rim (top ellipse)
    pygame.draw.ellipse(surface, (68, 48, 32), (bx + 1, by_b, bw - 2, 5))
    pygame.draw.ellipse(surface, (38, 28, 18), (bx + 1, by_b, bw - 2, 5), 1)
    return pygame.Rect(bx, y - 4, bw, 6)


def draw_hanging_sign(surface: pygame.Surface, x: int, y: int, seed: int = 0) -> pygame.Rect:
    """HD hanging sign — wrought iron bracket, chain links, painted board."""
    rng = random.Random(seed)
    # Wrought iron bracket — ornate L-shape with scroll
    # Vertical piece
    for row in range(24):
        shade = 66 + int(math.sin(row * 0.5) * 6)
        pygame.draw.line(surface, (shade, shade - 2, shade - 4), (x - 2, y - 44 + row), (x + 2, y - 44 + row))
    # Horizontal arm with scroll tip
    for row in range(4):
        shade = 68 + row * 2
        pygame.draw.line(surface, (shade, shade - 2, shade - 4), (x, y - 44 + row), (x + 28, y - 44 + row))
    # Scroll curl at end
    pygame.draw.arc(surface, (72, 70, 66), (x + 24, y - 48, 10, 10), -math.pi / 2, math.pi, 2)
    # Scroll curl at bracket joint
    pygame.draw.arc(surface, (68, 66, 62), (x - 6, y - 24, 8, 8), math.pi / 2, math.pi * 1.5, 1)
    # Chains — individual links
    for chain_x_off in (8, 22):
        cx_c = x + chain_x_off
        for li in range(4):
            ly = y - 40 + li * 4
            pygame.draw.ellipse(surface, (78, 76, 72), (cx_c - 2, ly, 4, 5), 1)
            pygame.draw.line(surface, (96, 94, 88), (cx_c, ly + 1), (cx_c, ly + 1), 1)  # Link highlight
    # Sign board — wood with iron frame
    sign_w, sign_h = 26, 18
    sx_s = x + 3
    sy_s = y - 24
    # Board planks
    for pi in range(2):
        plank_x = sx_s + pi * (sign_w // 2)
        pw = sign_w // 2
        base = rng.choice([78, 72, 82])
        for col_off in range(pw):
            cx_p = plank_x + col_off
            if cx_p >= sx_s + sign_w:
                break
            curve = abs(col_off - pw // 2) / max(1, pw // 2)
            s = max(0, int(base - curve * 12))
            pygame.draw.line(surface, (s, int(s * 0.72), int(s * 0.50)),
                             (cx_p, sy_s), (cx_p, sy_s + sign_h))
    # Iron frame
    pygame.draw.rect(surface, (56, 54, 50), (sx_s, sy_s, sign_w, sign_h), 2, border_radius=1)
    # Iron corner rivets
    for crx, cry in [(sx_s + 2, sy_s + 2), (sx_s + sign_w - 3, sy_s + 2),
                     (sx_s + 2, sy_s + sign_h - 3), (sx_s + sign_w - 3, sy_s + sign_h - 3)]:
        pygame.draw.circle(surface, (86, 84, 80), (crx, cry), 1)
    # Painted symbol — gold on dark
    sym_cx = sx_s + sign_w // 2
    sym_cy = sy_s + sign_h // 2
    gold = (196, 168, 82)
    gold_d = (156, 132, 62)
    variant = rng.randint(0, 4)
    if variant == 0:  # Anvil
        pygame.draw.polygon(surface, gold, [(sym_cx - 5, sym_cy + 2), (sym_cx + 5, sym_cy + 2),
                                            (sym_cx + 4, sym_cy - 1), (sym_cx + 6, sym_cy - 3),
                                            (sym_cx - 4, sym_cy - 3)])
        pygame.draw.polygon(surface, gold_d, [(sym_cx - 5, sym_cy + 2), (sym_cx + 5, sym_cy + 2),
                                              (sym_cx + 4, sym_cy - 1), (sym_cx + 6, sym_cy - 3),
                                              (sym_cx - 4, sym_cy - 3)], 1)
    elif variant == 1:  # Chalice
        pygame.draw.polygon(surface, gold, [(sym_cx - 4, sym_cy - 4), (sym_cx + 4, sym_cy - 4),
                                            (sym_cx + 2, sym_cy + 2), (sym_cx - 2, sym_cy + 2)])
        pygame.draw.rect(surface, gold, (sym_cx - 1, sym_cy + 2, 2, 3))
        pygame.draw.rect(surface, gold, (sym_cx - 3, sym_cy + 5, 6, 2))
    elif variant == 2:  # Crossed swords
        pygame.draw.line(surface, gold, (sym_cx - 5, sym_cy - 4), (sym_cx + 5, sym_cy + 4), 2)
        pygame.draw.line(surface, gold, (sym_cx + 5, sym_cy - 4), (sym_cx - 5, sym_cy + 4), 2)
        pygame.draw.circle(surface, gold_d, (sym_cx, sym_cy), 2)
    elif variant == 3:  # Shield
        pygame.draw.polygon(surface, gold, [(sym_cx, sym_cy - 5), (sym_cx - 5, sym_cy - 2),
                                            (sym_cx - 4, sym_cy + 3), (sym_cx, sym_cy + 5),
                                            (sym_cx + 4, sym_cy + 3), (sym_cx + 5, sym_cy - 2)])
        pygame.draw.polygon(surface, gold_d, [(sym_cx, sym_cy - 5), (sym_cx - 5, sym_cy - 2),
                                              (sym_cx - 4, sym_cy + 3), (sym_cx, sym_cy + 5),
                                              (sym_cx + 4, sym_cy + 3), (sym_cx + 5, sym_cy - 2)], 1)
    else:  # Wheat sheaf
        for woff in (-3, 0, 3):
            pygame.draw.line(surface, gold, (sym_cx + woff, sym_cy + 4), (sym_cx + woff, sym_cy - 3), 1)
            pygame.draw.circle(surface, gold, (sym_cx + woff, sym_cy - 4), 2)
        pygame.draw.line(surface, gold_d, (sym_cx - 4, sym_cy + 2), (sym_cx + 4, sym_cy + 2), 1)
    return pygame.Rect(x - 2, y - 8, 32, 10)


def draw_meat_rack(surface: pygame.Surface, x: int, y: int) -> pygame.Rect:
    """HD drying rack — pegged frame, hanging meats with fat marbling, drip tray."""
    rng = random.Random(x * 29 + y)
    # Shadow
    shad = pygame.Surface((52, 12), pygame.SRCALPHA)
    pygame.draw.ellipse(shad, (0, 0, 0, 28), shad.get_rect())
    surface.blit(shad, (x - 26, y - 4))
    # A-frame posts — gradient wood
    for side in (-1, 1):
        base_x = x + side * 22
        top_x = x + side * 10
        for seg in range(8):
            t = seg / 7.0
            px_a = int(base_x + (top_x - base_x) * t)
            py_a = int(y - t * 54)
            shade = int(76 - 16 * t)
            pygame.draw.line(surface, (shade, int(shade * 0.74), int(shade * 0.52)),
                             (px_a - 2, py_a), (px_a + 2, py_a), 3)
    # Post outlines
    pygame.draw.line(surface, (38, 28, 18), (x - 22, y), (x - 10, y - 54), 1)
    pygame.draw.line(surface, (38, 28, 18), (x + 22, y), (x + 10, y - 54), 1)
    # Crossbar — thick with pegs
    pygame.draw.line(surface, (82, 62, 42), (x - 12, y - 52), (x + 12, y - 52), 4)
    pygame.draw.line(surface, (96, 74, 50), (x - 12, y - 53), (x + 12, y - 53), 1)  # Highlight
    pygame.draw.line(surface, (38, 28, 18), (x - 12, y - 54), (x + 12, y - 54), 1)  # Top edge
    # Pegs
    for peg_x in range(x - 8, x + 10, 5):
        pygame.draw.rect(surface, (72, 54, 36), (peg_x, y - 52, 2, 4))
    # Hanging meats — with hooks, fat marbling, and drip
    meat_data = [
        (x - 8, 16, (134, 46, 36)), (x - 3, 20, (148, 54, 42)),
        (x + 2, 14, (124, 42, 32)), (x + 7, 18, (140, 50, 38)),
    ]
    for mx, length, col in meat_data:
        # Iron hook
        pygame.draw.line(surface, (78, 76, 72), (mx, y - 50), (mx, y - 46), 1)
        pygame.draw.arc(surface, (78, 76, 72), (mx - 2, y - 48, 4, 4), 0, math.pi, 1)
        # Meat body
        for row in range(length):
            t = row / max(1, length - 1)
            # Darken toward bottom
            s = max(0, int(col[0] - 18 * t))
            mc = (s, int(s * 0.38), int(s * 0.28))
            w = 5 - int(abs(t - 0.5) * 4)
            pygame.draw.line(surface, mc, (mx - w // 2, y - 44 + row), (mx + w // 2, y - 44 + row))
        # Fat marbling streaks
        for _ in range(2):
            fy_m = y - 44 + rng.randint(2, length - 3)
            pygame.draw.line(surface, (col[0] + 40, col[1] + 30, col[2] + 20),
                             (mx - 1, fy_m), (mx + 1, fy_m), 1)
        # Drip
        if rng.random() < 0.4:
            pygame.draw.line(surface, (col[0] - 20, col[1] - 10, col[2] - 10),
                             (mx, y - 44 + length), (mx, y - 44 + length + 3), 1)
    # Drip tray underneath
    pygame.draw.rect(surface, (62, 46, 32), (x - 10, y - 24, 20, 3), border_radius=1)
    pygame.draw.rect(surface, (38, 28, 18), (x - 10, y - 24, 20, 3), 1, border_radius=1)
    return pygame.Rect(x - 26, y - 6, 52, 8)


def draw_training_dummy(surface: pygame.Surface, x: int, y: int) -> pygame.Rect:
    rng = random.Random(x * 41 + y)
    # Shadow
    shad = pygame.Surface((32, 10), pygame.SRCALPHA)
    pygame.draw.ellipse(shad, (0, 0, 0, 28), shad.get_rect())
    surface.blit(shad, (x - 16, y - 3))
    # Base tripod — three legs with wood grain
    for leg_dx, leg_angle in [(-12, -0.3), (12, 0.3), (0, 0)]:
        lx0 = x + leg_dx
        lx1 = x
        for row in range(14):
            t = row / 13.0
            px_l = int(lx0 + (lx1 - lx0) * t)
            shade = int(76 - 14 * t)
            pygame.draw.line(surface, (shade, int(shade * 0.72), int(shade * 0.50)),
                             (px_l - 2, y - row), (px_l + 2, y - row))
    # Vertical post — gradient with grain
    pw_p = 6
    ph_p = 62
    for row in range(ph_p):
        t = row / max(1, ph_p - 1)
        shade = int(82 - 18 * t)
        pygame.draw.line(surface, (shade, int(shade * 0.74), int(shade * 0.52)),
                         (x - pw_p // 2, y - 14 - row), (x + pw_p // 2, y - 14 - row))
    pygame.draw.rect(surface, (36, 26, 18), (x - pw_p // 2, y - 14 - ph_p, pw_p, ph_p), 1)
    # Grain lines on post
    for gy_d in range(y - 70, y - 18, 8):
        pygame.draw.line(surface, (54, 40, 28), (x - 2, gy_d), (x + 2, gy_d), 1)
    # Cross arm — horizontal beam
    arm_w = 44
    for row in range(5):
        t = row / 4.0
        shade = int(78 - 12 * t)
        pygame.draw.line(surface, (shade, int(shade * 0.72), int(shade * 0.50)),
                         (x - arm_w // 2, y - 50 + row), (x + arm_w // 2, y - 50 + row))
    pygame.draw.rect(surface, (36, 26, 18), (x - arm_w // 2, y - 50, arm_w, 5), 1)
    # Iron bracket at cross joint
    pygame.draw.rect(surface, (68, 66, 62), (x - 4, y - 52, 8, 8))
    pygame.draw.circle(surface, (88, 86, 82), (x, y - 48), 1)
    # Straw body — textured with individual straw wisps
    body_rect = pygame.Rect(x - 14, y - 58, 28, 38)
    for row in range(38):
        t = row / 37.0
        base_y_col = int(178 - 24 * t)
        for col_off in range(28):
            noise = rng.randint(-6, 6)
            s = max(0, min(255, base_y_col + noise))
            surface.set_at((body_rect.left + col_off, body_rect.top + row),
                           (s, int(s * 0.88), int(s * 0.56)))
    pygame.draw.rect(surface, (128, 108, 54), body_rect, 1, border_radius=3)
    # Straw wisps poking out
    for _ in range(8):
        wx = rng.randint(body_rect.left - 3, body_rect.right + 3)
        wy = rng.randint(body_rect.top, body_rect.bottom)
        wl = rng.randint(4, 8)
        wa = rng.uniform(-0.5, 0.5)
        pygame.draw.line(surface, (196, 176, 108),
                         (wx, wy), (wx + int(wl * math.cos(wa)), wy + int(wl * math.sin(wa))), 1)
    # Head — burlap sack
    head_r = 11
    for hy_off in range(-head_r, head_r + 1):
        hw = int(math.sqrt(max(0, head_r * head_r - hy_off * hy_off)))
        t = (hy_off + head_r) / (2 * head_r)
        shade = int(174 - 20 * t)
        pygame.draw.line(surface, (shade, int(shade * 0.86), int(shade * 0.52)),
                         (x - hw, y - 70 + hy_off), (x + hw, y - 70 + hy_off))
    pygame.draw.circle(surface, (124, 106, 52), (x, y - 70), head_r, 1)
    # Face marks (X eyes, stitched mouth)
    pygame.draw.line(surface, (82, 62, 34), (x - 4, y - 73), (x - 2, y - 71), 1)
    pygame.draw.line(surface, (82, 62, 34), (x - 2, y - 73), (x - 4, y - 71), 1)
    pygame.draw.line(surface, (82, 62, 34), (x + 2, y - 73), (x + 4, y - 71), 1)
    pygame.draw.line(surface, (82, 62, 34), (x + 4, y - 73), (x + 2, y - 71), 1)
    pygame.draw.line(surface, (82, 62, 34), (x - 3, y - 66), (x + 3, y - 66), 1)
    # Target painted on chest
    pygame.draw.circle(surface, (148, 36, 28), (x, y - 42), 6, 1)
    pygame.draw.circle(surface, (148, 36, 28), (x, y - 42), 3, 1)
    pygame.draw.circle(surface, (148, 36, 28), (x, y - 42), 1)
    return pygame.Rect(x - 15, y - 10, 30, 10)

def draw_grave_stone(surface: pygame.Surface, x: int, y: int, variant: int = 0) -> pygame.Rect:
    rng = random.Random(x * 17 + y * 31 + variant * 101)
    style = variant % 5

    w = 26 if style != 3 else 22
    h = 36 if style in (0, 2, 4) else 34
    rect = pygame.Rect(x - w // 2, y - h, w, h)

    # Ground shadow
    sh = pygame.Surface((w + 18, 10), pygame.SRCALPHA)
    pygame.draw.ellipse(sh, (0, 0, 0, 28), sh.get_rect())
    surface.blit(sh, (x - sh.get_width() // 2, y - 4))

    base_col = 104 + rng.randint(-6, 6)
    col = (base_col, base_col + 2, base_col + 6)
    dark = (max(0, base_col - 44), max(0, base_col - 42), max(0, base_col - 40))
    edge = (40, 40, 44)

    # Base plinth
    pl_h = 8
    pl = pygame.Rect(rect.left - 2, rect.bottom - pl_h + 1, rect.width + 4, pl_h)
    pygame.draw.rect(surface, (col[0] - 10, col[1] - 10, col[2] - 12), pl, border_radius=2)
    pygame.draw.rect(surface, edge, pl, 1, border_radius=2)
    pygame.draw.line(surface, (col[0] + 18, col[1] + 18, col[2] + 16), (pl.left + 2, pl.top + 2), (pl.right - 3, pl.top + 2), 1)

    def _stone_gradient_fill(shape_rect: pygame.Rect, cap_round: bool = False) -> None:
        for row in range(shape_rect.height):
            t = row / max(1, shape_rect.height - 1)
            shade = int(col[0] - 12 * t) + rng.randint(-2, 2)
            c = (max(0, min(255, shade)),
                 max(0, min(255, shade + 2)),
                 max(0, min(255, shade + 6)))
            yv = shape_rect.top + row
            if cap_round and row < 10:
                # approximate rounded cap by shrinking width near top
                shrink = (10 - row) // 2
                pygame.draw.line(surface, c, (shape_rect.left + shrink, yv), (shape_rect.right - 1 - shrink, yv))
            else:
                pygame.draw.line(surface, c, (shape_rect.left, yv), (shape_rect.right - 1, yv))

    # Main shapes
    if style == 0:
        # Rounded headstone
        body = pygame.Rect(rect.left, rect.top + 10, rect.width, rect.height - 10)
        _stone_gradient_fill(body)
        pygame.draw.circle(surface, col, (rect.centerx, rect.top + 10), rect.width // 2)
        pygame.draw.circle(surface, edge, (rect.centerx, rect.top + 10), rect.width // 2, 1)
        pygame.draw.rect(surface, edge, body, 1)
        # Face inset
        inset = body.inflate(-6, -8)
        pygame.draw.rect(surface, (dark[0] + 10, dark[1] + 10, dark[2] + 12), inset, border_radius=2)
        pygame.draw.rect(surface, edge, inset, 1, border_radius=2)
    elif style == 1:
        # Cross marker (stone)
        stem = pygame.Rect(x - 4, y - 34, 8, 34)
        arm = pygame.Rect(x - 12, y - 26, 24, 8)
        _stone_gradient_fill(stem)
        _stone_gradient_fill(arm)
        pygame.draw.rect(surface, edge, stem, 1)
        pygame.draw.rect(surface, edge, arm, 1)
        # chipped corner
        if rng.random() > 0.5:
            pygame.draw.polygon(surface, dark, [(arm.right - 2, arm.top + 1), (arm.right - 6, arm.top + 1), (arm.right - 2, arm.top + 6)])
    elif style == 2:
        # Tall obelisk
        pts = [(x - w // 2, y), (x + w // 2, y), (x + w // 4, rect.top + 10), (x, rect.top), (x - w // 4, rect.top + 10)]
        pygame.draw.polygon(surface, col, pts)
        pygame.draw.polygon(surface, edge, pts, 1)
        for row in range(rect.top + 6, y, 7):
            pygame.draw.line(surface, (dark[0] + 16, dark[1] + 16, dark[2] + 18), (x - w // 2 + 3, row), (x + w // 2 - 3, row), 1)
    elif style == 3:
        # Broken slab
        slab = pygame.Rect(rect.left, rect.top + 6, rect.width, rect.height - 6)
        _stone_gradient_fill(slab, cap_round=True)
        pygame.draw.polygon(surface, col, [(slab.left, slab.top + 6), (slab.right, slab.top + 2), (slab.right - 4, slab.top), (slab.left + 4, slab.top)])
        pygame.draw.rect(surface, edge, slab, 1)
        # Crack
        cx = slab.left + 4 + rng.randint(0, slab.width - 9)
        cy = slab.top + 6
        for i in range(10):
            nx = cx + rng.randint(-2, 2)
            ny = cy + i * 2
            pygame.draw.line(surface, (32, 32, 36), (nx, ny), (nx + rng.randint(-2, 2), ny + 2), 1)
    else:
        # Simple square headstone with beveled top
        body = pygame.Rect(rect.left, rect.top + 6, rect.width, rect.height - 6)
        _stone_gradient_fill(body)
        pygame.draw.polygon(surface, col, [(body.left, body.top + 4), (body.right, body.top + 2), (body.right - 4, body.top), (body.left + 4, body.top)])
        pygame.draw.rect(surface, edge, body, 1)

    # Carved inscription lines (subtle)
    ins_y = rect.top + 16 + rng.randint(-1, 2)
    for li in range(rng.randint(2, 4)):
        lx1 = rect.left + 5 + rng.randint(0, 2)
        lx2 = rect.right - 6 - rng.randint(0, 2)
        pygame.draw.line(surface, (dark[0] + 8, dark[1] + 8, dark[2] + 10), (lx1, ins_y + li * 5), (lx2, ins_y + li * 5), 1)

    # Moss/lichen at base + damp stain
    if rng.random() > 0.35:
        moss_w = rng.randint(6, 11)
        moss = pygame.Surface((moss_w, 5), pygame.SRCALPHA)
        pygame.draw.ellipse(moss, (46, 82, 34, 150), (0, 0, moss_w, 5))
        surface.blit(moss, (rect.left + rng.randint(0, max(1, rect.width - moss_w)), y - 4))
    if rng.random() > 0.55:
        stain = pygame.Surface((w + 6, 10), pygame.SRCALPHA)
        pygame.draw.ellipse(stain, (24, 26, 28, 38), stain.get_rect())
        surface.blit(stain, (x - stain.get_width() // 2, y - 10))

    return pygame.Rect(x - 11, y - 8, 22, 8)

def draw_forge_prop(surface: pygame.Surface, x: int, y: int) -> pygame.Rect:
    rng = random.Random(x * 53 + y)
    w, h = 50, 40
    rect = pygame.Rect(x - w // 2, y - h, w, h)
    # Shadow
    shad = pygame.Surface((w + 12, 14), pygame.SRCALPHA)
    pygame.draw.ellipse(shad, (0, 0, 0, 30), shad.get_rect())
    surface.blit(shad, (x - w // 2 - 6, y - 4))
    # Stone base — gradient with mortar lines
    for row in range(h):
        t = row / max(1, h - 1)
        shade = int(66 - 14 * t)
        pygame.draw.line(surface, (shade, shade, shade + 4),
                         (rect.left + 1, rect.top + row), (rect.right - 1, rect.top + row))
    # Mortar lines (brick pattern)
    for my in range(rect.top + 8, rect.bottom - 4, 8):
        pygame.draw.line(surface, (34, 34, 38), (rect.left + 1, my), (rect.right - 1, my), 1)
    # Vertical mortar (offset each row)
    for my_idx, my in enumerate(range(rect.top + 4, rect.bottom - 4, 8)):
        offset = 10 if my_idx % 2 == 0 else 0
        for mx_off in range(offset, w, 20):
            pygame.draw.line(surface, (34, 34, 38), (rect.left + mx_off, my), (rect.left + mx_off, my + 8), 1)
    pygame.draw.rect(surface, (30, 30, 34), rect, 2)
    # Coal bed — glowing embers
    coal_rect = rect.inflate(-10, -10)
    coal_rect.top -= 5
    for _ in range(14):
        cx_c = coal_rect.left + rng.randint(0, coal_rect.width)
        cy_c = coal_rect.top + rng.randint(0, coal_rect.height)
        cr = rng.randint(2, 4)
        glow_val = rng.randint(0, 1)
        if glow_val:
            pygame.draw.circle(surface, (140 + rng.randint(0, 60), 40 + rng.randint(0, 30), 10), (cx_c, cy_c), cr)
        else:
            pygame.draw.circle(surface, (22 + rng.randint(0, 12), 20, 18), (cx_c, cy_c), cr)
    # Fire glow
    glow = pygame.Surface((60, 60), pygame.SRCALPHA)
    pygame.draw.circle(glow, (255, 100, 20, 60), (30, 30), 22)
    pygame.draw.circle(glow, (255, 180, 40, 30), (30, 30), 14)
    surface.blit(glow, (x - 30, y - h - 20))
    # Hood — gradient iron with rivets
    hood_pts = [
        (x - w // 2 - 5, y - h), (x + w // 2 + 5, y - h),
        (x + w // 2, y - h - 32), (x - w // 2, y - h - 32)
    ]
    # Gradient fill for hood
    for row in range(32):
        t = row / 31.0
        shade = int(54 - 12 * t)
        left_x = int(x - w // 2 - 5 + 5 * (1 - t))
        right_x = int(x + w // 2 + 5 - 5 * (1 - t))
        pygame.draw.line(surface, (shade, shade, shade + 4),
                         (left_x, y - h - row), (right_x, y - h - row))
    pygame.draw.polygon(surface, (24, 24, 28), hood_pts, 2)
    # Rivets on hood
    for rv_x in (x - w // 2 + 4, x + w // 2 - 4):
        for rv_y in (y - h - 8, y - h - 22):
            pygame.draw.circle(surface, (72, 72, 76), (rv_x, rv_y), 2)
            pygame.draw.circle(surface, (86, 86, 90), (rv_x - 1, rv_y - 1), 1)
    return rect


def draw_hd_forge_prop(surface: pygame.Surface, x: int, y: int, ticks: int = 0, seed: int = 0) -> pygame.Rect:
    w, h = 96, 78
    rect = pygame.Rect(x - w // 2, y - h, w, h)

    # Shadow
    pygame.draw.ellipse(surface, (10, 10, 12), (x - w // 2 - 6, y - 8, w + 12, 18))

    # Stone base with subtle gradient
    base = rect.inflate(0, -8)
    for i in range(base.height):
        t = i / max(1, base.height - 1)
        col = (int(70 - 16 * t), int(70 - 14 * t), int(74 - 18 * t))
        pygame.draw.line(surface, col, (base.left, base.top + i), (base.right, base.top + i))
    pygame.draw.rect(surface, (30, 30, 34), base, 2)

    # Brick lines
    for by in range(base.top + 6, base.bottom - 6, 10):
        pygame.draw.line(surface, (50, 50, 54), (base.left + 4, by), (base.right - 4, by), 1)
        for bx in range(base.left + 8, base.right - 8, 18):
            pygame.draw.line(surface, (44, 44, 48), (bx, by - 4), (bx, by + 4), 1)

    # Furnace mouth
    mouth = pygame.Rect(x - 16, y - 34, 32, 24)
    pygame.draw.rect(surface, (18, 16, 16), mouth, border_radius=4)
    ember = pygame.Surface((mouth.width, mouth.height), pygame.SRCALPHA)
    ember_col = (240, 130, 50, 210)
    pygame.draw.rect(ember, ember_col, ember.get_rect(), border_radius=4)
    pygame.draw.rect(ember, (250, 200, 110, 160), ember.get_rect().inflate(-8, -8), border_radius=3)
    surface.blit(ember, mouth.topleft, special_flags=pygame.BLEND_RGBA_ADD)
    pygame.draw.rect(surface, (90, 60, 30), mouth, 1, border_radius=4)

    # Hood + chimney
    hood_pts = [
        (base.left - 8, base.top - 18),
        (base.right + 8, base.top - 18),
        (base.right + 18, base.top + 8),
        (base.left - 18, base.top + 8),
    ]
    pygame.draw.polygon(surface, (46, 46, 50), hood_pts)
    pygame.draw.polygon(surface, (20, 20, 24), hood_pts, 2)
    chimney = pygame.Rect(x - 8, base.top - 42, 16, 24)
    pygame.draw.rect(surface, (30, 30, 34), chimney)
    pygame.draw.rect(surface, (18, 18, 22), chimney, 1)

    # Sparks
    for i in range(7):
        t = ticks * 0.002 + seed * 0.11 + i * 1.4
        px = mouth.centerx + math.sin(t * 1.5 + i) * 12
        py = mouth.top - 6 - (t * 24 + i * 6) % 20
        alpha = int(clamp(190 - (mouth.top - py) * 6, 40, 255))
        pygame.draw.circle(surface, (240, 190, 100, alpha), (int(px), int(py)), 2)

    return rect

def draw_anvil(surface: pygame.Surface, x: int, y: int) -> pygame.Rect:
    rng = random.Random(x * 59 + y)
    # Shadow
    shad = pygame.Surface((56, 12), pygame.SRCALPHA)
    pygame.draw.ellipse(shad, (0, 0, 0, 30), shad.get_rect())
    surface.blit(shad, (x - 28, y - 4))
    # Base/pedestal — gradient iron
    base = pygame.Rect(x - 14, y - 22, 28, 18)
    for row in range(18):
        t = row / 17.0
        shade = int(78 - 16 * t)
        pygame.draw.line(surface, (shade, shade, shade + 6),
                         (base.left + 1, base.top + row), (base.right - 1, base.top + row))
    pygame.draw.rect(surface, (32, 32, 36), base, 1, border_radius=2)
    # Face/top — gradient with wear marks
    top_pts = [(x - 30, y - 22), (x + 26, y - 22), (x + 14, y - 34), (x - 18, y - 34)]
    # Fill top face with gradient
    for row in range(12):
        t = row / 11.0
        shade = int(106 - 16 * t)
        left_x = int(x - 30 + 12 * t)
        right_x = int(x + 26 - 12 * t)
        pygame.draw.line(surface, (shade, shade + 2, shade + 8),
                         (left_x, y - 22 - row), (right_x, y - 22 - row))
    pygame.draw.polygon(surface, (44, 46, 50), top_pts, 2)
    # Hammer wear marks on face
    for _ in range(4):
        wx = x + rng.randint(-12, 8)
        wy = y - 28 + rng.randint(-3, 3)
        pygame.draw.circle(surface, (92, 94, 100), (wx, wy), rng.randint(1, 2))
    # Top face highlight
    pygame.draw.line(surface, (118, 120, 128), (x - 16, y - 33), (x + 12, y - 33), 1)
    # Horn — gradient with taper
    horn_pts = [(x + 26, y - 22), (x + 42, y - 24), (x + 36, y - 30), (x + 14, y - 34)]
    for row in range(12):
        t = row / 11.0
        shade = int(102 - 14 * t)
        left_x = int(x + 26 - 12 * t)
        right_x = int(x + 42 - 6 * t)
        pygame.draw.line(surface, (shade, shade + 2, shade + 8),
                         (left_x, y - 22 - row), (right_x, y - 22 - row))
    pygame.draw.polygon(surface, (44, 46, 50), horn_pts, 1)
    # Horn tip highlight
    pygame.draw.circle(surface, (116, 118, 126), (x + 39, y - 27), 2)
    # Hardy/pritchel holes on face
    pygame.draw.circle(surface, (28, 28, 32), (x - 4, y - 28), 2)
    pygame.draw.circle(surface, (28, 28, 32), (x + 4, y - 28), 1)
    return pygame.Rect(x - 30, y - 36, 70, 34)


def draw_hd_anvil(surface: pygame.Surface, x: int, y: int) -> pygame.Rect:
    # Shadow
    pygame.draw.ellipse(surface, (10, 10, 12), (x - 34, y - 4, 68, 12))
    # Base
    base = pygame.Rect(x - 18, y - 26, 36, 20)
    pygame.draw.rect(surface, (78, 80, 88), base, border_radius=4)
    pygame.draw.rect(surface, (36, 38, 44), base, 2, border_radius=4)
    # Top plate
    top = [(x - 36, y - 26), (x + 30, y - 26), (x + 18, y - 42), (x - 22, y - 42)]
    pygame.draw.polygon(surface, (110, 114, 124), top)
    pygame.draw.polygon(surface, (52, 54, 60), top, 2)
    # Horn
    horn = [(x + 30, y - 26), (x + 52, y - 30), (x + 36, y - 38), (x + 18, y - 42)]
    pygame.draw.polygon(surface, (106, 110, 120), horn)
    pygame.draw.polygon(surface, (52, 54, 60), horn, 1)
    # Hardy hole
    pygame.draw.rect(surface, (30, 30, 36), (x - 6, y - 40, 8, 6), border_radius=2)
    # Stand
    pygame.draw.rect(surface, (70, 60, 50), (x - 4, y - 6, 8, 10), border_radius=2)
    return pygame.Rect(x - 36, y - 46, 88, 44)


def draw_gladiator_arena(surface: pygame.Surface, cx: int, cy: int) -> List[pygame.Rect]:  # noqa: C901
    """Draw a large oval gladiator arena — Roman coliseum style, dark Gothic palette."""
    # ── palette ──────────────────────────────────────────────────────────────
    STONE   = (88, 84, 78)
    STONE_D = (62, 58, 54)
    STONE_L = (108, 104, 96)
    MORTAR  = (48, 44, 40)
    SAND    = (142, 128, 96)
    SAND_D  = (118, 106, 78)
    SAND_L  = (162, 148, 114)
    WOOD    = (66, 52, 38)
    WOOD_D  = (44, 34, 26)
    WOOD_L  = (82, 66, 48)
    IRON    = (62, 60, 58)
    IRON_H  = (96, 94, 90)
    BLOOD   = (92, 22, 18)
    BLOOD_D = (62, 14, 12)
    GOLD    = (192, 160, 72)
    GOLD_D  = (148, 122, 52)
    BANNER_R = (140, 28, 22)
    BANNER_R2 = (100, 18, 14)
    BANNER_BK = (30, 28, 26)
    MOSS    = (48, 64, 44)

    # ── dimensions ───────────────────────────────────────────────────────────
    outer_rx, outer_ry = 260, 160          # outer ellipse radii
    inner_rx, inner_ry = 190, 110          # inner arena floor
    wall_h = 36                            # wall height (3D effect)
    tier_count = 3                         # seating tiers
    tier_step_rx = 18                      # radial step per tier
    tier_step_ry = 12

    obstacles: List[pygame.Rect] = []

    # ── 1. Ground shadow ─────────────────────────────────────────────────────
    shad = pygame.Surface((outer_rx * 2 + 40, outer_ry * 2 + 60), pygame.SRCALPHA)
    pygame.draw.ellipse(shad, (0, 0, 0, 38), (0, 10, outer_rx * 2 + 40, outer_ry * 2 + 60))
    surface.blit(shad, (cx - outer_rx - 20, cy - outer_ry - 10))

    # ── 2. Outer foundation (thick stone base) ───────────────────────────────
    # Foundation ring — slightly larger than outer wall
    found_rx, found_ry = outer_rx + 14, outer_ry + 10
    pygame.draw.ellipse(surface, MORTAR, (cx - found_rx, cy - found_ry, found_rx * 2, found_ry * 2))
    pygame.draw.ellipse(surface, STONE_D, (cx - found_rx, cy - found_ry, found_rx * 2, found_ry * 2), 3)

    # ── 3. Seating tiers (outer to inner) ────────────────────────────────────
    rng = random.Random(7777)
    for tier in range(tier_count):
        trx = outer_rx - tier * tier_step_rx
        try_ = outer_ry - tier * tier_step_ry
        # Tier surface (raised stone)
        tier_col = (
            STONE[0] - tier * 8,
            STONE[1] - tier * 8,
            STONE[2] - tier * 8,
        )
        tier_dark = (tier_col[0] - 20, tier_col[1] - 20, tier_col[2] - 20)
        # 3D: draw "side" first (lower ellipse, darker)
        pygame.draw.ellipse(surface, tier_dark, (cx - trx, cy - try_ + 4, trx * 2, try_ * 2))
        # Top face
        pygame.draw.ellipse(surface, tier_col, (cx - trx, cy - try_, trx * 2, try_ * 2))
        # Outline
        pygame.draw.ellipse(surface, MORTAR, (cx - trx, cy - try_, trx * 2, try_ * 2), 2)

        # Stone block lines (radial seats)
        for i in range(24 + tier * 4):
            ang = (i / (24 + tier * 4)) * math.tau
            sx = cx + math.cos(ang) * (trx - 4)
            sy = cy + math.sin(ang) * (try_ - 3)
            ex = cx + math.cos(ang) * (trx - tier_step_rx + 4)
            ey = cy + math.sin(ang) * (try_ - tier_step_ry + 3)
            pygame.draw.line(surface, MORTAR, (int(sx), int(sy)), (int(ex), int(ey)), 1)

        # Spectator dots (tiny colored circles representing seated crowd)
        for i in range(16 + tier * 6):
            ang = rng.uniform(0, math.tau)
            r_frac = rng.uniform(0.3, 0.85)
            seat_rx = trx - tier_step_rx * r_frac
            seat_ry = try_ - tier_step_ry * r_frac
            px = cx + math.cos(ang) * seat_rx
            py = cy + math.sin(ang) * seat_ry
            # Vary crowd colors
            crowd_cols = [
                (120, 80, 60), (90, 70, 55), (140, 100, 70),
                (70, 60, 80), (110, 40, 35), (80, 90, 70),
            ]
            cc = rng.choice(crowd_cols)
            pygame.draw.circle(surface, cc, (int(px), int(py)), 3)
            # Head highlight
            pygame.draw.circle(surface, (min(cc[0] + 30, 255), min(cc[1] + 30, 255), min(cc[2] + 30, 255)),
                               (int(px), int(py) - 1), 2)

    # ── 4. Arena wall (inner ring — separates crowd from floor) ──────────────
    # Wall "side" (3D depth)
    for h_off in range(wall_h, 0, -2):
        shade = max(0, STONE_D[0] - h_off)
        pygame.draw.ellipse(surface, (shade, shade - 2, shade - 4),
                            (cx - inner_rx - 6, cy - inner_ry - 6 + h_off, (inner_rx + 6) * 2, (inner_ry + 6) * 2), 3)
    # Wall top
    pygame.draw.ellipse(surface, STONE_L, (cx - inner_rx - 6, cy - inner_ry - 6, (inner_rx + 6) * 2, (inner_ry + 6) * 2))
    pygame.draw.ellipse(surface, STONE_D, (cx - inner_rx - 6, cy - inner_ry - 6, (inner_rx + 6) * 2, (inner_ry + 6) * 2), 3)
    # Inner wall face
    pygame.draw.ellipse(surface, STONE, (cx - inner_rx, cy - inner_ry, inner_rx * 2, inner_ry * 2))
    pygame.draw.ellipse(surface, MORTAR, (cx - inner_rx, cy - inner_ry, inner_rx * 2, inner_ry * 2), 2)

    # ── 5. Arena floor (sand) ────────────────────────────────────────────────
    floor_rx, floor_ry = inner_rx - 8, inner_ry - 6
    pygame.draw.ellipse(surface, SAND, (cx - floor_rx, cy - floor_ry, floor_rx * 2, floor_ry * 2))
    # Sand texture — scattered darker patches
    for _ in range(60):
        sx = cx + rng.randint(-floor_rx + 12, floor_rx - 12)
        sy = cy + rng.randint(-floor_ry + 8, floor_ry - 8)
        # Check if inside ellipse
        if ((sx - cx) / floor_rx) ** 2 + ((sy - cy) / floor_ry) ** 2 <= 0.92:
            pygame.draw.circle(surface, SAND_D, (sx, sy), rng.randint(2, 6))
    # Light streaks
    for _ in range(15):
        sx = cx + rng.randint(-floor_rx + 30, floor_rx - 30)
        sy = cy + rng.randint(-floor_ry + 20, floor_ry - 20)
        if ((sx - cx) / floor_rx) ** 2 + ((sy - cy) / floor_ry) ** 2 <= 0.85:
            pygame.draw.line(surface, SAND_L, (sx, sy), (sx + rng.randint(-12, 12), sy + rng.randint(-4, 4)), 1)

    # Blood stains on sand
    for _ in range(8):
        bx = cx + rng.randint(-floor_rx + 30, floor_rx - 30)
        by = cy + rng.randint(-floor_ry + 15, floor_ry - 15)
        if ((bx - cx) / floor_rx) ** 2 + ((by - cy) / floor_ry) ** 2 <= 0.8:
            splat = pygame.Surface((rng.randint(8, 18), rng.randint(4, 10)), pygame.SRCALPHA)
            pygame.draw.ellipse(splat, (*BLOOD_D, 90), splat.get_rect())
            surface.blit(splat, (bx, by))

    # ── 6. Center ring marking ───────────────────────────────────────────────
    pygame.draw.ellipse(surface, SAND_D, (cx - 40, cy - 24, 80, 48), 2)
    # Skull emblem in center
    pygame.draw.circle(surface, (SAND_D[0] + 10, SAND_D[1] + 8, SAND_D[2] + 6), (cx, cy - 2), 8)
    pygame.draw.circle(surface, SAND_D, (cx, cy - 2), 8, 1)
    # Eye sockets
    pygame.draw.circle(surface, (SAND[0] - 20, SAND[1] - 20, SAND[2] - 20), (cx - 3, cy - 4), 2)
    pygame.draw.circle(surface, (SAND[0] - 20, SAND[1] - 20, SAND[2] - 20), (cx + 3, cy - 4), 2)
    # Jaw
    pygame.draw.line(surface, SAND_D, (cx - 4, cy + 2), (cx + 4, cy + 2), 1)

    # ── 7. Entrance arches (north and south gates) ───────────────────────────
    for gate_side, gate_ang in [(-1, math.pi / 2), (1, -math.pi / 2)]:
        gx = cx
        gy = cy + gate_side * (inner_ry + 4)
        # Archway frame
        arch_w, arch_h = 36, 28
        arch_rect = pygame.Rect(gx - arch_w // 2, gy - arch_h // 2, arch_w, arch_h)
        pygame.draw.rect(surface, STONE_D, arch_rect)
        pygame.draw.rect(surface, STONE_L, arch_rect, 2)
        # Portcullis bars (iron gate)
        for bx in range(arch_rect.left + 5, arch_rect.right - 4, 6):
            pygame.draw.line(surface, IRON, (bx, arch_rect.top + 3), (bx, arch_rect.bottom - 3), 2)
            pygame.draw.line(surface, IRON_H, (bx + 1, arch_rect.top + 3), (bx + 1, arch_rect.bottom - 3), 1)
        # Cross bar
        pygame.draw.line(surface, IRON, (arch_rect.left + 3, gy), (arch_rect.right - 3, gy), 2)
        # Keystone
        pygame.draw.polygon(surface, STONE_L, [
            (gx - 8, arch_rect.top), (gx + 8, arch_rect.top), (gx, arch_rect.top - 8)
        ])
        pygame.draw.polygon(surface, MORTAR, [
            (gx - 8, arch_rect.top), (gx + 8, arch_rect.top), (gx, arch_rect.top - 8)
        ], 1)

    # East and west gates
    for gate_side in [-1, 1]:
        gx = cx + gate_side * (inner_rx + 4)
        gy = cy
        arch_w, arch_h = 28, 24
        arch_rect = pygame.Rect(gx - arch_w // 2, gy - arch_h // 2, arch_w, arch_h)
        pygame.draw.rect(surface, STONE_D, arch_rect)
        pygame.draw.rect(surface, STONE_L, arch_rect, 2)
        for by_off in range(arch_rect.top + 4, arch_rect.bottom - 3, 5):
            pygame.draw.line(surface, IRON, (arch_rect.left + 3, by_off), (arch_rect.right - 3, by_off), 2)

    # ── 8. Pillars / columns around the rim ──────────────────────────────────
    pillar_count = 16
    for i in range(pillar_count):
        ang = (i / pillar_count) * math.tau
        px = cx + math.cos(ang) * (outer_rx - 4)
        py = cy + math.sin(ang) * (outer_ry - 3)
        # Pillar base
        pygame.draw.rect(surface, STONE_L, (int(px) - 6, int(py) - 14, 12, 18))
        pygame.draw.rect(surface, STONE_D, (int(px) - 6, int(py) - 14, 12, 18), 1)
        # Capital (top block)
        pygame.draw.rect(surface, STONE_L, (int(px) - 8, int(py) - 16, 16, 4))
        pygame.draw.rect(surface, MORTAR, (int(px) - 8, int(py) - 16, 16, 4), 1)
        # Base block
        pygame.draw.rect(surface, STONE_L, (int(px) - 7, int(py) + 2, 14, 4))

    # ── 9. Banners / flags on cardinal pillars ───────────────────────────────
    banner_angles = [0, math.pi / 2, math.pi, 3 * math.pi / 2]
    for ang in banner_angles:
        bx = cx + math.cos(ang) * (outer_rx + 10)
        by = cy + math.sin(ang) * (outer_ry + 8)
        # Pole
        pygame.draw.line(surface, WOOD_D, (int(bx), int(by) - 36), (int(bx), int(by) + 4), 3)
        pygame.draw.line(surface, WOOD_L, (int(bx) + 1, int(by) - 36), (int(bx) + 1, int(by) + 4), 1)
        # Banner cloth
        banner_pts = [
            (int(bx), int(by) - 34),
            (int(bx) + 18, int(by) - 28),
            (int(bx) + 16, int(by) - 14),
            (int(bx) + 8, int(by) - 8),
            (int(bx), int(by) - 12),
        ]
        pygame.draw.polygon(surface, BANNER_R, banner_pts)
        pygame.draw.polygon(surface, BANNER_R2, banner_pts, 1)
        # Skull/emblem on banner
        embx = int(bx) + 9
        emby = int(by) - 22
        pygame.draw.circle(surface, BANNER_BK, (embx, emby), 4)
        pygame.draw.circle(surface, (180, 170, 140), (embx, emby), 3)
        pygame.draw.circle(surface, BANNER_BK, (embx - 1, emby - 1), 1)
        pygame.draw.circle(surface, BANNER_BK, (embx + 1, emby - 1), 1)

    # ── 10. Weapon racks flanking south gate ─────────────────────────────────
    for side in [-1, 1]:
        rx = cx + side * 50
        ry = cy + inner_ry + 16
        # Rack frame
        pygame.draw.rect(surface, WOOD, (rx - 12, ry - 18, 24, 22))
        pygame.draw.rect(surface, WOOD_D, (rx - 12, ry - 18, 24, 22), 1)
        # Weapons (sword, axe, spear silhouettes)
        pygame.draw.line(surface, IRON_H, (rx - 6, ry - 16), (rx - 6, ry + 0), 2)
        pygame.draw.line(surface, IRON, (rx, ry - 14), (rx, ry + 2), 2)
        pygame.draw.line(surface, IRON_H, (rx + 6, ry - 16), (rx + 6, ry - 2), 2)
        # Axe head
        pygame.draw.polygon(surface, IRON, [
            (rx + 4, ry - 14), (rx + 10, ry - 12), (rx + 10, ry - 8), (rx + 4, ry - 6)
        ])

    # ── 11. Torches on inner wall ────────────────────────────────────────────
    torch_count = 8
    for i in range(torch_count):
        ang = (i / torch_count) * math.tau + 0.2
        tx = cx + math.cos(ang) * (inner_rx + 2)
        ty = cy + math.sin(ang) * (inner_ry + 2)
        # Sconce
        pygame.draw.rect(surface, IRON, (int(tx) - 2, int(ty) - 10, 4, 10))
        # Flame (static on pre-rendered surface)
        pygame.draw.polygon(surface, (220, 140, 40), [
            (int(tx), int(ty) - 16), (int(tx) - 3, int(ty) - 10), (int(tx) + 3, int(ty) - 10)
        ])
        pygame.draw.polygon(surface, (255, 200, 80), [
            (int(tx), int(ty) - 14), (int(tx) - 2, int(ty) - 10), (int(tx) + 2, int(ty) - 10)
        ])

    # ── 12. Weathering — moss and cracks ─────────────────────────────────────
    for _ in range(20):
        ang = rng.uniform(0, math.tau)
        r_frac = rng.uniform(0.85, 1.05)
        mx = cx + math.cos(ang) * outer_rx * r_frac
        my = cy + math.sin(ang) * outer_ry * r_frac
        pygame.draw.circle(surface, MOSS, (int(mx), int(my)), rng.randint(2, 5))

    # Cracks in stone
    for _ in range(12):
        ang = rng.uniform(0, math.tau)
        r_frac = rng.uniform(0.7, 0.95)
        crx = cx + math.cos(ang) * outer_rx * r_frac
        cry = cy + math.sin(ang) * outer_ry * r_frac
        dx, dy = rng.randint(-8, 8), rng.randint(-4, 4)
        pygame.draw.line(surface, MORTAR, (int(crx), int(cry)), (int(crx + dx), int(cry + dy)), 1)

    # ── 13. Collision obstacles ──────────────────────────────────────────────
    # Outer wall ring — approximate with rects on 8 cardinal/ordinal points
    for i in range(16):
        ang = (i / 16) * math.tau
        ox = cx + math.cos(ang) * (outer_rx - 10)
        oy = cy + math.sin(ang) * (outer_ry - 8)
        ix = cx + math.cos(ang) * (inner_rx + 8)
        iy = cy + math.sin(ang) * (inner_ry + 6)
        mid_x = (ox + ix) / 2
        mid_y = (oy + iy) / 2
        seg_w = max(20, abs(ox - ix) + 10)
        seg_h = max(16, abs(oy - iy) + 10)
        obstacles.append(pygame.Rect(int(mid_x - seg_w / 2), int(mid_y - seg_h / 2), int(seg_w), int(seg_h)))

    return obstacles


def draw_market_awning(surface: pygame.Surface, x: int, y: int,
                       color: tuple[int, int, int] = (128, 36, 28)) -> pygame.Rect:
    """HD market stall — wooden counter with striped fabric awning and displayed goods."""
    rng = random.Random(x * 83 + y)
    aw, ah = 80, 56
    # Shadow
    shad = pygame.Surface((aw + 12, 14), pygame.SRCALPHA)
    pygame.draw.ellipse(shad, (0, 0, 0, 26), shad.get_rect())
    surface.blit(shad, (x - aw // 2 - 6, y - 4))
    # Counter — planked wood
    cw, ch = aw - 8, 18
    for row in range(ch):
        t = row / max(1, ch - 1)
        shade = int(84 - 16 * t)
        pygame.draw.line(surface, (shade, int(shade * 0.72), int(shade * 0.50)),
                         (x - cw // 2, y - ch + row), (x + cw // 2, y - ch + row))
    for mx in range(x - cw // 2 + 14, x + cw // 2, 14):
        pygame.draw.line(surface, (42, 30, 20), (mx, y - ch + 1), (mx, y - 1), 1)
    pygame.draw.rect(surface, (38, 28, 18), (x - cw // 2, y - ch, cw, ch), 1)
    # Support posts
    for px in (x - aw // 2 + 4, x + aw // 2 - 4):
        for row in range(ah - 8):
            shade = int(72 - 12 * (row / max(1, ah - 9)))
            pygame.draw.line(surface, (shade, int(shade * 0.72), int(shade * 0.50)),
                             (px - 2, y - ah + row), (px + 2, y - ah + row))
    # Awning fabric — striped with drape
    stripe_w = 10
    for col in range(aw):
        stripe_idx = col // stripe_w
        is_alt = stripe_idx % 2 == 0
        base_c = color if is_alt else (min(255, color[0] + 60), min(255, color[1] + 50), min(255, color[2] + 40))
        drape = int(math.sin(col * 0.12) * 3)
        for row in range(10):
            t = row / 9.0
            r = max(0, min(255, int(base_c[0] - 14 * t)))
            g = max(0, min(255, int(base_c[1] - 14 * t)))
            b = max(0, min(255, int(base_c[2] - 14 * t)))
            surface.set_at((x - aw // 2 + col, y - ah + drape + row), (r, g, b))
    # Displayed goods on counter
    for gi in range(3):
        gx = x - cw // 3 + gi * (cw // 3)
        kind = rng.randint(0, 2)
        if kind == 0:  # bread loaf
            pygame.draw.ellipse(surface, (178, 148, 88), (gx - 6, y - ch - 6, 12, 6))
            pygame.draw.ellipse(surface, (148, 118, 68), (gx - 6, y - ch - 6, 12, 6), 1)
        elif kind == 1:  # cheese wheel
            pygame.draw.circle(surface, (198, 178, 68), (gx, y - ch - 4), 4)
            pygame.draw.circle(surface, (168, 148, 48), (gx, y - ch - 4), 4, 1)
        else:  # apple/fruit
            pygame.draw.circle(surface, (148, 38, 28), (gx, y - ch - 4), 3)
            pygame.draw.circle(surface, (118, 28, 18), (gx, y - ch - 4), 3, 1)
    return pygame.Rect(x - aw // 2, y - 6, aw, 8)


def draw_wine_rack(surface: pygame.Surface, x: int, y: int) -> pygame.Rect:
    """HD wine rack — wooden frame with bottles nestled in diamond shelves."""
    rng = random.Random(x * 89 + y)
    rw, rh = 36, 42
    # Shadow
    shad = pygame.Surface((rw + 8, 12), pygame.SRCALPHA)
    pygame.draw.ellipse(shad, (0, 0, 0, 28), shad.get_rect())
    surface.blit(shad, (x - rw // 2 - 4, y - 4))
    # Back panel — dark wood
    for row in range(rh):
        t = row / max(1, rh - 1)
        shade = int(52 - 14 * t)
        pygame.draw.line(surface, (shade, int(shade * 0.68), int(shade * 0.44)),
                         (x - rw // 2, y - rh + row), (x + rw // 2, y - rh + row))
    pygame.draw.rect(surface, (28, 20, 14), (x - rw // 2, y - rh, rw, rh), 1)
    # Diamond-pattern shelves with bottles
    slot_h = 10
    for row_i in range(3):
        for col_i in range(3):
            sx = x - rw // 2 + 6 + col_i * 10
            sy = y - rh + 6 + row_i * 12
            # Diamond frame
            pygame.draw.polygon(surface, (62, 46, 32),
                                [(sx + 5, sy), (sx + 10, sy + 5), (sx + 5, sy + 10), (sx, sy + 5)], 1)
            # Bottle (dark glass with neck)
            bcol = rng.choice([(42, 68, 38), (58, 34, 28), (38, 38, 56)])
            pygame.draw.ellipse(surface, bcol, (sx + 2, sy + 3, 6, 4))
            pygame.draw.line(surface, bcol, (sx + 5, sy + 2), (sx + 5, sy + 4), 1)
    return pygame.Rect(x - rw // 2, y - 6, rw, 8)


def draw_potted_tree(surface: pygame.Surface, x: int, y: int, seed: int = 0) -> pygame.Rect:
    """HD ornamental tree in stone pot — small decorative foliage."""
    rng = random.Random(x * 97 + y + seed)
    # Shadow
    shad = pygame.Surface((36, 12), pygame.SRCALPHA)
    pygame.draw.ellipse(shad, (0, 0, 0, 30), shad.get_rect())
    surface.blit(shad, (x - 18, y - 4))
    # Stone pot — gradient with carved detail
    pw, ph = 22, 16
    for row in range(ph):
        t = row / max(1, ph - 1)
        half_w = int(pw * 0.5 * (0.78 + 0.22 * t))
        shade = int(80 - 16 * t)
        c = (shade + rng.randint(-2, 2), shade + 2, shade + 5)
        pygame.draw.line(surface, c, (x - half_w, y - ph + row), (x + half_w, y - ph + row))
    # Pot rim — double band
    pygame.draw.ellipse(surface, (86, 88, 92), (x - pw // 2 - 1, y - ph - 3, pw + 2, 6))
    pygame.draw.ellipse(surface, (52, 54, 58), (x - pw // 2 - 1, y - ph - 3, pw + 2, 6), 1)
    pygame.draw.ellipse(surface, (78, 80, 84), (x - pw // 2, y - ph - 1, pw, 4))
    # Carved band on pot
    band_y = y - ph // 2
    pygame.draw.line(surface, (62, 64, 68), (x - pw // 3, band_y), (x + pw // 3, band_y), 1)
    pygame.draw.line(surface, (88, 90, 94), (x - pw // 3, band_y - 1), (x + pw // 3, band_y - 1), 1)
    # Soil visible at top with mulch texture
    pygame.draw.ellipse(surface, (48, 40, 32), (x - pw // 2 + 2, y - ph, pw - 4, 5))
    for _ in range(4):
        mx = x + rng.randint(-pw // 3, pw // 3)
        my = y - ph + rng.randint(1, 3)
        pygame.draw.circle(surface, (56, 44, 34), (mx, my), 1)
    # Trunk — slightly thicker with bark grain
    trunk_h = 18
    for row in range(trunk_h):
        t = row / max(1, trunk_h - 1)
        hw = 1 + int(0.5 * (1.0 - t * 0.3))
        shade = int(72 - 12 * t) + rng.randint(-3, 3)
        pygame.draw.line(surface, (shade, int(shade * 0.70), int(shade * 0.48)),
                         (x - hw, y - ph - row), (x + hw, y - ph - row))
    # Foliage — layered leaf clusters with depth
    top_y = y - ph - trunk_h
    # Back layer (darker, larger)
    for _ in range(6):
        fx = x + rng.randint(-10, 10)
        fy = top_y + rng.randint(-4, 6)
        fr = rng.randint(4, 7)
        g = 42 + rng.randint(-6, 6)
        pygame.draw.circle(surface, (g, g + 22, g - 4), (fx, fy), fr)
    # Middle layer
    for _ in range(8):
        fx = x + rng.randint(-9, 9)
        fy = top_y + rng.randint(-6, 3)
        fr = rng.randint(3, 6)
        g = 54 + rng.randint(-8, 8)
        pygame.draw.circle(surface, (g, g + 28, g - 2), (fx, fy), fr)
    # Individual leaf shapes on the surface
    for _ in range(10):
        lx = x + rng.randint(-8, 8)
        ly = top_y + rng.randint(-6, 4)
        la = rng.uniform(0, math.tau)
        ll = rng.randint(2, 4)
        lc = (48 + rng.randint(0, 20), 78 + rng.randint(0, 28), 38 + rng.randint(0, 10))
        ex, ey = lx + int(math.cos(la) * ll), ly + int(math.sin(la) * ll)
        pygame.draw.line(surface, lc, (lx, ly), (ex, ey), 1)
        pygame.draw.circle(surface, lc, (ex, ey), 1)
    # Top highlight dots
    for _ in range(5):
        fx = x + rng.randint(-6, 6)
        fy = top_y + rng.randint(-6, -1)
        pygame.draw.circle(surface, (78 + rng.randint(0, 16), 112 + rng.randint(0, 16), 68 + rng.randint(0, 10)), (fx, fy), rng.randint(1, 2))
    # Small flowers / berries on some trees
    if rng.random() > 0.5:
        for _ in range(rng.randint(2, 5)):
            bx = x + rng.randint(-7, 7)
            by = top_y + rng.randint(-4, 4)
            bc = rng.choice([(200, 60, 60), (240, 200, 80), (200, 120, 180), (255, 255, 220)])
            pygame.draw.circle(surface, bc, (bx, by), rng.randint(1, 2))
    return pygame.Rect(x - 14, y - 6, 28, 8)


def draw_signpost(surface: pygame.Surface, x: int, y: int, seed: int = 0) -> pygame.Rect:
    """HD directional signpost — wooden post with 2-3 arrow-shaped boards."""
    rng = random.Random(x * 101 + y + seed)
    # Shadow
    shad = pygame.Surface((20, 8), pygame.SRCALPHA)
    pygame.draw.ellipse(shad, (0, 0, 0, 26), shad.get_rect())
    surface.blit(shad, (x - 10, y - 3))
    # Post — gradient wood
    pw, ph = 6, 58
    for row in range(ph):
        t = row / max(1, ph - 1)
        shade = int(78 - 18 * t)
        pygame.draw.line(surface, (shade, int(shade * 0.74), int(shade * 0.52)),
                         (x - pw // 2, y - ph + row), (x + pw // 2, y - ph + row))
    pygame.draw.rect(surface, (36, 26, 18), (x - pw // 2, y - ph, pw, ph), 1)
    # Carved top finial
    pygame.draw.polygon(surface, (82, 64, 44),
                        [(x - pw // 2 - 1, y - ph), (x + pw // 2 + 1, y - ph), (x, y - ph - 7)])
    pygame.draw.polygon(surface, (40, 30, 20),
                        [(x - pw // 2 - 1, y - ph), (x + pw // 2 + 1, y - ph), (x, y - ph - 7)], 1)
    # Arrow-shaped sign boards (2-3 pointing different directions)
    num_signs = rng.randint(2, 3)
    for si in range(num_signs):
        sy_s = y - ph + 10 + si * 16
        direction = 1 if si % 2 == 0 else -1
        sw, sh = 30, 8
        sx_s = x + direction * 2
        base = 82 + rng.randint(-8, 8)
        # Board body
        for row in range(sh):
            t = row / max(1, sh - 1)
            shade = int(base - 10 * t)
            pygame.draw.line(surface, (shade, int(shade * 0.74), int(shade * 0.52)),
                             (sx_s, sy_s + row), (sx_s + direction * sw, sy_s + row))
        # Arrow point
        tip_x = sx_s + direction * (sw + 6)
        pygame.draw.polygon(surface, (base - 4, int((base - 4) * 0.72), int((base - 4) * 0.50)), [
            (sx_s + direction * sw, sy_s), (tip_x, sy_s + sh // 2), (sx_s + direction * sw, sy_s + sh)])
        # Board outline
        pygame.draw.rect(surface, (38, 28, 18), (min(sx_s, sx_s + direction * sw), sy_s,
                                                   abs(direction * sw), sh), 1)
        # Text scratches (simulated)
        for _ in range(3):
            tx = sx_s + direction * rng.randint(4, sw - 4)
            pygame.draw.line(surface, (base - 20, int((base - 20) * 0.70), int((base - 20) * 0.46)),
                             (tx, sy_s + 2), (tx + direction * rng.randint(4, 10), sy_s + 2), 1)
    return pygame.Rect(x - 8, y - 6, 16, 8)


def draw_water_pump(surface: pygame.Surface, x: int, y: int) -> pygame.Rect:
    """HD iron hand water pump with spout and handle."""
    # Shadow
    shad = pygame.Surface((30, 10), pygame.SRCALPHA)
    pygame.draw.ellipse(shad, (0, 0, 0, 28), shad.get_rect())
    surface.blit(shad, (x - 15, y - 3))
    # Stone base slab
    for row in range(6):
        shade = 72 - row * 2
        pygame.draw.line(surface, (shade, shade + 2, shade + 4),
                         (x - 12, y - 6 + row), (x + 12, y - 6 + row))
    pygame.draw.rect(surface, (42, 44, 48), (x - 12, y - 6, 24, 6), 1)
    # Iron body — gradient cylinder
    bw, bh = 10, 32
    for row in range(bh):
        t = row / max(1, bh - 1)
        shade = int(64 - 16 * t)
        hw = int(bw * 0.5 * (0.7 + 0.3 * math.sin(t * math.pi)))
        pygame.draw.line(surface, (shade, shade + 2, shade + 4),
                         (x - hw, y - 6 - row), (x + hw, y - 6 - row))
    # Spout — curves out to the right
    for seg in range(8):
        t = seg / 7.0
        sx = x + 4 + int(t * 10)
        sy = y - 22 + int(t * t * 6)
        shade = 58 + int(math.sin(t * math.pi) * 8)
        pygame.draw.circle(surface, (shade, shade + 2, shade + 4), (sx, sy), 2)
    # Water drip from spout
    pygame.draw.line(surface, (60, 100, 140), (x + 14, y - 16), (x + 14, y - 10), 1)
    pygame.draw.circle(surface, (70, 110, 150), (x + 14, y - 9), 1)
    # Handle — iron lever
    pygame.draw.line(surface, (62, 64, 68), (x, y - 36), (x - 10, y - 42), 2)
    pygame.draw.line(surface, (78, 80, 84), (x, y - 37), (x - 10, y - 43), 1)
    # Handle grip
    pygame.draw.circle(surface, (56, 58, 62), (x - 10, y - 42), 3)
    pygame.draw.circle(surface, (72, 74, 78), (x - 10, y - 43), 1)
    return pygame.Rect(x - 12, y - 6, 24, 8)


def draw_torch_stand(surface: pygame.Surface, x: int, y: int) -> pygame.Rect:
    """HD standing iron torch holder with flame."""
    # Shadow
    shad = pygame.Surface((18, 8), pygame.SRCALPHA)
    pygame.draw.ellipse(shad, (0, 0, 0, 26), shad.get_rect())
    surface.blit(shad, (x - 9, y - 3))
    # Tripod base
    for leg_dx in (-6, 6, 0):
        lx0 = x + leg_dx
        for row in range(8):
            t = row / 7.0
            px_l = int(lx0 + (x - lx0) * t)
            shade = int(62 - 10 * t)
            pygame.draw.line(surface, (shade, shade + 2, shade + 4),
                             (px_l - 1, y - row), (px_l + 1, y - row))
    # Iron shaft
    for row in range(40):
        t = row / 39.0
        shade = int(58 + 8 * math.sin(t * math.pi))
        pygame.draw.line(surface, (shade, shade + 2, shade + 4),
                         (x - 1, y - 8 - row), (x + 1, y - 8 - row))
    # Torch cup at top — iron basket
    for row in range(8):
        t = row / 7.0
        hw = int(4 + 2 * t)
        shade = 56 + int(t * 8)
        pygame.draw.line(surface, (shade, shade + 2, shade + 4),
                         (x - hw, y - 48 - row), (x + hw, y - 48 - row))
    pygame.draw.rect(surface, (38, 40, 44), (x - 6, y - 56, 12, 8), 1)
    # Flame — layered glow
    flame_colors = [
        (200, 80, 20, 70), (220, 130, 30, 55), (240, 190, 60, 40), (255, 230, 120, 25)
    ]
    for fi, (fr, fg, fb, fa) in enumerate(flame_colors):
        fh = 12 - fi * 2
        fw_f = 5 - fi
        fs = pygame.Surface((fw_f * 2, fh), pygame.SRCALPHA)
        pygame.draw.polygon(fs, (fr, fg, fb, fa), [(fw_f, 0), (0, fh), (fw_f * 2, fh)])
        surface.blit(fs, (x - fw_f, y - 56 - fh))
    # Warm glow around flame
    glow_s = pygame.Surface((24, 24), pygame.SRCALPHA)
    pygame.draw.circle(glow_s, (200, 100, 30, 20), (12, 12), 12)
    surface.blit(glow_s, (x - 12, y - 68))
    return pygame.Rect(x - 6, y - 4, 12, 6)


def draw_wall_torch(surface: pygame.Surface, x: int, y: int) -> None:
    """HD wall-mounted iron torch bracket with flame (non-obstacle decor)."""
    # Iron bracket — L-shaped
    for row in range(12):
        shade = 62 + int(math.sin(row * 0.5) * 6)
        pygame.draw.line(surface, (shade, shade + 2, shade + 4),
                         (x - 1, y - 12 + row), (x + 1, y - 12 + row))
    pygame.draw.line(surface, (60, 62, 66), (x, y - 12), (x + 8, y - 12), 2)
    # Torch
    pygame.draw.line(surface, (78, 58, 38), (x + 8, y - 14), (x + 8, y - 22), 3)
    # Flame
    flame_s = pygame.Surface((8, 10), pygame.SRCALPHA)
    pygame.draw.polygon(flame_s, (220, 120, 30, 80), [(4, 0), (0, 10), (8, 10)])
    pygame.draw.polygon(flame_s, (255, 200, 60, 50), [(4, 2), (2, 8), (6, 8)])
    surface.blit(flame_s, (x + 4, y - 32))
    # Glow
    glow_s = pygame.Surface((16, 16), pygame.SRCALPHA)
    pygame.draw.circle(glow_s, (200, 100, 30, 18), (8, 8), 8)
    surface.blit(glow_s, (x, y - 32))


def draw_pottery_stack(surface: pygame.Surface, x: int, y: int, seed: int = 0) -> pygame.Rect:
    """HD stack of clay pots, jugs, and amphora."""
    rng = random.Random(x * 107 + y + seed)
    # Shadow
    shad = pygame.Surface((36, 10), pygame.SRCALPHA)
    pygame.draw.ellipse(shad, (0, 0, 0, 24), shad.get_rect())
    surface.blit(shad, (x - 18, y - 3))
    # 3-4 pots of varying shapes
    pot_defs = [
        (x - 8, y, 6, 12, (148, 98, 62)),   # small round pot
        (x + 6, y, 7, 16, (138, 88, 52)),   # tall amphora
        (x - 2, y, 8, 10, (158, 108, 72)),  # wide bowl
        (x + 14, y, 5, 14, (142, 92, 58)),  # thin jug
    ]
    for px_p, py_p, pw_p, ph_p, col in pot_defs:
        # Pot body — gradient with curvature
        for row in range(ph_p):
            t = row / max(1, ph_p - 1)
            bulge = math.sin(t * math.pi) * 1.2
            hw = int(pw_p * (0.6 + 0.4 * bulge))
            shade_r = max(0, int(col[0] - 20 * t + 10 * bulge))
            shade_g = max(0, int(col[1] - 16 * t + 8 * bulge))
            shade_b = max(0, int(col[2] - 12 * t + 6 * bulge))
            pygame.draw.line(surface, (shade_r, shade_g, shade_b),
                             (px_p - hw, py_p - ph_p + row), (px_p + hw, py_p - ph_p + row))
        # Rim
        pygame.draw.ellipse(surface, (col[0] + 10, col[1] + 8, col[2] + 6),
                            (px_p - pw_p // 2, py_p - ph_p - 1, pw_p, 3))
        # Decorative band
        band_y = py_p - ph_p + ph_p // 3
        pygame.draw.line(surface, (col[0] - 24, col[1] - 20, col[2] - 16),
                         (px_p - pw_p // 2, band_y), (px_p + pw_p // 2, band_y), 1)
    return pygame.Rect(x - 14, y - 4, 32, 6)


def draw_fire_pit(surface: pygame.Surface, x: int, y: int) -> pygame.Rect:
    rng = random.Random(x * 37 + y)
    # Outer shadow glow
    glow_s = pygame.Surface((120, 48), pygame.SRCALPHA)
    pygame.draw.ellipse(glow_s, (0, 0, 0, 22), glow_s.get_rect())
    surface.blit(glow_s, (x - 60, y - 20))
    # Ash bed — gradient ellipse with charcoal texture
    for ring in range(6, 0, -1):
        t = ring / 6.0
        shade = int(26 + 12 * (1.0 - t))
        rx_r = int(44 * t)
        ry_r = int(16 * t)
        pygame.draw.ellipse(surface, (shade, shade - 2, shade - 4),
                            (x - rx_r, y - ry_r, rx_r * 2, ry_r * 2))
    # Charcoal chunks scattered in ash
    for _ in range(12):
        cx_c = x + rng.randint(-28, 28)
        cy_c = y + rng.randint(-8, 8)
        cs = rng.randint(2, 4)
        shade = rng.randint(18, 36)
        pygame.draw.circle(surface, (shade, shade - 2, shade - 4), (cx_c, cy_c), cs)
    # Ember glow patches in ash
    for _ in range(6):
        ex = x + rng.randint(-22, 22)
        ey = y + rng.randint(-6, 6)
        er = rng.randint(2, 5)
        eg = pygame.Surface((er * 2, er * 2), pygame.SRCALPHA)
        pygame.draw.circle(eg, (180, 60, 20, 50), (er, er), er)
        surface.blit(eg, (ex - er, ey - er))
    # Stone ring — individual stones with highlights and mortar
    num_stones = 14
    for i in range(num_stones):
        ang = (i / float(num_stones)) * math.tau
        sx_s = x + math.cos(ang) * 38
        sy_s = y + math.sin(ang) * 14
        # Stone base shade varies per stone
        base = 58 + rng.randint(-8, 8)
        stone_r = 8 + rng.randint(-1, 1)
        # Gradient stone (lighter top)
        for sr in range(stone_r, 0, -1):
            t = sr / float(stone_r)
            s = int(base + 14 * (1.0 - t))
            pygame.draw.circle(surface, (s, s - 2, s - 4), (int(sx_s), int(sy_s)), sr)
        pygame.draw.circle(surface, (28, 26, 24), (int(sx_s), int(sy_s)), stone_r, 1)
        # Top highlight
        pygame.draw.circle(surface, (base + 20, base + 18, base + 14), (int(sx_s) - 1, int(sy_s) - 2), 2)
    # Logs — 3D with bark texture and wood grain
    log_defs = [
        (x - 18, y - 1, x + 18, y + 3, 0.2),   # front-left to back-right
        (x + 18, y - 1, x - 18, y + 3, -0.15),  # front-right to back-left
        (x - 8, y - 3, x + 8, y - 1, 0.0),      # smaller top log
    ]
    for lx0, ly0, lx1, ly1, rot in log_defs:
        # Bark body
        length = math.hypot(lx1 - lx0, ly1 - ly0)
        for offset in range(-3, 4):
            t = (offset + 3) / 6.0
            shade = int(72 - 24 * abs(t - 0.5))
            norm_x = -(ly1 - ly0) / max(1, length)
            norm_y = (lx1 - lx0) / max(1, length)
            ox = int(norm_x * offset)
            oy = int(norm_y * offset)
            pygame.draw.line(surface, (shade, int(shade * 0.68), int(shade * 0.42)),
                             (lx0 + ox, ly0 + oy), (lx1 + ox, ly1 + oy), 1)
        # End grain circles
        pygame.draw.circle(surface, (68, 52, 34), (lx0, ly0), 3)
        pygame.draw.circle(surface, (48, 36, 24), (lx0, ly0), 3, 1)
        pygame.draw.circle(surface, (58, 44, 28), (lx0, ly0), 1)
    # Static fire — layered flame tongues (the VFX fire particles are added per-frame)
    flame_colors = [
        (200, 80, 20, 90), (220, 120, 30, 80), (240, 180, 50, 60),
        (255, 220, 100, 40), (255, 240, 180, 30),
    ]
    for fi, (fr, fg, fb, fa) in enumerate(flame_colors):
        fh = 18 - fi * 3
        fw_f = 14 - fi * 2
        flame_s = pygame.Surface((fw_f * 2, fh), pygame.SRCALPHA)
        # Draw flame tongue shape
        points = [(fw_f, 0), (0, fh), (fw_f * 2, fh)]
        pygame.draw.polygon(flame_s, (fr, fg, fb, fa), points)
        surface.blit(flame_s, (x - fw_f, y - 8 - fh))
    # Warm glow on ground around pit
    glow_r = pygame.Surface((100, 40), pygame.SRCALPHA)
    pygame.draw.ellipse(glow_r, (200, 100, 30, 16), glow_r.get_rect())
    surface.blit(glow_r, (x - 50, y - 16))
    return pygame.Rect(x - 40, y - 20, 80, 40)


def draw_stone_arch(surface: pygame.Surface, cx: int, base_y: int, w: int = 220, h: int = 180) -> None:
    """Draw a decorative stone archway frame with HD detail."""
    rng = random.Random(cx * 61 + base_y + w)
    pillar_w = 22
    pillar_h = h
    # Pillars — gradient stone with individual blocks and mortar
    for px in (cx - w // 2, cx + w // 2 - pillar_w):
        # Gradient fill
        for row in range(pillar_h):
            t = row / max(1, pillar_h - 1)
            shade = int(74 - 14 * t)
            pygame.draw.line(surface, (shade, shade + 2, shade + 4),
                             (px + 1, base_y - pillar_h + row), (px + pillar_w - 1, base_y - pillar_h + row))
        # Stone block mortar lines
        block_h = 14
        for bi, sy in enumerate(range(base_y - pillar_h, base_y, block_h)):
            pygame.draw.line(surface, (42, 44, 48), (px + 1, sy), (px + pillar_w - 1, sy), 1)
            # Vertical mortar (offset alternating rows)
            mx = px + pillar_w // 2 + (6 if bi % 2 == 0 else -6)
            pygame.draw.line(surface, (42, 44, 48), (mx, sy), (mx, sy + block_h), 1)
        # Weathering — darker stains near base
        for row in range(min(20, pillar_h)):
            alpha = max(0, 30 - row * 2)
            ws = pygame.Surface((pillar_w, 1), pygame.SRCALPHA)
            ws.fill((20, 30, 18, alpha))
            surface.blit(ws, (px, base_y - row))
        pygame.draw.rect(surface, (38, 40, 44), (px, base_y - pillar_h, pillar_w, pillar_h), 2)
        # Capital (decorative top of pillar)
        cap_rect = pygame.Rect(px - 3, base_y - pillar_h - 4, pillar_w + 6, 6)
        for row in range(6):
            shade = 78 - row * 2
            pygame.draw.line(surface, (shade, shade + 2, shade + 4),
                             (cap_rect.left, cap_rect.top + row), (cap_rect.right, cap_rect.top + row))
        pygame.draw.rect(surface, (40, 42, 46), cap_rect, 1)
    # Lintel/arch header — gradient with carved keystone
    arch_rect = pygame.Rect(cx - w // 2 - 4, base_y - pillar_h - 36, w + 8, 40)
    for row in range(40):
        t = row / 39.0
        shade = int(76 - 12 * t)
        pygame.draw.line(surface, (shade, shade + 2, shade + 4),
                         (arch_rect.left + 1, arch_rect.top + row), (arch_rect.right - 1, arch_rect.top + row))
    # Block joints on lintel
    for mx in range(arch_rect.left + 16, arch_rect.right - 8, 22):
        pygame.draw.line(surface, (42, 44, 48), (mx, arch_rect.top + 1), (mx, arch_rect.bottom - 1), 1)
    pygame.draw.rect(surface, (38, 40, 44), arch_rect, 2, border_radius=4)
    # Keystone — prominent center block
    ks_w, ks_h = 18, 28
    ks_rect = pygame.Rect(cx - ks_w // 2, arch_rect.top + 4, ks_w, ks_h)
    for row in range(ks_h):
        t = row / max(1, ks_h - 1)
        shade = int(82 - 10 * t)
        pygame.draw.line(surface, (shade, shade + 2, shade + 6),
                         (ks_rect.left + 1, ks_rect.top + row), (ks_rect.right - 1, ks_rect.top + row))
    pygame.draw.rect(surface, (40, 42, 46), ks_rect, 1)
    # Carved emblem on keystone
    pygame.draw.circle(surface, (62, 64, 68), (cx, ks_rect.centery), 5, 1)
    pygame.draw.line(surface, (62, 64, 68), (cx, ks_rect.centery - 3), (cx, ks_rect.centery + 3), 1)
    pygame.draw.line(surface, (62, 64, 68), (cx - 3, ks_rect.centery), (cx + 3, ks_rect.centery), 1)

def draw_district_ground(surface: pygame.Surface, rect: pygame.Rect, style: str, seed: int = 42) -> None:
    """Fills a rect with district-specific ground texture."""
    rng = random.Random(seed)
    
    # Base fill
    base_col = (60, 60, 60)
    if style == "ember": base_col = (45, 42, 42) # Soot dark
    elif style == "bloodmarket": base_col = (90, 85, 80) # Warm stone
    elif style == "saint": base_col = (70, 75, 70) # Pale/Mossy
    elif style == "rook": base_col = (55, 50, 40) # Dirt/Mud
    elif style == "iron": base_col = (80, 82, 85) # Cold stone
    
    pygame.draw.rect(surface, base_col, rect)
    
    # Texture details
    if style == "ember":
        # Soot patches and dark cobble
        for _ in range(int(rect.width * rect.height / 2000)):
            rx = rng.randint(rect.left, rect.right)
            ry = rng.randint(rect.top, rect.bottom)
            pygame.draw.circle(surface, (30, 28, 28), (rx, ry), rng.randint(4, 12))
    elif style == "bloodmarket":
        # Clean cobble
        draw_cobblestones(surface, rect, seed)
    elif style == "saint":
        # Cracked stone and moss
        for _ in range(int(rect.width * rect.height / 3000)):
            rx = rng.randint(rect.left, rect.right)
            ry = rng.randint(rect.top, rect.bottom)
            # Moss
            pygame.draw.circle(surface, (60, 80, 60), (rx, ry), rng.randint(3, 8))
    elif style == "rook":
        # Mud patches
        for _ in range(int(rect.width * rect.height / 1500)):
            rx = rng.randint(rect.left, rect.right)
            ry = rng.randint(rect.top, rect.bottom)
            pygame.draw.ellipse(surface, (45, 40, 30), (rx, ry, rng.randint(10, 30), rng.randint(5, 15)))
    elif style == "iron":
        # Large flagstones
        for y in range(rect.top, rect.bottom, 30):
            for x in range(rect.left, rect.right, 50):
                r = pygame.Rect(x, y, 48, 28)
                pygame.draw.rect(surface, (70, 72, 75), r)
                pygame.draw.rect(surface, (50, 52, 55), r, 1)



def draw_canal_water(surface: pygame.Surface, rect: pygame.Rect, ticks: int, color_base: tuple[int, int, int] = (24, 32, 40)) -> None:
    pygame.draw.rect(surface, color_base, rect)
    # Reflections/Ripples
    for i in range(0, rect.height, 4):
        off = (math.sin(i * 0.1 + ticks * 0.002) * 4)
        color = (color_base[0] + 10, color_base[1] + 12, color_base[2] + 14) if i % 8 == 0 else (color_base[0] + 4, color_base[1] + 4, color_base[2] + 6)
        pygame.draw.line(surface, color, (rect.left, rect.top + i), (rect.right, rect.top + i))

def draw_stone_bridge(surface: pygame.Surface, rect: pygame.Rect, vertical: bool = False) -> None:
    rng = random.Random(rect.x * 67 + rect.y)
    # Base gradient fill
    if vertical:
        for col_off in range(rect.width):
            t = col_off / max(1, rect.width - 1)
            shade = int(66 - 12 * abs(t - 0.5) * 2)
            pygame.draw.line(surface, (shade, shade + 2, shade + 4),
                             (rect.left + col_off, rect.top), (rect.left + col_off, rect.bottom))
    else:
        for row in range(rect.height):
            t = row / max(1, rect.height - 1)
            shade = int(66 - 12 * abs(t - 0.5) * 2)
            pygame.draw.line(surface, (shade, shade + 2, shade + 4),
                             (rect.left, rect.top + row), (rect.right, rect.top + row))
    # Stone block pattern with mortar
    block_size = 12
    if vertical:
        for bi, by in enumerate(range(rect.top, rect.bottom, block_size)):
            pygame.draw.line(surface, (44, 46, 50), (rect.left, by), (rect.right, by), 1)
            offset = 6 if bi % 2 == 0 else 0
            for bx in range(rect.left + offset, rect.right, block_size):
                pygame.draw.line(surface, (44, 46, 50), (bx, by), (bx, min(by + block_size, rect.bottom)), 1)
        # Railings/parapet walls
        for rail_x in (rect.left, rect.right - 6):
            rw = 6
            for row in range(rect.height):
                t = row / max(1, rect.height - 1)
                shade = int(52 - 10 * t)
                pygame.draw.line(surface, (shade, shade + 2, shade + 4),
                                 (rail_x, rect.top + row), (rail_x + rw, rect.top + row))
            pygame.draw.rect(surface, (36, 38, 42), (rail_x, rect.top, rw, rect.height), 1)
    else:
        for bi, bx in enumerate(range(rect.left, rect.right, block_size)):
            pygame.draw.line(surface, (44, 46, 50), (bx, rect.top), (bx, rect.bottom), 1)
            offset = 6 if bi % 2 == 0 else 0
            for by in range(rect.top + offset, rect.bottom, block_size):
                pygame.draw.line(surface, (44, 46, 50), (bx, by), (min(bx + block_size, rect.right), by), 1)
        # Railings
        for rail_y in (rect.top, rect.bottom - 6):
            rh = 6
            for row in range(rh):
                shade = 52 - row * 2
                pygame.draw.line(surface, (shade, shade + 2, shade + 4),
                                 (rect.left, rail_y + row), (rect.right, rail_y + row))
            pygame.draw.rect(surface, (36, 38, 42), (rect.left, rail_y, rect.width, rh), 1)
    # Weathering stains
    for _ in range(4):
        wx = rect.left + rng.randint(0, rect.width - 4)
        wy = rect.top + rng.randint(0, rect.height - 4)
        ws = pygame.Surface((rng.randint(4, 10), rng.randint(4, 10)), pygame.SRCALPHA)
        ws.fill((22, 28, 20, 18))
        surface.blit(ws, (wx, wy))
    # Outline
    pygame.draw.rect(surface, (36, 38, 42), rect, 2)

def draw_gothic_spire(surface: pygame.Surface, x: int, y: int, w: int, h: int, color: tuple[int, int, int]):
    rng = random.Random(x * 71 + y + w + h)
    rect = pygame.Rect(x - w // 2, y - h, w, h)
    # Tower body — gradient stone with block pattern
    for row in range(h):
        t = row / max(1, h - 1)
        shade_r = max(0, int(color[0] - 14 * t))
        shade_g = max(0, int(color[1] - 14 * t))
        shade_b = max(0, int(color[2] - 14 * t))
        pygame.draw.line(surface, (shade_r, shade_g, shade_b),
                         (rect.left + 1, rect.top + row), (rect.right - 1, rect.top + row))
    # Stone block mortar
    block_h = max(8, h // 8)
    for bi, my in enumerate(range(rect.top, rect.bottom, block_h)):
        pygame.draw.line(surface, (max(0, color[0] - 26), max(0, color[1] - 26), max(0, color[2] - 26)),
                         (rect.left + 1, my), (rect.right - 1, my), 1)
        offset = w // 3 if bi % 2 == 0 else 0
        for mx in range(rect.left + offset, rect.right, max(6, w // 2)):
            pygame.draw.line(surface, (max(0, color[0] - 26), max(0, color[1] - 26), max(0, color[2] - 26)),
                             (mx, my), (mx, min(my + block_h, rect.bottom)), 1)
    pygame.draw.rect(surface, (30, 30, 34), rect, 2)
    # Spire roof — gradient with tile lines
    roof_h = int(h * 1.5)
    for row in range(roof_h):
        t = row / max(1, roof_h - 1)
        half_w = int((w // 2 + 4) * (1.0 - t))
        shade = int(28 - 14 * t)
        pygame.draw.line(surface, (shade, shade + 2, shade + 4),
                         (x - half_w, y - h - row), (x + half_w, y - h - row))
    # Tile ridge lines on roof
    for row in range(4, roof_h - 4, 8):
        t = row / max(1, roof_h - 1)
        half_w = int((w // 2 + 4) * (1.0 - t))
        pygame.draw.line(surface, (14, 16, 18), (x - half_w + 1, y - h - row), (x + half_w - 1, y - h - row), 1)
    # Spire outline
    points = [(x - w // 2 - 4, y - h), (x + w // 2 + 4, y - h), (x, y - h - roof_h)]
    pygame.draw.polygon(surface, (12, 12, 14), points, 2)
    # Finial (spire tip ornament)
    pygame.draw.circle(surface, (68, 66, 62), (x, y - h - roof_h - 2), 3)
    pygame.draw.circle(surface, (88, 86, 82), (x, y - h - roof_h - 3), 1)
    # Gothic arch window — pointed arch shape with stained glass
    win_w = max(4, w // 3)
    win_h = max(6, h // 3)
    win_cx = x
    win_top = y - h + h // 4
    # Pointed arch shape
    arch_pts = []
    for i in range(16):
        t = i / 15.0
        ang = math.pi * t
        ax = win_cx + int(math.sin(ang) * win_w * 0.5) - win_w // 2
        ay = win_top + win_h - int((math.sin(ang * 0.5)) * win_h)
        arch_pts.append((win_cx + int(math.cos(ang + math.pi * 0.5) * win_w * 0.5), ay))
    if len(arch_pts) > 2:
        pygame.draw.polygon(surface, (8, 8, 12), arch_pts)
        pygame.draw.polygon(surface, (34, 34, 38), arch_pts, 1)
    # Stained glass glow
    glow_s = pygame.Surface((win_w + 4, win_h + 4), pygame.SRCALPHA)
    pygame.draw.ellipse(glow_s, (200, 170, 80, 40), glow_s.get_rect())
    surface.blit(glow_s, (win_cx - win_w // 2 - 2, win_top - 2))
    # Central mullion (divider)
    pygame.draw.line(surface, (46, 46, 50), (win_cx, win_top + 2), (win_cx, win_top + win_h - 2), 1)
    # Cross bar
    pygame.draw.line(surface, (46, 46, 50), (win_cx - win_w // 3, win_top + win_h // 2),
                     (win_cx + win_w // 3, win_top + win_h // 2), 1)

def draw_fortified_wall(surface: pygame.Surface, rect: pygame.Rect, vertical: bool = False) -> None:
    color = (50, 52, 56)
    dark = (30, 32, 36)
    pygame.draw.rect(surface, color, rect)
    pygame.draw.rect(surface, dark, rect, 2)
    
    # Crenellations
    cren_size = 12
    if vertical:
        for y in range(rect.top, rect.bottom, cren_size * 2):
            pygame.draw.rect(surface, dark, (rect.left + 2, y, 4, cren_size))
            pygame.draw.rect(surface, dark, (rect.right - 6, y, 4, cren_size))
    else:
        for x in range(rect.left, rect.right, cren_size * 2):
            pygame.draw.rect(surface, dark, (x, rect.top + 2, cren_size, 4))

def draw_district_house(surface, x, y, scale, seed, district="bloodmarket"):  # noqa: C901
    """Dispatch to one of the 6 HD house style functions based on district + seed.

    Each style function uses detailed helpers: gradient fills, hash-based masonry,
    iron hardware, weathering overlays, lanterns, etc.
    """
    # ── Style pools per district — each district favours certain architectural styles ──
    # Styles: 0=tudor, 1=stone, 2=cottage, 3=merchant, 4=rowhouse, 5=workshop
    _style_pools = {
        "noble":    [1, 1, 3, 3, 0, 4],       # stone townhouse + merchant dominant
        "saint":    [0, 0, 1, 3, 4, 4],        # tudor + rowhouse
        "artisan":  [5, 5, 2, 2, 0, 5],        # workshop + cottage
        "harbor":   [2, 2, 5, 4, 4, 2],        # cottage + rowhouse
        "shanty":   [2, 2, 2, 4, 4, 5],        # cottage (small) + rowhouse
        "ember":    [0, 5, 5, 1, 0, 4],        # tudor + workshop
        "rook":     [4, 4, 0, 1, 5, 3],        # rowhouse heavy
        "bloodmarket": [0, 1, 2, 3, 4, 5],     # all styles equally
    }
    import random as _rmod
    rng = _rmod.Random(seed)
    pool = _style_pools.get(district, _style_pools["bloodmarket"])
    style_idx = pool[seed % len(pool)]
    # Extra rotation based on seed to avoid repetition even within same district
    style_idx = (style_idx + seed // 7) % 6

    _style_funcs = [
        _draw_house_tudor,      # base ~128px wide
        _draw_house_stone,      # base ~90px wide
        _draw_house_cottage,    # base ~120px wide
        _draw_house_merchant,   # base ~140px wide
        _draw_house_rowhouse,   # base ~72px wide
        _draw_house_workshop,   # base ~126px wide
    ]
    # HD functions have small base sizes (~72-140px). Scale them up to match
    # the original district house sizes (200-420px).
    _base_widths = [128, 90, 120, 140, 72, 126]
    if district == "noble":
        _target_w = 420
    elif district == "shanty":
        _target_w = 200
    elif district == "artisan":
        _target_w = 340
    elif district == "harbor":
        _target_w = 260
    else:
        _target_w = 320
    _up = _target_w / _base_widths[style_idx]
    fnd = _style_funcs[style_idx](surface, x, y, scale * _up, seed)
    # Phase-3 uniqueness layer: structural add-ons (annex, dormers, laundry,
    # flower boxes, hoists, woodpiles...) so every house is a one-off. May
    # widen the returned collision rect when an annex extends the footprint.
    return _draw_house_variations(surface, x, y, scale * _up, seed, district, style_idx, fnd)




def _district_house_chimney_top(x: int, y: int, scale: float, seed: int, district: str = "bloodmarket") -> Optional[Tuple[int, int]]:
    """Return chimney top world position for a district house, or None.

    Uses the same style dispatch as draw_district_house → _house_chimney_top.
    """
    _style_pools = {
        "noble":    [1, 1, 3, 3, 0, 4],
        "saint":    [0, 0, 1, 3, 4, 4],
        "artisan":  [5, 5, 2, 2, 0, 5],
        "harbor":   [2, 2, 5, 4, 4, 2],
        "shanty":   [2, 2, 2, 4, 4, 5],
        "ember":    [0, 5, 5, 1, 0, 4],
        "rook":     [4, 4, 0, 1, 5, 3],
        "bloodmarket": [0, 1, 2, 3, 4, 5],
    }
    pool = _style_pools.get(district, _style_pools["bloodmarket"])
    style_idx = pool[seed % len(pool)]
    style_idx = (style_idx + seed // 7) % 6
    # Apply same scale-up as draw_district_house
    _base_widths = [128, 90, 120, 140, 72, 126]
    if district == "noble":
        _target_w = 420
    elif district == "shanty":
        _target_w = 200
    elif district == "artisan":
        _target_w = 340
    elif district == "harbor":
        _target_w = 260
    else:
        _target_w = 320
    _up = _target_w / _base_widths[style_idx]
    return _house_chimney_top(x, y, scale * _up, seed)


def collect_district_chimney_tops(house_specs, base_seed: int = 900) -> List[Tuple[int, int]]:
    """Build list of chimney top world positions from all district houses."""
    chimneys: List[Tuple[int, int]] = []
    for idx, spec in enumerate(house_specs):
        # Support both 3-tuple (x, y, style) and 4-tuple (x, y, style, scale)
        if len(spec) == 4:
            hx, hy, style, sc = spec
        else:
            hx, hy, style = spec
            sc = 1.0 if style != 'ember' else 1.08
        pos = _district_house_chimney_top(hx, hy, sc, base_seed + idx, style)
        if pos is not None:
            chimneys.append(pos)
    return chimneys


def draw_cathedral_v2(surface: pygame.Surface, x: int, y: int) -> pygame.Rect:
    # Massive gothic structure
    w, h = 400, 300
    base_rect = pygame.Rect(x - w // 2, y - h, w, h)
    
    # Main Nave
    pygame.draw.rect(surface, (70, 72, 76), base_rect)
    
    # Flying Buttresses
    for i in range(4):
        bx = base_rect.left - 30 + i * (w // 3)
        pygame.draw.line(surface, (50, 52, 56), (bx, y), (bx + 20, y - h // 2), 6)
    
    # Central Spire
    draw_gothic_spire(surface, x, y - h, 80, 180, (60, 62, 66))
    # Flanking Spires
    draw_gothic_spire(surface, x - 120, y - h + 40, 50, 120, (60, 62, 66))
    draw_gothic_spire(surface, x + 120, y - h + 40, 50, 120, (60, 62, 66))
    
    # Rose Window
    pygame.draw.circle(surface, (20, 20, 24), (x, y - h // 2), 40)
    pygame.draw.circle(surface, (100, 40, 140), (x, y - h // 2), 36, 4) # Stained glass rim
    
    # Entrance
    door_rect = pygame.Rect(x - 40, y - 80, 80, 80)
    pygame.draw.rect(surface, (30, 20, 10), door_rect, border_radius=40)
    pygame.draw.rect(surface, (50, 52, 56), door_rect, 4, border_radius=40)
    
    return pygame.Rect(x - w // 2, y - 100, w, 100)

def draw_hd_barrel(surface: pygame.Surface, x: int, y: int) -> pygame.Rect:
    w, h = 48, 64
    rect = pygame.Rect(x - w // 2, y - h, w, h)
    
    # Shadow
    pygame.draw.ellipse(surface, (10, 10, 12), (x - w // 2 - 4, y - 6, w + 8, 16))
    
    # Vertical planks
    plank_count = 6
    plank_w = w / plank_count
    
    for i in range(plank_count):
        px = rect.left + i * plank_w
        # Curvature shading: darker on sides
        dist_from_center = abs((i + 0.5) - plank_count / 2) / (plank_count / 2)
        base_col = (110, 75, 45)
        shade = int(40 * dist_from_center)
        col = (max(0, base_col[0] - shade), max(0, base_col[1] - shade), max(0, base_col[2] - shade))
        
        plank_r = pygame.Rect(px, rect.top, plank_w + 1, h)
        pygame.draw.rect(surface, col, plank_r)
        
        # Wood grain
        for _ in range(4):
            gy = rect.top + random.randint(5, h - 5)
            g_len = random.randint(4, 10)
            pygame.draw.line(surface, (max(0, col[0]-20), max(0, col[1]-20), max(0, col[2]-20)), (px + 2, gy), (px + 2 + g_len, gy), 1)
            
        # Vertical separators
        pygame.draw.line(surface, (40, 25, 15), (px, rect.top), (px, rect.bottom), 1)

    # Metal hoops
    hoop_color = (70, 75, 80)
    hoop_light = (110, 115, 120)
    hoop_dark = (30, 35, 40)
    
    hoop_y_positions = [rect.top + 10, rect.bottom - 16]
    
    for hy in hoop_y_positions:
        hoop_rect = pygame.Rect(rect.left - 2, hy, w + 4, 8)
        pygame.draw.rect(surface, hoop_color, hoop_rect, border_radius=3)
        # Highlight top
        pygame.draw.line(surface, hoop_light, (hoop_rect.left + 2, hoop_rect.top + 1), (hoop_rect.right - 2, hoop_rect.top + 1), 1)
        # Shadow bottom
        pygame.draw.line(surface, hoop_dark, (hoop_rect.left + 2, hoop_rect.bottom - 1), (hoop_rect.right - 2, hoop_rect.bottom - 1), 1)
        
        # Rivets
        for i in range(plank_count + 1):
            rx = rect.left + i * plank_w
            pygame.draw.circle(surface, (40, 40, 45), (int(rx), int(hy + 4)), 1)

    # Top lid (perspective)
    pygame.draw.ellipse(surface, (50, 30, 15), (rect.left, rect.top - 6, w, 12))
    pygame.draw.ellipse(surface, (90, 60, 35), (rect.left + 4, rect.top - 4, w - 8, 8))
    
    # Bung hole
    pygame.draw.circle(surface, (20, 10, 5), (rect.centerx, rect.centery), 3)
    
    return rect

def draw_hd_hay(surface: pygame.Surface, x: int, y: int) -> pygame.Rect:
    w, h = 52, 36
    rect = pygame.Rect(x - w // 2, y - h, w, h)
    
    # Shadow
    pygame.draw.ellipse(surface, (10, 10, 12), (x - w // 2 - 4, y - 6, w + 8, 14))
    
    # Bale body (Golden/Straw color)
    pygame.draw.rect(surface, (200, 170, 60), rect, border_radius=5)
    
    # Texture details (straw strands)
    for _ in range(25):
        sx = random.randint(rect.left + 4, rect.right - 4)
        sy = random.randint(rect.top + 4, rect.bottom - 4)
        sl = random.randint(4, 12)
        pygame.draw.line(surface, (160, 130, 40), (sx, sy), (sx + sl, sy + 1), 1)
        
    # Binding ropes
    rope_col = (120, 100, 80)
    pygame.draw.line(surface, rope_col, (rect.left + 14, rect.top), (rect.left + 14, rect.bottom), 2)
    pygame.draw.line(surface, rope_col, (rect.right - 14, rect.top), (rect.right - 14, rect.bottom), 2)
    
    # Outline/Shading
    pygame.draw.rect(surface, (130, 110, 40), rect, 1, border_radius=5)
    
    return rect

def draw_hd_cart(surface: pygame.Surface, x: int, y: int) -> pygame.Rect:
    w, h = 96, 48
    # Shadow
    pygame.draw.ellipse(surface, (10, 10, 12), (x - w // 2, y - 8, w, 16))
    
    # Back Wheel (darker/behind)
    pygame.draw.circle(surface, (40, 30, 20), (x + 20, y - 12), 18)
    pygame.draw.circle(surface, (20, 15, 10), (x + 20, y - 12), 18, 2)
    
    # Cart Bed
    bed_rect = pygame.Rect(x - w // 2, y - h - 12, w - 20, h)
    pygame.draw.rect(surface, (100, 70, 40), bed_rect, border_radius=2)
    pygame.draw.rect(surface, (60, 40, 20), bed_rect, 2, border_radius=2)
    
    # Wood planks on bed
    for i in range(1, 4):
        py = bed_rect.top + i * 10
        pygame.draw.line(surface, (80, 55, 30), (bed_rect.left + 2, py), (bed_rect.right - 2, py), 1)
        
    # Front Wheel (lighter/closer)
    pygame.draw.circle(surface, (70, 50, 30), (x - 10, y - 8), 20)
    pygame.draw.circle(surface, (40, 30, 15), (x - 10, y - 8), 20, 3)
    pygame.draw.circle(surface, (30, 20, 10), (x - 10, y - 8), 4) # Axle
    
    # Handle/Tongue
    pygame.draw.line(surface, (90, 65, 40), (bed_rect.right, bed_rect.bottom - 5), (x + w // 2 + 10, y), 4)
    
    return pygame.Rect(x - w // 2, y - h - 12, w + 10, h + 12)

def draw_transylvanian_asset(surface: pygame.Surface, x: int, y: int, kind: str) -> pygame.Rect:
    rect = pygame.Rect(x - 20, y - 20, 40, 40)
    
    if kind == "troita":
        # Roadside Cross (TroiÈ›Äƒ) - Intricate wooden cross with roof
        w, h = 40, 90
        rect = pygame.Rect(x - w//2, y - h, w, h)
        # Base
        pygame.draw.rect(surface, (70, 60, 50), (x - 12, y - 10, 24, 10))
        # Post
        pygame.draw.rect(surface, (55, 45, 35), (x - 5, y - h, 10, h))
        # Crossbars (Triple cross style common in orthodoxy)
        pygame.draw.rect(surface, (55, 45, 35), (x - 18, y - h + 25, 36, 6))
        pygame.draw.rect(surface, (55, 45, 35), (x - 12, y - h + 45, 24, 5))
        # Roof
        roof_poly = [(x - 28, y - h + 10), (x + 28, y - h + 10), (x, y - h - 12)]
        pygame.draw.polygon(surface, (45, 40, 35), roof_poly)
        # Carvings/Details
        pygame.draw.circle(surface, (180, 160, 100), (x, y - h + 28), 3)

    elif kind == "sweep_well":
        # FÃ¢ntÃ¢nÄƒ cu cumpÄƒnÄƒ (Sweep well)
        rect = pygame.Rect(x - 30, y - 60, 60, 60)
        # Fork post
        pygame.draw.line(surface, (80, 70, 60), (x + 20, y), (x + 20, y - 50), 5)
        # Sweep pole (diagonal)
        pygame.draw.line(surface, (70, 60, 50), (x + 20, y - 50), (x - 50, y - 10), 3) # Counterweight side
        pygame.draw.line(surface, (70, 60, 50), (x + 20, y - 50), (x + 45, y - 80), 3) # Bucket side
        # Rope & Bucket
        pygame.draw.line(surface, (110, 100, 90), (x + 45, y - 80), (x + 45, y - 20), 1)
        pygame.draw.rect(surface, (60, 50, 40), (x + 40, y - 20, 10, 12))
        # Well base
        pygame.draw.rect(surface, (90, 90, 95), (x + 35, y - 10, 20, 10))
        pygame.draw.rect(surface, (50, 50, 55), (x + 35, y - 10, 20, 10), 1)

    elif kind == "impaled_stake":
        # Vlad the Impaler theme
        rect = pygame.Rect(x - 5, y - 60, 10, 60)
        pygame.draw.line(surface, (70, 50, 40), (x, y), (x, y - 60), 5)
        # Sharp Point & Blood
        pygame.draw.line(surface, (140, 20, 20), (x, y - 40), (x, y - 60), 5)
        # Skull on top?
        pygame.draw.circle(surface, (200, 200, 190), (x, y - 64), 6)
        pygame.draw.circle(surface, (20, 10, 10), (x - 2, y - 64), 1)
        pygame.draw.circle(surface, (20, 10, 10), (x + 2, y - 64), 1)

    elif kind == "wooden_gate":
        # PoartÄƒ MaramureÈ™eanÄƒ (Monumental wooden gate)
        w, h = 110, 100
        rect = pygame.Rect(x - w//2, y - h, w, h)
        # Pillars
        pygame.draw.rect(surface, (70, 60, 50), (x - 45, y - h, 14, h))
        pygame.draw.rect(surface, (70, 60, 50), (x + 31, y - h, 14, h))
        # Arch/Lintel
        pygame.draw.rect(surface, (70, 60, 50), (x - 50, y - h, 100, 18))
        # Shingled Roof
        roof_poly = [(x - 60, y - h), (x + 60, y - h), (x, y - h - 24)]
        pygame.draw.polygon(surface, (50, 40, 30), roof_poly)
        # Carved Sun Motif (Rosette)
        pygame.draw.circle(surface, (60, 50, 40), (x - 38, y - h + 40), 10, 2)
        pygame.draw.circle(surface, (60, 50, 40), (x + 38, y - h + 40), 10, 2)

    elif kind == "haystack":
        # CÄƒpiÈ›Äƒ (Traditional conical haystack)
        w, h = 44, 64
        rect = pygame.Rect(x - w//2, y - h, w, h)
        # Cone body
        pts = [(x - 22, y), (x + 22, y), (x, y - 54)]
        pygame.draw.polygon(surface, (190, 170, 70), pts)
        # Central pole sticking out top
        pygame.draw.line(surface, (90, 80, 70), (x, y - 54), (x, y - 64), 3)
        # Texture lines
        for _ in range(12):
            rx = random.randint(x - 12, x + 12)
            ry = random.randint(y - 40, y)
            pygame.draw.line(surface, (150, 130, 50), (rx, ry), (rx + 4, ry + 4), 1)

    elif kind == "execution_block":
        rect = pygame.Rect(x - 15, y - 20, 30, 20)
        pygame.draw.rect(surface, (80, 70, 60), rect) # Stump
        pygame.draw.ellipse(surface, (100, 90, 80), (x - 15, y - 25, 30, 10)) # Top
        pygame.draw.ellipse(surface, (160, 30, 30), (x - 10, y - 24, 20, 8)) # Blood pool
        # Axe embedded
        pygame.draw.line(surface, (70, 60, 50), (x + 5, y - 25), (x + 25, y - 50), 3) # Handle
        pygame.draw.polygon(surface, (120, 120, 130), [(x + 5, y - 25), (x - 4, y - 30), (x + 8, y - 34)]) # Blade

    elif kind == "coffin":
        rect = pygame.Rect(x - 15, y - 40, 30, 40)
        pts = [(x, y - 40), (x + 14, y - 30), (x + 10, y), (x - 10, y), (x - 14, y - 30)]
        pygame.draw.polygon(surface, (50, 40, 35), pts)
        pygame.draw.polygon(surface, (30, 20, 15), pts, 1)
        pygame.draw.line(surface, (70, 60, 50), (x, y - 32), (x, y - 12), 2) # Cross vertical
        pygame.draw.line(surface, (70, 60, 50), (x - 6, y - 26), (x + 6, y - 26), 2) # Cross horizontal

    elif kind == "garlic_stand":
        rect = pygame.Rect(x - 20, y - 30, 40, 30)
        pygame.draw.rect(surface, (90, 70, 50), (x - 20, y - 20, 40, 20)) # Table
        for i in range(5): # Garlic bulbs
            pygame.draw.circle(surface, (230, 230, 220), (x - 15 + i * 8, y - 22), 3)

    return rect

# ═══════════════════════════════════════════════════════════════════════════
#  NEW TOWN FEATURES — Farms, Harbour, Cemetery, Dirt Roads
# ═══════════════════════════════════════════════════════════════════════════

def draw_paved_road(surface: pygame.Surface, x1: int, y1: int, x2: int, y2: int,
                    width: int = 90, seed: int = 0) -> None:
    """Draw a cobblestone paved road between two points with gutter edges."""
    rng = random.Random(seed + x1 * 3 + y1 * 11)
    dx = x2 - x1
    dy = y2 - y1
    length = max(1, int(math.hypot(dx, dy)))
    nx, ny = -dy / length, dx / length
    hw = width // 2
    # Build edge polygon
    left_pts = []
    right_pts = []
    steps = max(4, length // 50)
    for i in range(steps + 1):
        t = i / steps
        mx = x1 + dx * t
        my = y1 + dy * t
        left_pts.append((int(mx + nx * hw), int(my + ny * hw)))
        right_pts.append((int(mx - nx * hw), int(my - ny * hw)))
    pts = left_pts + list(reversed(right_pts))
    # Road base
    pygame.draw.polygon(surface, (68, 68, 72), pts)
    # Cobblestone fill via bounding rect
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    cob_rect = pygame.Rect(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
    if cob_rect.width > 0 and cob_rect.height > 0:
        cob_surf = pygame.Surface((cob_rect.width, cob_rect.height), pygame.SRCALPHA)
        cob_area = pygame.Rect(0, 0, cob_rect.width, cob_rect.height)
        draw_cobblestones(cob_surf, cob_area, seed=seed + 500)
        # Mask to road polygon shape
        mask_surf = pygame.Surface((cob_rect.width, cob_rect.height), pygame.SRCALPHA)
        shifted = [(p[0] - cob_rect.x, p[1] - cob_rect.y) for p in pts]
        pygame.draw.polygon(mask_surf, (255, 255, 255, 255), shifted)
        cob_surf.blit(mask_surf, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        surface.blit(cob_surf, cob_rect.topleft)
    # Gutter edges (darker border)
    pygame.draw.lines(surface, (38, 38, 42), False, left_pts, 3)
    pygame.draw.lines(surface, (38, 38, 42), False, list(reversed(right_pts)), 3)


def draw_dirt_road(surface: pygame.Surface, x1: int, y1: int, x2: int, y2: int,
                   width: int = 80, seed: int = 0) -> None:
    """Draw a dirt road segment between two points with rough edges."""
    rng = random.Random(seed + x1 * 7 + y1 * 13)
    dx = x2 - x1
    dy = y2 - y1
    length = max(1, int(math.hypot(dx, dy)))
    nx, ny = -dy / length, dx / length  # perpendicular normal

    hw = width // 2
    # Build edge points with jitter
    left_pts = []
    right_pts = []
    steps = max(4, length // 40)
    for i in range(steps + 1):
        t = i / steps
        mx = x1 + dx * t
        my = y1 + dy * t
        jl = rng.randint(-6, 6)
        jr = rng.randint(-6, 6)
        left_pts.append((int(mx + nx * (hw + jl)), int(my + ny * (hw + jl))))
        right_pts.append((int(mx - nx * (hw + jr)), int(my - ny * (hw + jr))))

    pts = left_pts + list(reversed(right_pts))
    # Base dirt
    pygame.draw.polygon(surface, (92, 78, 58), pts)
    pygame.draw.polygon(surface, (72, 62, 45), pts, 1)
    # Ruts and texture
    for _ in range(length // 20):
        rx = rng.randint(min(x1, x2) - hw, max(x1, x2) + hw)
        ry = rng.randint(min(y1, y2) - hw, max(y1, y2) + hw)
        rw = rng.randint(8, 20)
        rh = rng.randint(4, 10)
        shade = 82 + rng.randint(-12, 8)
        pygame.draw.ellipse(surface, (shade, shade - 10, shade - 22), (rx, ry, rw, rh))


# ─────────────────────────────────────────────────────────────────────────────
# FARM-PEN PAINTING HELPERS — shared by the chicken coop and pig pen below.
# All pen art is baked once at town build (render-to-texture at 2×), so
# per-pixel detail here is cheap. Light convention: sun from the UPPER-LEFT,
# every cast shadow falls to the lower-right.
# ─────────────────────────────────────────────────────────────────────────────


def _pen_soft_shadow(surface: pygame.Surface, cx: int, cy: int, w: int, h: int,
                     alpha: int = 70, dx: int = 3) -> None:
    """Layered soft elliptical contact shadow, nudged to the lower-right."""
    sw, sh = w + 12, h + 8
    s = pygame.Surface((sw, sh), pygame.SRCALPHA)
    pygame.draw.ellipse(s, (16, 11, 8, int(alpha * 0.40)), (0, 1, sw, sh - 2))
    pygame.draw.ellipse(s, (16, 11, 8, int(alpha * 0.72)), (3, 2, sw - 6, sh - 4))
    pygame.draw.ellipse(s, (16, 11, 8, alpha), (6, 3, sw - 12, sh - 6))
    surface.blit(s, (cx - sw // 2 + dx, cy - sh // 2 + 1))


def _pen_plank_wall(surface: pygame.Surface, rect, rng,
                    base=(124, 100, 68), weather: float = 0.5) -> None:
    """Vertical board wall: per-plank tone (warm wood drifting to silvered
    grey by `weather`), lit left edges, dark board gaps, grain, knots, nails."""
    x0, y0, w, h = rect
    px = x0
    while px < x0 + w:
        bw = min(rng.randint(5, 8), x0 + w - px)
        t = rng.uniform(0, weather)
        pr = int(base[0] + (126 - base[0]) * t) + rng.randint(-9, 9)
        pg = int(base[1] + (120 - base[1]) * t) + rng.randint(-7, 7)
        pb = int(base[2] + (104 - base[2]) * t) + rng.randint(-6, 6)
        for row in range(h):
            v = 1.0 - 0.22 * (row / max(1, h - 1))      # grounded boards darker
            pygame.draw.line(surface, (max(0, int(pr * v)), max(0, int(pg * v)), max(0, int(pb * v))),
                             (px, y0 + row), (px + bw - 2, y0 + row))
        # sun catches each board's left arris
        pygame.draw.line(surface, (min(255, pr + 24), min(255, pg + 20), min(255, pb + 16)),
                         (px, y0), (px, y0 + h - 1), 1)
        # board gap
        pygame.draw.line(surface, (42, 30, 18), (px + bw - 1, y0), (px + bw - 1, y0 + h - 1), 1)
        # grain streaks
        for _ in range(2):
            gx = px + rng.randint(1, max(1, bw - 3))
            gy0 = y0 + rng.randint(2, max(3, h // 2))
            gy1 = min(y0 + h - 2, gy0 + rng.randint(6, max(7, h - 4)))
            pygame.draw.line(surface, (int(pr * 0.76), int(pg * 0.74), int(pb * 0.72)),
                             (gx, gy0), (gx, gy1), 1)
        # the odd knot
        if bw >= 6 and rng.random() < 0.30:
            kx = px + bw // 2
            ky = y0 + rng.randint(6, max(7, h - 8))
            pygame.draw.circle(surface, (int(pr * 0.52), int(pg * 0.5), int(pb * 0.48)), (kx, ky), 2)
            pygame.draw.circle(surface, (int(pr * 0.8), int(pg * 0.78), int(pb * 0.74)), (kx, ky), 3, 1)
        # nails at top and bottom battens
        for ny in (y0 + 3, y0 + h - 4):
            pygame.draw.circle(surface, (58, 50, 40), (px + bw // 2, ny), 1)
        px += bw


def _pen_shake_roof(surface: pygame.Surface, rx0: int, rx1: int, ry: int,
                    ex0: int, ex1: int, ey: int, rng,
                    base=(130, 106, 72), moss: bool = True) -> None:
    """Front slope of a gable roof — ridge spans (rx0..rx1, y=ry), eave spans
    (ex0..ex1, y=ey) — painted as weathered wood shakes: lit at the ridge,
    darkening to the eave, staggered butt rows, tone-varied tiles, moss and
    lichen, a capped ridge and bargeboards."""
    H = max(1, ey - ry)
    # base fill, shaded ridge → eave
    for yy in range(ry, ey + 1):
        u = (yy - ry) / H
        xl = int(rx0 + (ex0 - rx0) * u)
        xr = int(rx1 + (ex1 - rx1) * u)
        v = 1.10 - 0.36 * u
        pygame.draw.line(surface, (min(255, int(base[0] * v)), min(255, int(base[1] * v)),
                                   min(255, int(base[2] * v))), (xl, yy), (xr, yy))
    # shingle butt rows + staggered joints
    ri = 0
    for yy in range(ry + 3, ey + 1, 4):
        u = (yy - ry) / H
        xl = int(rx0 + (ex0 - rx0) * u)
        xr = int(rx1 + (ex1 - rx1) * u)
        pygame.draw.line(surface, (72, 56, 36), (xl, yy), (xr, yy), 1)
        pygame.draw.line(surface, (158, 134, 96), (xl, yy - 1), (xr, yy - 1), 1)  # sun on the butt edge
        jx = xl + (3 if ri % 2 else 6)
        while jx < xr - 1:
            pygame.draw.line(surface, (84, 66, 44), (jx, yy - 3), (jx, yy - 1), 1)
            jx += rng.randint(5, 7)
        ri += 1
    # tone-varied / slipped / bleached tiles
    n_tiles = max(8, (rx1 - rx0) * H // 110)
    for _ in range(n_tiles):
        u = rng.uniform(0.08, 0.96)
        yy = ry + ((int(ry + H * u) - ry) // 4) * 4
        u2 = (yy - ry) / H
        xl = int(rx0 + (ex0 - rx0) * u2)
        xr = int(rx1 + (ex1 - rx1) * u2)
        if xr - xl < 12:
            continue
        tw_ = rng.randint(4, 7)
        px_ = rng.randint(xl + 2, xr - tw_ - 2)
        ts = pygame.Surface((tw_, 3), pygame.SRCALPHA)
        roll = rng.random()
        if roll < 0.16:
            ts.fill((40, 30, 19, 130))          # slipped/missing shake
        elif roll < 0.55:
            ts.fill((196, 174, 132, 38))        # sun-bleached
        else:
            ts.fill((54, 40, 25, 48))           # weather-stained
        surface.blit(ts, (px_, yy))
    if moss:
        for _ in range(10):
            u = rng.uniform(0.5, 0.95)
            xl = rx0 + (ex0 - rx0) * u
            xr = rx1 + (ex1 - rx1) * u
            side = rng.random() < 0.5
            mx_ = int(xl + (xr - xl) * (rng.uniform(0.02, 0.28) if side else rng.uniform(0.7, 0.96)))
            ms = pygame.Surface((9, 5), pygame.SRCALPHA)
            pygame.draw.ellipse(ms, (88, 104, 56, rng.randint(70, 125)),
                                (0, 0, rng.randint(4, 9), rng.randint(2, 4)))
            surface.blit(ms, (mx_, int(ry + H * u)))
        for _ in range(14):
            u = rng.uniform(0.1, 0.9)
            xl = int(rx0 + (ex0 - rx0) * u)
            xr = int(rx1 + (ex1 - rx1) * u)
            if xr - xl < 8:
                continue
            ls = pygame.Surface((3, 2), pygame.SRCALPHA)
            ls.fill((158, 160, 128, rng.randint(46, 88)))
            surface.blit(ls, (rng.randint(xl + 2, xr - 4), int(ry + H * u)))
    # ridge cap
    pygame.draw.line(surface, (58, 43, 26), (rx0 - 1, ry + 2), (rx1 + 1, ry + 2), 2)
    pygame.draw.line(surface, (126, 102, 68), (rx0 - 1, ry), (rx1 + 1, ry), 3)
    pygame.draw.line(surface, (160, 134, 94), (rx0 - 1, ry - 1), (rx1 + 1, ry - 1), 1)
    # bargeboards + eave drip edge
    pygame.draw.line(surface, (66, 50, 31), (rx0, ry), (ex0, ey), 2)
    pygame.draw.line(surface, (66, 50, 31), (rx1, ry), (ex1, ey), 2)
    pygame.draw.line(surface, (50, 36, 22), (ex0, ey), (ex1, ey), 2)


def _pen_straw_pile(surface: pygame.Surface, cx: int, cy: int, w: int, h: int, rng) -> None:
    """Loose straw heap: shaded mound with criss-cross strands, lit upper-left."""
    import math as _m
    _pen_soft_shadow(surface, cx + 2, cy + h // 2, w + 4, max(6, h // 2 + 4), alpha=58)
    pygame.draw.ellipse(surface, (132, 106, 54), (cx - w // 2, cy - h // 2, w, h))
    pygame.draw.ellipse(surface, (168, 140, 72), (cx - w // 2 + 1, cy - h // 2, w - 3, h - 2))
    pygame.draw.ellipse(surface, (200, 172, 96), (cx - w // 2 + 3, cy - h // 2 + 1, w - 9, h - 5))
    for _ in range(w + 12):
        a = rng.uniform(0, _m.tau)
        r0 = rng.uniform(0, 0.46)
        sx = cx + (w * 0.5) * r0 * _m.cos(a)
        sy = cy + (h * 0.5) * r0 * _m.sin(a) - 1
        ln = rng.uniform(3, 7)
        la = rng.uniform(0, _m.pi)
        col = rng.choice([(216, 188, 110), (182, 152, 80), (150, 122, 60), (228, 202, 126)])
        pygame.draw.line(surface, col, (int(sx), int(sy)),
                         (int(sx + ln * _m.cos(la)), int(sy + ln * _m.sin(la) * 0.5)), 1)
    for _ in range(8):  # strands fallen around the heap
        a = rng.uniform(0, _m.tau)
        sx = cx + (w * 0.62) * _m.cos(a)
        sy = cy + (h * 0.62) * _m.sin(a) + 1
        la = rng.uniform(0, _m.pi)
        pygame.draw.line(surface, (190, 162, 88), (int(sx), int(sy)),
                         (int(sx + 5 * _m.cos(la)), int(sy + 2.5 * _m.sin(la))), 1)


def draw_chicken_coop(surface: pygame.Surface, x: int, y: int, seed: int = 0) -> pygame.Rect:
    """Hand-painted chicken run (~224x152 logical px, sun upper-left): a
    scratched bare-earth yard with a grass fringe and dust-bath hollows, a
    raised board henhouse on stone-footed stilts (shake roof, wire window,
    open nesting boxes, cleated ramp), feed and water spots and farmyard
    clutter — ringed by the post-and-rail yard fence, which the building
    occludes at the back of the ring."""
    import math as _m
    rng = random.Random(seed + 7001)

    yard_w, yard_h = 224, 152
    rx_y, ry_y = yard_w // 2, yard_h // 2

    # Building geometry, upper-left of the yard. The runtime animal no-go
    # ellipse in build_farm_animals matches this placement — keep in sync.
    coop_w, coop_h = 84, 50
    coop_x = x - yard_w // 2 + 20
    wall_top = y - yard_h // 2 + 16
    wall_bot = wall_top + coop_h
    stilt_h = 14
    feet_y = wall_bot + stilt_h
    nb_x, nb_y, nb_w, nb_h = coop_x + coop_w - 1, wall_top + 16, 20, 30
    eave_l, eave_r = coop_x - 10, coop_x + coop_w + nb_w + 6
    eave_y = wall_top + 8
    ridge_l, ridge_r = eave_l + 12, eave_r - 12
    ridge_y = wall_top - 24

    def _in_yard(px, py, margin=10):
        nxx = (px - x) / max(1.0, rx_y - margin)
        nyy = (py - y) / max(1.0, ry_y - margin)
        return nxx * nxx + nyy * nyy <= 1.0

    # ── GROUND: layered scratched earth on its own surface, soft-masked ─────
    dsz = (yard_w + 28, yard_h + 28)
    gc_ = (dsz[0] // 2, dsz[1] // 2)
    ground = pygame.Surface(dsz, pygame.SRCALPHA)
    grng = random.Random(seed + 5151)
    ground.fill((118, 99, 72, 255))
    # broad tonal patches — sun-dried tan ↔ cooler packed earth
    for col, n, lo, hi in (((132, 112, 82), 9, 36, 70), ((108, 90, 64), 10, 40, 80),
                           ((96, 79, 56), 9, 36, 72), ((140, 122, 92), 5, 26, 50),
                           ((86, 70, 50), 6, 30, 60)):
        for _ in range(n):
            bw = grng.randint(26, 78)
            bh = grng.randint(14, 40)
            bs = pygame.Surface((bw, bh), pygame.SRCALPHA)
            pygame.draw.ellipse(bs, (col[0], col[1], col[2], grng.randint(lo, hi)), (0, 0, bw, bh))
            ground.blit(bs, (grng.randint(-10, dsz[0] - bw + 10), grng.randint(-10, dsz[1] - bh + 10)))
    # compacted lighter zone where the flock mills about
    zs = pygame.Surface((132, 76), pygame.SRCALPHA)
    pygame.draw.ellipse(zs, (134, 115, 86, 30), (0, 0, 132, 76))
    pygame.draw.ellipse(zs, (138, 120, 90, 24), (16, 10, 100, 56))
    ground.blit(zs, (gc_[0] - 60, gc_[1] - 26))
    # fine grit
    for _ in range(1700):
        gx = grng.randint(0, dsz[0] - 1)
        gy = grng.randint(0, dsz[1] - 1)
        v = 112 + grng.randint(-30, 26)
        ground.set_at((gx, gy), (v, int(v * 0.84), int(v * 0.61), grng.randint(50, 130)))
    # peck pocks: dark pit + pale crumb kicked out beside it
    for _ in range(90):
        gx = grng.randint(8, dsz[0] - 9)
        gy = grng.randint(8, dsz[1] - 9)
        ground.set_at((gx, gy), (74, 60, 42, 200))
        ground.set_at((gx + 1, gy + 1), (146, 128, 98, 160))
    # three-toe scratch rakes
    for _ in range(26):
        sx = grng.randint(18, dsz[0] - 18)
        sy = grng.randint(16, dsz[1] - 16)
        ang = grng.uniform(0, _m.pi)
        ca, sa = _m.cos(ang), _m.sin(ang) * 0.55
        for k in (-2, 0, 2):
            ox, oy = -sa * k, ca * k * 0.6
            pygame.draw.line(ground, (88, 72, 50, 210),
                             (sx - 5 * ca + ox, sy - 5 * sa + oy),
                             (sx + 5 * ca + ox, sy + 5 * sa + oy), 1)
        pygame.draw.line(ground, (140, 122, 92, 120),
                         (sx - 5 * ca, sy - 5 * sa + 2), (sx + 5 * ca, sy + 5 * sa + 2), 1)
    # grass fringe surviving at the lightly-trodden rim
    for _ in range(150):
        a = grng.uniform(0, _m.tau)
        rr_ = grng.uniform(0.80, 1.0)
        gx = gc_[0] + (dsz[0] / 2 - 11) * rr_ * _m.cos(a)
        gy = gc_[1] + (dsz[1] / 2 - 11) * rr_ * _m.sin(a)
        if grng.random() < 0.14:
            gcol = (164, 150, 92)            # the odd dry blade
        else:
            gcol = (grng.randint(78, 104), grng.randint(96, 124), grng.randint(44, 62))
        for _b in range(grng.randint(2, 4)):
            bx2 = gx + grng.randint(-2, 2)
            pygame.draw.line(ground, gcol, (bx2, gy),
                             (bx2 + grng.randint(-2, 2), gy - grng.randint(3, 7)), 1)
    # soft ellipse mask so the yard melts into the surrounding ground
    mask = pygame.Surface(dsz, pygame.SRCALPHA)
    pygame.draw.ellipse(mask, (255, 255, 255, 255), (8, 8, dsz[0] - 16, dsz[1] - 16))
    pygame.draw.ellipse(mask, (255, 255, 255, 120), (2, 2, dsz[0] - 4, dsz[1] - 4), 6)
    ground.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    surface.blit(ground, (x - gc_[0], y - gc_[1]))

    # ── Ground features ──────────────────────────────────────────────────────
    # dust-bath hollows (shaded inner wall upper-left, pale kicked-out dust ring)
    for dbx, dby in ((x - 44, y + 14), (x + 22, y + 36)):
        dw, dh = rng.randint(24, 30), rng.randint(12, 15)
        ds = pygame.Surface((dw + 8, dh + 6), pygame.SRCALPHA)
        pygame.draw.ellipse(ds, (152, 134, 104, 70), (0, 1, dw + 8, dh + 4))
        pygame.draw.ellipse(ds, (96, 79, 57, 235), (4, 3, dw, dh))
        pygame.draw.ellipse(ds, (126, 107, 80, 220), (6, 5, dw - 4, dh - 3))
        pygame.draw.arc(ds, (64, 51, 37, 200), (4, 3, dw, dh), _m.pi * 0.45, _m.pi * 1.1, 2)
        for k in range(4):
            lx = 7 + k * (dw - 9) // 3
            pygame.draw.line(ds, (108, 90, 64, 180), (lx, 6), (lx + 3, dh + 1), 1)
        surface.blit(ds, (dbx - (dw + 8) // 2, dby - (dh + 6) // 2))
    # worn run from the ramp foot to the gate
    p0, p1 = (x + 3, y + 18), (x - 2, y + 70)
    for i in range(10):
        t = i / 9.0
        ppx = int(p0[0] + (p1[0] - p0[0]) * t + rng.uniform(-2.5, 2.5))
        ppy = int(p0[1] + (p1[1] - p0[1]) * t)
        ps = pygame.Surface((18, 9), pygame.SRCALPHA)
        pygame.draw.ellipse(ps, (100, 83, 60, 60), (0, 0, 18, 9))
        pygame.draw.ellipse(ps, (128, 110, 82, 50), (3, 2, 12, 5))
        surface.blit(ps, (ppx - 9, ppy - 4))
    # half-buried stones
    for _ in range(7):
        stx = x + rng.randint(-rx_y + 20, rx_y - 20)
        sty = y + rng.randint(-ry_y + 16, ry_y - 16)
        if not _in_yard(stx, sty, margin=16):
            continue
        sv = 116 + rng.randint(-14, 12)
        pygame.draw.ellipse(surface, (52, 42, 30), (stx - 3, sty, 8, 4))
        pygame.draw.ellipse(surface, (sv, sv - 5, sv - 14), (stx - 3, sty - 3, 7, 5))
        pygame.draw.ellipse(surface, (min(255, sv + 26), min(255, sv + 20), sv), (stx - 2, sty - 3, 3, 2))
    # droppings — small, matte
    for _ in range(9):
        dpx = x + rng.randint(-rx_y + 20, rx_y - 20)
        dpy = y + rng.randint(-ry_y + 14, ry_y - 14)
        if not _in_yard(dpx, dpy, margin=16):
            continue
        pygame.draw.circle(surface, (88, 80, 58), (dpx, dpy), 1)
        pygame.draw.circle(surface, (226, 224, 212), (dpx, dpy - 1), 1)
    # moulted feathers — downy curls in white / buff / rust
    for _ in range(12):
        fx = x + rng.randint(-rx_y + 18, rx_y - 18)
        fy = y + rng.randint(-ry_y + 14, ry_y - 14)
        if not _in_yard(fx, fy, margin=14):
            continue
        fcol = rng.choice([(240, 235, 226), (224, 200, 162), (188, 124, 72)])
        fdk = (fcol[0] - 56, fcol[1] - 56, fcol[2] - 52)
        pygame.draw.arc(surface, fcol, (fx - 3, fy - 2, 7, 5), 0.4, 2.8, 1)
        pygame.draw.arc(surface, fdk, (fx - 3, fy - 1, 7, 5), 0.6, 2.6, 1)
        pygame.draw.line(surface, fdk, (fx + 3, fy), (fx + 5, fy - 1), 1)

    # ── HENHOUSE ─────────────────────────────────────────────────────────────
    # cast shadow thrown to the lower-right of the whole building
    bw_ = eave_r - eave_l
    shs = pygame.Surface((bw_ + 56, 34), pygame.SRCALPHA)
    pygame.draw.polygon(shs, (16, 11, 8, 34), [(2, 0), (bw_ + 6, 0), (bw_ + 50, 30), (44, 30)])
    pygame.draw.polygon(shs, (16, 11, 8, 30), [(4, 0), (bw_ + 4, 0), (bw_ + 34, 18), (28, 18)])
    surface.blit(shs, (eave_l, feet_y - 1))

    # dark cavity under the raised floor
    cav = pygame.Surface((coop_w - 4, stilt_h + 2), pygame.SRCALPHA)
    for row in range(stilt_h + 2):
        a = max(46, int(205 - 130 * (row / float(stilt_h + 1))))
        pygame.draw.line(cav, (20, 15, 10, a), (0, row), (coop_w - 5, row))
    surface.blit(cav, (coop_x + 2, wall_bot))
    for bxp in (coop_x + 24, coop_x + 56):       # back stilts in the gloom
        pygame.draw.rect(surface, (40, 30, 19), (bxp, wall_bot + 3, 4, stilt_h - 5))
    for _ in range(8):                           # stray straw blown underneath
        ux = coop_x + rng.randint(8, coop_w - 12)
        uy = wall_bot + rng.randint(6, stilt_h - 1)
        pygame.draw.line(surface, (122, 102, 58), (ux, uy), (ux + rng.randint(-3, 3), uy + 2), 1)
    # front stilt posts on flat stone footings
    for px_p in (coop_x + 4, coop_x + coop_w - 10):
        pygame.draw.ellipse(surface, (52, 44, 36), (px_p - 3, feet_y - 2, 12, 6))
        pygame.draw.ellipse(surface, (124, 118, 108), (px_p - 3, feet_y - 4, 12, 6))
        pygame.draw.ellipse(surface, (150, 144, 134), (px_p - 2, feet_y - 5, 8, 4))
        for ci in range(6):
            v = 98 - ci * 9 + rng.randint(-4, 4)
            pygame.draw.line(surface, (v, int(v * 0.74), int(v * 0.5)),
                             (px_p + ci, wall_bot - 1), (px_p + ci, feet_y - 3), 1)
        pygame.draw.line(surface, (44, 32, 18), (px_p + 5, wall_bot), (px_p + 5, feet_y - 3), 1)
    # X cross-brace between the front stilts
    bl, br = coop_x + 9, coop_x + coop_w - 10
    for p, q in (((bl, wall_bot + 2), (br, feet_y - 4)), ((bl, feet_y - 4), (br, wall_bot + 2))):
        pygame.draw.line(surface, (38, 27, 16), (p[0], p[1] + 2), (q[0], q[1] + 2), 2)
        pygame.draw.line(surface, (90, 70, 44), p, q, 2)
    # floor rim / joist band
    pygame.draw.rect(surface, (66, 49, 30), (coop_x - 2, wall_bot - 2, coop_w + 4, 4))
    pygame.draw.line(surface, (102, 80, 52), (coop_x - 2, wall_bot - 2), (coop_x + coop_w + 1, wall_bot - 2), 1)
    for jx in range(coop_x + 2, coop_x + coop_w, 9):
        pygame.draw.rect(surface, (52, 38, 22), (jx, wall_bot - 1, 4, 3))

    # board wall + corner trims
    _pen_plank_wall(surface, (coop_x, wall_top, coop_w, coop_h), rng,
                    base=(124, 100, 68), weather=0.55)
    for tx0 in (coop_x - 1, coop_x + coop_w - 4):
        pygame.draw.rect(surface, (104, 84, 56), (tx0, wall_top, 5, coop_h))
        pygame.draw.line(surface, (134, 110, 76), (tx0, wall_top), (tx0, wall_top + coop_h - 1), 1)
        pygame.draw.line(surface, (52, 38, 23), (tx0 + 4, wall_top), (tx0 + 4, wall_top + coop_h - 1), 1)
    # eave AO — the roof overhang shades the top of the wall
    ao = pygame.Surface((coop_w, 10), pygame.SRCALPHA)
    for row in range(10):
        pygame.draw.line(ao, (20, 14, 9, int(92 * (1 - row / 9.0))), (0, row), (coop_w - 1, row))
    surface.blit(ao, (coop_x, eave_y + 2))
    # rain-stain streaks bleeding down from the eave line
    for _ in range(6):
        sx_ = coop_x + rng.randint(4, coop_w - 7)
        ln = rng.randint(8, 22)
        st = pygame.Surface((2, ln), pygame.SRCALPHA)
        for row in range(ln):
            st.set_at((0, row), (40, 30, 20, int(56 * (1 - row / float(ln)))))
            st.set_at((1, row), (40, 30, 20, int(34 * (1 - row / float(ln)))))
        surface.blit(st, (sx_, eave_y + 3))

    # wire-mesh window with a roost pole inside
    win_x, win_y, win_w, win_h = coop_x + 10, wall_top + 18, 20, 14
    pygame.draw.rect(surface, (30, 21, 12), (win_x - 2, win_y - 2, win_w + 4, win_h + 4))
    for row in range(win_h):
        v = 16 + int(14 * (row / float(win_h)))
        pygame.draw.line(surface, (v + 6, v, max(0, v - 4)), (win_x, win_y + row), (win_x + win_w - 1, win_y + row))
    pygame.draw.line(surface, (54, 38, 22), (win_x + 2, win_y + 9), (win_x + win_w - 3, win_y + 8), 1)
    for mxi in range(win_x + 2, win_x + win_w, 4):
        pygame.draw.line(surface, (88, 86, 74), (mxi, win_y), (mxi, win_y + win_h - 1), 1)
    for myi in range(win_y + 2, win_y + win_h, 4):
        pygame.draw.line(surface, (74, 72, 62), (win_x, myi), (win_x + win_w - 1, myi), 1)
    pygame.draw.rect(surface, (118, 95, 62), (win_x - 3, win_y - 3, win_w + 6, win_h + 6), 2, border_radius=1)
    pygame.draw.line(surface, (148, 122, 84), (win_x - 3, win_y - 3), (win_x + win_w + 2, win_y - 3), 1)
    pygame.draw.rect(surface, (134, 110, 74), (win_x - 4, win_y + win_h + 2, win_w + 8, 3))
    pygame.draw.line(surface, (52, 38, 22), (win_x - 4, win_y + win_h + 5), (win_x + win_w + 4, win_y + win_h + 5), 1)

    # pop-door (slid open on its rail) with warm straw-lit threshold
    door_w, door_h = 14, 20
    door_x = coop_x + 54
    door_y = wall_bot - door_h
    pygame.draw.rect(surface, (26, 18, 11), (door_x - 2, door_y - 2, door_w + 4, door_h + 2))
    for row in range(door_h):
        v = 10 + int(10 * row / float(door_h))
        pygame.draw.line(surface, (v + 4, v, max(0, v - 2)), (door_x, door_y + row), (door_x + door_w - 1, door_y + row))
    pygame.draw.line(surface, (96, 78, 44), (door_x, wall_bot - 2), (door_x + door_w - 1, wall_bot - 2), 1)
    pygame.draw.line(surface, (152, 130, 72), (door_x + 2, wall_bot - 1), (door_x + door_w - 3, wall_bot - 1), 1)
    pygame.draw.line(surface, (70, 62, 52), (door_x - 3, door_y - 4), (door_x + door_w + 14, door_y - 4), 2)  # guide rail
    pygame.draw.rect(surface, (104, 84, 56), (door_x + door_w + 3, door_y - 1, 10, door_h - 2))
    pygame.draw.line(surface, (136, 112, 78), (door_x + door_w + 3, door_y - 1), (door_x + door_w + 3, door_y + door_h - 4), 1)
    pygame.draw.rect(surface, (54, 40, 24), (door_x + door_w + 3, door_y - 1, 10, door_h - 2), 1)
    pygame.draw.rect(surface, (60, 44, 26), (door_x - 2, door_y - 2, door_w + 4, door_h + 2), 1)

    # cleated ramp from the pop-door down to the yard
    r0 = (door_x + door_w // 2 - 4, wall_bot - 1)
    r1 = (door_x + door_w // 2 + 26, feet_y + 9)
    dxr, dyr = r1[0] - r0[0], r1[1] - r0[1]
    L = max(1.0, _m.hypot(dxr, dyr))
    nx_, ny_ = -dyr / L, dxr / L
    _pen_soft_shadow(surface, r1[0] - 2, r1[1] + 2, 26, 8, alpha=50)
    top = [(r0[0] + nx_ * 4, r0[1] + ny_ * 4), (r0[0] - nx_ * 3, r0[1] - ny_ * 3),
           (r1[0] - nx_ * 3, r1[1] - ny_ * 3), (r1[0] + nx_ * 4, r1[1] + ny_ * 4)]
    pygame.draw.polygon(surface, (120, 97, 64), [(int(px), int(py)) for px, py in top])
    side = [top[1], top[2], (top[2][0], top[2][1] + 3), (top[1][0], top[1][1] + 3)]
    pygame.draw.polygon(surface, (64, 48, 29), [(int(px), int(py)) for px, py in side])
    pygame.draw.line(surface, (152, 128, 90),
                     (int(r0[0] + nx_), int(r0[1] + ny_)), (int(r1[0] + nx_), int(r1[1] + ny_)), 2)
    for t in range(1, 7):
        tt = t / 7.0
        cxr, cyr = r0[0] + dxr * tt, r0[1] + dyr * tt
        pygame.draw.line(surface, (74, 56, 34),
                         (int(cxr + nx_ * 4), int(cyr + ny_ * 4)), (int(cxr - nx_ * 3), int(cyr - ny_ * 3)), 2)
        pygame.draw.line(surface, (142, 118, 82),
                         (int(cxr + nx_ * 4), int(cyr + ny_ * 4 - 1)), (int(cxr - nx_ * 3), int(cyr - ny_ * 3 - 1)), 1)
    pygame.draw.polygon(surface, (52, 38, 22), [(int(px), int(py)) for px, py in top], 1)

    # open-fronted nesting boxes on the right gable wall
    pygame.draw.line(surface, (58, 42, 25), (nb_x + 3, nb_y + nb_h), (nb_x + 3, nb_y + nb_h + 6), 2)
    pygame.draw.line(surface, (58, 42, 25), (nb_x + nb_w - 2, nb_y + nb_h), (nb_x + nb_w - 4, nb_y + nb_h + 7), 2)
    pygame.draw.line(surface, (50, 36, 21), (nb_x + nb_w - 4, nb_y + nb_h + 6), (nb_x + 1, nb_y + nb_h + 1), 1)
    for row in range(nb_h):
        t = row / max(1, nb_h - 1)
        v = int(118 - 26 * t) + (3 if (row // 8) % 2 else -3)
        pygame.draw.line(surface, (v, int(v * 0.8), int(v * 0.55)), (nb_x, nb_y + row), (nb_x + nb_w - 1, nb_y + row))
    pygame.draw.rect(surface, (54, 39, 23), (nb_x, nb_y, nb_w, nb_h), 1)
    comp_h = nb_h // 3
    for ci in range(3):
        cy0 = nb_y + ci * comp_h
        if ci:
            pygame.draw.line(surface, (50, 36, 20), (nb_x + 1, cy0), (nb_x + nb_w - 2, cy0), 1)
        pygame.draw.rect(surface, (28, 20, 12), (nb_x + 3, cy0 + 2, nb_w - 6, comp_h - 4))
        pygame.draw.rect(surface, (150, 124, 64), (nb_x + 3, cy0 + comp_h - 5, nb_w - 6, 3))
        for si in range(4):
            swx = nb_x + 4 + si * 3
            pygame.draw.line(surface, (192, 164, 90), (swx, cy0 + comp_h - 4),
                             (swx + rng.randint(-2, 2), cy0 + comp_h - 7), 1)
        if ci == 1:  # an egg catching the light
            pygame.draw.ellipse(surface, (206, 194, 170), (nb_x + 8, cy0 + comp_h - 9, 6, 7))
            pygame.draw.ellipse(surface, (242, 235, 217), (nb_x + 8, cy0 + comp_h - 10, 5, 6))
    lid = [(nb_x - 2, nb_y - 1), (nb_x + nb_w + 3, nb_y - 1), (nb_x + nb_w + 3, nb_y - 5), (nb_x - 2, nb_y - 8)]
    pygame.draw.polygon(surface, (138, 113, 76), lid)
    pygame.draw.line(surface, (166, 140, 98), (nb_x - 2, nb_y - 8), (nb_x + nb_w + 3, nb_y - 5), 2)
    pygame.draw.polygon(surface, (56, 41, 24), lid, 1)
    pygame.draw.rect(surface, (70, 66, 58), (nb_x + 3, nb_y - 4, 6, 2))
    pygame.draw.rect(surface, (70, 66, 58), (nb_x + nb_w - 8, nb_y - 3, 6, 2))

    # shake roof over house and nesting wing
    _pen_shake_roof(surface, ridge_l, ridge_r, ridge_y, eave_l, eave_r, eave_y, rng,
                    base=(130, 106, 72))

    # ── Yard props ───────────────────────────────────────────────────────────
    _pen_straw_pile(surface, x - 70, y + 28, 30, 14, rng)

    # water trough — planked, iron-banded, with still water and a sky glint
    wt_x, wt_y = x + 56, y + 6
    tw_, th_ = 42, 13
    _pen_soft_shadow(surface, wt_x + 2, wt_y + th_ - 2, tw_ + 8, 10, alpha=60)
    for lx_ in (wt_x - tw_ // 2 + 4, wt_x + tw_ // 2 - 8):
        pygame.draw.rect(surface, (54, 40, 24), (lx_, wt_y + th_ - 3, 4, 7))
        pygame.draw.line(surface, (86, 66, 42), (lx_, wt_y + th_ - 3), (lx_, wt_y + th_ + 3), 1)
    for row in range(th_):
        t = row / float(th_ - 1)
        v = int(126 - 30 * t)
        pygame.draw.line(surface, (v, int(v * 0.8), int(v * 0.56)),
                         (wt_x - tw_ // 2, wt_y + row), (wt_x + tw_ // 2, wt_y + row))
    for tvx in range(wt_x - tw_ // 2 + 6, wt_x + tw_ // 2 - 3, 9):
        pygame.draw.line(surface, (66, 50, 30), (tvx, wt_y + 4), (tvx, wt_y + th_ - 2), 1)
    for bx_ in (wt_x - tw_ // 2 + 2, wt_x + tw_ // 2 - 5):
        pygame.draw.rect(surface, (78, 74, 66), (bx_, wt_y, 3, th_))
        pygame.draw.line(surface, (108, 74, 50), (bx_ + 1, wt_y + 4), (bx_ + 1, wt_y + th_ - 1), 1)
    pygame.draw.rect(surface, (142, 118, 80), (wt_x - tw_ // 2 - 1, wt_y - 2, tw_ + 2, 3))
    pygame.draw.line(surface, (166, 142, 100), (wt_x - tw_ // 2 - 1, wt_y - 2), (wt_x + tw_ // 2 + 1, wt_y - 2), 1)
    pygame.draw.rect(surface, (50, 36, 21), (wt_x - tw_ // 2 - 1, wt_y - 2, tw_ + 2, th_ + 3), 1)
    # still water: murky olive-teal, back-rim shadow, soft sky band, one glint
    pygame.draw.rect(surface, (62, 76, 72), (wt_x - tw_ // 2 + 2, wt_y + 1, tw_ - 4, 5))
    pygame.draw.line(surface, (38, 48, 46), (wt_x - tw_ // 2 + 2, wt_y + 1), (wt_x + tw_ // 2 - 3, wt_y + 1), 1)
    pygame.draw.line(surface, (104, 126, 122), (wt_x - tw_ // 2 + 4, wt_y + 4), (wt_x + tw_ // 2 - 6, wt_y + 4), 2)
    pygame.draw.line(surface, (150, 170, 168), (wt_x - 10, wt_y + 3), (wt_x + 3, wt_y + 3), 1)
    pygame.draw.circle(surface, (200, 214, 212), (wt_x + 7, wt_y + 3), 1)
    drs = pygame.Surface((10, 5), pygame.SRCALPHA)
    pygame.draw.ellipse(drs, (52, 42, 30, 110), (0, 0, 10, 5))
    surface.blit(drs, (wt_x - 16, wt_y + th_ + 2))

    # low feed tray heaped with grain + the spill the hens peck over
    ft_x, ft_y = x - 22, y + 44
    _pen_soft_shadow(surface, ft_x + 1, ft_y + 5, 30, 8, alpha=55)
    pygame.draw.rect(surface, (96, 76, 50), (ft_x - 15, ft_y - 4, 30, 9), border_radius=2)
    pygame.draw.rect(surface, (128, 105, 72), (ft_x - 15, ft_y - 5, 30, 3), border_radius=1)
    pygame.draw.rect(surface, (58, 44, 28), (ft_x - 13, ft_y - 2, 26, 6), border_radius=2)
    pygame.draw.rect(surface, (174, 150, 86), (ft_x - 12, ft_y - 1, 24, 4), border_radius=2)
    for _ in range(14):
        pygame.draw.circle(surface, rng.choice([(198, 174, 104), (160, 136, 70), (212, 190, 120)]),
                           (ft_x + rng.randint(-11, 11), ft_y + rng.randint(-1, 2)), 1)
    for _ in range(26):
        a = rng.uniform(0, _m.tau)
        rr_ = rng.uniform(4, 20) * rng.uniform(0.5, 1.0)
        pygame.draw.circle(surface, rng.choice([(192, 168, 98), (164, 142, 74)]),
                           (int(ft_x + rr_ * _m.cos(a) * 1.4), int(ft_y + 2 + rr_ * _m.sin(a) * 0.6)), 1)

    # woven egg basket
    bx_, by_ = x + 30, y + 2
    _pen_soft_shadow(surface, bx_ + 1, by_ + 5, 24, 9, alpha=55)
    pygame.draw.ellipse(surface, (94, 71, 44), (bx_ - 12, by_ - 6, 24, 13))
    pygame.draw.ellipse(surface, (126, 99, 64), (bx_ - 11, by_ - 6, 22, 11))
    pygame.draw.ellipse(surface, (66, 49, 30), (bx_ - 9, by_ - 4, 18, 8))
    for wi, wx in enumerate(range(bx_ - 11, bx_ + 11, 3)):
        wc = (142, 114, 76) if wi % 2 else (104, 80, 50)
        pygame.draw.line(surface, wc, (wx, by_ + 2), (wx + 2, by_ + 6), 1)
    pygame.draw.arc(surface, (110, 86, 56), (bx_ - 9, by_ - 14, 18, 16), 0.3, _m.pi - 0.3, 2)
    pygame.draw.arc(surface, (148, 120, 82), (bx_ - 9, by_ - 15, 18, 16), 0.6, _m.pi - 0.6, 1)
    for k in range(3):
        ex_, ey_ = bx_ - 5 + k * 5, by_ - 2 + (k % 2)
        pygame.draw.ellipse(surface, (188, 176, 152), (ex_ - 2, ey_ - 3, 5, 7))
        pygame.draw.ellipse(surface, (238, 230, 210), (ex_ - 2, ey_ - 4, 4, 6))

    # grain sack slumped by the fence
    sk_x, sk_y = x + 80, y + 26
    _pen_soft_shadow(surface, sk_x + 2, sk_y + 8, 26, 9, alpha=60)
    sk_body = [(sk_x - 12, sk_y + 10), (sk_x - 10, sk_y - 2), (sk_x - 5, sk_y - 8),
               (sk_x + 4, sk_y - 9), (sk_x + 11, sk_y - 3), (sk_x + 13, sk_y + 10)]
    pygame.draw.polygon(surface, (122, 101, 66), sk_body)
    pygame.draw.polygon(surface, (150, 126, 86), [(sk_x - 10, sk_y + 6), (sk_x - 9, sk_y - 2),
                                                  (sk_x - 4, sk_y - 7), (sk_x + 1, sk_y - 7),
                                                  (sk_x - 2, sk_y + 6)])
    pygame.draw.polygon(surface, (96, 78, 50), [(sk_x + 6, sk_y - 5), (sk_x + 11, sk_y - 2),
                                                (sk_x + 12, sk_y + 9), (sk_x + 5, sk_y + 9)])
    pygame.draw.polygon(surface, (84, 67, 42), sk_body, 1)
    # rolled-open mouth with grain showing
    pygame.draw.ellipse(surface, (90, 72, 46), (sk_x - 5, sk_y - 11, 11, 5))
    pygame.draw.ellipse(surface, (174, 150, 86), (sk_x - 3, sk_y - 10, 7, 3))
    # two faint, broken weave creases
    pygame.draw.line(surface, (104, 85, 54), (sk_x - 8, sk_y + 1), (sk_x - 1, sk_y + 2), 1)
    pygame.draw.line(surface, (104, 85, 54), (sk_x + 2, sk_y + 4), (sk_x + 9, sk_y + 4), 1)
    for _ in range(10):
        pygame.draw.circle(surface, rng.choice([(198, 174, 104), (166, 142, 76)]),
                           (sk_x + rng.randint(-6, 8), sk_y + 11 + rng.randint(0, 4)), 1)

    # Yard footprint rect (returned obstacle). The circling fence is drawn
    # last so the ring sits in front of everything.
    fr = pygame.Rect(x - yard_w // 2 - 4, y - yard_h // 2 - 4, yard_w + 8, yard_h + 8)

    # ── Circling yard fence; the henhouse occludes the back of the ring ──────
    _coop_occlude = pygame.Rect(eave_l - 4, ridge_y - 2, (eave_r - eave_l) + 8,
                                (feet_y + 4) - (ridge_y - 2))
    _draw_yard_fence(surface, x, y, yard_w // 2 + 4, yard_h // 2 + 2,
                     seed=seed * 19 + 7, post_r=5, n_posts=22, occlude_rect=_coop_occlude)

    # (Chickens are drawn at runtime via the farm animal system)
    return fr


def _draw_round_post(surface: pygame.Surface, cx: int, cy: int, r: int = 5, seed: int = 0) -> None:
    """A weathered round timber fence post seen from the game's high angle:
    cylindrical body lit from the upper-left, end-grain top, soft shadow cast
    to the lower-right. (cx, cy) is the post's ground contact point."""
    rng = random.Random(seed * 2654435761 & 0xFFFFFF)
    rr = max(3, r)
    body_h = rr * 2 + 4

    # cast shadow stretching to the lower-right (plain alpha blit — NEVER
    # BLEND_MULT a partially-transparent surface onto the scene)
    sh_w, sh_h = rr * 4 + 6, rr + 4
    sh = pygame.Surface((sh_w, sh_h), pygame.SRCALPHA)
    pygame.draw.ellipse(sh, (14, 10, 7, 42), (0, 0, sh_w, sh_h))
    pygame.draw.ellipse(sh, (14, 10, 7, 66), (1, 1, sh_w - rr - 2, sh_h - 2))
    surface.blit(sh, (cx - rr + 1, cy - sh_h // 2 + 1))

    # body: lit left → core shadow right, faint bounce on the far edge
    tone = rng.randint(-10, 10)
    for i in range(rr * 2 + 1):
        ct = i / max(1, rr * 2)
        v = int(128 + tone - 76 * ct)
        if i == rr * 2:
            v += 14
        pygame.draw.line(surface, (max(0, v), max(0, int(v * 0.80)), max(0, int(v * 0.56))),
                         (cx - rr + i, cy - body_h), (cx - rr + i, cy), 1)
    for _ in range(3):  # grain streaks / a weather crack
        gx = cx + rng.randint(-rr + 1, rr - 1)
        gv = rng.randint(58, 84)
        pygame.draw.line(surface, (gv, int(gv * 0.8), int(gv * 0.55)),
                         (gx, cy - body_h + rng.randint(1, 3)), (gx, cy - rng.randint(0, 2)), 1)
    pygame.draw.line(surface, (38, 28, 18), (cx - rr + 1, cy), (cx + rr - 1, cy), 1)  # ground contact

    # end-grain top, rim lit upper-left
    top_y = cy - body_h
    pygame.draw.circle(surface, (58, 44, 28), (cx, top_y), rr + 1)
    pygame.draw.circle(surface, (134, 110, 74), (cx, top_y), rr)
    pygame.draw.circle(surface, (162, 136, 94), (cx - 1, top_y - 1), max(1, rr - 2))
    pygame.draw.circle(surface, (104, 82, 52), (cx, top_y), max(1, rr - 1), 1)
    pygame.draw.circle(surface, (86, 66, 40), (cx, top_y), max(1, rr - 3), 1)
    pygame.draw.circle(surface, (70, 52, 32), (cx, top_y), 1)
    # drying split across the cut face
    pygame.draw.line(surface, (96, 76, 48), (cx - rr + 2, top_y + rng.randint(-2, 1)),
                     (cx + rr - 2, top_y + rng.randint(-1, 2)), 1)


def _draw_perimeter_rail(surface: pygame.Surface, p1, p2, gap: int = 0) -> None:
    """Two weathered split rails spanning post-to-post with a slight sag and a
    soft ground shadow, so the span reads as a real post-and-rail fence."""
    x1, y1 = p1
    x2, y2 = p2
    mx, my = (x1 + x2) // 2, (y1 + y2) // 2
    # rail-pair ground shadow, offset to the lower-right
    shp = pygame.Surface((surface.get_width(), surface.get_height()), pygame.SRCALPHA)
    pygame.draw.line(shp, (14, 10, 7, 38), (x1 + 2, y1 + 3), (x2 + 2, y2 + 3), 5)
    surface.blit(shp, (0, 0))
    # deterministic per-span tone so rails differ subtly around the ring
    tone = ((x1 * 73 + y1 * 131 + x2 * 7) % 17) - 8
    for lift, sag in ((11, 2), (5, 1)):
        a = (x1, y1 - lift)
        b = (mx, my - lift + sag)
        c = (x2, y2 - lift)
        for s0, s1 in ((a, b), (b, c)):
            pygame.draw.line(surface, (52, 38, 24), (s0[0], s0[1] + 2), (s1[0], s1[1] + 2), 4)
            pygame.draw.line(surface, (104 + tone, 84 + tone, 56 + tone // 2), s0, s1, 3)
            pygame.draw.line(surface, (140 + tone, 118 + tone, 82 + tone // 2),
                             (s0[0], s0[1] - 1), (s1[0], s1[1] - 1), 1)


def _draw_yard_fence(surface: pygame.Surface, cx: int, cy: int, rx: int, ry: int,
                     seed: int = 0, post_r: int = 5, n_posts: int = 22,
                     gate: bool = True, occlude_rect: Optional[pygame.Rect] = None) -> None:
    """Draw a post-and-rail fence circling an elliptical yard (cx,cy radii
    rx,ry). Posts evenly spaced (with a little organic jitter) around the
    ellipse, double rails between consecutive posts, a gate opening at the
    front (bottom, angle ≈ +90°). If `occlude_rect` is given (a tall
    building), fence segments passing behind it are skipped so the building
    occludes the back of the ring."""
    import math as _m

    def _hidden(px, py):
        # A point is "behind" the building if it sits above the building's
        # bottom edge and within (a slightly padded) x-span → building hides it.
        if occlude_rect is None:
            return False
        return (occlude_rect.left - 4 <= px <= occlude_rect.right + 4
                and py <= occlude_rect.bottom)

    frng = random.Random(seed * 977 + 11)
    posts = []
    for i in range(n_posts):
        ang = (i / n_posts) * _m.tau - _m.pi / 2.0   # start at top, go clockwise
        jr = frng.uniform(-2.0, 2.0)
        px = int(cx + _m.cos(ang) * (rx + jr))
        py = int(cy + _m.sin(ang) * (ry + jr * 0.6))
        posts.append((px, py, ang))
    # Gate: the post pair straddling the front-center (angle nearest +pi/2).
    gate_idx = min(range(n_posts),
                   key=lambda i: abs(((posts[i][2] + _m.pi / 2) % _m.tau) - _m.pi)) if gate else -1

    # Rails behind posts (skip the gate span and any segment behind the building)
    for i in range(n_posts):
        if i == gate_idx:
            continue
        a = posts[i]
        b = posts[(i + 1) % n_posts]
        mx, my = (a[0] + b[0]) // 2, (a[1] + b[1]) // 2
        if _hidden(a[0], a[1]) and _hidden(b[0], b[1]) and _hidden(mx, my):
            continue
        _draw_perimeter_rail(surface, (a[0], a[1]), (b[0], b[1]))
    # Posts on top (skip those hidden behind the building)
    for i, (px, py, _ang) in enumerate(posts):
        if _hidden(px, py):
            continue
        _draw_round_post(surface, px, py, r=post_r, seed=seed * 71 + i)
    # A barred gate leaf swung open on the right gate post, hanging outward
    if gate and 0 <= gate_idx < n_posts:
        g1 = posts[gate_idx]
        hx, hy = g1[0], g1[1]
        ex_, ey_ = hx + 17, hy + 5
        shp = pygame.Surface((surface.get_width(), surface.get_height()), pygame.SRCALPHA)
        pygame.draw.line(shp, (14, 10, 7, 40), (hx + 2, hy + 2), (ex_ + 3, ey_ + 3), 4)
        surface.blit(shp, (0, 0))
        for lift in (10, 4):                 # two gate bars
            pygame.draw.line(surface, (54, 40, 26), (hx, hy - lift + 2), (ex_, ey_ - lift + 2), 3)
            pygame.draw.line(surface, (116, 94, 64), (hx, hy - lift), (ex_, ey_ - lift), 2)
            pygame.draw.line(surface, (148, 126, 90), (hx, hy - lift - 1), (ex_, ey_ - lift - 1), 1)
        pygame.draw.line(surface, (96, 76, 50), (hx, hy - 4), (ex_, ey_ - 10), 2)   # diagonal brace
        pygame.draw.line(surface, (60, 45, 28), (ex_, ey_ - 12), (ex_, ey_ + 1), 3)  # heel stile
        pygame.draw.line(surface, (124, 102, 70), (ex_ - 1, ey_ - 12), (ex_ - 1, ey_), 1)
        pygame.draw.circle(surface, (62, 58, 52), (hx, hy - 10), 2)                 # hinges
        pygame.draw.circle(surface, (62, 58, 52), (hx, hy - 4), 2)


def draw_pig_pen(surface: pygame.Surface, x: int, y: int, seed: int = 0) -> pygame.Rect:
    """Hand-painted pig pen (~200x140 logical px, sun upper-left): layered
    churned mud with a wet trampled heart, a worn track loop (gate → trough →
    shelter → wallow), cloven hoof prints, rooting gouges and wet-sheen
    glints; an open-fronted shake-roofed shelter hut glowing with straw
    bedding; a hollowed-log slop trough, a deep banked wallow with sky
    reflections, and farm clutter — circled by a post-and-rail fence that the
    hut occludes. Baked once at town build, so per-pixel detail is cheap."""
    import math as _m
    rng = random.Random(seed + 8001)

    pw, ph = 200, 140
    cx, cy = x, y
    yard_r, yard_t = cx + pw // 2, cy - ph // 2

    # Fixed prop anchors (the worn track below connects them, so they are
    # deterministic rather than randomized).
    TROUGH = (cx + 52, cy + 34)
    WALLOW = (cx - 50, cy + 28)
    MOUTH = (cx, cy + 8)          # shelter's open front
    GATE = (cx, cy + ph // 2 - 4)

    def _in_yard(px, py, margin=10):
        nx = (px - cx) / (pw / 2 - margin)
        ny = (py - cy) / (ph / 2 - margin)
        return nx * nx + ny * ny <= 1.0

    # ── GROUND: layered mud on its own surface, masked to a soft ellipse ─────
    msz = (pw + 44, ph + 44)
    mc = (msz[0] // 2, msz[1] // 2)
    mud = pygame.Surface(msz, pygame.SRCALPHA)
    mrng = random.Random(seed + 4242)
    mud.fill((104, 86, 60, 255))
    # broad tonal blotches — sun-dried tan ↔ damp umber
    for col, n in (((122, 103, 74), 10), ((110, 92, 66), 10), ((90, 72, 50), 10),
                   ((78, 62, 42), 9), ((130, 112, 84), 6), ((66, 52, 35), 7)):
        for _ in range(n):
            bw = mrng.randint(24, 70)
            bh = mrng.randint(12, 38)
            bs = pygame.Surface((bw, bh), pygame.SRCALPHA)
            pygame.draw.ellipse(bs, (col[0], col[1], col[2], mrng.randint(36, 88)), (0, 0, bw, bh))
            mud.blit(bs, (mrng.randint(-8, msz[0] - bw + 8), mrng.randint(-8, msz[1] - bh + 8)))
    # wet churned heart of the pen (south-centre, where the pigs mill)
    for ww_, wh_, a_ in ((150, 80, 36), (110, 60, 40), (70, 40, 44)):
        wsf = pygame.Surface((ww_, wh_), pygame.SRCALPHA)
        pygame.draw.ellipse(wsf, (58, 45, 30, a_), (0, 0, ww_, wh_))
        mud.blit(wsf, (mc[0] - ww_ // 2 - 4, mc[1] + 14 - wh_ // 2))
    # fine grit
    for _ in range(1700):
        gx = mrng.randint(0, msz[0] - 1)
        gy = mrng.randint(0, msz[1] - 1)
        v = 100 + mrng.randint(-30, 26)
        mud.set_at((gx, gy), (v, int(v * 0.81), int(v * 0.57), mrng.randint(45, 135)))

    # Worn track loop: pigs pace gate → trough → shelter mouth → wallow.
    # Stamped as overlapping soft dark ellipses → a churned, darker path.
    def _loc(p):  # world → mud-surface local
        return (p[0] - cx + mc[0], p[1] - cy + mc[1])
    way = [_loc(GATE), _loc(TROUGH), (mc[0] + 22, mc[1] + 12), _loc(MOUTH),
           (mc[0] - 26, mc[1] + 10), _loc(WALLOW), (mc[0] - 22, mc[1] + 44), _loc(GATE)]
    for i in range(len(way) - 1):
        ax, ay = way[i]
        bx, by = way[i + 1]
        steps = max(2, int(_m.hypot(bx - ax, by - ay) / 5))
        for s in range(steps + 1):
            t = s / steps
            px = ax + (bx - ax) * t + mrng.uniform(-3.0, 3.0)
            py = ay + (by - ay) * t + mrng.uniform(-2.0, 2.0)
            tw_ = mrng.randint(11, 17)
            th_ = mrng.randint(5, 8)
            ts = pygame.Surface((tw_, th_), pygame.SRCALPHA)
            pygame.draw.ellipse(ts, (56, 43, 28, mrng.randint(26, 55)), (0, 0, tw_, th_))
            mud.blit(ts, (int(px) - tw_ // 2, int(py) - th_ // 2))

    # Rooting gouges — short curved scrapes with a light displaced-soil ridge
    for _ in range(18):
        rx0 = mrng.randint(26, msz[0] - 26)
        ry0 = mrng.randint(24, msz[1] - 24)
        ang = mrng.uniform(0, _m.tau)
        ln = mrng.randint(6, 14)
        ex = rx0 + int(_m.cos(ang) * ln)
        ey = ry0 + int(_m.sin(ang) * ln * 0.5)
        pygame.draw.line(mud, (52, 40, 26, 210), (rx0, ry0), (ex, ey), 2)
        pygame.draw.line(mud, (122, 104, 76, 120), (rx0, ry0 - 2), (ex, ey - 2), 1)

    # Wet sheen — tiny cool glints where the churned mud is damp
    for _ in range(64):
        sx = mc[0] + mrng.randint(-72, 64)
        sy = mc[1] + mrng.randint(-8, 48)
        ln = mrng.randint(1, 3)
        pygame.draw.line(mud, (152, 148, 136, mrng.randint(48, 95)), (sx, sy), (sx + ln, sy), 1)
        if mrng.random() < 0.2:
            mud.set_at((sx, sy - 1), (192, 190, 180, 110))

    # surviving grass tufts along the least-trodden top rim
    for _ in range(16):
        a = mrng.uniform(-_m.pi * 0.92, -_m.pi * 0.08)
        rr_ = mrng.uniform(0.82, 0.97)
        gx = mc[0] + (msz[0] / 2 - 12) * rr_ * _m.cos(a)
        gy = mc[1] + (msz[1] / 2 - 12) * rr_ * _m.sin(a)
        for _b in range(mrng.randint(2, 4)):
            bx2 = gx + mrng.randint(-2, 2)
            if mrng.random() < 0.2:
                gcol2 = (158, 144, 90)       # the odd dry blade
            else:
                gcol2 = (mrng.randint(84, 102), mrng.randint(96, 114), mrng.randint(46, 60))
            pygame.draw.line(mud, gcol2,
                             (bx2, gy), (bx2 + mrng.randint(-2, 2), gy - mrng.randint(3, 6)), 1)

    # mask to a soft-edged ellipse so the yard blends into surrounding ground
    mask = pygame.Surface(msz, pygame.SRCALPHA)
    pygame.draw.ellipse(mask, (255, 255, 255, 255), (8, 8, msz[0] - 16, msz[1] - 16))
    pygame.draw.ellipse(mask, (255, 255, 255, 120), (2, 2, msz[0] - 4, msz[1] - 4), 6)
    mud.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    surface.blit(mud, (cx - mc[0], cy - mc[1]))

    # Hoof prints — paired cloven dints with a pale pressed rim, aligned to
    # the direction of travel along the worn track
    def _hoof(hx_, hy_, ang):
        ca, sa = _m.cos(ang), _m.sin(ang)
        for off in (-2.2, 2.2):
            tx = hx_ - sa * off
            ty = hy_ + ca * off * 0.6
            pygame.draw.ellipse(surface, (52, 39, 25), (int(tx) - 1, int(ty) - 2, 3, 5))
        pygame.draw.arc(surface, (128, 108, 78), (int(hx_) - 4, int(hy_) - 4, 9, 9),
                        _m.pi * 1.45, _m.tau, 1)
    track_pts = [GATE, TROUGH, MOUTH, WALLOW]
    for i in range(len(track_pts) - 1):
        ax, ay = track_pts[i]
        bx, by = track_pts[i + 1]
        seg_a = _m.atan2(by - ay, bx - ax)
        for s in range(4):
            t = (s + 0.5) / 4
            _hoof(ax + (bx - ax) * t + rng.randint(-4, 4),
                  ay + (by - ay) * t + rng.randint(-3, 3), seg_a + rng.uniform(-0.4, 0.4))
    for _ in range(10):
        hfx = cx + rng.randint(-pw // 2 + 18, pw // 2 - 18)
        hfy = cy + rng.randint(-ph // 2 + 14, ph // 2 - 14)
        if _in_yard(hfx, hfy, margin=16):
            _hoof(hfx, hfy, rng.uniform(0, _m.tau))

    # Scattered straw wisps (blown from the shelter bedding)
    for _ in range(14):
        swx = cx + rng.randint(-40, 44)
        swy = cy + rng.randint(-4, 34)
        if not _in_yard(swx, swy, margin=14):
            continue
        a2 = rng.uniform(0, _m.pi)
        pygame.draw.line(surface, rng.choice([(168, 144, 78), (188, 162, 92), (148, 126, 66)]),
                         (swx, swy), (swx + int(5 * _m.cos(a2)), swy + int(2.5 * _m.sin(a2))), 1)

    # Half-buried stones + droppings
    for _ in range(8):
        stx = cx + rng.randint(-pw // 2 + 20, pw // 2 - 20)
        sty = cy + rng.randint(-ph // 2 + 16, ph // 2 - 16)
        if not _in_yard(stx, sty, margin=16):
            continue
        sv = 100 + rng.randint(-12, 12)
        pygame.draw.ellipse(surface, (42, 33, 23), (stx - 2, sty, 6, 3))
        pygame.draw.ellipse(surface, (sv, sv - 4, sv - 12), (stx - 2, sty - 2, 5, 4))
        pygame.draw.ellipse(surface, (min(255, sv + 26), min(255, sv + 20), sv), (stx - 1, sty - 2, 2, 1))
    for _ in range(5):
        dpx = cx + rng.randint(-pw // 2 + 24, pw // 2 - 24)
        dpy = cy + rng.randint(0, ph // 2 - 18)
        if not _in_yard(dpx, dpy, margin=18):
            continue
        for k in range(3):
            pygame.draw.circle(surface, (58, 44, 26), (dpx + k * 2 - 2, dpy + (k % 2)), 2)
        pygame.draw.circle(surface, (80, 64, 42), (dpx, dpy - 1), 1)
        surface.set_at((dpx + 3, dpy - 3), (30, 26, 22))   # a fly

    # Returned footprint/obstacle rect (full yard, fence included).
    fence_r = pygame.Rect(cx - pw // 2 - 10, cy - ph // 2 - 8, pw + 20, ph + 16)

    # ── WALLOW: deep banked mud bath with murky water and sky reflections ───
    wx_, wy_ = WALLOW
    ww, wh = 74, 40
    ws = pygame.Surface((ww + 26, wh + 20), pygame.SRCALPHA)
    oc = ((ww + 26) // 2, (wh + 20) // 2)
    pygame.draw.ellipse(ws, (46, 36, 24, 60), (0, 2, ww + 26, wh + 16))        # soaking halo
    pygame.draw.ellipse(ws, (74, 58, 39, 255), (8, 6, ww + 10, wh + 8))        # churned bank
    pygame.draw.ellipse(ws, (102, 83, 58, 220), (10, 5, ww + 6, wh + 4))       # bank top in light
    pygame.draw.ellipse(ws, (40, 31, 20, 255), (13, 9, ww, wh))                # shadowed lip
    pygame.draw.ellipse(ws, (52, 53, 44, 255), (16, 12, ww - 8, wh - 7))       # murky water
    pygame.draw.ellipse(ws, (58, 60, 50, 255), (24, 14, ww - 18, wh - 10))
    pygame.draw.ellipse(ws, (66, 70, 60, 255), (oc[0] - 12, 15, ww // 2, wh // 2))  # shallows
    pygame.draw.ellipse(ws, (78, 62, 42, 255), (oc[0] + 8, oc[1] + 4, 12, 6))  # mud islands
    pygame.draw.ellipse(ws, (98, 80, 56, 255), (oc[0] + 9, oc[1] + 3, 10, 4))
    pygame.draw.ellipse(ws, (70, 56, 38, 255), (oc[0] - 22, oc[1] + 7, 9, 5))
    pygame.draw.ellipse(ws, (134, 150, 152, 150), (oc[0] - 18, 14, 22, 7))     # sky reflection
    pygame.draw.ellipse(ws, (178, 192, 192, 115), (oc[0] - 13, 15, 13, 4))
    pygame.draw.arc(ws, (104, 110, 100, 130), (oc[0] - 6, oc[1] - 4, 22, 12), 0.5, 2.6, 1)
    pygame.draw.arc(ws, (90, 96, 88, 100), (oc[0] - 10, oc[1] - 6, 30, 16), 3.5, 5.6, 1)
    surface.blit(ws, (wx_ - (ww + 26) // 2, wy_ - (wh + 20) // 2))
    for _ in range(14):                                                        # flung mud splatter
        a = rng.uniform(0, _m.tau)
        rr_ = rng.uniform(0.62, 1.05)
        sx = wx_ + (ww // 2 + 8) * rr_ * _m.cos(a)
        sy = wy_ + (wh // 2 + 6) * rr_ * _m.sin(a)
        pygame.draw.circle(surface, (62, 48, 32), (int(sx), int(sy)), rng.randint(1, 2))

    # second, smaller rain puddle right-of-centre
    p2 = pygame.Surface((40, 20), pygame.SRCALPHA)
    pygame.draw.ellipse(p2, (52, 42, 28, 90), (0, 0, 40, 20))
    pygame.draw.ellipse(p2, (48, 50, 42, 235), (5, 4, 30, 12))
    pygame.draw.ellipse(p2, (58, 62, 54, 255), (8, 6, 24, 8))
    pygame.draw.ellipse(p2, (140, 154, 156, 120), (12, 6, 12, 4))
    surface.blit(p2, (cx + 24 - 20, cy - 8 - 10))

    # ── SHELTER HUT: open-fronted, shake-roofed, straw glowing inside ───────
    sh_w = 66
    sh_l = cx - sh_w // 2          # centered in the upper yard (animal no-go
    ridge_y2 = cy - 46             # zone in build_farm_animals matches this)
    eave_y2 = cy - 14
    eave_l2, eave_r2 = cx - 40, cx + 40
    ridge_l2, ridge_r2 = cx - 30, cx + 30
    mouth_y = cy + 4

    # cast shadow to the lower-right + contact gloom at the mouth
    shs = pygame.Surface((sh_w + 60, 30), pygame.SRCALPHA)
    pygame.draw.polygon(shs, (16, 11, 8, 36), [(0, 0), (sh_w + 14, 0), (sh_w + 56, 26), (40, 26)])
    pygame.draw.polygon(shs, (16, 11, 8, 32), [(2, 0), (sh_w + 12, 0), (sh_w + 36, 15), (30, 15)])
    surface.blit(shs, (eave_l2 + 4, mouth_y - 1))

    # interior cavity: deep warm gloom under the roof
    cav_h = mouth_y - eave_y2
    cav = pygame.Surface((sh_w, cav_h + 4), pygame.SRCALPHA)
    for row in range(cav_h + 4):
        t = row / float(cav_h + 3)
        v = 14 + int(18 * t)
        pygame.draw.line(cav, (v + 6, v + 1, max(0, v - 4), 255), (0, row), (sh_w - 1, row))
    surface.blit(cav, (sh_l, eave_y2))
    # side-wall returns angling back at both ends
    for sgn, x0 in ((1, sh_l), (-1, sh_l + sh_w)):
        pts = [(x0, eave_y2 - 1), (x0 + sgn * 6, eave_y2 + 2), (x0 + sgn * 6, mouth_y + 2), (x0, mouth_y + 4)]
        pygame.draw.polygon(surface, (70, 53, 33) if sgn > 0 else (52, 39, 24), pts)
        pygame.draw.polygon(surface, (40, 29, 17), pts, 1)
    # straw bedding at the mouth — irregular, dark at the back, lit at the lip
    bed = pygame.Surface((sh_w - 6, 11), pygame.SRCALPHA)
    pygame.draw.ellipse(bed, (104, 82, 40, 220), (0, 0, sh_w - 6, 11))
    pygame.draw.ellipse(bed, (150, 124, 62, 225), (4, 2, sh_w - 14, 9))
    pygame.draw.ellipse(bed, (190, 162, 88, 230), (10, 4, sh_w - 26, 6))
    pygame.draw.ellipse(bed, (30, 22, 14, 120), (2, 0, sh_w - 10, 4))  # interior shadow on the bedding
    surface.blit(bed, (sh_l + 3, mouth_y - 5))
    for _ in range(20):
        swx = sh_l + 6 + rng.randint(0, sh_w - 12)
        swy = mouth_y + rng.randint(-2, 4)
        pygame.draw.line(surface, rng.choice([(208, 180, 104), (174, 146, 76), (146, 120, 60)]),
                         (swx, swy), (swx + rng.randint(-4, 4), swy + rng.randint(2, 6)), 1)
    for _ in range(12):  # single straws picked out by the sun at the lip
        swx = sh_l + 8 + rng.randint(0, sh_w - 16)
        pygame.draw.line(surface, (216, 190, 112), (swx, mouth_y + 1),
                         (swx + rng.randint(-3, 3), mouth_y + rng.randint(3, 5)), 1)
    # corner posts carrying the eaves
    for px0 in (sh_l + 1, sh_l + sh_w - 5):
        fs = pygame.Surface((10, 4), pygame.SRCALPHA)
        pygame.draw.ellipse(fs, (16, 11, 8, 70), (0, 0, 10, 4))
        surface.blit(fs, (px0 - 2, mouth_y + 3))
        for ci in range(5):
            v = 104 - ci * 12
            pygame.draw.line(surface, (v, int(v * 0.76), int(v * 0.52)),
                             (px0 + ci, eave_y2), (px0 + ci, mouth_y + 4), 1)
        pygame.draw.line(surface, (40, 29, 17), (px0 + 4, eave_y2), (px0 + 4, mouth_y + 4), 1)
    # lintel beam across the mouth under the eave
    pygame.draw.line(surface, (88, 68, 42), (sh_l - 2, eave_y2 + 1), (sh_l + sh_w + 2, eave_y2 + 1), 3)
    pygame.draw.line(surface, (122, 98, 64), (sh_l - 2, eave_y2 - 1), (sh_l + sh_w + 2, eave_y2 - 1), 1)
    # shake roof (same construction as the henhouse → consistent farm look)
    _pen_shake_roof(surface, ridge_l2, ridge_r2, ridge_y2, eave_l2, eave_r2, eave_y2, rng,
                    base=(120, 97, 66))

    # ── Hollowed-log slop trough (lower-right, per the farm layout) ─────────
    tx_, ty_ = TROUGH
    tl_, th_ = 50, 13
    _pen_soft_shadow(surface, tx_ + 2, ty_ + th_ // 2 + 4, tl_ + 10, 10, alpha=65)
    for fx_ in (tx_ - tl_ // 2 + 7, tx_ + tl_ // 2 - 11):     # cradle feet
        pygame.draw.line(surface, (58, 43, 26), (fx_ - 3, ty_ + th_ + 3), (fx_ + 2, ty_ + th_ - 2), 3)
        pygame.draw.line(surface, (70, 53, 33), (fx_ + 4, ty_ + th_ + 3), (fx_ - 1, ty_ + th_ - 2), 3)
    for row in range(th_):                                     # barked log body
        t = row / float(th_ - 1)
        v = int(112 - 58 * abs(t - 0.28) / 0.72)
        pygame.draw.line(surface, (v, int(v * 0.76), int(v * 0.52)),
                         (tx_ - tl_ // 2, ty_ + row), (tx_ + tl_ // 2, ty_ + row))
    for _ in range(8):                                         # bark streaks
        bx0 = tx_ - tl_ // 2 + rng.randint(2, tl_ - 12)
        by0 = ty_ + rng.randint(7, th_ - 1)
        pygame.draw.line(surface, (56, 42, 26), (bx0, by0), (bx0 + rng.randint(4, 10), by0), 1)
    for ex_, lit in ((tx_ - tl_ // 2, True), (tx_ + tl_ // 2, False)):   # end grain
        pygame.draw.ellipse(surface, (52, 38, 23), (ex_ - 3, ty_ - 1, 7, th_ + 2))
        pygame.draw.ellipse(surface, (144, 119, 82) if lit else (108, 88, 58), (ex_ - 2, ty_, 5, th_))
        pygame.draw.ellipse(surface, (96, 76, 48), (ex_ - 1, ty_ + 2, 3, th_ - 5), 1)
    pygame.draw.ellipse(surface, (38, 29, 18), (tx_ - tl_ // 2 + 4, ty_ + 1, tl_ - 8, 7))   # hollow
    pygame.draw.ellipse(surface, (106, 94, 66), (tx_ - tl_ // 2 + 6, ty_ + 2, tl_ - 12, 5))  # slop
    pygame.draw.ellipse(surface, (128, 113, 80), (tx_ - 10, ty_ + 2, 18, 3))
    for _ in range(6):                                         # floating chunks
        pygame.draw.circle(surface, rng.choice([(152, 136, 96), (170, 152, 106), (128, 118, 82)]),
                           (tx_ + rng.randint(-18, 18), ty_ + 3 + rng.randint(0, 2)), 1)
    pygame.draw.line(surface, (172, 170, 150), (tx_ - 6, ty_ + 3), (tx_ + 2, ty_ + 3), 1)   # sheen
    for _ in range(4):                                         # slop over the lip
        dx0 = tx_ + rng.randint(-16, 16)
        pygame.draw.line(surface, (98, 90, 62), (dx0, ty_ + 7), (dx0, ty_ + 7 + rng.randint(2, 4)), 1)
    sp = pygame.Surface((26, 10), pygame.SRCALPHA)             # spill on the ground
    pygame.draw.ellipse(sp, (76, 68, 46, 140), (0, 0, 26, 10))
    pygame.draw.ellipse(sp, (100, 92, 62, 120), (4, 2, 14, 5))
    surface.blit(sp, (tx_ - 26, ty_ + th_ + 1))
    for fpx, fpy in ((tx_ - 14, ty_ - 4), (tx_ + 9, ty_ - 6), (tx_ - 2, ty_ - 8)):  # flies
        surface.set_at((int(fpx), int(fpy)), (30, 26, 22))

    # ── Clutter ──────────────────────────────────────────────────────────────
    # burlap feed sack tipped over by the back-right fence, grain pouring out
    sk_x, sk_y = cx + 62, cy - 34
    _pen_soft_shadow(surface, sk_x + 2, sk_y + 7, 30, 9, alpha=60)
    sk_body = [(sk_x - 14, sk_y + 2), (sk_x - 12, sk_y - 4), (sk_x - 4, sk_y - 7),
               (sk_x + 8, sk_y - 6), (sk_x + 14, sk_y - 1), (sk_x + 13, sk_y + 5),
               (sk_x + 4, sk_y + 8), (sk_x - 8, sk_y + 7)]
    pygame.draw.polygon(surface, (124, 103, 68), sk_body)
    pygame.draw.polygon(surface, (152, 128, 88), [(sk_x - 12, sk_y - 3), (sk_x - 4, sk_y - 6),
                                                  (sk_x + 6, sk_y - 5), (sk_x + 2, sk_y - 1),
                                                  (sk_x - 8, sk_y)])
    pygame.draw.polygon(surface, (98, 80, 52), [(sk_x + 4, sk_y + 2), (sk_x + 12, sk_y + 1),
                                                (sk_x + 11, sk_y + 5), (sk_x + 3, sk_y + 7)])
    pygame.draw.polygon(surface, (84, 67, 42), sk_body, 1)
    # open mouth at the left end
    pygame.draw.ellipse(surface, (66, 52, 32), (sk_x - 17, sk_y - 3, 6, 8))
    pygame.draw.ellipse(surface, (104, 84, 54), (sk_x - 17, sk_y - 3, 6, 8), 1)
    # crease folds
    pygame.draw.line(surface, (104, 85, 54), (sk_x - 6, sk_y - 5), (sk_x - 4, sk_y + 5), 1)
    pygame.draw.line(surface, (104, 85, 54), (sk_x + 4, sk_y - 5), (sk_x + 6, sk_y + 4), 1)
    for _ in range(12):
        pygame.draw.circle(surface, rng.choice([(198, 174, 104), (166, 142, 76)]),
                           (sk_x - 16 + rng.randint(-5, 4), sk_y + 3 + rng.randint(0, 5)), 1)

    # tipped wooden bucket, leaked puddle at its mouth
    bk_x, bk_y = cx - 66, cy - 16
    _pen_soft_shadow(surface, bk_x + 3, bk_y + 9, 22, 8, alpha=55)
    bpts = [(bk_x - 6, bk_y - 1), (bk_x + 7, bk_y + 1), (bk_x + 9, bk_y + 10), (bk_x - 8, bk_y + 8)]
    pygame.draw.polygon(surface, (112, 90, 58), bpts)
    pygame.draw.polygon(surface, (140, 116, 78),
                        [bpts[0], bpts[1], (bk_x + 5, bk_y + 4), (bk_x - 5, bk_y + 3)])
    for k in range(4):
        u = k / 3.0
        pygame.draw.line(surface, (76, 58, 36),
                         (int(bk_x - 6 + 13 * u), int(bk_y - 1 + 2 * u)),
                         (int(bk_x - 8 + 17 * u), int(bk_y + 8 + 2 * u)), 1)
    pygame.draw.line(surface, (80, 76, 68), (bk_x - 7, bk_y + 2), (bk_x + 8, bk_y + 4), 1)
    pygame.draw.line(surface, (80, 76, 68), (bk_x - 8, bk_y + 6), (bk_x + 9, bk_y + 8), 1)
    pygame.draw.polygon(surface, (54, 40, 24), bpts, 1)
    pygame.draw.ellipse(surface, (40, 30, 19), (bk_x - 11, bk_y - 2, 7, 11))
    pygame.draw.ellipse(surface, (120, 98, 66), (bk_x - 11, bk_y - 2, 7, 11), 1)
    pq = pygame.Surface((20, 9), pygame.SRCALPHA)
    pygame.draw.ellipse(pq, (52, 56, 50, 200), (0, 0, 20, 9))
    pygame.draw.ellipse(pq, (130, 144, 146, 110), (5, 2, 8, 3))
    surface.blit(pq, (bk_x - 22, bk_y + 4))

    # scratching post — stout, strongly leaning, rub-worn pale at pig height
    sp_x, sp_y = cx + 76, cy + 10
    _pen_soft_shadow(surface, sp_x + 4, sp_y + 2, 18, 7, alpha=55)
    top = (sp_x - 9, sp_y - 13)
    for i in range(-3, 4):
        v = 114 - (i + 3) * 11
        pygame.draw.line(surface, (v, int(v * 0.78), int(v * 0.54)),
                         (sp_x + i, sp_y), (top[0] + i, top[1]), 2)
    # pale band worn smooth where the pigs rub
    pygame.draw.line(surface, (172, 150, 112), (sp_x - 4, sp_y - 5), (top[0] + 5, top[1] + 5), 4)
    pygame.draw.line(surface, (196, 174, 134), (sp_x - 4, sp_y - 6), (top[0] + 5, top[1] + 4), 1)
    # weathered broken tip
    pygame.draw.line(surface, (74, 58, 38), (top[0] - 3, top[1] + 1), (top[0] + 3, top[1] - 2), 3)
    pygame.draw.line(surface, (96, 78, 50), (top[0] - 2, top[1] - 1), (top[0] + 2, top[1] - 2), 1)
    msm = pygame.Surface((20, 8), pygame.SRCALPHA)
    pygame.draw.ellipse(msm, (60, 47, 31, 130), (0, 0, 20, 8))
    surface.blit(msm, (sp_x - 10, sp_y - 3))

    # ── Circling yard fence; the hut occludes the back of the ring ──────────
    _sh_occlude = pygame.Rect(eave_l2 - 2, ridge_y2 - 2, (eave_r2 - eave_l2) + 4,
                              (mouth_y + 6) - (ridge_y2 - 2))
    _draw_yard_fence(surface, cx, cy, pw // 2 + 6, ph // 2 + 4,
                     seed=seed * 13 + 3, post_r=5, n_posts=20, occlude_rect=_sh_occlude)

    # (Pigs are drawn at runtime via the farm animal system)
    return fence_r


def draw_sheep_pen(surface: pygame.Surface, x: int, y: int, seed: int = 0) -> pygame.Rect:
    """Draw a richly detailed sheep pasture farm scene (~240x160px)."""
    import math as _m
    rng = random.Random(seed + 9001)

    # ── Dimensions ──────────────────────────────────────────────────────────
    pw, ph = 240, 160
    yard = pygame.Rect(x - pw // 2, y - ph // 2, pw, ph)

    # ── Ground: multi-layer lush grass base ──────────────────────────────────
    grass_surf = pygame.Surface((pw + 24, ph + 24), pygame.SRCALPHA)
    pygame.draw.ellipse(grass_surf, (54, 90, 44, 240), (0, 0, pw + 24, ph + 24))
    pygame.draw.ellipse(grass_surf, (48, 84, 38, 210), (10, 8, pw + 4, ph + 8))
    pygame.draw.ellipse(grass_surf, (44, 78, 34, 170), (20, 15, pw - 10, ph - 4))
    surface.blit(grass_surf, (x - pw // 2 - 12, y - ph // 2 - 12))

    # Darker & lighter grass variation patches
    for _ in range(8):
        vpx = x + rng.randint(-pw // 2 + 12, pw // 2 - 12)
        vpy = y + rng.randint(-ph // 2 + 10, ph // 2 - 10)
        vc = rng.choice([(38, 78, 30, 120), (60, 98, 48, 100), (50, 88, 40, 90)])
        vp_surf = pygame.Surface((38, 20), pygame.SRCALPHA)
        pygame.draw.ellipse(vp_surf, vc, (0, 0, 38, 20))
        surface.blit(vp_surf, (vpx - 19, vpy - 10))

    # Individual blade tufts (3-line clusters)
    for _ in range(70):
        gx = x + rng.randint(-pw // 2 + 8, pw // 2 - 8)
        gy = y + rng.randint(-ph // 2 + 8, ph // 2 - 8)
        blade_h = rng.randint(5, 13)
        g_col = (36 + rng.randint(0, 24), 68 + rng.randint(0, 26), 26 + rng.randint(0, 14))
        g_col2 = (g_col[0] + 10, g_col[1] + 14, g_col[2] + 6)
        pygame.draw.line(surface, g_col, (gx, gy), (gx - 2, gy - blade_h), 1)
        pygame.draw.line(surface, g_col2, (gx, gy), (gx + 2, gy - blade_h + 2), 1)
        pygame.draw.line(surface, g_col, (gx + 1, gy), (gx + 1, gy - blade_h + 3), 1)

    # Clover patches
    for _ in range(10):
        cx_cl = x + rng.randint(-pw // 2 + 14, pw // 2 - 14)
        cy_cl = y + rng.randint(-ph // 2 + 12, ph // 2 - 12)
        for leaf in range(3):
            ang_cl = leaf * 2.094 + rng.uniform(-0.3, 0.3)
            lx_cl = cx_cl + int(4 * _m.cos(ang_cl))
            ly_cl = cy_cl + int(4 * _m.sin(ang_cl))
            pygame.draw.circle(surface, (42, 98, 38), (lx_cl, ly_cl), 2)
        # Clover stem
        pygame.draw.line(surface, (36, 84, 32), (cx_cl, cy_cl + 4), (cx_cl, cy_cl + 8), 1)

    # Wildflower dots (yellow and white)
    for _ in range(14):
        flx = x + rng.randint(-pw // 2 + 12, pw // 2 - 12)
        fly = y + rng.randint(-ph // 2 + 10, ph // 2 - 10)
        fl_col = rng.choice([(230, 220, 80), (255, 255, 200), (220, 180, 60), (200, 80, 80)])
        pygame.draw.circle(surface, fl_col, (flx, fly), 2)
        pygame.draw.circle(surface, (240, 220, 120), (flx, fly), 1)

    # Worn dirt paths
    for _ in range(4):
        px1 = x + rng.randint(-pw // 2 + 16, pw // 2 - 16)
        py1 = y + rng.randint(-ph // 2 + 12, ph // 2 - 12)
        px2 = px1 + rng.randint(-50, 50)
        py2 = py1 + rng.randint(-25, 25)
        pygame.draw.line(surface, (74, 66, 50), (px1, py1), (px2, py2), 5)
        pygame.draw.line(surface, (82, 74, 58), (px1 + 1, py1 + 1), (px2 + 1, py2 + 1), 2)

    # ── Stone wall fence (dry-stack, individual stones with hash color) ──────
    fr = yard.inflate(18, 18)
    wall_th = 12  # wall thickness

    def _draw_stone_row(sx_start, sx_end, sy_row, row_off, row_idx, is_horiz, is_bottom_edge=False):
        stone_spacing = 11
        for ssi in range(sx_start, sx_end - 4, stone_spacing):
            soff = row_off if row_idx % 2 == 0 else 0
            actual_x = ssi + soff
            if actual_x > sx_end - 5:
                break
            # Hash-based stone color
            shash = (actual_x * 7 + sy_row * 13 + row_idx * 5) % 26
            sc = 98 + shash
            sw_s = 8 + (actual_x * 3 + row_idx) % 6
            sh_s = wall_th - 2 + (sy_row * 7 + ssi) % 4
            if is_horiz:
                stone_rect = (actual_x, sy_row - sh_s // 2, min(sw_s, sx_end - actual_x - 2), sh_s)
            else:
                stone_rect = (sy_row - sh_s // 2, actual_x, sh_s, min(sw_s, sx_end - actual_x - 2))
            pygame.draw.rect(surface, (sc, sc - 5, sc - 12), stone_rect, border_radius=1)
            pygame.draw.rect(surface, (sc - 28, sc - 33, sc - 40), stone_rect, 1, border_radius=1)
            # Moss/lichen at base of wall
            if is_bottom_edge and rng.random() > 0.6:
                m_surf = pygame.Surface((sw_s, 4), pygame.SRCALPHA)
                pygame.draw.rect(m_surf, (46, 82, 34, 130), (0, 0, sw_s, 4))
                if is_horiz:
                    surface.blit(m_surf, (actual_x, sy_row + sh_s // 2 - 3))
                else:
                    pass  # skip moss on vertical sides for brevity

    # Top wall (2 rows of stacked stones)
    for row_i in range(2):
        _draw_stone_row(fr.left, fr.right, fr.top + row_i * (wall_th // 2), 5 if row_i % 2 else 0,
                        row_i, True, row_i == 1)
    # Bottom wall
    for row_i in range(2):
        _draw_stone_row(fr.left, fr.right, fr.bottom - wall_th // 2 + row_i * (wall_th // 2),
                        5 if row_i % 2 else 0, row_i + 4, True, row_i == 1)
    # Left wall
    for row_i in range(2):
        _draw_stone_row(fr.top, fr.bottom, fr.left + row_i * (wall_th // 2), 5 if row_i % 2 else 0,
                        row_i + 8, False)
    # Right wall
    for row_i in range(2):
        _draw_stone_row(fr.top, fr.bottom, fr.right - wall_th + row_i * (wall_th // 2), 5 if row_i % 2 else 0,
                        row_i + 12, False)

    # ── Wooden gate in bottom wall (cross-brace, iron hinges) ────────────────
    gate_x_s = fr.right - 44
    gate_y_s = fr.bottom - wall_th // 2
    gate_w_s = 40
    gate_h_s = wall_th + 14
    # Clear stone where gate is
    pygame.draw.rect(surface, (48, 84, 38), (gate_x_s, gate_y_s - gate_h_s // 2, gate_w_s, gate_h_s + 2))
    # Gate planks
    for row in range(gate_h_s):
        t = row / max(1, gate_h_s - 1)
        gshd = int(94 - 12 * t)
        pygame.draw.line(surface, (gshd, gshd - 16, gshd - 32),
                         (gate_x_s, gate_y_s - gate_h_s // 2 + row),
                         (gate_x_s + gate_w_s, gate_y_s - gate_h_s // 2 + row))
    # Plank verticals
    for gvx in range(gate_x_s + 10, gate_x_s + gate_w_s - 4, 10):
        pygame.draw.line(surface, (58, 42, 20),
                         (gvx, gate_y_s - gate_h_s // 2 + 2),
                         (gvx, gate_y_s + gate_h_s // 2 - 2), 1)
    # Cross-brace
    pygame.draw.line(surface, (64, 46, 24),
                     (gate_x_s + 2, gate_y_s - gate_h_s // 2 + 2),
                     (gate_x_s + gate_w_s - 2, gate_y_s + gate_h_s // 2 - 2), 2)
    pygame.draw.rect(surface, (52, 36, 18), (gate_x_s, gate_y_s - gate_h_s // 2, gate_w_s, gate_h_s), 1)
    # Iron hinges
    for ghy in [gate_y_s - gate_h_s // 2 + 4, gate_y_s + gate_h_s // 2 - 6]:
        pygame.draw.rect(surface, (52, 48, 42), (gate_x_s - 2, ghy, 14, 4), border_radius=1)
        pygame.draw.rect(surface, (34, 30, 26), (gate_x_s - 2, ghy, 14, 4), 1, border_radius=1)
        for ri in range(0, 12, 3):
            pygame.draw.circle(surface, (66, 60, 50), (gate_x_s + ri, ghy + 2), 1)
    # Iron latch
    pygame.draw.rect(surface, (52, 48, 42),
                     (gate_x_s + gate_w_s - 3, gate_y_s, 8, 4), border_radius=1)
    pygame.draw.circle(surface, (70, 64, 54), (gate_x_s + gate_w_s + 4, gate_y_s + 2), 2)
    # Wool wisp caught on gate
    for _ in range(2):
        wwx = gate_x_s + rng.randint(4, gate_w_s - 4)
        wwy = gate_y_s - gate_h_s // 2
        for wi in range(3):
            pygame.draw.line(surface, (240, 236, 228),
                             (wwx + wi, wwy), (wwx + wi + rng.randint(-2, 2), wwy - rng.randint(2, 5)), 1)

    # ── Shelter (3-post lean-to in corner, plank roof, hay bedding) ──────────
    shelt_x = fr.left + 8
    shelt_y = fr.top + 8
    shelt_w = 52
    shelt_h = 38
    # Back plank wall
    for row in range(shelt_h):
        t = row / max(1, shelt_h - 1)
        swshd = int(86 - 14 * t)
        pygame.draw.line(surface, (swshd, swshd - 16, swshd - 32),
                         (shelt_x, shelt_y + row), (shelt_x + shelt_w, shelt_y + row))
    for svx in range(shelt_x + 13, shelt_x + shelt_w - 6, 13):
        pygame.draw.line(surface, (52, 36, 16), (svx, shelt_y + 2), (svx, shelt_y + shelt_h - 2), 1)
    pygame.draw.rect(surface, (46, 30, 12), (shelt_x, shelt_y, shelt_w, shelt_h), 1)
    # 3 timber posts with grain
    for pxoff in [0, shelt_w // 2, shelt_w]:
        post_top = shelt_y - 6
        for row in range(shelt_h + 14):
            t = row / max(1, shelt_h + 13)
            ps = int(78 - 16 * t)
            pygame.draw.line(surface, (ps, ps - 14, ps - 30),
                             (shelt_x + pxoff - 2, post_top + row),
                             (shelt_x + pxoff + 2, post_top + row))
        pygame.draw.rect(surface, (44, 30, 12), (shelt_x + pxoff - 3, post_top, 5, shelt_h + 14), 1)
        # Grain texture line on post
        pygame.draw.line(surface, (60, 44, 22),
                         (shelt_x + pxoff, post_top + 4),
                         (shelt_x + pxoff - 1, post_top + shelt_h + 4), 1)
        # Moss at post base
        ms3 = pygame.Surface((9, 5), pygame.SRCALPHA)
        pygame.draw.ellipse(ms3, (46, 80, 34, 120), (0, 0, 9, 5))
        surface.blit(ms3, (shelt_x + pxoff - 3, post_top + shelt_h + 10))
    # Angled plank roof (overlapping planks)
    roof_pts_s2 = [
        (shelt_x - 8, shelt_y - 4),
        (shelt_x + shelt_w + 8, shelt_y + 8),
        (shelt_x + shelt_w + 8, shelt_y + 16),
        (shelt_x - 8, shelt_y + 4),
    ]
    # Fill roof row by row
    for ri_r2 in range(18):
        t = ri_r2 / 17
        lx_r2 = int(roof_pts_s2[0][0] + (roof_pts_s2[3][0] - roof_pts_s2[0][0]) * t)
        ly_r2 = int(roof_pts_s2[0][1] + (roof_pts_s2[3][1] - roof_pts_s2[0][1]) * t)
        rx_r2b = int(roof_pts_s2[1][0] + (roof_pts_s2[2][0] - roof_pts_s2[1][0]) * t)
        ry_r2b = int(roof_pts_s2[1][1] + (roof_pts_s2[2][1] - roof_pts_s2[1][1]) * t)
        rshd2 = int(100 - 14 * t) + rng.randint(-3, 3)
        pygame.draw.line(surface, (rshd2, rshd2 - 18, rshd2 - 36), (lx_r2, ly_r2), (rx_r2b, ry_r2b))
    # Plank seam lines on roof
    for roff in [shelt_w // 3, 2 * shelt_w // 3]:
        pygame.draw.line(surface, (54, 38, 18),
                         (shelt_x + roff, shelt_y - 2), (shelt_x + roff + 4, shelt_y + 14), 1)
    pygame.draw.polygon(surface, (52, 36, 16), roof_pts_s2, 1)
    # Drip edge beam
    pygame.draw.line(surface, (64, 46, 22), (shelt_x - 8, shelt_y - 4), (shelt_x + shelt_w + 8, shelt_y + 8), 2)

    # Hay bedding inside shelter
    pygame.draw.ellipse(surface, (162, 144, 74), (shelt_x + 4, shelt_y + shelt_h - 10, shelt_w - 8, 12))
    for si in range(10):
        shwx = shelt_x + 6 + si * 4
        shwy = shelt_y + shelt_h - 9
        pygame.draw.line(surface, (148, 130, 60), (shwx, shwy),
                         (shwx + rng.randint(-3, 3), shwy - rng.randint(3, 8)), 1)

    # ── Water trough (wooden, iron bands, specular highlight) ─────────────────
    tr_x = x + rng.randint(30, 70)
    tr_y = y + rng.randint(-50, -20)
    # Trough legs
    for tlx in [-18, 14]:
        for row in range(10):
            t = row / 9
            tls = int(76 - 14 * t)
            pygame.draw.line(surface, (tls, tls - 14, tls - 30),
                             (tr_x + tlx, tr_y + 12 + row), (tr_x + tlx + 4, tr_y + 12 + row))
    # Trough body (plank rows)
    for row in range(14):
        t = row / 13
        trshd = int(94 - 16 * t)
        pygame.draw.line(surface, (trshd, trshd - 18, trshd - 38),
                         (tr_x - 22, tr_y + row), (tr_x + 22, tr_y + row))
    for tvx in range(tr_x - 18, tr_x + 18, 8):
        pygame.draw.line(surface, (56, 40, 20), (tvx, tr_y + 2), (tvx, tr_y + 11), 1)
    # Iron bands
    for boff in [2, 10]:
        pygame.draw.rect(surface, (52, 48, 42), (tr_x - 23, tr_y + boff, 46, 3))
        pygame.draw.rect(surface, (34, 30, 26), (tr_x - 23, tr_y + boff, 46, 3), 1)
    pygame.draw.rect(surface, (46, 32, 14), (tr_x - 23, tr_y, 46, 14), 1)
    # Water surface
    pygame.draw.rect(surface, (68, 104, 132), (tr_x - 20, tr_y + 3, 40, 8))
    # Specular highlight on water
    pygame.draw.line(surface, (118, 155, 182), (tr_x - 12, tr_y + 4), (tr_x + 2, tr_y + 4), 2)
    pygame.draw.line(surface, (98, 135, 162), (tr_x - 4, tr_y + 7), (tr_x + 10, tr_y + 7), 1)

    # ── Salt lick block on wooden base ────────────────────────────────────────
    sl_x = x + rng.randint(-80, -40)
    sl_y = y + rng.randint(20, 50)
    # Wooden base
    for row in range(6):
        t = row / 5
        slshd = int(88 - 12 * t)
        pygame.draw.line(surface, (slshd, slshd - 16, slshd - 32),
                         (sl_x - 9, sl_y + row), (sl_x + 9, sl_y + row))
    pygame.draw.rect(surface, (52, 36, 16), (sl_x - 9, sl_y, 18, 6), 1)
    # Salt lick block (worn, slightly irregular)
    pygame.draw.rect(surface, (186, 158, 114), (sl_x - 7, sl_y - 12, 14, 12), border_radius=2)
    pygame.draw.rect(surface, (162, 132, 90), (sl_x - 7, sl_y - 12, 14, 12), 1, border_radius=2)
    # Lick marks (worn concave top)
    pygame.draw.ellipse(surface, (168, 142, 100), (sl_x - 4, sl_y - 14, 8, 4))

    # ── Shepherd's crook leaning on wall ─────────────────────────────────────
    crook_x = fr.left + rng.randint(14, 36)
    crook_y = fr.top + 4
    # Staff (straight part with grain)
    for row in range(28):
        t = row / 27
        crshd = int(92 - 14 * t)
        pygame.draw.line(surface, (crshd, crshd - 16, crshd - 32),
                         (crook_x - 1, crook_y - 22 + row), (crook_x + 1, crook_y - 22 + row))
    pygame.draw.line(surface, (60, 44, 22), (crook_x, crook_y - 22), (crook_x, crook_y + 6), 1)
    # Iron-tipped base
    pygame.draw.rect(surface, (52, 48, 44), (crook_x - 1, crook_y + 4, 3, 4), border_radius=1)
    # Crook arc
    pygame.draw.arc(surface, (78, 58, 32), (crook_x - 7, crook_y - 30, 14, 14), 0, _m.pi, 3)
    pygame.draw.arc(surface, (94, 72, 44), (crook_x - 7, crook_y - 30, 14, 14), 0, _m.pi, 1)

    # ── Hay rack (angled frame with hay) ─────────────────────────────────────
    hr_x = fr.right - 22
    hr_y = fr.top + 16
    hr_w, hr_h = 26, 30
    # Frame posts
    for pxr in [hr_x, hr_x + hr_w]:
        for row in range(hr_h + 6):
            t = row / max(1, hr_h + 5)
            hrshd = int(84 - 14 * t)
            pygame.draw.line(surface, (hrshd, hrshd - 14, hrshd - 28),
                             (pxr - 2, hr_y - 4 + row), (pxr + 2, hr_y - 4 + row))
        pygame.draw.rect(surface, (46, 32, 14), (pxr - 2, hr_y - 4, 5, hr_h + 6), 1)
    # Angled rack slats
    for si_r in range(4):
        t = si_r / 3
        slat_y = hr_y + int(hr_h * t)
        pygame.draw.line(surface, (78, 58, 30), (hr_x - 4, slat_y), (hr_x + hr_w + 4, slat_y + 4), 2)
    # Hay inside rack
    pygame.draw.rect(surface, (168, 148, 72), (hr_x + 2, hr_y + 4, hr_w - 4, hr_h - 6))
    for wi_r in range(5):
        wxr = hr_x + 4 + wi_r * 4
        pygame.draw.line(surface, (152, 132, 58), (wxr, hr_y + 4),
                         (wxr + rng.randint(-2, 2), hr_y + 4 + rng.randint(4, 10)), 1)
    pygame.draw.rect(surface, (52, 38, 16), (hr_x, hr_y, hr_w + 1, hr_h), 1)

    # ── Wool wisp caught on stone wall ────────────────────────────────────────
    for _ in range(3):
        wwx2 = fr.left + rng.randint(14, fr.width - 28)
        wwy2 = rng.choice([fr.top, fr.bottom])
        for wi2 in range(4):
            pygame.draw.circle(surface, (242, 238, 230), (wwx2 + wi2, wwy2 + wi2 - 2), 2)


    # (Sheep are now drawn at runtime via the farm animal system)

    # ── Optional sheepdog (40% chance) ────────────────────────────────────────
    if rng.random() < 0.4:
        dx_d = x + rng.randint(-pw // 2 + 20, pw // 2 - 20)
        dy_d = y + rng.randint(-ph // 2 + 20, ph // 2 - 20)
        df = rng.choice([-1, 1])

        # Shadow
        dsh = pygame.Surface((22, 8), pygame.SRCALPHA)
        pygame.draw.ellipse(dsh, (0, 0, 0, 48), (0, 0, 22, 8))
        surface.blit(dsh, (dx_d - 11, dy_d + 8))

        # Legs (4 alert stance)
        for dlx_o, dly_o in [(-6, 5), (-2, 6), (2, 6), (6, 5)]:
            pygame.draw.line(surface, (34, 30, 26), (dx_d + dlx_o, dy_d + dly_o),
                             (dx_d + dlx_o, dy_d + dly_o + 10), 2)
            pygame.draw.ellipse(surface, (26, 22, 18), (dx_d + dlx_o - 1, dy_d + dly_o + 9, 3, 3))

        # Body: black with white chest
        for brow in range(14):
            t = brow / 13
            bshd = int(42 - 8 * t)
            bw_d = int(_m.sqrt(max(0, 1 - ((brow - 7) / 7.5) ** 2)) * 10)
            if bw_d > 0:
                pygame.draw.line(surface, (bshd, bshd, bshd),
                                 (dx_d - bw_d, dy_d - 7 + brow), (dx_d + bw_d, dy_d - 7 + brow))
        # White chest patch
        pygame.draw.ellipse(surface, (230, 226, 218), (dx_d - 4, dy_d - 4, 8, 10))
        # White mane on back
        for _ in range(4):
            pygame.draw.circle(surface, (220, 216, 210), (dx_d + rng.randint(-4, 4), dy_d - 4), 3)

        # Tail (upright and bushy)
        for ti in range(4):
            pygame.draw.line(surface, (40, 36, 32) if ti % 2 == 0 else (220, 216, 210),
                             (dx_d - df * 9, dy_d - 2),
                             (dx_d - df * (12 + ti * 2), dy_d - 6 - ti * 3), 2)

        # Head (alert, ears up)
        dhx = dx_d + df * 11
        dhy = dy_d - 4
        pygame.draw.ellipse(surface, (36, 32, 28), (dhx - 5, dhy - 5, 10, 12))
        # White blaze on nose
        pygame.draw.ellipse(surface, (220, 216, 210), (dhx - 2, dhy - 2, 4, 6))
        # Alert upright ears
        pygame.draw.polygon(surface, (34, 30, 26),
                            [(dhx - 4, dhy - 5), (dhx - 6, dhy - 12), (dhx - 1, dhy - 5)])
        pygame.draw.polygon(surface, (34, 30, 26),
                            [(dhx + 1, dhy - 5), (dhx + 4, dhy - 12), (dhx + 6, dhy - 5)])
        # Eyes
        pygame.draw.circle(surface, (180, 130, 30), (dhx + df * 2 - 1, dhy - 1), 2)
        pygame.draw.circle(surface, (18, 14, 10), (dhx + df * 2 - 1, dhy - 1), 1)
        # Tongue out (panting)
        if rng.random() > 0.5:
            pygame.draw.ellipse(surface, (220, 80, 80), (dhx + df * 4 - 2, dhy + 4, 5, 4))

    return fr


def draw_dock(surface: pygame.Surface, x: int, y: int, length: int = 160,
              horizontal: bool = True) -> pygame.Rect:
    """Draw a wooden dock extending into water."""
    rng = random.Random(x * 11 + y * 17)
    if horizontal:
        rect = pygame.Rect(x, y - 16, length, 32)
    else:
        rect = pygame.Rect(x - 16, y, 32, length)
    # Shadow
    shadow = rect.inflate(6, 6).move(3, 3)
    s_surf = pygame.Surface((shadow.width, shadow.height), pygame.SRCALPHA)
    s_surf.fill((0, 0, 0, 35))
    surface.blit(s_surf, shadow.topleft)
    # Planks
    if horizontal:
        for px_d in range(rect.left, rect.right, 12):
            pw = min(10, rect.right - px_d)
            shade = 105 + rng.randint(-10, 10)
            pygame.draw.rect(surface, (shade, shade - 15, shade - 35),
                             (px_d, rect.top, pw, rect.height))
            pygame.draw.rect(surface, (70, 55, 35), (px_d, rect.top, pw, rect.height), 1)
    else:
        for py_d in range(rect.top, rect.bottom, 12):
            ph_d = min(10, rect.bottom - py_d)
            shade = 105 + rng.randint(-10, 10)
            pygame.draw.rect(surface, (shade, shade - 15, shade - 35),
                             (rect.left, py_d, rect.width, ph_d))
            pygame.draw.rect(surface, (70, 55, 35), (rect.left, py_d, rect.width, ph_d), 1)
    # Support posts
    if horizontal:
        for px_d in [rect.left + 10, rect.centerx, rect.right - 10]:
            pygame.draw.rect(surface, (80, 60, 35), (px_d - 3, rect.bottom, 6, 10))
    else:
        for py_d in [rect.top + 10, rect.centery, rect.bottom - 10]:
            pygame.draw.rect(surface, (80, 60, 35), (rect.right, py_d - 3, 10, 6))
    pygame.draw.rect(surface, (60, 42, 24), rect, 2)
    return rect


def draw_small_boat(surface: pygame.Surface, x: int, y: int, seed: int = 0) -> None:
    """Draw a small fishing boat (decorative, no collision)."""
    rng = random.Random(seed + 6001)
    # Hull
    hull_pts = [
        (x - 24, y - 6), (x + 24, y - 6),
        (x + 18, y + 8), (x - 18, y + 8),
    ]
    hull_color = rng.choice([(110, 70, 40), (90, 55, 30), (80, 50, 45)])
    pygame.draw.polygon(surface, hull_color, hull_pts)
    pygame.draw.polygon(surface, (50, 30, 15), hull_pts, 2)
    # Bow point
    pygame.draw.polygon(surface, (hull_color[0] - 10, hull_color[1] - 10, hull_color[2] - 10),
                        [(x + 24, y - 6), (x + 32, y + 1), (x + 24, y + 8)])
    # Mast
    pygame.draw.line(surface, (90, 70, 45), (x - 4, y - 6), (x - 4, y - 34), 2)
    # Sail (small triangle)
    sail_pts = [(x - 4, y - 32), (x - 4, y - 12), (x + 16, y - 18)]
    sail_color = (200 + rng.randint(-15, 15), 190 + rng.randint(-15, 10), 170 + rng.randint(-10, 10))
    pygame.draw.polygon(surface, sail_color, sail_pts)
    pygame.draw.polygon(surface, (140, 130, 110), sail_pts, 1)


def draw_sailing_ship(surface: pygame.Surface, x: int, y: int, scale: float = 1.0, seed: int = 0) -> pygame.Rect:
    """Draw a detailed galleon with curved hull, ornate stern, figurehead, gun ports, and full rigging."""
    rng = random.Random(seed + 7001)
    s = scale
    _s = lambda v: int(v * s)  # noqa: E731

    # ── Colors ──
    hull_base = (72, 44, 26)
    hull_dark = (48, 28, 14)
    hull_light = (92, 62, 38)
    trim_gold = (178, 148, 68)
    trim_dark = (120, 95, 42)
    deck_col = (110, 85, 55)
    deck_plank = (95, 72, 46)
    mast_col = (100, 78, 50)
    mast_dark = (72, 55, 35)
    rig_col = (68, 58, 42)
    sail_base = (218, 208, 188)
    sail_shade = (188, 178, 158)
    sail_seam = (168, 158, 140)

    hull_w = _s(200)
    hull_h = _s(60)
    bow_ext = _s(44)
    stern_ext = _s(28)
    deck_y = y - _s(14)

    # ── Water reflection / shadow ──
    wake_s = pygame.Surface((_s(260), _s(50)), pygame.SRCALPHA)
    pygame.draw.ellipse(wake_s, (8, 16, 36, 45), wake_s.get_rect())
    surface.blit(wake_s, (x - _s(130), y + _s(22)))
    # Bow wave
    bw_s = pygame.Surface((_s(30), _s(18)), pygame.SRCALPHA)
    pygame.draw.ellipse(bw_s, (140, 180, 210, 50), bw_s.get_rect())
    surface.blit(bw_s, (x + hull_w // 2 + bow_ext - _s(8), y + _s(4)))

    # ── Hull — curved shape via many polygon points ──
    stern_x = x - hull_w // 2 - stern_ext
    bow_x = x + hull_w // 2 + bow_ext
    # Upper hull edge (deck line, slight sheer)
    top_pts = []
    for t in range(21):
        f = t / 20.0
        hx = stern_x + f * (bow_x - stern_x)
        # Sheer: rises at bow and stern
        sheer = _s(4) * (4 * (f - 0.5) ** 2)
        top_pts.append((int(hx), deck_y - int(sheer)))
    # Bottom hull edge (keel curve)
    bot_pts = []
    for t in range(21):
        f = t / 20.0
        hx = stern_x + _s(8) + f * (bow_x - stern_x - _s(12))
        # Keel curve: deepest at center
        keel_depth = hull_h * (1.0 - 4 * (f - 0.5) ** 2) * 0.9 + hull_h * 0.1
        bot_pts.append((int(hx), y + int(keel_depth * 0.55)))
    hull_pts = top_pts + list(reversed(bot_pts))
    pygame.draw.polygon(surface, hull_base, hull_pts)

    # ── Hull strakes (planking lines following hull curve) ──
    for si in range(8):
        blend = (si + 1) / 9.0
        strake_pts = []
        for t in range(21):
            f = t / 20.0
            tx = stern_x + _s(6) + f * (bow_x - stern_x - _s(10))
            ty_top = top_pts[t][1]
            ty_bot = bot_pts[t][1]
            sy_v = ty_top + (ty_bot - ty_top) * blend
            strake_pts.append((int(tx), int(sy_v)))
        if len(strake_pts) > 1:
            col_v = hull_base[0] - 8 + (si % 2) * 6
            pygame.draw.lines(surface, (col_v, col_v - 14, col_v - 22), False, strake_pts, 1)
    # Hull outline
    pygame.draw.polygon(surface, hull_dark, hull_pts, 2)

    # ── Waterline stripe (gold trim) ──
    wl_pts = []
    for t in range(21):
        f = t / 20.0
        hx = stern_x + _s(6) + f * (bow_x - stern_x - _s(8))
        ty_top = top_pts[t][1]
        ty_bot = bot_pts[t][1]
        wl_y_v = ty_top + (ty_bot - ty_top) * 0.45
        wl_pts.append((int(hx), int(wl_y_v)))
    if len(wl_pts) > 1:
        pygame.draw.lines(surface, trim_gold, False, wl_pts, _s(3))
    # Second trim line above waterline
    wl2_pts = [(p[0], p[1] - _s(6)) for p in wl_pts]
    if len(wl2_pts) > 1:
        pygame.draw.lines(surface, trim_dark, False, wl2_pts, 1)

    # ── Gun ports (two rows) ──
    for row, blend_v in [(0.25, 0), (0.38, 1)]:
        for gi in range(7):
            f = 0.12 + gi * 0.11
            gx = int(stern_x + _s(6) + f * (bow_x - stern_x - _s(10)))
            ty_top = top_pts[int(f * 20)][1] if int(f * 20) < len(top_pts) else deck_y
            ty_bot = bot_pts[int(f * 20)][1] if int(f * 20) < len(bot_pts) else y + hull_h // 2
            gy = int(ty_top + (ty_bot - ty_top) * row)
            gp_w, gp_h = _s(8), _s(7)
            gp_r = pygame.Rect(gx - gp_w // 2, gy - gp_h // 2, gp_w, gp_h)
            pygame.draw.rect(surface, (22, 16, 10), gp_r)
            pygame.draw.rect(surface, trim_gold, gp_r, 1)
            # Cannon barrel hint
            pygame.draw.line(surface, (40, 35, 28), (gx, gy), (gx + _s(5), gy), _s(2))

    # ── Deck (visible strip) ──
    deck_pts_poly = []
    for t in range(21):
        f = t / 20.0
        hx = stern_x + f * (bow_x - stern_x)
        sheer = _s(4) * (4 * (f - 0.5) ** 2)
        deck_pts_poly.append((int(hx), deck_y - int(sheer)))
    deck_inner = [(p[0], p[1] + _s(6)) for p in deck_pts_poly]
    deck_fill = deck_pts_poly + list(reversed(deck_inner))
    pygame.draw.polygon(surface, deck_col, deck_fill)
    # Deck planks
    for dpi in range(stern_x + 6, bow_x - 4, _s(6)):
        pygame.draw.line(surface, deck_plank, (dpi, deck_y - _s(3)), (dpi, deck_y + _s(3)), 1)
    # Deck rail
    for t in range(21):
        deck_pts_poly[t] = (deck_pts_poly[t][0], deck_pts_poly[t][1] - 1)
    pygame.draw.lines(surface, hull_dark, False, deck_pts_poly, 2)

    # ── Forecastle (raised bow platform) ──
    fc_x = x + hull_w // 4
    fc_w = hull_w // 4 + bow_ext
    fc_h = _s(22)
    fc_top = deck_y - fc_h - _s(3)
    fc_rect = pygame.Rect(fc_x, fc_top, fc_w, fc_h)
    pygame.draw.rect(surface, (hull_base[0] + 10, hull_base[1] + 8, hull_base[2] + 5), fc_rect)
    pygame.draw.rect(surface, hull_dark, fc_rect, 2)
    # Forecastle rail
    pygame.draw.line(surface, trim_gold, (fc_x, fc_top), (fc_x + fc_w, fc_top), 2)
    # Forecastle windows
    for fwi in range(2):
        fw_r = pygame.Rect(fc_x + _s(8) + fwi * _s(16), fc_top + _s(6), _s(10), _s(8))
        pygame.draw.rect(surface, (160, 185, 210), fw_r)
        pygame.draw.rect(surface, hull_dark, fw_r, 1)

    # ── Stern castle (ornate, multi-level) ──
    sc_base_x = stern_x
    # Lower stern gallery
    sc1_h = _s(28)
    sc1_w = _s(50)
    sc1_rect = pygame.Rect(sc_base_x, deck_y - sc1_h, sc1_w, sc1_h)
    pygame.draw.rect(surface, (hull_base[0] + 6, hull_base[1] + 4, hull_base[2] + 2), sc1_rect)
    # Upper stern gallery
    sc2_h = _s(22)
    sc2_w = _s(40)
    sc2_rect = pygame.Rect(sc_base_x + _s(5), sc1_rect.top - sc2_h, sc2_w, sc2_h)
    pygame.draw.rect(surface, (hull_base[0] + 12, hull_base[1] + 9, hull_base[2] + 5), sc2_rect)
    # Poop deck
    sc3_h = _s(14)
    sc3_w = _s(30)
    sc3_rect = pygame.Rect(sc_base_x + _s(10), sc2_rect.top - sc3_h, sc3_w, sc3_h)
    pygame.draw.rect(surface, (hull_base[0] + 16, hull_base[1] + 12, hull_base[2] + 8), sc3_rect)
    # Ornate stern details — gold trim on each level
    for sc_r in (sc1_rect, sc2_rect, sc3_rect):
        pygame.draw.rect(surface, hull_dark, sc_r, 2)
        pygame.draw.line(surface, trim_gold, (sc_r.left, sc_r.top), (sc_r.right, sc_r.top), 2)
        pygame.draw.line(surface, trim_gold, (sc_r.left, sc_r.bottom), (sc_r.right, sc_r.bottom), 2)
    # Stern gallery windows (arched)
    for swi in range(4):
        swx = sc1_rect.left + _s(6) + swi * _s(11)
        swy = sc1_rect.top + _s(6)
        sw_r = pygame.Rect(swx, swy, _s(8), _s(12))
        pygame.draw.rect(surface, (170, 195, 225), sw_r)
        # Arched top
        pygame.draw.ellipse(surface, (170, 195, 225), (swx, swy - _s(3), _s(8), _s(6)))
        pygame.draw.ellipse(surface, hull_dark, (swx, swy - _s(3), _s(8), _s(6)), 1)
        pygame.draw.rect(surface, hull_dark, sw_r, 1)
        pygame.draw.line(surface, hull_dark, (swx + _s(4), sw_r.top), (swx + _s(4), sw_r.bottom), 1)
    # Upper stern windows
    for swi in range(3):
        swx = sc2_rect.left + _s(5) + swi * _s(12)
        swy = sc2_rect.top + _s(5)
        sw_r = pygame.Rect(swx, swy, _s(8), _s(10))
        pygame.draw.rect(surface, (180, 200, 220), sw_r)
        pygame.draw.rect(surface, hull_dark, sw_r, 1)
    # Stern lantern
    _lt_x = sc3_rect.centerx
    _lt_y = sc3_rect.top - _s(8)
    pygame.draw.line(surface, mast_col, (_lt_x, sc3_rect.top), (_lt_x, _lt_y), 2)
    _lt_r = pygame.Rect(_lt_x - _s(4), _lt_y - _s(6), _s(8), _s(10))
    pygame.draw.rect(surface, (30, 25, 18), _lt_r, border_radius=2)
    pygame.draw.rect(surface, trim_gold, _lt_r, 1, border_radius=2)
    pygame.draw.rect(surface, (240, 210, 120), _lt_r.inflate(-4, -4))
    # Glow
    glow = pygame.Surface((_s(20), _s(20)), pygame.SRCALPHA)
    pygame.draw.ellipse(glow, (255, 220, 100, 35), glow.get_rect())
    surface.blit(glow, (_lt_x - _s(10), _lt_y - _s(10)))

    # ── Bowsprit + figurehead ──
    bsp_base = (bow_x, y)
    bsp_tip = (bow_x + _s(55), y - _s(28))
    pygame.draw.line(surface, mast_col, bsp_base, bsp_tip, _s(3))
    pygame.draw.line(surface, mast_dark, (bsp_base[0], bsp_base[1] + 1), (bsp_tip[0], bsp_tip[1] + 1), 1)
    # Figurehead (carved shape at bow)
    fh_x, fh_y = bow_x + _s(2), y - _s(2)
    fh_pts = [(fh_x, fh_y), (fh_x + _s(14), fh_y + _s(10)),
              (fh_x + _s(18), fh_y + _s(4)), (fh_x + _s(12), fh_y - _s(4)),
              (fh_x + _s(6), fh_y - _s(6))]
    pygame.draw.polygon(surface, trim_gold, fh_pts)
    pygame.draw.polygon(surface, trim_dark, fh_pts, 1)
    # Jib sail (triangular on bowsprit)
    jib_pts = [(bsp_tip[0], bsp_tip[1]), (bsp_tip[0] - _s(10), bsp_tip[1] + _s(4)),
               (bsp_base[0] + _s(10), deck_y - _s(6))]
    jib_col = (sail_base[0] - 5, sail_base[1] - 5, sail_base[2] + 5)
    pygame.draw.polygon(surface, jib_col, jib_pts)
    pygame.draw.polygon(surface, sail_seam, jib_pts, 1)

    # ── Masts (3 masts with tops and cross-trees) ──
    mast_positions = [
        (x - _s(25), _s(150)),   # mainmast (tallest)
        (x + _s(35), _s(120)),   # foremast
        (sc_base_x + _s(22), _s(100)),  # mizzenmast
    ]
    for mi, (mx, mh) in enumerate(mast_positions):
        mast_top = deck_y - mh
        mast_base = deck_y
        # Main mast pole
        pygame.draw.line(surface, mast_col, (mx, mast_base), (mx, mast_top), _s(4))
        pygame.draw.line(surface, mast_dark, (mx + _s(2), mast_base), (mx + _s(2), mast_top), 1)
        # Topmast (thinner, extends above)
        topmast_h = _s(30)
        pygame.draw.line(surface, mast_col, (mx, mast_top), (mx, mast_top - topmast_h), _s(2))
        # Cross-trees / tops platform
        ct_y = mast_top + _s(5)
        ct_w = _s(18)
        pygame.draw.rect(surface, (85, 65, 40), (mx - ct_w // 2, ct_y - _s(2), ct_w, _s(4)))
        pygame.draw.rect(surface, mast_dark, (mx - ct_w // 2, ct_y - _s(2), ct_w, _s(4)), 1)
        # Crow's nest on mainmast
        if mi == 0:
            cn_w = _s(20)
            cn_h = _s(8)
            cn_y_v = ct_y - cn_h
            pygame.draw.rect(surface, (82, 62, 40), (mx - cn_w // 2, cn_y_v, cn_w, cn_h))
            pygame.draw.rect(surface, mast_dark, (mx - cn_w // 2, cn_y_v, cn_w, cn_h), 1)
            # Nest rail
            pygame.draw.rect(surface, mast_col, (mx - cn_w // 2 - 1, cn_y_v - 2, cn_w + 2, 3))

    # ── Sails (multiple tiers per mast) ──
    for mi, (mx, mh) in enumerate(mast_positions):
        mast_top = deck_y - mh
        topmast_top = mast_top - _s(30)
        # Determine number of square sails
        n_sails = 3 if mi == 0 else (2 if mi == 1 else 1)
        sail_zone_top = mast_top + _s(8)
        sail_zone_bot = deck_y - _s(20)
        tier_h = (sail_zone_bot - sail_zone_top) // max(1, n_sails)

        for si in range(n_sails):
            st = sail_zone_top + si * tier_h
            sb = st + tier_h - _s(4)
            # Sail width narrows toward top
            sw_v = _s(60 - si * 8) if mi < 2 else _s(42 - si * 8)
            # Billowed curve via multiple polygon points
            n_curve = 8
            left_pts = [(mx - 1, st)]
            right_pts = [(mx + sw_v, st + _s(3))]
            for ci in range(1, n_curve):
                t = ci / n_curve
                cy_v = st + (sb - st) * t
                # Billow bulge (max at center)
                bulge = _s(8) * math.sin(t * math.pi) * (1.0 - si * 0.2)
                left_pts.append((mx - 1, int(cy_v)))
                right_pts.append((int(mx + sw_v + bulge), int(cy_v + _s(1) * math.sin(t * 3))))
            left_pts.append((mx - 1, sb))
            right_pts.append((mx + sw_v - _s(3), sb - _s(2)))
            sail_poly = left_pts + list(reversed(right_pts))
            # Sail fill with subtle vertical gradient
            sail_surf = pygame.Surface((sw_v + _s(12), sb - st + _s(4)), pygame.SRCALPHA)
            for row_i in range(sb - st):
                t_v = row_i / max(1, sb - st)
                sr = int(sail_base[0] - 15 * t_v)
                sg = int(sail_base[1] - 15 * t_v)
                sb_c = int(sail_base[2] - 10 * t_v)
                pygame.draw.line(sail_surf, (sr, sg, sb_c, 255), (0, row_i), (sw_v + _s(10), row_i))
            # Mask sail shape
            mask = pygame.Surface(sail_surf.get_size(), pygame.SRCALPHA)
            shifted_poly = [(p[0] - mx + 1, p[1] - st) for p in sail_poly]
            if len(shifted_poly) >= 3:
                pygame.draw.polygon(mask, (255, 255, 255, 255), shifted_poly)
                sail_surf.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
                surface.blit(sail_surf, (mx - 1, st))
            # Sail outline
            if len(sail_poly) >= 3:
                pygame.draw.polygon(surface, sail_seam, sail_poly, 1)
            # Horizontal seams
            for seam_i in range(1, 4):
                sy_s = st + (sb - st) * seam_i // 4
                pygame.draw.line(surface, sail_seam, (mx, sy_s), (mx + sw_v - _s(1), sy_s), 1)
            # Yards (beams at top and bottom of each sail)
            pygame.draw.line(surface, mast_col, (mx - _s(8), st), (mx + sw_v + _s(6), st), _s(2))
            pygame.draw.line(surface, mast_col, (mx - _s(5), sb), (mx + sw_v + _s(2), sb), _s(2))

        # Topsail (small, above main sails, on topmast)
        ts_top = topmast_top + _s(4)
        ts_bot = mast_top + _s(2)
        ts_w = _s(35) if mi < 2 else _s(24)
        ts_pts = [(mx - 1, ts_top), (mx + ts_w, ts_top + _s(2)),
                  (mx + ts_w - _s(2), ts_bot - _s(2)), (mx - 1, ts_bot)]
        pygame.draw.polygon(surface, sail_base, ts_pts)
        pygame.draw.polygon(surface, sail_seam, ts_pts, 1)
        pygame.draw.line(surface, mast_col, (mx - _s(5), ts_top), (mx + ts_w + _s(4), ts_top), _s(2))

        # Mizzen lateen sail (triangular, only on mizzenmast)
        if mi == 2:
            lat_pts = [(mx, mast_top + _s(10)), (mx + _s(45), deck_y - _s(30)),
                       (mx, deck_y - _s(10))]
            lat_col = (sail_base[0] - 8, sail_base[1] - 6, sail_base[2])
            pygame.draw.polygon(surface, lat_col, lat_pts)
            pygame.draw.polygon(surface, sail_seam, lat_pts, 1)
            # Lateen yard (diagonal beam)
            pygame.draw.line(surface, mast_col, (mx - _s(4), deck_y - _s(8)),
                             (mx + _s(4), mast_top + _s(6)), _s(2))

    # ── Rigging (stays, shrouds, ratlines) ──
    for mi, (mx, mh) in enumerate(mast_positions):
        mast_top = deck_y - mh
        topmast_top = mast_top - _s(30)
        # Forestay
        pygame.draw.line(surface, rig_col, (mx, topmast_top), (bow_x + _s(10), deck_y - _s(4)), 1)
        # Backstay
        pygame.draw.line(surface, rig_col, (mx, topmast_top),
                         (sc_base_x + sc1_w, sc1_rect.top + _s(4)), 1)
        # Shrouds (3 ropes each side fanning down)
        shroud_base_y = deck_y + _s(2)
        shroud_top_y = mast_top + _s(8)
        for sri in range(3):
            spread = _s(8 + sri * 10)
            pygame.draw.line(surface, rig_col,
                             (mx, shroud_top_y + sri * _s(3)),
                             (mx - spread, shroud_base_y), 1)
        # Ratlines (horizontal rope ladders on shrouds)
        for rti in range(4):
            rt_y = shroud_top_y + int((shroud_base_y - shroud_top_y) * (rti + 1) / 5)
            rt_x_inner = mx - _s(4 + rti * 5)
            rt_x_outer = mx - _s(8 + rti * 10)
            pygame.draw.line(surface, rig_col, (rt_x_inner, rt_y), (rt_x_outer, rt_y), 1)

    # ── Flags ──
    # Main flag at mainmast top
    flag_x_v = mast_positions[0][0]
    flag_y_v = deck_y - mast_positions[0][1] - _s(30)
    flag_col = (160, 28, 28)
    flag_w, flag_h = _s(24), _s(14)
    # Waving flag shape
    flag_pts_v = [
        (flag_x_v, flag_y_v),
        (flag_x_v + flag_w, flag_y_v + _s(3)),
        (flag_x_v + flag_w - _s(2), flag_y_v + flag_h - _s(2)),
        (flag_x_v, flag_y_v + flag_h)
    ]
    pygame.draw.polygon(surface, flag_col, flag_pts_v)
    # Cross or emblem on flag
    fcx = flag_x_v + flag_w // 2
    fcy = flag_y_v + flag_h // 2
    pygame.draw.line(surface, (220, 200, 60), (fcx - _s(4), fcy), (fcx + _s(4), fcy), 2)
    pygame.draw.line(surface, (220, 200, 60), (fcx, fcy - _s(3)), (fcx, fcy + _s(3)), 2)
    pygame.draw.polygon(surface, (100, 18, 18), flag_pts_v, 1)
    # Pennant at foremast
    pen_x = mast_positions[1][0]
    pen_y = deck_y - mast_positions[1][1] - _s(30)
    pen_pts = [(pen_x, pen_y), (pen_x + _s(30), pen_y + _s(4)),
               (pen_x + _s(28), pen_y + _s(6)), (pen_x, pen_y + _s(5))]
    pygame.draw.polygon(surface, (30, 50, 140), pen_pts)
    pygame.draw.polygon(surface, (20, 35, 100), pen_pts, 1)

    # ── Anchor (hanging from bow) ──
    anch_x = bow_x - _s(6)
    anch_y = y + _s(14)
    pygame.draw.line(surface, (55, 50, 45), (anch_x, deck_y + _s(4)), (anch_x, anch_y), 1)  # chain
    pygame.draw.line(surface, (60, 55, 48), (anch_x, anch_y), (anch_x, anch_y + _s(10)), 2)  # shank
    pygame.draw.line(surface, (60, 55, 48), (anch_x - _s(6), anch_y + _s(10)),
                     (anch_x + _s(6), anch_y + _s(10)), 2)  # arms
    pygame.draw.line(surface, (60, 55, 48), (anch_x - _s(6), anch_y + _s(10)),
                     (anch_x - _s(4), anch_y + _s(14)), 2)  # fluke L
    pygame.draw.line(surface, (60, 55, 48), (anch_x + _s(6), anch_y + _s(10)),
                     (anch_x + _s(4), anch_y + _s(14)), 2)  # fluke R

    total_h = mast_positions[0][1] + _s(30) + hull_h
    return pygame.Rect(stern_x, deck_y - mast_positions[0][1] - _s(30),
                       bow_x - stern_x + _s(55), total_h)


def draw_cemetery_gate(surface: pygame.Surface, x: int, y: int) -> pygame.Rect:
    """Draw an iron cemetery gate with stone pillars."""
    # Left pillar
    for px_g, sign in [(x - 50, -1), (x + 50, 1)]:
        pillar = pygame.Rect(px_g - 10, y - 50, 20, 50)
        pygame.draw.rect(surface, (70, 68, 65), pillar)
        pygame.draw.rect(surface, (45, 43, 40), pillar, 2)
        # Cap
        pygame.draw.rect(surface, (80, 78, 72), (px_g - 12, y - 54, 24, 8))
        # Cross on top
        pygame.draw.line(surface, (55, 52, 48), (px_g, y - 54), (px_g, y - 66), 2)
        pygame.draw.line(surface, (55, 52, 48), (px_g - 5, y - 60), (px_g + 5, y - 60), 2)
    # Gate bars
    for gx in range(x - 38, x + 40, 8):
        pygame.draw.line(surface, (50, 48, 45), (gx, y - 42), (gx, y), 2)
    # Top rail
    pygame.draw.line(surface, (55, 52, 48), (x - 40, y - 42), (x + 40, y - 42), 3)
    # Arch
    pygame.draw.arc(surface, (55, 52, 48),
                    (x - 40, y - 58, 80, 32), 0, math.pi, 3)
    return pygame.Rect(x - 52, y - 50, 104, 50)


def draw_iron_fence(surface: pygame.Surface, x: int, y: int, length: int = 100) -> None:
    """Draw a decorative iron fence section (no collision)."""
    # Bottom rail
    pygame.draw.line(surface, (50, 48, 45), (x, y), (x + length, y), 2)
    # Top rail
    pygame.draw.line(surface, (55, 52, 48), (x, y - 28), (x + length, y - 28), 2)
    # Vertical bars
    for fx in range(x + 6, x + length, 10):
        pygame.draw.line(surface, (52, 50, 46), (fx, y), (fx, y - 28), 2)
        # Spear tip
        pygame.draw.polygon(surface, (58, 55, 50),
                            [(fx - 2, y - 28), (fx + 2, y - 28), (fx, y - 34)])


def draw_iron_fence_vertical(surface: pygame.Surface, x: int, y: int, length: int = 100) -> None:
    """Draw a decorative iron fence section rotated vertical (no collision)."""
    tmp_w = max(24, int(length) + 14)
    tmp_h = 52
    tmp = pygame.Surface((tmp_w, tmp_h), pygame.SRCALPHA)
    draw_iron_fence(tmp, 7, tmp_h - 10, length)
    rot = pygame.transform.rotate(tmp, 90)
    surface.blit(rot, (x - rot.get_width() // 2, y - rot.get_height() // 2))


def draw_cemetery_mausoleum(surface: pygame.Surface, x: int, y: int, seed: int = 0) -> pygame.Rect:
    """Small stone mausoleum/crypt suitable for the town cemetery."""
    rng = random.Random(seed + x * 3 + y * 11 + 9107)
    w, h = 132, 96
    rect = pygame.Rect(x - w // 2, y - h, w, h)

    # Shadow
    sh = pygame.Surface((w + 24, 16), pygame.SRCALPHA)
    pygame.draw.ellipse(sh, (0, 0, 0, 36), sh.get_rect())
    surface.blit(sh, (x - sh.get_width() // 2, y - 6))

    # Stone body gradient
    body = pygame.Rect(rect.left + 10, rect.top + 18, rect.width - 20, rect.height - 22)
    for row in range(body.height):
        t = row / max(1, body.height - 1)
        shade = int(78 - 18 * t) + rng.randint(-2, 2)
        pygame.draw.line(surface, (shade, shade - 2, shade - 6), (body.left, body.top + row), (body.right, body.top + row))
    pygame.draw.rect(surface, (36, 34, 32), body, 2)

    # Ashlar blocks
    for by in range(body.top + 4, body.bottom - 6, 12):
        off = 10 if ((by - body.top) // 12) % 2 else 0
        for bx in range(body.left + 4 + off, body.right - 10, 22):
            bw = min(20, body.right - bx - 4)
            sv = 70 + rng.randint(-6, 10)
            pygame.draw.rect(surface, (sv, sv - 2, sv - 6), (bx, by, bw, 9), border_radius=1)
            pygame.draw.rect(surface, (44, 42, 40), (bx, by, bw, 9), 1, border_radius=1)

    # Pediment roof
    roof = [(rect.left + 6, body.top), (rect.right - 6, body.top), (x, rect.top + 2)]
    pygame.draw.polygon(surface, (66, 64, 62), roof)
    pygame.draw.polygon(surface, (28, 26, 24), roof, 2)
    # Roof chips / weathering
    for _ in range(10):
        rx = rng.randint(rect.left + 10, rect.right - 10)
        ry = rng.randint(rect.top + 6, body.top - 4)
        pygame.draw.circle(surface, (54, 52, 50), (rx, ry), 1)

    # Door (iron) with cross relief
    door_w, door_h = 30, 46
    door = pygame.Rect(x - door_w // 2, y - door_h - 8, door_w, door_h)
    pygame.draw.rect(surface, (26, 24, 24), door, border_radius=2)
    pygame.draw.rect(surface, (50, 48, 46), door, 2, border_radius=2)
    pygame.draw.line(surface, (76, 72, 66), (door.centerx, door.top + 8), (door.centerx, door.bottom - 8), 2)
    pygame.draw.line(surface, (76, 72, 66), (door.left + 8, door.centery), (door.right - 8, door.centery), 2)
    # Hinges + handle
    for hy in (door.top + 10, door.bottom - 12):
        pygame.draw.rect(surface, (54, 52, 50), (door.left - 2, hy, 10, 4), border_radius=1)
    pygame.draw.circle(surface, (88, 82, 74), (door.right - 8, door.centery + 2), 2)

    # Small front steps
    step1 = pygame.Rect(door.left - 10, y - 10, door.width + 20, 8)
    step2 = pygame.Rect(door.left - 14, y - 2, door.width + 28, 8)
    pygame.draw.rect(surface, (64, 62, 60), step1, border_radius=2)
    pygame.draw.rect(surface, (46, 44, 42), step1, 1, border_radius=2)
    pygame.draw.rect(surface, (60, 58, 56), step2, border_radius=2)
    pygame.draw.rect(surface, (42, 40, 38), step2, 1, border_radius=2)

    # Candle offerings (tiny) at steps
    if rng.random() > 0.3:
        for _ in range(rng.randint(2, 4)):
            cx = x + rng.randint(-14, 14)
            cy = y - 6 + rng.randint(-2, 2)
            pygame.draw.rect(surface, (222, 208, 176), (cx, cy - 4, 2, 4))
            pygame.draw.circle(surface, (255, 170, 60), (cx + 1, cy - 6), 2)

    return pygame.Rect(x - 46, y - 18, 92, 18)


def draw_harbour_water(surface: pygame.Surface, rect: pygame.Rect, seed: int = 0) -> None:
    """Draw a harbour water area with depth gradient, caustics, reflections, and foam."""
    rng = random.Random(seed + 5001)
    # ── Water surface (render to temp surface for effects) ──
    water = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)

    # Deep water gradient with subtle horizontal color shifts
    for row in range(rect.height):
        t = row / max(1, rect.height - 1)
        r = int(18 + 16 * t)
        g = int(36 + 24 * t)
        b = int(72 + 30 * t)
        pygame.draw.line(water, (r, g, b), (0, row), (rect.width, row))

    # ── Caustic light patterns (shimmering light on water floor) ──
    for _ in range(rect.width * rect.height // 300):
        cx = rng.randint(4, rect.width - 4)
        cy = rng.randint(4, rect.height - 4)
        cw = rng.randint(6, 18)
        ch = rng.randint(3, 8)
        ca = rng.randint(12, 35)
        # Depth-dependent: brighter caustics in shallow water (near shore)
        depth_factor = 1.0 - min(1.0, cx / rect.width)
        ca = int(ca * (0.5 + 0.5 * depth_factor))
        caus = pygame.Surface((cw, ch), pygame.SRCALPHA)
        caus.fill((100, 180, 220, ca))
        water.blit(caus, (cx, cy))

    # ── Ripple rings (circular disturbance patterns) ──
    for _ in range(rng.randint(8, 14)):
        rx = rng.randint(30, rect.width - 30)
        ry = rng.randint(30, rect.height - 30)
        rr = rng.randint(8, 22)
        ra = rng.randint(18, 40)
        ring = pygame.Surface((rr * 2, rr * 2), pygame.SRCALPHA)
        pygame.draw.circle(ring, (130, 180, 210, ra), (rr, rr), rr, 1)
        if rr > 10:
            pygame.draw.circle(ring, (120, 170, 200, ra // 2), (rr, rr), rr - 4, 1)
        water.blit(ring, (rx - rr, ry - rr))

    # ── Larger wave crests with curvature ──
    for _ in range(rect.width * rect.height // 500):
        wx = rng.randint(6, rect.width - 6)
        wy = rng.randint(3, rect.height - 3)
        wl = rng.randint(16, 44)
        wh = rng.randint(2, 4)
        alpha = rng.randint(30, 65)
        # Slight curve via multiple offset segments
        wave_s = pygame.Surface((wl, wh + 2), pygame.SRCALPHA)
        for wi in range(0, wl, 3):
            yo = int(math.sin(wi * 0.3 + rng.random() * 2) * 1.5)
            pygame.draw.rect(wave_s, (150, 190, 220, alpha), (wi, yo + 1, 3, wh))
        water.blit(wave_s, (wx, wy))

    # ── Specular highlights (bright sun reflections) ──
    for _ in range(rng.randint(15, 30)):
        sx = rng.randint(rect.width // 4, rect.width * 3 // 4)
        sy = rng.randint(10, rect.height - 10)
        sw = rng.randint(4, 12)
        sh = rng.randint(2, 5)
        sa = rng.randint(40, 80)
        spec = pygame.Surface((sw, sh), pygame.SRCALPHA)
        pygame.draw.ellipse(spec, (220, 240, 255, sa), spec.get_rect())
        water.blit(spec, (sx, sy))

    # ── Dark depth patches (deep spots) ──
    for _ in range(rng.randint(6, 12)):
        dx = rng.randint(rect.width // 3, rect.width - 20)
        dy = rng.randint(20, rect.height - 20)
        dw = rng.randint(30, 80)
        dh = rng.randint(15, 40)
        da = rng.randint(15, 35)
        deep = pygame.Surface((dw, dh), pygame.SRCALPHA)
        pygame.draw.ellipse(deep, (8, 18, 40, da), deep.get_rect())
        water.blit(deep, (dx, dy))

    surface.blit(water, rect.topleft)

    # ── Shore edge (sandy gradient from land into water) ──
    shore_w = 30
    shore = pygame.Surface((shore_w, rect.height), pygame.SRCALPHA)
    for i in range(shore_w):
        alpha = int(180 * (1.0 - i / shore_w) ** 1.5)
        pygame.draw.line(shore, (78, 72, 58, alpha), (i, 0), (i, rect.height))
    surface.blit(shore, (rect.left - shore_w, rect.top))

    # ── Foam at shore (more detailed, layered) ──
    for fy in range(rect.top, rect.bottom, rng.randint(6, 14)):
        # Multiple foam layers
        for fl in range(rng.randint(1, 3)):
            fw = rng.randint(10, 28)
            fh = rng.randint(2, 5)
            fa = rng.randint(50, 110)
            foam_s = pygame.Surface((fw, fh), pygame.SRCALPHA)
            pygame.draw.ellipse(foam_s, (200, 220, 230, fa), foam_s.get_rect())
            surface.blit(foam_s, (rect.left - 8 + fl * 6 + rng.randint(-3, 3), fy + rng.randint(-2, 2)))

    # ── Top/bottom water edges ──
    for ex in range(rect.left, rect.right, rng.randint(8, 16)):
        ew = rng.randint(6, 16)
        ea = rng.randint(30, 70)
        edge = pygame.Surface((ew, 4), pygame.SRCALPHA)
        edge.fill((90, 120, 140, ea))
        surface.blit(edge, (ex, rect.top - 2))
        surface.blit(edge, (ex, rect.bottom - 2))


# Exported by build_town_scene for runtime systems (smoke VFX, debug renders):
# real chimney-top positions of the placed houses, and the reserved civic
# landmark footprints. Refreshed on every (re)build.
_TOWN_CHIMNEY_TOPS: list = []
_TOWN_LANDMARK_RECTS: list = []


def _draw_pennant_string(surface: pygame.Surface, x0: int, y0: int, x1: int, y1: int, seed: int = 0) -> None:
    """Festive bunting: a sagging cord with alternating triangular pennants."""
    rng = random.Random(seed * 911 + 3)
    L = max(1.0, math.hypot(x1 - x0, y1 - y0))
    sag = min(26.0, L * 0.08)
    n = max(8, int(L / 14))
    pts = []
    for i in range(n + 1):
        t = i / n
        pts.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t + math.sin(t * math.pi) * sag))
    pygame.draw.lines(surface, (188, 178, 158), False, [(int(a), int(b)) for a, b in pts], 1)
    cols = [(170, 44, 38), (196, 160, 62), (62, 96, 124), (104, 124, 60), (172, 158, 138)]
    for i in range(1, n, 2):
        px, py = int(pts[i][0]), int(pts[i][1])
        c = cols[(i // 2 + seed) % len(cols)]
        ph = rng.randint(9, 12)
        pygame.draw.polygon(surface, c, [(px - 5, py), (px + 5, py), (px, py + ph)])
        pygame.draw.polygon(surface, (max(0, c[0] - 50), max(0, c[1] - 50), max(0, c[2] - 44)),
                            [(px - 5, py), (px + 5, py), (px, py + ph)], 1)
        pygame.draw.line(surface, (230, 224, 208), (px - 5, py), (px + 5, py), 1)


def _draw_bunting_span(surface: pygame.Surface, x0: int, x1: int, y: int, seed: int = 0) -> None:
    """Two slim poles with a pennant string sagging between their tops."""
    for px in (x0, x1):
        sh = pygame.Surface((16, 7), pygame.SRCALPHA)
        pygame.draw.ellipse(sh, (10, 8, 6, 60), (0, 0, 16, 7))
        surface.blit(sh, (px - 7, y - 3))
        for ci in range(4):
            v = 96 - ci * 12
            pygame.draw.line(surface, (v, int(v * 0.78), int(v * 0.54)), (px + ci - 2, y), (px + ci - 2, y - 74), 1)
        pygame.draw.circle(surface, (196, 168, 84), (px, y - 76), 3)
        pygame.draw.circle(surface, (140, 116, 52), (px, y - 76), 3, 1)
    _draw_pennant_string(surface, x0, y - 72, x1, y - 72, seed=seed)


def _draw_small_bird(surface: pygame.Surface, x: int, y: int, kind: str = "pigeon", seed: int = 0) -> None:
    """Tiny ambient bird (pigeon = slate, gull = white), perched or pecking.
    (x, y) is its feet/ground contact point."""
    rng = random.Random(seed * 577 + x * 7 + y)
    if kind == "gull":
        body, wing, beak = (228, 228, 224), (176, 182, 188), (204, 150, 48)
    else:
        body, wing, beak = (124, 126, 134), (96, 98, 108), (70, 60, 48)
    f = -1 if rng.random() < 0.5 else 1
    pecking = rng.random() < 0.4
    sh = pygame.Surface((12, 5), pygame.SRCALPHA)
    pygame.draw.ellipse(sh, (10, 8, 6, 50), (0, 0, 12, 5))
    surface.blit(sh, (x - 6, y - 2))
    pygame.draw.line(surface, (60, 52, 40), (x - 1, y - 3), (x - 1, y), 1)   # legs
    pygame.draw.line(surface, (60, 52, 40), (x + 2, y - 3), (x + 2, y), 1)
    pygame.draw.line(surface, wing, (x - f * 4, y - 7), (x - f * 7, y - 6), 2)  # tail
    pygame.draw.ellipse(surface, body, (x - 4, y - 9, 9, 7))                 # body
    pygame.draw.ellipse(surface, wing, (x - 3, y - 8, 6, 4))                 # folded wing
    hx = x + f * 4
    hy = y - 10 + (3 if pecking else 0)
    pygame.draw.circle(surface, body, (hx, hy), 2)
    pygame.draw.line(surface, beak, (hx + f * 2, hy), (hx + f * 4, hy + (2 if pecking else 0)), 1)
    surface.set_at((hx + (1 if f > 0 else -1), hy - 1), (20, 18, 16))


# ─────────────────────────────────────────────────────────────────────────────
# PHASE-2 CIVIC LANDMARKS — curtain wall, palisades, town hall, windmill,
# granary, washhouse and wayside shrines. All baked once at town build.
# Light convention: sun upper-left, cast shadows fall lower-right.
# ─────────────────────────────────────────────────────────────────────────────


def draw_stone_curtain_wall(surface: pygame.Surface, x0: int, x1: int, gy: int, seed: int = 0) -> None:
    """Crenellated stone curtain wall run along ground line `gy` (face spans
    roughly gy-98..gy). Matches the south gate towers' masonry: staggered
    ashlar courses, buttresses with sloped feet, arrow slits, weathering
    streaks and moss at the foot."""
    _hh = _house_hash
    rng = random.Random(seed * 7919 + 5)
    if x1 - x0 < 60:
        return
    face_h = 84
    top_y = gy - face_h
    # soft contact shadow at the foot
    sh = pygame.Surface((x1 - x0, 16), pygame.SRCALPHA)
    pygame.draw.rect(sh, (10, 8, 6, 56), (0, 0, x1 - x0, 16))
    surface.blit(sh, (x0, gy - 4))
    # stone face, darker toward the ground
    for row in range(face_h):
        t = row / (face_h - 1)
        v = int(76 - 22 * t) + _hh(row * 11 + seed, 37) % 5
        pygame.draw.line(surface, (v, v - 5, v - 11), (x0, top_y + row), (x1, top_y + row))
    # staggered ashlar blocks
    for by in range(top_y + 6, gy - 8, 14):
        off = 11 if ((by - top_y) // 14) % 2 else 0
        for bx in range(x0 + off, x1 - 8, 22):
            bw = min(20, x1 - bx - 2)
            sv = 58 + _hh(bx * 5 + by * 3, 53) % 12
            pygame.draw.rect(surface, (sv, sv - 5, sv - 11), (bx, by, bw, 12))
            pygame.draw.rect(surface, (38, 34, 28), (bx, by, bw, 12), 1)
    # wall-walk lip + crenellations
    pygame.draw.rect(surface, (86, 80, 72), (x0, top_y - 4, x1 - x0, 7))
    pygame.draw.rect(surface, (44, 40, 34), (x0, top_y - 4, x1 - x0, 7), 1)
    for mx in range(x0 + 4, x1 - 14, 26):
        merlon = pygame.Rect(mx, top_y - 18, 14, 16)
        pygame.draw.rect(surface, (78, 72, 64), merlon)
        pygame.draw.rect(surface, (98, 92, 82), (mx, top_y - 18, 14, 3))
        pygame.draw.rect(surface, (40, 36, 30), merlon, 1)
    # buttresses with sloped feet
    for bx in range(x0 + 140, x1 - 70, 280):
        bw = 26
        for row in range(face_h + 8):
            t = row / (face_h + 7)
            v = int(88 - 26 * t)
            pygame.draw.line(surface, (v, v - 4, v - 10),
                             (bx, top_y - 8 + row), (bx + bw, top_y - 8 + row))
        pygame.draw.rect(surface, (40, 36, 30), (bx, top_y - 8, bw + 1, face_h + 8), 1)
        pygame.draw.line(surface, (104, 98, 88), (bx, top_y - 8), (bx, gy - 2), 1)
        pygame.draw.polygon(surface, (72, 66, 58),
                            [(bx - 5, gy), (bx + bw + 5, gy), (bx + bw, gy - 14), (bx, gy - 14)])
        pygame.draw.polygon(surface, (38, 34, 28),
                            [(bx - 5, gy), (bx + bw + 5, gy), (bx + bw, gy - 14), (bx, gy - 14)], 1)
    # arrow slits midway between buttresses
    for sx in range(x0 + 70, x1 - 40, 280):
        pygame.draw.rect(surface, (12, 10, 8), (sx, top_y + 22, 5, 20), border_radius=2)
        pygame.draw.rect(surface, (52, 48, 42), (sx - 1, top_y + 21, 7, 22), 1, border_radius=2)
    # weathering streaks + moss at the foot
    for _ in range(max(4, (x1 - x0) // 60)):
        wx = rng.randint(x0 + 6, x1 - 6)
        wy = top_y + rng.randint(4, 36)
        c = (98, 94, 86) if rng.random() < 0.45 else (44, 40, 34)
        pygame.draw.line(surface, c, (wx, wy), (wx, wy + rng.randint(8, 26)), 1)
    for _ in range(max(4, (x1 - x0) // 36)):
        mx = rng.randint(x0 + 4, x1 - 12)
        pygame.draw.ellipse(surface, (52, 74, 38), (mx, gy - rng.randint(4, 12), rng.randint(4, 10), 4))


def _draw_palisade_watchpost(surface: pygame.Surface, x: int, y: int, seed: int = 0) -> None:
    """Small roofed watch platform on stilts straddling the palisade line."""
    sh = pygame.Surface((74, 26), pygame.SRCALPHA)
    pygame.draw.ellipse(sh, (10, 8, 6, 54), (0, 0, 74, 26))
    surface.blit(sh, (x - 30, y + 34))
    # stilt legs (rear pair shorter — they sit further "up" the view)
    for lx, ly in ((x - 22, y + 42), (x + 22, y + 42), (x - 15, y + 28), (x + 15, y + 28)):
        pygame.draw.line(surface, (38, 28, 17), (lx + 2, y - 8), (lx + 2, ly), 4)
        pygame.draw.line(surface, (86, 66, 42), (lx, y - 10), (lx, ly - 2), 2)
    # platform deck
    deck = pygame.Rect(x - 30, y - 24, 60, 18)
    pygame.draw.rect(surface, (98, 78, 50), deck)
    for px in range(deck.left + 5, deck.right - 2, 7):
        pygame.draw.line(surface, (62, 47, 28), (px, deck.top + 1), (px, deck.bottom - 2), 1)
    pygame.draw.line(surface, (128, 104, 70), (deck.left + 1, deck.top + 1), (deck.right - 2, deck.top + 1), 1)
    pygame.draw.rect(surface, (50, 38, 22), deck, 1)
    # railing
    pygame.draw.line(surface, (106, 84, 54), (deck.left + 2, deck.top - 11), (deck.right - 2, deck.top - 11), 2)
    for rx in range(deck.left + 4, deck.right, 12):
        pygame.draw.line(surface, (76, 58, 36), (rx, deck.top - 10), (rx, deck.top), 1)
    # corner posts + small pyramidal roof
    for cx2 in (deck.left + 6, deck.right - 6):
        pygame.draw.line(surface, (58, 44, 26), (cx2, deck.top - 8), (cx2, deck.top - 36), 2)
    roof = [(deck.left - 8, deck.top - 34), (deck.right + 8, deck.top - 34), (x, deck.top - 56)]
    pygame.draw.polygon(surface, (70, 52, 30), roof)
    pygame.draw.polygon(surface, (98, 78, 48),
                        [(deck.left - 8, deck.top - 34), (x, deck.top - 56), (x + 3, deck.top - 51), (deck.left - 2, deck.top - 32)])
    pygame.draw.polygon(surface, (40, 30, 18), roof, 1)
    # brazier coals glowing on the deck
    pygame.draw.circle(surface, (96, 60, 30), (x + 18, deck.top - 3), 4)
    pygame.draw.circle(surface, (216, 124, 42), (x + 18, deck.top - 4), 3)
    pygame.draw.circle(surface, (255, 206, 96), (x + 18, deck.top - 5), 1)


def draw_palisade_v(surface: pygame.Surface, x: int, y0: int, y1: int, seed: int = 0) -> None:
    """North-south running palisade of sharpened logs seen edge-on: a column
    of round end-grain log tops with lashed rails on the inside face and a
    roofed watch platform breaking up long runs."""
    rng = random.Random(seed * 6271 + 3)
    if y1 - y0 < 60:
        return
    # ground shadow strip to the right of the line
    sh = pygame.Surface((16, y1 - y0), pygame.SRCALPHA)
    pygame.draw.rect(sh, (10, 8, 6, 44), (0, 0, 16, y1 - y0))
    surface.blit(sh, (x + 6, y0))
    # log tops marching down the line
    yy = y0
    while yy < y1:
        r = rng.randint(8, 11)
        tone = rng.randint(-12, 10)
        pygame.draw.rect(surface, (52 + tone, 40 + tone, 26 + max(-26, tone)),
                         (x - r + 1, yy, r * 2 - 2, 10))
        pygame.draw.circle(surface, (44, 32, 20), (x, yy), r + 1)
        pygame.draw.circle(surface, (108 + tone, 86 + tone, 56 + tone), (x, yy), r)
        pygame.draw.circle(surface, (138 + tone, 114 + tone, 78 + tone), (x - 2, yy - 2), max(2, r - 4))
        pygame.draw.circle(surface, (82 + tone, 64 + tone, 40 + tone), (x, yy), max(2, r - 2), 1)
        pygame.draw.line(surface, (70, 54, 34), (x - r + 3, yy + rng.randint(-2, 1)),
                         (x + r - 3, yy + rng.randint(-1, 2)), 1)
        yy += r + rng.randint(4, 7)
    # lashed rails pinned along the inside face
    for ry in range(y0 + 40, y1 - 60, 110):
        pygame.draw.line(surface, (58, 44, 26), (x + 9, ry), (x + 9, ry + 64), 3)
        pygame.draw.line(surface, (94, 74, 48), (x + 8, ry), (x + 8, ry + 64), 1)
    # watch platforms breaking long runs
    ty = y0 + 460
    while ty < y1 - 280:
        _draw_palisade_watchpost(surface, x, ty, seed=seed * 17 + ty)
        ty += 1150


def draw_town_hall(surface: pygame.Surface, x: int, y: int, seed: int = 0) -> pygame.Rect:
    """Civic town hall fronting the market square: arcaded stone ground
    floor, jettied timber-framed council floor, steep slate roof and a
    central clock/bell tower with a weathervane. (x, y) is the base centre;
    the hall faces south onto the square."""
    _hh = _house_hash
    rng = random.Random(seed * 4111 + 9)
    hw = 280
    g_h, t_h, r_h = 122, 108, 96
    g_top = y - g_h
    t_top = g_top - t_h
    r_top = t_top - r_h

    # cast shadow to the lower-right
    shs = pygame.Surface((hw * 2 + 90, 46), pygame.SRCALPHA)
    pygame.draw.polygon(shs, (12, 9, 7, 38), [(0, 0), (hw * 2 + 8, 0), (hw * 2 + 86, 42), (60, 42)])
    pygame.draw.polygon(shs, (12, 9, 7, 32), [(4, 0), (hw * 2 + 4, 0), (hw * 2 + 52, 24), (42, 24)])
    surface.blit(shs, (x - hw, y - 2))

    # ── stone ground floor ──
    for row in range(g_h):
        t = row / (g_h - 1)
        v = int(98 - 26 * t) + _hh(row * 7 + seed, 31) % 5
        pygame.draw.line(surface, (v, v - 4, v - 9), (x - hw, g_top + row), (x + hw, g_top + row))
    for by in range(g_top + 8, y - 12, 15):
        off = 12 if ((by - g_top) // 15) % 2 else 0
        for bx in range(x - hw + off, x + hw - 10, 24):
            sv = 84 + _hh(bx * 3 + by * 5, 47) % 11
            pygame.draw.rect(surface, (sv, sv - 4, sv - 9), (bx, by, 22, 13))
            pygame.draw.rect(surface, (56, 52, 46), (bx, by, 22, 13), 1)
    for qy in range(g_top + 4, y - 14, 18):                       # corner quoins
        for qx in (x - hw - 3, x + hw - 15):
            qo = 0 if ((qy - g_top) // 18) % 2 else 5
            pygame.draw.rect(surface, (112, 108, 100), (qx + qo, qy, 18, 16))
            pygame.draw.rect(surface, (58, 54, 48), (qx + qo, qy, 18, 16), 1)
    pygame.draw.rect(surface, (64, 60, 54), (x - hw - 4, y - 10, hw * 2 + 8, 10))   # plinth
    pygame.draw.rect(surface, (40, 37, 32), (x - hw - 4, y - 10, hw * 2 + 8, 10), 1)
    for _ in range(46):                                            # rising-damp grime
        gx2 = rng.randint(x - hw + 4, x + hw - 4)
        pygame.draw.line(surface, (52, 49, 44), (gx2, y - 12 - rng.randint(0, 10)), (gx2, y - 11), 1)

    # ── arched windows flanking the door (warm-lit, leaded) ──
    for wx in (x - 198, x - 118, x + 118, x + 198):
        ww, wh = 38, 52
        w_top = y - 102
        pygame.draw.rect(surface, (70, 66, 58), (wx - ww // 2 - 4, w_top - 4, ww + 8, wh + 6))
        pygame.draw.circle(surface, (70, 66, 58), (wx, w_top), ww // 2 + 4)
        for row in range(wh):
            t = row / (wh - 1)
            pygame.draw.line(surface, (216 - int(58 * t), 168 - int(52 * t), 92 - int(30 * t)),
                             (wx - ww // 2, w_top + row), (wx + ww // 2 - 1, w_top + row))
        pygame.draw.circle(surface, (224, 178, 100), (wx, w_top), ww // 2)
        pygame.draw.circle(surface, (255, 232, 160), (wx - 5, w_top - 5), 5)
        for mx in range(wx - ww // 2 + 6, wx + ww // 2, 8):        # leading
            pygame.draw.line(surface, (60, 50, 38), (mx, w_top - ww // 2), (mx, w_top + wh - 2), 1)
        for my in range(w_top + 2, w_top + wh - 2, 9):
            pygame.draw.line(surface, (60, 50, 38), (wx - ww // 2 + 1, my), (wx + ww // 2 - 2, my), 1)
        pygame.draw.circle(surface, (48, 44, 38), (wx, w_top), ww // 2 + 1, 2)
        pygame.draw.rect(surface, (48, 44, 38), (wx - ww // 2 - 1, w_top, ww + 2, wh + 1), 2)
        pygame.draw.rect(surface, (118, 114, 104), (wx - ww // 2 - 5, w_top + wh, ww + 10, 4))  # sill

    # ── arched double door with stone steps ──
    d_w, d_h = 76, 84
    d_x = x - d_w // 2
    d_top = y - d_h
    for si, sw2 in enumerate((d_w + 48, d_w + 26)):                # steps
        sy2 = y - si * 8
        pygame.draw.rect(surface, (106, 102, 94), (x - sw2 // 2, sy2 - 8, sw2, 8))
        pygame.draw.rect(surface, (134, 130, 120), (x - sw2 // 2, sy2 - 8, sw2, 2))
        pygame.draw.rect(surface, (52, 48, 42), (x - sw2 // 2, sy2 - 8, sw2, 8), 1)
    pygame.draw.rect(surface, (120, 116, 106), (d_x - 12, d_top - 8, d_w + 24, d_h + 8))   # surround
    pygame.draw.circle(surface, (120, 116, 106), (x, d_top), d_w // 2 + 12)
    # door leaves: dark oak gradient under an arched head
    pygame.draw.circle(surface, (38, 28, 18), (x, d_top), d_w // 2)
    for row in range(d_h):
        v = 44 - int(16 * row / d_h)
        pygame.draw.line(surface, (v + 6, v - 2, max(0, v - 12)), (d_x, d_top + row), (d_x + d_w - 1, d_top + row))
    for px2 in range(d_x + 8, d_x + d_w - 4, 11):                  # plank seams
        pygame.draw.line(surface, (22, 15, 9), (px2, d_top - 22), (px2, y - 10), 1)
    pygame.draw.line(surface, (16, 11, 7), (x, d_top - d_w // 2 + 4), (x, y - 10), 2)      # centre part
    for hy2 in (d_top + 14, d_top + 48):                           # iron strap hinges
        for sgn in (-1, 1):
            pygame.draw.line(surface, (74, 72, 68), (x + sgn * 6, hy2), (x + sgn * (d_w // 2 - 4), hy2 + 3), 3)
            pygame.draw.circle(surface, (94, 92, 88), (x + sgn * (d_w // 2 - 8), hy2 + 2), 2)
    for sgn in (-1, 1):                                            # ring handles
        pygame.draw.circle(surface, (88, 86, 82), (x + sgn * 10, d_top + 38), 4, 2)
    # voussoirs over the arch
    for ai in range(7):
        aa = math.pi + ai * (math.pi / 6.0)
        pygame.draw.line(surface, (62, 58, 52),
                         (x + int(math.cos(aa) * (d_w // 2 + 2)), d_top + int(math.sin(aa) * (d_w // 2 + 2))),
                         (x + int(math.cos(aa) * (d_w // 2 + 11)), d_top + int(math.sin(aa) * (d_w // 2 + 11))), 2)
    pygame.draw.circle(surface, (50, 46, 40), (x, d_top), d_w // 2 + 1, 2)
    # crest shield above the door
    sh_pts = [(x - 11, d_top - 56), (x + 11, d_top - 56), (x + 11, d_top - 42), (x, d_top - 32), (x - 11, d_top - 42)]
    pygame.draw.polygon(surface, (142, 36, 30), sh_pts)
    pygame.draw.polygon(surface, (196, 158, 60), sh_pts, 2)
    pygame.draw.line(surface, (196, 158, 60), (x - 8, d_top - 49), (x + 8, d_top - 49), 2)
    # lanterns flanking the door
    for sgn in (-1, 1):
        lx2 = x + sgn * (d_w // 2 + 24)
        pygame.draw.line(surface, (56, 52, 46), (lx2, d_top - 12), (lx2, d_top - 2), 2)
        pygame.draw.rect(surface, (40, 36, 30), (lx2 - 4, d_top - 2, 8, 12), 1)
        pygame.draw.rect(surface, (255, 196, 92), (lx2 - 2, d_top, 5, 8))
        glow = pygame.Surface((26, 26), pygame.SRCALPHA)
        pygame.draw.circle(glow, (255, 190, 90, 38), (13, 13), 13)
        surface.blit(glow, (lx2 - 13, d_top - 8))

    # ── jetty beam + timber-framed council floor ──
    pygame.draw.rect(surface, (54, 40, 26), (x - hw - 14, g_top - 8, hw * 2 + 28, 12))
    pygame.draw.rect(surface, (84, 64, 42), (x - hw - 14, g_top - 8, hw * 2 + 28, 3))
    pygame.draw.rect(surface, (30, 22, 14), (x - hw - 14, g_top - 8, hw * 2 + 28, 12), 1)
    for jx in range(x - hw - 6, x + hw + 6, 24):                   # jetty bracket ends
        pygame.draw.rect(surface, (66, 50, 32), (jx, g_top + 2, 8, 6))
        pygame.draw.rect(surface, (34, 25, 16), (jx, g_top + 2, 8, 6), 1)
    thw = hw + 14
    for row in range(t_h - 8):                                     # plaster field
        t = row / (t_h - 9)
        v = int(208 - 34 * t)
        pygame.draw.line(surface, (v, v - 10, v - 38), (x - thw, t_top + row), (x + thw, t_top + row))
    for _ in range(80):                                            # plaster mottling
        mx2 = rng.randint(x - thw + 4, x + thw - 4)
        my2 = t_top + rng.randint(4, t_h - 14)
        mv = rng.randint(-14, 8)
        pygame.draw.ellipse(surface, (196 + mv, 186 + mv, 152 + mv), (mx2, my2, rng.randint(3, 9), rng.randint(2, 5)))
    timber = (58, 42, 26)
    timber_lt = (88, 68, 44)
    pygame.draw.rect(surface, timber, (x - thw, t_top, thw * 2, 7))             # head beam
    pygame.draw.rect(surface, timber, (x - thw, g_top - 16, thw * 2, 8))        # sill beam
    n_bays = 8
    for bi in range(n_bays + 1):                                   # studs
        sx2 = x - thw + int(bi * (thw * 2) / n_bays)
        pygame.draw.rect(surface, timber, (sx2 - 3, t_top, 7, t_h - 8))
        pygame.draw.line(surface, timber_lt, (sx2 - 3, t_top), (sx2 - 3, t_top + t_h - 9), 1)
    for sgn in (-1, 1):                                            # end-bay braces
        bx0 = x + sgn * (thw - 4)
        bx1 = x + sgn * (thw - int(thw * 2 / n_bays) + 2)
        pygame.draw.line(surface, timber, (bx0, t_top + 6), (bx1, g_top - 12), 6)
        pygame.draw.line(surface, timber_lt, (bx0, t_top + 5), (bx1, g_top - 13), 1)
    # council-chamber windows (warm-lit, mullioned)
    for wi in range(5):
        wx = x - 168 + wi * 84
        ww, wh = 44, 50
        w_top = t_top + 26
        pygame.draw.rect(surface, (44, 32, 20), (wx - ww // 2 - 3, w_top - 3, ww + 6, wh + 6))
        for row in range(wh):
            t = row / (wh - 1)
            pygame.draw.line(surface, (222 - int(64 * t), 174 - int(58 * t), 96 - int(34 * t)),
                             (wx - ww // 2, w_top + row), (wx + ww // 2 - 1, w_top + row))
        pygame.draw.circle(surface, (255, 234, 168), (wx - 8, w_top + 8), 5)
        pygame.draw.line(surface, (50, 38, 26), (wx, w_top), (wx, w_top + wh), 2)          # mullion
        pygame.draw.line(surface, (50, 38, 26), (wx - ww // 2, w_top + wh // 2), (wx + ww // 2, w_top + wh // 2), 2)
        for mx in range(wx - ww // 2 + 5, wx + ww // 2, 7):
            pygame.draw.line(surface, (96, 76, 50), (mx, w_top + 1), (mx, w_top + wh - 1), 1)
        pygame.draw.rect(surface, (40, 30, 20), (wx - ww // 2, w_top, ww, wh), 1)
        pygame.draw.rect(surface, (100, 78, 52), (wx - ww // 2 - 4, w_top + wh + 2, ww + 8, 3))
    # twin crimson banners flanking the centre window
    for sgn in (-1, 1):
        bx2 = x + sgn * 70
        pygame.draw.line(surface, (60, 56, 48), (bx2 - 9, t_top + 12), (bx2 + 9, t_top + 12), 2)
        for row in range(40):
            t = row / 39.0
            v = int(150 - 64 * t)
            wob = int(math.sin(row * 0.5 + sgn) * 1.5)
            pygame.draw.line(surface, (v, 26, 22), (bx2 - 8 + wob, t_top + 13 + row), (bx2 + 8 + wob, t_top + 13 + row))
        pygame.draw.polygon(surface, (16, 12, 12), [(bx2 - 8, t_top + 52), (bx2 + 8, t_top + 52), (bx2, t_top + 46)])
        pygame.draw.circle(surface, (212, 172, 70), (bx2, t_top + 28), 4)
        pygame.draw.circle(surface, (150, 110, 40), (bx2, t_top + 28), 4, 1)

    # ── steep slate roof (hipped) ──
    e_l, e_r = x - thw - 10, x + thw + 10
    rg_l, rg_r = x - hw + 96, x + hw - 96
    roof_pts = [(e_l, t_top + 2), (rg_l, r_top), (rg_r, r_top), (e_r, t_top + 2)]
    pygame.draw.polygon(surface, (64, 68, 78), roof_pts)
    H_r = max(1, (t_top + 2) - r_top)
    for yy in range(r_top, t_top + 2, 5):                          # slate courses
        u = (yy - r_top) / H_r
        xl = int(rg_l + (e_l - rg_l) * u)
        xr = int(rg_r + (e_r - rg_r) * u)
        pygame.draw.line(surface, (44, 48, 56), (xl, yy), (xr, yy), 1)
        pygame.draw.line(surface, (84, 90, 102), (xl, yy - 1), (xr, yy - 1), 1)
    for _ in range(60):                                            # tone-varied slates
        u = rng.uniform(0.1, 0.95)
        yy = r_top + int(H_r * u)
        xl = int(rg_l + (e_l - rg_l) * u)
        xr = int(rg_r + (e_r - rg_r) * u)
        if xr - xl < 20:
            continue
        sx3 = rng.randint(xl + 4, xr - 12)
        sv = rng.randint(-12, 14)
        pygame.draw.rect(surface, (62 + sv, 66 + sv, 76 + sv), (sx3, yy - (yy - r_top) % 5, 8, 4))
    pygame.draw.line(surface, (96, 100, 110), (rg_l, r_top - 1), (rg_r, r_top - 1), 3)     # ridge
    pygame.draw.line(surface, (38, 42, 50), (rg_l, r_top + 2), (rg_r, r_top + 2), 1)
    pygame.draw.line(surface, (38, 42, 50), (e_l, t_top + 2), (rg_l, r_top), 2)            # hips
    pygame.draw.line(surface, (38, 42, 50), (e_r, t_top + 2), (rg_r, r_top), 2)
    pygame.draw.rect(surface, (50, 38, 24), (e_l, t_top, e_r - e_l, 5))                    # eave fascia
    for di, dx2 in enumerate((x - 150, x + 150)):                  # dormers
        d_top2 = r_top + 34
        pygame.draw.rect(surface, (58, 44, 28), (dx2 - 14, d_top2, 28, 22))
        pygame.draw.rect(surface, (228, 182, 104), (dx2 - 9, d_top2 + 4, 18, 15))
        pygame.draw.line(surface, (54, 40, 28), (dx2, d_top2 + 4), (dx2, d_top2 + 18), 1)
        pygame.draw.rect(surface, (40, 30, 20), (dx2 - 9, d_top2 + 4, 18, 15), 1)
        pygame.draw.polygon(surface, (74, 78, 88), [(dx2 - 18, d_top2 + 2), (dx2 + 18, d_top2 + 2), (dx2, d_top2 - 14)])
        pygame.draw.polygon(surface, (40, 44, 52), [(dx2 - 18, d_top2 + 2), (dx2 + 18, d_top2 + 2), (dx2, d_top2 - 14)], 1)

    # ── central clock/bell tower ──
    tw2 = 44
    tower_top = r_top - 96
    for row in range(r_top + 30 - tower_top):                      # stone shaft
        t = row / max(1, r_top + 29 - tower_top)
        v = int(102 - 20 * t) + _hh(row * 13 + seed, 23) % 5
        pygame.draw.line(surface, (v, v - 4, v - 9), (x - tw2, tower_top + row), (x + tw2, tower_top + row))
    for by in range(tower_top + 4, r_top + 26, 13):
        off = 9 if ((by - tower_top) // 13) % 2 else 0
        for bx in range(x - tw2 + off, x + tw2 - 8, 18):
            pygame.draw.rect(surface, (52, 48, 42), (bx, by, 16, 11), 1)
    pygame.draw.line(surface, (122, 118, 108), (x - tw2, tower_top), (x - tw2, r_top + 30), 2)
    pygame.draw.line(surface, (44, 40, 34), (x + tw2 - 1, tower_top), (x + tw2 - 1, r_top + 30), 2)
    # bell stage: arched opening + bell
    b_top = tower_top + 10
    pygame.draw.rect(surface, (14, 11, 8), (x - 16, b_top, 32, 30))
    pygame.draw.circle(surface, (14, 11, 8), (x, b_top + 2), 16)
    pygame.draw.circle(surface, (96, 92, 84), (x, b_top + 2), 17, 2)
    pygame.draw.rect(surface, (96, 92, 84), (x - 17, b_top + 2, 2, 28))
    pygame.draw.rect(surface, (96, 92, 84), (x + 15, b_top + 2, 2, 28))
    pygame.draw.polygon(surface, (148, 122, 58), [(x - 7, b_top + 8), (x + 7, b_top + 8), (x + 9, b_top + 22), (x - 9, b_top + 22)])
    pygame.draw.line(surface, (188, 162, 88), (x - 6, b_top + 9), (x - 8, b_top + 21), 1)
    pygame.draw.circle(surface, (60, 48, 24), (x, b_top + 25), 2)
    pygame.draw.rect(surface, (96, 92, 84), (x - 18, b_top + 31, 36, 3))
    # clock face below the bell
    c_cy = b_top + 52
    pygame.draw.circle(surface, (52, 48, 42), (x, c_cy), 17)
    pygame.draw.circle(surface, (214, 198, 158), (x, c_cy), 14)
    pygame.draw.circle(surface, (176, 144, 62), (x, c_cy), 14, 2)
    for hi in range(12):
        ha = hi * math.tau / 12.0
        pygame.draw.line(surface, (74, 60, 38),
                         (x + int(math.cos(ha) * 11), c_cy + int(math.sin(ha) * 11)),
                         (x + int(math.cos(ha) * 13), c_cy + int(math.sin(ha) * 13)), 1)
    pygame.draw.line(surface, (40, 30, 18), (x, c_cy), (x + 6, c_cy - 6), 2)
    pygame.draw.line(surface, (40, 30, 18), (x, c_cy), (x - 2, c_cy - 9), 2)
    pygame.draw.circle(surface, (40, 30, 18), (x, c_cy), 2)
    # spire + weathervane
    pygame.draw.polygon(surface, (58, 62, 72), [(x - tw2 - 4, tower_top), (x + tw2 + 4, tower_top), (x, tower_top - 46)])
    pygame.draw.polygon(surface, (86, 92, 104), [(x - tw2 - 4, tower_top), (x, tower_top - 46), (x + 3, tower_top - 41), (x - tw2 + 6, tower_top - 2)])
    pygame.draw.polygon(surface, (36, 40, 48), [(x - tw2 - 4, tower_top), (x + tw2 + 4, tower_top), (x, tower_top - 46)], 1)
    pygame.draw.line(surface, (180, 156, 80), (x, tower_top - 46), (x, tower_top - 62), 2)
    pygame.draw.circle(surface, (212, 184, 96), (x, tower_top - 50), 3)
    pygame.draw.polygon(surface, (196, 168, 84), [(x, tower_top - 62), (x + 10, tower_top - 59), (x, tower_top - 56)])
    pygame.draw.line(surface, (196, 168, 84), (x - 7, tower_top - 59), (x + 7, tower_top - 59), 1)

    return pygame.Rect(x - hw - 10, y - g_h - t_h - r_h - 40, hw * 2 + 20, g_h + t_h + r_h + 40).inflate(-24, -16)


def draw_windmill(surface: pygame.Surface, x: int, y: int, seed: int = 0) -> pygame.Rect:
    """Smock windmill on a low grassy knoll: stone roundhouse base, tarred
    weatherboard tower with a gallery, domed cap with tail pole, and four
    lattice sails (two carrying furled canvas). (x, y) = base centre."""
    _hh = _house_hash
    rng = random.Random(seed * 5237 + 1)

    # grassy knoll the mill stands on
    kn = pygame.Surface((380, 130), pygame.SRCALPHA)
    pygame.draw.ellipse(kn, (74, 88, 48, 220), (0, 10, 380, 110))
    pygame.draw.ellipse(kn, (88, 104, 58, 235), (14, 6, 352, 104))
    pygame.draw.ellipse(kn, (102, 120, 66, 200), (40, 4, 300, 84))
    surface.blit(kn, (x - 190, y - 78))
    krng = random.Random(seed + 77)
    for _ in range(120):
        a = krng.uniform(0, math.tau)
        rr = krng.uniform(0, 1.0) ** 0.6
        gx = x + int(math.cos(a) * 175 * rr)
        gy2 = y - 24 + int(math.sin(a) * 48 * rr)
        gc = (krng.randint(78, 110), krng.randint(98, 130), krng.randint(44, 64))
        pygame.draw.line(surface, gc, (gx, gy2), (gx + krng.randint(-2, 2), gy2 - krng.randint(3, 7)), 1)
    # worn track to the door
    for ti in range(8):
        t = ti / 7.0
        pygame.draw.ellipse(surface, (104, 88, 62),
                            (x - 8 + int(t * 36) + krng.randint(-3, 3), y - 4 + int(t * 26), 16, 7))

    # building shadow cast lower-right
    shs = pygame.Surface((240, 60), pygame.SRCALPHA)
    pygame.draw.polygon(shs, (12, 9, 7, 40), [(0, 0), (150, 0), (236, 54), (70, 54)])
    surface.blit(shs, (x - 70, y - 18))

    # stone roundhouse base
    rh_w, rh_h = 150, 56
    rh_top = y - rh_h
    for row in range(rh_h):
        t = row / (rh_h - 1)
        v = int(92 - 24 * t) + _hh(row * 9 + seed, 33) % 5
        pygame.draw.line(surface, (v, v - 5, v - 11), (x - rh_w // 2, rh_top + row), (x + rh_w // 2, rh_top + row))
    for by in range(rh_top + 4, y - 6, 12):
        off = 9 if ((by - rh_top) // 12) % 2 else 0
        for bx in range(x - rh_w // 2 + off, x + rh_w // 2 - 8, 18):
            pygame.draw.rect(surface, (50, 46, 40), (bx, by, 16, 10), 1)
    pygame.draw.line(surface, (116, 112, 102), (x - rh_w // 2, rh_top), (x - rh_w // 2, y - 2), 2)
    pygame.draw.rect(surface, (40, 36, 30), (x - rh_w // 2, rh_top, rh_w, rh_h), 1)
    # arched mill door + lintel lamp
    pygame.draw.rect(surface, (26, 18, 11), (x - 16, y - 40, 32, 40))
    pygame.draw.circle(surface, (26, 18, 11), (x, y - 40), 16)
    pygame.draw.circle(surface, (66, 50, 32), (x, y - 40), 17, 2)
    for px2 in (x - 8, x, x + 8):
        pygame.draw.line(surface, (14, 10, 6), (px2, y - 50), (px2, y - 2), 1)
    pygame.draw.circle(surface, (96, 92, 86), (x + 9, y - 22), 2)

    # tarred smock tower (tapered, lit from the left)
    t_h2 = 184
    tw_b, tw_t = 64, 33
    t_top2 = rh_top - t_h2
    for row in range(t_h2):
        u = row / (t_h2 - 1)
        hw2 = int(tw_t + (tw_b - tw_t) * u)
        base_v = 70 - int(18 * u)
        for col in range(-hw2, hw2 + 1, 1):
            cv = base_v + int(26 * (0.5 - (col + hw2) / max(1, hw2 * 2))) + _hh(col * 7 + row * 3 + seed, 29) % 4
            surface.set_at((x + col, t_top2 + row), (max(0, cv), max(0, cv - 14), max(0, cv - 26)))
    for bi in range(9):                                            # board seams following the taper
        f = bi / 8.0 - 0.5
        pygame.draw.line(surface, (38, 28, 18),
                         (x + int(f * 2 * tw_t * 0.92), t_top2), (x + int(f * 2 * tw_b * 0.92), rh_top), 1)
    pygame.draw.line(surface, (108, 88, 62), (x - tw_t, t_top2), (x - tw_b, rh_top), 2)
    pygame.draw.line(surface, (30, 22, 14), (x + tw_t, t_top2), (x + tw_b, rh_top), 2)
    # small lit window up the tower
    pygame.draw.rect(surface, (224, 178, 100), (x - 7, t_top2 + 52, 14, 18))
    pygame.draw.line(surface, (54, 40, 26), (x, t_top2 + 52), (x, t_top2 + 70), 1)
    pygame.draw.line(surface, (54, 40, 26), (x - 7, t_top2 + 61), (x + 7, t_top2 + 61), 1)
    pygame.draw.rect(surface, (40, 30, 20), (x - 8, t_top2 + 51, 16, 20), 1)
    # gallery ring around the tower
    gal_y = rh_top - 38
    pygame.draw.rect(surface, (74, 56, 34), (x - 86, gal_y, 172, 7))
    pygame.draw.rect(surface, (104, 82, 52), (x - 86, gal_y, 172, 2))
    pygame.draw.rect(surface, (40, 30, 18), (x - 86, gal_y, 172, 7), 1)
    for gx2 in range(x - 82, x + 84, 12):                          # railing + struts
        pygame.draw.line(surface, (66, 50, 30), (gx2, gal_y - 12), (gx2, gal_y), 1)
    pygame.draw.line(surface, (88, 68, 42), (x - 84, gal_y - 12), (x + 84, gal_y - 12), 2)
    for sgn in (-1, 1):
        pygame.draw.line(surface, (52, 40, 24), (x + sgn * 80, gal_y + 6), (x + sgn * 52, gal_y + 26), 2)

    # domed cap
    cap_r = pygame.Rect(x - tw_t - 6, t_top2 - 34, (tw_t + 6) * 2, 44)
    pygame.draw.ellipse(surface, (52, 40, 26), cap_r)
    pygame.draw.ellipse(surface, (84, 66, 42), (cap_r.x + 3, cap_r.y + 2, cap_r.w - 10, cap_r.h - 12))
    pygame.draw.ellipse(surface, (36, 27, 17), cap_r, 2)
    pygame.draw.line(surface, (110, 88, 58), (cap_r.left + 8, cap_r.top + 8), (cap_r.right - 14, cap_r.top + 6), 2)
    # tail pole down to the gallery
    pygame.draw.line(surface, (58, 44, 26), (x + tw_t, t_top2 - 8), (x + 96, gal_y - 2), 4)
    pygame.draw.line(surface, (88, 68, 42), (x + tw_t, t_top2 - 9), (x + 96, gal_y - 3), 1)

    # ── four lattice sails on the cap hub ──
    hub = (x, t_top2 - 12)
    pygame.draw.circle(surface, (40, 30, 18), hub, 7)
    sail_len = 168
    for si, ang_deg in enumerate((38, 128, 218, 308)):
        a = math.radians(ang_deg)
        ca, sa = math.cos(a), math.sin(a)
        nx2, ny2 = -sa, ca
        tip = (hub[0] + int(ca * sail_len), hub[1] + int(sa * sail_len))
        # stock
        pygame.draw.line(surface, (34, 26, 16), hub, tip, 5)
        pygame.draw.line(surface, (74, 58, 36), (hub[0] - 1, hub[1] - 1), (tip[0] - 1, tip[1] - 1), 1)
        # lattice frame on the trailing side
        f0 = 0.22
        fr_in = (hub[0] + ca * sail_len * f0, hub[1] + sa * sail_len * f0)
        frame = [fr_in,
                 (fr_in[0] + nx2 * 17, fr_in[1] + ny2 * 17),
                 (tip[0] + nx2 * 17, tip[1] + ny2 * 17), tip]
        pygame.draw.polygon(surface, (52, 42, 28), [(int(px3), int(py3)) for px3, py3 in frame], 1)
        pygame.draw.line(surface, (52, 42, 28),
                         (int(fr_in[0] + nx2 * 17), int(fr_in[1] + ny2 * 17)),
                         (int(tip[0] + nx2 * 17), int(tip[1] + ny2 * 17)), 2)
        n_bars = 9
        for bi in range(1, n_bars):
            bt = f0 + (1.0 - f0) * bi / n_bars
            bx2 = hub[0] + ca * sail_len * bt
            by2 = hub[1] + sa * sail_len * bt
            pygame.draw.line(surface, (60, 48, 30), (int(bx2), int(by2)),
                             (int(bx2 + nx2 * 17), int(by2 + ny2 * 17)), 1)
        # canvas on two opposite sails (partly set)
        if si % 2 == 0:
            cv_pts = [(hub[0] + ca * sail_len * 0.30, hub[1] + sa * sail_len * 0.30),
                      (hub[0] + ca * sail_len * 0.30 + nx2 * 15, hub[1] + sa * sail_len * 0.30 + ny2 * 15),
                      (hub[0] + ca * sail_len * 0.92 + nx2 * 15, hub[1] + sa * sail_len * 0.92 + ny2 * 15),
                      (hub[0] + ca * sail_len * 0.92, hub[1] + sa * sail_len * 0.92)]
            pygame.draw.polygon(surface, (186, 176, 150), [(int(px3), int(py3)) for px3, py3 in cv_pts])
            pygame.draw.polygon(surface, (140, 130, 106), [(int(px3), int(py3)) for px3, py3 in cv_pts], 1)
            for ci in range(3):                                    # canvas seams
                ct = 0.30 + (0.92 - 0.30) * (ci + 1) / 4
                pygame.draw.line(surface, (158, 148, 124),
                                 (int(hub[0] + ca * sail_len * ct), int(hub[1] + sa * sail_len * ct)),
                                 (int(hub[0] + ca * sail_len * ct + nx2 * 15), int(hub[1] + sa * sail_len * ct + ny2 * 15)), 1)
    pygame.draw.circle(surface, (74, 58, 36), hub, 4)
    pygame.draw.circle(surface, (110, 90, 60), (hub[0] - 1, hub[1] - 1), 2)

    # flour sacks + leaning millstone by the door
    for sx3, sy3 in ((x - 44, y - 6), (x - 58, y - 2)):
        pygame.draw.ellipse(surface, (40, 32, 22, 120), (sx3 - 9, sy3 + 2, 20, 7))
        pygame.draw.ellipse(surface, (150, 128, 92), (sx3 - 8, sy3 - 14, 17, 18))
        pygame.draw.ellipse(surface, (180, 158, 118), (sx3 - 7, sy3 - 14, 11, 12))
        pygame.draw.line(surface, (96, 78, 52), (sx3 - 4, sy3 - 13), (sx3 + 4, sy3 - 13), 2)
    ms_c = (x + 52, y - 12)
    pygame.draw.circle(surface, (40, 36, 32), (ms_c[0] + 2, ms_c[1] + 3), 15)
    pygame.draw.circle(surface, (104, 100, 92), ms_c, 15)
    pygame.draw.circle(surface, (128, 124, 114), (ms_c[0] - 3, ms_c[1] - 3), 10)
    pygame.draw.circle(surface, (54, 50, 44), ms_c, 15, 2)
    pygame.draw.circle(surface, (38, 34, 30), ms_c, 4)

    return pygame.Rect(x - 84, y - rh_h - t_h2 - 40, 168, rh_h + t_h2 + 40)


def draw_granary(surface: pygame.Surface, x: int, y: int, seed: int = 0) -> pygame.Rect:
    """Raised timber granary on mushroom-capped staddle stones (rat guards),
    lap-boarded walls, shake gable roof, loading hatch with a leaning ladder
    and grain sacks below. (x, y) = ground centre."""
    rng = random.Random(seed * 3917 + 7)
    bw = 200                       # body width
    floor_y = y - 40               # underside of the raised floor
    body_h = 92
    body_top = floor_y - body_h

    # cast shadow
    shs = pygame.Surface((bw + 70, 36), pygame.SRCALPHA)
    pygame.draw.polygon(shs, (12, 9, 7, 40), [(0, 0), (bw + 6, 0), (bw + 66, 32), (52, 32)])
    surface.blit(shs, (x - bw // 2, y - 8))

    # dark gloom under the raised floor + back staddles
    cav = pygame.Surface((bw - 16, 40), pygame.SRCALPHA)
    for row in range(40):
        a = max(40, 190 - row * 5)
        pygame.draw.line(cav, (18, 14, 10, a), (0, row), (bw - 17, row))
    surface.blit(cav, (x - bw // 2 + 8, floor_y))
    for sx3 in (x - 56, x + 2, x + 58):
        pygame.draw.rect(surface, (52, 46, 40), (sx3 - 5, floor_y + 6, 10, 18))
        pygame.draw.ellipse(surface, (74, 70, 64), (sx3 - 9, floor_y + 2, 18, 9))
    # front staddle stones (stem + mushroom cap)
    for sx3 in (x - 78, x - 2, x + 76):
        pygame.draw.ellipse(surface, (34, 28, 20, 110), (sx3 - 11, y - 5, 24, 8))
        for ci in range(12):
            v = 96 - ci * 3 + rng.randint(-3, 3)
            pygame.draw.line(surface, (v, v - 4, v - 10), (sx3 - 6, y - 6 - ci), (sx3 + 6, y - 6 - ci))
        pygame.draw.ellipse(surface, (66, 62, 56), (sx3 - 13, y - 26, 26, 11))
        pygame.draw.ellipse(surface, (118, 114, 106), (sx3 - 13, y - 29, 26, 11))
        pygame.draw.ellipse(surface, (142, 138, 128), (sx3 - 10, y - 29, 14, 6))
    # floor joist band
    pygame.draw.rect(surface, (60, 45, 28), (x - bw // 2 - 6, floor_y - 6, bw + 12, 10))
    pygame.draw.rect(surface, (92, 72, 46), (x - bw // 2 - 6, floor_y - 6, bw + 12, 3))
    pygame.draw.rect(surface, (34, 25, 16), (x - bw // 2 - 6, floor_y - 6, bw + 12, 10), 1)

    # lap-boarded body (horizontal weatherboards, lit course tops)
    brow = body_top
    bi = 0
    while brow < floor_y - 6:
        bh2 = min(9, floor_y - 6 - brow)
        tone = rng.randint(-8, 8)
        base = 116 + tone - (4 if bi % 2 else 0)
        pygame.draw.rect(surface, (base, int(base * 0.79), int(base * 0.53)), (x - bw // 2, brow, bw, bh2))
        pygame.draw.line(surface, (min(255, base + 26), min(255, int(base * 0.79) + 22), min(255, int(base * 0.53) + 16)),
                         (x - bw // 2, brow), (x + bw // 2 - 1, brow), 1)
        pygame.draw.line(surface, (52, 39, 24), (x - bw // 2, brow + bh2 - 1), (x + bw // 2 - 1, brow + bh2 - 1), 1)
        brow += bh2
        bi += 1
    for tx0 in (x - bw // 2 - 2, x + bw // 2 - 3):                 # corner trims
        pygame.draw.rect(surface, (96, 76, 50), (tx0, body_top, 5, body_h))
        pygame.draw.line(surface, (126, 102, 70), (tx0, body_top), (tx0, floor_y - 7), 1)
    # loading hatch + strap hinges
    pygame.draw.rect(surface, (30, 21, 12), (x - 22, body_top + 26, 44, 50))
    for row in range(50):
        v = 38 - int(12 * row / 50)
        pygame.draw.line(surface, (v + 6, v, max(0, v - 6)), (x - 20, body_top + 27 + row), (x + 20, body_top + 27 + row))
    pygame.draw.line(surface, (18, 13, 8), (x, body_top + 27, ), (x, body_top + 75), 1)
    pygame.draw.rect(surface, (58, 44, 26), (x - 23, body_top + 25, 46, 52), 2)
    for hy2 in (body_top + 34, body_top + 64):
        pygame.draw.line(surface, (76, 74, 70), (x - 18, hy2), (x - 4, hy2 + 1), 2)
        pygame.draw.line(surface, (76, 74, 70), (x + 18, hy2), (x + 4, hy2 + 1), 2)
    # ladder leaning to the hatch
    l0, l1 = (x + 44, y + 2), (x + 26, body_top + 56)
    for off in (-6, 6):
        pygame.draw.line(surface, (54, 40, 24), (l0[0] + off, l0[1]), (l1[0] + off, l1[1]), 3)
        pygame.draw.line(surface, (94, 74, 48), (l0[0] + off - 1, l0[1]), (l1[0] + off - 1, l1[1]), 1)
    for li in range(7):
        t = (li + 0.5) / 7
        rx2 = l0[0] + (l1[0] - l0[0]) * t
        ry2 = l0[1] + (l1[1] - l0[1]) * t
        pygame.draw.line(surface, (84, 66, 42), (int(rx2) - 7, int(ry2)), (int(rx2) + 7, int(ry2)), 2)

    # gable shake roof
    e_l, e_r = x - bw // 2 - 16, x + bw // 2 + 16
    ridge_y = body_top - 54
    _pen_shake_roof(surface, x - bw // 2 + 34, x + bw // 2 - 34, ridge_y, e_l, e_r, body_top - 2,
                    rng, base=(124, 100, 68))
    # gable vent
    pygame.draw.rect(surface, (22, 16, 10), (x - 7, ridge_y + 16, 14, 12))
    for vx in (x - 4, x, x + 4):
        pygame.draw.line(surface, (66, 52, 32), (vx, ridge_y + 16), (vx, ridge_y + 27), 1)

    # grain sacks + spill at the foot
    for sx3, sy3 in ((x - 64, y + 6), (x - 46, y + 10)):
        pygame.draw.ellipse(surface, (40, 32, 22, 120), (sx3 - 9, sy3 + 3, 20, 7))
        pygame.draw.ellipse(surface, (148, 124, 86), (sx3 - 8, sy3 - 13, 17, 18))
        pygame.draw.ellipse(surface, (176, 152, 110), (sx3 - 7, sy3 - 13, 11, 12))
        pygame.draw.line(surface, (94, 76, 50), (sx3 - 4, sy3 - 12), (sx3 + 4, sy3 - 12), 2)
    for _ in range(22):
        pygame.draw.circle(surface, rng.choice([(198, 174, 104), (164, 142, 76), (212, 190, 120)]),
                           (x - 52 + rng.randint(-18, 26), y + 12 + rng.randint(-4, 6)), 1)

    return pygame.Rect(x - bw // 2 - 12, ridge_y - 10, bw + 24, (y + 4) - (ridge_y - 10))


def draw_washhouse(surface: pygame.Surface, x: int, y: int, seed: int = 0) -> pygame.Rect:
    """Open-fronted communal washhouse (lavoir): a shake roof on timber posts
    over a stone washing basin, with scrubbing boards, wicker baskets and a
    laundry line of drying linen strung to a side pole. (x, y) = base centre."""
    rng = random.Random(seed * 2789 + 11)
    hw = 130

    # cast shadow
    shs = pygame.Surface((hw * 2 + 70, 34), pygame.SRCALPHA)
    pygame.draw.polygon(shs, (12, 9, 7, 36), [(0, 0), (hw * 2 + 8, 0), (hw * 2 + 66, 30), (50, 30)])
    surface.blit(shs, (x - hw, y - 6))

    # back wall (low stone) seen through the open front
    bk_top = y - 118
    for row in range(34):
        t = row / 33.0
        v = int(66 - 20 * t)
        pygame.draw.line(surface, (v, v - 4, v - 9), (x - hw + 10, bk_top + row), (x + hw - 10, bk_top + row))
    for by in range(bk_top + 3, bk_top + 30, 9):
        off = 7 if ((by - bk_top) // 9) % 2 else 0
        for bx in range(x - hw + 12 + off, x + hw - 18, 15):
            pygame.draw.rect(surface, (40, 36, 30), (bx, by, 13, 8), 1)
    # interior gloom under the roof
    cav = pygame.Surface((hw * 2 - 20, 50), pygame.SRCALPHA)
    for row in range(50):
        a = max(30, 150 - row * 3)
        pygame.draw.line(cav, (16, 13, 10, a), (0, row), (hw * 2 - 21, row))
    surface.blit(cav, (x - hw + 10, bk_top + 30))

    # stone basin with water
    bs = pygame.Rect(x - 96, y - 64, 192, 52)
    pygame.draw.rect(surface, (58, 54, 48), bs.move(2, 3), border_radius=8)
    pygame.draw.rect(surface, (98, 94, 86), bs, border_radius=8)
    pygame.draw.rect(surface, (122, 118, 108), (bs.x, bs.y, bs.w, 5), border_radius=4)
    pygame.draw.rect(surface, (50, 46, 40), bs, 2, border_radius=8)
    wtr = bs.inflate(-18, -18)
    pygame.draw.rect(surface, (40, 52, 56), wtr, border_radius=6)
    pygame.draw.rect(surface, (52, 66, 70), wtr.inflate(-8, -8), border_radius=6)
    pygame.draw.line(surface, (24, 32, 36), (wtr.left + 2, wtr.top + 1), (wtr.right - 3, wtr.top + 1), 1)
    pygame.draw.line(surface, (118, 142, 146), (wtr.left + 8, wtr.top + 6), (wtr.right - 24, wtr.top + 6), 1)
    pygame.draw.line(surface, (186, 204, 206), (wtr.centerx - 14, wtr.top + 5), (wtr.centerx + 4, wtr.top + 5), 1)
    pygame.draw.arc(surface, (108, 128, 132), (wtr.centerx - 16, wtr.centery - 6, 30, 14), 0, math.tau, 1)
    # scrubbing boards over the rim
    for bx2, ang in ((x - 52, -0.18), (x + 34, 0.14)):
        bl = 46
        ex2 = bx2 + int(math.cos(ang) * 16)
        pygame.draw.polygon(surface, (118, 96, 62),
                            [(bx2 - 9, y - 64 + 4), (bx2 + 9, y - 64 + 2), (ex2 + 9, y - 64 + 4 - bl // 2), (ex2 - 9, y - 64 + 6 - bl // 2)])
        for gi in range(4):
            gy3 = y - 62 - gi * 5
            pygame.draw.line(surface, (84, 66, 42), (bx2 - 7, gy3), (bx2 + 7, gy3 - 1), 1)
        pygame.draw.polygon(surface, (56, 42, 26),
                            [(bx2 - 9, y - 64 + 4), (bx2 + 9, y - 64 + 2), (ex2 + 9, y - 64 + 4 - bl // 2), (ex2 - 9, y - 64 + 6 - bl // 2)], 1)
    # wet stone apron + drips in front of the basin
    ap = pygame.Surface((bs.w + 16, 14), pygame.SRCALPHA)
    pygame.draw.ellipse(ap, (46, 52, 50, 130), (0, 0, bs.w + 16, 14))
    surface.blit(ap, (bs.x - 8, bs.bottom - 2))
    for _ in range(10):
        dx2 = rng.randint(bs.left, bs.right)
        pygame.draw.circle(surface, (70, 84, 86), (dx2, bs.bottom + rng.randint(2, 10)), 1)

    # corner posts carrying the roof
    for px2, py2 in ((x - hw + 6, y - 4), (x + hw - 6, y - 4), (x - hw + 16, y - 88), (x + hw - 16, y - 88)):
        pygame.draw.ellipse(surface, (30, 24, 18, 100), (px2 - 7, py2 - 2, 14, 6))
        for ci in range(5):
            v = 104 - ci * 13
            pygame.draw.line(surface, (v, int(v * 0.78), int(v * 0.52)), (px2 - 2 + ci, py2), (px2 - 2 + ci, y - 132), 1)
    # lintel + shake roof
    pygame.draw.line(surface, (86, 66, 42), (x - hw - 4, y - 132), (x + hw + 4, y - 132), 4)
    pygame.draw.line(surface, (118, 94, 62), (x - hw - 4, y - 134), (x + hw + 4, y - 134), 1)
    _pen_shake_roof(surface, x - hw + 42, x + hw - 42, y - 188, x - hw - 14, x + hw + 14, y - 134,
                    rng, base=(118, 95, 64))

    # wicker baskets of linen at the left
    for bx2, by2 in ((x - hw - 24, y - 10), (x - hw - 4, y - 2)):
        pygame.draw.ellipse(surface, (34, 26, 18, 110), (bx2 - 12, by2 + 1, 26, 8))
        pygame.draw.ellipse(surface, (112, 88, 56), (bx2 - 12, by2 - 12, 25, 16))
        for wi2, wx2 in enumerate(range(bx2 - 11, bx2 + 12, 4)):
            pygame.draw.line(surface, (140, 112, 74) if wi2 % 2 else (92, 72, 46), (wx2, by2 - 10), (wx2 + 2, by2 + 2), 1)
        pygame.draw.ellipse(surface, (66, 50, 32), (bx2 - 12, by2 - 12, 25, 16), 1)
        pygame.draw.ellipse(surface, (228, 224, 214), (bx2 - 8, by2 - 15, 17, 9))
        pygame.draw.ellipse(surface, (188, 184, 174), (bx2 - 8, by2 - 15, 17, 9), 1)

    # laundry line strung to a side pole, linen drying
    pole_x = x + hw + 64
    pygame.draw.ellipse(surface, (30, 24, 18, 110), (pole_x - 7, y - 4, 16, 6))
    for ci in range(4):
        v = 100 - ci * 14
        pygame.draw.line(surface, (v, int(v * 0.78), int(v * 0.52)), (pole_x + ci - 1, y - 2), (pole_x + ci - 1, y - 96), 1)
    pygame.draw.line(surface, (168, 162, 150), (x + hw - 14, y - 118), (pole_x, y - 94), 1)
    cloth_cols = ((232, 228, 218), (196, 168, 120), (122, 134, 162), (224, 220, 210))
    for ci2, ct in enumerate((0.16, 0.40, 0.62, 0.84)):
        cx3 = int((x + hw - 14) + (pole_x - (x + hw - 14)) * ct)
        cy3 = int((y - 118) + ((y - 94) - (y - 118)) * ct)
        cw2, ch2 = (13, 22) if ci2 % 2 else (16, 17)
        col2 = cloth_cols[ci2]
        pygame.draw.rect(surface, col2, (cx3 - cw2 // 2, cy3, cw2, ch2))
        pygame.draw.polygon(surface, col2, [(cx3 - cw2 // 2, cy3 + ch2), (cx3 + cw2 // 2, cy3 + ch2),
                                            (cx3 + cw2 // 2 - 2, cy3 + ch2 + 4), (cx3 - cw2 // 2 + 3, cy3 + ch2 + 3)])
        pygame.draw.line(surface, (max(0, col2[0] - 40), max(0, col2[1] - 40), max(0, col2[2] - 36)),
                         (cx3 - cw2 // 2 + 3, cy3 + 2), (cx3 - cw2 // 2 + 3, cy3 + ch2 - 2), 1)
        for pgx in (cx3 - cw2 // 2 + 1, cx3 + cw2 // 2 - 1):
            pygame.draw.line(surface, (96, 76, 50), (pgx, cy3 - 2), (pgx, cy3 + 2), 1)

    return pygame.Rect(x - hw - 10, y - 196, hw * 2 + 20, 196).inflate(-16, -10)


def draw_wayside_shrine(surface: pygame.Surface, x: int, y: int, seed: int = 0) -> pygame.Rect:
    """Small roadside shrine: stone plinth, timber post carrying a roofed
    niche with a gilt icon, lit candles and offerings at the foot."""
    rng = random.Random(seed * 1543 + 13)
    # worn ground + contact shadow
    ws = pygame.Surface((64, 22), pygame.SRCALPHA)
    pygame.draw.ellipse(ws, (96, 82, 60, 90), (0, 0, 64, 22))
    pygame.draw.ellipse(ws, (30, 24, 18, 80), (14, 6, 40, 12))
    surface.blit(ws, (x - 32, y - 11))
    # plinth
    pygame.draw.rect(surface, (76, 72, 66), (x - 15, y - 12, 30, 10))
    pygame.draw.rect(surface, (104, 100, 92), (x - 15, y - 14, 30, 4))
    pygame.draw.rect(surface, (44, 40, 36), (x - 15, y - 14, 30, 12), 1)
    # post
    for ci in range(6):
        v = 102 - ci * 11
        pygame.draw.line(surface, (v, int(v * 0.78), int(v * 0.54)), (x - 3 + ci, y - 14), (x - 3 + ci, y - 66), 1)
    # niche box with gabled roof
    nb = pygame.Rect(x - 17, y - 96, 34, 32)
    pygame.draw.rect(surface, (88, 68, 44), nb)
    pygame.draw.rect(surface, (112, 90, 60), (nb.x, nb.y, 4, nb.h))
    pygame.draw.rect(surface, (46, 34, 20), nb, 2)
    inner = nb.inflate(-10, -10)
    pygame.draw.rect(surface, (26, 19, 12), inner)
    # gilt icon + halo
    pygame.draw.rect(surface, (188, 152, 64), (inner.centerx - 3, inner.centery - 5, 7, 12))
    pygame.draw.circle(surface, (224, 192, 96), (inner.centerx, inner.centery - 6), 4, 1)
    pygame.draw.circle(surface, (255, 232, 150), (inner.centerx - 1, inner.centery - 7), 1)
    roof_pts = [(nb.left - 6, nb.top), (nb.right + 6, nb.top), (nb.centerx, nb.top - 16)]
    pygame.draw.polygon(surface, (74, 56, 34), roof_pts)
    pygame.draw.polygon(surface, (104, 82, 50),
                        [(nb.left - 6, nb.top), (nb.centerx, nb.top - 16), (nb.centerx + 3, nb.top - 12), (nb.left, nb.top + 2)])
    pygame.draw.polygon(surface, (40, 30, 18), roof_pts, 1)
    pygame.draw.line(surface, (150, 124, 70), (nb.centerx, nb.top - 16), (nb.centerx, nb.top - 22), 2)
    # candles at the foot, lit
    for cx3, ch3 in ((x - 22, 7), (x + 20, 5), (x + 26, 8)):
        pygame.draw.rect(surface, (216, 206, 184), (cx3 - 2, y - 8 - ch3, 4, ch3))
        pygame.draw.circle(surface, (255, 196, 80), (cx3, y - 10 - ch3), 2)
        glow = pygame.Surface((18, 18), pygame.SRCALPHA)
        pygame.draw.circle(glow, (255, 184, 80, 44), (9, 9), 9)
        surface.blit(glow, (cx3 - 9, y - 18 - ch3))
    # flowers + a coin offering
    for _ in range(6):
        fx2 = x + rng.randint(-24, 24)
        fy2 = y - rng.randint(2, 8)
        pygame.draw.line(surface, (66, 88, 44), (fx2, fy2), (fx2 + rng.randint(-2, 2), fy2 - rng.randint(3, 6)), 1)
        pygame.draw.circle(surface, rng.choice([(196, 88, 96), (228, 198, 90), (224, 224, 214), (150, 110, 190)]),
                           (fx2 + rng.randint(-2, 2), fy2 - rng.randint(4, 8)), rng.randint(1, 2))
    pygame.draw.circle(surface, (212, 184, 96), (x + 8, y - 6), 2)
    pygame.draw.circle(surface, (150, 124, 60), (x + 8, y - 6), 2, 1)

    return pygame.Rect(x - 18, y - 14, 36, 14)


def _draw_town_wilderness_gate(surface: pygame.Surface, x: int, y: int) -> None:
    """Draw an ornate, grand stone gate at the south end of town — open archway to the wilderness."""
    _hh = _house_hash

    # ── Ground: cobblestone path widening toward the gate ──
    for py in range(y + 80, y - 10, -2):
        t = (y + 80 - py) / 90.0
        hw = int(50 + 60 * t)
        shade = 52 + int(12 * t) + _hh(py * 3, 77) % 6
        pygame.draw.line(surface, (shade, shade - 2, shade - 6), (x - hw, py), (x + hw, py))
    # cobble lines
    for py in range(y + 78, y - 8, 8):
        off = 5 if (py // 8) % 2 else 0
        t = (y + 80 - py) / 90.0
        hw = int(50 + 60 * t)
        for px in range(x - hw + off, x + hw - 4, 12):
            sv = 46 + _hh(px * 7 + py * 3, 99) % 12
            pygame.draw.rect(surface, (sv, sv - 3, sv - 8), (px, py, 10, 6), 1)

    # ── Twin guard towers (larger, more detailed) ──
    for side_x, sign in [(x - 150, -1), (x + 150, 1)]:
        tw = 80; th = 180
        tower = pygame.Rect(side_x - tw // 2, y - th, tw, th)
        # stone gradient body
        for row in range(tower.height):
            t = row / max(1, tower.height - 1)
            base = int(72 - 18 * t)
            r = base + _hh(row * 13 + sign * 7, 55) % 6
            pygame.draw.line(surface, (r, r - 6, r - 12),
                             (tower.left, tower.top + row), (tower.right, tower.top + row))
        # ashlar masonry (staggered blocks)
        for by in range(tower.top + 4, tower.bottom - 4, 12):
            off = 8 if ((by - tower.top) // 12) % 2 else 0
            for bx_s in range(tower.left + 2 + off, tower.right - 4, 18):
                bw = min(16, tower.right - bx_s - 2)
                sv = 56 + _hh(bx_s * 5 + by * 3, 41) % 10
                pygame.draw.rect(surface, (sv, sv - 4, sv - 10), (bx_s, by, bw, 10))
                pygame.draw.rect(surface, (38, 34, 28), (bx_s, by, bw, 10), 1)
        # corner pilasters (raised stone strips)
        for cx in [tower.left, tower.right - 6]:
            pygame.draw.rect(surface, (78, 72, 64), (cx, tower.top, 6, tower.height))
            pygame.draw.rect(surface, (42, 38, 32), (cx, tower.top, 6, tower.height), 1)
        # decorative string course bands
        for band_y in [tower.top + th // 3, tower.top + 2 * th // 3]:
            pygame.draw.rect(surface, (88, 82, 72), (tower.left - 3, band_y - 2, tw + 6, 5))
            pygame.draw.rect(surface, (44, 40, 34), (tower.left - 3, band_y - 2, tw + 6, 5), 1)
        pygame.draw.rect(surface, (36, 32, 28), tower, 2)
        # crenellations (battlements with merlons)
        for bx_s in range(tower.left - 2, tower.right, 14):
            merlon = pygame.Rect(bx_s, tower.top - 16, 10, 18)
            pygame.draw.rect(surface, (76, 70, 62), merlon)
            pygame.draw.rect(surface, (38, 34, 28), merlon, 1)
        # arrow slits (two per tower)
        for slit_y in [y - 120, y - 60]:
            pygame.draw.rect(surface, (10, 8, 6), (side_x - 3, slit_y, 6, 22), border_radius=2)
            pygame.draw.rect(surface, (50, 46, 40), (side_x - 4, slit_y - 1, 8, 24), 1, border_radius=2)
        # torch bracket + flame
        torch_x = side_x + sign * 36
        # iron bracket
        pygame.draw.line(surface, (50, 48, 44), (side_x + sign * 4, y - 76), (torch_x, y - 76), 3)
        pygame.draw.line(surface, (50, 48, 44), (torch_x, y - 76), (torch_x, y - 58), 3)
        # torch body
        pygame.draw.rect(surface, (100, 72, 40), (torch_x - 3, y - 58, 6, 20), border_radius=1)
        # flame layers
        pygame.draw.circle(surface, (200, 80, 20), (torch_x, y - 62), 8)
        pygame.draw.circle(surface, (240, 160, 50), (torch_x, y - 64), 6)
        pygame.draw.circle(surface, (255, 220, 100), (torch_x, y - 66), 3)
        # banner hanging from tower
        ban_x = side_x - sign * 12
        ban_top = y - 140
        ban_h = 48
        ban_w = 18
        # banner pole
        pygame.draw.line(surface, (60, 56, 48), (ban_x, ban_top - 4), (ban_x, ban_top + ban_h + 8), 2)
        # banner cloth (dark crimson with gold trim)
        for br in range(ban_h):
            wave = int(2 * math.sin((ban_top + br) * 0.12))
            r_shade = 110 - br // 2
            pygame.draw.line(surface, (r_shade, 18, 22),
                             (ban_x - ban_w // 2 + wave, ban_top + br),
                             (ban_x + ban_w // 2 + wave, ban_top + br))
        # gold trim edges
        for br in range(ban_h):
            wave = int(2 * math.sin((ban_top + br) * 0.12))
            pygame.draw.rect(surface, (180, 150, 60), (ban_x - ban_w // 2 + wave, ban_top + br, 2, 1))
            pygame.draw.rect(surface, (180, 150, 60), (ban_x + ban_w // 2 - 2 + wave, ban_top + br, 2, 1))
        # banner point (triangular bottom)
        bw2 = ban_w // 2
        wave_b = int(2 * math.sin((ban_top + ban_h) * 0.12))
        pygame.draw.polygon(surface, (90, 14, 18), [
            (ban_x - bw2 + wave_b, ban_top + ban_h),
            (ban_x + bw2 + wave_b, ban_top + ban_h),
            (ban_x + wave_b, ban_top + ban_h + 14)])
        # skull/emblem on banner
        emb_y = ban_top + ban_h // 2 - 4
        pygame.draw.circle(surface, (180, 160, 80), (ban_x, emb_y), 5)
        pygame.draw.circle(surface, (140, 120, 50), (ban_x, emb_y), 5, 1)

    # ── Curtain walls connecting towers ──
    for wx, ww2 in [(x - 210, 60), (x + 150, 60)]:
        wall_r = pygame.Rect(wx, y - 140, ww2, 140)
        for row in range(wall_r.height):
            t = row / max(1, wall_r.height - 1)
            sv = int(64 - 12 * t)
            pygame.draw.line(surface, (sv, sv - 4, sv - 10),
                             (wall_r.left, wall_r.top + row), (wall_r.right, wall_r.top + row))
        # wall masonry
        for by in range(wall_r.top + 4, wall_r.bottom - 4, 12):
            off = 8 if ((by - wall_r.top) // 12) % 2 else 0
            for bx_s in range(wall_r.left + 2 + off, wall_r.right - 4, 18):
                bw = min(16, wall_r.right - bx_s - 2)
                pygame.draw.rect(surface, (42, 38, 32), (bx_s, by, bw, 10), 1)
        pygame.draw.rect(surface, (36, 32, 28), wall_r, 1)
        # wall-top crenellations
        for bx_s in range(wall_r.left, wall_r.right - 6, 14):
            pygame.draw.rect(surface, (72, 66, 58), (bx_s, wall_r.top - 12, 10, 14))
            pygame.draw.rect(surface, (38, 34, 28), (bx_s, wall_r.top - 12, 10, 14), 1)

    # ── Grand archway (OPEN — no portcullis) ──
    arch_w, arch_h = 160, 130
    arch_rect = pygame.Rect(x - arch_w // 2, y - arch_h, arch_w, arch_h)
    # dark passageway interior with depth gradient
    for row in range(arch_rect.height):
        t = row / max(1, arch_rect.height - 1)
        d = int(8 + 14 * t)
        pygame.draw.line(surface, (d, d - 2, d + 2),
                         (arch_rect.left + 6, arch_rect.top + row),
                         (arch_rect.right - 6, arch_rect.top + row))
    # arch top (pointed gothic arch)
    arch_peak_y = arch_rect.top - 40
    # fill the gothic arch area
    for row in range(50):
        fy = arch_rect.top - row
        t = row / 50.0
        hw = int(arch_w // 2 * (1.0 - t * t))
        d = int(8 + 6 * (1.0 - t))
        if hw > 0:
            pygame.draw.line(surface, (d, d - 2, d + 2), (x - hw + 6, fy), (x + hw - 6, fy))
    # stone voussoirs (arch stones)
    for i in range(14):
        angle = math.pi * i / 13
        r_inner = arch_w // 2
        r_outer = r_inner + 12
        x1 = x + int(r_inner * math.cos(angle))
        y1 = arch_rect.top + 10 - int(r_inner * 0.38 * math.sin(angle))
        x2 = x + int(r_outer * math.cos(angle))
        y2 = arch_rect.top + 10 - int(r_outer * 0.38 * math.sin(angle))
        sv = 68 + _hh(i * 17, 33) % 12
        pygame.draw.line(surface, (sv, sv - 4, sv - 10), (x1, y1), (x2, y2), 3)
    # arch frame pillars (ornate columns)
    for cx in [arch_rect.left - 4, arch_rect.right - 6]:
        # column base
        pygame.draw.rect(surface, (82, 76, 66), (cx - 4, arch_rect.bottom - 14, 18, 14))
        pygame.draw.rect(surface, (44, 40, 34), (cx - 4, arch_rect.bottom - 14, 18, 14), 1)
        # column shaft
        pygame.draw.rect(surface, (76, 70, 62), (cx, arch_rect.top + 10, 10, arch_rect.height - 24))
        # fluting (vertical grooves)
        pygame.draw.line(surface, (66, 60, 52), (cx + 3, arch_rect.top + 14), (cx + 3, arch_rect.bottom - 16), 1)
        pygame.draw.line(surface, (66, 60, 52), (cx + 7, arch_rect.top + 14), (cx + 7, arch_rect.bottom - 16), 1)
        # column capital (ornate top)
        cap_y = arch_rect.top + 6
        pygame.draw.rect(surface, (88, 82, 72), (cx - 4, cap_y, 18, 8))
        pygame.draw.rect(surface, (44, 40, 34), (cx - 4, cap_y, 18, 8), 1)
        # scroll ornament
        pygame.draw.circle(surface, (92, 86, 76), (cx + 1, cap_y + 2), 4)
        pygame.draw.circle(surface, (92, 86, 76), (cx + 9, cap_y + 2), 4)
    # keystone (large, ornate, with skull carving)
    ks_w, ks_h = 28, 24
    ks_x, ks_y = x - ks_w // 2, arch_peak_y - 4
    pygame.draw.polygon(surface, (96, 88, 76), [
        (ks_x, ks_y + ks_h), (ks_x + ks_w, ks_y + ks_h),
        (ks_x + ks_w - 4, ks_y), (ks_x + 4, ks_y)])
    pygame.draw.polygon(surface, (56, 50, 42), [
        (ks_x, ks_y + ks_h), (ks_x + ks_w, ks_y + ks_h),
        (ks_x + ks_w - 4, ks_y), (ks_x + 4, ks_y)], 1)
    # skull carving on keystone
    pygame.draw.circle(surface, (120, 112, 96), (x, ks_y + 10), 7)
    pygame.draw.circle(surface, (70, 64, 54), (x, ks_y + 10), 7, 1)
    pygame.draw.circle(surface, (20, 18, 16), (x - 3, ks_y + 9), 2)  # left eye
    pygame.draw.circle(surface, (20, 18, 16), (x + 3, ks_y + 9), 2)  # right eye
    pygame.draw.line(surface, (20, 18, 16), (x - 1, ks_y + 13), (x + 1, ks_y + 13), 1)  # nose
    pygame.draw.line(surface, (20, 18, 16), (x - 4, ks_y + 15), (x + 4, ks_y + 15), 1)  # mouth

    # ── Iron chains hanging from arch (decorative) ──
    for ch_x in [x - 50, x + 50]:
        for cy in range(arch_rect.top + 20, arch_rect.top + 70, 6):
            pygame.draw.circle(surface, (58, 58, 64), (ch_x, cy), 3, 1)

    # ── Hanging lanterns inside archway ──
    for lan_x in [x - 30, x + 30]:
        pygame.draw.line(surface, (50, 48, 44), (lan_x, arch_rect.top + 16), (lan_x, arch_rect.top + 34), 1)
        pygame.draw.rect(surface, (40, 38, 34), (lan_x - 4, arch_rect.top + 34, 8, 12))
        pygame.draw.rect(surface, (60, 56, 48), (lan_x - 4, arch_rect.top + 34, 8, 12), 1)
        pygame.draw.circle(surface, (220, 180, 80), (lan_x, arch_rect.top + 40), 3)

    # ── Wooden sign: "THE WILDERNESS" ──
    sign_w, sign_h = 140, 30
    sign_rect = pygame.Rect(x - sign_w // 2, y - arch_h - 60, sign_w, sign_h)
    # sign board
    pygame.draw.rect(surface, (56, 40, 26), sign_rect, border_radius=4)
    pygame.draw.rect(surface, (100, 80, 50), sign_rect, 2, border_radius=4)
    # iron corner brackets
    for cx2, cy2 in [(sign_rect.left + 2, sign_rect.top + 2),
                     (sign_rect.right - 8, sign_rect.top + 2),
                     (sign_rect.left + 2, sign_rect.bottom - 8),
                     (sign_rect.right - 8, sign_rect.bottom - 8)]:
        pygame.draw.rect(surface, (60, 58, 62), (cx2, cy2, 6, 6))
    # hanging chains from sign
    pygame.draw.line(surface, (54, 52, 56), (sign_rect.left + 12, sign_rect.top), (sign_rect.left + 12, sign_rect.top - 16), 2)
    pygame.draw.line(surface, (54, 52, 56), (sign_rect.right - 12, sign_rect.top), (sign_rect.right - 12, sign_rect.top - 16), 2)

    # ── Decorative iron spikes atop wall ──
    for sp_x in range(x - 200, x + 210, 22):
        if abs(sp_x - x) < 85:
            continue  # skip over the arch
        pygame.draw.line(surface, (44, 44, 50), (sp_x, y - 152), (sp_x, y - 164), 2)
        pygame.draw.circle(surface, (52, 52, 58), (sp_x, y - 166), 3)

    # ── Ground skulls / bones near the gate (warning) ──
    for bx, by2 in [(x - 80, y + 20), (x + 75, y + 15), (x - 40, y + 50)]:
        pygame.draw.circle(surface, (160, 150, 130), (bx, by2), 5)
        pygame.draw.circle(surface, (100, 92, 78), (bx, by2), 5, 1)
        pygame.draw.circle(surface, (30, 26, 22), (bx - 2, by2 - 1), 1)
        pygame.draw.circle(surface, (30, 26, 22), (bx + 2, by2 - 1), 1)
        # small bone
        pygame.draw.line(surface, (150, 140, 120), (bx + 6, by2 + 2), (bx + 16, by2 - 2), 2)


def _draw_gate_vfx(screen: pygame.Surface, gate_world_x: int, gate_world_y: int,
                    cam_x: float, cam_y: float, ticks: int) -> None:
    """Draw animated VFX over the wilderness gate: embers, mist swirls, eerie glow."""
    gx = gate_world_x - int(cam_x)
    gy = gate_world_y - int(cam_y)
    # cull if off-screen
    if gx < -250 or gx > SCREEN_WIDTH + 250 or gy < -250 or gy > SCREEN_HEIGHT + 250:
        return
    t = ticks * 0.001  # seconds

    # ── Eerie green/amber glow pulsing inside the archway ──
    glow_alpha = int(28 + 18 * math.sin(t * 1.8))
    glow_surf = pygame.Surface((180, 160), pygame.SRCALPHA)
    for r in range(80, 10, -6):
        a = max(0, min(255, glow_alpha - (80 - r)))
        pygame.draw.ellipse(glow_surf, (180, 200, 120, a),
                            (90 - r, 80 - r, r * 2, r * 2))
    screen.blit(glow_surf, (gx - 90, gy - 140), special_flags=pygame.BLEND_RGBA_ADD)

    # ── Rising embers / sparks ──
    for i in range(16):
        seed_v = i * 137 + 53
        phase = (t * (0.6 + (seed_v % 10) * 0.08) + seed_v * 0.1) % 3.0
        if phase > 2.5:
            continue  # gap between cycles
        ex = gx + int(math.sin(seed_v * 1.7 + t * 0.9) * 60) + (seed_v % 40 - 20)
        ey = gy - 20 - int(phase * 55)
        sz = max(1, 3 - int(phase))
        alpha_e = max(0, min(255, int(200 - phase * 80)))
        r_c = min(255, 200 + (seed_v % 56))
        g_c = min(255, 100 + (seed_v % 80))
        ember_col = (r_c, g_c, 30, alpha_e)
        if sz >= 2:
            es = pygame.Surface((sz * 2, sz * 2), pygame.SRCALPHA)
            pygame.draw.circle(es, ember_col, (sz, sz), sz)
            screen.blit(es, (ex - sz, ey - sz))
        else:
            es = pygame.Surface((4, 4), pygame.SRCALPHA)
            es.fill(ember_col)
            screen.blit(es, (ex, ey))

    # ── Ground mist / fog tendrils ──
    mist_surf = pygame.Surface((320, 60), pygame.SRCALPHA)
    for mi in range(6):
        mx = 40 + mi * 44 + int(12 * math.sin(t * 0.5 + mi * 1.1))
        my = 20 + int(8 * math.sin(t * 0.7 + mi * 0.9))
        mr = 28 + int(10 * math.sin(t * 0.4 + mi * 2.0))
        ma = max(0, min(50, int(30 + 18 * math.sin(t * 0.6 + mi * 1.3))))
        pygame.draw.ellipse(mist_surf, (180, 195, 210, ma), (mx - mr, my - mr // 2, mr * 2, mr))
    screen.blit(mist_surf, (gx - 160, gy - 10))

    # ── Torch flicker (animated flame on each tower) ──
    for sign in [-1, 1]:
        tx = gx + sign * 186
        ty = gy - 64
        flicker = int(3 * math.sin(t * 8.0 + sign * 2.0))
        # outer glow
        glow_s = pygame.Surface((30, 30), pygame.SRCALPHA)
        pygame.draw.circle(glow_s, (255, 160, 40, 60), (15, 15), 14)
        screen.blit(glow_s, (tx - 15, ty - 15 + flicker), special_flags=pygame.BLEND_RGBA_ADD)
        # flame core
        glow_s2 = pygame.Surface((16, 16), pygame.SRCALPHA)
        pygame.draw.circle(glow_s2, (255, 230, 120, 120), (8, 8), 6)
        screen.blit(glow_s2, (tx - 8, ty - 10 + flicker), special_flags=pygame.BLEND_RGBA_ADD)

    # ── Floating dust motes ──
    for di in range(10):
        ds = di * 97 + 31
        dx = gx - 80 + int(160 * ((ds * 13 + int(t * 20)) % 200) / 200.0)
        dy = gy - 130 + int(120 * ((ds * 7 + int(t * 12)) % 200) / 200.0)
        da = max(0, min(120, int(60 + 50 * math.sin(t * 1.2 + ds))))
        dot_s = pygame.Surface((4, 4), pygame.SRCALPHA)
        pygame.draw.circle(dot_s, (220, 210, 180, da), (2, 2), 2)
        screen.blit(dot_s, (dx - 2, dy - 2))


def _draw_giant_fire_pit(surface: pygame.Surface, x: int, y: int) -> None:
    """Draw a massive ornate fire pit as the town's central gathering place."""
    _hh = _house_hash

    # ── Scale — this is the town centrepiece, make it BIG ──
    outer_rx, outer_ry = 260, 110          # outermost decorative ring
    mid_rx, mid_ry = 210, 88              # mid ring (cobblestone apron)
    inner_rx, inner_ry = 160, 66          # inner fire ring
    core_rx, core_ry = 110, 44            # actual fire bowl

    # ── Ground shadow / scorch zone ──
    _shw, _shh = outer_rx * 2 + 80, outer_ry * 2 + 60
    _sh = pygame.Surface((_shw, _shh), pygame.SRCALPHA)
    pygame.draw.ellipse(_sh, (8, 6, 4, 110), (0, 0, _shw, _shh))
    pygame.draw.ellipse(_sh, (14, 10, 6, 60), (30, 15, _shw - 60, _shh - 30))
    surface.blit(_sh, (x - _shw // 2, y - _shh // 2))

    # ── Cobblestone apron (ring between outer and mid) ──
    _aprng = random.Random(4444)
    for i in range(80):
        ang = (i / 80.0) * math.tau + _aprng.random() * 0.08
        rad_f = 0.82 + _aprng.random() * 0.18
        cx2 = x + int(math.cos(ang) * outer_rx * rad_f)
        cy2 = y + int(math.sin(ang) * outer_ry * rad_f)
        # Skip if inside mid ring
        dx_n = (cx2 - x) / max(1, mid_rx)
        dy_n = (cy2 - y) / max(1, mid_ry)
        if dx_n * dx_n + dy_n * dy_n < 0.85:
            continue
        sv = 54 + _aprng.randint(0, 16)
        sw = _aprng.randint(12, 22)
        sh2 = _aprng.randint(8, 14)
        pygame.draw.ellipse(surface, (sv, sv - 2, sv - 6), (cx2 - sw // 2, cy2 - sh2 // 2, sw, sh2))
        pygame.draw.ellipse(surface, (sv - 12, sv - 14, sv - 18), (cx2 - sw // 2, cy2 - sh2 // 2, sw, sh2), 1)

    # ── Outer stone ring — 36 large carved masonry blocks ──
    for i in range(36):
        ang = (i / 36.0) * math.tau
        sx = x + int(math.cos(ang) * mid_rx)
        sy = y + int(math.sin(ang) * mid_ry)
        sw = 24 + _hh(i * 13, 77) % 8
        sh2 = 18 + _hh(i * 7, 33) % 6
        sv = 62 + _hh(i * 11, 55) % 16
        sc2 = (sv, sv - 4, sv - 10)
        pygame.draw.ellipse(surface, sc2, (sx - sw // 2, sy - sh2 // 2, sw, sh2))
        pygame.draw.ellipse(surface, (sv - 18, sv - 22, sv - 28), (sx - sw // 2, sy - sh2 // 2, sw, sh2), 2)
        # Carved rune marks on every 3rd stone
        if i % 3 == 0:
            _rx, _ry = sx, sy
            pygame.draw.line(surface, (sv + 18, sv + 12, sv + 6), (_rx - 4, _ry - 3), (_rx + 4, _ry + 3), 2)
            pygame.draw.line(surface, (sv + 18, sv + 12, sv + 6), (_rx - 3, _ry + 3), (_rx + 3, _ry - 3), 2)
            pygame.draw.circle(surface, (sv + 20, sv + 14, sv + 8), (_rx, _ry), 2)

    # ── Inner fire-bowl ring — 28 heat-darkened stones ──
    for i in range(28):
        ang = (i / 28.0) * math.tau
        sx = x + int(math.cos(ang) * inner_rx)
        sy = y + int(math.sin(ang) * inner_ry)
        sw = 20 + _hh(i * 17, 91) % 6
        sh2 = 14 + _hh(i * 9, 41) % 5
        sv = 42 + _hh(i * 19, 63) % 12
        pygame.draw.ellipse(surface, (sv, sv - 6, sv - 12), (sx - sw // 2, sy - sh2 // 2, sw, sh2))
        pygame.draw.ellipse(surface, (sv - 14, sv - 18, sv - 24), (sx - sw // 2, sy - sh2 // 2, sw, sh2), 2)

    # ── Ash bed (gradient rings from center) ──
    for ring in range(16, 0, -1):
        t = ring / 16.0
        shade = int(18 + 22 * (1.0 - t))
        rx_r = int(core_rx * t)
        ry_r = int(core_ry * t)
        if rx_r > 1 and ry_r > 1:
            pygame.draw.ellipse(surface, (shade, shade - 2, shade + 4),
                                (x - rx_r, y - ry_r, rx_r * 2, ry_r * 2))

    # ── Charcoal chunks ──
    _fprng = random.Random(2222)
    for _ in range(80):
        cx2 = x + _fprng.randint(-int(core_rx * 0.8), int(core_rx * 0.8))
        cy2 = y + _fprng.randint(-int(core_ry * 0.7), int(core_ry * 0.7))
        cv = _fprng.randint(14, 34)
        cr = _fprng.randint(2, 7)
        pygame.draw.circle(surface, (cv, cv - 2, cv + 4), (cx2, cy2), cr)

    # ── Ember glow patches (static base) ──
    for _ in range(40):
        ex = x + _fprng.randint(-int(core_rx * 0.65), int(core_rx * 0.65))
        ey = y + _fprng.randint(-int(core_ry * 0.55), int(core_ry * 0.55))
        er = _fprng.randint(6, 18)
        _es = pygame.Surface((er * 2, er * 2), pygame.SRCALPHA)
        pygame.draw.circle(_es, (220, 70, 15, _fprng.randint(50, 120)), (er, er), er)
        surface.blit(_es, (ex - er, ey - er))

    # ── Logs arranged in star pattern (8 big logs) ──
    for li in range(8):
        ang = (li / 8.0) * math.tau + 0.2
        lx1 = x + int(math.cos(ang) * 30)
        ly1 = y + int(math.sin(ang) * 12)
        lx2 = x + int(math.cos(ang) * core_rx * 0.85)
        ly2 = y + int(math.sin(ang) * core_ry * 0.85)
        lv = 48 + _hh(li * 7, 33) % 14
        pygame.draw.line(surface, (lv, lv - 10, lv - 20), (lx1, ly1), (lx2, ly2), 8)
        pygame.draw.line(surface, (lv + 14, lv + 2, lv - 6), (lx1, ly1), (lx2, ly2), 3)
        # Bark texture marks
        for bi in range(6):
            t = (bi + 1) / 7.0
            bx = int(lx1 + (lx2 - lx1) * t)
            by = int(ly1 + (ly2 - ly1) * t)
            pygame.draw.line(surface, (lv - 16, lv - 24, lv - 30), (bx - 3, by - 2), (bx + 3, by + 2), 1)
        # Burning tip glow
        _btg = pygame.Surface((20, 20), pygame.SRCALPHA)
        pygame.draw.circle(_btg, (255, 100, 20, 100), (10, 10), 8)
        surface.blit(_btg, (lx1 - 10, ly1 - 10))

    # ── Large static flame tongues (base layer — VFX adds animated ones) ──
    flame_colors = [(220, 60, 15), (240, 100, 20), (255, 160, 40), (255, 220, 80)]
    for fi in range(16):
        ang = (fi / 16.0) * math.tau + 0.1
        dist = 28 + (fi % 3) * 8
        fx = x + int(math.cos(ang) * dist)
        fy = y + int(math.sin(ang) * dist * 0.4) - 6
        fh = 30 + _hh(fi * 11, 77) % 24
        fw = 8 + _hh(fi * 7, 33) % 6
        pts = [(fx - fw, fy), (fx + fw, fy), (fx + _hh(fi, 11) % 6 - 3, fy - fh)]
        pygame.draw.polygon(surface, flame_colors[fi % 4], pts)
        pts2 = [(fx - fw // 2, fy), (fx + fw // 2, fy), (fx, fy - fh * 2 // 3)]
        pygame.draw.polygon(surface, flame_colors[min(3, fi % 4 + 1)], pts2)

    # ── Central fire glow (static warm light baked into ground) ──
    for gr in range(5):
        gr_r = 60 - gr * 10
        gr_ry = int(gr_r * 0.4)
        _cg = pygame.Surface((gr_r * 2, gr_ry * 2), pygame.SRCALPHA)
        _ca = min(80, 30 + gr * 12)
        pygame.draw.ellipse(_cg, (255, 120 + gr * 20, 20, _ca), (0, 0, gr_r * 2, gr_ry * 2))
        surface.blit(_cg, (x - gr_r, y - gr_ry - 8))

    # ── 6 iron torch stands (hexagonal arrangement) ──
    for ti in range(6):
        ang = (ti / 6.0) * math.tau
        tx = x + int(math.cos(ang) * (outer_rx + 30))
        ty = y + int(math.sin(ang) * (outer_ry + 14))
        # Iron stand (taller)
        pygame.draw.rect(surface, (42, 42, 48), (tx - 4, ty - 70, 8, 70))
        pygame.draw.rect(surface, (52, 52, 58), (tx - 4, ty - 70, 8, 70), 1)
        # Cross brace
        pygame.draw.line(surface, (48, 48, 54), (tx - 12, ty), (tx + 12, ty), 3)
        # Brazier cup
        pygame.draw.polygon(surface, (60, 56, 50), [(tx - 12, ty - 76), (tx + 12, ty - 76),
                                                      (tx + 10, ty - 68), (tx - 10, ty - 68)])
        pygame.draw.polygon(surface, (38, 36, 32), [(tx - 12, ty - 76), (tx + 12, ty - 76),
                                                      (tx + 10, ty - 68), (tx - 10, ty - 68)], 1)
        # Flame
        pygame.draw.polygon(surface, (240, 120, 30), [(tx - 6, ty - 76), (tx + 6, ty - 76), (tx, ty - 96)])
        pygame.draw.polygon(surface, (255, 200, 80), [(tx - 3, ty - 76), (tx + 3, ty - 76), (tx, ty - 88)])
        # Glow
        _gs = pygame.Surface((50, 50), pygame.SRCALPHA)
        pygame.draw.circle(_gs, (255, 160, 40, 55), (25, 25), 22)
        surface.blit(_gs, (tx - 25, ty - 98))

    # ── Decorative iron chain links between stands ──
    for ci in range(6):
        ang1 = (ci / 6.0) * math.tau
        ang2 = ((ci + 1) / 6.0) * math.tau
        for cj in range(8):
            t = (cj + 1) / 9.0
            ca = ang1 + (ang2 - ang1) * t
            ccx = x + int(math.cos(ca) * (outer_rx + 22))
            ccy = y + int(math.sin(ca) * (outer_ry + 10))
            sag = int(6 * math.sin(t * math.pi))
            pygame.draw.circle(surface, (52, 52, 58), (ccx, ccy + sag), 4, 1)

    # ── 8 stone benches around the pit for gathering ──
    for bi in range(8):
        ang = (bi / 8.0) * math.tau + 0.2
        bx = x + int(math.cos(ang) * (outer_rx + 60))
        by = y + int(math.sin(ang) * (outer_ry + 26))
        bw, bh = 36, 12
        sv = 58 + _hh(bi * 13, 99) % 12
        pygame.draw.rect(surface, (sv, sv - 4, sv - 8), (bx - bw // 2, by - bh // 2, bw, bh), border_radius=3)
        pygame.draw.rect(surface, (sv - 16, sv - 20, sv - 24), (bx - bw // 2, by - bh // 2, bw, bh), 1, border_radius=3)
        # Stone legs
        for loff in [-bw // 3, bw // 3]:
            pygame.draw.rect(surface, (sv - 8, sv - 12, sv - 16), (bx + loff - 3, by + bh // 2 - 2, 6, 8))


def _draw_fire_pit_vfx(screen: pygame.Surface, pit_x: int, pit_y: int,
                        cam_x: float, cam_y: float, ticks: int) -> None:
    """Render animated VFX for the giant central fire pit — flames, sparks, heat haze, smoke."""
    sx = pit_x - int(cam_x)
    sy = pit_y - int(cam_y)
    if sx < -400 or sx > SCREEN_WIDTH + 400 or sy < -400 or sy > SCREEN_HEIGHT + 400:
        return
    t = ticks * 0.001

    # ── Firelight ground pool (contained warm light, not a flat orange oval) ──
    # Two flickering frequencies so the pool breathes instead of pulsing uniformly.
    flick = 0.5 + 0.5 * (0.6 * math.sin(t * 2.2) + 0.4 * math.sin(t * 5.7 + 1.3))
    glow_r = int(118 + 18 * flick)          # ~half the old footprint
    glow_ry = int(glow_r * 0.42)            # flattened to sit on the ground plane
    glow_surf = pygame.Surface((glow_r * 2 + 4, glow_ry * 2 + 4), pygame.SRCALPHA)
    gcx, gcy = glow_r + 2, glow_ry + 2
    # Steep quadratic falloff: bright contained core, edges vanish smoothly.
    for r in range(glow_r, 6, -6):
        frac = r / float(glow_r)
        edge = (1.0 - frac)
        a = max(0, min(58, int(58 * edge * edge)))   # peak alpha ~58, was ~90 stacked
        # Hotter (more yellow) toward the centre, deep ember-orange at the rim.
        g_val = int(70 + 120 * edge)
        b_val = int(10 + 40 * edge * edge)
        ry2 = int(r * 0.42)
        if r > 0 and ry2 > 0:
            pygame.draw.ellipse(glow_surf, (255, g_val, b_val, a),
                                (gcx - r, gcy - ry2, r * 2, ry2 * 2))
    screen.blit(glow_surf, (sx - gcx, sy - gcy), special_flags=pygame.BLEND_RGBA_ADD)

    # Tight hot core right at the coals — small, bright, flickering.
    core_r = int(34 + 8 * flick)
    core_ry = int(core_r * 0.5)
    core_surf = pygame.Surface((core_r * 2 + 4, core_ry * 2 + 4), pygame.SRCALPHA)
    for r in range(core_r, 2, -3):
        frac = r / float(core_r)
        a = max(0, min(120, int(120 * (1.0 - frac))))
        ry2 = max(1, int(r * 0.5))
        pygame.draw.ellipse(core_surf, (255, int(190 + 60 * (1.0 - frac)), 110, a),
                            (core_r + 2 - r, core_ry + 2 - ry2, r * 2, ry2 * 2))
    screen.blit(core_surf, (sx - core_r - 2, sy - core_ry - 2), special_flags=pygame.BLEND_RGBA_ADD)

    # ── Animated flame tongues (20 dancing flames in two rings) ──
    for fi in range(20):
        seed_v = fi * 97 + 41
        ring = 0 if fi < 12 else 1
        n = 12 if ring == 0 else 8
        idx = fi if ring == 0 else fi - 12
        ang = (idx / float(n)) * math.tau
        dist = 35 + ring * 25
        base_x = sx + int(math.cos(ang) * dist)
        base_y = sy + int(math.sin(ang) * dist * 0.4)
        fh = int(35 + 20 * math.sin(t * 4.0 + seed_v * 0.7))
        fw = int(8 + 5 * math.sin(t * 3.0 + seed_v * 1.1))
        sway = int(6 * math.sin(t * 2.5 + seed_v * 0.3))
        _fs = pygame.Surface((fw * 4 + 30, fh + 30), pygame.SRCALPHA)
        _ox = fw * 2 + 15
        _oy = fh + 20
        _fpts = [(_ox - fw, _oy), (_ox + fw, _oy), (_ox + sway, _oy - fh)]
        r_val = min(255, 200 + (seed_v % 56))
        g_val = min(255, 80 + (seed_v % 80))
        pygame.draw.polygon(_fs, (r_val, g_val, 20, 190), _fpts)
        _fpts2 = [(_ox - fw // 2, _oy), (_ox + fw // 2, _oy), (_ox + sway // 2, _oy - fh * 2 // 3)]
        pygame.draw.polygon(_fs, (255, min(255, g_val + 80), 60, 230), _fpts2)
        screen.blit(_fs, (base_x - fw * 2 - 15, base_y - fh - 20))

    # ── Rising sparks / embers (50 particles) ──
    for i in range(50):
        sv = i * 137 + 53
        phase = (t * (0.5 + (sv % 10) * 0.06) + sv * 0.1) % 5.0
        if phase > 4.0:
            continue
        ex = sx + int(math.sin(sv * 1.7 + t * 1.2) * 80) + (sv % 80 - 40)
        ey = sy - 12 - int(phase * 50)
        sz = max(1, 4 - int(phase * 0.7))
        alpha_e = max(0, min(255, int(240 - phase * 50)))
        r_c = min(255, 200 + (sv % 56))
        g_c = min(255, 80 + (sv % 100))
        es = pygame.Surface((sz * 2 + 2, sz * 2 + 2), pygame.SRCALPHA)
        pygame.draw.circle(es, (r_c, g_c, 20, alpha_e), (sz + 1, sz + 1), sz)
        screen.blit(es, (ex - sz - 1, ey - sz - 1))

    # ── Rising smoke wisps (10 wisps) ──
    for si in range(10):
        sv = si * 211 + 17
        sp = (t * 0.3 + sv * 0.1) % 6.0
        smx = sx + int(math.sin(sv * 0.7 + t * 0.4) * 60) + (sv % 60 - 30)
        smy = sy - 60 - int(sp * 40)
        smr = int(12 + sp * 8)
        sma = max(0, min(45, int(40 - sp * 7)))
        sm_s = pygame.Surface((smr * 2, smr * 2), pygame.SRCALPHA)
        pygame.draw.circle(sm_s, (80, 78, 74, sma), (smr, smr), smr)
        screen.blit(sm_s, (smx - smr, smy - smr))

    # ── Heat distortion shimmer (wider, more lines) ──
    for hi in range(8):
        hv = hi * 73 + 19
        hx = sx - 80 + int(160 * ((hv * 7 + int(t * 30)) % 100) / 100.0)
        hy = sy - 70 - hi * 14
        hw = 30 + int(16 * math.sin(t * 3.0 + hv))
        ha = max(0, min(35, int(25 + 10 * math.sin(t * 2.0 + hv * 0.5))))
        hs = pygame.Surface((hw, 3), pygame.SRCALPHA)
        hs.fill((255, 240, 200, ha))
        screen.blit(hs, (hx, hy))

    # ── Torch stand flicker (6 hexagonal torch flames) ──
    for ti in range(6):
        ang = (ti / 6.0) * math.tau
        tx = sx + int(math.cos(ang) * 290)
        ty = sy + int(math.sin(ang) * 124)
        flicker = int(3 * math.sin(t * 7.0 + ti * 1.5))
        gs2 = pygame.Surface((28, 28), pygame.SRCALPHA)
        pygame.draw.circle(gs2, (255, 160, 40, 55), (14, 14), 12)
        screen.blit(gs2, (tx - 14, ty - 70 + flicker), special_flags=pygame.BLEND_RGBA_ADD)
