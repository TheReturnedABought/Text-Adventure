# Syntax Combat System Design (Revised)

## Core Rules
- Command prompt is the combat system.
- AP cost uses token letter count (spaces excluded).
- Longer, more structured sentences are more efficient and more targeted.
- Short commands are general and lower-resolution.

## Semantic Layers
1. Verb
2. Determiner
3. Preposition
4. Adverb
5. Semantic role (instrument)
6. Semantic role (location)

## Determiner Rules
- `the`: explicit lock targeting.
- `a` / `an`: adds structure but does not hard-lock target.

## Unlock Schedule (all classes)
- Determiners: unlocked from start.
- Prepositions tier 1: level 3.
- Prepositions tier 2: level 6.
- Prepositions tier 3: level 7.

## Multi-target Grammar
Examples:
- `flurry the goblin and the goblin archer and the wizard`
- parser extracts each locked noun phrase in sequence.

## Duplicate Name Targeting
If multiple entities share the same display name and `the` is used:
- parser selects deterministic first match
- parser emits warning with selected entity id for transparency

## Outside Combat Behavior
Combat commands may still parse while outside combat.
If a targeted entity is a room object, parser warns that using combat syntax here may not be a good idea unless explicitly supported by game rules.

## Noun-like Commands
Tokens like `bolt` and `spark` are interpreted as verbs when used command-first.
