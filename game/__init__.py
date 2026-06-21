# Raven Hollow RPG — game package
# This package is the target architecture for splitting main.py.
#
# Intended module layout:
#   game/constants.py   — screen/world dimensions, paths, tuning values
#   game/utils.py       — pure math/geometry helpers (clamp, rotate_vec, …)
#   game/audio.py       — GameAudio class
#   game/world/         — level surfaces, portals, walk bounds
#   game/systems/       — combat, quests, crafting, loot, status effects
#   game/ui/            — HUD, inventory, dialogue, minimap, spell bar
#   game/save.py        — JSON save/load helpers
#   game/assets/        — asset loading, catalog, level decor
