from __future__ import annotations

from game.models import ParsedCommand


class CommandParser:
    """Parser-first combat command resolver.

    Expand this class to support richer grammar, synonyms, and disambiguation.
    """

    def parse(self, raw_command: str) -> ParsedCommand:
        command = raw_command.strip().lower()
        if not command:
            return ParsedCommand(intent="invalid", raw=raw_command)

        tokens = command.split()
        verb = tokens[0]

        if verb in {"attack", "hit", "strike"}:
            target = tokens[1] if len(tokens) > 1 else None
            return ParsedCommand(intent="attack", target=target, raw=raw_command)

        if verb in {"equip", "wear"}:
            item = " ".join(tokens[1:]) if len(tokens) > 1 else None
            return ParsedCommand(intent="equip", item_name=item, raw=raw_command)

        if verb in {"ability", "cast", "use"}:
            item = " ".join(tokens[1:]) if len(tokens) > 1 else None
            return ParsedCommand(intent="ability", item_name=item, raw=raw_command)

        if verb in {"help", "?"}:
            return ParsedCommand(intent="help", raw=raw_command)

        return ParsedCommand(intent="invalid", raw=raw_command)
