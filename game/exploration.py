"""Exploration controller – movement, object interaction, item pickup."""

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
        self.puzzle_flags = puzzle_flags or {}
        self.item_catalog = item_catalog or {}

    def player_input(self, raw: str) -> ExplorationResult:
        result = ExplorationResult()
        parsed = self.parser.parse(raw, self.player, CommandContext.WORLD)
        if not parsed.valid:
            result.add(parsed.error or "Invalid command.")
            return result

        intent = (parsed.intent or "").lower()
        if intent in {"go", "move"}:
            self._resolve_go(parsed, result)
        elif intent == "look":
            self._resolve_look(parsed, result)
        elif intent in {"open", "close", "unlock", "smash", "push", "pull", "move_object"}:
            self._resolve_object_command(parsed, result)
        elif intent == "put":
            self._resolve_put(parsed, result)
        elif intent in {"take", "pickup", "pick"}:
            self._resolve_take(parsed, result)
        elif intent == "drop":
            self._resolve_drop(parsed, result)
        elif intent == "equip":
            self._resolve_equip(parsed, result)
        elif intent == "unequip":
            self._resolve_unequip(parsed, result)
        elif intent in {"inventory", "inv"}:
            self._resolve_inventory(result)
        elif intent == "help":
            self._resolve_help(result)
        else:
            result.add("Nothing happens.")

        # Check for combat trigger
        aggressors = self.world.enemies_visible_from_current()
        if aggressors:
            result.combat_triggered = True
            result.aggressors = aggressors
        else:
            result.lines.extend(self.world.step_enemy_outside_combat(self.world.current_room_id))
        return result

    def _resolve_go(self, parsed: "ParsedCommand", result: ExplorationResult) -> None:
        direction = (parsed.target_name or "").strip().lower()
        if not direction:
            result.add("Go where?")
            return
        ok, msg = self.world.move_player(direction)
        result.add(msg)
        if ok and self.world.current_room():
            result.add(self.world.current_room().get_description(verbose=True))

    def _resolve_look(self, parsed: "ParsedCommand", result: ExplorationResult) -> None:
        room = self.world.current_room()
        if not room:
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
        obj = room.find_object(target)
        if obj:
            result.add(obj.examine())
            return
        result.add("You don't see that.")

    def _resolve_object_command(self, parsed: "ParsedCommand", result: ExplorationResult) -> None:
        room = self.world.current_room()
        if not room:
            result.add("No room loaded.")
            return
        if not parsed.target_name:
            result.add("Target what?")
            return
        obj = room.find_object(parsed.target_name)
        if not obj:
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

    def _resolve_take(self, parsed: "ParsedCommand", result: ExplorationResult) -> None:
        room = self.world.current_room()
        if not room:
            result.add("No room loaded.")
            return
        target = (parsed.target_name or "").strip().lower()
        if not target:
            result.add("Take what?")
            return
        matching_id = None
        for item_id in room.items_on_ground:
            if target in item_id.lower():
                matching_id = item_id
                break
        if not matching_id:
            result.add("No such item on the ground.")
            return
        item_obj = self.item_catalog.get(matching_id)
        if not item_obj:
            result.add(f"Unknown item: {matching_id}")
            return
        room.items_on_ground.remove(matching_id)
        self.player.pick_up(item_obj)
        result.add(f"Picked up {item_obj.name}.")

    def _resolve_drop(self, parsed: "ParsedCommand", result: ExplorationResult) -> None:
        room = self.world.current_room()
        if not room:
            result.add("No room loaded.")
            return
        if not parsed.target_name:
            result.add("Drop what?")
            return
        item, msg = self.player.drop(parsed.target_name)
        result.add(msg)
        if item:
            room.items_on_ground.append(item.id)

    def _resolve_equip(self, parsed: "ParsedCommand", result: ExplorationResult) -> None:
        item_name = parsed.item_name or parsed.target_name
        if not item_name:
            result.add("Equip what?")
            return
        result.add(self.player.equip(item_name))

    def _resolve_unequip(self, parsed: "ParsedCommand", result: ExplorationResult) -> None:
        slot = parsed.target_name or ""
        if not slot:
            result.add("Unequip which slot?")
            return
        result.add(self.player.unequip(slot))

    def _resolve_inventory(self, result: ExplorationResult) -> None:
        result.add(self.player.inventory_summary())

    def _resolve_put(self, parsed: "ParsedCommand", result: ExplorationResult) -> None:
        result.add("Put command not fully implemented yet.")

    def _resolve_help(self, result: ExplorationResult) -> None:
        cmds = self.registry.available_for(self.player, CommandContext.WORLD)
        if not cmds:
            result.add("No exploration commands available.")
            return
        result.add("Available commands: " + ", ".join(sorted(c.name for c in cmds)))