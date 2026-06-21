"""game/items.py — item/equipment/sprite metrics, icon building/resolution,
tooltips, generated-item stats, and their caches."""
import os
import math
import random
import colorsys
from typing import Dict, List, Optional, Tuple, Any, Union, Set

import pygame
from pygame import Vector2

from game.utils import clamp, lerp, exp_smooth, rotate_vec, color_lerp, hsv_to_rgb, point_in_rect
from game.vfx import spawn_particle_burst
from game.data.icons import *

__all__ = [
    'profession_xp_to_next',
    'profession_rank_name',
    'normalize_equipment_stats',
    'clone_item_data',
    'item_is_food',
    'item_can_go_in_potion_bar',
    'item_rarity',
    'item_rarity_border',
    'item_class_lock',
    'item_blocked_for_class',
    'ellipsize_text',
    'item_effect_tooltip',
    'format_item_stat_line',
    'build_item_tooltip_lines',
    'draw_item_tooltip',
    'build_empty_equipment_slot_tooltip',
    'sprite_metrics',
    '_sprite_slot_scores',
    'sprite_slot_from_metrics',
    'infer_external_icon_slot',
    'infer_item_visual_slot',
    'sprite_rarity_from_metrics',
    'sprite_theme_name',
    'generated_item_stats',
    'generated_food_effect_from_metrics',
    'build_food_crop_consumables',
    'build_external_item_library',
    'load_external_item_icon',
    'get_items_sheet',
    'load_items_sheet_icon',
    'get_arbitrary_sheet',
    'load_arbitrary_sheet_icon',
    'build_item_fallback_icon',
    'build_loot_misc_icon',
    'resolve_loot_entry_icon',
    'resolve_item_icon',
    'normalize_class_id',
    'SPELL_ICON_SOURCES',
]


def profession_xp_to_next(skill: int) -> int:
    s = max(1, int(skill))
    return 44 + s * 4


def profession_rank_name(skill: int) -> str:
    s = int(skill)
    if s >= 120:
        return "Master"
    if s >= 90:
        return "Artisan"
    if s >= 60:
        return "Expert"
    if s >= 30:
        return "Journeyman"
    return "Apprentice"




SPELL_ICON_SOURCES: Dict[str, tuple] = {}

_EXTERNAL_ITEM_LIBRARY: Optional[List[Dict[str, object]]] = None
_EXTERNAL_ICON_CACHE: Dict[Tuple[str, int], Optional[pygame.Surface]] = {}
_EXTERNAL_SLOT_CACHE: Dict[str, Tuple[str, float]] = {}
_ITEMS_SHEET_CACHE: Optional[pygame.Surface] = None
_ITEMS_ICON_CACHE: Dict[Tuple[int, int, int], Optional[pygame.Surface]] = {}
_ARBITRARY_SHEET_CACHE: Dict[str, Optional[pygame.Surface]] = {}
_ARBITRARY_SHEET_ICON_CACHE: Dict[Tuple[str, int, int, int, int], Optional[pygame.Surface]] = {}
_LOOT_ICON_CACHE: Dict[Tuple[str, str, int], pygame.Surface] = {}
_PASSIVE_ICON_CACHE: Dict[Tuple[str, int], pygame.Surface] = {}
_TOOLTIP_SURFACE: Optional[pygame.Surface] = None
_TOOLTIP_LAST_ITEM: Optional[object] = None


def normalize_equipment_stats(stats: Dict[str, object]) -> Dict[str, float]:
    out: dict[str, float] = {}
    for key, raw_val in stats.items():
        try:
            out[str(key)] = float(raw_val)
        except (TypeError, ValueError):
            continue

    flat_steps = {
        "max_hp": 2.0,
        "max_mana": 2.0,
        "mana_regen": 0.1,
        "spell_power": 1.0,
        "basic_damage": 1.0,
        "armor": 1.0,
    }
    flat_mins = {
        "max_hp": 6.0,
        "max_mana": 6.0,
        "mana_regen": 0.3,
        "spell_power": 3.0,
        "basic_damage": 3.0,
        "armor": 3.0,
    }
    for key in ("max_hp", "max_mana", "mana_regen", "spell_power", "basic_damage", "armor"):
        raw = float(out.get(key, 0.0))
        step = flat_steps[key]
        rounded = round(raw / step) * step
        if abs(rounded) < flat_mins[key]:
            rounded = 0.0
        out[key] = round(rounded, 2)

    for key in ("damage_reduction", "move_speed", "cooldown_reduction"):
        raw = float(out.get(key, 0.0))
        rounded = round(raw / 0.005) * 0.005
        if abs(rounded) < 0.01:
            rounded = 0.0
        out[key] = round(rounded, 4)
    return out


def clone_item_data(item: Dict[str, object]) -> Dict[str, object]:
    out = dict(item)
    stats = item.get("stats")
    if isinstance(stats, dict):
        out["stats"] = normalize_equipment_stats(stats)
    item_type = str(out.get("item_type", "")).strip().lower()
    equip_slot = str(out.get("equip_slot", "")).strip().lower()
    if item_type == "equipment":
        visual_slot, visual_conf = infer_item_visual_slot(out)
        if visual_slot in EQUIPMENT_SLOT_ORDER and visual_conf >= 0.72:
            item_id = str(out.get("id", ""))
            icon_path = str(out.get("icon_path", ""))
            normalized_path = os.path.normpath(icon_path).replace("\\", "/").lower()
            is_external = item_id.startswith("ext_fc_") or "/assets/items/64x64/" in f"/{normalized_path}/"
            if is_external and equip_slot != visual_slot:
                out["equip_slot"] = visual_slot
                if item_id.startswith("ext_fc_"):
                    old_name = str(out.get("name", ""))
                    for lbl in EQUIPMENT_SLOT_LABELS.values():
                        token = f" {lbl} "
                        if token in old_name:
                            new_label = EQUIPMENT_SLOT_LABELS.get(visual_slot, visual_slot.title())
                            out["name"] = old_name.replace(token, f" {new_label} ", 1)
                            break
    return out


def item_is_food(item: Optional[Dict[str, object]]) -> bool:
    if not isinstance(item, dict):
        return False
    item_id = str(item.get("id", "")).strip().lower()
    if item_id.startswith("food_crop_"):
        return True
    raw_sheet = str(item.get("icon_sheet", "")).replace("\\", "/").strip().lower()
    if "items food everything" in raw_sheet:
        return True
    return False


def item_can_go_in_potion_bar(item: Optional[Dict[str, object]]) -> bool:
    if not isinstance(item, dict):
        return False
    if item_is_food(item):
        return False
    item_type = str(item.get("item_type", "consumable")).strip().lower()
    if item_type and item_type != "consumable":
        return False
    equip_slot = str(item.get("equip_slot", "")).strip().lower()
    if equip_slot:
        return False
    effect = str(item.get("effect", "")).strip().lower()
    return effect in POTION_BAR_ALLOWED_EFFECTS


def item_rarity(item: Dict[str, object]) -> str:
    rarity = str(item.get("rarity", "common")).lower()
    if rarity not in ITEM_RARITY_COLORS:
        return "common"
    return rarity


def item_rarity_border(item: Dict[str, object]) -> Tuple[int, int, int]:
    return ITEM_RARITY_COLORS.get(item_rarity(item), ITEM_RARITY_COLORS["common"])


def item_class_lock(item: Dict[str, object]) -> str:
    return str(item.get("class_lock", "")).strip().lower()


def item_blocked_for_class(item: Dict[str, object], class_id: str) -> bool:
    lock = item_class_lock(item)
    cls = str(class_id).strip().lower()
    return bool(lock and cls and lock != cls)


def ellipsize_text(font: pygame.font.Font, text: str, max_width: int) -> str:
    raw = str(text).strip()
    if not raw:
        return ""
    if font.size(raw)[0] <= max_width:
        return raw
    if max_width <= font.size("...")[0]:
        return ""
    out = raw
    while len(out) > 1 and font.size(out + "...")[0] > max_width:
        out = out[:-1]
    return out + "..."


def item_effect_tooltip(effect_id: str) -> str:
    effect = str(effect_id).strip().lower()
    if not effect:
        return ""
    known = ITEM_EFFECT_TOOLTIPS.get(effect)
    if isinstance(known, str):
        return known
    if effect.startswith("hp_"):
        val = effect.split("_", 1)[1]
        if val.isdigit():
            return f"Restore {int(val)} HP."
    if effect.startswith("mp_"):
        val = effect.split("_", 1)[1]
        if val.isdigit():
            return f"Restore {int(val)} mana."
    return effect.replace("_", " ").title()


def format_item_stat_line(stat_key: str, raw_val: object) -> Optional[str]:
    try:
        val = float(raw_val)
    except (TypeError, ValueError):
        return None
    if abs(val) < 1e-6:
        return None
    if stat_key == "max_mana" and abs(val) < 6.0:
        return None
    if stat_key == "max_hp" and abs(val) < 6.0:
        return None
    if stat_key in ("spell_power", "basic_damage", "armor") and abs(val) < 3.0:
        return None
    if stat_key == "mana_regen" and abs(val) < 0.3:
        return None
    label = ITEM_STAT_LABELS.get(stat_key, stat_key.replace("_", " ").title())
    if stat_key in ("damage_reduction", "move_speed", "cooldown_reduction"):
        pct = val * 100.0
        if abs(pct) < 0.05:
            return None
        return f"+{pct:.1f}% {label}"
    if stat_key == "mana_regen":
        return f"+{val:.1f} {label}"
    if abs(val - round(val)) < 0.01:
        return f"+{int(round(val))} {label}"
    return f"+{val:.2f} {label}"


def build_item_tooltip_lines(item: Dict[str, object]) -> List[Tuple[str, Tuple[int, int, int]]]:
    rarity = item_rarity(item)
    rarity_col = ITEM_RARITY_COLORS.get(rarity, ITEM_RARITY_COLORS["common"])
    lines: List[Tuple[str, Tuple[int, int, int]]] = []
    name = str(item.get("name", "Unknown Item"))
    lines.append((name, rarity_col))

    item_type = str(item.get("item_type", "")).strip().lower()
    equip_slot = str(item.get("equip_slot", "")).strip().lower()
    if item_type == "equipment" or equip_slot:
        slot_label = EQUIPMENT_SLOT_LABELS.get(equip_slot, equip_slot.title() if equip_slot else "Equipment")
        lines.append((f"{rarity.title()} {slot_label}", (198, 192, 174)))
    else:
        lines.append((f"{rarity.title()} Consumable", (198, 192, 174)))

    class_lock = str(item.get("class_lock", "")).strip()
    if class_lock:
        lines.append((f"Class: {class_lock.title()}", (188, 168, 132)))

    set_name = str(item.get("set_name", "")).strip()
    if set_name:
        lines.append((f"Set: {set_name}", (192, 170, 114)))

    desc = str(item.get("desc", "")).strip()
    if desc:
        lines.append((desc, (176, 172, 160)))

    effect_text = item_effect_tooltip(str(item.get("effect", "")))
    if effect_text:
        lines.append((effect_text, (164, 202, 166)))

    stats_obj = item.get("stats")
    if isinstance(stats_obj, dict) and stats_obj:
        # Use canonical ordering first, then any extra generated keys.
        for key in EQUIP_STAT_KEYS:
            stat_line = format_item_stat_line(str(key), stats_obj.get(key, 0.0))
            if stat_line:
                lines.append((stat_line, (206, 210, 214)))
        for key, raw_val in sorted(stats_obj.items(), key=lambda kv: str(kv[0])):
            k = str(key)
            if k in EQUIP_STAT_KEYS:
                continue
            stat_line = format_item_stat_line(k, raw_val)
            if stat_line:
                lines.append((stat_line, (206, 210, 214)))
    return lines


def draw_item_tooltip(
    screen: pygame.Surface,
    item: Dict[str, object],
    anchor_rect: pygame.Rect,
    title_font: pygame.font.Font,
    body_font: pygame.font.Font,
) -> None:
    lines = build_item_tooltip_lines(item)
    if not lines:
        return

    rendered: List[Tuple[pygame.Surface, Tuple[int, int, int]]] = []
    max_w = 0
    max_line_w = 390
    for idx, (text, col) in enumerate(lines):
        font = title_font if idx == 0 else body_font
        line_text = ellipsize_text(font, str(text), max_line_w)
        surf = font.render(line_text, True, col)
        rendered.append((surf, col))
        max_w = max(max_w, surf.get_width())

    line_h = max(title_font.get_height(), body_font.get_height()) + 2
    tip_w = max_w + 20
    tip_h = 12 + len(rendered) * line_h
    tip = pygame.Rect(anchor_rect.right + 10, anchor_rect.top - 4, tip_w, tip_h)
    if tip.right > SCREEN_WIDTH - 10:
        tip.x = anchor_rect.left - tip_w - 10
    if tip.left < 10:
        tip.x = 10
    if tip.bottom > SCREEN_HEIGHT - 10:
        tip.y = SCREEN_HEIGHT - 10 - tip_h
    if tip.top < 10:
        tip.y = 10

    pygame.draw.rect(screen, (16, 16, 20), tip, border_radius=8)
    pygame.draw.rect(screen, item_rarity_border(item), tip, 1, border_radius=8)
    y = tip.top + 6
    for idx, (surf, _) in enumerate(rendered):
        screen.blit(surf, (tip.left + 10, y))
        y += line_h
        if idx == 0 and len(rendered) > 1:
            pygame.draw.line(screen, (64, 62, 56), (tip.left + 8, y - 2), (tip.right - 8, y - 2), 1)


def build_empty_equipment_slot_tooltip(slot: str) -> Dict[str, object]:
    slot_key = str(slot).strip().lower()
    slot_label = EQUIPMENT_SLOT_LABELS.get(slot_key, slot_key.title() if slot_key else "Equipment")
    return {
        "name": f"{slot_label} Slot",
        "item_type": "equipment",
        "equip_slot": slot_key,
        "rarity": "common",
        "desc": f"Equip a {slot_label.lower()} item here.",
        "stats": {},
    }


def sprite_metrics(surface: pygame.Surface) -> Dict[str, float]:
    w, h = surface.get_width(), surface.get_height()
    non_transparent = 0
    weighted_r = 0.0
    weighted_g = 0.0
    weighted_b = 0.0
    weighted_alpha = 0.0
    min_x, min_y = w, h
    max_x, max_y = -1, -1
    top_mass = 0
    bottom_mass = 0
    for y in range(h):
        for x in range(w):
            px = surface.get_at((x, y))
            a = int(px.a)
            if a <= 8:
                continue
            non_transparent += 1
            weighted_r += px.r * a
            weighted_g += px.g * a
            weighted_b += px.b * a
            weighted_alpha += a
            min_x = min(min_x, x)
            min_y = min(min_y, y)
            max_x = max(max_x, x)
            max_y = max(max_y, y)
            if y < h // 3:
                top_mass += 1
            elif y > (2 * h) // 3:
                bottom_mass += 1

    if non_transparent <= 0 or max_x < min_x or max_y < min_y or weighted_alpha <= 0.0:
        return {
            "coverage": 0.0,
            "bbox_w": 0.0,
            "bbox_h": 0.0,
            "aspect": 1.0,
            "top_mass": 0.0,
            "bottom_mass": 0.0,
            "hue_deg": 0.0,
            "sat": 0.0,
            "val": 0.0,
        }

    bbox_w = float(max_x - min_x + 1)
    bbox_h = float(max_y - min_y + 1)
    aspect = bbox_w / max(1.0, bbox_h)
    coverage = non_transparent / float(w * h)
    r = (weighted_r / weighted_alpha) / 255.0
    g = (weighted_g / weighted_alpha) / 255.0
    b = (weighted_b / weighted_alpha) / 255.0
    h_norm, s, v = colorsys.rgb_to_hsv(r, g, b)
    return {
        "coverage": coverage,
        "bbox_w": bbox_w,
        "bbox_h": bbox_h,
        "aspect": aspect,
        "top_mass": top_mass / max(1.0, non_transparent),
        "bottom_mass": bottom_mass / max(1.0, non_transparent),
        "hue_deg": h_norm * 360.0,
        "sat": s,
        "val": v,
    }


def _sprite_slot_scores(metrics: Dict[str, float]) -> Dict[str, float]:
    bbox_w = float(metrics.get("bbox_w", 0.0))
    bbox_h = float(metrics.get("bbox_h", 0.0))
    aspect = float(metrics.get("aspect", 1.0))
    coverage = float(metrics.get("coverage", 0.0))
    top_mass = float(metrics.get("top_mass", 0.0))
    bottom_mass = float(metrics.get("bottom_mass", 0.0))
    hue = float(metrics.get("hue_deg", 0.0))
    tallness = bbox_h / max(1.0, bbox_w)

    score = {slot: 0.0 for slot in EQUIPMENT_SLOT_ORDER}

    if bbox_w <= 22 and bbox_h <= 22 and coverage <= 0.22:
        score["ring"] += 3.8
    if bbox_w <= 18 and bbox_h <= 18:
        score["ring"] += 1.2

    if aspect >= 1.7 and bbox_h <= 26:
        score["belt"] += 3.4
    if aspect >= 2.2:
        score["belt"] += 0.9

    if bbox_h >= 44 and tallness >= 1.35:
        score["weapon"] += 2.8
    if bbox_h >= 52 and bbox_w <= 30:
        score["weapon"] += 2.2
    if tallness >= 1.8:
        score["weapon"] += 1.4

    if bbox_h >= 38 and bbox_w >= 32 and coverage >= 0.24:
        score["chest"] += 3.1
    if bbox_h >= 44 and bbox_w >= 36:
        score["chest"] += 1.1

    if 26 <= bbox_h <= 42 and 18 <= bbox_w <= 34 and 0.14 <= coverage <= 0.44:
        score["pants"] += 2.2
    if bbox_h >= 28 and 0.44 <= bottom_mass <= 0.64:
        score["pants"] += 0.8

    if 20 <= bbox_h <= 34 and top_mass >= bottom_mass + 0.06:
        score["head"] += 2.8
    if bbox_h <= 28 and bbox_w >= 22 and top_mass >= 0.44:
        score["head"] += 1.4

    if 20 <= bbox_h <= 34 and bottom_mass >= top_mass + 0.08:
        score["feet"] += 2.8
    if bbox_h <= 30 and bbox_w >= 22 and bottom_mass >= 0.42:
        score["feet"] += 1.2

    if bbox_w <= 32 and bbox_h <= 34 and coverage <= 0.38:
        score["hands"] += 2.2
    if bbox_w <= 28 and bbox_h <= 30:
        score["hands"] += 0.8

    if 45.0 <= hue <= 95.0 and coverage <= 0.36:
        score["amulet"] += 2.1
    if bbox_w <= 28 and bbox_h <= 30 and 35.0 <= hue <= 75.0:
        score["amulet"] += 1.2

    if 170.0 <= hue <= 265.0 and coverage <= 0.40:
        score["offhand"] += 1.8
    if 24 <= bbox_w <= 42 and 26 <= bbox_h <= 44 and 0.16 <= coverage <= 0.48:
        score["offhand"] += 1.5

    # Keep weapon vs armor strict to avoid sword-in-chest misclassification.
    if score["weapon"] >= 2.4:
        score["chest"] -= 0.8
        score["head"] -= 0.5
        score["hands"] -= 0.5
        score["feet"] -= 0.5

    return score


def sprite_slot_from_metrics(metrics: Dict[str, float], index_hint: int) -> str:
    score = _sprite_slot_scores(metrics)
    if not score:
        return "offhand"
    return max(score.items(), key=lambda kv: kv[1])[0]


def infer_external_icon_slot(icon_path: str) -> Tuple[str, float]:
    path = os.path.normpath(str(icon_path))
    if not path:
        return "", 0.0
    cached = _EXTERNAL_SLOT_CACHE.get(path)
    if isinstance(cached, tuple) and len(cached) == 2:
        return str(cached[0]), float(cached[1])
    if not os.path.isabs(path):
        path = os.path.normpath(path)
    if not os.path.exists(path):
        _EXTERNAL_SLOT_CACHE[path] = ("", 0.0)
        return "", 0.0
    try:
        surf = pygame.image.load(path).convert_alpha()
    except pygame.error:
        _EXTERNAL_SLOT_CACHE[path] = ("", 0.0)
        return "", 0.0
    metrics = sprite_metrics(surf)
    score = _sprite_slot_scores(metrics)
    ordered = sorted(score.items(), key=lambda kv: kv[1], reverse=True)
    if not ordered:
        _EXTERNAL_SLOT_CACHE[path] = ("", 0.0)
        return "", 0.0
    slot = ordered[0][0]
    top_score = float(ordered[0][1])
    second_score = float(ordered[1][1]) if len(ordered) > 1 else 0.0
    confidence = max(0.0, min(1.0, 0.28 + top_score * 0.11 + (top_score - second_score) * 0.25))
    _EXTERNAL_SLOT_CACHE[path] = (slot, confidence)
    return slot, confidence


def infer_item_visual_slot(item: Dict[str, object]) -> Tuple[str, float]:
    raw_icon = item.get("icon")
    if isinstance(raw_icon, (tuple, list)) and len(raw_icon) == 2:
        try:
            row = int(raw_icon[0])
            col = int(raw_icon[1])
        except (TypeError, ValueError):
            row = -1
            col = -1
        if row >= 0 and col >= 0:
            hinted = ITEM_SHEET_SLOT_HINTS.get((row, col), "")
            if hinted in EQUIPMENT_SLOT_ORDER:
                return hinted, 1.0

    icon_path = item.get("icon_path")
    if isinstance(icon_path, str) and icon_path:
        return infer_external_icon_slot(icon_path)
    return "", 0.0


def sprite_rarity_from_metrics(metrics: Dict[str, float], sprite_idx: int) -> str:
    sat = float(metrics.get("sat", 0.0))
    val = float(metrics.get("val", 0.0))
    cov = float(metrics.get("coverage", 0.0))
    score = sat * 0.46 + val * 0.36 + cov * 0.18
    roll = (sprite_idx * 37 + int(score * 1000.0)) % 1000
    if roll >= 992:
        return "legendary"
    if roll >= 930:
        return "epic"
    if roll >= 760:
        return "rare"
    return "common"


def sprite_theme_name(hue_deg: float) -> str:
    h = hue_deg % 360.0
    if h < 24.0:
        return "Ember"
    if h < 60.0:
        return "Sun"
    if h < 100.0:
        return "Verdant"
    if h < 155.0:
        return "Jade"
    if h < 210.0:
        return "Tide"
    if h < 260.0:
        return "Aether"
    if h < 315.0:
        return "Void"
    return "Crimson"


def generated_item_stats(
    slot: str,
    rarity: str,
    hue_deg: float,
    sat: float,
    val: float,
    sprite_idx: int,
) -> Dict[str, float]:
    rarity_mult = {
        "common": 1.0,
        "rare": 1.4,
        "epic": 1.9,
        "legendary": 2.6,
    }.get(rarity, 1.0)
    slot_base: Dict[str, Dict[str, float]] = {
        "weapon": {"basic_damage": 8.0, "spell_power": 5.0},
        "offhand": {"armor": 12.0, "damage_reduction": 0.010},
        "head": {"armor": 8.0, "max_mana": 10.0},
        "chest": {"armor": 18.0, "max_hp": 16.0},
        "pants": {"armor": 14.0, "max_hp": 12.0},
        "hands": {"cooldown_reduction": 0.010, "spell_power": 5.0},
        "feet": {"move_speed": 0.015, "armor": 7.0},
        "amulet": {"max_mana": 12.0, "mana_regen": 0.35},
        "ring": {"spell_power": 6.0, "cooldown_reduction": 0.008},
        "belt": {"max_hp": 14.0, "armor": 8.0},
    }
    hue_bonus: dict[str, float] = {}
    hue_factor = 0.65 + rarity_mult * 0.35
    if hue_deg < 48.0 or hue_deg >= 330.0:
        hue_bonus = {"basic_damage": 3.0, "max_hp": 6.0}
    elif hue_deg < 95.0:
        hue_bonus = {"armor": 6.0, "damage_reduction": 0.007}
    elif hue_deg < 170.0:
        hue_bonus = {"move_speed": 0.012, "cooldown_reduction": 0.007}
    elif hue_deg < 260.0:
        hue_bonus = {"max_mana": 8.0, "mana_regen": 0.28}
    else:
        hue_bonus = {"spell_power": 4.0, "cooldown_reduction": 0.006}
    stats = {key: 0.0 for key in EQUIP_STAT_KEYS}
    for key, base_val in slot_base.get(slot, slot_base["ring"]).items():
        stats[key] += float(base_val) * rarity_mult
    for key, bonus_val in hue_bonus.items():
        stats[key] += float(bonus_val) * hue_factor

    # Keep sprite personality without introducing tiny/noisy values.
    if sat >= 0.62:
        stats["spell_power"] += 2.0 * rarity_mult
    if val >= 0.66:
        stats["basic_damage"] += 2.0 * rarity_mult
    if (sprite_idx % 7) == 0:
        stats["armor"] += 2.0 * rarity_mult

    return normalize_equipment_stats(stats)


def generated_food_effect_from_metrics(metrics: Dict[str, float], sprite_idx: int) -> Tuple[str, str]:
    hue = float(metrics.get("hue_deg", 0.0))
    sat = float(metrics.get("sat", 0.0))
    val = float(metrics.get("val", 0.0))
    roll = (sprite_idx * 13 + int(sat * 100.0) + int(val * 80.0)) % 5
    if sat < 0.24:
        return "hp_25", "Hearty ration that restores 25 HP."
    if 12.0 <= hue <= 58.0:
        return ("hp_60", "Warm cooked meal that restores 60 HP.") if roll in (1, 3) else ("hp_25", "Field ration that restores 25 HP.")
    if 168.0 <= hue <= 268.0:
        return ("mp_full", "Arcane brew that restores all mana.") if roll == 0 else ("mp_80", "Cool tonic that restores 80 mana.")
    if 78.0 <= hue <= 158.0:
        return "speed_boost_60", "Gain +28% move speed for 60s."
    if 278.0 <= hue <= 340.0:
        return "dmg_boost_120", "Gain +35% damage for 120s."
    if roll == 2:
        return "speed_boost_60", "Gain +28% move speed for 60s."
    if roll == 4:
        return "dmg_boost_120", "Gain +35% damage for 120s."
    return "hp_25", "Light provisions that restore 25 HP."


def build_food_crop_consumables(sheet_path: str) -> List[Dict[str, object]]:
    norm_path = os.path.normpath(sheet_path.replace("\\", "/"))
    sheet = get_arbitrary_sheet(norm_path)
    if not isinstance(sheet, pygame.Surface):
        return []
    tile_size = 64
    cols = max(1, sheet.get_width() // tile_size)
    rows = max(1, sheet.get_height() // tile_size)
    out: List[Dict[str, object]] = []
    idx = 0
    for row in range(rows):
        for col in range(cols):
            rect = pygame.Rect(col * tile_size, row * tile_size, tile_size, tile_size)
            tile = pygame.Surface((tile_size, tile_size), pygame.SRCALPHA)
            tile.blit(sheet, (0, 0), rect)
            metrics = sprite_metrics(tile)
            coverage = float(metrics.get("coverage", 0.0))
            if coverage <= 0.012:
                continue
            idx += 1
            rarity = sprite_rarity_from_metrics(metrics, idx)
            effect, desc = generated_food_effect_from_metrics(metrics, idx)
            theme = sprite_theme_name(float(metrics.get("hue_deg", 0.0)))
            if effect == "hp_25":
                noun = "Ration"
            elif effect == "hp_60":
                noun = "Meal"
            elif effect == "mp_80":
                noun = "Tonic"
            elif effect == "mp_full":
                noun = "Arcane Brew"
            elif effect == "speed_boost_60":
                noun = "Trail Snack"
            else:
                noun = "Battle Draft"
            out.append(
                {
                    "id": f"food_crop_{idx:05d}",
                    "name": f"{theme} {noun} {idx:04d}",
                    "item_type": "consumable",
                    "equip_slot": "",
                    "rarity": rarity,
                    "class_lock": "",
                    "effect": effect,
                    "desc": desc,
                    "icon_sheet": norm_path,
                    "icon_tile": (row, col),
                    "icon_tile_size": tile_size,
                    "stats": {},
                }
            )
    return out


def build_external_item_library() -> List[Dict[str, object]]:
    global _EXTERNAL_ITEM_LIBRARY
    if _EXTERNAL_ITEM_LIBRARY is not None:
        return _EXTERNAL_ITEM_LIBRARY

    folder = os.path.join("assets", "items", "64x64")
    catalog: List[Dict[str, object]] = []
    if os.path.isdir(folder):
        paths = sorted(
            os.path.join(folder, name)
            for name in os.listdir(folder)
            if name.lower().endswith(".png")
        )
        for path_idx, path in enumerate(paths):
            stem = os.path.splitext(os.path.basename(path))[0].lower()
            sprite_idx = path_idx + 1
            if stem.startswith("fc") and stem[2:].isdigit():
                sprite_idx = int(stem[2:])
            else:
                digits = "".join(ch for ch in stem if ch.isdigit())
                if digits:
                    try:
                        sprite_idx = int(digits[-7:])
                    except ValueError:
                        sprite_idx = path_idx + 1
            try:
                sprite = pygame.image.load(path).convert_alpha()
            except pygame.error:
                continue

            metrics = sprite_metrics(sprite)
            if float(metrics.get("coverage", 0.0)) <= 0.0:
                continue

            score = _sprite_slot_scores(metrics)
            ordered_scores = sorted(score.items(), key=lambda kv: kv[1], reverse=True)
            slot = ordered_scores[0][0] if ordered_scores else "offhand"
            top_score = float(ordered_scores[0][1]) if ordered_scores else 0.0
            second_score = float(ordered_scores[1][1]) if len(ordered_scores) > 1 else 0.0
            slot_confidence = max(0.0, min(1.0, 0.28 + top_score * 0.11 + (top_score - second_score) * 0.25))
            rarity = sprite_rarity_from_metrics(metrics, sprite_idx)
            hue = float(metrics.get("hue_deg", 0.0))
            sat = float(metrics.get("sat", 0.0))
            val = float(metrics.get("val", 0.0))
            theme = sprite_theme_name(hue)
            slot_name = EQUIPMENT_SLOT_LABELS.get(slot, "Relic")
            name = f"{theme} {slot_name} {sprite_idx:04d}"
            stats = generated_item_stats(slot, rarity, hue, sat, val, sprite_idx)
            norm_path = os.path.normpath(path.replace("\\", "/"))
            _EXTERNAL_SLOT_CACHE[norm_path] = (slot, slot_confidence)
            if stem.startswith("fc") and stem[2:].isdigit():
                item_id = f"ext_fc_{sprite_idx:04d}"
            else:
                item_id = f"ext_{stem}"

            catalog.append(
                {
                    "id": item_id,
                    "name": name,
                    "item_type": "equipment",
                    "equip_slot": slot,
                    "rarity": rarity,
                    "class_lock": "",
                    "icon_path": path.replace("\\", "/"),
                    "stats": stats,
                    "desc": f"{rarity.title()} item forged from sprite analysis.",
                    "sprite_index": sprite_idx,
                    "slot_confidence": round(slot_confidence, 3),
                    "hue": round(hue, 2),
                    "coverage": round(float(metrics.get("coverage", 0.0)), 4),
                }
            )

    _EXTERNAL_ITEM_LIBRARY = catalog
    return catalog


def load_external_item_icon(item: Dict[str, object], size: int = 36) -> Optional[pygame.Surface]:
    raw_path = item.get("icon_path")
    if not isinstance(raw_path, str) or not raw_path:
        return None
    key = (raw_path, size)
    if key in _EXTERNAL_ICON_CACHE:
        return _EXTERNAL_ICON_CACHE[key]
    norm_path = os.path.normpath(raw_path)
    try:
        if not os.path.exists(norm_path):
            raise FileNotFoundError(f"External item icon not found at {norm_path}")
        surf = pygame.image.load(raw_path).convert_alpha()
    except pygame.error:
        _EXTERNAL_ICON_CACHE[key] = None
        return None
    if surf.get_width() != size or surf.get_height() != size:
        surf = pygame.transform.smoothscale(surf, (size, size))
    _EXTERNAL_ICON_CACHE[key] = surf
    return surf


def get_items_sheet() -> Optional[pygame.Surface]:
    global _ITEMS_SHEET_CACHE
    if isinstance(_ITEMS_SHEET_CACHE, pygame.Surface):
        return _ITEMS_SHEET_CACHE
    sheet_path = "assets/items.png"
    try:
        if not os.path.exists(sheet_path):
            raise FileNotFoundError(f"Item sheet not found at {sheet_path}")
        _ITEMS_SHEET_CACHE = pygame.image.load("assets/items.png").convert_alpha()
    except pygame.error:
        _ITEMS_SHEET_CACHE = None
    return _ITEMS_SHEET_CACHE


def load_items_sheet_icon(row: int, col: int, size: int = 48) -> Optional[pygame.Surface]:
    key = (row, col, size)
    if key in _ITEMS_ICON_CACHE:
        return _ITEMS_ICON_CACHE[key]
    sheet = get_items_sheet()
    if not isinstance(sheet, pygame.Surface):
        _ITEMS_ICON_CACHE[key] = None
        return None
    tile = extract_sheet_tile(sheet, row, col, 32)
    if tile.get_bounding_rect(min_alpha=1).width <= 0:
        _ITEMS_ICON_CACHE[key] = None
        return None
    icon = pygame.transform.smoothscale(tile, (size, size))
    _ITEMS_ICON_CACHE[key] = icon
    return icon


def get_arbitrary_sheet(path: str) -> Optional[pygame.Surface]:
    norm = os.path.normpath(str(path).replace("\\", "/"))
    if norm in _ARBITRARY_SHEET_CACHE:
        return _ARBITRARY_SHEET_CACHE[norm]
    try:
        sheet = pygame.image.load(norm).convert_alpha()
    except pygame.error:
        sheet = None
    _ARBITRARY_SHEET_CACHE[norm] = sheet
    return sheet


def load_arbitrary_sheet_icon(
    sheet_path: str,
    row: int,
    col: int,
    tile_size: int = 64,
    size: int = 48,
) -> Optional[pygame.Surface]:
    norm = os.path.normpath(str(sheet_path).replace("\\", "/"))
    key = (norm, int(row), int(col), int(tile_size), int(size))
    if key in _ARBITRARY_SHEET_ICON_CACHE:
        return _ARBITRARY_SHEET_ICON_CACHE[key]
    sheet = get_arbitrary_sheet(norm)
    if not isinstance(sheet, pygame.Surface):
        _ARBITRARY_SHEET_ICON_CACHE[key] = None
        return None
    rect = pygame.Rect(int(col) * int(tile_size), int(row) * int(tile_size), int(tile_size), int(tile_size))
    if rect.right > sheet.get_width() or rect.bottom > sheet.get_height():
        _ARBITRARY_SHEET_ICON_CACHE[key] = None
        return None
    tile = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    tile.blit(sheet, (0, 0), rect)
    if tile.get_bounding_rect(min_alpha=1).width <= 0:
        _ARBITRARY_SHEET_ICON_CACHE[key] = None
        return None
    icon = pygame.transform.smoothscale(tile, (size, size)) if size != rect.width else tile
    _ARBITRARY_SHEET_ICON_CACHE[key] = icon
    return icon


def build_item_fallback_icon(item: Dict[str, object], size: int) -> pygame.Surface:
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.rect(surf, (16, 16, 20), pygame.Rect(0, 0, size, size), border_radius=max(4, size // 8))
    glyph = (220, 210, 188)
    dark = (70, 60, 44)
    c = size // 2
    equip_slot = str(item.get("equip_slot", "")).strip().lower()
    effect = str(item.get("effect", "")).strip().lower()
    item_type = str(item.get("item_type", "")).strip().lower()

    if item_type == "equipment" or equip_slot:
        if equip_slot == "weapon":
            pygame.draw.rect(surf, dark, pygame.Rect(c - 2, size // 6, 4, size - size // 3), border_radius=2)
            pygame.draw.polygon(surf, glyph, [(c, size // 8), (c - 5, size // 4), (c + 5, size // 4)])
            pygame.draw.line(surf, glyph, (c - 7, size - size // 3), (c + 7, size - size // 3), 2)
        elif equip_slot == "offhand":
            pygame.draw.polygon(
                surf,
                glyph,
                [(c, size // 7), (size - size // 5, c - 2), (c, size - size // 7), (size // 5, c - 2)],
            )
            pygame.draw.polygon(
                surf,
                dark,
                [(c, size // 5), (size - size // 4, c - 2), (c, size - size // 5), (size // 4, c - 2)],
                1,
            )
        elif equip_slot == "head":
            pygame.draw.arc(surf, glyph, pygame.Rect(size // 5, size // 5, size - (2 * (size // 5)), size // 2), math.pi, math.tau, 2)
            pygame.draw.rect(surf, glyph, pygame.Rect(size // 4, c - 2, size // 2, size // 5), border_radius=2)
        elif equip_slot == "chest":
            pts = [(c, size // 5), (size - size // 5, size // 3), (size - size // 4, size - size // 5), (size // 4, size - size // 5), (size // 5, size // 3)]
            pygame.draw.polygon(surf, glyph, pts)
            pygame.draw.polygon(surf, dark, pts, 1)
        elif equip_slot == "pants":
            waist = pygame.Rect(size // 4, size // 5, size // 2, max(4, size // 7))
            left_leg = [(size // 4, size // 3), (c - 1, size // 3), (c - 3, size - size // 6), (size // 5, size - size // 6)]
            right_leg = [(c + 1, size // 3), (size - size // 4, size // 3), (size - size // 5, size - size // 6), (c + 3, size - size // 6)]
            pygame.draw.rect(surf, glyph, waist, border_radius=2)
            pygame.draw.polygon(surf, glyph, left_leg)
            pygame.draw.polygon(surf, glyph, right_leg)
            pygame.draw.rect(surf, dark, waist, 1, border_radius=2)
            pygame.draw.polygon(surf, dark, left_leg, 1)
            pygame.draw.polygon(surf, dark, right_leg, 1)
        elif equip_slot == "hands":
            pygame.draw.rect(surf, glyph, pygame.Rect(size // 5, c - 4, size // 3, size // 3), border_radius=2)
            pygame.draw.rect(surf, glyph, pygame.Rect(c - 2, c - 1, size // 3, size // 3), border_radius=2)
        elif equip_slot == "feet":
            pygame.draw.rect(surf, glyph, pygame.Rect(size // 4, c, size // 2, size // 4), border_radius=3)
            pygame.draw.rect(surf, glyph, pygame.Rect(c - 3, size // 3, size // 4, size // 3), border_radius=3)
        elif equip_slot == "amulet":
            pygame.draw.circle(surf, glyph, (c, c + 2), max(3, size // 6), 2)
            pygame.draw.line(surf, glyph, (c, size // 6), (c - 4, c - 3), 1)
            pygame.draw.line(surf, glyph, (c, size // 6), (c + 4, c - 3), 1)
        elif equip_slot == "ring":
            pygame.draw.circle(surf, glyph, (c, c), max(4, size // 4), 2)
            pygame.draw.circle(surf, dark, (c, c), max(2, size // 8))
        elif equip_slot == "belt":
            belt_h = max(5, size // 5)
            pygame.draw.rect(surf, glyph, pygame.Rect(size // 6, c - belt_h // 2, size - size // 3, belt_h), border_radius=2)
            buckle = pygame.Rect(c - 3, c - 4, 7, 8)
            pygame.draw.rect(surf, dark, buckle)
            pygame.draw.rect(surf, glyph, buckle, 1)
        else:
            pygame.draw.circle(surf, glyph, (c, c), max(4, size // 4), 2)
    else:
        bottle_col = (176, 176, 188)
        if effect.startswith("hp_") or effect == "full_restore":
            bottle_col = (206, 94, 94)
        elif effect.startswith("mp_"):
            bottle_col = (84, 136, 220)
        elif "dmg_boost" in effect:
            bottle_col = (102, 180, 88)
        elif "speed_boost" in effect:
            bottle_col = (108, 194, 218)
        elif effect == "town_portal":
            parchment = pygame.Rect(size // 4, size // 4, size // 2, size // 2)
            pygame.draw.rect(surf, (210, 186, 132), parchment, border_radius=2)
            pygame.draw.rect(surf, dark, parchment, 1, border_radius=2)
            pygame.draw.line(surf, dark, (parchment.left + 3, parchment.top + 5), (parchment.right - 3, parchment.top + 5), 1)
            pygame.draw.line(surf, dark, (parchment.left + 3, parchment.top + 9), (parchment.right - 6, parchment.top + 9), 1)
            return surf
        elif effect == "teleport_book":
            # Book icon: purple/arcane tome
            book = pygame.Rect(size // 5, size // 5, int(size * 0.6), int(size * 0.65))
            # cover
            pygame.draw.rect(surf, (90, 50, 160), book, border_radius=3)
            pygame.draw.rect(surf, (60, 30, 120), book, 1, border_radius=3)
            # spine
            pygame.draw.rect(surf, (70, 38, 130), (book.left, book.top + 2, 4, book.height - 4), border_radius=1)
            # pages
            pages = book.inflate(-8, -6)
            pages.left += 4
            pygame.draw.rect(surf, (220, 210, 190), pages, border_radius=1)
            # arcane symbol on cover
            cx_b, cy_b = book.centerx + 1, book.centery
            r_sym = max(3, size // 8)
            pygame.draw.circle(surf, (180, 140, 255), (cx_b, cy_b), r_sym, 1)
            pygame.draw.line(surf, (180, 140, 255), (cx_b, cy_b - r_sym + 1), (cx_b, cy_b + r_sym - 1), 1)
            pygame.draw.line(surf, (180, 140, 255), (cx_b - r_sym + 1, cy_b), (cx_b + r_sym - 1, cy_b), 1)
            return surf
        neck = pygame.Rect(c - 3, size // 5, 6, size // 8)
        body = pygame.Rect(size // 4, size // 3, size // 2, size // 2)
        pygame.draw.rect(surf, bottle_col, body, border_radius=3)
        pygame.draw.rect(surf, bottle_col, neck, border_radius=2)
        pygame.draw.rect(surf, dark, body, 1, border_radius=3)
        pygame.draw.rect(surf, dark, neck, 1, border_radius=2)
    return surf


def build_loot_misc_icon(kind: str, key: str, size: int, tint: Optional[Tuple[int, int, int]] = None) -> pygame.Surface:
    cache_key = (str(kind), str(key), int(size))
    cached = _LOOT_ICON_CACHE.get(cache_key)
    if isinstance(cached, pygame.Surface):
        return cached
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    c = size // 2
    if kind == "gold":
        pygame.draw.circle(surf, (158, 118, 34), (c, c), max(4, size // 3))
        pygame.draw.circle(surf, (232, 194, 84), (c, c), max(3, size // 3 - 1))
        pygame.draw.circle(surf, (252, 226, 136), (c - 2, c - 2), max(1, size // 10))
    elif kind == "material" and key == "wolf_pelt":
        pts = [(size // 2, 2), (size - 3, size // 3), (size - 5, size - 4), (size // 2, size - 2), (3, size - 5), (2, size // 3)]
        pygame.draw.polygon(surf, (146, 106, 78), pts)
        pygame.draw.polygon(surf, (82, 58, 42), pts, 1)
        pygame.draw.circle(surf, (186, 150, 112), (c, c), max(2, size // 6))
    elif kind == "material" and key == "wolf_fang":
        pts = [(c, 2), (size - 4, size - 4), (4, size - 4)]
        pygame.draw.polygon(surf, (230, 222, 202), pts)
        pygame.draw.polygon(surf, (138, 132, 118), pts, 1)
        pygame.draw.line(surf, (164, 156, 140), (c, size // 4), (c, size - 5), 1)
    elif kind == "material" and key == "wolf_claw":
        claw_col = (186, 170, 140)
        for i in range(3):
            x = size // 4 + i * max(2, size // 6)
            pygame.draw.line(surf, claw_col, (x, size - 4), (x + 3, 3), 2)
    elif kind == "material" and key == "wolf_bone":
        bone_col = (214, 206, 188)
        pygame.draw.line(surf, bone_col, (size // 4, c), (size - size // 4, c), 3)
        pygame.draw.circle(surf, bone_col, (size // 5, c), max(2, size // 7))
        pygame.draw.circle(surf, bone_col, (size - size // 5, c), max(2, size // 7))
        pygame.draw.circle(surf, bone_col, (size // 4, c - 3), max(2, size // 8))
        pygame.draw.circle(surf, bone_col, (size - size // 4, c + 3), max(2, size // 8))
    elif kind == "material" and key == "venom_sac":
        pygame.draw.circle(surf, (74, 150, 62), (c, c + 1), max(4, size // 3))
        pygame.draw.circle(surf, (108, 210, 92), (c - 2, c - 2), max(2, size // 6))
        pygame.draw.circle(surf, (42, 88, 38), (c + 3, c + 3), max(1, size // 8))
    else:
        base = tint if (isinstance(tint, tuple) and len(tint) >= 3) else (164, 164, 170)
        pygame.draw.circle(surf, (int(base[0]), int(base[1]), int(base[2])), (c, c), max(3, size // 3))
    _LOOT_ICON_CACHE[cache_key] = surf
    return surf


def resolve_loot_entry_icon(
    kind: str,
    key: str,
    row_color: tuple[int, int, int],
    item_payload: Optional[Dict[str, object]],
    size: int,
) -> Optional[pygame.Surface]:
    if kind == "item" and isinstance(item_payload, dict):
        return resolve_item_icon(item_payload, size)
    if kind == "gold":
        return build_loot_misc_icon("gold", "gold", size)
    if kind == "material":
        return build_loot_misc_icon("material", key, size, row_color)
    return None


def resolve_item_icon(item: Dict[str, object], size: int) -> Optional[pygame.Surface]:
    icon = load_external_item_icon(item, size)
    if isinstance(icon, pygame.Surface):
        return icon
    raw_sheet = item.get("icon_sheet")
    raw_tile = item.get("icon_tile")
    if isinstance(raw_sheet, str) and isinstance(raw_tile, (tuple, list)) and len(raw_tile) == 2:
        try:
            row = int(raw_tile[0])
            col = int(raw_tile[1])
            tile_size = int(item.get("icon_tile_size", 64))
        except (TypeError, ValueError):
            row = -1
            col = -1
            tile_size = 64
        if row >= 0 and col >= 0:
            sheet_icon = load_arbitrary_sheet_icon(raw_sheet, row, col, tile_size=tile_size, size=size)
            if isinstance(sheet_icon, pygame.Surface):
                return sheet_icon
    raw_icon = item.get("icon")
    if isinstance(raw_icon, (tuple, list)) and len(raw_icon) == 2:
        try:
            row = int(raw_icon[0])
            col = int(raw_icon[1])
        except (TypeError, ValueError):
            row = -1
            col = -1
        if row >= 0 and col >= 0:
            sheet_icon = load_items_sheet_icon(row, col, size)
            if isinstance(sheet_icon, pygame.Surface):
                return sheet_icon
    return build_item_fallback_icon(item, size)


def normalize_class_id(raw_class: object, fallback: str = "rogue") -> str:
    value = str(raw_class if raw_class is not None else "").strip()
    if value in CLASS_ARCHETYPES:
        return value

    lowered = value.lower()
    if lowered in CLASS_ARCHETYPES:
        return lowered

    if lowered:
        for class_id, class_data in CLASS_ARCHETYPES.items():
            class_name = str(class_data.get("name", "")).strip().lower()
            if class_name == lowered:
                return class_id

    if fallback in CLASS_ARCHETYPES:
        return fallback
    return next(iter(CLASS_ARCHETYPES.keys()), "rogue")
