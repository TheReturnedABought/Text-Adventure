# Text Adventure Game

A text-based adventure game in Python with combat, inventory, multi-enemy encounters,
a letter-based AP economy, class selection, relic rarities, a puzzle system, locked
doors, a listen command for environmental storytelling, ASCII art, and a full
status-effect system inspired by Slay the Spire.

---

## Quick Start

```
git clone https://github.com/yourusername/text-adventure.git
cd text-adventure
python -m venv venv
```

Activate:

- **Windows:** `venv\Scripts\activate`
- **macOS/Linux:** `source venv/bin/activate`

```
pip install -r requirements.txt
python main.py
```

---

## World Map

### Area 1 — Castle Complex Entrance

```
           [Entrance Hall]
                 |
[Puzzle Room] ─ [Riddle Hall] ─🔒─ [Crypt Gate] ──► Area 2
      |               |
      └────────── [Ratssss!] ──── [Servants' Quarters]
                                     (holds crypt key)
```

| Room | Enemies | Notes |
|------|---------|-------|
| Entrance Hall | Castle Guard | Tutorial fight; ASCII banner on entry |
| Riddle Hall | Goblin Guard, Goblin Archer | Hub; directional hints carved into the walls |
| Puzzle Room | — | Riddle puzzle (reward wired, not yet assigned) |
| Ratssss! | Giant Rat x2, Rat Swarm | Three-enemy fight |
| Servants' Quarters | Skeleton Servant x2 | Contains crypt key |
| Crypt Gate | Crypt Warden, Wraith, Bone Archer | Boss encounter |

Every room has an `on_enter` function that prints an ASCII banner and dialogue
before combat begins. Rooms also have ambient flavour lines — one random line
is shown each visit.

---

## Commands

### Exploration

| Command | Description |
|---------|-------------|
| `north` / `south` / `east` / `west` | Move (🔒 = locked door) |
| `take <n>` | Pick up an item or relic (partial name match) |
| `drop <n>` | Drop an item |
| `inventory` | List carried items |
| `relics` | Show relics with ASCII art, rarity, and description |
| `listen` | Hear sensory clues about neighbouring rooms |
| `examine` | Read the puzzle in this room |
| `solve <answer>` | Attempt a puzzle solution |
| `look` | Redescribe the current room |
| `rest` | Restore AP (safe rooms only) |
| `help` | Show all commands including unlocked class commands |
| `quit` | Exit the game |

### Combat

AP resets to full at the start of your turn. Command cost = number of letters in the word.

| Command | AP | Notes |
|---------|----|-------|
| `attack` | 6 | Deal 8–18 damage to a target |
| `heal` | 4 (+1 MP) | Restore 8–15 HP |
| `block` | 5 | Gain 7 Block this turn |
| `end` | — | End your turn immediately (free, no confirm) |
| `relics` | — | Show relics mid-combat (free) |
| `help` | — | Show all commands (free) |

When AP hits zero naturally you are prompted to confirm before the turn ends,
so you can still use free commands. Typing `end` explicitly skips the prompt.

Confirmation prompts also appear after each enemy defeat and before the enemy
turn begins, giving time to read the state before anything changes.

Multi-enemy rooms prompt target selection:

```
  [1] Goblin Guard    HP: 28/28
  [2] Goblin Archer   HP: 20/20
  Target (1-2):
```

---

## Classes

Choose your class at character creation. Each class has a distinct AP command tree
unlocked through levelling and a unique starter relic. ASCII art is shown for the
starter relic when you receive it and whenever you browse your collection.

### ⚔  Soldier — Damage vs Block

Block is a resource. Your strongest commands scale with or consume it.

**Starter relic — Iron-Cast Helm** `[Uncommon]`
Gain 12 Block at the start of each combat.

| Lvl | Command | AP | Effect |
|-----|---------|----|--------|
| 2 | brace | 5 | Gain 3 Block; 8 if you have none. |
| 5 | guard | 5 | +8 Block; counter 10 dmg if block breaks. |
| 5 | berserk | 7 | Rage x2 + Volatile. |
| 5 | discipline | 10 | Clear all debuffs; +15 Block; no attacks this turn. |
| 10 | rally | 5 | +6 Block; next attack +6 damage. |
| 10 | cleave | 6 | Hit all enemies twice for 75% damage. |
| 10 | fortify | 7 | +5 Block now and at every turn-end this combat. |
| 15 | warcry | 6 | Weak 2 + Vulnerable 2 on all enemies. |
| 15 | sentinel | 8 | +16 Block; attackers take 4 thorns damage. |
| 15 | execute | 7 | 2x dmg; 3x if enemy <30% HP; +1x per 10 Block consumed. |
| 20 | juggernaut | 9 | Attack; gain Block equal to damage dealt. |
| 20 | unbreakable | 10 | Damage capped at 6; Block persists between turns. |
| 20 | overwhelm | 9 | Weak 2 + Vulnerable 2; Stun 1 if target has 3+ statuses. |

---

### 🗡  Rogue — Actions vs Burst vs Poison

Chain short cheap commands, build up stacks, then detonate with a finisher.

**Starter relic — Sleightmaker's Glove** `[Rare]`
Actions with an AP cost of 4 or less cost 1 fewer AP.

| Lvl | Command | AP | Effect |
|-----|---------|----|--------|
| 2 | cut | 3 | Deal 6–10 damage. |
| 5 | flow | 4 | Actions cost -1 AP this turn; no repeating commands. |
| 5 | feint | 5 | Disorient target; next attack cannot miss. |
| 5 | mark | 4 | Vulnerable 2; next hit +5 damage. |
| 10 | venom | 5 | Poison 3; +1 if target is Vulnerable. |
| 10 | flurry | 6 | Strike 3 times. |
| 10 | dash | 4 | +8 Block and 8 damage. |
| 15 | toxin | 5 | Double target's Poison stacks (max 8). |
| 15 | assault | 7 | 3+ strikes; hits scale with prior actions this turn. |
| 15 | evade | 5 | Dodge next enemy attack; +2 AP next turn if triggered. |
| 20 | pandemic | 8 | Poison 6; +3 more if already poisoned. |
| 20 | assassinate | 8 | Massive damage; x1.5 if first action this turn. |
| 20 | shadowstrike | 12 | 6 x (total actions this combat) damage. |

---

### 🔮  Mage — MP Management

Most spells cost Mana. Running dry leaves you with only basic commands.

**Starter relic — Aether-Spun Tapestry** `[Rare]`
Max MP +2. Restore 1 MP at the start of each turn.

| Lvl | Command | AP | MP | Effect |
|-----|---------|----|----|--------|
| 2 | spark | 5 | 1 | Deal 8–12 Lightning damage. |
| 5 | bolt | 4 | 1 | Deal 18–26 damage. |
| 5 | ward | 4 | 1 | +8 Block; spells cost -1 MP this turn. |
| 5 | curse | 5 | — | Vulnerable 2 + Weak 2. |
| 10 | blaze | 5 | 2 | Burn 3 (Poison) + Volatile on target. |
| 10 | charm | 5 | 2 | Stun 1; Charm on cooldown next turn. |
| 10 | drain | 5 | 1 | Consume target's Poison; heal that many HP. |
| 15 | shatter | 7 | 2 | 10–18 x Vulnerable stacks (cap x4). |
| 15 | silence | 7 | 1 | Stun 1 + Weak 2. |
| 15 | torment | 7 | 2 | Extend all enemy debuffs by 1 turn. |
| 20 | obliterate | 10 | 3 | Deal 50–70 damage. |
| 20 | rift | 4 | 1 | Restore 3 MP; Vulnerable 1 on self and all enemies. |
| 20 | apocalypse | 10 | 3 | (total enemy status stacks) x 5 damage (cap 40). |

---

## Relics

Relics are passive items that trigger on combat events. Each relic has a small
ASCII art icon shown on pickup and when browsing your collection with `relics`.

Four rarity tiers, colour-coded in the terminal:

| Colour | Rarity |
|--------|--------|
| Grey (default) | Common |
| Green | Uncommon |
| Blue | Rare |
| Yellow | Legendary |

| Relic | Rarity | Effect |
|-------|--------|--------|
| Frog Statue | Common | Each 'a' typed poisons the target for 1 stack. |
| Venom Gland | Common | Every attack poisons the target for 1 stack. |
| Thorn Bracelet | Common | Each time you are hit, gain 1 Rage. |
| Cursed Eye | Common | Each 'i' typed applies 1 Vulnerable to the target. |
| Whisper Charm | Common | Each 'k' typed applies 2 Weak to the target. |
| Whetstone | Common | Each 's' typed applies 1 Bleed to the target. |
| Iron Will | Uncommon | Gain 5 Block at the end of each turn. |
| Berserker Helm | Uncommon | Each 'r' typed applies 2 Rage to yourself. |
| Blessed Eye | Uncommon | Each 'i' typed grants 2 Block. |
| Bear's Hide | Uncommon | Each 'r' typed grants 1 AP. |
| Iron-Cast Helm | Uncommon | +12 Block at the start of each combat. |
| Silent Lamb Wool | Rare | Vowels (a/e/i/o/u) also count as 'l' when typed. |
| Vampiric Blade | Rare | Each attack drains 2 HP from the target. |
| Echo Chamber | Rare | Echo triggers twice instead of once. |
| Sleightmaker's Glove | Rare | Actions costing 4 AP or less cost 1 fewer AP. |
| Aether-Spun Tapestry | Rare | Max MP +2; restore 1 MP at the start of each turn. |

---

## Status Effects

| Icon | Status | Effect |
|------|--------|--------|
| ☠ | Poison | Deals stacks damage per turn, then decays by 1. |
| 🩸 | Bleed | Fixed damage per turn — does **not** decay; must be cleansed. |
| 🌿 | Regen | Restores stacks HP at start of turn, then decays by 1. |
| ⚖️ | Burden | +1 AP cost per stack to every command (player); -2 dmg per stack (enemy). Decays 1/turn. |
| ⚡ | Stun | Entity loses their next turn. |
| 🔥 | Rage | Next attack deals x2, then clears. |
| 💢 | Vulnerable | Next hit deals x1.5, then loses 1 stack. |
| 🌀 | Weak | Entity's next attack deals x0.75, then loses 1 stack. |
| 🛡 | Block | Absorbs incoming damage; clears at the start of your turn. |
| 💥 | Volatile | +50% damage dealt; 50% chance of 5 self-damage per action. |
| 🔊 | Echo | Last command repeats for free at end of turn (x2 with Echo Chamber). |
| 🌪 | Disorient | 50% miss chance on attacks; decays each turn. |

---

## Puzzles

Rooms can contain a single puzzle. Use `examine` to read the description and
hints, then `solve <your answer>` to attempt a solution. A correct answer fires
the room's `reward_fn` — wired but unassigned in Area 1.

The Puzzle Room in Area 1 contains:

> *"Speak me and I vanish. Hold me and I am forever kept. What am I?"*
>
> Answer: **silence**

---

## Folder Structure

```
text_adventure/
│
├── main.py                     # Entry point — Game class, CommandRouter, main loop
│
├── game_engine/
│   ├── engine.py               # GameEngine (expandable game state holder)
│   └── parser.py               # Command parser with single-letter aliases
│
├── entities/
│   ├── player.py               # Stats, class, command unlocks, relics, XP/levelling
│   ├── enemy.py                # Enemy class with weighted move selection
│   ├── enemy_moves.py          # Reusable move effect functions and factory
│   ├── relic.py                # Relic base class and trigger constants
│   ├── class_data.py           # Command tables and descriptions for all 3 classes
│   └── class_commands.py       # Effect functions for every class command
│
├── rooms/
│   ├── room.py                 # Room class — link(), locks, puzzle, listen, on_enter
│   ├── puzzle.py               # Puzzle class — examine / attempt / reward hook
│   ├── enemy_data.py           # Enemy factory functions (one per enemy type)
│   ├── area1.py                # Area 1 — Castle Complex layout, dialogue, enemies
│   └── map_data.py             # World coordinator — imports and chains area modules
│
└── utils/
    ├── constants.py            # MAX_HEALTH, MAX_AP, MAX_MANA, XP_PER_LEVEL
    ├── helpers.py              # print_slow, print_status, make_bar, rarity colours
    ├── ascii_art.py            # Room banners, relic icons, print_art() helper
    ├── display.py              # show_room, show_help, show_levelup, show_relics, etc.
    ├── actions.py              # Exploration actions — move, take, drop, listen, solve
    ├── combat.py               # CombatSession class — player turn, enemy turn, echo
    ├── status_effects.py       # All status apply / consume / tick logic
    └── relics.py               # Relic class definitions and registry
```

### Adding a New Area

1. Create `rooms/area2.py` with a `setup_area2()` function following the pattern in `area1.py`.
2. Add any new enemy types to `rooms/enemy_data.py`.
3. Add room banners to `utils/ascii_art.py`.
4. In `rooms/map_data.py`, import `setup_area2` and connect its entrance room to the
   Area 1 exit (the east door of the Crypt Gate).

---

## Building the .exe

```
pyinstaller --onefile --add-data "assets:assets" main.py
```

Output appears in `dist/`.

---

## Dependencies

- Built-in: `os`, `sys`, `json`, `random`
- External: `colorama`, `pyfiglet` (optional), `rich` (optional), `pyinstaller`

---

## License

MIT License