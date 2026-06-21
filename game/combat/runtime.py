from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Set, Tuple

import pygame
from pygame import Vector2

from .feedback import CombatFeedback
from .spells import SPELL_IMPLEMENTATIONS, TimelineSpell
from .vfx import VFXManager


DamageNumber = Dict[str, object]


@dataclass
class CombatSceneContext:
    current_level: str
    enemies: List[Dict[str, object]]
    passive_animals: List[Dict[str, object]]
    walk_bounds: pygame.Rect
    obstacles: List[pygame.Rect]
    player_pos: Vector2
    damage_numbers: List[DamageNumber]
    camera_director: Any = None
    screen_effects: Any = None
    audio: Any = None


@dataclass
class CombatCastResult:
    handled: bool
    success: bool
    status_message: str = ""
    status_duration: float = 0.85
    spell_id: str = ""
    cooldown_remaining: float = 0.0
    spell_global_cooldown: float = 0.0
    mana_regen_lock_timer: float = 0.0
    player_mana: float = 0.0
    player_pos: Optional[Vector2] = None
    player_target: Optional[Vector2] = None
    clear_player_path: bool = False
    facing: int = 1
    aim_direction: Vector2 = field(default_factory=lambda: Vector2())


@dataclass
class CombatUpdateResult:
    killed_wolves: int = 0
    dead_wolves: List[Dict[str, object]] = field(default_factory=list)
    killed_passives: int = 0
    dead_passives: List[Dict[str, object]] = field(default_factory=list)


class SpellManager:
    def __init__(self) -> None:
        self.active_spells: List[TimelineSpell] = []

    def clear(self) -> None:
        self.active_spells.clear()

    def add(self, spell: TimelineSpell, runtime: "CombatRuntime", context: CombatSceneContext) -> None:
        self.active_spells.append(spell)
        spell.start(runtime, context)

    def update(self, dt: float, runtime: "CombatRuntime", context: CombatSceneContext) -> None:
        if dt <= 0.0:
            return
        keep: List[TimelineSpell] = []
        for spell in self.active_spells:
            spell.update(dt, runtime, context)
            if spell.alive:
                keep.append(spell)
        self.active_spells = keep

    def draw(self, surface: pygame.Surface, camera: Vector2) -> None:
        for spell in self.active_spells:
            spell.draw(surface, camera)


class CombatRuntime:
    def __init__(
        self,
        *,
        move_with_collision: Optional[Callable[[Vector2, Vector2, float, pygame.Rect, List[pygame.Rect], float], Vector2]] = None,
        player_collision_radius: float = 18.0,
    ) -> None:
        self.move_with_collision = move_with_collision
        self.player_collision_radius = float(player_collision_radius)
        self.feedback = CombatFeedback()
        self.vfx = VFXManager()
        self.spells = SpellManager()
        self._runtime_classes: Set[str] = {"mage"}

    def clear(self) -> None:
        self.feedback.clear()
        self.vfx.clear()
        self.spells.clear()

    def handles_class(self, class_id: str) -> bool:
        return str(class_id).strip().lower() in self._runtime_classes

    def begin_frame(self, dt: float) -> None:
        self.feedback.begin_frame(dt)

    def filter_world_dt(self, world_dt: float) -> float:
        return self.feedback.filter_world_dt(world_dt)

    def cast_spell(
        self,
        *,
        class_id: str,
        spell: Dict[str, object],
        spell_mods: Dict[str, float],
        player_pos: Vector2,
        player_mana: float,
        target_world: Vector2,
        facing: int,
        bonus_power: float,
        class_damage_mult: float,
        mana_cost: float,
        cooldown_scale: float,
        passive_spell_cooldown_mult: float,
        spell_global_cooldown: float,
        mana_regen_lock_timer: float,
        context: CombatSceneContext,
    ) -> CombatCastResult:
        if not self.handles_class(class_id):
            return CombatCastResult(handled=False, success=False)
        spell_id = str(spell.get("id", ""))
        spell_cls = SPELL_IMPLEMENTATIONS.get(spell_id)
        if spell_cls is None:
            return CombatCastResult(handled=False, success=False)
        origin = Vector2(player_pos)
        target = Vector2(target_world)
        cast_range = max(0.0, float(spell.get("cast_range", 0.0)))
        if cast_range > 0.0:
            offset = target - origin
            if offset.length_squared() > cast_range * cast_range and offset.length_squared() > 1e-6:
                target = origin + offset.normalize() * cast_range
        new_player_pos: Optional[Vector2] = None
        clear_path = False
        is_blink = spell_id in ("mage_phase_blink", "mage_foozle_portal_blink")
        if is_blink:
            blink_range = max(90.0, float(spell.get("cast_range", 280.0)) + float(spell_mods.get("blink_range_bonus", 0.0)))
            offset = target - origin
            if offset.length_squared() > blink_range * blink_range:
                target = origin + offset.normalize() * blink_range
            if self.move_with_collision is not None:
                target = self.move_with_collision(origin, target, origin.distance_to(target), context.walk_bounds, context.obstacles, self.player_collision_radius)
            new_player_pos = Vector2(target)
            clear_path = True
        kwargs = {
            "spell_mods": spell_mods,
            "bonus_power": bonus_power,
            "class_damage_mult": class_damage_mult,
        }
        if is_blink:
            runtime_spell = spell_cls(spell, origin, target, facing, destination=target, **kwargs)
        else:
            runtime_spell = spell_cls(spell, origin, target, facing, **kwargs)
        self.spells.add(runtime_spell, self, context)
        cooldown_mult = max(0.7, float(spell_mods.get("cooldown_mult", 1.0)))
        cooldown_remaining = max(0.12, float(spell.get("cooldown", 0.45)) * cooldown_scale * cooldown_mult * passive_spell_cooldown_mult)
        global_cd = 0.28 if bool(spell.get("is_ultimate", False)) else 0.14
        mana_lock = 0.80 if bool(spell.get("is_ultimate", False)) else 0.42
        aim_direction = target - origin
        if aim_direction.length_squared() <= 1e-6:
            aim_direction = Vector2(1.0 if facing >= 0 else -1.0, 0.0)
        return CombatCastResult(
            handled=True,
            success=True,
            status_message=f"Casted {spell.get('name', 'spell')}.",
            status_duration=0.85,
            spell_id=spell_id,
            cooldown_remaining=cooldown_remaining,
            spell_global_cooldown=max(spell_global_cooldown, global_cd),
            mana_regen_lock_timer=max(mana_regen_lock_timer, mana_lock),
            player_mana=max(0.0, player_mana - mana_cost),
            player_pos=new_player_pos,
            player_target=Vector2(new_player_pos) if isinstance(new_player_pos, Vector2) else None,
            clear_player_path=clear_path,
            facing=1 if target.x >= origin.x else -1,
            aim_direction=aim_direction,
        )

    def projectile_hits_obstacle(self, pos: Vector2, radius: float, obstacles: Sequence[pygame.Rect]) -> bool:
        for rect in obstacles:
            if rect.inflate(int(radius * 2.0), int(radius * 2.0)).collidepoint(int(pos.x), int(pos.y)):
                return True
        return False

    def enemy_position(self, enemy: Dict[str, object]) -> Optional[Vector2]:
        pos = enemy.get("pos")
        if isinstance(pos, Vector2):
            return Vector2(pos)
        return None

    def closest_enemies(
        self,
        center: Vector2,
        enemies: Iterable[Dict[str, object]],
        *,
        radius: float,
        ignore: Set[int],
    ) -> List[Dict[str, object]]:
        found: List[Tuple[float, Dict[str, object]]] = []
        radius_sq = float(radius) * float(radius)
        for enemy in enemies:
            if id(enemy) in ignore or float(enemy.get("hp", 0.0)) <= 0.0:
                continue
            pos = self.enemy_position(enemy)
            if pos is None:
                continue
            dist_sq = pos.distance_squared_to(center)
            if dist_sq <= radius_sq:
                found.append((dist_sq, enemy))
        found.sort(key=lambda item: item[0])
        return [enemy for _, enemy in found]

    def first_enemy_hit(
        self,
        center: Vector2,
        radius: float,
        enemies: Iterable[Dict[str, object]],
        ignore: Set[int],
        context: Optional[CombatSceneContext] = None,
    ) -> Optional[Dict[str, object]]:
        for enemy in self.closest_enemies(center, enemies, radius=radius + 24.0, ignore=ignore):
            pos = self.enemy_position(enemy)
            if pos is None:
                continue
            enemy_radius = max(10.0, float(enemy.get("radius", 15.0)))
            if pos.distance_to(center) <= enemy_radius + radius:
                return enemy
        if context is not None:
            for animal in list(context.passive_animals):
                if id(animal) in ignore or bool(animal.get("promoted_to_enemy", False)):
                    continue
                if float(animal.get("hp", 0.0)) <= 0.0:
                    continue
                pos = animal.get("pos")
                if not isinstance(pos, Vector2):
                    continue
                animal_radius = max(10.0, float(animal.get("radius", 12.0)))
                if pos.distance_to(center) <= animal_radius + radius:
                    return self._promote_passive_to_enemy(context, animal)
        return None

    def _promote_passive_to_enemy(
        self,
        context: CombatSceneContext,
        animal: Dict[str, object],
    ) -> Optional[Dict[str, object]]:
        pos = animal.get("pos")
        if not isinstance(pos, Vector2):
            return None
        home = Vector2(pos)
        max_hp = max(30.0, float(animal.get("max_hp", 30.0)))
        radius = max(10.0, float(animal.get("radius", 14.0)))
        speed = max(60.0, float(animal.get("speed", 70.0)) * 1.15)
        enemy: Dict[str, object] = {
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
        context.enemies.append(enemy)
        animal["promoted_to_enemy"] = True
        animal["hp"] = 0.0
        return enemy

    def _append_damage_number(self, bucket: List[DamageNumber], pos: Vector2, amount: float, kind: str = "outgoing") -> None:
        value = max(0, int(round(float(amount))))
        if value <= 0:
            return
        if str(kind) == "incoming":
            color = (236, 112, 104)
            outline = (78, 22, 18)
            text = f"-{value}"
        else:
            color = (246, 220, 126)
            outline = (74, 54, 16)
            text = str(value)
        bucket.append(
            {
                "pos": Vector2(pos.x, pos.y - 24.0),
                "vel": Vector2(0.0, -72.0),
                "life": 0.82,
                "duration": 0.82,
                "text": text,
                "color": color,
                "outline": outline,
            }
        )

    def damage_enemy(
        self,
        context: CombatSceneContext,
        enemy: Dict[str, object],
        amount: float,
        hit_pos: Vector2,
        *,
        flash_color: Tuple[int, int, int],
        screen_flash_color: Tuple[int, int, int],
        hit_stop: float,
        shake: float,
    ) -> float:
        dealt = max(0.0, float(amount))
        if dealt <= 0.0:
            return 0.0
        hp_before = max(0.0, float(enemy.get("hp", 0.0)))
        if hp_before <= 0.0:
            return 0.0
        enemy["hp"] = max(0.0, hp_before - dealt)
        actual = min(hp_before, dealt)
        if actual > 0.0:
            enemy["chasing"] = True
            enemy["aggro_timer"] = max(float(enemy.get("aggro_timer", 0.0)), 3.5)
            self._append_damage_number(context.damage_numbers, hit_pos, actual, kind="outgoing")
            self.feedback.register_hit(
                enemy,
                actual,
                camera_director=context.camera_director,
                screen_effects=context.screen_effects,
                flash_color=flash_color,
                screen_flash_color=screen_flash_color,
                hit_stop=hit_stop,
                shake=shake,
            )
        return actual

    def damage_enemies_in_radius(
        self,
        context: CombatSceneContext,
        *,
        center: Vector2,
        radius: float,
        amount: float,
        ignore: Set[int],
        flash_color: Tuple[int, int, int],
        screen_flash_color: Tuple[int, int, int],
        hit_stop: float,
        shake: float,
    ) -> float:
        total = 0.0
        for enemy in self.closest_enemies(center, context.enemies, radius=radius, ignore=ignore):
            pos = self.enemy_position(enemy)
            if pos is None:
                continue
            total += self.damage_enemy(
                context,
                enemy,
                amount,
                pos,
                flash_color=flash_color,
                screen_flash_color=screen_flash_color,
                hit_stop=hit_stop,
                shake=shake,
            )
        radius_sq = float(radius) * float(radius)
        for animal in list(context.passive_animals):
            if bool(animal.get("promoted_to_enemy", False)):
                continue
            if float(animal.get("hp", 0.0)) <= 0.0:
                continue
            pos = animal.get("pos")
            if not isinstance(pos, Vector2):
                continue
            if pos.distance_squared_to(center) > radius_sq:
                continue
            promoted = self._promote_passive_to_enemy(context, animal)
            if promoted is None:
                continue
            total += self.damage_enemy(
                context,
                promoted,
                amount,
                Vector2(pos),
                flash_color=flash_color,
                screen_flash_color=screen_flash_color,
                hit_stop=hit_stop,
                shake=shake,
            )
        return total

    def knockback_enemy(self, context: CombatSceneContext, enemy: Dict[str, object], origin: Vector2, distance: float) -> None:
        pos = self.enemy_position(enemy)
        if pos is None:
            return
        direction = pos - origin
        if direction.length_squared() <= 1e-6:
            return
        target = pos + direction.normalize() * max(0.0, float(distance))
        if self.move_with_collision is not None:
            enemy["pos"] = self.move_with_collision(pos, target, pos.distance_to(target), context.walk_bounds, context.obstacles, max(10.0, float(enemy.get("radius", 15.0))))
        else:
            enemy["pos"] = target

    def pull_enemy(self, context: CombatSceneContext, enemy: Dict[str, object], target: Vector2, distance: float) -> None:
        pos = self.enemy_position(enemy)
        if pos is None:
            return
        direction = target - pos
        if direction.length_squared() <= 1e-6:
            return
        destination = pos + direction.normalize() * max(0.0, float(distance))
        if self.move_with_collision is not None:
            enemy["pos"] = self.move_with_collision(pos, destination, pos.distance_to(destination), context.walk_bounds, context.obstacles, max(10.0, float(enemy.get("radius", 15.0))))
        else:
            enemy["pos"] = destination

    def update(self, dt: float, world_dt: float, context: CombatSceneContext) -> CombatUpdateResult:
        self.feedback.update_enemy_flash(context.enemies, dt)
        if world_dt > 0.0:
            self.spells.update(world_dt, self, context)
            self.vfx.update(world_dt)
        alive: List[Dict[str, object]] = []
        dead_wolves: List[Dict[str, object]] = []
        for enemy in context.enemies:
            if float(enemy.get("hp", 0.0)) <= 0.0:
                if not bool(enemy.get("death_emitted", False)):
                    enemy["death_emitted"] = True
                    enemy["dying"] = True
                    enemy["death_timer"] = 0.55
                    enemy["death_duration"] = 0.55
                    enemy["attack_state"] = "idle"
                    enemy["attack_visual"] = 0.0
                    enemy["chasing"] = False
                    pos = self.enemy_position(enemy)
                    if pos is not None:
                        dead_wolves.append(
                            {
                                "pos": pos,
                                "level": max(1, int(enemy.get("level", 1))),
                                "name": str(enemy.get("name", "Wolf")),
                                "xp_reward": max(1, int(enemy.get("xp_reward", 14))),
                            }
                        )
                enemy["death_timer"] = max(0.0, float(enemy.get("death_timer", 0.0)) - dt)
                if float(enemy.get("death_timer", 0.0)) > 0.0:
                    alive.append(enemy)
            else:
                alive.append(enemy)
        context.enemies[:] = alive
        return CombatUpdateResult(killed_wolves=len(dead_wolves), dead_wolves=dead_wolves)

    def draw_ground(self, surface: pygame.Surface, camera: Vector2) -> None:
        self.vfx.draw_ground(surface, camera)

    def draw_world(self, surface: pygame.Surface, camera: Vector2) -> None:
        self.spells.draw(surface, camera)
        self.vfx.draw_world(surface, camera)

    def draw_overlay(self, surface: pygame.Surface, camera: Vector2) -> None:
        self.vfx.draw_overlay(surface, camera)
