from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, TYPE_CHECKING

import pygame
import pygame.gfxdraw
from pygame import Vector2

from game.utils import clamp

if TYPE_CHECKING:
    from .runtime import CombatRuntime, CombatSceneContext


@dataclass(frozen=True)
class SpellPhase:
    name: str
    duration: float


class TimelineSpell:
    def __init__(
        self,
        definition: Dict[str, object],
        caster_pos: Vector2,
        target_pos: Vector2,
        facing: int,
        *,
        spell_mods: Optional[Dict[str, float]] = None,
        bonus_power: float = 0.0,
        class_damage_mult: float = 1.0,
    ) -> None:
        self.definition = dict(definition)
        self.spell_id = str(self.definition.get("id", "runtime_spell"))
        self.name = str(self.definition.get("name", self.spell_id))
        self.origin = Vector2(caster_pos)
        self.target = Vector2(target_pos)
        self.facing = 1 if int(facing) >= 0 else -1
        self.spell_mods = dict(spell_mods or {})
        self.bonus_power = float(bonus_power)
        self.class_damage_mult = max(0.1, float(class_damage_mult))
        self.phase_index = 0
        self.phase_elapsed = 0.0
        self.total_elapsed = 0.0
        self.alive = True
        self.phases: Sequence[SpellPhase] = tuple(self.build_phases())
        if not self.phases:
            self.phases = (SpellPhase("action", 0.1),)

    def build_phases(self) -> Sequence[SpellPhase]:
        raise NotImplementedError

    def start(self, runtime: "CombatRuntime", context: "CombatSceneContext") -> None:
        self.on_phase_enter(self.current_phase.name, runtime, context)

    @property
    def current_phase(self) -> SpellPhase:
        return self.phases[min(self.phase_index, len(self.phases) - 1)]

    def mod(self, key: str, default: float = 0.0) -> float:
        return float(self.spell_mods.get(key, default))

    def mult(self, key: str, default: float = 1.0) -> float:
        return max(0.1, float(self.spell_mods.get(key, default)))

    def base_damage(self, base: float) -> float:
        return (float(base) + self.bonus_power * 3.0) * self.mult("damage_mult", 1.0) * self.class_damage_mult

    def phase_progress(self) -> float:
        return clamp(self.phase_elapsed / max(0.001, self.current_phase.duration), 0.0, 1.0)

    def update(self, dt: float, runtime: "CombatRuntime", context: "CombatSceneContext") -> None:
        if not self.alive or dt <= 0.0:
            return
        remaining = dt
        while remaining > 0.0 and self.alive:
            phase = self.current_phase
            slice_dt = remaining
            if phase.duration > 0.0:
                slice_dt = min(slice_dt, phase.duration - self.phase_elapsed)
            self.phase_elapsed += slice_dt
            self.total_elapsed += slice_dt
            self.on_phase_update(phase.name, slice_dt, runtime, context)
            remaining -= slice_dt
            if phase.duration > 0.0 and self.phase_elapsed + 1e-6 >= phase.duration and self.alive:
                self.on_phase_exit(phase.name, runtime, context)
                self.phase_index += 1
                if self.phase_index >= len(self.phases):
                    self.alive = False
                    break
                self.phase_elapsed = 0.0
                self.on_phase_enter(self.current_phase.name, runtime, context)

    def on_phase_enter(self, phase: str, runtime: "CombatRuntime", context: "CombatSceneContext") -> None:
        del phase, runtime, context

    def on_phase_update(self, phase: str, dt: float, runtime: "CombatRuntime", context: "CombatSceneContext") -> None:
        del phase, dt, runtime, context

    def on_phase_exit(self, phase: str, runtime: "CombatRuntime", context: "CombatSceneContext") -> None:
        del phase, runtime, context

    def draw(self, surface: pygame.Surface, camera: Vector2) -> None:
        del surface, camera


class ArcBoltSpell(TimelineSpell):
    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        direction = self.target - self.origin
        if direction.length_squared() <= 1e-6:
            direction = Vector2(1.0 if self.facing >= 0 else -1.0, 0.0)
        self.direction = direction.normalize()
        self.pos = Vector2(self.origin.x, self.origin.y - 22.0)
        self.speed = 1020.0 * self.mult("speed_mult", 1.0)
        self.radius = 14.0 + self.mod("radius_bonus", 0.0)
        self.max_range = float(self.definition.get("cast_range", 980.0))
        self.distance_travelled = 0.0
        self.hit_targets: set[int] = set()
        self.trail_timer = 0.0
        self.returning = False
        self.pierce_remaining = max(0, int(round(self.mod("pierce_bonus", 0.0))))
        self.impact_flash = tuple(self.definition.get("colors", {}).get("core", (244, 232, 255)))  # type: ignore[index]

    def build_phases(self) -> Sequence[SpellPhase]:
        return (
            SpellPhase("windup", 0.12),
            SpellPhase("action", 0.70),
            SpellPhase("aftermath", 0.10),
        )

    def on_phase_enter(self, phase: str, runtime: "CombatRuntime", context: "CombatSceneContext") -> None:
        if phase == "windup":
            runtime.vfx.spawn("arcane_cast_flash", Vector2(self.origin.x, self.origin.y - 18.0))
            if context.audio is not None:
                context.audio.play_sfx("cast_projectile", cooldown_ms=22)

    def on_phase_update(self, phase: str, dt: float, runtime: "CombatRuntime", context: "CombatSceneContext") -> None:
        if phase != "action":
            return
        prev = Vector2(self.pos)
        self.pos += self.direction * self.speed * dt
        self.distance_travelled += self.speed * dt
        self.trail_timer += dt
        if self.trail_timer >= 0.016:
            self.trail_timer = 0.0
            runtime.vfx.spawn("arcane_trail", self.pos, self.direction * self.speed)
        if runtime.projectile_hits_obstacle(self.pos, self.radius, context.obstacles):
            runtime.vfx.spawn("arcane_impact", self.pos)
            self.alive = False
            return
        hit_enemy = runtime.first_enemy_hit(self.pos, self.radius, context.enemies, self.hit_targets, context=context)
        if hit_enemy is not None:
            self.hit_targets.add(id(hit_enemy))
            self._impact_enemy(hit_enemy, runtime, context)
            if self.pierce_remaining > 0:
                self.pierce_remaining -= 1
            else:
                self.phase_index = min(self.phase_index, len(self.phases) - 1)
                self.phase_elapsed = self.current_phase.duration
            return
        if self.distance_travelled >= self.max_range:
            if self.mod("return_bolt", 0.0) > 0.0 and not self.returning:
                self.returning = True
                to_origin = self.origin - self.pos
                if to_origin.length_squared() > 1e-6:
                    self.direction = to_origin.normalize()
                self.distance_travelled = 0.0
                return
            runtime.vfx.spawn("arcane_impact", self.pos)
            self.alive = False
        elif self.returning and self.pos.distance_to(self.origin) <= 16.0:
            runtime.vfx.spawn("arcane_impact", self.pos)
            self.alive = False
        elif prev.distance_squared_to(self.pos) > 0.0:
            runtime.vfx.spawn_trail(prev, self.pos, color0=(196, 180, 255), color1=(96, 78, 168), duration=0.10, width0=5.0, width1=1.0)

    def _impact_enemy(self, enemy: Dict[str, object], runtime: "CombatRuntime", context: "CombatSceneContext") -> None:
        damage = self.base_damage(float(self.definition.get("damage", 26.0)))
        runtime.vfx.spawn("arcane_impact", self.pos)
        runtime.damage_enemy(
            context,
            enemy,
            damage,
            self.pos,
            flash_color=(255, 244, 224),
            screen_flash_color=(230, 210, 255),
            hit_stop=0.045,
            shake=4.4,
        )
        splash_radius = 34.0 + self.mod("impact_burst_radius_bonus", 0.0)
        splash_damage = damage * 0.35
        runtime.damage_enemies_in_radius(
            context,
            center=self.pos,
            radius=splash_radius,
            amount=splash_damage,
            ignore={id(enemy)},
            flash_color=(232, 222, 255),
            screen_flash_color=(214, 200, 248),
            hit_stop=0.02,
            shake=1.8,
        )
        chain_count = max(0, int(round(self.mod("fork_shards", 0.0))))
        if chain_count > 0:
            for fork in runtime.closest_enemies(self.pos, context.enemies, radius=150.0, ignore=self.hit_targets)[:chain_count]:
                fork_pos = runtime.enemy_position(fork)
                if fork_pos is None:
                    continue
                runtime.vfx.spawn_trail(self.pos, fork_pos, color0=(246, 236, 255), color1=(154, 118, 240), duration=0.14, width0=4.0, width1=1.0)
                runtime.damage_enemy(
                    context,
                    fork,
                    damage * 0.45,
                    fork_pos,
                    flash_color=(250, 236, 255),
                    screen_flash_color=(222, 206, 255),
                    hit_stop=0.02,
                    shake=1.6,
                )
                self.hit_targets.add(id(fork))

    def draw(self, surface: pygame.Surface, camera: Vector2) -> None:
        if self.current_phase.name != "action":
            return
        sx = int(self.pos.x - camera.x)
        sy = int(self.pos.y - camera.y)
        pygame.gfxdraw.filled_circle(surface, sx, sy, int(self.radius) + 3, (136, 110, 220, 48))
        pygame.gfxdraw.filled_circle(surface, sx, sy, int(self.radius), (230, 220, 255, 220))
        pygame.gfxdraw.aacircle(surface, sx, sy, max(4, int(self.radius)), (150, 110, 255, 220))


class StarfallSigilSpell(TimelineSpell):
    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.center = Vector2(self.target)
        self.radius = 84.0 + self.mod("radius_bonus", 0.0)
        self.field_timer = 0.0
        self.aftershock_done = 0
        self.field_duration = 0.65 + self.mod("field_duration_bonus", 0.0)
        self.final_blast_triggered = False

    def build_phases(self) -> Sequence[SpellPhase]:
        return (
            SpellPhase("windup", 0.16),
            SpellPhase("action", 0.55),
            SpellPhase("impact", 0.15),
            SpellPhase("aftermath", 0.65 + self.mod("field_duration_bonus", 0.0)),
        )

    def on_phase_enter(self, phase: str, runtime: "CombatRuntime", context: "CombatSceneContext") -> None:
        if phase == "windup":
            runtime.vfx.spawn_telegraph(self.center, radius=self.radius, duration=0.71, color=(255, 170, 78), outline=(255, 232, 172), fill_alpha=44)
            if context.audio is not None:
                context.audio.play_sfx("cast_ward", cooldown_ms=36)
        elif phase == "impact":
            self._burst(runtime, context, bonus_mult=1.0)
        elif phase == "aftermath":
            runtime.vfx.spawn_ring(self.center, radius0=self.radius * 0.35, radius1=self.radius, duration=0.42, color=(255, 214, 126), width=3, layer="ground")

    def on_phase_update(self, phase: str, dt: float, runtime: "CombatRuntime", context: "CombatSceneContext") -> None:
        if phase == "action":
            runtime.vfx.spawn_particles(
                self.center + Vector2(random.uniform(-self.radius * 0.4, self.radius * 0.4), -random.uniform(14.0, 42.0)),
                color0=(255, 246, 208),
                color1=(255, 164, 82),
                count=1,
                speed_min=30.0,
                speed_max=80.0,
                life_min=0.08,
                life_max=0.16,
                size0=3.2,
                size1=0.4,
                gravity=26.0,
                drag=1.2,
                layer="world",
            )
        elif phase == "aftermath":
            self.field_timer += dt
            while self.field_timer >= 0.28:
                self.field_timer -= 0.28
                pulse_damage_mult = self.mod("field_pulse_damage_mult", 0.0)
                if pulse_damage_mult > 0.0:
                    runtime.vfx.spawn_ring(self.center, radius0=self.radius * 0.4, radius1=self.radius * 0.95, duration=0.16, color=(255, 224, 142), width=2, layer="ground")
                    runtime.damage_enemies_in_radius(
                        context,
                        center=self.center,
                        radius=self.radius,
                        amount=self.base_damage(float(self.definition.get("damage", 38.0))) * pulse_damage_mult,
                        ignore=set(),
                        flash_color=(255, 234, 176),
                        screen_flash_color=(255, 214, 120),
                        hit_stop=0.01,
                        shake=1.4,
                    )
                extra_pulses = max(0, int(round(self.mod("aftershock_pulses", 0.0))))
                if self.aftershock_done < extra_pulses:
                    self.aftershock_done += 1
                    self._burst(runtime, context, bonus_mult=0.58)
            if not self.final_blast_triggered and self.mod("final_detonation", 0.0) > 0.0 and self.phase_progress() >= 0.92:
                self.final_blast_triggered = True
                self._burst(runtime, context, bonus_mult=0.8)

    def _burst(self, runtime: "CombatRuntime", context: "CombatSceneContext", *, bonus_mult: float) -> None:
        damage = self.base_damage(float(self.definition.get("damage", 38.0))) * bonus_mult
        runtime.vfx.spawn("meteor_impact", self.center)
        runtime.damage_enemies_in_radius(
            context,
            center=self.center,
            radius=self.radius,
            amount=damage,
            ignore=set(),
            flash_color=(255, 236, 178),
            screen_flash_color=(255, 210, 132),
            hit_stop=0.03,
            shake=3.4,
        )

    def draw(self, surface: pygame.Surface, camera: Vector2) -> None:
        if self.current_phase.name not in ("action", "impact", "aftermath"):
            return
        sx = int(self.center.x - camera.x)
        sy = int(self.center.y - camera.y)
        alpha = 110 if self.current_phase.name == "action" else 74
        pygame.gfxdraw.filled_circle(surface, sx, sy, max(8, int(self.radius * 0.18)), (255, 214, 124, alpha))


class PhaseBlinkSpell(TimelineSpell):
    def __init__(self, *args: object, destination: Vector2, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.destination = Vector2(destination)
        self.arrival_radius = 86.0 + self.mod("blink_radius_bonus", 0.0)
        self.knockback = 72.0 + self.mod("blink_knockback_bonus", 0.0)

    def build_phases(self) -> Sequence[SpellPhase]:
        return (
            SpellPhase("windup", 0.10),
            SpellPhase("action", 0.08),
            SpellPhase("aftermath", 0.28),
        )

    def on_phase_enter(self, phase: str, runtime: "CombatRuntime", context: "CombatSceneContext") -> None:
        if phase == "windup":
            runtime.vfx.spawn_telegraph(self.destination, radius=self.arrival_radius * 0.55, duration=0.14, color=(144, 214, 255), outline=(222, 250, 255), fill_alpha=26)
            if context.audio is not None:
                context.audio.play_sfx("cast_orb", cooldown_ms=36)
        elif phase == "action":
            runtime.vfx.spawn("blink_depart", self.origin)
            runtime.vfx.spawn("blink_arrive", self.destination)
            if self.mod("departure_nova", 0.0) > 0.0:
                runtime.damage_enemies_in_radius(
                    context,
                    center=self.origin,
                    radius=self.arrival_radius * 0.55,
                    amount=self.base_damage(float(self.definition.get("damage", 38.0))) * 0.45,
                    ignore=set(),
                    flash_color=(210, 244, 255),
                    screen_flash_color=(176, 228, 255),
                    hit_stop=0.015,
                    shake=1.4,
                )
            hit_enemies = runtime.closest_enemies(self.destination, context.enemies, radius=self.arrival_radius, ignore=set())
            for enemy in hit_enemies:
                enemy_pos = runtime.enemy_position(enemy)
                if enemy_pos is None:
                    continue
                runtime.damage_enemy(
                    context,
                    enemy,
                    self.base_damage(float(self.definition.get("damage", 38.0))) * self.mult("blink_arrival_damage_mult", 1.0),
                    enemy_pos,
                    flash_color=(214, 246, 255),
                    screen_flash_color=(196, 226, 255),
                    hit_stop=0.03,
                    shake=2.8,
                )
                runtime.knockback_enemy(context, enemy, self.destination, self.knockback)

    def draw(self, surface: pygame.Surface, camera: Vector2) -> None:
        if self.current_phase.name != "windup":
            return
        ax = int(self.origin.x - camera.x)
        ay = int(self.origin.y - camera.y - 18)
        bx = int(self.destination.x - camera.x)
        by = int(self.destination.y - camera.y - 8)
        pygame.draw.line(surface, (164, 220, 255, 160), (ax, ay), (bx, by), 2)


class AstralCataclysmSpell(TimelineSpell):
    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.zone_radius = 160.0 + self.mod("zone_radius_bonus", 0.0)
        self.strike_timer = 0.0
        self.strike_index = 0
        self.strike_points = self._build_strike_points()

    def build_phases(self) -> Sequence[SpellPhase]:
        return (
            SpellPhase("windup", 0.20),
            SpellPhase("action", 0.75),
            SpellPhase("impact", 1.00),
            SpellPhase("aftermath", 0.45),
        )

    def _build_strike_points(self) -> List[Vector2]:
        count = 4 + max(0, int(round(self.mod("extra_meteors", 0.0))))
        points: List[Vector2] = []
        if self.mod("line_pattern", 0.0) > 0.0:
            for idx in range(count):
                t = idx / max(1, count - 1)
                points.append(self.origin.lerp(self.target, t))
            return points
        rng = random.Random(f"{self.origin.x:.2f}:{self.origin.y:.2f}:{self.target.x:.2f}:{self.target.y:.2f}")
        for _ in range(count):
            ang = rng.random() * math.tau
            dist = rng.uniform(0.18, 1.0) ** 0.75 * self.zone_radius
            points.append(self.target + Vector2(math.cos(ang), math.sin(ang)) * dist)
        return points

    def on_phase_enter(self, phase: str, runtime: "CombatRuntime", context: "CombatSceneContext") -> None:
        if phase == "windup":
            runtime.vfx.spawn_telegraph(self.target, radius=self.zone_radius, duration=0.95, color=(255, 150, 94), outline=(255, 232, 182), fill_alpha=52)
            if context.audio is not None:
                context.audio.play_sfx("cast_ward", cooldown_ms=44)
                context.audio.play_sfx("cast_nova", cooldown_ms=36)

    def on_phase_update(self, phase: str, dt: float, runtime: "CombatRuntime", context: "CombatSceneContext") -> None:
        if phase != "impact":
            return
        self.strike_timer += dt
        interval = 0.22
        while self.strike_timer >= interval and self.strike_index < len(self.strike_points):
            self.strike_timer -= interval
            strike_pos = self.strike_points[self.strike_index]
            self.strike_index += 1
            runtime.vfx.spawn("meteor_impact", strike_pos)
            runtime.damage_enemies_in_radius(
                context,
                center=strike_pos,
                radius=92.0,
                amount=self.base_damage(float(self.definition.get("damage", 54.0))) * self.mult("impact_damage_mult", 1.0),
                ignore=set(),
                flash_color=(255, 242, 214),
                screen_flash_color=(255, 188, 118),
                hit_stop=0.045,
                shake=5.2,
            )
            pull_strength = self.mod("gravity_pull", 0.0)
            if pull_strength > 0.0:
                for enemy in runtime.closest_enemies(self.target, context.enemies, radius=self.zone_radius, ignore=set()):
                    runtime.pull_enemy(context, enemy, self.target, pull_strength)

    def draw(self, surface: pygame.Surface, camera: Vector2) -> None:
        if self.current_phase.name in ("windup", "action"):
            sx = int(self.target.x - camera.x)
            sy = int(self.target.y - camera.y)
            pygame.gfxdraw.aacircle(surface, sx, sy, int(self.zone_radius), (255, 220, 172, 120))
            for point in self.strike_points:
                px = int(point.x - camera.x)
                py = int(point.y - camera.y)
                pygame.draw.line(surface, (255, 228, 182, 120), (px, py - 18), (px, py + 4), 1)
        elif self.current_phase.name == "aftermath":
            sx = int(self.target.x - camera.x)
            sy = int(self.target.y - camera.y)
            pygame.gfxdraw.filled_circle(surface, sx, sy, max(8, int(self.zone_radius * 0.30)), (255, 166, 110, 34))


class _FoozleSpellBase(TimelineSpell):
    """Shared helpers for Foozle pixel-art spells that draw a sprite-sheet frame in world.

    Subclasses set ANIM_NAME (matching a key in VFXManager._animation_paths) and
    call self._frames(runtime) to get the cached frame list.
    """
    ANIM_NAME: str = ""
    SPRITE_SCALE: float = 3.0

    def _frames(self, runtime: "CombatRuntime") -> List[pygame.Surface]:
        return runtime.vfx.load_frames(self.ANIM_NAME) if self.ANIM_NAME else []

    def _scaled_frame(self, frames: List[pygame.Surface], idx: int, scale: float) -> pygame.Surface:
        frame = frames[max(0, min(idx, len(frames) - 1))]
        if scale != 1.0:
            size = (max(8, int(frame.get_width() * scale)), max(8, int(frame.get_height() * scale)))
            frame = pygame.transform.scale(frame, size)
        return frame


class FoozleFireBallSpell(_FoozleSpellBase):
    """Q — projectile fireball that plays the Fire_Ball sprite looping as it travels."""
    ANIM_NAME = "foozle_fire_ball"

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        direction = self.target - self.origin
        if direction.length_squared() <= 1e-6:
            direction = Vector2(1.0 if self.facing >= 0 else -1.0, 0.0)
        self.direction = direction.normalize()
        self.pos = Vector2(self.origin.x, self.origin.y - 22.0)
        self.speed = 780.0 * self.mult("speed_mult", 1.0)
        self.radius = 22.0 + self.mod("radius_bonus", 0.0)
        self.max_range = float(self.definition.get("cast_range", 1000.0))
        self.distance_travelled = 0.0
        self.hit_targets: set[int] = set()
        self.exploded = False

    def build_phases(self) -> Sequence[SpellPhase]:
        return (
            SpellPhase("windup", 0.10),
            SpellPhase("action", 1.40),
            SpellPhase("aftermath", 0.25),
        )

    def on_phase_enter(self, phase: str, runtime: "CombatRuntime", context: "CombatSceneContext") -> None:
        if phase == "windup":
            if context.audio is not None:
                context.audio.play_sfx("cast_projectile", cooldown_ms=22)

    def on_phase_update(self, phase: str, dt: float, runtime: "CombatRuntime", context: "CombatSceneContext") -> None:
        if phase != "action" or self.exploded:
            return
        self.pos += self.direction * self.speed * dt
        self.distance_travelled += self.speed * dt
        if runtime.projectile_hits_obstacle(self.pos, self.radius, context.obstacles):
            self._explode(runtime, context)
            return
        hit_enemy = runtime.first_enemy_hit(self.pos, self.radius, context.enemies, self.hit_targets, context=context)
        if hit_enemy is not None:
            self.hit_targets.add(id(hit_enemy))
            self._explode(runtime, context, primary=hit_enemy)
            return
        if self.distance_travelled >= self.max_range:
            self._explode(runtime, context)

    def _explode(self, runtime: "CombatRuntime", context: "CombatSceneContext", *, primary: Optional[Dict[str, object]] = None) -> None:
        self.exploded = True
        damage = self.base_damage(float(self.definition.get("damage", 44.0)))
        runtime.vfx.spawn_sprite_animation("foozle_explosion", self.pos, duration=0.50, scale=self.SPRITE_SCALE, pixel_art=True)
        if primary is not None:
            runtime.damage_enemy(context, primary, damage, self.pos,
                flash_color=(255, 210, 140), screen_flash_color=(255, 180, 90),
                hit_stop=0.04, shake=4.0)
        splash_radius = 58.0 + self.mod("splash_bonus", 0.0)
        ignore = {id(primary)} if primary is not None else set()
        runtime.damage_enemies_in_radius(context, center=self.pos, radius=splash_radius,
            amount=damage * 0.6, ignore=ignore,
            flash_color=(255, 210, 140), screen_flash_color=(255, 170, 90),
            hit_stop=0.02, shake=2.4)
        self.phase_index = len(self.phases) - 1
        self.phase_elapsed = 0.0

    def draw(self, surface: pygame.Surface, camera: Vector2) -> None:
        if self.exploded or self.current_phase.name != "action":
            return
        # This draw runs without a runtime reference; we rely on VFXManager caching
        # frames the first time the spell fires via a throw-away spawn. We can't
        # call vfx here, so we stash them on the class after first cast via start().
        frames = type(self)._shared_frames  # type: ignore[attr-defined]
        if not frames:
            return
        fps = 18.0
        idx = int(self.total_elapsed * fps) % len(frames)
        frame = frames[idx]
        size = (int(frame.get_width() * self.SPRITE_SCALE), int(frame.get_height() * self.SPRITE_SCALE))
        scaled = pygame.transform.scale(frame, size)
        # Rotate fireball to match travel direction (sprite's default forward is +X).
        angle = -math.degrees(math.atan2(self.direction.y, self.direction.x))
        rotated = pygame.transform.rotate(scaled, angle)
        rect = rotated.get_rect(center=(int(self.pos.x - camera.x), int(self.pos.y - camera.y)))
        surface.blit(rotated, rect)

    def start(self, runtime: "CombatRuntime", context: "CombatSceneContext") -> None:
        type(self)._shared_frames = self._frames(runtime)  # type: ignore[attr-defined]
        super().start(runtime, context)


FoozleFireBallSpell._shared_frames = []  # type: ignore[attr-defined]


class FoozleWaterGeyserSpell(_FoozleSpellBase):
    """W — targeted AoE geyser that erupts at target location with 3 damage pulses."""
    ANIM_NAME = "foozle_water_geyser"
    SPRITE_SCALE = 3.5

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.center = Vector2(self.target)
        self.radius = 82.0 + self.mod("radius_bonus", 0.0)
        self.tick_count = 3
        self.ticks_fired = 0
        self.tick_interval = 0.22

    def build_phases(self) -> Sequence[SpellPhase]:
        return (
            SpellPhase("windup", 0.35),
            SpellPhase("action", 0.72),
            SpellPhase("aftermath", 0.25),
        )

    def on_phase_enter(self, phase: str, runtime: "CombatRuntime", context: "CombatSceneContext") -> None:
        if phase == "windup":
            runtime.vfx.spawn_telegraph(self.center, radius=self.radius, duration=0.40,
                color=(90, 170, 240), outline=(200, 230, 255), fill_alpha=44)
            if context.audio is not None:
                context.audio.play_sfx("cast_ward", cooldown_ms=36)
        elif phase == "action":
            runtime.vfx.spawn_sprite_animation("foozle_water_geyser", self.center,
                duration=0.72, scale=self.SPRITE_SCALE, pixel_art=True, anchor="midbottom")

    def on_phase_update(self, phase: str, dt: float, runtime: "CombatRuntime", context: "CombatSceneContext") -> None:
        if phase != "action" or self.ticks_fired >= self.tick_count:
            return
        target_elapsed = (self.ticks_fired + 1) * self.tick_interval - self.tick_interval
        if self.phase_elapsed < target_elapsed:
            return
        self.ticks_fired += 1
        is_first = self.ticks_fired == 1
        base = float(self.definition.get("damage", 56.0))
        damage = self.base_damage(base * (0.55 if is_first else 0.30)) * self.mult("damage_mult", 1.0)
        shake = 3.8 if is_first else 1.8
        runtime.damage_enemies_in_radius(context, center=self.center, radius=self.radius,
            amount=damage, ignore=set(),
            flash_color=(200, 230, 255), screen_flash_color=(140, 200, 255),
            hit_stop=0.04 if is_first else 0.018, shake=shake)
        if is_first:
            for enemy in runtime.closest_enemies(self.center, context.enemies, radius=self.radius, ignore=set()):
                runtime.knockback_enemy(context, enemy, self.center, 42.0)


class FoozlePortalBlinkSpell(_FoozleSpellBase):
    """E — short-range blink that plays Portal at both the origin and destination."""
    ANIM_NAME = "foozle_portal"
    SPRITE_SCALE = 2.5

    def __init__(self, *args: object, destination: Vector2, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.destination = Vector2(destination)
        self.arrival_radius = 78.0 + self.mod("blink_radius_bonus", 0.0)
        self.knockback = 60.0

    def build_phases(self) -> Sequence[SpellPhase]:
        return (
            SpellPhase("windup", 0.14),
            SpellPhase("action", 0.08),
            SpellPhase("aftermath", 0.42),
        )

    def on_phase_enter(self, phase: str, runtime: "CombatRuntime", context: "CombatSceneContext") -> None:
        if phase == "windup":
            runtime.vfx.spawn_sprite_animation("foozle_portal", self.origin,
                duration=0.55, scale=self.SPRITE_SCALE, pixel_art=True)
            if context.audio is not None:
                context.audio.play_sfx("cast_orb", cooldown_ms=36)
        elif phase == "action":
            runtime.vfx.spawn_sprite_animation("foozle_portal", self.destination,
                duration=0.55, scale=self.SPRITE_SCALE, pixel_art=True)
            for enemy in runtime.closest_enemies(self.destination, context.enemies, radius=self.arrival_radius, ignore=set()):
                enemy_pos = runtime.enemy_position(enemy)
                if enemy_pos is None:
                    continue
                runtime.damage_enemy(context, enemy,
                    self.base_damage(float(self.definition.get("damage", 34.0))),
                    enemy_pos,
                    flash_color=(214, 184, 255), screen_flash_color=(196, 160, 255),
                    hit_stop=0.03, shake=2.8)
                runtime.knockback_enemy(context, enemy, self.destination, self.knockback)


class FoozleExplosionSpell(_FoozleSpellBase):
    """R — ultimate AoE that drops a giant pixel explosion at the target."""
    ANIM_NAME = "foozle_explosion"
    SPRITE_SCALE = 5.0

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.center = Vector2(self.target)
        self.radius = 150.0 + self.mod("radius_bonus", 0.0)

    def build_phases(self) -> Sequence[SpellPhase]:
        return (
            SpellPhase("windup", 0.55),
            SpellPhase("action", 0.75),
            SpellPhase("aftermath", 0.35),
        )

    def on_phase_enter(self, phase: str, runtime: "CombatRuntime", context: "CombatSceneContext") -> None:
        if phase == "windup":
            runtime.vfx.spawn_telegraph(self.center, radius=self.radius, duration=0.55,
                color=(255, 150, 80), outline=(255, 224, 170), fill_alpha=58)
            if context.audio is not None:
                context.audio.play_sfx("cast_nova", cooldown_ms=36)
        elif phase == "action":
            runtime.vfx.spawn_sprite_animation("foozle_explosion", self.center,
                duration=0.65, scale=self.SPRITE_SCALE, pixel_art=True)
            damage = self.base_damage(float(self.definition.get("damage", 96.0))) * self.mult("damage_mult", 1.0)
            runtime.damage_enemies_in_radius(context, center=self.center, radius=self.radius,
                amount=damage, ignore=set(),
                flash_color=(255, 220, 160), screen_flash_color=(255, 170, 90),
                hit_stop=0.06, shake=5.8)
            for enemy in runtime.closest_enemies(self.center, context.enemies, radius=self.radius + 20.0, ignore=set()):
                runtime.knockback_enemy(context, enemy, self.center, 90.0)


class FoozleEarthSpikeSpell(_FoozleSpellBase):
    """Line of rising earth spikes erupting from caster toward target."""
    ANIM_NAME = "foozle_earth_spike"
    SPRITE_SCALE = 2.8

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        offset = self.target - self.origin
        if offset.length_squared() <= 1e-6:
            offset = Vector2(1.0 if self.facing >= 0 else -1.0, 0.0)
        self.direction = offset.normalize()
        self.line_length = min(max(offset.length(), 180.0), 420.0)
        spike_count = 5 + max(0, int(round(self.mod("extra_spikes", 0.0))))
        self.spike_points: List[Vector2] = []
        for i in range(spike_count):
            t = (i + 1) / (spike_count + 1)
            self.spike_points.append(self.origin + self.direction * (self.line_length * t))
        self.spike_index = 0
        self.spike_timer = 0.0
        self.spike_interval = 0.08
        self.damage_done: set[int] = set()

    def build_phases(self) -> Sequence[SpellPhase]:
        return (
            SpellPhase("windup", 0.18),
            SpellPhase("action", 0.70),
            SpellPhase("aftermath", 0.20),
        )

    def on_phase_enter(self, phase: str, runtime: "CombatRuntime", context: "CombatSceneContext") -> None:
        if phase == "windup":
            if context.audio is not None:
                context.audio.play_sfx("cast_ward", cooldown_ms=30)

    def on_phase_update(self, phase: str, dt: float, runtime: "CombatRuntime", context: "CombatSceneContext") -> None:
        if phase != "action":
            return
        self.spike_timer += dt
        while self.spike_timer >= self.spike_interval and self.spike_index < len(self.spike_points):
            self.spike_timer -= self.spike_interval
            pos = self.spike_points[self.spike_index]
            self.spike_index += 1
            runtime.vfx.spawn_sprite_animation("foozle_earth_spike", pos,
                duration=0.42, scale=self.SPRITE_SCALE, pixel_art=True)
            damage = self.base_damage(float(self.definition.get("damage", 48.0)))
            runtime.damage_enemies_in_radius(context, center=pos, radius=54.0,
                amount=damage, ignore=self.damage_done,
                flash_color=(200, 168, 120), screen_flash_color=(170, 130, 80),
                hit_stop=0.03, shake=2.6)
            for enemy in runtime.closest_enemies(pos, context.enemies, radius=54.0, ignore=set()):
                runtime.knockback_enemy(context, enemy, pos, 32.0)


class FoozleMoltenSpearSpell(_FoozleSpellBase):
    """Piercing line projectile of lava. Plays Molten_Spear frames while traveling."""
    ANIM_NAME = "foozle_molten_spear"
    SPRITE_SCALE = 3.0

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        direction = self.target - self.origin
        if direction.length_squared() <= 1e-6:
            direction = Vector2(1.0 if self.facing >= 0 else -1.0, 0.0)
        self.direction = direction.normalize()
        self.pos = Vector2(self.origin.x, self.origin.y - 20.0)
        self.speed = 1050.0 * self.mult("speed_mult", 1.0)
        self.radius = 24.0
        self.max_range = float(self.definition.get("cast_range", 900.0))
        self.distance_travelled = 0.0
        self.hit_targets: set[int] = set()

    def build_phases(self) -> Sequence[SpellPhase]:
        return (
            SpellPhase("windup", 0.10),
            SpellPhase("action", 1.20),
            SpellPhase("aftermath", 0.12),
        )

    def on_phase_enter(self, phase: str, runtime: "CombatRuntime", context: "CombatSceneContext") -> None:
        if phase == "windup":
            if context.audio is not None:
                context.audio.play_sfx("cast_projectile", cooldown_ms=22)

    def on_phase_update(self, phase: str, dt: float, runtime: "CombatRuntime", context: "CombatSceneContext") -> None:
        if phase != "action":
            return
        self.pos += self.direction * self.speed * dt
        self.distance_travelled += self.speed * dt
        if runtime.projectile_hits_obstacle(self.pos, self.radius, context.obstacles):
            runtime.vfx.spawn_sprite_animation("foozle_explosion", self.pos,
                duration=0.36, scale=3.0, pixel_art=True)
            self.phase_index = len(self.phases) - 1
            self.phase_elapsed = 0.0
            return
        damage = self.base_damage(float(self.definition.get("damage", 52.0)))
        for enemy in runtime.closest_enemies(self.pos, context.enemies, radius=self.radius + 24.0, ignore=self.hit_targets):
            enemy_pos = runtime.enemy_position(enemy)
            if enemy_pos is None:
                continue
            if enemy_pos.distance_to(self.pos) <= max(10.0, float(enemy.get("radius", 15.0))) + self.radius:
                self.hit_targets.add(id(enemy))
                runtime.damage_enemy(context, enemy, damage, enemy_pos,
                    flash_color=(255, 200, 120), screen_flash_color=(255, 150, 70),
                    hit_stop=0.035, shake=3.2)
        if self.distance_travelled >= self.max_range:
            runtime.vfx.spawn_sprite_animation("foozle_explosion", self.pos,
                duration=0.36, scale=3.0, pixel_art=True)
            self.phase_index = len(self.phases) - 1
            self.phase_elapsed = 0.0

    def draw(self, surface: pygame.Surface, camera: Vector2) -> None:
        if self.current_phase.name != "action":
            return
        frames = type(self)._shared_frames  # type: ignore[attr-defined]
        if not frames:
            return
        fps = 16.0
        idx = int(self.total_elapsed * fps) % len(frames)
        frame = frames[idx]
        size = (int(frame.get_width() * self.SPRITE_SCALE), int(frame.get_height() * self.SPRITE_SCALE))
        scaled = pygame.transform.scale(frame, size)
        angle = -math.degrees(math.atan2(self.direction.y, self.direction.x))
        rotated = pygame.transform.rotate(scaled, angle)
        rect = rotated.get_rect(center=(int(self.pos.x - camera.x), int(self.pos.y - camera.y)))
        surface.blit(rotated, rect)

    def start(self, runtime: "CombatRuntime", context: "CombatSceneContext") -> None:
        type(self)._shared_frames = self._frames(runtime)  # type: ignore[attr-defined]
        super().start(runtime, context)


FoozleMoltenSpearSpell._shared_frames = []  # type: ignore[attr-defined]


class FoozleRocksSpell(_FoozleSpellBase):
    """Scatter-drop cluster of rock impacts over a zone."""
    ANIM_NAME = "foozle_rocks"
    SPRITE_SCALE = 2.8

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.center = Vector2(self.target)
        self.zone_radius = 140.0 + self.mod("zone_radius_bonus", 0.0)
        count = 5 + max(0, int(round(self.mod("extra_rocks", 0.0))))
        rng = random.Random(f"rocks:{self.origin.x:.1f}:{self.target.x:.1f}:{self.target.y:.1f}")
        self.drop_points: List[Vector2] = []
        for _ in range(count):
            ang = rng.random() * math.tau
            dist = rng.uniform(0.15, 1.0) ** 0.75 * self.zone_radius
            self.drop_points.append(self.center + Vector2(math.cos(ang), math.sin(ang)) * dist)
        self.drop_index = 0
        self.drop_timer = 0.0
        self.drop_interval = 0.14

    def build_phases(self) -> Sequence[SpellPhase]:
        return (
            SpellPhase("windup", 0.25),
            SpellPhase("action", 1.20),
            SpellPhase("aftermath", 0.25),
        )

    def on_phase_enter(self, phase: str, runtime: "CombatRuntime", context: "CombatSceneContext") -> None:
        if phase == "windup":
            runtime.vfx.spawn_telegraph(self.center, radius=self.zone_radius, duration=0.45,
                color=(160, 130, 90), outline=(220, 190, 140), fill_alpha=40)
            if context.audio is not None:
                context.audio.play_sfx("cast_ward", cooldown_ms=36)

    def on_phase_update(self, phase: str, dt: float, runtime: "CombatRuntime", context: "CombatSceneContext") -> None:
        if phase != "action":
            return
        self.drop_timer += dt
        while self.drop_timer >= self.drop_interval and self.drop_index < len(self.drop_points):
            self.drop_timer -= self.drop_interval
            pos = self.drop_points[self.drop_index]
            self.drop_index += 1
            runtime.vfx.spawn_sprite_animation("foozle_rocks", pos,
                duration=0.55, scale=self.SPRITE_SCALE, pixel_art=True)
            damage = self.base_damage(float(self.definition.get("damage", 42.0)))
            runtime.damage_enemies_in_radius(context, center=pos, radius=62.0,
                amount=damage, ignore=set(),
                flash_color=(220, 190, 140), screen_flash_color=(200, 160, 110),
                hit_stop=0.03, shake=3.0)


class FoozleTornadoSpell(_FoozleSpellBase):
    """Moving vortex that drifts from caster toward target, pulling enemies inward and ticking damage."""
    ANIM_NAME = "foozle_tornado"
    SPRITE_SCALE = 3.2

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        direction = self.target - self.origin
        if direction.length_squared() <= 1e-6:
            direction = Vector2(1.0 if self.facing >= 0 else -1.0, 0.0)
        self.direction = direction.normalize()
        self.pos = Vector2(self.origin)
        self.speed = 220.0
        self.radius = 70.0
        self.tick_timer = 0.0
        self.tick_interval = 0.22

    def build_phases(self) -> Sequence[SpellPhase]:
        return (
            SpellPhase("windup", 0.15),
            SpellPhase("action", 2.20),
            SpellPhase("aftermath", 0.25),
        )

    def on_phase_enter(self, phase: str, runtime: "CombatRuntime", context: "CombatSceneContext") -> None:
        if phase == "windup":
            if context.audio is not None:
                context.audio.play_sfx("cast_ward", cooldown_ms=32)

    def on_phase_update(self, phase: str, dt: float, runtime: "CombatRuntime", context: "CombatSceneContext") -> None:
        if phase != "action":
            return
        self.pos += self.direction * self.speed * dt
        self.tick_timer += dt
        while self.tick_timer >= self.tick_interval:
            self.tick_timer -= self.tick_interval
            damage = self.base_damage(float(self.definition.get("damage", 22.0)))
            runtime.damage_enemies_in_radius(context, center=self.pos, radius=self.radius,
                amount=damage, ignore=set(),
                flash_color=(220, 232, 250), screen_flash_color=(180, 200, 230),
                hit_stop=0.012, shake=1.4)
            for enemy in runtime.closest_enemies(self.pos, context.enemies, radius=self.radius + 30.0, ignore=set()):
                runtime.pull_enemy(context, enemy, self.pos, 28.0)

    def draw(self, surface: pygame.Surface, camera: Vector2) -> None:
        if self.current_phase.name != "action":
            return
        frames = type(self)._shared_frames  # type: ignore[attr-defined]
        if not frames:
            return
        fps = 14.0
        idx = int(self.total_elapsed * fps) % len(frames)
        frame = frames[idx]
        size = (int(frame.get_width() * self.SPRITE_SCALE), int(frame.get_height() * self.SPRITE_SCALE))
        scaled = pygame.transform.scale(frame, size)
        rect = scaled.get_rect(center=(int(self.pos.x - camera.x), int(self.pos.y - camera.y)))
        surface.blit(scaled, rect)

    def start(self, runtime: "CombatRuntime", context: "CombatSceneContext") -> None:
        type(self)._shared_frames = self._frames(runtime)  # type: ignore[attr-defined]
        super().start(runtime, context)


FoozleTornadoSpell._shared_frames = []  # type: ignore[attr-defined]


class FoozleWaterWaveSpell(_FoozleSpellBase):
    """Forward sweeping water wave from caster in target direction."""
    ANIM_NAME = "foozle_water"
    SPRITE_SCALE = 3.0

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        direction = self.target - self.origin
        if direction.length_squared() <= 1e-6:
            direction = Vector2(1.0 if self.facing >= 0 else -1.0, 0.0)
        self.direction = direction.normalize()
        self.pos = Vector2(self.origin)
        self.speed = 640.0
        self.radius = 68.0
        self.max_distance = 360.0
        self.distance_travelled = 0.0
        self.damaged: set[int] = set()
        self.trail_timer = 0.0

    def build_phases(self) -> Sequence[SpellPhase]:
        return (
            SpellPhase("windup", 0.12),
            SpellPhase("action", 0.75),
            SpellPhase("aftermath", 0.18),
        )

    def on_phase_enter(self, phase: str, runtime: "CombatRuntime", context: "CombatSceneContext") -> None:
        if phase == "windup":
            if context.audio is not None:
                context.audio.play_sfx("cast_ward", cooldown_ms=30)
        elif phase == "action":
            runtime.vfx.spawn_sprite_animation("foozle_water", self.pos,
                duration=0.55, scale=self.SPRITE_SCALE, pixel_art=True)

    def on_phase_update(self, phase: str, dt: float, runtime: "CombatRuntime", context: "CombatSceneContext") -> None:
        if phase != "action":
            return
        self.pos += self.direction * self.speed * dt
        self.distance_travelled += self.speed * dt
        self.trail_timer += dt
        if self.trail_timer >= 0.10:
            self.trail_timer = 0.0
            runtime.vfx.spawn_sprite_animation("foozle_water", self.pos,
                duration=0.45, scale=self.SPRITE_SCALE, pixel_art=True)
        damage = self.base_damage(float(self.definition.get("damage", 46.0)))
        for enemy in runtime.closest_enemies(self.pos, context.enemies, radius=self.radius, ignore=self.damaged):
            enemy_pos = runtime.enemy_position(enemy)
            if enemy_pos is None:
                continue
            self.damaged.add(id(enemy))
            runtime.damage_enemy(context, enemy, damage, enemy_pos,
                flash_color=(180, 220, 255), screen_flash_color=(140, 190, 240),
                hit_stop=0.03, shake=2.6)
            runtime.knockback_enemy(context, enemy, self.pos, 48.0)
        if self.distance_travelled >= self.max_distance:
            self.phase_index = len(self.phases) - 1
            self.phase_elapsed = 0.0


class FoozleWindSlashSpell(_FoozleSpellBase):
    """Wide forward wind cleave in front of caster."""
    ANIM_NAME = "foozle_wind"
    SPRITE_SCALE = 3.4

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        direction = self.target - self.origin
        if direction.length_squared() <= 1e-6:
            direction = Vector2(1.0 if self.facing >= 0 else -1.0, 0.0)
        self.direction = direction.normalize()
        self.center = self.origin + self.direction * 90.0
        self.radius = 110.0
        self.damage_done = False

    def build_phases(self) -> Sequence[SpellPhase]:
        return (
            SpellPhase("windup", 0.10),
            SpellPhase("action", 0.45),
            SpellPhase("aftermath", 0.15),
        )

    def on_phase_enter(self, phase: str, runtime: "CombatRuntime", context: "CombatSceneContext") -> None:
        if phase == "windup":
            if context.audio is not None:
                context.audio.play_sfx("cast_projectile", cooldown_ms=22)
        elif phase == "action":
            runtime.vfx.spawn_sprite_animation("foozle_wind", self.center,
                duration=0.40, scale=self.SPRITE_SCALE, pixel_art=True)
            if not self.damage_done:
                self.damage_done = True
                damage = self.base_damage(float(self.definition.get("damage", 40.0)))
                for enemy in runtime.closest_enemies(self.center, context.enemies, radius=self.radius, ignore=set()):
                    enemy_pos = runtime.enemy_position(enemy)
                    if enemy_pos is None:
                        continue
                    to_enemy = enemy_pos - self.origin
                    if to_enemy.length_squared() <= 1e-6:
                        continue
                    # Cone check: within +/- 65 degrees of forward direction
                    if self.direction.dot(to_enemy.normalize()) < 0.42:
                        continue
                    runtime.damage_enemy(context, enemy, damage, enemy_pos,
                        flash_color=(220, 240, 230), screen_flash_color=(190, 220, 210),
                        hit_stop=0.025, shake=2.2)
                    runtime.knockback_enemy(context, enemy, self.origin, 70.0)


SPELL_IMPLEMENTATIONS = {
    "mage_arc_bolt": ArcBoltSpell,
    "mage_starfall_sigil": StarfallSigilSpell,
    "mage_phase_blink": PhaseBlinkSpell,
    "mage_astral_cataclysm": AstralCataclysmSpell,
    "mage_foozle_fireball":      FoozleFireBallSpell,
    "mage_foozle_water_geyser":  FoozleWaterGeyserSpell,
    "mage_foozle_portal_blink":  FoozlePortalBlinkSpell,
    "mage_foozle_explosion":     FoozleExplosionSpell,
    "mage_foozle_earth_spike":   FoozleEarthSpikeSpell,
    "mage_foozle_molten_spear":  FoozleMoltenSpearSpell,
    "mage_foozle_rocks":         FoozleRocksSpell,
    "mage_foozle_tornado":       FoozleTornadoSpell,
    "mage_foozle_water":         FoozleWaterWaveSpell,
    "mage_foozle_wind":          FoozleWindSlashSpell,
}
