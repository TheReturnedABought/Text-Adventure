# Text Adventure — Full Project Structure

## Directory layout

```
Text-Adventure/
│
├── main.py                         Entry point
│
├── assets/                         ── ALL game content lives here (no hardcoding) ──
│   ├── rooms/
│   │   ├── _schema.json            Reference schema for room files
│   │   └── *.json                  One file per room
│   ├── items/
│   │   ├── _schema.json            Reference schema for item files
│   │   └── *.json                  One file per equippable item
│   ├── enemies/
│   │   ├── _schema.json            Reference schema for enemy files
│   │   └── *.json                  One file per enemy template
│   ├── classes/
│   │   ├── _schema.json            Reference schema for class files
│   │   └── *.json                  One file per character class
│   ├── abilities/
│   │   └── *.json                  Optional: standalone ability sets
│   └── commands/
│       └── commands.json           Master command + modifier + article table
│
└── game/
    ├── __init__.py
    ├── dice.py                     DiceExpression — parse, roll, scale
    ├── effects.py                  StatusEffect, EffectRegistry, EffectManager
    ├── commands.py                 CommandDefinition, CommandModifier,
    │                               CommandRegistry, UnlockTable
    ├── models.py                   Ability, EquippableItem, CharacterClass,
    │                               EnemyIntent, ParsedCommand, BattleContext, …
    ├── entities.py                 Entity (base), Player, Enemy
    ├── world.py                    Material, MaterialProperties,
    │                               WorldObject, Room, WorldMap
    ├── parser.py                   CommandParser
    ├── combat.py                   CombatController, TurnResult
    ├── exploration.py              ExplorationController, ExplorationResult
    ├── loader.py                   AssetLoader (JSON → objects)
    └── game.py                     TextAdventureGame (orchestrator + run loop)
```

---

## Data flow at startup

```
AssetLoader.load_all_items()       → item_catalog
AssetLoader.load_all_enemy_templates() → enemy_templates
AssetLoader.load_all_classes()     → class_catalog
AssetLoader.load_commands_into(registry) → CommandRegistry populated
AssetLoader.build_world_map(enemy_templates) → WorldMap (rooms wired + enemies spawned)

CommandParser(registry)
ExplorationController(parser, registry, player, world)
CombatController(parser, registry, player, enemies)   ← created per encounter
```

---
# Combat
## AP cost rule (letter count system)

```
ap_cost = len(raw_command.strip())
        - player.ap_cost_reduction_for(intent)   # from equipped items
minimum cost of command = 1 
```

**Example**

| Typed | Letters | Item reduction                      | Final AP |
|-------|---------|-------------------------------------|----------|
| `attack the goblin` | 18 | 0                                   | 18 |
| `block` | 5 | bronze blade: cost of letter b -= 1 | 4 |
| `heavy attack a goblin` | 22 | 0                                   | 22 |
| `smash the door` | 15 | 0                                   | 15 |

---
## mp cost rule (special word count system)

```

```

**Example**

| Typed             | Letters | Item reduction | Final MP | Final AP |
|-------------------|---------|----------------|----------|----------|
| `heal the goblin` | 16      | 0              | 1        | 16       |
| `heal me`         | 6       | 0              | 1        | 6        |
| `heal`            | 4       | 1              | 4        | 4        |
| `fireball`        | 9       | 2              | 8        | 9        |
| `summon`          | 5       | 3              | 6        | 5        |
---
## Combat turn order

```
Player turn:
  player.current_ap = player.max_ap
  while player.current_ap > 0:
    read input → parse → validate AP → resolve action → spend AP
    if enemy ap changes thanks to actions enenmy:
        enemy.plan_turn(player)          # fills active_intents greedily
        plan next round intents for all enemies (displayed as telegraphed intent)
    if AP = 0 OR player types 'wait'/'end' → end_player_turn()

Enemy turn (each enemy, in order):
  for intent in active_intents:
    resolve_enemy_intent(enemy, intent)
    enemy.spend_ap(intent.ap_cost)

round += 1
enemy.plan_turn(player)          # fills active_intents greedily
plan next round intents for all enemies (displayed as telegraphed intent)
```

---

## Article / targeting rule

| Player types | ArticleType | Target selection | Damage  |
|---|---|---|---------|
| `attack` | NONE | random  | -2 flat |
| `attack goblin` | NONE | random from matching enemies | base    |
| `attack the goblin` | SPECIFIC | must resolve to 1 named target | +2 flat |
| `attack a goblin` | GENERIC | random from matching enemies | +3 flat |

# Damage types

Damage has multiple types.

Some enemies are resistant to some types of damage taking half the damage, 

Some enemies are vulnerable to some types of damage taking double damage,

Some are neither,

The types of damage are the following:

- bludgeoning
- piercing
- slashing
- tearing 
- fire
- lightning
- cold
- flood
- force
- acid
- poison 
- necrotic 
- radiant 
- psychic 
- sonic
- force

## aliases for combat commands

Since the length of a combat command determines it's cost aliases can be very powerful,
To amend this damage types are added for each command and each class.


attack for soldier --> slashing
strike for soldier --> half slashing + half bludgeoning
hit for soldier --> half bludgeoning

---

## Material interaction matrix for physics simulation

Rooms and objects can be made up of diffrent materials and react diffrently to damage types.
If you attack an enemy there is a chance based on the room type to apply an effect to the room.

for example you attack a goblin with a lightning attack in a metal room there is a 90% chance that you get shocked and take damage too.
for example you attack a goblin with a lightning attack and there is a metal object/item there is a 10% chance that it gets shocked (but if you aren't holding it you do not get shocked).

Items and rooms that ignite burn over time and become charcoal. If you stand in a burning room you take fire damage.

Not all results are permanent, some are temporary, some effects are negative for you some would be positive.

| type \ material | Wood       | Metal                | Stone                | Water              | Glass                         | Ice        | Flesh              | Bone         | Cloth        | Crystal              | Sand         | Plant             |
| --------------- | ---------- |----------------------| -------------------- | ------------------ | ----------------------------- | ---------- | ------------------ | ------------ | ------------ | -------------------- | ------------ | ----------------- |
| **Fire**        | Ignites    | Heats                | —                    | Extinguished       | Cracks/shatters (heat stress) | Melts      | Burns              | Burns (slow) | Ignites fast | May fracture         | —            | Ignites rapidly   |
| **Lightning**   | —          | Conducts (spreads)   | —                    | Conducts (spreads) | —                             | —          | Shocks             | —            | —            | Amplifies / refracts | —            | —                 |
| **Cold**        | Brittle    | Brittle              | —                    | Freezes            | Becomes brittle               | Reinforces | Slows              | Brittle      | Stiffens     | Stabilizes           | Compacts     | Slows growth      |
| **Flood**       | Floats     | Sinks                | Sinks                | —                  | Sinks                         | Floats     | Pushes             | Sinks        | Floats       | Sinks                | Saturates    | Uproots           |
| **Slashing**    | Cuts       | —                    | Sparks → fire chance | —                  | Shatters                      | Cuts       | Lacerates          | Chips        | Tears        | Scratches            | Displaces    | Cuts              |
| **Bludgeoning** | Cracks     | Dents (noise)        | Chips/cracks         | —                  | Shatters                      | Shatters   | Bruises            | Cracks       | —            | Cracks               | Compacts     | Crushes           |
| **Piercing**    | Penetrates | —                    | —                    | —                  | Shatters                      | Pierces    | Impales            | Penetrates   | Pierces      | —                    | Pass-through | Pierces           |
| **Tearing**     | Splinters  | —                    | —                    | —                  | —                             | —          | Severe trauma      | Splits       | Rips         | —                    | Disrupts     | Rips              |
| **Acid**        | Corrodes   | Corrodes (slow/fast) | Erodes               | Dilutes            | Etches                        | Melts      | Dissolves          | Weakens      | Dissolves    | Etches               | Neutralizes  | Dissolves         |
| **Poison**      | —          | —                    | —                    | Contaminates       | —                             | —          | Affects            | —            | —            | —                    | —            | Affects           |
| **Necrotic**    | Decays     | —                    | —                    | Stagnates          | —                             | —          | Rot                | Weakens      | Rot          | —                    | —            | Wilts             |
| **Radiant**     | Purifies   | Heats                | —                    | Purifies           | Refracts                      | Melts      | Burns/cleanses     | —            | Cleanses     | Amplifies            | —            | Stimulates growth |
| **Psychic**     | —          | —                    | —                    | —                  | —                             | —          | Mental dmg         | —            | —            | Resonates            | —            | —                 |
| **Sonic**       | Vibrates   | Resonates            | Cracks               | Ripples            | Shatters                      | Cracks     | Disorients         | —            | Tears        | Resonates strongly   | Displaces    | Rustles           |
| **Force**       | Pushes     | Pushes               | Pushes               | Displaces          | Shatters                      | Shatters   | Impacts            | Impacts      | Pushes       | Shatters             | Scatters     | Pushes            |

---

# Adding content checklist

**New room**: create `assets/rooms/<id>.json`, reference exits by room id.  
**New item**: create `assets/items/<id>.json`, reference in class `starting_items` or loot table.  
**New enemy**: create `assets/enemies/<id>.json`, reference in room `enemy_spawns`.  
**New class**: create `assets/classes/<id>.json`, populate `level_unlocks`.  
**New command**: add entry to `assets/commands/commands.json`.  
**New status effect**: subclass `StatusEffect` in `game/effects.py`, register in `EffectRegistry`.  
**New ability execute**: wire callback in `AbilityRegistry` (to be built in `game/abilities.py`).