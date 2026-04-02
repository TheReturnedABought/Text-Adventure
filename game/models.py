from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from game.dice import DiceExpression
    from game.effects import StatusEffect


# ══════════════════════════════════════════════════════════════════════════════
# Ability
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class Ability:
    """Active or passive effect attached to an item or class.

    Attributes:
        id              – machine-readable key, matches ability JSON id
        name            – player-facing name (e.g. 'Ember Slash')
        description     – short rules text shown in inventory / help
        ap_cost         – fixed AP override; None = use letter count of the typed command
        dice_expression – string like '2d6+1'; None = non-damaging utility ability
        effect_on_hit   – status effect ID to apply on a successful hit (or None)
        effect_duration – turns the applied status effect lasts
        effect_stacks   – how many stacks to apply
        tags            – ['lightning', 'aoe', 'single-target', …]
        execute         – runtime callback wired by AbilityRegistry (None until wired)
    """

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


# ══════════════════════════════════════════════════════════════════════════════
# EquippableItem
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class EquippableItem:
    """Equipment-first progression object.

    Attributes:
        id                   – matches the item JSON id
        name                 – display name
        slot                 – 'weapon', 'offhand', 'armor', 'trinket', …
        description          – flavour text
        material             – 'metal', 'wood', 'leather', … (world interaction)
        rarity               – 'common', 'uncommon', 'rare', 'legendary'
        tier                 – numeric tier for scaling (1 = starter)
        stat_modifiers       – {stat_name: flat_bonus}
        ability_cost_reductions – {command_name: ap_reduction} (e.g. block: 1)
        abilities            – active/passive abilities granted while equipped
        equip_requirements   – {'min_level': int, 'classes': [str]}
        upgrade_path         – item_id of the next tier upgrade (or None)
    """

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


# ══════════════════════════════════════════════════════════════════════════════
# CharacterClass
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class PassiveTrait:
    """A permanent passive bonus provided by a class (or high-tier item)."""
    id: str
    name: str
    description: str
    stat_bonuses: dict[str, int] = field(default_factory=dict)


@dataclass
class CharacterClass:
    """Role archetype. All growth is driven by level_unlocks and items.

    Attributes:
        id              – machine key (e.g. 'fighter')
        name            – display name
        description     – flavour text
        base_stats      – {'hp', 'attack', 'defense', 'ap'}
        starting_items  – item IDs resolved to EquippableItem by loader
        passive_traits  – always-on bonuses active while playing this class
        level_unlocks   – {level_int: [command_names]}
        choice_unlocks  – {level_int: [[option_a, option_b], …]}  – player picks one per group
    """

    id: str
    name: str
    description: str
    base_stats: dict[str, int] = field(default_factory=dict)
    starting_items: list[EquippableItem] = field(default_factory=list)
    passive_traits: list[PassiveTrait] = field(default_factory=list)
    level_unlocks: dict[int, list[str]] = field(default_factory=dict)
    choice_unlocks: dict[int, list[list[str]]] = field(default_factory=dict)


# ══════════════════════════════════════════════════════════════════════════════
# Enemy intents
# ══════════════════════════════════════════════════════════════════════════════

class IntentType(Enum):
    ATTACK = auto()
    BLOCK = auto()
    BUFF = auto()
    DEBUFF = auto()
    FLEE = auto()
    WAIT = auto()


@dataclass
class EnemyIntent:
    """A single action an enemy can choose on its turn.

    Attributes:
        id              – machine key matching the JSON id
        intent_type     – what category of action this is (shown as icon/colour)
        description     – narration string ('scratches with its knife')
        dice_expression – damage/block dice; None = no dice (e.g. buff/wait)
        ap_cost         – how much of the enemy's AP pool this uses
        weight          – relative probability weight when AI is choosing
        condition       – optional rule string evaluated at choice time
                          ('hp_below_half', 'player_has_buff:shield', …)
        effect_on_hit   – status effect ID applied to target on success
        effect_duration – turns the effect lasts
    """

    id: str
    intent_type: IntentType
    description: str
    dice_expression: str | None = None
    ap_cost: int = 6
    weight: int = 1
    condition: str | None = None
    effect_on_hit: str | None = None
    effect_duration: int = 1


# ══════════════════════════════════════════════════════════════════════════════
# Loot
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class LootEntry:
    """One row in an enemy or room loot table."""
    item_id: str
    chance: float          # 0.0 – 1.0
    count_expression: str = "1"   # dice expression or plain int for quantity


# ══════════════════════════════════════════════════════════════════════════════
# Parsed command
# ══════════════════════════════════════════════════════════════════════════════

class ArticleType(Enum):
    SPECIFIC = auto()    # 'the goblin' – player wants a specific target
    GENERIC = auto()     # 'a goblin'   – player doesn't care → random + bonus damage
    NONE = auto()        # no article used


@dataclass
class ParsedCommand:
    """Fully normalised output of CommandParser.parse().

    Attributes:
        intent          – canonical command name (e.g. 'attack', 'block', 'smash')
        raw             – original typed string (used for AP cost calculation)
        target_name     – name fragment of the intended target (or None)
        target_index    – 1-based index if player typed a number to disambiguate
        article         – SPECIFIC / GENERIC / NONE
        modifiers       – ordered list of modifier names found (e.g. ['heavy'])
        item_name       – item or ability name for equip/ability commands
        is_world_action – True if intent is valid in world context but not combat
    """

    intent: str
    raw: str = ""
    target_name: str | None = None
    target_index: int | None = None
    article: ArticleType = ArticleType.NONE
    modifiers: list[str] = field(default_factory=list)
    item_name: str | None = None
    is_world_action: bool = False


# ══════════════════════════════════════════════════════════════════════════════
# Battle context (passed to ability execute callbacks)
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class BattleContext:
    """Snapshot of combat state passed into ability execute callbacks.

    Do NOT store references that change between turns – copy values.
    """

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
    roll_result: int | None = None     # populated after dice are rolled
    is_critical: bool = False