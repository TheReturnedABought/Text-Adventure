"""Combat controller – turn order, AP costs, targeting, zone-based LOS.

Enemies can enter/leave combat based on line of sight (combat zone).
Ranged attacks target any visible room; melee requires same room.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING

from game.commands import CommandContext
from game.dice import DiceExpression
from game.effects import EffectTrigger, EffectCategory, StatusEffect
from game.models import ParsedCommand, ArticleType
from game.world import DamageType, Material, coerce_damage_type, resolve_material_interaction
from game.window import window

if TYPE_CHECKING:
    from game.entities import Enemy, Player
    from game.parser import CommandParser
    from game.commands import CommandRegistry, CommandDefinition
    from game.world import WorldMap


class CombatOutcome(Enum):
    ONGOING = auto()
    PLAYER_WON = auto()
    PLAYER_FLED = auto()
    PLAYER_DEFEATED = auto()


@dataclass
class TurnResult:
    lines: list[str] = field(default_factory=list)
    ap_spent: int = 0
    outcome: CombatOutcome = CombatOutcome.ONGOING

    def add(self, line: str) -> None:
        self.lines.append(line)

    def is_finished(self) -> bool:
        return self.outcome != CombatOutcome.ONGOING

    def display(self) -> str:
        return "\n".join(self.lines)


class CombatController:
    def __init__(self, parser: "CommandParser", registry: "CommandRegistry",
                 player: "Player", enemies: list["Enemy"],
                 world: "WorldMap | None" = None,
                 player_room_id: str | None = None,
                 puzzle_flags: dict | None = None,
                 debug: bool = False) -> None:
        self.parser = parser
        self.registry = registry
        self.player = player
        self.enemies = enemies
        self.world = world
        self.player_room_id = player_room_id
        self.puzzle_flags = puzzle_flags or {}
        self.round = 1
        self.combat_zone: set[str] = set()
        self._pending_disambiguation: list[Enemy] | None = None
        self._pending_attack_parsed: ParsedCommand | None = None
        self._debug = debug
        self._refresh_combat_zone()

    def _debug_log(self, msg: str) -> None:
        if self._debug:
            print(f"[DEBUG] {msg}")

    # ----------------------------------------------------------------------
    # Combat zone management (line of sight)
    # ----------------------------------------------------------------------
    def _refresh_combat_zone(self) -> None:
        self._debug_log("_refresh_combat_zone()")
        if not self.world:
            self.combat_zone = set()
            return
        zone = set()
        for enemy in self.enemies:
            if enemy.is_alive and enemy.combat_room_id:
                zone |= self._zone_from_anchor(enemy.combat_room_id)
        self.combat_zone = zone

    def _zone_from_anchor(self, room_id: str) -> set[str]:
        room = self.world.get_room(room_id) if self.world else None
        if not room:
            return set()
        return {room.id, *room.line_of_sight}

    def _enemy_in_zone(self, enemy: "Enemy") -> bool:
        room_id = enemy.combat_room_id or self.player_room_id
        return not self.combat_zone or room_id in self.combat_zone

    def _eligible_targets(self, ranged: bool) -> list["Enemy"]:
        self._debug_log(f"_eligible_targets(ranged={ranged})")
        living = [e for e in self.enemies if e.is_alive and self._enemy_in_zone(e)]
        if ranged or not self.world:
            return living
        # Melee: only enemies in the same room
        return [e for e in living if e.combat_room_id == self.player_room_id]

    # ----------------------------------------------------------------------
    # Combat flow
    # ----------------------------------------------------------------------
    def start_encounter(self) -> str:
        self._debug_log("start_encounter()")
        self._refresh_combat_zone()
        self._refresh_movement_hints()
        for enemy in self.enemies:
            enemy.reset_ap()
            enemy.plan_turn(self.player)
        return f"Combat begins! You face: {', '.join(e.name for e in self.enemies if e.is_alive)}."

    def _refresh_movement_hints(self) -> None:
        for enemy in self.enemies:
            enemy.movement_hint = self._direction_hint_to_enemy(enemy)

    def player_input(self, raw: str) -> TurnResult:
        self._debug_log(f"player_input({raw})")
        result = TurnResult()

        if self._pending_disambiguation:
            target = self._resolve_disambiguation(raw, result)
            if target is None:
                return result
            if self._pending_attack_parsed is not None:
                parsed = self._pending_attack_parsed
                self._pending_attack_parsed = None
                attack_performed = self._resolve_attack(parsed, result, forced_target=target)
                if attack_performed and result.outcome == CombatOutcome.ONGOING:
                    self.player.spend_ap(parsed.ap_cost)
                    self.player.mana -= parsed.mp_cost
                    result.ap_spent = parsed.ap_cost
                    for line in self.player.tick_effects(EffectTrigger.ON_ACTION):
                        result.add(line)
                    self._refresh_combat_zone()
                result.outcome = self.check_outcome() if result.outcome == CombatOutcome.ONGOING else result.outcome
                if result.outcome == CombatOutcome.ONGOING and self.player.current_ap <= 0:
                    end = self.end_player_turn()
                    result.lines.extend(end.lines)
                    result.outcome = end.outcome
                return result
            result.add(f"Target selected: {target.name}.")
            return result

        parsed = self.parser.parse(raw, self.player, CommandContext.COMBAT)
        if not parsed.valid:
            result.add(parsed.error or "Invalid command.")
            return result
        else:
            cmd = self.registry.get_command(parsed.intent)
            raw_ap = cmd.base_ap_cost if cmd else 0
            print(f"[DEBUG] Raw AP: {raw_ap}, Reduced AP: {parsed.ap_cost}")
        intent = parsed.intent or ""

        # Handle movement if command is "go"
        if intent == "go":
            self._refresh_movement_hints()
            return self._handle_combat_movement(parsed, result)

        if intent in {"status", "look"}:
            self._resolve_status(result)
            return result
        if intent == "help":
            self._resolve_help(result)
            return result
        if intent in {"wait", "end"}:
            return self.end_player_turn()

        if parsed.ap_cost > self.player.current_ap:
            result.add("Not enough AP.")
            return result
        if parsed.mp_cost > getattr(self.player, "mana", 0):
            result.add("Not enough MP.")
            return result

        # Resolve command
        action_performed = False
        if intent in {"attack", "strike", "hit"}:
            action_performed = self._resolve_attack(parsed, result)
        elif intent == "block":
            self._resolve_block(parsed, result)
            action_performed = True
        elif intent in {"ability", "cast", "use"}:
            # Spend AP/MP first (already checked they are sufficient)
            self.player.spend_ap(parsed.ap_cost)
            self.player.mana -= parsed.mp_cost
            result.ap_spent = parsed.ap_cost
            # Resolve ability (returns restoration amounts, adds any non‑restoration messages)
            restore_ap, restore_mp = self._resolve_ability(parsed, result)
            # Apply restoration silently (no messages)
            if restore_ap > 0:
                self.player.current_ap = min(self.player.total_ap, self.player.current_ap + restore_ap)
            if restore_mp > 0:
                self.player.mana = min(self.player.max_mana, self.player.mana + restore_mp)
            action_performed = True
        elif intent == "equip":
            self._resolve_equip(parsed, result)
            action_performed = True
        elif intent == "flee":
            self._resolve_flee(parsed, result)
            action_performed = True
        else:
            result.add("That command has no combat resolver yet.")

        if result.outcome == CombatOutcome.ONGOING and action_performed:
            # For other commands that didn't already spend AP (attack, block, etc.)
            if intent not in {"ability", "cast", "use"}:
                self.player.spend_ap(parsed.ap_cost)
                self.player.mana -= parsed.mp_cost
                result.ap_spent = parsed.ap_cost
            for line in self.player.tick_effects(EffectTrigger.ON_ACTION):
                result.add(line)
            self._refresh_combat_zone()

        result.outcome = self.check_outcome() if result.outcome == CombatOutcome.ONGOING else result.outcome
        if result.outcome == CombatOutcome.ONGOING and self.player.current_ap <= 0:
            end = self.end_player_turn()
            result.lines.extend(end.lines)
            result.outcome = end.outcome
        return result

    def end_player_turn(self) -> TurnResult:
        self._debug_log("end_player_turn()")
        self._refresh_movement_hints()
        result = TurnResult()
        self.player.clear_block()
        for line in self.player.tick_effects(EffectTrigger.ON_TURN_END):
            result.add(line)

        for enemy in [e for e in self.enemies if e.is_alive and self._enemy_in_zone(e)]:
            enemy_result = self._enemy_turn(enemy)
            result.lines.extend(enemy_result.lines)
            if enemy_result.outcome != CombatOutcome.ONGOING:
                result.outcome = enemy_result.outcome
                return result

        self.round += 1
        self.player.reset_ap()
        for enemy in self.enemies:
            enemy.reset_ap()
            enemy.plan_turn(self.player)
        for line in self.player.tick_effects(EffectTrigger.ON_TURN_START):
            result.add(line)
        result.outcome = self.check_outcome()
        return result

    def _enemy_turn(self, enemy: "Enemy") -> TurnResult:
        self._debug_log(f"_enemy_turn({enemy.name})")
        result = TurnResult()
        enemy.clear_block()
        for intent in list(enemy.active_intents):
            if not enemy.is_alive:
                break
            if not enemy.spend_ap(intent.ap_cost):
                continue
            self._resolve_enemy_intent(enemy, intent, result)
            if self.check_outcome() == CombatOutcome.PLAYER_DEFEATED:
                result.outcome = CombatOutcome.PLAYER_DEFEATED
                return result
        for line in enemy.tick_effects(EffectTrigger.ON_TURN_END):
            result.add(line)
        return result

    def check_outcome(self) -> CombatOutcome:
        self._debug_log("check_outcome()")
        if not self.player.is_alive:
            return CombatOutcome.PLAYER_DEFEATED
        if not any(e.is_alive for e in self.enemies):
            return CombatOutcome.PLAYER_WON
        return CombatOutcome.ONGOING

    # ----------------------------------------------------------------------
    # Movement during combat (using parsed command)
    # ----------------------------------------------------------------------
    def _handle_combat_movement(self, parsed: ParsedCommand, result: TurnResult) -> TurnResult:
        direction = parsed.target_name
        if not direction:
            result.add("Go where?")
            return result

        ap_cost = parsed.ap_cost
        if ap_cost > self.player.current_ap:
            result.add("Not enough AP to move.")
            return result

        room = self.world.get_room(self.player_room_id)
        if not room or direction not in room.exits:
            result.add("You cannot go that way.")
            return result

        target_room_id = room.exits[direction]
        will_flee = target_room_id not in self.combat_zone

        if will_flee:
            result.add("You try to flee, but enemies react!")
            # Enemies get a full turn before you leave
            for enemy in [e for e in self.enemies if e.is_alive and self._enemy_in_zone(e)]:
                enemy.reset_ap()
                enemy.plan_turn(self.player)
                free_turn = self._enemy_turn(enemy)
                result.lines.extend(free_turn.lines)
                if free_turn.outcome != CombatOutcome.ONGOING:
                    result.outcome = free_turn.outcome
                    return result

            if self.player.is_alive:
                # Reset AP to full instead of spending
                self.player.current_ap = self.player.total_ap
                result.ap_spent = 0
                self.player_room_id = target_room_id
                self.world.current_room_id = target_room_id
                self._refresh_combat_zone()
                result.add(f"You flee to {target_room_id}.")
                new_room = self.world.current_room()
                if new_room:
                    result.add(new_room.get_description(verbose=False))
                result.outcome = CombatOutcome.PLAYER_FLED
            else:
                result.outcome = CombatOutcome.PLAYER_DEFEATED
            return result

        # Normal move (staying in combat zone) – spend AP as usual
        self.player.spend_ap(ap_cost)
        result.ap_spent = ap_cost
        self.player_room_id = target_room_id
        self.world.current_room_id = target_room_id
        self._refresh_combat_zone()
        result.add(f"You move {direction} ({ap_cost} AP).")
        new_room = self.world.current_room()
        if new_room:
            result.add(new_room.get_description(verbose=False))
        if self.player.current_ap <= 0:
            end = self.end_player_turn()
            result.lines.extend(end.lines)
            result.outcome = end.outcome
        return result

    # ----------------------------------------------------------------------
    # Attack resolution (with damage types & material interactions)
    # ----------------------------------------------------------------------
    def _resolve_attack(self, parsed: ParsedCommand, result: TurnResult, forced_target: "Enemy | None" = None) -> bool:
        self._debug_log("_resolve_attack()")
        target = forced_target or self._resolve_target(parsed, result)
        if target is None:
            self._pending_attack_parsed = parsed
            return False
        self._pending_attack_parsed = None

        cmd = self.registry.get_command(parsed.intent or "attack")
        damage_type = self._get_damage_type(cmd)
        dice = self._build_attack_dice(cmd, parsed)
        total, rolls, mod = dice.roll_with_breakdown()

        # Determine if we are using a specific weapon
        weapon_bonus = 0
        if parsed.item_name:
            weapon_bonus = self.player.weapon_attack_bonus(parsed.item_name)
            if weapon_bonus == 0:
                result.add(f"You don't have '{parsed.item_name}' equipped.")
                return False
            total += weapon_bonus
        else:
            # Use base attack (no weapon bonuses)
            total += self.player.base_attack_value()

        # Apply material interactions
        room_material = self._current_room_material()
        interaction = resolve_material_interaction(damage_type, room_material)
        total = int(total * interaction.damage_multiplier)

        target_material = self._material_from_str(target.material)
        target_interaction = resolve_material_interaction(damage_type, target_material)
        total = int(total * target_interaction.damage_multiplier)

        # Apply enemy-specific vulnerabilities and resistances
        vuln_mult = 2.0 if damage_type.value in target.vulnerabilities else 1.0
        resist_mult = 0.5 if damage_type.value in target.resistances else 1.0
        total = int(total * vuln_mult * resist_mult)

        # Article bonus
        if parsed.article == ArticleType.GENERIC:
            total += self.registry.article_rule.generic_flat_bonus
        elif parsed.article == ArticleType.SPECIFIC:
            total += self.registry.article_rule.specific_flat_bonus

        dealt = target.receive_damage(total)
        result.add(f"You hit {target.name} for {dealt} damage ({self._format_roll(dice, rolls, total)}).")

        # Environmental reaction
        env_lines = self._apply_environmental_reaction(damage_type, target)
        for line in env_lines:
            result.add(line)
        return True

    def _get_damage_type(self, cmd: "CommandDefinition | None") -> DamageType:
        if not cmd:
            return DamageType.SLASHING
        for tag in cmd.tags:
            dt = coerce_damage_type(tag)
            if dt:
                return dt
        return DamageType.SLASHING

    def _current_room_material(self) -> Material:
        if self.world and self.player_room_id:
            room = self.world.get_room(self.player_room_id)
            if room:
                return room.material
        return Material.STONE

    def _material_from_str(self, mat_str: str) -> Material:
        try:
            return Material(mat_str.lower())
        except ValueError:
            return Material.FLESH

    def _apply_environmental_reaction(self, damage_type: DamageType, target: "Enemy") -> list[str]:
        if not self.world or not self.player_room_id:
            return []
        room = self.world.get_room(self.player_room_id)
        if not room:
            return []
        return room.apply_elemental_effect(damage_type.value, self.player)

    # ----------------------------------------------------------------------
    # Other combat actions
    # ----------------------------------------------------------------------
    def _resolve_block(self, parsed: ParsedCommand, result: TurnResult) -> None:
        self._debug_log("_resolve_block()")
        cmd = self.registry.get_command(parsed.intent or "block")
        dice = DiceExpression.parse(cmd.base_dice) if cmd and cmd.base_dice else DiceExpression.flat(max(1, self.player.defense_value()))
        dice = self._apply_modifiers_to_dice(dice, parsed.modifiers)
        block_value = max(0, dice.roll())
        self.player.add_block(block_value)
        result.add(f"You brace yourself, gaining {block_value} block.")

    def _resolve_ability(self, parsed: ParsedCommand, result: TurnResult) -> tuple[int, int]:
        """Returns (restore_ap, restore_mp) after resolving ability effects. No messages for restoration."""
        name = (parsed.item_name or parsed.target_name or "").lower()
        restore_ap = 0
        restore_mp = 0
        for item in self.player.equipped.values():
            for ability in item.abilities:
                if name and name not in ability.name.lower() and name != ability.id.lower():
                    continue
                if ability.dice_expression:
                    dice = DiceExpression.parse(ability.dice_expression)
                    dmg = dice.roll()
                    target = self._resolve_target(parsed, result)
                    if target:
                        dealt = target.receive_damage(dmg)
                        result.add(f"You use {ability.name} and deal {dealt} damage.")
                        if ability.effect_on_hit:
                            effect = StatusEffect(
                                id=ability.effect_on_hit,
                                name=ability.effect_on_hit.capitalize(),
                                description="",
                                trigger=EffectTrigger.ON_TURN_END,
                                category=EffectCategory.DEBUFF,
                                duration=ability.effect_duration,
                                stacks=ability.effect_stacks,
                            )
                            result.add(target.apply_effect(effect))
                else:
                    result.add(f"You use {ability.name}.")
                # Collect restoration values (no messages added here)
                restore_ap = int(ability.payload.get("restore_ap", 0) or 0)
                restore_mp = int(ability.payload.get("restore_mp", 0) or 0)
                return restore_ap, restore_mp
        result.add("No matching ability is equipped.")
        return 0, 0

    def _resolve_equip(self, parsed: ParsedCommand, result: TurnResult) -> None:
        self._debug_log("_resolve_equip()")
        item_name = parsed.item_name or parsed.target_name
        if not item_name:
            result.add("Equip what?")
            return
        result.add(self.player.equip(item_name))

    def _resolve_flee(self, parsed: ParsedCommand, result: TurnResult) -> None:
        self._debug_log("_resolve_flee()")
        if random.random() < 0.5:
            result.add("You successfully flee.")
            result.outcome = CombatOutcome.PLAYER_FLED
        else:
            result.add("You fail to flee!")

    def _resolve_status(self, result: TurnResult) -> None:
        self._debug_log("_resolve_status()")
        result.add(self.player.status_line())
        for enemy in self.enemies:
            if enemy.is_alive:
                result.add(enemy.status_line() + f" | Intents: {enemy.intent_display()}")

    def _resolve_help(self, result: TurnResult) -> None:
        self._debug_log("_resolve_help()")
        cmds = self.registry.available_for(self.player, CommandContext.COMBAT)
        if not cmds:
            result.add("No combat commands available.")
            return
        for cmd in sorted(cmds, key=lambda c: c.name):
            # AP cost for display only – we don't recalc here
            result.add(f"{cmd.name} - {cmd.description}")

    # ----------------------------------------------------------------------
    # Enemy intent resolution
    # ----------------------------------------------------------------------
    def _resolve_enemy_intent(self, enemy: "Enemy", intent, result: TurnResult) -> None:
        self._debug_log(f"_resolve_enemy_intent({enemy.name}, {intent.id})")
        kind = getattr(intent.intent_type, "name", "ATTACK")
        if kind == "ATTACK" and not self._enemy_can_hit_player(enemy, intent):
            if self._enemy_step_toward_player(enemy):
                result.add(f"{enemy.name} advances toward your position.")
            if not self._enemy_can_hit_player(enemy, intent):
                result.add(f"{enemy.name} cannot reach you from there.")
                return

        if kind == "ATTACK":
            dice = DiceExpression.parse(intent.dice_expression) if intent.dice_expression else DiceExpression.flat(enemy.attack)
            dmg = max(0, dice.roll() + enemy.attack)
            dealt = self.player.receive_damage(dmg)
            result.add(f"{enemy.name} {intent.description} for {dealt} damage.")
            if intent.effect_on_hit:
                effect = StatusEffect(
                    id=intent.effect_on_hit,
                    name=intent.effect_on_hit.capitalize(),
                    description="",
                    trigger=EffectTrigger.ON_TURN_END,
                    category=EffectCategory.DEBUFF,
                    duration=intent.effect_duration
                )
                result.add(self.player.apply_effect(effect))
        elif kind == "BLOCK":
            dice = DiceExpression.parse(intent.dice_expression) if intent.dice_expression else DiceExpression.flat(enemy.defense)
            block = max(0, dice.roll())
            enemy.add_block(block)
            result.add(f"{enemy.name} gains {block} block.")
        elif kind == "FLEE":
            enemy.current_hp = 0
            result.add(f"{enemy.name} flees!")
        else:
            result.add(f"{enemy.name} {intent.description}.")

    def _enemy_can_hit_player(self, enemy: "Enemy", intent) -> bool:
        if not self.world:
            return True
        enemy_room = enemy.combat_room_id or self.player_room_id
        if enemy_room == self.player_room_id:
            return True
        tags = getattr(intent, "tags", [])
        if "ranged" in tags:
            return bool(self.player_room_id in self._zone_from_anchor(enemy_room))
        return False

    def _enemy_step_toward_player(self, enemy: "Enemy") -> bool:
        # Guard AI never moves from its home room
        if getattr(enemy, "ai_profile", "") == "guard" and enemy.guard_home:
            return False
        if not self.world or not self.player_room_id:
            return False
        enemy_room = enemy.combat_room_id
        if not enemy_room or enemy_room == self.player_room_id:
            return False
        path = self.world.shortest_path(enemy_room, self.player_room_id)
        if len(path) < 2:
            return False
        next_zone = path[1]
        current_room = self.world.get_room(enemy_room)
        next_room = self.world.get_room(next_zone)
        if not current_room or not next_room:
            return False
        current_room.remove_enemy(enemy)
        next_room.add_enemy(enemy)
        enemy.combat_room_id = next_zone
        enemy.current_zone = next_zone
        self._refresh_combat_zone()
        return True

    # ----------------------------------------------------------------------
    # Target selection & disambiguation
    # ----------------------------------------------------------------------
    def _resolve_target(self, parsed: ParsedCommand, result: TurnResult) -> "Enemy | None":
        self._debug_log("_resolve_target()")
        cmd = self.registry.get_command(parsed.intent or "")
        ranged = bool(cmd and "ranged" in [t.lower() for t in cmd.tags])
        living = self._eligible_targets(ranged=ranged)
        if not living:
            all_enemies = [e for e in self.enemies if e.is_alive and self._enemy_in_zone(e)]
            if all_enemies:
                result.add(
                    "No enemies in this room. You cannot reach them from here. Try moving closer or using a ranged attack.")
            else:
                result.add("There are no enemies left.")
            return None
        if parsed.target_index is not None:
            if 1 <= parsed.target_index <= len(living):
                return living[parsed.target_index - 1]
            result.add("Invalid target number.")
            return None
        if parsed.target_name:
            matches = [e for e in living if parsed.target_name.lower() in e.name.lower()]
            if len(matches) == 1:
                return matches[0]
            if not matches:
                result.add("No target matches that name.")
                return None
            if parsed.article == ArticleType.GENERIC:
                return random.choice(matches)
            self._pending_disambiguation = matches
            result.add("Which one?")
            for i, e in enumerate(matches, 1):
                result.add(f"  {i}. {e.name}")
            return None
        if len(living) == 1:
            return living[0]
        self._pending_disambiguation = living
        result.add("Which enemy?")
        for i, e in enumerate(living, 1):
            result.add(f"  {i}. {e.name}")
        return None

    def _resolve_disambiguation(self, raw: str, result: TurnResult) -> "Enemy | None":
        self._debug_log("_resolve_disambiguation()")
        if not self._pending_disambiguation:
            return None
        if not raw.strip().isdigit():
            result.add("Please enter a number.")
            return None
        idx = int(raw.strip())
        if not (1 <= idx <= len(self._pending_disambiguation)):
            result.add("Number out of range.")
            return None
        enemy = self._pending_disambiguation[idx - 1]
        self._pending_disambiguation = None
        return enemy

    # ----------------------------------------------------------------------
    # Movement hints
    # ----------------------------------------------------------------------
    def _direction_hint_to_enemy(self, enemy: "Enemy") -> str:
        """Return a string like 'south' or 'south → east' to reach the enemy's room."""
        if not self.world or not self.player_room_id:
            return "?"
        enemy_room = enemy.combat_room_id or getattr(enemy, "current_zone", None)
        if not enemy_room or enemy_room == self.player_room_id:
            return "here"
        path = self.world.shortest_path(self.player_room_id, enemy_room)
        if len(path) < 2:
            return "?"
        current_room = self.world.get_room(self.player_room_id)
        if not current_room:
            return "?"
        next_room_id = path[1]
        direction = None
        for exit_name, target in current_room.exits.items():
            if target == next_room_id:
                direction = exit_name
                break
        if not direction:
            return "?"
        if len(path) > 2:
            next_room = self.world.get_room(next_room_id)
            if next_room:
                for exit_name, target in next_room.exits.items():
                    if target == path[2]:
                        return f"{direction} → {exit_name}"
        return direction

    # ----------------------------------------------------------------------
    # Dice helpers
    # ----------------------------------------------------------------------
    def _build_attack_dice(self, cmd: "CommandDefinition | None", parsed: ParsedCommand) -> DiceExpression:
        if cmd and cmd.base_dice:
            base = DiceExpression.parse(cmd.base_dice)
        else:
            base = DiceExpression.flat(self.player.attack_value())
        return self._apply_modifiers_to_dice(base, parsed.modifiers)

    def _apply_modifiers_to_dice(self, base: DiceExpression, modifier_names: list[str]) -> DiceExpression:
        out = base
        for name in modifier_names:
            mod = self.registry.get_modifier(name)
            if mod is None:
                continue
            out = out.multiply_count(mod.dice_count_mult)
            if mod.dice_sides_mult != 1.0:
                out = DiceExpression(out.count, max(1, int(round(out.sides * mod.dice_sides_mult))), out.modifier, out.raw)
            if mod.flat_bonus:
                out = out.add_modifier(mod.flat_bonus)
        return out

    def _format_roll(self, expr: DiceExpression, rolls: list[int], total: int) -> str:
        return f"rolled {expr} -> {rolls} = {total}"