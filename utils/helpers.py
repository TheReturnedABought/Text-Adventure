# utils/helpers.py
"""
Low-level print utilities and shared ANSI colour constants.

When the window is active (utils/window.py), print_slow() routes
through window.log() so output appears in the LOG panel.
print_status() becomes a no-op (the STATUS panel handles it).
"""
import sys
import time
from utils.constants import MAX_AP, MAX_MANA

BLUE  = "\033[94m"
RESET = "\033[0m"

RARITY_COLORS = {
    "Common":    "\033[37m",
    "Uncommon":  "\033[32m",
    "Rare":      "\033[34m",
    "Legendary": "\033[33m",
}


def _win():
    """Return the window singleton if active, else None."""
    try:
        from utils.window import window
        return window if window._active else None
    except Exception:
        return None


def print_slow(text, delay: float = 0.02):
    """
    Print text with pacing.
    Window active  → instant, routed to LOG panel.
    Window inactive → classic character stream to stdout.
    """
    w = _win()
    if w:
        w.log(str(text))
        # Light sleep so rapid messages don't blur into one wall of text
        time.sleep(min(0.04, delay * max(len(str(text)), 1) * 0.05))
        return
    for char in str(text):
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(delay)
    print()


def print_status(player):
    """
    Print HP/AP/MP inline.
    Suppressed when the window is active — STATUS panel handles it.
    """
    if _win():
        return   # STATUS panel renders this

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
    color = RARITY_COLORS.get(getattr(relic, "rarity", "Common"), "")
    return f"{color}{relic.name}{RESET}"