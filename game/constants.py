"""
game/constants.py — canonical tuning constants and asset paths for Sangeroasa.

Single source of truth. main.py imports these with:  from game.constants import *
Do not redefine these values elsewhere.
"""
import os

# ── Display ───────────────────────────────────────────────────────────────────
SCREEN_WIDTH = 1400
SCREEN_HEIGHT = 840
FPS = 60
FRAME_DT = 1.0 / FPS  # fixed simulation timestep — keeps gameplay speed constant when framerate dips

# ── World sizes (pixels) ──────────────────────────────────────────────────────
WORLD_WIDTH = 10000
WORLD_HEIGHT = 7000
WILDERNESS_WIDTH = 6400
WILDERNESS_HEIGHT = 4400
ICE_WIDTH = 6400
ICE_HEIGHT = 4400

# ── Scene constants ───────────────────────────────────────────────────────────
HORIZON_Y = 360          # Y pixel where sky meets ground

# ── Collision radii (pixels) ──────────────────────────────────────────────────
PLAYER_COLLISION_RADIUS = 18.0
WOLF_COLLISION_RADIUS = 15.0
VENDOR_COLLISION_RADIUS = 18.0
VENDOR_SHOP_COLLISION_RADIUS = 120.0

# ── Vendor / shop layout ──────────────────────────────────────────────────────
VENDOR_LAYOUT_MODE = "scatter"  # "scatter" (spread across town) or "circle" (backup ring)
# Shops scattered across the town (far apart, houses between them).
# Northwest — forge district
BLACKSMITH_SHOP_ANCHOR_OFFSET = (-3400, 840)
BLACKSMITH_VENDOR_OFFSET = (0, 110)
BLACKSMITH_SHOP_ANCHOR_MODE = "lamppost"  # "player_always", "player_once", or "lamppost"
# North-center — bakery square
BAKER_SHOP_ANCHOR_OFFSET = (-800, 640)
BAKER_VENDOR_OFFSET = (0, 110)
# Northeast — tailor quarter
TAILOR_SHOP_ANCHOR_OFFSET = (2000, 840)
TAILOR_VENDOR_OFFSET = (0, 110)
# West — alchemist grove
ALCHEMIST_SHOP_ANCHOR_OFFSET = (-3600, 2440)
ALCHEMIST_VENDOR_OFFSET = (0, 110)
# Center — merchant plaza (near arena)
MERCHANT_SHOP_ANCHOR_OFFSET = (0, 2040)
MERCHANT_VENDOR_OFFSET = (0, 110)
# East — leatherworker yard
LEATHERWORKER_SHOP_ANCHOR_OFFSET = (3600, 2440)
LEATHERWORKER_VENDOR_OFFSET = (0, 110)
# Southwest — herbalist garden
HERBALIST_SHOP_ANCHOR_OFFSET = (-3000, 4040)
HERBALIST_VENDOR_OFFSET = (0, 110)
# South-center — miller's corner
MILLER_SHOP_ANCHOR_OFFSET = (0, 3840)
MILLER_VENDOR_OFFSET = (0, 110)
# Southeast — cooper's workshop
COOPER_SHOP_ANCHOR_OFFSET = (3000, 4040)
COOPER_VENDOR_OFFSET = (0, 110)
# South gate west — guard post
GUARD_SHOP_ANCHOR_OFFSET = (-1500, 5240)
GUARD_VENDOR_OFFSET = (0, 110)
# South gate east — tanner
TANNER_SHOP_ANCHOR_OFFSET = (1500, 5240)
TANNER_VENDOR_OFFSET = (0, 110)
# East coast — harbour / sailor
SAILOR_SHOP_ANCHOR_OFFSET = (4200, 1440)
SAILOR_VENDOR_OFFSET = (0, 110)

# ── Navigation ────────────────────────────────────────────────────────────────
NAV_CELL_SIZE = 34

# ── Asset / level-decor paths (relative to repo root; main.py chdirs there) ────
LEVEL_DECOR_ROOT = os.path.join("assets", "level_decor")
LEVEL_DECOR_LAYOUT_PATH = os.path.join(LEVEL_DECOR_ROOT, "layout.json")
PROP_DELETIONS_PATH = os.path.join(LEVEL_DECOR_ROOT, "prop_deletions.json")
NPC_POSITIONS_PATH = os.path.join(LEVEL_DECOR_ROOT, "npc_positions.json")
CHURCH_POSITION_PATH = os.path.join(LEVEL_DECOR_ROOT, "church_position.json")
BLACKSMITH_SHOP_ANCHOR_PATH = os.path.join(LEVEL_DECOR_ROOT, "blacksmith_shop.json")
LEVEL_DECOR_PACK_ROOT = os.path.join("assets", "generated_town")
MEDIEVAL_PACK_ROOT = os.path.join("assets_generated", "medieval_rpg")
MEDIEVAL_PACK_CATALOG_PATH = os.path.join(MEDIEVAL_PACK_ROOT, "catalog.json")
MEDIEVAL_PACK_OVERRIDES_PATH = os.path.join(MEDIEVAL_PACK_ROOT, "catalog_overrides.json")
MEDIEVAL_DEMO_LEVEL_PATH = os.path.join("levels", "demo_medieval_rpg.json")

# ── Level-decor editor ────────────────────────────────────────────────────────
LEVEL_DECOR_SCOPES = ("shared", "town", "wilderness")
LEVEL_DECOR_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
DECOR_EDITOR_PANEL_WIDTH = 340
DECOR_EDITOR_GRID_SIZE = 32

# ── Warrior sprite asset config ───────────────────────────────────────────────
WARRIOR_ASSET_ROOT = os.path.join("assets", "classes", "warrior", "PNG")
WARRIOR_ROW_TO_DIRECTION = ("right", "down", "left", "up")
WARRIOR_TIER_LEVEL_THRESHOLDS = ((20, 3), (10, 2), (1, 1))
WARRIOR_SPRITE_ACTION_FILES = (
    ("idle", "Idle"),
    ("walk", "Walk"),
    ("run", "Run"),
    ("attack", "attack"),
    ("walk_attack", "Walk_Attack"),
    ("run_attack", "Run_Attack"),
    ("hurt", "Hurt"),
    ("death", "Death"),
)
WARRIOR_NON_LOOPING_STATES = {"attack", "walk_attack", "run_attack", "hurt", "death"}

# ── Save path & inventory sizes ───────────────────────────────────────────────
SAVE_PATH = os.path.join(os.path.expanduser("~"), "sangeroasa_save.json")
HOTBAR_SLOT_COUNT = 8
BACKPACK_SLOT_COUNT = 24
