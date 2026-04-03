"""Status effect system – buffs, debuffs, and timed effects."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from game.entities import Entity


class EffectTrigger(Enum):
    ON_TURN_START = auto()
    ON_TURN_END = auto()
    ON_DAMAGE_RECEIVED = auto()
    ON_DAMAGE_DEALT = auto()
    ON_ACTION = auto()
    ON_APPLY = auto()
    PASSIVE = auto()


class EffectCategory(Enum):
    BUFF = auto()
    DEBUFF = auto()
    NEUTRAL = auto()


@dataclass
class StatusEffect:
    """A temporary effect attached to an entity."""
    id: str
    name: str
    description: str
    trigger: EffectTrigger
    category: EffectCategory
    duration: int
    stacks: int = 1
    max_stacks: int = 1
    source_ability: str | None = None

    def on_apply(self, target: "Entity") -> str:
        return f"{target.name} gains {self.name}."

    def on_tick(self, target: "Entity") -> str:
        return ""

    def on_expire(self, target: "Entity") -> str:
        return f"{self.name} fades from {target.name}."

    def on_stack_added(self, target: "Entity", added: int) -> str:
        return f"{self.name} on {target.name} increases by {added}."

    def add_stacks(self, amount: int, target: "Entity") -> str:
        before = self.stacks
        self.stacks = min(self.max_stacks, self.stacks + max(0, amount))
        added = self.stacks - before
        return self.on_stack_added(target, added) if added > 0 else ""

    def is_expired(self) -> bool:
        return self.duration == 0

    def tick_duration(self) -> None:
        if self.duration > 0:
            self.duration -= 1


class EffectRegistry:
    """Factory for creating status effects by ID."""
    def __init__(self):
        self._classes: dict[str, type[StatusEffect]] = {}

    def register(self, effect_class: type[StatusEffect]) -> None:
        effect_id = getattr(effect_class, "id", None)
        if not effect_id:
            raise ValueError("Effect class must define class-level 'id'.")
        self._classes[str(effect_id)] = effect_class

    def create(self, effect_id: str, stacks: int = 1, duration: int = 1,
               source_ability: str | None = None) -> StatusEffect:
        if effect_id not in self._classes:
            raise KeyError(f"Unknown effect: {effect_id}")
        return self._classes[effect_id](stacks=stacks, duration=duration, source_ability=source_ability)

    def is_known(self, effect_id: str) -> bool:
        return effect_id in self._classes

    def all_ids(self) -> list[str]:
        return sorted(self._classes.keys())


class EffectManager:
    """Manages active effects on an entity."""
    def __init__(self):
        self._active: dict[str, StatusEffect] = {}

    def apply(self, effect: StatusEffect, target: "Entity") -> str:
        existing = self._active.get(effect.id)
        if existing:
            line = existing.add_stacks(effect.stacks, target)
            if effect.duration > existing.duration:
                existing.duration = effect.duration
            return line or f"{target.name} is still affected by {existing.name}."
        self._active[effect.id] = effect
        return effect.on_apply(target)

    def remove(self, effect_id: str, target: "Entity") -> str:
        effect = self._active.pop(effect_id, None)
        return effect.on_expire(target) if effect else ""

    def has(self, effect_id: str) -> bool:
        return effect_id in self._active

    def get(self, effect_id: str) -> StatusEffect | None:
        return self._active.get(effect_id)

    def get_all(self) -> list[StatusEffect]:
        return list(self._active.values())

    def get_by_category(self, category: EffectCategory) -> list[StatusEffect]:
        return [e for e in self._active.values() if e.category == category]

    def tick_all(self, trigger: EffectTrigger, target: "Entity") -> list[str]:
        lines = []
        to_remove = []
        for effect in list(self._active.values()):
            if effect.trigger == trigger:
                text = effect.on_tick(target)
                if text:
                    lines.append(text)
            if trigger in {EffectTrigger.ON_TURN_START, EffectTrigger.ON_TURN_END}:
                effect.tick_duration()
            if effect.is_expired():
                expire = effect.on_expire(target)
                if expire:
                    lines.append(expire)
                to_remove.append(effect.id)
        for eid in to_remove:
            self._active.pop(eid, None)
        return lines

    def clear_all(self, target: "Entity") -> None:
        self._active.clear()

    def stat_bonus(self, stat_name: str) -> int:
        total = 0
        for effect in self._active.values():
            if effect.trigger != EffectTrigger.PASSIVE:
                continue
            bonuses = getattr(effect, "stat_bonuses", {})
            total += int(bonuses.get(stat_name, 0))
        return total

    def summary(self) -> str:
        if not self._active:
            return "none"
        parts = [f"{e.name} x{e.stacks}({e.duration})" for e in self._active.values()]
        return ", ".join(parts)