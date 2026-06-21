"""Sprite review grid: every animal kind x state x animation phase, rendered
at in-game scale then nearest-neighbour upscaled 3x so actual pixels are
visible. Saved to _visual_review/animal_grid.png."""
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame
pygame.init()
pygame.display.set_mode((1, 1))
import main
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_visual_review")

CELL_W, CELL_H = 72, 60
PHASES = [0.06, 0.21, 0.38, 0.55]

rows = [
    ("hen white", lambda su, x, y, st, tt, ff: main._draw_live_chicken(su, x, y, ff, (238, 228, 208), st, tt, 1.0, False),
     ["idle", "peck", "walk"], (110, 92, 66)),
    ("hen brown", lambda su, x, y, st, tt, ff: main._draw_live_chicken(su, x, y, ff, (182, 124, 62), st, tt, 1.0, False),
     ["idle", "peck", "walk"], (110, 92, 66)),
    ("rooster", lambda su, x, y, st, tt, ff: main._draw_live_chicken(su, x, y, ff, (170, 52, 28), st, tt, 1.4, True),
     ["idle", "peck", "walk"], (110, 92, 66)),
    ("pig", lambda su, x, y, st, tt, ff: main._draw_live_pig(su, x, y, ff, (226, 182, 158), st, tt, 1.1),
     ["idle", "root", "walk", "mud"], (96, 78, 54)),
    ("sheep", lambda su, x, y, st, tt, ff: main._draw_live_sheep(su, x, y, ff, (224, 220, 212), st, tt, 1.05),
     ["idle", "graze", "walk"], (62, 88, 46)),
]

max_cols = max(len(states) * len(PHASES) + 1 for _, _, states, _ in rows)
grid = pygame.Surface((max_cols * CELL_W, len(rows) * CELL_H))
grid.fill((40, 34, 26))

for ri, (label, fn, states, bg) in enumerate(rows):
    ci = 0
    for st in states:
        for ph in PHASES:
            cx = ci * CELL_W
            cy = ri * CELL_H
            pygame.draw.rect(grid, bg, (cx + 1, cy + 1, CELL_W - 2, CELL_H - 2))
            fn(grid, cx + CELL_W // 2, cy + CELL_H // 2 + 8, st, ph, 1)
            ci += 1
    # last cell: facing flip check (idle)
    cx = ci * CELL_W
    cy = ri * CELL_H
    pygame.draw.rect(grid, bg, (cx + 1, cy + 1, CELL_W - 2, CELL_H - 2))
    fn(grid, cx + CELL_W // 2, cy + CELL_H // 2 + 8, "idle", 0.3, -1)

big = pygame.transform.scale(grid, (grid.get_width() * 3, grid.get_height() * 3))
pygame.image.save(big, os.path.join(OUT, "animal_grid.png"))
print("saved animal_grid.png", big.get_size(), flush=True)
