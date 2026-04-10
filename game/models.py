# game/models.py
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, List, Dict, Optional

@dataclass
class Ability:
    id: str
    name: str
    description: str
    ap_cost: Optional[int] = None
    dice_expression: Optional[str] = None
    effect_on_hit: Optional[str] = None
    effect_duration: int = 1
    effect_stacks: int = 1
    tags: List[str] = field(default_factory=list)
    payload: Dict = field(default_factory=dict)
    execute: Optional[Callable[["BattleContext"], str]] = None

@dataclass
class EquippableItem:
    id: str
    name: str
    slot: str
    description: str
    material: str = "metal"
    rarity: str = "common"
    tier: int = 1
    stat_modifiers: Dict[str, int] = field(default_factory=dict)
    letter_cost_reductions: Dict[str, int] = field(default_factory=dict)
    ability_cost_reductions: Dict[str, int] = field(default_factory=dict)
    abilities: List[Ability] = field(default_factory=list)
    equip_requirements: Dict = field(default_factory=dict)
    upgrade_path: Optional[str] = None
    readable_text: Optional[str] = None
    item_flags: List[str] = field(default_factory=list)
    on_hit_effects: Dict = field(default_factory=dict)
    passive_effects: Dict = field(default_factory=dict)
    value: int = 0
    damage_type: Optional[str] = None   # "slashing", "piercing", "bludgeoning"

    def __post_init__(self):
        if self.value == 0:
            self.value = self.tier * 10

@dataclass
class PassiveTrait:
    id: str
    name: str
    description: str
    stat_bonuses: Dict[str, int] = field(default_factory=dict)

@dataclass
class CharacterClass:
    id: str
    name: str
    description: str
    base_stats: Dict[str, int] = field(default_factory=dict)
    starting_items: List[EquippableItem] = field(default_factory=list)
    passive_traits: List[PassiveTrait] = field(default_factory=list)
    level_unlocks: Dict[int, List[str]] = field(default_factory=dict)
    choice_unlocks: Dict[int, List[List[str]]] = field(default_factory=dict)

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
    dice_expression: Optional[str] = None
    ap_cost: int = 6
    weight: int = 1
    condition: Optional[str] = None
    effect_on_hit: Optional[str] = None
    effect_duration: int = 1
    tags: List[str] = field(default_factory=list)

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
    intent: Optional[str]
    raw: str = ""
    target_name: Optional[str] = None
    target_index: Optional[int] = None
    article: ArticleType = ArticleType.NONE
    modifiers: List[str] = field(default_factory=list)
    item_name: Optional[str] = None
    ap_cost: int = 0
    mp_cost: int = 0
    valid: bool = True
    error: Optional[str] = None

@dataclass
class BattleContext:
    actor_name: str
    target_name: Optional[str]
    actor_attack: int
    actor_defense: int
    actor_block: int = 0
    actor_ap_remaining: int = 0
    target_hp: int = 0
    target_max_hp: int = 0
    target_block: int = 0
    active_effects_on_actor: List[str] = field(default_factory=list)
    active_effects_on_target: List[str] = field(default_factory=list)
    roll_result: Optional[int] = None
    is_critical: bool = False