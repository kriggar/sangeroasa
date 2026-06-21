import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame
pygame.init()
pygame.display.set_mode((1, 1))
import main
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_visual_review")


def zoomed(fn, seed, factor=4.0, tw=600, th=500, crop_w=300, crop_h=230):
    temp = pygame.Surface((tw, th), pygame.SRCALPHA)
    fn(temp, tw // 2, th // 2, seed=seed)
    crop = pygame.Rect(tw // 2 - crop_w // 2, th // 2 - crop_h // 2, crop_w, crop_h)
    sub = temp.subsurface(crop).copy()
    return pygame.transform.smoothscale(sub, (int(crop_w * factor), int(crop_h * factor)))


def save(name, surf):
    bg = pygame.Surface(surf.get_size())
    bg.fill((96, 80, 56))
    bg.blit(surf, (0, 0))
    pygame.image.save(bg, os.path.join(OUT, name))
    print("saved", name, flush=True)


save("zoom_pig.png", zoomed(main.draw_pig_pen, 3))
save("zoom_chicken.png", zoomed(main.draw_chicken_coop, 1))
print("done", flush=True)
