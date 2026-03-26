# Text Adventure

A terminal-first Python RPG with exploration, tactical AP/MP combat, class command unlocks, relic synergies, enemy intent telegraphing, and save/load support.

## Quick Start

```bash
git clone https://github.com/yourusername/text-adventure.git
cd text-adventure
python -m venv venv
source venv/bin/activate   # Windows: venv\\Scripts\\activate
pip install -r requirements.txt
python main.py
```

---

## Core Combat Rules

- **AP turn economy:** You get a full AP pool each turn (base **12 AP**).
- **AP growth:** +1 max AP at levels **9** and **16**.
- **Command costs:** by default, AP cost is command-name length unless overridden in class data.
- **MP:** used by healing and many mage commands.
- **Enemy intent:** enemies plan actions until AP is spent; intents are shown before actions resolve.
- **Statuses clear at combat end.**

### Intended Combat Length Targets

- **Normal encounters:** 3–5 turns
- **Elite encounters (e.g., Crypt Warden):** 5–8 turns
- **Boss encounters:** 10+ turns

These targets are used when tuning enemy HP/AP and player damage scaling.

---

## Class Progression & Health

Starting HP:
- **Soldier:** 50
- **Rogue:** 40
- **Mage:** 35

Level-up HP growth:
- Soldier/Rogue: ~10% of starting HP per level
- Mage: alternates **+3 / +4** HP per level

---

## Notable Balance Updates

### Soldier
- **Unbreakable:** Block persists between turns for this combat.
- **Fortify:** tuned to **Fortify 4**.
- New level 4 choices:
  - **Downcut** (7 AP, 1 MP): 2d10+4, cannot gain Block for rest of turn.
  - **Defiant** (7 AP, 1 MP): if Block survives enemy turn, gain +2 AP next turn and +2 Strength.

### Rogue
- New level 4 choices:
  - **Aim** (3 AP, 1 MP): next attack cannot miss; once/turn; gain Strength 1 this combat.
  - **Weave** (5 AP, 1 MP): gain Dexterity 1 this combat.
- **Flurry:** now hits twice for 1d4+2 each, can split across targets.
- **Evade:** 50% chance enemy actions miss; gains +2 AP next turn when triggered.

### Mage
- **Spark:** hits twice for 1d4+2 Lightning each (same or different targets).
- New level 4 choices:
  - **Conduit** (7 AP, 2 MP): next non-AOE spell hits an additional target (Targeting status).
  - **Icewall** (8 AP, 1 MP): gain 2d8+3 Block, apply Weak 1 to all enemies.
- **Drain:** deal 1d6+2 and heal that amount.
- **Shatter:** 1d6 × remaining mana + 3.

### Shared Level 12 Choices (all classes)
- **Quickshot** (9 AP): 1d4+2 damage, up to 4 targets.
- **Plan** (4 AP): at start of next turn, first command gets AP/MP discount.
- **Shielded** (8 AP, 1 MP): Fortify 2; attacks grant block while active.

---

## Multi-Target Selection Rules

- Multi-hit/multi-target commands now use a shared target picker.
- You are prompted for each hit, and you may select the **same target multiple times**.
- This applies to commands like **Spark**, **Flurry**, **Quickshot**, and Conduit bonus targeting.

---

## Statuses

Key statuses include:
- **Strength:** offensive dice rolls gain extra dice.
- **Dexterity:** defensive/block rolls gain extra dice.
- **Evade:** 50% enemy miss chance with AP refund trigger.
- **Aim:** next attack cannot miss.
- **Targeting:** next non-AOE spell gains an additional target.

---

## Project Structure

```text
main.py
entities/
  player.py          # player stats, level growth, unlock tracking
  class_data.py      # command unlock/cost/source-of-truth metadata
  class_commands.py  # command effect implementations
  enemy.py           # enemy AP planning + move selection
  enemy_moves.py     # move behavior helpers
game_engine/
  engine.py          # game loop orchestration
  parser.py          # command parsing
  save_manager.py    # JSON save/load
utils/
  combat.py          # combat session loop
  status_effects.py  # status apply/tick/format helpers
  dice.py            # dice parser/roller
  display.py         # help/level-up display
rooms/
  area1.py, map_data.py, room.py, enemy_data.py
```

---

## Save / Load

- Save file: `save_data/save.json`
- Save includes player stats, progression, known commands, statuses, relics, room state, and journal data.

---

## Notes

- Minimum recommended terminal size: **80×26**.
- This project is built for text-mode play; no browser UI is required.
