"""Headless smoke test: boots the game loop for a bounded number of frames
under dummy SDL drivers and asserts it runs without raising.

Run:  python tests/smoke_test.py
Exit code 0 = OK, 1 = the game raised before completing the frame budget.

This is the verification harness used while decomposing main.py: after every
extraction, the import test (module-level code) plus this runtime loop should
still pass.
"""
import os
import sys
import json

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

# Make the repo root importable regardless of where this is launched from.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# Seed a deterministic save so the character picker has something to select.
SAVE_PATH = os.path.join(os.path.expanduser("~"), "sangeroasa_save.json")
with open(SAVE_PATH, "w") as f:
    json.dump([{
        "class": "mage",
        "player_name": "SmokeBot",
        "player_level": 5,
        "created_at": 0,
    }], f)

MAX_FRAMES = int(os.environ.get("SMOKE_FRAMES", "180"))

import pygame  # noqa: E402

_orig_flip = pygame.display.flip
_state = {"n": 0}


def _patched_flip(*a, **kw):
    _orig_flip(*a, **kw)
    _state["n"] += 1
    n = _state["n"]
    # Tap SPACE/ENTER through the intro + picker during the first second.
    if n < 120 and n % 15 == 0:
        for key in (pygame.K_SPACE, pygame.K_RETURN):
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, {"key": key, "mod": 0, "unicode": "", "scancode": 0}))
            pygame.event.post(pygame.event.Event(pygame.KEYUP, {"key": key, "mod": 0, "scancode": 0}))
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
    print(f"[smoke] FAIL after {_state['n']} frames: {exc!r}", flush=True)
    sys.exit(1)

print(f"[smoke] OK — ran {_state['n']} frames without error", flush=True)
sys.exit(0)
