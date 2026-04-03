"""Command registry – stores all commands, modifiers, and unlock rules.

This module defines:
- CommandDefinition: structure for a single command (attack, go, etc.)
- CommandModifier: alters command behaviour (heavy, quick)
- CommandRegistry: central storage with alias resolution
- UnlockTable: tracks class-based command unlocks
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from game.entities import Player


class CommandContext(Enum):
    """Where a command can be used."""
    COMBAT = auto()
    WORLD = auto()
    ANY = auto()


@dataclass
class CommandModifier:
    """Modifier like 'heavy' – changes dice, AP cost, etc."""
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


@dataclass
class ArticleRule:
    """Rules for articles 'the', 'a', 'an'."""
    specific_words: list[str] = field(default_factory=lambda: ["the"])
    generic_words: list[str] = field(default_factory=lambda: ["a", "an"])
    generic_flat_bonus: int = 3
    specific_flat_bonus: int = 0


@dataclass
class CommandDefinition:
    """A single command (attack, go, look, ...)."""
    name: str
    aliases: list[str]
    description: str
    ap_cost_override: int | None = None
    mp_cost_override: int | None = None
    costs_mp: bool = False
    base_dice: str | None = None
    unlock_class: str | None = None
    unlock_level: int = 0
    valid_contexts: list[CommandContext] = field(default_factory=lambda: [CommandContext.COMBAT, CommandContext.WORLD])
    modifiers_allowed: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    world_use_hint: str | None = None
    base_ap_cost: int = 0
    base_mp_cost: int = 0
    unlocked_by_default: bool = False          # If True, available to any class at level 1

    @property
    def intent(self) -> str:
        return self.name

    @property
    def requires_unlock(self) -> bool:
        return self.unlock_level > 0 or self.unlock_class is not None


class CommandRegistry:
    """Holds all commands, maps aliases, tracks modifiers."""

    def __init__(self) -> None:
        self._commands: dict[str, CommandDefinition] = {}
        self._alias_map: dict[str, str] = {}
        self._modifiers: dict[str, CommandModifier] = {}
        self.article_rule: ArticleRule = ArticleRule()

    def register_command(self, cmd: CommandDefinition) -> None:
        key = cmd.name.lower()
        self._commands[key] = cmd
        self._alias_map[key] = key
        for alias in cmd.aliases:
            alias_key = alias.lower()
            if alias_key:
                self._alias_map[alias_key] = key

    def register_modifier(self, mod: CommandModifier) -> None:
        self._modifiers[mod.name.lower()] = mod

    def load_from_dict(self, data: dict) -> None:
        """Load commands, modifiers, articles from parsed JSON."""
        # Commands
        for raw in data.get("commands", []):
            contexts = [self._coerce_context(c) for c in raw.get("valid_contexts", [])]
            valid_contexts = [c for c in contexts if c] or [CommandContext.COMBAT, CommandContext.WORLD]
            self.register_command(CommandDefinition(
                name=raw.get("name", "").strip().lower(),
                aliases=[a.strip().lower() for a in raw.get("aliases", []) if a.strip()],
                description=raw.get("description", "").strip(),
                ap_cost_override=raw.get("ap_cost_override"),
                mp_cost_override=raw.get("mp_cost_override"),
                costs_mp=bool(raw.get("costs_mp", False)),
                base_dice=raw.get("base_dice"),
                unlock_class=raw.get("unlock_class"),
                unlock_level=int(raw.get("unlock_level", 0) or 0),
                valid_contexts=valid_contexts,
                modifiers_allowed=[m.lower() for m in raw.get("modifiers_allowed", [])],
                tags=[t.lower() for t in raw.get("tags", [])],
                world_use_hint=raw.get("world_use_hint"),
                base_ap_cost=int(raw.get("base_ap_cost", 6)),
                base_mp_cost=int(raw.get("base_mp_cost", 0)),
                unlocked_by_default=bool(raw.get("unlocked_by_default", False)),
            ))

        # Modifiers
        for raw in data.get("modifiers", []):
            contexts = [self._coerce_context(c) for c in raw.get("valid_contexts", [])]
            valid_contexts = [c for c in contexts if c] or [CommandContext.ANY]
            self.register_modifier(CommandModifier(
                name=raw.get("name", "").strip().lower(),
                description=raw.get("description", "").strip(),
                dice_count_mult=float(raw.get("dice_count_mult", 1.0) or 1.0),
                dice_sides_mult=float(raw.get("dice_sides_mult", 1.0) or 1.0),
                flat_bonus=int(raw.get("flat_bonus", 0) or 0),
                ap_cost_flat=int(raw.get("ap_cost_flat", 0) or 0),
                unlock_class=raw.get("unlock_class"),
                unlock_level=int(raw.get("unlock_level", 0) or 0),
                valid_contexts=valid_contexts,
                tags=[t.lower() for t in raw.get("tags", [])],
            ))

        # Articles
        art = data.get("articles", {})
        if art:
            self.article_rule = ArticleRule(
                specific_words=[w.lower() for w in art.get("specific_words", ["the"])],
                generic_words=[w.lower() for w in art.get("generic_words", ["a", "an"])],
                generic_flat_bonus=int(art.get("generic_flat_bonus", 3) or 0),
                specific_flat_bonus=int(art.get("specific_flat_bonus", 0) or 0),
            )

    def get_command(self, verb: str) -> CommandDefinition | None:
        key = self._alias_map.get(verb.lower())
        return self._commands.get(key) if key else None

    def get_modifier(self, word: str) -> CommandModifier | None:
        return self._modifiers.get(word.lower())

    def all_commands(self) -> list[CommandDefinition]:
        return list(self._commands.values())

    def all_intents(self) -> list[str]:
        return list(self._commands.keys())

    def available_for(self, player: "Player", context: CommandContext) -> list[CommandDefinition]:
        return [c for c in self.all_commands() if self.is_available_for(player, c.name, context)]

    def is_available_for(self, player: "Player", command_name: str, context: CommandContext) -> bool:
        cmd = self.get_command(command_name)
        if not cmd:
            return False
        if cmd.unlocked_by_default:
            return True
        if context not in (CommandContext.ANY,) and CommandContext.ANY not in cmd.valid_contexts and context not in cmd.valid_contexts:
            return False
        if cmd.unlock_class and getattr(player, "char_class_name", "").lower() != cmd.unlock_class.lower():
            return False
        if getattr(player, "level", 1) < cmd.unlock_level:
            return False
        return True

    @staticmethod
    def _coerce_context(raw):
        if isinstance(raw, CommandContext):
            return raw
        if raw is None:
            return None
        val = str(raw).strip().upper()
        return CommandContext[val] if val in CommandContext.__members__ else None


class UnlockTable:
    """Tracks which commands a class unlocks at each level."""

    def __init__(self):
        self._level_unlocks: dict[str, dict[int, list[str]]] = {}
        self._choice_unlocks: dict[str, dict[int, list[list[str]]]] = {}

    def add_unlock(self, class_name: str, level: int, command: str) -> None:
        cls = class_name.lower()
        self._level_unlocks.setdefault(cls, {}).setdefault(level, []).append(command)

    def add_choice_unlock(self, class_name: str, level: int, choices: list[str]) -> None:
        cls = class_name.lower()
        self._choice_unlocks.setdefault(cls, {}).setdefault(level, []).append(list(choices))

    def get_unlocks(self, class_name: str, level: int) -> list[str]:
        return self._level_unlocks.get(class_name.lower(), {}).get(level, [])

    def get_choice_unlocks(self, class_name: str, level: int) -> list[list[str]]:
        return self._choice_unlocks.get(class_name.lower(), {}).get(level, [])

    def load_from_dict(self, data: dict) -> None:
        for cls, payload in data.items():
            for lvl_str, cmds in payload.get("level_unlocks", {}).items():
                lvl = int(lvl_str)
                for cmd in cmds:
                    self.add_unlock(cls, lvl, cmd)
            for lvl_str, groups in payload.get("choice_unlocks", {}).items():
                lvl = int(lvl_str)
                for group in groups:
                    self.add_choice_unlock(cls, lvl, group)