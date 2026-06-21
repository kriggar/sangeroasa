from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from .talents import build_runtime_skill_tree


@dataclass(frozen=True)
class AbilitySpec:
    id: str
    slot: str
    key: str
    name: str
    description: str
    timing: str
    windup: float
    action: float
    recovery: float
    cooldown: float
    mana_cost: float
    cast_range: float
    vfx_plan: str
    implementation_key: Optional[str]
    colors: Dict[str, tuple[int, int, int]]


@dataclass(frozen=True)
class ClassKit:
    id: str
    name: str
    role: str
    gameplay_loop: str
    strengths: str
    weaknesses: str
    passive_name: str
    passive_desc: str
    abilities: List[AbilitySpec]


MAGE_ABILITIES = [
    AbilitySpec(
        id="mage_foozle_fireball",
        slot="1",
        key="Q",
        name="Fireball",
        description="Fast pixel fireball that explodes on impact and scatters splash damage.",
        timing="0.10s windup, projectile travel, burst impact",
        windup=0.10,
        action=1.40,
        recovery=0.25,
        cooldown=0.55,
        mana_cost=16.0,
        cast_range=1000.0,
        vfx_plan="Fire_Ball sprite streams along the travel line, Explosion sprite on impact.",
        implementation_key="mage_foozle_fireball",
        colors={"core": (255, 170, 60), "trail": (255, 110, 30), "outline": (120, 50, 10)},
    ),
    AbilitySpec(
        id="mage_foozle_water_geyser",
        slot="2",
        key="W",
        name="Water Geyser",
        description="Targeted water eruption that bursts upward for heavy zone damage.",
        timing="0.35s telegraph, 0.72s eruption, 0.25s aftermath",
        windup=0.35,
        action=0.72,
        recovery=0.25,
        cooldown=1.10,
        mana_cost=24.0,
        cast_range=760.0,
        vfx_plan="Telegraph ring, Water_Geyser sprite erupting from the ground.",
        implementation_key="mage_foozle_water_geyser",
        colors={"core": (180, 226, 255), "trail": (140, 200, 255), "outline": (60, 130, 200)},
    ),
    AbilitySpec(
        id="mage_foozle_portal_blink",
        slot="3",
        key="E",
        name="Portal Step",
        description="Blink between two portals, damaging and knocking back enemies at arrival.",
        timing="0.14s open, 0.08s blink, 0.42s aftermath",
        windup=0.14,
        action=0.08,
        recovery=0.42,
        cooldown=2.20,
        mana_cost=22.0,
        cast_range=320.0,
        vfx_plan="Portal sprite at origin and destination, ring of force on arrival.",
        implementation_key="mage_foozle_portal_blink",
        colors={"core": (214, 184, 255), "trail": (196, 160, 255), "outline": (120, 80, 210)},
    ),
    AbilitySpec(
        id="mage_foozle_explosion",
        slot="4",
        key="R",
        name="Cataclysm",
        description="Ultimate: a massive telegraphed pixel explosion that obliterates a wide zone.",
        timing="0.55s telegraph, 0.75s detonation, 0.35s aftermath",
        windup=0.55,
        action=0.75,
        recovery=0.35,
        cooldown=6.50,
        mana_cost=48.0,
        cast_range=900.0,
        vfx_plan="Giant telegraph, colossal Explosion sprite, heavy shake and flash.",
        implementation_key="mage_foozle_explosion",
        colors={"core": (255, 160, 80), "trail": (255, 110, 40), "outline": (130, 50, 10)},
    ),
]


MAGE_UNLOCK_SPELLS: List[Dict[str, object]] = [
    {
        "id": "mage_foozle_molten_spear",
        "name": "Molten Spear",
        "skill": "mage_foozle_unlock_molten_spear",
        "slot": "5",
        "key": "T",
        "cooldown": 0.95,
        "mana_cost": 22.0,
        "damage": 52.0,
        "cast_range": 900.0,
        "is_ultimate": False,
        "description": "Piercing lava spear that rips a line through enemies.",
        "colors": {"core": (255, 190, 90), "trail": (255, 130, 40), "outline": (130, 60, 10)},
    },
    {
        "id": "mage_foozle_rocks",
        "name": "Meteor Rocks",
        "skill": "mage_foozle_unlock_rocks",
        "slot": "6",
        "key": "1",
        "cooldown": 3.80,
        "mana_cost": 38.0,
        "damage": 42.0,
        "cast_range": 820.0,
        "is_ultimate": False,
        "description": "Scatter-drop cluster of rocks saturates the target zone.",
        "colors": {"core": (220, 190, 140), "trail": (200, 160, 110), "outline": (120, 80, 40)},
    },
    {
        "id": "mage_foozle_earth_spike",
        "name": "Earth Spike",
        "skill": "mage_foozle_unlock_earth_spike",
        "slot": "7",
        "key": "2",
        "cooldown": 1.40,
        "mana_cost": 24.0,
        "damage": 48.0,
        "cast_range": 500.0,
        "is_ultimate": False,
        "description": "Line of rising stone spikes erupts from you toward the target.",
        "colors": {"core": (200, 168, 120), "trail": (170, 130, 80), "outline": (110, 80, 40)},
    },
    {
        "id": "mage_foozle_water",
        "name": "Tidal Wave",
        "skill": "mage_foozle_unlock_water",
        "slot": "8",
        "key": "3",
        "cooldown": 2.40,
        "mana_cost": 28.0,
        "damage": 46.0,
        "cast_range": 560.0,
        "is_ultimate": False,
        "description": "Forward-sweeping water wall knocks enemies back.",
        "colors": {"core": (180, 220, 255), "trail": (140, 200, 255), "outline": (60, 130, 200)},
    },
]

ASSASSIN_ABILITIES = [
    AbilitySpec(
        id="assassin_shadow_fang",
        slot="1",
        key="Q",
        name="Shadow Fang",
        description="Fast line strike that marks a target for execution and sets up burst windows.",
        timing="0.08s windup, dash slash, 0.18s recover",
        windup=0.08,
        action=0.18,
        recovery=0.18,
        cooldown=0.55,
        mana_cost=12.0,
        cast_range=220.0,
        vfx_plan="Shadow wake, knife ribbon, and marked-hit bloom.",
        implementation_key=None,
        colors={"core": (224, 220, 242), "trail": (126, 118, 182), "outline": (56, 48, 84)},
    ),
    AbilitySpec(
        id="assassin_smoke_lunge",
        slot="2",
        key="W",
        name="Smoke Lunge",
        description="Drop smoke, then cut through its edge to break target tracking and re-angle the fight.",
        timing="0.12s cast, smoke bloom, follow-up lunge",
        windup=0.12,
        action=0.30,
        recovery=0.22,
        cooldown=1.80,
        mana_cost=22.0,
        cast_range=320.0,
        vfx_plan="Smoke veil, dagger trails, and edge rupture.",
        implementation_key=None,
        colors={"core": (180, 188, 220), "trail": (96, 98, 132), "outline": (42, 42, 64)},
    ),
    AbilitySpec(
        id="assassin_mirror_step",
        slot="3",
        key="E",
        name="Mirror Step",
        description="Snap through a target and echo the stab from behind with a delayed mirror hit.",
        timing="0.10s windup, snap step, delayed echo",
        windup=0.10,
        action=0.16,
        recovery=0.24,
        cooldown=2.40,
        mana_cost=24.0,
        cast_range=260.0,
        vfx_plan="Twin afterimages, echo slash, and delayed puncture flash.",
        implementation_key=None,
        colors={"core": (214, 198, 255), "trail": (144, 118, 224), "outline": (60, 44, 110)},
    ),
    AbilitySpec(
        id="assassin_midnight_verdict",
        slot="4",
        key="R",
        name="Midnight Verdict",
        description="Short channel into repeated execution dashes across the marked target.",
        timing="0.18s windup, multi-dash burst, end flourish",
        windup=0.18,
        action=0.70,
        recovery=0.42,
        cooldown=7.20,
        mana_cost=64.0,
        cast_range=540.0,
        vfx_plan="Cross-cut lines, clone echoes, and kill bloom.",
        implementation_key=None,
        colors={"core": (255, 146, 164), "trail": (196, 72, 120), "outline": (84, 26, 46)},
    ),
]

TANK_ABILITIES = [
    AbilitySpec(
        id="tank_breach_charge",
        slot="1",
        key="Q",
        name="Breach Charge",
        description="Armored rush that knocks up the first line it collides with.",
        timing="0.16s brace, charge, impact skid",
        windup=0.16,
        action=0.26,
        recovery=0.24,
        cooldown=0.70,
        mana_cost=10.0,
        cast_range=280.0,
        vfx_plan="Shield wake, dust ribbon, and slam ring.",
        implementation_key=None,
        colors={"core": (224, 202, 152), "trail": (158, 126, 82), "outline": (72, 56, 34)},
    ),
    AbilitySpec(
        id="tank_bulwark_field",
        slot="2",
        key="W",
        name="Bulwark Field",
        description="Ground telegraph that becomes a zone enemies struggle to leave.",
        timing="0.14s cast, field rise, pulse window",
        windup=0.14,
        action=0.50,
        recovery=0.34,
        cooldown=2.20,
        mana_cost=20.0,
        cast_range=260.0,
        vfx_plan="Shield panels, pulse rings, and denial decals.",
        implementation_key=None,
        colors={"core": (188, 212, 236), "trail": (118, 152, 184), "outline": (54, 72, 92)},
    ),
    AbilitySpec(
        id="tank_iron_rebuke",
        slot="3",
        key="E",
        name="Iron Rebuke",
        description="Absorb pressure, then hammer it back out in a retaliatory shockwave.",
        timing="0.12s guard, hold, release",
        windup=0.12,
        action=0.34,
        recovery=0.30,
        cooldown=3.00,
        mana_cost=24.0,
        cast_range=0.0,
        vfx_plan="Guard shimmer, delayed crack ring, and terrain sparks.",
        implementation_key=None,
        colors={"core": (244, 228, 188), "trail": (196, 164, 96), "outline": (90, 72, 38)},
    ),
    AbilitySpec(
        id="tank_citadel_drop",
        slot="4",
        key="R",
        name="Citadel Drop",
        description="Massive telegraphed leap that walls off the center of the fight.",
        timing="0.22s windup, air hang, impact fortress",
        windup=0.22,
        action=0.80,
        recovery=0.50,
        cooldown=8.00,
        mana_cost=66.0,
        cast_range=520.0,
        vfx_plan="Huge telegraph, crater, and wall eruptions.",
        implementation_key=None,
        colors={"core": (255, 224, 164), "trail": (210, 160, 98), "outline": (88, 58, 30)},
    ),
]

RANGER_ABILITIES = [
    AbilitySpec(
        id="ranger_pinning_shot",
        slot="1",
        key="Q",
        name="Pinning Shot",
        description="Precision bolt that rewards edge-of-range hits and clean aim discipline.",
        timing="0.10s draw, flight, pin bloom",
        windup=0.10,
        action=0.50,
        recovery=0.10,
        cooldown=0.42,
        mana_cost=14.0,
        cast_range=1080.0,
        vfx_plan="Arrow wake, wind ribbons, and pin flare.",
        implementation_key=None,
        colors={"core": (222, 252, 188), "trail": (136, 200, 116), "outline": (52, 78, 38)},
    ),
    AbilitySpec(
        id="ranger_briar_trap",
        slot="2",
        key="W",
        name="Briar Trap",
        description="Delayed ground trap that blooms into a kiting zone when triggered.",
        timing="0.14s toss, arm time, snare bloom",
        windup=0.14,
        action=0.50,
        recovery=0.42,
        cooldown=1.90,
        mana_cost=20.0,
        cast_range=720.0,
        vfx_plan="Trap telegraph, thorn burst, and leaf motes.",
        implementation_key=None,
        colors={"core": (192, 236, 142), "trail": (108, 170, 72), "outline": (46, 84, 28)},
    ),
    AbilitySpec(
        id="ranger_featherstep",
        slot="3",
        key="E",
        name="Featherstep",
        description="Quick evasive hop that leaves slowing caltrops behind you.",
        timing="0.08s windup, lateral hop, caltrop linger",
        windup=0.08,
        action=0.18,
        recovery=0.26,
        cooldown=2.60,
        mana_cost=18.0,
        cast_range=240.0,
        vfx_plan="Feather streak, heel dust, and caltrop sparkle.",
        implementation_key=None,
        colors={"core": (202, 244, 220), "trail": (142, 208, 178), "outline": (58, 94, 76)},
    ),
    AbilitySpec(
        id="ranger_crosswind_barrage",
        slot="4",
        key="R",
        name="Crosswind Barrage",
        description="Wide telegraph that rains converging arrows across a lane.",
        timing="0.18s aim, barrage lane, after-volley fade",
        windup=0.18,
        action=0.90,
        recovery=0.40,
        cooldown=7.10,
        mana_cost=58.0,
        cast_range=980.0,
        vfx_plan="Lane telegraph, staggered impacts, and gust lines.",
        implementation_key=None,
        colors={"core": (255, 242, 176), "trail": (232, 208, 122), "outline": (112, 94, 32)},
    ),
]

BRUISER_ABILITIES = [
    AbilitySpec(
        id="bruiser_blood_rush",
        slot="1",
        key="Q",
        name="Blood Rush",
        description="Heavy lunge that opens a sustain window on contact.",
        timing="0.10s windup, leap hit, blood flare",
        windup=0.10,
        action=0.18,
        recovery=0.20,
        cooldown=0.58,
        mana_cost=10.0,
        cast_range=200.0,
        vfx_plan="Heavy step trail, impact streaks, and blood sparks.",
        implementation_key=None,
        colors={"core": (255, 190, 160), "trail": (220, 112, 86), "outline": (98, 42, 28)},
    ),
    AbilitySpec(
        id="bruiser_crushing_heel",
        slot="2",
        key="W",
        name="Crushing Heel",
        description="Telegraphed stomp that threatens a second slam if you stay in range.",
        timing="0.14s windup, stomp, lingering threat ring",
        windup=0.14,
        action=0.34,
        recovery=0.26,
        cooldown=1.70,
        mana_cost=18.0,
        cast_range=120.0,
        vfx_plan="Ground crack telegraph and double-stomp bloom.",
        implementation_key=None,
        colors={"core": (242, 210, 164), "trail": (198, 152, 84), "outline": (92, 60, 24)},
    ),
    AbilitySpec(
        id="bruiser_second_wind",
        slot="3",
        key="E",
        name="Second Wind",
        description="Brace, shrug damage, then burst back into motion.",
        timing="0.10s brace, absorb beat, burst release",
        windup=0.10,
        action=0.30,
        recovery=0.34,
        cooldown=2.80,
        mana_cost=22.0,
        cast_range=0.0,
        vfx_plan="Shoulder aura, shockwave release, and heal embers.",
        implementation_key=None,
        colors={"core": (208, 230, 180), "trail": (126, 182, 108), "outline": (52, 84, 40)},
    ),
    AbilitySpec(
        id="bruiser_earthbreaker",
        slot="4",
        key="R",
        name="Earthbreaker",
        description="Commit to a brutal multi-hit finish that keeps enemies trapped nearby.",
        timing="0.16s windup, chained crushes, dust ring fade",
        windup=0.16,
        action=0.86,
        recovery=0.44,
        cooldown=7.40,
        mana_cost=60.0,
        cast_range=260.0,
        vfx_plan="Layered slam impacts, dust walls, and sustain siphon glow.",
        implementation_key=None,
        colors={"core": (255, 214, 166), "trail": (224, 126, 88), "outline": (104, 48, 28)},
    ),
]


RUNTIME_KITS: Dict[str, ClassKit] = {
    "mage": ClassKit(
        id="mage",
        name="Mage",
        role="Burst / AoE / Zone Control",
        gameplay_loop="Scout angles with Arc Bolt, force movement with Starfall Sigil, reposition with Phase Blink, then collapse the fight with Astral Cataclysm.",
        strengths="Explosive ranged pressure, layered telegraphs, strong self-repositioning, and premium battlefield clarity.",
        weaknesses="Low base durability, commitment during telegraphed casts, and heavy punishment if blink is unavailable.",
        passive_name="Celestial Flow",
        passive_desc="Spell tempo accelerates after committing to a full cast sequence, rewarding proactive space control.",
        abilities=MAGE_ABILITIES,
    ),
    "assassin": ClassKit(
        id="assassin",
        name="Assassin",
        role="Mobility / Burst",
        gameplay_loop="Mark a target, misdirect vision, dash through their blind spots, and finish with chained burst windows.",
        strengths="Explosive target access, high outplay potential, and strong execution pressure.",
        weaknesses="Punished by failed commits, weak into grouped peel, and limited sustained combat.",
        passive_name="Bloodtrail Instinct",
        passive_desc="Damaging isolated targets opens bonus movement routes and accelerates reset windows.",
        abilities=ASSASSIN_ABILITIES,
    ),
    "tank": ClassKit(
        id="tank",
        name="Tank",
        role="Control / Durability",
        gameplay_loop="Initiate first contact, pin priority targets in telegraphed zones, and hold space long enough for allies to follow.",
        strengths="Reliable engage, excellent crowd-control layering, and durable front-line presence.",
        weaknesses="Low burst without setup and vulnerable if engage tools are baited out.",
        passive_name="Anchor Plate",
        passive_desc="Standing your ground turns incoming aggression into momentum for the next engage.",
        abilities=TANK_ABILITIES,
    ),
    "ranger": ClassKit(
        id="ranger",
        name="Ranger",
        role="Precision / Kiting",
        gameplay_loop="Play range bands, create trap pressure, and punish every forced movement with clean follow-up shots.",
        strengths="Long reach, consistent poke, and excellent fight shaping through zones.",
        weaknesses="Fragile if cornered and dependent on aim discipline.",
        passive_name="Field Rhythm",
        passive_desc="Maintaining ideal spacing empowers each follow-up shot and trap pulse.",
        abilities=RANGER_ABILITIES,
    ),
    "bruiser": ClassKit(
        id="bruiser",
        name="Bruiser",
        role="Sustain / Melee Pressure",
        gameplay_loop="Stay glued to the fight, convert contact into healing tempo, and win through repeated heavy trades.",
        strengths="Sticky melee threat, high durability in extended fights, and strong mid-range engage.",
        weaknesses="Limited range and vulnerable to repeated disengage.",
        passive_name="War Drinker",
        passive_desc="Extended contact converts aggression into healing and renewed chase pressure.",
        abilities=BRUISER_ABILITIES,
    ),
}


def spellbook_for_class(class_id: str) -> List[Dict[str, object]]:
    kit = RUNTIME_KITS.get(class_id)
    if kit is None:
        return []
    spellbook: List[Dict[str, object]] = []
    for ability in kit.abilities:
        spellbook.append(
            {
                "id": ability.id,
                "name": ability.name,
                "skill": "mage_core" if class_id == "mage" else ability.id,
                "slot": ability.slot,
                "cooldown": ability.cooldown,
                "mana_cost": ability.mana_cost,
                "damage": 26.0 if ability.key == "Q" else (54.0 if ability.key == "R" else 38.0),
                "kind": "timeline",
                "cast_range": ability.cast_range,
                "is_ultimate": ability.key == "R",
                "description": ability.description,
                "timing": ability.timing,
                "vfx_plan": ability.vfx_plan,
                "implementation_key": ability.implementation_key,
                "colors": dict(ability.colors),
            }
        )
    if class_id == "mage":
        for extra in MAGE_UNLOCK_SPELLS:
            entry = dict(extra)
            entry.setdefault("kind", "timeline")
            entry.setdefault("implementation_key", entry.get("id"))
            entry["colors"] = dict(entry.get("colors", {}))
            spellbook.append(entry)
    return spellbook


def apply_class_overrides(
    class_archetypes: Dict[str, Dict[str, object]],
    class_combat_stats: Dict[str, Dict[str, object]],
    class_passives: Dict[str, Dict[str, object]],
    class_core_skill_meta: Dict[str, Dict[str, str]],
) -> None:
    mage_kit = RUNTIME_KITS["mage"]
    core_meta = {
        "id": "mage_core",
        "name": "Arcane Core",
        "desc": "Unlocks the starter spell kit: Fireball, Water Geyser, Portal Step, and Cataclysm.",
    }
    class_core_skill_meta["mage"] = core_meta
    class_archetypes["mage"] = {
        **class_archetypes.get("mage", {}),
        "name": mage_kit.name,
        "description": "High-clarity battle mage built around phased skillshots, telegraphed zones, and blink tempo.",
        "starter_skills": [core_meta["id"]],
        "spellbook": spellbook_for_class("mage"),
        "skill_tree": build_runtime_skill_tree(
            "mage",
            core_id=core_meta["id"],
            core_name=core_meta["name"],
            core_desc=core_meta["desc"],
        ),
        "custom_skill_tree": True,
        "combat_runtime_class": True,
    }
    class_combat_stats["mage"] = {
        "max_hp": 164.0,
        "max_mana": 224.0,
        "mana_regen": 7.8,
        "basic_cooldown": 0.31,
        "basic_damage": 18.0,
        "basic_type": "cast",
    }
    class_passives["mage"] = {
        "id": "mage_celestial_flow",
        "name": mage_kit.passive_name,
        "desc": mage_kit.passive_desc,
        "glyph": "star",
        "icon_colors": {"base": (62, 74, 126), "accent": (202, 222, 255), "line": (234, 244, 255)},
        "effects": {"mana_regen_mult": 1.05, "spell_cooldown_mult": 0.94},
    }
