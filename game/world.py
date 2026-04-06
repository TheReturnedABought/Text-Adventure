"""World map, rooms, objects, materials, damage types, and interactions.

Line of sight determines visibility between rooms.
Enemies can move between rooms and join/leave combat based on LOS.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from game.entities import Enemy, Player


class Material(Enum):
    WOOD = "wood"
    STONE = "stone"
    METAL = "metal"
    WATER = "water"
    GLASS = "glass"
    FLESH = "flesh"
    CLOTH = "cloth"
    ICE = "ice"
    EARTH = "earth"


class DamageType(Enum):
    BLUDGEONING = "bludgeoning"
    PIERCING = "piercing"
    SLASHING = "slashing"
    TEARING = "tearing"
    FIRE = "fire"
    LIGHTNING = "lightning"
    COLD = "cold"
    FLOOD = "flood"
    FORCE = "force"
    ACID = "acid"
    POISON = "poison"
    NECROTIC = "necrotic"
    RADIANT = "radiant"
    PSYCHIC = "psychic"
    SONIC = "sonic"


@dataclass(frozen=True)
class MaterialInteraction:
    summary: str
    damage_multiplier: float = 1.0
    applies_status: str | None = None
    spreads: bool = False


@dataclass
class MaterialProperties:
    name: str
    burns: bool = False
    conducts_electricity: bool = False
    floats: bool = False
    blocks_sight: bool = True
    breaks_on_smash: bool = False
    conducts_cold: bool = False

    @classmethod
    def for_material(cls, material: Material) -> "MaterialProperties":
        lookup = {
            Material.WOOD: cls("wood", burns=True, breaks_on_smash=True),
            Material.STONE: cls("stone"),
            Material.METAL: cls("metal", conducts_electricity=True, conducts_cold=True),
            Material.WATER: cls("water", conducts_electricity=True, blocks_sight=False),
            Material.GLASS: cls("glass", breaks_on_smash=True, blocks_sight=False),
            Material.FLESH: cls("flesh", burns=True, blocks_sight=False),
            Material.CLOTH: cls("cloth", burns=True, breaks_on_smash=True, blocks_sight=False),
            Material.ICE: cls("ice", conducts_cold=True, breaks_on_smash=True, blocks_sight=False),
            Material.EARTH: cls("earth", breaks_on_smash=True, blocks_sight=False),
        }
        return lookup.get(material, cls(material.value))


# Material interaction matrix (simplified; expand as needed)
MATERIAL_INTERACTIONS: dict[DamageType, dict[Material, MaterialInteraction]] = {
    DamageType.FIRE: {
        Material.WOOD: MaterialInteraction("ignites", 1.25, "burning"),
        Material.METAL: MaterialInteraction("heats", 1.0),
        Material.WATER: MaterialInteraction("extinguished", 0.2),
        Material.GLASS: MaterialInteraction("cracks", 1.15),
        Material.ICE: MaterialInteraction("melts", 1.5),
        Material.FLESH: MaterialInteraction("burns", 1.2, "burning"),
        Material.CLOTH: MaterialInteraction("ignites", 1.3, "burning"),
    },
    DamageType.LIGHTNING: {
        Material.METAL: MaterialInteraction("conducts", 1.2, spreads=True),
        Material.WATER: MaterialInteraction("conducts", 1.2, spreads=True),
        Material.FLESH: MaterialInteraction("shocks", 1.1, "shocked"),
    },
    # ... add other damage types similarly
}


def resolve_material_interaction(damage_type: DamageType, material: Material) -> MaterialInteraction:
    table = MATERIAL_INTERACTIONS.get(damage_type, {})
    return table.get(material, MaterialInteraction("has little effect", 1.0))


def coerce_damage_type(raw: str) -> DamageType | None:
    text = str(raw or "").strip().lower()
    return next((dt for dt in DamageType if dt.value == text), None)


@dataclass
class WorldObject:
    id: str
    name: str
    description: str
    material: Material = Material.WOOD
    is_container: bool = False
    is_moveable: bool = False
    is_locked: bool = False
    key_item_id: str | None = None
    hidden: bool = False
    reveals: list[str] = field(default_factory=list)
    on_interact: dict[str, str] = field(default_factory=dict)
    required_commands: dict[str, dict] = field(default_factory=dict)
    contents: list["WorldObject"] = field(default_factory=list)
    items_inside: list[str] = field(default_factory=list)

    def can_interact_with(self, command_name: str, player: "Player") -> tuple[bool, str]:
        if self.hidden:
            return False, "You don't see that here."
        if self.is_locked and command_name not in {"unlock", "open"}:
            return False, f"The {self.name} is locked."
        req = self.required_commands.get(command_name, {})
        if player.level < req.get("min_level", 0):
            return False, f"You need level {req['min_level']} to do that."
        class_id = getattr(getattr(player, "char_class", None), "id", None)
        if req.get("class") and class_id != req["class"]:
            return False, "Your class cannot do that."
        return True, ""

    def interact(self, command_name: str, player: "Player", room: "Room") -> tuple[str, list["WorldObject"]]:
        if command_name == "open" and self.is_locked:
            return f"The {self.name} is locked.", []
        if command_name == "unlock":
            if not self.is_locked:
                return f"The {self.name} is already unlocked.", []
            if self.key_item_id and not player.find_in_inventory(self.key_item_id):
                return f"You need {self.key_item_id} to unlock the {self.name}.", []
            self.is_locked = False
            return f"You unlock the {self.name}.", []
        narration = self.on_interact.get(command_name, f"You {command_name} the {self.name}.")
        revealed = []
        for obj_id in self.reveals:
            if obj_id in room.objects:
                room.objects[obj_id].hidden = False
                revealed.append(room.objects[obj_id])
        return narration, revealed

    def examine(self) -> str:
        bits = [self.description]
        if self.is_locked:
            bits.append("It is locked.")
        if self.is_container and self.items_inside:
            bits.append("Contains: " + ", ".join(self.items_inside))
        return " ".join(bits)


@dataclass
class Room:
    id: str
    name: str
    description: str          # template string with {{object_id_desc}} placeholders
    material: Material = Material.STONE
    is_outdoor: bool = False
    light_level: int = 10
    exits: dict[str, str] = field(default_factory=dict)
    line_of_sight: list[str] = field(default_factory=list)
    enemies: list["Enemy"] = field(default_factory=list)
    objects: dict[str, WorldObject] = field(default_factory=dict)
    items_on_ground: list[str] = field(default_factory=list)
    ambient: list = field(default_factory=list)
    is_start: bool = False
    visited: bool = False
    enemy_spawns: list[dict] = field(default_factory=list)
    description_snippets: dict[str, str] = field(default_factory=dict)   # object_id -> snippet
    interaction_rules: list[dict] = field(default_factory=list)

    def get_description(self, verbose: bool = False) -> str:
        # Substitute all {{object_id_desc}} placeholders
        desc = self.description
        for obj_id, snippet in self.description_snippets.items():
            placeholder = f"{{{{{obj_id}_desc}}}}"   # e.g. {{letter_desc}}
            desc = desc.replace(placeholder, snippet)
        lines = [self.name]
        if verbose or not self.visited:
            lines.append(desc)
            # Fixed: use random.random() and random.choice() correctly
            if self.ambient and random.random() > 0.3:
                chosen = random.choice(self.ambient)  # pick one random string
                lines.append(chosen)
        living = self.living_enemies()
        if living:
            lines.append("Enemies: " + ", ".join(e.name for e in living))
        return "\n".join(lines)

    def living_enemies(self) -> list["Enemy"]:
        return [e for e in self.enemies if e.is_alive]

    def add_enemy(self, enemy: "Enemy") -> None:
        enemy.current_zone = self.id
        enemy.combat_room_id = self.id
        self.enemies.append(enemy)

    def remove_enemy(self, enemy: "Enemy") -> None:
        self.enemies = [e for e in self.enemies if e is not enemy]

    def find_object(self, name: str) -> WorldObject | None:
        needle = name.lower()
        for _, obj in self.objects.items():
            if not obj.hidden and needle in obj.name.lower():
                return obj
        return None

    def find_matching_rule(self, intent: str, target_name: str | None = None) -> dict | None:
        command = (intent or "").strip().lower()
        target = (target_name or "").strip().lower()
        for rule in self.interaction_rules:
            verbs = [v.strip().lower() for v in rule.get("commands", []) if str(v).strip()]
            if verbs and command not in verbs:
                continue
            targets = [t.strip().lower() for t in rule.get("targets", []) if str(t).strip()]
            if targets and target not in targets:
                continue
            return rule
        return None

    def enemies_visible_from(self, from_room: "Room") -> list["Enemy"]:
        if self.light_level <= 1:
            return []
        if from_room.id not in self.line_of_sight and self.id not in from_room.line_of_sight:
            return []
        return self.living_enemies()

    def apply_elemental_effect(self, effect_type: str, source: "Enemy | Player") -> list[str]:
        dt = coerce_damage_type(effect_type)
        if not dt:
            return [f"The {effect_type} energy dissipates."]
        interaction = resolve_material_interaction(dt, self.material)
        lines = [f"{source.name}'s {dt.value} effect {interaction.summary} in {self.name}."]
        if interaction.spreads:
            lines.append("The effect spreads through the environment.")
        if interaction.applies_status:
            lines.append(f"Nearby entities risk becoming {interaction.applies_status}.")
        return lines


class WorldMap:
    def __init__(self):
        self.rooms: dict[str, Room] = {}
        self.current_room_id: str | None = None
        self.start_room_id: str | None = None

    def add_room(self, room: Room) -> None:
        self.rooms[room.id] = room
        if room.is_start and not self.start_room_id:
            self.start_room_id = room.id
        if not self.current_room_id:
            self.current_room_id = room.id

    def current_room(self) -> Room | None:
        return self.rooms.get(self.current_room_id) if self.current_room_id else None

    def get_room(self, room_id: str) -> Room | None:
        return self.rooms.get(room_id)

    def move_player(self, direction: str) -> tuple[bool, str]:
        room = self.current_room()
        if not room:
            return False, "No current room."
        if direction not in room.exits:
            return False, "You cannot go that way."
        target = room.exits[direction]
        if target not in self.rooms:
            return False, "That exit leads nowhere."
        self.current_room_id = target
        new_room = self.current_room()
        was_visited = new_room.visited
        new_room.visited = True
        return True, new_room.get_description(verbose=not was_visited)

    def neighbors_of(self, room_id: str) -> list[str]:
        room = self.get_room(room_id)
        return [rid for rid in room.exits.values() if rid in self.rooms] if room else []

    def neighbor_rooms(self, room_id: str) -> list[str]:
        return self.neighbors_of(room_id)

    def shortest_path(self, start: str, goal: str, blocked: set[str] | None = None) -> list[str]:
        if start == goal:
            return [start]
        blocked = blocked or set()
        if start in blocked or goal in blocked:
            return []
        from collections import deque
        queue = deque([start])
        prev = {start: None}
        while queue:
            current = queue.popleft()
            for nxt in self.neighbors_of(current):
                if nxt in blocked or nxt in prev:
                    continue
                prev[nxt] = current
                if nxt == goal:
                    path = [goal]
                    while prev[path[-1]] is not None:
                        path.append(prev[path[-1]])
                    return list(reversed(path))
                queue.append(nxt)
        return []

    def distance_between(self, a: str, b: str) -> int:
        path = self.shortest_path(a, b)
        return len(path) - 1 if path else 999999

    def enemies_visible_from_current(self) -> list["Enemy"]:
        room = self.current_room()
        if not room:
            return []
        visible = list(room.living_enemies())
        for other_id in room.line_of_sight:
            other = self.get_room(other_id)
            if other:
                visible.extend(other.enemies_visible_from(room))
        return visible

    def step_enemy_outside_combat(self, player_room_id: str | None) -> list[str]:
        lines = []
        for room in list(self.rooms.values()):
            for enemy in list(room.living_enemies()):
                enemy.current_zone = room.id
                next_zone = enemy.choose_world_move(self, player_room_id)
                if not next_zone or next_zone == room.id:
                    continue
                if next_zone not in self.rooms:
                    continue
                room.remove_enemy(enemy)
                self.rooms[next_zone].add_enemy(enemy)
        return lines

    def snapshot(self) -> dict:
        return {
            "current_room_id": self.current_room_id,
            "rooms": {
                rid: {
                    "visited": r.visited,
                    "items_on_ground": list(r.items_on_ground),
                    "objects_hidden": {oid: obj.hidden for oid, obj in r.objects.items()},
                    "description_snippets": dict(r.description_snippets)  # persist snippets
                } for rid, r in self.rooms.items()
            }
        }

    def restore_snapshot(self, data: dict) -> None:
        self.current_room_id = data.get("current_room_id", self.current_room_id)
        for rid, state in data.get("rooms", {}).items():
            room = self.rooms.get(rid)
            if room:
                room.visited = state.get("visited", room.visited)
                room.items_on_ground = state.get("items_on_ground", room.items_on_ground)
                for oid, hidden in state.get("objects_hidden", {}).items():
                    if oid in room.objects:
                        room.objects[oid].hidden = hidden
                room.description_snippets.update(state.get("description_snippets", {}))
