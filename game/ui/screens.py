"""game/ui/screens.py — pre-game screens (character selection, intro cinematic) +
ultimate-class factory."""
import math
import random
from typing import Dict, List, Optional, Tuple, Any, Union, Set

import pygame
from pygame import Vector2

from game.constants import *
from game.utils import *
from game.audio import *
from game.gameplay_math import *
from game.sprites import *
from game.classes_runtime import *
from game.data.classes import *
from game.items import *
from game.render.props import *
from game.combat.ultimates import *
from game.ui.hud import *

__all__ = [
    'ULTIMATE_CLASS_MAP',
    'create_ultimate_for_class',
    'character_selection_screen',
    'INTRO_CINEMATIC_DEFAULT_FINAL_CAPTION',
    'INTRO_CINEMATIC_CLASS_FINAL_CAPTIONS',
    'play_intro_cinematic',
]


ULTIMATE_CLASS_MAP: Dict[str, Any] = {
    "mage": MageCataclysmUltimate,
    "rogue": RogueTeleportUltimate,
    "ranger": RangerStormUltimate,
    "necromancer": NecromancerSummonUltimate,
    "warrior": WarriorDashUltimate,
    "paladin": PaladinTransformationUltimate,
}


def create_ultimate_for_class(
    class_id: str,
    spell: Dict[str, object],
    caster_pos: Vector2,
    target_pos: Vector2,
    facing: int,
    bonus_power: float,
    spell_mods: Optional[Dict[str, float]] = None,
    class_damage_mult: float = 1.0,
) -> Optional[UltimateBase]:
    ultimate_cls = ULTIMATE_CLASS_MAP.get(str(class_id))
    if ultimate_cls is None:
        return None
    return ultimate_cls(spell, caster_pos, target_pos, facing, bonus_power, spell_mods, class_damage_mult)

def character_selection_screen(
    screen: pygame.Surface,
    clock: pygame.time.Clock,
    saves: List[Dict],
    class_visuals: Dict[str, Dict[str, Union[pygame.Surface, str]]],
    fonts: Dict[str, pygame.font.Font],
) -> Optional[int]:
    """
    Displays character selection.
    Returns:
        index of selected save (0..N)
        -1 for 'Create New'
        None for 'Quit'
    """
    title_font = fonts["title"]
    info_font = fonts["info"]
    node_font = fonts["node"]
    tiny_font = fonts["tiny"]
    
    selected_idx = 0 if saves else -1

    # Ensure OS cursor is visible on this screen — run_session hides it for
    # the custom in-game cursor, and re-entering the menu used to leave the
    # cursor invisible, making character creation effectively unusable.
    pygame.mouse.set_visible(True)

    while True:
        # Reassert cursor visibility every frame — guards against SDL on
        # Windows silently dropping the first set_visible(True) when the
        # window is still receiving initial focus events (fresh launch bug).
        if not pygame.mouse.get_visible():
            pygame.mouse.set_visible(True)
        screen.fill((12, 14, 18))
        draw_vertical_gradient(screen, pygame.Rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT), (8, 10, 16), (24, 28, 36))
        
        # Title
        title_s = title_font.render("Select Character", True, (220, 210, 190))
        screen.blit(title_s, (SCREEN_WIDTH // 2 - title_s.get_width() // 2, 40))
        
        # Character List
        list_w = 400
        list_x = 100
        list_y = 120
        
        # "Create New" slot
        create_rect = pygame.Rect(list_x, list_y, list_w, 60)
        hover = create_rect.collidepoint(pygame.mouse.get_pos())
        sel = (selected_idx == -1)
        
        pygame.draw.rect(screen, (40, 50, 40) if sel else ((30, 34, 30) if hover else (20, 22, 24)), create_rect, border_radius=8)
        pygame.draw.rect(screen, (120, 200, 120) if sel else (60, 80, 60), create_rect, 2 if sel else 1, border_radius=8)
        create_s = node_font.render("+ Create New Character", True, (180, 220, 180) if sel else (140, 160, 140))
        screen.blit(create_s, (create_rect.centerx - create_s.get_width() // 2, create_rect.centery - create_s.get_height() // 2))
        
        # Existing saves
        for i, save in enumerate(saves):
            rect = pygame.Rect(list_x, list_y + 80 + i * 70, list_w, 60)
            is_sel = (i == selected_idx)
            is_hover = rect.collidepoint(pygame.mouse.get_pos())
            
            bg = (50, 44, 40) if is_sel else ((36, 32, 34) if is_hover else (26, 24, 26))
            border = (220, 180, 100) if is_sel else (80, 80, 90)
            
            pygame.draw.rect(screen, bg, rect, border_radius=8)
            pygame.draw.rect(screen, border, rect, 2 if is_sel else 1, border_radius=8)
            
            name = str(save.get("player_name", "Unknown"))
            cls_id = normalize_class_id(save.get("class", "rogue"))
            cls = str(CLASS_ARCHETYPES.get(cls_id, {}).get("name", cls_id.title()))
            lvl = int(save.get("player_level", 1))
            
            name_s = node_font.render(name, True, (230, 220, 200) if is_sel else (180, 180, 190))
            meta_s = info_font.render(f"Level {lvl} {cls}", True, (160, 150, 120) if is_sel else (120, 120, 130))
            
            screen.blit(name_s, (rect.left + 20, rect.top + 8))
            screen.blit(meta_s, (rect.left + 20, rect.bottom - 24))

        # Preview Panel (Right side)
        preview_rect = pygame.Rect(SCREEN_WIDTH - 500, 120, 360, 500)
        draw_ornate_panel(screen, preview_rect)
        
        if selected_idx >= 0 and selected_idx < len(saves):
            save = saves[selected_idx]
            cls_id = normalize_class_id(save.get("class", "rogue"))
            visual = resolve_class_visual_entry(class_visuals, cls_id, lvl)
            sprite = visual.get("sprite")
            if isinstance(sprite, pygame.Surface):
                # Scale up for preview
                scale = 3
                w, h = sprite.get_width() * scale, sprite.get_height() * scale
                scaled = pygame.transform.scale(sprite, (w, h))
                screen.blit(scaled, (preview_rect.centerx - w // 2, preview_rect.centery - h // 2 - 40))
            
            p_name = node_font.render(str(save.get("player_name", "Hero")), True, (240, 220, 180))
            cls_name = str(CLASS_ARCHETYPES.get(cls_id, {}).get("name", cls_id.title()))
            p_cls = info_font.render(f"Level {save.get('player_level', 1)} {cls_name}", True, (180, 170, 160))
            p_zone = info_font.render("Raven Hollow", True, (140, 140, 150))
            
            screen.blit(p_name, (preview_rect.centerx - p_name.get_width() // 2, preview_rect.bottom - 120))
            screen.blit(p_cls, (preview_rect.centerx - p_cls.get_width() // 2, preview_rect.bottom - 90))
            screen.blit(p_zone, (preview_rect.centerx - p_zone.get_width() // 2, preview_rect.bottom - 60))
            
            play_btn = pygame.Rect(preview_rect.centerx - 80, preview_rect.bottom + 30, 160, 40)
            phover = play_btn.collidepoint(pygame.mouse.get_pos())
            draw_ui_button(screen, play_btn, hovered=phover, text="Enter World", font=node_font)
            
            delete_btn = pygame.Rect(preview_rect.centerx - 60, play_btn.bottom + 16, 120, 30)
            dhover = delete_btn.collidepoint(pygame.mouse.get_pos())
            pygame.draw.rect(screen, (60, 20, 20) if dhover else (40, 10, 10), delete_btn, border_radius=6)
            pygame.draw.rect(screen, (180, 60, 60) if dhover else (120, 40, 40), delete_btn, 1, border_radius=6)
            del_s = tiny_font.render("Delete", True, (220, 160, 160))
            screen.blit(del_s, (delete_btn.centerx - del_s.get_width() // 2, delete_btn.centery - del_s.get_height() // 2))

        elif selected_idx == -1:
            # New Character Preview
            hint = info_font.render("Create a new hero to begin your journey.", True, (160, 160, 170))
            screen.blit(hint, (preview_rect.centerx - hint.get_width() // 2, preview_rect.centery))
            
            create_btn = pygame.Rect(preview_rect.centerx - 80, preview_rect.bottom + 30, 160, 40)
            chover = create_btn.collidepoint(pygame.mouse.get_pos())
            draw_ui_button(screen, create_btn, hovered=chover, text="Create", font=node_font, color=(120, 220, 120))

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return None
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return None
                if event.key == pygame.K_RETURN:
                    return selected_idx
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    # Check list clicks
                    if create_rect.collidepoint(event.pos):
                        selected_idx = -1
                    for i in range(len(saves)):
                        r = pygame.Rect(list_x, list_y + 80 + i * 70, list_w, 60)
                        if r.collidepoint(event.pos):
                            selected_idx = i
                    
                    # Check button clicks
                    if selected_idx >= 0 and selected_idx < len(saves):
                        play_btn = pygame.Rect(preview_rect.centerx - 80, preview_rect.bottom + 30, 160, 40)
                        if play_btn.collidepoint(event.pos):
                            return selected_idx
                        delete_btn = pygame.Rect(preview_rect.centerx - 60, play_btn.bottom + 16, 120, 30)
                        if delete_btn.collidepoint(event.pos):
                            saves.pop(selected_idx)
                            save_all_saves(saves)
                            if selected_idx >= len(saves):
                                selected_idx = max(-1, len(saves) - 1)
                            if not saves:
                                selected_idx = -1
                    elif selected_idx == -1:
                        create_btn = pygame.Rect(preview_rect.centerx - 80, preview_rect.bottom + 30, 160, 40)
                        if create_btn.collidepoint(event.pos):
                            return selected_idx

        pygame.display.flip()
        clock.tick_busy_loop(FPS)


INTRO_CINEMATIC_DEFAULT_FINAL_CAPTION = (
    "You came to Sangeroasa for your own reasons. Gold, truth, vengeance, faith — the valley does not care."
)

INTRO_CINEMATIC_CLASS_FINAL_CAPTIONS: Dict[str, str] = {
    "mage": "Ley-lines bleed beneath this valley. The wolves carry traces of what you came to study.",
    "ranger": "Somewhere in these woods, your trail ends where your sibling's vanished.",
    "rogue": "A bounty brought you here. Someone in Sangeroasa still owes a debt in blood.",
    "necromancer": "The veil is thin in this valley. Wolf-spirits cross it, and you came to master what slips through.",
    "warrior": "You came for monsters, not mercy. Sangeroasa has plenty of both.",
    "paladin": "Your order sent an envoy who never returned. You came to finish what faith began.",
}


def play_intro_cinematic(
    screen: pygame.Surface,
    clock: pygame.time.Clock,
    fonts: Dict[str, pygame.font.Font],
    town_surface: pygame.Surface,
    wilderness_surface: pygame.Surface,
    player_name: str,
    player_class: str,
    start_level: str,
    start_pos: Vector2,
    audio: Optional[GameAudio] = None,
) -> str:
    title_font = fonts["title"]
    body_font = fonts["dialog_text"]
    tiny_font = fonts["tiny"]

    def resolve_final_caption(raw_class: object) -> str:
        key = str(raw_class).strip().lower()
        if key in INTRO_CINEMATIC_CLASS_FINAL_CAPTIONS:
            return INTRO_CINEMATIC_CLASS_FINAL_CAPTIONS[key]
        for class_id, class_data in CLASS_ARCHETYPES.items():
            class_name = str(class_data.get("name", "")).strip().lower()
            if key and key == class_name:
                return INTRO_CINEMATIC_CLASS_FINAL_CAPTIONS.get(class_id, INTRO_CINEMATIC_DEFAULT_FINAL_CAPTION)
        return INTRO_CINEMATIC_DEFAULT_FINAL_CAPTION

    start_level_norm = "wilderness" if str(start_level).strip().lower() == "wilderness" else "town"
    if isinstance(start_pos, Vector2):
        entry_pos = Vector2(start_pos)
    else:
        entry_pos = Vector2(WORLD_WIDTH * 0.5, HORIZON_Y + 760)

    display_name = str(player_name).strip() or "Traveler"
    final_caption = resolve_final_caption(player_class)

    # Per-shot script and timing are centralized for easy tuning.
    shots: List[Dict[str, object]] = [
        {
            "world": "town",
            "focus": Vector2(WORLD_WIDTH * 0.5, HORIZON_Y + 260),
            "drift": Vector2(240.0, 20.0),
            "duration": 3.6,
            "headline": "Sangeroasa",
            "caption": "Old stone. Dim lanterns. A cathedral built over older bones. In Sangeroasa, every alley keeps a secret.",
        },
        {
            "world": "town",
            "focus": Vector2(WORLD_WIDTH * 0.5 - 260.0, HORIZON_Y + 770),
            "drift": Vector2(320.0, -26.0),
            "duration": 3.4,
            "headline": "Raven Hollow",
            "caption": "The gate district never truly sleeps. Merchants, guards, and refugees all pass through — if the dark lets them.",
        },
        {
            "world": "wilderness",
            "focus": Vector2(WILDERNESS_WIDTH * 0.5, HORIZON_Y + 980),
            "drift": Vector2(-420.0, 42.0),
            "duration": 3.8,
            "headline": "The Wilderness",
            "caption": "Beyond the walls, wolf packs rule the trails. Pelts, bones, and venom buy survival — if you return alive.",
        },
        {
            "world": start_level_norm,
            "focus": Vector2(entry_pos),
            "drift": Vector2(180.0, 0.0),
            "duration": 3.8,
            "headline": display_name,
            "caption": final_caption,
        },
    ]

    vignette = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    for i in range(0, 66):
        alpha = int(1 + (i / 65.0) * 4.0)
        rect = pygame.Rect(i, i, SCREEN_WIDTH - i * 2, SCREEN_HEIGHT - i * 2)
        if rect.width > 0 and rect.height > 0:
            pygame.draw.rect(vignette, (0, 0, 0, alpha), rect, width=2, border_radius=26)

    shot_idx = 0
    shot_t = 0.0
    total_t = 0.0
    fade_in_s = 1.05
    current_music_track = ""

    while shot_idx < len(shots):
        clock.tick_busy_loop(FPS)
        dt = FRAME_DT
        total_t += dt
        shot_t += dt

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "QUIT"
            if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE):
                return "DONE"
            if event.type == pygame.MOUSEBUTTONDOWN and event.button in (1, 3):
                return "DONE"

        shot = shots[shot_idx]
        duration = max(0.4, float(shot.get("duration", 3.5)))
        if shot_t >= duration:
            shot_t -= duration
            shot_idx += 1
            continue

        world_name = str(shot.get("world", "town")).strip().lower()
        if world_name == "wilderness":
            level_surface = wilderness_surface if isinstance(wilderness_surface, pygame.Surface) else None
            world_w = WILDERNESS_WIDTH
            world_h = WILDERNESS_HEIGHT
            target_track = "wilderness"
        else:
            level_surface = town_surface if isinstance(town_surface, pygame.Surface) else None
            world_w = WORLD_WIDTH
            world_h = WORLD_HEIGHT
            target_track = "town"

        if isinstance(audio, GameAudio) and current_music_track != target_track:
            # TODO: add dedicated one-shot bell/wind cinematic stingers when unique ambience assets are available.
            audio.ensure_level_theme(target_track, force=True)
            current_music_track = target_track

        focus_raw = shot.get("focus")
        focus = Vector2(focus_raw) if isinstance(focus_raw, Vector2) else Vector2(world_w * 0.5, world_h * 0.5)
        drift_raw = shot.get("drift")
        drift = Vector2(drift_raw) if isinstance(drift_raw, Vector2) else Vector2(0, 0)
        t = clamp(shot_t / duration, 0.0, 1.0)
        ease = 0.5 - 0.5 * math.cos(math.pi * t)
        cam_focus = (focus - drift * 0.5).lerp(focus + drift * 0.5, ease)

        cam_x = clamp(cam_focus.x - SCREEN_WIDTH * 0.5, 0, max(0, world_w - SCREEN_WIDTH))
        cam_y = clamp(cam_focus.y - SCREEN_HEIGHT * 0.56, 0, max(0, world_h - SCREEN_HEIGHT))

        if isinstance(level_surface, pygame.Surface):
            screen.blit(level_surface, (-int(cam_x), -int(cam_y)))
        else:
            draw_vertical_gradient(screen, pygame.Rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT), (8, 10, 16), (22, 26, 36))

        tint = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        tint.fill((8, 10, 16, 118))
        screen.blit(tint, (0, 0))
        screen.blit(vignette, (0, 0))

        letterbox_t = clamp(total_t / 0.65, 0.0, 1.0)
        bar_h = int(78 * letterbox_t)
        if bar_h > 0:
            pygame.draw.rect(screen, (0, 0, 0), pygame.Rect(0, 0, SCREEN_WIDTH, bar_h))
            pygame.draw.rect(screen, (0, 0, 0), pygame.Rect(0, SCREEN_HEIGHT - bar_h, SCREEN_WIDTH, bar_h))

        edge_fade_s = 0.9
        shot_fade = min(1.0, shot_t / edge_fade_s, (duration - shot_t) / edge_fade_s)
        shot_fade = clamp(shot_fade, 0.0, 1.0)

        panel = pygame.Rect(86, SCREEN_HEIGHT - 212, SCREEN_WIDTH - 172, 134)
        panel_surface = pygame.Surface((panel.width, panel.height), pygame.SRCALPHA)
        pygame.draw.rect(panel_surface, (6, 8, 12, int(196 * shot_fade)), panel_surface.get_rect(), border_radius=12)
        pygame.draw.rect(panel_surface, (176, 146, 102, int(220 * shot_fade)), panel_surface.get_rect(), width=1, border_radius=12)
        screen.blit(panel_surface, panel.topleft)

        headline = str(shot.get("headline", ""))
        caption = str(shot.get("caption", ""))
        txt_alpha = int(255 * shot_fade)

        title_s = title_font.render(headline, True, (238, 220, 188))
        title_s.set_alpha(txt_alpha)
        screen.blit(title_s, (panel.left + 22, panel.top + 10))

        lines = wrap_text_lines(body_font, caption, panel.width - 44, max_lines=3)
        line_y = panel.top + 64
        for line in lines:
            line_s = body_font.render(line, True, (214, 216, 224))
            line_s.set_alpha(txt_alpha)
            screen.blit(line_s, (panel.left + 22, line_y))
            line_y += line_s.get_height() + 4

        hint_s = tiny_font.render("Esc / Space / Enter / Click to skip", True, (164, 172, 188))
        hint_s.set_alpha(int(220 * shot_fade))
        screen.blit(hint_s, (SCREEN_WIDTH - hint_s.get_width() - 16, SCREEN_HEIGHT - 28))

        if total_t < fade_in_s:
            fade_in = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            fade_in.fill((0, 0, 0, int(255 * (1.0 - total_t / fade_in_s))))
            screen.blit(fade_in, (0, 0))

        transition_alpha = int(255 * (1.0 - shot_fade))
        if transition_alpha > 0:
            fade_between = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            fade_between.fill((0, 0, 0, transition_alpha))
            screen.blit(fade_between, (0, 0))

        pygame.display.flip()

    return "DONE"
