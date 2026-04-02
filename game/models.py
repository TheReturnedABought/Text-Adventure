from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass(slots=True)
class Ability:
    """Active or passive effect attached to equippable items or classes."""

    name: str
    description: str
    ap_cost: int = 0
    execute: Callable[["BattleContext"], str] | None = None


@dataclass(slots=True)
class EquippableItem:
    """Equipment-first progression object with optional combat abilities."""

    name: str
    slot: str
    description: str
    stat_modifiers: dict[str, int] = field(default_factory=dict)
    abilities: list[Ability] = field(default_factory=list)


@dataclass(slots=True)
class CharacterClass:
    """Role archetype. Extend this with class trees and unlock requirements."""

    name: str
    description: str
    base_stats: dict[str, int]
    starting_items: list[EquippableItem] = field(default_factory=list)


@dataclass(slots=True)
class ParsedCommand:
    """Normalized parser output used by the combat controller."""

    intent: str
    target: str | None = None
    item_name: str | None = None
    raw: str = ""


@dataclass(slots=True)
class BattleContext:
    """Context object passed to abilities for deterministic combat effects."""

    actor_name: str
    target_name: str | None
    actor_attack: int
    actor_defense: int
