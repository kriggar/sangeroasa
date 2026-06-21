"""game/loaders.py — rogue choices, class visuals, vendor archetype & NPC sprite loaders."""
import os
import math
import random
from typing import Dict, List, Optional, Tuple, Any, Union, Set

import pygame
from pygame import Vector2

from game.constants import *
from game.utils import *
from game.sprites import *
from game.classes_runtime import *
from game.render.props import *

__all__ = [
    'load_rogue_choices',
    'build_class_visuals',
    'load_vendor_archetypes',
    'load_npc_sprites',
]


def load_rogue_choices(max_choices: int = 32) -> List[Dict[str, Union[pygame.Surface, str]]]:
    try:
        sheet_path = "assets/rogues.png"
        if not os.path.exists(sheet_path):
            raise FileNotFoundError(f"Rogue sheet not found at {sheet_path}")
        sheet = pygame.image.load(sheet_path).convert_alpha()
    except (pygame.error, FileNotFoundError):
        return []

    tile_size = 32
    cols = sheet.get_width() // tile_size
    rows = sheet.get_height() // tile_size

    labels: List[str] = []
    try:
        with open("assets/rogues.txt", "r", encoding="utf-8") as f:
            labels = [line.strip() for line in f.readlines() if line.strip()]
    except OSError:
        labels = []

    choices: List[Dict[str, Union[pygame.Surface, str]]] = []
    label_idx = 0

    for row in range(rows):
        for col in range(cols):
            rect = pygame.Rect(col * tile_size, row * tile_size, tile_size, tile_size)

            tile = pygame.Surface((tile_size, tile_size), pygame.SRCALPHA)
            tile.blit(sheet, (0, 0), rect)

            bbox = tile.get_bounding_rect(min_alpha=1)
            if bbox.width == 0 or bbox.height == 0:
                continue

            if label_idx < len(labels):
                raw_label = labels[label_idx]
                name = raw_label.split(". ", 1)[1] if ". " in raw_label else raw_label
            else:
                name = f"rogue {label_idx + 1}"
            label_idx += 1

            pixel_count = 0
            for py in range(tile_size):
                for px in range(tile_size):
                    if tile.get_at((px, py)).a > 0:
                        pixel_count += 1

            # Skip malformed tiles from the sheet.
            if not (220 <= pixel_count <= 700 and 14 <= bbox.width <= 31 and 22 <= bbox.height <= 32):
                continue

            sprite = pygame.transform.scale(tile, (96, 96))
            sprite_left = pygame.transform.flip(sprite, True, False)
            preview = pygame.transform.scale(tile, (64, 64))

            choices.append(
                {
                    "name": name,
                    "sprite": sprite,
                    "sprite_left": sprite_left,
                    "preview": preview,
                }
            )
            if len(choices) >= max_choices:
                return choices

    return choices


def build_class_visuals(
    choices: List[Dict[str, Union[pygame.Surface, str]]],
) -> Dict[str, Dict[str, Union[pygame.Surface, str]]]:
    keywords = {
        "mage": ["female wizard", "male wizard", "dwarf mage", "druid", "desert sage"],
        "rogue": ["rogue", "bandit", "ranger", "fencer"],
        "necromancer": ["warlock", "elder schema monk", "desert sage", "male wizard"],
        "ranger": ["ranger", "elf", "hunter", "archer"],
        "warrior": ["male fighter", "swordsman", "male barbarian", "female barbarian", "shield knight"],
        "paladin": ["templar", "knight", "male war cleric", "female war cleric", "priest"],
    }

    used_idxs: Set[int] = set()
    visuals: Dict[str, Dict[str, Union[pygame.Surface, str]]] = {}

    for class_id in CLASS_ORDER:
        selected_idx = -1
        class_keywords = keywords.get(class_id, [])
        for key in class_keywords:
            for idx, entry in enumerate(choices):
                if idx in used_idxs:
                    continue
                name = str(entry.get("name", "")).lower()
                if key in name:
                    selected_idx = idx
                    break
            if selected_idx >= 0:
                break

        if selected_idx < 0:
            for idx, _ in enumerate(choices):
                if idx not in used_idxs:
                    selected_idx = idx
                    break

        if selected_idx >= 0:
            used_idxs.add(selected_idx)
            visuals[class_id] = choices[selected_idx]

    return visuals


def load_vendor_archetypes() -> List[Dict[str, Union[pygame.Surface, str]]]:
    try:
        sheet = pygame.image.load("assets/rogues.png").convert_alpha()
    except (pygame.error, FileNotFoundError):
        return []
    tile_size = 32
    cols = sheet.get_width() // tile_size
    rows = sheet.get_height() // tile_size

    labels: List[str] = []
    try:
        with open("assets/rogues.txt", "r", encoding="utf-8") as f:
            labels = [line.strip() for line in f.readlines() if line.strip()]
    except OSError:
        labels = []

    vendor_rows = [rows - 1, max(0, rows - 2)]
    tiles: List[pygame.Surface] = []
    for row in vendor_rows:
        for col in range(cols):
            rect = pygame.Rect(col * tile_size, row * tile_size, tile_size, tile_size)
            tile = pygame.Surface((tile_size, tile_size), pygame.SRCALPHA)
            tile.blit(sheet, (0, 0), rect)
            if tile.get_bounding_rect(min_alpha=1).width > 0:
                tiles.append(tile)

    row_labels: List[str] = []
    if labels:
        for row in vendor_rows:
            start = max(0, row * cols)
            end = min(len(labels), start + cols)
            if start < end:
                row_labels.extend(labels[start:end])
    archetypes: List[Dict[str, Union[pygame.Surface, str]]] = []
    for idx, tile in enumerate(tiles):
        sprite = pygame.transform.scale(tile, (96, 96))
        sprite_left = pygame.transform.flip(sprite, True, False)

        if idx < len(row_labels):
            raw = row_labels[idx]
            name = raw.split(". ", 1)[1] if ". " in raw else raw
        else:
            name = f"vendor {idx + 1}"

        archetypes.append({"name": name, "sprite": sprite, "sprite_left": sprite_left})

    return archetypes


def load_npc_sprites() -> Tuple[List[Dict[str, Union[pygame.Surface, str]]], List[Dict[str, Union[pygame.Surface, str]]]]:
    """Load specific rows for Guards (Knights) and Citizens (Peasants)."""
    try:
        sheet = pygame.image.load("assets/rogues.png").convert_alpha()
    except (pygame.error, FileNotFoundError):
        return [], []
    tile_size = 32
    cols = sheet.get_width() // tile_size
    
    def load_row(row_idx: int, base_name: str) -> List[Dict[str, Union[pygame.Surface, str]]]:
        out = []
        for col in range(cols):
            rect = pygame.Rect(col * tile_size, row_idx * tile_size, tile_size, tile_size)
            tile = pygame.Surface((tile_size, tile_size), pygame.SRCALPHA)
            tile.blit(sheet, (0, 0), rect)
            if tile.get_bounding_rect(min_alpha=1).width > 0:
                sprite = pygame.transform.scale(tile, (96, 96))
                sprite_left = pygame.transform.flip(sprite, True, False)
                out.append({
                    "name": f"{base_name} {col+1}",
                    "sprite": sprite,
                    "sprite_left": sprite_left
                })
        return out

    # Row 1 (index 1): Knights/Fighters -> Guards
    # Row 7 (index 7): Peasants -> Citizens
    # Row 6 (index 6): Farmers -> Citizens
    guards = load_row(1, "Guard")
    citizens = load_row(7, "Citizen")
    citizens.extend(load_row(6, "Citizen"))
    return guards, citizens
