"""game/world/level_decor.py — level-decor asset pack, catalog, layouts, IO,
archetype/sprite loaders, and the in-game level-decor editor overlay."""
import os
import json
import math
import random
from typing import Dict, List, Optional, Tuple, Any, Union, Set

import pygame
from pygame import Vector2

from game.constants import *
from game.utils import *
from game.nav import *
from game.vfx import *
from game.gameplay_math import *
from game.sprites import *
from game.assets import *
from game.assets import _scale_surface_to_fit, _humanize_catalog_asset_id
from game.items import *
from game.render.props import *
from game.render.glyphs import *
from game.render.shops import *
from game.farm import *
from game.entities import *
from game.vendors import *
from game.ui.hud import *

__all__ = [
    'ensure_level_decor_folders',
    '_level_decor_display_name',
    '_level_decor_group_name',
    'load_medieval_generated_asset_manager',
    'merge_generated_assets_into_level_decor_assets',
    '_prepare_alpha_surface',
    '_draw_with_seed',
    '_render_builtin_decor_surface',
    'build_builtin_level_decor_pack',
    'load_level_decor_assets',
    'load_prop_deletions',
    'save_prop_deletions',
    'save_church_position',
    'load_level_decor_layout',
    'load_npc_positions',
    'load_blacksmith_shop_anchor_record',
    'load_blacksmith_shop_anchor',
    'save_blacksmith_shop_anchor',
    'resolve_blacksmith_shop_anchor',
    'save_npc_positions',
    'save_level_decor_layout',
    'level_decor_catalog',
    'level_decor_asset_lookup',
    'load_wolf_sprites',
    'load_menacing_archetypes',
    'load_passive_archetypes',
    'load_fire_animation',
    'load_animals_sheet',
    'load_ice_archetypes',
    'level_decor_asset_layer',
    'level_decor_asset_preview_surface',
    'level_decor_asset_uses_tile_brush',
    'level_decor_asset_uses_scatter',
    'snap_editor_point_to_grid',
    'road_autotile_id_for_mask',
    'frozen_road_autotile_id_for_mask',
    'get_level_decor_collision_rect',
    'build_medieval_demo_layout',
    'build_frozen_tundra_layout',
    'get_level_decor_instance_surface',
    'get_level_decor_instance_anchor',
    'get_level_decor_instance_rect',
    'draw_level_decor_instance',
    'draw_level_decor_editor_overlay',
]


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
