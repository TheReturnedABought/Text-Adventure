from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from game.effects import EffectManager
from game.models import CharacterClass, EquippableItem, EnemyIntent, LootEntry

if TYPE_CHECKING:
    from game.effects import StatusEffect


# ══════════════════════════════════════════════════════════════════════════════
# Base entity
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class Entity:
    """Shared base for Player and Enemy.

    Attributes:
        name        – display name
        max_hp      – maximum hit points
        attack      – base attack stat (before item bonuses)
        defense     – flat damage reduction
        current_hp  – current hit points (initialised to max_hp if None)
        block       – temporary block that absorbs damage before HP (resets each turn)
        material    – 'flesh', 'metal', 'stone', 'wood' – affects world interactions
        effects     – live status effect manager for this entity
    """

    name: str
    max_hp: int
    attack: int
    defense: int
    current_hp: int | None = None
    block: int = 0
    material: str = "flesh"

    def __post_init__(self) -> None:
        if self.current_hp is None:
            self.current_hp = self.max_hp
        self.effects: EffectManager = EffectManager()

    # ── Properties ────────────────────────────────────────────────────────

    @property
    def is_alive(self) -> bool:
        ...

    @property
    def hp_fraction(self) -> float:
        """Current HP as a fraction of max (0.0 – 1.0). Used by AI conditions."""
        ...

    # ── Damage / healing ──────────────────────────────────────────────────

    def receive_damage(self, amount: int) -> int:
        """Apply damage: drain block first, then apply defense reduction, then HP.

        Returns the final HP damage dealt (after block and defense).
        """
        ...

    def receive_block_damage(self, amount: int) -> tuple[int, int]:
        """Separate block-drain from HP damage. Returns (block_drained, hp_damage)."""
        ...

    def heal(self, amount: int) -> int:
        """Restore HP up to max_hp. Returns actual HP restored."""
        ...

    def add_block(self, amount: int) -> None:
        """Add temporary block (STS-style: stacks, cleared at turn start)."""
        ...

    def clear_block(self) -> None:
        """Reset block to 0 at the start of this entity's turn."""
        ...

    # ── Effects ───────────────────────────────────────────────────────────

    def apply_effect(self, effect: "StatusEffect") -> str:
        """Delegate to EffectManager.apply(). Returns narration."""
        ...

    def tick_effects(self, trigger) -> list[str]:
        """Delegate to EffectManager.tick_all(). Returns narration list."""
        ...

    # ── Status display ────────────────────────────────────────────────────

    def status_line(self) -> str:
        """One-line combat summary: name, HP bar, block, active effects."""
        ...

    def hp_bar(self, width: int = 20) -> str:
        """ASCII HP bar of given character width."""
        ...


# ══════════════════════════════════════════════════════════════════════════════
# Player
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class Player(Entity):
    """The player character.

    Attributes:
        char_class        – active CharacterClass
        level             – current level (drives unlock checks)
        xp                – experience points accumulated
        xp_to_next_level  – threshold for levelling up
        total_ap          – max AP per turn (from class base stats)
        current_ap        – remaining AP this turn
        inventory         – all items carried (equipped and unequipped)
        equipped          – {slot: EquippableItem} currently worn
        unlocked_commands – set of command names available (class + level + choices)
    """

    char_class: CharacterClass | None = None
    level: int = 1
    xp: int = 0
    xp_to_next_level: int = 100
    total_ap: int = 24
    current_ap: int = 0
    inventory: list[EquippableItem] = field(default_factory=list)
    equipped: dict[str, EquippableItem] = field(default_factory=dict)
    unlocked_commands: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        super().__post_init__()
        self.current_ap = self.total_ap

    # ── AP management ─────────────────────────────────────────────────────

    def reset_ap(self) -> None:
        """Restore current_ap to total_ap at the start of the player's turn."""
        ...

    def spend_ap(self, amount: int) -> bool:
        """Deduct AP. Returns False (and does nothing) if insufficient AP."""
        ...

    def has_ap_for(self, amount: int) -> bool:
        ...

    # ── Equipment ─────────────────────────────────────────────────────────

    def equip(self, item_name: str) -> str:
        """Equip item from inventory. Checks class/level requirements.

        Returns narration string. Swaps previous item back to inventory.
        """
        ...

    def unequip(self, slot: str) -> str:
        """Move the equipped item in `slot` back to inventory."""
        ...

    def can_equip(self, item: EquippableItem) -> tuple[bool, str]:
        """Check class and level requirements. Returns (allowed, reason_if_not)."""
        ...

    # ── Stats (with equipment bonuses) ────────────────────────────────────

    def attack_value(self) -> int:
        """Base attack + all equipped stat_modifiers['attack'] + effect bonuses."""
        ...

    def defense_value(self) -> int:
        """Base defense + all equipped stat_modifiers['defense'] + effect bonuses."""
        ...

    def ap_cost_reduction_for(self, command_name: str) -> int:
        """Sum ability_cost_reductions for `command_name` across all equipped items."""
        ...

    # ── Inventory management ──────────────────────────────────────────────

    def pick_up(self, item: EquippableItem) -> str:
        """Add item to inventory. Returns narration."""
        ...

    def drop(self, item_name: str) -> tuple[EquippableItem | None, str]:
        """Remove item from inventory (and unequip if needed). Returns (item, narration)."""
        ...

    def find_in_inventory(self, name: str) -> EquippableItem | None:
        """Case-insensitive partial name match in inventory."""
        ...

    # ── Progression ───────────────────────────────────────────────────────

    def gain_xp(self, amount: int) -> list[str]:
        """Add XP. Trigger level_up() if threshold met. Returns narration list."""
        ...

    def level_up(self) -> list[str]:
        """Increment level, apply stat increases, return newly unlocked command names."""
        ...

    def unlock_command(self, command_name: str) -> None:
        """Add a command to the player's available set (called by level_up or choice)."""
        ...

    # ── Inventory display ─────────────────────────────────────────────────

    def inventory_summary(self) -> str:
        """Multi-line inventory listing grouped by equipped vs carried."""
        ...

    def equipped_summary(self) -> str:
        """One-line summary of equipped slots for combat display."""
        ...


# ══════════════════════════════════════════════════════════════════════════════
# Enemy
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class Enemy(Entity):
    """A hostile entity.

    Attributes:
        template_id     – links back to the source JSON template
        ai_profile      – named strategy ('aggressive', 'cautious', 'berserker', …)
        total_ap        – max AP per turn
        current_ap      – remaining AP this turn
        intent_pool     – all possible actions loaded from JSON
        active_intents  – ordered list of intents the enemy will execute this turn
        loot_table      – items the enemy may drop on defeat
        xp_reward       – XP granted to the player on kill
    """

    template_id: str = ""
    ai_profile: str = "basic"
    total_ap: int = 18
    current_ap: int = 0
    intent_pool: list[EnemyIntent] = field(default_factory=list)
    active_intents: list[EnemyIntent] = field(default_factory=list)
    loot_table: list[LootEntry] = field(default_factory=list)
    xp_reward: int = 0

    def __post_init__(self) -> None:
        super().__post_init__()
        self.current_ap = self.total_ap

    # ── Turn planning ─────────────────────────────────────────────────────

    def plan_turn(self, player: "Player") -> list[EnemyIntent]:
        """Greedily fill active_intents from intent_pool until AP is exhausted.

        Steps:
        1. Filter intent_pool by condition (hp_below_half, etc.).
        2. Select intents by weight until no valid intent fits remaining AP.
        3. Store result in self.active_intents and return it.
        """
        ...

    def choose_intent(self, available: list[EnemyIntent]) -> EnemyIntent | None:
        """Weighted random selection from a list of valid intents."""
        ...

    def evaluate_condition(self, condition: str, player: "Player") -> bool:
        """Parse and evaluate a condition string against live game state.

        Condition examples: 'hp_below_half', 'player_has_buff:shield', 'always'
        """
        ...

    # ── AP management ─────────────────────────────────────────────────────

    def reset_ap(self) -> None:
        """Restore current_ap to total_ap at the start of the enemy's turn."""
        ...

    def spend_ap(self, amount: int) -> bool:
        """Deduct AP. If an external effect reduces AP mid-turn, re-plan intents."""
        ...

    def modify_ap(self, delta: int, player: "Player") -> str:
        """Apply a delta (positive = restore, negative = drain) and replan.

        Returns narration string describing the AP change and any intent change.
        """
        ...

    # ── Loot ──────────────────────────────────────────────────────────────

    def roll_loot(self) -> list[str]:
        """Roll the loot table. Returns list of item_ids that drop."""
        ...

    # ── Intent display ────────────────────────────────────────────────────

    def intent_display(self) -> str:
        """Formatted string of upcoming intents shown to the player."""
        ...