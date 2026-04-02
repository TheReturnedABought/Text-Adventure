from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING

"""Command registry + unlock table layer.

The parser and controllers depend on these runtime helpers to resolve aliases,
enforce unlock/context rules, and compute AP costs from raw command text.
"""
if TYPE_CHECKING:
    from game.entities import Player


class CommandContext(Enum):
    COMBAT = auto()
    WORLD = auto()
    ANY = auto()


@dataclass
class CommandModifier:
    """A keyword that can prefix a command verb to alter how it resolves."""

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
    """Defines what article words imply and their mechanical effects."""

    specific_words: list[str] = field(default_factory=lambda: ["the"])
    generic_words: list[str] = field(default_factory=lambda: ["a", "an"])
    generic_flat_bonus: int = 3
    specific_flat_bonus: int = 0


@dataclass
class CommandDefinition:
    """Full definition of one learnable/unlockable player command."""

    name: str
    aliases: list[str]
    description: str
    ap_cost_override: int | None = None
    mp_cost_override: int | None = None
    costs_mp: bool = False
    base_dice: str | None = None
    unlock_class: str | None = None
    unlock_level: int = 0
    valid_contexts: list[CommandContext] = field(
        default_factory=lambda: [CommandContext.COMBAT, CommandContext.WORLD]
    )
    modifiers_allowed: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    world_use_hint: str | None = None

    @property
    def intent(self) -> str:
        return self.name

    @property
    def allowed_contexts(self) -> list[CommandContext]:
        return self.valid_contexts

    @property
    def requires_unlock(self) -> bool:
        return self.unlock_level > 0 or self.unlock_class is not None


class CommandRegistry:
    """Central store for all CommandDefinitions and CommandModifiers."""

    def __init__(self) -> None:
        self._commands: dict[str, CommandDefinition] = {}
        self._alias_map: dict[str, str] = {}
        self._modifiers: dict[str, CommandModifier] = {}
        self.article_rule: ArticleRule = ArticleRule()

    def register_command(self, cmd: CommandDefinition) -> None:
        key = cmd.name.strip().lower()
        self._commands[key] = cmd
        self._alias_map[key] = key
        for alias in cmd.aliases:
            alias_key = alias.strip().lower()
            if alias_key:
                self._alias_map[alias_key] = key

    def register_modifier(self, mod: CommandModifier) -> None:
        self._modifiers[mod.name.strip().lower()] = mod

    def load_from_dict(self, data: dict) -> None:
        for raw in data.get("commands", []):
            contexts = [self._coerce_context(c) for c in raw.get("valid_contexts", [])]
            valid_contexts = [c for c in contexts if c is not None] or [CommandContext.COMBAT, CommandContext.WORLD]
            self.register_command(
                CommandDefinition(
                    name=str(raw.get("name", "")).strip().lower(),
                    aliases=[str(a).strip().lower() for a in raw.get("aliases", []) if str(a).strip()],
                    description=str(raw.get("description", "")).strip(),
                    ap_cost_override=raw.get("ap_cost_override"),
                    mp_cost_override=raw.get("mp_cost_override"),
                    costs_mp=bool(raw.get("costs_mp", False)),
                    base_dice=raw.get("base_dice"),
                    unlock_class=raw.get("unlock_class"),
                    unlock_level=int(raw.get("unlock_level", 0) or 0),
                    valid_contexts=valid_contexts,
                    modifiers_allowed=[str(m).strip().lower() for m in raw.get("modifiers_allowed", [])],
                    tags=[str(t).strip().lower() for t in raw.get("tags", [])],
                    world_use_hint=raw.get("world_use_hint"),
                )
            )

        for raw in data.get("modifiers", []):
            contexts = [self._coerce_context(c) for c in raw.get("valid_contexts", [])]
            valid_contexts = [c for c in contexts if c is not None] or [CommandContext.ANY]
            self.register_modifier(
                CommandModifier(
                    name=str(raw.get("name", "")).strip().lower(),
                    description=str(raw.get("description", "")).strip(),
                    dice_count_mult=float(raw.get("dice_count_mult", 1.0) or 1.0),
                    dice_sides_mult=float(raw.get("dice_sides_mult", 1.0) or 1.0),
                    flat_bonus=int(raw.get("flat_bonus", 0) or 0),
                    ap_cost_flat=int(raw.get("ap_cost_flat", 0) or 0),
                    unlock_class=raw.get("unlock_class"),
                    unlock_level=int(raw.get("unlock_level", 0) or 0),
                    valid_contexts=valid_contexts,
                    tags=[str(t).strip().lower() for t in raw.get("tags", [])],
                )
            )

        article_data = data.get("articles") or {}
        if article_data:
            self.article_rule = ArticleRule(
                specific_words=[w.lower() for w in article_data.get("specific_words", ["the"])],
                generic_words=[w.lower() for w in article_data.get("generic_words", ["a", "an"])],
                generic_flat_bonus=int(article_data.get("generic_flat_bonus", 3) or 0),
                specific_flat_bonus=int(article_data.get("specific_flat_bonus", 0) or 0),
            )

    def get_command(self, verb: str) -> CommandDefinition | None:
        key = self._alias_map.get(str(verb).strip().lower())
        return self._commands.get(key) if key else None

    def get_modifier(self, word: str) -> CommandModifier | None:
        return self._modifiers.get(str(word).strip().lower())

    def all_commands(self) -> list[CommandDefinition]:
        return list(self._commands.values())

    def all_intents(self) -> list[str]:
        return list(self._commands.keys())

    def all_modifier_names(self) -> list[str]:
        return list(self._modifiers.keys())

    def available_for(self, player: "Player", context: CommandContext) -> list[CommandDefinition]:
        return [
            cmd for cmd in self.all_commands()
            if self.is_available_for(player, cmd.name, context)
        ]

    def is_available_for(self, player: "Player", command_name: str,
                         context: CommandContext) -> bool:
        cmd = self.get_command(command_name)
        if cmd is None:
            return False
        if context not in (CommandContext.ANY,) and CommandContext.ANY not in cmd.valid_contexts and context not in cmd.valid_contexts:
            return False
        if cmd.unlock_class is not None and getattr(player, "char_class_name", "").lower() != cmd.unlock_class.lower():
            return False
        if getattr(player, "level", 1) < cmd.unlock_level:
            return False
        return True

    def ap_cost_for(self, raw_command: str, cmd: CommandDefinition,
                    player: "Player") -> int:
        base = cmd.ap_cost_override if cmd.ap_cost_override is not None else len(raw_command.strip())
        reduced = base - player.ap_cost_reduction_for(cmd.name)
        return max(1, int(reduced))

    @staticmethod
    def _coerce_context(raw: str | CommandContext | None) -> CommandContext | None:
        if isinstance(raw, CommandContext):
            return raw
        if raw is None:
            return None
        val = str(raw).strip().upper()
        return CommandContext[val] if val in CommandContext.__members__ else None


class UnlockTable:
    """Maps (class_name, level) → list of command names newly unlocked."""

    def __init__(self) -> None:
        self._table: dict[str, dict[int, list[str]]] = {}
        self._choice_table: dict[str, dict[int, list[list[str]]]] = {}

    def add_unlock(self, class_name: str, level: int, command_name: str) -> None:
        cls = class_name.strip().lower()
        self._table.setdefault(cls, {}).setdefault(level, [])
        if command_name not in self._table[cls][level]:
            self._table[cls][level].append(command_name)

    def add_choice_unlock(self, class_name: str, level: int,
                          choices: list[str]) -> None:
        cls = class_name.strip().lower()
        self._choice_table.setdefault(cls, {}).setdefault(level, []).append(list(choices))

    def get_unlocks(self, class_name: str, level: int) -> list[str]:
        return list(self._table.get(class_name.strip().lower(), {}).get(level, []))

    def get_choice_unlocks(self, class_name: str, level: int) -> list[list[str]]:
        return [list(group) for group in self._choice_table.get(class_name.strip().lower(), {}).get(level, [])]

    def all_unlocked_by(self, class_name: str, up_to_level: int) -> list[str]:
        out: list[str] = []
        for lvl, names in sorted(self._table.get(class_name.strip().lower(), {}).items()):
            if lvl <= up_to_level:
                out.extend(names)
        return out

    def load_from_dict(self, data: dict) -> None:
        for cls_name, payload in data.items():
            for lvl_raw, names in (payload.get("level_unlocks", {}) or {}).items():
                lvl = int(lvl_raw)
                for name in names:
                    self.add_unlock(cls_name, lvl, str(name))
            for lvl_raw, groups in (payload.get("choice_unlocks", {}) or {}).items():
                lvl = int(lvl_raw)
                for group in groups:
                    self.add_choice_unlock(cls_name, lvl, [str(v) for v in group])
