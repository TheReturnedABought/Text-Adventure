import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from game.combat import CombatController
from game.commands import CommandContext, CommandDefinition, CommandRegistry
from game.entities import Enemy, Player
from game.models import EnemyIntent, IntentType
from game.parser import CommandParser
from game.world import Material, Room


def _make_registry() -> CommandRegistry:
    registry = CommandRegistry()
    registry.register_command(
        CommandDefinition(
            name="attack",
            aliases=["hit", "strike"],
            description="Basic attack",
            base_dice="1d6+2",
            valid_contexts=[CommandContext.COMBAT],
            tags=["melee", "single-target"],
            base_ap_cost=6,
            base_mp_cost=0,
        )
    )
    return registry


def _make_player() -> Player:
    p = Player(name="Hero", max_hp=40, attack=8, defense=2, total_ap=24, max_mana=0, mana=0)
    p.unlocked_commands = {"attack"}
    return p


def _make_enemy() -> Enemy:
    intent = EnemyIntent(
        id="scratch",
        intent_type=IntentType.ATTACK,
        description="scratches",
        dice_expression="1d4",
        ap_cost=6,
    )
    return Enemy(name="Skeleton Guard", max_hp=18, attack=3, defense=1, total_ap=18, intent_pool=[intent], material="bone")


def test_ambiguous_attack_does_not_spend_ap_until_target_selected():
    player = _make_player()
    e1 = _make_enemy()
    e2 = _make_enemy()
    parser = CommandParser(_make_registry())
    combat = CombatController(parser, _make_registry(), player, [e1, e2])
    combat.start_encounter()

    before_ap = player.current_ap
    prompt = combat.player_input("attack skeleton")

    assert "Which one?" in "\n".join(prompt.lines)
    assert player.current_ap == before_ap

    choose = combat.player_input("1")
    assert any("You hit Skeleton Guard for" in line for line in choose.lines)
    assert player.current_ap == before_ap - 6
    assert e1.current_hp < e1.max_hp or e2.current_hp < e2.max_hp


def test_room_description_replaces_braced_snippet_without_desc_suffix():
    room = Room(
        id="r1",
        name="Room",
        description="Before. {{combat_update}} After.",
        material=Material.STONE,
        description_snippets={"combat_update": "Enemies defeated."},
    )

    desc = room.get_description(verbose=True)
    assert "{{combat_update}}" not in desc
    assert "Enemies defeated." in desc
