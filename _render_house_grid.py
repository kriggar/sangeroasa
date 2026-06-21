"""House uniqueness review grid: draw_district_house across districts x seeds
(mimicking the overlay-surface bounds used in build_town_scene) so the Phase-3
variation layer (annexes, dormers, laundry, hoists...) can be reviewed.
Saves _visual_review/house_grid_<district>.png sheets."""
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame
pygame.init()
pygame.display.set_mode((1, 1))
import main

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_visual_review")

CELL_W, CELL_H = 360, 480
COLS, ROWS = 6, 3
BG = {"noble": (96, 92, 86), "saint": (104, 96, 78), "artisan": (98, 86, 62),
      "harbor": (110, 100, 80), "shanty": (84, 72, 54)}

for district, sc in (("noble", 0.78), ("saint", 0.85), ("artisan", 0.82),
                     ("harbor", 0.85), ("shanty", 0.62)):
    sheet = pygame.Surface((COLS * CELL_W, ROWS * CELL_H))
    sheet.fill(BG[district])
    for i in range(COLS * ROWS):
        cx = (i % COLS) * CELL_W + CELL_W // 2
        cy = (i // COLS) * CELL_H + CELL_H - 60
        pygame.draw.rect(sheet, (60, 54, 44), ((i % COLS) * CELL_W, (i // COLS) * CELL_H, CELL_W, CELL_H), 1)
        main.draw_district_house(sheet, cx, cy, sc, 900 + i * 7 + hash(district) % 5, district)
    pygame.image.save(sheet, os.path.join(OUT, f"house_grid_{district}.png"))
    print(f"saved house_grid_{district}.png", flush=True)
print("done", flush=True)
