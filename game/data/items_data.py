"""game/data/items_data.py — item & equipment data tables (pure data)."""
from typing import Dict, List, Tuple, Any, Set

EQUIPMENT_SLOT_ORDER = ["head", "chest", "pants", "hands", "feet", "weapon", "offhand", "amulet", "ring", "belt"]

EQUIPMENT_SLOT_LABELS = {
    "head": "Head",
    "chest": "Chest",
    "pants": "Pants",
    "hands": "Hands",
    "feet": "Feet",
    "weapon": "Weapon",
    "offhand": "Offhand",
    "amulet": "Amulet",
    "ring": "Ring",
    "belt": "Belt",
}

ITEM_RARITY_COLORS: Dict[str, Tuple[int, int, int]] = {
    "common": (120, 120, 132),
    "rare": (88, 144, 236),
    "epic": (174, 108, 220),
    "legendary": (232, 164, 72),
    # Backward compatibility for old item data.
    "magic": (88, 144, 236),
    "set": (174, 108, 220),
}

EQUIP_STAT_KEYS = [
    "max_hp",
    "max_mana",
    "mana_regen",
    "spell_power",
    "basic_damage",
    "armor",
    "damage_reduction",
    "move_speed",
    "cooldown_reduction",
]

ITEM_STAT_LABELS: Dict[str, str] = {
    "max_hp": "Max HP",
    "max_mana": "Max Mana",
    "mana_regen": "Mana Regen",
    "spell_power": "Spell Power",
    "basic_damage": "Basic Damage",
    "armor": "Armor",
    "damage_reduction": "Damage Reduction",
    "move_speed": "Move Speed",
    "cooldown_reduction": "Cooldown Reduction",
}

ITEM_EFFECT_TOOLTIPS: Dict[str, str] = {
    "hp_80": "Restore 80 HP.",
    "hp_60": "Restore 60 HP.",
    "hp_25": "Restore 25 HP.",
    "mp_80": "Restore 80 mana.",
    "mp_full": "Restore all mana.",
    "full_restore": "Fully restore HP and mana.",
    "dmg_boost": "Gain +20% damage for 90s.",
    "dmg_boost_120": "Gain +35% damage for 120s.",
    "speed_boost_60": "Gain +28% move speed for 60s.",
    "max_hp_15": "Permanently gain +15 max HP (up to 3 stacks).",
    "mana_regen_05": "Permanently gain +0.5 mana regen/s (up to 3 stacks).",
    "skill_point": "Gain +1 skill point.",
    "town_portal": "Return to Sangeroasa through a town portal.",
}

POTION_BAR_ALLOWED_EFFECTS: Set[str] = {
    "hp_25",
    "hp_60",
    "hp_80",
    "mp_80",
    "mp_full",
    "full_restore",
    "dmg_boost",
    "dmg_boost_120",
    "speed_boost_60",
    "teleport_book",
}

ITEM_SHEET_SLOT_HINTS: Dict[Tuple[int, int], str] = {}

CLASS_ARMOR_SETS: Dict[str, Dict[str, object]] = {
    "mage": {
        "set_name": "Astralweave Regalia",
        "pieces": [
            {"slot": "head", "name": "Astral Hood", "icon": (15, 2), "color": (90, 120, 210), "stats": {"max_mana": 18.0, "mana_regen": 0.8}},
            {"slot": "chest", "name": "Astral Robe", "icon": (12, 2), "color": (70, 100, 200), "stats": {"spell_power": 10.0, "armor": 8.0}},
            {"slot": "pants", "name": "Astral Legwraps", "color": (78, 108, 208), "stats": {"max_mana": 12.0, "armor": 6.0}},
            {"slot": "hands", "name": "Astral Grips", "icon": (13, 2), "color": (100, 130, 220), "stats": {"cooldown_reduction": 0.03}},
            {"slot": "feet", "name": "Astral Boots", "icon": (14, 2), "color": (80, 110, 200), "stats": {"move_speed": 0.05, "armor": 6.0}},
            {"slot": "weapon", "name": "Crystalfocus Staff", "icon": (10, 7), "color": (140, 180, 240), "stats": {"spell_power": 14.0}},
            {"slot": "amulet", "name": "Pendant of the Rift", "icon": (16, 2), "color": (120, 150, 230), "stats": {"max_mana": 14.0, "mana_regen": 0.7}},
        ],
    },
    "ranger": {
        "set_name": "Wildstalker Gear",
        "pieces": [
            {"slot": "head", "name": "Stalker Hood", "icon": (16, 1), "color": (80, 130, 60), "stats": {"armor": 10.0, "basic_damage": 4.0}},
            {"slot": "chest", "name": "Stalker Tunic", "icon": (13, 1), "color": (70, 120, 50), "stats": {"max_hp": 20.0, "armor": 12.0}},
            {"slot": "pants", "name": "Stalker Leggings", "color": (84, 126, 60), "stats": {"armor": 10.0, "move_speed": 0.04}},
            {"slot": "hands", "name": "Stalker Gloves", "icon": (14, 1), "color": (90, 140, 70), "stats": {"basic_damage": 5.0}},
            {"slot": "feet", "name": "Stalker Boots", "icon": (15, 1), "color": (100, 130, 80), "stats": {"move_speed": 0.06}},
            {"slot": "weapon", "name": "Composite Bow", "icon": (10, 2), "color": (140, 110, 60), "stats": {"basic_damage": 12.0}},
        ],
    },
    "rogue": {
        "set_name": "Nightstalker Harness",
        "pieces": [
            {"slot": "head", "name": "Night Hood", "icon": (15, 1), "color": (90, 75, 120), "stats": {"armor": 12.0, "cooldown_reduction": 0.02}},
            {"slot": "chest", "name": "Night Jacket", "icon": (12, 1), "color": (70, 60, 110), "stats": {"max_hp": 18.0, "armor": 16.0}},
            {"slot": "pants", "name": "Night Trousers", "color": (78, 64, 118), "stats": {"armor": 12.0, "cooldown_reduction": 0.02}},
            {"slot": "hands", "name": "Night Gloves", "icon": (13, 1), "color": (100, 85, 140), "stats": {"spell_power": 7.0}},
            {"slot": "feet", "name": "Night Boots", "icon": (14, 1), "color": (80, 65, 115), "stats": {"move_speed": 0.08, "armor": 10.0}},
            {"slot": "weapon", "name": "Silent Fang", "icon": (0, 7), "color": (150, 140, 170), "stats": {"basic_damage": 6.0, "spell_power": 7.0}},
            {"slot": "ring", "name": "Onyx Signet", "icon": (17, 5), "color": (110, 95, 145), "stats": {"cooldown_reduction": 0.03, "spell_power": 4.0}},
        ],
    },
    "necromancer": {
        "set_name": "Gravebound Vestments",
        "pieces": [
            {"slot": "head", "name": "Grave Cowl", "icon": (15, 0), "color": (90, 60, 110), "stats": {"max_mana": 12.0, "mana_regen": 0.6}},
            {"slot": "chest", "name": "Grave Robe", "icon": (12, 2), "color": (80, 50, 100), "stats": {"max_hp": 12.0, "spell_power": 9.0, "armor": 10.0}},
            {"slot": "pants", "name": "Grave Legwraps", "color": (88, 58, 110), "stats": {"max_mana": 10.0, "armor": 8.0}},
            {"slot": "hands", "name": "Grave Wraps", "icon": (13, 0), "color": (100, 70, 120), "stats": {"spell_power": 8.0}},
            {"slot": "feet", "name": "Grave Slippers", "icon": (14, 0), "color": (85, 55, 105), "stats": {"move_speed": 0.04, "armor": 8.0}},
            {"slot": "weapon", "name": "Red Crystal Rod", "icon": (10, 5), "color": (180, 50, 60), "stats": {"spell_power": 13.0}},
            {"slot": "amulet", "name": "Mourning Locket", "icon": (16, 5), "color": (110, 80, 130), "stats": {"max_mana": 12.0, "mana_regen": 0.7}},
        ],
    },
    "warrior": {
        "set_name": "Ironhowl Plate",
        "pieces": [
            {"slot": "head", "name": "Ironhowl Helm", "icon": (15, 6), "color": (160, 140, 110), "stats": {"armor": 28.0, "max_hp": 18.0}},
            {"slot": "chest", "name": "Ironhowl Chestplate", "icon": (12, 5), "color": (150, 130, 100), "stats": {"armor": 42.0, "max_hp": 28.0}},
            {"slot": "pants", "name": "Ironhowl Legplates", "color": (152, 132, 102), "stats": {"armor": 26.0, "max_hp": 16.0}},
            {"slot": "hands", "name": "Ironhowl Gauntlets", "icon": (13, 3), "color": (170, 150, 120), "stats": {"armor": 20.0, "basic_damage": 5.0}},
            {"slot": "feet", "name": "Ironhowl Greaves", "icon": (14, 3), "color": (155, 135, 105), "stats": {"armor": 24.0, "move_speed": 0.03}},
            {"slot": "weapon", "name": "Packbreaker Axe", "icon": (3, 3), "color": (190, 170, 130), "stats": {"basic_damage": 8.0, "spell_power": 4.0}},
            {"slot": "offhand", "name": "Bastion Shield", "icon": (11, 6), "color": (145, 125, 95), "stats": {"armor": 30.0, "damage_reduction": 0.05}},
        ],
    },
    "paladin": {
        "set_name": "Sunwarden Aegis",
        "pieces": [
            {"slot": "head", "name": "Sunwarden Crown", "icon": (15, 7), "color": (230, 210, 120), "stats": {"armor": 24.0, "max_mana": 10.0}},
            {"slot": "chest", "name": "Sunwarden Mail", "icon": (12, 4), "color": (220, 200, 110), "stats": {"armor": 34.0, "max_hp": 20.0}},
            {"slot": "pants", "name": "Sunwarden Tassets", "color": (228, 206, 118), "stats": {"armor": 22.0, "max_mana": 8.0}},
            {"slot": "hands", "name": "Sunwarden Gauntlets", "icon": (13, 3), "color": (240, 220, 130), "stats": {"armor": 18.0, "cooldown_reduction": 0.02}},
            {"slot": "feet", "name": "Sunwarden Sabatons", "icon": (14, 3), "color": (225, 205, 115), "stats": {"armor": 20.0, "move_speed": 0.03}},
            {"slot": "weapon", "name": "Judicator Spear", "icon": (6, 4), "color": (245, 230, 140), "stats": {"basic_damage": 6.0, "spell_power": 6.0}},
            {"slot": "offhand", "name": "Sanctified Shield", "icon": (11, 2), "color": (235, 215, 125), "stats": {"armor": 26.0, "damage_reduction": 0.04}},
        ],
    },
}
