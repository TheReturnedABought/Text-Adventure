"""Combat controller – turn order, AP costs, targeting, zone-based LOS."""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional, Set

from game.commands import CommandContext, CommandDefinition
from game.dice import DiceExpression
from game.effects import EffectTrigger, EffectCategory, StatusEffect
from game.entities import Enemy, Player
from game.models import ParsedCommand, ArticleType
from game.world import DamageType, Material, coerce_damage_type, resolve_material_interaction

class CombatOutcome(Enum):
    ONGOING = auto(); PLAYER_WON = auto(); PLAYER_FLED = auto(); PLAYER_DEFEATED = auto()

@dataclass
class TurnResult:
    lines: List[str] = field(default_factory=list); ap_spent: int = 0; outcome: CombatOutcome = CombatOutcome.ONGOING
    def add(self, line: str) -> None: self.lines.append(line)
    def is_finished(self) -> bool: return self.outcome != CombatOutcome.ONGOING
    def display(self) -> str: return "\n".join(self.lines)

class CombatController:
    def __init__(self, parser: "CommandParser", registry: "CommandRegistry",
                 player: "Player", enemies: list["Enemy"],
                 world: "WorldMap | None" = None,
                 player_room_id: str | None = None,
                 puzzle_flags: dict | None = None,
                 debug: bool = False,
                 loader: "AssetLoader | None" = None,
                 enemy_templates: dict | None = None) -> None:
        self.parser = parser
        self.registry = registry
        self.player = player
        self.enemies = enemies
        self.world = world
        self.player_room_id = player_room_id
        self.puzzle_flags = puzzle_flags or {}
        self.round = 1
        self.combat_zone: set[str] = set()
        self._pending_disambiguation: list["Enemy"] | None = None
        self._pending_attack_parsed: ParsedCommand | None = None
        self._debug = debug
        self.loader = loader
        self.enemy_templates = enemy_templates or {}
        self._refresh_combat_zone()
        self.player.combat_defense_bonus = 0
        for e in enemies: e.reset_ap(); e.plan_turn(player)

    def _log(self, msg: str) -> None:
        if self._debug:
            print(f"[DEBUG] {msg}")

    # --- Zone helpers ---
    def _zone_ids(self, room_id: str) -> set[str]:
        room = self.world.get_room(room_id) if self.world else None
        return {room.id, *room.line_of_sight} if room else set()

    def _refresh_combat_zone(self) -> None:
        if not self.world:
            self.combat_zone = set()
            self._log("No world, combat_zone cleared")
            return
        zone: set[str] = set()
        for e in self.enemies:
            if e.is_alive and e.combat_room_id:
                zone |= self._zone_ids(e.combat_room_id)
        self.combat_zone = zone
        self._log(f"Combat zone refreshed: {self.combat_zone}")

    def _enemy_in_zone(self, enemy: "Enemy") -> bool:
        rid = enemy.combat_room_id or self.player_room_id
        in_zone = not self.combat_zone or rid in self.combat_zone
        self._log(f"Enemy {enemy.name} room={rid} in_zone={in_zone} (zone={self.combat_zone})")
        return in_zone

    def _has_ranged_weapon(self) -> bool:
        for item in self.player.equipped.values():
            flags = [f.lower() for f in getattr(item, "item_flags", [])]
            if "ranged" in flags or "ranged_attack" in flags:
                return True
        return False

    def _eligible_targets(self, ranged: bool) -> list["Enemy"]:
        living = [e for e in self.enemies if e.is_alive and self._enemy_in_zone(e)]
        if ranged or self._has_ranged_weapon():
            return living
        same_room = [e for e in living if e.combat_room_id == self.player_room_id]
        return same_room

    def _refresh_movement_hints(self) -> None:
        for enemy in self.enemies:
            enemy.movement_hint = self._direction_hint_to_enemy(enemy)

    # --- Encounter ---
    def start_encounter(self) -> str:
        self._refresh_combat_zone()
        self._refresh_movement_hints()
        self.player.combat_defense_bonus = 0
        for e in self.enemies:
            e.reset_ap()
            e.plan_turn(self.player)
        return f"Combat begins! You face: {', '.join(e.name for e in self.enemies if e.is_alive)}."

    # --- Player input ---
    def player_input(self, raw: str) -> TurnResult:
        result = TurnResult()
        if self._pending_disambiguation:
            target = self._resolve_disambiguation(raw, result)
            if target is None: return result
            if self._pending_attack_parsed:
                parsed = self._pending_attack_parsed
                self._pending_attack_parsed = None
                if self._resolve_attack(parsed, result, forced_target=target):
                    self._spend_and_tick(parsed, result)
                self._finalise(result)
            else:
                result.add(f"Target selected: {target.name}.")
            return result

        parsed = self.parser.parse(raw, self.player, CommandContext.COMBAT)
        if not parsed.valid:
            result.add(parsed.error or "Invalid command.")
            return result

        self._log(f"Raw AP: {raw}, Reduced AP: {parsed.ap_cost}")
        intent = parsed.intent or ""

        if intent == "go":
            self._refresh_movement_hints()
            return self._handle_combat_movement(parsed, result)

        if intent in {"status", "look", "inventory", "inv", "i"}:
            result.add(self.player.status_line())
            for e in self.enemies:
                if e.is_alive:
                    result.add(e.status_line() + f" | Intents: {e.intent_display()}")
            if intent in {"inventory", "inv", "i"}:
                result.add(self.player.inventory_summary())
            return result

        if intent == "help":
            for cmd in sorted(self.registry.available_for(self.player, CommandContext.COMBAT) or [],
                               key=lambda c: c.name):
                result.add(f"{cmd.name} - {cmd.description}")
            return result

        if intent in {"wait", "end"}:
            return self.end_player_turn()

        if parsed.ap_cost > self.player.current_ap:
            result.add("Not enough AP.")
            return result
        if parsed.mp_cost > getattr(self.player, "mana", 0):
            result.add("Not enough MP.")
            return result

        action_performed = False
        if intent in {"attack", "strike", "hit"}:
            action_performed = self._resolve_attack(parsed, result)
        elif intent == "block":
            cmd = self.registry.get_command("block")
            base = DiceExpression.parse(cmd.base_dice) if cmd and cmd.base_dice else DiceExpression.flat(max(1, self.player.defense_value()))
            block_value = max(0, self._apply_modifiers(base, parsed.modifiers).roll())
            self.player.add_block(block_value)
            result.add(f"You brace yourself, gaining {block_value} block.")
            action_performed = True
        elif intent in {"ability", "cast", "use"}:
            self.player.spend_ap(parsed.ap_cost)
            self.player.mana -= parsed.mp_cost
            result.ap_spent = parsed.ap_cost
            restore_ap, restore_mp = self._resolve_ability(parsed, result)
            if restore_ap:
                self.player.current_ap = min(self.player.total_ap, self.player.current_ap + restore_ap)
            if restore_mp:
                self.player.mana = min(self.player.max_mana, self.player.mana + restore_mp)
            for line in self.player.tick_effects(EffectTrigger.ON_ACTION):
                result.add(line)
            self._refresh_combat_zone()
            action_performed = True
        elif intent == "equip":
            item_name = parsed.item_name or parsed.target_name
            result.add(self.player.equip(item_name) if item_name else "Equip what?")
            self._refresh_combat_zone()
            action_performed = True
        elif intent == "flee":
            if random.random() < 0.5:
                result.add("You successfully flee.")
                result.outcome = CombatOutcome.PLAYER_FLED
            else:
                result.add("You fail to flee!")
            action_performed = True
        else:
            result.add("That command has no combat resolver yet.")

        if result.outcome == CombatOutcome.ONGOING and action_performed and intent not in {"ability", "cast", "use"}:
            self._spend_and_tick(parsed, result)
        self._finalise(result)
        return result

    def _spend_and_tick(self, parsed: ParsedCommand, result: TurnResult) -> None:
        self.player.spend_ap(parsed.ap_cost)
        self.player.mana -= parsed.mp_cost
        result.ap_spent = parsed.ap_cost
        for line in self.player.tick_effects(EffectTrigger.ON_ACTION):
            result.add(line)
        self._refresh_combat_zone()

    def _finalise(self, result: TurnResult) -> None:
        if result.outcome == CombatOutcome.ONGOING:
            result.outcome = self.check_outcome()
        if result.outcome == CombatOutcome.ONGOING and self.player.current_ap <= 0:
            end = self.end_player_turn()
            result.lines.extend(end.lines)
            result.outcome = end.outcome

    # --- Turn flow ---
    def end_player_turn(self) -> TurnResult:
        result = TurnResult()
        self.player.clear_block()
        for line in self.player.tick_effects(EffectTrigger.ON_TURN_END):
            result.add(line)
        for line in self._tick_enemy_dot():
            result.add(line)
        for line in self._apply_turn_passives():
            result.add(line)
        for enemy in [e for e in self.enemies if e.is_alive and self._enemy_in_zone(e)]:
            enemy_result = self._enemy_turn(enemy)
            result.lines.extend(enemy_result.lines)
            if enemy_result.outcome != CombatOutcome.ONGOING:
                result.outcome = enemy_result.outcome
                return result
        self.round += 1
        if self.world: self.world.advance_turn()
        self.player.reset_ap()
        for e in self.enemies:
            e.reset_ap()
            e.plan_turn(self.player)
        for line in self.player.tick_effects(EffectTrigger.ON_TURN_START):
            result.add(line)
        self._refresh_movement_hints()
        result.outcome = self.check_outcome()
        return result

    def _enemy_turn(self, enemy: "Enemy") -> TurnResult:
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
        if not self.player.is_alive:
            return CombatOutcome.PLAYER_DEFEATED
        if not any(e.is_alive for e in self.enemies):
            return CombatOutcome.PLAYER_WON
        return CombatOutcome.ONGOING

    # --- Combat movement ---
    def _handle_combat_movement(self, parsed: ParsedCommand, result: TurnResult) -> TurnResult:
        direction = parsed.target_name
        if not direction:
            result.add("Go where?")
            return result
        if parsed.ap_cost > self.player.current_ap:
            result.add("Not enough AP to move.")
            return result
        room = self.world.get_room(self.player_room_id)
        if not room or direction not in room.exits:
            result.add("You cannot go that way.")
            return result

        target_room_id = room.exits[direction]
        if target_room_id not in self.combat_zone:
            result.add("You try to flee, but enemies react!")
            for enemy in [e for e in self.enemies if e.is_alive and self._enemy_in_zone(e)]:
                enemy.reset_ap()
                enemy.plan_turn(self.player)
                free = self._enemy_turn(enemy)
                result.lines.extend(free.lines)
                if free.outcome != CombatOutcome.ONGOING:
                    result.outcome = free.outcome
                    return result
            if self.player.is_alive:
                self._move_player(target_room_id, result)
                result.add(f"You flee to {target_room_id}.")
                result.outcome = CombatOutcome.PLAYER_FLED
            else:
                result.outcome = CombatOutcome.PLAYER_DEFEATED
            return result

        self.player.spend_ap(parsed.ap_cost)
        result.ap_spent = parsed.ap_cost
        self._move_player(target_room_id, result)
        result.add(f"You move {direction} ({parsed.ap_cost} AP).")
        if self.player.current_ap <= 0:
            end = self.end_player_turn()
            result.lines.extend(end.lines)
            result.outcome = end.outcome
        return result

    def _move_player(self, room_id: str, result: TurnResult) -> None:
        self.player_room_id = room_id
        self.world.current_room_id = room_id
        self._refresh_combat_zone()
        self._refresh_movement_hints()
        new_room = self.world.current_room()
        if new_room:
            result.add(new_room.get_description(verbose=False))

    # --- Damage type for attack ---
    def _get_damage_type_for_attack(self, parsed: ParsedCommand, weapon, cmd: CommandDefinition) -> Optional[DamageType]:
        intent = parsed.intent or ""
        # Basic attack uses weapon's damage_type
        if intent == "attack":
            if weapon and getattr(weapon, "damage_type", None):
                dt = coerce_damage_type(weapon.damage_type)
                if dt:
                    return dt
            # Unarmed
            return DamageType.BLUDGEONING
        # Other commands use command tags
        if cmd:
            for tag in cmd.tags:
                dt = coerce_damage_type(tag)
                if dt:
                    return dt
        return DamageType.SLASHING

    # --- Attack resolution ---
    def _resolve_attack(self, parsed: ParsedCommand, result: TurnResult,
                        forced_target: "Enemy | None" = None) -> bool:
        target = forced_target or self._resolve_target(parsed, result)
        if target is None:
            self._pending_attack_parsed = parsed
            return False
        self._pending_attack_parsed = None

        cmd = self.registry.get_command(parsed.intent or "attack")
        weapon = self._active_weapon(parsed.item_name)
        damage_type = self._get_damage_type_for_attack(parsed, weapon, cmd)

        # Build dice expression
        base_dice = DiceExpression.parse(cmd.base_dice) if cmd and cmd.base_dice else DiceExpression.flat(self.player.attack_value())
        dice = self._apply_modifiers(base_dice, parsed.modifiers)
        dice_roll, rolls, mod = dice.roll_with_breakdown()

        base_attack = self.player.base_attack_value()
        # Determine formula components
        if cmd and cmd.base_dice:
            # Attack uses command dice + base attack
            formula_parts = [f"base {base_attack}", f"{dice_str}"]
            roll_sum = dice_roll + base_attack
        else:
            formula_parts = [dice_str]
            roll_sum = dice_roll
            base_attack = 0

        weapon_bonus = 0
        if parsed.item_name:
            weapon_bonus = self.player.weapon_attack_bonus(parsed.item_name)
            if not weapon_bonus:
                result.add(f"You don't have '{parsed.item_name}' equipped.")
                return False
            roll_sum += weapon_bonus
            formula_parts.append(f"weapon {weapon_bonus}")

        # Article bonuses
        article_bonus = 0
        if parsed.article == ArticleType.GENERIC:
            article_bonus = self.registry.article_rule.generic_flat_bonus
        elif parsed.article == ArticleType.SPECIFIC:
            article_bonus = self.registry.article_rule.specific_flat_bonus
        if article_bonus:
            roll_sum += article_bonus
            formula_parts.append(f"article {article_bonus}")

        total_before_mult = roll_sum

        # Material interactions
        room_mat = Material.STONE
        if self.world and self.player_room_id:
            room = self.world.get_room(self.player_room_id)
            if room:
                room_mat = room.material
        try:
            target_mat = Material(getattr(target, "material", "flesh").lower())
        except ValueError:
            target_mat = Material.FLESH

        total = int(total_before_mult * resolve_material_interaction(damage_type, room_mat).damage_multiplier)
        total = int(total * resolve_material_interaction(damage_type, target_mat).damage_multiplier)

        # Vulnerability / resistance
        vuln_mult = 1.0
        eff_msg = ""
        if damage_type.value in getattr(target, "vulnerabilities", []):
            vuln_mult = 2.0
            eff_msg = " It's super effective!"
        elif damage_type.value in getattr(target, "resistances", []):
            vuln_mult = 0.5
            eff_msg = " It's not very effective..."
        total = int(total * vuln_mult)

        # Weapon-specific bonuses (bone crusher)
        if weapon and "bone_crusher" in weapon.item_flags and "skeleton" in target.template_id:
            total += 2

        dealt = target.receive_damage(max(0, total))

        # Build the attack message with clear breakdown
        formula_str = " + ".join(formula_parts)
        breakdown_parts = []
        if base_attack:
            breakdown_parts.append(str(base_attack))
        if cmd and cmd.base_dice:
            breakdown_parts.append(f"[{'+'.join(map(str, rolls))}]")
            if mod:
                breakdown_parts.append(str(mod))
        else:
            breakdown_parts.append(f"[{'+'.join(map(str, rolls))}]")
            if mod:
                breakdown_parts.append(str(mod))
        if weapon_bonus:
            breakdown_parts.append(str(weapon_bonus))
        if article_bonus:
            breakdown_parts.append(str(article_bonus))
        breakdown = " + ".join(breakdown_parts)
        total_display = total_before_mult
        result.add(f"You hit {target.name} for {dealt} {damage_type.value} damage. ({formula_str} → {breakdown} = {total_display}){eff_msg}")

        # On-hit effects
        for line in self._weapon_on_hit_effects(weapon, target, dealt):
            result.add(line)
        if self.world and self.player_room_id:
            room = self.world.get_room(self.player_room_id)
            if room:
                for line in room.apply_elemental_effect(damage_type.value, self.player):
                    result.add(line)

        # --- SPLITTING LOGIC (flag-based) ---
        if not target.is_alive:
            split_data = getattr(target, 'split', None)
            if split_data:
                trigger_types = split_data.get('trigger_damage_types', [])
                if trigger_types:
                    if damage_type and damage_type.value in trigger_types:
                        spawn_template = split_data.get('spawn_template', target.template_id)
                        # Count current living enemies of that template
                        current_count = sum(1 for e in self.enemies
                                            if e.is_alive and e.template_id == spawn_template)
                        max_total = split_data.get('max_total', 99)
                        if current_count < max_total:
                            # Parse spawn count (dice expression or integer)
                            count_expr = split_data.get('spawn_count', '2')
                            try:
                                to_spawn = DiceExpression.parse(count_expr).roll()
                            except Exception:
                                to_spawn = int(count_expr) if str(count_expr).isdigit() else 2
                            to_spawn = min(to_spawn, max_total - current_count)

                            if to_spawn > 0:
                                for _ in range(to_spawn):
                                    new_enemy = self._create_enemy_from_template(spawn_template)
                                    # Copy split config so new heads can also split
                                    new_enemy.split = split_data
                                    self.enemies.append(new_enemy)
                                    if self.world and target.combat_room_id:
                                        room = self.world.get_room(target.combat_room_id)
                                        if room:
                                            room.add_enemy(new_enemy)
                                # Show custom message
                                msg = split_data.get('message', f"The {target.name} splits into {to_spawn} new enemies!")
                                result.add(msg.format(count=to_spawn, name=target.name))
        return True

    def _create_enemy_from_template(self, template_id: str) -> Enemy:
        """Instantiate an enemy from the loaded templates."""
        if not self.loader or not self.enemy_templates:
            raise RuntimeError("Enemy loader or templates not available in CombatController")
        template = self.enemy_templates.get(template_id)
        if not template:
            raise ValueError(f"Unknown enemy template: {template_id}")
        return self.loader.instantiate_enemy(template_id, self.enemy_templates)

    # --- Ability ---
    def _resolve_ability(self, parsed: ParsedCommand, result: TurnResult) -> tuple[int, int]:
        name = (parsed.item_name or parsed.target_name or "").lower()
        for item in self.player.equipped.values():
            for ability in item.abilities:
                if name and name not in ability.name.lower() and name != ability.id.lower():
                    continue
                # Resolve target first
                target = None
                if ability.dice_expression:
                    target = self._resolve_target(parsed, result)
                    if target is None:
                        return (0, 0)
                # Now deduct AP/MP
                if not self.player.spend_ap(parsed.ap_cost):
                    result.add("Not enough AP.")
                    return (0, 0)
                if parsed.mp_cost > getattr(self.player, "mana", 0):
                    result.add("Not enough MP.")
                    return (0, 0)
                self.player.mana -= parsed.mp_cost
                result.ap_spent = parsed.ap_cost

                if ability.dice_expression:
                    target = self._resolve_target(parsed, result)
                    if target:
                        dealt = target.receive_damage(DiceExpression.parse(ability.dice_expression).roll())
                        result.add(f"You use {ability.name} and deal {dealt} damage.")
                        if ability.effect_on_hit:
                            result.add(target.apply_effect(StatusEffect(
                                id=ability.effect_on_hit,
                                name=ability.effect_on_hit.capitalize(),
                                description="",
                                trigger=EffectTrigger.ON_TURN_END,
                                category=EffectCategory.DEBUFF,
                                duration=ability.effect_duration,
                                stacks=ability.effect_stacks,
                            )))
                else:
                    result.add(f"You use {ability.name}.")
                return (int(ability.payload.get("restore_ap", 0) or 0),
                        int(ability.payload.get("restore_mp", 0) or 0))
        result.add("No matching ability is equipped.")
        return (0, 0)

    # --- Enemy turns ---
    def _resolve_enemy_intent(self, enemy: "Enemy", intent, result: TurnResult) -> None:
        kind = getattr(intent.intent_type, "name", "ATTACK")

        if kind == "ATTACK" and not self._enemy_can_reach(enemy, intent):
            if self._enemy_step_toward_player(enemy):
                result.add(f"{enemy.name} advances toward your position.")
            if not self._enemy_can_reach(enemy, intent):
                result.add(f"{enemy.name} cannot reach you from there.")
                return

        if kind == "ATTACK":
            dice = DiceExpression.parse(intent.dice_expression) if intent.dice_expression else DiceExpression.flat(enemy.attack)
            dealt = self.player.receive_damage(max(0, dice.roll() + enemy.attack))
            result.add(f"{enemy.name} {intent.description} for {dealt} damage.")
            reflected = self._maybe_reflect(intent, enemy, dealt)
            if reflected:
                result.add(reflected)
            if dealt > 0:
                self._proc_gambeson(dealt, result)
            if intent.effect_on_hit:
                result.add(self.player.apply_effect(StatusEffect(
                    id=intent.effect_on_hit,
                    name=intent.effect_on_hit.capitalize(),
                    description="",
                    trigger=EffectTrigger.ON_TURN_END,
                    category=EffectCategory.DEBUFF,
                    duration=intent.effect_duration,
                )))
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

    def _enemy_can_reach(self, enemy: "Enemy", intent) -> bool:
        if not self.world:
            return True
        enemy_room = enemy.combat_room_id
        if enemy_room == self.player_room_id:
            return True
        return "ranged" in getattr(intent, "tags", []) and self.player_room_id in self._zone_ids(enemy_room)

    def _enemy_step_toward_player(self, enemy: "Enemy") -> bool:
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

    # --- Passive / DOT effects ---
    def _tick_enemy_dot(self) -> list[str]:
        lines: list[str] = []
        for enemy in [e for e in self.enemies if e.is_alive]:
            poison = int(getattr(enemy, "poison_turns", 0))
            if poison > 0:
                lines.append(f"{enemy.name} takes {enemy.receive_damage(DiceExpression.parse('1d4').roll())} poison damage.")
                enemy.poison_turns = poison - 1
            spore = int(getattr(enemy, "spore_turns", 0))
            if spore > 0:
                enemy.spore_turns = spore - 1
                for other in self.enemies:
                    if other.is_alive and other is not enemy and other.combat_room_id == enemy.combat_room_id:
                        lines.append(f"Spore cloud harms {other.name} for {other.receive_damage(DiceExpression.parse('1d4').roll())}.")
        return lines

    def _apply_turn_passives(self) -> list[str]:
        lines: list[str] = []
        if not self.world or not self.player_room_id:
            return lines
        room = self.world.get_room(self.player_room_id)
        if not room:
            return lines
        for item in self.player.equipped.values():
            if "beasts_heart" in item.item_flags and (
                self.player_room_id.startswith("wyrmwood") or room.material.value == "flesh"
            ):
                if self.player.heal(1):
                    lines.append("Beast's Heart regenerates 1 HP.")
            if "arcane_cloak" in item.item_flags:
                before = self.player.mana
                self.player.mana = min(self.player.max_mana, self.player.mana + 1)
                if self.player.mana > before:
                    lines.append("Arcane Cloak restores 1 MP.")
        return lines

    def _weapon_on_hit_effects(self, weapon, target: "Enemy", dealt: int) -> list[str]:
        lines: list[str] = []
        if not weapon or dealt <= 0:
            return lines
        flags = set(getattr(weapon, "item_flags", []))
        if "wasp_needle" in flags and random.random() < 0.2:
            target.poison_turns = int(getattr(target, "poison_turns", 0)) + 3
            lines.append(f"{target.name} is poisoned.")
        if "fungal_shiv" in flags and random.random() < 0.25:
            target.spore_turns = 2
            lines.append(f"Spores burst from the wound around {target.name}.")
        if "bone_crusher" in flags and not target.is_alive and random.random() < 0.2:
            lines.append(f"{target.name} shatters violently!")
            for other in self.enemies:
                if other.is_alive and other is not target and other.combat_room_id == target.combat_room_id:
                    lines.append(f"{other.name} takes {other.receive_damage(DiceExpression.parse('1d4').roll())} splash damage.")
        return lines

    def _maybe_reflect(self, intent, enemy: "Enemy", dealt: int) -> str | None:
        shield = self.player.equipped.get("offhand")
        if not shield or "mirror_shield" not in shield.item_flags or dealt <= 0:
            return None
        if not ({"lightning", "radiant"} & {t.lower() for t in getattr(intent, "tags", [])}):
            return None
        reflected = max(1, dealt // 2)
        self.player.heal(reflected)
        enemy.receive_damage(reflected)
        return f"Mirror Shield reflects {reflected} damage back to {enemy.name}."

    def _proc_gambeson(self, dealt: int, result: TurnResult) -> None:
        chest = self.player.equipped.get("chest")
        if not chest or "gambeson_scars" not in chest.item_flags or self.player.combat_defense_bonus >= 5:
            return
        self.player.combat_defense_bonus += 1
        result.add("Gambeson of Scars hardens. Defense +1 (combat).")

    # --- Target selection ---
    def _resolve_target(self, parsed: ParsedCommand, result: TurnResult) -> "Enemy | None":
        cmd = self.registry.get_command(parsed.intent or "")
        ranged = (bool(cmd and "ranged" in [t.lower() for t in cmd.tags])) or self._has_ranged_weapon()
        living = self._eligible_targets(ranged=ranged)

        if not living:
            if any(e.is_alive and self._enemy_in_zone(e) for e in self.enemies):
                if self._has_ranged_weapon():
                    result.add("No enemies in range. (You have a ranged weapon equipped.)")
                else:
                    result.add("No enemies in range. Try moving closer or using a ranged attack.")
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
        if not raw.strip().isdigit():
            result.add("Please enter a number.")
            return None
        idx = int(raw.strip())
        if not (1 <= idx <= len(self._pending_disambiguation)):
            result.add("Number out of range.")
            return None
        enemy = self._pending_disambiguation[idx-1]
        self._pending_disambiguation = None
        return enemy

    def _active_weapon(self, weapon_name: str | None):
        for item in self.player.equipped.values():
            if item.slot != "weapon":
                continue
            if weapon_name and weapon_name.lower() not in item.name.lower():
                continue
            return item
        return None

    # --- Movement hints ---
    def _direction_hint_to_enemy(self, enemy: "Enemy") -> str:
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
        direction = next((d for d, t in current_room.exits.items() if t == next_room_id), None)
        if not direction:
            return "?"
        if len(path) > 2:
            next_room = self.world.get_room(next_room_id)
            if next_room:
                next_dir = next((d for d, t in next_room.exits.items() if t == path[2]), None)
                if next_dir:
                    return f"{direction} → {next_dir}"
        return direction

    # --- Dice helpers ---
    def _build_attack_dice(self, cmd: "CommandDefinition | None", parsed: ParsedCommand) -> DiceExpression:
        base = DiceExpression.parse(cmd.base_dice) if cmd and cmd.base_dice else DiceExpression.flat(self.player.attack_value())
        return self._apply_modifiers(base, parsed.modifiers)

    def _apply_modifiers(self, base: DiceExpression, modifier_names: list[str]) -> DiceExpression:
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