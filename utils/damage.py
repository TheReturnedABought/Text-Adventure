"""Damage typing utilities: resistances, weaknesses, and combat feedback."""

from utils.helpers import print_slow
from utils.status_effects import consume_block


EFFECTIVE_TEXT = {
    "very": "It's very effective!",
    "not": "It's not very effective.",
    "normal": "",
}


CLASS_BASE_ATTACK_TYPE = {
    "soldier": "piercing",
    "rogue": "slashing",
    "mage": "force",
    "wizard": "force",  # alias for design docs / future rename
}


COMMAND_DAMAGE_TYPES = {
    # soldier
    "cut": "slashing",
    "cleave": "slashing",
    "downcut": "bludgeoning",
    "execute": "piercing",
    "juggernaut": "bludgeoning",
    "quickshot": "piercing",
    "assault": "slashing",
    "assassinate": "piercing",
    "shadowstrike": "slashing",
    # mage / spell examples
    "spark": "lightning",
    "bolt": "lightning",
    "wave": "lightning",
    "storm": "lightning",
    "tempest": "lightning",
    "blaze": "fire",
    "torment": "fire",
    "drain": "force",
    "obliterate": "force",
    "shatter": "force",
    "apocalypse": "force",
}


def command_damage_type(command: str, fallback: str = "physical") -> str:
    return COMMAND_DAMAGE_TYPES.get((command or "").lower(), fallback)


def class_base_attack_type(char_class: str) -> str:
    return CLASS_BASE_ATTACK_TYPE.get((char_class or "").lower(), "physical")


def damage_multiplier(target, damage_type: str):
    dtype = (damage_type or "physical").lower()
    weak = {x.lower() for x in getattr(target, "weaknesses", set())}
    resist = {x.lower() for x in getattr(target, "resistances", set())}

    if dtype in weak:
        return 1.5, "very"
    if dtype in resist:
        return 0.5, "not"
    return 1.0, "normal"


def apply_typed_damage(attacker, target, dmg, damage_type="physical", label="Hit", ctx=None):
    """Apply typed player damage to enemy with block and effectiveness hints."""
    multi, tag = damage_multiplier(target, damage_type)
    scaled = int(max(1, round(dmg * multi)))

    actual, absorbed = consume_block(target, scaled)
    target.take_damage(actual)

    msg = f"  {label} {target.name}: you dealt {actual} {damage_type} damage"
    if absorbed:
        msg += f" ({absorbed} blocked)"
    msg += "."
    print_slow(msg)

    hint = EFFECTIVE_TEXT.get(tag, "")
    if hint:
        print_slow(f"  {hint}")

    session = (ctx or {}).get("combat_session") if ctx else None
    if hasattr(target, "on_damaged"):
        target.on_damaged(
            attacker=attacker,
            damage=actual,
            damage_type=damage_type,
            combat_session=session,
            ctx=ctx or {},
        )

    return actual, absorbed, tag
