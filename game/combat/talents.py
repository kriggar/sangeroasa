from __future__ import annotations

from typing import Dict, List


RUNTIME_TALENT_BRANCHES: Dict[str, List[Dict[str, object]]] = {
    "mage": [
        {
            "id": "destruction",
            "name": "Destruction",
            "playstyle": "Unlock fire-themed burst spells.",
            "nodes": [
                {
                    "id": "mage_foozle_unlock_molten_spear",
                    "name": "Molten Spear",
                    "desc": "Unlocks Molten Spear on T — a piercing lava spear that rips a line through enemies.",
                    "cost": 1,
                },
                {
                    "id": "mage_foozle_unlock_rocks",
                    "name": "Meteor Rocks",
                    "desc": "Unlocks Meteor Rocks on 1 — a cluster of falling rocks saturates a targeted zone.",
                    "cost": 2,
                },
                {
                    "id": "mage_destruction_amplify",
                    "name": "Amplify",
                    "desc": "Fireball gains a wider splash and Cataclysm grows larger.",
                    "cost": 2,
                    "spell_mods": {
                        "mage_foozle_fireball": {"splash_bonus": 28.0},
                        "mage_foozle_explosion": {"radius_bonus": 32.0},
                    },
                },
            ],
        },
        {
            "id": "earth",
            "name": "Earth",
            "playstyle": "Unlock setup and control spells.",
            "nodes": [
                {
                    "id": "mage_foozle_unlock_earth_spike",
                    "name": "Earth Spike",
                    "desc": "Unlocks Earth Spike on 2 — rising stone spikes erupt in a line toward the target.",
                    "cost": 1,
                },
                {
                    "id": "mage_foozle_unlock_water",
                    "name": "Tidal Wave",
                    "desc": "Unlocks Tidal Wave on 3 — a forward-sweeping water wall knocks enemies back.",
                    "cost": 2,
                },
                {
                    "id": "mage_earth_fortify",
                    "name": "Fortify",
                    "desc": "Water Geyser covers a wider zone and Earth Spike drops an extra spike.",
                    "cost": 2,
                    "spell_mods": {
                        "mage_foozle_water_geyser": {"radius_bonus": 28.0},
                        "mage_foozle_earth_spike": {"extra_spikes": 2.0},
                    },
                },
            ],
        },
        {
            "id": "arcane",
            "name": "Arcane",
            "playstyle": "Buff the starter kit with movement and power.",
            "nodes": [
                {
                    "id": "mage_arcane_blink_power",
                    "name": "Portal Reach",
                    "desc": "Portal Step reaches farther and leaves a wider arrival nova.",
                    "cost": 1,
                    "spell_mods": {
                        "mage_foozle_portal_blink": {"blink_range_bonus": 80.0, "blink_radius_bonus": 28.0},
                    },
                },
                {
                    "id": "mage_arcane_cooldown",
                    "name": "Flow State",
                    "desc": "All spells recover from cooldown faster.",
                    "cost": 1,
                    "cooldown_reduction": 0.15,
                },
                {
                    "id": "mage_arcane_overcast",
                    "name": "Overcast",
                    "desc": "Raises base spell power, amplifying every cast.",
                    "cost": 2,
                    "bonus_power": 4.0,
                },
            ],
        },
    ],
    "assassin": [
        {
            "id": "execution",
            "name": "Execution",
            "playstyle": "Reset pressure and kill confirms.",
            "nodes": [
                {"id": "assassin_execution_1", "name": "Cull Window", "desc": "Q executes low-health targets and refunds movement.", "cost": 1},
                {"id": "assassin_execution_2", "name": "Bloodstep", "desc": "E grants a second dash on takedown.", "cost": 1},
                {"id": "assassin_execution_3", "name": "Guillotine", "desc": "R re-casts if it kills its mark.", "cost": 2},
            ],
        },
        {
            "id": "misdirection",
            "name": "Misdirection",
            "playstyle": "Stealth, clones, and threat manipulation.",
            "nodes": [
                {"id": "assassin_misdirection_1", "name": "False Angle", "desc": "Q spawns a delayed mirror slash.", "cost": 1},
                {"id": "assassin_misdirection_2", "name": "Smoke Veil", "desc": "W drops a blinding smoke field.", "cost": 1},
                {"id": "assassin_misdirection_3", "name": "Phantom Trail", "desc": "R leaves clone strikes behind each dash.", "cost": 2},
            ],
        },
        {
            "id": "venom",
            "name": "Venom",
            "playstyle": "Tag targets, kite disengages, and collapse later.",
            "nodes": [
                {"id": "assassin_venom_1", "name": "Septic Brand", "desc": "Q infects and empowers follow-up hits.", "cost": 1},
                {"id": "assassin_venom_2", "name": "Toxic Drift", "desc": "E leaves poison behind the dash path.", "cost": 1},
                {"id": "assassin_venom_3", "name": "Night Toxin", "desc": "R detonates all active poison stacks in an AoE.", "cost": 2},
            ],
        },
    ],
    "tank": [
        {
            "id": "fortress",
            "name": "Fortress",
            "playstyle": "Anchor space, deny dive lines, and survive the first engage.",
            "nodes": [
                {"id": "tank_fortress_1", "name": "Bastion Ring", "desc": "W becomes a persistent body-blocking zone.", "cost": 1},
                {"id": "tank_fortress_2", "name": "Iron Reprisal", "desc": "E stores damage and re-bursts it outward.", "cost": 1},
                {"id": "tank_fortress_3", "name": "Citadel Drop", "desc": "R creates walls that reshape the fight.", "cost": 2},
            ],
        },
        {
            "id": "vanguard",
            "name": "Vanguard",
            "playstyle": "Long-range engage and crowd control layering.",
            "nodes": [
                {"id": "tank_vanguard_1", "name": "Shock Entry", "desc": "Q charge ends in a knock-up cone.", "cost": 1},
                {"id": "tank_vanguard_2", "name": "Trample Pulse", "desc": "E drags enemies inward before the slam.", "cost": 1},
                {"id": "tank_vanguard_3", "name": "Frontline Breaker", "desc": "R chains a second collapse behind the first.", "cost": 2},
            ],
        },
        {
            "id": "warden",
            "name": "Warden",
            "playstyle": "Peel, redirects, and ally protection.",
            "nodes": [
                {"id": "tank_warden_1", "name": "Intercept", "desc": "Q can be recast to bodyguard an ally.", "cost": 1},
                {"id": "tank_warden_2", "name": "Shield Relay", "desc": "W propagates protection to nearby allies.", "cost": 1},
                {"id": "tank_warden_3", "name": "Last Rampart", "desc": "R redirects hostile projectiles while active.", "cost": 2},
            ],
        },
    ],
    "ranger": [
        {
            "id": "deadeye",
            "name": "Deadeye",
            "playstyle": "Precision skillshots and execution windows.",
            "nodes": [
                {"id": "ranger_deadeye_1", "name": "Thread The Needle", "desc": "Q pierces and crits only the first target.", "cost": 1},
                {"id": "ranger_deadeye_2", "name": "Lockstep", "desc": "W marks targets and refunds E on marked hits.", "cost": 1},
                {"id": "ranger_deadeye_3", "name": "Crosswind Verdict", "desc": "R gains a second converging shot.", "cost": 2},
            ],
        },
        {
            "id": "skirmish",
            "name": "Skirmish",
            "playstyle": "Kiting, repositioning, and tempo shots.",
            "nodes": [
                {"id": "ranger_skirmish_1", "name": "Ricochet", "desc": "Q bounces after terrain contact.", "cost": 1},
                {"id": "ranger_skirmish_2", "name": "Featherstep", "desc": "E leaves slowing caltrops in your wake.", "cost": 1},
                {"id": "ranger_skirmish_3", "name": "Run And Volley", "desc": "R fires while you move through the channel.", "cost": 2},
            ],
        },
        {
            "id": "trapper",
            "name": "Trapper",
            "playstyle": "Layered zones and setup control.",
            "nodes": [
                {"id": "ranger_trapper_1", "name": "Barbed Ground", "desc": "W splits into twin trap fields.", "cost": 1},
                {"id": "ranger_trapper_2", "name": "Guided Prey", "desc": "E tethers enemies toward the trap center.", "cost": 1},
                {"id": "ranger_trapper_3", "name": "Kill Box", "desc": "R repeats its barrage wherever your traps overlap.", "cost": 2},
            ],
        },
    ],
    "bruiser": [
        {
            "id": "onslaught",
            "name": "Onslaught",
            "playstyle": "Gap close, stick, and overwhelm in extended melee.",
            "nodes": [
                {"id": "bruiser_onslaught_1", "name": "Blood Rush", "desc": "Q lunges farther after damaging a target.", "cost": 1},
                {"id": "bruiser_onslaught_2", "name": "Crushing Heel", "desc": "W slams twice if you stay in range.", "cost": 1},
                {"id": "bruiser_onslaught_3", "name": "No Escape", "desc": "R cages enemies inside the final impact.", "cost": 2},
            ],
        },
        {
            "id": "sustain",
            "name": "Sustain",
            "playstyle": "Drain tempo and survive through trading windows.",
            "nodes": [
                {"id": "bruiser_sustain_1", "name": "Ravenous Cuts", "desc": "Q leaves a healing bleed trail.", "cost": 1},
                {"id": "bruiser_sustain_2", "name": "Second Wind", "desc": "E converts stored damage into self-heal.", "cost": 1},
                {"id": "bruiser_sustain_3", "name": "Last Feast", "desc": "R siphons from every enemy caught in the storm.", "cost": 2},
            ],
        },
        {
            "id": "juggernaut",
            "name": "Juggernaut",
            "playstyle": "Slow, unstoppable, and area-denial focused.",
            "nodes": [
                {"id": "bruiser_juggernaut_1", "name": "Heavy Step", "desc": "Q leaves fissures that slow pursuit paths.", "cost": 1},
                {"id": "bruiser_juggernaut_2", "name": "Hammer Turn", "desc": "W pivots into a sweeping backhand.", "cost": 1},
                {"id": "bruiser_juggernaut_3", "name": "Earthbreaker", "desc": "R throws repeated shockwaves from your position.", "cost": 2},
            ],
        },
    ],
}


def build_runtime_skill_tree(
    class_id: str,
    *,
    core_id: str,
    core_name: str,
    core_desc: str,
) -> List[Dict[str, object]]:
    branches = RUNTIME_TALENT_BRANCHES.get(class_id, [])
    nodes: List[Dict[str, object]] = [
        {
            "id": core_id,
            "name": core_name,
            "desc": core_desc,
            "cost": 0,
            "requires": [],
            "spell": None,
            "bonus_power": 0.0,
            "cooldown_reduction": 0.0,
            "spell_mods": {},
            "pos": (0.50, 0.10),
            "tier": "core",
        }
    ]
    x_positions = (0.20, 0.50, 0.80)
    y_start = 0.28
    y_step = 0.16
    for branch_index, branch in enumerate(branches[:3]):
        branch_id = f"{class_id}_{branch['id']}"
        x_pos = x_positions[min(branch_index, len(x_positions) - 1)]
        previous = core_id
        for node_index, node in enumerate(branch.get("nodes", [])):
            node_id = str(node["id"])
            nodes.append(
                {
                    "id": node_id,
                    "name": str(node["name"]),
                    "desc": str(node["desc"]),
                    "cost": int(node.get("cost", 1)),
                    "requires": [previous],
                    "spell": None,
                    "bonus_power": float(node.get("bonus_power", 0.0)),
                    "cooldown_reduction": float(node.get("cooldown_reduction", 0.0)),
                    "spell_mods": dict(node.get("spell_mods", {})),
                    "pos": (x_pos, y_start + y_step * node_index),
                    "tier": f"{branch_id}_{node_index + 1}",
                }
            )
            previous = node_id
    return nodes
