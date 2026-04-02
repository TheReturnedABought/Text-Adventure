from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import get_close_matches
from typing import TYPE_CHECKING

from game.commands import CommandRegistry, CommandContext
from game.models import ParsedCommand, ArticleType

if TYPE_CHECKING:
    from game.entities import Player
    from game.world import Room


# ── Configuration ─────────────────────────────────────────────────────────────

TURN_STACK_SIZE = 10
ENTITY_LOG_DECAY_TURNS = 20


# ── Turn stack / entity log data structures ───────────────────────────────────

@dataclass
class TurnEntry:
    """One resolved command, pushed onto the player's turn stack."""
    verb: str
    target_id: str | None
    target_name: str | None        # display name for reconstruction
    room_id: str
    article: str                   # raw article word ("the", "a", "an", "")
    modifiers: list[str] = field(default_factory=list)
    disambiguated: bool = False
    turn_number: int = 0


@dataclass
class EntityLogEntry:
    """An entity the player has interacted with, for temporal reference."""
    entity_id: str
    entity_name: str
    entity_type: str               # "enemy" | "item"
    number: str                    # "singular" | "plural"
    adjectives: list[str] = field(default_factory=list)
    room_id: str = ""
    turn_number: int = 0
    last_verb: str = ""


# ── Context resolver ──────────────────────────────────────────────────────────

class ContextResolver:
    """Pre-processing layer that rewrites raw input using conversation history.

    Called by CommandParser.parse() before tokenisation. Returns either a
    rewritten string (one of the three passes succeeded) or the original string
    unchanged. Has no dependency on CommandRegistry and does not validate.

    Three rewrite passes (attempted in order, first success wins):
      1. Pronoun resolution   — "it", "them", "the one", …
      2. Ellipsis expansion   — "with the sword" → borrow last verb + target
      3. Temporal references  — "the goblin I fought earlier"
    """

    # Maps pronoun → (grammatical_number, semantic_category)
    # number:   "singular" | "plural"
    # category: "enemy" | "item" | "any"
    PRONOUN_MAP: dict[str, tuple[str, str]] = {
        "the one": ("singular", "any"),    # multi-word checked before single-word
        "those":   ("plural",   "any"),
        "them":    ("plural",   "any"),
        "him":     ("singular", "enemy"),
        "her":     ("singular", "any"),
        "that":    ("singular", "any"),
        "it":      ("singular", "any"),
    }

    # Prepositions that signal the player typed a verb-less fragment
    FRAGMENT_STARTERS: frozenset[str] = frozenset({
        "with", "using", "to", "at", "on", "onto", "into",
        "from", "against", "toward", "towards", "via",
    })

    # (compiled pattern, base_score) — each pattern must capture group 'n'
    TEMPORAL_PATTERNS: list[tuple[re.Pattern[str], float]] = [
        (re.compile(r"the (?P<n>.+?) i (?:fought|attacked|hit|killed) earlier", re.I), 1.0),
        (re.compile(r"the (?P<n>.+?) from (?:the )?(?:last|previous) room",     re.I), 0.9),
        (re.compile(r"the (?P<n>.+?) i (?:saw|found|picked up) earlier",        re.I), 0.8),
        (re.compile(r"that (?P<n>.+?) (?:from before|earlier)",                 re.I), 0.8),
        (re.compile(r"the (?P<n>.+?) i (?:used|took|grabbed)",                  re.I), 0.7),
    ]

    # ── Main entry point ──────────────────────────────────────────────────────

    def rewrite(self, raw: str, player: "Player") -> str:
        """Attempt the three rewrite passes in order.

        Returns the rewritten string if any pass succeeds, otherwise returns
        raw unchanged so the tokenizer can produce its own error.
        """
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

    # ── Pass 1: pronoun resolution ────────────────────────────────────────────

    def _resolve_pronouns(self, raw: str, tokens: list[str],
                          player: "Player") -> str | None:
        """Replace the first pronoun in raw with the most recent matching entity.

        Multi-word pronouns ("the one") are checked before single-word ones so
        that "attack the one" doesn't get partially matched on "one".
        """
        joined = " ".join(tokens)
        for pronoun, (number, category) in self.PRONOUN_MAP.items():
            if pronoun not in joined:
                continue
            referent = self._find_referent(number, category, player)
            if referent is None:
                continue
            return re.sub(re.escape(pronoun), referent, joined, count=1, flags=re.I)
        return None

    def _find_referent(self, number: str, category: str,
                       player: "Player") -> str | None:
        """Scan the turn stack (newest first) for a matching entity name."""
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

    def _find_in_entity_log(self, entity_id: str | None,
                             player: "Player") -> EntityLogEntry | None:
        if entity_id is None:
            return None
        log: list[EntityLogEntry] = getattr(player, "entity_log", [])
        for entry in reversed(log):
            if entry.entity_id == entity_id:
                return entry
        return None

    # ── Pass 2: ellipsis expansion ────────────────────────────────────────────

    def _expand_ellipsis(self, raw: str, tokens: list[str],
                         player: "Player") -> str | None:
        """Detect a verb-less fragment and prepend the last command's verb + target.

        "with the sword" → "attack goblin with the sword"
        "to the guard"   → "talk to the guard"
        """
        stripped = [t for t in tokens if t not in ("a", "an", "the")]
        if not stripped or stripped[0] not in self.FRAGMENT_STARTERS:
            return None

        stack: list[TurnEntry] = getattr(player, "turn_stack", [])
        if not stack:
            return None

        last = stack[-1]
        prefix = (
            f"{last.verb} {last.target_name}"
            if last.target_name
            else last.verb
        )
        return f"{prefix} {raw.strip()}"

    # ── Pass 3: temporal reference resolution ─────────────────────────────────

    def _resolve_temporal(self, raw: str, player: "Player") -> str | None:
        """Replace a temporal reference phrase with the best-scoring entity name."""
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

    def _score_entity_match(self, fragment: str, base_score: float,
                            player: "Player") -> tuple[EntityLogEntry | None, float]:
        """Score each entity log entry against the name fragment.

        Scoring: base × word_overlap × recency_factor.
        Recency decays linearly to 0 at ENTITY_LOG_DECAY_TURNS.
        """
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

    # ── Turn stack / entity log helpers (called by controllers) ───────────────

    @staticmethod
    def push_turn(player: "Player", entry: TurnEntry) -> None:
        """Push a resolved command onto the player's turn stack, capped at TURN_STACK_SIZE."""
        stack: list[TurnEntry] = getattr(player, "turn_stack", [])
        stack.append(entry)
        if len(stack) > TURN_STACK_SIZE:
            stack.pop(0)
        player.turn_stack = stack

    @staticmethod
    def log_entity(player: "Player", entry: EntityLogEntry) -> None:
        """Add or refresh an entity in the player's entity log."""
        log: list[EntityLogEntry] = getattr(player, "entity_log", [])
        log = [e for e in log if e.entity_id != entry.entity_id]
        log.append(entry)
        player.entity_log = log


# ── Command parser ────────────────────────────────────────────────────────────

class CommandParser:
    """Parser-first command resolver.

    Responsibilities:
      1. Hand raw input to ContextResolver for conversational rewriting.
      2. Tokenise the rewritten string.
      3. Strip and record modifier keywords (heavy, quick, …).
      4. Strip and record article keywords (the, a, an) → ArticleType.
      5. Identify the verb and resolve it to a CommandDefinition.
      6. Extract target name, target index (disambiguation), and item name.
      7. Validate the resolved command against the current context and player.
      8. Calculate AP / MP cost from the *raw* (pre-expansion) string.
         AP cost = len(raw) - reductions, min 1.
         MP cost = fixed value from command definition (mp_cost_override) if costs_mp, else 0.
      9. Return a fully populated ParsedCommand.

    The parser does NOT look up enemies or objects by name — that is the
    responsibility of the caller (CombatController or ExplorationController).
    """

    _ARTICLES: dict[str, ArticleType] = {
        "the": ArticleType.SPECIFIC,
        "a":   ArticleType.GENERIC,
        "an":  ArticleType.GENERIC,
    }

    _ITEM_PREPS: frozenset[str] = frozenset({"with", "using"})

    def __init__(self, registry: CommandRegistry) -> None:
        self.registry = registry
        self._resolver = ContextResolver()

    # ── Main entry point ──────────────────────────────────────────────────────

    def parse(self, raw: str, player: "Player",
              context: CommandContext) -> ParsedCommand:
        """Parse a raw command string into a fully normalised ParsedCommand.

        Steps (in order):
        1.  Normalise whitespace, lowercase.
        2.  ContextResolver.rewrite() — pronoun, ellipsis, temporal passes.
        3.  Tokenise the expanded string.
        4.  extract_modifiers() — pull learned modifiers out of the token list.
            Unlearned modifiers (exist in registry but player hasn't unlocked)
            produce an error immediately.
        5.  extract_article() — detect and record the article type.
        6.  Split remaining tokens: verb + rest.
        7.  Resolve verb via registry.get_command(); unknown verb → unknown_feedback().
        8.  Split rest on item preposition ("with", "using") to isolate item_name.
        9.  extract_target() — target name or numeric disambiguation index.
        10. validate_command() — context check + unlock check.
        11. calculate_ap_cost() from raw; _calculate_mp_cost() from command definition.
        12. Return ParsedCommand.
        """
        # 1. Normalise
        normalised = raw.strip().lower()
        if not normalised:
            return self._make_error(raw, "What do you want to do?", ArticleType.NONE)

        # 2. Conversational rewrite (pronoun / ellipsis / temporal)
        expanded = self._resolver.rewrite(normalised, player)

        # 3. Tokenise
        tokens: list[str] = expanded.split()

        # 4. Modifiers
        #    Pass A: reject any token that is a registered modifier the player
        #            hasn't learned yet — before stripping, so the error is precise.
        for token in tokens:
            mod = self.registry.get_modifier(token)
            if mod is not None and not player.has_unlocked(mod.name):
                return self._make_error(
                    raw,
                    f"You don't know how to use '{mod.name}' yet.",
                    ArticleType.NONE,
                )

        #    Pass B: strip learned modifiers
        modifiers, tokens = self.extract_modifiers(tokens, player)

        # 5. Article
        article, tokens = self.extract_article(tokens)

        # 6. Verb
        if not tokens:
            return self._make_error(
                raw, self.unknown_feedback("", player, context), article
            )

        verb, *rest = tokens

        # 7. Resolve verb
        cmd_def = self.registry.get_command(verb)
        if cmd_def is None:
            return self._make_error(
                raw, self.unknown_feedback(verb, player, context), article
            )

        # 8. Separate item from target ("attack goblin with sword")
        item_name: str | None = None
        for prep in self._ITEM_PREPS:
            if prep in rest:
                idx = rest.index(prep)
                item_tokens = rest[idx + 1:]
                rest = rest[:idx]
                item_name = " ".join(item_tokens) or None
                break

        # 9. Target + disambiguation index
        target_name, target_index = self.extract_target(rest)

        # 10. Validate
        valid, error_msg = self.validate_command(cmd_def.intent, player, context)
        if not valid:
            return self._make_error(raw, error_msg, article)

        # 11. Costs — always from *raw* for AP, from command definition for MP.
        #     AP cost: len(raw) - reductions, min 1.
        #     MP cost: fixed value from cmd_def.mp_cost_override (or 0 if not costs_mp)
        ap_cost = self.calculate_ap_cost(raw, cmd_def.intent, player)
        mp_cost = self._calculate_mp_cost(cmd_def, player)

        # 12. Return
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

    def extract_modifiers(self, tokens: list[str],
                          player: "Player") -> tuple[list[str], list[str]]:
        """Scan tokens for learned modifier keywords and strip them.

        Assumes unlearned modifiers have already been rejected in parse().
        Returns (found_modifier_names, remaining_tokens).
        Modifiers can appear anywhere in the token list.
        """
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
        """Find and remove the first article word in tokens.

        Returns (ArticleType, remaining_tokens).
        Defaults to ArticleType.NONE when no article is present.
        """
        for i, token in enumerate(tokens):
            if token in self._ARTICLES:
                article = self._ARTICLES[token]
                remaining = tokens[:i] + tokens[i + 1:]
                return article, remaining
        return ArticleType.NONE, tokens

    def extract_target(self, tokens: list[str]) -> tuple[str | None, int | None]:
        """Parse remaining tokens (after verb extraction) for a target.

        Returns (target_name_fragment, target_index).
          - target_index is set when tokens is a single digit string ('1', '2', …);
            this signals the player is answering a disambiguation prompt.
          - target_name_fragment is the joined remaining text otherwise.
        """
        if not tokens:
            return None, None
        if len(tokens) == 1 and tokens[0].isdigit():
            return None, int(tokens[0])
        joined = " ".join(tokens)
        return (joined or None), None

    # ── Disambiguation ────────────────────────────────────────────────────────

    def needs_disambiguation(self, target_name: str | None,
                             candidates: list) -> bool:
        """Return True if target_name matches more than one candidate."""
        if not target_name or not candidates:
            return False
        fragment = target_name.lower()
        matches = [c for c in candidates if fragment in str(c).lower()]
        return len(matches) > 1

    def build_disambiguation_prompt(self, candidates: list) -> str:
        """Return a numbered list string for the player to choose from.

        Example output:
            Which one?
              1. Goblin Scout
              2. Goblin Guard
        """
        lines = ["Which one?"]
        for i, candidate in enumerate(candidates, start=1):
            lines.append(f"  {i}. {candidate}")
        return "\n".join(lines)

    def resolve_target_by_index(self, index: int, candidates: list):
        """Return the candidate at 1-based index, or None if out of range."""
        if 1 <= index <= len(candidates):
            return candidates[index - 1]
        return None

    # ── Validation ────────────────────────────────────────────────────────────

    def validate_command(self, intent: str, player: "Player",
                         context: CommandContext) -> tuple[bool, str]:
        """Check if the resolved command is available to this player.

        Returns (valid, error_message).
        Checks (in order): command exists · player has unlocked it · valid context.
        """
        cmd_def = self.registry.get_command(intent)
        if cmd_def is None:
            return False, f"Unknown command: '{intent}'."

        if getattr(cmd_def, "requires_unlock", False) and not player.has_unlocked(intent):
            return False, f"You haven't learned how to {intent} yet."

        allowed_contexts: list[CommandContext] = getattr(cmd_def, "allowed_contexts", [])
        if allowed_contexts and context not in allowed_contexts:
            return False, "You can't do that here."

        return True, ""

    # ── AP / MP cost calculation ──────────────────────────────────────────────

    def calculate_ap_cost(self, raw: str, intent: str,
                          player: "Player") -> int:
        """Calculate the AP cost of a typed command.

        Rules (in priority order):
        1. If CommandDefinition.ap_cost_override is set → use that value.
        2. Else → len(raw.strip()) — the number of characters typed.
           Using the *raw* string (not the expanded one) rewards players who use
           shorthand: "attack it" (9) costs less than "attack goblin" (13).
        3. Subtract player.ap_cost_reduction_for(intent) from equipped items.
        Minimum cost is always 1.
        """
        cmd_def = self.registry.get_command(intent)
        override: int | None = getattr(cmd_def, "ap_cost_override", None)
        base = override if override is not None else len(raw.strip())
        reduction = player.ap_cost_reduction_for(intent)
        return max(1, base - reduction)

    def _calculate_mp_cost(self, cmd_def: "CommandDefinition",
                           player: "Player") -> int:
        """Calculate the MP cost of a command.

        Rules:
        1. If the command does not have `costs_mp` set to True → cost 0.
        2. Otherwise, base MP cost = cmd_def.mp_cost_override (if provided) or 1.
        3. Subtract player.mp_cost_reduction_for(cmd_def.intent) from equipped items.
        4. Minimum cost is 0.
        """
        if not getattr(cmd_def, "costs_mp", False):
            return 0

        base = cmd_def.mp_cost_override
        if base is None:
            # default MP cost for a command that costs MP but no override given
            base = 1

        reduction = (
            player.mp_cost_reduction_for(cmd_def.intent)
            if hasattr(player, "mp_cost_reduction_for")
            else 0
        )
        return max(0, base - reduction)

    # ── Feedback ──────────────────────────────────────────────────────────────

    def unknown_feedback(self, verb: str, player: "Player",
                         context: CommandContext) -> str:
        """Return a helpful error for an unrecognised word.

        Collects every command and modifier name currently visible to this
        player, then suggests the closest match if edit distance is small
        enough (cutoff 0.6).
        """
        if not verb:
            return "What do you want to do?"

        known: list[str] = []
        for intent in self.registry.all_intents():
            cmd_def = self.registry.get_command(intent)
            if cmd_def is None:
                continue
            if not getattr(cmd_def, "requires_unlock", False) or player.has_unlocked(intent):
                known.append(intent)

        known.extend(
            name for name in self.registry.all_modifier_names()
            if player.has_unlocked(name)
        )

        close = get_close_matches(verb, known, n=1, cutoff=0.6)
        if close:
            return f"I don't know the word '{verb}'. Did you mean '{close[0]}'?"
        return f"I don't know the word '{verb}'."

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _make_error(self, raw: str, error: str,
                    article: ArticleType) -> ParsedCommand:
        """Construct a ParsedCommand that signals a parse failure."""
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