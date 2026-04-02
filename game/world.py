from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
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
        lookup: dict[Material, MaterialProperties] = {
            Material.WOOD: cls("wood", burns=True, breaks_on_smash=True, blocks_sight=True),
            Material.STONE: cls("stone", blocks_sight=True),
            Material.METAL: cls("metal", conducts_electricity=True, conducts_cold=True, blocks_sight=True),
            Material.WATER: cls("water", conducts_electricity=True, floats=False, blocks_sight=False),
            Material.GLASS: cls("glass", breaks_on_smash=True, blocks_sight=False),
            Material.FLESH: cls("flesh", burns=True, blocks_sight=False),
            Material.CLOTH: cls("cloth", burns=True, breaks_on_smash=True, blocks_sight=False),
            Material.ICE: cls("ice", conducts_cold=True, breaks_on_smash=True, blocks_sight=False),
            Material.EARTH: cls("earth", blocks_sight=False, breaks_on_smash=True),
        }
        return lookup.get(material, cls(material.value))


# FIX: Complete material interactions for all damage types (based on your matrix)
MATERIAL_INTERACTIONS: dict[DamageType, dict[Material, MaterialInteraction]] = {
    DamageType.FIRE: {
        Material.WOOD: MaterialInteraction("ignites", damage_multiplier=1.25, applies_status="burning"),
        Material.METAL: MaterialInteraction("heats", damage_multiplier=1.0),
        Material.WATER: MaterialInteraction("extinguished", damage_multiplier=0.2),
        Material.GLASS: MaterialInteraction("cracks from heat", damage_multiplier=1.15),
        Material.ICE: MaterialInteraction("melts", damage_multiplier=1.5),
        Material.FLESH: MaterialInteraction("burns", damage_multiplier=1.2, applies_status="burning"),
        Material.CLOTH: MaterialInteraction("ignites", damage_multiplier=1.3, applies_status="burning"),
        Material.EARTH: MaterialInteraction("scorches", damage_multiplier=0.9),
    },
    DamageType.LIGHTNING: {
        Material.METAL: MaterialInteraction("conducts", damage_multiplier=1.2, spreads=True),
        Material.WATER: MaterialInteraction("conducts", damage_multiplier=1.2, spreads=True),
        Material.FLESH: MaterialInteraction("shocks", damage_multiplier=1.1, applies_status="shocked"),
    },
    DamageType.COLD: {
        Material.WOOD: MaterialInteraction("brittle", damage_multiplier=1.1),
        Material.METAL: MaterialInteraction("brittle", damage_multiplier=1.1),
        Material.WATER: MaterialInteraction("freezes", damage_multiplier=0.8),
        Material.ICE: MaterialInteraction("reinforces", damage_multiplier=0.5),
        Material.FLESH: MaterialInteraction("slows", damage_multiplier=0.9, applies_status="slowed"),
    },
    DamageType.FLOOD: {
        Material.WOOD: MaterialInteraction("floats", damage_multiplier=0.8),
        Material.WATER: MaterialInteraction("no effect", damage_multiplier=0.0),
        Material.FLESH: MaterialInteraction("pushes", damage_multiplier=0.5),
    },
    DamageType.SLASHING: {
        Material.WOOD: MaterialInteraction("cuts", damage_multiplier=1.1),
        Material.GLASS: MaterialInteraction("shatters", damage_multiplier=1.5),
        Material.FLESH: MaterialInteraction("lacerates", damage_multiplier=1.2, applies_status="bleeding"),
        Material.CLOTH: MaterialInteraction("tears", damage_multiplier=1.2),
    },
    DamageType.BLUDGEONING: {
        Material.WOOD: MaterialInteraction("cracks", damage_multiplier=1.2),
        Material.GLASS: MaterialInteraction("shatters", damage_multiplier=1.5),
        Material.FLESH: MaterialInteraction("bruises", damage_multiplier=1.1),
    },
    DamageType.PIERCING: {
        Material.WOOD: MaterialInteraction("penetrates", damage_multiplier=1.1),
        Material.GLASS: MaterialInteraction("shatters", damage_multiplier=1.5),
        Material.FLESH: MaterialInteraction("impales", damage_multiplier=1.2),
    },
    DamageType.ACID: {
        Material.WOOD: MaterialInteraction("corrodes", damage_multiplier=1.3, applies_status="corroding"),
        Material.METAL: MaterialInteraction("corrodes", damage_multiplier=1.3, applies_status="corroding"),
        Material.FLESH: MaterialInteraction("dissolves", damage_multiplier=1.4, applies_status="acid_burn"),
    },
    DamageType.POISON: {
        Material.WATER: MaterialInteraction("contaminates", damage_multiplier=0.5, applies_status="poisoned"),
        Material.FLESH: MaterialInteraction("poisons", damage_multiplier=1.0, applies_status="poisoned"),
    },
    DamageType.NECROTIC: {
        Material.WOOD: MaterialInteraction("decays", damage_multiplier=1.2),
        Material.FLESH: MaterialInteraction("rots", damage_multiplier=1.2, applies_status="decaying"),
    },
    DamageType.RADIANT: {
        Material.WOOD: MaterialInteraction("purifies", damage_multiplier=1.0),
        Material.FLESH: MaterialInteraction("burns", damage_multiplier=1.2, applies_status="radiant_burn"),
    },
    DamageType.SONIC: {
        Material.GLASS: MaterialInteraction("shatters", damage_multiplier=1.5),
        Material.METAL: MaterialInteraction("resonates", damage_multiplier=1.1, spreads=True),
    },
    DamageType.FORCE: {
        Material.GLASS: MaterialInteraction("shatters", damage_multiplier=1.5),
        Material.WOOD: MaterialInteraction("splinters", damage_multiplier=1.2),
    },
}


def resolve_material_interaction(damage_type: DamageType, material: Material) -> MaterialInteraction:
    table = MATERIAL_INTERACTIONS.get(damage_type, {})
    return table.get(material, MaterialInteraction("has little effect", damage_multiplier=1.0))


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
        min_level = int(req.get("min_level", 0))
        if getattr(player, "level", 1) < min_level:
            return False, f"You need level {min_level} to do that."
        cls = req.get("class")
        class_id = getattr(getattr(player, "char_class", None), "id", None)
        if cls and class_id != cls:
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
        revealed: list[WorldObject] = []
        for obj_id in self.reveals:
            if obj_id in room.objects:
                room.objects[obj_id].hidden = False
                revealed.append(room.objects[obj_id])
        return narration, revealed

    def put_object(self, obj: "WorldObject") -> str:
        if not self.is_container:
            return f"{self.name} is not a container."
        self.contents.append(obj)
        return f"Placed {obj.name} in {self.name}."

    def take_object(self, obj_id: str) -> tuple["WorldObject | None", str]:
        for i, obj in enumerate(self.contents):
            if obj.id == obj_id:
                return self.contents.pop(i), f"Took {obj.name} from {self.name}."
        return None, f"{obj_id} is not inside {self.name}."

    def put_item(self, item_id: str) -> str:
        if not self.is_container:
            return f"{self.name} is not a container."
        self.items_inside.append(item_id)
        return f"Placed {item_id} in {self.name}."

    def take_item(self, item_id: str) -> tuple[str | None, str]:
        if item_id in self.items_inside:
            self.items_inside.remove(item_id)
            return item_id, f"Took {item_id} from {self.name}."
        return None, f"{item_id} is not in {self.name}."

    def list_contents(self) -> str:
        parts = [obj.name for obj in self.contents] + self.items_inside
        return "Empty." if not parts else "Contains: " + ", ".join(parts)

    def examine(self) -> str:
        bits = [self.description]
        if self.is_locked:
            bits.append("It is locked.")
        if self.is_container:
            bits.append(self.list_contents())
        return " ".join(bits)


@dataclass
class Room:
    id: str
    name: str
    description: str
    material: Material = Material.STONE
    is_outdoor: bool = False
    light_level: int = 10
    exits: dict[str, str] = field(default_factory=dict)
    line_of_sight: list[str] = field(default_factory=list)
    enemies: list["Enemy"] = field(default_factory=list)
    objects: dict[str, WorldObject] = field(default_factory=dict)
    items_on_ground: list[str] = field(default_factory=list)
    ambient: str = ""
    is_start: bool = False
    visited: bool = False
    # FIX: enemy_spawns is now properly stored
    enemy_spawns: list[dict] = field(default_factory=list)

    def get_description(self, verbose: bool = False) -> str:
        lines = [self.name]
        if verbose or not self.visited:
            lines.append(self.description)
            if self.ambient:
                lines.append(self.ambient)
            obj = self.objects_summary()
            if obj:
                lines.append(obj)
        living = self.living_enemies()
        if living:
            lines.append("Enemies: " + ", ".join(e.name for e in living))
        lines.append(self.exits_summary())
        return "\n".join([l for l in lines if l])

    def exits_summary(self) -> str:
        return "Exits: " + ", ".join(sorted(self.exits.keys())) if self.exits else "No obvious exits."

    def objects_summary(self) -> str:
        visible = [o.name for o in self.objects.values() if not o.hidden]
        return "Objects: " + ", ".join(visible) if visible else ""

    def add_enemy(self, enemy: "Enemy") -> None:
        setattr(enemy, "current_zone", self.id)
        setattr(enemy, "combat_room_id", self.id)
        self.enemies.append(enemy)

    def remove_enemy(self, enemy: "Enemy") -> None:
        self.enemies = [e for e in self.enemies if e is not enemy]

    def living_enemies(self) -> list["Enemy"]:
        return [e for e in self.enemies if e.is_alive]

    def get_enemy_by_name(self, name: str) -> list["Enemy"]:
        needle = name.lower()
        return [e for e in self.living_enemies() if needle in e.name.lower()]

    def get_enemy_by_index(self, index: int) -> "Enemy | None":
        living = self.living_enemies()
        return living[index - 1] if 1 <= index <= len(living) else None

    def add_object(self, obj: WorldObject) -> None:
        self.objects[obj.id] = obj

    def remove_object(self, obj_id: str) -> WorldObject | None:
        return self.objects.pop(obj_id, None)

    def find_object(self, name: str) -> WorldObject | None:
        needle = name.lower()
        for obj in self.objects.values():
            if not obj.hidden and needle in obj.name.lower():
                return obj
        return None

    def reveal_object(self, obj_id: str) -> None:
        if obj_id in self.objects:
            self.objects[obj_id].hidden = False

    def drop_item(self, item_id: str) -> None:
        self.items_on_ground.append(item_id)

    def pick_up_item(self, item_id: str) -> bool:
        if item_id in self.items_on_ground:
            self.items_on_ground.remove(item_id)
            return True
        return False

    # FIX: complete elemental effect handler for all damage types
    def apply_elemental_effect(self, effect_type: str, source: "Enemy | Player") -> list[str]:
        damage_type = coerce_damage_type(effect_type)
        if damage_type is None:
            return [f"The {effect_type} energy dissipates without a clear material reaction."]
        interaction = resolve_material_interaction(damage_type, self.material)
        source_name = getattr(source, "name", "Something")
        lines = [f"{source_name}'s {damage_type.value} effect {interaction.summary} in {self.name}."]
        if interaction.spreads:
            lines.append("The effect spreads through the environment.")
        if interaction.applies_status:
            lines.append(f"Nearby entities risk becoming {interaction.applies_status}.")
            # Actually apply status to all entities in room (including player?)
            for entity in self.living_enemies() + ([source] if isinstance(source, Player) else []):
                if hasattr(entity, "apply_effect"):
                    from game.effects import StatusEffect, EffectTrigger, EffectCategory
                    effect = StatusEffect(
                        id=interaction.applies_status,
                        name=interaction.applies_status.capitalize(),
                        description="",
                        trigger=EffectTrigger.ON_TURN_END,
                        category=EffectCategory.DEBUFF,
                        duration=2
                    )
                    lines.append(entity.apply_effect(effect))
        if self.objects:
            sample = ", ".join(obj.name for obj in list(self.objects.values())[:3])
            lines.append(f"Objects react: {sample}.")
        return lines

    def material_properties(self) -> MaterialProperties:
        return MaterialProperties.for_material(self.material)

    def peek_description(self, from_room: "Room") -> str:
        _ = from_room
        living = self.living_enemies()
        enemy_text = f" You spot {', '.join(e.name for e in living)}." if living else ""
        return f"You glimpse {self.name}. {self.description}{enemy_text}".strip()

    def enemies_visible_from(self, from_room: "Room") -> list["Enemy"]:
        if self.light_level <= 1:
            return []
        if from_room.id not in self.line_of_sight and self.id not in from_room.line_of_sight:
            return []
        return self.living_enemies()


class WorldMap:
    def __init__(self) -> None:
        self.rooms: dict[str, Room] = {}
        self.current_room_id: str | None = None
        self.start_room_id: str | None = None
        self.moves: int | None = 0

    def add_room(self, room: Room) -> None:
        self.rooms[room.id] = room
        if room.is_start and self.start_room_id is None:
            self.start_room_id = room.id
        if self.current_room_id is None:
            self.current_room_id = room.id

    def get_room(self, room_id: str) -> Room | None:
        return self.rooms.get(room_id)

    def current_room(self) -> Room | None:
        return self.rooms.get(self.current_room_id) if self.current_room_id else None

    def validate_exits(self) -> list[str]:
        errors: list[str] = []
        for room in self.rooms.values():
            for direction, target in room.exits.items():
                if target not in self.rooms:
                    errors.append(f"{room.id}.{direction} -> unknown room '{target}'")
        return errors

    def move_player(self, direction: str) -> tuple[bool, str]:
        ok, reason = self.can_move(direction)
        if not ok:
            return False, reason
        room = self.current_room()
        assert room is not None
        self.current_room_id = room.exits[direction]
        new_room = self.current_room()
        if new_room is not None:
            new_room.visited = True
            return True, new_room.get_description(verbose=not new_room.visited)
        return False, "Movement failed."

    def can_move(self, direction: str) -> tuple[bool, str]:
        room = self.current_room()
        if room is None:
            return False, "No current room."
        if direction not in room.exits:
            return False, "You cannot go that way."
        target = room.exits[direction]
        if target not in self.rooms:
            return False, "That exit leads nowhere."
        return True, ""

    def check_line_of_sight(self, from_id: str, to_id: str) -> bool:
        room = self.rooms.get(from_id)
        return bool(room and to_id in room.line_of_sight)

    def rooms_visible_from_current(self) -> list[Room]:
        room = self.current_room()
        if room is None:
            return []
        return [self.rooms[rid] for rid in room.line_of_sight if rid in self.rooms]

    def enemies_visible_from_current(self) -> list["Enemy"]:
        room = self.current_room()
        if room is None:
            return []
        visible: list[Enemy] = []
        for enemy in room.living_enemies():
            setattr(enemy, "combat_room_id", room.id)
            visible.append(enemy)
        for other in self.rooms_visible_from_current():
            for enemy in other.enemies_visible_from(room):
                setattr(enemy, "combat_room_id", other.id)
                visible.append(enemy)
        return visible

    def find_item_in_world(self, item_id: str) -> tuple[Room | None, str]:
        for room in self.rooms.values():
            if item_id in room.items_on_ground:
                return room, f"on the ground in {room.name}"
        return None, "not found"

    def neighbor_rooms(self, room_id: str) -> list[str]:
        room = self.get_room(room_id)
        if room is None:
            return []
        return [rid for rid in room.exits.values() if rid in self.rooms]

    def shortest_path(self, start_id: str, goal_id: str, blocked: set[str] | None = None) -> list[str]:
        if start_id == goal_id:
            return [start_id]
        blocked = blocked or set()
        if start_id in blocked or goal_id in blocked:
            return []
        frontier: list[str] = [start_id]
        prev: dict[str, str | None] = {start_id: None}
        while frontier:
            current = frontier.pop(0)
            for nxt in self.neighbor_rooms(current):
                if nxt in blocked or nxt in prev:
                    continue
                prev[nxt] = current
                if nxt == goal_id:
                    path = [goal_id]
                    node = goal_id
                    while prev[node] is not None:
                        node = prev[node]  # type: ignore[index]
                        path.append(node)
                    return list(reversed(path))
                frontier.append(nxt)
        return []

    def distance_between(self, start_id: str, goal_id: str) -> int:
        path = self.shortest_path(start_id, goal_id)
        return max(0, len(path) - 1) if path else 999999

    def step_enemy_outside_combat(self, player_room_id: str | None) -> list[str]:
        lines: list[str] = []
        for room in self.rooms.values():
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
            "start_room_id": self.start_room_id,
            "rooms": {
                rid: {
                    "visited": room.visited,
                    "items_on_ground": list(room.items_on_ground),
                    "objects_hidden": {oid: obj.hidden for oid, obj in room.objects.items()},
                }
                for rid, room in self.rooms.items()
            },
        }

    def restore_snapshot(self, data: dict) -> None:
        self.current_room_id = data.get("current_room_id", self.current_room_id)
        self.start_room_id = data.get("start_room_id", self.start_room_id)
        for rid, state in data.get("rooms", {}).items():
            room = self.rooms.get(rid)
            if room is None:
                continue
            room.visited = bool(state.get("visited", room.visited))
            room.items_on_ground = list(state.get("items_on_ground", room.items_on_ground))
            for oid, hidden in state.get("objects_hidden", {}).items():
                if oid in room.objects:
                    room.objects[oid].hidden = bool(hidden)