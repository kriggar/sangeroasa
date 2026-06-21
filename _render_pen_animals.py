"""Render each pen at 2x (as in-game) with live animals after a simulated
wander period — verifies the flock spreads across the yard and never overlaps."""
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame
pygame.init()
pygame.display.set_mode((1, 1))
import main
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_visual_review")

W, H = 1000, 760
CX, CY = W // 2, H // 2


def run(name, draw_fn, seed, pen):
    world = pygame.Surface((W, H))
    world.fill((96, 80, 56))
    # bake pen art at 2x like _scale_farm does
    temp = pygame.Surface((600, 500), pygame.SRCALPHA)
    draw_fn(temp, 300, 250, seed=seed)
    scaled = pygame.transform.smoothscale(temp, (1200, 1000))
    world.blit(scaled, (CX - 600, CY - 500))

    animals = main.build_farm_animals([pen])
    for _ in range(40 * 30):                      # 40 simulated seconds @30fps
        main.update_farm_animals(animals, 1.0 / 30.0)
    for a in animals:
        main.draw_farm_animal(world, a, 0, 0, 0)

    # numeric checks: spread + overlap
    import itertools
    pts = [a["pos"] for a in animals]
    min_d, worst = 1e9, None
    for a, b in itertools.combinations(animals, 2):
        d = (a["pos"] - b["pos"]).length()
        need = (main._FARM_ANIMAL_RADIUS.get(a["kind"], 12.0)
                + main._FARM_ANIMAL_RADIUS.get(b["kind"], 12.0))
        if d - need < min_d:
            min_d, worst = d - need, (a["kind"], b["kind"], round(d, 1))
    xs = [p.x for p in pts]
    ys = [p.y for p in pts]
    # any animal inside a building no-go ellipse? (would draw on the roof)
    on_building = 0
    for a in animals:
        blk = a.get("block")
        if not blk:
            continue
        p = a["pos"]
        if any(((p.x - bx) / brx) ** 2 + ((p.y - by) / bry) ** 2 < 1.0
               for bx, by, brx, bry in blk):
            on_building += 1
    print(f"{name}: n={len(animals)}  x-spread={max(xs)-min(xs):.0f}  "
          f"y-spread={max(ys)-min(ys):.0f}  min gap beyond radii={min_d:.1f} {worst}  "
          f"on-building={on_building}")
    pygame.image.save(world, os.path.join(OUT, name))
    print("saved", name, flush=True)


run("anim_chicken.png", main.draw_chicken_coop, 1,
    {"kind": "chicken", "cx": CX, "cy": CY, "hw": 200, "hh": 140})
run("anim_pig.png", main.draw_pig_pen, 3,
    {"kind": "pig", "cx": CX, "cy": CY, "hw": 180, "hh": 120})
print("done", flush=True)
