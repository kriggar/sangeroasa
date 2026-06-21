"""game/data/spell_layout.py — spell hotbar key labels & per-class slot layout (pure data)."""
from typing import Dict, List

SPELL_KEY_LABELS: List[str] = ["Q", "W", "E", "R", "T", "1", "2", "3"]
CLASS_SPELL_SLOT_COUNTS: Dict[str, int] = {
    "mage": 8, "ranger": 8, "rogue": 8, "necromancer": 8, "warrior": 8, "paladin": 8,
}
CLASS_COMBAT_SPELL_LAYOUT: Dict[str, List[str]] = {
    "mage": [
        "mage_foozle_fireball",       # Q - Fire_Ball projectile (starter)
        "mage_foozle_water_geyser",   # W - Water_Geyser AoE (starter)
        "mage_foozle_portal_blink",   # E - Portal blink (starter)
        "mage_foozle_explosion",      # R - Explosion ultimate (starter)
        "mage_foozle_molten_spear",   # T - unlock: Destruction tier 1
        "mage_foozle_rocks",          # 1 - unlock: Destruction tier 2
        "mage_foozle_earth_spike",    # 2 - unlock: Earth tier 1
        "mage_foozle_water",          # 3 - unlock: Earth tier 2
    ],
    "ranger": [
        "ranger_quick_shot",       # Q - fastest basic
        "ranger_power_shot",       # W - standard shot
        "ranger_concussive_shot",  # E - slowing shot
        "ranger_serpent_sting",    # R - poison dot
        "ranger_multi_shot",       # T - cone fan
        "ranger_bear_trap",        # 1 - CC trap
        "ranger_explosive_shot",   # 2 - burst shot
        "ranger_kill_shot",        # 3 - execute ult
    ],
    "rogue": [
        "rogue_sinister_strike",   # Q - fast basic
        "rogue_shadow_knife",      # W - shadow melee
        "rogue_backstab",          # E - high dmg melee
        "rogue_smoke_burst",       # R - shadowstep gap-close
        "rogue_fan_of_knives",     # T - cone cleave
        "rogue_envenom",           # 1 - poison proj
        "rogue_venom_trap",        # 2 - venom orb
        "rogue_evasion_sigil",     # 3 - ultimate
    ],
    "necromancer": [
        "necro_bone_spear",        # Q - basic bone proj
        "necro_shadow_bolt",       # W - shadow proj
        "necro_death_coil",        # E - death proj
        "necro_grave_chill",       # R - chill nova
        "necro_plague_cone",       # T - plague cone
        "necro_wraith_orb",        # 1 - wraith orb
        "necro_soul_well",         # 2 - raise skeleton
        "necro_unholy_ground",     # 3 - ultimate
    ],
    "warrior": [
        "warrior_heroic_strike",   # Q - fast basic
        "warrior_iron_javelin",    # W - standard melee
        "warrior_slam",            # E - heavy melee
        "warrior_war_stomp",       # R - ground nova
        "warrior_cleave",          # T - cone cleave
        "warrior_charge",          # 1 - charge proj
        "warrior_whirling_axe",    # 2 - spin orb
        "warrior_avatar",          # 3 - ultimate
    ],
    "paladin": [
        "paladin_crusader_strike",  # Q - fast melee
        "paladin_judgment_spear",   # W - proj
        "paladin_holy_shock",       # E - holy proj
        "paladin_holy_burst",       # R - nova
        "paladin_light_of_dawn",    # T - cone heal/dmg
        "paladin_exorcism",         # 1 - heavy proj
        "paladin_radiant_orb",      # 2 - orb
        "paladin_avenging_wrath",   # 3 - ultimate
    ],
}
