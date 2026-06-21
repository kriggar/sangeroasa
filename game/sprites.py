"""game/sprites.py — sprite/anim frame helpers, class-visual loaders,
directional/LPC spritesheet handling, palette recolour & equipped-sprite building,
and basic movement/pathing helpers."""
import os
import math
import random
import colorsys
from typing import Dict, List, Optional, Tuple, Any, Union, Set

import pygame
from pygame import Vector2

from game.constants import *
from game.utils import *
from game.nav import *
from game.vfx import *
from game.gameplay_math import *
from game.data.classes import *
from game.data.icons import *
from game.data.items_data import *
from game.items import *

__all__ = [
    'get_facing_sprite',
    'actor_world_rect',
    'palette_swap_hsl',
    '_CHROMAKEY_SLOTS',
    '_SPRITE_HUE_CACHE',
    'detect_sprite_armor_hue',
    '_item_color_hue',
    '_is_skin_pixel',
    '_is_metal_pixel',
    '_find_cloth_hues',
    '_CLOTH_HUE_CACHE',
    '_recolor_region',
    '_add_contour',
    '_dominant_color_from_icon',
    '_resolve_item_visual_color',
    'build_equipped_sprite',
    'build_equip_tint_overlay',
    '_deep_copy_anim_frames',
    'build_equipped_anim_frames',
    'LPC_FRAME_W',
    'LPC_FRAME_H',
    'LPC_ANIMS',
    'LPC_DIRS',
    'WOLF_ANIMS',
    '_build_anim_frames',
    'build_sprite_idle_cycle',
    'cardinal_anim_direction',
    'warrior_visual_tier_for_level',
    'load_directional_sprite_rows',
    'load_warrior_class_visuals',
    'resolve_class_visual_entry',
    'load_lpc_spritesheet',
    'load_wolf_spritesheet',
    'get_lpc_frame',
    'get_directional_anim_frame',
    'load_resource_bar_assets',
    'move_with_collision',
    'find_path_astar',
]


def get_facing_sprite(
    facing: int,
    sprite_right: pygame.Surface,
    sprite_left: pygame.Surface,
) -> pygame.Surface:
    # Source sheet orientation is opposite of our facing semantic,
    # so facing-right uses the flipped sprite.
    return sprite_left if facing >= 0 else sprite_right


def actor_world_rect(
    position: Vector2,
    facing: int,
    sprite_right: pygame.Surface,
    sprite_left: pygame.Surface,
) -> pygame.Rect:
    sprite = get_facing_sprite(facing, sprite_right, sprite_left)
    return sprite.get_rect(midbottom=(int(position.x), int(position.y) + 2))


def palette_swap_hsl(
    surf: pygame.Surface,
    src_hue_min: float,
    src_hue_max: float,
    dst_hue: float,
    sat_min: float = 0.12,
    sat_max: float = 1.0,
    light_min: float = 0.18,
    light_max: float = 0.80,
    dst_sat_scale: float = 1.0,
    dst_val_scale: float = 1.0,
    clip_rect: Optional[pygame.Rect] = None,
) -> pygame.Surface:
    """Return a copy of surf with pixels whose HSV hue falls in [src_hue_min, src_hue_max]
    recolored to dst_hue. clip_rect restricts which pixels are eligible (for per-slot regions)."""
    import colorsys
    result = surf.copy()
    w, h = surf.get_size()
    dst_h_norm = (dst_hue % 360.0) / 360.0
    src_lo = src_hue_min / 360.0
    src_hi = src_hue_max / 360.0
    x0 = clip_rect.left   if clip_rect else 0
    x1 = clip_rect.right  if clip_rect else w
    y0 = clip_rect.top    if clip_rect else 0
    y1 = clip_rect.bottom if clip_rect else h
    for py in range(max(0, y0), min(h, y1)):
        for px in range(max(0, x0), min(w, x1)):
            r, g, b, a = surf.get_at((px, py))
            if a < 10:
                continue
            hue, sat, val = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
            light = (max(r, g, b) + min(r, g, b)) / 510.0
            if not (src_lo <= hue <= src_hi):
                continue
            if not (sat_min <= sat <= sat_max):
                continue
            if not (light_min <= light <= light_max):
                continue
            nr, ng, nb = colorsys.hsv_to_rgb(
                dst_h_norm,
                min(1.0, sat * dst_sat_scale),
                min(1.0, val * dst_val_scale),
            )
            result.set_at((px, py), (int(nr * 255), int(ng * 255), int(nb * 255), a))
    return result


# ── Chromakey equipment system ──────────────────────────────────────────────
# Each slot: list of (region, match_mode) pairs
#   region     = (x_frac, y_frac, w_frac, h_frac)
#   match_mode:
#     "skin"     → only recolor skin-tone pixels (for gloves/bracers)
#     "non_skin" → recolor everything EXCEPT skin (for armor over clothes)
#     "all"      → recolor all opaque pixels
# Each slot: list of (region, match_mode) pairs.
# match_mode: "skin", "non_skin", "all", "dominant", "secondary"
# "dominant"  → only recolor pixels matching the sprite's most-common cloth hue (hood/cloak)
# "secondary" → only recolor pixels matching the sprite's 2nd-most-common cloth hue (robe)
_CHROMAKEY_SLOTS: Dict[str, List[Tuple[Tuple[float, float, float, float], str]]] = {
    # Hood: full top 45%, matched by hood-hue (sampled from the top strip of
    # the sprite) so face pixels (eyes/nose/mouth — different hues) stay intact.
    "head":    [((0.00, 0.00, 1.00, 0.45), "hood")],
    "chest":   [((0.00, 0.34, 1.00, 0.58), "chest")],     # full torso — matched by chest hue
    "pants":   [((0.24, 0.66, 0.52, 0.16), "pants")],
    "hands":   [((0.0, 0.34, 0.38, 0.54), "skin"),
                ((0.66, 0.55, 0.34, 0.25), "skin")],
    "belt":    [((0.25, 0.58, 0.55, 0.08), "non_skin")],
    "feet":    [((0.25, 0.82, 0.55, 0.18), "all")],
    # Held/worn items — regions kept strictly BELOW the head (y >= 0.46)
    # so they can never overwrite hood pixels.
    "weapon":  [((0.00, 0.50, 0.35, 0.40), "non_skin")],   # left-hand side (player's right)
    "offhand": [((0.65, 0.50, 0.35, 0.40), "non_skin")],   # right-hand side (player's left)
    "amulet":  [((0.32, 0.46, 0.36, 0.10), "non_skin")],   # neckline, just under head
    "ring":    [((0.05, 0.62, 0.28, 0.22), "skin"),        # hand areas (tiny metal on skin)
                ((0.67, 0.62, 0.28, 0.22), "skin")],
}


# Each recipe: (src_hue_min, src_hue_max, dst_hue, sat_min, light_min, light_max,
#                dst_sat_scale, dst_val_scale)
# Cache: id(surface) → (center_hue_deg, spread_deg)
_SPRITE_HUE_CACHE: Dict[int, Tuple[float, float]] = {}


def detect_sprite_armor_hue(surf: pygame.Surface) -> Tuple[float, float]:
    """Return (center_hue_deg, spread_deg) of the dominant cloth/armor color in the sprite.
    Excludes transparent pixels, near-grey pixels, and warm skin tones.
    Result is cached by surface id so repeated calls are free."""
    import colorsys
    sid = id(surf)
    if sid in _SPRITE_HUE_CACHE:
        return _SPRITE_HUE_CACHE[sid]

    bins: Dict[int, int] = {}
    for py in range(surf.get_height()):
        for px in range(surf.get_width()):
            r, g, b, a = surf.get_at((px, py))
            if a < 10:
                continue
            h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
            if s < 0.14:
                continue  # too grey / washed out
            hue_deg = h * 360.0
            light = (max(r, g, b) + min(r, g, b)) / 510.0
            # Skip warm skin tones (red-orange hue + relatively bright)
            if hue_deg <= 34.0 and light >= 0.46:
                continue
            key = int(hue_deg / 5) * 5
            bins[key] = bins.get(key, 0) + 1

    if not bins:
        _SPRITE_HUE_CACHE[sid] = (-1.0, 0.0)
        return -1.0, 0.0

    peak = float(max(bins, key=bins.get)) + 2.5  # centre of dominant 5° bin
    _SPRITE_HUE_CACHE[sid] = (peak, 28.0)
    return peak, 28.0


def _item_color_hue(item: Dict[str, object]) -> float:
    """Return the hue (0-360°) that represents this item's visual color.
    Uses _resolve_item_visual_color for consistent color lookup.
    Returns -1.0 for grey items (no swap)."""
    import colorsys
    r, g, b = _resolve_item_visual_color(item)
    h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
    if s < 0.10:
        return -1.0  # grey — no meaningful hue, skip swap
    return h * 360.0


def _is_skin_pixel(r: int, g: int, b: int) -> bool:
    """Return True if (r,g,b) looks like a skin-tone pixel in pixel-art sprites.
    Matches warm hues (0-40°) with some saturation, including darker skin shades."""
    import colorsys
    h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
    hue_deg = h * 360.0
    light = (max(r, g, b) + min(r, g, b)) / 510.0
    return hue_deg <= 40.0 and s >= 0.08 and light >= 0.22


def _is_metal_pixel(r: int, g: int, b: int) -> bool:
    """Return True for neutral metal pixels used by blades, buckles, and trims."""
    import colorsys
    if _is_skin_pixel(r, g, b):
        return False
    h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
    hue_deg = h * 360.0
    delta = max(abs(r - g), abs(g - b), abs(r - b))
    if v < 0.18:
        return False
    if s <= 0.24 and delta <= 48 and max(r, g, b) >= 64:
        return True
    if 185.0 <= hue_deg <= 250.0 and s <= 0.38 and v >= 0.24 and delta <= 92:
        return True
    return False


def _find_cloth_hues(surf: pygame.Surface) -> Tuple[Optional[float], Optional[float]]:
    """Find the two dominant non-skin cloth hues in a sprite.
    Returns (dominant_hue_deg, secondary_hue_deg) or None for missing."""
    import colorsys
    bins: Dict[int, int] = {}  # hue_bin(10°) → pixel count
    for py in range(surf.get_height()):
        for px in range(surf.get_width()):
            r, g, b, a = surf.get_at((px, py))
            if a < 20:
                continue
            if _is_skin_pixel(r, g, b):
                continue
            h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
            if s < 0.08:
                continue  # skip greys
            hue_deg = h * 360.0
            key = int(hue_deg / 20) * 20  # 20° bins
            bins[key] = bins.get(key, 0) + 1
    if not bins:
        return None, None
    sorted_bins = sorted(bins.items(), key=lambda x: -x[1])
    dom_hue = float(sorted_bins[0][0]) + 10.0  # center of bin
    sec_hue = None
    # Find second hue at least 40° away from dominant
    for hue_bin, count in sorted_bins[1:]:
        candidate = float(hue_bin) + 10.0
        diff = abs(candidate - dom_hue)
        if diff > 180:
            diff = 360 - diff
        if diff >= 40:
            sec_hue = candidate
            break
    return dom_hue, sec_hue


# Cache: id(surface) → (dominant_hue, secondary_hue)
_CLOTH_HUE_CACHE: Dict[int, Tuple[Optional[float], Optional[float]]] = {}


def _recolor_region(
    surf: pygame.Surface,
    region: Tuple[float, float, float, float],
    target_rgb: Tuple[int, int, int],
    match_mode: str = "skin",
    base_surf: Optional["pygame.Surface"] = None,
) -> set:
    """Recolor pixels within a fractional region of *surf* in-place.
    match_mode: 'skin' = only skin pixels, 'non_skin' = opaque non-skin,
                'all' = all opaque, 'dominant' = dominant cloth hue,
                'secondary' = secondary cloth hue,
                'hood' = pixels matching the hood hue sampled from the top of
                         the sprite (skips eyes/nose/mouth which have different hues).
    Returns set of (x, y) tuples that were recolored."""
    import colorsys
    sw, sh = surf.get_size()
    xf, yf, wf, hf = region
    x0 = int(xf * sw)
    y0 = int(yf * sh)
    x1 = min(sw, x0 + max(1, int(wf * sw)))
    y1 = min(sh, y0 + max(1, int(hf * sh)))
    ref = base_surf if base_surf is not None else surf

    # For dominant/secondary modes, detect cloth hues from the base (unmodified) surface
    hue_target: Optional[float] = None
    hue_tolerance = 30.0  # ±30° match window
    if match_mode in ("dominant", "secondary"):
        sid = id(ref)
        if sid not in _CLOTH_HUE_CACHE:
            _CLOTH_HUE_CACHE[sid] = _find_cloth_hues(ref)
        dom, sec = _CLOTH_HUE_CACHE[sid]
        hue_target = dom if match_mode == "dominant" else sec
        if hue_target is None:
            return set()
    elif match_mode in ("hood", "chest", "pants"):
        # Sample the garment hue from a slot-specific sub-area of the BASE
        # sprite, then match that hue across the region. Face/hood/body/etc.
        # have different hues so each stays contained.
        if match_mode == "hood":
            sx0, sy0, sx1, sy1 = 0, 0, sw, max(1, int(0.18 * sh))
        else:  # chest — sample center torso
            sx0 = int(0.30 * sw)
            sx1 = int(0.70 * sw)
            sy0 = int(0.55 * sh)
            sy1 = int(0.72 * sh)
        if match_mode == "pants":
            sx0 = int(0.28 * sw)
            sx1 = int(0.72 * sw)
            sy0 = int(0.68 * sh)
            sy1 = int(0.82 * sh)
        bins: Dict[int, int] = {}
        for sy in range(sy0, sy1):
            for sx in range(sx0, sx1):
                r, g, b, a = ref.get_at((sx, sy))
                if a < 20:
                    continue
                if _is_skin_pixel(r, g, b):
                    continue
                hh, ss, vv = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
                if ss < 0.08:
                    continue  # skip greys/blacks — can't hue-match reliably
                key = int((hh * 360.0) / 10) * 10
                bins[key] = bins.get(key, 0) + 1
        if not bins:
            return set()
        hue_target = float(max(bins, key=bins.get)) + 5.0  # center of 10° bin
        hue_tolerance = 28.0

    # Convert target color to HSV so we can transfer its hue/sat while
    # preserving each original pixel's value (lightness). This is a palette
    # swap — lines, highlights, and shadows are preserved.
    th, ts, tv = colorsys.rgb_to_hsv(target_rgb[0] / 255.0, target_rgb[1] / 255.0, target_rgb[2] / 255.0)

    changed: set = set()
    for py in range(y0, y1):
        for px in range(x0, x1):
            ref_r, ref_g, ref_b, ref_a = ref.get_at((px, py))
            if ref_a < 20:
                continue
            r, g, b, a = surf.get_at((px, py))
            if a < 20:
                continue
            if match_mode == "skin":
                if not _is_skin_pixel(ref_r, ref_g, ref_b):
                    continue
            elif match_mode == "non_skin":
                if _is_skin_pixel(ref_r, ref_g, ref_b):
                    continue
            elif match_mode == "metal":
                if not _is_metal_pixel(ref_r, ref_g, ref_b):
                    continue
            elif match_mode in ("dominant", "secondary", "hood", "chest", "pants"):
                if _is_skin_pixel(ref_r, ref_g, ref_b):
                    continue
                h, s, v = colorsys.rgb_to_hsv(ref_r / 255.0, ref_g / 255.0, ref_b / 255.0)
                if s < 0.08:
                    continue  # skip greys/blacks
                px_hue = h * 360.0
                diff = abs(px_hue - hue_target)
                if diff > 180:
                    diff = 360 - diff
                if diff > hue_tolerance:
                    continue
            # match_mode == "all" falls through — no filtering

            # Palette swap: replace hue + saturation with target, preserve value.
            # This keeps the original pixel's shading/highlight/shadow lines.
            _h, _s, _v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
            nr, ng, nb = colorsys.hsv_to_rgb(th, ts, _v)
            surf.set_at((px, py), (int(nr * 255), int(ng * 255), int(nb * 255), a))
            changed.add((px, py))
    return changed


def _add_contour(surf: pygame.Surface, changed: set) -> None:
    """Add a 1px dark contour around recolored pixels.
    Any recolored pixel that borders a transparent or non-recolored pixel
    gets darkened to create a clean outline."""
    if not changed:
        return
    sw, sh = surf.get_size()
    edge_pixels: list = []
    for (px, py) in changed:
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nx, ny = px + dx, py + dy
            if nx < 0 or nx >= sw or ny < 0 or ny >= sh:
                edge_pixels.append((px, py))
                break
            if (nx, ny) not in changed:
                na = surf.get_at((nx, ny))[3]
                if na < 20:
                    edge_pixels.append((px, py))
                    break
    # Only apply contour if edge pixels are a minority of the recolored area.
    # On tiny features (hoods, small armor pieces), almost every pixel is an edge
    # and darkening them all would obliterate the color.
    if len(edge_pixels) > len(changed) * 0.6:
        return
    for (px, py) in edge_pixels:
        r, g, b, a = surf.get_at((px, py))
        # Darken to ~55% brightness for contour
        surf.set_at((px, py), (max(0, r * 55 // 100), max(0, g * 55 // 100), max(0, b * 55 // 100), a))


def _dominant_color_from_icon(item: Dict[str, object]) -> Optional[Tuple[int, int, int]]:
    """Extract the dominant color from an item's icon surface."""
    import colorsys
    raw_path = item.get("icon_path")
    raw_sheet = item.get("icon_sheet")
    raw_tile = item.get("icon_tile")
    raw_icon = item.get("icon")
    has_explicit_icon = (
        (isinstance(raw_path, str) and bool(raw_path))
        or (isinstance(raw_sheet, str) and isinstance(raw_tile, (tuple, list)) and len(raw_tile) == 2)
        or (isinstance(raw_icon, (tuple, list)) and len(raw_icon) == 2)
    )
    if not has_explicit_icon:
        return None
    icon = resolve_item_icon(item, 36)
    if not isinstance(icon, pygame.Surface):
        return None
    bins: Dict[int, Tuple[int, int, int, int]] = {}  # hue_bin → (total_r, total_g, total_b, count)
    for py in range(icon.get_height()):
        for px in range(icon.get_width()):
            r, g, b, a = icon.get_at((px, py))
            if a < 30:
                continue
            h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
            if s < 0.12 or v < 0.12:
                continue  # skip greys and near-black
            key = int((h * 360) / 20) * 20
            tr, tg, tb, tc = bins.get(key, (0, 0, 0, 0))
            bins[key] = (tr + r, tg + g, tb + b, tc + 1)
    if not bins:
        return None
    # Pick the bin with most pixels
    best_bin = max(bins.values(), key=lambda x: x[3])
    tr, tg, tb, tc = best_bin
    return (tr // tc, tg // tc, tb // tc)


def _resolve_item_visual_color(item: Dict[str, object]) -> Tuple[int, int, int]:
    """Get the visual recoloring color for an equipment item.
    Priority: icon dominant color → item 'color' field → CLASS_ARMOR_SETS → hue → rarity."""
    # 1) Dominant color from the item's icon
    icon_color = _dominant_color_from_icon(item)
    if icon_color is not None:
        return icon_color

    # 2) Item's own color field
    own_color = item.get("color")
    if isinstance(own_color, (tuple, list)) and len(own_color) >= 3:
        c = (int(own_color[0]), int(own_color[1]), int(own_color[2]))
        rarity_col = item_rarity_border(item)
        if c != rarity_col:
            return c

    # 3) Look up from CLASS_ARMOR_SETS by set_name + slot
    set_name = item.get("set_name", "")
    equip_slot = str(item.get("equip_slot", "")).strip().lower()
    if set_name and equip_slot:
        for _cls_id, _set_data in CLASS_ARMOR_SETS.items():
            if _set_data.get("set_name") == set_name:
                for _piece in _set_data.get("pieces", []):
                    if isinstance(_piece, dict) and _piece.get("slot") == equip_slot:
                        pc = _piece.get("color")
                        if isinstance(pc, (tuple, list)) and len(pc) >= 3:
                            return (int(pc[0]), int(pc[1]), int(pc[2]))
                break

    # 4) Hue from external sprite analysis
    if "hue" in item:
        import colorsys as _cs
        _h = float(item["hue"]) / 360.0
        _r, _g, _b = _cs.hsv_to_rgb(_h, 0.65, 0.80)
        return (int(_r * 255), int(_g * 255), int(_b * 255))

    # 5) Rarity color
    return item_rarity_border(item)


def build_equipped_sprite(
    base_surf: pygame.Surface,
    equipped_items: Dict[str, Dict[str, object]],
    class_primary_rgb: Tuple[int, int, int] = (160, 160, 180),
) -> pygame.Surface:
    """Return base_surf with per-slot chromakey recoloring applied.
    Each equipped slot recolors its body region to the item's rarity color,
    then adds a dark contour around the recolored area."""
    result = base_surf.copy()

    all_changed: set = set()
    slot_colors: Dict[str, Tuple[int, int, int]] = {}
    for slot, region_entries in _CHROMAKEY_SLOTS.items():
        it = equipped_items.get(slot)
        if not isinstance(it, dict):
            continue
        slot_color = slot_colors.setdefault(slot, _resolve_item_visual_color(it))
        for region, match_mode in region_entries:
            changed = _recolor_region(result, region, slot_color, match_mode, base_surf=base_surf)
            all_changed.update(changed)

    def _recolor_slot_metal(slot_key: str, target_rgb: Optional[Tuple[int, int, int]]) -> None:
        if target_rgb is None:
            return
        for region, _match_mode in _CHROMAKEY_SLOTS.get(slot_key, []):
            changed = _recolor_region(result, region, target_rgb, "metal", base_surf=base_surf)
            all_changed.update(changed)

    weapon_item = equipped_items.get("weapon")
    offhand_item = equipped_items.get("offhand")
    weapon_color = slot_colors.get("weapon") if isinstance(weapon_item, dict) else None
    offhand_color = slot_colors.get("offhand") if isinstance(offhand_item, dict) else None
    _recolor_slot_metal("weapon", weapon_color)
    if offhand_color is not None:
        _recolor_slot_metal("offhand", offhand_color)
    elif weapon_color is not None:
        _recolor_slot_metal("offhand", weapon_color)

    return result


def build_equip_tint_overlay(
    base_surf: pygame.Surface,
    equipped_items: Dict[str, Dict[str, object]],
    class_primary_rgb: Tuple[int, int, int] = (160, 160, 180),
) -> Optional[pygame.Surface]:
    """Equipment visuals are now handled by pixel-level chromakey in
    build_equipped_sprite(). This returns None (no rectangle overlay)."""
    return None


def _deep_copy_anim_frames(
    frames: Dict[str, Dict[str, List[pygame.Surface]]],
) -> Dict[str, Dict[str, List[pygame.Surface]]]:
    """Deep-copy an LPC animation dict so originals are never touched."""
    result: Dict[str, Dict[str, List[pygame.Surface]]] = {}
    for anim_name, directions in frames.items():
        result[anim_name] = {}
        for direction, frame_list in directions.items():
            result[anim_name][direction] = [f.copy() for f in frame_list]
    return result


def build_equipped_anim_frames(
    base_frames: Dict[str, Dict[str, List[pygame.Surface]]],
    equipped_items: Dict[str, Dict[str, object]],
    class_primary_rgb: Tuple[int, int, int] = (160, 160, 180),
) -> Dict[str, Dict[str, List[pygame.Surface]]]:
    """Apply equipment chromakey recoloring to every frame in an LPC animation dict.
    Always returns a NEW dict — never the same reference as base_frames."""
    has_equip = any(
        isinstance(equipped_items.get(slot), dict)
        for slot in _CHROMAKEY_SLOTS
    )
    if not has_equip:
        # Return copies so caller never aliases the base frames
        return _deep_copy_anim_frames(base_frames)

    result: Dict[str, Dict[str, List[pygame.Surface]]] = {}
    for anim_name, directions in base_frames.items():
        result[anim_name] = {}
        for direction, frames in directions.items():
            result[anim_name][direction] = [
                build_equipped_sprite(frame, equipped_items, class_primary_rgb)
                for frame in frames
            ]
    return result


LPC_FRAME_W: int = 64
LPC_FRAME_H: int = 64
# LPC standard row layout: anim -> (start_row, frames_per_direction, num_directions)
LPC_ANIMS: Dict[str, Tuple[int, int, int]] = {
    "spellcast": (0,  7, 4),
    "thrust":    (4,  8, 4),
    "walk":      (8,  9, 4),
    "slash":     (12, 6, 4),
    "shoot":     (16, 13, 4),
    "hurt":      (20, 6,  1),
}
LPC_DIRS: List[str] = ["up", "left", "down", "right"]

WOLF_ANIMS: List[str] = ["walk", "run", "bite", "howl", "die"]
def _build_anim_frames(
    sprite: pygame.Surface,
    x_offsets: List[int],
    y_offsets: List[int],
    scales: List[float],
) -> Tuple[List[pygame.Surface], List[pygame.Surface]]:
    """Generate right-facing and left-facing frame lists from offset/scale tables."""
    w, h = sprite.get_size()
    count = len(x_offsets)
    right_frames: List[pygame.Surface] = []
    for idx in range(count):
        canvas = pygame.Surface((w, h), pygame.SRCALPHA)
        factor = scales[idx % len(scales)]
        draw_h = max(1, int(round(h * factor)))
        frame = sprite
        if draw_h != h:
            frame = pygame.transform.scale(sprite, (w, draw_h))
        rect = frame.get_rect(midbottom=(w // 2 + x_offsets[idx], h + y_offsets[idx]))
        canvas.blit(frame, rect)
        right_frames.append(canvas)
    left_frames = [pygame.transform.flip(f, True, False) for f in right_frames]
    return right_frames, left_frames


def build_sprite_idle_cycle(sprite: pygame.Surface, frame_count: int = 4) -> Dict[str, Dict[str, List[pygame.Surface]]]:
    w, h = sprite.get_size()
    if w <= 0 or h <= 0:
        blank = pygame.Surface((max(1, w), max(1, h)), pygame.SRCALPHA)
        dirs = {"right": [blank], "left": [blank], "down": [blank], "up": [blank]}
        return {"idle": dirs, "walk": dict(dirs)}

    # Idle: gentle breathing bob (subtle scale shifts, no lateral sway)
    idle_x = [0, 0, 0, 0]
    idle_y = [0, -1, 0, 0]
    idle_s = [1.0, 0.99, 1.0, 0.995]
    idle_r, idle_l = _build_anim_frames(sprite, idle_x, idle_y, idle_s)

    # Walk: pronounced stepping bounce with lateral lean
    walk_x = [0, 2, 0, -2]
    walk_y = [0, -3, 0, -3]
    walk_s = [1.0, 0.97, 1.0, 0.97]
    walk_r, walk_l = _build_anim_frames(sprite, walk_x, walk_y, walk_s)

    return {
        "idle": {"right": idle_r, "left": idle_l, "down": idle_r, "up": idle_r},
        "walk": {"right": walk_r, "left": walk_l, "down": walk_r, "up": walk_r},
    }


def cardinal_anim_direction(delta: Vector2, fallback: str = "down") -> str:
    dx = float(delta.x)
    dy = float(delta.y)
    if abs(dx) <= 0.001 and abs(dy) <= 0.001:
        return fallback
    if abs(dx) >= abs(dy):
        return "right" if dx >= 0.0 else "left"
    return "down" if dy >= 0.0 else "up"


def warrior_visual_tier_for_level(player_level: int) -> int:
    level_value = max(1, int(player_level))
    for min_level, tier in WARRIOR_TIER_LEVEL_THRESHOLDS:
        if level_value >= min_level:
            return tier
    return 1


def load_directional_sprite_rows(path: str, target_size: int = 96) -> Optional[Dict[str, List[pygame.Surface]]]:
    try:
        sheet = pygame.image.load(path).convert_alpha()
    except (pygame.error, FileNotFoundError, OSError):
        return None

    row_count = len(WARRIOR_ROW_TO_DIRECTION)
    if row_count <= 0 or sheet.get_height() < row_count:
        return None

    frame_h = sheet.get_height() // row_count
    frame_w = frame_h
    if frame_w <= 0:
        return None

    col_count = sheet.get_width() // frame_w
    if col_count <= 0:
        return None

    frames: Dict[str, List[pygame.Surface]] = {}
    for row_index, dir_key in enumerate(WARRIOR_ROW_TO_DIRECTION):
        row_frames: List[pygame.Surface] = []
        for col in range(col_count):
            rect = pygame.Rect(col * frame_w, row_index * frame_h, frame_w, frame_h)
            if rect.right > sheet.get_width() or rect.bottom > sheet.get_height():
                break
            tile = pygame.Surface((frame_w, frame_h), pygame.SRCALPHA)
            tile.blit(sheet, (0, 0), rect)
            if tile.get_bounding_rect(min_alpha=1).width <= 0:
                continue
            if target_size != frame_w or target_size != frame_h:
                tile = pygame.transform.scale(tile, (target_size, target_size))
            row_frames.append(tile)
        if row_frames:
            frames[dir_key] = row_frames
    return frames if frames else None


def load_warrior_class_visuals(target_size: int = 96) -> Dict[int, Dict[str, object]]:
    visuals: Dict[int, Dict[str, object]] = {}
    fps_map = {
        "idle": 6.0,
        "walk": 7.0,
        "run": 9.0,
        "attack": 11.0,
        "walk_attack": 9.0,
        "run_attack": 11.0,
        "hurt": 11.0,
        "death": 8.0,
    }

    for tier in (1, 2, 3):
        tier_root = os.path.join(WARRIOR_ASSET_ROOT, f"Swordsman_lvl{tier}", "Without_shadow")
        if not os.path.isdir(tier_root):
            continue

        anim_frames: Dict[str, Dict[str, List[pygame.Surface]]] = {}
        anim_fps: Dict[str, float] = {}
        anim_durations: Dict[str, float] = {}

        for anim_name, suffix in WARRIOR_SPRITE_ACTION_FILES:
            path = os.path.join(tier_root, f"Swordsman_lvl{tier}_{suffix}_without_shadow.png")
            frames = load_directional_sprite_rows(path, target_size=target_size)
            if not frames:
                continue
            fps = float(fps_map.get(anim_name, 8.0))
            anim_frames[anim_name] = frames
            anim_fps[anim_name] = fps
            frame_count = max((len(dir_frames) for dir_frames in frames.values()), default=1)
            anim_durations[anim_name] = max(0.05, float(frame_count) / max(0.1, fps))

        idle_frames = anim_frames.get("idle", {})
        left_idle = idle_frames.get("left") or idle_frames.get("down") or idle_frames.get("right") or idle_frames.get("up") or []
        right_idle = idle_frames.get("right") or idle_frames.get("down") or idle_frames.get("left") or idle_frames.get("up") or []
        preview_frames = idle_frames.get("down") or right_idle or left_idle
        if not left_idle or not right_idle or not preview_frames:
            continue

        preview_src = preview_frames[0]
        if preview_src.get_width() == 72 and preview_src.get_height() == 72:
            preview = preview_src
        else:
            preview = pygame.transform.smoothscale(preview_src, (72, 72))

        visuals[tier] = {
            "name": f"warrior tier {tier}",
            "sprite": left_idle[0],
            "sprite_left": right_idle[0],
            "preview": preview,
            "anim_frames": anim_frames,
            "anim_fps": anim_fps,
            "anim_durations": anim_durations,
            "tier": tier,
        }

    return visuals


def resolve_class_visual_entry(
    class_visuals: Dict[str, Dict[str, object]],
    class_id: str,
    player_level: int = 1,
    fallback: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    entry = class_visuals.get(class_id)
    if isinstance(entry, dict):
        variants = entry.get("variants")
        if class_id == "warrior" and isinstance(variants, dict):
            preferred_tier = warrior_visual_tier_for_level(player_level)
            for tier in (preferred_tier, 3, 2, 1):
                variant = variants.get(tier)
                if isinstance(variant, dict):
                    return variant
        return entry
    if isinstance(fallback, dict):
        return fallback
    return {}


def load_lpc_spritesheet(path: str, target_size: int = 96) -> Optional[Dict[str, Dict[str, List[pygame.Surface]]]]:
    """Load a LPC-format sprite sheet PNG and return animation frames dict.

    Returns {anim_name: {direction: [Surface, ...]}} or None on failure.
    Directions are "up", "left", "down", "right".
    Falls back to None so callers can use the existing single-sprite path.
    """
    try:
        sheet = pygame.image.load(path).convert_alpha()
    except (pygame.error, FileNotFoundError, OSError):
        return None
    frames: Dict[str, Dict[str, List[pygame.Surface]]] = {}
    for anim, (start_row, n_frames, n_dirs) in LPC_ANIMS.items():
        frames[anim] = {}
        for d in range(n_dirs):
            dir_key = LPC_DIRS[d] if n_dirs > 1 else "all"
            row = start_row + d
            row_frames: List[pygame.Surface] = []
            for col in range(n_frames):
                sx = col * LPC_FRAME_W
                sy = row * LPC_FRAME_H
                if sx + LPC_FRAME_W > sheet.get_width() or sy + LPC_FRAME_H > sheet.get_height():
                    break
                tile = sheet.subsurface((sx, sy, LPC_FRAME_W, LPC_FRAME_H))
                if target_size != LPC_FRAME_W:
                    tile = pygame.transform.scale(tile, (target_size, target_size))
                row_frames.append(tile)
            if row_frames:
                frames[anim][dir_key] = row_frames
    return frames if frames else None


def load_wolf_spritesheet(path: str, target_size: int = 64) -> Optional[Dict[str, Dict[str, List[pygame.Surface]]]]:
    """Load the OpenGameArt LPC Wolf animated sprite sheet (wolfsheet1.png).

    Actual sheet layout (640x384, 64x64 frames, 10 cols x 6 rows):
      Row 0: Walk south/down  (7 frames)
      Row 1: Walk west/left   (10 frames)
      Row 2: Walk east/right  (10 frames)
      Row 3: Walk north/up    (9 frames)
      Row 4: Run/chase        (10 frames, east-facing — mirrored for west)
      Row 5: Die              (5 frames at columns 5-9)

    Returns {anim: {direction: [Surface, ...]}} or None on failure.
    """
    try:
        sheet = pygame.image.load(path).convert_alpha()
    except (pygame.error, FileNotFoundError, OSError):
        return None

    fw = fh = 64
    w, h = sheet.get_size()
    n_cols = w // fw

    def get_row(row: int, start_col: int = 0, max_frames: int | None = None) -> List[pygame.Surface]:
        limit = n_cols if max_frames is None else min(n_cols, start_col + max_frames)
        out: List[pygame.Surface] = []
        for col in range(start_col, limit):
            if (row + 1) * fh > h or (col + 1) * fw > w:
                break
            tile = sheet.subsurface((col * fw, row * fh, fw, fh))
            if target_size != fw:
                tile = pygame.transform.scale(tile, (target_size, target_size))
            out.append(tile)
        return out

    walk_down  = get_row(0)
    walk_left  = get_row(1)
    walk_right = get_row(2)
    walk_up    = get_row(3)
    run_right  = get_row(4)
    run_left   = [pygame.transform.flip(f, True, False) for f in run_right]
    die_frames = get_row(5, start_col=5)   # only cols 5-9 have content

    frames: Dict[str, Dict[str, List[pygame.Surface]]] = {
        "walk": {
            "down":  walk_down,
            "left":  walk_left,
            "right": walk_right,
            "up":    walk_up,
        },
        "run": {
            "right": run_right,
            "left":  run_left,
            "down":  walk_down,
            "up":    walk_up,
        },
        "bite": {
            "right": run_right,
            "left":  run_left,
            "down":  walk_down,
            "up":    walk_up,
        },
        "die": {
            "right": die_frames if die_frames else walk_right,
            "left":  [pygame.transform.flip(f, True, False) for f in die_frames] if die_frames else walk_left,
            "down":  die_frames if die_frames else walk_down,
            "up":    die_frames if die_frames else walk_up,
        },
    }
    return frames


def get_lpc_frame(
    frames: Optional[Dict[str, Dict[str, List[pygame.Surface]]]],
    anim: str,
    direction: str,
    anim_timer: float,
    fps: float = 8.0,
) -> Optional[pygame.Surface]:
    """Return the current animation frame Surface, or None if frames is unavailable.

    direction should be one of: "left", "right", "up", "down".
    anim_timer is an accumulating float (seconds); fps controls playback speed.
    """
    if frames is None:
        return None
    anim_data = frames.get(anim) or frames.get("walk") or {}
    dir_frames = anim_data.get(direction) or anim_data.get("down") or []
    if not dir_frames:
        return None
    idx = int(anim_timer * fps) % len(dir_frames)
    return dir_frames[idx]


def get_directional_anim_frame(
    frames: Optional[Dict[str, Dict[str, List[pygame.Surface]]]],
    anim: str,
    direction: str,
    anim_timer: float,
    fps: float = 8.0,
    loop: bool = True,
) -> Optional[pygame.Surface]:
    if frames is None:
        return None
    anim_data = frames.get(anim) or frames.get("idle") or frames.get("walk") or {}
    dir_frames = (
        anim_data.get(direction)
        or anim_data.get("down")
        or anim_data.get("right")
        or next((value for value in anim_data.values() if value), [])
    )
    if not dir_frames:
        return None
    safe_fps = max(0.1, float(fps))
    if loop:
        idx = int(max(0.0, anim_timer) * safe_fps) % len(dir_frames)
    else:
        idx = min(len(dir_frames) - 1, int(max(0.0, anim_timer) * safe_fps))
    return dir_frames[idx]


def load_resource_bar_assets() -> Dict[str, pygame.Surface]:
    global _RESOURCE_BAR_ASSETS
    if _RESOURCE_BAR_ASSETS is not None:
        return _RESOURCE_BAR_ASSETS
    _RESOURCE_BAR_ASSETS = {}
    return _RESOURCE_BAR_ASSETS






def move_with_collision(start: Vector2, end: Vector2, step: float, bounds: pygame.Rect, obstacles: List[pygame.Rect], radius: float, extra_obstacles: Optional[List[pygame.Rect]] = None) -> Vector2:
    direction = end - start
    dist = direction.length()
    if dist <= 0.001: return start
    move = direction.normalize() * step if dist > step else direction
    target = start + move
    all_obs = obstacles + (extra_obstacles if extra_obstacles else [])
    if is_walkable(target, bounds, all_obs, radius): return target
    if abs(move.x) > 0.001 and is_walkable(start + Vector2(move.x, 0), bounds, all_obs, radius): return start + Vector2(move.x, 0)
    if abs(move.y) > 0.001 and is_walkable(start + Vector2(0, move.y), bounds, all_obs, radius): return start + Vector2(0, move.y)
    return start


def find_path_astar(start: Vector2, end: Vector2, bounds: pygame.Rect, obstacles: List[pygame.Rect], cell_size: int = 32, actor_radius: float = 0.0, max_expansions: int = 1000) -> List[Tuple[float, float]]:
    return [(start.x, start.y), (end.x, end.y)]


# (sx, sy, angle[, alpha]) deformation specs per animation state. Travel/lunge offsets
# are added by draw_player(); these frames carry the POSE deformation only.
_PROC_ANIM_SPECS = {
    "idle":   (6.0,  True,  [(1.0, 1.0, 0), (1.0, 1.02, 0), (1.0, 1.0, 0), (1.0, 0.985, 0)]),
    "walk":   (10.0, True,  [(1.0, 1.0, 3), (1.03, 0.97, 1), (1.0, 1.0, 0), (1.0, 1.0, -3), (1.03, 0.97, -1), (1.0, 1.0, 0)]),
    "run":    (13.0, True,  [(1.0, 1.05, -5), (1.06, 0.95, -2), (1.0, 1.06, -7), (1.0, 1.05, -5), (1.06, 0.95, -2), (1.0, 1.06, -7)]),
    "attack": (16.0, False, [(0.96, 1.05, 8), (1.14, 0.9, -12), (1.06, 0.97, -4), (1.0, 1.0, 0)]),
    "hurt":   (12.0, False, [(1.07, 0.93, 12), (1.03, 0.98, 6), (1.0, 1.0, 0)]),
    "death":  (9.0,  False, [(1.0, 1.0, -8, 255), (1.0, 0.97, -28, 235), (1.06, 0.9, -52, 205),
                              (1.12, 0.8, -72, 165), (1.16, 0.7, -84, 115), (1.2, 0.6, -88, 65)]),
}
# walk_attack / run_attack reuse the attack pose.
_PROC_ANIM_SPECS["walk_attack"] = _PROC_ANIM_SPECS["attack"]
_PROC_ANIM_SPECS["run_attack"] = _PROC_ANIM_SPECS["attack"]


def _deform_sprite(base, sx=1.0, sy=1.0, angle=0.0, alpha=255):
    """Return a transformed copy of base (scale for squash/stretch, rotate for lean)."""
    w, h = base.get_size()
    s = base
    if abs(sx - 1.0) > 0.001 or abs(sy - 1.0) > 0.001:
        s = pygame.transform.smoothscale(base, (max(2, int(w * sx)), max(2, int(h * sy))))
    if abs(angle) > 0.1:
        s = pygame.transform.rotozoom(s, float(angle), 1.0)
    if alpha < 255:
        s = s.copy()
        s.set_alpha(alpha)
    return s


def load_rogue_anim_frames(asset_dir: str = "assets/rogue_anim", target_size: int = 96):
    """Load the AI-generated rogue animation set (per-(state,direction) horizontal strips of
    64px cells, described by manifest.json) into the engine's anim format.

    Returns (anim_frames, anim_fps, anim_durations) or None if assets are missing.
    Derives left = mirror(right), run = walk, walk_attack/run_attack = attack so every
    engine state the player state-machine can request is covered.
    """
    import json as _json
    manifest_path = os.path.join(asset_dir, "manifest.json")
    try:
        with open(manifest_path, "r", encoding="utf-8") as fh:
            manifest = _json.load(fh)
    except (OSError, ValueError):
        return None

    CELL = 64
    raw: Dict[str, Dict[str, List[pygame.Surface]]] = {}
    fps: Dict[str, float] = {}
    base_dirs = ("down", "up", "right")
    base_states = ("idle", "walk", "attack", "hurt", "death")
    for st in base_states:
        for d in base_dirs:
            key = f"{st}_{d}"
            info = manifest.get(key)
            if not isinstance(info, dict):
                continue
            path = os.path.join(asset_dir, f"{key}.png")
            try:
                strip = pygame.image.load(path).convert_alpha()
            except (pygame.error, FileNotFoundError, OSError):
                continue
            n = int(info.get("frames", strip.get_width() // CELL))
            cells: List[pygame.Surface] = []
            for i in range(n):
                if (i + 1) * CELL > strip.get_width():
                    break
                tile = pygame.Surface((CELL, CELL), pygame.SRCALPHA)
                tile.blit(strip, (0, 0), pygame.Rect(i * CELL, 0, CELL, CELL))
                if target_size != CELL:
                    tile = pygame.transform.scale(tile, (target_size, target_size))
                cells.append(tile)
            if not cells:
                continue
            raw.setdefault(st, {})[d] = cells
            fps[st] = float(info.get("fps", 8.0))

    if not raw.get("idle") and not raw.get("walk"):
        return None

    # left = mirror of right
    for st, dirs in raw.items():
        if "right" in dirs and "left" not in dirs:
            dirs["left"] = [pygame.transform.flip(f, True, False) for f in dirs["right"]]

    anim_frames: Dict[str, Dict[str, List[pygame.Surface]]] = {st: dict(dirs) for st, dirs in raw.items()}
    # Aliases so the player state-machine always finds a clip.
    if "walk" in anim_frames:
        anim_frames.setdefault("run", {k: list(v) for k, v in anim_frames["walk"].items()})
        fps.setdefault("run", fps.get("walk", 9.0) * 1.35)
    if "attack" in anim_frames:
        for alias in ("walk_attack", "run_attack"):
            anim_frames.setdefault(alias, {k: list(v) for k, v in anim_frames["attack"].items()})
            fps.setdefault(alias, fps.get("attack", 12.0))

    non_looping = {"attack", "walk_attack", "run_attack", "hurt", "death"}
    durations: Dict[str, float] = {}
    for st, dirs in anim_frames.items():
        if st in non_looping:
            n = max((len(v) for v in dirs.values()), default=1)
            durations[st] = max(0.05, float(n) / max(0.1, fps.get(st, 8.0)))
    return anim_frames, fps, durations


def build_procedural_anim_frames(sprite_right, sprite_left):
    """Synthesize a full directional animation set from a single character sprite by
    applying per-state pose deformations (squash/stretch/lean/topple). Returns
    (frames, fps, durations) in the same format the engine uses for sheet-animated classes.
    frames: {state: {direction: [Surface, ...]}}; up/down/right share the right sprite,
    left uses the flipped sprite (with mirrored lean)."""
    def gen(base, mirror):
        sign = -1.0 if mirror else 1.0
        out = {}
        for state, (_fps, _loop, specs) in _PROC_ANIM_SPECS.items():
            frames = []
            for spec in specs:
                sx, sy, ang = spec[0], spec[1], spec[2] * sign
                a = spec[3] if len(spec) > 3 else 255
                frames.append(_deform_sprite(base, sx, sy, ang, a))
            out[state] = frames
        return out

    right = gen(sprite_right, False)
    left = gen(sprite_left, True)
    frames = {}
    for state in _PROC_ANIM_SPECS:
        frames[state] = {"right": right[state], "up": right[state],
                         "down": right[state], "left": left[state]}
    fps = {state: spec[0] for state, spec in _PROC_ANIM_SPECS.items()}
    durations = {state: (len(spec[2]) / max(0.1, spec[0]))
                 for state, spec in _PROC_ANIM_SPECS.items() if not spec[1]}
    return frames, fps, durations
