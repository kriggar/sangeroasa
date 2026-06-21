"""game/assets.py — AssetManager (catalog-driven asset pack loader) + helpers."""
import os
import json
import math
from typing import Dict, List, Optional, Tuple, Any

import pygame

from game.utils import clamp


def _scale_surface_to_fit(surface: pygame.Surface, max_size: int) -> pygame.Surface:
    width = max(1, int(surface.get_width()))
    height = max(1, int(surface.get_height()))
    scale = min(float(max_size) / float(width), float(max_size) / float(height), 1.0)
    if scale >= 0.999:
        return surface.copy()
    target = (
        max(12, int(round(width * scale))),
        max(12, int(round(height * scale))),
    )
    return pygame.transform.smoothscale(surface, target)


def _humanize_catalog_asset_id(asset_id: str) -> str:
    parts = [part for part in str(asset_id).replace("-", "_").split("_") if part]
    ignore = {"terrain", "nature", "container", "containers", "furniture", "house", "houses", "vfx", "ambient"}
    while parts and parts[0] in ignore:
        parts.pop(0)
    replacements = {
        "ns": "North South",
        "we": "West East",
        "ne": "North East",
        "nw": "North West",
        "se": "South East",
        "sw": "South West",
        "nwe": "North West East",
        "nse": "North South East",
        "nsw": "North South West",
        "swe": "South West East",
    }
    pretty = [replacements.get(part, part.title()) for part in parts]
    return " ".join(pretty) if pretty else "Asset"


class AssetManager:
    def __init__(self, root: str) -> None:
        self.root = root
        self.catalog_path = os.path.join(root, "catalog.json")
        self.overrides_path = os.path.join(root, "catalog_overrides.json")
        self.atlas_json_path = os.path.join(root, "atlas", "atlas.json")
        self.atlas_image_path = os.path.join(root, "atlas", "atlas.png")
        self.entries: List[Dict[str, object]] = []
        self.by_id: Dict[str, Dict[str, object]] = {}
        self._atlas_surface: Optional[pygame.Surface] = None
        self._atlas_sprites: Dict[str, Dict[str, int]] = {}

    def _load_json(self, path: str) -> object:
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, ValueError, json.JSONDecodeError):
            return None

    def _load_atlas(self) -> None:
        self._atlas_surface = None
        self._atlas_sprites = {}
        atlas_json = self._load_json(self.atlas_json_path)
        if not isinstance(atlas_json, dict):
            return
        sprites = atlas_json.get("sprites", {})
        if not isinstance(sprites, dict):
            return
        if os.path.exists(self.atlas_image_path):
            try:
                self._atlas_surface = pygame.image.load(self.atlas_image_path).convert_alpha()
            except pygame.error:
                self._atlas_surface = None
        for key, value in sprites.items():
            if not isinstance(value, dict):
                continue
            try:
                self._atlas_sprites[str(key).replace("\\", "/")] = {
                    "x": int(value.get("x", 0)),
                    "y": int(value.get("y", 0)),
                    "w": int(value.get("w", 0)),
                    "h": int(value.get("h", 0)),
                }
            except (TypeError, ValueError):
                continue

    def _load_surface(self, rel_path: str) -> Optional[pygame.Surface]:
        normalized = str(rel_path).replace("\\", "/")
        abs_path = os.path.join(self.root, normalized)
        if os.path.exists(abs_path):
            try:
                return pygame.image.load(abs_path).convert_alpha()
            except pygame.error:
                pass
        rect = self._atlas_sprites.get(normalized)
        if self._atlas_surface is None or not isinstance(rect, dict):
            return None
        area = pygame.Rect(rect["x"], rect["y"], rect["w"], rect["h"])
        if area.width <= 0 or area.height <= 0:
            return None
        try:
            return self._atlas_surface.subsurface(area).copy()
        except ValueError:
            return None

    def _anchor_offset_for(self, surface: pygame.Surface, origin: object) -> int:
        if not isinstance(surface, pygame.Surface):
            return 0
        if not isinstance(origin, dict):
            return 0
        try:
            origin_y = float(origin.get("y", 1.0))
        except (TypeError, ValueError):
            origin_y = 1.0
        origin_y = clamp(origin_y, 0.0, 1.0)
        return max(0, int(round(float(surface.get_height()) * (1.0 - origin_y))))

    def load(self) -> None:
        self.entries = []
        self.by_id = {}
        self._load_atlas()
        catalog_blob = self._load_json(self.catalog_path)
        overrides_blob = self._load_json(self.overrides_path)
        overrides = overrides_blob if isinstance(overrides_blob, dict) else {}
        raw_assets: List[object]
        if isinstance(catalog_blob, dict):
            assets_raw = catalog_blob.get("assets", [])
            raw_assets = assets_raw if isinstance(assets_raw, list) else []
        elif isinstance(catalog_blob, list):
            raw_assets = catalog_blob
        else:
            raw_assets = []
        for raw_entry in raw_assets:
            if not isinstance(raw_entry, dict):
                continue
            asset_id = str(raw_entry.get("id", "")).strip()
            if not asset_id:
                continue
            merged = dict(raw_entry)
            override = overrides.get(asset_id)
            if isinstance(override, dict):
                merged.update(override)
            rel_path = str(merged.get("path", "")).strip()
            if not rel_path:
                continue
            primary = self._load_surface(rel_path)
            if not isinstance(primary, pygame.Surface):
                continue
            animation_surfaces: List[pygame.Surface] = []
            animation_data = merged.get("animation")
            if isinstance(animation_data, dict):
                frames_raw = animation_data.get("frames", [])
                if isinstance(frames_raw, list):
                    for frame_rel in frames_raw:
                        frame_surface = self._load_surface(str(frame_rel))
                        if isinstance(frame_surface, pygame.Surface):
                            animation_surfaces.append(frame_surface)
            if not animation_surfaces:
                animation_surfaces = [primary]
            origin = merged.get("origin", {"mode": "bottom_center", "x": 0.5, "y": 1.0})
            entry = {
                "id": asset_id,
                "scope": "shared",
                "source": "medieval_generated",
                "asset_pack": "medieval_generated",
                "filename": os.path.basename(rel_path),
                "name": _humanize_catalog_asset_id(asset_id),
                "group": str(merged.get("category", "Generated")),
                "path": os.path.join(self.root, rel_path),
                "surface": primary,
                "thumbnail": _scale_surface_to_fit(primary, 68),
                "size": primary.get_size(),
                "anchor_offset": self._anchor_offset_for(primary, origin),
                "tags": list(merged.get("tags", [])) if isinstance(merged.get("tags"), list) else [],
                "layer": str(merged.get("layer", "OBJECT")).upper(),
                "collision": merged.get("collision") if isinstance(merged.get("collision"), dict) else None,
                "origin": origin if isinstance(origin, dict) else {"mode": "bottom_center", "x": 0.5, "y": 1.0},
                "animation_fps": int(animation_data.get("fps", 0)) if isinstance(animation_data, dict) else 0,
                "animation_surfaces": animation_surfaces,
                "animation": animation_data if isinstance(animation_data, dict) else None,
                "category": str(merged.get("category", "Generated")),
                "variants": list(merged.get("variants", [])) if isinstance(merged.get("variants"), list) else [],
                "variant_index": merged.get("variant_index"),
                "autotile_group": merged.get("autotile_group"),
                "autotile_mask": merged.get("autotile_mask"),
            }
            self.entries.append(entry)
            self.by_id[asset_id] = entry

    def get_asset(self, asset_id: str) -> Optional[Dict[str, object]]:
        entry = self.by_id.get(str(asset_id))
        return entry if isinstance(entry, dict) else None

    def save_override(self, asset_id: str, changes: Dict[str, object]) -> bool:
        if not asset_id or not isinstance(changes, dict):
            return False
        current = self._load_json(self.overrides_path)
        payload = current if isinstance(current, dict) else {}
        existing = payload.get(asset_id, {})
        merged = dict(existing) if isinstance(existing, dict) else {}
        merged.update(changes)
        payload[asset_id] = merged
        os.makedirs(self.root, exist_ok=True)
        try:
            with open(self.overrides_path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
            return True
        except OSError:
            return False
