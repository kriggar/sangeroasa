"""game/vendors.py — vendor placement/spawning, shop positioning, city population,
vendor update AI, and vendor/stand/quest-marker rendering."""
import math
import random
from typing import Dict, List, Optional, Tuple, Any, Union, Set

import pygame
from pygame import Vector2

from game.constants import *
from game.utils import *
from game.nav import *
from game.vfx import *
from game.gameplay_math import *
from game.sprites import *
from game.render.props import *
from game.render.glyphs import *
from game.render.shops import *
from game.items import *

__all__ = [
    '_build_vendor_ring_positions',
    '_build_vendor_scatter_positions',
    'build_vendors',
    'relocate_blacksmith_shop_to',
    'get_blacksmith_shop_pos',
    'keep_player_out_of_blacksmith_shop',
    'blacksmith_shop_anchor_from_lamppost',
    'build_city_population',
    'update_vendors',
    'draw_player',
    '_shop_offset',
    'vendor_shop_position',
    'find_vendor_shop_pos',
    'build_shop_patrol_points',
    'build_blacksmith_patrol_points',
    'blacksmith_shop_collision_rects',
    'spell_collision_obstacles',
    '_seeded_barrel',
    '_draw_vendor_stand_unrotated',
    '_SHOP_TEMP_SIZE',
    'draw_vendor_stand',
    'draw_vendor',
    'draw_vendor_quest_marker',
]


def _build_vendor_ring_positions(center_x: float, fire_y: float, count: int) -> List[Vector2]:
    if count <= 0:
        return []
    ring_radius = max(260.0, 160.0 + (count * 55.0) / math.tau)
    start_angle = -math.pi / 2
    positions: List[Vector2] = []
    for idx in range(count):
        angle = (idx / count) * math.tau + start_angle
        vx = center_x + math.cos(angle) * ring_radius
        vy = fire_y + math.sin(angle) * ring_radius
        positions.append(Vector2(vx, vy))
    return positions


def _build_vendor_scatter_positions(
    count: int,
    center_x: float,
    walk_bounds: pygame.Rect,
    obstacles: List[pygame.Rect],
) -> List[Vector2]:
    if count <= 0:
        return []

    # Scatter crowd NPCs across the town — use several plazas spread around
    # the expanded world so NPCs appear in different districts.
    nw_plaza = pygame.Rect(center_x - 4000, HORIZON_Y + 600, 1200, 600)
    ne_plaza = pygame.Rect(center_x + 1500, HORIZON_Y + 600, 1200, 600)
    center_plaza = pygame.Rect(center_x - 600, HORIZON_Y + 1600, 1200, 1000)
    sw_plaza = pygame.Rect(center_x - 3600, HORIZON_Y + 3800, 1200, 600)
    se_plaza = pygame.Rect(center_x + 2500, HORIZON_Y + 3800, 1200, 600)
    south_plaza = pygame.Rect(center_x - 2000, HORIZON_Y + 5000, 4000, 600)
    plazas = [nw_plaza, ne_plaza, center_plaza, sw_plaza, se_plaza, south_plaza]

    rng = random.Random(4317)
    min_dist = 130.0
    margin = 90

    if count <= len(plazas):
        targets = [1 if i < count else 0 for i in range(len(plazas))]
    else:
        weights = [0.38, 0.38, 0.24]
        targets = [int(round(count * w)) for w in weights]
        while sum(targets) < count:
            targets[targets.index(max(targets))] += 1
        while sum(targets) > count:
            targets[targets.index(max(targets))] -= 1

    positions: List[Vector2] = []

    def try_add(pos: Vector2) -> bool:
        if not walk_bounds.collidepoint(pos.x, pos.y):
            return False
        for existing in positions:
            if existing.distance_to(pos) < min_dist:
                return False
        positions.append(pos)
        return True

    for plaza, target in zip(plazas, targets):
        attempts = 0
        while target > 0 and attempts < 240:
            attempts += 1
            px = rng.uniform(plaza.left + margin, plaza.right - margin)
            py = rng.uniform(plaza.top + margin, plaza.bottom - margin)
            p = nearest_walkable(Vector2(px, py), walk_bounds, obstacles, VENDOR_COLLISION_RADIUS)
            if try_add(p):
                target -= 1

    # If any remain, sprinkle around plazas with extra jitter.
    while len(positions) < count:
        plaza = rng.choice(plazas)
        px = rng.uniform(plaza.left + 60, plaza.right - 60)
        py = rng.uniform(plaza.top + 60, plaza.bottom - 60)
        p = nearest_walkable(Vector2(px, py), walk_bounds, obstacles, VENDOR_COLLISION_RADIUS)
        if try_add(p):
            continue
        if len(positions) >= count:
            break

    # Final fallback: keep them inside bounds even if clustered.
    while len(positions) < count:
        px = rng.uniform(walk_bounds.left + 80, walk_bounds.right - 80)
        py = rng.uniform(walk_bounds.top + 120, walk_bounds.bottom - 80)
        positions.append(nearest_walkable(Vector2(px, py), walk_bounds, obstacles, VENDOR_COLLISION_RADIUS))

    return positions


def build_vendors(
    archetypes: List[Dict[str, Union[pygame.Surface, str]]],
    walk_bounds: pygame.Rect,
    obstacles: List[pygame.Rect],
) -> List[Dict[str, object]]:
    if not archetypes:
        return []

    center_x = walk_bounds.centerx
    fire_y = HORIZON_Y + 480

    templates = [
        {
            "role": "Blacksmith",
            "job": "Forging weapons and armour at the market anvil",
            "lines": [
                "Hammers and nails keep half this town standing.",
                "I sharpen blades for the guards on the bridge.",
                "Bring clean iron and I can rework almost anything.",
            ],
        },
        {
            "role": "Alchemist",
            "job": "Brewing potions and elixirs for adventurers",
            "lines": [
                "Every flask is measured twice before it leaves my table.",
                "A good antidote is worth more than any blade.",
                "The forest hides rare reagents — bring them and I'll reward you.",
            ],
        },
        {
            "role": "Tailor",
            "job": "Stitching cloaks and garments for the trade district",
            "lines": [
                "Strong seams matter more than flashy dye.",
                "Tailors come to me before they touch needle to cloth.",
                "Wool for cold nights, linen for the road — I stock both.",
            ],
        },
        {
            "role": "Leatherworker",
            "job": "Crafting leather armour and goods for travelers",
            "lines": [
                "Boot straps and tack don't stitch themselves.",
                "I cure hides in the lower quarter where wind runs dry.",
                "A good leather jerkin can save your life in winter rain.",
            ],
        },
    ]
    # First four names are for the named craft vendors; the rest fill the townsfolk pool.
    all_npc_names = [
        "Aldric", "Marta", "Bran", "Iris",
        "Oswin", "Celia", "Dorin", "Vesna",
        "Halvard", "Lenna", "Cormac", "Syla",
        "Torveld", "Pira", "Edwyn", "Dagna",
        "Rowan", "Thessaly", "Ferris", "Ilara",
        "Gareth", "Nola", "Emmet", "Sabine",
    ]

    template_count = min(len(templates), len(archetypes))
    participants: List[Dict[str, object]] = []

    for idx in range(template_count):
        template = templates[idx]
        arche = archetypes[idx]
        proper_name = all_npc_names[idx % len(all_npc_names)]
        role = template["role"]
        lines = list(template["lines"])
        participants.append(
            {
                "name": f"{proper_name} the {role}",
                "role": role,
                "job": template["job"],
                "sprite": arche["sprite"],
                "sprite_left": arche["sprite_left"],
                "lines": lines,
                "line": lines[0],
                "idle_time": idx * 1.17,
            }
        )

    crowd_roles = ["Merchant", "Baker", "Guard", "Herbalist", "Sailor", "Miller", "Tanner", "Cooper"]
    crowd_lines = [
        "The fire keeps the square alive after dusk.",
        "Best place in town to hear every rumor before dawn.",
        "We gather here when the market slows and the lamps come up.",
    ]
    for idx, arche in enumerate(archetypes[template_count:]):
        name_idx = template_count + idx
        proper_name = all_npc_names[name_idx % len(all_npc_names)]
        crowd_role = crowd_roles[idx % len(crowd_roles)]
        participants.append(
            {
                "name": f"{proper_name} the {crowd_role}",
                "role": crowd_role,
                "job": "Warming by the market fire",
                "sprite": arche["sprite"],
                "sprite_left": arche["sprite_left"],
                "lines": list(crowd_lines),
                "line": crowd_lines[0],
                "idle_time": (template_count + idx) * 0.91,
            }
        )

    vendors: List[Dict[str, object]] = []
    participant_count = len(participants)
    if participant_count <= 0:
        return vendors

    ring_positions = _build_vendor_ring_positions(center_x, fire_y, participant_count)
    scatter_positions = _build_vendor_scatter_positions(participant_count, center_x, walk_bounds, obstacles)
    use_positions = scatter_positions if VENDOR_LAYOUT_MODE == "scatter" else ring_positions

    blacksmith_shop_anchor = Vector2(
        center_x + float(BLACKSMITH_SHOP_ANCHOR_OFFSET[0]),
        HORIZON_Y + float(BLACKSMITH_SHOP_ANCHOR_OFFSET[1]),
    )
    tailor_shop_anchor = Vector2(
        center_x + float(TAILOR_SHOP_ANCHOR_OFFSET[0]),
        HORIZON_Y + float(TAILOR_SHOP_ANCHOR_OFFSET[1]),
    )
    alchemist_shop_anchor = Vector2(
        center_x + float(ALCHEMIST_SHOP_ANCHOR_OFFSET[0]),
        HORIZON_Y + float(ALCHEMIST_SHOP_ANCHOR_OFFSET[1]),
    )
    sailor_shop_anchor = Vector2(
        center_x + float(SAILOR_SHOP_ANCHOR_OFFSET[0]),
        HORIZON_Y + float(SAILOR_SHOP_ANCHOR_OFFSET[1]),
    )
    baker_shop_anchor = Vector2(
        center_x + float(BAKER_SHOP_ANCHOR_OFFSET[0]),
        HORIZON_Y + float(BAKER_SHOP_ANCHOR_OFFSET[1]),
    )
    merchant_shop_anchor = Vector2(
        center_x + float(MERCHANT_SHOP_ANCHOR_OFFSET[0]),
        HORIZON_Y + float(MERCHANT_SHOP_ANCHOR_OFFSET[1]),
    )
    herbalist_shop_anchor = Vector2(
        center_x + float(HERBALIST_SHOP_ANCHOR_OFFSET[0]),
        HORIZON_Y + float(HERBALIST_SHOP_ANCHOR_OFFSET[1]),
    )
    cooper_shop_anchor = Vector2(
        center_x + float(COOPER_SHOP_ANCHOR_OFFSET[0]),
        HORIZON_Y + float(COOPER_SHOP_ANCHOR_OFFSET[1]),
    )
    miller_shop_anchor = Vector2(
        center_x + float(MILLER_SHOP_ANCHOR_OFFSET[0]),
        HORIZON_Y + float(MILLER_SHOP_ANCHOR_OFFSET[1]),
    )
    guard_shop_anchor = Vector2(
        center_x + float(GUARD_SHOP_ANCHOR_OFFSET[0]),
        HORIZON_Y + float(GUARD_SHOP_ANCHOR_OFFSET[1]),
    )
    tanner_shop_anchor = Vector2(
        center_x + float(TANNER_SHOP_ANCHOR_OFFSET[0]),
        HORIZON_Y + float(TANNER_SHOP_ANCHOR_OFFSET[1]),
    )
    leatherworker_shop_anchor = Vector2(
        center_x + float(LEATHERWORKER_SHOP_ANCHOR_OFFSET[0]),
        HORIZON_Y + float(LEATHERWORKER_SHOP_ANCHOR_OFFSET[1]),
    )

    # Map role keys to their pre-computed shop anchors.
    _shop_anchor_map: Dict[str, Vector2] = {
        "blacksmith": blacksmith_shop_anchor,
        "tailor": tailor_shop_anchor,
        "alchemist": alchemist_shop_anchor,
        "sailor": sailor_shop_anchor,
        "baker": baker_shop_anchor,
        "merchant": merchant_shop_anchor,
        "herbalist": herbalist_shop_anchor,
        "cooper": cooper_shop_anchor,
        "miller": miller_shop_anchor,
        "guard": guard_shop_anchor,
        "tanner": tanner_shop_anchor,
        "leatherworker": leatherworker_shop_anchor,
    }

    for idx, entry in enumerate(participants):
        role = str(entry["role"])
        role_key = role.strip().lower()

        # Resolve shop position from the anchor map, or derive one.
        if role_key in _shop_anchor_map:
            shop_pos = Vector2(_shop_anchor_map[role_key])
        else:
            fallback = use_positions[idx] if idx < len(use_positions) else Vector2(center_x, fire_y)
            facing_tmp = 1 if fallback.x < center_x else -1
            shop_pos = Vector2(find_vendor_shop_pos(role, fallback, facing_tmp, walk_bounds, obstacles))

        # Build patrol path in front of the shop.
        patrol_points = build_shop_patrol_points(shop_pos, walk_bounds, obstacles)
        patrol_speed = 28.0

        # Place the vendor at the first patrol point (directly in front of shop).
        pos = Vector2(patrol_points[0])
        backup_pos = Vector2(pos)
        facing = 1 if pos.x < shop_pos.x else -1
        name = str(entry["name"])
        stand_seed = sum(ord(ch) for ch in name) % 10000
        # Build procedural idle animation from the static sprite.
        _sprite_r = entry["sprite"]
        _idle_frames = build_sprite_idle_cycle(_sprite_r, frame_count=4) if isinstance(_sprite_r, pygame.Surface) else None
        vendors.append(
            {
                "name": name,
                "role": role,
                "job": str(entry["job"]),
                "pos": Vector2(pos),
                "backup_pos": Vector2(backup_pos),
                "shop_pos": shop_pos,
                "facing": facing,
                "home_facing": facing,
                "idle_time": float(entry["idle_time"]),
                "sprite": entry["sprite"],
                "sprite_left": entry["sprite_left"],
                "wait": 0.0,
                "lines": list(entry["lines"]),
                "line": str(entry["line"]),
                "anim_frames": _idle_frames,
                "anim_timer": 0.0,
                "patrol_moving": False,
                "stand_seed": stand_seed,
                "patrol_points": patrol_points,
                "patrol_idx": 0,
                "patrol_speed": patrol_speed,
                "patrol_wait": 0.0,
            }
        )

    return vendors


def relocate_blacksmith_shop_to(
    vendors: List[Dict[str, object]],
    desired_pos: Vector2,
    walk_bounds: pygame.Rect,
    obstacles: List[pygame.Rect],
) -> None:
    if not vendors:
        return
    for vendor in vendors:
        role = str(vendor.get("role", "")).strip().lower()
        if role != "blacksmith":
            continue
        desired = Vector2(desired_pos)
        if is_walkable(desired, walk_bounds, obstacles, VENDOR_SHOP_COLLISION_RADIUS):
            shop_pos = Vector2(desired)
        else:
            shop_pos = nearest_walkable(desired, walk_bounds, obstacles, VENDOR_SHOP_COLLISION_RADIUS)
        vendor["shop_pos"] = Vector2(shop_pos)
        patrol_pts = build_blacksmith_patrol_points(shop_pos, walk_bounds, obstacles)
        vendor["patrol_points"] = patrol_pts
        vendor["patrol_idx"] = 0
        vendor["patrol_speed"] = float(vendor.get("patrol_speed", 28.0)) or 28.0
        vendor_pos = Vector2(patrol_pts[0])
        vendor["pos"] = Vector2(vendor_pos)
        vendor["backup_pos"] = Vector2(vendor_pos)
        facing = 1 if vendor_pos.x < shop_pos.x else -1
        vendor["facing"] = facing
        vendor["home_facing"] = facing
        break


def get_blacksmith_shop_pos(vendors: List[Dict[str, object]]) -> Optional[Vector2]:
    for vendor in vendors:
        if str(vendor.get("role", "")).strip().lower() != "blacksmith":
            continue
        shop_pos = vendor.get("shop_pos")
        if isinstance(shop_pos, Vector2):
            return Vector2(shop_pos)
    return None


def keep_player_out_of_blacksmith_shop(
    player_pos: Vector2,
    vendors: List[Dict[str, object]],
    walk_bounds: pygame.Rect,
    obstacles: List[pygame.Rect],
    default_spawn: Optional[Vector2] = None,
) -> Vector2:
    shop_pos = get_blacksmith_shop_pos(vendors)
    if not isinstance(shop_pos, Vector2):
        return player_pos
    shop_rects = blacksmith_shop_collision_rects(shop_pos)
    if not any(rect.collidepoint(int(player_pos.x), int(player_pos.y)) for rect in shop_rects):
        return player_pos
    offsets = [
        Vector2(0, 130),
        Vector2(0, 170),
        Vector2(0, 210),
        Vector2(90, 140),
        Vector2(-90, 140),
        Vector2(140, 90),
        Vector2(-140, 90),
        Vector2(160, 170),
        Vector2(-160, 170),
    ]
    blockers = obstacles + shop_rects
    for off in offsets:
        cand = shop_pos + off
        if is_walkable(cand, walk_bounds, blockers, PLAYER_COLLISION_RADIUS):
            return Vector2(cand)
        snapped = nearest_walkable(cand, walk_bounds, blockers, PLAYER_COLLISION_RADIUS)
        if is_walkable(snapped, walk_bounds, blockers, PLAYER_COLLISION_RADIUS):
            return Vector2(snapped)
    safe_target = Vector2(shop_pos.x, shop_pos.y + 200)
    safe = nearest_walkable(safe_target, walk_bounds, blockers, PLAYER_COLLISION_RADIUS)
    if is_walkable(safe, walk_bounds, blockers, PLAYER_COLLISION_RADIUS):
        return Vector2(safe)
    # If still no valid position found, use default spawn or original position
    if default_spawn is not None and is_walkable(default_spawn, walk_bounds, blockers, PLAYER_COLLISION_RADIUS):
        return Vector2(default_spawn)
    return player_pos


def blacksmith_shop_anchor_from_lamppost(walk_bounds: pygame.Rect) -> Vector2:
    center_x = walk_bounds.centerx
    return Vector2(float(center_x + BLACKSMITH_SHOP_ANCHOR_OFFSET[0]),
                   float(HORIZON_Y + BLACKSMITH_SHOP_ANCHOR_OFFSET[1]))


def build_city_population(
    guard_archetypes: List[Dict[str, Union[pygame.Surface, str]]],
    citizen_archetypes: List[Dict[str, Union[pygame.Surface, str]]],
    walk_bounds: pygame.Rect,
    obstacles: List[pygame.Rect],
) -> List[Dict[str, object]]:
    population: List[Dict[str, object]] = []
    center_x = walk_bounds.centerx
    rng = random.Random(999)

    # 2. Citizens (Wandering)
    citizen_zones = [
        # Trade District
        pygame.Rect(center_x - 2800, HORIZON_Y + 300, 1200, 800),
        # Old Town
        pygame.Rect(center_x + 1600, HORIZON_Y + 300, 1200, 800),
        # Lower City
        pygame.Rect(center_x - 1000, HORIZON_Y + 1600, 2000, 600),
    ]

    for _ in range(20):
        if not citizen_archetypes: break
        zone = rng.choice(citizen_zones)
        cx = rng.randint(zone.left, zone.right)
        cy = rng.randint(zone.top, zone.bottom)
        pos = nearest_walkable(Vector2(cx, cy), walk_bounds, obstacles)
        arche = rng.choice(citizen_archetypes)
        population.append({
            "name": "Citizen",
            "role": "Citizen",
            "job": "Resident of Sangeroasa",
            "pos": pos,
            "facing": 1 if rng.random() > 0.5 else -1,
            "home_facing": 1,
            "idle_time": rng.random() * 10.0,
            "sprite": arche["sprite"],
            "sprite_left": arche["sprite_left"],
            "wait": 0.0,
            "lines": ["Good day.", "Busy, busy...", "The mist is thick today.", "Have you seen the cathedral?"],
            "line": "Good day.",
        })

    return population


def update_vendors(
    vendors: List[Dict[str, object]],
    dt: float,
    _walk_bounds: pygame.Rect,
    _obstacles: List[pygame.Rect],
    interacting_idx: Optional[int] = None,
) -> None:
    """Drive vendor idle animation and optional patrol paths."""
    for idx, vendor in enumerate(vendors):
        talking_visual = interacting_idx is not None and idx == interacting_idx
        is_patrolling = False

        # Tick interaction wait-timer (used after player clicks vendor)
        wait = float(vendor.get("wait", 0.0))
        if wait > 0.0:
            vendor["wait"] = max(0.0, wait - dt)

        # Advance idle-animation clock
        idle_time = float(vendor.get("idle_time", 0.0)) + dt
        vendor["idle_time"] = idle_time
        vendor["anim_timer"] = float(vendor.get("anim_timer", 0.0)) + dt

        # Patrol around shop perimeter if configured.
        patrol_points = vendor.get("patrol_points")
        try:
            patrol_wait = float(vendor.get("patrol_wait", 0.0))
        except (TypeError, ValueError):
            patrol_wait = 0.0
        if (
            not talking_visual
            and isinstance(patrol_points, list)
            and len(patrol_points) >= 2
            and float(vendor.get("patrol_speed", 0.0)) > 0.0
        ):
            # Count down idle pause at the current waypoint.
            if patrol_wait > 0.0:
                vendor["patrol_wait"] = patrol_wait - dt
            else:
                try:
                    cur_pos = vendor.get("pos")
                    if isinstance(cur_pos, Vector2):
                        p_idx = int(vendor.get("patrol_idx", 0)) % len(patrol_points)
                        target = Vector2(patrol_points[p_idx])
                        to = target - cur_pos
                        dist = to.length()
                        if dist < 6.0:
                            # Pick a random different waypoint and pause 1.5–4 s.
                            others = [i for i in range(len(patrol_points)) if i != p_idx]
                            vendor["patrol_idx"] = random.choice(others) if others else (p_idx + 1) % len(patrol_points)
                            vendor["patrol_wait"] = 1.5 + random.random() * 2.5
                        elif dist > 0.01:
                            # Guard against normalize() on near-zero vector.
                            speed = float(vendor.get("patrol_speed", 24.0))
                            step = speed * dt
                            direction = to.normalize()
                            new_pos = move_with_collision(cur_pos, cur_pos + direction * step, step, _walk_bounds, _obstacles, VENDOR_COLLISION_RADIUS)
                            vendor["pos"] = new_pos
                            vendor["facing"] = 1 if direction.x >= 0 else -1
                            is_patrolling = True
                except (TypeError, ValueError, ZeroDivisionError):
                    pass

        vendor["patrol_moving"] = is_patrolling

        # Periodic look-around: every 7 s, face the other way for 1.4 s, then back.
        # We derive this purely from idle_time so it's deterministic and stagger-free.
        if talking_visual or is_patrolling:
            continue  # keep facing fixed while player is talking or patrolling
        home_facing = int(vendor.get("home_facing", 1))
        phase = idle_time % 7.0
        vendor["facing"] = -home_facing if phase > 5.6 else home_facing






def draw_player(
    surface: pygame.Surface,
    position: Vector2,
    facing: int,
    sprite_right: pygame.Surface,
    sprite_left: pygame.Surface,
    is_moving: bool = False,
    anim_timer: float = 0.0,
    anim_frames: Optional[Dict[str, Dict[str, List[pygame.Surface]]]] = None,
    anim_state: str = "",
    anim_direction: str = "down",
    anim_fps: Optional[Dict[str, float]] = None,
    equip_tint_right: Optional[pygame.Surface] = None,
    equip_tint_left: Optional[pygame.Surface] = None,
    hit_flash_strength: float = 0.0,
) -> None:
    x = int(position.x)
    y = int(position.y)
    sprite = get_facing_sprite(facing, sprite_right, sprite_left)
    state_key = str(anim_state or ("walk" if is_moving else "idle")).strip().lower()
    direction_key = str(anim_direction or ("right" if facing >= 0 else "left")).strip().lower()
    using_sheet_animation = False

    if anim_frames:
        fps = 8.0
        if isinstance(anim_fps, dict):
            try:
                fps = float(anim_fps.get(state_key, anim_fps.get("idle", fps)))
            except (TypeError, ValueError):
                fps = 8.0
        animated_sprite = get_directional_anim_frame(
            anim_frames,
            state_key,
            direction_key,
            anim_timer,
            fps=fps,
            loop=state_key not in WARRIOR_NON_LOOPING_STATES,
        )
        if isinstance(animated_sprite, pygame.Surface):
            sprite = animated_sprite
            using_sheet_animation = True

    t = max(0.0, float(anim_timer))
    walk_like = state_key in ("walk", "walk_attack")
    run_like = state_key in ("run", "run_attack")
    attack_like = state_key in ("attack", "walk_attack", "run_attack")
    hurt_like = state_key == "hurt"
    x_off = 0
    y_off = 0
    face_sign = 1 if facing >= 0 else -1

    if run_like:
        y_off -= int(abs(math.sin(t * 11.0)) * 4.0)
        x_off += int(math.sin(t * 7.2) * 1.6)
    elif walk_like or is_moving:
        y_off -= int(abs(math.sin(t * 8.0)) * 2.2)
        x_off += int(math.sin(t * 4.8) * 1.2)
    else:
        y_off -= int(math.sin(t * 2.2 + x * 0.012) * 1.2)
        x_off += int(math.sin(t * 1.6 + y * 0.01) * 0.8)

    if attack_like:
        attack_duration = 0.20 if run_like else 0.24
        attack_progress = clamp(t / max(0.05, attack_duration), 0.0, 1.0)
        lunge = math.sin(attack_progress * math.pi)
        x_off += int(face_sign * (6.0 + (2.0 if run_like else 0.0)) * lunge)
        y_off -= int(2.2 * lunge)
    elif hurt_like:
        hurt_progress = clamp(t / 0.18, 0.0, 1.0)
        recoil = 1.0 - hurt_progress
        x_off -= int(face_sign * 8.0 * recoil)
        y_off += int(2.2 * recoil)

    if not using_sheet_animation:
        squash = 1.0
        if run_like:
            squash += math.sin(t * 13.0) * 0.05
        elif walk_like:
            squash += math.sin(t * 10.0) * 0.03
        elif attack_like:
            squash += math.sin(min(math.pi, t * 9.0)) * 0.04
        if abs(squash - 1.0) > 0.01:
            sw = max(8, int(sprite.get_width() * (1.0 - (squash - 1.0) * 0.35)))
            sh = max(8, int(sprite.get_height() * squash))
            sprite = pygame.transform.smoothscale(sprite, (sw, sh))

    shadow_w_scale = 0.44 + (0.06 if run_like else (0.03 if walk_like else 0.0))
    shadow_w = max(34, int(sprite.get_width() * shadow_w_scale))
    shadow_h = 14 + (2 if run_like else (1 if walk_like else 0))
    shadow_x = x + int(x_off * 0.25) - shadow_w // 2
    pygame.draw.ellipse(surface, (12, 12, 14), (shadow_x, y - 3, shadow_w, shadow_h))
    pygame.draw.ellipse(surface, (18, 18, 20), (shadow_x + 4, y + 1, max(8, shadow_w - 8), max(5, shadow_h - 7)))

    flash_strength = clamp(float(hit_flash_strength), 0.0, 1.0)
    if flash_strength > 0.0:
        _flash = pygame.Surface(sprite.get_size(), pygame.SRCALPHA)
        _flash_alpha = int(80 + 150 * flash_strength)
        _flash.fill((236, 60, 48, _flash_alpha))
        _flashed = sprite.copy()
        _flashed.blit(_flash, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
        sprite = _flashed

    rect = sprite.get_rect(midbottom=(x + x_off, y + 2 + y_off))
    surface.blit(sprite, rect)

    # Equipment color tint overlay — scales to match current frame size
    _tint = equip_tint_right if facing >= 0 else equip_tint_left
    if isinstance(_tint, pygame.Surface):
        _tw, _th = _tint.get_size()
        if (_tw, _th) != (rect.width, rect.height) and _tw > 0 and _th > 0:
            _tint = pygame.transform.scale(_tint, (rect.width, rect.height))
        surface.blit(_tint, rect.topleft)

    if attack_like:
        swing_len = int(8 + 10 * abs(math.sin(t * 14.0)))
        arc_y = rect.centery - 8
        pygame.draw.line(surface, (236, 208, 140), (rect.centerx, arc_y), (rect.centerx + face_sign * swing_len, arc_y - 4), 1)
    if hurt_like and ((pygame.time.get_ticks() // 45) % 2 == 0):
        flash = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        flash.fill((188, 54, 54, 56))
        surface.blit(flash, rect.topleft, special_flags=pygame.BLEND_RGBA_ADD)




def _shop_offset(facing: int) -> Vector2:
    offset_x = -140 if facing >= 0 else 140
    return Vector2(offset_x, 8)


def vendor_shop_position(role_key: str, vendor_pos: Vector2, facing: int) -> Vector2:
    role = role_key.strip().lower()
    if role == "blacksmith":
        return vendor_pos + Vector2(-220 if facing >= 0 else 220, 12)
    return vendor_pos + _shop_offset(facing)


def find_vendor_shop_pos(
    role_key: str,
    vendor_pos: Vector2,
    facing: int,
    walk_bounds: pygame.Rect,
    obstacles: List[pygame.Rect],
) -> Vector2:
    role = role_key.strip().lower()
    base = vendor_shop_position(role_key, vendor_pos, facing)
    radius = VENDOR_SHOP_COLLISION_RADIUS if role == "blacksmith" else 70.0

    offsets = [
        Vector2(0, 0),
        Vector2(60, 0), Vector2(-60, 0),
        Vector2(0, 60), Vector2(0, -60),
        Vector2(90, 40), Vector2(-90, 40),
        Vector2(90, -40), Vector2(-90, -40),
    ]
    if role == "blacksmith":
        offsets = [
            Vector2(0, 0),
            Vector2(120, 0), Vector2(-120, 0),
            Vector2(0, 80), Vector2(0, -80),
            Vector2(160, 60), Vector2(-160, 60),
            Vector2(160, -60), Vector2(-160, -60),
        ]

    for off in offsets:
        cand = base + off
        if is_walkable(cand, walk_bounds, obstacles, radius):
            return cand

    return nearest_walkable(base, walk_bounds, obstacles, radius)


def build_shop_patrol_points(
    shop_pos: Vector2,
    walk_bounds: pygame.Rect,
    obstacles: List[pygame.Rect],
) -> List[Vector2]:
    """Patrol just in front of the shop — left, center, and right waypoints.

    Always returns at least one point (the shop position itself as a last
    resort) so callers can safely index ``[0]`` without risk of IndexError.
    """
    sx = float(shop_pos.x)
    front_y = float(shop_pos.y) + 96.0
    candidates = [
        Vector2(sx - 120.0, front_y),
        Vector2(sx, front_y),
        Vector2(sx + 120.0, front_y),
    ]
    points: List[Vector2] = []
    for c in candidates:
        try:
            points.append(nearest_walkable(c, walk_bounds, obstacles, VENDOR_COLLISION_RADIUS))
        except (TypeError, ValueError):
            points.append(Vector2(c))
    # Guarantee at least one entry so [0] never fails.
    if not points:
        points.append(Vector2(shop_pos))
    return points


# Keep old name as alias so existing call-sites don't break.
build_blacksmith_patrol_points = build_shop_patrol_points


def blacksmith_shop_collision_rects(shop_pos: Vector2) -> List[pygame.Rect]:
    x = int(shop_pos.x)
    ground = int(shop_pos.y)
    # Block the shop footprint while leaving a strip in front for the vendor.
    main = pygame.Rect(x - 200, ground - 180, 420, 170)
    return [main]

def spell_collision_obstacles(spell_effects: List[Dict[str, object]]) -> List[pygame.Rect]:
    blockers: List[pygame.Rect] = []
    for effect in spell_effects:
        if not isinstance(effect, dict):
            continue
        if str(effect.get("kind", "")) != "pillar":
            continue
        if float(effect.get("life", 0.0)) <= 0.0:
            continue
        pos = effect.get("pos")
        if not isinstance(pos, Vector2):
            continue
        size = max(32.0, float(effect.get("size", 64.0)))
        width = int(size)
        height = max(18, int(size * 0.55))
        blockers.append(pygame.Rect(int(pos.x - width * 0.5), int(pos.y - height * 0.5), width, height))
    return blockers


def _seeded_barrel(surface: pygame.Surface, x: int, y: int, seed: int) -> pygame.Rect:
    state = random.getstate()
    random.seed(seed)
    rect = draw_hd_barrel(surface, x, y)
    random.setstate(state)
    return rect




def _draw_vendor_stand_unrotated(
    surface: pygame.Surface,
    position: Vector2,
    role_key: str,
    ticks: int,
    stand_seed: int = 0,
) -> None:
    role = role_key.strip().lower()
    shop_pos = position
    if role == "blacksmith":
        _draw_blacksmith_shop(surface, shop_pos, ticks, stand_seed)
    elif role == "alchemist":
        _draw_alchemist_shop(surface, shop_pos, ticks, stand_seed)
    elif role == "tailor":
        _draw_tailor_shop(surface, shop_pos, ticks, stand_seed)
    elif role == "leatherworker":
        _draw_leather_shop(surface, shop_pos, ticks, stand_seed)
    elif role == "merchant":
        _draw_merchant_shop(surface, shop_pos, ticks, stand_seed)
    elif role == "baker":
        _draw_baker_shop(surface, shop_pos, ticks, stand_seed)
    elif role == "guard":
        _draw_guard_shop(surface, shop_pos, ticks, stand_seed)
    elif role == "herbalist":
        _draw_herbalist_shop(surface, shop_pos, ticks, stand_seed)
    elif role == "sailor":
        _draw_sailor_shop(surface, shop_pos, ticks, stand_seed)
    elif role == "miller":
        _draw_miller_shop(surface, shop_pos, ticks, stand_seed)
    elif role == "tanner":
        _draw_tanner_shop(surface, shop_pos, ticks, stand_seed)
    elif role == "cooper":
        _draw_cooper_shop(surface, shop_pos, ticks, stand_seed)
    else:
        _draw_merchant_shop(surface, shop_pos, ticks, stand_seed)


_SHOP_TEMP_SIZE = 700  # px – generous buffer for the largest shop (blacksmith ~420×280)


def draw_vendor_stand(
    surface: pygame.Surface,
    position: Vector2,
    role_key: str,
    ticks: int,
    stand_seed: int = 0,
    rotation: float = 0.0,
) -> None:
    rotation = rotation % 360.0
    if abs(rotation) < 0.5:
        _draw_vendor_stand_unrotated(surface, position, role_key, ticks, stand_seed)
        return
    half = _SHOP_TEMP_SIZE // 2
    tmp = pygame.Surface((_SHOP_TEMP_SIZE, _SHOP_TEMP_SIZE), pygame.SRCALPHA)
    _draw_vendor_stand_unrotated(tmp, Vector2(half, half), role_key, ticks, stand_seed)
    rotated = pygame.transform.rotozoom(tmp, -rotation, 1.0)
    rx, ry = rotated.get_size()
    surface.blit(rotated, (int(position.x) - rx // 2, int(position.y) - ry // 2))

def draw_vendor(
    surface: pygame.Surface,
    position: Vector2,
    shop_position: Optional[Vector2],
    role: str,
    facing: int,
    sprite_right: pygame.Surface,
    sprite_left: pygame.Surface,
    idle_time: float = 0.0,
    anim_frames: Optional[Dict[str, Dict[str, List[pygame.Surface]]]] = None,
    stand_seed: int = 0,
    ticks: int = 0,
    draw_stand: bool = True,
    shop_rotation: float = 0.0,
    is_moving: bool = False,
) -> None:
    x = int(position.x)
    role_key = str(role).strip().lower()
    shop_pos = shop_position if isinstance(shop_position, Vector2) else position
    if draw_stand:
        draw_vendor_stand(surface, shop_pos, role_key, ticks, stand_seed, rotation=shop_rotation)
    sprite = get_facing_sprite(facing, sprite_right, sprite_left)
    t = float(idle_time)

    # Use the same sinusoidal motion as the player character.
    x_off = 0
    y_off = 0
    if is_moving:
        # Walk bounce — identical to player walk
        y_off -= int(abs(math.sin(t * 8.0)) * 2.2)
        x_off += int(math.sin(t * 4.8) * 1.2)
    else:
        # Idle breathing — identical to player idle
        y_off -= int(math.sin(t * 2.2 + x * 0.012) * 1.2)
        x_off += int(math.sin(t * 1.6 + int(position.y) * 0.01) * 0.8)

    # Squash-stretch (sprite scale pulse) — matches player
    squash = 1.0
    if is_moving:
        squash += math.sin(t * 10.0) * 0.03
    if abs(squash - 1.0) > 0.01:
        sw = max(8, int(sprite.get_width() * (1.0 - (squash - 1.0) * 0.35)))
        sh = max(8, int(sprite.get_height() * squash))
        sprite = pygame.transform.scale(sprite, (sw, sh))

    y = int(position.y) + y_off
    rect = sprite.get_rect(midbottom=(x + x_off, y + 1))
    surface.blit(sprite, rect)


def draw_vendor_quest_marker(
    surface: pygame.Surface,
    position: Vector2,
    facing: int,
    sprite_right: pygame.Surface,
    sprite_left: pygame.Surface,
    idle_time: float,
    marker: str,
    marker_font: pygame.font.Font,
    ticks: int,
    highlighted: bool = False,
    nameplate_top: Optional[int] = None,
) -> None:
    symbol = str(marker).strip()
    if symbol not in ("!", "?"):
        return

    x = int(position.x)
    y = int(position.y)
    sprite = get_facing_sprite(facing, sprite_right, sprite_left)
    rect = sprite.get_rect(midbottom=(x, y + 1))

    float_y = int(abs(math.sin(ticks * 0.006)) * 2.6)
    cx = rect.centerx
    if nameplate_top is not None:
        cy = nameplate_top - 12 - float_y
    else:
        cy = rect.top - 18 - float_y

    if symbol == "!":
        fill_col = (250, 218, 96)
        ring_col = (166, 132, 66)
        glow_col = (240, 198, 82, 120 if highlighted else 92)
    else:
        fill_col = (166, 224, 248)
        ring_col = (86, 132, 154)
        glow_col = (126, 196, 228, 120 if highlighted else 92)

    glow = pygame.Surface((36, 36), pygame.SRCALPHA)
    pygame.draw.circle(glow, glow_col, (18, 18), 11)
    surface.blit(glow, (cx - 18, cy - 18))

    pygame.draw.circle(surface, (16, 14, 12), (cx, cy), 10)
    pygame.draw.circle(surface, ring_col, (cx, cy), 10, 1)

    text_outline = marker_font.render(symbol, True, (10, 10, 10))
    text_fill = marker_font.render(symbol, True, fill_col)
    tx = cx - text_fill.get_width() // 2
    ty = cy - text_fill.get_height() // 2 - 1
    surface.blit(text_outline, (tx - 1, ty))
    surface.blit(text_outline, (tx + 1, ty))
    surface.blit(text_outline, (tx, ty - 1))
    surface.blit(text_outline, (tx, ty + 1))
    surface.blit(text_fill, (tx, ty))
