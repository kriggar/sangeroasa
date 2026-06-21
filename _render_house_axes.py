"""Focused Phase-3 axis check: tudor + stone houses with the variation layer,
12 seeds each, large cells — verifies dormers, annexes, laundry, woodpiles
render correctly and within bounds. Saves _visual_review/house_axes.png."""
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame
pygame.init()
pygame.display.set_mode((1, 1))
import main

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_visual_review")
CW, CH = 440, 560
COLS, ROWS = 6, 4
sheet = pygame.Surface((COLS * CW, ROWS * CH))
sheet.fill((96, 84, 64))

n_dormer = 0
for i in range(COLS * ROWS):
    cx = (i % COLS) * CW + CW // 2
    cy = (i // COLS) * CH + CH - 70
    pygame.draw.rect(sheet, (62, 54, 42), ((i % COLS) * CW, (i // COLS) * CH, CW, CH), 1)
    style = 0 if i < COLS * 2 else 1                  # 2 rows tudor, 2 rows stone
    seed = 300 + i * 11
    s = 2.0 if style == 0 else 2.6
    fn = main._draw_house_tudor if style == 0 else main._draw_house_stone
    fnd = fn(sheet, cx, cy, s, seed)
    out = main._draw_house_variations(sheet, cx, cy, s, seed, "saint" if i % 2 else "harbor", style, fnd)
    if out.w != fnd.w:
        print(f"cell {i}: annex (w {fnd.w} -> {out.w})")
pygame.image.save(sheet, os.path.join(OUT, "house_axes.png"))
print("saved house_axes.png", flush=True)
