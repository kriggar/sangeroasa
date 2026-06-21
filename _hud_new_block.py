# ─── HUD ornate globe frame cache (static brass/iron/gold art, built once) ──
_HUD_ORB_R = 60
_HUD_FRAME_CACHE: Dict[str, pygame.Surface] = {}

_HUD_GLOBE_STYLES: Dict[str, Dict[str, Tuple[int, int, int]]] = {
    "hp": {
        "top":    (255, 124,  96),
        "mid":    (198,  32,  32),
        "bot":    ( 70,   8,  12),
        "aura":   (230,  50,  40),
        "jewel":  (255,  80,  60),
        "jewelD": (120,  10,  10),
        "text":   (252, 232, 212),
    },
    "mp": {
        "top":    (180, 226, 255),
        "mid":    ( 60, 130, 230),
        "bot":    ( 10,  22,  78),
        "aura":   ( 60, 120, 240),
        "jewel":  ( 90, 180, 255),
        "jewelD": ( 20,  40, 120),
        "text":   (222, 238, 255),
    },
}


def _build_hud_globe_frame(style: str) -> pygame.Surface:
    """Build the static multi-ring bronze/gold bezel for one globe style (cached)."""
    cached = _HUD_FRAME_CACHE.get(style)
    if cached is not None:
        return cached
    r = _HUD_ORB_R
    size = r * 2 + 48
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    cx = cy = size // 2
    palette = _HUD_GLOBE_STYLES[style]

    # Multi-ring ornate bezel: iron -> gold -> iron stack
    pygame.draw.circle(surf, (  4,   2,   2), (cx, cy), r + 16, 1)
    pygame.draw.circle(surf, ( 22,  16,  10), (cx, cy), r + 15, 3)
    pygame.draw.circle(surf, ( 50,  36,  20), (cx, cy), r + 12, 4)
    pygame.draw.circle(surf, ( 94,  70,  32), (cx, cy), r +  9, 2)
    pygame.draw.circle(surf, (168, 126,  54), (cx, cy), r +  7, 1)
    pygame.draw.circle(surf, (226, 184,  94), (cx, cy), r +  6, 1)
    pygame.draw.circle(surf, ( 76,  54,  26), (cx, cy), r +  3, 2)
    pygame.draw.circle(surf, (  8,   6,   4), (cx, cy), r +  1, 2)

    # 16 small rivets around the perimeter
    for i in range(16):
        ang = (i / 16) * 2 * math.pi - math.pi / 2
        rx = cx + int((r + 9) * math.cos(ang))
        ry = cy + int((r + 9) * math.sin(ang))
        pygame.draw.circle(surf, (  8,   6,   4), (rx, ry), 3)
        pygame.draw.circle(surf, (178, 136,  60), (rx, ry), 2)
        pygame.draw.circle(surf, (254, 224, 150), (rx - 1, ry - 1), 1)

    # 4 cabochon jewels at cardinal points (larger ornament)
    jewel_col  = palette["jewel"]
    jewel_dark = palette["jewelD"]
    for ang in (-math.pi / 2, 0.0, math.pi / 2, math.pi):
        jx = cx + int((r + 13) * math.cos(ang))
        jy = cy + int((r + 13) * math.sin(ang))
        pygame.draw.circle(surf, (  4,   2,   2), (jx, jy), 8)
        pygame.draw.circle(surf, ( 26,  18,  10), (jx, jy), 7)
        pygame.draw.circle(surf, (158, 118,  52), (jx, jy), 7, 1)
        pygame.draw.circle(surf, (216, 168,  72), (jx, jy), 6, 1)
        pygame.draw.circle(surf, jewel_dark,      (jx, jy), 5)
        pygame.draw.circle(surf, jewel_col,       (jx, jy), 4)
        pygame.draw.circle(surf, (255, 255, 255), (jx - 1, jy - 1), 1)

    _HUD_FRAME_CACHE[style] = surf.convert_alpha()
    return _HUD_FRAME_CACHE[style]


def _draw_hud_globe(
    screen: pygame.Surface,
    center: Tuple[int, int],
    ratio: float,
    style: str,
    value_text: str,
    seed: int,
    tiny_font: pygame.font.Font,
    extra_pulse: float = 0.0,
    flash: float = 0.0,
) -> None:
    """Render one ornate Diablo II style globe with full VFX at `center`.

    Draws pulsing aura, dark socket, 3-stop gradient liquid fill with rising
    bubbles + caustic shimmer + wavy meniscus, glass dome highlights, cached
    multi-ring bezel with rivets and cabochon jewels, and a value text plaque.
    """
    ticks = pygame.time.get_ticks()
    t_sec = ticks / 1000.0
    orb_r = _HUD_ORB_R
    cx, cy = center
    size = orb_r * 2 + 2
    palette = _HUD_GLOBE_STYLES[style]
    fill_top = palette["top"]
    fill_mid = palette["mid"]
    fill_bot = palette["bot"]
    aura_col = palette["aura"]
    text_col = palette["text"]

    # ── Pulsing outer aura (breath + low-resource pulse + damage/spend flash) ──
    aura_outer = orb_r + 34
    _aura_surf = pygame.Surface((aura_outer * 2 + 4, aura_outer * 2 + 4), pygame.SRCALPHA)
    _aacx = _aacy = _aura_surf.get_width() // 2
    _breath = 0.55 + 0.45 * (0.5 + 0.5 * math.sin(t_sec * 1.3 + seed))
    _pulse = min(2.2, _breath + extra_pulse * 1.3 + flash * 0.9)
    _base_a = int(60 * _pulse)
    for _rr in range(aura_outer, orb_r - 2, -1):
        _falloff = (_rr - (orb_r - 2)) / max(1, aura_outer - (orb_r - 2))
        _a = int(((1.0 - _falloff) ** 2.1) * _base_a)
        if _a > 0:
            pygame.draw.circle(_aura_surf, (*aura_col, _a), (_aacx, _aacy), _rr)
    screen.blit(_aura_surf, (cx - _aacx, cy - _aacy))

    # ── Dark socket (empty well) ──
    pygame.draw.circle(screen, ( 8,  4,  6), (cx, cy), orb_r)
    pygame.draw.circle(screen, (20, 12, 18), (cx, cy), orb_r - 2)
    pygame.draw.circle(screen, (28, 18, 24), (cx, cy), orb_r - 4)

    # ── Liquid fill drawn offscreen then masked to the circle ──
    orb_surf = pygame.Surface((size, size), pygame.SRCALPHA)
    local_top_y = size
    if ratio > 0.0:
        fill_h = int(orb_r * 2 * ratio)
        local_top_y = size - fill_h
        # 3-stop vertical gradient
        for yy in range(local_top_y, size):
            _tt = (yy - local_top_y) / max(1, fill_h - 1)
            if _tt < 0.5:
                t2 = _tt * 2
                c = (
                    int(fill_top[0] + (fill_mid[0] - fill_top[0]) * t2),
                    int(fill_top[1] + (fill_mid[1] - fill_top[1]) * t2),
                    int(fill_top[2] + (fill_mid[2] - fill_top[2]) * t2),
                )
            else:
                t2 = (_tt - 0.5) * 2
                c = (
                    int(fill_mid[0] + (fill_bot[0] - fill_mid[0]) * t2),
                    int(fill_mid[1] + (fill_bot[1] - fill_mid[1]) * t2),
                    int(fill_mid[2] + (fill_bot[2] - fill_mid[2]) * t2),
                )
            pygame.draw.line(orb_surf, (*c, 255), (0, yy), (size, yy))

        # Saturated core highlight band near the top of the fill
        core_top = local_top_y + 4
        core_bot = min(size, core_top + max(4, int(fill_h * 0.22)))
        for yy in range(core_top, core_bot):
            _ta = (yy - core_top) / max(1, core_bot - core_top - 1)
            _a = int(50 * (1 - _ta))
            if _a > 0:
                pygame.draw.line(orb_surf, (255, 255, 255, _a), (6, yy), (size - 6, yy))

        # Wavy meniscus (cut + bright highlight line)
        if ratio < 1.0:
            wave_poly: List[Tuple[int, int]] = [(-2, -2)]
            for x in range(0, size + 3, 2):
                wy = local_top_y + int(2.8 * math.sin((x * 0.13) + ticks * 0.004 + seed * 1.7))
                wave_poly.append((x, wy))
            wave_poly.append((size + 2, -2))
            pygame.draw.polygon(orb_surf, (0, 0, 0, 0), wave_poly)
            for x in range(0, size, 2):
                wy = local_top_y + int(2.8 * math.sin((x * 0.13) + ticks * 0.004 + seed * 1.7))
                if 0 <= wy < size:
                    orb_surf.set_at((x, wy), (255, 245, 225, 230))
                    if wy + 1 < size:
                        orb_surf.set_at((x, wy + 1), (255, 222, 200, 150))

        # Rising bubbles
        for _bi in range(6):
            _phase = ((ticks * 0.00042 + _bi * 0.18 + seed * 0.07) % 1.0)
            _bx_n = 0.25 + 0.5 * (0.5 + 0.5 * math.sin(ticks * 0.0013 + _bi * 2.1 + seed))
            _bx = int(size * _bx_n)
            _rise = max(1, size - local_top_y - 8)
            _by = int(size - 4 - _phase * _rise)
            if _by > local_top_y + 4:
                _br = 2 + (_bi % 2)
                _a = int(200 * (1.0 - _phase * 0.45))
                pygame.draw.circle(orb_surf, (0, 0, 0, int(_a * 0.35)), (_bx, _by), _br + 1, 1)
                pygame.draw.circle(orb_surf, (255, 255, 255, _a), (_bx, _by), _br, 1)
                if 0 <= _bx - 1 < size and 0 <= _by - 1 < size:
                    orb_surf.set_at((_bx - 1, _by - 1), (255, 255, 255, min(255, _a + 40)))

        # Moving caustic streak
        _sp = (ticks * 0.00028 + seed * 0.31) % 1.0
        _sy0 = local_top_y + int((size - local_top_y) * _sp) - 3
        for _dy in range(7):
            _yy = _sy0 + _dy
            if 0 <= _yy < size:
                _bell = math.exp(-((_dy - 3) ** 2) / 3.5)
                _a = int(48 * _bell)
                if _a > 0:
                    pygame.draw.line(orb_surf, (255, 255, 255, _a), (8, _yy), (size - 8, _yy))

    # Mask liquid to circle
    _mask = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.circle(_mask, (255, 255, 255, 255), (size // 2, size // 2), orb_r - 1)
    orb_surf.blit(_mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    screen.blit(orb_surf, (cx - size // 2, cy - size // 2))

    # ── Glass dome highlights clipped to circle ──
    dome = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.ellipse(dome, (255, 255, 255, 44),
        pygame.Rect(orb_r - int(orb_r * 0.75), orb_r - int(orb_r * 0.92),
                    int(orb_r * 1.5), int(orb_r * 0.95)))
    pygame.draw.ellipse(dome, (255, 255, 255, 92),
        pygame.Rect(orb_r - int(orb_r * 0.42), orb_r - int(orb_r * 0.76),
                    int(orb_r * 0.85), int(orb_r * 0.52)))
    pygame.draw.ellipse(dome, (255, 255, 255, 175),
        pygame.Rect(orb_r - int(orb_r * 0.18), orb_r - int(orb_r * 0.66),
                    int(orb_r * 0.36), int(orb_r * 0.2)))
    pygame.draw.ellipse(dome, (0, 0, 0, 55),
        pygame.Rect(2, orb_r + int(orb_r * 0.45), size - 4, int(orb_r * 0.8)))
    dome.blit(_mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    screen.blit(dome, (cx - size // 2, cy - size // 2))

    # ── Ornate static frame (cached) ──
    frame = _build_hud_globe_frame(style)
    fw, fh = frame.get_size()
    screen.blit(frame, (cx - fw // 2, cy - fh // 2))

    # ── Value text centered on the globe (over the liquid) ──
    _vs = tiny_font.render(value_text, True, text_col)
    _vs_sh = tiny_font.render(value_text, True, (0, 0, 0))
    _vw, _vh = _vs.get_size()
    _vx = cx - _vw // 2
    _vy = cy - _vh // 2
    screen.blit(_vs_sh, (_vx + 1, _vy + 1))
    screen.blit(_vs, (_vx, _vy))


def draw_player_resource_bars(
    screen: pygame.Surface,
    hp: float,
    max_hp: float,
    mana: float,
    max_mana: float,
    _ui_font: pygame.font.Font,
    tiny_font: pygame.font.Font,
    gold: int = 0,
    player_level: int = 1,
    xp: float = 0.0,
    xp_to_next: float = 100.0,
) -> None:
    """Deprecated — HP/MP globes, level medallion, gold plaque and XP strip are
    now drawn inside the unified ornate action belt by draw_spell_bar(). This
    stub remains for backwards compatibility and is a no-op."""
    return None
