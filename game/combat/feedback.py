from __future__ import annotations

from typing import Any, Iterable, Tuple

from game.utils import clamp


class CombatFeedback:
    """Central combat feedback controller: hit stop, shakes, flashes, and enemy hit flash."""

    def __init__(self) -> None:
        self.hit_stop_remaining = 0.0

    def clear(self) -> None:
        self.hit_stop_remaining = 0.0

    def begin_frame(self, dt: float) -> None:
        if dt <= 0.0:
            return
        self.hit_stop_remaining = max(0.0, self.hit_stop_remaining - dt)

    def filter_world_dt(self, world_dt: float) -> float:
        if self.hit_stop_remaining > 0.0:
            return 0.0
        return max(0.0, float(world_dt))

    def request_hit_stop(self, duration: float) -> None:
        self.hit_stop_remaining = max(self.hit_stop_remaining, max(0.0, float(duration)))

    def apply_enemy_flash(
        self,
        enemy: dict[str, object],
        duration: float = 0.14,
        color: Tuple[int, int, int] = (255, 244, 220),
    ) -> None:
        duration = max(0.04, float(duration))
        enemy["hit_flash_timer"] = max(duration, float(enemy.get("hit_flash_timer", 0.0)))
        enemy["hit_flash_duration"] = max(duration, float(enemy.get("hit_flash_duration", duration)))
        enemy["hit_flash_color"] = tuple(color)

    def update_enemy_flash(self, enemies: Iterable[dict[str, object]], dt: float) -> None:
        if dt <= 0.0:
            return
        for enemy in enemies:
            timer = max(0.0, float(enemy.get("hit_flash_timer", 0.0)) - dt)
            enemy["hit_flash_timer"] = timer

    def register_hit(
        self,
        enemy: dict[str, object],
        damage: float,
        *,
        camera_director: Any = None,
        screen_effects: Any = None,
        flash_color: Tuple[int, int, int] = (255, 244, 220),
        screen_flash_color: Tuple[int, int, int] = (255, 232, 196),
        hit_stop: float = 0.045,
        shake: float = 4.2,
    ) -> None:
        dealt = max(0.0, float(damage))
        if dealt <= 0.0:
            return
        intensity = clamp(0.55 + dealt / 90.0, 0.55, 1.55)
        self.request_hit_stop(hit_stop * intensity)
        self.apply_enemy_flash(enemy, duration=0.14 * intensity, color=flash_color)
        if camera_director is not None:
            camera_director.impulse(shake * intensity, 0.08 + 0.03 * intensity)
        if screen_effects is not None:
            alpha = int(clamp(18.0 + dealt * 1.3, 18.0, 88.0))
            screen_effects.flash(screen_flash_color, alpha=alpha, duration=0.06 + 0.02 * intensity)
