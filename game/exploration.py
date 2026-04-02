"""Exploration controller – movement, object interaction, item pickup, puzzle flags."""

from __future__ import annotations

from typing import TYPE_CHECKING

from game.commands import CommandContext

if TYPE_CHECKING:
    from game.entities import Player, Enemy
    from game.models import ParsedCommand, EquippableItem
    from game.world import Room, WorldMap, WorldObject
    from game.parser import CommandParser
    from game.commands import CommandRegistry


class ExplorationResult:
    def __init__(self, lines: list[str] | None = None,
                 combat_triggered: bool = False,
                 aggressors: list["Enemy"] | None = None) -> None:
        self.lines = lines or []
        self.combat_triggered = combat_triggered
        self.aggressors = aggressors or []

    def add(self, line: str) -> None:
        self.lines.append(line)

    def display(self) -> str:
        return "\n".join(self.lines)


class ExplorationController:
    def __init__(self, parser: "CommandParser", registry: "CommandRegistry",
                 player: "Player", world: "WorldMap",
                 puzzle_flags: dict | None = None,
                 item_catalog: dict[str, "EquippableItem"] | None = None) -> None:
        self.parser = parser
        self.registry = registry
        self.player = player
        self.world = world
        self.puzzle_flags = puzzle_flags or {}  # global puzzle state
        self.item_catalog = item_catalog or {}  # <--- FIX: added item catalog

    def player_input(self, raw: str) -> ExplorationResult:
        result = ExplorationResult()
        parsed = self.parser.parse(raw, self.player, CommandContext.WORLD)
        if not parsed.valid:
            result.add(parsed.error or "Invalid command.")
            return result
        intent = (parsed.intent or "").lower()
        if intent in {"go", "move"}:
            self.resolve_go(parsed, result)
        elif intent == "look":
            self.resolve_look(parsed, result)
        elif intent in {"open", "close", "unlock", "smash", "push", "pull", "move_object"}:
            self.resolve_object_command(parsed, result)
        elif intent == "put":
            self.resolve_put(parsed, result)
        elif intent in {"take", "pickup", "pick"}:
            self.resolve_take(parsed, result)
        elif intent == "drop":
            self.resolve_drop(parsed, result)
        elif intent == "equip":
            self.resolve_equip(parsed, result)
        elif intent == "unequip":
            self.resolve_unequip(parsed, result)
        elif intent in {"inventory", "inv"}:
            self.resolve_inventory(result)
        elif intent == "help":
            self.resolve_help(result)
        else:
            self.resolve_world_combat_command(parsed, result)

        aggressors = self.check_combat_trigger()
        if aggressors:
            result.combat_triggered = True
            result.aggressors = aggressors
        else:
            result.lines.extend(self.world.step_enemy_outside_combat(self.world.current_room_id))
        return result

    def check_combat_trigger(self) -> list["Enemy"]:
        return self.world.enemies_visible_from_current()

    def resolve_go(self, parsed: "ParsedCommand", result: ExplorationResult) -> None:
        direction = (parsed.target_name or "").strip().lower()
        if not direction:
            result.add("Go where?")
            return
        ok, msg = self.world.move_player(direction)
        result.add(msg)
        if ok and self.world.current_room():
            result.add(self.world.current_room().get_description(verbose=True))

    def resolve_look(self, parsed: "ParsedCommand", result: ExplorationResult) -> None:
        room = self.world.current_room()
        if room is None:
            result.add("You are nowhere.")
            return
        target = (parsed.target_name or "").strip().lower()
        if not target:
            result.add(room.get_description(verbose=True))
            return
        if target in room.exits:
            adj = self.world.get_room(room.exits[target])
            result.add(adj.peek_description(room) if adj else "You see nothing that way.")
            return
        obj = self.find_object_in_room(target)
        if obj:
            result.add(obj.examine())
            return
        result.add("You don't see that.")

    def resolve_object_command(self, parsed: "ParsedCommand", result: ExplorationResult) -> None:
        room = self.world.current_room()
        if room is None:
            result.add("No room loaded.")
            return
        if not parsed.target_name:
            result.add("Target what?")
            return
        obj = self.find_object_in_room(parsed.target_name)
        if obj is None:
            result.add("No such object here.")
            return
        ok, reason = obj.can_interact_with(parsed.intent or "", self.player)
        if not ok:
            result.add(reason)
            return
        text, revealed = obj.interact(parsed.intent or "", self.player, room)
        result.add(text)
        for new_obj in revealed:
            room.add_object(new_obj)
            result.add(f"Revealed: {new_obj.name}.")

    def resolve_take(self, parsed: "ParsedCommand", result: ExplorationResult) -> None:
        """Take item from ground and add EquippableItem to inventory."""
        room = self.world.current_room()
        if room is None:
            result.add("No room loaded.")
            return
        target = (parsed.target_name or "").strip().lower()
        if not target:
            result.add("Take what?")
            return

        # Find matching item ID in room.items_on_ground
        matching_id = None
        for item_id in room.items_on_ground:
            if target in item_id.lower():
                matching_id = item_id
                break

        if not matching_id:
            result.add("No such item on the ground.")
            return

        # Retrieve actual EquippableItem from catalog
        item_obj = self.item_catalog.get(matching_id)
        if not item_obj:
            result.add(f"Unknown item: {matching_id}")
            return

        room.items_on_ground.remove(matching_id)
        self.player.pick_up(item_obj)  # <--- FIX: use pick_up method
        result.add(f"Picked up {item_obj.name}.")

    def resolve_drop(self, parsed: "ParsedCommand", result: ExplorationResult) -> None:
        room = self.world.current_room()
        if room is None:
            result.add("No room loaded.")
            return
        if not parsed.target_name:
            result.add("Drop what?")
            return
        item, msg = self.player.drop(parsed.target_name)
        result.add(msg)
        if item is not None:
            # Store the actual EquippableItem object on the ground
            room.items_on_ground.append(item.id)   # store ID, not object

    def resolve_equip(self, parsed: "ParsedCommand", result: ExplorationResult) -> None:
        item_name = parsed.item_name or parsed.target_name
        if not item_name:
            result.add("Equip what?")
            return
        result.add(self.player.equip(item_name))

    def resolve_unequip(self, parsed: "ParsedCommand", result: ExplorationResult) -> None:
        slot = parsed.target_name or ""
        if not slot:
            result.add("Unequip which slot?")
            return
        result.add(self.player.unequip(slot))

    def resolve_inventory(self, result: ExplorationResult) -> None:
        result.add(self.player.inventory_summary())

    def resolve_put(self, parsed: "ParsedCommand", result: ExplorationResult) -> None:
        # Stub – can be expanded
        result.add("Put command not fully implemented yet.")

    def resolve_world_combat_command(self, parsed: "ParsedCommand", result: ExplorationResult) -> None:
        if parsed.intent == "smash":
            self.resolve_object_command(parsed, result)
        else:
            result.add("Nothing happens.")

    def find_object_in_room(self, name: str) -> "WorldObject | None":
        room = self.world.current_room()
        return room.find_object(name) if room else None

    def find_container_in_room(self, name: str) -> "WorldObject | None":
        room = self.world.current_room()
        if room is None:
            return None
        obj = room.find_object(name)
        return obj if obj and obj.is_container else None

    def resolve_help(self, result: ExplorationResult) -> None:
        cmds = self.registry.available_for(self.player, CommandContext.WORLD)
        if not cmds:
            result.add("No exploration commands available.")
            return
        result.add("Available commands: " + ", ".join(sorted(c.name for c in cmds)))