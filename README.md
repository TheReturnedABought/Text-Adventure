# Text Adventure

A terminal-first Python RPG with room exploration, puzzle interactions, relic-driven build variety, and AP/MP tactical combat.

## Running the game

From the repository root:

```bash
python main.py
```

No packaging step is required for local play.

## Core gameplay systems

### Exploration
- Traverse connected rooms (`north`, `south`, `east`, `west`).
- Inspect and manipulate environment objects (`look`, `listen`, `examine`, `interact`).
- Puzzle rooms accept direct answer text (no `solve` prefix required).
- Manage inventory, relics, map, and journal.

### Combat
- Turn-based AP economy with optional MP costs for spell/class commands.
- Enemy intents are shown before enemy actions.
- Typed damage system (e.g., slashing, lightning, force) with effectiveness modifiers.
- Status effects and relic passives can heavily alter turn flow.

### Progression
- Class-specific command unlock trees (`soldier`, `rogue`, `mage`).
- XP leveling with stat scaling and new command unlocks/choices.
- Persistent saves include player state, room graph state, enemies, inventory/relics, and journal.

## Parser model

The project currently ships two parser layers:

1. **Legacy command parser** (`game_engine/parser.py`)
   - Active in the current game loop.
   - Normalizes aliases and supports Zork-like phrasing:
     - direction aliases: `n`, `s`, `e`, `w`
     - noun/verb shorthand: `x statue`, `inv`, `?`
     - phrasal verbs: `pick up relic`, `look at altar`, `talk to hermit`
     - movement normalization: `go north`, `walk to east`

2. **Syntax engine parser** (`game_engine/syntax_engine/*`)
   - Exposed via `parse_syntax_command(...)`.
   - Supports richer grammar metadata (determiners, prepositions, adverbs, semantic roles, target resolution).
   - Designed for progressive unlock-based language-combat extensions.

## Project layout

```text
main.py
entities/
  player.py
  class_data.py
  class_commands.py
  enemy.py
  enemy_moves.py
  relic.py
game_engine/
  engine.py
  game_state.py
  parser.py
  journal.py
  save_manager.py
  syntax_engine/
    parser.py
    resolver.py
    lexicon.py
    models.py
    unlocks.py
utils/
  actions.py
  combat.py
  damage.py
  status_effects.py
  display.py
  window.py
rooms/
  area1.py
  room.py
  map_data.py
  enemy_data.py
docs/
  syntax_combat_design.md
```

## Notes

- Recommended terminal size: at least **80x26**.
- A Tk window HUD adapter exists (`utils/window.py`) and mirrors terminal output/input when enabled.
