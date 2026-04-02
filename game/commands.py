from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from game.entities import Player


# ── Context enum ──────────────────────────────────────────────────────────────

class CommandContext(Enum):
    COMBAT = auto()
    WORLD = auto()
    ANY = auto()


# ── Command modifier ──────────────────────────────────────────────────────────

@dataclass
class CommandModifier:
    """A keyword that can prefix a command verb to alter how it resolves.

    Examples: 'heavy', 'quick', 'silent', 'smash'
    AP is still letter-count-based for the full command string.

    Attributes:
        name            – keyword as typed (e.g. 'heavy')
        description     – player-facing explanation
        dice_count_mult – multiplier applied to the base command's dice count (e.g. 2.0 = heavy)
        dice_sides_mult – multiplier on die size (rarely used)
        flat_bonus      – extra flat damage/block added after dice
        ap_cost_flat    – extra flat AP added on top of letter cost (can be 0)
        unlock_class    – None = available to all
        unlock_level    – 0 = baseline, no unlock needed
        valid_contexts  – which game modes allow this modifier
        tags            – ['aoe', 'elemental', …] for future filtering
    """

    name: str
    description: str
    dice_count_mult: float = 1.0
    dice_sides_mult: float = 1.0
    flat_bonus: int = 0
    ap_cost_flat: int = 0
    unlock_class: str | None = None
    unlock_level: int = 0
    valid_contexts: list[CommandContext] = field(default_factory=lambda: [CommandContext.ANY])
    tags: list[str] = field(default_factory=list)


# ── Article rule ──────────────────────────────────────────────────────────────

@dataclass
class ArticleRule:
    """Defines what article words imply and their mechanical effects.

    Specific articles ('the') imply target precision.
    Generic articles ('a', 'an') imply indifference → bonus damage.
    """

    specific_words: list[str] = field(default_factory=lambda: ["the"])
    generic_words: list[str] = field(default_factory=lambda: ["a", "an"])
    generic_flat_bonus: int = 3     # damage bonus when using a generic article
    specific_flat_bonus: int = 0    # (currently 0, but keep extendable)


# ── Command definition ────────────────────────────────────────────────────────

@dataclass
class CommandDefinition:
    """Full definition of one learnable/unlockable player command.

    Attributes:
        name              – canonical verb (e.g. 'attack', 'smash', 'block')
        aliases           – alternative verbs that map to this command
        description       – player-facing rules text
        ap_cost_override  – if set, ignore letter-count; use this fixed AP cost
        base_dice         – dice expression string (e.g. '3d6+2'); None = no dice (e.g. 'equip')
        unlock_class      – None = any class
        unlock_level      – 0 = no unlock required (base command)
        valid_contexts    – COMBAT, WORLD, or ANY
        modifiers_allowed – list of modifier names valid with this command
        tags              – ['melee', 'aoe', 'block', 'destructive', …]
        world_use_hint    – flavour string for world use ('You smash the __')
    """

    name: str
    aliases: list[str]
    description: str
    ap_cost_override: int | None = None
    base_dice: str | None = None
    unlock_class: str | None = None
    unlock_level: int = 0
    valid_contexts: list[CommandContext] = field(
        default_factory=lambda: [CommandContext.COMBAT, CommandContext.WORLD]
    )
    modifiers_allowed: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    world_use_hint: str | None = None


# ── Command registry ──────────────────────────────────────────────────────────

class CommandRegistry:
    """Central store for all CommandDefinitions and CommandModifiers.

    Load JSON data once at startup, then query at runtime.
    """

    def __init__(self) -> None:
        self._commands: dict[str, CommandDefinition] = {}    # name -> definition
        self._alias_map: dict[str, str] = {}                 # alias -> canonical name
        self._modifiers: dict[str, CommandModifier] = {}     # name -> modifier

    # ── Registration ──────────────────────────────────────────────────────

    def register_command(self, cmd: CommandDefinition) -> None:
        """Add a command and index all its aliases."""
        ...

    def register_modifier(self, mod: CommandModifier) -> None:
        """Add a modifier keyword."""
        ...

    def load_from_dict(self, data: dict) -> None:
        """Bulk-load commands and modifiers from a parsed JSON dict.

        Expected top-level keys: 'commands', 'modifiers', 'articles'
        """
        ...

    # ── Lookup ────────────────────────────────────────────────────────────

    def get_command(self, verb: str) -> CommandDefinition | None:
        """Resolve verb or alias → CommandDefinition. None if unknown."""
        ...

    def get_modifier(self, word: str) -> CommandModifier | None:
        ...

    def all_commands(self) -> list[CommandDefinition]:
        ...

    # ── Player-scoped queries ─────────────────────────────────────────────

    def available_for(self, player: "Player", context: CommandContext) -> list[CommandDefinition]:
        """Return commands unlocked by this player's class/level in the given context."""
        ...

    def is_available_for(self, player: "Player", command_name: str,
                         context: CommandContext) -> bool:
        ...

    # ── AP helpers ────────────────────────────────────────────────────────

    def ap_cost_for(self, raw_command: str, cmd: CommandDefinition,
                    player: "Player") -> int:
        """Calculate AP cost for a full typed command string.

        Rules:
        1. If cmd.ap_cost_override is set → use that.
        2. Else → len(raw_command) stripped of leading/trailing spaces.
        3. Subtract any per-item cost reductions the player has equipped.
        """
        ...


# ── Unlock table ──────────────────────────────────────────────────────────────

class UnlockTable:
    """Maps (class_name, level) → list of command names newly unlocked.

    For choice unlocks (level grants one of several options) store each
    choice group as a separate entry; the game.py handles presenting the
    choice to the player.
    """

    def __init__(self) -> None:
        # { class_name: { level: [command_names] } }
        self._table: dict[str, dict[int, list[str]]] = {}
        # { class_name: { level: [[choice_a, choice_b], …] } }  – optional forks
        self._choice_table: dict[str, dict[int, list[list[str]]]] = {}

    def add_unlock(self, class_name: str, level: int, command_name: str) -> None:
        ...

    def add_choice_unlock(self, class_name: str, level: int,
                          choices: list[str]) -> None:
        """Register a level-up fork: player chooses one command from `choices`."""
        ...

    def get_unlocks(self, class_name: str, level: int) -> list[str]:
        """Commands unlocked at exactly this class + level (not cumulative)."""
        ...

    def get_choice_unlocks(self, class_name: str, level: int) -> list[list[str]]:
        """Choice groups presented to the player at this level-up."""
        ...

    def all_unlocked_by(self, class_name: str, up_to_level: int) -> list[str]:
        """Flat list of all non-choice commands available up to and including level."""
        ...

    def load_from_dict(self, data: dict) -> None:
        """Load from the 'level_unlocks' and 'choice_unlocks' blocks in a class JSON."""
        ...