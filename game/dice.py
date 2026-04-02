from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DiceExpression:
    """Represents a parsed dice expression like '3d6+2' or '1d4-1'.

    Attributes:
        count    – number of dice to roll (the 3 in 3d6)
        sides    – faces per die            (the 6 in 3d6)
        modifier – flat bonus/penalty added after rolling
        raw      – original string for display purposes
    """

    count: int
    sides: int
    modifier: int = 0
    raw: str = ""

    # ── Construction ──────────────────────────────────────────────────────

    @classmethod
    def parse(cls, expression: str) -> "DiceExpression":
        """Parse a string like '3d6+2', '1d4', or '2d8-1' into a DiceExpression.

        Raises ValueError on malformed input.
        """
        ...

    @classmethod
    def flat(cls, value: int) -> "DiceExpression":
        """Create a fixed-value expression (0 dice, modifier = value)."""
        ...

    # ── Rolling ───────────────────────────────────────────────────────────

    def roll(self) -> int:
        """Roll all dice, sum results, add modifier. Return total."""
        ...

    def roll_with_breakdown(self) -> tuple[int, list[int], int]:
        """Roll and return (total, [individual_die_results], modifier)."""
        ...

    def min_value(self) -> int:
        """Theoretical minimum roll (all 1s + modifier)."""
        ...

    def max_value(self) -> int:
        """Theoretical maximum roll (all max + modifier)."""
        ...

    def average(self) -> float:
        """Statistical average of this expression."""
        ...

    # ── Modifiers ─────────────────────────────────────────────────────────

    def multiply_count(self, factor: float) -> "DiceExpression":
        """Return a new expression with dice count scaled by factor (e.g. heavy = x2).

        Rounds count up to nearest int.
        """
        ...

    def add_modifier(self, bonus: int) -> "DiceExpression":
        """Return a new expression with a flat bonus added to the modifier."""
        ...

    def with_extra_die(self, count: int = 1) -> "DiceExpression":
        """Return a new expression with additional dice of the same size."""
        ...

    # ── Display ───────────────────────────────────────────────────────────

    def __str__(self) -> str:
        """Canonical string form, e.g. '3d6+2'."""
        ...