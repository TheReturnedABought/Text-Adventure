# utils/helpers.py
import sys
import time
from utils.constants import MAX_AP, MAX_MANA

BLUE  = "\033[94m"
RESET = "\033[0m"

# Rarity colours (used when displaying relic names)
RARITY_COLORS = {
    "Common":    "\033[37m",    # grey/white
    "Uncommon":  "\033[32m",    # green
    "Rare":      "\033[34m",    # blue
    "Legendary": "\033[33m",    # gold/yellow
}


def print_slow(text, delay=0.02):
    for char in str(text):
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(delay)
    print()


def print_status(player):
    hp_bar   = make_bar(player.health,     player.max_health, length=20, fill="█", empty="░")
    ap_bar   = make_bar(player.current_ap, MAX_AP,            length=12, fill="◆", empty="◇")
    mana_bar = make_bar(player.mana,       MAX_MANA,          length=5,  fill="●", empty="○")
    print(f"  HP [{hp_bar}] {player.health}/{player.max_health}  "
          f"AP [{ap_bar}] {player.current_ap}/{MAX_AP}  "
          f"{BLUE}MP [{mana_bar}] {player.mana}/{MAX_MANA}{RESET}  "
          f"LVL {player.level}  XP {player.xp}")


def make_bar(current, maximum, length=20, fill="█", empty="░"):
    filled = int((current / max(maximum, 1)) * length)
    return fill * filled + empty * (length - filled)


def rarity_colored(relic):
    """Return the relic's name wrapped in its rarity colour."""
    color = RARITY_COLORS.get(getattr(relic, "rarity", "Common"), "")
    return f"{color}{relic.name}{RESET}"