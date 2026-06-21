"""game/systems/core.py — runtime systems: day/night, weather, particles,
status effects, screen/celebration/level-up VFX, camera, ambient overlay.
Depends only on constants + game.utils + game.vfx (no main.py imports)."""
import math
import random
import colorsys
from typing import Dict, List, Optional, Tuple, Any, Union, Set

import pygame
from pygame import Vector2

from game.constants import HORIZON_Y, SCREEN_WIDTH, SCREEN_HEIGHT
from game.utils import clamp, exp_smooth, rotate_vec, color_lerp
from game.vfx import spawn_particle_burst, spawn_blood_splatter, spawn_damage_number


class DayNightCycle:
    def __init__(self) -> None:
        self.time = 8.0  # Start at 8 AM
        self.day_duration = 300.0  # Seconds per day

    def update(self, dt: float) -> None:
        self.time = (self.time + (dt / self.day_duration) * 24.0) % 24.0

    def get_tint(self) -> tuple[int, int, int, int]:
        # Simple 4-phase cycle: Day, Dusk, Night, Dawn.
        # Night alpha is deliberately kept moderate (was 160) so the detailed
        # buildings/ground stay readable instead of crushing to near-black.
        if 6.0 <= self.time < 18.0:  # Day
            return (0, 0, 0, 0)
        elif 18.0 <= self.time < 20.0:  # Dusk
            alpha = int(96 * ((self.time - 18.0) / 2.0))
            return (104, 62, 24, alpha)
        elif 20.0 <= self.time or self.time < 5.0:  # Night
            return (16, 18, 40, 112)
        else:  # Dawn (5.0 to 6.0)
            alpha = int(96 * (1.0 - (self.time - 5.0)))
            return (104, 62, 24, alpha)


class WeatherSystem:
    PROFILES: Dict[str, Dict[str, object]] = {
        "clear": {
            "label": "Clear",
            "cloud": 0.08,
            "rain": 0.0,
            "fog": 0.0,
            "wind": 16.0,
            "ui_color": (196, 218, 228),
        },
        "cloudy": {
            "label": "Overcast",
            "cloud": 0.44,
            "rain": 0.0,
            "fog": 0.06,
            "wind": 24.0,
            "ui_color": (188, 194, 208),
        },
        "rain": {
            "label": "Rain",
            "cloud": 0.64,
            "rain": 0.68,
            "fog": 0.14,
            "wind": 48.0,
            "ui_color": (154, 184, 214),
        },
        "storm": {
            "label": "Storm",
            "cloud": 0.84,
            "rain": 1.0,
            "fog": 0.26,
            "wind": 78.0,
            "ui_color": (236, 214, 164),
        },
        "fog": {
            "label": "Fog",
            "cloud": 0.26,
            "rain": 0.0,
            "fog": 0.82,
            "wind": 10.0,
            "ui_color": (216, 220, 224),
        },
    }

    def __init__(self, initial_level: str = "town", day_time: float = 8.0) -> None:
        self.rng = random.Random(random.randrange(1_000_000_000))
        self.state = "clear"
        self.current_level = str(initial_level)
        self.transition_timer = 0.0
        self.cloud_cover = 0.0
        self.precipitation = 0.0
        self.fog_density = 0.0
        self.wind = 0.0
        self.target_cloud_cover = 0.0
        self.target_precipitation = 0.0
        self.target_fog_density = 0.0
        self.target_wind = 0.0
        self.flash_timer = 0.0
        self.flash_cooldown = 0.0
        self.rain_streaks: List[Dict[str, float]] = [self._spawn_rain_streak(initial=True) for _ in range(96)]
        self.fog_banks: List[Dict[str, float]] = [self._spawn_fog_bank(initial=True) for _ in range(10)]
        self.snow_flakes: List[Dict[str, float]] = [self._spawn_snow_flake(initial=True) for _ in range(120)]
        self._apply_profile(self._choose_next_state(initial_level, day_time), immediate=True)
        self.transition_timer = self._next_duration(self.state)

    def _spawn_snow_flake(self, initial: bool = False) -> Dict[str, float]:
        x = self.rng.uniform(-30.0, SCREEN_WIDTH + 30.0)
        y = self.rng.uniform(-SCREEN_HEIGHT, SCREEN_HEIGHT) if initial else self.rng.uniform(-20.0, -4.0)
        return {
            "x": x,
            "y": y,
            "size": self.rng.uniform(1.5, 4.0),
            "speed": self.rng.uniform(55.0, 130.0),
            "drift": self.rng.uniform(-18.0, 18.0),
            "wobble": self.rng.uniform(0.0, math.tau),
            "wobble_speed": self.rng.uniform(0.8, 2.2),
            "alpha": self.rng.uniform(140.0, 230.0),
        }

    def _spawn_rain_streak(self, initial: bool = False) -> Dict[str, float]:
        if initial:
            x = self.rng.uniform(-50.0, SCREEN_WIDTH + 50.0)
            y = self.rng.uniform(-SCREEN_HEIGHT, SCREEN_HEIGHT)
        else:
            x = self.rng.uniform(-50.0, SCREEN_WIDTH + 50.0)
            y = self.rng.uniform(-140.0, -12.0)
            if self.wind < -22.0 and self.rng.random() < 0.35:
                x = SCREEN_WIDTH + self.rng.uniform(12.0, 80.0)
                y = self.rng.uniform(-20.0, SCREEN_HEIGHT * 0.65)
            elif self.wind > 22.0 and self.rng.random() < 0.35:
                x = -self.rng.uniform(12.0, 80.0)
                y = self.rng.uniform(-20.0, SCREEN_HEIGHT * 0.65)
        return {
            "x": x,
            "y": y,
            "length": self.rng.uniform(11.0, 24.0),
            "speed": self.rng.uniform(480.0, 920.0),
            "drift": self.rng.uniform(-8.0, 8.0),
            "alpha": self.rng.uniform(88.0, 164.0),
        }

    def _spawn_fog_bank(self, initial: bool = False) -> Dict[str, float]:
        if initial:
            x = self.rng.uniform(-220.0, SCREEN_WIDTH + 220.0)
        elif self.wind >= 0.0:
            x = -260.0 - self.rng.uniform(0.0, 120.0)
        else:
            x = SCREEN_WIDTH + 260.0 + self.rng.uniform(0.0, 120.0)
        return {
            "x": x,
            "y": self.rng.uniform(HORIZON_Y - 40.0, SCREEN_HEIGHT + 40.0),
            "radius": self.rng.uniform(110.0, 220.0),
            "pulse": self.rng.uniform(0.42, 1.08),
            "alpha": self.rng.uniform(0.55, 1.0),
            "drift": self.rng.uniform(-4.0, 4.0),
            "phase": self.rng.uniform(0.0, math.tau),
        }

    def _next_duration(self, state: str) -> float:
        ranges = {
            "clear": (24.0, 52.0),
            "cloudy": (20.0, 40.0),
            "rain": (18.0, 34.0),
            "storm": (14.0, 26.0),
            "fog": (16.0, 30.0),
        }
        low, high = ranges.get(state, (20.0, 36.0))
        return self.rng.uniform(low, high)

    def _choose_next_state(self, level: str, day_time: float) -> str:
        level_key = "wilderness" if str(level).strip().lower() == "wilderness" else "town"
        hour = float(day_time) % 24.0
        weights = {
            "clear": 32,
            "cloudy": 28,
            "rain": 20,
            "storm": 8,
            "fog": 12,
        }
        if level_key == "town":
            weights["clear"] += 8
            weights["storm"] = max(3, weights["storm"] - 3)
            weights["rain"] = max(10, weights["rain"] - 4)
        else:
            weights["rain"] += 6
            weights["storm"] += 4
        if 4.0 <= hour < 8.0:
            weights["fog"] += 24
            weights["clear"] = max(6, weights["clear"] - 8)
        elif 17.0 <= hour < 21.0:
            weights["cloudy"] += 10
            weights["rain"] += 6
            weights["storm"] += 4
        elif hour >= 21.0 or hour < 4.0:
            weights["fog"] += 8
            weights["storm"] += 6
            weights["clear"] = max(6, weights["clear"] - 10)
        total = float(sum(max(1, weight) for weight in weights.values()))
        roll = self.rng.uniform(0.0, total)
        cursor = 0.0
        for key in ("clear", "cloudy", "rain", "storm", "fog"):
            cursor += float(max(1, weights.get(key, 1)))
            if roll <= cursor:
                return key
        return "clear"

    def _apply_profile(self, state: str, immediate: bool = False) -> None:
        state_key = state if state in self.PROFILES else "clear"
        profile = self.PROFILES[state_key]
        self.state = state_key
        self.target_cloud_cover = clamp(float(profile["cloud"]) * self.rng.uniform(0.9, 1.08), 0.0, 1.0)
        self.target_precipitation = clamp(float(profile["rain"]) * self.rng.uniform(0.88, 1.1), 0.0, 1.0)
        self.target_fog_density = clamp(float(profile["fog"]) * self.rng.uniform(0.88, 1.12), 0.0, 1.0)
        wind_dir = -1.0 if self.rng.random() < 0.32 else 1.0
        self.target_wind = float(profile["wind"]) * wind_dir * self.rng.uniform(0.82, 1.18)
        if immediate:
            self.cloud_cover = self.target_cloud_cover
            self.precipitation = self.target_precipitation
            self.fog_density = self.target_fog_density
            self.wind = self.target_wind
        self.flash_timer = 0.0
        self.flash_cooldown = self.rng.uniform(2.4, 5.8)

    def _update_rain_streaks(self, dt: float) -> None:
        drift = self.wind * 0.56
        for streak in self.rain_streaks:
            streak["x"] += (drift + streak["drift"]) * dt
            streak["y"] += streak["speed"] * dt
            if (
                streak["y"] > SCREEN_HEIGHT + 44.0
                or streak["x"] < -90.0
                or streak["x"] > SCREEN_WIDTH + 90.0
            ):
                streak.clear()
                streak.update(self._spawn_rain_streak())

    def _update_fog_banks(self, dt: float) -> None:
        drift = self.wind * 0.08
        for bank in self.fog_banks:
            bank["x"] += (drift + bank["drift"]) * dt
            bank["phase"] = (bank["phase"] + bank["pulse"] * dt) % math.tau
            if bank["x"] < -360.0 or bank["x"] > SCREEN_WIDTH + 360.0:
                bank.clear()
                bank.update(self._spawn_fog_bank())

    def _update_snow_flakes(self, dt: float) -> None:
        drift_base = self.wind * 0.22
        for flake in self.snow_flakes:
            flake["wobble"] = (flake["wobble"] + flake["wobble_speed"] * dt) % math.tau
            flake["x"] += (drift_base + flake["drift"] + math.sin(flake["wobble"]) * 8.0) * dt
            flake["y"] += flake["speed"] * dt
            if flake["y"] > SCREEN_HEIGHT + 10.0 or flake["x"] < -60.0 or flake["x"] > SCREEN_WIDTH + 60.0:
                flake.clear()
                flake.update(self._spawn_snow_flake())

    def update(self, dt: float, level: str, day_time: float) -> bool:
        if dt <= 0.0:
            return False
        self.current_level = str(level)
        weather_changed = False
        self.transition_timer -= dt
        if self.transition_timer <= 0.0:
            next_state = self._choose_next_state(level, day_time)
            weather_changed = next_state != self.state
            self._apply_profile(next_state)
            self.transition_timer = self._next_duration(self.state)
        blend = min(1.0, dt * 0.42)
        wind_blend = min(1.0, dt * 0.26)
        self.cloud_cover += (self.target_cloud_cover - self.cloud_cover) * blend
        self.precipitation += (self.target_precipitation - self.precipitation) * blend
        self.fog_density += (self.target_fog_density - self.fog_density) * blend
        self.wind += (self.target_wind - self.wind) * wind_blend
        self._update_rain_streaks(dt)
        self._update_fog_banks(dt)
        if self.current_level == "ice_biome":
            self._update_snow_flakes(dt)
        self.flash_timer = max(0.0, self.flash_timer - dt)
        self.flash_cooldown = max(0.0, self.flash_cooldown - dt)
        if self.state == "storm" and self.precipitation > 0.58 and self.flash_cooldown <= 0.0:
            flash_chance = dt * (0.22 + max(0.0, self.precipitation - 0.58) * 0.5)
            if self.rng.random() < flash_chance:
                self.flash_timer = self.rng.uniform(0.08, 0.18)
                self.flash_cooldown = self.rng.uniform(3.2, 7.2)
        return weather_changed

    def get_display_name(self) -> str:
        profile = self.PROFILES.get(self.state, self.PROFILES["clear"])
        return str(profile["label"])

    def get_ui_color(self) -> Tuple[int, int, int]:
        profile = self.PROFILES.get(self.state, self.PROFILES["clear"])
        return tuple(int(v) for v in profile["ui_color"])

    def get_speed_multiplier(self, level: str) -> float:
        lv = str(level).strip().lower()
        if lv == "town":
            return 1.0
        slowdown = self.precipitation * 0.08 + max(0.0, self.fog_density - 0.45) * 0.05
        if lv == "ice_biome":
            slowdown += 0.10  # permanent cold-wind penalty
        return clamp(1.0 - slowdown, 0.75 if lv == "ice_biome" else 0.88, 1.0)

    def get_hud_detail(self, level: str) -> str:
        lv = str(level).strip().lower()
        if lv == "ice_biome":
            move_pct = int(round(self.get_speed_multiplier(level) * 100.0))
            if move_pct < 100:
                return f"Blizzard rages — {move_pct}% speed"
            return "Frost hangs heavy"
        if lv == "wilderness":
            move_pct = int(round(self.get_speed_multiplier(level) * 100.0))
            if move_pct < 100:
                return f"Move speed {move_pct}%"
            if self.fog_density >= 0.48:
                return "Visibility reduced"
        if self.precipitation >= 0.45:
            return "Ground is slick"
        if self.fog_density >= 0.45:
            return "Mist hangs low"
        if self.cloud_cover >= 0.45:
            return "Heavy cloud cover"
        return "Calm air"

    def render(self, surface: pygame.Surface) -> None:
        cloud_alpha = int(92 * clamp(self.cloud_cover, 0.0, 1.0))
        if cloud_alpha > 0:
            # Reuse one full-screen scratch surface instead of allocating ~4.7MB every frame.
            cloud_surface = getattr(self, "_fs_buf", None)
            if cloud_surface is None:
                cloud_surface = self._fs_buf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            if self.state == "storm":
                cloud_color = (18, 22, 34, cloud_alpha)
            elif self.state == "rain":
                cloud_color = (24, 30, 40, cloud_alpha)
            else:
                cloud_color = (28, 32, 38, cloud_alpha)
            cloud_surface.fill(cloud_color)
            surface.blit(cloud_surface, (0, 0))

        if self.fog_density > 0.04:
            fog_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            base_alpha = int(110 * clamp(self.fog_density, 0.0, 1.0))
            fog_band_top = max(0, HORIZON_Y - 24)
            pygame.draw.rect(
                fog_surface,
                (214, 218, 224, int(base_alpha * 0.22)),
                pygame.Rect(0, fog_band_top, SCREEN_WIDTH, SCREEN_HEIGHT - fog_band_top),
            )
            for bank in self.fog_banks:
                wobble = math.sin(bank["phase"]) * 18.0
                radius = int(bank["radius"] * (0.72 + 0.12 * math.sin(bank["phase"] * 0.6 + 0.4)))
                alpha = int(base_alpha * bank["alpha"] * 0.3)
                if radius < 8 or alpha <= 0:
                    continue
                center = (int(bank["x"]), int(bank["y"] + wobble))
                pygame.draw.circle(fog_surface, (214, 218, 224, alpha), center, radius)
                pygame.draw.circle(
                    fog_surface,
                    (214, 218, 224, max(0, alpha - 12)),
                    (center[0] + radius // 3, center[1]),
                    max(8, radius * 2 // 3),
                )
            surface.blit(fog_surface, (0, 0))

        if self.precipitation > 0.02:
            rain_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            drop_count = max(8, int(len(self.rain_streaks) * clamp(self.precipitation, 0.0, 1.0)))
            slant = int(self.wind * 0.028)
            for idx in range(drop_count):
                streak = self.rain_streaks[idx]
                start_x = int(streak["x"])
                start_y = int(streak["y"])
                end_x = start_x + slant
                end_y = int(streak["y"] + streak["length"])
                alpha = int(streak["alpha"] * (0.35 + 0.65 * self.precipitation))
                pygame.draw.line(rain_surface, (178, 196, 220, alpha), (start_x, start_y), (end_x, end_y), 1)
                if (
                    self.precipitation > 0.35
                    and start_y > HORIZON_Y + 80
                    and self.rng.random() < 0.025 * self.precipitation
                ):
                    splash_y = min(SCREEN_HEIGHT - 3, end_y)
                    pygame.draw.line(
                        rain_surface,
                        (190, 205, 224, max(18, alpha // 4)),
                        (start_x - 2, splash_y),
                        (start_x + 2, splash_y),
                        1,
                    )
            if self.precipitation > 0.18:
                mist = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
                mist.fill((52, 64, 76, int(36 * self.precipitation)))
                rain_surface.blit(mist, (0, 0))
            surface.blit(rain_surface, (0, 0))

        if self.flash_timer > 0.0:
            flash_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            flash_alpha = int(150 * min(1.0, self.flash_timer / 0.18))
            flash_surface.fill((228, 236, 255, flash_alpha))
            surface.blit(flash_surface, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

        # Ice biome: always render snowfall
        if self.current_level == "ice_biome":
            snow_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            for flake in self.snow_flakes:
                sx = int(flake["x"])
                sy = int(flake["y"])
                if sy < -6 or sy > SCREEN_HEIGHT + 6:
                    continue
                r = max(1, int(flake["size"]))
                a = int(flake["alpha"])
                pygame.gfxdraw.filled_circle(snow_surf, sx, sy, r, (235, 244, 255, a))
                if r > 2:
                    pygame.gfxdraw.filled_circle(snow_surf, sx, sy, r - 1, (255, 255, 255, min(255, a + 30)))
            surface.blit(snow_surf, (0, 0))


def damage_wolf_entity(
    wolf: Dict[str, object],
    damage: float,
    damage_numbers: Optional[List[Dict[str, object]]] = None,
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
    if dealt > 0.0:
        wolf["chasing"] = True
        wolf["aggro_timer"] = max(float(wolf.get("aggro_timer", 0.0)), 3.5)
        if isinstance(damage_numbers, list):
            pos = hit_pos
            if not isinstance(pos, Vector2):
                pos_raw = wolf.get("pos")
                if isinstance(pos_raw, Vector2):
                    pos = Vector2(pos_raw)
            if isinstance(pos, Vector2):
                spawn_damage_number(damage_numbers, pos, dealt, kind="outgoing")
    return dealt


def draw_point_light(
    surface: pygame.Surface,
    sx: int,
    sy: int,
    color: Tuple[int, int, int],
    inner_radius: int,
    outer_radius: int,
    alpha: int = 80,
) -> None:
    """Draw a soft radial glow at screen coords (sx, sy) with additive-style blending."""
    if outer_radius <= 0:
        return
    glow = pygame.Surface((outer_radius * 2, outer_radius * 2), pygame.SRCALPHA)
    steps = max(4, outer_radius // 6)
    for i in range(steps, 0, -1):
        r = int(outer_radius * i / steps)
        t = 1.0 - (i / steps)  # 0 at edge, 1 at center
        a = int(alpha * (t ** 1.6))
        pygame.gfxdraw.filled_circle(glow, outer_radius, outer_radius, r, (color[0], color[1], color[2], a))
    # Bright core
    core_r = max(1, inner_radius)
    pygame.gfxdraw.filled_circle(glow, outer_radius, outer_radius, core_r, (min(255, color[0] + 60), min(255, color[1] + 50), min(255, color[2] + 30), min(255, alpha + 60)))
    surface.blit(glow, (sx - outer_radius, sy - outer_radius), special_flags=pygame.BLEND_RGBA_ADD)


def point_segment_distance_sq(point: Vector2, start: Vector2, end: Vector2) -> float:
    seg = end - start
    seg_len_sq = seg.length_squared()
    if seg_len_sq <= 1e-6:
        return point.distance_squared_to(start)
    t = clamp((point - start).dot(seg) / seg_len_sq, 0.0, 1.0)
    nearest = start + seg * t
    return point.distance_squared_to(nearest)


def circle_hits_segment(center: Vector2, radius: float, start: Vector2, end: Vector2) -> bool:
    rr = max(0.0, float(radius))
    return point_segment_distance_sq(center, start, end) <= rr * rr


class ParticleEmitter:
    def __init__(self) -> None:
        self.particles: List[Dict[str, object]] = []

    def burst(
        self,
        origin: Vector2,
        primary: Tuple[int, int, int],
        secondary: Tuple[int, int, int],
        count: int = 12,
        speed_min: float = 80.0,
        speed_max: float = 220.0,
        life_min: float = 0.16,
        life_max: float = 0.42,
        size_start: float = 4.0,
        size_end: float = 0.6,
        spread: float = math.tau,
        direction: Optional[Vector2] = None,
        gravity: float = 0.0,
        drag: float = 0.0,
        shape: str = "orb",
        alpha: int = 220,
        streak: float = 12.0,
    ) -> None:
        if count <= 0:
            return
        base_dir: Optional[Vector2] = None
        if isinstance(direction, Vector2) and direction.length_squared() > 1e-6:
            base_dir = direction.normalize()
        for _ in range(int(count)):
            if isinstance(base_dir, Vector2):
                if spread < math.tau - 0.001:
                    ang = random.uniform(-spread * 0.5, spread * 0.5)
                    vel_dir = rotate_vec(base_dir, ang)
                else:
                    vel_dir = rotate_vec(base_dir, random.uniform(0.0, math.tau))
            else:
                ang = random.uniform(0.0, math.tau)
                vel_dir = Vector2(math.cos(ang), math.sin(ang))
            speed = random.uniform(speed_min, speed_max)
            life = random.uniform(life_min, life_max)
            self.particles.append(
                {
                    "pos": Vector2(origin),
                    "vel": vel_dir * speed,
                    "life": life,
                    "duration": life,
                    "size0": max(0.4, size_start * random.uniform(0.82, 1.18)),
                    "size1": max(0.2, size_end * random.uniform(0.8, 1.2)),
                    "primary": primary,
                    "secondary": secondary,
                    "gravity": gravity,
                    "drag": max(0.0, drag),
                    "shape": shape,
                    "alpha": int(clamp(float(alpha) * random.uniform(0.78, 1.0), 12.0, 255.0)),
                    "streak": max(4.0, float(streak) * random.uniform(0.75, 1.25)),
                }
            )

    def update(self, dt: float) -> None:
        if dt <= 0.0 or not self.particles:
            return
        keep: List[Dict[str, object]] = []
        for particle in self.particles:
            life = float(particle.get("life", 0.0)) - dt
            if life <= 0.0:
                continue
            pos = particle.get("pos")
            vel = particle.get("vel")
            if not isinstance(pos, Vector2) or not isinstance(vel, Vector2):
                continue
            drag = max(0.0, float(particle.get("drag", 0.0)))
            if drag > 0.0:
                vel *= max(0.0, 1.0 - drag * dt)
            gravity = float(particle.get("gravity", 0.0))
            if gravity != 0.0:
                vel.y += gravity * dt
            pos += vel * dt
            particle["life"] = life
            particle["pos"] = pos
            particle["vel"] = vel
            keep.append(particle)
        self.particles = keep

    def draw(self, surface: pygame.Surface, camera: Vector2) -> None:
        for particle in self.particles:
            pos = particle.get("pos")
            vel = particle.get("vel")
            if not isinstance(pos, Vector2):
                continue
            life = float(particle.get("life", 0.0))
            duration = max(0.001, float(particle.get("duration", 1.0)))
            fade = clamp(life / duration, 0.0, 1.0)
            sx = int(pos.x - camera.x)
            sy = int(pos.y - camera.y)
            if sx < -40 or sx > SCREEN_WIDTH + 40 or sy < -40 or sy > SCREEN_HEIGHT + 40:
                continue
            c0 = particle.get("primary", (220, 220, 220))
            c1 = particle.get("secondary", (140, 140, 140))
            if not (isinstance(c0, tuple) and len(c0) == 3):
                c0 = (220, 220, 220)
            if not (isinstance(c1, tuple) and len(c1) == 3):
                c1 = (140, 140, 140)
            blend = 1.0 - fade
            color = (
                int(c0[0] + (c1[0] - c0[0]) * blend),
                int(c0[1] + (c1[1] - c0[1]) * blend),
                int(c0[2] + (c1[2] - c0[2]) * blend),
            )
            alpha = max(10, int(float(particle.get("alpha", 220)) * fade))
            rr = max(
                1,
                int(
                    float(particle.get("size1", 0.6))
                    + (float(particle.get("size0", 4.0)) - float(particle.get("size1", 0.6))) * fade
                ),
            )
            shape = str(particle.get("shape", "orb"))
            if shape == "spark" and isinstance(vel, Vector2) and vel.length_squared() > 1e-5:
                tail = vel.normalize() * max(4.0, float(particle.get("streak", 12.0))) * (0.45 + 0.55 * fade)
                ex = int(sx - tail.x)
                ey = int(sy - tail.y)
                pygame.draw.line(surface, color, (sx, sy), (ex, ey), 2 if rr > 2 else 1)
                pygame.gfxdraw.filled_circle(surface, sx, sy, max(1, rr - 1), (color[0], color[1], color[2], alpha))
            elif shape == "diamond":
                diamond = pygame.Surface((rr * 4, rr * 4), pygame.SRCALPHA)
                cx = diamond.get_width() // 2
                cy = diamond.get_height() // 2
                pts = [(cx, cy - rr), (cx + rr, cy), (cx, cy + rr), (cx - rr, cy)]
                pygame.draw.polygon(diamond, (color[0], color[1], color[2], alpha), pts)
                surface.blit(diamond, (sx - cx, sy - cy))
            else:
                pygame.gfxdraw.filled_circle(surface, sx, sy, rr + 2, (color[0], color[1], color[2], max(8, alpha // 4)))
                pygame.gfxdraw.filled_circle(surface, sx, sy, rr, (color[0], color[1], color[2], alpha))

    def alive(self) -> bool:
        return bool(self.particles)


class StatusEffect:
    def __init__(
        self,
        kind: str,
        duration: float,
        potency: float = 0.0,
        tick_interval: float = 0.0,
        color: Tuple[int, int, int] = (220, 220, 220),
    ) -> None:
        self.kind = str(kind)
        self.duration = max(0.0, float(duration))
        self.potency = float(potency)
        self.tick_interval = max(0.0, float(tick_interval))
        self.tick_timer = self.tick_interval
        self.color = color


class StatusEffectSystem:
    PLAYER_KEY = "player"

    def __init__(self) -> None:
        self.effects: Dict[str, List[StatusEffect]] = {}

    def wolf_key(self, wolf: Dict[str, object]) -> str:
        return f"wolf:{id(wolf)}"

    def add_effect(self, target_key: str, effect: StatusEffect) -> None:
        if effect.duration <= 0.0:
            return
        effects = self.effects.setdefault(str(target_key), [])
        if effect.kind == "burn":
            burns = [entry for entry in effects if entry.kind == "burn"]
            if len(burns) >= 3:
                weakest = min(burns, key=lambda entry: entry.potency * max(0.15, entry.duration))
                weakest.duration = max(weakest.duration, effect.duration)
                weakest.potency = max(weakest.potency, effect.potency)
                weakest.tick_interval = effect.tick_interval if effect.tick_interval > 0.0 else weakest.tick_interval
                weakest.tick_timer = min(weakest.tick_timer, max(0.01, weakest.tick_interval))
                weakest.color = effect.color
                return
            effects.append(effect)
            return
        for existing in effects:
            if existing.kind != effect.kind:
                continue
            if effect.kind == "shield":
                existing.potency += max(0.0, effect.potency)
                existing.duration = max(existing.duration, effect.duration)
            else:
                existing.potency = max(existing.potency, effect.potency)
                existing.duration = max(existing.duration, effect.duration)
                if effect.tick_interval > 0.0:
                    if existing.tick_interval <= 0.0:
                        existing.tick_interval = effect.tick_interval
                    else:
                        existing.tick_interval = min(existing.tick_interval, effect.tick_interval)
                    existing.tick_timer = min(existing.tick_timer, existing.tick_interval)
            existing.color = effect.color
            return
        effects.append(effect)

    def get_effects(self, target_key: str) -> List[StatusEffect]:
        return self.effects.get(str(target_key), [])

    def consume_effect(self, target_key: str, kind: str) -> Optional[StatusEffect]:
        effects = self.effects.get(str(target_key), [])
        for idx, effect in enumerate(effects):
            if effect.kind != kind:
                continue
            consumed = effects.pop(idx)
            if effects:
                self.effects[str(target_key)] = effects
            else:
                self.effects.pop(str(target_key), None)
            return consumed
        return None

    def move_multiplier(self, target_key: str) -> float:
        mult = 1.0
        for effect in self.get_effects(target_key):
            if effect.kind == "slow":
                mult *= clamp(1.0 - effect.potency, 0.15, 1.0)
            elif effect.kind == "freeze":
                mult = 0.0
        return clamp(mult, 0.0, 1.0)

    def is_disabled(self, target_key: str) -> bool:
        for effect in self.get_effects(target_key):
            if effect.kind in ("stun", "freeze"):
                return True
        return False

    def shield_value(self, target_key: str) -> float:
        total = 0.0
        for effect in self.get_effects(target_key):
            if effect.kind == "shield":
                total += max(0.0, effect.potency)
        return total

    def consume_shield(self, target_key: str, amount: float) -> float:
        remaining = max(0.0, float(amount))
        if remaining <= 0.0:
            return 0.0
        absorbed = 0.0
        effects = self.effects.get(str(target_key), [])
        for effect in effects:
            if effect.kind != "shield" or remaining <= 0.0:
                continue
            block = min(max(0.0, effect.potency), remaining)
            if block <= 0.0:
                continue
            effect.potency -= block
            remaining -= block
            absorbed += block
        self.effects[str(target_key)] = [
            entry for entry in effects if entry.duration > 0.0 and not (entry.kind == "shield" and entry.potency <= 0.0)
        ]
        if not self.effects[str(target_key)]:
            self.effects.pop(str(target_key), None)
        return absorbed

    def update(
        self,
        dt: float,
        wolves: List[Dict[str, object]],
        damage_numbers: Optional[List[Dict[str, object]]] = None,
        spell_effects: Optional[List[Dict[str, object]]] = None,
    ) -> None:
        live_wolves: Dict[str, Dict[str, object]] = {}
        for wolf in wolves:
            if float(wolf.get("hp", 0.0)) <= 0.0:
                continue
            live_wolves[self.wolf_key(wolf)] = wolf
        for target_key in list(self.effects.keys()):
            if target_key != self.PLAYER_KEY and target_key not in live_wolves:
                self.effects.pop(target_key, None)
        if dt < 0.0:
            dt = 0.0
        if dt > 0.0:
            for target_key, effects in list(self.effects.items()):
                target_wolf = live_wolves.get(target_key)
                keep: List[StatusEffect] = []
                for effect in effects:
                    effect.duration = max(0.0, effect.duration - dt)
                    if effect.duration <= 0.0:
                        continue
                    if effect.kind == "burn" and effect.tick_interval > 0.0 and isinstance(target_wolf, dict):
                        effect.tick_timer -= dt
                        while effect.tick_timer <= 0.0 and effect.duration > 0.0:
                            pos_raw = target_wolf.get("pos")
                            hit_pos = Vector2(pos_raw) if isinstance(pos_raw, Vector2) else None
                            dealt = damage_wolf_entity(target_wolf, effect.potency, damage_numbers, hit_pos)
                            if dealt > 0.0 and isinstance(spell_effects, list) and isinstance(hit_pos, Vector2):
                                # Fire tick — rising flame sparks
                                spawn_particle_burst(
                                    spell_effects, hit_pos,
                                    effect.color, (255, 240, 180),
                                    count=5, speed_min=30.0, speed_max=100.0,
                                    life_min=0.12, life_max=0.34,
                                    size_start=3.2, size_end=0.4,
                                    spread=math.tau,
                                    gravity=-40.0, drag=1.4,
                                    vfx_scale=0.8,
                                )
                                # Ember sparks arcing up
                                spawn_particle_burst(
                                    spell_effects,
                                    Vector2(hit_pos.x, hit_pos.y - 8),
                                    (255, 200, 80), (255, 140, 40),
                                    count=3, speed_min=60.0, speed_max=160.0,
                                    life_min=0.08, life_max=0.22,
                                    size_start=1.8, size_end=0.2,
                                    spread=1.2,
                                    direction=Vector2(0, -1),
                                    gravity=50.0, drag=2.2,
                                    vfx_scale=0.6,
                                )
                            effect.tick_timer += max(0.01, effect.tick_interval)
                    if effect.kind == "shield" and effect.potency <= 0.0:
                        continue
                    keep.append(effect)
                if keep:
                    self.effects[target_key] = keep
                else:
                    self.effects.pop(target_key, None)
        for wolf in wolves:
            wolf["status_move_mult"] = 1.0
            wolf["status_disabled"] = False
            if float(wolf.get("hp", 0.0)) <= 0.0:
                wolf.pop("freeze_anchor", None)
                continue
            key = self.wolf_key(wolf)
            if key not in self.effects:
                wolf.pop("freeze_anchor", None)
                continue
            active = self.effects.get(key, [])
            is_frozen = any(entry.kind == "freeze" for entry in active)
            wolf["status_move_mult"] = self.move_multiplier(key)
            wolf["status_disabled"] = self.is_disabled(key)
            if is_frozen:
                pos_raw = wolf.get("pos")
                anchor_raw = wolf.get("freeze_anchor")
                if not isinstance(anchor_raw, Vector2) and isinstance(pos_raw, Vector2):
                    wolf["freeze_anchor"] = Vector2(pos_raw)
                    anchor_raw = wolf["freeze_anchor"]
                if isinstance(anchor_raw, Vector2):
                    wolf["pos"] = Vector2(anchor_raw)
                wolf["queued_strike"] = False
                wolf["attack_state"] = "idle"
                wolf["attack_timer"] = 0.0
                wolf["attack_visual"] = 0.0
            else:
                wolf.pop("freeze_anchor", None)

    def clear(self, wolves: Optional[List[Dict[str, object]]] = None) -> None:
        self.effects.clear()
        if isinstance(wolves, list):
            for wolf in wolves:
                wolf["status_move_mult"] = 1.0
                wolf["status_disabled"] = False
                wolf.pop("freeze_anchor", None)


class ScreenEffectController:
    def __init__(self) -> None:
        self.flashes: List[Dict[str, object]] = []

    def flash(
        self,
        color: Tuple[int, int, int],
        alpha: int = 100,
        duration: float = 0.16,
        additive: bool = True,
    ) -> None:
        self.flashes.append(
            {
                "color": color,
                "alpha": max(8, min(255, int(alpha))),
                "life": max(0.02, float(duration)),
                "duration": max(0.02, float(duration)),
                "additive": bool(additive),
            }
        )

    def update(self, dt: float) -> None:
        if dt <= 0.0 or not self.flashes:
            return
        keep: List[Dict[str, object]] = []
        for flash in self.flashes:
            flash["life"] = float(flash.get("life", 0.0)) - dt
            if float(flash.get("life", 0.0)) > 0.0:
                keep.append(flash)
        self.flashes = keep

    def draw(self, surface: pygame.Surface) -> None:
        for flash in self.flashes:
            life = float(flash.get("life", 0.0))
            duration = max(0.001, float(flash.get("duration", 0.1)))
            fade = clamp(life / duration, 0.0, 1.0)
            color = flash.get("color", (255, 255, 255))
            if not (isinstance(color, tuple) and len(color) == 3):
                color = (255, 255, 255)
            alpha = max(0, int(float(flash.get("alpha", 100)) * fade))
            if alpha <= 0:
                continue
            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            overlay.fill((color[0], color[1], color[2], alpha))
            if bool(flash.get("additive", True)):
                surface.blit(overlay, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
            else:
                surface.blit(overlay, (0, 0))

    def clear(self) -> None:
        self.flashes.clear()


class QuestCelebrationVFX:
    """Button-anchored celebration: particles burst from the Complete Quest button."""

    def __init__(self) -> None:
        self.particles: List[Dict[str, float]] = []
        self.active = False
        self.timer = 0.0
        self.btn_rect: Optional[pygame.Rect] = None

    def trigger(self, btn_rect: Optional[pygame.Rect] = None) -> None:
        """Start celebration from the button position."""
        self.active = True
        self.timer = 1.6
        self.particles.clear()
        # Default to screen center if no rect
        if btn_rect:
            cx = btn_rect.centerx
            cy = btn_rect.centery
            self.btn_rect = pygame.Rect(btn_rect)
        else:
            cx, cy = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
            self.btn_rect = None
        rng = random.Random()
        # Golden motes rising upward from button
        for _ in range(30):
            self.particles.append({
                "x": float(cx + rng.uniform(-60, 60)),
                "y": float(cy + rng.uniform(-8, 8)),
                "vx": rng.uniform(-20, 20),
                "vy": rng.uniform(-120, -50),
                "life": rng.uniform(0.8, 1.5),
                "max_life": 0.0,
                "size": rng.uniform(2, 4),
                "cr": rng.uniform(220, 255), "cg": rng.uniform(180, 230), "cb": rng.uniform(30, 80),
                "kind": "rise",
                "drift": rng.uniform(-10, 10),
                "phase": rng.uniform(0, 6.28),
            })
        # Sparkle burst outward from button edges
        for _ in range(24):
            angle = rng.uniform(0, 2 * math.pi)
            speed = rng.uniform(60, 180)
            self.particles.append({
                "x": float(cx + math.cos(angle) * 40),
                "y": float(cy + math.sin(angle) * 10),
                "vx": math.cos(angle) * speed,
                "vy": math.sin(angle) * speed * 0.5 - rng.uniform(20, 50),
                "life": rng.uniform(0.5, 1.0),
                "max_life": 0.0,
                "size": rng.uniform(1.5, 3.5),
                "cr": 255, "cg": rng.uniform(220, 255), "cb": rng.uniform(120, 200),
                "kind": "burst",
                "drift": 0.0, "phase": 0.0,
            })
        for p in self.particles:
            p["max_life"] = p["life"]

    def update(self, dt: float) -> None:
        if not self.active:
            return
        self.timer -= dt
        if self.timer <= 0:
            self.active = False
            self.particles.clear()
            return
        keep = []
        for p in self.particles:
            p["life"] -= dt
            if p["life"] <= 0:
                continue
            if p["kind"] == "rise":
                p["x"] += (p["vx"] + math.sin(p["life"] * 4 + p["phase"]) * p["drift"]) * dt
                p["y"] += p["vy"] * dt
            else:
                p["x"] += p["vx"] * dt
                p["y"] += p["vy"] * dt
                p["vx"] *= 0.97
                p["vy"] *= 0.97
            keep.append(p)
        self.particles = keep

    def draw(self, surface: pygame.Surface) -> None:
        if not self.active:
            return
        # Soft glow behind button area during effect
        if self.btn_rect and self.timer > 0.5:
            glow_a = int(50 * min(1.0, (self.timer - 0.5) / 0.5))
            gw, gh = self.btn_rect.width + 40, self.btn_rect.height + 30
            gs = pygame.Surface((gw, gh), pygame.SRCALPHA)
            pygame.draw.ellipse(gs, (255, 220, 80, glow_a), (0, 0, gw, gh))
            surface.blit(gs, (self.btn_rect.centerx - gw // 2, self.btn_rect.centery - gh // 2),
                         special_flags=pygame.BLEND_RGBA_ADD)
        # Particles
        for p in self.particles:
            fade = max(0.0, p["life"] / max(0.01, p["max_life"]))
            alpha = int(230 * fade)
            size = max(1, int(p["size"] * (0.4 + 0.6 * fade)))
            ps = pygame.Surface((size * 2 + 2, size * 2 + 2), pygame.SRCALPHA)
            pygame.draw.circle(ps, (int(p["cr"]), int(p["cg"]), int(p["cb"]), alpha),
                               (size + 1, size + 1), size)
            surface.blit(ps, (int(p["x"]) - size - 1, int(p["y"]) - size - 1),
                         special_flags=pygame.BLEND_RGBA_ADD)


class LevelUpVFX:
    """Minimalist but intense level-up VFX — pillar, ring, rising motes, sparkles."""

    def __init__(self) -> None:
        self.active = False
        self.timer = 0.0
        self.max_time = 3.0
        self.player_level = 0
        self.pillar_particles: List[Dict[str, float]] = []
        self.ring_particles: List[Dict[str, float]] = []
        self.sparkles: List[Dict[str, float]] = []
        self.text_alpha = 0.0
        self.text_scale = 0.0
        self._rng = random.Random()

    def trigger(self, level: int) -> None:
        self.active = True
        self.timer = 0.0
        self.player_level = level
        self.pillar_particles.clear()
        self.ring_particles.clear()
        self.sparkles.clear()
        self.text_alpha = 0.0
        self.text_scale = 0.0
        rng = self._rng
        # Rising golden motes from feet
        for _ in range(60):
            self.pillar_particles.append({
                "ox": rng.uniform(-28, 28),
                "vy": rng.uniform(-180, -400),
                "life": rng.uniform(0.6, 1.8),
                "max_life": 0.0,
                "delay": rng.uniform(0.0, 0.5),
                "size": rng.uniform(2.0, 5.0),
                "cr": rng.uniform(220, 255), "cg": rng.uniform(180, 230), "cb": rng.uniform(40, 100),
                "drift": rng.uniform(-15, 15),
                "phase": rng.uniform(0, 6.28),
            })
        for p in self.pillar_particles:
            p["max_life"] = p["life"]
        # Ring burst particles
        for _ in range(40):
            angle = rng.uniform(0, 2 * math.pi)
            speed = rng.uniform(100, 280)
            self.ring_particles.append({
                "vx": math.cos(angle) * speed,
                "vy": math.sin(angle) * speed * 0.4,
                "life": rng.uniform(0.5, 1.2),
                "max_life": 0.0,
                "delay": rng.uniform(0.2, 0.6),
                "size": rng.uniform(1.5, 4.0),
                "cr": rng.uniform(200, 255), "cg": rng.uniform(200, 255), "cb": rng.uniform(100, 200),
            })
        for p in self.ring_particles:
            p["max_life"] = p["life"]
        # Cross-shaped sparkles
        for _ in range(30):
            self.sparkles.append({
                "ox": rng.uniform(-60, 60),
                "oy": rng.uniform(-120, -20),
                "life": rng.uniform(1.0, 2.5),
                "max_life": 0.0,
                "delay": rng.uniform(0.3, 1.2),
                "twinkle_speed": rng.uniform(6, 14),
                "size": rng.uniform(1.5, 3.5),
                "phase": rng.uniform(0, 6.28),
            })
        for p in self.sparkles:
            p["max_life"] = p["life"]

    def update(self, dt: float) -> None:
        if not self.active:
            return
        self.timer += dt
        if self.timer > self.max_time:
            self.active = False
            return
        t = self.timer
        # Text: smooth scale punch then hold then fade
        if t < 0.4:
            p = t / 0.4
            self.text_scale = 1.0 + 0.3 * math.sin(p * math.pi)
            self.text_alpha = min(255, p * 400)
        elif t < 0.7:
            self.text_scale = 1.0 + 0.05 * math.sin((t - 0.4) / 0.3 * math.pi)
            self.text_alpha = 255
        elif t < 2.2:
            self.text_scale = 1.0
            self.text_alpha = 255
        else:
            fade = (t - 2.2) / 0.8
            self.text_scale = 1.0
            self.text_alpha = max(0, 255 * (1.0 - fade * fade))

    def draw(self, surface: pygame.Surface, px: float, py: float, font: pygame.font.Font) -> None:
        if not self.active:
            return
        t = self.timer
        cx = int(px)
        cy = int(py)
        foot_y = cy + 16

        # === Golden light pillar ===
        if t < 2.0:
            fade_in = min(1.0, t / 0.3)
            fade_out = max(0.0, 1.0 - max(0, t - 1.2) / 0.8)
            pillar_alpha = int(80 * fade_in * fade_out)
            if pillar_alpha > 0:
                pillar_w = 50 + int(20 * math.sin(t * 3))
                pillar_h = 200
                ps = pygame.Surface((pillar_w, pillar_h), pygame.SRCALPHA)
                for row in range(pillar_h):
                    row_t = row / pillar_h
                    a = int(pillar_alpha * (1.0 - row_t) * (0.6 + 0.4 * math.sin(row_t * 6 + t * 4)))
                    w_at_row = int(pillar_w * (0.3 + 0.7 * (1.0 - row_t)))
                    x_off = (pillar_w - w_at_row) // 2
                    pygame.draw.line(ps, (255, 220, 80, max(0, min(255, a))),
                                     (x_off, pillar_h - 1 - row), (x_off + w_at_row, pillar_h - 1 - row))
                surface.blit(ps, (cx - pillar_w // 2, foot_y - pillar_h), special_flags=pygame.BLEND_RGBA_ADD)

        # === Expanding ground ring ===
        if 0.15 < t < 1.5:
            ring_t = (t - 0.15) / 1.35
            ease_t = 1.0 - (1.0 - ring_t) ** 3
            ring_r = int(20 + 120 * ease_t)
            ring_alpha = int(150 * math.sin(ring_t * math.pi))
            ring_h = max(1, int(ring_r * 0.35))
            rs = pygame.Surface((ring_r * 2 + 4, ring_h * 2 + 4), pygame.SRCALPHA)
            col = (255, 230, 100, max(0, min(255, ring_alpha)))
            pygame.draw.ellipse(rs, col, (2, 2, ring_r * 2, ring_h * 2), 2)
            if ring_r > 10:
                inner_col = (255, 240, 150, max(0, min(255, ring_alpha // 2)))
                pygame.draw.ellipse(rs, inner_col, (6, 6, ring_r * 2 - 8, ring_h * 2 - 8), 1)
            surface.blit(rs, (cx - ring_r - 2, foot_y - ring_h - 2), special_flags=pygame.BLEND_RGBA_ADD)

        # === Rising golden motes ===
        for p in self.pillar_particles:
            age = t - p["delay"]
            if age < 0 or age > p["max_life"]:
                continue
            life_t = age / p["max_life"]
            fade = math.sin(life_t * math.pi)
            px2 = cx + p["ox"] + math.sin(age * 3 + p["phase"]) * p["drift"]
            py2 = foot_y + p["vy"] * age
            alpha = int(255 * fade)
            size = max(1, int(p["size"] * (0.5 + 0.5 * fade)))
            ps = pygame.Surface((size * 2 + 2, size * 2 + 2), pygame.SRCALPHA)
            pygame.draw.circle(ps, (int(p["cr"]), int(p["cg"]), int(p["cb"]), alpha),
                               (size + 1, size + 1), size)
            surface.blit(ps, (int(px2) - size - 1, int(py2) - size - 1), special_flags=pygame.BLEND_RGBA_ADD)

        # === Ring burst particles ===
        for p in self.ring_particles:
            age = t - p["delay"]
            if age < 0 or age > p["max_life"]:
                continue
            life_t = age / p["max_life"]
            fade = math.sin(life_t * math.pi)
            rx = cx + p["vx"] * age
            ry = foot_y + p["vy"] * age
            alpha = int(200 * fade)
            size = max(1, int(p["size"] * (0.3 + 0.7 * fade)))
            ps = pygame.Surface((size * 2 + 2, size * 2 + 2), pygame.SRCALPHA)
            pygame.draw.circle(ps, (int(p["cr"]), int(p["cg"]), int(p["cb"]), alpha),
                               (size + 1, size + 1), size)
            surface.blit(ps, (int(rx) - size - 1, int(ry) - size - 1), special_flags=pygame.BLEND_RGBA_ADD)

        # === Twinkling sparkles ===
        for p in self.sparkles:
            age = t - p["delay"]
            if age < 0 or age > p["max_life"]:
                continue
            life_t = age / p["max_life"]
            fade = math.sin(life_t * math.pi)
            twinkle = 0.5 + 0.5 * math.sin(age * p["twinkle_speed"] + p["phase"])
            alpha = int(220 * fade * twinkle)
            if alpha < 5:
                continue
            sx = cx + p["ox"] + math.sin(age * 1.5 + p["phase"]) * 8
            sy = cy + p["oy"] - age * 20
            size = max(1, int(p["size"] * twinkle))
            ss = pygame.Surface((size * 4 + 2, size * 4 + 2), pygame.SRCALPHA)
            sc = (255, 255, 220, alpha)
            center = size * 2 + 1
            pygame.draw.line(ss, sc, (center - size * 2, center), (center + size * 2, center), 1)
            pygame.draw.line(ss, sc, (center, center - size * 2), (center, center + size * 2), 1)
            pygame.draw.circle(ss, (255, 255, 200, min(255, alpha + 30)), (center, center), max(1, size // 2))
            surface.blit(ss, (int(sx) - center, int(sy) - center), special_flags=pygame.BLEND_RGBA_ADD)

        # === "Level X!" text ===
        if self.text_alpha > 5:
            txt = f"Level {self.player_level}!"
            ts = font.render(txt, True, (255, 230, 100))
            if self.text_scale > 0.1 and abs(self.text_scale - 1.0) > 0.01:
                new_w = max(1, int(ts.get_width() * self.text_scale))
                new_h = max(1, int(ts.get_height() * self.text_scale))
                ts = pygame.transform.smoothscale(ts, (new_w, new_h))
            ts_shadow = font.render(txt, True, (40, 20, 0))
            if self.text_scale > 0.1 and abs(self.text_scale - 1.0) > 0.01:
                ts_shadow = pygame.transform.smoothscale(ts_shadow, (ts.get_width(), ts.get_height()))
            alpha_int = max(0, min(255, int(self.text_alpha)))
            ts.set_alpha(alpha_int)
            ts_shadow.set_alpha(max(0, alpha_int - 40))
            tx = cx - ts.get_width() // 2
            float_up = int(20 * min(1.0, self.timer / 0.6))
            ty = cy - 120 - float_up - ts.get_height() // 2
            surface.blit(ts_shadow, (tx + 2, ty + 2))
            surface.blit(ts, (tx, ty))


class CameraDirector:
    def __init__(self, initial: Vector2) -> None:
        self.position = Vector2(initial)
        self.shake_strength = 0.0
        self.shake_time = 0.0
        self.shake_duration = 0.1
        self.seed = random.random() * math.tau

    def jump_to(self, pos: Vector2) -> None:
        self.position = Vector2(pos)
        self.shake_time = 0.0
        self.shake_strength = max(0.0, self.shake_strength * 0.4)

    def impulse(self, strength: float = 4.0, duration: float = 0.12) -> None:
        self.shake_strength = max(self.shake_strength, max(0.0, float(strength)))
        self.shake_duration = max(0.04, float(duration))
        self.shake_time = self.shake_duration

    def update(
        self,
        dt: float,
        target: Vector2,
        world_width: int,
        world_height: int,
        smooth: bool = True,
    ) -> Vector2:
        max_x = max(0.0, float(int(world_width) - SCREEN_WIDTH))
        max_y = max(0.0, float(int(world_height) - SCREEN_HEIGHT))
        goal_x = clamp(float(target.x), 0.0, max_x)
        goal_y = clamp(float(target.y), 0.0, max_y)

        if smooth and dt > 0.0:
            self.position.x = exp_smooth(self.position.x, goal_x, 11.6, dt)
            self.position.y = exp_smooth(self.position.y, goal_y, 10.8, dt)
        else:
            self.position.x = goal_x
            self.position.y = goal_y

        self.position.x = clamp(self.position.x, 0.0, max_x)
        self.position.y = clamp(self.position.y, 0.0, max_y)
        self.shake_time = max(0.0, self.shake_time - max(0.0, dt))
        return self.get_render_position()

    def get_render_position(self) -> Vector2:
        out = Vector2(self.position)
        if self.shake_time <= 0.0 or self.shake_strength <= 0.05:
            return out
        fade = clamp(self.shake_time / max(0.001, self.shake_duration), 0.0, 1.0)
        amp = self.shake_strength * (fade ** 1.15)
        ticks = pygame.time.get_ticks() * 0.045 + self.seed
        out.x += math.sin(ticks * 1.93) * amp
        out.y += math.cos(ticks * 2.31) * amp * 0.78
        return out


class AmbientOverlaySystem:
    def __init__(self) -> None:
        self.rng = random.Random(random.randrange(1_000_000_000))
        self.level = "town"
        self.particles: List[Dict[str, float]] = []
        self.layer = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)

    def _target_count(self, level: str, cloud_cover: float, precipitation: float, fog_density: float) -> int:
        level_key = str(level).strip().lower()
        if level_key == "ice_biome":
            base = 58
        elif level_key == "wilderness":
            base = 66
        else:
            base = 52
        cloud_bonus = int(clamp(cloud_cover, 0.0, 1.0) * 14.0)
        fog_bonus = int(clamp(fog_density, 0.0, 1.0) * 18.0)
        rain_penalty = int(clamp(precipitation, 0.0, 1.0) * 16.0)
        return int(clamp(float(base + cloud_bonus + fog_bonus - rain_penalty), 26.0, 92.0))

    def _spawn_particle(self, level: str, initial: bool = False) -> Dict[str, float]:
        level_key = str(level).strip().lower()
        if level_key == "town":
            y = self.rng.uniform(-10.0, SCREEN_HEIGHT + 30.0) if initial else self.rng.uniform(SCREEN_HEIGHT + 4.0, SCREEN_HEIGHT + 44.0)
            return {
                "x": self.rng.uniform(-12.0, SCREEN_WIDTH + 12.0),
                "y": y,
                "vx": self.rng.uniform(-10.0, 10.0),
                "vy": -self.rng.uniform(12.0, 34.0),
                "size": self.rng.uniform(1.0, 2.6),
                "alpha": self.rng.uniform(62.0, 132.0),
                "phase": self.rng.uniform(0.0, math.tau),
                "twinkle": self.rng.uniform(1.1, 2.7),
                "mode": 0.0,  # ember
            }
        if level_key == "ice_biome":
            y = self.rng.uniform(-16.0, SCREEN_HEIGHT + 20.0) if initial else self.rng.uniform(-20.0, -4.0)
            return {
                "x": self.rng.uniform(-24.0, SCREEN_WIDTH + 24.0),
                "y": y,
                "vx": self.rng.uniform(-14.0, 14.0),
                "vy": self.rng.uniform(20.0, 54.0),
                "size": self.rng.uniform(1.0, 2.8),
                "alpha": self.rng.uniform(58.0, 142.0),
                "phase": self.rng.uniform(0.0, math.tau),
                "twinkle": self.rng.uniform(0.8, 1.9),
                "mode": 1.0,  # frost
            }
        side_left = self.rng.random() < 0.5
        x = self.rng.uniform(-20.0, SCREEN_WIDTH + 20.0) if initial else (-26.0 if side_left else SCREEN_WIDTH + 26.0)
        return {
            "x": x,
            "y": self.rng.uniform(HORIZON_Y - 26.0, SCREEN_HEIGHT + 30.0),
            "vx": self.rng.uniform(10.0, 40.0) * (1.0 if side_left else -1.0),
            "vy": self.rng.uniform(-6.0, 6.0),
            "size": self.rng.uniform(1.0, 2.2),
            "alpha": self.rng.uniform(46.0, 118.0),
            "phase": self.rng.uniform(0.0, math.tau),
            "twinkle": self.rng.uniform(0.9, 2.2),
            "mode": 2.0,  # pollen/dust
        }

    def update(self, dt: float, level: str, cloud_cover: float, precipitation: float, fog_density: float, wind: float) -> None:
        if dt <= 0.0:
            return
        level_key = str(level).strip().lower()
        target_count = self._target_count(level_key, cloud_cover, precipitation, fog_density)
        if level_key != self.level:
            self.level = level_key
            self.particles.clear()
        while len(self.particles) < target_count:
            self.particles.append(self._spawn_particle(level_key, initial=True))
        if len(self.particles) > target_count:
            del self.particles[target_count:]

        wind_push = float(wind) * 0.065
        for particle in self.particles:
            mode = int(float(particle.get("mode", 0.0)))
            particle["phase"] = (float(particle.get("phase", 0.0)) + float(particle.get("twinkle", 1.0)) * dt) % math.tau
            particle["x"] += (float(particle.get("vx", 0.0)) + wind_push) * dt
            particle["y"] += float(particle.get("vy", 0.0)) * dt
            if mode == 0:
                particle["x"] += math.sin(particle["phase"] * 1.4) * 6.0 * dt
            elif mode == 1:
                particle["x"] += math.sin(particle["phase"] * 1.6) * 8.0 * dt
            else:
                particle["y"] += math.sin(particle["phase"]) * 4.0 * dt

            x = float(particle.get("x", 0.0))
            y = float(particle.get("y", 0.0))
            if mode == 0:
                dead = y < -24.0 or x < -40.0 or x > SCREEN_WIDTH + 40.0
            elif mode == 1:
                dead = y > SCREEN_HEIGHT + 16.0 or x < -34.0 or x > SCREEN_WIDTH + 34.0
            else:
                dead = y < HORIZON_Y - 40.0 or y > SCREEN_HEIGHT + 24.0 or x < -34.0 or x > SCREEN_WIDTH + 34.0
            if dead:
                particle.clear()
                particle.update(self._spawn_particle(level_key, initial=False))

    def draw(
        self,
        surface: pygame.Surface,
        level: str,
        cloud_cover: float,
        precipitation: float,
        fog_density: float,
        day_time: float,
    ) -> None:
        if not self.particles:
            return
        level_key = str(level).strip().lower()
        hour = float(day_time) % 24.0
        if 6.0 <= hour < 18.0:
            night_factor = 0.0
        elif 18.0 <= hour < 20.0:
            night_factor = (hour - 18.0) / 2.0
        elif 5.0 <= hour < 7.0:
            night_factor = 1.0 - (hour - 5.0) / 2.0
        else:
            night_factor = 1.0
        weather_dampen = 1.0 - clamp(float(precipitation), 0.0, 1.0) * 0.38
        fog_boost = 0.9 + clamp(float(fog_density), 0.0, 1.0) * 0.3
        self.layer.fill((0, 0, 0, 0))
        for particle in self.particles:
            mode = int(float(particle.get("mode", 0.0)))
            twinkle = 0.58 + 0.42 * math.sin(float(particle.get("phase", 0.0)))
            alpha = int(float(particle.get("alpha", 70.0)) * twinkle * weather_dampen * fog_boost)
            if alpha <= 8:
                continue
            if level_key == "town":
                light_boost = 0.72 + night_factor * 0.62
                color = (246, 166, 94, int(alpha * light_boost))
            elif level_key == "ice_biome":
                light_boost = 0.86 + night_factor * 0.34 + clamp(float(cloud_cover), 0.0, 1.0) * 0.15
                color = (210, 236, 255, int(alpha * light_boost))
            else:
                light_boost = 0.74 + clamp(float(cloud_cover), 0.0, 1.0) * 0.34
                color = (188, 208, 160, int(alpha * light_boost))

            px = int(float(particle.get("x", 0.0)))
            py = int(float(particle.get("y", 0.0)))
            radius = max(1, int(float(particle.get("size", 1.0))))
            pygame.gfxdraw.filled_circle(self.layer, px, py, radius, color)
            if radius > 1 and mode != 0:
                pygame.gfxdraw.aacircle(self.layer, px, py, radius, color)
        surface.blit(self.layer, (0, 0))
