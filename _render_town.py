"""Bake the current town scene headless and save an overview + zoomed crops
to _visual_review/ so the layout and detail level can be reviewed."""
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame
pygame.init()
pygame.display.set_mode((1, 1))
import time
import main

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_visual_review")

t0 = time.time()
result = main.build_town_scene(size=(main.WORLD_WIDTH, main.WORLD_HEIGHT), deleted_props=set())
scene = result[0]
house_overlays = result[4]
print(f"built town in {time.time() - t0:.1f}s  size={scene.get_size()}  "
      f"houses={len(house_overlays)}", flush=True)
# composite the runtime house overlays so the render shows the full town
for entry in house_overlays:
    surf, vis_rect = entry[0], entry[1]
    scene.blit(surf, vis_rect.topleft)

# overview
ow = 1500
oh = int(scene.get_height() * ow / scene.get_width())
overview = pygame.transform.smoothscale(scene, (ow, oh))
pygame.image.save(overview, os.path.join(OUT, "town_overview.png"))
print("saved town_overview.png", flush=True)

# zoom crops (world coords): plaza/church centre, market, harbor row, slums
crops = {
    "town_zoom_center.png": (main.WORLD_WIDTH // 2 - 1100, main.HORIZON_Y + 900, 2200, 1500),
    "town_zoom_market.png": (main.WORLD_WIDTH // 2 - 2400, main.HORIZON_Y + 1800, 2200, 1500),
    "town_zoom_eastres.png": (main.WORLD_WIDTH // 2 + 900, main.HORIZON_Y + 500, 2200, 1500),
    "town_zoom_south.png": (main.WORLD_WIDTH // 2 - 1100, main.HORIZON_Y + 4400, 2200, 1500),
}
for name, (cx0, cy0, cw, ch) in crops.items():
    r = pygame.Rect(cx0, cy0, cw, ch).clip(scene.get_rect())
    sub = scene.subsurface(r).copy()
    sub = pygame.transform.smoothscale(sub, (cw * 2 // 3, ch * 2 // 3))
    pygame.image.save(sub, os.path.join(OUT, name))
    print("saved", name, flush=True)
print("done", flush=True)
