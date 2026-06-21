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

```
main.py                  Game entry point and (currently) most of the engine/runtime
game/                    Extracted, importable engine modules
  constants.py             Shared constants
  utils.py                 Small shared helpers
  combat/                  Combat runtime, spells, kits, talents, vfx, feedback
  hud/                     HUD widgets (e.g. orb/globe)
  systems/ ui/ world/      Targets for ongoing extraction from main.py
tools/
  generate_medieval_assets.py   Procedural asset-pack generator
assets/                  Game art, audio, level decor, fonts (authored content)
assets_generated/        Output of local sprite generation (ComfyUI pipeline)
tests/
  smoke_test.py          Headless boot test (dummy SDL drivers, bounded frames)
```

## Development

Verify the game still boots and runs headlessly after a change:

```bash
python -c "import main"          # fast: executes all module-level definitions
python tests/smoke_test.py       # runs the real game loop for ~180 frames headless
```

The runtime writes `assets/level_decor/npc_positions.json` during play, so it may
show as modified after running the game or the smoke test.

## Asset generation

Pixel-art sprites can be generated locally (ComfyUI + SDXL + Pixel Art XL on the GPU)
and saved into `assets_generated/`. Procedural assets are produced by
`tools/generate_medieval_assets.py`.
