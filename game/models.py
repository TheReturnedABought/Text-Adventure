"""Data models for abilities, items, classes, enemy intents, loot, and parsed commands."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from game.dice import DiceExpression
    from game.effects import StatusEffect


@dataclass
class Ability:
    id: str
    name: str
    description: str
    ap_cost: int | None = None
    dice_expression: str | None = None
    effect_on_hit: str | None = None
    effect_duration: int = 1
    effect_stacks: int = 1
    tags: list[str] = field(default_factory=list)
    execute: Callable[["BattleContext"], str] | None = None


@dataclass
class EquippableItem:
    id: str
    name: str
    slot: str
    description: str
    material: str = "metal"
    rarity: str = "common"
    tier: int = 1
    stat_modifiers: dict[str, int] = field(default_factory=dict)
    ability_cost_reductions: dict[str, int] = field(default_factory=dict)
    abilities: list[Ability] = field(default_factory=list)
    equip_requirements: dict = field(default_factory=dict)
    upgrade_path: str | None = None
    readable_text: str | None = None

@dataclass
class PassiveTrait:
    id: str
    name: str
    description: str
    stat_bonuses: dict[str, int] = field(default_factory=dict)


@dataclass
class CharacterClass:
    id: str
    name: str
    description: str
    base_stats: dict[str, int] = field(default_factory=dict)
    starting_items: list[EquippableItem] = field(default_factory=list)
    passive_traits: list[PassiveTrait] = field(default_factory=list)
    level_unlocks: dict[int, list[str]] = field(default_factory=dict)
    choice_unlocks: dict[int, list[list[str]]] = field(default_factory=dict)


class IntentType(Enum):
    ATTACK = auto()
    BLOCK = auto()
    BUFF = auto()
    DEBUFF = auto()
    FLEE = auto()
    WAIT = auto()


@dataclass
class EnemyIntent:
    id: str
    intent_type: IntentType
    description: str
    dice_expression: str | None = None
    ap_cost: int = 6
    weight: int = 1
    condition: str | None = None
    effect_on_hit: str | None = None
    effect_duration: int = 1
    tags: list[str] = field(default_factory=list)


@dataclass
class LootEntry:
    item_id: str
    chance: float
    count_expression: str = "1"


class ArticleType(Enum):
    SPECIFIC = auto()
    GENERIC = auto()
    NONE = auto()


@dataclass
class ParsedCommand:
    intent: str | None
    raw: str = ""
    target_name: str | None = None
    target_index: int | None = None
    article: ArticleType = ArticleType.NONE
    modifiers: list[str] = field(default_factory=list)
    item_name: str | None = None
    ap_cost: int = 0
    mp_cost: int = 0
    valid: bool = True
    error: str | None = None


@dataclass
class BattleContext:
    actor_name: str
    target_name: str | None
    actor_attack: int
    actor_defense: int
    actor_block: int = 0
    actor_ap_remaining: int = 0
    target_hp: int = 0
    target_max_hp: int = 0
    target_block: int = 0
    active_effects_on_actor: list[str] = field(default_factory=list)
    active_effects_on_target: list[str] = field(default_factory=list)
    roll_result: int | None = None
    is_critical: bool = False