"""
QA Test Runner for Sangeroasa (main.py)
Launches the game and drives it via pyautogui, running a suite of ~60-second
scenarios that cover each major feature. Takes screenshots and logs actions.

Controls reference (from main.py):
  WASD / Arrows       Movement
  Q W E R T 1 2 3     Spell slots
  Left Click          Cast selected spell / interact
  TAB                 Cycle spell / cycle spellbook tab
  I                   Inventory (crafting/backpack)
  B                   Shop (when near vendor) / crafting fallback
  P                   Character sheet
  J                   Quest log
  A                   Accept quest (in quest log)
  T                   Turn in quest (in quest log)
  F                   Fishing (ice biome near rack)
  SPACE               Fishing catch / menu confirm
  F1-F8               Use hotbar items
  ENTER               Craft selected
  ESC                 Close menu
"""
import os, sys, time, subprocess, datetime

import pyautogui
import pygetwindow as gw
import ctypes as _ct
from ctypes import wintypes as _wt

# ── Win32 direct input via PostMessage (works without window focus) ──
_u32 = _ct.WinDLL("user32", use_last_error=True)
_u32.FindWindowW.restype = _wt.HWND
_u32.FindWindowW.argtypes = [_wt.LPCWSTR, _wt.LPCWSTR]
_u32.PostMessageW.argtypes = [_wt.HWND, _ct.c_uint, _wt.WPARAM, _wt.LPARAM]
_u32.SendMessageW.argtypes = [_wt.HWND, _ct.c_uint, _wt.WPARAM, _wt.LPARAM]
_u32.MapVirtualKeyW.argtypes = [_ct.c_uint, _ct.c_uint]
_u32.GetClientRect.argtypes = [_wt.HWND, _ct.POINTER(_wt.RECT)]
_u32.ClientToScreen.argtypes = [_wt.HWND, _ct.POINTER(_wt.POINT)]

WM_KEYDOWN = 0x0100
WM_KEYUP   = 0x0101
WM_CHAR    = 0x0102
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP   = 0x0202
WM_MOUSEMOVE   = 0x0200
MK_LBUTTON = 0x0001

# Virtual key codes
VK = {
    "w": 0x57, "a": 0x41, "s": 0x53, "d": 0x44,
    "q": 0x51, "e": 0x45, "r": 0x52, "t": 0x54,
    "i": 0x49, "b": 0x42, "p": 0x50, "j": 0x4A,
    "1": 0x31, "2": 0x32, "3": 0x33, "4": 0x34,
    "5": 0x35, "6": 0x36,
    "space": 0x20, "enter": 0x0D, "escape": 0x1B, "tab": 0x09,
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73,
    "f5": 0x74, "f6": 0x75, "f7": 0x76, "f8": 0x77,
    "left": 0x25, "up": 0x26, "right": 0x27, "down": 0x28,
}

_GAME_HWND = None

def _hwnd():
    global _GAME_HWND
    if _GAME_HWND:
        return _GAME_HWND
    _GAME_HWND = _u32.FindWindowW(None, WINDOW_TITLE)
    return _GAME_HWND


def _lparam(vk, down=True):
    scan = _u32.MapVirtualKeyW(vk, 0) & 0xFF
    lp = 1 | (scan << 16)
    if not down:
        lp |= (1 << 30) | (1 << 31)
    return lp


def pm_keydown(key):
    h = _hwnd();
    if not h: return
    vk = VK[key]
    _u32.PostMessageW(h, WM_KEYDOWN, vk, _lparam(vk, True))


def pm_keyup(key):
    h = _hwnd();
    if not h: return
    vk = VK[key]
    _u32.PostMessageW(h, WM_KEYUP, vk, _lparam(vk, False))


def pm_tap(key):
    pm_keydown(key)
    time.sleep(0.04)
    pm_keyup(key)


def pm_click(client_x, client_y):
    h = _hwnd()
    if not h: return
    lp = (client_y << 16) | (client_x & 0xFFFF)
    _u32.PostMessageW(h, WM_MOUSEMOVE, 0, lp)
    _u32.PostMessageW(h, WM_LBUTTONDOWN, MK_LBUTTON, lp)
    time.sleep(0.03)
    _u32.PostMessageW(h, WM_LBUTTONUP, 0, lp)


def pm_client_size():
    h = _hwnd()
    r = _wt.RECT()
    _u32.GetClientRect(h, _ct.byref(r))
    return (r.right - r.left, r.bottom - r.top)

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.02

ROOT = os.path.dirname(os.path.abspath(__file__))
SHOT_DIR = os.path.join(ROOT, "qa_screenshots")
os.makedirs(SHOT_DIR, exist_ok=True)

WINDOW_TITLE = "Sangeroasa"
LOG_LINES = []


def log(msg):
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    LOG_LINES.append(line)


def find_window():
    for w in gw.getAllWindows():
        if WINDOW_TITLE.lower() in (w.title or "").lower():
            return w
    return None


import ctypes
from ctypes import wintypes

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_user32.FindWindowW.restype = wintypes.HWND
_user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
_user32.SetForegroundWindow.argtypes = [wintypes.HWND]
_user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
_user32.BringWindowToTop.argtypes = [wintypes.HWND]
_user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
_user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
_user32.GetForegroundWindow.restype = wintypes.HWND
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_kernel32.GetCurrentThreadId.restype = wintypes.DWORD


def _force_foreground(hwnd):
    # Attach input thread trick — reliable FG switch on Win10/11.
    fg = _user32.GetForegroundWindow()
    cur_tid = _kernel32.GetCurrentThreadId()
    fg_tid = _user32.GetWindowThreadProcessId(fg, None)
    tgt_tid = _user32.GetWindowThreadProcessId(hwnd, None)
    _user32.AttachThreadInput(cur_tid, fg_tid, True)
    _user32.AttachThreadInput(cur_tid, tgt_tid, True)
    _user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    _user32.BringWindowToTop(hwnd)
    _user32.SetForegroundWindow(hwnd)
    _user32.AttachThreadInput(cur_tid, fg_tid, False)
    _user32.AttachThreadInput(cur_tid, tgt_tid, False)


def focus_game():
    hwnd = _user32.FindWindowW(None, WINDOW_TITLE)
    if not hwnd:
        # fall back to substring
        w = find_window()
        if not w:
            return False
        hwnd = _user32.FindWindowW(None, w.title)
    if not hwnd:
        return False
    try:
        _force_foreground(hwnd)
    except Exception as e:
        log(f"   focus error: {e}")
    time.sleep(0.2)
    return True


def shot(tag):
    focus_game()
    time.sleep(0.1)
    path = os.path.join(SHOT_DIR, f"{tag}.png")
    try:
        img = pyautogui.screenshot()
        img.save(path)
        log(f"   screenshot -> {path}")
    except Exception as e:
        log(f"   screenshot failed: {e}")


_PYAG_MAP = {"enter": "enter", "escape": "esc", "space": "space", "tab": "tab"}

def _pyag_key(k):
    return _PYAG_MAP.get(k, k)

def press(k, hold=0.0, n=1, gap=0.08):
    focus_game()
    for _ in range(n):
        if hold:
            pyautogui.keyDown(_pyag_key(k)); time.sleep(hold); pyautogui.keyUp(_pyag_key(k))
        else:
            pyautogui.press(_pyag_key(k))
        time.sleep(gap)


def hold(k, dur):
    focus_game()
    pyautogui.keyDown(_pyag_key(k))
    time.sleep(dur)
    pyautogui.keyUp(_pyag_key(k))


def click_center(dx=0, dy=0):
    focus_game()
    w = find_window()
    if not w:
        return
    cx = w.left + w.width // 2 + dx
    cy = w.top + w.height // 2 + dy
    pyautogui.moveTo(cx, cy, duration=0.05)
    pyautogui.click()


def move_mouse_center(dx=0, dy=0):
    cw, ch = pm_client_size()
    h = _hwnd()
    if not h: return
    lp = ((ch // 2 + dy) << 16) | ((cw // 2 + dx) & 0xFFFF)
    _u32.PostMessageW(h, WM_MOUSEMOVE, 0, lp)


def wait_until(pred, timeout=10.0, poll=0.25):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if pred():
            return True
        time.sleep(poll)
    return False


# ============================================================
# Tests
# ============================================================

def test_01_startup():
    log("TEST 1: Startup -> character select -> enter world")
    focus_game()
    time.sleep(2.5)  # allow "Generating World..." to finish
    shot("t01_a_initial")
    # Character select screen: press ENTER to load highlighted character
    press("enter"); time.sleep(1.5)
    shot("t01_b_after_enter")
    # If it's still on a menu (sprite picker / class picker), try SPACE + 1
    press("space"); time.sleep(0.8)
    press("1"); time.sleep(0.4)
    press("space"); time.sleep(1.5)
    shot("t01_c_in_game")
    log("  entered game world")


def test_02_town_walk():
    log("TEST 2: Town exploration / movement (~60s)")
    log("  Walk in all 4 directions, verify movement + camera + collisions")
    focus_game()
    patterns = [("w",1.5), ("d",1.5), ("s",1.5), ("a",1.5),
                ("w",2.0), ("d",2.0), ("s",2.0), ("a",2.0),
                ("w",1.0), ("a",1.0), ("s",1.0), ("d",1.0)]
    for k, dur in patterns:
        log(f"   hold {k.upper()} for {dur}s")
        hold(k, dur)
    shot("t02_town_walked")
    # Sprint-walk loop to explore further
    hold("d", 3.0); hold("w", 3.0); hold("a", 3.0); hold("s", 3.0)
    shot("t02_town_explored")


def test_03_ui_panels():
    log("TEST 3: UI panels — inventory, character, quests, spellbook (~45s)")
    focus_game()
    log("   open inventory (I)")
    press("i"); time.sleep(1.5); shot("t03_a_inventory")
    press("i"); time.sleep(0.5)
    log("   open character sheet (P)")
    press("p"); time.sleep(1.5); shot("t03_b_character")
    press("p"); time.sleep(0.5)
    log("   open quest log (J)")
    press("j"); time.sleep(1.5); shot("t03_c_quests")
    press("j"); time.sleep(0.5)
    log("   cycle spell (TAB)")
    press("tab", n=3, gap=0.4)
    shot("t03_d_spell_cycle")


def test_04_vendor_shop():
    log("TEST 4: Vendor interaction & shop (~60s)")
    focus_game()
    log("   walk looking for a vendor (assume nearby NPC)")
    hold("s", 2.0); hold("d", 2.0)
    shot("t04_a_near_vendor")
    # Click on NPC roughly in screen
    log("   left click center to interact with nearest NPC")
    click_center(0, -50)
    time.sleep(1.2)
    shot("t04_b_npc_menu")
    log("   press B to open shop if vendor")
    press("b"); time.sleep(1.2)
    shot("t04_c_shop_try")
    log("   press 1 to try buy first item")
    press("1"); time.sleep(0.8)
    shot("t04_d_after_buy")
    # (Previously pressed ESC twice here, but discovered that
    # double-ESC exits to character-select without confirmation.)


def test_05_quests_and_professions():
    log("TEST 5: Quests + professions panel (~40s)")
    focus_game()
    press("j"); time.sleep(1.0); shot("t05_a_quest_log")
    press("a"); time.sleep(0.4)
    shot("t05_b_after_accept")
    press("j"); time.sleep(0.4)


def test_06_wilderness_combat():
    log("TEST 6: Wilderness combat (~90s) — leave town and fight")
    focus_game()
    # Head south/east looking for a boundary crossing or combat area
    log("   running south for 6s")
    hold("s", 6.0)
    log("   running east for 6s")
    hold("d", 6.0)
    log("   running west for 4s")
    hold("a", 4.0)
    shot("t06_a_wandered")
    # Spam spell cast attempts
    log("   spamming Q/W/E spells + left click")
    for _ in range(12):
        press("q"); time.sleep(0.15)
        click_center(60, -30)
        time.sleep(0.25)
        press("w"); time.sleep(0.15)
        click_center(-60, 30)
        time.sleep(0.25)
        press("e"); time.sleep(0.15)
        click_center(0, 60)
        time.sleep(0.3)
    shot("t06_b_after_combat")


def test_07_crafting():
    log("TEST 7: Crafting panel (~30s)")
    focus_game()
    press("i"); time.sleep(1.0); shot("t07_a_crafting")
    log("   press ENTER to attempt a craft")
    press("enter"); time.sleep(0.6); shot("t07_b_craft_attempt")
    press("i"); time.sleep(0.4)  # close with I (not ESC)


def test_08_hotbar_items():
    log("TEST 8: Hotbar item use F1..F4 (~20s)")
    focus_game()
    for fk in ("f1", "f2", "f3", "f4"):
        log(f"   press {fk.upper()}")
        press(fk); time.sleep(0.6)
    shot("t08_hotbar")


def test_09_general_feel():
    log("TEST 9: Free play / general feel (~60s)")
    focus_game()
    import random
    random.seed(2)
    end = time.time() + 60
    keys = ["w","a","s","d"]
    spells = ["q","w","e","r","t","1","2","3"]
    while time.time() < end:
        k = random.choice(keys)
        d = random.uniform(0.4, 1.6)
        hold(k, d)
        if random.random() < 0.5:
            press(random.choice(spells))
        if random.random() < 0.3:
            click_center(random.randint(-200,200), random.randint(-150,150))
    shot("t09_free_play_end")


def test_10_save_exit():
    log("TEST 10: Final state capture (no ESC — avoids accidental quit)")
    focus_game()
    # Cycle through a few spells and take a final screenshot
    press("tab", n=2, gap=0.3)
    time.sleep(0.3)
    shot("t10_end")


def main():
    log("=" * 60)
    log("Sangeroasa QA Test Run")
    log("=" * 60)
    # Launch game
    log("Launching main.py ...")
    proc = subprocess.Popen([sys.executable, "main.py"], cwd=ROOT)
    # Wait for window
    ok = wait_until(lambda: find_window() is not None, timeout=25.0)
    if not ok:
        log("FAILED: game window never appeared")
        proc.terminate()
        return
    log("game window detected")
    focus_game()
    time.sleep(1.0)

    tests = [
        test_01_startup,
        test_02_town_walk,
        test_03_ui_panels,
        test_04_vendor_shop,
        test_05_quests_and_professions,
        test_06_wilderness_combat,
        test_07_crafting,
        test_08_hotbar_items,
        test_09_general_feel,
        test_10_save_exit,
    ]
    def close_all_panels():
        # Press each UI toggle twice to guarantee closed (opens+closes if open)
        for k in ("i", "p", "j"):
            pm_tap(k); time.sleep(0.1); pm_tap(k); time.sleep(0.1)

    for t in tests:
        try:
            log("-" * 60)
            focus_game()
            if t is not test_01_startup:
                close_all_panels()
            t()
        except Exception as e:
            log(f"  EXCEPTION in {t.__name__}: {e}")
        if proc.poll() is not None:
            log("GAME CRASHED — process exited")
            break

    log("-" * 60)
    log("Tests complete. Terminating game.")
    try:
        proc.terminate()
        proc.wait(timeout=5)
    except Exception:
        proc.kill()

    logf = os.path.join(SHOT_DIR, "qa_log.txt")
    with open(logf, "w", encoding="utf-8") as f:
        f.write("\n".join(LOG_LINES))
    log(f"Log saved -> {logf}")


if __name__ == "__main__":
    main()
