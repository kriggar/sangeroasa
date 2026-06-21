"""game/combat/ultimates.py — class ultimate abilities (beam, cataclysm, teleport,
storm, summon, dash, transformation) and their shared UltimateContext/UltimateBase."""
import math
import random
import colorsys
from typing import Dict, List, Optional, Tuple, Any, Union, Set

import pygame
from pygame import Vector2

from game.constants import (PLAYER_COLLISION_RADIUS, SCREEN_HEIGHT, SCREEN_WIDTH, WOLF_COLLISION_RADIUS)
from game.utils import clamp, exp_smooth, rotate_vec, color_lerp
from game.vfx import spawn_particle_burst, spawn_blood_splatter, spawn_damage_number, spell_vfx_palette
from game.nav import is_walkable, nearest_walkable
from game.systems.core import (ParticleEmitter, StatusEffect, StatusEffectSystem, ScreenEffectController,
    draw_point_light, damage_wolf_entity, point_segment_distance_sq, circle_hits_segment)


class UltimateContext:
    def __init__(
        self,
        player_get: Any,
        player_set: Any,
        facing_get: Any,
        wolves: List[Dict[str, object]],
        walk_bounds: pygame.Rect,
        obstacles: List[pygame.Rect],
        status_effects: StatusEffectSystem,
        screen_effects: ScreenEffectController,
        damage_numbers: List[Dict[str, object]],
        spell_effects: List[Dict[str, object]],
        set_status: Any,
    ) -> None:
        self._player_get = player_get
        self._player_set = player_set
        self._facing_get = facing_get
        self.wolves = wolves
        self.walk_bounds = walk_bounds
        self.obstacles = obstacles
        self.status_effects = status_effects
        self.screen_effects = screen_effects
        self.damage_numbers = damage_numbers
        self.spell_effects = spell_effects
        self._set_status = set_status

    def player_pos(self) -> Vector2:
        value = self._player_get()
        if isinstance(value, Vector2):
            return Vector2(value)
        return Vector2(0.0, 0.0)

    def player_facing(self) -> int:
        try:
            return 1 if int(self._facing_get()) >= 0 else -1
        except (TypeError, ValueError):
            return 1

    def move_player(self, pos: Vector2) -> None:
        self._player_set(Vector2(pos))

    def status(self, text: str, duration: float = 1.2) -> None:
        self._set_status(text, duration)

    def living_wolves(self) -> List[Dict[str, object]]:
        return [wolf for wolf in self.wolves if float(wolf.get("hp", 0.0)) > 0.0 and isinstance(wolf.get("pos"), Vector2)]

    def find_wolf_by_id(self, wolf_id: int) -> Optional[Dict[str, object]]:
        for wolf in self.wolves:
            if id(wolf) == wolf_id and float(wolf.get("hp", 0.0)) > 0.0:
                return wolf
        return None

    def nearest_wolf(
        self,
        origin: Vector2,
        max_dist: float = 99999.0,
        exclude: Optional[Set[int]] = None,
    ) -> Optional[Dict[str, object]]:
        best: Optional[Dict[str, object]] = None
        best_dist = max(0.0, float(max_dist))
        excluded = exclude if isinstance(exclude, set) else set()
        for wolf in self.wolves:
            if float(wolf.get("hp", 0.0)) <= 0.0 or id(wolf) in excluded:
                continue
            pos_raw = wolf.get("pos")
            if not isinstance(pos_raw, Vector2):
                continue
            dist = Vector2(pos_raw).distance_to(origin)
            if dist > best_dist:
                continue
            best_dist = dist
            best = wolf
        return best

    def wolves_in_radius(self, origin: Vector2, radius: float) -> List[Dict[str, object]]:
        rr = max(0.0, float(radius))
        rr_sq = rr * rr
        found: List[Dict[str, object]] = []
        for wolf in self.wolves:
            if float(wolf.get("hp", 0.0)) <= 0.0:
                continue
            pos_raw = wolf.get("pos")
            if not isinstance(pos_raw, Vector2):
                continue
            if Vector2(pos_raw).distance_squared_to(origin) <= rr_sq:
                found.append(wolf)
        return found

    def damage_wolf(
        self,
        wolf: Dict[str, object],
        amount: float,
        hit_pos: Optional[Vector2] = None,
        gore: float = 1.0,
    ) -> float:
        amount = float(amount)
        if isinstance(self.status_effects, StatusEffectSystem):
            scorched = self.status_effects.consume_effect(self.status_effects.wolf_key(wolf), "scorched")
            if isinstance(scorched, StatusEffect):
                amount *= 1.0 + max(0.0, scorched.potency)
                if isinstance(hit_pos, Vector2):
                    spawn_particle_burst(
                        self.spell_effects,
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
        dealt = damage_wolf_entity(wolf, amount, self.damage_numbers, hit_pos)
        if dealt > 0.0:
            wolf["chasing"] = True
            wolf["aggro_timer"] = max(float(wolf.get("aggro_timer", 0.0)), 1.2)
            if gore > 0.0:
                pos = hit_pos
                if not isinstance(pos, Vector2):
                    pos_raw = wolf.get("pos")
                    if isinstance(pos_raw, Vector2):
                        pos = Vector2(pos_raw)
                if isinstance(pos, Vector2):
                    spawn_blood_splatter(self.spell_effects, pos, intensity=max(0.3, gore))
        return dealt

    def nearest_walkable(self, pos: Vector2, radius: float = PLAYER_COLLISION_RADIUS) -> Vector2:
        return nearest_walkable(Vector2(pos), self.walk_bounds, self.obstacles, float(radius))

    def is_walkable(self, pos: Vector2, radius: float = PLAYER_COLLISION_RADIUS) -> bool:
        return is_walkable(Vector2(pos), self.walk_bounds, self.obstacles, float(radius))

    def push_wolf(self, wolf: Dict[str, object], direction: Vector2, distance: float) -> None:
        pos_raw = wolf.get("pos")
        if not isinstance(pos_raw, Vector2):
            return
        if direction.length_squared() <= 1e-6 or distance <= 1.0:
            return
        target = Vector2(pos_raw) + direction.normalize() * distance
        radius = max(8.0, float(wolf.get("radius", WOLF_COLLISION_RADIUS)))
        wolf["pos"] = nearest_walkable(target, self.walk_bounds, self.obstacles, radius)


class UltimateBase:
    def __init__(
        self,
        spell: Dict[str, object],
        caster_pos: Vector2,
        target_pos: Vector2,
        facing: int,
        bonus_power: float,
        spell_mods: Optional[Dict[str, float]] = None,
        class_damage_mult: float = 1.0,
    ) -> None:
        self.spell = dict(spell)
        self.spell_id = str(spell.get("id", "ultimate"))
        self.name = str(spell.get("name", "Ultimate"))
        self.caster_pos = Vector2(caster_pos)
        self.target_pos = Vector2(target_pos)
        self.facing = 1 if int(facing) >= 0 else -1
        self.bonus_power = float(bonus_power)
        self.mods = dict(spell_mods or {})
        self.damage_scale = max(0.1, float(self.mods.get("damage_mult", 1.0))) * max(0.1, float(class_damage_mult))
        self.radius_scale = max(0.1, float(self.mods.get("radius_mult", 1.0))) * max(0.1, float(self.mods.get("max_radius_mult", 1.0)))
        self.duration_scale = max(0.1, float(self.mods.get("duration_mult", 1.0)))
        self.interval_scale = max(0.2, float(self.mods.get("interval_mult", 1.0)))
        self.base_damage = (float(spell.get("damage", 18.0)) + self.bonus_power * 5.5 + float(self.mods.get("bonus_damage", 0.0))) * self.damage_scale
        self.core_color, self.accent_color, self.shadow_color = spell_vfx_palette(
            self.spell_id,
            spell.get("colors") if isinstance(spell.get("colors"), dict) else {},
        )
        self.emitters: List[ParticleEmitter] = []
        self.elapsed = 0.0
        self.finished = False
        self.movement_mult = 1.0

    def add_emitter(self) -> ParticleEmitter:
        emitter = ParticleEmitter()
        self.emitters.append(emitter)
        return emitter

    def start(self, ctx: UltimateContext) -> None:
        pass

    def update(self, dt: float, ctx: UltimateContext) -> None:
        self.elapsed += max(0.0, dt)
        for emitter in self.emitters:
            emitter.update(dt)

    def draw(self, surface: pygame.Surface, camera: Vector2) -> None:
        for emitter in self.emitters:
            emitter.draw(surface, camera)

    def is_alive(self) -> bool:
        return (not self.finished) or any(emitter.alive() for emitter in self.emitters)


class MageBeamUltimate(UltimateBase):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.windup = 0.34
        self.active_time = 0.52 * self.duration_scale
        self.fade_time = 0.24
        self.length = clamp(self.caster_pos.distance_to(self.target_pos), 320.0, 760.0)
        self.width = 34.0 * self.radius_scale
        self.fired = False
        self.hit_ids: Set[int] = set()
        self.emitter = self.add_emitter()

    def _origin_and_end(self, ctx: UltimateContext) -> Tuple[Vector2, Vector2, Vector2]:
        origin = ctx.player_pos() + Vector2(0.0, -26.0)
        aim = self.target_pos - origin
        if aim.length_squared() <= 1e-5:
            aim = Vector2(float(self.facing), 0.0)
        direction = aim.normalize()
        return origin, origin + direction * self.length, direction

    def update(self, dt: float, ctx: UltimateContext) -> None:
        super().update(dt, ctx)
        self.caster_pos = ctx.player_pos() + Vector2(0.0, -26.0)
        origin, end, direction = self._origin_and_end(ctx)
        self.target_pos = Vector2(end)
        if self.elapsed < self.windup:
            if random.random() < 0.8:
                self.emitter.burst(
                    origin + direction * random.uniform(10.0, 40.0),
                    self.core_color,
                    self.accent_color,
                    count=2,
                    speed_min=22.0,
                    speed_max=72.0,
                    life_min=0.12,
                    life_max=0.28,
                    size_start=2.8,
                    size_end=0.5,
                    spread=0.8,
                    direction=direction,
                    gravity=-16.0,
                    drag=1.4,
                    shape="spark",
                )
            return
        if not self.fired:
            self.fired = True
            ctx.screen_effects.flash((236, 218, 178), alpha=92, duration=0.12)
            self.emitter.burst(
                origin,
                self.core_color,
                self.accent_color,
                count=24,
                speed_min=180.0,
                speed_max=360.0,
                life_min=0.16,
                life_max=0.36,
                size_start=4.6,
                size_end=0.6,
                spread=0.42,
                direction=direction,
                drag=1.6,
                shape="spark",
            )
        if self.elapsed <= self.windup + self.active_time:
            beam_radius = self.width * 0.5 + 22.0
            for wolf in ctx.living_wolves():
                wolf_id = id(wolf)
                if wolf_id in self.hit_ids:
                    continue
                pos_raw = wolf.get("pos")
                if not isinstance(pos_raw, Vector2):
                    continue
                if not circle_hits_segment(Vector2(pos_raw), beam_radius, origin, end):
                    continue
                dealt = ctx.damage_wolf(wolf, self.base_damage * 2.5, Vector2(pos_raw), gore=1.35)
                if dealt <= 0.0:
                    continue
                self.hit_ids.add(wolf_id)
                ctx.status_effects.add_effect(
                    ctx.status_effects.wolf_key(wolf),
                    StatusEffect("burn", 3.2, potency=max(4.0, self.base_damage * 0.18), tick_interval=0.55, color=self.accent_color),
                )
                self.emitter.burst(
                    Vector2(pos_raw),
                    self.accent_color,
                    (255, 245, 220),
                    count=12,
                    speed_min=90.0,
                    speed_max=220.0,
                    life_min=0.12,
                    life_max=0.30,
                    size_start=3.6,
                    size_end=0.5,
                    spread=math.tau,
                    gravity=-20.0,
                    drag=1.2,
                    shape="spark",
                )
            for _ in range(3):
                spark_pos = origin.lerp(end, random.uniform(0.15, 1.0))
                self.emitter.burst(
                    spark_pos,
                    self.core_color,
                    self.accent_color,
                    count=2,
                    speed_min=30.0,
                    speed_max=86.0,
                    life_min=0.10,
                    life_max=0.24,
                    size_start=2.4,
                    size_end=0.4,
                    spread=math.tau,
                    gravity=-10.0,
                    drag=1.1,
                    shape="spark",
                )
        elif self.elapsed >= self.windup + self.active_time + self.fade_time:
            self.finished = True

    def draw(self, surface: pygame.Surface, camera: Vector2) -> None:
        if self.finished:
            super().draw(surface, camera)
            return
        draw_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        sx1 = int(self.caster_pos.x - camera.x)
        sy1 = int(self.caster_pos.y - camera.y)
        sx2 = int(self.target_pos.x - camera.x)
        sy2 = int(self.target_pos.y - camera.y)
        if self.elapsed < self.windup:
            ratio = clamp(self.elapsed / max(0.001, self.windup), 0.0, 1.0)
            width = max(2, int(4 + 8 * ratio))
            pygame.draw.line(draw_surface, (*self.accent_color, 90), (sx1, sy1), (sx2, sy2), width)
            pygame.draw.circle(draw_surface, (*self.accent_color, 110), (sx2, sy2), int(18 + 16 * ratio), 2)
        else:
            fade = 1.0
            if self.elapsed > self.windup + self.active_time:
                tail = self.elapsed - (self.windup + self.active_time)
                fade = clamp(1.0 - tail / max(0.001, self.fade_time), 0.0, 1.0)
            outer_w = max(6, int(self.width * fade))
            inner_w = max(2, int(self.width * 0.44 * fade))
            pygame.draw.line(draw_surface, (*self.shadow_color, int(150 * fade)), (sx1, sy1), (sx2, sy2), outer_w + 6)
            pygame.draw.line(draw_surface, (*self.accent_color, int(220 * fade)), (sx1, sy1), (sx2, sy2), outer_w)
            pygame.draw.line(draw_surface, (*self.core_color, int(255 * fade)), (sx1, sy1), (sx2, sy2), inner_w)
            pygame.draw.circle(draw_surface, (*self.accent_color, int(160 * fade)), (sx2, sy2), max(12, int(self.width * 0.65 * fade)))
        surface.blit(draw_surface, (0, 0))
        super().draw(surface, camera)


class MageCataclysmUltimate(UltimateBase):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.windup = 0.35
        self.channel_time = 5.0 * self.duration_scale
        self.fade_time = 0.35
        self.start_radius = 70.0 * self.radius_scale
        self.end_radius = 220.0 * self.radius_scale
        self.orbit_speed = 3.1
        self.tick_interval = max(0.08, 0.22 * self.interval_scale)
        self.tick_timer = 0.0
        self.movement_mult = 0.55
        self.elements = ["wind", "fire", "ice", "earth"]
        self.element_emitters: Dict[str, ParticleEmitter] = {name: self.add_emitter() for name in self.elements}
        self.core_emitter = self.add_emitter()
        self.element_colors = {
            "wind": ((204, 234, 255), (120, 176, 214)),
            "fire": ((255, 182, 108), (255, 120, 62)),
            "ice": ((176, 224, 255), (118, 176, 214)),
            "earth": ((168, 136, 96), (94, 76, 54)),
        }
        self.storm_radius = max(70.0, self.end_radius * 0.45)
        self.pull_strength = 26.0 * self.radius_scale

    def start(self, ctx: UltimateContext) -> None:
        ctx.screen_effects.flash((24, 30, 42), alpha=120, duration=0.30, additive=False)
        ctx.status("Elemental Cataclysm unleashed.", 1.4)
        self.core_emitter.burst(
            ctx.player_pos() + Vector2(0.0, -18.0),
            (180, 210, 240),
            (120, 150, 200),
            count=16,
            speed_min=60.0,
            speed_max=160.0,
            life_min=0.18,
            life_max=0.42,
            size_start=3.8,
            size_end=0.6,
            spread=math.tau,
            gravity=-18.0,
            drag=1.2,
            shape="spark",
        )

    def _element_positions(self) -> List[Tuple[str, Vector2]]:
        if self.elapsed <= self.windup:
            progress = 0.0
        else:
            progress = clamp((self.elapsed - self.windup) / max(0.001, self.channel_time), 0.0, 1.0)
        radius = self.start_radius + (self.end_radius - self.start_radius) * progress
        base_angle = self.elapsed * self.orbit_speed
        positions: List[Tuple[str, Vector2]] = []
        count = max(1, len(self.elements))
        for idx, element in enumerate(self.elements):
            ang = base_angle + idx * (math.tau / float(count))
            orbit = Vector2(math.cos(ang), math.sin(ang) * 0.65)
            positions.append((element, self.caster_pos + orbit * radius))
        return positions

    def update(self, dt: float, ctx: UltimateContext) -> None:
        super().update(dt, ctx)
        self.caster_pos = ctx.player_pos() + Vector2(0.0, -18.0)
        if self.elapsed < self.windup:
            if random.random() < 0.6:
                self.core_emitter.burst(
                    self.caster_pos,
                    (214, 236, 255),
                    (126, 160, 210),
                    count=2,
                    speed_min=20.0,
                    speed_max=70.0,
                    life_min=0.12,
                    life_max=0.32,
                    size_start=2.6,
                    size_end=0.4,
                    spread=math.tau,
                    gravity=-16.0,
                    drag=1.4,
                    shape="spark",
                )
            return
        if self.elapsed >= self.windup + self.channel_time + self.fade_time:
            self.finished = True
            return

        positions = self._element_positions()
        swirl_angle = pygame.time.get_ticks() * 0.003
        ring_pos = self.caster_pos + Vector2(math.cos(swirl_angle), math.sin(swirl_angle) * 0.6) * 26.0
        self.core_emitter.burst(
            ring_pos,
            (210, 232, 255),
            (132, 168, 212),
            count=1,
            speed_min=18.0,
            speed_max=60.0,
            life_min=0.14,
            life_max=0.34,
            size_start=2.8,
            size_end=0.4,
            spread=math.tau,
            gravity=-12.0,
            drag=1.5,
            shape="spark",
        )

        for element, pos in positions:
            emitter = self.element_emitters[element]
            core_col, accent_col = self.element_colors[element]
            emitter.burst(
                pos,
                core_col,
                accent_col,
                count=2,
                speed_min=24.0,
                speed_max=90.0,
                life_min=0.16,
                life_max=0.44,
                size_start=3.4,
                size_end=0.6,
                spread=math.tau,
                gravity=-16.0,
                drag=1.3,
            )
            if element == "fire" and random.random() < 0.35:
                meteor_dir = Vector2(1.0, 1.0).normalize()
                start = pos + Vector2(-90.0, -90.0)
                emitter.burst(
                    start,
                    core_col,
                    accent_col,
                    count=2,
                    speed_min=220.0,
                    speed_max=360.0,
                    life_min=0.10,
                    life_max=0.22,
                    size_start=2.6,
                    size_end=0.4,
                    spread=0.32,
                    direction=meteor_dir,
                    gravity=80.0,
                    drag=2.2,
                    shape="spark",
                    streak=18.0,
                )

        self.tick_timer -= dt
        if self.tick_timer <= 0.0:
            self.tick_timer += self.tick_interval
            storm_radius = self.storm_radius
            damage_per_hit = self.base_damage * 0.45
            for element, pos in positions:
                for wolf in ctx.living_wolves():
                    wpos_raw = wolf.get("pos")
                    if not isinstance(wpos_raw, Vector2):
                        continue
                    if Vector2(wpos_raw).distance_squared_to(pos) > storm_radius * storm_radius:
                        continue
                    hit_pos = Vector2(wpos_raw.x, wpos_raw.y)
                    dealt = ctx.damage_wolf(wolf, damage_per_hit, hit_pos, gore=1.1)
                    if dealt <= 0.0:
                        continue
                    if element == "fire":
                        ctx.status_effects.add_effect(
                            ctx.status_effects.wolf_key(wolf),
                            StatusEffect("burn", 2.4, potency=max(3.0, self.base_damage * 0.14), tick_interval=0.55, color=(255, 154, 84)),
                        )
                    elif element == "ice":
                        ctx.status_effects.add_effect(
                            ctx.status_effects.wolf_key(wolf),
                            StatusEffect("freeze", 0.65, potency=1.0, color=(178, 224, 255)),
                        )
                    elif element == "wind":
                        pull_dir = self.caster_pos - hit_pos
                        if pull_dir.length_squared() > 1e-6:
                            ctx.push_wolf(wolf, pull_dir, self.pull_strength)
                    elif element == "earth":
                        ctx.status_effects.add_effect(
                            ctx.status_effects.wolf_key(wolf),
                            StatusEffect("stun", 0.45, potency=1.0, color=(168, 140, 102)),
                        )

    def draw(self, surface: pygame.Surface, camera: Vector2) -> None:
        if self.finished:
            super().draw(surface, camera)
            return
        if self.elapsed < self.windup:
            fade = clamp(self.elapsed / max(0.001, self.windup), 0.0, 1.0)
        elif self.elapsed > self.windup + self.channel_time:
            tail = self.elapsed - (self.windup + self.channel_time)
            fade = clamp(1.0 - tail / max(0.001, self.fade_time), 0.0, 1.0)
        else:
            fade = 1.0

        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((8, 10, 16, int(120 * fade)))
        surface.blit(overlay, (0, 0))

        now_ult = pygame.time.get_ticks() * 0.001
        cx_ult = int(self.caster_pos.x - camera.x)
        cy_ult = int(self.caster_pos.y - camera.y)

        # Outer storm vortex ring — swirling energy connecting the elements
        vortex_r = max(40, int(self.storm_radius * 1.3))
        vortex_segs = 32
        for vi in range(vortex_segs):
            v_ang = vi * (math.tau / vortex_segs) + now_ult * 2.5
            v_ang2 = (vi + 1) * (math.tau / vortex_segs) + now_ult * 2.5
            wobble = math.sin(now_ult * 6.0 + vi * 0.8) * 8.0
            r1 = vortex_r + wobble
            r2 = vortex_r + math.sin(now_ult * 6.0 + (vi + 1) * 0.8) * 8.0
            vx1 = cx_ult + int(math.cos(v_ang) * r1)
            vy1 = cy_ult + int(math.sin(v_ang) * r1 * 0.65)
            vx2 = cx_ult + int(math.cos(v_ang2) * r2)
            vy2 = cy_ult + int(math.sin(v_ang2) * r2 * 0.65)
            # Color cycles through elements
            elem_idx = int((v_ang / math.tau * 4) % 4)
            elem_name = self.elements[elem_idx]
            vc, _ = self.element_colors[elem_name]
            v_alpha = max(16, int(60 * fade))
            pygame.draw.line(surface, (vc[0], vc[1], vc[2], v_alpha), (vx1, vy1), (vx2, vy2), 2)

        # Ground scorch/frost ring beneath the storm
        ground_r = max(30, int(vortex_r * 0.7))
        pygame.gfxdraw.filled_circle(surface, cx_ult, cy_ult, ground_r, (40, 30, 50, int(50 * fade)))
        pygame.gfxdraw.aacircle(surface, cx_ult, cy_ult, ground_r, (120, 100, 160, int(80 * fade)))

        positions = self._element_positions()
        for element, pos in positions:
            esx = int(pos.x - camera.x)
            esy = int(pos.y - camera.y)
            core_col, accent_col = self.element_colors[element]

            # Element-specific visuals
            if element == "fire":
                # Flickering flame orb
                flame_r = 18 + int(4 * math.sin(now_ult * 16.0))
                pygame.gfxdraw.filled_circle(surface, esx, esy, flame_r + 8, (255, 80, 20, int(40 * fade)))
                pygame.gfxdraw.filled_circle(surface, esx, esy, flame_r + 4, (255, 140, 40, int(80 * fade)))
                pygame.gfxdraw.filled_circle(surface, esx, esy, flame_r, (core_col[0], core_col[1], core_col[2], int(200 * fade)))
                pygame.gfxdraw.filled_circle(surface, esx, esy - 2, max(3, flame_r - 6), (255, 230, 180, int(220 * fade)))
                # Rising heat wisps
                for wi in range(3):
                    wy = esy - 10 - int((now_ult * 40.0 + wi * 15) % 30)
                    wx = esx + int(math.sin(now_ult * 8.0 + wi * 2.0) * 5)
                    pygame.gfxdraw.filled_circle(surface, wx, wy, 2, (255, 180, 80, int(60 * fade)))
            elif element == "ice":
                # Frozen crystal orb with rotating shards
                ice_r = 16 + int(3 * math.sin(now_ult * 8.0))
                pygame.gfxdraw.filled_circle(surface, esx, esy, ice_r + 8, (80, 140, 220, int(35 * fade)))
                pygame.gfxdraw.filled_circle(surface, esx, esy, ice_r + 3, (140, 200, 255, int(90 * fade)))
                pygame.gfxdraw.filled_circle(surface, esx, esy, ice_r, (core_col[0], core_col[1], core_col[2], int(200 * fade)))
                pygame.gfxdraw.filled_circle(surface, esx - 2, esy - 2, max(2, ice_r // 2), (240, 250, 255, int(200 * fade)))
                # Orbiting ice shards
                for si in range(4):
                    s_ang = now_ult * 4.0 + si * (math.tau / 4)
                    s_x = esx + int(math.cos(s_ang) * (ice_r + 6))
                    s_y = esy + int(math.sin(s_ang) * (ice_r + 6))
                    pygame.draw.line(surface, (200, 235, 255, int(140 * fade)), (s_x - 2, s_y - 3), (s_x + 2, s_y + 3), 2)
            elif element == "wind":
                # Swirling vortex funnel
                wind_r = 16 + int(3 * math.sin(now_ult * 10.0))
                pygame.gfxdraw.filled_circle(surface, esx, esy, wind_r + 10, (140, 190, 230, int(25 * fade)))
                pygame.gfxdraw.filled_circle(surface, esx, esy, wind_r + 4, (core_col[0], core_col[1], core_col[2], int(70 * fade)))
                pygame.gfxdraw.aacircle(surface, esx, esy, wind_r, (core_col[0], core_col[1], core_col[2], int(180 * fade)))
                # Spinning wind arcs
                for ai in range(3):
                    a_ang = now_ult * 7.0 + ai * (math.tau / 3)
                    a_r = wind_r - 2
                    arc_rect = pygame.Rect(esx - a_r, esy - a_r, a_r * 2, a_r * 2)
                    pygame.draw.arc(surface, (220, 240, 255, int(120 * fade)), arc_rect, a_ang, a_ang + 1.2, 2)
            elif element == "earth":
                # Rocky boulder orb with floating debris
                earth_r = 16 + int(2 * math.sin(now_ult * 5.0))
                pygame.gfxdraw.filled_circle(surface, esx, esy, earth_r + 6, (100, 80, 50, int(50 * fade)))
                pygame.gfxdraw.filled_circle(surface, esx, esy, earth_r + 2, (core_col[0], core_col[1], core_col[2], int(180 * fade)))
                pygame.gfxdraw.filled_circle(surface, esx, esy, earth_r, (accent_col[0], accent_col[1], accent_col[2], int(210 * fade)))
                # Stone texture lines
                for li in range(3):
                    lx = esx - earth_r + 4 + li * (earth_r * 2 // 4)
                    pygame.draw.line(surface, (80, 60, 40, int(100 * fade)), (lx, esy - earth_r // 2), (lx + 2, esy + earth_r // 2), 1)
                # Floating rock fragments
                for fi in range(3):
                    f_ang = now_ult * 2.5 + fi * 2.1
                    f_r = earth_r + 8 + int(math.sin(now_ult * 3.0 + fi) * 4)
                    fx_p = esx + int(math.cos(f_ang) * f_r)
                    fy_p = esy + int(math.sin(f_ang) * f_r) - int(math.sin(now_ult * 4.0 + fi * 1.3) * 3)
                    pygame.draw.rect(surface, (accent_col[0], accent_col[1], accent_col[2], int(140 * fade)),
                        pygame.Rect(fx_p - 2, fy_p - 2, 4, 3))

            # Lightning arc connecting elements to caster
            arc_alpha = max(12, int(40 * fade * (0.5 + 0.5 * math.sin(now_ult * 12.0 + hash(element) * 0.01))))
            arc_steps = 5
            prev_pt = (cx_ult, cy_ult)
            for ai in range(arc_steps + 1):
                a_frac = ai / arc_steps
                ax = int(cx_ult + (esx - cx_ult) * a_frac)
                ay = int(cy_ult + (esy - cy_ult) * a_frac)
                if 0 < ai < arc_steps:
                    ax += int(math.sin(now_ult * 20.0 + ai * 3.0 + hash(element) * 0.01) * 8)
                    ay += int(math.cos(now_ult * 18.0 + ai * 2.7 + hash(element) * 0.01) * 6)
                pygame.draw.line(surface, (accent_col[0], accent_col[1], accent_col[2], arc_alpha), prev_pt, (ax, ay), 1)
                prev_pt = (ax, ay)

        # Central caster aura — pulsing energy core
        aura_pulse = 0.6 + 0.4 * math.sin(now_ult * 6.0)
        aura_r = int(22 * aura_pulse)
        pygame.gfxdraw.filled_circle(surface, cx_ult, cy_ult, aura_r + 8, (180, 200, 240, int(30 * fade)))
        pygame.gfxdraw.filled_circle(surface, cx_ult, cy_ult, aura_r, (220, 230, 255, int(80 * fade)))
        pygame.gfxdraw.aacircle(surface, cx_ult, cy_ult, aura_r + 4, (200, 220, 255, int(100 * fade)))

        super().draw(surface, camera)


class RogueTeleportUltimate(UltimateBase):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.route_ids: List[int] = []
        self.windup = 0.12
        self.strike_interval = max(0.08, 0.16 * self.interval_scale)
        self.next_strike_time = self.windup
        self.strike_index = 0
        self.final_burst_done = False
        self.smoke = self.add_emitter()

    def start(self, ctx: UltimateContext) -> None:
        candidates = [
            wolf for wolf in ctx.living_wolves()
            if isinstance(wolf.get("pos"), Vector2)
            and Vector2(wolf["pos"]).distance_to(self.target_pos) <= 520.0
        ]
        if not candidates:
            candidates = [
                wolf for wolf in ctx.living_wolves()
                if isinstance(wolf.get("pos"), Vector2)
                and Vector2(wolf["pos"]).distance_to(ctx.player_pos()) <= 420.0
            ]
        max_hits = max(2, 4 + int(round(float(self.mods.get("projectile_count_bonus", 0.0)))))
        chosen: List[Dict[str, object]] = []
        pivot = Vector2(self.target_pos)
        while candidates and len(chosen) < max_hits:
            nxt = min(candidates, key=lambda wolf: Vector2(wolf["pos"]).distance_to(pivot))
            candidates.remove(nxt)
            chosen.append(nxt)
            pivot = Vector2(nxt["pos"])
        self.route_ids = [id(wolf) for wolf in chosen]
        self.smoke.burst(
            ctx.player_pos() + Vector2(0.0, -10.0),
            self.accent_color,
            self.shadow_color,
            count=22,
            speed_min=80.0,
            speed_max=190.0,
            life_min=0.18,
            life_max=0.44,
            size_start=4.6,
            size_end=0.7,
            spread=math.tau,
            gravity=-24.0,
            drag=1.2,
        )

    def update(self, dt: float, ctx: UltimateContext) -> None:
        super().update(dt, ctx)
        self.caster_pos = ctx.player_pos() + Vector2(0.0, -8.0)
        if self.strike_index < len(self.route_ids) and self.elapsed >= self.next_strike_time:
            target = ctx.find_wolf_by_id(self.route_ids[self.strike_index])
            self.next_strike_time += self.strike_interval
            self.strike_index += 1
            if isinstance(target, dict):
                start_pos = ctx.player_pos()
                pos_raw = target.get("pos")
                if isinstance(pos_raw, Vector2):
                    target_pos = Vector2(pos_raw)
                    away = start_pos - target_pos
                    if away.length_squared() <= 1e-6:
                        away = Vector2(float(-self.facing), 0.0)
                    blink_pos = ctx.nearest_walkable(target_pos + away.normalize() * 54.0)
                    ctx.move_player(blink_pos)
                    self.caster_pos = Vector2(blink_pos.x, blink_pos.y - 8.0)
                    dealt = ctx.damage_wolf(target, self.base_damage * 1.55, target_pos, gore=1.45)
                    if dealt > 0.0:
                        ctx.status_effects.add_effect(ctx.status_effects.wolf_key(target), StatusEffect("stun", 0.55, potency=1.0, color=self.shadow_color))
                    slash_dir = target_pos - blink_pos
                    if slash_dir.length_squared() <= 1e-6:
                        slash_dir = Vector2(float(self.facing), 0.0)
                    self.smoke.burst(
                        start_pos + Vector2(0.0, -8.0),
                        self.shadow_color,
                        self.accent_color,
                        count=12,
                        speed_min=70.0,
                        speed_max=180.0,
                        life_min=0.12,
                        life_max=0.32,
                        size_start=3.8,
                        size_end=0.5,
                        spread=math.tau,
                        gravity=-16.0,
                        drag=1.4,
                    )
                    self.smoke.burst(
                        target_pos + Vector2(0.0, -8.0),
                        (242, 236, 255),
                        self.accent_color,
                        count=14,
                        speed_min=120.0,
                        speed_max=280.0,
                        life_min=0.10,
                        life_max=0.24,
                        size_start=3.6,
                        size_end=0.5,
                        spread=0.65,
                        direction=slash_dir,
                        drag=1.8,
                        shape="spark",
                    )
                    ctx.screen_effects.flash((90, 74, 118), alpha=32, duration=0.08)
        if not self.final_burst_done and self.strike_index >= len(self.route_ids) and self.elapsed >= self.next_strike_time:
            self.final_burst_done = True
            burst_pos = ctx.player_pos() + Vector2(0.0, -8.0)
            hit_any = False
            for wolf in ctx.wolves_in_radius(ctx.player_pos(), 116.0 * self.radius_scale):
                pos_raw = wolf.get("pos")
                if not isinstance(pos_raw, Vector2):
                    continue
                dealt = ctx.damage_wolf(wolf, self.base_damage * 0.9, Vector2(pos_raw), gore=1.0)
                if dealt <= 0.0:
                    continue
                hit_any = True
                ctx.status_effects.add_effect(ctx.status_effects.wolf_key(wolf), StatusEffect("slow", 1.8, potency=0.22, color=self.accent_color))
            self.smoke.burst(
                burst_pos,
                (230, 220, 255),
                self.accent_color,
                count=24,
                speed_min=140.0,
                speed_max=320.0,
                life_min=0.14,
                life_max=0.34,
                size_start=4.4,
                size_end=0.6,
                spread=math.tau,
                gravity=-18.0,
                drag=1.3,
                shape="spark",
            )
            if hit_any:
                ctx.screen_effects.flash((128, 98, 180), alpha=48, duration=0.10)
        if self.final_burst_done and self.elapsed >= self.next_strike_time + 0.18:
            self.finished = True

    def draw(self, surface: pygame.Surface, camera: Vector2) -> None:
        if self.finished:
            super().draw(surface, camera)
            return
        if self.elapsed < self.windup:
            sx = int(self.caster_pos.x - camera.x)
            sy = int(self.caster_pos.y - camera.y)
            ring = max(10, int(14 + 22 * clamp(self.elapsed / max(0.001, self.windup), 0.0, 1.0)))
            pygame.gfxdraw.aacircle(surface, sx, sy, ring, (*self.accent_color, 148))
            pygame.gfxdraw.aacircle(surface, sx, sy, max(6, ring - 8), (*self.shadow_color, 112))
        super().draw(surface, camera)


class RangerStormUltimate(UltimateBase):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.center = Vector2(self.target_pos)
        self.radius = 148.0 * self.radius_scale
        self.windup = 0.32
        self.storm_time = 2.3 * self.duration_scale
        self.spawn_interval = max(0.06, 0.12 * self.interval_scale)
        self.spawn_timer = self.windup
        self.arrows: List[Dict[str, object]] = []
        self.emitter = self.add_emitter()

    def _spawn_arrow(self) -> None:
        angle = random.uniform(0.0, math.tau)
        dist = self.radius * math.sqrt(random.random())
        impact = self.center + Vector2(math.cos(angle), math.sin(angle)) * dist
        start = impact + Vector2(random.uniform(-120.0, 120.0), -320.0 - random.uniform(0.0, 160.0))
        self.arrows.append(
            {
                "start": start,
                "end": impact,
                "travel": random.uniform(0.20, 0.34),
                "t": 0.0,
            }
        )

    def update(self, dt: float, ctx: UltimateContext) -> None:
        super().update(dt, ctx)
        if self.elapsed >= self.windup and self.elapsed <= self.windup + self.storm_time:
            self.spawn_timer -= dt
            while self.spawn_timer <= 0.0:
                self._spawn_arrow()
                if random.random() < 0.28 + max(0.0, float(self.mods.get("projectile_count_bonus", 0.0))) * 0.08:
                    self._spawn_arrow()
                self.spawn_timer += self.spawn_interval
        keep_arrows: List[Dict[str, object]] = []
        for arrow in self.arrows:
            arrow["t"] = float(arrow.get("t", 0.0)) + dt / max(0.05, float(arrow.get("travel", 0.25)))
            if float(arrow["t"]) >= 1.0:
                impact = arrow.get("end")
                if isinstance(impact, Vector2):
                    hit_any = False
                    for wolf in ctx.wolves_in_radius(impact, 60.0 * self.radius_scale):
                        pos_raw = wolf.get("pos")
                        if not isinstance(pos_raw, Vector2):
                            continue
                        dealt = ctx.damage_wolf(wolf, self.base_damage * 1.08, Vector2(pos_raw), gore=0.9)
                        if dealt <= 0.0:
                            continue
                        hit_any = True
                        ctx.status_effects.add_effect(
                            ctx.status_effects.wolf_key(wolf),
                            StatusEffect("slow", 2.2, potency=0.34, color=self.accent_color),
                        )
                    self.emitter.burst(
                        impact,
                        self.core_color,
                        self.accent_color,
                        count=16,
                        speed_min=90.0,
                        speed_max=220.0,
                        life_min=0.10,
                        life_max=0.28,
                        size_start=3.6,
                        size_end=0.5,
                        spread=math.tau,
                        gravity=16.0,
                        drag=1.6,
                        shape="spark",
                    )
                    self.emitter.burst(
                        impact,
                        (246, 236, 198),
                        (164, 132, 68),
                        count=10,
                        speed_min=60.0,
                        speed_max=140.0,
                        life_min=0.14,
                        life_max=0.32,
                        size_start=3.2,
                        size_end=0.5,
                        spread=math.tau,
                        gravity=-14.0,
                        drag=1.2,
                    )
                    if hit_any:
                        ctx.screen_effects.flash((196, 174, 110), alpha=28, duration=0.08)
                continue
            keep_arrows.append(arrow)
        self.arrows = keep_arrows
        if self.elapsed <= self.windup + self.storm_time and random.random() < 0.35:
            self.emitter.burst(
                self.center + Vector2(random.uniform(-self.radius * 0.75, self.radius * 0.75), random.uniform(-self.radius * 0.3, self.radius * 0.3)),
                self.accent_color,
                self.shadow_color,
                count=2,
                speed_min=12.0,
                speed_max=48.0,
                life_min=0.12,
                life_max=0.28,
                size_start=2.6,
                size_end=0.4,
                spread=math.tau,
                gravity=-10.0,
                drag=1.1,
            )
        if self.elapsed > self.windup + self.storm_time and not self.arrows:
            self.finished = True

    def draw(self, surface: pygame.Surface, camera: Vector2) -> None:
        if self.finished:
            super().draw(surface, camera)
            return
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        cx = int(self.center.x - camera.x)
        cy = int(self.center.y - camera.y)
        if self.elapsed < self.windup + self.storm_time:
            pulse = 0.76 + 0.24 * math.sin(pygame.time.get_ticks() * 0.012)
            radius = int(self.radius * pulse)
            pygame.draw.circle(overlay, (*self.accent_color, 92), (cx, cy), radius, 2)
            pygame.draw.circle(overlay, (*self.core_color, 44), (cx, cy), max(14, int(radius * 0.45)), 1)
        for arrow in self.arrows:
            start = arrow.get("start")
            end = arrow.get("end")
            if not isinstance(start, Vector2) or not isinstance(end, Vector2):
                continue
            t = clamp(float(arrow.get("t", 0.0)), 0.0, 1.0)
            pos = start.lerp(end, t)
            sx = int(pos.x - camera.x)
            sy = int(pos.y - camera.y)
            tail = pos.lerp(start, 0.18)
            tx = int(tail.x - camera.x)
            ty = int(tail.y - camera.y)
            pygame.draw.line(overlay, (*self.core_color, 196), (sx, sy), (tx, ty), 2)
            pygame.gfxdraw.filled_circle(overlay, sx, sy, 3, (*self.accent_color, 216))
        surface.blit(overlay, (0, 0))
        super().draw(surface, camera)


class NecromancerSummonUltimate(UltimateBase):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.rise_time = 0.38
        self.active_time = 5.8 * self.duration_scale
        self.pos = Vector2(self.target_pos)
        self.target_id: Optional[int] = None
        self.attack_cd = 0.0
        self.emitter = self.add_emitter()

    def start(self, ctx: UltimateContext) -> None:
        self.pos = ctx.nearest_walkable(self.target_pos, radius=24.0)
        self.emitter.burst(
            self.pos,
            self.accent_color,
            self.shadow_color,
            count=20,
            speed_min=70.0,
            speed_max=180.0,
            life_min=0.18,
            life_max=0.42,
            size_start=4.2,
            size_end=0.6,
            spread=math.tau,
            gravity=-24.0,
            drag=1.2,
        )

    def update(self, dt: float, ctx: UltimateContext) -> None:
        super().update(dt, ctx)
        if self.elapsed < self.rise_time:
            if random.random() < 0.6:
                self.emitter.burst(
                    self.pos + Vector2(random.uniform(-22.0, 22.0), random.uniform(-10.0, 10.0)),
                    self.accent_color,
                    (235, 228, 212),
                    count=2,
                    speed_min=18.0,
                    speed_max=60.0,
                    life_min=0.14,
                    life_max=0.30,
                    size_start=2.6,
                    size_end=0.4,
                    spread=math.tau,
                    gravity=-14.0,
                    drag=1.0,
                )
            return
        self.attack_cd = max(0.0, self.attack_cd - dt)
        target = ctx.find_wolf_by_id(self.target_id) if isinstance(self.target_id, int) else None
        if not isinstance(target, dict):
            target = ctx.nearest_wolf(self.pos, max_dist=520.0)
            self.target_id = id(target) if isinstance(target, dict) else None
        hover_target = ctx.player_pos() + Vector2(float(ctx.player_facing()) * 54.0, -18.0)
        if isinstance(target, dict):
            pos_raw = target.get("pos")
            if isinstance(pos_raw, Vector2):
                desired = Vector2(pos_raw) + Vector2(0.0, -20.0)
                travel = desired - self.pos
                if travel.length_squared() > 1e-6:
                    self.pos += travel.normalize() * min(travel.length(), 280.0 * dt)
                if self.pos.distance_to(desired) <= 62.0 and self.attack_cd <= 0.0:
                    self.attack_cd = max(0.32, 0.72 * self.interval_scale)
                    hit_any = False
                    for wolf in ctx.wolves_in_radius(Vector2(pos_raw), 94.0 * self.radius_scale):
                        wolf_pos_raw = wolf.get("pos")
                        if not isinstance(wolf_pos_raw, Vector2):
                            continue
                        dealt = ctx.damage_wolf(wolf, self.base_damage * 1.3, Vector2(wolf_pos_raw), gore=1.2)
                        if dealt <= 0.0:
                            continue
                        hit_any = True
                        ctx.status_effects.add_effect(ctx.status_effects.wolf_key(wolf), StatusEffect("freeze", 0.50, potency=1.0, color=self.accent_color))
                    self.emitter.burst(
                        Vector2(pos_raw),
                        self.accent_color,
                        (236, 228, 246),
                        count=18,
                        speed_min=90.0,
                        speed_max=220.0,
                        life_min=0.14,
                        life_max=0.34,
                        size_start=3.8,
                        size_end=0.5,
                        spread=math.tau,
                        gravity=-18.0,
                        drag=1.2,
                        shape="spark",
                    )
                    if hit_any:
                        ctx.screen_effects.flash((118, 94, 158), alpha=30, duration=0.08)
        else:
            drift = hover_target - self.pos
            if drift.length_squared() > 1e-6:
                self.pos += drift.normalize() * min(drift.length(), 180.0 * dt)
        if random.random() < 0.5:
            self.emitter.burst(
                self.pos + Vector2(random.uniform(-16.0, 16.0), random.uniform(-18.0, 14.0)),
                self.accent_color,
                self.shadow_color,
                count=2,
                speed_min=18.0,
                speed_max=54.0,
                life_min=0.12,
                life_max=0.26,
                size_start=2.4,
                size_end=0.4,
                spread=math.tau,
                gravity=-10.0,
                drag=1.1,
            )
        if self.elapsed >= self.rise_time + self.active_time:
            self.finished = True

    def draw(self, surface: pygame.Surface, camera: Vector2) -> None:
        if self.finished:
            super().draw(surface, camera)
            return
        sx = int(self.pos.x - camera.x)
        sy = int(self.pos.y - camera.y)
        phase = pygame.time.get_ticks() * 0.008
        body = pygame.Surface((90, 110), pygame.SRCALPHA)
        pygame.draw.ellipse(body, (*self.shadow_color, 84), pygame.Rect(16, 12, 58, 82))
        pygame.draw.ellipse(body, (*self.accent_color, 112), pygame.Rect(24, 20, 42, 66), 2)
        for idx in range(4):
            yy = 32 + idx * 12
            pygame.draw.line(body, (*self.core_color, 128), (30, yy), (60, yy), 1)
        for idx in range(3):
            ang = phase + idx * (math.tau / 3.0)
            px = 45 + int(math.cos(ang) * 24)
            py = 38 + int(math.sin(ang) * 14)
            pygame.gfxdraw.filled_circle(body, px, py, 3, (*self.accent_color, 156))
        surface.blit(body, (sx - body.get_width() // 2, sy - body.get_height() // 2))
        super().draw(surface, camera)


class WarriorDashUltimate(UltimateBase):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        direction = self.target_pos - self.caster_pos
        if direction.length_squared() <= 1e-5:
            direction = Vector2(float(self.facing), 0.0)
        self.direction = direction.normalize()
        self.windup = 0.18
        self.travel_left = 380.0 * self.radius_scale
        self.dash_speed = 1680.0
        self.shockwave_time = 0.26
        self.in_shockwave = False
        self.hit_ids: Set[int] = set()
        self.wave_hit_ids: Set[int] = set()
        self.shock_origin = Vector2(self.caster_pos)
        self.emitter = self.add_emitter()

    def update(self, dt: float, ctx: UltimateContext) -> None:
        super().update(dt, ctx)
        self.caster_pos = ctx.player_pos()
        if self.elapsed < self.windup:
            if random.random() < 0.7:
                self.emitter.burst(
                    self.caster_pos + Vector2(0.0, -8.0),
                    self.core_color,
                    self.accent_color,
                    count=2,
                    speed_min=24.0,
                    speed_max=84.0,
                    life_min=0.10,
                    life_max=0.26,
                    size_start=3.0,
                    size_end=0.4,
                    spread=0.6,
                    direction=self.direction,
                    gravity=20.0,
                    drag=1.4,
                    shape="spark",
                )
            return
        if not self.in_shockwave:
            start_pos = ctx.player_pos()
            step = min(self.travel_left, self.dash_speed * dt)
            desired = start_pos + self.direction * step
            if not ctx.is_walkable(desired):
                desired = ctx.nearest_walkable(start_pos + self.direction * max(18.0, step * 0.3))
                step = desired.distance_to(start_pos)
            if step > 0.01:
                ctx.move_player(desired)
                self.caster_pos = Vector2(desired)
                self.travel_left = max(0.0, self.travel_left - step)
                self.shock_origin = Vector2(desired)
                for wolf in ctx.living_wolves():
                    wolf_id = id(wolf)
                    if wolf_id in self.hit_ids:
                        continue
                    pos_raw = wolf.get("pos")
                    if not isinstance(pos_raw, Vector2):
                        continue
                    if not circle_hits_segment(Vector2(pos_raw), 54.0, start_pos, desired):
                        continue
                    dealt = ctx.damage_wolf(wolf, self.base_damage * 1.7, Vector2(pos_raw), gore=1.45)
                    if dealt > 0.0:
                        self.hit_ids.add(wolf_id)
                        ctx.status_effects.add_effect(ctx.status_effects.wolf_key(wolf), StatusEffect("stun", 0.65, potency=1.0, color=self.accent_color))
                        ctx.push_wolf(wolf, self.direction, 36.0)
                self.emitter.burst(
                    desired + Vector2(0.0, -10.0),
                    self.core_color,
                    self.accent_color,
                    count=4,
                    speed_min=60.0,
                    speed_max=160.0,
                    life_min=0.10,
                    life_max=0.24,
                    size_start=3.2,
                    size_end=0.5,
                    spread=0.7,
                    direction=self.direction,
                    gravity=26.0,
                    drag=1.6,
                    shape="spark",
                )
            if self.travel_left <= 0.0 or step <= 0.01:
                self.in_shockwave = True
                self.elapsed = self.windup
                ctx.screen_effects.flash((214, 168, 110), alpha=46, duration=0.08)
                self.emitter.burst(
                    self.shock_origin + Vector2(0.0, -6.0),
                    self.accent_color,
                    self.shadow_color,
                    count=18,
                    speed_min=80.0,
                    speed_max=220.0,
                    life_min=0.14,
                    life_max=0.34,
                    size_start=4.2,
                    size_end=0.6,
                    spread=math.tau,
                    gravity=34.0,
                    drag=1.4,
                    shape="spark",
                )
            return
        wave_progress = clamp((self.elapsed - self.windup) / max(0.001, self.shockwave_time), 0.0, 1.0)
        cone_len = 220.0 * wave_progress * self.radius_scale
        for wolf in ctx.living_wolves():
            wolf_id = id(wolf)
            if wolf_id in self.wave_hit_ids:
                continue
            pos_raw = wolf.get("pos")
            if not isinstance(pos_raw, Vector2):
                continue
            rel = Vector2(pos_raw) - self.shock_origin
            dist = rel.length()
            if dist <= 1e-5 or dist > cone_len:
                continue
            if rel.normalize().dot(self.direction) < 0.46:
                continue
            dealt = ctx.damage_wolf(wolf, self.base_damage * 1.15, Vector2(pos_raw), gore=1.1)
            if dealt <= 0.0:
                continue
            self.wave_hit_ids.add(wolf_id)
            ctx.status_effects.add_effect(ctx.status_effects.wolf_key(wolf), StatusEffect("stun", 0.45, potency=1.0, color=self.core_color))
        if self.elapsed >= self.windup + self.shockwave_time:
            self.finished = True

    def draw(self, surface: pygame.Surface, camera: Vector2) -> None:
        if self.finished:
            super().draw(surface, camera)
            return
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        if not self.in_shockwave and self.elapsed < self.windup:
            sx = int(self.caster_pos.x - camera.x)
            sy = int(self.caster_pos.y - camera.y - 8.0)
            ex = int(sx + self.direction.x * 110.0)
            ey = int(sy + self.direction.y * 110.0)
            pygame.draw.line(overlay, (*self.accent_color, 110), (sx, sy), (ex, ey), 4)
        if self.in_shockwave:
            progress = clamp((self.elapsed - self.windup) / max(0.001, self.shockwave_time), 0.0, 1.0)
            length = 220.0 * progress * self.radius_scale
            origin = self.shock_origin
            left = rotate_vec(self.direction, -0.88) * length
            right = rotate_vec(self.direction, 0.88) * length
            center = self.direction * length
            pts = [
                (int(origin.x - camera.x), int(origin.y - camera.y)),
                (int(origin.x + left.x - camera.x), int(origin.y + left.y - camera.y)),
                (int(origin.x + center.x - camera.x), int(origin.y + center.y - camera.y)),
                (int(origin.x + right.x - camera.x), int(origin.y + right.y - camera.y)),
            ]
            pygame.draw.polygon(overlay, (*self.accent_color, 72), pts)
            pygame.draw.lines(overlay, (*self.core_color, 166), False, pts[1:], 3)
        surface.blit(overlay, (0, 0))
        super().draw(surface, camera)


class PaladinTransformationUltimate(UltimateBase):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.total_time = 5.4 * self.duration_scale
        self.pulse_interval = max(0.20, 0.60 * self.interval_scale)
        self.pulse_timer = 0.06
        self.shield_amount = 40.0 + self.base_damage * 1.9
        self.buff_applied = False
        self.pulse_flash = 0.0
        self.pulse_dir = Vector2(float(self.facing), 0.0)
        self.emitter = self.add_emitter()

    def start(self, ctx: UltimateContext) -> None:
        ctx.screen_effects.flash((244, 224, 170), alpha=72, duration=0.12)

    def update(self, dt: float, ctx: UltimateContext) -> None:
        super().update(dt, ctx)
        self.caster_pos = ctx.player_pos()
        if not self.buff_applied:
            self.buff_applied = True
            ctx.status_effects.add_effect(
                ctx.status_effects.PLAYER_KEY,
                StatusEffect("shield", self.total_time, potency=self.shield_amount, color=self.accent_color),
            )
            ctx.status("Ascendant Aegis shields you in radiant fire.", 1.6)
        self.pulse_timer -= dt
        self.pulse_flash = max(0.0, self.pulse_flash - dt)
        player_pos = ctx.player_pos()
        if random.random() < 0.85:
            self.emitter.burst(
                player_pos + Vector2(random.uniform(-22.0, 22.0), random.uniform(-50.0, -10.0)),
                self.core_color,
                self.accent_color,
                count=2,
                speed_min=16.0,
                speed_max=44.0,
                life_min=0.14,
                life_max=0.34,
                size_start=2.6,
                size_end=0.4,
                spread=math.tau,
                gravity=-22.0,
                drag=1.2,
                shape="diamond",
            )
        if self.pulse_timer <= 0.0:
            self.pulse_timer += self.pulse_interval
            target = ctx.nearest_wolf(player_pos, max_dist=460.0)
            if isinstance(target, dict) and isinstance(target.get("pos"), Vector2):
                aim = Vector2(target["pos"]) - player_pos
                if aim.length_squared() > 1e-6:
                    self.pulse_dir = aim.normalize()
            else:
                self.pulse_dir = Vector2(float(ctx.player_facing()), 0.0)
            hit_any = False
            cone_range = 250.0 * self.radius_scale
            for wolf in ctx.living_wolves():
                pos_raw = wolf.get("pos")
                if not isinstance(pos_raw, Vector2):
                    continue
                rel = Vector2(pos_raw) - player_pos
                dist = rel.length()
                if dist <= 1e-5 or dist > cone_range:
                    continue
                if rel.normalize().dot(self.pulse_dir) < 0.42:
                    continue
                dealt = ctx.damage_wolf(wolf, self.base_damage * 1.05, Vector2(pos_raw), gore=0.95)
                if dealt <= 0.0:
                    continue
                hit_any = True
                ctx.status_effects.add_effect(
                    ctx.status_effects.wolf_key(wolf),
                    StatusEffect("burn", 2.6, potency=max(3.5, self.base_damage * 0.14), tick_interval=0.50, color=self.core_color),
                )
            self.pulse_flash = 0.22
            self.emitter.burst(
                player_pos + self.pulse_dir * 20.0,
                self.core_color,
                self.accent_color,
                count=16,
                speed_min=80.0,
                speed_max=220.0,
                life_min=0.10,
                life_max=0.28,
                size_start=3.4,
                size_end=0.5,
                spread=0.96,
                direction=self.pulse_dir,
                drag=1.5,
                shape="spark",
            )
            if hit_any:
                ctx.screen_effects.flash((234, 216, 138), alpha=36, duration=0.08)
        if self.elapsed >= self.total_time:
            self.finished = True

    def draw(self, surface: pygame.Surface, camera: Vector2) -> None:
        if self.finished:
            super().draw(surface, camera)
            return
        sx = int(self.caster_pos.x - camera.x)
        sy = int(self.caster_pos.y - camera.y)
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        halo_r = 34 + int(6 * math.sin(pygame.time.get_ticks() * 0.012))
        pygame.gfxdraw.aacircle(overlay, sx, sy - 16, halo_r, (*self.accent_color, 142))
        pygame.gfxdraw.aacircle(overlay, sx, sy - 16, max(12, halo_r - 10), (*self.core_color, 112))
        if self.pulse_flash > 0.0:
            length = 210.0 * clamp(self.pulse_flash / 0.22, 0.0, 1.0) * self.radius_scale
            left = rotate_vec(self.pulse_dir, -0.92) * length
            right = rotate_vec(self.pulse_dir, 0.92) * length
            center = self.pulse_dir * length
            pts = [
                (sx, sy - 8),
                (sx + int(left.x), sy - 8 + int(left.y)),
                (sx + int(center.x), sy - 8 + int(center.y)),
                (sx + int(right.x), sy - 8 + int(right.y)),
            ]
            pygame.draw.polygon(overlay, (*self.core_color, 74), pts)
            pygame.draw.lines(overlay, (*self.accent_color, 156), False, pts[1:], 3)
        surface.blit(overlay, (0, 0))
        super().draw(surface, camera)
