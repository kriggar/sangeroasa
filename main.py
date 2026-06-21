import json
import io
import math
import os
import random
import colorsys
import wave
from array import array
from typing import List, Dict, Optional, Union, Set, Tuple, Any

import pygame
import pygame.gfxdraw
from pygame import Vector2

try:
    from tools.generate_medieval_assets import generate_medieval_pack as run_medieval_pack_generator
except ImportError:
    run_medieval_pack_generator = None

# Canonical tuning constants and asset paths — single source of truth.
from game.constants import *  # noqa: F401,F403
from game.utils import clamp, exp_smooth, rotate_vec, color_lerp  # pure math/geometry/color helpers
from game.vfx import (spawn_particle_burst, spawn_blood_splatter, spawn_damage_number,
                      update_damage_numbers, draw_damage_numbers, spell_vfx_palette)
from game.nav import is_walkable, nearest_walkable
from game.assets import _scale_surface_to_fit, _humanize_catalog_asset_id, AssetManager
from game.data.quests import QUEST_DEFINITIONS
from game.dialogue import (QUEST_GIVER_ROLE_BY_ID, DEFAULT_QUEST_GIVER_ROLE, quest_giver_role_for_id, quest_marker_for_vendor_role, _quest_role_for_def, vendor_has_quest_menu, normalize_vendor_available_quests, DIALOGUE_DEFINITIONS, get_dialogue_for_npc, check_dialogue_condition, execute_dialogue_action, DialogueSession)

# game/ engine modules — architecture split
try:
    from game.combat import CombatRuntime, CombatSceneContext, apply_class_overrides  # type: ignore[import]
    from game.hud import (  # type: ignore[import]
        HUD_ORB_R as _HUD_ORB_R,
        HUD_GLOBE_STYLES as _HUD_GLOBE_STYLES,
        build_hud_globe_frame as _build_hud_globe_frame,
        build_hud_gem_fill as _build_hud_gem_fill,
        get_globe_value_font as _get_globe_value_font,
        get_potion_keybind_font as _get_potion_keybind_font,
        draw_hud_globe as _draw_hud_globe,
    )
except ImportError:
    CombatRuntime = None  # type: ignore[assignment]
    CombatSceneContext = None  # type: ignore[assignment]
    apply_class_overrides = None  # type: ignore[assignment]


# Ensure relative asset paths work regardless of where main.py is launched from
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(SCRIPT_DIR)


# Tuning constants and asset paths are defined in game/constants.py (imported via *).


from game.audio import GameAudio  # procedural audio engine


from game.data.classes import *  # class & skill data tables
from game.data.world_data import (_POTIONS, TELEPORT_BOOK_ITEM, CLASS_ARMOR_SET_BONUSES, WOLF_MATERIALS, MATERIAL_ORDER, PROFESSION_DEFINITIONS, PROFESSION_ORDER, PROFESSION_MAX_SKILL)
from game.state import VENDOR_SHOPS, _HUD_STATE
from game.data.icons import *  # spell-icon maps & class palettes
from game.data.items_data import *  # item/equipment data tables
from game.items import *  # item/sprite/icon/tooltip helpers
from game.render.props import *  # decorative/prop/building draw helpers
from game.world.scenes import *  # scene builders
from game.loaders import *  # rogue/class-visual/vendor/NPC loaders
from game.combat.spellcast import *  # spell casting + effects
from game.vendors import *  # vendor placement/update/render
from game.farm import *  # farm animals + rendering
from game.ui.charcreate import *  # character creation screens
from game.entities import *  # enemies/wolves/skeletons/animals/portals
from game.sprites import *  # sprite/anim/class-visual/recolour/movement helpers
from game.gameplay_math import *  # gameplay math helpers
from game.render.shops import *  # vendor shop draw functions
from game.render.glyphs import *  # tool/item glyph icons
from game.classes_runtime import *  # class spellbook/skill-tree/passive helpers

# Per-renderer caches whose only users (draw_hover_tooltip / build_class_passive_icon) live here.
_PASSIVE_ICON_CACHE: Dict[Tuple[str, int], pygame.Surface] = {}
_TOOLTIP_SURFACE: Optional[pygame.Surface] = None
_TOOLTIP_LAST_ITEM: Optional[object] = None

# Combat kits layer class-specific overrides onto the base tables at load.
if callable(apply_class_overrides):
    apply_class_overrides(CLASS_ARCHETYPES, CLASS_COMBAT_STATS, CLASS_PASSIVES, CLASS_CORE_SKILL_META)

# Items sold by specific vendor roles. key = vendor role string.

# Potion definitions — icons from items.txt rows 20-21 (0-indexed)


for _set_data in CLASS_ARMOR_SETS.values():
    pieces = _set_data.get("pieces")
    if not isinstance(pieces, list):
        continue
    for _piece in pieces:
        if not isinstance(_piece, dict):
            continue
        _icon = _piece.get("icon")
        if not (isinstance(_icon, (tuple, list)) and len(_icon) == 2):
            continue
        try:
            _row = int(_icon[0])
            _col = int(_icon[1])
        except (TypeError, ValueError):
            continue
        _slot = str(_piece.get("slot", "")).strip().lower()
        if _slot in EQUIPMENT_SLOT_ORDER:
            ITEM_SHEET_SLOT_HINTS[(_row, _col)] = _slot

# ── Crafting: materials dropped by wolves ─────────────────────────────────────

PASSIVE_ANIMAL_MATERIALS: Dict[str, Dict] = {
    "deer_hide":    {"name": "Deer Hide",    "color": (180, 150, 120), "drop_chance": 0.80, "max_drop": 2},
    "venison":      {"name": "Venison",      "color": (160, 80, 80),   "drop_chance": 0.60, "max_drop": 1},
    "bird_feather": {"name": "Bird Feather", "color": (210, 210, 210), "drop_chance": 0.75, "max_drop": 3},
    "poultry":      {"name": "Poultry",      "color": (200, 180, 170), "drop_chance": 0.50, "max_drop": 1},
    "rat_tail":     {"name": "Rat Tail",     "color": (200, 160, 160), "drop_chance": 0.90, "max_drop": 1},
    "arctic_fish":  {"name": "Arctic Fish",  "color": (120, 200, 230), "drop_chance": 0.85, "max_drop": 3},
    "icefish_oil":  {"name": "Icefish Oil",  "color": (180, 230, 240), "drop_chance": 0.45, "max_drop": 1},
    "frost_roe":    {"name": "Frost Roe",    "color": (200, 160, 200), "drop_chance": 0.30, "max_drop": 1},
}

ANIMAL_MATERIAL_MAP: Dict[str, List[str]] = {
    "Deer": ["deer_hide", "venison"],
    "Doe": ["deer_hide", "venison"],
    "Fawn": ["venison"],
    "Elk": ["deer_hide", "venison"],
    "Ram": ["deer_hide", "venison"],
    "Rabbit": ["venison"],
    "Hare": ["venison"],
    "Beaver": ["venison"],
    "Marmot": ["venison"],
    "Duck": ["bird_feather", "poultry"],
    "Goose": ["bird_feather", "poultry"],
    "Turkey": ["bird_feather", "poultry"],
    "Pheasant": ["bird_feather", "poultry"],
    "Owl": ["bird_feather"],
    "Crow": ["bird_feather"],
    "Wildfowl": ["bird_feather", "poultry"],
    "Giant Rat": ["rat_tail"],
    # Ice biome animals
    "Arctic Hare":    ["venison"],
    "Caribou":        ["deer_hide", "venison"],
    "Mountain Goat":  ["deer_hide", "venison"],
    "Tundra Yak":     ["deer_hide", "venison"],
    "Snowy Crane":    ["bird_feather"],
    "Penguin":        ["bird_feather", "poultry"],
    "Snow Goose":     ["bird_feather", "poultry"],
    "Snowy Owl":      ["bird_feather"],
    "Arctic Fox":     ["deer_hide", "venison"],
    "Musk Ox":        ["deer_hide", "venison"],
}


# ── Quests ────────────────────────────────────────────────────────────────────

CRAFTING_RECIPES: List[Dict] = [
    # Alchemy
    {
        "id": "craft_healing_salve",
        "name": "Healing Salve",
        "desc": "Restore 80 HP",
        "profession": "alchemy",
        "required_skill": 1,
        "xp": 16,
        "quality": "common",
        "category": "Consumable",
        "ingredients": {"wolf_pelt": 2},
        "result": {"effect": "hp_80", "name": "Healing Salve", "color": (200, 80, 80), "rarity": "common"},
    },
    {
        "id": "craft_mana_brew",
        "name": "Mana Brew",
        "desc": "Restore full mana",
        "profession": "alchemy",
        "required_skill": 20,
        "xp": 19,
        "quality": "rare",
        "category": "Consumable",
        "ingredients": {"venom_sac": 1, "wolf_bone": 1, "wolf_fang": 1},
        "result": {"effect": "mp_full", "name": "Mana Brew", "color": (80, 120, 220), "rarity": "rare"},
    },
    {
        "id": "craft_swift_tonic",
        "name": "Swift Tonic",
        "desc": "+28% move speed for 60s",
        "profession": "alchemy",
        "required_skill": 35,
        "xp": 22,
        "quality": "rare",
        "category": "Consumable",
        "ingredients": {"wolf_pelt": 2, "wolf_claw": 2},
        "result": {"effect": "speed_boost_60", "name": "Swift Tonic", "color": (120, 200, 230), "rarity": "rare"},
    },
    {
        "id": "craft_battle_oil",
        "name": "Battle Oil",
        "desc": "+20% damage for 90s",
        "profession": "alchemy",
        "required_skill": 50,
        "xp": 24,
        "quality": "rare",
        "category": "Consumable",
        "ingredients": {"venom_sac": 2, "wolf_fang": 2, "wolf_bone": 1},
        "result": {"effect": "dmg_boost", "name": "Battle Oil", "color": (186, 120, 72), "rarity": "rare"},
    },
    {
        "id": "craft_venom_flask",
        "name": "Venom Flask",
        "desc": "+35% damage for 120s",
        "profession": "alchemy",
        "required_skill": 72,
        "xp": 28,
        "quality": "epic",
        "category": "Consumable",
        "ingredients": {"venom_sac": 3, "wolf_claw": 2, "wolf_bone": 1},
        "result": {"effect": "dmg_boost_120", "name": "Venom Flask", "color": (80, 190, 80), "rarity": "epic"},
    },
    {
        "id": "craft_town_portal_scroll",
        "name": "Town Portal Scroll",
        "desc": "Return instantly to Raven Hollow",
        "profession": "alchemy",
        "required_skill": 88,
        "xp": 28,
        "quality": "rare",
        "category": "Special",
        "ingredients": {"venom_sac": 2, "wolf_bone": 2, "wolf_fang": 2},
        "result": {
            "effect": "town_portal",
            "name": "Town Portal Scroll",
            "desc": "Open a portal and return to Sangeroasa from anywhere.",
            "color": (120, 164, 228),
            "rarity": "rare",
            "icon": (16, 1),
        },
    },
    {
        "id": "craft_elixir_life",
        "name": "Elixir of Life",
        "desc": "Restore full HP and mana",
        "profession": "alchemy",
        "required_skill": 108,
        "xp": 34,
        "quality": "legendary",
        "category": "Consumable",
        "ingredients": {"wolf_pelt": 4, "venom_sac": 3, "wolf_bone": 3},
        "result": {"effect": "full_restore", "name": "Elixir of Life", "color": (220, 180, 60), "rarity": "legendary"},
    },
    # Blacksmithing
    {
        "id": "craft_pack_blade",
        "name": "Pack Blade",
        "desc": "Forged weapon with balanced damage",
        "profession": "blacksmithing",
        "required_skill": 14,
        "xp": 17,
        "quality": "common",
        "category": "Equipment",
        "ingredients": {"wolf_fang": 2, "wolf_claw": 2},
        "result": {
            "name": "Pack Blade",
            "item_type": "equipment",
            "equip_slot": "weapon",
            "rarity": "common",
            "color": (180, 175, 160),
            "stats": {"basic_damage": 5.0, "spell_power": 1.0},
            "icon": (3, 3),
            "desc": "A reliable forged blade for close combat.",
        },
    },
    {
        "id": "craft_pelt_cuirass",
        "name": "Pelt Cuirass",
        "desc": "Sturdy chest armor from reinforced pelts",
        "profession": "blacksmithing",
        "required_skill": 30,
        "xp": 20,
        "quality": "rare",
        "category": "Equipment",
        "ingredients": {"wolf_pelt": 4, "wolf_bone": 2, "wolf_fang": 1},
        "result": {
            "name": "Pelt Cuirass",
            "item_type": "equipment",
            "equip_slot": "chest",
            "rarity": "rare",
            "color": (140, 110, 80),
            "stats": {"armor": 16.0, "max_hp": 10.0},
            "icon": (12, 5),
            "desc": "Hardened leather and bone plates for frontline fights.",
        },
    },
    {
        "id": "craft_predator_helm",
        "name": "Predator Helm",
        "desc": "Heavy helm tuned for aggressive hunters",
        "profession": "blacksmithing",
        "required_skill": 46,
        "xp": 24,
        "quality": "rare",
        "category": "Equipment",
        "ingredients": {"wolf_fang": 4, "wolf_bone": 3},
        "result": {
            "name": "Predator Helm",
            "item_type": "equipment",
            "equip_slot": "head",
            "rarity": "rare",
            "color": (160, 140, 100),
            "stats": {"armor": 18.0, "basic_damage": 3.0},
            "icon": (15, 6),
            "desc": "A fang-lined helm built to pressure targets.",
        },
    },
    {
        "id": "craft_claw_gauntlets",
        "name": "Claw Gauntlets",
        "desc": "Weighted gloves for stronger strikes",
        "profession": "blacksmithing",
        "required_skill": 62,
        "xp": 26,
        "quality": "epic",
        "category": "Equipment",
        "ingredients": {"wolf_claw": 5, "wolf_bone": 3, "venom_sac": 1},
        "result": {
            "name": "Claw Gauntlets",
            "item_type": "equipment",
            "equip_slot": "hands",
            "rarity": "epic",
            "color": (120, 90, 160),
            "stats": {"basic_damage": 4.0, "armor": 12.0},
            "icon": (13, 3),
            "desc": "Reinforced gauntlets sharpened with beast claws.",
        },
    },
    {
        "id": "craft_tracker_leggings",
        "name": "Tracker Leggings",
        "desc": "Layered legguards made for quick hunts",
        "profession": "blacksmithing",
        "required_skill": 72,
        "xp": 27,
        "quality": "epic",
        "category": "Equipment",
        "ingredients": {"wolf_pelt": 4, "wolf_claw": 3, "wolf_bone": 2},
        "result": {
            "name": "Tracker Leggings",
            "item_type": "equipment",
            "equip_slot": "pants",
            "rarity": "epic",
            "color": (92, 118, 86),
            "stats": {"armor": 12.0, "max_hp": 10.0, "move_speed": 0.03},
            "desc": "Flexible plated leggings that keep your stance light.",
        },
    },
    {
        "id": "craft_hunter_greaves",
        "name": "Hunter Greaves",
        "desc": "Mobile greaves for tactical repositioning",
        "profession": "blacksmithing",
        "required_skill": 80,
        "xp": 29,
        "quality": "epic",
        "category": "Equipment",
        "ingredients": {"wolf_pelt": 5, "wolf_bone": 4, "wolf_claw": 3},
        "result": {
            "name": "Hunter Greaves",
            "item_type": "equipment",
            "equip_slot": "feet",
            "rarity": "epic",
            "color": (100, 140, 90),
            "stats": {"armor": 14.0, "move_speed": 0.05},
            "icon": (14, 3),
            "desc": "Boot plates crafted for relentless pursuit.",
        },
    },
    {
        "id": "craft_moonsteel_bulwark",
        "name": "Moonsteel Bulwark",
        "desc": "Legendary off-hand with defense and power",
        "profession": "blacksmithing",
        "required_skill": 105,
        "xp": 34,
        "quality": "legendary",
        "category": "Equipment",
        "ingredients": {"wolf_bone": 7, "wolf_fang": 6, "venom_sac": 3},
        "result": {
            "name": "Moonsteel Bulwark",
            "item_type": "equipment",
            "equip_slot": "offhand",
            "rarity": "legendary",
            "color": (200, 190, 140),
            "stats": {"armor": 28.0, "damage_reduction": 0.05, "spell_power": 4.0},
            "icon": (11, 2),
            "desc": "A masterwork ward infused with wilderness essence.",
        },
    },
    # Runecrafting
    {
        "id": "craft_iron_coat",
        "name": "Iron Coat",
        "desc": "+15 max HP (permanent, stacks 3x)",
        "profession": "runecrafting",
        "required_skill": 12,
        "xp": 16,
        "quality": "common",
        "category": "Enhancement",
        "ingredients": {"wolf_fang": 2, "wolf_bone": 2},
        "result": {"effect": "max_hp_15", "name": "Iron Coat", "color": (170, 140, 90), "rarity": "common"},
    },
    {
        "id": "craft_fang_amulet",
        "name": "Fang Amulet",
        "desc": "+0.5 mana regen/s (permanent, stacks 3x)",
        "profession": "runecrafting",
        "required_skill": 28,
        "xp": 19,
        "quality": "rare",
        "category": "Enhancement",
        "ingredients": {"wolf_fang": 4, "venom_sac": 2},
        "result": {"effect": "mana_regen_05", "name": "Fang Amulet", "color": (100, 160, 220), "rarity": "rare"},
    },
    {
        "id": "craft_bone_charm",
        "name": "Bone Charm",
        "desc": "+1 skill point",
        "profession": "runecrafting",
        "required_skill": 42,
        "xp": 22,
        "quality": "epic",
        "category": "Special",
        "ingredients": {"wolf_bone": 5, "wolf_fang": 3},
        "result": {"effect": "skill_point", "name": "Bone Charm", "color": (200, 190, 160), "rarity": "epic"},
    },
    {
        "id": "craft_rune_focus",
        "name": "Rune Focus",
        "desc": "Arcane weapon that boosts spell damage",
        "profession": "runecrafting",
        "required_skill": 58,
        "xp": 24,
        "quality": "epic",
        "category": "Equipment",
        "ingredients": {"venom_sac": 3, "wolf_bone": 3, "wolf_fang": 2},
        "result": {
            "name": "Rune Focus",
            "item_type": "equipment",
            "equip_slot": "weapon",
            "rarity": "epic",
            "color": (100, 80, 200),
            "stats": {"spell_power": 9.0, "max_mana": 12.0},
            "icon": (6, 4),
            "desc": "A rune-bound weapon channeling stable arcane force.",
        },
    },
    {
        "id": "craft_shadow_signet",
        "name": "Shadow Signet",
        "desc": "Ring that sharpens cooldown control",
        "profession": "runecrafting",
        "required_skill": 74,
        "xp": 27,
        "quality": "epic",
        "category": "Equipment",
        "ingredients": {"venom_sac": 3, "wolf_claw": 4, "wolf_fang": 3},
        "result": {
            "name": "Shadow Signet",
            "item_type": "equipment",
            "equip_slot": "ring",
            "rarity": "epic",
            "color": (80, 60, 120),
            "stats": {"cooldown_reduction": 0.04, "spell_power": 5.0},
            "icon": (17, 5),
            "desc": "A signet etched to tighten spell cadence.",
        },
    },
    {
        "id": "craft_guardian_charm",
        "name": "Guardian Charm",
        "desc": "Amulet for survivability and spell focus",
        "profession": "runecrafting",
        "required_skill": 92,
        "xp": 30,
        "quality": "legendary",
        "category": "Equipment",
        "ingredients": {"wolf_bone": 6, "wolf_fang": 5, "venom_sac": 4},
        "result": {
            "name": "Guardian Charm",
            "item_type": "equipment",
            "equip_slot": "amulet",
            "rarity": "legendary",
            "color": (220, 200, 100),
            "stats": {"max_hp": 18.0, "max_mana": 18.0, "spell_power": 6.0},
            "icon": (11, 7),
            "desc": "An engraved talisman carrying ancient warding magic.",
        },
    },
]




from game.data.spell_layout import *  # spell hotbar key labels & class slot layout




# clamp / exp_smooth / rotate_vec are imported from game.utils (see top of file).










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








# ═══════════════════════════════════════════════════════════════════
# LIVE FARM ANIMALS — animated chickens, pigs, sheep inside pens
# ═══════════════════════════════════════════════════════════════════





# ── Palette-swap helpers ──────────────────────────────────────────────────────









# ─── AAA HUD: persistent state for damage / spend flashes & lerping bars ───


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


def ensure_level_decor_folders() -> None:
    os.makedirs(LEVEL_DECOR_ROOT, exist_ok=True)
    for scope in LEVEL_DECOR_SCOPES:
        os.makedirs(os.path.join(LEVEL_DECOR_ROOT, scope), exist_ok=True)




def _level_decor_display_name(filename: str) -> str:
    stem = os.path.splitext(str(filename))[0]
    normalized = stem.replace("-", " ").replace("_", " ").strip().lower()
    raw_tokens = [token for token in normalized.split() if token]
    while raw_tokens and raw_tokens[0].isdigit():
        raw_tokens.pop(0)
    tokens = [token for token in raw_tokens if token not in {"prop"}]
    if not tokens:
        return "Decor"

    phrase = " ".join(tokens)
    name_map = {
        "house stone": "Stone House",
        "house timber": "Timber House",
        "house plaster": "Plaster House",
        "house forge": "Forge House",
        "crate": "Wood Crate",
        "barrel": "Weathered Barrel",
        "cart": "Hand Cart",
        "lamp": "Street Lamp",
        "well": "Village Well",
        "tree": "Blackwood Tree",
        "banner": "War Banner",
        "forge": "Forge Rack",
        "fence": "Fence Section",
    }
    mapped = name_map.get(phrase)
    if mapped:
        return mapped
    if tokens[0] == "house" and len(tokens) > 1:
        return f"{' '.join(token.title() for token in tokens[1:])} House"
    return " ".join(token.title() for token in tokens)


def _level_decor_group_name(filename: str) -> str:
    lower_name = str(filename).lower()
    if "house" in lower_name:
        return "Structures"
    if "prop" in lower_name:
        return "Props"
    if "tree" in lower_name or "bush" in lower_name:
        return "Nature"
    return "Decor"






def load_medieval_generated_asset_manager() -> AssetManager:
    manager = AssetManager(MEDIEVAL_PACK_ROOT)
    manager.load()
    return manager


def merge_generated_assets_into_level_decor_assets(level_decor_assets: Dict[str, object], manager: AssetManager) -> None:
    shared_entries = level_decor_assets.get("shared")
    if not isinstance(shared_entries, list):
        level_decor_assets["shared"] = []
        shared_entries = level_decor_assets["shared"]
    lookup = level_decor_assets.get("by_id")
    if not isinstance(lookup, dict):
        level_decor_assets["by_id"] = {}
        lookup = level_decor_assets["by_id"]
    for entry in manager.entries:
        asset_id = str(entry.get("id", ""))
        if not asset_id or asset_id in lookup:
            continue
        shared_entries.append(entry)
        lookup[asset_id] = entry


def _prepare_alpha_surface(
    surface: pygame.Surface,
    padding: int = 8,
    anchor_y: Optional[float] = None,
) -> Tuple[pygame.Surface, int]:
    bounds = surface.get_bounding_rect()
    if bounds.width <= 0 or bounds.height <= 0:
        return surface.copy(), 0
    padded = bounds.inflate(padding * 2, padding * 2)
    padded.clamp_ip(surface.get_rect())
    cropped = pygame.Surface((padded.width, padded.height), pygame.SRCALPHA)
    cropped.blit(surface, (0, 0), padded)
    if anchor_y is None:
        anchor_local = float(bounds.bottom - padded.top)
    else:
        anchor_local = float(anchor_y) - float(padded.top)
    anchor_local = clamp(anchor_local, 0.0, float(cropped.get_height()))
    anchor_offset = max(0, int(round(float(cropped.get_height()) - anchor_local)))
    return cropped, anchor_offset


def _draw_with_seed(seed: int, callback: object) -> None:
    state = random.getstate()
    random.seed(seed)
    try:
        callback()
    finally:
        random.setstate(state)


def _render_builtin_decor_surface(
    draw_callback: object,
    canvas_size: Tuple[int, int] = (320, 320),
    baseline_offset: int = 26,
    padding: int = 10,
) -> Tuple[pygame.Surface, int]:
    canvas = pygame.Surface(canvas_size, pygame.SRCALPHA)
    anchor_x = canvas_size[0] // 2
    anchor_y = canvas_size[1] - baseline_offset
    draw_callback(canvas, anchor_x, anchor_y)
    return _prepare_alpha_surface(canvas, padding=padding, anchor_y=float(anchor_y))


def build_builtin_level_decor_pack() -> List[Dict[str, object]]:
    entries: List[Dict[str, object]] = []

    def add_builtin(
        asset_key: str,
        name: str,
        scope: str,
        group: str,
        draw_callback: object,
        source_kind: str = "pack",
        canvas_size: Tuple[int, int] = (320, 320),
        baseline_offset: int = 26,
        padding: int = 10,
    ) -> None:
        sprite, anchor_offset = _render_builtin_decor_surface(
            draw_callback,
            canvas_size=canvas_size,
            baseline_offset=baseline_offset,
            padding=padding,
        )
        entries.append(
            {
                "id": f"builtin:{scope}:{asset_key}",
                "scope": scope,
                "source": source_kind,
                "asset_pack": "project",
                "filename": f"{asset_key}.png",
                "name": name,
                "group": group,
                "path": "<builtin-pack>",
                "surface": sprite,
                "thumbnail": _scale_surface_to_fit(sprite, 68),
                "size": sprite.get_size(),
                "anchor_offset": anchor_offset,
                "layer": "OBJECT",
                "tags": ["decor", group.lower(), source_kind],
                "origin": {"mode": "bottom_center", "x": 0.5, "y": 1.0},
                "collision": None,
            }
        )

    add_builtin(
        "supply_cache",
        "Supply Cache",
        "shared",
        "Props",
        lambda surf, x, y: (
            _draw_with_seed(1201, lambda: draw_hd_barrel(surf, x - 34, y)),
            _draw_with_seed(1202, lambda: draw_hd_barrel(surf, x + 18, y + 2)),
            draw_wood_crate(surf, x + 56, y + 2, 40),
            draw_wood_crate(surf, x + 18, y - 8, 34),
        ),
        canvas_size=(250, 210),
        baseline_offset=28,
    )
    add_builtin(
        "traveler_wagon",
        "Traveler Wagon",
        "shared",
        "Props",
        lambda surf, x, y: (
            _draw_with_seed(1210, lambda: draw_hd_cart(surf, x, y)),
            _draw_with_seed(1211, lambda: draw_hd_hay(surf, x - 44, y - 2)),
            _draw_with_seed(1212, lambda: draw_hd_barrel(surf, x + 54, y + 1)),
        ),
        canvas_size=(280, 220),
        baseline_offset=26,
    )
    add_builtin(
        "mossy_boulder_cluster",
        "Mossy Boulder Cluster",
        "shared",
        "Nature",
        lambda surf, x, y: (
            draw_boulder(surf, x - 34, y, 1.0),
            draw_boulder(surf, x + 10, y - 3, 0.88),
            draw_boulder(surf, x + 52, y + 1, 0.68),
            pygame.draw.ellipse(surf, (44, 72, 48), (x - 52, y - 8, 84, 12)),
            pygame.draw.ellipse(surf, (52, 82, 56), (x - 10, y - 6, 62, 10)),
        ),
        canvas_size=(250, 180),
        baseline_offset=24,
    )

    add_builtin(
        "saint_quarter_house",
        "Saint Quarter House",
        "town",
        "Structures",
        lambda surf, x, y: draw_district_house(surf, x, y - 2, 1.05, 2101, "saint"),
        canvas_size=(320, 320),
        baseline_offset=28,
    )
    add_builtin(
        "rookside_cottage",
        "Rookside Cottage",
        "town",
        "Structures",
        lambda surf, x, y: draw_district_house(surf, x, y, 0.96, 2102, "rook"),
        canvas_size=(300, 300),
        baseline_offset=28,
    )
    add_builtin(
        "ember_forgefront",
        "Ember Forgefront",
        "town",
        "Structures",
        lambda surf, x, y: (
            draw_district_house(surf, x, y - 2, 1.02, 2103, "ember"),
            _draw_with_seed(1220, lambda: draw_hd_barrel(surf, x - 64, y + 2)),
            draw_wood_crate(surf, x + 66, y + 1, 34),
            pygame.draw.circle(surf, (255, 160, 74, 70), (x + 48, y - 62), 12),
        ),
        canvas_size=(340, 320),
        baseline_offset=28,
    )
    add_builtin(
        "lantern_market",
        "Lantern Market",
        "town",
        "Props",
        lambda surf, x, y: (
            draw_market_stall(surf, x, y, 1.15),
            draw_wood_crate(surf, x - 52, y + 2, 34),
            _draw_with_seed(1230, lambda: draw_hd_barrel(surf, x + 56, y + 2)),
            draw_lamppost(surf, x + 102, y + 4, lit=True),
        ),
        canvas_size=(360, 250),
        baseline_offset=30,
    )
    add_builtin(
        "village_well",
        "Village Well",
        "town",
        "Props",
        lambda surf, x, y: (
            draw_well(surf, x, y),
            _draw_with_seed(1240, lambda: draw_hd_barrel(surf, x + 54, y + 4)),
            draw_wood_crate(surf, x - 52, y + 2, 32),
        ),
        canvas_size=(280, 240),
        baseline_offset=28,
    )
    add_builtin(
        "roadside_reliquary",
        "Roadside Reliquary",
        "town",
        "Relics",
        lambda surf, x, y: (
            draw_transylvanian_asset(surf, x, y, "troita"),
            draw_grave_stone(surf, x - 36, y - 2, 1),
            draw_grave_stone(surf, x + 34, y - 1, 2),
            pygame.draw.circle(surf, (255, 186, 96, 72), (x - 14, y - 24), 5),
            pygame.draw.circle(surf, (255, 186, 96, 72), (x + 12, y - 26), 5),
        ),
        canvas_size=(260, 250),
        baseline_offset=26,
    )
    add_builtin(
        "maramures_gate",
        "Maramures Gate",
        "town",
        "Structures",
        lambda surf, x, y: (
            draw_transylvanian_asset(surf, x, y, "wooden_gate"),
            draw_lamppost(surf, x - 82, y + 4, lit=True),
            draw_lamppost(surf, x + 82, y + 4, lit=True),
        ),
        canvas_size=(340, 260),
        baseline_offset=26,
    )

    add_builtin(
        "gnarled_dead_tree",
        "Gnarled Dead Tree",
        "wilderness",
        "Nature",
        lambda surf, x, y: (
            pygame.draw.ellipse(surf, (16, 18, 16), (x - 70, y - 8, 140, 18)),
            draw_dead_tree(surf, x, y, 1.15),
            draw_boulder(surf, x - 42, y + 1, 0.74),
            draw_boulder(surf, x + 46, y, 0.58),
        ),
        canvas_size=(280, 260),
        baseline_offset=26,
    )
    add_builtin(
        "black_pine_cluster",
        "Black Pine Cluster",
        "wilderness",
        "Nature",
        lambda surf, x, y: (
            draw_pine_tree(surf, x - 42, y + 4, 0.96),
            draw_pine_tree(surf, x + 8, y, 1.14),
            draw_pine_tree(surf, x + 58, y + 8, 0.84),
            pygame.draw.ellipse(surf, (34, 52, 34), (x - 70, y - 6, 148, 14)),
        ),
        canvas_size=(300, 280),
        baseline_offset=28,
    )
    add_builtin(
        "witch_stone_cairn",
        "Witch Stone Cairn",
        "wilderness",
        "Relics",
        lambda surf, x, y: (
            draw_boulder(surf, x - 40, y + 3, 0.92),
            draw_boulder(surf, x + 4, y - 2, 1.04),
            draw_boulder(surf, x + 48, y + 4, 0.74),
            draw_grave_stone(surf, x + 2, y - 4, 0),
            pygame.draw.circle(surf, (94, 166, 118, 44), (x + 2, y - 28), 18),
        ),
        canvas_size=(260, 210),
        baseline_offset=24,
    )
    add_builtin(
        "bone_stake_totem",
        "Bone Stake Totem",
        "wilderness",
        "Relics",
        lambda surf, x, y: (
            draw_transylvanian_asset(surf, x, y, "impaled_stake"),
            draw_boulder(surf, x - 28, y + 2, 0.62),
            draw_boulder(surf, x + 28, y + 1, 0.54),
            pygame.draw.line(surf, (140, 22, 28), (x, y - 42), (x + 8, y - 16), 2),
        ),
        canvas_size=(220, 220),
        baseline_offset=24,
    )
    add_builtin(
        "fallen_log",
        "Fallen Log",
        "wilderness",
        "Nature",
        lambda surf, x, y: (
            pygame.draw.ellipse(surf, (18, 20, 16), (x - 78, y - 8, 156, 16)),
            pygame.draw.rect(surf, (78, 56, 38), (x - 68, y - 24, 126, 18), border_radius=8),
            pygame.draw.rect(surf, (42, 30, 22), (x - 68, y - 24, 126, 18), 2, border_radius=8),
            pygame.draw.circle(surf, (106, 84, 58), (x + 56, y - 15), 11),
            pygame.draw.circle(surf, (54, 40, 28), (x + 56, y - 15), 11, 2),
            pygame.draw.circle(surf, (168, 60, 116), (x - 28, y - 10), 4),
            pygame.draw.circle(surf, (168, 60, 116), (x - 16, y - 12), 5),
            pygame.draw.circle(surf, (180, 74, 128), (x - 4, y - 10), 4),
            pygame.draw.ellipse(surf, (52, 86, 48), (x - 64, y - 10, 42, 10)),
        ),
        canvas_size=(260, 180),
        baseline_offset=22,
    )
    add_builtin(
        "moonlit_grave",
        "Moonlit Grave Marker",
        "wilderness",
        "Relics",
        lambda surf, x, y: (
            draw_grave_stone(surf, x, y, 3),
            draw_dead_tree(surf, x - 48, y + 2, 0.62),
            draw_boulder(surf, x + 42, y + 3, 0.58),
            pygame.draw.circle(surf, (182, 206, 236, 34), (x + 2, y - 30), 20),
        ),
        canvas_size=(240, 220),
        baseline_offset=24,
    )

    add_builtin(
        "barrel",
        "Weathered Barrel",
        "shared",
        "Scene",
        lambda surf, x, y: _draw_with_seed(2201, lambda: draw_hd_barrel(surf, x, y)),
        source_kind="scene",
        canvas_size=(150, 170),
        baseline_offset=26,
    )
    add_builtin(
        "hay_bale",
        "Tied Hay Bale",
        "shared",
        "Scene",
        lambda surf, x, y: _draw_with_seed(2202, lambda: draw_hd_hay(surf, x, y)),
        source_kind="scene",
        canvas_size=(170, 150),
        baseline_offset=24,
    )
    add_builtin(
        "wood_crate",
        "Wood Crate",
        "shared",
        "Scene",
        lambda surf, x, y: draw_wood_crate(surf, x, y, 40),
        source_kind="scene",
        canvas_size=(170, 150),
        baseline_offset=24,
    )
    add_builtin(
        "hand_cart",
        "Hand Cart",
        "shared",
        "Scene",
        lambda surf, x, y: _draw_with_seed(2203, lambda: draw_hd_cart(surf, x, y)),
        source_kind="scene",
        canvas_size=(220, 180),
        baseline_offset=24,
    )
    add_builtin(
        "field_boulder",
        "Field Boulder",
        "shared",
        "Scene",
        lambda surf, x, y: draw_boulder(surf, x, y, 0.95),
        source_kind="scene",
        canvas_size=(180, 150),
        baseline_offset=22,
    )

    add_builtin(
        "street_lamp",
        "Street Lamp",
        "town",
        "Scene",
        lambda surf, x, y: draw_lamppost(surf, x, y, lit=True),
        source_kind="scene",
        canvas_size=(180, 250),
        baseline_offset=24,
    )
    add_builtin(
        "market_stall",
        "Market Stall",
        "town",
        "Scene",
        lambda surf, x, y: draw_market_stall(surf, x, y, 1.0),
        source_kind="scene",
        canvas_size=(240, 220),
        baseline_offset=26,
    )
    add_builtin(
        "garlic_stand_small",
        "Garlic Stand",
        "town",
        "Scene",
        lambda surf, x, y: draw_transylvanian_asset(surf, x, y, "garlic_stand"),
        source_kind="scene",
        canvas_size=(170, 160),
        baseline_offset=24,
    )
    add_builtin(
        "haystack_cone",
        "Haystack",
        "town",
        "Scene",
        lambda surf, x, y: draw_transylvanian_asset(surf, x, y, "haystack"),
        source_kind="scene",
        canvas_size=(190, 190),
        baseline_offset=24,
    )
    add_builtin(
        "coffin_prop",
        "Village Coffin",
        "town",
        "Scene",
        lambda surf, x, y: draw_transylvanian_asset(surf, x, y, "coffin"),
        source_kind="scene",
        canvas_size=(170, 180),
        baseline_offset=24,
    )

    add_builtin(
        "pine_tree",
        "Pine Tree",
        "wilderness",
        "Scene",
        lambda surf, x, y: draw_pine_tree(surf, x, y, 1.0),
        source_kind="scene",
        canvas_size=(230, 290),
        baseline_offset=26,
    )
    add_builtin(
        "dead_tree",
        "Dead Tree",
        "wilderness",
        "Scene",
        lambda surf, x, y: draw_dead_tree(surf, x, y, 1.0),
        source_kind="scene",
        canvas_size=(230, 300),
        baseline_offset=26,
    )
    add_builtin(
        "grave_marker",
        "Grave Marker",
        "wilderness",
        "Scene",
        lambda surf, x, y: draw_grave_stone(surf, x, y, 2),
        source_kind="scene",
        canvas_size=(170, 180),
        baseline_offset=24,
    )
    add_builtin(
        "bone_stake",
        "Bone Stake",
        "wilderness",
        "Scene",
        lambda surf, x, y: draw_transylvanian_asset(surf, x, y, "impaled_stake"),
        source_kind="scene",
        canvas_size=(180, 220),
        baseline_offset=24,
    )
    add_builtin(
        "road_cross",
        "Roadside Cross",
        "wilderness",
        "Scene",
        lambda surf, x, y: draw_transylvanian_asset(surf, x, y, "troita"),
        source_kind="scene",
        canvas_size=(200, 240),
        baseline_offset=24,
    )

    # ── Town Structures & Props ───────────────────────────────────────────────
    add_builtin(
        "church_building",
        "Church",
        "town",
        "Structures",
        lambda surf, x, y: draw_church(surf, x, y),
        source_kind="scene",
        canvas_size=(500, 520),
        baseline_offset=40,
    )
    add_builtin(
        "fire_pit_prop",
        "Fire Pit",
        "town",
        "Scene",
        lambda surf, x, y: draw_fire_pit(surf, x, y),
        source_kind="scene",
        canvas_size=(200, 180),
        baseline_offset=26,
    )
    add_builtin(
        "training_dummy",
        "Training Dummy",
        "shared",
        "Scene",
        lambda surf, x, y: draw_training_dummy(surf, x, y),
        source_kind="scene",
        canvas_size=(180, 220),
        baseline_offset=26,
    )
    add_builtin(
        "fence_horizontal",
        "Fence (Horizontal)",
        "shared",
        "Scene",
        lambda surf, x, y: draw_fence_segment(surf, x - 64, y, length=128),
        source_kind="scene",
        canvas_size=(280, 120),
        baseline_offset=20,
    )
    add_builtin(
        "fence_vertical",
        "Fence (Vertical)",
        "shared",
        "Scene",
        lambda surf, x, y: draw_fence_segment_vertical(surf, x, y - 64, length=128),
        source_kind="scene",
        canvas_size=(120, 280),
        baseline_offset=60,
    )
    add_builtin(
        "sweep_well_prop",
        "Sweep Well",
        "town",
        "Scene",
        lambda surf, x, y: draw_transylvanian_asset(surf, x, y, "sweep_well"),
        source_kind="scene",
        canvas_size=(200, 200),
        baseline_offset=24,
    )
    add_builtin(
        "execution_block_prop",
        "Execution Block",
        "town",
        "Scene",
        lambda surf, x, y: draw_transylvanian_asset(surf, x, y, "execution_block"),
        source_kind="scene",
        canvas_size=(200, 180),
        baseline_offset=24,
    )
    add_builtin(
        "chicken_coop",
        "Chicken Coop",
        "town",
        "Structures",
        lambda surf, x, y: draw_chicken_coop(surf, x, y, seed=3301),
        source_kind="scene",
        canvas_size=(320, 280),
        baseline_offset=30,
    )
    add_builtin(
        "pig_pen",
        "Pig Pen",
        "town",
        "Structures",
        lambda surf, x, y: draw_pig_pen(surf, x, y, seed=3302),
        source_kind="scene",
        canvas_size=(380, 320),
        baseline_offset=34,
    )
    add_builtin(
        "sheep_pen",
        "Sheep Pen",
        "town",
        "Structures",
        lambda surf, x, y: draw_sheep_pen(surf, x, y, seed=3303),
        source_kind="scene",
        canvas_size=(380, 320),
        baseline_offset=34,
    )
    add_builtin(
        "standalone_boulder",
        "Boulder",
        "shared",
        "Scene",
        lambda surf, x, y: draw_boulder(surf, x, y, 1.0),
        source_kind="scene",
        canvas_size=(180, 160),
        baseline_offset=22,
    )
    add_builtin(
        "grave_stone_prop",
        "Grave Stone",
        "town",
        "Scene",
        lambda surf, x, y: draw_grave_stone(surf, x, y, 1),
        source_kind="scene",
        canvas_size=(160, 180),
        baseline_offset=24,
    )
    add_builtin(
        "market_cart_prop",
        "Market Cart",
        "town",
        "Scene",
        lambda surf, x, y: draw_market_cart(surf, x, y, 1.0),
        source_kind="scene",
        canvas_size=(220, 200),
        baseline_offset=26,
    )
    add_builtin(
        "hay_bale_small",
        "Hay Bale (Small)",
        "shared",
        "Scene",
        lambda surf, x, y: draw_hay_bale(surf, x, y, 60, 36),
        source_kind="scene",
        canvas_size=(180, 160),
        baseline_offset=22,
    )

    # ── Vendor Shops ──────────────────────────────────────────────────────────
    _SHOP_CANVAS = (620, 440)
    _SHOP_BASE   = 70

    add_builtin(
        "shop_blacksmith", "Blacksmith Shop", "town", "Structures",
        lambda surf, x, y: _draw_blacksmith_shop(surf, Vector2(x, y), 0, 7001),
        source_kind="scene", canvas_size=_SHOP_CANVAS, baseline_offset=_SHOP_BASE, padding=4,
    )
    add_builtin(
        "shop_alchemist", "Alchemist Shop", "town", "Structures",
        lambda surf, x, y: _draw_alchemist_shop(surf, Vector2(x, y), 0, 7002),
        source_kind="scene", canvas_size=_SHOP_CANVAS, baseline_offset=_SHOP_BASE, padding=4,
    )
    add_builtin(
        "shop_tailor", "Tailor Shop", "town", "Structures",
        lambda surf, x, y: _draw_tailor_shop(surf, Vector2(x, y), 0, 7003),
        source_kind="scene", canvas_size=_SHOP_CANVAS, baseline_offset=_SHOP_BASE, padding=4,
    )
    add_builtin(
        "shop_leatherworker", "Leatherworker Shop", "town", "Structures",
        lambda surf, x, y: _draw_leather_shop(surf, Vector2(x, y), 0, 7004),
        source_kind="scene", canvas_size=_SHOP_CANVAS, baseline_offset=_SHOP_BASE, padding=4,
    )
    add_builtin(
        "shop_merchant", "Merchant Shop", "town", "Structures",
        lambda surf, x, y: _draw_merchant_shop(surf, Vector2(x, y), 0, 7005),
        source_kind="scene", canvas_size=_SHOP_CANVAS, baseline_offset=_SHOP_BASE, padding=4,
    )
    add_builtin(
        "shop_baker", "Baker Shop", "town", "Structures",
        lambda surf, x, y: _draw_baker_shop(surf, Vector2(x, y), 0, 7006),
        source_kind="scene", canvas_size=_SHOP_CANVAS, baseline_offset=_SHOP_BASE, padding=4,
    )
    add_builtin(
        "shop_guard", "Guard Post", "town", "Structures",
        lambda surf, x, y: _draw_guard_shop(surf, Vector2(x, y), 0, 7007),
        source_kind="scene", canvas_size=_SHOP_CANVAS, baseline_offset=_SHOP_BASE, padding=4,
    )
    add_builtin(
        "shop_herbalist", "Herbalist Shop", "town", "Structures",
        lambda surf, x, y: _draw_herbalist_shop(surf, Vector2(x, y), 0, 7008),
        source_kind="scene", canvas_size=_SHOP_CANVAS, baseline_offset=_SHOP_BASE, padding=4,
    )
    add_builtin(
        "shop_sailor", "Sailor Shop", "town", "Structures",
        lambda surf, x, y: _draw_sailor_shop(surf, Vector2(x, y), 0, 7009),
        source_kind="scene", canvas_size=_SHOP_CANVAS, baseline_offset=_SHOP_BASE, padding=4,
    )
    add_builtin(
        "shop_miller", "Miller Shop", "town", "Structures",
        lambda surf, x, y: _draw_miller_shop(surf, Vector2(x, y), 0, 7010),
        source_kind="scene", canvas_size=_SHOP_CANVAS, baseline_offset=_SHOP_BASE, padding=4,
    )
    add_builtin(
        "shop_tanner", "Tanner Shop", "town", "Structures",
        lambda surf, x, y: _draw_tanner_shop(surf, Vector2(x, y), 0, 7011),
        source_kind="scene", canvas_size=_SHOP_CANVAS, baseline_offset=_SHOP_BASE, padding=4,
    )
    add_builtin(
        "shop_cooper", "Cooper Shop", "town", "Structures",
        lambda surf, x, y: _draw_cooper_shop(surf, Vector2(x, y), 0, 7012),
        source_kind="scene", canvas_size=_SHOP_CANVAS, baseline_offset=_SHOP_BASE, padding=4,
    )

    return entries


def load_level_decor_assets() -> Dict[str, object]:
    ensure_level_decor_folders()
    buckets: Dict[str, List[Dict[str, object]]] = {scope: [] for scope in LEVEL_DECOR_SCOPES}
    by_id: Dict[str, Dict[str, object]] = {}
    def add_asset(path: str, scope: str, source_kind: str) -> None:
        if not os.path.isfile(path):
            return
        filename = os.path.basename(path)
        ext = os.path.splitext(filename)[1].lower()
        if ext not in LEVEL_DECOR_IMAGE_EXTENSIONS:
            return
        try:
            source = pygame.image.load(path).convert_alpha()
        except (pygame.error, FileNotFoundError):
            return
        prepared_surface, anchor_offset = _prepare_alpha_surface(source, padding=3)
        asset_id = f"{source_kind}:{scope}:{filename.lower()}"
        if asset_id in by_id:
            return
        entry = {
            "id": asset_id,
            "scope": scope,
            "source": source_kind,
            "asset_pack": "project",
            "filename": filename,
            "name": _level_decor_display_name(filename),
            "group": _level_decor_group_name(filename),
            "path": path,
            "surface": prepared_surface,
            "thumbnail": _scale_surface_to_fit(prepared_surface, 68),
            "size": prepared_surface.get_size(),
            "anchor_offset": anchor_offset,
            "layer": "OBJECT",
            "tags": ["decor", _level_decor_group_name(filename).lower(), source_kind],
            "origin": {"mode": "bottom_center", "x": 0.5, "y": 1.0},
            "collision": None,
        }
        buckets[scope].append(entry)
        by_id[asset_id] = entry

    def add_builtin_entry(entry: Dict[str, object]) -> None:
        asset_id = str(entry.get("id", "")).strip()
        scope = str(entry.get("scope", "shared")).strip().lower()
        if not asset_id or scope not in buckets or asset_id in by_id:
            return
        buckets[scope].append(entry)
        by_id[asset_id] = entry

    for builtin_entry in build_builtin_level_decor_pack():
        add_builtin_entry(builtin_entry)

    for scope in LEVEL_DECOR_SCOPES:
        folder = os.path.join(LEVEL_DECOR_ROOT, scope)
        if not os.path.isdir(folder):
            continue
        for filename in sorted(os.listdir(folder)):
            add_asset(os.path.join(folder, filename), scope, "custom")

    if os.path.isdir(LEVEL_DECOR_PACK_ROOT):
        seen_families: Set[str] = set()
        for filename in sorted(os.listdir(LEVEL_DECOR_PACK_ROOT)):
            normalized = os.path.splitext(filename)[0].lower()
            while normalized and normalized[0].isdigit():
                normalized = normalized[1:]
            normalized = normalized.lstrip("_")
            if not normalized or normalized in seen_families:
                continue
            seen_families.add(normalized)
            add_asset(os.path.join(LEVEL_DECOR_PACK_ROOT, filename), "shared", "pack")

    for scope in LEVEL_DECOR_SCOPES:
        source_priority = {
            "scene": 0,
            "pack": 1,
            "custom": 2,
        }
        buckets[scope].sort(
            key=lambda entry: (
                source_priority.get(str(entry.get("source", "custom")), 3),
                str(entry.get("group", "")),
                str(entry.get("name", "")),
            )
        )
    medieval_manager = load_medieval_generated_asset_manager()
    level_decor_assets = {
        "shared": buckets["shared"],
        "town": buckets["town"],
        "wilderness": buckets["wilderness"],
        "by_id": by_id,
    }
    merge_generated_assets_into_level_decor_assets(level_decor_assets, medieval_manager)
    level_decor_assets["medieval_manager"] = medieval_manager
    return level_decor_assets


def load_prop_deletions() -> set:
    """Return a set of (kind, x, y) tuples for hardcoded town props that have been deleted."""
    if not os.path.exists(PROP_DELETIONS_PATH):
        return set()
    try:
        with open(PROP_DELETIONS_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        result: set = set()
        for entry in data:
            if not isinstance(entry, dict):
                continue
            kind = str(entry.get("kind", ""))
            x = int(round(float(entry.get("x", 0))))
            y = int(round(float(entry.get("y", 0))))
            result.add((kind, x, y))
        return result
    except Exception:
        return set()


def save_prop_deletions(deletions: set) -> None:
    ensure_level_decor_folders()
    data = [{"kind": k, "x": x, "y": y} for k, x, y in sorted(deletions)]
    try:
        with open(PROP_DELETIONS_PATH, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
    except OSError:
        pass




def save_church_position(x: float, y: float) -> None:
    ensure_level_decor_folders()
    try:
        with open(CHURCH_POSITION_PATH, "w", encoding="utf-8") as fh:
            json.dump({"x": round(x, 2), "y": round(y, 2)}, fh, indent=2)
    except OSError:
        pass


def load_level_decor_layout() -> Dict[str, List[Dict[str, object]]]:
    ensure_level_decor_folders()
    layout: Dict[str, List[Dict[str, object]]] = {
        "town": [],
        "wilderness": [],
        "ice_biome": [],
    }
    if not os.path.exists(LEVEL_DECOR_LAYOUT_PATH):
        return layout
    try:
        with open(LEVEL_DECOR_LAYOUT_PATH, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except (OSError, ValueError, json.JSONDecodeError):
        return layout
    if not isinstance(raw, dict):
        return layout
    for level_name in ("town", "wilderness", "ice_biome"):
        entries = raw.get(level_name, [])
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            asset_id = str(entry.get("asset_id", "")).strip()
            if not asset_id:
                continue
            try:
                x = float(entry.get("x", 0.0))
                y = float(entry.get("y", 0.0))
            except (TypeError, ValueError):
                continue
            try:
                scale = float(entry.get("scale", 1.0))
            except (TypeError, ValueError):
                scale = 1.0
            try:
                rotation = float(entry.get("rotation", 0.0))
            except (TypeError, ValueError):
                rotation = 0.0
            layout[level_name].append(
                {
                    "asset_id": asset_id,
                    "x": x,
                    "y": y,
                    "scale": max(0.25, min(4.0, scale)),
                    "rotation": rotation % 360.0,
                }
            )
    return layout


def load_npc_positions() -> Dict[str, List[Dict[str, object]]]:
    if not os.path.exists(NPC_POSITIONS_PATH):
        return {}
    try:
        with open(NPC_POSITIONS_PATH, "r", encoding="utf-8") as _fh:
            _raw = json.load(_fh)
        if isinstance(_raw, dict):
            return _raw
    except (OSError, ValueError, json.JSONDecodeError):
        pass
    return {}


def load_blacksmith_shop_anchor_record() -> Optional[Dict[str, object]]:
    if not os.path.exists(BLACKSMITH_SHOP_ANCHOR_PATH):
        return None
    try:
        with open(BLACKSMITH_SHOP_ANCHOR_PATH, "r", encoding="utf-8") as _fh:
            raw = json.load(_fh)
        if isinstance(raw, dict):
            return raw
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    return None


def load_blacksmith_shop_anchor() -> Optional[Vector2]:
    raw = load_blacksmith_shop_anchor_record()
    if not isinstance(raw, dict):
        return None
    try:
        x = float(raw.get("x", 0.0))
        y = float(raw.get("y", 0.0))
        return Vector2(x, y)
    except (TypeError, ValueError):
        return None


def save_blacksmith_shop_anchor(
    pos: Vector2,
    auto_place: bool = False,
    character_id: Optional[int] = None,
) -> None:
    ensure_level_decor_folders()
    payload = {
        "x": round(float(pos.x), 2),
        "y": round(float(pos.y), 2),
        "auto_place": bool(auto_place),
    }
    if character_id is not None:
        payload["character_id"] = int(character_id)
    try:
        with open(BLACKSMITH_SHOP_ANCHOR_PATH, "w", encoding="utf-8") as _fh:
            json.dump(payload, _fh, indent=2)
    except OSError:
        pass


def resolve_blacksmith_shop_anchor(
    preferred_pos: Vector2,
    walk_bounds: pygame.Rect,
    obstacles: List[pygame.Rect],
) -> Vector2:
    if BLACKSMITH_SHOP_ANCHOR_MODE == "lamppost":
        return blacksmith_shop_anchor_from_lamppost(walk_bounds)
    if BLACKSMITH_SHOP_ANCHOR_MODE == "player_always":
        return nearest_walkable(Vector2(preferred_pos), walk_bounds, obstacles, VENDOR_SHOP_COLLISION_RADIUS)
    saved = load_blacksmith_shop_anchor()
    if isinstance(saved, Vector2):
        return saved
    if BLACKSMITH_SHOP_ANCHOR_MODE == "player_once":
        return nearest_walkable(Vector2(preferred_pos), walk_bounds, obstacles, VENDOR_SHOP_COLLISION_RADIUS)
    return blacksmith_shop_anchor_from_lamppost(walk_bounds)


def save_npc_positions(vendors: List[Dict[str, object]]) -> None:
    ensure_level_decor_folders()
    entries: List[Dict[str, object]] = []
    for vendor in vendors:
        _pos = vendor.get("pos")
        if isinstance(_pos, Vector2):
            entry: Dict[str, object] = {"name": str(vendor.get("name", "")), "x": round(_pos.x, 2), "y": round(_pos.y, 2)}
            _shop_pos = vendor.get("shop_pos")
            if isinstance(_shop_pos, Vector2):
                entry["shop_x"] = round(_shop_pos.x, 2)
                entry["shop_y"] = round(_shop_pos.y, 2)
            _shop_rot = vendor.get("shop_rotation", 0.0)
            try:
                _shop_rot = float(_shop_rot) % 360.0
            except (TypeError, ValueError):
                _shop_rot = 0.0
            if abs(_shop_rot) > 0.01:
                entry["shop_rotation"] = round(_shop_rot, 2)
            entries.append(entry)
    try:
        with open(NPC_POSITIONS_PATH, "w", encoding="utf-8") as _fh:
            json.dump({"town": entries}, _fh, indent=2)
    except OSError:
        pass


def save_level_decor_layout(layout: Dict[str, List[Dict[str, object]]]) -> None:
    ensure_level_decor_folders()
    payload: Dict[str, List[Dict[str, object]]] = {
        "town": [],
        "wilderness": [],
        "ice_biome": [],
    }
    for level_name in payload:
        entries = layout.get(level_name, [])
        if not isinstance(entries, list):
            continue
        clean_entries: List[Dict[str, object]] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            asset_id = str(entry.get("asset_id", "")).strip()
            if not asset_id:
                continue
            try:
                x = float(entry.get("x", 0.0))
                y = float(entry.get("y", 0.0))
                scale = float(entry.get("scale", 1.0))
                rotation = float(entry.get("rotation", 0.0))
            except (TypeError, ValueError):
                continue
            clean_entries.append(
                {
                    "asset_id": asset_id,
                    "x": round(x, 2),
                    "y": round(y, 2),
                    "scale": round(max(0.25, min(4.0, scale)), 2),
                    "rotation": round(rotation % 360.0, 2),
                }
            )
        payload[level_name] = clean_entries
    with open(LEVEL_DECOR_LAYOUT_PATH, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def level_decor_catalog(
    level_decor_assets: Dict[str, object],
    level_name: str,
    filter_mode: str = "all",
    asset_pack_filter: str = "project",
    category_filter: str = "all",
    search_text: str = "",
) -> List[Dict[str, object]]:
    catalog: List[Dict[str, object]] = []
    shared_entries = level_decor_assets.get("shared", [])
    if isinstance(shared_entries, list):
        catalog.extend(entry for entry in shared_entries if isinstance(entry, dict))
    specific_entries = level_decor_assets.get(level_name, [])
    if isinstance(specific_entries, list):
        catalog.extend(entry for entry in specific_entries if isinstance(entry, dict))
    pack_filter = str(asset_pack_filter).strip().lower()
    if pack_filter in ("project", "medieval_generated"):
        catalog = [entry for entry in catalog if
                   str(entry.get("asset_pack", "project")).lower() == pack_filter
                   or str(entry.get("source", "")).lower() == "scene"]
    filt = str(filter_mode).strip().lower()
    if filt in ("scene", "pack", "custom"):
        catalog = [entry for entry in catalog if str(entry.get("source", "custom")) == filt]
    cat_filter = str(category_filter).strip().lower()
    if cat_filter and cat_filter != "all":
        catalog = [entry for entry in catalog if str(entry.get("category", entry.get("group", ""))).strip().lower() == cat_filter]
    search = str(search_text).strip().lower()
    if search:
        def matches(entry: Dict[str, object]) -> bool:
            name = str(entry.get("name", "")).lower()
            asset_id = str(entry.get("id", "")).lower()
            tags = entry.get("tags", [])
            tag_blob = " ".join(str(tag).lower() for tag in tags) if isinstance(tags, list) else ""
            return search in name or search in asset_id or search in tag_blob
        catalog = [entry for entry in catalog if matches(entry)]
    return catalog


def level_decor_asset_lookup(level_decor_assets: Dict[str, object], asset_id: str) -> Optional[Dict[str, object]]:
    lookup = level_decor_assets.get("by_id", {})
    if not isinstance(lookup, dict):
        return None
    entry = lookup.get(str(asset_id))
    return entry if isinstance(entry, dict) else None


def load_wolf_sprites() -> List[Dict[str, object]]:
    sprites = []
    try:
        sheet_path = "assets/monsters.png"
        if not os.path.exists(sheet_path):
            raise FileNotFoundError(f"Monsters sheet not found at {sheet_path}")
        sheet = pygame.image.load(sheet_path).convert_alpha()
        for i in range(4):
            s = pygame.transform.scale(extract_sheet_tile(sheet, 0, i, 32), (64, 64))
            sprites.append({"name": "Wolf", "sprite": s, "sprite_left": pygame.transform.flip(s, True, False), "radius": 15.0, "hp_mult": 1.0, "dmg_mult": 1.0})
    except (pygame.error, FileNotFoundError):
        s = pygame.Surface((64, 64), pygame.SRCALPHA)
        pygame.draw.circle(s, (100, 100, 100), (32, 32), 20)
        sprites.append({"name": "Wolf", "sprite": s, "sprite_left": s, "radius": 15.0, "hp_mult": 1.0, "dmg_mult": 1.0})
    return sprites


def load_menacing_archetypes() -> List[Dict[str, object]]:
    archetypes = []
    try:
        sheet_path = "assets/monsters.png"
        if not os.path.exists(sheet_path):
            raise FileNotFoundError(f"Monsters sheet not found at {sheet_path}")
        sheet = pygame.image.load(sheet_path).convert_alpha()

        def make_enemy(name: str, row: int, col: int, size: int, radius: float, hp_mult: float, dmg_mult: float) -> Dict[str, object]:
            sprite = pygame.transform.scale(extract_sheet_tile(sheet, row, col, 32), (size, size))
            sprite_right = sprite
            sprite_left = pygame.transform.flip(sprite_right, True, False)
            anim_frames = None
            return {
                "name": name,
                "sprite": sprite_right,
                "sprite_left": sprite_left,
                "radius": radius,
                "hp_mult": hp_mult,
                "dmg_mult": dmg_mult,
                "anim_frames": anim_frames,
            }
        
        # Wolves (existing)
        for i in range(4):
            archetypes.append(make_enemy("Wolf", 0, i, 64, 15.0, 1.0, 1.0))
            
        # Bear
        archetypes.append(make_enemy("Grizzly Bear", 6, 2, 80, 22.0, 1.8, 1.4))

        # Dire Wolf
        archetypes.append(make_enemy("Dire Wolf", 5, 3, 72, 18.0, 1.3, 1.2))

    except (pygame.error, FileNotFoundError):
        if not archetypes:
            s = pygame.Surface((64, 64), pygame.SRCALPHA)
            pygame.draw.circle(s, (100, 100, 100), (32, 32), 20)
            archetypes.append({"name": "Wolf", "sprite": s, "sprite_left": s, "radius": 15.0, "hp_mult": 1.0, "dmg_mult": 1.0})
    return archetypes


def load_passive_archetypes() -> List[Dict[str, object]]:
    archetypes = []
    try:
        sheet_path = "assets/monsters.png"
        if not os.path.exists(sheet_path):
            raise FileNotFoundError(f"Monsters sheet not found at {sheet_path}")
        sheet = pygame.image.load(sheet_path).convert_alpha()

        def make_passive(name: str, row: int, col: int, size: int, radius: float, speed: float, max_hp: float) -> Dict[str, object]:
            sprite = pygame.transform.scale(extract_sheet_tile(sheet, row, col, 32), (size, size))
            sprite_right = sprite
            sprite_left = pygame.transform.flip(sprite_right, True, False)
            anim_frames = None
            return {
                "name": name,
                "sprite": sprite_right,
                "sprite_left": sprite_left,
                "radius": radius,
                "speed": speed,
                "max_hp": max_hp,
                "anim_frames": anim_frames,
            }

        archetypes.append(make_passive("Deer", 6, 0, 64, 14.0, 160.0, 40.0))
        archetypes.append(make_passive("Wildfowl", 6, 6, 48, 10.0, 120.0, 25.0))
        archetypes.append(make_passive("Giant Rat", 5, 9, 40, 8.0, 100.0, 20.0))
    except (pygame.error, FileNotFoundError):
        s = pygame.Surface((32, 32), pygame.SRCALPHA); pygame.draw.circle(s, (150, 100, 50), (16, 16), 10)
        archetypes.append({"name": "Rabbit", "sprite": s, "sprite_left": s, "radius": 10.0, "speed": 40.0, "max_hp": 20.0})
    return archetypes

def load_fire_animation() -> List[pygame.Surface]:
    frames = []
    try:
        # Try hyphenated first as per text file convention
        sheet = pygame.image.load("assets/animated-tiles.png").convert_alpha()
    except (pygame.error, FileNotFoundError):
        try:
            sheet = pygame.image.load("assets/animated_tiles.png").convert_alpha()
        except (pygame.error, FileNotFoundError):
            return []
    
    # "9. fire" corresponds to row 8 (0-indexed). Assuming 4 frames of animation.
    tile_size = 32
    row = 8
    for col in range(4):
        if col * tile_size < sheet.get_width() and row * tile_size < sheet.get_height():
            tile = extract_sheet_tile(sheet, row, col, tile_size)
            frames.append(pygame.transform.scale(tile, (64, 64)))
    return frames

def load_animals_sheet() -> Tuple[List[Dict[str, object]], List[Dict[str, object]]]:
    predators = []
    passive = []
    try:
        sheet = pygame.image.load("assets/animals.png").convert_alpha()
        tile_size = 32
        
        def get_sprite(row, col, scale=64):
            if row * tile_size >= sheet.get_height() or col * tile_size >= sheet.get_width():
                return pygame.Surface((scale, scale), pygame.SRCALPHA), pygame.Surface((scale, scale), pygame.SRCALPHA)
            s = extract_sheet_tile(sheet, row, col, tile_size)
            s = pygame.transform.scale(s, (scale, scale))
            return s, pygame.transform.flip(s, True, False)

        def make_creature(name: str, row: int, col: int, scale: int, **extra: object) -> Dict[str, object]:
            sprite, sprite_left = get_sprite(row, col, scale)
            anim_frames = None
            payload: Dict[str, object] = {
                "name": name,
                "sprite": sprite,
                "sprite_left": sprite_left,
                "anim_frames": anim_frames,
            }
            payload.update(extra)
            return payload

        # Predators (Forest Biome)
        # Grizzly Bear (Row 0, Col 0)
        predators.append(make_creature("Grizzly Bear", 0, 0, 80, radius=20.0, hp_mult=1.6, dmg_mult=1.4))
        # Black Bear (Row 0, Col 1)
        predators.append(make_creature("Black Bear", 0, 1, 72, radius=18.0, hp_mult=1.4, dmg_mult=1.2))
        # Cougar (Row 3, Col 2)
        predators.append(make_creature("Cougar", 3, 2, 64, radius=16.0, hp_mult=1.1, dmg_mult=1.4))
        # Fox (Row 4, Col 3)
        predators.append(make_creature("Fox", 4, 3, 56, radius=14.0, hp_mult=0.8, dmg_mult=0.9))
        # Wolf (Row 4, Col 6)
        predators.append(make_creature("Wolf", 4, 6, 64, radius=16.0, hp_mult=1.0, dmg_mult=1.0))
        # Badger (Row 6, Col 2)
        predators.append(make_creature("Badger", 6, 2, 48, radius=12.0, hp_mult=0.9, dmg_mult=1.2))
        # Snake (Row 7, Col 0)
        predators.append(make_creature("Snake", 7, 0, 48, radius=10.0, hp_mult=0.6, dmg_mult=1.1))
        # Boar (Row 9, Col 7)
        predators.append(make_creature("Boar", 9, 7, 64, radius=16.0, hp_mult=1.2, dmg_mult=1.1))

        # Passive (Forest Biome)
        # Beaver (Row 5, Col 1)
        passive.append(make_creature("Beaver", 5, 1, 48, radius=12.0, speed=90.0, max_hp=25.0))
        # Rabbit (Row 6, Col 6)
        passive.append(make_creature("Rabbit", 6, 6, 40, radius=10.0, speed=140.0, max_hp=15.0))
        # Deer (Row 10, Col 1)
        passive.append(make_creature("Deer", 10, 1, 72, radius=16.0, speed=130.0, max_hp=35.0))
        # Owl (Row 11, Col 1)
        passive.append(make_creature("Owl", 11, 1, 48, radius=12.0, speed=110.0, max_hp=20.0))
        # Duck (Row 14, Col 2)
        passive.append(make_creature("Duck", 14, 2, 40, radius=10.0, speed=110.0, max_hp=20.0))
        # Turkey (Row 14, Col 4)
        passive.append(make_creature("Turkey", 14, 4, 56, radius=14.0, speed=100.0, max_hp=30.0))
        # Ram (Row 15, Col 3)
        passive.append(make_creature("Ram", 15, 3, 64, radius=15.0, speed=115.0, max_hp=40.0))
        # Hare (Rabbit variant)
        passive.append(make_creature("Hare", 6, 6, 42, radius=10.0, speed=150.0, max_hp=14.0))
        # Doe (Deer variant)
        passive.append(make_creature("Doe", 10, 1, 68, radius=15.0, speed=134.0, max_hp=32.0))
        # Fawn (Deer juvenile)
        passive.append(make_creature("Fawn", 10, 1, 58, radius=13.0, speed=146.0, max_hp=24.0))
        # Goose (Duck variant)
        passive.append(make_creature("Goose", 14, 2, 44, radius=11.0, speed=118.0, max_hp=22.0))
        # Pheasant (Turkey variant)
        passive.append(make_creature("Pheasant", 14, 4, 48, radius=12.0, speed=112.0, max_hp=24.0))
        # Marmot (Beaver variant)
        passive.append(make_creature("Marmot", 5, 1, 44, radius=11.0, speed=102.0, max_hp=22.0))
        # Crow (Owl variant)
        passive.append(make_creature("Crow", 11, 1, 44, radius=10.0, speed=124.0, max_hp=18.0))
        # Elk (Ram variant)
        passive.append(make_creature("Elk", 15, 3, 72, radius=17.0, speed=108.0, max_hp=52.0))
            
    except (pygame.error, FileNotFoundError):
        # Fallback to monsters.png if animals.png is missing
        return load_menacing_archetypes(), load_passive_archetypes()
        
    return predators, passive


def load_ice_archetypes() -> Tuple[List[Dict[str, object]], List[Dict[str, object]]]:
    """Return (ice_predators, ice_passives) using the animals.png sheet with arctic names/stats."""
    try:
        sheet = pygame.image.load("assets/animals.png").convert_alpha()
        tile_size = 32

        def get_sprite(row: int, col: int, scale: int = 64, frost: bool = False):
            if row * tile_size >= sheet.get_height() or col * tile_size >= sheet.get_width():
                return pygame.Surface((scale, scale), pygame.SRCALPHA), pygame.Surface((scale, scale), pygame.SRCALPHA)
            s = extract_sheet_tile(sheet, row, col, tile_size)
            s = pygame.transform.scale(s, (scale, scale))
            # Only apply a very subtle breath-of-frost overlay for non-white animals
            # — no BLEND_RGBA_MULT (that was making every animal look frozen/dead)
            if frost:
                overlay = pygame.Surface((scale, scale), pygame.SRCALPHA)
                overlay.fill((200, 230, 255, 28))
                s.blit(overlay, (0, 0))
            return s, pygame.transform.flip(s, True, False)

        def make_ice(name: str, row: int, col: int, scale: int, frost: bool = False, **extra: object) -> Dict[str, object]:
            sprite, sprite_left = get_sprite(row, col, scale, frost=frost)
            payload: Dict[str, object] = {
                "name": name,
                "sprite": sprite,
                "sprite_left": sprite_left,
                "anim_frames": None,
            }
            payload.update(extra)
            return payload

        ice_predators = [
            make_ice("Arctic Wolf",  3,  4, 64, frost=True,  radius=16.0, hp_mult=1.2,  dmg_mult=1.15),  # r03c04 grey wolf
            make_ice("Frost Bear",   0,  2, 80, frost=False, radius=20.0, hp_mult=1.8,  dmg_mult=1.5),   # r00c02 polar bear (already white)
            make_ice("Ice Lynx",     3,  2, 64, frost=True,  radius=16.0, hp_mult=1.0,  dmg_mult=1.5),   # r03c02 cougar/lynx
            make_ice("Tundra Fox",   4,  5, 56, frost=True,  radius=14.0, hp_mult=0.7,  dmg_mult=0.85),  # r04c05 pale arctic canid
        ]
        ice_passives = [
            # All naturally arctic animals — no heavy tint needed, they look alive
            make_ice("Arctic Hare",    6,  7, 40, frost=False, radius=10.0, speed=170.0, max_hp=14.0),  # r06c07 white hare
            make_ice("Caribou",       15,  1, 72, frost=False, radius=16.0, speed=118.0, max_hp=44.0),  # r15c01 white reindeer
            make_ice("Mountain Goat", 15,  0, 68, frost=False, radius=15.0, speed=105.0, max_hp=38.0),  # r15c00 white goat
            make_ice("Tundra Yak",    10,  3, 80, frost=True,  radius=18.0, speed=95.0,  max_hp=72.0),  # r10c03 yak (cold-weather ungulate)
            make_ice("Snowy Crane",   11,  0, 52, frost=False, radius=12.0, speed=120.0, max_hp=22.0),  # r11c00 grey/white crane
            make_ice("Penguin",       13,  0, 44, frost=False, radius=11.0, speed=88.0,  max_hp=18.0),  # r13c00 penguin
            make_ice("Snow Goose",    14,  3, 46, frost=False, radius=11.0, speed=130.0, max_hp=16.0),  # r14c03 white goose
            make_ice("Snowy Owl",      5,  4, 48, frost=False, radius=11.0, speed=145.0, max_hp=20.0),  # r05c04 owl
            make_ice("Arctic Fox",     4,  3, 52, frost=True,  radius=12.0, speed=155.0, max_hp=22.0),  # r04c03 pale fox variant
            make_ice("Musk Ox",       10,  1, 84, frost=True,  radius=20.0, speed=80.0,  max_hp=88.0),  # r10c01 heavy bovine
        ]
        return ice_predators, ice_passives
    except (pygame.error, FileNotFoundError):
        return load_menacing_archetypes(), load_passive_archetypes()


# ---------------------------------------------------------------------------
# LPC Animated Sprite Sheet Loaders
# ---------------------------------------------------------------------------



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


def level_decor_asset_layer(asset_entry: Optional[Dict[str, object]]) -> str:
    if not isinstance(asset_entry, dict):
        return "OBJECT"
    return str(asset_entry.get("layer", "OBJECT")).upper()


def level_decor_asset_preview_surface(asset_entry: Dict[str, object], animated: bool = False) -> Optional[pygame.Surface]:
    if not isinstance(asset_entry, dict):
        return None
    frames = asset_entry.get("animation_surfaces", [])
    if animated and isinstance(frames, list) and frames:
        fps = max(1, int(asset_entry.get("animation_fps", 8)))
        idx = (pygame.time.get_ticks() // max(1, int(1000 / fps))) % len(frames)
        frame = frames[idx]
        if isinstance(frame, pygame.Surface):
            return frame
    surface = asset_entry.get("surface")
    return surface if isinstance(surface, pygame.Surface) else None


def level_decor_asset_uses_tile_brush(asset_entry: Optional[Dict[str, object]]) -> bool:
    if not isinstance(asset_entry, dict):
        return False
    tags = asset_entry.get("tags", [])
    if isinstance(tags, list) and any(str(tag).lower() == "tile" for tag in tags):
        return True
    category = str(asset_entry.get("category", asset_entry.get("group", ""))).lower()
    return category in ("terrain", "roads", "water", "frozen terrain", "frozen roads")


def level_decor_asset_uses_scatter(asset_entry: Optional[Dict[str, object]]) -> bool:
    if not isinstance(asset_entry, dict):
        return False
    category = str(asset_entry.get("category", asset_entry.get("group", ""))).lower()
    tags = asset_entry.get("tags", [])
    tag_blob = " ".join(str(tag).lower() for tag in tags) if isinstance(tags, list) else ""
    return category in ("nature", "ice nature") or "nature" in tag_blob


def snap_editor_point_to_grid(world_pos: Vector2, grid_size: int = DECOR_EDITOR_GRID_SIZE) -> Vector2:
    gx = math.floor(world_pos.x / float(grid_size)) * grid_size + grid_size * 0.5
    gy = math.floor(world_pos.y / float(grid_size)) * grid_size + grid_size * 0.5
    return Vector2(gx, gy)


def road_autotile_id_for_mask(mask: Set[str]) -> str:
    mapping = {
        frozenset({"n", "s", "w", "e"}): "road_cross",
        frozenset({"n", "w", "e"}): "road_t_nwe",
        frozenset({"n", "s", "e"}): "road_t_nse",
        frozenset({"n", "s", "w"}): "road_t_nsw",
        frozenset({"s", "w", "e"}): "road_t_swe",
        frozenset({"n", "s"}): "road_straight_ns",
        frozenset({"w", "e"}): "road_straight_we",
        frozenset({"n", "e"}): "road_corner_ne",
        frozenset({"n", "w"}): "road_corner_nw",
        frozenset({"s", "e"}): "road_corner_se",
        frozenset({"s", "w"}): "road_corner_sw",
        frozenset({"n"}): "road_end_n",
        frozenset({"s"}): "road_end_s",
        frozenset({"w"}): "road_end_w",
        frozenset({"e"}): "road_end_e",
    }
    return mapping.get(frozenset(mask), "road_cross")


def frozen_road_autotile_id_for_mask(mask: Set[str]) -> str:
    mapping = {
        frozenset({"n", "s", "w", "e"}): "frozen_road_cross",
        frozenset({"n", "w", "e"}): "frozen_road_t_nwe",
        frozenset({"n", "s", "e"}): "frozen_road_t_nse",
        frozenset({"n", "s", "w"}): "frozen_road_t_nsw",
        frozenset({"s", "w", "e"}): "frozen_road_t_swe",
        frozenset({"n", "s"}): "frozen_road_straight_ns",
        frozenset({"w", "e"}): "frozen_road_straight_we",
        frozenset({"n", "e"}): "frozen_road_corner_ne",
        frozenset({"n", "w"}): "frozen_road_corner_nw",
        frozenset({"s", "e"}): "frozen_road_corner_se",
        frozenset({"s", "w"}): "frozen_road_corner_sw",
        frozenset({"n"}): "frozen_road_end_n",
        frozenset({"s"}): "frozen_road_end_s",
        frozenset({"w"}): "frozen_road_end_w",
        frozenset({"e"}): "frozen_road_end_e",
    }
    return mapping.get(frozenset(mask), "frozen_road_cross")


def get_level_decor_collision_rect(
    instance: Dict[str, object],
    level_decor_assets: Dict[str, object],
    render_cache: Dict[Tuple[str, int, int], pygame.Surface],
    camera: Optional[Vector2] = None,
) -> Optional[pygame.Rect]:
    asset_id = str(instance.get("asset_id", "")).strip()
    if not asset_id:
        return None
    asset_entry = level_decor_asset_lookup(level_decor_assets, asset_id)
    if not isinstance(asset_entry, dict):
        return None
    rect = get_level_decor_instance_rect(instance, level_decor_assets, render_cache, camera)
    if not isinstance(rect, pygame.Rect):
        return None
    try:
        anchor_x = int(round(float(instance.get("x", 0.0))))
        anchor_y = int(round(float(instance.get("y", 0.0))))
    except (TypeError, ValueError):
        anchor_x = rect.centerx
        anchor_y = rect.bottom
    if isinstance(camera, Vector2):
        anchor_x -= int(camera.x)
        anchor_y -= int(camera.y)
    collision = asset_entry.get("collision")
    if not isinstance(collision, dict):
        if level_decor_asset_uses_tile_brush(asset_entry):
            return None
        layer_name = level_decor_asset_layer(asset_entry)
        if layer_name in ("GROUND", "OVERLAY", "VFX"):
            return None
        category_name = str(asset_entry.get("category", asset_entry.get("group", ""))).strip().lower()
        wide_categories = {"houses", "structures"}
        if category_name in wide_categories or "house" in category_name:
            width_ratio = 0.72
            height_ratio = 0.24
        else:
            width_ratio = 0.56
            height_ratio = 0.18
        max_w = max(8, rect.width - 2)
        max_h = max(6, rect.height - 2)
        derived_w = max(8, min(max_w, int(round(rect.width * width_ratio))))
        derived_h = max(6, min(max_h, int(round(rect.height * height_ratio))))
        return pygame.Rect(
            int(anchor_x - derived_w * 0.5),
            int(anchor_y - derived_h + 2),
            derived_w,
            derived_h,
        )
    try:
        scale = float(instance.get("scale", 1.0))
    except (TypeError, ValueError):
        scale = 1.0
    scale = max(0.25, min(4.0, scale))
    try:
        cx = int(round(float(collision.get("x", 0.0)) * scale))
        cy = int(round(float(collision.get("y", 0.0)) * scale))
        cw = max(2, int(round(float(collision.get("w", 0.0)) * scale)))
        ch = max(2, int(round(float(collision.get("h", 0.0)) * scale)))
    except (TypeError, ValueError):
        return None
    return pygame.Rect(rect.left + cx, rect.top + cy, cw, ch)


def build_medieval_demo_layout(level_decor_assets: Dict[str, object]) -> Dict[str, List[Dict[str, object]]]:
    manager = level_decor_assets.get("medieval_manager")
    if not isinstance(manager, AssetManager) or not manager.entries:
        return {"town": [], "wilderness": []}

    generated_entries = [entry for entry in manager.entries if isinstance(entry, dict)]

    def category_entries(name: str) -> List[Dict[str, object]]:
        wanted = str(name).strip().lower()
        return [entry for entry in generated_entries if str(entry.get("category", "")).strip().lower() == wanted]

    def pick_asset(category: str, include: str = "", exclude: str = "") -> Optional[str]:
        include_token = str(include).strip().lower()
        exclude_token = str(exclude).strip().lower()
        candidates = category_entries(category)
        if include_token:
            filtered = [entry for entry in candidates if include_token in str(entry.get("id", "")).lower()]
            if filtered:
                candidates = filtered
        if exclude_token:
            filtered = [entry for entry in candidates if exclude_token not in str(entry.get("id", "")).lower()]
            if filtered:
                candidates = filtered
        if not candidates:
            return None
        candidates.sort(key=lambda entry: str(entry.get("id", "")))
        return str(candidates[0].get("id", ""))

    terrain_ids = [str(entry.get("id", "")) for entry in category_entries("terrain")]
    terrain_ids = [asset_id for asset_id in sorted(terrain_ids) if asset_id]
    terrain_ids = terrain_ids[:6] if terrain_ids else []
    house_ids = [str(entry.get("id", "")) for entry in category_entries("houses") if "prefab" in str(entry.get("id", ""))]
    house_ids = [asset_id for asset_id in sorted(house_ids) if asset_id][:3]
    furniture_ids = [str(entry.get("id", "")) for entry in category_entries("furniture") if str(entry.get("id", ""))]
    furniture_ids = sorted(furniture_ids)[:5]
    container_ids = [str(entry.get("id", "")) for entry in category_entries("containers") if str(entry.get("id", ""))]
    container_ids = sorted(container_ids)[:5]
    nature_ids = [str(entry.get("id", "")) for entry in category_entries("nature") if str(entry.get("id", ""))]
    nature_ids = sorted(nature_ids)
    vfx_ids = [str(entry.get("id", "")) for entry in category_entries("vfx") if str(entry.get("id", ""))]
    vfx_ids = sorted(vfx_ids)

    water_deep_id = pick_asset("water", "deep")
    shore_ids = {
        "n": pick_asset("water", "shore_north"),
        "s": pick_asset("water", "shore_south"),
        "w": pick_asset("water", "shore_west"),
        "e": pick_asset("water", "shore_east"),
        "nw": pick_asset("water", "shore_nw"),
        "ne": pick_asset("water", "shore_ne"),
        "sw": pick_asset("water", "shore_sw"),
        "se": pick_asset("water", "shore_se"),
    }

    town: List[Dict[str, object]] = []
    wilderness: List[Dict[str, object]] = []

    def add_entry(bucket: List[Dict[str, object]], asset_id: Optional[str], x: float, y: float, scale: float = 1.0, rotation: float = 0.0) -> None:
        if not asset_id:
            return
        bucket.append(
            {
                "asset_id": str(asset_id),
                "x": round(float(x), 2),
                "y": round(float(y), 2),
                "scale": round(max(0.25, min(4.0, float(scale))), 2),
                "rotation": round(float(rotation) % 360.0, 2),
            }
        )

    # Town: terrain patchwork, road loop, village core, prop gallery.
    if terrain_ids:
        start_x = 480.0
        start_y = 500.0
        for row in range(4):
            for col in range(6):
                terrain_id = terrain_ids[(row * 6 + col) % len(terrain_ids)]
                add_entry(town, terrain_id, start_x + col * DECOR_EDITOR_GRID_SIZE, start_y + row * DECOR_EDITOR_GRID_SIZE)
    road_loop_tiles = [
        ((0, 0), {"e", "s"}),
        ((1, 0), {"w", "e"}),
        ((2, 0), {"w", "e"}),
        ((3, 0), {"w", "s"}),
        ((0, 1), {"n", "s"}),
        ((3, 1), {"n", "s"}),
        ((0, 2), {"n", "e"}),
        ((1, 2), {"w", "e"}),
        ((2, 2), {"w", "e"}),
        ((3, 2), {"w", "n"}),
    ]
    road_origin_x = 720.0
    road_origin_y = 660.0
    for (tx, ty), mask in road_loop_tiles:
        add_entry(
            town,
            road_autotile_id_for_mask(mask),
            road_origin_x + tx * DECOR_EDITOR_GRID_SIZE,
            road_origin_y + ty * DECOR_EDITOR_GRID_SIZE,
        )
    for idx, house_id in enumerate(house_ids):
        add_entry(town, house_id, 950.0 + idx * 180.0, 600.0 + (idx % 2) * 36.0, scale=1.0)
    for idx, container_id in enumerate(container_ids):
        add_entry(town, container_id, 1120.0 + (idx % 3) * 70.0, 840.0 + (idx // 3) * 66.0)
    for idx, furniture_id in enumerate(furniture_ids):
        add_entry(town, furniture_id, 900.0 + (idx % 3) * 86.0, 980.0 + (idx // 3) * 76.0)

    # Wilderness: terrain patch, pond, road path, nature scatter, VFX row.
    if terrain_ids:
        start_x = 860.0
        start_y = 900.0
        for row in range(3):
            for col in range(6):
                terrain_id = terrain_ids[(row + col) % len(terrain_ids)]
                add_entry(wilderness, terrain_id, start_x + col * DECOR_EDITOR_GRID_SIZE, start_y + row * DECOR_EDITOR_GRID_SIZE)
    if water_deep_id:
        pond_origin_x = 1280.0
        pond_origin_y = 1160.0
        for row in range(3):
            for col in range(4):
                add_entry(wilderness, water_deep_id, pond_origin_x + col * DECOR_EDITOR_GRID_SIZE, pond_origin_y + row * DECOR_EDITOR_GRID_SIZE)
        for col in range(4):
            add_entry(wilderness, shore_ids.get("n"), pond_origin_x + col * DECOR_EDITOR_GRID_SIZE, pond_origin_y - DECOR_EDITOR_GRID_SIZE)
            add_entry(wilderness, shore_ids.get("s"), pond_origin_x + col * DECOR_EDITOR_GRID_SIZE, pond_origin_y + 3 * DECOR_EDITOR_GRID_SIZE)
        for row in range(3):
            add_entry(wilderness, shore_ids.get("w"), pond_origin_x - DECOR_EDITOR_GRID_SIZE, pond_origin_y + row * DECOR_EDITOR_GRID_SIZE)
            add_entry(wilderness, shore_ids.get("e"), pond_origin_x + 4 * DECOR_EDITOR_GRID_SIZE, pond_origin_y + row * DECOR_EDITOR_GRID_SIZE)
        add_entry(wilderness, shore_ids.get("nw"), pond_origin_x - DECOR_EDITOR_GRID_SIZE, pond_origin_y - DECOR_EDITOR_GRID_SIZE)
        add_entry(wilderness, shore_ids.get("ne"), pond_origin_x + 4 * DECOR_EDITOR_GRID_SIZE, pond_origin_y - DECOR_EDITOR_GRID_SIZE)
        add_entry(wilderness, shore_ids.get("sw"), pond_origin_x - DECOR_EDITOR_GRID_SIZE, pond_origin_y + 3 * DECOR_EDITOR_GRID_SIZE)
        add_entry(wilderness, shore_ids.get("se"), pond_origin_x + 4 * DECOR_EDITOR_GRID_SIZE, pond_origin_y + 3 * DECOR_EDITOR_GRID_SIZE)
    road_path_tiles = [
        ((0, 0), {"e"}),
        ((1, 0), {"w", "e"}),
        ((2, 0), {"w", "s"}),
        ((2, 1), {"n", "s"}),
        ((2, 2), {"n", "w"}),
        ((1, 2), {"w", "e"}),
        ((0, 2), {"e"}),
    ]
    road2_origin_x = 980.0
    road2_origin_y = 1280.0
    for (tx, ty), mask in road_path_tiles:
        add_entry(
            wilderness,
            road_autotile_id_for_mask(mask),
            road2_origin_x + tx * DECOR_EDITOR_GRID_SIZE,
            road2_origin_y + ty * DECOR_EDITOR_GRID_SIZE,
        )
    for idx, nature_id in enumerate(nature_ids[:7]):
        add_entry(
            wilderness,
            nature_id,
            1540.0 + (idx % 3) * 110.0 + (idx // 3) * 24.0,
            980.0 + (idx // 3) * 118.0,
            scale=1.0 + (0.08 * (idx % 2)),
        )
    for idx, vfx_id in enumerate(vfx_ids[:6]):
        add_entry(wilderness, vfx_id, 1060.0 + idx * 86.0, 1540.0, scale=1.0)

    return {"town": town, "wilderness": wilderness}


def build_frozen_tundra_layout() -> List[Dict[str, object]]:
    """Hand-crafted Frozen Tundra (ice_biome) decor layout.

    World: ICE_WIDTH=6400, ICE_HEIGHT=4400
    Player spawns at (3200, HORIZON_Y+980) = (3200, 1340)
    Return portal at (3200, HORIZON_Y+920) = (3200, 1280)
    Grid size: DECOR_EDITOR_GRID_SIZE = 32
    """
    G = DECOR_EDITOR_GRID_SIZE
    ice: List[Dict[str, object]] = []

    def add(asset_id: str, x: float, y: float, scale: float = 1.0, rotation: float = 0.0) -> None:
        ice.append({
            "asset_id": asset_id,
            "x": round(float(x), 2),
            "y": round(float(y), 2),
            "scale": round(max(0.25, min(4.0, float(scale))), 2),
            "rotation": round(float(rotation) % 360.0, 2),
        })

    def tile_patch(ids: List[str], sx: float, sy: float, cols: int, rows: int) -> None:
        for row in range(rows):
            for col in range(cols):
                add(ids[(row * cols + col) % len(ids)], sx + col * G, sy + row * G)

    # ── FROZEN ROAD: north-south spine + west branch ──────────────────────────
    # Northern terminus (road only goes south from this tile)
    add("frozen_road_end_s", 3200, 896)
    # Straight N-S: y=928..1248 (10 tiles) + portal tile at 1280 + south y=1312..1408 (4 tiles)
    for k in range(11):
        add("frozen_road_straight_ns", 3200, 928 + k * G)   # 928,960,...,1248
    add("frozen_road_straight_ns", 3200, 1280)               # portal row
    for k in range(4):
        add("frozen_road_straight_ns", 3200, 1312 + k * G)  # 1312,1344,1376,1408
    # Corner: N+W turn at base of south stretch
    add("frozen_road_corner_nw", 3200, 1440)
    # West branch: y=1440, x=3168 down to 2752 (13 tiles)
    for k in range(13):
        add("frozen_road_straight_we", 3200 - G - k * G, 1440)
    # West dead-end (faces east toward the road)
    add("frozen_road_end_e", 2720, 1440)

    # ── TERRAIN PATCHES ───────────────────────────────────────────────────────
    snow = ["ice_terrain_snow_1", "ice_terrain_snow_2"]
    ice_t = ["ice_terrain_ice_1", "ice_terrain_ice_2"]
    rock = ["ice_terrain_tundra_rock_1", "ice_terrain_tundra_rock_2"]
    perm = ["ice_terrain_permafrost_1", "ice_terrain_permafrost_2"]
    fgnd = ["ice_terrain_frozen_ground_1", "ice_terrain_frozen_ground_2"]

    tile_patch(snow,  3040, 1152, 10, 8)   # Portal plaza snow
    tile_patch(fgnd,  2624, 1408,  8, 6)   # Hunter camp ground
    tile_patch(ice_t, 3520, 1152,  9, 6)   # Crystal fields ice
    tile_patch(ice_t, 3840, 1248,  4, 4)   # Frozen pond
    tile_patch(rock,  2880,  864, 18, 8)   # Ancient ruins rock
    tile_patch(perm,  1280, 1408, 10, 8)   # Mammoth graveyard permafrost
    tile_patch(snow,  2880,  672, 12, 6)   # Far north approach

    # ── ZONE 1: PORTAL PLAZA ─────────────────────────────────────────────────
    add("ice_frost_lantern",   3088, 1280)
    add("ice_frost_lantern",   3312, 1280)
    add("ice_frost_shrine",    3200, 1210)
    add("ice_supply_cache",    3264, 1360)
    add("ice_icicle_group",    3140, 1245)
    add("ice_icicle_group",    3260, 1245)
    add("ice_snowdrift_small", 3040, 1340)
    add("ice_snowdrift_small", 3360, 1320)
    add("ice_snowdrift_small", 3100, 1400)
    add("ice_snowdrift_small", 3300, 1400)
    add("ice_frost_flower",    3070, 1310)
    add("ice_frost_flower",    3330, 1310)
    add("ice_tundra_grass",    3060, 1350)
    add("ice_tundra_grass",    3340, 1350)

    # ── ZONE 2: NORTH ROAD CORRIDOR ──────────────────────────────────────────
    add("ice_frost_lantern",   3136, 1100);  add("ice_frost_lantern",   3264, 1100)
    add("ice_frost_lantern",   3136,  980);  add("ice_frost_lantern",   3264,  980)
    add("ice_snowdrift_small", 3060, 1160);  add("ice_snowdrift_small", 3340, 1160)
    add("ice_snowdrift_small", 3060, 1060);  add("ice_snowdrift_small", 3340, 1060)
    add("ice_dead_tree",       3048, 1196);  add("ice_dead_tree",       3352, 1196)
    add("ice_dead_tree_small", 3040, 1056);  add("ice_dead_tree_small", 3360, 1056)
    add("ice_frost_flower",    3074, 1130);  add("ice_frost_flower",    3326, 1130)
    add("ice_tundra_grass",    3080, 1080);  add("ice_tundra_grass",    3320, 1080)
    add("ice_bone_totem",      3080, 1000);  add("ice_bone_totem",      3320, 1000)

    # ── ZONE 3: ANCIENT RUINS (north centre) ─────────────────────────────────
    add("ice_frost_shrine",    3200, 876)
    add("ice_stone_pillar_frozen", 2976, 960);  add("ice_stone_pillar_frozen", 3072, 920)
    add("ice_stone_pillar_frozen", 3328, 920);  add("ice_stone_pillar_frozen", 3424, 960)
    add("ice_stone_pillar_frozen", 2944, 1040); add("ice_stone_pillar_frozen", 3456, 1040)
    add("ice_stone_cairn",     2920, 1080);  add("ice_stone_cairn",     3480, 1080)
    add("ice_stone_cairn",     3120,  904);  add("ice_stone_cairn",     3280,  904)
    add("ice_dead_campfire",   3200,  964)
    add("ice_frost_lantern",   3002,  944);  add("ice_frost_lantern",   3398,  944)
    for px, py in [(2960,1024),(3040,1060),(3360,1060),(3440,1024),(3160,972),(3240,972)]:
        add("ice_snowdrift_small", px, py)
    add("ice_icicle_group",    2900,  960);  add("ice_icicle_group",    3500,  940)
    add("ice_icicle_group",    3100,  844);  add("ice_icicle_group",    3300,  844)
    for px, py in [(3080,1002),(3320,1002),(3000,1072),(3400,1072)]:
        add("ice_tundra_grass", px, py)

    # ── ZONE 4: ICE CAVE ENTRANCE (far north) ────────────────────────────────
    add("ice_cave_entrance",   3200, 756)
    add("ice_icicle_group",    3088, 776);   add("ice_icicle_group",    3312, 776)
    add("ice_crystal_large",   3060, 820);   add("ice_crystal_large",   3340, 820)
    add("ice_crystal_cluster", 3120, 800);   add("ice_crystal_cluster", 3280, 800)
    add("ice_snowdrift_large", 3100, 820);   add("ice_snowdrift_large", 3300, 820)
    add("ice_bone_totem",      3010, 800);   add("ice_bone_totem",      3390, 800)
    add("ice_pine_bent",       2980, 758);   add("ice_pine_bent",       3420, 758)
    add("ice_pine_snowy",      2940, 830);   add("ice_pine_snowy",      3460, 830)
    add("ice_frost_flower",    3170, 796);   add("ice_frost_flower",    3230, 796)

    # ── ZONE 5: HUNTER'S CAMP (west end of road) ─────────────────────────────
    add("ice_hunter_hut",      2720, 1518)
    add("ice_dead_campfire",   2824, 1558)
    add("ice_fish_rack",       2768, 1478)
    add("ice_frozen_barrel",   2660, 1548);  add("ice_frozen_barrel",   2700, 1560)
    add("ice_sled",            2598, 1508)
    add("ice_supply_cache",    2642, 1620)
    add("ice_hunter_trap",     2882, 1638);  add("ice_hunter_trap",     2562, 1638)
    add("ice_skull_pole",      2602, 1460);  add("ice_skull_pole",      2882, 1460)
    add("ice_snowdrift_small", 2640, 1490);  add("ice_snowdrift_small", 2842, 1502)
    add("ice_snowdrift_large", 2720, 1622)
    add("ice_pine_snowy",      2540, 1498);  add("ice_pine_snowy",      2920, 1498)
    add("ice_pine_bent",       2558, 1578)
    add("ice_frost_lantern",   2752, 1500)
    add("ice_snow_boulder_small", 2902, 1552); add("ice_snow_boulder_small", 2578, 1558)
    add("ice_frost_bush",      2862, 1600);  add("ice_frost_bush",      2620, 1600)
    for px, py in [(2660,1512),(2780,1590),(2842,1490)]:
        add("ice_tundra_grass", px, py)

    # ── ZONE 6: ICE CRYSTAL FIELDS (east of portal) ──────────────────────────
    for px, py in [(3600,1240),(3700,1202),(3800,1272),(3920,1220),(3642,1352),(3782,1382)]:
        add("ice_crystal_large", px, py)
    for px, py in [(3562,1290),(3662,1312),(3852,1312),(3962,1302),(3742,1252),(3902,1362)]:
        add("ice_crystal_cluster", px, py)
    add("ice_icicle_group",    3832, 1252);  add("ice_icicle_group",    3962, 1252)
    add("ice_icicle_group",    3832, 1382);  add("ice_icicle_group",    3962, 1382)
    for px, py in [(3522,1332),(3682,1402),(3822,1432),(3942,1412),(3602,1182),(3762,1162)]:
        add("ice_snowdrift_small", px, py)
    for px, py in [(3572,1272),(3702,1322),(3852,1202),(3982,1282),(3722,1402)]:
        add("ice_frost_flower", px, py)
    add("ice_dead_tree",       3502, 1202);  add("ice_dead_tree",       3502, 1382)
    add("ice_dead_tree_small", 4022, 1252);  add("ice_dead_tree_small", 4022, 1382)
    add("ice_snow_boulder_large", 3542, 1342); add("ice_snow_boulder_large", 4002, 1332)
    add("ice_snow_boulder_small", 3582, 1162); add("ice_snow_boulder_small", 3952, 1182)

    # ── ZONE 7: PINE FOREST (northeast) ──────────────────────────────────────
    for px, py, sc in [
        (3752,900,1.0),(3852,942,0.95),(3952,882,1.0),(4052,922,1.05),(4152,872,0.9),
        (4252,930,1.0),(4352,902,0.95),(4452,952,1.05),(4552,892,1.0),(4652,942,0.9),
        (4752,912,1.0),(4852,962,1.05),(3802,1022,0.95),(3922,1002,1.0),(4022,1062,0.9),
        (4122,1012,1.0),(4222,1052,1.05),(4322,1022,0.95),(4422,1062,1.0),(4522,1012,0.9),
        (4622,1062,1.05),(4722,1022,1.0),(4822,1062,0.95),(4922,1002,1.0),(4302,1142,0.9),
        (4402,1102,1.05),(4502,1152,1.0),(4602,1122,0.95),(4702,1152,1.0),(3852,1182,0.9),
        (3952,1142,1.05),(4052,1182,1.0),(4152,1162,0.95),(4252,1202,1.0),(4752,1102,0.9),
        (4852,1142,1.05),(4952,1082,1.0),(5052,1122,0.95),(4102,1302,1.0),(4202,1252,0.9),
        (4302,1322,1.05),(4402,1282,1.0),(4502,1332,0.95),(4602,1302,1.0),(4702,1352,1.05),
        (4802,1302,0.9),(4902,1352,1.0),(5002,1302,1.05),(5102,1352,0.95),
    ]:
        add("ice_pine_snowy", px, py, scale=sc)
    for px, py in [(3722,972),(3802,852),(4102,862),(4202,822),(4402,862),(4602,822),(4802,872),(5002,902),(3702,1202),(5202,1102)]:
        add("ice_pine_bent", px, py)
    for px, py in [(3802,1102),(3902,952),(4052,822),(4182,1102),(4382,1152),(4582,1072),(4682,842),(4902,1202),(5052,952),(5152,1182)]:
        add("ice_dead_tree", px, py)
    for px, py, rot in [(3862,1122,0),(4012,1252,30),(4352,1202,60),(4702,1222,15),(5052,1302,45)]:
        add("ice_frozen_log", px, py, rotation=float(rot))
    for px, py in [(3782,1152),(4002,902),(4202,1172),(4462,1092),(4782,1162),(5002,1082)]:
        add("ice_snow_boulder_large", px, py)
    for px, py in [(3852,1052),(4152,1042),(4502,1202),(4752,1042),(5102,1202)]:
        add("ice_snow_boulder_small", px, py)
    for px, py in [(3872,1202),(4092,1302),(4382,1282),(4642,1272),(4912,1302),(5122,1352)]:
        add("ice_frost_bush", px, py)
    for px, py in [(3822,1012),(4002,1072),(4202,992),(4402,1042),(4602,1002),(4802,1072),(5002,1032)]:
        add("ice_tundra_grass", px, py)

    # ── ZONE 8: MAMMOTH GRAVEYARD (far west) ─────────────────────────────────
    for px, py in [(1682,1542),(1902,1622),(2102,1562),(1782,1722),(2002,1802),(1602,1752),(2202,1702)]:
        add("ice_mammoth_bones", px, py)
    for px, py in [(1542,1482),(1782,1462),(2022,1462),(2262,1482),(1642,1782),(2162,1782),(1542,1902),(2262,1862)]:
        add("ice_skull_pole", px, py)
    add("ice_bone_totem", 1862, 1542); add("ice_bone_totem", 2062, 1642); add("ice_bone_totem", 1662, 1702)
    for px, py in [(1502,1562),(2322,1582),(1702,1802),(2102,1862)]:
        add("ice_stone_cairn", px, py)
    add("ice_frost_lantern", 1872, 1662)
    add("ice_frost_shrine", 1802, 1500)
    for px, py in [(1582,1502),(1722,1602),(1862,1472),(2002,1532),(2142,1592),(2282,1512),(1622,1782),(1802,1842),(2002,1882),(2202,1842),(1542,1682),(2322,1702)]:
        add("ice_snowdrift_large" if py > 1700 else "ice_snowdrift_small", px, py)
    for px, py in [(1562,1542),(1702,1702),(1922,1762),(2122,1722),(2282,1622),(1482,1802)]:
        add("ice_dead_tree", px, py)
    for px, py in [(1602,1602),(1822,1682),(2082,1682),(2202,1762),(1742,1862)]:
        add("ice_tundra_grass", px, py)

    # ── ZONE 9: RUINED OUTPOST (southeast) ───────────────────────────────────
    add("ice_broken_watchtower", 4642, 2002)
    add("ice_frozen_wagon",  4382, 2042);  add("ice_frozen_wagon",  4882, 1982)
    add("ice_supply_cache",  4442, 2122);  add("ice_supply_cache",  4722, 2102); add("ice_supply_cache", 4542, 1962)
    add("ice_dead_campfire", 4562, 1982)
    add("ice_bone_totem",    4602, 1922)
    add("ice_hunter_trap",   4502, 1902);  add("ice_hunter_trap",   4682, 2062); add("ice_hunter_trap", 4422, 2162); add("ice_hunter_trap", 4802, 2042)
    add("ice_skull_pole",    4342, 1942);  add("ice_skull_pole",    4882, 1902); add("ice_skull_pole", 4482, 2202); add("ice_skull_pole", 4742, 2182)
    add("ice_frozen_barrel", 4462, 2002);  add("ice_frozen_barrel", 4842, 2022); add("ice_frozen_barrel", 4502, 2062)
    for px, py in [(4362,2002),(4482,2162),(4622,2082),(4782,2142),(4902,1962)]:
        add("ice_snowdrift_large" if py > 2100 else "ice_snowdrift_small", px, py)
    for px, py in [(4282,1962),(4962,2002),(4322,2102),(4982,2062)]:
        add("ice_pine_snowy", px, py)
    for px, py in [(4302,1902),(4942,1922),(4422,2242),(4862,2162)]:
        add("ice_dead_tree", px, py)
    for px, py in [(4362,1962),(4862,2142),(4522,2202)]:
        add("ice_snow_boulder_large", px, py)
    add("ice_frost_shrine", 4802, 1600)

    # ── SCATTERED FAR FIELD ELEMENTS ─────────────────────────────────────────
    far_dead = [
        (802,1202),(902,1402),(1102,1102),(1202,1602),(1002,1802),
        (5402,1102),(5502,1402),(5302,1602),(5602,1802),(5402,2102),
        (1502,2602),(2002,2802),(2502,3002),(3002,2902),(3502,3102),
        (4002,2902),(4502,3002),(5002,2802),(5502,2602),(602,2002),
        (702,2402),(802,2802),(902,3202),(5602,2202),(5702,2602),(5802,3002),
    ]
    for i, (px, py) in enumerate(far_dead):
        add("ice_dead_tree" if i % 3 != 0 else "ice_dead_tree_small", px, py)

    far_pine = [
        (802,902),(902,1002),(1002,882),(1102,952),(2502,702),(2602,752),(2702,722),(2802,772),
        (3402,722),(3502,762),(3602,732),(3702,782),(5102,802),(5202,852),(5302,812),(5402,872),
        (1202,2202),(1302,2302),(1202,2402),(5302,2302),(5402,2402),(5302,2502),
    ]
    for i, (px, py) in enumerate(far_pine):
        add("ice_pine_snowy" if i % 2 == 0 else "ice_pine_bent", px, py)

    for px, py in [(1002,1302),(1302,902),(2202,1002),(2602,1102),(3052,1302),(3952,1452),(4202,1302),(4852,1052),(5102,1502),(5302,2002),(1102,2502),(1502,3002),(3202,2602),(4602,2602),(5002,3102)]:
        add("ice_snow_boulder_large", px, py)

    for px, py in [(1602,902),(1802,1002),(2002,952),(2202,1052),(2402,902),(2602,982),(3602,1502),(3802,1582),(4002,1552),(4202,1502),(4402,1452),(1402,2002),(1602,2102),(1802,2202),(4802,2402),(5002,2602),(5202,2802)]:
        add("ice_snowdrift_small", px, py)

    for px, py in [(2702,1202),(2802,1102),(2902,1282),(3002,1202),(3402,1292),(3502,1202),(3602,1292),(2602,1302),(2702,1352),(2802,1282)]:
        add("ice_frost_flower", px, py)

    for px, py in [(2502,1202),(2602,1152),(2702,1202),(2802,1152),(2502,1352),(2602,1402),(2702,1352),(3402,1452),(3502,1502),(3602,1452)]:
        add("ice_tundra_grass", px, py)

    return ice


def get_level_decor_instance_surface(
    instance: Dict[str, object],
    level_decor_assets: Dict[str, object],
    render_cache: Dict[Tuple[str, int, int], pygame.Surface],
) -> Optional[pygame.Surface]:
    asset_id = str(instance.get("asset_id", "")).strip()
    if not asset_id:
        return None
    asset_entry = level_decor_asset_lookup(level_decor_assets, asset_id)
    if asset_entry is None:
        return None
    source = level_decor_asset_preview_surface(asset_entry, animated=True)
    if not isinstance(source, pygame.Surface):
        return None
    try:
        scale = float(instance.get("scale", 1.0))
    except (TypeError, ValueError):
        scale = 1.0
    try:
        rotation = float(instance.get("rotation", 0.0))
    except (TypeError, ValueError):
        rotation = 0.0
    scale = max(0.25, min(4.0, scale))
    rotation = rotation % 360.0
    cache_key = (asset_id, int(round(scale * 100.0)), int(round(rotation)))
    cached = render_cache.get(cache_key)
    if isinstance(cached, pygame.Surface):
        return cached
    transformed = pygame.transform.rotozoom(source, -rotation, scale)
    render_cache[cache_key] = transformed
    return transformed


def get_level_decor_instance_anchor(
    instance: Dict[str, object],
    asset_entry: Dict[str, object],
    transformed_surface: pygame.Surface,
) -> Tuple[float, float]:
    source = asset_entry.get("surface")
    if not isinstance(source, pygame.Surface):
        return (transformed_surface.get_width() * 0.5, float(transformed_surface.get_height()))
    try:
        scale = float(instance.get("scale", 1.0))
    except (TypeError, ValueError):
        scale = 1.0
    try:
        rotation = float(instance.get("rotation", 0.0))
    except (TypeError, ValueError):
        rotation = 0.0
    scale = max(0.25, min(4.0, scale))
    rotation = rotation % 360.0
    try:
        source_anchor_offset = float(asset_entry.get("anchor_offset", 0.0))
    except (TypeError, ValueError):
        source_anchor_offset = 0.0
    source_w = float(source.get_width())
    source_h = float(source.get_height())
    anchor_y = source_h - source_anchor_offset
    vector_y = (anchor_y - source_h * 0.5) * scale
    theta = math.radians(-rotation)
    dx = -vector_y * math.sin(theta)
    dy = vector_y * math.cos(theta)
    return (
        transformed_surface.get_width() * 0.5 + dx,
        transformed_surface.get_height() * 0.5 + dy,
    )


def get_level_decor_instance_rect(
    instance: Dict[str, object],
    level_decor_assets: Dict[str, object],
    render_cache: Dict[Tuple[str, int, int], pygame.Surface],
    camera: Optional[Vector2] = None,
) -> Optional[pygame.Rect]:
    transformed_surface = get_level_decor_instance_surface(instance, level_decor_assets, render_cache)
    asset_id = str(instance.get("asset_id", "")).strip()
    asset_entry = level_decor_asset_lookup(level_decor_assets, asset_id)
    if transformed_surface is None or asset_entry is None:
        return None
    try:
        x = int(round(float(instance.get("x", 0.0))))
        y = int(round(float(instance.get("y", 0.0))))
    except (TypeError, ValueError):
        return None
    if isinstance(camera, Vector2):
        x -= int(camera.x)
        y -= int(camera.y)
    anchor_x, anchor_y = get_level_decor_instance_anchor(instance, asset_entry, transformed_surface)
    rect = transformed_surface.get_rect()
    rect.left = int(round(float(x) - anchor_x))
    rect.top = int(round(float(y) - anchor_y))
    return rect


def draw_level_decor_instance(
    surface: pygame.Surface,
    instance: Dict[str, object],
    level_decor_assets: Dict[str, object],
    render_cache: Dict[Tuple[str, int, int], pygame.Surface],
    camera: Vector2,
    alpha: int = 255,
    highlight: bool = False,
    show_anchor: bool = False,
) -> Optional[pygame.Rect]:
    sprite = get_level_decor_instance_surface(instance, level_decor_assets, render_cache)
    rect = get_level_decor_instance_rect(instance, level_decor_assets, render_cache, camera)
    if sprite is None or rect is None:
        return None
    try:
        anchor_screen_x = int(round(float(instance.get("x", 0.0)) - float(camera.x)))
        anchor_screen_y = int(round(float(instance.get("y", 0.0)) - float(camera.y)))
    except (TypeError, ValueError):
        anchor_screen_x = rect.centerx
        anchor_screen_y = rect.bottom
    if not rect.colliderect(pygame.Rect(-140, -140, SCREEN_WIDTH + 280, SCREEN_HEIGHT + 280)):
        return rect
    shadow_w = max(20, int(sprite.get_width() * 0.42))
    shadow_h = max(8, int(sprite.get_width() * 0.12))
    shadow = pygame.Surface((shadow_w, shadow_h), pygame.SRCALPHA)
    pygame.draw.ellipse(shadow, (0, 0, 0, 72 if alpha >= 220 else 48), shadow.get_rect())
    shadow_rect = shadow.get_rect(midtop=(anchor_screen_x, anchor_screen_y - max(2, shadow_h // 3)))
    surface.blit(shadow, shadow_rect)
    if alpha >= 250:
        surface.blit(sprite, rect)
    else:
        faded = sprite.copy()
        faded.set_alpha(max(20, min(255, alpha)))
        surface.blit(faded, rect)
    if highlight:
        glow = rect.inflate(12, 10)
        glow_surf = pygame.Surface((glow.width, glow.height), pygame.SRCALPHA)
        pygame.draw.rect(glow_surf, (228, 202, 132, 44), glow_surf.get_rect(), border_radius=10)
        pygame.draw.rect(glow_surf, (240, 220, 160, 170), glow_surf.get_rect(), 1, border_radius=10)
        surface.blit(glow_surf, glow.topleft)
    if show_anchor:
        pygame.draw.line(surface, (240, 218, 160), (anchor_screen_x - 7, anchor_screen_y), (anchor_screen_x + 7, anchor_screen_y), 2)
        pygame.draw.line(surface, (240, 218, 160), (anchor_screen_x, anchor_screen_y - 8), (anchor_screen_x, anchor_screen_y + 4), 2)
    return rect


def draw_level_decor_editor_overlay(
    surface: pygame.Surface,
    current_level: str,
    available_assets: List[Dict[str, object]],
    selected_asset_id: Optional[str],
    asset_pack_mode: str,
    catalog_filter: str,
    category_filter: str,
    search_text: str,
    search_active: bool,
    placement_mode: str,
    selected_scale: float,
    selected_rotation: float,
    scroll_offset: int,
    title_font: pygame.font.Font,
    body_font: pygame.font.Font,
    small_font: pygame.font.Font,
    placed_count: int,
    dirty: bool,
    generate_seed: int,
    collision_preview: bool,
    ai_prompt: str = "",
    ai_input_active: bool = False,
    ai_generating: bool = False,
    ai_scope: str = "shared",
    clear_pending: bool = False,
    panel_side: str = "right",
) -> Dict[str, object]:
    mouse_pos = pygame.mouse.get_pos()

    # ── Panel geometry (compact) ──────────────────────────────────────────────
    _PW = DECOR_EDITOR_PANEL_WIDTH
    if panel_side == "left":
        panel_x = 8
    else:
        panel_x = SCREEN_WIDTH - _PW - 8
    panel_rect = pygame.Rect(panel_x, 8, _PW, SCREEN_HEIGHT - 16)
    if panel_side == "left":
        world_rect = pygame.Rect(panel_rect.right + 8, 8, max(220, SCREEN_WIDTH - panel_rect.right - 16), SCREEN_HEIGHT - 16)
    else:
        world_rect = pygame.Rect(8, 8, max(220, panel_rect.left - 16), SCREEN_HEIGHT - 16)
    inner_left = panel_rect.left + 8
    inner_w = panel_rect.width - 16

    # ── Section geometry ─────────────────────────────────────────────────────
    _GAP = 4
    _BOTTOM_H = 84

    _y = panel_rect.top + 6
    header_rect = pygame.Rect(inner_left, _y, inner_w, 28)
    _y = header_rect.bottom + _GAP

    # Mode buttons row (right below header)
    mode_row_rect = pygame.Rect(inner_left, _y, inner_w, 22)
    _y = mode_row_rect.bottom + _GAP

    # Category tabs row
    cat_row_rect = pygame.Rect(inner_left, _y, inner_w, 22)
    _y = cat_row_rect.bottom + _GAP

    # Search bar
    search_rect = pygame.Rect(inner_left, _y, inner_w - 38, 22)
    clear_search_rect = pygame.Rect(search_rect.right + 3, _y, 35, 22)
    _y = search_rect.bottom + _GAP

    # Asset grid
    grid_rect = pygame.Rect(inner_left, _y, inner_w, panel_rect.bottom - _BOTTOM_H - _GAP - _y)
    bottom_rect = pygame.Rect(inner_left, panel_rect.bottom - _BOTTOM_H - 2, inner_w, _BOTTOM_H)

    # ── Background ───────────────────────────────────────────────────────────
    draw_ornate_panel(surface, panel_rect)
    overlay_glow = pygame.Surface(world_rect.size, pygame.SRCALPHA)
    pygame.draw.rect(overlay_glow, (8, 10, 16, 22), overlay_glow.get_rect(), border_radius=8)
    pygame.draw.rect(overlay_glow, (190, 168, 108, 44), overlay_glow.get_rect(), 1, border_radius=8)
    surface.blit(overlay_glow, world_rect.topleft)

    # ── World guide hint ─────────────────────────────────────────────────────
    guide = small_font.render("LMB: place/drag  RMB: erase anything  R: rotate  Wheel: scale", True, (184, 178, 168))
    guide_bg = pygame.Rect(world_rect.left + 8, world_rect.top + 6, min(world_rect.width - 16, guide.get_width() + 14), 22)
    pygame.draw.rect(surface, (12, 12, 18), guide_bg, border_radius=6)
    pygame.draw.rect(surface, (118, 110, 92), guide_bg, 1, border_radius=6)
    surface.blit(guide, (guide_bg.left + 7, guide_bg.top + 3))

    # ── Header (compact single row) ──────────────────────────────────────────
    title_surf = small_font.render("Level Editor", True, (242, 232, 202))
    surface.blit(title_surf, (header_rect.left, header_rect.top + 4))

    _status_col = (230, 180, 100) if dirty else (140, 200, 148)
    _status_dot = small_font.render("\u25cf", True, _status_col)
    surface.blit(_status_dot, (header_rect.left + title_surf.get_width() + 6, header_rect.top + 4))

    _placed_txt = small_font.render(f"{placed_count} | {current_level.title()}", True, (168, 162, 148))
    surface.blit(_placed_txt, (header_rect.left + title_surf.get_width() + 20, header_rect.top + 4))

    save_rect = pygame.Rect(header_rect.right - 40, header_rect.top + 2, 40, 22)
    reload_rect = pygame.Rect(save_rect.left - 44, header_rect.top + 2, 42, 22)
    clear_rect = pygame.Rect(reload_rect.left - 44, header_rect.top + 2, 42, 22)
    _save_col = (180, 230, 160) if dirty else (190, 200, 178)
    draw_ui_button(surface, save_rect, hovered=save_rect.collidepoint(mouse_pos), text="Save", font=small_font, color=_save_col)
    draw_ui_button(surface, reload_rect, hovered=reload_rect.collidepoint(mouse_pos), text="Rld", font=small_font, color=(210, 210, 200))
    draw_ui_button(
        surface,
        clear_rect,
        hovered=clear_rect.collidepoint(mouse_pos),
        text="OK?" if clear_pending else "Clr",
        font=small_font,
        color=(240, 188, 172) if clear_pending else (220, 206, 188),
    )

    # ── Mode buttons row ─────────────────────────────────────────────────────
    mode_rects: Dict[str, pygame.Rect] = {}
    _mode_defs = [("single", "Paint"), ("scatter", "Scatter"), ("move", "Move")]
    _mode_cols = {"single": (190, 230, 190), "scatter": (190, 210, 240), "delete": (240, 180, 180), "move": (240, 220, 160)}
    _mx = mode_row_rect.left
    for _mid, _mlbl in _mode_defs:
        _mw = small_font.size(_mlbl)[0] + 14
        _mrect = pygame.Rect(_mx, mode_row_rect.top, _mw, mode_row_rect.height)
        _mact = (_mid == placement_mode)
        draw_ui_button(surface, _mrect, hovered=_mrect.collidepoint(mouse_pos), text=_mlbl, font=small_font, color=_mode_cols[_mid] if _mact else (160, 156, 146))
        mode_rects[_mid] = _mrect
        _mx += _mw + 4

    # ── Category tab bar (compact, scrollable if needed) ─────────────────────
    _CAT_DISPLAY: Dict[str, str] = {
        "all": "All", "terrain": "Ter", "roads": "Rd", "water": "Wtr",
        "nature": "Nat", "containers": "Ctn", "furniture": "Fur",
        "houses": "Str", "vfx": "FX",
        "scene": "Scn", "props": "Prp", "structures": "Str", "relics": "Rel",
    }
    _cat_ids = (
        ["all", "terrain", "roads", "water", "nature", "containers", "furniture", "houses", "vfx"]
        if asset_pack_mode == "medieval_generated"
        else ["all", "scene", "props", "structures", "nature", "relics"]
    )
    category_rects: Dict[str, pygame.Rect] = {}
    _cat_x = inner_left
    for _ci, _cat in enumerate(_cat_ids):
        _lbl = _CAT_DISPLAY.get(_cat, _cat[:3].title())
        _bw = small_font.size(_lbl)[0] + 10
        _brect = pygame.Rect(_cat_x, cat_row_rect.top, _bw, cat_row_rect.height)
        if _brect.right > inner_left + inner_w:
            break
        _active = (_cat == category_filter) or (_cat == "all" and not category_filter)
        pygame.draw.rect(surface, (54, 46, 28) if _active else (20, 18, 14), _brect, border_radius=4)
        pygame.draw.rect(surface, (220, 194, 118) if _active else (72, 68, 56), _brect, 1, border_radius=4)
        _lt = small_font.render(_lbl, True, (240, 230, 200) if _active else (172, 166, 152))
        surface.blit(_lt, (_brect.left + (_bw - _lt.get_width()) // 2, _brect.top + (_brect.height - _lt.get_height()) // 2))
        category_rects[_cat] = _brect
        _cat_x += _bw + 3

    # ── Search bar ───────────────────────────────────────────────────────────
    pygame.draw.rect(surface, (12, 12, 18), search_rect, border_radius=6)
    pygame.draw.rect(surface, (140, 118, 78) if search_active else (72, 66, 54), search_rect, 1, border_radius=6)
    _slbl = (search_text + ("|" if search_active else "")) if (search_text or search_active) else "Search..."
    _scol = (232, 224, 206) if (search_text or search_active) else (116, 112, 102)
    surface.blit(small_font.render(ellipsize_text(small_font, _slbl, search_rect.width - 10), True, _scol), (search_rect.left + 5, search_rect.top + 4))
    draw_ui_button(surface, clear_search_rect, hovered=clear_search_rect.collidepoint(mouse_pos), text="X", font=small_font, color=(200, 194, 176))

    # ── Asset grid (compact 3 columns) ───────────────────────────────────────
    pygame.draw.rect(surface, (10, 10, 14), grid_rect, border_radius=8)
    pygame.draw.rect(surface, (68, 64, 54), grid_rect, 1, border_radius=8)
    asset_rects: Dict[str, pygame.Rect] = {}
    _COLS = 3
    _CGAP = 4
    _CW = (grid_rect.width - (_COLS - 1) * _CGAP - 8) // _COLS
    _THUMB = 48
    _CH = _THUMB + 20
    _rows = (len(available_assets) + _COLS - 1) // _COLS
    content_height = max(0, _rows * (_CH + _CGAP) - _CGAP + 6)
    scroll_offset = max(0, int(scroll_offset))

    _prev_clip = surface.get_clip()
    surface.set_clip(grid_rect.inflate(-2, -2))
    if available_assets:
        for _ai, _asset in enumerate(available_assets):
            _row = _ai // _COLS
            _col = _ai % _COLS
            _cx = grid_rect.left + 4 + _col * (_CW + _CGAP)
            _cy = grid_rect.top + 4 + _row * (_CH + _CGAP) - scroll_offset
            _cell = pygame.Rect(_cx, _cy, _CW, _CH)
            if _cell.bottom < grid_rect.top or _cell.top > grid_rect.bottom:
                continue
            _aid = str(_asset.get("id", ""))
            _sel = _aid == str(selected_asset_id or "")
            _hov = _cell.collidepoint(mouse_pos)
            pygame.draw.rect(surface, (46, 40, 28) if _sel else (20, 18, 24), _cell, border_radius=6)
            pygame.draw.rect(surface, (220, 194, 118) if _sel else ((118, 106, 80) if _hov else (56, 54, 66)), _cell, 1, border_radius=6)
            _tbox = pygame.Rect(_cell.centerx - _THUMB // 2, _cell.top + 3, _THUMB, _THUMB)
            pygame.draw.rect(surface, (24, 22, 30), _tbox, border_radius=4)
            _tsurf = level_decor_asset_preview_surface(_asset, animated=_hov)
            if isinstance(_tsurf, pygame.Surface):
                _t = _scale_surface_to_fit(_tsurf, _THUMB - 4)
                surface.blit(_t, _t.get_rect(center=_tbox.center))
            _ntxt = small_font.render(ellipsize_text(small_font, str(_asset.get("name", "Obj")), _CW - 4), True, (234, 226, 210) if _sel else (186, 180, 166))
            surface.blit(_ntxt, (_cell.centerx - _ntxt.get_width() // 2, _cell.bottom - _ntxt.get_height() - 2))
            asset_rects[_aid] = _cell
    else:
        _em1 = small_font.render("No assets loaded.", True, (180, 174, 160))
        _em2 = small_font.render("Click Generate below.", True, (160, 154, 140))
        surface.blit(_em1, (grid_rect.centerx - _em1.get_width() // 2, grid_rect.top + 20))
        surface.blit(_em2, (grid_rect.centerx - _em2.get_width() // 2, grid_rect.top + 40))
    surface.set_clip(_prev_clip)

    # Scrollbar
    if content_height > grid_rect.height:
        _tr = pygame.Rect(grid_rect.right - 6, grid_rect.top + 3, 3, grid_rect.height - 6)
        pygame.draw.rect(surface, (24, 24, 30), _tr, border_radius=2)
        _ms = max(1, content_height - grid_rect.height)
        _hh = max(24, int(_tr.height * (grid_rect.height / float(content_height))))
        _hy = _tr.top + int((_tr.height - _hh) * (scroll_offset / float(_ms)))
        pygame.draw.rect(surface, (158, 138, 90), pygame.Rect(_tr.left, _hy, _tr.width, _hh), border_radius=2)

    # Generate pack button (visible only when no assets)
    generate_rect = pygame.Rect(grid_rect.centerx - 60, grid_rect.top + 62, 120, 24)
    if not available_assets:
        draw_ui_button(surface, generate_rect, hovered=generate_rect.collidepoint(mouse_pos), text="Generate Pack", font=small_font, color=(240, 220, 155))

    # ── Bottom bar: selected asset + controls ────────────────────────────────
    pygame.draw.rect(surface, (16, 14, 12), bottom_rect, border_radius=8)
    pygame.draw.rect(surface, (108, 94, 62), bottom_rect, 1, border_radius=8)

    _ICON = 42
    icon_rect = pygame.Rect(bottom_rect.left + 6, bottom_rect.top + 6, _ICON, _ICON)
    pygame.draw.rect(surface, (28, 26, 34), icon_rect, border_radius=6)
    pygame.draw.rect(surface, (96, 86, 68), icon_rect, 1, border_radius=6)
    selected_asset = next((a for a in available_assets if str(a.get("id")) == str(selected_asset_id)), None)
    if selected_asset:
        _psurf = level_decor_asset_preview_surface(selected_asset, animated=True)
        if isinstance(_psurf, pygame.Surface):
            _p = _scale_surface_to_fit(_psurf, _ICON - 4)
            surface.blit(_p, _p.get_rect(center=icon_rect.center))

    _info_x = icon_rect.right + 6
    _info_avail_w = inner_w - _ICON - 18

    if selected_asset:
        _aname = str(selected_asset.get("name", "Object"))
    else:
        _aname = "No selection"
    _nsurf = small_font.render(ellipsize_text(small_font, _aname, _info_avail_w), True, (242, 234, 216))
    surface.blit(_nsurf, (_info_x, bottom_rect.top + 6))

    # Scale / Rotate (compact single row)
    _ctrl_y = bottom_rect.top + 24
    scale_minus_rect = pygame.Rect(_info_x, _ctrl_y, 18, 18)
    scale_plus_rect = pygame.Rect(_info_x + 74, _ctrl_y, 18, 18)
    draw_ui_button(surface, scale_minus_rect, hovered=scale_minus_rect.collidepoint(mouse_pos), text="-", font=small_font, color=(200, 196, 178))
    draw_ui_button(surface, scale_plus_rect, hovered=scale_plus_rect.collidepoint(mouse_pos), text="+", font=small_font, color=(200, 196, 178))
    _sc_lbl = small_font.render(f"S {selected_scale:.1f}x", True, (196, 190, 172))
    surface.blit(_sc_lbl, (_info_x + 20, _ctrl_y + 2))

    rot_minus_rect = pygame.Rect(_info_x + 100, _ctrl_y, 18, 18)
    rot_plus_rect = pygame.Rect(_info_x + 174, _ctrl_y, 18, 18)
    draw_ui_button(surface, rot_minus_rect, hovered=rot_minus_rect.collidepoint(mouse_pos), text="-", font=small_font, color=(200, 196, 178))
    draw_ui_button(surface, rot_plus_rect, hovered=rot_plus_rect.collidepoint(mouse_pos), text="+", font=small_font, color=(200, 196, 178))
    _rot_lbl = small_font.render(f"R {int(round(selected_rotation))}\u00b0", True, (196, 190, 172))
    surface.blit(_rot_lbl, (_info_x + 120, _ctrl_y + 2))

    # ── 8-direction nudge pad for shops (compact) ────────────────────────────
    _nudge_size = 18
    _nudge_gap = 1
    _nudge_step = _nudge_size + _nudge_gap
    _nudge_ox = bottom_rect.left + 6
    _nudge_oy = bottom_rect.top + 54
    _nudge_dirs = {
        "nw": (-1, -1), "n": (0, -1), "ne": (1, -1),
        "w":  (-1,  0),                "e":  (1,  0),
        "sw": (-1,  1), "s": (0,  1),  "se": (1,  1),
    }
    _nudge_grid = {
        "nw": (0, 0), "n": (1, 0), "ne": (2, 0),
        "w":  (0, 1),              "e":  (2, 1),
        "sw": (0, 2), "s": (1, 2), "se": (2, 2),
    }
    _arrow_chars = {"nw": "\u2196", "n": "\u2191", "ne": "\u2197", "w": "\u2190", "e": "\u2192", "sw": "\u2199", "s": "\u2193", "se": "\u2198"}
    nudge_rects: Dict[str, pygame.Rect] = {}
    _nlbl = small_font.render("Nudge", True, (150, 144, 130))
    surface.blit(_nlbl, (_nudge_ox + _nudge_step * 3 + 4, _nudge_oy + _nudge_step))
    for _nid, (_gx, _gy) in _nudge_grid.items():
        _nr = pygame.Rect(_nudge_ox + _gx * _nudge_step, _nudge_oy + _gy * _nudge_step, _nudge_size, _nudge_size)
        draw_ui_button(surface, _nr, hovered=_nr.collidepoint(mouse_pos), text=_arrow_chars[_nid], font=small_font, color=(210, 200, 170))
        nudge_rects[_nid] = _nr

    # ── Offscreen dummy rects for removed features ────────────────────────────
    _off = pygame.Rect(-9999, -9999, 1, 1)
    inspector_rects: Dict[str, pygame.Rect] = {}

    return {
        "panel_rect": panel_rect,
        "world_rect": world_rect,
        "save_rect": save_rect,
        "reload_rect": reload_rect,
        "clear_rect": clear_rect,
        "generate_rect": generate_rect,
        "demo_rect": _off,
        "seed_minus_rect": _off,
        "seed_plus_rect": _off,
        "pack_rects": {},
        "filter_rects": {},
        "category_rects": category_rects,
        "mode_rects": mode_rects,
        "collision_rect": _off,
        "inspector_rects": inspector_rects,
        "asset_rects": asset_rects,
        "search_rect": search_rect,
        "clear_search_rect": clear_search_rect,
        "content_height": content_height,
        "ai_prompt_rect": _off,
        "ai_generate_btn_rect": _off,
        "ai_scope_rects": {},
        "scale_minus_rect": scale_minus_rect,
        "scale_plus_rect": scale_plus_rect,
        "rot_minus_rect": rot_minus_rect,
        "rot_plus_rect": rot_plus_rect,
        "nudge_rects": nudge_rects,
    }


_RESOURCE_BAR_ASSETS: Optional[Dict[str, pygame.Surface]] = None



from game.systems.core import (DayNightCycle, WeatherSystem, damage_wolf_entity, draw_point_light, point_segment_distance_sq, circle_hits_segment, ParticleEmitter, StatusEffect, StatusEffectSystem, ScreenEffectController, QuestCelebrationVFX, LevelUpVFX, CameraDirector, AmbientOverlaySystem)  # runtime systems


from game.combat.ultimates import (UltimateContext, UltimateBase, MageBeamUltimate, MageCataclysmUltimate, RogueTeleportUltimate, RangerStormUltimate, NecromancerSummonUltimate, WarriorDashUltimate, PaladinTransformationUltimate)


ULTIMATE_CLASS_MAP: Dict[str, Any] = {
    "mage": MageCataclysmUltimate,
    "rogue": RogueTeleportUltimate,
    "ranger": RangerStormUltimate,
    "necromancer": NecromancerSummonUltimate,
    "warrior": WarriorDashUltimate,
    "paladin": PaladinTransformationUltimate,
}


def create_ultimate_for_class(
    class_id: str,
    spell: Dict[str, object],
    caster_pos: Vector2,
    target_pos: Vector2,
    facing: int,
    bonus_power: float,
    spell_mods: Optional[Dict[str, float]] = None,
    class_damage_mult: float = 1.0,
) -> Optional[UltimateBase]:
    ultimate_cls = ULTIMATE_CLASS_MAP.get(str(class_id))
    if ultimate_cls is None:
        return None
    return ultimate_cls(spell, caster_pos, target_pos, facing, bonus_power, spell_mods, class_damage_mult)

def character_selection_screen(
    screen: pygame.Surface,
    clock: pygame.time.Clock,
    saves: List[Dict],
    class_visuals: Dict[str, Dict[str, Union[pygame.Surface, str]]],
    fonts: Dict[str, pygame.font.Font],
) -> Optional[int]:
    """
    Displays character selection.
    Returns:
        index of selected save (0..N)
        -1 for 'Create New'
        None for 'Quit'
    """
    title_font = fonts["title"]
    info_font = fonts["info"]
    node_font = fonts["node"]
    tiny_font = fonts["tiny"]
    
    selected_idx = 0 if saves else -1

    # Ensure OS cursor is visible on this screen — run_session hides it for
    # the custom in-game cursor, and re-entering the menu used to leave the
    # cursor invisible, making character creation effectively unusable.
    pygame.mouse.set_visible(True)

    while True:
        # Reassert cursor visibility every frame — guards against SDL on
        # Windows silently dropping the first set_visible(True) when the
        # window is still receiving initial focus events (fresh launch bug).
        if not pygame.mouse.get_visible():
            pygame.mouse.set_visible(True)
        screen.fill((12, 14, 18))
        draw_vertical_gradient(screen, pygame.Rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT), (8, 10, 16), (24, 28, 36))
        
        # Title
        title_s = title_font.render("Select Character", True, (220, 210, 190))
        screen.blit(title_s, (SCREEN_WIDTH // 2 - title_s.get_width() // 2, 40))
        
        # Character List
        list_w = 400
        list_x = 100
        list_y = 120
        
        # "Create New" slot
        create_rect = pygame.Rect(list_x, list_y, list_w, 60)
        hover = create_rect.collidepoint(pygame.mouse.get_pos())
        sel = (selected_idx == -1)
        
        pygame.draw.rect(screen, (40, 50, 40) if sel else ((30, 34, 30) if hover else (20, 22, 24)), create_rect, border_radius=8)
        pygame.draw.rect(screen, (120, 200, 120) if sel else (60, 80, 60), create_rect, 2 if sel else 1, border_radius=8)
        create_s = node_font.render("+ Create New Character", True, (180, 220, 180) if sel else (140, 160, 140))
        screen.blit(create_s, (create_rect.centerx - create_s.get_width() // 2, create_rect.centery - create_s.get_height() // 2))
        
        # Existing saves
        for i, save in enumerate(saves):
            rect = pygame.Rect(list_x, list_y + 80 + i * 70, list_w, 60)
            is_sel = (i == selected_idx)
            is_hover = rect.collidepoint(pygame.mouse.get_pos())
            
            bg = (50, 44, 40) if is_sel else ((36, 32, 34) if is_hover else (26, 24, 26))
            border = (220, 180, 100) if is_sel else (80, 80, 90)
            
            pygame.draw.rect(screen, bg, rect, border_radius=8)
            pygame.draw.rect(screen, border, rect, 2 if is_sel else 1, border_radius=8)
            
            name = str(save.get("player_name", "Unknown"))
            cls_id = normalize_class_id(save.get("class", "rogue"))
            cls = str(CLASS_ARCHETYPES.get(cls_id, {}).get("name", cls_id.title()))
            lvl = int(save.get("player_level", 1))
            
            name_s = node_font.render(name, True, (230, 220, 200) if is_sel else (180, 180, 190))
            meta_s = info_font.render(f"Level {lvl} {cls}", True, (160, 150, 120) if is_sel else (120, 120, 130))
            
            screen.blit(name_s, (rect.left + 20, rect.top + 8))
            screen.blit(meta_s, (rect.left + 20, rect.bottom - 24))

        # Preview Panel (Right side)
        preview_rect = pygame.Rect(SCREEN_WIDTH - 500, 120, 360, 500)
        draw_ornate_panel(screen, preview_rect)
        
        if selected_idx >= 0 and selected_idx < len(saves):
            save = saves[selected_idx]
            cls_id = normalize_class_id(save.get("class", "rogue"))
            visual = resolve_class_visual_entry(class_visuals, cls_id, lvl)
            sprite = visual.get("sprite")
            if isinstance(sprite, pygame.Surface):
                # Scale up for preview
                scale = 3
                w, h = sprite.get_width() * scale, sprite.get_height() * scale
                scaled = pygame.transform.scale(sprite, (w, h))
                screen.blit(scaled, (preview_rect.centerx - w // 2, preview_rect.centery - h // 2 - 40))
            
            p_name = node_font.render(str(save.get("player_name", "Hero")), True, (240, 220, 180))
            cls_name = str(CLASS_ARCHETYPES.get(cls_id, {}).get("name", cls_id.title()))
            p_cls = info_font.render(f"Level {save.get('player_level', 1)} {cls_name}", True, (180, 170, 160))
            p_zone = info_font.render("Raven Hollow", True, (140, 140, 150))
            
            screen.blit(p_name, (preview_rect.centerx - p_name.get_width() // 2, preview_rect.bottom - 120))
            screen.blit(p_cls, (preview_rect.centerx - p_cls.get_width() // 2, preview_rect.bottom - 90))
            screen.blit(p_zone, (preview_rect.centerx - p_zone.get_width() // 2, preview_rect.bottom - 60))
            
            play_btn = pygame.Rect(preview_rect.centerx - 80, preview_rect.bottom + 30, 160, 40)
            phover = play_btn.collidepoint(pygame.mouse.get_pos())
            draw_ui_button(screen, play_btn, hovered=phover, text="Enter World", font=node_font)
            
            delete_btn = pygame.Rect(preview_rect.centerx - 60, play_btn.bottom + 16, 120, 30)
            dhover = delete_btn.collidepoint(pygame.mouse.get_pos())
            pygame.draw.rect(screen, (60, 20, 20) if dhover else (40, 10, 10), delete_btn, border_radius=6)
            pygame.draw.rect(screen, (180, 60, 60) if dhover else (120, 40, 40), delete_btn, 1, border_radius=6)
            del_s = tiny_font.render("Delete", True, (220, 160, 160))
            screen.blit(del_s, (delete_btn.centerx - del_s.get_width() // 2, delete_btn.centery - del_s.get_height() // 2))

        elif selected_idx == -1:
            # New Character Preview
            hint = info_font.render("Create a new hero to begin your journey.", True, (160, 160, 170))
            screen.blit(hint, (preview_rect.centerx - hint.get_width() // 2, preview_rect.centery))
            
            create_btn = pygame.Rect(preview_rect.centerx - 80, preview_rect.bottom + 30, 160, 40)
            chover = create_btn.collidepoint(pygame.mouse.get_pos())
            draw_ui_button(screen, create_btn, hovered=chover, text="Create", font=node_font, color=(120, 220, 120))

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return None
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return None
                if event.key == pygame.K_RETURN:
                    return selected_idx
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    # Check list clicks
                    if create_rect.collidepoint(event.pos):
                        selected_idx = -1
                    for i in range(len(saves)):
                        r = pygame.Rect(list_x, list_y + 80 + i * 70, list_w, 60)
                        if r.collidepoint(event.pos):
                            selected_idx = i
                    
                    # Check button clicks
                    if selected_idx >= 0 and selected_idx < len(saves):
                        play_btn = pygame.Rect(preview_rect.centerx - 80, preview_rect.bottom + 30, 160, 40)
                        if play_btn.collidepoint(event.pos):
                            return selected_idx
                        delete_btn = pygame.Rect(preview_rect.centerx - 60, play_btn.bottom + 16, 120, 30)
                        if delete_btn.collidepoint(event.pos):
                            saves.pop(selected_idx)
                            save_all_saves(saves)
                            if selected_idx >= len(saves):
                                selected_idx = max(-1, len(saves) - 1)
                            if not saves:
                                selected_idx = -1
                    elif selected_idx == -1:
                        create_btn = pygame.Rect(preview_rect.centerx - 80, preview_rect.bottom + 30, 160, 40)
                        if create_btn.collidepoint(event.pos):
                            return selected_idx

        pygame.display.flip()
        clock.tick_busy_loop(FPS)


INTRO_CINEMATIC_DEFAULT_FINAL_CAPTION = (
    "You came to Sangeroasa for your own reasons. Gold, truth, vengeance, faith — the valley does not care."
)

INTRO_CINEMATIC_CLASS_FINAL_CAPTIONS: Dict[str, str] = {
    "mage": "Ley-lines bleed beneath this valley. The wolves carry traces of what you came to study.",
    "ranger": "Somewhere in these woods, your trail ends where your sibling's vanished.",
    "rogue": "A bounty brought you here. Someone in Sangeroasa still owes a debt in blood.",
    "necromancer": "The veil is thin in this valley. Wolf-spirits cross it, and you came to master what slips through.",
    "warrior": "You came for monsters, not mercy. Sangeroasa has plenty of both.",
    "paladin": "Your order sent an envoy who never returned. You came to finish what faith began.",
}


def play_intro_cinematic(
    screen: pygame.Surface,
    clock: pygame.time.Clock,
    fonts: Dict[str, pygame.font.Font],
    town_surface: pygame.Surface,
    wilderness_surface: pygame.Surface,
    player_name: str,
    player_class: str,
    start_level: str,
    start_pos: Vector2,
    audio: Optional[GameAudio] = None,
) -> str:
    title_font = fonts["title"]
    body_font = fonts["dialog_text"]
    tiny_font = fonts["tiny"]

    def resolve_final_caption(raw_class: object) -> str:
        key = str(raw_class).strip().lower()
        if key in INTRO_CINEMATIC_CLASS_FINAL_CAPTIONS:
            return INTRO_CINEMATIC_CLASS_FINAL_CAPTIONS[key]
        for class_id, class_data in CLASS_ARCHETYPES.items():
            class_name = str(class_data.get("name", "")).strip().lower()
            if key and key == class_name:
                return INTRO_CINEMATIC_CLASS_FINAL_CAPTIONS.get(class_id, INTRO_CINEMATIC_DEFAULT_FINAL_CAPTION)
        return INTRO_CINEMATIC_DEFAULT_FINAL_CAPTION

    start_level_norm = "wilderness" if str(start_level).strip().lower() == "wilderness" else "town"
    if isinstance(start_pos, Vector2):
        entry_pos = Vector2(start_pos)
    else:
        entry_pos = Vector2(WORLD_WIDTH * 0.5, HORIZON_Y + 760)

    display_name = str(player_name).strip() or "Traveler"
    final_caption = resolve_final_caption(player_class)

    # Per-shot script and timing are centralized for easy tuning.
    shots: List[Dict[str, object]] = [
        {
            "world": "town",
            "focus": Vector2(WORLD_WIDTH * 0.5, HORIZON_Y + 260),
            "drift": Vector2(240.0, 20.0),
            "duration": 3.6,
            "headline": "Sangeroasa",
            "caption": "Old stone. Dim lanterns. A cathedral built over older bones. In Sangeroasa, every alley keeps a secret.",
        },
        {
            "world": "town",
            "focus": Vector2(WORLD_WIDTH * 0.5 - 260.0, HORIZON_Y + 770),
            "drift": Vector2(320.0, -26.0),
            "duration": 3.4,
            "headline": "Raven Hollow",
            "caption": "The gate district never truly sleeps. Merchants, guards, and refugees all pass through — if the dark lets them.",
        },
        {
            "world": "wilderness",
            "focus": Vector2(WILDERNESS_WIDTH * 0.5, HORIZON_Y + 980),
            "drift": Vector2(-420.0, 42.0),
            "duration": 3.8,
            "headline": "The Wilderness",
            "caption": "Beyond the walls, wolf packs rule the trails. Pelts, bones, and venom buy survival — if you return alive.",
        },
        {
            "world": start_level_norm,
            "focus": Vector2(entry_pos),
            "drift": Vector2(180.0, 0.0),
            "duration": 3.8,
            "headline": display_name,
            "caption": final_caption,
        },
    ]

    vignette = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    for i in range(0, 66):
        alpha = int(1 + (i / 65.0) * 4.0)
        rect = pygame.Rect(i, i, SCREEN_WIDTH - i * 2, SCREEN_HEIGHT - i * 2)
        if rect.width > 0 and rect.height > 0:
            pygame.draw.rect(vignette, (0, 0, 0, alpha), rect, width=2, border_radius=26)

    shot_idx = 0
    shot_t = 0.0
    total_t = 0.0
    fade_in_s = 1.05
    current_music_track = ""

    while shot_idx < len(shots):
        clock.tick_busy_loop(FPS)
        dt = FRAME_DT
        total_t += dt
        shot_t += dt

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "QUIT"
            if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE):
                return "DONE"
            if event.type == pygame.MOUSEBUTTONDOWN and event.button in (1, 3):
                return "DONE"

        shot = shots[shot_idx]
        duration = max(0.4, float(shot.get("duration", 3.5)))
        if shot_t >= duration:
            shot_t -= duration
            shot_idx += 1
            continue

        world_name = str(shot.get("world", "town")).strip().lower()
        if world_name == "wilderness":
            level_surface = wilderness_surface if isinstance(wilderness_surface, pygame.Surface) else None
            world_w = WILDERNESS_WIDTH
            world_h = WILDERNESS_HEIGHT
            target_track = "wilderness"
        else:
            level_surface = town_surface if isinstance(town_surface, pygame.Surface) else None
            world_w = WORLD_WIDTH
            world_h = WORLD_HEIGHT
            target_track = "town"

        if isinstance(audio, GameAudio) and current_music_track != target_track:
            # TODO: add dedicated one-shot bell/wind cinematic stingers when unique ambience assets are available.
            audio.ensure_level_theme(target_track, force=True)
            current_music_track = target_track

        focus_raw = shot.get("focus")
        focus = Vector2(focus_raw) if isinstance(focus_raw, Vector2) else Vector2(world_w * 0.5, world_h * 0.5)
        drift_raw = shot.get("drift")
        drift = Vector2(drift_raw) if isinstance(drift_raw, Vector2) else Vector2(0, 0)
        t = clamp(shot_t / duration, 0.0, 1.0)
        ease = 0.5 - 0.5 * math.cos(math.pi * t)
        cam_focus = (focus - drift * 0.5).lerp(focus + drift * 0.5, ease)

        cam_x = clamp(cam_focus.x - SCREEN_WIDTH * 0.5, 0, max(0, world_w - SCREEN_WIDTH))
        cam_y = clamp(cam_focus.y - SCREEN_HEIGHT * 0.56, 0, max(0, world_h - SCREEN_HEIGHT))

        if isinstance(level_surface, pygame.Surface):
            screen.blit(level_surface, (-int(cam_x), -int(cam_y)))
        else:
            draw_vertical_gradient(screen, pygame.Rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT), (8, 10, 16), (22, 26, 36))

        tint = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        tint.fill((8, 10, 16, 118))
        screen.blit(tint, (0, 0))
        screen.blit(vignette, (0, 0))

        letterbox_t = clamp(total_t / 0.65, 0.0, 1.0)
        bar_h = int(78 * letterbox_t)
        if bar_h > 0:
            pygame.draw.rect(screen, (0, 0, 0), pygame.Rect(0, 0, SCREEN_WIDTH, bar_h))
            pygame.draw.rect(screen, (0, 0, 0), pygame.Rect(0, SCREEN_HEIGHT - bar_h, SCREEN_WIDTH, bar_h))

        edge_fade_s = 0.9
        shot_fade = min(1.0, shot_t / edge_fade_s, (duration - shot_t) / edge_fade_s)
        shot_fade = clamp(shot_fade, 0.0, 1.0)

        panel = pygame.Rect(86, SCREEN_HEIGHT - 212, SCREEN_WIDTH - 172, 134)
        panel_surface = pygame.Surface((panel.width, panel.height), pygame.SRCALPHA)
        pygame.draw.rect(panel_surface, (6, 8, 12, int(196 * shot_fade)), panel_surface.get_rect(), border_radius=12)
        pygame.draw.rect(panel_surface, (176, 146, 102, int(220 * shot_fade)), panel_surface.get_rect(), width=1, border_radius=12)
        screen.blit(panel_surface, panel.topleft)

        headline = str(shot.get("headline", ""))
        caption = str(shot.get("caption", ""))
        txt_alpha = int(255 * shot_fade)

        title_s = title_font.render(headline, True, (238, 220, 188))
        title_s.set_alpha(txt_alpha)
        screen.blit(title_s, (panel.left + 22, panel.top + 10))

        lines = wrap_text_lines(body_font, caption, panel.width - 44, max_lines=3)
        line_y = panel.top + 64
        for line in lines:
            line_s = body_font.render(line, True, (214, 216, 224))
            line_s.set_alpha(txt_alpha)
            screen.blit(line_s, (panel.left + 22, line_y))
            line_y += line_s.get_height() + 4

        hint_s = tiny_font.render("Esc / Space / Enter / Click to skip", True, (164, 172, 188))
        hint_s.set_alpha(int(220 * shot_fade))
        screen.blit(hint_s, (SCREEN_WIDTH - hint_s.get_width() - 16, SCREEN_HEIGHT - 28))

        if total_t < fade_in_s:
            fade_in = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            fade_in.fill((0, 0, 0, int(255 * (1.0 - total_t / fade_in_s))))
            screen.blit(fade_in, (0, 0))

        transition_alpha = int(255 * (1.0 - shot_fade))
        if transition_alpha > 0:
            fade_between = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            fade_between.fill((0, 0, 0, transition_alpha))
            screen.blit(fade_between, (0, 0))

        pygame.display.flip()

    return "DONE"


def run_session(
    screen: pygame.Surface,
    clock: pygame.time.Clock,
    audio: GameAudio,
    fonts: Dict[str, pygame.font.Font],
    assets: Dict[str, object],
    character_data: Dict,
    save_callback: object, # Callable
) -> str:
    """
    Runs the main game loop for a specific character.
    Returns "MENU" to go back to character selection, or "QUIT".
    """
    # Unpack fonts
    font = fonts["main"]
    ui_font = fonts["ui"]
    tiny_font = fonts["tiny"]
    dialog_name_font = fonts["dialog_name"]
    dialog_text_font = fonts["dialog_text"]
    skill_title_font = fonts["skill_title"]
    skill_node_font = fonts["node"]
    skill_info_font = fonts["info"]
    npc_name_font = fonts["npc_name"]

    # Unpack assets
    rogue_choices = assets["rogue_choices"]
    class_visuals = assets["class_visuals"]
    town_surface = assets["town_surface"]
    town_obstacles = assets["town_obstacles"]
    town_canals = assets["town_canals"]
    town_house_overlays = assets.get("town_house_overlays", [])
    town_foliage_anim: list = assets.get("town_foliage_anim", [])
    wilderness_surface = assets["wilderness_surface"]
    wilderness_obstacles = assets["wilderness_obstacles"]
    wilderness_spawn_points = assets["wilderness_spawn_points"]
    ice_surface = assets.get("ice_surface")
    ice_obstacles: List[pygame.Rect] = list(assets.get("ice_obstacles", []))
    ice_spawn_points: List[Vector2] = list(assets.get("ice_spawn_points", []))
    ice_predators: List[Dict[str, object]] = list(assets.get("ice_predators", []))
    ice_passives: List[Dict[str, object]] = list(assets.get("ice_passives", []))
    town_walk_bounds = assets["town_walk_bounds"]
    wilderness_walk_bounds = assets["wilderness_walk_bounds"]
    ice_walk_bounds: pygame.Rect = assets.get("ice_walk_bounds", pygame.Rect(70, HORIZON_Y + 92, ICE_WIDTH - 140, ICE_HEIGHT - (HORIZON_Y + 172)))
    spell_icons = assets["spell_icons"]
    external_item_library = assets["external_item_library"]
    predator_archetypes = assets["predator_archetypes"]
    prey_archetypes = assets["prey_archetypes"]
    vendor_archetypes = assets["vendor_archetypes"]

    town_road_rects: list = assets.get("town_road_rects", [])
    town_farm_pens: list = assets.get("town_farm_pens", [])
    fire_frames = assets.get("fire_frames", [])
    lpc_wolf_frames = assets.get("lpc_wolf_frames")
    town_chimney_tops: List[Tuple[int, int]] = list(assets.get("town_chimney_tops", []))
    level_decor_assets = assets.get("level_decor_assets")
    if not isinstance(level_decor_assets, dict):
        level_decor_assets = load_level_decor_assets()
        assets["level_decor_assets"] = level_decor_assets
    level_decor_layout = assets.get("level_decor_layout")
    if not isinstance(level_decor_layout, dict):
        level_decor_layout = load_level_decor_layout()
        assets["level_decor_layout"] = level_decor_layout

    # Load character data
    selected_class = normalize_class_id(character_data.get("class", "rogue"))
    character_data["class"] = selected_class
    player_name = str(character_data.get("player_name", "Hero"))
    
    active_class = CLASS_ARCHETYPES[selected_class]
    active_spellbook = class_spellbook(selected_class)
    full_class_spellbook = list(CLASS_ARCHETYPES[selected_class].get("spellbook", []))
    active_skill_tree = class_skill_tree(selected_class)
    active_stats = class_combat_stats(selected_class)
    active_passive = class_passive_data(selected_class)
    passive_effects = class_passive_effects(selected_class)
    passive_name = str(active_passive.get("name", "Class Passive"))
    passive_damage_mult = max(0.1, float(passive_effects.get("damage_mult", 1.0)))
    passive_mana_regen_mult = max(0.1, float(passive_effects.get("mana_regen_mult", 1.0)))
    passive_mana_cost_mult = max(0.1, float(passive_effects.get("mana_cost_mult", 1.0)))
    passive_spell_cooldown_mult = max(0.1, float(passive_effects.get("spell_cooldown_mult", 1.0)))
    passive_basic_cooldown_mult = max(0.1, float(passive_effects.get("basic_cooldown_mult", 1.0)))
    passive_move_speed_mult = max(0.1, float(passive_effects.get("move_speed_mult", 1.0)))
    passive_incoming_damage_mult = max(0.1, float(passive_effects.get("incoming_damage_mult", 1.0)))

    selected_entry: Dict[str, object] = {}
    player_sprite = rogue_choices[0].get("sprite")
    player_sprite_left = rogue_choices[0].get("sprite_left")
    player_anim_frames: Optional[Dict[str, Dict[str, List[pygame.Surface]]]] = None
    player_anim_fps: Dict[str, float] = {}
    player_anim_durations: Dict[str, float] = {}
    
    gothic_cursor_surface, gothic_cursor_hotspot = build_gothic_cursor()
    pouch_cursor_surface, pouch_cursor_hotspot = build_pouch_cursor()
    vendor_shop_icon = build_vendor_shop_icon()
    # Build red X delete cursor
    _del_cur_sz = 28
    delete_cursor_surface = pygame.Surface((_del_cur_sz, _del_cur_sz), pygame.SRCALPHA)
    _dc_c = _del_cur_sz // 2
    pygame.draw.circle(delete_cursor_surface, (180, 30, 30, 180), (_dc_c, _dc_c), 12, 2)
    pygame.draw.line(delete_cursor_surface, (220, 40, 40, 230), (_dc_c - 7, _dc_c - 7), (_dc_c + 7, _dc_c + 7), 3)
    pygame.draw.line(delete_cursor_surface, (220, 40, 40, 230), (_dc_c + 7, _dc_c - 7), (_dc_c - 7, _dc_c + 7), 3)
    delete_cursor_hotspot = (_dc_c, _dc_c)
    pygame.mouse.set_visible(False)

    day_night = DayNightCycle()
    status_effects = StatusEffectSystem()
    screen_effects = ScreenEffectController()
    level_up_vfx = LevelUpVFX()

    external_by_rarity: Dict[str, List[Dict[str, object]]] = {
        "common": [],
        "rare": [],
        "epic": [],
        "legendary": [],
    }
    for ext_item in external_item_library:
        rarity = item_rarity(ext_item)
        if rarity in external_by_rarity:
            external_by_rarity[rarity].append(ext_item)

    cooldowns = {str(spell["id"]): 0.0 for spell in active_spellbook}
    spell_global_cooldown = 0.0
    mana_regen_lock_timer = 0.0
    spell_effects: List[Dict[str, object]] = []
    summoned_skeletons: List[Dict[str, object]] = []
    active_ultimates: List[UltimateBase] = []
    damage_numbers: List[Dict[str, object]] = []
    selected_spell_idx = 0
    spell_slot_keybinds: List[int] = [
        pygame.K_q, pygame.K_w, pygame.K_e, pygame.K_r, pygame.K_t,
        pygame.K_1, pygame.K_2, pygame.K_3,
    ]
    keybind_editing_slot: int = -1   # -1 = not editing; 0-7 = slot being rebound
    _spell_bar_slot_rects: List[pygame.Rect] = []  # updated each frame by draw_spell_bar

    # Load progress from character_data
    unlocked_skills: Set[str] = set(str(s) for s in character_data.get("unlocked_skills", []))
    if not unlocked_skills:
        unlocked_skills = set(str(node) for node in active_class.get("starter_skills", []))
        
    skill_points = int(character_data.get("skill_points", 4))
    skill_hover: Optional[str] = None
    skill_node_rects: Dict[str, pygame.Rect] = {}

    wolves_slain = int(character_data.get("wolves_slain", 0))
    player_level = max(1, int(character_data.get("player_level", 1)))
    player_xp = float(character_data.get("player_xp", 0.0))
    player_xp_next = float(xp_required_for_level(player_level))
    wolf_respawn_timer = 0.0
    passive_respawn_timer = 0.0
    passive_target_count = 220
    player_anim_timer = 0.0
    player_gold = int(character_data.get("gold", 0))
    damage_boost_timer = 0.0   # seconds remaining for Blacksmith buff
    shop_open: Optional[str] = None  # role of vendor whose shop is open

    # Level-up perk selection
    perk_choice_pending: bool = False
    perk_choices: List[Dict[str, object]] = []
    perk_hover_idx: int = -1

    # All possible perks pool
    ALL_PERKS: List[Dict[str, object]] = [
        {"id": "hp",      "name": "Vitality",       "desc": "Max HP +25",         "col": (200, 80, 80)},
        {"id": "mana",    "name": "Arcane Flow",     "desc": "Max Mana +25",       "col": (80, 130, 220)},
        {"id": "regen",   "name": "Mana Spring",     "desc": "Mana Regen +2/s",    "col": (100, 180, 240)},
        {"id": "speed",   "name": "Swift Feet",      "desc": "Move Speed +8%",     "col": (120, 220, 140)},
        {"id": "dmg",     "name": "Combat Edge",     "desc": "Spell Power +10%",   "col": (240, 150, 60)},
        {"id": "hp_regen","name": "Iron Blood",      "desc": "Regen 2 HP/s passively", "col": (220, 80, 100)},
        {"id": "sp",      "name": "Insight",         "desc": "+2 Skill Points",    "col": (200, 160, 240)},
        {"id": "gold",    "name": "Merchant's Eye",  "desc": "+30 Gold",           "col": (220, 200, 80)},
    ]

    # Fishing system state
    fishing_active: bool = False
    fishing_timer: float = 0.0        # countdown for catch window
    fishing_bar_pos: float = 0.5      # 0..1 position of moving target on bar
    fishing_bar_vel: float = 0.8      # speed of target movement
    fishing_catch_zone: float = 0.0   # left edge of catch zone 0..1
    fishing_result: str = ""          # "success" | "fail" | ""
    fishing_result_timer: float = 0.0
    passive_hp_regen: float = 0.0     # bonus from "iron blood" perk (HP/s)

    # Must be defined before refresh_player_visuals (captured as free variable)
    equipped_items: Dict[str, Dict[str, object]] = {
        k: clone_item_data(v) for k, v in character_data.get("equipped_items", {}).items()
    }

    base_player_sprite: Optional[pygame.Surface] = None
    base_player_sprite_left: Optional[pygame.Surface] = None
    base_player_anim_frames: Optional[Dict[str, Dict[str, List[pygame.Surface]]]] = None
    player_equip_tint: Optional[pygame.Surface] = None
    player_equip_tint_left: Optional[pygame.Surface] = None

    def refresh_player_visuals() -> None:
        nonlocal selected_entry, player_sprite, player_sprite_left, player_anim_frames, player_anim_fps, player_anim_durations, base_player_sprite, base_player_sprite_left, base_player_anim_frames, player_equip_tint, player_equip_tint_left
        selected_entry = resolve_class_visual_entry(class_visuals, selected_class, player_level, rogue_choices[0])

        sprite_candidate = selected_entry.get("sprite")
        sprite_left_candidate = selected_entry.get("sprite_left")
        fallback_entry = rogue_choices[0]
        fallback_sprite = fallback_entry.get("sprite")
        fallback_sprite_left = fallback_entry.get("sprite_left")

        _base_right = sprite_candidate if isinstance(sprite_candidate, pygame.Surface) else fallback_sprite
        _base_left  = sprite_left_candidate if isinstance(sprite_left_candidate, pygame.Surface) else fallback_sprite_left

        # Store clean COPIES of base sprites so originals are never corrupted
        base_player_sprite       = _base_right.copy() if isinstance(_base_right, pygame.Surface) else _base_right
        base_player_sprite_left  = _base_left.copy() if isinstance(_base_left, pygame.Surface) else _base_left

        # Clear stale sprite hue caches (Python reuses object ids)
        _SPRITE_HUE_CACHE.clear()
        _CLOTH_HUE_CACHE.clear()

        # Apply equipment chromakey on the right-facing sprite, then flip for left.
        _cls_color = CLASS_PALETTES.get(selected_class, CLASS_PALETTES.get("default", {})).get("primary", (160, 160, 180))
        player_sprite       = build_equipped_sprite(base_player_sprite, equipped_items, _cls_color)
        player_sprite_left  = pygame.transform.flip(player_sprite, True, False)

        # Tint overlays disabled — chromakey is baked into the sprite now.
        player_equip_tint      = None
        player_equip_tint_left = None

        frames_candidate = selected_entry.get("anim_frames")
        # Deep-copy base frames so re-equipping always starts from clean originals
        if isinstance(frames_candidate, dict):
            base_player_anim_frames = _deep_copy_anim_frames(frames_candidate)
        else:
            base_player_anim_frames = None

        # Apply equipment recoloring to every animation frame
        if isinstance(base_player_anim_frames, dict):
            player_anim_frames = build_equipped_anim_frames(base_player_anim_frames, equipped_items, _cls_color)
        else:
            player_anim_frames = None

        fps_candidate = selected_entry.get("anim_fps")
        player_anim_fps = dict(fps_candidate) if isinstance(fps_candidate, dict) else {}

        durations_candidate = selected_entry.get("anim_durations")
        player_anim_durations = dict(durations_candidate) if isinstance(durations_candidate, dict) else {}

    def refresh_palette_swap() -> None:
        """Re-run only the palette-swap step (fast path: no anim reload)."""
        nonlocal player_sprite, player_sprite_left, player_anim_frames, player_equip_tint, player_equip_tint_left
        _SPRITE_HUE_CACHE.clear()
        _CLOTH_HUE_CACHE.clear()
        _cls_color = CLASS_PALETTES.get(selected_class, CLASS_PALETTES.get("default", {})).get("primary", (160, 160, 180))
        if isinstance(base_player_sprite, pygame.Surface):
            player_sprite      = build_equipped_sprite(base_player_sprite,      equipped_items, _cls_color)
            player_sprite_left = build_equipped_sprite(base_player_sprite_left, equipped_items, _cls_color)
            player_equip_tint      = None
            player_equip_tint_left = None
        # Recolor animation frames from clean base copies
        if isinstance(base_player_anim_frames, dict):
            player_anim_frames = build_equipped_anim_frames(base_player_anim_frames, equipped_items, _cls_color)

    refresh_player_visuals()

    # ── Crafting & Quest state ─────────────────────────────────────────────────
    materials: Dict[str, int] = {str(k): int(v) for k, v in character_data.get("materials", {}).items()}
    item_inventory: List[Optional[Dict]] = [None] * HOTBAR_SLOT_COUNT  # fixed 4-slot potion bar
    backpack_inventory: List[Dict] = []       # overflow consumables
    
    # Load inventories
    for i, d in enumerate(character_data.get("item_inventory", [])):
        if i < HOTBAR_SLOT_COUNT:
            item_inventory[i] = clone_item_data(d) if d else None
    for d in character_data.get("backpack_inventory", []):
        if len(backpack_inventory) < BACKPACK_SLOT_COUNT:
            entry = clone_item_data(d)
            if not item_is_food(entry):
                backpack_inventory.append(entry)
    for i in range(HOTBAR_SLOT_COUNT):
        if item_is_food(item_inventory[i]):
            item_inventory[i] = None
    # New characters start with 4 health potions + Book of Teleportation
    if not character_data.get("item_inventory") and not character_data.get("backpack_inventory"):
        for i in range(4):
            item_inventory[i] = {"id": f"starter_hp_{i}", "name": "Health Potion", "effect": "hp_60",
                "icon": (19, 1), "color": (200, 60, 60), "rarity": "common",
                "item_type": "consumable", "equip_slot": "", "desc": "Restores 60 HP."}
        backpack_inventory.append(dict(TELEPORT_BOOK_ITEM))
    # Ensure existing characters also have the Book of Teleportation
    _has_teleport_book = any(
        str(s.get("id", "") if s else "") == "book_of_teleportation"
        for s in list(item_inventory) + list(backpack_inventory)
    )
    if not _has_teleport_book:
        backpack_inventory.append(dict(TELEPORT_BOOK_ITEM))
        
    quest_states: Dict[str, str] = dict(character_data.get("quest_states", {}))
    quest_progress: Dict[str, List[int]] = {k: list(v) for k, v in character_data.get("quest_progress", {}).items()}
    
    show_crafting = False
    show_professions = False
    show_professions = False
    show_quest_log = False
    quest_actions_from_vendor = False
    quest_vendor_role: Optional[str] = None
    show_character = False

    # ── Delete-item confirmation dialog (WoW-style "type DELETE") ─────────────
    delete_confirm_item: Optional[Dict[str, object]] = None   # item pending deletion
    delete_confirm_source: str = ""   # "backpack:N" or "equip:slot"
    delete_confirm_typed: str = ""    # what the player has typed so far

    crafting_selected: Optional[str] = character_data.get("selected_recipe")
    selected_profession = str(character_data.get("selected_profession", PROFESSION_ORDER[0] if PROFESSION_ORDER else "alchemy"))
    
    profession_state: Dict[str, Dict[str, float]] = {
        pid: {"skill": 1.0, "xp": 0.0, "crafted": 0.0} for pid in PROFESSION_ORDER
    }
    saved_prof = character_data.get("profession_state", {})
    for pid, val in saved_prof.items():
        if pid in profession_state:
            profession_state[pid] = val

    dialogue_flags: Set[str] = set(character_data.get("dialogue_flags", []))
    character_data["dialogue_flags"] = dialogue_flags
            
    quest_selected: Optional[str] = None         # selected quest id in quest log
    crafting_rects: Dict[str, pygame.Rect] = {}
    profession_tab_rects: Dict[str, pygame.Rect] = {}
    profession_craft_rect = pygame.Rect(0, 0, 0, 0)
    quest_rects: Dict[str, pygame.Rect] = {}
    speed_boost_timer = 0.0
    potion_last_used_ms: int = 0   # ms timestamp of last potion use (anti-repeat guard)
    show_spellbook: bool = False   # WoW-style spellbook overlay toggle [N]
    spellbook_tab: str = "class"   # active tab: "class" | "passive" | "general"
    bonus_max_hp = float(character_data.get("bonus_max_hp", 0.0))
    bonus_mana_regen = float(character_data.get("bonus_mana_regen", 0.0))
    iron_coat_count = int(character_data.get("iron_coat_count", 0))
    fang_amulet_count = int(character_data.get("fang_amulet_count", 0))
    
    loot_piles: List[Dict] = []
    open_loot_windows: List[Dict[str, int]] = []
    loot_window_rects: Dict[int, pygame.Rect] = {}
    loot_close_rects: Dict[int, pygame.Rect] = {}
    loot_take_all_rects: Dict[int, pygame.Rect] = {}
    loot_entry_rects: Dict[Tuple[int, str, str], pygame.Rect] = {}
    next_loot_pile_id = 1
    npc_menu_mode: str = ""          # "" | "menu" | "chat" | "shop"
    active_dialogue: Optional[DialogueSession] = None
    npc_option_rects: Dict[str, pygame.Rect] = {}
    inv_tab: str = "Backpack"
    inv_slot_rects: Dict[int, pygame.Rect] = {}
    backpack_slot_rects: Dict[int, pygame.Rect] = {}
    potion_slot_rects: Dict[int, pygame.Rect] = {}
    _backpack_btn_rect: pygame.Rect = pygame.Rect(0, 0, 0, 0)
    inv_tab_rects: Dict[str, pygame.Rect] = {}
    character_slot_rects: Dict[str, pygame.Rect] = {}
    drag_item: Optional[Dict[str, object]] = None
    drag_source_kind: str = ""
    drag_source_id: Optional[Union[int, str]] = None
    char_stat_view: str = "Attributes"
    char_dropdown_open: bool = False

    def sync_dialogue_data(save: bool) -> None:
        nonlocal player_gold, player_xp, skill_points, backpack_inventory, materials, quest_states, quest_progress
        if save:
            character_data["gold"] = player_gold
            character_data["player_xp"] = player_xp
            character_data["skill_points"] = skill_points
            character_data["backpack_inventory"] = backpack_inventory
            character_data["materials"] = materials
            character_data["quest_states"] = quest_states
            character_data["quest_progress"] = quest_progress
            character_data["dialogue_flags"] = dialogue_flags
        else:
            player_gold = int(character_data.get("gold", 0))
            player_xp = float(character_data.get("player_xp", 0))
            skill_points = int(character_data.get("skill_points", 0))
            # Re-clone inventory to ensure local list matches data
            backpack_inventory[:] = []
            for d in character_data.get("backpack_inventory", []):
                if len(backpack_inventory) >= BACKPACK_SLOT_COUNT:
                    break
                entry = clone_item_data(d)
                if item_is_food(entry):
                    continue
                backpack_inventory.append(entry)
            materials.clear(); materials.update(character_data.get("materials", {}))
            quest_states.clear(); quest_states.update(character_data.get("quest_states", {}))
            quest_progress.clear(); quest_progress.update(character_data.get("quest_progress", {}))

    # Initialise quest availability (quests with no requirements start as available)
    def refresh_quest_availability() -> None:
        open_roles: Set[str] = set()
        for qdef in QUEST_DEFINITIONS:
            qid = str(qdef.get("id", "")).strip()
            if not qid:
                continue
            state = str(quest_states.get(qid, "")).strip().lower()
            if state in ("available", "active", "complete"):
                role = _quest_role_for_def(qdef)
                if role:
                    open_roles.add(role)
        added_roles: Set[str] = set()
        for qdef in QUEST_DEFINITIONS:
            qid = qdef["id"]
            if qid in quest_states:
                continue
            reqs_met = all(quest_states.get(r) == "turned_in" for r in qdef["requires"])
            if reqs_met:
                role = _quest_role_for_def(qdef)
                if role and (role in open_roles or role in added_roles):
                    continue
                quest_states[qid] = "available"
                if role:
                    added_roles.add(role)
        normalize_vendor_available_quests(quest_states, QUEST_DEFINITIONS)

    refresh_quest_availability()

    def check_quest_completions() -> None:
        for qdef in QUEST_DEFINITIONS:
            qid = qdef["id"]
            if quest_states.get(qid) != "active":
                continue
            prog = quest_progress.get(qid, [0] * len(qdef["objectives"]))
            if all(prog[i] >= obj["count"] for i, obj in enumerate(qdef["objectives"])):
                quest_states[qid] = "complete"
                set_status(f"Quest complete: {qdef['title']}! Turn it in at a town NPC/vendor.", 3.0)

    def update_kill_quests(count: int) -> None:
        for qdef in QUEST_DEFINITIONS:
            qid = qdef["id"]
            if quest_states.get(qid) != "active":
                continue
            prog = quest_progress.setdefault(qid, [0] * len(qdef["objectives"]))
            for i, obj in enumerate(qdef["objectives"]):
                if obj["type"] == "kill":
                    prog[i] = min(prog[i] + count, obj["count"])
        check_quest_completions()

    def update_gather_quests() -> None:
        for qdef in QUEST_DEFINITIONS:
            qid = qdef["id"]
            if quest_states.get(qid) != "active":
                continue
            prog = quest_progress.setdefault(qid, [0] * len(qdef["objectives"]))
            for i, obj in enumerate(qdef["objectives"]):
                if obj["type"] == "gather":
                    prog[i] = min(materials.get(obj["item"], 0), obj["count"])
        check_quest_completions()

    def update_craft_quests(recipe_id: str) -> None:
        for qdef in QUEST_DEFINITIONS:
            qid = qdef["id"]
            if quest_states.get(qid) != "active":
                continue
            prog = quest_progress.setdefault(qid, [0] * len(qdef["objectives"]))
            for i, obj in enumerate(qdef["objectives"]):
                if obj["type"] == "craft" and obj.get("recipe_id") == recipe_id:
                    prog[i] = min(prog[i] + 1, obj["count"])
        check_quest_completions()

    def update_kill_type_quests(enemy_name: str, count: int = 1) -> None:
        """Track kills of specific enemy types (e.g. 'Grizzly Bear')."""
        for qdef in QUEST_DEFINITIONS:
            qid = qdef["id"]
            if quest_states.get(qid) != "active":
                continue
            prog = quest_progress.setdefault(qid, [0] * len(qdef["objectives"]))
            for i, obj in enumerate(qdef["objectives"]):
                if obj["type"] == "kill_type" and obj.get("enemy_name") == enemy_name:
                    prog[i] = min(prog[i] + count, obj["count"])
        check_quest_completions()

    def update_talk_to_quests(vendor_role: str) -> None:
        """Track talking to specific vendor roles."""
        for qdef in QUEST_DEFINITIONS:
            qid = qdef["id"]
            if quest_states.get(qid) != "active":
                continue
            prog = quest_progress.setdefault(qid, [0] * len(qdef["objectives"]))
            for i, obj in enumerate(qdef["objectives"]):
                if obj["type"] == "talk_to" and obj.get("vendor_role") == vendor_role:
                    prog[i] = min(prog[i] + 1, obj["count"])
        check_quest_completions()

    def update_visit_level_quests(level_name: str) -> None:
        """Track entering a specific level/zone."""
        for qdef in QUEST_DEFINITIONS:
            qid = qdef["id"]
            if quest_states.get(qid) != "active":
                continue
            prog = quest_progress.setdefault(qid, [0] * len(qdef["objectives"]))
            for i, obj in enumerate(qdef["objectives"]):
                if obj["type"] == "visit_level" and obj.get("level") == level_name:
                    prog[i] = min(1, obj["count"])
        check_quest_completions()

    def update_reach_level_quests() -> None:
        """Sync player level with reach_level objectives."""
        for qdef in QUEST_DEFINITIONS:
            qid = qdef["id"]
            if quest_states.get(qid) != "active":
                continue
            prog = quest_progress.setdefault(qid, [0] * len(qdef["objectives"]))
            for i, obj in enumerate(qdef["objectives"]):
                if obj["type"] == "reach_level":
                    prog[i] = min(player_level, obj["count"])
        check_quest_completions()

    def update_gold_accumulate_quests() -> None:
        """Sync current gold with gold_accumulate objectives."""
        for qdef in QUEST_DEFINITIONS:
            qid = qdef["id"]
            if quest_states.get(qid) != "active":
                continue
            prog = quest_progress.setdefault(qid, [0] * len(qdef["objectives"]))
            for i, obj in enumerate(qdef["objectives"]):
                if obj["type"] == "gold_accumulate":
                    prog[i] = min(player_gold, obj["count"])
        check_quest_completions()

    def update_survive_time_quests(dt: float) -> None:
        """Accumulate time spent in wilderness for survive_time objectives."""
        if current_level not in ("wilderness", "ice_biome"):
            return
        for qdef in QUEST_DEFINITIONS:
            qid = qdef["id"]
            if quest_states.get(qid) != "active":
                continue
            prog = quest_progress.setdefault(qid, [0] * len(qdef["objectives"]))
            for i, obj in enumerate(qdef["objectives"]):
                if obj["type"] == "survive_time":
                    prog[i] = min(int(prog[i] + dt), obj["count"])
        check_quest_completions()

    def update_profession_skill_quests() -> None:
        """Sync profession skill levels with profession_skill objectives."""
        for qdef in QUEST_DEFINITIONS:
            qid = qdef["id"]
            if quest_states.get(qid) != "active":
                continue
            prog = quest_progress.setdefault(qid, [0] * len(qdef["objectives"]))
            for i, obj in enumerate(qdef["objectives"]):
                if obj["type"] == "profession_skill":
                    prof = obj.get("profession", "alchemy")
                    skill_val = int(profession_state.get(prof, {}).get("skill", 1))
                    prog[i] = min(skill_val, obj["count"])
        check_quest_completions()

    def update_equip_slot_quests() -> None:
        """Sync equipped item slots with equip_slot objectives."""
        for qdef in QUEST_DEFINITIONS:
            qid = qdef["id"]
            if quest_states.get(qid) != "active":
                continue
            prog = quest_progress.setdefault(qid, [0] * len(qdef["objectives"]))
            for i, obj in enumerate(qdef["objectives"]):
                if obj["type"] == "equip_slot":
                    slot = obj.get("slot", "weapon")
                    prog[i] = 1 if equipped_items.get(slot) else 0
        check_quest_completions()

    def update_spend_gold_quests(amount: int) -> None:
        """Track gold spent at vendors."""
        for qdef in QUEST_DEFINITIONS:
            qid = qdef["id"]
            if quest_states.get(qid) != "active":
                continue
            prog = quest_progress.setdefault(qid, [0] * len(qdef["objectives"]))
            for i, obj in enumerate(qdef["objectives"]):
                if obj["type"] == "spend_gold":
                    prog[i] = min(prog[i] + amount, obj["count"])
        check_quest_completions()

    def recipes_for_profession(prof_id: str) -> List[Dict[str, object]]:
        out = [r for r in CRAFTING_RECIPES if str(r.get("profession", "alchemy")) == prof_id]
        out.sort(key=lambda r: (int(r.get("required_skill", 1)), str(r.get("name", ""))))
        return out

    def ensure_profession_selection() -> None:
        nonlocal selected_profession, crafting_selected
        if selected_profession not in PROFESSION_DEFINITIONS:
            selected_profession = PROFESSION_ORDER[0] if PROFESSION_ORDER else "alchemy"
        rows = recipes_for_profession(selected_profession)
        if not rows:
            crafting_selected = None
            return
        recipe_ids = {str(r.get("id", "")) for r in rows}
        if not isinstance(crafting_selected, str) or crafting_selected not in recipe_ids:
            crafting_selected = str(rows[0].get("id", ""))

    def grant_profession_progress(prof_id: str, recipe: dict[str, object]) -> str:
        state = profession_state.setdefault(prof_id, {"skill": 1.0, "xp": 0.0, "crafted": 0.0})
        skill = max(1, min(PROFESSION_MAX_SKILL, int(state.get("skill", 1.0))))
        xp_pool = max(0.0, float(state.get("xp", 0.0)))
        gain = max(1, int(recipe.get("xp", 10)))
        req_skill = max(1, int(recipe.get("required_skill", 1)))
        delta = skill - req_skill
        if delta >= 45:
            gain = max(1, gain // 5)
        elif delta >= 30:
            gain = max(2, gain // 3)
        elif delta >= 15:
            gain = max(3, gain // 2)
        elif delta >= 8:
            gain = max(4, int(round(gain * 0.66)))
        xp_pool += float(gain)

        skill_gained = 0
        while skill < PROFESSION_MAX_SKILL:
            needed = float(profession_xp_to_next(skill))
            if xp_pool < needed:
                break
            xp_pool -= needed
            skill += 1
            skill_gained += 1

        state["skill"] = float(skill)
        state["xp"] = float(xp_pool)
        state["crafted"] = float(max(0, int(state.get("crafted", 0.0)) + 1))
        prof_name = str(PROFESSION_DEFINITIONS.get(prof_id, {}).get("name", prof_id.title()))
        if skill_gained > 0:
            return f"{prof_name} +{skill_gained} skill ({skill}/{PROFESSION_MAX_SKILL})."
        return f"{prof_name} +{gain} XP."

    def try_craft_selected_recipe() -> bool:
        nonlocal player_max_hp, player_hp, bonus_max_hp, iron_coat_count
        nonlocal bonus_mana_regen, mana_regen, fang_amulet_count, skill_points
        ensure_profession_selection()
        if not isinstance(crafting_selected, str) or not crafting_selected:
            set_status("No recipe selected.", 1.1)
            return False
        recipe = next((r for r in CRAFTING_RECIPES if str(r.get("id", "")) == crafting_selected), None)
        if recipe is None:
            set_status("Recipe not found.", 1.1)
            return False

        recipe_prof = str(recipe.get("profession", "alchemy"))
        if recipe_prof != selected_profession:
            set_status("Selected recipe belongs to another profession.", 1.1)
            return False
        prof_data = PROFESSION_DEFINITIONS.get(recipe_prof, {})
        prof_name = str(prof_data.get("name", recipe_prof.title()))
        prof_skill = max(1, int(profession_state.get(recipe_prof, {}).get("skill", 1.0)))
        req_skill = max(1, int(recipe.get("required_skill", 1)))
        if prof_skill < req_skill:
            set_status(f"{prof_name} skill {req_skill} required.", 1.4)
            return False

        ingredients_raw = recipe.get("ingredients", {})
        ingredients = dict(ingredients_raw) if isinstance(ingredients_raw, dict) else {}
        if not all(materials.get(str(mid), 0) >= int(cnt) for mid, cnt in ingredients.items()):
            set_status("Not enough materials to craft that.", 1.4)
            return False

        result_raw = recipe.get("result", {})
        result = dict(result_raw) if isinstance(result_raw, dict) else {}
        effect = str(result.get("effect", "")).strip().lower()
        has_instant = effect in ("max_hp_15", "mana_regen_05", "skill_point")
        if not has_instant and len(backpack_inventory) >= BACKPACK_SLOT_COUNT:
            set_status("Backpack full. Free space first.", 1.4)
            return False

        for mid, cnt in ingredients.items():
            materials[str(mid)] = materials.get(str(mid), 0) - int(cnt)

        crafted_name = str(result.get("name", recipe.get("name", "Crafted Item")))
        crafted_success = False
        base_msg = ""
        eff_hp_max = player_max_hp + bonus_max_hp
        if effect == "max_hp_15":
            if iron_coat_count >= 3:
                for mid, cnt in ingredients.items():
                    materials[str(mid)] = materials.get(str(mid), 0) + int(cnt)
                set_status(f"{crafted_name} already at max stacks (3).", 1.4)
                return False
            iron_coat_count += 1
            bonus_max_hp += 15.0
            player_max_hp += 15.0
            player_hp = min(player_hp + 15.0, player_max_hp + bonus_max_hp)
            base_msg = f"Crafted {crafted_name}. Max HP permanently increased."
            crafted_success = True
        elif effect == "mana_regen_05":
            if fang_amulet_count >= 3:
                for mid, cnt in ingredients.items():
                    materials[str(mid)] = materials.get(str(mid), 0) + int(cnt)
                set_status(f"{crafted_name} already at max stacks (3).", 1.4)
                return False
            fang_amulet_count += 1
            bonus_mana_regen += 0.5
            mana_regen += 0.5
            base_msg = f"Crafted {crafted_name}. Mana regen permanently increased."
            crafted_success = True
        elif effect == "skill_point":
            skill_points += 1
            base_msg = f"Crafted {crafted_name}. +1 skill point."
            crafted_success = True
        else:
            crafted_entry = clone_item_data(result)
            crafted_entry.setdefault("id", f"{str(recipe.get('id', 'craft'))}_{pygame.time.get_ticks()}_{random.randint(100, 999)}")
            crafted_entry.setdefault("name", str(recipe.get("name", "Crafted Item")))
            crafted_entry.setdefault("desc", str(recipe.get("desc", "")))
            crafted_entry.setdefault("rarity", str(recipe.get("quality", "common")))
            crafted_entry.setdefault("item_type", "consumable")
            crafted_entry.setdefault("equip_slot", "")
            crafted_entry.setdefault("stats", {})
            crafted_entry.setdefault("class_lock", "")
            if not add_item_to_inventory(crafted_entry, prefer_hotbar=False):
                for mid, cnt in ingredients.items():
                    materials[str(mid)] = materials.get(str(mid), 0) + int(cnt)
                set_status("Backpack full. Craft canceled.", 1.4)
                return False
            if crafted_entry.get("item_type") == "equipment":
                base_msg = f"Forged {crafted_name}."
            elif effect == "hp_80":
                base_msg = f"Brewed {crafted_name}. Restores 80 HP."
            elif effect == "mp_full":
                base_msg = f"Brewed {crafted_name}. Restores full mana."
            elif effect == "dmg_boost":
                base_msg = f"Brewed {crafted_name}. +20% damage potion."
            elif effect == "dmg_boost_120":
                base_msg = f"Brewed {crafted_name}. +35% damage potion."
            elif effect == "speed_boost_60":
                base_msg = f"Brewed {crafted_name}. +28% move speed potion."
            elif effect == "full_restore":
                base_msg = f"Brewed {crafted_name}. Full restore potion."
            elif effect == "town_portal":
                base_msg = f"Inscribed {crafted_name}."
            else:
                base_msg = f"Crafted {crafted_name}."
            crafted_success = True

        if not crafted_success:
            for mid, cnt in ingredients.items():
                materials[str(mid)] = materials.get(str(mid), 0) + int(cnt)
            return False

        progress_msg = grant_profession_progress(recipe_prof, recipe)
        update_craft_quests(str(recipe.get("id", "")))
        update_gather_quests()
        update_profession_skill_quests()
        audio.play_sfx("craft", cooldown_ms=80)
        set_status(f"{base_msg} {progress_msg}", 2.1)
        return True

    ensure_profession_selection()

    def normalize_potion_hotbar() -> None:
        for i in range(HOTBAR_SLOT_COUNT):
            entry = item_inventory[i]
            if entry is None:
                continue
            if item_is_food(entry):
                item_inventory[i] = None
                continue
            if item_can_go_in_potion_bar(entry):
                continue
            if len(backpack_inventory) < BACKPACK_SLOT_COUNT:
                item_inventory[i] = None
                backpack_inventory.append(entry)

    normalize_potion_hotbar()

    def target_predator_population(tier_value: int) -> int:
        return int(clamp(35.0 + float(max(0, tier_value)) * 3.0, 35.0, 80.0))

    wolf_tier = wolves_slain // 10
    predator_target_count = target_predator_population(wolf_tier)
    wolves = build_enemies(predator_archetypes, wilderness_spawn_points, wilderness_walk_bounds, wilderness_obstacles, tier=wolf_tier, lpc_wolf_frames=lpc_wolf_frames)
    if len(wolves) > predator_target_count:
        random.shuffle(wolves)
        wolves = wolves[:predator_target_count]
    ice_wolves: List[Dict[str, object]] = build_enemies(ice_predators, ice_spawn_points, ice_walk_bounds, ice_obstacles, tier=wolf_tier, lpc_wolf_frames=lpc_wolf_frames)
    ice_wolf_respawn_timer: float = 0.0
    ice_passive_respawn_timer: float = 0.0
    ice_passive_target_count: int = 130
    selected_wolf_id: int | None = None
    passive_animals = build_passive_animals(prey_archetypes, wilderness_walk_bounds, wilderness_obstacles, count=passive_target_count)
    ice_passive_animals: List[Dict[str, object]] = build_passive_animals(ice_passives, ice_walk_bounds, ice_obstacles, count=min(80, passive_target_count))

    vendors = build_vendors(vendor_archetypes, town_walk_bounds, town_obstacles)
    farm_animals: List[Dict[str, object]] = build_farm_animals(town_farm_pens)
    # Apply any saved shop_pos overrides from npc_positions.json
    _saved_npc_data = load_npc_positions()
    _vendors_with_saved_shop: set = set()
    for _saved_entry in _saved_npc_data.get("town", []):
        if not isinstance(_saved_entry, dict):
            continue
        _saved_name = str(_saved_entry.get("name", "")).strip()
        if "shop_x" in _saved_entry and "shop_y" in _saved_entry:
            try:
                _sx = float(_saved_entry["shop_x"])
                _sy = float(_saved_entry["shop_y"])
            except (TypeError, ValueError):
                continue
            _srot = 0.0
            try:
                _srot = float(_saved_entry.get("shop_rotation", 0.0)) % 360.0
            except (TypeError, ValueError):
                _srot = 0.0
            for _vendor in vendors:
                if str(_vendor.get("name", "")).strip() == _saved_name:
                    _new_shop = Vector2(_sx, _sy)
                    _vendor["shop_pos"] = _new_shop
                    _vendor["shop_rotation"] = _srot
                    # Rebuild patrol path and place vendor in front of updated shop
                    _pts = build_shop_patrol_points(_new_shop, town_walk_bounds, town_obstacles)
                    _vendor["patrol_points"] = _pts
                    _vendor["patrol_idx"] = 0
                    _vendor["pos"] = Vector2(_pts[0])
                    _vendor["backup_pos"] = Vector2(_pts[0])
                    _facing = 1 if _pts[0].x < _new_shop.x else -1
                    _vendor["facing"] = _facing
                    _vendor["home_facing"] = _facing
                    _vendors_with_saved_shop.add(_saved_name)
                    break

    # ── Build POI registry (town only for now) ──
    _poi_registry: List[Dict[str, object]] = []
    # Vendors as POIs
    for _v in vendors:
        _vn = str(_v.get("name", "")).strip()
        _vr = str(_v.get("role", "")).strip()
        _vsp = _v.get("shop_pos")
        if isinstance(_vsp, Vector2) and _vn:
            _poi_registry.append({
                "key": f"vendor_{_vn}",
                "name": _vn,
                "desc": f"{_vr} — trades goods and wares" if _vr else "A local merchant",
                "pos": Vector2(_vsp),
                "level": "town",
            })

    saved_level_raw = str(character_data.get("last_level", "town")).strip().lower()
    current_level = saved_level_raw if saved_level_raw in ("town", "wilderness", "ice_biome") else "town"
    center_x = WORLD_WIDTH // 2
    # Plaza center Y for fire pit VFX (matches build_town_scene's plaza.centery + 40)
    _plaza_h = WORLD_HEIGHT - (HORIZON_Y + 320)
    plaza_center_y_approx = HORIZON_Y + 210 + _plaza_h // 2 + 40
    _tgs = (WORLD_HEIGHT - HORIZON_Y) / 1840.0   # town ground scale
    _town_gsx = WORLD_WIDTH / 3200.0
    town_square_fire_pit_pos = Vector2(center_x + int(-400 * _town_gsx), HORIZON_Y + int(480 * _tgs))
    town_square_well_pos = Vector2(center_x + int(400 * _town_gsx), HORIZON_Y + int(480 * _tgs))
    town_portal_pos     = Vector2(center_x - 440, HORIZON_Y + int(910 * _tgs))
    town_ice_portal_pos = Vector2(center_x + 440, HORIZON_Y + int(910 * _tgs))
    wilderness_portal_pos = Vector2(WILDERNESS_WIDTH // 2, HORIZON_Y + 920)
    ice_portal_pos        = Vector2(ICE_WIDTH // 2, HORIZON_Y + 920)
    town_gate_pos = Vector2(center_x, WORLD_HEIGHT - 460)
    gate_trigger_radius = 80.0
    gate_hovered = False
    # Landmark POIs (added after positional constants are known)
    _poi_registry.extend([
        {"key": "church", "name": "The Church of Dawn", "desc": "A towering sanctuary of stone and stained glass",
         "pos": Vector2(center_x, HORIZON_Y + 286), "level": "town"},
        {"key": "fire_pit", "name": "The Great Fire Pit", "desc": "Heart of the town — warmth and gathering place",
         "pos": Vector2(center_x, plaza_center_y_approx), "level": "town"},
        {"key": "gate_wilderness", "name": "The Wilderness Gate", "desc": "An ornate fortified passage to the wilds beyond",
         "pos": Vector2(town_gate_pos), "level": "town"},
        {"key": "portal_frost", "name": "Frostveil Portal", "desc": "Shimmering gateway to the frozen tundra",
         "pos": Vector2(town_ice_portal_pos), "level": "town"},
        {"key": "portal_wild", "name": "Wilderness Portal", "desc": "Arcane doorway leading to untamed lands",
         "pos": Vector2(town_portal_pos), "level": "town"},
        {"key": "well", "name": "The Town Well", "desc": "Ancient stone well at the crossroads",
         "pos": Vector2(center_x, HORIZON_Y + 518), "level": "town"},
        {"key": "fountain", "name": "The Stone Fountain", "desc": "Cool water splashes in a carved basin",
         "pos": Vector2(center_x + 360, HORIZON_Y + 520), "level": "town"},
        {"key": "gallows", "name": "The Gallows", "desc": "A grim reminder of the town's justice",
         "pos": Vector2(center_x - 1200, WORLD_HEIGHT - 1400), "level": "town"},
        {"key": "training_grounds", "name": "Militia Training Grounds", "desc": "Where the town guard hones its skill",
         "pos": Vector2(center_x + 850, HORIZON_Y + 3220), "level": "town"},
        {"key": "market_road", "name": "The Market Road", "desc": "Merchants hawk their wares from weathered carts",
         "pos": Vector2(center_x - 500, HORIZON_Y + 1600), "level": "town"},
    ])
    universal_delete_mode = False  # DEL key toggles; click to delete ANY object
    portal_trigger_radius = 66.0
    portal_hover_radius = 92.0
    portal_cooldown = 0.0
    portal_hovered = False
    portal_label = "Portal"
    portal_hint = "Click to travel"
    active_portal_pos = town_portal_pos
    teleport_menu_open = False
    teleport_menu_rects: Dict[str, pygame.Rect] = {}
    # Book portal VFX state
    book_portal_active = False
    book_portal_origin: Optional[Vector2] = None
    book_portal_dest_level: str = ""
    book_portal_timer: float = 0.0
    book_portal_total: float = 1.8        # seconds before teleport fires
    book_portal_arrival_timer: float = 0.0  # VFX at destination after arrival
    book_portal_arrival_pos: Optional[Vector2] = None
    book_portal_particle_cd: float = 0.0   # cooldown for particle bursts

    # ── POI Discovery System ──
    # Every 15-30s of player movement, show a nearby point of interest
    poi_move_timer: float = 0.0            # accumulates movement time
    poi_next_trigger: float = 18.0         # seconds until next POI reveal (randomised 15-30)
    poi_active: bool = False               # True while a POI banner is on-screen
    poi_display_timer: float = 0.0         # countdown for display duration
    poi_display_duration: float = 5.0      # how long the banner stays visible
    poi_name: str = ""                     # current POI label
    poi_desc: str = ""                     # short flavour text
    poi_world_pos: Optional[Vector2] = None  # world position of the POI
    poi_visited_set: set = set()           # POI keys already shown this session
    poi_fade_alpha: float = 0.0            # 0..255 for fade in/out

    audio.ensure_level_theme(current_level, force=True)
    weather_system = WeatherSystem(current_level, day_night.time)

    # Full-screen color grading (vignette intentionally removed)
    warm_grade_overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    warm_grade_overlay.fill((44, 26, 12, 255))
    cold_grade_overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    cold_grade_overlay.fill((16, 30, 56, 255))

    # Cached radial vignette — darkens the screen corners to focus the eye on
    # the player and hide the busy periphery (classic ARPG screenshot polish).
    # Built once on a small surface then smoothscaled up for a soft falloff.
    gameplay_vignette = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    _vg_small = pygame.Surface((128, 77), pygame.SRCALPHA)
    _vg_cx, _vg_cy = 64.0, 38.5
    _vg_maxd = math.hypot(_vg_cx, _vg_cy)
    for _vy in range(77):
        for _vx in range(128):
            _vd = math.hypot(_vx - _vg_cx, _vy - _vg_cy) / _vg_maxd  # 0 center .. 1 corner
            # Flat in the middle, ramps up past ~55% toward the corners.
            _vt = clamp((_vd - 0.55) / 0.45, 0.0, 1.0)
            _va = int(120 * (_vt ** 2.2))  # peak ~120 in the very corners
            if _va > 0:
                _vg_small.set_at((_vx, _vy), (8, 6, 14, _va))
    gameplay_vignette = pygame.transform.smoothscale(_vg_small, (SCREEN_WIDTH, SCREEN_HEIGHT))

    # Town light sources — positioned at key landmarks across the scattered town
    _tcx = WORLD_WIDTH // 2
    # Shop positions for light placement
    _tl_blacksmith = (_tcx + BLACKSMITH_SHOP_ANCHOR_OFFSET[0], HORIZON_Y + BLACKSMITH_SHOP_ANCHOR_OFFSET[1])
    _tl_baker = (_tcx + BAKER_SHOP_ANCHOR_OFFSET[0], HORIZON_Y + BAKER_SHOP_ANCHOR_OFFSET[1])
    _tl_tailor = (_tcx + TAILOR_SHOP_ANCHOR_OFFSET[0], HORIZON_Y + TAILOR_SHOP_ANCHOR_OFFSET[1])
    _tl_merchant = (_tcx + MERCHANT_SHOP_ANCHOR_OFFSET[0], HORIZON_Y + MERCHANT_SHOP_ANCHOR_OFFSET[1])
    _tl_sailor = (_tcx + SAILOR_SHOP_ANCHOR_OFFSET[0], HORIZON_Y + SAILOR_SHOP_ANCHOR_OFFSET[1])
    TOWN_LIGHTS: List[Tuple[int, int, Tuple[int, int, int], int, int, int]] = [
        # Fire pit & well (near center, between church and arena)
        (_tcx - 400, HORIZON_Y + 1200, (255, 180, 80), 10, 90, 110),
        (_tcx + 400, HORIZON_Y + 1200, (255, 160, 60),  8, 70,  90),
        # Arena center
        (_tcx, HORIZON_Y + 3300, (255, 140, 50), 12, 100, 100),
        # Blacksmith forge glow
        (_tl_blacksmith[0], _tl_blacksmith[1], (255, 160, 60), 8, 70, 90),
        # Baker ovens
        (_tl_baker[0], _tl_baker[1], (255, 180, 80), 6, 50, 70),
        # Tailor lamplight
        (_tl_tailor[0], _tl_tailor[1], (255, 200, 100), 5, 52, 75),
        # Merchant market
        (_tl_merchant[0], _tl_merchant[1], (255, 200, 100), 5, 52, 75),
        # Harbour
        (_tl_sailor[0], _tl_sailor[1], (255, 200, 100), 5, 52, 75),
    ]

    world_map_cache_by_level: Dict[str, Dict[str, object]] = {
        "town": build_world_map_cache(town_surface, WORLD_WIDTH, WORLD_HEIGHT),
        "wilderness": build_world_map_cache(wilderness_surface, WILDERNESS_WIDTH, WILDERNESS_HEIGHT),
        "ice_biome": build_world_map_cache(ice_surface, ICE_WIDTH, ICE_HEIGHT) if ice_surface is not None else {},
    }

    default_town_spawn = Vector2(WORLD_WIDTH / 2, HORIZON_Y + int(960 * _tgs))
    default_wilderness_spawn = Vector2(WILDERNESS_WIDTH / 2, HORIZON_Y + 980)
    default_ice_spawn = Vector2(ICE_WIDTH / 2, HORIZON_Y + 980)
    if current_level == "wilderness":
        player_pos = Vector2(default_wilderness_spawn)
    elif current_level == "ice_biome":
        player_pos = Vector2(default_ice_spawn)
    else:
        player_pos = Vector2(default_town_spawn)
    saved_pos_raw = character_data.get("last_pos")
    if isinstance(saved_pos_raw, dict):
        try:
            sx = float(saved_pos_raw.get("x", player_pos.x))
            sy = float(saved_pos_raw.get("y", player_pos.y))
            if current_level == "wilderness":
                player_pos = nearest_walkable(Vector2(sx, sy), wilderness_walk_bounds, wilderness_obstacles, PLAYER_COLLISION_RADIUS)
            elif current_level == "ice_biome":
                player_pos = nearest_walkable(Vector2(sx, sy), ice_walk_bounds, ice_obstacles, PLAYER_COLLISION_RADIUS)
            else:
                player_pos = nearest_walkable(Vector2(sx, sy), town_walk_bounds, town_obstacles, PLAYER_COLLISION_RADIUS)
        except (TypeError, ValueError):
            pass
    player_target = Vector2(player_pos)
    blacksmith_character_id = int(character_data.get("created_at", 0) or 0)
    _bs_name = next((str(v.get("name","")).strip() for v in vendors if str(v.get("role","")).strip().lower() == "blacksmith"), "")
    if current_level == "town" and _bs_name not in _vendors_with_saved_shop:
        bs_anchor = resolve_blacksmith_shop_anchor(player_pos, town_walk_bounds, town_obstacles)
        relocate_blacksmith_shop_to(vendors, bs_anchor, town_walk_bounds, town_obstacles)
    player_path: list[Vector2] = []
    if current_level == "town":
        player_pos = keep_player_out_of_blacksmith_shop(player_pos, vendors, town_walk_bounds, town_obstacles)
        player_target = Vector2(player_pos)
    speed = 235.0
    facing = 1
    moving = False
    player_anim_direction = "right"
    player_attack_anim_state = ""
    player_attack_anim_elapsed = 0.0
    player_hurt_anim_state = ""
    player_hurt_anim_elapsed = 0.0
    player_hit_flash_timer = 0.0
    player_hit_flash_duration = 0.28
    death_screen_active = False
    death_screen_timer = 0.0
    player_max_hp = float(active_stats.get("max_hp", 170.0))
    player_hp = player_max_hp
    player_max_mana = float(active_stats.get("max_mana", 170.0))
    player_mana = player_max_mana
    mana_regen = float(active_stats.get("mana_regen", 12.0))
    level_hp_bonus, level_mana_bonus, level_regen_bonus = level_progression_bonus(player_level)
    player_max_hp += bonus_max_hp + level_hp_bonus
    player_max_mana += level_mana_bonus
    mana_regen += bonus_mana_regen + level_regen_bonus
    player_hp = player_max_hp
    player_mana = player_max_mana

    def effective_mana_regen_value(ignore_lock: bool = False) -> float:
        if (not ignore_lock) and mana_regen_lock_timer > 0.0:
            return 0.0
        return max(0.0, mana_regen * passive_mana_regen_mult)

    basic_attack_cooldown = 0.0
    _cam_w = ICE_WIDTH if current_level == "ice_biome" else (WILDERNESS_WIDTH if current_level == "wilderness" else WORLD_WIDTH)
    _cam_h = ICE_HEIGHT if current_level == "ice_biome" else (WILDERNESS_HEIGHT if current_level == "wilderness" else WORLD_HEIGHT)
    camera = Vector2(
        clamp(player_pos.x - SCREEN_WIDTH * 0.5, 0, max(0, _cam_w - SCREEN_WIDTH)),
        clamp(player_pos.y - SCREEN_HEIGHT * 0.62, 0, max(0, _cam_h - SCREEN_HEIGHT)),
    )
    camera_director = CameraDirector(camera)
    ambient_overlay = AmbientOverlaySystem()

    pending_vendor_idx: Optional[int] = None
    active_vendor_idx: Optional[int] = None
    active_vendor_line = ""
    show_skill_tree = False
    show_world_map = False
    show_level_decor_editor = False
    extra_spell_hint = ""
    if CLASS_SPELL_SLOT_COUNTS.get(selected_class, 4) > 4:
        extra_spell_hint = ", T (Stone Pillar)"
    status_line = f"Class: {active_class['name']} | Passive: {passive_name} | Spells: Q/W/E/R (R is Ultimate){extra_spell_hint} | Potions: 1-4 | Character: P | Map: M | Move Blacksmith: F8 | Decorator: F9 | Basic attack: Right Click."
    status_timer = 5.2
    level_banner = "Frozen Tundra" if current_level == "ice_biome" else ("The Wilderness" if current_level == "wilderness" else "Raven Hollow")
    level_banner_timer = 2.8
    level_decor_render_cache: Dict[Tuple[str, int, int], pygame.Surface] = {}
    medieval_manager = level_decor_assets.get("medieval_manager")
    decor_selected_asset_id: Optional[str] = None
    decor_catalog_filter = "all"
    decor_asset_pack_mode = "medieval_generated" if isinstance(medieval_manager, AssetManager) and medieval_manager.entries else "project"
    decor_category_filter = "all"
    decor_search_text = ""
    decor_search_active = False
    decor_generate_seed = 123
    decor_placement_mode = "single"
    decor_grabbed: Optional[Dict[str, object]] = None
    decor_grab_vendor_idx: Optional[int] = None
    decor_grab_church: bool = False
    decor_editor_panel_side: str = "right"
    decor_collision_preview = False
    decor_selected_scale = 1.0
    decor_selected_rotation = 0.0
    decor_editor_scroll = 0
    decor_editor_dirty = False
    decor_editor_camera = Vector2(camera)

    def snap_camera_to_player() -> None:
        nonlocal camera, decor_editor_camera
        cam_w = ICE_WIDTH if current_level == "ice_biome" else (WILDERNESS_WIDTH if current_level == "wilderness" else WORLD_WIDTH)
        cam_h = ICE_HEIGHT if current_level == "ice_biome" else (WILDERNESS_HEIGHT if current_level == "wilderness" else WORLD_HEIGHT)
        cam_x = clamp(player_pos.x - SCREEN_WIDTH * 0.5, 0.0, max(0.0, float(cam_w - SCREEN_WIDTH)))
        cam_y = clamp(player_pos.y - SCREEN_HEIGHT * 0.62, 0.0, max(0.0, float(cam_h - SCREEN_HEIGHT)))
        snapped = Vector2(cam_x, cam_y)
        camera_director.jump_to(snapped)
        camera = Vector2(snapped)
        decor_editor_camera = Vector2(snapped)

    drag_npc_idx: Optional[int] = None
    clear_decor_confirm = False
    ai_asset_prompt: str = ""
    ai_asset_input_active: bool = False
    ai_asset_generating: bool = False
    ai_asset_scope: str = "shared"
    decor_editor_ui: Dict[str, object] = {
        "panel_rect": pygame.Rect(0, 0, 0, 0),
        "save_rect": pygame.Rect(0, 0, 0, 0),
        "reload_rect": pygame.Rect(0, 0, 0, 0),
        "generate_rect": pygame.Rect(0, 0, 0, 0),
        "demo_rect": pygame.Rect(0, 0, 0, 0),
        "seed_minus_rect": pygame.Rect(0, 0, 0, 0),
        "seed_plus_rect": pygame.Rect(0, 0, 0, 0),
        "pack_rects": {},
        "filter_rects": {},
        "category_rects": {},
        "mode_rects": {},
        "collision_rect": pygame.Rect(0, 0, 0, 0),
        "inspector_rects": {},
        "asset_rects": {},
        "search_rect": pygame.Rect(0, 0, 0, 0),
        "clear_search_rect": pygame.Rect(0, 0, 0, 0),
        "content_height": 0,
    }

    def pick_vendor(world_pos: Vector2) -> Optional[int]:
        draw_order = sorted(range(len(vendors)), key=lambda i: float(vendors[i]["pos"].y), reverse=True)
        for i in draw_order:
            v = vendors[i]
            sprite = v["sprite"]
            sprite_left = v["sprite_left"]
            if not isinstance(sprite, pygame.Surface) or not isinstance(sprite_left, pygame.Surface):
                continue
            rect = actor_world_rect(v["pos"], int(v["facing"]), sprite, sprite_left).inflate(18, 10)
            if rect.collidepoint(world_pos.x, world_pos.y):
                return i
        return None

    def pick_wolf(world_pos: Vector2) -> Optional[int]:
        enemy_list = active_enemies()
        draw_order = sorted(range(len(enemy_list)), key=lambda i: float(enemy_list[i]["pos"].y), reverse=True)
        for i in draw_order:
            wolf = enemy_list[i]
            if float(wolf.get("hp", 0.0)) <= 0.0:
                continue
            sprite = wolf.get("sprite")
            sprite_left = wolf.get("sprite_left")
            if not isinstance(sprite, pygame.Surface) or not isinstance(sprite_left, pygame.Surface):
                continue
            rect = actor_world_rect(
                wolf["pos"],
                int(wolf.get("facing", 1)),
                sprite,
                sprite_left,
            ).inflate(14, 10)
            if rect.collidepoint(world_pos.x, world_pos.y):
                return i
        return None

    def selected_wolf_entity() -> Optional[Dict[str, object]]:
        nonlocal selected_wolf_id
        if current_level not in ("wilderness", "ice_biome"):
            return None
        if selected_wolf_id is None:
            return None
        for wolf in active_enemies():
            if id(wolf) != selected_wolf_id:
                continue
            if float(wolf.get("hp", 0.0)) > 0.0:
                return wolf
            break
        selected_wolf_id = None
        return None

    def acquire_ranged_wolf_target(preferred_target: Optional[Vector2] = None, max_player_dist: float = 760.0) -> Tuple[Optional[int], Optional[Vector2]]:
        sel_wolf = selected_wolf_entity()
        if isinstance(sel_wolf, dict):
            wpos = sel_wolf.get("pos")
            if isinstance(wpos, Vector2):
                return id(sel_wolf), Vector2(wpos.x, wpos.y - 10.0)

        if current_level not in ("wilderness", "ice_biome"):
            return None, None

        anchor = Vector2(preferred_target) if isinstance(preferred_target, Vector2) else Vector2(player_pos)
        best_id: Optional[int] = None
        best_pos: Optional[Vector2] = None
        best_score = 1e12
        for wolf in active_enemies():
            if float(wolf.get("hp", 0.0)) <= 0.0:
                continue
            wpos = wolf.get("pos")
            if not isinstance(wpos, Vector2):
                continue
            if player_pos.distance_to(wpos) > max_player_dist:
                continue
            score = wpos.distance_to(anchor) + player_pos.distance_to(wpos) * 0.15
            if score >= best_score:
                continue
            best_score = score
            best_id = id(wolf)
            best_pos = Vector2(wpos.x, wpos.y - 10.0)
        return best_id, best_pos

    def selected_wolf_target(default_target: Vector2, allow_projectile_lock: bool = False) -> Vector2:
        # Auto-target selected/nearby wolves in wilderness or ice biome.
        if current_level not in ("wilderness", "ice_biome"):
            return default_target
        if not allow_projectile_lock and str(active_stats.get("basic_type", "melee")).lower() != "cast":
            return default_target
        _, target_pos = acquire_ranged_wolf_target(default_target)
        if isinstance(target_pos, Vector2):
            return target_pos
        return default_target

    def loot_pile_by_id(pile_id: int) -> Optional[Dict[str, object]]:
        for pile in loot_piles:
            try:
                pid = int(pile.get("id", -1))
            except (TypeError, ValueError):
                continue
            if pid != pile_id:
                continue
            if bool(pile.get("collected", False)):
                return None
            if float(pile.get("timer", 0.0)) <= 0.0:
                return None
            return pile
        return None

    def loot_entry_total(pile: dict[str, object]) -> int:
        count = 0
        if int(pile.get("gold", 0)) > 0:
            count += 1
        mats_raw = pile.get("materials")
        if isinstance(mats_raw, dict):
            for cnt in mats_raw.values():
                try:
                    if int(cnt) > 0:
                        count += 1
                except (TypeError, ValueError):
                    continue
        items_raw = pile.get("items")
        if isinstance(items_raw, list):
            count += len(items_raw)
        return count

    def close_loot_window(pile_id: int) -> None:
        open_loot_windows[:] = [w for w in open_loot_windows if int(w.get("pile_id", -1)) != pile_id]

    def focus_loot_window(pile_id: int) -> None:
        for idx, win in enumerate(open_loot_windows):
            if int(win.get("pile_id", -1)) == pile_id:
                open_loot_windows.append(open_loot_windows.pop(idx))
                return

    def prune_loot_windows() -> None:
        valid_ids: Set[int] = set()
        for pile in loot_piles:
            if bool(pile.get("collected", False)):
                continue
            if float(pile.get("timer", 0.0)) <= 0.0:
                continue
            try:
                valid_ids.add(int(pile.get("id", -1)))
            except (TypeError, ValueError):
                continue
        if not valid_ids:
            open_loot_windows.clear()
            return
        open_loot_windows[:] = [w for w in open_loot_windows if int(w.get("pile_id", -1)) in valid_ids]

    def open_loot_window(pile_id: int, anchor_screen: Optional[Tuple[int, int]] = None) -> bool:
        nonlocal player_target
        pile = loot_pile_by_id(pile_id)
        if not isinstance(pile, dict):
            return False
        pile_pos = pile.get("pos")
        if not isinstance(pile_pos, Vector2):
            return False
        if player_pos.distance_to(pile_pos) > 178.0:
            request_player_path(Vector2(pile_pos))
            set_status("Move closer to loot the corpse.", 1.2)
            return False

        for idx, win in enumerate(open_loot_windows):
            if int(win.get("pile_id", -1)) != pile_id:
                continue
            existing = open_loot_windows.pop(idx)
            open_loot_windows.append(existing)
            return True

        open_loot_windows.append({"pile_id": pile_id})
        audio.play_sfx("loot_open", cooldown_ms=80)
        return True

    def pick_loot_pile(world_pos: Vector2) -> Optional[int]:
        best: Optional[Tuple[float, int]] = None
        for pile in loot_piles:
            if bool(pile.get("collected", False)):
                continue
            if float(pile.get("timer", 0.0)) <= 0.0:
                continue
            pile_pos = pile.get("pos")
            if not isinstance(pile_pos, Vector2):
                continue
            dist = world_pos.distance_to(pile_pos)
            if dist > 30.0:
                continue
            try:
                pid = int(pile.get("id", -1))
            except (TypeError, ValueError):
                continue
            if best is None or pile_pos.y > best[0]:
                best = (pile_pos.y, pid)
        return best[1] if best is not None else None

    def find_raisable_corpse(preferred_target: Optional[Vector2], max_player_dist: float) -> Optional[Dict[str, object]]:
        if current_level != "wilderness":
            return None
        anchor = Vector2(preferred_target) if isinstance(preferred_target, Vector2) else Vector2(player_pos)
        best_pile: Optional[Dict[str, object]] = None
        best_score = 1e12
        for pile in loot_piles:
            if bool(pile.get("collected", False)):
                continue
            if float(pile.get("timer", 0.0)) <= 0.0:
                continue
            if bool(pile.get("raised", False)):
                continue
            if str(pile.get("corpse_kind", "")) != "predator":
                continue
            pile_pos = pile.get("pos")
            if not isinstance(pile_pos, Vector2):
                continue
            player_dist = player_pos.distance_to(pile_pos)
            if player_dist > max_player_dist:
                continue
            score = pile_pos.distance_to(anchor) + player_dist * 0.14
            if score >= best_score:
                continue
            best_score = score
            best_pile = pile
        return best_pile

    def take_loot_entry(pile_id: int, entry_kind: str, entry_key: str) -> bool:
        nonlocal player_gold
        pile = loot_pile_by_id(pile_id)
        if not isinstance(pile, dict):
            close_loot_window(pile_id)
            return False

        changed = False
        if entry_kind == "gold":
            gold_amt = int(pile.get("gold", 0))
            if gold_amt > 0:
                player_gold += gold_amt
                pile["gold"] = 0
                update_gold_accumulate_quests()
                set_status(f"Looted {gold_amt} gold.", 1.2)
                changed = True
        elif entry_kind == "material":
            mats_raw = pile.get("materials")
            if isinstance(mats_raw, dict):
                mat_id = str(entry_key)
                mat_cnt = int(mats_raw.get(mat_id, 0))
                if mat_cnt > 0:
                    mats_raw[mat_id] = 0
                    if mat_id in mats_raw:
                        mats_raw.pop(mat_id, None)
                    materials[mat_id] = materials.get(mat_id, 0) + mat_cnt
                    update_gather_quests()
                    mat_name = str(WOLF_MATERIALS.get(mat_id, {}).get("name", mat_id.replace("_", " ").title()))
                    set_status(f"Looted {mat_cnt}x {mat_name}.", 1.2)
                    changed = True
        elif entry_kind == "item":
            try:
                item_idx = int(entry_key)
            except ValueError:
                item_idx = -1
            items_raw = pile.get("items")
            if isinstance(items_raw, list) and 0 <= item_idx < len(items_raw):
                item_entry = items_raw[item_idx]
                if isinstance(item_entry, dict):
                    if add_item_to_inventory(item_entry, prefer_hotbar=False):
                        looted_name = str(item_entry.get("name", "item"))
                        items_raw.pop(item_idx)
                        set_status(f"Looted {looted_name}.", 1.2)
                        changed = True
                    else:
                        set_status("Inventory full. Move items or use consumables.", 1.4)
                        return False

        if changed and loot_entry_total(pile) <= 0:
            pile["collected"] = True
            close_loot_window(pile_id)
        if changed:
            audio.play_sfx("loot_pick", cooldown_ms=40)
        return changed

    def take_all_loot(pile_id: int) -> None:
        nonlocal player_gold
        pile = loot_pile_by_id(pile_id)
        if not isinstance(pile, dict):
            close_loot_window(pile_id)
            return

        gold_taken = int(pile.get("gold", 0))
        if gold_taken > 0:
            player_gold += gold_taken
            pile["gold"] = 0
            update_gold_accumulate_quests()

        mat_taken = 0
        mats_raw = pile.get("materials")
        if isinstance(mats_raw, dict):
            for mat_id in list(mats_raw.keys()):
                mat_cnt = int(mats_raw.get(mat_id, 0))
                if mat_cnt <= 0:
                    mats_raw.pop(mat_id, None)
                    continue
                mats_raw.pop(mat_id, None)
                materials[str(mat_id)] = materials.get(str(mat_id), 0) + mat_cnt
                mat_taken += mat_cnt
        if mat_taken > 0:
            update_gather_quests()

        items_taken = 0
        items_left = 0
        items_raw = pile.get("items")
        if isinstance(items_raw, list) and items_raw:
            kept: List[Dict[str, object]] = []
            for entry in items_raw:
                if not isinstance(entry, dict):
                    continue
                if add_item_to_inventory(entry, prefer_hotbar=False):
                    items_taken += 1
                else:
                    kept.append(entry)
            pile["items"] = kept
            items_left = len(kept)

        if loot_entry_total(pile) <= 0:
            pile["collected"] = True
            close_loot_window(pile_id)

        if gold_taken <= 0 and mat_taken <= 0 and items_taken <= 0:
            set_status("Nothing to loot.", 0.9)
            return
        audio.play_sfx("loot_all", cooldown_ms=90)
        msg = f"Looted: {gold_taken}g"
        if mat_taken > 0:
            msg += f", {mat_taken} mats"
        if items_taken > 0:
            msg += f", {items_taken} item{'s' if items_taken != 1 else ''}"
        if items_left > 0:
            msg += f" ({items_left} left, inventory full)"
        set_status(msg, 1.8)

    def draw_loot_windows_ui() -> None:
        loot_window_rects.clear()
        loot_close_rects.clear()
        loot_take_all_rects.clear()
        loot_entry_rects.clear()
        if not open_loot_windows or current_level not in ("wilderness", "ice_biome"):
            return

        prune_loot_windows()
        mouse_pos = pygame.mouse.get_pos()
        ticks = pygame.time.get_ticks()
        hovered_item: Optional[Dict[str, object]] = None
        hovered_anchor: Optional[pygame.Rect] = None

        # Draw only the topmost window (last in stack)
        for win in open_loot_windows[-1:]:
            pile_id = int(win.get("pile_id", -1))
            pile = loot_pile_by_id(pile_id)
            if not isinstance(pile, dict):
                continue

            # ── Build entries ────────────────────────────────────────────────
            entries: List[Tuple[str, str, str, Tuple[int, int, int], Optional[Dict[str, object]]]] = []
            gold_amt = int(pile.get("gold", 0))
            if gold_amt > 0:
                entries.append(("gold", "gold", f"Gold  {gold_amt}", (224, 190, 96), None))
            mats_raw = pile.get("materials")
            if isinstance(mats_raw, dict):
                for mat_id, raw_cnt in mats_raw.items():
                    mat_cnt = int(raw_cnt)
                    if mat_cnt <= 0:
                        continue
                    mat_data = WOLF_MATERIALS.get(str(mat_id), {})
                    mat_name = str(mat_data.get("name", str(mat_id).replace("_", " ").title()))
                    mat_col_raw = mat_data.get("color", (158, 168, 178))
                    mat_col: Tuple[int,int,int] = (int(mat_col_raw[0]), int(mat_col_raw[1]), int(mat_col_raw[2])) if isinstance(mat_col_raw, tuple) and len(mat_col_raw) >= 3 else (158, 168, 178)
                    entries.append(("material", str(mat_id), f"{mat_name}  x{mat_cnt}", mat_col, None))
            items_raw = pile.get("items")
            if isinstance(items_raw, list):
                for idx, item_entry in enumerate(items_raw):
                    if not isinstance(item_entry, dict):
                        continue
                    entries.append(("item", str(idx), str(item_entry.get("name", "Unknown")), item_rarity_border(item_entry), item_entry))

            corpse_name = str(pile.get("source_name", "Wolf")) if pile.get("source_name") else "Wolf"
            corpse_level = max(1, int(pile.get("source_level", 1)))
            # ── Layout (compact, right-center) ───────────────────────────────
            panel_w   = 268
            row_h     = 26
            header_h  = 52
            footer_h  = 38
            panel_h   = header_h + max(1, len(entries)) * row_h + footer_h
            px        = SCREEN_WIDTH - panel_w - 22
            py        = (SCREEN_HEIGHT - panel_h) // 2
            panel     = pygame.Rect(px, py, panel_w, panel_h)
            loot_window_rects[pile_id] = panel

            # ── PARTICLES — golden motes drifting upward ─────────────────────
            # Collect accent colours from entries for particle tint variety
            accent_cols = [(224, 190, 96)]  # always gold
            for _, _, _, ec, ep in entries:
                if ep is not None:   # item rarity colours
                    accent_cols.append(ec)
            num_particles = 14
            for p in range(num_particles):
                seed   = p * 1337 + pile_id * 97
                bx     = panel.left + (seed % panel_w)
                phase  = (seed * 0.017) % (2 * math.pi)
                # vertical: float from bottom↑top of panel over ~3 s, looping
                cycle  = ((ticks * 0.0003 + p * 0.13) % 1.0)
                fy     = panel.bottom + 4 - cycle * (panel_h + 24)
                fx     = bx + math.sin(ticks * 0.0018 + phase) * 14
                alpha  = int(clamp(math.sin(cycle * math.pi) * 200, 0, 200))
                pcol   = accent_cols[p % len(accent_cols)]
                size   = 2 if (seed % 3 == 0) else 1
                ps     = pygame.Surface((size * 2 + 2, size * 2 + 2), pygame.SRCALPHA)
                pygame.draw.circle(ps, (*pcol, alpha), (size + 1, size + 1), size)
                screen.blit(ps, (int(fx) - size, int(fy) - size))

            # Also draw a few larger star-sparkles near the header
            for s in range(5):
                sx    = panel.left + 24 + s * ((panel_w - 48) // 4)
                sy    = panel.top  + 6 + int(math.sin(ticks * 0.0025 + s * 1.3) * 5)
                sal   = int(clamp(130 + 70 * math.sin(ticks * 0.004 + s), 60, 200))
                star_col = (*accent_cols[s % len(accent_cols)], sal)
                sp    = pygame.Surface((7, 7), pygame.SRCALPHA)
                cx, cy = 3, 3
                pygame.draw.line(sp, star_col, (cx, 0), (cx, 6), 1)
                pygame.draw.line(sp, star_col, (0, cy), (6, cy), 1)
                pygame.draw.line(sp, (*star_col[:3], sal // 2), (cx - 1, cy - 1), (cx + 1, cy + 1), 1)
                pygame.draw.line(sp, (*star_col[:3], sal // 2), (cx + 1, cy - 1), (cx - 1, cy + 1), 1)
                screen.blit(sp, (sx - 3, sy - 3))

            # ── BACKGROUND ───────────────────────────────────────────────────
            bg = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
            pygame.draw.rect(bg, (7, 6, 10, 228), bg.get_rect(), border_radius=14)
            # subtle top-gradient highlight
            gline = pygame.Surface((panel_w - 28, 2), pygame.SRCALPHA)
            gline.fill((255, 230, 160, 30))
            bg.blit(gline, (14, 2))
            screen.blit(bg, panel.topleft)

            # ── OUTER BORDER — double gold ring ──────────────────────────────
            pulse_a = int(160 + 60 * math.sin(ticks * 0.003))
            bord_outer = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
            pygame.draw.rect(bord_outer, (180, 148, 76, pulse_a), bord_outer.get_rect(), 2, border_radius=14)
            screen.blit(bord_outer, panel.topleft)
            bord_inner = pygame.Surface((panel_w - 6, panel_h - 6), pygame.SRCALPHA)
            pygame.draw.rect(bord_inner, (100, 80, 40, 120), bord_inner.get_rect(), 1, border_radius=11)
            screen.blit(bord_inner, (panel.left + 3, panel.top + 3))

            # ── CORNER ORNAMENTS ─────────────────────────────────────────────
            def _corner(ox: int, oy: int, fx: int, fy: int) -> None:
                gc = (200, 168, 88, 200)
                pygame.draw.line(screen, gc, (ox, oy), (ox + fx * 10, oy), 1)
                pygame.draw.line(screen, gc, (ox, oy), (ox, oy + fy * 10), 1)
                pygame.draw.circle(screen, gc, (ox, oy), 2)
                dim = (160, 130, 60, 130)
                pygame.draw.line(screen, dim, (ox + fx * 3, oy + fy * 2), (ox + fx * 8, oy + fy * 2), 1)
                pygame.draw.line(screen, dim, (ox + fx * 2, oy + fy * 3), (ox + fx * 2, oy + fy * 8), 1)
            _corner(panel.left  + 6, panel.top    + 6,  1,  1)
            _corner(panel.right - 6, panel.top    + 6, -1,  1)
            _corner(panel.left  + 6, panel.bottom - 6,  1, -1)
            _corner(panel.right - 6, panel.bottom - 6, -1, -1)

            # ── HEADER ───────────────────────────────────────────────────────
            # Skull icon centred + title
            skull_x = panel.left + 14
            skull_y = panel.top  + 10
            sc = (200, 168, 80)
            # simplified skull: circle head + two eye dots
            pygame.draw.circle(screen, sc, (skull_x + 5, skull_y + 5), 5, 1)
            pygame.draw.circle(screen, sc, (skull_x + 3, skull_y + 4), 1)
            pygame.draw.circle(screen, sc, (skull_x + 7, skull_y + 4), 1)
            pygame.draw.rect(screen, sc, pygame.Rect(skull_x + 2, skull_y + 8, 6, 3), 1)

            title_col_pulse = (
                min(255, 220 + int(20 * math.sin(ticks * 0.004))),
                min(255, 198 + int(16 * math.sin(ticks * 0.004 + 1))),
                min(255, 110 + int(20 * math.sin(ticks * 0.004 + 2))),
            )
            title_txt = dialog_name_font.render(f"{corpse_name}  Lv {corpse_level}", True, title_col_pulse)
            screen.blit(title_txt, (panel.left + 26, panel.top + 8))


            # Ornate divider with central diamond
            div_y = panel.top + header_h - 8
            div_col = (140, 110, 50, 180)
            div_surf = pygame.Surface((panel_w - 20, 3), pygame.SRCALPHA)
            div_surf.fill(div_col)
            screen.blit(div_surf, (panel.left + 10, div_y))
            mid_x = panel.centerx
            diam_pts = [(mid_x, div_y - 4), (mid_x + 5, div_y + 1), (mid_x, div_y + 6), (mid_x - 5, div_y + 1)]
            pygame.draw.polygon(screen, (200, 168, 80), diam_pts)
            pygame.draw.polygon(screen, (255, 224, 140), diam_pts, 1)

            # ── CLOSE BUTTON ─────────────────────────────────────────────────
            close_rect = pygame.Rect(panel.right - 20, panel.top + 8, 14, 14)
            loot_close_rects[pile_id] = close_rect
            close_hover = close_rect.collidepoint(mouse_pos)
            pygame.draw.rect(screen, (88, 44, 44) if close_hover else (50, 28, 28), close_rect, border_radius=4)
            pygame.draw.rect(screen, (200, 100, 100), close_rect, 1, border_radius=4)
            lx, ly = close_rect.left + 3, close_rect.top + 3
            pygame.draw.line(screen, (240, 180, 180), (lx, ly), (close_rect.right - 3, close_rect.bottom - 3), 1)
            pygame.draw.line(screen, (240, 180, 180), (close_rect.right - 3, ly), (lx, close_rect.bottom - 3), 1)

            # ── LOOT ROWS ────────────────────────────────────────────────────
            list_top = panel.top + header_h
            if entries:
                for idx, (kind, key, label, row_col, item_payload) in enumerate(entries):
                    row_rect = pygame.Rect(panel.left + 8, list_top + idx * row_h, panel_w - 16, row_h - 2)
                    loot_entry_rects[(pile_id, kind, key)] = row_rect
                    row_hover = row_rect.collidepoint(mouse_pos)

                    # Row bg
                    row_bg_col = (55, 50, 38) if row_hover else ((40, 36, 28) if idx % 2 == 0 else (32, 29, 22))
                    rb = pygame.Surface((row_rect.width, row_rect.height), pygame.SRCALPHA)
                    pygame.draw.rect(rb, (*row_bg_col, 220), rb.get_rect(), border_radius=5)
                    screen.blit(rb, row_rect.topleft)

                    # Left colour accent bar
                    acc = pygame.Surface((3, row_rect.height - 4), pygame.SRCALPHA)
                    acc.fill((*row_col, 200))
                    screen.blit(acc, (row_rect.left + 1, row_rect.top + 2))

                    # Hover shimmer
                    if row_hover:
                        sh = pygame.Surface((row_rect.width, row_rect.height), pygame.SRCALPHA)
                        shim_a = int(30 + 20 * math.sin(ticks * 0.006))
                        pygame.draw.rect(sh, (220, 196, 120, shim_a), sh.get_rect(), border_radius=5)
                        screen.blit(sh, row_rect.topleft)
                        pygame.draw.rect(screen, (*row_col, 180), row_rect, 1, border_radius=5)

                    icon = resolve_loot_entry_icon(kind, key, row_col, item_payload, 16)
                    text_x = row_rect.left + 8
                    if isinstance(icon, pygame.Surface):
                        screen.blit(icon, (row_rect.left + 6, row_rect.top + (row_rect.height - 16) // 2))
                        text_x = row_rect.left + 26

                    if kind == "item" and isinstance(item_payload, dict):
                        blocked = item_blocked_for_class(item_payload, selected_class)
                        draw_col = (230, 110, 110) if blocked else row_col
                        label_fit = ellipsize_text(tiny_font, label, row_rect.width - (text_x - row_rect.left) - 6)
                        txt = tiny_font.render(label_fit, True, draw_col)
                        screen.blit(txt, (text_x, row_rect.centery - txt.get_height() // 2))
                        if row_hover:
                            hovered_item = item_payload
                            hovered_anchor = row_rect
                    else:
                        label_fit = ellipsize_text(tiny_font, label, row_rect.width - (text_x - row_rect.left) - 6)
                        txt = tiny_font.render(label_fit, True, row_col)
                        screen.blit(txt, (text_x, row_rect.centery - txt.get_height() // 2))
            else:
                empty_s = tiny_font.render("No loot remains.", True, (110, 108, 100))
                screen.blit(empty_s, (panel.centerx - empty_s.get_width() // 2, list_top + 6))

            # ── TAKE ALL BUTTON ───────────────────────────────────────────────
            btn_w, btn_h = 110, 22
            take_all_rect = pygame.Rect(panel.centerx - btn_w // 2, panel.bottom - footer_h + 8, btn_w, btn_h)
            loot_take_all_rects[pile_id] = take_all_rect
            active_take = loot_entry_total(pile) > 0
            take_hover  = active_take and take_all_rect.collidepoint(mouse_pos)

            if active_take:
                btn_glow_a = int(80 + 40 * math.sin(ticks * 0.005))
                bg_pulse   = (60 + int(20 * math.sin(ticks * 0.005)), 50, 22)
                btn_bg_col = (80, 68, 30) if take_hover else bg_pulse
                btn_bord   = (220, 190, 90) if take_hover else (180, 148, 60)
                btn_txt_col= (255, 240, 180) if take_hover else (230, 210, 148)
                # Glow behind button
                glow_s = pygame.Surface((btn_w + 20, btn_h + 14), pygame.SRCALPHA)
                pygame.draw.ellipse(glow_s, (200, 168, 60, btn_glow_a), glow_s.get_rect())
                screen.blit(glow_s, (take_all_rect.left - 10, take_all_rect.top - 7))
            else:
                btn_bg_col  = (28, 26, 28)
                btn_bord    = (66, 66, 72)
                btn_txt_col = (110, 110, 120)

            pygame.draw.rect(screen, btn_bg_col, take_all_rect, border_radius=7)
            pygame.draw.rect(screen, btn_bord,   take_all_rect, 1, border_radius=7)
            # Inner highlight line
            hl = pygame.Surface((btn_w - 10, 1), pygame.SRCALPHA)
            hl.fill((255, 255, 200, 50 if active_take else 0))
            screen.blit(hl, (take_all_rect.left + 5, take_all_rect.top + 2))

            take_lbl = tiny_font.render("Take All", True, btn_txt_col)
            screen.blit(take_lbl, (take_all_rect.centerx - take_lbl.get_width() // 2,
                                   take_all_rect.centery - take_lbl.get_height() // 2))

        if hovered_item is not None and hovered_anchor is not None:
            draw_item_tooltip(screen, hovered_item, hovered_anchor, tiny_font, tiny_font)

    def active_bounds() -> pygame.Rect:
        if current_level == "ice_biome":
            return ice_walk_bounds
        return town_walk_bounds if current_level == "town" else wilderness_walk_bounds

    def active_obstacles() -> List[pygame.Rect]:
        if current_level == "ice_biome":
            base = ice_obstacles
        elif current_level == "town":
            base = town_obstacles
        else:
            base = wilderness_obstacles
        blockers = list(base)
        blockers.extend(active_level_decor_collision_obstacles())
        return blockers

    def active_enemies() -> List[Dict[str, object]]:
        if current_level == "wilderness":
            return wolves
        if current_level == "ice_biome":
            return ice_wolves
        return []

    def active_passives() -> List[Dict[str, object]]:
        if current_level == "ice_biome":
            return ice_passive_animals
        return passive_animals

    def dynamic_collision_obstacles(
        ignore_vendor_idx: int | None = None,
        ignore_wolf_id: int | None = None,
    ) -> List[pygame.Rect]:
        blockers: List[pygame.Rect] = []
        if current_level == "town":
            rv = int(VENDOR_COLLISION_RADIUS)
            for idx, vendor in enumerate(vendors):
                if ignore_vendor_idx is not None and idx == ignore_vendor_idx:
                    continue
                vpos = vendor.get("pos")
                if not isinstance(vpos, Vector2):
                    continue
                blockers.append(pygame.Rect(int(vpos.x - rv), int(vpos.y - rv + 3), rv * 2, rv * 2))
            for vendor in vendors:
                if str(vendor.get("role", "")).strip().lower() != "blacksmith":
                    continue
                shop_pos = vendor.get("shop_pos")
                if not isinstance(shop_pos, Vector2):
                    continue
                blockers.extend(blacksmith_shop_collision_rects(shop_pos))
        elif current_level in ("wilderness", "ice_biome"):
            rw = int(WOLF_COLLISION_RADIUS)
            for wolf in active_enemies():
                if float(wolf.get("hp", 0.0)) <= 0.0:
                    continue
                if ignore_wolf_id is not None and id(wolf) == ignore_wolf_id:
                    continue
                wpos = wolf.get("pos")
                if not isinstance(wpos, Vector2):
                    continue
                blockers.append(pygame.Rect(int(wpos.x - rw), int(wpos.y - rw + 2), rw * 2, rw * 2))
            for critter in active_passives():
                cpos = critter.get("pos")
                if not isinstance(cpos, Vector2):
                    continue
                rr = int(max(8.0, float(critter.get("radius", 11.0))))
                blockers.append(pygame.Rect(int(cpos.x - rr), int(cpos.y - rr + 1), rr * 2, rr * 2))
        blockers.extend(spell_collision_obstacles(spell_effects))
        return blockers

    def request_player_path(target_world: Vector2, ignore_vendor_idx: Optional[int] = None) -> None:
        nonlocal player_target, player_path
        bounds = active_bounds()
        static_obs = active_obstacles()
        dynamic_obs = dynamic_collision_obstacles(ignore_vendor_idx=ignore_vendor_idx)
        all_obstacles = static_obs + dynamic_obs
        goal = nearest_walkable(target_world, bounds, all_obstacles, PLAYER_COLLISION_RADIUS)
        path = find_path_astar(
            player_pos,
            goal,
            bounds,
            all_obstacles,
            cell_size=NAV_CELL_SIZE,
            actor_radius=PLAYER_COLLISION_RADIUS,
            max_expansions=5000
        )
        player_target = Vector2(goal)
        if len(path) > 1:
            player_path = [Vector2(p) for p in path[1:]]
        else:
            player_path = [Vector2(goal)]

    def set_status(text: str, duration: float = 2.2) -> None:
        nonlocal status_line, status_timer
        status_line = text
        status_timer = duration
        audio.play_status(text)

    def set_player_position(pos: Vector2) -> None:
        nonlocal player_pos, player_target, player_path
        player_pos = Vector2(pos)
        player_target = Vector2(pos)
        player_path = []

    combat_runtime = (
        CombatRuntime(
            move_with_collision=move_with_collision,
            player_collision_radius=PLAYER_COLLISION_RADIUS,
        )
        if CombatRuntime is not None
        else None
    )

    def set_blacksmith_shop_anchor_to_player() -> None:
        nonlocal player_pos, player_target
        if current_level != "town":
            return
        anchor = nearest_walkable(Vector2(player_pos), town_walk_bounds, town_obstacles, VENDOR_SHOP_COLLISION_RADIUS)
        save_blacksmith_shop_anchor(anchor, auto_place=False, character_id=blacksmith_character_id)
        relocate_blacksmith_shop_to(vendors, anchor, town_walk_bounds, town_obstacles)
        player_pos = keep_player_out_of_blacksmith_shop(player_pos, vendors, town_walk_bounds, town_obstacles)
        player_target = Vector2(player_pos)
        set_status("Blacksmith shop moved here.", 1.6)

    def active_level_decor_entries() -> List[Dict[str, object]]:
        entries = level_decor_layout.get(current_level)
        if isinstance(entries, list):
            return entries
        level_decor_layout[current_level] = []
        return level_decor_layout[current_level]

    def active_level_decor_collision_obstacles() -> List[pygame.Rect]:
        blockers: List[pygame.Rect] = []
        for entry in active_level_decor_entries():
            if not isinstance(entry, dict):
                continue
            collision_rect = get_level_decor_collision_rect(
                entry,
                level_decor_assets,
                level_decor_render_cache,
                None,
            )
            if not isinstance(collision_rect, pygame.Rect):
                continue
            if collision_rect.width <= 0 or collision_rect.height <= 0:
                continue
            blockers.append(collision_rect)
        return blockers

    def available_level_decor_assets() -> List[Dict[str, object]]:
        return level_decor_catalog(
            level_decor_assets,
            current_level,
            decor_catalog_filter,
            decor_asset_pack_mode,
            decor_category_filter,
            decor_search_text,
        )

    def level_decor_max_scroll() -> int:
        catalog = available_level_decor_assets()
        rows = (len(catalog) + 1) // 2
        content_height = max(0, rows * 104 - 10)
        visible_height = max(180, SCREEN_HEIGHT - 520) - 8
        return max(0, content_height - visible_height)

    def ensure_level_decor_selection() -> None:
        nonlocal decor_selected_asset_id, decor_editor_scroll
        catalog = available_level_decor_assets()
        valid_ids = {str(entry.get("id", "")) for entry in catalog}
        if not catalog:
            decor_selected_asset_id = None
        elif str(decor_selected_asset_id or "") not in valid_ids:
            decor_selected_asset_id = str(catalog[0].get("id", ""))
        decor_editor_scroll = max(0, min(decor_editor_scroll, level_decor_max_scroll()))

    def save_level_decor_state(show_feedback: bool = True) -> None:
        nonlocal decor_editor_dirty
        try:
            save_level_decor_layout(level_decor_layout)
            save_npc_positions(vendors)
            decor_editor_dirty = False
            if show_feedback:
                set_status("Level decor & NPC positions saved.", 1.0)
        except OSError:
            decor_editor_dirty = True
            if show_feedback:
                set_status("Could not save level decor.", 1.3)

    def reload_level_decor_asset_library() -> None:
        nonlocal level_decor_assets, medieval_manager, decor_asset_pack_mode
        level_decor_assets = load_level_decor_assets()
        medieval_manager = level_decor_assets.get("medieval_manager")
        if decor_asset_pack_mode == "medieval_generated" and not (isinstance(medieval_manager, AssetManager) and medieval_manager.entries):
            decor_asset_pack_mode = "project"
        assets["level_decor_assets"] = level_decor_assets
        level_decor_render_cache.clear()
        ensure_level_decor_selection()
        set_status("Decoration assets reloaded.", 1.1)

    def generate_ai_decor_asset() -> None:
        nonlocal ai_asset_generating, decor_selected_asset_id
        if ai_asset_generating or not ai_asset_prompt.strip():
            return
        ai_asset_generating = True
        set_status("Generating AI asset...", 5.0)
        try:
            try:
                import anthropic as _anthropic
            except ImportError:
                set_status("Run: pip install anthropic  to use AI generation.", 4.0)
                return
            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
            if not api_key:
                set_status("Set ANTHROPIC_API_KEY env var to use AI generation.", 4.0)
                return
            client = _anthropic.Anthropic(api_key=api_key)
            sys_p = (
                "You are an RPG pixel-art sprite code generator. "
                "Given a description, output ONLY raw Python code (no markdown, no comments) that draws a sprite. "
                "Rules:\n"
                "- Start with: surface = pygame.Surface((W, H), pygame.SRCALPHA)  choosing W/H 32-128px\n"
                "- Draw using pygame.draw.rect/circle/polygon/line, pygame.gfxdraw, or surface.fill\n"
                "- Use vibrant, appropriate colors for an RPG game sprite\n"
                "- Make it detailed and recognizable\n"
                "- Never call pygame.init(), pygame.display, or use external files/fonts\n"
                "- Output raw Python code only — no markdown fences, no explanations"
            )
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1024,
                system=sys_p,
                messages=[{"role": "user", "content": f"Generate a pygame sprite for: {ai_asset_prompt.strip()}"}],
            )
            code = response.content[0].text.strip()
            # Strip any accidental markdown fences
            if code.startswith("```"):
                code = "\n".join(code.splitlines()[1:])
            if code.endswith("```"):
                code = "\n".join(code.splitlines()[:-1])
            ns: Dict[str, object] = {"pygame": pygame, "math": math, "random": random}
            exec(compile(code, "<ai_asset>", "exec"), ns)  # nosec
            gen_surf = ns.get("surface")
            if not isinstance(gen_surf, pygame.Surface):
                set_status("AI returned invalid code — try rephrasing the prompt.", 3.0)
                return
            words = [w.lower() for w in ai_asset_prompt.split() if w.isalnum()][:4]
            safe = "_".join(words) or "asset"
            save_dir = os.path.join(LEVEL_DECOR_ROOT, ai_asset_scope)
            os.makedirs(save_dir, exist_ok=True)
            fname = f"ai_{safe}.png"
            fpath = os.path.join(save_dir, fname)
            ctr = 1
            while os.path.exists(fpath):
                fname = f"ai_{safe}_{ctr}.png"
                fpath = os.path.join(save_dir, fname)
                ctr += 1
            pygame.image.save(gen_surf, fpath)
            reload_level_decor_asset_library()
            decor_selected_asset_id = f"custom:{ai_asset_scope}:{fname.lower()}"
            set_status(f"AI asset created: {fname}", 2.5)
        except Exception as exc:
            set_status(f"AI generation failed: {str(exc)[:52]}", 3.0)
        finally:
            ai_asset_generating = False

    def set_level_decor_filter(filter_id: str) -> None:
        nonlocal decor_catalog_filter, decor_editor_scroll
        normalized = str(filter_id).strip().lower()
        if normalized not in ("all", "scene", "pack", "custom"):
            normalized = "all"
        decor_catalog_filter = normalized
        decor_editor_scroll = 0
        ensure_level_decor_selection()

    def set_level_decor_asset_pack(pack_id: str) -> None:
        nonlocal decor_asset_pack_mode, decor_category_filter, decor_catalog_filter, decor_editor_scroll
        normalized = str(pack_id).strip().lower()
        if normalized not in ("project", "medieval_generated"):
            normalized = "project"
        if normalized == "medieval_generated" and not (isinstance(medieval_manager, AssetManager) and medieval_manager.entries):
            normalized = "project"
        decor_asset_pack_mode = normalized
        decor_category_filter = "all"
        if decor_asset_pack_mode != "project":
            decor_catalog_filter = "all"
        decor_editor_scroll = 0
        ensure_level_decor_selection()

    def set_level_decor_category(category_id: str) -> None:
        nonlocal decor_category_filter, decor_editor_scroll
        decor_category_filter = str(category_id).strip().lower() or "all"
        decor_editor_scroll = 0
        ensure_level_decor_selection()

    def set_level_decor_search(text: str) -> None:
        nonlocal decor_search_text, decor_editor_scroll
        decor_search_text = str(text)[:48]
        decor_editor_scroll = 0
        ensure_level_decor_selection()

    def selected_level_decor_asset() -> Optional[Dict[str, object]]:
        if not decor_selected_asset_id:
            return None
        return level_decor_asset_lookup(level_decor_assets, decor_selected_asset_id)

    def save_medieval_demo_level_file(payload: Dict[str, List[Dict[str, object]]]) -> bool:
        os.makedirs(os.path.dirname(MEDIEVAL_DEMO_LEVEL_PATH), exist_ok=True)
        try:
            with open(MEDIEVAL_DEMO_LEVEL_PATH, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
            return True
        except OSError:
            return False

    def create_medieval_demo_level() -> bool:
        nonlocal decor_editor_dirty
        payload = build_medieval_demo_layout(level_decor_assets)
        if not payload.get("town") and not payload.get("wilderness"):
            set_status("Generate the medieval pack before building the demo level.", 1.6)
            return False
        level_decor_layout["town"] = list(payload.get("town", []))
        level_decor_layout["wilderness"] = list(payload.get("wilderness", []))
        level_decor_layout["ice_biome"] = build_frozen_tundra_layout()
        payload["ice_biome"] = level_decor_layout["ice_biome"]
        decor_editor_dirty = True
        save_level_decor_state(show_feedback=False)
        if not save_medieval_demo_level_file(payload):
            set_status("Demo level applied, but the separate demo file could not be saved.", 1.8)
            return True
        set_status("Demo level created — town, wilderness & Frozen Tundra.", 1.6)
        return True

    def generate_medieval_asset_pack() -> bool:
        nonlocal decor_asset_pack_mode
        if not callable(run_medieval_pack_generator):
            set_status("Medieval asset generator is unavailable.", 1.4)
            return False
        try:
            run_medieval_pack_generator(int(decor_generate_seed), MEDIEVAL_PACK_ROOT)
        except Exception:
            set_status("Medieval asset generation failed.", 1.5)
            return False
        reload_level_decor_asset_library()
        set_level_decor_asset_pack("medieval_generated")
        set_status("Generated medieval asset pack and hot-reloaded it.", 1.6)
        return True

    def cycle_selected_decor_layer() -> bool:
        manager = medieval_manager if isinstance(medieval_manager, AssetManager) else None
        asset_entry = selected_level_decor_asset()
        if manager is None or not isinstance(asset_entry, dict) or str(asset_entry.get("asset_pack", "")).lower() != "medieval_generated":
            return False
        layer_order = ["GROUND", "DECOR", "OBJECT", "OVERLAY", "VFX"]
        current_layer = level_decor_asset_layer(asset_entry)
        next_layer = layer_order[(layer_order.index(current_layer) + 1) % len(layer_order)] if current_layer in layer_order else layer_order[0]
        if not manager.save_override(str(asset_entry.get("id", "")), {"layer": next_layer}):
            return False
        reload_level_decor_asset_library()
        return True

    def toggle_selected_decor_origin() -> bool:
        manager = medieval_manager if isinstance(medieval_manager, AssetManager) else None
        asset_entry = selected_level_decor_asset()
        if manager is None or not isinstance(asset_entry, dict) or str(asset_entry.get("asset_pack", "")).lower() != "medieval_generated":
            return False
        current_origin = asset_entry.get("origin")
        current_mode = str((current_origin or {}).get("mode", "bottom_center")).strip().lower()
        next_origin = {"mode": "center", "x": 0.5, "y": 0.5} if current_mode == "bottom_center" else {"mode": "bottom_center", "x": 0.5, "y": 1.0}
        if not manager.save_override(str(asset_entry.get("id", "")), {"origin": next_origin}):
            return False
        reload_level_decor_asset_library()
        return True

    def toggle_selected_decor_collision() -> bool:
        manager = medieval_manager if isinstance(medieval_manager, AssetManager) else None
        asset_entry = selected_level_decor_asset()
        if manager is None or not isinstance(asset_entry, dict) or str(asset_entry.get("asset_pack", "")).lower() != "medieval_generated":
            return False
        source_surface = asset_entry.get("surface")
        current_collision = asset_entry.get("collision")
        if isinstance(current_collision, dict):
            override: Dict[str, object] = {"collision": None}
        elif isinstance(source_surface, pygame.Surface):
            width = max(8, source_surface.get_width())
            height = max(8, source_surface.get_height())
            override = {
                "collision": {
                    "x": int(round(width * 0.2)),
                    "y": int(round(height * 0.55)),
                    "w": int(round(width * 0.6)),
                    "h": int(round(height * 0.25)),
                }
            }
        else:
            return False
        if not manager.save_override(str(asset_entry.get("id", "")), override):
            return False
        reload_level_decor_asset_library()
        return True

    def toggle_level_decor_editor() -> None:
        nonlocal show_level_decor_editor, decor_editor_camera, decor_editor_scroll, decor_search_active, drag_npc_idx, clear_decor_confirm, decor_grab_vendor_idx
        show_level_decor_editor = not show_level_decor_editor
        if show_level_decor_editor:
            set_level_decor_filter(decor_catalog_filter)
            ensure_level_decor_selection()
            player_path.clear()
            player_target.x = player_pos.x
            player_target.y = player_pos.y
            decor_editor_scroll = 0
            decor_search_active = False
            clear_decor_confirm = False
            drag_npc_idx = None
            decor_grab_vendor_idx = None
            decor_editor_camera = Vector2(camera)
            audio.play_sfx("ui_open", cooldown_ms=70)
            set_status("Level decorator opened. Place decor, drag town NPCs, or clear the level.", 1.8)
        else:
            decor_search_active = False
            clear_decor_confirm = False
            if drag_npc_idx is not None:
                save_npc_positions(vendors)
                drag_npc_idx = None
            if decor_grab_vendor_idx is not None:
                save_npc_positions(vendors)
                decor_grab_vendor_idx = None
            if decor_editor_dirty:
                save_level_decor_state(show_feedback=False)
            audio.play_sfx("ui_close", cooldown_ms=70)
            set_status("Level decorator closed.", 0.9)

    def adjust_level_decor_scroll(delta: int) -> None:
        nonlocal decor_editor_scroll
        max_scroll = level_decor_max_scroll()
        decor_editor_scroll = max(0, min(max_scroll, decor_editor_scroll + int(delta)))

    def adjust_level_decor_scale(delta: float) -> None:
        nonlocal decor_selected_scale
        if not decor_selected_asset_id:
            return
        decor_selected_scale = max(0.25, min(4.0, decor_selected_scale + float(delta)))

    def level_decor_grid_key(entry: Dict[str, object]) -> Optional[Tuple[int, int]]:
        if not isinstance(entry, dict):
            return None
        try:
            x = int(round(float(entry.get("x", 0.0))))
            y = int(round(float(entry.get("y", 0.0))))
        except (TypeError, ValueError):
            return None
        return (x, y)

    def find_level_decor_index_at(anchor: Vector2, tile_only: bool = False) -> Optional[int]:
        entries = active_level_decor_entries()
        target = (int(round(anchor.x)), int(round(anchor.y)))
        for index in range(len(entries) - 1, -1, -1):
            entry = entries[index]
            if not isinstance(entry, dict):
                continue
            grid_key = level_decor_grid_key(entry)
            if grid_key != target:
                continue
            if tile_only:
                existing_asset = level_decor_asset_lookup(level_decor_assets, str(entry.get("asset_id", "")))
                if not level_decor_asset_uses_tile_brush(existing_asset):
                    continue
            return index
        return None

    def refresh_road_autotiles(anchor: Vector2) -> None:
        entries = active_level_decor_entries()
        road_positions: Dict[Tuple[int, int], int] = {}
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                continue
            asset_entry = level_decor_asset_lookup(level_decor_assets, str(entry.get("asset_id", "")))
            if not isinstance(asset_entry, dict):
                continue
            if str(asset_entry.get("autotile_group", "")).strip().lower() != "dirt_road":
                continue
            grid_key = level_decor_grid_key(entry)
            if grid_key is not None:
                road_positions[grid_key] = index
        if not road_positions:
            return
        center = (int(round(anchor.x)), int(round(anchor.y)))
        targets = {
            center,
            (center[0], center[1] - DECOR_EDITOR_GRID_SIZE),
            (center[0], center[1] + DECOR_EDITOR_GRID_SIZE),
            (center[0] - DECOR_EDITOR_GRID_SIZE, center[1]),
            (center[0] + DECOR_EDITOR_GRID_SIZE, center[1]),
        }
        for grid_pos in targets:
            road_index = road_positions.get(grid_pos)
            if road_index is None or not (0 <= road_index < len(entries)):
                continue
            neighbor_mask: Set[str] = set()
            if (grid_pos[0], grid_pos[1] - DECOR_EDITOR_GRID_SIZE) in road_positions:
                neighbor_mask.add("n")
            if (grid_pos[0], grid_pos[1] + DECOR_EDITOR_GRID_SIZE) in road_positions:
                neighbor_mask.add("s")
            if (grid_pos[0] - DECOR_EDITOR_GRID_SIZE, grid_pos[1]) in road_positions:
                neighbor_mask.add("w")
            if (grid_pos[0] + DECOR_EDITOR_GRID_SIZE, grid_pos[1]) in road_positions:
                neighbor_mask.add("e")
            next_id = road_autotile_id_for_mask(neighbor_mask)
            if level_decor_asset_lookup(level_decor_assets, next_id) is None:
                continue
            entries[road_index]["asset_id"] = next_id
            entries[road_index]["scale"] = 1.0
            entries[road_index]["rotation"] = 0.0

    def place_level_decor(world_pos: Vector2) -> bool:
        nonlocal decor_editor_dirty
        ensure_level_decor_selection()
        if not decor_selected_asset_id:
            set_status("No decoration asset selected.", 1.0)
            return False
        selected_asset = selected_level_decor_asset()
        if not isinstance(selected_asset, dict):
            set_status("Selected asset could not be resolved.", 1.0)
            return False
        world_w = WILDERNESS_WIDTH if current_level == "wilderness" else WORLD_WIDTH
        world_h = WILDERNESS_HEIGHT if current_level == "wilderness" else WORLD_HEIGHT
        clamped_world = Vector2(
            clamp(world_pos.x, 0.0, float(world_w)),
            clamp(world_pos.y, 0.0, float(world_h)),
        )
        entries = active_level_decor_entries()
        generated_asset = str(selected_asset.get("asset_pack", "")).lower() == "medieval_generated"
        use_tile_mode = decor_placement_mode == "tile" or level_decor_asset_uses_tile_brush(selected_asset)
        use_scatter_mode = decor_placement_mode == "scatter" and level_decor_asset_uses_scatter(selected_asset) and not use_tile_mode

        if use_tile_mode:
            snapped = snap_editor_point_to_grid(clamped_world)
            previous_index = find_level_decor_index_at(snapped, tile_only=True)
            replaced_road = False
            if previous_index is not None and 0 <= previous_index < len(entries):
                previous_asset = level_decor_asset_lookup(level_decor_assets, str(entries[previous_index].get("asset_id", "")))
                replaced_road = isinstance(previous_asset, dict) and str(previous_asset.get("autotile_group", "")).strip().lower() == "dirt_road"
            tile_entry = {
                "asset_id": decor_selected_asset_id,
                "x": float(snapped.x),
                "y": float(snapped.y),
                "scale": 1.0,
                "rotation": 0.0,
            }
            if previous_index is None:
                entries.append(tile_entry)
            else:
                entries[previous_index] = tile_entry
            if replaced_road or str(selected_asset.get("autotile_group", "")).strip().lower() == "dirt_road":
                refresh_road_autotiles(snapped)
        elif use_scatter_mode:
            scatter_count = 6
            for _ in range(scatter_count):
                offset = Vector2(random.uniform(-64.0, 64.0), random.uniform(-44.0, 44.0))
                spawn = clamped_world + offset
                spawn.x = clamp(spawn.x, 0.0, float(world_w))
                spawn.y = clamp(spawn.y, 0.0, float(world_h))
                entries.append(
                    {
                        "asset_id": decor_selected_asset_id,
                        "x": round(float(spawn.x), 2),
                        "y": round(float(spawn.y), 2),
                        "scale": round(max(0.45, min(2.5, decor_selected_scale + random.uniform(-0.14, 0.16))), 2),
                        "rotation": round(random.uniform(-7.0, 7.0), 2),
                    }
                )
        else:
            if generated_asset:
                clamped_world = snap_editor_point_to_grid(clamped_world)
            entries.append(
                {
                    "asset_id": decor_selected_asset_id,
                    "x": round(float(clamped_world.x), 2),
                    "y": round(float(clamped_world.y), 2),
                    "scale": round(decor_selected_scale, 2),
                    "rotation": round(decor_selected_rotation % 360.0, 2),
                }
            )
        decor_editor_dirty = True
        save_level_decor_state(show_feedback=False)
        return True

    def remove_level_decor(world_pos: Vector2) -> bool:
        nonlocal decor_editor_dirty
        entries = active_level_decor_entries()
        best_index: Optional[int] = None
        best_distance = 120.0  # generous fallback radius for small props without a rect
        for index in range(len(entries) - 1, -1, -1):
            entry = entries[index]
            if not isinstance(entry, dict):
                continue
            rect = get_level_decor_instance_rect(entry, level_decor_assets, level_decor_render_cache, None)
            if isinstance(rect, pygame.Rect) and rect.inflate(24, 20).collidepoint(world_pos.x, world_pos.y):
                best_index = index
                break
            try:
                anchor = Vector2(float(entry.get("x", 0.0)), float(entry.get("y", 0.0)))
            except (TypeError, ValueError):
                continue
            dist = world_pos.distance_to(anchor)
            if dist <= best_distance:
                best_distance = dist
                best_index = index
        if best_index is None:
            return False
        removed_entry = entries[best_index]
        removed_asset = level_decor_asset_lookup(level_decor_assets, str(removed_entry.get("asset_id", ""))) if isinstance(removed_entry, dict) else None
        if isinstance(removed_asset, dict) and str(removed_asset.get("autotile_group", "")).strip().lower() in ("dirt_road", "frozen_road"):
            set_status("Paved road cannot be deleted.", 1.1)
            return False
        try:
            removed_anchor = Vector2(float(removed_entry.get("x", world_pos.x)), float(removed_entry.get("y", world_pos.y))) if isinstance(removed_entry, dict) else Vector2(world_pos)
        except (TypeError, ValueError):
            removed_anchor = Vector2(world_pos)
        entries.pop(best_index)
        decor_editor_dirty = True
        save_level_decor_state(show_feedback=False)
        return True

    def rebuild_town_surface() -> None:
        """Re-bake the town static surface with current prop deletions applied."""
        nonlocal town_surface, town_obstacles, town_canals, town_house_overlays, town_foliage_anim, farm_animals
        deletions = load_prop_deletions()
        new_surf, new_obs, new_canals, new_registry, new_hoverlays, new_foliage, _new_roads, _new_pens = build_town_scene(
            size=(WORLD_WIDTH, WORLD_HEIGHT), deleted_props=deletions
        )
        town_surface = new_surf
        town_obstacles = new_obs
        town_canals = new_canals
        town_house_overlays = new_hoverlays
        town_foliage_anim = new_foliage
        assets["town_surface"] = new_surf
        assets["town_obstacles"] = new_obs
        assets["town_canals"] = new_canals
        assets["town_prop_registry"] = new_registry
        assets["town_house_overlays"] = new_hoverlays
        assets["town_foliage_anim"] = new_foliage
        assets["town_road_rects"] = _new_roads
        assets["town_farm_pens"] = _new_pens
        assets["town_chimney_tops"] = list(_TOWN_CHIMNEY_TOPS)
        # Respawn farm animals for the surviving pens so deleting a pen also
        # removes its animals (and re-adding one brings them back).
        farm_animals = build_farm_animals(_new_pens)

    # Approximate hitboxes for hardcoded town props: (dx, dy, w, h)
    # dx/dy = offset from anchor to rect top-left. Anchor is bottom-center.
    _PROP_HITBOXES: Dict[str, Tuple[int, int, int, int]] = {
        "church":         (-200, -420, 400, 440),
        "wall_house":     (-220, -110, 440, 120),
        "house":          (-110, -260, 220, 270),
        "town_gate":      (-140, -180, 280, 200),
        "giant_fire_pit": (-70,  -100, 140, 110),
        "fire_pit":       (-40,   -65,  80,  75),
        "lamp":           (-18,  -120,  36, 130),
        "well":           (-55,   -80, 110,  90),
        "hd_cart":        (-80,   -70, 160,  85),
        "hd_hay":         (-55,   -60, 110,  80),
        "hd_barrel":      (-30,   -65,  60,  75),
        "scarecrow":      (-35,  -100,  70, 110),
        "wheelbarrow":    (-50,   -65, 100,  80),
        "tool_rack":      (-40,   -85,  80, 100),
        "milk_churn":     (-28,   -65,  56,  75),
        # Animal pens are anchored at their CENTER (not bottom-center) and are
        # rendered at 2× scale, so they need large centered hitboxes or the
        # delete cursor can't catch them.
        "pig_pen":        (-200, -150, 400, 300),
        "chicken_coop":   (-220, -170, 440, 340),
        "sheep_pen":      (-240, -180, 480, 360),
        "stone_path":     (-35,   -25,  70,  35),
        "farm_sign":      (-35,   -90,  70, 100),
        "dummy":          (-28,   -95,  56, 105),
        "grave":          (-35,   -85,  70,  95),
        "green_patch":    (-80,   -30, 160,  45),
        "grass_strip":    (-60,   -20, 120,  35),
        "garden_bed":     (-55,   -45, 110,  60),
        "boulevard_bush": (-45,   -50,  90,  65),
        # Phase-2 civic landmarks (anchor is base bottom-center)
        "town_hall":      (-300, -500, 600, 510),
        "windmill":       (-190, -450, 380, 470),
        "granary":        (-120, -220, 240, 240),
        "washhouse":      (-150, -200, 360, 215),
        "shrine":         (-35,  -120,  70, 135),
        "south_wall":     (-700, -110, 1400, 120),
        "palisade_w":     (-40,  -900,  80, 1800),
        "palisade_e":     (-40,  -900,  80, 1800),
    }
    _PROP_DEFAULT_HITBOX = (-60, -100, 120, 115)

    def remove_hardcoded_prop(world_pos: Vector2) -> bool:
        """Delete the hardcoded town prop under the cursor (anywhere inside its
        bounding box) and rebuild the scene. Works on large buildings too."""
        if current_level != "town":
            return False
        registry: list = assets.get("town_prop_registry", [])
        best_entry: Optional[dict] = None
        best_dist = 9999.0
        wx, wy = int(world_pos.x), int(world_pos.y)
        for entry in registry:
            try:
                ex = float(entry["x"])
                ey = float(entry["y"])
                kind = str(entry["kind"])
            except (KeyError, TypeError, ValueError):
                continue
            hb = _PROP_HITBOXES.get(kind, _PROP_DEFAULT_HITBOX)
            dx, dy, hw, hh = hb
            hit_rect = pygame.Rect(int(ex) + dx, int(ey) + dy, hw, hh)
            if hit_rect.collidepoint(wx, wy):
                dist = world_pos.distance_to(Vector2(ex, ey))
                if dist < best_dist:
                    best_dist = dist
                    best_entry = entry
        if best_entry is None:
            return False
        kind = str(best_entry["kind"])
        px = int(round(float(best_entry["x"])))
        py = int(round(float(best_entry["y"])))
        deletions = load_prop_deletions()
        deletions.add((kind, px, py))
        save_prop_deletions(deletions)
        rebuild_town_surface()
        set_status(f"Deleted: {kind}", 1.2)
        return True

    def grab_level_decor(world_pos: Vector2) -> bool:
        nonlocal decor_grabbed, decor_editor_dirty
        entries = active_level_decor_entries()
        # First pass: rect hit-test (works for any size asset including shops)
        for index in range(len(entries) - 1, -1, -1):
            entry = entries[index]
            if not isinstance(entry, dict):
                continue
            rect = get_level_decor_instance_rect(entry, level_decor_assets, level_decor_render_cache, None)
            if isinstance(rect, pygame.Rect) and rect.collidepoint(world_pos.x, world_pos.y):
                decor_grabbed = entries.pop(index)
                decor_editor_dirty = True
                save_level_decor_state(show_feedback=False)
                set_status("Grabbed — click to drop. ESC to cancel.", 3.0)
                return True
        # Second pass: nearest anchor within 200px (fallback for assets with no rect)
        best_index: Optional[int] = None
        best_distance = 200.0
        for index in range(len(entries) - 1, -1, -1):
            entry = entries[index]
            if not isinstance(entry, dict):
                continue
            try:
                anchor = Vector2(float(entry.get("x", 0.0)), float(entry.get("y", 0.0)))
            except (TypeError, ValueError):
                continue
            dist = world_pos.distance_to(anchor)
            if dist < best_distance:
                best_distance = dist
                best_index = index
        if best_index is None:
            return False
        decor_grabbed = entries.pop(best_index)
        decor_editor_dirty = True
        save_level_decor_state(show_feedback=False)
        set_status("Grabbed — click to drop. ESC to cancel.", 3.0)
        return True

    def drop_level_decor(world_pos: Vector2) -> None:
        nonlocal decor_grabbed, decor_editor_dirty
        if decor_grabbed is None:
            return
        decor_grabbed["x"] = round(world_pos.x, 2)
        decor_grabbed["y"] = round(world_pos.y, 2)
        active_level_decor_entries().append(decor_grabbed)
        decor_grabbed = None
        decor_editor_dirty = True
        save_level_decor_state(show_feedback=False)
        set_status("Placed.", 0.8)

    def cancel_grab() -> None:
        nonlocal decor_grabbed, decor_editor_dirty
        if decor_grabbed is None:
            return
        active_level_decor_entries().append(decor_grabbed)
        decor_grabbed = None
        decor_editor_dirty = True
        save_level_decor_state(show_feedback=False)
        set_status("Move cancelled.", 0.8)

    def grab_vendor_shop(world_pos: Vector2) -> bool:
        nonlocal decor_grab_vendor_idx, decor_selected_rotation
        if current_level != "town":
            return False
        best_idx: Optional[int] = None
        best_dist = 350.0
        for idx, vendor in enumerate(vendors):
            sp = vendor.get("shop_pos")
            if not isinstance(sp, Vector2):
                continue
            dist = world_pos.distance_to(sp)
            if dist < best_dist:
                best_dist = dist
                best_idx = idx
        if best_idx is None:
            return False
        decor_grab_vendor_idx = best_idx
        # Load the shop's existing rotation so R key continues from it
        try:
            decor_selected_rotation = float(vendors[best_idx].get("shop_rotation", 0.0)) % 360.0
        except (TypeError, ValueError):
            decor_selected_rotation = 0.0
        set_status("Shop grabbed — R to rotate, click to drop. ESC to cancel.", 3.0)
        return True

    def drop_vendor_shop(world_pos: Vector2) -> None:
        nonlocal decor_grab_vendor_idx
        if decor_grab_vendor_idx is None:
            return
        _v = vendors[decor_grab_vendor_idx]
        _new_sp = Vector2(world_pos)
        _v["shop_pos"] = _new_sp
        _v["shop_rotation"] = decor_selected_rotation % 360.0
        # Rebuild patrol and reposition vendor in front of the new shop location
        _pp = build_shop_patrol_points(_new_sp, town_walk_bounds, town_obstacles)
        _v["patrol_points"] = _pp
        _v["patrol_idx"] = 0
        _v["pos"] = Vector2(_pp[0])
        _v["backup_pos"] = Vector2(_pp[0])
        _f = 1 if _pp[0].x < _new_sp.x else -1
        _v["facing"] = _f
        _v["home_facing"] = _f
        save_npc_positions(vendors)
        decor_grab_vendor_idx = None
        set_status(f"Shop placed at {int(decor_selected_rotation % 360)}\u00b0.", 0.8)

    def cancel_vendor_shop_grab() -> None:
        nonlocal decor_grab_vendor_idx
        if decor_grab_vendor_idx is None:
            return
        decor_grab_vendor_idx = None
        set_status("Move cancelled.", 0.8)

    # ── Church grab/drop ──────────────────────────────────────────────────────
    _church_saved_pos = load_church_position()
    church_pos = Vector2(_church_saved_pos[0], _church_saved_pos[1]) if _church_saved_pos else Vector2(WORLD_WIDTH // 2, HORIZON_Y + 286)

    def grab_church(world_pos: Vector2) -> bool:
        nonlocal decor_grab_church
        if current_level != "town":
            return False
        if world_pos.distance_to(church_pos) > 300:
            return False
        decor_grab_church = True
        set_status("Church grabbed — click to drop. ESC to cancel.", 3.0)
        return True

    def drop_church(world_pos: Vector2) -> None:
        nonlocal decor_grab_church
        if not decor_grab_church:
            return
        church_pos.x = world_pos.x
        church_pos.y = world_pos.y
        save_church_position(church_pos.x, church_pos.y)
        decor_grab_church = False
        rebuild_town_surface()
        set_status("Church placed.", 0.8)

    def cancel_church_grab() -> None:
        nonlocal decor_grab_church
        if not decor_grab_church:
            return
        decor_grab_church = False
        set_status("Move cancelled.", 0.8)

    def clear_active_level_decor() -> bool:
        nonlocal decor_editor_dirty
        entries = active_level_decor_entries()
        if not entries:
            return False
        road_entries = [
            e for e in entries
            if isinstance(e, dict) and str(
                (level_decor_asset_lookup(level_decor_assets, str(e.get("asset_id", ""))) or {}).get("autotile_group", "")
            ).strip().lower() in ("dirt_road", "frozen_road")
        ]
        entries[:] = road_entries
        decor_editor_dirty = True
        save_level_decor_state(show_feedback=False)
        return True

    def vendor_screen_rect(index: int) -> Optional[pygame.Rect]:
        if current_level != "town" or not (0 <= index < len(vendors)):
            return None
        vendor = vendors[index]
        vpos = vendor.get("pos")
        sprite_right = vendor.get("sprite")
        sprite_left = vendor.get("sprite_left")
        if not isinstance(vpos, Vector2):
            return None
        if not isinstance(sprite_right, pygame.Surface) or not isinstance(sprite_left, pygame.Surface):
            return None
        screen_pos = vpos - camera
        sprite = get_facing_sprite(int(vendor.get("facing", 1)), sprite_right, sprite_left)
        return sprite.get_rect(midbottom=(int(screen_pos.x), int(screen_pos.y) + 1))

    def find_vendor_at_screen(screen_pos: Tuple[int, int]) -> Optional[int]:
        if current_level != "town":
            return None
        for index in range(len(vendors) - 1, -1, -1):
            vendor_rect = vendor_screen_rect(index)
            if isinstance(vendor_rect, pygame.Rect) and vendor_rect.inflate(18, 12).collidepoint(screen_pos):
                return index
        return None

    def move_vendor_to_world(index: int, world_pos: Vector2) -> bool:
        if current_level != "town" or not (0 <= index < len(vendors)):
            return False
        nav_obstacles = active_obstacles() + dynamic_collision_obstacles(ignore_vendor_idx=index)
        vendors[index]["pos"] = nearest_walkable(Vector2(world_pos), town_walk_bounds, nav_obstacles, VENDOR_COLLISION_RADIUS)
        return True

    def build_ultimate_context() -> UltimateContext:
        return UltimateContext(
            player_get=lambda: player_pos,
            player_set=set_player_position,
            facing_get=lambda: facing,
            wolves=active_enemies(),
            walk_bounds=active_bounds(),
            obstacles=active_obstacles(),
            status_effects=status_effects,
            screen_effects=screen_effects,
            damage_numbers=damage_numbers,
            spell_effects=spell_effects,
            set_status=set_status,
        )

    def clear_combat_effects() -> None:
        spell_effects.clear()
        summoned_skeletons.clear()
        active_ultimates.clear()
        if combat_runtime is not None:
            combat_runtime.clear()
        screen_effects.clear()
        status_effects.clear(wolves + ice_wolves)

    def backpack_insert_at(item: Dict[str, object], index: int) -> bool:
        if len(backpack_inventory) >= BACKPACK_SLOT_COUNT:
            return False
        insert_idx = max(0, min(index, len(backpack_inventory)))
        backpack_inventory.insert(insert_idx, item)
        return True

    def cancel_drag_item() -> None:
        nonlocal drag_item, drag_source_kind, drag_source_id
        if not isinstance(drag_item, dict):
            drag_item = None
            drag_source_kind = ""
            drag_source_id = None
            return
        _was_equip = drag_source_kind == "equip"
        if drag_source_kind == "equip" and isinstance(drag_source_id, str):
            equipped_items[drag_source_id] = drag_item
        elif drag_source_kind == "backpack" and isinstance(drag_source_id, int):
            backpack_insert_at(drag_item, drag_source_id)
        elif drag_source_kind == "hotbar" and isinstance(drag_source_id, int):
            if 0 <= drag_source_id < HOTBAR_SLOT_COUNT:
                item_inventory[drag_source_id] = drag_item
        else:
            if len(backpack_inventory) < BACKPACK_SLOT_COUNT:
                backpack_inventory.append(drag_item)
        drag_item = None
        drag_source_kind = ""
        drag_source_id = None
        if _was_equip:
            refresh_palette_swap()

    def begin_drag_from_backpack(index: int) -> bool:
        nonlocal drag_item, drag_source_kind, drag_source_id
        if not (0 <= index < len(backpack_inventory)):
            return False
        if drag_item is not None:
            return False
        drag_item = backpack_inventory.pop(index)
        drag_source_kind = "backpack"
        drag_source_id = index
        return True

    def begin_drag_from_equip(slot: str) -> bool:
        nonlocal drag_item, drag_source_kind, drag_source_id
        item = equipped_items.get(slot)
        if not isinstance(item, dict):
            return False
        if drag_item is not None:
            return False
        drag_item = equipped_items.pop(slot)
        drag_source_kind = "equip"
        drag_source_id = slot
        refresh_palette_swap()
        return True

    def begin_drag_from_potion_bar(index: int) -> bool:
        nonlocal drag_item, drag_source_kind, drag_source_id
        if not (0 <= index < HOTBAR_SLOT_COUNT):
            return False
        if drag_item is not None:
            return False
        if item_inventory[index] is None:
            return False
        drag_item = item_inventory[index]
        item_inventory[index] = None
        drag_source_kind = "hotbar"
        drag_source_id = index
        return True

    def finish_drag_drop(mouse_pos: tuple[int, int]) -> None:
        nonlocal drag_item, drag_source_kind, drag_source_id
        nonlocal delete_confirm_item, delete_confirm_source, delete_confirm_typed
        if not isinstance(drag_item, dict):
            return

        # Try equipment slots first.
        for slot, rect in character_slot_rects.items():
            if not rect.collidepoint(mouse_pos):
                continue
            can_equip, reason = can_item_equip_to_slot(drag_item, slot, selected_class)
            if not can_equip:
                set_status(reason, 1.2)
                cancel_drag_item()
                return

            swapped = equipped_items.get(slot)
            equipped_items[slot] = drag_item
            if isinstance(swapped, dict):
                if drag_source_kind == "equip" and isinstance(drag_source_id, str):
                    equipped_items[drag_source_id] = swapped
                elif drag_source_kind == "backpack" and isinstance(drag_source_id, int):
                    backpack_insert_at(swapped, drag_source_id)
                else:
                    backpack_insert_at(swapped, len(backpack_inventory))
            set_status(f"Equipped {drag_item.get('name', 'item')}.", 1.2)
            update_equip_slot_quests()
            refresh_palette_swap()
            drag_item = None
            drag_source_kind = ""
            drag_source_id = None
            return

        # Drop into backpack grid.
        for index, rect in backpack_slot_rects.items():
            if not rect.collidepoint(mouse_pos):
                continue
            _was_equip_drop = drag_source_kind == "equip"
            if index < len(backpack_inventory):
                swapped = backpack_inventory[index]
                backpack_inventory[index] = drag_item
                if drag_source_kind == "equip" and isinstance(drag_source_id, str):
                    equipped_items[drag_source_id] = swapped
                elif drag_source_kind == "backpack" and isinstance(drag_source_id, int):
                    backpack_insert_at(swapped, drag_source_id)
                else:
                    backpack_insert_at(swapped, len(backpack_inventory))
            else:
                backpack_insert_at(drag_item, index)
            if _was_equip_drop:
                refresh_palette_swap()
            drag_item = None
            drag_source_kind = ""
            drag_source_id = None
            return

        # Drop into potion bar — only potion consumables allowed.
        for index, rect in potion_slot_rects.items():
            if not rect.collidepoint(mouse_pos):
                continue
            if not item_can_go_in_potion_bar(drag_item):
                set_status("Only potions can go in the potion bar.", 1.2)
                cancel_drag_item()
                return
            swapped = item_inventory[index]  # may be None (empty slot)
            item_inventory[index] = drag_item
            if swapped is not None:
                if drag_source_kind == "backpack" and isinstance(drag_source_id, int):
                    backpack_insert_at(swapped, drag_source_id)
                elif drag_source_kind == "hotbar" and isinstance(drag_source_id, int):
                    if 0 <= drag_source_id < HOTBAR_SLOT_COUNT:
                        item_inventory[drag_source_id] = swapped
                else:
                    backpack_insert_at(swapped, len(backpack_inventory))
            drag_item = None
            drag_source_kind = ""
            drag_source_id = None
            return

        # Dropped outside all valid targets — offer to destroy the item.
        _pending_item   = drag_item
        _pending_source = drag_source_kind + (":" + str(drag_source_id) if drag_source_id is not None else "")
        cancel_drag_item()   # put item back first (dialog won't remove it until confirmed)
        delete_confirm_item   = _pending_item
        delete_confirm_source = _pending_source
        delete_confirm_typed  = ""

    def add_item_to_inventory(item: dict[str, object], prefer_hotbar: bool = False) -> bool:
        entry = clone_item_data(item)
        if item_is_food(entry):
            return False
        _bar_free = next((i for i, s in enumerate(item_inventory) if s is None), None)
        can_go_potion_bar = item_can_go_in_potion_bar(entry)
        if prefer_hotbar and can_go_potion_bar and _bar_free is not None:
            item_inventory[_bar_free] = entry
            return True
        if len(backpack_inventory) < BACKPACK_SLOT_COUNT:
            backpack_inventory.append(entry)
            return True
        if can_go_potion_bar and _bar_free is not None:
            item_inventory[_bar_free] = entry
            return True
        return False

    def roll_external_rarity(tier: int) -> str:
        tier = max(0, tier)
        weights = {
            "common": max(22.0, 78.0 - tier * 4.0),
            "rare": min(42.0, 18.0 + tier * 2.5),
            "epic": min(28.0, 4.0 + tier * 1.8),
            "legendary": min(12.0, 0.8 + tier * 0.9),
        }
        total = sum(weights.values())
        r = random.random() * total
        run = 0.0
        for rarity in ("common", "rare", "epic", "legendary"):
            run += weights[rarity]
            if r <= run:
                return rarity
        return "common"

    def roll_external_item(tier: int) -> Optional[Dict[str, object]]:
        rarity = roll_external_rarity(tier)
        pool = external_by_rarity.get(rarity, [])
        if not pool:
            all_items = external_item_library
            if not all_items:
                return None
            return clone_item_data(random.choice(all_items))
        return clone_item_data(random.choice(pool))

    def build_legendary_test_set_items() -> List[Dict[str, object]]:
        out: List[Dict[str, object]] = []
        slot_priority = ["head", "chest", "pants", "weapon", "offhand", "hands", "feet", "amulet", "ring", "belt"]
        for class_id, set_data in CLASS_ARMOR_SETS.items():
            pieces = set_data.get("pieces", [])
            if not isinstance(pieces, list) or not pieces:
                continue
            set_name = str(set_data.get("set_name", f"{class_id.title()} Legendary Set"))
            by_slot: Dict[str, Dict[str, object]] = {}
            for p in pieces:
                if isinstance(p, dict):
                    by_slot[str(p.get("slot", ""))] = p
            chosen: List[Dict[str, object]] = []
            for slot in slot_priority:
                piece = by_slot.get(slot)
                if isinstance(piece, dict):
                    chosen.append(piece)
                if len(chosen) >= 4:
                    break

            for piece in chosen:
                slot = str(piece.get("slot", "chest"))
                base_stats_raw = piece.get("stats", {})
                base_stats = base_stats_raw if isinstance(base_stats_raw, dict) else {}
                boosted: Dict[str, float] = {}
                for key, val in base_stats.items():
                    try:
                        fval = float(val)
                    except (TypeError, ValueError):
                        continue
                    boosted[str(key)] = round(fval * 2.4, 4 if str(key).endswith("reduction") or str(key).endswith("speed") else 2)
                # Give every legendary test item a small universal bump.
                boosted["max_hp"] = round(float(boosted.get("max_hp", 0.0)) + 12.0, 2)
                boosted["max_mana"] = round(float(boosted.get("max_mana", 0.0)) + 8.0, 2)
                boosted["spell_power"] = round(float(boosted.get("spell_power", 0.0)) + 4.0, 2)

                icon = piece.get("icon")
                icon_tuple = tuple(icon) if isinstance(icon, (tuple, list)) and len(icon) == 2 else None
                item_id = f"legend_set_{class_id}_{slot}"
                # Use piece-specific color if defined, otherwise rarity color
                _piece_color = piece.get("color")
                if not (isinstance(_piece_color, (tuple, list)) and len(_piece_color) >= 3):
                    _piece_color = ITEM_RARITY_COLORS["legendary"]
                out.append(
                    {
                        "id": item_id,
                        "name": f"{set_name} - {piece.get('name', slot.title())}",
                        "desc": f"Legendary test piece for {class_id.title()} ({slot.title()})",
                        "item_type": "equipment",
                        "equip_slot": slot,
                        "class_lock": class_id,
                        "set_name": set_name,
                        "rarity": "legendary",
                        "color": _piece_color,
                        "stats": boosted,
                        "icon": icon_tuple,
                    }
                )
        return out

    def seed_legendary_test_sets() -> None:
        existing = {str(it.get("id", "")) for it in item_inventory if it is not None}
        existing.update(str(it.get("id", "")) for it in backpack_inventory)
        added = 0
        for item in build_legendary_test_set_items():
            item_id = str(item.get("id", ""))
            if item_id in existing:
                continue
            if len(backpack_inventory) < BACKPACK_SLOT_COUNT:
                backpack_inventory.append(clone_item_data(item))
                existing.add(item_id)
                added += 1
            else:
                break
        if added > 0:
            set_status(f"Added {added} legendary set pieces to backpack for testing.", 2.6)

    def seed_town_portal_scroll() -> None:
        has_scroll = any(str(it.get("effect", "")) == "town_portal" for it in item_inventory if it is not None)
        has_scroll = has_scroll or any(str(it.get("effect", "")) == "town_portal" for it in backpack_inventory)
        if has_scroll:
            return
        scroll_item = {
            "id": "consumable_town_portal_scroll",
            "name": "Town Portal Scroll",
            "desc": "Open a portal and return to Raven Hollow from anywhere.",
            "effect": "town_portal",
            "rarity": "rare",
            "color": ITEM_RARITY_COLORS["rare"],
            "icon": (16, 1),
        }
        if len(backpack_inventory) < BACKPACK_SLOT_COUNT:
            backpack_inventory.insert(0, clone_item_data(scroll_item))
            set_status("Added Town Portal Scroll to backpack.", 1.8)

    def persist_progress() -> None:
        character_data.update({
            "class": selected_class,
            "player_name": player_name,
            "skill_points": skill_points,
            "unlocked_skills": list(unlocked_skills),
            "wolves_slain": wolves_slain,
            "player_level": player_level,
            "player_xp": player_xp,
            "gold": player_gold,
            "materials": materials,
            "item_inventory": [dict(it) if it is not None else {} for it in item_inventory],
            "backpack_inventory": [dict(it) for it in backpack_inventory],
            "equipped_items": {slot: dict(it) for slot, it in equipped_items.items()},
            "quest_states": dict(quest_states),
            "quest_progress": {k: list(v) for k, v in quest_progress.items()},
            "profession_state": {pid: dict(val) for pid, val in profession_state.items()},
            "selected_profession": selected_profession,
            "selected_recipe": crafting_selected,
            "bonus_max_hp": bonus_max_hp,
            "bonus_mana_regen": bonus_mana_regen,
            "iron_coat_count": iron_coat_count,
            "fang_amulet_count": fang_amulet_count,
            "last_level": current_level,
            "last_pos": {
                "x": round(float(player_pos.x), 2),
                "y": round(float(player_pos.y), 2),
            },
            "dialogue_flags": dialogue_flags,
        })
        save_npc_positions(vendors)
        save_callback()

    def use_town_portal_scroll() -> bool:
        nonlocal current_level, player_pos, player_target, player_path, active_vendor_idx, pending_vendor_idx
        nonlocal active_vendor_line, shop_open, npc_menu_mode, level_banner, level_banner_timer
        nonlocal portal_cooldown, selected_wolf_id, quest_actions_from_vendor
        if current_level == "town":
            set_status("You are already in Sangeroasa.", 1.2)
            return False
        current_level = "town"
        player_pos = nearest_walkable(Vector2(town_portal_pos.x, town_portal_pos.y + 130), town_walk_bounds, town_obstacles, PLAYER_COLLISION_RADIUS)
        player_target = Vector2(player_pos)
        player_path = []
        snap_camera_to_player()
        camera_director.impulse(4.0, 0.10)
        active_vendor_idx = None
        pending_vendor_idx = None
        active_vendor_line = ""
        shop_open = None
        npc_menu_mode = ""
        quest_actions_from_vendor = False
        quest_vendor_role = None
        clear_combat_effects()
        loot_piles.clear()
        open_loot_windows.clear()
        loot_window_rects.clear()
        loot_close_rects.clear()
        loot_take_all_rects.clear()
        loot_entry_rects.clear()
        level_banner = "Raven Hollow"
        level_banner_timer = 2.6
        portal_cooldown = 0.5
        selected_wolf_id = None
        set_status("Town Portal Scroll opened. You return to Raven Hollow.", 2.2)
        persist_progress()
        return True

    def teleport_to_destination(dest: str) -> bool:
        nonlocal current_level, player_pos, player_target, player_path, active_vendor_idx, pending_vendor_idx
        nonlocal active_vendor_line, shop_open, npc_menu_mode, level_banner, level_banner_timer
        nonlocal portal_cooldown, selected_wolf_id, quest_actions_from_vendor, teleport_menu_open
        nonlocal quest_vendor_role
        if dest == current_level:
            set_status("You are already here.", 1.2)
            teleport_menu_open = False
            return False
        if dest == "town":
            current_level = "town"
            player_pos = nearest_walkable(Vector2(town_portal_pos.x, town_portal_pos.y + 130), town_walk_bounds, town_obstacles, PLAYER_COLLISION_RADIUS)
            level_banner = "Sangeroasa"
            set_status("The Book glows — you are transported to Sangeroasa.", 2.2)
        elif dest == "wilderness":
            current_level = "wilderness"
            player_pos = nearest_walkable(Vector2(wilderness_portal_pos.x, wilderness_portal_pos.y + 130), wilderness_walk_bounds, wilderness_obstacles, PLAYER_COLLISION_RADIUS)
            level_banner = "The Wilderness"
            set_status("The Book glows — you are transported to The Wilderness.", 2.2)
            update_visit_level_quests("wilderness")
        elif dest == "ice_biome":
            current_level = "ice_biome"
            player_pos = nearest_walkable(Vector2(ice_portal_pos.x, ice_portal_pos.y + 130), ice_walk_bounds, ice_obstacles, PLAYER_COLLISION_RADIUS)
            level_banner = "Frozen Tundra"
            set_status("The Book glows — you are transported to the Frozen Tundra.", 2.2)
            update_visit_level_quests("ice_biome")
        else:
            teleport_menu_open = False
            return False
        player_target = Vector2(player_pos)
        player_path = []
        snap_camera_to_player()
        camera_director.impulse(4.0, 0.10)
        active_vendor_idx = None
        pending_vendor_idx = None
        active_vendor_line = ""
        shop_open = None
        npc_menu_mode = ""
        quest_actions_from_vendor = False
        quest_vendor_role = None
        clear_combat_effects()
        loot_piles.clear()
        open_loot_windows.clear()
        loot_window_rects.clear()
        loot_close_rects.clear()
        loot_take_all_rects.clear()
        loot_entry_rects.clear()
        level_banner_timer = 2.6
        portal_cooldown = 0.5
        selected_wolf_id = None
        teleport_menu_open = False
        audio.ensure_level_theme(current_level, force=True)
        persist_progress()
        return True

    def draw_teleport_menu(screen_surf: pygame.Surface) -> Dict[str, pygame.Rect]:
        nonlocal teleport_menu_open
        rects: Dict[str, pygame.Rect] = {}
        destinations = [
            ("town", "Sangeroasa", "Return to the safety of town.", (160, 130, 220)),
            ("wilderness", "The Wilderness", "Brave the wilds beyond the walls.", (120, 180, 100)),
            ("ice_biome", "Frozen Tundra", "Enter the frozen wastes.", (100, 180, 220)),
        ]
        panel_w, panel_h = 360, 320
        px = (SCREEN_WIDTH - panel_w) // 2
        py = (SCREEN_HEIGHT - panel_h) // 2
        panel = pygame.Rect(px, py, panel_w, panel_h)
        # backdrop
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 140))
        screen_surf.blit(overlay, (0, 0))
        # panel
        pygame.draw.rect(screen_surf, (18, 16, 28), panel, border_radius=12)
        pygame.draw.rect(screen_surf, (120, 100, 200), panel, 2, border_radius=12)
        # title
        title = ui_font.render("Book of Teleportation", True, (220, 200, 255))
        screen_surf.blit(title, (panel.centerx - title.get_width() // 2, panel.top + 14))
        # separator
        pygame.draw.line(screen_surf, (80, 70, 140), (panel.left + 20, panel.top + 44), (panel.right - 20, panel.top + 44), 1)
        # destination buttons
        btn_y = panel.top + 58
        mouse_pos = pygame.mouse.get_pos()
        for dest_key, dest_name, dest_desc, dest_col in destinations:
            btn = pygame.Rect(panel.left + 20, btn_y, panel_w - 40, 68)
            hovered = btn.collidepoint(mouse_pos)
            is_current = (dest_key == current_level)
            bg = (40, 36, 56) if not hovered else (60, 52, 86)
            if is_current:
                bg = (30, 28, 40)
            pygame.draw.rect(screen_surf, bg, btn, border_radius=8)
            border_col = dest_col if not is_current else (60, 56, 70)
            pygame.draw.rect(screen_surf, border_col, btn, 1, border_radius=8)
            # icon circle
            icon_col = dest_col if not is_current else (50, 48, 60)
            pygame.draw.circle(screen_surf, icon_col, (btn.left + 26, btn.centery), 14)
            pygame.draw.circle(screen_surf, (220, 210, 240) if not is_current else (80, 76, 90), (btn.left + 26, btn.centery), 14, 1)
            # rune inside circle
            rune = tiny_font.render(dest_name[0], True, (240, 230, 255) if not is_current else (90, 86, 100))
            screen_surf.blit(rune, (btn.left + 26 - rune.get_width() // 2, btn.centery - rune.get_height() // 2))
            # text
            name_col = (230, 220, 250) if not is_current else (100, 96, 110)
            name_surf = ui_font.render(dest_name, True, name_col)
            screen_surf.blit(name_surf, (btn.left + 50, btn.top + 10))
            desc_col = (160, 156, 180) if not is_current else (70, 68, 80)
            desc_surf = tiny_font.render(dest_desc if not is_current else "(You are here)", True, desc_col)
            screen_surf.blit(desc_surf, (btn.left + 50, btn.top + 34))
            if not is_current:
                rects[dest_key] = btn
            btn_y += 78
        # close button
        close_btn = pygame.Rect(panel.right - 36, panel.top + 8, 24, 24)
        pygame.draw.rect(screen_surf, (60, 50, 80), close_btn, border_radius=4)
        pygame.draw.line(screen_surf, (200, 190, 220), (close_btn.left + 6, close_btn.top + 6), (close_btn.right - 6, close_btn.bottom - 6), 2)
        pygame.draw.line(screen_surf, (200, 190, 220), (close_btn.right - 6, close_btn.top + 6), (close_btn.left + 6, close_btn.bottom - 6), 2)
        rects["close"] = close_btn
        return rects

    def unlocked_spell_indices() -> List[int]:
        out: List[int] = []
        for idx, spell in enumerate(active_spellbook):
            if str(spell.get("skill", "")) in unlocked_skills:
                out.append(idx)
        return out

    def ensure_selected_spell_unlocked() -> None:
        nonlocal selected_spell_idx
        unlocked_idx = unlocked_spell_indices()
        if not unlocked_idx:
            selected_spell_idx = 0
            return
        if selected_spell_idx not in unlocked_idx:
            selected_spell_idx = unlocked_idx[0]

    def try_cast_slot(slot_idx: int, target_world: Vector2) -> None:
        nonlocal selected_spell_idx, player_mana, player_pos, player_target, player_path, selected_wolf_id, facing
        nonlocal spell_global_cooldown, mana_regen_lock_timer
        nonlocal player_anim_direction
        if not (0 <= slot_idx < len(active_spellbook)):
            return
        selected_spell_idx = slot_idx
        spell = active_spellbook[slot_idx]
        spell_id = str(spell["id"])
        spell_name = str(spell["name"])
        skill_id = str(spell["skill"])
        if skill_id not in unlocked_skills:
            set_status(f"{spell_name} is locked. Open the skill tree (K).", 1.5)
            return

        cooldown = float(cooldowns.get(spell_id, 0.0))
        if cooldown > 0.0:
            set_status(f"{spell_name} cooldown: {cooldown:.1f}s", 1.0)
            return
        if spell_global_cooldown > 0.0:
            set_status(f"Global cooldown: {spell_global_cooldown:.1f}s", 0.65)
            return

        spell_mods = skill_spell_modifiers(unlocked_skills, active_skill_tree).get(spell_id, {})
        mana_cost = spell_mana_cost(spell, selected_class) * max(0.1, float(spell_mods.get("mana_mult", 1.0))) * passive_mana_cost_mult
        if player_mana < mana_cost:
            set_status(f"Not enough mana for {spell_name} ({int(mana_cost)} MP).", 1.2)
            return

        bonus_power = skill_damage_bonus(unlocked_skills, active_skill_tree)
        if damage_boost_timer > 0.0:
            bonus_power += 3.0  # Blacksmith Oil: roughly +20% power
        cooldown_scale = skill_cooldown_scale(unlocked_skills, active_skill_tree)
        if combat_runtime is not None and combat_runtime.handles_class(selected_class):
            runtime_context = (
                CombatSceneContext(
                    current_level=current_level,
                    enemies=active_enemies(),
                    passive_animals=active_passives() if current_level in ("wilderness", "ice_biome") else [],
                    walk_bounds=active_bounds(),
                    obstacles=active_obstacles(),
                    player_pos=Vector2(player_pos),
                    damage_numbers=damage_numbers,
                    camera_director=camera_director,
                    screen_effects=screen_effects,
                    audio=audio,
                )
                if CombatSceneContext is not None
                else None
            )
            if runtime_context is not None:
                runtime_result = combat_runtime.cast_spell(
                    class_id=selected_class,
                    spell=spell,
                    spell_mods=spell_mods,
                    player_pos=player_pos,
                    player_mana=player_mana,
                    target_world=target_world,
                    facing=facing,
                    bonus_power=bonus_power,
                    class_damage_mult=passive_damage_mult,
                    mana_cost=mana_cost,
                    cooldown_scale=cooldown_scale,
                    passive_spell_cooldown_mult=passive_spell_cooldown_mult,
                    spell_global_cooldown=spell_global_cooldown,
                    mana_regen_lock_timer=mana_regen_lock_timer,
                    context=runtime_context,
                )
                if runtime_result.handled:
                    if runtime_result.success:
                        player_mana = runtime_result.player_mana
                        if isinstance(runtime_result.player_pos, Vector2):
                            player_pos = Vector2(runtime_result.player_pos)
                        if isinstance(runtime_result.player_target, Vector2):
                            player_target = Vector2(runtime_result.player_target)
                        if runtime_result.clear_player_path:
                            player_path = []
                            selected_wolf_id = None
                        facing = runtime_result.facing
                        cooldowns[spell_id] = runtime_result.cooldown_remaining
                        spell_global_cooldown = runtime_result.spell_global_cooldown
                        mana_regen_lock_timer = runtime_result.mana_regen_lock_timer
                        player_anim_direction = cardinal_anim_direction(runtime_result.aim_direction, player_anim_direction)
                    if runtime_result.status_message:
                        set_status(runtime_result.status_message, runtime_result.status_duration)
                    return
        spell_kind = str(spell.get("kind", ""))
        allow_projectile_lock = spell_kind == "projectile"
        cast_target = selected_wolf_target(target_world, allow_projectile_lock=allow_projectile_lock)
        homing_target_id: Optional[int] = None
        if allow_projectile_lock:
            acquired_id, acquired_pos = acquire_ranged_wolf_target(target_world)
            if acquired_id is not None:
                homing_target_id = acquired_id
            if isinstance(acquired_pos, Vector2):
                cast_target = acquired_pos

        # Rogue Shadowstep: blink behind a target in range, then strike.
        if bool(spell.get("shadowstep", False)):
            if current_level not in ("wilderness", "ice_biome"):
                set_status("Shadowstep requires a hostile target in the wilderness.", 1.2)
                return
            step_range = max(120.0, float(spell.get("cast_range", 720.0)) + max(0.0, float(spell_mods.get("cast_range_bonus", 0.0))))
            target_id, _ = acquire_ranged_wolf_target(target_world, max_player_dist=step_range)
            if target_id is None:
                set_status("No target in Shadowstep range.", 1.0)
                return
            target_wolf: Optional[Dict[str, object]] = None
            for wolf in active_enemies():
                if id(wolf) == target_id and float(wolf.get("hp", 0.0)) > 0.0:
                    target_wolf = wolf
                    break
            if target_wolf is None:
                set_status("Shadowstep target lost.", 1.0)
                return
            wolf_pos_raw = target_wolf.get("pos")
            if not isinstance(wolf_pos_raw, Vector2):
                return
            wolf_pos = Vector2(wolf_pos_raw)
            approach = player_pos - wolf_pos
            if approach.length_squared() < 1e-4:
                approach = Vector2(-1.0 if facing >= 0 else 1.0, 0.0)
            desired = wolf_pos + approach.normalize() * 58.0
            nav_obstacles = active_obstacles() + dynamic_collision_obstacles(ignore_wolf_id=target_id)
            blink_pos = nearest_walkable(desired, active_bounds(), nav_obstacles, PLAYER_COLLISION_RADIUS)
            if blink_pos.distance_to(wolf_pos) > 132.0:
                found_alt = False
                for i in range(10):
                    ang = (math.tau * i) / 10.0
                    cand = wolf_pos + Vector2(math.cos(ang), math.sin(ang)) * 58.0
                    alt = nearest_walkable(cand, active_bounds(), nav_obstacles, PLAYER_COLLISION_RADIUS)
                    if alt.distance_to(wolf_pos) <= 132.0:
                        blink_pos = alt
                        found_alt = True
                        break
                if not found_alt:
                    set_status("Path blocked for Shadowstep.", 1.0)
                    return
            player_pos = Vector2(blink_pos)
            player_target = Vector2(blink_pos)
            player_path = []
            selected_wolf_id = target_id
            cast_target = Vector2(wolf_pos.x, wolf_pos.y - 8.0)
            facing = 1 if wolf_pos.x >= player_pos.x else -1
            sc, ac, _ = spell_vfx_palette(spell_id, spell.get("colors") if isinstance(spell.get("colors"), dict) else {})
            spawn_particle_burst(
                spell_effects,
                Vector2(player_pos.x, player_pos.y - 10.0),
                sc,
                ac,
                count=18,
                speed_min=110.0,
                speed_max=250.0,
                life_min=0.12,
                life_max=0.34,
                size_start=5.0,
                size_end=0.8,
                spread=math.tau,
                gravity=12.0,
                drag=1.2,
            )
            camera_director.impulse(4.4, 0.10)
        casted_special = False
        if spell_id == "necro_soul_well":
            corpse_range = max(
                120.0,
                (float(spell.get("cast_range", 320.0)) + max(0.0, float(spell_mods.get("cast_range_bonus", 0.0))))
                * max(1.0, float(spell_mods.get("radius_mult", 1.0))),
            )
            corpse_pile = find_raisable_corpse(target_world, corpse_range)
            if not isinstance(corpse_pile, dict):
                set_status("Raise Skeleton needs a fresh predator corpse.", 1.2)
                return
            corpse_pos_raw = corpse_pile.get("pos")
            if not isinstance(corpse_pos_raw, Vector2):
                set_status("That corpse cannot be raised.", 1.0)
                return
            corpse_pos = Vector2(corpse_pos_raw)
            corpse_level = max(1, int(corpse_pile.get("source_level", 1)))
            corpse_pile["raised"] = True
            corpse_pile["timer"] = max(float(corpse_pile.get("timer", 0.0)), 12.0)
            summon_duration = max(8.0, float(spell.get("duration", 16.0)) * max(0.1, float(spell_mods.get("duration_mult", 1.0))))
            summon_damage = (
                float(spell.get("damage", 16.0))
                + bonus_power * 2.4
                + float(spell_mods.get("bonus_damage", 0.0))
                + corpse_level * 0.6
            ) * max(0.1, float(spell_mods.get("damage_mult", 1.0))) * passive_damage_mult
            summon_speed = 150.0 * max(0.75, float(spell_mods.get("speed_mult", 1.0)))
            summon_radius_scale = max(1.0, float(spell_mods.get("radius_mult", 1.0)))
            if len(summoned_skeletons) >= 3:
                summoned_skeletons.pop(0)
            summoned_skeletons.append(
                {
                    "pos": Vector2(corpse_pos),
                    "home": Vector2(corpse_pos),
                    "facing": 1 if corpse_pos.x >= player_pos.x else -1,
                    "life": summon_duration,
                    "duration": summon_duration,
                    "attack_cd": 0.20,
                    "damage": summon_damage,
                    "attack_interval": max(0.34, 0.78 * max(0.2, float(spell_mods.get("interval_mult", 1.0)))),
                    "attack_range": 42.0 * summon_radius_scale,
                    "aggro_radius": 320.0 * summon_radius_scale,
                    "speed": summon_speed,
                    "radius": 14.0,
                    "level": corpse_level,
                    "target_id": None,
                    "ambient_timer": 0.0,
                    "swing": 0.0,
                    "orbit_phase": random.uniform(0.0, math.tau),
                }
            )
            spawn_particle_burst(
                spell_effects,
                Vector2(corpse_pos.x, corpse_pos.y - 10.0),
                (224, 214, 236),
                (126, 96, 172),
                count=22,
                speed_min=70.0,
                speed_max=180.0,
                life_min=0.16,
                life_max=0.40,
                size_start=4.2,
                size_end=0.6,
                spread=math.tau,
                gravity=-24.0,
                drag=1.2,
                vfx_scale=1.0,
            )
            spawn_particle_burst(
                spell_effects,
                Vector2(corpse_pos.x, corpse_pos.y - 4.0),
                (242, 236, 255),
                (172, 154, 214),
                count=10,
                speed_min=110.0,
                speed_max=240.0,
                life_min=0.10,
                life_max=0.22,
                size_start=3.0,
                size_end=0.4,
                spread=0.9,
                direction=Vector2(0.0, -1.0),
                drag=1.4,
                vfx_scale=0.9,
            )
            audio.play_sfx("cast_orb", cooldown_ms=40)
            audio.play_sfx("cast_ward", cooldown_ms=55)
            casted_special = True
        casted_ultimate = False
        if bool(spell.get("is_ultimate", False)):
            ultimate = create_ultimate_for_class(
                selected_class,
                spell,
                player_pos,
                cast_target,
                facing,
                bonus_power,
                spell_mods,
                class_damage_mult=passive_damage_mult,
            )
            if isinstance(ultimate, UltimateBase):
                active_ultimates.append(ultimate)
                ultimate.start(build_ultimate_context())
                casted_ultimate = True
                audio.play_sfx("cast_nova", cooldown_ms=30)
                audio.play_sfx("cast_ward", cooldown_ms=50)
                camera_director.impulse(6.2, 0.12)

        if not casted_special and not casted_ultimate:
            cast_spell(
                spell,
                player_pos,
                cast_target,
                facing,
                spell_effects,
                bonus_power,
                spell_mods,
                class_damage_mult=passive_damage_mult,
                homing_target_id=homing_target_id,
            )
            if spell_kind == "projectile":
                audio.play_sfx("cast_projectile", cooldown_ms=24)
            elif spell_kind == "nova":
                audio.play_sfx("cast_nova", cooldown_ms=40)
            elif spell_kind == "orb":
                audio.play_sfx("cast_orb", cooldown_ms=50)
            elif spell_kind == "ward":
                audio.play_sfx("cast_ward", cooldown_ms=60)
                if spell_id == "rogue_evasion_sigil":
                    audio.play_sfx("cast_nova", cooldown_ms=45)
            elif spell_kind == "melee_arc":
                audio.play_sfx("cast_melee", cooldown_ms=30)
            elif spell_kind == "cone":
                audio.play_sfx("cast_melee", cooldown_ms=30)
            elif spell_kind == "pillar":
                audio.play_sfx("cast_ward", cooldown_ms=55)
        player_anim_direction = cardinal_anim_direction(cast_target - player_pos, player_anim_direction)
        player_mana = max(0.0, player_mana - mana_cost)
        spell_cdr = max(0.70, float(spell_mods.get("cooldown_mult", 1.0)))
        slot_key = str(spell.get("slot", "1"))
        spell_floor = float(MIN_SPELL_COOLDOWN_BY_SLOT.get(slot_key, 0.85))
        cooldowns[spell_id] = max(
            spell_floor,
            float(spell["cooldown"]) * cooldown_scale * spell_cdr * passive_spell_cooldown_mult,
        )
        if bool(spell.get("is_ultimate", False)):
            spell_global_cooldown = max(spell_global_cooldown, GLOBAL_ULTIMATE_COOLDOWN)
            mana_regen_lock_timer = max(mana_regen_lock_timer, MANA_REGEN_LOCK_AFTER_ULTIMATE)
        else:
            spell_global_cooldown = max(spell_global_cooldown, GLOBAL_SPELL_COOLDOWN)
            mana_regen_lock_timer = max(mana_regen_lock_timer, MANA_REGEN_LOCK_AFTER_CAST)
        set_status(f"Casted {spell_name}.", 0.85)

    def try_basic_attack(target_world: Vector2) -> None:
        nonlocal basic_attack_cooldown, player_attack_anim_state, player_attack_anim_elapsed, player_anim_direction
        if basic_attack_cooldown > 0.0:
            return
        bonus_power = skill_damage_bonus(unlocked_skills, active_skill_tree)
        homing_target_id: Optional[int] = None
        basic_type = str(active_stats.get("basic_type", "melee")).lower()
        basic_target = Vector2(target_world)
        if basic_type != "melee":
            acquired_id, acquired_pos = acquire_ranged_wolf_target(target_world)
            homing_target_id = acquired_id
            if isinstance(acquired_pos, Vector2):
                basic_target = acquired_pos
        player_anim_direction = cardinal_anim_direction(basic_target - player_pos, player_anim_direction)
        cast_basic_attack(
            selected_class,
            player_pos,
            facing,
            basic_target,
            spell_effects,
            bonus_power,
            damage_mult=passive_damage_mult,
            homing_target_id=homing_target_id,
        )
        if basic_type == "melee":
            audio.play_sfx("cast_melee", cooldown_ms=40)
        else:
            audio.play_sfx("cast_projectile", cooldown_ms=30)
        if player_anim_frames:
            if moving:
                if speed_boost_timer > 0.0 and "run_attack" in player_anim_frames:
                    player_attack_anim_state = "run_attack"
                elif "walk_attack" in player_anim_frames:
                    player_attack_anim_state = "walk_attack"
                else:
                    player_attack_anim_state = "attack"
            else:
                player_attack_anim_state = "attack"
            if player_attack_anim_state not in player_anim_frames:
                player_attack_anim_state = ""
            player_attack_anim_elapsed = 0.0
        basic_attack_cooldown = float(active_stats.get("basic_cooldown", 0.30)) * passive_basic_cooldown_mult

    if not bool(character_data.get("intro_cinematic_seen", False)):
        cinematic_result = play_intro_cinematic(
            screen,
            clock,
            fonts,
            town_surface,
            wilderness_surface,
            player_name,
            selected_class,
            current_level,
            player_pos,
            audio=audio,
        )
        if cinematic_result == "QUIT":
            persist_progress()
            return "QUIT"
        character_data["intro_cinematic_seen"] = True
        save_callback()

    seed_legendary_test_sets()

    running = True
    while running:
        # Real elapsed time (seconds) so the game runs at the correct speed even
        # when the framerate dips below FPS. Clamped to avoid a huge catch-up
        # step after a hitch/pause (which would teleport everything).
        frame_ms = clock.tick_busy_loop(FPS)
        dt = min(max(frame_ms / 1000.0, 1.0 / 240.0), 1.0 / 20.0)
        if combat_runtime is not None:
            combat_runtime.begin_frame(dt)
        world_dt = 0.0 if (death_screen_active or show_skill_tree or show_character or show_crafting or show_quest_log or show_professions or show_world_map or show_level_decor_editor or npc_menu_mode != "") else dt
        if combat_runtime is not None:
            world_dt = combat_runtime.filter_world_dt(world_dt)
        if death_screen_active:
            death_screen_timer += dt
        day_night.update(world_dt)
        screen_effects.update(dt)
        level_up_vfx.update(dt)
        if weather_system.update(world_dt, current_level, day_night.time):
            set_status(f"Weather shifts to {weather_system.get_display_name().lower()}.", 1.7)
        ambient_dt = world_dt if world_dt > 0.0 else dt * 0.25
        ambient_overlay.update(
            ambient_dt,
            current_level,
            weather_system.cloud_cover,
            weather_system.precipitation,
            weather_system.fog_density,
            weather_system.wind,
        )
        audio.ensure_level_theme(current_level)
        _player_feared = False  # set True below when fear debuff active
        if show_level_decor_editor:
            editor_world_w = WILDERNESS_WIDTH if current_level == "wilderness" else WORLD_WIDTH
            editor_world_h = WILDERNESS_HEIGHT if current_level == "wilderness" else WORLD_HEIGHT
            decor_editor_camera.x = clamp(decor_editor_camera.x, 0.0, max(0.0, float(editor_world_w - SCREEN_WIDTH)))
            decor_editor_camera.y = clamp(decor_editor_camera.y, 0.0, max(0.0, float(editor_world_h - SCREEN_HEIGHT)))
            camera = Vector2(decor_editor_camera)

        for spell in active_spellbook:
            sid = str(spell["id"])
            cooldowns[sid] = max(0.0, float(cooldowns.get(sid, 0.0)) - world_dt)
        spell_global_cooldown = max(0.0, spell_global_cooldown - world_dt)
        mana_regen_lock_timer = max(0.0, mana_regen_lock_timer - world_dt)
        basic_attack_cooldown = max(0.0, basic_attack_cooldown - world_dt)
        damage_boost_timer = max(0.0, damage_boost_timer - world_dt)
        speed_boost_timer  = max(0.0, speed_boost_timer  - world_dt)
        # Fishing minigame timer
        if fishing_active:
            fishing_bar_pos += fishing_bar_vel * world_dt
            if fishing_bar_pos >= 1.0 or fishing_bar_pos <= 0.0:
                fishing_bar_vel = -fishing_bar_vel
                fishing_bar_pos = clamp(fishing_bar_pos, 0.0, 1.0)
            fishing_timer = max(0.0, fishing_timer - world_dt)
            if fishing_timer <= 0.0:
                fishing_active = False
                fishing_result = "fail"
                fishing_result_timer = 2.0
                set_status("The fish got away...", 1.8)
        if fishing_result_timer > 0.0:
            fishing_result_timer = max(0.0, fishing_result_timer - world_dt)
        if world_dt > 0.0:
            player_mana = min(player_max_mana, player_mana + effective_mana_regen_value() * world_dt)
            if passive_hp_regen > 0.0 and player_hp < player_max_hp:
                player_hp = min(player_max_hp, player_hp + passive_hp_regen * world_dt)
            # ── Bite DoT ticking on player ──
            _bite_fx_list = [e for e in status_effects.get_effects(StatusEffectSystem.PLAYER_KEY) if e.kind == "bite" and e.tick_interval > 0.0]
            for _bfx in _bite_fx_list:
                _bfx.tick_timer -= world_dt
                while _bfx.tick_timer <= 0.0 and _bfx.duration > 0.0:
                    _bite_dmg = _bfx.potency
                    player_hp = max(0.0, player_hp - _bite_dmg)
                    if _bite_dmg > 0.0:
                        player_hit_flash_timer = player_hit_flash_duration
                    spawn_damage_number(damage_numbers, Vector2(player_pos.x + random.uniform(-6, 6), player_pos.y - 20), _bite_dmg, kind="incoming")
                    _bfx.tick_timer += max(0.01, _bfx.tick_interval)
            # ── Fear check — compute once per frame ──
            _fear_fx = [e for e in status_effects.get_effects(StatusEffectSystem.PLAYER_KEY) if e.kind == "fear" and e.duration > 0.0]
            _player_feared = len(_fear_fx) > 0
            if current_level in ("wilderness", "ice_biome"):
                update_survive_time_quests(world_dt)
            player_anim_timer += world_dt
            if player_attack_anim_state:
                player_attack_anim_elapsed += world_dt
                if player_attack_anim_elapsed >= float(player_anim_durations.get(player_attack_anim_state, 0.24)):
                    player_attack_anim_state = ""
                    player_attack_anim_elapsed = 0.0
            if player_hurt_anim_state:
                player_hurt_anim_elapsed += world_dt
                if player_hurt_anim_elapsed >= float(player_anim_durations.get(player_hurt_anim_state, 0.18)):
                    player_hurt_anim_state = ""
                    player_hurt_anim_elapsed = 0.0
            if player_hit_flash_timer > 0.0:
                player_hit_flash_timer = max(0.0, player_hit_flash_timer - world_dt)
        status_timer = max(0.0, status_timer - dt)
        level_banner_timer = max(0.0, level_banner_timer - dt)
        portal_cooldown = max(0.0, portal_cooldown - dt)

        # Book portal animation countdown
        if book_portal_active and book_portal_timer > 0.0:
            book_portal_timer = max(0.0, book_portal_timer - dt)
            # Periodic particle bursts while portal is open
            book_portal_particle_cd -= dt
            if book_portal_particle_cd <= 0.0 and book_portal_origin is not None:
                book_portal_particle_cd = 0.25
                spawn_particle_burst(
                    spell_effects, book_portal_origin,
                    (255, 220, 80), (255, 180, 40),
                    6, 30, 80, 0.3, 0.7, 3.0, 0.5,
                    gravity=-50.0, drag=2.0,
                )
            if book_portal_timer <= 0.0:
                # Time's up — execute the teleport
                book_portal_active = False
                _bp_dest = book_portal_dest_level
                teleport_to_destination(_bp_dest)
                # Set up arrival portal VFX
                book_portal_arrival_timer = 2.5
                book_portal_arrival_pos = Vector2(player_pos)
                spawn_particle_burst(
                    spell_effects, player_pos,
                    (255, 200, 50), (255, 160, 30),
                    24, 50, 120, 0.5, 1.0, 5.0, 1.0,
                    gravity=-40.0, drag=1.5,
                )
        # Arrival portal fade-out timer
        if book_portal_arrival_timer > 0.0:
            book_portal_arrival_timer = max(0.0, book_portal_arrival_timer - dt)

        ensure_selected_spell_unlocked()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                persist_progress()
                return "QUIT"
            if death_screen_active:
                trigger_respawn = False
                if event.type == pygame.KEYDOWN and event.key in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_ESCAPE):
                    trigger_respawn = True
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and death_screen_timer >= 0.6:
                    trigger_respawn = True
                if trigger_respawn:
                    current_level = "town"
                    player_pos = nearest_walkable(Vector2(center_x, default_town_spawn.y), town_walk_bounds, town_obstacles, PLAYER_COLLISION_RADIUS)
                    player_target = Vector2(player_pos)
                    player_path = []
                    snap_camera_to_player()
                    camera_director.impulse(5.2, 0.14)
                    player_anim_direction = "down"
                    player_attack_anim_state = ""
                    player_attack_anim_elapsed = 0.0
                    player_hurt_anim_state = ""
                    player_hurt_anim_elapsed = 0.0
                    player_hit_flash_timer = 0.0
                    selected_wolf_id = None
                    active_vendor_idx = None
                    pending_vendor_idx = None
                    active_vendor_line = ""
                    quest_actions_from_vendor = False
                    quest_vendor_role = None
                    clear_combat_effects()
                    damage_numbers.clear()
                    loot_piles.clear()
                    open_loot_windows.clear()
                    loot_window_rects.clear()
                    loot_close_rects.clear()
                    loot_take_all_rects.clear()
                    loot_entry_rects.clear()
                    player_hp = player_max_hp
                    player_mana = max(player_mana, player_max_mana * 0.6)
                    level_banner = "Sangeroasa"
                    level_banner_timer = 2.4
                    set_status("You fell in the wilderness and woke up in Sangeroasa.", 2.2)
                    death_screen_active = False
                    death_screen_timer = 0.0
                continue
            if event.type == pygame.MOUSEMOTION:
                if show_level_decor_editor and drag_npc_idx is not None and current_level == "town":
                    panel_rect = decor_editor_ui.get("panel_rect")
                    if not (isinstance(panel_rect, pygame.Rect) and panel_rect.collidepoint(event.pos)):
                        world_mouse = Vector2(event.pos[0] + camera.x, event.pos[1] + camera.y)
                        move_vendor_to_world(drag_npc_idx, world_mouse)
                if show_level_decor_editor and decor_grab_vendor_idx is not None and current_level == "town":
                    world_mouse = Vector2(event.pos[0] + camera.x, event.pos[1] + camera.y)
                    vendors[decor_grab_vendor_idx]["shop_pos"] = Vector2(world_mouse)
                    vendors[decor_grab_vendor_idx]["shop_rotation"] = decor_selected_rotation % 360.0
                if show_level_decor_editor and decor_grab_church and current_level == "town":
                    world_mouse = Vector2(event.pos[0] + camera.x, event.pos[1] + camera.y)
                    church_pos.x = world_mouse.x
                    church_pos.y = world_mouse.y
                if show_skill_tree:
                    skill_hover = None
                    for node_id, rect in skill_node_rects.items():
                        if rect.collidepoint(event.pos):
                            skill_hover = node_id
                            break
            elif event.type == pygame.KEYDOWN:
                ctrl_down = bool(event.mod & pygame.KMOD_CTRL)

                # ── Delete-confirm dialog intercepts all key input ─────────────
                if delete_confirm_item is not None:
                    if event.key == pygame.K_ESCAPE:
                        delete_confirm_item   = None
                        delete_confirm_source = ""
                        delete_confirm_typed  = ""
                    elif event.key == pygame.K_BACKSPACE:
                        delete_confirm_typed = delete_confirm_typed[:-1]
                    elif event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
                        if delete_confirm_typed.upper() == "DELETE":
                            _src = delete_confirm_source
                            if _src.startswith("backpack:"):
                                _bi = int(_src.split(":")[1])
                                if 0 <= _bi < len(backpack_inventory) and backpack_inventory[_bi] is delete_confirm_item:
                                    backpack_inventory.pop(_bi)
                                    refresh_palette_swap()
                            elif _src.startswith("equip:"):
                                _eslot = _src.split(":")[1]
                                if equipped_items.get(_eslot) is delete_confirm_item:
                                    del equipped_items[_eslot]
                                    refresh_palette_swap()
                            set_status(f"Destroyed {str(delete_confirm_item.get('name','item'))}.", 1.5)
                            delete_confirm_item   = None
                            delete_confirm_source = ""
                            delete_confirm_typed  = ""
                    elif event.unicode and event.unicode.isprintable():
                        if len(delete_confirm_typed) < 10:
                            delete_confirm_typed += event.unicode
                    continue  # swallow all other keys while dialog is open

                # Perk selection intercepts all input when active
                if perk_choice_pending and perk_choices:
                    _key_to_idx = {pygame.K_1: 0, pygame.K_2: 1, pygame.K_3: 2}
                    if event.key in _key_to_idx:
                        _chosen_idx = _key_to_idx[event.key]
                        if _chosen_idx < len(perk_choices):
                            _chosen_perk = perk_choices[_chosen_idx]
                            _pid = str(_chosen_perk["id"])
                            if _pid == "hp":
                                player_max_hp += 25.0; player_hp = min(player_max_hp, player_hp + 25.0)
                            elif _pid == "mana":
                                player_max_mana += 25.0; player_mana = min(player_max_mana, player_mana + 25.0)
                            elif _pid == "regen":
                                mana_regen += 2.0
                            elif _pid == "speed":
                                passive_move_speed_mult = min(2.5, passive_move_speed_mult + 0.08)
                            elif _pid == "dmg":
                                passive_damage_mult = min(4.0, passive_damage_mult + 0.10)
                            elif _pid == "hp_regen":
                                passive_hp_regen += 2.0
                            elif _pid == "sp":
                                skill_points += 2
                            elif _pid == "gold":
                                player_gold += 30
                            perk_choice_pending = False
                            perk_choices.clear()
                            set_status(f"Perk chosen: {_chosen_perk['name']} — {_chosen_perk['desc']}", 2.2)
                            audio.play_sfx("level_up", cooldown_ms=100)
                    continue
                if event.key == pygame.K_ESCAPE:
                    if isinstance(drag_item, dict):
                        cancel_drag_item()
                        continue
                    if teleport_menu_open:
                        teleport_menu_open = False
                        continue
                    elif show_spellbook:
                        show_spellbook = False
                        audio.play_sfx("ui_close", cooldown_ms=70)
                    elif show_world_map:
                        show_world_map = False
                        audio.play_sfx("ui_close", cooldown_ms=70)
                    elif show_skill_tree:
                        show_skill_tree = False
                        skill_hover = None
                        audio.play_sfx("ui_close", cooldown_ms=70)
                    elif show_character:
                        cancel_drag_item()
                        show_character = False
                        audio.play_sfx("ui_close", cooldown_ms=70)
                    elif show_crafting:
                        show_crafting = False
                        audio.play_sfx("ui_close", cooldown_ms=70)
                    elif show_quest_log:
                        show_quest_log = False
                        quest_actions_from_vendor = False
                        quest_vendor_role = None
                        audio.play_sfx("ui_close", cooldown_ms=70)
                    elif show_professions:
                        show_professions = False
                        show_quest_log = False
                        quest_actions_from_vendor = False
                        quest_vendor_role = None
                        audio.play_sfx("ui_close", cooldown_ms=70)
                    elif npc_menu_mode in ("chat", "shop"):
                        npc_menu_mode = "menu"
                        active_dialogue = None
                        shop_open = None
                        audio.play_sfx("ui_close", cooldown_ms=70)
                    elif npc_menu_mode == "menu":
                        npc_menu_mode = ""
                        active_vendor_idx = None
                        active_vendor_line = ""
                        audio.play_sfx("ui_close", cooldown_ms=70)
                    elif npc_menu_mode == "dialogue":
                        npc_menu_mode = "menu"
                        active_dialogue = None
                        audio.play_sfx("ui_close", cooldown_ms=70)
                    elif shop_open:
                        shop_open = None
                        audio.play_sfx("ui_close", cooldown_ms=70)
                    elif show_level_decor_editor:
                        toggle_level_decor_editor()
                    else:
                        persist_progress()
                        return "MENU"
                elif event.key == pygame.K_k:
                    if show_level_decor_editor or show_character or show_crafting or show_quest_log or show_professions or show_world_map:
                        continue
                    show_skill_tree = not show_skill_tree
                    skill_hover = None
                    if show_skill_tree:
                        set_status("Skill tree opened.", 1.0)
                    else:
                        audio.play_sfx("ui_close", cooldown_ms=70)
                elif event.key == pygame.K_m:
                    if show_level_decor_editor or show_skill_tree or show_character or show_crafting or show_quest_log or show_professions:
                        continue
                    if npc_menu_mode != "" or bool(shop_open):
                        continue
                    show_world_map = not show_world_map
                    audio.play_sfx("ui_open" if show_world_map else "ui_close", cooldown_ms=70)
                elif event.key == pygame.K_F8:
                    if show_level_decor_editor or show_skill_tree or show_character or show_crafting or show_quest_log or show_professions or show_world_map or npc_menu_mode != "" or bool(shop_open):
                        continue
                    set_blacksmith_shop_anchor_to_player()
                elif event.key == pygame.K_DELETE:
                    universal_delete_mode = not universal_delete_mode
                    if universal_delete_mode:
                        set_status("DELETE MODE ON — click anything to remove it", 2.5)
                    else:
                        set_status("Delete mode OFF", 1.2)
                elif event.key == pygame.K_F9:
                    if not show_level_decor_editor and (show_skill_tree or show_character or show_crafting or show_quest_log or show_professions or show_world_map or npc_menu_mode != "" or bool(shop_open)):
                        continue
                    toggle_level_decor_editor()
                elif show_level_decor_editor:
                    if ctrl_down and event.key == pygame.K_s:
                        save_level_decor_state(show_feedback=True)
                    elif event.key == pygame.K_F10:
                        reload_level_decor_asset_library()
                    elif event.key == pygame.K_ESCAPE and (decor_search_active or ai_asset_input_active):
                        decor_search_active = False
                        ai_asset_input_active = False
                    elif ai_asset_input_active:
                        if event.key == pygame.K_BACKSPACE:
                            ai_asset_prompt = ai_asset_prompt[:-1]
                        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                            ai_asset_input_active = False
                            generate_ai_decor_asset()
                        else:
                            ch = event.unicode
                            if ch and ch.isprintable() and len(ai_asset_prompt) < 120:
                                ai_asset_prompt += ch
                    elif event.key in (pygame.K_SLASH, pygame.K_f):
                        decor_search_active = True
                    elif decor_search_active:
                        if event.key == pygame.K_BACKSPACE:
                            set_level_decor_search(decor_search_text[:-1])
                        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                            decor_search_active = False
                        else:
                            char = event.unicode
                            if char and char.isprintable():
                                set_level_decor_search(decor_search_text + char)
                    elif event.key == pygame.K_r:
                        decor_selected_rotation = (decor_selected_rotation + 15.0) % 360.0
                    elif event.key == pygame.K_1:
                        decor_placement_mode = "single"
                    elif event.key == pygame.K_2:
                        decor_placement_mode = "tile"
                    elif event.key == pygame.K_3:
                        decor_placement_mode = "scatter"
                    elif event.key == pygame.K_4:
                        decor_placement_mode = "move"
                        cancel_grab()
                        cancel_vendor_shop_grab()
                    elif event.key == pygame.K_ESCAPE and decor_grabbed is not None:
                        cancel_grab()
                    elif event.key == pygame.K_ESCAPE and decor_grab_vendor_idx is not None:
                        cancel_vendor_shop_grab()
                    elif event.key == pygame.K_ESCAPE and decor_grab_church:
                        cancel_church_grab()
                    elif event.key == pygame.K_h:
                        decor_editor_panel_side = "left" if decor_editor_panel_side == "right" else "right"
                    elif event.key in (pygame.K_LEFTBRACKET, pygame.K_MINUS, pygame.K_KP_MINUS):
                        adjust_level_decor_scale(-0.05)
                    elif event.key in (pygame.K_RIGHTBRACKET, pygame.K_EQUALS, pygame.K_KP_PLUS):
                        adjust_level_decor_scale(0.05)
                    continue
                elif show_world_map:
                    continue
                elif event.key == pygame.K_o and not show_skill_tree and not show_character and not show_crafting and not show_quest_log and not show_world_map:
                    show_professions = not show_professions
                    if show_professions:
                        audio.play_sfx("ui_open", cooldown_ms=70)
                    else:
                        audio.play_sfx("ui_close", cooldown_ms=70)
                elif keybind_editing_slot >= 0:
                    # Capture any key press to set the binding for the editing slot
                    if event.key == pygame.K_ESCAPE:
                        keybind_editing_slot = -1
                    else:
                        spell_slot_keybinds[keybind_editing_slot] = event.key
                        keybind_editing_slot = -1
                elif event.key in spell_slot_keybinds:
                    if show_skill_tree or show_character or show_crafting or show_quest_log or show_professions or show_world_map or show_spellbook:
                        pass
                    elif npc_menu_mode != "":
                        pass
                    else:
                        _slot_idx = spell_slot_keybinds.index(event.key)
                        _mouse = pygame.mouse.get_pos()
                        _world_mouse = Vector2(_mouse[0] + camera.x, _mouse[1] + camera.y)
                        facing = 1 if _world_mouse.x >= player_pos.x else -1
                        try_cast_slot(_slot_idx, _world_mouse)
                elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4):
                    if show_skill_tree or show_character or show_crafting or show_quest_log or show_professions or show_world_map:
                        continue
                    if npc_menu_mode not in ("", "menu", "shop"):
                        continue
                    if npc_menu_mode == "menu" and active_vendor_idx is not None and 0 <= active_vendor_idx < len(vendors):
                        vnm = vendors[active_vendor_idx]
                        rnm = str(vnm.get("role", ""))
                        opts_nm: List[str] = ["talk"]
                        if rnm in VENDOR_SHOPS:
                            opts_nm.append("shop")
                        if rnm == "Blacksmith":
                            opts_nm.append("craft")
                        if vnm.get("profession_id"):
                            opts_nm.append("profession")
                        if vendor_has_quest_menu(rnm, quest_states, QUEST_DEFINITIONS):
                            opts_nm.append("quests")
                        opt_idx = event.key - pygame.K_1
                        if 0 <= opt_idx < len(opts_nm):
                            chosen = opts_nm[opt_idx]
                            if chosen == "talk":
                                sync_dialogue_data(save=True)
                                d_def = get_dialogue_for_npc(str(vnm.get("role", "")))
                                if d_def:
                                    active_dialogue = DialogueSession(d_def, character_data, {})
                                    npc_menu_mode = "dialogue"
                                else:
                                    npc_menu_mode = "chat"
                                audio.play_sfx("ui_open", cooldown_ms=70)
                            elif chosen == "shop":
                                shop_open = rnm
                                npc_menu_mode = "shop"
                            elif chosen == "craft":
                                show_crafting = True
                                inv_tab = "Craft"
                                npc_menu_mode = ""
                            elif chosen == "profession":
                                show_professions = True
                                selected_profession = str(vnm.get("profession_id", selected_profession))
                                npc_menu_mode = ""
                                audio.play_sfx("ui_open", cooldown_ms=70)
                            elif chosen == "quests":
                                show_quest_log = True
                                quest_actions_from_vendor = current_level == "town"
                                npc_menu_mode = ""
                                audio.play_sfx("ui_open", cooldown_ms=70)
                    elif npc_menu_mode == "dialogue" and active_dialogue:
                        # Number keys for dialogue choices
                        choice_idx = event.key - pygame.K_1
                        choices = active_dialogue.get_available_choices()
                        if 0 <= choice_idx < len(choices):
                            cont, msg = active_dialogue.select_choice(choice_idx)
                            if msg: set_status(msg, 1.5)
                            sync_dialogue_data(save=False)
                            if not cont or not active_dialogue.get_current_node():
                                npc_menu_mode = "menu"
                                active_dialogue = None
                            audio.play_sfx("ui_open", cooldown_ms=50)
                    elif shop_open and event.key in (pygame.K_1, pygame.K_2, pygame.K_3):
                        items = VENDOR_SHOPS.get(shop_open, [])
                        item_idx = event.key - pygame.K_1
                        if 0 <= item_idx < len(items):
                            item = items[item_idx]
                            cost = int(item["cost"])
                            if player_gold >= cost:
                                entry = {
                                    "id": f"shop_{shop_open.lower()}_{item_idx}_{pygame.time.get_ticks()}",
                                    "name": str(item.get("name", "Item")),
                                    "desc": str(item.get("desc", "")),
                                    "effect": str(item.get("effect", "")),
                                    "rarity": str(item.get("rarity", "common")),
                                    "item_type": str(item.get("item_type", "consumable")),
                                    "equip_slot": str(item.get("equip_slot", "")),
                                    "color": item.get("color", (170, 170, 176)),
                                    "icon": item.get("icon"),
                                }
                                is_consumable = str(item.get("item_type", "consumable")) == "consumable"
                                _free_slot = next((i for i, s in enumerate(item_inventory) if s is None), None)
                                goes_to_bar = is_consumable and item_can_go_in_potion_bar(entry) and _free_slot is not None
                                if goes_to_bar:
                                    item_inventory[_free_slot] = clone_item_data(entry)
                                    player_gold -= cost
                                    update_spend_gold_quests(cost)
                                    update_gold_accumulate_quests()
                                    set_status(f"Bought {item['name']}. Added to potion bar.", 1.6)
                                elif add_item_to_inventory(entry, prefer_hotbar=False):
                                    player_gold -= cost
                                    update_spend_gold_quests(cost)
                                    update_gold_accumulate_quests()
                                    set_status(f"Bought {item['name']}. Sent to backpack.", 1.6)
                                else:
                                    set_status("Backpack full. Free space first.", 1.4)
                            else:
                                set_status(f"Not enough gold. Need {cost}g (have {player_gold}g).", 1.4)
                    else:
                        slot = event.key - pygame.K_1
                        _now_ms = pygame.time.get_ticks()
                        if _now_ms - potion_last_used_ms >= 350:
                            _slot_item = item_inventory[slot] if 0 <= slot < HOTBAR_SLOT_COUNT else None
                            if _slot_item is not None:
                                potion_last_used_ms = _now_ms
                                item = _slot_item
                                if not item_can_go_in_potion_bar(item):
                                    set_status("Only potions can be used from the potion bar.", 1.1)
                                    continue
                                item_inventory[slot] = None
                                effect = str(item.get("effect", ""))
                                eff_hp_max = player_max_hp + bonus_max_hp
                                if effect == "hp_80":
                                    player_hp = min(eff_hp_max, player_hp + 80.0)
                                    set_status(f"Used {item['name']}. +80 HP.", 1.6)
                                elif effect == "hp_60":
                                    player_hp = min(eff_hp_max, player_hp + 60.0)
                                    set_status(f"Used {item['name']}. +60 HP.", 1.6)
                                elif effect == "hp_25":
                                    player_hp = min(eff_hp_max, player_hp + 25.0)
                                    set_status(f"Used {item['name']}. +25 HP.", 1.6)
                                elif effect == "mp_80":
                                    player_mana = min(player_max_mana, player_mana + 80.0)
                                    set_status(f"Used {item['name']}. +80 MP.", 1.6)
                                elif effect == "mp_full":
                                    player_mana = player_max_mana
                                    set_status(f"Used {item['name']}. Mana restored.", 1.6)
                                elif effect == "full_restore":
                                    player_hp = eff_hp_max
                                    player_mana = player_max_mana
                                    set_status(f"Used {item['name']}. HP and Mana fully restored!", 2.0)
                                elif effect == "dmg_boost":
                                    damage_boost_timer = 90.0
                                    set_status(f"Used {item['name']}. +20% damage for 90s!", 2.0)
                                elif effect == "dmg_boost_120":
                                    damage_boost_timer = 120.0
                                    set_status(f"Used {item['name']}. +35% damage for 120s!", 2.0)
                                elif effect == "speed_boost_60":
                                    speed_boost_timer = 60.0
                                    set_status(f"Used {item['name']}. +28% speed for 60s!", 2.0)
                                elif effect == "town_portal":
                                    if not use_town_portal_scroll():
                                        item_inventory[slot] = item
                                elif effect == "teleport_book":
                                    item_inventory[slot] = item
                                    teleport_menu_open = True
                                else:
                                    item_inventory[slot] = item
                                    set_status("That slot has a non-usable item.", 0.9)
                            else:
                                set_status("No potion in that slot.", 0.8)
                elif event.key == pygame.K_n:
                    # Toggle WoW-style spellbook overlay
                    if not show_skill_tree and not show_character and not show_crafting and not show_quest_log and not show_world_map:
                        show_spellbook = not show_spellbook
                        audio.play_sfx("ui_open" if show_spellbook else "ui_close", cooldown_ms=70)
                    elif show_spellbook:
                        show_spellbook = False
                        audio.play_sfx("ui_close", cooldown_ms=70)
                elif event.key == pygame.K_TAB:
                    if show_character or show_crafting or show_quest_log or show_professions or show_world_map:
                        continue
                    if show_spellbook:
                        # Cycle spellbook tabs
                        _tabs = ["class", "passive", "general"]
                        spellbook_tab = _tabs[(_tabs.index(spellbook_tab) + 1) % len(_tabs)]
                    else:
                        selected_spell_idx = (selected_spell_idx + 1) % max(1, len(active_spellbook))
                elif event.key == pygame.K_b and not show_skill_tree and not show_character and not show_crafting and not show_quest_log and not show_professions and not show_world_map and current_level == "town":
                    # Open/close shop for the nearest shop vendor
                    if shop_open:
                        shop_open = None
                        if npc_menu_mode == "shop":
                            npc_menu_mode = "menu"
                        audio.play_sfx("ui_close", cooldown_ms=70)
                    elif active_vendor_idx is not None and 0 <= active_vendor_idx < len(vendors):
                        role = str(vendors[active_vendor_idx].get("role", ""))
                        if role in VENDOR_SHOPS:
                            shop_open = role
                            npc_menu_mode = "shop"
                            audio.play_sfx("ui_open", cooldown_ms=70)
                        else:
                            set_status("This vendor doesn't sell anything.", 1.2)
                    else:
                        # No vendor nearby — fall through to open backpack
                        show_crafting = not show_crafting
                        if show_crafting:
                            inv_tab = "Backpack"
                            crafting_selected = crafting_selected or (CRAFTING_RECIPES[0]["id"] if CRAFTING_RECIPES else None)
                            audio.play_sfx("ui_open", cooldown_ms=70)
                        else:
                            audio.play_sfx("ui_close", cooldown_ms=70)
                        shop_open = None
                # ── Crafting toggle ───────────────────────────────────────────
                elif event.key in (pygame.K_i, pygame.K_b) and not show_skill_tree and not show_quest_log and not show_world_map:
                    if show_character:
                        pass # Allow both open
                    show_crafting = not show_crafting
                    if show_crafting:
                        inv_tab = "Backpack"
                        crafting_selected = crafting_selected or (CRAFTING_RECIPES[0]["id"] if CRAFTING_RECIPES else None)
                        audio.play_sfx("ui_open", cooldown_ms=70)
                    else:
                        audio.play_sfx("ui_close", cooldown_ms=70)
                    shop_open = None
                    npc_menu_mode = ""

                elif event.key == pygame.K_p and not show_skill_tree and not show_quest_log and not show_world_map:
                    if show_crafting:
                        pass # Allow both open
                    show_character = not show_character
                    if not show_character:
                        cancel_drag_item()
                        audio.play_sfx("ui_close", cooldown_ms=70)
                    else:
                        audio.play_sfx("ui_open", cooldown_ms=70)
                    shop_open = None
                    npc_menu_mode = ""

                # ── Fishing (F near fish rack in ice biome) ──────────────────
                elif event.key == pygame.K_f and current_level == "ice_biome" and not fishing_active and not perk_choice_pending:
                    _fish_rack_pos = Vector2(2768, 1478)
                    if player_pos.distance_to(_fish_rack_pos) <= 180:
                        fishing_active = True
                        fishing_timer = 4.0
                        fishing_bar_pos = 0.5
                        fishing_bar_vel = random.uniform(0.6, 1.1) * random.choice([-1, 1])
                        fishing_catch_zone = random.uniform(0.18, 0.62)
                        fishing_result = ""
                        set_status("Fishing... Press SPACE when the bar is in the green zone!", 4.0)
                    else:
                        set_status("No fishing spot nearby. Find the fish rack.", 1.4)
                # ── Fishing catch (SPACE) ──────────────────────────────────
                elif event.key == pygame.K_SPACE and fishing_active:
                    # Check if bar is in catch zone (zone spans 0.22 width centered on fishing_catch_zone)
                    _catch_half = 0.11
                    _hit = abs(fishing_bar_pos - (fishing_catch_zone + _catch_half)) <= _catch_half
                    fishing_active = False
                    if _hit:
                        # Award fish loot
                        _fish_loot: Dict[str, int] = {}
                        for _mat_id in ("arctic_fish", "icefish_oil", "frost_roe"):
                            _mat = PASSIVE_ANIMAL_MATERIALS[_mat_id]
                            if random.random() < _mat["drop_chance"]:
                                _fish_loot[_mat_id] = random.randint(1, int(_mat["max_drop"]))
                        for _fmat, _fqty in _fish_loot.items():
                            materials[_fmat] = materials.get(_fmat, 0) + _fqty
                        _fish_names = [PASSIVE_ANIMAL_MATERIALS[k]["name"] for k in _fish_loot]
                        fishing_result = "success"
                        fishing_result_timer = 2.5
                        _gain_str = ", ".join(_fish_names) if _fish_names else "nothing rare"
                        set_status(f"Caught fish! You got: {_gain_str}", 2.5)
                        audio.play_sfx("pickup_gold", cooldown_ms=100)
                    else:
                        fishing_result = "fail"
                        fishing_result_timer = 1.8
                        set_status("Missed! The fish slipped away.", 1.8)

                # ── Quest log toggle ──────────────────────────────────────────
                elif event.key == pygame.K_j and not show_skill_tree and not show_crafting and not show_character and not show_world_map:
                    show_quest_log = not show_quest_log
                    quest_actions_from_vendor = False
                    quest_vendor_role = None
                    audio.play_sfx("ui_open" if show_quest_log else "ui_close", cooldown_ms=70)
                    shop_open = None
                    npc_menu_mode = ""

                # ── Crafting: ENTER to craft ──────────────────────────────────
                elif event.key == pygame.K_RETURN and show_crafting and crafting_selected:
                    recipe = next((r for r in CRAFTING_RECIPES if r["id"] == crafting_selected), None)
                    if recipe:
                        can_afford = all(materials.get(mid, 0) >= cnt for mid, cnt in recipe["ingredients"].items())
                        result = recipe["result"]
                        effect = result["effect"]
                        has_instant = effect in ("max_hp_15", "mana_regen_05", "skill_point")
                        inv_full = len(backpack_inventory) >= BACKPACK_SLOT_COUNT
                        if not can_afford:
                            set_status("Not enough materials to craft that.", 1.4)
                        elif inv_full and not has_instant:
                            set_status("Backpack full. Free space first.", 1.4)
                        else:
                            for mid, cnt in recipe["ingredients"].items():
                                materials[mid] = materials.get(mid, 0) - cnt
                            if effect == "max_hp_15" and iron_coat_count < 3:
                                iron_coat_count += 1
                                bonus_max_hp += 15.0
                                player_max_hp += 15.0
                                player_hp = min(player_hp + 15.0, player_max_hp + bonus_max_hp)
                                set_status(f"Crafted {result['name']}! Max HP +15 (permanent).", 2.0)
                            elif effect == "mana_regen_05" and fang_amulet_count < 3:
                                fang_amulet_count += 1
                                bonus_mana_regen += 0.5
                                mana_regen += 0.5
                                set_status(f"Crafted {result['name']}! Mana regen +0.5/s (permanent).", 2.0)
                            elif effect == "skill_point":
                                skill_points += 1
                                set_status(f"Crafted {result['name']}! +1 Skill Point.", 2.0)
                            elif effect in ("max_hp_15", "mana_regen_05"):
                                set_status(f"{result['name']} already at max stacks (3).", 1.4)
                                # Refund ingredients
                                for mid, cnt in recipe["ingredients"].items():
                                    materials[mid] = materials.get(mid, 0) + cnt
                            else:
                                crafted_entry = dict(result)
                                crafted_entry.setdefault("item_type", "consumable")
                                crafted_entry.setdefault("equip_slot", "")
                                if add_item_to_inventory(crafted_entry, prefer_hotbar=False):
                                    set_status(f"Crafted {result['name']}!", 1.6)
                                else:
                                    for mid, cnt in recipe["ingredients"].items():
                                        materials[mid] = materials.get(mid, 0) + cnt
                                    set_status("Backpack full. Craft canceled.", 1.4)
                            if effect not in ("max_hp_15", "mana_regen_05") or (effect == "max_hp_15" and iron_coat_count <= 3) or (effect == "mana_regen_05" and fang_amulet_count <= 3):
                                update_craft_quests(crafting_selected)
                            update_gather_quests()

                # ── Quest log: Accept / Turn In ───────────────────────────────
                elif event.key == pygame.K_a and show_quest_log and quest_selected:
                    if not quest_actions_from_vendor or current_level != "town":
                        set_status("Accept quests from town vendors/NPCs.", 1.4)
                        continue
                    sel_role = quest_giver_role_for_id(quest_selected).strip().lower()
                    if quest_vendor_role and sel_role != str(quest_vendor_role).strip().lower():
                        set_status("That quest belongs to another vendor.", 1.4)
                        continue
                    has_open_same_vendor = False
                    for qdef in QUEST_DEFINITIONS:
                        qid = str(qdef.get("id", "")).strip()
                        if not qid or qid == quest_selected:
                            continue
                        if _quest_role_for_def(qdef) != sel_role:
                            continue
                        if quest_states.get(qid) in ("active", "complete"):
                            has_open_same_vendor = True
                            break
                    if has_open_same_vendor:
                        set_status("Finish your current quest for this vendor first.", 1.6)
                        continue
                    if quest_states.get(quest_selected) == "available":
                        quest_states[quest_selected] = "active"
                        quest_progress[quest_selected] = [0] * len(next(q["objectives"] for q in QUEST_DEFINITIONS if q["id"] == quest_selected))
                        q_title = next(q["title"] for q in QUEST_DEFINITIONS if q["id"] == quest_selected)
                        normalize_vendor_available_quests(quest_states, QUEST_DEFINITIONS)
                        update_gather_quests()
                        set_status(f"Quest accepted: {q_title}.", 1.8)
                elif event.key == pygame.K_t and show_quest_log and quest_selected:
                    if not quest_actions_from_vendor or current_level != "town":
                        set_status("Turn in quests at town vendors/NPCs.", 1.4)
                        continue
                    sel_role = quest_giver_role_for_id(quest_selected).strip().lower()
                    if quest_vendor_role and sel_role != str(quest_vendor_role).strip().lower():
                        set_status("That quest belongs to another vendor.", 1.4)
                        continue
                    if quest_states.get(quest_selected) == "complete":
                        qdef = next((q for q in QUEST_DEFINITIONS if q["id"] == quest_selected), None)
                        if qdef:
                            rew = qdef["rewards"]
                            player_gold   += rew.get("gold", 0)
                            skill_points  += rew.get("sp", 0)
                            if rew.get("item"):
                                add_item_to_inventory(dict(rew["item"]), prefer_hotbar=False)
                            quest_states[quest_selected] = "turned_in"
                            update_gold_accumulate_quests()
                            set_status(f"Turned in: {qdef['title']}! +{rew.get('gold',0)}g +{rew.get('sp',0)} SP.", 2.4)
                            if qdef.get("chain_next"):
                                quest_states[qdef["chain_next"]] = "available"
                            refresh_quest_availability()
                            quest_selected = None
                            audio.play_sfx("quest_complete", cooldown_ms=100)

                # ── Use consumable items F1-F8 ────────────────────────────────
                elif event.key in (pygame.K_F1, pygame.K_F2, pygame.K_F3, pygame.K_F4,
                                   pygame.K_F5, pygame.K_F6, pygame.K_F7, pygame.K_F8):
                    if not show_skill_tree and not show_character and not show_crafting and not show_quest_log and not show_professions and not show_world_map:
                        slot = event.key - pygame.K_F1
                        _fslot_item = item_inventory[slot] if 0 <= slot < HOTBAR_SLOT_COUNT else None
                        if _fslot_item is not None:
                            item = _fslot_item
                            if not item_can_go_in_potion_bar(item):
                                set_status("Only potions can be used from the potion bar.", 1.1)
                                continue
                            item_inventory[slot] = None
                            effect = str(item.get("effect", ""))
                            eff_hp_max = player_max_hp + bonus_max_hp
                            if effect == "hp_80":
                                player_hp = min(eff_hp_max, player_hp + 80.0)
                                set_status(f"Used {item['name']}. +80 HP.", 1.6)
                            elif effect == "hp_60":
                                player_hp = min(eff_hp_max, player_hp + 60.0)
                                set_status(f"Used {item['name']}. +60 HP.", 1.6)
                            elif effect == "hp_25":
                                player_hp = min(eff_hp_max, player_hp + 25.0)
                                set_status(f"Used {item['name']}. +25 HP.", 1.6)
                            elif effect == "mp_80":
                                player_mana = min(player_max_mana, player_mana + 80.0)
                                set_status(f"Used {item['name']}. +80 MP.", 1.6)
                            elif effect == "mp_full":
                                player_mana = player_max_mana
                                set_status(f"Used {item['name']}. Mana restored.", 1.6)
                            elif effect == "full_restore":
                                player_hp   = eff_hp_max
                                player_mana = player_max_mana
                                set_status(f"Used {item['name']}. HP and Mana fully restored!", 2.0)
                            elif effect == "dmg_boost":
                                damage_boost_timer = 90.0
                                set_status(f"Used {item['name']}. +20% damage for 90s!", 2.0)
                            elif effect == "dmg_boost_120":
                                damage_boost_timer = 120.0
                                set_status(f"Used {item['name']}. +35% damage for 120s!", 2.0)
                            elif effect == "speed_boost_60":
                                speed_boost_timer = 60.0
                                set_status(f"Used {item['name']}. +28% speed for 60s!", 2.0)
                            elif effect == "town_portal":
                                if not use_town_portal_scroll():
                                    item_inventory[slot] = item
                            elif effect == "teleport_book":
                                item_inventory[slot] = item
                                teleport_menu_open = True
                        else:
                            set_status("No item in that slot.", 0.8)
            elif event.type == pygame.MOUSEWHEEL and show_level_decor_editor:
                panel_rect = decor_editor_ui.get("panel_rect")
                mouse_pos = pygame.mouse.get_pos()
                if isinstance(panel_rect, pygame.Rect) and panel_rect.collidepoint(mouse_pos):
                    adjust_level_decor_scroll(-int(event.y) * 56)
                else:
                    adjust_level_decor_scale(float(event.y) * 0.05)
                continue
            elif event.type == pygame.MOUSEBUTTONUP:
                if show_level_decor_editor:
                    if event.button == 1 and drag_npc_idx is not None:
                        save_npc_positions(vendors)
                        drag_npc_idx = None
                        set_status("NPC position saved.", 0.9)
                    continue
                if show_world_map:
                    continue
                # Second click while holding a drag item — do nothing on mouseup,
                # the drop is handled on MOUSEBUTTONDOWN below.
            elif event.type == pygame.MOUSEBUTTONDOWN:
                # Delete-confirm dialog absorbs all clicks
                if delete_confirm_item is not None:
                    if isinstance(_delete_cancel_rect, pygame.Rect) and _delete_cancel_rect.collidepoint(event.pos):
                        delete_confirm_item   = None
                        delete_confirm_source = ""
                        delete_confirm_typed  = ""
                    continue

                # Second click while holding an item — try to place it, or destroy it
                if event.button == 1 and isinstance(drag_item, dict):
                    finish_drag_drop(event.pos)
                    continue

                # Right-click on action bar slot → enter keybind edit mode
                if event.button == 3 and not show_spellbook and not show_character and not show_skill_tree:
                    for _kb_i, _kb_rect in enumerate(_spell_bar_slot_rects):
                        if _kb_rect.collidepoint(event.pos):
                            keybind_editing_slot = _kb_i
                            break
                # Teleport menu — handle clicks
                if teleport_menu_open and event.button == 1:
                    _tp_clicked = False
                    for _tp_key, _tp_rect in teleport_menu_rects.items():
                        if _tp_rect.collidepoint(event.pos):
                            if _tp_key == "close":
                                teleport_menu_open = False
                            else:
                                # Start book portal animation instead of instant teleport
                                book_portal_active = True
                                book_portal_origin = Vector2(player_pos)
                                book_portal_dest_level = _tp_key
                                book_portal_timer = book_portal_total
                                book_portal_particle_cd = 0.0
                                teleport_menu_open = False
                                set_status("A golden portal tears open...", 1.8)
                                spawn_particle_burst(
                                    spell_effects, player_pos,
                                    (255, 200, 50), (255, 160, 30),
                                    18, 40, 100, 0.4, 0.9, 4.0, 1.0,
                                    gravity=-30.0, drag=1.5,
                                )
                            _tp_clicked = True
                            break
                    if not _tp_clicked:
                        teleport_menu_open = False
                    continue
                # Perk selection — handle clicks on cards
                if perk_choice_pending and perk_choices and event.button == 1:
                    _perk_card_w2 = 270
                    _perk_total_w2 = len(perk_choices) * (_perk_card_w2 + 24) - 24
                    _perk_sx2 = SCREEN_WIDTH // 2 - _perk_total_w2 // 2
                    for _pi2, _perk2 in enumerate(perk_choices):
                        _pr2 = pygame.Rect(_perk_sx2 + _pi2 * (_perk_card_w2 + 24), 230, _perk_card_w2, 130)
                        if _pr2.collidepoint(event.pos):
                            _pid2 = str(_perk2["id"])
                            if _pid2 == "hp":
                                player_max_hp += 25.0; player_hp = min(player_max_hp, player_hp + 25.0)
                            elif _pid2 == "mana":
                                player_max_mana += 25.0; player_mana = min(player_max_mana, player_mana + 25.0)
                            elif _pid2 == "regen":
                                mana_regen += 2.0
                            elif _pid2 == "speed":
                                passive_move_speed_mult = min(2.5, passive_move_speed_mult + 0.08)
                            elif _pid2 == "dmg":
                                passive_damage_mult = min(4.0, passive_damage_mult + 0.10)
                            elif _pid2 == "hp_regen":
                                passive_hp_regen += 2.0
                            elif _pid2 == "sp":
                                skill_points += 2
                            elif _pid2 == "gold":
                                player_gold += 30
                            perk_choice_pending = False
                            perk_choices.clear()
                            set_status(f"Perk chosen: {_perk2['name']} — {_perk2['desc']}", 2.2)
                            audio.play_sfx("level_up", cooldown_ms=100)
                            break
                    continue
                if show_level_decor_editor and event.button in (4, 5):
                    panel_rect = decor_editor_ui.get("panel_rect")
                    if isinstance(panel_rect, pygame.Rect) and panel_rect.collidepoint(event.pos):
                        adjust_level_decor_scroll(56 if event.button == 5 else -56)
                    else:
                        adjust_level_decor_scale(-0.05 if event.button == 5 else 0.05)
                    continue
                if show_level_decor_editor:
                    panel_rect = decor_editor_ui.get("panel_rect")
                    save_rect = decor_editor_ui.get("save_rect")
                    reload_rect = decor_editor_ui.get("reload_rect")
                    clear_rect = decor_editor_ui.get("clear_rect")
                    generate_rect = decor_editor_ui.get("generate_rect")
                    demo_rect = decor_editor_ui.get("demo_rect")
                    seed_minus_rect = decor_editor_ui.get("seed_minus_rect")
                    seed_plus_rect = decor_editor_ui.get("seed_plus_rect")
                    pack_rects = decor_editor_ui.get("pack_rects", {})
                    filter_rects = decor_editor_ui.get("filter_rects", {})
                    category_rects = decor_editor_ui.get("category_rects", {})
                    mode_rects = decor_editor_ui.get("mode_rects", {})
                    collision_rect = decor_editor_ui.get("collision_rect")
                    inspector_rects = decor_editor_ui.get("inspector_rects", {})
                    asset_rects = decor_editor_ui.get("asset_rects", {})
                    search_rect = decor_editor_ui.get("search_rect")
                    clear_search_rect = decor_editor_ui.get("clear_search_rect")
                    ai_prompt_rect = decor_editor_ui.get("ai_prompt_rect")
                    ai_generate_btn_rect = decor_editor_ui.get("ai_generate_btn_rect")
                    ai_scope_rects = decor_editor_ui.get("ai_scope_rects", {})
                    scale_minus_rect = decor_editor_ui.get("scale_minus_rect")
                    scale_plus_rect = decor_editor_ui.get("scale_plus_rect")
                    rot_minus_rect = decor_editor_ui.get("rot_minus_rect")
                    rot_plus_rect = decor_editor_ui.get("rot_plus_rect")
                    if event.button == 1:
                        if isinstance(clear_rect, pygame.Rect) and clear_rect.collidepoint(event.pos):
                            entry_count = len(active_level_decor_entries())
                            if entry_count <= 0:
                                clear_decor_confirm = False
                                set_status("No placed decorations to clear.", 0.9)
                                continue
                            if clear_decor_confirm:
                                if clear_active_level_decor():
                                    noun = "decoration" if entry_count == 1 else "decorations"
                                    set_status(f"Cleared {entry_count} {noun} from this level.", 1.2)
                                clear_decor_confirm = False
                            else:
                                clear_decor_confirm = True
                                set_status("Click Clear All again to wipe this level's placed decorations.", 1.6)
                            continue
                        clear_decor_confirm = False
                        if isinstance(save_rect, pygame.Rect) and save_rect.collidepoint(event.pos):
                            save_level_decor_state(show_feedback=True)
                            continue
                        if isinstance(reload_rect, pygame.Rect) and reload_rect.collidepoint(event.pos):
                            reload_level_decor_asset_library()
                            continue
                        if isinstance(generate_rect, pygame.Rect) and generate_rect.collidepoint(event.pos):
                            generate_medieval_asset_pack()
                            continue
                        if isinstance(demo_rect, pygame.Rect) and demo_rect.collidepoint(event.pos):
                            create_medieval_demo_level()
                            continue
                        if isinstance(seed_minus_rect, pygame.Rect) and seed_minus_rect.collidepoint(event.pos):
                            decor_generate_seed = max(1, decor_generate_seed - 1)
                            continue
                        if isinstance(seed_plus_rect, pygame.Rect) and seed_plus_rect.collidepoint(event.pos):
                            decor_generate_seed = min(999999, decor_generate_seed + 1)
                            continue
                        if isinstance(scale_minus_rect, pygame.Rect) and scale_minus_rect.collidepoint(event.pos):
                            adjust_level_decor_scale(-0.1)
                            continue
                        if isinstance(scale_plus_rect, pygame.Rect) and scale_plus_rect.collidepoint(event.pos):
                            adjust_level_decor_scale(0.1)
                            continue
                        if isinstance(rot_minus_rect, pygame.Rect) and rot_minus_rect.collidepoint(event.pos):
                            decor_selected_rotation = (decor_selected_rotation - 15.0) % 360.0
                            continue
                        if isinstance(rot_plus_rect, pygame.Rect) and rot_plus_rect.collidepoint(event.pos):
                            decor_selected_rotation = (decor_selected_rotation + 15.0) % 360.0
                            continue
                        # 8-direction nudge buttons for shops
                        _nudge_rects = decor_editor_ui.get("nudge_rects")
                        if isinstance(_nudge_rects, dict):
                            _NUDGE_DIRS = {
                                "nw": (-1, -1), "n": (0, -1), "ne": (1, -1),
                                "w":  (-1,  0),               "e":  (1,  0),
                                "sw": (-1,  1), "s": (0,  1), "se": (1,  1),
                            }
                            _NUDGE_DIST = 30.0
                            _nudge_hit = False
                            for _nid, _nrect in _nudge_rects.items():
                                if isinstance(_nrect, pygame.Rect) and _nrect.collidepoint(event.pos):
                                    _ndx, _ndy = _NUDGE_DIRS.get(_nid, (0, 0))
                                    _noffset = Vector2(_ndx * _NUDGE_DIST, _ndy * _NUDGE_DIST)
                                    # Nudge the grabbed shop, or find nearest shop to player/camera center
                                    if decor_grab_vendor_idx is not None:
                                        _nv = vendors[decor_grab_vendor_idx]
                                        _nsp = _nv.get("shop_pos")
                                        if isinstance(_nsp, Vector2):
                                            _nv["shop_pos"] = _nsp + _noffset
                                    else:
                                        _cam_center = Vector2(camera.x + SCREEN_WIDTH / 2, camera.y + SCREEN_HEIGHT / 2)
                                        _best_vi = None
                                        _best_vd = 999999.0
                                        for _vi, _vv in enumerate(vendors):
                                            _vsp = _vv.get("shop_pos")
                                            if isinstance(_vsp, Vector2):
                                                _vd = _cam_center.distance_to(_vsp)
                                                if _vd < _best_vd:
                                                    _best_vd = _vd
                                                    _best_vi = _vi
                                        if _best_vi is not None:
                                            _nsp2 = vendors[_best_vi].get("shop_pos")
                                            if isinstance(_nsp2, Vector2):
                                                vendors[_best_vi]["shop_pos"] = _nsp2 + _noffset
                                    save_npc_positions(vendors)
                                    _nudge_hit = True
                                    break
                            if _nudge_hit:
                                continue
                        if isinstance(pack_rects, dict):
                            picked_pack = False
                            for pack_id, pack_rect in pack_rects.items():
                                if isinstance(pack_rect, pygame.Rect) and pack_rect.collidepoint(event.pos):
                                    set_level_decor_asset_pack(str(pack_id))
                                    picked_pack = True
                                    break
                            if picked_pack:
                                continue
                        if isinstance(filter_rects, dict):
                            picked_filter = False
                            for filter_id, filter_rect in filter_rects.items():
                                if isinstance(filter_rect, pygame.Rect) and filter_rect.collidepoint(event.pos):
                                    set_level_decor_filter(str(filter_id))
                                    picked_filter = True
                                    break
                            if picked_filter:
                                continue
                        if isinstance(category_rects, dict):
                            picked_category = False
                            for category_id, category_rect in category_rects.items():
                                if isinstance(category_rect, pygame.Rect) and category_rect.collidepoint(event.pos):
                                    set_level_decor_category(str(category_id))
                                    picked_category = True
                                    break
                            if picked_category:
                                continue
                        if isinstance(mode_rects, dict):
                            picked_mode = False
                            for mode_id, mode_rect in mode_rects.items():
                                if isinstance(mode_rect, pygame.Rect) and mode_rect.collidepoint(event.pos):
                                    decor_placement_mode = str(mode_id)
                                    picked_mode = True
                                    break
                            if picked_mode:
                                continue
                        if isinstance(collision_rect, pygame.Rect) and collision_rect.collidepoint(event.pos):
                            decor_collision_preview = not decor_collision_preview
                            continue
                        if isinstance(search_rect, pygame.Rect) and search_rect.collidepoint(event.pos):
                            decor_search_active = True
                            continue
                        if isinstance(clear_search_rect, pygame.Rect) and clear_search_rect.collidepoint(event.pos):
                            if decor_search_text:
                                set_level_decor_search("")
                            decor_search_active = False
                            continue
                        # AI asset generator clicks
                        if isinstance(ai_prompt_rect, pygame.Rect) and ai_prompt_rect.collidepoint(event.pos):
                            ai_asset_input_active = True
                            decor_search_active = False
                            continue
                        if isinstance(ai_generate_btn_rect, pygame.Rect) and ai_generate_btn_rect.collidepoint(event.pos):
                            ai_asset_input_active = False
                            generate_ai_decor_asset()
                            continue
                        if isinstance(ai_scope_rects, dict):
                            picked_ai_scope = False
                            for _scope_id, _scope_rect in ai_scope_rects.items():
                                if isinstance(_scope_rect, pygame.Rect) and _scope_rect.collidepoint(event.pos):
                                    ai_asset_scope = str(_scope_id)
                                    picked_ai_scope = True
                                    break
                            if picked_ai_scope:
                                continue
                        if isinstance(inspector_rects, dict):
                            if isinstance(inspector_rects.get("layer"), pygame.Rect) and inspector_rects["layer"].collidepoint(event.pos):
                                if cycle_selected_decor_layer():
                                    set_status("Asset layer override updated.", 1.1)
                                continue
                            if isinstance(inspector_rects.get("origin"), pygame.Rect) and inspector_rects["origin"].collidepoint(event.pos):
                                if toggle_selected_decor_origin():
                                    set_status("Asset origin override updated.", 1.1)
                                continue
                            if isinstance(inspector_rects.get("collision"), pygame.Rect) and inspector_rects["collision"].collidepoint(event.pos):
                                if toggle_selected_decor_collision():
                                    set_status("Asset collision override updated.", 1.1)
                                continue
                        if isinstance(asset_rects, dict):
                            picked_asset = False
                            for asset_id, asset_rect in asset_rects.items():
                                if isinstance(asset_rect, pygame.Rect) and asset_rect.collidepoint(event.pos):
                                    decor_selected_asset_id = str(asset_id)
                                    decor_search_active = False
                                    picked_asset = True
                                    break
                            if picked_asset:
                                continue
                        if isinstance(panel_rect, pygame.Rect) and panel_rect.collidepoint(event.pos):
                            decor_search_active = False
                            ai_asset_input_active = False
                            continue
                        world_click = Vector2(event.pos[0] + camera.x, event.pos[1] + camera.y)
                        if decor_placement_mode == "move":
                            if decor_grabbed is not None:
                                drop_level_decor(world_click)
                            elif decor_grab_vendor_idx is not None:
                                drop_vendor_shop(world_click)
                            elif decor_grab_church:
                                drop_church(world_click)
                            else:
                                if not grab_level_decor(world_click):
                                    if not grab_vendor_shop(world_click):
                                        if not grab_church(world_click):
                                            set_status("No asset under cursor.", 0.9)
                        else:
                            vendor_idx = find_vendor_at_screen(event.pos)
                            if vendor_idx is not None:
                                drag_npc_idx = vendor_idx
                                move_vendor_to_world(vendor_idx, world_click)
                                decor_search_active = False
                                ai_asset_input_active = False
                                continue
                            # Shop/church grab only in move mode (not paint/scatter/delete)

                            if decor_placement_mode == "delete":
                                if not remove_level_decor(world_click):
                                    if not remove_hardcoded_prop(world_click):
                                        set_status("No placed asset under the cursor.", 0.9)
                            else:
                                place_level_decor(world_click)
                    elif event.button == 3:
                        clear_decor_confirm = False
                        if isinstance(panel_rect, pygame.Rect) and panel_rect.collidepoint(event.pos):
                            continue
                        world_click = Vector2(event.pos[0] + camera.x, event.pos[1] + camera.y)
                        if not remove_level_decor(world_click):
                            remove_hardcoded_prop(world_click)
                    continue
                if show_world_map:
                    continue
                # Backpack icon button
                if event.button == 1 and _backpack_btn_rect.collidepoint(event.pos):
                    show_crafting = not show_crafting
                    if show_crafting:
                        inv_tab = "Backpack"
                        audio.play_sfx("ui_open", cooldown_ms=70)
                    else:
                        audio.play_sfx("ui_close", cooldown_ms=70)

                # Left-click on spell bar slot → select & cast that spell
                if event.button == 1 and drag_item is None and not show_spellbook and not show_character and not show_skill_tree:
                    _clicked_spell_slot = False
                    for _si, _sr in enumerate(_spell_bar_slot_rects):
                        if _sr.collidepoint(event.pos):
                            _world_mouse = Vector2(event.pos[0] + camera.x, event.pos[1] + camera.y)
                            facing = 1 if _world_mouse.x >= player_pos.x else -1
                            try_cast_slot(_si, _world_mouse)
                            _clicked_spell_slot = True
                            break
                    if _clicked_spell_slot:
                        continue

                # Left-click on potion bar → use the potion
                if event.button == 1 and drag_item is None:
                    _used_pot = False
                    for idx, rect in potion_slot_rects.items():
                        if rect.collidepoint(event.pos) and idx < len(item_inventory):
                            _now_ms = pygame.time.get_ticks()
                            _slot_item = item_inventory[idx] if 0 <= idx < HOTBAR_SLOT_COUNT else None
                            if _slot_item is not None and _now_ms - potion_last_used_ms >= 350:
                                if not item_can_go_in_potion_bar(_slot_item):
                                    set_status("Only potions can be used from the potion bar.", 1.1)
                                else:
                                    potion_last_used_ms = _now_ms
                                    item_inventory[idx] = None
                                    effect = str(_slot_item.get("effect", ""))
                                    eff_hp_max = player_max_hp + bonus_max_hp
                                    if effect == "hp_80":
                                        player_hp = min(eff_hp_max, player_hp + 80.0)
                                        set_status(f"Used {_slot_item['name']}. +80 HP.", 1.6)
                                    elif effect == "hp_60":
                                        player_hp = min(eff_hp_max, player_hp + 60.0)
                                        set_status(f"Used {_slot_item['name']}. +60 HP.", 1.6)
                                    elif effect == "hp_25":
                                        player_hp = min(eff_hp_max, player_hp + 25.0)
                                        set_status(f"Used {_slot_item['name']}. +25 HP.", 1.6)
                                    elif effect == "mp_80":
                                        player_mana = min(player_max_mana, player_mana + 80.0)
                                        set_status(f"Used {_slot_item['name']}. +80 MP.", 1.6)
                                    elif effect == "mp_full":
                                        player_mana = player_max_mana
                                        set_status(f"Used {_slot_item['name']}. Mana restored.", 1.6)
                                    elif effect == "full_restore":
                                        player_hp = eff_hp_max
                                        player_mana = player_max_mana
                                        set_status(f"Used {_slot_item['name']}. HP and Mana fully restored!", 2.0)
                                    elif effect == "dmg_boost":
                                        damage_boost_timer = 90.0
                                        set_status(f"Used {_slot_item['name']}. +20% damage for 90s!", 2.0)
                                    elif effect == "dmg_boost_120":
                                        damage_boost_timer = 120.0
                                        set_status(f"Used {_slot_item['name']}. +35% damage for 120s!", 2.0)
                                    elif effect == "speed_boost_60":
                                        speed_boost_timer = 60.0
                                        set_status(f"Used {_slot_item['name']}. +28% speed for 60s!", 2.0)
                                    elif effect == "town_portal":
                                        if not use_town_portal_scroll():
                                            item_inventory[idx] = _slot_item
                                    else:
                                        item_inventory[idx] = _slot_item
                                        set_status("That slot has a non-usable item.", 0.9)
                            elif _slot_item is None:
                                set_status("No potion in that slot.", 0.8)
                            _used_pot = True
                            break
                    if _used_pot:
                        continue

                # Right-click on potion bar → drag the potion out
                if event.button == 3 and drag_item is None:
                    for idx, rect in potion_slot_rects.items():
                        if rect.collidepoint(event.pos) and idx < len(item_inventory):
                            begin_drag_from_potion_bar(idx)
                            break

                if show_character and event.button == 1:
                    if drag_item is None:
                        picked = False
                        for slot, rect in character_slot_rects.items():
                            if rect.collidepoint(event.pos):
                                picked = begin_drag_from_equip(slot)
                                break
                    continue

                if show_skill_tree and event.button == 1:
                    for node_id, rect in skill_node_rects.items():
                        if rect.collidepoint(event.pos):
                            success, new_points, message = try_unlock_skill(node_id, active_skill_tree, unlocked_skills, skill_points)
                            skill_points = new_points
                            set_status(message, 1.5 if success else 1.2)
                            break
                    continue

                if show_skill_tree:
                    continue

                # Inventory overlay click
                if show_crafting:
                    if event.button == 1:
                        for tab_name, tab_rect in inv_tab_rects.items():
                            if tab_rect.collidepoint(event.pos):
                                inv_tab = tab_name
                                break
                        else:
                            if inv_tab == "Craft":
                                for rid, rect in crafting_rects.items():
                                    if rect.collidepoint(event.pos):
                                        crafting_selected = rid
                                        break
                    if inv_tab == "Backpack" and event.button == 1:
                        # Drag start from backpack
                        for slot_idx2, slot_rect2 in backpack_slot_rects.items():
                            if slot_rect2.collidepoint(event.pos) and slot_idx2 < len(backpack_inventory):
                                begin_drag_from_backpack(slot_idx2)
                                break
                    if inv_tab == "Backpack" and event.button == 3:
                        # Right click use/equip
                        for slot_idx2, slot_rect2 in backpack_slot_rects.items():
                            if not slot_rect2.collidepoint(event.pos) or slot_idx2 >= len(backpack_inventory):
                                continue
                            item2 = backpack_inventory[slot_idx2]
                            item_type2 = str(item2.get("item_type", "")).strip().lower()
                            eff2 = str(item2.get("effect", "")).strip().lower()
                            if item_type2 == "equipment":
                                # Try equip
                                target_slot = str(item2.get("equip_slot", ""))
                                can_eq, reason = can_item_equip_to_slot(item2, target_slot, selected_class)
                                if can_eq:
                                    swapped = equipped_items.get(target_slot)
                                    equipped_items[target_slot] = item2
                                    backpack_inventory[slot_idx2] = swapped if swapped else None
                                    if backpack_inventory[slot_idx2] is None:
                                        backpack_inventory.pop(slot_idx2)
                                    set_status(f"Equipped {item2.get('name', 'item')}.", 1.2)
                                    update_equip_slot_quests()
                                    refresh_palette_swap()
                                else:
                                    set_status(reason, 1.0)
                                break
                            else:
                                # Try use
                                used = False
                                eff_hp_max2 = player_max_hp + bonus_max_hp
                                if eff2 == "hp_80":
                                    player_hp = min(eff_hp_max2, player_hp + 80.0)
                                    set_status(f"Used {item2['name']}. +80 HP.", 1.6)
                                    used = True
                                elif eff2 == "hp_60":
                                    player_hp = min(eff_hp_max2, player_hp + 60.0)
                                    set_status(f"Used {item2['name']}. +60 HP.", 1.6)
                                    used = True
                                elif eff2 == "hp_25":
                                    player_hp = min(eff_hp_max2, player_hp + 25.0)
                                    set_status(f"Used {item2['name']}. +25 HP.", 1.6)
                                    used = True
                                elif eff2 == "mp_80":
                                    player_mana = min(player_max_mana, player_mana + 80.0)
                                    set_status(f"Used {item2['name']}. +80 MP.", 1.6)
                                    used = True
                                elif eff2 == "mp_full":
                                    player_mana = player_max_mana
                                    set_status(f"Used {item2['name']}. Mana restored.", 1.6)
                                    used = True
                                elif eff2 == "full_restore":
                                    player_hp = eff_hp_max2
                                    player_mana = player_max_mana
                                    set_status(f"Used {item2['name']}. HP and Mana fully restored!", 2.0)
                                    used = True
                                elif eff2 == "dmg_boost":
                                    damage_boost_timer = 90.0
                                    set_status(f"Used {item2['name']}. +20% damage for 90s!", 2.0)
                                    used = True
                                elif eff2 == "dmg_boost_120":
                                    damage_boost_timer = 120.0
                                    set_status(f"Used {item2['name']}. +35% damage for 120s!", 2.0)
                                    used = True
                                elif eff2 == "speed_boost_60":
                                    speed_boost_timer = 60.0
                                    set_status(f"Used {item2['name']}. +28% speed for 60s!", 2.0)
                                    used = True
                                elif eff2 == "town_portal":
                                    used = use_town_portal_scroll()
                                elif eff2 == "teleport_book":
                                    teleport_menu_open = True
                                    used = False
                                if used:
                                    if not item2.get("permanent", False):
                                        backpack_inventory.pop(slot_idx2)
                                break

                if show_professions and event.button == 1:
                    for pid, rect in profession_tab_rects.items():
                        if rect.collidepoint(event.pos):
                            selected_profession = pid
                            crafting_selected = None
                            break
                    else:
                        for rid, rect in crafting_rects.items():
                            if rect.collidepoint(event.pos):
                                crafting_selected = rid
                                break
                        if profession_craft_rect.collidepoint(event.pos):
                            try_craft_selected_recipe()
                    continue

                if show_professions:
                    continue

                # Quest log overlay click
                if show_quest_log and event.button == 1:
                    # Complete Quest button click
                    _cpl_btn = quest_rects.get("__complete_btn__")
                    if _cpl_btn and _cpl_btn.collidepoint(event.pos) and quest_selected:
                        if not quest_actions_from_vendor or current_level != "town":
                            set_status("Turn in quests at town vendors/NPCs.", 1.4)
                            continue
                        sel_role = quest_giver_role_for_id(quest_selected).strip().lower()
                        if quest_vendor_role and sel_role != str(quest_vendor_role).strip().lower():
                            set_status("That quest belongs to another vendor.", 1.4)
                            continue
                        if quest_states.get(quest_selected) == "complete":
                            qdef = next((q for q in QUEST_DEFINITIONS if q["id"] == quest_selected), None)
                            if qdef:
                                rew = qdef["rewards"]
                                player_gold   += rew.get("gold", 0)
                                skill_points  += rew.get("sp", 0)
                                if rew.get("item"):
                                    add_item_to_inventory(dict(rew["item"]), prefer_hotbar=False)
                                quest_states[quest_selected] = "turned_in"
                                update_gold_accumulate_quests()
                                set_status(f"Turned in: {qdef['title']}! +{rew.get('gold',0)}g +{rew.get('sp',0)} SP.", 2.4)
                                if qdef.get("chain_next"):
                                    quest_states[qdef["chain_next"]] = "available"
                                refresh_quest_availability()
                                quest_selected = None
                                audio.play_sfx("quest_complete", cooldown_ms=100)
                        else:
                            set_status("Turn in quests at town vendors/NPCs.", 1.4)
                        continue
                    for qid, rect in quest_rects.items():
                        if qid == "__complete_btn__":
                            continue
                        if rect.collidepoint(event.pos):
                            quest_selected = qid
                            break
                    continue

                if show_quest_log:
                    continue

                # NPC menu click
                if npc_menu_mode in ("menu", "chat") and event.button == 1:
                    picked_option = False
                    for opt_id, opt_rect in npc_option_rects.items():
                        if opt_rect.collidepoint(event.pos):
                            picked_option = True
                            if active_vendor_idx is not None and 0 <= active_vendor_idx < len(vendors):
                                vnm2 = vendors[active_vendor_idx]
                                rnm2 = str(vnm2.get("role", ""))
                                if opt_id == "talk":
                                    sync_dialogue_data(save=True)
                                    d_def = get_dialogue_for_npc(rnm2)
                                    if d_def:
                                        active_dialogue = DialogueSession(d_def, character_data, {})
                                        npc_menu_mode = "dialogue"
                                    else:
                                        npc_menu_mode = "chat"
                                    audio.play_sfx("ui_open", cooldown_ms=70)
                                elif opt_id == "shop":
                                    shop_open = rnm2
                                    npc_menu_mode = "shop"
                                elif opt_id == "craft":
                                    show_crafting = True
                                    inv_tab = "Craft"
                                    npc_menu_mode = ""
                                elif opt_id == "profession":
                                    show_professions = True
                                    selected_profession = str(vnm2.get("profession_id", selected_profession))
                                    npc_menu_mode = ""
                                    audio.play_sfx("ui_open", cooldown_ms=70)
                                elif opt_id == "quests":
                                    show_quest_log = True
                                    quest_actions_from_vendor = current_level == "town"
                                    quest_vendor_role = rnm2 if quest_actions_from_vendor else None
                                    npc_menu_mode = ""
                                    audio.play_sfx("ui_open", cooldown_ms=70)
                            break
                elif npc_menu_mode == "dialogue" and active_dialogue:
                    for opt_id, opt_rect in npc_option_rects.items():
                        if opt_id.startswith("choice_") and opt_rect.collidepoint(event.pos):
                            idx = int(opt_id.split("_")[1])
                            cont, msg = active_dialogue.select_choice(idx)
                            if msg: set_status(msg, 1.5)
                            sync_dialogue_data(save=False)
                            if not cont or not active_dialogue.get_current_node():
                                npc_menu_mode = "menu"
                                active_dialogue = None
                            audio.play_sfx("ui_open", cooldown_ms=50)
                            picked_option = True
                            break

                    if picked_option:
                        if npc_menu_mode in ("menu", "chat", "dialogue"):
                            continue
                    else:
                        # Ground click closes dialog/menu and allows movement click-through.
                        npc_menu_mode = ""
                        active_vendor_line = ""

                if npc_menu_mode in ("menu", "chat", "dialogue"):
                    # While still open, block gameplay clicks underneath.
                    if event.button == 1:
                        continue

                if npc_menu_mode != "":
                    continue

                if event.button == 1 and current_level == "wilderness":
                    handled_loot_ui = False
                    for win in reversed(open_loot_windows):
                        pile_id = int(win.get("pile_id", -1))
                        panel_rect = loot_window_rects.get(pile_id)
                        if panel_rect is None:
                            continue

                        close_rect = loot_close_rects.get(pile_id)
                        if close_rect is not None and close_rect.collidepoint(event.pos):
                            close_loot_window(pile_id)
                            handled_loot_ui = True
                            break

                        take_all_rect = loot_take_all_rects.get(pile_id)
                        if take_all_rect is not None and take_all_rect.collidepoint(event.pos):
                            take_all_loot(pile_id)
                            handled_loot_ui = True
                            break

                        entry_hit = False
                        for (entry_pid, entry_kind, entry_key), entry_rect in list(loot_entry_rects.items()):
                            if entry_pid != pile_id:
                                continue
                            if not entry_rect.collidepoint(event.pos):
                                continue
                            take_loot_entry(pile_id, entry_kind, entry_key)
                            handled_loot_ui = True
                            entry_hit = True
                            break
                        if entry_hit:
                            break

                        if panel_rect.collidepoint(event.pos):
                            focus_loot_window(pile_id)
                            handled_loot_ui = True
                            break

                    if handled_loot_ui:
                        continue

                world_click = Vector2(event.pos[0] + camera.x, event.pos[1] + camera.y)

                # ── Block combat/movement input while feared ──
                if _player_feared and current_level in ("wilderness", "ice_biome"):
                    continue

                if event.button == 2:
                    facing = 1 if world_click.x >= player_pos.x else -1
                    try_basic_attack(world_click)
                    continue

                if (
                    event.button == 3
                    and not show_skill_tree
                    and not show_character
                    and not show_crafting
                    and not show_quest_log
                    and not show_professions
                ):
                    facing = 1 if world_click.x >= player_pos.x else -1
                    try_basic_attack(world_click)
                    continue

                if event.button != 1:
                    continue

                # ── Universal delete mode — click to remove anything ──
                if universal_delete_mode:
                    _del_done = False
                    # 1) Vendor
                    if current_level == "town" and not _del_done:
                        _dv = pick_vendor(world_click)
                        if _dv is not None:
                            _dv_name = str(vendors[_dv].get("name", "vendor"))
                            vendors.pop(_dv)
                            if active_vendor_idx is not None and active_vendor_idx >= _dv:
                                active_vendor_idx = None
                                npc_menu_mode = ""
                            set_status(f"Deleted vendor: {_dv_name}", 1.5)
                            _del_done = True
                    # 2) Enemy mob (wolf / ice wolf)
                    if not _del_done:
                        _del_enemies = active_enemies()
                        _best_ei = None; _best_ed = 60.0
                        for _ei, _ew in enumerate(_del_enemies):
                            _ed = world_click.distance_to(Vector2(_ew["pos"]))
                            if _ed < _best_ed:
                                _best_ed = _ed; _best_ei = _ei
                        if _best_ei is not None:
                            _ew_name = str(_del_enemies[_best_ei].get("kind", "enemy"))
                            _del_enemies.pop(_best_ei)
                            set_status(f"Deleted enemy: {_ew_name}", 1.5)
                            _del_done = True
                    # 3) Farm animal
                    if not _del_done and current_level == "town":
                        _best_fi = None; _best_fd = 60.0
                        for _fi, _fa in enumerate(farm_animals):
                            _fd = world_click.distance_to(Vector2(_fa["pos"]))
                            if _fd < _best_fd:
                                _best_fd = _fd; _best_fi = _fi
                        if _best_fi is not None:
                            _fa_name = str(farm_animals[_best_fi].get("kind", "animal"))
                            farm_animals.pop(_best_fi)
                            set_status(f"Deleted animal: {_fa_name}", 1.5)
                            _del_done = True
                    # 4) Passive animal
                    if not _del_done:
                        _del_passives = active_passives()
                        _best_pi = None; _best_pd = 60.0
                        for _pi, _pa in enumerate(_del_passives):
                            _pd = world_click.distance_to(Vector2(_pa["pos"]))
                            if _pd < _best_pd:
                                _best_pd = _pd; _best_pi = _pi
                        if _best_pi is not None:
                            _pa_name = str(_del_passives[_best_pi].get("kind", "animal"))
                            _del_passives.pop(_best_pi)
                            set_status(f"Deleted passive: {_pa_name}", 1.5)
                            _del_done = True
                    # 5) House overlay
                    if not _del_done and current_level == "town":
                        for _hi, _ho_entry in enumerate(town_house_overlays):
                            _ho_vis = _ho_entry[1]
                            if _ho_vis.collidepoint(world_click.x, world_click.y):
                                _ho_tag = _ho_entry[3] if len(_ho_entry) > 3 else "house"
                                town_house_overlays.pop(_hi)
                                set_status(f"Deleted: {_ho_tag}", 1.5)
                                _del_done = True
                                break
                    # 6) Hardcoded prop (town props registry)
                    if not _del_done and current_level == "town":
                        if remove_hardcoded_prop(world_click):
                            _del_done = True
                    # 7) Level decor asset
                    if not _del_done:
                        if remove_level_decor(world_click):
                            _del_done = True
                    # 8) Loot pile
                    if not _del_done:
                        _best_li = None; _best_ld = 60.0
                        for _li, _lp in enumerate(loot_piles):
                            _ld = world_click.distance_to(Vector2(_lp["pos"]))
                            if _ld < _best_ld:
                                _best_ld = _ld; _best_li = _li
                        if _best_li is not None:
                            loot_piles.pop(_best_li)
                            set_status("Deleted loot pile", 1.5)
                            _del_done = True
                    if not _del_done:
                        set_status("Nothing to delete here", 1.0)
                    continue

                if current_level in ("wilderness", "ice_biome"):
                    clicked_pile_id = pick_loot_pile(world_click)
                    if clicked_pile_id is not None:
                        open_loot_window(clicked_pile_id, anchor_screen=event.pos)
                        continue

                facing = 1 if world_click.x >= player_pos.x else -1
                # ── Click gate → enter wilderness ──
                if current_level == "town" and world_click.distance_to(town_gate_pos) <= gate_trigger_radius + 30:
                    current_level = "wilderness"
                    ratio_x = player_pos.x / float(WORLD_WIDTH)
                    new_x = ratio_x * WILDERNESS_WIDTH
                    player_pos = nearest_walkable(
                        Vector2(new_x, HORIZON_Y + 200),
                        wilderness_walk_bounds, wilderness_obstacles, PLAYER_COLLISION_RADIUS)
                    player_target = Vector2(player_pos)
                    player_path = []
                    snap_camera_to_player()
                    active_vendor_idx = None
                    pending_vendor_idx = None
                    active_vendor_line = ""
                    shop_open = None
                    npc_menu_mode = ""
                    quest_actions_from_vendor = False
                    quest_vendor_role = None
                    level_banner = "The Wilderness"
                    level_banner_timer = 2.8
                    audio.ensure_level_theme(current_level, force=True)
                    portal_cooldown = 0.3
                    update_visit_level_quests("wilderness")
                    continue
                if current_level == "town":
                    vendor_idx = pick_vendor(world_click)
                    if vendor_idx is not None:
                        vendor = vendors[vendor_idx]
                        vendor_pos = vendor["pos"]
                        if player_pos.distance_to(vendor_pos) <= 124:
                            active_vendor_idx = vendor_idx
                            line_choices = vendor["lines"]
                            if isinstance(line_choices, list) and line_choices:
                                vendor["line"] = random.choice(line_choices)
                            active_vendor_line = f"{vendor['job']}. {vendor['line']}"
                            vendor["wait"] = 1.4
                            pending_vendor_idx = None
                            active_dialogue = None
                            npc_menu_mode = "menu"
                            shop_open = None
                        else:
                            approach_x = vendor_pos.x + (-76 if player_pos.x < vendor_pos.x else 76)
                            request_player_path(Vector2(approach_x, vendor_pos.y + 6), ignore_vendor_idx=vendor_idx)
                            pending_vendor_idx = vendor_idx
                            active_vendor_idx = None
                            active_vendor_line = ""
                    else:
                        request_player_path(world_click)
                        pending_vendor_idx = None
                        active_vendor_idx = None
                        active_vendor_line = ""
                else:
                    wolf_idx = pick_wolf(world_click)
                    _enemy_list = active_enemies()
                    if wolf_idx is not None and 0 <= wolf_idx < len(_enemy_list):
                        selected_wolf_id = id(_enemy_list[wolf_idx])
                        audio.play_sfx("target_lock", cooldown_ms=80)
                        pending_vendor_idx = None
                        active_vendor_idx = None
                        active_vendor_line = ""
                        continue
                    request_player_path(world_click)
                    pending_vendor_idx = None
                    active_vendor_idx = None
                    active_vendor_line = ""

        if show_level_decor_editor:
            pressed = pygame.key.get_pressed()
            pan_direction = Vector2(0.0, 0.0)
            if not decor_search_active and (pressed[pygame.K_LEFT] or pressed[pygame.K_a]):
                pan_direction.x -= 1.0
            if not decor_search_active and (pressed[pygame.K_RIGHT] or pressed[pygame.K_d]):
                pan_direction.x += 1.0
            if not decor_search_active and (pressed[pygame.K_UP] or pressed[pygame.K_w]):
                pan_direction.y -= 1.0
            if not decor_search_active and (pressed[pygame.K_DOWN] or pressed[pygame.K_s]):
                pan_direction.y += 1.0
            if pan_direction.length_squared() > 0.0:
                pan_direction = pan_direction.normalize() * (620.0 * dt)
                decor_editor_camera += pan_direction
            editor_world_w = WILDERNESS_WIDTH if current_level == "wilderness" else WORLD_WIDTH
            editor_world_h = WILDERNESS_HEIGHT if current_level == "wilderness" else WORLD_HEIGHT
            decor_editor_camera.x = clamp(decor_editor_camera.x, 0.0, max(0.0, float(editor_world_w - SCREEN_WIDTH)))
            decor_editor_camera.y = clamp(decor_editor_camera.y, 0.0, max(0.0, float(editor_world_h - SCREEN_HEIGHT)))
            camera = Vector2(decor_editor_camera)

        # ── Fear override — forced flee from nearest wolf ──
        if _player_feared and current_level in ("wilderness", "ice_biome"):
            player_path = []
            _enemies = active_enemies()
            _nearest_wolf_pos = None
            _nearest_dist = float("inf")
            for _fw in _enemies:
                _fwp = _fw.get("pos")
                if _fwp is None:
                    continue
                _fd = player_pos.distance_to(Vector2(_fwp))
                if _fd < _nearest_dist:
                    _nearest_dist = _fd
                    _nearest_wolf_pos = Vector2(_fwp)
            if _nearest_wolf_pos is not None:
                _flee_dir = player_pos - _nearest_wolf_pos
                if _flee_dir.length_squared() < 1.0:
                    _flee_dir = Vector2(random.uniform(-1, 1), random.uniform(-1, 1))
                _flee_dir = _flee_dir.normalize()
                player_target = player_pos + _flee_dir * 200.0
            else:
                player_target = Vector2(player_pos)
        elif player_path:
            while player_path and player_pos.distance_to(Vector2(player_path[0])) <= 10.0:
                player_path.pop(0)
            if player_path:
                player_target = Vector2(player_path[0])
            else:
                player_target = Vector2(player_pos)

        to_target = player_target - player_pos
        distance = to_target.length()
        moving = distance > 1.5 and world_dt > 0.0
        audio.update_footsteps(world_dt, moving, current_level, sprinting=(speed_boost_timer > 0.0))
        ultimate_move_mult = 1.0
        if active_ultimates:
            for ultimate in active_ultimates:
                if ultimate.finished:
                    continue
                try:
                    ultimate_move_mult = min(ultimate_move_mult, float(getattr(ultimate, "movement_mult", 1.0)))
                except (TypeError, ValueError):
                    continue

        if moving:
            player_anim_direction = cardinal_anim_direction(to_target, player_anim_direction)
            _fear_speed_mult = 1.4 if _player_feared else 1.0
            effective_speed = speed * passive_move_speed_mult * weather_system.get_speed_multiplier(current_level) * (1.28 if speed_boost_timer > 0.0 else 1.0) * ultimate_move_mult * _fear_speed_mult
            step = min(distance, effective_speed * world_dt)
            dyn_obs = dynamic_collision_obstacles()
            candidate = move_with_collision(
                player_pos,
                player_target,
                step,
                active_bounds(),
                active_obstacles(),
                PLAYER_COLLISION_RADIUS,
                extra_obstacles=dyn_obs
            )
            if candidate.distance_to(player_pos) > 0.01:
                player_pos = candidate
            else:
                if player_path:
                    player_path = player_path[1:]
                    if player_path:
                        player_target = Vector2(player_path[0])
                    else:
                        player_target = Vector2(player_pos)
                else:
                    player_target = Vector2(player_pos)

        # ── POI Discovery System update ──
        if moving and current_level == "town":
            poi_move_timer += world_dt
        if poi_active:
            poi_display_timer -= dt
            # Fade in/out
            if poi_display_timer > poi_display_duration - 0.5:
                poi_fade_alpha = min(255.0, poi_fade_alpha + dt * 510.0)
            elif poi_display_timer < 1.0:
                poi_fade_alpha = max(0.0, poi_fade_alpha - dt * 255.0)
            else:
                poi_fade_alpha = 255.0
            if poi_display_timer <= 0.0:
                poi_active = False
                poi_fade_alpha = 0.0
        elif poi_move_timer >= poi_next_trigger and current_level == "town":
            # Find nearest un-shown POI within 2500px
            _best_poi = None
            _best_dist = 2500.0
            for _p in _poi_registry:
                if _p["key"] in poi_visited_set:
                    continue
                if str(_p.get("level", "town")) != current_level:
                    continue
                _pd = player_pos.distance_to(_p["pos"])
                if _pd < _best_dist:
                    _best_dist = _pd
                    _best_poi = _p
            if _best_poi is None:
                # All shown — reset the visited set so they cycle again
                poi_visited_set.clear()
                for _p in _poi_registry:
                    if str(_p.get("level", "town")) != current_level:
                        continue
                    _pd = player_pos.distance_to(_p["pos"])
                    if _pd < _best_dist:
                        _best_dist = _pd
                        _best_poi = _p
            if _best_poi is not None:
                poi_name = str(_best_poi["name"])
                poi_desc = str(_best_poi["desc"])
                poi_world_pos = Vector2(_best_poi["pos"])
                poi_visited_set.add(_best_poi["key"])
                poi_active = True
                poi_display_timer = poi_display_duration
                poi_fade_alpha = 0.0
            poi_move_timer = 0.0
            poi_next_trigger = random.uniform(15.0, 30.0)

        # ── Seamless level transitions ──
        if portal_cooldown <= 0.0 and moving:
            if current_level == "town" and player_pos.y >= WORLD_HEIGHT - 120:
                # Walk south through the town gate → enter wilderness from the north
                current_level = "wilderness"
                ratio_x = player_pos.x / float(WORLD_WIDTH)
                new_x = ratio_x * WILDERNESS_WIDTH
                player_pos = nearest_walkable(
                    Vector2(new_x, HORIZON_Y + 200),
                    wilderness_walk_bounds, wilderness_obstacles, PLAYER_COLLISION_RADIUS)
                player_target = Vector2(player_pos)
                player_path = []
                snap_camera_to_player()
                active_vendor_idx = None
                pending_vendor_idx = None
                active_vendor_line = ""
                shop_open = None
                npc_menu_mode = ""
                quest_actions_from_vendor = False
                quest_vendor_role = None
                level_banner = "The Wilderness"
                level_banner_timer = 2.8
                audio.ensure_level_theme(current_level, force=True)
                portal_cooldown = 0.3
                update_visit_level_quests("wilderness")
            elif current_level == "wilderness" and player_pos.y <= HORIZON_Y + 140:
                # Walk north in wilderness → return to town through the gate
                current_level = "town"
                ratio_x = player_pos.x / float(WILDERNESS_WIDTH)
                new_x = ratio_x * WORLD_WIDTH
                player_pos = nearest_walkable(
                    Vector2(new_x, WORLD_HEIGHT - 160),
                    town_walk_bounds, town_obstacles, PLAYER_COLLISION_RADIUS)
                player_pos = keep_player_out_of_blacksmith_shop(player_pos, vendors, town_walk_bounds, town_obstacles)
                player_target = Vector2(player_pos)
                player_path = []
                snap_camera_to_player()
                level_banner = "Sangeroasa"
                level_banner_timer = 2.6
                audio.ensure_level_theme(current_level, force=True)
                portal_cooldown = 0.3
                persist_progress()

        if world_dt > 0.0 and active_ultimates:
            ultimate_ctx = build_ultimate_context()
            for ultimate in active_ultimates:
                if ultimate.finished:
                    for emitter in ultimate.emitters:
                        emitter.update(world_dt)
                    continue
                ultimate.update(world_dt, ultimate_ctx)
            active_ultimates[:] = [ultimate for ultimate in active_ultimates if ultimate.is_alive()]
        elif active_ultimates:
            active_ultimates[:] = [ultimate for ultimate in active_ultimates if ultimate.is_alive()]

        status_effects.update(
            world_dt,
            active_enemies(),
            damage_numbers=damage_numbers,
            spell_effects=spell_effects,
        )
        spell_blockers = spell_collision_obstacles(spell_effects)
        combined_obstacles = active_obstacles() + spell_blockers

        if current_level == "town":
            if active_vendor_idx is not None and 0 <= active_vendor_idx < len(vendors):
                if player_pos.distance_to(vendors[active_vendor_idx]["pos"]) > 168:
                    active_vendor_idx = None
                    active_vendor_line = ""
                    shop_open = None
                    npc_menu_mode = ""

            if pending_vendor_idx is not None and 0 <= pending_vendor_idx < len(vendors):
                vendor_pos = vendors[pending_vendor_idx]["pos"]
                if player_pos.distance_to(vendor_pos) <= 124:
                    active_vendor_idx = pending_vendor_idx
                    line_choices = vendors[pending_vendor_idx]["lines"]
                    if isinstance(line_choices, list) and line_choices:
                        vendors[pending_vendor_idx]["line"] = random.choice(line_choices)
                    active_vendor_line = f"{vendors[pending_vendor_idx]['job']}. {vendors[pending_vendor_idx]['line']}"
                    vendors[pending_vendor_idx]["wait"] = 1.4
                    _talk_role = str(vendors[pending_vendor_idx].get("role", ""))
                    pending_vendor_idx = None
                    active_dialogue = None
                    npc_menu_mode = "menu"
                    shop_open = None
                    if _talk_role:
                        update_talk_to_quests(_talk_role)
                elif not moving or player_target.distance_to(vendor_pos) > 170:
                    approach_x = vendor_pos.x + (-76 if player_pos.x < vendor_pos.x else 76)
                    request_player_path(Vector2(approach_x, vendor_pos.y + 6), ignore_vendor_idx=pending_vendor_idx)

            update_vendors(vendors, world_dt, town_walk_bounds, combined_obstacles, active_vendor_idx)
            update_farm_animals(farm_animals, world_dt)
        else:
            active_vendor_idx = None
            pending_vendor_idx = None
            active_vendor_line = ""
            update_passive_animals(
                active_passives(),
                world_dt,
                player_pos,
                active_bounds(),
                combined_obstacles,
                predators=active_enemies(),
            )
            update_wolves(
                active_enemies(),
                world_dt,
                player_pos,
                active_bounds(),
                combined_obstacles,
                passive_animals=active_passives(),
            )
            if world_dt > 0.0:
                incoming = 0.0
                passive_by_id: Dict[int, Dict[str, object]] = {
                    id(animal): animal
                    for animal in active_passives()
                    if float(animal.get("hp", 0.0)) > 0.0 and isinstance(animal.get("pos"), Vector2)
                }
                for wolf in active_enemies():
                    if bool(wolf.get("status_disabled", False)):
                        wolf["queued_strike"] = False
                        continue
                    wpos = wolf.get("pos")
                    if not isinstance(wpos, Vector2):
                        continue
                    if not bool(wolf.pop("queued_strike", False)):
                        continue
                    target_type = str(
                        wolf.pop("queued_target_type", wolf.get("attack_target_type", "player"))
                    ).lower()
                    target_raw = wolf.pop("queued_target_id", wolf.get("attack_target_id", 0))
                    target_id = int(target_raw) if isinstance(target_raw, (int, float)) else 0
                    reach = 66.0 + float(wolf.get("radius", WOLF_COLLISION_RADIUS)) * 0.35
                    atk_min = float(wolf.get("attack_min", 7.0))
                    atk_max = float(wolf.get("attack_max", atk_min + 4.0))
                    if atk_max < atk_min:
                        atk_max = atk_min
                    if target_type == "passive" and target_id != 0:
                        prey = passive_by_id.get(target_id)
                        if isinstance(prey, dict) and float(prey.get("hp", 0.0)) > 0.0:
                            ppos = prey.get("pos")
                            if isinstance(ppos, Vector2):
                                prey_radius = max(8.0, float(prey.get("radius", 12.0)))
                                prey_reach = reach + prey_radius * 0.35
                                if wpos.distance_to(ppos) <= prey_reach:
                                    dmg = random.uniform(atk_min, atk_max) * 0.88
                                    hp_before = float(prey.get("hp", 0.0))
                                    hp_after = max(0.0, hp_before - dmg)
                                    prey["hp"] = hp_after
                                    prey["flee_timer"] = max(float(prey.get("flee_timer", 0.0)), 3.5)
                                    prey["wait"] = 0.0
                                    prey["last_hit_by_predator"] = True
                                    flee_vec = ppos - wpos
                                    if flee_vec.length_squared() > 1e-5:
                                        prey["wander_target"] = ppos + flee_vec.normalize() * 210.0
                                    spawn_damage_number(
                                        damage_numbers,
                                        Vector2(ppos.x + random.uniform(-7.0, 7.0), ppos.y - random.uniform(8.0, 18.0)),
                                        dmg,
                                        kind="outgoing",
                                    )
                                    spawn_particle_burst(
                                        spell_effects,
                                        Vector2(ppos.x, ppos.y - 8.0),
                                        (196, 88, 74),
                                        (124, 42, 32),
                                        count=5,
                                        speed_min=60.0,
                                        speed_max=180.0,
                                        life_min=0.10,
                                        life_max=0.24,
                                        size_start=3.2,
                                        size_end=0.7,
                                        spread=1.0,
                                        direction=flee_vec if flee_vec.length_squared() > 1e-5 else Vector2(1, 0),
                                        gravity=22.0,
                                        drag=1.6,
                                        vfx_scale=0.9,
                                    )
                                    wolf["attack_cd"] = max(0.70, 1.10 - float(wolf.get("level", 1)) * 0.024)
                                    wolf["hunt_cooldown"] = max(float(wolf.get("hunt_cooldown", 0.0)), 2.2)
                                    if hp_after <= 0.0:
                                        wolf["satiety"] = min(24.0, float(wolf.get("satiety", 12.0)) + 10.0 + float(prey.get("max_hp", 22.0)) * 0.12)
                                        wolf["prey_target_id"] = 0
                                        wolf["hunt_scan_timer"] = 1.8 + random.random() * 2.2
                                    else:
                                        wolf["satiety"] = min(24.0, float(wolf.get("satiety", 12.0)) + 1.6 + dmg * 0.02)
                        else:
                            wolf["prey_target_id"] = 0
                        wolf["attack_cd"] = max(float(wolf.get("attack_cd", 0.0)), 0.32)
                        continue

                    if wpos.distance_to(player_pos) > reach:
                        continue
                    dmg = random.uniform(atk_min, atk_max)
                    incoming += dmg
                    hit_pos = Vector2(player_pos.x + random.uniform(-8.0, 8.0), player_pos.y - random.uniform(10.0, 22.0))
                    spawn_damage_number(damage_numbers, hit_pos, dmg, kind="incoming")
                    strike_dir = player_pos - wpos
                    if strike_dir.length_squared() > 1e-5:
                        strike_dir = strike_dir.normalize()
                    else:
                        strike_dir = Vector2(1.0 if int(wolf.get("facing", 1)) >= 0 else -1.0, 0.0)
                    spawn_particle_burst(
                        spell_effects,
                        Vector2(player_pos.x, player_pos.y - 16.0),
                        (196, 42, 36),
                        (102, 14, 18),
                        count=14,
                        speed_min=120.0,
                        speed_max=300.0,
                        life_min=0.14,
                        life_max=0.34,
                        size_start=4.4,
                        size_end=0.6,
                        spread=1.25,
                        direction=strike_dir,
                        gravity=40.0,
                        drag=1.2,
                        vfx_scale=1.0,
                    )
                    spawn_particle_burst(
                        spell_effects,
                        Vector2(player_pos.x, player_pos.y - 10.0),
                        (140, 20, 24),
                        (60, 6, 10),
                        count=8,
                        speed_min=30.0,
                        speed_max=110.0,
                        life_min=0.55,
                        life_max=1.05,
                        size_start=2.6,
                        size_end=1.2,
                        spread=math.tau,
                        gravity=180.0,
                        drag=0.3,
                        vfx_scale=1.0,
                    )
                    wolf["attack_cd"] = max(0.75, 1.18 - float(wolf.get("level", 1)) * 0.026)
                    # ── Wolf bite applies bleed DoT debuff ──
                    _bite_potency = dmg * 0.18  # 18% of hit as DoT per tick
                    _bite_dur = 4.0 + float(wolf.get("level", 1)) * 0.3
                    status_effects.add_effect(
                        StatusEffectSystem.PLAYER_KEY,
                        StatusEffect("bite", _bite_dur, _bite_potency,
                                     tick_interval=0.6, color=(200, 80, 50)),
                    )
                    # ── Fear howl when wolf is near death (below 20% HP) ──
                    _w_hp = float(wolf.get("hp", 0.0))
                    _w_max = float(wolf.get("max_hp", 1.0))
                    _already_howled = bool(wolf.get("_howled", False))
                    if _w_hp > 0.0 and _w_hp / max(1.0, _w_max) < 0.20 and not _already_howled:
                        wolf["_howled"] = True
                        # Apply fear to player — 2 second forced flee
                        status_effects.add_effect(
                            StatusEffectSystem.PLAYER_KEY,
                            StatusEffect("fear", 2.0, 1.0, color=(160, 60, 200)),
                        )
                        set_status("The wounded wolf lets out a terrifying howl!", 1.5)
                        # Howl particle burst (purple/dark)
                        spawn_particle_burst(
                            spell_effects, Vector2(wpos.x, wpos.y - 20),
                            (160, 60, 200), (100, 30, 140),
                            count=18, speed_min=80.0, speed_max=260.0,
                            life_min=0.3, life_max=0.7,
                            size_start=5.0, size_end=1.0,
                            spread=math.tau, gravity=-20.0, drag=1.2,
                            vfx_scale=1.2,
                        )
                if incoming > 0.0:
                    reduced_incoming = incoming * passive_incoming_damage_mult
                    blocked = status_effects.consume_shield(status_effects.PLAYER_KEY, reduced_incoming)
                    final_incoming = max(0.0, reduced_incoming - blocked)
                    player_hp = max(0.0, player_hp - final_incoming)
                    if final_incoming > 0.0 and player_anim_frames and "hurt" in player_anim_frames:
                        player_hurt_anim_state = "hurt"
                        player_hurt_anim_elapsed = 0.0
                    if final_incoming > 0.0:
                        player_hit_flash_timer = player_hit_flash_duration
                        hit_alpha = int(clamp(34.0 + final_incoming * 2.4, 28.0, 120.0))
                        screen_effects.flash((146, 34, 34), alpha=hit_alpha, duration=0.08)
                        camera_director.impulse(clamp(2.8 + final_incoming * 0.13, 2.6, 9.2), 0.12)
                    if blocked > 0.0:
                        screen_effects.flash((214, 206, 132), alpha=26, duration=0.06)
                    set_status(f"Predators hit you for {int(round(final_incoming))} damage.", 0.9)

        if current_level in ("wilderness", "ice_biome") and world_dt > 0.0 and summoned_skeletons:
            update_summoned_skeletons(
                summoned_skeletons,
                world_dt,
                player_pos,
                active_enemies(),
                active_bounds(),
                active_obstacles(),
                damage_numbers=damage_numbers,
                spell_effects=spell_effects,
            )

        runtime_killed_wolves = 0
        runtime_dead_wolves: List[Dict[str, object]] = []
        if combat_runtime is not None:
            runtime_context = (
                CombatSceneContext(
                    current_level=current_level,
                    enemies=active_enemies(),
                    passive_animals=active_passives() if current_level in ("wilderness", "ice_biome") else [],
                    walk_bounds=active_bounds(),
                    obstacles=combined_obstacles,
                    player_pos=Vector2(player_pos),
                    damage_numbers=damage_numbers,
                    camera_director=camera_director,
                    screen_effects=screen_effects,
                    audio=audio,
                )
                if CombatSceneContext is not None
                else None
            )
            if runtime_context is not None:
                runtime_update = combat_runtime.update(dt, world_dt, runtime_context)
                runtime_killed_wolves = runtime_update.killed_wolves
                runtime_dead_wolves = list(runtime_update.dead_wolves)

        legacy_killed_wolves, legacy_dead_wolves, killed_passives, dead_passives = update_spell_effects(
            spell_effects,
            world_dt,
            active_enemies(),
            active_passives() if current_level in ("wilderness", "ice_biome") else [],
            active_bounds(),
            combined_obstacles,
            player_pos,
            damage_numbers=damage_numbers,
            status_effects=status_effects,
        )
        killed_wolves = legacy_killed_wolves + runtime_killed_wolves
        dead_wolves = list(legacy_dead_wolves) + runtime_dead_wolves
        if killed_wolves > 0:
            wolves_slain += killed_wolves
            skill_points += killed_wolves
            screen_effects.flash((222, 176, 108), alpha=min(88, 24 + killed_wolves * 10), duration=0.09)
            camera_director.impulse(min(6.4, 2.2 + killed_wolves * 0.8), 0.11)
            tier_bonus = (wolves_slain // 10) * 0.05
            rarity_drop_counts: Dict[str, int] = {"common": 0, "rare": 0, "epic": 0, "legendary": 0}
            drop_tier = wolves_slain // 14
            xp_gain = 0
            for dead_entry in dead_wolves:
                pos_raw = dead_entry.get("pos")
                if not isinstance(pos_raw, Vector2):
                    continue
                pos = Vector2(pos_raw)
                wolf_name = str(dead_entry.get("name", "Wolf"))
                wolf_level = max(1, int(dead_entry.get("level", max(1, drop_tier + 1))))
                xp_gain += max(1, int(dead_entry.get("xp_reward", 10 + wolf_level * 4)))
                pile_mats: Dict[str, int] = {}
                pile_gold = random.randint(4, 10)
                for mat_id, mat_data in WOLF_MATERIALS.items():
                    chance = min(0.95, mat_data["drop_chance"] + tier_bonus)
                    if random.random() < chance:
                        pile_mats[mat_id] = random.randint(1, int(mat_data["max_drop"]))
                pile_items: List[Dict[str, object]] = []
                if external_item_library:
                    drop_chance = min(0.82, 0.36 + drop_tier * 0.03)
                    if random.random() <= drop_chance:
                        rolled = roll_external_item(drop_tier)
                        if isinstance(rolled, dict):
                            pile_items.append(rolled)
                            rr = item_rarity(rolled)
                            if rr in rarity_drop_counts:
                                rarity_drop_counts[rr] += 1
                loot_piles.append(
                    {
                        "id": next_loot_pile_id,
                        "source_name": wolf_name,
                        "source_level": wolf_level,
                        "pos": Vector2(pos),
                        "gold": pile_gold,
                        "materials": pile_mats,
                        "items": pile_items,
                        "timer": 80.0,
                        "collected": False,
                        "corpse_kind": "predator",
                        "raised": False,
                    }
                )
                next_loot_pile_id += 1

            level_ups = 0
            if xp_gain > 0:
                player_xp += float(xp_gain)
                while player_xp >= player_xp_next:
                    player_xp -= player_xp_next
                    player_level += 1
                    level_ups += 1
                    hp_gain = 9.0 + (player_level // 3)
                    mana_gain = 6.0 + (player_level // 4)
                    player_max_hp += hp_gain
                    player_max_mana += mana_gain
                    mana_regen += 0.14
                    player_hp = min(player_max_hp, player_hp + hp_gain)
                    player_mana = min(player_max_mana, player_mana + mana_gain)
                    skill_points += 1
                    player_xp_next = float(max(1, xp_required_for_level(player_level)))
                if level_ups > 0:
                    refresh_player_visuals()
                    screen_effects.flash((255, 235, 130), alpha=50, duration=0.5)
                    level_up_vfx.trigger(player_level)
                    audio.play_sfx("level_up", cooldown_ms=200)
                    update_reach_level_quests()

            rarity_notes = []
            for rr in ("legendary", "epic", "rare", "common"):
                count_rr = rarity_drop_counts.get(rr, 0)
                if count_rr > 0:
                    rarity_notes.append(f"{count_rr} {rr[:1].upper()}")
            rarity_tail = f"  |  Item drops: {' '.join(rarity_notes)}" if rarity_notes else ""
            xp_tail = f"  |  XP +{xp_gain}" if xp_gain > 0 else ""
            level_tail = f"  |  LEVEL UP! Lv {player_level}" if level_ups > 0 else ""
            set_status(
                f"Defeated {killed_wolves} predator{'s' if killed_wolves > 1 else ''}! +{killed_wolves} SP. Click corpse loot to collect.{xp_tail}{level_tail}{rarity_tail}",
                2.4,
            )
            update_kill_quests(killed_wolves)
            # Track kills by enemy type for kill_type quests
            _kill_type_counts: Dict[str, int] = {}
            for _de in dead_wolves:
                _ename = str(_de.get("name", "Wolf"))
                _kill_type_counts[_ename] = _kill_type_counts.get(_ename, 0) + 1
            for _ename, _ecount in _kill_type_counts.items():
                update_kill_type_quests(_ename, _ecount)
            update_reach_level_quests()

        if killed_passives > 0:
            player_hunted = 0
            predator_hunted = 0
            for dead_animal in dead_passives:
                if bool(dead_animal.get("last_hit_by_predator", False)):
                    predator_hunted += 1
                    continue
                player_hunted += 1
                pos = dead_animal.get("pos")
                if not isinstance(pos, Vector2): continue
                animal_name = str(dead_animal.get("name", "Creature"))
                pile_mats: Dict[str, int] = {}
                material_keys = ANIMAL_MATERIAL_MAP.get(animal_name, [])
                for mat_id in material_keys:
                    mat_data = PASSIVE_ANIMAL_MATERIALS[mat_id]
                    if random.random() < mat_data["drop_chance"]:
                        pile_mats[mat_id] = random.randint(1, int(mat_data["max_drop"]))
                if not pile_mats: continue
                loot_piles.append({
                    "id": next_loot_pile_id,
                    "source_name": animal_name,
                    "source_level": 1,
                    "pos": Vector2(pos),
                    "gold": 0,
                    "materials": pile_mats,
                    "items": [],
                    "timer": 80.0,
                    "collected": False,
                    "corpse_kind": "passive",
                    "raised": False,
                })
                next_loot_pile_id += 1
            if player_hunted > 0:
                set_status(
                    f"Hunted {player_hunted} animal{'s' if player_hunted > 1 else ''}. Click corpse to gather materials.",
                    2.0,
                )
            elif predator_hunted > 0 and random.random() < 0.35:
                set_status("Predators are hunting nearby wildlife.", 1.2)

        if player_hp <= 0.0 and not death_screen_active:
            death_screen_active = True
            death_screen_timer = 0.0
            player_path = []
            player_attack_anim_state = ""
            player_attack_anim_elapsed = 0.0

        wolf_tier = wolves_slain // 10
        if current_level == "wilderness":
            predator_target_count = target_predator_population(wolf_tier)
            if len(wolves) < predator_target_count:
                wolf_respawn_timer += world_dt
                if wolf_respawn_timer >= 10.5:
                    need = max(1, predator_target_count - len(wolves))
                    batch = build_enemies(
                        predator_archetypes,
                        wilderness_spawn_points,
                        wilderness_walk_bounds,
                        wilderness_obstacles,
                        tier=wolf_tier,
                        lpc_wolf_frames=lpc_wolf_frames,
                    )
                    existing_positions = [
                        Vector2(w["pos"])
                        for w in wolves
                        if isinstance(w.get("pos"), Vector2) and float(w.get("hp", 0.0)) > 0.0
                    ]
                    added = 0
                    for predator in batch:
                        ppos = predator.get("pos")
                        if not isinstance(ppos, Vector2):
                            continue
                        if ppos.distance_to(player_pos) < 360.0:
                            continue
                        if any(ppos.distance_to(ep) < 170.0 for ep in existing_positions):
                            continue
                        wolves.append(predator)
                        existing_positions.append(Vector2(ppos))
                        added += 1
                        if added >= min(8, need):
                            break
                    wolf_respawn_timer = 0.0
                    if added > 0 and random.random() < 0.22:
                        tier_note = f" (Tier {wolf_tier + 1})" if wolf_tier > 0 else ""
                        set_status(f"Predators migrate into the biome{tier_note}.", 1.3)
            else:
                wolf_respawn_timer = 0.0
                if len(wolves) > predator_target_count + 6:
                    random.shuffle(wolves)
                    del wolves[predator_target_count:]

            if len(passive_animals) < passive_target_count:
                passive_respawn_timer += world_dt
                if passive_respawn_timer >= 6.8:
                    need = max(1, passive_target_count - len(passive_animals))
                    batch = min(18, need)
                    seed = pygame.time.get_ticks() + random.randint(0, 9999)
                    new_passives = build_passive_animals(
                        prey_archetypes,
                        wilderness_walk_bounds,
                        wilderness_obstacles,
                        count=batch,
                        seed=seed,
                    )
                    existing_positions = [
                        Vector2(a["pos"])
                        for a in passive_animals
                        if isinstance(a.get("pos"), Vector2) and float(a.get("hp", 0.0)) > 0.0
                    ]
                    wolf_positions = [
                        Vector2(w["pos"])
                        for w in wolves
                        if isinstance(w.get("pos"), Vector2) and float(w.get("hp", 0.0)) > 0.0
                    ]
                    added = 0
                    for critter in new_passives:
                        cpos = critter.get("pos")
                        if not isinstance(cpos, Vector2):
                            continue
                        if cpos.distance_to(player_pos) < 260.0:
                            continue
                        if any(cpos.distance_to(ep) < 88.0 for ep in existing_positions):
                            continue
                        if any(cpos.distance_to(wp) < 112.0 for wp in wolf_positions):
                            continue
                        passive_animals.append(critter)
                        existing_positions.append(Vector2(cpos))
                        added += 1
                    passive_respawn_timer = 0.0
                    if added > 0 and random.random() < 0.22:
                        set_status("Wildlife stirs deeper in the forest.", 1.0)
            else:
                passive_respawn_timer = 0.0

        elif current_level == "ice_biome":
            ice_predator_target = target_predator_population(wolf_tier)
            if len(ice_wolves) < ice_predator_target:
                ice_wolf_respawn_timer += world_dt
                if ice_wolf_respawn_timer >= 12.0:
                    need = max(1, ice_predator_target - len(ice_wolves))
                    batch = build_enemies(
                        ice_predators,
                        ice_spawn_points,
                        ice_walk_bounds,
                        ice_obstacles,
                        tier=wolf_tier,
                        lpc_wolf_frames=lpc_wolf_frames,
                    )
                    existing_positions = [
                        Vector2(w["pos"])
                        for w in ice_wolves
                        if isinstance(w.get("pos"), Vector2) and float(w.get("hp", 0.0)) > 0.0
                    ]
                    added = 0
                    for predator in batch:
                        ppos = predator.get("pos")
                        if not isinstance(ppos, Vector2):
                            continue
                        if ppos.distance_to(player_pos) < 360.0:
                            continue
                        if any(ppos.distance_to(ep) < 170.0 for ep in existing_positions):
                            continue
                        ice_wolves.append(predator)
                        existing_positions.append(Vector2(ppos))
                        added += 1
                        if added >= min(8, need):
                            break
                    ice_wolf_respawn_timer = 0.0
                    if added > 0 and random.random() < 0.22:
                        set_status("Arctic predators prowl the tundra.", 1.3)
            else:
                ice_wolf_respawn_timer = 0.0
                if len(ice_wolves) > ice_predator_target + 6:
                    random.shuffle(ice_wolves)
                    del ice_wolves[ice_predator_target:]

            # Ice passive respawn
            if len(ice_passive_animals) < ice_passive_target_count:
                ice_passive_respawn_timer += world_dt
                if ice_passive_respawn_timer >= 8.0:
                    need = max(1, ice_passive_target_count - len(ice_passive_animals))
                    batch_seed = pygame.time.get_ticks() + random.randint(0, 9999)
                    new_ice_passives = build_passive_animals(
                        ice_passives,
                        ice_walk_bounds,
                        ice_obstacles,
                        count=min(12, need),
                        seed=batch_seed,
                    )
                    existing_ice_pos = [
                        Vector2(a["pos"])
                        for a in ice_passive_animals
                        if isinstance(a.get("pos"), Vector2) and float(a.get("hp", 0.0)) > 0.0
                    ]
                    pred_positions = [
                        Vector2(w["pos"])
                        for w in ice_wolves
                        if isinstance(w.get("pos"), Vector2) and float(w.get("hp", 0.0)) > 0.0
                    ]
                    ice_added = 0
                    for critter in new_ice_passives:
                        cpos = critter.get("pos")
                        if not isinstance(cpos, Vector2):
                            continue
                        if cpos.distance_to(player_pos) < 280.0:
                            continue
                        if any(cpos.distance_to(ep) < 88.0 for ep in existing_ice_pos):
                            continue
                        if any(cpos.distance_to(pp) < 130.0 for pp in pred_positions):
                            continue
                        ice_passive_animals.append(critter)
                        existing_ice_pos.append(Vector2(cpos))
                        ice_added += 1
                    ice_passive_respawn_timer = 0.0
                    if ice_added > 0 and random.random() < 0.18:
                        set_status("Tundra wildlife stirs across the plain.", 1.0)
            else:
                ice_passive_respawn_timer = 0.0

        if selected_wolf_id is not None:
            still_exists = False
            for wolf in active_enemies():
                if id(wolf) == selected_wolf_id and float(wolf.get("hp", 0.0)) > 0.0:
                    still_exists = True
                    break
            if not still_exists:
                selected_wolf_id = None

        # Decay corpse loot over time; looting is click-driven via loot windows.
        if current_level in ("wilderness", "ice_biome") and world_dt > 0.0:
            for pile in loot_piles:
                if bool(pile.get("collected", False)):
                    continue
                pile["timer"] = float(pile.get("timer", 0.0)) - world_dt
                if float(pile.get("timer", 0.0)) <= 0.0:
                    pile["collected"] = True
            loot_piles[:] = [p for p in loot_piles if not p["collected"] and float(p["timer"]) > 0.0]
            prune_loot_windows()

        update_damage_numbers(damage_numbers, dt)

        _cam_w = ICE_WIDTH if current_level == "ice_biome" else (WILDERNESS_WIDTH if current_level == "wilderness" else WORLD_WIDTH)
        _cam_h = ICE_HEIGHT if current_level == "ice_biome" else (WILDERNESS_HEIGHT if current_level == "wilderness" else WORLD_HEIGHT)
        if show_level_decor_editor:
            camera = Vector2(decor_editor_camera)
        else:
            camera.x = clamp(player_pos.x - SCREEN_WIDTH * 0.5, 0.0, max(0.0, float(_cam_w - SCREEN_WIDTH)))
            camera.y = clamp(player_pos.y - SCREEN_HEIGHT * 0.62, 0.0, max(0.0, float(_cam_h - SCREEN_HEIGHT)))
            decor_editor_camera = Vector2(camera)

        mouse_pos = pygame.mouse.get_pos()
        mouse_world = Vector2(mouse_pos[0] + camera.x, mouse_pos[1] + camera.y)
        ice_portal_hovered = False
        portal_hovered = False
        _player_behind_house = False
        gate_hovered = (current_level == "town" and mouse_world.distance_to(town_gate_pos) <= gate_trigger_radius)

        if current_level == "town":
            screen.blit(town_surface, (-int(camera.x), -int(camera.y)))
            # ── Animated grass / foliage sway overlay ──
            _anim_ticks = pygame.time.get_ticks()
            _cam_ix, _cam_iy = int(camera.x), int(camera.y)
            _vis_left = _cam_ix - 20
            _vis_right = _cam_ix + SCREEN_WIDTH + 20
            _vis_top = _cam_iy - 20
            _vis_bottom = _cam_iy + SCREEN_HEIGHT + 20
            for _fa_x, _fa_y, _fa_kind, _fa_sz in town_foliage_anim:
                # Frustum cull
                if _fa_x < _vis_left or _fa_x > _vis_right or _fa_y < _vis_top or _fa_y > _vis_bottom:
                    continue
                _sx = _fa_x - _cam_ix
                _sy = _fa_y - _cam_iy
                if _fa_kind == "grass_tuft":
                    # Draw 3-5 swaying grass blades
                    for _bi in range(4):
                        _bx = _sx + _bi * 3 - 4
                        _blade_h = _fa_sz + _bi * 2
                        # Wind sway: sin wave using ticks + position for phase variation
                        _sway = math.sin(_anim_ticks * 0.0015 + _fa_x * 0.02 + _bi * 1.3) * 3.5
                        _sway2 = math.sin(_anim_ticks * 0.0022 + _fa_y * 0.015 + _bi * 0.9) * 1.5
                        _total_sway = _sway + _sway2
                        # Color variation per blade
                        _g_base = 50 + (_bi * 7 + (_fa_x * 3 + _fa_y * 7) % 20)
                        _gc = (max(0, min(255, _g_base - 14)),
                               max(0, min(255, _g_base + 22)),
                               max(0, min(255, _g_base - 22)))
                        _tip_x = _bx + int(_total_sway)
                        _tip_y = _sy - _blade_h
                        _mid_x = _bx + int(_total_sway * 0.4)
                        _mid_y = _sy - _blade_h // 2
                        pygame.draw.line(screen, _gc, (_bx, _sy), (_mid_x, _mid_y), 1)
                        # Lighter tip
                        _tc = (min(255, _gc[0] + 22), min(255, _gc[1] + 18), min(255, _gc[2] + 14))
                        pygame.draw.line(screen, _tc, (_mid_x, _mid_y), (_tip_x, _tip_y), 1)

            # ── House overlays — transparent when player is behind ──
            _px, _py = int(player_pos.x), int(player_pos.y)
            _player_behind_house = False
            _town_house_overlays_fg: List[Tuple[pygame.Surface, int, int, str]] = []
            _p_probe_sprite = get_facing_sprite(facing, player_sprite, player_sprite_left)
            _p_probe_w, _p_probe_h = _p_probe_sprite.get_size()
            # Use multiple probe points (head/chest grid) to avoid false fades when the
            # player is merely near a building edge.
            _p_probe_y_chest = _py - int(_p_probe_h * 0.60)
            _p_probe_y_head = _py - int(_p_probe_h * 0.82)
            _p_probe_x1 = max(6, int(_p_probe_w * 0.18))
            _p_probe_x2 = max(_p_probe_x1 + 4, int(_p_probe_w * 0.32))
            _p_probe_points: List[Tuple[int, int]] = []
            for _yy in (_p_probe_y_chest, _p_probe_y_head):
                for _xo in (0, -_p_probe_x1, _p_probe_x1, -_p_probe_x2, _p_probe_x2):
                    _p_probe_points.append((_px + _xo, _yy))
            _p_upper_rect = pygame.Rect(
                _px - max(6, int(_p_probe_w * 0.28)),
                _py - max(10, int(_p_probe_h * 0.88)),
                max(14, int(_p_probe_w * 0.56)),
                max(16, int(_p_probe_h * 0.56)),
            )
            for _ho_entry in town_house_overlays:
                _ho_surf, _ho_vis, _ho_coll = _ho_entry[0], _ho_entry[1], _ho_entry[2]
                _ho_tag = _ho_entry[3] if len(_ho_entry) > 3 else ""
                _ho_arch_local = _ho_entry[4] if len(_ho_entry) > 4 else None
                # Cull off-screen overlays
                _ho_sx = _ho_vis.x - _cam_ix
                _ho_sy = _ho_vis.y - _cam_iy
                if _ho_sx + _ho_vis.w < 0 or _ho_sx > SCREEN_WIDTH:
                    continue
                if _ho_sy + _ho_vis.h < 0 or _ho_sy > SCREEN_HEIGHT:
                    continue
                # Check if player is visually behind this house (skip church)
                _is_behind = False
                if _ho_tag != "church" and isinstance(_ho_arch_local, pygame.Rect):
                    # Precise check: player must be north of the house base (behind),
                    # and their body must overlap opaque architecture pixels.
                    _base_y = int(_ho_coll.bottom)
                    if _py < _base_y - 2:
                        _arch_world = _ho_arch_local.move(_ho_vis.left, _ho_vis.top)
                        # Broad-phase: avoid triggering from far-away houses on the same column.
                        if _arch_world.colliderect(_p_upper_rect):
                            # Additional gating: require proximity to the footprint width.
                            _x_gate = int(_ho_coll.w * 0.70) + 44
                            if abs(_px - int(_ho_coll.centerx)) <= _x_gate:
                                _hit_count = 0
                                _center_hits = 0
                                _head_hits = 0
                                for _tx, _ty in _p_probe_points:
                                    if not _arch_world.collidepoint(_tx, _ty):
                                        continue
                                    _lx = int(_tx - _ho_vis.left)
                                    _ly = int(_ty - _ho_vis.top)
                                    if 0 <= _lx < _ho_surf.get_width() and 0 <= _ly < _ho_surf.get_height():
                                        if _ho_surf.get_at((_lx, _ly)).a >= 180:
                                            _hit_count += 1
                                            if abs(_tx - _px) <= _p_probe_x1:
                                                _center_hits += 1
                                            if _ty == _p_probe_y_head:
                                                _head_hits += 1
                                            # Accept with a couple of solid hits including head + center.
                                            if _head_hits >= 1 and _center_hits >= 1 and _hit_count >= 2:
                                                _is_behind = True
                                                break
                                            # Or accept with strong overlap even if centered isn't hit.
                                            if _head_hits >= 1 and _hit_count >= 4:
                                                _is_behind = True
                                                break
                if _is_behind:
                    _player_behind_house = True
                    # Draw after actors so it can occlude, but with reduced opacity.
                    _town_house_overlays_fg.append((_ho_surf, _ho_sx, _ho_sy, _ho_tag))
                else:
                    screen.blit(_ho_surf, (_ho_sx, _ho_sy))
            # Draw animated water on top of the static background
            ticks = pygame.time.get_ticks()
            for canal in town_canals:
                # Only draw if visible
                screen_rect = canal.move(-int(camera.x), -int(camera.y))
                if screen_rect.colliderect(screen.get_rect()):
                    draw_canal_water(screen, screen_rect, ticks, color_base=(28, 36, 44))
            # Giant central fire pit VFX
            _draw_fire_pit_vfx(screen, center_x, plaza_center_y_approx,
                               camera.x, camera.y, ticks)
            # Small fire pit VFX (town square, west side)
            if random.random() < 0.45:
                spawn_particle_burst(
                    spell_effects,
                    Vector2(town_square_fire_pit_pos.x, town_square_fire_pit_pos.y - 5),
                    (255, 90, 30), (255, 180, 60),
                    count=2,
                    speed_min=15.0, speed_max=45.0,
                    life_min=0.6, life_max=1.4,
                    size_start=5.0, size_end=1.0,
                    spread=math.tau,
                    gravity=-55.0,
                    drag=0.5
                )
            # Giant fire pit particle spawn
            if random.random() < 0.6:
                spawn_particle_burst(
                    spell_effects,
                    Vector2(center_x, plaza_center_y_approx - 10),
                    (255, 100, 20), (255, 200, 60),
                    count=3,
                    speed_min=20.0, speed_max=60.0,
                    life_min=0.8, life_max=1.8,
                    size_start=6.0, size_end=1.0,
                    spread=math.tau,
                    gravity=-65.0,
                    drag=0.4
                )
            # Chimney smoke VFX
            for _cx, _cy in town_chimney_tops:
                _scx = _cx - int(camera.x)
                _scy = _cy - int(camera.y)
                if -50 <= _scx <= SCREEN_WIDTH + 50 and -50 <= _scy <= SCREEN_HEIGHT + 50:
                    if random.random() < 0.12:
                        spawn_particle_burst(
                            spell_effects,
                            Vector2(_cx, _cy),
                            (80, 78, 74), (50, 48, 44),
                            count=1,
                            speed_min=8.0, speed_max=20.0,
                            life_min=1.0, life_max=2.5,
                            size_start=4.0, size_end=8.0,
                            spread=0.6,
                            gravity=-30.0,
                            drag=0.8
                        )
            # Arena torch VFX (8 torches on inner wall)
            _arena_cx_vfx = center_x
            _arena_cy_vfx = HORIZON_Y + 810
            _arena_inner_rx, _arena_inner_ry = 190, 110
            for _ti in range(8):
                _tang = (_ti / 8) * math.tau + 0.2
                _atx = _arena_cx_vfx + math.cos(_tang) * (_arena_inner_rx + 2)
                _aty = _arena_cy_vfx + math.sin(_tang) * (_arena_inner_ry + 2)
                _ascx = _atx - camera.x
                _ascy = _aty - camera.y
                if -30 <= _ascx <= SCREEN_WIDTH + 30 and -30 <= _ascy <= SCREEN_HEIGHT + 30:
                    if random.random() < 0.3:
                        spawn_particle_burst(
                            spell_effects,
                            Vector2(_atx, _aty - 14),
                            (255, 160, 40), (255, 100, 20),
                            count=1,
                            speed_min=10.0, speed_max=30.0,
                            life_min=0.3, life_max=0.8,
                            size_start=3.0, size_end=1.0,
                            spread=0.8,
                            gravity=-50.0,
                            drag=0.4
                        )

        elif current_level == "ice_biome" and ice_surface is not None:
            screen.blit(ice_surface, (-int(camera.x), -int(camera.y)))
        else:
            screen.blit(wilderness_surface, (-int(camera.x), -int(camera.y)))

        tint = day_night.get_tint()
        if tint[3] > 0:
            tint_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            tint_surf.fill(tint)
            screen.blit(tint_surf, (0, 0))

        if combat_runtime is not None:
            combat_runtime.draw_ground(screen, camera)
        draw_spell_effects(screen, spell_effects, camera)
        if combat_runtime is not None:
            combat_runtime.draw_world(screen, camera)
        ticks = pygame.time.get_ticks()

        # Book portal VFX — origin portal (at player's casting location)
        if book_portal_active and book_portal_origin is not None:
            _bp_progress = 1.0 - (book_portal_timer / book_portal_total) if book_portal_total > 0 else 1.0
            draw_book_portal(screen, book_portal_origin, camera, ticks, progress=_bp_progress)
        # Book portal VFX — arrival portal (at destination after teleport)
        if book_portal_arrival_timer > 0.0 and book_portal_arrival_pos is not None:
            _bp_fade = book_portal_arrival_timer / 2.5
            draw_book_portal(screen, book_portal_arrival_pos, camera, ticks, progress=_bp_fade)

        # Draw loot piles (wilderness + ice biome)
        if current_level in ("wilderness", "ice_biome"):
            ticks = pygame.time.get_ticks()
            for pile in loot_piles:
                if bool(pile.get("collected", False)):
                    continue
                pile_pos = pile.get("pos")
                if not isinstance(pile_pos, Vector2):
                    continue
                sx = int(float(pile_pos.x) - camera.x)
                sy = int(float(pile_pos.y) - camera.y)
                if not (-30 <= sx <= SCREEN_WIDTH + 30 and -30 <= sy <= SCREEN_HEIGHT + 30):
                    continue
                pile_id = int(pile.get("id", -1))
                is_open = any(int(win.get("pile_id", -1)) == pile_id for win in open_loot_windows)
                is_raised = bool(pile.get("raised", False))
                pulse = abs(math.sin(ticks * 0.005)) * 0.5 + 0.5
                glow_alpha = int((120 if is_open else 90) * pulse)
                glow_surf = pygame.Surface((40, 40), pygame.SRCALPHA)
                if is_raised:
                    glow_col = (184, 164, 232, glow_alpha) if is_open else (132, 110, 188, glow_alpha)
                    shell_col = (56, 46, 74)
                    core_col = (150, 126, 214) if is_open else (128, 102, 184)
                    label_col = (232, 222, 248)
                else:
                    glow_col = (230, 208, 120, glow_alpha) if is_open else (220, 180, 60, glow_alpha)
                    shell_col = (64, 56, 26)
                    core_col = (220, 188, 88) if is_open else (200, 165, 50)
                    label_col = (244, 224, 138)
                pygame.draw.circle(glow_surf, glow_col, (20, 20), 18)
                screen.blit(glow_surf, (sx - 20, sy - 20))
                pygame.draw.circle(screen, shell_col, (sx, sy), 14)
                pygame.draw.circle(screen, core_col, (sx, sy), 10)
                if player_pos.distance_to(pile_pos) <= 140:
                    loot_entries = loot_entry_total(pile)
                    lbl_txt = f"Risen Loot [{loot_entries}]" if is_raised else f"Loot [{loot_entries}]"
                    lbl = tiny_font.render(lbl_txt, True, label_col)
                    screen.blit(lbl, (sx - lbl.get_width() // 2, sy - 28))

        ensure_level_decor_selection()
        current_level_decor = active_level_decor_entries()
        actors: List[Tuple[float, str, int]] = []
        ground_decor_indices: List[int] = []
        overlay_decor_indices: List[int] = []
        for i, decor_entry in enumerate(current_level_decor):
            if not isinstance(decor_entry, dict):
                continue
            decor_asset = level_decor_asset_lookup(level_decor_assets, str(decor_entry.get("asset_id", "")))
            layer_name = level_decor_asset_layer(decor_asset)
            if layer_name in ("GROUND", "DECOR"):
                ground_decor_indices.append(i)
                continue
            if layer_name in ("OVERLAY", "VFX"):
                overlay_decor_indices.append(i)
                continue
            try:
                decor_y = float(decor_entry.get("y", 0.0))
            except (TypeError, ValueError):
                continue
            actors.append((decor_y, "decor", i))
        if current_level == "town":
            for i, vendor in enumerate(vendors):
                actors.append((float(vendor["pos"].y), "vendor", i))
            for i, fa in enumerate(farm_animals):
                fa_pos = fa.get("pos")
                if isinstance(fa_pos, Vector2):
                    actors.append((float(fa_pos.y), "farm_animal", i))
            actors.append((float(town_square_fire_pit_pos.y), "fire", 0))
        else:
            for i, wolf in enumerate(active_enemies()):
                actors.append((float(wolf["pos"].y), "predator", i))
            for i, critter in enumerate(active_passives()):
                actors.append((float(critter["pos"].y), "wildlife", i))
            for i, summon in enumerate(summoned_skeletons):
                summon_pos = summon.get("pos")
                if isinstance(summon_pos, Vector2):
                    actors.append((float(summon_pos.y), "skeleton", i))

        actors.append((player_pos.y, "player", -1))
        actors.sort(key=lambda item: item[0])
        vendor_quest_markers: Dict[int, str] = {}
        if current_level == "town":
            for i, vendor in enumerate(vendors):
                role = str(vendor.get("role", ""))
                marker = quest_marker_for_vendor_role(role, quest_states, QUEST_DEFINITIONS)
                if marker:
                    vendor_quest_markers[i] = marker

        for decor_index in ground_decor_indices:
            if 0 <= decor_index < len(current_level_decor):
                decor_entry = current_level_decor[decor_index]
                if isinstance(decor_entry, dict):
                    draw_level_decor_instance(
                        screen,
                        decor_entry,
                        level_decor_assets,
                        level_decor_render_cache,
                        camera,
                    )

        # Draw all vendor stands first so shop walls are always behind actors.
        # Use int(camera) to match the town_surface blit offset and avoid 1px sub-pixel flicker.
        _vendor_behind_flags: list = []  # per-vendor: True if player is behind this vendor's shop
        if current_level == "town":
            _cam_ix, _cam_iy = int(camera.x), int(camera.y)
            _px, _py = int(player_pos.x), int(player_pos.y)
            for vendor in vendors:
                _shop_world = vendor.get("shop_pos")
                if isinstance(_shop_world, Vector2):
                    _shop_screen = Vector2(_shop_world.x - _cam_ix, _shop_world.y - _cam_iy)
                else:
                    _vpos = vendor["pos"]
                    _shop_screen = Vector2(_vpos.x - _cam_ix, _vpos.y - _cam_iy)
                # Check if player is behind this shop (use both stand and vendor pos)
                _sw = _shop_world if isinstance(_shop_world, Vector2) else vendor["pos"]
                _vw = vendor["pos"]
                _shop_margin = 120
                _check_y = min(_sw.y, _vw.y)  # use the furthest-north position
                _check_x = (_sw.x + _vw.x) / 2  # midpoint between stand and vendor
                _v_behind = (_py < _check_y - 10 and
                             _py > _check_y - 250 and
                             abs(_px - _check_x) < _shop_margin + 80)
                _vendor_behind_flags.append(_v_behind)
                if _v_behind:
                    # Draw stand to temp surface, apply transparency
                    _vs_w, _vs_h = 700, 700
                    _vs_tmp = pygame.Surface((_vs_w, _vs_h), pygame.SRCALPHA)
                    # Position center-bottom of the surface at the shop screen pos
                    _vs_center = Vector2(_vs_w // 2, _vs_h - 100)
                    draw_vendor_stand(
                        _vs_tmp, _vs_center,
                        str(vendor.get("role", "")).strip().lower(),
                        ticks, int(vendor.get("stand_seed", 0)),
                        rotation=float(vendor.get("shop_rotation", 0.0)),
                    )
                    _vs_alpha = pygame.Surface((_vs_w, _vs_h), pygame.SRCALPHA)
                    _vs_alpha.fill((255, 255, 255, 120))
                    _vs_tmp.blit(_vs_alpha, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
                    screen.blit(_vs_tmp, (int(_shop_screen.x) - _vs_w // 2,
                                          int(_shop_screen.y) - _vs_h + 100))
                else:
                    draw_vendor_stand(
                        screen, _shop_screen,
                        str(vendor.get("role", "")).strip().lower(),
                        ticks, int(vendor.get("stand_seed", 0)),
                        rotation=float(vendor.get("shop_rotation", 0.0)),
                    )

        for _, actor_type, idx in actors:
            if actor_type == "decor":
                if 0 <= idx < len(current_level_decor):
                    decor_entry = current_level_decor[idx]
                    if isinstance(decor_entry, dict):
                        draw_level_decor_instance(
                            screen,
                            decor_entry,
                            level_decor_assets,
                            level_decor_render_cache,
                            camera,
                        )
            elif actor_type == "player":
                player_draw_state = "run" if (moving and speed_boost_timer > 0.0) else ("walk" if moving else "idle")
                player_draw_timer = player_anim_timer
                if player_hurt_anim_state:
                    player_draw_state = player_hurt_anim_state
                    player_draw_timer = player_hurt_anim_elapsed
                elif player_attack_anim_state:
                    player_draw_state = player_attack_anim_state
                    player_draw_timer = player_attack_anim_elapsed
                draw_player(
                    screen,
                    player_pos - camera,
                    facing,
                    player_sprite,
                    player_sprite_left,
                    is_moving=moving,
                    anim_timer=player_draw_timer,
                    anim_frames=player_anim_frames,
                    anim_state=player_draw_state,
                    anim_direction=player_anim_direction,
                    anim_fps=player_anim_fps,
                    equip_tint_right=player_equip_tint,
                    equip_tint_left=player_equip_tint_left,
                    hit_flash_strength=clamp(player_hit_flash_timer / max(0.01, player_hit_flash_duration), 0.0, 1.0),
                )
                # ── Glowing contour when player is behind a house ──
                if _player_behind_house and current_level == "town":
                    _cs = get_facing_sprite(facing, player_sprite, player_sprite_left)
                    if _cs is not None:
                        _cw, _ch = _cs.get_size()
                        _cp = _cs.get_rect(midbottom=(int(player_pos.x - camera.x), int(player_pos.y - camera.y) + 1))
                        _outline_pad = 3
                        _ol_w = _cw + _outline_pad * 2
                        _ol_h = _ch + _outline_pad * 2
                        _ol_surf = pygame.Surface((_ol_w, _ol_h), pygame.SRCALPHA)
                        # Create colored silhouette using pygame.mask
                        _spr_mask = pygame.mask.from_surface(_cs, 50)
                        _sil = _spr_mask.to_surface(setcolor=(220, 200, 140, 255), unsetcolor=(0, 0, 0, 0))
                        # Stamp silhouette at 8 offsets to form outline
                        for _odx, _ody in [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(1,-1),(-1,1),(1,1)]:
                            _ol_surf.blit(_sil, (_outline_pad + _odx * 2, _outline_pad + _ody * 2))
                        # Cut out center so only border remains
                        _erase = _spr_mask.to_surface(setcolor=(255, 255, 255, 255), unsetcolor=(0, 0, 0, 0))
                        _ol_surf.blit(_erase, (_outline_pad, _outline_pad), special_flags=pygame.BLEND_RGBA_SUB)
                        # Pulse alpha
                        _ol_alpha = int(160 + 60 * math.sin(ticks * 0.006))
                        _ol_surf.set_alpha(_ol_alpha)
                        screen.blit(_ol_surf, (_cp.x - _outline_pad, _cp.y - _outline_pad))
                # ── Debuff icons above player head (from sprite sheet) ──
                _p_fx = status_effects.get_effects(StatusEffectSystem.PLAYER_KEY)
                if _p_fx:
                    _DEBUFF_SHEET = "assets/items food everything.png"
                    _DEBUFF_ICON_MAP = {
                        "bite": (16, 4),   # red claw scratch — row 16, col 4
                        "fear": (46, 0),   # purple swirl — row 46, col 0
                    }
                    _dbi_size = 28
                    _dbi_count = 0
                    _px_scr = int(player_pos.x - camera.x)
                    _py_scr = int(player_pos.y - camera.y) - 68  # above head
                    for _dfx in _p_fx:
                        _dbi_rc = _DEBUFF_ICON_MAP.get(_dfx.kind)
                        if _dbi_rc is None:
                            continue
                        _dbi_icon = load_arbitrary_sheet_icon(
                            _DEBUFF_SHEET, _dbi_rc[0], _dbi_rc[1],
                            tile_size=64, size=_dbi_size,
                        )
                        if _dbi_icon is None:
                            continue
                        _dbi_x = _px_scr - (_dbi_size // 2) + _dbi_count * (_dbi_size + 4) - ((_dbi_size + 4) * min(len(_p_fx), 3) // 2) + (_dbi_size + 4) // 2
                        _dbi_y = _py_scr + int(math.sin(pygame.time.get_ticks() * 0.004 + _dbi_count * 1.2) * 3)
                        # Pulsing alpha based on remaining duration
                        _dbi_alpha = max(120, min(255, int(180 + 75 * math.sin(pygame.time.get_ticks() * 0.008 + _dbi_count))))
                        _dbi_copy = _dbi_icon.copy()
                        _dbi_copy.set_alpha(_dbi_alpha)
                        screen.blit(_dbi_copy, (_dbi_x, _dbi_y))
                        _dbi_count += 1
            elif actor_type == "vendor":
                vendor = vendors[idx]
                _shop_world = vendor.get("shop_pos")
                _shop_screen = _shop_world - camera if isinstance(_shop_world, Vector2) else None
                _vb_flag = _vendor_behind_flags[idx] if idx < len(_vendor_behind_flags) else False
                # Choose render target: screen directly or temp surface for transparency
                if _vb_flag:
                    _vt_w, _vt_h = 200, 200
                    _vt_surf = pygame.Surface((_vt_w, _vt_h), pygame.SRCALPHA)
                    _vt_cx = int(vendor["pos"].x - camera.x)
                    _vt_cy = int(vendor["pos"].y - camera.y)
                    _vt_ox = _vt_cx - _vt_w // 2
                    _vt_oy = _vt_cy - _vt_h + 20
                    _vt_offset = Vector2(_vt_ox, _vt_oy)
                    draw_vendor(
                        _vt_surf,
                        vendor["pos"] - camera - _vt_offset,
                        None,
                        str(vendor.get("role", "")),
                        int(vendor["facing"]),
                        vendor["sprite"], vendor["sprite_left"],
                        float(vendor.get("anim_timer", vendor.get("idle_time", 0.0))),
                        anim_frames=vendor.get("anim_frames"),
                        stand_seed=int(vendor.get("stand_seed", 0)),
                        ticks=ticks, draw_stand=False,
                        is_moving=bool(vendor.get("patrol_moving", False)),
                    )
                    _vt_alpha = pygame.Surface((_vt_w, _vt_h), pygame.SRCALPHA)
                    _vt_alpha.fill((255, 255, 255, 120))
                    _vt_surf.blit(_vt_alpha, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
                    screen.blit(_vt_surf, (int(_vt_ox), int(_vt_oy)))
                else:
                    draw_vendor(
                        screen,
                        vendor["pos"] - camera,
                        _shop_screen,
                        str(vendor.get("role", "")),
                        int(vendor["facing"]),
                        vendor["sprite"], vendor["sprite_left"],
                        float(vendor.get("anim_timer", vendor.get("idle_time", 0.0))),
                        anim_frames=vendor.get("anim_frames"),
                        stand_seed=int(vendor.get("stand_seed", 0)),
                        ticks=ticks, draw_stand=False,
                        is_moving=bool(vendor.get("patrol_moving", False)),
                    )
                # WoW-style nameplate above sprite
                _vsprite = vendor["sprite"]
                _vrect = _vsprite.get_rect(midbottom=(int(vendor["pos"].x - camera.x), int(vendor["pos"].y - camera.y) + 1))
                _vname = str(vendor.get("name", ""))
                marker = vendor_quest_markers.get(idx, "")
                _nameplate_top = _vrect.top - 4
                if _vname:
                    _vnsurf = npc_name_font.render(_vname, True, (238, 220, 168))
                    _vnjob  = npc_name_font.render(str(vendor.get("role", "")), True, (168, 196, 220))
                    _vnw = max(_vnsurf.get_width(), _vnjob.get_width()) + 6
                    _vnh = _vnsurf.get_height() + _vnjob.get_height() + 4
                    _vnx = _vrect.centerx - _vnw // 2
                    _vny = _vrect.top - _vnh - 4
                    _nameplate_top = _vny
                    _bg = pygame.Surface((_vnw, _vnh), pygame.SRCALPHA)
                    _bg.fill((8, 8, 14, 165))
                    screen.blit(_bg, (_vnx, _vny))
                    screen.blit(_vnsurf, (_vnx + (_vnw - _vnsurf.get_width()) // 2, _vny + 2))
                    screen.blit(_vnjob,  (_vnx + (_vnw - _vnjob.get_width())  // 2, _vny + 2 + _vnsurf.get_height() + 1))
                # Vendor shop icon (floating pouch above nameplate)
                _icon_bob = int(math.sin(ticks * 0.004 + idx * 1.7) * 2)
                _icon_x = _vrect.centerx - vendor_shop_icon.get_width() // 2
                _icon_y = _nameplate_top - vendor_shop_icon.get_height() - 2 + _icon_bob
                screen.blit(vendor_shop_icon, (_icon_x, _icon_y))
                if marker:
                    draw_vendor_quest_marker(
                        screen,
                        vendor["pos"] - camera,
                        int(vendor["facing"]),
                        vendor["sprite"],
                        vendor["sprite_left"],
                        float(vendor.get("idle_time", 0.0)),
                        marker,
                        ui_font,
                        pygame.time.get_ticks(),
                        highlighted=(active_vendor_idx == idx),
                        nameplate_top=_nameplate_top,
                    )
                if show_level_decor_editor:
                    vendor_pos = vendor.get("pos")
                    if isinstance(vendor_pos, Vector2):
                        anchor = (int(vendor_pos.x - camera.x), int(vendor_pos.y - camera.y - 10))
                        ring_color = (244, 208, 132) if drag_npc_idx == idx else (118, 224, 232)
                        pygame.draw.circle(screen, ring_color, anchor, 8 if drag_npc_idx == idx else 6, 2)
                        if drag_npc_idx == idx:
                            drag_label = tiny_font.render("Moving", True, (248, 236, 196))
                            screen.blit(drag_label, (anchor[0] - drag_label.get_width() // 2, anchor[1] - 24))
            elif actor_type == "farm_animal":
                _fa_entry = farm_animals[idx]
                draw_farm_animal(screen, _fa_entry, int(camera.x), int(camera.y), ticks)
            elif actor_type == "wildlife":
                critter = active_passives()[idx]
                draw_passive_animal(
                    screen,
                    critter["pos"] - camera,
                    int(critter["facing"]),
                    critter["sprite"],
                    critter["sprite_left"],
                    float(critter.get("hp", 0.0)),
                    float(critter.get("max_hp", 1.0)),
                    anim_frames=critter.get("anim_frames"),
                    anim_timer=float(critter.get("anim_timer", 0.0)),
                    name=str(critter.get("name", "")),
                    moving=bool(critter.get("moving", False)),
                )
            elif actor_type == "skeleton":
                summon = summoned_skeletons[idx]
                summon_pos = summon.get("pos")
                if isinstance(summon_pos, Vector2):
                    draw_summoned_skeleton(
                        screen,
                        summon_pos - camera,
                        int(summon.get("facing", 1)),
                        float(summon.get("life", 0.0)),
                        float(summon.get("duration", 1.0)),
                        level=max(1, int(summon.get("level", 1))),
                        swing=float(summon.get("swing", 0.0)),
                    )
            elif actor_type == "fire":
                if fire_frames:
                    frame_idx = (pygame.time.get_ticks() // 150) % len(fire_frames)
                    f = fire_frames[frame_idx]
                    # Draw centered on the fire pit location (town square, west side)
                    _fx = int(town_square_fire_pit_pos.x) - f.get_width() // 2 - int(camera.x)
                    _fy = int(town_square_fire_pit_pos.y) - f.get_height() + 12 - int(camera.y)
                    screen.blit(f, (_fx, _fy))
            else:
                wolf = active_enemies()[idx] # "predator"
                wolf_fx = status_effects.get_effects(status_effects.wolf_key(wolf))
                freeze_strength = 0.0
                _wolf_burn_str = 0.0
                _wolf_slow_str = 0.0
                _wolf_stun_str = 0.0
                for fx in wolf_fx:
                    if fx.kind == "freeze":
                        freeze_strength = max(freeze_strength, clamp(float(fx.duration) / 2.4, 0.0, 1.0))
                    elif fx.kind == "burn":
                        _wolf_burn_str = max(_wolf_burn_str, clamp(float(fx.duration) / 3.0, 0.0, 1.0))
                    elif fx.kind == "scorched":
                        _wolf_burn_str = max(_wolf_burn_str, clamp(float(fx.duration) / 5.0, 0.3, 0.7))
                    elif fx.kind == "slow":
                        _wolf_slow_str = max(_wolf_slow_str, clamp(float(fx.potency), 0.0, 1.0))
                    elif fx.kind == "stun":
                        _wolf_stun_str = max(_wolf_stun_str, clamp(float(fx.duration) / 1.0, 0.0, 1.0))
                _wolf_hit_flash_dur = max(0.001, float(wolf.get("hit_flash_duration", 0.14)))
                _wolf_hit_flash = clamp(float(wolf.get("hit_flash_timer", 0.0)) / _wolf_hit_flash_dur, 0.0, 1.0)
                _wolf_hit_flash_color_raw = wolf.get("hit_flash_color", (255, 244, 220))
                _wolf_hit_flash_color = _wolf_hit_flash_color_raw if isinstance(_wolf_hit_flash_color_raw, tuple) and len(_wolf_hit_flash_color_raw) == 3 else (255, 244, 220)
                draw_wolf(
                    screen,
                    wolf["pos"] - camera,
                    int(wolf["facing"]),
                    wolf["sprite"],
                    wolf["sprite_left"],
                    float(wolf["hp"]),
                    float(wolf["max_hp"]),
                    level=int(wolf.get("level", 1)),
                    selected=(id(wolf) == selected_wolf_id),
                    attack_state=str(wolf.get("attack_state", "idle")),
                    attack_visual=float(wolf.get("attack_visual", 0.0)),
                    engage_role=str(wolf.get("engage_role", "patrol")),
                    chasing=bool(wolf.get("chasing", False)),
                    anim_frames=wolf.get("anim_frames"),
                    anim_timer=float(wolf.get("anim_timer", 0.0)),
                    frozen=freeze_strength > 0.0,
                    frozen_strength=freeze_strength,
                    burn_strength=_wolf_burn_str,
                    slow_strength=_wolf_slow_str,
                    stun_strength=_wolf_stun_str,
                    hit_flash_strength=_wolf_hit_flash,
                    hit_flash_color=_wolf_hit_flash_color,
                    dying=bool(wolf.get("dying", False)),
                    death_progress=(1.0 - clamp(float(wolf.get("death_timer", 0.0)) / max(0.001, float(wolf.get("death_duration", 0.55))), 0.0, 1.0)),
                )

        # Foreground house overlays (transparent) — draw after actors so roofs can occlude.
        if current_level == "town" and _town_house_overlays_fg:
            for _ho_surf, _ho_sx, _ho_sy, _ho_tag in _town_house_overlays_fg:
                    # Skip church even if tagged (church never fades)
                    if _ho_tag == "church":
                        continue
                    _ho_copy = _ho_surf.copy()
                    _alpha_surf = pygame.Surface(_ho_copy.get_size(), pygame.SRCALPHA)
                    _alpha_surf.fill((255, 255, 255, 100))  # ~39% opacity
                    _ho_copy.blit(_alpha_surf, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
                    screen.blit(_ho_copy, (_ho_sx, _ho_sy))

        for decor_index in overlay_decor_indices:
            if 0 <= decor_index < len(current_level_decor):
                decor_entry = current_level_decor[decor_index]
                if isinstance(decor_entry, dict):
                    draw_level_decor_instance(
                        screen,
                        decor_entry,
                        level_decor_assets,
                        level_decor_render_cache,
                        camera,
                    )

        if show_level_decor_editor and decor_collision_preview:
            for decor_entry in current_level_decor:
                if not isinstance(decor_entry, dict):
                    continue
                collision_rect = get_level_decor_collision_rect(
                    decor_entry,
                    level_decor_assets,
                    level_decor_render_cache,
                    camera,
                )
                if not isinstance(collision_rect, pygame.Rect):
                    continue
                if not collision_rect.colliderect(pygame.Rect(-60, -60, SCREEN_WIDTH + 120, SCREEN_HEIGHT + 120)):
                    continue
                fill = pygame.Surface((collision_rect.width, collision_rect.height), pygame.SRCALPHA)
                fill.fill((82, 198, 204, 48))
                screen.blit(fill, collision_rect.topleft)
                pygame.draw.rect(screen, (110, 228, 236), collision_rect, 1)

        if show_level_decor_editor and decor_selected_asset_id and decor_placement_mode not in ("delete", "move"):
            placement_rect = pygame.Rect(16, 16, max(220, SCREEN_WIDTH - DECOR_EDITOR_PANEL_WIDTH - 44), SCREEN_HEIGHT - 32)
            if placement_rect.collidepoint(mouse_pos):
                preview_asset = selected_level_decor_asset()
                preview_world = Vector2(float(mouse_pos[0] + camera.x), float(mouse_pos[1] + camera.y))
                preview_generated = isinstance(preview_asset, dict) and str(preview_asset.get("asset_pack", "")).lower() == "medieval_generated"
                if preview_generated or level_decor_asset_uses_tile_brush(preview_asset) or decor_placement_mode == "tile":
                    preview_world = snap_editor_point_to_grid(preview_world)
                preview_entry = {
                    "asset_id": decor_selected_asset_id,
                    "x": float(preview_world.x),
                    "y": float(preview_world.y),
                    "scale": 1.0 if level_decor_asset_uses_tile_brush(preview_asset) else decor_selected_scale,
                    "rotation": 0.0 if level_decor_asset_uses_tile_brush(preview_asset) else decor_selected_rotation,
                }
                draw_level_decor_instance(
                    screen,
                    preview_entry,
                    level_decor_assets,
                    level_decor_render_cache,
                    camera,
                    alpha=158,
                    highlight=True,
                    show_anchor=True,
                )

        if show_level_decor_editor and decor_grabbed is not None:
            _grab_world = Vector2(float(mouse_pos[0] + camera.x), float(mouse_pos[1] + camera.y))
            _grab_preview = dict(decor_grabbed)
            _grab_preview["x"] = float(_grab_world.x)
            _grab_preview["y"] = float(_grab_world.y)
            draw_level_decor_instance(
                screen,
                _grab_preview,
                level_decor_assets,
                level_decor_render_cache,
                camera,
                alpha=180,
                highlight=True,
                show_anchor=True,
            )

        if show_level_decor_editor and decor_grab_church and current_level == "town":
            _ch_screen = Vector2(church_pos.x - camera.x, church_pos.y - camera.y)
            _ch_preview = pygame.Surface((500, 700), pygame.SRCALPHA)
            draw_church(_ch_preview, 250, 600)
            _ch_preview.set_alpha(160)
            screen.blit(_ch_preview, (int(_ch_screen.x) - 250, int(_ch_screen.y) - 600))

        for ultimate in active_ultimates:
            ultimate.draw(screen, camera)
        draw_damage_numbers(screen, damage_numbers, camera, tiny_font)
        if combat_runtime is not None:
            combat_runtime.draw_overlay(screen, camera)
        ambient_overlay.draw(
            screen,
            current_level,
            weather_system.cloud_cover,
            weather_system.precipitation,
            weather_system.fog_density,
            day_night.time,
        )

        # Draw point-light glows for town lamps/braziers/fire (before weather overlay)
        if current_level == "town":
            night_factor = 0.0
            _dn_t = day_night.time
            if _dn_t >= 20.0 or _dn_t < 5.0:
                night_factor = 1.0
            elif 18.0 <= _dn_t < 20.0:
                night_factor = (_dn_t - 18.0) / 2.0
            elif 5.0 <= _dn_t < 7.0:
                night_factor = 1.0 - (_dn_t - 5.0) / 2.0
            if night_factor > 0.02:
                for _lx, _ly, _lc, _li, _lo, _la in TOWN_LIGHTS:
                    _sx = _lx - int(camera.x)
                    _sy = _ly - int(camera.y)
                    if -_lo <= _sx <= SCREEN_WIDTH + _lo and -_lo <= _sy <= SCREEN_HEIGHT + _lo:
                        draw_point_light(screen, _sx, _sy, _lc, _li, int(_lo * (0.5 + 0.5 * night_factor)), int(_la * night_factor))

        weather_system.render(screen)
        screen_effects.draw(screen)

        # ── Fear visual overlay — pulsing purple vignette + screen wobble ──
        if _player_feared:
            _fear_alpha = int(48 + 22 * math.sin(pygame.time.get_ticks() * 0.006))
            _fear_ov = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            # Dark purple edges (vignette)
            _fcx, _fcy = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
            _fmax_r = math.hypot(_fcx, _fcy)
            for _fri in range(5):
                _fr = _fmax_r * (0.55 + _fri * 0.12)
                _fa = min(255, _fear_alpha + _fri * 18)
                pygame.draw.circle(_fear_ov, (80, 20, 120, _fa), (_fcx, _fcy), int(_fr), width=max(40, int(_fmax_r * 0.12)))
            screen.blit(_fear_ov, (0, 0))
            # Subtle screen shake
            _shake_x = random.randint(-3, 3)
            _shake_y = random.randint(-2, 2)
            _shifted = screen.copy()
            screen.fill((0, 0, 0))
            screen.blit(_shifted, (_shake_x, _shake_y))

        _lvl_px = (player_pos - camera).x
        _lvl_py = (player_pos - camera).y
        level_up_vfx.draw(screen, _lvl_px, _lvl_py, skill_title_font)

        # Adaptive color-grade overlays and atmospheric edge lighting.
        _grade_hour = day_night.time % 24.0
        if 6.0 <= _grade_hour < 18.0:
            _night_grade = 0.0
        elif 18.0 <= _grade_hour < 20.0:
            _night_grade = (_grade_hour - 18.0) / 2.0
        elif 5.0 <= _grade_hour < 7.0:
            _night_grade = 1.0 - (_grade_hour - 5.0) / 2.0
        else:
            _night_grade = 1.0
        _daylight = clamp(1.0 - abs(_grade_hour - 12.0) / 6.0, 0.0, 1.0)
        _warm_alpha = int(22.0 * _daylight * (1.0 - clamp(weather_system.cloud_cover * 0.82 + weather_system.precipitation * 0.78, 0.0, 1.0)))
        if current_level != "ice_biome" and _warm_alpha > 0:
            warm_grade_overlay.set_alpha(_warm_alpha)
            screen.blit(warm_grade_overlay, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
        _cold_alpha = int(
            clamp(
                12.0
                + _night_grade * 22.0  # was 34 — keep night readable (detail stays visible)
                + weather_system.precipitation * 30.0
                + weather_system.fog_density * 22.0
                + (14.0 if current_level == "ice_biome" else 0.0),
                0.0,
                88.0,
            )
        )
        if _cold_alpha > 0:
            cold_grade_overlay.set_alpha(_cold_alpha)
            screen.blit(cold_grade_overlay, (0, 0))

        # Radial vignette — focuses the eye and frames the scene (cheap polish).
        screen.blit(gameplay_vignette, (0, 0))

        if current_level == "wilderness":
            lock_name = ""
            if selected_wolf_id is not None:
                for wolf in active_enemies():
                    if id(wolf) == selected_wolf_id:
                        lock_name = str(wolf.get("name", "Target"))
                        break
            lock_txt = f"  Â·  {lock_name}" if lock_name else ""
            info = tiny_font.render(
                f"{active_class['name']}  Â·  Predators {len(active_enemies())}  Â·  Slain {wolves_slain}{lock_txt}",
                True, (170, 178, 160),
            )
            screen.blit(info, (24, 16))

        # Gate VFX (embers, mist, glow — always rendered when in town)
        if current_level == "town":
            _draw_gate_vfx(screen, int(town_gate_pos.x), int(town_gate_pos.y),
                           camera.x, camera.y, pygame.time.get_ticks())

        # Gate tooltip
        if gate_hovered:
            gx = int(town_gate_pos.x - camera.x)
            gy = int(town_gate_pos.y - camera.y)
            _gl1 = ui_font.render("Town Gate", True, (226, 224, 245))
            _gl2 = tiny_font.render("[Click] Enter The Wilderness", True, (196, 194, 218))
            _gtw = max(_gl1.get_width(), _gl2.get_width()) + 18
            _gth = _gl1.get_height() + _gl2.get_height() + 14
            _gtr = pygame.Rect(0, 0, _gtw, _gth)
            _gtr.midbottom = (gx, gy - 100)
            _gtr.clamp_ip(pygame.Rect(10, 10, SCREEN_WIDTH - 20, SCREEN_HEIGHT - 20))
            pygame.draw.rect(screen, (14, 14, 22), _gtr, border_radius=8)
            pygame.draw.rect(screen, (118, 112, 176), _gtr, 1, border_radius=8)
            screen.blit(_gl1, (_gtr.left + 9, _gtr.top + 5))
            screen.blit(_gl2, (_gtr.left + 9, _gtr.top + 8 + _gl1.get_height()))

        draw_player_resource_bars(
            screen,
            player_hp,
            player_max_hp,
            player_mana,
            player_max_mana,
            ui_font,
            tiny_font,
            gold=player_gold,
            player_level=player_level,
            xp=player_xp,
            xp_to_next=player_xp_next,
        )
        # Backpack button (bottom-right, above action belt level)
        _bp_size = 44
        _bp_x = SCREEN_WIDTH - _bp_size - 16
        _bp_y = SCREEN_HEIGHT - _bp_size - 8
        _backpack_btn_rect = pygame.Rect(_bp_x, _bp_y, _bp_size, _bp_size)
        _bp_hov = _backpack_btn_rect.collidepoint(pygame.mouse.get_pos())
        _bp_pressed = _bp_hov and pygame.mouse.get_pressed(3)[0]
        draw_backpack_button_realistic(
            screen, _backpack_btn_rect, tiny_font,
            backpack_count=len(backpack_inventory), backpack_capacity=BACKPACK_SLOT_COUNT,
            hovered=_bp_hov, pressed=_bp_pressed, ticks=pygame.time.get_ticks(),
        )

        # ── WoW Target Frame ─────────────────────────────────────────────────
        if (current_level in ("wilderness", "ice_biome") and selected_wolf_id is not None
                and not show_world_map and not show_skill_tree and not show_character
                and not show_crafting and not show_quest_log):
            for _twolf in active_enemies():
                if id(_twolf) == selected_wolf_id and float(_twolf.get("hp", 0.0)) > 0.0:
                    draw_target_frame(
                        screen,
                        str(_twolf.get("name", "Target")),
                        float(_twolf.get("hp", 0.0)),
                        float(_twolf.get("max_hp", 100.0)),
                        int(_twolf.get("level", 1)),
                        tiny_font,
                    )
                    break

        # ── WoW Buff Tracker (below player panel) ─────────────────────────────
        if not show_world_map and not show_skill_tree and not show_character and not show_crafting:
            draw_buff_tracker(screen, damage_boost_timer, speed_boost_timer, tiny_font)

        selected_target_pos: Optional[Vector2] = None
        if current_level in ("wilderness", "ice_biome") and selected_wolf_id is not None:
            for wolf in active_enemies():
                if id(wolf) == selected_wolf_id and isinstance(wolf.get("pos"), Vector2):
                    selected_target_pos = Vector2(wolf["pos"])
                    break
        map_vendor_positions: List[Vector2] = []
        if current_level == "town":
            map_vendor_positions = [Vector2(v["pos"]) for v in vendors if isinstance(v.get("pos"), Vector2)]
        active_map_cache = world_map_cache_by_level.get(current_level, {})
        minimap_rect = pygame.Rect(0, 0, 0, 0)
        tracker_anchor_y = 16
        if not show_world_map and not show_skill_tree and not show_character and not show_crafting and not show_quest_log and not show_professions and not show_level_decor_editor:
            minimap_rect = draw_wow_minimap(
                screen,
                active_map_cache,
                current_level,
                player_pos,
                facing,
                None,
                map_vendor_positions,
                selected_target_pos,
                tiny_font,
                tiny_font,
                day_night.time,
            )
            tracker_anchor_y = minimap_rect.bottom + 10
            weather_title = tiny_font.render(f"Weather: {weather_system.get_display_name()}", True, weather_system.get_ui_color())
            weather_detail = tiny_font.render(weather_system.get_hud_detail(current_level), True, (168, 176, 190))
            weather_rect = pygame.Rect(
                minimap_rect.left,
                minimap_rect.bottom + 8,
                max(weather_title.get_width(), weather_detail.get_width()) + 18,
                weather_title.get_height() + weather_detail.get_height() + 14,
            )
            weather_rect.clamp_ip(pygame.Rect(8, 8, SCREEN_WIDTH - 16, SCREEN_HEIGHT - 16))
            draw_ornate_panel(screen, weather_rect)
            screen.blit(weather_title, (weather_rect.left + 9, weather_rect.top + 5))
            screen.blit(weather_detail, (weather_rect.left + 9, weather_rect.top + 7 + weather_title.get_height()))
            tracker_anchor_y = max(tracker_anchor_y, weather_rect.bottom + 10)

        # Active quest tracker (top-right) — compact parchment
        active_quest_def = next(
            (q for q in QUEST_DEFINITIONS if quest_states.get(q["id"]) in ("active", "complete")),
            None,
        )
        qt_x = SCREEN_WIDTH - 260
        qt_y = tracker_anchor_y
        if active_quest_def:
            qid = active_quest_def["id"]
            prog = quest_progress.get(qid, [0] * len(active_quest_def["objectives"]))
            is_complete = quest_states.get(qid) == "complete"
            num_obj = len(active_quest_def["objectives"])
            qt_h = 28 + num_obj * 18 + (16 if is_complete else 0)
            qt_w = 248
            qt_panel = pygame.Rect(qt_x - 6, qt_y - 3, qt_w, qt_h)
            # Bright parchment bg
            _parch = _make_parchment(qt_w, qt_h)
            screen.blit(_parch, qt_panel.topleft)
            pygame.draw.rect(screen, (120, 90, 40), qt_panel, 1, border_radius=2)
            # Title in dark ink
            _qt_title = tiny_font.render(active_quest_def["title"], True, (35, 20, 5))
            screen.blit(_qt_title, (qt_x, qt_y))
            _div_y = qt_y + _qt_title.get_height() + 1
            pygame.draw.line(screen, (150, 120, 60), (qt_x, _div_y), (qt_x + qt_w - 16, _div_y), 1)
            _oy = _div_y + 3
            for i, obj in enumerate(active_quest_def["objectives"]):
                cur = min(prog[i] if i < len(prog) else 0, obj["count"])
                tgt = obj["count"]
                done = cur >= tgt
                lbl = obj["label"].split("(")[0].strip()
                _lbl_col = (30, 120, 30) if done else (55, 35, 10)
                _obj_s = tiny_font.render(f"- {lbl}  ({cur}/{tgt})", True, _lbl_col)
                screen.blit(_obj_s, (qt_x + 2, _oy))
                _oy += 18
            if is_complete:
                _ready_s = tiny_font.render("READY -- [J] Turn In", True, (160, 45, 30))
                screen.blit(_ready_s, (qt_x + (qt_w - 16 - _ready_s.get_width()) // 2, _oy))
            qt_y += qt_panel.height + 4

        # Buff indicators
        buff_y = qt_y
        for buff_label, timer, col in [
            (f"DMG +35%  {int(damage_boost_timer)}s", damage_boost_timer, (255, 200, 80)),
            (f"SPD +28%  {int(speed_boost_timer)}s",  speed_boost_timer,  (120, 210, 240)),
        ]:
            if timer > 0.0:
                bs = tiny_font.render(buff_label, True, col)
                bx = SCREEN_WIDTH - bs.get_width() - 16
                pygame.draw.rect(screen, (22, 20, 14), pygame.Rect(bx - 6, buff_y - 2, bs.get_width() + 12, 22), border_radius=6)
                screen.blit(bs, (bx, buff_y))
                buff_y += 26

        # ── POI Discovery Banner (top-center) ──
        if poi_active and poi_fade_alpha > 0.1 and poi_world_pos is not None:
            _poi_alpha = int(min(255, poi_fade_alpha))
            _poi_title_s = ui_font.render(poi_name, True, (255, 230, 170))
            _poi_desc_s = tiny_font.render(poi_desc, True, (200, 190, 160))
            _poi_bw = max(_poi_title_s.get_width(), _poi_desc_s.get_width()) + 60
            _poi_bh = _poi_title_s.get_height() + _poi_desc_s.get_height() + 22
            _poi_bx = (SCREEN_WIDTH - _poi_bw) // 2
            _poi_by = 18
            _poi_panel = pygame.Surface((_poi_bw, _poi_bh), pygame.SRCALPHA)
            # Dark parchment background
            pygame.draw.rect(_poi_panel, (18, 14, 10, _poi_alpha), (0, 0, _poi_bw, _poi_bh), border_radius=8)
            pygame.draw.rect(_poi_panel, (160, 120, 50, _poi_alpha), (0, 0, _poi_bw, _poi_bh), 2, border_radius=8)
            # Gold accent lines
            pygame.draw.line(_poi_panel, (180, 140, 60, _poi_alpha), (10, _poi_bh - 6), (_poi_bw - 10, _poi_bh - 6), 1)
            pygame.draw.line(_poi_panel, (180, 140, 60, _poi_alpha), (10, 5), (_poi_bw - 10, 5), 1)
            # Compass marker icon (small diamond)
            _dm_cx = 20
            _dm_cy = _poi_bh // 2
            pygame.draw.polygon(_poi_panel, (220, 180, 60, _poi_alpha),
                                [(_dm_cx, _dm_cy - 8), (_dm_cx + 6, _dm_cy), (_dm_cx, _dm_cy + 8), (_dm_cx - 6, _dm_cy)])
            # Text
            _poi_title_s.set_alpha(_poi_alpha)
            _poi_desc_s.set_alpha(_poi_alpha)
            _poi_panel.blit(_poi_title_s, (36, 8))
            _poi_panel.blit(_poi_desc_s, (36, 10 + _poi_title_s.get_height()))
            screen.blit(_poi_panel, (_poi_bx, _poi_by))
            # Directional arrow pointing toward POI on screen edge
            _poi_sx = poi_world_pos.x - camera.x
            _poi_sy = poi_world_pos.y - camera.y
            _poi_on_screen = 40 < _poi_sx < SCREEN_WIDTH - 40 and 40 < _poi_sy < SCREEN_HEIGHT - 40
            if not _poi_on_screen:
                # Clamp to screen edge and draw arrow
                _arr_x = max(30, min(SCREEN_WIDTH - 30, _poi_sx))
                _arr_y = max(_poi_by + _poi_bh + 20, min(SCREEN_HEIGHT - 50, _poi_sy))
                _arr_dx = poi_world_pos.x - (player_pos.x)
                _arr_dy = poi_world_pos.y - (player_pos.y)
                _arr_len = max(1.0, math.sqrt(_arr_dx * _arr_dx + _arr_dy * _arr_dy))
                _arr_nx = _arr_dx / _arr_len
                _arr_ny = _arr_dy / _arr_len
                _arr_sz = 12
                _tip_x = int(_arr_x + _arr_nx * _arr_sz)
                _tip_y = int(_arr_y + _arr_ny * _arr_sz)
                _l_x = int(_arr_x - _arr_ny * _arr_sz * 0.5 - _arr_nx * _arr_sz * 0.3)
                _l_y = int(_arr_y + _arr_nx * _arr_sz * 0.5 - _arr_ny * _arr_sz * 0.3)
                _r_x = int(_arr_x + _arr_ny * _arr_sz * 0.5 - _arr_nx * _arr_sz * 0.3)
                _r_y = int(_arr_y - _arr_nx * _arr_sz * 0.5 - _arr_ny * _arr_sz * 0.3)
                _acol = (220, 180, 60, _poi_alpha)
                _arr_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
                pygame.draw.polygon(_arr_surf, _acol, [(_tip_x, _tip_y), (_l_x, _l_y), (_r_x, _r_y)])
                pygame.draw.circle(_arr_surf, _acol, (int(_arr_x), int(_arr_y)), 4)
                screen.blit(_arr_surf, (0, 0))

        # Player status effect icons (debuffs/buffs from combat)
        _EFFECT_ICONS: Dict[str, Tuple[Tuple[int,int,int], str]] = {
            "burn":    ((255, 100, 30),  "BURN"),
            "freeze":  ((80,  200, 255), "FRZE"),
            "slow":    ((130, 160, 220), "SLOW"),
            "stun":    ((240, 220, 60),  "STUN"),
            "shield":  ((220, 195, 80),  "SHLD"),
            "bleed":   ((210, 60,  80),  "BLEED"),
            "bite":    ((200, 80,  50),  "BITE"),
            "fear":    ((160, 60, 200),  "FEAR"),
        }
        _player_fx = status_effects.get_effects(StatusEffectSystem.PLAYER_KEY)
        if _player_fx:
            _fx_icon_size = 30
            # Position below minimap (WoW-style)
            _minimap_right = SCREEN_WIDTH - 18
            _minimap_bottom = 16 + 216 + 6  # frame_size=216, gap
            _fx_x = _minimap_right
            _fx_y = _minimap_bottom
            for _fx in _player_fx:
                _fx_col, _fx_lbl = _EFFECT_ICONS.get(_fx.kind, ((200, 200, 200), _fx.kind[:4].upper()))
                _fx_x -= _fx_icon_size + 4  # right-aligned, grow leftward
                # Icon background
                _fx_surf = pygame.Surface((_fx_icon_size, _fx_icon_size), pygame.SRCALPHA)
                pygame.draw.rect(_fx_surf, (12, 10, 16, 210), _fx_surf.get_rect(), border_radius=6)
                # Colored border — thicker for hostile debuffs
                _border_w = 2 if _fx.kind in ("shield",) else 2
                pygame.draw.rect(_fx_surf, (*_fx_col, 200), _fx_surf.get_rect(), _border_w, border_radius=6)
                # Fill sweep (clockwise drain visual — approximated as bottom-up fill)
                _fx_fill = clamp(_fx.duration / max(0.1, _fx.duration + 0.5), 0.0, 1.0)
                _fill_h = int((_fx_icon_size - 4) * _fx_fill)
                if _fill_h > 0:
                    _fill_s = pygame.Surface((_fx_icon_size - 4, _fill_h), pygame.SRCALPHA)
                    _fill_s.fill((*_fx_col, 50))
                    _fx_surf.blit(_fill_s, (2, _fx_icon_size - _fill_h - 2))
                # Icon symbol
                _lbl_s = tiny_font.render(_fx_lbl, True, _fx_col)
                _fx_surf.blit(_lbl_s, (_fx_icon_size // 2 - _lbl_s.get_width() // 2,
                                        _fx_icon_size // 2 - _lbl_s.get_height() // 2 - 1))
                screen.blit(_fx_surf, (_fx_x, _fx_y))
                # Duration text below
                _dur_s = tiny_font.render(f"{_fx.duration:.0f}s", True, (180, 180, 180))
                screen.blit(_dur_s, (_fx_x + _fx_icon_size // 2 - _dur_s.get_width() // 2,
                                      _fx_y + _fx_icon_size + 1))

        if npc_menu_mode != "" and active_vendor_idx is not None and current_level == "town" and 0 <= active_vendor_idx < len(vendors):
            vendor = vendors[active_vendor_idx]
            dialog = active_vendor_line if active_vendor_line else str(vendor.get("line", ""))
            draw_npc_menu(
                screen,
                vendor,
                npc_menu_mode,
                active_dialogue,
                dialog,
                quest_states,
                QUEST_DEFINITIONS,
                npc_option_rects,
                dialog_name_font,
                dialog_text_font,
                tiny_font,
            )

        # Shop panel (shown when shop_open is set)
        if shop_open and shop_open in VENDOR_SHOPS:
            shop_items = VENDOR_SHOPS[shop_open]
            sp_panel = pygame.Rect(SCREEN_WIDTH - 340, SCREEN_HEIGHT - 280, 316, 44 + len(shop_items) * 46)
            draw_ornate_panel(screen, sp_panel)
            title_s = dialog_name_font.render(f"{shop_open} Shop  (Gold: {player_gold}g)", True, (200, 230, 160))
            screen.blit(title_s, (sp_panel.left + 12, sp_panel.top + 10))
            for si, sitem in enumerate(shop_items):
                row_y = sp_panel.top + 44 + si * 46
                key_s = tiny_font.render(f"[{si + 1}]", True, (220, 196, 100))
                name_s = dialog_text_font.render(f"{sitem['name']} — {sitem['desc']}", True, (228, 228, 228))
                cost_s = tiny_font.render(f"{sitem['cost']}g", True, (220, 196, 100))
                screen.blit(key_s, (sp_panel.left + 12, row_y))
                screen.blit(name_s, (sp_panel.left + 44, row_y))
                screen.blit(cost_s, (sp_panel.right - cost_s.get_width() - 12, row_y))
                pygame.draw.line(screen, (60, 60, 70), (sp_panel.left + 10, row_y + 38), (sp_panel.right - 10, row_y + 38))

        # Potion shared-cooldown percentage for radial overlay (used inside unified bar)
        _potion_cd_elapsed = (pygame.time.get_ticks() - potion_last_used_ms) / 1000.0
        _potion_cd_pct = max(0.0, 1.0 - _potion_cd_elapsed / 0.35) if potion_last_used_ms > 0 else 0.0
        _spell_bar_slot_rects, potion_slot_rects = draw_spell_bar(
            screen, active_spellbook, spell_icons, cooldowns, unlocked_skills,
            player_mana, selected_spell_idx, tiny_font, ui_font,
            class_id=selected_class,
            max_mana=player_max_mana,
            spell_global_cooldown=spell_global_cooldown,
            global_cd_max=GLOBAL_SPELL_COOLDOWN,
            keybinds=spell_slot_keybinds,
            keybind_editing=keybind_editing_slot,
            hp=player_hp,
            max_hp=player_max_hp + bonus_max_hp,
            gold=player_gold,
            player_level=player_level,
            xp=player_xp,
            xp_to_next=player_xp_next,
            item_inventory=item_inventory,
            potion_shared_cd_pct=_potion_cd_pct,
        )
        # WoW-style vertical secondary action bar (right side)
        if not show_spellbook and not show_character and not show_skill_tree:
            draw_spell_bar_vertical(
                screen, full_class_spellbook, active_spellbook,
                spell_icons, cooldowns, unlocked_skills,
                player_mana, tiny_font, class_id=selected_class,
            )
        draw_loot_windows_ui()

        # ── WoW Spellbook Overlay ─────────────────────────────────────────────
        if show_spellbook and not show_world_map and not perk_choice_pending:
            _sb_rects = draw_spellbook_overlay(
                screen, full_class_spellbook, spell_icons, unlocked_skills,
                spellbook_tab, selected_class, tiny_font, ui_font, dialog_name_font,
            )
            # Handle tab clicks via mouse (checked each frame while overlay is open)
            _sb_mouse = pygame.mouse.get_pos()
            _sb_clicked = pygame.mouse.get_pressed(3)[0]
            if _sb_clicked:
                for _tab_key in ("tab_class", "tab_passive", "tab_general"):
                    if _tab_key in _sb_rects and _sb_rects[_tab_key].collidepoint(_sb_mouse):
                        spellbook_tab = _tab_key[4:]   # strip "tab_" prefix

        # Fishing minigame HUD
        if fishing_active:
            _fb_w = 340
            _fb_h = 28
            _fb_x = SCREEN_WIDTH // 2 - _fb_w // 2
            _fb_y = SCREEN_HEIGHT - 210
            # Background bar
            pygame.draw.rect(screen, (14, 12, 20), pygame.Rect(_fb_x - 2, _fb_y - 2, _fb_w + 4, _fb_h + 4), border_radius=8)
            pygame.draw.rect(screen, (30, 28, 40), pygame.Rect(_fb_x, _fb_y, _fb_w, _fb_h), border_radius=6)
            # Catch zone (green)
            _cz_x = _fb_x + int(fishing_catch_zone * _fb_w)
            _cz_w = int(0.22 * _fb_w)
            pygame.draw.rect(screen, (60, 200, 100), pygame.Rect(_cz_x, _fb_y, _cz_w, _fb_h), border_radius=4)
            # Moving bar (white indicator)
            _bar_ix = _fb_x + int(fishing_bar_pos * _fb_w) - 4
            pygame.draw.rect(screen, (255, 255, 255), pygame.Rect(_bar_ix, _fb_y - 2, 8, _fb_h + 4), border_radius=3)
            # Border
            pygame.draw.rect(screen, (140, 200, 240), pygame.Rect(_fb_x - 2, _fb_y - 2, _fb_w + 4, _fb_h + 4), 2, border_radius=8)
            # Timer label
            _ft_s = tiny_font.render(f"FISHING  [{fishing_timer:.1f}s]  SPACE to catch!", True, (200, 240, 255))
            screen.blit(_ft_s, (_fb_x + _fb_w // 2 - _ft_s.get_width() // 2, _fb_y - 22))
        elif fishing_result_timer > 0.0:
            _fr_col = (80, 220, 120) if fishing_result == "success" else (220, 80, 80)
            _fr_txt = tiny_font.render("Caught!" if fishing_result == "success" else "Missed!", True, _fr_col)
            _fr_alpha = int(255 * min(1.0, fishing_result_timer / 0.6))
            _fr_surf = pygame.Surface((_fr_txt.get_width(), _fr_txt.get_height()), pygame.SRCALPHA)
            _fr_surf.blit(_fr_txt, (0, 0)); _fr_surf.set_alpha(_fr_alpha)
            screen.blit(_fr_surf, (SCREEN_WIDTH // 2 - _fr_txt.get_width() // 2, SCREEN_HEIGHT - 220))

        # Near fish rack prompt
        if current_level == "ice_biome" and not fishing_active and not perk_choice_pending:
            _fish_rack_pos2 = Vector2(2768, 1478)
            if player_pos.distance_to(_fish_rack_pos2) <= 180:
                _fp_s = tiny_font.render("[F] Fish at the rack", True, (160, 220, 240))
                screen.blit(_fp_s, (SCREEN_WIDTH // 2 - _fp_s.get_width() // 2, SCREEN_HEIGHT - 170))

        if status_timer > 0.0 and status_line:
            _st = pygame.time.get_ticks()
            _fade = clamp(status_timer / 0.55, 0.0, 1.0)   # fade-out over last 0.55s
            _alpha = int(_fade * 255)

            # Pick accent colour by message content
            _sl = status_line.lower()
            if any(w in _sl for w in ("looted", "gold", "material", "wolf")):
                _accent = (210, 175, 72)   # gold
            elif any(w in _sl for w in ("+hp", "hp.", "health", "restored")):
                _accent = (190, 72, 72)    # red
            elif any(w in _sl for w in ("+mp", "mp.", "mana")):
                _accent = (72, 130, 220)   # blue
            elif any(w in _sl for w in ("damage", "speed", "+20%", "+28%", "+35%")):
                _accent = (220, 140, 60)   # orange
            elif any(w in _sl for w in ("quest", "turned in", "complete")):
                _accent = (120, 220, 120)  # green
            elif any(w in _sl for w in ("skill", "level up", "unlocked")):
                _accent = (170, 110, 240)  # purple
            else:
                _accent = (180, 170, 150)  # neutral

            _txt_surf = ui_font.render(status_line, True, (240, 236, 224))
            _pw = max(280, _txt_surf.get_width() + 60)
            _ph = 28
            _px = SCREEN_WIDTH // 2 - _pw // 2
            _py = 6

            # Background
            _bg = pygame.Surface((_pw, _ph), pygame.SRCALPHA)
            pygame.draw.rect(_bg, (8, 7, 12, int(210 * _fade)), _bg.get_rect(), border_radius=10)
            screen.blit(_bg, (_px, _py))

            # Pulsing gold outer border
            _pb_a = int(_fade * (150 + 60 * math.sin(_st * 0.004)))
            _bord = pygame.Surface((_pw, _ph), pygame.SRCALPHA)
            pygame.draw.rect(_bord, (*_accent, _pb_a), _bord.get_rect(), 1, border_radius=10)
            screen.blit(_bord, (_px, _py))

            # Inner accent glow line (top edge)
            _gl = pygame.Surface((_pw - 16, 1), pygame.SRCALPHA)
            _gl.fill((*_accent, int(60 * _fade)))
            screen.blit(_gl, (_px + 8, _py + 2))

            # Left and right diamond end-caps
            for _ex, _sign in ((_px + 6, -1), (_px + _pw - 6, 1)):
                _ey = _py + _ph // 2
                _dpts = [(_ex, _ey - 4), (_ex + _sign * 4, _ey), (_ex, _ey + 4), (_ex - _sign * 4, _ey)]
                _ds = pygame.Surface((12, 10), pygame.SRCALPHA)
                _doff = (min(_ex, _ex + _sign * 4) - 2, _ey - 5)
                pygame.draw.polygon(screen, (*_accent, _alpha), _dpts)

            # Floating sparkle particles around the bar
            for _pi in range(6):
                _pseed  = _pi * 491 + hash(status_line[:8]) % 997
                _cycle  = ((_st * 0.0004 + _pi * 0.18) % 1.0)
                _pfx    = _px + 10 + (_pseed % (_pw - 20))
                _pfy    = _py + _ph // 2 + math.sin(_st * 0.003 + _pi * 1.1) * 10 - _cycle * 18
                _pa     = int(clamp(math.sin(_cycle * math.pi) * 160 * _fade, 0, 200))
                _psize  = 1 if _pseed % 2 == 0 else 2
                _ps     = pygame.Surface((_psize * 2 + 2, _psize * 2 + 2), pygame.SRCALPHA)
                pygame.draw.circle(_ps, (*_accent, _pa), (_psize + 1, _psize + 1), _psize)
                screen.blit(_ps, (int(_pfx), int(_pfy)))

            # Text with alpha
            _txt_a = pygame.Surface((_txt_surf.get_width(), _txt_surf.get_height()), pygame.SRCALPHA)
            _txt_a.blit(_txt_surf, (0, 0))
            _txt_a.set_alpha(_alpha)
            screen.blit(_txt_a, (SCREEN_WIDTH // 2 - _txt_surf.get_width() // 2,
                                 _py + _ph // 2 - _txt_surf.get_height() // 2))

        if level_banner_timer > 0.0:
            alpha = int(255 * clamp(level_banner_timer / 2.8, 0.0, 1.0))
            banner = font.render(level_banner, True, (236, 236, 236))
            banner.set_alpha(alpha)
            screen.blit(banner, (SCREEN_WIDTH // 2 - banner.get_width() // 2, 16))

        # Teleport book menu
        if teleport_menu_open:
            teleport_menu_rects = draw_teleport_menu(screen)

        # Level-up perk selection screen
        if perk_choice_pending and perk_choices:
            # Dim overlay
            _pov = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            _pov.fill((0, 0, 0, 170))
            screen.blit(_pov, (0, 0))
            # Title
            _pt = font.render(f"LEVEL UP!  Choose a Perk", True, (220, 200, 100))
            screen.blit(_pt, (SCREEN_WIDTH // 2 - _pt.get_width() // 2, 140))
            _psub = ui_font.render(f"You are now Level {player_level}  —  Pick one bonus:", True, (180, 175, 155))
            screen.blit(_psub, (SCREEN_WIDTH // 2 - _psub.get_width() // 2, 180))
            _perk_card_w = 270
            _perk_card_h = 130
            _perk_total_w = len(perk_choices) * (_perk_card_w + 24) - 24
            _perk_start_x = SCREEN_WIDTH // 2 - _perk_total_w // 2
            _perk_rects: List[pygame.Rect] = []
            _mx, _my = pygame.mouse.get_pos()
            for _pi, _perk in enumerate(perk_choices):
                _pr = pygame.Rect(_perk_start_x + _pi * (_perk_card_w + 24), 230, _perk_card_w, _perk_card_h)
                _perk_rects.append(_pr)
                _hovered = _pr.collidepoint(_mx, _my)
                _pcol = tuple(_perk["col"])
                # Card background
                _card = pygame.Surface((_perk_card_w, _perk_card_h), pygame.SRCALPHA)
                pygame.draw.rect(_card, (18, 16, 26, 230), _card.get_rect(), border_radius=12)
                pygame.draw.rect(_card, (*_pcol, 200 if _hovered else 120), _card.get_rect(), 2, border_radius=12)
                if _hovered:
                    _shine = pygame.Surface((_perk_card_w, _perk_card_h), pygame.SRCALPHA)
                    pygame.draw.rect(_shine, (*_pcol, 28), _shine.get_rect(), border_radius=12)
                    _card.blit(_shine, (0, 0))
                screen.blit(_card, _pr.topleft)
                # Perk name
                _pn = ui_font.render(str(_perk["name"]), True, _pcol)
                screen.blit(_pn, (_pr.left + _perk_card_w // 2 - _pn.get_width() // 2, _pr.top + 18))
                # Divider
                pygame.draw.line(screen, (*_pcol, 100), (_pr.left + 20, _pr.top + 44), (_pr.right - 20, _pr.top + 44))
                # Perk desc
                _pd = tiny_font.render(str(_perk["desc"]), True, (210, 210, 210))
                screen.blit(_pd, (_pr.left + _perk_card_w // 2 - _pd.get_width() // 2, _pr.top + 56))
                # Number hint
                _pk = tiny_font.render(f"[{_pi + 1}]", True, (140, 140, 140))
                screen.blit(_pk, (_pr.left + _perk_card_w // 2 - _pk.get_width() // 2, _pr.top + 100))

        if show_skill_tree:
            skill_node_rects = draw_skill_tree(
                screen,
                str(active_class["name"]),
                active_skill_tree,
                unlocked_skills,
                skill_points,
                skill_hover,
                skill_title_font,
                skill_node_font,
                skill_info_font,
                spell_icons,
            )
        else:
            skill_node_rects = {}

        if show_character:
            # Keep character sheet aligned with live runtime values shown in HUD/combat.
            passive_damage_reduction = max(0.0, 1.0 - passive_incoming_damage_mult)
            passive_spell_cdr = max(0.0, 1.0 - passive_spell_cooldown_mult)
            display_stats = {
                "max_hp": player_max_hp,
                "max_mana": player_max_mana,
                "mana_regen": effective_mana_regen_value(ignore_lock=True),
                "armor": 0.0,
                "spell_power": 0.0,
                "basic_damage": float(active_stats.get("basic_damage", 0.0)) * passive_damage_mult,
                "move_speed": passive_move_speed_mult,
                "cooldown_reduction": passive_spell_cdr,
                "damage_reduction": passive_damage_reduction,
            }
            character_slot_rects, char_dropdown_rect, char_option_rects = draw_character_screen(
                screen,
                player_name,
                str(active_class["name"]),
                selected_class,
                equipped_items,
                player_level,
                display_stats,
                char_stat_view,
                char_dropdown_open,
                skill_title_font,
                skill_node_font,
                skill_info_font,
                tiny_font,
                spell_icons,
            )
        else:
            character_slot_rects = {}
            char_dropdown_rect = pygame.Rect(0, 0, 0, 0)
            char_option_rects = {}

        if show_crafting:
            crafting_rects, inv_slot_rects, backpack_slot_rects, inv_tab_rects = draw_inventory_screen(
                screen,
                item_inventory,
                backpack_inventory,
                selected_class,
                materials,
                CRAFTING_RECIPES,
                crafting_selected,
                inv_tab,
                skill_title_font,
                skill_node_font,
                skill_info_font,
                tiny_font,
            )
        else:
            crafting_rects = {}
            inv_slot_rects = {}
            backpack_slot_rects = {}
            inv_tab_rects = {}

        if show_professions:
            crafting_rects, profession_tab_rects, profession_craft_rect = draw_profession_screen(
                screen,
                materials,
                profession_state,
                selected_profession,
                CRAFTING_RECIPES,
                crafting_selected,
                skill_title_font,
                skill_node_font,
                skill_info_font,
                tiny_font,
            )

        if show_quest_log:
            quest_rects = draw_quest_log(
                screen,
                quest_states,
                quest_progress,
                QUEST_DEFINITIONS,
                wolves_slain,
                materials,
                quest_selected,
                quest_actions_from_vendor and current_level == "town",
                quest_vendor_role if quest_actions_from_vendor and current_level == "town" else None,
                skill_title_font,
                skill_node_font,
                skill_info_font,
                tiny_font,
            )
            if quest_actions_from_vendor and quest_selected not in quest_rects:
                quest_selected = None
        else:
            quest_rects = {}

        if show_world_map:
            draw_world_map_overlay(
                screen,
                active_map_cache,
                current_level,
                player_pos,
                facing,
                camera,
                None,
                map_vendor_positions,
                selected_target_pos,
                skill_title_font,
                skill_node_font,
                tiny_font,
            )

        if show_level_decor_editor:
            decor_editor_ui = draw_level_decor_editor_overlay(
                screen,
                current_level,
                available_level_decor_assets(),
                decor_selected_asset_id,
                decor_asset_pack_mode,
                decor_catalog_filter,
                decor_category_filter,
                decor_search_text,
                decor_search_active,
                decor_placement_mode,
                decor_selected_scale,
                decor_selected_rotation,
                decor_editor_scroll,
                skill_title_font,
                ui_font,
                tiny_font,
                placed_count=len(current_level_decor),
                dirty=decor_editor_dirty,
                generate_seed=decor_generate_seed,
                collision_preview=decor_collision_preview,
                ai_prompt=ai_asset_prompt,
                ai_input_active=ai_asset_input_active,
                ai_generating=ai_asset_generating,
                ai_scope=ai_asset_scope,
                clear_pending=clear_decor_confirm,
                panel_side=decor_editor_panel_side,
            )
        else:
            decor_editor_ui = {
                "panel_rect": pygame.Rect(0, 0, 0, 0),
                "save_rect": pygame.Rect(0, 0, 0, 0),
                "reload_rect": pygame.Rect(0, 0, 0, 0),
                "clear_rect": pygame.Rect(0, 0, 0, 0),
                "generate_rect": pygame.Rect(0, 0, 0, 0),
                "demo_rect": pygame.Rect(0, 0, 0, 0),
                "seed_minus_rect": pygame.Rect(0, 0, 0, 0),
                "seed_plus_rect": pygame.Rect(0, 0, 0, 0),
                "pack_rects": {},
                "filter_rects": {},
                "category_rects": {},
                "mode_rects": {},
                "collision_rect": pygame.Rect(0, 0, 0, 0),
                "inspector_rects": {},
                "asset_rects": {},
                "search_rect": pygame.Rect(0, 0, 0, 0),
                "clear_search_rect": pygame.Rect(0, 0, 0, 0),
                "content_height": 0,
                "ai_prompt_rect": pygame.Rect(0, 0, 0, 0),
                "ai_generate_btn_rect": pygame.Rect(0, 0, 0, 0),
                "ai_scope_rects": {},
                "scale_minus_rect": pygame.Rect(0, 0, 0, 0),
                "scale_plus_rect": pygame.Rect(0, 0, 0, 0),
                "rot_minus_rect": pygame.Rect(0, 0, 0, 0),
                "rot_plus_rect": pygame.Rect(0, 0, 0, 0),
            }

        if isinstance(drag_item, dict) and not show_world_map:
            mx, my = pygame.mouse.get_pos()
            ghost = pygame.Rect(mx - 30, my - 30, 60, 60)
            pygame.draw.rect(screen, (20, 20, 26), ghost, border_radius=8)
            icon = resolve_item_icon(drag_item, 50)
            if isinstance(icon, pygame.Surface):
                screen.blit(icon, (ghost.left + 5, ghost.top + 5))
            else:
                pygame.draw.rect(screen, drag_item.get("color", (176, 176, 184)), ghost.inflate(-12, -12), border_radius=6)
            blocked = item_blocked_for_class(drag_item, selected_class)
            if blocked:
                pygame.gfxdraw.box(screen, ghost, (140, 24, 24, 96))
            pygame.draw.rect(screen, (196, 70, 70) if blocked else item_rarity_border(drag_item), ghost, 2, border_radius=8)

        mouse_down = pygame.mouse.get_pressed(3)
        cursor_surface = gothic_cursor_surface
        cursor_hotspot = gothic_cursor_hotspot
        # Swap to pouch cursor when hovering over a vendor in town
        _mpos = pygame.mouse.get_pos()
        if universal_delete_mode:
            cursor_surface = delete_cursor_surface
            cursor_hotspot = delete_cursor_hotspot
            # Red border + "DELETE MODE" indicator
            _del_pulse = int(140 + 60 * math.sin(pygame.time.get_ticks() * 0.004))
            pygame.draw.rect(screen, (_del_pulse, 30, 30), (0, 0, SCREEN_WIDTH, SCREEN_HEIGHT), 3)
            _del_txt = ui_font.render("DELETE MODE [DEL to exit]", True, (255, 60, 60))
            _del_bg = pygame.Surface((_del_txt.get_width() + 16, _del_txt.get_height() + 8), pygame.SRCALPHA)
            _del_bg.fill((20, 0, 0, 180))
            screen.blit(_del_bg, (SCREEN_WIDTH // 2 - _del_bg.get_width() // 2, 4))
            screen.blit(_del_txt, (SCREEN_WIDTH // 2 - _del_txt.get_width() // 2, 8))
        elif current_level == "town" and not npc_menu_mode and not show_crafting:
            _world_mouse = Vector2(_mpos[0] + camera.x, _mpos[1] + camera.y)
            _hov_vendor = pick_vendor(_world_mouse)
            if _hov_vendor is not None:
                cursor_surface = pouch_cursor_surface
                cursor_hotspot = pouch_cursor_hotspot
        # ── Delete-confirm dialog (drawn last, on top of everything) ──────────
        _delete_cancel_rect: Optional[pygame.Rect] = None
        if delete_confirm_item is not None:
            _delete_cancel_rect = draw_delete_confirm_dialog(
                screen,
                delete_confirm_item,
                delete_confirm_typed,
                fonts["node"],
                fonts["tiny"],
            )

        cursor_pressed = bool(mouse_down[0] or mouse_down[1] or mouse_down[2])
        draw_gothic_cursor(
            screen,
            cursor_surface,
            cursor_hotspot,
            _mpos,
            cursor_pressed,
        )

        _fps_val = clock.get_fps()
        _fps_col = (120, 240, 140) if _fps_val >= 55 else ((240, 220, 120) if _fps_val >= 40 else (240, 120, 120))
        _fps_txt = tiny_font.render(f"FPS: {_fps_val:.0f}", True, _fps_col)
        _fps_bg = pygame.Surface((_fps_txt.get_width() + 10, _fps_txt.get_height() + 4), pygame.SRCALPHA)
        _fps_bg.fill((0, 0, 0, 140))
        screen.blit(_fps_bg, (8, 8))
        screen.blit(_fps_txt, (13, 10))

        if not death_screen_active and player_max_hp > 0.0:
            hp_ratio_live = clamp(player_hp / player_max_hp, 0.0, 1.0)
            if hp_ratio_live < 0.32:
                sw_v, sh_v = screen.get_size()
                hurt_t = clamp((0.32 - hp_ratio_live) / 0.32, 0.0, 1.0)
                pulse = 0.65 + 0.35 * math.sin(pygame.time.get_ticks() * 0.006)
                alpha_peak = int(clamp(70.0 * hurt_t * pulse, 18.0, 120.0))
                vig_w = max(sw_v // 5, 80)
                left_strip = pygame.Surface((vig_w, sh_v), pygame.SRCALPHA)
                for xp in range(vig_w):
                    falloff = 1.0 - (xp / vig_w)
                    a = int(alpha_peak * falloff * falloff)
                    if a > 0:
                        pygame.draw.line(left_strip, (180, 18, 18, a), (xp, 0), (xp, sh_v))
                screen.blit(left_strip, (0, 0))
                right_strip = pygame.transform.flip(left_strip, True, False)
                screen.blit(right_strip, (sw_v - vig_w, 0))
                vig_h = max(sh_v // 6, 60)
                top_strip = pygame.Surface((sw_v, vig_h), pygame.SRCALPHA)
                for yp in range(vig_h):
                    falloff = 1.0 - (yp / vig_h)
                    a = int(alpha_peak * 0.85 * falloff * falloff)
                    if a > 0:
                        pygame.draw.line(top_strip, (180, 18, 18, a), (0, yp), (sw_v, yp))
                screen.blit(top_strip, (0, 0))
                bottom_strip = pygame.transform.flip(top_strip, False, True)
                screen.blit(bottom_strip, (0, sh_v - vig_h))

        if death_screen_active:
            sw, sh = screen.get_size()
            fade_t = clamp(death_screen_timer / 1.2, 0.0, 1.0)
            veil = pygame.Surface((sw, sh), pygame.SRCALPHA)
            veil.fill((8, 0, 0, int(220 * fade_t)))
            screen.blit(veil, (0, 0))
            vignette_radius = int(max(sw, sh) * (0.92 - 0.32 * fade_t))
            vignette = pygame.Surface((sw, sh), pygame.SRCALPHA)
            pygame.draw.circle(vignette, (0, 0, 0, 0), (sw // 2, sh // 2), vignette_radius)
            vignette.fill((0, 0, 0, int(140 * fade_t)), special_flags=pygame.BLEND_RGBA_MAX)
            try:
                big_font = pygame.font.SysFont("serif", 128, bold=True)
            except Exception:
                big_font = pygame.font.Font(None, 128)
            try:
                sub_font = pygame.font.SysFont("serif", 24, italic=True)
            except Exception:
                sub_font = pygame.font.Font(None, 28)
            title_alpha = int(255 * clamp((death_screen_timer - 0.3) / 1.0, 0.0, 1.0))
            title_color = (168, 18, 18)
            title = big_font.render("YOU DIED", True, title_color)
            title.set_alpha(title_alpha)
            shadow = big_font.render("YOU DIED", True, (0, 0, 0))
            shadow.set_alpha(int(title_alpha * 0.85))
            tx = sw // 2 - title.get_width() // 2
            ty = sh // 2 - title.get_height() // 2 - 20
            screen.blit(shadow, (tx + 4, ty + 6))
            screen.blit(title, (tx, ty))
            if death_screen_timer >= 0.6:
                pulse = 0.65 + 0.35 * math.sin(death_screen_timer * 3.2)
                hint = sub_font.render("Click or press Space to continue", True, (220, 210, 200))
                hint.set_alpha(int(clamp(200 * pulse, 80, 230)))
                hx = sw // 2 - hint.get_width() // 2
                hy = ty + title.get_height() + 40
                screen.blit(hint, (hx, hy))

        pygame.display.flip()


def choose_launch_mode(
    screen: pygame.Surface,
    clock: pygame.time.Clock,
    fonts: Dict[str, pygame.font.Font],
) -> Optional[str]:
    title_font = fonts["title"]
    item_font = fonts["node"]
    hint_font = fonts["tiny"]

    options = [
        ("single", "Singleplayer"),
        ("quit", "Quit"),
    ]
    selected = 0

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return None
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return None
                if event.key in (pygame.K_UP, pygame.K_w):
                    selected = (selected - 1) % len(options)
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    selected = (selected + 1) % len(options)
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    chosen = options[selected][0]
                    return None if chosen == "quit" else chosen
                elif event.key in (pygame.K_1, pygame.K_2):
                    idx = int(event.key - pygame.K_1)
                    if 0 <= idx < len(options):
                        chosen = options[idx][0]
                        return None if chosen == "quit" else chosen
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                base_y = SCREEN_HEIGHT // 2 - 80
                for idx, _ in enumerate(options):
                    r = pygame.Rect(SCREEN_WIDTH // 2 - 240, base_y + idx * 74, 480, 56)
                    if r.collidepoint((mx, my)):
                        chosen = options[idx][0]
                        return None if chosen == "quit" else chosen

        draw_vertical_gradient(screen, pygame.Rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT), (8, 10, 16), (22, 26, 36))
        title = title_font.render("Sangeroasa", True, (238, 220, 188))
        subtitle = item_font.render("Choose Mode", True, (188, 182, 170))
        screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 96))
        screen.blit(subtitle, (SCREEN_WIDTH // 2 - subtitle.get_width() // 2, 164))

        base_y = SCREEN_HEIGHT // 2 - 80
        mouse_pos = pygame.mouse.get_pos()
        for idx, (_, label) in enumerate(options):
            rect = pygame.Rect(SCREEN_WIDTH // 2 - 240, base_y + idx * 74, 480, 56)
            hovered = rect.collidepoint(mouse_pos)
            focused = idx == selected
            bg = (54, 46, 42) if focused else ((40, 36, 38) if hovered else (24, 26, 32))
            border = (220, 180, 108) if focused else ((142, 132, 112) if hovered else (74, 80, 98))
            pygame.draw.rect(screen, bg, rect, border_radius=10)
            pygame.draw.rect(screen, border, rect, 2 if focused else 1, border_radius=10)
            txt = item_font.render(f"{idx + 1}. {label}", True, (236, 230, 212) if focused else (188, 196, 212))
            screen.blit(txt, (rect.centerx - txt.get_width() // 2, rect.centery - txt.get_height() // 2))

        hint = hint_font.render("Use arrows + Enter, number keys, or mouse. Esc quits.", True, (142, 152, 172))
        screen.blit(hint, (SCREEN_WIDTH // 2 - hint.get_width() // 2, SCREEN_HEIGHT - 58))
        pygame.display.flip()
        clock.tick_busy_loop(FPS)


def main() -> None:
    # tools/generate_medieval_assets.py sets SDL_VIDEODRIVER=dummy at import time;
    # remove it so pygame uses the real display driver.
    os.environ.pop("SDL_VIDEODRIVER", None)
    pygame.mixer.pre_init(12000, -16, 2, 512)
    pygame.init()
    pygame.display.set_caption("Sangeroasa")
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.DOUBLEBUF, vsync=1)
    pygame.mouse.set_visible(True)
    clock = pygame.time.Clock()

    # Bring window to foreground on Windows (prevents focus-stealing prevention from hiding it)
    try:
        import ctypes
        hwnd = pygame.display.get_wm_info().get("window")
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            ctypes.windll.user32.SetForegroundWindow(hwnd)
    except Exception:
        pass
    
    # Fonts
    fonts = {
        "main": pygame.font.SysFont("georgia", 26, bold=True),
        "ui": pygame.font.SysFont("georgia", 20),
        "tiny": pygame.font.SysFont("georgia", 16, bold=True),
        "npc_name": pygame.font.SysFont("georgia", 10),
        "dialog_name": pygame.font.SysFont("georgia", 24, bold=True),
        "dialog_text": pygame.font.SysFont("georgia", 20),
        "skill_title": pygame.font.SysFont("georgia", 36, bold=True),
        "node": pygame.font.SysFont("georgia", 20, bold=True),
        "info": pygame.font.SysFont("georgia", 17),
        "title": pygame.font.SysFont("georgia", 48, bold=True),
    }
    
    audio = GameAudio()
    audio.init()
    load_ui_assets()

    # Load Assets
    rogue_choices = load_rogue_choices(49)
    if not rogue_choices:
        fallback = pygame.Surface((96, 96), pygame.SRCALPHA)
        pygame.draw.rect(fallback, (130, 130, 140), (20, 10, 56, 76))
        pygame.draw.rect(fallback, (28, 28, 30), (20, 10, 56, 76), 2)
        fallback_left = pygame.transform.flip(fallback, True, False)
        rogue_choices = [{"name": "default rogue", "sprite": fallback, "sprite_left": fallback_left, "preview": fallback}]

    class_visuals = build_class_visuals(rogue_choices)
    screen.fill((12, 14, 18))
    loading_text = fonts["main"].render("Generating World...", True, (200, 200, 210))
    screen.blit(loading_text, (SCREEN_WIDTH // 2 - loading_text.get_width() // 2, SCREEN_HEIGHT // 2 - 20))
    pygame.display.flip()

    _initial_prop_deletions = load_prop_deletions()
    town_surface, town_obstacles, town_canals, town_prop_registry, town_house_overlays, town_foliage_anim, town_road_rects, town_farm_pens = build_town_scene(size=(WORLD_WIDTH, WORLD_HEIGHT), deleted_props=_initial_prop_deletions)
    # Chimney tops for smoke VFX — exported by build_town_scene from the REAL
    # placed houses (the old approximated grid here predated the district
    # rebuild and made smoke rise from empty ground).
    town_chimney_tops: List[Tuple[int, int]] = list(_TOWN_CHIMNEY_TOPS)
    wilderness_surface, wilderness_obstacles, wilderness_spawn_points = build_wilderness_scene(size=(WILDERNESS_WIDTH, WILDERNESS_HEIGHT))
    ice_surface, ice_obstacles, ice_spawn_points = build_ice_biome_scene(size=(ICE_WIDTH, ICE_HEIGHT))
    predator_archetypes, prey_archetypes = load_animals_sheet() # Fixed
    ice_predators, ice_passives = load_ice_archetypes()
    vendor_archetypes = load_vendor_archetypes()

    fire_frames = load_fire_animation()
    level_decor_assets = load_level_decor_assets()
    level_decor_layout = load_level_decor_layout()

    lpc_wolf_frames = None
    assets = {
        "rogue_choices": rogue_choices,
        "class_visuals": class_visuals,
        "town_surface": town_surface,
        "town_obstacles": town_obstacles,
        "town_canals": town_canals,
        "town_prop_registry": town_prop_registry,
        "town_house_overlays": town_house_overlays,
        "town_foliage_anim": town_foliage_anim,
        "town_road_rects": town_road_rects,
        "town_farm_pens": town_farm_pens,
        "wilderness_surface": wilderness_surface,
        "wilderness_obstacles": wilderness_obstacles,
        "wilderness_spawn_points": wilderness_spawn_points,
        "ice_surface": ice_surface,
        "ice_obstacles": ice_obstacles,
        "ice_spawn_points": ice_spawn_points,
        "ice_predators": ice_predators,
        "ice_passives": ice_passives,
        "town_walk_bounds": pygame.Rect(70, HORIZON_Y + 92, WORLD_WIDTH - 140, WORLD_HEIGHT - (HORIZON_Y + 172)),
        "wilderness_walk_bounds": pygame.Rect(70, HORIZON_Y + 92, WILDERNESS_WIDTH - 140, WILDERNESS_HEIGHT - (HORIZON_Y + 172)),
        "ice_walk_bounds": pygame.Rect(70, HORIZON_Y + 92, ICE_WIDTH - 140, ICE_HEIGHT - (HORIZON_Y + 172)),
        "spell_icons": load_spell_icons(),
        "external_item_library": build_external_item_library(),
        "predator_archetypes": predator_archetypes,
        "prey_archetypes": prey_archetypes,
        "vendor_archetypes": vendor_archetypes,

        "fire_frames": fire_frames,
        "level_decor_assets": level_decor_assets,
        "level_decor_layout": level_decor_layout,
        "lpc_wolf_frames": lpc_wolf_frames,
        "town_chimney_tops": town_chimney_tops,
    }
    # App Loop
    quit_requested = False
    force_character_picker = False
    while not quit_requested:
        saves = load_all_saves()
        if len(saves) == 1 and not force_character_picker:
            selected_idx = 0
        else:
            selected_idx = character_selection_screen(screen, clock, saves, class_visuals, fonts)
            if selected_idx is None:
                break

        character_data: Dict[str, object]
        if selected_idx == -1:
            pygame.mouse.set_visible(True)
            new_class = choose_class(screen, clock, class_visuals, 0)
            selected_entry = resolve_class_visual_entry(class_visuals, new_class, 1, rogue_choices[0])
            sprite = selected_entry.get("sprite")
            if not isinstance(sprite, pygame.Surface):
                sprite = rogue_choices[0]["sprite"]
            new_name = choose_character_name(screen, clock, sprite, str(CLASS_ARCHETYPES[new_class].get("name", "Hero")))
            pygame.mouse.set_visible(False)
            character_data = {
                "class": new_class,
                "player_name": new_name,
                "player_level": 1,
                "created_at": pygame.time.get_ticks(),
            }
            saves.append(character_data)
            save_all_saves(saves)
        else:
            character_data = saves[selected_idx]

        result = run_session(
            screen,
            clock,
            audio,
            fonts,
            assets,
            character_data,
            save_callback=lambda: save_all_saves(saves),
        )
        save_all_saves(saves)
        if result == "QUIT":
            quit_requested = True
        elif result != "MENU":
            break
        else:
            force_character_picker = True

    pygame.mouse.set_visible(True)
    pygame.quit()


if __name__ == "__main__":
    main()
