"""game/state.py — shared mutable runtime state (vendor shop inventories, HUD flash state).
In-place mutated (never reassigned), so safe to share across modules via import."""
from typing import Dict, List

from game.data.world_data import _POTIONS


VENDOR_SHOPS: Dict[str, List[Dict[str, object]]] = {}
VENDOR_SHOPS.update({
    "Herbalist":     [p for p in _POTIONS if p["effect"] in ("hp_60", "hp_80", "mp_80", "full_restore")],
    "Quartermaster": list(_POTIONS),
})
_HUD_STATE: Dict[str, float] = {
    "last_hp": -1.0,
    "last_mana": -1.0,
    "last_xp": -1.0,
    "hp_flash": 0.0,         # white flash on damage taken
    "mp_flash": 0.0,         # cyan flash on mana spend
    "xp_flash": 0.0,         # purple flash on xp gain
    "hp_lag": -1.0,          # lagged HP for "ghost" trailing bar
    "mp_lag": -1.0,
    "level_pop": 0.0,        # bounce on level-up
    "last_level": -1.0,
    "last_tick_ms": -1.0,
}
