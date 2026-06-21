"""Captures screenshots from a live game session for visual review."""
import os
import json
import sys

SAVE_PATH = os.path.join(os.path.expanduser("~"), "sangeroasa_save.json")
default_save = [{
    "class": "mage",
    "player_name": "VTester",
    "player_level": 5,
    "created_at": 0,
}]
with open(SAVE_PATH, "w") as f:
    json.dump(default_save, f)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_visual_review")
os.makedirs(OUT, exist_ok=True)
for old in os.listdir(OUT):
    if old.endswith(".png"):
        try: os.remove(os.path.join(OUT, old))
        except OSError: pass

import pygame  # noqa: E402

_orig_flip = pygame.display.flip
_state = {"n": 0, "saved": 0, "skip_sent": 0}

# Frames to save (assuming ~60fps): 1s/3s/8s/14s/20s/26s/35s
SAVE_FRAMES = {60, 180, 480, 840, 1200, 1560, 2100}
MAX_FRAMES = 2400  # ~40 seconds

def _patched_flip(*a, **kw):
    _orig_flip(*a, **kw)
    _state["n"] += 1
    n = _state["n"]
    # Auto-press SPACE every 30 frames during the first ~6s to skip intro slides.
    if n < 360 and n % 30 == 0:
        evt_down = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_SPACE, "mod": 0, "unicode": " ", "scancode": 44})
        evt_up = pygame.event.Event(pygame.KEYUP, {"key": pygame.K_SPACE, "mod": 0, "scancode": 44})
        pygame.event.post(evt_down)
        pygame.event.post(evt_up)
        _state["skip_sent"] += 1
    if n in SAVE_FRAMES:
        try:
            surf = pygame.display.get_surface()
            if surf is not None:
                fname = os.path.join(OUT, f"frame_{n:05d}.png")
                pygame.image.save(surf, fname)
                _state["saved"] += 1
                print(f"[capture] saved {fname}", flush=True)
        except Exception as e:
            print(f"[capture] save failed: {e}", flush=True)
    if n >= MAX_FRAMES:
        pygame.event.post(pygame.event.Event(pygame.QUIT))

pygame.display.flip = _patched_flip

import main  # noqa: E402
try:
    main.main()
except SystemExit:
    pass
print(f"[capture] total saved frames: {_state['saved']}, skip presses: {_state['skip_sent']}", flush=True)
