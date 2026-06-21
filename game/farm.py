"""game/farm.py — farm animal spawning, wander/separation AI, and live animal rendering."""
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

__all__ = [
    '_random_yard_point',
    'build_farm_animals',
    '_farm_block_push',
    '_farm_path_blocked',
    '_FARM_ANIMAL_RADIUS',
    '_separate_farm_animals',
    'update_farm_animals',
    'draw_farm_animal',
    '_draw_live_chicken',
    '_draw_live_pig',
    '_draw_live_sheep',
]


def _random_yard_point(rng, cx, cy, hw, hh, block=None, margin=20,
                       avoid=None, avoid_r=0.0):
    """Pick a point spread across the whole yard ellipse, avoiding the
    building no-go ellipse `block`. hw/hh are the pen's world-space
    HALF-extents (matching the farm_animal_pens records). If `avoid` is a
    list of Vector2 positions, candidates closer than `avoid_r` to any of
    them are rejected so animals spread out instead of bunching up."""
    rx = max(8, hw - margin)
    ry = max(6, hh - margin)
    spaced_fallback = None
    for _try in range(18):
        # uniform-ish sample within the ellipse via rejection
        u = rng.uniform(-1.0, 1.0)
        v = rng.uniform(-1.0, 1.0)
        if u * u + v * v > 1.0:
            continue
        px = cx + u * rx
        py = cy + v * ry
        if block:
            blocked = False
            for bx, by, brx, bry in block:
                nx = (px - bx) / brx
                ny = (py - by) / bry
                if nx * nx + ny * ny < 1.18:
                    blocked = True
                    break
            if blocked:
                continue
        if avoid and avoid_r > 0.0:
            too_close = False
            for ap in avoid:
                if (px - ap.x) ** 2 + (py - ap.y) ** 2 < avoid_r * avoid_r:
                    too_close = True
                    break
            if too_close:
                # legal yard point, just near a pen-mate — keep as fallback
                if spaced_fallback is None:
                    spaced_fallback = Vector2(px, py)
                continue
        return Vector2(px, py)
    if spaced_fallback is not None:
        return spaced_fallback
    # fallback: somewhere along the open front of the yard
    return Vector2(cx + rng.uniform(-rx * 0.6, rx * 0.6), cy + ry * 0.5)


def build_farm_animals(pens: List[Dict[str, object]]) -> List[Dict[str, object]]:
    """Spawn animated farm animals inside each pen."""
    animals: List[Dict[str, object]] = []
    rng = random.Random(55123)
    _chicken_colors = [
        (238, 228, 208), (182, 124, 62), (144, 92, 46),
        (202, 82, 52), (64, 58, 52), (224, 194, 132), (200, 180, 140),
    ]
    for pen in pens:
        kind = str(pen.get("kind", ""))
        cx = int(pen.get("cx", 0))
        cy = int(pen.get("cy", 0))
        hw = int(pen.get("hw", 100))
        hh = int(pen.get("hh", 80))

        # Building no-go zones (world coords, LIST of ellipses) covering the
        # building's FULL drawn silhouette — walls AND roof. Animals render on
        # top of the baked pen art, so an animal allowed to wander behind a
        # building would be drawn standing on its roof. Offsets match the pen
        # art at 2× scale (see draw_chicken_coop / draw_pig_pen geometry).
        if kind == "pig":
            # Centered shelter hut: wall/mouth mass + roof trapezoid above it.
            block = [(cx, cy - 28, 92, 48), (cx, cy - 64, 96, 44)]
        elif kind == "chicken":
            # Upper-left henhouse: wall/stilt/nesting mass + the shake roof.
            block = [(cx - 52, cy - 45, 132, 82), (cx - 84, cy - 136, 142, 58)]
        elif kind == "sheep":
            block = None
        else:
            block = None
        # Positions already taken in this pen — new spawns keep their distance
        # so the group starts scattered across the yard, not in a clump.
        placed: List[Vector2] = []
        if kind == "chicken":
            count = rng.randint(7, 10)
            # One rooster, spread anywhere in the yard
            rp = _random_yard_point(rng, cx, cy, hw, hh, block, avoid=placed, avoid_r=34.0)
            placed.append(rp)
            animals.append({
                "kind": "rooster", "pen_cx": cx, "pen_cy": cy, "pen_hw": hw, "pen_hh": hh,
                "pos": rp, "target": Vector2(rp),
                "facing": rng.choice([-1, 1]), "color": (170, 52, 28),
                "state": "idle", "timer": rng.uniform(1.0, 4.0),
                "anim_t": rng.uniform(0, 10.0), "size": 1.4,
            })
            for _ in range(count):
                ap = _random_yard_point(rng, cx, cy, hw, hh, block, avoid=placed, avoid_r=30.0)
                placed.append(ap)
                col = rng.choice(_chicken_colors)
                animals.append({
                    "kind": "chicken", "pen_cx": cx, "pen_cy": cy, "pen_hw": hw, "pen_hh": hh,
                    "pos": ap, "target": Vector2(ap),
                    "facing": rng.choice([-1, 1]), "color": col,
                    "state": rng.choice(["idle", "peck", "walk"]),
                    "timer": rng.uniform(0.5, 3.0), "anim_t": rng.uniform(0, 10.0),
                    "size": 1.0,
                })
        elif kind == "pig":
            count = rng.randint(4, 6)
            for _ in range(count):
                ap = _random_yard_point(rng, cx, cy, hw, hh, block, avoid=placed, avoid_r=48.0)
                placed.append(ap)
                pink = rng.randint(0, 30)
                col = (216 + pink, 172 + pink, 148 + pink)
                animals.append({
                    "kind": "pig", "pen_cx": cx, "pen_cy": cy, "pen_hw": hw, "pen_hh": hh,
                    "pos": ap, "target": Vector2(ap),
                    "facing": rng.choice([-1, 1]), "color": col,
                    "state": rng.choice(["idle", "root", "walk", "mud"]),
                    "timer": rng.uniform(1.0, 5.0), "anim_t": rng.uniform(0, 10.0),
                    "size": 1.0 + rng.uniform(-0.1, 0.2),
                })
        elif kind == "sheep":
            count = rng.randint(5, 8)
            for _ in range(count):
                ap = _random_yard_point(rng, cx, cy, hw, hh, block, avoid=placed, avoid_r=42.0)
                placed.append(ap)
                wool_v = 220 + rng.randint(-15, 15)
                col = (wool_v, wool_v - 4, wool_v - 10)
                animals.append({
                    "kind": "sheep", "pen_cx": cx, "pen_cy": cy, "pen_hw": hw, "pen_hh": hh,
                    "pos": ap, "target": Vector2(ap),
                    "facing": rng.choice([-1, 1]), "color": col,
                    "state": rng.choice(["idle", "graze", "walk"]),
                    "timer": rng.uniform(1.0, 5.0), "anim_t": rng.uniform(0, 10.0),
                    "size": 1.0 + rng.uniform(-0.1, 0.15),
                })

        # Tag this pen's animals with the building no-go zones, and re-scatter
        # any that spawned inside one across the yard (not all to one spot).
        if block is not None:
            for a in animals:
                if a.get("pen_cx") != cx or a.get("pen_cy") != cy:
                    continue
                a["block"] = block
                p = a["pos"]
                inside = any(((p.x - bx) / brx) ** 2 + ((p.y - by) / bry) ** 2 < 1.0
                             for bx, by, brx, bry in block)
                if inside:
                    np = _random_yard_point(rng, cx, cy, hw, hh, block,
                                            avoid=placed, avoid_r=30.0)
                    placed.append(np)
                    a["pos"] = np
                    a["target"] = Vector2(np)
    return animals


def _farm_block_push(pos: Vector2, block) -> None:
    """If `pos` is inside any building no-go ellipse [(bx,by,brx,bry), ...],
    push it out to just outside that boundary. Two passes settle points near
    the seam where two ellipses overlap."""
    if not block:
        return
    import math as _m
    for _pass in range(2):
        moved = False
        for bx, by, brx, bry in block:
            dx = (pos.x - bx) / brx
            dy = (pos.y - by) / bry
            d2 = dx * dx + dy * dy
            if d2 < 1.0:
                d = _m.sqrt(d2) if d2 > 1e-6 else 0.0001
                # scale the normalized offset out to the boundary (small margin)
                s = 1.06 / d
                pos.x = bx + dx * brx * s
                pos.y = by + dy * bry * s
                moved = True
        if not moved:
            break


def _farm_path_blocked(p0: Vector2, p1: Vector2, block) -> bool:
    """True if the straight walk from p0 to p1 cuts through a building no-go
    ellipse — used to pick wander targets the animal can reach without being
    shoved around the building mid-walk."""
    if not block:
        return False
    for s in range(1, 7):
        t = s / 7.0
        px = p0.x + (p1.x - p0.x) * t
        py = p0.y + (p1.y - p0.y) * t
        for bx, by, brx, bry in block:
            nx = (px - bx) / brx
            ny = (py - by) / bry
            if nx * nx + ny * ny < 1.0:
                return True
    return False


_FARM_ANIMAL_RADIUS = {"chicken": 9.0, "rooster": 11.0, "pig": 16.0, "sheep": 14.0}


def _separate_farm_animals(animals: List[Dict[str, object]]) -> None:
    """Push overlapping farm animals apart so they don't stack on each other.
    O(n^2) per pen, but pens hold <=12 animals so this is cheap."""
    # Bucket by pen so animals only repel pen-mates (different pens are far apart).
    pens: Dict[Tuple[int, int], list] = {}
    for a in animals:
        pos = a.get("pos")
        if not isinstance(pos, Vector2):
            continue
        key = (int(a.get("pen_cx", 0)), int(a.get("pen_cy", 0)))
        pens.setdefault(key, []).append(a)

    # Two relaxation passes: the second pass settles chains of touching
    # animals that the first pass pushed into each other.
    for _pass in range(2):
        for group in pens.values():
            for i in range(len(group)):
                a = group[i]
                pa = a["pos"]
                ra = _FARM_ANIMAL_RADIUS.get(str(a.get("kind", "")), 12.0)
                for j in range(i + 1, len(group)):
                    b = group[j]
                    pb = b["pos"]
                    rb = _FARM_ANIMAL_RADIUS.get(str(b.get("kind", "")), 12.0)
                    delta = pa - pb
                    d = delta.length()
                    min_d = ra + rb + 3.0   # small breathing gap, never touching
                    if d < min_d:
                        if d < 0.01:
                            # exactly overlapping — nudge apart on a deterministic axis
                            delta = Vector2(1.0 if (i + j) % 2 == 0 else -1.0, 0.5)
                            d = delta.length()
                        push = (min_d - d) * 0.5
                        n = delta / d
                        pa += n * push
                        pb -= n * push


def update_farm_animals(animals: List[Dict[str, object]], dt: float) -> None:
    """Tick farm animal AI — wander, peck, graze, root, idle within pens."""
    for a in animals:
        a["anim_t"] = float(a.get("anim_t", 0)) + dt
        timer = float(a.get("timer", 0)) - dt
        kind = str(a.get("kind", ""))
        pos = a.get("pos")
        if not isinstance(pos, Vector2):
            continue

        pen_cx = int(a.get("pen_cx", 0))
        pen_cy = int(a.get("pen_cy", 0))
        pen_hw = int(a.get("pen_hw", 100))
        pen_hh = int(a.get("pen_hh", 80))

        state = str(a.get("state", "idle"))
        if state == "walk":
            target = a.get("target")
            if isinstance(target, Vector2):
                to = target - pos
                dist = to.length()
                if dist < 4.0:
                    a["state"] = random.choice(["idle", "idle", "peck"] if kind in ("chicken", "rooster") else
                                                ["idle", "idle", "graze"] if kind == "sheep" else
                                                ["idle", "idle", "root", "mud"])
                    a["timer"] = 1.5 + random.random() * 4.0
                else:
                    speed = 24.0 if kind in ("chicken", "rooster") else 14.0 if kind == "pig" else 16.0
                    step = min(dist, speed * dt)
                    direction = to.normalize()
                    new_pos = pos + direction * step
                    # (Final ellipse clamp at the end of the tick keeps animals in
                    # the yard; just keep them off the building here.)
                    _farm_block_push(new_pos, a.get("block"))
                    a["pos"] = new_pos
                    a["facing"] = 1 if direction.x >= 0 else -1
        elif timer <= 0:
            # Pick new behavior
            roll = random.random()
            if roll < 0.45:
                # Walk to a new spot spread across the whole yard, away from
                # both the building and the current pen-mates, so the flock
                # wanders and spreads out instead of bunching up.
                mates = [b.get("pos") for b in animals
                         if b is not a and isinstance(b.get("pos"), Vector2)
                         and int(b.get("pen_cx", 0)) == pen_cx
                         and int(b.get("pen_cy", 0)) == pen_cy]
                rad = _FARM_ANIMAL_RADIUS.get(kind, 12.0)
                blk = a.get("block")
                cand = pos
                for _try in range(4):
                    cand = _random_yard_point(random, pen_cx, pen_cy,
                                              pen_hw, pen_hh, blk,
                                              avoid=mates, avoid_r=rad * 2.0 + 12.0)
                    # walk around the building, not through it
                    if not _farm_path_blocked(pos, cand, blk):
                        break
                a["target"] = cand
                a["state"] = "walk"
                a["timer"] = 8.0
            elif roll < 0.7:
                a["state"] = "peck" if kind in ("chicken", "rooster") else "graze" if kind == "sheep" else "root"
                a["timer"] = 1.0 + random.random() * 2.5
            elif roll < 0.85 and kind == "pig":
                a["state"] = "mud"
                a["timer"] = 2.0 + random.random() * 3.0
            else:
                a["state"] = "idle"
                a["timer"] = 1.5 + random.random() * 3.0
                if random.random() > 0.6:
                    a["facing"] = -int(a.get("facing", 1))
        else:
            a["timer"] = timer

    # Keep animals from stacking, then re-clamp inside their pen.
    _separate_farm_animals(animals)
    for a in animals:
        pos = a.get("pos")
        if not isinstance(pos, Vector2):
            continue
        pcx = int(a.get("pen_cx", 0))
        pcy = int(a.get("pen_cy", 0))
        phw = int(a.get("pen_hw", 100))
        phh = int(a.get("pen_hh", 80))
        # Clamp inside the yard ellipse (full extent, with a margin) so animals
        # can use the whole pen. phw/phh are world-space HALF-extents — the old
        # `phw // 2` here halved them again and penned everyone into a tiny
        # centre patch.
        rx = max(8, phw - 20); ry = max(6, phh - 16)
        ddx = (pos.x - pcx) / rx; ddy = (pos.y - pcy) / ry
        d2 = ddx * ddx + ddy * ddy
        if d2 > 1.0:
            import math as _m
            s = 1.0 / _m.sqrt(d2)
            pos.x = pcx + ddx * rx * s
            pos.y = pcy + ddy * ry * s
        _farm_block_push(pos, a.get("block"))   # keep off the building after separation


def draw_farm_animal(
    surface: pygame.Surface, animal: Dict[str, object],
    cam_x: int, cam_y: int, ticks: int,
) -> None:
    """Draw a single animated farm animal on screen."""
    pos = animal.get("pos")
    if not isinstance(pos, Vector2):
        return
    kind = str(animal.get("kind", ""))
    sx = int(pos.x) - cam_x
    sy = int(pos.y) - cam_y
    facing = int(animal.get("facing", 1))
    col = animal.get("color", (200, 200, 200))
    state = str(animal.get("state", "idle"))
    anim_t = float(animal.get("anim_t", 0))
    sz = float(animal.get("size", 1.0))

    if kind in ("chicken", "rooster"):
        _draw_live_chicken(surface, sx, sy, facing, col, state, anim_t, sz, kind == "rooster")
    elif kind == "pig":
        _draw_live_pig(surface, sx, sy, facing, col, state, anim_t, sz)
    elif kind == "sheep":
        _draw_live_sheep(surface, sx, sy, facing, col, state, anim_t, sz)


def _draw_live_chicken(
    surface: pygame.Surface, sx: int, sy: int, facing: int,
    col: tuple, state: str, t: float, sz: float, is_rooster: bool,
) -> None:
    """Animated chicken/rooster, lit from the upper-left like the pen art:
    teardrop body with breast highlight, scalloped folded wing, fanned tail
    (glossy arched sickle plumes + golden saddle on the rooster), jointed
    stepping legs with lifted feet, scalloped comb, two-lobe wattle, two-tone
    beak that opens at the peck impact and kicks up a puff of dust."""
    import math as _m
    f = facing
    s = sz

    def _sh_col(c, d):
        return (max(0, c[0] - d), max(0, c[1] - d), max(0, c[2] - d))

    def _hi_col(c, d):
        return (min(255, c[0] + d), min(255, c[1] + d), min(255, c[2] + d))

    shade = _sh_col(col, 28)
    deep = _sh_col(col, 54)
    light = _hi_col(col, 26)
    rim = _hi_col(col, 46)

    # ── Animation drivers ────────────────────────────────────────────────────
    walk = state == "walk"
    leg_phase = t * 11.0
    walk_bob = abs(_m.sin(leg_phase)) * 1.7 * s if walk else 0.0
    idle_bob = _m.sin(t * 2.4) * 0.6 * s
    pk = max(0.0, _m.sin(t * 5.0)) if state == "peck" else 0.0   # 0 up → 1 at ground
    head_turn = _m.sin(t * 0.9) if state == "idle" else 0.0      # slow look-around
    by = int(sy - 1.5 * s - walk_bob - idle_bob + pk * 1.2 * s)
    ground_y = sy + int(4.5 * s)

    bw = int(9 * s) if is_rooster else int(8 * s)
    bh = int(11 * s) if is_rooster else int(10 * s)

    # ── Ground shadow (sun upper-left → nudged right) ────────────────────────
    shw, shh = int(24 * s), int(9 * s)
    _sh = pygame.Surface((shw, shh), pygame.SRCALPHA)
    pygame.draw.ellipse(_sh, (14, 10, 7, 36), (0, 0, shw, shh))
    pygame.draw.ellipse(_sh, (14, 10, 7, 52),
                        (int(3 * s), int(2 * s), shw - int(6 * s), shh - int(4 * s)))
    surface.blit(_sh, (sx - shw // 2 + int(1 * s), ground_y - shh // 2 + int(1 * s)))

    # ── Legs: hip → hock → foot, with a real stepping foot-lift ─────────────
    leg_col = (212, 170, 56)
    leg_dk = (140, 102, 28)
    hip_y = by + int(2.5 * s)
    for li, hip_dx in enumerate((-2.5, 2.0)):
        ph = leg_phase + li * _m.pi
        swing = _m.sin(ph) * 3.0 * s if walk else 0.0
        lift = max(0.0, _m.sin(ph + _m.pi * 0.5)) * 2.2 * s if walk else 0.0
        hx0 = sx + int(hip_dx * s)
        fx0 = hx0 + int(f * swing)
        fy0 = int(ground_y - lift)
        mx0 = (hx0 + fx0) // 2 - f * int(1.2 * s)         # hock kicks back
        my0 = (hip_y + fy0) // 2
        for c_l, w_ in ((leg_dk, max(2, int(2 * s))), (leg_col, max(1, int(1.2 * s)))):
            pygame.draw.line(surface, c_l, (hx0, hip_y), (mx0, my0), w_)
            pygame.draw.line(surface, c_l, (mx0, my0), (fx0, fy0), w_)
        for toe in (-2.6, 0.0, 2.6):                       # three toes + rear spur
            pygame.draw.line(surface, leg_col, (fx0, fy0),
                             (fx0 + f * int((3 + toe) * 0.8 * s), fy0 + int(2.2 * s)), 1)
        pygame.draw.line(surface, leg_dk, (fx0, fy0),
                         (fx0 - f * int(2 * s), fy0 + int(1.2 * s)), 1)

    # ── Tail ─────────────────────────────────────────────────────────────────
    tail_x = sx - f * int(6.5 * s)
    tail_y = by - int(3 * s) - int(pk * 2 * s)             # tail tips up while pecking
    if is_rooster:
        # golden saddle feathers hiding the join
        pygame.draw.ellipse(surface, (188, 110, 36),
                            (tail_x - int(4 * s), tail_y - int(2 * s), int(9 * s), int(7 * s)))
        pygame.draw.ellipse(surface, (224, 150, 56),
                            (tail_x - int(3 * s), tail_y - int(2 * s), int(6 * s), int(4 * s)))
        # arched glossy sickle plumes, dark → bright green, one cool glint
        sickle = [(14, 44, 30), (22, 70, 44), (34, 98, 58), (52, 128, 74)]
        specs = [(1.6, 7.0), (1.15, 11.0), (0.65, 15.0), (0.25, 18.0)]
        glint_pts = None
        for scol, (lean, height) in zip(sickle, specs):
            length = (8 + lean * 5) * s
            pts = []
            for k in range(8):
                u = k / 7.0
                px = tail_x - f * int(length * u)
                py = tail_y - int(height * s * (u ** 0.62)) - int(2 * s)
                pts.append((px, py))
            pygame.draw.lines(surface, scol, False, pts, max(2, int(1.8 * s)))
            tip = pts[-1]
            pygame.draw.line(surface, scol, tip,
                             (tip[0] - f * int(2 * s), tip[1] + int(2.5 * s)),
                             max(1, int(1.3 * s)))
            glint_pts = pts
        if glint_pts:                                      # iridescent sheen on top plume
            pygame.draw.lines(surface, (118, 196, 150), False, glint_pts[1:5], 1)
    else:
        # hen: upright fan of four shaded feathers
        for a_, fl_, fcol in ((0.12, 9.0, deep), (0.42, 9.5, shade),
                              (0.74, 9.0, col), (1.05, 7.5, light)):
            tip = (tail_x - f * int(_m.cos(a_) * fl_ * s),
                   tail_y - int(_m.sin(a_) * fl_ * s) - int(2 * s))
            pygame.draw.line(surface, fcol, (tail_x, tail_y), tip, max(2, int(2.2 * s)))
        pygame.draw.line(surface, _sh_col(col, 40), (tail_x, tail_y),
                         (tail_x - f * int(8 * s), tail_y - int(6 * s)), 1)

    # ── Body: teardrop (round breast + tapered rear) ─────────────────────────
    back_x = sx - f * int(4 * s)
    breast_x = sx + f * int(3 * s)
    pygame.draw.ellipse(surface, shade, (back_x - int(6 * s), by - bh // 2, int(12 * s), bh))
    pygame.draw.ellipse(surface, col,
                        (breast_x - int(6.5 * s), by - bh // 2 + int(0.5 * s), int(13 * s), bh))
    pygame.draw.ellipse(surface, col, (sx - int(6 * s), by - bh // 2, int(12 * s), bh - int(1 * s)))
    pygame.draw.ellipse(surface, deep, (sx - int(5 * s), by + int(2.5 * s), int(10 * s), int(3.5 * s)))
    pygame.draw.ellipse(surface, light,
                        (breast_x - int(3 * s), by - int(4.5 * s), int(7 * s), int(6 * s)))
    pygame.draw.arc(surface, rim, (sx - int(7 * s), by - bh // 2, int(14 * s), bh),
                    _m.pi * 0.2, _m.pi * 0.9, max(1, int(s)))

    # folded wing with scalloped flight feathers
    wx0 = sx - f * int(2 * s)
    wy0 = by - int(1 * s)
    wing = pygame.Rect(wx0 - int(5 * s), wy0 - int(3.5 * s), int(10 * s), int(7 * s))
    pygame.draw.ellipse(surface, shade, wing)
    pygame.draw.ellipse(surface, _sh_col(col, 14), wing.inflate(-int(2 * s), -int(2 * s)))
    for sc in range(3):
        scx = wx0 - f * int((1 + sc * 2.4) * s)
        pygame.draw.arc(surface, deep,
                        (scx - int(3 * s), wy0 - int(1 * s) + sc, int(6 * s), int(5 * s)),
                        _m.pi * 1.1, _m.pi * 1.95, 1)
    pygame.draw.line(surface, deep, (wx0 + f * int(3 * s), wy0 - int(2 * s)),
                     (wx0 - f * int(5 * s), wy0 + int(2 * s)), 1)

    # ── Neck + head (head dives forward-down through the peck) ───────────────
    hx = sx + f * int((8.5 + pk * 3.5) * s) + int(head_turn * 1.2 * s)
    hy = by - int((9 - pk * 11) * s)
    hr = int(4 * s) if is_rooster else int(3.4 * s)
    sh_x, sh_y = sx + f * int(3.5 * s), by - int(2 * s)
    neck_w0, neck_w1 = 3.4 * s, 2.2 * s
    nvx, nvy = hx - sh_x, hy + int(2 * s) - sh_y
    nl = max(1.0, _m.hypot(nvx, nvy))
    nnx, nny = -nvy / nl, nvx / nl
    neck_col = (208, 122, 38) if is_rooster else col       # rooster: golden hackle cape
    neck_lt = (236, 168, 70) if is_rooster else light
    poly = [(sh_x + nnx * neck_w0, sh_y + nny * neck_w0),
            (sh_x - nnx * neck_w0, sh_y - nny * neck_w0),
            (hx - nnx * neck_w1, hy + int(2 * s) - nny * neck_w1),
            (hx + nnx * neck_w1, hy + int(2 * s) + nny * neck_w1)]
    pygame.draw.polygon(surface, neck_col, [(int(a), int(b)) for a, b in poly])
    pygame.draw.line(surface, neck_lt, (sh_x + f * int(1 * s), sh_y - int(1 * s)),
                     (hx, hy + int(2 * s)), max(1, int(1.2 * s)))
    if is_rooster:                                          # hackle feather ticks
        for hk in range(3):
            u = 0.25 + hk * 0.25
            kx = int(sh_x + nvx * u)
            ky = int(sh_y + nvy * u)
            pygame.draw.line(surface, (180, 96, 30), (kx, ky),
                             (kx - f * int(2 * s), ky + int(2.5 * s)), 1)
    head_col = neck_col if is_rooster else col
    pygame.draw.circle(surface, _sh_col(head_col, 18), (hx, hy), hr)
    pygame.draw.circle(surface, head_col, (hx - f, hy - 1), max(1, hr - 1))
    pygame.draw.circle(surface, _hi_col(head_col, 30),
                       (hx - f * int(1 * s), hy - int(1.5 * s)), max(1, int(hr * 0.55)))

    # comb
    comb_col = (214, 46, 36)
    comb_dk = (158, 26, 22)
    comb_lt = (238, 84, 64)
    if is_rooster:
        comb_pts = [(hx - f * int(3.5 * s), hy - int(2.5 * s)),
                    (hx - f * int(2.5 * s), hy - int(6.5 * s)),
                    (hx - f * int(0.5 * s), hy - int(4.5 * s)),
                    (hx + f * int(1 * s), hy - int(8 * s)),
                    (hx + f * int(3 * s), hy - int(5 * s)),
                    (hx + f * int(4.5 * s), hy - int(6.5 * s)),
                    (hx + f * int(5 * s), hy - int(2.5 * s))]
        pygame.draw.polygon(surface, comb_col, comb_pts)
        pygame.draw.polygon(surface, comb_dk, comb_pts, 1)
        pygame.draw.line(surface, comb_lt, comb_pts[1], comb_pts[3], 1)
    else:
        for cdx, cr_ in ((-1.8, 1.6), (0.2, 2.0), (1.9, 1.5)):  # scalloped lobes
            pygame.draw.circle(surface, comb_col,
                               (hx + f * int(cdx * s), hy - int(4.2 * s)), max(1, int(cr_ * s)))
        pygame.draw.circle(surface, comb_lt, (hx, hy - int(4.6 * s)), max(1, int(0.8 * s)))

    # beak: two-tone, opens near the peck impact
    bx0, by0 = hx + f * int(3 * s), hy
    blen = int(4.5 * s)
    open_amt = int((1.6 if pk > 0.7 else 0.4) * s)
    pygame.draw.polygon(surface, (230, 180, 66),
                        [(bx0, by0 - int(1.4 * s)), (bx0 + f * blen, by0 - open_amt),
                         (bx0, by0 + int(0.2 * s))])
    pygame.draw.polygon(surface, (196, 140, 44),
                        [(bx0, by0 + int(0.2 * s)), (bx0 + f * int(blen * 0.85), by0 + open_amt),
                         (bx0, by0 + int(1.5 * s))])
    # wattles: two lobes under the chin
    wat_h = max(2, int((5.5 if is_rooster else 3.5) * s))
    pygame.draw.ellipse(surface, comb_dk,
                        (bx0 - f * int(1 * s) - int(1.4 * s), by0 + int(1 * s), int(3 * s), wat_h))
    pygame.draw.ellipse(surface, comb_col,
                        (bx0 - f * int(2 * s) - int(1.2 * s), by0 + int(0.6 * s),
                         max(2, int(2.6 * s)), max(2, wat_h - int(1 * s))))
    # eye (rooster gets a fiery iris ring)
    eyx, eyy = hx + f * int(1.4 * s), hy - int(1.2 * s)
    if is_rooster:
        pygame.draw.circle(surface, (196, 120, 40), (eyx, eyy), max(1, int(1.8 * s)))
    pygame.draw.circle(surface, (26, 18, 12), (eyx, eyy), max(1, int(1.2 * s)))
    pygame.draw.circle(surface, (252, 248, 238), (eyx + 1, eyy - 1), 1)
    # dust puff where the beak strikes
    if pk > 0.85:
        tipx, tipy = bx0 + f * blen, ground_y + int(1 * s)
        for d_ in (-2, 1, 3):
            pygame.draw.circle(surface, (150, 128, 96), (tipx + d_, tipy - abs(d_)), 1)


def _draw_live_pig(
    surface: pygame.Surface, sx: int, sy: int, facing: int,
    col: tuple, state: str, t: float, sz: float,
) -> None:
    """Animated pig, lit from the upper-left: barrel body with ham/shoulder
    masses and a spine highlight, jointed trotting legs with cloven hooves,
    floppy flapping ears, jowl, glossy disc snout, double-curl wagging tail.
    Rooting kicks dirt at the snout; the mud state sinks the pig blissfully
    (eyes shut) into a rimmed, sheened wallow pool."""
    import math as _m
    f = facing
    s = sz

    def _sh_col(c, d):
        return (max(0, c[0] - d), max(0, c[1] - d), max(0, c[2] - d))

    def _hi_col(c, d):
        return (min(255, c[0] + d), min(255, c[1] + d), min(255, c[2] + d))

    base = col
    shade = _sh_col(base, 32)
    deep = _sh_col(base, 58)
    light = _hi_col(base, 22)
    rim = _hi_col(base, 40)
    skin = (min(255, base[0] + 4), max(0, base[1] - 26), max(0, base[2] - 22))
    snout_c = (min(255, base[0] + 8), max(0, base[1] - 18), max(0, base[2] - 16))

    # ── Animation drivers ────────────────────────────────────────────────────
    walk = state == "walk"
    leg_phase = t * 8.0
    walk_bob = abs(_m.sin(leg_phase)) * 1.5 * s if walk else 0.0
    root = max(0.0, _m.sin(t * 4.2)) if state == "root" else 0.0   # snout dig cycle
    mud_sink = int(3 * s) if state == "mud" else 0
    idle_bob = _m.sin(t * 1.8) * 0.7 * s
    by = int(sy - walk_bob - idle_bob) + mud_sink
    ground_y = sy + int(8 * s)
    bw = int(16 * s)
    bh = int(9 * s)

    # ── Ground shadow ────────────────────────────────────────────────────────
    shw, shh = int(42 * s), int(14 * s)
    _sh = pygame.Surface((shw, shh), pygame.SRCALPHA)
    pygame.draw.ellipse(_sh, (14, 10, 7, 40), (0, 0, shw, shh))
    pygame.draw.ellipse(_sh, (14, 10, 7, 56),
                        (int(5 * s), int(3 * s), shw - int(10 * s), shh - int(6 * s)))
    surface.blit(_sh, (sx - shw // 2 + int(2 * s), sy + int(4 * s)))

    # ── Wallow pool under the pig in the mud state ───────────────────────────
    if state == "mud":
        pw_, ph_ = int(48 * s), int(19 * s)
        mud = pygame.Surface((pw_, ph_), pygame.SRCALPHA)
        pygame.draw.ellipse(mud, (46, 35, 24, 210), (0, 0, pw_, ph_))
        pygame.draw.ellipse(mud, (62, 48, 33, 230),
                            (int(2 * s), int(1.5 * s), pw_ - int(4 * s), ph_ - int(3 * s)))
        pygame.draw.ellipse(mud, (80, 63, 44, 200),
                            (int(5 * s), int(3 * s), pw_ - int(10 * s), ph_ - int(6 * s)))
        pygame.draw.ellipse(mud, (132, 124, 110, 90),
                            (int(8 * s), int(3.5 * s), int(14 * s), int(3 * s)))   # wet sheen
        surface.blit(mud, (sx - pw_ // 2, sy - int(2 * s)))
        for mi in range(3):                                  # lazily stirred mud blobs
            mx = sx + int(_m.sin(t * 1.6 + mi * 2.1) * 12 * s)
            my = sy + int(3.5 * s) + int(_m.cos(t * 1.2 + mi) * 1.5)
            pygame.draw.circle(surface, (92, 72, 48), (mx, my), max(1, int(1.8 * s)))
        pygame.draw.arc(surface, (110, 96, 76),
                        (sx - int(14 * s), sy + int(1 * s), int(28 * s), int(9 * s)), 0.3, 2.6, 1)

    # ── Legs: tapered, cloven trotters, diagonal-pair trot ───────────────────
    def _leg(lx_off, ph_off, near):
        lx = sx + f * int(lx_off * s)
        swing = _m.sin(leg_phase + ph_off) * 2.6 * s if walk else 0.0
        lift = max(0.0, _m.sin(leg_phase + ph_off + 0.5)) * 1.8 * s if walk else 0.0
        top_y = by + int(3 * s)
        fx = lx + int(f * swing)
        fy = int(ground_y - lift)
        c_out = shade if near else deep
        c_in = base if near else shade
        pygame.draw.line(surface, c_out, (lx, top_y), (fx, fy - int(1 * s)), max(2, int(3.6 * s)))
        pygame.draw.line(surface, c_in, (lx - f, top_y), (fx - f, fy - int(1.4 * s)),
                         max(1, int(1.8 * s)))
        pygame.draw.ellipse(surface, (54, 42, 32),
                            (fx - int(2.2 * s), fy - int(1.6 * s), int(4.4 * s), int(3 * s)))
        pygame.draw.line(surface, (32, 24, 18), (fx, fy - int(1 * s)), (fx, fy + int(1 * s)), 1)

    if state != "mud":
        _leg(-10, _m.pi, False)     # far rear
        _leg(6, 0.0, False)         # far front (diagonal pairs)

    # ── Double-curl tail, wagging ────────────────────────────────────────────
    tx = sx - f * int(15.5 * s)
    ty = by - int(3 * s)
    wag = _m.sin(t * 5.0) * 0.5
    cr = max(2, int(3 * s))
    pygame.draw.arc(surface, shade, (tx - cr, ty - cr, cr * 2, cr * 2),
                    0.3 + wag, _m.pi * 1.6 + wag, max(2, int(2 * s)))
    pygame.draw.arc(surface, base, (tx - cr + 1, ty - cr + 1, cr * 2 - 2, cr * 2 - 2),
                    0.6 + wag, _m.pi * 1.3 + wag, max(1, int(1.4 * s)))
    pygame.draw.arc(surface, shade, (tx - cr // 2, ty - cr // 2 - int(1 * s), cr, cr),
                    0.8 + wag, _m.pi * 1.5 + wag, max(1, int(1.2 * s)))

    # ── Body: barrel + ham/shoulder masses + spine light ─────────────────────
    body_r = pygame.Rect(sx - bw, by - bh, bw * 2, bh * 2)
    pygame.draw.ellipse(surface, shade, body_r)
    pygame.draw.ellipse(surface, base,
                        body_r.move(0, -int(1 * s)).inflate(-int(1 * s), -int(2 * s)))
    ham_x = sx - f * int(9 * s)
    pygame.draw.ellipse(surface, _sh_col(base, 12),
                        (ham_x - int(6 * s), by - int(7 * s), int(12 * s), int(12 * s)))
    pygame.draw.ellipse(surface, _sh_col(base, 6),
                        (sx + f * int(5 * s) - int(5 * s), by - int(7 * s), int(10 * s), int(11 * s)))
    pygame.draw.ellipse(surface, light,
                        (sx - int(bw * 0.55), by - bh, int(bw * 1.1), int(bh * 0.9)))
    pygame.draw.arc(surface, rim, body_r.inflate(-int(3 * s), -int(2 * s)),
                    _m.pi * 0.2, _m.pi * 0.9, max(1, int(1.2 * s)))
    pygame.draw.ellipse(surface, deep,
                        (sx - int(bw * 0.65), by + int(3 * s), int(bw * 1.3), int(bh * 0.6)))
    # soft dapples
    pygame.draw.ellipse(surface, _sh_col((base[0], base[1] - 6, base[2] - 4), 22),
                        (sx - f * int(6 * s) - int(3 * s), by - int(4 * s), int(8 * s), int(6 * s)))
    pygame.draw.ellipse(surface, _sh_col((base[0], base[1] - 4, base[2] - 2), 14),
                        (sx + int(2 * s), by - int(2 * s), int(6 * s), int(5 * s)))
    # drying mud splotches while wallowing
    if state == "mud":
        for mi, (mdx, mdy, mw_, mh_) in enumerate(((-9, 1, 7, 4), (-1, 3, 9, 5),
                                                   (7, 0, 6, 4), (-4, -4, 5, 3))):
            pygame.draw.ellipse(surface, (96, 76, 52) if mi % 2 else (78, 61, 42),
                                (sx + f * int(mdx * s) - int(mw_ * s / 2), by + int(mdy * s),
                                 int(mw_ * s), int(mh_ * s)))

    # ── Head: skull, jowl, brow, ears, snout, eye ────────────────────────────
    hx = sx + f * int(15 * s)
    hy = by - int(1 * s) + int(root * 4.5 * s)
    head_r = pygame.Rect(hx - int(7 * s), hy - int(7 * s), int(14 * s), int(13 * s))
    pygame.draw.ellipse(surface, shade, head_r)
    pygame.draw.ellipse(surface, base, head_r.inflate(-int(1 * s), -int(1 * s)))
    pygame.draw.ellipse(surface, _sh_col(base, 10),
                        (hx - int(3 * s), hy, int(8 * s), int(6 * s)))                  # jowl
    pygame.draw.ellipse(surface, light, (hx - int(5 * s), hy - int(6 * s), int(8 * s), int(5 * s)))
    pygame.draw.arc(surface, _sh_col(base, 22),
                    (hx - int(2 * s), hy - int(4.5 * s), int(6 * s), int(4 * s)),
                    _m.pi * 0.15, _m.pi * 0.85, 1)                                      # brow fold

    # floppy ears (far darker, near lighter), tips flapping
    for esign in (-0.45, 0.5):
        ebx = hx - f * int(3 * s) + f * int(esign * 5 * s)
        eby = hy - int(6.5 * s)
        flop = _m.sin(t * 3.2 + esign * 2.0) * (0.9 if walk or state == "root" else 0.25) * s
        ep = [(ebx, eby + int(1 * s)),
              (ebx + f * int(2.5 * s), eby - int(2.2 * s)),
              (ebx + f * int(5.5 * s), eby + int(1.5 * s) + int(flop)),
              (ebx + f * int(4.5 * s), eby + int(4.5 * s) + int(flop))]
        pygame.draw.polygon(surface, _sh_col(base, 30) if esign < 0 else _sh_col(base, 10), ep)
        inner = [(ebx + f * int(1.5 * s), eby + int(0.5 * s)),
                 (ebx + f * int(3.5 * s), eby - int(0.5 * s)),
                 (ebx + f * int(4.2 * s), eby + int(3 * s) + int(flop))]
        pygame.draw.polygon(surface, skin, inner)
        pygame.draw.lines(surface, _sh_col(base, 36), False, [ep[1], ep[2], ep[3]], 1)

    # snout: bridge + glossy disc + nostrils + mouth line
    snx = hx + f * int(7.5 * s)
    sny = hy + int(2 * s) + int(root * 2 * s)
    pygame.draw.ellipse(surface, base,
                        (hx + f * int(2 * s) - int(2 * s), sny - int(3.2 * s), int(8 * s), int(6.4 * s)))
    pygame.draw.ellipse(surface, _sh_col(snout_c, 20),
                        (snx - int(3.4 * s), sny - int(3.4 * s), int(7 * s), int(7 * s)))
    pygame.draw.ellipse(surface, snout_c,
                        (snx - int(3 * s), sny - int(3 * s), max(3, int(6.4 * s)), max(3, int(6.4 * s))))
    pygame.draw.ellipse(surface, _hi_col(snout_c, 26),
                        (snx - int(2 * s), sny - int(2.2 * s), max(2, int(3 * s)), max(1, int(2 * s))))
    for ni in (-1, 1):
        pygame.draw.ellipse(surface, _sh_col(snout_c, 55),
                            (snx + ni * int(1.6 * s) - 1, sny - int(s),
                             max(1, int(1.4 * s)), max(2, int(2.4 * s))))
    pygame.draw.arc(surface, _sh_col(base, 30),
                    (hx + f * int(3 * s) - int(3 * s), sny + int(1 * s), int(6 * s), int(4 * s)),
                    _m.pi * 1.05, _m.pi * 1.95, 1)                                      # mouth line
    # dirt kicked up at the snout while rooting
    if state == "root" and root > 0.75:
        for d_, h_ in ((-3, 2), (0, 4), (3, 1)):
            pygame.draw.circle(surface, (124, 102, 72),
                               (int(snx + f * d_ * s), int(ground_y - h_ * s)), 1)

    # eye: open with glint, or blissfully shut in the mud
    eyx = hx + f * int(2 * s)
    eyy = hy - int(2.2 * s)
    if state == "mud":
        pygame.draw.arc(surface, (40, 28, 22),
                        (eyx - int(1.6 * s), eyy - int(1 * s), max(3, int(3.2 * s)), max(3, int(2.6 * s))),
                        _m.pi * 0.15, _m.pi * 0.85, max(1, int(1 * s)))
    else:
        pygame.draw.circle(surface, (30, 22, 16), (eyx, eyy), max(1, int(1.7 * s)))
        pygame.draw.circle(surface, (250, 246, 236), (eyx + 1, eyy - 1), max(1, int(0.7 * s)))

    # ── Near-side legs over the body ─────────────────────────────────────────
    if state != "mud":
        _leg(-6, 0.0, True)         # near rear
        _leg(10, _m.pi, True)       # near front


def _draw_live_sheep(
    surface: pygame.Surface, sx: int, sy: int, facing: int,
    col: tuple, state: str, t: float, sz: float,
) -> None:
    """Animated sheep, lit from the upper-left: clumpy two-scale fleece with a
    sunlit crown and shaded skirt, slim dark legs in a stepping gait, dark
    face with pale muzzle, wool topknot and drooped ears; grazes with green
    nibble flecks and flicks its tail puff."""
    import math as _m
    f = facing
    s = sz

    def _sh_col(c, d):
        return (max(0, c[0] - d), max(0, c[1] - d), max(0, c[2] - d))

    def _hi_col(c, d):
        return (min(255, c[0] + d), min(255, c[1] + d), min(255, c[2] + d))

    wool_dk = _sh_col(col, 46)
    col2 = _sh_col(col, 24)
    wool_lt = _hi_col(col, 18)
    wool_rim = _hi_col(col, 32)

    # ── Animation drivers ────────────────────────────────────────────────────
    walk = state == "walk"
    leg_phase = t * 7.5
    walk_bob = abs(_m.sin(leg_phase)) * 1.8 * s if walk else 0.0
    gz = max(0.0, _m.sin(t * 3.0)) if state == "graze" else 0.0
    idle_bob = _m.sin(t * 2.0) * 0.7 * s
    by = int(sy - walk_bob - idle_bob)
    ground_y = sy + int(7 * s)
    bw = int(13 * s)
    bh = int(10 * s)

    # ── Ground shadow ────────────────────────────────────────────────────────
    shw, shh = int(34 * s), int(12 * s)
    _sh = pygame.Surface((shw, shh), pygame.SRCALPHA)
    pygame.draw.ellipse(_sh, (14, 10, 7, 38), (0, 0, shw, shh))
    pygame.draw.ellipse(_sh, (14, 10, 7, 52),
                        (int(4 * s), int(2.5 * s), shw - int(8 * s), shh - int(5 * s)))
    surface.blit(_sh, (sx - shw // 2 + int(2 * s), sy + int(3 * s)))

    # ── Legs: slim, dark, stepping in diagonal pairs ─────────────────────────
    def _leg(lx_off, ph_off, near):
        lx = sx + f * int(lx_off * s)
        swing = _m.sin(leg_phase + ph_off) * 2.4 * s if walk else 0.0
        lift = max(0.0, _m.sin(leg_phase + ph_off + 0.5)) * 1.6 * s if walk else 0.0
        fx = lx + int(f * swing)
        fy = int(ground_y - lift)
        c = (58, 47, 37) if near else (42, 34, 26)
        pygame.draw.line(surface, c, (lx, by + int(3 * s)), (fx, fy), max(2, int(2.6 * s)))
        if near:
            pygame.draw.line(surface, (82, 68, 54), (lx - f, by + int(3 * s)), (fx - f, fy), 1)
        pygame.draw.ellipse(surface, (30, 24, 18),
                            (fx - int(1.5 * s), fy - int(s), int(3 * s), int(2.5 * s)))

    _leg(-8, _m.pi, False)
    _leg(4.5, 0.0, False)

    # tail puff (behind the fleece)
    tx = sx - f * int(12.5 * s)
    ty = by - int(1 * s) + int(_m.sin(t * 3.5) * 1.5)
    pygame.draw.circle(surface, col2, (tx, ty), max(2, int(3.2 * s)))
    pygame.draw.circle(surface, col, (tx, ty - 1), max(2, int(2.8 * s)))
    pygame.draw.circle(surface, wool_lt, (tx - 1, ty - 2), max(1, int(1.6 * s)))

    # ── Fleece: shaded base mass + two scales of clumps + sunlit crown ───────
    pygame.draw.ellipse(surface, wool_dk, (sx - bw, by - bh // 2 + int(2 * s), bw * 2, bh))
    for wi in range(11):
        ang = (wi / 11.0) * _m.tau
        wxp = sx + int(_m.cos(ang) * bw * 0.84)
        wyp = by + int(_m.sin(ang) * bh * 0.66)
        wr = max(2, int((4.0 + _m.sin(wi * 2.3 + t * 1.1) * 0.5) * s))
        depth = (_m.sin(ang) + 1.0) * 0.5            # 0 top → 1 bottom
        ctone = wool_dk if depth > 0.72 else col2 if depth > 0.45 else col
        pygame.draw.circle(surface, ctone, (wxp, wyp + int(0.5 * s)), wr)
    pygame.draw.ellipse(surface, col, (sx - bw + int(2 * s), by - bh // 2, int(bw * 1.85), bh))
    pygame.draw.ellipse(surface, wool_lt, (sx - int(7 * s), by - int(6 * s), int(13 * s), int(6 * s)))
    for wi in range(6):                               # small crown bumps catching the sun
        lxp = sx + int((-8 + wi * 3.2) * s)
        lyp = by - int(5.2 * s) + int(_m.sin(wi * 1.7 + t * 0.9) * 0.8 * s)
        pygame.draw.circle(surface, wool_rim if wi in (1, 2, 3) else wool_lt,
                           (lxp, lyp), max(1, int(2.4 * s)))
    pygame.draw.ellipse(surface, _sh_col(col, 10),    # faintly dingy flank patch
                        (sx - f * int(6 * s), by, int(7 * s), int(4 * s)))

    # ── Head: ruff, dark face, pale muzzle, topknot, ears, one profile eye ───
    hdx = int(gz * 2.5 * s)
    hdy = int(gz * 8.5 * s)
    hx = sx + f * (int(11.5 * s) + hdx)
    hy = by - int(2.5 * s) + hdy
    face = (66, 54, 43)
    face_dk = (48, 39, 31)
    muzzle = (104, 88, 70)
    pygame.draw.circle(surface, col, (hx - f * int(4 * s), hy - int(1 * s)), max(2, int(4.6 * s)))
    pygame.draw.circle(surface, col2, (hx - f * int(4 * s), hy + int(1 * s)), max(2, int(3.4 * s)))
    pygame.draw.ellipse(surface, face_dk,
                        (hx - int(4.6 * s), hy - int(4 * s) + int(s), int(9.2 * s), int(9 * s)))
    pygame.draw.ellipse(surface, face,
                        (hx - int(4.6 * s), hy - int(4.4 * s), int(9.2 * s), int(8.6 * s)))
    pygame.draw.ellipse(surface, muzzle,
                        (hx + f * int(1.2 * s) - int(2.6 * s), hy + int(0.5 * s), int(5.2 * s), int(4 * s)))
    # far ear (dark, mostly hidden) + near drooped ear with inner skin
    pygame.draw.ellipse(surface, face_dk,
                        (hx - f * int(3.4 * s) - int(2.6 * s), hy - int(4.8 * s), int(5.2 * s), int(2.8 * s)))
    ex0 = hx - f * int(1 * s)
    ey0 = hy - int(3.6 * s)
    ep = [(ex0, ey0),
          (ex0 - f * int(4.6 * s), ey0 + int(1.8 * s)),
          (ex0 - f * int(3.6 * s), ey0 + int(3.4 * s))]
    pygame.draw.polygon(surface, face, ep)
    pygame.draw.polygon(surface, (118, 98, 80),
                        [(ex0 - f * int(1.2 * s), ey0 + int(1 * s)),
                         (ex0 - f * int(3.6 * s), ey0 + int(1.9 * s)),
                         (ex0 - f * int(3 * s), ey0 + int(2.8 * s))])
    # wool topknot on the crown
    pygame.draw.circle(surface, col, (hx - f * int(1 * s), hy - int(4.4 * s)), max(2, int(2.8 * s)))
    pygame.draw.circle(surface, wool_rim, (hx - f * int(1.6 * s), hy - int(5 * s)), max(1, int(1.8 * s)))
    # one profile eye + glint
    pygame.draw.circle(surface, (20, 16, 12), (hx + f * int(1.6 * s), hy - int(1.4 * s)),
                       max(1, int(1.5 * s)))
    pygame.draw.circle(surface, (242, 238, 226), (hx + f * int(1.6 * s) + 1, hy - int(1.8 * s)), 1)
    # nostril + nibbling mouth with green flecks while grazing
    pygame.draw.ellipse(surface, (40, 32, 26),
                        (hx + f * int(3 * s) - int(1.4 * s), hy + int(1.6 * s), int(2.8 * s), int(2 * s)))
    if state == "graze" and gz > 0.5:
        pygame.draw.ellipse(surface, (34, 27, 21),
                            (hx + f * int(2.4 * s) - int(1.6 * s), hy + int(3.2 * s), int(3.2 * s), int(2 * s)))
        for gdx in (-1, 2):
            pygame.draw.circle(surface, (96, 134, 64),
                               (int(hx + f * (3 + gdx) * s), int(hy + 5 * s)), 1)

    # ── Near-side legs over the fleece ───────────────────────────────────────
    _leg(-4.5, 0.0, True)
    _leg(8, _m.pi, True)
