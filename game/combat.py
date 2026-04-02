from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING

from game.commands import CommandContext
from game.effects import EffectTrigger
from game.models import BattleContext, ParsedCommand

if TYPE_CHECKING:
    from game.entities import Enemy, Player
    from game.parser import CommandParser
    from game.commands import CommandRegistry, CommandDefinition
    from game.dice import DiceExpression


# ══════════════════════════════════════════════════════════════════════════════
# Combat result
# ══════════════════════════════════════════════════════════════════════════════

class CombatOutcome(Enum):
    ONGOING = auto()
    PLAYER_WON = auto()
    PLAYER_FLED = auto()
    PLAYER_DEFEATED = auto()


@dataclass
class TurnResult:
    """Collected log of everything that happened in one entity's turn."""
    lines: list[str] = field(default_factory=list)
    ap_spent: int = 0
    outcome: CombatOutcome = CombatOutcome.ONGOING

    def add(self, line: str) -> None:
        self.lines.append(line)

    def is_finished(self) -> bool:
        return self.outcome != CombatOutcome.ONGOING

    def display(self) -> str:
        return "\n".join(self.lines)


# ══════════════════════════════════════════════════════════════════════════════
# Combat controller
# ══════════════════════════════════════════════════════════════════════════════

class CombatController:
    """Turn-based combat engine driven by parsed player commands.

    One CombatController is instantiated per combat encounter and discarded
    when the encounter ends.

    Attributes:
        parser      – shared CommandParser
        registry    – shared CommandRegistry
        enemies     – all enemies in this encounter (may be >1)
        player      – the player entity
        round       – current round number (increments after all entities act)
        log         – full combat log as a list of strings
    """

    def __init__(self, parser: "CommandParser", registry: "CommandRegistry",
                 player: "Player", enemies: list["Enemy"]) -> None:
        self.parser = parser
        self.registry = registry
        self.player = player
        self.enemies = enemies
        self.round: int = 1
        self.log: list[str] = []
        self._pending_disambiguation: list["Enemy"] | None = None

    # ══════════════════════════════════════════════════════════════════════
    # Public API (called by game.py loop)
    # ══════════════════════════════════════════════════════════════════════

    def start_encounter(self) -> str:
        """Called once when combat begins (line-of-sight trigger or room entry).

        Returns the opening narration shown to the player.
        Plan first-round enemy intents.
        """
        ...

    def player_input(self, raw: str) -> TurnResult:
        """Process one player command string.

        Steps:
        1. Check if we're waiting for disambiguation → route to resolve_disambiguation().
        2. parse() in COMBAT context.
        3. Check intent: 'flee', 'look', 'status', 'help' → non-AP costing meta commands.
        4. Check AP: if cost > current_ap → return 'Not enough AP.' (turn not wasted).
        5. Dispatch to the correct resolve_* method.
        6. Spend AP via player.spend_ap().
        7. Tick ON_ACTION effects.
        8. Check win/defeat conditions → set outcome if met.
        9. If player's AP reaches 0 → end_player_turn().
        """
        ...

    def end_player_turn(self) -> TurnResult:
        """Called automatically when player AP is exhausted, or by 'wait' command.

        Steps:
        1. Clear player block.
        2. Tick ON_TURN_END effects on player.
        3. Reset player AP for next round.
        4. Run enemy_turn() for each living enemy.
        5. Increment round counter.
        6. Plan enemy intents for next round.
        7. Tick ON_TURN_START effects on player.
        8. Return combined TurnResult.
        """
        ...

    def enemy_turn(self, enemy: "Enemy") -> TurnResult:
        """Execute all of this enemy's active_intents in order.

        For each intent:
        1. Spend enemy AP.
        2. Call resolve_enemy_intent().
        3. Add to result log.
        4. Clear enemy block (at start of their micro-turn).
        Tick ON_TURN_END on enemy after all intents done.
        """
        ...

    def check_outcome(self) -> CombatOutcome:
        """Evaluate win/loss conditions. Called after each action."""
        ...

    # ══════════════════════════════════════════════════════════════════════
    # Player action resolution
    # ══════════════════════════════════════════════════════════════════════

    def resolve_attack(self, parsed: ParsedCommand, result: TurnResult) -> None:
        """Resolve a basic attack command.

        Steps:
        1. Identify target: resolve_target() handles multi-enemy + disambiguation.
        2. Build DiceExpression from command base_dice + modifiers.
        3. Apply article bonus (generic article → +flat_bonus).
        4. Roll damage.
        5. Apply target block and defense via enemy.receive_damage().
        6. Apply effect_on_hit if command specifies one.
        7. Tick ON_DAMAGE_DEALT on player.
        8. Log result.
        """
        ...

    def resolve_block(self, parsed: ParsedCommand, result: TurnResult) -> None:
        """Resolve a block command.

        Roll block dice → call player.add_block().
        Apply any modifier scaling (a modifier could reduce or increase block).
        """
        ...

    def resolve_ability(self, parsed: ParsedCommand, result: TurnResult) -> None:
        """Resolve an ability command (e.g. 'use spark', 'cast ember slash').

        1. Find ability in player.equipped by ability name.
        2. Build BattleContext snapshot.
        3. Call ability.execute(context).
        4. Apply effect_on_hit if specified.
        5. Log result.
        """
        ...

    def resolve_equip(self, parsed: ParsedCommand, result: TurnResult) -> None:
        """Equip or unequip an item mid-combat (costs AP like any other command)."""
        ...

    def resolve_flee(self, parsed: ParsedCommand, result: TurnResult) -> None:
        """Attempt to flee combat.

        Implement flee success chance here (e.g. dice roll vs enemy level).
        On success → set outcome PLAYER_FLED.
        """
        ...

    def resolve_status(self, result: TurnResult) -> None:
        """Print full status: player HP/AP/block/effects, all enemy HP/intents."""
        ...

    def resolve_help(self, result: TurnResult) -> None:
        """Print available combat commands with AP costs for this player."""
        ...

    # ══════════════════════════════════════════════════════════════════════
    # Enemy action resolution
    # ══════════════════════════════════════════════════════════════════════

    def resolve_enemy_intent(self, enemy: "Enemy",
                             intent, result: TurnResult) -> None:
        """Execute one EnemyIntent.

        ATTACK: roll dice → player.receive_damage() → apply effect_on_hit.
        BLOCK:  roll dice → enemy.add_block().
        BUFF/DEBUFF: apply status effect.
        FLEE/WAIT: narrate only.
        """
        ...

    # ══════════════════════════════════════════════════════════════════════
    # Target resolution
    # ══════════════════════════════════════════════════════════════════════

    def resolve_target(self, parsed: ParsedCommand,
                       result: TurnResult) -> "Enemy | None":
        """Identify which enemy the player's command targets.

        Logic:
        1. If parsed.target_index is set → get_enemy_by_index().
        2. Else if parsed.target_name → filter living enemies by name fragment.
        3. If exactly 1 match → return it.
        4. If 0 matches → error.
        5. If >1 matches and article is GENERIC → pick randomly.
        6. If >1 matches and article is SPECIFIC → set _pending_disambiguation,
           return None (caller must halt and ask player to type a number).
        7. If no target_name and only 1 living enemy → auto-target it.
        8. If no target_name and multiple enemies → disambiguation.
        """
        ...

    def resolve_disambiguation(self, raw: str, result: TurnResult) -> "Enemy | None":
        """Called when _pending_disambiguation is set.

        raw is the player's response (expected to be a number).
        Clears _pending_disambiguation on success.
        """
        ...

    # ══════════════════════════════════════════════════════════════════════
    # Dice and modifier application
    # ══════════════════════════════════════════════════════════════════════

    def build_attack_dice(self, cmd: "CommandDefinition",
                          parsed: ParsedCommand,
                          player: "Player") -> "DiceExpression":
        """Construct the final DiceExpression for an attack.

        Applies modifier multipliers (heavy → x2 count), flat article bonus,
        and any passive equipment bonuses that affect dice.
        """
        ...

    def apply_modifiers_to_dice(self, base: "DiceExpression",
                                modifier_names: list[str]) -> "DiceExpression":
        """Chain modifier transformations onto a base DiceExpression."""
        ...

    # ══════════════════════════════════════════════════════════════════════
    # Display helpers
    # ══════════════════════════════════════════════════════════════════════

    def combat_header(self) -> str:
        """Status bar shown at the start of each player input prompt.

        Format:  Round N | [Hero] HP: 40/40  AP: 18/24  Block: 0
                          [Goblin] HP: 8/12  | Intends: scratch (1d4+1), cower
        """
        ...

    def format_roll(self, expression: "DiceExpression", rolls: list[int],
                    total: int) -> str:
        """Format a dice roll for the log: 'rolled 3d6+2 → [4,2,5] +2 = 13'."""
        ...