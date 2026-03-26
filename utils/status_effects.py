# utils/status_effects.py
from utils.helpers import print_slow


STATUS_ICONS = {
    "poison":     "☠",
    "stun":       "⚡",
    "rage":       "🔥",
    "vulnerable": "💢",
    "weak":       "🌀",
    "block":      "🛡",
    "volatile":   "💥",
    "echo":       "🔊",
    "disorient":  "🌪",
    "bleed":      "🩸",   # fixed dmg/turn, no decay
    "regen":      "🌿",   # heal stacks/turn, decays 1/turn
    "burden":     "⚖️",   # +1 AP/stack per command (player); -2 dmg/stack (enemy)
    # ── New powers / debuffs ──────────────────────────────────────────────────
    "fortify":    "🏰",   # POWER: gain stacks Block at start of every turn (permanent)
    "cursed":     "🛑",   # DEBUFF: healing reduced by stacks×10% (enemy-applied)
    "speed":      "💨",   # BUFF: next stacks commands cost 1 fewer AP, consumed per action
    "slow":       "🕸",   # DEBUFF: next stacks commands cost 1 more AP, consumed per action
    "soul_tax":   "⚰",   # DEBUFF: at turn end take (stacks × AP_spent) damage
    "counter":    "🔄",   # BUFF: when hit deal stacks damage back; persists, no decay
}


# ── Applying ─────────────────────────────────────────────────────────────────

def _apply(entity, status, stacks):
    entity.statuses[status] = entity.statuses.get(status, 0) + stacks
    icon = STATUS_ICONS.get(status, "◈")
    name = getattr(entity, "name", "You")
    total = entity.statuses[status]
    print_slow(f"  {icon} {name} gains {stacks}x {status.upper()} (total: {total})")


def apply_poison(entity, stacks=1):     _apply(entity, "poison", stacks)
def apply_stun(entity, stacks=1):       _apply(entity, "stun", stacks)
def apply_rage(entity, stacks=1):       _apply(entity, "rage", stacks)
def apply_vulnerable(entity, stacks=1): _apply(entity, "vulnerable", stacks)
def apply_weak(entity, stacks=1):       _apply(entity, "weak", stacks)
def apply_bleed(entity, stacks=1):      _apply(entity, "bleed", stacks)
def apply_regen(entity, stacks=1):      _apply(entity, "regen", stacks)
def apply_burden(entity, stacks=1):     _apply(entity, "burden", stacks)
def apply_fortify(entity, stacks=1):    _apply(entity, "fortify", stacks)
def apply_cursed(entity, stacks=1):     _apply(entity, "cursed", stacks)
def apply_speed(entity, stacks=1):      _apply(entity, "speed", stacks)
def apply_slow(entity, stacks=1):       _apply(entity, "slow", stacks)
def apply_soul_tax(entity, stacks=1):   _apply(entity, "soul_tax", stacks)
def apply_counter(entity, stacks=1):    _apply(entity, "counter", stacks)

def apply_volatile(entity):
    """Max 1 stack. Caps at 1 regardless of how many times applied."""
    if entity.statuses.get("volatile", 0) == 0:
        _apply(entity, "volatile", 2)   # value = remaining turns

def apply_echo(entity, last_command):
    """Max 1 stack. Stores the command to echo as the value string."""
    entity.statuses["echo"] = last_command
    name = getattr(entity, "name", "You")
    print_slow(f"  🔊 {name} will echo '{last_command}' next turn!")

def apply_disorient(entity, stacks=1):
    """Max 1 stack total."""
    if entity.statuses.get("disorient", 0) == 0:
        _apply(entity, "disorient", min(stacks, 1))

def apply_block(entity, stacks):
    """Block absorbs incoming damage. Stacks within a turn, clears at turn start."""
    entity.statuses["block"] = entity.statuses.get("block", 0) + stacks
    icon = STATUS_ICONS["block"]
    name = getattr(entity, "name", "You")
    total = entity.statuses["block"]
    print_slow(f"  {icon} {name} gains {stacks} BLOCK (total: {total})")


# ── Queries ───────────────────────────────────────────────────────────────────

def is_stunned(entity):    return entity.statuses.get("stun", 0) > 0
def is_raging(entity):     return entity.statuses.get("rage", 0) > 0
def get_block(entity):     return entity.statuses.get("block", 0)
def is_volatile(entity):   return entity.statuses.get("volatile", 0) > 0
def is_disoriented(entity):return entity.statuses.get("disorient", 0) > 0
def get_echo(entity):      return entity.statuses.get("echo", None)
def get_burden(entity):    return entity.statuses.get("burden", 0)
def get_regen(entity):     return entity.statuses.get("regen", 0)
def get_bleed(entity):     return entity.statuses.get("bleed", 0)
def get_fortify(entity):   return entity.statuses.get("fortify", 0)
def get_cursed(entity):    return entity.statuses.get("cursed", 0)
def get_speed(entity):     return entity.statuses.get("speed", 0)
def get_slow(entity):      return entity.statuses.get("slow", 0)
def get_soul_tax(entity):  return entity.statuses.get("soul_tax", 0)
def get_counter(entity):   return entity.statuses.get("counter", 0)


# ── Consume (read + remove for one-shot effects) ──────────────────────────────

def consume_vulnerable(entity):
    if entity.statuses.get("vulnerable", 0) > 0:
        entity.statuses["vulnerable"] -= 1
        if entity.statuses["vulnerable"] <= 0:
            del entity.statuses["vulnerable"]
        return 1.5
    return 1.0

def consume_weak(entity):
    if entity.statuses.get("weak", 0) > 0:
        entity.statuses["weak"] -= 1
        if entity.statuses["weak"] <= 0:
            del entity.statuses["weak"]
        return 0.75
    return 1.0

def consume_rage(entity):
    if is_raging(entity):
        del entity.statuses["rage"]
        return 2.0
    return 1.0

def consume_block(entity, incoming_dmg, ignore_first_block=False):
    """
    Absorb as much incoming damage as possible with block stacks.
    Returns (damage_after_block, block_absorbed).
    Block is fully cleared after use (StS style).
    """
    block = entity.statuses.get("block", 0)
    if block <= 0 or ignore_first_block:
        return incoming_dmg, 0
    absorbed    = min(block, incoming_dmg)
    remaining   = incoming_dmg - absorbed
    new_block   = block - absorbed
    if new_block <= 0:
        entity.statuses.pop("block", None)
    else:
        entity.statuses["block"] = new_block
    return remaining, absorbed


# ── End-of-turn tick ──────────────────────────────────────────────────────────

def tick_statuses(entity):
    """Tick DOTs and durations at end of entity's turn. Block clears at START of turn (handled in regen_ap)."""
    import random
    name = getattr(entity, "name", "You")

    # Poison — deals stacks damage, then stacks decay by 1 (StS style)
    stacks = entity.statuses.get("poison", 0)
    if stacks > 0:
        entity.health = max(0, entity.health - stacks)
        print_slow(f"  ☠  {name} takes {stacks} poison damage! (HP: {entity.health})")
        entity.statuses["poison"] -= 1
        if entity.statuses["poison"] <= 0:
            del entity.statuses["poison"]

    # Stun — decrement duration
    if entity.statuses.get("stun", 0) > 0:
        entity.statuses["stun"] -= 1
        if entity.statuses["stun"] <= 0:
            del entity.statuses["stun"]
            print_slow(f"  ⚡ {name} is no longer stunned.")

    # Volatile — decrement turn counter; self-damage is handled in combat.py on each action
    if entity.statuses.get("volatile", 0) > 0:
        entity.statuses["volatile"] -= 1
        if entity.statuses["volatile"] <= 0:
            del entity.statuses["volatile"]
            print_slow(f"  💥 {name}'s Volatile fades.")

    # Echo — clears after 1 turn (combat.py fires the echo before tick)
    if "echo" in entity.statuses:
        del entity.statuses["echo"]

    # Disorient — decrement duration
    if entity.statuses.get("disorient", 0) > 0:
        entity.statuses["disorient"] -= 1
        if entity.statuses["disorient"] <= 0:
            del entity.statuses["disorient"]
            print_slow(f"  🌪 {name} is no longer disoriented.")

    # Bleed — fixed damage, does NOT decay; must be cleansed
    bleed = entity.statuses.get("bleed", 0)
    if bleed > 0:
        entity.health = max(0, entity.health - bleed)
        print_slow(f"  🩸 {name} bleeds for {bleed} damage! (HP: {entity.health})")

    # Regen — heal stacks HP, then decay by 1
    regen = entity.statuses.get("regen", 0)
    if regen > 0:
        entity.health = min(getattr(entity, "max_health", entity.health + regen),
                            entity.health + regen)
        print_slow(f"  🌿 {name} regenerates {regen} HP! (HP: {entity.health})")
        entity.statuses["regen"] -= 1
        if entity.statuses["regen"] <= 0:
            del entity.statuses["regen"]

    # Burden — decrement duration
    if entity.statuses.get("burden", 0) > 0:
        entity.statuses["burden"] -= 1
        if entity.statuses["burden"] <= 0:
            del entity.statuses["burden"]
            print_slow(f"  ⚖️ {name} is no longer burdened.")

    # Speed — countdown only (consumed per-action in combat.py AP block)
    # Nothing to tick here; stacks are consumed by the AP cost logic.

    # Slow — countdown only (consumed per-action in combat.py AP block)
    # Nothing to tick here; stacks are consumed by the AP cost logic.

    # Soul Tax — damage is applied by combat.py at turn end using ap_spent_this_turn.
    # No tick here; the status itself is permanent until combat ends.

    # Fortify — POWER (permanent); Block is applied at turn start in _regen_ap, not here.

    # Cursed — DEBUFF (permanent); reduces healing, no tick needed.

def clear_block(entity):
    """Clear block at the start of a new turn (StS: block doesn't carry over)."""
    if entity.statuses.pop("block", None):
        pass  # silently clear — no message needed


def modified_heal(entity, base_amount):
    """
    Apply Cursed reduction to a heal amount.
    Returns the final healed value (already clamped ≥ 0).
    """
    cursed = entity.statuses.get("cursed", 0)
    if cursed:
        reduction = min(cursed * 0.10, 1.0)   # cap at 100% reduction
        final = int(base_amount * (1.0 - reduction))
        if final < base_amount:
            print_slow(f"  🛑 Cursed — heal reduced by {int(reduction*100)}%! ({base_amount} → {final})")
        return max(0, final)
    return base_amount


# ── Display ───────────────────────────────────────────────────────────────────

def format_statuses(entity):
    if not entity.statuses:
        return ""
    parts = []
    for k, v in entity.statuses.items():
        icon = STATUS_ICONS.get(k, "◈")
        parts.append(f"{icon}{v}")
    return " ".join(parts)