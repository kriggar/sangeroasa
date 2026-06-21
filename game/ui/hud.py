"""game/ui/hud.py — HUD + all in-game UI: minimap, spell bar, skill tree, spellbook,
inventory/character/quest/crafting/profession screens, target frame, panels, slots."""
import os
import json
import math
import random
import colorsys
from typing import Dict, List, Optional, Tuple, Any, Union, Set

import pygame
from pygame import Vector2

from game.constants import *
from game.utils import *
from game.vfx import *
from game.gameplay_math import *
from game.sprites import *
from game.data.classes import *
from game.data.icons import *
from game.data.items_data import *
from game.data.spell_layout import *
from game.data.world_data import *
from game.classes_runtime import *
from game.items import *
from game.dialogue import *
from game.render.props import *
from game.state import VENDOR_SHOPS, _HUD_STATE
from game.hud import (HUD_ORB_R as _HUD_ORB_R, HUD_GLOBE_STYLES as _HUD_GLOBE_STYLES,
    build_hud_globe_frame as _build_hud_globe_frame, build_hud_gem_fill as _build_hud_gem_fill,
    get_globe_value_font as _get_globe_value_font, get_potion_keybind_font as _get_potion_keybind_font,
    draw_hud_globe as _draw_hud_globe)

_PASSIVE_ICON_CACHE: Dict[Tuple[str, int], pygame.Surface] = {}
_TOOLTIP_SURFACE: Optional[pygame.Surface] = None
_TOOLTIP_LAST_ITEM: Optional[object] = None

__all__ = [
    '_hud_skewed_polygon',
    '_hud_skewed_polygon_clipped',
    '_hud_draw_gradient_poly',
    'draw_player_resource_bars',
    '_MINIMAP_MASK_CACHE',
    '_get_minimap_mask',
    'build_world_map_cache',
    'draw_wow_minimap',
    'draw_world_map_overlay',
    '_draw_radial_cooldown',
    'draw_target_frame',
    'draw_delete_confirm_dialog',
    'draw_buff_tracker',
    '_draw_spellbook_spell_tooltip',
    'draw_spellbook_overlay',
    'draw_spell_bar',
    'draw_spell_bar_vertical',
    'skill_tree_layout',
    'wrap_text_lines',
    'draw_skill_tree',
    '_blend_ui_color',
    '_brighten_ui_color',
    '_darken_ui_color',
    '_truncate_ui_text',
    '_SKILL_TREE_FONT_CACHE',
    '_skill_tree_font',
    '_skill_tree_node_spell_id',
    '_skill_tree_node_type_label',
    '_skill_tree_extract_mods',
    '_SKILL_TREE_BADGE_SOURCES',
    '_SKILL_TREE_BADGE_SHEET_CACHE',
    '_SKILL_TREE_BADGE_ICON_CACHE',
    '_load_skill_tree_badge_icon',
    '_skill_tree_upgrade_motif',
    '_skill_tree_node_bonus_lines',
    '_build_skill_tree_icon',
    '_draw_skill_tree_type_badge',
    '_draw_skill_tree_class_backdrop',
    'draw_skill_tree',
    'try_unlock_skill',
    'draw_backpack_button_realistic',
    'draw_item_bar',
    'build_gothic_cursor',
    'build_pouch_cursor',
    'build_vendor_shop_icon',
    'draw_gothic_cursor',
    'draw_crafting_ui',
    'draw_profession_screen',
    '_PARCHMENT_CACHE',
    '_make_parchment',
    '_draw_parchment_divider',
    '_draw_wax_seal',
    'draw_quest_log',
    'draw_npc_menu',
    'draw_inventory_screen',
    'can_item_equip_to_slot',
    'summarize_equipped_stats',
    'draw_character_screen',
    'load_all_saves',
    'save_all_saves',
    'UI_ASSETS',
    'load_ui_assets',
    'draw_nine_slice',
    '_SLOT_ICON_CACHE',
    '_SLOT_GHOST_ICON_HINTS',
    '_SLOT_PIXEL_ART',
    '_build_slot_ghost_icon',
    '_build_belt_slot_icon',
    'get_slot_icon',
    'draw_ui_slot',
    'draw_empty_equipment_slot',
    '_UI_PANEL_IMG',
    'get_ui_panel_img',
    'make_fallback_icon',
    '_draw_passive_glyph',
    'build_class_passive_icon',
    'load_spell_icons',
    'draw_ornate_panel',
    'draw_ornate_panel_backup',
    'draw_ui_tab',
    'draw_ui_button',
]


def _hud_skewed_polygon(rect: pygame.Rect, skew: int = 8) -> List[Tuple[int, int]]:
    """Return a 4-point parallelogram (slanted right): bottom shifted left, top shifted right."""
    return [
        (rect.left + skew, rect.top),
        (rect.right,       rect.top),
        (rect.right - skew, rect.bottom),
        (rect.left,         rect.bottom),
    ]


def _hud_skewed_polygon_clipped(rect: pygame.Rect, skew: int, fill_w: int) -> List[Tuple[int, int]]:
    """Skewed polygon clipped to a fill width from the left edge."""
    fill_w = max(0, min(fill_w, rect.width))
    if fill_w <= 0:
        return []
    # Top edge clip x: rect.left + skew + fill_w  (but capped to rect.right)
    top_right_x = min(rect.left + skew + fill_w, rect.right)
    # Bottom edge clip x: rect.left + fill_w (capped to rect.right - skew)
    bot_right_x = min(rect.left + fill_w, rect.right - skew)
    bot_right_x = max(bot_right_x, rect.left)
    return [
        (rect.left + skew, rect.top),
        (top_right_x,      rect.top),
        (bot_right_x,      rect.bottom),
        (rect.left,        rect.bottom),
    ]


def _hud_draw_gradient_poly(
    surface: pygame.Surface,
    rect: pygame.Rect,
    poly: List[Tuple[int, int]],
    top_col: Tuple[int, int, int],
    mid_col: Tuple[int, int, int],
    bot_col: Tuple[int, int, int],
) -> None:
    """Render the polygon with a vertical 3-stop gradient by clipping horizontal strips."""
    if not poly:
        return
    # Build a temporary surface that contains the gradient over the bounding box
    bbox = pygame.Rect(min(p[0] for p in poly), min(p[1] for p in poly),
                       max(p[0] for p in poly) - min(p[0] for p in poly),
                       max(p[1] for p in poly) - min(p[1] for p in poly))
    if bbox.width <= 0 or bbox.height <= 0:
        return
    grad = pygame.Surface((bbox.width, bbox.height), pygame.SRCALPHA)
    half = bbox.height // 2
    for _y in range(bbox.height):
        if _y < half and half > 0:
            _t = _y / max(1, half)
            _c = (int(top_col[0] + (mid_col[0] - top_col[0]) * _t),
                  int(top_col[1] + (mid_col[1] - top_col[1]) * _t),
                  int(top_col[2] + (mid_col[2] - top_col[2]) * _t))
        else:
            _t = (_y - half) / max(1, bbox.height - half)
            _c = (int(mid_col[0] + (bot_col[0] - mid_col[0]) * _t),
                  int(mid_col[1] + (bot_col[1] - mid_col[1]) * _t),
                  int(mid_col[2] + (bot_col[2] - mid_col[2]) * _t))
        pygame.draw.line(grad, (*_c, 255), (0, _y), (bbox.width, _y))
    # Mask to polygon
    mask = pygame.Surface((bbox.width, bbox.height), pygame.SRCALPHA)
    mask_poly = [(p[0] - bbox.left, p[1] - bbox.top) for p in poly]
    pygame.draw.polygon(mask, (255, 255, 255, 255), mask_poly)
    grad.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    surface.blit(grad, bbox.topleft)


# HUD globe rendering lives in game/hud/globe.py (imported above as
# _HUD_ORB_R / _HUD_GLOBE_STYLES / _build_hud_globe_frame / _build_hud_gem_fill /
# _get_globe_value_font / _get_potion_keybind_font / _draw_hud_globe).


def draw_player_resource_bars(
    screen: pygame.Surface,
    hp: float,
    max_hp: float,
    mana: float,
    max_mana: float,
    _ui_font: pygame.font.Font,
    tiny_font: pygame.font.Font,
    gold: int = 0,
    player_level: int = 1,
    xp: float = 0.0,
    xp_to_next: float = 100.0,
) -> None:
    """Deprecated — HP/MP globes, level medallion, gold plaque and XP strip are
    now drawn inside the unified ornate action belt by draw_spell_bar(). This
    stub remains for backwards compatibility and is a no-op."""
    return None


_MINIMAP_MASK_CACHE: Dict[int, pygame.Surface] = {}


def _get_minimap_mask(size: int) -> pygame.Surface:
    key = max(16, int(size))
    cached = _MINIMAP_MASK_CACHE.get(key)
    if isinstance(cached, pygame.Surface):
        return cached
    mask = pygame.Surface((key, key), pygame.SRCALPHA)
    r = key // 2
    pygame.gfxdraw.filled_circle(mask, r, r, r, (255, 255, 255, 255))
    pygame.gfxdraw.aacircle(mask, r, r, r, (255, 255, 255, 255))
    _MINIMAP_MASK_CACHE[key] = mask
    return mask


def build_world_map_cache(level_surface: pygame.Surface, world_w: int, world_h: int) -> Dict[str, object]:
    ww = max(1, int(world_w))
    wh = max(1, int(world_h))
    if isinstance(level_surface, pygame.Surface):
        src = level_surface
    else:
        src = pygame.Surface((max(128, ww // 6), max(128, wh // 6)), pygame.SRCALPHA)
        src.fill((26, 30, 38, 255))

    mini_target_w = min(1040, max(760, ww // 4))
    mini_scale = mini_target_w / float(ww)
    mini_w = max(240, int(ww * mini_scale))
    mini_h = max(180, int(wh * mini_scale))
    mini_surface = pygame.transform.smoothscale(src, (mini_w, mini_h))
    mini_tint = pygame.Surface((mini_w, mini_h), pygame.SRCALPHA)
    mini_tint.fill((20, 22, 28, 40))
    mini_surface.blit(mini_tint, (0, 0))

    full_max_w = max(620, SCREEN_WIDTH - 280)
    full_max_h = max(380, SCREEN_HEIGHT - 260)
    full_scale = min(full_max_w / float(ww), full_max_h / float(wh))
    full_w = max(320, int(ww * full_scale))
    full_h = max(220, int(wh * full_scale))
    full_surface = pygame.transform.smoothscale(src, (full_w, full_h))
    full_tint = pygame.Surface((full_w, full_h), pygame.SRCALPHA)
    full_tint.fill((18, 16, 12, 44))
    full_surface.blit(full_tint, (0, 0))

    return {
        "world_w": ww,
        "world_h": wh,
        "mini_surface": mini_surface,
        "full_surface": full_surface,
        "mini_scale_x": mini_w / float(ww),
        "mini_scale_y": mini_h / float(wh),
    }


def draw_wow_minimap(
    screen: pygame.Surface,
    cache: Dict[str, object],
    level_name: str,
    player_pos: Vector2,
    facing: int,
    portal_pos: Optional[Vector2],
    vendor_positions: List[Vector2],
    selected_target_pos: Optional[Vector2],
    title_font: pygame.font.Font,
    tiny_font: pygame.font.Font,
    world_time: float,
) -> pygame.Rect:
    mini_surface = cache.get("mini_surface")
    if not isinstance(mini_surface, pygame.Surface):
        return pygame.Rect(0, 0, 0, 0)
    world_w = max(1, int(cache.get("world_w", 1)))
    world_h = max(1, int(cache.get("world_h", 1)))
    scale_x = float(cache.get("mini_scale_x", mini_surface.get_width() / float(world_w)))
    scale_y = float(cache.get("mini_scale_y", mini_surface.get_height() / float(world_h)))

    diameter = 180
    ring = 18
    frame_size = diameter + ring * 2
    frame_rect = pygame.Rect(SCREEN_WIDTH - frame_size - 18, 16, frame_size, frame_size)
    circle_rect = frame_rect.inflate(-ring * 2, -ring * 2)
    center_x, center_y = circle_rect.center
    radius = circle_rect.width // 2

    src_size = min(mini_surface.get_width(), mini_surface.get_height(), 248)
    src_size = max(96, int(src_size))
    player_mx = float(player_pos.x) * scale_x
    player_my = float(player_pos.y) * scale_y
    src_x = int(player_mx - src_size * 0.5)
    src_y = int(player_my - src_size * 0.5)
    src_x = max(0, min(src_x, mini_surface.get_width() - src_size))
    src_y = max(0, min(src_y, mini_surface.get_height() - src_size))
    src_rect = pygame.Rect(src_x, src_y, src_size, src_size)

    cutout = pygame.Surface((src_size, src_size), pygame.SRCALPHA)
    cutout.blit(mini_surface, (0, 0), src_rect)
    disc = pygame.transform.smoothscale(cutout, (diameter, diameter))
    mask = _get_minimap_mask(diameter)
    disc.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

    shadow = pygame.Surface((frame_rect.width + 16, frame_rect.height + 16), pygame.SRCALPHA)
    pygame.draw.circle(shadow, (0, 0, 0, 120), (shadow.get_width() // 2, shadow.get_height() // 2), radius + ring + 8)
    screen.blit(shadow, (frame_rect.left - 8, frame_rect.top - 4))

    # Draw frame base first so the circular map remains visible.
    pygame.draw.circle(screen, (30, 28, 24), frame_rect.center, radius + ring + 1)
    screen.blit(disc, circle_rect.topleft)
    pygame.draw.circle(screen, (196, 168, 102), frame_rect.center, radius + ring + 1, 3)
    pygame.draw.circle(screen, (108, 96, 72), frame_rect.center, radius + ring - 6, 2)

    def world_to_minimap(pos: Optional[Vector2]) -> Optional[Tuple[int, int]]:
        if not isinstance(pos, Vector2):
            return None
        mx = float(pos.x) * scale_x
        my = float(pos.y) * scale_y
        u = (mx - src_rect.left) / float(src_rect.width)
        v = (my - src_rect.top) / float(src_rect.height)
        if u < 0.0 or u > 1.0 or v < 0.0 or v > 1.0:
            return None
        px = circle_rect.left + int(u * circle_rect.width)
        py = circle_rect.top + int(v * circle_rect.height)
        if (px - center_x) ** 2 + (py - center_y) ** 2 > (radius - 3) ** 2:
            return None
        return px, py

    portal_pt = world_to_minimap(portal_pos)
    if portal_pt is not None:
        px, py = portal_pt
        diamond = [(px, py - 5), (px + 5, py), (px, py + 5), (px - 5, py)]
        pygame.draw.polygon(screen, (238, 206, 116), diamond)
        pygame.draw.polygon(screen, (62, 50, 24), diamond, 1)

    for vendor_pos in vendor_positions:
        vp = world_to_minimap(vendor_pos)
        if vp is None:
            continue
        pygame.draw.circle(screen, (106, 208, 224), vp, 3)
        pygame.draw.circle(screen, (24, 52, 60), vp, 3, 1)

    target_pt = world_to_minimap(selected_target_pos)
    if target_pt is not None:
        tx, ty = target_pt
        pygame.draw.circle(screen, (236, 88, 76), (tx, ty), 4, 1)
        pygame.draw.line(screen, (236, 88, 76), (tx - 4, ty), (tx + 4, ty), 1)
        pygame.draw.line(screen, (236, 88, 76), (tx, ty - 4), (tx, ty + 4), 1)

    player_pt = world_to_minimap(player_pos)
    if player_pt is None:
        player_pt = (center_x, center_y)
    px, py = player_pt
    dir_x = 1 if int(facing) >= 0 else -1
    arrow = [(px + dir_x * 8, py), (px - dir_x * 6, py - 5), (px - dir_x * 6, py + 5)]
    pygame.draw.polygon(screen, (248, 240, 222), arrow)
    pygame.draw.polygon(screen, (38, 34, 24), arrow, 1)

    north_s = tiny_font.render("N", True, (232, 220, 186))
    screen.blit(north_s, (frame_rect.centerx - north_s.get_width() // 2, frame_rect.top + 2))

    zone_name = "Raven Hollow" if str(level_name) == "town" else "The Wilderness"
    zone_s = title_font.render(zone_name, True, (216, 206, 178))
    screen.blit(zone_s, (frame_rect.centerx - zone_s.get_width() // 2, frame_rect.top - 20))

    hour = int(world_time) % 24
    minute = int((float(world_time) - math.floor(float(world_time))) * 60.0) % 60
    clock_s = tiny_font.render(f"{hour:02d}:{minute:02d}", True, (172, 182, 198))
    hint_s = tiny_font.render("[M] Map", True, (188, 172, 122))
    screen.blit(clock_s, (frame_rect.centerx - clock_s.get_width() // 2, frame_rect.bottom + 2))
    screen.blit(hint_s, (frame_rect.centerx - hint_s.get_width() // 2, frame_rect.bottom + 18))

    return pygame.Rect(frame_rect.left - 6, frame_rect.top - 24, frame_rect.width + 12, frame_rect.height + 50)


def draw_world_map_overlay(
    screen: pygame.Surface,
    cache: Dict[str, object],
    level_name: str,
    player_pos: Vector2,
    facing: int,
    camera: Vector2,
    portal_pos: Optional[Vector2],
    vendor_positions: List[Vector2],
    selected_target_pos: Optional[Vector2],
    title_font: pygame.font.Font,
    node_font: pygame.font.Font,
    tiny_font: pygame.font.Font,
) -> None:
    full_surface = cache.get("full_surface")
    if not isinstance(full_surface, pygame.Surface):
        return
    world_w = max(1, int(cache.get("world_w", 1)))
    world_h = max(1, int(cache.get("world_h", 1)))

    fade = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    fade.fill((0, 0, 0, 188))
    screen.blit(fade, (0, 0))

    panel = pygame.Rect(74, 44, SCREEN_WIDTH - 148, SCREEN_HEIGHT - 88)
    draw_ornate_panel(screen, panel)

    zone_name = "Raven Hollow" if str(level_name) == "town" else "The Wilderness"
    title_s = title_font.render(f"{zone_name} Map", True, (236, 220, 182))
    hint_s = tiny_font.render("[M] Close Map", True, (188, 174, 132))
    screen.blit(title_s, (panel.left + 22, panel.top + 14))
    screen.blit(hint_s, (panel.right - hint_s.get_width() - 20, panel.top + 20))

    map_slot = pygame.Rect(panel.left + 26, panel.top + 62, panel.width - 52, panel.height - 120)
    pygame.draw.rect(screen, (12, 14, 18), map_slot, border_radius=10)
    pygame.draw.rect(screen, (82, 78, 66), map_slot, 1, border_radius=10)

    map_rect = full_surface.get_rect(center=map_slot.center)
    screen.blit(full_surface, map_rect.topleft)

    for i in range(1, 4):
        gx = map_rect.left + (map_rect.width * i) // 4
        gy = map_rect.top + (map_rect.height * i) // 4
        pygame.draw.line(screen, (54, 52, 48), (gx, map_rect.top), (gx, map_rect.bottom), 1)
        pygame.draw.line(screen, (54, 52, 48), (map_rect.left, gy), (map_rect.right, gy), 1)

    def world_to_full(pos: Optional[Vector2]) -> Optional[Tuple[int, int]]:
        if not isinstance(pos, Vector2):
            return None
        ux = clamp(float(pos.x) / float(world_w), 0.0, 1.0)
        uy = clamp(float(pos.y) / float(world_h), 0.0, 1.0)
        px = map_rect.left + int(ux * (map_rect.width - 1))
        py = map_rect.top + int(uy * (map_rect.height - 1))
        return px, py

    top_left = world_to_full(Vector2(camera.x, camera.y))
    bottom_right = world_to_full(Vector2(camera.x + SCREEN_WIDTH, camera.y + SCREEN_HEIGHT))
    if top_left is not None and bottom_right is not None:
        vx = min(top_left[0], bottom_right[0])
        vy = min(top_left[1], bottom_right[1])
        vw = max(8, abs(bottom_right[0] - top_left[0]))
        vh = max(8, abs(bottom_right[1] - top_left[1]))
        view_rect = pygame.Rect(vx, vy, vw, vh).clip(map_rect)
        pygame.draw.rect(screen, (204, 184, 118), view_rect, 2, border_radius=4)

    portal_pt = world_to_full(portal_pos)
    if portal_pt is not None:
        px, py = portal_pt
        diamond = [(px, py - 8), (px + 8, py), (px, py + 8), (px - 8, py)]
        pygame.draw.polygon(screen, (244, 214, 132), diamond)
        pygame.draw.polygon(screen, (64, 52, 24), diamond, 1)

    for vendor_pos in vendor_positions:
        vp = world_to_full(vendor_pos)
        if vp is None:
            continue
        pygame.draw.circle(screen, (104, 202, 220), vp, 4)
        pygame.draw.circle(screen, (24, 52, 62), vp, 4, 1)

    target_pt = world_to_full(selected_target_pos)
    if target_pt is not None:
        tx, ty = target_pt
        pygame.draw.circle(screen, (236, 86, 76), (tx, ty), 6, 1)
        pygame.draw.line(screen, (236, 86, 76), (tx - 6, ty), (tx + 6, ty), 1)
        pygame.draw.line(screen, (236, 86, 76), (tx, ty - 6), (tx, ty + 6), 1)

    player_pt = world_to_full(player_pos)
    if player_pt is not None:
        px, py = player_pt
        dir_x = 1 if int(facing) >= 0 else -1
        arrow = [(px + dir_x * 12, py), (px - dir_x * 8, py - 7), (px - dir_x * 8, py + 7)]
        pygame.draw.polygon(screen, (252, 246, 226), arrow)
        pygame.draw.polygon(screen, (40, 34, 24), arrow, 1)

    coords_s = node_font.render(f"Player: X {int(player_pos.x)}  Y {int(player_pos.y)}", True, (212, 206, 190))
    legend_s = tiny_font.render("Gold: Portal  Blue: Vendors  Red: Target", True, (176, 178, 182))
    screen.blit(coords_s, (panel.left + 26, panel.bottom - 48))
    screen.blit(legend_s, (panel.left + 26, panel.bottom - 26))


# =============================================================================
#  WoW-STYLE HUD HELPERS
# =============================================================================

def _draw_radial_cooldown(
    surface: pygame.Surface,
    rect: pygame.Rect,
    pct: float,
    color: Tuple[int, ...] = (12, 12, 18, 215),
) -> None:
    """Sweep a clock-face cooldown overlay over `rect` (0=none, 1=full)."""
    pct = clamp(pct, 0.0, 1.0)
    if pct <= 0.0:
        return
    local = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    cx, cy = rect.width // 2, rect.height // 2
    r = max(cx, cy) + 3
    start = -math.pi / 2
    sweep = pct * 2 * math.pi
    steps = max(24, int(sweep * 32))
    pts: List[Tuple[float, float]] = [(float(cx), float(cy))]
    for i in range(steps + 1):
        a = start + (i / steps) * sweep
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    if len(pts) >= 3:
        pygame.draw.polygon(local, color, pts)
    surface.blit(local, rect.topleft)


def draw_target_frame(
    screen: pygame.Surface,
    target_name: str,
    target_hp: float,
    target_max_hp: float,
    target_level: int,
    font: pygame.font.Font,
) -> pygame.Rect:
    """Draw a WoW-style enemy target frame at the top-center of the screen."""
    ticks = pygame.time.get_ticks()
    pw, ph = 288, 62
    px = SCREEN_WIDTH // 2 - pw // 2
    py = 18
    panel = pygame.Rect(px, py, pw, ph)

    # Animated outer glow halo (red tint)
    ga = int(30 + 20 * math.sin(ticks * 0.0022))
    gsurf = pygame.Surface((pw + 14, ph + 14), pygame.SRCALPHA)
    pygame.draw.rect(gsurf, (210, 50, 50, ga), gsurf.get_rect(), border_radius=14)
    screen.blit(gsurf, (px - 7, py - 7))

    # Panel BG
    bg = pygame.Surface((pw, ph), pygame.SRCALPHA)
    pygame.draw.rect(bg, (16, 10, 13, 240), bg.get_rect(), border_radius=10)
    screen.blit(bg, panel.topleft)

    # Border (double line)
    pygame.draw.rect(screen, (90, 32, 32), panel, 2, border_radius=10)
    ib = panel.inflate(-2, -2)
    ib_s = pygame.Surface((ib.width, ib.height), pygame.SRCALPHA)
    pygame.draw.rect(ib_s, (185, 62, 62, 160), ib_s.get_rect(), 1, border_radius=9)
    screen.blit(ib_s, ib.topleft)

    # Corner accent dots
    for cdx, cdy in [(px + 7, py + 7), (px + pw - 7, py + 7), (px + 7, py + ph - 7), (px + pw - 7, py + ph - 7)]:
        pygame.draw.circle(screen, (200, 70, 70), (cdx, cdy), 3)

    # Name + level
    hp_ratio = clamp(float(target_hp) / max(1.0, float(target_max_hp)), 0.0, 1.0)
    name_col = (248, 208, 208) if hp_ratio > 0.3 else (255, 80, 80)
    name_s = font.render(str(target_name), True, name_col)
    lvl_s = font.render(f"Lv.{target_level}", True, (162, 152, 142))
    screen.blit(name_s, (panel.left + 12, panel.top + 8))
    screen.blit(lvl_s, (panel.right - lvl_s.get_width() - 12, panel.top + 8))

    # HP bar
    bar = pygame.Rect(panel.left + 10, panel.top + 30, panel.width - 20, 18)
    pygame.draw.rect(screen, (24, 8, 8), bar, border_radius=6)
    if hp_ratio > 0.0:
        fw = max(0, int((bar.width - 4) * hp_ratio))
        if fw > 0:
            if hp_ratio > 0.5:
                fc = (190, 50, 50)
            elif hp_ratio > 0.25:
                fc = (215, 130, 40)
            else:
                fa = int(80 + 80 * abs(math.sin(ticks * 0.008)))
                fc = (230, 40 + fa // 5, 40)
            fill_r = pygame.Rect(bar.left + 2, bar.top + 2, fw, bar.height - 4)
            pygame.draw.rect(screen, fc, fill_r, border_radius=5)
            if fw > 8:
                sh = pygame.Surface((fw, 4), pygame.SRCALPHA)
                sh.fill((255, 200, 200, 55))
                screen.blit(sh, (fill_r.left, fill_r.top))
    pygame.draw.rect(screen, (120, 44, 44), bar, 1, border_radius=6)
    hp_t = font.render(f"{int(target_hp)} / {int(target_max_hp)}", True, (218, 198, 198))
    screen.blit(hp_t, (bar.centerx - hp_t.get_width() // 2, bar.top + 2))

    return panel


def draw_delete_confirm_dialog(
    screen: pygame.Surface,
    item: Dict[str, object],
    typed: str,
    font: pygame.font.Font,
    small_font: pygame.font.Font,
) -> pygame.Rect:
    """Draw WoW-style delete confirmation dialog. Returns the cancel button rect."""
    ticks = pygame.time.get_ticks()
    TARGET = "DELETE"
    confirmed = typed.upper() == TARGET

    pw, ph = 420, 220
    px = SCREEN_WIDTH // 2 - pw // 2
    py = SCREEN_HEIGHT // 2 - ph // 2

    # Dim backdrop
    dim = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    dim.fill((0, 0, 0, 160))
    screen.blit(dim, (0, 0))

    # Panel
    panel_surf = pygame.Surface((pw, ph), pygame.SRCALPHA)
    pygame.draw.rect(panel_surf, (18, 14, 12, 245), panel_surf.get_rect(), border_radius=12)
    screen.blit(panel_surf, (px, py))
    pygame.draw.rect(screen, (160, 40, 40), pygame.Rect(px, py, pw, ph), 2, border_radius=12)

    # Animated red inner glow
    _ga = int(40 + 22 * math.sin(ticks * 0.004))
    _gs = pygame.Surface((pw + 8, ph + 8), pygame.SRCALPHA)
    pygame.draw.rect(_gs, (200, 30, 30, _ga), _gs.get_rect(), 4, border_radius=14)
    screen.blit(_gs, (px - 4, py - 4))

    # Item icon + name header
    icon = resolve_item_icon(item, 40)
    if isinstance(icon, pygame.Surface):
        screen.blit(icon, (px + 16, py + 14))
    item_name = str(item.get("name", "item"))
    rarity = str(item.get("rarity", "common")).lower()
    rarity_colors = {
        "common": (200, 200, 200), "uncommon": (30, 200, 80),
        "rare": (60, 130, 255), "epic": (160, 60, 240), "legendary": (255, 140, 0),
    }
    name_col = rarity_colors.get(rarity, (200, 200, 200))
    name_surf = font.render(item_name, True, name_col)
    screen.blit(name_surf, (px + 64, py + 20))

    # Warning line
    warn = small_font.render("This item will be permanently destroyed.", True, (200, 170, 130))
    screen.blit(warn, (px + pw // 2 - warn.get_width() // 2, py + 62))

    # Instruction
    instr = small_font.render('Type  "DELETE"  to confirm:', True, (160, 150, 140))
    screen.blit(instr, (px + pw // 2 - instr.get_width() // 2, py + 88))

    # Text input box
    box_w, box_h = 220, 34
    box_x = px + pw // 2 - box_w // 2
    box_y = py + 112
    box_col = (40, 10, 10) if not confirmed else (10, 40, 10)
    pygame.draw.rect(screen, box_col, pygame.Rect(box_x, box_y, box_w, box_h), border_radius=6)
    border_col = (220, 60, 60) if not confirmed else (60, 220, 80)
    pygame.draw.rect(screen, border_col, pygame.Rect(box_x, box_y, box_w, box_h), 2, border_radius=6)

    # Typed text with caret
    display_text = typed + ("|" if (ticks // 500) % 2 == 0 else "")
    text_col = (255, 100, 100) if not confirmed else (100, 255, 100)
    typed_surf = font.render(display_text, True, text_col)
    screen.blit(typed_surf, (box_x + box_w // 2 - typed_surf.get_width() // 2,
                             box_y + box_h // 2 - typed_surf.get_height() // 2))

    # Partial match hint (highlight matched prefix in green)
    matched = 0
    for i, ch in enumerate(typed.upper()):
        if i < len(TARGET) and ch == TARGET[i]:
            matched += 1
        else:
            break
    hint_parts = []
    for i, ch in enumerate(TARGET):
        col = (80, 220, 80) if i < matched else (120, 100, 100)
        hint_parts.append((ch, col))
    hint_x = px + pw // 2 - (small_font.size(TARGET)[0]) // 2
    for ch, col in hint_parts:
        ch_s = small_font.render(ch, True, col)
        screen.blit(ch_s, (hint_x, py + 152))
        hint_x += ch_s.get_width() + 1

    # Cancel button
    cancel_w, cancel_h = 100, 30
    cancel_rect = pygame.Rect(px + pw // 2 - cancel_w // 2, py + ph - cancel_h - 10, cancel_w, cancel_h)
    mouse_pos = pygame.mouse.get_pos()
    cancel_hover = cancel_rect.collidepoint(mouse_pos)
    cancel_bg = (70, 30, 30) if not cancel_hover else (110, 40, 40)
    pygame.draw.rect(screen, cancel_bg, cancel_rect, border_radius=6)
    pygame.draw.rect(screen, (160, 60, 60), cancel_rect, 1, border_radius=6)
    cancel_label = small_font.render("Cancel  [Esc]", True, (200, 160, 160))
    screen.blit(cancel_label, (cancel_rect.centerx - cancel_label.get_width() // 2,
                               cancel_rect.centery - cancel_label.get_height() // 2))

    return cancel_rect


def draw_buff_tracker(
    screen: pygame.Surface,
    damage_boost_timer: float,
    speed_boost_timer: float,
    font: pygame.font.Font,
) -> None:
    """Draw active player buff icons anchored below the player resource panel."""
    ticks = pygame.time.get_ticks()
    slot_size = 40
    gap = 6
    # Anchored just below player panel (panel is at y=104, h=140 → bottom=244)
    bx, by = 24, 252
    buffs: List[Tuple[str, float, float, Tuple[int, int, int]]] = []
    if damage_boost_timer > 0.0:
        buffs.append(("ATK", damage_boost_timer, 120.0, (230, 140, 50)))
    if speed_boost_timer > 0.0:
        buffs.append(("SPD", speed_boost_timer, 60.0, (80, 220, 130)))
    for label, timer, max_dur, col in buffs:
        slot = pygame.Rect(bx, by, slot_size, slot_size)
        # Animated glow
        pa = int(22 + 14 * math.sin(ticks * 0.003))
        glow = pygame.Surface((slot_size + 10, slot_size + 10), pygame.SRCALPHA)
        pygame.draw.rect(glow, (*col, pa), glow.get_rect(), border_radius=10)
        screen.blit(glow, (slot.left - 5, slot.top - 5))
        # Slot bg
        pygame.draw.rect(screen, (20, 20, 26), slot, border_radius=8)
        # Radial drain shows time remaining
        remain_pct = clamp(timer / max(0.001, max_dur), 0.0, 1.0)
        _draw_radial_cooldown(screen, slot, 1.0 - remain_pct, (14, 14, 20, 185))
        # Border
        pygame.draw.rect(screen, col, slot, 2, border_radius=8)
        # Label + timer
        lbl = font.render(label, True, col)
        screen.blit(lbl, (slot.centerx - lbl.get_width() // 2, slot.top + 5))
        dur = font.render(f"{int(timer)}s", True, (215, 210, 200))
        screen.blit(dur, (slot.centerx - dur.get_width() // 2, slot.bottom - dur.get_height() - 3))
        bx += slot_size + gap


def _draw_spellbook_spell_tooltip(
    screen: pygame.Surface,
    spell: Dict[str, object],
    slot: pygame.Rect,
    class_id: str,
    mana_mult: float,
    font: pygame.font.Font,
) -> None:
    mana_cost = spell_mana_cost(spell, class_id) * mana_mult
    cooldown = float(spell.get("cooldown", 0.0))
    damage = float(spell.get("damage", 0.0))
    kind = str(spell.get("kind", "spell"))
    kind_desc = {
        "projectile": "Launches a fast projectile that hits in a line.",
        "nova": "Expands outward hitting all enemies in a ring.",
        "orb": "Places a pulsing orb that repeatedly damages nearby enemies.",
        "ward": "Creates a standing zone dealing damage over time.",
        "melee_arc": "Performs a close melee arc in front of you.",
        "cone": "Sweeps a wide cone forward.",
        "pillar": "Raises a blocking pillar that damages on impact.",
        "ultimate": "Channels a catastrophic elemental storm.",
    }.get(kind, "Cast a combat ability.")
    lines: List[str] = [str(spell.get("name", "Spell")), kind_desc]
    if bool(spell.get("is_ultimate", False)):
        lines.append("ULTIMATE — Strongest class finisher.")
    lines.append(f"Damage: {int(damage)}   Mana: {int(mana_cost)}   CD: {cooldown:.1f}s")
    tw = max(font.size(l)[0] for l in lines) + 28
    th = 10 + len(lines) * 22 + 10
    tx = min(slot.right + 10, SCREEN_WIDTH - tw - 8)
    ty = clamp(slot.top - th // 2, 8, SCREEN_HEIGHT - th - 8)
    tip_bg = pygame.Surface((tw, th), pygame.SRCALPHA)
    pygame.draw.rect(tip_bg, (18, 16, 22, 245), tip_bg.get_rect(), border_radius=8)
    pygame.draw.rect(tip_bg, (148, 122, 74), tip_bg.get_rect(), 1, border_radius=8)
    screen.blit(tip_bg, (tx, ty))
    for li, line in enumerate(lines):
        col = (252, 232, 184) if li == 0 else (202, 194, 174)
        ls = font.render(line, True, col)
        screen.blit(ls, (tx + 14, ty + 10 + li * 22))


def draw_spellbook_overlay(
    screen: pygame.Surface,
    spellbook: List[Dict[str, object]],
    spell_icons: Dict[str, pygame.Surface],
    unlocked_skills: Set[str],
    active_tab: str,
    class_id: str,
    font: pygame.font.Font,
    small_font: pygame.font.Font,
    title_font: pygame.font.Font,
) -> Dict[str, pygame.Rect]:
    """Clean, minimal fullscreen spellbook overlay. Returns clickable rects."""
    _pal = CLASS_PALETTES.get(class_id, CLASS_PALETTES["default"])
    accent = _pal["primary"]

    # Flat dim backdrop
    dim = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    dim.fill((0, 0, 0, 210))
    screen.blit(dim, (0, 0))

    # Flat panel
    pw, ph = 920, 640
    panel = pygame.Rect(SCREEN_WIDTH // 2 - pw // 2, SCREEN_HEIGHT // 2 - ph // 2, pw, ph)
    bg_surf = pygame.Surface((pw, ph), pygame.SRCALPHA)
    bg_surf.fill((16, 18, 24, 244))
    screen.blit(bg_surf, panel.topleft)
    pygame.draw.rect(screen, (68, 72, 86), panel, 1, border_radius=6)

    result_rects: Dict[str, pygame.Rect] = {}
    class_name = CLASS_ARCHETYPES.get(class_id, {}).get("name", class_id.title())

    # Header: title left, close right, thin divider
    title = title_font.render(f"Spellbook — {class_name}", True, (236, 230, 214))
    _hdr_cy = panel.top + 30
    screen.blit(title, (panel.left + 24, _hdr_cy - title.get_height() // 2))
    cls_s = font.render("[N] Close", True, (148, 144, 136))
    screen.blit(cls_s, (panel.right - cls_s.get_width() - 24, _hdr_cy - cls_s.get_height() // 2))
    pygame.draw.line(screen, (52, 56, 68), (panel.left + 20, panel.top + 56), (panel.right - 20, panel.top + 56), 1)

    # Tabs — text with underline for active
    tabs = [("class", "Spells"), ("passive", "Passive"), ("general", "General")]
    tab_x = panel.left + 24
    tab_y = panel.top + 70
    for tab_id, tab_label in tabs:
        is_active = tab_id == active_tab
        lbl_col = accent if is_active else (158, 154, 146)
        lbl = font.render(tab_label, True, lbl_col)
        tab_rect = pygame.Rect(tab_x - 6, tab_y - 4, lbl.get_width() + 12, lbl.get_height() + 10)
        result_rects[f"tab_{tab_id}"] = tab_rect
        screen.blit(lbl, (tab_x, tab_y))
        if is_active:
            pygame.draw.line(screen, accent, (tab_x, tab_y + lbl.get_height() + 4), (tab_x + lbl.get_width(), tab_y + lbl.get_height() + 4), 2)
        tab_x += lbl.get_width() + 28

    grid_top = tab_y + 42
    grid_rect = pygame.Rect(panel.left + 24, grid_top, panel.width - 48, panel.bottom - grid_top - 44)

    passive_effects = class_passive_effects(class_id)
    passive_mana_mult = max(0.1, float(passive_effects.get("mana_cost_mult", 1.0)))
    mouse_pos = pygame.mouse.get_pos()
    hovered_spell: Optional[Dict[str, object]] = None
    hovered_slot_rect: Optional[pygame.Rect] = None

    if active_tab == "class":
        slot_size = 64
        gap_x = 18
        gap_y = 36  # room for name label
        cols = 8
        row_stride = slot_size + gap_y

        for i, spell in enumerate(spellbook):
            col_i = i % cols
            row_i = i // cols
            sx = grid_rect.left + col_i * (slot_size + gap_x)
            sy = grid_rect.top + row_i * row_stride
            slot = pygame.Rect(sx, sy, slot_size, slot_size)

            spell_id = str(spell.get("id", ""))
            is_unlocked = str(spell.get("skill", "")) in unlocked_skills
            is_ultimate = bool(spell.get("is_ultimate", False))

            # Flat slot background
            pygame.draw.rect(screen, (24, 26, 32), slot, border_radius=4)

            # Icon
            icon = spell_icons.get(spell_id)
            if isinstance(icon, pygame.Surface):
                icon_s = pygame.transform.smoothscale(icon, (slot_size - 8, slot_size - 8))
                if not is_unlocked:
                    grey_ov = pygame.Surface(icon_s.get_size(), pygame.SRCALPHA)
                    grey_ov.fill((20, 20, 30, 170))
                    icon_s = icon_s.copy()
                    icon_s.blit(grey_ov, (0, 0))
                screen.blit(icon_s, (slot.left + 4, slot.top + 4))

            # Lock marker
            if not is_unlocked:
                lk = small_font.render("LOCKED", True, (120, 116, 108))
                _lk_bg = pygame.Surface((lk.get_width() + 6, lk.get_height() + 2), pygame.SRCALPHA)
                _lk_bg.fill((0, 0, 0, 180))
                screen.blit(_lk_bg, (slot.centerx - _lk_bg.get_width() // 2, slot.centery - _lk_bg.get_height() // 2))
                screen.blit(lk, (slot.centerx - lk.get_width() // 2, slot.centery - lk.get_height() // 2))

            hovered = slot.collidepoint(mouse_pos)
            if hovered:
                hovered_spell = spell
                hovered_slot_rect = slot

            # Border
            if hovered:
                bdr = accent
                bdr_w = 2
            elif is_ultimate and is_unlocked:
                bdr = (200, 168, 90)
                bdr_w = 1
            elif is_unlocked:
                bdr = (84, 86, 100)
                bdr_w = 1
            else:
                bdr = (46, 48, 58)
                bdr_w = 1
            pygame.draw.rect(screen, bdr, slot, bdr_w, border_radius=4)

            # Spell name under slot
            name_col = accent if (is_unlocked and hovered) else ((204, 198, 182) if is_unlocked else (100, 98, 92))
            nm_text = str(spell.get("name", ""))
            nm = small_font.render(nm_text, True, name_col)
            if nm.get_width() > slot_size + gap_x - 4:
                # truncate
                while nm.get_width() > slot_size + gap_x - 4 and len(nm_text) > 2:
                    nm_text = nm_text[:-1]
                    nm = small_font.render(nm_text + "…", True, name_col)
            screen.blit(nm, (slot.centerx - nm.get_width() // 2, slot.bottom + 6))

        if hovered_spell is not None and hovered_slot_rect is not None:
            _draw_spellbook_spell_tooltip(screen, hovered_spell, hovered_slot_rect, class_id, passive_mana_mult, font)

    elif active_tab == "passive":
        passive = class_passive_data(class_id)
        passive_name = str(passive.get("name", "Class Passive"))
        passive_desc = str(passive.get("desc", ""))
        icon = spell_icons.get(f"passive_{class_id}")
        if not isinstance(icon, pygame.Surface):
            icon = build_class_passive_icon(class_id, 80)
        icon_s = pygame.transform.smoothscale(icon, (80, 80))
        ix, iy = grid_rect.left + 8, grid_rect.top + 8
        pygame.draw.rect(screen, (24, 26, 32), pygame.Rect(ix, iy, 80, 80), border_radius=4)
        screen.blit(icon_s, (ix, iy))
        pygame.draw.rect(screen, (84, 86, 100), pygame.Rect(ix, iy, 80, 80), 1, border_radius=4)

        name_s = title_font.render(passive_name, True, accent)
        screen.blit(name_s, (ix + 100, iy + 2))
        desc_lines = wrap_text_lines(font, passive_desc, grid_rect.width - 130, max_lines=5)
        for li, line in enumerate(desc_lines):
            ls = font.render(line, True, (196, 192, 176))
            screen.blit(ls, (ix + 100, iy + 34 + li * 22))
        eff_y = iy + 100 + max(0, (len(desc_lines) - 3)) * 22
        for eli, eline in enumerate(class_passive_effect_lines(passive)):
            es = font.render(f"•  {eline}", True, (170, 196, 234))
            screen.blit(es, (ix + 100, eff_y + eli * 22))

    else:
        hint = font.render("General abilities are available to all classes.", True, (158, 154, 146))
        hint2 = font.render("More content coming in future updates.", True, (120, 118, 110))
        screen.blit(hint, (grid_rect.centerx - hint.get_width() // 2, grid_rect.centery - 14))
        screen.blit(hint2, (grid_rect.centerx - hint2.get_width() // 2, grid_rect.centery + 10))

    # Footer
    pygame.draw.line(screen, (52, 56, 68), (panel.left + 20, panel.bottom - 34), (panel.right - 20, panel.bottom - 34), 1)
    footer = small_font.render("Q W E R T 1 2 3  —  Action bar    [TAB] Switch tab    [N] Close", True, (120, 118, 110))
    screen.blit(footer, (panel.left + 24, panel.bottom - 26))

    return result_rects


def draw_spell_bar(
    screen: pygame.Surface,
    spellbook: List[Dict[str, object]],
    spell_icons: Dict[str, pygame.Surface],
    cooldowns: Dict[str, float],
    unlocked_skills: Set[str],
    current_mana: float,
    selected_idx: int,
    font: pygame.font.Font,
    small_font: pygame.font.Font,
    class_id: str = "",
    max_mana: float = 200.0,
    spell_global_cooldown: float = 0.0,
    global_cd_max: float = 0.5,
    keybinds: Optional[List[int]] = None,
    keybind_editing: int = -1,
    hp: float = 0.0,
    max_hp: float = 0.0,
    gold: int = 0,
    player_level: int = 1,
    xp: float = 0.0,
    xp_to_next: float = 100.0,
    item_inventory: Optional[List] = None,
    potion_shared_cd_pct: float = 0.0,
) -> Tuple[List[pygame.Rect], Dict[int, pygame.Rect]]:
    """Compact unified action belt with integrated spell slots and consumable slots.

    Returns (spell_slot_rects, potion_slot_rects).
    Layout: [HP orb] [passive|spells|div|potions] [MP orb]
    All ornate brass/gold, but scaled down ~35% from the previous oversized version.
    """
    passive = class_passive_data(class_id)
    passive_effects = class_passive_effects(class_id)
    passive_mana_mult = max(0.1, float(passive_effects.get("mana_cost_mult", 1.0)))

    _pal = CLASS_PALETTES.get(class_id, CLASS_PALETTES["default"])
    accent = _pal["primary"]

    visible_slots: List[Tuple[int, Dict[str, object]]] = []
    for idx, spell in enumerate(spellbook):
        if str(spell.get("skill", "")) in unlocked_skills:
            visible_slots.append((idx, spell))
    slot_count = len(visible_slots)

    if item_inventory is None:
        item_inventory = []
    max_potion_slots = 4

    ticks = pygame.time.get_ticks()
    t_sec = ticks / 1000.0

    # ── State tracking: damage/spend flashes, level pop, xp flash ──
    _last_tick = _HUD_STATE["last_tick_ms"]
    dt = clamp(t_sec - _last_tick, 0.0, 0.1) if _last_tick > 0 else 0.016
    _HUD_STATE["last_tick_ms"] = t_sec
    _last_hp = _HUD_STATE["last_hp"]
    _last_mp = _HUD_STATE["last_mana"]
    if _last_hp >= 0 and hp < _last_hp - 0.5:
        _HUD_STATE["hp_flash"] = 1.0
    if _last_mp >= 0 and current_mana < _last_mp - 0.5:
        _HUD_STATE["mp_flash"] = 1.0
    _HUD_STATE["last_hp"] = float(hp)
    _HUD_STATE["last_mana"] = float(current_mana)
    _HUD_STATE["hp_flash"] = max(0.0, _HUD_STATE["hp_flash"] - dt * 2.4)
    _HUD_STATE["mp_flash"] = max(0.0, _HUD_STATE["mp_flash"] - dt * 2.4)
    if _HUD_STATE["last_level"] >= 0 and player_level > _HUD_STATE["last_level"]:
        _HUD_STATE["level_pop"] = 1.0
    _HUD_STATE["last_level"] = float(player_level)
    _HUD_STATE["level_pop"] = max(0.0, _HUD_STATE["level_pop"] - dt * 1.0)
    _last_xp = _HUD_STATE["last_xp"]
    if _last_xp >= 0 and xp > _last_xp + 0.01:
        _HUD_STATE["xp_flash"] = 1.0
    _HUD_STATE["last_xp"] = float(xp)
    _HUD_STATE["xp_flash"] = max(0.0, _HUD_STATE["xp_flash"] - dt * 1.6)

    hp_ratio = 0.0 if max_hp <= 0 else clamp(hp / max_hp, 0.0, 1.0)
    mp_ratio = clamp(current_mana / max(1.0, max_mana), 0.0, 1.0)
    xp_ratio = clamp(float(xp) / max(1.0, float(xp_to_next)), 0.0, 1.0)

    low_hp_pulse = 0.0
    if hp_ratio < 0.28:
        low_hp_pulse = (0.5 + 0.5 * math.sin(t_sec * 6.5)) * (1.0 - hp_ratio / 0.28)
    low_mp_pulse = 0.0
    if mp_ratio < 0.18:
        low_mp_pulse = (0.5 + 0.5 * math.sin(t_sec * 5.5)) * (1.0 - mp_ratio / 0.18) * 0.6

    # ── Compact panel geometry ──
    orb_r = 38                  # down from 60
    orb_d = orb_r * 2
    slot_sz = 44                # down from 64
    slot_gap = 4                # tighter
    passive_sz = 44
    pot_sz = 42                 # potion slots close to spell slot size
    pot_gap = 4
    outer_pad = 10
    inner_pad = 14

    # Central strip: passive + spell slots + divider + potion slots
    spell_strip_w = passive_sz
    if slot_count > 0:
        spell_strip_w += 8 + slot_count * slot_sz + (slot_count - 1) * slot_gap
    else:
        spell_strip_w += 180
    pot_strip_w = max_potion_slots * pot_sz + (max_potion_slots - 1) * pot_gap
    divider_w = 12              # brass divider between spells and potions
    _strip_w = spell_strip_w + divider_w + pot_strip_w

    panel_h = 56                # compact height
    panel_w = 2 * (outer_pad + orb_d + inner_pad) + _strip_w
    panel_x = (SCREEN_WIDTH - panel_w) // 2
    # Position so globe aura (orb_r + ~14px) doesn't clip below screen
    _globe_visual_extent = orb_r + max(8, int(14 * (orb_r / 60.0)))
    panel_y = SCREEN_HEIGHT - panel_h // 2 - _globe_visual_extent - 4
    panel = pygame.Rect(panel_x, panel_y, panel_w, panel_h)

    hp_cx = panel.left + outer_pad + orb_r
    mp_cx = panel.right - outer_pad - orb_r
    orb_cy = panel.centery

    mouse_pos = pygame.mouse.get_pos()
    hovered_spell: Optional[Dict[str, object]] = None
    hovered_slot: Optional[pygame.Rect] = None
    hovered_passive = False
    hovered_potion: Optional[Dict[str, object]] = None
    hovered_pot_slot: Optional[pygame.Rect] = None

    # ── Soft drop shadow ──
    _sh = pygame.Surface((panel_w + 12, panel_h + 10), pygame.SRCALPHA)
    pygame.draw.rect(_sh, (0, 0, 0, 120), _sh.get_rect().inflate(-2, -2), border_radius=8)
    screen.blit(_sh, (panel.left - 6, panel.top - 3))

    # ── Ornate panel backdrop (compact brass bezel) ──
    _pbg = pygame.Surface((panel_w + 2, panel_h + 2), pygame.SRCALPHA)
    _pr = _pbg.get_rect()
    pygame.draw.rect(_pbg, (14, 12, 18, 236), _pr, border_radius=7)
    pygame.draw.rect(_pbg, (52, 38, 16), _pr, 2, border_radius=7)
    pygame.draw.rect(_pbg, (160, 120, 48), _pr.inflate(-3, -3), 1, border_radius=6)
    pygame.draw.rect(_pbg, (210, 170, 80), _pr.inflate(-5, -5), 1, border_radius=5)
    pygame.draw.rect(_pbg, (36, 26, 14), _pr.inflate(-7, -7), 1, border_radius=5)
    screen.blit(_pbg, (panel.left - 1, panel.top - 1))

    # ── Interior channel (slots live here) ──
    _ch_left = hp_cx + orb_r + inner_pad - 4
    _ch_right = mp_cx - orb_r - inner_pad + 4
    _ch = pygame.Rect(_ch_left, panel.top + 6, max(0, _ch_right - _ch_left), panel_h - 12)
    if _ch.width > 0 and _ch.height > 0:
        _cs = pygame.Surface(_ch.size, pygame.SRCALPHA)
        pygame.draw.rect(_cs, (4, 4, 8, 140), _cs.get_rect(), border_radius=4)
        pygame.draw.rect(_cs, (60, 44, 20), _cs.get_rect(), 1, border_radius=4)
        screen.blit(_cs, _ch.topleft)

    # Compact rivets (fewer, just top/bottom of channel edges)
    for _ry in (_ch.top + 2, _ch.bottom - 2):
        for _rx in (_ch.left + 4, _ch.right - 4):
            pygame.draw.circle(screen, (6, 4, 2), (_rx, _ry), 2)
            pygame.draw.circle(screen, (160, 120, 50), (_rx, _ry), 1)

    # ── HP globe (left) ──
    _draw_hud_globe(
        screen, (hp_cx, orb_cy), hp_ratio, "hp",
        value_text=f"{int(hp)}/{int(max_hp)}",
        seed=1, tiny_font=small_font,
        extra_pulse=low_hp_pulse,
        flash=_HUD_STATE["hp_flash"],
    )
    # ── MP globe (right) ──
    _draw_hud_globe(
        screen, (mp_cx, orb_cy), mp_ratio, "mp",
        value_text=f"{int(current_mana)}/{int(max_mana)}",
        seed=2, tiny_font=small_font,
        extra_pulse=low_mp_pulse,
        flash=_HUD_STATE["mp_flash"],
    )

    # ── Passive slot ──
    _passive_x = _ch.left + 4
    _passive_y = panel.top + (panel_h - passive_sz) // 2
    passive_slot = pygame.Rect(_passive_x, _passive_y, passive_sz, passive_sz)
    _ps_bg = pygame.Surface((passive_sz, passive_sz), pygame.SRCALPHA)
    pygame.draw.rect(_ps_bg, (10, 8, 14), _ps_bg.get_rect(), border_radius=4)
    pygame.draw.rect(_ps_bg, (22, 18, 28), _ps_bg.get_rect().inflate(-2, -2), border_radius=3)
    screen.blit(_ps_bg, passive_slot.topleft)
    _p_icon = spell_icons.get(f"passive_{class_id}")
    if not isinstance(_p_icon, pygame.Surface):
        _p_icon = build_class_passive_icon(class_id, 64)
    _p_fit = pygame.transform.smoothscale(_p_icon, (passive_sz - 6, passive_sz - 6))
    screen.blit(_p_fit, (passive_slot.left + 3, passive_slot.top + 3))
    pygame.draw.rect(screen, (64, 48, 18), passive_slot, 1, border_radius=4)
    pygame.draw.rect(screen, (170, 130, 60), passive_slot.inflate(-2, -2), 1, border_radius=3)
    if passive_slot.collidepoint(mouse_pos):
        hovered_passive = True
        pygame.draw.rect(screen, accent, passive_slot.inflate(-3, -3), 1, border_radius=3)

    # ── Spell slots ──
    slot_origin_x = passive_slot.right + 8
    slot_origin_y = _passive_y + (passive_sz - slot_sz) // 2
    _slot_rects_out: List[pygame.Rect] = []

    if slot_count <= 0:
        _ls = small_font.render("No skills unlocked [K]", True, (130, 128, 120))
        screen.blit(_ls, (slot_origin_x + 2, slot_origin_y + slot_sz // 2 - _ls.get_height() // 2))
    else:
        for vis_idx, (spell_idx, spell) in enumerate(visible_slots):
            spell_id = str(spell["id"])
            mana_cost = spell_mana_cost(spell, class_id) * passive_mana_mult
            enough_mana = current_mana >= mana_cost
            is_ultimate = bool(spell.get("is_ultimate", False))

            sx = slot_origin_x + vis_idx * (slot_sz + slot_gap)
            slot = pygame.Rect(sx, slot_origin_y, slot_sz, slot_sz)
            _slot_rects_out.append(slot)

            # Slot bg
            _sl_bg = pygame.Surface((slot_sz, slot_sz), pygame.SRCALPHA)
            pygame.draw.rect(_sl_bg, (10, 8, 14), _sl_bg.get_rect(), border_radius=4)
            pygame.draw.rect(_sl_bg, (22, 18, 28), _sl_bg.get_rect().inflate(-2, -2), border_radius=3)
            screen.blit(_sl_bg, slot.topleft)

            if slot.collidepoint(mouse_pos):
                hovered_spell = spell
                hovered_slot = slot

            _icon = spell_icons.get(spell_id)
            if isinstance(_icon, pygame.Surface):
                _sc = pygame.transform.smoothscale(_icon, (slot_sz - 6, slot_sz - 6))
                screen.blit(_sc, (slot.left + 3, slot.top + 3))

            # Cooldown overlay
            _cd = float(cooldowns.get(spell_id, 0.0))
            if _cd > 0.0:
                _cd_max = max(0.001, float(spell.get("cooldown", _cd)))
                _draw_radial_cooldown(screen, slot, clamp(_cd / _cd_max, 0.0, 1.0), (10, 10, 16, 190))
                _cd_t = small_font.render(f"{_cd:.1f}", True, (240, 220, 130))
                screen.blit(_cd_t, (slot.centerx - _cd_t.get_width() // 2, slot.centery - _cd_t.get_height() // 2))

            if spell_global_cooldown > 0.0 and _cd <= 0.0:
                _gcd_pct = clamp(spell_global_cooldown / max(0.001, global_cd_max), 0.0, 1.0)
                _gcd_ov = pygame.Surface((slot_sz, slot_sz), pygame.SRCALPHA)
                _gcd_ov.fill((160, 150, 120, int(_gcd_pct * 50)))
                screen.blit(_gcd_ov, slot.topleft)

            # Border states
            if spell_idx == selected_idx:
                pygame.draw.rect(screen, (24, 16, 6), slot, 2, border_radius=4)
                pygame.draw.rect(screen, accent, slot.inflate(-1, -1), 1, border_radius=4)
                _sel_pulse = 0.5 + 0.5 * math.sin(t_sec * 3.0)
                _sg_a = int(40 + 60 * _sel_pulse)
                _sg = pygame.Surface((slot_sz + 6, slot_sz + 6), pygame.SRCALPHA)
                pygame.draw.rect(_sg, (*accent, _sg_a), _sg.get_rect(), 2, border_radius=6)
                screen.blit(_sg, (slot.left - 3, slot.top - 3))
            elif slot.collidepoint(mouse_pos) and _cd <= 0.0:
                pygame.draw.rect(screen, (64, 48, 18), slot, 1, border_radius=4)
                pygame.draw.rect(screen, (200, 190, 165), slot.inflate(-1, -1), 1, border_radius=3)
            elif not enough_mana:
                pygame.draw.rect(screen, (64, 48, 18), slot, 1, border_radius=4)
                pygame.draw.rect(screen, (140, 50, 50), slot.inflate(-1, -1), 1, border_radius=3)
                _nm = pygame.Surface((slot_sz, slot_sz), pygame.SRCALPHA)
                _nm.fill((50, 8, 12, 70))
                screen.blit(_nm, slot.topleft)
            elif is_ultimate:
                pygame.draw.rect(screen, (64, 48, 18), slot, 1, border_radius=4)
                pygame.draw.rect(screen, (220, 186, 90), slot.inflate(-1, -1), 1, border_radius=3)
                _up = 0.5 + 0.5 * math.sin(t_sec * 3.0 + vis_idx * 0.4)
                _up_s = pygame.Surface((slot_sz + 4, slot_sz + 4), pygame.SRCALPHA)
                pygame.draw.rect(_up_s, (255, 210, 100, int(40 + 60 * _up)), _up_s.get_rect(), 1, border_radius=5)
                screen.blit(_up_s, (slot.left - 2, slot.top - 2))
            else:
                pygame.draw.rect(screen, (64, 48, 18), slot, 1, border_radius=4)
                pygame.draw.rect(screen, (170, 130, 60), slot.inflate(-1, -1), 1, border_radius=3)

            # Keybind label (compact)
            if keybind_editing == vis_idx:
                _pulse_a = int(140 + 80 * abs(math.sin(ticks * 0.006)))
                _ke_s = pygame.Surface((slot_sz + 4, slot_sz + 4), pygame.SRCALPHA)
                pygame.draw.rect(_ke_s, (255, 60, 60, _pulse_a), _ke_s.get_rect(), 2, border_radius=5)
                screen.blit(_ke_s, (slot.left - 2, slot.top - 2))
                _kl = "?"
            elif keybinds and vis_idx < len(keybinds):
                _raw = pygame.key.name(keybinds[vis_idx])
                _kl = _raw.upper() if len(_raw) <= 3 else _raw[:2].upper()
            else:
                _kl = SPELL_KEY_LABELS[vis_idx] if vis_idx < len(SPELL_KEY_LABELS) else str(vis_idx + 1)
            _kc = (240, 220, 150) if enough_mana else (220, 110, 90)
            _ks = small_font.render(_kl, True, _kc)
            _kb_bg = pygame.Surface((_ks.get_width() + 4, _ks.get_height() + 2), pygame.SRCALPHA)
            pygame.draw.rect(_kb_bg, (0, 0, 0, 180), _kb_bg.get_rect(), border_radius=2)
            screen.blit(_kb_bg, (slot.left + 2, slot.top + 2))
            screen.blit(_ks, (slot.left + 4, slot.top + 3))

    if keybind_editing >= 0:
        _kb_s = font.render("PRESS ANY KEY  |  ESC to cancel", True, (255, 100, 100))
        _kb_bg2 = pygame.Surface((_kb_s.get_width() + 12, _kb_s.get_height() + 4), pygame.SRCALPHA)
        _kb_bg2.fill((30, 0, 0, 210))
        screen.blit(_kb_bg2, (panel.centerx - _kb_bg2.get_width() // 2, panel.top - _kb_bg2.get_height() - 4))
        screen.blit(_kb_s, (panel.centerx - _kb_s.get_width() // 2, panel.top - _kb_bg2.get_height() - 2))

    # ── Brass divider between spells and potions ──
    _div_x = slot_origin_x + max(0, slot_count) * (slot_sz + slot_gap) + (8 if slot_count > 0 else spell_strip_w - passive_sz - 8)
    _div_top = panel.top + 10
    _div_bot = panel.bottom - 10
    pygame.draw.line(screen, (40, 30, 14), (_div_x, _div_top), (_div_x, _div_bot), 1)
    pygame.draw.line(screen, (160, 120, 48), (_div_x + 1, _div_top), (_div_x + 1, _div_bot), 1)
    pygame.draw.line(screen, (210, 170, 80), (_div_x + 2, _div_top + 2), (_div_x + 2, _div_bot - 2), 1)
    # Divider rivets top and bottom
    for _dry in (_div_top - 1, _div_bot + 1):
        pygame.draw.circle(screen, (6, 4, 2), (_div_x + 1, _dry), 2)
        pygame.draw.circle(screen, (180, 140, 58), (_div_x + 1, _dry), 1)

    # ── Consumable / potion slots (integrated) ──
    pot_origin_x = _div_x + divider_w
    pot_origin_y = panel.top + (panel_h - pot_sz) // 2
    _pot_rects_out: Dict[int, pygame.Rect] = {}

    for i in range(max_potion_slots):
        px = pot_origin_x + i * (pot_sz + pot_gap)
        py = pot_origin_y
        pot_slot = pygame.Rect(px, py, pot_sz, pot_sz)
        _pot_rects_out[i] = pot_slot

        _pot_entry = item_inventory[i] if i < len(item_inventory) else None
        filled = _pot_entry is not None

        # Slot bg
        _pb = pygame.Surface((pot_sz, pot_sz), pygame.SRCALPHA)
        pygame.draw.rect(_pb, (12, 10, 16) if filled else (8, 8, 14), _pb.get_rect(), border_radius=4)
        pygame.draw.rect(_pb, (24, 20, 28) if filled else (16, 14, 22), _pb.get_rect().inflate(-2, -2), border_radius=3)
        screen.blit(_pb, pot_slot.topleft)

        if filled:
            item = _pot_entry
            _bdr_col = item_rarity_border(item)

            _p_icon = resolve_item_icon(item, pot_sz - 6)
            if isinstance(_p_icon, pygame.Surface):
                screen.blit(_p_icon, (pot_slot.left + 3, pot_slot.top + 3))
            else:
                _col = tuple(item.get("color", (160, 160, 160)))
                pygame.draw.rect(screen, _col, pot_slot.inflate(-8, -8), border_radius=3)

            # Radial cooldown
            if potion_shared_cd_pct > 0.0:
                _draw_radial_cooldown(screen, pot_slot, potion_shared_cd_pct, (12, 12, 18, 180))

            # Stack count
            _qty = int(item.get("quantity", item.get("stack", 0)))
            if _qty > 1:
                _q_s = small_font.render(str(_qty), True, (230, 226, 200))
                _qr = pygame.Rect(pot_slot.right - _q_s.get_width() - 2, pot_slot.bottom - _q_s.get_height() - 1,
                                  _q_s.get_width() + 2, _q_s.get_height())
                pygame.draw.rect(screen, (14, 12, 18, 180), _qr, border_radius=2)
                screen.blit(_q_s, (_qr.left + 1, _qr.top))

            # Border
            if pot_slot.collidepoint(mouse_pos):
                hovered_potion = item
                hovered_pot_slot = pot_slot
                pygame.draw.rect(screen, (200, 196, 216), pot_slot, 1, border_radius=4)
            else:
                pygame.draw.rect(screen, _bdr_col, pot_slot, 1, border_radius=4)
        else:
            pygame.draw.rect(screen, (36, 34, 44), pot_slot, 1, border_radius=4)

        # Potion keybind (1-4 relative) — small muted label
        _pot_key_font = _get_potion_keybind_font()
        _pk_col = (110, 105, 85) if filled else (55, 52, 46)
        _pks = _pot_key_font.render(str(i + 1), True, _pk_col)
        _pkbg = pygame.Surface((_pks.get_width() + 2, _pks.get_height()), pygame.SRCALPHA)
        pygame.draw.rect(_pkbg, (0, 0, 0, 140), _pkbg.get_rect(), border_radius=2)
        screen.blit(_pkbg, (pot_slot.right - _pks.get_width() - 3, pot_slot.bottom - _pks.get_height() - 1))
        screen.blit(_pks, (pot_slot.right - _pks.get_width() - 2, pot_slot.bottom - _pks.get_height() - 1))

    # ── Level badge (compact, above HP globe) ──
    _pop = _HUD_STATE["level_pop"]
    _lvl_scale = 1.0 + 0.22 * _pop
    _med_r = int(13 * _lvl_scale)
    _med_cx = hp_cx - orb_r - _med_r + 6
    _med_cy = panel.top + _med_r + 4
    # Glow
    _glow_breath = 0.3 + 0.2 * (0.5 + 0.5 * math.sin(t_sec * 1.8))
    _glow_strength = _glow_breath + _pop * 0.8
    _glow_r = _med_r + 8 + int(10 * _pop)
    _gs = pygame.Surface((_glow_r * 2 + 4, _glow_r * 2 + 4), pygame.SRCALPHA)
    for _rr in range(_glow_r, _med_r - 1, -1):
        _fo = (_rr - (_med_r - 1)) / max(1, _glow_r - (_med_r - 1))
        _ga = int(((1.0 - _fo) ** 2.2) * 130 * _glow_strength)
        if _ga > 0:
            pygame.draw.circle(_gs, (255, 220, 110, _ga), (_glow_r + 2, _glow_r + 2), _rr)
    screen.blit(_gs, (_med_cx - _glow_r - 2, _med_cy - _glow_r - 2))
    # Laurel (compact, 2 per side)
    for _side in (-1, 1):
        for _li in range(2):
            _lx = _med_cx + _side * (_med_r + 3 + _li * 3)
            _ly = _med_cy + (_li - 0.5) * 4
            _leaf = pygame.Rect(0, 0, 7, 4)
            _leaf.center = (int(_lx), int(_ly))
            pygame.draw.ellipse(screen, (28, 44, 18), _leaf)
            pygame.draw.ellipse(screen, (80, 120, 42), _leaf, 1)
    # Medallion rings
    pygame.draw.circle(screen, (4, 2, 2), (_med_cx, _med_cy), _med_r + 2)
    pygame.draw.circle(screen, (70, 50, 18), (_med_cx, _med_cy), _med_r + 1)
    pygame.draw.circle(screen, (200, 164, 72), (_med_cx, _med_cy), _med_r)
    pygame.draw.circle(screen, (80, 56, 22), (_med_cx, _med_cy), _med_r, 2)
    pygame.draw.circle(screen, (20, 14, 10), (_med_cx, _med_cy), _med_r - 2)
    pygame.draw.circle(screen, (38, 28, 16), (_med_cx, _med_cy), _med_r - 3)
    _lvl_font = pygame.font.SysFont("georgia", max(9, int(14 * _lvl_scale)), bold=True)
    _lvl_s = _lvl_font.render(str(int(player_level)), True, (252, 232, 160))
    _lvl_sh = _lvl_font.render(str(int(player_level)), True, (0, 0, 0))
    _lvw, _lvh = _lvl_s.get_size()
    screen.blit(_lvl_sh, (_med_cx - _lvw // 2 + 1, _med_cy - _lvh // 2 + 1))
    screen.blit(_lvl_s, (_med_cx - _lvw // 2, _med_cy - _lvh // 2))
    # Level-up burst
    if _pop > 0:
        _ring_r = int(_med_r + (1.0 - _pop) * 34)
        _ring_a = int(200 * _pop)
        _ring = pygame.Surface((_ring_r * 2 + 4, _ring_r * 2 + 4), pygame.SRCALPHA)
        pygame.draw.circle(_ring, (255, 230, 120, _ring_a), (_ring_r + 2, _ring_r + 2), _ring_r, 2)
        screen.blit(_ring, (_med_cx - _ring_r - 2, _med_cy - _ring_r - 2))
        for _bi in range(10):
            _ba = (_bi / 10) * 2 * math.pi
            _bd = int((1 - _pop) * 36 + 10)
            _bx = _med_cx + int(_bd * math.cos(_ba))
            _by = _med_cy + int(_bd * math.sin(_ba))
            _spark = pygame.Surface((8, 8), pygame.SRCALPHA)
            pygame.draw.circle(_spark, (255, 230, 120, int(220 * _pop)), (4, 4), 2)
            screen.blit(_spark, (_bx - 4, _by - 4))

    # ── Gold plaque removed — gold is shown in the backpack ──

    # ── XP strip (thin, below panel) ──
    _xp_w = max(0, _ch.width - 8)
    if _xp_w > 60:
        _xp_h = 5
        _xp_x = _ch.left + 4
        _xp_y = panel.bottom + 2
        _xp_bg = pygame.Surface((_xp_w, _xp_h), pygame.SRCALPHA)
        pygame.draw.rect(_xp_bg, (6, 4, 10, 220), _xp_bg.get_rect(), border_radius=2)
        pygame.draw.rect(_xp_bg, (40, 28, 56), _xp_bg.get_rect(), 1, border_radius=2)
        screen.blit(_xp_bg, (_xp_x, _xp_y))
        _fill_w = int((_xp_w - 2) * xp_ratio)
        if _fill_w > 0:
            _xp_fill = pygame.Rect(_xp_x + 1, _xp_y + 1, _fill_w, _xp_h - 2)
            for yy in range(_xp_fill.height):
                _t = yy / max(1, _xp_fill.height - 1)
                _c = (int(180 + (100 - 180) * _t), int(110 + (40 - 110) * _t), int(240 + (150 - 240) * _t))
                pygame.draw.line(screen, _c, (_xp_fill.left, _xp_fill.top + yy), (_xp_fill.right - 1, _xp_fill.top + yy))
            # Shimmer sweep
            _sweep = ((ticks * 0.0008) % 2.0) - 0.3
            if -0.1 <= _sweep <= 1.15 and _fill_w > 8:
                _sw_cx = int(_fill_w * _sweep)
                _sw_s = pygame.Surface((_fill_w, _xp_fill.height), pygame.SRCALPHA)
                for _dx in range(-14, 15):
                    _xx = _sw_cx + _dx
                    if 0 <= _xx < _fill_w:
                        _bell = math.exp(-(_dx * _dx) / 36)
                        _a = int(150 * _bell)
                        if _a > 0:
                            pygame.draw.line(_sw_s, (255, 230, 255, _a), (_xx, 0), (_xx, _xp_fill.height))
                screen.blit(_sw_s, (_xp_fill.left, _xp_fill.top))
        for _ti in range(1, 10):
            _tx = _xp_x + int(_xp_w * _ti / 10)
            pygame.draw.line(screen, (60, 42, 82), (_tx, _xp_y + 1), (_tx, _xp_y + _xp_h - 1))

    # ── Tooltip for passive ──
    passive_name = str(passive.get("name", "Class Passive"))
    passive_desc = str(passive.get("desc", ""))

    def draw_hover_tooltip(lines: List[str], anchor: pygame.Rect, cache_key: object) -> None:
        width = 0
        rendered: List[pygame.Surface] = []
        for li, line in enumerate(lines):
            surf = font.render(line, True, (252, 234, 196) if li == 0 else (204, 196, 178))
            rendered.append(surf)
            width = max(width, surf.get_width())
        tip = pygame.Rect(0, 0, width + 22, 12 + len(rendered) * 24)
        tip.midbottom = (anchor.centerx, anchor.top - 8)
        tip.clamp_ip(pygame.Rect(10, 10, SCREEN_WIDTH - 20, SCREEN_HEIGHT - 20))
        global _TOOLTIP_SURFACE, _TOOLTIP_LAST_ITEM
        if _TOOLTIP_LAST_ITEM != cache_key:
            _TOOLTIP_SURFACE = pygame.Surface((tip.width, tip.height), pygame.SRCALPHA)
            pygame.draw.rect(_TOOLTIP_SURFACE, (18, 16, 22, 242), (0, 0, tip.width, tip.height), border_radius=8)
            pygame.draw.rect(_TOOLTIP_SURFACE, (150, 124, 76), (0, 0, tip.width, tip.height), 1, border_radius=8)
            _ty = 6
            for surf in rendered:
                _TOOLTIP_SURFACE.blit(surf, (11, _ty))
                _ty += 24
            _TOOLTIP_LAST_ITEM = cache_key
        if _TOOLTIP_SURFACE:
            screen.blit(_TOOLTIP_SURFACE, tip.topleft)

    if hovered_spell is not None and hovered_slot is not None:
        _kind = str(hovered_spell.get("kind", "spell"))
        _dmg = float(hovered_spell.get("damage", 0.0))
        _cd_val = float(hovered_spell.get("cooldown", 0.0))
        _mc = spell_mana_cost(hovered_spell, class_id) * passive_mana_mult
        _unlocked = str(hovered_spell.get("skill", "")) in unlocked_skills
        _kl_map = {
            "projectile": "Launches a fast projectile that hits enemies in a line.",
            "nova": "Expands outward in a ring, damaging enemies in radius.",
            "orb": "Places a pulsing orb that repeatedly damages nearby enemies.",
            "ward": "Creates a standing zone that damages enemies over time.",
            "melee_arc": "Performs a close melee arc in front of you.",
            "cone": "Sweeps a wide cone forward, disrupting enemies.",
            "pillar": "Raises a blocking pillar that damages on impact.",
            "ultimate": "Channel a catastrophic elemental storm around you.",
        }
        _lines: List[str] = [str(hovered_spell.get("name", "Spell")), _kl_map.get(_kind, "Cast a combat spell.")]
        if bool(hovered_spell.get("is_ultimate", False)):
            _lines.append("ULTIMATE — Strongest class finisher.")
        _lines.append(f"Damage {int(round(_dmg))}   Mana {int(round(_mc))}   Cooldown {_cd_val:.1f}s")
        if _kind == "projectile":
            _lines.append(f"Speed {int(float(hovered_spell.get('speed', 0.0)))}   Radius {int(float(hovered_spell.get('radius', 0.0)))}")
        elif _kind == "nova":
            _lines.append(f"Max Radius {int(float(hovered_spell.get('max_radius', 0.0)))}")
        elif _kind == "melee_arc":
            _lines.append(f"Melee Reach {int(float(hovered_spell.get('radius', 0.0)))}")
        elif _kind == "cone":
            _lines.append(f"Reach {int(float(hovered_spell.get('radius', 0.0)))}   Angle {int(float(hovered_spell.get('cone_angle', 0.0)))}")
        elif _kind == "pillar":
            _lines.append(f"Duration {float(hovered_spell.get('duration', 0.0)):.1f}s")
        elif _kind in ("orb", "ward"):
            _lines.append(f"Area Radius {int(float(hovered_spell.get('radius', 0.0)))}")
        if not _unlocked:
            _lines.append("LOCKED — Unlock in the Skill Tree [K].")
        draw_hover_tooltip(_lines, hovered_slot, hovered_spell)
    elif hovered_passive:
        _p_lines: List[str] = [f"{passive_name} (Class Passive)"]
        _p_lines.extend(wrap_text_lines(font, passive_desc, 360, max_lines=2))
        _p_lines.extend(class_passive_effect_lines(passive, max_lines=3))
        draw_hover_tooltip(_p_lines, passive_slot, ("passive", class_id))
    elif hovered_potion is not None and hovered_pot_slot is not None:
        draw_item_tooltip(screen, hovered_potion, hovered_pot_slot, font, small_font)

    return _slot_rects_out, _pot_rects_out


def draw_spell_bar_vertical(
    screen: pygame.Surface,
    full_spellbook: List[Dict[str, object]],
    active_spellbook: List[Dict[str, object]],
    spell_icons: Dict[str, pygame.Surface],
    cooldowns: Dict[str, float],
    unlocked_skills: Set[str],
    current_mana: float,
    font: pygame.font.Font,
    class_id: str = "",
) -> None:
    """Draw a WoW-style vertical side action bar on the right of the screen
    showing secondary spells (those not on the main 8-slot horizontal bar)."""
    ticks = pygame.time.get_ticks()

    # Class palette
    _pal = CLASS_PALETTES.get(class_id, CLASS_PALETTES["default"])
    accent = _pal["primary"]
    _pal_bg = _pal["panel_bg"]

    passive_effects = class_passive_effects(class_id)
    passive_mana_mult = max(0.1, float(passive_effects.get("mana_cost_mult", 1.0)))

    # Determine secondary spells (in full spellbook but NOT in the active bar)
    active_ids = {str(s.get("id", "")) for s in active_spellbook}
    secondary: List[Dict[str, object]] = [s for s in full_spellbook if str(s.get("id", "")) not in active_ids]

    if not secondary:
        return

    slot_size = 40
    gap = 3
    bar_padding = 6

    total_h = bar_padding * 2 + len(secondary) * slot_size + max(0, len(secondary) - 1) * gap
    bar_w = slot_size + bar_padding * 2 + 4  # +4 for label column on left
    # Position left of the minimap (minimap frame_size=216, at SCREEN_WIDTH-216-18)
    _minimap_left = SCREEN_WIDTH - 216 - 18
    bar_x = _minimap_left - bar_w - 8
    # Start below the minimap + weather area (~280px from top), bottom-align to spell bar
    _bar_bottom = SCREEN_HEIGHT - 100  # above the unified action belt
    bar_y = max(280, _bar_bottom - total_h)

    bar_rect = pygame.Rect(bar_x, bar_y, bar_w, total_h)

    # Panel background (class-tinted)
    bg = pygame.Surface((bar_w, total_h), pygame.SRCALPHA)
    pygame.draw.rect(bg, (*_pal_bg, 220), bg.get_rect(), border_radius=12)
    screen.blit(bg, bar_rect.topleft)

    # Animated border glow (class color)
    _ba = int(40 + 20 * math.sin(ticks * 0.0016))
    _glow = pygame.Surface((bar_w + 6, total_h + 6), pygame.SRCALPHA)
    pygame.draw.rect(_glow, (*accent, _ba), _glow.get_rect(), 2, border_radius=14)
    screen.blit(_glow, (bar_x - 3, bar_y - 3))
    pygame.draw.rect(screen, tuple(max(0, c - 10) for c in _pal_bg), bar_rect, 1, border_radius=12)

    # Top label
    _lbl = font.render("II", True, (*accent, 180))
    screen.blit(_lbl, (bar_rect.centerx - _lbl.get_width() // 2, bar_y - _lbl.get_height() - 2))

    mouse_pos = pygame.mouse.get_pos()
    hovered_spell_v: Optional[Dict[str, object]] = None
    hovered_slot_v: Optional[pygame.Rect] = None

    for i, spell in enumerate(secondary):
        spell_id = str(spell.get("id", ""))
        is_unlocked = str(spell.get("skill", "")) in unlocked_skills
        is_ultimate = bool(spell.get("is_ultimate", False))
        mana_cost = spell_mana_cost(spell, class_id) * passive_mana_mult
        enough_mana = current_mana >= mana_cost

        sx = bar_x + bar_padding
        sy = bar_y + bar_padding + i * (slot_size + gap)
        slot = pygame.Rect(sx, sy, slot_size, slot_size)

        # Slot background
        _slot_col = (34, 22, 10) if is_ultimate else (20, 20, 28)
        pygame.draw.rect(screen, _slot_col, slot, border_radius=8)

        # Icon
        _icon = spell_icons.get(spell_id)
        if isinstance(_icon, pygame.Surface):
            _sc = pygame.transform.smoothscale(_icon, (slot_size - 6, slot_size - 6))
            if not is_unlocked:
                _grey_ov = pygame.Surface(_sc.get_size(), pygame.SRCALPHA)
                _grey_ov.fill((30, 30, 50, 150))
                _sc.blit(_grey_ov, (0, 0))
            screen.blit(_sc, (slot.left + 3, slot.top + 3))

        # Radial cooldown
        _cd = float(cooldowns.get(spell_id, 0.0))
        if _cd > 0.0:
            _cd_max = max(0.001, float(spell.get("cooldown", _cd)))
            _draw_radial_cooldown(screen, slot, clamp(_cd / _cd_max, 0.0, 1.0), (10, 10, 18, 200))
            _cd_t = font.render(f"{_cd:.1f}", True, (255, 230, 120))
            screen.blit(_cd_t, (slot.centerx - _cd_t.get_width() // 2, slot.centery - _cd_t.get_height() // 2))

        # Hover
        hovered = slot.collidepoint(mouse_pos)
        if hovered:
            hovered_spell_v = spell
            hovered_slot_v = slot

        # Border
        if hovered:
            bdr = accent
            bdr_w = 2
        elif is_ultimate:
            bdr = (210, 170, 88) if is_unlocked else (80, 60, 24)
            bdr_w = 2
        elif not enough_mana:
            bdr = (110, 36, 36)
            bdr_w = 1
        else:
            bdr = accent if is_unlocked else (44, 44, 58)
            bdr_w = 1
        pygame.draw.rect(screen, bdr, slot, bdr_w, border_radius=8)

        # Lock overlay
        if not is_unlocked:
            _lk_s = pygame.Surface((slot_size, slot_size), pygame.SRCALPHA)
            pygame.draw.rect(_lk_s, (0, 0, 0, 120), _lk_s.get_rect(), border_radius=8)
            screen.blit(_lk_s, slot.topleft)

    # Tooltip for hovered vertical bar spell
    if hovered_spell_v is not None and hovered_slot_v is not None:
        _name = str(hovered_spell_v.get("name", "Spell"))
        _dmg = float(hovered_spell_v.get("damage", 0.0))
        _mc_val = spell_mana_cost(hovered_spell_v, class_id) * passive_mana_mult
        _cd_val = float(hovered_spell_v.get("cooldown", 0.0))
        _unlocked = str(hovered_spell_v.get("skill", "")) in unlocked_skills
        _tip_lines = [_name, f"Dmg {int(round(_dmg))}  Mana {int(round(_mc_val))}  CD {_cd_val:.1f}s"]
        if not _unlocked:
            _tip_lines.append("LOCKED — Skill Tree [K]")
        _tw = max(font.size(l)[0] for l in _tip_lines) + 20
        _th = len(_tip_lines) * 22 + 10
        _tip_x = hovered_slot_v.left - _tw - 6
        _tip_y = hovered_slot_v.centery - _th // 2
        _tip_x = max(4, _tip_x)
        _tip_y = max(4, min(_tip_y, SCREEN_HEIGHT - _th - 4))
        _ts = pygame.Surface((_tw, _th), pygame.SRCALPHA)
        pygame.draw.rect(_ts, (16, 14, 20, 240), (0, 0, _tw, _th), border_radius=7)
        pygame.draw.rect(_ts, (148, 124, 76), (0, 0, _tw, _th), 1, border_radius=7)
        for _li, _line in enumerate(_tip_lines):
            _col = accent if _li == 0 else (200, 192, 172)
            _ls = font.render(_line, True, _col)
            _ts.blit(_ls, (10, 5 + _li * 22))
        screen.blit(_ts, (_tip_x, _tip_y))


def skill_tree_layout(panel: pygame.Rect, skill_tree_nodes: List[Dict[str, object]]) -> Dict[str, pygame.Rect]:
    rects: Dict[str, pygame.Rect] = {}
    if not skill_tree_nodes:
        return rects

    x_values = sorted({round(float(node.get("pos", (0.5, 0.5))[0]), 4) for node in skill_tree_nodes})
    y_values = sorted({round(float(node.get("pos", (0.5, 0.5))[1]), 4) for node in skill_tree_nodes})

    card_w = 94 if len(x_values) <= 5 else 86
    card_h = 92 if len(y_values) <= 4 else 84
    left_pad = max(72, min(124, panel.width // 9))
    right_pad = max(52, min(96, panel.width // 12))
    top_pad = max(44, min(68, panel.height // 9))
    bottom_pad = max(58, min(84, panel.height // 8))

    usable_w = max(card_w + 18, panel.width - left_pad - right_pad)
    usable_h = max(card_h + 18, panel.height - top_pad - bottom_pad)

    x_index = {value: idx for idx, value in enumerate(x_values)}
    y_index = {value: idx for idx, value in enumerate(y_values)}

    for node in skill_tree_nodes:
        px, py = node["pos"]
        px_key = round(float(px), 4)
        py_key = round(float(py), 4)

        if len(x_values) <= 1:
            cx = panel.left + panel.width // 2
        else:
            cx = panel.left + left_pad + int((usable_w * x_index.get(px_key, 0)) / max(1, len(x_values) - 1))

        if len(y_values) <= 1:
            cy = panel.top + panel.height // 2
        else:
            cy = panel.top + top_pad + int((usable_h * y_index.get(py_key, 0)) / max(1, len(y_values) - 1))

        rect = pygame.Rect(0, 0, card_w, card_h)
        rect.center = (cx, cy)
        rects[str(node["id"])] = rect
    return rects


def wrap_text_lines(font: pygame.font.Font, text: str, max_width: int, max_lines: int = 2) -> List[str]:
    words = text.split()
    if not words:
        return [""]
    lines: List[str] = []
    current = words[0]
    idx = 1
    while idx < len(words):
        trial = f"{current} {words[idx]}"
        if font.size(trial)[0] <= max_width:
            current = trial
            idx += 1
            continue
        lines.append(current)
        current = words[idx]
        idx += 1
        if len(lines) >= max_lines - 1:
            break
    if idx < len(words):
        tail = " ".join([current] + words[idx:])
        while font.size(tail + "...")[0] > max_width and " " in tail:
            tail = tail.rsplit(" ", 1)[0]
        lines.append((tail + "...") if len(tail) < len(" ".join([current] + words[idx:])) else tail)
    else:
        lines.append(current)
    return lines[:max_lines]


def draw_skill_tree(
    screen: pygame.Surface,
    class_name: str,
    skill_tree_nodes: List[Dict[str, object]],
    unlocked_skills: Set[str],
    skill_points: int,
    skill_hover: Optional[str],
    title_font: pygame.font.Font,
    node_font: pygame.font.Font,
    info_font: pygame.font.Font,
    spell_icons: Dict[str, pygame.Surface],
) -> Dict[str, pygame.Rect]:
    overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 188))
    screen.blit(overlay, (0, 0))

    panel = pygame.Rect(70, 46, SCREEN_WIDTH - 140, SCREEN_HEIGHT - 92)
    draw_ornate_panel(screen, panel)
    inner = panel.inflate(-10, -10)
    for y in range(inner.height):
        t = y / max(1, inner.height - 1)
        shade = int(18 + 20 * t)
        pygame.draw.line(screen, (shade, shade, shade + 6), (inner.left, inner.top + y), (inner.right, inner.top + y))
    for x in range(inner.left + 26, inner.right, 52):
        pygame.draw.line(screen, (34, 32, 30), (x, inner.top), (x, inner.bottom), 1)

    title = title_font.render(f"{class_name} Skill Tree", True, (238, 220, 170))
    points = info_font.render(f"Skill Points: {skill_points}", True, (238, 210, 140))
    hint = info_font.render("Click nodes to unlock. Tiered progression like classic ARPG trees. [K] Close", True, (186, 176, 156))
    screen.blit(title, (panel.left + 22, panel.top + 14))
    screen.blit(points, (panel.right - points.get_width() - 22, panel.top + 20))
    screen.blit(hint, (panel.centerx - hint.get_width() // 2, panel.top + 54))

    content = pygame.Rect(panel.left + 62, panel.top + 106, panel.width - 124, panel.height - 238)
    pygame.draw.rect(screen, (14, 14, 18), content, border_radius=8)
    pygame.draw.rect(screen, (72, 70, 62), content, 1, border_radius=8)

    node_rects = skill_tree_layout(content, skill_tree_nodes)
    node_by_id = {str(node["id"]): node for node in skill_tree_nodes}
    req_name_by_id = {nid: str(node.get("name", nid)) for nid, node in node_by_id.items()}

    tier_lines = [("Core", 0.10), ("Tier I", 0.28), ("Tier II", 0.50), ("Tier III", 0.72)]
    for label, py in tier_lines:
        ly = content.top + int(content.height * py)
        pygame.draw.line(screen, (58, 58, 64), (content.left + 10, ly), (content.right - 10, ly), 1)
        ls = info_font.render(label, True, (164, 160, 148))
        screen.blit(ls, (content.left + 12, ly - 16))

    unlock_nodes = [n for n in skill_tree_nodes if n.get("spell")]
    unlock_nodes.sort(key=lambda n: float(n.get("pos", (0.0, 0.0))[0]))

    def node_spell_id(node_id: str, node: dict[str, object]) -> str:
        sid = str(node.get("spell", ""))
        if sid:
            return sid
        for suffix in ("_tier2", "_tier3"):
            if node_id.endswith(suffix):
                return node_id[: -len(suffix)]
        if node_id.endswith("_core") and unlock_nodes:
            return str(unlock_nodes[0].get("spell", ""))
        return ""

    lane_name_font = pygame.font.SysFont("georgia", 15, bold=True)
    for lane in unlock_nodes:
        lane_id = str(lane["id"])
        lane_rect = node_rects.get(lane_id)
        if lane_rect is None:
            continue
        lane_label = str(lane.get("name", lane_id))
        ls = lane_name_font.render(lane_label, True, (198, 186, 152))
        screen.blit(ls, (lane_rect.centerx - ls.get_width() // 2, content.top + 8))

    icon_cache: Dict[str, pygame.Surface] = {}

    def node_icon(node_id: str, node: dict[str, object]) -> pygame.Surface:
        cached = icon_cache.get(node_id)
        if isinstance(cached, pygame.Surface):
            return cached

        sid = node_spell_id(node_id, node)
        base = spell_icons.get(sid)
        if isinstance(base, pygame.Surface):
            icon = pygame.transform.scale(base, (64, 64)).copy()
        else:
            c = 80 + (sum(ord(ch) for ch in node_id) % 140)
            icon = make_fallback_icon((c, min(255, c + 36), max(80, c - 24)))

        tier_text = "C"
        if node_id.endswith("_tier3"):
            tier_text = "III"
        elif node_id.endswith("_tier2"):
            tier_text = "II"
        elif str(node.get("spell", "")):
            tier_text = "I"

        badge = pygame.Rect(icon.get_width() - 22, icon.get_height() - 22, 18, 18)
        pygame.draw.circle(icon, (22, 22, 26), badge.center, 10)
        pygame.draw.circle(icon, (206, 172, 102), badge.center, 10, 2)
        badge_font = pygame.font.SysFont("georgia", 11, bold=True)
        ts = badge_font.render(tier_text, True, (236, 222, 182))
        icon.blit(ts, (badge.centerx - ts.get_width() // 2, badge.centery - ts.get_height() // 2))

        if tier_text == "C":
            pygame.draw.circle(icon, (220, 186, 116), (12, 12), 5)
            pygame.draw.circle(icon, (70, 50, 20), (12, 12), 5, 1)

        icon_cache[node_id] = icon
        return icon

    # Draw links before nodes.
    for node in skill_tree_nodes:
        node_id = str(node["id"])
        for req in node.get("requires", []):
            req_id = str(req)
            if req_id not in node_rects or node_id not in node_rects:
                continue
            parent_rect = node_rects[req_id]
            child_rect = node_rects[node_id]
            a = parent_rect.center
            b = child_rect.center
            linked = req_id in unlocked_skills and node_id in unlocked_skills
            available_path = req_id in unlocked_skills
            if linked:
                line_col = (214, 178, 92)
                line_w = 4
            elif available_path:
                line_col = (124, 106, 72)
                line_w = 3
            else:
                line_col = (70, 70, 78)
                line_w = 2
            pygame.draw.line(screen, line_col, a, b, line_w)

    for node_id, rect in node_rects.items():
        node = node_by_id[node_id]
        unlocked = node_id in unlocked_skills
        requires = [str(req) for req in node.get("requires", [])]
        available = all(req in unlocked_skills for req in requires)
        affordable = int(node.get("cost", 0)) <= skill_points

        socket_center = rect.center
        socket_r = 36
        if unlocked:
            ring = (198, 186, 108)
            glow = (72, 116, 72)
        elif available and affordable:
            ring = (196, 150, 82)
            glow = (86, 62, 34)
        elif available:
            ring = (160, 94, 90)
            glow = (70, 34, 34)
        else:
            ring = (94, 94, 102)
            glow = (38, 38, 42)

        pygame.draw.circle(screen, (14, 14, 18), socket_center, socket_r + 5)
        pygame.draw.circle(screen, glow, socket_center, socket_r)
        pygame.draw.circle(screen, ring, socket_center, socket_r, 3)
        if skill_hover == node_id:
            pygame.draw.circle(screen, (226, 198, 120), socket_center, socket_r + 7, 2)

        icon = node_icon(node_id, node)
        icon_rect = icon.get_rect(center=socket_center)
        screen.blit(icon, icon_rect)

        name = str(node.get("name", node_id))
        if node_font.size(name)[0] > 150:
            short = name
            while len(short) > 4 and node_font.size(short + "...")[0] > 150:
                short = short[:-1]
            name = short + "..."
        name_s = node_font.render(name, True, (224, 218, 200))
        screen.blit(name_s, (rect.centerx - name_s.get_width() // 2, rect.bottom + 4))

        cost = int(node.get("cost", 0))
        cost_bg = pygame.Rect(rect.centerx + 18, rect.top - 2, 24, 16)
        pygame.draw.rect(screen, (18, 18, 20), cost_bg, border_radius=5)
        pygame.draw.rect(screen, (118, 100, 66), cost_bg, 1, border_radius=5)
        cost_s = info_font.render(str(cost), True, (236, 214, 152))
        screen.blit(cost_s, (cost_bg.centerx - cost_s.get_width() // 2, cost_bg.centery - cost_s.get_height() // 2))

    if skill_hover and skill_hover in node_by_id:
        node = node_by_id[skill_hover]
        tip = pygame.Rect(panel.left + 22, panel.bottom - 112, panel.width - 44, 86)
        pygame.draw.rect(screen, (16, 16, 20), tip, border_radius=8)
        pygame.draw.rect(screen, (120, 98, 62), tip, 1, border_radius=8)

        node_id = str(node["id"])
        icon = node_icon(node_id, node)
        screen.blit(icon, (tip.left + 10, tip.top + 10))

        title_s = node_font.render(str(node.get("name", node_id)), True, (236, 224, 190))
        screen.blit(title_s, (tip.left + 84, tip.top + 10))

        req_names = [req_name_by_id.get(str(r), str(r)) for r in node.get("requires", [])]
        req_text = ", ".join(req_names) if req_names else "None"
        req_s = info_font.render(f"Requires: {req_text}", True, (188, 184, 170))
        screen.blit(req_s, (tip.left + 84, tip.top + 34))

        mod_hint = "Progressive upgrade node."
        spell_mods = node.get("spell_mods")
        if isinstance(spell_mods, dict) and spell_mods:
            first_mod = next(iter(spell_mods.values()))
            if isinstance(first_mod, dict) and first_mod:
                parts: List[str] = []
                key_names = {
                    "damage_mult": "dmg",
                    "cooldown_mult": "cd",
                    "mana_mult": "mana",
                    "radius_mult": "radius",
                    "max_radius_mult": "blast",
                    "duration_mult": "duration",
                    "interval_mult": "tick",
                    "speed_mult": "speed",
                    "projectile_count_bonus": "proj",
                    "pierce_bonus": "pierce",
                    "impact_nova_radius_bonus": "nova",
                }
                for key, val in first_mod.items():
                    if key not in key_names:
                        continue
                    if key.endswith("_mult"):
                        parts.append(f"{key_names[key]} x{float(val):.2f}")
                    else:
                        parts.append(f"{key_names[key]} +{int(round(float(val)))}")
                if parts:
                    mod_hint = "Upgrade: " + ", ".join(parts)
        mod_s = info_font.render(mod_hint, True, (170, 200, 160))
        screen.blit(mod_s, (tip.left + 84, tip.top + 58))

    return node_rects


def _blend_ui_color(a: Tuple[int, int, int], b: Tuple[int, int, int], t: float) -> Tuple[int, int, int]:
    tt = clamp(t, 0.0, 1.0)
    return (
        int(a[0] + (b[0] - a[0]) * tt),
        int(a[1] + (b[1] - a[1]) * tt),
        int(a[2] + (b[2] - a[2]) * tt),
    )


def _brighten_ui_color(color: Tuple[int, int, int], amt: int) -> Tuple[int, int, int]:
    return (
        min(255, color[0] + amt),
        min(255, color[1] + amt),
        min(255, color[2] + amt),
    )


def _darken_ui_color(color: Tuple[int, int, int], amt: int) -> Tuple[int, int, int]:
    return (
        max(0, color[0] - amt),
        max(0, color[1] - amt),
        max(0, color[2] - amt),
    )


def _truncate_ui_text(font: pygame.font.Font, text: str, max_width: int) -> str:
    value = str(text)
    if font.size(value)[0] <= max_width:
        return value
    short = value
    while len(short) > 3 and font.size(short + "...")[0] > max_width:
        short = short[:-1]
    return short + "..."


_SKILL_TREE_FONT_CACHE: Dict[Tuple[str, int, bool, bool], pygame.font.Font] = {}


def _skill_tree_font(size: int, bold: bool = False, italic: bool = False, flavor: str = "body") -> pygame.font.Font:
    key = (flavor, int(size), bool(bold), bool(italic))
    cached = _SKILL_TREE_FONT_CACHE.get(key)
    if isinstance(cached, pygame.font.Font):
        return cached

    if flavor == "title":
        candidates = ["cinzel", "palatino linotype", "book antiqua", "constantia", "cambria", "georgia"]
    elif flavor == "label":
        candidates = ["constantia", "cambria", "palatino linotype", "book antiqua", "georgia"]
    else:
        candidates = ["constantia", "cambria", "palatino linotype", "book antiqua", "georgia"]

    for name in candidates:
        path = pygame.font.match_font(name, bold=bold, italic=italic)
        if not path:
            continue
        font = pygame.font.Font(path, size)
        _SKILL_TREE_FONT_CACHE[key] = font
        return font

    font = pygame.font.SysFont("georgia", size, bold=bold, italic=italic)
    _SKILL_TREE_FONT_CACHE[key] = font
    return font


def _skill_tree_node_spell_id(
    node_id: str,
    node: Dict[str, object],
    unlock_nodes: List[Dict[str, object]],
) -> str:
    sid = str(node.get("spell", ""))
    if sid:
        return sid
    for suffix in ("_tier2", "_tier3"):
        if node_id.endswith(suffix):
            return node_id[: -len(suffix)]
    if node_id.endswith("_core") and unlock_nodes:
        return str(unlock_nodes[0].get("spell", ""))
    return ""


def _skill_tree_node_type_label(node_id: str, node: Dict[str, object]) -> str:
    if node_id.endswith("_core") or int(node.get("cost", 0)) == 0:
        return "Core"
    spell_mods = node.get("spell_mods")
    if isinstance(spell_mods, dict) and spell_mods:
        return "Upgrade"
    if str(node.get("spell", "")):
        return "Spell"
    return "Passive"


def _skill_tree_extract_mods(node: Dict[str, object]) -> Dict[str, object]:
    spell_mods = node.get("spell_mods")
    if isinstance(spell_mods, dict) and spell_mods:
        first_mod = next(iter(spell_mods.values()))
        if isinstance(first_mod, dict):
            return first_mod
    return {}


_SKILL_TREE_BADGE_SOURCES: Dict[str, Tuple[str, int, int]] = {
    "core": ("monsters", 11, 0),
    "spell": ("items", 10, 1),
    "passive": ("items", 16, 4),
    "status_owned": ("items", 16, 4),
    "status_ready": ("items", 10, 1),
    "status_need_sp": ("items", 19, 4),
    "status_locked": ("items", 16, 6),
    "upgrade_spear": ("items", 6, 0),
    "upgrade_volley": ("items", 23, 1),
    "upgrade_ring": ("items", 16, 6),
    "upgrade_hourglass": ("items", 10, 8),
    "upgrade_banner": ("items", 10, 8),
    "upgrade_wing": ("monsters", 11, 0),
    "upgrade_drop": ("items", 19, 4),
    "upgrade_burst": ("monsters", 5, 2),
}
_SKILL_TREE_BADGE_SHEET_CACHE: Dict[str, Optional[pygame.Surface]] = {}
_SKILL_TREE_BADGE_ICON_CACHE: Dict[Tuple[str, int], Optional[pygame.Surface]] = {}


def _load_skill_tree_badge_icon(kind: str, size: int = 16) -> Optional[pygame.Surface]:
    cache_key = (str(kind), int(size))
    if cache_key in _SKILL_TREE_BADGE_ICON_CACHE:
        return _SKILL_TREE_BADGE_ICON_CACHE[cache_key]

    source = _SKILL_TREE_BADGE_SOURCES.get(str(kind))
    if not source:
        _SKILL_TREE_BADGE_ICON_CACHE[cache_key] = None
        return None

    sheet_id, row, col = source
    sheet = _SKILL_TREE_BADGE_SHEET_CACHE.get(sheet_id)
    if sheet_id not in _SKILL_TREE_BADGE_SHEET_CACHE:
        path = SPELL_ICON_SHEETS.get(sheet_id, "")
        if path and os.path.exists(path):
            try:
                sheet = pygame.image.load(path).convert_alpha()
            except pygame.error:
                sheet = None
        else:
            sheet = None
        _SKILL_TREE_BADGE_SHEET_CACHE[sheet_id] = sheet

    if not isinstance(sheet, pygame.Surface):
        _SKILL_TREE_BADGE_ICON_CACHE[cache_key] = None
        return None

    try:
        tile = extract_sheet_tile(sheet, int(row), int(col), 32)
    except (ValueError, IndexError, pygame.error):
        _SKILL_TREE_BADGE_ICON_CACHE[cache_key] = None
        return None

    icon = pygame.transform.smoothscale(tile, (int(size), int(size)))
    _SKILL_TREE_BADGE_ICON_CACHE[cache_key] = icon
    return icon


def _skill_tree_upgrade_motif(node_id: str, node: Dict[str, object]) -> str:
    mods = _skill_tree_extract_mods(node)
    signature = f"{node.get('name', '')} {node.get('desc', '')}".lower()
    if "pierce_bonus" in mods or any(word in signature for word in ("pierce", "impale", "spear", "lance", "skewer", "shatterbone")):
        return "spear"
    if "projectile_count_bonus" in mods or any(word in signature for word in ("twin", "split", "volley", "fan", "crosswind", "barrage")):
        return "volley"
    if "radius_mult" in mods or "max_radius_mult" in mods or any(word in signature for word in ("radius", "blast", "wide", "wider", "expands", "spiral", "halo")):
        return "ring"
    if "cooldown_mult" in mods or "interval_mult" in mods or any(word in signature for word in ("cooldown", "faster", "cadence", "recovery", "tick", "aftershock")):
        return "hourglass"
    if "duration_mult" in mods or any(word in signature for word in ("duration", "linger", "longer", "uptime", "persists", "quartermaster")):
        return "banner"
    if "speed_mult" in mods or any(word in signature for word in ("speed", "swift", "march", "accelerates", "gale")):
        return "wing"
    if "mana_mult" in mods or any(word in signature for word in ("mana", "cheaper", "efficiency", "easing")):
        return "drop"
    return "burst"


def _skill_tree_node_bonus_lines(
    node_id: str,
    node: Dict[str, object],
    spell_lookup: Dict[str, Dict[str, object]],
    unlock_nodes: List[Dict[str, object]],
) -> List[str]:
    lines: List[str] = []
    bonus_power = float(node.get("bonus_power", 0.0))
    if bonus_power > 0.0:
        lines.append(f"Spell power +{bonus_power:.1f}")
    cdr = float(node.get("cooldown_reduction", 0.0))
    if cdr > 0.0:
        lines.append(f"Cooldown recovery +{int(round(cdr * 100))}%")

    mod_labels = {
        "damage_mult": "Damage",
        "cooldown_mult": "Cooldown",
        "mana_mult": "Mana cost",
        "radius_mult": "Radius",
        "max_radius_mult": "Blast radius",
        "duration_mult": "Duration",
        "interval_mult": "Tick rate",
        "speed_mult": "Speed",
        "projectile_count_bonus": "Projectiles",
        "pierce_bonus": "Pierce",
        "impact_nova_radius_bonus": "Impact nova",
        "cast_range_bonus": "Cast range",
        "spread_deg_bonus": "Spread",
    }
    for key, val in _skill_tree_extract_mods(node).items():
        label = mod_labels.get(str(key))
        if not label:
            continue
        if str(key).endswith("_mult"):
            pct = int(round((float(val) - 1.0) * 100))
            sign = "+" if pct >= 0 else ""
            lines.append(f"{label} {sign}{pct}%")
        else:
            sign = "+" if float(val) >= 0 else ""
            lines.append(f"{label} {sign}{int(round(float(val)))}")

    if not lines:
        node_type = _skill_tree_node_type_label(node_id, node)
        if node_type == "Core":
            lines.append("Enables the mastery tree and your class progression path.")
        elif node_type == "Passive":
            lines.append("Improves your combat efficiency and class identity.")
        elif node_type == "Upgrade":
            lines.append("Enhances an existing spell with new combat properties.")
        else:
            spell_id = _skill_tree_node_spell_id(node_id, node, unlock_nodes)
            spell_name = str(spell_lookup.get(spell_id, {}).get("name", node.get("name", "Spell")))
            lines.append(f"Unlocks {spell_name} for combat use.")
    return lines[:4]


def _build_skill_tree_icon(
    node_id: str,
    node: Dict[str, object],
    size: int,
    spell_icons: Dict[str, pygame.Surface],
    unlock_nodes: List[Dict[str, object]],
    core_col: Tuple[int, int, int],
    accent_col: Tuple[int, int, int],
    shadow_col: Tuple[int, int, int],
    brass: Tuple[int, int, int],
    badge_font: pygame.font.Font,
) -> pygame.Surface:
    sid = _skill_tree_node_spell_id(node_id, node, unlock_nodes)
    base = spell_icons.get(sid)
    node_type = _skill_tree_node_type_label(node_id, node)
    icon = pygame.Surface((size, size), pygame.SRCALPHA)
    center = (size // 2, size // 2)
    shell_col = _blend_ui_color((14, 16, 22), shadow_col, 0.22)
    pygame.draw.circle(icon, shell_col, center, size // 2)
    pygame.draw.circle(icon, _blend_ui_color((92, 102, 120), brass, 0.42), center, size // 2, 2)
    pygame.draw.circle(icon, _blend_ui_color((18, 20, 26), shadow_col, 0.18), center, max(8, size // 2 - 5))

    art_size = max(18, size - 12)
    if isinstance(base, pygame.Surface):
        art = pygame.transform.smoothscale(base, (art_size, art_size)).copy()
    else:
        fallback = make_fallback_icon(_blend_ui_color(core_col, accent_col, 0.45))
        art = pygame.transform.smoothscale(fallback, (art_size, art_size)).copy()
    if node_type == "Upgrade":
        art.set_alpha(76)
    icon.blit(art, art.get_rect(center=center))

    if node_type == "Upgrade":
        rune_glow = _brighten_ui_color(core_col, 24)
        rune_edge = _brighten_ui_color(accent_col, 12)
        inner_r = max(9, size // 2 - 9)
        pygame.draw.circle(icon, (*rune_glow, 34), center, inner_r)
        pygame.draw.circle(icon, rune_edge, center, inner_r, 1)
        motif = _skill_tree_upgrade_motif(node_id, node)
        badge_icon = _load_skill_tree_badge_icon(f"upgrade_{motif}", max(14, size - 16))
        if isinstance(badge_icon, pygame.Surface):
            overlay = badge_icon.copy()
            overlay.set_alpha(174)
            icon.blit(overlay, overlay.get_rect(center=center))

        cx, cy = center
        if motif == "spear":
            pygame.draw.line(icon, rune_edge, (cx, cy + 8), (cx, cy - 8), 3)
            pygame.draw.polygon(icon, rune_glow, [(cx, cy - 13), (cx - 4, cy - 6), (cx + 4, cy - 6)])
            pygame.draw.line(icon, rune_glow, (cx - 6, cy + 1), (cx + 6, cy + 1), 2)
        elif motif == "volley":
            for dx in (-6, 0, 6):
                pygame.draw.line(icon, rune_edge, (cx + dx // 3, cy + 8), (cx + dx, cy - 6), 2)
                pygame.draw.polygon(icon, rune_glow, [(cx + dx, cy - 10), (cx + dx - 3, cy - 4), (cx + dx + 3, cy - 4)])
        elif motif == "ring":
            pygame.draw.circle(icon, rune_edge, center, 10, 2)
            pygame.draw.circle(icon, rune_glow, center, 5, 1)
            for ox, oy in ((0, -12), (10, 0), (0, 12), (-10, 0)):
                pygame.draw.circle(icon, rune_glow, (cx + ox, cy + oy), 2)
        elif motif == "hourglass":
            pygame.draw.polygon(icon, rune_edge, [(cx - 6, cy - 8), (cx + 6, cy - 8), (cx, cy - 1)], 2)
            pygame.draw.polygon(icon, rune_edge, [(cx - 6, cy + 8), (cx + 6, cy + 8), (cx, cy + 1)], 2)
            pygame.draw.line(icon, rune_glow, (cx - 4, cy - 6), (cx + 4, cy + 6), 1)
            pygame.draw.line(icon, rune_glow, (cx + 4, cy - 6), (cx - 4, cy + 6), 1)
        elif motif == "banner":
            pygame.draw.line(icon, rune_edge, (cx - 6, cy + 8), (cx - 6, cy - 10), 2)
            pygame.draw.polygon(icon, rune_glow, [(cx - 5, cy - 9), (cx + 7, cy - 6), (cx + 2, cy - 1), (cx + 7, cy + 3), (cx - 5, cy + 5)])
        elif motif == "wing":
            pygame.draw.line(icon, rune_edge, (cx - 8, cy + 6), (cx - 1, cy - 7), 2)
            pygame.draw.line(icon, rune_edge, (cx + 8, cy + 6), (cx + 1, cy - 7), 2)
            pygame.draw.line(icon, rune_glow, (cx - 4, cy + 2), (cx, cy - 2), 2)
            pygame.draw.line(icon, rune_glow, (cx + 4, cy + 2), (cx, cy - 2), 2)
        elif motif == "drop":
            pygame.draw.polygon(icon, rune_glow, [(cx, cy - 10), (cx + 7, cy), (cx + 3, cy + 9), (cx - 3, cy + 9), (cx - 7, cy)])
            pygame.draw.line(icon, rune_edge, (cx, cy - 7), (cx, cy + 6), 1)
        else:
            burst = [(cx, cy - 10), (cx + 3, cy - 3), (cx + 10, cy), (cx + 3, cy + 3), (cx, cy + 10), (cx - 3, cy + 3), (cx - 10, cy), (cx - 3, cy - 3)]
            pygame.draw.polygon(icon, rune_glow, burst)
            pygame.draw.polygon(icon, rune_edge, burst, 1)

        if node_id.endswith("_tier3"):
            pygame.draw.circle(icon, _brighten_ui_color(rune_edge, 18), center, inner_r - 3, 1)
            pygame.draw.arc(icon, rune_glow, pygame.Rect(cx - 12, cy - 12, 24, 24), 0.25, 2.7, 1)

    glyph = ""
    if node_type == "Core":
        glyph = "C"
    elif node_type == "Passive":
        glyph = "P"
    elif node_type == "Upgrade":
        glyph = "U"
    if glyph:
        plate_center = (8, 8)
        pygame.draw.circle(icon, (12, 14, 18), plate_center, 6)
        pygame.draw.circle(icon, brass, plate_center, 6, 1)
        gs = badge_font.render(glyph, True, (240, 232, 206))
        icon.blit(gs, gs.get_rect(center=plate_center))

    tier_text = "I"
    if node_id.endswith("_tier3"):
        tier_text = "III"
    elif node_id.endswith("_tier2"):
        tier_text = "II"
    elif node_type == "Core":
        tier_text = "0"
    elif node_type == "Passive":
        tier_text = "P"
    tier_center = (size - 8, size - 8)
    pygame.draw.circle(icon, shell_col, tier_center, 6)
    pygame.draw.circle(icon, _brighten_ui_color(brass, 26), tier_center, 6, 1)
    ts = badge_font.render(tier_text, True, (246, 238, 214))
    icon.blit(ts, ts.get_rect(center=tier_center))
    return icon


def _draw_skill_tree_type_badge(
    surface: pygame.Surface,
    rect: pygame.Rect,
    node_type: str,
    edge: Tuple[int, int, int],
    core_col: Tuple[int, int, int],
    accent_col: Tuple[int, int, int],
) -> None:
    pygame.draw.rect(surface, (12, 14, 18), rect, border_radius=7)
    pygame.draw.rect(surface, edge, rect, 1, border_radius=7)
    badge_key = "spell"
    if node_type == "Core":
        badge_key = "core"
    elif node_type == "Passive":
        badge_key = "passive"
    elif node_type == "Upgrade":
        badge_key = "upgrade_burst"
    badge_icon = _load_skill_tree_badge_icon(badge_key, max(10, min(rect.width, rect.height) - 4))
    if isinstance(badge_icon, pygame.Surface):
        surface.blit(badge_icon, badge_icon.get_rect(center=rect.center))
        return
    cx, cy = rect.center
    if node_type == "Core":
        pygame.draw.circle(surface, _brighten_ui_color(accent_col, 18), (cx, cy), 3)
        pygame.draw.circle(surface, _brighten_ui_color(core_col, 26), (cx, cy), 6, 1)
    elif node_type == "Upgrade":
        diamond = [(cx, cy - 4), (cx + 4, cy), (cx, cy + 4), (cx - 4, cy)]
        pygame.draw.polygon(surface, _brighten_ui_color(core_col, 22), diamond)
        pygame.draw.polygon(surface, _brighten_ui_color(accent_col, 10), diamond, 1)
        pygame.draw.line(surface, _brighten_ui_color(accent_col, 14), (cx, cy + 5), (cx, cy - 6), 1)
    elif node_type == "Passive":
        pygame.draw.polygon(surface, _brighten_ui_color(accent_col, 16), [(cx, cy - 5), (cx + 4, cy - 1), (cx + 2, cy + 5), (cx - 2, cy + 5), (cx - 4, cy - 1)])
        pygame.draw.line(surface, _brighten_ui_color(core_col, 18), (cx, cy - 3), (cx, cy + 4), 1)
    else:
        spark = [(cx, cy - 5), (cx + 2, cy - 1), (cx + 6, cy), (cx + 2, cy + 1), (cx, cy + 5), (cx - 2, cy + 1), (cx - 6, cy), (cx - 2, cy - 1)]
        pygame.draw.polygon(surface, _brighten_ui_color(core_col, 18), spark)
        pygame.draw.polygon(surface, _brighten_ui_color(accent_col, 10), spark, 1)


def _draw_skill_tree_class_backdrop(
    surface: pygame.Surface,
    rect: pygame.Rect,
    class_id: str,
    core_col: Tuple[int, int, int],
    accent_col: Tuple[int, int, int],
    shadow_col: Tuple[int, int, int],
    ticks: int,
) -> None:
    if rect.width <= 24 or rect.height <= 24:
        return

    art = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    cx = rect.width // 2
    cy = rect.height // 2
    pulse = 0.45 + 0.55 * math.sin(ticks * 0.0018)
    haze_col = (*core_col, 12)
    rim_col = (*_brighten_ui_color(accent_col, 18), 24)

    pygame.draw.circle(art, haze_col, (cx, cy), min(rect.width, rect.height) // 3)
    pygame.draw.circle(art, rim_col, (cx, cy), max(24, min(rect.width, rect.height) // 4), 1)

    if class_id == "necromancer":
        skull = pygame.Rect(cx - 72, cy - 92, 144, 150)
        jaw = pygame.Rect(cx - 46, cy + 16, 92, 48)
        eye_y = cy - 28
        pygame.draw.ellipse(art, (*_brighten_ui_color(shadow_col, 10), 20), skull)
        pygame.draw.ellipse(art, (*_brighten_ui_color(accent_col, 18), 34), skull, 2)
        pygame.draw.rect(art, (*_brighten_ui_color(shadow_col, 6), 18), jaw, border_radius=18)
        pygame.draw.rect(art, (*_brighten_ui_color(accent_col, 10), 28), jaw, 2, border_radius=18)
        for ex in (-28, 28):
            pygame.draw.circle(art, (*_darken_ui_color(shadow_col, 14), 42), (cx + ex, eye_y), 16)
            pygame.draw.circle(art, (*_brighten_ui_color(core_col, 20), 34), (cx + ex, eye_y), 7)
        pygame.draw.polygon(art, (*_brighten_ui_color(core_col, 20), 28), [(cx, cy - 6), (cx - 11, cy + 14), (cx + 11, cy + 14)])
        for offset in range(-32, 33, 16):
            pygame.draw.line(art, (*_brighten_ui_color(accent_col, 12), 24), (cx + offset, cy + 28), (cx + offset, cy + 58), 1)
        for angle in range(0, 360, 45):
            rad = math.radians(angle)
            px = cx + int(math.cos(rad) * 104)
            py = cy + int(math.sin(rad) * 104)
            pygame.draw.circle(art, (*_brighten_ui_color(core_col, 20), 26), (px, py), 4)
    elif class_id == "mage":
        pygame.draw.circle(art, (*_brighten_ui_color(accent_col, 20), 28), (cx, cy), 86, 2)
        star = []
        for idx in range(10):
            ang = -math.pi / 2 + idx * math.pi / 5
            radius = 82 if idx % 2 == 0 else 34
            star.append((cx + int(math.cos(ang) * radius), cy + int(math.sin(ang) * radius)))
        pygame.draw.polygon(art, (*_brighten_ui_color(core_col, 22), 24), star, 2)
        pygame.draw.line(art, (*_brighten_ui_color(accent_col, 18), 22), (cx - 110, cy), (cx + 110, cy), 1)
        pygame.draw.line(art, (*_brighten_ui_color(accent_col, 18), 22), (cx, cy - 110), (cx, cy + 110), 1)
    elif class_id == "rogue":
        pygame.draw.arc(art, (*_brighten_ui_color(accent_col, 18), 28), pygame.Rect(cx - 88, cy - 88, 176, 176), 0.8, 4.8, 3)
        dagger = [(cx - 10, cy + 70), (cx + 10, cy + 70), (cx + 4, cy - 28), (cx + 12, cy - 56), (cx, cy - 96), (cx - 12, cy - 56), (cx - 4, cy - 28)]
        pygame.draw.polygon(art, (*_brighten_ui_color(core_col, 20), 30), dagger)
        pygame.draw.polygon(art, (*_brighten_ui_color(accent_col, 12), 24), dagger, 1)
    elif class_id == "ranger":
        pygame.draw.arc(art, (*_brighten_ui_color(accent_col, 18), 28), pygame.Rect(cx - 100, cy - 70, 200, 140), 1.9, 4.4, 3)
        pygame.draw.line(art, (*_brighten_ui_color(core_col, 22), 24), (cx - 48, cy - 78), (cx + 64, cy + 78), 2)
        for offset in (-36, 0, 36):
            pygame.draw.line(art, (*_brighten_ui_color(accent_col, 14), 22), (cx + offset, cy - 78), (cx + offset + 32, cy - 110), 2)
    elif class_id == "warrior":
        shield = pygame.Rect(cx - 76, cy - 98, 152, 176)
        pygame.draw.ellipse(art, (*_brighten_ui_color(shadow_col, 12), 18), shield)
        pygame.draw.ellipse(art, (*_brighten_ui_color(accent_col, 14), 24), shield, 2)
        pygame.draw.line(art, (*_brighten_ui_color(core_col, 20), 24), (cx - 92, cy + 82), (cx + 28, cy - 72), 3)
        pygame.draw.line(art, (*_brighten_ui_color(core_col, 20), 24), (cx + 92, cy + 82), (cx - 28, cy - 72), 3)
    elif class_id == "paladin":
        pygame.draw.circle(art, (*_brighten_ui_color(accent_col, 18), 28), (cx, cy - 24), 82, 2)
        pygame.draw.line(art, (*_brighten_ui_color(core_col, 22), 26), (cx, cy - 118), (cx, cy + 98), 3)
        pygame.draw.line(art, (*_brighten_ui_color(core_col, 22), 24), (cx - 44, cy - 30), (cx + 44, cy - 30), 3)
        for ray in range(-2, 3):
            pygame.draw.line(art, (*_brighten_ui_color(accent_col, 16), 18), (cx + ray * 18, cy - 104), (cx + ray * 28, cy - 144), 2)
    else:
        pygame.draw.circle(art, (*_brighten_ui_color(accent_col, 18), 24), (cx, cy), 90, 2)
        pygame.draw.circle(art, (*_brighten_ui_color(core_col, 18), 24), (cx, cy), 42, 1)

    surface.blit(art, rect.topleft)


def draw_skill_tree(
    screen: pygame.Surface,
    class_name: str,
    skill_tree_nodes: List[Dict[str, object]],
    unlocked_skills: Set[str],
    skill_points: int,
    skill_hover: Optional[str],
    title_font: pygame.font.Font,
    node_font: pygame.font.Font,
    info_font: pygame.font.Font,
    spell_icons: Dict[str, pygame.Surface],
) -> Dict[str, pygame.Rect]:
    ticks = pygame.time.get_ticks()
    t_sec = ticks / 1000.0
    class_id = normalize_class_id(class_name)
    class_data = CLASS_ARCHETYPES.get(class_id, {})
    class_desc = str(class_data.get("description", "Master your class through disciplined progression."))
    _pal = CLASS_PALETTES.get(class_id, CLASS_PALETTES["default"])
    accent = _pal["primary"]

    # ── Ornate backdrop: deep vignette + radial class-tinted glow + drifting motes ──
    overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    overlay.fill((6, 4, 10, 234))
    # Radial class-tinted wash around screen center
    _cx = SCREEN_WIDTH // 2
    _cy = SCREEN_HEIGHT // 2
    _max_r = int(math.hypot(_cx, _cy))
    for _ri in range(6, 0, -1):
        _rr = int(_max_r * (_ri / 6.0))
        _a = int(18 * (1.0 - _ri / 6.0))
        pygame.draw.circle(overlay, (accent[0] // 6, accent[1] // 6, accent[2] // 6, _a), (_cx, _cy), _rr)
    screen.blit(overlay, (0, 0))
    # Drifting ember/rune motes (animated backdrop VFX)
    for _mi in range(28):
        _mx_n = (0.11 * _mi + 0.07 * math.sin(t_sec * 0.3 + _mi * 1.7)) % 1.0
        _my_n = ((t_sec * 0.03 + _mi * 0.097) % 1.2) - 0.1
        _mx = int(_mx_n * SCREEN_WIDTH)
        _my = int(_my_n * SCREEN_HEIGHT)
        if 0 <= _my < SCREEN_HEIGHT:
            _ma = int(50 + 60 * (0.5 + 0.5 * math.sin(t_sec * 1.2 + _mi)))
            _ms = pygame.Surface((6, 6), pygame.SRCALPHA)
            pygame.draw.circle(_ms, (accent[0], accent[1], accent[2], _ma), (3, 3), 3)
            pygame.draw.circle(_ms, (255, 240, 200, min(255, _ma + 40)), (3, 3), 1)
            screen.blit(_ms, (_mx - 3, _my - 3))

    # ── Ornate multi-ring panel backdrop (parchment + brass bezel) ──
    panel = pygame.Rect(48, 36, SCREEN_WIDTH - 96, SCREEN_HEIGHT - 72)
    # Drop shadow
    _sh = pygame.Surface((panel.width + 16, panel.height + 16), pygame.SRCALPHA)
    pygame.draw.rect(_sh, (0, 0, 0, 160), _sh.get_rect(), border_radius=10)
    screen.blit(_sh, (panel.left - 8, panel.top - 2))
    # Parchment body
    pygame.draw.rect(screen, (18, 16, 22), panel, border_radius=8)
    pygame.draw.rect(screen, (28, 22, 28), panel.inflate(-4, -4), border_radius=7)
    # Multi-ring bronze/iron/gold bezel
    pygame.draw.rect(screen, (8, 6, 4), panel, 1, border_radius=8)
    pygame.draw.rect(screen, (78, 58, 28), panel.inflate(-2, -2), 1, border_radius=8)
    pygame.draw.rect(screen, (168, 126, 54), panel.inflate(-4, -4), 1, border_radius=7)
    pygame.draw.rect(screen, (226, 184, 94), panel.inflate(-5, -5), 1, border_radius=7)
    pygame.draw.rect(screen, (78, 58, 28), panel.inflate(-7, -7), 1, border_radius=6)
    pygame.draw.rect(screen, (8, 6, 4), panel.inflate(-9, -9), 1, border_radius=6)
    # Corner rivets
    for _cx_r, _cy_r in (
        (panel.left + 12, panel.top + 12),
        (panel.right - 12, panel.top + 12),
        (panel.left + 12, panel.bottom - 12),
        (panel.right - 12, panel.bottom - 12),
    ):
        pygame.draw.circle(screen, (8, 6, 4), (_cx_r, _cy_r), 4)
        pygame.draw.circle(screen, (178, 136, 60), (_cx_r, _cy_r), 3)
        pygame.draw.circle(screen, (254, 224, 150), (_cx_r - 1, _cy_r - 1), 1)
    inner = panel.inflate(-12, -12)

    header = pygame.Rect(inner.left + 20, inner.top + 18, inner.width - 40, 64)

    inspector_w = int(clamp(panel.width * 0.30, 300, 360))
    body_top = header.bottom + 16
    body_h = inner.bottom - body_top - 18
    graph = pygame.Rect(inner.left + 20, body_top, inner.width - inspector_w - 54, body_h)
    inspector = pygame.Rect(graph.right + 14, body_top, inspector_w, body_h)
    graph_inner = pygame.Rect(
        graph.left + 64,
        graph.top + 48,
        max(180, graph.width - 104),
        max(180, graph.height - 96),
    )

    node_rects = skill_tree_layout(graph_inner, skill_tree_nodes)
    node_by_id = {str(node["id"]): node for node in skill_tree_nodes}
    req_name_by_id = {nid: str(node.get("name", nid)) for nid, node in node_by_id.items()}
    unlock_nodes = [n for n in skill_tree_nodes if n.get("spell")]
    unlock_nodes.sort(key=lambda n: float(n.get("pos", (0.0, 0.0))[0]))
    spell_lookup = {str(spell.get("id", "")): spell for spell in class_spellbook(class_id)}

    unlocked_count = sum(1 for node_id in node_by_id if node_id in unlocked_skills)
    available_count = 0
    for node_id, node in node_by_id.items():
        if node_id in unlocked_skills:
            continue
        reqs = [str(req) for req in node.get("requires", [])]
        if all(req in unlocked_skills for req in reqs):
            available_count += 1

    focus_node_id = skill_hover if skill_hover in node_by_id else None
    if focus_node_id is None:
        for node in skill_tree_nodes:
            nid = str(node["id"])
            if nid in unlocked_skills:
                continue
            reqs = [str(req) for req in node.get("requires", [])]
            if all(req in unlocked_skills for req in reqs):
                focus_node_id = nid
                break
    if focus_node_id is None and skill_tree_nodes:
        focus_node_id = str(skill_tree_nodes[0]["id"])
    focus_node = node_by_id.get(str(focus_node_id), skill_tree_nodes[0] if skill_tree_nodes else {"id": "unknown"})
    focus_node_id = str(focus_node.get("id", "unknown"))

    # Keep these around because _build_skill_tree_icon / _draw_skill_tree_type_badge expect them
    core_col, accent_col, shadow_col = spell_vfx_palette(f"{class_id}_skill_tree", {})
    brass = (190, 162, 100)

    title_font_big = _skill_tree_font(24, bold=True, flavor="title")
    hero_name_font = _skill_tree_font(22, bold=True, flavor="title")
    section_font = _skill_tree_font(15, bold=True, flavor="title")
    caption_font = _skill_tree_font(11, bold=True, flavor="label")
    card_title_font = _skill_tree_font(10, bold=True, flavor="title")
    card_meta_font = _skill_tree_font(10, flavor="label")
    detail_font = _skill_tree_font(13, flavor="label")
    detail_bold = _skill_tree_font(14, bold=True, flavor="title")
    badge_font = _skill_tree_font(10, bold=True, flavor="title")
    icon_cache: Dict[Tuple[str, int], pygame.Surface] = {}

    def get_icon(node_id: str, node: Dict[str, object], size: int) -> pygame.Surface:
        key = (node_id, size)
        cached = icon_cache.get(key)
        if isinstance(cached, pygame.Surface):
            return cached
        icon = _build_skill_tree_icon(
            node_id, node, size, spell_icons, unlock_nodes,
            core_col, accent_col, shadow_col, brass, badge_font,
        )
        icon_cache[key] = icon
        return icon

    # ── Header: ornate title plaque with class sigil + stat chips ──
    # Title plaque background
    _hdr_bg = pygame.Rect(header.left, header.top, header.width, header.height)
    pygame.draw.rect(screen, (22, 18, 26), _hdr_bg, border_radius=5)
    pygame.draw.rect(screen, (78, 58, 28), _hdr_bg, 1, border_radius=5)
    pygame.draw.rect(screen, (168, 126, 54), _hdr_bg.inflate(-2, -2), 1, border_radius=4)
    # Class sigil medallion in header
    _sigil_cx = header.left + 36
    _sigil_cy = header.top + header.height // 2
    pygame.draw.circle(screen, (8, 6, 4), (_sigil_cx, _sigil_cy), 22)
    pygame.draw.circle(screen, (50, 36, 20), (_sigil_cx, _sigil_cy), 20)
    pygame.draw.circle(screen, (168, 126, 54), (_sigil_cx, _sigil_cy), 18, 2)
    pygame.draw.circle(screen, (accent[0], accent[1], accent[2]), (_sigil_cx, _sigil_cy), 14)
    pygame.draw.circle(screen, (226, 184, 94), (_sigil_cx, _sigil_cy), 14, 1)
    # Class initial letter inside sigil
    _init_s = title_font_big.render(class_name[0].upper() if class_name else "?", True, (252, 240, 200))
    screen.blit(_init_s, (_sigil_cx - _init_s.get_width() // 2, _sigil_cy - _init_s.get_height() // 2))
    # Title text
    title = title_font_big.render(f"{class_name} — Skill Tree", True, (236, 230, 214))
    _title_sh = title_font_big.render(f"{class_name} — Skill Tree", True, (0, 0, 0))
    screen.blit(_title_sh, (header.left + 65, header.top + 9))
    screen.blit(title, (header.left + 64, header.top + 8))
    hint = caption_font.render("Hover to inspect   •   Click to unlock   •   [K] Close", True, (148, 146, 138))
    screen.blit(hint, (header.left + 64, header.top + 38))

    # Ornate stat chips with brass ring borders
    chips = [(f"{skill_points}", "POINTS"), (f"{unlocked_count}/{len(node_by_id)}", "UNLOCKED"), (f"{available_count}", "READY")]
    chip_right = header.right - 6
    for value, label in reversed(chips):
        v_s = title_font_big.render(value, True, accent)
        l_s = caption_font.render(label, True, (190, 170, 130))
        chip_w = max(72, max(v_s.get_width(), l_s.get_width()) + 20)
        chip = pygame.Rect(chip_right - chip_w, header.top + 6, chip_w, 52)
        chip_right = chip.left - 8
        pygame.draw.rect(screen, (18, 16, 22), chip, border_radius=5)
        pygame.draw.rect(screen, (8, 6, 4), chip, 1, border_radius=5)
        pygame.draw.rect(screen, (94, 70, 32), chip.inflate(-2, -2), 1, border_radius=4)
        pygame.draw.rect(screen, (168, 126, 54), chip.inflate(-4, -4), 1, border_radius=3)
        screen.blit(v_s, (chip.centerx - v_s.get_width() // 2, chip.top + 6))
        screen.blit(l_s, (chip.centerx - l_s.get_width() // 2, chip.bottom - l_s.get_height() - 5))

    # Ornate separator with brass line + rivets
    _sep_y = header.bottom + 8
    pygame.draw.line(screen, (50, 36, 20), (inner.left + 20, _sep_y), (inner.right - 20, _sep_y), 1)
    pygame.draw.line(screen, (168, 126, 54), (inner.left + 20, _sep_y + 1), (inner.right - 20, _sep_y + 1), 1)
    for _rx in range(inner.left + 40, inner.right - 30, 80):
        pygame.draw.circle(screen, (178, 136, 60), (_rx, _sep_y), 2)
        pygame.draw.circle(screen, (254, 224, 150), (_rx - 1, _sep_y - 1), 1)

    # ── Graph panel: ornate inset with brass bezel ──
    pygame.draw.rect(screen, (14, 12, 18), graph, border_radius=6)
    pygame.draw.rect(screen, (8, 6, 4), graph, 1, border_radius=6)
    pygame.draw.rect(screen, (50, 36, 20), graph.inflate(-2, -2), 1, border_radius=5)
    pygame.draw.rect(screen, (94, 70, 32), graph.inflate(-4, -4), 1, border_radius=4)
    # Section title with underline accent
    _tn_s = section_font.render("Talent Network", True, (220, 216, 200))
    _tn_sh = section_font.render("Talent Network", True, (0, 0, 0))
    screen.blit(_tn_sh, (graph.left + 15, graph.top + 11))
    screen.blit(_tn_s, (graph.left + 14, graph.top + 10))
    pygame.draw.line(screen, (168, 126, 54), (graph.left + 14, graph.top + 30), (graph.left + 14 + _tn_s.get_width(), graph.top + 30), 1)

    # Tier rails (ornate with brass ticks + roman numeral labels)
    _tier_numerals = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII"]
    tier_positions = sorted({round(float(node.get("pos", (0.0, 0.0))[1]), 2) for node in skill_tree_nodes})
    for idx, py in enumerate(tier_positions):
        y = graph_inner.top + int(graph_inner.height * py)
        pygame.draw.line(screen, (34, 30, 40), (graph.left + 12, y), (graph.right - 12, y), 1)
        pygame.draw.line(screen, (60, 46, 24), (graph.left + 12, y + 1), (graph.right - 12, y + 1), 1)
        _tn = _tier_numerals[idx] if idx < len(_tier_numerals) else f"T{idx + 1}"
        tier_s = caption_font.render(_tn, True, (168, 136, 80))
        # Small brass bracket around tier label
        _tx = graph.left + 14
        _ty = y - tier_s.get_height() // 2
        pygame.draw.line(screen, (94, 70, 32), (_tx - 2, _ty - 1), (_tx - 2, _ty + tier_s.get_height() + 1), 1)
        screen.blit(tier_s, (_tx, _ty))

    # ── Connections: animated flowing lines for active, dim for locked ──
    for node in skill_tree_nodes:
        node_id = str(node["id"])
        child_rect = node_rects.get(node_id)
        if child_rect is None:
            continue
        for req in node.get("requires", []):
            req_id = str(req)
            parent_rect = node_rects.get(req_id)
            if parent_rect is None:
                continue
            start = (parent_rect.centerx, parent_rect.bottom - 4)
            end = (child_rect.centerx, child_rect.top + 4)
            rail_y = (start[1] + end[1]) // 2
            points = [start, (start[0], rail_y), (end[0], rail_y), end]
            is_active = req_id in unlocked_skills
            if is_active:
                # Glow underlay
                for a, b in zip(points, points[1:]):
                    _glow_s = pygame.Surface((abs(b[0] - a[0]) + 8, abs(b[1] - a[1]) + 8), pygame.SRCALPHA)
                    pygame.draw.line(_glow_s, (accent[0], accent[1], accent[2], 50),
                        (min(a[0], b[0]) - min(a[0], b[0]) + 4, min(a[1], b[1]) - min(a[1], b[1]) + 4),
                        (max(a[0], b[0]) - min(a[0], b[0]) + 4, max(a[1], b[1]) - min(a[1], b[1]) + 4), 6)
                    screen.blit(_glow_s, (min(a[0], b[0]) - 4, min(a[1], b[1]) - 4))
                # Bright core line
                for a, b in zip(points, points[1:]):
                    pygame.draw.line(screen, accent, a, b, 2)
                # Flowing energy dot
                _flow_t = (t_sec * 0.4 + hash(req_id) * 0.1) % 1.0
                _seg_count = len(points) - 1
                _seg_idx = min(int(_flow_t * _seg_count), _seg_count - 1)
                _seg_t = (_flow_t * _seg_count) - _seg_idx
                _fa = points[_seg_idx]
                _fb = points[_seg_idx + 1]
                _fx = int(_fa[0] + (_fb[0] - _fa[0]) * _seg_t)
                _fy = int(_fa[1] + (_fb[1] - _fa[1]) * _seg_t)
                pygame.draw.circle(screen, (255, 255, 255), (_fx, _fy), 3)
                pygame.draw.circle(screen, accent, (_fx, _fy), 2)
            else:
                # Dim dashed-style locked line
                for a, b in zip(points, points[1:]):
                    pygame.draw.line(screen, (50, 48, 60), a, b, 1)

    # ── Node cards: ornate with status glow, brass borders, pulsing when available ──
    for node_id, rect in node_rects.items():
        node = node_by_id[node_id]
        reqs = [str(req) for req in node.get("requires", [])]
        unlocked = node_id in unlocked_skills
        available = all(req in unlocked_skills for req in reqs)
        affordable = int(node.get("cost", 0)) <= skill_points
        focused = node_id == focus_node_id
        hovered = node_id == skill_hover

        if unlocked:
            edge = accent
            txt = (236, 232, 216)
        elif available and affordable:
            edge = (210, 180, 100)
            txt = (232, 226, 208)
        elif available:
            edge = (170, 90, 90)
            txt = (220, 200, 200)
        else:
            edge = (70, 74, 88)
            txt = (170, 172, 182)

        card = rect.inflate(-2, -2)

        # Glow aura for unlocked/available nodes
        if unlocked or (available and affordable):
            _glow_col = accent if unlocked else (210, 180, 100)
            _glow_pulse = 0.6 + 0.4 * (0.5 + 0.5 * math.sin(t_sec * 2.0 + hash(node_id) * 0.3))
            _glow_a = int(40 * _glow_pulse) if unlocked else int(55 * _glow_pulse)
            _glow_surf = pygame.Surface((card.width + 16, card.height + 16), pygame.SRCALPHA)
            pygame.draw.rect(_glow_surf, (_glow_col[0], _glow_col[1], _glow_col[2], _glow_a),
                (0, 0, card.width + 16, card.height + 16), border_radius=8)
            screen.blit(_glow_surf, (card.left - 8, card.top - 8))

        # Card body with gradient feel
        pygame.draw.rect(screen, (18, 16, 24), card, border_radius=5)
        pygame.draw.rect(screen, (26, 24, 32), card.inflate(-2, -2), border_radius=4)

        # Multi-ring border (brass for unlocked/available, iron for locked)
        if unlocked or available:
            pygame.draw.rect(screen, (8, 6, 4), card, 1, border_radius=5)
            pygame.draw.rect(screen, (94, 70, 32), card.inflate(-2, -2), 1, border_radius=4)
            pygame.draw.rect(screen, edge, card.inflate(-4, -4), 1, border_radius=3)
        else:
            pygame.draw.rect(screen, (40, 38, 48), card, 1, border_radius=5)
            pygame.draw.rect(screen, edge, card.inflate(-2, -2), 1, border_radius=4)

        # Hovered/focused highlight ring
        if focused or hovered:
            pygame.draw.rect(screen, (226, 184, 94), card, 2, border_radius=5)

        icon = get_icon(node_id, node, 30)
        icon_center = (card.centerx, card.top + 24)
        screen.blit(icon, icon.get_rect(center=icon_center))

        text_left = card.left + 6
        text_width = card.width - 12
        title_lines = wrap_text_lines(card_title_font, str(node.get("name", node_id)), text_width, max_lines=2)
        title_y = card.top + 42
        for ti, title_line in enumerate(title_lines):
            _ts = card_title_font.render(title_line, True, txt)
            _ts_sh = card_title_font.render(title_line, True, (0, 0, 0))
            screen.blit(_ts_sh, (text_left + 1, title_y + ti * 12 + 1))
            screen.blit(_ts, (text_left, title_y + ti * 12))

        # Cost badge with brass ring
        cost = int(node.get("cost", 0))
        cost_s = card_meta_font.render(str(cost), True, (232, 222, 196))
        cost_bg = pygame.Rect(card.right - cost_s.get_width() - 10, card.top + 4, cost_s.get_width() + 8, cost_s.get_height() + 4)
        pygame.draw.rect(screen, (18, 16, 22), cost_bg, border_radius=3)
        pygame.draw.rect(screen, (94, 70, 32), cost_bg, 1, border_radius=3)
        screen.blit(cost_s, (cost_bg.left + 4, cost_bg.top + 2))

    # ── Inspector panel: ornate scroll/codex with brass bezel ──
    pygame.draw.rect(screen, (16, 14, 20), inspector, border_radius=6)
    pygame.draw.rect(screen, (22, 20, 28), inspector.inflate(-4, -4), border_radius=5)
    # Multi-ring bezel
    pygame.draw.rect(screen, (8, 6, 4), inspector, 1, border_radius=6)
    pygame.draw.rect(screen, (50, 36, 20), inspector.inflate(-2, -2), 1, border_radius=5)
    pygame.draw.rect(screen, (168, 126, 54), inspector.inflate(-4, -4), 1, border_radius=4)
    pygame.draw.rect(screen, (94, 70, 32), inspector.inflate(-6, -6), 1, border_radius=3)
    # Corner rivets on inspector
    for _icx, _icy in (
        (inspector.left + 10, inspector.top + 10),
        (inspector.right - 10, inspector.top + 10),
        (inspector.left + 10, inspector.bottom - 10),
        (inspector.right - 10, inspector.bottom - 10),
    ):
        pygame.draw.circle(screen, (8, 6, 4), (_icx, _icy), 3)
        pygame.draw.circle(screen, (178, 136, 60), (_icx, _icy), 2)

    focus_reqs = [req_name_by_id.get(str(req), str(req)) for req in focus_node.get("requires", [])]
    focus_unlocked = focus_node_id in unlocked_skills
    focus_available = all(str(req) in unlocked_skills for req in focus_node.get("requires", []))
    focus_affordable = int(focus_node.get("cost", 0)) <= skill_points
    if focus_unlocked:
        state_text = "Unlocked"
        state_col = (160, 220, 170)
    elif focus_available and focus_affordable:
        state_text = "Available"
        state_col = (232, 200, 130)
    elif focus_available:
        state_text = "Need Skill Points"
        state_col = (216, 140, 140)
    else:
        state_text = "Locked"
        state_col = (150, 156, 170)

    # Section header with brass underline
    _det_s = section_font.render("DETAILS", True, (190, 170, 130))
    screen.blit(_det_s, (inspector.left + 14, inspector.top + 12))
    pygame.draw.line(screen, (168, 126, 54), (inspector.left + 14, inspector.top + 32), (inspector.left + 14 + _det_s.get_width(), inspector.top + 32), 1)

    # Hero row with ornate icon frame
    hero_top = inspector.top + 40
    hero_icon_center = (inspector.left + 44, hero_top + 34)
    _hero_frame = pygame.Rect(inspector.left + 14, hero_top, 60, 60)
    pygame.draw.rect(screen, (18, 16, 22), _hero_frame, border_radius=5)
    pygame.draw.rect(screen, (8, 6, 4), _hero_frame, 1, border_radius=5)
    pygame.draw.rect(screen, (94, 70, 32), _hero_frame.inflate(-2, -2), 1, border_radius=4)
    pygame.draw.rect(screen, (168, 126, 54), _hero_frame.inflate(-4, -4), 1, border_radius=3)
    hero_icon = get_icon(focus_node_id, focus_node, 52)
    screen.blit(hero_icon, hero_icon.get_rect(center=hero_icon_center))
    # Status glow on hero icon if unlocked
    if focus_unlocked:
        _hero_glow = pygame.Surface((68, 68), pygame.SRCALPHA)
        pygame.draw.rect(_hero_glow, (accent[0], accent[1], accent[2], 35), (0, 0, 68, 68), border_radius=6)
        screen.blit(_hero_glow, (_hero_frame.left - 4, _hero_frame.top - 4))

    focus_name = hero_name_font.render(_truncate_ui_text(hero_name_font, str(focus_node.get("name", focus_node_id)), inspector.width - 100), True, (240, 232, 210))
    _fn_sh = hero_name_font.render(_truncate_ui_text(hero_name_font, str(focus_node.get("name", focus_node_id)), inspector.width - 100), True, (0, 0, 0))
    screen.blit(_fn_sh, (inspector.left + 87, hero_top + 3))
    screen.blit(focus_name, (inspector.left + 86, hero_top + 2))
    type_s = detail_font.render(_skill_tree_node_type_label(focus_node_id, focus_node), True, (182, 180, 168))
    screen.blit(type_s, (inspector.left + 86, hero_top + 26))
    state_s = detail_bold.render(state_text, True, state_col)
    screen.blit(state_s, (inspector.left + 86, hero_top + 44))

    y_cursor = hero_top + 76
    # Ornate brass divider
    pygame.draw.line(screen, (50, 36, 20), (inspector.left + 14, y_cursor), (inspector.right - 14, y_cursor), 1)
    pygame.draw.line(screen, (168, 126, 54), (inspector.left + 14, y_cursor + 1), (inspector.right - 14, y_cursor + 1), 1)
    y_cursor += 12

    # Description
    screen.blit(caption_font.render("DESCRIPTION", True, (148, 146, 138)), (inspector.left + 14, y_cursor))
    y_cursor += 18
    for line in wrap_text_lines(detail_font, str(focus_node.get("desc", "No description.")), inspector.width - 28, max_lines=4):
        line_s = detail_font.render(line, True, (188, 190, 198))
        screen.blit(line_s, (inspector.left + 14, y_cursor))
        y_cursor += line_s.get_height() + 2
    y_cursor += 10

    # Stats (Cost / Type / Spell / Requires)
    focus_type = _skill_tree_node_type_label(focus_node_id, focus_node)
    if focus_type in ("Core", "Passive"):
        linked_name = "Passive"
    else:
        linked_name = str(spell_lookup.get(_skill_tree_node_spell_id(focus_node_id, focus_node, unlock_nodes), {}).get("name", "None"))
    stat_items = [
        ("COST", str(int(focus_node.get("cost", 0)))),
        ("TYPE", focus_type),
        ("SPELL", linked_name),
        ("REQUIRES", str(len(focus_reqs))),
    ]
    for idx, (label, value) in enumerate(stat_items):
        x = inspector.left + 14 if idx % 2 == 0 else inspector.left + (inspector.width // 2) + 4
        y = y_cursor + (idx // 2) * 30
        screen.blit(caption_font.render(label, True, (148, 146, 138)), (x, y))
        screen.blit(detail_bold.render(_truncate_ui_text(detail_bold, value, inspector.width // 2 - 20), True, (228, 224, 208)), (x, y + 13))
    y_cursor += 64
    # Ornate brass divider
    pygame.draw.line(screen, (50, 36, 20), (inspector.left + 14, y_cursor), (inspector.right - 14, y_cursor), 1)
    pygame.draw.line(screen, (168, 126, 54), (inspector.left + 14, y_cursor + 1), (inspector.right - 14, y_cursor + 1), 1)
    y_cursor += 12

    # Benefits with ornate bullet jewels
    _ben_s = caption_font.render("BENEFITS", True, (190, 170, 130))
    screen.blit(_ben_s, (inspector.left + 14, y_cursor))
    pygame.draw.line(screen, (94, 70, 32), (inspector.left + 14, y_cursor + 14), (inspector.left + 14 + _ben_s.get_width(), y_cursor + 14), 1)
    y_cursor += 20
    for line in _skill_tree_node_bonus_lines(focus_node_id, focus_node, spell_lookup, unlock_nodes):
        _bul_col = state_col if (focus_unlocked or (focus_available and focus_affordable)) else (120, 122, 130)
        # Ornate diamond bullet
        _bx, _by = inspector.left + 18, y_cursor + 7
        pygame.draw.polygon(screen, _bul_col, [(_bx, _by - 4), (_bx + 4, _by), (_bx, _by + 4), (_bx - 4, _by)])
        pygame.draw.polygon(screen, (255, 255, 255), [(_bx, _by - 2), (_bx + 2, _by), (_bx, _by + 2), (_bx - 2, _by)], 1)
        line_s = detail_font.render(line, True, (200, 202, 212))
        screen.blit(line_s, (inspector.left + 28, y_cursor))
        y_cursor += line_s.get_height() + 4

    # Prerequisites with ornate divider
    req_y = inspector.bottom - 80
    pygame.draw.line(screen, (50, 36, 20), (inspector.left + 14, req_y - 8), (inspector.right - 14, req_y - 8), 1)
    pygame.draw.line(screen, (168, 126, 54), (inspector.left + 14, req_y - 7), (inspector.right - 14, req_y - 7), 1)
    _pre_s = caption_font.render("PREREQUISITES", True, (190, 170, 130))
    screen.blit(_pre_s, (inspector.left + 14, req_y))
    req_text = ", ".join(focus_reqs) if focus_reqs else "None"
    for ri, line in enumerate(wrap_text_lines(detail_font, req_text, inspector.width - 28, max_lines=2)):
        line_s = detail_font.render(line, True, (200, 202, 210))
        screen.blit(line_s, (inspector.left + 14, req_y + 16 + ri * (line_s.get_height() + 1)))

    # Footer with state-colored accent line
    footer_text = (
        "Already unlocked." if focus_unlocked
        else "Click to spend points and unlock." if (focus_available and focus_affordable)
        else "Need more skill points." if focus_available
        else "Unlock prerequisites first."
    )
    pygame.draw.line(screen, state_col, (inspector.left + 14, inspector.bottom - 28), (inspector.right - 14, inspector.bottom - 28), 1)
    footer_s = caption_font.render(_truncate_ui_text(caption_font, footer_text, inspector.width - 28), True, state_col)
    screen.blit(footer_s, (inspector.left + 14, inspector.bottom - 22))

    # ── Legend: ornate jewel-style indicators with brass frame ──
    _legend_bg = pygame.Rect(graph.left + 8, graph.bottom - 28, graph.width - 16, 24)
    pygame.draw.rect(screen, (14, 12, 18, 200), _legend_bg, border_radius=4)
    pygame.draw.rect(screen, (50, 36, 20), _legend_bg, 1, border_radius=4)
    legend_x = _legend_bg.left + 10
    legend_y = _legend_bg.centery
    for col, label in ((accent, "Unlocked"), ((210, 180, 100), "Ready"), ((170, 90, 90), "Need SP"), ((120, 124, 136), "Locked")):
        # Diamond indicator
        pygame.draw.polygon(screen, col, [
            (legend_x, legend_y - 4), (legend_x + 4, legend_y),
            (legend_x, legend_y + 4), (legend_x - 4, legend_y)])
        ls = caption_font.render(label, True, (190, 188, 178))
        screen.blit(ls, (legend_x + 8, legend_y - ls.get_height() // 2))
        legend_x += ls.get_width() + 36

    return node_rects

def try_unlock_skill(
    node_id: str,
    skill_tree_nodes: List[Dict[str, object]],
    unlocked_skills: Set[str],
    skill_points: int,
) -> Tuple[bool, int, str]:
    node = next((n for n in skill_tree_nodes if str(n["id"]) == node_id), None)
    if node is None:
        return False, skill_points, "Unknown skill."
    if node_id in unlocked_skills:
        return False, skill_points, "Skill already unlocked."
    if int(node["cost"]) > skill_points:
        return False, skill_points, "Not enough skill points."
    for req in node["requires"]:
        if str(req) not in unlocked_skills:
            return False, skill_points, "Missing prerequisite skill."

    unlocked_skills.add(node_id)
    new_points = skill_points - int(node["cost"])
    if node.get("spell"):
        return True, new_points, f"Unlocked {node['name']} and new spell."
    return True, new_points, f"Unlocked {node['name']}."


def draw_backpack_button_realistic(
    screen: pygame.Surface,
    rect: pygame.Rect,
    tiny_font: pygame.font.Font,
    backpack_count: int,
    backpack_capacity: int,
    hovered: bool,
    pressed: bool,
    ticks: int,
) -> None:
    y_offset = 1 if pressed else 0
    draw_rect = rect.move(0, y_offset)

    shadow = pygame.Surface((draw_rect.width + 12, draw_rect.height + 12), pygame.SRCALPHA)
    pygame.draw.ellipse(
        shadow,
        (0, 0, 0, 110 if hovered else 90),
        pygame.Rect(4, draw_rect.height - 2, draw_rect.width + 2, 10),
    )
    screen.blit(shadow, (draw_rect.left - 5, draw_rect.top - 3))

    button = pygame.Surface((draw_rect.width, draw_rect.height), pygame.SRCALPHA)
    outer = pygame.Rect(0, 0, draw_rect.width, draw_rect.height)
    inner = outer.inflate(-4, -4)
    leather = inner.inflate(-6, -6)
    cx = button.get_width() // 2

    # Steel frame with beveled edge.
    pygame.draw.rect(button, (38, 34, 30, 238), outer, border_radius=12)
    pygame.draw.rect(button, (120, 105, 86, 245), outer, 2, border_radius=12)
    pygame.draw.rect(button, (64, 56, 48, 220), inner, border_radius=10)

    # Worn leather body gradient.
    top_color = (174, 121, 73) if hovered else (154, 106, 64)
    bottom_color = (86, 52, 30) if hovered else (74, 44, 26)
    for y in range(leather.top, leather.bottom):
        t = (y - leather.top) / max(1, leather.height - 1)
        col = (
            int(top_color[0] + (bottom_color[0] - top_color[0]) * t),
            int(top_color[1] + (bottom_color[1] - top_color[1]) * t),
            int(top_color[2] + (bottom_color[2] - top_color[2]) * t),
        )
        pygame.draw.line(button, col, (leather.left, y), (leather.right - 1, y))
    pygame.draw.rect(button, (58, 36, 22), leather, 1, border_radius=9)

    # Top handle and flap.
    handle_rect = pygame.Rect(cx - 10, leather.top - 7, 20, 10)
    pygame.draw.ellipse(button, (120, 82, 52), handle_rect)
    pygame.draw.ellipse(button, (52, 34, 22), handle_rect, 1)

    flap = pygame.Rect(leather.left + 4, leather.top + 2, leather.width - 8, 14)
    pygame.draw.rect(button, (170, 116, 66), flap, border_radius=5)
    pygame.draw.rect(button, (62, 38, 22), flap, 1, border_radius=5)

    # Central strap and buckle.
    strap = pygame.Rect(cx - 4, flap.bottom - 2, 8, leather.height - 6)
    pygame.draw.rect(button, (92, 56, 30), strap, border_radius=2)
    pygame.draw.rect(button, (46, 28, 16), strap, 1, border_radius=2)

    buckle = pygame.Rect(cx - 6, flap.bottom + 7, 12, 10)
    pygame.draw.rect(button, (178, 150, 102), buckle, border_radius=2)
    pygame.draw.rect(button, (70, 56, 34), buckle, 1, border_radius=2)
    pygame.draw.rect(button, (66, 40, 22), buckle.inflate(-6, -4), border_radius=1)

    # Side pouches for depth.
    left_pouch = pygame.Rect(leather.left + 1, leather.top + 16, 9, 14)
    right_pouch = pygame.Rect(leather.right - 10, leather.top + 16, 9, 14)
    pygame.draw.rect(button, (134, 90, 54), left_pouch, border_radius=3)
    pygame.draw.rect(button, (134, 90, 54), right_pouch, border_radius=3)
    pygame.draw.rect(button, (56, 35, 20), left_pouch, 1, border_radius=3)
    pygame.draw.rect(button, (56, 35, 20), right_pouch, 1, border_radius=3)

    # Stitching around the flap and body.
    stitch_col = (210, 172, 120, 215)
    for x in range(flap.left + 3, flap.right - 2, 4):
        button.set_at((x, flap.top + 2), stitch_col)
    for y in range(leather.top + 10, leather.bottom - 4, 4):
        button.set_at((leather.left + 2, y), stitch_col)
        button.set_at((leather.right - 3, y), stitch_col)

    # Subtle specular highlight.
    highlight = pygame.Surface((leather.width, 14), pygame.SRCALPHA)
    hl_strength = 72 if hovered else 52
    for y in range(14):
        alpha = int(hl_strength * (1.0 - y / 13.0))
        pygame.draw.line(highlight, (248, 224, 184, alpha), (0, y), (leather.width - 1, y))
    button.blit(highlight, (leather.left, leather.top + 6))

    if hovered:
        glow = pygame.Surface((draw_rect.width + 6, draw_rect.height + 6), pygame.SRCALPHA)
        pulse = int(92 + 24 * math.sin(ticks * 0.006))
        pygame.draw.rect(glow, (214, 168, 92, pulse), glow.get_rect(), 2, border_radius=14)
        screen.blit(glow, (draw_rect.left - 3, draw_rect.top - 3))

    screen.blit(button, draw_rect.topleft)

    if backpack_count > 0:
        count_text = "99+" if backpack_count > 99 else str(backpack_count)
        badge_center = (draw_rect.right - 8, draw_rect.bottom - 7)
        badge_r = 11 if len(count_text) <= 2 else 13
        full_ratio = 0.0 if backpack_capacity <= 0 else clamp(backpack_count / float(backpack_capacity), 0.0, 1.0)
        badge_top = (196, 58, 42) if full_ratio >= 1.0 else (168, 46, 38)
        badge_bottom = (98, 24, 20)

        pygame.draw.circle(screen, (18, 10, 8), badge_center, badge_r + 2)
        for r in range(badge_r, 0, -1):
            t = 1.0 - (r / max(1.0, float(badge_r)))
            col = (
                int(badge_top[0] + (badge_bottom[0] - badge_top[0]) * t),
                int(badge_top[1] + (badge_bottom[1] - badge_top[1]) * t),
                int(badge_top[2] + (badge_bottom[2] - badge_top[2]) * t),
            )
            pygame.draw.circle(screen, col, badge_center, r)
        pygame.draw.circle(screen, (236, 196, 144), badge_center, badge_r, 1)

        badge_s = tiny_font.render(count_text, True, (255, 236, 214))
        screen.blit(
            badge_s,
            (badge_center[0] - badge_s.get_width() // 2, badge_center[1] - badge_s.get_height() // 2),
        )


def draw_item_bar(
    screen: pygame.Surface,
    item_inventory: List[Dict],
    tiny_font: pygame.font.Font,
    backpack_count: int = 0,
    backpack_capacity: int = BACKPACK_SLOT_COUNT,
    potion_shared_cd_pct: float = 0.0,   # 0–1 fraction of shared potion cooldown remaining
) -> Tuple[Dict[int, pygame.Rect], pygame.Rect]:
    """WoW-style consumable bar with radial cooldown and rarity-border slots."""
    max_potion_slots = 4
    slot_size = 48
    gap = 9
    ticks = pygame.time.get_ticks()

    # ── Layout: mirrored from new draw_spell_bar (slot_size=52, bar_h=78) ────
    spell_bar_h = 52 + 26
    spell_bar_top = SCREEN_HEIGHT - spell_bar_h - 12
    bar_w = max_potion_slots * slot_size + (max_potion_slots - 1) * gap + 28
    bar_h = slot_size + 22
    panel_x = (SCREEN_WIDTH - bar_w) // 2
    panel_y = spell_bar_top - bar_h - 7
    panel = pygame.Rect(panel_x, panel_y, bar_w, bar_h)

    # ── Panel background — obsidian with animated amber border ───────────────
    _bg = pygame.Surface((bar_w, bar_h), pygame.SRCALPHA)
    pygame.draw.rect(_bg, (10, 11, 15, 220), _bg.get_rect(), border_radius=12)
    screen.blit(_bg, panel.topleft)
    pygame.draw.rect(screen, (48, 44, 36), panel, 2, border_radius=12)
    _ib_a = int(68 + 30 * math.sin(ticks * 0.0014))
    _ib = panel.inflate(-3, -3)
    _ib_s = pygame.Surface((_ib.width, _ib.height), pygame.SRCALPHA)
    pygame.draw.rect(_ib_s, (140, 116, 58, _ib_a), _ib_s.get_rect(), 1, border_radius=10)
    screen.blit(_ib_s, _ib.topleft)

    # "CONSUMABLES" label at top of panel
    _lbl = tiny_font.render("CONSUMABLES", True, (140, 128, 90))
    screen.blit(_lbl, (panel.left + 10, panel.top + 3))

    mouse_pos = pygame.mouse.get_pos()
    hovered_item: Optional[Dict[str, object]] = None
    hovered_slot: Optional[pygame.Rect] = None

    slot_rects: Dict[int, pygame.Rect] = {}
    for i in range(max_potion_slots):
        sx = panel.left + 14 + i * (slot_size + gap)
        sy = panel.top + 14
        slot_rect = pygame.Rect(sx, sy, slot_size, slot_size)
        slot_rects[i] = slot_rect

        _slot_entry = item_inventory[i] if i < len(item_inventory) else None
        filled = _slot_entry is not None

        # Slot bg
        pygame.draw.rect(screen, (28, 24, 20) if filled else (20, 20, 28), slot_rect, border_radius=7)

        if filled:
            item = _slot_entry
            _col = tuple(item.get("color", (160, 160, 160)))
            _bdr_col = item_rarity_border(item)

            _icon = resolve_item_icon(item, slot_size - 8)
            if isinstance(_icon, pygame.Surface):
                screen.blit(_icon, (slot_rect.left + 4, slot_rect.top + 4))
            else:
                pygame.draw.rect(screen, _col, slot_rect.inflate(-8, -8), border_radius=5)

            # ── Radial shared-cooldown clock overlay ──────────────────────
            if potion_shared_cd_pct > 0.0:
                _draw_radial_cooldown(screen, slot_rect, potion_shared_cd_pct, (12, 12, 18, 195))

            # ── Stack count badge ─────────────────────────────────────────
            _qty = int(item.get("quantity", item.get("stack", 0)))
            if _qty > 1:
                _q_s = tiny_font.render(str(_qty), True, (230, 226, 200))
                _qr = pygame.Rect(slot_rect.right - _q_s.get_width() - 3, slot_rect.bottom - _q_s.get_height() - 1,
                                  _q_s.get_width() + 2, _q_s.get_height())
                pygame.draw.rect(screen, (14, 12, 18, 190), _qr, border_radius=3)
                screen.blit(_q_s, (_qr.left + 1, _qr.top))

            # Border
            if slot_rect.collidepoint(mouse_pos):
                hovered_item = item
                hovered_slot = slot_rect
                pygame.draw.rect(screen, (218, 214, 236), slot_rect, 2, border_radius=7)
            else:
                pygame.draw.rect(screen, _bdr_col, slot_rect, 1, border_radius=7)
        else:
            pygame.draw.rect(screen, (44, 42, 54), slot_rect, 1, border_radius=7)

        # Keybind label
        _k_col = (168, 160, 138) if filled else (80, 78, 72)
        _ks = tiny_font.render(str(i + 1), True, _k_col)
        screen.blit(_ks, (slot_rect.centerx - _ks.get_width() // 2, slot_rect.bottom - _ks.get_height() - 1))

    # ── Backpack button (bottom-right corner) ─────────────────────────────────
    bp_size = 52
    bp_x = SCREEN_WIDTH - bp_size - 14
    bp_y = SCREEN_HEIGHT - bp_size - 14
    backpack_btn_rect = pygame.Rect(bp_x, bp_y, bp_size, bp_size)
    _bp_hov = backpack_btn_rect.collidepoint(mouse_pos)
    _bp_pressed = _bp_hov and pygame.mouse.get_pressed(3)[0]
    draw_backpack_button_realistic(
        screen, backpack_btn_rect, tiny_font,
        backpack_count=backpack_count, backpack_capacity=backpack_capacity,
        hovered=_bp_hov, pressed=_bp_pressed, ticks=ticks,
    )

    if hovered_item is not None and hovered_slot is not None:
        draw_item_tooltip(screen, hovered_item, hovered_slot, tiny_font, tiny_font)
    return slot_rects, backpack_btn_rect


def build_gothic_cursor() -> Tuple[pygame.Surface, Tuple[int, int]]:
    cursor = pygame.Surface((28, 28), pygame.SRCALPHA)
    shadow = pygame.Surface((28, 28), pygame.SRCALPHA)

    # Shadow silhouette gives the cursor a heavier gothic silhouette.
    shadow_pts = [(5, 5), (5, 22), (10, 18), (13, 26), (17, 24), (14, 15), (23, 10)]
    pygame.draw.polygon(shadow, (0, 0, 0, 90), shadow_pts)
    cursor.blit(shadow, (1, 1))

    outline = (28, 24, 22)
    steel_dark = (86, 78, 70)
    steel_light = (204, 190, 156)
    bronze = (146, 112, 62)
    ember = (172, 48, 42)
    ember_glow = (232, 128, 96)

    blade_outer = [(4, 4), (4, 21), (9, 17), (12, 26), (16, 24), (13, 14), (22, 9)]
    blade_inner = [(6, 6), (6, 18), (9, 16), (11, 22), (13, 21), (11, 13), (18, 10)]
    pygame.draw.polygon(cursor, outline, blade_outer)
    pygame.draw.polygon(cursor, steel_dark, blade_outer)
    pygame.draw.polygon(cursor, steel_light, blade_inner)

    # Filigree and cross-guard motif.
    pygame.draw.line(cursor, bronze, (9, 16), (16, 12), 2)
    pygame.draw.line(cursor, outline, (8, 17), (17, 11), 1)
    pygame.draw.line(cursor, bronze, (11, 14), (14, 24), 2)
    pygame.draw.circle(cursor, outline, (12, 20), 3)
    pygame.draw.circle(cursor, ember, (12, 20), 2)
    pygame.draw.circle(cursor, ember_glow, (12, 20), 1)

    return cursor, (4, 4)


def build_pouch_cursor() -> Tuple[pygame.Surface, Tuple[int, int]]:
    """Pixel-art coin pouch cursor shown when hovering over vendors."""
    sz = 28
    surf = pygame.Surface((sz, sz), pygame.SRCALPHA)

    # Pouch body — a leather bag shape
    leather = (142, 92, 48)
    leather_hi = (186, 136, 72)
    leather_dk = (96, 58, 28)
    gold = (238, 198, 68)
    gold_hi = (255, 228, 128)
    string_col = (112, 78, 42)

    # Shadow
    shadow = pygame.Surface((sz, sz), pygame.SRCALPHA)
    pygame.draw.ellipse(shadow, (0, 0, 0, 70), (6, 10, 18, 17))
    surf.blit(shadow, (1, 1))

    # Bag body (rounded rect approximation)
    pygame.draw.ellipse(surf, leather_dk, (5, 10, 18, 16))
    pygame.draw.ellipse(surf, leather, (6, 11, 16, 14))
    pygame.draw.ellipse(surf, leather_hi, (8, 12, 10, 8))

    # Drawstring top
    pygame.draw.arc(surf, string_col, (8, 5, 12, 12), 0.3, 2.8, 2)
    pygame.draw.line(surf, string_col, (9, 10), (12, 6), 2)
    pygame.draw.line(surf, string_col, (19, 10), (16, 6), 2)

    # Gold coins peeking out
    pygame.draw.circle(surf, gold, (11, 9), 3)
    pygame.draw.circle(surf, gold_hi, (10, 8), 1)
    pygame.draw.circle(surf, gold, (17, 10), 3)
    pygame.draw.circle(surf, gold_hi, (16, 9), 1)

    # Coin $ marks
    pygame.draw.line(surf, leather_dk, (11, 8), (11, 11), 1)
    pygame.draw.line(surf, leather_dk, (17, 9), (17, 12), 1)

    return surf, (14, 14)


def build_vendor_shop_icon() -> pygame.Surface:
    """Small coin-pouch icon drawn above vendor nameplates."""
    sz = 20
    surf = pygame.Surface((sz, sz), pygame.SRCALPHA)
    gold = (238, 198, 68)
    gold_hi = (255, 228, 128)
    leather = (142, 92, 48)
    leather_hi = (186, 136, 72)
    leather_dk = (96, 58, 28)
    string_col = (112, 78, 42)

    # Bag body
    pygame.draw.ellipse(surf, leather_dk, (3, 7, 14, 12))
    pygame.draw.ellipse(surf, leather, (4, 8, 12, 10))
    pygame.draw.ellipse(surf, leather_hi, (6, 9, 7, 6))

    # Drawstring
    pygame.draw.arc(surf, string_col, (5, 3, 10, 10), 0.3, 2.8, 2)
    pygame.draw.line(surf, string_col, (6, 7), (8, 4), 1)
    pygame.draw.line(surf, string_col, (14, 7), (12, 4), 1)

    # Coin
    pygame.draw.circle(surf, gold, (10, 7), 3)
    pygame.draw.circle(surf, gold_hi, (9, 6), 1)

    return surf


def draw_gothic_cursor(
    screen: pygame.Surface,
    cursor_surface: pygame.Surface,
    hotspot: Tuple[int, int],
    mouse_pos: Tuple[int, int],
    pressed: bool,
) -> None:
    mx, my = mouse_pos
    hx, hy = hotspot
    dx = mx - hx
    dy = my - hy
    if pressed:
        glow = pygame.Surface((30, 30), pygame.SRCALPHA)
        pygame.draw.circle(glow, (178, 78, 64, 72), (15, 15), 10)
        screen.blit(glow, (mx - 15, my - 15))
        dx += 1
        dy += 1
    screen.blit(cursor_surface, (dx, dy))


def draw_hand_cursor(screen, sprite, hotspot, mouse_pos, ticks, hovering=False, pressed=False):
    """Animated gauntlet-hand cursor: pulsing arcane glow on the palm gem, brighter +
    a ring on hover, a small press offset, and an occasional fingertip twinkle."""
    mx, my = mouse_pos
    hx, hy = hotspot
    off = 1 if pressed else 0
    sw, sh = sprite.get_width(), sprite.get_height()
    gem_x = mx - hx + sw // 2 + off
    gem_y = my - hy + int(sh * 0.66) + off
    pulse = 0.5 + 0.5 * math.sin(ticks * 0.006)
    glow_r = int((9 + (5 if hovering else 0)) + 3 * pulse)
    alpha = int((46 + 60 * pulse) + (70 if hovering else 0))
    col = (150, 215, 255) if hovering else (96, 178, 255)
    if glow_r > 0:
        glow = pygame.Surface((glow_r * 2 + 2, glow_r * 2 + 2), pygame.SRCALPHA)
        pygame.draw.circle(glow, (*col, min(190, alpha)), (glow_r + 1, glow_r + 1), glow_r)
        pygame.draw.circle(glow, (*col, min(110, alpha // 2)), (glow_r + 1, glow_r + 1), max(2, glow_r // 2))
        screen.blit(glow, (gem_x - glow_r - 1, gem_y - glow_r - 1), special_flags=pygame.BLEND_RGBA_ADD)
    if hovering:
        ring_r = glow_r + 5
        ring = pygame.Surface((ring_r * 2 + 2, ring_r * 2 + 2), pygame.SRCALPHA)
        pygame.draw.circle(ring, (180, 225, 255, 120), (ring_r + 1, ring_r + 1), ring_r, 1)
        screen.blit(ring, (gem_x - ring_r - 1, gem_y - ring_r - 1), special_flags=pygame.BLEND_RGBA_ADD)
    screen.blit(sprite, (mx - hx + off, my - hy + off))
    tw = 0.5 + 0.5 * math.sin(ticks * 0.013 + 1.7)
    if tw > 0.6:
        ta = int(150 * (tw - 0.6) / 0.4)
        tx, ty = mx - hx + int(sw * 0.5), my - hy + 2
        spk = pygame.Surface((9, 9), pygame.SRCALPHA)
        pygame.draw.line(spk, (235, 248, 255, ta), (4, 1), (4, 7))
        pygame.draw.line(spk, (235, 248, 255, ta), (1, 4), (7, 4))
        screen.blit(spk, (tx - 4, ty - 4), special_flags=pygame.BLEND_RGBA_ADD)


def update_and_draw_cursor_fx(screen, fx_list, dt):
    """Advance + draw screen-space click ripples (expanding ring + sparks); prune finished."""
    if not fx_list:
        return
    alive = []
    for fx in fx_list:
        fx["t"] = fx.get("t", 0.0) + dt
        t = fx["t"]
        if t >= 0.42:
            continue
        alive.append(fx)
        p = t / 0.42
        cx, cy = fx["pos"]
        radius = int(6 + 30 * p)
        a = int(170 * (1.0 - p))
        col = (255, 150, 90) if fx.get("btn", 1) == 3 else (130, 200, 255)
        size = radius * 2 + 4
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.circle(surf, (*col, a), (size // 2, size // 2), radius, 2)
        if radius > 6:
            pygame.draw.circle(surf, (*col, a // 2), (size // 2, size // 2), radius - 4, 1)
        screen.blit(surf, (cx - size // 2, cy - size // 2), special_flags=pygame.BLEND_RGBA_ADD)
        for i in range(6):
            ang = (i / 6.0) * math.tau + t * 4.0
            sx, sy = cx + int(math.cos(ang) * radius), cy + int(math.sin(ang) * radius)
            sp = pygame.Surface((3, 3), pygame.SRCALPHA)
            sp.fill((*col, a))
            screen.blit(sp, (sx - 1, sy - 1), special_flags=pygame.BLEND_RGBA_ADD)
    fx_list[:] = alive


def draw_crafting_ui(
    screen: pygame.Surface,
    materials: Dict[str, int],
    recipes: List[Dict],
    selected_recipe_id: Optional[str],
    item_inventory: List[Dict],
    title_font: pygame.font.Font,
    node_font: pygame.font.Font,
    info_font: pygame.font.Font,
    tiny_font: pygame.font.Font,
) -> Dict[str, pygame.Rect]:
    """Draw crafting overlay. Returns dict of recipe_id -> clickable Rect."""
    overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 180))
    screen.blit(overlay, (0, 0))

    # Left panel — recipe list
    lp = pygame.Rect(60, 60, 520, SCREEN_HEIGHT - 120)
    draw_ornate_panel(screen, lp)
    title_s = title_font.render("Crafting", True, (234, 220, 180))
    screen.blit(title_s, (lp.centerx - title_s.get_width() // 2, lp.top + 14))

    recipe_rects: Dict[str, pygame.Rect] = {}
    cat_colors = {"Consumable": (80, 160, 100), "Enhancement": (100, 130, 200), "Special": (200, 170, 80)}
    y = lp.top + 64
    current_cat = ""
    for recipe in recipes:
        cat = recipe["category"]
        if cat != current_cat:
            current_cat = cat
            cat_s = tiny_font.render(f"── {cat} ──", True, cat_colors.get(cat, (160, 160, 160)))
            screen.blit(cat_s, (lp.left + 18, y))
            y += 22
        row = pygame.Rect(lp.left + 10, y, lp.width - 20, 48)
        recipe_rects[recipe["id"]] = row
        selected = recipe["id"] == selected_recipe_id
        can_craft = all(materials.get(mid, 0) >= cnt for mid, cnt in recipe["ingredients"].items())
        bg = (52, 48, 36) if selected else (32, 32, 38)
        border = (200, 170, 80) if selected else ((80, 160, 100) if can_craft else (70, 70, 80))
        pygame.draw.rect(screen, bg, row, border_radius=7)
        pygame.draw.rect(screen, border, row, 1, border_radius=7)
        name_s = node_font.render(recipe["name"], True, (230, 225, 210))
        desc_s = info_font.render(recipe["desc"], True, (160, 158, 148))
        screen.blit(name_s, (row.left + 10, row.top + 5))
        screen.blit(desc_s, (row.left + 10, row.top + 26))
        # Ingredient dots
        dot_x = row.right - 12
        for mid, cnt in reversed(list(recipe["ingredients"].items())):
            have = materials.get(mid, 0)
            dot_color = (80, 200, 100) if have >= cnt else (200, 70, 70)
            pygame.gfxdraw.filled_circle(screen, dot_x, row.centery, 6, dot_color)
            dot_x -= 16
        y += 54

    hint_s = info_font.render("[I] Close   [↑↓ / Click] Select   [Enter] Craft", True, (140, 138, 128))
    screen.blit(hint_s, (lp.centerx - hint_s.get_width() // 2, lp.bottom - 28))

    # Right panel — detail + materials
    rp = pygame.Rect(600, 60, SCREEN_WIDTH - 660, SCREEN_HEIGHT - 120)
    draw_ornate_panel(screen, rp)

    # Materials stock (top half of right panel)
    mat_title = node_font.render("Materials", True, (200, 190, 160))
    screen.blit(mat_title, (rp.left + 16, rp.top + 14))
    my = rp.top + 46
    for mid in MATERIAL_ORDER:
        mat = WOLF_MATERIALS[mid]
        count = materials.get(mid, 0)
        col = tuple(mat["color"])
        pygame.gfxdraw.filled_circle(screen, rp.left + 22, my + 10, 8, col + (255,))
        name_s = info_font.render(mat["name"], True, (210, 208, 200))
        count_s = node_font.render(str(count), True, (240, 220, 160) if count > 0 else (100, 100, 110))
        screen.blit(name_s, (rp.left + 38, my + 2))
        screen.blit(count_s, (rp.right - count_s.get_width() - 16, my + 2))
        my += 30
    pygame.draw.line(screen, (60, 60, 70), (rp.left + 12, my + 4), (rp.right - 12, my + 4))
    my += 14

    # Selected recipe detail (bottom half of right panel)
    sel_recipe = next((r for r in recipes if r["id"] == selected_recipe_id), None)
    if sel_recipe:
        rtitle = node_font.render(sel_recipe["name"], True, (234, 220, 160))
        screen.blit(rtitle, (rp.left + 16, my))
        my += 28
        rdesc = info_font.render(sel_recipe["desc"], True, (190, 185, 170))
        screen.blit(rdesc, (rp.left + 16, my))
        my += 26
        ing_title = info_font.render("Ingredients:", True, (160, 158, 148))
        screen.blit(ing_title, (rp.left + 16, my))
        my += 22
        for mid, cnt in sel_recipe["ingredients"].items():
            have = materials.get(mid, 0)
            mat_name = WOLF_MATERIALS[mid]["name"]
            col = (80, 200, 100) if have >= cnt else (200, 70, 70)
            ing_s = info_font.render(f"  {mat_name}  {have}/{cnt}", True, col)
            screen.blit(ing_s, (rp.left + 16, my))
            my += 22
        my += 8
        can_craft = all(materials.get(mid, 0) >= cnt for mid, cnt in sel_recipe["ingredients"].items())
        inv_full = all(s is not None for s in item_inventory) and len(backpack_inventory) >= BACKPACK_SLOT_COUNT
        has_instant = sel_recipe["result"]["effect"] in ("max_hp_15", "mana_regen_05", "skill_point")
        if can_craft:
            if inv_full and not has_instant:
                craft_hint = info_font.render("Inventory full! (max 8 items)", True, (220, 100, 80))
            else:
                craft_hint = info_font.render("[Enter]  Craft now", True, (100, 220, 130))
        else:
            craft_hint = info_font.render("Missing ingredients", True, (180, 80, 80))
        screen.blit(craft_hint, (rp.left + 16, my))
    else:
        hint = info_font.render("Select a recipe to see details", True, (130, 128, 120))
        screen.blit(hint, (rp.centerx - hint.get_width() // 2, rp.centery))

    return recipe_rects


def draw_profession_screen(
    screen: pygame.Surface,
    materials: Dict[str, int],
    profession_state: Dict[str, Dict[str, float]],
    selected_profession: str,
    recipes: List[Dict[str, object]],
    selected_recipe_id: Optional[str],
    title_font: pygame.font.Font,
    node_font: pygame.font.Font,
    info_font: pygame.font.Font,
    tiny_font: pygame.font.Font,
) -> Tuple[Dict[str, pygame.Rect], Dict[str, pygame.Rect], pygame.Rect]:
    overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 190))
    screen.blit(overlay, (0, 0))

    panel = pygame.Rect(54, 42, SCREEN_WIDTH - 108, SCREEN_HEIGHT - 84)
    draw_ornate_panel(screen, panel)
    title_s = title_font.render("Professions", True, (236, 220, 180))
    subtitle_s = info_font.render("Craft from dropped wilderness materials and raise profession skill.", True, (166, 160, 146))
    close_s = tiny_font.render("[O] Close", True, (138, 138, 150))
    screen.blit(title_s, (panel.left + 18, panel.top + 12))
    screen.blit(subtitle_s, (panel.left + 20, panel.top + 52))
    screen.blit(close_s, (panel.right - close_s.get_width() - 18, panel.top + 16))

    tab_rects: Dict[str, pygame.Rect] = {}
    tab_x = panel.left + 20
    tab_y = panel.top + 82
    tab_w = 228
    for prof_id in PROFESSION_ORDER:
        data = PROFESSION_DEFINITIONS.get(prof_id, {})
        state = profession_state.get(prof_id, {})
        skill = int(state.get("skill", 1))
        rank = profession_rank_name(skill)
        prof_name = str(data.get("name", prof_id.title()))
        col = data.get("color", (120, 120, 130))
        if not (isinstance(col, tuple) and len(col) >= 3):
            col = (120, 120, 130)
        tr = pygame.Rect(tab_x, tab_y, tab_w, 56)
        tab_rects[prof_id] = tr
        active = prof_id == selected_profession
        draw_ui_tab(screen, tr, active=active)
        p_name = node_font.render(prof_name, True, (230, 225, 210))
        p_meta = tiny_font.render(f"{rank}  Skill {skill}/{PROFESSION_MAX_SKILL}", True, (180, 176, 164))
        screen.blit(p_name, (tr.left + 10, tr.top + 6))
        screen.blit(p_meta, (tr.left + 10, tr.top + 30))
        tab_x += tab_w + 10

    selected_data = PROFESSION_DEFINITIONS.get(selected_profession, {})
    selected_state = profession_state.get(selected_profession, {"skill": 1, "xp": 0.0, "crafted": 0})
    selected_skill = max(1, int(selected_state.get("skill", 1)))
    selected_xp = max(0.0, float(selected_state.get("xp", 0.0)))
    next_xp = float(profession_xp_to_next(selected_skill))
    crafted_total = int(selected_state.get("crafted", 0))
    selected_name = str(selected_data.get("name", selected_profession.title()))
    selected_rank = profession_rank_name(selected_skill)
    selected_desc = str(selected_data.get("desc", ""))

    list_panel = pygame.Rect(panel.left + 18, panel.top + 150, 560, panel.height - 172)
    detail_panel = pygame.Rect(list_panel.right + 14, list_panel.top, panel.right - list_panel.right - 32, list_panel.height)
    pygame.draw.rect(screen, (22, 22, 28), list_panel, border_radius=10)
    pygame.draw.rect(screen, (70, 70, 82), list_panel, 1, border_radius=10)
    pygame.draw.rect(screen, (20, 20, 26), detail_panel, border_radius=10)
    pygame.draw.rect(screen, (78, 78, 90), detail_panel, 1, border_radius=10)

    prof_title = node_font.render(f"{selected_name} Recipes", True, (230, 220, 190))
    prof_desc = info_font.render(selected_desc, True, (168, 162, 148))
    screen.blit(prof_title, (list_panel.left + 12, list_panel.top + 10))
    screen.blit(prof_desc, (list_panel.left + 12, list_panel.top + 36))

    bar = pygame.Rect(list_panel.left + 12, list_panel.top + 64, list_panel.width - 24, 16)
    pygame.draw.rect(screen, (26, 26, 34), bar, border_radius=5)
    fill_w = int((bar.width - 2) * clamp(selected_xp / max(1.0, next_xp), 0.0, 1.0))
    if fill_w > 0:
        pygame.draw.rect(screen, (120, 170, 220), pygame.Rect(bar.left + 1, bar.top + 1, fill_w, bar.height - 2), border_radius=4)
    pygame.draw.rect(screen, (118, 110, 90), bar, 1, border_radius=5)
    xp_s = tiny_font.render(
        f"{selected_rank}  Skill {selected_skill}/{PROFESSION_MAX_SKILL}  XP {int(selected_xp)}/{int(next_xp)}  Crafted {crafted_total}",
        True,
        (202, 196, 176),
    )
    screen.blit(xp_s, (bar.left + 8, bar.top - 18))

    recipe_rects: Dict[str, pygame.Rect] = {}
    prof_recipes = [r for r in recipes if str(r.get("profession", "alchemy")) == selected_profession]
    prof_recipes.sort(key=lambda r: (int(r.get("required_skill", 1)), str(r.get("name", ""))))
    row_y = list_panel.top + 90
    max_rows = max(1, (list_panel.height - 108) // 52)
    for recipe in prof_recipes[:max_rows]:
        rid = str(recipe.get("id", ""))
        req = max(1, int(recipe.get("required_skill", 1)))
        unlocked = selected_skill >= req
        can_afford = all(materials.get(str(mid), 0) >= int(cnt) for mid, cnt in dict(recipe.get("ingredients", {})).items())
        selected = rid == selected_recipe_id
        row = pygame.Rect(list_panel.left + 10, row_y, list_panel.width - 20, 46)
        recipe_rects[rid] = row
        if not unlocked:
            bg = (36, 24, 26)
            border = (128, 74, 74)
            txt_col = (202, 132, 132)
        elif selected:
            bg = (52, 48, 36)
            border = (200, 170, 84)
            txt_col = (236, 224, 192)
        elif can_afford:
            bg = (34, 40, 32)
            border = (98, 156, 94)
            txt_col = (220, 220, 206)
        else:
            bg = (30, 30, 36)
            border = (80, 80, 92)
            txt_col = (194, 190, 178)
        pygame.draw.rect(screen, bg, row, border_radius=7)
        pygame.draw.rect(screen, border, row, 1, border_radius=7)
        name_s = node_font.render(str(recipe.get("name", "Recipe")), True, txt_col)
        meta_s = tiny_font.render(
            f"Req {req}  XP +{int(recipe.get('xp', 0))}  {'READY' if unlocked and can_afford else ('LOCKED' if not unlocked else 'MISSING MATS')}",
            True,
            (190, 186, 170),
        )
        screen.blit(name_s, (row.left + 10, row.top + 4))
        screen.blit(meta_s, (row.left + 10, row.top + 26))
        row_y += 52

    selected_recipe = None
    if selected_recipe_id:
        selected_recipe = next((r for r in recipes if str(r.get("id", "")) == selected_recipe_id), None)
    if selected_recipe is None and prof_recipes:
        selected_recipe = prof_recipes[0]

    craft_button_rect = pygame.Rect(detail_panel.right - 166, detail_panel.bottom - 40, 150, 28)
    if selected_recipe is not None:
        r_name = node_font.render(str(selected_recipe.get("name", "Recipe")), True, (234, 220, 180))
        r_desc = info_font.render(str(selected_recipe.get("desc", "")), True, (188, 184, 172))
        screen.blit(r_name, (detail_panel.left + 14, detail_panel.top + 12))
        screen.blit(r_desc, (detail_panel.left + 14, detail_panel.top + 40))
        req_skill = max(1, int(selected_recipe.get("required_skill", 1)))
        req_s = info_font.render(
            f"Requires {selected_name} skill {req_skill} ({selected_rank} {selected_skill})",
            True,
            (214, 146, 146) if selected_skill < req_skill else (154, 206, 154),
        )
        screen.blit(req_s, (detail_panel.left + 14, detail_panel.top + 70))
        xp_gain = int(selected_recipe.get("xp", 0))
        xp_hint = info_font.render(f"Craft XP: +{xp_gain}", True, (174, 168, 150))
        screen.blit(xp_hint, (detail_panel.left + 14, detail_panel.top + 96))

        ingredients = dict(selected_recipe.get("ingredients", {}))
        iy = detail_panel.top + 132
        ing_t = node_font.render("Ingredients", True, (220, 214, 192))
        screen.blit(ing_t, (detail_panel.left + 14, iy))
        iy += 30
        for mid, cnt_raw in ingredients.items():
            cnt = int(cnt_raw)
            have = int(materials.get(str(mid), 0))
            mat_data = WOLF_MATERIALS.get(str(mid), {})
            mat_name = str(mat_data.get("name", str(mid).replace("_", " ").title()))
            col = (110, 220, 110) if have >= cnt else (220, 110, 110)
            line = info_font.render(f"{mat_name}: {have}/{cnt}", True, col)
            screen.blit(line, (detail_panel.left + 18, iy))
            iy += 24

        craftable = selected_skill >= req_skill and all(materials.get(str(mid), 0) >= int(cnt) for mid, cnt in ingredients.items())
        draw_ui_button(screen, craft_button_rect, hovered=craft_button_rect.collidepoint(pygame.mouse.get_pos()), text="[ENTER] Craft", font=tiny_font, color=(238, 226, 188) if craftable else (140, 140, 150))
    else:
        none_s = info_font.render("No recipes available for this profession yet.", True, (136, 136, 148))
        screen.blit(none_s, (detail_panel.left + 14, detail_panel.top + 14))

    help_s = tiny_font.render("Click profession tabs or recipes. Crafting consumes dropped materials.", True, (132, 132, 144))
    screen.blit(help_s, (panel.left + 18, panel.bottom - 22))

    return recipe_rects, tab_rects, craft_button_rect


_PARCHMENT_CACHE: Dict[Tuple[int,int], pygame.Surface] = {}

def _make_parchment(w: int, h: int) -> pygame.Surface:
    """WoW-style bright parchment with warm tan base and burnt edges."""
    key = (w, h)
    if key in _PARCHMENT_CACHE:
        return _PARCHMENT_CACHE[key]
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    # Bright warm parchment base
    for y in range(h):
        t = y / max(h - 1, 1)
        r = int(205 + 20 * math.sin(t * 2.4) - 8 * t)
        g = int(185 + 15 * math.sin(t * 2.1) - 10 * t)
        b = int(140 + 10 * math.sin(t * 1.8) - 12 * t)
        pygame.draw.line(surf, (r, g, b), (0, y), (w - 1, y))
    # Subtle fibre / paper texture noise
    rng = random.Random(77)
    for _ in range(w * h // 120):
        sx = rng.randint(0, w - 1)
        sy = rng.randint(0, h - 1)
        sr = rng.randint(1, 3)
        shade = rng.randint(170, 210)
        a = rng.randint(20, 50)
        spot = pygame.Surface((sr * 2, sr * 2), pygame.SRCALPHA)
        pygame.draw.circle(spot, (shade, shade - 20, shade - 50, a), (sr, sr), sr)
        surf.blit(spot, (sx - sr, sy - sr))
    # Burnt / darkened edges
    edge_surf = pygame.Surface((w, h), pygame.SRCALPHA)
    edge_w = 22
    for i in range(edge_w):
        a = int(80 * (1.0 - i / edge_w) ** 1.5)
        pygame.draw.rect(edge_surf, (60, 40, 20, a), (i, i, w - 2 * i, h - 2 * i), 1)
    surf.blit(edge_surf, (0, 0))
    _PARCHMENT_CACHE[key] = surf
    return surf


def _draw_parchment_divider(surface: pygame.Surface, x: int, y: int, width: int) -> None:
    """Ornamental line with diamond center."""
    mid = x + width // 2
    col = (130, 95, 50)
    pygame.draw.line(surface, col, (x + 12, y), (mid - 14, y), 1)
    pygame.draw.line(surface, col, (mid + 14, y), (x + width - 12, y), 1)
    pts = [(mid, y - 4), (mid + 4, y), (mid, y + 4), (mid - 4, y)]
    pygame.draw.polygon(surface, (160, 120, 60), pts)
    pygame.draw.polygon(surface, col, pts, 1)
    for dx in (-10, 10):
        pygame.draw.circle(surface, col, (mid + dx, y), 2)


def _draw_wax_seal(surface: pygame.Surface, cx: int, cy: int, radius: int, color: Tuple[int,int,int]) -> None:
    """Decorative wax seal."""
    for i in range(10):
        angle = i * (2 * math.pi / 10)
        bx = int(cx + (radius + 2) * math.cos(angle))
        by = int(cy + (radius + 2) * math.sin(angle))
        pygame.draw.circle(surface, color, (bx, by), 3)
    pygame.draw.circle(surface, color, (cx, cy), radius)
    darker = (max(0, color[0] - 35), max(0, color[1] - 25), max(0, color[2] - 15))
    pygame.draw.circle(surface, darker, (cx, cy), radius - 3, 1)


def draw_quest_log(
    screen: pygame.Surface,
    quest_states: Dict[str, str],
    quest_progress: Dict[str, List[int]],
    quest_defs: List[Dict],
    _wolves_slain: int,
    _materials: Dict[str, int],
    selected_quest_id: Optional[str],
    allow_vendor_actions: bool,
    vendor_role_filter: Optional[str],
    title_font: pygame.font.Font,
    node_font: pygame.font.Font,
    info_font: pygame.font.Font,
    tiny_font: pygame.font.Font,
) -> Dict[str, pygame.Rect]:
    """Quest log on a parchment scroll with ornate framing, section cartouches,
    wax-seal quest bullets and right-aligned counters."""

    # --- Color palette: dark ink on bright parchment ---
    INK       = (35, 20, 5)        # near-black brown for titles
    INK_BODY  = (55, 35, 10)       # dark brown for body text
    INK_DIM   = (100, 75, 40)      # faded brown for secondary
    GOLD      = (180, 145, 45)     # gold accents / selected
    GOLD_DIM  = (140, 110, 40)     # dimmer gold
    RED_SEAL  = (160, 45, 30)      # wax seal / turn-in badge
    GREEN_OK  = (30, 120, 30)      # completed objective
    GREEN_BAR = (50, 140, 50)      # progress bar fill
    BAR_BG    = (160, 140, 105)    # progress bar background track
    FRAME     = (60, 40, 18)       # dark wood frame
    FRAME_GLD = (150, 115, 50)     # gold liner
    CARD_SHD  = (120, 90, 45)      # cartouche shadow

    # --- Dim overlay behind the scroll ---
    overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 170))
    screen.blit(overlay, (0, 0))

    # --- Compact centered panel (not fullscreen) ---
    pw, ph = 860, 600
    px = (SCREEN_WIDTH - pw) // 2
    py = (SCREEN_HEIGHT - ph) // 2
    panel = pygame.Rect(px, py, pw, ph)

    # Parchment background
    parchment = _make_parchment(pw, ph)
    screen.blit(parchment, panel.topleft)

    # Double ornate border: thick dark outer, thin gold inner, second liner
    pygame.draw.rect(screen, FRAME,     panel,                    3, border_radius=5)
    pygame.draw.rect(screen, FRAME_GLD, panel.inflate(-6, -6),    1, border_radius=4)
    pygame.draw.rect(screen, FRAME_GLD, panel.inflate(-14, -14),  1, border_radius=3)

    # --- Decorative corner flourishes (hand-drawn feel) ---
    def _corner(cx: int, cy: int, sx: int, sy: int) -> None:
        # L-shaped gold flourish anchored at (cx,cy) opening toward (sx,sy)
        pygame.draw.line(screen, GOLD,     (cx, cy), (cx + sx * 18, cy),           2)
        pygame.draw.line(screen, GOLD,     (cx, cy), (cx,           cy + sy * 18), 2)
        pygame.draw.line(screen, FRAME,    (cx + sx * 4, cy + sy * 4),
                                           (cx + sx * 14, cy + sy * 4),            1)
        pygame.draw.line(screen, FRAME,    (cx + sx * 4, cy + sy * 4),
                                           (cx + sx * 4,  cy + sy * 14),           1)
        pygame.draw.circle(screen, GOLD,   (cx + sx * 4, cy + sy * 4), 2)
    _corner(panel.left  + 10, panel.top    + 10,  1,  1)
    _corner(panel.right - 10, panel.top    + 10, -1,  1)
    _corner(panel.left  + 10, panel.bottom - 10,  1, -1)
    _corner(panel.right - 10, panel.bottom - 10, -1, -1)

    # --- Header ribbon: centered title with side flourishes ---
    header_y  = panel.top + 18
    title_s   = title_font.render("Quest Log", True, INK)
    title_sh  = title_font.render("Quest Log", True, (200, 170, 110))
    title_x   = panel.centerx - title_s.get_width() // 2
    # Soft gold glow behind title
    glow = pygame.Surface((title_s.get_width() + 40, title_s.get_height() + 14), pygame.SRCALPHA)
    pygame.draw.ellipse(glow, (210, 170, 80, 55), glow.get_rect())
    screen.blit(glow, (title_x - 20, header_y - 4))
    screen.blit(title_sh, (title_x + 1, header_y + 1))
    screen.blit(title_s,  (title_x,     header_y))
    # Side flourishes (fleur-de-lis-ish little diamonds + lines)
    _fl_y   = header_y + title_s.get_height() // 2
    _fl_lx  = title_x - 30
    _fl_rx  = title_x + title_s.get_width() + 30
    for _fx, _dir in ((_fl_lx, -1), (_fl_rx, 1)):
        pygame.draw.line(screen, FRAME_GLD, (_fx, _fl_y), (_fx + _dir * 80, _fl_y), 1)
        pygame.draw.polygon(screen, GOLD,
                            [(_fx, _fl_y - 4), (_fx + _dir * 6, _fl_y),
                             (_fx, _fl_y + 4), (_fx - _dir * 6, _fl_y)])
        pygame.draw.polygon(screen, FRAME,
                            [(_fx, _fl_y - 4), (_fx + _dir * 6, _fl_y),
                             (_fx, _fl_y + 4), (_fx - _dir * 6, _fl_y)], 1)

    divider_y = header_y + title_s.get_height() + 10
    _draw_parchment_divider(screen, panel.left + 30, divider_y, pw - 60)

    content_top = divider_y + 14
    content_bot = panel.bottom - 50

    # ============ LEFT: quest list (cartouche) ============
    list_x = panel.left + 24
    list_w = 300
    list_rect = pygame.Rect(list_x - 6, content_top - 8, list_w + 12, content_bot - content_top + 16)

    # Inset parchment cartouche — softer "inked page" feel instead of a hard rect
    card_shadow = pygame.Surface((list_rect.width, list_rect.height), pygame.SRCALPHA)
    card_shadow.fill((120, 90, 45, 32))
    screen.blit(card_shadow, list_rect.topleft)
    # Hand-inked border: 4 slightly-irregular strokes (no rect, no radius)
    _ink = (70, 45, 18)
    for _ox, _oy in ((0, 0), (1, 0), (0, 1)):
        pygame.draw.line(screen, _ink, (list_rect.left + 2 + _ox, list_rect.top + _oy),      (list_rect.right - 2 + _ox, list_rect.top + _oy),      1)
        pygame.draw.line(screen, _ink, (list_rect.left + 2 + _ox, list_rect.bottom - 1 + _oy),(list_rect.right - 2 + _ox, list_rect.bottom - 1 + _oy),1)
    pygame.draw.line(screen, _ink, (list_rect.left + 1,  list_rect.top + 2), (list_rect.left + 1,  list_rect.bottom - 2), 1)
    pygame.draw.line(screen, _ink, (list_rect.right - 1, list_rect.top + 2), (list_rect.right - 1, list_rect.bottom - 2), 1)
    # Tiny ink-dot ornaments at each corner
    for _cx, _cy in ((list_rect.left + 3, list_rect.top + 3), (list_rect.right - 4, list_rect.top + 3),
                     (list_rect.left + 3, list_rect.bottom - 4), (list_rect.right - 4, list_rect.bottom - 4)):
        pygame.draw.circle(screen, _ink, (_cx, _cy), 2)

    # "Journal" label — centered, with flanking ink dashes for calligraphic feel
    _lbl = tiny_font.render("~ Journal ~", True, INK_BODY)
    _lbl_x = list_rect.centerx - _lbl.get_width() // 2
    _lbl_y = list_rect.top - _lbl.get_height() - 2
    screen.blit(_lbl, (_lbl_x, _lbl_y))

    quest_rects: Dict[str, pygame.Rect] = {}
    qy = content_top + 4

    role_filter = str(vendor_role_filter).strip().lower() if vendor_role_filter else ""
    visible = [
        q for q in quest_defs
        if quest_states.get(q["id"], "hidden") not in ("hidden", "turned_in")
        and (not role_filter or _quest_role_for_def(q) == role_filter)
    ]
    ROW_H = 44
    for qdef in visible:
        if qy + ROW_H > content_bot:
            break
        st = quest_states.get(qdef["id"], "hidden")
        row = pygame.Rect(list_x, qy, list_w, ROW_H - 4)
        quest_rects[qdef["id"]] = row
        is_sel = qdef["id"] == selected_quest_id

        # Selection highlight: soft gold wash + gold border
        if is_sel:
            hl = pygame.Surface((row.width, row.height), pygame.SRCALPHA)
            hl.fill((200, 160, 75, 70))
            screen.blit(hl, row.topleft)
            pygame.draw.rect(screen, GOLD, row, 2, border_radius=3)
            # Small pointer triangle on the right indicating "open"
            pygame.draw.polygon(screen, GOLD,
                                [(row.right + 2, row.centery - 5),
                                 (row.right + 8, row.centery),
                                 (row.right + 2, row.centery + 5)])

        # Wax-seal bullet (state-colored)
        seal_x = row.left + 16
        seal_y = row.centery
        if st == "complete":
            _draw_wax_seal(screen, seal_x, seal_y, 8, RED_SEAL)
            pygame.draw.line(screen, (240, 220, 150), (seal_x - 3, seal_y - 2), (seal_x + 3, seal_y + 2), 1)
        elif st == "turned_in":
            _draw_wax_seal(screen, seal_x, seal_y, 7, (60, 100, 55))
        elif st == "active":
            _draw_wax_seal(screen, seal_x, seal_y, 7, GOLD_DIM)
        else:  # available
            pygame.draw.circle(screen, INK_DIM, (seal_x, seal_y), 6, 1)
            pygame.draw.circle(screen, INK_DIM, (seal_x, seal_y), 2)

        # Title text — left-aligned, vertically centered
        t_col = INK if is_sel else INK_BODY
        if st == "turned_in":
            t_col = INK_DIM
        title_text = qdef["title"]
        q_ts = info_font.render(title_text, True, t_col)
        # Clip overly long titles with ellipsis
        _max_text_w = row.width - 64
        if q_ts.get_width() > _max_text_w:
            while title_text and info_font.size(title_text + "…")[0] > _max_text_w:
                title_text = title_text[:-1]
            q_ts = info_font.render(title_text + "…", True, t_col)
        screen.blit(q_ts, (row.left + 30, row.centery - q_ts.get_height() // 2))

        # "NEW" / "!" right-aligned badge for complete quests
        if st == "complete":
            badge_txt = tiny_font.render("TURN IN", True, (250, 240, 200))
            badge_w = badge_txt.get_width() + 10
            badge_h = badge_txt.get_height() + 4
            badge_rect = pygame.Rect(row.right - badge_w - 6,
                                     row.centery - badge_h // 2,
                                     badge_w, badge_h)
            pygame.draw.rect(screen, RED_SEAL, badge_rect, border_radius=3)
            pygame.draw.rect(screen, (90, 20, 10), badge_rect, 1, border_radius=3)
            screen.blit(badge_txt,
                        (badge_rect.centerx - badge_txt.get_width() // 2,
                         badge_rect.centery - badge_txt.get_height() // 2))

        # Hairline separator below each row (not under selected)
        if not is_sel:
            sep_x1 = row.left + 14
            sep_x2 = row.right - 14
            pygame.draw.line(screen, (170, 150, 110), (sep_x1, row.bottom + 1), (sep_x2, row.bottom + 1), 1)
            # Tiny center ornament on the separator
            pygame.draw.circle(screen, (150, 120, 65), ((sep_x1 + sep_x2) // 2, row.bottom + 1), 1)

        qy += ROW_H

    if not visible:
        empty = info_font.render("No quests in your journal.", True, INK_DIM)
        screen.blit(empty, (list_rect.centerx - empty.get_width() // 2,
                            content_top + (content_bot - content_top) // 2 - empty.get_height() // 2))

    # ============ DIVIDER between list and detail (ink vine) ============
    div_x = list_rect.right + 14
    _div_top = content_top - 4
    _div_bot = content_bot + 4
    # Wavering ink stroke rather than a straight rule
    _prev = (div_x, _div_top)
    for _i in range(1, 24):
        _t = _i / 23.0
        _jx = div_x + int(math.sin(_t * math.pi * 3.2) * 2)
        _jy = int(_div_top + _t * (_div_bot - _div_top))
        pygame.draw.line(screen, (110, 80, 35), _prev, (_jx, _jy), 1)
        _prev = (_jx, _jy)
    # Ornate mid flourish: leaf-and-dot motif
    _dv_mid = (content_top + content_bot) // 2
    pygame.draw.polygon(screen, GOLD,
                        [(div_x, _dv_mid - 6), (div_x + 5, _dv_mid),
                         (div_x, _dv_mid + 6), (div_x - 5, _dv_mid)])
    pygame.draw.polygon(screen, FRAME,
                        [(div_x, _dv_mid - 6), (div_x + 5, _dv_mid),
                         (div_x, _dv_mid + 6), (div_x - 5, _dv_mid)], 1)
    pygame.draw.circle(screen, FRAME, (div_x, _dv_mid - 14), 2)
    pygame.draw.circle(screen, FRAME, (div_x, _dv_mid + 14), 2)

    # ============ RIGHT: detail ============
    det_x = div_x + 18
    det_w = panel.right - det_x - 24

    # Helper: section header drawn like a hand-inked chapter title —
    # small quill ornament, italic-feel label, and a flourished tail.
    def _section_header(label: str, y: int) -> int:
        # Opening ornament: small diamond + short stroke
        pygame.draw.polygon(screen, FRAME,
                            [(det_x, y + 10), (det_x + 4, y + 7),
                             (det_x + 8, y + 10), (det_x + 4, y + 13)])
        pygame.draw.line(screen, FRAME, (det_x + 9, y + 10), (det_x + 14, y + 10), 1)
        hdr = node_font.render(label, True, INK)
        screen.blit(hdr, (det_x + 17, y))
        # Trailing flourish: wavering ink line that fades into a teardrop
        _tx = det_x + 17 + hdr.get_width() + 6
        _ty = y + hdr.get_height() // 2 + 1
        _end = det_x + det_w - 6
        _prev = (_tx, _ty)
        for _i in range(1, 12):
            _t = _i / 11.0
            _jx = int(_tx + _t * (_end - _tx))
            _jy = int(_ty + math.sin(_t * math.pi * 2.0) * 1.5)
            pygame.draw.line(screen, (120, 85, 35), _prev, (_jx, _jy), 1)
            _prev = (_jx, _jy)
        pygame.draw.circle(screen, FRAME, (_end, _ty), 2)
        return y + hdr.get_height() + 8

    if role_filter:
        sel_q = next((q for q in quest_defs if q["id"] == selected_quest_id and _quest_role_for_def(q) == role_filter), None)
    else:
        sel_q = next((q for q in quest_defs if q["id"] == selected_quest_id), None)

    if sel_q:
        st = quest_states.get(sel_q["id"], "hidden")
        dy = content_top

        # --- Title + status pill on the same row ---
        qt = node_font.render(sel_q["title"], True, INK)
        screen.blit(qt, (det_x, dy))

        stag = {"available": "AVAILABLE", "active": "IN PROGRESS",
                "complete": "COMPLETE",  "turned_in": "TURNED IN"}.get(st, "")
        stag_col = {"available": INK_DIM, "active": GOLD,
                    "complete":  RED_SEAL, "turned_in": GREEN_OK}.get(st, INK_DIM)
        if stag:
            # Wax-stamp style: ribbon with torn tail, inked outline, centered text
            pill_txt = tiny_font.render(stag, True, (250, 240, 210))
            pill_w = pill_txt.get_width() + 22
            pill_h = pill_txt.get_height() + 8
            pill_rect = pygame.Rect(det_x + det_w - pill_w,
                                    dy + qt.get_height() // 2 - pill_h // 2,
                                    pill_w, pill_h)
            # Shadow
            _shd = pygame.Surface((pill_w + 4, pill_h + 4), pygame.SRCALPHA)
            _shd.fill((0, 0, 0, 55))
            screen.blit(_shd, (pill_rect.left - 1, pill_rect.top + 2))
            # Body with subtle vertical gradient
            for _i in range(pill_h):
                _f = _i / max(1, pill_h - 1)
                _shade = (max(0, int(stag_col[0] * (1.0 - _f * 0.25))),
                          max(0, int(stag_col[1] * (1.0 - _f * 0.25))),
                          max(0, int(stag_col[2] * (1.0 - _f * 0.25))))
                pygame.draw.line(screen, _shade,
                                 (pill_rect.left + 2, pill_rect.top + _i),
                                 (pill_rect.right - 2, pill_rect.top + _i))
            # Torn-ribbon notches on left/right
            pygame.draw.polygon(screen, stag_col,
                                [(pill_rect.left, pill_rect.top),
                                 (pill_rect.left + 4, pill_rect.centery),
                                 (pill_rect.left, pill_rect.bottom)])
            pygame.draw.polygon(screen, stag_col,
                                [(pill_rect.right, pill_rect.top),
                                 (pill_rect.right - 4, pill_rect.centery),
                                 (pill_rect.right, pill_rect.bottom)])
            # Inked outline
            pygame.draw.rect(screen, (30, 20, 5), pill_rect, 1)
            pygame.draw.line(screen, (255, 230, 180, 100),
                             (pill_rect.left + 3, pill_rect.top + 1),
                             (pill_rect.right - 3, pill_rect.top + 1), 1)
            screen.blit(pill_txt,
                        (pill_rect.centerx - pill_txt.get_width() // 2,
                         pill_rect.centery - pill_txt.get_height() // 2))
        dy += qt.get_height() + 8

        # Thin divider under title
        pygame.draw.line(screen, (150, 120, 65), (det_x, dy), (det_x + det_w, dy), 1)
        dy += 10

        # --- STORY ---
        dy = _section_header("Story", dy)
        desc_words = sel_q["desc"].split()
        wrap_w = det_w - 8
        line, lines = "", []
        for wd in desc_words:
            test = (line + " " + wd).strip()
            if info_font.size(test)[0] > wrap_w:
                if line:
                    lines.append(line)
                line = wd
            else:
                line = test
        if line:
            lines.append(line)
        for ln in lines:
            ds = info_font.render(ln, True, INK_BODY)
            screen.blit(ds, (det_x + 4, dy))
            dy += ds.get_height() + 1
        dy += 10

        # --- OBJECTIVES ---
        dy = _section_header("Objectives", dy)
        prog_list = quest_progress.get(sel_q["id"], [0] * len(sel_q["objectives"]))
        for i, obj in enumerate(sel_q["objectives"]):
            cur = min(prog_list[i] if i < len(prog_list) else 0, obj["count"])
            tgt = obj["count"]
            done = cur >= tgt
            lbl = obj["label"].split("(")[0].strip()
            lbl_col = GREEN_OK if done else INK_BODY

            # Hand-drawn checkbox: irregular ink square + sloppy check when done
            box_x = det_x + 6
            box_y = dy + 4
            # Two slightly offset strokes give a quill-on-parchment look
            pygame.draw.line(screen, INK_BODY, (box_x, box_y),       (box_x + 11, box_y),       1)
            pygame.draw.line(screen, INK_BODY, (box_x, box_y + 1),   (box_x + 11, box_y + 1),   1)
            pygame.draw.line(screen, INK_BODY, (box_x, box_y + 11),  (box_x + 11, box_y + 11),  1)
            pygame.draw.line(screen, INK_BODY, (box_x, box_y),       (box_x, box_y + 11),       1)
            pygame.draw.line(screen, INK_BODY, (box_x + 11, box_y),  (box_x + 11, box_y + 11),  1)
            if done:
                # Inked check that overshoots the box slightly
                pygame.draw.line(screen, GREEN_OK, (box_x + 1, box_y + 6),  (box_x + 5, box_y + 10), 2)
                pygame.draw.line(screen, GREEN_OK, (box_x + 5, box_y + 10), (box_x + 13, box_y - 2), 2)

            # Label (left) + counter (right-aligned, italicized feel via dim color)
            obj_s = info_font.render(lbl, True, lbl_col)
            screen.blit(obj_s, (box_x + 18, dy))
            cnt_s = info_font.render(f"{cur} / {tgt}", True, INK_DIM if not done else GREEN_OK)
            screen.blit(cnt_s, (det_x + det_w - cnt_s.get_width() - 4, dy))

            # Inked progress rail: dotted track with a solid hand-inked fill
            bar_y2 = dy + obj_s.get_height() + 3
            bar_x2 = box_x + 18
            bar_w2 = det_w - (bar_x2 - det_x) - 6
            bar_h2 = 3
            # Dotted track (parchment dots)
            for _dx in range(0, bar_w2, 4):
                pygame.draw.circle(screen, (155, 130, 85), (bar_x2 + _dx, bar_y2 + 1), 1)
            fill2 = int(bar_w2 * min(cur / max(tgt, 1), 1.0))
            if fill2 > 0:
                # Solid inked rail underneath the dots
                pygame.draw.rect(screen, GREEN_OK if done else GREEN_BAR,
                                 (bar_x2, bar_y2, fill2, bar_h2))
                # Slim highlight for parchment ink-pop
                pygame.draw.line(screen, (240, 255, 220),
                                 (bar_x2, bar_y2),
                                 (bar_x2 + fill2 - 1, bar_y2), 1)
            dy += obj_s.get_height() + bar_h2 + 9

        dy += 6

        # --- REWARDS (framed cartouche) ---
        dy = _section_header("Rewards", dy)
        rew = sel_q["rewards"]
        rew_items: List[Tuple[str, Tuple[int, int, int]]] = []
        if rew.get("gold"):
            rew_items.append((f"{rew['gold']} Gold", (210, 170, 60)))
        if rew.get("sp"):
            rew_items.append((f"+{rew['sp']} Skill Point{'s' if rew['sp'] != 1 else ''}", (180, 140, 220)))
        if rew.get("item"):
            rew_items.append((str(rew["item"]["name"]), (190, 220, 150)))

        # Reward "coin pouches": soft rounded tan tags with a leading sigil
        # (coin / star / scroll) that hint at the type of reward.
        rw_y = dy
        rw_x = det_x + 4
        for (txt, col) in rew_items:
            _rs = info_font.render(txt, True, INK_BODY)
            sigil_w = 18
            box_w = _rs.get_width() + sigil_w + 20
            box_h = _rs.get_height() + 10
            if rw_x + box_w > det_x + det_w:
                rw_x = det_x + 4
                rw_y += box_h + 6
            box_rect = pygame.Rect(rw_x, rw_y, box_w, box_h)
            # Drop shadow
            _sh = pygame.Surface((box_w + 2, box_h + 2), pygame.SRCALPHA)
            _sh.fill((60, 40, 15, 70))
            screen.blit(_sh, (box_rect.left + 1, box_rect.top + 2))
            # Soft tan body (two-tone gradient)
            for _i in range(box_h):
                _f = _i / max(1, box_h - 1)
                _shade = (int(238 - _f * 22), int(216 - _f * 24), int(160 - _f * 28))
                pygame.draw.line(screen, _shade,
                                 (box_rect.left + 3, box_rect.top + _i),
                                 (box_rect.right - 3, box_rect.top + _i))
            # Rounded inked outline
            pygame.draw.rect(screen, FRAME, box_rect, 1, border_radius=6)
            pygame.draw.line(screen, (255, 240, 200, 120),
                             (box_rect.left + 4, box_rect.top + 1),
                             (box_rect.right - 4, box_rect.top + 1), 1)
            # Sigil dot in the accent color of the reward
            _scx = box_rect.left + sigil_w // 2 + 4
            _scy = box_rect.centery
            pygame.draw.circle(screen, col, (_scx, _scy), 5)
            pygame.draw.circle(screen, FRAME, (_scx, _scy), 5, 1)
            pygame.draw.circle(screen, (255, 250, 220), (_scx - 1, _scy - 1), 1)
            screen.blit(_rs, (_scx + 9,
                              box_rect.centery - _rs.get_height() // 2))
            rw_x += box_w + 8
        dy = rw_y + (info_font.get_height() + 14)

        # Action
        if st == "available":
            if allow_vendor_actions:
                act = node_font.render("[A] Accept Quest", True, GREEN_OK)
            else:
                act = info_font.render("Accept at a town NPC.", True, INK_DIM)
            screen.blit(act, (det_x, dy))
        elif st == "complete":
            # Fancy "Complete Quest" button with glow VFX — right after rewards
            btn_w, btn_h = 220, 38
            btn_x = det_x + (det_w - btn_w) // 2
            btn_y = dy + 4
            btn_rect = pygame.Rect(btn_x, btn_y, btn_w, btn_h)
            quest_rects["__complete_btn__"] = btn_rect

            # Animated pulse glow behind the button
            _pulse = 0.5 + 0.5 * math.sin(pygame.time.get_ticks() * 0.004)
            glow_alpha = int(40 + 60 * _pulse)
            glow_r = int(12 + 6 * _pulse)
            glow_surf = pygame.Surface((btn_w + glow_r * 2, btn_h + glow_r * 2), pygame.SRCALPHA)
            pygame.draw.rect(glow_surf, (255, 200, 60, glow_alpha),
                             (0, 0, btn_w + glow_r * 2, btn_h + glow_r * 2), border_radius=10)
            screen.blit(glow_surf, (btn_x - glow_r, btn_y - glow_r))

            # Button body — rich dark with gold border
            pygame.draw.rect(screen, (50, 35, 15), btn_rect, border_radius=6)
            pygame.draw.rect(screen, (40, 28, 10), btn_rect.inflate(-4, -4), border_radius=5)
            # Gold border with shimmer
            border_col = (int(160 + 40 * _pulse), int(130 + 30 * _pulse), int(40 + 20 * _pulse))
            pygame.draw.rect(screen, border_col, btn_rect, 2, border_radius=6)
            # Inner highlight line at top
            hl_alpha = int(30 + 40 * _pulse)
            hl_surf = pygame.Surface((btn_w - 12, 1), pygame.SRCALPHA)
            hl_surf.fill((255, 230, 150, hl_alpha))
            screen.blit(hl_surf, (btn_x + 6, btn_y + 3))

            # Corner ornaments on the button
            for cx, cy, fx, fy in [(btn_rect.left + 3, btn_rect.top + 3, 1, 1),
                                    (btn_rect.right - 4, btn_rect.top + 3, -1, 1),
                                    (btn_rect.left + 3, btn_rect.bottom - 4, 1, -1),
                                    (btn_rect.right - 4, btn_rect.bottom - 4, -1, -1)]:
                pygame.draw.line(screen, border_col, (cx, cy), (cx + fx * 8, cy), 1)
                pygame.draw.line(screen, border_col, (cx, cy), (cx, cy + fy * 8), 1)

            # Button text
            btn_label = "Complete Quest"
            btn_text = node_font.render(btn_label, True, (255, 230, 150))
            btn_shadow = node_font.render(btn_label, True, (30, 20, 5))
            screen.blit(btn_shadow, (btn_rect.centerx - btn_text.get_width() // 2 + 1,
                                     btn_rect.centery - btn_text.get_height() // 2 + 1))
            screen.blit(btn_text, (btn_rect.centerx - btn_text.get_width() // 2,
                                   btn_rect.centery - btn_text.get_height() // 2))

            # Sparkle particles around button
            _t = pygame.time.get_ticks()
            for si in range(6):
                sp_phase = si * 1.047 + _t * 0.003
                sp_x = btn_rect.centerx + int((btn_w // 2 + 8) * math.cos(sp_phase))
                sp_y = btn_rect.centery + int((btn_h // 2 + 4) * math.sin(sp_phase * 0.7))
                sp_alpha = int(120 + 100 * math.sin(_t * 0.006 + si))
                sp_alpha = max(0, min(255, sp_alpha))
                sp_size = 2 + int(1.5 * abs(math.sin(_t * 0.005 + si * 0.8)))
                sp_s = pygame.Surface((sp_size * 2, sp_size * 2), pygame.SRCALPHA)
                pygame.draw.circle(sp_s, (255, 220, 100, sp_alpha), (sp_size, sp_size), sp_size)
                screen.blit(sp_s, (sp_x - sp_size, sp_y - sp_size))

            if not allow_vendor_actions:
                hint_s = tiny_font.render("Return to a town NPC first.", True, INK_DIM)
                screen.blit(hint_s, (det_x + (det_w - hint_s.get_width()) // 2, btn_y + btn_h + 6))
        elif st == "active":
            act = info_font.render("In progress...", True, GOLD)
            screen.blit(act, (det_x, dy))
        elif st == "turned_in":
            act = info_font.render("Completed.", True, GREEN_OK)
            screen.blit(act, (det_x, dy))
    else:
        hint = info_font.render("Select a quest.", True, INK_DIM)
        screen.blit(hint, (det_x + det_w // 2 - hint.get_width() // 2, content_top + (content_bot - content_top) // 2))

    # --- Bottom footnote bar — calligraphic hint strip ---
    _draw_parchment_divider(screen, panel.left + 16, panel.bottom - 38, pw - 32)
    if allow_vendor_actions:
        _hints = ["[J] Close Journal", "[A] Accept Quest"]
    else:
        _hints = ["[J] Close Journal", "Visit a town NPC to Accept or Turn In"]
    _hint_gap = pw // (len(_hints) + 1)
    _foot_y = panel.bottom - 26
    for _hi, _htxt in enumerate(_hints):
        _hs = tiny_font.render(_htxt, True, INK_BODY)
        _hx = panel.left + _hint_gap * (_hi + 1) - _hs.get_width() // 2
        # Inked bracket ornaments around each hint
        _br_l = _hx - 8
        _br_r = _hx + _hs.get_width() + 6
        _br_y = _foot_y + _hs.get_height() // 2
        pygame.draw.line(screen, FRAME, (_br_l, _br_y - 4), (_br_l, _br_y + 4), 1)
        pygame.draw.line(screen, FRAME, (_br_l, _br_y - 4), (_br_l + 3, _br_y - 4), 1)
        pygame.draw.line(screen, FRAME, (_br_l, _br_y + 4), (_br_l + 3, _br_y + 4), 1)
        pygame.draw.line(screen, FRAME, (_br_r, _br_y - 4), (_br_r, _br_y + 4), 1)
        pygame.draw.line(screen, FRAME, (_br_r, _br_y - 4), (_br_r - 3, _br_y - 4), 1)
        pygame.draw.line(screen, FRAME, (_br_r, _br_y + 4), (_br_r - 3, _br_y + 4), 1)
        screen.blit(_hs, (_hx, _foot_y))

    return quest_rects






def draw_npc_menu(
    screen: pygame.Surface,
    vendor: dict,
    npc_menu_mode: str,
    active_dialogue: Optional[DialogueSession],
    dialog_text: str,
    quest_states: Dict[str, str],
    quest_defs: List[Dict],
    option_rects_out: Dict[str, pygame.Rect],
    name_font: pygame.font.Font,
    text_font: pygame.font.Font,
    tiny_font: pygame.font.Font,
) -> None:
    """Draw NPC interaction menu or chat dialog panel above spell bar."""
    vendor_role = str(vendor.get("role", ""))
    has_shop = vendor_role in VENDOR_SHOPS
    is_blacksmith = vendor_role == "Blacksmith"
    has_quests = vendor_has_quest_menu(vendor_role, quest_states, quest_defs)

    options: List[Tuple[str, str, str]] = []
    if npc_menu_mode not in ("chat", "dialogue"):
        num = 1
        options.append((str(num), "Talk", "talk")); num += 1
        if has_shop:
            options.append((str(num), "Shop", "shop")); num += 1
        if is_blacksmith:
            options.append((str(num), "Craft", "craft")); num += 1
        if has_quests:
            options.append((str(num), "Quests", "quests"))

    pad_x = 18
    pad_y = 12
    panel_w = min(640, SCREEN_WIDTH - 200)
    content_w = panel_w - pad_x * 2
    role_lines = wrap_text_lines(tiny_font, str(vendor.get("job", "")), content_w, max_lines=2)
    role_line_h = tiny_font.get_height() + 2
    header_h = name_font.get_height() + 4 + len(role_lines) * role_line_h
    divider_gap = 10

    chat_lines: List[str] = []
    choices: List[Dict[str, object]] = []
    speaker = ""
    if npc_menu_mode == "chat":
        chat_lines = wrap_text_lines(text_font, dialog_text, content_w, max_lines=3)
    elif npc_menu_mode == "dialogue" and active_dialogue:
        node = active_dialogue.get_current_node()
        if node:
            speaker = str(node.get("speaker", vendor.get("name", "NPC")))
            text = str(node.get("text", "..."))
            chat_lines = wrap_text_lines(text_font, text, content_w, max_lines=3)
            choices = active_dialogue.get_available_choices()

    body_h = 0
    if npc_menu_mode == "chat":
        body_h = len(chat_lines) * (text_font.get_height() + 4)
    elif npc_menu_mode == "dialogue" and active_dialogue:
        speaker_h = tiny_font.get_height() + 2 if speaker else 0
        text_h = len(chat_lines) * (text_font.get_height() + 4)
        body_h = speaker_h + text_h
        if choices:
            choice_h = 26
            choice_gap = 6
            body_h += 8 + len(choices) * choice_h + max(0, len(choices) - 1) * choice_gap
    else:
        opt_h = 30
        opt_gap = 6
        body_h = len(options) * opt_h + max(0, len(options) - 1) * opt_gap

    panel_h = max(120, pad_y + header_h + divider_gap + body_h + pad_y)

    # Keep the dialog panel above the unified action belt to avoid overlap.
    _bar_visual_h = 56 + 30  # panel_h + globe protrusion + XP strip
    default_bottom = SCREEN_HEIGHT - _bar_visual_h - 12
    safe_bottom = default_bottom
    panel_top = max(12, safe_bottom - panel_h)
    panel = pygame.Rect((SCREEN_WIDTH - panel_w) // 2, panel_top, panel_w, panel_h)
    draw_ornate_panel(screen, panel)

    left_x = panel.left + pad_x
    name_s = name_font.render(str(vendor.get("name", "???")), True, (236, 214, 158))
    screen.blit(name_s, (left_x, panel.top + pad_y))

    role_y = panel.top + pad_y + name_s.get_height() + 4
    for li, line in enumerate(role_lines):
        role_s = tiny_font.render(line, True, (180, 170, 140))
        screen.blit(role_s, (left_x, role_y + li * role_line_h))

    divider_y = role_y + len(role_lines) * role_line_h + 6
    pygame.draw.line(screen, (80, 70, 50), (panel.left + pad_x, divider_y), (panel.right - pad_x, divider_y), 1)

    esc_label = "[ESC] Back" if npc_menu_mode in ("chat", "dialogue") else "[ESC] Leave"
    esc_s = tiny_font.render(esc_label, True, (140, 140, 150))
    screen.blit(esc_s, (panel.right - esc_s.get_width() - pad_x, panel.top + pad_y))

    if npc_menu_mode == "chat":
        option_rects_out.clear()
        body_y = divider_y + 8
        for li, line in enumerate(chat_lines):
            ta = text_font.render(line, True, (228, 230, 234))
            screen.blit(ta, (panel.left + pad_x, body_y + li * (text_font.get_height() + 4)))
    elif npc_menu_mode == "dialogue" and active_dialogue:
        option_rects_out.clear()
        body_y = divider_y + 8
        if speaker:
            spk_s = tiny_font.render(f"{speaker}:", True, (210, 190, 140))
            screen.blit(spk_s, (panel.left + pad_x, body_y))
            body_y += spk_s.get_height() + 2

        for li, line in enumerate(chat_lines):
            ta = text_font.render(line, True, (228, 230, 234))
            screen.blit(ta, (panel.left + pad_x, body_y + li * (text_font.get_height() + 4)))
        body_y += len(chat_lines) * (text_font.get_height() + 4)

        if choices:
            body_y += 8
            mx, my = pygame.mouse.get_pos()
            choice_w = content_w
            choice_h = 26
            choice_gap = 6
            for i, choice in enumerate(choices):
                c_rect = pygame.Rect(panel.left + pad_x, body_y, choice_w, choice_h)
                option_rects_out[f"choice_{i}"] = c_rect
                hover = c_rect.collidepoint(mx, my)
                draw_ui_button(screen, c_rect, hovered=hover)
                c_text = str(choice.get("text", ""))
                screen.blit(tiny_font.render(c_text, True, (220, 220, 220)),
                            (c_rect.left + 8, c_rect.centery - tiny_font.get_height() // 2))
                body_y += choice_h + choice_gap
    else:
        option_rects_out.clear()
        mx, my = pygame.mouse.get_pos()
        opt_h = 30
        opt_gap = 6
        opt_w = min(300, content_w)
        ox = panel.left + pad_x
        oy = divider_y + 8

        def draw_menu_option_icon(surface: pygame.Surface, opt_id: str, icon_box: pygame.Rect) -> None:
            cx, cy = icon_box.center
            pygame.draw.rect(surface, (34, 34, 40), icon_box, border_radius=4)
            pygame.draw.rect(surface, (96, 96, 106), icon_box, 1, border_radius=4)

            if opt_id == "talk":
                bubble = pygame.Rect(icon_box.left + 3, icon_box.top + 3, icon_box.width - 6, icon_box.height - 7)
                pygame.draw.rect(surface, (182, 168, 126), bubble, border_radius=4)
                tail = [(bubble.left + 4, bubble.bottom - 1), (bubble.left + 8, bubble.bottom - 1), (bubble.left + 5, bubble.bottom + 3)]
                pygame.draw.polygon(surface, (182, 168, 126), tail)
                pygame.draw.line(surface, (84, 76, 56), (bubble.left + 4, cy - 2), (bubble.right - 4, cy - 2), 1)
                pygame.draw.line(surface, (84, 76, 56), (bubble.left + 4, cy + 2), (bubble.right - 6, cy + 2), 1)
            elif opt_id == "shop":
                pygame.draw.ellipse(surface, (194, 156, 82), (icon_box.left + 3, icon_box.top + 5, icon_box.width - 6, icon_box.height - 7))
                pygame.draw.rect(surface, (104, 74, 36), (icon_box.left + 4, icon_box.top + 4, icon_box.width - 8, 3))
                pygame.draw.circle(surface, (228, 196, 112), (cx + 2, cy + 1), 2)
            elif opt_id == "craft":
                pygame.draw.rect(surface, (152, 116, 70), (cx - 1, cy - 3, 3, 8), border_radius=1)
                pygame.draw.rect(surface, (136, 138, 148), (cx - 5, cy - 6, 10, 4), border_radius=1)
                pygame.draw.rect(surface, (98, 102, 114), (cx + 2, cy - 5, 3, 2), border_radius=1)
            elif opt_id == "quests":
                page = pygame.Rect(icon_box.left + 4, icon_box.top + 3, icon_box.width - 8, icon_box.height - 6)
                pygame.draw.rect(surface, (200, 188, 152), page, border_radius=2)
                pygame.draw.line(surface, (130, 118, 88), (page.left + 2, page.top + 4), (page.right - 2, page.top + 4), 1)
                pygame.draw.line(surface, (130, 118, 88), (page.left + 2, page.top + 7), (page.right - 4, page.top + 7), 1)
                pygame.draw.circle(surface, (166, 150, 116), (page.left + 1, page.top + 2), 2)
                pygame.draw.circle(surface, (166, 150, 116), (page.right - 1, page.bottom - 2), 2)

        for key, label, opt_id in options:
            opt_rect = pygame.Rect(ox, oy, opt_w, opt_h)
            option_rects_out[opt_id] = opt_rect
            hovered = opt_rect.collidepoint(mx, my)
            draw_ui_button(screen, opt_rect, hovered=hovered)
            icon_rect = pygame.Rect(opt_rect.left + 10, opt_rect.top + 7, 16, 16)
            draw_menu_option_icon(screen, opt_id, icon_rect)
            lbl_s = text_font.render(label, True, (228, 225, 210))
            screen.blit(lbl_s, (icon_rect.right + 8, opt_rect.centery - lbl_s.get_height() // 2))
            oy += opt_h + opt_gap


def draw_inventory_screen(
    screen: pygame.Surface,
    item_inventory: List[Dict],
    backpack_inventory: List[Dict],
    class_id: str,
    materials: Dict[str, int],
    recipes: List[Dict],
    selected_recipe_id: Optional[str],
    inv_tab: str,
    title_font: pygame.font.Font,
    node_font: pygame.font.Font,
    info_font: pygame.font.Font,
    tiny_font: pygame.font.Font,
) -> Tuple[Dict[str, pygame.Rect], Dict[int, pygame.Rect], Dict[int, pygame.Rect], Dict[str, pygame.Rect]]:
    """Draw tabbed inventory screen.

    Returns (crafting_rects, hotbar_slot_rects, backpack_slot_rects, tab_rects).
    """
    # Improved standalone inventory panel (Right side)
    panel_w = 440
    panel_h = 560
    panel = pygame.Rect(SCREEN_WIDTH - panel_w - 80, 120, panel_w, panel_h)
    draw_ornate_panel(screen, panel)
    title_s = title_font.render("Inventory", True, (234, 220, 180))
    close_s = tiny_font.render("[I] Close", True, (140, 140, 150))
    # Vertically align both labels by their visual centers along a header strip
    _hdr_cy = panel.top + 14 + title_s.get_height() // 2
    screen.blit(title_s, (panel.left + 20, _hdr_cy - title_s.get_height() // 2))
    screen.blit(close_s, (panel.right - close_s.get_width() - 16, _hdr_cy - close_s.get_height() // 2))

    if inv_tab == "Items":
        inv_tab = "Backpack"
    if inv_tab not in ("Backpack", "Materials", "Craft"):
        inv_tab = "Backpack"
    tabs = ["Backpack", "Materials"]
    tab_rects: Dict[str, pygame.Rect] = {}
    tab_x = panel.left + 160
    tab_y = panel.top + 14
    for tab in tabs:
        tw = 110
        tr = pygame.Rect(tab_x, tab_y, tw, 30)
        tab_rects[tab] = tr
        active = inv_tab == tab
        draw_ui_tab(screen, tr, active=active, text=tab, font=node_font)
        tab_x += tw + 8

    content_top = panel.top + 62
    content_rect = pygame.Rect(panel.left + 16, content_top, panel.width - 32, panel.height - 76)
    crafting_rects: Dict[str, pygame.Rect] = {}
    hotbar_slot_rects: Dict[int, pygame.Rect] = {}
    backpack_slot_rects: Dict[int, pygame.Rect] = {}
    mouse_pos = pygame.mouse.get_pos()
    hovered_item: Optional[Dict[str, object]] = None
    hovered_item_slot: Optional[pygame.Rect] = None

    if inv_tab == "Items":
        slot_size = 72
        cols = 4
        gap = 16
        grid_w = cols * slot_size + (cols - 1) * gap
        start_x = content_rect.centerx - grid_w // 2
        start_y = content_top + 12
        count_s = tiny_font.render(
            f"Hotbar {sum(1 for s in item_inventory if s is not None)}/{HOTBAR_SLOT_COUNT}    Backpack {len(backpack_inventory)}/{BACKPACK_SLOT_COUNT}",
            True,
            (160, 150, 120),
        )
        screen.blit(count_s, (content_rect.centerx - count_s.get_width() // 2, start_y - 16))
        for i in range(HOTBAR_SLOT_COUNT):
            col = i % cols
            row = i // cols
            sx = start_x + col * (slot_size + gap)
            sy = start_y + row * (slot_size + gap + 34)
            slot_rect = pygame.Rect(sx, sy, slot_size, slot_size)
            hotbar_slot_rects[i] = slot_rect
            _inv_entry = item_inventory[i] if i < len(item_inventory) else None
            if _inv_entry is not None:
                item = _inv_entry
                item_col = item.get("color", (200, 200, 200))
                blocked = item_blocked_for_class(item, class_id)
                draw_ui_slot(screen, slot_rect, hovered=slot_rect.collidepoint(mouse_pos), blocked=blocked)
                icon = resolve_item_icon(item, slot_size - 12)
                if isinstance(icon, pygame.Surface):
                    screen.blit(icon, (slot_rect.left + 6, slot_rect.top + 6))
                else:
                    pygame.draw.rect(screen, item_col, slot_rect.inflate(-14, -14), border_radius=6)
                if blocked:
                    pygame.gfxdraw.box(screen, slot_rect, (140, 24, 24, 96))
                if slot_rect.collidepoint(mouse_pos):
                    hovered_item = item
                    hovered_item_slot = slot_rect
                    pygame.draw.rect(screen, (224, 96, 96) if blocked else (224, 196, 118), slot_rect, 2, border_radius=8)
                item_name = ellipsize_text(tiny_font, str(item.get("name", "?")), slot_size - 6)
                name_s2 = tiny_font.render(item_name, True, (230, 140, 140) if blocked else (230, 225, 210))
                screen.blit(name_s2, (slot_rect.left + 2, slot_rect.bottom + 4))
                key_s2 = tiny_font.render(f"[F{i + 1}]", True, (160, 150, 100))
                screen.blit(key_s2, (slot_rect.right - key_s2.get_width() - 2, slot_rect.bottom + 22))
            else:
                draw_ui_slot(screen, slot_rect)
                empty_s = tiny_font.render("Empty", True, (70, 70, 80))
                screen.blit(empty_s, (slot_rect.left + 2, slot_rect.bottom + 4))
        hint2 = info_font.render("Left click: use item   Right click: move to backpack", True, (130, 130, 150))
        hy = start_y + 2 * (slot_size + gap + 34) - 2
        screen.blit(hint2, (content_rect.centerx - hint2.get_width() // 2, hy))
    elif inv_tab == "Backpack":
        slot_size = 64
        cols = 5
        gap = 14
        row_gap_extra = 16
        grid_w = cols * slot_size + (cols - 1) * gap
        start_x = content_rect.centerx - grid_w // 2
        start_y = content_top + 12
        title2 = node_font.render(f"Backpack ({len(backpack_inventory)}/{BACKPACK_SLOT_COUNT})", True, (222, 214, 188))
        screen.blit(title2, (content_rect.centerx - title2.get_width() // 2, start_y - 22))
        for i in range(BACKPACK_SLOT_COUNT):
            col = i % cols
            row = i // cols
            sx = start_x + col * (slot_size + gap)
            sy = start_y + row * (slot_size + gap + row_gap_extra)
            slot_rect = pygame.Rect(sx, sy, slot_size, slot_size)
            backpack_slot_rects[i] = slot_rect
            if i < len(backpack_inventory):
                item = backpack_inventory[i]
                item_col = item.get("color", (170, 170, 170))
                blocked = item_blocked_for_class(item, class_id)
                draw_ui_slot(screen, slot_rect, hovered=slot_rect.collidepoint(mouse_pos), blocked=blocked)
                icon = resolve_item_icon(item, slot_size - 12)
                if isinstance(icon, pygame.Surface):
                    screen.blit(icon, (slot_rect.left + 6, slot_rect.top + 6))
                else:
                    pygame.draw.rect(screen, item_col, slot_rect.inflate(-14, -14), border_radius=6)
                if blocked:
                    pygame.gfxdraw.box(screen, slot_rect, (140, 24, 24, 96))
                if slot_rect.collidepoint(mouse_pos):
                    hovered_item = item
                    hovered_item_slot = slot_rect
                    pygame.draw.rect(screen, (224, 96, 96) if blocked else (224, 196, 118), slot_rect, 2, border_radius=8)
                short_name = ellipsize_text(tiny_font, str(item.get("name", "?")), slot_size - 6)
                item_s = tiny_font.render(short_name, True, (230, 140, 140) if blocked else (216, 210, 192))
                screen.blit(item_s, (slot_rect.left + 2, slot_rect.bottom + 2))
            else:
                draw_ui_slot(screen, slot_rect)
        hint_bp = info_font.render("Left: Drag   Right: Use/Equip", True, (130, 130, 150))
        hint_y = start_y + 4 * (slot_size + gap + row_gap_extra) - 10
        screen.blit(hint_bp, (content_rect.centerx - hint_bp.get_width() // 2, hint_y))
    elif inv_tab == "Materials":
        y = content_top + 20
        x_left = content_rect.left + 24
        if not any(materials.get(m, 0) > 0 for m in MATERIAL_ORDER):
            none_s = node_font.render("No materials yet. Hunt wolves to gather them!", True, (160, 150, 130))
            screen.blit(none_s, (content_rect.centerx - none_s.get_width() // 2, y + 40))
        else:
            # Tidy table: name left-aligned, count right-aligned to the same column
            _row_right = content_rect.right - 24
            for mat_id in MATERIAL_ORDER:
                mat_data = WOLF_MATERIALS.get(mat_id)
                if mat_data is None:
                    continue
                count = materials.get(mat_id, 0)
                col = mat_data["color"]
                pygame.draw.circle(screen, col, (x_left + 10, y + 12), 10)
                name_ms = node_font.render(str(mat_data["name"]), True, (220, 215, 200))
                count_ms = node_font.render(f"x{count}", True, (200, 190, 140) if count > 0 else (80, 80, 90))
                # Vertically center both texts on the same baseline as the dot
                _ny = y + 12 - name_ms.get_height() // 2
                screen.blit(name_ms, (x_left + 28, _ny))
                screen.blit(count_ms, (_row_right - count_ms.get_width(), _ny))
                y += 36
    else:
        msg = node_font.render("Crafting moved to Professions [O].", True, (206, 194, 158))
        sub = info_font.render("Use the dedicated profession screen for progression and recipes.", True, (144, 140, 130))
        screen.blit(msg, (content_rect.centerx - msg.get_width() // 2, content_rect.centery - 14))
        screen.blit(sub, (content_rect.centerx - sub.get_width() // 2, content_rect.centery + 14))

    if hovered_item is not None and hovered_item_slot is not None:
        draw_item_tooltip(screen, hovered_item, hovered_item_slot, node_font, info_font)

    return crafting_rects, hotbar_slot_rects, backpack_slot_rects, tab_rects


def can_item_equip_to_slot(
    item: Dict[str, object],
    target_slot: str,
    class_id: str,
) -> Tuple[bool, str]:
    item_type = str(item.get("item_type", "")).strip().lower()
    equip_slot = str(item.get("equip_slot", "")).strip().lower()
    if item_type != "equipment" and not equip_slot:
        return False, "This item cannot be equipped."
    if equip_slot not in EQUIPMENT_SLOT_ORDER:
        return False, "This item has no valid equipment slot."
    visual_slot, visual_conf = infer_item_visual_slot(item)
    if visual_slot in EQUIPMENT_SLOT_ORDER and visual_conf >= 0.80 and equip_slot != visual_slot:
        need_visual = EQUIPMENT_SLOT_LABELS.get(visual_slot, visual_slot.title())
        return False, f"Icon indicates {need_visual} slot."
    if equip_slot != target_slot:
        need = EQUIPMENT_SLOT_LABELS.get(equip_slot, equip_slot.title())
        return False, f"Requires {need} slot."
    class_lock = str(item.get("class_lock", "")).strip().lower()
    if class_lock and class_lock != class_id.strip().lower():
        return False, f"Only {class_lock.title()} can equip this."
    return True, ""


def summarize_equipped_stats(
    equipped_items: Dict[str, Dict[str, object]],
    class_id: str,
) -> Tuple[Dict[str, float], List[str]]:
    totals: Dict[str, float] = {key: 0.0 for key in EQUIP_STAT_KEYS}
    set_counts: Dict[str, int] = {}
    class_norm = class_id.strip().lower()

    for slot in EQUIPMENT_SLOT_ORDER:
        item = equipped_items.get(slot)
        if not isinstance(item, dict):
            continue
        if item_blocked_for_class(item, class_norm):
            continue
        raw_stats = item.get("stats")
        if isinstance(raw_stats, dict):
            for key, raw_val in raw_stats.items():
                try:
                    val = float(raw_val)
                except (TypeError, ValueError):
                    continue
                stat_key = str(key)
                totals[stat_key] = totals.get(stat_key, 0.0) + val
        set_name = str(item.get("set_name", "")).strip()
        lock = str(item.get("class_lock", "")).strip().lower()
        if set_name and (not lock or lock == class_norm):
            set_counts[set_name] = set_counts.get(set_name, 0) + 1

    bonus_lines: List[str] = []
    set_bonuses = CLASS_ARMOR_SET_BONUSES.get(class_norm, {})
    if isinstance(set_bonuses, dict):
        for set_name, piece_count in set_counts.items():
            for needed in sorted(set_bonuses.keys()):
                if piece_count < int(needed):
                    continue
                bonus_stats = set_bonuses.get(needed)
                if not isinstance(bonus_stats, dict):
                    continue
                parts: List[str] = []
                for key, raw_val in bonus_stats.items():
                    try:
                        val = float(raw_val)
                    except (TypeError, ValueError):
                        continue
                    stat_key = str(key)
                    totals[stat_key] = totals.get(stat_key, 0.0) + val
                    line = format_item_stat_line(stat_key, val)
                    if line:
                        parts.append(line)
                if parts:
                    bonus_lines.append(f"{set_name} ({int(needed)}): " + ", ".join(parts))
    return totals, bonus_lines


def draw_character_screen(
    screen: pygame.Surface,
    player_name: str,
    class_name: str,
    class_id: str,
    equipped_items: Dict[str, Dict[str, object]],
    player_level: int,
    total_stats: Dict[str, float],
    stat_view: str,
    dropdown_open: bool,
    title_font: pygame.font.Font,
    node_font: pygame.font.Font,
    info_font: pygame.font.Font,
    tiny_font: pygame.font.Font,
    spell_icons: Dict[str, pygame.Surface],
) -> Tuple[Dict[str, pygame.Rect], pygame.Rect, Dict[str, pygame.Rect]]:
    # Improved standalone character panel (Left side)
    panel_w = 400
    panel_h = 560
    panel = pygame.Rect(80, 120, panel_w, panel_h)
    draw_ornate_panel(screen, panel)

    title_s = title_font.render("Character", True, (234, 220, 180))
    close_s = tiny_font.render("[P] Close", True, (140, 140, 150))
    name_s = node_font.render(player_name, True, (214, 208, 188))
    cls_s = tiny_font.render(class_name, True, (176, 172, 162))

    header_y = panel.top + 12
    header_h = max(title_s.get_height(), close_s.get_height())
    title_pos = (panel.centerx - title_s.get_width() // 2, header_y)
    close_pos = (
        panel.right - close_s.get_width() - 16,
        header_y + (header_h - close_s.get_height()) // 2,
    )
    screen.blit(title_s, title_pos)
    screen.blit(close_s, close_pos)

    # Character layout is measured from the header down so the equipment stack,
    # portrait, labels, and stats panel stay aligned as one block.
    content_top = header_y + header_h + 8
    slot_size = 48
    slot_gap = 12
    side_gap = 20

    # Portrait Area
    portrait = pygame.Rect(0, 0, 92, 102)
    portrait.midtop = (panel.centerx, content_top + slot_size + 6)
    pygame.draw.rect(screen, (28, 28, 34), portrait, border_radius=8)
    pygame.draw.rect(screen, (84, 84, 96), portrait, 1, border_radius=8)
    
    name_y = portrait.bottom + 6
    class_y = name_y + name_s.get_height()
    pants_y = class_y + cls_s.get_height() + 6
    belt_y = pants_y + slot_size + 8
    screen.blit(name_s, (panel.centerx - name_s.get_width() // 2, name_y))
    screen.blit(cls_s, (panel.centerx - cls_s.get_width() // 2, class_y))

    # Equipment Slots Layout
    cx = portrait.centerx
    side_column_top = portrait.top + 6
    slot_positions = {
        "head": (cx - slot_size // 2, content_top),
        "chest": (cx - slot_size // 2, portrait.centery - slot_size // 2),
        "pants": (cx - slot_size // 2, pants_y),
        "belt": (cx - slot_size // 2, belt_y),

        "weapon": (portrait.left - slot_size - side_gap, side_column_top),
        "hands": (portrait.left - slot_size - side_gap, side_column_top + slot_size + slot_gap),
        "ring": (portrait.left - slot_size - side_gap, side_column_top + (slot_size + slot_gap) * 2),

        "offhand": (portrait.right + side_gap, side_column_top),
        "feet": (portrait.right + side_gap, side_column_top + slot_size + slot_gap),
        "amulet": (portrait.right + side_gap, side_column_top + (slot_size + slot_gap) * 2),
    }
    
    equip_rects: Dict[str, pygame.Rect] = {}
    mouse_pos = pygame.mouse.get_pos()
    hovered_item: Optional[Dict[str, object]] = None
    hovered_rect: Optional[pygame.Rect] = None

    for slot in EQUIPMENT_SLOT_ORDER:
        pos = slot_positions.get(slot)
        if pos is None:
            continue
        rect = pygame.Rect(pos[0], pos[1], slot_size, slot_size)
        equip_rects[slot] = rect
        item = equipped_items.get(slot)
        if isinstance(item, dict):
            blocked = item_blocked_for_class(item, class_id)
            draw_ui_slot(screen, rect, hovered=rect.collidepoint(mouse_pos), blocked=blocked)
            icon = resolve_item_icon(item, slot_size - 10)
            if isinstance(icon, pygame.Surface):
                screen.blit(icon, (rect.left + 5, rect.top + 5))
            else:
                pygame.draw.rect(screen, item.get("color", (170, 170, 170)), rect.inflate(-12, -12), border_radius=5)
            if blocked:
                pygame.gfxdraw.box(screen, rect, (140, 24, 24, 96))
            if rect.collidepoint(mouse_pos):
                hovered_item = item
                hovered_rect = rect
                pygame.draw.rect(screen, (224, 96, 96) if blocked else (226, 198, 120), rect, 2, border_radius=8)
        else:
            draw_empty_equipment_slot(screen, rect, slot, hovered=rect.collidepoint(mouse_pos))
            if rect.collidepoint(mouse_pos):
                hovered_item = build_empty_equipment_slot_tooltip(slot)
                hovered_rect = rect

    # Stats Panel with Dropdown
    stats_panel_bottom = panel.bottom - 20
    stats_panel_target_h = 214
    stats_panel_top = max(belt_y + slot_size + 14, stats_panel_bottom - stats_panel_target_h)
    stats_panel = pygame.Rect(panel.left + 24, stats_panel_top, panel.width - 48, stats_panel_bottom - stats_panel_top)
    pygame.draw.rect(screen, (24, 24, 30), stats_panel, border_radius=6)
    pygame.draw.rect(screen, (60, 60, 70), stats_panel, 1, border_radius=6)
    
    # Dropdown Header
    dropdown_rect = pygame.Rect(stats_panel.left + 10, stats_panel.top + 10, stats_panel.width - 20, 24)
    pygame.draw.rect(screen, (40, 40, 48), dropdown_rect, border_radius=4)
    pygame.draw.rect(screen, (80, 80, 90), dropdown_rect, 1, border_radius=4)
    view_label = tiny_font.render(stat_view, True, (220, 220, 220))
    view_arrow = tiny_font.render("v", True, (200, 200, 210))
    screen.blit(view_label, (dropdown_rect.left + 10, dropdown_rect.centery - view_label.get_height() // 2))
    screen.blit(
        view_arrow,
        (dropdown_rect.right - 10 - view_arrow.get_width(), dropdown_rect.centery - view_arrow.get_height() // 2),
    )
    
    # Stats Content
    stat_y = dropdown_rect.bottom + 12
    stat_x = stats_panel.left + 16
    stat_w = stats_panel.width - 32
    
    def draw_row(label: str, value: str, color: Tuple[int, int, int] = (220, 220, 220)) -> None:
        nonlocal stat_y
        lbl_s = tiny_font.render(label, True, (160, 160, 170))
        val_s = tiny_font.render(value, True, color)
        row_h = max(lbl_s.get_height(), val_s.get_height())
        row_y = stat_y
        screen.blit(lbl_s, (stat_x, row_y))
        screen.blit(val_s, (stat_x + stat_w - val_s.get_width(), row_y))
        sep_y = row_y + row_h + 2
        pygame.draw.line(screen, (44, 44, 50), (stat_x, sep_y), (stat_x + stat_w, sep_y))
        stat_y = sep_y + 3

    if stat_view == "Attributes":
        draw_row("Health", f"{int(total_stats.get('max_hp', 0))}", (100, 220, 100))
        draw_row("Mana", f"{int(total_stats.get('max_mana', 0))}", (100, 150, 255))
        draw_row("Level", f"{player_level}", (220, 200, 100))
        draw_row("Move Speed", f"{int(total_stats.get('move_speed', 1.0) * 100)}%", (200, 200, 220))
    elif stat_view == "Melee":
        dmg = int(total_stats.get('basic_damage', 0))
        draw_row("Damage", f"{dmg} - {int(dmg * 1.2)}", (220, 100, 100))
        draw_row("Attack Power", f"{dmg * 2}", (220, 150, 100))
        draw_row("Crit Chance", "5.0%", (220, 200, 100))
        draw_row("Speed", "1.00", (200, 200, 200))
    elif stat_view == "Spell":
        pwr = int(total_stats.get('spell_power', 0))
        draw_row("Spell Power", f"{pwr}", (150, 100, 255))
        draw_row("Mana Regen", f"{total_stats.get('mana_regen', 0):.1f} / s", (100, 200, 255))
        cdr = total_stats.get('cooldown_reduction', 0.0) * 100
        draw_row("Cooldown Red.", f"{cdr:.1f}%", (200, 220, 100))
        draw_row("Crit Chance", "5.0%", (220, 200, 100))
    elif stat_view == "Defense":
        armor = int(total_stats.get('armor', 0))
        draw_row("Armor", f"{armor}", (200, 200, 200))
        dr = total_stats.get('damage_reduction', 0.0) * 100
        draw_row("Dmg Reduction", f"{dr:.1f}%", (100, 220, 100))
        draw_row("Block", "0%", (160, 160, 160))
        draw_row("Dodge", "5%", (160, 160, 160))

    # Dropdown Options Overlay
    option_rects: Dict[str, pygame.Rect] = {}
    if dropdown_open:
        options = ["Attributes", "Melee", "Spell", "Defense"]
        opt_h = 24
        list_h = len(options) * opt_h
        list_rect = pygame.Rect(dropdown_rect.left, dropdown_rect.bottom, dropdown_rect.width, list_h)
        pygame.draw.rect(screen, (30, 30, 36), list_rect, border_radius=4)
        pygame.draw.rect(screen, (80, 80, 90), list_rect, 1, border_radius=4)
        
        for i, opt in enumerate(options):
            opt_rect = pygame.Rect(list_rect.left, list_rect.top + i * opt_h, list_rect.width, opt_h)
            option_rects[opt] = opt_rect
            hover = opt_rect.collidepoint(mouse_pos)
            if hover:
                pygame.draw.rect(screen, (50, 50, 60), opt_rect)
            opt_s = tiny_font.render(opt, True, (220, 220, 220) if hover else (180, 180, 180))
            screen.blit(opt_s, (opt_rect.left + 10, opt_rect.centery - opt_s.get_height() // 2))

    if hovered_item is not None and hovered_rect is not None:
        draw_item_tooltip(screen, hovered_item, hovered_rect, node_font, info_font)
    
    return equip_rects, dropdown_rect, option_rects


def load_all_saves() -> List[Dict]:
    if not os.path.exists(SAVE_PATH):
        return []
    try:
        with open(SAVE_PATH, "r") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return [data]
            elif isinstance(data, list):
                return data
            return []
    except Exception:
        return []

def save_all_saves(saves: List[Dict]) -> None:
    class SetEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, set):
                return list(obj)
            return super().default(obj)
    try:
        with open(SAVE_PATH, "w") as f:
            json.dump(saves, f, indent=2, cls=SetEncoder)
    except Exception:
        pass

UI_ASSETS: Dict[str, pygame.Surface] = {}


def load_ui_assets() -> None:
    if UI_ASSETS:
        return

    files = {
        "panel": "panel.png",
        "slot": "slot.png",
        "slot_select": "slot_select.png",
        "slot_locked": "slot_locked.png",
        "tab": "tab.png",
        "tab_active": "tab_active.png",
        "button": "button.png",
        "button_hover": "button_hover.png",
        "bar_hp": "bar_hp.png",
        "bar_mp": "bar_mp.png",
        "bar_xp": "bar_xp.png",
        "bar_frame": "bar_frame.png",
    }

    # Try multiple possible folder names for the new UI assets
    possible_bases = [
        os.path.join("assets", "ui"),
        os.path.join("assets", "new ui"),
        os.path.join("assets", "new_ui"),
        os.path.join("asset", "new ui"),
        "assets",
    ]
    
    base = possible_bases[0]
    for b in possible_bases:
        if os.path.isdir(b) and (os.path.exists(os.path.join(b, "panel.png")) or os.path.exists(os.path.join(b, "slot.png"))):
            base = b
            break

    for key, filename in files.items():
        try:
            path = os.path.join(base, filename)
            if os.path.exists(path):
                UI_ASSETS[key] = pygame.image.load(path).convert_alpha()
        except (pygame.error, FileNotFoundError):
            pass


def draw_nine_slice(surface: pygame.Surface, img: pygame.Surface, dest: pygame.Rect, corner: int = 16) -> None:
    w, h = img.get_size()
    if w < corner * 2 or h < corner * 2:
        surface.blit(pygame.transform.scale(img, (dest.width, dest.height)), dest)
        return

    surface.blit(img, (dest.left, dest.top), (0, 0, corner, corner))
    surface.blit(img, (dest.right - corner, dest.top), (w - corner, 0, corner, corner))
    surface.blit(img, (dest.left, dest.bottom - corner), (0, h - corner, corner, corner))
    surface.blit(img, (dest.right - corner, dest.bottom - corner), (w - corner, h - corner, corner, corner))

    center_w = max(0, dest.width - 2 * corner)
    center_h = max(0, dest.height - 2 * corner)

    if center_w > 0:
        top = pygame.transform.scale(img.subsurface((corner, 0, w - 2 * corner, corner)), (center_w, corner))
        bot = pygame.transform.scale(img.subsurface((corner, h - corner, w - 2 * corner, corner)), (center_w, corner))
        surface.blit(top, (dest.left + corner, dest.top))
        surface.blit(bot, (dest.left + corner, dest.bottom - corner))

    if center_h > 0:
        left = pygame.transform.scale(img.subsurface((0, corner, corner, h - 2 * corner)), (corner, center_h))
        right = pygame.transform.scale(img.subsurface((w - corner, corner, corner, h - 2 * corner)), (corner, center_h))
        surface.blit(left, (dest.left, dest.top + corner))
        surface.blit(right, (dest.right - corner, dest.top + corner))

    if center_w > 0 and center_h > 0:
        center = pygame.transform.scale(img.subsurface((corner, corner, w - 2 * corner, h - 2 * corner)), (center_w, center_h))
        surface.blit(center, (dest.left + corner, dest.top + corner))


_SLOT_ICON_CACHE: Dict[Tuple[str, int], pygame.Surface] = {}
_SLOT_GHOST_ICON_HINTS: Dict[str, Tuple[int, int]] = {
    "head": (15, 6),
    "chest": (12, 5),
    "hands": (13, 3),
    "feet": (14, 3),
    "weapon": (3, 3),
    "offhand": (11, 2),
    "amulet": (11, 7),
    "ring": (17, 5),
}

# Pixel-art silhouettes on a 16x16 grid. ' ' = transparent, '.' = dark shadow,
# '#' = main fill, '+' = highlight. All icons are hand-designed to be
# instantly recognizable even at tiny UI sizes.
_SLOT_PIXEL_ART: Dict[str, List[str]] = {
    "head": [
        "                ",
        "    ..####..    ",
        "   .########.   ",
        "  .##########.  ",
        "  .###++++###.  ",
        " .####++++####. ",
        " .####++++####. ",
        " .############. ",
        " .############. ",
        "  .##########.  ",
        "  .##########.  ",
        "   .########.   ",
        "    .######.    ",
        "     .####.     ",
        "                ",
        "                ",
    ],
    "chest": [
        "                ",
        "  ..##....##..  ",
        " .###.#..#.###. ",
        " .####....####. ",
        " .############. ",
        " .###++++++###. ",
        " .##++####++##. ",
        " .##+######+##. ",
        " .##+######+##. ",
        " .##++####++##. ",
        " .###++++++###. ",
        " .############. ",
        "  .##########.  ",
        "   .########.   ",
        "                ",
        "                ",
    ],
    "pants": [
        "                ",
        "   .########.   ",
        "  .##########.  ",
        "  .##++++++##.  ",
        "  .##+####+##.  ",
        "  .##+####+##.  ",
        "  .##+####+##.  ",
        "  .##+....+##.  ",
        "  .##.    .##.  ",
        "  .##.    .##.  ",
        "  .##.    .##.  ",
        "  .##.    .##.  ",
        "  .##.    .##.  ",
        "   ..      ..   ",
        "                ",
        "                ",
    ],
    "hands": [
        "                ",
        "      ####      ",
        "    ..####..    ",
        "   .########.   ",
        "  .##########.  ",
        "  .###++++###.  ",
        "  .##+####+##.  ",
        "  .##+####+##.  ",
        "  .###++++###.  ",
        "  .##########.  ",
        "   .########.   ",
        "    .######.    ",
        "     .####.     ",
        "      .##.      ",
        "                ",
        "                ",
    ],
    "feet": [
        "                ",
        "                ",
        "    .####.      ",
        "   .######.     ",
        "   .##++##.     ",
        "   .##++##.     ",
        "   .######.     ",
        "   .######....  ",
        "   .##########. ",
        "   .####++####. ",
        "   .##########. ",
        "   .##########. ",
        "    .########.  ",
        "     .......    ",
        "                ",
        "                ",
    ],
    "weapon": [
        "                ",
        "           .##  ",
        "          .###  ",
        "         .###.  ",
        "        .###.   ",
        "       .###.    ",
        "      .###.     ",
        "     .###.      ",
        "    .###.       ",
        "   .###.        ",
        "  .####.        ",
        " .######.       ",
        " .######.       ",
        " ..####..       ",
        "   .##.         ",
        "                ",
    ],
    "offhand": [
        "                ",
        "   ..######..   ",
        "  .##########.  ",
        "  .##########.  ",
        "  .####++####.  ",
        "  .###+##+###.  ",
        "  .###+##+###.  ",
        "  .###+##+###.  ",
        "  .####++####.  ",
        "  .##########.  ",
        "   .########.   ",
        "    .######.    ",
        "     .####.     ",
        "      .##.      ",
        "       ..       ",
        "                ",
    ],
    "amulet": [
        "                ",
        "  ..        ..  ",
        "  ##.      .##  ",
        "   .#.    .#.   ",
        "    .#.  .#.    ",
        "     .####.     ",
        "     .####.     ",
        "    .######.    ",
        "   .########.   ",
        "   .###++###.   ",
        "   .##++++##.   ",
        "   .##++++##.   ",
        "   .###++###.   ",
        "    .######.    ",
        "     .####.     ",
        "                ",
    ],
    "ring": [
        "                ",
        "                ",
        "      .##.      ",
        "     .####.     ",
        "     .#++#.     ",
        "      .##.      ",
        "    .######.    ",
        "   .########.   ",
        "  .##########.  ",
        "  .###....###.  ",
        "  .##.    .##.  ",
        "  .##.    .##.  ",
        "  .###....###.  ",
        "   .########.   ",
        "    .######.    ",
        "                ",
    ],
    "belt": [
        "                ",
        "                ",
        "                ",
        "                ",
        " .############. ",
        " .##++####++##. ",
        " .##+##++##+##. ",
        " .##+#+##+#+##. ",
        " .##+#+##+#+##. ",
        " .##+##++##+##. ",
        " .##++####++##. ",
        " .############. ",
        "                ",
        "                ",
        "                ",
        "                ",
    ],
}


def _build_slot_ghost_icon(slot: str, size: int) -> Optional[pygame.Surface]:
    coords = _SLOT_GHOST_ICON_HINTS.get(slot)
    if coords is None:
        return None
    icon = load_items_sheet_icon(int(coords[0]), int(coords[1]), size)
    if not isinstance(icon, pygame.Surface):
        return None
    mask = pygame.mask.from_surface(icon, 8)
    if mask.count() <= 0:
        return None

    ghost = pygame.Surface((size, size), pygame.SRCALPHA)
    highlight = mask.to_surface(setcolor=(204, 208, 220, 76), unsetcolor=(0, 0, 0, 0))
    shadow = mask.to_surface(setcolor=(20, 22, 28, 156), unsetcolor=(0, 0, 0, 0))
    fill = mask.to_surface(setcolor=(128, 132, 146, 226), unsetcolor=(0, 0, 0, 0))
    ghost.blit(highlight, (-1, -1))
    ghost.blit(shadow, (1, 1))
    ghost.blit(fill, (0, 0))
    return ghost


def _build_belt_slot_icon(size: int) -> Optional[pygame.Surface]:
    sheet = get_arbitrary_sheet("assets/rogues.png")
    if not isinstance(sheet, pygame.Surface):
        return None

    tile_size = 32
    tile = pygame.Surface((tile_size, tile_size), pygame.SRCALPHA)
    tile.blit(sheet, (0, 0), pygame.Rect(tile_size, tile_size * 3, tile_size, tile_size))

    source_band = pygame.Surface((16, 3), pygame.SRCALPHA)
    source_band.blit(tile, (0, 0), pygame.Rect(8, 15, 16, 3))

    band_w = max(22, int(size * 1.02))
    band_h = max(5, int(size * 0.22))
    scaled_band = pygame.transform.scale(source_band, (band_w, band_h))

    shadow = (48, 48, 58, 255)
    fill = (148, 148, 162, 255)
    hilite = (200, 200, 216, 255)

    mono_band = pygame.Surface((band_w, band_h), pygame.SRCALPHA)
    band_shadow = pygame.Surface((band_w, band_h), pygame.SRCALPHA)
    for y in range(band_h):
        for x in range(band_w):
            px = scaled_band.get_at((x, y))
            if px.a <= 12:
                continue
            lum = (0.299 * px.r) + (0.587 * px.g) + (0.114 * px.b)
            col = hilite if lum >= 170.0 else (fill if lum >= 85.0 else shadow)
            mono_band.set_at((x, y), col)
            band_shadow.set_at((x, y), shadow)

    icon = pygame.Surface((size, size), pygame.SRCALPHA)
    band_x = (size - band_w) // 2
    band_y = max(4, (size - band_h) // 2 - 1)
    icon.blit(band_shadow, (band_x + 1, band_y + 1))
    icon.blit(mono_band, (band_x, band_y))

    plate_w = max(8, size // 3)
    plate_h = max(7, size // 4)
    plate = pygame.Rect(
        (size - plate_w) // 2,
        band_y + (band_h // 2) - (plate_h // 2),
        plate_w,
        plate_h,
    )
    pygame.draw.rect(icon, shadow, plate.move(1, 1), border_radius=2)
    pygame.draw.rect(icon, fill, plate, border_radius=2)
    pygame.draw.rect(icon, hilite, plate, 1, border_radius=2)

    inner = plate.inflate(-max(4, plate.width // 3), -max(3, plate.height // 3))
    if inner.width > 2 and inner.height > 2:
        pygame.draw.rect(icon, shadow, inner, 1, border_radius=1)

    clasp_x = plate.left + max(2, plate.width // 3)
    pygame.draw.line(icon, hilite, (clasp_x, plate.top + 1), (clasp_x, plate.bottom - 2), 1)
    pygame.draw.line(icon, fill, (clasp_x, plate.centery), (plate.right - 2, plate.centery), 1)

    gem = pygame.Rect(plate.centerx - 1, plate.centery - 1, 3, 3)
    pygame.draw.rect(icon, hilite, gem, border_radius=1)

    tassel_h = max(3, size // 8)
    tassel = pygame.Rect(plate.centerx - 1, plate.bottom - 1, 2, tassel_h)
    pygame.draw.rect(icon, shadow, tassel.move(1, 1), border_radius=1)
    pygame.draw.rect(icon, fill, tassel, border_radius=1)

    hole_y = band_y + (band_h // 2)
    for hole_x in (plate.right + 3, plate.right + 6):
        if hole_x < band_x + band_w - 2:
            icon.set_at((hole_x, hole_y), shadow)
            if hole_y + 1 < size:
                icon.set_at((hole_x, hole_y + 1), shadow)
    return icon


def get_slot_icon(slot: str, size: int) -> pygame.Surface:
    """Return a pixel-art silhouette for an equipment slot type.
    Built from a 16x16 template and scaled to `size`. Cached."""
    key = (slot, size)
    if key in _SLOT_ICON_CACHE:
        return _SLOT_ICON_CACHE[key]

    if slot == "belt":
        belt_icon = _build_belt_slot_icon(size)
        if isinstance(belt_icon, pygame.Surface):
            _SLOT_ICON_CACHE[key] = belt_icon
            return belt_icon

    ghost_icon = _build_slot_ghost_icon(slot, size)
    if isinstance(ghost_icon, pygame.Surface):
        _SLOT_ICON_CACHE[key] = ghost_icon
        return ghost_icon

    template = _SLOT_PIXEL_ART.get(slot)
    if template is None:
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.rect(surf, (110, 110, 125),
                         (size // 4, size // 4, size // 2, size // 2), 2)
        _SLOT_ICON_CACHE[key] = surf
        return surf

    # Colors — soft grey palette so they read as "empty slot hint"
    shadow = (48, 48, 58, 255)
    fill   = (148, 148, 162, 255)
    hilite = (200, 200, 216, 255)
    palette = {".": shadow, "#": fill, "+": hilite}

    # Draw onto a 16x16 base, then scale to target with nearest-neighbor
    # so the pixel art stays crisp.
    base = pygame.Surface((16, 16), pygame.SRCALPHA)
    for py, row in enumerate(template):
        for px, ch in enumerate(row[:16]):
            col = palette.get(ch)
            if col is not None:
                base.set_at((px, py), col)

    surf = pygame.transform.scale(base, (size, size))
    _SLOT_ICON_CACHE[key] = surf
    return surf


def draw_ui_slot(surface: pygame.Surface, rect: pygame.Rect, selected: bool = False, hovered: bool = False, blocked: bool = False) -> None:
    slot_img = UI_ASSETS.get("slot")
    if slot_img:
        surface.blit(pygame.transform.scale(slot_img, (rect.width, rect.height)), rect)
        if blocked and "slot_locked" in UI_ASSETS:
            surface.blit(pygame.transform.scale(UI_ASSETS["slot_locked"], (rect.width, rect.height)), rect)
        elif (selected or hovered) and "slot_select" in UI_ASSETS:
            surface.blit(pygame.transform.scale(UI_ASSETS["slot_select"], (rect.width, rect.height)), rect)
        elif blocked:
            s = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
            s.fill((100, 20, 20, 120))
            surface.blit(s, rect)
        elif selected or hovered:
            # Fallback highlight if image missing
            pygame.draw.rect(surface, (220, 200, 120), rect, 2, border_radius=4)
    else:
        fill = (50, 44, 40) if selected else (30, 30, 34)
        if blocked: fill = (40, 20, 20)
        pygame.draw.rect(surface, fill, rect, border_radius=8)
        border_col = (180, 150, 80) if selected else ((224, 196, 118) if hovered else (80, 80, 90))
        pygame.draw.rect(surface, border_col, rect, 2, border_radius=8)


def draw_empty_equipment_slot(
    surface: pygame.Surface,
    rect: pygame.Rect,
    slot: str,
    hovered: bool = False,
) -> None:
    draw_ui_slot(surface, rect, hovered=hovered)

    inner = rect.inflate(-14, -14)
    inner_surf = pygame.Surface((inner.width, inner.height), pygame.SRCALPHA)
    inner_fill = (16, 18, 24, 126) if hovered else (12, 14, 20, 98)
    inner_border = (144, 128, 92, 84) if hovered else (92, 96, 112, 64)
    pygame.draw.rect(inner_surf, inner_fill, inner_surf.get_rect(), border_radius=7)
    pygame.draw.rect(inner_surf, inner_border, inner_surf.get_rect(), 1, border_radius=7)
    surface.blit(inner_surf, inner)

    icon_sz = max(20, rect.width - (10 if hovered else 12))
    slot_icon = get_slot_icon(slot, icon_sz)
    icon_rect = slot_icon.get_rect(center=rect.center)
    surface.blit(slot_icon, icon_rect)


_UI_PANEL_IMG: Optional[pygame.Surface] = None

def get_ui_panel_img() -> pygame.Surface | None:
    global _UI_PANEL_IMG
    if _UI_PANEL_IMG is None:
        if "panel" in UI_ASSETS:
            _UI_PANEL_IMG = UI_ASSETS["panel"]
        else:
            try:
                _UI_PANEL_IMG = pygame.image.load("assets/ui.png").convert_alpha()
            except (pygame.error, FileNotFoundError):
                pass
    return _UI_PANEL_IMG




def make_fallback_icon(color: Tuple[int, int, int]) -> pygame.Surface:
    surf = pygame.Surface((64, 64), pygame.SRCALPHA)
    pygame.draw.rect(surf, color, (4, 4, 56, 56), border_radius=8)
    pygame.draw.rect(surf, (200, 200, 200), (4, 4, 56, 56), 2, border_radius=8)
    return surf


def _draw_passive_glyph(
    surface: pygame.Surface,
    glyph: str,
    fill: Tuple[int, int, int],
    line: Tuple[int, int, int],
) -> None:
    w, h = surface.get_size()
    cx = w // 2
    cy = h // 2
    r = max(6, int(min(w, h) * 0.30))
    g = str(glyph).strip().lower()

    if g == "dagger":
        blade = [(cx, cy - r - 6), (cx + 7, cy - 2), (cx, cy + 4), (cx - 7, cy - 2)]
        pygame.draw.polygon(surface, fill, blade)
        pygame.draw.polygon(surface, line, blade, 2)
        guard = pygame.Rect(cx - 13, cy + 4, 26, 6)
        pygame.draw.rect(surface, fill, guard, border_radius=3)
        pygame.draw.rect(surface, line, guard, 2, border_radius=3)
        handle = pygame.Rect(cx - 4, cy + 10, 8, r + 2)
        pygame.draw.rect(surface, fill, handle, border_radius=3)
        pygame.draw.rect(surface, line, handle, 2, border_radius=3)
        return

    if g == "arrow":
        shaft_top = cy - r + 4
        shaft_bot = cy + r + 8
        pygame.draw.line(surface, fill, (cx, shaft_bot), (cx, shaft_top), 5)
        pygame.draw.line(surface, line, (cx, shaft_bot), (cx, shaft_top), 2)
        head = [(cx, cy - r - 10), (cx + 12, cy - r + 4), (cx - 12, cy - r + 4)]
        pygame.draw.polygon(surface, fill, head)
        pygame.draw.polygon(surface, line, head, 2)
        pygame.draw.line(surface, line, (cx - 10, cy + r - 2), (cx, cy + r + 10), 2)
        pygame.draw.line(surface, line, (cx + 10, cy + r - 2), (cx, cy + r + 10), 2)
        return

    if g == "skull":
        pygame.draw.circle(surface, fill, (cx, cy - 2), r)
        pygame.draw.circle(surface, line, (cx, cy - 2), r, 2)
        jaw = pygame.Rect(cx - int(r * 0.65), cy + int(r * 0.15), int(r * 1.3), int(r * 0.9))
        pygame.draw.rect(surface, fill, jaw, border_radius=6)
        pygame.draw.rect(surface, line, jaw, 2, border_radius=6)
        eye_r = max(2, r // 5)
        pygame.draw.circle(surface, (18, 14, 24), (cx - eye_r - 3, cy - 2), eye_r)
        pygame.draw.circle(surface, (18, 14, 24), (cx + eye_r + 3, cy - 2), eye_r)
        return

    if g == "shield":
        top = cy - r - 4
        shield_pts = [
            (cx, top),
            (cx + r, cy - r // 2),
            (cx + r - 4, cy + r // 2),
            (cx, cy + r + 10),
            (cx - r + 4, cy + r // 2),
            (cx - r, cy - r // 2),
        ]
        pygame.draw.polygon(surface, fill, shield_pts)
        pygame.draw.polygon(surface, line, shield_pts, 2)
        pygame.draw.line(surface, line, (cx, top + 5), (cx, cy + r + 5), 2)
        return

    if g == "sun":
        pygame.draw.circle(surface, fill, (cx, cy), r - 5)
        pygame.draw.circle(surface, line, (cx, cy), r - 5, 2)
        for i in range(8):
            ang = (math.tau * i) / 8.0
            inner = Vector2(cx, cy) + Vector2(math.cos(ang), math.sin(ang)) * (r - 1)
            outer = Vector2(cx, cy) + Vector2(math.cos(ang), math.sin(ang)) * (r + 8)
            pygame.draw.line(surface, line, inner, outer, 2)
        return

    # Default: rune star.
    points: List[Tuple[int, int]] = []
    for i in range(10):
        ang = -math.pi / 2.0 + i * (math.tau / 10.0)
        rr = r + 4 if i % 2 == 0 else max(4, int(r * 0.45))
        points.append((int(cx + math.cos(ang) * rr), int(cy + math.sin(ang) * rr)))
    pygame.draw.polygon(surface, fill, points)
    pygame.draw.polygon(surface, line, points, 2)


def build_class_passive_icon(class_id: str, size: int = 64) -> pygame.Surface:
    sid = normalize_class_id(class_id)
    icon_size = max(28, int(size))
    cache_key = (sid, icon_size)
    cached = _PASSIVE_ICON_CACHE.get(cache_key)
    if isinstance(cached, pygame.Surface):
        return cached

    passive = class_passive_data(sid)
    colors_raw = passive.get("icon_colors")
    colors = colors_raw if isinstance(colors_raw, dict) else {}
    base = colors.get("base") if isinstance(colors.get("base"), tuple) else (60, 62, 74)
    accent = colors.get("accent") if isinstance(colors.get("accent"), tuple) else (186, 190, 214)
    line = colors.get("line") if isinstance(colors.get("line"), tuple) else (236, 240, 252)

    surf = pygame.Surface((icon_size, icon_size), pygame.SRCALPHA)
    cx = icon_size // 2
    cy = icon_size // 2
    outer = max(10, icon_size // 2 - 3)
    inner = max(6, outer - max(3, icon_size // 11))

    for i in range(5):
        t = i / 4.0
        col = color_lerp(base, (16, 16, 22), t * 0.55)
        rad = outer - i
        pygame.gfxdraw.filled_circle(surf, cx, cy, rad, (*col, 255))
    pygame.gfxdraw.aacircle(surf, cx, cy, outer, (*accent, 220))
    pygame.gfxdraw.aacircle(surf, cx, cy, max(2, inner), (*line, 160))
    pygame.draw.circle(surf, (*accent, 70), (cx, cy), inner + 1, 2)

    glyph_layer = pygame.Surface((icon_size, icon_size), pygame.SRCALPHA)
    _draw_passive_glyph(glyph_layer, str(passive.get("glyph", "star")), accent, line)
    surf.blit(glyph_layer, (0, 0))

    _PASSIVE_ICON_CACHE[cache_key] = surf
    return surf


def load_spell_icons() -> Dict[str, pygame.Surface]:
    icons: Dict[str, pygame.Surface] = {}
    for spell_id, path in SPELL_ICON_FILES.items():
        if os.path.exists(path):
            try:
                loaded = pygame.image.load(path).convert_alpha()
                if loaded.get_width() != 64 or loaded.get_height() != 64:
                    loaded = pygame.transform.smoothscale(loaded, (64, 64))
                icons[spell_id] = loaded
            except pygame.error:
                pass
    sheets: Dict[str, pygame.Surface] = {}
    for sheet_id, path in SPELL_ICON_SHEETS.items():
        if os.path.exists(path):
            try:
                sheets[sheet_id] = pygame.image.load(path).convert_alpha()
            except pygame.error:
                pass
    for spell_id, _entry in SPELL_ICON_SOURCES.items():
        if spell_id in icons:
            continue
        _sheet_id, _row, _col = _entry[0], _entry[1], _entry[2]
        _src_px = _entry[3] if len(_entry) > 3 else 32
        _sheet = sheets.get(_sheet_id)
        if _sheet:
            _rect = pygame.Rect(_col * 32, _row * 32, _src_px, _src_px)
            _tile = pygame.Surface((_src_px, _src_px), pygame.SRCALPHA)
            _tile.blit(_sheet, (0, 0), _rect)
            icons[spell_id] = pygame.transform.smoothscale(_tile, (64, 64))
    for class_id in CLASS_ORDER:
        icons[f"passive_{class_id}"] = build_class_passive_icon(class_id, 64)
    return icons


def draw_ornate_panel(surface: pygame.Surface, rect: pygame.Rect) -> None:
    img = get_ui_panel_img()
    if img:
        draw_nine_slice(surface, img, rect, corner=24)
    else:
        draw_ornate_panel_backup(surface, rect)


def draw_ornate_panel_backup(surface: pygame.Surface, rect: pygame.Rect) -> None:
    """Draws a Steam-like ornate panel background (Backup)."""
    pygame.draw.rect(surface, (20, 22, 26), rect, border_radius=6)
    pygame.draw.rect(surface, (30, 32, 38), rect.inflate(-4, -4), border_radius=6)
    inner = rect.inflate(-8, -8)
    pygame.draw.rect(surface, (14, 14, 18), inner, border_radius=4)
    pygame.draw.rect(surface, (100, 84, 50), rect, 1, border_radius=6)
    pygame.draw.rect(surface, (180, 150, 80), rect.inflate(-2, -2), 1, border_radius=6)
    corner_len = 12
    corner_col = (220, 190, 110)
    for x, y in [(rect.left, rect.top), (rect.right - 1, rect.top), (rect.left, rect.bottom - 1), (rect.right - 1, rect.bottom - 1)]:
        dx = 1 if x == rect.left else -1
        dy = 1 if y == rect.top else -1
        pygame.draw.line(surface, corner_col, (x, y), (x + dx * corner_len, y), 2)
        pygame.draw.line(surface, corner_col, (x, y), (x, y + dy * corner_len), 2)
        pygame.draw.circle(surface, corner_col, (x, y), 2)


def draw_ui_tab(surface: pygame.Surface, rect: pygame.Rect, active: bool = False, text: str = "", font: Optional[pygame.font.Font] = None, color: Tuple[int,int,int]=(200,200,200)) -> None:
    img = UI_ASSETS.get("tab_active" if active else "tab")
    if img:
        draw_nine_slice(surface, img, rect, corner=8)
    else:
        bg = (52, 48, 36) if active else (32, 32, 38)
        border = (200, 170, 80) if active else (80, 80, 90)
        pygame.draw.rect(surface, bg, rect, border_radius=6)
        pygame.draw.rect(surface, border, rect, 1, border_radius=6)
    
    if text and font:
        ts = font.render(text, True, (230, 220, 180) if active else (160, 155, 140))
        surface.blit(ts, (rect.centerx - ts.get_width() // 2, rect.centery - ts.get_height() // 2))


def draw_ui_button(surface: pygame.Surface, rect: pygame.Rect, hovered: bool = False, text: str = "", font: Optional[pygame.font.Font] = None, color: Tuple[int,int,int]=(200,200,200)) -> None:
    img = UI_ASSETS.get("button_hover" if hovered else "button")
    if img:
        draw_nine_slice(surface, img, rect, corner=8)
    else:
        bg = (52, 48, 36) if hovered else (32, 32, 38)
        border = (220, 190, 100) if hovered else (100, 96, 80)
        pygame.draw.rect(surface, bg, rect, border_radius=6)
        pygame.draw.rect(surface, border, rect, 1, border_radius=6)

    if text and font:
        ts = font.render(text, True, color)
        surface.blit(ts, (rect.centerx - ts.get_width() // 2, rect.centery - ts.get_height() // 2))
