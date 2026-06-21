from __future__ import annotations

import glob
import math
import os
import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import pygame
import pygame.gfxdraw
from pygame import Vector2

from game.utils import clamp, lerp


Color = Tuple[int, int, int]


def _color_lerp(a: Color, b: Color, t: float) -> Color:
    tt = clamp(t, 0.0, 1.0)
    return (
        int(lerp(a[0], b[0], tt)),
        int(lerp(a[1], b[1], tt)),
        int(lerp(a[2], b[2], tt)),
    )


@dataclass
class Particle:
    pos: Vector2
    vel: Vector2
    life: float
    duration: float
    size0: float
    size1: float
    color0: Color
    color1: Color
    gravity: float = 0.0
    drag: float = 0.0
    layer: str = "world"

    @property
    def alive(self) -> bool:
        return self.life > 0.0

    def update(self, dt: float) -> None:
        self.life = max(0.0, self.life - dt)
        if self.life <= 0.0:
            return
        if self.drag > 0.0:
            self.vel *= max(0.0, 1.0 - self.drag * dt)
        if self.gravity != 0.0:
            self.vel.y += self.gravity * dt
        self.pos += self.vel * dt

    def draw(self, surface: pygame.Surface, camera: Vector2) -> None:
        fade = clamp(self.life / max(0.001, self.duration), 0.0, 1.0)
        color = _color_lerp(self.color1, self.color0, fade)
        radius = max(1, int(lerp(self.size1, self.size0, fade)))
        alpha = max(18, int(210 * fade))
        sx = int(self.pos.x - camera.x)
        sy = int(self.pos.y - camera.y)
        if sx < -40 or sy < -40 or sx > surface.get_width() + 40 or sy > surface.get_height() + 40:
            return
        pygame.gfxdraw.filled_circle(surface, sx, sy, radius + 2, (color[0], color[1], color[2], max(8, alpha // 5)))
        pygame.gfxdraw.filled_circle(surface, sx, sy, radius, (color[0], color[1], color[2], alpha))


@dataclass
class TrailSegment:
    start: Vector2
    end: Vector2
    life: float
    duration: float
    width0: float
    width1: float
    color0: Color
    color1: Color
    layer: str = "world"

    @property
    def alive(self) -> bool:
        return self.life > 0.0

    def update(self, dt: float) -> None:
        self.life = max(0.0, self.life - dt)

    def draw(self, surface: pygame.Surface, camera: Vector2) -> None:
        fade = clamp(self.life / max(0.001, self.duration), 0.0, 1.0)
        width = max(1, int(lerp(self.width1, self.width0, fade)))
        color = _color_lerp(self.color1, self.color0, fade)
        alpha = max(12, int(170 * fade))
        ax = int(self.start.x - camera.x)
        ay = int(self.start.y - camera.y)
        bx = int(self.end.x - camera.x)
        by = int(self.end.y - camera.y)
        pygame.draw.line(surface, (color[0], color[1], color[2], alpha), (ax, ay), (bx, by), width)


@dataclass
class GroundTelegraph:
    pos: Vector2
    radius: float
    life: float
    duration: float
    color: Color
    outline: Color
    fill_alpha: int = 36
    pulse: float = 7.5
    layer: str = "ground"

    @property
    def alive(self) -> bool:
        return self.life > 0.0

    def update(self, dt: float) -> None:
        self.life = max(0.0, self.life - dt)

    def draw(self, surface: pygame.Surface, camera: Vector2) -> None:
        fade = clamp(self.life / max(0.001, self.duration), 0.0, 1.0)
        phase = pygame.time.get_ticks() * 0.006
        pulse = 1.0 + math.sin(phase + self.pos.x * 0.01) * 0.05 * self.pulse
        rx = max(12, int(self.radius * pulse))
        ry = max(8, int(self.radius * 0.58 * pulse))
        sx = int(self.pos.x - camera.x)
        sy = int(self.pos.y - camera.y)
        telegraph = pygame.Surface((rx * 2 + 18, ry * 2 + 18), pygame.SRCALPHA)
        cx = telegraph.get_width() // 2
        cy = telegraph.get_height() // 2
        pygame.gfxdraw.filled_ellipse(
            telegraph,
            cx,
            cy,
            rx,
            ry,
            (self.color[0], self.color[1], self.color[2], int(self.fill_alpha * fade)),
        )
        pygame.gfxdraw.ellipse(
            telegraph,
            cx,
            cy,
            rx,
            ry,
            (self.outline[0], self.outline[1], self.outline[2], int(180 * fade)),
        )
        pygame.gfxdraw.ellipse(
            telegraph,
            cx,
            cy,
            max(8, rx - 8),
            max(4, ry - 5),
            (self.color[0], self.color[1], self.color[2], int(110 * fade)),
        )
        surface.blit(telegraph, (sx - cx, sy - cy))


@dataclass
class PulseRing:
    pos: Vector2
    radius0: float
    radius1: float
    life: float
    duration: float
    color: Color
    width: int = 2
    layer: str = "world"

    @property
    def alive(self) -> bool:
        return self.life > 0.0

    def update(self, dt: float) -> None:
        self.life = max(0.0, self.life - dt)

    def draw(self, surface: pygame.Surface, camera: Vector2) -> None:
        fade = clamp(self.life / max(0.001, self.duration), 0.0, 1.0)
        radius = max(4, int(lerp(self.radius1, self.radius0, fade)))
        alpha = max(14, int(190 * fade))
        sx = int(self.pos.x - camera.x)
        sy = int(self.pos.y - camera.y)
        pygame.gfxdraw.aacircle(surface, sx, sy, radius, (self.color[0], self.color[1], self.color[2], alpha))
        if radius > 5:
            pygame.gfxdraw.aacircle(surface, sx, sy, max(1, radius - self.width), (self.color[0], self.color[1], self.color[2], max(10, alpha // 2)))


@dataclass
class SpriteAnimation:
    frames: Sequence[pygame.Surface]
    pos: Vector2
    life: float
    duration: float
    scale: float = 1.0
    layer: str = "world"
    pixel_art: bool = False
    anchor: str = "center"

    @property
    def alive(self) -> bool:
        return self.life > 0.0

    def update(self, dt: float) -> None:
        self.life = max(0.0, self.life - dt)

    def draw(self, surface: pygame.Surface, camera: Vector2) -> None:
        if not self.frames:
            return
        progress = 1.0 - clamp(self.life / max(0.001, self.duration), 0.0, 1.0)
        idx = min(len(self.frames) - 1, int(progress * len(self.frames)))
        frame = self.frames[idx]
        if self.scale != 1.0:
            size = (
                max(8, int(frame.get_width() * self.scale)),
                max(8, int(frame.get_height() * self.scale)),
            )
            if self.pixel_art:
                frame = pygame.transform.scale(frame, size)
            else:
                frame = pygame.transform.smoothscale(frame, size)
        anchor_x = int(self.pos.x - camera.x)
        anchor_y = int(self.pos.y - camera.y)
        if self.anchor == "midbottom":
            rect = frame.get_rect(midbottom=(anchor_x, anchor_y))
        else:
            rect = frame.get_rect(center=(anchor_x, anchor_y))
        surface.blit(frame, rect)


class VFXManager:
    def __init__(self) -> None:
        self.effects: List[object] = []
        self._sprite_cache: Dict[str, List[pygame.Surface]] = {}
        self._animation_paths = {
            "bolt_cast_flash": os.path.join("assets_generated", "medieval_rpg", "vfx", "spells", "bolt_cast_flash_*.png"),
            "bolt_impact": os.path.join("assets_generated", "medieval_rpg", "vfx", "spells", "bolt_impact_*.png"),
            "foozle_fire_ball":    os.path.join("assets", "Foozle_2DE0001_Pixel_Magic_Effects", "Fire_Ball",    "*.png"),
            "foozle_water_geyser": os.path.join("assets", "Foozle_2DE0001_Pixel_Magic_Effects", "Water_Geyser", "*.png"),
            "foozle_portal":       os.path.join("assets", "Foozle_2DE0001_Pixel_Magic_Effects", "Portal",       "*.png"),
            "foozle_explosion":    os.path.join("assets", "Foozle_2DE0001_Pixel_Magic_Effects", "Explosion",    "*.png"),
            "foozle_earth_spike":  os.path.join("assets", "Foozle_2DE0001_Pixel_Magic_Effects", "Earth_Spike",  "*.png"),
            "foozle_molten_spear": os.path.join("assets", "Foozle_2DE0001_Pixel_Magic_Effects", "Molten_Spear", "*.png"),
            "foozle_rocks":        os.path.join("assets", "Foozle_2DE0001_Pixel_Magic_Effects", "Rocks",        "*.png"),
            "foozle_tornado":      os.path.join("assets", "Foozle_2DE0001_Pixel_Magic_Effects", "Tornado",      "*.png"),
            "foozle_water":        os.path.join("assets", "Foozle_2DE0001_Pixel_Magic_Effects", "Water",        "*.png"),
            "foozle_wind":         os.path.join("assets", "Foozle_2DE0001_Pixel_Magic_Effects", "Wind",         "*.png"),
        }

    def clear(self) -> None:
        self.effects.clear()

    def _load_frames(self, name: str) -> List[pygame.Surface]:
        if name in self._sprite_cache:
            return self._sprite_cache[name]
        pattern = self._animation_paths.get(name)
        frames: List[pygame.Surface] = []
        if pattern:
            for path in sorted(glob.glob(pattern)):
                try:
                    frames.append(pygame.image.load(path).convert_alpha())
                except pygame.error:
                    continue
        self._sprite_cache[name] = frames
        return frames

    def spawn_particles(
        self,
        pos: Vector2,
        *,
        color0: Color,
        color1: Color,
        count: int,
        speed_min: float,
        speed_max: float,
        life_min: float,
        life_max: float,
        size0: float,
        size1: float,
        direction: Optional[Vector2] = None,
        spread: float = math.tau,
        gravity: float = 0.0,
        drag: float = 0.0,
        layer: str = "world",
    ) -> None:
        base_dir = Vector2(direction) if isinstance(direction, Vector2) and direction.length_squared() > 1e-6 else None
        if isinstance(base_dir, Vector2):
            base_dir = base_dir.normalize()
        for _ in range(max(1, int(count))):
            if isinstance(base_dir, Vector2):
                ang = random.uniform(-spread * 0.5, spread * 0.5)
                vel_dir = base_dir.rotate_rad(ang)
            else:
                ang = random.uniform(0.0, math.tau)
                vel_dir = Vector2(math.cos(ang), math.sin(ang))
            speed = random.uniform(speed_min, speed_max)
            life = random.uniform(life_min, life_max)
            self.effects.append(
                Particle(
                    pos=Vector2(pos),
                    vel=vel_dir * speed,
                    life=life,
                    duration=life,
                    size0=size0 * random.uniform(0.8, 1.2),
                    size1=size1 * random.uniform(0.8, 1.2),
                    color0=color0,
                    color1=color1,
                    gravity=gravity,
                    drag=drag,
                    layer=layer,
                )
            )

    def spawn_trail(
        self,
        start: Vector2,
        end: Vector2,
        *,
        color0: Color,
        color1: Color,
        duration: float = 0.12,
        width0: float = 6.0,
        width1: float = 1.0,
        layer: str = "world",
    ) -> None:
        self.effects.append(
            TrailSegment(
                start=Vector2(start),
                end=Vector2(end),
                life=duration,
                duration=duration,
                width0=width0,
                width1=width1,
                color0=color0,
                color1=color1,
                layer=layer,
            )
        )

    def spawn_ring(
        self,
        pos: Vector2,
        *,
        radius0: float,
        radius1: float,
        duration: float,
        color: Color,
        width: int = 2,
        layer: str = "world",
    ) -> None:
        self.effects.append(
            PulseRing(
                pos=Vector2(pos),
                radius0=radius0,
                radius1=radius1,
                life=duration,
                duration=duration,
                color=color,
                width=width,
                layer=layer,
            )
        )

    def spawn_telegraph(
        self,
        pos: Vector2,
        *,
        radius: float,
        duration: float,
        color: Color,
        outline: Color,
        fill_alpha: int = 34,
    ) -> None:
        self.effects.append(
            GroundTelegraph(
                pos=Vector2(pos),
                radius=radius,
                life=duration,
                duration=duration,
                color=color,
                outline=outline,
                fill_alpha=fill_alpha,
            )
        )

    def spawn_sprite_animation(self, name: str, pos: Vector2, *, duration: float = 0.22, scale: float = 1.0, layer: str = "world", pixel_art: bool = False, anchor: str = "center") -> None:
        frames = self._load_frames(name)
        if not frames:
            return
        self.effects.append(
            SpriteAnimation(
                frames=frames,
                pos=Vector2(pos),
                life=duration,
                duration=duration,
                scale=scale,
                layer=layer,
                pixel_art=pixel_art,
                anchor=anchor,
            )
        )

    def load_frames(self, name: str) -> List[pygame.Surface]:
        """Public accessor so spells can render sprite frames directly in their own draw()."""
        return self._load_frames(name)

    def spawn(self, name: str, position: Vector2, velocity: Optional[Vector2] = None, **kwargs: object) -> None:
        pos = Vector2(position)
        vel = Vector2(velocity) if isinstance(velocity, Vector2) else None
        if name == "arcane_cast_flash":
            self.spawn_sprite_animation("bolt_cast_flash", pos, duration=0.18, scale=1.0)
            self.spawn_ring(pos, radius0=12.0, radius1=44.0, duration=0.18, color=(220, 210, 255))
            self.spawn_particles(
                pos,
                color0=(244, 236, 255),
                color1=(136, 102, 232),
                count=10,
                speed_min=60.0,
                speed_max=160.0,
                life_min=0.10,
                life_max=0.22,
                size0=4.0,
                size1=0.6,
                layer="world",
            )
            return
        if name == "arcane_trail" and isinstance(vel, Vector2) and vel.length_squared() > 0.0:
            end = pos - vel.normalize() * 16.0
            self.spawn_trail(pos, end, color0=(200, 184, 255), color1=(108, 82, 190), duration=0.12, width0=6.0, width1=1.0)
            self.spawn_particles(
                pos,
                color0=(230, 220, 255),
                color1=(130, 102, 214),
                count=2,
                speed_min=30.0,
                speed_max=90.0,
                life_min=0.06,
                life_max=0.16,
                size0=2.4,
                size1=0.3,
                direction=-vel.normalize(),
                spread=0.55,
                drag=1.4,
                layer="world",
            )
            return
        if name == "arcane_impact":
            self.spawn_sprite_animation("bolt_impact", pos, duration=0.22, scale=1.1)
            self.spawn_ring(pos, radius0=18.0, radius1=76.0, duration=0.18, color=(244, 232, 255))
            self.spawn_particles(
                pos,
                color0=(255, 244, 224),
                color1=(144, 110, 242),
                count=16,
                speed_min=80.0,
                speed_max=230.0,
                life_min=0.10,
                life_max=0.24,
                size0=5.2,
                size1=0.6,
                gravity=18.0,
                drag=1.2,
                layer="world",
            )
            return
        if name == "blink_depart":
            self.spawn_ring(pos, radius0=22.0, radius1=90.0, duration=0.18, color=(170, 216, 255))
            self.spawn_particles(
                pos,
                color0=(210, 248, 255),
                color1=(112, 180, 236),
                count=14,
                speed_min=80.0,
                speed_max=220.0,
                life_min=0.10,
                life_max=0.26,
                size0=4.4,
                size1=0.5,
                gravity=-24.0,
                drag=1.2,
                layer="world",
            )
            return
        if name == "blink_arrive":
            self.spawn_ring(pos, radius0=16.0, radius1=112.0, duration=0.22, color=(196, 244, 255))
            self.spawn_particles(
                pos,
                color0=(240, 252, 255),
                color1=(108, 194, 255),
                count=22,
                speed_min=100.0,
                speed_max=260.0,
                life_min=0.10,
                life_max=0.28,
                size0=5.0,
                size1=0.5,
                gravity=12.0,
                drag=1.1,
                layer="world",
            )
            return
        if name == "meteor_impact":
            self.spawn_ring(pos, radius0=24.0, radius1=128.0, duration=0.26, color=(255, 210, 154))
            self.spawn_particles(
                pos,
                color0=(255, 240, 204),
                color1=(255, 118, 72),
                count=24,
                speed_min=120.0,
                speed_max=320.0,
                life_min=0.12,
                life_max=0.34,
                size0=6.0,
                size1=0.7,
                gravity=32.0,
                drag=1.0,
                layer="world",
            )
            return

    def update(self, dt: float) -> None:
        if dt <= 0.0:
            return
        keep: List[object] = []
        for effect in self.effects:
            update = getattr(effect, "update", None)
            if callable(update):
                update(dt)
            if bool(getattr(effect, "alive", True)):
                keep.append(effect)
        self.effects = keep

    def _draw_layer(self, surface: pygame.Surface, camera: Vector2, layer: str) -> None:
        for effect in self.effects:
            if getattr(effect, "layer", "world") != layer:
                continue
            draw = getattr(effect, "draw", None)
            if callable(draw):
                draw(surface, camera)

    def draw_ground(self, surface: pygame.Surface, camera: Vector2) -> None:
        self._draw_layer(surface, camera, "ground")

    def draw_world(self, surface: pygame.Surface, camera: Vector2) -> None:
        self._draw_layer(surface, camera, "world")

    def draw_overlay(self, surface: pygame.Surface, camera: Vector2) -> None:
        self._draw_layer(surface, camera, "overlay")
