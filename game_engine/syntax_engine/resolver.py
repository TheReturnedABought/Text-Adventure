from collections import defaultdict

from .models import EntityRef, ParseContext, ParsedTarget


class TargetResolver:
    def __init__(self, context: ParseContext):
        self.context = context
        self._index = self._build_index(context.entities)

    @staticmethod
    def _build_index(entities: list[EntityRef]) -> dict[str, list[EntityRef]]:
        index: dict[str, list[EntityRef]] = defaultdict(list)
        for entity in entities:
            names = {entity.display_name.lower(), *[alias.lower() for alias in entity.aliases]}
            for key in names:
                index[key].append(entity)
        return index

    def resolve_phrase_targets(self, phrases: list[str], precise: bool) -> tuple[list[ParsedTarget], list[str]]:
        targets: list[ParsedTarget] = []
        warnings: list[str] = []

        for phrase in phrases:
            query = phrase.strip().lower()
            if not query:
                continue

            candidates = self._index.get(query, [])
            if not candidates:
                targets.append(ParsedTarget(raw_text=phrase, canonical_name=query, target_id=None))
                warnings.append(f"No visible target matched '{phrase}'.")
                continue

            # Exact targeting with 'the': choose deterministic first living/first listed candidate.
            if precise:
                choice = candidates[0]
                targets.append(
                    ParsedTarget(
                        raw_text=phrase,
                        canonical_name=choice.display_name.lower(),
                        target_id=choice.entity_id,
                    )
                )
                if len(candidates) > 1:
                    warnings.append(
                        f"Multiple '{phrase}' targets found; defaulted to {choice.entity_id}."
                    )
            else:
                # Non-precise: leave unresolved so combat rules may randomize valid targets.
                targets.append(ParsedTarget(raw_text=phrase, canonical_name=query, target_id=None))

        if not self.context.in_combat:
            for t in targets:
                if t.target_id:
                    entity = next((e for e in self.context.entities if e.entity_id == t.target_id), None)
                    if entity and entity.kind == "room_object":
                        warnings.append(
                            f"Target '{entity.display_name}' is a room object; combat command may be a bad idea here."
                        )

        return targets, warnings
