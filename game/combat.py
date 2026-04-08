# game/combat.py
import random
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional, Set

from game.commands import CommandContext, CommandDefinition
from game.dice import DiceExpression
from game.effects import EffectTrigger, EffectCategory, StatusEffect
from game.entities import Enemy, Player
from game.models import ParsedCommand, ArticleType
from game.world import DamageType, Material, coerce_damage_type, resolve_material_interaction, apply_turn_passives
from game.window import window

class CombatOutcome(Enum):
    ONGOING = auto(); PLAYER_WON = auto(); PLAYER_FLED = auto(); PLAYER_DEFEATED = auto()

@dataclass
class TurnResult:
    lines: List[str] = field(default_factory=list); ap_spent: int = 0; outcome: CombatOutcome = CombatOutcome.ONGOING
    def add(self, line: str) -> None: self.lines.append(line)
    def is_finished(self) -> bool: return self.outcome != CombatOutcome.ONGOING
    def display(self) -> str: return "\n".join(self.lines)

class CombatController:
    def __init__(self, parser, registry, player: Player, enemies: List[Enemy], world=None, player_room_id=None, puzzle_flags=None, debug=False):
        self.parser = parser; self.registry = registry; self.player = player; self.enemies = enemies
        self.world = world; self.player_room_id = player_room_id; self.puzzle_flags = puzzle_flags or {}
        self.round = 1; self.combat_zone: Set[str] = set(); self._pending_disambiguation = None
        self._pending_attack_parsed = None
        self._refresh_combat_zone()
        self.player.combat_defense_bonus = 0
        for e in enemies: e.reset_ap(); e.plan_turn(player)

    def _refresh_combat_zone(self):
        if not self.world: self.combat_zone = set(); return
        zone = set()
        for e in self.enemies:
            if e.is_alive and e.combat_room_id:
                room = self.world.get_room(e.combat_room_id)
                if room: zone |= {room.id, *room.line_of_sight}
        self.combat_zone = zone

    def start_encounter(self) -> str:
        for e in self.enemies: e.movement_hint = self._direction_hint(e)
        return f"Combat begins! You face: {', '.join(e.name for e in self.enemies if e.is_alive)}."

    def _direction_hint(self, enemy: Enemy) -> str:
        if not self.world or not self.player_room_id: return "?"
        enemy_room = enemy.combat_room_id or getattr(enemy, "current_zone", None)
        if not enemy_room or enemy_room == self.player_room_id: return "here"
        path = self.world.shortest_path(self.player_room_id, enemy_room)
        if len(path) < 2: return "?"
        cur = self.world.get_room(self.player_room_id)
        if not cur: return "?"
        dir = next((d for d,t in cur.exits.items() if t == path[1]), None)
        if not dir: return "?"
        if len(path) > 2:
            nxt = self.world.get_room(path[1])
            if nxt:
                nxt_dir = next((d for d,t in nxt.exits.items() if t == path[2]), None)
                if nxt_dir: return f"{dir} → {nxt_dir}"
        return dir

    def player_input(self, raw: str) -> TurnResult:
        result = TurnResult()
        if self._pending_disambiguation:
            target = self._resolve_disambiguation(raw, result)
            if target is None: return result
            if self._pending_attack_parsed:
                parsed = self._pending_attack_parsed
                self._pending_attack_parsed = None
                if self._attack(parsed, result, forced_target=target):
                    self.player.spend_ap(parsed.ap_cost); self.player.mana -= parsed.mp_cost
                    result.ap_spent = parsed.ap_cost
                    for line in self.player.tick_effects(EffectTrigger.ON_ACTION): result.add(line)
                    self._refresh_combat_zone()
                result.outcome = self.check_outcome() if result.outcome == CombatOutcome.ONGOING else result.outcome
                if result.outcome == CombatOutcome.ONGOING and self.player.current_ap <= 0:
                    end = self.end_player_turn()
                    result.lines.extend(end.lines); result.outcome = end.outcome
                return result
            result.add(f"Target selected: {target.name}.")
            return result

        parsed = self.parser.parse(raw, self.player, CommandContext.COMBAT)
        if not parsed.valid: result.add(parsed.error or "Invalid command."); return result
        if parsed.intent == "go":
            self._go(parsed, result); return result
        if parsed.intent in {"status", "look"}: self._status(parsed, result); return result
        if parsed.intent == "help": self._help(parsed, result); return result
        if parsed.intent in {"wait", "end"}: self._wait(parsed, result); return result
        if parsed.ap_cost > self.player.current_ap: result.add("Not enough AP."); return result
        if parsed.mp_cost > getattr(self.player, "mana", 0): result.add("Not enough MP."); return result

        handler = {
            "attack": self._attack, "block": self._block, "ability": self._ability, "equip": self._equip,
            "flee": self._flee, "go": self._go, "status": self._status, "help": self._help, "wait": self._wait
        }.get(parsed.intent)
        if handler:
            action = handler(parsed, result)
            if result.outcome == CombatOutcome.ONGOING and action:
                if parsed.intent not in {"ability","cast","use"}:
                    self.player.spend_ap(parsed.ap_cost); self.player.mana -= parsed.mp_cost
                    result.ap_spent = parsed.ap_cost
                for line in self.player.tick_effects(EffectTrigger.ON_ACTION): result.add(line)
                self._refresh_combat_zone()
        else: result.add("That command has no combat resolver yet.")
        result.outcome = self.check_outcome() if result.outcome == CombatOutcome.ONGOING else result.outcome
        if result.outcome == CombatOutcome.ONGOING and self.player.current_ap <= 0:
            end = self.end_player_turn()
            result.lines.extend(end.lines); result.outcome = end.outcome
        return result

    def end_player_turn(self) -> TurnResult:
        result = TurnResult()
        self.player.clear_block()
        for line in self.player.tick_effects(EffectTrigger.ON_TURN_END): result.add(line)
        # poison/spore ticks
        for e in [e for e in self.enemies if e.is_alive]:
            poison = getattr(e, "poison_turns", 0)
            if poison > 0:
                dmg = DiceExpression.parse("1d4").roll()
                dealt = e.receive_damage(dmg)
                e.poison_turns = poison - 1
                result.add(f"{e.name} takes {dealt} poison damage.")
            spore = getattr(e, "spore_turns", 0)
            if spore > 0:
                e.spore_turns = spore - 1
                for other in self.enemies:
                    if other.is_alive and other is not e and other.combat_room_id == e.combat_room_id:
                        dmg = DiceExpression.parse("1d4").roll()
                        dealt = other.receive_damage(dmg)
                        result.add(f"Spore cloud harms {other.name} for {dealt}.")
        for line in apply_turn_passives(self.player, self.world, self.player_room_id): result.add(line)

        for e in [e for e in self.enemies if e.is_alive and (not self.combat_zone or e.combat_room_id in self.combat_zone)]:
            e.clear_block()
            for intent in list(e.active_intents):
                if not e.is_alive: break
                if not e.spend_ap(intent.ap_cost): continue
                kind = getattr(intent.intent_type, "name", "ATTACK")
                if kind == "ATTACK":
                    # check reach
                    enemy_room = e.combat_room_id or self.player_room_id
                    if self.world and enemy_room != self.player_room_id and "ranged" not in getattr(intent, "tags", []):
                        # move if possible
                        if self._enemy_step_toward(e):
                            result.add(f"{e.name} advances.")
                        else:
                            result.add(f"{e.name} cannot reach you.")
                            continue
                    dice = DiceExpression.parse(intent.dice_expression) if intent.dice_expression else DiceExpression.flat(e.attack)
                    dmg = max(0, dice.roll() + e.attack)
                    dealt = self.player.receive_damage(dmg)
                    # mirror shield reflection
                    shield = self.player.equipped.get("offhand")
                    reflected = None
                    if shield and "mirror_shield" in shield.item_flags and dealt>0 and {"lightning","radiant"} & {t.lower() for t in getattr(intent,"tags",[])}:
                        reflected = max(1, dealt//2)
                        self.player.heal(reflected)
                        e.receive_damage(reflected)
                    result.add(f"{e.name} {intent.description} for {dealt} damage.")
                    if reflected: result.add(f"Mirror Shield reflects {reflected} damage back to {e.name}.")
                    if dealt>0:
                        chest = self.player.equipped.get("chest")
                        if chest and "gambeson_scars" in chest.item_flags and self.player.combat_defense_bonus <5:
                            self.player.combat_defense_bonus +=1
                            result.add("Gambeson of Scars hardens. Defense +1 (combat).")
                    if intent.effect_on_hit:
                        effect = StatusEffect(id=intent.effect_on_hit, name=intent.effect_on_hit.capitalize(), description="",
                                              trigger=EffectTrigger.ON_TURN_END, category=EffectCategory.DEBUFF,
                                              duration=intent.effect_duration)
                        result.add(self.player.apply_effect(effect))
                elif kind == "BLOCK":
                    dice = DiceExpression.parse(intent.dice_expression) if intent.dice_expression else DiceExpression.flat(e.defense)
                    block = max(0, dice.roll())
                    e.add_block(block)
                    result.add(f"{e.name} gains {block} block.")
                elif kind == "FLEE":
                    e.current_hp = 0
                    result.add(f"{e.name} flees!")
                else:
                    result.add(f"{e.name} {intent.description}.")
            for line in e.tick_effects(EffectTrigger.ON_TURN_END): result.add(line)
            if self.check_outcome() == CombatOutcome.PLAYER_DEFEATED:
                result.outcome = CombatOutcome.PLAYER_DEFEATED
                return result

        self.round += 1
        if self.world: self.world.advance_turn()
        self.player.reset_ap()
        for e in self.enemies: e.reset_ap(); e.plan_turn(self.player)
        for line in self.player.tick_effects(EffectTrigger.ON_TURN_START): result.add(line)
        result.outcome = self.check_outcome()
        return result

    def _enemy_step_toward(self, enemy: Enemy) -> bool:
        if getattr(enemy, "ai_profile", "") == "guard" and enemy.guard_home: return False
        if not self.world or not self.player_room_id: return False
        e_room = enemy.combat_room_id
        if not e_room or e_room == self.player_room_id: return False
        path = self.world.shortest_path(e_room, self.player_room_id)
        if len(path) < 2: return False
        next_zone = path[1]
        cur_room = self.world.get_room(e_room); next_room = self.world.get_room(next_zone)
        if not cur_room or not next_room: return False
        cur_room.remove_enemy(enemy)
        next_room.add_enemy(enemy)
        enemy.combat_room_id = next_zone
        enemy.current_zone = next_zone
        self._refresh_combat_zone()
        return True

    def check_outcome(self) -> CombatOutcome:
        if not self.player.is_alive: return CombatOutcome.PLAYER_DEFEATED
        if not any(e.is_alive for e in self.enemies): return CombatOutcome.PLAYER_WON
        return CombatOutcome.ONGOING

    def _attack(self, parsed: ParsedCommand, result: TurnResult, forced_target=None) -> bool:
        target = forced_target or self._resolve_target(parsed, result)
        if target is None:
            self._pending_attack_parsed = parsed
            return False
        self._pending_attack_parsed = None

        cmd = self.registry.get_command(parsed.intent or "attack")
        damage_type = next((coerce_damage_type(t) for t in getattr(cmd,"tags",[]) if coerce_damage_type(t)), DamageType.SLASHING)
        base_dice = DiceExpression.parse(cmd.base_dice) if cmd and cmd.base_dice else DiceExpression.flat(self.player.attack_value())
        # apply modifiers
        for mod_name in parsed.modifiers:
            mod = self.registry.get_modifier(mod_name)
            if mod:
                base_dice = base_dice.multiply_count(mod.dice_count_mult)
                if mod.dice_sides_mult != 1.0:
                    base_dice = DiceExpression(base_dice.count, max(1, int(round(base_dice.sides * mod.dice_sides_mult))), base_dice.modifier, base_dice.raw)
                if mod.flat_bonus: base_dice = base_dice.add_modifier(mod.flat_bonus)
        total, rolls, mod = base_dice.roll_with_breakdown()
        weapon_bonus = 0
        if parsed.item_name:
            weapon_bonus = self.player.weapon_attack_bonus(parsed.item_name)
            if weapon_bonus == 0: result.add(f"You don't have '{parsed.item_name}' equipped."); return False
            total += weapon_bonus
        else: total += self.player.base_attack_value()

        room_mat = self.world.get_room(self.player_room_id).material if self.world else Material.STONE
        total = int(total * resolve_material_interaction(damage_type, room_mat).damage_multiplier)
        target_mat = next((m for m in Material if m.value == target.material), Material.FLESH)
        total = int(total * resolve_material_interaction(damage_type, target_mat).damage_multiplier)
        vuln_mult = 2.0 if damage_type.value in target.vulnerabilities else 1.0
        resist_mult = 0.5 if damage_type.value in target.resistances else 1.0
        total = int(total * vuln_mult * resist_mult)

        weapon = None
        for it in self.player.equipped.values():
            if it.slot == "weapon" and (not parsed.item_name or parsed.item_name.lower() in it.name.lower()):
                weapon = it; break
        if weapon and "bone_crusher" in weapon.item_flags and "skeleton" in target.template_id: total += 2
        if parsed.article == ArticleType.GENERIC: total += self.registry.article_rule.generic_flat_bonus
        elif parsed.article == ArticleType.SPECIFIC: total += self.registry.article_rule.specific_flat_bonus

        dealt = target.receive_damage(total)
        result.add(f"You hit {target.name} for {dealt} damage (rolled {base_dice} -> {rolls} = {total}).")
        if weapon:
            if "wasp_needle" in weapon.item_flags and random.random()<0.2:
                target.poison_turns = getattr(target, "poison_turns",0)+3
                result.add(f"{target.name} is poisoned.")
            if "fungal_shiv" in weapon.item_flags and random.random()<0.25:
                target.spore_turns = 2
                result.add(f"Spores burst from the wound around {target.name}.")
            if "bone_crusher" in weapon.item_flags and not target.is_alive and random.random()<0.2:
                result.add(f"{target.name} shatters violently!")
                for other in self.enemies:
                    if other.is_alive and other is not target and other.combat_room_id == target.combat_room_id:
                        splash = DiceExpression.parse("1d4").roll()
                        dealt_splash = other.receive_damage(splash)
                        result.add(f"{other.name} takes {dealt_splash} splash damage.")
        if self.world:
            room = self.world.get_room(self.player_room_id)
            if room:
                for line in room.apply_elemental_effect(damage_type.value, self.player): result.add(line)
        return True

    def _block(self, parsed: ParsedCommand, result: TurnResult) -> bool:
        cmd = self.registry.get_command(parsed.intent or "block")
        dice = DiceExpression.parse(cmd.base_dice) if cmd and cmd.base_dice else DiceExpression.flat(max(1, self.player.defense_value()))
        for mod_name in parsed.modifiers:
            mod = self.registry.get_modifier(mod_name)
            if mod:
                dice = dice.multiply_count(mod.dice_count_mult)
                if mod.dice_sides_mult != 1.0: dice = DiceExpression(dice.count, max(1, int(round(dice.sides * mod.dice_sides_mult))), dice.modifier, dice.raw)
                if mod.flat_bonus: dice = dice.add_modifier(mod.flat_bonus)
        block_value = max(0, dice.roll())
        self.player.add_block(block_value)
        result.add(f"You brace yourself, gaining {block_value} block.")
        return True

    def _ability(self, parsed: ParsedCommand, result: TurnResult) -> bool:
        name = (parsed.item_name or parsed.target_name or "").lower()
        restore_ap = restore_mp = 0
        for item in self.player.equipped.values():
            for ability in item.abilities:
                if name and name not in ability.name.lower() and name != ability.id.lower(): continue
                if ability.dice_expression:
                    dice = DiceExpression.parse(ability.dice_expression)
                    dmg = dice.roll()
                    target = self._resolve_target(parsed, result)
                    if target:
                        dealt = target.receive_damage(dmg)
                        result.add(f"You use {ability.name} and deal {dealt} damage.")
                        if ability.effect_on_hit:
                            effect = StatusEffect(id=ability.effect_on_hit, name=ability.effect_on_hit.capitalize(), description="",
                                                  trigger=EffectTrigger.ON_TURN_END, category=EffectCategory.DEBUFF,
                                                  duration=ability.effect_duration, stacks=ability.effect_stacks)
                            result.add(target.apply_effect(effect))
                else: result.add(f"You use {ability.name}.")
                restore_ap = int(ability.payload.get("restore_ap", 0) or 0)
                restore_mp = int(ability.payload.get("restore_mp", 0) or 0)
                if restore_ap>0 or restore_mp>0:
                    self.player.current_ap = min(self.player.total_ap, self.player.current_ap + restore_ap)
                    self.player.mana = min(self.player.max_mana, self.player.mana + restore_mp)
                return True
        result.add("No matching ability is equipped.")
        return False

    def _equip(self, parsed: ParsedCommand, result: TurnResult) -> bool:
        item_name = parsed.item_name or parsed.target_name
        if not item_name: result.add("Equip what?"); return False
        result.add(self.player.equip(item_name))
        return True

    def _flee(self, parsed: ParsedCommand, result: TurnResult) -> bool:
        if random.random() < 0.5: result.add("You successfully flee."); result.outcome = CombatOutcome.PLAYER_FLED
        else: result.add("You fail to flee!")
        return True

    def _go(self, parsed: ParsedCommand, result: TurnResult) -> bool:
        direction = parsed.target_name
        if not direction: result.add("Go where?"); return False
        if parsed.ap_cost > self.player.current_ap: result.add("Not enough AP to move."); return False
        room = self.world.get_room(self.player_room_id)
        if not room or direction not in room.exits: result.add("You cannot go that way."); return False
        target_id = room.exits[direction]
        will_flee = target_id not in self.combat_zone
        if will_flee:
            result.add("You try to flee, but enemies react!")
            for e in [e for e in self.enemies if e.is_alive and (not self.combat_zone or e.combat_room_id in self.combat_zone)]:
                e.reset_ap(); e.plan_turn(self.player)
                # one free turn for each enemy
                for intent in list(e.active_intents):
                    if not e.spend_ap(intent.ap_cost): continue
                    kind = getattr(intent.intent_type, "name", "ATTACK")
                    if kind == "ATTACK":
                        dice = DiceExpression.parse(intent.dice_expression) if intent.dice_expression else DiceExpression.flat(e.attack)
                        dmg = max(0, dice.roll() + e.attack)
                        dealt = self.player.receive_damage(dmg)
                        result.add(f"{e.name} {intent.description} for {dealt} damage.")
                        if dealt>0:
                            chest = self.player.equipped.get("chest")
                            if chest and "gambeson_scars" in chest.item_flags and self.player.combat_defense_bonus<5:
                                self.player.combat_defense_bonus+=1
                                result.add("Gambeson of Scars hardens. Defense +1 (combat).")
                    elif kind == "BLOCK":
                        dice = DiceExpression.parse(intent.dice_expression) if intent.dice_expression else DiceExpression.flat(e.defense)
                        block = max(0, dice.roll())
                        e.add_block(block)
                        result.add(f"{e.name} gains {block} block.")
            if self.player.is_alive:
                self.player.current_ap = self.player.total_ap
                result.ap_spent = 0
                self.player_room_id = target_id
                self.world.current_room_id = target_id
                self._refresh_combat_zone()
                result.add(f"You flee to {target_id}.")
                new_room = self.world.current_room()
                if new_room: result.add(new_room.get_description(verbose=False))
                result.outcome = CombatOutcome.PLAYER_FLED
            else: result.outcome = CombatOutcome.PLAYER_DEFEATED
            return True
        self.player.spend_ap(parsed.ap_cost)
        result.ap_spent = parsed.ap_cost
        self.player_room_id = target_id
        self.world.current_room_id = target_id
        self._refresh_combat_zone()
        result.add(f"You move {direction} ({parsed.ap_cost} AP).")
        new_room = self.world.current_room()
        if new_room: result.add(new_room.get_description(verbose=False))
        if self.player.current_ap <= 0:
            end = self.end_player_turn()
            result.lines.extend(end.lines); result.outcome = end.outcome
        return True

    def _status(self, parsed: ParsedCommand, result: TurnResult) -> bool:
        result.add(self.player.status_line())
        for e in self.enemies:
            if e.is_alive: result.add(e.status_line() + f" | Intents: {e.intent_display()}")
        return True

    def _help(self, parsed: ParsedCommand, result: TurnResult) -> bool:
        cmds = self.registry.available_for(self.player, CommandContext.COMBAT)
        if not cmds: result.add("No combat commands available.")
        else:
            for cmd in sorted(cmds, key=lambda c: c.name):
                result.add(f"{cmd.name} - {cmd.description}")
        return True

    def _wait(self, parsed: ParsedCommand, result: TurnResult) -> bool:
        end = self.end_player_turn()
        result.lines.extend(end.lines); result.outcome = end.outcome
        return True

    def _resolve_target(self, parsed: ParsedCommand, result: TurnResult):
        cmd = self.registry.get_command(parsed.intent or "")
        ranged = bool(cmd and "ranged" in [t.lower() for t in cmd.tags]) or any("ranged_attack" in it.item_flags for it in self.player.equipped.values())
        living = []
        for e in self.enemies:
            if e.is_alive and (not self.combat_zone or e.combat_room_id in self.combat_zone):
                if ranged or not self.world: living.append(e)
                elif e.combat_room_id == self.player_room_id: living.append(e)
        if not living:
            if any(e.is_alive for e in self.enemies): result.add("No enemies in this room. You cannot reach them from here. Try moving closer or using a ranged attack.")
            else: result.add("There are no enemies left.")
            return None
        if parsed.target_index is not None:
            if 1 <= parsed.target_index <= len(living): return living[parsed.target_index-1]
            result.add("Invalid target number."); return None
        if parsed.target_name:
            matches = [e for e in living if parsed.target_name.lower() in e.name.lower()]
            if len(matches)==1: return matches[0]
            if not matches: result.add("No target matches that name."); return None
            if parsed.article == ArticleType.GENERIC: return random.choice(matches)
            self._pending_disambiguation = matches
            result.add("Which one?")
            for i,e in enumerate(matches,1): result.add(f"  {i}. {e.name}")
            return None
        if len(living)==1: return living[0]
        self._pending_disambiguation = living
        result.add("Which enemy?")
        for i,e in enumerate(living,1): result.add(f"  {i}. {e.name}")
        return None

    def _resolve_disambiguation(self, raw: str, result: TurnResult):
        if not self._pending_disambiguation: return None
        if not raw.strip().isdigit(): result.add("Please enter a number."); return None
        idx = int(raw.strip())
        if not (1 <= idx <= len(self._pending_disambiguation)): result.add("Number out of range."); return None
        enemy = self._pending_disambiguation[idx-1]
        self._pending_disambiguation = None
        return enemy