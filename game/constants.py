"""
game/constants.py
All tuning constants and path definitions for Raven Hollow RPG.
These are extracted here from main.py to serve as the canonical source of truth.
Import in any module with:  from game.constants import *
"""
import os

# ── Display ───────────────────────────────────────────────────────────────────
SCREEN_WIDTH  = 1400
SCREEN_HEIGHT = 840
FPS           = 60

# ── World sizes (pixels) ──────────────────────────────────────────────────────
WORLD_WIDTH       = 10000
WORLD_HEIGHT      = 7000
WILDERNESS_WIDTH  = 6400
WILDERNESS_HEIGHT = 4400
ICE_WIDTH         = 6400
ICE_HEIGHT        = 4400

# ── Scene constants ───────────────────────────────────────────────────────────
HORIZON_Y = 360          # Y pixel where sky meets ground

# ── Collision radii (pixels) ──────────────────────────────────────────────────
PLAYER_COLLISION_RADIUS = 18.0
WOLF_COLLISION_RADIUS   = 15.0
VENDOR_COLLISION_RADIUS = 18.0

# ── Navigation ────────────────────────────────────────────────────────────────
NAV_CELL_SIZE = 34

# ── Asset paths ───────────────────────────────────────────────────────────────
LEVEL_DECOR_ROOT            = os.path.join("assets", "level_decor")
LEVEL_DECOR_LAYOUT_PATH     = os.path.join(LEVEL_DECOR_ROOT, "layout.json")
NPC_POSITIONS_PATH          = os.path.join(LEVEL_DECOR_ROOT, "npc_positions.json")
LEVEL_DECOR_PACK_ROOT       = os.path.join("assets", "generated_town")
MEDIEVAL_PACK_ROOT          = os.path.join("assets_generated", "medieval_rpg")
MEDIEVAL_PACK_CATALOG_PATH  = os.path.join(MEDIEVAL_PACK_ROOT, "catalog.json")
MEDIEVAL_PACK_OVERRIDES_PATH= os.path.join(MEDIEVAL_PACK_ROOT, "catalog_overrides.json")
MEDIEVAL_DEMO_LEVEL_PATH    = os.path.join("levels", "demo_medieval_rpg.json")

# ── Editor ────────────────────────────────────────────────────────────────────
LEVEL_DECOR_SCOPES           = ("shared", "town", "wilderness")
LEVEL_DECOR_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
DECOR_EDITOR_PANEL_WIDTH     = 700
DECOR_EDITOR_GRID_SIZE       = 32

# ── Warrior sprite asset paths ────────────────────────────────────────────────
WARRIOR_ASSET_ROOT = os.path.join("assets", "classes", "warrior", "PNG")
WARRIOR_ROW_TO_DIRECTION = ("right", "down", "left", "up")
WARRIOR_TIER_LEVEL_THRESHOLDS = ((20, 3), (10, 2), (1, 1))
WARRIOR_SPRITE_ACTION_FILES = (
    ("idle",        "Idle"),
    ("walk",        "Walk"),
    ("run",         "Run"),
    ("attack",      "attack"),
    ("walk_attack", "Walk_Attack"),
    ("run_attack",  "Run_Attack"),
    ("hurt",        "Hurt"),
    ("death",       "Death"),
)
WARRIOR_NON_LOOPING_STATES = frozenset({"attack", "walk_attack", "run_attack", "hurt", "death"})

# ── Save path ─────────────────────────────────────────────────────────────────
SAVE_PATH = os.path.join(os.path.expanduser("~"), "raven_hollow_save.json")

# ── Inventory ─────────────────────────────────────────────────────────────────
BACKPACK_SLOT_COUNT = 20
