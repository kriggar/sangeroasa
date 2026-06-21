"""game/world/scenes.py — town / wilderness / ice-biome scene builders + church-pos load."""
import os
import json
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
from game.farm import *
from game.entities import *
from game.vendors import *
from game.items import *
from game.assets import *

__all__ = [
    'build_town_scene',
    'build_wilderness_scene',
    'build_ice_biome_scene',
    'load_church_position',
]


def build_town_scene(size: Tuple[int, int], deleted_props: Optional[set] = None) -> Tuple[pygame.Surface, List[pygame.Rect], list, list, list, list]:  # noqa: C901
    if deleted_props is None:
        deleted_props = set()

    # Animated foliage positions: list of (x, y, kind, size) for per-frame animation
    # kind: "grass_tuft" | "bush_sway" | "tree_crown"
    foliage_anim_positions: list = []

    def _deleted(kind: str, x: float, y: float) -> bool:
        return (kind, int(round(x)), int(round(y))) in deleted_props

    prop_registry: list = []

    def _reg(kind: str, x: float, y: float) -> None:
        prop_registry.append({"kind": kind, "x": int(round(x)), "y": int(round(y))})

    width, height = size
    scene = pygame.Surface(size).convert()
    center_x = width // 2
    rng = random.Random(42)

    # Ground-space scale factors (relative to original 3200×2200 town)
    _gsx = width / 3200.0
    _gsy = (height - HORIZON_Y) / 1840.0  # 1840 = original 2200 - 360
    def H(y_off):
        """Scale a Y offset from HORIZON_Y for the expanded world."""
        return HORIZON_Y + int(y_off * _gsy)
    def CX(x_off):
        """Scale an X offset from center_x for the expanded world."""
        return center_x + int(x_off * _gsx)

    draw_vertical_gradient(scene, pygame.Rect(0, 0, width, HORIZON_Y + 70), (10, 14, 24), (34, 40, 54))
    draw_vertical_gradient(scene, pygame.Rect(0, HORIZON_Y, width, height - HORIZON_Y), (66, 60, 50), (46, 42, 36))

    obstacles: List[pygame.Rect] = []
    canal_rects: List[pygame.Rect] = []

    wall_y = HORIZON_Y + 120
    draw_fortified_wall(scene, pygame.Rect(60, wall_y, width - 120, 100))
    # Stone arch behind church removed — church facade covers this area
    obstacles.append(pygame.Rect(center_x - 180, wall_y + 50, 360, 34))

    for tx in (150, width - 150):
        _reg("wall_house", tx, wall_y + 40)
        if not _deleted("wall_house", tx, wall_y + 40):
            t = draw_district_house(scene, tx, wall_y + 40, 0.95, 700 + tx, 'saint')
            obstacles.append(t.inflate(-8, -8))

    plaza = pygame.Rect(80, HORIZON_Y + 210, width - 160, height - (HORIZON_Y + 320))
    # Full ground rect — covers EVERYTHING below the sky
    _ground = pygame.Rect(0, HORIZON_Y, width, height - HORIZON_Y)
    # ── REALISTIC DIRT GROUND — multi-pass tile + detail ──
    _grng = random.Random(77)

    # Build 3 different 64×64 dirt tiles for variety
    _TILE = 64
    _dirt_tiles: list = []
    for _ti in range(3):
        _dt = pygame.Surface((_TILE, _TILE))
        _dt_seed = 9999 + _ti * 7777
        # Per-pixel procedural noise
        for _ty2 in range(_TILE):
            for _tx2 in range(_TILE):
                # Multi-octave hash noise
                _h1 = ((_tx2 * 2654435761 + _dt_seed) ^ (_ty2 * 2246822519)) & 0xFFFFFFFF
                _h2 = (((_tx2 >> 1) * 1640531527 + _dt_seed) ^ ((_ty2 >> 1) * 2891336453)) & 0xFFFFFFFF
                _h3 = (((_tx2 >> 2) * 3266489917 + _dt_seed) ^ ((_ty2 >> 2) * 668265263)) & 0xFFFFFFFF
                _n1 = ((_h1 >> 8) & 0xFF) / 255.0  # fine grain
                _n2 = ((_h2 >> 8) & 0xFF) / 255.0  # medium
                _n3 = ((_h3 >> 8) & 0xFF) / 255.0  # coarse
                _nf = _n1 * 0.5 + _n2 * 0.3 + _n3 * 0.2
                # Wide colour range for visible texture — warm lived-in earth
                # (the old 36-84 range read as black mud under dusk lighting)
                _base_r = 78 + int(_nf * 52)   # 78-130
                _base_g = 66 + int(_nf * 44)   # 66-110
                _base_b = 47 + int(_nf * 31)   # 47-78
                # Warm/cool patches
                _h4 = ((_tx2 * 48271 + _ty2 * 16807 + _dt_seed) >> 10) & 0xFF
                if _h4 > 200:
                    _base_r += 8; _base_g += 4
                elif _h4 < 40:
                    _base_g += 5; _base_b += 4
                elif _h4 < 80:
                    _base_r -= 4; _base_g -= 2; _base_b += 2
                _dt.set_at((_tx2, _ty2), (max(0, min(255, _base_r)),
                                           max(0, min(255, _base_g)),
                                           max(0, min(255, _base_b))))
        # Embedded pebbles in tile
        _dt_rng = random.Random(_dt_seed + 111)
        for _ in range(100):
            _ppx = _dt_rng.randint(0, _TILE - 1)
            _ppy = _dt_rng.randint(0, _TILE - 1)
            _ppr = _dt_rng.randint(1, 3)
            _ppv = _dt_rng.randint(90, 122)
            pygame.draw.circle(_dt, (_ppv, _ppv - 6, _ppv - 14), (_ppx, _ppy), _ppr)
            if _ppr >= 2:
                pygame.draw.circle(_dt, (min(255, _ppv + 16), min(255, _ppv + 10), min(255, _ppv + 2)), (_ppx - 1, _ppy - 1), 1)
                pygame.draw.circle(_dt, (max(0, _ppv - 20), max(0, _ppv - 24), max(0, _ppv - 28)), (_ppx + 1, _ppy + 1), 1)
        # Dark grain lines
        for _ in range(30):
            _glx = _dt_rng.randint(0, _TILE - 1)
            _gly = _dt_rng.randint(0, _TILE - 1)
            _glx2 = _glx + _dt_rng.randint(-6, 6)
            _gly2 = _gly + _dt_rng.randint(-6, 6)
            _glv = _dt_rng.randint(58, 74)
            pygame.draw.line(_dt, (_glv, _glv - 6, _glv - 12), (_glx, _gly), (_glx2, _gly2), 1)
        _dirt_tiles.append(_dt)

    # Stamp tiles across the ENTIRE ground with variety
    _tile_rng = random.Random(4242)
    for _sy in range(_ground.top, _ground.bottom, _TILE):
        for _sx in range(_ground.left, _ground.right, _TILE):
            _ti_idx = ((_sx // _TILE) * 3 + (_sy // _TILE) * 7) % 3
            scene.blit(_dirt_tiles[_ti_idx], (_sx, _sy))

    # Large-scale colour zones — massive soft blobs for natural variation
    _earth_overlays = [
        (118, 102, 76), (106, 92, 68), (96, 84, 62), (88, 76, 56),
        (104, 98, 78), (94, 88, 72), (124, 108, 78), (112, 98, 66),
        (92, 78, 54), (102, 88, 60), (84, 74, 52), (116, 106, 82),
    ]
    for _ in range(500):
        _ew = _grng.randint(100, 600)
        _eh = _grng.randint(50, 300)
        _ex = _grng.randint(_ground.left - 40, max(_ground.left, _ground.right - _ew))
        _ey = _grng.randint(_ground.top - 20, max(_ground.top, _ground.bottom - _eh))
        _ec = _earth_overlays[_grng.randint(0, len(_earth_overlays) - 1)]
        _ep = pygame.Surface((_ew, _eh), pygame.SRCALPHA)
        pygame.draw.ellipse(_ep, (*_ec, _grng.randint(25, 70)), (0, 0, _ew, _eh))
        scene.blit(_ep, (_ex, _ey))

    # Dark compacted/wet soil patches
    for _ in range(200):
        _dw = _grng.randint(20, 160)
        _dh = _grng.randint(10, 80)
        _dx2 = _grng.randint(_ground.left, max(_ground.left + 1, _ground.right - _dw))
        _dy2 = _grng.randint(_ground.top, max(_ground.top + 1, _ground.bottom - _dh))
        _dp = pygame.Surface((_dw, _dh), pygame.SRCALPHA)
        _dv = _grng.randint(0, 10)
        pygame.draw.ellipse(_dp, (58 + _dv, 49 + _dv, 36 + _dv, _grng.randint(30, 80)), (0, 0, _dw, _dh))
        scene.blit(_dp, (_dx2, _dy2))

    # Lighter sandy patches (drier areas)
    for _ in range(150):
        _lw = _grng.randint(30, 200)
        _lh = _grng.randint(15, 100)
        _lx = _grng.randint(_ground.left, max(_ground.left + 1, _ground.right - _lw))
        _ly = _grng.randint(_ground.top, max(_ground.top + 1, _ground.bottom - _lh))
        _lp = pygame.Surface((_lw, _lh), pygame.SRCALPHA)
        _lv = _grng.randint(0, 12)
        pygame.draw.ellipse(_lp, (134 + _lv, 119 + _lv, 88 + _lv, _grng.randint(20, 55)), (0, 0, _lw, _lh))
        scene.blit(_lp, (_lx, _ly))

    # Branching cracks in dried earth (sparse — this is a lived-in town, not a desert)
    for _ in range(110):
        _cx1 = _grng.randint(_ground.left + 10, _ground.right - 10)
        _cy1 = _grng.randint(_ground.top + 10, _ground.bottom - 10)
        _cang = _grng.uniform(0, math.tau)
        _segs = _grng.randint(2, 6)
        _cpx, _cpy = _cx1, _cy1
        for _si in range(_segs):
            _clen = _grng.randint(8, 35)
            _cang += _grng.uniform(-0.7, 0.7)
            _cnx = _cpx + int(math.cos(_cang) * _clen)
            _cny = _cpy + int(math.sin(_cang) * _clen)
            _cv = _grng.randint(62, 76)
            pygame.draw.line(scene, (_cv, _cv - 4, _cv - 8), (_cpx, _cpy), (_cnx, _cny), 1)
            if _grng.random() > 0.55:
                _ba = _cang + _grng.uniform(0.4, 1.4) * _grng.choice([-1, 1])
                _bl = _grng.randint(6, 18)
                pygame.draw.line(scene, (_cv + 2, _cv - 2, _cv - 6),
                                 (_cpx, _cpy),
                                 (_cpx + int(math.cos(_ba) * _bl), _cpy + int(math.sin(_ba) * _bl)), 1)
            _cpx, _cpy = _cnx, _cny

    # Scattered rocks — irregular shapes with proper shadow+highlight
    for _ in range(1000):
        _rx = _grng.randint(_ground.left + 4, _ground.right - 4)
        _ry = _grng.randint(_ground.top + 4, _ground.bottom - 4)
        _rw = _grng.randint(2, 12)
        _rh = _grng.randint(2, 8)
        _rv = _grng.randint(92, 126)
        pygame.draw.ellipse(scene, (max(0, _rv - 30), max(0, _rv - 34), max(0, _rv - 38)), (_rx + 1, _ry + 1, _rw, _rh))
        pygame.draw.ellipse(scene, (_rv, _rv - 6, _rv - 14), (_rx, _ry, _rw, _rh))
        if _rw > 4:
            pygame.draw.ellipse(scene, (min(255, _rv + 20), min(255, _rv + 14), min(255, _rv + 4)),
                                (_rx + 1, _ry + 1, max(2, _rw - 3), max(2, _rh - 2)), 1)

    # Mud puddles with wet shine
    for _ in range(80):
        _mx = _grng.randint(_ground.left + 20, _ground.right - 20)
        _my = _grng.randint(_ground.top + 20, _ground.bottom - 20)
        _mw = _grng.randint(16, 70)
        _mh = _grng.randint(8, 35)
        _ms = pygame.Surface((_mw, _mh), pygame.SRCALPHA)
        pygame.draw.ellipse(_ms, (48, 42, 34, 130), (0, 0, _mw, _mh))
        pygame.draw.ellipse(_ms, (60, 56, 50, 90), (_mw // 6, _mh // 6, _mw * 2 // 3, _mh * 2 // 3))
        pygame.draw.ellipse(_ms, (118, 128, 130, 70), (_mw // 4, _mh // 4, _mw // 3, max(2, _mh // 5)))
        scene.blit(_ms, (_mx, _my))

    # Wheel ruts and worn trails
    for _ in range(60):
        _rtx = _grng.randint(_ground.left + 40, _ground.right - 40)
        _rty = _grng.randint(_ground.top + 40, _ground.bottom - 40)
        _rtlen = _grng.randint(40, 200)
        _rtang = _grng.uniform(-0.5, 0.5)
        _rtx2 = _rtx + int(_rtlen * math.cos(_rtang))
        _rty2 = _rty + int(_rtlen * math.sin(_rtang))
        pygame.draw.line(scene, (66, 55, 40), (_rtx, _rty), (_rtx2, _rty2), 2)
        pygame.draw.line(scene, (60, 50, 36), (_rtx, _rty + 14), (_rtx2, _rty2 + 14), 2)

    # Footprint trails
    for _ in range(50):
        _fpx = _grng.randint(_ground.left + 40, _ground.right - 40)
        _fpy = _grng.randint(_ground.top + 40, _ground.bottom - 40)
        _fpang = _grng.uniform(0, math.tau)
        for _fsi in range(_grng.randint(8, 20)):
            _fps = pygame.Surface((8, 4), pygame.SRCALPHA)
            pygame.draw.ellipse(_fps, (60, 50, 38, 70), (0, 0, 8, 4))
            _rot_fp = pygame.transform.rotate(_fps, -math.degrees(_fpang))
            scene.blit(_rot_fp, (_fpx - _rot_fp.get_width() // 2, _fpy - _rot_fp.get_height() // 2))
            _fpx += int(math.cos(_fpang) * 12)
            _fpy += int(math.sin(_fpang) * 12)
            _fpang += _grng.uniform(-0.25, 0.25)

    # Scattered twigs and debris
    for _ in range(500):
        _twx = _grng.randint(_ground.left + 4, _ground.right - 4)
        _twy = _grng.randint(_ground.top + 4, _ground.bottom - 4)
        _twlen = _grng.randint(3, 16)
        _twang = _grng.uniform(0, math.pi)
        _twv = _grng.randint(76, 104)
        _twc2 = (_twv, _twv - 10, _twv - 18)
        _twx2 = _twx + int(math.cos(_twang) * _twlen)
        _twy2 = _twy + int(math.sin(_twang) * _twlen)
        pygame.draw.line(scene, _twc2, (_twx, _twy), (_twx2, _twy2), 1)
        if _twlen > 8 and _grng.random() > 0.4:
            _bm = ((_twx + _twx2) // 2, (_twy + _twy2) // 2)
            _ba2 = _twang + _grng.uniform(0.3, 1.2) * _grng.choice([-1, 1])
            pygame.draw.line(scene, _twc2, _bm,
                             (_bm[0] + int(math.cos(_ba2) * 5), _bm[1] + int(math.sin(_ba2) * 5)), 1)

    # Small leaf litter
    for _ in range(300):
        _lfx = _grng.randint(_ground.left + 4, _ground.right - 4)
        _lfy = _grng.randint(_ground.top + 4, _ground.bottom - 4)
        _lfv = _grng.randint(0, 2)
        if _lfv == 0:
            _lfc = (_grng.randint(92, 116), _grng.randint(70, 84), _grng.randint(38, 50))
        elif _lfv == 1:
            _lfc = (_grng.randint(104, 126), _grng.randint(78, 94), _grng.randint(44, 56))
        else:
            _lfc = (_grng.randint(76, 92), _grng.randint(84, 100), _grng.randint(46, 58))
        _lfs = pygame.Surface((6, 4), pygame.SRCALPHA)
        pygame.draw.ellipse(_lfs, (*_lfc, 180), (0, 0, 6, 4))
        _rot_lf = pygame.transform.rotate(_lfs, _grng.randint(0, 180))
        scene.blit(_rot_lf, (_lfx, _lfy))

    # (dirt-to-stone transition added after _road_rects is built)

    # Layer 3: Dense grass tuft clusters with curved multi-blade detail
    for _ in range(1500):
        _tx = _grng.randint(plaza.left + 14, plaza.right - 14)
        _ty = _grng.randint(plaza.top + 14, plaza.bottom - 14)
        _blade_count = _grng.randint(4, 8)
        for _bi in range(_blade_count):
            _bx = _tx + _grng.randint(-3, 3)
            _bh = _grng.randint(6, 16)
            _curve = _grng.uniform(-4, 4)
            _gc = (50 + _grng.randint(0, 32), 86 + _grng.randint(0, 38), 40 + _grng.randint(0, 18))
            _thickness = _grng.choice([1, 1, 1, 2])
            # Two-segment curved blade
            _mid_x = _bx + int(_curve * 0.5)
            _mid_y = _ty - _bh // 2
            _tip_x = _bx + int(_curve)
            _tip_y = _ty - _bh
            pygame.draw.line(scene, _gc, (_bx, _ty), (_mid_x, _mid_y), _thickness)
            # Lighter tip
            _tc = (min(255, _gc[0] + 20), min(255, _gc[1] + 22), min(255, _gc[2] + 12))
            pygame.draw.line(scene, _tc, (_mid_x, _mid_y), (_tip_x, _tip_y), 1)
        # Collect for animation (every 3rd tuft to keep perf reasonable)
        if _ % 3 == 0:
            foliage_anim_positions.append((_tx, _ty, "grass_tuft", _grng.randint(6, 14)))

    # Layer 4: Lush grass patches with individual blade detail and depth
    for _ in range(420):
        _gw = _grng.randint(60, 220)
        _gh = _grng.randint(30, 110)
        _gx = _grng.randint(plaza.left + 20, max(plaza.left + 21, plaza.right - _gw - 20))
        _gy = _grng.randint(plaza.top + 20, max(plaza.top + 21, plaza.bottom - _gh - 20))
        _gs = _grng.randint(0, 18)
        # Outer soft feather
        _gpatch_o = pygame.Surface((_gw + 10, _gh + 6), pygame.SRCALPHA)
        pygame.draw.ellipse(_gpatch_o, (50 + _gs, 80 + _gs, 42 + _gs // 2, 95), (0, 0, _gw + 10, _gh + 6))
        scene.blit(_gpatch_o, (_gx - 5, _gy - 3))
        # Main grass body
        _gpatch = pygame.Surface((_gw, _gh), pygame.SRCALPHA)
        pygame.draw.ellipse(_gpatch, (58, 92 + _gs, 44 + _gs // 2, 155), (0, 0, _gw, _gh))
        # Inner lighter variation
        _iw = max(4, _gw - _grng.randint(20, 40))
        _ih = max(4, _gh - _grng.randint(10, 20))
        _ix = (_gw - _iw) // 2 + _grng.randint(-4, 4)
        _iy = (_gh - _ih) // 2 + _grng.randint(-2, 2)
        pygame.draw.ellipse(_gpatch, (66 + _gs, 102 + _gs, 50 + _gs // 2, 125), (_ix, _iy, _iw, _ih))
        scene.blit(_gpatch, (_gx, _gy))
        # Individual blade tufts on this patch
        _pcx, _pcy = _gx + _gw // 2, _gy + _gh // 2
        for _ in range(_grng.randint(4, 10)):
            _bpx = _pcx + _grng.randint(-_gw // 3, _gw // 3)
            _bpy = _pcy + _grng.randint(-_gh // 3, _gh // 3)
            _bbh = _grng.randint(5, 12)
            _bgc = (42 + _grng.randint(0, 22), 72 + _grng.randint(0, 26), 32 + _grng.randint(0, 12))
            _bcurve = _grng.randint(-3, 3)
            pygame.draw.line(scene, _bgc, (_bpx, _bpy), (_bpx + _bcurve, _bpy - _bbh), 1)
        # Collect center for animation
        foliage_anim_positions.append((_pcx, _pcy, "grass_tuft", _grng.randint(8, 14)))

    # Layer 5: Mud ruts and wheel tracks (dark linear marks)
    for _ in range(30):
        _rx = _grng.randint(plaza.left + 60, plaza.right - 60)
        _ry = _grng.randint(plaza.top + 60, plaza.bottom - 60)
        _rlen = _grng.randint(40, 160)
        _rang = _grng.uniform(-0.4, 0.4)
        _rx2 = _rx + int(_rlen * math.cos(_rang))
        _ry2 = _ry + int(_rlen * math.sin(_rang))
        pygame.draw.line(scene, (68, 57, 42), (_rx, _ry), (_rx2, _ry2), 2)
        # Parallel rut (wheel pair)
        pygame.draw.line(scene, (64, 54, 40), (_rx, _ry + 14), (_rx2, _ry2 + 14), 2)

    # Layer 6: Wildflowers — multi-petal with stems and leaves
    for _ in range(200):
        _fx = _grng.randint(plaza.left + 20, plaza.right - 20)
        _fy = _grng.randint(plaza.top + 20, plaza.bottom - 20)
        _stem_h = _grng.randint(5, 12)
        _stem_c = (38 + _grng.randint(0, 14), 66 + _grng.randint(0, 16), 28 + _grng.randint(0, 6))
        # Curved stem
        _scurve = _grng.randint(-2, 2)
        pygame.draw.line(scene, _stem_c, (_fx, _fy), (_fx + _scurve, _fy - _stem_h), 1)
        # Small leaf on stem
        if _stem_h > 7:
            _lside = _grng.choice([-1, 1])
            _ly = _fy - _stem_h // 2
            pygame.draw.line(scene, _stem_c, (_fx + _scurve // 2, _ly), (_fx + _scurve // 2 + _lside * 3, _ly - 1), 1)
        # Flower head
        _ftype = _grng.randint(0, 3)
        _ftx = _fx + _scurve
        _fty = _fy - _stem_h
        if _ftype == 0:
            # Daisy
            _fc = (240, 240, 245)
            for _pi in range(_grng.randint(5, 7)):
                _pa = _pi * (math.tau / 6) + _grng.uniform(-0.2, 0.2)
                _pr = _grng.randint(2, 3)
                _ppx = _ftx + int(math.cos(_pa) * _pr)
                _ppy = _fty + int(math.sin(_pa) * _pr)
                pygame.draw.circle(scene, _fc, (_ppx, _ppy), 1)
            pygame.draw.circle(scene, (230, 200, 50), (_ftx, _fty), 1)
        elif _ftype == 1:
            # Red poppy
            _fc = (200 + _grng.randint(0, 40), 40 + _grng.randint(0, 20), 30)
            pygame.draw.circle(scene, _fc, (_ftx, _fty), _grng.randint(2, 3))
            pygame.draw.circle(scene, (40, 30, 28), (_ftx, _fty), 1)
        elif _ftype == 2:
            # Bluebell
            pygame.draw.ellipse(scene, (80 + _grng.randint(0, 30), 100 + _grng.randint(0, 30), 200 + _grng.randint(0, 40)),
                                (_ftx - 2, _fty, 4, 3))
        else:
            # Buttercup
            pygame.draw.circle(scene, (240, 210, 40), (_ftx, _fty), 2)
            pygame.draw.circle(scene, (255, 230, 80), (_ftx, _fty), 1)

    # Layer 7: Clover patches and moss clusters for ground realism
    for _ in range(150):
        _cx = _grng.randint(plaza.left + 30, plaza.right - 30)
        _cy = _grng.randint(plaza.top + 30, plaza.bottom - 30)
        _ctype = _grng.randint(0, 1)
        if _ctype == 0:
            # Clover cluster (3-leaf)
            _cc = (36 + _grng.randint(0, 14), 62 + _grng.randint(0, 18), 28 + _grng.randint(0, 8))
            for _li in range(3):
                _la = _li * (math.tau / 3) + _grng.uniform(-0.3, 0.3)
                _ldist = _grng.randint(2, 4)
                _lxp = _cx + int(math.cos(_la) * _ldist)
                _lyp = _cy + int(math.sin(_la) * _ldist)
                pygame.draw.circle(scene, _cc, (_lxp, _lyp), 2)
            # Occasional 4th leaf (lucky clover)
            if _grng.random() > 0.9:
                _la = math.tau * 0.75
                pygame.draw.circle(scene, _cc, (_cx + int(math.cos(_la) * 3), _cy + int(math.sin(_la) * 3)), 2)
        else:
            # Moss patch
            _mr = _grng.randint(3, 8)
            _mc = (44 + _grng.randint(0, 12), 70 + _grng.randint(0, 16), 34 + _grng.randint(0, 8))
            _ms = pygame.Surface((_mr * 2, _mr * 2), pygame.SRCALPHA)
            pygame.draw.circle(_ms, (*_mc, 100), (_mr, _mr), _mr)
            scene.blit(_ms, (_cx - _mr, _cy - _mr))

    # Town border wall base
    pygame.draw.rect(scene, (34, 34, 38), plaza, 3, border_radius=18)

    # ═══════════════════════════════════════════════════════════════════
    # SHOP POSITIONS — computed from scattered anchor offsets (needed for roads)
    # ═══════════════════════════════════════════════════════════════════
    _shop = {}
    _anchor_map = {
        "blacksmith": BLACKSMITH_SHOP_ANCHOR_OFFSET,
        "baker": BAKER_SHOP_ANCHOR_OFFSET,
        "tailor": TAILOR_SHOP_ANCHOR_OFFSET,
        "alchemist": ALCHEMIST_SHOP_ANCHOR_OFFSET,
        "merchant": MERCHANT_SHOP_ANCHOR_OFFSET,
        "leatherworker": LEATHERWORKER_SHOP_ANCHOR_OFFSET,
        "herbalist": HERBALIST_SHOP_ANCHOR_OFFSET,
        "miller": MILLER_SHOP_ANCHOR_OFFSET,
        "cooper": COOPER_SHOP_ANCHOR_OFFSET,
        "guard": GUARD_SHOP_ANCHOR_OFFSET,
        "tanner": TANNER_SHOP_ANCHOR_OFFSET,
        "sailor": SAILOR_SHOP_ANCHOR_OFFSET,
    }
    for _sname, (_sox, _soy) in _anchor_map.items():
        _shop[_sname] = (center_x + _sox, HORIZON_Y + _soy)

    # ═══════════════════════════════════════════════════════════════════
    # ROAD NETWORK — drawn BEFORE houses/props to prevent clipping
    # Main avenues = cobblestone paved, branches = dirt
    # ═══════════════════════════════════════════════════════════════════
    _road_y_n = HORIZON_Y + 840
    _road_y_m = HORIZON_Y + 2440
    _road_y_s = HORIZON_Y + 4040
    _road_y_fs = HORIZON_Y + 5240

    # ── ORGANIC WINDING STREETS ──────────────────────────────────────────
    # Same topology as before (every shop/farm/cemetery stays connected) but
    # every road is a gently bending polyline stamped in short segments, so
    # the town reads as grown-not-planned. Exclusion rects follow each
    # segment, so _on_road()/prop checks hug the actual curve.
    _road_margin = 30  # extra clearance on each side
    _road_rects: list = []
    _paved_specs: list = []   # (pts, width, seed) — re-stamped after dirt lanes

    def _bend_pts(x1, y1, x2, y2, seed, amp=44, bends=2.2):
        """Gently winding polyline between two points, ends pinned."""
        _wr = random.Random(seed * 9176 + 13)
        _dx, _dy = x2 - x1, y2 - y1
        _L = max(1.0, math.hypot(_dx, _dy))
        _nx, _ny = -_dy / _L, _dx / _L
        _steps = max(3, int(_L / 170))
        _ph = _wr.uniform(0, math.tau)
        _a = amp * _wr.uniform(0.65, 1.0)
        _pts = []
        for _i in range(_steps + 1):
            _t = _i / _steps
            _env = math.sin(_t * math.pi) ** 0.7
            _off = (math.sin(_t * bends * math.pi + _ph) * _a + _wr.uniform(-7, 7)) * _env
            _pts.append((x1 + _dx * _t + _nx * _off, y1 + _dy * _t + _ny * _off))
        return _pts

    def _stamp_road_pts(pts, rwidth, seed, paved, record=True):
        """Stamp road segments along a polyline (slightly overlapped so the
        per-segment outlines don't read as seams) + record exclusion rects."""
        for _i in range(len(pts) - 1):
            _ax, _ay = pts[_i]
            _bx, _by = pts[_i + 1]
            _sl = max(1.0, math.hypot(_bx - _ax, _by - _ay))
            _ex = _bx + (_bx - _ax) / _sl * 10.0   # overlap into the next segment
            _ey = _by + (_by - _ay) / _sl * 10.0
            if paved:
                draw_paved_road(scene, int(_ax), int(_ay), int(_ex), int(_ey), width=rwidth, seed=seed + _i)
            else:
                draw_dirt_road(scene, int(_ax), int(_ay), int(_ex), int(_ey), width=rwidth, seed=seed + _i)
            if record:
                _hw = rwidth // 2 + _road_margin
                _road_rects.append(pygame.Rect(int(min(_ax, _bx)) - _hw, int(min(_ay, _by)) - _hw,
                                               int(abs(_bx - _ax)) + _hw * 2, int(abs(_by - _ay)) + _hw * 2))
        if not paved:
            # wheel ruts + hoof scuffs following the lane
            _rrng = random.Random(seed * 31 + 7)
            for _i in range(len(pts) - 1):
                _ax, _ay = pts[_i]
                _bx, _by = pts[_i + 1]
                _ddx, _ddy = _bx - _ax, _by - _ay
                _sl = max(1.0, math.hypot(_ddx, _ddy))
                _nx, _ny = -_ddy / _sl, _ddx / _sl
                for _ro in (-rwidth * 0.22, rwidth * 0.22):
                    pygame.draw.line(scene, (74, 61, 44),
                                     (_ax + _nx * _ro, _ay + _ny * _ro),
                                     (_bx + _nx * _ro, _by + _ny * _ro), 3)
                    pygame.draw.line(scene, (62, 51, 36),
                                     (_ax + _nx * _ro, _ay + _ny * _ro + 1),
                                     (_bx + _nx * _ro, _by + _ny * _ro + 1), 1)
                for _ in range(int(_sl / 38)):
                    _t = _rrng.random()
                    pygame.draw.ellipse(scene, (88, 73, 52),
                                        (int(_ax + _ddx * _t) - 4, int(_ay + _ddy * _t) - 2, 8, 4))

    def _road(x1, y1, x2, y2, rwidth, seed, paved=False, amp=44):
        _pts = _bend_pts(x1, y1, x2, y2, seed, amp=amp)
        if paved:
            _paved_specs.append((_pts, rwidth, seed))
        _stamp_road_pts(_pts, rwidth, seed, paved)

    # High street: north gate → market square, and market square → south.
    # (It feeds INTO the square instead of slicing through it.)
    _sq_top = HORIZON_Y + 1600
    _sq_bot = HORIZON_Y + 2500
    _road(center_x, HORIZON_Y + 250, center_x, _sq_top + 60, rwidth=100, seed=1, paved=True, amp=52)
    _road(center_x, _sq_bot - 60, center_x, height - 300, rwidth=100, seed=16, paved=True, amp=58)
    # East-west paved cross streets (the middle one breaks at the square)
    _road(400, _road_y_n, width - 400, _road_y_n, rwidth=85, seed=2, paved=True, amp=46)
    _road(400, _road_y_m, center_x - 660, _road_y_m, rwidth=85, seed=3, paved=True, amp=42)
    _road(center_x + 660, _road_y_m, width - 400, _road_y_m, rwidth=85, seed=17, paved=True, amp=42)
    _road(400, _road_y_s, width - 400, _road_y_s, rwidth=85, seed=4, paved=True, amp=46)
    # Far south cross road (dirt — winds like a country lane)
    _road(800, _road_y_fs, width - 800, _road_y_fs, rwidth=70, seed=5, amp=72)

    # Dirt branch lanes to shops (short, nearly straight; overshoot the
    # junction so they always meet the curved arterial)
    _road(_shop["blacksmith"][0], _shop["blacksmith"][1] + 120,
          _shop["blacksmith"][0], _road_y_n + 70, rwidth=55, seed=8, amp=14)
    _road(_shop["tailor"][0], _shop["tailor"][1] + 120,
          _shop["tailor"][0], _road_y_n + 70, rwidth=55, seed=9, amp=14)
    _road(_shop["alchemist"][0], _shop["alchemist"][1] + 120,
          _shop["alchemist"][0], _road_y_m + 70, rwidth=55, seed=10, amp=14)
    _road(_shop["leatherworker"][0], _shop["leatherworker"][1] + 120,
          _shop["leatherworker"][0], _road_y_m + 70, rwidth=55, seed=11, amp=14)
    # Road to harbour (dirt branch east)
    _road(_shop["sailor"][0] - 200, _road_y_n, _shop["sailor"][0], _shop["sailor"][1],
          rwidth=65, seed=6, amp=30)
    _road(_shop["sailor"][0], _shop["sailor"][1], _shop["sailor"][0], _shop["sailor"][1] + 600,
          rwidth=55, seed=7, amp=22)
    # Farm lanes (country lanes wander the most)
    _farm_sw = (1800, HORIZON_Y + 4600)
    _farm_se = (8200, HORIZON_Y + 4600)
    _road(_shop["herbalist"][0], _road_y_s + 60, _farm_sw[0], _farm_sw[1], rwidth=50, seed=12, amp=88)
    _road(_shop["cooper"][0], _road_y_s + 60, _farm_se[0], _farm_se[1], rwidth=50, seed=13, amp=88)
    # Cemetery walk (paved spur off the boulevard)
    _cemetery_pos = (center_x - 420, HORIZON_Y + 5700)
    _road(center_x, _cemetery_pos[1] - 120, _cemetery_pos[0], _cemetery_pos[1] - 120,
          rwidth=58, seed=14, paved=True, amp=22)
    # Secondary residential lanes (narrow winding dirt paths between rows)
    _lane_ys: list = []
    for _lane_y in range(HORIZON_Y + 1200, HORIZON_Y + 5000, 600):
        if abs(_lane_y - _road_y_n) > 200 and abs(_lane_y - _road_y_m) > 200 and abs(_lane_y - _road_y_s) > 200:
            _road(300, _lane_y, width - 300, _lane_y, rwidth=40, seed=20 + _lane_y, amp=54)
            _lane_ys.append(_lane_y)

    # Re-stamp paved streets after all dirt lanes so dirt never overwrites
    # cobbles at crossings.
    for _pp_pts, _pp_w, _pp_seed in _paved_specs:
        _stamp_road_pts(_pp_pts, _pp_w, _pp_seed, paved=True, record=False)

    def _on_road(px: int, py: int) -> bool:
        """Return True if (px, py) falls on any road rectangle."""
        for _rr in _road_rects:
            if _rr.collidepoint(px, py):
                return True
        return False

    # ═══════════════════════════════════════════════════════════════════
    # CENTRAL COBBLESTONE PLAZA — small square around the arena/town center
    # ═══════════════════════════════════════════════════════════════════
    _plaza_core = pygame.Rect(center_x - 700, HORIZON_Y + 1600, 1400, 900)
    _sq_rng = random.Random(8181)
    _sq_cx, _sq_cy = _plaza_core.centerx, _plaza_core.centery
    # cobble slab + worn pavement
    pygame.draw.rect(scene, (98, 95, 90), _plaza_core, border_radius=42)
    draw_cobblestones(scene, _plaza_core.inflate(-10, -10), seed=12)
    # eroded edges — earth bites into the pavement rim, stray setts kicked loose
    for _ in range(150):
        _u = _sq_rng.random()
        if _sq_rng.random() < 0.5:   # top/bottom edge
            _bx2 = _plaza_core.left + int(_plaza_core.w * _u)
            _by2 = _plaza_core.top if _sq_rng.random() < 0.5 else _plaza_core.bottom
        else:                        # left/right edge
            _bx2 = _plaza_core.left if _sq_rng.random() < 0.5 else _plaza_core.right
            _by2 = _plaza_core.top + int(_plaza_core.h * _u)
        _bw2 = _sq_rng.randint(14, 44)
        _bh2 = _sq_rng.randint(8, 20)
        _bs2 = pygame.Surface((_bw2, _bh2), pygame.SRCALPHA)
        pygame.draw.ellipse(_bs2, (104, 90, 66, _sq_rng.randint(140, 220)), (0, 0, _bw2, _bh2))
        scene.blit(_bs2, (_bx2 - _bw2 // 2, _by2 - _bh2 // 2))
    for _ in range(70):              # loose cobbles scattered just outside
        _a2 = _sq_rng.uniform(0, math.tau)
        _lx2 = _sq_cx + int(math.cos(_a2) * (_plaza_core.w // 2 + _sq_rng.randint(14, 70)))
        _ly2 = _sq_cy + int(math.sin(_a2) * (_plaza_core.h // 2 + _sq_rng.randint(10, 56)))
        _sv2 = _sq_rng.randint(0, 18)
        pygame.draw.ellipse(scene, (96 + _sv2, 94 + _sv2, 88 + _sv2), (_lx2, _ly2, _sq_rng.randint(4, 8), _sq_rng.randint(3, 5)))
        pygame.draw.ellipse(scene, (70 + _sv2, 68 + _sv2, 64 + _sv2), (_lx2, _ly2, _sq_rng.randint(4, 8), _sq_rng.randint(3, 5)), 1)
    # traffic wear — darker trodden lanes from each entry toward the centre
    for _ex2, _ey2 in ((_sq_cx, _plaza_core.top), (_sq_cx, _plaza_core.bottom),
                       (_plaza_core.left, _road_y_m), (_plaza_core.right, _road_y_m)):
        for _ in range(70):
            _t2 = _sq_rng.random()
            _wx2 = _ex2 + (_sq_cx - _ex2) * _t2 + _sq_rng.randint(-40, 40)
            _wy2 = _ey2 + (_sq_cy - _ey2) * _t2 + _sq_rng.randint(-26, 26)
            _ws2 = pygame.Surface((30, 12), pygame.SRCALPHA)
            pygame.draw.ellipse(_ws2, (52, 48, 42, _sq_rng.randint(16, 30)), (0, 0, 30, 12))
            scene.blit(_ws2, (int(_wx2) - 15, int(_wy2) - 6))
    # grime between setts + straw wisps blown across the pavement
    for _ in range(380):
        _gx2 = _sq_rng.randint(_plaza_core.left + 12, _plaza_core.right - 12)
        _gy2 = _sq_rng.randint(_plaza_core.top + 12, _plaza_core.bottom - 12)
        _gs2 = pygame.Surface((_sq_rng.randint(3, 9), _sq_rng.randint(2, 5)), pygame.SRCALPHA)
        _gs2.fill((58, 54, 46, _sq_rng.randint(22, 50)))
        scene.blit(_gs2, (_gx2, _gy2))
    for _ in range(90):
        _sx2 = _sq_rng.randint(_plaza_core.left + 30, _plaza_core.right - 30)
        _sy2 = _sq_rng.randint(_plaza_core.top + 30, _plaza_core.bottom - 30)
        _sa2 = _sq_rng.uniform(0, math.pi)
        pygame.draw.line(scene, _sq_rng.choice([(168, 146, 84), (148, 128, 70), (184, 162, 96)]),
                         (_sx2, _sy2), (_sx2 + int(7 * math.cos(_sa2)), _sy2 + int(3 * math.sin(_sa2))), 1)
    # ── market WELL on the square's west half (the centre belongs to the
    # merchant's stand, which is drawn at runtime on the shop anchor) ──
    _well_x, _well_y = _sq_cx - 300, _sq_cy + 40
    # pale polished ring where feet circle the well
    _ring = pygame.Surface((300, 170), pygame.SRCALPHA)
    pygame.draw.ellipse(_ring, (132, 128, 120, 34), (0, 0, 300, 170))
    pygame.draw.ellipse(_ring, (0, 0, 0, 0), (52, 34, 196, 102))
    scene.blit(_ring, (_well_x - 150, _well_y - 85))
    _reg("well", _well_x, _well_y)
    if not _deleted("well", _well_x, _well_y):
        _sq_well_r = draw_well(scene, _well_x, _well_y)
        obstacles.append(_sq_well_r.inflate(-24, -56))

    # ── MARKET CROSS — stepped stone base, shaft and cross head ──
    _mc_x, _mc_y = _sq_cx - 80, _sq_cy - 250
    _reg("market_cross", _mc_x, _mc_y)
    if not _deleted("market_cross", _mc_x, _mc_y):
        _mcs = pygame.Surface((130, 40), pygame.SRCALPHA)
        pygame.draw.ellipse(_mcs, (16, 11, 8, 60), (0, 6, 130, 30))
        scene.blit(_mcs, (_mc_x - 60, _mc_y - 14))
        for _stw, _sth, _sty_off, _sv in ((112, 30, 0, 0), (84, 24, -14, 12), (58, 19, -26, 22)):
            _sr = pygame.Rect(_mc_x - _stw // 2, _mc_y - _sth // 2 + _sty_off, _stw, _sth)
            pygame.draw.ellipse(scene, (74 + _sv, 72 + _sv, 68 + _sv), _sr.move(0, 3))   # riser
            pygame.draw.ellipse(scene, (108 + _sv, 105 + _sv, 99 + _sv), _sr)            # tread
            pygame.draw.arc(scene, (134 + _sv, 131 + _sv, 124 + _sv), _sr, math.pi * 0.2, math.pi * 0.9, 2)
        for _mi in range(5):   # moss + wear flecks on the steps
            pygame.draw.ellipse(scene, (86, 100, 58),
                                (_mc_x + _sq_rng.randint(-46, 40), _mc_y + _sq_rng.randint(-6, 12),
                                 _sq_rng.randint(3, 7), 2))
        _sh_top = _mc_y - 100
        for _ci in range(7):   # tapered shaft, lit from the left
            _cv = 118 - _ci * 9
            pygame.draw.line(scene, (_cv, _cv - 2, _cv - 6),
                             (_mc_x - 3 + _ci, _mc_y - 32), (_mc_x - 2 + _ci, _sh_top), 1)
        pygame.draw.line(scene, (60, 58, 54), (_mc_x + 4, _mc_y - 32), (_mc_x + 4, _sh_top), 1)
        pygame.draw.rect(scene, (104, 101, 95), (_mc_x - 3, _sh_top - 26, 7, 28))         # cross upright
        pygame.draw.rect(scene, (104, 101, 95), (_mc_x - 13, _sh_top - 18, 27, 7))        # cross arms
        pygame.draw.rect(scene, (134, 131, 124), (_mc_x - 13, _sh_top - 18, 27, 2))       # sunlit top arm
        pygame.draw.rect(scene, (134, 131, 124), (_mc_x - 3, _sh_top - 26, 2, 28))
        pygame.draw.rect(scene, (52, 50, 47), (_mc_x - 13, _sh_top - 18, 27, 7), 1)
        obstacles.append(pygame.Rect(_mc_x - 56, _mc_y - 22, 112, 50))

    # ── STALL ROWS east of the centre + square furniture (two tidy pairs —
    # the merchant's own stand at the centre carries the rest of the trade) ──
    for _si2, (_stx2, _sty2) in enumerate((
            (_sq_cx + 230, _sq_cy - 120), (_sq_cx + 430, _sq_cy - 120),
            (_sq_cx + 230, _sq_cy + 90), (_sq_cx + 430, _sq_cy + 90))):
        _reg("market_stall", _stx2, _sty2)
        if not _deleted("market_stall", _stx2, _sty2):
            _st_r2 = draw_market_stall(scene, _stx2, _sty2, 1.0 + (_si2 % 3) * 0.05)
            obstacles.append(_st_r2.inflate(-8, -8))
    _reg("market_cart", _sq_cx - 360, _sq_cy + 230)
    if not _deleted("market_cart", _sq_cx - 360, _sq_cy + 230):
        obstacles.append(draw_market_cart(scene, _sq_cx - 360, _sq_cy + 230, 1.0).inflate(-8, -8))
    _reg("notice", _sq_cx - 560, _sq_cy - 240)
    if not _deleted("notice", _sq_cx - 560, _sq_cy - 240):
        obstacles.append(draw_notice_board(scene, _sq_cx - 560, _sq_cy - 240))
    for _hx2, _hy2 in ((_sq_cx + 480, _sq_cy - 250),):
        _reg("hd_hay", _hx2, _hy2)
        if not _deleted("hd_hay", _hx2, _hy2):
            obstacles.append(draw_hd_hay(scene, _hx2, _hy2).inflate(-4, -4))
    for _bx3, _by3 in ((_sq_cx + 120, _sq_cy + 240),):
        _reg("hd_barrel", _bx3, _by3)
        if not _deleted("hd_barrel", _bx3, _by3):
            obstacles.append(draw_hd_barrel(scene, _bx3, _by3).inflate(-4, -4))

    # Church drawn AFTER roads — overlay for transparency
    _church_saved = load_church_position()
    _church_cx = int(_church_saved[0]) if _church_saved else center_x
    _church_by = int(_church_saved[1]) if _church_saved else HORIZON_Y + 286
    _reg("church", _church_cx, _church_by)
    _church_overlay = None
    if not _deleted("church", _church_cx, _church_by):
        _ch2_ov_w = 600; _ch2_ov_h = 700; _ch2_pad = 60
        _ch2_vl = _church_cx - _ch2_ov_w // 2 - _ch2_pad
        _ch2_vt = _church_by - _ch2_ov_h - _ch2_pad
        _ch2_vr = _church_cx + _ch2_ov_w // 2 + _ch2_pad
        _ch2_vb = _church_by + _ch2_pad
        _ch2_vw, _ch2_vh = _ch2_vr - _ch2_vl, _ch2_vb - _ch2_vt
        _ch2_vis = pygame.Rect(_ch2_vl, _ch2_vt, _ch2_vw, _ch2_vh)
        _ch2_surf = pygame.Surface((_ch2_vw, _ch2_vh), pygame.SRCALPHA)
        church_rect = draw_church(_ch2_surf, _church_cx - _ch2_vl, _church_by - _ch2_vt)
        _ch2_world = pygame.Rect(church_rect.x + _ch2_vl, church_rect.y + _ch2_vt,
                                  church_rect.w, church_rect.h)
        obstacles.append(_ch2_world.inflate(-124, -92))
        _ch2_arch_local = _ch2_surf.get_bounding_rect(min_alpha=128)
        if _ch2_arch_local.w <= 0 or _ch2_arch_local.h <= 0:
            _ch2_arch_local = _ch2_surf.get_bounding_rect()
        _church_overlay = (_ch2_surf, _ch2_vis, _ch2_world, "church", _ch2_arch_local)

    # ═══════════════════════════════════════════════════════════════════
    # GREEN SPACES — parks, gardens, meadows with rich visual detail
    # ═══════════════════════════════════════════════════════════════════
    _park_zones = [
        pygame.Rect(center_x - 2200, HORIZON_Y + 1000, 600, 400),
        pygame.Rect(center_x + 600, HORIZON_Y + 1000, 600, 400),
        # (kept clear of the market square — _plaza_core spans center_x±700)
        pygame.Rect(center_x - 1300, HORIZON_Y + 1700, 400, 300),
        pygame.Rect(center_x + 900, HORIZON_Y + 1700, 400, 300),
        pygame.Rect(center_x - 3200, HORIZON_Y + 2800, 500, 350),
        pygame.Rect(center_x + 2800, HORIZON_Y + 2800, 500, 350),
        pygame.Rect(1200, HORIZON_Y + 4200, 500, 300),
        pygame.Rect(7800, HORIZON_Y + 4200, 500, 300),
        pygame.Rect(center_x - 1800, HORIZON_Y + 4800, 400, 250),
        pygame.Rect(center_x + 1400, HORIZON_Y + 4800, 400, 250),
        # Extra parks for better coverage
        pygame.Rect(center_x - 600, HORIZON_Y + 3400, 450, 300),
        pygame.Rect(center_x + 1800, HORIZON_Y + 3400, 400, 280),
        pygame.Rect(center_x - 1200, HORIZON_Y + 5200, 350, 250),
        pygame.Rect(center_x + 2400, HORIZON_Y + 4400, 400, 280),
    ]
    _park_rng = random.Random(88)

    def _draw_grass_tuft(sx, sy, sz):
        """Draw a detailed grass tuft with curved blades, varied thickness, and seed heads."""
        blade_count = _park_rng.randint(6, 12)
        for _ in range(blade_count):
            bx = sx + _park_rng.randint(-sz, sz)
            blade_h = _park_rng.randint(sz, sz * 3)
            curve = _park_rng.uniform(-5, 5)
            thickness = _park_rng.choice([1, 1, 1, 2])
            gc = (36 + _park_rng.randint(0, 32), 64 + _park_rng.randint(0, 38), 26 + _park_rng.randint(0, 18))
            # Draw blade in 2 segments for curve
            mid_x = bx + int(curve * 0.5)
            mid_y = sy - blade_h // 2
            tip_x = bx + int(curve)
            tip_y = sy - blade_h
            pygame.draw.line(scene, gc, (bx, sy), (mid_x, mid_y), thickness)
            # Lighter tip
            tip_c = (min(255, gc[0] + 18), min(255, gc[1] + 22), min(255, gc[2] + 10))
            pygame.draw.line(scene, tip_c, (mid_x, mid_y), (tip_x, tip_y), 1)
        # Occasional seed head on tallest blade
        if _park_rng.random() > 0.6:
            sh = _park_rng.randint(sz * 2, sz * 3)
            stx = sx + _park_rng.randint(-2, 2)
            sty = sy - sh
            pygame.draw.circle(scene, (130, 118, 72), (stx, sty), _park_rng.randint(1, 2))
        # Small base shadow
        pygame.draw.ellipse(scene, (30, 44, 28), (sx - sz, sy - 1, sz * 2, 3))

    def _draw_wildflower(sx, sy):
        """Draw a detailed wildflower — species-varied with petals, center, leaves."""
        stem_h = _park_rng.randint(6, 14)
        stem_curve = _park_rng.randint(-3, 3)
        stem_c = (38 + _park_rng.randint(0, 18), 68 + _park_rng.randint(0, 22), 28 + _park_rng.randint(0, 8))
        # Draw curved stem
        mid_x = sx + stem_curve // 2
        mid_y = sy - stem_h // 2
        tip_x = sx + stem_curve
        tip_y = sy - stem_h
        pygame.draw.line(scene, stem_c, (sx, sy), (mid_x, mid_y), 1)
        pygame.draw.line(scene, stem_c, (mid_x, mid_y), (tip_x, tip_y), 1)
        # Small leaf on stem
        if stem_h > 7:
            ly = sy - stem_h // 2 + _park_rng.randint(-1, 1)
            lside = _park_rng.choice([-1, 1])
            lx = mid_x + lside * _park_rng.randint(2, 4)
            pygame.draw.line(scene, stem_c, (mid_x, ly), (lx, ly - 1), 1)
            pygame.draw.circle(scene, (stem_c[0] + 6, stem_c[1] + 8, stem_c[2] + 2), (lx, ly - 1), 1)
        # Flower head — different species
        species = _park_rng.randint(0, 4)
        if species == 0:
            # Daisy — white petals + yellow center
            petals = _park_rng.randint(5, 8)
            pr = _park_rng.randint(2, 4)
            for pi in range(petals):
                pa = pi * (math.tau / petals) + _park_rng.uniform(-0.2, 0.2)
                px = tip_x + int(math.cos(pa) * pr)
                py = tip_y + int(math.sin(pa) * pr)
                pygame.draw.circle(scene, (240, 240, 245), (px, py), max(1, pr // 2))
            pygame.draw.circle(scene, (230, 200, 50), (tip_x, tip_y), max(1, pr // 2))
        elif species == 1:
            # Poppy — red with dark center
            pr = _park_rng.randint(3, 5)
            pygame.draw.circle(scene, (200 + _park_rng.randint(0, 40), 40 + _park_rng.randint(0, 30), 30), (tip_x, tip_y), pr)
            pygame.draw.circle(scene, (40, 30, 30), (tip_x, tip_y), max(1, pr - 2))
        elif species == 2:
            # Bluebell — drooping bell shape
            pygame.draw.ellipse(scene, (80 + _park_rng.randint(0, 30), 90 + _park_rng.randint(0, 30), 200 + _park_rng.randint(0, 40)),
                                (tip_x - 2, tip_y, 5, 4))
            pygame.draw.line(scene, (100, 120, 220), (tip_x, tip_y), (tip_x - 1, tip_y + 3), 1)
        elif species == 3:
            # Buttercup — small golden
            pr = _park_rng.randint(2, 3)
            petals = 5
            for pi in range(petals):
                pa = pi * (math.tau / petals)
                px = tip_x + int(math.cos(pa) * pr)
                py = tip_y + int(math.sin(pa) * pr)
                pygame.draw.circle(scene, (240, 210, 40), (px, py), 1)
            pygame.draw.circle(scene, (255, 230, 80), (tip_x, tip_y), 1)
        else:
            # Lavender — small purple spike
            for li in range(3):
                pygame.draw.circle(scene, (160 + _park_rng.randint(0, 30), 80 + _park_rng.randint(0, 20), 180 + _park_rng.randint(0, 40)),
                                   (tip_x, tip_y - li * 2), 1)

    def _draw_bush(sx, sy, bw, bh):
        """Draw a detailed bush with visible branches, leaf clusters, berries, and depth."""
        # Ground shadow
        shad = pygame.Surface((bw + 10, bh // 2 + 6), pygame.SRCALPHA)
        pygame.draw.ellipse(shad, (0, 0, 0, 28), shad.get_rect())
        scene.blit(shad, (sx - 5, sy + bh // 2 - 3))
        # Visible branch structure underneath
        trunk_x = sx + bw // 2
        trunk_y = sy + bh
        for _ in range(_park_rng.randint(3, 5)):
            bx2 = trunk_x + _park_rng.randint(-bw // 3, bw // 3)
            by2 = sy + _park_rng.randint(0, bh // 3)
            bc = (52 + _park_rng.randint(-6, 6), 40 + _park_rng.randint(-4, 4), 30)
            pygame.draw.line(scene, bc, (trunk_x, trunk_y - 2), (bx2, by2), _park_rng.randint(1, 2))
        # Multi-layer foliage with depth — 5 layers
        for li in range(5):
            lw = max(4, bw - li * 4 + _park_rng.randint(-3, 3))
            lh = max(4, bh - li * 3 + _park_rng.randint(-2, 2))
            lx = sx + li * 2 + _park_rng.randint(-2, 2)
            ly = sy + li * 1 + _park_rng.randint(-1, 1)
            g_base = 28 + li * 9
            gc = (g_base + _park_rng.randint(-4, 8),
                  g_base + 30 + _park_rng.randint(-6, 12),
                  g_base + 2 + _park_rng.randint(-2, 4))
            pygame.draw.ellipse(scene, gc, (lx, ly, lw, lh))
        # Individual leaf cluster bumps on surface
        for _ in range(_park_rng.randint(6, 12)):
            lx = sx + _park_rng.randint(3, max(4, bw - 3))
            ly = sy + _park_rng.randint(2, max(3, bh - 2))
            lr = _park_rng.randint(2, max(3, min(6, bw // 5)))
            g = 44 + _park_rng.randint(0, 24)
            pygame.draw.circle(scene, (g, g + 26 + _park_rng.randint(0, 10), g - 2), (lx, ly), lr)
        # Highlight specks (sunlit leaves)
        for _ in range(_park_rng.randint(4, 8)):
            hx = sx + _park_rng.randint(4, max(5, bw - 4))
            hy = sy + _park_rng.randint(2, max(3, bh // 2))
            pygame.draw.circle(scene, (72 + _park_rng.randint(0, 24), 104 + _park_rng.randint(0, 24), 52 + _park_rng.randint(0, 10)),
                               (hx, hy), 1)
        # Shadow depth on bottom
        for _ in range(_park_rng.randint(2, 4)):
            dx = sx + _park_rng.randint(2, max(3, bw - 2))
            dy = sy + _park_rng.randint(max(1, bh // 2), max(2, bh - 2))
            pygame.draw.circle(scene, (24 + _park_rng.randint(0, 8), 38 + _park_rng.randint(0, 8), 20), (dx, dy), _park_rng.randint(1, 3))
        # Berries on some bushes
        if _park_rng.random() > 0.55:
            berry_c = _park_rng.choice([(180, 40, 40), (60, 40, 120), (200, 140, 40), (40, 40, 60)])
            for _ in range(_park_rng.randint(3, 7)):
                bx2 = sx + _park_rng.randint(3, max(4, bw - 3))
                by2 = sy + _park_rng.randint(bh // 4, max(bh // 4 + 1, bh - 4))
                pygame.draw.circle(scene, berry_c, (bx2, by2), _park_rng.randint(1, 2))
                pygame.draw.circle(scene, (min(255, berry_c[0] + 50), min(255, berry_c[1] + 50), min(255, berry_c[2] + 50)),
                                   (bx2, by2 - 1), 1)
        # Edge outline for definition
        pygame.draw.ellipse(scene, (22 + _park_rng.randint(0, 6), 36 + _park_rng.randint(0, 8), 18),
                            (sx, sy, bw, bh), 1)

    def _draw_hedgerow(sx, sy, length, vertical=False):
        """Draw a detailed trimmed hedgerow with leaf texture, branch structure, and flower buds."""
        step = 8
        if vertical:
            # Shadow strip
            shad = pygame.Surface((22, length + 4), pygame.SRCALPHA)
            pygame.draw.rect(shad, (0, 0, 0, 18), shad.get_rect(), border_radius=4)
            scene.blit(shad, (sx + 6, sy + 2))
            # Base darker layer
            for hi in range(0, length, step):
                hw = _park_rng.randint(14, 20)
                hh = _park_rng.randint(8, 12)
                gc_dark = (28 + _park_rng.randint(0, 6), 48 + _park_rng.randint(0, 8), 24)
                pygame.draw.ellipse(scene, gc_dark, (sx - hw // 2 - 1, sy + hi - 1, hw + 2, hh + 2))
            # Main foliage layer
            for hi in range(0, length, step):
                hw = _park_rng.randint(12, 18)
                hh = _park_rng.randint(8, 12)
                gc = (36 + _park_rng.randint(0, 12), 62 + _park_rng.randint(0, 14), 30 + _park_rng.randint(0, 6))
                pygame.draw.ellipse(scene, gc, (sx - hw // 2, sy + hi, hw, hh))
                # Leaf texture bumps
                for _ in range(_park_rng.randint(2, 4)):
                    lx = sx + _park_rng.randint(-hw // 3, hw // 3)
                    ly = sy + hi + _park_rng.randint(1, max(2, hh - 2))
                    lg = gc[1] + _park_rng.randint(-8, 12)
                    pygame.draw.circle(scene, (gc[0] + _park_rng.randint(-4, 6), min(255, lg), gc[2] + _park_rng.randint(-2, 4)),
                                       (lx, ly), _park_rng.randint(1, 3))
                # Top edge highlight
                pygame.draw.arc(scene, (min(255, gc[0] + 16), min(255, gc[1] + 18), min(255, gc[2] + 10)),
                                (sx - hw // 2, sy + hi, hw, hh), 0, math.pi, 1)
                # Outline
                pygame.draw.ellipse(scene, (gc[0] - 10, gc[1] - 10, max(0, gc[2] - 8)),
                                    (sx - hw // 2, sy + hi, hw, hh), 1)
            # Occasional flower buds
            if _park_rng.random() > 0.5:
                fc = _park_rng.choice([(220, 220, 240), (240, 200, 200), (200, 220, 180)])
                for _ in range(_park_rng.randint(2, 5)):
                    fx = sx + _park_rng.randint(-6, 6)
                    fy = sy + _park_rng.randint(0, length)
                    pygame.draw.circle(scene, fc, (fx, fy), 1)
        else:
            # Shadow strip
            shad = pygame.Surface((length + 4, 22), pygame.SRCALPHA)
            pygame.draw.rect(shad, (0, 0, 0, 18), shad.get_rect(), border_radius=4)
            scene.blit(shad, (sx + 2, sy + 6))
            # Base darker layer
            for hi in range(0, length, step):
                hw = _park_rng.randint(8, 12)
                hh = _park_rng.randint(14, 20)
                gc_dark = (28 + _park_rng.randint(0, 6), 48 + _park_rng.randint(0, 8), 24)
                pygame.draw.ellipse(scene, gc_dark, (sx + hi - 1, sy - hh // 2 - 1, hw + 2, hh + 2))
            # Main foliage layer
            for hi in range(0, length, step):
                hw = _park_rng.randint(8, 12)
                hh = _park_rng.randint(12, 18)
                gc = (36 + _park_rng.randint(0, 12), 62 + _park_rng.randint(0, 14), 30 + _park_rng.randint(0, 6))
                pygame.draw.ellipse(scene, gc, (sx + hi, sy - hh // 2, hw, hh))
                # Leaf texture bumps
                for _ in range(_park_rng.randint(2, 4)):
                    lx = sx + hi + _park_rng.randint(1, max(2, hw - 2))
                    ly = sy + _park_rng.randint(-hh // 3, hh // 3)
                    lg = gc[1] + _park_rng.randint(-8, 12)
                    pygame.draw.circle(scene, (gc[0] + _park_rng.randint(-4, 6), min(255, lg), gc[2] + _park_rng.randint(-2, 4)),
                                       (lx, ly), _park_rng.randint(1, 3))
                # Top edge highlight
                pygame.draw.arc(scene, (min(255, gc[0] + 16), min(255, gc[1] + 18), min(255, gc[2] + 10)),
                                (sx + hi, sy - hh // 2, hw, hh), 0, math.pi, 1)
                # Outline
                pygame.draw.ellipse(scene, (gc[0] - 10, gc[1] - 10, max(0, gc[2] - 8)),
                                    (sx + hi, sy - hh // 2, hw, hh), 1)
            # Occasional flower buds
            if _park_rng.random() > 0.5:
                fc = _park_rng.choice([(220, 220, 240), (240, 200, 200), (200, 220, 180)])
                for _ in range(_park_rng.randint(2, 5)):
                    fx = sx + _park_rng.randint(0, length)
                    fy = sy + _park_rng.randint(-6, 6)
                    pygame.draw.circle(scene, fc, (fx, fy), 1)

    for _pz in _park_zones:
        _reg("green_patch", _pz.centerx, _pz.centery)
        if not _deleted("green_patch", _pz.centerx, _pz.centery):
            # ── Multi-layer grass base ──
            # Outer soft edge
            # Textured vegetation stamps (avoid a clean green ellipse)
            _patch_count = max(6, (_pz.width * _pz.height) // 15000)
            for _ in range(_patch_count):
                ang = _park_rng.random() * math.tau
                rr = math.sqrt(_park_rng.random())
                _gx = _pz.centerx + int(math.cos(ang) * rr * (_pz.width * 0.48))
                _gy = _pz.centery + int(math.sin(ang) * rr * (_pz.height * 0.48))
                _pw = _park_rng.randint(max(70, _pz.width // 7), max(80, min(180, _pz.width // 2)))
                _ph = _park_rng.randint(max(38, _pz.height // 7), max(46, min(120, _pz.height // 2)))
                _ps = pygame.Surface((_pw + 24, _ph + 24), pygame.SRCALPHA)
                draw_grass_patch(
                    _ps,
                    _ps.get_width() // 2,
                    _ps.get_height() // 2,
                    _pw,
                    _ph,
                    seed=_park_rng.randint(0, 1_000_000_000),
                    outline=False,
                )
                scene.blit(_ps, (_gx - _ps.get_width() // 2, _gy - _ps.get_height() // 2))

            # ── Grass tufts scattered across park ──
            if _pz.width > 20 and _pz.height > 20:
                for _ in range(_pz.width * _pz.height // 3000):
                    _tx = _park_rng.randint(_pz.left + 10, max(_pz.left + 10, _pz.right - 10))
                    _ty = _park_rng.randint(_pz.top + 10, max(_pz.top + 10, _pz.bottom - 10))
                    _draw_grass_tuft(_tx, _ty, _park_rng.randint(2, 5))

            # ── Wildflower clusters ──
            if _pz.width > 40 and _pz.height > 30:
                n_clusters = _park_rng.randint(3, 6)
                for _ in range(n_clusters):
                    _cx = _park_rng.randint(_pz.left + 20, max(_pz.left + 20, _pz.right - 20))
                    _cy = _park_rng.randint(_pz.top + 15, max(_pz.top + 15, _pz.bottom - 15))
                    for _fi in range(_park_rng.randint(4, 10)):
                        _fx = _cx + _park_rng.randint(-18, 18)
                        _fy = _cy + _park_rng.randint(-10, 10)
                        _draw_wildflower(_fx, _fy)

            # ── Bushes along park edges ──
            for _ in range(_park_rng.randint(2, 5)):
                _edge = _park_rng.choice(["top", "bottom", "left", "right"])
                if _edge == "top" and _pz.width >= 60:
                    _bx = _park_rng.randint(_pz.left + 20, _pz.right - 40)
                    _by = _pz.top + _park_rng.randint(-4, 8)
                elif _edge == "bottom" and _pz.width >= 60:
                    _bx = _park_rng.randint(_pz.left + 20, _pz.right - 40)
                    _by = _pz.bottom - _park_rng.randint(12, 20)
                elif _edge == "left" and _pz.height >= 30:
                    _bx = _pz.left + _park_rng.randint(-4, 8)
                    _by = _park_rng.randint(_pz.top + 10, _pz.bottom - 20)
                elif _edge == "right" and _pz.height >= 30:
                    _bx = _pz.right - _park_rng.randint(14, 22)
                    _by = _park_rng.randint(_pz.top + 10, _pz.bottom - 20)
                else:
                    continue
                _draw_bush(_bx, _by, _park_rng.randint(16, 30), _park_rng.randint(10, 18))

            # ── Park border ──
            # Natural edge: sprinkle tufts instead of a clean outline
            for _ in range(_park_rng.randint(10, 16)):
                ang = _park_rng.random() * math.tau
                _ex = _pz.centerx + int(math.cos(ang) * (_pz.width * 0.52))
                _ey = _pz.centery + int(math.sin(ang) * (_pz.height * 0.52))
                _draw_grass_tuft(_ex, _ey, _park_rng.randint(3, 6))

            # ── Hedgerow along one side of each park ──
            _hedge_side = _park_rng.choice(["top", "left"])
            if _hedge_side == "top":
                _draw_hedgerow(_pz.left + 10, _pz.top - 4, _pz.width - 20, vertical=False)
            else:
                _draw_hedgerow(_pz.left - 4, _pz.top + 10, _pz.height - 20, vertical=True)

    # ── Roadside grass strips with grass tufts and flowers ──
    for _ry in [_road_y_n, _road_y_m, _road_y_s]:
        for _sx in range(500, width - 500, 200):
            _sw = _park_rng.randint(50, 120)
            _sh = _park_rng.randint(16, 32)
            for _side, _off in [(-70, "above"), (55, "below")]:
                _sy = _ry + _side
                _reg("grass_strip", _sx, _sy)
                if not _deleted("grass_strip", _sx, _sy):
                    _gcx = _sx + _sw // 2
                    _gcy = _sy + _sh // 2
                    _gsurf = pygame.Surface((_sw + 24, _sh + 24), pygame.SRCALPHA)
                    draw_grass_patch(
                        _gsurf,
                        _gsurf.get_width() // 2,
                        _gsurf.get_height() // 2,
                        _sw,
                        _sh,
                        seed=_park_rng.randint(0, 1_000_000_000),
                        outline=False,
                    )
                    scene.blit(_gsurf, (_gcx - _gsurf.get_width() // 2, _gcy - _gsurf.get_height() // 2))
                    # Tufts on strip
                    for _ in range(_park_rng.randint(1, 3)):
                        _draw_grass_tuft(_sx + _park_rng.randint(5, _sw - 5), _sy + _sh, 2)
                    # Occasional flower
                    if _park_rng.random() > 0.6:
                        _draw_wildflower(_sx + _park_rng.randint(8, _sw - 8), _sy + _sh - 2)

    # ── Garden beds near houses with flowers ──
    for _gbx in range(400, width - 400, 400):
        for _gby_off in [plaza.top + 100, plaza.bottom - 100]:
            _reg("garden_bed", _gbx, _gby_off)
            if not _deleted("garden_bed", _gbx, _gby_off):
                _gbw = _park_rng.randint(30, 70)
                _gbh = _park_rng.randint(15, 30)
                # Soil base
                pygame.draw.ellipse(scene, (58, 48, 36), (_gbx, _gby_off, _gbw, _gbh))
                # Planted flowers
                for _fbi in range(_park_rng.randint(3, 7)):
                    _fbx = _gbx + _park_rng.randint(4, _gbw - 4)
                    _fby = _gby_off + _gbh
                    _draw_wildflower(_fbx, _fby)
                # Edge stones
                pygame.draw.ellipse(scene, (68, 62, 52), (_gbx, _gby_off, _gbw, _gbh), 1)

    # ── Scattered bushes and tufts along the N-S boulevard ──
    for _by_off in range(HORIZON_Y + 400, height - 500, 200):
        if _plaza_core.inflate(160, 120).collidepoint(center_x, _by_off):
            continue   # keep the market square pavement clear
        _bush_x = center_x + _park_rng.randint(-10, 10)
        _reg("boulevard_bush", _bush_x, _by_off)
        if not _deleted("boulevard_bush", _bush_x, _by_off):
            for _bside in [-110, 110]:
                if _park_rng.random() > 0.4:
                    _draw_bush(center_x + _bside + _park_rng.randint(-10, 10), _by_off, _park_rng.randint(14, 24), _park_rng.randint(8, 14))
            if _park_rng.random() > 0.5:
                _draw_grass_tuft(center_x + _park_rng.randint(-80, 80), _by_off, 3)

    # ── Gladiator Arena (center of plaza) ──
    arena_cx = center_x
    arena_cy = plaza.centery + 40
    # Giant central fire pit replaces the old arena
    _reg("giant_fire_pit", arena_cx, arena_cy)
    if not _deleted("giant_fire_pit", arena_cx, arena_cy):
        _draw_giant_fire_pit(scene, arena_cx, arena_cy)
        # Stone ring obstacle (matches new bigger outer radius 260x110)
        obstacles.append(pygame.Rect(arena_cx - 220, arena_cy - 95, 440, 190))

    _fp_x, _fp_y = CX(-400), H(480)
    _reg("fire_pit", _fp_x, _fp_y)
    if not _deleted("fire_pit", _fp_x, _fp_y):
        fire_rect = draw_fire_pit(scene, _fp_x, _fp_y)
        obstacles.append(fire_rect.inflate(-10, -10))

    _wl_x, _wl_y = CX(400), H(480)
    _reg("well", _wl_x, _wl_y)
    if not _deleted("well", _wl_x, _wl_y):
        well_rect = draw_well(scene, _wl_x, _wl_y)
        obstacles.append(well_rect.inflate(-24, -56))

    # ── Prop Helpers ────────────────────────────────────────────────────
    def _hd_cart(x: float, y: float) -> None:
        _reg("hd_cart", x, y)
        if not _deleted("hd_cart", x, y):
            obstacles.append(draw_hd_cart(scene, x, y).inflate(-10, -10))

    def _hd_hay(x: float, y: float) -> None:
        _reg("hd_hay", x, y)
        if not _deleted("hd_hay", x, y):
            obstacles.append(draw_hd_hay(scene, x, y).inflate(-4, -4))

    def _hd_barrel(x: float, y: float) -> None:
        _reg("hd_barrel", x, y)
        if not _deleted("hd_barrel", x, y):
            obstacles.append(draw_hd_barrel(scene, x, y).inflate(-4, -4))

    def _prop(kind: str, fn, x: float, y: float, *a, **kw) -> None:
        _reg(kind, x, y)
        if not _deleted(kind, x, y):
            r = fn(scene, int(x), int(y), *a, **kw)
            if isinstance(r, pygame.Rect):
                obstacles.append(r)

    def _decor(kind: str, fn, x: float, y: float, *a, **kw) -> None:
        """Non-obstacle decorative prop (no collision)."""
        _reg(kind, x, y)
        if not _deleted(kind, x, y):
            fn(scene, int(x), int(y), *a, **kw)

    def _tasset(x: float, y: float, name: str) -> None:
        kind = f"tasset_{name}"
        _reg(kind, x, y)
        if not _deleted(kind, x, y):
            obstacles.append(draw_transylvanian_asset(scene, x, y, name))

    # ── PHASE-2 CIVIC LANDMARK SITES ─────────────────────────────────────
    # Footprints reserved up-front so houses and lamps keep clear (seeded
    # into the house de-overlap pass below). The structures themselves are
    # drawn near the end of the build, after district terrain and props,
    # so nothing paints over them.
    _townhall_pos = (_sq_cx - 430, _plaza_core.top + 40)
    _windmill_pos = (1050, HORIZON_Y + 3340)
    _granary_pos = (2750, HORIZON_Y + 4480)
    _washhouse_pos = (width - 880, HORIZON_Y + 2330)
    _stocks_sq_pos = (_sq_cx - 490, _sq_cy + 60)
    _shrine_spots = ((center_x + 210, _road_y_n + 160),
                     (center_x + 230, _cemetery_pos[1] - 240),
                     (7600, HORIZON_Y + 4290))
    _south_wall_gy = height - 460          # ground line shared with the town gate
    _landmark_rects = [
        pygame.Rect(_townhall_pos[0] - 320, _townhall_pos[1] - 500, 640, 540),
        pygame.Rect(_windmill_pos[0] - 270, _windmill_pos[1] - 500, 540, 580),
        pygame.Rect(_granary_pos[0] - 190, _granary_pos[1] - 250, 380, 310),
        pygame.Rect(_washhouse_pos[0] - 210, _washhouse_pos[1] - 210, 420, 270),
        pygame.Rect(40, _south_wall_gy - 150, width - 80, 260),             # south curtain wall band
        pygame.Rect(40, wall_y + 110, 200, _south_wall_gy - wall_y - 110),  # west palisade strip
        pygame.Rect(width - 240, wall_y + 110, 200, _south_wall_gy - wall_y - 110),  # east palisade strip
    ]
    for _shx, _shy in _shrine_spots:
        _landmark_rects.append(pygame.Rect(_shx - 70, _shy - 140, 140, 170))

    # ═══════════════════════════════════════════════════════════════════
    # FIVE DISTINCT NEIGHBORHOODS — houses throughout the town
    # ═══════════════════════════════════════════════════════════════════
    # 1. Noble Quarter (NW) — large ornate houses, cobblestone, gardens
    # 2. Market District (center) — medium houses mixed with market life
    # 3. Artisan Ward (W/SW) — workshop houses, chimneys, craft props
    # 4. Harbor Row (E) — small weathered fishing houses
    # 5. Outer Slums (S near gate) — shanties, mud, broken props
    house_specs = []
    _nhood_rng = random.Random(333)

    def _blocks_shop(hx, hy, radius_x=340, radius_y=320):
        """True if house at (hx,hy) is too close to OR visually in front of any shop."""
        for sx, sy in _shop.values():
            # Standard proximity check (symmetric)
            if abs(hx - sx) < radius_x and abs(hy - sy) < radius_y:
                return True
            # Front-blocking check: house is BELOW shop (rendered in front)
            # and within horizontal range to visually overlap the shop
            dy = hy - sy  # positive = house is in front of shop
            if 0 < dy < 600 and abs(hx - sx) < 350:
                return True
        return False

    # ═══════════════════════════════════════════════════════════════════
    # DISTRICT TERRAIN SYSTEM — unique ground per district, seamless blending
    # Each district gets its own tileset + detail overlays that feather at edges
    # ═══════════════════════════════════════════════════════════════════
    _DTILE = 48  # smaller tiles for finer blending

    def _make_terrain_tile(base_rgb, var_range, pebble_rgb, grain_col, seed_val):
        """Create a procedural terrain tile with given colour palette."""
        _t = pygame.Surface((_DTILE, _DTILE))
        for _ty in range(_DTILE):
            for _tx in range(_DTILE):
                _h1 = ((_tx * 2654435761 + seed_val) ^ (_ty * 2246822519)) & 0xFFFFFFFF
                _h2 = (((_tx >> 1) * 1640531527 + seed_val) ^ ((_ty >> 1) * 2891336453)) & 0xFFFFFFFF
                _h3 = (((_tx >> 2) * 3266489917 + seed_val) ^ ((_ty >> 2) * 668265263)) & 0xFFFFFFFF
                _nf = ((_h1 >> 8) & 0xFF) / 255.0 * 0.5 + ((_h2 >> 8) & 0xFF) / 255.0 * 0.3 + ((_h3 >> 8) & 0xFF) / 255.0 * 0.2
                r = max(0, min(255, base_rgb[0] + int(_nf * var_range[0])))
                g = max(0, min(255, base_rgb[1] + int(_nf * var_range[1])))
                b = max(0, min(255, base_rgb[2] + int(_nf * var_range[2])))
                # Warm/cool patch variation
                _h4 = ((_tx * 48271 + _ty * 16807 + seed_val) >> 10) & 0xFF
                if _h4 > 200: r = min(255, r + 6); g = min(255, g + 3)
                elif _h4 < 40: g = min(255, g + 4); b = min(255, b + 3)
                _t.set_at((_tx, _ty), (r, g, b))
        _prng = random.Random(seed_val + 111)
        for _ in range(60):
            _px = _prng.randint(0, _DTILE - 1); _py = _prng.randint(0, _DTILE - 1)
            _pr = _prng.randint(1, 2)
            _pv = _prng.randint(pebble_rgb[0], pebble_rgb[1])
            pygame.draw.circle(_t, (_pv, max(0, _pv - 4), max(0, _pv - 10)), (_px, _py), _pr)
        for _ in range(20):
            _lx = _prng.randint(0, _DTILE - 1); _ly = _prng.randint(0, _DTILE - 1)
            _lx2 = _lx + _prng.randint(-5, 5); _ly2 = _ly + _prng.randint(-5, 5)
            pygame.draw.line(_t, grain_col, (_lx, _ly), (_lx2, _ly2), 1)
        return _t

    # ── Build terrain tile sets for each district ──
    # (Lifted to match the warm mid-tone base ground — the old 40-64 bases
    # painted the whole town back to mud-black over the bright base layer.)
    # Noble: clean swept stone — pale grey-blue
    _noble_tiles = [_make_terrain_tile((106, 108, 114), (26, 24, 22), (118, 142), (86, 84, 80), 5000 + i * 777) for i in range(3)]
    # Market/Saint: worn warm cobble dust — sandy grey
    _saint_tiles = [_make_terrain_tile((104, 100, 92), (30, 28, 24), (110, 134), (80, 76, 70), 6000 + i * 777) for i in range(3)]
    # Artisan: packed ochre clay — warm earth tones
    _artisan_tiles = [_make_terrain_tile((102, 88, 64), (32, 28, 22), (102, 126), (74, 64, 48), 7000 + i * 777) for i in range(3)]
    # Harbor: sandy gravel — pale tan/beige
    _harbor_tiles = [_make_terrain_tile((116, 108, 88), (24, 26, 24), (114, 138), (92, 84, 70), 8000 + i * 777) for i in range(3)]
    # Shanty: churned mud — darkest district, but still readable
    _shanty_tiles = [_make_terrain_tile((84, 72, 54), (24, 22, 18), (78, 100), (62, 53, 40), 9000 + i * 777) for i in range(3)]
    # Ember/Rook: packed earth with ash — grey-brown
    _ember_tiles = [_make_terrain_tile((96, 90, 80), (28, 26, 24), (98, 122), (70, 66, 58), 10000 + i * 777) for i in range(3)]

    _district_tilesets = {
        'noble': _noble_tiles, 'saint': _saint_tiles, 'artisan': _artisan_tiles,
        'harbor': _harbor_tiles, 'shanty': _shanty_tiles, 'ember': _ember_tiles,
        'rook': _ember_tiles,
    }

    # ═══════════════════════════════════════════════════════════════════
    # DISTRICT ZONE DEFINITIONS (medieval castle layout)
    # Inner keep → market district → wards radiate outward
    # ═══════════════════════════════════════════════════════════════════

    # ── 1. NOBLE QUARTER — northwest, walled estate area ──
    _noble_zone = pygame.Rect(center_x - 4200, HORIZON_Y + 350, 2600, 1600)

    # ── 2. MARKET DISTRICT — central ring around the plaza ──
    _market_zone_l = pygame.Rect(center_x - 1800, HORIZON_Y + 900, 1200, 2000)
    _market_zone_r = pygame.Rect(center_x + 600, HORIZON_Y + 900, 1200, 2000)

    # ── 3. ARTISAN WARD — west side, workshops ──
    _artisan_zone = pygame.Rect(center_x - 4400, HORIZON_Y + 2100, 2400, 2400)

    # ── 4. HARBOR ROW — east, docks & fishing ──
    _harbor_zone = pygame.Rect(center_x + 2200, HORIZON_Y + 900, 2200, 2200)

    # ── 5. OUTER SLUMS — south outskirts ──
    _slum_zone_l = pygame.Rect(center_x - 3000, HORIZON_Y + 4600, 2400, 1600)
    _slum_zone_r = pygame.Rect(center_x + 600, HORIZON_Y + 4600, 2400, 1600)

    # ── 6. EMBER/ROOK — mid-south fill ──
    _mse_zone = pygame.Rect(center_x - 2000, HORIZON_Y + 2900, 6800, 1200)
    _fse_zone = pygame.Rect(center_x + 2500, HORIZON_Y + 3200, 2400, 1400)
    _cs_zone = pygame.Rect(center_x - 2000, HORIZON_Y + 4100, 4000, 600)

    # All zones with their district type for terrain painting
    _all_zones = [
        (_noble_zone, 'noble'), (_market_zone_l, 'saint'), (_market_zone_r, 'saint'),
        (_artisan_zone, 'artisan'), (_harbor_zone, 'harbor'),
        (_slum_zone_l, 'shanty'), (_slum_zone_r, 'shanty'),
        (_mse_zone, 'ember'), (_fse_zone, 'harbor'), (_cs_zone, 'ember'),
    ]

    # ── Paint district terrain tiles with feathered edges ──
    _blend_margin = 120  # pixels of soft blending at zone edges
    for _zone, _dtype in _all_zones:
        _tiles = _district_tilesets.get(_dtype, _ember_tiles)
        _exp = _zone.inflate(60, 60)  # slight overpaint for overlap
        for _ty in range(_exp.top, _exp.bottom, _DTILE):
            for _tx in range(_exp.left, _exp.right, _DTILE):
                if _tx < 0 or _ty < HORIZON_Y or _tx >= width or _ty >= height:
                    continue
                _ti = ((_tx // _DTILE) * 3 + (_ty // _DTILE) * 7) % 3
                # Compute feather alpha based on distance from zone edge
                _dx = min(_tx - _zone.left, _zone.right - _tx - _DTILE)
                _dy = min(_ty - _zone.top, _zone.bottom - _ty - _DTILE)
                _edge_dist = min(_dx, _dy)
                if _edge_dist < -40:
                    continue
                if _edge_dist < _blend_margin:
                    _alpha = max(20, min(255, int(255 * (_edge_dist + 40) / (_blend_margin + 40))))
                else:
                    _alpha = 255
                if _alpha >= 250:
                    scene.blit(_tiles[_ti], (_tx, _ty))
                else:
                    _tmp = _tiles[_ti].copy()
                    _tmp.set_alpha(_alpha)
                    scene.blit(_tmp, (_tx, _ty))

    # ── District-specific detail overlays ──
    _dtrng = random.Random(5555)

    # NOBLE: polished stone kerbs, garden borders, decorative tiles
    for _ in range(120):
        _nx = _dtrng.randint(_noble_zone.left + 60, _noble_zone.right - 60)
        _ny = _dtrng.randint(_noble_zone.top + 60, _noble_zone.bottom - 60)
        if _on_road(_nx, _ny): continue
        _sv = 72 + _dtrng.randint(-6, 8)
        _sw = _dtrng.randint(8, 18); _sh = _dtrng.randint(6, 12)
        pygame.draw.rect(scene, (_sv, _sv + 2, _sv + 6), (_nx, _ny, _sw, _sh))
        pygame.draw.rect(scene, (_sv - 16, _sv - 14, _sv - 10), (_nx, _ny, _sw, _sh), 1)
    # Noble: decorative stone borders every ~400px
    for _bx in range(_noble_zone.left + 100, _noble_zone.right - 100, 380):
        _by = _noble_zone.top + 200 + _dtrng.randint(-30, 30)
        for _si in range(16):
            _sv = 66 + _dtrng.randint(-4, 6)
            pygame.draw.rect(scene, (_sv, _sv, _sv + 4),
                             (_bx + _si * 14, _by, 12, 8))
            pygame.draw.rect(scene, (42, 42, 46), (_bx + _si * 14, _by, 12, 8), 1)

    # ARTISAN: soot marks, metal filings, clay stains
    for _ in range(200):
        _ax = _dtrng.randint(_artisan_zone.left + 40, _artisan_zone.right - 40)
        _ay = _dtrng.randint(_artisan_zone.top + 40, _artisan_zone.bottom - 40)
        if _on_road(_ax, _ay): continue
        _kind = _dtrng.randint(0, 3)
        if _kind == 0:  # soot patch
            _sr = _dtrng.randint(8, 30)
            _sa = pygame.Surface((_sr * 2, _sr), pygame.SRCALPHA)
            pygame.draw.ellipse(_sa, (24, 22, 20, _dtrng.randint(30, 80)), (0, 0, _sr * 2, _sr))
            scene.blit(_sa, (_ax - _sr, _ay - _sr // 2))
        elif _kind == 1:  # metal filing sparkle
            _sv = _dtrng.randint(80, 110)
            pygame.draw.circle(scene, (_sv, _sv - 6, _sv - 20), (_ax, _ay), _dtrng.randint(1, 3))
        elif _kind == 2:  # clay stain
            _cw = _dtrng.randint(12, 40); _ch = _dtrng.randint(6, 20)
            _cr = _dtrng.randint(0, 8)
            pygame.draw.ellipse(scene, (60 + _cr, 48 + _cr, 32 + _cr), (_ax, _ay, _cw, _ch))
        else:  # ash streak
            _al = _dtrng.randint(10, 40)
            _aang = _dtrng.uniform(-0.5, 0.5)
            pygame.draw.line(scene, (36, 34, 30),
                             (_ax, _ay), (_ax + int(_al * math.cos(_aang)), _ay + int(_al * math.sin(_aang))), 1)

    # HARBOR: shells, driftwood, rope, sand ripples
    for _ in range(180):
        _hx = _dtrng.randint(_harbor_zone.left + 40, _harbor_zone.right - 40)
        _hy = _dtrng.randint(_harbor_zone.top + 40, _harbor_zone.bottom - 40)
        if _on_road(_hx, _hy): continue
        _kind = _dtrng.randint(0, 4)
        if _kind == 0:  # small shell
            _sv = _dtrng.randint(140, 180)
            pygame.draw.ellipse(scene, (_sv, _sv - 10, _sv - 30), (_hx, _hy, _dtrng.randint(3, 7), _dtrng.randint(2, 5)))
        elif _kind == 1:  # driftwood
            _dl = _dtrng.randint(8, 28)
            _dang = _dtrng.uniform(0, math.pi)
            _dv = _dtrng.randint(60, 82)
            pygame.draw.line(scene, (_dv, _dv - 8, _dv - 18),
                             (_hx, _hy), (_hx + int(_dl * math.cos(_dang)), _hy + int(_dl * math.sin(_dang))), 2)
        elif _kind == 2:  # sand ripple
            _rw = _dtrng.randint(20, 60)
            _ra = _dtrng.randint(20, 45)
            _rs = pygame.Surface((_rw, 6), pygame.SRCALPHA)
            pygame.draw.line(_rs, (74, 70, 58, _ra), (0, 3), (_rw, 3), 1)
            pygame.draw.line(_rs, (56, 52, 42, _ra), (0, 4), (_rw, 4), 1)
            scene.blit(_rs, (_hx, _hy))
        elif _kind == 3:  # coiled rope
            _rv = _dtrng.randint(48, 62)
            pygame.draw.circle(scene, (_rv, _rv - 6, _rv - 16), (_hx, _hy), _dtrng.randint(4, 8), 1)
        else:  # tar spot
            _tr = _dtrng.randint(3, 8)
            _ts = pygame.Surface((_tr * 2, _tr * 2), pygame.SRCALPHA)
            pygame.draw.circle(_ts, (18, 16, 14, _dtrng.randint(60, 140)), (_tr, _tr), _tr)
            scene.blit(_ts, (_hx - _tr, _hy - _tr))

    # SHANTY: mud puddles, refuse, broken wood, sewage stains
    for _sz in (_slum_zone_l, _slum_zone_r):
        for _ in range(120):
            _sx = _dtrng.randint(_sz.left + 30, _sz.right - 30)
            _sy = _dtrng.randint(_sz.top + 30, _sz.bottom - 30)
            if _on_road(_sx, _sy): continue
            _kind = _dtrng.randint(0, 4)
            if _kind == 0:  # mud puddle with wet sheen
                _pw = _dtrng.randint(16, 60); _ph = _dtrng.randint(8, 30)
                _ps = pygame.Surface((_pw, _ph), pygame.SRCALPHA)
                _mv = _dtrng.randint(28, 42)
                pygame.draw.ellipse(_ps, (_mv, _mv - 4, _mv - 10, _dtrng.randint(100, 200)), (0, 0, _pw, _ph))
                scene.blit(_ps, (_sx, _sy))
                # wet highlight
                pygame.draw.ellipse(scene, (min(255, _mv + 28), min(255, _mv + 24), min(255, _mv + 16)),
                                    (_sx + _pw // 4, _sy + _ph // 4, _pw // 3, _ph // 3), 1)
            elif _kind == 1:  # broken plank
                _pl = _dtrng.randint(8, 24)
                _pang = _dtrng.uniform(0, math.pi)
                _pv = _dtrng.randint(44, 58)
                pygame.draw.line(scene, (_pv, _pv - 8, _pv - 16),
                                 (_sx, _sy), (_sx + int(_pl * math.cos(_pang)), _sy + int(_pl * math.sin(_pang))), 2)
            elif _kind == 2:  # sewage stain
                _sw2 = _dtrng.randint(10, 35); _sh2 = _dtrng.randint(6, 18)
                _ss = pygame.Surface((_sw2, _sh2), pygame.SRCALPHA)
                pygame.draw.ellipse(_ss, (36, 38, 26, _dtrng.randint(40, 100)), (0, 0, _sw2, _sh2))
                scene.blit(_ss, (_sx, _sy))
            elif _kind == 3:  # scattered refuse/rags
                for _ri in range(3):
                    _rx = _sx + _dtrng.randint(-8, 8)
                    _ry = _sy + _dtrng.randint(-4, 4)
                    _rv = _dtrng.randint(36, 52)
                    pygame.draw.rect(scene, (_rv, _rv - 6, _rv - 12), (_rx, _ry, _dtrng.randint(3, 8), _dtrng.randint(2, 5)))
            else:  # boot prints in mud
                for _bi in range(4):
                    _bx = _sx + _bi * _dtrng.randint(8, 14)
                    _by = _sy + _dtrng.randint(-3, 3)
                    pygame.draw.ellipse(scene, (34, 30, 24), (_bx, _by, 6, 4))

    # EMBER/ROOK: scattered stones, ash deposits, worn flagstones
    for _ in range(250):
        _ex = _dtrng.randint(_mse_zone.left + 40, _mse_zone.right - 40)
        _ey = _dtrng.randint(_mse_zone.top + 40, _mse_zone.bottom - 40)
        if _on_road(_ex, _ey): continue
        _kind = _dtrng.randint(0, 3)
        if _kind == 0:  # worn flagstone
            _fw = _dtrng.randint(14, 28); _fh = _dtrng.randint(10, 20)
            _fv = 54 + _dtrng.randint(-6, 8)
            pygame.draw.rect(scene, (_fv, _fv - 2, _fv - 6), (_ex, _ey, _fw, _fh))
            pygame.draw.rect(scene, (_fv - 16, _fv - 14, _fv - 18), (_ex, _ey, _fw, _fh), 1)
        elif _kind == 1:  # ash deposit
            _aw = _dtrng.randint(10, 35); _ah = _dtrng.randint(6, 18)
            _as = pygame.Surface((_aw, _ah), pygame.SRCALPHA)
            pygame.draw.ellipse(_as, (44, 42, 40, _dtrng.randint(30, 80)), (0, 0, _aw, _ah))
            scene.blit(_as, (_ex, _ey))
        elif _kind == 2:  # scattered pebbles
            for _pi in range(5):
                _px = _ex + _dtrng.randint(-6, 6); _py = _ey + _dtrng.randint(-4, 4)
                _pv = _dtrng.randint(48, 68)
                pygame.draw.circle(scene, (_pv, _pv - 4, _pv - 10), (_px, _py), _dtrng.randint(1, 3))
        else:  # dark stain
            _sw3 = _dtrng.randint(8, 24); _sh3 = _dtrng.randint(5, 14)
            _ss2 = pygame.Surface((_sw3, _sh3), pygame.SRCALPHA)
            pygame.draw.ellipse(_ss2, (32, 30, 28, _dtrng.randint(25, 70)), (0, 0, _sw3, _sh3))
            scene.blit(_ss2, (_ex, _ey))

    # ═══════════════════════════════════════════════════════════════════
    # HOUSE PLACEMENT — medieval castle layout with organic scatter
    # Inner keep (church/plaza) → market ring → wards → outskirts
    # ═══════════════════════════════════════════════════════════════════

    # ── 1. NOBLE QUARTER — stately manors, generous spacing, slight jitter ──
    for _ny in range(_noble_zone.top + 280, _noble_zone.bottom - 200, 520):
        for _nx in range(_noble_zone.left + 280, _noble_zone.right - 280, 470):
            _jx = _nx + _nhood_rng.randint(-60, 60)
            _jy = _ny + _nhood_rng.randint(-40, 40)
            if not _blocks_shop(_jx, _jy, 400, 380):
                house_specs.append((_jx, _jy, 'noble', 0.85 + _nhood_rng.random() * 0.10))

    # ── 2. MARKET DISTRICT — medium houses flanking the central plaza ──
    for _mz in (_market_zone_l, _market_zone_r):
        for _ny in range(_mz.top + 200, _mz.bottom - 150, 395):
            for _nx in range(_mz.left + 200, _mz.right - 200, 360):
                _jx = _nx + _nhood_rng.randint(-50, 50)
                _jy = _ny + _nhood_rng.randint(-35, 35)
                _in_plaza = _plaza_core.inflate(100, 100).collidepoint(_jx, _jy)
                if not _blocks_shop(_jx, _jy, 360, 340) and not _in_plaza:
                    house_specs.append((_jx, _jy, 'saint', 0.90 + _nhood_rng.random() * 0.10))

    # ── 3. ARTISAN WARD — workshops clustered with irregular spacing ──
    for _ny in range(_artisan_zone.top + 240, _artisan_zone.bottom - 150, 415):
        for _nx in range(_artisan_zone.left + 240, _artisan_zone.right - 220, 378):
            _jx = _nx + _nhood_rng.randint(-70, 70)
            _jy = _ny + _nhood_rng.randint(-50, 50)
            if not _blocks_shop(_jx, _jy, 340, 320):
                house_specs.append((_jx, _jy, 'artisan', 0.85 + _nhood_rng.random() * 0.12))

    # ── 4. HARBOR ROW — dense, small, irregular waterfront layout ──
    for _ny in range(_harbor_zone.top + 180, _harbor_zone.bottom - 150, 325):
        for _nx in range(_harbor_zone.left + 180, _harbor_zone.right - 180, 306):
            _jx = _nx + _nhood_rng.randint(-55, 55)
            _jy = _ny + _nhood_rng.randint(-40, 40)
            if not _blocks_shop(_jx, _jy, 300, 280) and _jx < width - 700:
                house_specs.append((_jx, _jy, 'harbor', 0.82 + _nhood_rng.random() * 0.13))

    # ── 5. OUTER SLUMS — chaotic, cramped, very irregular ──
    for _sz in (_slum_zone_l, _slum_zone_r):
        for _ny in range(_sz.top + 140, _sz.bottom - 100, 252):
            for _nx in range(_sz.left + 140, _sz.right - 120, 234):
                _jx = _nx + _nhood_rng.randint(-80, 80)
                _jy = _ny + _nhood_rng.randint(-60, 60)
                if not _blocks_shop(_jx, _jy, 240, 220):
                    house_specs.append((_jx, _jy, 'shanty', 0.72 + _nhood_rng.random() * 0.14))

    # ── 6. NE residential — upper-class extension ──
    _ne_zone = pygame.Rect(center_x + 600, HORIZON_Y + 350, 1500, 700)
    for _ny in range(_ne_zone.top + 220, _ne_zone.bottom - 150, 396):
        for _nx in range(_ne_zone.left + 200, _ne_zone.right - 200, 378):
            _jx = _nx + _nhood_rng.randint(-45, 45)
            _jy = _ny + _nhood_rng.randint(-30, 30)
            if not _blocks_shop(_jx, _jy, 360, 340):
                house_specs.append((_jx, _jy, 'saint', 0.90 + _nhood_rng.random() * 0.10))

    # ── 7. Mid-south (ember/rook) — working-class fill, organic scatter ──
    for _ny in range(_mse_zone.top + 220, _mse_zone.bottom - 150, 396):
        for _nx in range(_mse_zone.left + 220, _mse_zone.right - 220, 378):
            _jx = _nx + _nhood_rng.randint(-60, 60)
            _jy = _ny + _nhood_rng.randint(-40, 40)
            _in_plaza = _plaza_core.inflate(80, 80).collidepoint(_jx, _jy)
            _in_artisan = _artisan_zone.collidepoint(_jx, _jy)
            _in_harbor = _harbor_zone.collidepoint(_jx, _jy)
            if not _blocks_shop(_jx, _jy, 360, 340) and not _in_plaza and not _in_artisan and not _in_harbor:
                if _jx > center_x + 1500:
                    house_specs.append((_jx, _jy, 'rook', 0.85 + _nhood_rng.random() * 0.12))
                elif _jx < center_x - 500:
                    house_specs.append((_jx, _jy, 'artisan', 0.85 + _nhood_rng.random() * 0.12))
                else:
                    house_specs.append((_jx, _jy, 'ember', 0.88 + _nhood_rng.random() * 0.10))

    # ── 8. Far SE extension ──
    for _ny in range(_fse_zone.top + 200, _fse_zone.bottom - 150, 345):
        for _nx in range(_fse_zone.left + 200, _fse_zone.right - 200, 308):
            _jx = _nx + _nhood_rng.randint(-50, 50)
            _jy = _ny + _nhood_rng.randint(-35, 35)
            if not _blocks_shop(_jx, _jy, 300, 280) and _jx < width - 200:
                house_specs.append((_jx, _jy, 'harbor', 0.82 + _nhood_rng.random() * 0.13))

    # ── 9. South corners — shanty sprawl ──
    _sw_corner = pygame.Rect(400, HORIZON_Y + 5200, 1800, 1200)
    _se_corner = pygame.Rect(width - 2200, HORIZON_Y + 5200, 1800, 1200)
    for _corner in (_sw_corner, _se_corner):
        for _ny in range(_corner.top + 140, _corner.bottom - 100, 280):
            for _nx in range(_corner.left + 140, _corner.right - 120, 260):
                _jx = _nx + _nhood_rng.randint(-70, 70)
                _jy = _ny + _nhood_rng.randint(-50, 50)
                if not _blocks_shop(_jx, _jy, 240, 220):
                    house_specs.append((_jx, _jy, 'shanty', 0.72 + _nhood_rng.random() * 0.14))

    # ── 10. Center-south transition ──
    for _ny in range(_cs_zone.top + 200, _cs_zone.bottom - 100, 400):
        for _nx in range(_cs_zone.left + 220, _cs_zone.right - 220, 400):
            _jx = _nx + _nhood_rng.randint(-55, 55)
            _jy = _ny + _nhood_rng.randint(-35, 35)
            if not _blocks_shop(_jx, _jy, 340, 320):
                house_specs.append((_jx, _jy, 'ember', 0.82 + _nhood_rng.random() * 0.14))

    # ── Border wall houses ──
    for x_hw in range(280, width - 260, 460):
        # keep the row clear of the church silhouette (its position is saved
        # in church_position.json and may be anywhere along the north side)
        if abs(x_hw - _church_cx) < 460:
            continue
        house_specs.append((x_hw + _nhood_rng.randint(-20, 20), plaza.top + 42, 'saint', 0.95))
    for y_hw in range(plaza.top + 200, plaza.bottom - 150, 480):
        house_specs.append((200, y_hw + _nhood_rng.randint(-20, 20), 'ember', 0.96))
        house_specs.append((width - 200, y_hw + _nhood_rng.randint(-20, 20), 'rook', 0.95))

    # Extra poor shacks scattered outside the core districts (adds variety beyond the slum blocks).
    _shack_rng = random.Random(919)
    _shack_areas = [
        pygame.Rect(450, HORIZON_Y + 4400, 2600, 2100),                 # SW outskirts
        pygame.Rect(width - 3050, HORIZON_Y + 4400, 2600, 2100),         # SE outskirts
        pygame.Rect(center_x - 2400, HORIZON_Y + 5200, 4800, 1500),      # far south belt
    ]
    for _area in _shack_areas:
        _tries = 26
        for _ in range(_tries):
            _jx = _shack_rng.randint(_area.left + 140, _area.right - 140)
            _jy = _shack_rng.randint(_area.top + 140, _area.bottom - 120)
            if _on_road(_jx, _jy):
                continue
            if _plaza_core.inflate(260, 260).collidepoint(_jx, _jy):
                continue
            if not plaza.collidepoint(_jx, _jy):
                continue
            if abs(_jx - _cemetery_pos[0]) < 520 and abs(_jy - _cemetery_pos[1]) < 520:
                continue
            if _blocks_shop(_jx, _jy, 240, 220):
                continue
            house_specs.append((_jx, _jy, 'shanty', 0.68 + _shack_rng.random() * 0.16))

    # De-overlap pass — remove houses that would clip with already-placed
    # houses (seeded with the civic-landmark footprints so no house can
    # clip the town hall, windmill, granary, washhouse, walls or shrines)
    _placed_rects = [_lr.copy() for _lr in _landmark_rects]
    # Shops are runtime-drawn vendor stands (largest ~420x280 above the
    # anchor, customers milling below) — reserve their full visual rect so
    # no house can ever clip a shop, regardless of zone-check radii.
    for _sp_x, _sp_y in _shop.values():
        _placed_rects.append(pygame.Rect(_sp_x - 270, _sp_y - 360, 540, 600))
    _clean_specs = []
    _deoverlap_targets = {
        "noble": 420, "shanty": 200, "artisan": 340,
        "harbor": 260, "saint": 320, "ember": 320,
        "rook": 320, "bloodmarket": 320,
    }
    for hx, hy, style, sc in house_specs:
        _tw = _deoverlap_targets.get(style, 320)
        _hw = int(_tw * sc)
        _hh = int(_tw * 1.5 * sc)  # houses are roughly 1.5x as tall as wide
        _gap = 30
        _hr = pygame.Rect(hx - _hw // 2 - _gap, hy - _hh - _gap, _hw + _gap * 2, _hh + _gap * 2)
        _clips = False
        for _pr in _placed_rects:
            if _hr.colliderect(_pr):
                _clips = True
                break
        if not _clips:
            _placed_rects.append(_hr)
            _clean_specs.append((hx, hy, style, sc))
    house_specs = _clean_specs

    # Poor-town tuning: slightly smaller houses overall (less towering, more grounded).
    _house_scale_mult = 0.90
    house_specs = [(hx, hy, style, sc * _house_scale_mult) for (hx, hy, style, sc) in house_specs]

    def _rect_hits_road(r: pygame.Rect) -> bool:
        for _rr in _road_rects:
            if r.colliderect(_rr):
                return True
        return False

    def _draw_house_fence(hx: int, hy: int, house_base: pygame.Rect, district: str, sc: float, seed: int) -> None:
        """Decorative per-house fence. Uses district + seed for variety; avoids roads."""
        frng = random.Random(seed + hx * 5 + hy * 11)

        # Approximate building footprint depth (collision rect is a thin base strip).
        base_w = max(90, int(house_base.w))
        foot_h = int(max(110, min(260, base_w * (0.56 + 0.10 * frng.random()))))
        footprint = pygame.Rect(house_base.centerx - base_w // 2, house_base.bottom - foot_h, base_w, foot_h)

        # Yard padding (scaled by house size)
        pad_x = int(max(18, min(92, base_w * (0.16 + 0.10 * frng.random()))))
        pad_y = int(max(14, min(72, foot_h * (0.12 + 0.08 * frng.random()))))
        yard = footprint.inflate(pad_x * 2, pad_y * 2)

        # Clamp yard to playable area
        yard.clamp_ip(pygame.Rect(40, HORIZON_Y + 120, width - 80, height - (HORIZON_Y + 160)))

        # Fence material by district
        if district == "noble":
            fence_kind = "stone"
        elif district == "shanty":
            fence_kind = "wattle" if frng.random() < 0.65 else "wood"
        elif district == "harbor":
            fence_kind = "wood" if frng.random() < 0.75 else "wattle"
        elif district in ("artisan", "ember", "rook"):
            fence_kind = "wood" if frng.random() < 0.85 else "stone"
        else:
            fence_kind = "wood" if frng.random() < 0.70 else "wattle"

        # Decide which sides exist (half fences / broken fences)
        draw_top = True
        draw_bottom = (district != "shanty" and frng.random() > 0.35) or (district == "shanty" and frng.random() > 0.70)
        draw_left = frng.random() > (0.18 if district != "shanty" else 0.45)
        draw_right = frng.random() > (0.18 if district != "shanty" else 0.45)

        # If a side would overlap a road, skip it.
        h_map = {"wood": 38, "wattle": 30, "stone": 22}
        fh = h_map.get(fence_kind, 34)
        if draw_bottom and _rect_hits_road(pygame.Rect(yard.left, yard.bottom - fh, yard.width, fh)):
            draw_bottom = False
        if draw_top and _rect_hits_road(pygame.Rect(yard.left, yard.top - fh, yard.width, fh)):
            draw_top = False
        if draw_left and _rect_hits_road(pygame.Rect(yard.left - fh, yard.top, fh, yard.height)):
            draw_left = False
        if draw_right and _rect_hits_road(pygame.Rect(yard.right, yard.top, fh, yard.height)):
            draw_right = False

        # Gate opening on the "front" (south) when bottom fence exists
        gate_w = int(max(46, min(96, base_w * 0.24)))
        gate_x = house_base.centerx + int((frng.random() - 0.5) * base_w * 0.35)

        def _draw_h(kind: str, cx: int, by: int, length: int, *, seed_off: int = 0) -> None:
            if length < 26:
                return
            if kind == "stone":
                draw_low_stone_wall_segment(scene, cx, by, length, seed=seed + seed_off)
                if district == "noble" and length >= 60:
                    draw_iron_fence(scene, cx - length // 2 + 6, by - 2, length - 12)
            elif kind == "wattle":
                draw_wattle_fence_segment(scene, cx, by, length, seed=seed + seed_off)
            else:
                draw_fence_segment(scene, cx, by, length)

        def _draw_v(kind: str, cx: int, cy: int, length: int, *, seed_off: int = 0) -> None:
            if length < 26:
                return
            if kind == "stone":
                draw_low_stone_wall_segment_vertical(scene, cx, cy, length, seed=seed + seed_off)
                if district == "noble" and length >= 60:
                    draw_iron_fence_vertical(scene, cx + 2, cy, length - 12)
            elif kind == "wattle":
                draw_wattle_fence_segment_vertical(scene, cx, cy, length, seed=seed + seed_off)
            else:
                draw_fence_segment_vertical(scene, cx, cy, length)

        # Draw sides (slightly inset so fences don't look glued to roads)
        inset = 6
        if draw_top:
            _draw_h(fence_kind, yard.centerx, yard.top + fh + inset, yard.width - inset * 2, seed_off=1)
        if draw_bottom:
            left_len = max(0, (gate_x - gate_w // 2) - yard.left - inset)
            right_len = max(0, yard.right - inset - (gate_x + gate_w // 2))
            _draw_h(fence_kind, yard.left + inset + left_len // 2, yard.bottom, left_len, seed_off=2)
            _draw_h(fence_kind, yard.right - inset - right_len // 2, yard.bottom, right_len, seed_off=3)
        if draw_left:
            _draw_v(fence_kind, yard.left, yard.centery, yard.height - inset * 2, seed_off=4)
        if draw_right:
            _draw_v(fence_kind, yard.right, yard.centery, yard.height - inset * 2, seed_off=5)

    # ── Draw all houses onto separate overlay surfaces (for Diablo 2-style transparency) ──
    house_overlays = []  # list of (pygame.Surface, pygame.Rect) — surface with SRCALPHA, world rect
    _chimney_tops: list = []  # real chimney positions of placed houses (for smoke VFX)
    for idx, (hx, hy, style, sc) in enumerate(house_specs):
        _reg("house", hx, hy)
        _rval = rng.random()
        _roff = rng.randint(-26, 26) if _rval < 0.28 else 0
        if not _deleted("house", hx, hy):
            # Visual bounds: target_w * sc wide, ~2x that tall (roof + chimney)
            _ov_target = _deoverlap_targets.get(style, 320)
            _hw = int(_ov_target * sc * 1.2)
            _hh = int(_ov_target * sc * 2.5)  # include roof + chimney height
            pad = 40
            vl = hx - _hw // 2 - pad
            vt = hy - _hh - pad
            vr = hx + _hw // 2 + pad
            vb = hy + pad
            vw, vh = vr - vl, vb - vt
            vis_rect = pygame.Rect(vl, vt, vw, vh)
            # Draw house onto its own SRCALPHA surface
            overlay_surf = pygame.Surface((vw, vh), pygame.SRCALPHA)
            lx, ly = hx - vl, hy - vt  # local coords within overlay
            rect = draw_district_house(overlay_surf, lx, ly, sc, 900 + idx, style)
            # Map collision rect back to world coords
            world_rect = pygame.Rect(rect.x + vl, rect.y + vt, rect.w, rect.h)
            obstacles.append(world_rect.inflate(-10, -10))
            _draw_house_fence(hx, hy, world_rect, style, sc, 900 + idx)

            # Worn front path from the door down toward the lane — ties every
            # house to the street so it reads as lived-in, not dropped-in.
            _fp_rng = random.Random(9000 + idx)
            _fp_cx = world_rect.centerx + _fp_rng.randint(-14, 14)
            for _fp_i in range(_fp_rng.randint(4, 7)):
                _fp_w = max(14, 28 - _fp_i * 2)
                _fps = pygame.Surface((_fp_w, 10), pygame.SRCALPHA)
                pygame.draw.ellipse(_fps, (98, 84, 62, 130), (0, 0, _fp_w, 10))
                pygame.draw.ellipse(_fps, (116, 100, 76, 100), (3, 2, _fp_w - 6, 6))
                scene.blit(_fps, (_fp_cx - _fp_w // 2 + _fp_rng.randint(-4, 4),
                                  world_rect.bottom + 4 + _fp_i * 13))
            # flat stepping stones on the path for better-off households
            if style in ('noble', 'saint') and _fp_rng.random() < 0.7:
                for _fp_i in range(3):
                    _ssx = _fp_cx + _fp_rng.randint(-5, 5)
                    _ssy = world_rect.bottom + 12 + _fp_i * 22
                    pygame.draw.ellipse(scene, (122, 119, 112), (_ssx - 7, _ssy, 14, 7))
                    pygame.draw.ellipse(scene, (88, 86, 80), (_ssx - 7, _ssy, 14, 7), 1)

            # Trampled doorstep — dark wear right at the threshold
            _dws = pygame.Surface((44, 16), pygame.SRCALPHA)
            pygame.draw.ellipse(_dws, (58, 47, 34, 88), (0, 0, 44, 16))
            pygame.draw.ellipse(_dws, (70, 58, 42, 66), (6, 3, 32, 10))
            scene.blit(_dws, (_fp_cx - 22, world_rect.bottom - 8))

            # Kitchen garden beside the house: tilled rows + greens
            if style in ('saint', 'artisan', 'ember', 'noble', 'rook') and _fp_rng.random() < 0.5:
                _gd_w = _fp_rng.randint(56, 96)
                _gd_h = _fp_rng.randint(32, 48)
                _gd_x = (world_rect.left - _gd_w - 16) if _fp_rng.random() < 0.5 else (world_rect.right + 16)
                _gd_y = world_rect.bottom - _gd_h + _fp_rng.randint(-10, 6)
                _gd_r = pygame.Rect(_gd_x, _gd_y, _gd_w, _gd_h)
                if not _rect_hits_road(_gd_r) and plaza.contains(_gd_r):
                    _gds = pygame.Surface((_gd_w, _gd_h), pygame.SRCALPHA)
                    pygame.draw.rect(_gds, (86, 70, 50, 235), (0, 0, _gd_w, _gd_h), border_radius=4)
                    pygame.draw.rect(_gds, (70, 56, 40, 255), (0, 0, _gd_w, _gd_h), 2, border_radius=4)
                    for _gr_y in range(5, _gd_h - 3, 9):       # tilled furrows
                        pygame.draw.line(_gds, (66, 53, 38, 220), (4, _gr_y), (_gd_w - 5, _gr_y), 2)
                        pygame.draw.line(_gds, (108, 90, 66, 160), (4, _gr_y - 2), (_gd_w - 5, _gr_y - 2), 1)
                        for _gv_x in range(7, _gd_w - 6, _fp_rng.randint(8, 12)):
                            _gv_c = _fp_rng.choice([(74, 112, 54), (88, 124, 62), (64, 100, 48)])
                            pygame.draw.circle(_gds, _gv_c, (_gv_x, _gr_y - 1), _fp_rng.randint(2, 3))
                            pygame.draw.circle(_gds, (104, 142, 76), (_gv_x - 1, _gr_y - 2), 1)
                    scene.blit(_gds, (_gd_x, _gd_y))
                    # wicker edge posts
                    for _wp_x in (_gd_x + 2, _gd_x + _gd_w - 3):
                        pygame.draw.line(scene, (96, 76, 50), (_wp_x, _gd_y + 2), (_wp_x, _gd_y + _gd_h - 2), 2)
            _arch_local = overlay_surf.get_bounding_rect(min_alpha=128)
            if _arch_local.w <= 0 or _arch_local.h <= 0:
                _arch_local = overlay_surf.get_bounding_rect()
            house_overlays.append((overlay_surf, vis_rect, world_rect, style, _arch_local))
            _ch_pos = _district_house_chimney_top(hx, hy, sc, 900 + idx, style)
            if _ch_pos is not None:
                _chimney_tops.append(_ch_pos)
            if _rval < 0.28 and style not in ('noble', 'shanty'):
                crate_x, crate_y = world_rect.centerx + _roff, world_rect.bottom - 6
                p = draw_wood_crate(scene, crate_x, crate_y)
                obstacles.append(p)

    # Merge church overlay into the main overlay list
    if _church_overlay is not None:
        house_overlays.append(_church_overlay)

    # ═══════════════════════════════════════════════════════════════════
    # NEIGHBORHOOD-THEMED PROPS — dense, distinct character per district
    # ═══════════════════════════════════════════════════════════════════
    _np_rng = random.Random(777)

    # ── Ornament helpers (defined before _scatter_props so they can be dispatched) ──
    def _draw_scarecrow(sx, sy, seed=0):
        """Detailed scarecrow with hat, clothes, and straw stuffing."""
        _reg("scarecrow", sx, sy)
        if _deleted("scarecrow", sx, sy):
            return
        _rng = random.Random(seed + 5555)
        _sh = pygame.Surface((30, 10), pygame.SRCALPHA)
        pygame.draw.ellipse(_sh, (0, 0, 0, 30), _sh.get_rect())
        scene.blit(_sh, (sx - 15, sy - 3))
        for row in range(70):
            t = row / 69
            c = int(78 - 14 * t) + _rng.randint(-3, 3)
            pygame.draw.line(scene, (c, c - 14, c - 28), (sx - 2, sy - row), (sx + 2, sy - row))
        arm_y = sy - 52
        pygame.draw.line(scene, (72, 56, 34), (sx - 24, arm_y), (sx + 24, arm_y), 3)
        pygame.draw.line(scene, (58, 44, 26), (sx - 24, arm_y), (sx + 24, arm_y), 1)
        shirt_c = _rng.choice([(140, 90, 60), (100, 110, 130), (130, 120, 80), (110, 80, 80)])
        pts = [(sx - 22, arm_y), (sx + 22, arm_y), (sx + 14, sy - 24), (sx - 14, sy - 24)]
        pygame.draw.polygon(scene, shirt_c, pts)
        pygame.draw.polygon(scene, (max(0, shirt_c[0] - 30), max(0, shirt_c[1] - 30), max(0, shirt_c[2] - 30)), pts, 1)
        px = sx + _rng.randint(-8, 8)
        py = arm_y + _rng.randint(4, 16)
        patch_c = _rng.choice([(120, 80, 50), (90, 100, 110), (110, 100, 70)])
        pygame.draw.rect(scene, patch_c, (px - 4, py - 3, 8, 6))
        pygame.draw.rect(scene, (max(0, patch_c[0] - 20), max(0, patch_c[1] - 20), max(0, patch_c[2] - 20)), (px - 4, py - 3, 8, 6), 1)
        for _ in range(6):
            stx = sx + _rng.choice([-22, 22, -14, 14]) + _rng.randint(-2, 2)
            sty = arm_y + _rng.randint(0, 20)
            pygame.draw.line(scene, (178, 158, 72), (stx, sty), (stx + _rng.randint(-6, 6), sty + _rng.randint(-8, 2)), 1)
        head_y = sy - 62
        pygame.draw.circle(scene, (168, 148, 108), (sx, head_y), 8)
        pygame.draw.circle(scene, (138, 118, 78), (sx, head_y), 8, 1)
        pygame.draw.circle(scene, (42, 36, 30), (sx - 3, head_y - 1), 2)
        pygame.draw.circle(scene, (42, 36, 30), (sx + 3, head_y - 1), 2)
        pygame.draw.line(scene, (42, 36, 30), (sx - 3, head_y + 3), (sx + 3, head_y + 3), 1)
        for i in range(-3, 4, 2):
            pygame.draw.line(scene, (42, 36, 30), (sx + i, head_y + 3), (sx + i, head_y + 4), 1)
        hat_c = _rng.choice([(92, 72, 42), (72, 72, 82), (82, 62, 52)])
        pygame.draw.ellipse(scene, hat_c, (sx - 14, head_y - 11, 28, 8))
        pygame.draw.rect(scene, (hat_c[0] - 10, hat_c[1] - 10, hat_c[2] - 8), (sx - 7, head_y - 18, 14, 10), border_radius=2)
        pygame.draw.ellipse(scene, (hat_c[0] - 16, hat_c[1] - 16, hat_c[2] - 12), (sx - 14, head_y - 11, 28, 8), 1)
        if _rng.random() > 0.5:
            crow_x = sx + _rng.choice([-20, 20])
            crow_y = arm_y - 6
            pygame.draw.ellipse(scene, (22, 22, 28), (crow_x - 4, crow_y, 8, 5))
            pygame.draw.circle(scene, (22, 22, 28), (crow_x + _rng.choice([-3, 3]), crow_y - 1), 3)
            pygame.draw.circle(scene, (220, 180, 40), (crow_x + _rng.choice([-2, 4]), crow_y - 2), 1)
            pygame.draw.line(scene, (180, 140, 40), (crow_x + _rng.choice([-4, 4]), crow_y - 1),
                             (crow_x + _rng.choice([-6, 6]), crow_y - 2), 1)

    def _draw_wheelbarrow(sx, sy, seed=0):
        """Detailed wheelbarrow with optional contents."""
        _reg("wheelbarrow", sx, sy)
        if _deleted("wheelbarrow", sx, sy):
            return
        _rng = random.Random(seed + 7777)
        _sh = pygame.Surface((36, 10), pygame.SRCALPHA)
        pygame.draw.ellipse(_sh, (0, 0, 0, 28), _sh.get_rect())
        scene.blit(_sh, (sx - 18, sy - 3))
        pygame.draw.circle(scene, (68, 60, 48), (sx - 12, sy - 2), 7, 2)
        pygame.draw.circle(scene, (52, 44, 34), (sx - 12, sy - 2), 3)
        for a in range(0, 360, 60):
            rad = math.radians(a)
            pygame.draw.line(scene, (58, 48, 36), (sx - 12, sy - 2),
                             (sx - 12 + int(5 * math.cos(rad)), sy - 2 + int(5 * math.sin(rad))), 1)
        tray_pts = [(sx - 6, sy - 4), (sx + 18, sy - 8), (sx + 18, sy - 20), (sx - 6, sy - 14)]
        for row in range(16):
            t = row / 15
            c = int(96 - 12 * t) + _rng.randint(-3, 3)
            y_r = sy - 4 - row
            lx = sx - 6 + int(row * 0.2)
            rx = sx + 18 - int(row * 0.1)
            pygame.draw.line(scene, (c, c - 16, c - 34), (lx, y_r), (rx, y_r))
        pygame.draw.polygon(scene, (52, 38, 18), tray_pts, 1)
        pygame.draw.line(scene, (72, 56, 34), (sx + 16, sy - 6), (sx + 28, sy - 2), 2)
        pygame.draw.line(scene, (72, 56, 34), (sx + 16, sy - 10), (sx + 28, sy - 6), 2)
        _fill = _rng.randint(0, 2)
        if _fill == 0:
            pygame.draw.ellipse(scene, (72, 58, 38), (sx - 2, sy - 18, 16, 8))
        elif _fill == 1:
            for _ in range(8):
                hx = sx + _rng.randint(-2, 14)
                hy = sy - _rng.randint(14, 22)
                pygame.draw.line(scene, (172, 152, 72), (hx, hy), (hx + _rng.randint(-3, 3), hy - _rng.randint(3, 8)), 1)
        else:
            for _ in range(4):
                vx = sx + _rng.randint(0, 12)
                vy = sy - _rng.randint(14, 20)
                vc = _rng.choice([(180, 80, 40), (40, 140, 40), (200, 160, 40)])
                pygame.draw.circle(scene, vc, (vx, vy), _rng.randint(2, 3))

    def _draw_tool_rack(sx, sy, seed=0):
        """Wooden rack with farm tools (pitchfork, rake, hoe)."""
        _reg("tool_rack", sx, sy)
        if _deleted("tool_rack", sx, sy):
            return
        _rng = random.Random(seed + 8888)
        for px in [sx - 12, sx + 12]:
            for row in range(45):
                t = row / 44
                c = int(82 - 12 * t) + _rng.randint(-2, 2)
                pygame.draw.line(scene, (c, c - 14, c - 28), (px - 2, sy - row), (px + 1, sy - row))
        pygame.draw.line(scene, (76, 58, 34), (sx - 14, sy - 36), (sx + 14, sy - 36), 3)
        pygame.draw.line(scene, (58, 42, 22), (sx - 14, sy - 36), (sx + 14, sy - 36), 1)
        tools = _rng.sample(["pitchfork", "rake", "hoe", "shovel"], 3)
        for ti, tool in enumerate(tools):
            tx = sx - 10 + ti * 10
            pygame.draw.line(scene, (92, 74, 48), (tx, sy - 36), (tx, sy - 6), 2)
            if tool == "pitchfork":
                for prong in [-3, 0, 3]:
                    pygame.draw.line(scene, (62, 58, 52), (tx + prong, sy - 6), (tx + prong, sy + 4), 1)
            elif tool == "rake":
                pygame.draw.line(scene, (62, 58, 52), (tx - 4, sy - 4), (tx + 4, sy - 4), 2)
                for r in range(-3, 4, 2):
                    pygame.draw.line(scene, (62, 58, 52), (tx + r, sy - 4), (tx + r, sy + 2), 1)
            elif tool == "hoe":
                pygame.draw.polygon(scene, (62, 58, 52), [(tx - 4, sy - 4), (tx + 3, sy - 4), (tx + 3, sy + 3), (tx - 2, sy + 3)])
            elif tool == "shovel":
                pygame.draw.polygon(scene, (62, 58, 52), [(tx - 3, sy - 4), (tx + 3, sy - 4), (tx + 2, sy + 5), (tx - 2, sy + 5)])

    def _draw_milk_churn(sx, sy, seed=0):
        """Metal milk churn / butter churn."""
        _reg("milk_churn", sx, sy)
        if _deleted("milk_churn", sx, sy):
            return
        _rng = random.Random(seed + 4444)
        _sh = pygame.Surface((16, 6), pygame.SRCALPHA)
        pygame.draw.ellipse(_sh, (0, 0, 0, 28), _sh.get_rect())
        scene.blit(_sh, (sx - 8, sy - 2))
        for row in range(22):
            t = row / 21
            hw = int(5 * (0.85 + 0.15 * math.sin(t * math.pi)))
            c = int(148 - 20 * t) + _rng.randint(-3, 3)
            pygame.draw.line(scene, (c, c - 2, c - 4), (sx - hw, sy - row), (sx + hw, sy - row))
        for ry in [sy - 4, sy - 14]:
            pygame.draw.line(scene, (120, 118, 114), (sx - 5, ry), (sx + 5, ry), 1)
        pygame.draw.ellipse(scene, (158, 156, 152), (sx - 4, sy - 23, 8, 4))
        pygame.draw.ellipse(scene, (128, 126, 122), (sx - 4, sy - 23, 8, 4), 1)
        pygame.draw.arc(scene, (130, 128, 124), (sx - 3, sy - 28, 6, 8), 0, math.pi, 2)

    def _draw_stone_path(x1, y1, x2, y2, seed=0):
        """Rustic stepping stone path between two points."""
        _reg("stone_path", x1, y1)
        if _deleted("stone_path", x1, y1):
            return
        _rng = random.Random(seed + 9999)
        dx = x2 - x1
        dy = y2 - y1
        dist = max(1, int(math.hypot(dx, dy)))
        steps = dist // 28
        for i in range(steps):
            t = (i + 0.5) / max(1, steps)
            px = int(x1 + dx * t) + _rng.randint(-4, 4)
            py = int(y1 + dy * t) + _rng.randint(-3, 3)
            sw = _rng.randint(10, 16)
            sh = _rng.randint(7, 11)
            sc = 72 + _rng.randint(-8, 8)
            pygame.draw.ellipse(scene, (sc, sc - 2, sc - 6), (px - sw // 2, py - sh // 2, sw, sh))
            pygame.draw.ellipse(scene, (sc - 18, sc - 20, sc - 24), (px - sw // 2, py - sh // 2, sw, sh), 1)
            # Highlight
            pygame.draw.ellipse(scene, (sc + 10, sc + 8, sc + 4), (px - sw // 3, py - sh // 3, sw // 2, sh // 2))

    def _draw_farm_sign(sx, sy, text, seed=0):
        """Rustic wooden farm sign with carved text."""
        _reg("farm_sign", sx, sy)
        if _deleted("farm_sign", sx, sy):
            return
        _rng = random.Random(seed + 6666)
        # Post
        for row in range(40):
            t = row / 39
            c = int(82 - 12 * t) + _rng.randint(-2, 2)
            pygame.draw.line(scene, (c, c - 12, c - 26), (sx - 2, sy - row), (sx + 2, sy - row))
        # Sign board
        bw = max(60, len(text) * 7 + 16)
        bh = 20
        bx = sx - bw // 2
        by = sy - 38 - bh
        for row in range(bh):
            t = row / max(1, bh - 1)
            c = int(108 - 14 * t) + _rng.randint(-3, 3)
            pygame.draw.line(scene, (c, c - 18, c - 38), (bx, by + row), (bx + bw, by + row))
        # Wood grain
        for _ in range(3):
            gy = by + _rng.randint(2, bh - 2)
            pygame.draw.line(scene, (62, 46, 22), (bx + 2, gy), (bx + bw - 2, gy), 1)
        pygame.draw.rect(scene, (52, 36, 16), (bx, by, bw, bh), 2, border_radius=2)
        # Iron brackets
        for bkx in [bx + 4, bx + bw - 8]:
            pygame.draw.rect(scene, (52, 48, 42), (bkx, by + bh - 2, 4, 6))
            pygame.draw.circle(scene, (66, 60, 50), (bkx + 2, by + bh + 2), 1)
        # Carved text (dark burned lettering)
        try:
            _font = pygame.font.SysFont("arial", 10)
            _ts = _font.render(text, True, (38, 28, 16))
            scene.blit(_ts, (sx - _ts.get_width() // 2, by + bh // 2 - _ts.get_height() // 2))
        except Exception:
            pass

    def _scatter_props(zone, count, palette, rng_ref):
        """Place random props from a themed palette within a zone."""
        for _ in range(count):
            _sx = rng_ref.randint(zone.left + 80, max(zone.left + 81, zone.right - 80))
            _sy = rng_ref.randint(zone.top + 80, max(zone.top + 81, zone.bottom - 80))
            if _on_road(_sx, _sy):
                continue
            _pt = rng_ref.choice(palette)
            if _pt == "barrel":
                _hd_barrel(_sx, _sy)
            elif _pt == "cart":
                _hd_cart(_sx, _sy)
            elif _pt == "hay":
                _hd_hay(_sx, _sy)
            elif _pt == "flowerbox":
                _decor("flowerbox", draw_flower_box, _sx, _sy, seed=_sx + _sy)
            elif _pt == "potted_tree":
                _prop("potted_tree", draw_potted_tree, _sx, _sy, seed=_sx)
            elif _pt == "planter":
                _prop("planter", draw_stone_planter, _sx, _sy, seed=_sx + _sy)
            elif _pt == "bench":
                _prop("bench", draw_wooden_bench, _sx, _sy, rng_ref.random() > 0.5)
            elif _pt == "woodpile":
                _prop("woodpile", draw_woodpile, _sx, _sy)
            elif _pt == "lumber":
                _prop("lumber", draw_lumber_stack, _sx, _sy)
            elif _pt == "crate":
                _prop("crate", draw_wood_crate, _sx, _sy)
            elif _pt == "sacks":
                _prop("sacks", draw_sack_pile, _sx, _sy)
            elif _pt == "water_trough":
                _prop("water_trough", draw_water_trough, _sx, _sy)
            elif _pt == "rain_barrel":
                _prop("rain_barrel", draw_rain_barrel, _sx, _sy)
            elif _pt == "meat_rack":
                _prop("meat_rack", draw_meat_rack, _sx, _sy)
            elif _pt == "torch":
                _prop("torch_stand", draw_torch_stand, _sx, _sy)
            elif _pt == "stocks":
                _prop("stocks", draw_stocks, _sx, _sy)
            elif _pt == "horse_hitch":
                _prop("horse_hitch", draw_horse_hitch, _sx, _sy)
            elif _pt == "fence":
                _prop("fence", draw_fence_segment, _sx, _sy, rng_ref.randint(60, 120))
            elif _pt == "signpost":
                _prop("signpost", draw_signpost, _sx, _sy, seed=_sx)
            elif _pt == "wheelbarrow":
                _draw_wheelbarrow(_sx, _sy, seed=_sx + _sy)
            elif _pt == "tool_rack":
                _draw_tool_rack(_sx, _sy, seed=_sx + _sy)
            elif _pt == "scarecrow":
                _draw_scarecrow(_sx, _sy, seed=_sx + _sy)
            elif _pt == "milk_churn":
                _draw_milk_churn(_sx, _sy, seed=_sx + _sy)

    # ── Noble Quarter — gardens, planters, benches, lampposts ──
    _noble_palette = ["planter", "potted_tree", "bench", "flowerbox", "flowerbox",
                      "potted_tree", "planter", "bench", "signpost", "horse_hitch",
                      "milk_churn", "flowerbox"]
    _scatter_props(_noble_zone, 45, _noble_palette, _np_rng)
    for _nlx in range(_noble_zone.left + 200, _noble_zone.right - 200, 200):
        for _nly_off in [_noble_zone.top + 280, _noble_zone.centery, _noble_zone.bottom - 200]:
            _reg("lamp", _nlx, _nly_off)
            if not _deleted("lamp", _nlx, _nly_off):
                draw_lamppost(scene, _nlx, _nly_off, lit=True)
                obstacles.append(pygame.Rect(_nlx - 5, _nly_off - 5, 10, 10))

    # ── Artisan Ward — workshops, materials, craft tools ──
    _artisan_palette = ["woodpile", "lumber", "water_trough", "rain_barrel", "sacks",
                        "barrel", "crate", "torch", "fence", "woodpile", "lumber",
                        "tool_rack", "wheelbarrow", "tool_rack"]
    _scatter_props(_artisan_zone, 50, _artisan_palette, _np_rng)

    # ── Harbor Row — maritime, storage, fish ──
    _harbor_palette = ["barrel", "barrel", "crate", "crate", "sacks", "meat_rack",
                       "bench", "torch", "barrel", "crate", "rain_barrel",
                       "wheelbarrow", "rain_barrel"]
    _harbor_prop_zone = _harbor_zone.copy()
    _harbor_prop_zone.width = min(_harbor_prop_zone.width, width - _harbor_prop_zone.left - 750)
    _scatter_props(_harbor_prop_zone, 35, _harbor_palette, _np_rng)

    # ── Slums — broken, scattered, muddy ──
    _slum_palette = ["cart", "cart", "barrel", "woodpile", "crate", "hay",
                     "stocks", "cart", "barrel", "hay", "fence", "wheelbarrow",
                     "scarecrow"]
    for _sz in (_slum_zone_l, _slum_zone_r):
        _scatter_props(_sz, 28, _slum_palette, _np_rng)
        for _ in range(12):
            _mpx = _np_rng.randint(_sz.left + 50, _sz.right - 50)
            _mpy = _np_rng.randint(_sz.top + 50, _sz.bottom - 50)
            _mpw = _np_rng.randint(30, 100)
            _mph = _np_rng.randint(15, 50)
            pygame.draw.ellipse(scene, (38 + _np_rng.randint(-4, 4), 32 + _np_rng.randint(-4, 4), 24), (_mpx, _mpy, _mpw, _mph))

    # ── Market District props — awnings, sacks, display goods ──
    _market_palette = ["barrel", "crate", "sacks", "bench", "torch",
                       "signpost", "horse_hitch", "potted_tree", "flowerbox",
                       "wheelbarrow", "milk_churn"]
    for _mz in (_market_zone_l, _market_zone_r):
        _scatter_props(_mz, 25, _market_palette, _np_rng)

    # ── Infill zone props (mid-south, NE, SE, transitions) ──
    _infill_palette = ["woodpile", "barrel", "crate", "bench", "torch",
                       "rain_barrel", "fence", "potted_tree", "hay", "signpost"]
    _scatter_props(_mse_zone, 45, _infill_palette, _np_rng)
    _scatter_props(_ne_zone, 15, _market_palette, _np_rng)
    _scatter_props(_fse_zone, 20, _harbor_palette, _np_rng)
    _scatter_props(_cs_zone, 18, _infill_palette, _np_rng)
    for _corner in (_sw_corner, _se_corner):
        _scatter_props(_corner, 16, _slum_palette, _np_rng)
        for _ in range(6):
            _mpx = _np_rng.randint(_corner.left + 30, _corner.right - 30)
            _mpy = _np_rng.randint(_corner.top + 30, _corner.bottom - 30)
            pygame.draw.ellipse(scene, (40 + _np_rng.randint(-3, 5), 34 + _np_rng.randint(-3, 5), 26), (_mpx, _mpy, _np_rng.randint(25, 70), _np_rng.randint(12, 35)))

    # ═══════════════════════════════════════════════════════════════════
    # GAP-FILLER PASS — scan the whole town and place props in empty cells
    # ═══════════════════════════════════════════════════════════════════
    _gf_rng = random.Random(999)
    _gf_cell = 400
    _occupied = set()
    for p in prop_registry:
        _occupied.add((p['x'] // _gf_cell, p['y'] // _gf_cell))
    _generic_palette = ["potted_tree", "bench", "torch", "barrel", "fence",
                        "woodpile", "rain_barrel", "signpost", "horse_hitch", "crate",
                        "wheelbarrow", "tool_rack", "milk_churn", "flowerbox"]
    for _gx in range(1, width // _gf_cell - 1):
        for _gy in range((HORIZON_Y + 250) // _gf_cell, (height - 400) // _gf_cell):
            if (_gx, _gy) not in _occupied:
                _fx = _gx * _gf_cell + _gf_rng.randint(80, _gf_cell - 80)
                _fy = _gy * _gf_cell + _gf_rng.randint(80, _gf_cell - 80)
                if _on_road(_fx, _fy):
                    continue
                # Place 2-4 props per empty cell to create mini-clusters
                for _gi in range(_gf_rng.randint(2, 4)):
                    _gox = _fx + _gf_rng.randint(-60, 60)
                    _goy = _fy + _gf_rng.randint(-30, 30)
                    if _on_road(_gox, _goy):
                        continue
                    _gpt = _gf_rng.choice(_generic_palette)
                    if _gpt == "barrel":
                        _hd_barrel(_gox, _goy)
                    elif _gpt == "potted_tree":
                        _prop("potted_tree", draw_potted_tree, _gox, _goy, seed=_gox + _goy)
                    elif _gpt == "bench":
                        _prop("bench", draw_wooden_bench, _gox, _goy, _gf_rng.random() > 0.5)
                    elif _gpt == "torch":
                        _prop("torch_stand", draw_torch_stand, _gox, _goy)
                    elif _gpt == "fence":
                        _prop("fence", draw_fence_segment, _gox, _goy, _gf_rng.randint(60, 120))
                    elif _gpt == "woodpile":
                        _prop("woodpile", draw_woodpile, _gox, _goy)
                    elif _gpt == "rain_barrel":
                        _prop("rain_barrel", draw_rain_barrel, _gox, _goy)
                    elif _gpt == "signpost":
                        _prop("signpost", draw_signpost, _gox, _goy, seed=_gox)
                    elif _gpt == "horse_hitch":
                        _prop("horse_hitch", draw_horse_hitch, _gox, _goy)
                    elif _gpt == "crate":
                        _prop("crate", draw_wood_crate, _gox, _goy)
                    elif _gpt == "wheelbarrow":
                        _draw_wheelbarrow(_gox, _goy, seed=_gox + _goy)
                    elif _gpt == "tool_rack":
                        _draw_tool_rack(_gox, _goy, seed=_gox + _goy)
                    elif _gpt == "milk_churn":
                        _draw_milk_churn(_gox, _goy, seed=_gox + _goy)
                    elif _gpt == "flowerbox":
                        _decor("flowerbox", draw_flower_box, _gox, _goy, seed=_gox + _goy)

    for px, py in [
        (plaza.left + 80, plaza.top + 120), (plaza.left + 95, plaza.bottom - 120),
        (plaza.right - 95, plaza.top + 120), (plaza.right - 80, plaza.bottom - 120),
    ]:
        _reg("dummy", px, py)
        if not _deleted("dummy", px, py):
            obstacles.append(draw_training_dummy(scene, px, py))

    for i in range(6):
        gx = plaza.left + 180 + i * 110
        gy = wall_y + 140
        _reg("grave", gx, gy)
        if not _deleted("grave", gx, gy):
            obstacles.append(draw_grave_stone(scene, gx, gy, i))

    # ═══════════════════════════════════════════════════════════════════
    # LAMPPOSTS — along all major roads at ~300px intervals
    # ═══════════════════════════════════════════════════════════════════
    lamp_points = []
    # Along north-south boulevard (both sides)
    for _ly in range(HORIZON_Y + 400, height - 400, 300):
        lamp_points.append((center_x - 70, _ly))
        lamp_points.append((center_x + 70, _ly))
    # Along east-west cross roads
    for _ry in [_road_y_n, _road_y_m, _road_y_s]:
        for _lx in range(500, width - 500, 300):
            if abs(_lx - center_x) > 120:  # skip where N-S road crosses
                lamp_points.append((_lx, _ry - 60))
    # Along far south road
    for _lx in range(900, width - 900, 350):
        lamp_points.append((_lx, _road_y_fs - 55))
    # Central plaza perimeter
    for _lx in range(_plaza_core.left + 80, _plaza_core.right - 80, 200):
        lamp_points.append((_lx, _plaza_core.top - 30))
        lamp_points.append((_lx, _plaza_core.bottom + 30))
    for _ly in range(_plaza_core.top + 100, _plaza_core.bottom - 100, 200):
        lamp_points.append((_plaza_core.left - 30, _ly))
        lamp_points.append((_plaza_core.right + 30, _ly))
    # Deduplicate lamps too close together
    _final_lamps = []
    for lx, ly in lamp_points:
        if any(_lr.collidepoint(lx, ly) for _lr in _landmark_rects):
            continue  # don't plant a lamp inside a civic landmark footprint
        if all(abs(lx - ex) > 120 or abs(ly - ey) > 120 for ex, ey in _final_lamps):
            _final_lamps.append((lx, ly))
    for lx, ly in _final_lamps:
        _reg("lamp", lx, ly)
        if not _deleted("lamp", lx, ly):
            draw_lamppost(scene, lx, ly, lit=True)
            obstacles.append(pygame.Rect(lx - 5, ly - 5, 10, 10))

    # ═══════════════════════════════════════════════════════════════════════
    # MEDIEVAL TOWN PROP DISTRIBUTION — Themed Clusters
    # ═══════════════════════════════════════════════════════════════════════
    # Layout philosophy: every prop belongs to a logical zone.  Props are
    # grouped in clusters that make sense together (forge + anvil + water,
    # market stall + sacks + crates, etc.).  Nothing is randomly scattered.

    # ═══════════════════════════════════════════════════════════════════
    # HARBOUR — east coast water area with docks and boats
    # ═══════════════════════════════════════════════════════════════════
    _harbour_x = width - 700
    _harbour_top = HORIZON_Y + 1000
    _harbour_h = 1200
    _harbour_rect = pygame.Rect(_harbour_x, _harbour_top, 700, _harbour_h)
    draw_harbour_water(scene, _harbour_rect, seed=42)
    # Water is an obstacle (can't walk into it)
    obstacles.append(_harbour_rect.inflate(-40, -20))
    # Docks extending into water
    _dock1 = draw_dock(scene, _harbour_x - 20, _harbour_top + 200, 160, horizontal=True)
    obstacles.append(_dock1)
    _dock2 = draw_dock(scene, _harbour_x - 20, _harbour_top + 500, 140, horizontal=True)
    obstacles.append(_dock2)
    _dock3 = draw_dock(scene, _harbour_x - 20, _harbour_top + 800, 120, horizontal=True)
    obstacles.append(_dock3)
    # ── Large sailing ship moored at main dock ──
    _ship_x = _harbour_x + 300
    _ship_y = _harbour_top + 400
    draw_sailing_ship(scene, _ship_x, _ship_y, scale=1.2, seed=42)
    # Long dock for the ship
    _ship_dock = draw_dock(scene, _harbour_x - 20, _harbour_top + 380, 200, horizontal=True)
    obstacles.append(_ship_dock)
    # (small fishing boats removed — galleon dominates harbour)
    # Harbour props (near sailor shop)
    _sx, _sy = _shop["sailor"]
    _prop("crate", draw_wood_crate, _sx - 120, _sy - 60)
    _prop("crate", draw_wood_crate, _sx - 80, _sy - 60)
    _hd_barrel(_sx + 80, _sy - 60)
    _hd_barrel(_sx + 120, _sy - 40)
    _prop("sacks", draw_sack_pile, _sx - 120, _sy + 40)
    _prop("bench", draw_wooden_bench, _sx + 80, _sy + 60)
    _prop("torch_stand", draw_torch_stand, _sx - 160, _sy)
    _prop("torch_stand", draw_torch_stand, _sx + 160, _sy)
    _prop("signpost", draw_signpost, _sx - 180, _sy - 80, seed=600)
    _tasset(_sx - 40, _sy + 80, "garlic_stand")

    # ═══════════════════════════════════════════════════════════════════
    # SCATTERED SHOP PROP ZONES — each shop has themed props around it
    # ═══════════════════════════════════════════════════════════════════

    # ── CHURCHYARD (north-center, near church) ────────────────────
    _tasset(center_x - 240, HORIZON_Y + 420, "troita")
    _tasset(center_x + 240, HORIZON_Y + 420, "troita")
    _tasset(center_x - 440, HORIZON_Y + 340, "coffin")
    _tasset(center_x + 440, HORIZON_Y + 340, "coffin")
    _prop("bench", draw_wooden_bench, center_x - 140, HORIZON_Y + 440)
    _prop("bench", draw_wooden_bench, center_x + 140, HORIZON_Y + 440)
    _decor("flowerbox", draw_flower_box, center_x - 80, HORIZON_Y + 350, seed=20)
    _decor("flowerbox", draw_flower_box, center_x + 80, HORIZON_Y + 350, seed=21)

    # ── BLACKSMITH — northwest forge yard (L-shaped cluster) ──────
    _bx, _by = _shop["blacksmith"]
    # L-shape: forge line (N-S) + supply line (E-W)
    _prop("forge", draw_hd_forge_prop, _bx - 140, _by - 80)
    _prop("anvil", draw_hd_anvil, _bx - 140, _by - 20)
    _prop("water_trough", draw_water_trough, _bx - 140, _by + 40)  # quench trough in line
    # Supply corner (perpendicular)
    _prop("lumber", draw_lumber_stack, _bx - 60, _by + 40)
    _hd_barrel(_bx + 20, _by + 40)
    _prop("crate", draw_wood_crate, _bx + 20, _by + 80)
    # Opposite side: display & seating
    _prop("weapon_rack", draw_weapon_rack, _bx + 140, _by - 60)
    _prop("weapon_rack", draw_weapon_rack, _bx + 140, _by + 10)
    _prop("bench", draw_wooden_bench, _bx + 140, _by + 70)
    # Framing torches
    _prop("torch_stand", draw_torch_stand, _bx - 200, _by - 80)
    _prop("torch_stand", draw_torch_stand, _bx + 200, _by - 80)
    _prop("sign", draw_hanging_sign, _bx + 40, _by - 80, seed=10)

    # ── BAKER — north-center market corner ───────────────────────
    _bkx, _bky = _shop["baker"]
    # Awning + display cluster
    _prop("market_awning", draw_market_awning, _bkx - 40, _bky - 50, (148, 88, 38))
    _prop("sacks", draw_sack_pile, _bkx - 130, _bky - 40)
    _prop("sacks", draw_sack_pile, _bkx - 130, _bky + 10)
    _hd_barrel(_bkx - 70, _bky + 10)
    # Cart + supply L-shape
    _hd_cart(_bkx + 100, _bky - 50)
    _prop("crate", draw_wood_crate, _bkx + 100, _bky + 10)
    _prop("woodpile", draw_woodpile, _bkx + 140, _bky + 60)
    # Seating area
    _prop("bench", draw_wooden_bench, _bkx - 80, _bky + 80)
    _prop("bench", draw_wooden_bench, _bkx + 40, _bky + 80)
    _prop("torch_stand", draw_torch_stand, _bkx - 170, _bky)
    _prop("torch_stand", draw_torch_stand, _bkx + 170, _bky)
    _decor("flowerbox", draw_flower_box, _bkx, _bky + 110, seed=25)

    # ── TAILOR — northeast dye yard ──────────────────────────────
    _tx, _ty = _shop["tailor"]
    # Drying lines + work area
    _decor("laundry", draw_laundry_line, _tx - 120, _ty - 70, 120)
    _decor("laundry", draw_laundry_line, _tx - 120, _ty - 30, 100)
    # Supply corner (L-shape)
    _prop("crate", draw_wood_crate, _tx + 130, _ty - 50)
    _prop("crate", draw_wood_crate, _tx + 130, _ty - 10)
    _prop("wine_rack", draw_wine_rack, _tx + 130, _ty + 40)
    _hd_barrel(_tx + 80, _ty + 40)
    # Display side
    _prop("bench", draw_wooden_bench, _tx - 140, _ty + 30, True)
    _prop("sign", draw_hanging_sign, _tx + 30, _ty - 60, seed=60)
    _prop("potted_tree", draw_potted_tree, _tx - 180, _ty - 30, seed=61)
    _prop("torch_stand", draw_torch_stand, _tx - 200, _ty)
    _prop("torch_stand", draw_torch_stand, _tx + 200, _ty)

    # ── ALCHEMIST — west herb garden + lab ───────────────────────
    _ax, _ay = _shop["alchemist"]
    # Lab cluster (cauldron + pottery + rain barrel in L)
    _prop("cauldron", draw_cauldron, _ax - 140, _ay - 60)
    _prop("pottery", draw_pottery_stack, _ax - 140, _ay + 10, seed=30)
    _prop("rain_barrel", draw_rain_barrel, _ax - 60, _ay + 10)
    _hd_barrel(_ax - 60, _ay - 60)
    # Herb garden side
    _prop("planter", draw_stone_planter, _ax + 80, _ay - 60, seed=43)
    _prop("planter", draw_stone_planter, _ax + 80, _ay + 10, seed=44)
    _decor("flowerbox", draw_flower_box, _ax + 140, _ay - 40, seed=32)
    _decor("flowerbox", draw_flower_box, _ax + 140, _ay + 20, seed=33)
    # Framing
    _prop("potted_tree", draw_potted_tree, _ax - 200, _ay, seed=41)
    _prop("potted_tree", draw_potted_tree, _ax + 200, _ay, seed=42)
    _prop("sign", draw_hanging_sign, _ax + 30, _ay - 60, seed=40)
    _prop("bench", draw_wooden_bench, _ax, _ay + 70)

    # ── MERCHANT — center marketplace ────────────────────────────
    _mx, _my = _shop["merchant"]
    # Main stall cluster
    _prop("market_awning", draw_market_awning, _mx - 60, _my - 50, (36, 68, 108))
    _prop("market_awning", draw_market_awning, _mx + 80, _my - 50, (108, 68, 36))
    # Supply L behind stalls
    _hd_cart(_mx - 160, _my - 30)
    _hd_barrel(_mx - 160, _my + 30)
    _prop("sacks", draw_sack_pile, _mx - 100, _my + 30)
    # Display goods
    _prop("crate", draw_wood_crate, _mx + 160, _my - 30)
    _tasset(_mx + 160, _my + 30, "garlic_stand")
    _prop("crate", draw_wood_crate, _mx + 100, _my + 30)
    # Seating & info
    _prop("bench", draw_wooden_bench, _mx - 60, _my + 80)
    _prop("bench", draw_wooden_bench, _mx + 60, _my + 80, True)
    _prop("notice", draw_notice_board, _mx - 200, _my - 60)
    _prop("torch_stand", draw_torch_stand, _mx - 220, _my)
    _prop("torch_stand", draw_torch_stand, _mx + 220, _my)

    # ── LEATHERWORKER — east tanning yard ────────────────────────
    _lx, _ly = _shop["leatherworker"]
    # Tanning cluster (racks + trough in L)
    _prop("meat_rack", draw_meat_rack, _lx - 140, _ly - 60)
    _prop("meat_rack", draw_meat_rack, _lx - 140, _ly + 10)
    _prop("water_trough", draw_water_trough, _lx - 60, _ly + 10)
    # Supply side
    _prop("woodpile", draw_woodpile, _lx + 100, _ly - 50)
    _hd_hay(_lx + 100, _ly + 10)
    _hd_barrel(_lx + 140, _ly + 60)
    _prop("pottery", draw_pottery_stack, _lx + 40, _ly - 50, seed=80)
    _prop("bench", draw_wooden_bench, _lx, _ly + 70)
    _prop("torch_stand", draw_torch_stand, _lx - 200, _ly)
    _prop("torch_stand", draw_torch_stand, _lx + 200, _ly)

    # ── HERBALIST — southwest healing garden ─────────────────────
    _hx, _hy = _shop["herbalist"]
    # Garden bed cluster (planters in row + flowers)
    _prop("planter", draw_stone_planter, _hx - 140, _hy - 60, seed=50)
    _prop("planter", draw_stone_planter, _hx - 60, _hy - 60, seed=51)
    _prop("planter", draw_stone_planter, _hx + 20, _hy - 60, seed=55)
    # Side garden with trees
    _prop("potted_tree", draw_potted_tree, _hx + 140, _hy - 40, seed=52)
    _prop("potted_tree", draw_potted_tree, _hx - 180, _hy - 40, seed=56)
    # Supplies
    _prop("rain_barrel", draw_rain_barrel, _hx + 140, _hy + 30)
    _prop("bench", draw_wooden_bench, _hx - 100, _hy + 60)
    _prop("bench", draw_wooden_bench, _hx + 40, _hy + 60)
    _decor("flowerbox", draw_flower_box, _hx - 120, _hy + 90, seed=53)
    _decor("flowerbox", draw_flower_box, _hx - 40, _hy + 90, seed=54)
    _decor("flowerbox", draw_flower_box, _hx + 40, _hy + 90, seed=57)

    # ── MILLER — south-center grain yard ─────────────────────────
    _mlx, _mly = _shop["miller"]
    # Grain storage L-shape
    _prop("sacks", draw_sack_pile, _mlx - 140, _mly - 60)
    _prop("sacks", draw_sack_pile, _mlx - 140, _mly)
    _hd_barrel(_mlx - 60, _mly)
    _hd_barrel(_mlx - 60, _mly - 60)
    # Processing side
    _hd_hay(_mlx + 80, _mly - 40)
    _hd_hay(_mlx + 80, _mly + 20)
    _hd_cart(_mlx + 140, _mly + 60)
    _tasset(_mlx + 30, _mly - 60, "sweep_well")
    _prop("torch_stand", draw_torch_stand, _mlx - 200, _mly)
    _prop("torch_stand", draw_torch_stand, _mlx + 200, _mly)

    # ── COOPER — southeast barrel workshop ───────────────────────
    _cpx, _cpy = _shop["cooper"]
    # Barrel display cluster (stacked/grouped)
    _hd_barrel(_cpx - 120, _cpy - 60)
    _hd_barrel(_cpx - 80, _cpy - 50)
    _hd_barrel(_cpx - 40, _cpy - 60)
    _hd_barrel(_cpx - 100, _cpy)
    _hd_barrel(_cpx - 60, _cpy + 10)
    # Woodworking side
    _prop("woodpile", draw_woodpile, _cpx + 100, _cpy - 50)
    _prop("lumber", draw_lumber_stack, _cpx + 100, _cpy + 10)
    _prop("water_trough", draw_water_trough, _cpx + 140, _cpy + 60)
    _prop("bench", draw_wooden_bench, _cpx, _cpy + 70)
    _prop("torch_stand", draw_torch_stand, _cpx - 180, _cpy)
    _prop("torch_stand", draw_torch_stand, _cpx + 200, _cpy)

    # ── GUARD — south gate west barracks ─────────────────────────
    _gx, _gy = _shop["guard"]
    # Armory cluster (L-shape)
    _prop("weapon_rack", draw_weapon_rack, _gx - 140, _gy - 60)
    _prop("weapon_rack", draw_weapon_rack, _gx - 140, _gy)
    _prop("crate", draw_wood_crate, _gx - 60, _gy)
    _prop("crate", draw_wood_crate, _gx - 60, _gy - 60)
    # Punishment area
    _prop("stocks", draw_stocks, _gx + 80, _gy + 40)
    _tasset(_gx + 140, _gy + 40, "impaled_stake")
    # Guard posts
    _prop("banner", draw_banner_post, _gx - 200, _gy - 80, (130, 28, 24), (212, 184, 112))
    _prop("banner", draw_banner_post, _gx + 200, _gy - 80, (130, 28, 24), (212, 184, 112))
    _prop("torch_stand", draw_torch_stand, _gx - 220, _gy)
    _prop("torch_stand", draw_torch_stand, _gx + 220, _gy)

    # ── TANNER — south gate east hide yard ───────────────────────
    _tnx, _tny = _shop["tanner"]
    # Tanning rack cluster
    _prop("meat_rack", draw_meat_rack, _tnx - 140, _tny - 60)
    _prop("meat_rack", draw_meat_rack, _tnx - 140, _tny + 10)
    _prop("water_trough", draw_water_trough, _tnx - 60, _tny + 10)
    # Drying/supply side
    _hd_barrel(_tnx + 80, _tny - 50)
    _hd_barrel(_tnx + 80, _tny + 10)
    _prop("woodpile", draw_woodpile, _tnx + 140, _tny - 40)
    _prop("rain_barrel", draw_rain_barrel, _tnx + 140, _tny + 20)
    _prop("bench", draw_wooden_bench, _tnx, _tny + 70)
    _prop("torch_stand", draw_torch_stand, _tnx - 200, _tny)
    _prop("torch_stand", draw_torch_stand, _tnx + 200, _tny)

    # ═══════════════════════════════════════════════════════════════════
    # ARENA PROMENADE — center of town
    # ═══════════════════════════════════════════════════════════════════
    arena_cy_approx = plaza.centery + 40
    _prop("bench", draw_wooden_bench, center_x - 360, arena_cy_approx - 260)
    _prop("bench", draw_wooden_bench, center_x + 360, arena_cy_approx - 260, True)
    _prop("bench", draw_wooden_bench, center_x - 360, arena_cy_approx + 260)
    _prop("bench", draw_wooden_bench, center_x + 360, arena_cy_approx + 260, True)
    _prop("banner", draw_banner_post, center_x - 320, arena_cy_approx - 230, (92, 22, 18), (180, 170, 140))
    _prop("banner", draw_banner_post, center_x + 320, arena_cy_approx - 230, (92, 22, 18), (180, 170, 140))
    _prop("brazier", draw_brazier, center_x - 320, arena_cy_approx)
    _prop("brazier", draw_brazier, center_x + 320, arena_cy_approx)
    _prop("weapon_rack", draw_weapon_rack, center_x + 380, arena_cy_approx - 30)
    _prop("market_awning", draw_market_awning, center_x - 380, arena_cy_approx - 30, (128, 36, 28))

    # ═══════════════════════════════════════════════════════════════════
    # TOWN SQUARE — fire pit & well between church and arena
    # ═══════════════════════════════════════════════════════════════════
    _sq_y = (_fp_y + arena_cy_approx) // 2
    _prop("bench", draw_wooden_bench, center_x - 300, _sq_y - 40)
    _prop("bench", draw_wooden_bench, center_x + 300, _sq_y - 40, True)
    _prop("horse_hitch", draw_horse_hitch, center_x - 400, _sq_y)
    _prop("horse_hitch", draw_horse_hitch, center_x + 400, _sq_y)
    _prop("signpost", draw_signpost, center_x, _sq_y + 40, seed=120)
    _prop("notice", draw_notice_board, center_x - 350, _sq_y - 100)

    # ═══════════════════════════════════════════════════════════════════
    # FARMS — chicken coops, pig pens, sheep pens (2× scale)
    # ═══════════════════════════════════════════════════════════════════

    def _scale_farm(fn, surface, fx, fy, seed, factor=2.0):
        """Render a farm function at scaled-up size using render-to-texture."""
        tw, th = 600, 500
        temp = pygame.Surface((tw, th), pygame.SRCALPHA)
        rect = fn(temp, tw // 2, th // 2, seed=seed)
        nw, nh = int(tw * factor), int(th * factor)
        scaled = pygame.transform.smoothscale(temp, (nw, nh))
        surface.blit(scaled, (fx - nw // 2, fy - nh // 2))
        if rect:
            rx = fx - nw // 2 + int(rect.x * factor)
            ry = fy - nh // 2 + int(rect.y * factor)
            return pygame.Rect(rx, ry, int(rect.w * factor), int(rect.h * factor))
        return pygame.Rect(fx - 200, fy - 150, 400, 300)

    def _farm_prop(kind, fn, fx, fy, seed):
        """Place a 2×-scaled farm building."""
        _reg(kind, fx, fy)
        if not _deleted(kind, fx, fy):
            r = _scale_farm(fn, scene, int(fx), int(fy), seed)
            if r:
                obstacles.append(r.inflate(-12, -12))

    # Farm pen locations for runtime animated animals
    # Each entry: {"kind": str, "cx": int, "cy": int, "hw": int, "hh": int}
    # (world-space center and half-extents of the pen yard, after 2× scaling)
    farm_animal_pens: list = []

    # ── SOUTHWEST FARM (near herbalist) — enlarged + ornate ──
    _fsw = _farm_sw  # (1800, HORIZON_Y + 4600)
    # Stone path from road to farm
    _draw_stone_path(_fsw[0], _fsw[1] - 300, _fsw[0], _fsw[1] - 80, seed=50)
    # Farm sign
    _draw_farm_sign(_fsw[0], _fsw[1] - 260, "Raven's Roost Farm", seed=51)
    # Chicken coops (2× scaled, spread apart)
    _farm_prop("chicken_coop", draw_chicken_coop, _fsw[0] - 340, _fsw[1], seed=1)
    farm_animal_pens.append({"kind": "chicken", "cx": _fsw[0] - 340, "cy": _fsw[1], "hw": 200, "hh": 140})
    _farm_prop("chicken_coop", draw_chicken_coop, _fsw[0] + 340, _fsw[1] + 60, seed=2)
    farm_animal_pens.append({"kind": "chicken", "cx": _fsw[0] + 340, "cy": _fsw[1] + 60, "hw": 200, "hh": 140})
    # Pig pen (2× scaled)
    _farm_prop("pig_pen", draw_pig_pen, _fsw[0], _fsw[1] + 360, seed=1)
    farm_animal_pens.append({"kind": "pig", "cx": _fsw[0], "cy": _fsw[1] + 360, "hw": 180, "hh": 120})
    # Ornamental props
    _draw_scarecrow(_fsw[0] - 120, _fsw[1] + 140, seed=52)
    _draw_scarecrow(_fsw[0] + 180, _fsw[1] + 200, seed=53)
    _draw_wheelbarrow(_fsw[0] + 460, _fsw[1] + 100, seed=54)
    _draw_tool_rack(_fsw[0] - 460, _fsw[1] + 60, seed=55)
    _draw_milk_churn(_fsw[0] + 100, _fsw[1] + 460, seed=56)
    _draw_milk_churn(_fsw[0] + 120, _fsw[1] + 450, seed=57)
    _hd_hay(_fsw[0] - 400, _fsw[1] + 120)
    _hd_hay(_fsw[0] - 380, _fsw[1] + 140)
    _hd_hay(_fsw[0] + 400, _fsw[1] + 120)
    _prop("water_trough", draw_water_trough, _fsw[0] - 160, _fsw[1] + 480)
    _prop("water_trough", draw_water_trough, _fsw[0] + 240, _fsw[1] + 460)
    # (standalone decorative fence segments removed — each pen has its own circling fence now)
    _prop("torch_stand", draw_torch_stand, _fsw[0] - 540, _fsw[1])
    _prop("torch_stand", draw_torch_stand, _fsw[0] + 500, _fsw[1])
    _prop("woodpile", draw_woodpile, _fsw[0] + 500, _fsw[1] + 300)
    _prop("woodpile", draw_woodpile, _fsw[0] - 500, _fsw[1] + 300)
    _decor("flowerbox", draw_flower_box, _fsw[0] - 340, _fsw[1] - 180, seed=58)
    _decor("flowerbox", draw_flower_box, _fsw[0] + 340, _fsw[1] - 180, seed=59)
    _prop("bench", draw_wooden_bench, _fsw[0], _fsw[1] - 200)
    _draw_stone_path(_fsw[0] - 340, _fsw[1] + 80, _fsw[0] + 340, _fsw[1] + 80, seed=60)
    _draw_stone_path(_fsw[0], _fsw[1] + 80, _fsw[0], _fsw[1] + 360, seed=61)

    # ── SOUTHEAST FARM (near cooper) — enlarged + ornate ──
    _fse = _farm_se  # (8200, HORIZON_Y + 4600)
    # Stone path approach
    _draw_stone_path(_fse[0], _fse[1] - 320, _fse[0], _fse[1] - 80, seed=70)
    # Farm sign
    _draw_farm_sign(_fse[0], _fse[1] - 280, "Shepherd's Meadow", seed=71)
    # Sheep pens (2× scaled, spread apart)
    _farm_prop("sheep_pen", draw_sheep_pen, _fse[0] - 380, _fse[1], seed=1)
    farm_animal_pens.append({"kind": "sheep", "cx": _fse[0] - 380, "cy": _fse[1], "hw": 220, "hh": 150})
    _farm_prop("sheep_pen", draw_sheep_pen, _fse[0] + 100, _fse[1] + 100, seed=2)
    farm_animal_pens.append({"kind": "sheep", "cx": _fse[0] + 100, "cy": _fse[1] + 100, "hw": 220, "hh": 150})
    # Chicken coop (2× scaled)
    _farm_prop("chicken_coop", draw_chicken_coop, _fse[0] + 460, _fse[1] + 60, seed=3)
    farm_animal_pens.append({"kind": "chicken", "cx": _fse[0] + 460, "cy": _fse[1] + 60, "hw": 200, "hh": 140})
    # Ornamental props
    _draw_scarecrow(_fse[0] - 160, _fse[1] + 200, seed=72)
    _draw_wheelbarrow(_fse[0] - 520, _fse[1] + 100, seed=73)
    _draw_tool_rack(_fse[0] + 560, _fse[1] + 60, seed=74)
    _draw_milk_churn(_fse[0] - 80, _fse[1] + 400, seed=75)
    _draw_milk_churn(_fse[0] - 60, _fse[1] + 410, seed=76)
    _hd_hay(_fse[0] + 300, _fse[1] - 60)
    _hd_hay(_fse[0] + 320, _fse[1] - 40)
    _hd_hay(_fse[0] - 460, _fse[1] + 200)
    _prop("water_trough", draw_water_trough, _fse[0] - 180, _fse[1] + 420)
    _prop("water_trough", draw_water_trough, _fse[0] + 300, _fse[1] + 400)
    # (standalone decorative fence segments removed — each pen has its own circling fence now)
    _prop("torch_stand", draw_torch_stand, _fse[0] - 580, _fse[1])
    _prop("torch_stand", draw_torch_stand, _fse[0] + 620, _fse[1])
    _prop("woodpile", draw_woodpile, _fse[0] - 560, _fse[1] + 380)
    _prop("woodpile", draw_woodpile, _fse[0] + 560, _fse[1] + 380)
    _decor("flowerbox", draw_flower_box, _fse[0] - 380, _fse[1] - 200, seed=77)
    _decor("flowerbox", draw_flower_box, _fse[0] + 460, _fse[1] - 200, seed=78)
    _prop("bench", draw_wooden_bench, _fse[0], _fse[1] - 240, True)
    _draw_stone_path(_fse[0] - 380, _fse[1] + 80, _fse[0] + 460, _fse[1] + 80, seed=79)
    _draw_stone_path(_fse[0], _fse[1] + 80, _fse[0], _fse[1] + 380, seed=80)

    # ── MID-WEST PIG FARM (between alchemist and herbalist) — enlarged + ornate ──
    _pig_mid = (1600, HORIZON_Y + 3200)
    # Stone path approach
    _draw_stone_path(_pig_mid[0], _pig_mid[1] - 280, _pig_mid[0], _pig_mid[1] - 60, seed=90)
    # Farm sign
    _draw_farm_sign(_pig_mid[0], _pig_mid[1] - 240, "Mudfoot Sty", seed=91)
    # Pig pens (2× scaled, spread apart)
    _farm_prop("pig_pen", draw_pig_pen, _pig_mid[0] - 240, _pig_mid[1], seed=3)
    farm_animal_pens.append({"kind": "pig", "cx": _pig_mid[0] - 240, "cy": _pig_mid[1], "hw": 180, "hh": 120})
    _farm_prop("pig_pen", draw_pig_pen, _pig_mid[0] + 320, _pig_mid[1] + 60, seed=4)
    farm_animal_pens.append({"kind": "pig", "cx": _pig_mid[0] + 320, "cy": _pig_mid[1] + 60, "hw": 180, "hh": 120})
    # Ornamental props
    _draw_scarecrow(_pig_mid[0] + 60, _pig_mid[1] + 180, seed=92)
    _draw_wheelbarrow(_pig_mid[0] - 400, _pig_mid[1] + 80, seed=93)
    _draw_tool_rack(_pig_mid[0] + 480, _pig_mid[1] + 60, seed=94)
    _hd_hay(_pig_mid[0] - 340, _pig_mid[1] + 140)
    _hd_hay(_pig_mid[0] + 400, _pig_mid[1] + 140)
    _prop("water_trough", draw_water_trough, _pig_mid[0] + 80, _pig_mid[1] + 280)
    _prop("water_trough", draw_water_trough, _pig_mid[0] - 180, _pig_mid[1] + 260)
    # (standalone decorative fence segments removed — each pen has its own circling fence now)
    _prop("torch_stand", draw_torch_stand, _pig_mid[0] - 420, _pig_mid[1])
    _prop("torch_stand", draw_torch_stand, _pig_mid[0] + 520, _pig_mid[1])
    _prop("woodpile", draw_woodpile, _pig_mid[0] - 420, _pig_mid[1] + 200)
    _draw_milk_churn(_pig_mid[0] - 280, _pig_mid[1] + 200, seed=95)
    _draw_stone_path(_pig_mid[0] - 240, _pig_mid[1] + 80, _pig_mid[0] + 320, _pig_mid[1] + 80, seed=96)
    _decor("flowerbox", draw_flower_box, _pig_mid[0] - 240, _pig_mid[1] - 160, seed=97)
    _prop("bench", draw_wooden_bench, _pig_mid[0] + 100, _pig_mid[1] - 180)

    # ═══════════════════════════════════════════════════════════════════
    # CEMETERY — south-center, between guard/tanner area and gate
    # ═══════════════════════════════════════════════════════════════════
    _cem_x, _cem_y = _cemetery_pos
    _cem_top_y = _cem_y - 120
    _cem_rect = pygame.Rect(_cem_x - 270, _cem_top_y, 540, 380)
    _cem_rng = random.Random(88014)

    # Ground patch: darker soil + gravel + sparse dead grass (no clean ellipse)
    _cg = pygame.Surface((_cem_rect.width, _cem_rect.height), pygame.SRCALPHA)
    pygame.draw.rect(_cg, (54, 50, 46, 190), _cg.get_rect(), border_radius=28)
    pygame.draw.rect(_cg, (46, 42, 38, 170), _cg.get_rect().inflate(-18, -12), border_radius=26)
    for _ in range(560):
        px = _cem_rng.randint(12, _cem_rect.width - 12)
        py = _cem_rng.randint(12, _cem_rect.height - 12)
        if _cem_rng.random() < 0.60:
            sv = 72 + _cem_rng.randint(-14, 12)
            pygame.draw.circle(_cg, (sv, sv, sv + 2, _cem_rng.randint(30, 85)), (px, py), 1)
        else:
            g = 52 + _cem_rng.randint(-10, 16)
            pygame.draw.line(_cg, (g - 18, g + 8, g - 22, _cem_rng.randint(35, 70)),
                             (px, py), (px + _cem_rng.randint(-2, 2), py - _cem_rng.randint(3, 7)), 1)
    for _ in range(10):
        mx = _cem_rng.randint(18, _cem_rect.width - 80)
        my = _cem_rng.randint(40, _cem_rect.height - 60)
        mw = _cem_rng.randint(36, 110)
        mh = _cem_rng.randint(18, 54)
        pygame.draw.ellipse(_cg, (34, 30, 26, 70), (mx, my, mw, mh))
    scene.blit(_cg, _cem_rect.topleft)

    # Central cobble path + two cross aisles
    _main_path = pygame.Rect(_cem_x - 26, _cem_rect.top + 18, 52, _cem_rect.height - 46)
    pygame.draw.rect(scene, (62, 62, 66), _main_path, border_radius=14)
    draw_cobblestones(scene, _main_path.inflate(-8, -8), seed=141)
    pygame.draw.rect(scene, (34, 34, 38), _main_path, 2, border_radius=14)
    _aisles = [
        pygame.Rect(_cem_rect.left + 34, _cem_rect.top + 120, _cem_rect.width - 68, 40),
        pygame.Rect(_cem_rect.left + 34, _cem_rect.top + 200, _cem_rect.width - 68, 40),
    ]
    for _ai, _ar in enumerate(_aisles):
        pygame.draw.rect(scene, (60, 60, 64), _ar, border_radius=12)
        draw_cobblestones(scene, _ar.inflate(-8, -8), seed=200 + _ai)
        pygame.draw.rect(scene, (32, 32, 36), _ar, 2, border_radius=12)

    # Perimeter stone curb + iron fence (decor)
    def _cem_stone_wall(wr: pygame.Rect, seed: int) -> None:
        rng = random.Random(seed)
        pygame.draw.rect(scene, (72, 70, 66), wr, border_radius=3)
        for by in range(wr.top + 2, wr.bottom - 2, 10):
            off = 10 if ((by - wr.top) // 10) % 2 else 0
            for bx in range(wr.left + 2 + off, wr.right - 8, 20):
                bw = min(18, wr.right - bx - 2)
                sv = 74 + rng.randint(-8, 10)
                pygame.draw.rect(scene, (sv, sv - 2, sv - 6), (bx, by, bw, 8), border_radius=2)
                pygame.draw.rect(scene, (42, 40, 36), (bx, by, bw, 8), 1, border_radius=2)
        pygame.draw.rect(scene, (38, 36, 32), wr, 2, border_radius=3)
        # moss at bottom edge
        if wr.width > 16:
            for _ in range(10):
                if rng.random() > 0.6:
                    mx = rng.randint(wr.left + 6, wr.right - 10)
                    pygame.draw.circle(scene, (38, 70, 32), (mx, wr.bottom - 2), 2)

    _wall_th = 12
    _gate_gap = 124
    _gate_l = _cem_x - _gate_gap // 2
    _gate_r = _cem_x + _gate_gap // 2
    _cem_stone_wall(pygame.Rect(_cem_rect.left, _cem_rect.top, _gate_l - _cem_rect.left, _wall_th), 9901)
    _cem_stone_wall(pygame.Rect(_gate_r, _cem_rect.top, _cem_rect.right - _gate_r, _wall_th), 9902)
    _cem_stone_wall(pygame.Rect(_cem_rect.left, _cem_rect.bottom - _wall_th, _cem_rect.width, _wall_th), 9903)
    _cem_stone_wall(pygame.Rect(_cem_rect.left, _cem_rect.top, _wall_th, _cem_rect.height), 9904)
    _cem_stone_wall(pygame.Rect(_cem_rect.right - _wall_th, _cem_rect.top, _wall_th, _cem_rect.height), 9905)

    _f_y = _cem_rect.top + _wall_th - 1
    _f_left_len = max(0, (_gate_l - (_cem_rect.left + _wall_th + 6)))
    _f_right_len = max(0, ((_cem_rect.right - _wall_th - 6) - _gate_r))
    if _f_left_len >= 26:
        draw_iron_fence(scene, _cem_rect.left + _wall_th + 6, _f_y, _f_left_len)
    if _f_right_len >= 26:
        draw_iron_fence(scene, _gate_r + 2, _f_y, _f_right_len)
    draw_iron_fence(scene, _cem_rect.left + _wall_th + 6, _cem_rect.bottom - 4, _cem_rect.width - _wall_th * 2 - 12)
    draw_iron_fence_vertical(scene, _cem_rect.left + 6, _cem_rect.centery, _cem_rect.height - 28)
    draw_iron_fence_vertical(scene, _cem_rect.right - 6, _cem_rect.centery, _cem_rect.height - 28)

    # Gate entrance (decorative; don't block path)
    _decor("cemetery_gate", draw_cemetery_gate, _cem_x, _cem_rect.top + 2)

    # Mausoleum at the back
    _prop("mausoleum", draw_cemetery_mausoleum, _cem_x, _cem_rect.bottom - 8, seed=7331)

    # Dead trees + torches
    _decor("dead_tree", draw_dead_tree, _cem_rect.left + 70, _cem_rect.top + 160, scale=0.75)
    _decor("dead_tree", draw_dead_tree, _cem_rect.right - 78, _cem_rect.top + 180, scale=0.70)
    _prop("torch_stand", draw_torch_stand, _cem_rect.left + 44, _cem_rect.top + 22)
    _prop("torch_stand", draw_torch_stand, _cem_rect.right - 44, _cem_rect.top + 22)

    # Gravestones — denser, varied, and kept off the main path
    _grave_cols_l = [_cem_x - 158, _cem_x - 102, _cem_x - 48]
    _grave_cols_r = [_cem_x + 48, _cem_x + 102, _cem_x + 158]
    _grave_rows = [(_cem_rect.top + 88), (_cem_rect.top + 138), (_cem_rect.top + 168),
                   (_cem_rect.top + 248), (_cem_rect.top + 298)]
    _gi = 0
    for gy in _grave_rows:
        for gx in (_grave_cols_l + _grave_cols_r):
            if _cem_rng.random() < 0.12:
                continue
            px = gx + _cem_rng.randint(-7, 7)
            py = gy + _cem_rng.randint(-6, 6)
            if _main_path.inflate(22, 26).collidepoint(px, py):
                continue
            if any(_ar.inflate(18, 18).collidepoint(px, py) for _ar in _aisles):
                continue
            _prop("grave", draw_grave_stone, px, py, _gi)
            # Tiny offerings
            if _cem_rng.random() > 0.82:
                ox = px + _cem_rng.randint(-8, 8)
                oy = py + _cem_rng.randint(-6, 2)
                pygame.draw.circle(scene, (222, 210, 188), (ox, oy), 2)
                pygame.draw.circle(scene, (160, 140, 120), (ox, oy), 2, 1)
                pygame.draw.circle(scene, (255, 170, 60), (ox, oy - 4), 2)
            if _cem_rng.random() > 0.86:
                fx = px + _cem_rng.randint(-10, 10)
                fy = py + _cem_rng.randint(-10, 0)
                pygame.draw.circle(scene, (210, 90, 90), (fx, fy), 2)
                pygame.draw.circle(scene, (240, 220, 120), (fx + 2, fy - 1), 1)
            _gi += 1

    # Crosses and benches for visitors
    _tasset(_cem_x - 170, _cem_rect.top + 232, "troita")
    _tasset(_cem_x + 170, _cem_rect.top + 232, "troita")
    _prop("bench", draw_wooden_bench, _cem_x - 70, _cem_rect.bottom - 32, False)
    _prop("bench", draw_wooden_bench, _cem_x + 70, _cem_rect.bottom - 32, True)

    # ═══════════════════════════════════════════════════════════════════
    # RESIDENTIAL VIGNETTES — clustered prop scenes along house rows
    # 6 template types instead of mechanical mod-3 repetition
    # ═══════════════════════════════════════════════════════════════════
    _res_rng = random.Random(555)
    # Vignette templates: each is a function of (base_x, base_y, flip)
    def _vignette_woodshed(bx, by, flip):
        """Woodpile + chopping block + potted tree"""
        d = -1 if flip else 1
        _prop("woodpile", draw_woodpile, bx, by)
        _prop("lumber", draw_lumber_stack, bx + d * 80, by + 10)
        _prop("potted_tree", draw_potted_tree, bx + d * 40, by - 50, seed=bx + by)

    def _vignette_sitting(bx, by, flip):
        """Bench + flower box + rain barrel"""
        d = -1 if flip else 1
        _prop("bench", draw_wooden_bench, bx, by, flip)
        _decor("flowerbox", draw_flower_box, bx + d * 60, by - 30, seed=bx)
        _prop("rain_barrel", draw_rain_barrel, bx + d * 90, by + 20)

    def _vignette_storage(bx, by, flip):
        """Barrel cluster + crate + sacks"""
        d = -1 if flip else 1
        _hd_barrel(bx, by)
        _hd_barrel(bx + d * 35, by + 8)
        _prop("crate", draw_wood_crate, bx + d * 70, by - 10)
        _prop("sacks", draw_sack_pile, bx - d * 30, by + 20)

    def _vignette_merchant(bx, by, flip):
        """Market awning + sacks + cart"""
        d = -1 if flip else 1
        _prop("market_awning", draw_market_awning, bx, by, (120 + _res_rng.randint(0, 40), 80, 36))
        _prop("sacks", draw_sack_pile, bx + d * 80, by + 20)
        _hd_cart(bx - d * 60, by + 10)

    def _vignette_garden(bx, by, flip):
        """Planters + flower boxes + potted tree"""
        d = -1 if flip else 1
        _prop("planter", draw_stone_planter, bx, by, seed=bx + by)
        _decor("flowerbox", draw_flower_box, bx + d * 70, by, seed=bx + 1)
        _decor("flowerbox", draw_flower_box, bx + d * 70, by + 30, seed=bx + 2)
        _prop("potted_tree", draw_potted_tree, bx - d * 40, by - 20, seed=bx)

    def _vignette_guard(bx, by, flip):
        """Torch stand + weapon rack + banner"""
        d = -1 if flip else 1
        _prop("torch_stand", draw_torch_stand, bx, by)
        _prop("weapon_rack", draw_weapon_rack, bx + d * 80, by + 10)
        _prop("banner", draw_banner_post, bx - d * 40, by - 30, (100, 28, 24), (180, 160, 120))

    _vignettes = [_vignette_woodshed, _vignette_sitting, _vignette_storage,
                  _vignette_merchant, _vignette_garden, _vignette_guard]

    # Left residential column
    for _ri, _ry_off in enumerate(range(500, 5400, 360)):
        _ry = HORIZON_Y + _ry_off
        _vf = _vignettes[_ri % len(_vignettes)]
        _vf(300, _ry, False)

    # Right residential column
    for _ri, _ry_off in enumerate(range(500, 5400, 360)):
        _ry = HORIZON_Y + _ry_off
        _vf = _vignettes[(_ri + 3) % len(_vignettes)]  # offset so left/right differ
        _vf(width - 300, _ry, True)

    # Flower boxes between top row houses
    for _fbi, _fbx in enumerate(range(295, width - 300, 460)):
        _decor("flowerbox", draw_flower_box, _fbx, plaza.top + 90, seed=300 + _fbi)
    # Flower boxes between bottom row houses
    for _fbi, _fbx in enumerate(range(295, width - 300, 460)):
        _decor("flowerbox", draw_flower_box, _fbx, plaza.bottom - 80, seed=350 + _fbi)
    # Wall torches along upper houses
    for _wti, _wtx in enumerate(range(410, width - 410, 460)):
        _decor("wall_torch", draw_wall_torch, _wtx, plaza.top + 60)

    # Additional scattered vignettes in open areas between districts
    _scatter_spots = [
        (center_x - 1600, HORIZON_Y + 1200, False),
        (center_x + 1600, HORIZON_Y + 1200, True),
        (center_x - 2000, HORIZON_Y + 3400, False),
        (center_x + 2000, HORIZON_Y + 3400, True),
        (center_x - 800, HORIZON_Y + 4400, False),
        (center_x + 800, HORIZON_Y + 4400, True),
    ]
    for _si, (_svx, _svy, _sflip) in enumerate(_scatter_spots):
        _vignettes[_si % len(_vignettes)](_svx, _svy, _sflip)

    # ═══════════════════════════════════════════════════════════════════
    # NORTH WALL GUARD POSTS
    # ═══════════════════════════════════════════════════════════════════
    _prop("weapon_rack", draw_weapon_rack, plaza.left + 180, HORIZON_Y + 340)
    _prop("crate", draw_wood_crate, plaza.left + 280, HORIZON_Y + 340)
    _hd_barrel(plaza.left + 380, HORIZON_Y + 340)
    _prop("weapon_rack", draw_weapon_rack, plaza.right - 180, HORIZON_Y + 340)
    _prop("crate", draw_wood_crate, plaza.right - 280, HORIZON_Y + 340)
    _hd_barrel(plaza.right - 380, HORIZON_Y + 340)
    _prop("banner", draw_banner_post, 200, HORIZON_Y + 300, (130, 28, 24), (212, 184, 112))
    _prop("banner", draw_banner_post, width - 200, HORIZON_Y + 300, (130, 28, 24), (212, 184, 112))
    _decor("wall_torch", draw_wall_torch, plaza.left + 120, HORIZON_Y + 280)
    _decor("wall_torch", draw_wall_torch, plaza.right - 120, HORIZON_Y + 280)

    # ═══════════════════════════════════════════════════════════════════
    # CONNECTING ELEMENTS — corner planters, path trees
    # ═══════════════════════════════════════════════════════════════════
    _prop("planter", draw_stone_planter, plaza.left + 220, plaza.top + 200, seed=200)
    _prop("planter", draw_stone_planter, plaza.right - 220, plaza.top + 200, seed=201)
    _prop("planter", draw_stone_planter, plaza.left + 220, plaza.bottom - 200, seed=202)
    _prop("planter", draw_stone_planter, plaza.right - 220, plaza.bottom - 200, seed=203)
    # Execution props near south
    _tasset(center_x - 600, height - 700, "impaled_stake")
    _tasset(center_x + 600, height - 700, "impaled_stake")
    _tasset(center_x - 300, height - 650, "execution_block")

    # ═══════════════════════════════════════════════════════════════════
    # ADDITIONAL MEDIEVAL PROPS — scattered for cohesion
    # ═══════════════════════════════════════════════════════════════════
    # Fountain near the church approach
    _prop("fountain", draw_fountain, center_x + 360, HORIZON_Y + 520)
    # Gallows in the justice district (south-west)
    _prop("gallows", draw_gallows, center_x - 1200, height - 1400)
    _prop("stocks", draw_stocks, center_x - 1100, height - 1340)
    # Market carts along the main avenue
    _prop("market_cart", draw_market_cart, center_x - 500, HORIZON_Y + 1600, 0.9)
    _prop("market_cart", draw_market_cart, center_x + 500, HORIZON_Y + 1800, 1.0)
    _prop("market_cart", draw_market_cart, center_x - 300, HORIZON_Y + 2800, 0.85)
    # Water pumps (practical medieval utility)
    _prop("water_pump", draw_water_pump, center_x - 900, HORIZON_Y + 1100)
    _prop("water_pump", draw_water_pump, center_x + 1400, HORIZON_Y + 2200)
    # Additional notice boards for medieval flavour
    _prop("notice", draw_notice_board, center_x - 400, HORIZON_Y + 600)
    _prop("notice", draw_notice_board, center_x + 800, HORIZON_Y + 2400)
    # Extra benches for rest stops along roads
    _prop("bench", draw_wooden_bench, center_x - 600, HORIZON_Y + 1200)
    _prop("bench", draw_wooden_bench, center_x + 600, HORIZON_Y + 1200, True)
    _prop("bench", draw_wooden_bench, center_x - 200, HORIZON_Y + 2200)
    _prop("bench", draw_wooden_bench, center_x + 200, HORIZON_Y + 2200, True)
    # Horse hitches along main streets
    _prop("horse_hitch", draw_horse_hitch, center_x - 700, HORIZON_Y + 900)
    _prop("horse_hitch", draw_horse_hitch, center_x + 700, HORIZON_Y + 1400)
    # Training dummies near the fire pit (town militia practice)
    _prop("training_dummy", draw_training_dummy, center_x + 800, HORIZON_Y + 3200)
    _prop("training_dummy", draw_training_dummy, center_x + 900, HORIZON_Y + 3250)
    # Meat racks near the harbor district
    _prop("meat_rack", draw_meat_rack, center_x + 1600, HORIZON_Y + 2800)
    _prop("meat_rack", draw_meat_rack, center_x + 1700, HORIZON_Y + 2850)
    # Pottery stacks near artisan area
    _prop("pottery", draw_pottery_stack, center_x - 1500, HORIZON_Y + 2000, seed=90)
    _prop("pottery", draw_pottery_stack, center_x - 1400, HORIZON_Y + 2050, seed=91)
    # Wine racks near the tavern/merchant area
    _prop("wine_rack", draw_wine_rack, center_x + 1100, HORIZON_Y + 1600)
    # Scattered woodpiles
    _prop("woodpile", draw_woodpile, center_x - 1800, HORIZON_Y + 1600)
    _prop("woodpile", draw_woodpile, center_x + 1800, HORIZON_Y + 3000)
    _prop("woodpile", draw_woodpile, center_x - 600, HORIZON_Y + 4200)
    # Sack piles near storage areas
    _prop("sack_pile", draw_sack_pile, center_x - 1300, HORIZON_Y + 1800)
    _prop("sack_pile", draw_sack_pile, center_x + 1300, HORIZON_Y + 2600)
    # Hay bales near farm areas
    _prop("hay", draw_hay_bale, center_x - 2200, HORIZON_Y + 2400)
    _prop("hay", draw_hay_bale, center_x + 2200, HORIZON_Y + 2400)
    _prop("hay", draw_hay_bale, center_x - 2100, HORIZON_Y + 2450)
    # Extra signposts for wayfinding
    _prop("signpost", draw_signpost, center_x, HORIZON_Y + 1000, seed=700)
    _prop("signpost", draw_signpost, center_x - 1000, HORIZON_Y + 3000, seed=701)
    _prop("signpost", draw_signpost, center_x + 1000, HORIZON_Y + 3600, seed=702)

    # ═══════════════════════════════════════════════════════════════════
    # PHASE-2 CIVIC LANDMARKS — drawn near-last so nothing paints over them
    # ═══════════════════════════════════════════════════════════════════
    # Town hall presiding over the market square, stocks out front
    _prop("town_hall", draw_town_hall, _townhall_pos[0], _townhall_pos[1], seed=4501)
    _prop("stocks", draw_stocks, _stocks_sq_pos[0], _stocks_sq_pos[1])
    # Windmill on its knoll + raised granary out by the west farmland
    _prop("windmill", draw_windmill, _windmill_pos[0], _windmill_pos[1], seed=4503)
    _prop("granary", draw_granary, _granary_pos[0], _granary_pos[1], seed=4504)
    # Communal washhouse (lavoir) on the harbour bank
    _prop("washhouse", draw_washhouse, _washhouse_pos[0], _washhouse_pos[1], seed=4505)
    # Wayside shrines at the road junctions
    for _shi, (_shx, _shy) in enumerate(_shrine_spots):
        _prop("shrine", draw_wayside_shrine, _shx, _shy, seed=4510 + _shi)

    # ── TOWN DEFENCES — south curtain wall flanking the gate + palisades ──
    # (registered off-centre so its delete anchor doesn't collide with the gate's)
    _reg("south_wall", center_x - 1500, _south_wall_gy)
    if not _deleted("south_wall", center_x - 1500, _south_wall_gy):
        draw_stone_curtain_wall(scene, 80, center_x - 188, _south_wall_gy, seed=61)
        draw_stone_curtain_wall(scene, center_x + 188, width - 80, _south_wall_gy, seed=62)
        obstacles.append(pygame.Rect(80, _south_wall_gy - 92, (center_x - 188) - 80, 86))
        obstacles.append(pygame.Rect(center_x + 188, _south_wall_gy - 92, (width - 80) - (center_x + 188), 86))
    _reg("palisade_w", 110, HORIZON_Y + 3000)
    if not _deleted("palisade_w", 110, HORIZON_Y + 3000):
        draw_palisade_v(scene, 110, wall_y + 110, _south_wall_gy - 100, seed=63)
        obstacles.append(pygame.Rect(96, wall_y + 110, 28, (_south_wall_gy - 100) - (wall_y + 110)))
    _reg("palisade_e", width - 110, HORIZON_Y + 3000)
    if not _deleted("palisade_e", width - 110, HORIZON_Y + 3000):
        _pal_ex = width - 110
        # the harbour water interrupts the east run — the sea closes the circuit
        draw_palisade_v(scene, _pal_ex, wall_y + 110, _harbour_rect.top - 14, seed=64)
        draw_palisade_v(scene, _pal_ex, _harbour_rect.bottom + 14, _south_wall_gy - 100, seed=65)
        obstacles.append(pygame.Rect(_pal_ex - 14, wall_y + 110, 28, (_harbour_rect.top - 14) - (wall_y + 110)))
        obstacles.append(pygame.Rect(_pal_ex - 14, _harbour_rect.bottom + 14, 28,
                                     (_south_wall_gy - 100) - (_harbour_rect.bottom + 14)))

    # ═══════════════════════════════════════════════════════════════════
    # PHASE-4 LIFE & CLUTTER — festival bunting, wall braziers, street
    # banners, ambient birds, junction clutter, gate notice board
    # ═══════════════════════════════════════════════════════════════════
    # Festival bunting over the square's north entry + along the stall lane
    _reg("bunting", _sq_cx, _plaza_core.top - 12)
    if not _deleted("bunting", _sq_cx, _plaza_core.top - 12):
        _draw_bunting_span(scene, _sq_cx - 140, _sq_cx + 140, _plaza_core.top - 12, seed=71)
    _reg("bunting", _sq_cx + 335, _sq_cy - 15)
    if not _deleted("bunting", _sq_cx + 335, _sq_cy - 15):
        _draw_bunting_span(scene, _sq_cx + 180, _sq_cx + 490, _sq_cy - 15, seed=72)

    # Watch braziers burning along the south wall walk
    for _bz_x in list(range(700, center_x - 420, 900)) + list(range(center_x + 500, width - 600, 900)):
        _decor("wall_brazier", draw_brazier, _bz_x, _south_wall_gy - 96)

    # Heraldic banner posts lining the high street near the square
    for _bp_x, _bp_y, _bp_cols in ((center_x - 130, HORIZON_Y + 1450, ((130, 28, 24), (212, 184, 112))),
                                   (center_x + 130, HORIZON_Y + 1450, ((36, 60, 130), (200, 196, 180))),
                                   (center_x - 130, HORIZON_Y + 2650, ((36, 60, 130), (200, 196, 180))),
                                   (center_x + 130, HORIZON_Y + 2650, ((130, 28, 24), (212, 184, 112)))):
        _reg("banner_post", _bp_x, _bp_y)
        if not _deleted("banner_post", _bp_x, _bp_y):
            obstacles.append(draw_banner_post(scene, _bp_x, _bp_y, _bp_cols[0], _bp_cols[1]))

    # Ambient birds: pigeons working the square, gulls loafing at the harbour
    for _pg_i, (_pg_x, _pg_y) in enumerate(((_sq_cx - 70, _sq_cy + 150), (_sq_cx + 96, _sq_cy - 168),
                                            (_sq_cx - 238, _sq_cy + 62), (_sq_cx + 34, _sq_cy + 212))):
        _draw_small_bird(scene, _pg_x, _pg_y, kind="pigeon", seed=81 + _pg_i)
    for _gl_i, (_gl_x, _gl_y) in enumerate(((_harbour_x + 88, _harbour_top + 196),
                                            (_harbour_x + 64, _harbour_top + 494),
                                            (_washhouse_pos[0] - 28, _washhouse_pos[1] - 184))):
        _draw_small_bird(scene, _gl_x, _gl_y, kind="gull", seed=91 + _gl_i)

    # Junction clutter + traffic wear where the high street crosses the EW roads
    _jrng = random.Random(60606)
    for _jn_y in (_road_y_n, _road_y_m, _road_y_s):
        for _ in range(14):
            _ws3 = pygame.Surface((26, 11), pygame.SRCALPHA)
            pygame.draw.ellipse(_ws3, (50, 44, 36, _jrng.randint(18, 34)), (0, 0, 26, 11))
            scene.blit(_ws3, (center_x + _jrng.randint(-90, 90) - 13, _jn_y + _jrng.randint(-40, 40) - 5))
        _prop("hd_barrel", draw_hd_barrel, center_x - 185, _jn_y + 118)
        _prop("crate", draw_wood_crate, center_x - 150, _jn_y + 134)

    # Notice board just inside the south gate (wanted posters for arrivals)
    _prop("notice", draw_notice_board, center_x - 280, _south_wall_gy - 150)

    # ── Town Gate to the Wilderness (south) ──
    gate_x = center_x
    gate_y = height - 460   # near bottom of town (460px from south edge)
    _reg("town_gate", gate_x, gate_y)
    if not _deleted("town_gate", gate_x, gate_y):
        _draw_town_wilderness_gate(scene, gate_x, gate_y)
        # Gate collision (block walking through the wall, but leave archway open)
        obstacles.append(pygame.Rect(gate_x - 200, gate_y - 110, 130, 100))
        obstacles.append(pygame.Rect(gate_x + 70, gate_y - 110, 130, 100))

    mist = pygame.Surface(size, pygame.SRCALPHA)
    pygame.draw.ellipse(mist, (180, 185, 195, 16), (plaza.left + 120, plaza.top + 80, plaza.width - 240, plaza.height - 120))
    pygame.draw.rect(mist, (8, 10, 18, 28), (0, 0, width, height))
    scene.blit(mist, (0, 0))

    # Remove obstacles that overlap roads so the player can walk freely on them
    _clean_obs: list = []
    for _ob in obstacles:
        _ob_cx = _ob.centerx
        _ob_cy = _ob.centery
        if _on_road(_ob_cx, _ob_cy):
            continue
        _clean_obs.append(_ob)
    obstacles = _clean_obs

    # Drop runtime animals for any pen whose prop was deleted, so deleting a pen
    # also removes its animals instead of leaving them floating in empty mud.
    _pen_prop_kind = {"pig": "pig_pen", "chicken": "chicken_coop", "sheep": "sheep_pen"}
    farm_animal_pens = [
        _pen for _pen in farm_animal_pens
        if not _deleted(_pen_prop_kind.get(str(_pen.get("kind", "")), ""),
                        _pen.get("cx", 0), _pen.get("cy", 0))
    ]

    # Export real chimney tops + landmark footprints for runtime systems
    # (smoke VFX, debug renders). Module-level so the 8-tuple API stays put.
    global _TOWN_CHIMNEY_TOPS, _TOWN_LANDMARK_RECTS
    _TOWN_CHIMNEY_TOPS = list(_chimney_tops)
    _TOWN_LANDMARK_RECTS = [pygame.Rect(_lr) for _lr in _landmark_rects]

    return scene, obstacles, canal_rects, prop_registry, house_overlays, foliage_anim_positions, _road_rects, farm_animal_pens


def build_wilderness_scene(size: Tuple[int, int]) -> Tuple[pygame.Surface, List[pygame.Rect], List[Vector2]]: # Fixed
    scene = pygame.Surface(size).convert()
    width, height = size
    center_x = int(width) // 2
    # Scale counts based on area relative to original size
    area_factor = (width * height) / (3200 * 2200)
    rng = random.Random(112)

    draw_vertical_gradient(scene, pygame.Rect(0, 0, width, HORIZON_Y + 62), (8, 14, 28), (46, 58, 74))
    draw_vertical_gradient(scene, pygame.Rect(0, HORIZON_Y, width, height - HORIZON_Y), (56, 64, 58), (30, 32, 28))

    moon = pygame.Surface((160, 160), pygame.SRCALPHA)
    pygame.draw.circle(moon, (218, 226, 238, 192), (80, 80), 44)
    pygame.draw.circle(moon, (146, 162, 178, 70), (67, 66), 7)
    pygame.draw.circle(moon, (146, 162, 178, 52), (98, 92), 6)
    scene.blit(moon, (width - 460, 84))

    cloud_step = max(400, width // 10)
    for ci in range(width // cloud_step + 1):
        cx = int(cloud_step * 0.4 + ci * cloud_step + rng.randint(-60, 60))
        cy = rng.randint(120, 185)
        size_cloud = rng.randint(74, 100)
        alpha = rng.randint(32, 44)
        draw_cloud(scene, (cx, cy), size_cloud, alpha)

    floor = pygame.Rect(0, HORIZON_Y + 24, width, height - (HORIZON_Y + 24))
    pygame.draw.rect(scene, (50, 58, 52), floor)
    for _ in range(int(340 * area_factor)):
        px = rng.randint(0, width - 1)
        py = rng.randint(HORIZON_Y + 30, height - 1)
        rw = rng.randint(12, 30)
        rh = rng.randint(7, 20)
        shade = 46 + rng.randint(-12, 10)
        pygame.draw.ellipse(scene, (shade, shade + 8, shade + 2), (px - rw // 2, py - rh // 2, rw, rh))

    # Main crossing road from town gate into deeper wilderness.
    ancient_road = [
        (center_x - 120, HORIZON_Y + 36),
        (center_x + 120, HORIZON_Y + 36),
        (center_x + 260, height),
        (center_x - 260, height),
    ]
    pygame.draw.polygon(scene, (70, 70, 76), ancient_road)
    pygame.draw.polygon(scene, (30, 30, 34), ancient_road, 2)

    branch_roads = [
        pygame.Rect(center_x - 980, HORIZON_Y + 740, 860, 136),
        pygame.Rect(center_x + 120, HORIZON_Y + 740, 860, 136),
        pygame.Rect(center_x - 760, HORIZON_Y + 1080, 1520, 154),
        pygame.Rect(center_x - 980, HORIZON_Y + 1380, 1960, 168),
        # Extended roads for the wider wilderness
        pygame.Rect(0, HORIZON_Y + 740, center_x - 980, 120),
        pygame.Rect(center_x + 980, HORIZON_Y + 740, width - (center_x + 980), 120),
        pygame.Rect(0, HORIZON_Y + 1680, width, 148),
        pygame.Rect(0, HORIZON_Y + 2300, width, 148),
        pygame.Rect(0, HORIZON_Y + 2900, width, 148),
        pygame.Rect(center_x - 980, HORIZON_Y + 1080, -1 * (center_x - 980 - 60), 120),
        pygame.Rect(center_x + 760, HORIZON_Y + 1080, width - (center_x + 760), 120),
    ]
    for road in branch_roads:
        if road.width <= 0 or road.height <= 0:
            continue
        pygame.draw.rect(scene, (66, 66, 72), road, border_radius=38)
        pygame.draw.rect(scene, (28, 28, 32), road, 2, border_radius=38)

    clearing = pygame.Rect(center_x - 390, HORIZON_Y + 500, 780, 500)
    pygame.draw.ellipse(scene, (78, 80, 84), clearing)
    pygame.draw.ellipse(scene, (32, 32, 36), clearing, 2)
    draw_cobblestones(scene, clearing.inflate(-54, -54), seed=51)

    obs: List[pygame.Rect] = []
    path_axis = pygame.Rect(center_x - 240, HORIZON_Y + 120, 480, height - (HORIZON_Y + 120))

    # Framing pines at borders — spaced evenly down the full height.
    edge_y_step = max(280, (height - (HORIZON_Y + 330)) // 8)
    for ei in range(8):
        ey = HORIZON_Y + 330 + ei * edge_y_step
        if ey > height - 80:
            break
        sc = 1.0 + (ei % 3) * 0.08
        obs.append(draw_pine_tree(scene, 120 + (ei % 2) * 60, ey, sc).inflate(-6, -8))
        obs.append(draw_pine_tree(scene, width - 120 - (ei % 2) * 60, ey, sc).inflate(-6, -8))

    # Large procedural groves for an "immense" wilderness feel.
    for _ in range(int(18 * area_factor)):
        px = rng.randint(120, width - 120)
        py = rng.randint(HORIZON_Y + 340, height - 70)
        if path_axis.collidepoint(px, py):
            continue
        if abs(px - center_x) < 360 and py < HORIZON_Y + 620:
            continue
        sc = rng.uniform(0.84, 1.30)
        obs.append(draw_pine_tree(scene, px, py, sc).inflate(-8, -10))

    for _ in range(int(8 * area_factor)):
        px = rng.randint(120, width - 120)
        py = rng.randint(HORIZON_Y + 380, height - 60)
        if path_axis.collidepoint(px, py):
            continue
        draw_dead_tree(scene, px, py, rng.uniform(0.78, 1.18))

    for _ in range(int(12 * area_factor)):
        px = rng.randint(120, width - 120)
        py = rng.randint(HORIZON_Y + 400, height - 50)
        if path_axis.collidepoint(px, py):
            continue
        sc = rng.uniform(0.82, 1.24)
        obs.append(draw_boulder(scene, px, py, sc))

    # Light markers around central crossing only.
    for lx, ly in [
        (center_x - 240, HORIZON_Y + 660),
        (center_x + 240, HORIZON_Y + 660),
        (center_x - 240, HORIZON_Y + 980),
        (center_x + 240, HORIZON_Y + 980),
    ]:
        draw_lamppost(scene, lx, ly, lit=True)

    mist = pygame.Surface(size, pygame.SRCALPHA)
    mist_bands = [
        (HORIZON_Y + 420, 360, 9),
        (HORIZON_Y + 820, 440, 7),
        (HORIZON_Y + 1220, 500, 6),
        (HORIZON_Y + 1800, 520, 6),
        (HORIZON_Y + 2400, 500, 5),
        (HORIZON_Y + 3000, 480, 5),
    ]
    for my, mh, alpha in mist_bands:
        if my + mh > height:
            break
        pygame.draw.ellipse(mist, (150, 162, 168, alpha), pygame.Rect(40, my, width - 80, mh))
    scene.blit(mist, (0, 0))

    walk_bounds = pygame.Rect(70, HORIZON_Y + 92, width - 140, height - (HORIZON_Y + 172))
    wolf_spawn_points: List[Vector2] = []
    spawn_cols = 12
    spawn_rows = 8
    spawn_cell_w = max(1, walk_bounds.width // spawn_cols)
    spawn_cell_h = max(1, walk_bounds.height // spawn_rows)
    min_spawn_sep = 180.0
    max_snap_dist = 150.0

    def try_add_wolf_spawn(raw: Vector2) -> bool:
        cand = nearest_walkable(raw, walk_bounds, obs, WOLF_COLLISION_RADIUS)
        if cand.distance_to(raw) > max_snap_dist:
            return False
        if any(cand.distance_to(existing) < min_spawn_sep for existing in wolf_spawn_points):
            return False
        wolf_spawn_points.append(cand)
        return True

    sectors = [(cx, cy) for cy in range(spawn_rows) for cx in range(spawn_cols)]
    rng.shuffle(sectors)
    for cx, cy in sectors:
        left = walk_bounds.left + cx * spawn_cell_w
        top = walk_bounds.top + cy * spawn_cell_h
        right = walk_bounds.right if cx == spawn_cols - 1 else left + spawn_cell_w
        bottom = walk_bounds.bottom if cy == spawn_rows - 1 else top + spawn_cell_h
        if right - left < 36 or bottom - top < 36:
            continue
        for _ in range(16):
            px = rng.randint(left + 16, right - 16)
            py = rng.randint(top + 16, bottom - 16)
            # Keep the central road lighter, but do not fully exclude it.
            if path_axis.collidepoint(px, py) and rng.random() < 0.88:
                continue
            if try_add_wolf_spawn(Vector2(px, py)):
                break

    target_spawn_points = int(clamp(120.0 + area_factor * 40.0, 120.0, 200.0))
    for _ in range(450):
        if len(wolf_spawn_points) >= target_spawn_points:
            break
        px = rng.randint(walk_bounds.left + 16, walk_bounds.right - 16)
        py = rng.randint(walk_bounds.top + 16, walk_bounds.bottom - 16)
        if path_axis.collidepoint(px, py) and rng.random() < 0.72:
            continue
        try_add_wolf_spawn(Vector2(px, py))

    if len(wolf_spawn_points) < 10:
        fallback_points = [
            Vector2(walk_bounds.left + 220, HORIZON_Y + 760),
            Vector2(walk_bounds.right - 220, HORIZON_Y + 760),
            Vector2(walk_bounds.left + 420, HORIZON_Y + 1320),
            Vector2(walk_bounds.right - 420, HORIZON_Y + 1320),
            Vector2(walk_bounds.left + 380, HORIZON_Y + 2240),
            Vector2(walk_bounds.right - 380, HORIZON_Y + 2240),
            Vector2(walk_bounds.left + 460, HORIZON_Y + 3180),
            Vector2(walk_bounds.right - 460, HORIZON_Y + 3180),
            Vector2(center_x, HORIZON_Y + 1660),
            Vector2(center_x, HORIZON_Y + 2780),
        ]
        for raw in fallback_points:
            try_add_wolf_spawn(raw)

    return scene, obs, wolf_spawn_points


def build_ice_biome_scene(size: Tuple[int, int]) -> Tuple[pygame.Surface, List[pygame.Rect], List[Vector2]]:
    """Build the Frozen Tundra biome scene — 6400×4400 arctic world."""
    width, height = size
    rng = random.Random(0x1CEB10E)
    center_x = width // 2
    area_factor = (width * height) / (3200.0 * 2200.0)

    scene = pygame.Surface((width, height))

    # --- Sky gradient (dark arctic night-blue) ---
    for y in range(HORIZON_Y):
        t = y / max(1, HORIZON_Y - 1)
        r = int(4  + t * 58)
        g = int(8  + t * 82)
        b = int(22 + t * 108)
        pygame.draw.line(scene, (r, g, b), (0, y), (width, y))

    # --- Ground gradient (snow white → deep ice blue) ---
    for y in range(HORIZON_Y, height):
        t = (y - HORIZON_Y) / max(1, height - HORIZON_Y - 1)
        r = int(210 - t * 42)
        g = int(224 - t * 34)
        b = int(238 - t * 26)
        pygame.draw.line(scene, (r, g, b), (0, y), (width, y))

    # --- Moon (pale blue-white) ---
    moon_surf = pygame.Surface((180, 180), pygame.SRCALPHA)
    pygame.draw.circle(moon_surf, (210, 230, 252, 200), (90, 90), 72)
    pygame.draw.circle(moon_surf, (230, 244, 255, 80), (90, 90), 78, 8)
    scene.blit(moon_surf, (width - 520, 62))

    # --- Overcast clouds ---
    cloud_rng = random.Random(0x1CEC10D)
    for _ in range(int(18 * area_factor)):
        cx = cloud_rng.randint(0, width)
        cy = cloud_rng.randint(20, HORIZON_Y - 40)
        cw = cloud_rng.randint(120, 280)
        ch = cloud_rng.randint(28, 58)
        alpha = cloud_rng.randint(55, 82)
        cloud_s = pygame.Surface((cw, ch), pygame.SRCALPHA)
        pygame.draw.ellipse(cloud_s, (195, 210, 230, alpha), (0, 0, cw, ch))
        scene.blit(cloud_s, (cx - cw // 2, cy - ch // 2))

    # --- Snow patch texture on ground ---
    snow_rng = random.Random(0x5A0F)
    for _ in range(int(420 * area_factor)):
        sx2 = snow_rng.randint(0, width)
        sy2 = snow_rng.randint(HORIZON_Y, height)
        sw = snow_rng.randint(32, 120)
        sh = snow_rng.randint(10, 36)
        shade = snow_rng.randint(228, 248)
        alpha = snow_rng.randint(40, 100)
        s2 = pygame.Surface((sw, sh), pygame.SRCALPHA)
        pygame.draw.ellipse(s2, (shade, shade + 2, 255, alpha), (0, 0, sw, sh))
        scene.blit(s2, (sx2 - sw // 2, sy2 - sh // 2))

    # --- Frozen lake (central) ---
    lake_cx = center_x
    lake_cy = HORIZON_Y + 1100
    lake_w, lake_h = 980, 600
    pygame.draw.ellipse(scene, (120, 180, 225), (lake_cx - lake_w // 2, lake_cy - lake_h // 2, lake_w, lake_h))
    pygame.draw.ellipse(scene, (90, 150, 200), (lake_cx - lake_w // 2, lake_cy - lake_h // 2, lake_w, lake_h), 5)
    # Ice surface sheen
    sheen = pygame.Surface((lake_w, lake_h), pygame.SRCALPHA)
    pygame.draw.ellipse(sheen, (200, 235, 255, 60), (0, 0, lake_w, lake_h))
    scene.blit(sheen, (lake_cx - lake_w // 2, lake_cy - lake_h // 2))
    # Crack lines on lake
    for _ in range(12):
        x1 = rng.randint(lake_cx - 400, lake_cx + 400)
        y1 = rng.randint(lake_cy - 250, lake_cy + 250)
        x2 = x1 + rng.randint(-80, 80)
        y2 = y1 + rng.randint(-40, 40)
        pygame.draw.line(scene, (80, 130, 190), (x1, y1), (x2, y2), 1)

    # --- Icy road (path to portal) ---
    road_top_y = HORIZON_Y + 120
    road_w = 140
    road_pts = [
        (center_x - road_w // 2, road_top_y),
        (center_x + road_w // 2, road_top_y),
        (center_x + road_w // 2 + 60, height),
        (center_x - road_w // 2 - 60, height),
    ]
    pygame.draw.polygon(scene, (170, 195, 220), road_pts)
    pygame.draw.polygon(scene, (130, 155, 185), road_pts, 3)

    # --- Ice spires (boulders tinted blue-white) ---
    obs: List[pygame.Rect] = []
    ice_spawn_points: List[Vector2] = []

    def draw_ice_spire(x: int, y: int, scale: float) -> pygame.Rect:
        col_base = (180, 215, 240)
        col_hi   = (220, 240, 252)
        h_spire = int(60 * scale)
        w_spire = int(28 * scale)
        # Shadow
        pygame.draw.ellipse(scene, (140, 165, 190), (x - int(w_spire * 0.6), y - 5, int(w_spire * 1.2), 10))
        # Main spire body
        pts = [(x, y - h_spire), (x - w_spire // 2, y), (x + w_spire // 2, y)]
        pygame.draw.polygon(scene, col_base, pts)
        # Highlight facet
        pts2 = [(x, y - h_spire), (x, y - h_spire // 4), (x + w_spire // 4, y - h_spire // 2)]
        pygame.draw.polygon(scene, col_hi, pts2)
        pygame.draw.polygon(scene, (100, 150, 200), pts, 2)
        return pygame.Rect(x - w_spire // 2, y - h_spire, w_spire, h_spire)

    road_avoid_left = center_x - 260
    road_avoid_right = center_x + 260
    road_avoid_top = HORIZON_Y + 80

    def spire_ok(x: int, y: int) -> bool:
        if road_avoid_left < x < road_avoid_right and y > road_avoid_top:
            return False
        return True

    # Edge spires (left & right)
    for side in (-1, 1):
        col_x = center_x + side * int(width * 0.46)
        for idx in range(8):
            sy3 = HORIZON_Y + 200 + idx * int((height - HORIZON_Y - 200) // 8)
            sc = rng.uniform(0.9, 1.6)
            r = draw_ice_spire(col_x + rng.randint(-60, 60), sy3, sc)
            obs.append(r)

    # Scattered spires
    for _ in range(int(22 * area_factor)):
        sx4 = rng.randint(80, width - 80)
        sy4 = rng.randint(HORIZON_Y + 200, height - 80)
        sc = rng.uniform(0.8, 1.8)
        if not spire_ok(sx4, sy4):
            continue
        r = draw_ice_spire(sx4, sy4, sc)
        obs.append(r)

    # --- Snow-covered frost trees (fully ice-palette, no green) ---
    def draw_ice_tree(x: int, y: int, scale: float) -> pygame.Rect:
        trunk_w = max(6, int(12 * scale))
        trunk_h = max(22, int(26 * scale))
        crown_h = max(54, int(96 * scale))
        crown_w = max(44, int(84 * scale))
        # Shadow
        pygame.draw.ellipse(scene, (140, 160, 185),
                            (x - int(crown_w * 0.28), y - 6,
                             int(crown_w * 0.56), max(8, int(12 * scale))))
        # Trunk (grey-blue bark)
        trunk = pygame.Rect(x - trunk_w // 2, y - trunk_h, trunk_w, trunk_h)
        pygame.draw.rect(scene, (110, 125, 145), trunk)
        pygame.draw.rect(scene, (80, 95, 115), trunk, 1)
        top_y = y - trunk_h - crown_h
        layers = 4
        for i in range(layers):
            t = i / max(1, layers - 1)
            layer_w = int(crown_w * (0.45 + 0.55 * (i + 1) / layers))
            layer_h = int(crown_h * (0.20 + 0.08 * i))
            cy = int(top_y + crown_h * (0.18 + t * 0.68))
            pts = [(x, cy - layer_h), (x - layer_w // 2, cy + layer_h // 2),
                   (x + layer_w // 2, cy + layer_h // 2)]
            pygame.draw.polygon(scene, (195, 218, 240), pts)
            inner = [(x, cy - int(layer_h * 0.7)),
                     (x - int(layer_w * 0.38), cy),
                     (x + int(layer_w * 0.38), cy)]
            pygame.draw.polygon(scene, (225, 238, 252), inner)
            pygame.draw.polygon(scene, (140, 170, 200), pts, 1)
        return pygame.Rect(x - int(crown_w * 0.18), y - int(18 * scale),
                           int(crown_w * 0.36), int(20 * scale))

    # Edge frost-tree rows
    for side in (-1, 1):
        col_x2 = 80 if side == -1 else width - 80
        for idx in range(10):
            py3 = HORIZON_Y + 180 + idx * int((height - HORIZON_Y - 250) // 10)
            sc = rng.uniform(1.0, 1.3)
            r = draw_ice_tree(col_x2 + rng.randint(-30, 30), py3, sc)
            obs.append(r)

    # Scattered frost grove
    for _ in range(int(20 * area_factor)):
        px2 = rng.randint(120, width - 120)
        py2 = rng.randint(HORIZON_Y + 200, height - 120)
        sc = rng.uniform(0.8, 1.3)
        if not spire_ok(px2, py2):
            continue
        r = draw_ice_tree(px2, py2, sc)
        obs.append(r)

    # --- Dead trees ---
    for _ in range(int(10 * area_factor)):
        dtx = rng.randint(80, width - 80)
        dty = rng.randint(HORIZON_Y + 180, height - 80)
        if not spire_ok(dtx, dty):
            continue
        draw_dead_tree(scene, dtx, dty, rng.uniform(0.8, 1.2))

    # --- Blizzard mist bands ---
    for i in range(8):
        band_y = HORIZON_Y + int(i * (height - HORIZON_Y) / 8)
        band_alpha = 10 + i * 2
        mist = pygame.Surface((width, 80), pygame.SRCALPHA)
        mist.fill((230, 240, 255, band_alpha))
        scene.blit(mist, (0, band_y))

    # --- Lampposts at path junction ---
    for side in (-1, 1):
        draw_lamppost(scene, center_x + side * 90, HORIZON_Y + 560)

    # --- Spawn points (grid) ---
    min_spawn_sep = 180.0
    max_snap_dist = 150.0

    def is_near_obstacle(pos: Vector2) -> bool:
        for ob in obs:
            if ob.inflate(40, 40).collidepoint(int(pos.x), int(pos.y)):
                return True
        return False

    def try_add_spawn(raw: Vector2) -> None:
        if raw.x < 80 or raw.x > width - 80 or raw.y < HORIZON_Y + 120 or raw.y > height - 80:
            return
        if is_near_obstacle(raw):
            return
        if any(raw.distance_to(sp) < min_spawn_sep for sp in ice_spawn_points):
            return
        ice_spawn_points.append(raw)

    rows = max(8, int(12 * area_factor ** 0.5))
    cols = max(8, int(12 * area_factor ** 0.5))
    for row in range(rows):
        for col in range(cols):
            gx = int(80 + (width - 160) * col / max(1, cols - 1))
            gy = int(HORIZON_Y + 200 + (height - HORIZON_Y - 280) * row / max(1, rows - 1))
            jitter = Vector2(rng.uniform(-80, 80), rng.uniform(-80, 80))
            try_add_spawn(Vector2(gx, gy) + jitter)

    # Ensure minimum spawn coverage
    if len(ice_spawn_points) < 48:
        for _ in range(200):
            fx = rng.randint(120, width - 120)
            fy = rng.randint(HORIZON_Y + 200, height - 120)
            try_add_spawn(Vector2(fx, fy))

    return scene, obs, ice_spawn_points


def load_church_position() -> Optional[Tuple[float, float]]:
    if not os.path.exists(CHURCH_POSITION_PATH):
        return None
    try:
        with open(CHURCH_POSITION_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict) and "x" in data and "y" in data:
            return (float(data["x"]), float(data["y"]))
    except Exception:
        pass
    return None
