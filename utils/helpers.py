# utils/helpers.py
import sys
import time
from utils.constants import MAX_AP


def print_slow(text, delay=0.02):
    """Print text character by character for dramatic effect."""
    for char in str(text):
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(delay)
    print()


def print_status(player):
    """Print a compact status bar for the player."""
    hp_bar = make_bar(player.health, player.max_health, length=20, fill="█", empty="░")
    ap_bar = make_bar(player.current_ap, MAX_AP, length=12, fill="◆", empty="◇")
    print(f"  HP [{hp_bar}] {player.health}/{player.max_health}  "
          f"AP [{ap_bar}] {player.current_ap}/{MAX_AP}  "
          f"LVL {player.level}  XP {player.xp}")


def make_bar(current, maximum, length=20, fill="█", empty="░"):
    filled = int((current / max(maximum, 1)) * length)
    return fill * filled + empty * (length - filled)