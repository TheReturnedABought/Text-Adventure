from __future__ import annotations

from typing import TYPE_CHECKING

from game.commands import CommandContext

if TYPE_CHECKING:
    from game.entities import Player, Enemy
    from game.models import ParsedCommand
    from game.world import Room, WorldMap, WorldObject
    from game.parser import CommandParser
    from game.commands import CommandRegistry


class ExplorationResult:
    """Result of one exploration command."""

    def __init__(self, lines: list[str] | None = None,
                 combat_triggered: bool = False,
                 aggressors: list["Enemy"] | None = None) -> None:
        self.lines: list[str] = lines or []
        self.combat_triggered: bool = combat_triggered
        self.aggressors: list["Enemy"] = aggressors or []

    def add(self, line: str) -> None:
        self.lines.append(line)

    def display(self) -> str:
        return "\n".join(self.lines)


class ExplorationController:
    """Handles all world-state interactions outside of active combat.

    Manages movement, object interaction, item pickup/drop, and the
    line-of-sight combat trigger when enemies notice the player.
    """

    def __init__(self, parser: "CommandParser", registry: "CommandRegistry",
                 player: "Player", world: "WorldMap") -> None:
        self.parser = parser
        self.registry = registry
        self.player = player
        self.world = world

    # ══════════════════════════════════════════════════════════════════════
    # Public API (called by game.py loop)
    # ══════════════════════════════════════════════════════════════════════

    def player_input(self, raw: str) -> ExplorationResult:
        """Parse and route one exploration command.

        Always checks for line-of-sight combat trigger after the action.
        Returns ExplorationResult with combat_triggered=True if enemies spotted.
        """
        ...

    def check_combat_trigger(self) -> list["Enemy"]:
        """Scan line-of-sight rooms and current room for living enemies.

        Returns list of enemies that 'notice' the player (triggers combat).
        Called after every action and after every room transition.
        """
        ...

    # ══════════════════════════════════════════════════════════════════════
    # Movement
    # ══════════════════════════════════════════════════════════════════════

    def resolve_go(self, parsed: "ParsedCommand",
                   result: ExplorationResult) -> None:
        """Move the player in the specified direction.

        1. world.move_player(direction).
        2. On success: print room description.
        3. Check combat trigger in new room.
        """
        ...

    def resolve_look(self, parsed: "ParsedCommand",
                     result: ExplorationResult) -> None:
        """'Look' / 'look at <object>' / 'look <direction>'.

        No target → full room description.
        Direction target → peek_description() of adjacent room (does NOT move player).
        Object target → object.examine().
        """
        ...

    # ══════════════════════════════════════════════════════════════════════
    # Object interaction
    # ══════════════════════════════════════════════════════════════════════

    def resolve_object_command(self, parsed: "ParsedCommand",
                               result: ExplorationResult) -> None:
        """General handler for any command targeted at a WorldObject.

        1. Find the object in the current room (find_object by name).
        2. Call object.can_interact_with() to validate.
        3. Call object.interact() → get (narration, newly_revealed_objects).
        4. Add revealed objects to room.
        5. Trigger any material effects if relevant (e.g. smash in wood room).
        """
        ...

    def resolve_open(self, parsed: "ParsedCommand",
                     result: ExplorationResult) -> None:
        """Open a door, chest, container, or trapdoor."""
        ...

    def resolve_close(self, parsed: "ParsedCommand",
                      result: ExplorationResult) -> None:
        ...

    def resolve_move_object(self, parsed: "ParsedCommand",
                            result: ExplorationResult) -> None:
        """Move / push / pull an object. Triggers reveals if any."""
        ...

    def resolve_smash(self, parsed: "ParsedCommand",
                      result: ExplorationResult) -> None:
        """Attempt to smash an object. Requires command to be unlocked.

        Checks required_commands on the target object.
        Applies material destruction rules.
        """
        ...

    def resolve_unlock(self, parsed: "ParsedCommand",
                       result: ExplorationResult) -> None:
        """Unlock an object using a key item in the player's inventory."""
        ...

    # ══════════════════════════════════════════════════════════════════════
    # Container interaction
    # ══════════════════════════════════════════════════════════════════════

    def resolve_put(self, parsed: "ParsedCommand",
                    result: ExplorationResult) -> None:
        """'put <item> in <container>' – move item from inventory into container."""
        ...

    def resolve_take(self, parsed: "ParsedCommand",
                     result: ExplorationResult) -> None:
        """'take <item> from <container>' OR 'take <item>' from the floor."""
        ...

    def resolve_drop(self, parsed: "ParsedCommand",
                     result: ExplorationResult) -> None:
        """Drop an item from inventory onto the room floor."""
        ...

    # ══════════════════════════════════════════════════════════════════════
    # Equipment
    # ══════════════════════════════════════════════════════════════════════

    def resolve_equip(self, parsed: "ParsedCommand",
                      result: ExplorationResult) -> None:
        """Equip an item from inventory (no AP cost outside combat)."""
        ...

    def resolve_unequip(self, parsed: "ParsedCommand",
                        result: ExplorationResult) -> None:
        """Unequip an item to inventory."""
        ...

    def resolve_inventory(self, result: ExplorationResult) -> None:
        """Print full inventory summary."""
        ...

    # ══════════════════════════════════════════════════════════════════════
    # World-targeted combat commands (e.g. 'smash the door')
    # ══════════════════════════════════════════════════════════════════════

    def resolve_world_combat_command(self, parsed: "ParsedCommand",
                                     result: ExplorationResult) -> None:
        """Handle commands tagged 'destructive' used against world objects.

        These commands work like combat attacks but target WorldObjects.
        Checks object.required_commands for level/class gates.
        Applies structural damage; may destroy the object or trigger reveals.
        """
        ...

    # ══════════════════════════════════════════════════════════════════════
    # Helpers
    # ══════════════════════════════════════════════════════════════════════

    def find_object_in_room(self, name: str) -> "WorldObject | None":
        """Delegate to current room's find_object()."""
        ...

    def find_container_in_room(self, name: str) -> "WorldObject | None":
        """Find a container object by name."""
        ...

    def resolve_help(self, result: ExplorationResult) -> None:
        """Print available exploration commands for this player."""
        ...