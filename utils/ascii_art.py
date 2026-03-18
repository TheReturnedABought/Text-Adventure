# utils/ascii_art.py
"""
ASCII art strings and a small display helper.
All art is stored as plain multiline strings.
print_art() centres each line within a given width.
"""
from utils.helpers import print_slow


def print_art(art, indent=2):
    """Print each line of an art string with a fixed left indent."""
    for line in art.strip("\n").splitlines():
        print(" " * indent + line)
    print()


# ── Room banners ──────────────────────────────────────────────────────────────

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

# ── Relic art ─────────────────────────────────────────────────────────────────

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

# ── Map to relic name ─────────────────────────────────────────────────────────

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