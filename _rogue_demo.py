import os, sys, json
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(os.path.expanduser("~"), "sangeroasa_save.json"), "w") as f:
    json.dump([{"class": "rogue", "player_name": "RogueBot", "player_level": 5, "created_at": 0}], f)
import pygame
from PIL import Image
_flip = pygame.display.flip
st = {"n": 0, "shots": {}, "held": []}
OUT = "assets_generated/rogue_build/demo"
os.makedirs(OUT, exist_ok=True)
K = pygame
SEQ = [("idle", []), ("run_E", [K.K_d]), ("run_S", [K.K_s]), ("run_NW", [K.K_w, K.K_a]),
       ("run_N", [K.K_w]), ("run_W", [K.K_a])]


def grab(tag, zoom):
    s = pygame.display.get_surface()
    if not s:
        return
    im = Image.frombytes("RGBA", s.get_size(), pygame.image.tostring(s, "RGBA"))
    W, H = im.size
    cx, cy = int(W * 0.5), int(H * 0.52)
    h = 95
    c = im.crop((cx - h, cy - h, cx + h, cy + h))
    st["shots"][tag] = c.resize((int(h * 2 * zoom), int(h * 2 * zoom)), Image.NEAREST)


def setkeys(keys):
    for k in st["held"]:
        if k not in keys:
            pygame.event.post(pygame.event.Event(K.KEYUP, {"key": k, "mod": 0, "scancode": 0}))
    for k in keys:
        pygame.event.post(pygame.event.Event(K.KEYDOWN, {"key": k, "mod": 0, "unicode": "", "scancode": 0}))
    st["held"] = list(keys)


def _f(*a, **k):
    _flip(*a, **k)
    st["n"] += 1
    n = st["n"]
    if n < 120 and n % 15 == 0:
        for key in (K.K_SPACE, K.K_RETURN):
            pygame.event.post(pygame.event.Event(K.KEYDOWN, {"key": key, "mod": 0, "unicode": "", "scancode": 0}))
            pygame.event.post(pygame.event.Event(K.KEYUP, {"key": key, "mod": 0, "scancode": 0}))
    if n >= 140:
        idx = (n - 140) // 16
        if idx < len(SEQ):
            tag, keys = SEQ[idx]
            setkeys(keys)
            if (n - 140) % 16 == 12:
                grab(tag, 1.6)
        else:
            setkeys([])
            pygame.event.post(pygame.event.Event(K.QUIT))


pygame.display.flip = _f
import main
try:
    main.main()
except SystemExit:
    pass
except Exception as e:
    import traceback
    traceback.print_exc()
    print("FAIL", repr(e))
    sys.exit(1)

shots = st["shots"]
if shots:
    from PIL import ImageDraw
    order = [s[0] for s in SEQ if s[0] in shots]
    cw = shots[order[0]].width
    cols = 3
    rows = (len(order) + cols - 1) // cols
    M = Image.new("RGBA", (cols * (cw + 6) + 6, rows * (cw + 24) + 6), (44, 40, 46, 255))
    dd = ImageDraw.Draw(M)
    for i, t in enumerate(order):
        x = 6 + (i % cols) * (cw + 6)
        y = 24 + (i // cols) * (cw + 24)
        dd.text((x, y - 16), t, fill=(240, 230, 235, 255))
        M.alpha_composite(shots[t], (x, y))
    M.convert("RGB").save(os.path.join(OUT, "_demo_ingame.png"))
print("OK ran", st["n"], "captured", list(shots.keys()))
