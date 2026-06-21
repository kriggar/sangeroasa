"""game/render/shops.py — vendor shop exterior/interior draw functions."""
import math
import random
from typing import Dict, List, Optional, Tuple, Any

import pygame
from pygame import Vector2

from game.utils import clamp
from game.render.props import *
from game.render.glyphs import *

__all__ = [
    '_draw_blacksmith_shop',
    '_draw_alchemist_shop',
    '_draw_tailor_shop',
    '_draw_leather_shop',
    '_draw_merchant_shop',
    '_draw_baker_shop',
    '_draw_guard_shop',
    '_draw_herbalist_shop',
    '_draw_sailor_shop',
    '_draw_miller_shop',
    '_draw_tanner_shop',
    '_draw_cooper_shop',
]


def _draw_blacksmith_shop(surface: pygame.Surface, pos: Vector2, ticks: int, seed: int) -> None:
    x = int(pos.x)
    ground = int(pos.y)


    # ── Back wall: timber-frame with stone lower half ──
    wall = pygame.Rect(x - 190, ground - 180, 380, 160)
    # stone lower section
    stone = pygame.Rect(wall.left, wall.top + 60, wall.width, wall.height - 60)
    for row in range(stone.top, stone.bottom, 12):
        offset = 8 if ((row - stone.top) // 12) % 2 else 0
        for col in range(stone.left + offset, stone.right - 4, 24):
            bw = min(22, stone.right - col)
            bh = min(11, stone.bottom - row)
            shade = 56 + (row * 3 + col * 7 + seed) % 18
            pygame.draw.rect(surface, (shade, shade - 6, shade - 10), (col, row, bw, bh))
            pygame.draw.rect(surface, (shade - 20, shade - 26, shade - 30), (col, row, bw, bh), 1)
    # timber upper section
    upper = pygame.Rect(wall.left, wall.top, wall.width, 62)
    pygame.draw.rect(surface, (62, 48, 36), upper)
    # horizontal beams
    for by in (wall.top, wall.top + 30, wall.top + 60, wall.bottom):
        pygame.draw.rect(surface, (80, 62, 44), (wall.left, by - 3, wall.width, 6))
        pygame.draw.rect(surface, (50, 38, 28), (wall.left, by - 3, wall.width, 6), 1)
    # vertical beams
    for bx in (wall.left, wall.left + 95, wall.centerx, wall.right - 95, wall.right):
        pygame.draw.rect(surface, (80, 62, 44), (bx - 3, wall.top, 6, wall.height))
        pygame.draw.rect(surface, (50, 38, 28), (bx - 3, wall.top, 6, wall.height), 1)
    # cross braces in upper panels
    for px in (wall.left + 3, wall.left + 98, wall.centerx + 3, wall.right - 92):
        pw = 89
        pygame.draw.line(surface, (72, 56, 40), (px, wall.top + 3), (px + pw, wall.top + 57), 2)
        pygame.draw.line(surface, (72, 56, 40), (px + pw, wall.top + 3), (px, wall.top + 57), 2)
    pygame.draw.rect(surface, (42, 34, 26), wall, 2)

    # ── Roof: steep A-frame with overhang ──
    roof_peak = ground - 240
    roof_l = x - 210
    roof_r = x + 210
    roof_base_y = ground - 176
    # roof fill
    roof_pts = [(roof_l, roof_base_y), (x, roof_peak), (roof_r, roof_base_y)]
    pygame.draw.polygon(surface, (52, 44, 36), roof_pts)
    # shingle rows
    for ry in range(roof_peak + 12, roof_base_y, 10):
        t_row = (ry - roof_peak) / max(1, roof_base_y - roof_peak)
        half_w = int(210 * t_row)
        shade = 48 + (ry * 7 + seed) % 14
        pygame.draw.line(surface, (shade, shade - 6, shade - 10), (x - half_w, ry), (x + half_w, ry), 1)
    pygame.draw.polygon(surface, (30, 24, 18), roof_pts, 3)
    # ridge beam
    pygame.draw.line(surface, (90, 72, 54), (x - 6, roof_peak), (x + 6, roof_peak), 4)
    # eave trim
    pygame.draw.line(surface, (100, 82, 60), (roof_l, roof_base_y), (roof_r, roof_base_y), 3)

    # ── Chimney (right side) ──
    chim = pygame.Rect(x + 100, roof_peak - 30, 28, 70)
    pygame.draw.rect(surface, (70, 66, 62), chim)
    for cy in range(chim.top, chim.bottom, 8):
        pygame.draw.line(surface, (56, 52, 48), (chim.left + 2, cy), (chim.right - 2, cy), 1)
    pygame.draw.rect(surface, (40, 38, 34), chim, 2)
    # chimney cap
    pygame.draw.rect(surface, (56, 54, 50), (chim.left - 4, chim.top - 4, chim.width + 8, 6))
    pygame.draw.rect(surface, (36, 34, 30), (chim.left - 4, chim.top - 4, chim.width + 8, 6), 1)
    # chimney smoke
    for i in range(6):
        t = ticks * 0.0008 + seed * 0.04 + i * 0.7
        sx = chim.centerx + math.sin(t * 1.1 + i) * (8 + i * 2)
        sy = chim.top - 10 - (t * 16 + i * 8) % 40
        sz = 8 + i * 3
        sm = pygame.Surface((sz, sz), pygame.SRCALPHA)
        alpha = max(20, 80 - i * 12)
        pygame.draw.ellipse(sm, (90, 88, 94, alpha), sm.get_rect())
        surface.blit(sm, (int(sx) - sz // 2, int(sy) - sz // 2), special_flags=pygame.BLEND_RGBA_ADD)

    # ── Hanging sign (iron bracket + wooden board) ──
    sign_x = x + 160
    sign_y = ground - 160
    # bracket
    pygame.draw.line(surface, (60, 60, 66), (sign_x - 30, sign_y - 30), (sign_x, sign_y - 30), 3)
    pygame.draw.line(surface, (60, 60, 66), (sign_x - 30, sign_y - 30), (sign_x - 30, sign_y - 20), 2)
    # chains
    pygame.draw.line(surface, (100, 100, 110), (sign_x - 20, sign_y - 30), (sign_x - 16, sign_y - 18), 1)
    pygame.draw.line(surface, (100, 100, 110), (sign_x + 14, sign_y - 30), (sign_x + 10, sign_y - 18), 1)
    sign_rect = pygame.Rect(sign_x - 26, sign_y - 18, 52, 34)
    pygame.draw.rect(surface, (60, 46, 32), sign_rect, border_radius=3)
    pygame.draw.rect(surface, (100, 80, 58), sign_rect, 2, border_radius=3)
    _draw_hammer_icon(surface, sign_rect.centerx - 6, sign_rect.centery + 8, 1.0)
    _draw_gear_icon(surface, sign_rect.centerx + 14, sign_rect.centery + 2, 0.7)

    # ── FORGE (left side, large stone furnace) ──
    draw_hd_forge_prop(surface, x - 120, ground - 2, ticks=ticks, seed=seed)
    # extra forge glow on ground
    glow = pygame.Surface((80, 30), pygame.SRCALPHA)
    pygame.draw.ellipse(glow, (255, 140, 40, 35), glow.get_rect())
    surface.blit(glow, (x - 160, ground - 16), special_flags=pygame.BLEND_RGBA_ADD)

    # ── BELLOWS next to forge ──
    bel_x, bel_y = x - 60, ground - 8
    # body
    pygame.draw.polygon(surface, (70, 55, 40), [
        (bel_x - 16, bel_y), (bel_x + 16, bel_y),
        (bel_x + 10, bel_y - 18), (bel_x - 10, bel_y - 18)])
    pygame.draw.polygon(surface, (50, 40, 30), [
        (bel_x - 16, bel_y), (bel_x + 16, bel_y),
        (bel_x + 10, bel_y - 18), (bel_x - 10, bel_y - 18)], 1)
    # nozzle
    pygame.draw.line(surface, (100, 100, 110), (bel_x - 16, bel_y - 6), (bel_x - 28, bel_y - 10), 3)
    # handle
    pygame.draw.line(surface, (90, 70, 50), (bel_x + 16, bel_y - 4), (bel_x + 28, bel_y - 10), 3)
    pygame.draw.circle(surface, (110, 85, 60), (bel_x + 28, bel_y - 10), 3)
    # leather folds
    for i in range(3):
        fy = bel_y - 4 - i * 4
        pygame.draw.line(surface, (56, 44, 32), (bel_x - 12, fy), (bel_x + 12, fy), 1)

    # ── PRIMARY ANVIL (large, on oak stump) ──
    # oak stump
    stump_x, stump_y = x - 10, ground
    pygame.draw.ellipse(surface, (12, 12, 14), (stump_x - 24, stump_y - 4, 48, 10))
    pygame.draw.rect(surface, (82, 62, 42), (stump_x - 16, stump_y - 22, 32, 22), border_radius=4)
    pygame.draw.rect(surface, (58, 44, 30), (stump_x - 16, stump_y - 22, 32, 22), 1, border_radius=4)
    # wood grain lines
    for gy in range(stump_y - 20, stump_y - 2, 5):
        pygame.draw.line(surface, (72, 54, 36), (stump_x - 14, gy), (stump_x + 14, gy), 1)
    # top ring
    pygame.draw.ellipse(surface, (90, 70, 48), (stump_x - 16, stump_y - 26, 32, 8))
    pygame.draw.ellipse(surface, (60, 46, 32), (stump_x - 16, stump_y - 26, 32, 8), 1)
    # anvil
    draw_hd_anvil(surface, stump_x, stump_y - 22)

    # ── SECOND SMALLER ANVIL (detail piece) ──
    draw_anvil(surface, x + 40, ground + 2)

    # ── QUENCH TROUGH (water trough for cooling) ──
    trough = pygame.Rect(x + 60, ground - 16, 50, 20)
    pygame.draw.rect(surface, (56, 52, 48), trough, border_radius=3)
    pygame.draw.rect(surface, (36, 34, 30), trough, 2, border_radius=3)
    # water inside
    water = trough.inflate(-6, -8)
    water.top += 4
    pygame.draw.rect(surface, (40, 70, 100), water, border_radius=2)
    pygame.draw.rect(surface, (60, 100, 140), water.inflate(-4, -4), border_radius=1)
    # steam wisps
    for i in range(3):
        t = ticks * 0.0015 + seed * 0.07 + i * 1.1
        stx = trough.centerx + math.sin(t * 1.3 + i) * 8
        sty = trough.top - 4 - (t * 12 + i * 5) % 16
        steam = pygame.Surface((10, 8), pygame.SRCALPHA)
        pygame.draw.ellipse(steam, (180, 190, 200, 50), steam.get_rect())
        surface.blit(steam, (int(stx) - 5, int(sty) - 4), special_flags=pygame.BLEND_RGBA_ADD)

    # ── WEAPON RACK (tall, multi-tier) ──
    rack_x = x + 140
    # back board
    pygame.draw.rect(surface, (70, 54, 38), (rack_x - 24, ground - 80, 48, 76), border_radius=3)
    pygame.draw.rect(surface, (50, 38, 26), (rack_x - 24, ground - 80, 48, 76), 1, border_radius=3)
    # pegs
    for py_off in (-66, -46, -26):
        pygame.draw.circle(surface, (90, 72, 52), (rack_x - 16, ground + py_off), 3)
        pygame.draw.circle(surface, (90, 72, 52), (rack_x + 16, ground + py_off), 3)
    # swords on rack
    for i, py_off in enumerate((-68, -48, -28)):
        blade_col = (160 + i * 10, 165 + i * 8, 175 + i * 6)
        pygame.draw.line(surface, blade_col, (rack_x - 18, ground + py_off), (rack_x + 18, ground + py_off), 2)
        pygame.draw.circle(surface, (120, 90, 60), (rack_x - 18, ground + py_off), 3)
    # shield leaning against rack
    _draw_shield_icon(surface, rack_x + 30, ground - 10, 1.2)


    # ── CRATES (material storage) ──
    draw_wood_crate(surface, x + 110, ground + 8, size=32)
    draw_wood_crate(surface, x + 130, ground + 2, size=26)

    # ── METAL INGOT STACKS on crate ──
    for row in range(3):
        for col in range(3 - row):
            ix = x + 104 + col * 12 + row * 6
            iy = ground - 20 - row * 7
            shade = 100 + row * 15 + (col * 23 + seed) % 20
            ingot = pygame.Rect(ix, iy, 10, 6)
            pygame.draw.rect(surface, (shade, shade + 8, shade + 16), ingot, border_radius=1)
            pygame.draw.rect(surface, (shade - 40, shade - 32, shade - 24), ingot, 1, border_radius=1)

    # ── TOOL WALL (pegboard with tools) ──
    peg = pygame.Rect(x - 40, ground - 140, 120, 60)
    pygame.draw.rect(surface, (52, 46, 38), peg)
    pygame.draw.rect(surface, (38, 32, 26), peg, 1)
    # peg holes
    for pr in range(peg.top + 8, peg.bottom - 4, 14):
        for pc in range(peg.left + 10, peg.right - 8, 16):
            pygame.draw.circle(surface, (42, 36, 30), (pc, pr), 2)
    # tools hanging
    _draw_hammer_icon(surface, x - 24, ground - 100, 0.9)
    _draw_tongs_icon(surface, x - 2, ground - 102, 0.9)
    _draw_pliers_icon(surface, x + 18, ground - 100, 0.9)
    _draw_wrench_icon(surface, x + 38, ground - 102, 0.9)
    _draw_gear_icon(surface, x + 56, ground - 98, 0.8)
    _draw_hammer_icon(surface, x - 16, ground - 118, 0.7)
    _draw_tongs_icon(surface, x + 8, ground - 120, 0.7)
    _draw_wrench_icon(surface, x + 30, ground - 118, 0.7)
    _draw_pliers_icon(surface, x + 48, ground - 116, 0.7)

    # ── WORKBENCH (heavy oak table with vise) ──
    bench = pygame.Rect(x - 160, ground - 22, 80, 16)
    pygame.draw.rect(surface, (76, 60, 42), bench, border_radius=3)
    pygame.draw.rect(surface, (56, 44, 30), bench, 1, border_radius=3)
    # wood grain
    for ly in range(bench.top + 2, bench.bottom - 2, 3):
        pygame.draw.line(surface, (68, 52, 36), (bench.left + 2, ly), (bench.right - 2, ly), 1)
    # legs
    for lx in (bench.left + 6, bench.right - 6):
        pygame.draw.rect(surface, (66, 50, 34), (lx - 2, bench.bottom, 4, 12), border_radius=1)
    # vise on bench edge
    vise_x = bench.right - 12
    pygame.draw.rect(surface, (90, 92, 100), (vise_x - 6, bench.top - 10, 12, 10))
    pygame.draw.rect(surface, (60, 62, 68), (vise_x - 6, bench.top - 10, 12, 10), 1)
    pygame.draw.rect(surface, (100, 102, 110), (vise_x - 8, bench.top - 14, 16, 4), border_radius=1)
    # tools on bench
    _draw_hammer_icon(surface, bench.left + 18, bench.top + 6, 0.6)
    _draw_tongs_icon(surface, bench.left + 36, bench.top + 4, 0.6)
    _draw_pliers_icon(surface, bench.left + 50, bench.top + 6, 0.6)

    # ── GRINDING WHEEL ──
    gw_x, gw_y = x + 80, ground - 4
    # frame
    pygame.draw.rect(surface, (70, 56, 40), (gw_x - 12, gw_y - 30, 4, 30), border_radius=1)
    pygame.draw.rect(surface, (70, 56, 40), (gw_x + 8, gw_y - 30, 4, 30), border_radius=1)
    # wheel
    wheel_r = 14
    pygame.draw.circle(surface, (120, 120, 128), (gw_x, gw_y - 18), wheel_r)
    pygame.draw.circle(surface, (90, 90, 98), (gw_x, gw_y - 18), wheel_r, 2)
    pygame.draw.circle(surface, (70, 70, 78), (gw_x, gw_y - 18), 3)
    # handle
    t_handle = ticks * 0.001
    hx = gw_x + int(math.cos(t_handle) * (wheel_r - 4))
    hy = gw_y - 18 + int(math.sin(t_handle) * (wheel_r - 4))
    pygame.draw.line(surface, (100, 80, 60), (gw_x, gw_y - 18), (hx, hy), 2)
    pygame.draw.circle(surface, (110, 88, 64), (hx, hy), 3)
    # trough beneath
    pygame.draw.rect(surface, (50, 48, 44), (gw_x - 14, gw_y - 2, 28, 6), border_radius=2)
    pygame.draw.rect(surface, (40, 70, 95), (gw_x - 12, gw_y - 1, 24, 4), border_radius=1)

    # ── CHAIN + HOOKS from ceiling ──
    for cx_off in (-80, 30, 100):
        chain_x = x + cx_off
        chain_top = ground - 170
        chain_bot = ground - 140
        for cy in range(chain_top, chain_bot, 4):
            col = (100, 100, 110) if (cy // 4) % 2 else (80, 80, 90)
            pygame.draw.rect(surface, col, (chain_x - 1, cy, 3, 4))
        # hook
        pygame.draw.arc(surface, (110, 110, 120),
                        (chain_x - 4, chain_bot - 2, 8, 10), 3.14, 6.28, 2)

    # ── HOT IRON on anvil (animated glow) ──
    iron_glow = int(180 + 60 * math.sin(ticks * 0.004))
    iron_col = (iron_glow, int(iron_glow * 0.45), 20)
    pygame.draw.rect(surface, iron_col, (stump_x - 8, stump_y - 46, 20, 4), border_radius=1)
    # glow halo
    glow_s = pygame.Surface((32, 16), pygame.SRCALPHA)
    pygame.draw.ellipse(glow_s, (255, 120, 30, 40), glow_s.get_rect())
    surface.blit(glow_s, (stump_x - 14, stump_y - 52), special_flags=pygame.BLEND_RGBA_ADD)

    # ── FORGE SPARKS (animated) ──
    for i in range(12):
        t = ticks * 0.002 + seed * 0.09 + i * 1.1
        px = (x - 120) + math.sin(t * 1.6 + i) * 16
        py = (ground - 56) - (t * 28 + i * 7) % 30
        brightness = int(clamp(220 - (ground - 56 - py) * 5, 40, 255))
        spark_col = (brightness, int(brightness * 0.7), int(brightness * 0.3))
        sz = 1 + (i % 3)
        pygame.draw.circle(surface, spark_col, (int(px), int(py)), sz)

    # ── ANVIL SPARKS (when hot iron is struck, slower animation) ──
    spark_phase = math.sin(ticks * 0.003) * 0.5 + 0.5
    if spark_phase > 0.6:
        for i in range(5):
            t = ticks * 0.003 + i * 0.8
            spx = stump_x + math.sin(t * 2.5 + i) * (10 + i * 4)
            spy = stump_y - 48 - abs(math.sin(t * 1.8 + i * 0.6)) * 18
            pygame.draw.circle(surface, (255, 200, 80), (int(spx), int(spy)), 1)

    # ── FORGE AMBIENT GLOW (warm light pool) ──
    for r, alpha in [(60, 18), (40, 28), (20, 40)]:
        g = pygame.Surface((r * 2, r), pygame.SRCALPHA)
        pygame.draw.ellipse(g, (255, 130, 40, alpha), g.get_rect())
        surface.blit(g, (x - 120 - r, ground - 10 - r // 2), special_flags=pygame.BLEND_RGBA_ADD)

    # ── FLOOR DETAILS: scattered metal bits, coal ──
    coal_positions = [(x - 90, ground + 4), (x - 70, ground + 8), (x - 30, ground + 6),
                      (x + 20, ground + 10), (x + 50, ground + 4), (x - 140, ground + 6)]
    for cx_pos, cy_pos in coal_positions:
        pygame.draw.circle(surface, (22, 20, 18), (cx_pos, cy_pos), 3)
        pygame.draw.circle(surface, (16, 14, 12), (cx_pos, cy_pos), 3, 1)
    # metal shavings
    for i in range(8):
        mx = x - 100 + (seed * 41 + i * 53) % 240
        my = ground + 2 + (seed * 17 + i * 31) % 10
        pygame.draw.line(surface, (130, 135, 142), (mx, my), (mx + 4, my - 1), 1)


def _draw_alchemist_shop(surface: pygame.Surface, pos: Vector2, ticks: int, seed: int) -> None:  # noqa: C901
    x = int(pos.x)
    ground = int(pos.y)

    # ── Arcane ground circle (slow rotation) ──
    rot_t = ticks * 0.0008 + seed
    for ri in range(8):
        ang = math.radians(ri * 45 + rot_t * 28)
        rx0 = x + int(math.cos(ang) * 115)
        ry0 = ground - 14 + int(math.sin(ang) * 22)
        rp0 = pygame.Surface((7, 7), pygame.SRCALPHA)
        rb0 = int(70 + 60 * math.sin(ticks * 0.004 + ri * 0.785))
        pygame.draw.circle(rp0, (110, rb0, 220, rb0), (3, 3), 2)
        surface.blit(rp0, (rx0 - 3, ry0 - 3), special_flags=pygame.BLEND_RGBA_ADD)
    circ_s = pygame.Surface((240, 56), pygame.SRCALPHA)
    pygame.draw.ellipse(circ_s, (70, 35, 170, 25), (0, 0, 240, 56), 1)
    pygame.draw.ellipse(circ_s, (90, 50, 190, 16), (28, 8, 184, 40), 1)
    surface.blit(circ_s, (x - 120, ground - 28))

    # ── Side buttresses ──
    for bx_off, side in ((-210, -1), (210, 1)):
        bx1 = x + bx_off
        pygame.draw.polygon(surface, (26, 22, 36), [
            (bx1, ground - 162), (bx1 + side * 24, ground - 80),
            (bx1 + side * 30, ground), (bx1, ground)
        ])
        pygame.draw.polygon(surface, (14, 10, 22), [
            (bx1, ground - 162), (bx1 + side * 24, ground - 80),
            (bx1 + side * 30, ground), (bx1, ground)
        ], 2)
        for cy0 in (ground - 128, ground - 88):
            cx0 = bx1 if side == 1 else bx1 - 14
            pygame.draw.rect(surface, (34, 27, 44), (cx0, cy0 - 4, 14, 9), border_radius=2)

    # ── Main back wall ──
    wall = pygame.Rect(x - 200, ground - 192, 400, 170)
    pygame.draw.rect(surface, (24, 20, 34), wall)
    for row in range(wall.top, wall.bottom, 16):
        off = 14 if ((row - wall.top) // 16) % 2 else 0
        for col in range(wall.left + off, wall.right - 4, 36):
            bw = min(34, wall.right - col)
            bh = min(15, wall.bottom - row)
            shade = 26 + (row * 3 + col * 7 + seed) % 16
            pygame.draw.rect(surface, (shade, shade - 2, shade + 10), (col, row, bw, bh))
            pygame.draw.rect(surface, (14, 10, 22), (col, row, bw, bh), 1)
    pygame.draw.rect(surface, (12, 8, 20), wall, 2)
    # heavy timber beams
    for bby in (wall.top, wall.top + 57, wall.top + 114, wall.bottom):
        pygame.draw.rect(surface, (42, 32, 52), (wall.left, bby - 4, wall.width, 8))
        pygame.draw.rect(surface, (22, 16, 32), (wall.left, bby - 4, wall.width, 8), 1)
    for bbx in (wall.left, wall.left + 100, wall.centerx, wall.right - 100, wall.right):
        pygame.draw.rect(surface, (42, 32, 52), (bbx - 4, wall.top, 8, wall.height))
        pygame.draw.rect(surface, (22, 16, 32), (bbx - 4, wall.top, 8, wall.height), 1)
    # arcane rune carvings
    carve_pulse = int(100 + 70 * math.sin(ticks * 0.0025 + seed * 0.3))
    carve_pos = [(-148, -162), (-88, -146), (-28, -163), (32, -146),
                 (-158, -108), (-98, -94), (52, -108), (112, -94), (142, -160)]
    carve_cols = [(80, carve_pulse, 200), (carve_pulse, 60, 180), (60, 180, carve_pulse),
                  (180, carve_pulse, 80), (carve_pulse, 140, 60), (60, carve_pulse, 160),
                  (200, 80, carve_pulse), (carve_pulse, 80, 200), (80, 200, carve_pulse)]
    for ci, (cx_off, cy_off) in enumerate(carve_pos):
        cx2, cy2 = x + cx_off, ground + cy_off
        cc = carve_cols[ci % len(carve_cols)]
        pygame.draw.circle(surface, cc, (cx2, cy2), 5, 1)
        pygame.draw.line(surface, cc, (cx2, cy2 - 5), (cx2, cy2 + 5), 1)
        pygame.draw.line(surface, cc, (cx2 - 5, cy2), (cx2 + 5, cy2), 1)
        rg_s = pygame.Surface((10, 10), pygame.SRCALPHA)
        pygame.draw.circle(rg_s, (*cc, 32), (5, 5), 4)
        surface.blit(rg_s, (cx2 - 5, cy2 - 5), special_flags=pygame.BLEND_RGBA_ADD)
    # gothic arch doorway (right side)
    door_x = x + 88
    door_rect = pygame.Rect(door_x - 22, ground - 74, 44, 74)
    pygame.draw.rect(surface, (10, 6, 18), door_rect)
    arch_pts = [(door_rect.left, door_rect.top), (door_rect.centerx, door_rect.top - 26),
                (door_rect.right, door_rect.top)]
    pygame.draw.polygon(surface, (10, 6, 18), arch_pts)
    pygame.draw.polygon(surface, (58, 42, 88), arch_pts, 2)
    pygame.draw.rect(surface, (58, 42, 88), door_rect, 2)
    for si in range(3):
        sw = 44 + si * 8
        pygame.draw.rect(surface, (30, 24, 40), (door_x - sw // 2, ground - si * 4, sw, 5), border_radius=1)
    arch_peak_pt = (door_x, door_rect.top - 26)
    ap_pulse = int(140 + 80 * math.sin(ticks * 0.003 + seed))
    ap_s = pygame.Surface((12, 12), pygame.SRCALPHA)
    pygame.draw.circle(ap_s, (ap_pulse, 80, 220, ap_pulse // 2), (6, 6), 5)
    surface.blit(ap_s, (arch_peak_pt[0] - 6, arch_peak_pt[1] - 6), special_flags=pygame.BLEND_RGBA_ADD)

    # ── Wizard tower / turret (right side, tall) ──
    tower_x = x + 148
    tower_base_y = ground - 188
    tower_top_y = ground - 348
    tower_w = 54
    pygame.draw.rect(surface, (20, 16, 30), (tower_x - tower_w // 2, tower_base_y, tower_w, 160))
    for tr in range(tower_base_y, ground - 24, 18):
        off2 = 8 if ((tr - tower_base_y) // 18) % 2 else 0
        for tc in range(tower_x - tower_w // 2 + off2, tower_x + tower_w // 2 - 4, 24):
            tw2 = min(20, tower_x + tower_w // 2 - tc)
            th2 = min(16, ground - 24 - tr)
            shade2 = 22 + (tr * 5 + tc * 3 + seed + 7) % 14
            pygame.draw.rect(surface, (shade2, shade2 - 2, shade2 + 8), (tc, tr, tw2, th2))
            pygame.draw.rect(surface, (10, 6, 18), (tc, tr, tw2, th2), 1)
    pygame.draw.rect(surface, (10, 6, 18), (tower_x - tower_w // 2, tower_base_y, tower_w, 160), 2)
    # crenellations
    for ci in range(5):
        cren_x = tower_x - tower_w // 2 + ci * 12
        pygame.draw.rect(surface, (24, 18, 36), (cren_x, tower_base_y - 12, 10, 14))
        pygame.draw.rect(surface, (10, 6, 18), (cren_x, tower_base_y - 12, 10, 14), 1)
    # conical roof
    tower_roof_pts = [(tower_x - tower_w // 2 - 4, tower_base_y - 10),
                      (tower_x, tower_top_y), (tower_x + tower_w // 2 + 4, tower_base_y - 10)]
    pygame.draw.polygon(surface, (16, 12, 26), tower_roof_pts)
    for trl_y in range(tower_top_y + 14, tower_base_y - 10, 12):
        t_frac = (trl_y - tower_top_y) / max(1, tower_base_y - 10 - tower_top_y)
        trl_hw = int((tower_w // 2 + 4) * t_frac)
        shade3 = 14 + (trl_y * 3 + seed) % 10
        pygame.draw.line(surface, (shade3, shade3 - 2, shade3 + 8),
                         (tower_x - trl_hw, trl_y), (tower_x + trl_hw, trl_y), 1)
    pygame.draw.polygon(surface, (8, 6, 16), tower_roof_pts, 2)
    # tower slit window
    pygame.draw.rect(surface, (10, 6, 18), (tower_x - 5, tower_base_y + 38, 10, 30), border_radius=2)
    tw_glow = int(120 + 80 * math.sin(ticks * 0.003 + seed + 1.0))
    tw_s = pygame.Surface((10, 30), pygame.SRCALPHA)
    pygame.draw.rect(tw_s, (tw_glow // 5, tw_glow // 7, tw_glow, 55), (0, 0, 10, 30), border_radius=2)
    surface.blit(tw_s, (tower_x - 5, tower_base_y + 38), special_flags=pygame.BLEND_RGBA_ADD)
    # arcane orb at peak
    orb_pulse = int(180 + 60 * math.sin(ticks * 0.005 + seed))
    pygame.draw.circle(surface, (orb_pulse // 3, orb_pulse // 5, orb_pulse), (tower_x, tower_top_y + 2), 5)
    for or2, oa2 in ((12, 35), (8, 65), (4, 110)):
        op_s = pygame.Surface((or2 * 2, or2 * 2), pygame.SRCALPHA)
        pygame.draw.circle(op_s, (orb_pulse // 2, 80, orb_pulse, int(oa2 * orb_pulse / 240)), (or2, or2), or2)
        surface.blit(op_s, (tower_x - or2, tower_top_y + 2 - or2), special_flags=pygame.BLEND_RGBA_ADD)

    # ── Main roof: steep slate ──
    roof_peak = ground - 264
    roof_base_y = ground - 190
    roof_l, roof_r = x - 218, x + 116
    roof_cx = (roof_l + roof_r) // 2
    roof_pts = [(roof_l, roof_base_y), (roof_cx, roof_peak), (roof_r, roof_base_y)]
    pygame.draw.polygon(surface, (18, 14, 28), roof_pts)
    for rl_y in range(roof_peak + 12, roof_base_y, 10):
        t_frac2 = (rl_y - roof_peak) / max(1, roof_base_y - roof_peak)
        rl_hw = int(((roof_r - roof_l) // 2) * t_frac2)
        shade4 = 16 + (rl_y * 4 + seed) % 12
        pygame.draw.line(surface, (shade4, shade4 - 2, shade4 + 10),
                         (roof_cx - rl_hw, rl_y), (roof_cx + rl_hw, rl_y), 1)
    pygame.draw.polygon(surface, (8, 6, 16), roof_pts, 3)
    pygame.draw.line(surface, (58, 42, 80), (roof_l, roof_base_y), (roof_r, roof_base_y), 3)
    star_t = int(160 + 80 * math.sin(ticks * 0.004 + seed))
    for sa in range(0, 360, 45):
        sa_rad = math.radians(sa)
        ex2, ey2 = roof_cx + int(math.cos(sa_rad) * 10), roof_peak + int(math.sin(sa_rad) * 10)
        pygame.draw.line(surface, (star_t, star_t // 2, 255), (roof_cx, roof_peak), (ex2, ey2), 1)
    pygame.draw.circle(surface, (star_t, star_t // 2, 255), (roof_cx, roof_peak), 4)
    rstar_s = pygame.Surface((22, 22), pygame.SRCALPHA)
    pygame.draw.circle(rstar_s, (star_t // 2, 60, 220, 55), (11, 11), 10)
    surface.blit(rstar_s, (roof_cx - 11, roof_peak - 11), special_flags=pygame.BLEND_RGBA_ADD)

    # ── Chimney ──
    chim_rect = pygame.Rect(roof_cx - 88, roof_peak + 14, 24, 62)
    pygame.draw.rect(surface, (32, 26, 42), chim_rect)
    for cr_y in range(chim_rect.top, chim_rect.bottom, 9):
        pygame.draw.line(surface, (24, 18, 34), (chim_rect.left + 2, cr_y), (chim_rect.right - 2, cr_y), 1)
    pygame.draw.rect(surface, (14, 10, 24), chim_rect, 2)
    pygame.draw.rect(surface, (44, 34, 60), (chim_rect.left - 5, chim_rect.top - 5, chim_rect.width + 10, 7))

    # ── Stained glass window (6 coloured panes, gothic arch) ──
    win_cx, win_cy = x - 72, ground - 132
    win = pygame.Rect(win_cx - 46, win_cy - 46, 92, 84)
    pygame.draw.rect(surface, (22, 16, 36), win, border_radius=4)
    hue_cycle = ticks * 0.0005
    pane_base = [(100, 40, 200), (40, 160, 220), (200, 80, 40),
                 (40, 200, 120), (200, 160, 40), (120, 40, 200)]
    for pi in range(6):
        pr, pc_row = pi % 2, pi // 2
        pw, ph = 36, 24
        px2 = win.left + 6 + pr * (pw + 6)
        py2 = win.top + 6 + pc_row * (ph + 4)
        pane_col = pane_base[pi]
        pane_bright = int(80 + 50 * math.sin(hue_cycle + pi * 1.05))
        pcr = min(255, pane_col[0] + pane_bright)
        pcg = min(255, pane_col[1] + pane_bright)
        pcb = min(255, pane_col[2] + pane_bright)
        pygame.draw.rect(surface, (pcr // 3, pcg // 3, pcb // 3), (px2, py2, pw, ph), border_radius=2)
        pg_s = pygame.Surface((pw, ph), pygame.SRCALPHA)
        pygame.draw.rect(pg_s, (pcr, pcg, pcb, 38), (0, 0, pw, ph), border_radius=2)
        surface.blit(pg_s, (px2, py2), special_flags=pygame.BLEND_RGBA_ADD)
        pygame.draw.rect(surface, (50, 38, 68), (px2, py2, pw, ph), 1, border_radius=2)
    pygame.draw.line(surface, (46, 36, 62), (win.left + 46, win.top + 4), (win.left + 46, win.bottom - 4), 2)
    for dy in (win.top + 30, win.top + 58):
        pygame.draw.line(surface, (46, 36, 62), (win.left + 4, dy), (win.right - 4, dy), 2)
    win_arch = [(win.left, win.top), (win.centerx, win.top - 24), (win.right, win.top)]
    pygame.draw.polygon(surface, (18, 12, 30), win_arch)
    pygame.draw.polygon(surface, (58, 42, 88), win_arch, 2)
    pygame.draw.rect(surface, (58, 42, 88), win, 2, border_radius=4)
    # window cast light on ground
    wcast_r = int(50 + 35 * math.sin(hue_cycle * 1.1))
    wcast_g = int(25 + 25 * math.sin(hue_cycle * 0.7 + 2.0))
    wcast_b = int(70 + 45 * math.sin(hue_cycle * 0.9 + 4.1))
    wcast_s = pygame.Surface((52, 18), pygame.SRCALPHA)
    pygame.draw.ellipse(wcast_s, (wcast_r, wcast_g, wcast_b, 32), (0, 0, 52, 18))
    surface.blit(wcast_s, (win_cx - 26, ground - 12), special_flags=pygame.BLEND_RGBA_ADD)

    # ── Hanging sign on left: ornate flask chain ──
    hsign_x = x - 162
    hsign_y = ground - 155
    for chi in range(6):
        cy3 = hsign_y - 30 + chi * 5
        pygame.draw.ellipse(surface, (68, 58, 86), (hsign_x - 3, cy3, 6, 4), 1)
    sign_board = pygame.Rect(hsign_x - 28, hsign_y - 4, 56, 42)
    pygame.draw.rect(surface, (18, 14, 30), sign_board, border_radius=4)
    pygame.draw.rect(surface, (78, 58, 108), sign_board, 2, border_radius=4)
    for sdx, sdy in ((sign_board.left + 4, sign_board.top + 4), (sign_board.right - 4, sign_board.top + 4),
                     (sign_board.left + 4, sign_board.bottom - 4), (sign_board.right - 4, sign_board.bottom - 4)):
        pygame.draw.circle(surface, (98, 78, 128), (sdx, sdy), 2)
    sfk_x, sfk_y = sign_board.centerx, sign_board.centery + 3
    pygame.draw.rect(surface, (108, 98, 128), (sfk_x - 4, sfk_y - 14, 8, 7), border_radius=1)
    pygame.draw.ellipse(surface, (38, 28, 58), (sfk_x - 12, sfk_y - 9, 24, 20))
    sign_brew_col = (int(80 + 80 * math.sin(ticks * 0.004 + seed)),
                     int(160 + 60 * math.sin(ticks * 0.003 + seed + 1.0)),
                     int(200 + 50 * math.sin(ticks * 0.005 + seed + 2.0)))
    pygame.draw.ellipse(surface, sign_brew_col, (sfk_x - 8, sfk_y - 5, 16, 12))
    pygame.draw.ellipse(surface, (78, 58, 108), (sfk_x - 12, sfk_y - 9, 24, 20), 1)
    sfg = pygame.Surface((14, 12), pygame.SRCALPHA)
    pygame.draw.ellipse(sfg, (*sign_brew_col, 48), (0, 0, 14, 12))
    surface.blit(sfg, (sfk_x - 7, sfk_y - 5), special_flags=pygame.BLEND_RGBA_ADD)

    # ── Crystal ball on ornate pedestal ──
    cball_x, cball_y = x + 42, ground - 30
    pygame.draw.rect(surface, (34, 28, 46), (cball_x - 16, cball_y, 32, 10), border_radius=2)
    pygame.draw.rect(surface, (58, 48, 76), (cball_x - 16, cball_y, 32, 10), 1, border_radius=2)
    pygame.draw.rect(surface, (40, 32, 54), (cball_x - 8, cball_y - 20, 16, 20), border_radius=2)
    pygame.draw.rect(surface, (58, 48, 76), (cball_x - 8, cball_y - 20, 16, 20), 1, border_radius=2)
    pygame.draw.rect(surface, (48, 38, 62), (cball_x - 12, cball_y - 22, 24, 5), border_radius=2)
    cb_pulse = int(160 + 70 * math.sin(ticks * 0.004 + seed * 0.5))
    cb_col_r = int(60 + 60 * math.sin(ticks * 0.003 + seed))
    cb_col_g = int(80 + 60 * math.sin(ticks * 0.004 + seed + 2.0))
    cb_col_b = int(200 + 40 * math.sin(ticks * 0.005 + seed + 4.0))
    pygame.draw.circle(surface, (38, 32, 56), (cball_x, cball_y - 34), 18)
    pygame.draw.circle(surface, (cb_col_r, cb_col_g, cb_col_b), (cball_x, cball_y - 34), 14)
    pygame.draw.circle(surface, (min(255, cb_col_r + 60), min(255, cb_col_g + 60), 255),
                       (cball_x - 5, cball_y - 40), 5)
    pygame.draw.circle(surface, (210, 210, 255), (cball_x - 7, cball_y - 42), 2)
    pygame.draw.circle(surface, (98, 78, 138), (cball_x, cball_y - 34), 18, 2)
    for rr, ra in ((14, 55), (9, 90), (5, 130)):
        cb_gs = pygame.Surface((rr * 2, rr * 2), pygame.SRCALPHA)
        pygame.draw.circle(cb_gs, (cb_col_r, cb_col_g, cb_col_b, ra), (rr, rr), rr)
        surface.blit(cb_gs, (cball_x - rr, cball_y - 34 - rr), special_flags=pygame.BLEND_RGBA_ADD)
    ring_phase = (ticks * 0.002 + seed) % 1.0
    pr_size = int(20 + 8 * ring_phase)
    pr_alpha = int(55 * (1.0 - ring_phase))
    if pr_alpha > 4:
        pr_s = pygame.Surface((pr_size * 2, pr_size * 2), pygame.SRCALPHA)
        pygame.draw.circle(pr_s, (cb_col_r, cb_col_g, cb_col_b, pr_alpha), (pr_size, pr_size), pr_size, 1)
        surface.blit(pr_s, (cball_x - pr_size, cball_y - 34 - pr_size))

    # ── Giant cauldron (left centerpiece) ──
    cld_x, cld_y = x - 108, ground
    for leg_off in (-20, 0, 20):
        pygame.draw.line(surface, (42, 36, 54), (cld_x + leg_off, cld_y), (cld_x, cld_y - 18), 3)
    cshadow = pygame.Surface((74, 16), pygame.SRCALPHA)
    pygame.draw.ellipse(cshadow, (0, 0, 0, 48), (0, 0, 74, 16))
    surface.blit(cshadow, (cld_x - 37, cld_y - 8))
    pygame.draw.ellipse(surface, (26, 22, 38), (cld_x - 40, cld_y - 58, 80, 62))
    for band_y in (cld_y - 48, cld_y - 30, cld_y - 14):
        band_width = int(72 * math.sqrt(max(0, 1 - ((band_y - (cld_y - 29)) / 32) ** 2)))
        pygame.draw.line(surface, (68, 60, 86),
                         (cld_x - band_width // 2, band_y), (cld_x + band_width // 2, band_y), 2)
    pygame.draw.ellipse(surface, (58, 50, 76), (cld_x - 40, cld_y - 58, 80, 62), 2)
    pygame.draw.ellipse(surface, (60, 52, 78), (cld_x - 42, cld_y - 60, 84, 14))
    pygame.draw.ellipse(surface, (88, 78, 108), (cld_x - 42, cld_y - 60, 84, 14), 2)
    for hr_off in (-38, 38):
        pygame.draw.arc(surface, (78, 68, 98),
                        (cld_x + hr_off - 8, cld_y - 44, 16, 12), 0, math.pi, 2)
    brew_t = ticks * 0.0022
    brew_r = int(50 + 100 * abs(math.sin(brew_t + seed)))
    brew_g = int(160 + 80 * abs(math.sin(brew_t * 0.7 + seed + 1.2)))
    brew_b = int(80 + 120 * abs(math.sin(brew_t * 1.4 + seed + 2.4)))
    pygame.draw.ellipse(surface, (brew_r, brew_g, brew_b), (cld_x - 38, cld_y - 56, 76, 14))
    # ripples
    for rip_i in range(3):
        rip_t = (ticks * 0.002 + seed + rip_i * 0.9) % 1.0
        rip_w = int(8 + 30 * rip_t)
        rip_a = int(60 * (1.0 - rip_t))
        rip_s = pygame.Surface((rip_w * 2, rip_w), pygame.SRCALPHA)
        pygame.draw.ellipse(rip_s, (min(255, brew_r + 40), min(255, brew_g + 40), min(255, brew_b + 40), rip_a),
                            (0, 0, rip_w * 2, rip_w), 1)
        surface.blit(rip_s, (cld_x - rip_w, cld_y - 52))
    for cr3, ca3 in ((14, 85), (9, 125), (5, 165)):
        cgs3 = pygame.Surface((cr3 * 2, cr3 * 2), pygame.SRCALPHA)
        pygame.draw.circle(cgs3, (brew_r, brew_g, brew_b, ca3), (cr3, cr3), cr3)
        surface.blit(cgs3, (cld_x - cr3, cld_y - 52 - cr3), special_flags=pygame.BLEND_RGBA_ADD)
    # fire (7 flames)
    for fi in range(7):
        ft2 = ticks * 0.004 + seed * 0.15 + fi * 0.7
        fx2 = cld_x - 18 + fi * 6 + int(math.sin(ft2 * 2.5) * 4)
        fy2 = cld_y - 4 - int(abs(math.sin(ft2 * 1.8 + fi)) * 12)
        fc_r2 = min(255, 180 + fi * 10)
        fc_g2 = max(0, int(140 - fi * 15) + int(math.sin(ft2 * 3) * 20))
        pygame.draw.circle(surface, (fc_r2, fc_g2, 10), (int(fx2), int(fy2)), 2 + fi % 3)
        pygame.draw.circle(surface, (255, 230, 100), (int(fx2), int(fy2) - 2), 1)
    # rotating runic circle
    rune_circle_a = int(50 + 40 * math.sin(ticks * 0.002 + seed))
    for ra2 in range(0, 360, 30):
        rad2 = math.radians(ra2 + ticks * 0.04)
        rx3 = cld_x + int(math.cos(rad2) * 44)
        ry3 = cld_y - 3 + int(math.sin(rad2) * 10)
        rs2 = pygame.Surface((5, 5), pygame.SRCALPHA)
        pygame.draw.circle(rs2, (110, 60, 230, rune_circle_a), (2, 2), 2)
        surface.blit(rs2, (rx3 - 2, ry3 - 2))
    # overflow drips
    if brew_g > 210:
        for drip_i in range(3):
            drip_t2 = (ticks * 0.0015 + seed + drip_i * 0.7) % 1.0
            if drip_t2 < 0.5:
                dripx = cld_x - 30 + drip_i * 30
                dripY = cld_y - 42 + int(drip_t2 * 34)
                pygame.draw.circle(surface, (brew_r, brew_g, brew_b), (dripx, dripY), 2)

    # ── Reagent shelves (2 rows) ──
    for row, shelf_y in enumerate((ground - 162, ground - 122)):
        shelf_r = pygame.Rect(x - 52, shelf_y, 126, 9)
        pygame.draw.rect(surface, (34, 26, 46), shelf_r, border_radius=2)
        pygame.draw.rect(surface, (62, 50, 80), shelf_r, 1, border_radius=2)
        pots = [(120, 210, 230), (200, 100, 210), (100, 220, 140),
                (230, 190, 80), (90, 140, 230), (210, 80, 100)]
        for pi2 in range(6):
            pc2 = pots[(pi2 + row * 3) % 6]
            _draw_potion_icon(surface, shelf_r.left + 10 + pi2 * 19, shelf_r.bottom, pc2)
            ppulse = int(24 + 18 * math.sin(ticks * 0.005 + pi2 * 0.95 + row * 1.5))
            pg2 = pygame.Surface((10, 10), pygame.SRCALPHA)
            pygame.draw.circle(pg2, (*pc2, ppulse), (5, 5), 4)
            surface.blit(pg2, (shelf_r.left + 5 + pi2 * 19, shelf_r.bottom - 10),
                         special_flags=pygame.BLEND_RGBA_ADD)

    # ── Hanging herb bundles from beam ──
    beam_y2 = ground - 178
    pygame.draw.line(surface, (36, 28, 46), (x - 172, beam_y2), (x - 28, beam_y2), 4)
    for hi2, hx_off2 in enumerate((-158, -132, -106, -80, -54)):
        hx3 = x + hx_off2
        sway = int(math.sin(ticks * 0.001 + hi2 * 0.8 + seed) * 2)
        pygame.draw.line(surface, (52, 42, 24), (hx3, beam_y2), (hx3 + sway, beam_y2 + 22), 1)
        hcol = [(80, 140, 60), (100, 120, 50), (60, 160, 80), (120, 100, 40), (70, 150, 70)][hi2 % 5]
        for li2 in range(4):
            lx2 = hx3 + sway - 4 + li2 * 3
            pygame.draw.line(surface, hcol, (lx2, beam_y2 + 22), (lx2 + (li2 - 1) * 4 + sway, beam_y2 + 34), 1)
        pygame.draw.circle(surface, (68, 52, 32), (hx3 + sway, beam_y2 + 22), 3)

    # ── Work bench with mortar, tome, alembic ──
    bench2 = pygame.Rect(x - 48, ground - 26, 80, 18)
    pygame.draw.rect(surface, (30, 24, 42), bench2, border_radius=3)
    pygame.draw.rect(surface, (58, 48, 76), bench2, 1, border_radius=3)
    for lx3 in (bench2.left + 6, bench2.right - 6):
        pygame.draw.rect(surface, (26, 20, 36), (lx3 - 3, bench2.bottom, 5, 10), border_radius=1)
    pygame.draw.ellipse(surface, (74, 66, 88), (x - 38, bench2.top - 10, 22, 14))
    pygame.draw.ellipse(surface, (48, 42, 64), (x - 38, bench2.top - 10, 22, 14), 1)
    pygame.draw.line(surface, (98, 88, 114), (x - 30, bench2.top - 12), (x - 24, bench2.top - 20), 2)
    pygame.draw.rect(surface, (128, 98, 62), (x - 12, bench2.top - 14, 32, 22), border_radius=2)
    pygame.draw.rect(surface, (88, 68, 42), (x - 12, bench2.top - 14, 32, 22), 1, border_radius=2)
    pygame.draw.line(surface, (68, 48, 34), (x + 4, bench2.top - 14), (x + 4, bench2.top + 8), 1)
    for tl2 in range(3):
        pygame.draw.line(surface, (52, 42, 30), (x - 10, bench2.top - 9 + tl2 * 6), (x + 2, bench2.top - 9 + tl2 * 6), 1)
        pygame.draw.line(surface, (52, 42, 30), (x + 7, bench2.top - 9 + tl2 * 6), (x + 18, bench2.top - 9 + tl2 * 6), 1)
    # small alembic
    alb_x = x + 24
    pygame.draw.ellipse(surface, (26, 22, 38), (alb_x - 10, bench2.top - 18, 20, 14))
    alb_col = (int(100 + 80 * math.sin(ticks * 0.004 + seed + 1.0)),
               int(180 + 60 * math.sin(ticks * 0.003 + seed + 2.0)),
               int(140 + 80 * math.sin(ticks * 0.005 + seed + 3.0)))
    pygame.draw.ellipse(surface, alb_col, (alb_x - 7, bench2.top - 14, 14, 9))
    pygame.draw.ellipse(surface, (58, 48, 76), (alb_x - 10, bench2.top - 18, 20, 14), 1)
    pygame.draw.rect(surface, (68, 108, 98), (alb_x - 2, bench2.top - 26, 4, 10), border_radius=1)

    # ── Distillation apparatus (right area) ──
    dist_x = x + 74
    pygame.draw.rect(surface, (38, 32, 50), (dist_x - 22, ground - 86, 4, 86), border_radius=1)
    pygame.draw.rect(surface, (38, 32, 50), (dist_x + 18, ground - 86, 4, 86), border_radius=1)
    pygame.draw.rect(surface, (38, 32, 50), (dist_x - 22, ground - 86, 44, 4), border_radius=1)
    pygame.draw.rect(surface, (54, 46, 68), (dist_x - 22, ground - 86, 44, 4), 1, border_radius=1)
    pygame.draw.ellipse(surface, (22, 18, 34), (dist_x - 18, ground - 48, 36, 30))
    pygame.draw.ellipse(surface, (68, 148, 128), (dist_x - 14, ground - 44, 28, 22))
    pygame.draw.ellipse(surface, (48, 108, 98), (dist_x - 18, ground - 48, 36, 30), 1)
    pygame.draw.rect(surface, (58, 118, 108), (dist_x - 3, ground - 60, 6, 14), border_radius=2)
    pygame.draw.ellipse(surface, (22, 18, 34), (dist_x - 13, ground - 78, 26, 20))
    upper_col = (int(80 + 70 * math.sin(ticks * 0.004 + seed)),
                 int(100 + 90 * math.sin(ticks * 0.003 + seed + 1.5)),
                 int(180 + 60 * math.sin(ticks * 0.005 + seed + 3.0)))
    pygame.draw.ellipse(surface, upper_col, (dist_x - 9, ground - 74, 18, 13))
    pygame.draw.ellipse(surface, (48, 68, 88), (dist_x - 13, ground - 78, 26, 20), 1)
    pygame.draw.line(surface, (48, 88, 78), (dist_x + 12, ground - 66), (dist_x + 30, ground - 52), 2)
    pygame.draw.line(surface, (48, 88, 78), (dist_x + 30, ground - 52), (dist_x + 30, ground - 34), 2)
    pygame.draw.ellipse(surface, (22, 18, 34), (dist_x + 22, ground - 38, 18, 14))
    pygame.draw.ellipse(surface, (178, 118, 58), (dist_x + 24, ground - 35, 14, 9))
    pygame.draw.ellipse(surface, (48, 40, 62), (dist_x + 22, ground - 38, 18, 14), 1)
    for flask_pos, flask_col in (((dist_x, ground - 33), (68, 148, 128)),
                                  ((dist_x, ground - 65), upper_col),
                                  ((dist_x + 31, ground - 29), (178, 118, 58))):
        for fg_r, fg_a in ((9, 38), (5, 68)):
            fg_s = pygame.Surface((fg_r * 2, fg_r * 2), pygame.SRCALPHA)
            pygame.draw.circle(fg_s, (*flask_col, fg_a), (fg_r, fg_r), fg_r)
            surface.blit(fg_s, (flask_pos[0] - fg_r, flask_pos[1] - fg_r), special_flags=pygame.BLEND_RGBA_ADD)
    drip_phase = (ticks * 0.0018 + seed) % 1.0
    if drip_phase > 0.66:
        dy = ground - 24 + int((drip_phase - 0.66) / 0.34 * 14)
        pygame.draw.circle(surface, (178, 118, 58), (dist_x + 31, dy), 2)

    # ═══════════════════════════════════════
    # VFX & PARTICLES
    # ═══════════════════════════════════════

    # ── Ground mist (low-lying magical fog) ──
    mist_t = ticks * 0.0006
    for mi in range(7):
        mt = mist_t + mi * 0.38 + seed * 0.07
        mx = x - 188 + int((mi / 17) * 376) + int(math.sin(mt + mi) * 14)
        my = ground - 7 - int(abs(math.sin(mt * 0.5 + mi)) * 8)
        mw = 30 + mi % 18
        mh = 11 + mi % 7
        ms = pygame.Surface((mw, mh), pygame.SRCALPHA)
        mist_a = max(1, int(8 + 11 * math.sin(mt * 0.7 + mi)))
        pygame.draw.ellipse(ms, (130, 100, 190, mist_a), ms.get_rect())
        surface.blit(ms, (mx - mw // 2, my - mh // 2))

    # ── Cauldron rising bubbles ──
    for i in range(8):
        t = ticks * 0.0012 + seed * 0.11 + i * 0.5
        life = (t * 22 + i * 7) % 54
        bx = cld_x + int(math.sin(t * 1.9 + i) * 28)
        by = int(cld_y - 44 - life * 1.2)
        radius = max(1, 3 - int(life / 18))
        fade = max(0, 180 - int(life * 3.4))
        b_r2 = min(255, int(brew_r * 0.7 + 50))
        b_g2 = min(255, int(brew_g * 0.6 + 40))
        b_b2 = min(255, int(brew_b * 0.7 + 50))
        bs = pygame.Surface((radius * 2 + 2, radius * 2 + 2), pygame.SRCALPHA)
        pygame.draw.circle(bs, (b_r2, b_g2, b_b2, fade), (radius + 1, radius + 1), radius)
        pygame.draw.circle(bs, (255, 255, 255, fade // 4), (radius, radius), max(1, radius - 1), 1)
        surface.blit(bs, (bx - radius - 1, by - radius - 1))

    # ── Cauldron steam ──
    for i in range(4):
        t = ticks * 0.0009 + seed * 0.07 + i * 1.1
        sx = cld_x + int(math.sin(t * 1.2 + i) * 22)
        sy = cld_y - 50 - int((t * 20 + i * 9) % 42)
        sz = 12 + i * 4
        sm = pygame.Surface((sz, sz), pygame.SRCALPHA)
        a = max(5, 54 - i * 6)
        scol = (78, 38, 148) if i % 3 == 0 else (48, 128, 178) if i % 3 == 1 else (98, 58, 158)
        pygame.draw.ellipse(sm, (*scol, a), sm.get_rect())
        surface.blit(sm, (int(sx) - sz // 2, int(sy) - sz // 2), special_flags=pygame.BLEND_RGBA_ADD)

    # ── Lightning arc: tower peak → cauldron (periodic) ──
    arc_phase = (ticks * 0.0025 + seed) % 1.0
    if arc_phase < 0.06:
        arc_int = int(200 * math.sin(arc_phase / 0.14 * math.pi))
        arc_start = (tower_x, tower_top_y)
        arc_end = (cld_x, cld_y - 50)
        prev_pt = arc_start
        for ai in range(1, 11):
            t_f = ai / 10
            nx = int(arc_start[0] + (arc_end[0] - arc_start[0]) * t_f)
            ny = int(arc_start[1] + (arc_end[1] - arc_start[1]) * t_f)
            jx = int(math.sin(ticks * 0.11 + ai * 2.7) * 13 * (1.0 - abs(t_f - 0.5) * 2))
            jy = int(math.cos(ticks * 0.09 + ai * 1.9) * 6 * (1.0 - abs(t_f - 0.5) * 2))
            cur_pt = (nx + jx, ny + jy)
            pygame.draw.line(surface, (arc_int, arc_int // 2, 255), prev_pt, cur_pt, 1)
            if ai % 3 == 0 and ai < 10:
                bx3 = cur_pt[0] + int(math.sin(ticks * 0.2 + ai) * 22)
                by3 = cur_pt[1] + int(math.cos(ticks * 0.2 + ai) * 22)
                pygame.draw.line(surface, (arc_int // 2, arc_int // 4, 200), cur_pt, (bx3, by3), 1)
            prev_pt = cur_pt

    # ── Orbiting sparks around cauldron ──
    for i in range(5):
        t = ticks * 0.0022 + i * 0.449
        orbit_r2 = 42 + (i % 4) * 9
        spark_x2 = cld_x + int(math.cos(t + i * 0.7) * orbit_r2)
        spark_y2 = cld_y - 28 + int(math.sin(t + i * 0.7) * orbit_r2 * 0.28)
        sc2 = [(180, 80, 255), (80, 220, 200), (255, 180, 60),
               (100, 200, 255), (255, 80, 160), (60, 255, 120), (255, 200, 80)][i % 7]
        bright2 = int(140 + 90 * math.sin(ticks * 0.007 + i * 1.2))
        ss2 = pygame.Surface((6, 6), pygame.SRCALPHA)
        pygame.draw.circle(ss2, (*sc2, bright2), (3, 3), 1 + i % 2)
        surface.blit(ss2, (spark_x2 - 3, spark_y2 - 3), special_flags=pygame.BLEND_RGBA_ADD)

    # ── Mana orbs (2 drifting) ──
    orb_colors = [(120, 80, 255), (60, 200, 220), (220, 100, 180), (80, 220, 140), (220, 180, 60)]
    for i in range(2):
        ot2 = ticks * 0.0007 + i * 1.26
        ox2 = x - 80 + int(math.sin(ot2 + i * 1.1) * 72)
        oy2 = ground - 82 + int(math.cos(ot2 * 0.8 + i) * 32)
        oc2 = orb_colors[i]
        ob2 = int(120 + 90 * math.sin(ticks * 0.005 + i * 2.05))
        for or3, oa3 in ((10, 24), (6, 50), (3, 88)):
            ogs2 = pygame.Surface((or3 * 2, or3 * 2), pygame.SRCALPHA)
            pygame.draw.circle(ogs2, (*oc2, int(oa3 * ob2 / 210)), (or3, or3), or3)
            surface.blit(ogs2, (ox2 - or3, oy2 - or3), special_flags=pygame.BLEND_RGBA_ADD)
        pygame.draw.circle(surface, (230, 220, 255), (ox2, oy2), 2)

    # ── Floating rune symbols drifting upward ──
    for i in range(4):
        t = ticks * 0.0007 + seed * 0.13 + i * 0.89
        life_r = (t * 12 + i * 5) % 62
        rx4 = x - 162 + int((i / 9) * 290) + int(math.sin(t + i) * 12)
        ry4 = ground - 58 - int(life_r * 1.8)
        rc4 = [(120, 80, 220), (80, 200, 180), (220, 120, 80), (80, 120, 220),
               (180, 80, 200), (80, 220, 120), (220, 80, 120), (120, 180, 220),
               (200, 200, 80), (80, 160, 220)][i]
        fade_r = max(0, 100 - int(life_r * 1.6))
        if fade_r > 2:
            rs3 = pygame.Surface((10, 10), pygame.SRCALPHA)
            pygame.draw.circle(rs3, (*rc4, fade_r), (5, 5), 4, 1)
            pygame.draw.line(rs3, (*rc4, fade_r), (5, 1), (5, 9), 1)
            pygame.draw.line(rs3, (*rc4, fade_r), (1, 5), (9, 5), 1)
            surface.blit(rs3, (rx4 - 5, ry4 - 5))

    # ── Chimney arcane vapour ──
    for i in range(7):
        t = ticks * 0.0008 + seed * 0.06 + i * 1.0
        sx3 = chim_rect.centerx + math.sin(t * 1.5 + i) * (5 + i * 2)
        sy3 = chim_rect.top - 8 - (t * 14 + i * 6) % 36
        sz3 = 8 + i * 3
        sm3 = pygame.Surface((sz3, sz3), pygame.SRCALPHA)
        vc = (88, 48, 198) if i % 2 == 0 else (48, 138, 198)
        pygame.draw.ellipse(sm3, (*vc, max(6, 46 - i * 6)), sm3.get_rect())
        surface.blit(sm3, (int(sx3) - sz3 // 2, int(sy3) - sz3 // 2), special_flags=pygame.BLEND_RGBA_ADD)

    # ── Stained glass window light beams ──
    for pane_i in range(6):
        pr2, pc3 = pane_i % 2, pane_i // 2
        pane_cx = win.left + 6 + pr2 * (36 + 6) + 18
        pane_cy = win.top + 6 + pc3 * (24 + 4) + 12
        pcol2 = pane_base[pane_i]
        pb2 = int(38 + 28 * math.sin(hue_cycle + pane_i * 1.05))
        beam_surf = pygame.Surface((20, 38), pygame.SRCALPHA)
        for bby in range(38):
            beam_a = int(pb2 * (1.0 - bby / 38) * 0.55)
            if beam_a > 0:
                pygame.draw.line(beam_surf, (*pcol2, beam_a), (0, bby), (19, bby))
        surface.blit(beam_surf, (pane_cx - 10, pane_cy), special_flags=pygame.BLEND_RGBA_ADD)

    # ── Reagent shelf energy wisps ──
    for i in range(4):
        t = ticks * 0.0013 + seed * 0.09 + i * 0.7
        life_w = (t * 18 + i * 8) % 50
        wx = (x - 48) + int((i / 9) * 114)
        wy = ground - 120 - int(life_w * 1.2)
        wc2 = [(130, 80, 220), (80, 200, 180), (220, 130, 80), (80, 130, 220),
               (180, 80, 200), (80, 220, 120), (220, 80, 130), (130, 180, 220),
               (200, 200, 80), (80, 200, 220)][i]
        fade_w = max(0, 78 - int(life_w * 1.6))
        if fade_w > 2:
            ws = pygame.Surface((7, 7), pygame.SRCALPHA)
            pygame.draw.circle(ws, (*wc2, fade_w), (3, 3), 2)
            surface.blit(ws, (wx - 3, wy - 3))

    # ── Ambient sparkles ──
    for i in range(6):
        t = ticks * 0.0015 + seed * 0.17 + i * 0.55
        spark_life = (t * 14 + i * 6) % 1.0
        sax = x - 178 + int((i / 19) * 356) + int(math.sin(t * 2 + i) * 20)
        say = ground - 22 - int(spark_life * 165)
        bright_s = int(200 * math.sin(spark_life * math.pi))
        if bright_s > 20:
            sc3 = [(200, 160, 255), (160, 220, 255), (255, 200, 160),
                   (160, 255, 200), (255, 160, 220)][i % 5]
            sa_surf = pygame.Surface((4, 4), pygame.SRCALPHA)
            pygame.draw.circle(sa_surf, (*sc3, bright_s), (2, 2), 1)
            surface.blit(sa_surf, (sax - 2, say - 2), special_flags=pygame.BLEND_RGBA_ADD)

    # ── Crystal glints on distillation glass ──
    glint = math.sin(ticks * 0.007 + seed)
    if glint > 0.55:
        intensity = int((glint - 0.55) / 0.45 * 255)
        for gpt in ((dist_x - 12, ground - 72), (dist_x + 22, ground - 35), (dist_x - 14, ground - 42)):
            gs3 = pygame.Surface((10, 10), pygame.SRCALPHA)
            pygame.draw.line(gs3, (255, 255, 255, intensity), (5, 0), (5, 9))
            pygame.draw.line(gs3, (255, 255, 255, intensity // 2), (0, 5), (9, 5))
            surface.blit(gs3, (gpt[0] - 5, gpt[1] - 5), special_flags=pygame.BLEND_RGBA_ADD)


def _draw_tailor_shop(surface: pygame.Surface, pos: Vector2, ticks: int, seed: int) -> None:
    x = int(pos.x)
    ground = int(pos.y)

    # ── Back wall: timber-frame with cream plaster panels ──
    wall = pygame.Rect(x - 190, ground - 180, 380, 160)
    pygame.draw.rect(surface, (178, 168, 152), wall)
    for col_idx, col_start in enumerate((wall.left + 3, wall.left + 98, wall.centerx + 3, wall.right - 92)):
        for row_idx, row_start in enumerate((wall.top + 3, wall.top + 65)):
            panel = pygame.Rect(col_start + 2, row_start + 2, 85, 55)
            shade = 192 + (col_start * 3 + row_start * 5 + seed) % 14
            pygame.draw.rect(surface, (shade, shade - 10, shade - 16), panel)
            for py in range(panel.top + 3, panel.bottom - 2, 5):
                if (py // 5 + col_idx + seed) % 4 == 0:
                    pygame.draw.line(surface, (shade - 12, shade - 20, shade - 26),
                                     (panel.left + 1, py), (panel.right - 1, py), 1)
    for by in (wall.top, wall.top + 63, wall.bottom):
        pygame.draw.rect(surface, (82, 60, 40), (wall.left, by - 3, wall.width, 6))
        pygame.draw.rect(surface, (58, 42, 28), (wall.left, by - 3, wall.width, 6), 1)
    for bx in (wall.left, wall.left + 95, wall.centerx, wall.right - 95, wall.right):
        pygame.draw.rect(surface, (82, 60, 40), (bx - 3, wall.top, 6, wall.height))
        pygame.draw.rect(surface, (58, 42, 28), (bx - 3, wall.top, 6, wall.height), 1)
    pygame.draw.line(surface, (70, 50, 32), (wall.left + 3, wall.top + 3), (wall.left + 92, wall.top + 59), 2)
    pygame.draw.rect(surface, (46, 36, 26), wall, 2)

    # ── Roof: A-frame terracotta with striped awning ──
    roof_peak = ground - 240
    roof_l = x - 210
    roof_r = x + 210
    roof_base_y = ground - 176
    roof_pts = [(roof_l, roof_base_y), (x, roof_peak), (roof_r, roof_base_y)]
    pygame.draw.polygon(surface, (88, 56, 46), roof_pts)
    for ry in range(roof_peak + 12, roof_base_y, 10):
        t_row = (ry - roof_peak) / max(1, roof_base_y - roof_peak)
        half_w = int(210 * t_row)
        shade = 82 + (ry * 7 + seed) % 14
        pygame.draw.line(surface, (shade, shade // 2 + 4, shade // 2),
                         (x - half_w, ry), (x + half_w, ry), 1)
    pygame.draw.polygon(surface, (56, 36, 28), roof_pts, 3)
    pygame.draw.line(surface, (112, 82, 66), (x - 6, roof_peak), (x + 6, roof_peak), 4)
    pygame.draw.line(surface, (122, 90, 72), (roof_l, roof_base_y), (roof_r, roof_base_y), 3)
    # striped fabric awning below eave
    awning_y = ground - 175
    for i in range(8):
        ax = x - 190 + i * 48
        col = (148, 62, 84) if i % 2 == 0 else (92, 54, 108)
        pygame.draw.polygon(surface, col, [
            (ax, awning_y), (ax + 44, awning_y),
            (ax + 38, awning_y + 18), (ax + 6, awning_y + 18)
        ])
        pygame.draw.polygon(surface, (56, 28, 48), [
            (ax, awning_y), (ax + 44, awning_y),
            (ax + 38, awning_y + 18), (ax + 6, awning_y + 18)
        ], 1)

    # ── Small chimney with smoke ──
    chim = pygame.Rect(x - 118, roof_peak - 10, 20, 50)
    pygame.draw.rect(surface, (88, 78, 72), chim)
    for cy in range(chim.top, chim.bottom, 8):
        pygame.draw.line(surface, (70, 60, 54), (chim.left + 2, cy), (chim.right - 2, cy), 1)
    pygame.draw.rect(surface, (50, 42, 36), chim, 2)
    pygame.draw.rect(surface, (72, 62, 56), (chim.left - 3, chim.top - 3, chim.width + 6, 5))
    for i in range(4):
        t = ticks * 0.0007 + seed * 0.06 + i * 0.9
        sx = chim.centerx + math.sin(t * 1.2 + i) * (5 + i * 2)
        sy = chim.top - 8 - (t * 14 + i * 6) % 32
        sz = 6 + i * 3
        sm = pygame.Surface((sz, sz), pygame.SRCALPHA)
        pygame.draw.ellipse(sm, (200, 190, 210, max(12, 60 - i * 14)), sm.get_rect())
        surface.blit(sm, (int(sx) - sz // 2, int(sy) - sz // 2), special_flags=pygame.BLEND_RGBA_ADD)

    # ── Hanging sign (scissors + needle) ──
    sign_x = x + 162
    sign_y = ground - 160
    pygame.draw.line(surface, (78, 68, 58), (sign_x - 28, sign_y - 28), (sign_x, sign_y - 28), 3)
    pygame.draw.line(surface, (78, 68, 58), (sign_x - 28, sign_y - 28), (sign_x - 28, sign_y - 18), 2)
    pygame.draw.line(surface, (118, 108, 98), (sign_x - 16, sign_y - 28), (sign_x - 12, sign_y - 18), 1)
    pygame.draw.line(surface, (118, 108, 98), (sign_x + 2, sign_y - 28), (sign_x - 2, sign_y - 18), 1)
    sign_rect = pygame.Rect(sign_x - 26, sign_y - 18, 52, 34)
    pygame.draw.rect(surface, (72, 54, 46), sign_rect, border_radius=3)
    pygame.draw.rect(surface, (132, 102, 82), sign_rect, 2, border_radius=3)
    sc_x, sc_y = sign_rect.centerx, sign_rect.centery + 4
    pygame.draw.line(surface, (200, 202, 212), (sc_x - 10, sc_y - 6), (sc_x + 6, sc_y + 6), 2)
    pygame.draw.line(surface, (200, 202, 212), (sc_x - 10, sc_y + 6), (sc_x + 6, sc_y - 6), 2)
    pygame.draw.circle(surface, (168, 170, 180), (sc_x - 10, sc_y - 6), 3)
    pygame.draw.circle(surface, (168, 170, 180), (sc_x - 10, sc_y + 6), 3)
    pygame.draw.line(surface, (220, 220, 232), (sc_x + 2, sc_y - 10), (sc_x + 10, sc_y - 2), 1)
    pygame.draw.circle(surface, (190, 166, 106), (sc_x + 2, sc_y - 10), 2)

    # ── Display window with flower box ──
    win = pygame.Rect(x - 78, ground - 160, 96, 76)
    pygame.draw.rect(surface, (48, 68, 88), win, border_radius=4)
    pygame.draw.rect(surface, (96, 128, 158), win.inflate(-4, -4), border_radius=3)
    for wy in range(win.top + 4, win.bottom - 4, 8):
        pygame.draw.line(surface, (78, 108, 138), (win.left + 4, wy), (win.right - 4, wy), 1)
    pygame.draw.line(surface, (128, 158, 188), (win.centerx, win.top + 2), (win.centerx, win.bottom - 2), 1)
    pygame.draw.line(surface, (128, 158, 188), (win.left + 2, win.centery), (win.right - 2, win.centery), 1)
    pygame.draw.rect(surface, (88, 68, 50), win, 2, border_radius=4)
    fbox = pygame.Rect(win.left - 4, win.bottom - 2, win.width + 8, 10)
    pygame.draw.rect(surface, (78, 60, 40), fbox, border_radius=2)
    for fi, fc in enumerate([(220, 80, 100), (240, 190, 60), (180, 80, 210), (80, 200, 120)]):
        fx = fbox.left + 8 + fi * 22
        pygame.draw.circle(surface, fc, (fx, fbox.top - 4), 4)
        pygame.draw.line(surface, (60, 120, 60), (fx, fbox.top - 1), (fx, fbox.top + 4), 1)

    # ── Dress form / mannequin (left side) ──
    mf_x, mf_y = x - 122, ground
    pygame.draw.rect(surface, (78, 68, 58), (mf_x - 1, mf_y - 60, 3, 60), border_radius=1)
    pygame.draw.ellipse(surface, (58, 48, 38), (mf_x - 16, mf_y - 6, 32, 8))
    pygame.draw.ellipse(surface, (188, 158, 138), (mf_x - 14, mf_y - 56, 28, 40))
    pygame.draw.ellipse(surface, (158, 128, 108), (mf_x - 14, mf_y - 56, 28, 40), 1)
    pygame.draw.line(surface, (98, 78, 62), (mf_x - 16, mf_y - 52), (mf_x + 16, mf_y - 52), 3)
    pygame.draw.line(surface, (98, 78, 62), (mf_x, mf_y - 56), (mf_x, mf_y - 62), 2)
    dress_pts = [(mf_x - 13, mf_y - 50), (mf_x + 13, mf_y - 50),
                 (mf_x + 18, mf_y - 22), (mf_x - 18, mf_y - 22)]
    pygame.draw.polygon(surface, (142, 62, 92), dress_pts)
    pygame.draw.polygon(surface, (98, 38, 68), dress_pts, 1)
    for si in range(3):
        pygame.draw.line(surface, (182, 102, 132), (mf_x - 10, mf_y - 48 + si * 8),
                         (mf_x + 10, mf_y - 48 + si * 8), 1)

    # ── Fabric bolt shelf (right side) ──
    shelf = pygame.Rect(x + 42, ground - 160, 128, 58)
    pygame.draw.rect(surface, (62, 48, 36), shelf, border_radius=4)
    pygame.draw.rect(surface, (102, 82, 62), shelf, 1, border_radius=4)
    pygame.draw.line(surface, (82, 64, 46), (shelf.left + 2, shelf.centery), (shelf.right - 2, shelf.centery), 2)
    for bi, bc in enumerate([(162, 62, 82), (62, 112, 172), (82, 162, 92),
                              (202, 172, 72), (132, 62, 162), (182, 122, 62)]):
        bx2 = shelf.left + 8 + (bi % 3) * 38
        by2 = shelf.top + 6 + (bi // 3) * 24
        pygame.draw.rect(surface, bc, (bx2, by2, 32, 16), border_radius=2)
        pygame.draw.rect(surface, (max(0, bc[0]-40), max(0, bc[1]-20), max(0, bc[2]-20)),
                         (bx2, by2, 32, 16), 1, border_radius=2)
        pygame.draw.ellipse(surface, (min(255, bc[0]+28), min(255, bc[1]+18), min(255, bc[2]+18)),
                            (bx2 + 2, by2 + 2, 28, 12))

    # ── Sewing table with tools ──
    stable = pygame.Rect(x - 58, ground - 22, 98, 16)
    pygame.draw.rect(surface, (74, 58, 42), stable, border_radius=3)
    pygame.draw.rect(surface, (122, 98, 74), stable, 1, border_radius=3)
    for ly in range(stable.top + 2, stable.bottom - 1, 3):
        pygame.draw.line(surface, (66, 52, 38), (stable.left + 2, ly), (stable.right - 2, ly), 1)
    for lx in (stable.left + 5, stable.right - 5):
        pygame.draw.rect(surface, (64, 50, 36), (lx - 2, stable.bottom, 4, 10), border_radius=1)
    sc2x = x - 18
    pygame.draw.line(surface, (182, 187, 197), (sc2x - 8, stable.top - 4), (sc2x + 4, stable.top + 4), 2)
    pygame.draw.line(surface, (182, 187, 197), (sc2x - 8, stable.top + 4), (sc2x + 4, stable.top - 4), 2)
    pygame.draw.circle(surface, (152, 157, 167), (sc2x - 8, stable.top - 4), 2)
    pygame.draw.circle(surface, (152, 157, 167), (sc2x - 8, stable.top + 4), 2)
    pygame.draw.rect(surface, (182, 162, 102), (x + 16, stable.top - 6, 8, 8), border_radius=2)
    pygame.draw.rect(surface, (142, 122, 72), (x + 16, stable.top - 6, 8, 8), 1, border_radius=2)
    pygame.draw.rect(surface, (102, 82, 62), (x + 28, stable.top - 4, 12, 6), border_radius=2)
    for ni in range(3):
        pygame.draw.line(surface, (202, 202, 212),
                         (x + 29 + ni * 4, stable.top - 7), (x + 29 + ni * 4, stable.top - 1), 1)

    # ── Cloth rolls on table ──
    _draw_cloth_roll(surface, x - 44, ground - 16, (172, 82, 112))
    _draw_cloth_roll(surface, x - 20, ground - 16, (82, 132, 182))
    _draw_cloth_roll(surface, x + 4, ground - 16, (162, 152, 72))

    # ── Hanging garments (animated sway) ──
    rail_y = ground - 165
    pygame.draw.line(surface, (92, 82, 72), (x - 58, rail_y), (x + 22, rail_y), 3)
    for hi, hx in enumerate((x - 48, x - 28, x - 8, x + 12)):
        pygame.draw.arc(surface, (112, 107, 102), (hx - 4, rail_y, 8, 8), 3.14, 6.28, 2)
        sway = int(math.sin(ticks * 0.0018 + hi * 1.1) * 2)
        hue = [(162, 62, 82), (72, 122, 182), (82, 162, 82), (202, 162, 62)][hi]
        gpts = [(hx - 9 + sway, rail_y + 10), (hx + 9 + sway, rail_y + 10),
                (hx + 12 + sway, rail_y + 34), (hx - 12 + sway, rail_y + 34)]
        pygame.draw.polygon(surface, hue, gpts)
        pygame.draw.polygon(surface, (max(0, hue[0]-42), max(0, hue[1]-32), max(0, hue[2]-32)), gpts, 1)
        # highlight sheen sweep across garment
        sheen_x = int((math.sin(ticks * 0.0009 + hi * 0.8) * 0.5 + 0.5) * 18)
        sh = pygame.Surface((6, 22), pygame.SRCALPHA)
        pygame.draw.rect(sh, (255, 255, 255, 28), sh.get_rect(), border_radius=2)
        surface.blit(sh, (hx - 9 + sway + sheen_x, rail_y + 12))
        pygame.draw.line(surface, (max(0, hue[0]-22), max(0, hue[1]-17), max(0, hue[2]-17)),
                         (hx - 9 + sway, rail_y + 14), (hx - 16 + sway, rail_y + 22), 2)

    # ── Hanging lantern outside shop (right bracket) ──
    lan_x, lan_y = x + 175, ground - 148
    pygame.draw.line(surface, (70, 62, 54), (x + 190, ground - 176), (lan_x, lan_y - 12), 2)
    pygame.draw.line(surface, (70, 62, 54), (lan_x, lan_y - 12), (lan_x, lan_y), 1)
    lan_swing = int(math.sin(ticks * 0.0014) * 3)
    lan_sx = lan_x + lan_swing
    # lantern body
    pygame.draw.rect(surface, (54, 46, 36), (lan_sx - 7, lan_y, 14, 18), border_radius=3)
    pygame.draw.rect(surface, (100, 88, 70), (lan_sx - 7, lan_y, 14, 18), 1, border_radius=3)
    pygame.draw.rect(surface, (54, 46, 36), (lan_sx - 5, lan_y - 4, 10, 5), border_radius=2)
    # lantern glass glow (warm flicker)
    lan_flicker = int(180 + 40 * math.sin(ticks * 0.011 + seed))
    pygame.draw.rect(surface, (lan_flicker, int(lan_flicker * 0.7), 30), (lan_sx - 5, lan_y + 2, 10, 13), border_radius=2)
    # lantern outer glow — tight radius, not a blob
    for lr, la in ((14, 28), (9, 48), (5, 70)):
        lg = pygame.Surface((lr * 2, lr * 2), pygame.SRCALPHA)
        pygame.draw.circle(lg, (255, 200, 80, la), (lr, lr), lr)
        surface.blit(lg, (lan_sx - lr, lan_y + 8 - lr), special_flags=pygame.BLEND_RGBA_ADD)

    # ── Candles on windowsill — layered flame + tight glow ──
    for ci, cx_off in enumerate((-70, -50)):
        cx_pos = x + cx_off
        cy_pos = win.bottom + 6
        pygame.draw.rect(surface, (232, 212, 182), (cx_pos - 2, cy_pos - 10, 5, 10), border_radius=1)
        pygame.draw.rect(surface, (182, 162, 132), (cx_pos - 3, cy_pos, 7, 4), border_radius=1)
        flicker = math.sin(ticks * 0.011 + ci * 2.3)
        flame_h = 7 + int(abs(flicker) * 3)
        flame_y = cy_pos - 10 - flame_h
        lean = int(flicker * 1.5)
        # outer flame (orange)
        pygame.draw.polygon(surface, (240, 140, 30), [
            (cx_pos - 3, cy_pos - 10), (cx_pos + 3, cy_pos - 10),
            (cx_pos + 1 + lean, flame_y + 3), (cx_pos + lean, flame_y)
        ])
        # inner flame (yellow-white)
        pygame.draw.polygon(surface, (255, 230, 140), [
            (cx_pos - 1, cy_pos - 10), (cx_pos + 1, cy_pos - 10),
            (cx_pos + lean, flame_y + 4)
        ])
        # tight per-candle glow
        for cr, ca in ((10, 44), (6, 68), (3, 90)):
            cg = pygame.Surface((cr * 2, cr * 2), pygame.SRCALPHA)
            pygame.draw.circle(cg, (255, 190, 60, ca), (cr, cr), cr)
            surface.blit(cg, (cx_pos - cr, flame_y - cr + 2), special_flags=pygame.BLEND_RGBA_ADD)
        # candle smoke wisp
        for wi in range(2):
            wt = ticks * 0.0009 + ci * 1.7 + wi * 0.6
            wx = cx_pos + int(math.sin(wt * 2.1) * 3)
            wy = flame_y - 4 - int((wt * 10 + wi * 4) % 14)
            ws = pygame.Surface((6, 6), pygame.SRCALPHA)
            pygame.draw.circle(ws, (180, 175, 190, max(8, 38 - wi * 16)), (3, 3), 2)
            surface.blit(ws, (wx - 3, wy - 3))

    # ── Window light beam (thin diagonal ray, not a blob) ──
    beam = pygame.Surface((win.width - 8, 40), pygame.SRCALPHA)
    for brow in range(beam.get_height()):
        alpha = max(0, 18 - brow)
        pygame.draw.line(beam, (255, 230, 160, alpha), (0, brow), (beam.get_width(), brow + 6))
    surface.blit(beam, (win.left + 4, win.bottom), special_flags=pygame.BLEND_RGBA_ADD)

    # ── Dust motes in window beam ──
    for i in range(10):
        t = ticks * 0.0006 + seed * 0.11 + i * 0.73
        mote_x = win.left + 4 + int((math.sin(t * 0.7 + i) * 0.5 + 0.5) * (win.width - 12))
        mote_y = win.bottom + int((t * 8 + i * 5) % 36)
        alpha = max(0, 60 - int((t * 8 + i * 5) % 36) * 1.5)
        ms = pygame.Surface((4, 4), pygame.SRCALPHA)
        pygame.draw.circle(ms, (255, 240, 200, int(alpha)), (2, 2), 1)
        surface.blit(ms, (mote_x - 2, mote_y - 2))

    # ── Flower pots at ground level ──
    for px_off in (-162, 142):
        px2 = x + px_off
        pygame.draw.polygon(surface, (132, 82, 62), [
            (px2 - 8, ground), (px2 + 8, ground),
            (px2 + 6, ground - 14), (px2 - 6, ground - 14)
        ])
        pygame.draw.polygon(surface, (102, 62, 46), [
            (px2 - 8, ground), (px2 + 8, ground),
            (px2 + 6, ground - 14), (px2 - 6, ground - 14)
        ], 1)
        pygame.draw.ellipse(surface, (52, 102, 52), (px2 - 6, ground - 18, 12, 6))
        for li, lc in enumerate([(222, 72, 92), (242, 192, 62), (182, 82, 202)]):
            pygame.draw.circle(surface, lc, (px2 - 4 + li * 4, ground - 20 - li % 2 * 3), 3)

    # ── Floating thread fibers (long curved strands) ──
    for i in range(12):
        t = ticks * 0.0011 + seed * 0.09 + i * 0.83
        life = (t * 18 + i * 7) % 55
        fade = int(max(0, 70 - life * 1.2))
        fx = x - 100 + int(math.sin(t * 0.9 + i) * 80)
        fy = (ground - 30) - int(life)
        curl = int(math.sin(t * 2.2 + i * 0.5) * 5)
        thread_col = [(210, 140, 170), (140, 180, 220), (200, 190, 130),
                      (170, 130, 210), (130, 210, 160), (220, 160, 100)][i % 6]
        ts = pygame.Surface((14, 4), pygame.SRCALPHA)
        pygame.draw.line(ts, (*thread_col, fade), (0, 2), (13, 2 + curl % 3), 1)
        surface.blit(ts, (fx, fy))

    # ── Needle glint sparkles (occasional flash on shelf tools) ──
    glint_phase = math.sin(ticks * 0.004 + seed * 0.3)
    if glint_phase > 0.7:
        for gx_off, gy_off in ((x + 29, stable.top - 7), (sc2x + 4, stable.top + 4),
                                (sc_x + 10, sc_y - 2)):
            intensity = int((glint_phase - 0.7) / 0.3 * 200)
            gs = pygame.Surface((8, 8), pygame.SRCALPHA)
            pygame.draw.line(gs, (255, 255, 255, intensity), (4, 0), (4, 7))
            pygame.draw.line(gs, (255, 255, 255, intensity // 2), (0, 4), (7, 4))
            surface.blit(gs, (gx_off - 4, gy_off - 4), special_flags=pygame.BLEND_RGBA_ADD)

    # ── Fabric bolt shimmer sweep ──
    shimmer_pos = (math.sin(ticks * 0.0007) * 0.5 + 0.5)
    for bi in range(6):
        bx2 = shelf.left + 8 + (bi % 3) * 38
        by2 = shelf.top + 6 + (bi // 3) * 24
        sweep_x = bx2 + int(shimmer_pos * 28)
        sh2 = pygame.Surface((5, 14), pygame.SRCALPHA)
        pygame.draw.rect(sh2, (255, 255, 255, 30), sh2.get_rect(), border_radius=1)
        surface.blit(sh2, (sweep_x, by2 + 1), special_flags=pygame.BLEND_RGBA_ADD)

    # ── Awning fringe tassels (gentle wave) ──
    for i in range(9):
        ax = x - 185 + i * 47
        sway2 = int(math.sin(ticks * 0.002 + i * 0.7) * 2)
        pygame.draw.line(surface, (180, 80, 110) if i % 2 == 0 else (110, 70, 140),
                         (ax, awning_y + 18), (ax + sway2, awning_y + 26), 2)
        pygame.draw.circle(surface, (220, 120, 150) if i % 2 == 0 else (150, 100, 180),
                           (ax + sway2, awning_y + 26), 2)


def _draw_leather_shop(surface: pygame.Surface, pos: Vector2, ticks: int, seed: int) -> None:  # noqa: C901
    x = int(pos.x)
    ground = int(pos.y)
    # ════════════════════════════════════════════════════
    # BUILDING
    # ════════════════════════════════════════════════════

    # ── Ground shadow ──
    gs = pygame.Surface((380, 24), pygame.SRCALPHA)
    pygame.draw.ellipse(gs, (0, 0, 0, 40), (0, 0, 380, 24))
    surface.blit(gs, (x - 190, ground - 12))

    # ── Rough stone foundation ──
    for row_f in range(2):
        off_f = 14 if row_f % 2 else 0
        for col_f in range(x - 196 + off_f, x + 196, 36):
            sh_f = 72 + (col_f * 5 + row_f * 11 + seed) % 20
            pygame.draw.rect(surface, (sh_f, int(sh_f * 0.88), int(sh_f * 0.76)),
                             (col_f, ground - 20 + row_f * 10, 34, 10))
            pygame.draw.rect(surface, (48, 40, 32), (col_f, ground - 20 + row_f * 10, 34, 10), 1)

    # ── Back wall: dark weathered planks with knots & nail heads ──
    wall = pygame.Rect(x - 196, ground - 196, 392, 176)
    pygame.draw.rect(surface, (52, 38, 24), wall)
    plank_heights = [11, 13, 10, 14, 12, 11, 13, 12, 11, 14, 10, 13, 12, 14]
    cy_plank = wall.top
    for pi_p, ph in enumerate(plank_heights):
        if cy_plank >= wall.bottom:
            break
        sh_p = 54 + (pi_p * 7 + seed) % 22
        pygame.draw.rect(surface, (sh_p, int(sh_p * 0.72), int(sh_p * 0.46)), (wall.left, cy_plank, wall.width, ph))
        pygame.draw.rect(surface, (36, 26, 14), (wall.left, cy_plank, wall.width, ph), 1)
        # grain
        for gi_p in range(wall.left + 20, wall.right - 10, 28):
            pygame.draw.line(surface, (sh_p - 10, int((sh_p - 10) * 0.68), int((sh_p - 10) * 0.42)),
                             (gi_p, cy_plank + 3), (gi_p + 18, cy_plank + ph - 3), 1)
        # nail heads
        for ni_p in range(wall.left + 12, wall.right - 8, 48):
            pygame.draw.circle(surface, (60, 55, 48), (ni_p + (pi_p * 7) % 20, cy_plank + ph // 2), 2)
            pygame.draw.circle(surface, (80, 72, 62), (ni_p + (pi_p * 7) % 20, cy_plank + ph // 2), 2, 1)
        # knot every few planks
        if (pi_p + seed) % 5 == 0:
            kx = wall.left + 40 + (pi_p * 37 + seed) % (wall.width - 80)
            pygame.draw.circle(surface, (38, 26, 14), (kx, cy_plank + ph // 2), 4)
            pygame.draw.circle(surface, (50, 36, 20), (kx, cy_plank + ph // 2), 4, 1)
        cy_plank += ph
    pygame.draw.rect(surface, (28, 18, 8), wall, 2)

    # ── Massive vertical support posts + iron band brackets ──
    for post_x2 in (wall.left + 5, wall.left + 100, wall.centerx, wall.right - 100, wall.right - 5):
        pygame.draw.rect(surface, (40, 28, 14), (post_x2 - 6, wall.top, 12, wall.height))
        pygame.draw.rect(surface, (58, 44, 24), (post_x2 - 6, wall.top, 12, wall.height), 1)
        pygame.draw.line(surface, (66, 50, 28), (post_x2, wall.top + 4), (post_x2, wall.bottom - 4), 1)
        # iron band brackets at top and bottom
        for band_y2 in (wall.top + 16, wall.bottom - 16):
            pygame.draw.rect(surface, (58, 58, 62), (post_x2 - 8, band_y2 - 4, 16, 8), border_radius=1)
            pygame.draw.rect(surface, (80, 80, 86), (post_x2 - 8, band_y2 - 4, 16, 8), 1, border_radius=1)
    # horizontal beams
    for beam_y3 in (wall.top, wall.top + 88, wall.bottom):
        pygame.draw.rect(surface, (40, 28, 14), (wall.left, beam_y3 - 6, wall.width, 12))
        pygame.draw.rect(surface, (58, 44, 24), (wall.left, beam_y3 - 6, wall.width, 12), 1)

    # ── Trophy mounts on upper wall (antlers + skulls) ──
    for tri, (tr_off, tr_col) in enumerate(((-128, (180, 150, 110)), (0, (160, 132, 94)), (128, (190, 158, 118)))):
        tr_x, tr_y = x + tr_off, ground - 168
        # skull
        pygame.draw.circle(surface, tr_col, (tr_x, tr_y), 8)
        pygame.draw.circle(surface, (max(0, tr_col[0] - 20), max(0, tr_col[1] - 16), max(0, tr_col[2] - 12)),
                           (tr_x, tr_y), 8, 1)
        pygame.draw.ellipse(surface, (max(0, tr_col[0] - 30), 0, 0), (tr_x - 4, tr_y - 1, 3, 4))
        pygame.draw.ellipse(surface, (max(0, tr_col[0] - 30), 0, 0), (tr_x + 1, tr_y - 1, 3, 4))
        # antler left
        pygame.draw.line(surface, tr_col, (tr_x - 4, tr_y - 6), (tr_x - 14, tr_y - 22), 2)
        pygame.draw.line(surface, tr_col, (tr_x - 9, tr_y - 14), (tr_x - 20, tr_y - 20), 1)
        pygame.draw.line(surface, tr_col, (tr_x - 14, tr_y - 22), (tr_x - 18, tr_y - 30), 1)
        # antler right
        pygame.draw.line(surface, tr_col, (tr_x + 4, tr_y - 6), (tr_x + 14, tr_y - 22), 2)
        pygame.draw.line(surface, tr_col, (tr_x + 9, tr_y - 14), (tr_x + 20, tr_y - 20), 1)
        pygame.draw.line(surface, tr_col, (tr_x + 14, tr_y - 22), (tr_x + 18, tr_y - 30), 1)
        # mounting plaque
        pygame.draw.rect(surface, (64, 46, 26), (tr_x - 10, tr_y + 6, 20, 8), border_radius=2)
        pygame.draw.rect(surface, (88, 66, 38), (tr_x - 10, tr_y + 6, 20, 8), 1, border_radius=2)

    # ── Iron-barred window (left, forge glow) ──
    lwin2 = pygame.Rect(x - 168, ground - 155, 70, 56)
    pygame.draw.rect(surface, (32, 22, 12), lwin2, border_radius=2)
    # pane with interior amber haze
    forge_pulse = int(60 + 40 * math.sin(ticks * 0.002 + seed))
    pygame.draw.rect(surface, (forge_pulse + 30, forge_pulse, 18), lwin2.inflate(-6, -6), border_radius=1)
    for bar_x3 in range(lwin2.left + 14, lwin2.right - 4, 14):
        pygame.draw.line(surface, (54, 58, 64), (bar_x3, lwin2.top + 3), (bar_x3, lwin2.bottom - 3), 2)
        pygame.draw.line(surface, (74, 78, 84), (bar_x3, lwin2.top + 3), (bar_x3 + 1, lwin2.bottom - 3), 1)
    pygame.draw.line(surface, (54, 58, 64), (lwin2.left + 3, lwin2.centery), (lwin2.right - 3, lwin2.centery), 2)
    pygame.draw.rect(surface, (46, 34, 18), lwin2, 2, border_radius=2)
    # forge glow radiating through
    for fgr2, fga2 in ((26, 40), (16, 70), (8, 110)):
        fg2 = pygame.Surface((fgr2 * 2, fgr2 * 2), pygame.SRCALPHA)
        pygame.draw.circle(fg2, (min(255, forge_pulse + 100), forge_pulse + 30, 20, fga2), (fgr2, fgr2), fgr2)
        surface.blit(fg2, (lwin2.centerx - fgr2, lwin2.centery - fgr2), special_flags=pygame.BLEND_RGBA_ADD)

    # ── Leather strip curtain door (center-right) ──
    curtain_x = x + 80
    for cs_i in range(7):
        cx_s = curtain_x - 18 + cs_i * 6
        csway = int(math.sin(ticks * 0.0008 + cs_i * 0.7 + seed) * 3)
        strip_col = [(110, 78, 42), (98, 68, 36), (122, 86, 46), (106, 74, 40)][cs_i % 4]
        pygame.draw.line(surface, strip_col, (cx_s, ground - 72), (cx_s + csway, ground - 12), 4)
        pygame.draw.line(surface, (max(0, strip_col[0] - 20), max(0, strip_col[1] - 16), max(0, strip_col[2] - 10)),
                         (cx_s, ground - 72), (cx_s + csway, ground - 12), 1)
        # stitch line
        for sy_s in range(ground - 68, ground - 14, 10):
            pygame.draw.circle(surface, (80, 56, 26), (cx_s + int(csway * (sy_s - (ground - 72)) / 60), sy_s), 1)
    # curtain rod
    pygame.draw.line(surface, (60, 50, 32), (curtain_x - 22, ground - 72), (curtain_x + 22, ground - 72), 3)
    pygame.draw.circle(surface, (80, 66, 42), (curtain_x - 22, ground - 72), 4)
    pygame.draw.circle(surface, (80, 66, 42), (curtain_x + 22, ground - 72), 4)

    # ── Hanging sign: stretched hide silhouette on ornate board ──
    hs_x2 = x - 155
    hs_y2 = ground - 150
    pygame.draw.line(surface, (62, 46, 24), (hs_x2, wall.top + 28), (hs_x2, hs_y2 - 28), 2)
    for chi2 in range(6):
        cy_s2 = hs_y2 - 28 + chi2 * 5
        pygame.draw.ellipse(surface, (72, 56, 30), (hs_x2 - 3, cy_s2, 6, 5), 1)
    sb2 = pygame.Rect(hs_x2 - 30, hs_y2 - 4, 60, 44)
    pygame.draw.rect(surface, (86, 58, 32), sb2, border_radius=5)
    pygame.draw.rect(surface, (126, 90, 54), sb2, 2, border_radius=5)
    pygame.draw.rect(surface, (72, 48, 26), sb2.inflate(-10, -10), border_radius=3)
    for sc_d in ((sb2.left + 5, sb2.top + 5), (sb2.right - 5, sb2.top + 5),
                 (sb2.left + 5, sb2.bottom - 5), (sb2.right - 5, sb2.bottom - 5)):
        pygame.draw.circle(surface, (140, 100, 56), sc_d, 3)
        pygame.draw.circle(surface, (100, 72, 38), sc_d, 3, 1)
    sc2x, sc2y = sb2.centerx, sb2.centery + 2
    hide_sign_pts = [(sc2x, sc2y - 15), (sc2x + 11, sc2y - 5), (sc2x + 9, sc2y + 8),
                     (sc2x, sc2y + 14), (sc2x - 9, sc2y + 8), (sc2x - 11, sc2y - 5)]
    pygame.draw.polygon(surface, (154, 108, 60), hide_sign_pts)
    pygame.draw.polygon(surface, (108, 76, 40), hide_sign_pts, 1)
    for sh_pt in hide_sign_pts[::2]:
        pygame.draw.circle(surface, (90, 62, 30), sh_pt, 2)

    # ── Roof: layered dark shingles with overhang ──
    roof_peak = ground - 264
    roof_base_y = ground - 194
    roof_l2, roof_r2 = x - 218, x + 218
    roof_pts2 = [(roof_l2, roof_base_y), (x, roof_peak), (roof_r2, roof_base_y)]
    pygame.draw.polygon(surface, (34, 26, 14), roof_pts2)
    for ry2 in range(roof_peak + 6, roof_base_y, 8):
        t2 = (ry2 - roof_peak) / max(1, roof_base_y - roof_peak)
        hw2 = int(218 * t2)
        sh2 = 32 + (ry2 * 5 + seed) % 18
        pygame.draw.line(surface, (sh2, int(sh2 * 0.72), int(sh2 * 0.44)), (x - hw2, ry2), (x + hw2, ry2), 3)
        for si3 in range(0, hw2 * 2, 16):
            sx3 = x - hw2 + si3 + (ry2 // 8 * 5 + seed) % 8
            pygame.draw.line(surface, (22, 14, 6), (sx3, ry2 - 1), (sx3, ry2 + 6), 1)
    pygame.draw.polygon(surface, (18, 10, 4), roof_pts2, 3)
    pygame.draw.line(surface, (54, 40, 22), (roof_l2, roof_base_y), (roof_r2, roof_base_y), 3)
    # iron ridge cap
    pygame.draw.rect(surface, (44, 42, 40), (x - 8, roof_peak - 4, 16, 14), border_radius=2)
    pygame.draw.rect(surface, (66, 64, 60), (x - 8, roof_peak - 4, 16, 14), 1, border_radius=2)
    # roof spike decoration
    for rsp_off in (-60, 0, 60):
        rs_x3 = x + rsp_off
        rs_frac = abs(rsp_off) / 60 if rsp_off != 0 else 0
        rs_y3 = roof_peak + int(rs_frac * (roof_base_y - roof_peak) * 0.22)
        pygame.draw.line(surface, (54, 50, 46), (rs_x3, rs_y3), (rs_x3, rs_y3 - 14), 2)
        pygame.draw.polygon(surface, (72, 66, 60), [(rs_x3 - 3, rs_y3 - 14), (rs_x3, rs_y3 - 22), (rs_x3 + 3, rs_y3 - 14)])

    # ── Stone chimney (left, wide) ──
    chim_rect = pygame.Rect(x - 106, roof_peak + 12, 34, 70)
    for cr_y2 in range(chim_rect.top, chim_rect.bottom, 12):
        off_c2 = 10 if ((cr_y2 - chim_rect.top) // 12) % 2 else 0
        for cr_x2 in range(chim_rect.left + off_c2, chim_rect.right - 2, 20):
            cw3 = min(18, chim_rect.right - cr_x2)
            ch4 = min(11, chim_rect.bottom - cr_y2)
            sh_c2 = 82 + (cr_y2 * 4 + cr_x2 * 3 + seed) % 18
            pygame.draw.rect(surface, (sh_c2, int(sh_c2 * 0.84), int(sh_c2 * 0.72)), (cr_x2, cr_y2, cw3, ch4))
            pygame.draw.rect(surface, (54, 44, 34), (cr_x2, cr_y2, cw3, ch4), 1)
    pygame.draw.rect(surface, (54, 44, 34), chim_rect, 2)
    pygame.draw.rect(surface, (100, 82, 62), (chim_rect.left - 5, chim_rect.top - 6, chim_rect.width + 10, 8), border_radius=1)

    # ── Hanging leather strips beam (like herbalist herbs but leather) ──
    strip_beam_y = ground - 178
    pygame.draw.line(surface, (52, 38, 20), (x - 10, strip_beam_y), (x + 176, strip_beam_y), 5)
    pygame.draw.line(surface, (70, 54, 30), (x - 10, strip_beam_y - 1), (x + 176, strip_beam_y - 1), 1)
    strip_cols = [(120, 84, 46), (140, 100, 54), (100, 68, 36), (158, 112, 62), (110, 76, 40), (130, 92, 50)]
    for li_s, lx_off in enumerate((6, 26, 46, 66, 86, 106, 126, 146, 166)):
        lx_s = x + lx_off
        sc_s = strip_cols[li_s % 6]
        # strip sway
        sway_s = int(math.sin(ticks * 0.0008 + li_s * 0.7 + seed) * 3)
        # hanging peg
        pygame.draw.circle(surface, (70, 54, 28), (lx_s, strip_beam_y), 2)
        # leather strip (varied widths)
        strip_w = 3 + (li_s * 3 + seed) % 3
        strip_len = 22 + (li_s * 5 + seed) % 16
        pygame.draw.line(surface, sc_s, (lx_s, strip_beam_y + 2), (lx_s + sway_s, strip_beam_y + strip_len), strip_w)
        pygame.draw.line(surface, (max(0, sc_s[0] - 22), max(0, sc_s[1] - 16), max(0, sc_s[2] - 10)),
                         (lx_s, strip_beam_y + 2), (lx_s + sway_s, strip_beam_y + strip_len), 1)
        # end tassel / fringe
        for fi4 in range(3):
            pygame.draw.line(surface, sc_s,
                             (lx_s + sway_s, strip_beam_y + strip_len),
                             (lx_s + sway_s + (fi4 - 1) * 3, strip_beam_y + strip_len + 6 + fi4 % 2), 1)

    # ── 4 large hide-stretching frames ──
    frame_configs = [
        (x - 168, ground - 60, 44, 90, (118, 82, 48)),
        (x - 108, ground - 50, 52, 78, (152, 110, 64)),
        (x - 42,  ground - 58, 48, 86, (106, 70, 38)),
        (x + 24,  ground - 46, 56, 72, (166, 122, 72)),
    ]
    for fx, fy, fw, fh, hc in frame_configs:
        # outer frame posts
        pygame.draw.rect(surface, (52, 36, 18), (fx - fw // 2 - 5, fy - fh - 4, 8, fh + 8), border_radius=1)
        pygame.draw.rect(surface, (52, 36, 18), (fx + fw // 2 - 3, fy - fh - 4, 8, fh + 8), border_radius=1)
        pygame.draw.rect(surface, (52, 36, 18), (fx - fw // 2 - 5, fy - fh - 4, fw + 10, 8), border_radius=1)
        pygame.draw.rect(surface, (52, 36, 18), (fx - fw // 2 - 5, fy - 4, fw + 10, 8), border_radius=1)
        for fp in ((fx - fw // 2 - 1, fy - fh), (fx + fw // 2 + 1, fy - fh),
                   (fx - fw // 2 - 1, fy), (fx + fw // 2 + 1, fy)):
            pygame.draw.circle(surface, (44, 30, 14), fp, 4)
            pygame.draw.circle(surface, (68, 52, 26), fp, 4, 1)
        # hide
        h_pts = [(fx - fw // 2 + 4, fy - fh + 6), (fx + fw // 2 - 4, fy - fh + 6),
                 (fx + fw // 2 + 3, fy - fh // 2), (fx + fw // 2 - 4, fy - 7),
                 (fx - fw // 2 + 4, fy - 7), (fx - fw // 2 - 3, fy - fh // 2)]
        pygame.draw.polygon(surface, hc, h_pts)
        # hide shading bands
        for htl2 in range(4):
            hy2 = fy - fh + 10 + htl2 * int((fh - 16) / 4)
            shd = (max(0, hc[0] - 18 - htl2 * 6), max(0, hc[1] - 14 - htl2 * 4), max(0, hc[2] - 8 - htl2 * 3))
            pygame.draw.line(surface, shd, (fx - fw // 2 + 6, hy2), (fx + fw // 2 - 6, hy2), 1)
        # cross crease mark
        pygame.draw.line(surface, (max(0, hc[0] - 30), max(0, hc[1] - 22), max(0, hc[2] - 14)),
                         (fx - fw // 2 + 8, fy - fh + 12), (fx + fw // 2 - 8, fy - 12), 1)
        pygame.draw.polygon(surface, (max(0, hc[0] - 26), max(0, hc[1] - 20), max(0, hc[2] - 12)), h_pts, 1)
        # lacing cord
        for lp in h_pts:
            pygame.draw.circle(surface, (64, 46, 22), lp, 3)
            pygame.draw.circle(surface, (84, 62, 34), lp, 3, 1)

    # ── Tanning barrel (large, fire underneath) ──
    vat_x2, vat_y2 = x + 108, ground
    for leg_v in (-18, 0, 18):
        pygame.draw.line(surface, (54, 40, 22), (vat_x2 + leg_v, vat_y2), (vat_x2, vat_y2 - 16), 3)
    pygame.draw.ellipse(surface, (58, 44, 26), (vat_x2 - 34, vat_y2 - 58, 68, 62))
    for band_v in (vat_y2 - 46, vat_y2 - 28, vat_y2 - 12):
        bw_v = int(62 * math.sqrt(max(0, 1 - ((band_v - (vat_y2 - 29)) / 32) ** 2)))
        pygame.draw.line(surface, (80, 72, 58), (vat_x2 - bw_v // 2, band_v), (vat_x2 + bw_v // 2, band_v), 2)
    pygame.draw.ellipse(surface, (76, 58, 34), (vat_x2 - 34, vat_y2 - 58, 68, 62), 2)
    pygame.draw.ellipse(surface, (68, 52, 30), (vat_x2 - 36, vat_y2 - 60, 72, 14))
    pygame.draw.ellipse(surface, (90, 70, 44), (vat_x2 - 36, vat_y2 - 60, 72, 14), 1)
    # tannin liquid
    tannin_t = ticks * 0.0018
    tan_r2 = int(88 + 22 * math.sin(tannin_t + seed))
    tan_g2 = int(56 + 16 * math.sin(tannin_t * 0.7 + seed))
    tan_b2 = int(26 + 10 * math.sin(tannin_t * 1.3 + seed))
    pygame.draw.ellipse(surface, (tan_r2, tan_g2, tan_b2), (vat_x2 - 32, vat_y2 - 58, 64, 14))
    # ripple
    rip_v = (ticks * 0.002 + seed) % 1.0
    rip_sv = pygame.Surface((int(12 + 20 * rip_v) * 2, int(5 + 8 * rip_v)), pygame.SRCALPHA)
    pygame.draw.ellipse(rip_sv, (min(255, tan_r2 + 30), min(255, tan_g2 + 20), min(255, tan_b2 + 14),
                                 int(50 * (1 - rip_v))), rip_sv.get_rect(), 1)
    surface.blit(rip_sv, (vat_x2 - (12 + int(20 * rip_v)), vat_y2 - 54))
    # hide submerged
    pygame.draw.ellipse(surface, (100, 72, 40), (vat_x2 - 22, vat_y2 - 52, 44, 12))
    pygame.draw.ellipse(surface, (78, 56, 28), (vat_x2 - 22, vat_y2 - 52, 44, 12), 1)
    # fire under barrel
    for fi5 in range(5):
        ft5 = ticks * 0.004 + seed * 0.14 + fi5 * 0.76
        fx5 = vat_x2 - 12 + fi5 * 6 + int(math.sin(ft5 * 2.4) * 3)
        fy5 = vat_y2 - 4 - int(abs(math.sin(ft5 * 1.7 + fi5)) * 10)
        pygame.draw.circle(surface, (min(255, 188 + fi5 * 12), max(0, 126 - fi5 * 18), 14), (int(fx5), int(fy5)), 2 + fi5 % 2)
        pygame.draw.circle(surface, (255, 220, 80), (int(fx5), int(fy5) - 1), 1)

    # ── Heavy work bench with detailed tools ──
    bench = pygame.Rect(x + 138, ground - 28, 50, 22)
    pygame.draw.rect(surface, (64, 48, 26), bench, border_radius=3)
    pygame.draw.rect(surface, (100, 76, 44), bench, 1, border_radius=3)
    pygame.draw.line(surface, (82, 62, 34), (bench.left + 3, bench.top + 4), (bench.right - 3, bench.top + 4), 1)
    for lx_b2 in (bench.left + 8, bench.right - 8):
        pygame.draw.rect(surface, (54, 40, 20), (lx_b2 - 3, bench.bottom, 6, 12), border_radius=1)
    # leather panel being worked
    pygame.draw.polygon(surface, (144, 104, 58),
                        [(bench.left + 4, bench.top - 3), (bench.right - 4, bench.top - 5),
                         (bench.right - 4, bench.top - 16), (bench.left + 4, bench.top - 14)])
    pygame.draw.polygon(surface, (110, 78, 40),
                        [(bench.left + 4, bench.top - 3), (bench.right - 4, bench.top - 5),
                         (bench.right - 4, bench.top - 16), (bench.left + 4, bench.top - 14)], 1)
    for sp_i in range(4):
        pygame.draw.circle(surface, (76, 52, 26), (bench.left + 8 + sp_i * 9, bench.top - 10), 1)
    # awl poking through leather
    pygame.draw.line(surface, (110, 102, 88), (bench.left + 30, bench.top - 22), (bench.left + 26, bench.top - 8), 2)
    pygame.draw.rect(surface, (76, 56, 32), (bench.left + 23, bench.top - 9, 8, 6), border_radius=1)

    # ── Grindstone wheel ──
    gs_x, gs_y = x + 154, ground - 14
    pygame.draw.circle(surface, (86, 82, 76), (gs_x, gs_y), 22)
    # spokes
    for sp_a in range(0, 360, 60):
        sp_rad = math.radians(sp_a + ticks * 0.04)
        pygame.draw.line(surface, (68, 64, 58), (gs_x, gs_y),
                         (gs_x + int(math.cos(sp_rad) * 18), gs_y + int(math.sin(sp_rad) * 18)), 2)
    pygame.draw.circle(surface, (100, 96, 88), (gs_x, gs_y), 22, 3)
    pygame.draw.circle(surface, (68, 64, 58), (gs_x, gs_y), 8)
    pygame.draw.circle(surface, (86, 82, 76), (gs_x, gs_y), 8, 1)
    # axle
    pygame.draw.line(surface, (54, 50, 44), (gs_x - 26, gs_y), (gs_x + 26, gs_y), 3)
    # ground contact highlight
    pygame.draw.ellipse(surface, (72, 68, 60), (gs_x - 22, gs_y + 16, 44, 8), 1)

    # ── Iron lanterns (3, along the front beam) ──
    lan_beam_y = ground - 178
    pygame.draw.line(surface, (44, 32, 16), (x - 196, lan_beam_y), (x - 10, lan_beam_y), 3)
    for lan_off in (-180, -130, -80):
        lan_x3, lan_y3 = x + lan_off, ground - 148
        # drop chain
        for ci3 in range(5):
            chain_y3 = lan_beam_y + ci3 * 6
            pygame.draw.ellipse(surface, (58, 56, 52), (lan_x3 - 3, chain_y3, 6, 5), 1)
        # cage
        pygame.draw.rect(surface, (38, 34, 28), (lan_x3 - 9, lan_y3 - 14, 18, 24), border_radius=2)
        pygame.draw.rect(surface, (66, 60, 50), (lan_x3 - 9, lan_y3 - 14, 18, 24), 1, border_radius=2)
        # top / bottom plates
        pygame.draw.rect(surface, (50, 46, 38), (lan_x3 - 11, lan_y3 - 16, 22, 4))
        pygame.draw.rect(surface, (50, 46, 38), (lan_x3 - 11, lan_y3 + 9, 22, 4))
        # cage bars
        for bar_i3 in range(4):
            pygame.draw.line(surface, (54, 50, 42), (lan_x3 - 7 + bar_i3 * 5, lan_y3 - 12),
                             (lan_x3 - 7 + bar_i3 * 5, lan_y3 + 8), 1)

    # ════════════════════════════════════════════════════
    # VFX & PARTICLES
    # ════════════════════════════════════════════════════

    # ── Chimney smoke (thick, sooty) ──
    for i in range(10):
        t = ticks * 0.0008 + seed * 0.06 + i * 0.9
        sx_c = chim_rect.centerx + math.sin(t * 1.2 + i) * (6 + i * 2)
        sy_c = chim_rect.top - 8 - (t * 14 + i * 8) % 48
        sz_c = 12 + i * 4
        sm_c = pygame.Surface((sz_c, sz_c), pygame.SRCALPHA)
        smoke_a = max(4, 48 - i * 5)
        scol2 = (74, 64, 52) if i % 2 == 0 else (92, 80, 66)
        pygame.draw.ellipse(sm_c, (*scol2, smoke_a), sm_c.get_rect())
        surface.blit(sm_c, (int(sx_c) - sz_c // 2, int(sy_c) - sz_c // 2))

    # ── Tanning barrel fire & steam ──
    for i in range(6):
        t = ticks * 0.001 + seed * 0.07 + i * 1.0
        sx_v2 = vat_x2 + int(math.sin(t * 1.3 + i) * 14)
        sy_v2 = vat_y2 - 62 - int((t * 12 + i * 6) % 32)
        sz_v2 = 9 + i * 3
        sv2 = pygame.Surface((sz_v2, sz_v2), pygame.SRCALPHA)
        av2 = max(4, 42 - i * 7)
        pygame.draw.ellipse(sv2, (106, 88, 66, av2), sv2.get_rect())
        surface.blit(sv2, (int(sx_v2) - sz_v2 // 2, int(sy_v2) - sz_v2 // 2))

    # ── Grindstone sparks (continuous low stream + periodic burst) ──
    spark_t = ticks * 0.002 + seed
    for si4 in range(16):
        sp_angle = math.radians(200 + si4 * 12 + math.sin(spark_t * 3 + si4) * 20)
        sp_dist = 20 + si4 * 1.5 + math.sin(spark_t * 2.1 + si4 * 0.8) * 6
        sp_x4 = gs_x + int(math.cos(sp_angle) * sp_dist)
        sp_y4 = gs_y + int(math.sin(sp_angle) * sp_dist * 0.5)
        sp_life = (spark_t * 8 + si4 * 0.63) % 1.0
        sp_fade = int(220 * math.sin(sp_life * math.pi))
        if sp_fade > 20:
            sp_col4 = (255, 200, 60) if si4 % 3 == 0 else (255, 155, 30) if si4 % 3 == 1 else (255, 240, 130)
            ss4 = pygame.Surface((4, 4), pygame.SRCALPHA)
            pygame.draw.circle(ss4, (*sp_col4, sp_fade), (2, 2), 1)
            surface.blit(ss4, (sp_x4 - 2, sp_y4 - 2), special_flags=pygame.BLEND_RGBA_ADD)


    # ── Amber dust motes in lantern beams ──
    for i in range(18):
        t = ticks * 0.0006 + seed * 0.14 + i * 0.38
        mote_life = (t * 4 + i * 1.5) % 1.0
        mote_x2 = x - 188 + int((i / 17) * 200) + int(math.sin(t * 1.4 + i) * 18)
        mote_y2 = ground - 24 - int(mote_life * 110)
        mote_b = int(140 * math.sin(mote_life * math.pi))
        if mote_b > 10:
            ms2 = pygame.Surface((4, 4), pygame.SRCALPHA)
            pygame.draw.circle(ms2, (216, 172, 106, mote_b), (2, 2), 1)
            surface.blit(ms2, (mote_x2 - 2, mote_y2 - 2), special_flags=pygame.BLEND_RGBA_ADD)

    # ── Forge glow pulse through window onto ground ──
    forge_cast = pygame.Surface((80, 18), pygame.SRCALPHA)
    fca = int(22 + 14 * math.sin(ticks * 0.003 + seed))
    pygame.draw.ellipse(forge_cast, (min(255, forge_pulse + 110), forge_pulse + 30, 20, fca), (0, 0, 80, 18))
    surface.blit(forge_cast, (lwin2.centerx - 40, ground - 10), special_flags=pygame.BLEND_RGBA_ADD)

    # ── Ember float from barrel fire ──
    for i in range(10):
        t = ticks * 0.0014 + seed * 0.12 + i * 0.63
        em_life = (t * 10 + i * 4) % 1.0
        em_x = vat_x2 - 20 + int((i / 9) * 40) + int(math.sin(t * 2 + i) * 12)
        em_y = vat_y2 - 60 - int(em_life * 50)
        em_bright = int(210 * math.sin(em_life * math.pi))
        if em_bright > 15:
            em_col = (255, 160, 40) if i % 2 == 0 else (255, 100, 20)
            em_s = pygame.Surface((4, 4), pygame.SRCALPHA)
            pygame.draw.circle(em_s, (*em_col, em_bright), (2, 2), 1)
            surface.blit(em_s, (em_x - 2, em_y - 2), special_flags=pygame.BLEND_RGBA_ADD)


def _draw_merchant_shop(surface: pygame.Surface, pos: Vector2, ticks: int, seed: int) -> None:  # noqa: C901
    x = int(pos.x)
    ground = int(pos.y)

    # ════════════════════════════════════════════════════
    # BUILDING
    # ════════════════════════════════════════════════════

    # ── Stone foundation ──
    foundation = pygame.Rect(x - 196, ground - 22, 392, 22)
    pygame.draw.rect(surface, (106, 94, 74), foundation)
    for fs in range(foundation.left, foundation.right - 4, 30):
        sh = 102 + (fs * 7 + seed) % 18
        pygame.draw.rect(surface, (sh, sh - 8, sh - 14), (fs, foundation.top + 2, 28, 9))
        pygame.draw.rect(surface, (78, 68, 52), (fs, foundation.top + 2, 28, 9), 1)
    pygame.draw.rect(surface, (78, 68, 52), foundation, 2)

    # ── Back wall — warm cream plaster, prosperous looking ──
    wall = pygame.Rect(x - 196, ground - 210, 392, 188)
    pygame.draw.rect(surface, (214, 196, 154), wall)
    for row_idx, row_y in enumerate((wall.top + 4, wall.top + 68, wall.top + 124)):
        for col_idx, col_x in enumerate((wall.left + 6, wall.left + 106, wall.centerx + 4, wall.right - 100)):
            ph = 42 if row_idx == 2 else 54
            ps = 218 + (col_x * 3 + row_y * 5 + seed) % 16
            panel = pygame.Rect(col_x + 2, row_y + 2, 88, ph)
            pygame.draw.rect(surface, (ps, ps - 14, ps - 28), panel)
            if (col_idx + row_idx + seed) % 3 == 0:
                pygame.draw.line(surface, (ps - 20, ps - 32, ps - 44),
                                 (panel.left + 8, panel.top + 6), (panel.left + 20, panel.top + 18), 1)
    for bby in (wall.top, wall.top + 66, wall.top + 122, wall.bottom):
        pygame.draw.rect(surface, (80, 54, 24), (wall.left, bby - 5, wall.width, 10))
        pygame.draw.rect(surface, (56, 34, 10), (wall.left, bby - 5, wall.width, 10), 1)
        pygame.draw.line(surface, (98, 70, 32), (wall.left + 2, bby), (wall.right - 2, bby), 1)
    for bbx in (wall.left, wall.left + 100, wall.centerx, wall.right - 100, wall.right):
        pygame.draw.rect(surface, (80, 54, 24), (bbx - 5, wall.top, 10, wall.height))
        pygame.draw.rect(surface, (56, 34, 10), (bbx - 5, wall.top, 10, wall.height), 1)
    pygame.draw.rect(surface, (56, 34, 10), wall, 2)

    # ── Decorative painted trade banner on wall (centre panel) ──
    banner = pygame.Rect(x - 44, wall.top + 72, 88, 34)
    pygame.draw.rect(surface, (148, 28, 28), banner, border_radius=3)
    pygame.draw.rect(surface, (200, 60, 40), banner, 1, border_radius=3)
    for bs in range(5):
        bsx = banner.left + 8 + bs * 16
        pygame.draw.line(surface, (220, 180, 60), (bsx, banner.top + 4), (bsx, banner.bottom - 4), 1)
    pygame.draw.circle(surface, (220, 196, 80), (banner.centerx, banner.centery), 9)
    pygame.draw.circle(surface, (180, 148, 40), (banner.centerx, banner.centery), 9, 1)
    pygame.draw.line(surface, (200, 170, 50), (banner.centerx - 6, banner.centery),
                     (banner.centerx + 6, banner.centery), 1)
    pygame.draw.line(surface, (200, 170, 50), (banner.centerx, banner.centery - 6),
                     (banner.centerx, banner.centery + 6), 1)

    # ── Chimney ──
    chim_rect = pygame.Rect(x - 58, wall.top - 60, 28, 64)
    for crow in range(7):
        cy = chim_rect.top + crow * 9
        off = 6 if crow % 2 else 0
        for ci in range(-1, 3):
            bx = chim_rect.left + ci * 14 + off
            bc = 156 + (crow * 11 + ci * 7 + seed) % 22
            pygame.draw.rect(surface, (bc, bc // 2 + 22, bc // 3 + 8), (bx, cy, 12, 8))
            pygame.draw.rect(surface, (96, 56, 28), (bx, cy, 12, 8), 1)
    pygame.draw.rect(surface, (96, 56, 28), chim_rect, 1)
    pygame.draw.rect(surface, (84, 60, 34), (chim_rect.left - 4, chim_rect.top, chim_rect.width + 8, 7))

    # ── Steep warm-toned roof ──
    roof_peak_x = x
    roof_peak_y = wall.top - 70
    roof_left = wall.left - 10
    roof_right = wall.right + 10
    pygame.draw.polygon(surface, (130, 68, 28),
                        [(roof_left, wall.top + 4), (roof_peak_x, roof_peak_y), (roof_right, wall.top + 4)])
    for row_r in range(10):
        row_frac = row_r / 9
        ry = int(roof_peak_y + row_frac * (wall.top + 4 - roof_peak_y))
        rw = int(row_frac * (roof_right - roof_left))
        rx = roof_peak_x - rw // 2
        td = 122 + row_r * 3
        for ti in range(rw // 14 + 1):
            tx = rx + ti * 14
            pygame.draw.rect(surface, (td, td - 30, td - 54), (tx, ry, 13, 8), border_radius=2)
            pygame.draw.rect(surface, (88, 40, 12), (tx, ry, 13, 8), 1, border_radius=2)
    pygame.draw.line(surface, (96, 46, 14), (roof_left, wall.top + 4), (roof_peak_x, roof_peak_y), 3)
    pygame.draw.line(surface, (96, 46, 14), (roof_peak_x, roof_peak_y), (roof_right, wall.top + 4), 3)
    pygame.draw.circle(surface, (110, 58, 22), (roof_peak_x, roof_peak_y), 5)
    pygame.draw.circle(surface, (80, 36, 8), (roof_peak_x, roof_peak_y), 5, 1)
    pygame.draw.line(surface, (78, 34, 8), (roof_left, wall.top + 5), (roof_right, wall.top + 5), 3)

    # ── Striped awning over front display area ──
    awn_left = wall.left + 4
    awn_right = wall.right - 4
    awn_top_y = ground - 118
    awn_bot_y = ground - 78
    awn_stripe_w = (awn_right - awn_left) // 14
    for si in range(14):
        sx = awn_left + si * awn_stripe_w
        stripe_col = (188, 28, 28) if si % 2 == 0 else (220, 190, 80)
        pts_awn = [(sx, awn_top_y), (sx + awn_stripe_w, awn_top_y),
                   (sx + awn_stripe_w + 6, awn_bot_y), (sx - 6, awn_bot_y)]
        pygame.draw.polygon(surface, stripe_col, pts_awn)
    # awning border/trim
    pygame.draw.line(surface, (140, 18, 18), (awn_left, awn_top_y), (awn_right, awn_top_y), 3)
    pygame.draw.line(surface, (160, 22, 22), (awn_left - 8, awn_bot_y), (awn_right + 8, awn_bot_y), 3)
    # scalloped lower edge
    for sc_i in range(18):
        sc_x = awn_left - 4 + sc_i * 22
        pygame.draw.arc(surface, (148, 18, 18),
                        (sc_x, awn_bot_y - 5, 22, 12), math.pi, 2 * math.pi, 2)
    # awning support rods
    for rod_x in (awn_left + 20, x, awn_right - 20):
        pygame.draw.line(surface, (100, 72, 36), (rod_x, awn_top_y), (rod_x, awn_bot_y), 2)

    # ── Central doorway ──
    door_rect = pygame.Rect(x - 26, ground - 110, 52, 88)
    pygame.draw.rect(surface, (68, 46, 22), door_rect)
    pygame.draw.ellipse(surface, (68, 46, 22), (door_rect.left, door_rect.top - 18, door_rect.width, 36))
    pygame.draw.ellipse(surface, (48, 28, 10), (door_rect.left, door_rect.top - 18, door_rect.width, 36), 2)
    pygame.draw.rect(surface, (108, 76, 36), door_rect, 2)
    # door knocker
    pygame.draw.circle(surface, (180, 154, 60), (door_rect.centerx, door_rect.top + 30), 5, 2)
    pygame.draw.circle(surface, (180, 154, 60), (door_rect.centerx, door_rect.top + 38), 3)

    # ── Left window — warm amber glow ──
    lwin = pygame.Rect(x - 178, ground - 172, 68, 54)
    pygame.draw.rect(surface, (44, 30, 14), lwin, border_radius=2)
    wpl = int(186 + 32 * math.sin(ticks * 0.0014 + seed))
    pygame.draw.rect(surface, (wpl, wpl - 36, wpl - 82),
                     (lwin.left + 3, lwin.top + 3, lwin.width - 6, lwin.height - 6))
    pygame.draw.line(surface, (64, 44, 18), (lwin.centerx, lwin.top), (lwin.centerx, lwin.bottom), 2)
    pygame.draw.line(surface, (64, 44, 18), (lwin.left, lwin.centery), (lwin.right, lwin.centery), 2)
    pygame.draw.rect(surface, (86, 60, 26), lwin, 2, border_radius=2)

    # ── Right window — wide display window ──
    rwin = pygame.Rect(x + 64, ground - 172, 108, 54)
    pygame.draw.rect(surface, (44, 30, 14), rwin, border_radius=2)
    wpr = int(192 + 28 * math.sin(ticks * 0.0011 + seed + 1.3))
    pygame.draw.rect(surface, (wpr, wpr - 38, wpr - 84),
                     (rwin.left + 3, rwin.top + 3, rwin.width - 6, rwin.height - 6))
    # shelf and goods silhouettes inside window
    pygame.draw.line(surface, (96, 66, 28), (rwin.left + 4, rwin.bottom - 18),
                     (rwin.right - 4, rwin.bottom - 18), 2)
    for gi in range(5):
        gx6 = rwin.left + 10 + gi * 18
        gc6 = [(200, 80, 40), (80, 140, 80), (180, 160, 40), (120, 80, 160), (60, 120, 180)][gi]
        pygame.draw.rect(surface, gc6, (gx6, rwin.bottom - 32, 12, 14), border_radius=2)
    pygame.draw.rect(surface, (86, 60, 26), rwin, 2, border_radius=2)

    # ── Hanging sign — coin and scale silhouette ──
    sign_arm_x = x + 196
    sign_arm_y = ground - 164
    pygame.draw.line(surface, (80, 56, 24), (wall.right, sign_arm_y), (sign_arm_x + 24, sign_arm_y), 3)
    pygame.draw.line(surface, (80, 56, 24), (sign_arm_x + 24, sign_arm_y), (sign_arm_x + 24, sign_arm_y + 14), 2)
    sboard = pygame.Rect(sign_arm_x - 20, sign_arm_y + 14, 56, 32)
    pygame.draw.rect(surface, (100, 68, 28), sboard, border_radius=4)
    pygame.draw.rect(surface, (150, 110, 50), sboard, 1, border_radius=4)
    # coin icon
    pygame.draw.circle(surface, (218, 186, 68), (sboard.left + 14, sboard.centery), 10)
    pygame.draw.circle(surface, (168, 134, 36), (sboard.left + 14, sboard.centery), 10, 1)
    pygame.draw.circle(surface, (200, 166, 54), (sboard.left + 14, sboard.centery), 6)
    # divider
    pygame.draw.line(surface, (130, 94, 36), (sboard.centerx, sboard.top + 4),
                     (sboard.centerx, sboard.bottom - 4), 1)
    # scale icon
    sc2_cx = sboard.right - 14
    pygame.draw.line(surface, (200, 172, 60), (sc2_cx, sboard.top + 4), (sc2_cx, sboard.bottom - 4), 1)
    pygame.draw.line(surface, (200, 172, 60), (sc2_cx - 8, sboard.top + 8), (sc2_cx + 8, sboard.top + 8), 1)
    pygame.draw.arc(surface, (200, 172, 60),
                    (sc2_cx - 10, sboard.top + 7, 8, 6), math.pi, 2 * math.pi, 1)
    pygame.draw.arc(surface, (200, 172, 60),
                    (sc2_cx + 2, sboard.top + 9, 8, 6), math.pi, 2 * math.pi, 1)
    for sx2, sy2 in ((sboard.left + 3, sboard.top + 3), (sboard.right - 5, sboard.top + 3),
                     (sboard.left + 3, sboard.bottom - 5), (sboard.right - 5, sboard.bottom - 5)):
        pygame.draw.circle(surface, (180, 148, 56), (sx2, sy2), 2)

    # ════════════════════════════════════════════════════
    # PROPS & FURNITURE
    # ════════════════════════════════════════════════════

    # ── Display table with varied goods ──
    dtable = pygame.Rect(x - 96, ground - 22, 192, 16)
    pygame.draw.rect(surface, (108, 76, 38), dtable, border_radius=3)
    pygame.draw.rect(surface, (148, 108, 56), dtable, 1, border_radius=3)
    pygame.draw.rect(surface, (88, 60, 26), (dtable.left + 6, dtable.bottom, dtable.width - 12, 4))
    # cloth drape on table
    cloth2 = pygame.Rect(dtable.left - 2, dtable.top - 2, dtable.width + 4, 6)
    pygame.draw.rect(surface, (168, 28, 28), cloth2)
    pygame.draw.rect(surface, (220, 188, 60), cloth2, 1)
    for stripe2 in range(cloth2.left + 4, cloth2.right - 2, 12):
        pygame.draw.line(surface, (220, 188, 60), (stripe2, cloth2.top), (stripe2, cloth2.bottom), 1)

    # goods on table: pottery, spice jars, cloth roll, coin pile, exotic fruit
    # pottery jug
    jug_x = x - 80
    pygame.draw.ellipse(surface, (160, 100, 50), (jug_x - 8, dtable.top - 20, 16, 16))
    pygame.draw.rect(surface, (148, 90, 42), (jug_x - 6, dtable.top - 12, 12, 10))
    pygame.draw.ellipse(surface, (160, 100, 50), (jug_x - 6, dtable.top - 14, 12, 6))
    pygame.draw.ellipse(surface, (120, 68, 28), (jug_x - 8, dtable.top - 20, 16, 16), 1)
    pygame.draw.line(surface, (120, 68, 28), (jug_x + 6, dtable.top - 15), (jug_x + 12, dtable.top - 10), 2)

    # spice jars (3 small)
    for sj_i in range(3):
        sj_x = x - 52 + sj_i * 16
        sj_col = [(180, 80, 30), (60, 140, 80), (160, 60, 130)][sj_i]
        pygame.draw.rect(surface, sj_col, (sj_x - 5, dtable.top - 16, 10, 14), border_radius=2)
        pygame.draw.rect(surface, (220, 210, 180), (sj_x - 4, dtable.top - 18, 8, 4), border_radius=1)
        pygame.draw.rect(surface, (sj_col[0] - 30, sj_col[1] - 20, sj_col[2] - 20),
                         (sj_x - 5, dtable.top - 16, 10, 14), 1, border_radius=2)

    # cloth bolt
    cb_x = x + 4
    pygame.draw.ellipse(surface, (60, 100, 160), (cb_x - 6, dtable.top - 14, 26, 12))
    pygame.draw.ellipse(surface, (40, 78, 138), (cb_x - 6, dtable.top - 14, 26, 12), 1)
    pygame.draw.line(surface, (50, 88, 148), (cb_x - 4, dtable.top - 8), (cb_x + 18, dtable.top - 8), 1)

    # coin pile
    cp_x = x + 40
    for ci_row in range(3):
        for ci_col in range(3 - ci_row):
            pygame.draw.circle(surface, (222, 190, 68),
                               (cp_x + ci_col * 7 + ci_row * 3, dtable.top - 6 - ci_row * 5), 4)
            pygame.draw.circle(surface, (168, 136, 36),
                               (cp_x + ci_col * 7 + ci_row * 3, dtable.top - 6 - ci_row * 5), 4, 1)

    # exotic round fruit
    for ef_i in range(4):
        ef_x = x + 62 + ef_i * 10
        ef_col = [(200, 60, 40), (240, 180, 30), (80, 170, 60), (180, 100, 200)][ef_i]
        pygame.draw.circle(surface, ef_col, (ef_x, dtable.top - 8), 5)
        pygame.draw.circle(surface, (ef_col[0] - 30, ef_col[1] - 20, ef_col[2] - 20),
                           (ef_x, dtable.top - 8), 5, 1)
        pygame.draw.line(surface, (60, 100, 40), (ef_x, dtable.top - 13), (ef_x + 2, dtable.top - 17), 1)

    # ── Hanging spice bags from beam above door ──
    spice_beam_y = ground - 124
    pygame.draw.line(surface, (90, 64, 30), (x - 58, spice_beam_y), (x + 58, spice_beam_y), 3)
    for sb_i in range(5):
        sb_x = x - 40 + sb_i * 20
        sb_sway = math.sin(ticks * 0.0007 + sb_i * 1.3 + seed) * 2
        pygame.draw.line(surface, (110, 82, 44), (sb_x, spice_beam_y), (sb_x + int(sb_sway), spice_beam_y + 8), 1)
        bag_col = [(180, 100, 40), (80, 140, 60), (160, 60, 40), (200, 160, 40), (100, 80, 160)][sb_i]
        pygame.draw.ellipse(surface, bag_col,
                            (sb_x + int(sb_sway) - 7, spice_beam_y + 8, 14, 16))
        pygame.draw.ellipse(surface, (bag_col[0] - 30, bag_col[1] - 20, bag_col[2] - 20),
                            (sb_x + int(sb_sway) - 7, spice_beam_y + 8, 14, 16), 1)
        pygame.draw.ellipse(surface, (220, 200, 170),
                            (sb_x + int(sb_sway) - 5, spice_beam_y + 8, 10, 5))

    # ── Crate stack (left side) ──
    for cr_i2, (cr_x3, cr_y3, cr_w3, cr_h3) in enumerate((
        (x - 162, ground - 28, 44, 28), (x - 158, ground - 54, 36, 26), (x - 154, ground - 76, 30, 22)
    )):
        cr_c2 = (88 + cr_i2 * 8, 66 + cr_i2 * 5, 38 + cr_i2 * 4)
        pygame.draw.rect(surface, cr_c2, (cr_x3, cr_y3, cr_w3, cr_h3), border_radius=2)
        pygame.draw.rect(surface, (60, 44, 22), (cr_x3, cr_y3, cr_w3, cr_h3), 1, border_radius=2)
        pygame.draw.line(surface, (60, 44, 22), (cr_x3, cr_y3), (cr_x3 + cr_w3, cr_y3 + cr_h3), 1)
        pygame.draw.line(surface, (60, 44, 22), (cr_x3 + cr_w3, cr_y3), (cr_x3, cr_y3 + cr_h3), 1)

    # ── Barrel cluster (right side) ──
    for bar_i3, (bar_x3, bar_h3) in enumerate(((x + 148, 34), (x + 166, 28), (x + 156, 52))):
        bt3 = ground - bar_h3
        bar_c3 = (96 + bar_i3 * 6, 72 + bar_i3 * 4, 40 + bar_i3 * 3)
        pygame.draw.ellipse(surface, bar_c3, (bar_x3 - 14, bt3 - 7, 28, 12))
        pygame.draw.rect(surface, bar_c3, (bar_x3 - 14, bt3 - 2, 28, bar_h3))
        pygame.draw.ellipse(surface, bar_c3, (bar_x3 - 14, ground - 12, 28, 12))
        for hoop3 in (bt3 + 4, bt3 + bar_h3 // 2):
            pygame.draw.ellipse(surface, (58, 40, 18), (bar_x3 - 15, hoop3, 30, 7), 2)
        pygame.draw.rect(surface, (66, 46, 20), (bar_x3 - 14, bt3 - 2, 28, bar_h3), 1)

    # ── Merchant's scale on small stand ──
    msc_x = x - 118
    msc_y = ground - 42
    pygame.draw.line(surface, (130, 100, 44), (msc_x, msc_y), (msc_x, msc_y - 36), 2)
    pygame.draw.line(surface, (140, 108, 48), (msc_x - 22, msc_y - 36), (msc_x + 22, msc_y - 36), 2)
    pygame.draw.circle(surface, (150, 116, 50), (msc_x, msc_y - 36), 4)
    sc_wobble = int(math.sin(ticks * 0.0012 + seed) * 3)
    pygame.draw.line(surface, (120, 92, 36), (msc_x - 22, msc_y - 36), (msc_x - 22, msc_y - 22 + sc_wobble), 1)
    pygame.draw.line(surface, (120, 92, 36), (msc_x + 22, msc_y - 36), (msc_x + 22, msc_y - 22 - sc_wobble), 1)
    pygame.draw.ellipse(surface, (190, 160, 60), (msc_x - 30, msc_y - 26 + sc_wobble, 16, 6))
    pygame.draw.ellipse(surface, (190, 160, 60), (msc_x + 14, msc_y - 26 - sc_wobble, 16, 6))
    pygame.draw.rect(surface, (100, 74, 30), (msc_x - 6, msc_y - 6, 12, 6))

    # ── Rolled-up map / scroll on wall ──
    scroll_x = x - 148
    scroll_y = ground - 148
    pygame.draw.rect(surface, (210, 188, 130), (scroll_x - 12, scroll_y - 20, 24, 28), border_radius=2)
    pygame.draw.ellipse(surface, (196, 172, 114), (scroll_x - 14, scroll_y - 22, 28, 10))
    pygame.draw.ellipse(surface, (196, 172, 114), (scroll_x - 14, scroll_y + 6, 28, 10))
    pygame.draw.rect(surface, (168, 140, 80), (scroll_x - 12, scroll_y - 20, 24, 28), 1, border_radius=2)
    for rl in range(4):
        pygame.draw.line(surface, (140, 110, 60),
                         (scroll_x - 8, scroll_y - 14 + rl * 6),
                         (scroll_x + 8, scroll_y - 14 + rl * 6), 1)

    # ── Ornate hanging lantern (left of door) ──
    ol_x = x - 44
    ol_y = ground - 138
    pygame.draw.line(surface, (80, 60, 28), (ol_x, ground - 160), (ol_x, ol_y - 8), 2)
    pygame.draw.ellipse(surface, (68, 52, 24), (ol_x - 5, ol_y - 10, 10, 6))
    pygame.draw.rect(surface, (50, 38, 16), (ol_x - 8, ol_y - 4, 16, 22), border_radius=3)
    pygame.draw.rect(surface, (84, 64, 28), (ol_x - 8, ol_y - 4, 16, 22), 1, border_radius=3)
    ol_flicker = int(200 + 38 * math.sin(ticks * 0.011 + seed))
    pygame.draw.rect(surface, (ol_flicker, int(ol_flicker * 0.72), 28),
                     (ol_x - 5, ol_y, 10, 14), border_radius=2)
    for olgr, olga in ((10, 28), (6, 46), (3, 68)):
        olgs = pygame.Surface((olgr * 2, olgr * 2), pygame.SRCALPHA)
        pygame.draw.circle(olgs, (ol_flicker, int(ol_flicker * 0.6), 20, olga), (olgr, olgr), olgr)
        surface.blit(olgs, (ol_x - olgr, ol_y + 7 - olgr), special_flags=pygame.BLEND_RGBA_ADD)

    # ════════════════════════════════════════════════════
    # VFX & PARTICLES
    # ════════════════════════════════════════════════════

    # ── Chimney smoke ──
    for i in range(10):
        t = ticks * 0.0007 + seed * 0.06 + i * 0.85
        sx_c = chim_rect.centerx + math.sin(t * 1.1 + i) * (5 + i * 2)
        sy_c = chim_rect.top - 6 - (t * 11 + i * 9) % 50
        sz_c = 10 + i * 4
        sa_c = max(0, int(82 - i * 6))
        sc_s2 = pygame.Surface((sz_c, sz_c), pygame.SRCALPHA)
        pygame.draw.ellipse(sc_s2, (186 + i * 3, 170 + i * 3, 148 + i * 2, sa_c), sc_s2.get_rect())
        surface.blit(sc_s2, (int(sx_c) - sz_c // 2, int(sy_c) - sz_c // 2))

    # ── Gold coin shimmer ──
    for i in range(8):
        t = ticks * 0.002 + seed * 0.14 + i * 0.5
        coin_life = (t * 5 + i) % 1.0
        cn_x = cp_x + (i % 3) * 7 + int(math.sin(t * 3 + i) * 2)
        cn_y = dtable.top - 6 - (i // 3) * 5
        cn_a = int(180 * math.sin(coin_life * math.pi))
        if cn_a > 30:
            cns = pygame.Surface((4, 4), pygame.SRCALPHA)
            pygame.draw.circle(cns, (255, 230, 100, cn_a), (2, 2), 2)
            surface.blit(cns, (cn_x - 2, cn_y - 2), special_flags=pygame.BLEND_RGBA_ADD)

    # ── Warm golden dust motes ──
    for i in range(16):
        t = ticks * 0.0005 + seed * 0.17 + i * 0.44
        dm_life = (t * 2.8 + i * 1.0) % 1.0
        dm_x = x - 180 + int((i / 15) * 360) + int(math.sin(t * 1.6 + i) * 14)
        dm_y = ground - 14 - int(dm_life * 100)
        dm_a = int(110 * math.sin(dm_life * math.pi))
        if dm_a > 10:
            dms2 = pygame.Surface((4, 4), pygame.SRCALPHA)
            pygame.draw.circle(dms2, (220, 190, 90, dm_a), (2, 2), 1)
            surface.blit(dms2, (dm_x - 2, dm_y - 2))

    # ── Spice bag colour wisps ──
    for sb_j in range(5):
        t2 = ticks * 0.0009 + seed * 0.1 + sb_j * 0.88
        sw_life = (t2 * 4 + sb_j * 0.6) % 1.0
        sw_x2 = x - 40 + sb_j * 20 + int(math.sin(t2 * 1.5 + sb_j) * 4)
        sw_y2 = spice_beam_y + 20 - int(sw_life * 28)
        sw_a2 = int(80 * math.sin(sw_life * math.pi))
        if sw_a2 > 8:
            swc2 = [(180, 100, 40), (80, 140, 60), (160, 60, 40), (200, 160, 40), (100, 80, 160)][sb_j]
            sws2 = pygame.Surface((5, 5), pygame.SRCALPHA)
            pygame.draw.circle(sws2, (*swc2, sw_a2), (2, 2), 2)
            surface.blit(sws2, (sw_x2 - 2, sw_y2 - 2))


def _draw_baker_shop(surface: pygame.Surface, pos: Vector2, ticks: int, seed: int) -> None:  # noqa: C901
    x = int(pos.x)
    ground = int(pos.y)

    # ════════════════════════════════════════════════════
    # BUILDING
    # ════════════════════════════════════════════════════

    # ── Stone foundation ──
    foundation = pygame.Rect(x - 196, ground - 22, 392, 22)
    pygame.draw.rect(surface, (104, 90, 70), foundation)
    for fs in range(foundation.left, foundation.right - 4, 30):
        sh = 100 + (fs * 7 + seed) % 20
        pygame.draw.rect(surface, (sh, sh - 8, sh - 14), (fs, foundation.top + 2, 28, 9))
        pygame.draw.rect(surface, (78, 66, 50), (fs, foundation.top + 2, 28, 9), 1)
    pygame.draw.rect(surface, (78, 66, 50), foundation, 2)

    # ── Back wall — warm cream plaster + dark timber frame ──
    wall = pygame.Rect(x - 196, ground - 210, 392, 188)
    pygame.draw.rect(surface, (218, 200, 158), wall)
    # plaster panels with warm tint variation
    for row_idx, row_y in enumerate((wall.top + 4, wall.top + 68, wall.top + 124)):
        for col_idx, col_x in enumerate((wall.left + 6, wall.left + 106, wall.centerx + 4, wall.right - 100)):
            ph = 42 if row_idx == 2 else 54
            panel_shade = 222 + (col_x * 3 + row_y * 5 + seed) % 16
            panel = pygame.Rect(col_x + 2, row_y + 2, 88, ph)
            pygame.draw.rect(surface, (panel_shade, panel_shade - 12, panel_shade - 26), panel)
            if (col_idx + row_idx + seed) % 3 == 0:
                pygame.draw.line(surface, (panel_shade - 18, panel_shade - 28, panel_shade - 38),
                                 (panel.left + 8, panel.top + 6), (panel.left + 20, panel.top + 18), 1)
    # timber frame beams
    for bby in (wall.top, wall.top + 66, wall.top + 122, wall.bottom):
        pygame.draw.rect(surface, (74, 50, 26), (wall.left, bby - 5, wall.width, 10))
        pygame.draw.rect(surface, (50, 32, 14), (wall.left, bby - 5, wall.width, 10), 1)
        pygame.draw.line(surface, (92, 66, 36), (wall.left + 2, bby), (wall.right - 2, bby), 1)
    for bbx in (wall.left, wall.left + 100, wall.centerx, wall.right - 100, wall.right):
        pygame.draw.rect(surface, (74, 50, 26), (bbx - 5, wall.top, 10, wall.height))
        pygame.draw.rect(surface, (50, 32, 14), (bbx - 5, wall.top, 10, wall.height), 1)
    pygame.draw.rect(surface, (50, 32, 14), wall, 2)

    # ── Brick chimney (left of centre) ──
    chim_rect = pygame.Rect(x - 60, wall.top - 68, 34, 72)
    for crow in range(8):
        cy = chim_rect.top + crow * 9
        offset = 8 if crow % 2 else 0
        for ci in range(-1, 3):
            bx = chim_rect.left + ci * 18 + offset
            bc = 154 + (crow * 13 + ci * 7 + seed) % 24
            pygame.draw.rect(surface, (bc, bc // 2 + 20, bc // 3), (bx, cy, 16, 8))
            pygame.draw.rect(surface, (90, 50, 30), (bx, cy, 16, 8), 1)
    pygame.draw.rect(surface, (90, 50, 30), chim_rect, 1)
    # chimney cap
    pygame.draw.rect(surface, (80, 56, 36), (chim_rect.left - 4, chim_rect.top, chim_rect.width + 8, 7))

    # ── Steep terracotta-tiled roof ──
    roof_peak_x = x
    roof_peak_y = wall.top - 70
    roof_left = wall.left - 10
    roof_right = wall.right + 10
    # main triangular fill
    pygame.draw.polygon(surface, (154, 82, 42),
                        [(roof_left, wall.top + 4), (roof_peak_x, roof_peak_y), (roof_right, wall.top + 4)])
    # tile rows
    for row_r in range(10):
        row_frac = row_r / 9
        ry = int(roof_peak_y + row_frac * (wall.top + 4 - roof_peak_y))
        rw = int(row_frac * (roof_right - roof_left))
        rx = roof_peak_x - rw // 2
        tile_col_r = (146 + row_r * 2, 74 + row_r, 36 + row_r)
        for ti in range(rw // 14 + 1):
            tx = rx + ti * 14
            pygame.draw.rect(surface, tile_col_r, (tx, ry, 13, 8), border_radius=2)
            pygame.draw.rect(surface, (100, 50, 22), (tx, ry, 13, 8), 1, border_radius=2)
    # ridge cap
    pygame.draw.line(surface, (120, 60, 28), (roof_left, wall.top + 4), (roof_peak_x, roof_peak_y), 3)
    pygame.draw.line(surface, (120, 60, 28), (roof_peak_x, roof_peak_y), (roof_right, wall.top + 4), 3)
    pygame.draw.circle(surface, (130, 68, 32), (roof_peak_x, roof_peak_y), 5)
    pygame.draw.circle(surface, (100, 48, 18), (roof_peak_x, roof_peak_y), 5, 1)
    # eave overhang shadow
    pygame.draw.line(surface, (60, 40, 18), (roof_left, wall.top + 5), (roof_right, wall.top + 5), 3)

    # ── Decorative wheat-sheaf carved panel above door ──
    wpanel = pygame.Rect(x - 32, wall.top + 70, 64, 24)
    pygame.draw.rect(surface, (200, 176, 120), wpanel, border_radius=3)
    pygame.draw.rect(surface, (120, 88, 40), wpanel, 1, border_radius=3)
    for wi in range(5):
        wx = wpanel.left + 8 + wi * 12
        pygame.draw.line(surface, (160, 120, 48), (wx, wpanel.bottom - 4), (wx - 2 + wi % 2 * 4, wpanel.top + 4), 1)
        pygame.draw.ellipse(surface, (210, 170, 70), (wx - 3, wpanel.top + 2, 6, 8))
        pygame.draw.ellipse(surface, (150, 110, 36), (wx - 3, wpanel.top + 2, 6, 8), 1)

    # ── Central arched doorway ──
    door_rect = pygame.Rect(x - 26, ground - 110, 52, 88)
    pygame.draw.rect(surface, (64, 42, 22), door_rect, border_radius=0)
    pygame.draw.ellipse(surface, (64, 42, 22), (door_rect.left, door_rect.top - 18, door_rect.width, 36))
    pygame.draw.ellipse(surface, (50, 32, 14), (door_rect.left, door_rect.top - 18, door_rect.width, 36), 2)
    pygame.draw.rect(surface, (100, 70, 36), door_rect, 2)
    # hanging curtain strips
    for ds in range(5):
        strip_x = door_rect.left + 5 + ds * 9
        sway = int(math.sin(ticks * 0.0008 + ds * 0.9 + seed) * 3)
        strip_col = (218 + ds * 4, 202 + ds * 2, 164) if ds % 2 == 0 else (196, 178, 142)
        pygame.draw.line(surface, strip_col,
                         (strip_x, door_rect.top + 4),
                         (strip_x + sway, door_rect.bottom - 6), 3)
        pygame.draw.ellipse(surface, (strip_col[0] - 20, strip_col[1] - 20, strip_col[2] - 20),
                            (strip_x + sway - 2, door_rect.bottom - 10, 5, 6))

    # ── Left window — 4-pane with flower box ──
    lwin = pygame.Rect(x - 174, ground - 176, 66, 54)
    pygame.draw.rect(surface, (42, 28, 14), lwin, border_radius=2)
    win_pulse_l = int(180 + 32 * math.sin(ticks * 0.0015 + seed))
    for pr, pc in (((0, 0, 33, 25), (win_pulse_l, win_pulse_l - 40, win_pulse_l - 90)),
                   ((33, 0, 33, 25), (win_pulse_l - 8, win_pulse_l - 46, win_pulse_l - 94)),
                   ((0, 25, 33, 29), (win_pulse_l - 4, win_pulse_l - 42, win_pulse_l - 92)),
                   ((33, 25, 33, 29), (win_pulse_l - 12, win_pulse_l - 48, win_pulse_l - 96))):
        pygame.draw.rect(surface, pc, (lwin.left + pr[0] + 2, lwin.top + pr[1] + 2, pr[2] - 4, pr[3] - 4))
    pygame.draw.line(surface, (60, 40, 18), (lwin.centerx, lwin.top), (lwin.centerx, lwin.bottom), 2)
    pygame.draw.line(surface, (60, 40, 18), (lwin.left, lwin.top + 27), (lwin.right, lwin.top + 27), 2)
    pygame.draw.rect(surface, (80, 54, 28), lwin, 2, border_radius=2)
    # flower box
    fbox_l = pygame.Rect(lwin.left - 3, lwin.bottom, lwin.width + 6, 10)
    pygame.draw.rect(surface, (96, 62, 32), fbox_l, border_radius=2)
    pygame.draw.rect(surface, (64, 40, 18), fbox_l, 1, border_radius=2)
    for fi in range(5):
        fx = fbox_l.left + 6 + fi * 12
        sway_f = math.sin(ticks * 0.001 + fi * 1.4 + seed) * 2.5
        stem_top = int(fbox_l.top - 8 + sway_f)
        pygame.draw.line(surface, (58, 110, 44), (fx, fbox_l.top), (fx + int(sway_f), stem_top), 1)
        petal_col = [(220, 80, 60), (240, 180, 50), (200, 60, 120), (230, 120, 40), (180, 210, 60)][fi]
        angle_off = ticks * 0.003 + fi * 1.1
        for p in range(5):
            pa = angle_off + p * 1.257
            px2 = fx + int(math.cos(pa) * 4)
            py2 = stem_top - 1 + int(math.sin(pa) * 3)
            pygame.draw.circle(surface, petal_col, (px2, py2), 2)
        pygame.draw.circle(surface, (255, 220, 60), (fx, stem_top), 2)

    # ── Right window — wide display with bread inside ──
    rwin = pygame.Rect(x + 60, ground - 176, 110, 60)
    pygame.draw.rect(surface, (42, 28, 14), rwin, border_radius=2)
    win_pulse_r = int(190 + 28 * math.sin(ticks * 0.0012 + seed + 1.2))
    pygame.draw.rect(surface, (win_pulse_r, win_pulse_r - 38, win_pulse_r - 86),
                     (rwin.left + 3, rwin.top + 3, rwin.width - 6, rwin.height - 6))
    pygame.draw.rect(surface, (80, 54, 28), rwin, 2, border_radius=2)
    # bread shelf inside window
    shelf_y = rwin.bottom - 20
    pygame.draw.line(surface, (90, 60, 28), (rwin.left + 4, shelf_y), (rwin.right - 4, shelf_y), 2)
    for bi2 in range(4):
        bx2 = rwin.left + 10 + bi2 * 24
        br_col = (180 + bi2 * 8, 110 + bi2 * 5, 50 + bi2 * 4)
        pygame.draw.ellipse(surface, br_col, (bx2, shelf_y - 12, 18, 10))
        pygame.draw.ellipse(surface, (br_col[0] - 30, br_col[1] - 20, br_col[2] - 10), (bx2, shelf_y - 12, 18, 10), 1)
        pygame.draw.line(surface, (br_col[0] - 40, br_col[1] - 28, 20), (bx2 + 5, shelf_y - 9), (bx2 + 13, shelf_y - 9), 1)
    # flower box under right window
    fbox_r = pygame.Rect(rwin.left - 3, rwin.bottom, rwin.width + 6, 10)
    pygame.draw.rect(surface, (96, 62, 32), fbox_r, border_radius=2)
    pygame.draw.rect(surface, (64, 40, 18), fbox_r, 1, border_radius=2)
    for fi2 in range(7):
        fx2 = fbox_r.left + 8 + fi2 * 14
        sway_f2 = math.sin(ticks * 0.001 + fi2 * 1.1 + seed + 2.0) * 2.5
        stem_top2 = int(fbox_r.top - 8 + sway_f2)
        pygame.draw.line(surface, (58, 110, 44), (fx2, fbox_r.top), (fx2 + int(sway_f2), stem_top2), 1)
        petal_col2 = [(220, 80, 60), (240, 180, 50), (200, 60, 120), (230, 120, 40), (180, 210, 60), (255, 160, 80), (200, 230, 80)][fi2]
        angle_off2 = ticks * 0.003 + fi2 * 0.9
        for p2 in range(5):
            pa2 = angle_off2 + p2 * 1.257
            px3 = fx2 + int(math.cos(pa2) * 4)
            py3 = stem_top2 - 1 + int(math.sin(pa2) * 3)
            pygame.draw.circle(surface, petal_col2, (px3, py3), 2)
        pygame.draw.circle(surface, (255, 220, 60), (fx2, stem_top2), 2)

    # ── Hanging sign — wrought iron arm + bread loaf silhouette ──
    sign_arm_x = x + 196
    sign_arm_y = ground - 168
    pygame.draw.line(surface, (54, 44, 32), (wall.right, sign_arm_y), (sign_arm_x + 24, sign_arm_y), 3)
    pygame.draw.line(surface, (54, 44, 32), (sign_arm_x + 24, sign_arm_y), (sign_arm_x + 24, sign_arm_y + 14), 2)
    sboard = pygame.Rect(sign_arm_x - 18, sign_arm_y + 14, 54, 28)
    pygame.draw.rect(surface, (96, 64, 30), sboard, border_radius=4)
    pygame.draw.rect(surface, (140, 100, 46), sboard, 1, border_radius=4)
    pygame.draw.ellipse(surface, (210, 148, 60), (sboard.left + 4, sboard.top + 5, 28, 16))
    pygame.draw.ellipse(surface, (160, 100, 30), (sboard.left + 4, sboard.top + 5, 28, 16), 1)
    pygame.draw.line(surface, (180, 120, 40), (sboard.left + 8, sboard.top + 9), (sboard.left + 28, sboard.top + 9), 1)
    pygame.draw.line(surface, (180, 120, 40), (sboard.left + 10, sboard.top + 13), (sboard.left + 26, sboard.top + 13), 1)
    for sx2, sy2 in ((sboard.left + 3, sboard.top + 3), (sboard.right - 5, sboard.top + 3),
                     (sboard.left + 3, sboard.bottom - 5), (sboard.right - 5, sboard.bottom - 5)):
        pygame.draw.circle(surface, (180, 140, 60), (sx2, sy2), 2)

    # ════════════════════════════════════════════════════
    # PROPS & FURNITURE
    # ════════════════════════════════════════════════════

    # ── Large domed bread oven (left exterior, iconic piece) ──
    ov_x = x - 136
    ov_base_y = ground - 18
    pygame.draw.rect(surface, (100, 84, 62), (ov_x - 44, ov_base_y - 14, 88, 14), border_radius=2)
    pygame.draw.rect(surface, (72, 58, 40), (ov_x - 44, ov_base_y - 14, 88, 14), 1, border_radius=2)
    ov_dome = pygame.Rect(ov_x - 40, ov_base_y - 60, 80, 50)
    pygame.draw.ellipse(surface, (136, 94, 54), ov_dome)
    for db_row in range(4):
        db_y = ov_dome.top + 8 + db_row * 11
        db_offset = 10 if db_row % 2 else 0
        for db_col in range(-1, 5):
            db_x = ov_dome.left + db_col * 18 + db_offset
            if ov_dome.left <= db_x <= ov_dome.right - 10:
                bc = 128 + db_row * 6 + db_col * 3
                pygame.draw.rect(surface, (bc, bc // 2 + 14, bc // 3 + 4), (db_x, db_y, 16, 9))
                pygame.draw.rect(surface, (82, 54, 28), (db_x, db_y, 16, 9), 1)
    pygame.draw.ellipse(surface, (82, 54, 28), ov_dome, 2)
    pygame.draw.ellipse(surface, (110, 74, 40), (ov_x - 8, ov_dome.top - 4, 16, 10))
    pygame.draw.ellipse(surface, (70, 46, 22), (ov_x - 8, ov_dome.top - 4, 16, 10), 1)
    ov_pulse = int(200 + 44 * math.sin(ticks * 0.006 + seed))
    ov_mouth = pygame.Rect(ov_x - 22, ov_base_y - 40, 44, 30)
    pygame.draw.rect(surface, (30, 18, 10), ov_mouth)
    pygame.draw.ellipse(surface, (100, 68, 38), (ov_mouth.left, ov_mouth.top - 10, ov_mouth.width, 20))
    pygame.draw.ellipse(surface, (70, 46, 22), (ov_mouth.left, ov_mouth.top - 10, ov_mouth.width, 20), 2)
    for or2, oa2 in ((18, 60), (12, 90), (7, 120), (3, 160)):
        og2 = pygame.Surface((or2 * 2, or2 * 2), pygame.SRCALPHA)
        pygame.draw.circle(og2, (ov_pulse, ov_pulse // 2, 20, oa2), (or2, or2), or2)
        surface.blit(og2, (ov_x - or2, ov_base_y - 26 - or2), special_flags=pygame.BLEND_RGBA_ADD)
    pygame.draw.line(surface, (130, 90, 44), (ov_x + 34, ground - 6), (ov_x + 52, ov_dome.top + 18), 3)
    pygame.draw.ellipse(surface, (148, 106, 54), (ov_x + 46, ov_dome.top + 10, 22, 14))
    pygame.draw.ellipse(surface, (100, 68, 30), (ov_x + 46, ov_dome.top + 10, 22, 14), 1)

    # ── Flour barrels (two, by oven) ──
    for bar_i, bar_x in enumerate((ov_x + 46, ov_x + 66)):
        bar_top = ground - 38 - bar_i * 4
        pygame.draw.ellipse(surface, (210, 198, 172), (bar_x - 12, bar_top - 8, 24, 10))
        pygame.draw.rect(surface, (196, 182, 154), (bar_x - 12, bar_top - 4, 24, 26))
        pygame.draw.ellipse(surface, (196, 182, 154), (bar_x - 12, bar_top + 18, 24, 10))
        for hoop_y in (bar_top + 2, bar_top + 14):
            pygame.draw.ellipse(surface, (100, 76, 44), (bar_x - 13, hoop_y, 26, 7), 2)
        pygame.draw.rect(surface, (160, 146, 118), (bar_x - 12, bar_top - 4, 24, 26), 1)

    # ── Wheat sheaves leaning on wall (right side) ──
    ws_x = x + 168
    for wsi in range(3):
        lean = (wsi - 1) * 6
        stalk_col = (194 + wsi * 6, 162 + wsi * 4, 60)
        pygame.draw.line(surface, stalk_col, (ws_x + wsi * 10, ground - 6), (ws_x + wsi * 10 + lean, ground - 52), 2)
        for gj in range(4):
            gx3 = ws_x + wsi * 10 + lean + int(math.sin(gj * 0.8) * 4)
            gy3 = ground - 52 - gj * 8
            pygame.draw.ellipse(surface, (216, 180, 68), (gx3 - 3, gy3 - 5, 6, 9))
            pygame.draw.ellipse(surface, (160, 126, 40), (gx3 - 3, gy3 - 5, 6, 9), 1)
    pygame.draw.line(surface, (140, 100, 36), (ws_x - 2, ground - 28), (ws_x + 22, ground - 28), 2)

    # ── Outdoor display table with breads, pies, rolls ──
    dtable = pygame.Rect(x - 60, ground - 22, 130, 16)
    pygame.draw.rect(surface, (102, 72, 40), dtable, border_radius=3)
    pygame.draw.rect(surface, (140, 102, 56), dtable, 1, border_radius=3)
    pygame.draw.rect(surface, (82, 58, 30), (dtable.left + 4, dtable.bottom, dtable.width - 8, 4))
    cloth = pygame.Rect(dtable.left - 2, dtable.top - 3, dtable.width + 4, 6)
    pygame.draw.rect(surface, (220, 210, 180), cloth, border_radius=2)
    for stripe_x in range(cloth.left + 6, cloth.right - 2, 10):
        pygame.draw.line(surface, (180, 160, 120), (stripe_x, cloth.top), (stripe_x, cloth.bottom), 1)

    # bread loaves on table
    for i_b, (boff, bw, bh, btype) in enumerate((
        (-52, 26, 14, 0), (-22, 20, 12, 1), (4, 28, 14, 0), (36, 18, 10, 2), (58, 22, 12, 1)
    )):
        bx3 = x + boff
        by3 = dtable.top - bh + 2
        bread_base = (168 + i_b * 8, 104 + i_b * 4, 42 + i_b * 3)
        if btype == 0:
            pygame.draw.ellipse(surface, bread_base, (bx3, by3, bw, bh))
            pygame.draw.ellipse(surface, (bread_base[0] - 30, bread_base[1] - 22, 18), (bx3, by3, bw, bh), 1)
            pygame.draw.line(surface, (bread_base[0] - 40, bread_base[1] - 30, 14),
                             (bx3 + 4, by3 + bh // 2 - 1), (bx3 + bw - 4, by3 + bh // 2 - 1), 1)
        elif btype == 1:
            pygame.draw.rect(surface, bread_base, (bx3, by3 + 3, bw, bh - 6), border_radius=4)
            pygame.draw.rect(surface, (bread_base[0] - 28, bread_base[1] - 20, 16), (bx3, by3 + 3, bw, bh - 6), 1, border_radius=4)
            for sc in range(3):
                pygame.draw.line(surface, (bread_base[0] - 38, bread_base[1] - 28, 12),
                                 (bx3 + 4 + sc * 5, by3 + 3), (bx3 + 3 + sc * 5, by3 + bh - 4), 1)
        else:
            for ri in range(3):
                rx3 = bx3 + ri * 6
                ry3 = by3 + (1 if ri % 2 else 0)
                pygame.draw.circle(surface, bread_base, (rx3, ry3 + bh // 2), bh // 2 - 1)
                pygame.draw.circle(surface, (bread_base[0] - 26, bread_base[1] - 18, 14),
                                   (rx3, ry3 + bh // 2), bh // 2 - 1, 1)

    # ── Pie on display table ──
    pie_x = x + 8
    pie_y = dtable.top - 8
    pygame.draw.ellipse(surface, (190, 134, 56), (pie_x - 14, pie_y, 28, 10))
    pygame.draw.ellipse(surface, (140, 86, 30), (pie_x - 14, pie_y, 28, 10), 1)
    pygame.draw.ellipse(surface, (200, 148, 66), (pie_x - 14, pie_y - 4, 28, 8))
    pygame.draw.ellipse(surface, (148, 96, 34), (pie_x - 14, pie_y - 4, 28, 8), 1)
    for lx4 in range(-3, 4, 2):
        pygame.draw.line(surface, (180, 120, 42), (pie_x + lx4, pie_y - 6), (pie_x + lx4, pie_y - 1), 1)
    for ly4 in (-5, -3):
        pygame.draw.line(surface, (180, 120, 42), (pie_x - 10, pie_y + ly4), (pie_x + 10, pie_y + ly4), 1)

    # ── Cooling rack (near door, right of oven) ──
    rack_x = x - 56
    rack_y = ground - 44
    pygame.draw.rect(surface, (90, 66, 36), (rack_x - 28, rack_y, 56, 6), border_radius=2)
    pygame.draw.rect(surface, (90, 66, 36), (rack_x - 28, rack_y + 20, 56, 6), border_radius=2)
    for wire_i in range(6):
        pygame.draw.line(surface, (110, 82, 46), (rack_x - 24 + wire_i * 10, rack_y + 2),
                         (rack_x - 24 + wire_i * 10, rack_y + 24), 1)
    pygame.draw.line(surface, (80, 56, 28), (rack_x - 22, rack_y + 26), (rack_x - 22, ground - 4), 2)
    pygame.draw.line(surface, (80, 56, 28), (rack_x + 22, rack_y + 26), (rack_x + 22, ground - 4), 2)
    for ci5 in range(3):
        cx5 = rack_x - 18 + ci5 * 18
        bread_c = (172 + ci5 * 6, 108 + ci5 * 4, 44 + ci5 * 3)
        pygame.draw.ellipse(surface, bread_c, (cx5, rack_y - 10, 16, 9))
        pygame.draw.ellipse(surface, (bread_c[0] - 28, bread_c[1] - 20, 16), (cx5, rack_y - 10, 16, 9), 1)

    # ════════════════════════════════════════════════════
    # VFX & PARTICLES
    # ════════════════════════════════════════════════════

    # ── Chimney smoke (warm, billowing) ──
    for i in range(12):
        t = ticks * 0.0007 + seed * 0.07 + i * 0.8
        sx_c = chim_rect.centerx + math.sin(t * 1.1 + i) * (5 + i * 2)
        sy_c = chim_rect.top - 6 - (t * 12 + i * 9) % 54
        sz_c = 10 + i * 4
        sa_c = max(0, int(90 - i * 6))
        smoke_r = min(255, 180 + i * 5)
        smoke_g = min(255, 140 + i * 4)
        sc_s = pygame.Surface((sz_c, sz_c), pygame.SRCALPHA)
        pygame.draw.ellipse(sc_s, (smoke_r, smoke_g, 90, sa_c), sc_s.get_rect())
        surface.blit(sc_s, (int(sx_c) - sz_c // 2, int(sy_c) - sz_c // 2))

    # ── Steam wisps from cooling loaves ──
    for i in range(6):
        t = ticks * 0.0009 + seed * 0.11 + i * 1.1
        st_life = (t * 5 + i * 0.7) % 1.0
        st_x = rack_x - 14 + i * 10 + int(math.sin(t * 2.1 + i) * 4)
        st_y = rack_y - 12 - int(st_life * 22)
        st_a = int(100 * math.sin(st_life * math.pi))
        if st_a > 8:
            st_s = pygame.Surface((6, 6), pygame.SRCALPHA)
            pygame.draw.ellipse(st_s, (230, 220, 210, st_a), (0, 0, 6, 6))
            surface.blit(st_s, (st_x - 3, st_y - 3))

    # ── Oven mouth ember glow (tight) ──
    for or3, oa3 in ((10, 36), (6, 56), (3, 80)):
        og3 = pygame.Surface((or3 * 2, or3 * 2), pygame.SRCALPHA)
        pygame.draw.circle(og3, (ov_pulse, ov_pulse // 3, 10, oa3), (or3, or3), or3)
        surface.blit(og3, (ov_x - or3, ov_base_y - 26 - or3), special_flags=pygame.BLEND_RGBA_ADD)

    # ── Flour dust motes ──
    for i in range(16):
        t = ticks * 0.0005 + seed * 0.18 + i * 0.42
        mote_life = (t * 3 + i * 1.3) % 1.0
        mote_x = x - 170 + int((i / 15) * 340) + int(math.sin(t * 1.6 + i) * 14)
        mote_y = ground - 14 - int(mote_life * 90)
        mote_a = int(110 * math.sin(mote_life * math.pi))
        if mote_a > 10:
            ms3 = pygame.Surface((4, 4), pygame.SRCALPHA)
            pygame.draw.circle(ms3, (240, 234, 220, mote_a), (2, 2), 1)
            surface.blit(ms3, (mote_x - 2, mote_y - 2))


def _draw_guard_shop(surface: pygame.Surface, pos: Vector2, ticks: int, seed: int) -> None:
    x = int(pos.x)
    ground = int(pos.y)
    rack = pygame.Rect(x - 60, ground - 60, 50, 46)
    pygame.draw.rect(surface, (50, 60, 74), rack, border_radius=4)
    pygame.draw.rect(surface, (110, 130, 160), rack, 1, border_radius=4)
    _draw_sword_icon(surface, rack.left + 16, rack.bottom - 6, 0.9)
    _draw_shield_icon(surface, rack.left + 34, rack.bottom - 6, 0.8)
    shield = pygame.Rect(x + 10, ground - 28, 40, 28)
    pygame.draw.rect(surface, (70, 90, 120), shield, border_radius=6)
    pygame.draw.rect(surface, (130, 160, 190), shield, 1, border_radius=6)


def _draw_herbalist_shop(surface: pygame.Surface, pos: Vector2, ticks: int, seed: int) -> None:  # noqa: C901
    x = int(pos.x)
    ground = int(pos.y)
    # ════════════════════════════════════════════════════
    # BUILDING
    # ════════════════════════════════════════════════════

    # ── Stone foundation ──
    foundation = pygame.Rect(x - 196, ground - 22, 392, 22)
    pygame.draw.rect(surface, (90, 80, 68), foundation)
    for fs in range(foundation.left, foundation.right - 4, 32):
        sh = 84 + (fs * 5 + seed) % 16
        pygame.draw.rect(surface, (sh, sh - 6, sh - 12), (fs, foundation.top + 2, 30, 9))
        pygame.draw.rect(surface, (70, 62, 52), (fs, foundation.top + 2, 30, 9), 1)
    pygame.draw.rect(surface, (70, 62, 52), foundation, 2)

    # ── Back wall: aged plaster + heavy timber frame ──
    wall = pygame.Rect(x - 196, ground - 192, 392, 170)
    pygame.draw.rect(surface, (190, 178, 152), wall)
    # plaster panels with subtle colour variation
    for row_idx, row_start in enumerate((wall.top + 4, wall.top + 70, wall.top + 118)):
        for col_idx, col_start in enumerate((wall.left + 4, wall.left + 102, wall.centerx + 4, wall.right - 98)):
            panel = pygame.Rect(col_start + 2, row_start + 2, 88, 42 if row_idx == 2 else 58)
            shade = 196 + (col_start * 3 + row_start * 7 + seed) % 18
            pygame.draw.rect(surface, (shade, shade - 10, shade - 18), panel)
            # aged cracks / texture
            if (col_idx + row_idx + seed) % 3 == 0:
                pygame.draw.line(surface, (shade - 16, shade - 24, shade - 30),
                                 (panel.left + 10, panel.top + 8), (panel.left + 22, panel.top + 20), 1)
    # heavy timber beams
    for bby in (wall.top, wall.top + 68, wall.top + 116, wall.bottom):
        pygame.draw.rect(surface, (76, 56, 32), (wall.left, bby - 5, wall.width, 10))
        pygame.draw.rect(surface, (52, 36, 18), (wall.left, bby - 5, wall.width, 10), 1)
        pygame.draw.line(surface, (90, 68, 40), (wall.left + 2, bby), (wall.right - 2, bby), 1)
    for bbx in (wall.left, wall.left + 98, wall.centerx, wall.right - 98, wall.right):
        pygame.draw.rect(surface, (76, 56, 32), (bbx - 5, wall.top, 10, wall.height))
        pygame.draw.rect(surface, (52, 36, 18), (bbx - 5, wall.top, 10, wall.height), 1)
    pygame.draw.rect(surface, (52, 36, 18), wall, 2)

    # ── Thick ivy colony — left two thirds of wall ──
    ivy_global_sway = math.sin(ticks * 0.0007 + seed) * 2.5
    for vi in range(32):
        vt = vi / 31
        vine_y = wall.bottom - int(vt * wall.height * 1.02)
        vx = int(wall.left + 8 + (vi % 4) * 22 + math.sin(vt * 5.5 + (vi % 4) * 1.1 + seed * 0.3) * 14
                 + ivy_global_sway * (0.5 + vi % 3 * 0.3))
        pygame.draw.circle(surface, (44, 80, 28), (vx, vine_y), 1)
        if vi % 2 == 0:
            ld = 1 if (vi // 2 + seed) % 2 else -1
            lw = 4 + vi % 4
            leaf_col = [(54, 106, 38), (66, 122, 44), (46, 92, 32), (74, 134, 50)][vi % 4]
            pygame.draw.ellipse(surface, leaf_col, (vx + ld * 2 - lw // 2, vine_y - 3, lw + 4, 5))
            # leaf highlight
            pygame.draw.line(surface, (min(255, leaf_col[0] + 20), min(255, leaf_col[1] + 20), leaf_col[2]),
                             (vx + ld * 2, vine_y - 1), (vx + ld * 2 + ld * 3, vine_y - 3), 1)

    # ── Left window (4-pane) with deep flower box ──
    lwin = pygame.Rect(x - 168, ground - 158, 74, 60)
    pygame.draw.rect(surface, (100, 78, 48), lwin, border_radius=3)
    pygame.draw.rect(surface, (168, 218, 235), lwin.inflate(-6, -6), border_radius=2)
    # pane cross
    pygame.draw.line(surface, (84, 64, 36), (lwin.centerx, lwin.top + 2), (lwin.centerx, lwin.bottom - 2), 2)
    pygame.draw.line(surface, (84, 64, 36), (lwin.left + 2, lwin.centery), (lwin.right - 2, lwin.centery), 2)
    pygame.draw.rect(surface, (84, 64, 36), lwin, 2, border_radius=3)
    # warm amber interior glow
    lw_glow = int(70 + 34 * math.sin(ticks * 0.0018 + seed + 0.5))
    for wgr, wga in ((24, 22), (14, 40), (8, 62)):
        wg = pygame.Surface((wgr * 2, wgr * 2), pygame.SRCALPHA)
        pygame.draw.circle(wg, (lw_glow + 50, lw_glow + 10, 18, wga), (wgr, wgr), wgr)
        surface.blit(wg, (lwin.centerx - wgr, lwin.centery - wgr), special_flags=pygame.BLEND_RGBA_ADD)
    # deep flower box
    fb_l = pygame.Rect(lwin.left - 4, lwin.bottom, lwin.width + 8, 13)
    pygame.draw.rect(surface, (72, 50, 26), fb_l, border_radius=2)
    pygame.draw.rect(surface, (102, 74, 44), fb_l, 1, border_radius=2)
    pygame.draw.rect(surface, (54, 38, 18), (fb_l.left + 2, fb_l.top + 3, fb_l.width - 4, 6))
    flower_set_l = [(218, 72, 88), (238, 172, 36), (168, 72, 218), (76, 196, 96), (218, 108, 52), (96, 172, 238)]
    for fi, fx in enumerate(range(fb_l.left + 7, fb_l.right - 5, 11)):
        fc = flower_set_l[fi % 6]
        fsway = int(math.sin(ticks * 0.0011 + fi * 1.1 + seed) * 2)
        pygame.draw.line(surface, (56, 104, 36), (fx, fb_l.top + 2), (fx + fsway, fb_l.top - 9), 1)
        # 5-petal flower
        for petal in range(5):
            pa = math.radians(petal * 72 + ticks * 0.02 * (1 if fi % 2 else -1))
            px_f = fx + fsway + int(math.cos(pa) * 3)
            py_f = fb_l.top - 9 + int(math.sin(pa) * 3)
            pygame.draw.circle(surface, fc, (px_f, py_f), 2)
        pygame.draw.circle(surface, (255, 240, 160), (fx + fsway, fb_l.top - 9), 1)

    # ── Main window (center, arched top) with flower box ──
    mwin_r = pygame.Rect(x - 74, ground - 162, 96, 76)
    pygame.draw.rect(surface, (100, 78, 48), mwin_r, border_radius=3)
    pygame.draw.rect(surface, (148, 204, 226), mwin_r.inflate(-6, -6), border_radius=2)
    # arch on top
    arch_top = [(mwin_r.left, mwin_r.top), (mwin_r.centerx, mwin_r.top - 22), (mwin_r.right, mwin_r.top)]
    pygame.draw.polygon(surface, (148, 204, 226), arch_top)
    pygame.draw.polygon(surface, (84, 64, 36), arch_top, 2)
    pygame.draw.line(surface, (84, 64, 36), (mwin_r.centerx, mwin_r.top + 2), (mwin_r.centerx, mwin_r.bottom - 2), 2)
    pygame.draw.line(surface, (84, 64, 36), (mwin_r.left + 2, mwin_r.centery), (mwin_r.right - 2, mwin_r.centery), 2)
    pygame.draw.rect(surface, (84, 64, 36), mwin_r, 2, border_radius=3)
    # warm amber interior glow
    win_warm = int(82 + 42 * math.sin(ticks * 0.002 + seed))
    for wgr2, wga2 in ((30, 20), (20, 36), (11, 56)):
        wgs2 = pygame.Surface((wgr2 * 2, wgr2 * 2), pygame.SRCALPHA)
        pygame.draw.circle(wgs2, (win_warm + 50, win_warm + 12, 22, wga2), (wgr2, wgr2), wgr2)
        surface.blit(wgs2, (mwin_r.centerx - wgr2, mwin_r.centery - wgr2), special_flags=pygame.BLEND_RGBA_ADD)
    # flower box
    fb_m = pygame.Rect(mwin_r.left - 4, mwin_r.bottom, mwin_r.width + 8, 13)
    pygame.draw.rect(surface, (72, 50, 26), fb_m, border_radius=2)
    pygame.draw.rect(surface, (102, 74, 44), fb_m, 1, border_radius=2)
    pygame.draw.rect(surface, (54, 38, 18), (fb_m.left + 2, fb_m.top + 3, fb_m.width - 4, 6))
    flower_set_m = [(196, 92, 198), (236, 194, 54), (96, 196, 76), (196, 76, 76), (96, 174, 238), (220, 130, 58)]
    for fi2, fx2 in enumerate(range(fb_m.left + 7, fb_m.right - 5, 10)):
        fc2 = flower_set_m[fi2 % 6]
        fsway2 = int(math.sin(ticks * 0.001 + fi2 * 0.85 + seed * 0.7) * 2)
        pygame.draw.line(surface, (56, 104, 36), (fx2, fb_m.top + 2), (fx2 + fsway2, fb_m.top - 9), 1)
        for petal2 in range(5):
            pa2 = math.radians(petal2 * 72 + ticks * 0.018 * (1 if fi2 % 2 else -1) + fi2 * 22)
            px_f2 = fx2 + fsway2 + int(math.cos(pa2) * 3)
            py_f2 = fb_m.top - 9 + int(math.sin(pa2) * 3)
            pygame.draw.circle(surface, fc2, (px_f2, py_f2), 2)
        pygame.draw.circle(surface, (255, 240, 160), (fx2 + fsway2, fb_m.top - 9), 1)

    # ── Hanging sign: mortar & pestle on chain ──
    hs_x = x + 164
    hs_y = ground - 152
    pygame.draw.line(surface, (100, 78, 48), (hs_x, wall.top + 40), (hs_x, hs_y - 34), 2)
    for chi in range(6):
        cy_s = hs_y - 30 + chi * 5
        pygame.draw.ellipse(surface, (100, 78, 48), (hs_x - 3, cy_s, 6, 5), 1)
    sign_b = pygame.Rect(hs_x - 28, hs_y - 4, 56, 42)
    pygame.draw.rect(surface, (148, 118, 70), sign_b, border_radius=5)
    pygame.draw.rect(surface, (186, 152, 96), sign_b, 1, border_radius=5)
    pygame.draw.rect(surface, (118, 94, 54), sign_b.inflate(-8, -8), border_radius=3)
    for sdx2, sdy2 in ((sign_b.left + 5, sign_b.top + 5), (sign_b.right - 5, sign_b.top + 5),
                       (sign_b.left + 5, sign_b.bottom - 5), (sign_b.right - 5, sign_b.bottom - 5)):
        pygame.draw.circle(surface, (186, 152, 96), (sdx2, sdy2), 2)
    # mortar bowl icon
    scx2, scy2 = sign_b.centerx, sign_b.centery + 3
    pygame.draw.ellipse(surface, (80, 160, 80), (scx2 - 12, scy2 - 6, 24, 16))
    pygame.draw.ellipse(surface, (54, 130, 54), (scx2 - 12, scy2 - 6, 24, 16), 1)
    pygame.draw.ellipse(surface, (60, 140, 60), (scx2 - 8, scy2 - 2, 16, 8))
    pygame.draw.line(surface, (100, 180, 100), (scx2 - 2, scy2 - 8), (scx2 + 8, scy2 - 18), 2)
    # sign glow
    sg_mortar = pygame.Surface((14, 12), pygame.SRCALPHA)
    sg_a = int(40 + 24 * math.sin(ticks * 0.004 + seed))
    pygame.draw.ellipse(sg_mortar, (80, 200, 80, sg_a), (0, 0, 14, 12))
    surface.blit(sg_mortar, (scx2 - 7, scy2 - 4), special_flags=pygame.BLEND_RGBA_ADD)

    # ── Thatched roof — layered with overhang ──
    roof_peak = ground - 268
    roof_base_y = ground - 190
    roof_l, roof_r = x - 218, x + 218
    # base fill
    roof_pts = [(roof_l, roof_base_y), (x, roof_peak), (roof_r, roof_base_y)]
    pygame.draw.polygon(surface, (138, 114, 52), roof_pts)
    # thatch rows — alternating light/dark bundles
    for ry in range(roof_peak + 6, roof_base_y, 6):
        t_frac = (ry - roof_peak) / max(1, roof_base_y - roof_peak)
        half_w = int(218 * t_frac)
        shade = 122 + (ry * 5 + seed) % 24
        # main row stroke
        pygame.draw.line(surface, (shade, int(shade * 0.82), int(shade * 0.36)),
                         (x - half_w, ry), (x + half_w, ry), 2)
        # individual thatch strands
        for ti in range(0, half_w * 2, 10):
            tx = x - half_w + ti
            tlen = 3 + (ti * 7 + ry * 3 + seed) % 5
            tcol_r = shade - 18
            pygame.draw.line(surface, (tcol_r, int(tcol_r * 0.76), int(tcol_r * 0.32)),
                             (tx, ry), (tx + 2, ry + tlen), 1)
    pygame.draw.polygon(surface, (96, 76, 30), roof_pts, 3)
    pygame.draw.line(surface, (108, 86, 36), (roof_l, roof_base_y), (roof_r, roof_base_y), 3)
    # ridge cap: thick bundle tied with cord
    pygame.draw.rect(surface, (102, 84, 38), (x - 22, roof_peak - 4, 44, 12), border_radius=3)
    for ri2 in range(-18, 20, 5):
        pygame.draw.line(surface, (86, 68, 28), (x + ri2, roof_peak - 4), (x + ri2, roof_peak + 7), 2)
    pygame.draw.line(surface, (64, 48, 20), (x - 22, roof_peak + 2), (x + 22, roof_peak + 2), 2)
    # decorative roof herbs hanging from eaves
    for eh_off in (-180, -130, -80, -30, 30, 80, 130, 180):
        eh_x = x + eh_off
        eh_t = (roof_base_y - roof_peak) / max(1, roof_base_y - roof_peak)
        eh_y = roof_base_y
        eh_sway = int(math.sin(ticks * 0.0008 + eh_off * 0.08 + seed) * 2)
        eh_col = [(60, 110, 38), (80, 130, 44), (50, 100, 34), (70, 120, 40)][abs(eh_off) % 4]
        pygame.draw.line(surface, eh_col, (eh_x, eh_y), (eh_x + eh_sway, eh_y + 14), 1)
        for el in range(3):
            pygame.draw.line(surface, eh_col, (eh_x + eh_sway, eh_y + 14),
                             (eh_x + eh_sway + (el - 1) * 5, eh_y + 22), 1)

    # ── Left chimney (warm brick) ──
    chim_rect = pygame.Rect(x - 110, roof_peak + 16, 28, 62)
    for cr_y in range(chim_rect.top, chim_rect.bottom, 10):
        off3 = 8 if ((cr_y - chim_rect.top) // 10) % 2 else 0
        for cr_x in range(chim_rect.left + off3, chim_rect.right - 2, 16):
            cw = min(14, chim_rect.right - cr_x)
            ch2 = min(9, chim_rect.bottom - cr_y)
            shade_c = 148 + (cr_y * 5 + cr_x * 3 + seed) % 18
            pygame.draw.rect(surface, (shade_c, int(shade_c * 0.6), int(shade_c * 0.42)), (cr_x, cr_y, cw, ch2))
            pygame.draw.rect(surface, (108, 74, 52), (cr_x, cr_y, cw, ch2), 1)
    pygame.draw.rect(surface, (108, 74, 52), chim_rect, 2)
    pygame.draw.rect(surface, (168, 128, 84), (chim_rect.left - 5, chim_rect.top - 6, chim_rect.width + 10, 8),
                     border_radius=2)

    # ── Ceiling herb drying rack (heavy timber, full width) ──
    beam_y = ground - 180
    pygame.draw.line(surface, (78, 58, 32), (x - 178, beam_y), (x + 70, beam_y), 5)
    pygame.draw.line(surface, (98, 76, 44), (x - 178, beam_y - 1), (x + 70, beam_y - 1), 1)
    # secondary parallel beam
    beam_y2 = ground - 168
    pygame.draw.line(surface, (70, 52, 28), (x - 140, beam_y2), (x + 40, beam_y2), 3)
    # herb bundles — 10 varied bundles with individual sway
    bundle_offsets = (-162, -138, -114, -90, -66, -42, -18, 6, 30, 54)
    for hi, hx_off in enumerate(bundle_offsets):
        hx = x + hx_off
        sway = int(math.sin(ticks * 0.0009 + hx_off * 0.14 + seed) * 3)
        # hook + string
        pygame.draw.circle(surface, (90, 70, 40), (hx, beam_y), 2)
        pygame.draw.line(surface, (110, 88, 52), (hx, beam_y + 3), (hx + sway, beam_y + 18), 1)
        # knot wrap
        pygame.draw.line(surface, (80, 60, 34), (hx + sway - 4, beam_y + 18), (hx + sway + 4, beam_y + 18), 2)
        btype = (hi + seed) % 4
        if btype == 0:  # dense leafy bundle
            hcol = [(52, 112, 38), (64, 132, 46), (44, 96, 32)][hi % 3]
            for li in range(5):
                lx_h = hx + sway - 5 + li * 2
                sl = int(math.sin(ticks * 0.001 + li * 0.8 + hx_off) * 2)
                pygame.draw.line(surface, hcol, (lx_h, beam_y + 18), (lx_h + (li - 2) * 4 + sl, beam_y + 32), 1)
                # small leaf nubs
                pygame.draw.circle(surface, (min(255, hcol[0] + 16), min(255, hcol[1] + 16), hcol[2]),
                                   (lx_h + (li - 2) * 4 + sl, beam_y + 32), 2)
        elif btype == 1:  # flower bundle
            fstem_col = (56, 100, 36)
            for li in range(4):
                lx_h = hx + sway - 4 + li * 3
                fl_y = beam_y + 28 + (li % 2) * 4
                pygame.draw.line(surface, fstem_col, (lx_h, beam_y + 18), (lx_h, fl_y), 1)
                fcol_b = [(210, 90, 60), (228, 168, 38), (176, 78, 168), (80, 200, 90)][li % 4]
                pygame.draw.circle(surface, fcol_b, (lx_h, fl_y), 3)
                pygame.draw.circle(surface, (255, 240, 160), (lx_h, fl_y), 1)
        elif btype == 2:  # root / dried bundle
            pygame.draw.ellipse(surface, (108, 76, 44), (hx + sway - 6, beam_y + 18, 12, 16))
            pygame.draw.ellipse(surface, (84, 58, 30), (hx + sway - 6, beam_y + 18, 12, 16), 1)
            for rt in range(3):
                pygame.draw.line(surface, (78, 54, 28),
                                 (hx + sway - 3 + rt * 3, beam_y + 33),
                                 (hx + sway - 5 + rt * 4, beam_y + 40), 1)
        else:  # lavender / purple flower spray
            for li in range(5):
                lx_h = hx + sway - 4 + li * 2
                lg = beam_y + 20 + li % 2
                pygame.draw.line(surface, (70, 90, 50), (lx_h, beam_y + 18), (lx_h + (li - 2), lg + 12), 1)
                pygame.draw.circle(surface, (160, 80, 180), (lx_h + (li - 2), lg + 12), 2)

    # ── Reagent shelves (2 rows, green/yellow herbal potions) ──
    for row, shelf_y in enumerate((ground - 162, ground - 125)):
        shelf_r = pygame.Rect(x - 54, shelf_y, 126, 10)
        pygame.draw.rect(surface, (92, 68, 38), shelf_r, border_radius=2)
        pygame.draw.rect(surface, (130, 100, 60), shelf_r, 1, border_radius=2)
        pygame.draw.line(surface, (110, 84, 50), (shelf_r.left + 2, shelf_r.top + 2), (shelf_r.right - 2, shelf_r.top + 2), 1)
        herb_cols = [(76, 196, 96), (152, 218, 56), (96, 176, 76), (198, 198, 54),
                     (76, 158, 118), (138, 218, 76)]
        for pi in range(6):
            pc = herb_cols[(pi + row * 2) % 6]
            _draw_potion_icon(surface, shelf_r.left + 10 + pi * 19, shelf_r.bottom, pc)
            ppulse = int(20 + 16 * math.sin(ticks * 0.004 + pi * 0.95 + row * 1.4))
            pg_s = pygame.Surface((10, 10), pygame.SRCALPHA)
            pygame.draw.circle(pg_s, (*pc, ppulse), (5, 5), 4)
            surface.blit(pg_s, (shelf_r.left + 5 + pi * 19, shelf_r.bottom - 10),
                         special_flags=pygame.BLEND_RGBA_ADD)

    # ── Front display table ──
    table = pygame.Rect(x - 158, ground - 26, 210, 20)
    pygame.draw.rect(surface, (92, 70, 40), table, border_radius=3)
    pygame.draw.rect(surface, (138, 108, 66), table, 1, border_radius=3)
    pygame.draw.line(surface, (116, 90, 52), (table.left + 3, table.top + 3), (table.right - 3, table.top + 3), 1)
    for lx_t in (table.left + 10, table.left + 72, table.centerx + 20, table.right - 10):
        pygame.draw.rect(surface, (76, 56, 30), (lx_t - 3, table.bottom, 6, 12), border_radius=1)

    # wicker baskets (3 types)
    for bi, bx_off in enumerate((-136, -108, -78)):
        bx_t = x + bx_off
        bcol = [(144, 110, 58), (162, 124, 68), (134, 102, 52)][bi]
        pygame.draw.ellipse(surface, bcol, (bx_t - 13, table.top - 12, 26, 14))
        pygame.draw.rect(surface, bcol, (bx_t - 11, table.top - 8, 22, 9))
        pygame.draw.ellipse(surface, (min(255, bcol[0] + 24), min(255, bcol[1] + 18), bcol[2]),
                            (bx_t - 13, table.top - 12, 26, 14), 1)
        # basket weave lines
        for bwl in range(3):
            pygame.draw.line(surface, (min(255, bcol[0] - 20), min(255, bcol[1] - 16), bcol[2] - 10),
                             (bx_t - 10, table.top - 7 + bwl * 3), (bx_t + 10, table.top - 7 + bwl * 3), 1)
        ccol = [(76, 156, 48), (198, 158, 36), (178, 78, 38)][bi]
        pygame.draw.ellipse(surface, ccol, (bx_t - 9, table.top - 10, 18, 8))

    # potted plants on table (3 varied)
    plant_types = [
        [(50, 140, 38), (70, 162, 48), (60, 132, 44)],   # leafy
        [(180, 60, 90), (200, 80, 110)],                  # flowering (rose-type)
        [(40, 100, 200), (60, 120, 220)],                 # blue flower
    ]
    for pi_t, px_off in enumerate((-42, -18, 8)):
        pot_x = x + px_off
        # terracotta pot
        pygame.draw.polygon(surface, (176, 96, 54),
                            [(pot_x - 8, table.top - 2), (pot_x + 8, table.top - 2),
                             (pot_x + 6, table.top - 16), (pot_x - 6, table.top - 16)])
        pygame.draw.polygon(surface, (144, 76, 38),
                            [(pot_x - 8, table.top - 2), (pot_x + 8, table.top - 2),
                             (pot_x + 6, table.top - 16), (pot_x - 6, table.top - 16)], 1)
        pygame.draw.line(surface, (196, 116, 74), (pot_x - 8, table.top - 6), (pot_x + 8, table.top - 6), 1)
        pygame.draw.rect(surface, (192, 112, 68), (pot_x - 9, table.top - 3, 18, 3), border_radius=1)
        # soil
        pygame.draw.ellipse(surface, (60, 44, 28), (pot_x - 7, table.top - 18, 14, 5))
        plant_sway = int(math.sin(ticks * 0.001 + pi_t * 1.4 + seed) * 2)
        pcols = plant_types[pi_t % 3]
        for stem_i in range(4):
            angle_s = math.radians(-30 + stem_i * 20)
            sx_s = pot_x + int(math.cos(angle_s) * 7) + plant_sway
            sy_s = table.top - 16 - int(abs(math.sin(angle_s)) * 11)
            pygame.draw.line(surface, (56, 108, 38), (pot_x, table.top - 16), (sx_s, sy_s), 1)
            pygame.draw.ellipse(surface, pcols[stem_i % len(pcols)], (sx_s - 5, sy_s - 3, 10, 6))
            if pi_t == 1 or pi_t == 2:
                pygame.draw.circle(surface, (255, 240, 180), (sx_s, sy_s), 1)

    # large mortar & pestle
    mp_x = x + 30
    pygame.draw.ellipse(surface, (120, 108, 82), (mp_x - 14, table.top - 16, 28, 18))
    pygame.draw.ellipse(surface, (94, 84, 60), (mp_x - 14, table.top - 16, 28, 18), 2)
    pygame.draw.ellipse(surface, (96, 170, 86), (mp_x - 10, table.top - 12, 20, 10))
    pygame.draw.line(surface, (148, 136, 106), (mp_x - 4, table.top - 18), (mp_x + 10, table.top - 28), 3)
    pygame.draw.circle(surface, (168, 154, 122), (mp_x + 10, table.top - 28), 3)

    # open recipe book
    bk_x = x + 58
    pygame.draw.rect(surface, (136, 104, 60), (bk_x - 16, table.top - 18, 32, 22), border_radius=2)
    pygame.draw.rect(surface, (104, 78, 44), (bk_x - 16, table.top - 18, 32, 22), 1, border_radius=2)
    pygame.draw.line(surface, (84, 62, 34), (bk_x, table.top - 18), (bk_x, table.top + 4), 1)
    for tl2 in range(3):
        pygame.draw.line(surface, (64, 50, 30), (bk_x - 14, table.top - 14 + tl2 * 6), (bk_x - 2, table.top - 14 + tl2 * 6), 1)
        pygame.draw.line(surface, (64, 50, 30), (bk_x + 3, table.top - 14 + tl2 * 6), (bk_x + 14, table.top - 14 + tl2 * 6), 1)

    # ════════════════════════════════════════════════════
    # VFX & PARTICLES
    # ════════════════════════════════════════════════════

    # ── Warm chimney smoke ──
    for i in range(8):
        t = ticks * 0.0009 + seed * 0.06 + i * 1.0
        sx_c = chim_rect.centerx + math.sin(t * 1.3 + i) * (5 + i * 2)
        sy_c = chim_rect.top - 8 - (t * 13 + i * 7) % 42
        sz_c = 10 + i * 3
        sm_c = pygame.Surface((sz_c, sz_c), pygame.SRCALPHA)
        smoke_a = max(5, 50 - i * 6)
        smoke_col = (148, 126, 96) if i % 2 == 0 else (168, 148, 116)
        pygame.draw.ellipse(sm_c, (*smoke_col, smoke_a), sm_c.get_rect())
        surface.blit(sm_c, (int(sx_c) - sz_c // 2, int(sy_c) - sz_c // 2))

    # ── Bioluminescent mushrooms at base (5 glowing caps) ──
    mush_positions = [(-172, -8), (-148, -6), (140, -9), (162, -7), (176, -5)]
    mush_cols = [(160, 80, 200), (80, 200, 160), (200, 160, 60), (80, 160, 220), (180, 80, 160)]
    for mi, (mx_off, my_off) in enumerate(mush_positions):
        mx2 = x + mx_off
        my2 = ground + my_off
        mc = mush_cols[mi]
        # stalk
        pygame.draw.line(surface, (200, 188, 170), (mx2, my2), (mx2, my2 - 12), 2)
        # cap
        pygame.draw.ellipse(surface, mc, (mx2 - 9, my2 - 18, 18, 10))
        pygame.draw.ellipse(surface, (min(255, mc[0] + 30), min(255, mc[1] + 30), min(255, mc[2] + 30)),
                            (mx2 - 7, my2 - 16, 14, 6))
        pygame.draw.ellipse(surface, (max(0, mc[0] - 30), max(0, mc[1] - 30), max(0, mc[2] - 30)),
                            (mx2 - 9, my2 - 18, 18, 10), 1)
        # pulsing glow on mushroom
        mush_pulse = int(40 + 30 * math.sin(ticks * 0.003 + mi * 1.26 + seed))
        for mr, ma in ((12, mush_pulse // 2), (7, mush_pulse), (4, mush_pulse + 20)):
            mg_s = pygame.Surface((mr * 2, mr * 2), pygame.SRCALPHA)
            pygame.draw.circle(mg_s, (*mc, min(255, ma)), (mr, mr), mr)
            surface.blit(mg_s, (mx2 - mr, my2 - 14 - mr), special_flags=pygame.BLEND_RGBA_ADD)

    # ── Cauldron in corner: green bubbling brew ──
    cld2_x, cld2_y = x - 148, ground
    for leg_off2 in (-14, 0, 14):
        pygame.draw.line(surface, (60, 50, 34), (cld2_x + leg_off2, cld2_y), (cld2_x, cld2_y - 14), 3)
    pygame.draw.ellipse(surface, (44, 40, 32), (cld2_x - 30, cld2_y - 46, 60, 50))
    pygame.draw.ellipse(surface, (70, 64, 50), (cld2_x - 30, cld2_y - 46, 60, 50), 2)
    pygame.draw.ellipse(surface, (60, 54, 40), (cld2_x - 32, cld2_y - 48, 64, 12))
    pygame.draw.ellipse(surface, (84, 76, 58), (cld2_x - 32, cld2_y - 48, 64, 12), 1)
    brew2_t = ticks * 0.002
    brew2_r = int(40 + 60 * abs(math.sin(brew2_t + seed)))
    brew2_g = int(160 + 70 * abs(math.sin(brew2_t * 0.8 + seed + 1.0)))
    brew2_b = int(50 + 60 * abs(math.sin(brew2_t * 1.2 + seed + 2.0)))
    pygame.draw.ellipse(surface, (brew2_r, brew2_g, brew2_b), (cld2_x - 28, cld2_y - 44, 56, 12))
    # brew glow (tight layers)
    for cr4, ca4 in ((12, 90), (8, 130), (4, 170)):
        cg4 = pygame.Surface((cr4 * 2, cr4 * 2), pygame.SRCALPHA)
        pygame.draw.circle(cg4, (brew2_r, brew2_g, brew2_b, ca4), (cr4, cr4), cr4)
        surface.blit(cg4, (cld2_x - cr4, cld2_y - 42 - cr4), special_flags=pygame.BLEND_RGBA_ADD)
    # fire
    for fi3 in range(5):
        ft3 = ticks * 0.004 + seed * 0.12 + fi3 * 0.78
        fx3 = cld2_x - 12 + fi3 * 6 + int(math.sin(ft3 * 2.4) * 3)
        fy3 = cld2_y - 4 - int(abs(math.sin(ft3 * 1.7 + fi3)) * 10)
        pygame.draw.circle(surface, (min(255, 190 + fi3 * 12), max(0, 130 - fi3 * 20), 14), (int(fx3), int(fy3)), 2 + fi3 % 2)
        pygame.draw.circle(surface, (255, 220, 80), (int(fx3), int(fy3) - 1), 1)
    # brew bubbles
    for i in range(12):
        t = ticks * 0.0013 + seed * 0.1 + i * 0.52
        life = (t * 20 + i * 6) % 48
        bx_b = cld2_x + int(math.sin(t * 1.8 + i) * 22)
        by_b = int(cld2_y - 36 - life * 1.1)
        rad_b = max(1, 3 - int(life / 16))
        fade_b = max(0, 170 - int(life * 3.6))
        bs_b = pygame.Surface((rad_b * 2 + 2, rad_b * 2 + 2), pygame.SRCALPHA)
        pygame.draw.circle(bs_b, (brew2_r, brew2_g, brew2_b, fade_b), (rad_b + 1, rad_b + 1), rad_b)
        pygame.draw.circle(bs_b, (255, 255, 255, fade_b // 4), (rad_b, rad_b), max(1, rad_b - 1), 1)
        surface.blit(bs_b, (bx_b - rad_b - 1, by_b - rad_b - 1))

    # ── Brew steam (green-tinted) ──
    for i in range(7):
        t = ticks * 0.0009 + seed * 0.06 + i * 1.05
        sx_st = cld2_x + int(math.sin(t * 1.1 + i) * 16)
        sy_st = cld2_y - 48 - int((t * 18 + i * 8) % 38)
        sz_st = 11 + i * 3
        sm_st = pygame.Surface((sz_st, sz_st), pygame.SRCALPHA)
        a_st = max(5, 50 - i * 7)
        scol_st = (50, 130, 50) if i % 2 == 0 else (40, 110, 60)
        pygame.draw.ellipse(sm_st, (*scol_st, a_st), sm_st.get_rect())
        surface.blit(sm_st, (int(sx_st) - sz_st // 2, int(sy_st) - sz_st // 2), special_flags=pygame.BLEND_RGBA_ADD)

    # ── Fireflies — low near ground, slow drift with proper halos ──
    for i in range(12):
        t = ticks * 0.0006 + seed * 0.16 + i * 0.52
        # slow sinusoidal path, stays within 30px of ground
        fly_x = x - 170 + int((i / 11) * 340) + int(math.sin(t * 1.1 + i * 0.9) * 30)
        fly_y = ground - 10 - int(abs(math.sin(t * 0.7 + i * 1.3)) * 28)
        fly_bright = int(180 + 60 * math.sin(ticks * 0.005 + i * 2.1))
        fly_col = [(130, 220, 70), (170, 240, 50), (90, 210, 110), (150, 230, 70), (110, 200, 90)][i % 5]
        # halo (largest layer first, tight radii)
        for fr, fa in ((10, fly_bright // 6), (6, fly_bright // 3), (3, fly_bright // 2), (1, fly_bright)):
            ff_gs = pygame.Surface((fr * 2, fr * 2), pygame.SRCALPHA)
            pygame.draw.circle(ff_gs, (*fly_col, min(255, fa)), (fr, fr), fr)
            surface.blit(ff_gs, (fly_x - fr, fly_y - fr), special_flags=pygame.BLEND_RGBA_ADD)
        pygame.draw.circle(surface, (240, 255, 200), (fly_x, fly_y), 1)

    # ── Herb shelf wisps (soft green upward drift) ──
    for i in range(10):
        t = ticks * 0.001 + seed * 0.09 + i * 0.73
        life_w = (t * 12 + i * 5) % 50
        wx_h = (x - 50) + int((i / 9) * 118)
        wy_h = ground - 123 - int(life_w * 1.3)
        wc_h = [(76, 196, 94), (116, 218, 56), (56, 178, 88), (96, 198, 68),
                (76, 218, 118), (136, 198, 58), (56, 158, 78), (96, 218, 78),
                (148, 198, 76), (76, 198, 218)][i]
        fade_w = max(0, 72 - int(life_w * 1.45))
        if fade_w > 2:
            hw_s = pygame.Surface((7, 7), pygame.SRCALPHA)
            pygame.draw.circle(hw_s, (*wc_h, fade_w), (3, 3), 2)
            surface.blit(hw_s, (wx_h - 3, wy_h - 3))

    # ── Window amber glow cast on ground ──
    for win_obj, glow_x in ((mwin_r, mwin_r.centerx), (lwin, lwin.centerx)):
        wcast = pygame.Surface((60, 16), pygame.SRCALPHA)
        wc_a = int(18 + 10 * math.sin(ticks * 0.002 + seed))
        pygame.draw.ellipse(wcast, (210, 168, 58, wc_a), (0, 0, 60, 16))
        surface.blit(wcast, (glow_x - 30, ground - 10), special_flags=pygame.BLEND_RGBA_ADD)

    # ── Ivy green ambient shimmer ──
    ivy_glow_a = int(8 + 6 * math.sin(ticks * 0.001 + seed))
    ivy_gs = pygame.Surface((56, wall.height), pygame.SRCALPHA)
    pygame.draw.rect(ivy_gs, (38, 96, 28, ivy_glow_a), (0, 0, 56, wall.height))
    surface.blit(ivy_gs, (wall.left, wall.top), special_flags=pygame.BLEND_RGBA_ADD)


def _draw_sailor_shop(surface: pygame.Surface, pos: Vector2, ticks: int, seed: int) -> None:  # noqa: C901
    x = int(pos.x)
    ground = int(pos.y)

    # ════════════════════════════════════════════════════
    # BUILDING
    # ════════════════════════════════════════════════════

    # ── Stone foundation ──
    foundation = pygame.Rect(x - 196, ground - 22, 392, 22)
    pygame.draw.rect(surface, (88, 84, 78), foundation)
    for fs in range(foundation.left, foundation.right - 4, 30):
        sh = 86 + (fs * 7 + seed) % 16
        pygame.draw.rect(surface, (sh, sh - 4, sh - 8), (fs, foundation.top + 2, 28, 9))
        pygame.draw.rect(surface, (64, 60, 54), (fs, foundation.top + 2, 28, 9), 1)
    pygame.draw.rect(surface, (64, 60, 54), foundation, 2)

    # ── Back wall — dark weathered planks with sea-worn timber frame ──
    wall = pygame.Rect(x - 196, ground - 210, 392, 188)
    pygame.draw.rect(surface, (78, 88, 96), wall)
    for pi2 in range(wall.left, wall.right, 18):
        plank_h = wall.height - 4 + (pi2 * 3 + seed) % 8
        pc = 74 + (pi2 * 5 + seed) % 16
        pygame.draw.rect(surface, (pc, pc + 8, pc + 14), (pi2, wall.top + 2, 16, plank_h))
        pygame.draw.rect(surface, (54, 62, 70), (pi2, wall.top + 2, 16, plank_h), 1)
        if (pi2 + seed) % 54 < 18:
            pygame.draw.ellipse(surface, (56, 64, 72), (pi2 + 6, wall.top + 20 + (pi2 * 7 + seed) % 60, 4, 3))
    pygame.draw.rect(surface, (50, 58, 66), wall, 2)
    # heavy cross-beams
    for bby in (wall.top + 62, wall.top + 124):
        pygame.draw.rect(surface, (56, 46, 30), (wall.left, bby - 5, wall.width, 10))
        pygame.draw.rect(surface, (38, 28, 14), (wall.left, bby - 5, wall.width, 10), 1)
    for bbx in (wall.left, wall.centerx, wall.right):
        pygame.draw.rect(surface, (56, 46, 30), (bbx - 5, wall.top, 10, wall.height))
        pygame.draw.rect(surface, (38, 28, 14), (bbx - 5, wall.top, 10, wall.height), 1)
    pygame.draw.rect(surface, (38, 28, 14), wall, 2)

    # ── Fishing net draped across upper wall ──
    net_top = wall.top + 8
    net_bot = wall.top + 56
    net_sway = math.sin(ticks * 0.0006 + seed) * 4
    net_col = (80, 110, 80)
    for nx in range(wall.left + 8, wall.right - 8, 16):
        droop = int(6 + (nx - wall.centerx) ** 2 * 0.0004 + net_sway)
        pygame.draw.line(surface, net_col, (nx, net_top), (nx, net_bot + droop), 1)
    for ny_step in range(5):
        ny = net_top + ny_step * 10
        for nx2 in range(wall.left + 8, wall.right - 8, 16):
            droop2 = int(6 + (nx2 - wall.centerx) ** 2 * 0.0004 + net_sway * (ny_step / 4))
            nx_end = nx2 + 16
            ny_end = ny + int(6 + (nx_end - wall.centerx) ** 2 * 0.0004 + net_sway * (ny_step / 4))
            pygame.draw.line(surface, net_col, (nx2, ny + droop2), (nx_end, ny_end + (0 if ny_step == 4 else 0)), 1)
    # floats on net edge
    for fi_n in range(10):
        fn_x = wall.left + 20 + fi_n * 36
        fn_y = net_top + int(6 + (fn_x - wall.centerx) ** 2 * 0.0004)
        pygame.draw.circle(surface, (200, 68, 44), (fn_x, fn_y), 3)
        pygame.draw.circle(surface, (140, 40, 22), (fn_x, fn_y), 3, 1)

    # ── Chimney (left side) ──
    chim_rect = pygame.Rect(x - 60, wall.top - 58, 28, 62)
    for crow in range(7):
        cy = chim_rect.top + crow * 9
        off = 6 if crow % 2 else 0
        for ci in range(-1, 3):
            bx = chim_rect.left + ci * 14 + off
            bc = 138 + (crow * 11 + ci * 7 + seed) % 20
            pygame.draw.rect(surface, (bc, bc // 2 + 10, bc // 3), (bx, cy, 12, 8))
            pygame.draw.rect(surface, (80, 40, 22), (bx, cy, 12, 8), 1)
    pygame.draw.rect(surface, (80, 40, 22), chim_rect, 1)
    pygame.draw.rect(surface, (70, 50, 30), (chim_rect.left - 4, chim_rect.top, chim_rect.width + 8, 6))

    # ── Steep dark roof ──
    roof_peak_x = x
    roof_peak_y = wall.top - 70
    roof_left = wall.left - 10
    roof_right = wall.right + 10
    pygame.draw.polygon(surface, (46, 52, 58),
                        [(roof_left, wall.top + 4), (roof_peak_x, roof_peak_y), (roof_right, wall.top + 4)])
    for row_r in range(10):
        row_frac = row_r / 9
        ry = int(roof_peak_y + row_frac * (wall.top + 4 - roof_peak_y))
        rw = int(row_frac * (roof_right - roof_left))
        rx = roof_peak_x - rw // 2
        td = 40 + row_r * 3
        for ti in range(rw // 14 + 1):
            tx = rx + ti * 14
            pygame.draw.rect(surface, (td, td + 4, td + 8), (tx, ry, 13, 8), border_radius=2)
            pygame.draw.rect(surface, (28, 34, 40), (tx, ry, 13, 8), 1, border_radius=2)
    pygame.draw.line(surface, (32, 38, 44), (roof_left, wall.top + 4), (roof_peak_x, roof_peak_y), 3)
    pygame.draw.line(surface, (32, 38, 44), (roof_peak_x, roof_peak_y), (roof_right, wall.top + 4), 3)
    pygame.draw.circle(surface, (50, 58, 64), (roof_peak_x, roof_peak_y), 5)
    pygame.draw.circle(surface, (28, 34, 40), (roof_peak_x, roof_peak_y), 5, 1)
    pygame.draw.line(surface, (24, 30, 36), (roof_left, wall.top + 5), (roof_right, wall.top + 5), 3)

    # ── Mast pole (left side, rises above roof) ──
    mast_x = x - 158
    mast_base = ground - 16
    mast_top = roof_peak_y - 52
    pygame.draw.line(surface, (100, 78, 44), (mast_x, mast_base), (mast_x, mast_top), 4)
    pygame.draw.line(surface, (80, 60, 30), (mast_x - 1, mast_base), (mast_x - 1, mast_top), 1)
    # crow's nest ring
    pygame.draw.ellipse(surface, (86, 66, 38), (mast_x - 12, mast_top + 10, 24, 10), 2)
    # yard arm
    yard_y = mast_top + 20
    pygame.draw.line(surface, (90, 70, 38), (mast_x - 36, yard_y), (mast_x + 36, yard_y), 3)
    # waving flag (triangular pennant)
    flag_sway = math.sin(ticks * 0.002 + seed) * 6
    flag_base_x, flag_base_y = mast_x, mast_top
    flag_tip_x = flag_base_x + 36 + int(flag_sway)
    flag_tip_y = flag_base_y + 10 + int(flag_sway * 0.3)
    flag_bot_x = flag_base_x + 34 + int(flag_sway * 0.8)
    flag_bot_y = flag_base_y + 20 + int(flag_sway * 0.5)
    pygame.draw.polygon(surface, (180, 30, 30),
                        [(flag_base_x, flag_base_y), (flag_tip_x, flag_tip_y), (flag_bot_x, flag_bot_y)])
    pygame.draw.polygon(surface, (120, 16, 16),
                        [(flag_base_x, flag_base_y), (flag_tip_x, flag_tip_y), (flag_bot_x, flag_bot_y)], 1)
    # rigging lines from mast to building
    pygame.draw.line(surface, (80, 68, 46), (mast_x, yard_y), (wall.right, wall.top + 10), 1)
    pygame.draw.line(surface, (80, 68, 46), (mast_x, mast_base + 20), (wall.left + 20, mast_base + 20), 1)

    # ── Central doorway ──
    door_rect = pygame.Rect(x - 26, ground - 108, 52, 86)
    pygame.draw.rect(surface, (44, 50, 56), door_rect)
    pygame.draw.ellipse(surface, (44, 50, 56), (door_rect.left, door_rect.top - 18, door_rect.width, 36))
    pygame.draw.ellipse(surface, (28, 34, 40), (door_rect.left, door_rect.top - 18, door_rect.width, 36), 2)
    pygame.draw.rect(surface, (70, 80, 88), door_rect, 2)
    pygame.draw.line(surface, (60, 68, 76), (door_rect.centerx, door_rect.top), (door_rect.centerx, door_rect.bottom), 1)

    # ── Left window — blue-tinted (sea light) ──
    lwin = pygame.Rect(x - 178, ground - 176, 64, 52)
    pygame.draw.rect(surface, (30, 36, 44), lwin, border_radius=2)
    wp_l = int(140 + 28 * math.sin(ticks * 0.0013 + seed))
    pygame.draw.rect(surface, (wp_l - 30, wp_l - 10, wp_l + 30),
                     (lwin.left + 3, lwin.top + 3, lwin.width - 6, lwin.height - 6))
    pygame.draw.line(surface, (48, 56, 64), (lwin.centerx, lwin.top), (lwin.centerx, lwin.bottom), 2)
    pygame.draw.line(surface, (48, 56, 64), (lwin.left, lwin.top + 26), (lwin.right, lwin.top + 26), 2)
    pygame.draw.rect(surface, (60, 70, 78), lwin, 2, border_radius=2)

    # ── Right window — wide, with rope/gear display ──
    rwin = pygame.Rect(x + 68, ground - 176, 104, 52)
    pygame.draw.rect(surface, (30, 36, 44), rwin, border_radius=2)
    wp_r = int(100 + 20 * math.sin(ticks * 0.001 + seed + 1.4))
    pygame.draw.rect(surface, (wp_r, wp_r + 8, wp_r + 20),
                     (rwin.left + 3, rwin.top + 3, rwin.width - 6, rwin.height - 6))
    pygame.draw.rect(surface, (60, 70, 78), rwin, 2, border_radius=2)
    # small wheel silhouette inside window
    wh_cx = rwin.left + 36
    wh_cy = rwin.centery
    pygame.draw.circle(surface, (140, 120, 70), (wh_cx, wh_cy), 14, 2)
    pygame.draw.circle(surface, (140, 120, 70), (wh_cx, wh_cy), 5, 1)
    for spi in range(8):
        spa = spi * math.pi / 4
        pygame.draw.line(surface, (130, 110, 62),
                         (wh_cx + int(math.cos(spa) * 5), wh_cy + int(math.sin(spa) * 5)),
                         (wh_cx + int(math.cos(spa) * 13), wh_cy + int(math.sin(spa) * 13)), 1)

    # ── Hanging anchor sign ──
    sign_arm_x = x + 196
    sign_arm_y = ground - 162
    pygame.draw.line(surface, (60, 70, 78), (wall.right, sign_arm_y), (sign_arm_x + 20, sign_arm_y), 3)
    pygame.draw.line(surface, (60, 70, 78), (sign_arm_x + 20, sign_arm_y), (sign_arm_x + 20, sign_arm_y + 14), 2)
    sboard = pygame.Rect(sign_arm_x - 16, sign_arm_y + 14, 48, 34)
    pygame.draw.rect(surface, (50, 60, 70), sboard, border_radius=4)
    pygame.draw.rect(surface, (90, 106, 118), sboard, 1, border_radius=4)
    an_cx = sboard.centerx
    an_cy = sboard.centery
    pygame.draw.line(surface, (160, 180, 190), (an_cx, an_cy - 12), (an_cx, an_cy + 12), 2)
    pygame.draw.ellipse(surface, (160, 180, 190), (an_cx - 8, an_cy - 14, 16, 8), 2)
    pygame.draw.line(surface, (160, 180, 190), (an_cx - 10, an_cy + 10), (an_cx + 10, an_cy + 10), 2)
    pygame.draw.circle(surface, (160, 180, 190), (an_cx - 10, an_cy + 10), 3, 1)
    pygame.draw.circle(surface, (160, 180, 190), (an_cx + 10, an_cy + 10), 3, 1)

    # ── Ship's wheel (mounted right of doorway on wall) ──
    sw_cx = x + 46
    sw_cy = ground - 140
    sw_r = 26
    sw_rot = ticks * 0.0004 + seed
    pygame.draw.circle(surface, (100, 78, 42), (sw_cx, sw_cy), sw_r, 3)
    pygame.draw.circle(surface, (80, 60, 28), (sw_cx, sw_cy), sw_r, 1)
    pygame.draw.circle(surface, (110, 86, 46), (sw_cx, sw_cy), 9)
    pygame.draw.circle(surface, (78, 58, 24), (sw_cx, sw_cy), 9, 2)
    for spi2 in range(8):
        spa2 = sw_rot + spi2 * (math.pi / 4)
        ix2 = sw_cx + int(math.cos(spa2) * 10)
        iy2 = sw_cy + int(math.sin(spa2) * 10)
        ex3 = sw_cx + int(math.cos(spa2) * sw_r)
        ey3 = sw_cy + int(math.sin(spa2) * sw_r)
        pygame.draw.line(surface, (92, 70, 36), (ix2, iy2), (ex3, ey3), 2)
        pygame.draw.circle(surface, (120, 94, 50), (ex3, ey3), 4)
        pygame.draw.circle(surface, (78, 58, 26), (ex3, ey3), 4, 1)

    # ════════════════════════════════════════════════════
    # PROPS & FURNITURE
    # ════════════════════════════════════════════════════

    # ── Large anchor (leaning on wall, left side) ──
    anch_x = x - 92
    anch_y = ground - 14
    pygame.draw.line(surface, (90, 96, 104), (anch_x, anch_y), (anch_x, anch_y - 52), 4)
    pygame.draw.ellipse(surface, (90, 96, 104), (anch_x - 12, anch_y - 58, 24, 12), 3)
    pygame.draw.line(surface, (90, 96, 104), (anch_x - 20, anch_y - 6), (anch_x + 20, anch_y - 6), 4)
    pygame.draw.circle(surface, (90, 96, 104), (anch_x - 20, anch_y - 6), 5, 3)
    pygame.draw.circle(surface, (90, 96, 104), (anch_x + 20, anch_y - 6), 5, 3)
    pygame.draw.rect(surface, (70, 76, 84), (anch_x - 2, anch_y - 52, 4, 52))
    pygame.draw.ellipse(surface, (110, 118, 126), (anch_x - 13, anch_y - 59, 26, 14), 1)

    # ── Rope coils (3, varied sizes) ──
    for rc_i, (rc_x, rc_ry, rc_r) in enumerate(((x - 168, ground - 12, 14), (x - 148, ground - 8, 10), (x - 164, ground - 26, 8))):
        rc_col = (164 + rc_i * 8, 136 + rc_i * 6, 80 + rc_i * 4)
        for rc_ring in range(3, 0, -1):
            pygame.draw.ellipse(surface, rc_col,
                                (rc_x - rc_r - rc_ring, rc_ry - rc_ring * 3,
                                 (rc_r + rc_ring) * 2, (rc_ring * 2 + 4)), 2)

    # ── Fish drying rack ──
    rack_fx = x - 126
    rack_fy = ground - 64
    pygame.draw.line(surface, (80, 62, 36), (rack_fx - 32, rack_fy), (rack_fx + 32, rack_fy), 3)
    pygame.draw.line(surface, (80, 62, 36), (rack_fx - 32, rack_fy), (rack_fx - 32, ground - 4), 2)
    pygame.draw.line(surface, (80, 62, 36), (rack_fx + 32, rack_fy), (rack_fx + 32, ground - 4), 2)
    for fi3 in range(5):
        fx3 = rack_fx - 24 + fi3 * 12
        fish_sway = math.sin(ticks * 0.0008 + fi3 * 1.2 + seed) * 2
        pygame.draw.line(surface, (100, 80, 50), (fx3, rack_fy), (fx3 + int(fish_sway), rack_fy + 8), 1)
        fc3 = [(90, 140, 160), (80, 120, 150), (100, 150, 170), (70, 110, 140), (110, 160, 180)][fi3]
        pygame.draw.ellipse(surface, fc3, (fx3 + int(fish_sway) - 6, rack_fy + 8, 12, 6))
        pygame.draw.ellipse(surface, (fc3[0] - 20, fc3[1] - 20, fc3[2] - 20),
                            (fx3 + int(fish_sway) - 6, rack_fy + 8, 12, 6), 1)
        tail_pts = [(fx3 + int(fish_sway) + 6, rack_fy + 11),
                    (fx3 + int(fish_sway) + 10, rack_fy + 8),
                    (fx3 + int(fish_sway) + 10, rack_fy + 14)]
        pygame.draw.polygon(surface, fc3, tail_pts)

    # ── Barrels (salt fish / goods) ──
    for bar_i2, (bar_x2, bar_h2) in enumerate(((x + 134, 32), (x + 154, 28), (x + 170, 36))):
        bt2 = ground - bar_h2
        pygame.draw.ellipse(surface, (72, 84, 92), (bar_x2 - 14, bt2 - 7, 28, 12))
        pygame.draw.rect(surface, (64, 76, 84), (bar_x2 - 14, bt2 - 2, 28, bar_h2))
        pygame.draw.ellipse(surface, (64, 76, 84), (bar_x2 - 14, ground - 12, 28, 12))
        for hoop2 in (bt2 + 4, bt2 + bar_h2 // 2):
            pygame.draw.ellipse(surface, (48, 58, 68), (bar_x2 - 15, hoop2, 30, 7), 2)
        pygame.draw.rect(surface, (50, 62, 70), (bar_x2 - 14, bt2 - 2, 28, bar_h2), 1)

    # ── Crates (stacked, right side) ──
    for cr_i, (cr_x2, cr_y2, cr_w2, cr_h2) in enumerate((
        (x + 100, ground - 24, 36, 24), (x + 106, ground - 46, 28, 22), (x + 112, ground - 64, 22, 18)
    )):
        cr_c = (76 + cr_i * 6, 84 + cr_i * 5, 92 + cr_i * 4)
        pygame.draw.rect(surface, cr_c, (cr_x2, cr_y2, cr_w2, cr_h2), border_radius=2)
        pygame.draw.rect(surface, (54, 62, 70), (cr_x2, cr_y2, cr_w2, cr_h2), 1, border_radius=2)
        pygame.draw.line(surface, (54, 62, 70), (cr_x2, cr_y2), (cr_x2 + cr_w2, cr_y2 + cr_h2), 1)
        pygame.draw.line(surface, (54, 62, 70), (cr_x2 + cr_w2, cr_y2), (cr_x2, cr_y2 + cr_h2), 1)

    # ── Lobster trap (wicker basket shape) ──
    lt_x = x - 50
    lt_y = ground - 18
    pygame.draw.ellipse(surface, (128, 106, 62), (lt_x - 20, lt_y - 8, 40, 16))
    pygame.draw.ellipse(surface, (90, 72, 38), (lt_x - 20, lt_y - 8, 40, 16), 1)
    pygame.draw.ellipse(surface, (110, 90, 52), (lt_x - 20, lt_y - 18, 40, 14))
    pygame.draw.ellipse(surface, (80, 64, 32), (lt_x - 20, lt_y - 18, 40, 14), 1)
    for lt_i in range(5):
        lx5 = lt_x - 16 + lt_i * 8
        pygame.draw.line(surface, (90, 72, 38), (lx5, lt_y - 16), (lx5, lt_y - 2), 1)
    for lt_row in range(3):
        pygame.draw.ellipse(surface, (90, 72, 38),
                            (lt_x - 18 + lt_row, lt_y - 16 + lt_row * 4, 36 - lt_row * 2, 5), 1)

    # ── Coiled rope on dock post ──
    post_x = x - 8
    pygame.draw.line(surface, (90, 70, 38), (post_x, ground - 4), (post_x, ground - 44), 4)
    for ri3 in range(4):
        rangle = ticks * 0.0 + ri3 * (math.pi / 2)
        rx5 = post_x + int(math.cos(rangle) * (8 + ri3 * 2))
        ry5 = ground - 28 + int(math.sin(rangle) * 4)
        pygame.draw.circle(surface, (148, 120, 68), (rx5, ry5), 3)
    pygame.draw.circle(surface, (110, 88, 44), (post_x, ground - 44), 5)
    pygame.draw.circle(surface, (80, 62, 28), (post_x, ground - 44), 5, 1)

    # ════════════════════════════════════════════════════
    # VFX & PARTICLES
    # ════════════════════════════════════════════════════

    # ── Chimney smoke ──
    for i in range(10):
        t = ticks * 0.0007 + seed * 0.06 + i * 0.85
        sx_c = chim_rect.centerx + math.sin(t * 1.1 + i) * (5 + i * 2)
        sy_c = chim_rect.top - 6 - (t * 11 + i * 9) % 50
        sz_c = 10 + i * 4
        sa_c = max(0, int(80 - i * 6))
        sc_s = pygame.Surface((sz_c, sz_c), pygame.SRCALPHA)
        pygame.draw.ellipse(sc_s, (140 + i * 4, 148 + i * 3, 154 + i * 2, sa_c), sc_s.get_rect())
        surface.blit(sc_s, (int(sx_c) - sz_c // 2, int(sy_c) - sz_c // 2))

    # ── Sea mist at ground level ──
    for i in range(12):
        t = ticks * 0.0004 + seed * 0.13 + i * 0.52
        mist_life = (t * 2 + i * 0.7) % 1.0
        mist_x = x - 180 + int((i / 11) * 360) + int(math.sin(t * 0.8 + i) * 20)
        mist_y = ground - 6 - int(mist_life * 18)
        mist_w = 28 + i * 4
        mist_a = int(50 * math.sin(mist_life * math.pi))
        if mist_a > 6:
            ms4 = pygame.Surface((mist_w, 10), pygame.SRCALPHA)
            pygame.draw.ellipse(ms4, (160, 180, 196, mist_a), ms4.get_rect())
            surface.blit(ms4, (mist_x - mist_w // 2, mist_y - 5))

    # ── Rope rigging creak shimmer (subtle sparkle on lines) ──
    for i in range(6):
        t = ticks * 0.0008 + seed * 0.15 + i * 0.8
        creak_life = (t * 4 + i) % 1.0
        creak_x = int(mast_x + (wall.right - mast_x) * (i / 5))
        creak_y = int(yard_y + (wall.top + 10 - yard_y) * (i / 5))
        creak_a = int(100 * math.sin(creak_life * math.pi))
        if creak_a > 20:
            cr_s = pygame.Surface((4, 4), pygame.SRCALPHA)
            pygame.draw.circle(cr_s, (180, 200, 220, creak_a), (2, 2), 1)
            surface.blit(cr_s, (creak_x - 2, creak_y - 2), special_flags=pygame.BLEND_RGBA_ADD)

    # ── Salt spray motes ──
    for i in range(14):
        t = ticks * 0.0005 + seed * 0.17 + i * 0.44
        sp_life = (t * 3 + i * 1.1) % 1.0
        sp_x = x - 180 + int((i / 13) * 360) + int(math.sin(t * 2.0 + i) * 12)
        sp_y = ground - 20 - int(sp_life * 70)
        sp_a = int(90 * math.sin(sp_life * math.pi))
        if sp_a > 10:
            sp_s = pygame.Surface((4, 4), pygame.SRCALPHA)
            pygame.draw.circle(sp_s, (200, 220, 240, sp_a), (2, 2), 1)
            surface.blit(sp_s, (sp_x - 2, sp_y - 2))


def _draw_miller_shop(surface: pygame.Surface, pos: Vector2, ticks: int, seed: int) -> None:  # noqa: C901
    x = int(pos.x)
    ground = int(pos.y)

    # ════════════════════════════════════════════════════
    # BUILDING
    # ════════════════════════════════════════════════════

    # ── Stone foundation ──
    foundation = pygame.Rect(x - 196, ground - 22, 392, 22)
    pygame.draw.rect(surface, (98, 86, 66), foundation)
    for fs in range(foundation.left, foundation.right - 4, 30):
        sh = 94 + (fs * 7 + seed) % 18
        pygame.draw.rect(surface, (sh, sh - 8, sh - 14), (fs, foundation.top + 2, 28, 9))
        pygame.draw.rect(surface, (72, 60, 44), (fs, foundation.top + 2, 28, 9), 1)
    pygame.draw.rect(surface, (72, 60, 44), foundation, 2)

    # ── Back wall — aged grey plaster + heavy timber frame ──
    wall = pygame.Rect(x - 196, ground - 210, 392, 188)
    pygame.draw.rect(surface, (186, 174, 148), wall)
    for row_idx, row_y in enumerate((wall.top + 4, wall.top + 68, wall.top + 124)):
        for col_idx, col_x in enumerate((wall.left + 6, wall.left + 106, wall.centerx + 4, wall.right - 100)):
            ph = 42 if row_idx == 2 else 54
            ps = 190 + (col_x * 3 + row_y * 5 + seed) % 14
            panel = pygame.Rect(col_x + 2, row_y + 2, 88, ph)
            pygame.draw.rect(surface, (ps, ps - 10, ps - 20), panel)
            if (col_idx + row_idx + seed) % 3 == 0:
                pygame.draw.line(surface, (ps - 20, ps - 28, ps - 36),
                                 (panel.left + 10, panel.top + 8), (panel.left + 22, panel.top + 20), 1)
    for bby in (wall.top, wall.top + 66, wall.top + 122, wall.bottom):
        pygame.draw.rect(surface, (68, 48, 24), (wall.left, bby - 5, wall.width, 10))
        pygame.draw.rect(surface, (46, 28, 10), (wall.left, bby - 5, wall.width, 10), 1)
        pygame.draw.line(surface, (86, 62, 32), (wall.left + 2, bby), (wall.right - 2, bby), 1)
    for bbx in (wall.left, wall.left + 100, wall.centerx, wall.right - 100, wall.right):
        pygame.draw.rect(surface, (68, 48, 24), (bbx - 5, wall.top, 10, wall.height))
        pygame.draw.rect(surface, (46, 28, 10), (bbx - 5, wall.top, 10, wall.height), 1)
    pygame.draw.rect(surface, (46, 28, 10), wall, 2)

    # ── Brick chimney ──
    chim_rect = pygame.Rect(x + 50, wall.top - 62, 30, 66)
    for crow in range(8):
        cy = chim_rect.top + crow * 9
        off = 7 if crow % 2 else 0
        for ci in range(-1, 3):
            bx = chim_rect.left + ci * 16 + off
            bc = 148 + (crow * 11 + ci * 7 + seed) % 22
            pygame.draw.rect(surface, (bc, bc // 2 + 16, bc // 3), (bx, cy, 14, 8))
            pygame.draw.rect(surface, (86, 46, 26), (bx, cy, 14, 8), 1)
    pygame.draw.rect(surface, (86, 46, 26), chim_rect, 1)
    pygame.draw.rect(surface, (76, 52, 32), (chim_rect.left - 4, chim_rect.top, chim_rect.width + 8, 7))

    # ── Steep dark shingle roof ──
    roof_peak_x = x
    roof_peak_y = wall.top - 72
    roof_left = wall.left - 10
    roof_right = wall.right + 10
    pygame.draw.polygon(surface, (60, 48, 32),
                        [(roof_left, wall.top + 4), (roof_peak_x, roof_peak_y), (roof_right, wall.top + 4)])
    for row_r in range(10):
        row_frac = row_r / 9
        ry = int(roof_peak_y + row_frac * (wall.top + 4 - roof_peak_y))
        rw = int(row_frac * (roof_right - roof_left))
        rx = roof_peak_x - rw // 2
        tile_dark = 52 + row_r * 3
        for ti in range(rw // 14 + 1):
            tx = rx + ti * 14
            pygame.draw.rect(surface, (tile_dark, tile_dark - 8, tile_dark - 16), (tx, ry, 13, 8), border_radius=2)
            pygame.draw.rect(surface, (36, 26, 14), (tx, ry, 13, 8), 1, border_radius=2)
    pygame.draw.line(surface, (44, 32, 16), (roof_left, wall.top + 4), (roof_peak_x, roof_peak_y), 3)
    pygame.draw.line(surface, (44, 32, 16), (roof_peak_x, roof_peak_y), (roof_right, wall.top + 4), 3)
    pygame.draw.circle(surface, (56, 42, 22), (roof_peak_x, roof_peak_y), 5)
    pygame.draw.circle(surface, (36, 24, 10), (roof_peak_x, roof_peak_y), 5, 1)
    pygame.draw.line(surface, (34, 22, 8), (roof_left, wall.top + 5), (roof_right, wall.top + 5), 3)

    # ── Windmill tower (left side, rises above roof) ──
    mill_cx = x - 148
    mill_cy = roof_peak_y - 32
    mill_tower_rect = pygame.Rect(mill_cx - 20, wall.top - 8, 40, wall.height // 2 + 8)
    pygame.draw.rect(surface, (110, 96, 72), mill_tower_rect)
    for tw_row in range(7):
        tw_y = mill_tower_rect.top + tw_row * 14
        tw_off = 6 if tw_row % 2 else 0
        for tw_col in range(-1, 4):
            twx = mill_tower_rect.left + tw_col * 14 + tw_off
            twc = 104 + (tw_row * 9 + tw_col * 5 + seed) % 20
            pygame.draw.rect(surface, (twc, twc - 10, twc - 18), (twx, tw_y, 12, 12))
            pygame.draw.rect(surface, (72, 56, 36), (twx, tw_y, 12, 12), 1)
    pygame.draw.rect(surface, (72, 56, 36), mill_tower_rect, 2)
    # tower cap (conical)
    pygame.draw.polygon(surface, (54, 42, 26),
                        [(mill_cx - 22, mill_tower_rect.top),
                         (mill_cx, mill_cy - 14),
                         (mill_cx + 22, mill_tower_rect.top)])
    pygame.draw.polygon(surface, (36, 24, 12),
                        [(mill_cx - 22, mill_tower_rect.top),
                         (mill_cx, mill_cy - 14),
                         (mill_cx + 22, mill_tower_rect.top)], 1)
    # tower window
    pygame.draw.rect(surface, (36, 26, 14), (mill_cx - 8, mill_tower_rect.top + 16, 16, 20), border_radius=2)
    pygame.draw.rect(surface, (88, 70, 44), (mill_cx - 8, mill_tower_rect.top + 16, 16, 20), 1, border_radius=2)

    # ── Windmill hub + axle ──
    pygame.draw.circle(surface, (88, 68, 40), (mill_cx, mill_cy), 10)
    pygame.draw.circle(surface, (60, 44, 22), (mill_cx, mill_cy), 10, 2)
    pygame.draw.circle(surface, (130, 100, 58), (mill_cx, mill_cy), 5)
    pygame.draw.line(surface, (80, 60, 32), (mill_cx - 2, mill_cy - 10), (mill_cx + 2, mill_cy + 10), 3)
    pygame.draw.line(surface, (80, 60, 32), (mill_cx - 10, mill_cy - 2), (mill_cx + 10, mill_cy + 2), 3)

    # ── Rotating sails (4 blades) ──
    sail_angle = ticks * 0.0009 + seed * 0.6
    sail_arm = 52
    for si in range(4):
        angle = sail_angle + si * (math.pi / 2)
        ax = mill_cx + int(math.cos(angle) * sail_arm)
        ay = mill_cy + int(math.sin(angle) * sail_arm)
        pygame.draw.line(surface, (76, 56, 28), (mill_cx, mill_cy), (ax, ay), 3)
        perp = angle + math.pi / 2
        sw = 10
        inner_dist = 10
        ix = mill_cx + int(math.cos(angle) * inner_dist)
        iy = mill_cy + int(math.sin(angle) * inner_dist)
        pts = [
            (ix + int(math.cos(perp) * sw), iy + int(math.sin(perp) * sw)),
            (ax + int(math.cos(perp) * sw), ay + int(math.sin(perp) * sw)),
            (ax - int(math.cos(perp) * sw), ay - int(math.sin(perp) * sw)),
            (ix - int(math.cos(perp) * sw), iy - int(math.sin(perp) * sw)),
        ]
        sail_shade = 194 if math.cos(angle) > 0 else 168
        pygame.draw.polygon(surface, (sail_shade, sail_shade - 16, sail_shade - 34), pts)
        pygame.draw.polygon(surface, (100, 76, 40), pts, 1)
        # crossbrace on each sail
        mx = (pts[0][0] + pts[3][0]) // 2
        my = (pts[0][1] + pts[3][1]) // 2
        ex2 = (pts[1][0] + pts[2][0]) // 2
        ey2 = (pts[1][1] + pts[2][1]) // 2
        pygame.draw.line(surface, (110, 84, 44), (mx, my), (ex2, ey2), 1)

    # ── Hanging millstone sign ──
    sign_arm_x = x + 196
    sign_arm_y = ground - 168
    pygame.draw.line(surface, (60, 48, 30), (wall.right, sign_arm_y), (sign_arm_x + 22, sign_arm_y), 3)
    pygame.draw.line(surface, (60, 48, 30), (sign_arm_x + 22, sign_arm_y), (sign_arm_x + 22, sign_arm_y + 14), 2)
    # circular millstone sign
    ms_cx = sign_arm_x + 4
    ms_cy = sign_arm_y + 36
    pygame.draw.circle(surface, (148, 130, 100), (ms_cx, ms_cy), 22)
    pygame.draw.circle(surface, (100, 84, 60), (ms_cx, ms_cy), 22, 2)
    pygame.draw.circle(surface, (80, 66, 46), (ms_cx, ms_cy), 7)
    pygame.draw.circle(surface, (60, 48, 30), (ms_cx, ms_cy), 7, 1)
    for groove_i in range(8):
        ga = groove_i * math.pi / 4
        gx1 = ms_cx + int(math.cos(ga) * 9)
        gy1 = ms_cy + int(math.sin(ga) * 9)
        gx2 = ms_cx + int(math.cos(ga) * 20)
        gy2 = ms_cy + int(math.sin(ga) * 20)
        pygame.draw.line(surface, (110, 90, 66), (gx1, gy1), (gx2, gy2), 1)

    # ── Central doorway ──
    door_rect = pygame.Rect(x - 26, ground - 108, 52, 86)
    pygame.draw.rect(surface, (50, 36, 18), door_rect)
    pygame.draw.ellipse(surface, (50, 36, 18), (door_rect.left, door_rect.top - 18, door_rect.width, 36))
    pygame.draw.ellipse(surface, (36, 24, 10), (door_rect.left, door_rect.top - 18, door_rect.width, 36), 2)
    pygame.draw.rect(surface, (80, 60, 32), door_rect, 2)
    pygame.draw.line(surface, (72, 54, 26), (door_rect.centerx, door_rect.top), (door_rect.centerx, door_rect.bottom), 1)

    # ── Right window (small, square) ──
    rwin = pygame.Rect(x + 76, ground - 176, 72, 52)
    pygame.draw.rect(surface, (38, 26, 12), rwin, border_radius=2)
    wp = int(160 + 24 * math.sin(ticks * 0.001 + seed))
    pygame.draw.rect(surface, (wp, wp - 30, wp - 60), (rwin.left + 3, rwin.top + 3, rwin.width - 6, rwin.height - 6))
    pygame.draw.line(surface, (56, 38, 16), (rwin.centerx, rwin.top), (rwin.centerx, rwin.bottom), 2)
    pygame.draw.line(surface, (56, 38, 16), (rwin.left, rwin.top + 26), (rwin.right, rwin.top + 26), 2)
    pygame.draw.rect(surface, (72, 52, 24), rwin, 2, border_radius=2)

    # ════════════════════════════════════════════════════
    # PROPS & FURNITURE
    # ════════════════════════════════════════════════════

    # ── Millstone pair (centrepiece, right of door) ──
    ms2_x = x + 60
    ms2_y = ground - 16
    # lower stone (stationary)
    pygame.draw.ellipse(surface, (140, 120, 90), (ms2_x - 34, ms2_y - 14, 68, 22))
    pygame.draw.ellipse(surface, (90, 74, 52), (ms2_x - 34, ms2_y - 14, 68, 22), 2)
    # upper stone (slow rotate — groove pattern)
    ms_rot = ticks * 0.0006 + seed
    pygame.draw.ellipse(surface, (122, 104, 78), (ms2_x - 30, ms2_y - 28, 60, 18))
    pygame.draw.ellipse(surface, (80, 64, 44), (ms2_x - 30, ms2_y - 28, 60, 18), 2)
    for gi2 in range(6):
        ga2 = ms_rot + gi2 * (math.pi / 3)
        gx3 = ms2_x + int(math.cos(ga2) * 20)
        gy3 = ms2_y - 20 + int(math.sin(ga2) * 7)
        gx4 = ms2_x + int(math.cos(ga2) * 10)
        gy4 = ms2_y - 20 + int(math.sin(ga2) * 4)
        pygame.draw.line(surface, (96, 78, 56), (gx4, gy4), (gx3, gy3), 1)
    pygame.draw.ellipse(surface, (100, 80, 56), (ms2_x - 7, ms2_y - 26, 14, 8))
    pygame.draw.ellipse(surface, (68, 52, 32), (ms2_x - 7, ms2_y - 26, 14, 8), 1)
    # grain hopper above millstone
    hop_pts = [(ms2_x - 22, ms2_y - 60), (ms2_x + 22, ms2_y - 60),
               (ms2_x + 10, ms2_y - 32), (ms2_x - 10, ms2_y - 32)]
    pygame.draw.polygon(surface, (106, 82, 52), hop_pts)
    pygame.draw.polygon(surface, (70, 52, 28), hop_pts, 2)
    pygame.draw.line(surface, (80, 60, 32), (ms2_x - 22, ms2_y - 60), (ms2_x - 28, ms2_y - 72), 2)
    pygame.draw.line(surface, (80, 60, 32), (ms2_x + 22, ms2_y - 60), (ms2_x + 28, ms2_y - 72), 2)
    pygame.draw.line(surface, (80, 60, 32), (ms2_x - 28, ms2_y - 72), (ms2_x + 28, ms2_y - 72), 2)
    # flour chute from millstone to collection bin
    pygame.draw.line(surface, (90, 72, 46), (ms2_x + 28, ms2_y - 20), (ms2_x + 46, ms2_y - 6), 3)
    # flour drizzle from chute
    for fd_i in range(3):
        fd_t = (ticks * 0.004 + fd_i * 0.4) % 1.0
        fd_x = ms2_x + 28 + int(fd_t * 18)
        fd_y = ms2_y - 20 + int(fd_t * 14)
        fd_a = int(180 * math.sin(fd_t * math.pi))
        if fd_a > 20:
            fds = pygame.Surface((4, 4), pygame.SRCALPHA)
            pygame.draw.circle(fds, (230, 220, 200, fd_a), (2, 2), 1)
            surface.blit(fds, (fd_x - 2, fd_y - 2))

    # ── Collection bin (receives flour) ──
    bin_r = pygame.Rect(ms2_x + 40, ground - 26, 42, 22)
    pygame.draw.rect(surface, (86, 64, 38), bin_r, border_radius=3)
    pygame.draw.rect(surface, (130, 100, 60), bin_r, 1, border_radius=3)
    pygame.draw.ellipse(surface, (210, 200, 180), (bin_r.left + 3, bin_r.top + 3, bin_r.width - 6, 8))
    pygame.draw.ellipse(surface, (170, 160, 140), (bin_r.left + 3, bin_r.top + 3, bin_r.width - 6, 8), 1)

    # ── Grain sacks (pile left of door) ──
    sack_base_x = x - 90
    sack_positions = [(-32, 0), (-16, 0), (0, 0), (-24, -18), (-8, -18)]
    for sk_i, (sk_dx, sk_dy) in enumerate(sack_positions):
        sk_x = sack_base_x + sk_dx
        sk_y = ground - 16 + sk_dy
        sk_c = (176 + sk_i * 4, 154 + sk_i * 3, 112 + sk_i * 2)
        pygame.draw.ellipse(surface, sk_c, (sk_x - 12, sk_y - 22, 24, 24))
        pygame.draw.ellipse(surface, (sk_c[0] - 30, sk_c[1] - 28, sk_c[2] - 20), (sk_x - 12, sk_y - 22, 24, 24), 1)
        pygame.draw.line(surface, (sk_c[0] - 40, sk_c[1] - 36, sk_c[2] - 28),
                         (sk_x - 4, sk_y - 20), (sk_x + 4, sk_y - 12), 1)
        pygame.draw.ellipse(surface, (130, 108, 72), (sk_x - 5, sk_y - 26, 10, 6))
        pygame.draw.ellipse(surface, (90, 70, 42), (sk_x - 5, sk_y - 26, 10, 6), 1)

    # ── Wheat sheaves leaning on wall (left side) ──
    for wsi in range(4):
        lean = (wsi - 1.5) * 5
        wx5 = x - 172 + wsi * 14
        stalk_c = (188 + wsi * 5, 158 + wsi * 4, 58)
        pygame.draw.line(surface, stalk_c, (wx5, ground - 6), (wx5 + int(lean), ground - 56), 2)
        for gj2 in range(4):
            gx5 = wx5 + int(lean) + int(math.sin(gj2 * 0.8) * 4)
            gy5 = ground - 56 - gj2 * 8
            pygame.draw.ellipse(surface, (210, 176, 64), (gx5 - 3, gy5 - 5, 6, 9))
            pygame.draw.ellipse(surface, (152, 118, 36), (gx5 - 3, gy5 - 5, 6, 9), 1)
    pygame.draw.line(surface, (130, 96, 32), (x - 176, ground - 28), (x - 148, ground - 28), 2)

    # ── Weighing scale (right side of door) ──
    sc_x = x + 34
    sc_y = ground - 36
    pygame.draw.line(surface, (90, 68, 36), (sc_x, sc_y), (sc_x, sc_y - 30), 2)
    pygame.draw.line(surface, (90, 68, 36), (sc_x - 20, sc_y - 30), (sc_x + 20, sc_y - 30), 2)
    pygame.draw.circle(surface, (110, 84, 48), (sc_x, sc_y - 30), 3)
    wobble = int(math.sin(ticks * 0.001 + seed) * 4)
    pygame.draw.line(surface, (80, 60, 30), (sc_x - 20, sc_y - 30), (sc_x - 20, sc_y - 16 + wobble), 1)
    pygame.draw.line(surface, (80, 60, 30), (sc_x + 20, sc_y - 30), (sc_x + 20, sc_y - 16 - wobble), 1)
    pygame.draw.ellipse(surface, (162, 140, 100), (sc_x - 26, sc_y - 20 + wobble, 12, 5))
    pygame.draw.ellipse(surface, (162, 140, 100), (sc_x + 14, sc_y - 20 - wobble, 12, 5))
    pygame.draw.rect(surface, (80, 60, 32), (sc_x - 4, sc_y - 6, 8, 6))

    # ── Long wooden workbench (left, near oven) ──
    bench = pygame.Rect(x - 186, ground - 24, 80, 18)
    pygame.draw.rect(surface, (96, 70, 40), bench, border_radius=2)
    pygame.draw.rect(surface, (134, 100, 58), bench, 1, border_radius=2)
    for wg3 in range(5):
        pygame.draw.line(surface, (80, 58, 30), (bench.left + 4 + wg3 * 16, bench.top + 2),
                         (bench.left + 2 + wg3 * 16, bench.bottom - 2), 1)
    pygame.draw.line(surface, (80, 58, 30), (bench.left + 6, bench.bottom), (bench.left + 6, ground - 4), 2)
    pygame.draw.line(surface, (80, 58, 30), (bench.right - 6, bench.bottom), (bench.right - 6, ground - 4), 2)
    # items on workbench: sieve + small bowl
    pygame.draw.ellipse(surface, (160, 138, 100), (bench.left + 8, bench.top - 6, 22, 8))
    pygame.draw.ellipse(surface, (110, 88, 60), (bench.left + 8, bench.top - 6, 22, 8), 1)
    for se_i in range(4):
        pygame.draw.line(surface, (120, 100, 70),
                         (bench.left + 11 + se_i * 5, bench.top - 4),
                         (bench.left + 11 + se_i * 5, bench.top + 1), 1)
    pygame.draw.arc(surface, (130, 100, 60), (bench.left + 36, bench.top - 7, 16, 8), 0, math.pi, 2)

    # ════════════════════════════════════════════════════
    # VFX & PARTICLES
    # ════════════════════════════════════════════════════

    # ── Chimney smoke (dusty, grey-brown) ──
    for i in range(10):
        t = ticks * 0.0007 + seed * 0.06 + i * 0.85
        sx_c = chim_rect.centerx + math.sin(t * 1.2 + i) * (5 + i * 2)
        sy_c = chim_rect.top - 6 - (t * 11 + i * 9) % 50
        sz_c = 10 + i * 4
        sa_c = max(0, int(85 - i * 6))
        sc_s = pygame.Surface((sz_c, sz_c), pygame.SRCALPHA)
        pygame.draw.ellipse(sc_s, (160 + i * 4, 148 + i * 3, 126 + i * 2, sa_c), sc_s.get_rect())
        surface.blit(sc_s, (int(sx_c) - sz_c // 2, int(sy_c) - sz_c // 2))

    # ── Flour dust cloud (fine white motes rising from millstone area) ──
    for i in range(20):
        t = ticks * 0.0005 + seed * 0.14 + i * 0.36
        fl_life = (t * 3 + i * 1.1) % 1.0
        fl_x = ms2_x - 20 + int((i / 19) * 80) + int(math.sin(t * 1.8 + i) * 10)
        fl_y = ms2_y - 12 - int(fl_life * 60)
        fl_a = int(120 * math.sin(fl_life * math.pi))
        if fl_a > 10:
            fl_s = pygame.Surface((4, 4), pygame.SRCALPHA)
            pygame.draw.circle(fl_s, (240, 236, 226, fl_a), (2, 2), 1)
            surface.blit(fl_s, (fl_x - 2, fl_y - 2))

    # ── Grain chaff motes (golden, drifting across whole shop) ──
    for i in range(14):
        t = ticks * 0.0004 + seed * 0.2 + i * 0.47
        ch_life = (t * 2.5 + i * 0.9) % 1.0
        ch_x = x - 160 + int((i / 13) * 320) + int(math.sin(t * 1.3 + i) * 16)
        ch_y = ground - 10 - int(ch_life * 110)
        ch_a = int(130 * math.sin(ch_life * math.pi))
        if ch_a > 10:
            ch_s = pygame.Surface((4, 4), pygame.SRCALPHA)
            pygame.draw.circle(ch_s, (210, 182, 80, ch_a), (2, 2), 1)
            surface.blit(ch_s, (ch_x - 2, ch_y - 2))

    # ── Windmill sail motion blur (faint arc sweep) ──
    for blur_i in range(3):
        blur_angle = sail_angle - blur_i * 0.04
        ba2 = max(0, 18 - blur_i * 6)
        for si2 in range(4):
            a2 = blur_angle + si2 * (math.pi / 2)
            bx2 = mill_cx + int(math.cos(a2) * sail_arm)
            by2 = mill_cy + int(math.sin(a2) * sail_arm)
            blur_s = pygame.Surface((4, 4), pygame.SRCALPHA)
            pygame.draw.circle(blur_s, (180, 160, 120, ba2), (2, 2), 2)
            surface.blit(blur_s, (bx2 - 2, by2 - 2), special_flags=pygame.BLEND_RGBA_ADD)


def _draw_tanner_shop(surface: pygame.Surface, pos: Vector2, ticks: int, seed: int) -> None:  # noqa: C901
    x = int(pos.x)
    ground = int(pos.y)
    _rng = lambda v, s=seed: ((v * 2654435761 + s) >> 4) & 0xFFFF  # fast hash

    # ════════════════════════════════════════════════════
    # BUILDING — Tudor half-timber tannery with stone ground floor
    # ════════════════════════════════════════════════════

    # ── Cobblestone yard (tannin-stained, muddy) ──
    yard = pygame.Rect(x - 220, ground - 6, 440, 12)
    for cx in range(yard.left, yard.right - 6, 10):
        for cy2 in range(yard.top, yard.bottom - 4, 8):
            sc = 58 + _rng(cx * 31 + cy2 * 17) % 20
            stain = _rng(cx * 7 + cy2 * 13) % 50
            cr, cg, cb = sc, sc - 4 - stain // 6, sc - 10 - stain // 4
            sw, sh = 8 + _rng(cx * 3 + cy2) % 3, 6 + _rng(cx + cy2 * 5) % 3
            pygame.draw.rect(surface, (max(cr, 30), max(cg, 22), max(cb, 14)), (cx, cy2, sw, sh), border_radius=1)
            pygame.draw.rect(surface, (36, 28, 16), (cx, cy2, sw, sh), 1, border_radius=1)

    # ── Stone foundation (2 courses, stained dark from tannin runoff) ──
    fnd = pygame.Rect(x - 206, ground - 32, 412, 32)
    pygame.draw.rect(surface, (62, 52, 36), fnd)
    for fy in range(2):
        oy = fnd.top + fy * 16
        off = 18 if fy % 2 else 0
        for fx in range(fnd.left + off, fnd.right - 8, 36):
            sc = 58 + _rng(fx * 11 + fy * 7) % 22
            sw2 = 32 + _rng(fx * 3 + fy) % 6
            pygame.draw.rect(surface, (sc, sc - 6, sc - 14), (fx, oy + 1, sw2, 14), border_radius=1)
            pygame.draw.rect(surface, (40, 32, 20), (fx, oy + 1, sw2, 14), 1, border_radius=1)
            # tannin stain drips
            if _rng(fx * 13 + fy * 23) % 5 == 0:
                pygame.draw.line(surface, (44, 34, 18), (fx + sw2 // 2, oy + 12), (fx + sw2 // 2, oy + 16), 1)
    pygame.draw.rect(surface, (40, 32, 20), fnd, 2)

    # ── Ground floor: rough stone wall with tannin stains ──
    gf = pygame.Rect(x - 206, ground - 140, 412, 108)
    pygame.draw.rect(surface, (72, 60, 42), gf)
    # individual stones
    for row in range(6):
        sy = gf.top + 2 + row * 18
        off = 20 if row % 2 else 0
        for sx2 in range(gf.left + 2 + off, gf.right - 10, 40):
            sc = 66 + _rng(sx2 * 7 + row * 19) % 18
            sw2 = 36 + _rng(sx2 * 3 + row) % 6
            pygame.draw.rect(surface, (sc, sc - 6, sc - 14), (sx2, sy, sw2, 16), border_radius=1)
            pygame.draw.rect(surface, (48, 38, 24), (sx2, sy, sw2, 16), 1, border_radius=1)
    # dark tannin stain streaks on lower wall
    for si in range(8):
        sx3 = gf.left + 20 + _rng(si * 31 + 7) % (gf.width - 40)
        sh2 = 16 + _rng(si * 17) % 30
        stain_s = pygame.Surface((6, sh2), pygame.SRCALPHA)
        stain_s.fill((36, 28, 14, 40 + _rng(si * 9) % 30))
        surface.blit(stain_s, (sx3, gf.bottom - sh2 - 4))
    pygame.draw.rect(surface, (40, 32, 20), gf, 2)

    # ── Upper floor: timber frame with wattle-and-daub infill ──
    uf = pygame.Rect(x - 210, ground - 230, 420, 90)
    # daub infill (warm ochre/cream)
    pygame.draw.rect(surface, (148, 128, 92), uf)
    # plaster cracks and aging
    for ci2 in range(12):
        cx3 = uf.left + 10 + _rng(ci2 * 41) % (uf.width - 20)
        cy3 = uf.top + 4 + _rng(ci2 * 23) % (uf.height - 8)
        cl = 8 + _rng(ci2 * 13) % 14
        pygame.draw.line(surface, (120, 104, 72), (cx3, cy3), (cx3 + cl, cy3 + _rng(ci2 * 7) % 6 - 3), 1)
    # exposed wattle patches (shows underlying woven sticks)
    for wi in range(3):
        wx = uf.left + 40 + _rng(wi * 53) % (uf.width - 80)
        wy = uf.top + 10 + _rng(wi * 37) % 50
        ww, wh = 18 + _rng(wi * 11) % 14, 12 + _rng(wi * 19) % 10
        pygame.draw.rect(surface, (92, 74, 48), (wx, wy, ww, wh), border_radius=2)
        for wl in range(3):
            pygame.draw.line(surface, (78, 60, 36), (wx + 2, wy + 3 + wl * 4), (wx + ww - 2, wy + 3 + wl * 4), 1)
    # timber frame beams (dark, aged oak)
    _beam_col = (52, 38, 20)
    _beam_hi = (64, 48, 28)
    _beam_w = 10
    # horizontal beams
    for by in (uf.top, uf.top + uf.height // 2, uf.bottom):
        pygame.draw.rect(surface, _beam_col, (uf.left, by - _beam_w // 2, uf.width, _beam_w))
        pygame.draw.line(surface, _beam_hi, (uf.left, by - _beam_w // 2), (uf.right, by - _beam_w // 2), 1)
        pygame.draw.rect(surface, (36, 26, 12), (uf.left, by - _beam_w // 2, uf.width, _beam_w), 1)
    # vertical posts
    for bx in (uf.left, uf.left + uf.width // 4, uf.centerx, uf.left + 3 * uf.width // 4, uf.right - _beam_w):
        pygame.draw.rect(surface, _beam_col, (bx, uf.top, _beam_w, uf.height))
        pygame.draw.line(surface, _beam_hi, (bx, uf.top), (bx, uf.bottom), 1)
        pygame.draw.rect(surface, (36, 26, 12), (bx, uf.top, _beam_w, uf.height), 1)
    # diagonal braces (St. Andrew's crosses in panels)
    _panels = [(uf.left + _beam_w, uf.top + _beam_w // 2, uf.width // 4 - _beam_w * 2, uf.height // 2 - _beam_w),
               (uf.left + 3 * uf.width // 4 + _beam_w, uf.top + _beam_w // 2, uf.width // 4 - _beam_w * 2, uf.height // 2 - _beam_w)]
    for px, py, pw, ph in _panels:
        pygame.draw.line(surface, _beam_col, (px, py), (px + pw, py + ph), 3)
        pygame.draw.line(surface, _beam_col, (px + pw, py), (px, py + ph), 3)

    # ── Jetty overhang (upper floor protrudes 14px on each side) ──
    jetty_h = 8
    pygame.draw.rect(surface, (58, 44, 24), (uf.left - 4, uf.bottom - jetty_h, uf.width + 8, jetty_h))
    pygame.draw.rect(surface, (36, 26, 12), (uf.left - 4, uf.bottom - jetty_h, uf.width + 8, jetty_h), 1)
    # support corbels under jetty
    for ci3 in range(6):
        cx4 = uf.left + 20 + ci3 * (uf.width - 40) // 5
        pygame.draw.polygon(surface, (56, 42, 22), [(cx4, uf.bottom), (cx4 + 6, uf.bottom), (cx4 + 3, uf.bottom + 10)])
        pygame.draw.polygon(surface, (36, 26, 12), [(cx4, uf.bottom), (cx4 + 6, uf.bottom), (cx4 + 3, uf.bottom + 10)], 1)

    # ── Steep gabled roof with dark weathered shingles ──
    roof_peak_x = x
    roof_peak_y = uf.top - 80
    roof_left = uf.left - 16
    roof_right = uf.right + 16
    roof_eave_y = uf.top + 4
    # roof fill
    pygame.draw.polygon(surface, (46, 36, 22),
                        [(roof_left, roof_eave_y), (roof_peak_x, roof_peak_y), (roof_right, roof_eave_y)])
    # shingle rows
    for row_r in range(14):
        row_frac = row_r / 13
        ry = int(roof_peak_y + row_frac * (roof_eave_y - roof_peak_y))
        rw = int(row_frac * (roof_right - roof_left))
        rx = roof_peak_x - rw // 2
        off_r = 7 if row_r % 2 else 0
        for ti in range(rw // 12 + 1):
            tx = rx + ti * 12 + off_r
            td = 38 + row_r * 2 + _rng(tx * 5 + row_r * 11) % 10
            tw2 = 10 + _rng(tx * 3 + row_r) % 3
            pygame.draw.rect(surface, (td, td - 6, td - 14), (tx, ry, tw2, 10), border_radius=1)
            pygame.draw.rect(surface, (26, 18, 8), (tx, ry, tw2, 10), 1, border_radius=1)
    # moss patches on roof
    for mi in range(6):
        mx = roof_left + 30 + _rng(mi * 67) % (roof_right - roof_left - 60)
        my = uf.top - 20 - _rng(mi * 43) % 40
        ms = pygame.Surface((14, 8), pygame.SRCALPHA)
        ms.fill((48, 72, 34, 50 + _rng(mi * 11) % 40))
        surface.blit(ms, (mx, my))
    # ridge line and finials
    pygame.draw.line(surface, (30, 22, 10), (roof_left, roof_eave_y), (roof_peak_x, roof_peak_y), 3)
    pygame.draw.line(surface, (30, 22, 10), (roof_peak_x, roof_peak_y), (roof_right, roof_eave_y), 3)
    pygame.draw.line(surface, (24, 16, 6), (roof_left, roof_eave_y + 1), (roof_right, roof_eave_y + 1), 3)
    # ridge cap
    pygame.draw.circle(surface, (56, 42, 24), (roof_peak_x, roof_peak_y), 7)
    pygame.draw.circle(surface, (30, 22, 10), (roof_peak_x, roof_peak_y), 7, 1)
    # small iron weathervane at peak — hide shape
    pygame.draw.line(surface, (68, 58, 42), (roof_peak_x, roof_peak_y - 2), (roof_peak_x, roof_peak_y - 22), 2)
    wv_y = roof_peak_y - 20
    wv_pts = [(roof_peak_x - 10, wv_y + 2), (roof_peak_x + 12, wv_y - 2),
              (roof_peak_x + 14, wv_y + 6), (roof_peak_x + 6, wv_y + 10),
              (roof_peak_x - 4, wv_y + 8), (roof_peak_x - 12, wv_y + 6)]
    pygame.draw.polygon(surface, (82, 68, 48), wv_pts)
    pygame.draw.polygon(surface, (48, 38, 22), wv_pts, 1)

    # ── Chimney (brick, sooty, with corbelled cap) ──
    chim_rect = pygame.Rect(x + 70, roof_peak_y + 10, 32, roof_eave_y - roof_peak_y + 20)
    for crow in range(chim_rect.height // 9 + 1):
        cy = chim_rect.top + crow * 9
        off = 7 if crow % 2 else 0
        for ci in range(-1, 4):
            bx = chim_rect.left + ci * 11 + off
            if bx < chim_rect.left - 2 or bx > chim_rect.right - 4:
                continue
            bc = 76 + (crow * 9 + ci * 5 + seed) % 20
            pygame.draw.rect(surface, (bc, bc // 2 + 8, bc // 3 + 6), (bx, cy, 10, 8))
            pygame.draw.rect(surface, (38, 24, 14), (bx, cy, 10, 8), 1)
    pygame.draw.rect(surface, (38, 24, 14), chim_rect, 1)
    # chimney cap (corbelled stone)
    cap = pygame.Rect(chim_rect.left - 5, chim_rect.top - 4, chim_rect.width + 10, 8)
    pygame.draw.rect(surface, (64, 50, 32), cap, border_radius=2)
    pygame.draw.rect(surface, (38, 28, 16), cap, 1, border_radius=2)
    # soot stains above chimney
    for si2 in range(3):
        soot_s = pygame.Surface((8 + si2 * 4, 6), pygame.SRCALPHA)
        soot_s.fill((28, 22, 14, 50 - si2 * 12))
        surface.blit(soot_s, (chim_rect.centerx - 4 - si2 * 2, chim_rect.top - 8 - si2 * 5))

    # ── Upper floor windows (leaded glass, warm glow) ──
    for wi2, wx2 in enumerate((uf.left + uf.width // 4 + 16, uf.centerx + 16)):
        win_r = pygame.Rect(wx2, uf.top + 18, 42, 48)
        pygame.draw.rect(surface, (22, 18, 10), win_r, border_radius=2)
        wp = int(95 + 25 * math.sin(ticks * 0.0009 + wi2 * 1.4 + seed))
        pygame.draw.rect(surface, (wp, wp - 12, wp - 32),
                         (win_r.left + 3, win_r.top + 3, win_r.width - 6, win_r.height - 6))
        # leading (cross pattern)
        pygame.draw.line(surface, (42, 32, 18), (win_r.centerx, win_r.top + 2), (win_r.centerx, win_r.bottom - 2), 2)
        pygame.draw.line(surface, (42, 32, 18), (win_r.left + 2, win_r.centery), (win_r.right - 2, win_r.centery), 2)
        # diamond leading in each pane
        for px2, py2 in [(win_r.left + win_r.width // 4, win_r.top + win_r.height // 4),
                         (win_r.left + 3 * win_r.width // 4, win_r.top + win_r.height // 4),
                         (win_r.left + win_r.width // 4, win_r.top + 3 * win_r.height // 4),
                         (win_r.left + 3 * win_r.width // 4, win_r.top + 3 * win_r.height // 4)]:
            pygame.draw.line(surface, (42, 32, 18), (px2 - 4, py2), (px2 + 4, py2), 1)
            pygame.draw.line(surface, (42, 32, 18), (px2, py2 - 5), (px2, py2 + 5), 1)
        # wooden shutters on sides
        pygame.draw.rect(surface, (56, 42, 22), (win_r.left - 6, win_r.top, 6, win_r.height))
        pygame.draw.rect(surface, (36, 26, 12), (win_r.left - 6, win_r.top, 6, win_r.height), 1)
        pygame.draw.rect(surface, (56, 42, 22), (win_r.right, win_r.top, 6, win_r.height))
        pygame.draw.rect(surface, (36, 26, 12), (win_r.right, win_r.top, 6, win_r.height), 1)
        # shutter iron hinges
        for hy in (win_r.top + 8, win_r.bottom - 12):
            pygame.draw.rect(surface, (44, 36, 22), (win_r.left - 8, hy, 4, 6))
            pygame.draw.rect(surface, (44, 36, 22), (win_r.right + 4, hy, 4, 6))
        pygame.draw.rect(surface, (48, 36, 20), win_r, 2, border_radius=2)

    # ── Ground floor — wide arched doorway (work entrance) ──
    door_w, door_h = 64, 96
    door_rect = pygame.Rect(x - door_w // 2, ground - 32 - door_h, door_w, door_h)
    # stone arch (3 layers)
    for ai in range(3):
        arch_w = door_w + 12 + ai * 8
        arch_h = 24 + ai * 4
        arch_col = (56 + ai * 8, 44 + ai * 6, 28 + ai * 4)
        pygame.draw.ellipse(surface, arch_col, (x - arch_w // 2, door_rect.top - arch_h // 2, arch_w, arch_h))
        pygame.draw.ellipse(surface, (36, 26, 14), (x - arch_w // 2, door_rect.top - arch_h // 2, arch_w, arch_h), 1)
    # keystone
    pygame.draw.polygon(surface, (78, 64, 42), [(x - 8, door_rect.top - 14), (x + 8, door_rect.top - 14),
                                                  (x + 6, door_rect.top - 4), (x - 6, door_rect.top - 4)])
    pygame.draw.polygon(surface, (48, 38, 22), [(x - 8, door_rect.top - 14), (x + 8, door_rect.top - 14),
                                                  (x + 6, door_rect.top - 4), (x - 6, door_rect.top - 4)], 1)
    # dark interior
    pygame.draw.rect(surface, (18, 14, 8), door_rect)
    # heavy oak double doors (slightly ajar)
    left_door = pygame.Rect(door_rect.left + 2, door_rect.top + 2, door_w // 2 - 4, door_h - 4)
    right_door = pygame.Rect(door_rect.centerx + 2, door_rect.top + 2, door_w // 2 - 4, door_h - 4)
    for dr in (left_door, right_door):
        pygame.draw.rect(surface, (46, 34, 18), dr)
        # planks
        for dp in range(dr.left + 2, dr.right - 2, 8):
            pc = 42 + _rng(dp * 7) % 10
            pygame.draw.rect(surface, (pc, pc - 6, pc - 12), (dp, dr.top + 2, 6, dr.height - 4))
            pygame.draw.rect(surface, (32, 24, 12), (dp, dr.top + 2, 6, dr.height - 4), 1)
        # cross braces
        pygame.draw.line(surface, (38, 28, 14), (dr.left + 2, dr.top + dr.height // 3), (dr.right - 2, dr.top + dr.height // 3), 3)
        pygame.draw.line(surface, (38, 28, 14), (dr.left + 2, dr.top + 2 * dr.height // 3), (dr.right - 2, dr.top + 2 * dr.height // 3), 3)
        pygame.draw.rect(surface, (32, 24, 12), dr, 1)
    # iron strap hinges
    for hy2 in (door_rect.top + 20, door_rect.centery, door_rect.bottom - 24):
        pygame.draw.rect(surface, (58, 48, 32), (door_rect.left - 2, hy2, 10, 4), border_radius=1)
        pygame.draw.rect(surface, (58, 48, 32), (door_rect.right - 8, hy2, 10, 4), border_radius=1)
    # iron ring handles
    for hx2 in (left_door.right - 6, right_door.left + 4):
        pygame.draw.circle(surface, (72, 58, 38), (hx2, door_rect.centery), 5, 2)
        pygame.draw.circle(surface, (48, 38, 24), (hx2, door_rect.centery - 6), 2)
    pygame.draw.rect(surface, (40, 30, 16), door_rect, 2)

    # ── Ground floor windows (small, barred — ventilation for fumes) ──
    for wi3, wx3 in enumerate((gf.left + 24, gf.right - 66)):
        win2 = pygame.Rect(wx3, gf.top + 24, 42, 32)
        pygame.draw.rect(surface, (22, 16, 8), win2, border_radius=2)
        wp2 = int(72 + 16 * math.sin(ticks * 0.0008 + wi3 * 2.1 + seed))
        pygame.draw.rect(surface, (wp2, wp2 - 6, wp2 - 18),
                         (win2.left + 3, win2.top + 3, win2.width - 6, win2.height - 6))
        # iron bars (ventilation, keep out animals)
        for bar in range(4):
            bx2 = win2.left + 6 + bar * 10
            pygame.draw.line(surface, (62, 50, 34), (bx2, win2.top + 2), (bx2, win2.bottom - 2), 2)
        pygame.draw.line(surface, (62, 50, 34), (win2.left + 2, win2.centery), (win2.right - 2, win2.centery), 2)
        pygame.draw.rect(surface, (48, 36, 20), win2, 2, border_radius=2)
        # stone sill
        pygame.draw.rect(surface, (68, 56, 38), (win2.left - 3, win2.bottom, win2.width + 6, 5), border_radius=1)
        pygame.draw.rect(surface, (42, 32, 18), (win2.left - 3, win2.bottom, win2.width + 6, 5), 1, border_radius=1)

    # ── Hanging wooden sign (hide silhouette) ──
    sign_arm_x = gf.right + 6
    sign_arm_y = gf.top + 20
    # iron bracket
    pygame.draw.line(surface, (64, 50, 32), (gf.right, sign_arm_y), (sign_arm_x + 28, sign_arm_y), 3)
    pygame.draw.line(surface, (64, 50, 32), (gf.right, sign_arm_y + 14), (sign_arm_x + 12, sign_arm_y), 2)
    # chains
    pygame.draw.line(surface, (80, 66, 44), (sign_arm_x + 6, sign_arm_y), (sign_arm_x + 6, sign_arm_y + 14), 1)
    pygame.draw.line(surface, (80, 66, 44), (sign_arm_x + 22, sign_arm_y), (sign_arm_x + 22, sign_arm_y + 14), 1)
    sboard = pygame.Rect(sign_arm_x - 2, sign_arm_y + 14, 36, 28)
    sway_sign = math.sin(ticks * 0.0006 + seed * 0.3) * 1.5
    pygame.draw.rect(surface, (58, 44, 24), sboard, border_radius=3)
    pygame.draw.rect(surface, (86, 66, 38), sboard, 1, border_radius=3)
    # hide silhouette on sign
    hide_cx, hide_cy = sboard.centerx + int(sway_sign), sboard.centery
    h_pts = [(hide_cx - 8, hide_cy - 6), (hide_cx + 10, hide_cy - 4), (hide_cx + 12, hide_cy + 4),
             (hide_cx + 4, hide_cy + 8), (hide_cx - 6, hide_cy + 6), (hide_cx - 10, hide_cy)]
    pygame.draw.polygon(surface, (110, 80, 42), h_pts)
    pygame.draw.polygon(surface, (72, 50, 26), h_pts, 1)

    # ── Drying beam with support posts (front of building, prominent) ──
    beam_y = ground - 180
    post_left, post_right = x - 190, x + 190
    # wooden posts (thick, darkened)
    for px3 in (post_left, post_left + 120, post_right - 120, post_right):
        pygame.draw.rect(surface, (54, 40, 22), (px3 - 5, beam_y - 4, 10, ground - beam_y + 4))
        pygame.draw.rect(surface, (38, 28, 14), (px3 - 5, beam_y - 4, 10, ground - beam_y + 4), 1)
        # post caps
        pygame.draw.rect(surface, (62, 46, 26), (px3 - 7, beam_y - 8, 14, 8), border_radius=2)
    # main beam
    pygame.draw.rect(surface, (58, 44, 24), (post_left - 2, beam_y - 4, post_right - post_left + 4, 8))
    pygame.draw.rect(surface, (36, 26, 12), (post_left - 2, beam_y - 4, post_right - post_left + 4, 8), 1)
    # diagonal braces
    for bpx in (post_left, post_right):
        dx_sign = 1 if bpx == post_left else -1
        pygame.draw.line(surface, (50, 38, 20), (bpx, beam_y + 4), (bpx + dx_sign * 24, beam_y + 36), 3)

    # ── Hides hanging from beam (9 hides, varied stages and sway) ──
    _hide_stages = [0, 1, 2, 1, 0, 2, 0, 1, 2]
    for hi in range(9):
        hx = post_left + 16 + hi * 42
        sway_h = math.sin(ticks * 0.0006 + hi * 1.1 + seed) * 4
        hide_stage = _hide_stages[hi]
        # rope
        rope_bottom = beam_y + 16
        pygame.draw.line(surface, (90, 70, 40), (hx, beam_y + 4), (hx + int(sway_h * 0.3), rope_bottom), 2)
        # wooden peg at top
        pygame.draw.circle(surface, (72, 56, 32), (hx, beam_y + 4), 3)
        hx2 = hx + int(sway_h)
        hy2 = rope_bottom
        if hide_stage == 0:  # raw (yellowish, thick)
            hide_col = (172, 142, 92)
            hw, hh = 20, 52
        elif hide_stage == 1:  # mid-tan (rich brown)
            hide_col = (124, 90, 54)
            hw, hh = 18, 48
        else:  # cured (dark leather)
            hide_col = (82, 58, 32)
            hw, hh = 16, 44
        pts_h = [(hx2 - hw // 2, hy2), (hx2 + hw // 2 + 2, hy2 + 6), (hx2 + hw // 2 + 4, hy2 + hh - 8),
                 (hx2 + 4, hy2 + hh), (hx2 - 6, hy2 + hh - 4), (hx2 - hw // 2 - 2, hy2 + hh // 2)]
        pygame.draw.polygon(surface, hide_col, pts_h)
        # texture lines on raw hides
        if hide_stage == 0:
            for vl in range(4):
                pygame.draw.line(surface, (152, 122, 76),
                                 (hx2 - 6 + vl * 5, hy2 + 10), (hx2 - 4 + vl * 6, hy2 + hh - 14), 1)
        # stretch marks on cured hides
        elif hide_stage == 2:
            for sl in range(3):
                pygame.draw.line(surface, (68, 46, 24),
                                 (hx2 - 4 + sl * 4, hy2 + 8), (hx2 - 2 + sl * 5, hy2 + hh - 10), 1)
        pygame.draw.polygon(surface, (hide_col[0] - 28, hide_col[1] - 20, max(hide_col[2] - 14, 8)), pts_h, 1)

    # ════════════════════════════════════════════════════
    # PROPS & FURNITURE
    # ════════════════════════════════════════════════════

    # ── Five tanning vats (large, wooden, with iron bands) ──
    vat_positions = [x - 160, x - 90, x - 20, x + 50, x + 120]
    for vi, vat_cx in enumerate(vat_positions):
        vat_w = 48
        vat_d = 30 + vi % 3 * 2
        vr = pygame.Rect(vat_cx - vat_w // 2, ground - vat_d, vat_w, vat_d)
        # wooden staves
        for sv in range(vr.left, vr.right - 3, 6):
            sc2 = 60 + _rng(sv * 7 + vi * 13) % 16
            pygame.draw.rect(surface, (sc2, sc2 - 8, sc2 - 18), (sv, vr.top, 5, vr.height), border_radius=1)
        # iron hoops
        for hy3 in (vr.top + 4, vr.centery, vr.bottom - 5):
            pygame.draw.rect(surface, (50, 42, 30), (vr.left - 2, hy3, vr.width + 4, 3), border_radius=1)
            pygame.draw.rect(surface, (36, 28, 16), (vr.left - 2, hy3, vr.width + 4, 3), 1, border_radius=1)
        # tannin liquid (different stages per vat)
        liq_pulse = int(math.sin(ticks * 0.002 + vi * 1.6 + seed) * 2)
        liq_y = ground - 10 + liq_pulse
        liq_cols = [(72, 56, 28), (58, 44, 18), (48, 36, 14), (64, 50, 24), (54, 40, 16)]
        liq_col = liq_cols[vi % 5]
        pygame.draw.ellipse(surface, liq_col, (vr.left + 3, liq_y - 4, vr.width - 6, 8))
        pygame.draw.ellipse(surface, (36, 26, 10), (vr.left + 3, liq_y - 4, vr.width - 6, 8), 1)
        # hide peeking out of liquid
        sub_sway = int(math.sin(ticks * 0.0004 + vi * 2.3 + seed) * 2)
        hide_in_vat = (104 + vi * 6, 74 + vi * 4, 38 + vi * 3)
        pygame.draw.ellipse(surface, hide_in_vat,
                            (vat_cx - 10 + sub_sway, liq_y - 6, 20, 8))
        pygame.draw.ellipse(surface, (liq_col[0] - 10, liq_col[1] - 8, liq_col[2] - 4),
                            (vat_cx - 10 + sub_sway, liq_y - 6, 20, 8), 1)
        pygame.draw.rect(surface, (40, 30, 16), vr, 1, border_radius=2)

    # ── Bark pit (sunken pit with oak bark for tanning liquor) ──
    bark_x = x + 170
    pit = pygame.Rect(bark_x - 28, ground - 14, 56, 14)
    pygame.draw.rect(surface, (42, 32, 16), pit, border_radius=2)
    pygame.draw.rect(surface, (32, 24, 12), pit, 1, border_radius=2)
    for bi in range(8):
        bk_x2 = pit.left + 4 + _rng(bi * 31) % (pit.width - 8)
        bk_y = pit.top + 2 + _rng(bi * 17) % (pit.height - 6)
        bk_c = (78 + _rng(bi * 11) % 16, 56 + _rng(bi * 7) % 12, 28 + _rng(bi * 3) % 8)
        pygame.draw.rect(surface, bk_c, (bk_x2, bk_y, 8 + _rng(bi * 5) % 6, 4), border_radius=1)

    # ── Hide stretching frames (3 large A-frames, right side) ──
    for fr_i in range(3):
        fr_x = x + 140 + fr_i * 32
        fr_y = ground
        fr_h = 80 + fr_i * 8
        # A-frame legs
        pygame.draw.line(surface, (66, 50, 28), (fr_x - 16, fr_y), (fr_x, fr_y - fr_h), 3)
        pygame.draw.line(surface, (66, 50, 28), (fr_x + 16, fr_y), (fr_x, fr_y - fr_h), 3)
        # cross bar
        cb_y = fr_y - fr_h * 2 // 3
        pygame.draw.line(surface, (58, 44, 24), (fr_x - 10, cb_y), (fr_x + 10, cb_y), 2)
        # hide stretched on frame
        hfc = (136 - fr_i * 22, 100 - fr_i * 16, 56 - fr_i * 10)
        pygame.draw.polygon(surface, hfc, [(fr_x - 10, fr_y - fr_h + 8), (fr_x + 10, fr_y - fr_h + 8),
                                            (fr_x + 14, fr_y - 12), (fr_x - 14, fr_y - 12)])
        pygame.draw.polygon(surface, (hfc[0] - 20, hfc[1] - 14, max(hfc[2] - 10, 8)),
                            [(fr_x - 10, fr_y - fr_h + 8), (fr_x + 10, fr_y - fr_h + 8),
                             (fr_x + 14, fr_y - 12), (fr_x - 14, fr_y - 12)], 1)
        # lacing cords
        for lc3 in range(5):
            lc_y2 = fr_y - fr_h + 12 + lc3 * (fr_h - 24) // 4
            pygame.draw.line(surface, (130, 100, 56), (fr_x - 12, lc_y2), (fr_x + 12, lc_y2), 1)

    # ── Fleshing beam with draped hide ──
    fb_x, fb_y = x - 200, ground - 50
    # support posts
    pygame.draw.rect(surface, (62, 46, 26), (fb_x - 4, fb_y - 10, 8, ground - fb_y + 10))
    pygame.draw.rect(surface, (62, 46, 26), (fb_x + 32, fb_y - 4, 8, ground - fb_y + 4))
    # angled beam
    pygame.draw.line(surface, (78, 60, 34), (fb_x, fb_y), (fb_x + 40, fb_y - 18), 5)
    pygame.draw.line(surface, (58, 44, 24), (fb_x, fb_y), (fb_x + 40, fb_y - 18), 1)
    # hide draped over
    pygame.draw.ellipse(surface, (158, 122, 72), (fb_x - 4, fb_y - 28, 34, 38))
    pygame.draw.ellipse(surface, (108, 80, 44), (fb_x - 4, fb_y - 28, 34, 38), 1)
    # scraper and fleshing knife leaning against beam
    pygame.draw.line(surface, (100, 82, 50), (fb_x + 42, fb_y - 16), (fb_x + 52, fb_y + 8), 2)
    pygame.draw.ellipse(surface, (164, 148, 112), (fb_x + 48, fb_y + 4, 12, 6))

    # ── Stacked raw hides (pile near door) ──
    pile_x = x - 60
    for ph_i in range(5):
        ph_y = ground - 6 - ph_i * 6
        ph_w = 36 - ph_i * 3
        ph_c = (152 + ph_i * 5, 116 + ph_i * 4, 64 + ph_i * 3)
        pygame.draw.ellipse(surface, ph_c, (pile_x - ph_w // 2 + ph_i, ph_y - 5, ph_w, 8))
        pygame.draw.ellipse(surface, (100, 74, 40), (pile_x - ph_w // 2 + ph_i, ph_y - 5, ph_w, 8), 1)

    # ── Tanning tools on a wall-mounted rack ──
    rack_x, rack_y = gf.left + 10, gf.top + 60
    pygame.draw.rect(surface, (56, 42, 24), (rack_x, rack_y, 6, 50))
    pygame.draw.rect(surface, (56, 42, 24), (rack_x + 30, rack_y, 6, 50))
    pygame.draw.rect(surface, (62, 48, 28), (rack_x - 2, rack_y + 10, 40, 4))
    pygame.draw.rect(surface, (62, 48, 28), (rack_x - 2, rack_y + 30, 40, 4))
    # tools hanging: paddle, scraper, knife
    pygame.draw.line(surface, (88, 68, 38), (rack_x + 6, rack_y + 12), (rack_x + 6, rack_y + 44), 2)
    pygame.draw.rect(surface, (104, 84, 48), (rack_x + 3, rack_y + 40, 8, 6), border_radius=1)
    pygame.draw.line(surface, (78, 58, 32), (rack_x + 16, rack_y + 12), (rack_x + 16, rack_y + 38), 2)
    pygame.draw.ellipse(surface, (148, 132, 100), (rack_x + 13, rack_y + 34, 8, 5))
    pygame.draw.line(surface, (72, 54, 28), (rack_x + 26, rack_y + 12), (rack_x + 26, rack_y + 36), 2)
    pygame.draw.rect(surface, (90, 72, 42), (rack_x + 24, rack_y + 32, 6, 8), border_radius=1)

    # ── Water trough (for rinsing) ──
    trough_x = x + 64
    trough = pygame.Rect(trough_x - 24, ground - 16, 48, 16)
    pygame.draw.rect(surface, (58, 46, 28), trough, border_radius=2)
    pygame.draw.rect(surface, (40, 32, 18), trough, 1, border_radius=2)
    # water surface
    water_shimmer = int(math.sin(ticks * 0.003 + seed) * 6)
    pygame.draw.ellipse(surface, (48, 58, 72), (trough.left + 4, trough.top + 3, trough.width - 8, 8))
    pygame.draw.ellipse(surface, (62, 74, 88), (trough.left + 10 + water_shimmer, trough.top + 4, 16, 5))

    # ════════════════════════════════════════════════════
    # VFX & PARTICLES
    # ════════════════════════════════════════════════════

    # ── Chimney smoke (thick, dark sooty plumes) ──
    for i in range(14):
        t = ticks * 0.0006 + seed * 0.06 + i * 0.7
        sx_c = chim_rect.centerx + math.sin(t * 1.1 + i) * (4 + i * 2.5)
        sy_c = chim_rect.top - 8 - (t * 14 + i * 8) % 60
        sz_c = 8 + i * 4
        sa_c = max(0, int(90 - i * 5))
        if sa_c > 6:
            sc_s = pygame.Surface((sz_c, sz_c), pygame.SRCALPHA)
            pygame.draw.ellipse(sc_s, (54 + i * 2, 46 + i * 2, 36 + i, sa_c), sc_s.get_rect())
            surface.blit(sc_s, (int(sx_c) - sz_c // 2, int(sy_c) - sz_c // 2))

    # ── Tannin vat steam (murky, acrid-looking) ──
    for vi2, vat_cx2 in enumerate(vat_positions):
        for i in range(4):
            t = ticks * 0.0007 + seed * 0.11 + i * 0.8 + vi2 * 1.9
            st_life = (t * 3.5 + i * 0.9) % 1.0
            st_x = vat_cx2 - 8 + int((i / 3) * 16) + int(math.sin(t * 1.6 + i) * 4)
            st_y = ground - 16 - int(st_life * 28)
            st_a = int(70 * math.sin(st_life * math.pi))
            if st_a > 8:
                sts = pygame.Surface((10, 10), pygame.SRCALPHA)
                pygame.draw.ellipse(sts, (62, 52, 34, st_a), (0, 0, 10, 10))
                surface.blit(sts, (st_x - 5, st_y - 5))

    # ── Tannin dust motes (earthy, brown) ──
    for i in range(16):
        t = ticks * 0.0004 + seed * 0.17 + i * 0.42
        dm_life = (t * 2.2 + i * 0.85) % 1.0
        dm_x = x - 200 + int((i / 15) * 400) + int(math.sin(t * 1.3 + i) * 16)
        dm_y = ground - 10 - int(dm_life * 100)
        dm_a = int(90 * math.sin(dm_life * math.pi))
        if dm_a > 10:
            dms = pygame.Surface((4, 4), pygame.SRCALPHA)
            pygame.draw.circle(dms, (86, 66, 34, dm_a), (2, 2), 2)
            surface.blit(dms, (dm_x - 2, dm_y - 2))

    # ── Flies buzzing around hides ──
    for fi5 in range(6):
        ft = ticks * 0.004 + fi5 * 1.7 + seed * 0.3
        fly_x = x - 140 + fi5 * 60 + int(math.sin(ft * 2.3) * 14)
        fly_y = beam_y + 30 + int(math.cos(ft * 1.8 + fi5) * 18)
        pygame.draw.circle(surface, (28, 22, 14), (fly_x, fly_y), 1)


def _draw_cooper_shop(surface: pygame.Surface, pos: Vector2, ticks: int, seed: int) -> None:
    x = int(pos.x)
    ground = int(pos.y)
    _draw_barrel_icon(surface, x - 30, ground - 8)
    _draw_barrel_icon(surface, x - 8, ground - 12)
    _draw_barrel_icon(surface, x + 16, ground - 8)
