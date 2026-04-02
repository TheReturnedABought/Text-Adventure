from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from game.models import EquippableItem, CharacterClass, Ability
    from game.entities import Enemy
    from game.world import Room, WorldObject, WorldMap
    from game.commands import CommandRegistry


class AssetLoader:
    """Loads all game content from JSON files inside the assets/ directory.

    Every public method returns pure data objects; no game state is mutated.
    Call build_world_map() once at startup to wire rooms into a navigable graph.

    Expected asset folder layout:
        assets/
            rooms/          *.json  – one file per room
            items/          *.json  – one file per item
            enemies/        *.json  – one file per enemy template
            classes/        *.json  – one file per character class
            abilities/      *.json  – one file per ability set or single ability
            commands/       commands.json  – master command + modifier table
    """

    def __init__(self, assets_root: str | Path) -> None:
        self.assets_root = Path(assets_root)

    # ══════════════════════════════════════════════════════════════════════
    # Rooms
    # ══════════════════════════════════════════════════════════════════════

    def load_room(self, path: Path) -> "Room":
        """Parse a single room JSON file → Room instance.

        Calls load_world_object() for each entry in the 'objects' list.
        """
        ...

    def load_all_rooms(self) -> dict[str, "Room"]:
        """Load every .json in assets/rooms/ → {room_id: Room}.

        room_id is taken from the 'id' field inside each file.
        """
        ...

    def load_world_object(self, data: dict) -> "WorldObject":
        """Parse an object sub-dict (embedded in a room JSON) → WorldObject.

        Handles nested 'objects' lists for containers recursively.
        """
        ...

    # ══════════════════════════════════════════════════════════════════════
    # Items
    # ══════════════════════════════════════════════════════════════════════

    def load_item(self, path: Path) -> "EquippableItem":
        """Parse a single item JSON file → EquippableItem.

        Also parses the 'abilities' list inside the item.
        """
        ...

    def load_all_items(self) -> dict[str, "EquippableItem"]:
        """Load every .json in assets/items/ → {item_id: EquippableItem}."""
        ...

    # ══════════════════════════════════════════════════════════════════════
    # Abilities
    # ══════════════════════════════════════════════════════════════════════

    def load_ability(self, data: dict) -> "Ability":
        """Parse an ability sub-dict → Ability.

        The 'execute' callable is NOT wired here (pure data layer).
        Wire execute callbacks in a separate AbilityRegistry at startup.
        """
        ...

    def load_ability_file(self, path: Path) -> dict[str, dict]:
        """Parse an ability JSON file → {ability_id: raw_dict}.

        Use this to populate an AbilityRegistry.
        """
        ...

    # ══════════════════════════════════════════════════════════════════════
    # Enemies
    # ══════════════════════════════════════════════════════════════════════

    def load_enemy_template(self, path: Path) -> dict:
        """Parse a single enemy JSON file → raw template dict.

        Templates are blueprints; call instantiate_enemy() to create live instances.
        """
        ...

    def load_all_enemy_templates(self) -> dict[str, dict]:
        """Load every .json in assets/enemies/ → {enemy_id: template_dict}."""
        ...

    def instantiate_enemy(self, template_id: str,
                          templates: dict[str, dict]) -> "Enemy":
        """Create a fresh Enemy instance from a template.

        Copies stats so each instance is independent (separate HP pools, etc.).
        Raises KeyError if template_id not found.
        """
        ...

    def instantiate_enemies_for_room(self, spawn_list: list[dict],
                                     templates: dict[str, dict]) -> list["Enemy"]:
        """Process a room's 'enemy_spawns' list → list of Enemy instances.

        Each spawn entry: { "template_id": str, "count": int }
        """
        ...

    # ══════════════════════════════════════════════════════════════════════
    # Character classes
    # ══════════════════════════════════════════════════════════════════════

    def load_class(self, path: Path) -> "CharacterClass":
        """Parse a single class JSON file → CharacterClass.

        Also loads level_unlocks and choice_unlocks into the class object.
        """
        ...

    def load_all_classes(self) -> dict[str, "CharacterClass"]:
        """Load every .json in assets/classes/ → {class_id: CharacterClass}."""
        ...

    # ══════════════════════════════════════════════════════════════════════
    # Commands
    # ══════════════════════════════════════════════════════════════════════

    def load_commands_into(self, registry: "CommandRegistry") -> None:
        """Read assets/commands/commands.json and populate the registry.

        Registers all commands, modifiers, and article rules.
        """
        ...

    # ══════════════════════════════════════════════════════════════════════
    # World assembly
    # ══════════════════════════════════════════════════════════════════════

    def build_world_map(self, enemy_templates: dict[str, dict]) -> "WorldMap":
        """Load all rooms, spawn enemies, wire exits → ready WorldMap.

        Steps:
        1. load_all_rooms()
        2. For each room, instantiate_enemies_for_room()
        3. Wire room.exits (string IDs → validated against loaded room IDs)
        4. Set WorldMap.start_room_id from the room flagged 'is_start: true'
        """
        ...

    # ══════════════════════════════════════════════════════════════════════
    # Validation
    # ══════════════════════════════════════════════════════════════════════

    def validate_room(self, data: dict) -> list[str]:
        """Return a list of schema error strings. Empty list = valid."""
        ...

    def validate_item(self, data: dict) -> list[str]:
        ...

    def validate_enemy(self, data: dict) -> list[str]:
        ...

    def validate_class(self, data: dict) -> list[str]:
        ...

    def validate_all(self) -> dict[str, list[str]]:
        """Run all validators across all asset files.

        Returns { filepath: [error_strings] } for any file with errors.
        Use at startup to catch JSON mistakes early.
        """
        ...

    # ══════════════════════════════════════════════════════════════════════
    # Internal helpers
    # ══════════════════════════════════════════════════════════════════════

    def _read_json(self, path: Path) -> dict:
        """Open and parse a JSON file. Raises with a clear message on failure."""
        ...

    def _glob_json(self, subfolder: str) -> list[Path]:
        """Return sorted list of all .json paths in assets/<subfolder>/."""
        ...

    def _resolve_item_refs(self, item_ids: list[str],
                           item_catalog: dict[str, "EquippableItem"]) -> list["EquippableItem"]:
        """Convert a list of item ID strings → EquippableItem objects.

        Used when assembling class starting_items or room loot.
        Raises KeyError for unknown IDs.
        """
        ...