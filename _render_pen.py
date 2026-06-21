import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame
pygame.init()
pygame.display.set_mode((1, 1))
import main
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_visual_review")


def scaled(fn, seed, factor=3.0, tw=600, th=500):
    temp = pygame.Surface((tw, th), pygame.SRCALPHA)
    fn(temp, tw // 2, th // 2, seed=seed)
    return pygame.transform.smoothscale(temp, (int(tw * factor), int(th * factor)))


def save(name, surf):
    bg = pygame.Surface(surf.get_size()); bg.fill((96, 80, 56)); bg.blit(surf, (0, 0))
    pygame.image.save(bg, os.path.join(OUT, name)); print("saved", name, flush=True)


save("pen_pig.png", scaled(main.draw_pig_pen, 3))
save("pen_chicken.png", scaled(main.draw_chicken_coop, 1))
print("done", flush=True)
