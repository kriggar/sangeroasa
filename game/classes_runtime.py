"""game/classes_runtime.py — class spellbook/skill-tree/passive/stat runtime helpers."""
import math
from typing import Dict, List, Optional, Tuple, Any, Union, Set

from game.utils import clamp
from game.data.classes import *
from game.data.spell_layout import *

__all__ = [
    'class_spellbook',
    'class_skill_tree',
    '_build_progressive_skill_tree',
    'rebuild_progressive_skill_trees',
    'class_combat_stats',
    'PASSIVE_EFFECT_DEFAULTS',
    'class_passive_data',
    'class_passive_effects',
    '_format_effect_percent',
    'class_passive_effect_lines',
    'all_spell_defs',
    'spell_mana_cost',
    'skill_damage_bonus',
    'skill_cooldown_scale',
    'skill_spell_modifiers',
]


def class_spellbook(class_id: str) -> List[Dict[str, object]]:
    data = CLASS_ARCHETYPES.get(class_id, {})
    raw_spells = data.get("spellbook", [])
    if not isinstance(raw_spells, list):
        return []

    spell_by_id: Dict[str, Dict[str, object]] = {}
    for entry in raw_spells:
        if not isinstance(entry, dict):
            continue
        spell_id = str(entry.get("id", "")).strip()
        if spell_id and spell_id not in spell_by_id:
            spell_by_id[spell_id] = entry

    max_slots = int(CLASS_SPELL_SLOT_COUNTS.get(class_id, 4))
    if max_slots <= 0:
        max_slots = 4

    selected: List[Dict[str, object]] = []
    layout = CLASS_COMBAT_SPELL_LAYOUT.get(class_id, [])
    for spell_id in layout:
        spell = spell_by_id.get(spell_id)
        if isinstance(spell, dict):
            selected.append(dict(spell))
        if len(selected) >= max_slots:
            break

    if len(selected) < max_slots:
        used_ids = {str(spell.get("id", "")) for spell in selected}
        for entry in raw_spells:
            if not isinstance(entry, dict):
                continue
            spell_id = str(entry.get("id", "")).strip()
            if not spell_id or spell_id in used_ids:
                continue
            selected.append(dict(entry))
            used_ids.add(spell_id)
            if len(selected) >= max_slots:
                break

    selected = selected[:max_slots]
    explicit_ultimates = {str(spell.get("id", "")) for spell in selected if bool(spell.get("is_ultimate", False))}
    for idx, spell in enumerate(selected):
        slot_key = str(idx + 1)
        spell["slot"] = slot_key
        spell_id = str(spell.get("id", ""))
        spell.setdefault("skill", spell_id)
        if explicit_ultimates:
            spell["is_ultimate"] = spell_id in explicit_ultimates
        else:
            spell["is_ultimate"] = idx == min(3, len(selected) - 1)
        if "cooldown" in spell:
            try:
                base_cooldown = float(spell.get("cooldown", 0.0))
            except (TypeError, ValueError):
                base_cooldown = 0.0
            if base_cooldown > 0.0:
                cd_mult = float(SPELL_SLOT_COOLDOWN_MULT.get(slot_key, 1.0))
                cd_floor = float(MIN_SPELL_COOLDOWN_BY_SLOT.get(slot_key, 0.0))
                spell["cooldown"] = round(max(cd_floor, base_cooldown * cd_mult), 2)
    return selected


def class_skill_tree(class_id: str) -> List[Dict[str, object]]:
    data = CLASS_ARCHETYPES.get(class_id, {})
    nodes = data.get("skill_tree", [])
    if isinstance(nodes, list):
        return nodes
    return []


def _build_progressive_skill_tree(class_id: str) -> List[Dict[str, object]]:
    class_data = CLASS_ARCHETYPES.get(class_id, {})
    spellbook = class_spellbook(class_id)
    if not spellbook:
        return class_skill_tree(class_id)

    core_meta = CLASS_CORE_SKILL_META.get(class_id)
    if not isinstance(core_meta, dict):
        return class_skill_tree(class_id)
    core_id = str(core_meta.get("id", f"{class_id}_core"))
    core_name = str(core_meta.get("name", "Core"))
    core_desc = str(core_meta.get("desc", "Class discipline foundation."))

    blueprint = PROGRESSIVE_SKILL_BLUEPRINTS.get(class_id, {})
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

    spell_count = len(spellbook)
    col_count = max(1, min(5, 4 if spell_count <= 8 else 5))
    if spell_count <= 4:
        col_count = max(1, spell_count)
    row_count = max(1, (spell_count + col_count - 1) // col_count)
    x_min = 0.12
    x_max = 0.88
    x_step = 0.0 if col_count <= 1 else (x_max - x_min) / float(col_count - 1)
    unlock_top = 0.22
    unlock_bottom = 0.66
    row_step = 0.0 if row_count <= 1 else (unlock_bottom - unlock_top) / float(row_count - 1)
    tier_gap = 0.12

    for idx, spell in enumerate(spellbook):
        spell_id = str(spell.get("id", ""))
        spell_name = str(spell.get("name", spell_id))
        if not spell_id:
            continue

        lane = blueprint.get(spell_id, {})
        tier2 = lane.get("tier2", {})
        tier3 = lane.get("tier3", {})

        tier2_id = f"{spell_id}_tier2"
        tier3_id = f"{spell_id}_tier3"
        col = idx % col_count
        row = idx // col_count
        x = x_min + x_step * col if col_count > 1 else 0.50
        unlock_y = unlock_top + row_step * row
        tier2_y = min(0.86, unlock_y + tier_gap)
        tier3_y = min(0.92, unlock_y + tier_gap * 2.0)

        nodes.append(
            {
                "id": spell_id,
                "name": spell_name,
                "desc": f"Unlock {spell_name}.",
                "cost": 1,
                "requires": [core_id],
                "spell": spell_id,
                "bonus_power": 0.0,
                "cooldown_reduction": 0.0,
                "spell_mods": {},
                "pos": (x, unlock_y),
                "tier": "unlock",
            }
        )
        nodes.append(
            {
                "id": tier2_id,
                "name": str(tier2.get("name", f"{spell_name} Path I")),
                "desc": str(tier2.get("desc", "Refine this skill.")),
                "cost": 1,
                "requires": [spell_id],
                "spell": None,
                "bonus_power": 0.0,
                "cooldown_reduction": 0.0,
                "spell_mods": {spell_id: dict(tier2.get("mods", {}))},
                "pos": (x, tier2_y),
                "tier": "evolve",
            }
        )
        nodes.append(
            {
                "id": tier3_id,
                "name": str(tier3.get("name", f"{spell_name} Path II")),
                "desc": str(tier3.get("desc", "Master this skill's advanced form.")),
                "cost": 2,
                "requires": [tier2_id],
                "spell": None,
                "bonus_power": 0.0,
                "cooldown_reduction": 0.0,
                "spell_mods": {spell_id: dict(tier3.get("mods", {}))},
                "pos": (x, tier3_y),
                "tier": "mastery",
            }
        )

    if isinstance(class_data, dict):
        starter = [core_id]
        if spellbook:
            first_spell_id = str(spellbook[0].get("id", ""))
            if first_spell_id:
                starter.append(first_spell_id)
        class_data["starter_skills"] = starter

    return nodes


def rebuild_progressive_skill_trees() -> None:
    for class_id in CLASS_ORDER:
        class_data = CLASS_ARCHETYPES.get(class_id)
        if not isinstance(class_data, dict):
            continue
        if bool(class_data.get("custom_skill_tree", False)):
            continue
        class_data["skill_tree"] = _build_progressive_skill_tree(class_id)


rebuild_progressive_skill_trees()


def class_combat_stats(class_id: str) -> Dict[str, Union[float, str]]:
    stats = CLASS_COMBAT_STATS.get(class_id)
    if isinstance(stats, dict):
        return stats
    return {
        "max_hp": 170.0,
        "max_mana": 170.0,
        "mana_regen": 12.0,
        "basic_cooldown": 0.30,
        "basic_damage": 18.0,
        "basic_type": "cast",
    }


PASSIVE_EFFECT_DEFAULTS: Dict[str, float] = {
    "damage_mult": 1.0,
    "mana_regen_mult": 1.0,
    "mana_cost_mult": 1.0,
    "spell_cooldown_mult": 1.0,
    "basic_cooldown_mult": 1.0,
    "move_speed_mult": 1.0,
    "incoming_damage_mult": 1.0,
}


def class_passive_data(class_id: str) -> Dict[str, object]:
    passive = CLASS_PASSIVES.get(class_id)
    if isinstance(passive, dict):
        return passive
    for fallback in CLASS_ORDER:
        fallback_passive = CLASS_PASSIVES.get(fallback)
        if isinstance(fallback_passive, dict):
            return fallback_passive
    return {
        "id": "generic_class_passive",
        "name": "Class Passive",
        "desc": "A core discipline bonus for this class.",
        "glyph": "star",
        "icon_colors": {"base": (62, 62, 70), "accent": (198, 198, 212), "line": (238, 238, 248)},
        "effects": {},
    }


def class_passive_effects(class_id: str) -> Dict[str, float]:
    data = class_passive_data(class_id)
    raw = data.get("effects")
    raw_effects = raw if isinstance(raw, dict) else {}
    out = dict(PASSIVE_EFFECT_DEFAULTS)
    for key, base in PASSIVE_EFFECT_DEFAULTS.items():
        try:
            out[key] = max(0.05, float(raw_effects.get(key, base)))
        except (TypeError, ValueError):
            out[key] = base
    return out


def _format_effect_percent(prefix: str, value: float) -> str:
    sign = "+" if value >= 0.0 else "-"
    pct = abs(value) * 100.0
    if pct >= 10.0:
        return f"{sign}{int(round(pct))}% {prefix}"
    return f"{sign}{pct:.1f}% {prefix}"


def class_passive_effect_lines(passive: Dict[str, object], max_lines: int = 3) -> List[str]:
    raw = passive.get("effects")
    effects = raw if isinstance(raw, dict) else {}
    lines: List[str] = []

    def val(key: str, default: float = 1.0) -> float:
        try:
            return float(effects.get(key, default))
        except (TypeError, ValueError):
            return default

    damage_mult = val("damage_mult", 1.0)
    if abs(damage_mult - 1.0) > 0.0005:
        lines.append(_format_effect_percent("damage", damage_mult - 1.0))

    mana_regen_mult = val("mana_regen_mult", 1.0)
    if abs(mana_regen_mult - 1.0) > 0.0005:
        lines.append(_format_effect_percent("mana regen", mana_regen_mult - 1.0))

    mana_cost_mult = val("mana_cost_mult", 1.0)
    if abs(mana_cost_mult - 1.0) > 0.0005:
        lines.append(_format_effect_percent("spell mana cost", 1.0 - mana_cost_mult))

    spell_cdr_mult = val("spell_cooldown_mult", 1.0)
    if abs(spell_cdr_mult - 1.0) > 0.0005:
        lines.append(_format_effect_percent("spell cooldown recovery", 1.0 - spell_cdr_mult))

    basic_cdr_mult = val("basic_cooldown_mult", 1.0)
    if abs(basic_cdr_mult - 1.0) > 0.0005:
        lines.append(_format_effect_percent("basic attack recovery", 1.0 - basic_cdr_mult))

    move_speed_mult = val("move_speed_mult", 1.0)
    if abs(move_speed_mult - 1.0) > 0.0005:
        lines.append(_format_effect_percent("move speed", move_speed_mult - 1.0))

    incoming_mult = val("incoming_damage_mult", 1.0)
    if abs(incoming_mult - 1.0) > 0.0005:
        if incoming_mult < 1.0:
            lines.append(_format_effect_percent("damage reduction", 1.0 - incoming_mult))
        else:
            lines.append(_format_effect_percent("incoming damage taken", -(incoming_mult - 1.0)))

    return lines[: max(1, int(max_lines))]


def all_spell_defs() -> List[Dict[str, object]]:
    spells: List[Dict[str, object]] = []
    for class_id in CLASS_ORDER:
        spells.extend(class_spellbook(class_id))
    return spells


def spell_mana_cost(spell: Dict[str, object], class_id: str = "") -> float:
    slot = str(spell.get("slot", "1"))
    if "mana_cost" in spell:
        base = max(0.0, float(spell.get("mana_cost", 0.0)))
    else:
        default_costs = {"1": 14.0, "2": 22.0, "3": 30.0, "4": 38.0}
        base = float(default_costs.get(slot, 18.0))
    slot_mult = float(SPELL_SLOT_MANA_MULT.get(slot, 1.10))
    scale = MANA_COST_SCALE.get(class_id, 1.0)
    return max(1.0, round(base * slot_mult * scale, 1))


def skill_damage_bonus(unlocked_skills: Set[str], skill_tree_nodes: List[Dict[str, object]]) -> float:
    bonus = 0.0
    for node in skill_tree_nodes:
        node_id = str(node.get("id", ""))
        if node_id in unlocked_skills:
            bonus += float(node.get("bonus_power", 0.0))
    return bonus


def skill_cooldown_scale(unlocked_skills: Set[str], skill_tree_nodes: List[Dict[str, object]]) -> float:
    reduction = 0.0
    for node in skill_tree_nodes:
        node_id = str(node.get("id", ""))
        if node_id in unlocked_skills:
            reduction += float(node.get("cooldown_reduction", 0.0))
    return clamp(1.0 - reduction, 0.75, 1.0)


def skill_spell_modifiers(
    unlocked_skills: Set[str],
    skill_tree_nodes: List[Dict[str, object]],
) -> Dict[str, Dict[str, float]]:
    """Aggregate unlocked per-spell modifiers from skill nodes."""
    mult_keys = {
        "damage_mult",
        "speed_mult",
        "radius_mult",
        "max_radius_mult",
        "duration_mult",
        "interval_mult",
        "mana_mult",
        "cooldown_mult",
        "impact_nova_damage_mult",
    }
    mods_by_spell: Dict[str, Dict[str, float]] = {}
    for node in skill_tree_nodes:
        node_id = str(node.get("id", ""))
        if node_id not in unlocked_skills:
            continue
        spell_mods = node.get("spell_mods")
        if not isinstance(spell_mods, dict):
            continue
        for spell_id, raw_mods in spell_mods.items():
            if not isinstance(raw_mods, dict):
                continue
            sid = str(spell_id)
            bucket = mods_by_spell.setdefault(sid, {})
            for key, raw_val in raw_mods.items():
                try:
                    val = float(raw_val)
                except (TypeError, ValueError):
                    continue
                if key in mult_keys:
                    bucket[key] = float(bucket.get(key, 1.0)) * val
                else:
                    bucket[key] = float(bucket.get(key, 0.0)) + val
    return mods_by_spell
