"""Combat controller – turn order, AP costs, damage, material interactions, status effects."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING

from game.commands import CommandContext
from game.dice import DiceExpression
from game.effects import EffectTrigger
from game.models import ParsedCommand, ArticleType
from game.world import DamageType, coerce_damage_type, resolve_material_interaction

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
                 puzzle_flags: dict | None = None) -> None:
        self.parser = parser
        self.registry = registry
        self.player = player
        self.enemies = enemies
        self.world = world
        self.player_room_id = player_room_id
        self.puzzle_flags = puzzle_flags or {}
        self.round = 1
        self.log: list[str] = []
        self._pending_disambiguation: list["Enemy"] | None = None
        self.combat_zone: set[str] = set()

    def start_encounter(self) -> str:
        self._refresh_combat_zone()
        for enemy in self.enemies:
            enemy.reset_ap()
            enemy.plan_turn(self.player)
        names = ", ".join(e.name for e in self.enemies if e.is_alive)
        return f"Combat begins! You face: {names}."

    def player_input(self, raw: str) -> TurnResult:
        result = TurnResult()
        direction = raw.strip().lower()
        if self._is_combat_movement(direction):
            return self._handle_combat_movement(direction, raw)

        if self._pending_disambiguation is not None:
            target = self.resolve_disambiguation(raw, result)
            if target is None:
                return result
            result.add(f"Target selected: {target.name}.")
            return result

        parsed = self.parser.parse(raw, self.player, CommandContext.COMBAT)
        if not parsed.valid:
            result.add(parsed.error or "Invalid command.")
            return result

        intent = parsed.intent or ""
        if intent in {"status", "look"}:
            self.resolve_status(result)
            return result
        if intent == "help":
            self.resolve_help(result)
            return result
        if intent in {"wait", "end"}:
            return self.end_player_turn()

        if parsed.ap_cost > self.player.current_ap:
            result.add("Not enough AP.")
            return result

        if intent in {"attack", "strike", "hit"}:
            self.resolve_attack(parsed, result)
        elif intent == "block":
            self.resolve_block(parsed, result)
        elif intent in {"ability", "cast", "use"}:
            self.resolve_ability(parsed, result)
        elif intent == "equip":
            self.resolve_equip(parsed, result)
        elif intent == "flee":
            self.resolve_flee(parsed, result)
        else:
            result.add("That command has no combat resolver yet.")

        if result.outcome == CombatOutcome.ONGOING:
            self.player.spend_ap(parsed.ap_cost)
            result.ap_spent += parsed.ap_cost
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
        result = TurnResult()
        self.player.clear_block()
        for line in self.player.tick_effects(EffectTrigger.ON_TURN_END):
            result.add(line)

        for enemy in [e for e in self.enemies if e.is_alive]:
            if not self._enemy_in_zone(enemy):
                continue
            enemy_result = self.enemy_turn(enemy)
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

    def enemy_turn(self, enemy: "Enemy") -> TurnResult:
        result = TurnResult()
        enemy.clear_block()
        for intent in list(enemy.active_intents):
            if not enemy.is_alive:
                break
            if not enemy.spend_ap(intent.ap_cost):
                continue
            self.resolve_enemy_intent(enemy, intent, result)
            if self.check_outcome() == CombatOutcome.PLAYER_DEFEATED:
                result.outcome = CombatOutcome.PLAYER_DEFEATED
                return result
        for line in enemy.tick_effects(EffectTrigger.ON_TURN_END):
            result.add(line)
        return result

    def check_outcome(self) -> CombatOutcome:
        if not self.player.is_alive:
            return CombatOutcome.PLAYER_DEFEATED
        if not any(e.is_alive for e in self.enemies):
            return CombatOutcome.PLAYER_WON
        return CombatOutcome.ONGOING

    # ── Attack resolution with damage types & material interactions ───────
    def resolve_attack(self, parsed: ParsedCommand, result: TurnResult) -> None:
        target = self.resolve_target(parsed, result)
        if target is None:
            return

        # Determine damage type from command tags or default to "slashing"
        cmd = self.registry.get_command(parsed.intent or "attack")
        damage_type = self._get_damage_type_from_command(cmd)
        dice = self.build_attack_dice(cmd, parsed, self.player) if cmd else DiceExpression.flat(self.player.attack_value())
        total, rolls, mod = dice.roll_with_breakdown()

        # Article bonuses
        if parsed.article == ArticleType.GENERIC:
            total += self.registry.article_rule.generic_flat_bonus
        elif parsed.article == ArticleType.SPECIFIC:
            total += self.registry.article_rule.specific_flat_bonus

        # Apply material interaction (room material, target material)
        room_material = self._get_current_room_material()
        interaction = resolve_material_interaction(damage_type, room_material)
        total = int(total * interaction.damage_multiplier)

        # Apply target's own material resistances (if any)
        target_material = self._material_from_str(target.material)
        target_interaction = resolve_material_interaction(damage_type, target_material)
        total = int(total * target_interaction.damage_multiplier)

        # Apply damage
        dealt = target.receive_damage(total + self.player.attack_value())
        result.add(f"You hit {target.name} for {dealt} damage ({self.format_roll(dice, rolls, total)}).")

        # Apply status effect from command/ability
        if cmd and cmd.tags:
            effect_id = self._get_effect_from_damage_type(damage_type)
            if effect_id:
                from game.effects import StatusEffect  # local import to avoid circular
                # Create effect stub (concrete effects would be registered)
                effect = StatusEffect(id=effect_id, name=effect_id.capitalize(),
                                      description="", trigger=EffectTrigger.ON_TURN_END,
                                      category=None, duration=2)
                result.add(target.apply_effect(effect))

        # Environmental reaction (e.g., lightning in metal room)
        env_lines = self._apply_environmental_reaction(damage_type, self.player, target)
        for line in env_lines:
            result.add(line)

    def _get_damage_type_from_command(self, cmd: "CommandDefinition | None") -> DamageType:
        """Map command tags to a DamageType. Defaults to SLASHING."""
        if not cmd:
            return DamageType.SLASHING
        for tag in cmd.tags:
            dt = coerce_damage_type(tag)
            if dt:
                return dt
        return DamageType.SLASHING

    def _get_effect_from_damage_type(self, dt: DamageType) -> str | None:
        """Return status effect id based on damage type (simple mapping)."""
        mapping = {
            DamageType.FIRE: "burning",
            DamageType.LIGHTNING: "shocked",
            DamageType.COLD: "slowed",
            DamageType.POISON: "poisoned",
            DamageType.NECROTIC: "decaying",
        }
        return mapping.get(dt)

    def _get_current_room_material(self):
        if self.world and self.player_room_id:
            room = self.world.get_room(self.player_room_id)
            if room:
                return room.material
        from game.world import Material
        return Material.STONE

    def _material_from_str(self, mat_str: str):
        from game.world import Material
        try:
            return Material(mat_str.lower())
        except ValueError:
            return Material.FLESH

    def _apply_environmental_reaction(self, damage_type: DamageType, player: "Player", target: "Enemy") -> list[str]:
        """Apply room‑wide effects (e.g., shock in metal room, ignite wood)."""
        lines = []
        if not self.world or not self.player_room_id:
            return lines
        room = self.world.get_room(self.player_room_id)
        if not room:
            return lines
        # Use the room's apply_elemental_effect method
        lines.extend(room.apply_elemental_effect(damage_type.value, player))
        return lines

    # ── Block ─────────────────────────────────────────────────────────────
    def resolve_block(self, parsed: ParsedCommand, result: TurnResult) -> None:
        cmd = self.registry.get_command(parsed.intent or "block")
        dice = DiceExpression.parse(cmd.base_dice) if cmd and cmd.base_dice else DiceExpression.flat(max(1, self.player.defense_value()))
        dice = self.apply_modifiers_to_dice(dice, parsed.modifiers)
        block = max(0, dice.roll())
        self.player.add_block(block)
        result.add(f"You gain {block} block.")

    # ── Ability (item abilities) ─────────────────────────────────────────
    def resolve_ability(self, parsed: ParsedCommand, result: TurnResult) -> None:
        name = (parsed.item_name or parsed.target_name or "").lower().strip()
        for item in self.player.equipped.values():
            for ability in item.abilities:
                if name and name not in ability.name.lower() and name != ability.id.lower():
                    continue
                # Execute ability – here we just apply dice and effect
                if ability.dice_expression:
                    dice = DiceExpression.parse(ability.dice_expression)
                    dmg = dice.roll()
                    target = self.resolve_target(parsed, result)
                    if target:
                        dealt = target.receive_damage(dmg)
                        result.add(f"You use {ability.name} and deal {dealt} damage.")
                else:
                    result.add(f"You use {ability.name}.")
                return
        result.add("No matching ability is equipped.")

    # ── Equip / Flee / Status / Help ─────────────────────────────────────
    def resolve_equip(self, parsed: ParsedCommand, result: TurnResult) -> None:
        if not parsed.item_name and not parsed.target_name:
            result.add("Equip what?")
            return
        item_name = parsed.item_name or parsed.target_name or ""
        result.add(self.player.equip(item_name))

    def resolve_flee(self, parsed: ParsedCommand, result: TurnResult) -> None:
        _ = parsed
        chance = 0.5
        if random.random() < chance:
            result.add("You successfully flee.")
            result.outcome = CombatOutcome.PLAYER_FLED
        else:
            result.add("You fail to flee!")

    def resolve_status(self, result: TurnResult) -> None:
        result.add(self.player.status_line())
        for enemy in self.enemies:
            if enemy.is_alive:
                result.add(enemy.status_line() + f" | Intents: {enemy.intent_display()}")

    def resolve_help(self, result: TurnResult) -> None:
        cmds = self.registry.available_for(self.player, CommandContext.COMBAT)
        if not cmds:
            result.add("No combat commands available.")
            return
        for cmd in sorted(cmds, key=lambda c: c.name):
            cost = self.registry.ap_cost_for(cmd.name, cmd, self.player)
            result.add(f"{cmd.name} (AP {cost}) - {cmd.description}")

    # ── Enemy intent resolution ──────────────────────────────────────────
    def resolve_enemy_intent(self, enemy: "Enemy", intent, result: TurnResult) -> None:
        kind = getattr(intent.intent_type, "name", "ATTACK")
        if kind == "ATTACK" and not self._enemy_can_hit_player(enemy, intent):
            if self._enemy_step_toward_player(enemy):
                result.add(f"{enemy.name} advances toward your position.")
            if not self._enemy_can_hit_player(enemy, intent):
                result.add(f"{enemy.name} cannot reach you from there.")
                return
        elif not self._enemy_can_hit_player(enemy, intent):
            result.add(f"{enemy.name} cannot reach you from there.")
            return

        if kind == "ATTACK":
            dice = DiceExpression.parse(intent.dice_expression) if intent.dice_expression else DiceExpression.flat(enemy.attack)
            dmg = max(0, dice.roll() + enemy.attack)
            dealt = self.player.receive_damage(dmg)
            result.add(f"{enemy.name} {intent.description} for {dealt} damage.")
            # Apply effect on hit
            if intent.effect_on_hit:
                from game.effects import StatusEffect
                effect = StatusEffect(id=intent.effect_on_hit, name=intent.effect_on_hit.capitalize(),
                                      description="", trigger=EffectTrigger.ON_TURN_END,
                                      category=None, duration=intent.effect_duration)
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

    # ── Target selection & disambiguation ─────────────────────────────────
    def resolve_target(self, parsed: ParsedCommand, result: TurnResult) -> "Enemy | None":
        cmd = self.registry.get_command(parsed.intent or "")
        ranged = bool(cmd and "ranged" in [t.lower() for t in cmd.tags])
        living = self._eligible_targets(ranged=ranged)
        if not living:
            result.add("There are no enemies left.")
            return None
        if parsed.target_index is not None:
            target = living[parsed.target_index - 1] if 1 <= parsed.target_index <= len(living) else None
            if target is None:
                result.add("Invalid target number.")
            return target
        if parsed.target_name:
            matches = [e for e in living if parsed.target_name.lower() in e.name.lower()]
            if len(matches) == 1:
                return matches[0]
            if len(matches) == 0:
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

    def resolve_disambiguation(self, raw: str, result: TurnResult) -> "Enemy | None":
        if self._pending_disambiguation is None:
            return None
        text = raw.strip()
        if not text.isdigit():
            result.add("Please enter a number.")
            return None
        idx = int(text)
        if not (1 <= idx <= len(self._pending_disambiguation)):
            result.add("Number out of range.")
            return None
        enemy = self._pending_disambiguation[idx - 1]
        self._pending_disambiguation = None
        return enemy

    # ── Combat movement & zone logic ─────────────────────────────────────
    def _is_combat_movement(self, direction: str) -> bool:
        if not self.world or not self.player_room_id:
            return False
        room = self.world.get_room(self.player_room_id)
        return bool(room and direction in room.exits)

    def _handle_combat_movement(self, direction: str, raw: str) -> TurnResult:
        result = TurnResult()
        ap_cost = max(1, len(raw.strip()) - self.player.ap_cost_reduction_for(direction))
        if ap_cost > self.player.current_ap:
            result.add("Not enough AP to move.")
            return result
        assert self.world is not None and self.player_room_id is not None
        room = self.world.get_room(self.player_room_id)
        if room is None or direction not in room.exits:
            result.add("You cannot go that way.")
            return result
        self.player.spend_ap(ap_cost)
        result.ap_spent += ap_cost
        destination = room.exits[direction]
        self.player_room_id = destination
        self.world.current_room_id = destination
        self._refresh_combat_zone()
        result.add(f"You move {direction} ({ap_cost} AP).")

        if destination not in self.combat_zone:
            result.add("You moved out of the combat zone!")
            for enemy in [e for e in self.enemies if e.is_alive]:
                if not self._enemy_in_zone(enemy):
                    continue
                free_turn = self.enemy_turn(enemy)
                result.lines.extend(free_turn.lines)
            result.outcome = CombatOutcome.PLAYER_FLED
            return result

        if self.player.current_ap <= 0:
            end = self.end_player_turn()
            result.lines.extend(end.lines)
            result.outcome = end.outcome
        return result

    def _refresh_combat_zone(self) -> None:
        if self.world is None:
            self.combat_zone = set()
            return
        zone: set[str] = set()
        if self.player_room_id:
            zone |= self._zone_from_anchor(self.player_room_id)
        for enemy in self.enemies:
            if not enemy.is_alive:
                continue
            enemy_room = getattr(enemy, "combat_room_id", None)
            if enemy_room:
                zone |= self._zone_from_anchor(enemy_room)
        self.combat_zone = zone

    def _zone_from_anchor(self, room_id: str) -> set[str]:
        if not self.world:
            return set()
        room = self.world.get_room(room_id)
        if room is None:
            return set()
        return {room.id, *room.line_of_sight}

    def _enemy_in_zone(self, enemy: "Enemy") -> bool:
        room_id = getattr(enemy, "combat_room_id", self.player_room_id)
        return not self.combat_zone or room_id in self.combat_zone

    def _eligible_targets(self, ranged: bool) -> list["Enemy"]:
        living = [e for e in self.enemies if e.is_alive and self._enemy_in_zone(e)]
        if ranged or self.world is None:
            return living
        return [
            e for e in living
            if getattr(e, "combat_room_id", self.player_room_id) == self.player_room_id
        ]

    def _enemy_can_hit_player(self, enemy: "Enemy", intent) -> bool:
        if self.world is None:
            return True
        enemy_room = getattr(enemy, "combat_room_id", self.player_room_id)
        if enemy_room == self.player_room_id:
            return True
        tags = [str(t).lower() for t in getattr(intent, "tags", [])]
        if "ranged" in tags:
            return bool(self.player_room_id in self._zone_from_anchor(enemy_room))
        return False

    def _enemy_step_toward_player(self, enemy: "Enemy") -> bool:
        if self.world is None or self.player_room_id is None:
            return False
        enemy_room = getattr(enemy, "combat_room_id", None)
        if enemy_room is None or enemy_room == self.player_room_id:
            return False
        path = self.world.shortest_path(enemy_room, self.player_room_id)
        if len(path) < 2:
            return False
        next_zone = path[1]
        current_room = self.world.get_room(enemy_room)
        next_room = self.world.get_room(next_zone)
        if current_room is None or next_room is None:
            return False
        if next_zone not in current_room.exits.values():
            return False
        current_room.remove_enemy(enemy)
        next_room.add_enemy(enemy)
        setattr(enemy, "combat_room_id", next_zone)
        setattr(enemy, "current_zone", next_zone)
        self._refresh_combat_zone()
        return True

    # ── Dice helpers ─────────────────────────────────────────────────────
    def build_attack_dice(self, cmd: "CommandDefinition | None",
                          parsed: ParsedCommand,
                          player: "Player") -> DiceExpression:
        if cmd and cmd.base_dice:
            base = DiceExpression.parse(cmd.base_dice)
        else:
            base = DiceExpression.flat(player.attack_value())
        return self.apply_modifiers_to_dice(base, parsed.modifiers)

    def apply_modifiers_to_dice(self, base: DiceExpression,
                                modifier_names: list[str]) -> DiceExpression:
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

    def combat_header(self) -> str:
        enemy_parts = [f"[{e.name}] HP: {e.current_hp}/{e.max_hp} | Intends: {e.intent_display()}" for e in self.enemies if e.is_alive]
        return f"Round {self.round} | [{self.player.name}] HP: {self.player.current_hp}/{self.player.max_hp} AP: {self.player.current_ap}/{self.player.total_ap} Block: {self.player.block}\n" + "\n".join(enemy_parts)

    def format_roll(self, expression: DiceExpression, rolls: list[int], total: int) -> str:
        return f"rolled {expression} -> {rolls} = {total}"