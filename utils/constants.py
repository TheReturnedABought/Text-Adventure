# utils/constants.py
"""
Single source of truth for every numeric game constant.
Import from here — never hardcode magic numbers elsewhere.
"""

# ── Player stats ──────────────────────────────────────────────────────────────
MAX_HEALTH   = 100
MAX_AP       = 12
MAX_MANA     = 5
XP_PER_LEVEL = 30   # threshold = level × XP_PER_LEVEL

# ── Base command costs ────────────────────────────────────────────────────────
# Changing these propagates to show_help(), the combat HUD, and _calc_ap_cost().
BASE_COMMANDS = {
    "attack": {"ap_cost": 6, "mp_cost": 0, "desc": "Deal {atk_min}–{atk_max} damage to a target."},
    "heal":   {"ap_cost": 4, "mp_cost": 1, "desc": "Restore {heal_min}–{heal_max} HP."},
    "block":  {"ap_cost": 5, "mp_cost": 0, "desc": "Gain {base_block} Block this turn."},
}

# ── Combat values ─────────────────────────────────────────────────────────────
BASE_BLOCK        = 7    # block command base Block granted
UNBREAKABLE_CAP   = 6    # max damage per hit while Unbreakable is active

BASE_ATTACK_MIN   = 8
BASE_ATTACK_MAX   = 18
BASE_HEAL_MIN     = 8
BASE_HEAL_MAX     = 15
HEAL_MP_COST      = 1    # MP drained by the heal command

# ── Status caps ───────────────────────────────────────────────────────────────
MAX_BLEED_STACKS  = 5
MAX_POISON_DOUBLE = 8    # cap for toxin / poison-double effects

# ── Misc ──────────────────────────────────────────────────────────────────────
MAX_ENEMIES_PER_ROOM  = 4
COMMAND_HISTORY_SIZE  = 20