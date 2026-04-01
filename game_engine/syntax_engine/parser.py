import re

from .lexicon import (
    ADVERBS,
    CANONICAL_VERBS,
    DETERMINERS,
    NOUN_LIKE_COMMANDS,
    PREPOSITIONS,
    SEMANTIC_ROLES,
)
from .models import ParseContext, ParsedSyntaxCommand
from .resolver import TargetResolver
from .unlocks import SyntaxProgression

_TOKEN_RE = re.compile(r"[a-zA-Z']+")


class SyntaxCombatParser:
    """OO parser engine for syntax-driven combat commands."""

    def parse(self, raw_input: str, context: ParseContext) -> ParsedSyntaxCommand:
        clean_input = raw_input.strip().lower()
        tokens = _TOKEN_RE.findall(clean_input)
        if not tokens:
            return ParsedSyntaxCommand(raw_input=raw_input, verb="", ap_letters_cost=0, warnings=["Empty command."])

        unlocks = SyntaxProgression.from_level(context.level)
        verb = self._resolve_verb(tokens[0])

        command = ParsedSyntaxCommand(
            raw_input=clean_input,
            verb=verb,
            ap_letters_cost=self._ap_from_tokens(tokens),
        )

        command.determiners = [t for t in tokens if t in DETERMINERS] if unlocks.determiners else []
        command.prepositions = [
            t for t in tokens if t in PREPOSITIONS and PREPOSITIONS[t].tier <= unlocks.prepositions_tier
        ]
        command.adverbs = [t for t in tokens if t in ADVERBS] if unlocks.adverbs else []
        command.semantic_roles = [
            t for t in tokens if t in SEMANTIC_ROLES and SEMANTIC_ROLES[t].tier <= unlocks.semantic_roles_tier
        ]

        locked_phrases = self._extract_locked_target_phrases(tokens)
        targets, warnings = TargetResolver(context).resolve_phrase_targets(
            locked_phrases,
            precise=command.is_precise_targeting,
        )
        command.direct_targets = targets
        command.warnings.extend(warnings)

        command.warnings.extend(self._validate(tokens, command, unlocks.prepositions_tier))
        return command

    @staticmethod
    def _resolve_verb(token: str) -> str:
        for canonical, variants in CANONICAL_VERBS.items():
            if token in variants:
                return canonical
        return token if token in NOUN_LIKE_COMMANDS else token

    @staticmethod
    def _ap_from_tokens(tokens: list[str]) -> int:
        return sum(len(t) for t in tokens)

    @staticmethod
    def _extract_locked_target_phrases(tokens: list[str]) -> list[str]:
        """Parse target chunks from patterns like:
        - the goblin
        - the goblin and the wizard
        """
        phrases: list[str] = []
        i = 0
        while i < len(tokens):
            if tokens[i] == "the" and i + 1 < len(tokens):
                j = i + 1
                collected = []
                while j < len(tokens) and tokens[j] not in {"and", "the"}:
                    if tokens[j] not in PREPOSITIONS and tokens[j] not in ADVERBS and tokens[j] not in SEMANTIC_ROLES:
                        collected.append(tokens[j])
                    j += 1
                if collected:
                    phrases.append(" ".join(collected))
                i = j
                continue
            i += 1
        return phrases

    @staticmethod
    def _validate(tokens: list[str], command: ParsedSyntaxCommand, unlocked_tier: int) -> list[str]:
        warnings: list[str] = []

        # Prevent exploit chaining like "through through through"
        for prep in PREPOSITIONS:
            if tokens.count(prep) > 1:
                warnings.append(f"Repeated preposition '{prep}' detected; extra copies are ignored.")

        locked_preps = [t for t in tokens if t in PREPOSITIONS and PREPOSITIONS[t].tier > unlocked_tier]
        for prep in locked_preps:
            warnings.append(f"Preposition '{prep}' is locked at your current level.")

        if command.verb == "":
            warnings.append("Could not resolve a command verb.")

        if command.verb in NOUN_LIKE_COMMANDS and len(tokens) == 1:
            warnings.append(f"'{command.verb}' treated as a command verb (noun-like command support).")

        return warnings
