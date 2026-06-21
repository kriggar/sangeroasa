"""game/nav.py — pure navigation/geometry helpers (walkability tests).
Bounds + obstacle rects are passed in; no global nav state."""
import math

import pygame
from pygame import Vector2
from typing import List


def is_walkable(pos: Vector2, bounds: pygame.Rect, obstacles: List[pygame.Rect], radius: float = 0.0) -> bool:
    r = int(radius)
    test_rect = pygame.Rect(int(pos.x) - r, int(pos.y) - r, r * 2, r * 2)
    if not bounds.contains(test_rect):
        return False
    for obs in obstacles:
        if test_rect.colliderect(obs):
            return False
    return True


def nearest_walkable(target: Vector2, bounds: pygame.Rect, obstacles: List[pygame.Rect], radius: float = 0.0) -> Vector2:
    if is_walkable(target, bounds, obstacles, radius):
        return target
    for r in range(10, 600, 10):
        for theta in range(0, 360, 30):
            rad = math.radians(theta)
            p = target + Vector2(math.cos(rad), math.sin(rad)) * r
            if is_walkable(p, bounds, obstacles, radius):
                return p
    return target
