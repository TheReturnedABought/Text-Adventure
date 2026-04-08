# game/dice.py
import math
import random
import re
from dataclasses import dataclass

_DICE_RE = re.compile(r"^\s*(\d+)d(\d+)([+-]\d+)?\s*$", re.I)

@dataclass
class DiceExpression:
    count: int
    sides: int
    modifier: int = 0
    raw: str = ""

    @classmethod
    def parse(cls, expression: str) -> "DiceExpression":
        text = str(expression or "").strip().lower()
        if text.isdigit() or (text.startswith("-") and text[1:].isdigit()):
            return cls.flat(int(text))
        m = _DICE_RE.match(text)
        if not m:
            raise ValueError(f"Malformed dice expression: {expression!r}")
        count, sides, mod = m.groups()
        return cls(count=int(count), sides=int(sides), modifier=int(mod or 0), raw=text)

    @classmethod
    def flat(cls, value: int) -> "DiceExpression":
        return cls(count=0, sides=1, modifier=value, raw=str(value))

    def roll(self) -> int:
        total, _, _ = self.roll_with_breakdown()
        return total

    def roll_with_breakdown(self):
        rolls = [random.randint(1, self.sides) for _ in range(max(0, self.count))]
        total = sum(rolls) + self.modifier
        return total, rolls, self.modifier

    def multiply_count(self, factor: float) -> "DiceExpression":
        new_count = max(0, int(math.ceil(self.count * float(factor))))
        return DiceExpression(new_count, self.sides, self.modifier, self.raw)

    def add_modifier(self, bonus: int) -> "DiceExpression":
        return DiceExpression(self.count, self.sides, self.modifier + int(bonus), self.raw)

    def __str__(self) -> str:
        if self.count <= 0: return str(self.modifier)
        if self.modifier == 0: return f"{self.count}d{self.sides}"
        sign = "+" if self.modifier > 0 else ""
        return f"{self.count}d{self.sides}{sign}{self.modifier}"