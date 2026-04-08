# game/exploration.py
import re
from typing import List, Optional

from game.commands import CommandContext
from game.entities import Player, Enemy
from game.models import ParsedCommand, EquippableItem
from game.world import Room, WorldMap, WorldObject, apply_turn_passives
from game.parser import CommandParser
from game.commands import CommandRegistry
from game.window import window


class ExplorationResult:
    def __init__(self, lines=None, combat_triggered=False, aggressors=None):
        self.lines = lines or []
        self.combat_triggered = combat_triggered
        self.aggressors = aggressors or []

    def add(self, line: str):
        self.lines.append(line)

    def display(self) -> str:
        return "\n".join(self.lines)


class ExplorationController:
    def __init__(self, parser: CommandParser, registry: CommandRegistry, player: Player, world: WorldMap,
                 puzzle_flags=None, item_catalog=None, debug=False):
        self.parser = parser
        self.registry = registry
        self.player = player
        self.world = world
        self.puzzle_flags = puzzle_flags or {}
        self.item_catalog = item_catalog or {}
        self._handlers = {
            "go": self._go,
            "look": self._look,
            "open": self._object_command,
            "close": self._object_command,
            "unlock": self._object_command,
            "smash": self._object_command,
            "push": self._object_command,
            "pull": self._object_command,
            "move": self._object_command,
            "move_object": self._object_command,
            "put": self._put,
            "take": self._take,
            "drop": self._drop,
            "equip": self._equip,
            "unequip": self._unequip,
            "inventory": self._inventory,
            "help": self._help,
            "read": self._read,
            "compass": self._compass
        }

    def player_input(self, raw: str) -> ExplorationResult:
        result = ExplorationResult()
        parsed = self.parser.parse(raw, self.player, CommandContext.WORLD)
        if not parsed.valid:
            if not self._resolve_garnish_rule(raw, result):
                result.add(parsed.error or "Invalid command.")
            # Early return: do NOT process passives, enemy movement, or combat on invalid input
            return result

        intent = (parsed.intent or "").lower()
        handler = self._handlers.get(intent)
        if handler:
            handler(parsed, result)
        else:
            if not self._resolve_data_rule(parsed, result) and not self._resolve_garnish_rule(raw, result):
                result.add("Nothing happens.")

        for line in apply_turn_passives(self.player, self.world, self.world.current_room_id):
            result.add(line)

        aggressors = self._visible_enemies_including_los()
        if aggressors:
            result.combat_triggered = True
            result.aggressors = aggressors
        else:
            result.lines.extend(self.world.step_enemy_outside_combat(self.world.current_room_id))

        return result

    def _visible_enemies_including_los(self) -> List[Enemy]:
        """Return all alive enemies that are either in the current room or in
        a room that is in the current room's line_of_sight (and where light
        level permits visibility)."""
        room = self.world.current_room()
        if not room:
            return []

        # enemies in the same room (already filtered by light)
        enemies = self.world.enemies_visible_from_current()

        # also check line-of-sight rooms
        for other_id in room.line_of_sight:
            other = self.world.get_room(other_id)
            if other and other.light_level > 1:  # can see into that room
                for e in other.enemies:
                    if e.is_alive:
                        enemies.append(e)

        # remove duplicates (if an enemy somehow appears twice)
        seen = set()
        unique = []
        for e in enemies:
            if id(e) not in seen:
                seen.add(id(e))
                unique.append(e)
        return unique

    def _go(self, parsed: ParsedCommand, result: ExplorationResult):
        direction = (parsed.target_name or "").strip().lower()
        if not direction:
            result.add("Go where?")
            return
        ok, msg = self.world.move_player(direction)
        result.add(msg)
        if ok:
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

    def _look(self, parsed: ParsedCommand, result: ExplorationResult):
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

    def _object_command(self, parsed: ParsedCommand, result: ExplorationResult):
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

    def _take(self, parsed: ParsedCommand, result: ExplorationResult):
        room = self.world.current_room()
        if not room:
            result.add("No room loaded.")
            return
        target = (parsed.target_name or "").strip().lower()
        if not target:
            result.add("Take what?")
            return
        # item on ground
        for item_id in room.items_on_ground:
            if target in item_id.lower():
                item = self.item_catalog.get(item_id)
                if item:
                    room.items_on_ground.remove(item_id)
                    self.player.pick_up(item)
                    result.add(f"Picked up {item.name}.")
                    return
                else:
                    result.add(f"Unknown item: {item_id}")
                    return
        # moveable object
        obj = room.find_object(target)
        if obj and obj.is_moveable:
            item = EquippableItem(
                id=obj.id, name=obj.name, slot="misc", description=obj.description,
                material=obj.material.value, readable_text=obj.on_interact.get("read") or obj.on_interact.get("look")
            )
            if "compass" in item.item_flags:
                if not self.puzzle_flags.get("compass_unlock_shown", False):
                    self.puzzle_flags["compass_unlock_shown"] = True
                    self.world.global_flags["compass_unlock_shown"] = True
                    result.add("You now know how to use 'compass' (or 'exits') to check your bearings.")
            del room.objects[obj.id]
            self.player.inventory.append(item)
            result.add(f"Picked up {obj.name}.")
            for key in (obj.id, f"{obj.id}_desc"):
                if key in room.description_snippets:
                    room.description_snippets[key] = ""
            return
        if obj and not obj.is_moveable:
            result.add(f"You cannot take the {obj.name}; it's fixed in place.")
            return
        result.add("No such item on the ground or moveable object here.")

    def _put(self, parsed: ParsedCommand, result: ExplorationResult):
        room = self.world.current_room()
        if not room:
            result.add("No room loaded.")
            return
        target = (parsed.target_name or "").strip().lower()
        if not target:
            result.add("Put what where?")
            return
        parts = re.split(r'\s+(?:in|into)\s+', target, maxsplit=1)
        if len(parts) != 2:
            result.add("Usage: put <item> in <container>")
            return
        item_name, container_name = parts[0].strip(), parts[1].strip()
        container = room.find_object(container_name)
        if not container or not container.is_container:
            result.add(f"There is no container named '{container_name}' here.")
            return
        item = self.player.find_in_inventory(item_name)
        if not item:
            result.add(f"You don't have '{item_name}'.")
            return
        if container.id == "cabinet":
            self.player.add_score(item.value * 2)
            result.add(f"You deposit {item.name} into the cabinet. +{item.value * 2} score!")
            if item.id not in container.items_inside:
                container.items_inside.append(item.id)
            self.player.inventory.remove(item)
            contents_str = ", ".join(container.items_inside) if container.items_inside else "nothing"
            container.description_snippets["contents"] = contents_str
            return
        result.add(f"You put the {item.name} into the {container.name}, but nothing special happens.")

    def _drop(self, parsed: ParsedCommand, result: ExplorationResult):
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

    def _equip(self, parsed: ParsedCommand, result: ExplorationResult):
        item_name = parsed.item_name or parsed.target_name
        if not item_name:
            result.add("Equip what?")
            return
        result.add(self.player.equip(item_name))

    def _unequip(self, parsed: ParsedCommand, result: ExplorationResult):
        slot = parsed.target_name or ""
        if not slot:
            result.add("Unequip which slot?")
            return
        result.add(self.player.unequip(slot))

    def _inventory(self, parsed: ParsedCommand, result: ExplorationResult):
        result.add(self.player.inventory_summary())

    def _help(self, parsed: ParsedCommand, result: ExplorationResult):
        cmds = self.registry.available_for(self.player, CommandContext.WORLD)
        if not cmds:
            result.add("No exploration commands available.")
        else:
            result.add("Available commands: " + ", ".join(sorted(c.name for c in cmds)))

    def _read(self, parsed: ParsedCommand, result: ExplorationResult):
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
                else:
                    text = None
                if text:
                    result.add(text)
                    return
                else:
                    result.add(f"Unknown item: {item_id}")
                    return
        item = self.player.find_in_inventory(target)
        if item:
            text = getattr(item, "readable_text", None) or item.description
        else:
            for equipped in self.player.equipped.values():
                if target in equipped.name.lower():
                    item = equipped
                    break
            text = getattr(item, "readable_text", None) or item.description if item else None
        if text:
            result.add(text)
            return
        result.add("You don't see that here.")

    def _compass(self, parsed: ParsedCommand, result: ExplorationResult):
        if not any("compass" in it.item_flags for it in self.player.inventory + list(self.player.equipped.values())):
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
        result.add(f"The compass needle points to: {', '.join(sorted(exits.keys()))}.")

    def _resolve_data_rule(self, parsed: ParsedCommand, result: ExplorationResult) -> bool:
        room = self.world.current_room()
        if not room:
            return False
        rule = room.find_matching_rule(parsed.intent or "", parsed.target_name)
        if not rule:
            return False
        req = rule.get("requires", {}) or {}
        if self.player.level < int(req.get("min_level", 0)):
            result.add(rule.get("blocked_text", f"You need to be level {req['min_level']} to do that."))
            return True
        class_req = req.get("class")
        class_id = getattr(getattr(self.player, "char_class", None), "id", None)
        if class_req and class_id != class_req:
            result.add(rule.get("blocked_text", "You are not trained for that."))
            return True
        text = rule.get("text")
        if text:
            result.add(str(text))
        for obj_id in rule.get("reveal_objects", []):
            if obj_id in room.objects:
                room.objects[obj_id].hidden = False
                result.add(f"You reveal {room.objects[obj_id].name}.")
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
            req = rule.get("requires", {}) or {}
            if self.player.level < int(req.get("min_level", 0)):
                result.add(rule.get("blocked_text", f"You need to be level {req['min_level']} to do that."))
                return True
            class_req = req.get("class")
            class_id = getattr(getattr(self.player, "char_class", None), "id", None)
            if class_req and class_id != class_req:
                result.add(rule.get("blocked_text", "You are not trained for that."))
                return True
            text = str(rule.get("text") or "").strip()
            result.add(text if text else "Nothing remarkable happens.")
            return True
        if target:
            obj = room.find_object(target)
            if obj:
                result.add(f"You try to {command} the {obj.name}, but nothing interesting happens.")
                return True
        elif command in {"pray", "sing", "dance", "kneel", "wave"}:
            result.add(f"You {command} for a moment. The world keeps its own counsel.")
            return True
        return False