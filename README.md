<h1 align="center">⚔️ Sângeroasă</h1>

<p align="center">
  <b>A medieval-fantasy action RPG built in Python &amp; pygame.</b><br>
  Pick a class, master a real-time spell &amp; talent system, and explore the living town of <i>Raven Hollow</i> —
  its shops, farms, and the monster-haunted wilderness beyond.
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white">
  <img alt="pygame" src="https://img.shields.io/badge/pygame-2.6-1A8917">
  <img alt="Platform" src="https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-555">
  <img alt="Status" src="https://img.shields.io/badge/status-playable-brightgreen">
</p>

<p align="center">
  <img src="docs/screenshots/01_town.png" alt="Sângeroasă gameplay — the town of Raven Hollow" width="85%">
</p>

---

## 🏰 About

**Sângeroasă** is a single-player, top-down action RPG. You arrive a stranger in the town of
**Raven Hollow**, choose one of six classes, and grow from a level-1 nobody into a hero by completing
quests, crafting gear, and battling the creatures lurking in the wilds and the frozen north.

The whole game — rendering, audio, combat, world generation, UI — is hand-built in Python on top of
**pygame**, with procedurally generated buildings, props, and sound effects.

## ✨ Features

- **6 playable classes** — Mage, Rogue, Ranger, Necromancer, Warrior, Paladin — each with unique
  spells, passives, stats, and a class-specific **ultimate** ability.
- **Real-time combat** — an 8-slot spell bar, basic attacks, status effects, summons, and a deep
  per-class **talent / skill tree** with progressive upgrades.
- **A living town** — a dozen scattered shops (blacksmith, alchemist, tailor, herbalist, baker,
  tanner, miller, cooper, sailor, …) with vendors who walk patrols, plus a town hall, windmill,
  church, gladiator arena, harbour and docks.
- **Farms & wildlife** — animated chicken coops, pig pens and sheep pens with animals that wander,
  flock, and avoid obstacles; passive deer, birds and rats roam the world.
- **Three biomes** — the town, the monster-filled **wilderness**, and a frozen **ice biome**,
  reachable through portals.
- **Quests & professions** — a branching quest line, gathering materials from slain wolves, and
  crafting professions (alchemy, blacksmithing, runecrafting).
- **Atmosphere** — a day/night cycle, dynamic weather, particle VFX, screen effects, ambient
  overlays and a procedural audio engine.
- **An ornate fantasy UI** — gold-bezel HUD with gem HP/MP orbs, minimap, world map, inventory,
  equipment/character sheet, quest log, crafting & profession screens.

## 📸 Screenshots

| Combat & spells | Inventory & gear |
|---|---|
| ![Combat](docs/screenshots/06_combat.png) | ![Inventory](docs/screenshots/03_inventory.png) |

| Talent / skill tree | World map |
|---|---|
| ![Skill tree](docs/screenshots/04_skilltree.png) | ![World map](docs/screenshots/07_world.png) |

## 🎮 Controls

| Action | Keys |
|---|---|
| Move | `W` `A` `S` `D` |
| Aim / basic attack | Mouse move + **Left click** |
| Cast spells | `Q` `W` `E` `R` `T` `1` `2` `3` (hotbar) |
| Ultimate | `4` |
| Inventory | `I` |
| Character sheet | `C` |
| Skill tree | `K` |
| World map | `M` |
| Backpack / consumables | `B` |
| Interact / confirm | `F` / `Space` / `Enter` |
| Close panel / menu | `Esc` |

## 🚀 Getting started

Requires **Python 3.12+**.

```bash
git clone https://github.com/<your-username>/sangeroasa.git
cd sangeroasa
python -m pip install -r requirements.txt
python main.py
```

Save files are written to `~/sangeroasa_save.json`.

## 🧱 Project structure

The codebase was decomposed from a single monolithic file into a clean, importable `game/` package.
`main.py` now holds only the entry point and the `run_session()` game loop; everything else lives in
focused modules.

```
main.py            Entry point + run_session() game loop
game/
  constants  state  utils  gameplay_math  nav  vfx  audio
  sprites  items  classes_runtime  loaders  entities  farm  vendors  assets  dialogue
  data/      classes · icons · spell_layout · quests · items_data · world_data
  render/    props · shops · glyphs
  combat/    runtime · spells · kits · talents · vfx · spellcast · ultimates
  systems/   core (day/night, weather, particles, status, camera, …)
  hud/   ui/ (hud · screens · charcreate)   world/ (scenes · level_decor)
tools/   generate_medieval_assets.py   (procedural asset-pack generator)
assets/  authored art, audio, fonts, level decor
tests/   smoke_test.py · capture_screenshots.py
```

## 🛠️ Development

The game can be booted headlessly to verify changes:

```bash
python -c "import main"                          # structural check (runs all definitions)
python tests/smoke_test.py                       # ~180-frame headless run
SMOKE_FRAMES=500 python tests/smoke_test.py      # longer run; exercises spells/menus/combat
python tests/capture_screenshots.py              # regenerate docs/screenshots/
```

The runtime writes `assets/level_decor/npc_positions.json` during play, so it may appear modified
after running the game or the tests.

## 📦 Tech

Pure **Python 3.12** + **pygame 2.6** (with `pygame.gfxdraw`). No game engine — rendering, audio
synthesis, world generation, AI and UI are all custom. Sprites can also be generated locally with a
ComfyUI + SDXL + Pixel Art XL pipeline into `assets_generated/`.

## 📝 Credits

Game design, art direction, and code by the project author. Bundled art assets retain their own
licenses (see `assets/LICENSE.txt`).
