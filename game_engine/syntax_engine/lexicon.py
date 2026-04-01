from dataclasses import dataclass


@dataclass(frozen=True)
class PrepositionDef:
    family: str
    tier: int


@dataclass(frozen=True)
class SemanticRoleDef:
    family: str
    tier: int


CANONICAL_VERBS = {
    "attack": ("attack", "strike", "hit"),
    "cut": ("cut", "slash", "carve"),
    "dash": ("dash", "charge", "rush"),
    "mark": ("mark", "tag"),
    "feint": ("feint",),
    "bolt": ("bolt",),
    "spark": ("spark",),
    "flurry": ("flurry",),
    "guard": ("guard", "brace"),
}

# Noun-like command handling: words like "bolt" or "spark" can still act as verbs.
NOUN_LIKE_COMMANDS = {"bolt", "spark", "flurry", "guard", "mark"}

DETERMINERS = {"the", "a", "an"}

PREPOSITIONS = {
    "for": PrepositionDef(family="purpose", tier=1),
    "with": PrepositionDef(family="method", tier=1),
    "into": PrepositionDef(family="impact", tier=1),
    "through": PrepositionDef(family="pierce", tier=1),
    "against": PrepositionDef(family="anti_defense", tier=2),
    "around": PrepositionDef(family="spread_motion", tier=2),
    "beneath": PrepositionDef(family="priority_override", tier=3),
    "across": PrepositionDef(family="area_distribution", tier=3),
}

ADVERBS = {
    "swiftly": "speed",
    "quickly": "speed",
    "rapidly": "speed",
    "brutally": "force",
    "violently": "force",
    "heavily": "force",
    "precisely": "precision",
    "accurately": "precision",
    "carefully": "precision",
    "recklessly": "risk",
    "boldly": "risk",
    "cautiously": "risk",
    "continuously": "flow",
    "repeatedly": "flow",
    "fluidly": "flow",
}

# Added two semantic roles: instrument and location.
SEMANTIC_ROLES = {
    "using": SemanticRoleDef(family="instrument", tier=1),
    "via": SemanticRoleDef(family="instrument", tier=1),
    "near": SemanticRoleDef(family="location", tier=1),
    "behind": SemanticRoleDef(family="location", tier=1),
}
