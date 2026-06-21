import os, sys, json
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(os.path.expanduser("~"), "sangeroasa_save.json"), "w") as f:
    json.dump([{"class": "rogue", "player_name": "RogueBot", "player_level": 5, "created_at": 0}], f)
import pygame
from PIL import Image
_flip = pygame.display.flip
st = {"n": 0}
os.makedirs("assets_generated/rogue_build/truescale", exist_ok=True)


def _f(*a, **k):
    _flip(*a, **k)
    st["n"] += 1
    n = st["n"]
    if n < 120 and n % 15 == 0:
        for key in (pygame.K_SPACE, pygame.K_RETURN):
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, {"key": key, "mod": 0, "unicode": "", "scancode": 0}))
            pygame.event.post(pygame.event.Event(pygame.KEYUP, {"key": key, "mod": 0, "scancode": 0}))
    if 150 <= n <= 200:
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_d, "mod": 0, "unicode": "", "scancode": 0}))
    if n == 175:
        s = pygame.display.get_surface()
        im = Image.frombytes("RGBA", s.get_size(), pygame.image.tostring(s, "RGBA"))
        im.convert("RGB").save("assets_generated/rogue_build/truescale/fullscreen.png")
        W, H = im.size
        cx, cy = int(W * 0.5), int(H * 0.52)
        # TRUE scale crop (no upscale) ~ what the player actually sees
        im.crop((cx - 60, cy - 70, cx + 60, cy + 50)).save("assets_generated/rogue_build/truescale/player_truescale.png")
    if n >= 205:
        pygame.event.post(pygame.event.Event(pygame.QUIT))


pygame.display.flip = _f
import main
try:
    main.main()
except SystemExit:
    pass
except Exception as e:
    import traceback
    traceback.print_exc()
    print("BOOT FAIL:", repr(e))
    sys.exit(1)
print("BOOT OK, ran", st["n"], "frames")
