# game/parser.py
import re
from difflib import get_close_matches
from typing import List, Optional, Tuple

from game.commands import CommandRegistry, CommandContext
from game.models import ParsedCommand, ArticleType

_TYPO_MAP = {
    "wouth": "south", "sputh": "south", "gp": "go",
    "noth": "north", "eastt": "east", "westt": "west"
}
_ARTICLES = {"the": ArticleType.SPECIFIC, "a": ArticleType.GENERIC, "an": ArticleType.GENERIC}
_ITEM_PREPS = frozenset({"with", "using"})

class CommandParser:
    def __init__(self, registry: CommandRegistry):
        self.registry = registry
        self._known_commands = registry.all_intents() + registry.all_modifier_names()

    def parse(self, raw: str, player, context: CommandContext) -> ParsedCommand:
        normalised = self._preprocess_typos(raw.strip().lower())
        tokens = normalised.split()
        modifiers, tokens = self._extract_modifiers(tokens, player)
        article, tokens = self._extract_article(tokens)
        if not tokens:
            return self._make_error(raw, self._unknown_feedback("", player, context), article)
        verb, *rest = tokens
        cmd_def = self.registry.get_command(verb)
        if cmd_def is None:
            return self._make_error(raw, self._unknown_feedback(verb, player, context), article)
        target_name, target_index = None, None
        if cmd_def.name == "go" and not rest:
            target_name = verb
        else:
            target_name, target_index = self._extract_target(rest)
        item_name = None
        for prep in _ITEM_PREPS:
            if prep in rest:
                idx = rest.index(prep)
                item_name = " ".join(rest[idx+1:]) or None
                rest = rest[:idx]
                break
        if not self._is_available(cmd_def, player, context):
            return self._make_error(raw, f"You can't use '{cmd_def.name}' here.", article)
        ap_cost, mp_cost = self._compute_costs(cmd_def, player, normalised)
        return ParsedCommand(
            raw=raw, intent=cmd_def.intent, target_name=target_name,
            target_index=target_index, item_name=item_name, article=article,
            modifiers=modifiers, ap_cost=ap_cost, mp_cost=mp_cost, valid=True, error=None
        )

    def _preprocess_typos(self, raw: str) -> str:
        words = raw.strip().lower().split()
        corrected = [_TYPO_MAP.get(w, w) for w in words]
        return " ".join(corrected)

    def _extract_modifiers(self, tokens: List[str], player) -> Tuple[List[str], List[str]]:
        found, remaining = [], []
        for token in tokens:
            mod = self.registry.get_modifier(token)
            if mod and player.has_unlocked(mod.name):
                found.append(mod.name)
            else:
                remaining.append(token)
        return found, remaining

    def _extract_article(self, tokens: List[str]) -> Tuple[ArticleType, List[str]]:
        for i, token in enumerate(tokens):
            if token in _ARTICLES:
                article = _ARTICLES[token]
                remaining = tokens[:i] + tokens[i+1:]
                return article, remaining
        return ArticleType.NONE, tokens

    def _extract_target(self, tokens: List[str]) -> Tuple[Optional[str], Optional[int]]:
        if not tokens: return None, None
        if len(tokens) == 1 and tokens[0].isdigit():
            return None, int(tokens[0])
        return " ".join(tokens), None

    def _is_available(self, cmd_def, player, context: CommandContext) -> bool:
        if context not in cmd_def.valid_contexts and CommandContext.ANY not in cmd_def.valid_contexts:
            return False
        if cmd_def.requires_unlock and not player.has_unlocked(cmd_def.name):
            return False
        if cmd_def.unlock_class and getattr(player, "char_class_name", "").lower() != cmd_def.unlock_class.lower():
            return False
        if player.level < cmd_def.unlock_level: return False
        return True

    def _compute_costs(self, cmd_def, player, raw_text: str) -> Tuple[int, int]:
        base_ap = max(1, len(raw_text.strip()))
        reduction = player.ap_cost_reduction_for_text(raw_text)
        ap = max(1, base_ap - reduction)

        if cmd_def.costs_mp:
            if cmd_def.mp_cost_override is not None:
                mp = max(0, int(cmd_def.mp_cost_override))
            else:
                mp = max(0, cmd_def.base_mp_cost - player.mp_cost_reduction_for(cmd_def.name))
        else:
            mp = 0
        return ap, mp

    def _unknown_feedback(self, verb: str, player, context: CommandContext) -> str:
        if not verb: return "What do you want to do?"
        close = get_close_matches(verb, self._known_commands, n=1, cutoff=0.6)
        if close: return f"I don't know the word '{verb}'. Did you mean '{close[0]}'?"
        return f"I don't know the word '{verb}'."

    def _make_error(self, raw: str, error: str, article: ArticleType) -> ParsedCommand:
        return ParsedCommand(
            raw=raw, intent=None, target_name=None, target_index=None,
            item_name=None, article=article, modifiers=[], ap_cost=0, mp_cost=0,
            valid=False, error=error
        )