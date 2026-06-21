"""game/entities.py — enemies, wolves, summoned skeletons, passive animals, portals."""
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
from game.systems.core import *

__all__ = [
    'build_enemies',
    'build_passive_animals',
    'update_passive_animals',
    'update_wolves',
    '_WOLF_LEVEL_FONT',
    'draw_wolf',
    'update_summoned_skeletons',
    'draw_summoned_skeleton',
    'draw_passive_animal',
    'draw_town_portal',
    'draw_book_portal',
    'draw_ice_portal',
]


def build_enemies(
    archetypes: List[Dict[str, Union[pygame.Surface, str]]],
    spawn_points: List[Vector2],
    walk_bounds: pygame.Rect,
    obstacles: List[pygame.Rect],
    tier: int = 0,
    lpc_wolf_frames: Optional[Dict[str, object]] = None,
) -> List[Dict[str, object]]:
    if not archetypes or not spawn_points:
        return []

    enemy_names = [
        "Ashfang",
        "Bramble",
        "Nightclaw",
        "Hollow",
        "Thorn",
        "Cinder",
        "Morrow",
        "Gale",
        "Rook",
        "Ember",
    ]

    rng = random.Random(7201 + max(0, int(tier)) * 131 + len(spawn_points) * 7)
    pack_level = max(1, tier + 1)
    area_scale = max(0.55, (walk_bounds.width * walk_bounds.height) / float(3200 * 2200))
    candidates: List[Vector2] = [Vector2(p) for p in spawn_points]
    rng.shuffle(candidates)
    min_candidate_gap = 92.0

    # Add broad random anchors so distribution stays map-wide even if source points cluster.
    if len(candidates) < 80:
        extra_target = int(clamp(84.0 + area_scale * 28.0, 90.0, 180.0))
        for _ in range(1200):
            if len(candidates) >= extra_target:
                break
            raw = Vector2(
                rng.uniform(walk_bounds.left + 18, walk_bounds.right - 18),
                rng.uniform(walk_bounds.top + 18, walk_bounds.bottom - 18),
            )
            cand = nearest_walkable(raw, walk_bounds, obstacles, WOLF_COLLISION_RADIUS)
            if cand.distance_to(raw) > 155.0:
                continue
            if any(cand.distance_to(existing) < min_candidate_gap for existing in candidates):
                continue
            candidates.append(cand)

    def depth_ratio(pos: Vector2) -> float:
        span = max(1.0, float(walk_bounds.height))
        return clamp((pos.y - float(walk_bounds.top)) / span, 0.0, 1.0)

    def biome_score(arche: Dict[str, object], depth: float) -> float:
        name = str(arche.get("name", "")).lower()
        if "grizzly" in name:
            preferred = 0.88
        elif "black bear" in name:
            preferred = 0.78
        elif "cougar" in name or "lynx" in name:
            preferred = 0.66
        elif "snake" in name:
            preferred = 0.72
        elif "boar" in name:
            preferred = 0.58
        elif "frost bear" in name:
            preferred = 0.82
        elif "arctic wolf" in name:
            preferred = 0.40
        elif "wolf" in name:
            preferred = 0.46
        elif "badger" in name:
            preferred = 0.34
        elif "tundra fox" in name or "fox" in name:
            preferred = 0.22
        else:
            preferred = rng.uniform(0.25, 0.80)
        dist = abs(depth - preferred)
        return 1.48 - dist * 1.85 + rng.uniform(-0.05, 0.14)

    def predator_traits(arche_name: str) -> Dict[str, float]:
        n = str(arche_name).lower()
        if "wolf" in n:
            return {
                "human_aggression": 0.58,
                "hunt_bias": 0.72,
                "metabolism": 0.24,
                "aggro_radius": 188.0,
                "assist_radius": 220.0,
            }
        if "cougar" in n:
            return {
                "human_aggression": 0.52,
                "hunt_bias": 0.80,
                "metabolism": 0.22,
                "aggro_radius": 176.0,
                "assist_radius": 170.0,
            }
        if "grizzly" in n or "black bear" in n:
            return {
                "human_aggression": 0.34,
                "hunt_bias": 0.36,
                "metabolism": 0.16,
                "aggro_radius": 148.0,
                "assist_radius": 156.0,
            }
        if "fox" in n:
            return {
                "human_aggression": 0.20,
                "hunt_bias": 0.62,
                "metabolism": 0.18,
                "aggro_radius": 118.0,
                "assist_radius": 132.0,
            }
        if "snake" in n:
            return {
                "human_aggression": 0.42,
                "hunt_bias": 0.58,
                "metabolism": 0.20,
                "aggro_radius": 126.0,
                "assist_radius": 120.0,
            }
        if "badger" in n:
            return {
                "human_aggression": 0.30,
                "hunt_bias": 0.54,
                "metabolism": 0.20,
                "aggro_radius": 132.0,
                "assist_radius": 124.0,
            }
        if "boar" in n:
            return {
                "human_aggression": 0.38,
                "hunt_bias": 0.34,
                "metabolism": 0.18,
                "aggro_radius": 142.0,
                "assist_radius": 148.0,
            }
        return {
            "human_aggression": 0.40,
            "hunt_bias": 0.50,
            "metabolism": 0.20,
            "aggro_radius": 150.0,
            "assist_radius": 150.0,
        }

    def ranked_archetypes_for_depth(depth: float) -> List[Dict[str, object]]:
        ranked = sorted((a for a in archetypes), key=lambda a: biome_score(a, depth), reverse=True)
        return [dict(a) for a in ranked]

    zone_cols = 4
    zone_rows = 5
    zone_w = max(1.0, float(walk_bounds.width) / float(zone_cols))
    zone_h = max(1.0, float(walk_bounds.height) / float(zone_rows))
    zone_points: Dict[Tuple[int, int], List[Vector2]] = {}
    for cand in candidates:
        rel_x = clamp(cand.x - float(walk_bounds.left), 0.0, max(0.0, float(walk_bounds.width - 1)))
        rel_y = clamp(cand.y - float(walk_bounds.top), 0.0, max(0.0, float(walk_bounds.height - 1)))
        zx = int(clamp(int(rel_x / zone_w), 0, zone_cols - 1))
        zy = int(clamp(int(rel_y / zone_h), 0, zone_rows - 1))
        zone_points.setdefault((zx, zy), []).append(cand)

    target_pack_count = int(clamp(4.0 + area_scale * 1.45 + tier * 0.22, 5.0, 12.0))
    min_pack_gap = 330.0
    pack_centers: List[Vector2] = []

    # First pass: one center per occupied zone for even world coverage.
    zone_keys = list(zone_points.keys())
    rng.shuffle(zone_keys)
    for key in zone_keys:
        pts = list(zone_points.get(key, []))
        rng.shuffle(pts)
        for cand in pts:
            chosen = nearest_walkable(cand, walk_bounds, obstacles, WOLF_COLLISION_RADIUS)
            if any(chosen.distance_to(existing) < min_pack_gap for existing in pack_centers):
                continue
            pack_centers.append(chosen)
            break
        if len(pack_centers) >= target_pack_count:
            break

    # Second pass: fill remaining centers from all candidates.
    fill_candidates = list(candidates)
    rng.shuffle(fill_candidates)
    for cand in fill_candidates:
        chosen = nearest_walkable(cand, walk_bounds, obstacles, WOLF_COLLISION_RADIUS)
        if any(chosen.distance_to(existing) < min_pack_gap for existing in pack_centers):
            continue
        pack_centers.append(chosen)
        if len(pack_centers) >= target_pack_count:
            break

    if not pack_centers:
        pack_centers.append(nearest_walkable(Vector2(spawn_points[0]), walk_bounds, obstacles, WOLF_COLLISION_RADIUS))

    enemies: List[Dict[str, object]] = []
    occupied: List[Vector2] = []
    enemy_idx = 0
    pack_id_counter = 0

    def spawn_enemy(
        arche: Dict[str, object],
        home: Vector2,
        level: int,
        member_idx: int,
        pack_id: int,
        patrol_range_min: float,
        patrol_range_max: float,
        patrol_points: int,
    ) -> None:
        nonlocal enemy_idx
        traits = predator_traits(str(arche.get("name", "")))
        hp_mult = float(arche.get("hp_mult", 1.0))
        dmg_mult = float(arche.get("dmg_mult", 1.0))
        hp_scale = (1.0 + (level - 1) * 0.26) * hp_mult
        speed_bonus = (level - 1) * 4.0
        wolf_base_hp = round((138.0 + (member_idx % 3) * 6.0) * hp_scale, 1)
        attack_min = (5.8 + level * 1.55) * dmg_mult
        attack_max = attack_min + 4.9 + tier * 0.7
        xp_reward = max(10, int(14 + level * 6 + tier * 2))

        patrol = [Vector2(home)]
        for _ in range(patrol_points):
            ang = rng.uniform(0.0, math.tau)
            rr = rng.uniform(patrol_range_min, patrol_range_max)
            patrol.append(
                nearest_walkable(
                    home + Vector2(math.cos(ang), math.sin(ang)) * rr,
                    walk_bounds,
                    obstacles,
                    WOLF_COLLISION_RADIUS,
                )
            )

        enemies.append(
            {
                "name": str(arche.get("name", enemy_names[enemy_idx % len(enemy_names)])).title(),
                "pos": Vector2(home),
                "home": Vector2(home),
                "path": patrol,
                "path_idx": 1,
                "wait": 0.35 + rng.random() * 0.35,
                "speed": 86.0 + rng.uniform(0.0, 16.0) + speed_bonus,
                "aggro_radius": max(88.0, float(traits["aggro_radius"]) + rng.uniform(-14.0, 16.0)),
                "assist_radius": max(96.0, float(traits["assist_radius"]) + rng.uniform(-18.0, 18.0)),
                "leash": 620.0 + rng.uniform(0.0, 90.0),
                "facing": -1 if rng.random() < 0.5 else 1,
                "sprite": arche.get("sprite"),
                "sprite_left": arche.get("sprite_left"),
                "max_hp": wolf_base_hp,
                "radius": float(arche.get("radius", 15.0)),
                "hp": wolf_base_hp,
                "chasing": False,
                "aggro_timer": 0.0,
                "engage_role": "patrol",
                "attack_cd": rng.uniform(0.2, 0.8),
                "attack_min": attack_min,
                "attack_max": attack_max,
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
                "hunt_drive": clamp(float(traits["hunt_bias"]) + rng.uniform(-0.22, 0.24), 0.0, 1.0),
                "human_aggression": clamp(float(traits["human_aggression"]) + rng.uniform(-0.10, 0.10), 0.05, 0.98),
                "metabolism": clamp(float(traits["metabolism"]) + rng.uniform(-0.04, 0.05), 0.08, 0.48),
                "satiety": 10.0 + rng.uniform(4.0, 16.0),
                "hunt_cooldown": rng.uniform(0.4, 2.4),
                "hunt_scan_timer": rng.uniform(0.5, 1.8),
                "orbit_phase": rng.uniform(0.0, math.tau),
                "xp_reward": xp_reward,
                "level": level,
                "tier": tier,
                "pack_id": pack_id,
                "pack_slot": member_idx,
                "nav_path": [],
                "nav_goal": Vector2(home),
                "repath_cd": 0.0,
                # Animated sprite sheet (falls back to the static sprite if unavailable)
                "anim_frames": (lpc_wolf_frames if "wolf" in str(arche.get("name", "")).lower() else None) or arche.get("anim_frames"),
                "anim_timer": 0.0,
            }
        )
        enemy_idx += 1

    for center in pack_centers:
        pack_anchor = nearest_walkable(Vector2(center), walk_bounds, obstacles, WOLF_COLLISION_RADIUS)
        depth = depth_ratio(pack_anchor)
        ranked = ranked_archetypes_for_depth(depth)
        if not ranked:
            ranked = [dict(archetypes[0])]
        primary = ranked[0]
        pool_size = 2 + (1 if rng.random() < 0.70 else 0) + (1 if tier >= 4 and rng.random() < 0.45 else 0)
        species_pool = ranked[: max(2, min(len(ranked), pool_size + 1))]

        primary_name = str(primary.get("name", "")).lower()
        if any(tag in primary_name for tag in ("grizzly", "black bear", "cougar", "fox", "snake", "badger", "boar")):
            pack_size = 1 + rng.randint(0, 1)
        elif "wolf" in primary_name:
            pack_size = 2 + rng.randint(0, 2)
        else:
            pack_size = 1 + rng.randint(0, 2)
        if tier >= 8 and rng.random() < 0.25:
            pack_size += 1

        pack_positions: List[Vector2] = []
        for _ in range(pack_size):
            chosen: Optional[Vector2] = None
            for _attempt in range(30):
                ang = rng.uniform(0.0, math.tau)
                rr = rng.uniform(58.0, 212.0)
                cand = pack_anchor + Vector2(math.cos(ang), math.sin(ang)) * rr
                cand = nearest_walkable(cand, walk_bounds, obstacles, WOLF_COLLISION_RADIUS)
                if any(cand.distance_to(existing) < 80.0 for existing in pack_positions):
                    continue
                if any(cand.distance_to(existing) < 70.0 for existing in occupied):
                    continue
                chosen = cand
                break
            if chosen is None:
                fallback = pack_anchor + Vector2(rng.uniform(-92.0, 92.0), rng.uniform(-92.0, 92.0))
                chosen = nearest_walkable(fallback, walk_bounds, obstacles, WOLF_COLLISION_RADIUS)
            pack_positions.append(chosen)
            occupied.append(chosen)

        for member_idx, home in enumerate(pack_positions):
            if rng.random() < 0.54:
                arche = primary
            elif rng.random() < 0.90 and species_pool:
                arche = rng.choice(species_pool)
            else:
                arche = rng.choice(archetypes)
            variance = rng.choice([-1, 0, 0, 1])
            elite_bump = 1 if member_idx == len(pack_positions) - 1 and rng.random() < 0.26 else 0
            wolf_level = max(1, pack_level + variance + elite_bump)
            spawn_enemy(
                arche=arche,
                home=home,
                level=wolf_level,
                member_idx=member_idx,
                pack_id=pack_id_counter,
                patrol_range_min=110.0,
                patrol_range_max=230.0,
                patrol_points=4 + rng.randint(0, 1),
            )
        pack_id_counter += 1

    # Add lone prowlers to keep remote areas populated between packs.
    roamer_target = int(clamp(float(len(pack_centers)) * 0.18 + area_scale * 0.72, 1.0, 7.0))
    roamer_candidates = list(candidates)
    rng.shuffle(roamer_candidates)
    roamers_spawned = 0
    for cand in roamer_candidates:
        if roamers_spawned >= roamer_target:
            break
        home = nearest_walkable(cand, walk_bounds, obstacles, WOLF_COLLISION_RADIUS)
        if any(home.distance_to(existing) < 220.0 for existing in occupied):
            continue
        depth = depth_ratio(home)
        ranked = ranked_archetypes_for_depth(depth)
        arche = ranked[0] if ranked and rng.random() < 0.72 else rng.choice(archetypes)
        wolf_level = max(1, pack_level + rng.choice([-1, 0, 1]))
        occupied.append(home)
        spawn_enemy(
            arche=arche,
            home=home,
            level=wolf_level,
            member_idx=0,
            pack_id=pack_id_counter,
            patrol_range_min=160.0,
            patrol_range_max=320.0,
            patrol_points=5 + rng.randint(0, 1),
        )
        pack_id_counter += 1
        roamers_spawned += 1

    return enemies


def build_passive_animals(
    archetypes: List[Dict[str, object]],
    walk_bounds: pygame.Rect,
    obstacles: List[pygame.Rect],
    count: int = 40,
    seed: Optional[int] = None,
) -> List[Dict[str, object]]:
    if not archetypes:
        return []
    rng = random.Random(123 if seed is None else int(seed))

    cols = 10
    rows = 7
    cell_w = max(1, walk_bounds.width // cols)
    cell_h = max(1, walk_bounds.height // rows)
    sector_order = [(cx, cy) for cy in range(rows) for cx in range(cols)]
    rng.shuffle(sector_order)
    occupied: List[Vector2] = []

    def depth_ratio(pos: Vector2) -> float:
        span = max(1.0, float(walk_bounds.height))
        return clamp((pos.y - float(walk_bounds.top)) / span, 0.0, 1.0)

    def passive_score(arche: Dict[str, object], depth: float) -> float:
        name = str(arche.get("name", "")).lower()
        if "rabbit" in name or "hare" in name or "arctic hare" in name:
            pref = 0.18
        elif "penguin" in name:
            pref = 0.15
        elif "duck" in name or "goose" in name or "snow goose" in name:
            pref = 0.28
        elif "crane" in name or "snowy crane" in name:
            pref = 0.35
        elif "beaver" in name or "marmot" in name:
            pref = 0.34
        elif "owl" in name or "crow" in name:
            pref = 0.54
        elif "caribou" in name or "reindeer" in name:
            pref = 0.58
        elif "deer" in name or "doe" in name or "fawn" in name:
            pref = 0.62
        elif "mountain goat" in name or "goat" in name:
            pref = 0.72
        elif "turkey" in name or "pheasant" in name:
            pref = 0.74
        elif "ram" in name or "elk" in name:
            pref = 0.84
        elif "tundra yak" in name or "yak" in name:
            pref = 0.88
        elif "snowy owl" in name or "arctic fox" in name:
            pref = rng.uniform(0.20, 0.70)
        elif "frost deer" in name or "ice stag" in name:
            pref = rng.uniform(0.40, 0.80)
        else:
            pref = rng.uniform(0.15, 0.90)
        return 1.40 - abs(depth - pref) * 1.6 + rng.uniform(-0.04, 0.12)

    def pick_archetype(depth: float) -> Dict[str, object]:
        ranked = sorted(archetypes, key=lambda a: passive_score(a, depth), reverse=True)
        top = ranked[: max(2, min(4, len(ranked)))]
        return dict(rng.choice(top if top else archetypes))

    def sample_spawn_in_cell(cx: int, cy: int) -> Optional[Vector2]:
        left = walk_bounds.left + cx * cell_w
        top = walk_bounds.top + cy * cell_h
        right = walk_bounds.right if cx == cols - 1 else left + cell_w
        bottom = walk_bounds.bottom if cy == rows - 1 else top + cell_h
        if right - left < 30 or bottom - top < 30:
            return None
        for _ in range(18):
            px = rng.randint(left + 14, right - 14)
            py = rng.randint(top + 14, bottom - 14)
            raw = Vector2(px, py)
            cand = nearest_walkable(raw, walk_bounds, obstacles, 14.0)
            if cand.distance_to(raw) > 130.0:
                continue
            if any(cand.distance_to(existing) < 88.0 for existing in occupied):
                continue
            return cand
        return None

    wildlife: List[Dict[str, object]] = []
    for i in range(count):
        spawn: Optional[Vector2] = None
        cx, cy = sector_order[i % len(sector_order)]
        spawn = sample_spawn_in_cell(cx, cy)

        if spawn is None:
            for _ in range(24):
                fx = rng.randint(0, cols - 1)
                fy = rng.randint(0, rows - 1)
                spawn = sample_spawn_in_cell(fx, fy)
                if isinstance(spawn, Vector2):
                    break

        if not isinstance(spawn, Vector2):
            for _ in range(40):
                raw = Vector2(
                    rng.uniform(walk_bounds.left + 18, walk_bounds.right - 18),
                    rng.uniform(walk_bounds.top + 18, walk_bounds.bottom - 18),
                )
                cand = nearest_walkable(raw, walk_bounds, obstacles, 14.0)
                if cand.distance_to(raw) > 140.0:
                    continue
                if any(cand.distance_to(existing) < 88.0 for existing in occupied):
                    continue
                spawn = cand
                break
        if not isinstance(spawn, Vector2):
            continue

        occupied.append(spawn)
        arche = pick_archetype(depth_ratio(spawn))

        route = [Vector2(spawn)]
        route_len = rng.randint(3, 5)
        curr = Vector2(spawn)
        for _ in range(route_len):
            for _ in range(12):
                angle = rng.uniform(0.0, math.tau)
                dist = rng.uniform(180.0, 520.0)
                next_wp = curr + Vector2(math.cos(angle), math.sin(angle)) * dist
                cand = nearest_walkable(next_wp, walk_bounds, obstacles, 12.0)
                if cand.distance_to(curr) <= 100.0:
                    continue
                if cand.distance_to(spawn) > 760.0:
                    continue
                route.append(cand)
                curr = cand
                break

        wildlife.append(
            {
                "name": str(arche.get("name", "Creature")),
                "pos": Vector2(spawn),
                "home": Vector2(spawn),
                "route": route,
                "route_idx": 0,
                "sprite": arche["sprite"],
                "sprite_left": arche["sprite_left"],
                "anim_frames": arche.get("anim_frames"),
                "anim_timer": rng.random() * 3.0,
                "speed": arche["speed"],
                "facing": 1 if rng.random() > 0.5 else -1,
                "wait": rng.random() * 2.0,
                "radius": arche["radius"],
                "hp": float(arche.get("max_hp", 30.0)),
                "max_hp": float(arche.get("max_hp", 30.0)),
                "nav_path": [],
                "repath_cd": 0.0,
                "last_hit_by_predator": False,
                "social_scan": rng.uniform(0.4, 1.8),
            }
        )
    return wildlife


def update_passive_animals(
    animals: List[Dict[str, object]],
    dt: float,
    player_pos: Vector2,
    walk_bounds: pygame.Rect,
    obstacles: List[pygame.Rect],
    predators: Optional[List[Dict[str, object]]] = None,
) -> None:
    predator_positions: List[Vector2] = []
    if isinstance(predators, list):
        for pred in predators:
            if float(pred.get("hp", 0.0)) <= 0.0:
                continue
            ppos = pred.get("pos")
            if isinstance(ppos, Vector2):
                predator_positions.append(Vector2(ppos))

    for critter in animals:
        if float(critter.get("hp", 0.0)) <= 0.0:
            continue
        pos = critter.get("pos")
        if not isinstance(pos, Vector2): continue
        critter["anim_timer"] = float(critter.get("anim_timer", 0.0)) + dt
        critter["moving"] = False

        wait = float(critter.get("wait", 0.0))
        if wait > 0.0:
            critter["wait"] = max(0.0, wait - dt)
            continue

        flee_timer = max(0.0, float(critter.get("flee_timer", 0.0)) - dt)
        critter["flee_timer"] = flee_timer

        dist = pos.distance_to(player_pos)
        nearest_predator: Optional[Vector2] = None
        nearest_pred_dist = 1e12
        for ppos in predator_positions:
            pdist = pos.distance_to(ppos)
            if pdist < nearest_pred_dist:
                nearest_pred_dist = pdist
                nearest_predator = ppos

        predator_threat = nearest_pred_dist < 126.0
        fleeing = dist < 120.0 or flee_timer > 0.0 or predator_threat

        wander_target = critter.get("wander_target")
        if not isinstance(wander_target, Vector2):
            wander_target = None

        if fleeing:
            keep_existing_flee = flee_timer > 0.0 and isinstance(wander_target, Vector2) and pos.distance_to(wander_target) > 16.0
            if not keep_existing_flee:
                threat = nearest_predator if predator_threat and isinstance(nearest_predator, Vector2) else player_pos
                away_vec = pos - threat
                if away_vec.length_squared() <= 1e-5:
                    away_vec = Vector2(random.uniform(-1.0, 1.0), random.uniform(-1.0, 1.0))
                if away_vec.length_squared() <= 1e-5:
                    away_vec = Vector2(1.0, 0.0)
                wander_target = pos + away_vec.normalize() * 200.0
            critter["wander_target"] = wander_target
            critter["wait"] = 0.0
        elif wander_target is None or pos.distance_to(wander_target) < 20.0:
            home = critter.get("home")
            if not isinstance(home, Vector2): home = pos
            social_scan = max(0.0, float(critter.get("social_scan", 0.0)) - dt)
            critter["social_scan"] = social_scan
            species_name = str(critter.get("name", ""))
            social_target: Optional[Vector2] = None
            if social_scan <= 0.0 and species_name:
                critter["social_scan"] = 0.8 + random.random() * 2.0
                neighbors: List[Vector2] = []
                for other in animals:
                    if other is critter or float(other.get("hp", 0.0)) <= 0.0:
                        continue
                    if str(other.get("name", "")) != species_name:
                        continue
                    opos = other.get("pos")
                    if not isinstance(opos, Vector2):
                        continue
                    if pos.distance_to(opos) <= 230.0:
                        neighbors.append(opos)
                if neighbors:
                    center = Vector2(0.0, 0.0)
                    for np in neighbors:
                        center += np
                    center /= float(len(neighbors))
                    if pos.distance_to(center) > 120.0:
                        social_target = center + Vector2(random.uniform(-34.0, 34.0), random.uniform(-30.0, 30.0))

            if isinstance(social_target, Vector2):
                wander_target = social_target
            else:
                angle = random.uniform(0, math.tau)
                radius = random.uniform(80.0, 250.0)
                wander_target = home + Vector2(math.cos(angle), math.sin(angle)) * radius
            critter["wander_target"] = wander_target
            critter["wait"] = random.uniform(2.5, 6.0)

        if wander_target is not None:
            step = float(critter["speed"]) * (1.8 if fleeing else 0.6) * dt
            new_pos = move_with_collision(pos, wander_target, step, walk_bounds, obstacles, float(critter.get("radius", 12.0)))
            if new_pos.distance_to(pos) > 0.01:
                critter["facing"] = 1 if new_pos.x > pos.x else -1
                critter["pos"] = new_pos
                critter["moving"] = True
            else: # Stuck
                critter["wander_target"] = None
                critter["wait"] = 0.5


def update_wolves(
    wolves: List[Dict[str, object]],
    dt: float,
    player_pos: Vector2,
    walk_bounds: pygame.Rect,
    obstacles: List[pygame.Rect],
    passive_animals: Optional[List[Dict[str, object]]] = None,
) -> None:
    if dt <= 0.0:
        return

    base_radius = WOLF_COLLISION_RADIUS
    def as_target_id(value: object) -> int:
        if isinstance(value, (int, float)):
            return int(value)
        return 0
    alive_indices: List[int] = []
    alive_pos: Dict[int, Vector2] = {}

    for idx, wolf in enumerate(wolves):
        if float(wolf.get("hp", 0.0)) <= 0.0:
            continue
        pos_raw = wolf.get("pos")
        if not isinstance(pos_raw, Vector2):
            continue
        pos = Vector2(pos_raw)
        wolf["pos"] = pos
        alive_indices.append(idx)
        alive_pos[idx] = pos
        wolf["anim_timer"] = float(wolf.get("anim_timer", 0.0)) + dt
        wolf["moving"] = False

        wolf["attack_cd"] = max(0.0, float(wolf.get("attack_cd", 0.0)) - dt)
        metabolism = clamp(float(wolf.get("metabolism", 0.20)), 0.08, 0.52)
        satiety = max(0.0, float(wolf.get("satiety", 14.0)) - dt * metabolism)
        wolf["metabolism"] = metabolism
        wolf["satiety"] = satiety
        wolf["hunt_cooldown"] = max(0.0, float(wolf.get("hunt_cooldown", 0.0)) - dt)
        wolf["hunt_scan_timer"] = max(0.0, float(wolf.get("hunt_scan_timer", 0.0)) - dt)
        state = str(wolf.get("attack_state", "idle"))
        timer = max(0.0, float(wolf.get("attack_timer", 0.0)) - dt)
        wolf["attack_timer"] = timer

        if bool(wolf.get("status_disabled", False)):
            wolf["queued_strike"] = False
            wolf["attack_state"] = "idle"
            wolf["attack_timer"] = 0.0
            wolf["attack_visual"] = 0.0
            wolf["moving"] = False
            continue

        if state == "windup":
            windup = max(0.08, float(wolf.get("attack_windup", 0.36)))
            wolf["attack_visual"] = clamp(1.0 - timer / windup, 0.0, 1.0)
            if timer <= 0.0:
                target_type = str(wolf.get("attack_target_type", "player"))
                target_id = as_target_id(wolf.get("attack_target_id", 0))
                wolf["queued_target_type"] = target_type
                wolf["queued_target_id"] = target_id
                wolf["queued_strike"] = True
                recover = max(0.12, float(wolf.get("attack_recover", 0.22)))
                wolf["attack_state"] = "recover"
                wolf["attack_timer"] = recover
                wolf["attack_visual"] = 1.0
        elif state == "recover":
            recover = max(0.08, float(wolf.get("attack_recover", 0.22)))
            wolf["attack_visual"] = clamp(timer / recover, 0.0, 1.0)
            if timer <= 0.0:
                wolf["attack_state"] = "idle"
                wolf["attack_timer"] = 0.0
                wolf["attack_visual"] = 0.0
        else:
            wolf["attack_state"] = "idle"
            wolf["attack_timer"] = 0.0
            wolf["attack_visual"] = 0.0

    passive_lookup: Dict[int, Dict[str, object]] = {}
    passive_pos: Dict[int, Vector2] = {}
    if isinstance(passive_animals, list):
        for animal in passive_animals:
            if float(animal.get("hp", 0.0)) <= 0.0:
                continue
            apos_raw = animal.get("pos")
            if not isinstance(apos_raw, Vector2):
                continue
            apos = Vector2(apos_raw)
            animal["pos"] = apos
            aid = id(animal)
            passive_lookup[aid] = animal
            passive_pos[aid] = apos

    def prey_priority(wolf_name: str, prey_name: str) -> float:
        hunter = wolf_name.lower()
        prey = prey_name.lower()
        if "wolf" in hunter:
            if prey in ("deer", "doe", "fawn", "ram", "elk"):
                return 1.28
            if prey in ("rabbit", "hare", "turkey", "pheasant"):
                return 1.08
            return 0.82
        if "cougar" in hunter:
            if prey in ("deer", "doe", "fawn", "ram", "elk"):
                return 1.34
            if prey in ("rabbit", "hare"):
                return 1.06
            return 0.84
        if "fox" in hunter:
            if prey in ("rabbit", "hare", "duck", "goose", "pheasant", "crow"):
                return 1.34
            return 0.76
        if "snake" in hunter or "badger" in hunter:
            if prey in ("rabbit", "hare", "marmot", "beaver", "duck", "goose", "crow"):
                return 1.18
            return 0.74
        if "bear" in hunter:
            if prey in ("deer", "doe", "fawn", "ram", "elk"):
                return 1.02
            if prey in ("rabbit", "hare", "duck", "goose", "turkey"):
                return 0.92
            return 0.80
        if "boar" in hunter:
            if prey in ("rabbit", "hare", "duck", "goose", "turkey", "pheasant"):
                return 0.88
            return 0.64
        return 0.92

    # Aggro state update + timer-based persistence.
    for idx in alive_indices:
        wolf = wolves[idx]
        pos = alive_pos[idx]
        home_raw = wolf.get("home")
        home = Vector2(home_raw) if isinstance(home_raw, Vector2) else Vector2(pos)
        dist_player = player_pos.distance_to(pos)
        dist_home = pos.distance_to(home)
        aggro_radius = float(wolf.get("aggro_radius", 170.0))
        leash = float(wolf.get("leash", 620.0))
        aggro_timer = max(0.0, float(wolf.get("aggro_timer", 0.0)) - dt)
        chasing = bool(wolf.get("chasing", False))
        satiety = max(0.0, float(wolf.get("satiety", 14.0)))
        hunger = clamp(1.0 - satiety / 24.0, 0.0, 1.0)
        human_aggr = clamp(float(wolf.get("human_aggression", 0.42)), 0.05, 0.98)
        alert_radius = aggro_radius
        must_defend = dist_player <= aggro_radius
        willing_to_engage = True

        # Reset aggro only when the player escapes far beyond engagement range.
        reset_distance = max(aggro_radius * 3.6, 900.0)
        if dist_player > reset_distance:
            chasing = False
            aggro_timer = 0.0
        elif dist_player <= alert_radius and willing_to_engage:
            chasing = True
            aggro_timer = max(4.0, 5.0 + hunger * 2.5)
        elif aggro_timer > 0.0:
            chasing = True
        elif chasing:
            aggro_timer = max(aggro_timer, 3.0)

        wolf["chasing"] = chasing
        wolf["aggro_timer"] = aggro_timer

    # Pack assist: nearby wolves join when one of their neighbors gets aggro.
    active_chasers = [idx for idx in alive_indices if bool(wolves[idx].get("chasing", False))]
    for idx in alive_indices:
        wolf = wolves[idx]
        if bool(wolf.get("chasing", False)):
            continue
        pos = alive_pos[idx]
        satiety = max(0.0, float(wolf.get("satiety", 14.0)))
        hunger = clamp(1.0 - satiety / 24.0, 0.0, 1.0)
        human_aggr = clamp(float(wolf.get("human_aggression", 0.42)), 0.05, 0.98)
        aggro_radius = float(wolf.get("aggro_radius", 170.0))
        if player_pos.distance_to(pos) > aggro_radius * 1.16:
            continue
        assist_radius = float(wolf.get("assist_radius", 235.0))
        assisted = False
        for cidx in active_chasers:
            cpos = alive_pos.get(cidx)
            if not isinstance(cpos, Vector2):
                continue
            if cpos.distance_to(pos) <= assist_radius:
                assisted = True
                break
        if assisted:
            wolf["chasing"] = True
            wolf["aggro_timer"] = max(float(wolf.get("aggro_timer", 0.0)), 0.95)
            active_chasers.append(idx)

    # Non-aggro wolves may hunt passive animals.
    if passive_lookup:
        for idx in alive_indices:
            wolf = wolves[idx]
            if bool(wolf.get("chasing", False)):
                wolf["prey_target_id"] = 0
                continue
            pos = alive_pos[idx]
            home_raw = wolf.get("home")
            home = Vector2(home_raw) if isinstance(home_raw, Vector2) else Vector2(pos)
            leash = float(wolf.get("leash", 620.0))
            prey_target_id = as_target_id(wolf.get("prey_target_id", 0))
            prey_pos_current = passive_pos.get(prey_target_id)
            satiety = max(0.0, float(wolf.get("satiety", 14.0)))
            hunger = clamp(1.0 - satiety / 24.0, 0.0, 1.0)
            hunt_drive = clamp(float(wolf.get("hunt_drive", 0.5)), 0.0, 1.0)
            hunt_cd = max(0.0, float(wolf.get("hunt_cooldown", 0.0)))
            hunt_scan = max(0.0, float(wolf.get("hunt_scan_timer", 0.0)))

            if isinstance(prey_pos_current, Vector2):
                keep_radius = max(210.0, leash * 0.52)
                if pos.distance_to(prey_pos_current) <= keep_radius and home.distance_to(prey_pos_current) <= leash * 1.02:
                    if hunger > 0.22:
                        continue
                wolf["prey_target_id"] = 0

            if hunt_cd > 0.0 or hunger < (0.44 - hunt_drive * 0.24):
                wolf["prey_target_id"] = 0
                continue

            if hunt_scan > 0.0:
                continue
            wolf["hunt_scan_timer"] = 0.85 + random.random() * 1.65
            hunt_roll = 0.16 + hunger * 0.64 + hunt_drive * 0.20
            if random.random() > clamp(hunt_roll, 0.0, 0.95):
                wolf["prey_target_id"] = 0
                continue

            hunt_radius = 130.0 + float(wolf.get("radius", base_radius)) * (3.8 + hunger * 2.2)
            nearest_id = 0
            best_score = 1e12
            wolf_name = str(wolf.get("name", "Predator"))
            for aid, prey in passive_lookup.items():
                apos = passive_pos.get(aid)
                if not isinstance(apos, Vector2):
                    continue
                dist = pos.distance_to(apos)
                if dist > hunt_radius:
                    continue
                prey_name = str(prey.get("name", "Animal"))
                pref = max(0.12, prey_priority(wolf_name, prey_name))
                score = dist / pref
                if score >= best_score:
                    continue
                best_score = score
                nearest_id = aid
            wolf["prey_target_id"] = nearest_id
    else:
        for idx in alive_indices:
            wolves[idx]["prey_target_id"] = 0

    # Engagement slots: only a small number are active attackers; others circle and pressure.
    engage_candidates: List[Tuple[float, int]] = []
    close_pressure = 0
    for idx in alive_indices:
        wolf = wolves[idx]
        if not bool(wolf.get("chasing", False)):
            wolf["engage_role"] = "patrol"
            continue
        dist = alive_pos[idx].distance_to(player_pos)
        if dist <= 160.0:
            close_pressure += 1
        if dist <= 280.0:
            score = dist + float(wolf.get("attack_cd", 0.0)) * 34.0
            if str(wolf.get("engage_role", "")) == "engager":
                score -= 12.0
            engage_candidates.append((score, idx))

    # Keep combat readable: usually one active attacker, with a rare second attacker
    # only under extreme pressure.
    max_engagers = 1
    if close_pressure >= 12:
        max_engagers = 2
    engage_candidates.sort(key=lambda item: item[0])
    engager_ids = {idx for _, idx in engage_candidates[:max_engagers]}

    for idx in alive_indices:
        wolf = wolves[idx]
        if not bool(wolf.get("chasing", False)):
            wolf["engage_role"] = "patrol"
        elif idx in engager_ids:
            wolf["engage_role"] = "engager"
        else:
            wolf["engage_role"] = "support"

    # Navigation and attack behavior.
    for idx in alive_indices:
        wolf = wolves[idx]
        pos = alive_pos[idx]
        wolf_radius = float(wolf.get("radius", base_radius))
        chasing = bool(wolf.get("chasing", False))
        role = str(wolf.get("engage_role", "patrol"))
        state = str(wolf.get("attack_state", "idle"))
        to_player = player_pos - pos
        dist_player = to_player.length()
        prey_target_id = as_target_id(wolf.get("prey_target_id", 0))
        prey_target = passive_lookup.get(prey_target_id)
        prey_pos = passive_pos.get(prey_target_id)

        if bool(wolf.get("status_disabled", False)):
            wolf["nav_path"] = []
            wolf["queued_strike"] = False
            wolf["moving"] = False
            continue

        if chasing and abs(to_player.x) > 0.03:
            wolf["facing"] = 1 if to_player.x > 0 else -1

        if state in ("windup", "recover"):
            wolf["nav_path"] = []
            wolf["moving"] = False
            continue

        repath_cd = max(0.0, float(wolf.get("repath_cd", 0.0)) - dt)
        wolf["repath_cd"] = repath_cd

        wait = float(wolf.get("wait", 0.0))
        if wait > 0.0:
            wolf["wait"] = max(0.0, wait - dt)
            continue

        desired_target: Optional[Vector2] = None
        if chasing:
            if dist_player > 1e-4:
                forward = to_player.normalize()
            else:
                forward = Vector2(1 if int(wolf.get("facing", 1)) >= 0 else -1, 0)
            lateral = Vector2(-forward.y, forward.x)

            if role == "engager":
                preferred_range = 58.0 + (idx % 2) * 8.0 + wolf_radius * 0.30
                if dist_player <= preferred_range + 10.0:
                    if float(wolf.get("attack_cd", 0.0)) <= 0.0 and str(wolf.get("attack_state", "idle")) == "idle":
                        windup = 0.30 + random.random() * 0.16 + wolf_radius * 0.004
                        recover = 0.16 + random.random() * 0.12
                        wolf["attack_state"] = "windup"
                        wolf["attack_timer"] = windup
                        wolf["attack_windup"] = windup
                        wolf["attack_recover"] = recover
                        wolf["attack_target_type"] = "player"
                        wolf["attack_target_id"] = 0
                        wolf["queued_target_type"] = "player"
                        wolf["queued_target_id"] = 0
                        wolf["attack_visual"] = 0.0
                        wolf["queued_strike"] = False
                        wolf["nav_path"] = []
                        continue
                    strafe_sign = -1 if (idx % 2 == 0) else 1
                    desired_target = player_pos - forward * preferred_range + lateral * (22.0 * strafe_sign)
                else:
                    flank_sign = -1 if (idx % 2 == 0) else 1
                    desired_target = player_pos + lateral * (30.0 * flank_sign)
            else:
                phase = float(wolf.get("orbit_phase", 0.0)) + dt * (0.65 + (idx % 3) * 0.18)
                wolf["orbit_phase"] = phase
                orbit_r = 108.0 + (idx % 4) * 16.0 + wolf_radius * 0.45
                desired_target = player_pos + Vector2(math.cos(phase), math.sin(phase)) * orbit_r
                if dist_player < 84.0:
                    desired_target = player_pos - forward * (orbit_r + 30.0)

            if isinstance(desired_target, Vector2):
                desired_target = nearest_walkable(desired_target, walk_bounds, obstacles, wolf_radius)
        else:
            if isinstance(prey_target, dict) and isinstance(prey_pos, Vector2) and float(prey_target.get("hp", 0.0)) > 0.0:
                to_prey = prey_pos - pos
                dist_prey = to_prey.length()
                if abs(to_prey.x) > 0.03:
                    wolf["facing"] = 1 if to_prey.x > 0 else -1
                prey_radius = max(8.0, float(prey_target.get("radius", 12.0)))
                bite_range = 44.0 + wolf_radius * 0.45 + prey_radius * 0.42
                if dist_prey <= bite_range + 8.0:
                    if float(wolf.get("attack_cd", 0.0)) <= 0.0 and str(wolf.get("attack_state", "idle")) == "idle":
                        windup = 0.24 + random.random() * 0.14 + wolf_radius * 0.003
                        recover = 0.15 + random.random() * 0.10
                        wolf["attack_state"] = "windup"
                        wolf["attack_timer"] = windup
                        wolf["attack_windup"] = windup
                        wolf["attack_recover"] = recover
                        wolf["attack_target_type"] = "passive"
                        wolf["attack_target_id"] = prey_target_id
                        wolf["queued_target_type"] = "passive"
                        wolf["queued_target_id"] = prey_target_id
                        wolf["attack_visual"] = 0.0
                        wolf["queued_strike"] = False
                        wolf["nav_path"] = []
                        continue
                    if dist_prey > 1e-4:
                        desired_target = prey_pos - to_prey.normalize() * bite_range
                    else:
                        desired_target = Vector2(prey_pos)
                else:
                    desired_target = Vector2(prey_pos)
            else:
                wolf["prey_target_id"] = 0
                patrol = wolf.get("path")
                if isinstance(patrol, list) and patrol:
                    path_idx = int(wolf.get("path_idx", 0)) % len(patrol)
                    patrol_target = patrol[path_idx]
                    desired_target = Vector2(patrol_target) if not isinstance(patrol_target, Vector2) else Vector2(patrol_target)
                    if pos.distance_to(desired_target) <= 10.0:
                        wolf["path_idx"] = (path_idx + 1) % len(patrol)
                        wolf["wait"] = 0.28 + random.random() * 0.45
                        wolf["nav_path"] = []
                        continue

        if not isinstance(desired_target, Vector2):
            continue

        nav_obstacles = list(obstacles)
        pr = int(PLAYER_COLLISION_RADIUS)
        nav_obstacles.append(pygame.Rect(int(player_pos.x - pr), int(player_pos.y - pr - 5), pr * 2, pr * 2))
        nav_path_raw = wolf.get("nav_path")
        nav_path = nav_path_raw if isinstance(nav_path_raw, list) else []
        nav_goal_raw = wolf.get("nav_goal")
        nav_goal = nav_goal_raw if isinstance(nav_goal_raw, Vector2) else Vector2(desired_target)
        goal_changed = nav_goal.distance_to(desired_target) > (60.0 if chasing else 24.0)

        if goal_changed or repath_cd <= 0.0 or not nav_path:
            path = find_path_astar(
                pos,
                desired_target,
                walk_bounds,
                nav_obstacles,
                cell_size=max(24, NAV_CELL_SIZE - 4),
                actor_radius=wolf_radius,
                max_expansions=3200 if chasing else 2400,
            )
            nav_path = [Vector2(p) for p in path[1:]] if len(path) > 1 else [Vector2(desired_target)]
            wolf["nav_path"] = nav_path
            wolf["nav_goal"] = Vector2(desired_target)
            wolf["repath_cd"] = 0.28 + random.random() * 0.18

        while nav_path and pos.distance_to(Vector2(nav_path[0])) <= 10.0:
            nav_path.pop(0)
        move_target = Vector2(nav_path[0]) if nav_path else Vector2(desired_target)

        move_speed = float(wolf.get("speed", 94.0))
        move_speed *= clamp(float(wolf.get("status_move_mult", 1.0)), 0.0, 1.0)
        if chasing and role == "support":
            move_speed *= 0.92
        if chasing and role == "engager" and dist_player < 92.0:
            move_speed *= 0.86
        step = move_speed * dt

        candidate = move_with_collision(pos, move_target, step, walk_bounds, nav_obstacles, wolf_radius)
        moved = candidate.distance_to(pos) > 0.01
        wolf["moving"] = moved
        if moved:
            wolf["pos"] = candidate
            alive_pos[idx] = candidate
            heading = move_target - pos
            if abs(heading.x) > 0.03:
                wolf["facing"] = 1 if heading.x > 0 else -1
        else:
            wolf["repath_cd"] = 0.0
            wolf["wait"] = 0.10 if chasing else 0.18
            if not chasing:
                wolf["path_idx"] = (int(wolf.get("path_idx", 0)) + 1) % max(1, len(wolf.get("path", [])))

    # Separation pass with tighter personal space while still preserving pack clustering.
    alive_wolves: List[Dict[str, object]] = [w for w in wolves if float(w.get("hp", 0.0)) > 0.0 and isinstance(w.get("pos"), Vector2)]
    for i in range(len(alive_wolves)):
        wa = alive_wolves[i]
        pa = wa.get("pos")
        if not isinstance(pa, Vector2):
            continue
        ra = max(6.0, float(wa.get("radius", base_radius)))
        for j in range(i + 1, len(alive_wolves)):
            wb = alive_wolves[j]
            pb = wb.get("pos")
            if not isinstance(pb, Vector2):
                continue
            rb = max(6.0, float(wb.get("radius", base_radius)))
            same_pack = int(wa.get("pack_id", -1)) == int(wb.get("pack_id", -2))
            # Same-pack spacing stays compact; cross-pack spacing is wider to preserve cluster identity.
            target_sep = (ra + rb) * (1.58 if same_pack else 2.18)
            delta = pb - pa
            dist_sq = delta.length_squared()
            if dist_sq <= 1e-6 or dist_sq >= target_sep * target_sep:
                continue
            dist = math.sqrt(dist_sq)
            strength = 0.30 if same_pack else 0.26
            overlap = (target_sep - dist) * strength
            push = (delta / dist) * overlap if dist > 1e-6 else Vector2(1.0, 0.0) * overlap

            new_pa = pa - push
            new_pb = pb + push
            if is_walkable(new_pa, walk_bounds, obstacles, ra):
                wa["pos"] = new_pa
                pa = new_pa
            if is_walkable(new_pb, walk_bounds, obstacles, rb):
                wb["pos"] = new_pb


_WOLF_LEVEL_FONT: pygame.font.Font | None = None


def draw_wolf(
    surface: pygame.Surface,
    position: Vector2,
    facing: int,
    sprite_right: pygame.Surface,
    sprite_left: pygame.Surface,
    hp: float,
    max_hp: float,
    level: int = 1,
    selected: bool = False,
    attack_state: str = "idle",
    attack_visual: float = 0.0,
    engage_role: str = "patrol",
    chasing: bool = False,
    anim_frames: Optional[Dict[str, Dict[str, List[pygame.Surface]]]] = None,
    anim_timer: float = 0.0,
    frozen: bool = False,
    frozen_strength: float = 0.0,
    burn_strength: float = 0.0,
    slow_strength: float = 0.0,
    stun_strength: float = 0.0,
    hit_flash_strength: float = 0.0,
    hit_flash_color: Tuple[int, int, int] = (255, 244, 220),
    dying: bool = False,
    death_progress: float = 0.0,
) -> None:
    state = str(attack_state)
    phase = clamp(float(attack_visual), 0.0, 1.0)
    face_sign = 1 if facing >= 0 else -1
    hp_ratio = 0.0 if max_hp <= 0.0 else clamp(hp / max_hp, 0.0, 1.0)
    x = int(position.x)
    y = int(position.y)
    death_progress = clamp(float(death_progress), 0.0, 1.0)
    freeze_power = clamp(float(frozen_strength), 0.0, 1.0)
    attack_scale = 1.0
    attack_tint_strength = 0.0
    if state == "windup":
        x -= int(face_sign * 6.0 * phase)
        y -= int(3.0 * phase)
        attack_scale = 1.0 + 0.14 * phase
        attack_tint_strength = 0.35 + 0.55 * phase
    elif state == "recover":
        lunge = 1.0 - phase
        x += int(face_sign * 18.0 * lunge)
        y -= int(4.0 * lunge)
        attack_scale = 1.0 + 0.08 * lunge
        attack_tint_strength = 0.45 * lunge

    sprite = get_facing_sprite(facing, sprite_right, sprite_left)
    if anim_frames:
        dir_key = facing_to_direction(facing)
        if state in ("windup", "recover"):
            anim_name = "bite"
            anim_fps = 10.4
        elif chasing:
            anim_name = "run"
            anim_fps = 9.2
        else:
            anim_name = "walk"
            anim_fps = 7.2
        animated = get_lpc_frame(anim_frames, anim_name, dir_key, anim_timer, fps=anim_fps)
        if not isinstance(animated, pygame.Surface):
            animated = get_directional_anim_frame(anim_frames, anim_name, dir_key, anim_timer, fps=anim_fps, loop=True)
        if isinstance(animated, pygame.Surface):
            sprite = animated

    ticks = pygame.time.get_ticks()
    if frozen:
        tint = pygame.Surface(sprite.get_size(), pygame.SRCALPHA)
        tint_alpha = int(72 + 126 * freeze_power)
        tint.fill((132, 190, 255, tint_alpha))
        glazed = sprite.copy()
        glazed.blit(tint, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
        # Add thin icy crack highlights to avoid flat blue tint.
        crack = pygame.Surface(sprite.get_size(), pygame.SRCALPHA)
        sw = max(16, sprite.get_width())
        sh = max(16, sprite.get_height())
        phase_a = ticks * 0.0018 + x * 0.013
        for i in range(4):
            px0 = int(sw * (0.18 + i * 0.18))
            py0 = int(sh * (0.24 + (i % 2) * 0.18))
            px1 = int(px0 + math.cos(phase_a + i * 1.3) * (8 + i * 2))
            py1 = int(py0 + 10 + i * 4)
            pygame.draw.aaline(crack, (228, 246, 255, 118), (px0, py0), (px1, py1))
        glazed.blit(crack, (0, 0))
        sprite = glazed
    burn_power = clamp(float(burn_strength), 0.0, 1.0)
    slow_power = clamp(float(slow_strength), 0.0, 1.0)
    stun_power = clamp(float(stun_strength), 0.0, 1.0)
    if burn_power > 0.0 and not frozen:
        tint_b = pygame.Surface(sprite.get_size(), pygame.SRCALPHA)
        tint_b_alpha = int(40 + 80 * burn_power)
        tint_b.fill((255, 100, 20, tint_b_alpha))
        burned = sprite.copy()
        burned.blit(tint_b, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
        sprite = burned
    if slow_power > 0.0 and not frozen:
        tint_s = pygame.Surface(sprite.get_size(), pygame.SRCALPHA)
        tint_s_alpha = int(30 + 50 * slow_power)
        tint_s.fill((80, 140, 220, tint_s_alpha))
        slowed = sprite.copy()
        slowed.blit(tint_s, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
        sprite = slowed
    hit_flash_strength = clamp(float(hit_flash_strength), 0.0, 1.0)
    if hit_flash_strength > 0.0:
        flash_color = hit_flash_color if isinstance(hit_flash_color, tuple) and len(hit_flash_color) == 3 else (255, 244, 220)
        flash = pygame.Surface(sprite.get_size(), pygame.SRCALPHA)
        flash_alpha = int(56 + 168 * hit_flash_strength)
        flash.fill((flash_color[0], flash_color[1], flash_color[2], flash_alpha))
        flashed = sprite.copy()
        flashed.blit(flash, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
        sprite = flashed
    if attack_tint_strength > 0.0:
        atint = pygame.Surface(sprite.get_size(), pygame.SRCALPHA)
        atint_alpha = int(clamp(60.0 + 140.0 * attack_tint_strength, 0.0, 220.0))
        atint.fill((220, 60, 48, atint_alpha))
        tinted = sprite.copy()
        tinted.blit(atint, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
        sprite = tinted
    if abs(attack_scale - 1.0) > 0.005:
        sw = max(8, int(sprite.get_width() * attack_scale))
        sh = max(8, int(sprite.get_height() * attack_scale))
        sprite = pygame.transform.smoothscale(sprite, (sw, sh))
    locomotion = chasing or state in ("windup", "recover")
    gait = math.sin(max(0.0, anim_timer) * (11.6 if chasing else (8.4 if locomotion else 2.6)) + x * 0.012)
    if locomotion:
        y -= int(abs(gait) * (3.2 if chasing else 2.2))
        x += int(gait * (1.4 if chasing else 0.8))
    else:
        y -= int(math.sin(anim_timer * 2.2 + x * 0.02) * 1.2)
    if hp_ratio < 0.35 and locomotion:
        limp = math.sin(anim_timer * 5.2 + x * 0.013)
        if limp > 0.0:
            y += int(limp * 2.4)

    shadow_w = max(34, int(sprite.get_width() * 0.46))
    pygame.draw.ellipse(surface, (10, 10, 12), (x - shadow_w // 2, y - 3, shadow_w, 12))
    if frozen:
        freeze_layer = pygame.Surface((140, 92), pygame.SRCALPHA)
        fx = freeze_layer.get_width() // 2
        fy = freeze_layer.get_height() - 24
        pulse = 0.74 + 0.26 * math.sin(ticks * 0.010 + x * 0.02)
        outer_col = (126, 188, 244, int((86 + 56 * freeze_power) * pulse))
        inner_col = (198, 230, 255, int((120 + 74 * freeze_power) * pulse))
        pygame.gfxdraw.filled_ellipse(freeze_layer, fx, fy, 42, 12, (84, 126, 176, int(34 + 30 * freeze_power)))
        pygame.gfxdraw.aacircle(freeze_layer, fx, fy - 1, 34, outer_col)
        pygame.gfxdraw.aacircle(freeze_layer, fx, fy - 1, 26, inner_col)
        for i in range(8):
            ang = ticks * 0.0016 + i * (math.tau / 8.0)
            px = fx + int(math.cos(ang) * 30)
            py = fy - 2 + int(math.sin(ang) * 8)
            pygame.gfxdraw.filled_circle(freeze_layer, px, py, 2 if i % 2 == 0 else 1, (236, 248, 255, 146))
        surface.blit(freeze_layer, (x - fx, y - 44), special_flags=pygame.BLEND_RGBA_ADD)
    if chasing:
        if str(engage_role) == "engager":
            ring_rect = pygame.Rect(x - shadow_w // 2 - 4, y - 7, shadow_w + 8, 16)
            pygame.draw.ellipse(surface, (176, 66, 74), ring_rect, 1)
        elif str(engage_role) == "support":
            ring_rect = pygame.Rect(x - shadow_w // 2 - 2, y - 6, shadow_w + 4, 14)
            pygame.draw.ellipse(surface, (86, 92, 106), ring_rect, 1)

    if state == "windup":
        tele_w = shadow_w + int(10 + 16 * phase)
        tele_h = 14 + int(4 * phase)
        tele_x = x - tele_w // 2 + int(face_sign * (6.0 + 10.0 * phase))
        tele_rect = pygame.Rect(tele_x, y - 8, tele_w, tele_h)
        pygame.draw.ellipse(surface, (170, 52, 52), tele_rect, 2)
        inner = tele_rect.inflate(-8, -4)
        pygame.draw.ellipse(surface, (226, 130, 132), inner, 1)
    if selected:
        pulse = 0.55 + 0.45 * math.sin(ticks * 0.010)
        ring_w = shadow_w + 12
        ring_h = 16
        ring_rect = pygame.Rect(x - ring_w // 2, y - 8, ring_w, ring_h)
        pygame.draw.ellipse(surface, (172, 58, 66), ring_rect, 2)
        inner_rect = ring_rect.inflate(-10, -4)
        pygame.draw.ellipse(surface, (224, 118, 128), inner_rect, 1)
        if pulse > 0.78:
            glow_rect = ring_rect.inflate(8, 4)
            pygame.draw.ellipse(surface, (236, 148, 160), glow_rect, 1)

    if dying:
        dp = death_progress
        alpha = int(clamp(255.0 * (1.0 - dp * dp), 0.0, 255.0))
        collapse = 1.0 - 0.62 * dp
        new_w = max(4, int(sprite.get_width() * (1.0 + 0.18 * dp)))
        new_h = max(4, int(sprite.get_height() * collapse))
        sprite = pygame.transform.smoothscale(sprite, (new_w, new_h))
        tint = pygame.Surface(sprite.get_size(), pygame.SRCALPHA)
        tint.fill((180, 30, 28, int(90 * (1.0 - dp))))
        sprite.blit(tint, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
        sprite.set_alpha(alpha)
        if dp > 0.15:
            splat_r_x = max(6, int(sprite.get_width() * 0.55 * (0.6 + 0.7 * dp)))
            splat_r_y = max(3, int(7 + 6 * dp))
            splat = pygame.Surface((splat_r_x * 2 + 8, splat_r_y * 2 + 8), pygame.SRCALPHA)
            pygame.draw.ellipse(splat, (118, 18, 18, int(160 * (1.0 - dp * 0.5))), splat.get_rect().inflate(-4, -4))
            pygame.draw.ellipse(splat, (72, 10, 12, int(120 * (1.0 - dp * 0.5))), splat.get_rect().inflate(-12, -10), 2)
            surface.blit(splat, (x - splat.get_width() // 2, y - splat.get_height() // 2 + 2))

    rect = sprite.get_rect(midbottom=(x, y + 1))
    surface.blit(sprite, rect)
    if frozen:
        cage = pygame.Surface((sprite.get_width() + 44, sprite.get_height() + 40), pygame.SRCALPHA)
        cx = cage.get_width() // 2
        cy = cage.get_height() - 14
        shell_h = max(18, int(sprite.get_height() * 0.46))
        shell_w = max(16, int(sprite.get_width() * 0.58))
        top_y = cy - shell_h - 8
        alpha_main = int(104 + 96 * freeze_power)
        alpha_edge = int(66 + 72 * freeze_power)
        for i in range(7):
            ang = (math.tau * i) / 7.0 + ticks * 0.0013
            bx = cx + int(math.cos(ang) * shell_w)
            by = cy - int(abs(math.sin(ang)) * shell_h)
            tx = cx + int(math.cos(ang * 1.12) * (shell_w * 0.52))
            ty = top_y + int(math.sin(ang * 0.8) * 4)
            pygame.draw.aaline(cage, (176, 222, 255, alpha_main), (bx, by), (tx, ty))
        pygame.gfxdraw.aacircle(cage, cx, cy - shell_h // 2, shell_w + 2, (132, 188, 236, alpha_edge))
        pygame.gfxdraw.aacircle(cage, cx, cy - shell_h // 2, max(8, shell_w - 4), (198, 230, 255, alpha_main))
        surface.blit(cage, (rect.centerx - cx, rect.bottom - cage.get_height() + 8), special_flags=pygame.BLEND_RGBA_ADD)
    # ── Burn VFX: flickering flames + ember particles around wolf ──
    if burn_power > 0.0:
        now_b = ticks * 0.001
        # Ground scorch glow
        scorch_a = int(50 * burn_power)
        pygame.gfxdraw.filled_ellipse(surface, x, y + 2, max(6, int(22 * burn_power)), max(3, int(7 * burn_power)), (255, 80, 20, scorch_a))
        # Rising flame wisps
        flame_count = 4 + int(3 * burn_power)
        for fi in range(flame_count):
            f_phase = now_b * 6.0 + fi * 1.7
            f_y_off = (f_phase * 28.0) % 32.0
            f_x_off = math.sin(f_phase * 2.3 + fi * 0.9) * (6 + 4 * burn_power)
            fx_p = x + int(f_x_off) + int(math.sin(fi * 2.1) * 8)
            fy_p = y - int(f_y_off) - 4
            f_life = 1.0 - (f_y_off / 32.0)
            f_size = max(1, int((3.5 + burn_power * 2) * f_life))
            f_alpha = max(12, int(160 * f_life * burn_power))
            # Flame gradient: white-hot → orange → red as it rises
            if f_life > 0.7:
                f_col = (255, 240, 180, f_alpha)
            elif f_life > 0.4:
                f_col = (255, 160, 40, f_alpha)
            else:
                f_col = (200, 60, 20, max(8, f_alpha // 2))
            pygame.gfxdraw.filled_circle(surface, fx_p, fy_p, f_size, f_col)
        # Ember sparks orbiting
        for ei in range(3):
            e_ang = now_b * 4.0 + ei * (math.tau / 3)
            e_r = 12 + int(6 * burn_power)
            ex_p = x + int(math.cos(e_ang) * e_r)
            ey_p = y - 14 + int(math.sin(e_ang * 1.4) * 8)
            e_alpha = max(20, int(140 * burn_power * (0.5 + 0.5 * math.sin(now_b * 8.0 + ei * 2.0))))
            pygame.gfxdraw.filled_circle(surface, ex_p, ey_p, 2, (255, 200, 80, e_alpha))
    # ── Slow VFX: icy chains / blue mist at feet ──
    if slow_power > 0.0 and not frozen:
        now_s = ticks * 0.001
        # Cold ground mist
        mist_a = int(40 * slow_power)
        pygame.gfxdraw.filled_ellipse(surface, x, y + 1, max(8, int(26 * slow_power)), max(4, int(8 * slow_power)), (100, 170, 240, mist_a))
        # Slow chains / ice shards around feet
        chain_count = 5
        for ci in range(chain_count):
            c_ang = now_s * 1.5 + ci * (math.tau / chain_count)
            c_r = 14 + int(6 * slow_power)
            cx_p = x + int(math.cos(c_ang) * c_r)
            cy_p = y - 4 + int(math.sin(c_ang) * c_r * 0.35)
            c_alpha = max(16, int(100 * slow_power))
            pygame.draw.line(surface, (140, 200, 255, c_alpha), (cx_p - 2, cy_p - 3), (cx_p + 2, cy_p + 3), 2)
        # Pale swirl arcs
        for ai in range(2):
            a_ang = now_s * 2.5 + ai * math.pi
            a_r = max(10, int(18 * slow_power))
            arc_rect = pygame.Rect(x - a_r, y - 8 - a_r, a_r * 2, a_r * 2)
            pygame.draw.arc(surface, (160, 210, 255, int(80 * slow_power)), arc_rect, a_ang, a_ang + 1.4, 1)
    # ── Stun VFX: orbiting stars + daze rings ──
    if stun_power > 0.0:
        now_st = ticks * 0.001
        star_y = rect.top - 6
        # Orbiting stars
        star_count = 3 + int(2 * stun_power)
        for si in range(star_count):
            s_ang = now_st * 5.0 + si * (math.tau / star_count)
            s_r = 12 + int(4 * stun_power)
            s_x = x + int(math.cos(s_ang) * s_r)
            s_y = star_y + int(math.sin(s_ang * 0.7) * 4)
            s_alpha = max(30, int(200 * stun_power))
            # 4-pointed star shape
            s_sz = max(2, int(3 * stun_power))
            pygame.draw.line(surface, (255, 240, 100, s_alpha), (s_x - s_sz, s_y), (s_x + s_sz, s_y), 1)
            pygame.draw.line(surface, (255, 240, 100, s_alpha), (s_x, s_y - s_sz), (s_x, s_y + s_sz), 1)
            pygame.gfxdraw.filled_circle(surface, s_x, s_y, max(1, s_sz - 1), (255, 255, 200, s_alpha))
        # Daze ring
        daze_r = max(8, int(16 * stun_power))
        daze_a = int(60 * stun_power * (0.6 + 0.4 * math.sin(now_st * 6.0)))
        pygame.gfxdraw.aacircle(surface, x, star_y, daze_r, (255, 230, 80, daze_a))
    # ── Status effect icons above HP bar ──
    _sfx_icons: List[Tuple[Tuple[int,int,int], str]] = []
    if burn_power > 0.0:
        _sfx_icons.append(((255, 120, 30), "B"))
    if slow_power > 0.0 and not frozen:
        _sfx_icons.append(((100, 180, 255), "S"))
    if stun_power > 0.0:
        _sfx_icons.append(((255, 230, 80), "*"))
    if frozen:
        _sfx_icons.append(((140, 210, 255), "F"))
    if selected and not dying:
        # Small marker above the target, keeps visibility clear.
        mark_y = rect.top - 10 + int(math.sin(ticks * 0.012) * 2.0)
        pygame.draw.circle(surface, (220, 92, 102), (x, mark_y), 4, 1)
        pygame.draw.line(surface, (220, 92, 102), (x - 6, mark_y), (x + 6, mark_y), 1)

    if dying:
        return

    bar_w = 56
    bar_h = 6
    bar = pygame.Rect(x - bar_w // 2, rect.top - 10, bar_w, bar_h)
    pygame.draw.rect(surface, (24, 20, 20), bar, border_radius=3)
    fill = pygame.Rect(bar.left + 1, bar.top + 1, int((bar_w - 2) * hp_ratio), bar_h - 2)
    pygame.draw.rect(surface, (172, 54, 54), fill, border_radius=3)
    pygame.draw.rect(surface, (76, 42, 42), bar, 1, border_radius=3)
    global _WOLF_LEVEL_FONT
    if _WOLF_LEVEL_FONT is None:
        _WOLF_LEVEL_FONT = pygame.font.SysFont("georgia", 12, bold=True)
    lv_text = _WOLF_LEVEL_FONT.render(f"Lv {max(1, int(level))}", True, (222, 196, 128))
    surface.blit(lv_text, (bar.left, bar.top - lv_text.get_height() - 1))
    # Status effect mini-icons next to HP bar
    if _sfx_icons:
        _icon_x = bar.right + 3
        _icon_y = bar.top - 1
        for _ic_col, _ic_lbl in _sfx_icons:
            icon_sz = 10
            pygame.draw.rect(surface, (10, 8, 14, 180), pygame.Rect(_icon_x, _icon_y, icon_sz, icon_sz), border_radius=2)
            pygame.draw.rect(surface, (*_ic_col, 180), pygame.Rect(_icon_x, _icon_y, icon_sz, icon_sz), 1, border_radius=2)
            if _WOLF_LEVEL_FONT is not None:
                _ic_s = _WOLF_LEVEL_FONT.render(_ic_lbl, True, _ic_col)
                surface.blit(_ic_s, (_icon_x + icon_sz // 2 - _ic_s.get_width() // 2, _icon_y + icon_sz // 2 - _ic_s.get_height() // 2))
            _icon_x += icon_sz + 2


def update_summoned_skeletons(
    summons: List[Dict[str, object]],
    dt: float,
    player_pos: Vector2,
    wolves: List[Dict[str, object]],
    walk_bounds: pygame.Rect,
    obstacles: List[pygame.Rect],
    damage_numbers: Optional[List[Dict[str, object]]] = None,
    spell_effects: Optional[List[Dict[str, object]]] = None,
) -> None:
    if dt <= 0.0 or not summons:
        return

    wolf_lookup: Dict[int, Dict[str, object]] = {
        id(wolf): wolf
        for wolf in wolves
        if float(wolf.get("hp", 0.0)) > 0.0 and isinstance(wolf.get("pos"), Vector2)
    }
    kept: List[Dict[str, object]] = []

    for idx, summon in enumerate(summons):
        life = max(0.0, float(summon.get("life", 0.0)) - dt)
        if life <= 0.0:
            continue
        summon["life"] = life
        summon["attack_cd"] = max(0.0, float(summon.get("attack_cd", 0.0)) - dt)
        summon["ambient_timer"] = float(summon.get("ambient_timer", 0.0)) + dt
        summon["swing"] = max(0.0, float(summon.get("swing", 0.0)) - dt)

        pos_raw = summon.get("pos")
        if not isinstance(pos_raw, Vector2):
            continue
        pos = Vector2(pos_raw)
        summon["pos"] = pos
        home_raw = summon.get("home")
        home = Vector2(home_raw) if isinstance(home_raw, Vector2) else Vector2(pos)

        target_id = summon.get("target_id")
        target = wolf_lookup.get(int(target_id)) if isinstance(target_id, (int, float)) else None
        aggro_radius = max(140.0, float(summon.get("aggro_radius", 320.0)))
        if not isinstance(target, dict):
            best_target: Optional[Dict[str, object]] = None
            best_score = 1e12
            for wolf in wolves:
                if float(wolf.get("hp", 0.0)) <= 0.0:
                    continue
                wpos = wolf.get("pos")
                if not isinstance(wpos, Vector2):
                    continue
                dist = pos.distance_to(wpos)
                if dist > aggro_radius:
                    continue
                score = dist + player_pos.distance_to(wpos) * 0.10
                if score >= best_score:
                    continue
                best_score = score
                best_target = wolf
            target = best_target
            summon["target_id"] = id(target) if isinstance(target, dict) else None

        move_target: Optional[Vector2] = None
        if isinstance(target, dict):
            tpos_raw = target.get("pos")
            if isinstance(tpos_raw, Vector2):
                tpos = Vector2(tpos_raw)
                attack_range = max(32.0, float(summon.get("attack_range", 44.0)))
                to_target = tpos - pos
                dist = to_target.length()
                if dist <= attack_range:
                    if float(summon.get("attack_cd", 0.0)) <= 0.0:
                        dealt = damage_wolf_entity(target, float(summon.get("damage", 14.0)), damage_numbers, Vector2(tpos))
                        if dealt > 0.0:
                            summon["attack_cd"] = max(0.28, float(summon.get("attack_interval", 0.72)))
                            summon["swing"] = 0.18
                            target["chasing"] = True
                            target["aggro_timer"] = max(float(target.get("aggro_timer", 0.0)), 0.9)
                            if isinstance(spell_effects, list):
                                spawn_blood_splatter(spell_effects, Vector2(tpos), intensity=0.75)
                                spawn_particle_burst(
                                    spell_effects,
                                    Vector2(tpos.x, tpos.y - 8.0),
                                    (214, 198, 226),
                                    (132, 104, 166),
                                    count=4,
                                    speed_min=60.0,
                                    speed_max=160.0,
                                    life_min=0.10,
                                    life_max=0.24,
                                    size_start=3.0,
                                    size_end=0.5,
                                    spread=0.9,
                                    direction=to_target if dist > 1e-5 else Vector2(1.0, 0.0),
                                    gravity=-10.0,
                                    drag=1.4,
                                    vfx_scale=0.8,
                                )
                    if dist > 1e-5:
                        summon["facing"] = 1 if to_target.x >= 0.0 else -1
                else:
                    move_target = tpos
                    if abs(to_target.x) > 0.03:
                        summon["facing"] = 1 if to_target.x > 0 else -1
            else:
                summon["target_id"] = None
        else:
            orbit_phase = float(summon.get("orbit_phase", 0.0)) + dt * (0.8 + idx * 0.07)
            summon["orbit_phase"] = orbit_phase
            offset = Vector2(math.cos(orbit_phase), math.sin(orbit_phase * 1.25)) * (42.0 + (idx % 3) * 8.0)
            anchor = player_pos + offset
            if anchor.distance_to(home) > 240.0:
                anchor = home.lerp(player_pos, 0.45)
            if pos.distance_to(anchor) > 14.0:
                move_target = anchor
                if abs(anchor.x - pos.x) > 0.03:
                    summon["facing"] = 1 if anchor.x > pos.x else -1

        if isinstance(move_target, Vector2):
            speed = max(60.0, float(summon.get("speed", 150.0)))
            step = speed * dt
            pos = move_with_collision(pos, move_target, step, walk_bounds, obstacles, max(8.0, float(summon.get("radius", 14.0))))
            summon["pos"] = pos

        if float(summon.get("ambient_timer", 0.0)) >= 0.18:
            summon["ambient_timer"] = 0.0
            if isinstance(spell_effects, list):
                spawn_particle_burst(
                    spell_effects,
                    Vector2(pos.x, pos.y - 18.0),
                    (210, 200, 224),
                    (112, 88, 148),
                    count=2,
                    speed_min=18.0,
                    speed_max=42.0,
                    life_min=0.12,
                    life_max=0.28,
                    size_start=2.6,
                    size_end=0.4,
                    spread=math.tau,
                    gravity=-12.0,
                    drag=1.1,
                    vfx_scale=0.7,
                )

        kept.append(summon)

    summons[:] = kept


def draw_summoned_skeleton(
    surface: pygame.Surface,
    position: Vector2,
    facing: int,
    life: float,
    duration: float,
    level: int = 1,
    swing: float = 0.0,
) -> None:
    x = int(position.x)
    y = int(position.y)
    ticks = pygame.time.get_ticks()
    attack_phase = clamp(float(swing) / 0.18, 0.0, 1.0)
    slash_arc = math.sin(attack_phase * math.pi)
    idle_wave = math.sin(ticks * 0.0075 + x * 0.013)
    idle_bob = int(idle_wave * 2.0)
    stride = int(math.sin(ticks * 0.0095 + x * 0.016) * 3.0)
    y -= int(attack_phase * 4.0)

    pygame.draw.ellipse(surface, (10, 8, 14), (x - 20, y - 2, 40, 11))
    ring = pygame.Surface((72, 42), pygame.SRCALPHA)
    pygame.draw.ellipse(ring, (106, 78, 146, 42), pygame.Rect(8, 12, 56, 16))
    pygame.draw.ellipse(ring, (164, 134, 210, 28), pygame.Rect(14, 8, 44, 22), 1)
    surface.blit(ring, (x - 36, y - 14))

    sprite = pygame.Surface((84, 92), pygame.SRCALPHA)
    bone_shadow = (116, 110, 98)
    bone = (206, 202, 188)
    bone_high = (236, 232, 216)
    plate_dark = (46, 40, 54)
    plate_mid = (90, 82, 110)
    cloth_dark = (26, 18, 30)
    cloth_mid = (68, 48, 82)
    necro_glow = (170, 154, 214)
    rune_glow = (210, 198, 246)
    steel = (154, 164, 182)
    steel_shadow = (90, 96, 112)

    def bone_segment(start: Tuple[int, int], end: Tuple[int, int], width: int) -> None:
        pygame.draw.line(sprite, bone_shadow, (start[0] + 1, start[1] + 1), (end[0] + 1, end[1] + 1), max(1, width + 1))
        pygame.draw.line(sprite, bone, start, end, max(1, width))
        if width > 2:
            pygame.draw.line(sprite, bone_high, start, end, max(1, width - 2))

    def bone_joint(center: Tuple[int, int], radius: int) -> None:
        pygame.draw.circle(sprite, bone_shadow, (center[0] + 1, center[1] + 1), radius)
        pygame.draw.circle(sprite, bone, center, radius)
        if radius > 2:
            pygame.draw.circle(sprite, bone_high, (center[0] - 1, center[1] - 1), max(1, radius - 2))

    base_x = 34
    ground_y = 78
    hip = (base_x + 1, ground_y - 28 + idle_bob)
    chest = (base_x + 2, ground_y - 48 + idle_bob)
    head = (base_x + 2, ground_y - 66 + idle_bob)
    left_knee = (hip[0] - 6, ground_y - 15 + stride)
    right_knee = (hip[0] + 7, ground_y - 17 - stride)
    left_foot = (hip[0] - 11, ground_y)
    right_foot = (hip[0] + 12 + int(attack_phase * 2.0), ground_y - int(attack_phase * 2.0))
    left_shoulder = (chest[0] - 11, chest[1] - 1)
    right_shoulder = (chest[0] + 11, chest[1] - 1)
    left_elbow = (left_shoulder[0] - 8, chest[1] + 8 + stride // 2)
    left_hand = (left_elbow[0] - 6, left_elbow[1] + 7)
    right_elbow = (right_shoulder[0] + 8 + int(attack_phase * 4.0), chest[1] + 4 - int(slash_arc * 5.0))
    right_hand = (right_elbow[0] + 7 + int(attack_phase * 7.0), right_elbow[1] + 7 - int(slash_arc * 8.0))
    shield_center = (left_hand[0] - 7, left_hand[1] - 1)
    blade_guard = (right_hand[0] + 4, right_hand[1] - 1)
    blade_tip = (blade_guard[0] + 18 + int(attack_phase * 10.0), blade_guard[1] - 16 - int(slash_arc * 12.0))

    cloak = [
        (chest[0] - 13, chest[1] - 8),
        (chest[0] - 4, chest[1] + 4),
        (hip[0] - 2, hip[1] + 3),
        (hip[0] - 18, ground_y - 3),
        (hip[0] - 10, ground_y + 2),
        (hip[0] - 2, ground_y - 6),
    ]
    pygame.draw.polygon(sprite, cloth_dark, cloak)
    pygame.draw.lines(sprite, cloth_mid, False, cloak[:4], 2)
    pygame.draw.line(sprite, cloth_mid, cloak[3], cloak[5], 1)

    for wisp_x, wisp_y in ((hip[0] - 10, ground_y - 2), (hip[0] - 14, ground_y - 8), (hip[0] - 5, ground_y - 10)):
        pygame.draw.circle(sprite, necro_glow, (wisp_x, wisp_y), 1)
        pygame.draw.line(sprite, necro_glow, (wisp_x, wisp_y), (wisp_x - 4, wisp_y - 6), 1)

    bone_segment(hip, left_knee, 5)
    bone_segment(left_knee, left_foot, 4)
    bone_segment(hip, right_knee, 5)
    bone_segment(right_knee, right_foot, 4)
    pygame.draw.polygon(sprite, steel_shadow, [(left_foot[0] - 2, left_foot[1]), (left_foot[0] + 5, left_foot[1] - 1), (left_foot[0] + 3, left_foot[1] + 2)])
    pygame.draw.polygon(sprite, steel_shadow, [(right_foot[0] - 1, right_foot[1]), (right_foot[0] + 6, right_foot[1] - 2), (right_foot[0] + 4, right_foot[1] + 2)])
    bone_joint(left_knee, 3)
    bone_joint(right_knee, 3)

    pelvis_rect = pygame.Rect(hip[0] - 9, hip[1] - 4, 18, 10)
    pygame.draw.ellipse(sprite, bone_shadow, pelvis_rect.move(1, 1))
    pygame.draw.ellipse(sprite, bone, pelvis_rect)
    pygame.draw.ellipse(sprite, bone_high, pelvis_rect.inflate(-6, -4))

    bone_segment((hip[0], hip[1] - 2), (chest[0], chest[1] + 8), 4)
    for spine_y in range(hip[1] - 5, chest[1] + 6, -5):
        bone_joint((hip[0] + (spine_y % 2), spine_y), 2)

    rib_rect = pygame.Rect(chest[0] - 12, chest[1] - 9, 24, 19)
    pygame.draw.ellipse(sprite, bone_shadow, rib_rect.move(1, 1))
    pygame.draw.ellipse(sprite, bone, rib_rect)
    pygame.draw.ellipse(sprite, plate_dark, rib_rect.inflate(-8, -6))
    for rib_y in (rib_rect.top + 5, rib_rect.top + 9, rib_rect.top + 13):
        pygame.draw.line(sprite, bone_shadow, (rib_rect.left + 4, rib_y + 1), (rib_rect.right - 4, rib_y + 1), 2)
        pygame.draw.line(sprite, bone, (rib_rect.left + 4, rib_y), (rib_rect.right - 4, rib_y), 1)
    sternum = pygame.Rect(chest[0] - 2, rib_rect.top + 3, 4, 13)
    pygame.draw.rect(sprite, bone, sternum, border_radius=2)
    pygame.draw.rect(sprite, bone_high, sternum.inflate(-2, -2), border_radius=2)

    left_plate = [(left_shoulder[0] - 5, left_shoulder[1] - 2), (left_shoulder[0] + 4, left_shoulder[1] - 4), (left_shoulder[0] + 2, left_shoulder[1] + 5), (left_shoulder[0] - 7, left_shoulder[1] + 3)]
    right_plate = [(right_shoulder[0] - 4, right_shoulder[1] - 4), (right_shoulder[0] + 5, right_shoulder[1] - 2), (right_shoulder[0] + 7, right_shoulder[1] + 3), (right_shoulder[0] - 2, right_shoulder[1] + 5)]
    pygame.draw.polygon(sprite, plate_dark, left_plate)
    pygame.draw.polygon(sprite, plate_dark, right_plate)
    pygame.draw.lines(sprite, plate_mid, True, left_plate, 1)
    pygame.draw.lines(sprite, plate_mid, True, right_plate, 1)

    bone_segment(left_shoulder, left_elbow, 4)
    bone_segment(left_elbow, left_hand, 3)
    bone_joint(left_elbow, 3)
    shield_rect = pygame.Rect(shield_center[0] - 6, shield_center[1] - 9, 12, 18)
    pygame.draw.ellipse(sprite, plate_dark, shield_rect)
    pygame.draw.ellipse(sprite, plate_mid, shield_rect, 2)
    pygame.draw.line(sprite, rune_glow, (shield_center[0], shield_center[1] - 5), (shield_center[0], shield_center[1] + 5), 1)
    pygame.draw.line(sprite, rune_glow, (shield_center[0] - 3, shield_center[1]), (shield_center[0] + 3, shield_center[1]), 1)
    pygame.draw.circle(sprite, necro_glow, shield_center, 1)

    bone_segment(right_shoulder, right_elbow, 4)
    bone_segment(right_elbow, right_hand, 3)
    bone_joint(right_elbow, 3)
    pygame.draw.line(sprite, steel_shadow, (right_hand[0] + 1, right_hand[1] + 2), (blade_guard[0] + 1, blade_guard[1] + 2), 3)
    pygame.draw.line(sprite, steel, right_hand, blade_guard, 2)
    pygame.draw.line(sprite, plate_mid, (blade_guard[0] - 3, blade_guard[1] + 2), (blade_guard[0] + 4, blade_guard[1] - 3), 2)
    blade = [blade_guard, (blade_guard[0] + 16, blade_guard[1] - 4), blade_tip, (blade_guard[0] + 12, blade_guard[1] - 1)]
    pygame.draw.polygon(sprite, steel_shadow, [(p[0] + 1, p[1] + 1) for p in blade])
    pygame.draw.polygon(sprite, steel, blade)
    pygame.draw.line(sprite, bone_high, (blade_guard[0] + 2, blade_guard[1] - 1), (blade_tip[0] - 3, blade_tip[1] + 3), 1)
    if attack_phase > 0.08:
        arc_rect = pygame.Rect(blade_tip[0] - 12, blade_tip[1] - 6, 20, 18)
        pygame.draw.arc(sprite, necro_glow, arc_rect, -1.05, 0.45, 2)

    skull_rect = pygame.Rect(head[0] - 9, head[1] - 8, 18, 18)
    pygame.draw.ellipse(sprite, bone_shadow, skull_rect.move(1, 1))
    pygame.draw.ellipse(sprite, bone, skull_rect)
    pygame.draw.ellipse(sprite, bone_high, skull_rect.inflate(-6, -5))
    jaw_rect = pygame.Rect(head[0] - 6, head[1] + 5, 12, 6)
    pygame.draw.rect(sprite, bone, jaw_rect, border_radius=2)
    pygame.draw.rect(sprite, bone_high, jaw_rect.inflate(-4, -2), border_radius=2)
    eye_left = (head[0] - 4, head[1] - 1)
    eye_right = (head[0] + 4, head[1] - 1)
    pygame.draw.circle(sprite, plate_dark, eye_left, 3)
    pygame.draw.circle(sprite, plate_dark, eye_right, 3)
    pygame.draw.circle(sprite, necro_glow, eye_left, 2)
    pygame.draw.circle(sprite, necro_glow, eye_right, 2)
    pygame.draw.polygon(sprite, plate_dark, [(head[0], head[1] + 1), (head[0] - 2, head[1] + 5), (head[0] + 2, head[1] + 5)])
    pygame.draw.line(sprite, plate_mid, (head[0] - 2, head[1] - 7), (head[0] + 3, head[1] - 4), 1)
    pygame.draw.line(sprite, plate_mid, (head[0] + 1, head[1] - 4), (head[0] + 6, head[1] - 8), 1)

    if int(facing) < 0:
        sprite = pygame.transform.flip(sprite, True, False)

    rect = sprite.get_rect(midbottom=(x, y + 1))
    surface.blit(sprite, rect)

    life_ratio = 0.0 if duration <= 0.0 else clamp(float(life) / float(duration), 0.0, 1.0)
    bar = pygame.Rect(x - 20, rect.top - 9, 40, 5)
    pygame.draw.rect(surface, (24, 20, 24), bar, border_radius=2)
    fill_w = int((bar.width - 2) * life_ratio)
    if fill_w > 0:
        fill = pygame.Rect(bar.left + 1, bar.top + 1, fill_w, bar.height - 2)
        pygame.draw.rect(surface, (148, 122, 206), fill, border_radius=2)
    pygame.draw.rect(surface, (74, 58, 108), bar, 1, border_radius=2)
    global _WOLF_LEVEL_FONT
    if _WOLF_LEVEL_FONT is None:
        _WOLF_LEVEL_FONT = pygame.font.SysFont("georgia", 12, bold=True)
    if _WOLF_LEVEL_FONT is not None:
        txt = _WOLF_LEVEL_FONT.render(f"S{max(1, int(level))}", True, (220, 214, 232))
        surface.blit(txt, txt.get_rect(midbottom=(x, bar.top - 1)))


def draw_passive_animal(
    surface: pygame.Surface,
    position: Vector2,
    facing: int,
    sprite_right: pygame.Surface,
    sprite_left: pygame.Surface,
    hp: float,
    max_hp: float,
    anim_frames: Optional[Dict[str, Dict[str, List[pygame.Surface]]]] = None,
    anim_timer: float = 0.0,
    name: str = "",
    moving: bool = False,
) -> None:
    species = str(name).strip().lower()
    is_bird = any(tag in species for tag in ("owl", "duck", "goose", "crow", "pheasant", "wildfowl", "crane", "turkey"))
    is_hopper = any(tag in species for tag in ("hare", "rabbit"))
    is_heavy = any(tag in species for tag in ("deer", "doe", "fawn", "ram", "elk", "caribou", "goat", "yak", "ox"))
    x = int(position.x)
    y = int(position.y)
    sprite = get_facing_sprite(facing, sprite_right, sprite_left)
    if anim_frames:
        dir_key = facing_to_direction(facing)
        animated = get_directional_anim_frame(anim_frames, "walk", dir_key, anim_timer, fps=6.4, loop=True)
        if not isinstance(animated, pygame.Surface):
            animated = get_directional_anim_frame(anim_frames, "idle", dir_key, anim_timer, fps=5.2, loop=True)
        if isinstance(animated, pygame.Surface):
            sprite = animated
    t = max(0.0, float(anim_timer))
    if moving:
        if is_hopper:
            hop = abs(math.sin(t * 12.4))
            y -= int(hop * 4.4)
            x += int(math.sin(t * 6.8) * 1.4)
        elif is_bird:
            flap = abs(math.sin(t * 13.0))
            y -= int(flap * 2.8)
            x += int(math.sin(t * 7.0) * 1.6)
        elif is_heavy:
            y -= int(abs(math.sin(t * 6.2)) * 2.5)
        else:
            y -= int(abs(math.sin(t * 8.5)) * 2.0)
    else:
        y -= int(math.sin(t * 2.1 + x * 0.02) * (1.2 if is_bird else 0.8))
    shadow_w = max(24, int(sprite.get_width() * 0.46))
    shadow_h = 9 if moving else 8
    pygame.draw.ellipse(surface, (10, 10, 12), (x - shadow_w // 2, y - 2, shadow_w, shadow_h))
    rect = sprite.get_rect(midbottom=(x, y + 1))
    surface.blit(sprite, rect)
    if is_bird and moving and anim_frames is None:
        wing = int(4 + abs(math.sin(t * 13.4)) * 5)
        wy = rect.centery - 6
        col = (214, 214, 218)
        pygame.draw.line(surface, col, (rect.centerx - wing, wy), (rect.centerx - 1, wy - 2), 1)
        pygame.draw.line(surface, col, (rect.centerx + 1, wy - 2), (rect.centerx + wing, wy), 1)

    hp_ratio = 0.0 if max_hp <= 0.0 else clamp(hp / max_hp, 0.0, 1.0)
    if hp_ratio < 1.0:
        bar_w = 40
        bar_h = 5
        bar = pygame.Rect(x - bar_w // 2, rect.top - 8, bar_w, bar_h)
        pygame.draw.rect(surface, (24, 20, 20), bar, border_radius=3)
        fill = pygame.Rect(bar.left + 1, bar.top + 1, int((bar_w - 2) * hp_ratio), bar_h - 2)
        pygame.draw.rect(surface, (60, 160, 70), fill, border_radius=3)
        pygame.draw.rect(surface, (40, 70, 40), bar, 1, border_radius=3)


def draw_town_portal(
    surface: pygame.Surface,
    world_pos: Vector2,
    camera: Vector2,
    ticks: int,
    hovered: bool,
) -> None:
    sx = int(world_pos.x - camera.x)
    sy = int(world_pos.y - camera.y)
    if sx < -220 or sx > SCREEN_WIDTH + 220 or sy < -220 or sy > SCREEN_HEIGHT + 220:
        return

    pulse = 0.55 + 0.45 * math.sin(ticks * 0.006)
    outer_r = int(66 + pulse * 10)
    inner_r = int(34 + pulse * 6)

    # Ground glow
    pygame.gfxdraw.filled_circle(surface, sx, sy, outer_r, (88, 132, 255, int(58 + pulse * 52)))
    pygame.gfxdraw.filled_circle(surface, sx, sy, inner_r, (162, 118, 255, int(70 + pulse * 40)))

    # Portal ring + inner swirl
    ring_col = (206, 188, 255) if hovered else (164, 148, 236)
    core_col = (86, 114, 246)
    pygame.draw.circle(surface, ring_col, (sx, sy), outer_r, 4)
    pygame.draw.circle(surface, (56, 72, 168), (sx, sy), outer_r - 8, 2)
    pygame.draw.circle(surface, core_col, (sx, sy), inner_r)

    a0 = ticks * 0.004
    for i in range(3):
        rr = int(inner_r * (0.52 + i * 0.22))
        start = a0 + i * 1.2
        end = start + 1.6
        pygame.draw.arc(surface, (224, 230, 255), pygame.Rect(sx - rr, sy - rr, rr * 2, rr * 2), start, end, 2)

    # Vertical wisps for a Diablo-like portal feel.
    for i in range(8):
        ang = (ticks * 0.005 + i * 0.75)
        wx = sx + int(math.cos(ang) * (inner_r - 6))
        wy = sy - int(12 + (math.sin(ang * 1.7) * 10))
        pygame.gfxdraw.filled_ellipse(surface, wx, wy - 8, 9, 18, (180, 200, 255, 78))

    # Orbiting rune sparks around the frame.
    rune_count = 10
    for i in range(rune_count):
        ang = ticks * 0.0028 + i * (math.tau / rune_count)
        rr = outer_r + 8 + int(math.sin(ticks * 0.004 + i * 0.8) * 4)
        rx = sx + int(math.cos(ang) * rr)
        ry = sy + int(math.sin(ang) * rr * 0.72)
        spark_alpha = 150 + int(70 * math.sin(ticks * 0.01 + i))
        spark = pygame.Surface((12, 12), pygame.SRCALPHA)
        pygame.gfxdraw.filled_circle(surface, rx, ry, 3, (186, 210, 255, max(40, spark_alpha)))
        pygame.gfxdraw.aacircle(surface, rx, ry, 5, (116, 170, 255, max(24, spark_alpha // 2)))

    # Rising core particles.
    rise_count = 22 if hovered else 16
    for i in range(rise_count):
        t = (ticks * 0.0025 + i * 0.17) % 1.0
        ang = ticks * 0.003 + i * 0.58
        rad = inner_r * (0.24 + 0.62 * t)
        px = sx + int(math.cos(ang) * rad * 0.58)
        py = sy + int(math.sin(ang * 1.8) * 7 - t * (36 + inner_r * 0.85))
        alpha = int((1.0 - t) * (170 if hovered else 138))
        pcol = (162, 208, 255, max(24, alpha))
        pygame.gfxdraw.filled_circle(surface, px, py, 2, pcol)
        pygame.gfxdraw.aacircle(surface, px, py, 2, pcol)

    # Subtle runic ground ring.
    rune_ring_r = outer_r + 18
    for i in range(14):
        ang = ticks * 0.0018 + i * (math.tau / 14.0)
        gx = sx + int(math.cos(ang) * rune_ring_r)
        gy = sy + int(math.sin(ang) * rune_ring_r * 0.64)
        rune_h = 6 + (i % 3)
        pygame.draw.line(surface, (104, 132, 216), (gx, gy - rune_h // 2), (gx, gy + rune_h // 2), 1)
        pygame.draw.line(surface, (188, 208, 255), (gx - 1, gy), (gx + 1, gy), 1)

def draw_book_portal(
    surface: pygame.Surface,
    world_pos: Vector2,
    camera: Vector2,
    ticks: int,
    progress: float = 1.0,
) -> None:
    """Yellow / gold teleportation portal spawned by Book of Teleportation.
    *progress* 0→1 controls the opening animation (size ramp-up)."""
    sx = int(world_pos.x - camera.x)
    sy = int(world_pos.y - camera.y)
    if sx < -240 or sx > SCREEN_WIDTH + 240 or sy < -240 or sy > SCREEN_HEIGHT + 240:
        return

    ease = min(1.0, progress * 1.4)  # fast open
    pulse = 0.55 + 0.45 * math.sin(ticks * 0.007)
    base_outer = int((70 + pulse * 12) * ease)
    base_inner = int((36 + pulse * 7) * ease)

    # Ground glow — warm gold
    pygame.gfxdraw.filled_circle(surface, sx, sy, base_outer, (255, 200, 50, int((55 + pulse * 50) * ease)))
    pygame.gfxdraw.filled_circle(surface, sx, sy, base_inner, (255, 160, 30, int((65 + pulse * 40) * ease)))

    # Ring + inner core
    ring_col = (255, 230, 130)
    core_col = (220, 170, 40)
    pygame.draw.circle(surface, ring_col, (sx, sy), base_outer, 4)
    pygame.draw.circle(surface, (180, 130, 20), (sx, sy), base_outer - 8, 2)
    pygame.draw.circle(surface, core_col, (sx, sy), base_inner)

    # Inner swirl arcs
    a0 = ticks * 0.005
    for i in range(3):
        rr = int(base_inner * (0.52 + i * 0.22))
        start = a0 + i * 1.2
        end = start + 1.6
        pygame.draw.arc(surface, (255, 245, 200), pygame.Rect(sx - rr, sy - rr, rr * 2, rr * 2), start, end, 2)

    # Vertical wisps — golden
    for i in range(8):
        ang = (ticks * 0.006 + i * 0.75)
        wx = sx + int(math.cos(ang) * (base_inner - 6))
        wy = sy - int(12 + (math.sin(ang * 1.7) * 10))
        pygame.gfxdraw.filled_ellipse(surface, wx, wy - 8, 9, 18, (255, 220, 80, 72))

    # Orbiting sparks — amber
    rune_count = 10
    for i in range(rune_count):
        ang = ticks * 0.003 + i * (math.tau / rune_count)
        rr = base_outer + 8 + int(math.sin(ticks * 0.005 + i * 0.8) * 4)
        rx = sx + int(math.cos(ang) * rr)
        ry = sy + int(math.sin(ang) * rr * 0.72)
        spark_alpha = 150 + int(70 * math.sin(ticks * 0.012 + i))
        pygame.gfxdraw.filled_circle(surface, rx, ry, 3, (255, 220, 80, max(40, spark_alpha)))
        pygame.gfxdraw.aacircle(surface, rx, ry, 5, (255, 180, 40, max(24, spark_alpha // 2)))

    # Rising core particles — gold
    rise_count = 20
    for i in range(rise_count):
        t = (ticks * 0.003 + i * 0.17) % 1.0
        ang = ticks * 0.004 + i * 0.58
        rad = base_inner * (0.24 + 0.62 * t)
        px = sx + int(math.cos(ang) * rad * 0.58)
        py = sy + int(math.sin(ang * 1.8) * 7 - t * (36 + base_inner * 0.85))
        alpha = int((1.0 - t) * 150)
        pcol = (255, 230, 100, max(24, alpha))
        pygame.gfxdraw.filled_circle(surface, px, py, 2, pcol)
        pygame.gfxdraw.aacircle(surface, px, py, 2, pcol)

    # Ground rune ring — amber
    rune_ring_r = base_outer + 18
    for i in range(14):
        ang = ticks * 0.002 + i * (math.tau / 14.0)
        gx = sx + int(math.cos(ang) * rune_ring_r)
        gy = sy + int(math.sin(ang) * rune_ring_r * 0.64)
        rune_h = 6 + (i % 3)
        pygame.draw.line(surface, (200, 160, 40), (gx, gy - rune_h // 2), (gx, gy + rune_h // 2), 1)
        pygame.draw.line(surface, (255, 230, 120), (gx - 1, gy), (gx + 1, gy), 1)

def draw_ice_portal(
    surface: pygame.Surface,
    world_pos: Vector2,
    camera: Vector2,
    ticks: int,
    hovered: bool,
) -> None:
    sx = int(world_pos.x - camera.x)
    sy = int(world_pos.y - camera.y)
    if sx < -220 or sx > SCREEN_WIDTH + 220 or sy < -220 or sy > SCREEN_HEIGHT + 220:
        return

    pulse = 0.55 + 0.45 * math.sin(ticks * 0.006)
    outer_r = int(66 + pulse * 10)
    inner_r = int(34 + pulse * 6)

    # Icy ground glow
    pygame.gfxdraw.filled_circle(surface, sx, sy, outer_r, (60, 200, 255, int(50 + pulse * 48)))
    pygame.gfxdraw.filled_circle(surface, sx, sy, inner_r, (180, 240, 255, int(65 + pulse * 38)))

    # Portal ring + inner frost
    ring_col = (220, 248, 255) if hovered else (140, 210, 250)
    core_col = (30, 140, 220)
    pygame.draw.circle(surface, ring_col, (sx, sy), outer_r, 4)
    pygame.draw.circle(surface, (20, 90, 160), (sx, sy), outer_r - 8, 2)
    pygame.draw.circle(surface, core_col, (sx, sy), inner_r)

    # Frost swirl arcs
    a0 = ticks * 0.004
    for i in range(3):
        rr = int(inner_r * (0.52 + i * 0.22))
        start = a0 + i * 1.2
        end = start + 1.6
        pygame.draw.arc(surface, (200, 240, 255), pygame.Rect(sx - rr, sy - rr, rr * 2, rr * 2), start, end, 2)

    # Snowflake wisps
    for i in range(8):
        ang = (ticks * 0.005 + i * 0.75)
        wx = sx + int(math.cos(ang) * (inner_r - 6))
        wy = sy - int(12 + (math.sin(ang * 1.7) * 10))
        pygame.gfxdraw.filled_ellipse(surface, wx, wy - 8, 8, 16, (230, 248, 255, 80))

    # Orbiting ice sparks
    for i in range(10):
        ang = ticks * 0.0028 + i * (math.tau / 10)
        rr = outer_r + 8 + int(math.sin(ticks * 0.004 + i * 0.8) * 4)
        rx = sx + int(math.cos(ang) * rr)
        ry = sy + int(math.sin(ang) * rr * 0.72)
        spark_alpha = 150 + int(70 * math.sin(ticks * 0.01 + i))
        pygame.gfxdraw.filled_circle(surface, rx, ry, 3, (200, 240, 255, max(40, spark_alpha)))
        pygame.gfxdraw.aacircle(surface, rx, ry, 5, (140, 210, 255, max(24, spark_alpha // 2)))

    # Rising frost particles
    rise_count = 22 if hovered else 16
    for i in range(rise_count):
        t = (ticks * 0.0025 + i * 0.17) % 1.0
        ang = ticks * 0.003 + i * 0.58
        rad = inner_r * (0.24 + 0.62 * t)
        px = sx + int(math.cos(ang) * rad * 0.58)
        py = sy + int(math.sin(ang * 1.8) * 7 - t * (36 + inner_r * 0.85))
        alpha = int((1.0 - t) * (170 if hovered else 138))
        pcol = (210, 245, 255, max(24, alpha))
        pygame.gfxdraw.filled_circle(surface, px, py, 2, pcol)
        pygame.gfxdraw.aacircle(surface, px, py, 2, pcol)

    # Ground rune ring
    rune_ring_r = outer_r + 18
    for i in range(14):
        ang = ticks * 0.0018 + i * (math.tau / 14.0)
        gx = sx + int(math.cos(ang) * rune_ring_r)
        gy = sy + int(math.sin(ang) * rune_ring_r * 0.64)
        rune_h = 6 + (i % 3)
        pygame.draw.line(surface, (80, 180, 230), (gx, gy - rune_h // 2), (gx, gy + rune_h // 2), 1)
        pygame.draw.line(surface, (200, 240, 255), (gx - 1, gy), (gx + 1, gy), 1)
