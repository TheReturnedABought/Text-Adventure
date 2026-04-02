# utils/constants.py
"""
Single source of truth for every numeric game constant.

Dice expressions (used by combat.py, display.py)
─────────────────────────────────────────────────
  BASE_ATTACK_DICE = "2d6+6"   → range  8–18, avg 13
  BASE_HEAL_DICE   = "1d8+7"   → range  8–15, avg 11.5

Backward-compat aliases still referenced by display code:
  BASE_ATTACK_MIN / MAX  →  8 / 18
  BASE_HEAL_MIN   / MAX  →  8 / 15
"""

# ── Player stats ──────────────────────────────────────────────────────────────
MAX_HEALTH   = 100
MAX_AP       = 12
MAX_MANA     = 5
XP_PER_LEVEL = 30

# ── Dice expressions ──────────────────────────────────────────────────────────
BASE_ATTACK_DICE = "2d6+6"
BASE_HEAL_DICE   = "1d8+7"
BASE_ENEMY_DICE  = "1d6+2"   # enemy fallback

# Backward-compat
BASE_ATTACK_MIN = 8
BASE_ATTACK_MAX = 18
BASE_HEAL_MIN   = 8
BASE_HEAL_MAX   = 15

# ── Base command costs ────────────────────────────────────────────────────────
BASE_COMMANDS = {
    "attack": {
        "ap_cost": 6, "mp_cost": 0,
        "desc": "Deal 8–18 damage (2d6+6).",
    },
    "heal": {
        "ap_cost": 4, "mp_cost": 1,
        "desc": "Restore 8–15 HP (1d8+7).",
    },
    "block": {
        "ap_cost": 5, "mp_cost": 0,
        "desc": "Gain 7 Block this turn.",
    },
}

# ── Combat values ─────────────────────────────────────────────────────────────
BASE_BLOCK        = 7
UNBREAKABLE_CAP   = 6
HEAL_MP_COST      = 1

# ── Status caps ───────────────────────────────────────────────────────────────
MAX_BLEED_STACKS  = 5
MAX_POISON_DOUBLE = 8

# ── Misc ──────────────────────────────────────────────────────────────────────
MAX_ENEMIES_PER_ROOM  = 4
COMMAND_HISTORY_SIZE  = 20