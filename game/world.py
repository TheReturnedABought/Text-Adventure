from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from game.entities import Enemy, Player


# ══════════════════════════════════════════════════════════════════════════════
# Material system
# ══════════════════════════════════════════════════════════════════════════════

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


@dataclass
class MaterialProperties:
    """Mechanical properties of a material relevant to world interactions.

    These are read by room/object interaction logic and combat effects.

    Attributes:
        name                – display name
        burns               – catches fire; fire in a wood room deals AoE damage
        conducts_electricity – lightning hits spread to nearby entities in this material room
        floats              – object floats on water rather than sinking
        blocks_sight        – opaque to line-of-sight (e.g. stone walls)
        breaks_on_smash     – can be destroyed by smash / heavy commands
        conducts_cold       – cold effects spread
    """

    name: str
    burns: bool = False
    conducts_electricity: bool = False
    floats: bool = False
    blocks_sight: bool = True
    breaks_on_smash: bool = False
    conducts_cold: bool = False

    @classmethod
    def for_material(cls, material: Material) -> "MaterialProperties":
        """Return the standard property set for a given material enum value."""
        ...


# ══════════════════════════════════════════════════════════════════════════════
# World objects
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class WorldObject:
    """An interactive environmental object inside a room.

    Attributes:
        id                – unique ID within its room (e.g. 'old_rug')
        name              – player-facing name ('old rug')
        description       – examine text
        material          – physical material
        is_container      – can hold other objects
        is_moveable       – can be moved with 'move' / 'push' etc.
        is_locked         – requires a key or command unlock
        key_item_id       – item ID that unlocks this object (or None)
        hidden            – not listed in room description until revealed
        reveals           – object IDs added to the room when this is moved/opened
        on_interact       – {command_name: narration_string} for simple text responses
        required_commands – {command_name: {'min_level': int, 'class': str}}
                            restricts which commands can interact with this object
        contents          – child objects if is_container
        items_inside      – item IDs stored inside (if container)
    """

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

    # ── Interaction ───────────────────────────────────────────────────────

    def can_interact_with(self, command_name: str, player: "Player") -> tuple[bool, str]:
        """Check if `player` may use `command_name` on this object.

        Returns (allowed, reason_if_denied).
        Checks hidden status, lock state, and required_commands level/class gates.
        """
        ...

    def interact(self, command_name: str, player: "Player",
                 room: "Room") -> tuple[str, list["WorldObject"]]:
        """Execute an interaction.

        Returns (narration_string, list_of_newly_revealed_objects).
        Caller is responsible for adding revealed objects to the room.
        """
        ...

    # ── Container ops ─────────────────────────────────────────────────────

    def put_object(self, obj: "WorldObject") -> str:
        """Place another WorldObject inside this container. Returns narration."""
        ...

    def take_object(self, obj_id: str) -> tuple["WorldObject | None", str]:
        """Remove a child WorldObject by ID. Returns (object, narration)."""
        ...

    def put_item(self, item_id: str) -> str:
        """Store an item ID in this container."""
        ...

    def take_item(self, item_id: str) -> tuple[str | None, str]:
        """Remove an item ID from this container. Returns (item_id, narration)."""
        ...

    def list_contents(self) -> str:
        """Describe contents for examine/look inside."""
        ...

    # ── Display ───────────────────────────────────────────────────────────

    def examine(self) -> str:
        """Full examine text including lock/container state."""
        ...


# ══════════════════════════════════════════════════════════════════════════════
# Room
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class Room:
    """A single location node in the world graph.

    Attributes:
        id              – unique room ID (matches JSON file 'id' field)
        name            – display name
        description     – base description (shown on first entry or 'look')
        material        – room's primary material (affects elemental interactions)
        is_outdoor      – outdoor rooms ignore material conduction rules
        light_level     – 0 = pitch dark, 10 = full daylight; affects visibility
        exits           – {direction: room_id} map
        line_of_sight   – room_ids visible from this room before entering
        enemies         – live Enemy instances currently in this room
        objects         – {object_id: WorldObject} in this room
        items_on_ground – item IDs lying on the floor (can be picked up)
        ambient         – ambient description appended when standing here
        is_start        – marks the player's starting room
        visited         – set True after first entry (toggles short description)
    """

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

    # ── Description ───────────────────────────────────────────────────────

    def get_description(self, verbose: bool = False) -> str:
        """Return room description.

        verbose=True → full text + object list + visible exits.
        verbose=False (revisit) → short name + exits + living enemies only.
        """
        ...

    def exits_summary(self) -> str:
        """'Exits: north, east' style string."""
        ...

    def objects_summary(self) -> str:
        """List visible (non-hidden) objects in the room."""
        ...

    # ── Enemy management ──────────────────────────────────────────────────

    def add_enemy(self, enemy: "Enemy") -> None:
        ...

    def remove_enemy(self, enemy: "Enemy") -> None:
        ...

    def living_enemies(self) -> list["Enemy"]:
        ...

    def get_enemy_by_name(self, name: str) -> list["Enemy"]:
        """Return all living enemies whose names contain `name` (case-insensitive)."""
        ...

    def get_enemy_by_index(self, index: int) -> "Enemy | None":
        """1-based index into living_enemies()."""
        ...

    # ── Object management ─────────────────────────────────────────────────

    def add_object(self, obj: WorldObject) -> None:
        ...

    def remove_object(self, obj_id: str) -> WorldObject | None:
        ...

    def find_object(self, name: str) -> WorldObject | None:
        """Case-insensitive partial match against non-hidden objects."""
        ...

    def reveal_object(self, obj_id: str) -> None:
        """Mark a hidden object as visible (called after trigger interaction)."""
        ...

    # ── Item management ───────────────────────────────────────────────────

    def drop_item(self, item_id: str) -> None:
        ...

    def pick_up_item(self, item_id: str) -> bool:
        """Remove item from floor. Returns False if not present."""
        ...

    # ── Material / elemental interactions ─────────────────────────────────

    def apply_elemental_effect(self, effect_type: str,
                               source: "Enemy | Player") -> list[str]:
        """Spread an elemental effect based on room material.

        Examples:
            'fire'   + wood room  → all entities take ongoing burn damage
            'lightning' + metal room → all entities receive shock
            'water'  in room      → extinguishes fire; stone/metal objects sink

        Returns list of narration strings, one per entity affected.
        """
        ...

    def material_properties(self) -> MaterialProperties:
        """Shorthand to get the MaterialProperties for this room's material."""
        ...

    # ── Line of sight ─────────────────────────────────────────────────────

    def peek_description(self, from_room: "Room") -> str:
        """Short description of what is visible from an adjacent room.

        Called when player opens a door without stepping through.
        Does NOT include room objects or items.
        """
        ...

    def enemies_visible_from(self, from_room: "Room") -> list["Enemy"]:
        """Return living enemies in this room visible from `from_room`."""
        ...


# ══════════════════════════════════════════════════════════════════════════════
# World map
# ══════════════════════════════════════════════════════════════════════════════

class WorldMap:
    """The navigable graph of all rooms.

    Attributes:
        rooms           – {room_id: Room}
        current_room_id – player's current location
        start_room_id   – entry point (set by loader)
    """

    def __init__(self) -> None:
        self.rooms: dict[str, Room] = {}
        self.current_room_id: str | None = None
        self.start_room_id: str | None = None

    # ── Room management ───────────────────────────────────────────────────

    def add_room(self, room: Room) -> None:
        ...

    def get_room(self, room_id: str) -> Room | None:
        ...

    def current_room(self) -> Room | None:
        ...

    def validate_exits(self) -> list[str]:
        """Return list of errors where exits point to non-existent room IDs."""
        ...

    # ── Navigation ────────────────────────────────────────────────────────

    def move_player(self, direction: str) -> tuple[bool, str]:
        """Attempt to move the player in `direction`.

        Returns (success, narration).
        Fails if exit doesn't exist or is blocked.
        On success updates current_room_id and marks room visited.
        """
        ...

    def can_move(self, direction: str) -> tuple[bool, str]:
        """Check if movement is possible without executing it."""
        ...

    # ── Line of sight ─────────────────────────────────────────────────────

    def check_line_of_sight(self, from_id: str, to_id: str) -> bool:
        """Return True if to_id is in from_id's line_of_sight list."""
        ...

    def rooms_visible_from_current(self) -> list[Room]:
        """All rooms the player can see from their current position."""
        ...

    def enemies_visible_from_current(self) -> list["Enemy"]:
        """All living enemies in line-of-sight rooms (triggers combat)."""
        ...

    # ── Object / item helpers ─────────────────────────────────────────────

    def find_item_in_world(self, item_id: str) -> tuple[Room | None, str]:
        """Search all rooms for an item on the ground. Returns (room, location_desc)."""
        ...

    # ── Serialisation ─────────────────────────────────────────────────────

    def snapshot(self) -> dict:
        """Serialise world state to a dict for save/load."""
        ...

    def restore_snapshot(self, data: dict) -> None:
        """Restore world state from a saved snapshot dict."""
        ...