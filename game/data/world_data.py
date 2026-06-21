"""game/data/world_data.py — potion/teleport item data, armor-set bonuses, wolf materials, professions."""
from typing import Dict, List, Tuple, Any

_POTIONS: List[Dict[str, object]] = [
    {"name": "Health Potion",        "effect": "hp_60",          "icon": (19, 1), "color": (200, 60,  60),  "rarity": "common",    "cost": 25,  "desc": "Restores 60 HP.",                 "item_type": "consumable", "equip_slot": ""},
    {"name": "Greater Health Flask", "effect": "hp_80",          "icon": (19, 3), "color": (180, 40,  40),  "rarity": "rare",      "cost": 45,  "desc": "Restores 80 HP.",                 "item_type": "consumable", "equip_slot": ""},
    {"name": "Mana Potion",          "effect": "mp_80",          "icon": (20, 3), "color": (60,  100, 210),  "rarity": "common",    "cost": 30,  "desc": "Restores 80 mana.",               "item_type": "consumable", "equip_slot": ""},
    {"name": "Swift Tonic",          "effect": "speed_boost_60", "icon": (20, 4), "color": (80,  180, 220),  "rarity": "rare",      "cost": 35,  "desc": "Grants +28% move speed for 60s.", "item_type": "consumable", "equip_slot": ""},
    {"name": "Battle Brew",          "effect": "dmg_boost",      "icon": (19, 2), "color": (160, 100, 50),   "rarity": "rare",      "cost": 40,  "desc": "Grants +20% damage for 90s.",     "item_type": "consumable", "equip_slot": ""},
    {"name": "Elixir of Life",       "effect": "full_restore",   "icon": (19, 0), "color": (200, 160, 60),   "rarity": "legendary", "cost": 120, "desc": "Fully restores HP and mana.",     "item_type": "consumable", "equip_slot": ""},
]

TELEPORT_BOOK_ITEM: Dict[str, object] = {
    "id": "book_of_teleportation",
    "name": "Book of Teleportation",
    "effect": "teleport_book",
    "color": (120, 80, 200),
    "rarity": "legendary",
    "item_type": "consumable",
    "equip_slot": "",
    "desc": "An ancient tome of arcane travel. Use to open a portal to any known location.",
    "permanent": True,
}

CLASS_ARMOR_SET_BONUSES: Dict[str, Dict[int, Dict[str, float]]] = {
    "mage": {
        2: {"spell_power": 6.0},
        4: {"max_mana": 14.0, "cooldown_reduction": 0.03},
        6: {"spell_power": 12.0, "mana_regen": 1.1},
    },
    "ranger": {
        2: {"move_speed": 0.04, "basic_damage": 5.0},
        4: {"cooldown_reduction": 0.05, "max_hp": 15.0},
        6: {"basic_damage": 10.0, "armor": 10.0},
    },
    "rogue": {
        2: {"move_speed": 0.03, "spell_power": 4.0},
        4: {"cooldown_reduction": 0.04, "max_hp": 10.0},
        6: {"spell_power": 9.0, "basic_damage": 4.0},
    },
    "necromancer": {
        2: {"spell_power": 5.0, "max_mana": 10.0},
        4: {"mana_regen": 0.8, "cooldown_reduction": 0.03},
        6: {"spell_power": 11.0, "max_hp": 14.0},
    },
    "warrior": {
        2: {"armor": 18.0, "max_hp": 16.0},
        4: {"damage_reduction": 0.04, "basic_damage": 4.0},
        6: {"armor": 28.0, "max_hp": 24.0, "basic_damage": 6.0},
    },
    "paladin": {
        2: {"armor": 14.0, "max_mana": 10.0},
        4: {"cooldown_reduction": 0.03, "damage_reduction": 0.03},
        6: {"armor": 22.0, "basic_damage": 4.0, "spell_power": 6.0},
    },
}

WOLF_MATERIALS: Dict[str, Dict] = {
    "wolf_pelt": {"name": "Wolf Pelt",  "color": (160, 130, 100), "drop_chance": 0.70, "max_drop": 2},
    "wolf_fang": {"name": "Wolf Fang",  "color": (220, 215, 195), "drop_chance": 0.50, "max_drop": 2},
    "wolf_claw": {"name": "Wolf Claw",  "color": (175, 165, 140), "drop_chance": 0.40, "max_drop": 2},
    "wolf_bone": {"name": "Wolf Bone",  "color": (200, 195, 180), "drop_chance": 0.35, "max_drop": 2},
    "venom_sac": {"name": "Venom Sac",  "color": ( 90, 175,  75), "drop_chance": 0.22, "max_drop": 1},
}

MATERIAL_ORDER = ["wolf_pelt", "wolf_fang", "wolf_claw", "wolf_bone", "venom_sac", "deer_hide", "venison", "bird_feather", "poultry", "rat_tail", "arctic_fish", "icefish_oil", "frost_roe"]

PROFESSION_DEFINITIONS: Dict[str, Dict[str, object]] = {
    "alchemy": {
        "name": "Alchemy",
        "desc": "Brew combat tonics and battle elixirs from wild reagents.",
        "color": (92, 168, 122),
    },
    "blacksmithing": {
        "name": "Blacksmithing",
        "desc": "Forge durable weapons and armor from beast remains.",
        "color": (156, 126, 88),
    },
    "runecrafting": {
        "name": "Runecrafting",
        "desc": "Bind charms and sigils for permanent character upgrades.",
        "color": (128, 124, 210),
    },
}

PROFESSION_ORDER = ["alchemy", "blacksmithing", "runecrafting"]

PROFESSION_MAX_SKILL = 150
