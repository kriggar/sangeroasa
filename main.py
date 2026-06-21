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
from game.world.level_decor import *  # level-decor pack/catalog/layouts/IO/editor
from game.ui.hud import *  # HUD + in-game UI screens
from game.ui.hud import draw_hand_cursor, update_and_draw_cursor_fx  # animated cursor + click VFX (not in __all__)
from game.ui.screens import *  # pre-game screens + ultimate factory
from game.world.scenes import *  # scene builders
from game.loaders import *  # rogue/class-visual/vendor/NPC loaders
from game.combat.spellcast import *  # spell casting + effects
from game.vendors import *  # vendor placement/update/render
from game.farm import *  # farm animals + rendering
from game.ui.charcreate import *  # character creation screens
from game.entities import *  # enemies/wolves/skeletons/animals/portals
from game.sprites import *  # sprite/anim/class-visual/recolour/movement helpers
from game.sprites import build_procedural_anim_frames  # procedural per-state anims (not in __all__)
from game.gameplay_math import *  # gameplay math helpers
from game.render.shops import *  # vendor shop draw functions
from game.render.glyphs import *  # tool/item glyph icons
from game.classes_runtime import *  # class spellbook/skill-tree/passive helpers

# Per-renderer caches whose only users (draw_hover_tooltip / build_class_passive_icon) live here.

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




















# ═══════════════════════════════════════════════════════════════════
# LIVE FARM ANIMALS — animated chickens, pigs, sheep inside pens
# ═══════════════════════════════════════════════════════════════════





# ── Palette-swap helpers ──────────────────────────────────────────────────────









# ─── AAA HUD: persistent state for damage / spend flashes & lerping bars ───






_RESOURCE_BAR_ASSETS: Optional[Dict[str, pygame.Surface]] = None



from game.systems.core import (DayNightCycle, WeatherSystem, damage_wolf_entity, draw_point_light, point_segment_distance_sq, circle_hits_segment, ParticleEmitter, StatusEffect, StatusEffectSystem, ScreenEffectController, QuestCelebrationVFX, LevelUpVFX, CameraDirector, AmbientOverlaySystem)  # runtime systems


from game.combat.ultimates import (UltimateContext, UltimateBase, MageBeamUltimate, MageCataclysmUltimate, RogueTeleportUltimate, RangerStormUltimate, NecromancerSummonUltimate, WarriorDashUltimate, PaladinTransformationUltimate)




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
    try:
        _hand_cursor_img = pygame.image.load("assets/cursor/cursor_gauntlet.png").convert_alpha()
        gothic_cursor_surface = _hand_cursor_img
        # Hotspot = the pointing tip (topmost-leftmost opaque pixel).
        _hx, _hy = _hand_cursor_img.get_width() // 2, 0
        _cw, _ch = _hand_cursor_img.get_width(), _hand_cursor_img.get_height()
        _found = False
        for _yy in range(_ch):
            for _xx in range(_cw):
                if _hand_cursor_img.get_at((_xx, _yy)).a > 40:
                    _hx, _hy = _xx, _yy
                    _found = True
                    break
            if _found:
                break
        gothic_cursor_hotspot = (_hx, _hy)
    except Exception:
        pass
    cursor_fx: List[Dict[str, object]] = []  # screen-space click ripples
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

        # Rogue has no hand-drawn sheet — synthesize a full procedural animation set
        # (idle/walk/run/attack/walk_attack/run_attack/hurt/death) from its single sprite.
        if selected_class == "rogue":
            player_anim_frames, player_anim_fps, player_anim_durations = build_procedural_anim_frames(
                player_sprite, player_sprite_left
            )
            base_player_anim_frames = player_anim_frames

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
        # Rogue: regenerate procedural animations from the recolored sprite.
        if selected_class == "rogue":
            player_anim_frames = build_procedural_anim_frames(player_sprite, player_sprite_left)[0]

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
    _frozen_snapshot = None  # cached world+HUD frame reused while a full-screen menu is open
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
            if event.type == pygame.MOUSEBUTTONDOWN and event.button in (1, 3):
                cursor_fx.append({"pos": event.pos, "t": 0.0, "btn": event.button})
                if audio is not None:
                    audio.play_sfx("ui_click", cooldown_ms=40)
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
            # Skip farm-animal AI (wander + separation solver) when far from every pen —
            # off-screen animals don't need simulating and aren't visible.
            if any(isinstance(_a.get("pos"), Vector2) and player_pos.distance_to(_a["pos"]) < 1100.0
                   for _a in farm_animals):
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

        _frozen_menu = (show_skill_tree or show_character or show_crafting or show_quest_log or show_professions or show_world_map)
        _skip_world = _frozen_menu and _frozen_snapshot is not None
        if _skip_world:
            screen.blit(_frozen_snapshot, (0, 0))
        if not _skip_world:
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
                    # Viewport cull: shop stands are large and expensive to draw; skip any
                    # whose footprint is fully off-screen (generous margin for big buildings).
                    if (_shop_screen.x < -480 or _shop_screen.x > SCREEN_WIDTH + 480 or
                            _shop_screen.y < -640 or _shop_screen.y > SCREEN_HEIGHT + 320):
                        _vendor_behind_flags.append(False)
                        continue
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
                    _fa_pos = _fa_entry.get("pos")
                    if isinstance(_fa_pos, Vector2) and (
                            _fa_pos.x - camera.x < -120 or _fa_pos.x - camera.x > SCREEN_WIDTH + 120 or
                            _fa_pos.y - camera.y < -120 or _fa_pos.y - camera.y > SCREEN_HEIGHT + 120):
                        continue
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

            if _frozen_menu:
                _frozen_snapshot = screen.copy()
        if not _frozen_menu:
            _frozen_snapshot = None
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
        _cursor_hover = False
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
                _cursor_hover = True
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
        update_and_draw_cursor_fx(screen, cursor_fx, dt)
        if universal_delete_mode:
            draw_gothic_cursor(screen, cursor_surface, cursor_hotspot, _mpos, cursor_pressed)
        else:
            draw_hand_cursor(screen, cursor_surface, cursor_hotspot, _mpos, ticks, _cursor_hover, cursor_pressed)

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
