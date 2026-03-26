# Text Adventure Game

A text-based adventure game in Python with combat, inventory, multi-enemy encounters,
a letter-based AP economy, class selection, relic rarities, a puzzle system, locked
doors, a listen command, ASCII art, a modular event system, a full status-effect
system inspired by Slay the Spire, enemy telegraphing, an ASCII map, a journal/codex,
auto-save/load, command history, and a **4-panel terminal UI**.

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

Minimum terminal size: **80 × 26**. Larger terminals give more log history.

---

## Terminal UI

After the intro screen the game switches into a fixed 4-panel layout that
fills the terminal automatically.

```
┌─ ⚔ COMBAT ────────────────────────────────────────────────────────────────┐
│  [1] Crypt Warden      [2] Wraith          [3] Bone Archer               │
│  HP[████████░░] 55/70  HP[██████░░░] 20/30  HP[████████] 25/25           │
│  AP[◆◆◆◆◆◆◆◆◆◆]14/14  AP[◆◆◆◆◆◆◆◆] 8/10   AP[◆◆◆◆◆◆] 6/8              │
│  →DEATH GRIP(9)+1      →Soul Drain(7)       →Venomous Shaft(6)           │
│   /╔═══╗\              ~~~                   _____                        │
│   |║ ☠ ║|             /o  o\               (o) (o)                        │
│   \╠═══╣/            ( ~~~~ )               \___/                         │
├─ STATUS ──────────────────────────────────────────────────────────────────┤
│  HP [████████████░░░░░░] 62/100   AP [◆◆◆◆◆◆◆◆◆◆◆◆] 12/12               │
│  MP [●●●●●] 5/5   Lv3   XP 45                                            │
│  attack(6) heal(4+1MP) block(5)  │  cut(3) mark(4) venom(5)              │
├─ LOG ─────────────────────────────────────────────────────────────────────┤
│  You enter the Crypt Gate.                                                │
│  The Crypt Warden turns its head — slowly, deliberately.                 │
│  ⚔ COMBAT — Crypt Warden, Wraith, Bone Archer                            │
│  → You strike Crypt Warden for 14! (HP: 56/70)                           │
│  ☠ Bone Archer takes 2 poison damage! (HP: 23/25)                        │
├─ INPUT ────────────────────────────────────────────────────────────────────┤
│  > _                                                                      │
└────────────────────────────────────────────────────────────────────────────┘
```

### Panel breakdown

| # | Panel | Content |
|---|-------|---------|
| 1 | **ART** | **Combat mode** — one card per living enemy: ASCII portrait (or stat block if no art), HP/AP bars, and the enemy's telegraphed next move. Up to 4 enemies side-by-side (2 × 2 for 3–4). **Explore mode** — room ASCII art + live summary of enemies, relics, items, events, puzzles, and exits. Updates instantly on room change. |
| 2 | **STATUS** | HP / AP / MP progress bars with colour coding (green → yellow → red). Level, XP, active status effects, carried relics, and the full command list with AP costs. |
| 3 | **LOG** | Scrolling output — story text, NPC dialogue, combat results, item pickups. All `print_slow` calls route here when the UI is active. Fills available terminal space; earlier lines scroll off the top. |
| 4 | **INPUT** | Command prompt. Supports all existing commands and single-letter aliases. "Press Enter to continue" prompts show as a dimmed separator line in the log so they don't trigger a full redraw. |

### How it integrates

- `utils/ui.py` provides a singleton `ui` object.
- `ui.enable()` is called once in `Game.setup()` / `Game._load_game()` after the
  player and first room exist. From that point on:
  - `builtins.print` and `builtins.input` are monkey-patched — no other file needs
    to import the UI.
  - `print_slow()` in `helpers.py` checks `ui._active` and calls `ui.log()` instead
    of streaming to stdout directly.
- `ui.set_explore(player, room)` is called on every room transition.
- `ui.set_combat(player, room, enemies)` is called when combat starts.
- `ui.set_explore(player, room)` is called again when combat ends.

---

## Single Source of Truth

**Every numeric constant** lives in `utils/constants.py`.
**Every command definition** lives in `entities/class_data.py`.

### How command costs propagate

```python
# entities/class_data.py
{
    "name":    "execute",
    "desc":    "2× dmg; 3× if enemy <30% HP; +1× per 10 Block consumed.",
    "ap_cost": None,   # None = len(name); set int to override
    "mp_cost": 0,
    "unlock_mode": "choice",
}
```

`display.py`'s `show_help()`, `combat.py`'s `_calc_ap_cost()`, the level-up
screen, and the **STATUS panel** all read from the same function `cmd_ap_cost()`.

---

## World Map

### Area 1 — Castle Complex Entrance

```
                      [Entrance Hall]
                            |
    [Puzzle Room] ─── [Riddle Hall] ─🔒─ [The Crypt Gate] ──► Area 2
          |                 |
          └──────────── [Ratssss!]
                             |
  [Puzzle Alcove] ─── [The Crossroads 🔥] ─── [Servants' Quarters]
                             |                  (holds crypt key)
                       [Locked Hall]
                       (🔒►Area 3)(🔒►Area 4)
                       (stranger on 2nd visit)
                             |
                         [Kitchen]
                         (Goblin ×2)
```

| Room | Enemies | Notes |
|------|---------|-------|
| Entrance Hall | Castle Guard | Tutorial fight; contains torch |
| Riddle Hall | Goblin Guard, Goblin Archer | Hub; hints in carved walls |
| Puzzle Room | — | Riddle → Etched Stone relic |
| Ratssss! | Giant Rat ×2, Rat Swarm | Three-enemy fight |
| The Crypt Gate | Crypt Warden *(elite)*, Wraith, Bone Archer | Warden drops Warden's Brand |
| The Crossroads | — | Event — cold brazier; torch → Rage ×1 next fight |
| Puzzle Alcove | — | Mini-puzzle: sealed chest → healing draught + Frog Statue |
| Servants' Quarters | Skeleton Servant ×2 | Contains crypt key |
| Locked Hall | — | Stranger appears on 2nd visit; locked exits to Area 3 & 4 |
| Kitchen | Goblin ×2 | Food items |

---

## Commands

### Exploration

| Command | Description |
|---------|-------------|
| `north` / `south` / `east` / `west` | Move (🔒 = locked) |
| `take <n>` | Pick up an item or relic |
| `drop <item>` | Drop an item |
| `use <item>` | Use a consumable |
| `inventory` | List carried items |
| `relics` | Show relics with ASCII art, rarity, description |
| `interact` | Trigger room event or NPC |
| `listen` | Hear sensory clues about neighbouring rooms |
| `examine` | Read the puzzle or object in this room |
| `solve <answer>` | Attempt a puzzle solution |
| `look` | Redescribe the current room |
| `map` | ASCII map of all explored rooms |
| `journal` | Codex: lore entries and enemy bestiary |
| `help` | All commands including unlocked class commands |
| `quit` | Exit the game |

Single-letter aliases: `n/s/e/w`, `i` (inventory), `l` (look), `m` (map), `j` (journal), `h` (help).

### Combat

AP resets to full each turn. Command cost = letters in name.
**Each enemy's planned next move is shown in the ART panel and the combat HUD.**

| Command | Cost | Notes |
|---------|------|-------|
| `attack` | 6 AP | Deal 8–18 damage |
| `heal` | 4 AP +1 MP | Restore 8–15 HP |
| `block` | 5 AP | Gain 7 Block |
| `end` | free | End turn immediately |
| `relics` | free | Show relics mid-combat |
| `journal` | free | View codex mid-combat |

---

## New Systems

### 4-Panel Terminal UI
See the **Terminal UI** section above. Activated automatically at game start;
the intro and class-selection screens run in classic text mode first.

Key files: `utils/ui.py`, `utils/ascii_art.py` (ENEMY_ART + ROOM_ART dicts).

### Enemy Telegraphing
Each enemy's planned move is shown both in the **ART panel** header card
and in the inline combat HUD. Stun shows `⚡ STUNNED`.

### ASCII Map
`map` renders a live grid of all **explored** rooms. Unvisited neighbours
show as `[???]`. Current position is marked `[*Name]`. Locked exits show 🔒.

### Journal / Codex
`journal` opens two sections: **Lore** (scrolls, puzzle solves, NPC dialogue)
and **Bestiary** (HP range, attack power, moves seen, drops observed).

### Auto-Save / Load
Saves to `save_data/save.json` after every room transition, combat victory,
and quit. On startup, a save is offered to continue or start fresh.
Dying wipes the save.

### Command History
Press **↑ / ↓** to cycle through the last 20 commands. Uses `readline` on
Unix/macOS; `pyreadline3` on Windows.

### Environmental Combat *(hook in place)*
Rooms can hold `EnvObject` instances. `use <object>` in combat triggers the effect.

```python
room.env_objects = [
    EnvObject("lever", spike_trap_fn, uses=1, combat_only=True),
]
```

---

## Folder Structure

```
text_adventure/
│
├── main.py                        # Game, CommandRouter, entry point
├── save_data/
│   └── save.json                  # auto-save (created at runtime)
│
├── game_engine/
│   ├── engine.py                  # GameEngine — holds start_room reference
│   ├── parser.py                  # Command parser + single-letter aliases
│   ├── journal.py                 # Codex — lore + enemy bestiary
│   └── save_manager.py            # JSON serialise / deserialise game state
│
├── entities/
│   ├── player.py                  # Stats, class, relics, journal, pending effects
│   ├── enemy.py                   # Enemy — moves, drops, _planned_move (telegraphing)
│   ├── enemy_moves.py             # Move effect functions
│   ├── relic.py                   # Relic base class and trigger constants
│   ├── class_data.py              # ★ Single source of truth — all CommandDef dicts
│   └── class_commands.py          # Effect functions for every class command
│
├── rooms/
│   ├── room.py                    # Room — link/lock, listen, visit_count, EnvObject
│   ├── puzzle.py                  # Puzzle — examine/attempt/reward_fn
│   ├── events.py                  # Event system — builders, opt(), Event, Merchant
│   ├── enemy_data.py              # Enemy factories
│   ├── area1.py                   # Area 1 layout
│   └── map_data.py                # World root — start_room for map + SaveManager
│
└── utils/
    ├── constants.py               # ★ Single source of truth — all numeric constants
    ├── helpers.py                 # print_slow (routes through ui), BLUE, RESET, bars
    ├── ui.py                      # ★ 4-panel terminal UI — UIManager singleton
    ├── ascii_art.py               # Room/relic art + ENEMY_ART + ROOM_ART dicts
    ├── display.py                 # show_room/help/map/journal/levelup
    ├── actions.py                 # Exploration actions
    ├── combat.py                  # CombatSession — telegraphing HUD, journal hooks
    ├── status_effects.py          # All status apply/consume/tick logic
    └── relics.py                  # Relic class definitions and registry
```

---

## Adding a New Command

1. Add a `CommandDef` dict to the correct class tier in `entities/class_data.py`.
2. Write the effect function in `entities/class_commands.py` and register it in `COMMAND_EFFECTS`.
3. Done — `show_help()`, the combat HUD, the **STATUS panel**, and the level-up screen pick it up automatically.

## Adding a New Area

1. Create `rooms/area2.py` with `setup_area2()` following `area1.py`.
2. Add enemy factories to `rooms/enemy_data.py`.
3. Add room/relic art to `utils/ascii_art.py` and register names in `ROOM_ART` / `ENEMY_ART`.
4. In `rooms/map_data.py`, call `setup_area2()` and link its entrance to the Crypt Gate east exit.
5. The map renderer, SaveManager, and UI art panel discover the new rooms/enemies automatically.

## Adding an Environmental Hazard

1. Write a `use_fn(player, room, enemies) -> str` in `rooms/area_X.py`.
2. Attach it: `room.env_objects = [EnvObject("lever", use_fn, uses=1, combat_only=True)]`.
3. Done — `combat.py` and `utils/actions.py` dispatch `use <name>` to it automatically.

---

## Classes

### ⚔  Soldier

**Starter relic — Iron-Cast Helm** `[Uncommon]`: Gain 12 Block at combat start.

| Lvl | Command | AP | Effect |
|-----|---------|----|--------|
| 2 | brace | 5 | +3 Block; +10 if you have none. |
| 5 | guard | 5 | +8 Block; Counter 10. |
| 5 | berserk | 7 | Rage ×2 + Volatile. |
| 5 | discipline | 10 | Clear all debuffs; +23 Block; no attacks this turn. |
| 10 | rally | 5 | +6 Block; next attack +6 dmg. |
| 10 | cleave | 6 | Hit all enemies twice for 75% dmg. |
| 10 | fortify | 7 | Fortify 5 — gain 5 Block at the start of every turn this combat. |
| 15 | warcry | 6 | Weak 2 + Vulnerable 2 on all enemies. |
| 15 | sentinel | 8 | +16 Block; attackers take 4 thorns. |
| 15 | execute | 7 | 2× dmg; 3× if <30% HP; +1× per 10 Block consumed. |
| 20 | juggernaut | 9 | Attack; gain Block = damage dealt. |
| 20 | unbreakable | 10 | Damage capped at 6; Block persists between turns. |
| 20 | overwhelm | 9 | Weak 2 + Vulnerable 2; Stun 1 if 3+ statuses. |

### 🗡  Rogue

**Starter relic — Sleightmaker's Glove** `[Rare]`: 'l' doesn't count toward AP cost.

| Lvl | Command | AP | Effect |
|-----|---------|----|--------|
| 2 | cut | 3 | Deal 6–10 damage. |
| 5 | flow | 4 | Speed 5 — next 5 actions −1 AP each. |
| 5 | feint | 5 | Disorient target; next attack can't miss. |
| 5 | mark | 4 | Vulnerable 2; next hit +5 dmg. |
| 10 | venom | 5 | Poison 3; +1 if Vulnerable. |
| 10 | flurry | 6 | Strike 3 times. |
| 10 | dash | 4 | +8 Block, 8 dmg, Speed 1. |
| 15 | toxin | 5 | Double Poison stacks (max 8). |
| 15 | assault | 7 | 3+ strikes; scales with prior actions. |
| 15 | evade | 5 | Dodge next attack; +2 AP if triggered. |
| 20 | pandemic | 8 | Poison 6; +3 if already poisoned. |
| 20 | assassinate | 8 | ×1.5 first action or <40% HP; ×2 if both. |
| 20 | shadowstrike | 12 | 5 × (actions this turn) dmg, cap 50. |

### 🔮  Mage

**Starter relic — Aether-Spun Tapestry** `[Rare]`: Max MP +2; +1 MP per turn.

| Lvl | Command | AP | MP | Effect |
|-----|---------|----|----|--------|
| 2 | spark | 5 | 0 | 12–18 Lightning. |
| 5 | bolt | 4 | 1 | 22–32 damage. |
| 5 | coalesce | 8 | 0 | +17 Block; spells −1 MP for 2 turns. |
| 5 | delay | 5 | 1 | Slow 1 on target. |
| 10 | wave | 4 | 1 | 8–14 Lightning to all. |
| 10 | storm | 5 | 2 | 18–24 to all. |
| 10 | drain | 5 | 1 | Consume Poison; heal that HP. |
| 15 | rift | 4 | 1 | Restore 3 MP; apply Vulnerable 1 to yourself and all enemies. |
| 15 | silence | 7 | 1 | Stun + Weak 2. |
| 15 | torment | 7 | 2 | Extend all enemy debuffs +1 turn. |
| 20 | obliterate | 10 | 3 | 60–80 damage. |
| 20 | tempest | 7 | 3 | 30–45 to all. |
| 20 | apocalypse | 10 | 3 | (total status stacks) × 5, cap 60. |

---

## Consumable Items

| Item | Effect |
|------|--------|
| apple | +15 HP |
| bread | +20 HP |
| healing draught | +30 HP |
| red mushroom | Rage ×2 at next combat start |
| blue mushroom | Regen 4 at next combat start |
| gold mushroom | Block 10 at next combat start |
| dark mushroom | Poison 3 on yourself at next combat start |
| mushroom | Random of the above |

---

## Relics

| Colour | Rarity |
|--------|--------|
| Grey | Common |
| Green | Uncommon |
| Blue | Rare |
| Yellow | Legendary |

| Relic | Rarity | Effect |
|-------|--------|--------|
| Frog Statue | Common | Each 'a' typed poisons target 1 stack. |
| Venom Gland | Common | Every attack poisons target 1 stack. |
| Thorn Bracelet | Common | Each hit taken: +1 Rage. |
| Cursed Eye | Common | Each 'i' typed: +1 Vulnerable on target. |
| Whisper Charm | Common | Each 'k' typed: +2 Weak on target. |
| Whetstone | Common | Each 's' typed: +1 Bleed on target (max 5). |
| Etched Stone | Common | Each 'e' typed: +1 Vulnerable on target. |
| Warden's Brand | Common | All enemies enter combat with Vulnerable 1. |
| Iron Will | Uncommon | +5 Block at end of each turn. |
| Berserker Helm | Uncommon | Each 'r' typed: +2 Rage on self. |
| Blessed Eye | Uncommon | Each 'i' typed: +2 Block. |
| Bear Skin | Uncommon | Each 'a' in command: −1 AP (max −2). |
| Iron-Cast Helm | Uncommon | +12 Block at combat start. |
| Silent Lamb Wool | Rare | Vowels also count as 'l'. |
| Vampiric Blade | Rare | Each attack: drain 2 HP from enemy. |
| Echo Chamber | Rare | Echo triggers twice. |
| Sleightmaker's Glove | Rare | 'l' doesn't count toward AP cost. |
| Aether-Spun Tapestry | Rare | Max MP +2; +1 MP per turn. |

---

## Status Effects

| Icon | Status | Effect |
|------|--------|--------|
| ☠ | Poison | Stacks dmg/turn, decays 1/turn. |
| 🩸 | Bleed | Fixed dmg/turn, no decay; max 5 stacks. |
| 🌿 | Regen | Heals stacks HP/turn, decays 1/turn. |
| ⚖️ | Burden | +1 AP/stack (player); −2 dmg/stack (enemy). Decays. |
| ⚡ | Stun | Lose next turn. |
| 🔥 | Rage | Next attack ×2, then clears. |
| 💢 | Vulnerable | Next hit ×1.5, −1 stack. |
| 🌀 | Weak | Next attack ×0.75, −1 stack. |
| 🛡 | Block | Absorbs damage; clears at turn start. |
| 💥 | Volatile | +50% dmg; 50% self-damage per action. |
| 🔊 | Echo | Last command repeats at turn end. |
| 🌪 | Disorient | 50% miss chance; decays each turn. |
| 🏰 | Fortify | +stacks Block each turn start (permanent). |
| 🛑 | Cursed | Healing −stacks×10%. |
| 💨 | Speed | Next stacks actions −1 AP each. |
| 🕸 | Slow | Next stacks actions +1 AP each. |
| ⚰ | Soul Tax | Turn end: take stacks × AP_spent dmg. |
| 🔄 | Counter | When block breaks: deal stacks dmg back. |

---

## Building the .exe

```
pyinstaller --onefile --add-data "assets:assets" --add-data "save_data:save_data" main.py
```

---

## Dependencies

- Built-in: `os`, `sys`, `json`, `random`, `collections`, `re`, `shutil`, `readline` (Unix)
- Optional: `pyreadline3` (Windows command history), `colorama`, `pyinstaller`
- No external packages required for the UI — all ANSI rendering uses built-in escape codes.

---

## License

MIT License