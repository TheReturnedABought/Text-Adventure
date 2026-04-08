# game/world.py
from __future__ import annotations
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional, Tuple, Set
from collections import deque, Counter

from game.entities import Enemy, Player

class Material(Enum):
    WOOD = "wood"; STONE = "stone"; METAL = "metal"; WATER = "water"
    GLASS = "glass"; FLESH = "flesh"; CLOTH = "cloth"; ICE = "ice"; EARTH = "earth"

class DamageType(Enum):
    BLUDGEONING = "bludgeoning"; PIERCING = "piercing"; SLASHING = "slashing"
    TEARING = "tearing"; FIRE = "fire"; LIGHTNING = "lightning"; COLD = "cold"
    FLOOD = "flood"; FORCE = "force"; ACID = "acid"; POISON = "poison"
    NECROTIC = "necrotic"; RADIANT = "radiant"; PSYCHIC = "psychic"; SONIC = "sonic"

@dataclass(frozen=True)
class MaterialInteraction:
    summary: str; damage_multiplier: float = 1.0
    applies_status: Optional[str] = None; spreads: bool = False

@dataclass
class MaterialProperties:
    name: str; burns: bool = False; conducts_electricity: bool = False
    floats: bool = False; blocks_sight: bool = True; breaks_on_smash: bool = False
    conducts_cold: bool = False

    @classmethod
    def for_material(cls, material: Material) -> MaterialProperties:
        lookup = {
            Material.WOOD: cls("wood", burns=True, breaks_on_smash=True),
            Material.STONE: cls("stone"), Material.METAL: cls("metal", conducts_electricity=True, conducts_cold=True),
            Material.WATER: cls("water", conducts_electricity=True, blocks_sight=False),
            Material.GLASS: cls("glass", breaks_on_smash=True, blocks_sight=False),
            Material.FLESH: cls("flesh", burns=True, blocks_sight=False),
            Material.CLOTH: cls("cloth", burns=True, breaks_on_smash=True, blocks_sight=False),
            Material.ICE: cls("ice", conducts_cold=True, breaks_on_smash=True, blocks_sight=False),
            Material.EARTH: cls("earth", breaks_on_smash=True, blocks_sight=False),
        }
        return lookup.get(material, cls(material.value))

MATERIAL_INTERACTIONS: Dict[DamageType, Dict[Material, MaterialInteraction]] = {
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
}

def resolve_material_interaction(dt: DamageType, mat: Material) -> MaterialInteraction:
    return MATERIAL_INTERACTIONS.get(dt, {}).get(mat, MaterialInteraction("has little effect", 1.0))

def coerce_damage_type(raw: str) -> Optional[DamageType]:
    text = str(raw or "").strip().lower()
    return next((dt for dt in DamageType if dt.value == text), None)

def apply_turn_passives(player: Player, world_map: "WorldMap", room_id: str) -> List[str]:
    lines = []
    room = world_map.get_room(room_id)
    if not room: return lines
    for item in player.equipped.values():
        if "beasts_heart" in item.item_flags and (room.id.startswith("wyrmwood") or room.material.value == "flesh"):
            if player.heal(1): lines.append("Beast's Heart regenerates 1 HP.")
        if "arcane_cloak" in item.item_flags:
            before = player.mana
            player.mana = min(player.max_mana, player.mana + 1)
            if player.mana > before: lines.append("Arcane Cloak restores 1 MP.")
    return lines

@dataclass
class WorldObject:
    id: str; name: str; description: str
    material: Material = Material.WOOD
    is_container: bool = False; is_moveable: bool = False; is_locked: bool = False
    key_item_id: Optional[str] = None; hidden: bool = False
    reveals: List[str] = field(default_factory=list)
    on_interact: Dict[str, str] = field(default_factory=dict)
    required_commands: Dict[str, dict] = field(default_factory=dict)
    set_flags_on_interact: Dict[str, Dict[str, bool]] = field(default_factory=dict)
    contents: List["WorldObject"] = field(default_factory=list)
    items_inside: List[str] = field(default_factory=list)
    description_snippets: Dict[str, str] = field(default_factory=dict)

    def can_interact_with(self, command: str, player: Player) -> Tuple[bool, str]:
        if self.hidden: return False, "You don't see that here."
        if self.is_locked and command not in {"unlock", "open"}:
            return False, f"The {self.name} is locked."
        req = self.required_commands.get(command, {})
        if player.level < req.get("min_level", 0):
            return False, f"You need level {req['min_level']} to do that."
        class_id = getattr(getattr(player, "char_class", None), "id", None)
        if req.get("class") and class_id != req["class"]:
            return False, "Your class cannot do that."
        return True, ""

    def interact(self, command: str, player: Player, room: "Room") -> Tuple[str, List["WorldObject"]]:
        if command == "open" and self.is_locked: return f"The {self.name} is locked.", []
        if command == "unlock":
            if not self.is_locked: return f"The {self.name} is already unlocked.", []
            if self.key_item_id and not player.find_in_inventory(self.key_item_id):
                return f"You need {self.key_item_id} to unlock the {self.name}.", []
            self.is_locked = False
            return f"You unlock the {self.name}.", []
        narration = self.on_interact.get(command, f"You {command} the {self.name}.")
        if "{contents}" in narration and self.items_inside:
            narration = narration.replace("{contents}", ", ".join(self.items_inside))
        revealed = []
        for obj_id in self.reveals:
            if obj_id in room.objects:
                room.objects[obj_id].hidden = False
                revealed.append(room.objects[obj_id])
        return narration, revealed

    def examine(self) -> str:
        bits = [self.description]
        if self.is_locked: bits.append("It is locked.")
        if self.is_container and self.items_inside:
            bits.append("Contains: " + ", ".join(self.items_inside))
        return " ".join(bits)

@dataclass
class Room:
    id: str; name: str; description: str
    material: Material = Material.STONE
    is_outdoor: bool = False; light_level: int = 10
    exits: Dict[str, str] = field(default_factory=dict)
    exit_requirements: Dict[str, dict] = field(default_factory=dict)
    line_of_sight: List[str] = field(default_factory=list)
    enemies: List[Enemy] = field(default_factory=list)
    objects: Dict[str, WorldObject] = field(default_factory=dict)
    items_on_ground: List[str] = field(default_factory=list)
    ambient: List = field(default_factory=list)
    is_start: bool = False
    visited: bool = False
    enemy_spawns: List[dict] = field(default_factory=list)
    description_snippets: Dict[str, str] = field(default_factory=dict)
    interaction_rules: List[dict] = field(default_factory=list)
    combat_won_snippet: str = ""
    art_asset: Optional[str] = None

    def get_description(self, verbose: bool = False, turn_number: int = 0) -> str:
        if self.visited and not verbose:
            lines = [self.name]
            living = [e for e in self.enemies if e.is_alive]
            if living: lines.append("Enemies: " + ", ".join(e.name for e in living))
            if self.items_on_ground:
                counts = Counter(self.items_on_ground)
                items_str = ", ".join(f"{count} x {name}" if count > 1 else name for name, count in counts.items())
                lines.append(f"-{items_str}")
            return "\n".join(lines)
        desc = self.description
        for key, snippet in self.description_snippets.items():
            desc = desc.replace(f"{{{{{key}_desc}}}}", snippet).replace(f"{{{{{key}}}}}", snippet)
        lines = [self.name, desc]
        if turn_number:
            phase = ("dawn", "day", "dusk", "night")[((turn_number // 8) % 4)]
            lines.append(f"The world feels like {phase} (turn {turn_number}).")
        if self.ambient and random.random() > 0.3: lines.append(random.choice(self.ambient))
        living = [e for e in self.enemies if e.is_alive]
        if living: lines.append("Enemies: " + ", ".join(e.name for e in living))
        if self.items_on_ground:
            counts = Counter(self.items_on_ground)
            items_str = ", ".join(f"{count} x {name}" if count > 1 else name for name, count in counts.items())
            lines.append(f"-{items_str}")
        return "\n".join(lines)

    def add_enemy(self, enemy: Enemy) -> None:
        enemy.current_zone = self.id; enemy.combat_room_id = self.id
        self.enemies.append(enemy)

    def remove_enemy(self, enemy: Enemy) -> None:
        self.enemies = [e for e in self.enemies if e is not enemy]

    def living_enemies(self) -> List[Enemy]:
        """Return all enemies in this room that are still alive."""
        return [e for e in self.enemies if e.is_alive]

    def find_object(self, name: str) -> Optional[WorldObject]:
        needle = name.lower()
        for obj in self.objects.values():
            if not obj.hidden and needle in obj.name.lower(): return obj
        return None

    def find_matching_rule(self, intent: str, target_name: Optional[str] = None) -> Optional[dict]:
        command = (intent or "").strip().lower()
        target = (target_name or "").strip().lower()
        for rule in self.interaction_rules:
            verbs = [v.strip().lower() for v in rule.get("commands", []) if v]
            if verbs and command not in verbs: continue
            targets = [t.strip().lower() for t in rule.get("targets", []) if t]
            if targets and target not in targets: continue
            return rule
        return None

    def enemies_visible_from(self, from_room: "Room") -> List[Enemy]:
        if self.light_level <= 1: return []
        if from_room.id not in self.line_of_sight and self.id not in from_room.line_of_sight: return []
        return [e for e in self.enemies if e.is_alive]

    def apply_elemental_effect(self, effect_type: str, source) -> List[str]:
        dt = coerce_damage_type(effect_type)
        if not dt: return [f"The {effect_type} energy dissipates."]
        interaction = resolve_material_interaction(dt, self.material)
        if interaction.summary == "has little effect": return []
        lines = [f"{source.name}'s {dt.value} effect {interaction.summary} in {self.name}."]
        if interaction.spreads: lines.append("The effect spreads through the environment.")
        if interaction.applies_status: lines.append(f"Nearby entities risk becoming {interaction.applies_status}.")
        return lines

    def update_after_combat(self) -> None:
        if not [e for e in self.enemies if e.is_alive]:
            for obj in self.objects.values():
                if getattr(obj, "reveal_on_combat_end", False): obj.hidden = False
            if self.combat_won_snippet:
                self.description = self.combat_won_snippet
                self.description_snippets.clear()

class WorldMap:
    def __init__(self):
        self.rooms: Dict[str, Room] = {}
        self.current_room_id: Optional[str] = None
        self.start_room_id: Optional[str] = None
        self.global_flags: Dict[str, bool] = {}
        self.turn_counter: int = 0

    def add_room(self, room: Room) -> None:
        self.rooms[room.id] = room
        if room.is_start and not self.start_room_id: self.start_room_id = room.id
        if not self.current_room_id: self.current_room_id = room.id

    def current_room(self) -> Optional[Room]: return self.rooms.get(self.current_room_id)

    def get_room(self, room_id: str) -> Optional[Room]: return self.rooms.get(room_id)

    def neighbors_of(self, room_id: str) -> List[str]:
        room = self.get_room(room_id)
        return [rid for rid in room.exits.values() if rid in self.rooms] if room else []

    def move_player(self, direction: str) -> Tuple[bool, str]:
        room = self.current_room()
        if not room: return False, "No current room."
        if direction not in room.exits: return False, "You cannot go that way."
        req = room.exit_requirements.get(direction, {})
        required_flag = req.get("required_flag")
        if required_flag and not bool(self.global_flags.get(required_flag, False)):
            return False, req.get("blocked_text", "You cannot go that way yet.")
        target = room.exits[direction]
        if target not in self.rooms: return False, "That exit leads nowhere."
        self.current_room_id = target
        self.advance_turn()
        new_room = self.current_room()
        was_visited = new_room.visited
        new_room.visited = True
        return True, new_room.get_description(verbose=not was_visited, turn_number=self.turn_counter)

    def shortest_path(self, start: str, goal: str, blocked: Optional[Set[str]] = None) -> List[str]:
        if start == goal: return [start]
        blocked = blocked or set()
        if start in blocked or goal in blocked: return []
        queue = deque([start])
        prev = {start: None}
        while queue:
            cur = queue.popleft()
            for nxt in self.neighbors_of(cur):
                if nxt in blocked or nxt in prev: continue
                prev[nxt] = cur
                if nxt == goal:
                    path = [goal]
                    while prev[path[-1]] is not None: path.append(prev[path[-1]])
                    return list(reversed(path))
                queue.append(nxt)
        return []

    def distance_between(self, a: str, b: str) -> int:
        path = self.shortest_path(a, b)
        return len(path) - 1 if path else 999999

    def enemies_visible_from_current(self) -> List[Enemy]:
        room = self.current_room()
        if not room: return []
        visible = [e for e in room.enemies if e.is_alive]
        for other_id in room.line_of_sight:
            other = self.get_room(other_id)
            if other: visible.extend(other.enemies_visible_from(room))
        return visible

    def step_enemy_outside_combat(self, player_room_id: Optional[str]) -> List[str]:
        lines = []
        for room in list(self.rooms.values()):
            for enemy in list(room.enemies):
                if not enemy.is_alive: continue
                enemy.current_zone = room.id
                next_zone = enemy.choose_world_move(self, player_room_id)
                if not next_zone or next_zone == room.id: continue
                if next_zone not in self.rooms: continue
                room.remove_enemy(enemy)
                self.rooms[next_zone].add_enemy(enemy)
        return lines

    def advance_turn(self) -> None: self.turn_counter += 1

    def snapshot(self) -> dict:
        return {
            "current_room_id": self.current_room_id,
            "rooms": {
                rid: {
                    "visited": r.visited,
                    "items_on_ground": list(r.items_on_ground),
                    "objects_hidden": {oid: obj.hidden for oid, obj in r.objects.items()},
                    "description_snippets": dict(r.description_snippets)
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
                    if oid in room.objects: room.objects[oid].hidden = hidden
                room.description_snippets.update(state.get("description_snippets", {}))