# utils/dice.py
"""
Dice roller. All randomised combat numbers go through here.

Supported expressions: "2d6+6", "1d8+7", "d6", "3d4-1", "0"
roll(expr)     -> random result
min_roll(expr) -> lowest possible
max_roll(expr) -> highest possible
describe(expr) -> "8–18" string for display
"""
import random
import re

_DICE = re.compile(r'^(\d*)d(\d+)([+-]\d+)?$', re.IGNORECASE)


def roll(expr: str) -> int:
    expr = str(expr).strip()
    if expr == "0":
        return 0
    m = _DICE.match(expr)
    if not m:
        try:
            return max(1, int(expr))
        except ValueError:
            raise ValueError(f"Invalid dice expression: {expr!r}")
    n   = int(m.group(1)) if m.group(1) else 1
    d   = int(m.group(2))
    mod = int(m.group(3)) if m.group(3) else 0
    return max(1, sum(random.randint(1, d) for _ in range(n)) + mod)


def min_roll(expr: str) -> int:
    expr = str(expr).strip()
    if expr == "0":
        return 0
    m = _DICE.match(expr)
    if not m:
        return max(1, int(expr))
    n   = int(m.group(1)) if m.group(1) else 1
    mod = int(m.group(3)) if m.group(3) else 0
    return max(1, n + mod)


def max_roll(expr: str) -> int:
    expr = str(expr).strip()
    if expr == "0":
        return 0
    m = _DICE.match(expr)
    if not m:
        return max(1, int(expr))
    n   = int(m.group(1)) if m.group(1) else 1
    d   = int(m.group(2))
    mod = int(m.group(3)) if m.group(3) else 0
    return n * d + mod


def describe(expr: str) -> str:
    return f"{min_roll(expr)}–{max_roll(expr)}"


def add_dice(expr: str, extra_dice: int) -> str:
    """
    Return a dice expression with additional dice of the same size.
    Example: add_dice("1d4+2", 1) -> "2d4+2"
    """
    expr = str(expr).strip()
    m = _DICE.match(expr)
    if not m:
        return expr
    n = int(m.group(1)) if m.group(1) else 1
    d = int(m.group(2))
    mod = m.group(3) or ""
    n = max(1, n + max(0, int(extra_dice)))
    return f"{n}d{d}{mod}"
