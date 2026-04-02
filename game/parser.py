from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import get_close_matches
from typing import TYPE_CHECKING

from game.commands import CommandRegistry, CommandContext
from game.models import ParsedCommand, ArticleType

if TYPE_CHECKING:
    from game.entities import Player

# ── Configuration ─────────────────────────────────────────────────────────────
TURN_STACK_SIZE = 10
ENTITY_LOG_DECAY_TURNS = 20


# FIX: Turn stack / entity log data structures (unchanged, but moved here)
@dataclass
class TurnEntry:
    verb: str
    target_id: str | None
    target_name: str | None
    room_id: str
    article: str
    modifiers: list[str] = field(default_factory=list)
    disambiguated: bool = False
    turn_number: int = 0


@dataclass
class EntityLogEntry:
    entity_id: str
    entity_name: str
    entity_type: str
    number: str
    adjectives: list[str] = field(default_factory=list)
    room_id: str = ""
    turn_number: int = 0
    last_verb: str = ""


class ContextResolver:
    # (unchanged – keep as is)
    PRONOUN_MAP: dict[str, tuple[str, str]] = {
        "the one": ("singular", "any"),
        "those":   ("plural",   "any"),
        "them":    ("plural",   "any"),
        "him":     ("singular", "enemy"),
        "her":     ("singular", "any"),
        "that":    ("singular", "any"),
        "it":      ("singular", "any"),
    }
    FRAGMENT_STARTERS: frozenset[str] = frozenset({
        "with", "using", "to", "at", "on", "onto", "into",
        "from", "against", "toward", "towards", "via",
    })
    TEMPORAL_PATTERNS: list[tuple[re.Pattern[str], float]] = [
        (re.compile(r"the (?P<n>.+?) i (?:fought|attacked|hit|killed) earlier", re.I), 1.0),
        (re.compile(r"the (?P<n>.+?) from (?:the )?(?:last|previous) room",     re.I), 0.9),
        (re.compile(r"the (?P<n>.+?) i (?:saw|found|picked up) earlier",        re.I), 0.8),
        (re.compile(r"that (?P<n>.+?) (?:from before|earlier)",                 re.I), 0.8),
        (re.compile(r"the (?P<n>.+?) i (?:used|took|grabbed)",                  re.I), 0.7),
    ]

    def rewrite(self, raw: str, player: "Player") -> str:
        tokens = raw.strip().lower().split()
        if not tokens:
            return raw
        rewritten = self._resolve_pronouns(raw, tokens, player)
        if rewritten is not None:
            return rewritten
        rewritten = self._expand_ellipsis(raw, tokens, player)
        if rewritten is not None:
            return rewritten
        rewritten = self._resolve_temporal(raw, player)
        if rewritten is not None:
            return rewritten
        return raw

    def _resolve_pronouns(self, raw: str, tokens: list[str], player: "Player") -> str | None:
        joined = " ".join(tokens)
        for pronoun, (number, category) in self.PRONOUN_MAP.items():
            if pronoun not in joined:
                continue
            referent = self._find_referent(number, category, player)
            if referent is None:
                continue
            return re.sub(re.escape(pronoun), referent, joined, count=1, flags=re.I)
        return None

    def _find_referent(self, number: str, category: str, player: "Player") -> str | None:
        stack: list[TurnEntry] = getattr(player, "turn_stack", [])
        for entry in reversed(stack):
            if entry.target_name is None:
                continue
            log_entry = self._find_in_entity_log(entry.target_id, player)
            if log_entry is None:
                continue
            if number != "any" and log_entry.number != number:
                continue
            if category != "any" and log_entry.entity_type != category:
                continue
            return entry.target_name
        return None

    def _find_in_entity_log(self, entity_id: str | None, player: "Player") -> EntityLogEntry | None:
        if entity_id is None:
            return None
        log: list[EntityLogEntry] = getattr(player, "entity_log", [])
        for entry in reversed(log):
            if entry.entity_id == entity_id:
                return entry
        return None

    def _expand_ellipsis(self, raw: str, tokens: list[str], player: "Player") -> str | None:
        stripped = [t for t in tokens if t not in ("a", "an", "the")]
        if not stripped or stripped[0] not in self.FRAGMENT_STARTERS:
            return None
        stack: list[TurnEntry] = getattr(player, "turn_stack", [])
        if not stack:
            return None
        last = stack[-1]
        prefix = f"{last.verb} {last.target_name}" if last.target_name else last.verb
        return f"{prefix} {raw.strip()}"

    def _resolve_temporal(self, raw: str, player: "Player") -> str | None:
        log: list[EntityLogEntry] = getattr(player, "entity_log", [])
        if not log:
            return None
        best_score = 0.0
        best_replacement: str | None = None
        best_span: tuple[int, int] | None = None
        for pattern, base_score in self.TEMPORAL_PATTERNS:
            m = pattern.search(raw)
            if m is None:
                continue
            fragment = m.group("n").strip()
            entry, score = self._score_entity_match(fragment, base_score, player)
            if entry is not None and score > best_score:
                best_score = score
                best_replacement = entry.entity_name
                best_span = m.span()
        if best_replacement is None or best_span is None:
            return None
        start, end = best_span
        return raw[:start] + best_replacement + raw[end:]

    def _score_entity_match(self, fragment: str, base_score: float, player: "Player") -> tuple[EntityLogEntry | None, float]:
        log: list[EntityLogEntry] = getattr(player, "entity_log", [])
        current_turn: int = getattr(player, "turn_number", 0)
        best_entry: EntityLogEntry | None = None
        best_score = 0.0
        fragment_words = set(fragment.lower().split())
        for entry in log:
            name_words = set(entry.entity_name.lower().split())
            overlap = len(fragment_words & name_words) / max(len(fragment_words), 1)
            if overlap == 0:
                continue
            age = current_turn - entry.turn_number
            recency = max(0.0, 1.0 - age / ENTITY_LOG_DECAY_TURNS)
            score = base_score * overlap * recency
            if score > best_score:
                best_score = score
                best_entry = entry
        return best_entry, best_score

    @staticmethod
    def push_turn(player: "Player", entry: TurnEntry) -> None:
        stack: list[TurnEntry] = getattr(player, "turn_stack", [])
        stack.append(entry)
        if len(stack) > TURN_STACK_SIZE:
            stack.pop(0)
        player.turn_stack = stack

    @staticmethod
    def log_entity(player: "Player", entry: EntityLogEntry) -> None:
        log: list[EntityLogEntry] = getattr(player, "entity_log", [])
        log = [e for e in log if e.entity_id != entry.entity_id]
        log.append(entry)
        player.entity_log = log


class CommandParser:
    _ARTICLES: dict[str, ArticleType] = {
        "the": ArticleType.SPECIFIC,
        "a":   ArticleType.GENERIC,
        "an":  ArticleType.GENERIC,
    }
    _ITEM_PREPS: frozenset[str] = frozenset({"with", "using"})

    def __init__(self, registry: CommandRegistry) -> None:
        self.registry = registry
        self._resolver = ContextResolver()
        # FIX: cache known commands for faster unknown word suggestions
        self._known_commands_cache: list[str] = []
        self._refresh_known_commands()

    def _refresh_known_commands(self) -> None:
        """Refresh the cache of command names that are available to any player."""
        self._known_commands_cache = self.registry.all_intents() + self.registry.all_modifier_names()

    # ── Main entry point ──────────────────────────────────────────────────────
    def parse(self, raw: str, player: "Player", context: CommandContext) -> ParsedCommand:
        normalised = raw.strip().lower()
        if not normalised:
            return self._make_error(raw, "What do you want to do?", ArticleType.NONE)

        expanded = self._resolver.rewrite(normalised, player)
        tokens: list[str] = expanded.split()

        # Modifiers – check unlock first
        for token in tokens:
            mod = self.registry.get_modifier(token)
            if mod is not None and not player.has_unlocked(mod.name):
                return self._make_error(raw, f"You don't know how to use '{mod.name}' yet.", ArticleType.NONE)
        modifiers, tokens = self.extract_modifiers(tokens, player)

        article, tokens = self.extract_article(tokens)

        if not tokens:
            return self._make_error(raw, self.unknown_feedback("", player, context), article)

        verb, *rest = tokens
        cmd_def = self.registry.get_command(verb)
        if cmd_def is None:
            return self._make_error(raw, self.unknown_feedback(verb, player, context), article)

        item_name: str | None = None
        for prep in self._ITEM_PREPS:
            if prep in rest:
                idx = rest.index(prep)
                item_tokens = rest[idx + 1:]
                rest = rest[:idx]
                item_name = " ".join(item_tokens) or None
                break

        target_name, target_index = self.extract_target(rest)

        valid, error_msg = self.validate_command(cmd_def.intent, player, context)
        if not valid:
            return self._make_error(raw, error_msg, article)

        # FIX: AP cost based on command's base cost, not raw length
        ap_cost = self.calculate_ap_cost(cmd_def, player)
        mp_cost = self.calculate_mp_cost(cmd_def, player)

        return ParsedCommand(
            raw=raw,
            intent=cmd_def.intent,
            target_name=target_name,
            target_index=target_index,
            item_name=item_name,
            article=article,
            modifiers=modifiers,
            ap_cost=ap_cost,
            mp_cost=mp_cost,
            valid=True,
            error=None,
        )

    # ── Extraction helpers ────────────────────────────────────────────────────
    def extract_modifiers(self, tokens: list[str], player: "Player") -> tuple[list[str], list[str]]:
        found: list[str] = []
        remaining: list[str] = []
        for token in tokens:
            mod = self.registry.get_modifier(token)
            if mod is not None and player.has_unlocked(mod.name):
                found.append(mod.name)
            else:
                remaining.append(token)
        return found, remaining

    def extract_article(self, tokens: list[str]) -> tuple[ArticleType, list[str]]:
        for i, token in enumerate(tokens):
            if token in self._ARTICLES:
                article = self._ARTICLES[token]
                remaining = tokens[:i] + tokens[i + 1:]
                return article, remaining
        return ArticleType.NONE, tokens

    def extract_target(self, tokens: list[str]) -> tuple[str | None, int | None]:
        if not tokens:
            return None, None
        if len(tokens) == 1 and tokens[0].isdigit():
            return None, int(tokens[0])
        joined = " ".join(tokens)
        return (joined or None), None

    # ── Disambiguation ────────────────────────────────────────────────────────
    def needs_disambiguation(self, target_name: str | None, candidates: list) -> bool:
        if not target_name or not candidates:
            return False
        fragment = target_name.lower()
        matches = [c for c in candidates if fragment in str(c).lower()]
        return len(matches) > 1

    def build_disambiguation_prompt(self, candidates: list) -> str:
        lines = ["Which one?"]
        for i, candidate in enumerate(candidates, start=1):
            lines.append(f"  {i}. {candidate}")
        return "\n".join(lines)

    def resolve_target_by_index(self, index: int, candidates: list):
        if 1 <= index <= len(candidates):
            return candidates[index - 1]
        return None

    # ── Validation ────────────────────────────────────────────────────────────
    def validate_command(self, intent: str, player: "Player", context: CommandContext) -> tuple[bool, str]:
        cmd_def = self.registry.get_command(intent)
        if cmd_def is None:
            return False, f"Unknown command: '{intent}'."
        if getattr(cmd_def, "requires_unlock", False) and not player.has_unlocked(intent):
            return False, f"You haven't learned how to {intent} yet."
        allowed_contexts: list[CommandContext] = getattr(cmd_def, "allowed_contexts", [])
        if allowed_contexts and context not in allowed_contexts:
            return False, "You can't do that here."
        return True, ""

    # ── AP / MP cost calculation (FIXED) ──────────────────────────────────────
    def calculate_ap_cost(self, cmd_def: "CommandDefinition", player: "Player") -> int:
        """AP cost = command's base cost + modifiers flat cost, minus reductions."""
        base = cmd_def.ap_cost_override if cmd_def.ap_cost_override is not None else cmd_def.base_ap_cost
        # Add modifier flat costs
        mod_extra = 0
        for mod_name in getattr(player, "_current_modifiers", []):
            mod = self.registry.get_modifier(mod_name)
            if mod:
                mod_extra += mod.ap_cost_flat
        total = base + mod_extra - player.ap_cost_reduction_for(cmd_def.name)
        return max(1, total)

    def calculate_mp_cost(self, cmd_def: "CommandDefinition", player: "Player") -> int:
        if not cmd_def.costs_mp:
            return 0
        base = cmd_def.mp_cost_override if cmd_def.mp_cost_override is not None else cmd_def.base_mp_cost
        reduction = player.mp_cost_reduction_for(cmd_def.name)
        return max(0, base - reduction)

    # ── Feedback ──────────────────────────────────────────────────────────────
    def unknown_feedback(self, verb: str, player: "Player", context: CommandContext) -> str:
        if not verb:
            return "What do you want to do?"
        # Use cached known commands for speed
        close = get_close_matches(verb, self._known_commands_cache, n=1, cutoff=0.6)
        if close:
            return f"I don't know the word '{verb}'. Did you mean '{close[0]}'?"
        return f"I don't know the word '{verb}'."

    # ── Internal helpers ──────────────────────────────────────────────────────
    def _make_error(self, raw: str, error: str, article: ArticleType) -> ParsedCommand:
        return ParsedCommand(
            raw=raw,
            intent=None,
            target_name=None,
            target_index=None,
            item_name=None,
            article=article,
            modifiers=[],
            ap_cost=0,
            mp_cost=0,
            valid=False,
            error=error,
        )