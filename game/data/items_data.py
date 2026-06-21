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

