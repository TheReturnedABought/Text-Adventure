# utils/ascii_art.py
"""
ASCII art strings and display helpers.

New in this version
───────────────────
ENEMY_ART  : dict[enemy_name -> list[str]]
             Small per-enemy ASCII portraits shown in the UI combat art panel.
             If an enemy has no entry, only its stat card is shown.

ROOM_ART   : dict[room_name -> str]
             Maps room names to the multiline art strings already defined
             below, plus new entries for rooms that previously lacked art.
             Consumed by UIManager._room_art() for the explore art panel.
"""
from utils.helpers import print_slow


def print_art(art, indent=2):
    """Print each line of an art string with a fixed left indent."""
    for line in art.strip("\n").splitlines():
        print(" " * indent + line)
    print()


# ════════════════════════════════════════════════════════════════════════════════
#  Room banner art  (multiline strings)
# ════════════════════════════════════════════════════════════════════════════════

ENTRANCE_HALL = r"""
    ___________
   |     _     |
   |    | |    |
   |    | |    |
___|____|_|____|___
"""

RIDDLE_HALL = r"""
  ??  carved stone  ??
  ?                  ?
  ?   riddles line   ?
  ?    every wall    ?
  ??????????????????
"""

PUZZLE_ROOM = r"""
      *   *
    * * * * *
  * * * * * * *
    * * * * *
      * * *
        *
"""

RATSSSS = r"""
  .    .   .    .
    (\ /)  (\ /)
    ( o.o) ( o.o)
    (> < ) (> < )
  ~~~~~~~~~~~~~~~~~
"""

SERVANTS_QUARTERS = r"""
  ___   ___   ___
 |   | |   | |   |
 |   | |   | |   |
 |___| |___| |___|
 = = = = = = = = =
"""

CRYPT_GATE = r"""
     . . .
   .       .
  .  . . .  .
  . ( o o ) .
  .  (\_/)  .
   .  ---  .
  |_________|
  |  | | |  |
  |  | | |  |
"""

CROSSROADS = r"""
         |
         |
  ───────+───────
         |
         |
        [⊕]
"""

KITCHEN = r"""
  ___________________
 |  ___    ___    ___|
 | |   |  |   |  |   |
 | |___|  |___|  |___|
 |___________________|
   [_]    [_]    [_]
"""

LOCKED_HALL = r"""
  🔒─────────────🔒
  │               │
  │   SEALED      │
  │   PASSAGES    │
  │               │
  └───────────────┘
"""

PUZZLE_ALCOVE = r"""
   ┌───────────┐
   │  ╔═════╗  │
   │  ║ ??? ║  │
   │  ╚═════╝  │
   │   [lock]  │
   └───────────┘
"""

# ════════════════════════════════════════════════════════════════════════════════
#  Relic art  (multiline strings — legacy, used by show_relics / take messages)
# ════════════════════════════════════════════════════════════════════════════════

IRON_CAST_HELM = r"""
    /\/\
   /    \
  | (||) |
   \    /
   [====]
"""

SLEIGHTMAKERS_GLOVE = r"""
    _____
   /     \
  | ||| | |
  |  ___  |
   \_____/
"""

AETHER_TAPESTRY = r"""
  * . * . *
  . * . * .
  * . * . *
  . * . * .
  * . * . *
"""

FROG_STATUE = r"""
   @..@
  (----)
 ( >__< )
 ^^ ~~ ^^
"""

VENOM_GLAND = r"""
   _   _
  ( o o )
  |  ^  |
  | ~~~ |
   \___/
"""

IRON_WILL = r"""
    ___
   /   \
  | | | |
  |_____|
   |   |
"""

THORN_BRACELET = r"""
  /\/\/\/\
 / thorns  \
|  )(  )(  |
 \ thorns  /
  \/\/\/\/
"""

BERSERKER_HELM = r"""
   /\  /\
  /  \/  \
 | >    < |
 |   /\   |
  \_/  \_/
"""

CURSED_EYE = r"""
   _______
  /       \
 | >( * )< |
  \_______/
     | |
"""

WHISPER_CHARM = r"""
  ~~~~
 ~ .. ~
~  ()  ~
 ~ .. ~
  ~~~~
"""

BLESSED_EYE = r"""
   _______
  /       \
 | >( o )< |
  \_______/
    *   *
"""

SILENT_LAMB_WOOL = r"""
  (  .  .  )
  (  .  .  )
   \      /
    \ -- /
     \  /
"""

BEARS_HIDE = r"""
  / \  / \
 (   \/   )
  \ (  ) /
   \(  )/
    \  /
"""

VAMPIRIC_BLADE = r"""
     |
    /|\
   / | \
  /  |  \
     |
    ===
"""

WHETSTONE = r"""
  _______
 /       \
|  / / /  |
|  / / /  |
 \_______/
"""

ECHO_CHAMBER = r"""
  )  )  )
 )) )) ))
(((((((((
 )) )) ))
  )  )  )
"""

# ── Relic name → art ─────────────────────────────────────────────────────────

RELIC_ART = {
    "Iron-Cast Helm":       IRON_CAST_HELM,
    "Sleightmaker's Glove": SLEIGHTMAKERS_GLOVE,
    "Aether-Spun Tapestry": AETHER_TAPESTRY,
    "Frog Statue":          FROG_STATUE,
    "Venom Gland":          VENOM_GLAND,
    "Iron Will":            IRON_WILL,
    "Thorn Bracelet":       THORN_BRACELET,
    "Berserker Helm":       BERSERKER_HELM,
    "Cursed Eye":           CURSED_EYE,
    "Whisper Charm":        WHISPER_CHARM,
    "Blessed Eye":          BLESSED_EYE,
    "Silent Lamb Wool":     SILENT_LAMB_WOOL,
    "Bear's Hide":          BEARS_HIDE,
    "Vampiric Blade":       VAMPIRIC_BLADE,
    "Whetstone":            WHETSTONE,
    "Echo Chamber":         ECHO_CHAMBER,
}

# ════════════════════════════════════════════════════════════════════════════════
#  Enemy art  (list of strings — each string is one row of the portrait)
#  Keep each portrait ≤ 7 rows and ≤ 18 chars wide for clean side-by-side display.
# ════════════════════════════════════════════════════════════════════════════════

ENEMY_ART: dict[str, list[str]] = {

    "Castle Guard": [
        "   ╔══╗   ",
        "   ║()║   ",
        "  ╔╩══╩╗  ",
        "  ║████║  ",
        "  ╚═╤══╝  ",
        "   ╱ ╲   ",
    ],

    "Goblin": [
        "  ∩___∩  ",
        " ( ´.` ) ",
        "  (> <)  ",
        "   | |   ",
    ],

    "Goblin Guard": [
        "  ∩___∩  ",
        " (>._.<) ",
        " /|_█_|\ ",
        "   | |   ",
    ],

    "Goblin Archer": [
        "  ∩___∩  ",
        " ( °.°) )",
        "  /)(    ",
        "  |||    ",
    ],

    "Giant Rat": [
        "  /\\/|   ",
        " (o.o)   ",
        "  \\___/  ",
        "  (~V~)  ",
    ],

    "Rat Swarm": [
        " oo  oo  oo ",
        "(oo)(oo)(oo)",
        " vv  vv  vv ",
        "~~~~~~~~~~~~",
    ],

    "Skeleton Servant": [
        "  _____  ",
        " (o) (o) ",
        " | ___ | ",
        " /|   |\\ ",
        "  |   |  ",
    ],

    "Skeleton": [
        "  _____  ",
        " (o) (o) ",
        " | ___ | ",
        " /|   |\\ ",
        "  |   |  ",
    ],

    "Rotting Zombie": [
        "  ~~~~~  ",
        " (x) (x) ",
        " |  ~  | ",
        " /|   |\\ ",
        "  |   |  ",
    ],

    "Wraith": [
        "   ~~~   ",
        "  /o  o\\ ",
        " (  ~~  )",
        " /~~~~~~\\",
        "/        \\",
    ],

    "Bone Archer": [
        "  _____  ",
        " (o) (o) ",
        "  \\___/  ",
        " /|) |)\\ ",
        "  |   |  ",
    ],

    "Crypt Warden": [
        " /╔═══╗\\ ",
        " |║ ☠ ║| ",
        " \\╠═══╣/ ",
        "  ║███║  ",
        "  ╔═╤═╗  ",
        "  ╚═╧═╝  ",
    ],
}

# ════════════════════════════════════════════════════════════════════════════════
#  Room name → art string  (consumed by UIManager._room_art)
# ════════════════════════════════════════════════════════════════════════════════

ROOM_ART: dict[str, str] = {
    "Entrance Hall":      ENTRANCE_HALL,
    "Riddle Hall":        RIDDLE_HALL,
    "Puzzle Room":        PUZZLE_ROOM,
    "Ratssss!":           RATSSSS,
    "Servants' Quarters": SERVANTS_QUARTERS,
    "The Crypt Gate":     CRYPT_GATE,
    "The Crossroads":     CROSSROADS,
    "Kitchen":            KITCHEN,
    "Locked Hall":        LOCKED_HALL,
    "Puzzle Alcove":      PUZZLE_ALCOVE,
}