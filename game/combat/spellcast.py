"""game/combat/spellcast.py — basic attacks, spell casting, spell-effect update & render."""
import math
import random
import colorsys
from typing import Dict, List, Optional, Tuple, Any, Union, Set

import pygame
from pygame import Vector2

from game.constants import *
from game.utils import *
from game.nav import *
from game.vfx import *
from game.gameplay_math import *
from game.sprites import *
from game.classes_runtime import *
from game.systems.core import *
from game.render.props import *

__all__ = [
    'cast_basic_attack',
    'cast_spell',
    'update_spell_effects',
    'draw_spell_effects',
    'spell_is_unlocked',
]


def cast_basic_attack(
    class_id: str,
    player_pos: Vector2,
    facing: int,
    target_pos: Vector2,
    spell_effects: List[Dict[str, object]],
    bonus_power: float = 0.0,
    damage_mult: float = 1.0,
    homing_target_id: Optional[int] = None,
) -> None:
    stats = class_combat_stats(class_id)
    base_damage = (float(stats.get("basic_damage", 18.0)) + bonus_power * 2.0) * max(0.1, float(damage_mult))
    basic_type = str(stats.get("basic_type", "cast"))
    vfx_scale = clamp(1.0 + bonus_power * 0.08, 1.0, 2.2)
    core_col, accent_col, _ = spell_vfx_palette(f"{class_id}_basic_attack", {})

    if basic_type == "melee":
        direction = target_pos - player_pos
        if direction.length_squared() <= 1e-4:
            direction = Vector2(1 if facing >= 0 else -1, 0)
        direction = direction.normalize()
        spell_effects.append(
            {
                "kind": "melee_arc",
                "pos": Vector2(player_pos.x, player_pos.y - 8),
                "dir": Vector2(direction),
                "life": 0.16,
                "duration": 0.16,
                "radius": 86.0,
                "damage": base_damage,
                "hit": set(),
                "colors": {"ring": (232, 210, 146), "inner": (128, 96, 52)},
                "vfx": vfx_scale,
            }
        )
        spawn_particle_burst(
            spell_effects,
            Vector2(player_pos.x, player_pos.y - 10),
            core_col,
            accent_col,
            count=10,
            speed_min=120.0,
            speed_max=280.0,
            life_min=0.12,
            life_max=0.36,
            size_start=5.0,
            size_end=0.8,
            spread=1.45,
            direction=direction,
            drag=1.9,
            vfx_scale=vfx_scale,
        )
        return

    direction = target_pos - player_pos
    if direction.length_squared() <= 1e-4:
        direction = Vector2(1 if facing >= 0 else -1, 0)
    direction = direction.normalize()

    core = (224, 208, 164)
    trail = (244, 226, 178)
    outline = (112, 90, 42)
    if class_id in ("mage", "necromancer"):
        core = (206, 196, 252) if class_id == "necromancer" else (234, 208, 156)
        trail = (176, 142, 226) if class_id == "necromancer" else (255, 196, 116)
        outline = (74, 52, 104) if class_id == "necromancer" else (120, 72, 34)

    spell_effects.append(
        {
            "kind": "projectile",
            "spell_id": f"{class_id}_basic_attack",
            "pos": Vector2(player_pos.x, player_pos.y - 24),
            "vel": direction * 760.0,
            "life": 0.55,
            "duration": 0.55,
            "radius": 14.0,
            "damage": base_damage,
            "hit": set(),
            "colors": {"core": core, "outline": outline, "trail": trail},
            "trail_timer": 0.0,
            "vfx": vfx_scale,
            "homing_enabled": True,
            "homing_target_id": homing_target_id,
            "homing_turn_rate": 15.0,
            "homing_acquire_radius": 700.0,
        }
    )
    spawn_particle_burst(
        spell_effects,
        Vector2(player_pos.x, player_pos.y - 24),
        core_col,
        accent_col,
        count=8,
        speed_min=80.0,
        speed_max=200.0,
        life_min=0.12,
        life_max=0.30,
        size_start=4.2,
        size_end=0.7,
        spread=0.75,
        direction=direction,
        drag=1.6,
        vfx_scale=vfx_scale,
    )


def cast_spell(
    spell: dict[str, object],
    player_pos: Vector2,
    target_pos: Vector2,
    facing: int,
    spell_effects: List[Dict[str, object]],
    bonus_power: float = 0.0,
    spell_mods: Optional[Dict[str, float]] = None,
    class_damage_mult: float = 1.0,
    homing_target_id: Optional[int] = None,
) -> None:
    spell_id = str(spell.get("id", ""))
    kind = str(spell.get("kind", ""))
    mods = spell_mods if isinstance(spell_mods, dict) else {}
    damage_mult = max(0.1, float(mods.get("damage_mult", 1.0)))
    speed_mult = max(0.1, float(mods.get("speed_mult", 1.0)))
    radius_mult = max(0.1, float(mods.get("radius_mult", 1.0)))
    max_radius_mult = max(0.1, float(mods.get("max_radius_mult", 1.0)))
    duration_mult = max(0.1, float(mods.get("duration_mult", 1.0)))
    interval_mult = max(0.2, float(mods.get("interval_mult", 1.0)))
    bonus_damage = float(mods.get("bonus_damage", 0.0))
    cast_range = max(0.0, float(spell.get("cast_range", 0.0)) + max(0.0, float(mods.get("cast_range_bonus", 0.0))))
    self_cast = bool(spell.get("self_cast", False))
    anim_set = str(spell.get("anim_set", "")).strip()

    def anim_payload(size: int, loop: bool = False, rate: float = 1.0) -> Dict[str, object]:
        if not anim_set:
            return {}
        payload: dict[str, object] = {
            "anim_set": anim_set,
            "anim_size": int(max(32, size)),
        }
        if loop:
            payload["anim_loop"] = True
            payload["anim_rate"] = max(0.25, float(rate))
        return payload

    resolved_target = Vector2(target_pos)
    if cast_range > 0.0:
        aim = resolved_target - player_pos
        if aim.length_squared() > cast_range * cast_range:
            if aim.length_squared() <= 1e-5:
                aim = Vector2(1 if facing >= 0 else -1, 0)
            resolved_target = player_pos + aim.normalize() * cast_range

    base_damage = (float(spell.get("damage", 20.0)) + bonus_power * 3.0 + bonus_damage) * damage_mult * max(0.1, float(class_damage_mult))
    colors = spell.get("colors") if isinstance(spell.get("colors"), dict) else {}
    core_col, accent_col, shadow_col = spell_vfx_palette(spell_id, colors)
    vfx_scale = 1.0
    for key, val in mods.items():
        v = float(val)
        if key.endswith("_mult"):
            if v > 1.0:
                vfx_scale += (v - 1.0) * 0.9
            else:
                vfx_scale += (1.0 - v) * 0.28
        elif key in ("projectile_count_bonus", "pierce_bonus"):
            vfx_scale += max(0.0, v) * 0.55
        elif key in ("impact_nova_radius_bonus",):
            vfx_scale += max(0.0, v) / 80.0
    vfx_scale += clamp(bonus_power * 0.06, 0.0, 0.7)
    vfx_scale = clamp(vfx_scale, 1.0, 3.4)
    default_durations = {
        "projectile": 0.86,
        "nova": 0.72,
        "frost_wave": 0.54,
        "orb": 1.68,
        "ward": 1.96,
        "melee_arc": 0.22,
        "cone": 0.22,
        "pillar": 5.0,
    }
    duration = float(spell.get("duration", default_durations.get(kind, 1.0))) * duration_mult
    if duration <= 0.0:
        duration = 1.0

    def spawn_rogue_spell_vfx(
        sid: str,
        origin: Vector2,
        aim_dir: Optional[Vector2] = None,
    ) -> None:
        rogue_dir = Vector2(aim_dir) if isinstance(aim_dir, Vector2) and aim_dir.length_squared() > 1e-6 else None
        if isinstance(rogue_dir, Vector2):
            rogue_dir = rogue_dir.normalize()

        if sid == "rogue_shadow_knife":
            spawn_particle_burst(
                spell_effects,
                origin,
                (212, 220, 238),
                (110, 122, 156),
                count=18,
                speed_min=130.0,
                speed_max=320.0,
                life_min=0.10,
                life_max=0.28,
                size_start=4.2,
                size_end=0.6,
                spread=0.95,
                direction=rogue_dir,
                drag=2.2,
                vfx_scale=vfx_scale,
            )
            spawn_particle_burst(
                spell_effects,
                origin,
                (92, 84, 118),
                (52, 50, 72),
                count=12,
                speed_min=70.0,
                speed_max=170.0,
                life_min=0.14,
                life_max=0.36,
                size_start=4.8,
                size_end=1.0,
                spread=math.tau,
                gravity=-18.0,
                drag=1.4,
                vfx_scale=vfx_scale,
            )
        elif sid == "rogue_smoke_burst":
            spawn_particle_burst(
                spell_effects,
                origin,
                (178, 166, 214),
                (82, 76, 114),
                count=28,
                speed_min=55.0,
                speed_max=190.0,
                life_min=0.20,
                life_max=0.52,
                size_start=5.2,
                size_end=1.1,
                spread=math.tau,
                gravity=-30.0,
                drag=1.2,
                vfx_scale=vfx_scale,
            )
        elif sid == "rogue_venom_trap":
            spawn_particle_burst(
                spell_effects,
                origin,
                (112, 220, 124),
                (56, 134, 70),
                count=22,
                speed_min=44.0,
                speed_max=146.0,
                life_min=0.24,
                life_max=0.64,
                size_start=4.6,
                size_end=0.9,
                spread=math.tau,
                gravity=-20.0,
                drag=1.3,
                vfx_scale=vfx_scale,
            )
        elif sid == "rogue_evasion_sigil":
            spawn_particle_burst(
                spell_effects,
                origin,
                (222, 206, 246),
                (126, 102, 178),
                count=46,
                speed_min=120.0,
                speed_max=320.0,
                life_min=0.18,
                life_max=0.62,
                size_start=6.0,
                size_end=0.8,
                spread=math.tau,
                gravity=-44.0,
                drag=1.1,
                vfx_scale=vfx_scale,
            )
            spawn_particle_burst(
                spell_effects,
                origin,
                (102, 86, 154),
                (58, 46, 102),
                count=34,
                speed_min=80.0,
                speed_max=200.0,
                life_min=0.26,
                life_max=0.82,
                size_start=5.0,
                size_end=0.8,
                spread=math.tau,
                gravity=-24.0,
                drag=1.2,
                vfx_scale=vfx_scale,
            )
            for i in range(8):
                ang = (math.tau * i) / 8.0
                shock_dir = Vector2(math.cos(ang), math.sin(ang))
                spawn_particle_burst(
                    spell_effects,
                    origin + shock_dir * 6.0,
                    (244, 232, 255),
                    (150, 132, 210),
                    count=8,
                    speed_min=180.0,
                    speed_max=360.0,
                    life_min=0.10,
                    life_max=0.34,
                    size_start=3.6,
                    size_end=0.5,
                    spread=0.30,
                    direction=shock_dir,
                    drag=1.6,
                    vfx_scale=vfx_scale,
                )

    def spawn_non_rogue_spell_vfx(
        sid: str,
        origin: Vector2,
        spell_kind: str,
        aim_dir: Optional[Vector2] = None,
        area_radius: float = 0.0,
    ) -> None:
        cls = spell_class_id(sid)
        if cls in ("", "rogue"):
            return
        theme = CLASS_SPELL_VFX_THEMES.get(cls, {})
        themed_core = theme.get("core", core_col)
        themed_accent = theme.get("accent", accent_col)
        themed_shadow = theme.get("shadow", shadow_col)

        cast_dir = Vector2(aim_dir) if isinstance(aim_dir, Vector2) and aim_dir.length_squared() > 1e-6 else None
        if isinstance(cast_dir, Vector2):
            cast_dir = cast_dir.normalize()

        if spell_kind == "projectile":
            spawn_particle_burst(
                spell_effects,
                origin,
                themed_core,
                themed_accent,
                count=16,
                speed_min=130.0,
                speed_max=320.0,
                life_min=0.10,
                life_max=0.28,
                size_start=4.2,
                size_end=0.6,
                spread=0.42,
                direction=cast_dir,
                drag=1.9,
                vfx_scale=vfx_scale,
            )
            spawn_particle_burst(
                spell_effects,
                origin,
                themed_accent,
                themed_shadow,
                count=12,
                speed_min=60.0,
                speed_max=170.0,
                life_min=0.14,
                life_max=0.34,
                size_start=3.4,
                size_end=0.5,
                spread=math.tau,
                gravity=-16.0,
                drag=1.3,
                vfx_scale=vfx_scale,
            )
        elif spell_kind == "nova":
            spawn_particle_burst(
                spell_effects,
                origin,
                themed_core,
                themed_accent,
                count=30,
                speed_min=120.0,
                speed_max=330.0,
                life_min=0.18,
                life_max=0.50,
                size_start=5.6,
                size_end=0.7,
                spread=math.tau,
                gravity=20.0,
                drag=1.2,
                vfx_scale=vfx_scale,
            )
            spokes = 8
            for i in range(spokes):
                ang = (math.tau * i) / float(spokes)
                d = Vector2(math.cos(ang), math.sin(ang))
                spawn_particle_burst(
                    spell_effects,
                    origin + d * 8.0,
                    themed_accent,
                    themed_shadow,
                    count=4,
                    speed_min=160.0,
                    speed_max=340.0,
                    life_min=0.08,
                    life_max=0.24,
                    size_start=3.2,
                    size_end=0.5,
                    spread=0.26,
                    direction=d,
                    drag=1.5,
                    vfx_scale=vfx_scale,
                )
        elif spell_kind == "orb":
            spawn_particle_burst(
                spell_effects,
                origin,
                themed_core,
                themed_accent,
                count=22,
                speed_min=70.0,
                speed_max=190.0,
                life_min=0.20,
                life_max=0.58,
                size_start=5.2,
                size_end=0.8,
                spread=math.tau,
                gravity=-18.0,
                drag=1.3,
                vfx_scale=vfx_scale,
            )
            if area_radius > 10.0:
                sat_count = 5
                sat_r = min(max(18.0, area_radius * 0.28), area_radius * 0.82)
                for i in range(sat_count):
                    ang = (math.tau * i) / float(sat_count)
                    sat_pos = origin + Vector2(math.cos(ang), math.sin(ang)) * sat_r
                    spawn_particle_burst(
                        spell_effects,
                        sat_pos,
                        themed_accent,
                        themed_shadow,
                        count=2,
                        speed_min=44.0,
                        speed_max=100.0,
                        life_min=0.12,
                        life_max=0.30,
                        size_start=2.8,
                        size_end=0.5,
                        spread=math.tau,
                        drag=1.4,
                        vfx_scale=vfx_scale,
                    )
        elif spell_kind == "ward":
            spawn_particle_burst(
                spell_effects,
                origin,
                themed_accent,
                themed_shadow,
                count=26,
                speed_min=60.0,
                speed_max=170.0,
                life_min=0.24,
                life_max=0.74,
                size_start=4.6,
                size_end=0.8,
                spread=math.tau,
                gravity=-34.0,
                drag=1.2,
                vfx_scale=vfx_scale,
            )
            if area_radius > 18.0:
                ring_count = 9
                ring_r = min(max(26.0, area_radius * 0.66), area_radius * 0.96)
                for i in range(ring_count):
                    ang = (math.tau * i) / float(ring_count)
                    d = Vector2(math.cos(ang), math.sin(ang))
                    spawn_particle_burst(
                        spell_effects,
                        origin + d * ring_r,
                        themed_core,
                        themed_accent,
                        count=2,
                        speed_min=60.0,
                        speed_max=134.0,
                        life_min=0.12,
                        life_max=0.36,
                        size_start=2.8,
                        size_end=0.5,
                        spread=0.36,
                        direction=-d,
                        drag=1.5,
                        vfx_scale=vfx_scale,
                    )
        elif spell_kind == "melee_arc":
            spawn_particle_burst(
                spell_effects,
                origin,
                themed_core,
                themed_accent,
                count=18,
                speed_min=120.0,
                speed_max=280.0,
                life_min=0.10,
                life_max=0.28,
                size_start=3.8,
                size_end=0.6,
                spread=0.95,
                direction=cast_dir,
                drag=1.8,
                vfx_scale=vfx_scale,
            )
            spawn_particle_burst(
                spell_effects,
                origin,
                themed_accent,
                themed_shadow,
                count=12,
                speed_min=70.0,
                speed_max=190.0,
                life_min=0.12,
                life_max=0.30,
                size_start=3.0,
                size_end=0.5,
                spread=math.tau,
                gravity=14.0,
                drag=1.4,
                vfx_scale=vfx_scale,
            )
        elif spell_kind == "cone":
            spawn_particle_burst(
                spell_effects,
                origin,
                themed_core,
                themed_accent,
                count=22,
                speed_min=110.0,
                speed_max=260.0,
                life_min=0.12,
                life_max=0.32,
                size_start=4.0,
                size_end=0.6,
                spread=0.70,
                direction=cast_dir,
                drag=1.6,
                vfx_scale=vfx_scale,
            )
            spawn_particle_burst(
                spell_effects,
                origin,
                themed_accent,
                themed_shadow,
                count=12,
                speed_min=60.0,
                speed_max=150.0,
                life_min=0.12,
                life_max=0.30,
                size_start=3.0,
                size_end=0.5,
                spread=math.tau,
                gravity=10.0,
                drag=1.4,
                vfx_scale=vfx_scale,
            )
        elif spell_kind == "pillar":
            spawn_particle_burst(
                spell_effects,
                origin,
                themed_accent,
                themed_shadow,
                count=20,
                speed_min=40.0,
                speed_max=120.0,
                life_min=0.20,
                life_max=0.52,
                size_start=4.4,
                size_end=0.7,
                spread=math.tau,
                gravity=-32.0,
                drag=1.3,
                vfx_scale=vfx_scale,
            )

    if kind == "projectile":
        direction = resolved_target - player_pos
        if direction.length_squared() <= 1e-4:
            direction = Vector2(1 if facing >= 0 else -1, 0)
        direction = direction.normalize()
        is_firebolt = spell_id in ("mage_fire_ball", "mage_searing_bolt")
        is_frostbolt = spell_id in ("mage_wind", "mage_frostbolt")
        count = max(1, 1 + int(round(float(mods.get("projectile_count_bonus", 0.0)))))
        spread_deg = max(0.0, float(mods.get("spread_deg_bonus", 0.0)))
        spread = math.radians(spread_deg)
        pierce_count = max(0, int(round(float(mods.get("pierce_bonus", 0.0)))))
        impact_nova_radius = max(0.0, float(mods.get("impact_nova_radius_bonus", 0.0)))
        impact_nova_damage_mult = max(0.1, float(mods.get("impact_nova_damage_mult", 1.0)))

        offsets = [0.0]
        if count > 1 and spread > 0.0:
            step = spread / float(count - 1)
            offsets = [(-spread * 0.5) + step * i for i in range(count)]
        elif count > 1:
            offsets = [0.0 for _ in range(count)]

        for off in offsets:
            shot_dir = rotate_vec(direction, off) if abs(off) > 1e-4 else direction
            projectile_payload: Dict[str, object] = {
                "kind": "projectile",
                "spell_id": spell_id,
                "pos": Vector2(player_pos.x, player_pos.y - 28),
                "vel": shot_dir * float(spell.get("speed", 620.0)) * speed_mult,
                "life": duration,
                "duration": duration,
                "radius": float(spell.get("radius", 18.0)) * radius_mult,
                "damage": base_damage,
                "hit": set(),
                "colors": colors,
                "pierce_left": pierce_count,
                "impact_nova_radius": impact_nova_radius,
                "impact_nova_damage_mult": impact_nova_damage_mult,
                "scorch_bonus": float(spell.get("scorch_bonus", 0.0)),
                "scorch_duration": float(spell.get("scorch_duration", 0.0)),
                "trail_timer": 0.0,
                "vfx": vfx_scale,
                "homing_enabled": True,
                "homing_target_id": homing_target_id,
                "homing_turn_rate": 16.0,
                "homing_acquire_radius": 760.0,
                **anim_payload(74),
            }
            if is_firebolt:
                projectile_payload.update(
                    {
                        "trail_timer": 0.0,
                        "smoke_timer": 0.0,
                        "spark_timer": 0.0,
                        "firebolt_glow_phase": random.uniform(0.0, math.tau),
                        "homing_turn_rate": 18.0,
                    }
                )
            elif is_frostbolt:
                projectile_payload.update(
                    {
                        "frost_trail_timer": 0.0,
                        "frost_mist_timer": 0.0,
                        "frost_shard_timer": 0.0,
                        "frost_glow_phase": random.uniform(0.0, math.tau),
                        "homing_turn_rate": 17.0,
                    }
                )
            spell_effects.append(projectile_payload)
        spawn_particle_burst(
            spell_effects,
            Vector2(player_pos.x, player_pos.y - 28),
            core_col,
            accent_col,
            count=12 + count * 2,
            speed_min=90.0,
            speed_max=240.0,
            life_min=0.12,
            life_max=0.34,
            size_start=4.8,
            size_end=0.8,
            spread=0.85,
            direction=direction,
            drag=1.8,
            vfx_scale=vfx_scale,
        )
        if is_firebolt:
            muzzle = Vector2(player_pos.x, player_pos.y - 28)
            spawn_particle_burst(
                spell_effects,
                muzzle,
                (255, 236, 180),
                (255, 158, 80),
                count=14 + count * 2,
                speed_min=140.0,
                speed_max=360.0,
                life_min=0.10,
                life_max=0.28,
                size_start=4.4,
                size_end=0.5,
                spread=0.56,
                direction=direction,
                drag=2.0,
                vfx_scale=vfx_scale,
            )
            spawn_particle_burst(
                spell_effects,
                muzzle,
                (126, 84, 62),
                (74, 56, 46),
                count=8 + count,
                speed_min=34.0,
                speed_max=110.0,
                life_min=0.20,
                life_max=0.48,
                size_start=5.2,
                size_end=1.0,
                spread=1.10,
                direction=-direction,
                gravity=-18.0,
                drag=1.4,
                vfx_scale=vfx_scale,
            )
        elif is_frostbolt:
            muzzle = Vector2(player_pos.x, player_pos.y - 28)
            spawn_particle_burst(
                spell_effects,
                muzzle,
                (226, 244, 255),
                (160, 214, 255),
                count=14 + count * 2,
                speed_min=120.0,
                speed_max=320.0,
                life_min=0.10,
                life_max=0.30,
                size_start=4.2,
                size_end=0.5,
                spread=0.58,
                direction=direction,
                gravity=-8.0,
                drag=1.9,
                vfx_scale=vfx_scale,
            )
            spawn_particle_burst(
                spell_effects,
                muzzle,
                (172, 206, 234),
                (108, 146, 186),
                count=8 + count,
                speed_min=22.0,
                speed_max=88.0,
                life_min=0.22,
                life_max=0.54,
                size_start=5.0,
                size_end=1.0,
                spread=1.00,
                direction=-direction,
                gravity=-24.0,
                drag=1.5,
                vfx_scale=vfx_scale,
            )
        if spell_id.startswith("rogue_"):
            spawn_rogue_spell_vfx(spell_id, Vector2(player_pos.x, player_pos.y - 28), direction)
        else:
            spawn_non_rogue_spell_vfx(spell_id, Vector2(player_pos.x, player_pos.y - 28), "projectile", direction)
    elif kind == "nova":
        zone_pos = Vector2(player_pos.x, player_pos.y - 6) if self_cast else Vector2(resolved_target)
        freeze_duration = max(0.0, float(spell.get("freeze_duration", 0.0)) * duration_mult)
        max_radius = float(spell.get("max_radius", 176.0)) * max_radius_mult * radius_mult
        slow_duration = max(0.0, float(spell.get("slow_duration", 0.0)) * duration_mult)
        slow_potency = max(0.0, float(spell.get("slow_potency", 0.0)))
        knockback_force = max(0.0, float(spell.get("knockback", 0.0)) * radius_mult)
        nova_payload: Dict[str, object] = {
            "kind": "nova",
            "spell_id": spell_id,
            "pos": zone_pos,
            "life": duration,
            "duration": duration,
            "max_radius": max_radius,
            "damage": base_damage,
            "freeze_duration": freeze_duration,
            "slow_duration": slow_duration,
            "slow_potency": slow_potency,
            "knockback": knockback_force,
            "knockback_small_only": bool(spell.get("knockback_small_only", False)),
            "hit": set(),
            "colors": colors,
            "vfx": vfx_scale,
            **anim_payload(96),
        }
        if spell_id in ("mage_water", "mage_frost_nova"):
            nova_payload.update(
                {
                    "frost_shimmer_timer": 0.0,
                    "frost_mist_timer": 0.0,
                    "frost_seed": random.uniform(0.0, math.tau),
                }
            )
        spell_effects.append(nova_payload)
        spawn_particle_burst(
            spell_effects,
            zone_pos,
            core_col,
            accent_col,
            count=24,
            speed_min=110.0,
            speed_max=280.0,
            life_min=0.20,
            life_max=0.52,
            size_start=6.0,
            size_end=0.9,
            spread=math.tau,
            gravity=30.0,
            drag=1.2,
            vfx_scale=vfx_scale,
        )
        if spell_id in ("mage_water", "mage_frost_nova"):
            spawn_particle_burst(
                spell_effects,
                zone_pos,
                (232, 250, 255),
                (164, 214, 255),
                count=20,
                speed_min=120.0,
                speed_max=290.0,
                life_min=0.12,
                life_max=0.32,
                size_start=4.2,
                size_end=0.5,
                spread=math.tau,
                gravity=-8.0,
                drag=1.8,
                vfx_scale=vfx_scale,
            )
            spawn_particle_burst(
                spell_effects,
                zone_pos,
                (192, 224, 246),
                (112, 154, 196),
                count=10,
                speed_min=22.0,
                speed_max=84.0,
                life_min=0.22,
                life_max=0.62,
                size_start=5.0,
                size_end=1.0,
                spread=math.tau,
                gravity=-22.0,
                drag=1.3,
                vfx_scale=vfx_scale,
            )
            ring_count = 12
            ring_radius = max(22.0, max_radius * 0.58)
            for i in range(ring_count):
                ang = (math.tau * i) / float(ring_count)
                d = Vector2(math.cos(ang), math.sin(ang))
                spawn_particle_burst(
                    spell_effects,
                    zone_pos + d * ring_radius,
                    (238, 252, 255),
                    (178, 226, 255),
                    count=1,
                    speed_min=72.0,
                    speed_max=220.0,
                    life_min=0.10,
                    life_max=0.26,
                    size_start=2.6,
                    size_end=0.4,
                    spread=0.34,
                    direction=d,
                    gravity=8.0,
                    drag=1.9,
                    vfx_scale=vfx_scale,
                )
        if spell_id.startswith("rogue_"):
            spawn_rogue_spell_vfx(spell_id, zone_pos)
        else:
            spawn_non_rogue_spell_vfx(spell_id, zone_pos, "nova")
    elif kind == "frost_wave":
        direction = resolved_target - player_pos
        if direction.length_squared() <= 1e-4:
            direction = Vector2(1 if facing >= 0 else -1, 0)
        direction = direction.normalize()
        origin = Vector2(player_pos.x, player_pos.y - 18.0)
        max_length = cast_range if cast_range > 0.0 else float(spell.get("cast_range", 540.0))
        max_length = clamp(max_length, 160.0, 1040.0)
        end = origin + direction * max_length
        wave_width = max(30.0, float(spell.get("radius", 82.0)) * radius_mult)
        freeze_duration = max(0.08, float(spell.get("freeze_duration", 1.1)) * duration_mult)
        frost_colors = {
            "core": colors.get("core", core_col),
            "trail": colors.get("trail", accent_col),
            "outline": colors.get("outline", shadow_col),
            "ring": colors.get("ring", accent_col),
            "inner": colors.get("inner", core_col),
        }
        spell_effects.append(
            {
                "kind": "frost_wave",
                "spell_id": spell_id,
                "pos": Vector2(origin),
                "start": Vector2(origin),
                "end": Vector2(end),
                "dir": Vector2(direction),
                "life": duration,
                "duration": duration,
                "width": wave_width,
                "damage": base_damage,
                "freeze_duration": freeze_duration,
                "hit": set(),
                "hit_passives": set(),
                "prev_progress": 0.0,
                "ambient_timer": 0.0,
                "mist_timer": 0.0,
                "colors": frost_colors,
                "vfx": vfx_scale,
                **anim_payload(104, loop=True, rate=1.05),
            }
        )
        spawn_particle_burst(
            spell_effects,
            origin,
            (240, 252, 255),
            (170, 218, 255),
            count=30,
            speed_min=130.0,
            speed_max=340.0,
            life_min=0.16,
            life_max=0.44,
            size_start=5.2,
            size_end=0.7,
            spread=0.92,
            direction=direction,
            gravity=-12.0,
            drag=1.8,
            vfx_scale=vfx_scale * 1.06,
        )
        spawn_particle_burst(
            spell_effects,
            origin,
            (196, 230, 255),
            (112, 164, 216),
            count=16,
            speed_min=44.0,
            speed_max=130.0,
            life_min=0.26,
            life_max=0.72,
            size_start=5.8,
            size_end=1.1,
            spread=math.tau,
            gravity=-28.0,
            drag=1.4,
            vfx_scale=vfx_scale,
        )
        for i in range(5):
            ang = (-0.28 + i * 0.14) * math.pi
            spoke_dir = rotate_vec(direction, ang * 0.12)
            spawn_particle_burst(
                spell_effects,
                origin + direction * random.uniform(6.0, 18.0),
                (226, 246, 255),
                (154, 206, 250),
                count=4,
                speed_min=150.0,
                speed_max=330.0,
                life_min=0.08,
                life_max=0.22,
                size_start=3.2,
                size_end=0.4,
                spread=0.22,
                direction=spoke_dir,
                gravity=12.0,
                drag=2.0,
                vfx_scale=vfx_scale,
            )
        if spell_id.startswith("rogue_"):
            spawn_rogue_spell_vfx(spell_id, origin, direction)
        else:
            spawn_non_rogue_spell_vfx(spell_id, origin, "nova")
    elif kind == "melee_arc":
        direction = resolved_target - player_pos
        if direction.length_squared() <= 1e-4:
            direction = Vector2(1 if facing >= 0 else -1, 0)
        direction = direction.normalize()
        count = max(1, 1 + int(round(float(mods.get("projectile_count_bonus", 0.0)))))
        spread_deg = max(0.0, float(mods.get("spread_deg_bonus", 0.0)))
        spread = math.radians(spread_deg)
        impact_nova_radius = max(0.0, float(mods.get("impact_nova_radius_bonus", 0.0)))
        impact_nova_damage_mult = max(0.1, float(mods.get("impact_nova_damage_mult", 1.0)))

        offsets = [0.0]
        if count > 1 and spread > 0.0:
            step = spread / float(count - 1)
            offsets = [(-spread * 0.5) + step * i for i in range(count)]
        elif count > 1:
            offsets = [0.0 for _ in range(count)]

        swing_pos = Vector2(player_pos.x, player_pos.y - 8)
        reach = max(32.0, float(spell.get("radius", 86.0)) * radius_mult)
        arc_colors = {"ring": colors.get("ring", accent_col), "inner": colors.get("inner", shadow_col)}
        for off in offsets:
            arc_dir = rotate_vec(direction, off) if abs(off) > 1e-4 else direction
            spell_effects.append(
                {
                    "kind": "melee_arc",
                    "spell_id": spell_id,
                    "pos": Vector2(swing_pos),
                    "dir": Vector2(arc_dir),
                    "life": duration,
                    "duration": duration,
                    "radius": reach,
                    "damage": base_damage,
                    "hit": set(),
                    "colors": arc_colors,
                    "vfx": vfx_scale,
                    **anim_payload(84),
                }
            )
            if impact_nova_radius > 0.0:
                nova_pos = swing_pos + arc_dir * (reach * 0.85)
                spell_effects.append(
                    {
                        "kind": "nova",
                        "spell_id": f"{spell_id}_impact",
                        "pos": Vector2(nova_pos),
                        "life": 0.42,
                        "duration": 0.42,
                        "max_radius": impact_nova_radius,
                        "damage": base_damage * impact_nova_damage_mult,
                        "hit": set(),
                        "colors": {"ring": accent_col, "inner": core_col},
                        "vfx": vfx_scale,
                        **anim_payload(92),
                    }
                )
        spawn_particle_burst(
            spell_effects,
            swing_pos,
            accent_col,
            shadow_col,
            count=14 + count * 2,
            speed_min=90.0,
            speed_max=220.0,
            life_min=0.10,
            life_max=0.30,
            size_start=4.2,
            size_end=0.7,
            spread=1.2,
            direction=direction,
            drag=1.7,
            vfx_scale=vfx_scale,
        )
        if spell_id.startswith("rogue_"):
            spawn_rogue_spell_vfx(spell_id, swing_pos + direction * 18.0, direction)
        else:
            spawn_non_rogue_spell_vfx(spell_id, swing_pos + direction * 16.0, "melee_arc", direction)
    elif kind == "cone":
        direction = resolved_target - player_pos
        if direction.length_squared() <= 1e-4:
            direction = Vector2(1 if facing >= 0 else -1, 0)
        direction = direction.normalize()
        origin = Vector2(player_pos.x, player_pos.y - 8)
        reach = max(40.0, float(spell.get("radius", 150.0)) * radius_mult)
        cone_angle = max(20.0, float(spell.get("cone_angle", 90.0)))
        cone_colors = {
            "ring": colors.get("ring", accent_col),
            "inner": colors.get("inner", core_col),
            "trail": colors.get("trail", accent_col),
        }
        spell_effects.append(
            {
                "kind": "cone",
                "spell_id": spell_id,
                "pos": Vector2(origin),
                "dir": Vector2(direction),
                "life": duration,
                "duration": duration,
                "radius": reach,
                "angle": cone_angle,
                "damage": base_damage,
                "interrupt_duration": float(spell.get("interrupt_duration", 0.0)),
                "hit": set(),
                "colors": cone_colors,
                "vfx": vfx_scale,
                **anim_payload(90),
            }
        )
        spawn_particle_burst(
            spell_effects,
            origin + direction * 16.0,
            accent_col,
            shadow_col,
            count=16,
            speed_min=90.0,
            speed_max=220.0,
            life_min=0.10,
            life_max=0.30,
            size_start=4.0,
            size_end=0.6,
            spread=0.70,
            direction=direction,
            drag=1.7,
            vfx_scale=vfx_scale,
        )
        if spell_id.startswith("rogue_"):
            spawn_rogue_spell_vfx(spell_id, origin + direction * 14.0, direction)
        else:
            spawn_non_rogue_spell_vfx(spell_id, origin + direction * 12.0, "cone", direction, area_radius=reach)
    elif kind == "orb":
        zone_pos = Vector2(player_pos.x, player_pos.y - 8) if self_cast else Vector2(resolved_target)
        spell_effects.append(
            {
                "kind": "orb",
                "spell_id": spell_id,
                "pos": zone_pos,
                "life": duration,
                "duration": duration,
                "radius": float(spell.get("radius", 112.0)) * radius_mult,
                "damage": base_damage,
                "pulse": 0.0,
                "pulse_interval": max(0.08, float(spell.get("pulse_interval", 0.34)) * interval_mult),
                "colors": colors,
                "vfx": vfx_scale,
                "ambient_timer": 0.0,
                **anim_payload(94, loop=True, rate=1.0),
            }
        )
        spawn_particle_burst(
            spell_effects,
            zone_pos,
            core_col,
            accent_col,
            count=18,
            speed_min=60.0,
            speed_max=170.0,
            life_min=0.22,
            life_max=0.62,
            size_start=5.6,
            size_end=0.8,
            spread=math.tau,
            gravity=-20.0,
            drag=1.4,
            vfx_scale=vfx_scale,
        )
        if spell_id.startswith("rogue_"):
            spawn_rogue_spell_vfx(spell_id, zone_pos)
        else:
            spawn_non_rogue_spell_vfx(spell_id, zone_pos, "orb", area_radius=float(spell.get("radius", 112.0)) * radius_mult)
    elif kind == "ward":
        zone_pos = Vector2(player_pos.x, player_pos.y - 8) if self_cast else Vector2(resolved_target)
        spell_effects.append(
            {
                "kind": "ward",
                "spell_id": spell_id,
                "pos": zone_pos,
                "life": duration,
                "duration": duration,
                "radius": float(spell.get("radius", 108.0)) * radius_mult,
                "damage": base_damage,
                "tick": 0.0,
                "tick_interval": max(0.08, float(spell.get("tick_interval", 0.24)) * interval_mult),
                "colors": colors,
                "vfx": vfx_scale,
                "ambient_timer": 0.0,
                **anim_payload(100, loop=True, rate=0.9),
            }
        )
        spawn_particle_burst(
            spell_effects,
            zone_pos,
            accent_col,
            shadow_col,
            count=20,
            speed_min=50.0,
            speed_max=140.0,
            life_min=0.28,
            life_max=0.74,
            size_start=4.6,
            size_end=0.8,
            spread=math.tau,
            gravity=-40.0,
            drag=1.3,
            vfx_scale=vfx_scale,
        )
        if spell_id == "rogue_evasion_sigil":
            burst_radius = max(120.0, float(spell.get("ultimate_burst_radius", 210.0)) * max_radius_mult * radius_mult)
            burst_damage_mult = max(0.6, float(spell.get("ultimate_burst_damage_mult", 1.20)))
            spell_effects.append(
                {
                    "kind": "nova",
                    "spell_id": "rogue_evasion_sigil_burst",
                    "pos": Vector2(zone_pos),
                    "life": 0.52,
                    "duration": 0.52,
                    "max_radius": burst_radius,
                    "damage": base_damage * burst_damage_mult,
                    "hit": set(),
                    "colors": {"ring": (232, 210, 255), "inner": (128, 98, 184)},
                    "vfx": vfx_scale * 1.15,
                    **anim_payload(112),
                }
            )
            blade_count = max(8, int(round(float(spell.get("ultimate_blade_burst_count", 10)))))
            blade_radius = max(10.0, 12.0 * radius_mult)
            for i in range(blade_count):
                ang = (math.tau * i) / float(blade_count)
                blade_dir = Vector2(math.cos(ang), math.sin(ang))
                spell_effects.append(
                    {
                        "kind": "projectile",
                        "spell_id": "rogue_evasion_sigil_blade",
                        "pos": Vector2(zone_pos.x, zone_pos.y - 6.0),
                        "vel": blade_dir * 560.0 * speed_mult,
                        "life": 0.66,
                        "duration": 0.66,
                        "radius": blade_radius,
                        "damage": base_damage * 0.58,
                        "hit": set(),
                        "colors": {"core": (246, 238, 255), "outline": (112, 86, 170), "trail": (186, 164, 232)},
                        "pierce_left": 0,
                        "impact_nova_radius": 0.0,
                        "impact_nova_damage_mult": 1.0,
                        "trail_timer": 0.0,
                        "vfx": vfx_scale * 1.10,
                        "homing_enabled": False,
                        "homing_target_id": None,
                        "homing_turn_rate": 0.0,
                        "homing_acquire_radius": 0.0,
                    }
                )
            spawn_particle_burst(
                spell_effects,
                Vector2(zone_pos),
                (242, 232, 255),
                (150, 126, 214),
                count=28,
                speed_min=180.0,
                speed_max=360.0,
                life_min=0.14,
                life_max=0.36,
                size_start=4.2,
                size_end=0.6,
                spread=math.tau,
                gravity=-18.0,
                drag=1.6,
                vfx_scale=vfx_scale * 1.12,
            )
        if spell_id.startswith("rogue_"):
            spawn_rogue_spell_vfx(spell_id, zone_pos)
        else:
            spawn_non_rogue_spell_vfx(spell_id, zone_pos, "ward", area_radius=float(spell.get("radius", 108.0)) * radius_mult)
    elif kind == "pillar":
        zone_pos = Vector2(player_pos.x, player_pos.y - 8) if self_cast else Vector2(resolved_target)
        size = max(32.0, float(spell.get("size", 64.0)) * radius_mult)
        impact_radius = max(18.0, float(spell.get("impact_radius", size * 0.45)) * radius_mult)
        spell_effects.append(
            {
                "kind": "pillar",
                "spell_id": spell_id,
                "pos": Vector2(zone_pos),
                "life": duration,
                "duration": duration,
                "size": size,
                "damage": base_damage,
                "impact_radius": impact_radius,
                "hit": set(),
                "colors": colors,
                "vfx": vfx_scale,
                "ambient_timer": 0.0,
                **anim_payload(96),
            }
        )
        spawn_particle_burst(
            spell_effects,
            zone_pos,
            accent_col,
            shadow_col,
            count=18,
            speed_min=40.0,
            speed_max=120.0,
            life_min=0.20,
            life_max=0.58,
            size_start=4.4,
            size_end=0.7,
            spread=math.tau,
            gravity=-36.0,
            drag=1.3,
            vfx_scale=vfx_scale,
        )
        if spell_id.startswith("rogue_"):
            spawn_rogue_spell_vfx(spell_id, zone_pos)
        else:
            spawn_non_rogue_spell_vfx(spell_id, zone_pos, "pillar", area_radius=size * 0.6)








def update_spell_effects(
    spell_effects: List[Dict[str, object]],
    dt: float,
    wolves: List[Dict[str, object]],
    passive_animals: List[Dict[str, object]],
    walk_bounds: pygame.Rect,
    obstacles: List[pygame.Rect],
    player_pos: Vector2,
    damage_numbers: Optional[List[Dict[str, object]]] = None,
    status_effects: Optional["StatusEffectSystem"] = None,
) -> Tuple[int, List[Dict[str, object]], int, List[Dict[str, object]]]:
    spawned_effects: List[Dict[str, object]] = []

    def apply_wolf_damage(
        wolf: Dict[str, object],
        damage: float,
        hit_pos: Optional[Vector2] = None,
    ) -> float:
        amount = max(0.0, float(damage))
        if amount <= 0.0:
            return 0.0
        hp_before = max(0.0, float(wolf.get("hp", 0.0)))
        if hp_before <= 0.0:
            return 0.0
        wolf["hp"] = max(0.0, hp_before - amount)
        dealt = min(hp_before, amount)
        if dealt > 0.0 and isinstance(damage_numbers, list):
            text_pos = hit_pos
            if not isinstance(text_pos, Vector2):
                wolf_pos = wolf.get("pos")
                if isinstance(wolf_pos, Vector2):
                    text_pos = Vector2(wolf_pos.x, wolf_pos.y)
            if isinstance(text_pos, Vector2):
                spawn_damage_number(damage_numbers, text_pos, dealt, kind="outgoing")
        return dealt

    def apply_animal_damage(animal: Dict[str, object], damage: float, hit_pos: Vector2) -> None:
        amount = max(0.0, float(damage))
        if amount <= 0.0:
            return
        hp_before = max(0.0, float(animal.get("hp", 0.0)))
        if hp_before <= 0.0:
            return
        animal["hp"] = max(0.0, hp_before - amount)
        dealt = min(hp_before, amount)
        if dealt > 0.0:
            if isinstance(damage_numbers, list):
                spawn_damage_number(damage_numbers, hit_pos, dealt, kind="outgoing")
            animal["last_hit_by_predator"] = False
            hp_after = float(animal.get("hp", 0.0))
            if hp_after > 0.0 and not bool(animal.get("promoted_to_enemy", False)):
                promote_passive_to_enemy(animal)

    def promote_passive_to_enemy(animal: Dict[str, object]) -> None:
        pos = animal.get("pos")
        if not isinstance(pos, Vector2):
            return
        home = Vector2(pos)
        max_hp = max(30.0, float(animal.get("max_hp", 30.0)))
        radius = max(10.0, float(animal.get("radius", 14.0)))
        speed = max(60.0, float(animal.get("speed", 70.0)) * 1.15)
        enemy = {
            "name": str(animal.get("name", "Creature")).title(),
            "pos": Vector2(pos),
            "home": home,
            "path": [Vector2(home)],
            "path_idx": 0,
            "wait": 0.25,
            "speed": speed,
            "aggro_radius": 160.0,
            "assist_radius": 140.0,
            "leash": 520.0,
            "facing": int(animal.get("facing", 1)) or 1,
            "sprite": animal.get("sprite"),
            "sprite_left": animal.get("sprite_left"),
            "max_hp": max_hp,
            "radius": radius,
            "hp": float(animal.get("hp", max_hp)),
            "chasing": True,
            "aggro_timer": 4.0,
            "engage_role": "chase",
            "attack_cd": 0.3,
            "attack_min": 4.0,
            "attack_max": 8.0,
            "attack_state": "idle",
            "attack_timer": 0.0,
            "attack_windup": 0.0,
            "attack_recover": 0.0,
            "attack_visual": 0.0,
            "queued_strike": False,
            "queued_target_type": "player",
            "queued_target_id": 0,
            "attack_target_type": "player",
            "attack_target_id": 0,
            "prey_target_id": 0,
            "hunt_drive": 0.6,
            "human_aggression": 0.95,
            "metabolism": 0.2,
            "satiety": 12.0,
            "hunt_cooldown": 0.5,
            "hunt_scan_timer": 0.5,
            "orbit_phase": 0.0,
            "xp_reward": 6,
            "level": 1,
            "tier": 1,
            "pack_id": -1,
            "pack_slot": 0,
            "nav_path": [],
            "nav_goal": Vector2(pos),
            "repath_cd": 0.0,
            "anim_frames": animal.get("anim_frames"),
            "anim_timer": float(animal.get("anim_timer", 0.0)),
        }
        wolves.append(enemy)
        animal["promoted_to_enemy"] = True
        animal["hp"] = 0.0

    def apply_spell_damage(
        wolf: Dict[str, object],
        damage: float,
        hit_pos: Optional[Vector2],
        spell_id: str,
    ) -> float:
        amount = max(0.0, float(damage))
        if amount <= 0.0:
            return 0.0
        if isinstance(status_effects, StatusEffectSystem) and spell_id:
            scorched = status_effects.consume_effect(status_effects.wolf_key(wolf), "scorched")
            if isinstance(scorched, StatusEffect):
                amount *= 1.0 + max(0.0, scorched.potency)
                if isinstance(hit_pos, Vector2):
                    spawn_particle_burst(
                        spawned_effects,
                        Vector2(hit_pos),
                        (255, 190, 118),
                        (255, 236, 190),
                        count=4,
                        speed_min=40.0,
                        speed_max=120.0,
                        life_min=0.10,
                        life_max=0.28,
                        size_start=2.6,
                        size_end=0.4,
                        spread=math.tau,
                        gravity=-16.0,
                        drag=1.4,
                        vfx_scale=0.8,
                    )
        return apply_wolf_damage(wolf, amount, hit_pos)

    def knockback_wolf(wolf: Dict[str, object], origin: Vector2, distance: float) -> None:
        pos_raw = wolf.get("pos")
        if not isinstance(pos_raw, Vector2):
            return
        direction = Vector2(pos_raw) - origin
        if direction.length_squared() <= 1e-6:
            direction = Vector2(random.choice([-1.0, 1.0]), random.uniform(-0.3, 0.3))
        if distance <= 0.5:
            return
        radius = max(8.0, float(wolf.get("radius", WOLF_COLLISION_RADIUS)))
        target = Vector2(pos_raw) + direction.normalize() * distance
        wolf["pos"] = move_with_collision(Vector2(pos_raw), target, distance, walk_bounds, obstacles, radius)
        wolf["nav_path"] = []
        wolf["moving"] = False

    def lock_frozen_wolf(wolf: Dict[str, object], freeze_duration: float, color: Tuple[int, int, int]) -> None:
        freeze_time = max(0.08, float(freeze_duration))
        if isinstance(status_effects, StatusEffectSystem):
            status_effects.add_effect(
                status_effects.wolf_key(wolf),
                StatusEffect("freeze", freeze_time, potency=1.0, color=color),
            )
        pos_raw = wolf.get("pos")
        if isinstance(pos_raw, Vector2):
            wolf["freeze_anchor"] = Vector2(pos_raw)
        wolf["status_move_mult"] = 0.0
        wolf["status_disabled"] = True
        wolf["queued_strike"] = False
        wolf["attack_state"] = "idle"
        wolf["attack_timer"] = 0.0
        wolf["attack_visual"] = 0.0
        wolf["nav_path"] = []
        wolf["moving"] = False

    def emit_firebolt_trail(effect: Dict[str, object], pos: Vector2, vel: Vector2) -> None:
        if vel.length_squared() <= 1e-6:
            return
        vfx_scale = clamp(float(effect.get("vfx", 1.0)), 1.0, 2.8)
        dir_vec = vel.normalize()
        back_dir = -dir_vec
        perp_dir = Vector2(-dir_vec.y, dir_vec.x)
        trail_timer = float(effect.get("trail_timer", 0.0)) + dt
        smoke_timer = float(effect.get("smoke_timer", 0.0)) + dt
        spark_timer = float(effect.get("spark_timer", 0.0)) + dt

        # Main flame trail — bright core fire
        if trail_timer >= 0.014:
            trail_timer = 0.0
            spawn_particle_burst(
                spawned_effects,
                Vector2(pos) - dir_vec * 4.0,
                (255, 230, 160), (255, 140, 50),
                count=3, speed_min=80.0, speed_max=200.0,
                life_min=0.10, life_max=0.28,
                size_start=3.8, size_end=0.3,
                spread=0.55, direction=back_dir,
                gravity=20.0, drag=2.0,
                vfx_scale=vfx_scale,
            )
            # Flanking ember wisps
            side = 1.0 if random.random() > 0.5 else -1.0
            spawn_particle_burst(
                spawned_effects,
                Vector2(pos) + perp_dir * side * 3.0,
                (255, 200, 100), (255, 120, 40),
                count=1, speed_min=40.0, speed_max=100.0,
                life_min=0.08, life_max=0.18,
                size_start=2.0, size_end=0.2,
                spread=0.8, direction=back_dir + perp_dir * side * 0.3,
                gravity=30.0, drag=2.5,
                vfx_scale=vfx_scale,
            )

        # Dark smoke plume
        if smoke_timer >= 0.045:
            smoke_timer = 0.0
            spawn_particle_burst(
                spawned_effects,
                Vector2(pos) - dir_vec * 8.0,
                (110, 85, 70), (65, 50, 42),
                count=1, speed_min=14.0, speed_max=48.0,
                life_min=0.28, life_max=0.70,
                size_start=5.5, size_end=1.5,
                spread=0.80, direction=back_dir,
                gravity=-18.0, drag=1.6,
                vfx_scale=vfx_scale,
            )

        # Hot ember sparks — bright orange points
        if spark_timer >= 0.022:
            spark_timer = 0.0
            spawn_particle_burst(
                spawned_effects, Vector2(pos),
                (255, 248, 200), (255, 180, 80),
                count=1, speed_min=200.0, speed_max=380.0,
                life_min=0.06, life_max=0.18,
                size_start=1.8, size_end=0.2,
                spread=0.40, direction=dir_vec,
                gravity=100.0, drag=3.0,
                vfx_scale=vfx_scale,
            )

        effect["trail_timer"] = trail_timer
        effect["smoke_timer"] = smoke_timer
        effect["spark_timer"] = spark_timer

    def emit_frostbolt_trail(effect: Dict[str, object], pos: Vector2, vel: Vector2) -> None:
        if vel.length_squared() <= 1e-6:
            return
        vfx_scale = clamp(float(effect.get("vfx", 1.0)), 1.0, 2.8)
        dir_vec = vel.normalize()
        back_dir = -dir_vec
        perp_dir = Vector2(-dir_vec.y, dir_vec.x)
        trail_timer = float(effect.get("frost_trail_timer", 0.0)) + dt
        mist_timer = float(effect.get("frost_mist_timer", 0.0)) + dt
        shard_timer = float(effect.get("frost_shard_timer", 0.0)) + dt

        # Crystalline ice trail — bright, sharp
        if trail_timer >= 0.016:
            trail_timer = 0.0
            spawn_particle_burst(
                spawned_effects,
                Vector2(pos) - dir_vec * 3.0,
                (230, 248, 255), (160, 215, 255),
                count=3, speed_min=70.0, speed_max=170.0,
                life_min=0.10, life_max=0.30,
                size_start=3.2, size_end=0.3,
                spread=0.50, direction=back_dir,
                gravity=-10.0, drag=1.8,
                vfx_scale=vfx_scale,
            )
            # Flanking frost wisps
            side = 1.0 if random.random() > 0.5 else -1.0
            spawn_particle_burst(
                spawned_effects,
                Vector2(pos) + perp_dir * side * 4.0,
                (190, 225, 250), (130, 180, 220),
                count=1, speed_min=30.0, speed_max=80.0,
                life_min=0.12, life_max=0.28,
                size_start=2.2, size_end=0.3,
                spread=0.7, direction=back_dir + perp_dir * side * 0.4,
                gravity=-14.0, drag=2.2,
                vfx_scale=vfx_scale,
            )

        # Cold mist fog — slow, lingering
        if mist_timer >= 0.050:
            mist_timer = 0.0
            spawn_particle_burst(
                spawned_effects,
                Vector2(pos) - dir_vec * 6.0,
                (180, 215, 240), (120, 160, 200),
                count=1, speed_min=10.0, speed_max=36.0,
                life_min=0.30, life_max=0.80,
                size_start=5.5, size_end=1.5,
                spread=0.90, direction=back_dir,
                gravity=-28.0, drag=1.4,
                vfx_scale=vfx_scale,
            )

        # Ice crystal shards — sharp bright forward spray
        if shard_timer >= 0.028:
            shard_timer = 0.0
            spawn_particle_burst(
                spawned_effects, Vector2(pos),
                (248, 254, 255), (190, 230, 255),
                count=1, speed_min=180.0, speed_max=340.0,
                life_min=0.05, life_max=0.16,
                size_start=1.6, size_end=0.2,
                spread=0.35, direction=dir_vec,
                gravity=28.0, drag=2.8,
                vfx_scale=vfx_scale,
            )

        effect["frost_trail_timer"] = trail_timer
        effect["frost_mist_timer"] = mist_timer
        effect["frost_shard_timer"] = shard_timer

    def spawn_firebolt_impact(pos: Vector2, vel: Optional[Vector2], intensity: float = 1.0) -> None:
        scale = clamp(float(intensity), 0.8, 2.6)
        hit_dir = Vector2(1.0, 0.0)
        if isinstance(vel, Vector2) and vel.length_squared() > 1e-6:
            hit_dir = vel.normalize()
        # Main explosion — bright white-hot core burst
        spawn_particle_burst(
            spawned_effects, Vector2(pos),
            (255, 250, 220), (255, 200, 100),
            count=20, speed_min=180.0, speed_max=420.0,
            life_min=0.08, life_max=0.26,
            size_start=6.0, size_end=0.4,
            spread=math.tau, gravity=30.0, drag=1.6,
            vfx_scale=scale,
        )
        # Directed flame spray in hit direction
        spawn_particle_burst(
            spawned_effects, Vector2(pos),
            (255, 180, 80), (200, 70, 20),
            count=14, speed_min=120.0, speed_max=300.0,
            life_min=0.12, life_max=0.36,
            size_start=5.0, size_end=0.6,
            spread=1.0, direction=hit_dir,
            gravity=50.0, drag=1.8,
            vfx_scale=scale,
        )
        # Ember sparks — small bright points that arc high
        spawn_particle_burst(
            spawned_effects, Vector2(pos),
            (255, 220, 140), (255, 160, 60),
            count=10, speed_min=200.0, speed_max=500.0,
            life_min=0.20, life_max=0.50,
            size_start=2.4, size_end=0.3,
            spread=math.tau, gravity=120.0, drag=2.2,
            vfx_scale=scale,
        )
        # Smoke plume — dark, rising slowly
        spawn_particle_burst(
            spawned_effects, Vector2(pos),
            (120, 90, 70), (60, 50, 42),
            count=8, speed_min=20.0, speed_max=80.0,
            life_min=0.30, life_max=0.80,
            size_start=7.0, size_end=2.0,
            spread=math.tau, gravity=-30.0, drag=1.4,
            vfx_scale=scale,
        )
        # Ground scorch ring — slow expanding embers
        spawn_particle_burst(
            spawned_effects, Vector2(pos.x, pos.y + 4),
            (180, 100, 40), (120, 60, 20),
            count=6, speed_min=60.0, speed_max=140.0,
            life_min=0.16, life_max=0.40,
            size_start=3.0, size_end=0.8,
            spread=math.tau, gravity=8.0, drag=2.5,
            vfx_scale=scale,
        )

    def spawn_frostbolt_impact(pos: Vector2, vel: Optional[Vector2], intensity: float = 1.0) -> None:
        scale = clamp(float(intensity), 0.8, 2.6)
        hit_dir = Vector2(1.0, 0.0)
        if isinstance(vel, Vector2) and vel.length_squared() > 1e-6:
            hit_dir = vel.normalize()
        # Ice shatter burst — bright crystalline fragments
        spawn_particle_burst(
            spawned_effects, Vector2(pos),
            (240, 252, 255), (180, 230, 255),
            count=22, speed_min=160.0, speed_max=380.0,
            life_min=0.08, life_max=0.28,
            size_start=5.4, size_end=0.4,
            spread=math.tau, gravity=16.0, drag=1.6,
            vfx_scale=scale,
        )
        # Directed ice spray
        spawn_particle_burst(
            spawned_effects, Vector2(pos),
            (200, 235, 255), (120, 180, 240),
            count=14, speed_min=100.0, speed_max=280.0,
            life_min=0.10, life_max=0.32,
            size_start=4.2, size_end=0.5,
            spread=0.90, direction=hit_dir,
            gravity=22.0, drag=1.9,
            vfx_scale=scale,
        )
        # Frost mist cloud — slow lingering cold fog
        spawn_particle_burst(
            spawned_effects, Vector2(pos),
            (170, 210, 240), (100, 150, 190),
            count=10, speed_min=12.0, speed_max=60.0,
            life_min=0.35, life_max=0.90,
            size_start=7.0, size_end=2.0,
            spread=math.tau, gravity=-18.0, drag=1.3,
            vfx_scale=scale,
        )
        # Ice crystal shards — sharp bright points flying up
        spawn_particle_burst(
            spawned_effects, Vector2(pos),
            (230, 248, 255), (200, 230, 255),
            count=8, speed_min=180.0, speed_max=400.0,
            life_min=0.14, life_max=0.38,
            size_start=2.0, size_end=0.3,
            spread=math.tau, gravity=80.0, drag=2.4,
            vfx_scale=scale,
        )
        # Ground frost ring — spreading ice at feet
        spawn_particle_burst(
            spawned_effects, Vector2(pos.x, pos.y + 4),
            (160, 200, 230), (110, 160, 200),
            count=6, speed_min=50.0, speed_max=120.0,
            life_min=0.20, life_max=0.50,
            size_start=3.4, size_end=1.0,
            spread=math.tau, gravity=4.0, drag=2.8,
            vfx_scale=scale,
        )

    for effect in spell_effects:
        effect["life"] = float(effect.get("life", 0.0)) - dt

        kind = str(effect.get("kind", ""))
        if kind == "projectile":
            pos = effect.get("pos")
            vel = effect.get("vel")
            if isinstance(pos, Vector2) and isinstance(vel, Vector2):
                spell_id = str(effect.get("spell_id", ""))
                is_firebolt = spell_id in ("mage_fire_ball", "mage_searing_bolt")
                is_frostbolt = spell_id in ("mage_wind", "mage_frostbolt")
                is_searing_bolt = spell_id == "mage_searing_bolt"
                target_pos = None
                if bool(effect.get("homing_enabled", False)):
                    target_id = effect.get("homing_target_id")
                    if isinstance(target_id, int):
                        for wolf in wolves:
                            if id(wolf) != target_id:
                                continue
                            if float(wolf.get("hp", 0.0)) <= 0.0:
                                break
                            wpos = wolf.get("pos")
                            if isinstance(wpos, Vector2):
                                target_pos = Vector2(wpos.x, wpos.y - 10.0)
                            break
                    if target_pos is None:
                        acquire_radius = max(80.0, float(effect.get("homing_acquire_radius", 520.0)))
                        nearest_dist = 1e12
                        nearest_id: Optional[int] = None
                        nearest_pos: Optional[Vector2] = None
                        for wolf in wolves:
                            if float(wolf.get("hp", 0.0)) <= 0.0:
                                continue
                            wpos = wolf.get("pos")
                            if not isinstance(wpos, Vector2):
                                continue
                            dist = wpos.distance_to(pos)
                            if dist > acquire_radius or dist >= nearest_dist:
                                continue
                            nearest_dist = dist
                            nearest_id = id(wolf)
                            nearest_pos = Vector2(wpos.x, wpos.y - 10.0)
                        if isinstance(nearest_pos, Vector2):
                            target_pos = nearest_pos
                            effect["homing_target_id"] = nearest_id
                        else:
                            effect["homing_target_id"] = None
                    if isinstance(target_pos, Vector2):
                        to_target = target_pos - pos
                        if to_target.length_squared() > 1e-4:
                            speed = max(120.0, vel.length())
                            desired_dir = to_target.normalize()
                            current_dir = vel.normalize() if vel.length_squared() > 1e-5 else desired_dir
                            turn_strength = clamp(float(effect.get("homing_turn_rate", 16.0)) * dt, 0.0, 1.0)
                            steer_dir = (current_dir * (1.0 - turn_strength)) + (desired_dir * turn_strength)
                            if steer_dir.length_squared() <= 1e-6:
                                steer_dir = desired_dir
                            vel = steer_dir.normalize() * speed
                            effect["vel"] = vel
                pos += vel * dt
                effect["pos"] = pos
                if is_firebolt:
                    emit_firebolt_trail(effect, pos, vel)
                elif is_frostbolt:
                    emit_frostbolt_trail(effect, pos, vel)
                if not is_walkable(pos, walk_bounds, obstacles):
                    if is_firebolt:
                        spawn_firebolt_impact(Vector2(pos), vel, intensity=1.08)
                    elif is_frostbolt:
                        spawn_frostbolt_impact(Vector2(pos), vel, intensity=1.02)
                    impact_radius = float(effect.get("impact_nova_radius", 0.0))
                    if impact_radius > 0.0:
                        impact_damage = float(effect.get("damage", 0.0)) * max(0.1, float(effect.get("impact_nova_damage_mult", 1.0)))
                        spawned_effects.append(
                            {
                                "kind": "nova",
                                "spell_id": f"{effect.get('spell_id', '')}_impact",
                                "pos": Vector2(pos),
                                "life": 0.44,
                                "duration": 0.44,
                                "max_radius": impact_radius,
                                "damage": impact_damage,
                                "hit": set(),
                                "colors": effect.get("colors", {}),
                                "anim_set": effect.get("anim_set", ""),
                                "anim_size": int(max(40, float(effect.get("anim_size", 72)) + 14)),
                            }
                        )
                    effect["life"] = 0.0
                    continue
                hit_ids = effect.get("hit")
                if not isinstance(hit_ids, set):
                    hit_ids = set()
                    effect["hit"] = hit_ids
                for wolf in wolves:
                    if float(wolf.get("hp", 0.0)) <= 0.0:
                        continue
                    wolf_id = id(wolf)
                    if wolf_id in hit_ids:
                        continue
                    wpos = wolf.get("pos")
                    if not isinstance(wpos, Vector2):
                        continue
                    radius_sum = float(effect.get("radius", 18.0)) + 20.0
                    if wpos.distance_squared_to(pos) <= radius_sum * radius_sum:
                        dealt = apply_spell_damage(wolf, float(effect.get("damage", 32.0)), Vector2(wpos.x, wpos.y), spell_id)
                        hit_ids.add(wolf_id)
                        spawn_blood_splatter(spawned_effects, Vector2(wpos), intensity=1.25)
                        if dealt > 0.0 and is_searing_bolt and isinstance(status_effects, StatusEffectSystem):
                            scorch_bonus = max(0.0, float(effect.get("scorch_bonus", 0.0)))
                            scorch_duration = max(0.0, float(effect.get("scorch_duration", 0.0)))
                            if scorch_bonus > 0.0 and scorch_duration > 0.0:
                                status_effects.add_effect(
                                    status_effects.wolf_key(wolf),
                                    StatusEffect("scorched", scorch_duration, potency=scorch_bonus, color=(255, 132, 72)),
                                )
                            # Apply visible burn DoT on top of scorch
                            _burn_dmg = max(2.0, float(effect.get("damage", 30.0)) * 0.08)
                            status_effects.add_effect(
                                status_effects.wolf_key(wolf),
                                StatusEffect("burn", 3.5, potency=_burn_dmg, tick_interval=0.55, color=(255, 140, 50)),
                            )
                        if is_firebolt:
                            spawn_firebolt_impact(Vector2(wpos.x, wpos.y - 4.0), vel, intensity=1.0)
                        elif is_frostbolt:
                            spawn_frostbolt_impact(Vector2(wpos.x, wpos.y - 4.0), vel, intensity=0.96)
                        impact_radius = float(effect.get("impact_nova_radius", 0.0))
                        if impact_radius > 0.0:
                            impact_damage = float(effect.get("damage", 0.0)) * max(0.1, float(effect.get("impact_nova_damage_mult", 1.0)))
                            spawned_effects.append(
                                {
                                    "kind": "nova",
                                    "spell_id": f"{effect.get('spell_id', '')}_impact",
                                    "pos": Vector2(pos),
                                    "life": 0.44,
                                    "duration": 0.44,
                                    "max_radius": impact_radius,
                                    "damage": impact_damage,
                                    "hit": set(),
                                    "colors": effect.get("colors", {}),
                                    "anim_set": effect.get("anim_set", ""),
                                    "anim_size": int(max(40, float(effect.get("anim_size", 72)) + 14)),
                                }
                            )
                        pierce_left = int(effect.get("pierce_left", 0))
                        if pierce_left > 0:
                            effect["pierce_left"] = pierce_left - 1
                        else:
                            effect["life"] = 0.0
                            break

                hit_passives = effect.get("hit_passives")
                if not isinstance(hit_passives, set):
                    hit_passives = set()
                    effect["hit_passives"] = hit_passives
                for animal in passive_animals:
                    if float(animal.get("hp", 0.0)) <= 0.0:
                        continue
                    animal_id = id(animal)
                    if animal_id in hit_passives:
                        continue
                    apos = animal.get("pos")
                    if not isinstance(apos, Vector2):
                        continue
                    radius_sum = float(effect.get("radius", 18.0)) + float(animal.get("radius", 12.0))
                    if apos.distance_squared_to(pos) <= radius_sum * radius_sum:
                        apply_animal_damage(animal, float(effect.get("damage", 32.0)), Vector2(apos.x, apos.y))
                        hit_passives.add(animal_id)
                        if is_firebolt:
                            spawn_firebolt_impact(Vector2(apos.x, apos.y - 3.0), vel, intensity=0.9)
                        elif is_frostbolt:
                            spawn_frostbolt_impact(Vector2(apos.x, apos.y - 3.0), vel, intensity=0.86)
                        # Projectiles disappear after hitting a passive animal
                        pierce_left = int(effect.get("pierce_left", 0))
                        if pierce_left > 0:
                            effect["pierce_left"] = pierce_left - 1
                        else:
                            effect["life"] = 0.0
                            break




        elif kind == "nova":
            pos = effect.get("pos")
            if isinstance(pos, Vector2):
                spell_id = str(effect.get("spell_id", ""))
                is_freeze_nova = spell_id == "mage_water"
                is_chill_nova = spell_id == "mage_frost_nova"
                is_frost_nova = is_freeze_nova or is_chill_nova
                duration = max(0.01, float(effect.get("duration", 0.72)))
                progress = 1.0 - clamp(float(effect.get("life", 0.0)) / duration, 0.0, 1.0)
                if is_frost_nova:
                    radius = float(effect.get("max_radius", 180.0))
                else:
                    radius = 26.0 + float(effect.get("max_radius", 180.0)) * progress
                freeze_duration = max(0.08, float(effect.get("freeze_duration", 0.0)))
                slow_duration = max(0.0, float(effect.get("slow_duration", 0.0)))
                slow_potency = max(0.0, float(effect.get("slow_potency", 0.0)))
                knockback_force = max(0.0, float(effect.get("knockback", 0.0)))
                knockback_small_only = bool(effect.get("knockback_small_only", False))
                hit_ids = effect.get("hit")
                if not isinstance(hit_ids, set):
                    hit_ids = set()
                    effect["hit"] = hit_ids
                for wolf in wolves:
                    if float(wolf.get("hp", 0.0)) <= 0.0:
                        continue
                    wolf_id = id(wolf)
                    if wolf_id in hit_ids:
                        continue
                    wpos = wolf.get("pos")
                    if not isinstance(wpos, Vector2):
                        continue
                    if wpos.distance_squared_to(pos) <= radius * radius:
                        dealt = apply_spell_damage(wolf, float(effect.get("damage", 28.0)), Vector2(wpos.x, wpos.y), spell_id)
                        if dealt <= 0.0:
                            hit_ids.add(wolf_id)
                            continue
                        hit_ids.add(wolf_id)
                        if is_freeze_nova:
                            lock_frozen_wolf(wolf, freeze_duration, (186, 226, 255))
                            spawn_frostbolt_impact(Vector2(wpos.x, wpos.y - 2.0), None, intensity=1.0)
                        elif is_chill_nova:
                            if isinstance(status_effects, StatusEffectSystem) and slow_duration > 0.0 and slow_potency > 0.0:
                                status_effects.add_effect(
                                    status_effects.wolf_key(wolf),
                                    StatusEffect("slow", slow_duration, potency=slow_potency, color=(180, 220, 255)),
                                )
                            if knockback_force > 0.0:
                                wolf_radius = float(wolf.get("radius", WOLF_COLLISION_RADIUS))
                                is_small = wolf_radius <= WOLF_COLLISION_RADIUS + 1.5
                                if (not knockback_small_only) or is_small:
                                    knockback_wolf(wolf, Vector2(pos), knockback_force)
                            spawn_frostbolt_impact(Vector2(wpos.x, wpos.y - 2.0), None, intensity=0.96)
                        elif random.random() < 0.85:
                            spawn_blood_splatter(spawned_effects, Vector2(wpos), intensity=1.0)
                hit_passives = effect.get("hit_passives")
                if not isinstance(hit_passives, set):
                    hit_passives = set()
                    effect["hit_passives"] = hit_passives
                for animal in passive_animals:
                    if float(animal.get("hp", 0.0)) <= 0.0 or id(animal) in hit_passives:
                        continue
                    apos = animal.get("pos")
                    if not isinstance(apos, Vector2):
                        continue
                    if apos.distance_squared_to(pos) <= radius * radius:
                        apply_animal_damage(animal, float(effect.get("damage", 28.0)), Vector2(apos.x, apos.y))
                        hit_passives.add(id(animal))
                        if is_frost_nova:
                            spawn_frostbolt_impact(Vector2(apos.x, apos.y - 2.0), None, intensity=0.84)
                        elif random.random() < 0.6:
                            spawn_blood_splatter(spawned_effects, Vector2(apos), intensity=1.0)
                if is_frost_nova:
                    shimmer_timer = float(effect.get("frost_shimmer_timer", 0.0)) + dt
                    mist_timer = float(effect.get("frost_mist_timer", 0.0)) + dt
                    seed = float(effect.get("frost_seed", 0.0))
                    ring_radius = max(18.0, radius * (0.18 + 0.82 * progress))
                    vfx_scale = clamp(float(effect.get("vfx", 1.0)), 0.8, 3.0)
                    if shimmer_timer >= 0.030:
                        shimmer_timer = 0.0
                        spin = pygame.time.get_ticks() * 0.0017 + seed
                        for _ in range(2):
                            ang = spin + random.uniform(-0.60, 0.60)
                            radial = Vector2(math.cos(ang), math.sin(ang))
                            tangential = Vector2(-radial.y, radial.x) * random.uniform(-1.0, 1.0)
                            emit_pos = Vector2(pos) + radial * ring_radius * random.uniform(0.84, 1.06)
                            launch = (radial * 0.82 + tangential * 0.18).normalize()
                            spawn_particle_burst(
                                spawned_effects,
                                emit_pos,
                                (236, 252, 255),
                                (178, 226, 255),
                                count=1,
                                speed_min=90.0,
                                speed_max=220.0,
                                life_min=0.08,
                                life_max=0.24,
                                size_start=2.4,
                                size_end=0.3,
                                spread=0.24,
                                direction=launch,
                                gravity=8.0,
                                drag=2.0,
                                vfx_scale=vfx_scale,
                            )
                    if mist_timer >= 0.072:
                        mist_timer = 0.0
                        for _ in range(2):
                            ang = random.random() * math.tau
                            d = Vector2(math.cos(ang), math.sin(ang))
                            emit_pos = Vector2(pos) + d * ring_radius * random.uniform(0.32, 0.70)
                            spawn_particle_burst(
                                spawned_effects,
                                emit_pos,
                                (194, 224, 246),
                                (116, 154, 196),
                                count=1,
                                speed_min=8.0,
                                speed_max=28.0,
                                life_min=0.20,
                                life_max=0.56,
                                size_start=4.2,
                                size_end=0.9,
                                spread=math.tau,
                                gravity=-22.0,
                                drag=1.3,
                                vfx_scale=vfx_scale,
                            )
                    effect["frost_shimmer_timer"] = shimmer_timer
                    effect["frost_mist_timer"] = mist_timer

        elif kind == "frost_wave":
            start = effect.get("start")
            end = effect.get("end")
            if isinstance(start, Vector2) and isinstance(end, Vector2):
                path = end - start
                path_len = path.length()
                if path_len > 1e-5:
                    dir_vec = path / path_len
                    normal = Vector2(-dir_vec.y, dir_vec.x)
                    duration = max(0.01, float(effect.get("duration", 0.54)))
                    progress = clamp(1.0 - float(effect.get("life", 0.0)) / duration, 0.0, 1.0)
                    prev_progress = clamp(float(effect.get("prev_progress", 0.0)), 0.0, 1.0)
                    if progress < prev_progress:
                        prev_progress = progress
                    head = start + dir_vec * (path_len * progress)
                    tail = start + dir_vec * (path_len * max(0.0, progress - 0.28))
                    effect["pos"] = Vector2(head)
                    effect["head"] = Vector2(head)
                    effect["tail"] = Vector2(tail)
                    effect["prev_progress"] = progress

                    wave_width = max(22.0, float(effect.get("width", 80.0)))
                    wolf_hit_radius = wave_width * 0.48 + 14.0
                    animal_hit_radius = wave_width * 0.42 + 9.0
                    freeze_duration = max(0.08, float(effect.get("freeze_duration", 1.0)))
                    hit_ids = effect.get("hit")
                    if not isinstance(hit_ids, set):
                        hit_ids = set()
                        effect["hit"] = hit_ids
                    for wolf in wolves:
                        if float(wolf.get("hp", 0.0)) <= 0.0:
                            continue
                        wolf_id = id(wolf)
                        if wolf_id in hit_ids:
                            continue
                        wpos = wolf.get("pos")
                        if not isinstance(wpos, Vector2):
                            continue
                        if not circle_hits_segment(
                            wpos,
                            wolf_hit_radius + float(wolf.get("radius", WOLF_COLLISION_RADIUS)) * 0.35,
                            start,
                            head,
                        ):
                            continue
                        hit_pos = Vector2(wpos.x, wpos.y)
                        dealt = apply_spell_damage(wolf, float(effect.get("damage", 24.0)), hit_pos, str(effect.get("spell_id", "")))
                        if dealt <= 0.0:
                            continue
                        hit_ids.add(wolf_id)
                        lock_frozen_wolf(wolf, freeze_duration, (188, 228, 255))
                        spawn_frostbolt_impact(hit_pos + Vector2(0.0, -4.0), dir_vec * 120.0, intensity=1.12)
                        spawn_particle_burst(
                            spawned_effects,
                            hit_pos,
                            (226, 246, 255),
                            (154, 206, 250),
                            count=8,
                            speed_min=120.0,
                            speed_max=290.0,
                            life_min=0.10,
                            life_max=0.28,
                            size_start=3.0,
                            size_end=0.5,
                            spread=0.70,
                            direction=dir_vec,
                            gravity=14.0,
                            drag=2.0,
                            vfx_scale=float(effect.get("vfx", 1.0)),
                        )

                    hit_passives = effect.get("hit_passives")
                    if not isinstance(hit_passives, set):
                        hit_passives = set()
                        effect["hit_passives"] = hit_passives
                    for animal in passive_animals:
                        if float(animal.get("hp", 0.0)) <= 0.0:
                            continue
                        animal_id = id(animal)
                        if animal_id in hit_passives:
                            continue
                        apos = animal.get("pos")
                        if not isinstance(apos, Vector2):
                            continue
                        if not circle_hits_segment(
                            apos,
                            animal_hit_radius + float(animal.get("radius", 12.0)) * 0.35,
                            start,
                            head,
                        ):
                            continue
                        hit_passives.add(animal_id)
                        apply_animal_damage(animal, float(effect.get("damage", 24.0)), Vector2(apos.x, apos.y))
                        spawn_frostbolt_impact(Vector2(apos.x, apos.y - 2.0), dir_vec * 100.0, intensity=0.9)

                    ambient = float(effect.get("ambient_timer", 0.0)) + dt
                    mist = float(effect.get("mist_timer", 0.0)) + dt
                    span = head - tail
                    span_len_sq = span.length_squared()
                    vfx_scale = clamp(float(effect.get("vfx", 1.0)), 0.7, 3.2)
                    if ambient >= 0.026 and progress > 0.02:
                        ambient = 0.0
                        if span_len_sq <= 1e-6:
                            emit_pos = Vector2(head)
                        else:
                            emit_pos = tail + span * random.random()
                        emit_pos += normal * random.uniform(-wave_width * 0.36, wave_width * 0.36)
                        spawn_particle_burst(
                            spawned_effects,
                            emit_pos,
                            (226, 246, 255),
                            (158, 208, 252),
                            count=2,
                            speed_min=44.0,
                            speed_max=128.0,
                            life_min=0.10,
                            life_max=0.26,
                            size_start=2.6,
                            size_end=0.4,
                            spread=0.74,
                            direction=dir_vec,
                            gravity=10.0,
                            drag=2.1,
                            vfx_scale=vfx_scale,
                        )
                    if mist >= 0.075 and progress > 0.08:
                        mist = 0.0
                        if span_len_sq <= 1e-6:
                            mist_pos = Vector2(head)
                        else:
                            mist_pos = tail + span * random.random()
                        mist_pos += normal * random.uniform(-wave_width * 0.30, wave_width * 0.30)
                        spawn_particle_burst(
                            spawned_effects,
                            mist_pos,
                            (194, 224, 246),
                            (118, 156, 194),
                            count=1,
                            speed_min=10.0,
                            speed_max=38.0,
                            life_min=0.24,
                            life_max=0.62,
                            size_start=4.8,
                            size_end=1.0,
                            spread=math.tau,
                            gravity=-28.0,
                            drag=1.4,
                            vfx_scale=vfx_scale,
                        )
                    effect["ambient_timer"] = ambient
                    effect["mist_timer"] = mist

        elif kind == "orb":
            pos = effect.get("pos")
            if isinstance(pos, Vector2):
                spell_id = str(effect.get("spell_id", ""))
                ambient = float(effect.get("ambient_timer", 0.0)) + dt
                if spell_id == "rogue_venom_trap" and ambient >= 0.09:
                    ambient = 0.0
                    ring_color = effect.get("colors", {}).get("ring", (124, 206, 124))
                    aura_color = effect.get("colors", {}).get("aura", (78, 146, 86))
                    spawn_particle_burst(
                        spawned_effects,
                        Vector2(pos),
                        aura_color,
                        ring_color,
                        count=3,
                        speed_min=28.0,
                        speed_max=84.0,
                        life_min=0.16,
                        life_max=0.46,
                        size_start=3.2,
                        size_end=0.6,
                        spread=math.tau,
                        gravity=-12.0,
                        drag=1.2,
                        vfx_scale=float(effect.get("vfx", 1.0)),
                    )
                elif not spell_id.startswith("rogue_"):
                    cls = spell_class_id(spell_id)
                    theme = CLASS_SPELL_VFX_THEMES.get(cls, {})
                    c0 = theme.get("core", (144, 176, 210))
                    c1 = theme.get("accent", (218, 236, 250))
                    c2 = theme.get("shadow", (82, 94, 126))
                    interval = {
                        "mage": 0.08,
                        "ranger": 0.11,
                        "necromancer": 0.09,
                        "warrior": 0.12,
                        "paladin": 0.10,
                    }.get(cls, 0.11)
                    if ambient >= interval:
                        ambient = 0.0
                        orb_radius = float(effect.get("radius", 112.0))
                        ang = pygame.time.get_ticks() * 0.0047
                        orbit = Vector2(math.cos(ang), math.sin(ang * 1.14))
                        emit_pos = Vector2(pos) + orbit * max(16.0, orb_radius * 0.35)
                        spawn_particle_burst(
                            spawned_effects,
                            emit_pos,
                            c0,
                            c1,
                            count=3,
                            speed_min=26.0,
                            speed_max=96.0,
                            life_min=0.14,
                            life_max=0.42,
                            size_start=3.0,
                            size_end=0.5,
                            spread=math.tau,
                            gravity=-14.0,
                            drag=1.3,
                            vfx_scale=float(effect.get("vfx", 1.0)),
                        )
                        spawn_particle_burst(
                            spawned_effects,
                            Vector2(pos),
                            c1,
                            c2,
                            count=2,
                            speed_min=44.0,
                            speed_max=130.0,
                            life_min=0.10,
                            life_max=0.30,
                            size_start=2.2,
                            size_end=0.4,
                            spread=math.tau,
                            drag=1.4,
                            vfx_scale=float(effect.get("vfx", 1.0)),
                        )
                effect["ambient_timer"] = ambient
                pulse = float(effect.get("pulse", 0.0)) + dt
                effect["pulse"] = pulse
                if pulse >= float(effect.get("pulse_interval", 0.34)):
                    effect["pulse"] = 0.0
                    for wolf in wolves:
                        if float(wolf.get("hp", 0.0)) <= 0.0:
                            continue
                        wpos = wolf.get("pos")
                        if not isinstance(wpos, Vector2):
                            continue
                        radius = float(effect.get("radius", 112.0))
                        if wpos.distance_squared_to(pos) <= radius * radius:
                            apply_spell_damage(wolf, float(effect.get("damage", 16.0)), Vector2(wpos.x, wpos.y), spell_id)
                            if random.random() < 0.35:
                                spawn_blood_splatter(spawned_effects, Vector2(wpos), intensity=0.75)

        elif kind == "ward":
            pos = effect.get("pos")
            if isinstance(pos, Vector2):
                spell_id = str(effect.get("spell_id", ""))
                ambient = float(effect.get("ambient_timer", 0.0)) + dt
                if spell_id == "rogue_evasion_sigil" and ambient >= 0.07:
                    ambient = 0.0
                    ring_color = effect.get("colors", {}).get("ring", (210, 198, 236))
                    inner_color = effect.get("colors", {}).get("inner", (84, 70, 126))
                    spawn_particle_burst(
                        spawned_effects,
                        Vector2(pos),
                        ring_color,
                        inner_color,
                        count=6,
                        speed_min=40.0,
                        speed_max=128.0,
                        life_min=0.22,
                        life_max=0.56,
                        size_start=3.8,
                        size_end=0.6,
                        spread=math.tau,
                        gravity=-26.0,
                        drag=1.2,
                        vfx_scale=float(effect.get("vfx", 1.0)),
                    )
                    spawn_particle_burst(
                        spawned_effects,
                        Vector2(pos),
                        (238, 228, 255),
                        (154, 134, 206),
                        count=4,
                        speed_min=110.0,
                        speed_max=210.0,
                        life_min=0.10,
                        life_max=0.30,
                        size_start=2.8,
                        size_end=0.5,
                        spread=math.tau,
                        gravity=-10.0,
                        drag=1.4,
                        vfx_scale=float(effect.get("vfx", 1.0)),
                    )
                elif not spell_id.startswith("rogue_"):
                    cls = spell_class_id(spell_id)
                    theme = CLASS_SPELL_VFX_THEMES.get(cls, {})
                    c0 = theme.get("core", (170, 170, 178))
                    c1 = theme.get("accent", (228, 228, 234))
                    c2 = theme.get("shadow", (92, 92, 108))
                    interval = {
                        "mage": 0.09,
                        "ranger": 0.12,
                        "necromancer": 0.10,
                        "warrior": 0.13,
                        "paladin": 0.09,
                    }.get(cls, 0.11)
                    if ambient >= interval:
                        ambient = 0.0
                        ward_radius = max(18.0, float(effect.get("radius", 108.0)))
                        now = pygame.time.get_ticks() * 0.0018
                        for i in range(2):
                            ang = now + i * math.pi
                            emit_pos = Vector2(pos.x + math.cos(ang) * ward_radius * 0.65, pos.y + math.sin(ang) * ward_radius * 0.65)
                            spawn_particle_burst(
                                spawned_effects,
                                emit_pos,
                                c1,
                                c0,
                                count=2,
                                speed_min=38.0,
                                speed_max=110.0,
                                life_min=0.16,
                                life_max=0.48,
                                size_start=2.8,
                                size_end=0.5,
                                spread=math.tau,
                                gravity=-20.0,
                                drag=1.2,
                                vfx_scale=float(effect.get("vfx", 1.0)),
                            )
                        spawn_particle_burst(
                            spawned_effects,
                            Vector2(pos),
                            c0,
                            c2,
                            count=3,
                            speed_min=52.0,
                            speed_max=150.0,
                            life_min=0.10,
                            life_max=0.32,
                            size_start=2.6,
                            size_end=0.4,
                            spread=math.tau,
                            drag=1.5,
                            vfx_scale=float(effect.get("vfx", 1.0)),
                        )
                effect["ambient_timer"] = ambient
                tick = float(effect.get("tick", 0.0)) + dt
                effect["tick"] = tick
                if tick >= float(effect.get("tick_interval", 0.24)):
                    effect["tick"] = 0.0
                    for wolf in wolves:
                        if float(wolf.get("hp", 0.0)) <= 0.0:
                            continue
                        wpos = wolf.get("pos")
                        if not isinstance(wpos, Vector2):
                            continue
                        radius = float(effect.get("radius", 108.0))
                        if wpos.distance_squared_to(pos) <= radius * radius:
                            apply_spell_damage(wolf, float(effect.get("damage", 14.0)), Vector2(wpos.x, wpos.y), spell_id)
                            if random.random() < 0.28:
                                spawn_blood_splatter(spawned_effects, Vector2(wpos), intensity=0.72)

        elif kind == "melee_arc":
            pos = effect.get("pos")
            hit_ids = effect.get("hit")
            direction = effect.get("dir")
            if not isinstance(hit_ids, set):
                hit_ids = set()
                effect["hit"] = hit_ids
            if isinstance(pos, Vector2):
                dir_vec = Vector2(1, 0)
                if isinstance(direction, Vector2) and direction.length_squared() > 1e-5:
                    dir_vec = direction.normalize()
                for wolf in wolves:
                    if float(wolf.get("hp", 0.0)) <= 0.0:
                        continue
                    wolf_id = id(wolf)
                    if wolf_id in hit_ids:
                        continue
                    wpos = wolf.get("pos")
                    if not isinstance(wpos, Vector2):
                        continue
                    rel = wpos - pos
                    if rel.length_squared() <= float(effect.get("radius", 86.0)) ** 2:
                        rel_len = rel.length()
                        dot = 1.0
                        if rel_len > 0.001:
                            dot = rel.normalize().dot(dir_vec)
                        if dot >= -0.12:
                            apply_spell_damage(wolf, float(effect.get("damage", 18.0)), Vector2(wpos.x, wpos.y), str(effect.get("spell_id", "")))
                            hit_ids.add(wolf_id)
                            spawn_blood_splatter(spawned_effects, Vector2(wpos), intensity=1.35)

        elif kind == "cone":
            pos = effect.get("pos")
            hit_ids = effect.get("hit")
            direction = effect.get("dir")
            if not isinstance(hit_ids, set):
                hit_ids = set()
                effect["hit"] = hit_ids
            if isinstance(pos, Vector2):
                dir_vec = Vector2(1, 0)
                if isinstance(direction, Vector2) and direction.length_squared() > 1e-5:
                    dir_vec = direction.normalize()
                radius = max(20.0, float(effect.get("radius", 150.0)))
                half_angle = math.radians(max(20.0, float(effect.get("angle", 90.0))) * 0.5)
                dot_min = math.cos(half_angle)
                spell_id = str(effect.get("spell_id", ""))
                interrupt_duration = max(0.0, float(effect.get("interrupt_duration", 0.0)))
                for wolf in wolves:
                    if float(wolf.get("hp", 0.0)) <= 0.0:
                        continue
                    wolf_id = id(wolf)
                    if wolf_id in hit_ids:
                        continue
                    wpos = wolf.get("pos")
                    if not isinstance(wpos, Vector2):
                        continue
                    rel = wpos - pos
                    if rel.length_squared() > radius * radius:
                        continue
                    rel_len = rel.length()
                    if rel_len > 1e-5:
                        dot = rel.normalize().dot(dir_vec)
                        if dot < dot_min:
                            continue
                    hit_pos = Vector2(wpos.x, wpos.y)
                    dealt = apply_spell_damage(wolf, float(effect.get("damage", 18.0)), hit_pos, spell_id)
                    if dealt <= 0.0:
                        hit_ids.add(wolf_id)
                        continue
                    hit_ids.add(wolf_id)
                    spawn_blood_splatter(spawned_effects, Vector2(wpos), intensity=1.0)
                    # Wind burst VFX on hit
                    spawn_particle_burst(
                        spawned_effects, Vector2(wpos),
                        (200, 230, 255), (140, 190, 240),
                        count=8, speed_min=100.0, speed_max=260.0,
                        life_min=0.08, life_max=0.24,
                        size_start=3.0, size_end=0.4,
                        spread=0.8, direction=dir_vec,
                        gravity=-20.0, drag=2.0,
                    )
                    if interrupt_duration > 0.0:
                        if isinstance(status_effects, StatusEffectSystem):
                            status_effects.add_effect(
                                status_effects.wolf_key(wolf),
                                StatusEffect("stun", interrupt_duration, potency=1.0, color=(190, 220, 255)),
                            )
                        wolf["queued_strike"] = False
                        wolf["attack_state"] = "idle"
                        wolf["attack_timer"] = 0.0
                        wolf["attack_visual"] = 0.0

        elif kind == "pillar":
            pos = effect.get("pos")
            if isinstance(pos, Vector2):
                spell_id = str(effect.get("spell_id", ""))
                if not bool(effect.get("snapped", False)):
                    snapped = nearest_walkable(Vector2(pos), walk_bounds, obstacles, 10.0)
                    effect["pos"] = snapped
                    pos = snapped
                    effect["snapped"] = True
                if not bool(effect.get("impact_done", False)):
                    impact_radius = max(18.0, float(effect.get("impact_radius", 28.0)))
                    hit_ids = effect.get("hit")
                    if not isinstance(hit_ids, set):
                        hit_ids = set()
                        effect["hit"] = hit_ids
                    for wolf in wolves:
                        if float(wolf.get("hp", 0.0)) <= 0.0:
                            continue
                        wolf_id = id(wolf)
                        if wolf_id in hit_ids:
                            continue
                        wpos = wolf.get("pos")
                        if not isinstance(wpos, Vector2):
                            continue
                        if wpos.distance_squared_to(pos) <= impact_radius * impact_radius:
                            dealt = apply_spell_damage(wolf, float(effect.get("damage", 28.0)), Vector2(wpos.x, wpos.y), spell_id)
                            hit_ids.add(wolf_id)
                            if dealt > 0.0:
                                spawn_blood_splatter(spawned_effects, Vector2(wpos), intensity=0.9)
                                # Rock debris burst on hit
                                spawn_particle_burst(
                                    spawned_effects, Vector2(wpos),
                                    (180, 150, 100), (120, 95, 65),
                                    count=10, speed_min=80.0, speed_max=220.0,
                                    life_min=0.12, life_max=0.36,
                                    size_start=4.0, size_end=0.6,
                                    spread=math.tau, gravity=60.0, drag=2.0,
                                )
                                # Dust cloud
                                spawn_particle_burst(
                                    spawned_effects, Vector2(wpos.x, wpos.y + 4),
                                    (160, 140, 110), (100, 90, 70),
                                    count=6, speed_min=20.0, speed_max=60.0,
                                    life_min=0.25, life_max=0.60,
                                    size_start=5.0, size_end=1.5,
                                    spread=math.tau, gravity=-15.0, drag=1.5,
                                )
                                # Stone Pillar stuns on impact
                                if isinstance(status_effects, StatusEffectSystem):
                                    status_effects.add_effect(
                                        status_effects.wolf_key(wolf),
                                        StatusEffect("stun", 0.8, potency=1.0, color=(180, 155, 110)),
                                    )
                                    wolf["queued_strike"] = False
                                    wolf["attack_state"] = "idle"
                                    wolf["attack_timer"] = 0.0
                                    wolf["attack_visual"] = 0.0
                    effect["impact_done"] = True

                ambient = float(effect.get("ambient_timer", 0.0)) + dt
                if ambient >= 0.12:
                    ambient = 0.0
                    spawn_particle_burst(
                        spawned_effects,
                        Vector2(pos.x, pos.y + 6.0),
                        (170, 150, 118),
                        (104, 86, 68),
                        count=2,
                        speed_min=18.0,
                        speed_max=54.0,
                        life_min=0.26,
                        life_max=0.62,
                        size_start=3.6,
                        size_end=0.8,
                        spread=math.tau,
                        gravity=-18.0,
                        drag=1.4,
                        vfx_scale=float(effect.get("vfx", 1.0)),
                    )
                effect["ambient_timer"] = ambient

        elif kind == "particle":
            pos = effect.get("pos")
            vel = effect.get("vel")
            if isinstance(pos, Vector2) and isinstance(vel, Vector2):
                gravity = float(effect.get("gravity", 0.0))
                drag = max(0.0, float(effect.get("drag", 0.0)))
                if drag > 0.0:
                    vel *= max(0.0, 1.0 - drag * dt)
                if gravity != 0.0:
                    vel.y += gravity * dt
                pos += vel * dt
                effect["vel"] = vel
                effect["pos"] = pos

    if spawned_effects:
        spell_effects.extend(spawned_effects)

    spell_effects[:] = [effect for effect in spell_effects if float(effect.get("life", 0.0)) > 0.0]
    alive: List[Dict[str, object]] = []
    dead = 0
    dead_wolves: List[Dict[str, object]] = []
    for wolf in wolves:
        if float(wolf.get("hp", 0.0)) <= 0.0:
            if not bool(wolf.get("death_emitted", False)):
                wolf["death_emitted"] = True
                wolf["dying"] = True
                wolf["death_timer"] = 0.55
                wolf["death_duration"] = 0.55
                wolf["attack_state"] = "idle"
                wolf["attack_visual"] = 0.0
                wolf["chasing"] = False
                dead += 1
                wpos = wolf.get("pos")
                if isinstance(wpos, Vector2):
                    dead_wolves.append(
                        {
                            "pos": Vector2(wpos),
                            "level": max(1, int(wolf.get("level", 1))),
                            "name": str(wolf.get("name", "Wolf")),
                            "xp_reward": max(1, int(wolf.get("xp_reward", 14))),
                        }
                    )
            wolf["death_timer"] = max(0.0, float(wolf.get("death_timer", 0.0)) - dt)
            if float(wolf.get("death_timer", 0.0)) > 0.0:
                alive.append(wolf)
        else:
            alive.append(wolf)
    wolves[:] = alive
    
    alive_passives: List[Dict[str, object]] = []
    dead_passives_count = 0
    dead_passives_data: List[Dict[str, object]] = []
    for animal in passive_animals:
        if float(animal.get("hp", 0.0)) <= 0.0:
            if bool(animal.get("promoted_to_enemy", False)):
                continue
            dead_passives_count += 1
            dead_passives_data.append(animal)
        else:
            alive_passives.append(animal)
    passive_animals[:] = alive_passives

    return dead, dead_wolves, dead_passives_count, dead_passives_data

def draw_spell_effects(
    surface: pygame.Surface,
    spell_effects: List[Dict[str, object]],
    camera: Vector2,
) -> None:
    for effect in spell_effects:
        kind = str(effect.get("kind", ""))
        pos = effect.get("pos")
        if not isinstance(pos, Vector2):
            continue
        sx = int(pos.x - camera.x)
        sy = int(pos.y - camera.y)
        life = float(effect.get("life", 0.0))
        duration = max(0.001, float(effect.get("duration", 1.0)))
        t = clamp(1.0 - life / duration, 0.0, 1.0)
        colors = effect.get("colors")
        if not isinstance(colors, dict):
            colors = {}

        anim_set = str(effect.get("anim_set", "")).strip()
        has_anim = bool(anim_set)

        if kind == "projectile":
            trail_color = colors.get("trail", (255, 148, 78))
            core_color = colors.get("core", (255, 210, 130))
            outline_color = colors.get("outline", (142, 48, 30))
            spell_id = str(effect.get("spell_id", ""))
            class_id = spell_class_id(spell_id)
            vel = effect.get("vel")
            if spell_id in ("mage_wind", "mage_frostbolt"):
                now = pygame.time.get_ticks() * 0.001
                dir_vec = Vector2(1.0, 0.0)
                if isinstance(vel, Vector2) and vel.length_squared() > 1e-6:
                    dir_vec = vel.normalize()
                back = -dir_vec
                perp = Vector2(-dir_vec.y, dir_vec.x)
                glow_phase = float(effect.get("frost_glow_phase", 0.0))
                flicker = 0.84 + 0.16 * math.sin(now * 20.0 + glow_phase)
                core_r = max(4, int(float(effect.get("radius", 15.0)) * 0.50))

                # Outer frost mist halo
                pygame.gfxdraw.filled_circle(surface, sx, sy, core_r + 14, (100, 160, 220, int(28 * flicker)))
                pygame.gfxdraw.filled_circle(surface, sx, sy, core_r + 10, (140, 200, 255, int(40 * flicker)))

                # Main crystalline trail — longer, with ice shard shapes
                trail_steps = 10
                for i in range(trail_steps):
                    blend = i / max(1, trail_steps - 1)
                    dist = 2.0 + i * 3.2
                    wave = math.sin(now * 14.0 + i * 0.9) * 2.0 * blend
                    px = int(sx + back.x * dist + perp.x * wave)
                    py = int(sy + back.y * dist + perp.y * wave)
                    rr = max(1, int((6.5 - i * 0.55) * flicker))
                    col = color_lerp((242, 252, 255), (100, 170, 240), blend)
                    alpha = max(18, int((200 - i * 18) * flicker))
                    pygame.gfxdraw.filled_circle(surface, px, py, rr, (col[0], col[1], col[2], alpha))
                    # Ice crystal sparkle on every 3rd step
                    if i % 3 == 0 and i > 0:
                        spark_a = int(120 * flicker * (1.0 - blend))
                        pygame.gfxdraw.filled_circle(surface, px, py, max(1, rr + 2), (220, 240, 255, max(10, spark_a)))

                # Secondary wispy tendrils flanking the bolt
                for side in (-1, 1):
                    for i in range(4):
                        dist = 4.0 + i * 5.0
                        wave = math.sin(now * 8.0 + i * 1.6 + side * 2.0) * (4.0 + i * 1.5)
                        px = int(sx + back.x * dist + perp.x * wave * side)
                        py = int(sy + back.y * dist + perp.y * wave * side)
                        alpha = max(16, int((90 - i * 18) * flicker))
                        pygame.gfxdraw.filled_circle(surface, px, py, max(1, 3 - i // 2), (160, 210, 245, alpha))

                # Frost smoke wake
                for i in range(3):
                    dist = 16.0 + i * 7.0
                    px = int(sx + back.x * dist)
                    py = int(sy + back.y * dist + math.sin(now * 6.8 + i * 1.3) * 2.0)
                    pygame.gfxdraw.filled_circle(surface, px, py, 5 + i, (140, 180, 210, max(12, 48 - i * 12)))

                # Core bloom with layered glow
                pygame.gfxdraw.filled_circle(surface, sx, sy, core_r + 8, (100, 180, 255, int(50 * flicker)))
                pygame.gfxdraw.filled_circle(surface, sx, sy, core_r + 4, (170, 220, 255, int(140 * flicker)))
                pygame.gfxdraw.filled_circle(surface, sx, sy, core_r + 2, (210, 240, 255, int(190 * flicker)))
                pygame.gfxdraw.filled_circle(surface, sx, sy, max(2, core_r - 1), (248, 252, 255, 230))
                # Sharp highlight dot
                pygame.gfxdraw.filled_circle(surface, sx - 1, sy - 1, max(1, core_r // 2), (255, 255, 255, 240))
                pygame.gfxdraw.aacircle(surface, sx, sy, core_r + 3, (86, 122, 168, 180))
                continue
            if spell_id in ("mage_fire_ball", "mage_searing_bolt"):
                now = pygame.time.get_ticks() * 0.001
                dir_vec = Vector2(1.0, 0.0)
                if isinstance(vel, Vector2) and vel.length_squared() > 1e-6:
                    dir_vec = vel.normalize()
                back = -dir_vec
                perp = Vector2(-dir_vec.y, dir_vec.x)
                glow_phase = float(effect.get("firebolt_glow_phase", 0.0))
                flicker = 0.82 + 0.18 * math.sin(now * 28.0 + glow_phase)
                core_r = max(4, int(float(effect.get("radius", 14.0)) * 0.52))

                # Outer heat distortion halo
                heat_r = core_r + 16
                heat_pulse = 0.7 + 0.3 * math.sin(now * 18.0 + glow_phase)
                pygame.gfxdraw.filled_circle(surface, sx, sy, heat_r, (255, 120, 30, int(22 * heat_pulse)))
                pygame.gfxdraw.filled_circle(surface, sx, sy, heat_r - 4, (255, 160, 60, int(30 * heat_pulse)))

                # Main flame trail — long, flickering, with ember wisps
                trail_steps = 10
                for i in range(trail_steps):
                    blend = i / max(1, trail_steps - 1)
                    dist = 2.5 + i * 3.5
                    # Flame dance — trail wobbles side to side
                    wobble = math.sin(now * 22.0 + i * 1.1 + glow_phase) * (1.5 + blend * 3.0)
                    px = int(sx + back.x * dist + perp.x * wobble)
                    py = int(sy + back.y * dist + perp.y * wobble)
                    rr = max(1, int((7.0 - i * 0.6) * flicker))
                    col = color_lerp((255, 250, 210), (220, 80, 20), blend)
                    alpha = max(20, int((210 - i * 19) * flicker))
                    pygame.gfxdraw.filled_circle(surface, px, py, rr, (col[0], col[1], col[2], alpha))

                # Ember sparks flanking the bolt — hot orange points
                for side in (-1, 1):
                    for i in range(3):
                        dist = 6.0 + i * 6.0
                        wave = math.sin(now * 16.0 + i * 2.2 + side * 1.5) * (3.0 + i * 2.0)
                        px = int(sx + back.x * dist + perp.x * wave * side)
                        py = int(sy + back.y * dist + perp.y * wave * side)
                        alpha = max(20, int((110 - i * 28) * flicker))
                        pygame.gfxdraw.filled_circle(surface, px, py, max(1, 2), (255, 200, 100, alpha))

                # Smoke wake — dark wisps trailing behind
                for i in range(3):
                    dist = 22.0 + i * 8.0
                    wobble_s = math.sin(now * 5.0 + i * 1.8) * 3.0
                    px = int(sx + back.x * dist + perp.x * wobble_s)
                    py = int(sy + back.y * dist + perp.y * wobble_s)
                    smoke_r = 5 + i * 2
                    pygame.gfxdraw.filled_circle(surface, px, py, smoke_r, (80, 60, 50, max(10, 50 - i * 14)))

                # Core — bright layered bloom
                pygame.gfxdraw.filled_circle(surface, sx, sy, core_r + 10, (255, 100, 30, int(45 * flicker)))
                pygame.gfxdraw.filled_circle(surface, sx, sy, core_r + 6, (255, 150, 60, int(90 * flicker)))
                pygame.gfxdraw.filled_circle(surface, sx, sy, core_r + 3, (255, 200, 120, int(180 * flicker)))
                pygame.gfxdraw.filled_circle(surface, sx, sy, max(2, core_r), (255, 248, 210, 235))
                # Hot white center highlight
                pygame.gfxdraw.filled_circle(surface, sx - 1, sy - 1, max(1, core_r // 2), (255, 255, 240, 245))
                pygame.gfxdraw.aacircle(surface, sx, sy, core_r + 3, (160, 60, 20, 190))
                continue
            if isinstance(vel, Vector2):
                back = -vel.normalize() * 18.0
                for i in range(4):
                    fx = int(sx + back.x * i * 0.6)
                    fy = int(sy + back.y * i * 0.6)
                    alpha = max(34, 190 - i * 42)
                    pygame.gfxdraw.filled_circle(surface, fx, fy, 8 - i, (trail_color[0], trail_color[1], trail_color[2], alpha))
            if has_anim:
                draw_spell_anim(surface, effect, (sx, sy), t, loop=bool(effect.get("anim_loop", False)))
            else:
                pygame.draw.circle(surface, core_color, (sx, sy), 7)
                pygame.draw.circle(surface, outline_color, (sx, sy), 7, 1)
            if class_id and class_id != "rogue":
                theme = CLASS_SPELL_VFX_THEMES.get(class_id, {})
                glow = theme.get("accent", (226, 226, 236))
                halo_r = 9 + int(3 * (0.5 + 0.5 * math.sin(pygame.time.get_ticks() * 0.016 + sx * 0.03)))
                pygame.gfxdraw.aacircle(surface, sx, sy, halo_r, (glow[0], glow[1], glow[2], 120))

        elif kind == "frost_wave":
            start = effect.get("start")
            end = effect.get("end")
            if not isinstance(start, Vector2) or not isinstance(end, Vector2):
                continue
            path = end - start
            path_len = path.length()
            if path_len <= 1e-5:
                continue
            dir_vec = path / path_len
            normal = Vector2(-dir_vec.y, dir_vec.x)
            progress = clamp(1.0 - life / duration, 0.0, 1.0)
            tail_progress = max(0.0, progress - 0.28)
            head = start + dir_vec * (path_len * progress)
            tail = start + dir_vec * (path_len * tail_progress)
            sx_head = int(head.x - camera.x)
            sy_head = int(head.y - camera.y)
            sx_tail = int(tail.x - camera.x)
            sy_tail = int(tail.y - camera.y)
            sx_origin = int(start.x - camera.x)
            sy_origin = int(start.y - camera.y)

            wave_width = max(18.0, float(effect.get("width", 82.0)))
            fade = clamp(life / duration, 0.0, 1.0)
            now = pygame.time.get_ticks() * 0.001
            pulse = 0.84 + 0.16 * math.sin(now * 14.0 + progress * 8.0)
            core_color = colors.get("core", (208, 236, 255))
            trail_color = colors.get("trail", (162, 212, 255))
            ring_color = colors.get("ring", (194, 232, 255))
            outline_color = colors.get("outline", (92, 140, 196))
            inner_color = colors.get("inner", (104, 160, 220))

            wave_layer = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            outer_w = max(6, int(wave_width * (0.92 + 0.18 * pulse)))
            mid_w = max(4, int(wave_width * (0.56 + 0.12 * pulse)))
            inner_w = max(2, int(wave_width * (0.30 + 0.08 * pulse)))
            outer_alpha = int(126 * fade)
            mid_alpha = int(176 * fade)
            inner_alpha = int(220 * fade)

            pygame.draw.line(
                wave_layer,
                (outline_color[0], outline_color[1], outline_color[2], outer_alpha),
                (sx_tail, sy_tail),
                (sx_head, sy_head),
                outer_w,
            )
            pygame.draw.line(
                wave_layer,
                (trail_color[0], trail_color[1], trail_color[2], mid_alpha),
                (sx_tail, sy_tail),
                (sx_head, sy_head),
                mid_w,
            )
            pygame.draw.line(
                wave_layer,
                (core_color[0], core_color[1], core_color[2], inner_alpha),
                (sx_tail, sy_tail),
                (sx_head, sy_head),
                inner_w,
            )

            head_bloom = max(8, int(wave_width * (0.48 + 0.08 * pulse)))
            pygame.gfxdraw.filled_circle(
                wave_layer,
                sx_head,
                sy_head,
                head_bloom + 8,
                (trail_color[0], trail_color[1], trail_color[2], int(70 * fade)),
            )
            pygame.gfxdraw.filled_circle(
                wave_layer,
                sx_head,
                sy_head,
                head_bloom + 3,
                (ring_color[0], ring_color[1], ring_color[2], int(142 * fade)),
            )
            pygame.gfxdraw.filled_circle(
                wave_layer,
                sx_head,
                sy_head,
                max(3, head_bloom - 2),
                (242, 252, 255, int(222 * fade)),
            )

            origin_r = max(10, int(wave_width * 0.36))
            arc_shift = math.sin(now * 5.2) * 0.08
            pygame.gfxdraw.aacircle(
                wave_layer,
                sx_origin,
                sy_origin,
                origin_r,
                (ring_color[0], ring_color[1], ring_color[2], int(116 * fade)),
            )
            pygame.gfxdraw.aacircle(
                wave_layer,
                sx_origin,
                sy_origin,
                max(6, int(origin_r * 0.70)),
                (inner_color[0], inner_color[1], inner_color[2], int(138 * fade)),
            )
            for i in range(6):
                ang = arc_shift + (math.tau * i) / 6.0
                px = sx_origin + int(math.cos(ang) * origin_r)
                py = sy_origin + int(math.sin(ang) * origin_r)
                pygame.gfxdraw.filled_circle(
                    wave_layer,
                    px,
                    py,
                    2,
                    (236, 248, 255, int(154 * fade)),
                )

            shard_count = 5
            for i in range(shard_count):
                blend = (i + 0.5) / float(shard_count)
                sample = tail.lerp(head, blend)
                jitter = normal * math.sin(now * 9.0 + i * 1.4) * wave_width * 0.18
                px = int(sample.x + jitter.x - camera.x)
                py = int(sample.y + jitter.y - camera.y)
                rr = max(2, int(4 - i * 0.5))
                pygame.gfxdraw.filled_circle(
                    wave_layer,
                    px,
                    py,
                    rr + 1,
                    (outline_color[0], outline_color[1], outline_color[2], int(78 * fade)),
                )
                pygame.gfxdraw.filled_circle(
                    wave_layer,
                    px,
                    py,
                    rr,
                    (ring_color[0], ring_color[1], ring_color[2], int(148 * fade)),
                )

            surface.blit(wave_layer, (0, 0))

        elif kind == "particle":
            color = effect.get("color", (220, 220, 220))
            glow = effect.get("glow", color)
            if not (isinstance(color, tuple) and len(color) == 3):
                color = (220, 220, 220)
            if not (isinstance(glow, tuple) and len(glow) == 3):
                glow = color
            fade = clamp(life / duration, 0.0, 1.0)
            base_alpha = int(effect.get("alpha", 220))
            alpha = max(8, int(base_alpha * fade))
            size0 = max(0.4, float(effect.get("size0", 3.2)))
            size1 = max(0.2, float(effect.get("size1", 0.6)))
            rr = max(1, int(size0 + (size1 - size0) * (1.0 - fade)))
            pygame.gfxdraw.filled_circle(surface, sx, sy, rr + 2, (glow[0], glow[1], glow[2], max(8, alpha // 3)))
            pygame.gfxdraw.filled_circle(surface, sx, sy, rr, (color[0], color[1], color[2], alpha))

        elif kind == "nova":
            spell_id = str(effect.get("spell_id", ""))
            if spell_id in ("mage_water", "mage_frost_nova"):
                max_radius = max(24.0, float(effect.get("max_radius", 170.0)))
                progress = clamp(t, 0.0, 1.0)
                ease = 1.0 - ((1.0 - progress) ** 3)
                fade = clamp(1.0 - progress, 0.0, 1.0)
                now = pygame.time.get_ticks() * 0.001
                pulse = 0.78 + 0.22 * math.sin(now * 12.0 + sx * 0.009)
                ring_radius = max(16, int(max_radius * (0.10 + 0.90 * ease)))
                core_radius = max(8, int(ring_radius * 0.36))
                ring_color = colors.get("ring", (188, 228, 255))
                inner_color = colors.get("inner", (112, 166, 220))
                core_color = colors.get("core", (224, 246, 255))
                outline_color = colors.get("outline", (86, 128, 178))

                fx = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)

                # Frost bloom under the nova ring.
                pygame.gfxdraw.filled_circle(
                    fx,
                    sx,
                    sy,
                    max(10, int(ring_radius * 0.74)),
                    (82, 126, 176, int(58 * fade)),
                )
                pygame.gfxdraw.filled_circle(
                    fx,
                    sx,
                    sy,
                    max(8, int(ring_radius * 0.56)),
                    (132, 184, 236, int(86 * fade)),
                )
                pygame.gfxdraw.filled_circle(
                    fx,
                    sx,
                    sy,
                    core_radius + 6,
                    (198, 230, 255, int(116 * fade)),
                )
                pygame.gfxdraw.filled_circle(
                    fx,
                    sx,
                    sy,
                    core_radius,
                    (246, 252, 255, int(196 * fade)),
                )

                # Main shock ring + secondary glossy ring.
                outer_alpha = int(186 * fade)
                inner_alpha = int(142 * fade)
                pygame.gfxdraw.aacircle(fx, sx, sy, ring_radius + 2, (outline_color[0], outline_color[1], outline_color[2], max(0, outer_alpha - 36)))
                pygame.gfxdraw.aacircle(fx, sx, sy, ring_radius, (ring_color[0], ring_color[1], ring_color[2], outer_alpha))
                pygame.gfxdraw.aacircle(fx, sx, sy, max(8, ring_radius - 2), (core_color[0], core_color[1], core_color[2], inner_alpha))

                glossy_r = max(10, int(ring_radius * (0.72 + 0.08 * pulse)))
                pygame.gfxdraw.aacircle(
                    fx,
                    sx,
                    sy,
                    glossy_r,
                    (inner_color[0], inner_color[1], inner_color[2], int(120 * fade)),
                )

                # Radial glints for "shiny" AAA-style finish.
                spokes = 10
                for i in range(spokes):
                    ang = now * 1.8 + i * (math.tau / spokes)
                    d = Vector2(math.cos(ang), math.sin(ang))
                    start = (sx + int(d.x * core_radius * 0.7), sy + int(d.y * core_radius * 0.7))
                    end = (sx + int(d.x * ring_radius * 1.02), sy + int(d.y * ring_radius * 1.02))
                    pygame.draw.line(fx, (220, 244, 255, int(96 * fade)), start, end, 1)

                glints = 14
                for i in range(glints):
                    ang = -now * 2.4 + i * (math.tau / glints)
                    px = sx + int(math.cos(ang) * ring_radius)
                    py = sy + int(math.sin(ang) * ring_radius)
                    rr = 2 if i % 3 == 0 else 1
                    pygame.gfxdraw.filled_circle(
                        fx,
                        px,
                        py,
                        rr,
                        (236, 248, 255, int((136 if rr == 2 else 106) * fade)),
                    )

                # Rotating rune band — ice crystals
                rune_r = max(10, int(ring_radius * 0.62))
                rune_count = 8
                for i in range(rune_count):
                    ang = now * 1.4 + i * (math.tau / rune_count)
                    cx_r = sx + int(math.cos(ang) * rune_r)
                    cy_r = sy + int(math.sin(ang) * rune_r)
                    rect = pygame.Rect(cx_r - 2, cy_r - 2, 4, 4)
                    pygame.draw.rect(fx, (186, 224, 255, int(114 * fade)), rect, 1)
                    # Diamond crystal shape
                    cr_s = 3 + (i % 2)
                    pts = [(cx_r, cy_r - cr_s), (cx_r + cr_s, cy_r), (cx_r, cy_r + cr_s), (cx_r - cr_s, cy_r)]
                    pygame.draw.polygon(fx, (210, 240, 255, int(90 * fade)), pts, 1)

                # Ice crystal shards erupting outward from ring
                shard_count = 10
                for si in range(shard_count):
                    s_ang = now * 0.8 + si * (math.tau / shard_count) + 0.3
                    s_dist = ring_radius * (0.85 + 0.25 * math.sin(now * 3.0 + si * 1.7))
                    s_x = sx + int(math.cos(s_ang) * s_dist)
                    s_y = sy + int(math.sin(s_ang) * s_dist * 0.7)
                    s_len = max(4, int(12 * fade))
                    s_dir = Vector2(math.cos(s_ang), math.sin(s_ang) * 0.7)
                    s_end_x = s_x + int(s_dir.x * s_len)
                    s_end_y = s_y + int(s_dir.y * s_len)
                    s_alpha = max(20, int(140 * fade))
                    pygame.draw.line(fx, (200, 235, 255, s_alpha), (s_x, s_y), (s_end_x, s_end_y), 2)
                    # Bright tip
                    pygame.gfxdraw.filled_circle(fx, s_end_x, s_end_y, 2, (240, 250, 255, s_alpha))

                # Ground frost decal — expanding translucent ice floor
                frost_floor_r = max(8, int(ring_radius * 0.68 * ease))
                pygame.gfxdraw.filled_circle(fx, sx, sy, frost_floor_r, (160, 210, 240, int(28 * fade)))
                # Frost hex pattern on ground
                hex_count = 6
                for hi in range(hex_count):
                    h_ang = hi * (math.tau / hex_count)
                    h_r = frost_floor_r * 0.7
                    hx1 = sx + int(math.cos(h_ang) * h_r)
                    hy1 = sy + int(math.sin(h_ang) * h_r * 0.5)
                    h_ang2 = (hi + 1) * (math.tau / hex_count)
                    hx2 = sx + int(math.cos(h_ang2) * h_r)
                    hy2 = sy + int(math.sin(h_ang2) * h_r * 0.5)
                    pygame.draw.line(fx, (180, 220, 255, int(50 * fade)), (hx1, hy1), (hx2, hy2), 1)
                    pygame.draw.line(fx, (180, 220, 255, int(40 * fade)), (sx, sy), (hx1, hy1), 1)

                # Snowflake sparkle particles
                sparkle_count = 8
                for fi in range(sparkle_count):
                    f_phase = now * 2.0 + fi * 1.9
                    f_r_frac = 0.3 + 0.6 * ((math.sin(f_phase * 0.7) + 1.0) * 0.5)
                    f_ang = f_phase * 0.5
                    fpx = sx + int(math.cos(f_ang) * ring_radius * f_r_frac)
                    fpy = sy + int(math.sin(f_ang) * ring_radius * f_r_frac * 0.7) - int(math.sin(f_phase) * 6)
                    f_alpha = max(16, int(120 * fade * (0.5 + 0.5 * math.sin(f_phase * 3.0))))
                    # 6-pointed snowflake
                    for arm in range(6):
                        arm_ang = arm * (math.tau / 6) + now * 1.5
                        arm_len = 3
                        ax2 = fpx + int(math.cos(arm_ang) * arm_len)
                        ay2 = fpy + int(math.sin(arm_ang) * arm_len)
                        pygame.draw.line(fx, (230, 245, 255, f_alpha), (fpx, fpy), (ax2, ay2), 1)

                surface.blit(fx, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
                continue
            if has_anim:
                draw_spell_anim(surface, effect, (sx, sy), t, loop=bool(effect.get("anim_loop", False)))
                continue
            ring_color = colors.get("ring", (138, 210, 255))
            inner_color = colors.get("inner", (198, 240, 255))
            class_id = spell_class_id(spell_id)
            radius = int(26 + float(effect.get("max_radius", 180.0)) * t)
            alpha = int(138 * (1.0 - t))
            pygame.gfxdraw.aacircle(surface, sx, sy, radius, (ring_color[0], ring_color[1], ring_color[2], alpha))
            pygame.gfxdraw.aacircle(surface, sx, sy, radius - 1, (ring_color[0], ring_color[1], ring_color[2], alpha))
            pygame.gfxdraw.filled_circle(surface, sx, sy, max(8, radius // 3), (inner_color[0], inner_color[1], inner_color[2], alpha // 2))
            if class_id and class_id != "rogue":
                theme = CLASS_SPELL_VFX_THEMES.get(class_id, {})
                c0 = theme.get("core", ring_color)
                c1 = theme.get("accent", inner_color)
                ring2 = max(10, int(radius * 0.72))
                pygame.gfxdraw.aacircle(surface, sx, sy, ring2, (c0[0], c0[1], c0[2], max(44, alpha - 36)))
                pygame.gfxdraw.filled_circle(surface, sx, sy, max(4, radius // 5), (c1[0], c1[1], c1[2], max(28, alpha // 2)))

        elif kind == "orb":
            if has_anim:
                draw_spell_anim(surface, effect, (sx, sy), t, loop=bool(effect.get("anim_loop", False)))
                continue
            aura_color = colors.get("aura", (126, 76, 172))
            core_color = colors.get("core", (70, 40, 108))
            ring_color = colors.get("ring", (166, 116, 214))
            spell_id = str(effect.get("spell_id", ""))
            class_id = spell_class_id(spell_id)
            pulse = 1.0 + math.sin(pygame.time.get_ticks() * 0.012) * 0.2
            radius = int(26 * pulse)
            pygame.gfxdraw.filled_circle(surface, sx, sy, 52, (aura_color[0], aura_color[1], aura_color[2], 56))
            pygame.gfxdraw.filled_circle(surface, sx, sy, 30, (core_color[0], core_color[1], core_color[2], 94))
            pygame.draw.circle(surface, core_color, (sx, sy), radius)
            pygame.draw.circle(surface, ring_color, (sx, sy), radius, 2)
            ring_r = int(float(effect.get("radius", 110.0)))
            pygame.draw.circle(surface, aura_color, (sx, sy), ring_r, 1)
            if class_id and class_id != "rogue":
                theme = CLASS_SPELL_VFX_THEMES.get(class_id, {})
                c0 = theme.get("core", aura_color)
                c1 = theme.get("accent", ring_color)
                sat_count = 4
                now = pygame.time.get_ticks() * 0.0032
                orbit_r = max(12, int(ring_r * 0.46))
                for i in range(sat_count):
                    ang = now + i * (math.tau / sat_count)
                    px = sx + int(math.cos(ang) * orbit_r)
                    py = sy + int(math.sin(ang) * orbit_r)
                    pygame.gfxdraw.filled_circle(surface, px, py, 2, (c1[0], c1[1], c1[2], 170))
                pygame.gfxdraw.aacircle(surface, sx, sy, max(8, int(ring_r * 0.64)), (c0[0], c0[1], c0[2], 88))
            if str(effect.get("spell_id", "")) == "rogue_venom_trap":
                for i in range(3):
                    ang = pygame.time.get_ticks() * 0.004 + i * (math.tau / 3.0)
                    px = sx + int(math.cos(ang) * (14 + i * 6))
                    py = sy + int(math.sin(ang * 1.3) * (10 + i * 4))
                    pygame.gfxdraw.filled_circle(surface, px, py, 2 + (i % 2), (124, 212, 126, 138))

        elif kind == "ward":
            if has_anim:
                draw_spell_anim(surface, effect, (sx, sy), t, loop=bool(effect.get("anim_loop", False)))
                continue
            ring_color = colors.get("ring", (235, 208, 132))
            inner_color = colors.get("inner", (136, 108, 54))
            beam_color = colors.get("beam", (245, 216, 146))
            spell_id = str(effect.get("spell_id", ""))
            class_id = spell_class_id(spell_id)
            radius = int(float(effect.get("radius", 112.0)))
            pygame.gfxdraw.filled_ellipse(surface, sx, sy - 100, 51, 145, (beam_color[0], beam_color[1], beam_color[2], int(48 * (1.0 - t) + 18)))
            pygame.draw.circle(surface, ring_color, (sx, sy), radius, 3)
            pygame.draw.circle(surface, inner_color, (sx, sy), max(8, radius // 3), 1)
            if class_id and class_id != "rogue":
                theme = CLASS_SPELL_VFX_THEMES.get(class_id, {})
                c0 = theme.get("core", ring_color)
                c1 = theme.get("accent", beam_color)
                now = pygame.time.get_ticks() * 0.0017
                node_count = 6
                node_r = max(14, int(radius * 0.70))
                pygame.gfxdraw.aacircle(surface, sx, sy, node_r, (c0[0], c0[1], c0[2], 108))
                for i in range(node_count):
                    ang = now + i * (math.tau / node_count)
                    rx = sx + int(math.cos(ang) * node_r)
                    ry = sy + int(math.sin(ang) * node_r)
                    pygame.gfxdraw.filled_circle(surface, rx, ry, 2, (c1[0], c1[1], c1[2], 170))
            if str(effect.get("spell_id", "")) == "rogue_evasion_sigil":
                now = pygame.time.get_ticks() * 0.001
                pulse = 0.62 + 0.38 * math.sin(now * 7.0)
                outer_r = max(20, radius - 10)
                mid_r = max(14, int(outer_r * 0.74))
                inner_r = max(8, int(outer_r * 0.46))
                outer_col = (220, 204, 246, 164)
                mid_col = (178, 154, 226, 142)
                rune_col = (242, 232, 255, 172)
                pygame.gfxdraw.aacircle(surface, sx, sy, outer_r, outer_col)
                pygame.gfxdraw.aacircle(surface, sx, sy, mid_r, mid_col)
                pygame.gfxdraw.aacircle(surface, sx, sy, inner_r, rune_col)
                pygame.gfxdraw.filled_circle(surface, sx, sy, max(6, inner_r - 5), (108, 82, 170, 70))
                shard_count = 10
                for i in range(shard_count):
                    ang = now * 2.6 + i * (math.tau / shard_count)
                    ang2 = -now * 1.9 + i * (math.tau / shard_count)
                    rx = sx + int(math.cos(ang) * outer_r)
                    ry = sy + int(math.sin(ang) * outer_r)
                    rx2 = sx + int(math.cos(ang2) * mid_r)
                    ry2 = sy + int(math.sin(ang2) * mid_r)
                    pygame.gfxdraw.filled_circle(surface, rx, ry, 2, (242, 236, 255, 176))
                    pygame.gfxdraw.filled_circle(surface, rx2, ry2, 2, (176, 156, 228, 154))
                spoke_len = max(10, int(outer_r * (0.35 + 0.12 * pulse)))
                for i in range(6):
                    ang = now * 1.4 + i * (math.tau / 6.0)
                    x1 = sx + int(math.cos(ang) * (inner_r - 2))
                    y1 = sy + int(math.sin(ang) * (inner_r - 2))
                    x2 = sx + int(math.cos(ang) * (inner_r + spoke_len))
                    y2 = sy + int(math.sin(ang) * (inner_r + spoke_len))
                    pygame.draw.line(surface, (204, 188, 246, 122), (x1, y1), (x2, y2), 1)

        elif kind == "melee_arc":
            if has_anim:
                draw_spell_anim(surface, effect, (sx, sy), t, loop=bool(effect.get("anim_loop", False)))
                continue
            direction = effect.get("dir")
            if isinstance(direction, Vector2) and direction.length_squared() > 1e-4:
                dir_vec = direction.normalize()
            else:
                dir_vec = Vector2(1, 0)
            radius = int(float(effect.get("radius", 86.0)))
            ring_color = colors.get("ring", (232, 210, 146))
            inner_color = colors.get("inner", (128, 96, 52))
            start = math.atan2(-dir_vec.y, dir_vec.x) - 1.2
            end = math.atan2(-dir_vec.y, dir_vec.x) + 1.2
            arc_rect = pygame.Rect(sx - radius, sy - radius, radius * 2, radius * 2)
            pygame.draw.arc(surface, ring_color, arc_rect, start, end, 4)
            inner_rect = arc_rect.inflate(-22, -22)
            if inner_rect.width > 4 and inner_rect.height > 4:
                pygame.draw.arc(surface, inner_color, inner_rect, start, end, 2)
            spell_id = str(effect.get("spell_id", ""))
            class_id = spell_class_id(spell_id)
            if class_id and class_id != "rogue":
                theme = CLASS_SPELL_VFX_THEMES.get(class_id, {})
                c0 = theme.get("core", ring_color)
                mid_rect = arc_rect.inflate(-12, -12)
                if mid_rect.width > 4 and mid_rect.height > 4:
                    pygame.draw.arc(surface, c0, mid_rect, start + 0.04, end - 0.04, 2)
            if spell_id.startswith("rogue_"):
                slash_col = (196, 204, 232, 126)
                pygame.gfxdraw.arc(surface, sx, sy, max(6, radius - 10), int(math.degrees(start)), int(math.degrees(end)), slash_col)
                pygame.gfxdraw.arc(surface, sx, sy, max(6, radius - 20), int(math.degrees(start + 0.08)), int(math.degrees(end - 0.08)), (128, 132, 162, 112))

        elif kind == "cone":
            direction = effect.get("dir")
            if isinstance(direction, Vector2) and direction.length_squared() > 1e-4:
                dir_vec = direction.normalize()
            else:
                dir_vec = Vector2(1, 0)
            radius = max(26.0, float(effect.get("radius", 160.0)))
            angle_deg = max(20.0, float(effect.get("angle", 90.0)))
            half = math.radians(angle_deg * 0.5)
            left = rotate_vec(dir_vec, -half) * radius
            right = rotate_vec(dir_vec, half) * radius
            fade = clamp(life / duration, 0.0, 1.0)
            now_c = pygame.time.get_ticks() * 0.001
            spell_id_c = str(effect.get("spell_id", ""))
            fill_col = colors.get("trail", (186, 220, 255))
            edge_col = colors.get("ring", (120, 166, 204))
            core_col_c = colors.get("core", (210, 236, 255))
            cone_layer = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)

            # Multi-layered cone fill with gradient rings
            ring_steps = 5
            for ri in range(ring_steps):
                blend_r = ri / max(1, ring_steps - 1)
                r_scale = 0.3 + 0.7 * blend_r
                l_scaled = rotate_vec(dir_vec, -half) * radius * r_scale
                r_scaled = rotate_vec(dir_vec, half) * radius * r_scale
                mid_pts = []
                seg_count = 8
                for si in range(seg_count + 1):
                    frac = si / seg_count
                    ang = -half + frac * (half * 2)
                    pt = rotate_vec(dir_vec, ang) * radius * r_scale
                    mid_pts.append((sx + int(pt.x), sy + int(pt.y)))
                ring_alpha = int((50 + 30 * (1.0 - blend_r)) * fade)
                col_ring = color_lerp(core_col_c, fill_col, blend_r)
                for si in range(len(mid_pts) - 1):
                    pygame.draw.polygon(cone_layer, (col_ring[0], col_ring[1], col_ring[2], ring_alpha),
                        [(sx, sy), mid_pts[si], mid_pts[si + 1]])

            # Swirling wind lines — animated arcs inside the cone
            wind_count = 6
            for wi in range(wind_count):
                w_dist = 0.25 + 0.65 * (wi / max(1, wind_count - 1))
                w_phase = now_c * 8.0 + wi * 1.8
                w_ang_off = math.sin(w_phase) * half * 0.6
                w_dir = rotate_vec(dir_vec, w_ang_off)
                w_start = radius * w_dist * 0.4
                w_end = radius * w_dist
                for seg in range(4):
                    seg_t = seg / 3.0
                    seg_dist = w_start + (w_end - w_start) * seg_t
                    seg_wobble = math.sin(w_phase + seg * 1.2) * 6.0
                    w_perp = Vector2(-w_dir.y, w_dir.x)
                    wpx = int(sx + w_dir.x * seg_dist + w_perp.x * seg_wobble)
                    wpy = int(sy + w_dir.y * seg_dist + w_perp.y * seg_wobble)
                    w_alpha = max(16, int(110 * fade * (1.0 - seg_t * 0.5)))
                    pygame.gfxdraw.filled_circle(cone_layer, wpx, wpy, max(1, 3 - seg // 2), (220, 240, 255, w_alpha))

            # Edge gust streaks — bright lines along the cone edges
            for edge_dir in (rotate_vec(dir_vec, -half * 0.95), rotate_vec(dir_vec, half * 0.95)):
                for i in range(4):
                    d0 = radius * (0.2 + i * 0.2)
                    d1 = d0 + radius * 0.12
                    p0 = (sx + int(edge_dir.x * d0), sy + int(edge_dir.y * d0))
                    p1 = (sx + int(edge_dir.x * d1), sy + int(edge_dir.y * d1))
                    e_alpha = max(20, int(140 * fade * (1.0 - i * 0.2)))
                    pygame.draw.line(cone_layer, (200, 230, 255, e_alpha), p0, p1, 2)

            # Turbulence particles — small dots swirling within cone
            turb_count = 12
            for ti in range(turb_count):
                t_dist = random.Random(ti * 7 + 31).uniform(0.15, 0.92) * radius
                t_ang = -half + random.Random(ti * 13 + 7).uniform(0.0, 1.0) * half * 2
                t_wobble = math.sin(now_c * 6.0 + ti * 2.3) * 8.0
                t_dir = rotate_vec(dir_vec, t_ang)
                t_perp = Vector2(-t_dir.y, t_dir.x)
                tpx = int(sx + t_dir.x * t_dist + t_perp.x * t_wobble)
                tpy = int(sy + t_dir.y * t_dist + t_perp.y * t_wobble)
                t_alpha = max(14, int(90 * fade * math.sin(now_c * 4.0 + ti * 1.7) ** 2))
                pygame.gfxdraw.filled_circle(cone_layer, tpx, tpy, 2, (230, 245, 255, t_alpha))

            # Outer arc edge (smooth curved outline)
            arc_pts = []
            arc_segs = 14
            for ai in range(arc_segs + 1):
                frac = ai / arc_segs
                ang = -half + frac * (half * 2)
                pt = rotate_vec(dir_vec, ang) * radius
                arc_pts.append((sx + int(pt.x), sy + int(pt.y)))
            for ai in range(len(arc_pts) - 1):
                pygame.draw.line(cone_layer, (edge_col[0], edge_col[1], edge_col[2], int(180 * fade)), arc_pts[ai], arc_pts[ai + 1], 2)
            # Side edges
            pygame.draw.line(cone_layer, (edge_col[0], edge_col[1], edge_col[2], int(140 * fade)), (sx, sy), arc_pts[0], 1)
            pygame.draw.line(cone_layer, (edge_col[0], edge_col[1], edge_col[2], int(140 * fade)), (sx, sy), arc_pts[-1], 1)

            # Origin gust burst indicator
            gust_r = max(8, int(16 * fade))
            pygame.gfxdraw.filled_circle(cone_layer, sx, sy, gust_r, (core_col_c[0], core_col_c[1], core_col_c[2], int(80 * fade)))

            surface.blit(cone_layer, (0, 0))

        elif kind == "pillar":
            size = max(32.0, float(effect.get("size", 64.0)))
            base_w = int(size)
            base_h = max(18, int(size * 0.42))
            height = max(28, int(size * 0.92))
            now_p = pygame.time.get_ticks() * 0.001
            core_color_p = colors.get("core", (150, 124, 86))
            dark_color_p = colors.get("inner", (94, 76, 54))
            ring_color_p = colors.get("ring", (178, 150, 106))
            highlight_p = color_lerp(core_color_p, (232, 214, 176), 0.35)
            fade_p = clamp(life / duration, 0.0, 1.0)
            # Rise animation — pillar erupts from ground
            rise = clamp((1.0 - life / duration) * 5.0, 0.0, 1.0)  # fast rise in first 20% of life
            vis_height = max(4, int(height * rise))

            # Ground crack ring — expanding from base
            crack_r = int((base_w * 0.8 + 12) * min(1.0, rise * 1.5))
            if crack_r > 6:
                crack_segs = 8
                for ci in range(crack_segs):
                    ang1 = ci * (math.tau / crack_segs) + now_p * 0.3
                    ang2 = ang1 + 0.4
                    r1 = int(crack_r * (0.6 + 0.4 * math.sin(now_p * 2.0 + ci * 1.3)))
                    r2 = int(crack_r * (0.7 + 0.3 * math.sin(now_p * 2.4 + ci * 1.7)))
                    cx1 = sx + int(math.cos(ang1) * r1)
                    cy1 = sy + int(math.sin(ang1) * r1 * 0.5)
                    cx2 = sx + int(math.cos(ang2) * r2)
                    cy2 = sy + int(math.sin(ang2) * r2 * 0.5)
                    crack_a = max(20, int(90 * fade_p))
                    pygame.draw.line(surface, (dark_color_p[0], dark_color_p[1], dark_color_p[2], crack_a), (cx1, cy1), (cx2, cy2), 2)

            # Ground shadow — larger, softer
            shadow_w = base_w + 16
            shadow_h = base_h + 10
            shadow_surf = pygame.Surface((shadow_w + 10, shadow_h + 10), pygame.SRCALPHA)
            pygame.gfxdraw.filled_ellipse(shadow_surf, (shadow_w + 10) // 2, (shadow_h + 10) // 2,
                shadow_w // 2, shadow_h // 2, (0, 0, 0, int(100 * fade_p)))
            surface.blit(shadow_surf, (sx - (shadow_w + 10) // 2, sy - shadow_h // 2))

            # Dust cloud at base
            if rise < 0.8:
                dust_count = 6
                for di in range(dust_count):
                    d_ang = di * (math.tau / dust_count) + now_p * 1.5
                    d_r = int(base_w * 0.5 + 10 + rise * 20)
                    dx = sx + int(math.cos(d_ang) * d_r)
                    dy = sy + int(math.sin(d_ang) * d_r * 0.4) - int(rise * 8)
                    dust_a = max(10, int(60 * (1.0 - rise) * fade_p))
                    pygame.gfxdraw.filled_circle(surface, dx, dy, max(2, 5 - int(rise * 3)), (ring_color_p[0], ring_color_p[1], ring_color_p[2], dust_a))

            # Main pillar body — textured with vertical stone bands
            body_p = pygame.Rect(sx - base_w // 2, sy - vis_height, base_w, vis_height)
            pygame.draw.rect(surface, core_color_p, body_p, border_radius=5)
            # Vertical stone texture lines
            band_count = max(2, base_w // 10)
            for bi in range(band_count):
                bx = body_p.left + 4 + bi * (body_p.width - 8) // max(1, band_count - 1)
                shade = dark_color_p if bi % 2 == 0 else highlight_p
                pygame.draw.line(surface, shade, (bx, body_p.top + 4), (bx, body_p.bottom - 2), 1)
            # Horizontal crack lines
            for hi in range(max(1, vis_height // 18)):
                hy = body_p.top + 8 + hi * 18
                if hy < body_p.bottom - 4:
                    hx_off = int(math.sin(hi * 2.3) * 4)
                    pygame.draw.line(surface, dark_color_p,
                        (body_p.left + 3 + hx_off, hy), (body_p.right - 3 + hx_off, hy), 1)

            # Outline
            pygame.draw.rect(surface, dark_color_p, body_p, 2, border_radius=5)

            # Top cap — rocky crown with jagged edge
            cap_h = max(6, int(vis_height * 0.22))
            cap_p = pygame.Rect(body_p.left + 4, body_p.top + 2, body_p.width - 8, cap_h)
            pygame.draw.rect(surface, highlight_p, cap_p, border_radius=3)
            # Jagged crown points
            for ji in range(max(2, base_w // 12)):
                jx = cap_p.left + 2 + ji * max(1, (cap_p.width - 4) // max(1, base_w // 12 - 1))
                jh = 3 + (ji % 3) * 2
                pygame.draw.line(surface, highlight_p, (jx, cap_p.top), (jx, cap_p.top - jh), 2)

            # Ambient glow at base — earthy warmth
            glow_a = int(40 * fade_p * (0.7 + 0.3 * math.sin(now_p * 3.0)))
            pygame.gfxdraw.filled_circle(surface, sx, sy, max(4, base_w // 2 + 6), (ring_color_p[0], ring_color_p[1], ring_color_p[2], glow_a))

        elif kind == "blood_splatter":
            drops = effect.get("drops")
            if not isinstance(drops, list) or not drops:
                continue
            fade = clamp(life / duration, 0.0, 1.0)
            stain = pygame.Surface((96, 64), pygame.SRCALPHA)
            for drop in drops:
                if not isinstance(drop, (tuple, list)) or len(drop) < 3:
                    continue
                dx = int(float(drop[0]))
                dy = int(float(drop[1]))
                rr = max(1, int(float(drop[2])))
                alpha = int(110 * fade)
                pygame.gfxdraw.filled_ellipse(surface, sx + dx, sy + dy, rr, rr // 2, (96, 16, 18, alpha))
                if rr >= 3:
                    pygame.gfxdraw.filled_ellipse(surface, sx + dx, sy + dy - 1, rr // 2, rr // 4, (136, 24, 26, max(28, alpha // 2)))

        # ── Universal class-tinted ambient VFX particles ──
        # Emits orbiting ember/arcane motes around ANY active spell effect,
        # tinted by the caster's class palette. Adds cohesive class identity
        # across all spell kinds without modifying individual handlers.
        if kind in ("projectile", "nova", "orb", "ward", "melee_arc", "cone", "pillar", "frost_wave"):
            _eff_spell_id = str(effect.get("spell_id", ""))
            _eff_class_id = spell_class_id(_eff_spell_id)
            if _eff_class_id:
                _eff_theme = CLASS_SPELL_VFX_THEMES.get(_eff_class_id, {})
                _eff_core = _eff_theme.get("core", (200, 200, 200))
                _eff_accent = _eff_theme.get("accent", (180, 180, 180))
                _eff_now = pygame.time.get_ticks() * 0.001
                _eff_fade = clamp(life / max(0.001, duration), 0.0, 1.0)
                # 6 orbiting class motes with staggered phase and varying orbit radius
                for _mi in range(6):
                    _m_phase = _eff_now * (1.8 + _mi * 0.4) + _mi * (math.tau / 6.0) + hash(_eff_spell_id) * 0.1
                    _m_orbit = 14 + _mi * 5 + int(6 * math.sin(_eff_now * 0.7 + _mi))
                    _mx = sx + int(math.cos(_m_phase) * _m_orbit)
                    _my = sy + int(math.sin(_m_phase) * _m_orbit)
                    _m_col = _eff_core if _mi % 2 == 0 else _eff_accent
                    _m_alpha = max(10, int(100 * _eff_fade * (0.5 + 0.5 * math.sin(_eff_now * 3.0 + _mi * 1.1))))
                    _m_r = 2 + (_mi % 2)
                    # Soft glow halo
                    pygame.gfxdraw.filled_circle(surface, _mx, _my, _m_r + 3,
                        (_m_col[0], _m_col[1], _m_col[2], max(5, _m_alpha // 3)))
                    # Core mote
                    pygame.gfxdraw.filled_circle(surface, _mx, _my, _m_r,
                        (_m_col[0], _m_col[1], _m_col[2], _m_alpha))
                    # Hot center pixel
                    if _m_r >= 2 and _m_alpha > 40:
                        pygame.gfxdraw.filled_circle(surface, _mx, _my, 1,
                            (255, 255, 255, max(10, _m_alpha // 2)))
                # Rising spark trail (class-colored sparks drifting upward)
                for _si in range(4):
                    _s_phase = ((_eff_now * 0.6 + _si * 0.28 + hash(_eff_spell_id) * 0.05) % 1.0)
                    _s_x_off = int(12 * math.sin(_eff_now * 1.5 + _si * 2.3))
                    _s_y_off = -int(_s_phase * 40) - 8
                    _s_alpha = max(8, int(90 * (1.0 - _s_phase) * _eff_fade))
                    _s_col = _eff_accent
                    pygame.gfxdraw.filled_circle(surface, sx + _s_x_off, sy + _s_y_off, 2,
                        (_s_col[0], _s_col[1], _s_col[2], _s_alpha))
                    pygame.gfxdraw.filled_circle(surface, sx + _s_x_off, sy + _s_y_off, 4,
                        (_s_col[0], _s_col[1], _s_col[2], max(4, _s_alpha // 4)))


def spell_is_unlocked(spell_id: str, spellbook: List[Dict[str, object]], unlocked_skills: Set[str]) -> bool:
    for spell in spellbook:
        if str(spell["id"]) == spell_id:
            return str(spell["skill"]) in unlocked_skills
    return False
