from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from game.entities import Entity


# ── Trigger / Target enums ────────────────────────────────────────────────────

class EffectTrigger(Enum):
    ON_TURN_START = auto()       # fires at start of the affected entity's turn
    ON_TURN_END = auto()         # fires at end of the affected entity's turn
    ON_DAMAGE_RECEIVED = auto()  # fires whenever the entity takes damage
    ON_DAMAGE_DEALT = auto()     # fires whenever the entity deals damage
    ON_ACTION = auto()           # fires whenever the entity takes any action
    ON_APPLY = auto()            # fires only when the effect is first applied
    PASSIVE = auto()             # permanent stat modification, no per-turn tick


class EffectCategory(Enum):
    BUFF = auto()       # positive effect (block, strength, regen)
    DEBUFF = auto()     # negative effect (poison, weak, vulnerable)
    NEUTRAL = auto()    # informational or conditional


# ── Core status effect ────────────────────────────────────────────────────────

@dataclass
class StatusEffect:
    """A stackable or non-stackable effect applied to an Entity.

    Subclass this to implement concrete effects (Poison, Block, Shocked, etc.).
    All mutating logic goes in the hook methods below.

    Attributes:
        id            – unique string id used by the registry (e.g. 'poison')
        name          – display name shown to the player
        description   – short flavour / rules text
        trigger       – when the effect's tick logic fires
        category      – buff / debuff / neutral for UI colouring
        duration      – turns remaining; -1 means permanent until removed
        stacks        – current stack count
        max_stacks    – cap on stacks; 1 = non-stackable
        source_ability – which ability or item applied this (for log messages)
    """

    id: str
    name: str
    description: str
    trigger: EffectTrigger
    category: EffectCategory
    duration: int
    stacks: int = 1
    max_stacks: int = 1
    source_ability: str | None = None

    # ── Hooks (override in subclasses) ────────────────────────────────────

    def on_apply(self, target: "Entity") -> str:
        """Called once when first applied. Return narration string."""
        ...

    def on_tick(self, target: "Entity") -> str:
        """Called each trigger event. Mutate target stats here. Return narration."""
        ...

    def on_expire(self, target: "Entity") -> str:
        """Called when duration reaches 0. Reverse any permanent changes. Return narration."""
        ...

    def on_stack_added(self, target: "Entity", added: int) -> str:
        """Called when stacks are added to an existing application. Return narration."""
        ...

    # ── Stack helpers ─────────────────────────────────────────────────────

    def add_stacks(self, amount: int, target: "Entity") -> str:
        """Clamp stacks to max_stacks, call on_stack_added, return narration."""
        ...

    def is_expired(self) -> bool:
        """Return True if duration has reached 0 (ignores -1 permanent)."""
        ...

    def tick_duration(self) -> None:
        """Decrement duration by 1 (no-op if duration is -1)."""
        ...


# ── Effect registry ───────────────────────────────────────────────────────────

class EffectRegistry:
    """Central registry that maps effect IDs to their classes.

    Register all effect subclasses here at startup so the rest of the
    engine can instantiate effects by string ID (e.g. from JSON data).
    """

    def __init__(self) -> None:
        self._classes: dict[str, type[StatusEffect]] = {}

    def register(self, effect_class: type[StatusEffect]) -> None:
        """Register an effect class. Keyed by its `id` class attribute."""
        ...

    def create(self, effect_id: str, stacks: int = 1, duration: int = 1,
               source_ability: str | None = None) -> StatusEffect:
        """Instantiate a registered effect by ID. Raises KeyError if unknown."""
        ...

    def is_known(self, effect_id: str) -> bool:
        ...

    def all_ids(self) -> list[str]:
        ...


# ── Effect manager (per entity) ───────────────────────────────────────────────

class EffectManager:
    """Manages the live status effects on a single Entity.

    Attach one of these to every Entity instance.
    """

    def __init__(self) -> None:
        self._active: dict[str, StatusEffect] = {}  # effect_id -> instance

    def apply(self, effect: StatusEffect, target: "Entity") -> str:
        """Apply an effect. Stack if already present, otherwise add fresh. Return narration."""
        ...

    def remove(self, effect_id: str, target: "Entity") -> str:
        """Forcibly remove an effect by ID. Calls on_expire. Return narration."""
        ...

    def has(self, effect_id: str) -> bool:
        ...

    def get(self, effect_id: str) -> StatusEffect | None:
        ...

    def get_all(self) -> list[StatusEffect]:
        ...

    def get_by_category(self, category: EffectCategory) -> list[StatusEffect]:
        ...

    def tick_all(self, trigger: EffectTrigger, target: "Entity") -> list[str]:
        """Fire all effects matching trigger, decrement durations, remove expired.
        Returns list of narration strings."""
        ...

    def clear_all(self, target: "Entity") -> None:
        """Remove every effect without calling on_expire (e.g. combat end)."""
        ...

    def stat_bonus(self, stat_name: str) -> int:
        """Sum passive stat bonuses provided by all active PASSIVE effects."""
        ...

    def summary(self) -> str:
        """One-line summary of active effects for combat display."""
        ...