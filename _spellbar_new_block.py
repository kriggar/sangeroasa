def draw_spell_bar(
    screen: pygame.Surface,
    spellbook: List[Dict[str, object]],
    spell_icons: Dict[str, pygame.Surface],
    cooldowns: Dict[str, float],
    unlocked_skills: Set[str],
    current_mana: float,
    selected_idx: int,
    font: pygame.font.Font,
    small_font: pygame.font.Font,
    class_id: str = "",
    max_mana: float = 200.0,
    spell_global_cooldown: float = 0.0,
    global_cd_max: float = 0.5,
    keybinds: Optional[List[int]] = None,
    keybind_editing: int = -1,
    hp: float = 0.0,
    max_hp: float = 0.0,
    gold: int = 0,
    player_level: int = 1,
    xp: float = 0.0,
    xp_to_next: float = 100.0,
) -> List[pygame.Rect]:
    """Unified ornate action belt.

    Multi-ring bronze/gold panel with an embedded HP globe (left) and mana globe
    (right), a row of ornate spell slots flanked by the class passive, class-tinted
    selection and cooldown overlays, a level medallion with laurel wreath above
    the HP globe, a coin-stamped gold plaque above the mana globe, and a
    segmented XP strip with shimmer sweep inside the central channel. Tracks
    damage/spend flash + low-resource pulse state across frames.
    """
    passive = class_passive_data(class_id)
    passive_effects = class_passive_effects(class_id)
    passive_mana_mult = max(0.1, float(passive_effects.get("mana_cost_mult", 1.0)))

    _pal = CLASS_PALETTES.get(class_id, CLASS_PALETTES["default"])
    accent = _pal["primary"]

    visible_slots: List[Tuple[int, Dict[str, object]]] = []
    for idx, spell in enumerate(spellbook):
        if str(spell.get("skill", "")) in unlocked_skills:
            visible_slots.append((idx, spell))
    slot_count = len(visible_slots)

    ticks = pygame.time.get_ticks()
    t_sec = ticks / 1000.0

    # ── State tracking: damage/spend flashes, level pop, xp flash ──
    _last_tick = _HUD_STATE["last_tick_ms"]
    dt = clamp(t_sec - _last_tick, 0.0, 0.1) if _last_tick > 0 else 0.016
    _HUD_STATE["last_tick_ms"] = t_sec
    _last_hp = _HUD_STATE["last_hp"]
    _last_mp = _HUD_STATE["last_mana"]
    if _last_hp >= 0 and hp < _last_hp - 0.5:
        _HUD_STATE["hp_flash"] = 1.0
    if _last_mp >= 0 and current_mana < _last_mp - 0.5:
        _HUD_STATE["mp_flash"] = 1.0
    _HUD_STATE["last_hp"] = float(hp)
    _HUD_STATE["last_mana"] = float(current_mana)
    _HUD_STATE["hp_flash"] = max(0.0, _HUD_STATE["hp_flash"] - dt * 2.4)
    _HUD_STATE["mp_flash"] = max(0.0, _HUD_STATE["mp_flash"] - dt * 2.4)
    if _HUD_STATE["last_level"] >= 0 and player_level > _HUD_STATE["last_level"]:
        _HUD_STATE["level_pop"] = 1.0
    _HUD_STATE["last_level"] = float(player_level)
    _HUD_STATE["level_pop"] = max(0.0, _HUD_STATE["level_pop"] - dt * 1.0)
    _last_xp = _HUD_STATE["last_xp"]
    if _last_xp >= 0 and xp > _last_xp + 0.01:
        _HUD_STATE["xp_flash"] = 1.0
    _HUD_STATE["last_xp"] = float(xp)
    _HUD_STATE["xp_flash"] = max(0.0, _HUD_STATE["xp_flash"] - dt * 1.6)

    hp_ratio = 0.0 if max_hp <= 0 else clamp(hp / max_hp, 0.0, 1.0)
    mp_ratio = clamp(current_mana / max(1.0, max_mana), 0.0, 1.0)
    xp_ratio = clamp(float(xp) / max(1.0, float(xp_to_next)), 0.0, 1.0)

    low_hp_pulse = 0.0
    if hp_ratio < 0.28:
        low_hp_pulse = (0.5 + 0.5 * math.sin(t_sec * 6.5)) * (1.0 - hp_ratio / 0.28)
    low_mp_pulse = 0.0
    if mp_ratio < 0.18:
        low_mp_pulse = (0.5 + 0.5 * math.sin(t_sec * 5.5)) * (1.0 - mp_ratio / 0.18) * 0.6

    # ── Panel geometry ──
    orb_r = _HUD_ORB_R
    orb_d = orb_r * 2
    slot_size = 64
    slot_gap = 6
    passive_sz = 64

    _strip_w = passive_sz
    if slot_count > 0:
        _strip_w += 12 + slot_count * slot_size + (slot_count - 1) * slot_gap
    else:
        _strip_w += 260

    outer_pad = 20
    inner_pad = 26
    panel_h = 96
    panel_w = 2 * (outer_pad + orb_d + inner_pad) + _strip_w
    panel_x = (SCREEN_WIDTH - panel_w) // 2
    panel_y = SCREEN_HEIGHT - panel_h - 34
    panel = pygame.Rect(panel_x, panel_y, panel_w, panel_h)

    hp_cx = panel.left + outer_pad + orb_r
    mp_cx = panel.right - outer_pad - orb_r
    orb_cy = panel.centery

    mouse_pos = pygame.mouse.get_pos()
    hovered_spell: Optional[Dict[str, object]] = None
    hovered_slot: Optional[pygame.Rect] = None
    hovered_passive = False

    # ── Soft drop shadow beneath panel ──
    _sh = pygame.Surface((panel_w + 16, panel_h + 16), pygame.SRCALPHA)
    pygame.draw.rect(_sh, (0, 0, 0, 140), _sh.get_rect().inflate(-2, -2), border_radius=12)
    screen.blit(_sh, (panel.left - 8, panel.top - 6))

    # ── Ornate multi-ring panel backdrop ──
    _panel_bg = pygame.Surface((panel_w + 2, panel_h + 2), pygame.SRCALPHA)
    _pbgr = _panel_bg.get_rect()
    pygame.draw.rect(_panel_bg, (12, 10, 18, 234), _pbgr, border_radius=10)
    pygame.draw.rect(_panel_bg, ( 58,  40,  18, 255), _pbgr, 3, border_radius=10)
    pygame.draw.rect(_panel_bg, (180, 138,  58, 255), _pbgr.inflate(-4, -4), 2, border_radius=9)
    pygame.draw.rect(_panel_bg, (228, 188, 104, 255), _pbgr.inflate(-6, -6), 1, border_radius=9)
    pygame.draw.rect(_panel_bg, ( 40,  28,  16, 255), _pbgr.inflate(-9, -9), 1, border_radius=8)
    screen.blit(_panel_bg, (panel.left - 1, panel.top - 1))

    # Interior dark channel where the slots live (inset for depth)
    _channel_left = hp_cx + orb_r + inner_pad - 6
    _channel_right = mp_cx - orb_r - inner_pad + 6
    _inner_channel = pygame.Rect(
        _channel_left,
        panel.top + 10,
        max(0, _channel_right - _channel_left),
        panel_h - 20,
    )
    if _inner_channel.width > 0 and _inner_channel.height > 0:
        _ic_surf = pygame.Surface(_inner_channel.size, pygame.SRCALPHA)
        pygame.draw.rect(_ic_surf, (4, 4, 8, 160), _ic_surf.get_rect(), border_radius=6)
        pygame.draw.rect(_ic_surf, (72, 54, 24, 255), _ic_surf.get_rect(), 1, border_radius=6)
        screen.blit(_ic_surf, _inner_channel.topleft)

    # Rivets along top and bottom of the panel (within the central channel only)
    _rivet_y_top = panel.top + 8
    _rivet_y_bot = panel.bottom - 8
    _rivet_sx = _inner_channel.left + 6
    _rivet_ex = _inner_channel.right - 6
    _rivet_spacing = 32
    _rx = _rivet_sx
    while _rx <= _rivet_ex:
        for _ry in (_rivet_y_top, _rivet_y_bot):
            pygame.draw.circle(screen, (  6,  4,  2), (_rx, _ry), 3)
            pygame.draw.circle(screen, (170, 130, 56), (_rx, _ry), 2)
            pygame.draw.circle(screen, (252, 220, 144), (_rx - 1, _ry - 1), 1)
        _rx += _rivet_spacing

    # ── HP globe (clamped to left end of panel) ──
    _draw_hud_globe(
        screen, (hp_cx, orb_cy), hp_ratio, "hp",
        value_text=f"{int(hp)}/{int(max_hp)}",
        seed=1, tiny_font=small_font,
        extra_pulse=low_hp_pulse,
        flash=_HUD_STATE["hp_flash"],
    )
    # ── MP globe (clamped to right end of panel) ──
    _draw_hud_globe(
        screen, (mp_cx, orb_cy), mp_ratio, "mp",
        value_text=f"{int(current_mana)}/{int(max_mana)}",
        seed=2, tiny_font=small_font,
        extra_pulse=low_mp_pulse,
        flash=_HUD_STATE["mp_flash"],
    )

    # ── Passive slot ──
    _passive_x = hp_cx + orb_r + inner_pad
    _passive_y = panel.top + (panel_h - passive_sz) // 2 - 2
    passive_slot = pygame.Rect(_passive_x, _passive_y, passive_sz, passive_sz)
    _ps_bg = pygame.Surface((passive_sz, passive_sz), pygame.SRCALPHA)
    pygame.draw.rect(_ps_bg, (10, 8, 14, 255), _ps_bg.get_rect(), border_radius=6)
    pygame.draw.rect(_ps_bg, (24, 20, 30, 255), _ps_bg.get_rect().inflate(-4, -4), border_radius=5)
    screen.blit(_ps_bg, passive_slot.topleft)
    _p_icon = spell_icons.get(f"passive_{class_id}")
    if not isinstance(_p_icon, pygame.Surface):
        _p_icon = build_class_passive_icon(class_id, 64)
    _p_fit = pygame.transform.smoothscale(_p_icon, (passive_sz - 8, passive_sz - 8))
    screen.blit(_p_fit, (passive_slot.left + 4, passive_slot.top + 4))
    pygame.draw.rect(screen, (74, 54, 20, 255), passive_slot, 2, border_radius=6)
    pygame.draw.rect(screen, (196, 154, 72, 255), passive_slot.inflate(-2, -2), 1, border_radius=5)
    if passive_slot.collidepoint(mouse_pos):
        hovered_passive = True
        pygame.draw.rect(screen, accent, passive_slot.inflate(-4, -4), 2, border_radius=4)

    # ── Spell slots ──
    slot_origin_x = passive_slot.right + 12
    slot_origin_y = _passive_y
    _slot_rects_out: List[pygame.Rect] = []

    if slot_count <= 0:
        _ls = small_font.render("No skills unlocked. Open Skill Tree [K].", True, (140, 138, 130))
        screen.blit(_ls, (slot_origin_x + 4, slot_origin_y + slot_size // 2 - _ls.get_height() // 2))
    else:
        for vis_idx, (spell_idx, spell) in enumerate(visible_slots):
            spell_id = str(spell["id"])
            mana_cost = spell_mana_cost(spell, class_id) * passive_mana_mult
            enough_mana = current_mana >= mana_cost
            is_ultimate = bool(spell.get("is_ultimate", False))

            sx = slot_origin_x + vis_idx * (slot_size + slot_gap)
            slot = pygame.Rect(sx, slot_origin_y, slot_size, slot_size)
            _slot_rects_out.append(slot)

            # Ornate slot background (two-tone depth)
            _sl_bg = pygame.Surface((slot_size, slot_size), pygame.SRCALPHA)
            pygame.draw.rect(_sl_bg, (10, 8, 14, 255), _sl_bg.get_rect(), border_radius=6)
            pygame.draw.rect(_sl_bg, (24, 20, 30, 255), _sl_bg.get_rect().inflate(-4, -4), border_radius=5)
            screen.blit(_sl_bg, slot.topleft)

            if slot.collidepoint(mouse_pos):
                hovered_spell = spell
                hovered_slot = slot

            _icon = spell_icons.get(spell_id)
            if isinstance(_icon, pygame.Surface):
                _sc = pygame.transform.smoothscale(_icon, (slot_size - 8, slot_size - 8))
                screen.blit(_sc, (slot.left + 4, slot.top + 4))

            _cd = float(cooldowns.get(spell_id, 0.0))
            if _cd > 0.0:
                _cd_max = max(0.001, float(spell.get("cooldown", _cd)))
                _draw_radial_cooldown(screen, slot, clamp(_cd / _cd_max, 0.0, 1.0), (10, 10, 16, 200))
                _cd_t = font.render(f"{_cd:.1f}", True, (240, 220, 130))
                screen.blit(_cd_t, (slot.centerx - _cd_t.get_width() // 2, slot.centery - _cd_t.get_height() // 2))

            if spell_global_cooldown > 0.0 and _cd <= 0.0:
                _gcd_pct = clamp(spell_global_cooldown / max(0.001, global_cd_max), 0.0, 1.0)
                _gcd_ov = pygame.Surface((slot_size, slot_size), pygame.SRCALPHA)
                _gcd_ov.fill((180, 170, 130, int(_gcd_pct * 60)))
                screen.blit(_gcd_ov, slot.topleft)

            _outer_frame = (74, 54, 20)
            _inner_frame = (196, 154, 72)
            if spell_idx == selected_idx:
                pygame.draw.rect(screen, (28, 18, 8), slot, 3, border_radius=6)
                pygame.draw.rect(screen, accent, slot, 2, border_radius=6)
                _sel_pulse = 0.5 + 0.5 * math.sin(t_sec * 3.0)
                _sg_a = int(60 + 80 * _sel_pulse)
                _sg = pygame.Surface((slot_size + 10, slot_size + 10), pygame.SRCALPHA)
                pygame.draw.rect(_sg, (*accent, _sg_a), _sg.get_rect(), 3, border_radius=8)
                screen.blit(_sg, (slot.left - 5, slot.top - 5))
            elif slot.collidepoint(mouse_pos) and _cd <= 0.0:
                pygame.draw.rect(screen, _outer_frame, slot, 2, border_radius=6)
                pygame.draw.rect(screen, (220, 208, 180), slot.inflate(-2, -2), 1, border_radius=5)
            elif not enough_mana:
                pygame.draw.rect(screen, _outer_frame, slot, 2, border_radius=6)
                pygame.draw.rect(screen, (160, 60, 60), slot.inflate(-2, -2), 1, border_radius=5)
                _nm = pygame.Surface((slot_size, slot_size), pygame.SRCALPHA)
                _nm.fill((60, 10, 14, 90))
                screen.blit(_nm, slot.topleft)
            elif is_ultimate:
                pygame.draw.rect(screen, _outer_frame, slot, 2, border_radius=6)
                pygame.draw.rect(screen, (240, 200, 100), slot.inflate(-2, -2), 1, border_radius=5)
                _up = 0.5 + 0.5 * math.sin(t_sec * 3.0 + vis_idx * 0.4)
                _up_surf = pygame.Surface((slot_size + 6, slot_size + 6), pygame.SRCALPHA)
                pygame.draw.rect(_up_surf, (255, 220, 120, int(60 + 80 * _up)), _up_surf.get_rect(), 2, border_radius=8)
                screen.blit(_up_surf, (slot.left - 3, slot.top - 3))
            else:
                pygame.draw.rect(screen, _outer_frame, slot, 2, border_radius=6)
                pygame.draw.rect(screen, _inner_frame, slot.inflate(-2, -2), 1, border_radius=5)

            # Keybind label
            if keybind_editing == vis_idx:
                _pulse_a = int(160 + 95 * abs(math.sin(ticks * 0.006)))
                _ke_surf = pygame.Surface((slot_size + 8, slot_size + 8), pygame.SRCALPHA)
                pygame.draw.rect(_ke_surf, (255, 60, 60, _pulse_a), _ke_surf.get_rect(), 3, border_radius=8)
                screen.blit(_ke_surf, (slot.left - 4, slot.top - 4))
                _kl = "?"
            elif keybinds and vis_idx < len(keybinds):
                _raw = pygame.key.name(keybinds[vis_idx])
                _kl = _raw.upper() if len(_raw) <= 3 else _raw[:2].upper()
            else:
                _kl = SPELL_KEY_LABELS[vis_idx] if vis_idx < len(SPELL_KEY_LABELS) else str(vis_idx + 1)
            _kc = (252, 232, 168) if enough_mana else (240, 120, 100)
            _ks = small_font.render(_kl, True, _kc)
            _kbw, _kbh = _ks.get_width() + 6, _ks.get_height() + 2
            _kb_bg = pygame.Surface((_kbw, _kbh), pygame.SRCALPHA)
            pygame.draw.rect(_kb_bg, (0, 0, 0, 200), _kb_bg.get_rect(), border_radius=3)
            pygame.draw.rect(_kb_bg, (140, 100, 40, 255), _kb_bg.get_rect(), 1, border_radius=3)
            screen.blit(_kb_bg, (slot.left + 3, slot.top + 3))
            screen.blit(_ks, (slot.left + 6, slot.top + 4))

    if keybind_editing >= 0:
        _kb_s = font.render("PRESS ANY KEY  |  ESC to cancel", True, (255, 100, 100))
        _kb_bg = pygame.Surface((_kb_s.get_width() + 14, _kb_s.get_height() + 6), pygame.SRCALPHA)
        _kb_bg.fill((30, 0, 0, 220))
        screen.blit(_kb_bg, (panel.centerx - _kb_bg.get_width() // 2, panel.top - _kb_bg.get_height() - 6))
        screen.blit(_kb_s, (panel.centerx - _kb_s.get_width() // 2, panel.top - _kb_bg.get_height() - 3))

    # ── Level medallion above HP globe ──
    _pop = _HUD_STATE["level_pop"]
    _lvl_scale = 1.0 + 0.30 * _pop
    _med_r = int(18 * _lvl_scale)
    _med_cx = hp_cx
    _med_cy = panel.top - _med_r - 6
    _glow_breath = 0.35 + 0.25 * (0.5 + 0.5 * math.sin(t_sec * 1.8))
    _glow_strength = _glow_breath + _pop * 0.9
    _glow_r = _med_r + 10 + int(12 * _pop)
    _gs = pygame.Surface((_glow_r * 2 + 4, _glow_r * 2 + 4), pygame.SRCALPHA)
    for _rr in range(_glow_r, _med_r - 1, -1):
        _fo = (_rr - (_med_r - 1)) / max(1, _glow_r - (_med_r - 1))
        _ga = int(((1.0 - _fo) ** 2.2) * 160 * _glow_strength)
        if _ga > 0:
            pygame.draw.circle(_gs, (255, 220, 110, _ga), (_glow_r + 2, _glow_r + 2), _rr)
    screen.blit(_gs, (_med_cx - _glow_r - 2, _med_cy - _glow_r - 2))
    for _side in (-1, 1):
        for _li in range(3):
            _lx = _med_cx + _side * (_med_r + 4 + _li * 3)
            _ly = _med_cy + (_li - 1) * 5
            _leaf = pygame.Rect(0, 0, 9, 5)
            _leaf.center = (_lx, _ly)
            pygame.draw.ellipse(screen, (28, 44, 18), _leaf)
            pygame.draw.ellipse(screen, (86, 130, 46), _leaf, 1)
            pygame.draw.line(screen, (168, 200, 92), (_lx - 2, _ly), (_lx + 2, _ly))
    pygame.draw.circle(screen, (  4,   2,   2), (_med_cx, _med_cy), _med_r + 3)
    pygame.draw.circle(screen, ( 76,  54,  20), (_med_cx, _med_cy), _med_r + 2)
    pygame.draw.circle(screen, (220, 180,  88), (_med_cx, _med_cy), _med_r + 1)
    pygame.draw.circle(screen, (248, 218, 120), (_med_cx, _med_cy), _med_r)
    pygame.draw.circle(screen, ( 88,  62,  24), (_med_cx, _med_cy), _med_r, 2)
    pygame.draw.circle(screen, ( 22,  16,  10), (_med_cx, _med_cy), _med_r - 2)
    pygame.draw.circle(screen, ( 42,  30,  18), (_med_cx, _med_cy), _med_r - 3)
    _lvl_font = pygame.font.SysFont("georgia", max(11, int(18 * _lvl_scale)), bold=True)
    _lvl_s = _lvl_font.render(str(int(player_level)), True, (252, 232, 160))
    _lvl_sh = _lvl_font.render(str(int(player_level)), True, (0, 0, 0))
    _lvw, _lvh = _lvl_s.get_size()
    screen.blit(_lvl_sh, (_med_cx - _lvw // 2 + 1, _med_cy - _lvh // 2 + 1))
    screen.blit(_lvl_s, (_med_cx - _lvw // 2, _med_cy - _lvh // 2))
    if _pop > 0:
        _ring_r = int(_med_r + (1.0 - _pop) * 46)
        _ring_a = int(210 * _pop)
        _ring = pygame.Surface((_ring_r * 2 + 6, _ring_r * 2 + 6), pygame.SRCALPHA)
        pygame.draw.circle(_ring, (255, 230, 120, _ring_a), (_ring_r + 3, _ring_r + 3), _ring_r, 2)
        pygame.draw.circle(_ring, (255, 244, 200, int(_ring_a * 0.55)), (_ring_r + 3, _ring_r + 3), _ring_r + 1, 1)
        screen.blit(_ring, (_med_cx - _ring_r - 3, _med_cy - _ring_r - 3))
        for _bi in range(14):
            _ba = (_bi / 14) * 2 * math.pi
            _bd = int((1 - _pop) * 48 + 14)
            _bx = _med_cx + int(_bd * math.cos(_ba))
            _by = _med_cy + int(_bd * math.sin(_ba))
            _spark = pygame.Surface((10, 10), pygame.SRCALPHA)
            pygame.draw.circle(_spark, (255, 230, 120, int(230 * _pop)), (5, 5), 3)
            pygame.draw.circle(_spark, (255, 252, 220, int(255 * _pop)), (5, 5), 1)
            screen.blit(_spark, (_bx - 5, _by - 5))

    # ── Gold plaque above MP globe ──
    _gold_text = f"{int(gold):,}"
    _gold_s = small_font.render(_gold_text, True, (252, 224, 140))
    _gold_sh = small_font.render(_gold_text, True, (0, 0, 0))
    _gw = _gold_s.get_width()
    _gh = _gold_s.get_height()
    _coin_r = 8
    _gplaque_w = _gw + _coin_r * 2 + 24
    _gplaque_h = max(_gh, _coin_r * 2) + 8
    _gpx = mp_cx - _gplaque_w // 2
    _gpy = panel.top - _gplaque_h - 6
    _gplaque = pygame.Surface((_gplaque_w, _gplaque_h), pygame.SRCALPHA)
    pygame.draw.rect(_gplaque, ( 10,  6,  2, 230), _gplaque.get_rect(), border_radius=5)
    pygame.draw.rect(_gplaque, ( 84, 60, 20, 255), _gplaque.get_rect(), 2, border_radius=5)
    pygame.draw.rect(_gplaque, (196, 154, 72, 255), _gplaque.get_rect().inflate(-2, -2), 1, border_radius=5)
    screen.blit(_gplaque, (_gpx, _gpy))
    _coin_cx = _gpx + _coin_r + 6
    _coin_cy = _gpy + _gplaque_h // 2
    pygame.draw.circle(screen, ( 18,  12,   4), (_coin_cx, _coin_cy), _coin_r + 1)
    pygame.draw.circle(screen, ( 96,  68,  22), (_coin_cx, _coin_cy), _coin_r)
    pygame.draw.circle(screen, (200, 156,  64), (_coin_cx, _coin_cy), _coin_r - 1)
    pygame.draw.circle(screen, (248, 212, 108), (_coin_cx, _coin_cy), _coin_r - 2)
    _coin_phase = 0.5 + 0.5 * math.sin(t_sec * 2.6)
    pygame.draw.circle(screen, (255, 244, 190), (_coin_cx - 2, _coin_cy - 2),
                       max(1, int(1 + _coin_phase * 2)))
    _gtx = _coin_cx + _coin_r + 6
    _gty = _gpy + (_gplaque_h - _gh) // 2
    screen.blit(_gold_sh, (_gtx + 1, _gty + 1))
    screen.blit(_gold_s, (_gtx, _gty))

    # ── XP strip inside the bottom of the central channel ──
    _xp_pad_x = 10
    _xp_w = max(0, _inner_channel.width - _xp_pad_x * 2)
    if _xp_w > 80:
        _xp_h = 8
        _xp_x = _inner_channel.left + _xp_pad_x
        _xp_y = _inner_channel.bottom - _xp_h - 4
        _xp_rect = pygame.Rect(_xp_x, _xp_y, _xp_w, _xp_h)
        _xp_bg = pygame.Surface((_xp_w, _xp_h), pygame.SRCALPHA)
        pygame.draw.rect(_xp_bg, ( 6,  4, 10, 240), _xp_bg.get_rect(), border_radius=3)
        pygame.draw.rect(_xp_bg, (46, 30, 62, 255), _xp_bg.get_rect(), 1, border_radius=3)
        screen.blit(_xp_bg, (_xp_x, _xp_y))
        _fill_w = int((_xp_w - 2) * xp_ratio)
        if _fill_w > 0:
            _xp_fill = pygame.Rect(_xp_x + 1, _xp_y + 1, _fill_w, _xp_h - 2)
            for yy in range(_xp_fill.height):
                _t = yy / max(1, _xp_fill.height - 1)
                _c = (
                    int(188 + (104 - 188) * _t),
                    int(120 + ( 42 - 120) * _t),
                    int(248 + (158 - 248) * _t),
                )
                pygame.draw.line(screen, _c,
                                 (_xp_fill.left, _xp_fill.top + yy),
                                 (_xp_fill.right - 1, _xp_fill.top + yy))
            pygame.draw.line(screen, (230, 200, 255),
                             (_xp_fill.left, _xp_fill.top),
                             (_xp_fill.right - 1, _xp_fill.top))
            _sweep = ((ticks * 0.0008) % 2.0) - 0.3
            if -0.1 <= _sweep <= 1.15 and _fill_w > 10:
                _sw_cx = int(_fill_w * _sweep)
                _sw_surf = pygame.Surface((_fill_w, _xp_fill.height), pygame.SRCALPHA)
                for _dx in range(-18, 19):
                    _xx = _sw_cx + _dx
                    if 0 <= _xx < _fill_w:
                        _bell = math.exp(-(_dx * _dx) / 48)
                        _a = int(170 * _bell)
                        if _a > 0:
                            pygame.draw.line(_sw_surf, (255, 230, 255, _a),
                                             (_xx, 0), (_xx, _xp_fill.height))
                screen.blit(_sw_surf, (_xp_fill.left, _xp_fill.top))
        for _ti in range(1, 10):
            _tx = _xp_x + int(_xp_w * _ti / 10)
            pygame.draw.line(screen, (70, 48, 96), (_tx, _xp_y + 1), (_tx, _xp_y + _xp_h - 1))

    # Tooltip name lookups for passive (used after spell tooltip block)
    passive_name = str(passive.get("name", "Class Passive"))
    passive_desc = str(passive.get("desc", ""))

    def draw_hover_tooltip(lines: List[str], anchor: pygame.Rect, cache_key: object) -> None:
        width = 0
        rendered: List[pygame.Surface] = []
        for li, line in enumerate(lines):
            surf = font.render(line, True, (252, 234, 196) if li == 0 else (204, 196, 178))
            rendered.append(surf)
            width = max(width, surf.get_width())
        tip = pygame.Rect(0, 0, width + 22, 12 + len(rendered) * 24)
        tip.midbottom = (anchor.centerx, anchor.top - 8)
        tip.clamp_ip(pygame.Rect(10, 10, SCREEN_WIDTH - 20, SCREEN_HEIGHT - 20))
        global _TOOLTIP_SURFACE, _TOOLTIP_LAST_ITEM
        if _TOOLTIP_LAST_ITEM != cache_key:
            _TOOLTIP_SURFACE = pygame.Surface((tip.width, tip.height), pygame.SRCALPHA)
            pygame.draw.rect(_TOOLTIP_SURFACE, (18, 16, 22, 242), (0, 0, tip.width, tip.height), border_radius=8)
            pygame.draw.rect(_TOOLTIP_SURFACE, (150, 124, 76), (0, 0, tip.width, tip.height), 1, border_radius=8)
            _ty = 6
            for surf in rendered:
                _TOOLTIP_SURFACE.blit(surf, (11, _ty))
                _ty += 24
            _TOOLTIP_LAST_ITEM = cache_key
        if _TOOLTIP_SURFACE:
            screen.blit(_TOOLTIP_SURFACE, tip.topleft)

    if hovered_spell is not None and hovered_slot is not None:
        _kind = str(hovered_spell.get("kind", "spell"))
        _dmg = float(hovered_spell.get("damage", 0.0))
        _cd_val = float(hovered_spell.get("cooldown", 0.0))
        _mc = spell_mana_cost(hovered_spell, class_id) * passive_mana_mult
        _unlocked = str(hovered_spell.get("skill", "")) in unlocked_skills
        _kl_map = {
            "projectile": "Launches a fast projectile that hits enemies in a line.",
            "nova": "Expands outward in a ring, damaging enemies in radius.",
            "orb": "Places a pulsing orb that repeatedly damages nearby enemies.",
            "ward": "Creates a standing zone that damages enemies over time.",
            "melee_arc": "Performs a close melee arc in front of you.",
            "cone": "Sweeps a wide cone forward, disrupting enemies.",
            "pillar": "Raises a blocking pillar that damages on impact.",
            "ultimate": "Channel a catastrophic elemental storm around you.",
        }
        _lines: List[str] = [str(hovered_spell.get("name", "Spell")), _kl_map.get(_kind, "Cast a combat spell.")]
        if bool(hovered_spell.get("is_ultimate", False)):
            _lines.append("ULTIMATE — Strongest class finisher.")
        _lines.append(f"Damage {int(round(_dmg))}   Mana {int(round(_mc))}   Cooldown {_cd_val:.1f}s")
        if _kind == "projectile":
            _lines.append(f"Speed {int(float(hovered_spell.get('speed', 0.0)))}   Radius {int(float(hovered_spell.get('radius', 0.0)))}")
        elif _kind == "nova":
            _lines.append(f"Max Radius {int(float(hovered_spell.get('max_radius', 0.0)))}")
        elif _kind == "melee_arc":
            _lines.append(f"Melee Reach {int(float(hovered_spell.get('radius', 0.0)))}")
        elif _kind == "cone":
            _lines.append(f"Reach {int(float(hovered_spell.get('radius', 0.0)))}   Angle {int(float(hovered_spell.get('cone_angle', 0.0)))}")
        elif _kind == "pillar":
            _lines.append(f"Duration {float(hovered_spell.get('duration', 0.0)):.1f}s")
        elif _kind in ("orb", "ward"):
            _lines.append(f"Area Radius {int(float(hovered_spell.get('radius', 0.0)))}")
        if not _unlocked:
            _lines.append("LOCKED — Unlock in the Skill Tree [K].")
        draw_hover_tooltip(_lines, hovered_slot, hovered_spell)
    elif hovered_passive:
        _p_lines: List[str] = [f"{passive_name} (Class Passive)"]
        _p_lines.extend(wrap_text_lines(font, passive_desc, 360, max_lines=2))
        _p_lines.extend(class_passive_effect_lines(passive, max_lines=3))
        draw_hover_tooltip(_p_lines, passive_slot, ("passive", class_id))
    return _slot_rects_out
