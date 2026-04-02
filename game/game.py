from __future__ import annotations

from game.combat import CombatController
from game.entities import Enemy, Player
from game.models import Ability, CharacterClass, EquippableItem
from game.parser import CommandParser


class TextAdventureGame:
    """Minimal OO shell with parser-centric combat."""

    def __init__(self) -> None:
        self.parser = CommandParser()
        self.combat = CombatController(self.parser)
        self.player = self._build_player()

    def run(self) -> None:
        enemy = Enemy(name="Training Dummy", max_hp=24, attack=4, defense=1)
        print("Parser Combat Sandbox")
        print("Type: attack, equip bronze blade, ability spark, help")

        while self.player.is_alive and enemy.is_alive:
            command = input("\n> ")
            player_result = self.combat.resolve_player_turn(self.player, enemy, command)
            print(player_result.message)
            if player_result.finished:
                break

            enemy_result = self.combat.resolve_enemy_turn(self.player, enemy)
            if enemy_result.message:
                print(enemy_result.message)
            if enemy_result.finished:
                break

    def _build_player(self) -> Player:
        def spark(_):
            return "Spark ability triggered. TODO: add elemental scaling."

        spark_ability = Ability(name="spark", description="Deals bonus lightning damage.", execute=spark)
        blade = EquippableItem(
            name="Bronze Blade",
            slot="weapon",
            description="Starter weapon with a simple active ability.",
            stat_modifiers={"attack": 2},
            abilities=[spark_ability],
        )
        fighter = CharacterClass(
            name="fighter",
            description="Frontline class with strong equipment scaling.",
            base_stats={"hp": 40, "attack": 6, "defense": 2},
            starting_items=[blade],
        )
        player = Player(
            name="Hero",
            max_hp=fighter.base_stats["hp"],
            attack=fighter.base_stats["attack"],
            defense=fighter.base_stats["defense"],
            char_class=fighter,
            inventory=list(fighter.starting_items),
        )
        player.equip("Bronze Blade")
        return player
