# Removed Components Log

This project was intentionally reset to a clean object-oriented skeleton to make future expansion easier and to align with an equipment-first design.

## Why this reset happened

- The prior architecture mixed multiple systems (legacy relic loops, old room scripts, parser experiments, UI utilities) with overlapping responsibilities.
- Combat ownership was fragmented across parser, actions, display, and helper modules.
- Equipment and class progression were spread across many files, making special-ability items harder to evolve cleanly.

## What was removed

### Entire directories removed

- `entities/` — replaced by a single coherent entity model in `game/entities.py`.
- `game_engine/` — parser + engine responsibilities consolidated into focused classes (`game/parser.py`, `game/combat.py`, `game/game.py`).
- `rooms/` — removed old hand-scripted room content to keep this as a framework-first base.

### Legacy utility modules removed

The following modules were removed to eliminate old coupling and relic-era mechanics:

- `utils/actions.py`
- `utils/ascii_art.py`
- `utils/combat.py`
- `utils/constants.py`
- `utils/damage.py`
- `utils/dice.py`
- `utils/display.py`
- `utils/helpers.py`
- `utils/relics.py`
- `utils/status_effects.py`
- `utils/ui.py`

### Files kept intentionally

- `utils/window.py` remains untouched as requested.

## What replaced the removed code

- `game/models.py`: abilities, equippable items, classes, parsed command model, battle context.
- `game/entities.py`: base entity + player + enemy models.
- `game/parser.py`: parser-first command normalization.
- `game/combat.py`: turn resolution driven by parser output.
- `game/world.py`: minimal room/world map scaffolding for future expansion.
- `game/game.py`: orchestration shell for a playable parser-combat loop.
- `main.py`: minimal executable entry point.

## Design direction preserved

- Object-oriented classes remain the core pattern.
- Equipment with special abilities is the primary progression hook.
- Parser-driven combat is the center of combat flow.
- Skeleton methods and class boundaries are intentionally lightweight for rapid iteration.
