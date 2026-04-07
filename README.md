```md
# Text Adventure

A data-driven Python text adventure with:
- **world exploration** (rooms, objects, exits, puzzle flags),
- **turn-based combat** (AP/MP costs, intents, status effects, targeting),
- **JSON-first content authoring** (rooms, enemies, items, classes, commands),
- and a **Tkinter game window** for art, HUD, log, and input.

The core project goal is to keep gameplay logic in code, while keeping game content and tuning in `assets/*.json`.

---

## Project goals

1. **Data-driven design**
   - Rooms, enemies, items, classes, and commands are loaded from JSON.
   - Combat/AP/MP tuning should be configurable without rewriting core engine code.

2. **Readable engine code**
   - Keep subsystems separated: parser, exploration, combat, world, loader.
   - Prefer extending existing systems over one-off hardcoded logic.

3. **Easy content iteration**
   - Add or tune content by editing files under `assets/`.
   - Reuse shared ASCII art via `art_asset` references instead of duplicating art blobs.

---

## Project structure

```

Text-Adventure/
│
├── main.py                         Entry point
│
├── assets/                         ── ALL game content (no hardcoding) ──
│   ├── rooms/                      One JSON file per room (supports subfolders)
│   │   ├── _schema.json            Reference schema
│   │   └── */                      Zone folders with .json and art/
│   ├── items/                      One JSON file per equippable item
│   │   └── _schema.json
│   ├── enemies/                    One JSON file per enemy template
│   │   └── _schema.json
│   ├── classes/                    One JSON file per character class
│   │   └── _schema.json
│   ├── commands/
│   │   └── commands.json           Master command + modifier + article table
│   └── world_states.json           Global flag defaults
│
├── game/                           Core engine (all Python modules)
│   ├── __init__.py
│   ├── game.py                     TextAdventureGame orchestrator + run loop
│   ├── loader.py                   AssetLoader (JSON → objects)
│   ├── world.py                    Room, WorldObject, Material, WorldMap
│   ├── entities.py                 Entity, Player, Enemy
│   ├── commands.py                 CommandRegistry, CommandDefinition, modifiers
│   ├── parser.py                   CommandParser (aliases, articles, costs)
│   ├── combat.py                   CombatController, turn resolution
│   ├── exploration.py              ExplorationController (movement, interaction)
│   ├── dice.py                     DiceExpression parser/roller
│   ├── effects.py                  StatusEffect, EffectRegistry, EffectManager
│   ├── models.py                   Ability, EquippableItem, CharacterClass, etc.
│   └── window.py                   Tkinter UI (art, status, log, input)
│
├── tests/
│   ├── test_combat_balance.py      Combat simulation tests
│   └── test_combat_targeting.py    Targeting and disambiguation tests
│
└── docs/
    └── removed_components.md       Archive of previous design decisions

```

---

## Current architecture

```text
main.py
  -> TextAdventureGame (game/game.py)
      -> AssetLoader (game/loader.py)
      -> CommandRegistry + Parser (game/commands.py, game/parser.py)
      -> ExplorationController (game/exploration.py)
      -> CombatController (game/combat.py)
      -> Tk window UI (game/window.py)
```

### Key modules

- `game/game.py` — top-level orchestration and state transitions.
- `game/loader.py` — JSON loaders and world assembly.
- `game/world.py` — Room/Object/World graph, LOS, traversal, environmental interactions.
- `game/exploration.py` — world commands (`go`, `look`, `take`, rule-driven interactions).
- `game/combat.py` — encounter loop, AP/MP spend, targeting, enemy intents, outcomes.
- `game/parser.py` — command parsing, aliasing, article handling, cost resolution.
- `game/window.py` — UI panels (art, status, log, input).

---

## Running the game

### Requirements
- Python 3.11+

### Start

```bash
python main.py
```

`main.py` currently starts with `DEBUG = True`, so debug logs are enabled by default.

---

## Combat model (current)

- **Action Points (AP)** are based on the **raw length of the typed command** (letters only, spaces ignored), reduced by equipment letter‑cost reductions. Minimum AP cost is 1.
- **Magic Points (MP)** are based on the command’s `base_mp_cost` (or override) when `costs_mp` is true, reduced by equipment ability‑cost reductions.
- **Targeting**:
  - Supports indexed and name‑based targeting.
  - Article parsing (`a/an/the`) influences target selection and damage bonus rules.
- **Enemy AI**:
  - Enemies pick intents greedily using AP and intent weights/conditions.
- **Damage system**:
  - Damage types are tag‑driven.
  - Room material + enemy material + resist/vulnerability multipliers are applied.

---

## Data-driven content

All gameplay content lives in `assets/` (see structure above).

### Art assets

Rooms and enemies can define:

```json
"art_asset": "assets/rooms/Tent/art/east_of_tent.txt"
```

This allows one ASCII file to be reused by multiple rooms/enemies.

---

## Authoring workflow

### Add a room
1. Create `assets/rooms/<zone>/<room>.json`.
2. Add exits to existing rooms.
3. Optionally add `line_of_sight`, objects, spawns, and `art_asset`.

### Add an enemy template
1. Create `assets/enemies/<enemy>.json`.
2. Define stats and `intent_pool`.
3. Reference it from room `enemy_spawns`.
4. Optionally set `art_asset`.

### Add commands/modifiers
- Edit `assets/commands/commands.json`.
- Use `base_ap_cost`, `base_mp_cost`, tags, aliases, unlock rules, and contexts.

### Add class progression
- Edit `assets/classes/<class>.json`.
- Configure `base_stats`, `starting_items`, `level_unlocks`, `choice_unlocks`.

---

## Testing

Run the current test suite:

```bash
pytest -q
```

---

## Current scope / known gaps

- The project is a strong engine scaffold and already playable, but some systems are intentionally lightweight (example: certain world interactions and advanced ability scripting).
- Design direction is toward richer JSON‑defined combat/class/status behavior while keeping the engine maintainable.
```