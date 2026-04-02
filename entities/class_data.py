# entities/class_data.py
"""
Single source of truth for every class command.

Each command is a CommandDef dict:
    {
        "name":        str        — the typed command,
        "desc":        str        — shown in help and level-up,
        "ap_cost":     int|None   — None → len(name) rule applies,
        "mp_cost":     int        — 0 for non-mage or free commands,
        "unlock_mode": "auto"|"choice",
    }

Helpers (used by display.py, combat.py, level-up screen)
---------------------------------------------------------
cmd_ap_cost(cmd)         → int   resolves None → len(name)
cmd_mp_cost(cmd)         → int
get_command_def(cls, nm) → dict|None
get_command_display(cmd) → "N AP" or "N AP +M MP"

Changing a desc, ap_cost, or mp_cost here automatically propagates to:
  • show_help()  (display.py)
  • _calc_ap_cost() / combat HUD  (combat.py)
  • show_levelup()  (display.py)
"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def cmd_ap_cost(cmd: dict) -> int:
    """Return AP cost: explicit override, or len(name) if None."""
    override = cmd.get("ap_cost")
    return override if override is not None else len(cmd["name"])


def cmd_mp_cost(cmd: dict) -> int:
    return cmd.get("mp_cost", 0)


def get_command_def(char_class: str, cmd_name: str) -> dict | None:
    """Find a CommandDef by class and command name. Returns None if not found."""
    for tier in CLASS_COMMANDS.get(char_class, {}).values():
        for cmd in tier:
            if cmd["name"] == cmd_name:
                return cmd
    return None


def get_command_display(cmd: dict) -> str:
    """Return a concise cost string: '6 AP' or '4 AP +1 MP'."""
    ap = cmd_ap_cost(cmd)
    mp = cmd_mp_cost(cmd)
    return f"{ap} AP +{mp} MP" if mp else f"{ap} AP"


# ── Unlock schedule ───────────────────────────────────────────────────────────
#   Level  2 → 1 command, auto-unlocked
#   Level  4 → choose 1 of 2
#   Level  5 → choose 1 of 3
#   Level 10 → choose 1 of 3
#   Level 15 → choose 1 of 3
#   Level 20 → choose 1 of 3


# ── Soldier ───────────────────────────────────────────────────────────────────

SOLDIER_COMMANDS = {
    2: [
        {
            "name": "brace",
            "desc": "Gain 1d6 Block; gain 1d6+2 instead if you currently have no Block.",
            "ap_cost": None, "mp_cost": 0, "unlock_mode": "auto",
        },
    ],
    5: [
        {
            "name": "guard",
            "desc": "Gain 1d6+1 Block; apply Counter 10 — when your Block absorbs damage, deal 10 back.",
            "ap_cost": None, "mp_cost": 0, "unlock_mode": "choice",
        },
        {
            "name": "berserk",
            "desc": "Gain Rage ×2 + Volatile.",
            "ap_cost": None, "mp_cost": 0, "unlock_mode": "choice",
        },
        {
            "name": "discipline",
            "desc": "Remove core debuffs; gain 3d10+3 Block; cannot attack this turn.",
            "ap_cost": None, "mp_cost": 0, "unlock_mode": "choice",
        },
    ],
    10: [
        {
            "name": "rally",
            "desc": "Gain 1d10 Block; your next attack gains bonus damage equal to that roll.",
            "ap_cost": None, "mp_cost": 0, "unlock_mode": "choice",
        },
        {
            "name": "cleave",
            "desc": "Hit all enemies twice for 75% damage each.",
            "ap_cost": None, "mp_cost": 0, "unlock_mode": "choice",
        },
        {
            "name": "fortify",
            "desc": "Apply Fortify 4 — gain 4 Block at the start of every turn this combat.",
            "ap_cost": None, "mp_cost": 0, "unlock_mode": "choice",
        },
    ],
    4: [
        {
            "name": "downcut",
            "desc": "Deal 2d10+4; cannot gain Block for the rest of this turn.",
            "ap_cost": 7, "mp_cost": 1, "unlock_mode": "choice",
        },
        {
            "name": "defiant",
            "desc": "If you end the round with Block, gain +2 AP next turn and +2 Strength.",
            "ap_cost": 7, "mp_cost": 1, "unlock_mode": "choice",
        },
    ],
    15: [
        {
            "name": "warcry",
            "desc": "Apply Weak 2 + Vulnerable 2 to all enemies.",
            "ap_cost": None, "mp_cost": 1, "unlock_mode": "choice",
        },
        {
            "name": "sentinel",
            "desc": "Gain 2d8 Block; enemies who hit you take 4 damage back.",
            "ap_cost": None, "mp_cost": 0, "unlock_mode": "choice",
        },
        {
            "name": "execute",
            "desc": "2× dmg; 3× if enemy <30% HP; +1× per 10 Block consumed.",
            "ap_cost": None, "mp_cost": 0, "unlock_mode": "choice",
        },
    ],
    20: [
        {
            "name": "juggernaut",
            "desc": "Attack; gain Block equal to damage dealt.",
            "ap_cost": None, "mp_cost": 0, "unlock_mode": "choice",
        },
        {
            "name": "unbreakable",
            "desc": "Block no longer resets at end of turn this combat.",
            "ap_cost": None, "mp_cost": 0, "unlock_mode": "choice",
        },
        {
            "name": "overwhelm",
            "desc": "Apply Weak 2 + Vulnerable 2 to target; Stun 1 if 3+ statuses.",
            "ap_cost": None, "mp_cost": 0, "unlock_mode": "choice",
        },
    ],
    12: [
        {"name": "quickshot", "desc": "Hit 4 times for 1d4+2 each (same or different targets).", "ap_cost": 9, "mp_cost": 0, "unlock_mode": "choice"},
        {"name": "plan", "desc": "Next command costs 1d4 less AP (min 1) and 1 less MP (min 1).", "ap_cost": 4, "mp_cost": 0, "unlock_mode": "choice"},
        {"name": "shielded", "desc": "Apply Fortify 2; on your next turn, each damaging action grants 2d4 Block.", "ap_cost": 8, "mp_cost": 1, "unlock_mode": "choice"},
    ],
}


# ── Rogue ─────────────────────────────────────────────────────────────────────

ROGUE_COMMANDS = {
    2: [
        {
            "name": "cut",
            "desc": "Deal 5–8 damage.",
            "ap_cost": None, "mp_cost": 0, "unlock_mode": "auto",
        },
    ],
    4: [
        {"name": "aim", "desc": "Next attack cannot miss (once/turn); gain Strength 1 this combat.", "ap_cost": 3, "mp_cost": 1, "unlock_mode": "choice"},
        {"name": "weave", "desc": "Gain Dexterity 1 this combat.", "ap_cost": 5, "mp_cost": 1, "unlock_mode": "choice"},
    ],
    5: [
        {
            "name": "flow",
            "desc": "Gain Speed 5 — your next 5 actions each cost 1 fewer AP.",
            "ap_cost": None, "mp_cost": 0, "unlock_mode": "choice",
        },
        {
            "name": "feint",
            "desc": "Disorient target; your next attack this turn cannot miss.",
            "ap_cost": None, "mp_cost": 0, "unlock_mode": "choice",
        },
        {
            "name": "mark",
            "desc": "Apply Vulnerable 2; your next hit deals +5 damage.",
            "ap_cost": None, "mp_cost": 0, "unlock_mode": "choice",
        },
    ],
    10: [
        {
            "name": "venom",
            "desc": "Apply Poison 3; +1 stack if the target is Vulnerable.",
            "ap_cost": None, "mp_cost": 0, "unlock_mode": "choice",
        },
        {
            "name": "flurry",
            "desc": "Hit 3 times for 1d4+3 each (same or different targets).",
            "ap_cost": None, "mp_cost": 0, "unlock_mode": "choice",
        },
        {
            "name": "dash",
            "desc": "Gain 1d6+2 Block, deal 8 damage, and gain Speed 1.",
            "ap_cost": None, "mp_cost": 0, "unlock_mode": "choice",
        },
    ],
    15: [
        {
            "name": "toxin",
            "desc": "Double target's Poison stacks (max 8).",
            "ap_cost": None, "mp_cost": 0, "unlock_mode": "choice",
        },
        {
            "name": "assault",
            "desc": "Strike 3+ times; hits increase with prior actions this turn.",
            "ap_cost": None, "mp_cost": 0, "unlock_mode": "choice",
        },
        {
            "name": "evade",
            "desc": "Gain Evade this round: 50% chance enemy actions miss you; each trigger gives +2 AP next turn.",
            "ap_cost": None, "mp_cost": 0, "unlock_mode": "choice",
        },
    ],
    20: [
        {
            "name": "pandemic",
            "desc": "Apply Poison 6; +3 more if target is already Poisoned.",
            "ap_cost": None, "mp_cost": 0, "unlock_mode": "choice",
        },
        {
            "name": "assassinate",
            "desc": "Massive damage; ×1.5 first action this turn or target <40% HP; ×2 if both.",
            "ap_cost": None, "mp_cost": 0, "unlock_mode": "choice",
        },
        {
            "name": "shadowstrike",
            "desc": "Deal 5 × (actions taken THIS turn) damage (cap 50).",
            "ap_cost": None, "mp_cost": 0, "unlock_mode": "choice",
        },
    ],
    12: [
        {"name": "quickshot", "desc": "Hit 4 times for 1d4+2 each (same or different targets).", "ap_cost": 9, "mp_cost": 0, "unlock_mode": "choice"},
        {"name": "plan", "desc": "Next command costs 1d4 less AP (min 1) and 1 less MP (min 1).", "ap_cost": 4, "mp_cost": 0, "unlock_mode": "choice"},
        {"name": "shielded", "desc": "Apply Fortify 2; on your next turn, each damaging action grants 2d4 Block.", "ap_cost": 8, "mp_cost": 1, "unlock_mode": "choice"},
    ],
}


# ── Mage ──────────────────────────────────────────────────────────────────────

MAGE_COMMANDS = {
    2: [
        {
            "name": "spark",
            "desc": "Hit twice for 1d4+2 Lightning damage each (same or different targets).",
            "ap_cost": None, "mp_cost": 0, "unlock_mode": "auto",
        },
    ],
    4: [
        {"name": "conduit", "desc": "Next non-AOE spell hits one additional target.", "ap_cost": 7, "mp_cost": 2, "unlock_mode": "choice"},
        {"name": "icewall", "desc": "Gain 2d8+3 Block and apply Weak 1 to all enemies.", "ap_cost": 8, "mp_cost": 1, "unlock_mode": "choice"},
    ],
    5: [
        {
            "name": "bolt",
            "desc": "Deal 2d8+4 damage and apply Vulnerable 1.",
            "ap_cost": None, "mp_cost": 2, "unlock_mode": "choice",
        },
        {
            "name": "coalesce",
            "desc": "Mana solidifies — gain 17 Block; all spells cost −1 MP for 2 turns.  [free — no MP]",
            "ap_cost": None, "mp_cost": 0, "unlock_mode": "choice",
        },
        {
            "name": "delay",
            "desc": "Apply Slow 1 to target — each Slow stack gives a 50% chance to lose their turn.",
            "ap_cost": None, "mp_cost": 1, "unlock_mode": "choice",
        },
    ],
    10: [
        {
            "name": "wave",
            "desc": "Deal 1d6+4 Lightning damage to all enemies.",
            "ap_cost": None, "mp_cost": 1, "unlock_mode": "choice",
        },
        {
            "name": "storm",
            "desc": "Deal 2d6+6 damage to all enemies.",
            "ap_cost": None, "mp_cost": 2, "unlock_mode": "choice",
        },
        {
            "name": "drain",
            "desc": "Deal 1d6+2 damage and heal that amount.",
            "ap_cost": None, "mp_cost": 1, "unlock_mode": "choice",
        },
    ],
    15: [
        {
            "name": "rift",
            "desc": "Restore 3 MP; apply Vulnerable 1 to yourself and all enemies.",
            "ap_cost": None, "mp_cost": 1, "unlock_mode": "choice",
        },
        {
            "name": "silence",
            "desc": "Stun one target 1 turn; apply Weak 2.",
            "ap_cost": None, "mp_cost": 1, "unlock_mode": "choice",
        },
        {
            "name": "torment",
            "desc": "Apply 2d4+2 Poison and Disorient to one target.",
            "ap_cost": None, "mp_cost": 2, "unlock_mode": "choice",
        },
    ],
    20: [
        {
            "name": "obliterate",
            "desc": "Deal 60–80 damage to one target.",
            "ap_cost": None, "mp_cost": 3, "unlock_mode": "choice",
        },
        {
            "name": "tempest",
            "desc": "Deal 3d8+3 damage to all enemies.",
            "ap_cost": None, "mp_cost": 3, "unlock_mode": "choice",
        },
        {
            "name": "apocalypse",
            "desc": "Deal (total status stacks across ALL living enemies) × 5 (cap 60).",
            "ap_cost": None, "mp_cost": 3, "unlock_mode": "choice",
        },
    ],
    12: [
        {"name": "quickshot", "desc": "Hit 4 times for 1d4+2 each (same or different targets).", "ap_cost": 9, "mp_cost": 0, "unlock_mode": "choice"},
        {"name": "plan", "desc": "Next command costs 1d4 less AP (min 1) and 1 less MP (min 1).", "ap_cost": 4, "mp_cost": 0, "unlock_mode": "choice"},
        {"name": "shielded", "desc": "Apply Fortify 2; on your next turn, each damaging action grants 2d4 Block.", "ap_cost": 8, "mp_cost": 1, "unlock_mode": "choice"},
    ],
}


# ── Master table ──────────────────────────────────────────────────────────────

CLASS_COMMANDS = {
    "soldier": SOLDIER_COMMANDS,
    "rogue":   ROGUE_COMMANDS,
    "mage":    MAGE_COMMANDS,
}


# ── Class metadata ────────────────────────────────────────────────────────────

CLASS_RELIC_NAMES = {
    "soldier": "iron-cast helm",
    "rogue":   "sleightmakers glove",
    "mage":    "aether tapestry",
}

CLASS_DESCRIPTIONS = {
    "soldier": (
        "⚔  SOLDIER\n"
        "    A battle-hardened warrior who masters the tension between raw damage\n"
        "    and iron defence. Block powers your mightiest strikes.\n"
        "    Starter relic: Iron-Cast Helm — gain 12 Block at the start of each combat."
    ),
    "rogue": (
        "🗡  ROGUE\n"
        "    A swift, cunning fighter living in the space between burst damage,\n"
        "    chained actions, and creeping poison.\n"
        "    Starter relic: Sleightmaker's Glove — the letter 'l' does not count toward AP cost."
    ),
    "mage": (
        "🔮  MAGE\n"
        "    An arcane wielder who manages Mana as carefully as AP.\n"
        "    Every spell costs MP — spend it wisely.\n"
        "    Starter relic: Aether-Spun Tapestry — Max MP +2; restore 1 MP each turn."
    ),
}
