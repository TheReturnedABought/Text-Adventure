from __future__ import annotations

from dataclasses import dataclass

from game.entities import Enemy, Player
from game.models import BattleContext
from game.parser import CommandParser


@dataclass
class CombatResult:
    message: str
    finished: bool = False


class CombatController:
    """Turn controller driven by parsed commands."""

    def __init__(self, parser: CommandParser):
        self.parser = parser

    def resolve_player_turn(self, player: Player, enemy: Enemy, raw_command: str) -> CombatResult:
        parsed = self.parser.parse(raw_command)

        if parsed.intent == "help":
            return CombatResult("Commands: attack [target], equip <item>, ability <name>, help")

        if parsed.intent == "equip":
            if not parsed.item_name:
                return CombatResult("Equip what?")
            return CombatResult(player.equip(parsed.item_name))

        if parsed.intent == "ability":
            return self._use_ability(player, enemy, parsed.item_name)

        if parsed.intent == "attack":
            damage = enemy.receive_damage(player.attack_value())
            msg = f"{player.name} hits {enemy.name} for {damage} damage."
            if not enemy.is_alive:
                return CombatResult(f"{msg} {enemy.name} is defeated!", finished=True)
            return CombatResult(msg)

        return CombatResult("Unknown command. Type help for combat commands.")

    def resolve_enemy_turn(self, player: Player, enemy: Enemy) -> CombatResult:
        if not enemy.is_alive:
            return CombatResult("", finished=True)

        if enemy.choose_action() == "attack":
            damage = player.receive_damage(enemy.attack)
            msg = f"{enemy.name} attacks for {damage} damage."
            if not player.is_alive:
                return CombatResult(f"{msg} You are defeated.", finished=True)
            return CombatResult(msg)

        return CombatResult(f"{enemy.name} waits.")

    def _use_ability(self, player: Player, enemy: Enemy, ability_name: str | None) -> CombatResult:
        if not ability_name:
            return CombatResult("Use which ability?")

        for item in player.equipped.values():
            for ability in item.abilities:
                if ability.name.lower() != ability_name.lower():
                    continue
                if ability.execute is None:
                    return CombatResult(f"{ability.name} is not implemented yet.")
                context = BattleContext(
                    actor_name=player.name,
                    target_name=enemy.name,
                    actor_attack=player.attack_value(),
                    actor_defense=player.defense,
                )
                return CombatResult(ability.execute(context))

        return CombatResult(f"No equipped ability named '{ability_name}'.")
