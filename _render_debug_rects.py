"""No-clip verification: bakes the town, overlays collision/road/landmark
rects on the overview, and runs numeric overlap checks:
  - house drawn-art bounding boxes vs each other (pairwise)
  - house art boxes vs civic landmark footprints
  - obstacles whose center sits on a road (cleanup should leave none)
Saves _visual_review/town_debug_rects.png and prints a report."""
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame
pygame.init()
pygame.display.set_mode((1, 1))
import main

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_visual_review")

result = main.build_town_scene(size=(main.WORLD_WIDTH, main.WORLD_HEIGHT), deleted_props=set())
scene, obstacles, _canals, _registry, overlays, _fol, road_rects, _pens = result
landmarks = list(main._TOWN_LANDMARK_RECTS)
chimneys = list(main._TOWN_CHIMNEY_TOPS)

# world rects of the actual drawn house art (vis rect offset by bounding box)
house_art = []
for ov in overlays:
    surf, vis = ov[0], ov[1]
    style = ov[3] if len(ov) > 3 else "?"
    arch = ov[4] if len(ov) > 4 else surf.get_bounding_rect()
    house_art.append((pygame.Rect(vis.x + arch.x, vis.y + arch.y, arch.w, arch.h), style))
    scene.blit(surf, vis.topleft)

# ── numeric checks ──
pair_overlaps = []
for i in range(len(house_art)):
    for j in range(i + 1, len(house_art)):
        a, sa = house_art[i]
        b, sb = house_art[j]
        if a.colliderect(b):
            c = a.clip(b)
            pair_overlaps.append((sa, sb, c.w, c.h, a.center, b.center))
lm_overlaps = []
for r, st in house_art:
    if st == "church":
        continue
    for lm in landmarks:
        if r.colliderect(lm):
            c = r.clip(lm)
            lm_overlaps.append((st, c.w, c.h))
on_road = 0
for ob in obstacles:
    for rr in road_rects:
        if rr.collidepoint(ob.centerx, ob.centery):
            on_road += 1
            break

print(f"houses={len(house_art)}  obstacles={len(obstacles)}  roads={len(road_rects)}  "
      f"landmarks={len(landmarks)}  chimneys={len(chimneys)}")
print(f"house-vs-house art overlaps: {len(pair_overlaps)}")
for sa, sb, w, h, ca, cb in pair_overlaps[:12]:
    print(f"   {sa}@{ca} x {sb}@{cb}: {w}x{h}px")
print(f"house-vs-landmark overlaps: {len(lm_overlaps)}")
for st, w, h in lm_overlaps[:12]:
    print(f"   {st} vs landmark: {w}x{h}px")
print(f"obstacle centers on roads: {on_road}")

# ── debug overlay render ──
dbg = pygame.Surface(scene.get_size(), pygame.SRCALPHA)
for rr in road_rects:
    pygame.draw.rect(dbg, (60, 110, 220, 28), rr)
for ob in obstacles:
    pygame.draw.rect(dbg, (230, 60, 50, 200), ob, 3)
for r, _st in house_art:
    pygame.draw.rect(dbg, (70, 200, 90, 200), r, 3)
for lm in landmarks:
    pygame.draw.rect(dbg, (240, 200, 60, 220), lm, 4)
for cx, cy in chimneys:
    pygame.draw.circle(dbg, (255, 255, 255, 230), (int(cx), int(cy)), 6, 2)
scene.blit(dbg, (0, 0))
ow = 2000
oh = int(scene.get_height() * ow / scene.get_width())
pygame.image.save(pygame.transform.smoothscale(scene, (ow, oh)),
                  os.path.join(OUT, "town_debug_rects.png"))
print("saved town_debug_rects.png", flush=True)
