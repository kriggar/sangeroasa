"""Capture real in-game frames headlessly for the README / GitHub page.

Runs the game under dummy SDL drivers, drives it through gameplay + menus, and
saves full-resolution PNGs to docs/screenshots/. Run: python tests/capture_screenshots.py
"""
import os
import sys
import json

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "docs", "screenshots")
os.makedirs(OUT, exist_ok=True)

SAVE_PATH = os.path.join(os.path.expanduser("~"), "sangeroasa_save.json")
with open(SAVE_PATH, "w") as f:
    json.dump([{"class": "mage", "player_name": "Hero", "player_level": 12, "created_at": 0}], f)

import pygame  # noqa: E402

_orig_flip = pygame.display.flip
_state = {"n": 0, "saved": 0}

# frame -> filename to grab; the key cycle below sets up varied views first.
GRABS = {
    210: "01_town.png",
    280: "02_explore.png",
    330: "03_inventory.png",
    380: "04_skilltree.png",
    430: "05_character.png",
    480: "06_combat.png",
    540: "07_world.png",
    600: "08_extra.png",
}
MAX_FRAMES = 640


def _press(key):
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, {"key": key, "mod": 0, "unicode": "", "scancode": 0}))
    pygame.event.post(pygame.event.Event(pygame.KEYUP, {"key": key, "mod": 0, "scancode": 0}))


def _patched_flip(*a, **kw):
    _orig_flip(*a, **kw)
    _state["n"] += 1
    n = _state["n"]
    if n < 120 and n % 12 == 0:
        for k in (pygame.K_SPACE, pygame.K_RETURN):
            _press(k)
    # Drive varied views before each grab.
    if 120 <= n < 270 and n % 3 == 0:
        _press((pygame.K_w, pygame.K_d, pygame.K_a, pygame.K_s)[(n // 3) % 4])
    if n == 320:
        _press(pygame.K_i)            # open inventory
    if n == 360:
        _press(pygame.K_i); _press(pygame.K_k)   # close inv, open skill tree
    if n == 410:
        _press(pygame.K_k); _press(pygame.K_c)   # close, open character
    if 455 <= n < 478:
        _press(pygame.K_c)            # close character
        for k in (pygame.K_q, pygame.K_w, pygame.K_e, pygame.K_r):  # cast spells
            _press(k)
    if n == 520:
        _press(pygame.K_m)            # world map
    if n == 580:
        _press(pygame.K_m)
        _press(pygame.K_b)            # backpack / other panel
    if n in GRABS:
        surf = pygame.display.get_surface()
        if surf is not None:
            path = os.path.join(OUT, GRABS[n])
            pygame.image.save(surf, path)
            _state["saved"] += 1
            print(f"[shot] {path}", flush=True)
    if n >= MAX_FRAMES:
        pygame.event.post(pygame.event.Event(pygame.QUIT))


pygame.display.flip = _patched_flip

import main  # noqa: E402
try:
    main.main()
except SystemExit:
    pass
except Exception as exc:  # noqa: BLE001
    import traceback
    traceback.print_exc()
    print(f"[shot] crashed after {_state['n']} frames: {exc!r}", flush=True)
print(f"[shot] saved {_state['saved']} screenshots to {OUT}", flush=True)
