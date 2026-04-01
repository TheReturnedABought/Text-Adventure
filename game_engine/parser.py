"""Parser façade.

Legacy entrypoint `parse_command` remains for existing game loop integrations.
New OO syntax engine is exposed through `parse_syntax_command`.
"""

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
    "open": "interact",
}

_SYNTAX_PARSER = SyntaxCombatParser()


def parse_command(user_input: str) -> tuple[str, list[str]]:
    """Legacy parser interface used by the current command routers."""
    parts = user_input.strip().lower().split()
    if not parts:
        return "", []
    cmd = ALIASES.get(parts[0], parts[0])
    args = parts[1:]
    return cmd, args


def parse_syntax_command(user_input: str, *, level: int, in_combat: bool, entities=None):
    """Structured syntax parser for the new language-combat system."""
    context = ParseContext(level=level, in_combat=in_combat, entities=entities or [])
    return _SYNTAX_PARSER.parse(user_input, context)
