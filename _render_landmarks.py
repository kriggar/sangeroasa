"""Bake the town and save close-up crops of each Phase-2 civic landmark
(town hall, windmill, granary, washhouse, shrine, south wall + gate,
palisade run) to _visual_review/ for art review."""
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame
pygame.init()
pygame.display.set_mode((1, 1))
import main

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_visual_review")

result = main.build_town_scene(size=(main.WORLD_WIDTH, main.WORLD_HEIGHT), deleted_props=set())
scene = result[0]
for ov in result[4]:
    surf, vis = ov[0], ov[1]
    scene.blit(surf, vis.topleft)

W, H, HY = main.WORLD_WIDTH, main.WORLD_HEIGHT, main.HORIZON_Y
cx = W // 2
sq_cx, sq_cy = cx, HY + 2050

crops = {
    "lm_townhall.png": (sq_cx - 430 - 450, HY + 1640 - 620, 900, 800),
    "lm_windmill.png": (1050 - 400, HY + 3340 - 560, 800, 760),
    "lm_granary.png": (2750 - 350, HY + 4480 - 400, 700, 600),
    "lm_washhouse.png": (W - 880 - 400, HY + 2330 - 350, 800, 560),
    "lm_shrine.png": (cx + 210 - 220, HY + 840 + 160 - 250, 440, 360),
    "lm_southgate.png": (cx - 1000, H - 760, 2000, 720),
    "lm_palisade_w.png": (0, HY + 2600, 500, 900),
    "lm_stocks.png": (sq_cx - 490 - 200, sq_cy + 60 - 200, 400, 320),
}
for name, (x0, y0, w, h) in crops.items():
    r = pygame.Rect(x0, y0, w, h).clip(scene.get_rect())
    sub = scene.subsurface(r).copy()
    if w <= 500:
        sub = pygame.transform.scale(sub, (r.w * 2, r.h * 2))
    pygame.image.save(sub, os.path.join(OUT, name))
    print("saved", name, flush=True)
print("done", flush=True)
