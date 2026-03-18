# Text Adventure Game

A small, fun **text-based adventure game** in Python with combat, inventory, and action-point mechanics. Each action in combat consumes **action points (AP) based on the number of letters** in the command. Explore rooms, collect items, and defeat enemies to win!

---

## Features

- Explore multiple rooms with descriptions and items.
- Turn-based combat system with **letter-based AP economy**.
- Player inventory system with usable items.
- Multiple enemy types with simple AI.
- Optional ASCII art and color formatting.
- Save and load game state using JSON files.
- Ready for **.exe packaging** using PyInstaller.

---

## Installation

1. Clone the repository:

```
git clone https://github.com/yourusername/text-adventure.git
cd text-adventure
```

2. Create a Python virtual environment:

```
python -m venv venv
```

3. Activate the virtual environment:

- **Windows:**
```
venv\Scripts\activate
```

- **macOS/Linux:**
```
source venv/bin/activate
```

4. Install dependencies:

```
pip install -r requirements.txt
```

---

## Running the Game

```
python main.py
```

---

## Building the `.exe`

Use PyInstaller to create a standalone `.exe`:

```
pyinstaller --onefile --add-data "assets:assets" main.py
```

- `--onefile`: packs everything into a single `.exe`.
- `--add-data "assets:assets"`: ensures your ASCII art and JSON files are included.

The `.exe` will appear in the `dist/` folder.

---

## Folder Structure

```
text_adventure/
│
├── main.py                  # Entry point, game loop, command routing
├── game_engine/
│   ├── engine.py            # GameEngine initialiser (expandable)
│   └── parser.py            # Command parser with single-letter aliases
├── entities/
│   ├── player.py            # Player stats, inventory, relics, XP/levelling
│   ├── enemy.py             # Enemy class with weighted move selection
│   ├── enemy_moves.py       # Reusable move effect functions and factory
│   ├── relic.py             # Relic base class and trigger constants
│   └── item.py              # Item base class
├── rooms/
│   ├── room.py              # Room class (items, relics, enemies, connections)
│   └── map_data.py          # World layout, enemy placement, relic placement
│   └── enemy_data.py          # Enemy definitions
└── utils/
    ├── constants.py         # MAX_HEALTH, MAX_AP, MAX_MANA, XP_PER_LEVEL
    ├── helpers.py           # print_slow, print_status, make_bar, ANSI colours
    ├── display.py           # show_room, show_intro, show_help, show_levelup
    ├── actions.py           # Exploration actions (move, take, drop, rest, etc.)
    ├── combat.py            # Full combat loop, player turn, enemy turn
    ├── status_effects.py    # All status apply/consume/tick logic
    └── relics.py            # All relic class definitions and registry
```

---

## Dependencies

See `requirements.txt` for all Python packages needed.

- Built-in Python packages: `os`, `sys`, `json`, `random`
- External packages:
  - `colorama` (terminal colors)
  - `pyfiglet` (optional ASCII banners)
  - `rich` (optional fancy console output)
  - `pyinstaller` (for `.exe` build, usually installed globally)

---

## License

MIT License
