"""Parser façade.

Legacy entrypoint `parse_command` remains for existing game loop integrations.
New OO syntax engine is exposed through `parse_syntax_command`.

The legacy parser is intentionally "Zork-like":
- understands short aliases (`n`, `x statue`, `inv`)
- handles phrasal verbs (`pick up`, `look at`, `talk to`)
- strips lightweight filler words and determiners
- normalizes movement phrasing (`go north`, `walk to east`)
"""

import re
import shlex

from game_engine.syntax_engine import ParseContext, SyntaxCombatParser

ALIASES = {
    "n": "north",
    "s": "south",
    "e": "east",
    "w": "west",
    "i": "inventory",
    "l": "look",
    "h": "help",
    "g": "go",
    "j": "journal",
    "m": "map",
    "x": "examine",
    "inspect": "examine",
    "?": "help",
    "inv": "inventory",
    "get": "take",
    "pickup": "take",
    "grab": "take",
    "talk": "interact",
    "speak": "interact",
}

_DIRECTIONS = {"north", "south", "east", "west", "up", "down"}
_DETERMINERS = {"the", "a", "an"}
_FILLER = {"to", "at", "toward", "towards", "into", "on", "with", "please"}
_CLAUSE_BREAK = {"then", ";", ","}
_PUNCT_RE = re.compile(r"[^\w\s'?,;-]")

_PHRASAL_VERBS = {
    ("pick", "up"): "take",
    ("look", "at"): "examine",
    ("listen", "to"): "listen",
    ("talk", "to"): "interact",
    ("speak", "to"): "interact",
    ("go", "to"): "move",
    ("walk", "to"): "move",
}

_SYNTAX_PARSER = SyntaxCombatParser()
_EXPLICIT_COMMANDS = {
    "move", "go", "walk", "north", "south", "east", "west", "up", "down",
    "take", "drop", "inventory", "relics", "use", "listen", "interact",
    "examine", "look", "help", "map", "journal", "end", "done", "pass",
    "attack", "heal", "block", "quit", "exit",
}


def _tokenize_legacy(user_input: str) -> list[str]:
    raw = user_input.strip().lower()
    if not raw:
        return []
    cleaned = _PUNCT_RE.sub(" ", raw)
    try:
        tokens = shlex.split(cleaned)
    except ValueError:
        tokens = cleaned.split()
    return [t for t in tokens if t]


def _normalize_legacy(tokens: list[str]) -> tuple[str, list[str]]:
    # Single-clause parse for compatibility with one-command game loop.
    for i, tok in enumerate(tokens):
        if tok in _CLAUSE_BREAK:
            tokens = tokens[:i]
            break
    if not tokens:
        return "", []

    # Phrasal verb normalization (e.g. "pick up relic" -> take relic).
    if len(tokens) >= 2 and (tokens[0], tokens[1]) in _PHRASAL_VERBS:
        cmd = _PHRASAL_VERBS[(tokens[0], tokens[1])]
        args = tokens[2:]
    else:
        cmd = ALIASES.get(tokens[0], tokens[0])
        args = tokens[1:]

    # Direction shorthand ("go north", "walk east") keeps existing router behavior.
    if cmd in {"go", "move", "walk"} and args:
        first = ALIASES.get(args[0], args[0])
        if first in _DIRECTIONS:
            return first, args[1:]

    # "north"/"south" as direct commands.
    if cmd in _DIRECTIONS:
        return cmd, args

    # Zork-like object phrase cleanup ("examine the chest" -> examine chest).
    cleaned_args = [a for a in args if a not in _DETERMINERS and a not in _FILLER]
    if cmd in {"take", "drop", "use", "examine", "interact"}:
        args = cleaned_args

    return cmd, args


def parse_command(user_input: str) -> tuple[str, list[str]]:
    """Legacy parser interface used by the current command routers."""
    tokens = _tokenize_legacy(user_input)
    return _normalize_legacy(tokens)


def parse_puzzle_answer(user_input: str) -> list[str] | None:
    """Return answer tokens when the input is likely a free-form puzzle answer.

    Heuristic:
    - If the normalized lead token is an explicit game command, it's not an answer.
    - Otherwise, treat the full tokenized input as candidate answer text.
    """
    tokens = _tokenize_legacy(user_input)
    if not tokens:
        return None
    # Backward compatibility: allow old "solve <answer>" input.
    if tokens[0] == "solve":
        return tokens[1:] if len(tokens) > 1 else None
    command, _args = _normalize_legacy(tokens)
    if command in _EXPLICIT_COMMANDS or command in ALIASES.values() or command in _DIRECTIONS:
        return None
    return tokens


def parse_syntax_command(user_input: str, *, level: int, in_combat: bool, entities=None):
    """Structured syntax parser for the new language-combat system."""
    context = ParseContext(level=level, in_combat=in_combat, entities=entities or [])
    return _SYNTAX_PARSER.parse(user_input, context)
