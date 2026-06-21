import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame
pygame.init()
pygame.display.set_mode((1, 1))
import main
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_visual_review")


def detail(fn, seed, crop, factor=6.0, tw=600, th=500):
    temp = pygame.Surface((tw, th), pygame.SRCALPHA)
    fn(temp, tw // 2, th // 2, seed=seed)
    sub = temp.subsurface(pygame.Rect(crop)).copy()
    return pygame.transform.smoothscale(sub, (int(crop[2] * factor), int(crop[3] * factor)))


def save(name, surf):
    bg = pygame.Surface(surf.get_size())
    bg.fill((96, 80, 56))
    bg.blit(surf, (0, 0))
    pygame.image.save(bg, os.path.join(OUT, name))
    print("saved", name, flush=True)


# henhouse building area (local centre is 300,250)
save("det_coop_house.png", detail(main.draw_chicken_coop, 1, (180, 150, 160, 130)))
# coop yard front: gate, troughs, basket, sack
save("det_coop_yard.png", detail(main.draw_chicken_coop, 1, (240, 240, 180, 110)))
# pig hut + trough + sack
save("det_pig_hut.png", detail(main.draw_pig_pen, 3, (230, 180, 180, 130)))
# pig wallow + bucket + gate
save("det_pig_wallow.png", detail(main.draw_pig_pen, 3, (180, 240, 180, 110)))
print("done", flush=True)
