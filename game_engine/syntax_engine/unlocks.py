from .models import SyntaxUnlocks


class SyntaxProgression:
    """Single source of truth for syntax feature unlocks for all classes."""

    @staticmethod
    def from_level(level: int) -> SyntaxUnlocks:
        preposition_tier = 0
        if level >= 3:
            preposition_tier = 1
        if level >= 6:
            preposition_tier = 2
        if level >= 7:
            preposition_tier = 3

        semantic_roles_tier = 1 if level >= 3 else 0

        return SyntaxUnlocks(
            determiners=True,
            prepositions_tier=preposition_tier,
            adverbs=True,
            semantic_roles_tier=semantic_roles_tier,
        )
