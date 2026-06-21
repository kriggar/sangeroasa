import os, sys, json
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(os.path.expanduser("~"), "sangeroasa_save.json"), "w") as f:
    json.dump([{"class": "rogue", "player_name": "RogueBot", "player_level": 5, "created_at": 0}], f)
import pygame
from PIL import Image, ImageDraw
_flip = pygame.display.flip
st = {"n": 0, "seqs": {"idle": [], "move": [], "attack": []}, "held": []}
OUT = "assets_generated/rogue_build/fulldemo"
os.makedirs(OUT, exist_ok=True)
K = pygame
ZOOM = 2.4
HALF = 80


def grab(tag):
    s = pygame.display.get_surface()
    if not s:
        return
    im = Image.frombytes("RGBA", s.get_size(), pygame.image.tostring(s, "RGBA"))
    W, H = im.size
    cx, cy = int(W * 0.5), int(H * 0.52)
    c = im.crop((cx - HALF, cy - HALF, cx + HALF, cy + HALF)).resize((int(HALF * 2 * ZOOM),) * 2, Image.NEAREST)
    if len(st["seqs"][tag]) < 8:
        st["seqs"][tag].append(c)


def keys(ks):
    for k in st["held"]:
        if k not in ks:
            pygame.event.post(pygame.event.Event(K.KEYUP, {"key": k, "mod": 0, "scancode": 0}))
    for k in ks:
        pygame.event.post(pygame.event.Event(K.KEYDOWN, {"key": k, "mod": 0, "unicode": "", "scancode": 0}))
    st["held"] = list(ks)


def _f(*a, **k):
    _flip(*a, **k)
    st["n"] += 1
    n = st["n"]
    if n < 120 and n % 15 == 0:
        for key in (K.K_SPACE, K.K_RETURN):
            pygame.event.post(pygame.event.Event(K.KEYDOWN, {"key": key, "mod": 0, "unicode": "", "scancode": 0}))
            pygame.event.post(pygame.event.Event(K.KEYUP, {"key": key, "mod": 0, "scancode": 0}))
    if n == 145:
        grab("idle")
    # movement cycle (hold right), grab consecutive frames
    if 150 <= n <= 210:
        keys([K.K_d])
        if n >= 170 and (n - 170) % 4 == 0:
            grab("move")
    # attack: stop, click repeatedly, grab consecutive frames
    if n == 215:
        keys([])
    if n in (220, 224, 228, 232, 236):
        pos = (980, 430)
        pygame.event.post(pygame.event.Event(K.MOUSEBUTTONDOWN, {"pos": pos, "button": 1}))
        pygame.event.post(pygame.event.Event(K.MOUSEBUTTONUP, {"pos": pos, "button": 1}))
    if 221 <= n <= 245 and n % 3 == 0:
        grab("attack")
    if n >= 250:
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


def strip_gif(tag):
    fr = st["seqs"][tag]
    if not fr:
        return
    w = fr[0].width
    s = Image.new("RGBA", (w * len(fr), w), (44, 40, 46, 255))
    for i, f in enumerate(fr):
        s.alpha_composite(f, (i * w, 0))
    s.convert("RGB").save(os.path.join(OUT, f"{tag}_strip.png"))
    g = [f.convert("P", palette=Image.ADAPTIVE) for f in fr]
    g[0].save(os.path.join(OUT, f"{tag}.gif"), save_all=True, append_images=g[1:], duration=110, loop=0, disposal=2)


for t in ("idle", "move", "attack"):
    strip_gif(t)
# combined overview
rows = [(t, st["seqs"][t]) for t in ("idle", "move", "attack") if st["seqs"][t]]
if rows:
    w = rows[0][1][0].width
    maxn = max(len(s) for _, s in rows)
    M = Image.new("RGBA", (w * maxn + 110, w * len(rows) + 8), (30, 28, 32, 255))
    dd = ImageDraw.Draw(M)
    for ri, (t, s) in enumerate(rows):
        dd.text((6, ri * w + w // 2), t, fill=(240, 230, 235, 255))
        for i, f in enumerate(s):
            M.alpha_composite(f, (110 + i * w, ri * w + 4))
    sc = min(1.0, 1900 / M.width)
    M = M.resize((int(M.width * sc), int(M.height * sc)), Image.LANCZOS)
    M.convert("RGB").save(os.path.join(OUT, "_fulldemo.png"))
print("OK ran", st["n"], "grabs:", {t: len(st["seqs"][t]) for t in st["seqs"]})
