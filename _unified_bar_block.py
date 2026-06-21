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
    item_inventory: Optional[List] = None,
    potion_shared_cd_pct: float = 0.0,
) -> Tuple[List[pygame.Rect], Dict[int, pygame.Rect]]:
    """Compact unified action belt with integrated spell slots and consumable slots.

    Returns (spell_slot_rects, potion_slot_rects).
    Layout: [HP orb] [passive|spells|div|potions] [MP orb]
    All ornate brass/gold, but scaled down ~35% from the previous oversized version.
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

    if item_inventory is None:
        item_inventory = []
    max_potion_slots = 4

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

    # ── Compact panel geometry ──
    orb_r = 38                  # down from 60
    orb_d = orb_r * 2
    slot_sz = 44                # down from 64
    slot_gap = 4                # tighter
    passive_sz = 44
    pot_sz = 38                 # potion slots slightly smaller than spell slots
    pot_gap = 4
    outer_pad = 10
    inner_pad = 14

    # Central strip: passive + spell slots + divider + potion slots
    spell_strip_w = passive_sz
    if slot_count > 0:
        spell_strip_w += 8 + slot_count * slot_sz + (slot_count - 1) * slot_gap
    else:
        spell_strip_w += 180
    pot_strip_w = max_potion_slots * pot_sz + (max_potion_slots - 1) * pot_gap
    divider_w = 12              # brass divider between spells and potions
    _strip_w = spell_strip_w + divider_w + pot_strip_w

    panel_h = 62                # compact height (down from 96)
    panel_w = 2 * (outer_pad + orb_d + inner_pad) + _strip_w
    panel_x = (SCREEN_WIDTH - panel_w) // 2
    panel_y = SCREEN_HEIGHT - panel_h - 18
    panel = pygame.Rect(panel_x, panel_y, panel_w, panel_h)

    hp_cx = panel.left + outer_pad + orb_r
    mp_cx = panel.right - outer_pad - orb_r
    orb_cy = panel.centery

    mouse_pos = pygame.mouse.get_pos()
    hovered_spell: Optional[Dict[str, object]] = None
    hovered_slot: Optional[pygame.Rect] = None
    hovered_passive = False
    hovered_potion: Optional[Dict[str, object]] = None
    hovered_pot_slot: Optional[pygame.Rect] = None

    # ── Soft drop shadow ──
    _sh = pygame.Surface((panel_w + 12, panel_h + 10), pygame.SRCALPHA)
    pygame.draw.rect(_sh, (0, 0, 0, 120), _sh.get_rect().inflate(-2, -2), border_radius=8)
    screen.blit(_sh, (panel.left - 6, panel.top - 3))

    # ── Ornate panel backdrop (compact brass bezel) ──
    _pbg = pygame.Surface((panel_w + 2, panel_h + 2), pygame.SRCALPHA)
    _pr = _pbg.get_rect()
    pygame.draw.rect(_pbg, (14, 12, 18, 236), _pr, border_radius=7)
    pygame.draw.rect(_pbg, (52, 38, 16), _pr, 2, border_radius=7)
    pygame.draw.rect(_pbg, (160, 120, 48), _pr.inflate(-3, -3), 1, border_radius=6)
    pygame.draw.rect(_pbg, (210, 170, 80), _pr.inflate(-5, -5), 1, border_radius=5)
    pygame.draw.rect(_pbg, (36, 26, 14), _pr.inflate(-7, -7), 1, border_radius=5)
    screen.blit(_pbg, (panel.left - 1, panel.top - 1))

    # ── Interior channel (slots live here) ──
    _ch_left = hp_cx + orb_r + inner_pad - 4
    _ch_right = mp_cx - orb_r - inner_pad + 4
    _ch = pygame.Rect(_ch_left, panel.top + 6, max(0, _ch_right - _ch_left), panel_h - 12)
    if _ch.width > 0 and _ch.height > 0:
        _cs = pygame.Surface(_ch.size, pygame.SRCALPHA)
        pygame.draw.rect(_cs, (4, 4, 8, 140), _cs.get_rect(), border_radius=4)
        pygame.draw.rect(_cs, (60, 44, 20), _cs.get_rect(), 1, border_radius=4)
        screen.blit(_cs, _ch.topleft)

    # Compact rivets (fewer, just top/bottom of channel edges)
    for _ry in (_ch.top + 2, _ch.bottom - 2):
        for _rx in (_ch.left + 4, _ch.right - 4):
            pygame.draw.circle(screen, (6, 4, 2), (_rx, _ry), 2)
            pygame.draw.circle(screen, (160, 120, 50), (_rx, _ry), 1)

    # ── HP globe (left) ──
    _draw_hud_globe(
        screen, (hp_cx, orb_cy), hp_ratio, "hp",
        value_text=f"{int(hp)}/{int(max_hp)}",
        seed=1, tiny_font=small_font,
        extra_pulse=low_hp_pulse,
        flash=_HUD_STATE["hp_flash"],
    )
    # ── MP globe (right) ──
    _draw_hud_globe(
        screen, (mp_cx, orb_cy), mp_ratio, "mp",
        value_text=f"{int(current_mana)}/{int(max_mana)}",
        seed=2, tiny_font=small_font,
        extra_pulse=low_mp_pulse,
        flash=_HUD_STATE["mp_flash"],
    )

    # ── Passive slot ──
    _passive_x = _ch.left + 4
    _passive_y = panel.top + (panel_h - passive_sz) // 2
    passive_slot = pygame.Rect(_passive_x, _passive_y, passive_sz, passive_sz)
    _ps_bg = pygame.Surface((passive_sz, passive_sz), pygame.SRCALPHA)
    pygame.draw.rect(_ps_bg, (10, 8, 14), _ps_bg.get_rect(), border_radius=4)
    pygame.draw.rect(_ps_bg, (22, 18, 28), _ps_bg.get_rect().inflate(-2, -2), border_radius=3)
    screen.blit(_ps_bg, passive_slot.topleft)
    _p_icon = spell_icons.get(f"passive_{class_id}")
    if not isinstance(_p_icon, pygame.Surface):
        _p_icon = build_class_passive_icon(class_id, 64)
    _p_fit = pygame.transform.smoothscale(_p_icon, (passive_sz - 6, passive_sz - 6))
    screen.blit(_p_fit, (passive_slot.left + 3, passive_slot.top + 3))
    pygame.draw.rect(screen, (64, 48, 18), passive_slot, 1, border_radius=4)
    pygame.draw.rect(screen, (170, 130, 60), passive_slot.inflate(-2, -2), 1, border_radius=3)
    if passive_slot.collidepoint(mouse_pos):
        hovered_passive = True
        pygame.draw.rect(screen, accent, passive_slot.inflate(-3, -3), 1, border_radius=3)

    # ── Spell slots ──
    slot_origin_x = passive_slot.right + 8
    slot_origin_y = _passive_y + (passive_sz - slot_sz) // 2
    _slot_rects_out: List[pygame.Rect] = []

    if slot_count <= 0:
        _ls = small_font.render("No skills unlocked [K]", True, (130, 128, 120))
        screen.blit(_ls, (slot_origin_x + 2, slot_origin_y + slot_sz // 2 - _ls.get_height() // 2))
    else:
        for vis_idx, (spell_idx, spell) in enumerate(visible_slots):
            spell_id = str(spell["id"])
            mana_cost = spell_mana_cost(spell, class_id) * passive_mana_mult
            enough_mana = current_mana >= mana_cost
            is_ultimate = bool(spell.get("is_ultimate", False))

            sx = slot_origin_x + vis_idx * (slot_sz + slot_gap)
            slot = pygame.Rect(sx, slot_origin_y, slot_sz, slot_sz)
            _slot_rects_out.append(slot)

            # Slot bg
            _sl_bg = pygame.Surface((slot_sz, slot_sz), pygame.SRCALPHA)
            pygame.draw.rect(_sl_bg, (10, 8, 14), _sl_bg.get_rect(), border_radius=4)
            pygame.draw.rect(_sl_bg, (22, 18, 28), _sl_bg.get_rect().inflate(-2, -2), border_radius=3)
            screen.blit(_sl_bg, slot.topleft)

            if slot.collidepoint(mouse_pos):
                hovered_spell = spell
                hovered_slot = slot

            _icon = spell_icons.get(spell_id)
            if isinstance(_icon, pygame.Surface):
                _sc = pygame.transform.smoothscale(_icon, (slot_sz - 6, slot_sz - 6))
                screen.blit(_sc, (slot.left + 3, slot.top + 3))

            # Cooldown overlay
            _cd = float(cooldowns.get(spell_id, 0.0))
            if _cd > 0.0:
                _cd_max = max(0.001, float(spell.get("cooldown", _cd)))
                _draw_radial_cooldown(screen, slot, clamp(_cd / _cd_max, 0.0, 1.0), (10, 10, 16, 190))
                _cd_t = small_font.render(f"{_cd:.1f}", True, (240, 220, 130))
                screen.blit(_cd_t, (slot.centerx - _cd_t.get_width() // 2, slot.centery - _cd_t.get_height() // 2))

            if spell_global_cooldown > 0.0 and _cd <= 0.0:
                _gcd_pct = clamp(spell_global_cooldown / max(0.001, global_cd_max), 0.0, 1.0)
                _gcd_ov = pygame.Surface((slot_sz, slot_sz), pygame.SRCALPHA)
                _gcd_ov.fill((160, 150, 120, int(_gcd_pct * 50)))
                screen.blit(_gcd_ov, slot.topleft)

            # Border states
            if spell_idx == selected_idx:
                pygame.draw.rect(screen, (24, 16, 6), slot, 2, border_radius=4)
                pygame.draw.rect(screen, accent, slot.inflate(-1, -1), 1, border_radius=4)
                _sel_pulse = 0.5 + 0.5 * math.sin(t_sec * 3.0)
                _sg_a = int(40 + 60 * _sel_pulse)
                _sg = pygame.Surface((slot_sz + 6, slot_sz + 6), pygame.SRCALPHA)
                pygame.draw.rect(_sg, (*accent, _sg_a), _sg.get_rect(), 2, border_radius=6)
                screen.blit(_sg, (slot.left - 3, slot.top - 3))
            elif slot.collidepoint(mouse_pos) and _cd <= 0.0:
                pygame.draw.rect(screen, (64, 48, 18), slot, 1, border_radius=4)
                pygame.draw.rect(screen, (200, 190, 165), slot.inflate(-1, -1), 1, border_radius=3)
            elif not enough_mana:
                pygame.draw.rect(screen, (64, 48, 18), slot, 1, border_radius=4)
                pygame.draw.rect(screen, (140, 50, 50), slot.inflate(-1, -1), 1, border_radius=3)
                _nm = pygame.Surface((slot_sz, slot_sz), pygame.SRCALPHA)
                _nm.fill((50, 8, 12, 70))
                screen.blit(_nm, slot.topleft)
            elif is_ultimate:
                pygame.draw.rect(screen, (64, 48, 18), slot, 1, border_radius=4)
                pygame.draw.rect(screen, (220, 186, 90), slot.inflate(-1, -1), 1, border_radius=3)
                _up = 0.5 + 0.5 * math.sin(t_sec * 3.0 + vis_idx * 0.4)
                _up_s = pygame.Surface((slot_sz + 4, slot_sz + 4), pygame.SRCALPHA)
                pygame.draw.rect(_up_s, (255, 210, 100, int(40 + 60 * _up)), _up_s.get_rect(), 1, border_radius=5)
                screen.blit(_up_s, (slot.left - 2, slot.top - 2))
            else:
                pygame.draw.rect(screen, (64, 48, 18), slot, 1, border_radius=4)
                pygame.draw.rect(screen, (170, 130, 60), slot.inflate(-1, -1), 1, border_radius=3)

            # Keybind label (compact)
            if keybind_editing == vis_idx:
                _pulse_a = int(140 + 80 * abs(math.sin(ticks * 0.006)))
                _ke_s = pygame.Surface((slot_sz + 4, slot_sz + 4), pygame.SRCALPHA)
                pygame.draw.rect(_ke_s, (255, 60, 60, _pulse_a), _ke_s.get_rect(), 2, border_radius=5)
                screen.blit(_ke_s, (slot.left - 2, slot.top - 2))
                _kl = "?"
            elif keybinds and vis_idx < len(keybinds):
                _raw = pygame.key.name(keybinds[vis_idx])
                _kl = _raw.upper() if len(_raw) <= 3 else _raw[:2].upper()
            else:
                _kl = SPELL_KEY_LABELS[vis_idx] if vis_idx < len(SPELL_KEY_LABELS) else str(vis_idx + 1)
            _kc = (240, 220, 150) if enough_mana else (220, 110, 90)
            _ks = small_font.render(_kl, True, _kc)
            _kb_bg = pygame.Surface((_ks.get_width() + 4, _ks.get_height() + 2), pygame.SRCALPHA)
            pygame.draw.rect(_kb_bg, (0, 0, 0, 180), _kb_bg.get_rect(), border_radius=2)
            screen.blit(_kb_bg, (slot.left + 2, slot.top + 2))
            screen.blit(_ks, (slot.left + 4, slot.top + 3))

    if keybind_editing >= 0:
        _kb_s = font.render("PRESS ANY KEY  |  ESC to cancel", True, (255, 100, 100))
        _kb_bg2 = pygame.Surface((_kb_s.get_width() + 12, _kb_s.get_height() + 4), pygame.SRCALPHA)
        _kb_bg2.fill((30, 0, 0, 210))
        screen.blit(_kb_bg2, (panel.centerx - _kb_bg2.get_width() // 2, panel.top - _kb_bg2.get_height() - 4))
        screen.blit(_kb_s, (panel.centerx - _kb_s.get_width() // 2, panel.top - _kb_bg2.get_height() - 2))

    # ── Brass divider between spells and potions ──
    _div_x = slot_origin_x + max(0, slot_count) * (slot_sz + slot_gap) + (8 if slot_count > 0 else spell_strip_w - passive_sz - 8)
    _div_top = panel.top + 10
    _div_bot = panel.bottom - 10
    pygame.draw.line(screen, (40, 30, 14), (_div_x, _div_top), (_div_x, _div_bot), 1)
    pygame.draw.line(screen, (160, 120, 48), (_div_x + 1, _div_top), (_div_x + 1, _div_bot), 1)
    pygame.draw.line(screen, (210, 170, 80), (_div_x + 2, _div_top + 2), (_div_x + 2, _div_bot - 2), 1)
    # Divider rivets top and bottom
    for _dry in (_div_top - 1, _div_bot + 1):
        pygame.draw.circle(screen, (6, 4, 2), (_div_x + 1, _dry), 2)
        pygame.draw.circle(screen, (180, 140, 58), (_div_x + 1, _dry), 1)

    # ── Consumable / potion slots (integrated) ──
    pot_origin_x = _div_x + divider_w
    pot_origin_y = panel.top + (panel_h - pot_sz) // 2
    _pot_rects_out: Dict[int, pygame.Rect] = {}

    for i in range(max_potion_slots):
        px = pot_origin_x + i * (pot_sz + pot_gap)
        py = pot_origin_y
        pot_slot = pygame.Rect(px, py, pot_sz, pot_sz)
        _pot_rects_out[i] = pot_slot

        _pot_entry = item_inventory[i] if i < len(item_inventory) else None
        filled = _pot_entry is not None

        # Slot bg
        _pb = pygame.Surface((pot_sz, pot_sz), pygame.SRCALPHA)
        pygame.draw.rect(_pb, (12, 10, 16) if filled else (8, 8, 14), _pb.get_rect(), border_radius=4)
        pygame.draw.rect(_pb, (24, 20, 28) if filled else (16, 14, 22), _pb.get_rect().inflate(-2, -2), border_radius=3)
        screen.blit(_pb, pot_slot.topleft)

        if filled:
            item = _pot_entry
            _bdr_col = item_rarity_border(item)

            _p_icon = resolve_item_icon(item, pot_sz - 6)
            if isinstance(_p_icon, pygame.Surface):
                screen.blit(_p_icon, (pot_slot.left + 3, pot_slot.top + 3))
            else:
                _col = tuple(item.get("color", (160, 160, 160)))
                pygame.draw.rect(screen, _col, pot_slot.inflate(-8, -8), border_radius=3)

            # Radial cooldown
            if potion_shared_cd_pct > 0.0:
                _draw_radial_cooldown(screen, pot_slot, potion_shared_cd_pct, (12, 12, 18, 180))

            # Stack count
            _qty = int(item.get("quantity", item.get("stack", 0)))
            if _qty > 1:
                _q_s = small_font.render(str(_qty), True, (230, 226, 200))
                _qr = pygame.Rect(pot_slot.right - _q_s.get_width() - 2, pot_slot.bottom - _q_s.get_height() - 1,
                                  _q_s.get_width() + 2, _q_s.get_height())
                pygame.draw.rect(screen, (14, 12, 18, 180), _qr, border_radius=2)
                screen.blit(_q_s, (_qr.left + 1, _qr.top))

            # Border
            if pot_slot.collidepoint(mouse_pos):
                hovered_potion = item
                hovered_pot_slot = pot_slot
                pygame.draw.rect(screen, (200, 196, 216), pot_slot, 1, border_radius=4)
            else:
                pygame.draw.rect(screen, _bdr_col, pot_slot, 1, border_radius=4)
        else:
            pygame.draw.rect(screen, (36, 34, 44), pot_slot, 1, border_radius=4)

        # Potion keybind (1-4 relative)
        _pk_col = (150, 140, 110) if filled else (70, 68, 62)
        _pks = small_font.render(str(i + 1), True, _pk_col)
        screen.blit(_pks, (pot_slot.left + 3, pot_slot.bottom - _pks.get_height() - 1))

    # ── Level badge (compact, above HP globe) ──
    _pop = _HUD_STATE["level_pop"]
    _lvl_scale = 1.0 + 0.22 * _pop
    _med_r = int(13 * _lvl_scale)
    _med_cx = hp_cx
    _med_cy = panel.top - _med_r - 4
    # Glow
    _glow_breath = 0.3 + 0.2 * (0.5 + 0.5 * math.sin(t_sec * 1.8))
    _glow_strength = _glow_breath + _pop * 0.8
    _glow_r = _med_r + 8 + int(10 * _pop)
    _gs = pygame.Surface((_glow_r * 2 + 4, _glow_r * 2 + 4), pygame.SRCALPHA)
    for _rr in range(_glow_r, _med_r - 1, -1):
        _fo = (_rr - (_med_r - 1)) / max(1, _glow_r - (_med_r - 1))
        _ga = int(((1.0 - _fo) ** 2.2) * 130 * _glow_strength)
        if _ga > 0:
            pygame.draw.circle(_gs, (255, 220, 110, _ga), (_glow_r + 2, _glow_r + 2), _rr)
    screen.blit(_gs, (_med_cx - _glow_r - 2, _med_cy - _glow_r - 2))
    # Laurel (compact, 2 per side)
    for _side in (-1, 1):
        for _li in range(2):
            _lx = _med_cx + _side * (_med_r + 3 + _li * 3)
            _ly = _med_cy + (_li - 0.5) * 4
            _leaf = pygame.Rect(0, 0, 7, 4)
            _leaf.center = (int(_lx), int(_ly))
            pygame.draw.ellipse(screen, (28, 44, 18), _leaf)
            pygame.draw.ellipse(screen, (80, 120, 42), _leaf, 1)
    # Medallion rings
    pygame.draw.circle(screen, (4, 2, 2), (_med_cx, _med_cy), _med_r + 2)
    pygame.draw.circle(screen, (70, 50, 18), (_med_cx, _med_cy), _med_r + 1)
    pygame.draw.circle(screen, (200, 164, 72), (_med_cx, _med_cy), _med_r)
    pygame.draw.circle(screen, (80, 56, 22), (_med_cx, _med_cy), _med_r, 2)
    pygame.draw.circle(screen, (20, 14, 10), (_med_cx, _med_cy), _med_r - 2)
    pygame.draw.circle(screen, (38, 28, 16), (_med_cx, _med_cy), _med_r - 3)
    _lvl_font = pygame.font.SysFont("georgia", max(9, int(14 * _lvl_scale)), bold=True)
    _lvl_s = _lvl_font.render(str(int(player_level)), True, (252, 232, 160))
    _lvl_sh = _lvl_font.render(str(int(player_level)), True, (0, 0, 0))
    _lvw, _lvh = _lvl_s.get_size()
    screen.blit(_lvl_sh, (_med_cx - _lvw // 2 + 1, _med_cy - _lvh // 2 + 1))
    screen.blit(_lvl_s, (_med_cx - _lvw // 2, _med_cy - _lvh // 2))
    # Level-up burst
    if _pop > 0:
        _ring_r = int(_med_r + (1.0 - _pop) * 34)
        _ring_a = int(200 * _pop)
        _ring = pygame.Surface((_ring_r * 2 + 4, _ring_r * 2 + 4), pygame.SRCALPHA)
        pygame.draw.circle(_ring, (255, 230, 120, _ring_a), (_ring_r + 2, _ring_r + 2), _ring_r, 2)
        screen.blit(_ring, (_med_cx - _ring_r - 2, _med_cy - _ring_r - 2))
        for _bi in range(10):
            _ba = (_bi / 10) * 2 * math.pi
            _bd = int((1 - _pop) * 36 + 10)
            _bx = _med_cx + int(_bd * math.cos(_ba))
            _by = _med_cy + int(_bd * math.sin(_ba))
            _spark = pygame.Surface((8, 8), pygame.SRCALPHA)
            pygame.draw.circle(_spark, (255, 230, 120, int(220 * _pop)), (4, 4), 2)
            screen.blit(_spark, (_bx - 4, _by - 4))

    # ── Gold plaque (compact, above MP globe) ──
    _gold_text = f"{int(gold):,}"
    _gold_s = small_font.render(_gold_text, True, (252, 224, 140))
    _gold_sh = small_font.render(_gold_text, True, (0, 0, 0))
    _gw = _gold_s.get_width()
    _gh = _gold_s.get_height()
    _coin_r = 6
    _gplaque_w = _gw + _coin_r * 2 + 18
    _gplaque_h = max(_gh, _coin_r * 2) + 6
    _gpx = mp_cx - _gplaque_w // 2
    _gpy = panel.top - _gplaque_h - 4
    _gplaque = pygame.Surface((_gplaque_w, _gplaque_h), pygame.SRCALPHA)
    pygame.draw.rect(_gplaque, (10, 6, 2, 220), _gplaque.get_rect(), border_radius=4)
    pygame.draw.rect(_gplaque, (74, 54, 18), _gplaque.get_rect(), 1, border_radius=4)
    pygame.draw.rect(_gplaque, (170, 130, 60), _gplaque.get_rect().inflate(-2, -2), 1, border_radius=3)
    screen.blit(_gplaque, (_gpx, _gpy))
    _coin_cx = _gpx + _coin_r + 5
    _coin_cy = _gpy + _gplaque_h // 2
    pygame.draw.circle(screen, (16, 10, 4), (_coin_cx, _coin_cy), _coin_r + 1)
    pygame.draw.circle(screen, (86, 60, 20), (_coin_cx, _coin_cy), _coin_r)
    pygame.draw.circle(screen, (190, 148, 58), (_coin_cx, _coin_cy), _coin_r - 1)
    pygame.draw.circle(screen, (240, 200, 100), (_coin_cx, _coin_cy), _coin_r - 2)
    _gtx = _coin_cx + _coin_r + 5
    _gty = _gpy + (_gplaque_h - _gh) // 2
    screen.blit(_gold_sh, (_gtx + 1, _gty + 1))
    screen.blit(_gold_s, (_gtx, _gty))

    # ── XP strip (thin, below panel) ──
    _xp_w = max(0, _ch.width - 8)
    if _xp_w > 60:
        _xp_h = 5
        _xp_x = _ch.left + 4
        _xp_y = panel.bottom + 2
        _xp_bg = pygame.Surface((_xp_w, _xp_h), pygame.SRCALPHA)
        pygame.draw.rect(_xp_bg, (6, 4, 10, 220), _xp_bg.get_rect(), border_radius=2)
        pygame.draw.rect(_xp_bg, (40, 28, 56), _xp_bg.get_rect(), 1, border_radius=2)
        screen.blit(_xp_bg, (_xp_x, _xp_y))
        _fill_w = int((_xp_w - 2) * xp_ratio)
        if _fill_w > 0:
            _xp_fill = pygame.Rect(_xp_x + 1, _xp_y + 1, _fill_w, _xp_h - 2)
            for yy in range(_xp_fill.height):
                _t = yy / max(1, _xp_fill.height - 1)
                _c = (int(180 + (100 - 180) * _t), int(110 + (40 - 110) * _t), int(240 + (150 - 240) * _t))
                pygame.draw.line(screen, _c, (_xp_fill.left, _xp_fill.top + yy), (_xp_fill.right - 1, _xp_fill.top + yy))
            # Shimmer sweep
            _sweep = ((ticks * 0.0008) % 2.0) - 0.3
            if -0.1 <= _sweep <= 1.15 and _fill_w > 8:
                _sw_cx = int(_fill_w * _sweep)
                _sw_s = pygame.Surface((_fill_w, _xp_fill.height), pygame.SRCALPHA)
                for _dx in range(-14, 15):
                    _xx = _sw_cx + _dx
                    if 0 <= _xx < _fill_w:
                        _bell = math.exp(-(_dx * _dx) / 36)
                        _a = int(150 * _bell)
                        if _a > 0:
                            pygame.draw.line(_sw_s, (255, 230, 255, _a), (_xx, 0), (_xx, _xp_fill.height))
                screen.blit(_sw_s, (_xp_fill.left, _xp_fill.top))
        for _ti in range(1, 10):
            _tx = _xp_x + int(_xp_w * _ti / 10)
            pygame.draw.line(screen, (60, 42, 82), (_tx, _xp_y + 1), (_tx, _xp_y + _xp_h - 1))

    # ── Tooltip for passive ──
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
    elif hovered_potion is not None and hovered_pot_slot is not None:
        draw_item_tooltip(screen, hovered_potion, hovered_pot_slot, font, small_font)

    return _slot_rects_out, _pot_rects_out