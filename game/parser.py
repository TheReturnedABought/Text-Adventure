from __future__ import annotations

from typing import TYPE_CHECKING

from game.commands import CommandRegistry, CommandContext
from game.models import ParsedCommand, ArticleType

if TYPE_CHECKING:
    from game.entities import Player
    from game.world import Room


class CommandParser:
    """Parser-first command resolver.

    Responsibilities:
      1. Tokenise the raw input string.
      2. Strip and record modifier keywords (heavy, quick, …).
      3. Strip and record article keywords (the, a, an) → ArticleType.
      4. Identify the verb and resolve it to a CommandDefinition.
      5. Extract target name, target index (disambiguation), and item name.
      6. Validate the resolved command against the current context and player.
      7. Return a fully populated ParsedCommand.

    The parser does NOT look up enemies or objects by name – that is the
    responsibility of the caller (CombatController or ExplorationController).
    """

    def __init__(self, registry: CommandRegistry) -> None:
        self.registry = registry

    # ── Main entry point ──────────────────────────────────────────────────

    def parse(self, raw: str, player: "Player",
              context: CommandContext) -> ParsedCommand:
        """Parse a raw command string into a fully normalised ParsedCommand.

        Steps (in order):
        1. Normalise whitespace, lowercase.
        2. extract_modifiers() – pull out and remove modifier words.
        3. extract_article() – detect and record the article type.
        4. Split remaining tokens: verb + rest.
        5. Resolve verb via registry.get_command().
        6. Extract target / item from rest.
        7. Detect numeric disambiguation (rest is a single digit).
        8. Validate context and player unlock.
        9. Return ParsedCommand.
        """
        ...

    # ── Extraction helpers ────────────────────────────────────────────────

    def extract_modifiers(self, tokens: list[str],
                          player: "Player") -> tuple[list[str], list[str]]:
        """Scan tokens for known modifier keywords available to the player.

        Returns (found_modifier_names, remaining_tokens).
        Modifiers can appear before the verb or between words.
        """
        ...

    def extract_article(self, tokens: list[str]) -> tuple[ArticleType, list[str]]:
        """Find the first article word in tokens and remove it.

        Returns (ArticleType, remaining_tokens).
        """
        ...

    def extract_target(self, tokens: list[str]) -> tuple[str | None, int | None]:
        """Parse the remaining tokens after verb extraction for a target.

        Returns (target_name_fragment, target_index).
        target_index is set if tokens is a single digit string ('1', '2', …).
        target_name_fragment is the joined remaining text otherwise.
        """
        ...

    # ── Disambiguation ────────────────────────────────────────────────────

    def needs_disambiguation(self, target_name: str | None,
                             candidates: list) -> bool:
        """Return True if target_name matches more than one candidate."""
        ...

    def build_disambiguation_prompt(self, candidates: list) -> str:
        """Return a numbered list string for the player to choose from.

        Example: 'Which goblin?\n  1. Goblin Scout\n  2. Goblin Guard'
        """
        ...

    def resolve_target_by_index(self, index: int, candidates: list):
        """Return the candidate at 1-based index, or None if out of range."""
        ...

    # ── Validation ────────────────────────────────────────────────────────

    def validate_command(self, intent: str, player: "Player",
                         context: CommandContext) -> tuple[bool, str]:
        """Check if the resolved command is available to this player.

        Returns (valid, error_message_if_not).
        Checks: command exists, player has unlocked it, valid in current context.
        """
        ...

    # ── AP cost calculation ───────────────────────────────────────────────

    def calculate_ap_cost(self, raw: str, intent: str,
                          player: "Player") -> int:
        """Calculate the AP cost of a typed command.

        Rules (in priority order):
        1. If CommandDefinition.ap_cost_override is set → use that value.
        2. Else → len(raw.strip()) – the number of characters typed.
        3. Subtract player.ap_cost_reduction_for(intent) from equipped items.
        Minimum cost is always 1.
        """
        ...

    # ── Feedback ──────────────────────────────────────────────────────────

    def unknown_verb_feedback(self, verb: str, player: "Player",
                              context: CommandContext) -> str:
        """Return a helpful error for an unrecognised verb.

        Suggest the closest known command if edit distance is small.
        """
        ...

    def suggest_closest(self, verb: str,
                        available: list[str]) -> str | None:
        """Find the closest available command name by edit distance.

        Returns the suggestion string or None if nothing is close enough.
        """
        ...