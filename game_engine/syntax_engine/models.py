from dataclasses import dataclass, field


@dataclass(frozen=True)
class SyntaxUnlocks:
    determiners: bool = True
    prepositions_tier: int = 0
    adverbs: bool = True
    semantic_roles_tier: int = 0


@dataclass(frozen=True)
class ParsedTarget:
    raw_text: str
    canonical_name: str
    target_id: str | None = None
    role: str = "direct"


@dataclass
class ParsedSyntaxCommand:
    raw_input: str
    verb: str
    ap_letters_cost: int
    determiners: list[str] = field(default_factory=list)
    prepositions: list[str] = field(default_factory=list)
    adverbs: list[str] = field(default_factory=list)
    semantic_roles: list[str] = field(default_factory=list)
    direct_targets: list[ParsedTarget] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_precise_targeting(self) -> bool:
        return "the" in self.determiners

    @property
    def efficiency_score(self) -> float:
        """Longer + structurally richer commands are more efficient in this system."""
        structure_bonus = (
            len(self.prepositions) * 0.2
            + len(self.adverbs) * 0.15
            + len(self.semantic_roles) * 0.2
            + (0.35 if self.is_precise_targeting else 0)
        )
        length_bonus = min(0.6, len(self.raw_input.replace(" ", "")) / 80.0)
        return round(1.0 + structure_bonus + length_bonus, 2)


@dataclass(frozen=True)
class EntityRef:
    entity_id: str
    display_name: str
    aliases: tuple[str, ...]
    kind: str  # enemy | player | room_object | npc


@dataclass
class ParseContext:
    level: int
    in_combat: bool
    entities: list[EntityRef] = field(default_factory=list)
