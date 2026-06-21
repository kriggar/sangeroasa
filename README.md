# Sangeroasa

A medieval-fantasy action RPG built with [pygame](https://www.pygame.org/): class-based
characters, a real-time spell/combat system, an explorable town, and farm pens with
wandering animals.

## Run

```bash
python -m pip install -r requirements.txt
python main.py
```

Saves are written to `~/sangeroasa_save.json`.

## Project layout

`main.py` is now just the entry point + the `run_session` game loop; all engine code
lives in focused `game/` modules.

```
main.py                  Entry point: run_session() game loop, main(), choose_launch_mode()
game/
  constants.py             Tuning constants & asset paths (single source of truth)
  state.py                 Shared runtime state (vendor inventories, HUD flash state)
  utils.py                 Pure math/geometry/colour helpers
  gameplay_math.py         Gameplay math (facing, bezier, xp/level, spell VFX themes)
  nav.py                   Walkability / pathing helpers
  vfx.py                   Particle & damage-number spawn/update/draw
  audio.py                 Procedural audio engine (GameAudio)
  sprites.py               Sprite/anim, class visuals, recolour, equipped-sprite, movement
  items.py                 Item metrics, icon building/resolution, tooltips, caches
  classes_runtime.py       Spellbook / skill-tree / passive / stat helpers
  loaders.py               Rogue/class-visual/vendor/NPC loaders
  entities.py              Enemies, wolves, skeletons, passive animals, portals
  farm.py                  Farm animal spawn/AI/rendering
  vendors.py               Vendor placement/update/render, shop positioning
  assets.py                AssetManager (catalog-driven asset pack loader)
  dialogue.py              NPC dialogue + quest-giver logic, DialogueSession
  data/                    Pure data tables (classes, icons, items, quests, world, …)
  render/                  props.py (props/buildings), shops.py, glyphs.py (icon draws)
  combat/                  runtime, spells, kits, talents, vfx, spellcast, ultimates
  systems/core.py          Day/night, weather, particles, status effects, camera, …
  hud/                     Low-level HUD widgets (orb/globe)
  ui/                      hud.py (in-game UI screens), screens.py, charcreate.py
  world/                   scenes.py (town/wilderness/ice), level_decor.py
tools/
  generate_medieval_assets.py   Procedural asset-pack generator
assets/                  Game art, audio, level decor, fonts (authored content)
assets_generated/        Output of local sprite generation (ComfyUI pipeline)
tests/
  smoke_test.py          Headless boot test (dummy SDL, exercises gameplay/menus/spells)
```

## Development

Verify the game still boots and runs headlessly after a change:

```bash
python -c "import main"               # fast: executes all module-level definitions
python tests/smoke_test.py            # runs the real game loop ~180 frames headless
SMOKE_FRAMES=500 python tests/smoke_test.py   # longer run; exercises spells/menus/combat
```

The runtime writes `assets/level_decor/npc_positions.json` during play, so it may
show as modified after running the game or the smoke test.

## Asset generation

Pixel-art sprites can be generated locally (ComfyUI + SDXL + Pixel Art XL on the GPU)
and saved into `assets_generated/`. Procedural assets are produced by
`tools/generate_medieval_assets.py`.
