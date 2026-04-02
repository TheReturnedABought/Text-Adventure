# Text Adventure (OO Skeleton)

A clean, modular, object-oriented foundation focused on **parser-driven combat** and **equippable items with special abilities**.

## Current Structure

- `main.py` — app entry point.
- `game/models.py` — data models (abilities, items, classes, parsed commands, battle context).
- `game/entities.py` — `Entity`, `Player`, and `Enemy` classes.
- `game/parser.py` — command parsing and intent normalization.
- `game/combat.py` — combat turn resolution driven by parser intents.
- `game/world.py` — room and world map skeleton.
- `game/game.py` — orchestration shell and sample sandbox combat loop.
- `utils/window.py` — existing GUI window kept as-is.
- `docs/removed_components.md` — full log of removed code and rationale.

## Required Game Features (Roadmap)

Use this checklist as the required feature scope for the full game.

### 1) Parser and Input System

- [ ] Verb + object grammar (`attack goblin`, `equip iron sword`, `use ember slash`).
- [ ] Synonym tables and aliasing (`hit`, `strike`, `wear`, `cast`).
- [ ] Error-tolerant parsing with useful feedback and suggestions.
- [ ] Intent routing shared by exploration and combat.

### 2) Equipment-First Progression

- [ ] Distinct equipment slots (`weapon`, `offhand`, `armor`, `trinket`, etc.).
- [ ] Item stat modifiers and special abilities.
- [ ] Equip/unequip restrictions (class, level, conditions).
- [ ] Item rarity/tier scaling and upgrade paths.

### 3) Class System

- [ ] Class identity via passive traits and compatible gear themes.
- [ ] Class-specific command extensions where needed.
- [ ] Clear class progression hooks (talents, unlock trees, milestones).

### 4) Combat Loop (Parser-Centric)

- [ ] Turn order system with AP/stamina or equivalent economy.
- [ ] Intent resolution pipeline: parse -> validate -> execute -> report.
- [ ] Ability effects framework (damage, buffs, debuffs, counters, triggers).
- [ ] Enemy AI intents that can be surfaced to the parser/UI.

### 5) World and Content

- [ ] Room graph + encounter definitions.
- [ ] Interactive objects and parser-friendly room actions.
- [ ] Loot tables centered on equippable items and ability items.

### 6) Persistence and UX

- [ ] Save/load for player, equipment, abilities, and world progression.
- [ ] Combat log formatting and status summaries.
- [ ] Optional integration path for `utils/window.py` UI shell.

### 7) Testing and Stability

- [ ] Unit tests for parser normalization and combat resolution.
- [ ] Data validation for classes/items/enemies.
- [ ] Regression checks for command compatibility as grammar expands.

## Running

```bash
python main.py
```

## Notes

This repository is now intentionally lean so you can expand systems cleanly without legacy clashes.
