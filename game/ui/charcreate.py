"""game/ui/charcreate.py — character creation screens (class/name/rogue-sprite pickers)."""
import math
import random
from typing import Dict, List, Optional, Tuple, Any

import pygame
from pygame import Vector2

from game.constants import *
from game.utils import *
from game.classes_runtime import *
from game.items import *
from game.render.props import *
from game.sprites import *

__all__ = [
    'choose_rogue_sprite',
    'choose_character_name',
    'choose_class',
]


def choose_rogue_sprite(
    screen: pygame.Surface,
    clock: pygame.time.Clock,
    choices: List[Dict[str, Union[pygame.Surface, str]]],
    initial_index: int = 0,
) -> int:
    if not choices:
        return 0

    title_font = pygame.font.SysFont("georgia", 44, bold=True)
    name_font = pygame.font.SysFont("georgia", 18)
    hint_font = pygame.font.SysFont("georgia", 24, bold=True)
    info_font = pygame.font.SysFont("georgia", 20)

    columns = 8
    cell_w = 162
    cell_h = 148
    rows = (len(choices) + columns - 1) // columns
    grid_w = columns * cell_w
    start_x = (SCREEN_WIDTH - grid_w) // 2
    start_y = 122

    selected = int(clamp(initial_index, 0, len(choices) - 1))
    hover = -1

    pygame.mouse.set_visible(True)

    def tile_rect(index: int) -> pygame.Rect:
        col = index % columns
        row = index // columns
        return pygame.Rect(start_x + col * cell_w + 8, start_y + row * cell_h + 8, cell_w - 16, cell_h - 16)

    def hit_test(pos: Tuple[int, int]) -> int:
        for i in range(len(choices)):
            if tile_rect(i).collidepoint(pos):
                return i
        return -1

    while True:
        if not pygame.mouse.get_visible():
            pygame.mouse.set_visible(True)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                raise SystemExit
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return selected
                if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    return selected
                if event.key == pygame.K_RIGHT:
                    selected = min(len(choices) - 1, selected + 1)
                elif event.key == pygame.K_LEFT:
                    selected = max(0, selected - 1)
                elif event.key == pygame.K_UP:
                    selected = max(0, selected - columns)
                elif event.key == pygame.K_DOWN:
                    selected = min(len(choices) - 1, selected + columns)
            if event.type == pygame.MOUSEMOTION:
                hover = hit_test(event.pos)
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                hit = hit_test(event.pos)
                if hit >= 0:
                    return hit

        draw_vertical_gradient(screen, pygame.Rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT), (12, 16, 30), (28, 30, 36))

        title = title_font.render("Choose Your Rogue (32 Sprites)", True, (220, 222, 226))
        screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 28))

        hint = info_font.render("Click a sprite or use arrows + Enter", True, (184, 176, 156))
        screen.blit(hint, (SCREEN_WIDTH // 2 - hint.get_width() // 2, 74))

        for idx, choice in enumerate(choices):
            rect = tile_rect(idx)
            is_focus = idx == selected or idx == hover
            fill = (66, 68, 74) if is_focus else (44, 46, 52)
            border = (212, 188, 120) if is_focus else (90, 92, 100)
            pygame.draw.rect(screen, fill, rect, border_radius=8)
            pygame.draw.rect(screen, border, rect, 2, border_radius=8)

            preview = choice["preview"]
            if isinstance(preview, pygame.Surface):
                screen.blit(preview, (rect.centerx - preview.get_width() // 2, rect.top + 12))

            idx_label = name_font.render(f"{idx + 1:02d}", True, (238, 214, 148))
            screen.blit(idx_label, (rect.left + 10, rect.top + 8))

            name = str(choice["name"])
            if len(name) > 18:
                name = name[:15] + "..."
            name_surf = name_font.render(name, True, (224, 226, 230))
            screen.blit(name_surf, (rect.centerx - name_surf.get_width() // 2, rect.bottom - 26))

        selected_name = str(choices[selected]["name"])
        footer = hint_font.render(f"Selected: {selected_name}", True, (226, 202, 134))
        screen.blit(footer, (SCREEN_WIDTH // 2 - footer.get_width() // 2, SCREEN_HEIGHT - 76))

        sub_footer = info_font.render("Press C in town to change character again", True, (172, 170, 164))
        screen.blit(sub_footer, (SCREEN_WIDTH // 2 - sub_footer.get_width() // 2, SCREEN_HEIGHT - 44))

        pygame.display.flip()
        clock.tick_busy_loop(FPS)


def choose_character_name(
    screen: pygame.Surface,
    clock: pygame.time.Clock,
    sprite: pygame.Surface,
    current_name: str = "Rogue",
) -> str:
    title_font = pygame.font.SysFont("georgia", 46, bold=True)
    input_font = pygame.font.SysFont("georgia", 38, bold=True)
    hint_font = pygame.font.SysFont("georgia", 22)
    max_len = 18
    name = (current_name or "Rogue").strip()[:max_len]

    cursor_timer = 0.0
    show_cursor = True
    pygame.mouse.set_visible(True)

    while True:
        if not pygame.mouse.get_visible():
            pygame.mouse.set_visible(True)
        clock.tick_busy_loop(FPS)
        dt = FRAME_DT
        cursor_timer += dt
        if cursor_timer >= 0.5:
            cursor_timer = 0.0
            show_cursor = not show_cursor

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                raise SystemExit
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return name if name else "Rogue"
                if event.key == pygame.K_RETURN:
                    return name if name else "Rogue"
                if event.key == pygame.K_BACKSPACE:
                    name = name[:-1]
                elif event.unicode and event.unicode.isprintable():
                    if len(name) < max_len:
                        name += event.unicode

        draw_vertical_gradient(screen, pygame.Rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT), (14, 18, 34), (34, 36, 40))

        title = title_font.render("Name Your Character", True, (222, 224, 228))
        screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 72))

        preview_box = pygame.Rect(SCREEN_WIDTH // 2 - 90, 170, 180, 170)
        pygame.draw.rect(screen, (46, 48, 54), preview_box, border_radius=12)
        pygame.draw.rect(screen, (112, 114, 124), preview_box, 2, border_radius=12)
        screen.blit(sprite, (preview_box.centerx - sprite.get_width() // 2, preview_box.bottom - sprite.get_height() - 12))

        input_box = pygame.Rect(SCREEN_WIDTH // 2 - 320, 396, 640, 88)
        pygame.draw.rect(screen, (52, 54, 60), input_box, border_radius=10)
        pygame.draw.rect(screen, (184, 170, 130), input_box, 2, border_radius=10)

        text_display = name
        if show_cursor:
            text_display += "_"
        if not text_display:
            text_display = "_"
        name_surface = input_font.render(text_display, True, (236, 238, 242))
        screen.blit(name_surface, (input_box.centerx - name_surface.get_width() // 2, input_box.centery - name_surface.get_height() // 2))

        hint = hint_font.render("Type a name and press Enter. Esc keeps current name.", True, (188, 182, 166))
        screen.blit(hint, (SCREEN_WIDTH // 2 - hint.get_width() // 2, 514))

        char_count = hint_font.render(f"{len(name)}/{max_len}", True, (160, 160, 166))
        screen.blit(char_count, (input_box.right - char_count.get_width() - 16, input_box.bottom + 10))

        pygame.display.flip()


def choose_class(
    screen: pygame.Surface,
    clock: pygame.time.Clock,
    class_visuals: Dict[str, Dict[str, Union[pygame.Surface, str]]],
    initial_index: int = 0,
) -> str:
    classes = [CLASS_ARCHETYPES[cid] for cid in CLASS_ORDER]
    selected = int(clamp(initial_index, 0, len(classes) - 1))
    hover = -1

    title_font = pygame.font.SysFont("georgia", 48, bold=True)
    name_font  = pygame.font.SysFont("georgia", 22, bold=True)
    desc_font  = pygame.font.SysFont("georgia", 13)
    lore_font  = pygame.font.SysFont("georgia", 13, italic=True)
    hint_font  = pygame.font.SysFont("georgia", 18)

    # Class accent colours used for card glow/border
    _class_col: Dict[str, Tuple[int, int, int]] = {
        "mage":        (100, 140, 220),
        "rogue":       (130, 180, 130),
        "ranger":      (160, 200, 110),
        "necromancer": (170, 100, 200),
        "warrior":     (210, 130,  70),
        "paladin":     (230, 200,  90),
    }

    cols = 3
    card_w = 340
    card_h = 230
    grid_w = cols * card_w + (cols - 1) * 20
    start_x = (SCREEN_WIDTH - grid_w) // 2
    start_y = 150
    pygame.mouse.set_visible(True)

    def _ensure_cursor():
        if not pygame.mouse.get_visible():
            pygame.mouse.set_visible(True)

    def card_rect(idx: int) -> pygame.Rect:
        row = idx // cols
        col = idx % cols
        x = start_x + col * (card_w + 20)
        y = start_y + row * (card_h + 20)
        if row == 1 and len(classes) % cols != 0:
            leftover = len(classes) % cols
            x += (cols - leftover) * (card_w + 20) // 2
        return pygame.Rect(x, y, card_w, card_h)

    def hit_test(pos: Tuple[int, int]) -> int:
        for idx in range(len(classes)):
            if card_rect(idx).collidepoint(pos):
                return idx
        return -1

    def wrap_text(text: str, font: pygame.font.Font, max_w: int) -> List[str]:
        words = text.split()
        lines: List[str] = []
        cur = ""
        for w in words:
            test = (cur + " " + w).strip()
            if font.size(test)[0] <= max_w:
                cur = test
            else:
                if cur:
                    lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        return lines

    while True:
        _ensure_cursor()
        ticks = pygame.time.get_ticks()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                raise SystemExit
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return CLASS_ORDER[selected]
                if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    return CLASS_ORDER[selected]
                if event.key == pygame.K_RIGHT:
                    selected = min(len(classes) - 1, selected + 1)
                elif event.key == pygame.K_LEFT:
                    selected = max(0, selected - 1)
                elif event.key == pygame.K_UP:
                    selected = max(0, selected - cols)
                elif event.key == pygame.K_DOWN:
                    selected = min(len(classes) - 1, selected + cols)
                elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5, pygame.K_6):
                    idx = event.key - pygame.K_1
                    if 0 <= idx < len(classes):
                        return CLASS_ORDER[idx]
            if event.type == pygame.MOUSEMOTION:
                hover = hit_test(event.pos)
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                hit = hit_test(event.pos)
                if hit >= 0:
                    return CLASS_ORDER[hit]

        # ── Background ──────────────────────────────────────────────
        draw_vertical_gradient(screen, pygame.Rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT), (6, 8, 18), (20, 22, 32))

        # Ambient particle field (drifting motes)
        for pi in range(18):
            _phase = (ticks * 0.0006 + pi * 0.35) % (2 * math.pi)
            _px = int((pi * 137 + 60) % SCREEN_WIDTH)
            _py = int(((ticks * 0.025 + pi * 80) % SCREEN_HEIGHT))
            _pa = int(40 + 30 * math.sin(_phase))
            _ps = pygame.Surface((3, 3), pygame.SRCALPHA)
            pygame.draw.circle(_ps, (180, 170, 130, _pa), (1, 1), 1)
            screen.blit(_ps, (_px, _py))

        # ── Title ───────────────────────────────────────────────────
        _title_pulse = int(220 + 20 * math.sin(ticks * 0.0014))
        title_s = title_font.render("Choose Your Fate", True, (_title_pulse, _title_pulse - 10, _title_pulse - 30))
        screen.blit(title_s, (SCREEN_WIDTH // 2 - title_s.get_width() // 2, 42))

        # Decorative horizontal line under title
        _lx = SCREEN_WIDTH // 2
        _lw = title_s.get_width() + 80
        _la = int(140 + 60 * math.sin(ticks * 0.002))
        _line_surf = pygame.Surface((_lw, 2), pygame.SRCALPHA)
        pygame.draw.line(_line_surf, (200, 170, 80, _la), (0, 0), (_lw, 0), 2)
        screen.blit(_line_surf, (_lx - _lw // 2, 98))
        # Diamond centre ornament
        _dm = pygame.Surface((10, 10), pygame.SRCALPHA)
        pygame.draw.polygon(_dm, (220, 190, 100, _la), [(5, 0), (10, 5), (5, 10), (0, 5)])
        screen.blit(_dm, (_lx - 5, 94))

        subtitle_s = hint_font.render("Click a class or press 1—6  Â·  Arrow keys to navigate  Â·  Enter to confirm", True, (140, 136, 120))
        screen.blit(subtitle_s, (SCREEN_WIDTH // 2 - subtitle_s.get_width() // 2, 110))

        # ── Class Cards ─────────────────────────────────────────────
        for idx, class_data in enumerate(classes):
            rect = card_rect(idx)
            class_id = CLASS_ORDER[idx]
            is_sel   = (idx == selected)
            is_hover = (idx == hover)
            is_focus = is_sel or is_hover
            acc = _class_col.get(class_id, (160, 160, 160))

            # Outer glow for selected card
            if is_sel:
                _glow_a = int(50 + 30 * math.sin(ticks * 0.003))
                _glow_s = pygame.Surface((rect.width + 16, rect.height + 16), pygame.SRCALPHA)
                pygame.draw.rect(_glow_s, (acc[0], acc[1], acc[2], _glow_a), _glow_s.get_rect(), border_radius=18)
                screen.blit(_glow_s, (rect.left - 8, rect.top - 8))

            # Card BG
            _bg_col = (52, 46, 42) if is_sel else ((42, 38, 42) if is_hover else (28, 28, 34))
            _card_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
            pygame.draw.rect(_card_surf, (_bg_col[0], _bg_col[1], _bg_col[2], 230), _card_surf.get_rect(), border_radius=14)
            screen.blit(_card_surf, rect.topleft)

            # Border
            _brd_a = int(200 + 40 * math.sin(ticks * 0.002 + idx * 0.8)) if is_focus else 120
            _brd_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
            _brd_col = (acc[0], acc[1], acc[2], _brd_a) if is_focus else (80, 80, 90, 120)
            _brd_w = 2 if is_focus else 1
            pygame.draw.rect(_brd_surf, _brd_col, _brd_surf.get_rect(), _brd_w, border_radius=14)
            screen.blit(_brd_surf, rect.topleft)

            # Corner filigree dots
            for _cx2, _cy2 in [(rect.left + 6, rect.top + 6), (rect.right - 6, rect.top + 6),
                                (rect.left + 6, rect.bottom - 6), (rect.right - 6, rect.bottom - 6)]:
                _fa = int(160 + 60 * math.sin(ticks * 0.0018 + idx)) if is_focus else 80
                _fs = pygame.Surface((4, 4), pygame.SRCALPHA)
                pygame.draw.circle(_fs, (acc[0], acc[1], acc[2], _fa), (2, 2), 2)
                screen.blit(_fs, (_cx2 - 2, _cy2 - 2))

            # Portrait
            visual = resolve_class_visual_entry(class_visuals, class_id, 1)
            preview_surf = visual.get("preview")
            if not isinstance(preview_surf, pygame.Surface):
                sprite = visual.get("sprite")
                if isinstance(sprite, pygame.Surface):
                    preview_surf = pygame.transform.scale(sprite, (72, 72))

            portrait_box = pygame.Rect(rect.centerx - 36, rect.top + 12, 72, 72)
            _pb_surf = pygame.Surface((72, 72), pygame.SRCALPHA)
            pygame.draw.rect(_pb_surf, (20, 20, 26, 200), _pb_surf.get_rect(), border_radius=10)
            if is_focus:
                _port_a = int(180 + 60 * math.sin(ticks * 0.0025 + idx))
                pygame.draw.rect(_pb_surf, (acc[0], acc[1], acc[2], _port_a), _pb_surf.get_rect(), 2, border_radius=10)
            else:
                pygame.draw.rect(_pb_surf, (80, 80, 90, 100), _pb_surf.get_rect(), 1, border_radius=10)
            screen.blit(_pb_surf, portrait_box.topleft)

            if isinstance(preview_surf, pygame.Surface):
                _ps_w, _ps_h = preview_surf.get_width(), preview_surf.get_height()
                screen.blit(preview_surf, (portrait_box.centerx - _ps_w // 2, portrait_box.centery - _ps_h // 2))

            # Floating sparkle above portrait when selected
            if is_sel:
                for _spi in range(4):
                    _sph = (ticks * 0.0014 + _spi * 1.57) % (2 * math.pi)
                    if math.sin(_sph) > 0.5:
                        _spx = portrait_box.left + 8 + (_spi * 18) % (portrait_box.width - 16)
                        _spy = portrait_box.top - 4 + int(5 * math.cos(_sph * 2))
                        _spa = int(200 * ((math.sin(_sph) - 0.5) / 0.5))
                        _sps = pygame.Surface((4, 4), pygame.SRCALPHA)
                        pygame.draw.circle(_sps, (acc[0], acc[1], acc[2], _spa), (2, 2), 2)
                        screen.blit(_sps, (_spx, _spy))

            # Class name
            _name_col = (acc[0], acc[1], acc[2]) if is_focus else (200, 196, 186)
            name_s = name_font.render(f"{idx + 1}. {str(class_data['name'])}", True, _name_col)
            screen.blit(name_s, (rect.centerx - name_s.get_width() // 2, rect.top + 90))

            # Description (single line, truncated)
            desc_text = str(class_data.get("description", ""))
            desc_s = desc_font.render(desc_text, True, (180, 175, 165))
            if desc_s.get_width() > rect.width - 20:
                desc_s = desc_font.render(ellipsize_text(desc_font, desc_text, rect.width - 22), True, (180, 175, 165))
            screen.blit(desc_s, (rect.centerx - desc_s.get_width() // 2, rect.top + 118))

            # Lore (two lines, italic, only for selected/hover)
            lore_text = str(class_data.get("lore", ""))
            if lore_text and is_focus:
                _lore_lines = wrap_text(lore_text, lore_font, rect.width - 24)[:3]
                _lore_alpha = int(200 + 40 * math.sin(ticks * 0.002 + idx)) if is_sel else 160
                for _li, _ll in enumerate(_lore_lines):
                    _ls = lore_font.render(_ll, True, (190, 185, 165))
                    _ls_a = pygame.Surface((_ls.get_width(), _ls.get_height()), pygame.SRCALPHA)
                    _ls_a.blit(_ls, (0, 0))
                    _ls_a.set_alpha(_lore_alpha)
                    screen.blit(_ls_a, (rect.centerx - _ls.get_width() // 2, rect.top + 142 + _li * 16))
            elif not is_focus:
                # Show spell names when not focused
                spells = class_data.get("spellbook", [])
                names = [str(s.get("name", "")) for s in spells[:3] if isinstance(s, dict)]
                _sp_s = desc_font.render("  Â·  ".join(names), True, (140, 138, 128))
                screen.blit(_sp_s, (rect.centerx - _sp_s.get_width() // 2, rect.top + 142))

            # HP/MP tags bottom of card
            stats = CLASS_COMBAT_STATS.get(class_id, {})
            _hp_tag = desc_font.render(f"HP {int(stats.get('max_hp', 0))}", True, (220, 130, 130))
            _mp_tag = desc_font.render(f"MP {int(stats.get('max_mana', 0))}", True, (130, 170, 220))
            screen.blit(_hp_tag, (rect.left + 10, rect.bottom - 22))
            screen.blit(_mp_tag, (rect.right - _mp_tag.get_width() - 10, rect.bottom - 22))

        # ── Footer: Selected class lore panel ───────────────────────
        sel_class_data = classes[selected]
        sel_id = CLASS_ORDER[selected]
        sel_acc = _class_col.get(sel_id, (160, 160, 160))
        _footer_panel = pygame.Rect(start_x, start_y + 2 * (card_h + 20) + 10, grid_w, 72)

        _fp_surf = pygame.Surface((_footer_panel.width, _footer_panel.height), pygame.SRCALPHA)
        pygame.draw.rect(_fp_surf, (14, 14, 20, 210), _fp_surf.get_rect(), border_radius=12)
        _fp_ba = int(150 + 50 * math.sin(ticks * 0.002))
        pygame.draw.rect(_fp_surf, (sel_acc[0], sel_acc[1], sel_acc[2], _fp_ba), _fp_surf.get_rect(), 1, border_radius=12)
        screen.blit(_fp_surf, _footer_panel.topleft)

        _sel_name_s = name_font.render(str(sel_class_data["name"]), True, sel_acc)
        screen.blit(_sel_name_s, (_footer_panel.left + 18, _footer_panel.top + 10))

        _sel_lore = str(sel_class_data.get("lore", str(sel_class_data.get("description", ""))))
        _lore_wrapped = wrap_text(_sel_lore, lore_font, _footer_panel.width - 40)
        for _li2, _ll2 in enumerate(_lore_wrapped[:3]):
            _ls2 = lore_font.render(_ll2, True, (190, 185, 168))
            screen.blit(_ls2, (_footer_panel.left + 18, _footer_panel.top + 34 + _li2 * 14))

        pygame.display.flip()
        clock.tick_busy_loop(FPS)
