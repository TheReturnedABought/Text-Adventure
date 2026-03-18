# entities/class_data.py
"""
Class definitions, command tables, and metadata.

Unlock schedule:
  Level  2 → 1 command, auto-unlocked
  Level  5 → choose 1 of 3
  Level 10 → choose 1 of 3
  Level 15 → choose 1 of 3
  Level 20 → choose 1 of 3
"""

# ─────────────────────────────────────────────────────────────────────────────
#  Command tables  {level: [{name, desc}, ...]}
# ─────────────────────────────────────────────────────────────────────────────

SOLDIER_COMMANDS = {
    2: [
        {"name": "brace", "desc": "Gain 3 Block; if you have no Block, gain 8 instead."},
    ],
    5: [
        {"name": "guard",      "desc": "Gain 8 Block; if the enemy breaks your Block, deal 10 damage back."},
        {"name": "berserk",    "desc": "Gain Rage ×2 + Volatile."},
        {"name": "discipline", "desc": "Remove all debuffs; gain 15 Block; cannot attack this turn."},
    ],
    10: [
        {"name": "rally",   "desc": "Gain 6 Block; your next attack deals +6 damage."},
        {"name": "cleave",  "desc": "Hit all enemies twice for 75% damage each."},
        {"name": "fortify", "desc": "Gain 5 Block now and at the end of every turn this combat."},
    ],
    15: [
        {"name": "warcry",     "desc": "Apply Weak 2 + Vulnerable 2 to all enemies."},
        {"name": "sentinel",   "desc": "Gain 16 Block; enemies who hit you take 4 damage back."},
        {"name": "execute",    "desc": "2× dmg; 3× if enemy <30% HP; +1× per 10 Block consumed."},
    ],
    20: [
        {"name": "juggernaut",  "desc": "Attack; gain Block equal to damage dealt."},
        {"name": "unbreakable", "desc": "Damage capped at 6; Block does not clear between turns."},
        {"name": "overwhelm",   "desc": "Apply Weak 2 + Vulnerable 2 to target; Stun 1 if 3+ statuses."},
    ],
}

ROGUE_COMMANDS = {
    2: [
        {"name": "cut", "desc": "Deal 6–10 damage."},
    ],
    5: [
        {"name": "flow",  "desc": "Actions cost −1 AP this turn; cannot repeat the same command."},
        {"name": "feint", "desc": "Disorient target; your next attack this turn cannot miss."},
        {"name": "mark",  "desc": "Apply Vulnerable 2; your next hit deals +5 damage."},
    ],
    10: [
        {"name": "venom",  "desc": "Apply Poison 3; +1 stack if the target is Vulnerable."},
        {"name": "flurry", "desc": "Strike 3 times (relic letter-effects count per hit except 'l' once, 'r' twice)."},
        {"name": "dash",   "desc": "Gain 8 Block and deal 8 damage."},
    ],
    15: [
        {"name": "toxin",   "desc": "Double target's Poison stacks (max 8)."},
        {"name": "assault", "desc": "Strike 3+ times; hits increase with prior actions this turn."},
        {"name": "evade",   "desc": "Dodge the next enemy attack; if triggered, gain +2 AP next turn."},
    ],
    20: [
        {"name": "pandemic",     "desc": "Apply Poison 6; +3 more if target is already Poisoned."},
        {"name": "assassinate",  "desc": "Massive damage; 1.5× bonus if first action this turn."},
        {"name": "shadowstrike", "desc": "Deal 6 × (total actions taken this combat) damage."},
    ],
}

MAGE_COMMANDS = {
    2: [
        {"name": "spark", "desc": "Deal 8–12 Lightning damage.  [1 MP]"},
    ],
    5: [
        {"name": "bolt",  "desc": "Deal 18–26 damage.  [1 MP]"},
        {"name": "ward",  "desc": "Gain 8 Block; spells cost −1 MP this turn.  [1 MP]"},
        {"name": "curse", "desc": "Apply Vulnerable 2 + Weak 2.  [free]"},
    ],
    10: [
        {"name": "blaze", "desc": "Apply Burn 3 (Poison) + Volatile to target.  [2 MP]"},
        {"name": "charm", "desc": "Stun target 1 turn; Charm cannot be reused until next turn.  [2 MP]"},
        {"name": "drain", "desc": "Consume target's Poison; heal that many HP.  [1 MP]"},
    ],
    15: [
        {"name": "shatter", "desc": "Deal 10–18 × Vulnerable stacks (capped at ×4).  [2 MP]"},
        {"name": "silence", "desc": "Stun target 1 turn; apply Weak 2.  [1 MP]"},
        {"name": "torment", "desc": "Extend all debuffs on all enemies by 1 turn.  [2 MP]"},
    ],
    20: [
        {"name": "obliterate", "desc": "Deal 50–70 damage.  [3 MP]"},
        {"name": "rift",       "desc": "Restore 3 MP; apply Vulnerable 1 to yourself and all enemies.  [1 MP]"},
        {"name": "apocalypse", "desc": "Deal (total enemy status stacks) × 5 damage (cap 40).  [3 MP]"},
    ],
}

CLASS_COMMANDS = {
    "soldier": SOLDIER_COMMANDS,
    "rogue":   ROGUE_COMMANDS,
    "mage":    MAGE_COMMANDS,
}

# ─────────────────────────────────────────────────────────────────────────────
#  Class metadata
# ─────────────────────────────────────────────────────────────────────────────

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
        "    Starter relic: Sleightmaker's Glove — actions costing ≤4 AP cost 1 fewer AP."
    ),
    "mage": (
        "🔮  MAGE\n"
        "    An arcane wielder who manages Mana as carefully as AP.\n"
        "    Every spell costs MP — spend it wisely.\n"
        "    Starter relic: Aether-Spun Tapestry — Max MP +2; restore 1 MP each turn."
    ),
}

MAGE_MP_COSTS = {
    "spark": 1, "bolt": 1, "ward": 1, "curse": 0,
    "blaze": 2, "charm": 2, "drain": 1,
    "shatter": 2, "silence": 1, "torment": 2,
    "obliterate": 3, "rift": 1, "apocalypse": 3,
}