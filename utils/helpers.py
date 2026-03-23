# utils/helpers.py
"""
Low-level print utilities and shared ANSI colour constants.

When the UI is active (utils/ui.py), print_slow() routes through
ui.log() so output appears in the LOG panel instead of raw stdout.
"""
import sys
import time
from utils.constants import MAX_AP, MAX_MANA

# ── ANSI colours ──────────────────────────────────────────────────────────────
BLUE  = "\033[94m"
RESET = "\033[0m"

RARITY_COLORS = {
    "Common":    "\033[37m",
    "Uncommon":  "\033[32m",
    "Rare":      "\033[34m",
    "Legendary": "\033[33m",
}


def print_slow(text, delay=0.02):
    """
    Print text slowly.  When the terminal UI is enabled the text is
    routed to the UI log panel (no character-by-character delay needed
    there; the panel updates in real-time).  Otherwise the classic
    character-streaming output is used.
    """
    try:
        from utils.ui import ui
        if ui._active:
            ui.log(str(text))
            # Brief pause proportional to text length to preserve the
            # pacing feel even without per-character streaming.
            time.sleep(min(0.06, delay * max(len(str(text)), 1) * 0.08))
            return
    except Exception:
        pass
    # ── Classic mode (UI not active) ──────────────────────────────────────────
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