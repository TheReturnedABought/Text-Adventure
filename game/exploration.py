"""Exploration controller – movement, object interaction, item pickup, cabinet deposit."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from game.commands import CommandContext
from game.window import window
from game.models import EquippableItem
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
                 item_catalog: dict[str, "EquippableItem"] | None = None,
                 debug: bool = False) -> None:
        self.parser = parser
        self.registry = registry
        self.player = player
        self.world = world
        self.puzzle_flags = puzzle_flags or {}
        self.item_catalog = item_catalog or {}
        self._debug = debug

    def _debug_log(self, msg: str) -> None:
        if self._debug:
            print(f"[DEBUG] {msg}")

    def player_input(self, raw: str) -> ExplorationResult:
        self._debug_log(f"player_input({raw})")
        result = ExplorationResult()
        parsed = self.parser.parse(raw, self.player, CommandContext.WORLD)
        if not parsed.valid:
            handled = self._resolve_garnish_rule(raw, result)
            if not handled:
                result.add(parsed.error or "Invalid command.")
            self._apply_turn_passives(result)
            aggressors = self.world.enemies_visible_from_current()
            if aggressors:
                result.combat_triggered = True
                result.aggressors = aggressors
            else:
                result.lines.extend(self.world.step_enemy_outside_combat(self.world.current_room_id))
            return result

        intent = (parsed.intent or "").lower()
        if intent == "go":
            self._resolve_go(parsed, result)
        elif intent == "look":
            self._resolve_look(parsed, result)
        elif intent in {"open", "close", "unlock", "smash", "push", "pull", "move_object", "move"}:
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
        elif intent == "read":
            self._resolve_read(parsed, result)
        elif intent == "compass":
            self._resolve_compass(result)
        elif self._resolve_data_rule(parsed, result):
            pass
        else:
            result.add("Nothing happens.")

        self._apply_turn_passives(result)

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
        if not ok:
            result.add(msg)
            return
        result.add(msg)
        room = self.world.current_room()
        if room and room.light_level > 7:
            shield = self.player.equipped.get("offhand")
            if shield and "mirror_shield" in shield.item_flags:
                revealed = 0
                for obj in room.objects.values():
                    if obj.hidden:
                        obj.hidden = False
                        revealed += 1
                if revealed:
                    result.add(f"Mirror Shield gleams and reveals {revealed} hidden object(s).")

    def _resolve_look(self, parsed: "ParsedCommand", result: ExplorationResult) -> None:
        self._debug_log("_resolve_look()")
        room = self.world.current_room()
        if not room:
            result.add("You are nowhere.")
            return
        target = (parsed.target_name or "").strip().lower()
        if not target:
            result.add(room.get_description(verbose=True, turn_number=self.world.turn_counter))
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
        self._debug_log("_resolve_object_command()")
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
        for key, value in obj.set_flags_on_interact.get(parsed.intent or "", {}).items():
            self.puzzle_flags[str(key)] = bool(value)
            self.world.global_flags[str(key)] = bool(value)
        for new_obj in revealed:
            room.add_object(new_obj)
            result.add(f"Revealed: {new_obj.name}.")

    def _resolve_take(self, parsed: "ParsedCommand", result: ExplorationResult) -> None:
        self._debug_log("_resolve_take()")
        room = self.world.current_room()
        if not room:
            result.add("No room loaded.")
            return
        target = (parsed.target_name or "").strip().lower()
        if not target:
            result.add("Take what?")
            return

        # First check items on ground
        matching_id = None
        for item_id in room.items_on_ground:
            if target in item_id.lower():
                matching_id = item_id
                break
        if matching_id:
            item_obj = self.item_catalog.get(matching_id)
            if not item_obj:
                result.add(f"Unknown item: {matching_id}")
                return
            room.items_on_ground.remove(matching_id)
            self.player.pick_up(item_obj)
            result.add(f"Picked up {item_obj.name}.")
            return

        # Then check moveable objects
        obj = room.find_object(target)
        if obj and obj.is_moveable:
            # Convert object to a simple misc item
            item = EquippableItem(
                id=obj.id,
                name=obj.name,
                slot="misc",
                description=obj.description,
                material=obj.material.value,
                readable_text=obj.on_interact.get("read") or obj.on_interact.get("look"),
            )
            if "compass" in item.item_flags:
                if not self.puzzle_flags.get("compass_unlock_shown", False):
                    self.puzzle_flags["compass_unlock_shown"] = True
                    self.world.global_flags["compass_unlock_shown"] = True
                    result.add("You now know how to use 'compass' (or 'exits') to check your bearings.")
            # Remove object from room
            del room.objects[obj.id]
            # Add to player inventory
            self.player.inventory.append(item)
            result.add(f"Picked up {obj.name}.")

            # Remove the description snippet so the placeholder becomes empty
            for key in (obj.id, f"{obj.id}_desc"):
                if key in room.description_snippets:
                    room.description_snippets[key] = ""
            return

        if obj and not obj.is_moveable:
            result.add(f"You cannot take the {obj.name}; it's fixed in place.")
            return

        result.add("No such item on the ground or moveable object here.")

    def _resolve_put(self, parsed: "ParsedCommand", result: ExplorationResult) -> None:
        """Put an item into a container (like the cabinet)."""
        room = self.world.current_room()
        if not room:
            result.add("No room loaded.")
            return

        target = (parsed.target_name or "").strip().lower()
        if not target:
            result.add("Put what where?")
            return

        # Expect format: "item in container"
        parts = re.split(r'\s+(?:in|into)\s+', target, maxsplit=1)
        if len(parts) != 2:
            result.add("Usage: put <item> in <container>")
            return
        item_name, container_name = parts[0].strip(), parts[1].strip()

        # Find container object
        container = room.find_object(container_name)
        if not container or not container.is_container:
            result.add(f"There is no container named '{container_name}' here.")
            return

        # Find item in inventory
        item = self.player.find_in_inventory(item_name)
        if not item:
            result.add(f"You don't have '{item_name}'.")
            return

        # Deposit logic (special handling for cabinet)
        if container.id == "cabinet":
            # Add double score
            self.player.add_score(item.value * 2)
            result.add(f"You deposit {item.name} into the cabinet. +{item.value * 2} score!")
            # Add to cabinet's items_inside list (for persistence)
            if item.id not in container.items_inside:
                container.items_inside.append(item.id)
            # Remove from player inventory
            self.player.inventory.remove(item)
            # Update room description snippet to show cabinet contents
            if container.items_inside:
                contents_str = ", ".join(container.items_inside)
                container.description_snippets["contents"] = contents_str
            else:
                container.description_snippets["contents"] = "nothing"
            return

        # Generic container handling
        result.add(f"You put the {item.name} into the {container.name}, but nothing special happens.")

    def _resolve_data_rule(self, parsed: "ParsedCommand", result: ExplorationResult) -> bool:
        room = self.world.current_room()
        if not room:
            return False
        rule = room.find_matching_rule(parsed.intent or "", parsed.target_name)
        if not rule:
            return False

        if not self._check_rule_requirements(rule, result):
            return True

        text = rule.get("text")
        if text:
            result.add(str(text))

        for object_id in rule.get("reveal_objects", []):
            if object_id in room.objects:
                room.objects[object_id].hidden = False
                result.add(f"You reveal {room.objects[object_id].name}.")

        for item_id in rule.get("spawn_items", []):
            if item_id not in room.items_on_ground:
                room.items_on_ground.append(item_id)

        for direction, target_room in rule.get("set_exits", {}).items():
            room.exits[str(direction).lower()] = str(target_room)

        for direction in rule.get("remove_exits", []):
            room.exits.pop(str(direction).lower(), None)

        for key, value in rule.get("set_flags", {}).items():
            self.puzzle_flags[str(key)] = value
            self.world.global_flags[str(key)] = bool(value)

        return True

    def _check_rule_requirements(self, rule: dict, result: ExplorationResult) -> bool:
        req = rule.get("requires", {}) or {}
        min_level = int(req.get("min_level", 0) or 0)
        if self.player.level < min_level:
            result.add(rule.get("blocked_text", f"You need to be level {min_level} to do that."))
            return False

        class_req = req.get("class")
        class_id = getattr(getattr(self.player, "char_class", None), "id", None)
        if class_req and class_id != class_req:
            result.add(rule.get("blocked_text", "You are not trained for that."))
            return False
        return True

    def _resolve_garnish_rule(self, raw: str, result: ExplorationResult) -> bool:
        room = self.world.current_room()
        if not room:
            return False

        words = [w for w in str(raw or "").strip().lower().split() if w]
        if not words:
            return False
        command = words[0]
        ignored = {"the", "a", "an", "to", "at", "on", "with", "into"}
        target_words = [w for w in words[1:] if w not in ignored]
        target = " ".join(target_words).strip()
        rule = room.find_matching_rule(command, target or None)
        if rule:
            if not self._check_rule_requirements(rule, result):
                return True
            text = str(rule.get("text") or "").strip()
            if text:
                result.add(text)
            else:
                result.add("Nothing remarkable happens.")
            return True

        if target:
            obj = room.find_object(target)
            if obj:
                result.add(f"You try to {command} the {obj.name}, but nothing interesting happens.")
                return True
        elif command in {"pray", "sing", "dance", "kneel", "wave", "kiss"}:
            result.add(f"You {command} for a moment. The world keeps its own counsel.")
            return True
        return False

    def _resolve_drop(self, parsed: "ParsedCommand", result: ExplorationResult) -> None:
        self._debug_log("_resolve_drop()")
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
        self._debug_log("_resolve_equip()")
        item_name = parsed.item_name or parsed.target_name
        if not item_name:
            result.add("Equip what?")
            return
        result.add(self.player.equip(item_name))

    def _resolve_unequip(self, parsed: "ParsedCommand", result: ExplorationResult) -> None:
        self._debug_log("_resolve_unequip()")
        slot = parsed.target_name or ""
        if not slot:
            result.add("Unequip which slot?")
            return
        result.add(self.player.unequip(slot))

    def _resolve_inventory(self, result: ExplorationResult) -> None:
        self._debug_log("_resolve_inventory()")
        result.add(self.player.inventory_summary())

    def _resolve_help(self, result: ExplorationResult) -> None:
        self._debug_log("_resolve_help()")
        cmds = self.registry.available_for(self.player, CommandContext.WORLD)
        if not cmds:
            result.add("No exploration commands available.")
            return
        result.add("Available commands: " + ", ".join(sorted(c.name for c in cmds)))

    def _resolve_read(self, parsed: "ParsedCommand", result: ExplorationResult) -> None:
        """Read a readable object in the room (object, ground item, inventory, equipped)."""
        room = self.world.current_room()
        if not room:
            result.add("No room loaded.")
            return
        target = (parsed.target_name or "").strip().lower()
        if not target:
            result.add("Read what?")
            return
        obj = room.find_object(target)
        if obj:
            text = obj.on_interact.get("read") or obj.on_interact.get("look")
            if text:
                result.add(text)
                return

        for item_id in room.items_on_ground:
            if target in item_id.lower():
                item = self.item_catalog.get(item_id)
                if item:
                    text = getattr(item, "readable_text", None) or item.description
                    if text:
                        result.add(text)
                        return
                else:
                    result.add(f"Unknown item: {item_id}")
                    return

        item = self.player.find_in_inventory(target)
        if item:
            text = getattr(item, "readable_text", None) or item.description
            if text:
                result.add(text)
                return

        for equipped_item in self.player.equipped.values():
            if target in equipped_item.name.lower():
                text = getattr(equipped_item, "readable_text", None) or equipped_item.description
                if text:
                    result.add(text)
                    return

        result.add("You don't see that here.")

    def _apply_turn_passives(self, result: ExplorationResult) -> None:
        room = self.world.current_room()
        if not room:
            return
        for item in self.player.equipped.values():
            if "beasts_heart" in item.item_flags and (room.id.startswith("wyrmwood") or room.material.value == "flesh"):
                healed = self.player.heal(1)
                if healed:
                    result.add("Beast's Heart regenerates 1 HP.")
            if "arcane_cloak" in item.item_flags:
                before = self.player.mana
                self.player.mana = min(self.player.max_mana, self.player.mana + 1)
                if self.player.mana > before:
                    result.add("Arcane Cloak restores 1 MP.")

    def _resolve_compass(self, result: ExplorationResult) -> None:
        """Display available exits from current room using the compass."""
        if not self._has_compass():
            result.add("You don't have a compass.")
            return

        room = self.world.current_room()
        if not room:
            result.add("You are nowhere.")
            return

        exits = room.exits
        if not exits:
            result.add("Your compass spins aimlessly – there are no visible exits.")
            return

        dirs = sorted(exits.keys())
        result.add(f"The compass needle points to: {', '.join(dirs)}.")

    def _has_compass(self) -> bool:
        """Return True if player has any item with 'compass' flag."""
        for item in self.player.inventory:
            if "compass" in getattr(item, "item_flags", []):
                return True
        for item in self.player.equipped.values():
            if "compass" in getattr(item, "item_flags", []):
                return True
        return False