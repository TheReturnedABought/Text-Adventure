# Text Adventure

A terminal-first Python RPG focused on tactical, word-command combat.
You explore connected rooms, solve puzzles, collect relics, and fight in AP/MP-based encounters with visible enemy intents.

## Quick Start

```bash
git clone https://github.com/yourusername/text-adventure.git
cd text-adventure
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

---

## Gameplay Overview

### Exploration
- Move with: `north`, `south`, `east`, `west`
- Inspect environment: `look`, `listen`, `examine <object>`, `interact <object>`
- Solve puzzles: `solve <answer>`
- Inventory and relics: `inventory`, `relics`
- Lore and enemy memory: `journal`

### Combat Loop
- AP resets each turn (base 12 AP).
- Use commands until AP is exhausted, then `end` turn.
- Enemies telegraph planned actions in the HUD before they act.
- Core commands:
  - `attack`
  - `block`
  - `heal`
  - class commands (unlock by level)

---

## Damage Types, Weaknesses, and Resistances

The combat system now supports typed damage with effectiveness hints.

Example feedback:
- “you dealt 12 bludgeoning damage. It’s very effective!”
- “you dealt 20 piercing damage. It’s not very effective.”

### Supported Types (extensible)
- slashing
- piercing
- bludgeoning
- force
- lightning
- fire
- physical (fallback)

### Base `attack` damage type by class
- Soldier: **piercing**
- Rogue: **slashing**
- Mage/Wizard: **force**

---

## Enemy Encounter Scripting (Area 2 Prep)

Enemy definitions now support higher-drama scripting hooks:

- **Phase triggers**: trigger behaviors at HP thresholds (e.g. 66%, 50%, 33%).
- **Reactive counters**: fire in response to events like taking damage.
- **Combo scripts**: detect move sequences and trigger bonuses/effects.

This enables more memorable fights and smoother boss design for upcoming areas.

---

## Relics

### New relics
- **Mana Infused Bone**
  - Gain 1 Dexterity for each MP spent.
- **The Static Hunger**
  - Repeating the same action grants +1 Strength.

---

## Area 1 Tutorial Flow Update

Area 1 opening has been reworked to teach core systems more cleanly:

- Entrance now provides tutorial guidance.
- New room: **Entrance Corridor** between Entrance Hall and Riddle Hall.
- Corridor encounter includes a **Guard** and **Crossbowman** to demonstrate:
  - enemy intent reading,
  - typed damage effectiveness,
  - basic command economy.

---

## Progression & Leveling

### Starting HP
- Soldier: 50
- Rogue: 40
- Mage: 35

### HP growth per level
- Applied in `Player._apply_level_growth`.
- Soldier/Rogue: ~10% of base HP per level.
- Mage: alternates +3 / +4 by level.

### Important fix
- The level-up UI no longer adds an unintended extra flat +10 HP.
- HP growth is now only applied via `Player._apply_level_growth`.

---

## Project Structure

```text
main.py
entities/
  player.py          # player stats, growth, unlock tracking
  class_data.py      # command metadata (costs/unlocks)
  class_commands.py  # command effect implementations
  enemy.py           # enemy AI + phase/reactive/combo hooks
  enemy_moves.py     # move behaviors and factory
game_engine/
  parser.py          # legacy parser facade + syntax parser entrypoint
  syntax_engine/     # OO syntax-combat parsing engine
    parser.py
    resolver.py
    unlocks.py
    lexicon.py
    models.py
  save_manager.py    # save/load system
utils/
  combat.py          # combat session + AP/MP loop
  damage.py          # damage typing/effectiveness resolver
  relics.py          # relic definitions and registry
  status_effects.py  # status logic
rooms/
  area1.py           # area map + tutorial flow + encounters
  enemy_data.py      # enemy factories
```

---

## Save / Load

- Save file: `save_data/save.json`
- Save includes player progression, commands, room states, enemies, relics, and journal data.

---

## Notes

- Recommended terminal size: **80x26** or larger.
- Built for terminal/text-mode play.
