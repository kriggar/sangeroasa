"""Headless profiler: enables cProfile during a chosen gameplay/UI window and
prints the per-frame hot functions. Usage: python tests/profile_run.py [mode]
mode: town | skilltree | inventory | combat  (default skilltree)
"""
import os, sys, json, cProfile, pstats, io

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
MODE = sys.argv[1] if len(sys.argv) > 1 else "skilltree"

SAVE = os.path.join(os.path.expanduser("~"), "sangeroasa_save.json")
json.dump([{"class": "mage", "player_name": "Hero", "player_level": 12, "created_at": 0}], open(SAVE, "w"))

import pygame  # noqa: E402
_orig_flip = pygame.display.flip
prof = cProfile.Profile()
st = {"n": 0, "profiling": False}
OPEN = {"skilltree": pygame.K_k, "inventory": pygame.K_i, "character": pygame.K_c}.get(MODE)
PROF_START, PROF_END = 175, 475

def _press(k):
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, {"key": k, "mod": 0, "unicode": "", "scancode": 0}))
    pygame.event.post(pygame.event.Event(pygame.KEYUP, {"key": k, "mod": 0, "scancode": 0}))

def flip(*a, **k):
    _orig_flip(*a, **k)
    st["n"] += 1; n = st["n"]
    if n < 120 and n % 12 == 0:
        for kk in (pygame.K_SPACE, pygame.K_RETURN): _press(kk)
    if OPEN and n == 150: _press(OPEN)          # open the overlay
    if MODE == "combat" and 150 <= n < PROF_END and n % 5 == 0:
        for kk in (pygame.K_q, pygame.K_w, pygame.K_e, pygame.K_d): _press(kk)
    if n == PROF_START:
        prof.enable(); st["profiling"] = True
    if n == PROF_END:
        prof.disable(); st["profiling"] = False
        pygame.event.post(pygame.event.Event(pygame.QUIT))

pygame.display.flip = flip
import main  # noqa: E402
try:
    main.main()
except SystemExit:
    pass

frames = PROF_END - PROF_START
s = io.StringIO()
ps = pstats.Stats(prof, stream=s).sort_stats("tottime")
ps.print_stats(28)
print(f"\n=== PROFILE mode={MODE}, {frames} frames profiled ===")
for line in s.getvalue().splitlines():
    if line.strip() and ("main.py" in line or "game" in line or "function calls" in line or "ncalls" in line or "{" in line):
        print(line)
