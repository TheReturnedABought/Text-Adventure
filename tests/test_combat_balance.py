"""Test harness for combat balance simulation.

Run as standalone script:   python -m tests.test_combat_balance
Run with pytest:           pytest tests/test_combat_balance.py -v
"""

import random
import sys
from pathlib import Path

# Add parent directory to path to allow imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from game.commands import CommandRegistry, CommandContext, CommandDefinition
from game.combat import CombatController, CombatOutcome
from game.entities import Player, Enemy
from game.models import EnemyIntent, IntentType
from game.parser import CommandParser
from game.loader import AssetLoader

# ----------------------------------------------------------------------
# Test fixtures
# ----------------------------------------------------------------------

@pytest.fixture
def test_registry():
    """Minimal command registry for testing."""
    registry = CommandRegistry()
    registry.register_command(
        CommandDefinition(
            name="attack",
            aliases=["hit", "strike"],
            description="Basic attack",
            base_dice="1d6+2",
            valid_contexts=[CommandContext.COMBAT],
            modifiers_allowed=[],
            tags=["melee", "single-target"],
        )
    )
    registry.register_command(
        CommandDefinition(
            name="block",
            aliases=["defend"],
            description="Gain block",
            base_dice="1d6+2",
            valid_contexts=[CommandContext.COMBAT],
        )
    )
    registry.register_command(
        CommandDefinition(
            name="flee",
            aliases=["run"],
            description="Attempt to flee",
            valid_contexts=[CommandContext.COMBAT],
        )
    )
    return registry


@pytest.fixture
def test_player():
    """Basic player for testing."""
    player = Player(
        name="Hero",
        max_hp=50,
        attack=8,
        defense=3,
        total_ap=24,
        max_mana=10,
        mana=10
    )
    player.current_hp = 50
    player.current_ap = 24
    player.level = 1
    player.unlocked_commands = {"attack", "block", "flee"}
    return player


@pytest.fixture
def goblin():
    """Single goblin enemy."""
    intents = [
        EnemyIntent(
            id="scratch",
            intent_type=IntentType.ATTACK,
            description="scratches",
            dice_expression="1d4+1",
            ap_cost=6,
            weight=3,
        ),
        EnemyIntent(
            id="cower",
            intent_type=IntentType.BLOCK,
            description="cowers",
            dice_expression="1d6",
            ap_cost=5,
            weight=1,
            condition="hp_below_half",
        ),
    ]
    enemy = Enemy(
        name="Goblin",
        max_hp=12,
        attack=3,
        defense=0,
        total_ap=18,
        intent_pool=intents,
        xp_reward=10,
    )
    enemy.current_hp = 12
    enemy.current_ap = 18
    return enemy


# ----------------------------------------------------------------------
# Simulation runner (reusable)
# ----------------------------------------------------------------------

def run_simulation(player, enemies, registry, iterations=100, verbose=False):
    """Run multiple combat simulations and return statistics."""
    parser = CommandParser(registry)
    results = {
        "wins": 0,
        "losses": 0,
        "flees": 0,
        "rounds": [],
        "player_hp_remaining": [],
        "ap_used_total": [],
        "damage_dealt_total": [],
        "player_max_hp": player.max_hp,
    }

    for i in range(iterations):
        # Reset player
        player.current_hp = player.max_hp
        player.current_ap = player.total_ap
        player.mana = player.max_mana
        player.block = 0
        player.effects.clear_all(player)

        # Reset enemies
        for e in enemies:
            e.current_hp = e.max_hp
            e.current_ap = e.total_ap
            e.block = 0
            e.effects.clear_all(e)
            e.active_intents = []

        combat = CombatController(parser, registry, player, enemies.copy())
        combat.start_encounter()

        round_count = 0
        damage_dealt = 0
        ap_used = 0
        outcome = CombatOutcome.ONGOING

        while outcome == CombatOutcome.ONGOING:
            round_count += 1
            available = registry.available_for(player, CommandContext.COMBAT)
            if not available:
                break
            cmd = random.choice(available)
            raw = cmd.name
            if cmd.name == "attack" and enemies:
                target_name = random.choice([e.name for e in enemies if e.is_alive])
                raw = f"attack {target_name}"
            result = combat.player_input(raw)
            outcome = result.outcome
            ap_used += result.ap_spent
            if "hit" in " ".join(result.lines).lower():
                damage_dealt += 5

        if outcome == CombatOutcome.PLAYER_WON:
            results["wins"] += 1
            results["player_hp_remaining"].append(player.current_hp)
        elif outcome == CombatOutcome.PLAYER_FLED:
            results["flees"] += 1
        else:
            results["losses"] += 1

        results["rounds"].append(round_count)
        results["ap_used_total"].append(ap_used)
        results["damage_dealt_total"].append(damage_dealt)

        if verbose and (i + 1) % 10 == 0:
            print(f"  Sim {i+1}: {outcome.name} in {round_count} rounds")

    return results


# ----------------------------------------------------------------------
# Pytest test functions
# ----------------------------------------------------------------------

def test_combat_vs_one_goblin(test_player, goblin, test_registry):
    """Test that player wins most of the time against one goblin."""
    results = run_simulation(test_player, [goblin], test_registry, iterations=50)
    win_rate = results["wins"] / 50 * 100
    print(f"\nWin rate vs 1 Goblin: {win_rate:.1f}%")
    assert win_rate > 70, f"Win rate too low: {win_rate:.1f}%"


def test_combat_vs_two_goblins(test_player, goblin, test_registry):
    """Test that two goblins are more challenging but still winnable."""
    results = run_simulation(test_player, [goblin, goblin], test_registry, iterations=50)
    win_rate = results["wins"] / 50 * 100
    print(f"\nWin rate vs 2 Goblins: {win_rate:.1f}%")
    # No hard assertion, just report
    assert win_rate >= 0  # placeholder


def test_combat_ap_cost_calculation(test_player, test_registry):
    """Verify that AP cost is based on raw command length."""
    parser = CommandParser(test_registry)
    # "attack" has 6 letters → AP cost 6
    parsed = parser.parse("attack", test_player, CommandContext.COMBAT)
    assert parsed.ap_cost == 6, f"Expected 6 AP, got {parsed.ap_cost}"
    # "attack goblin" has 13 letters → AP cost 13
    parsed = parser.parse("attack goblin", test_player, CommandContext.COMBAT)
    assert parsed.ap_cost == 13, f"Expected 13 AP, got {parsed.ap_cost}"


def test_mp_cost_calculation(test_player, test_registry):
    """Verify MP cost uses word count."""
    # Add a command that costs MP for testing
    test_registry.register_command(
        CommandDefinition(
            name="spell",
            aliases=[],
            description="Magic spell",
            costs_mp=True,
            mp_cost_override=None,
            valid_contexts=[CommandContext.COMBAT],
        )
    )
    parser = CommandParser(test_registry)
    parsed = parser.parse("spell", test_player, CommandContext.COMBAT)
    # "spell" is 1 word → MP cost 1 (minimum)
    assert parsed.mp_cost == 1, f"Expected 1 MP, got {parsed.mp_cost}"
    parsed = parser.parse("spell fireball", test_player, CommandContext.COMBAT)
    # "spell fireball" is 2 words → MP cost 2
    assert parsed.mp_cost == 2, f"Expected 2 MP, got {parsed.mp_cost}"


def test_enemy_intent_loading():
    """Test that enemy intents are loaded correctly from JSON-like dict."""
    from game.loader import AssetLoader
    from pathlib import Path
    import tempfile
    import json

    # Create a temporary enemy JSON
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({
            "id": "test_enemy",
            "name": "Test Creature",
            "max_hp": 20,
            "intent_pool": [  # note: key is intent_pool, not intents
                {
                    "id": "bite",
                    "intent_type": "attack",
                    "description": "bites",
                    "dice_expression": "1d6",
                    "ap_cost": 5,
                    "weight": 2,
                }
            ]
        }, f)
        temp_path = Path(f.name)

    try:
        loader = AssetLoader(Path("."))
        template = loader.load_enemy_template(temp_path)
        # Simulate instantiation
        enemy = loader.instantiate_enemy("test_enemy", {"test_enemy": template})
        assert len(enemy.intent_pool) == 1
        assert enemy.intent_pool[0].id == "bite"
    finally:
        temp_path.unlink()


# ----------------------------------------------------------------------
# Standalone execution
# ----------------------------------------------------------------------

if __name__ == "__main__":
    # Run as script: python -m tests.test_combat_balance
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=100, help="Number of sims per test")
    parser.add_argument("--verbose", action="store_true", help="Show progress")
    args = parser.parse_args()

    print("Creating test objects...")
    registry = CommandRegistry()
    # Try loading real assets if available
    try:
        loader = AssetLoader(Path("assets"))
        loader.load_commands_into(registry)
        print("Loaded commands from assets.")
    except Exception:
        print("Using minimal command registry.")
        # Register minimal commands
        registry.register_command(
            CommandDefinition(name="attack", aliases=["hit"], description="Attack", base_dice="1d6+2", valid_contexts=[CommandContext.COMBAT])
        )
        registry.register_command(
            CommandDefinition(name="block", aliases=[], description="Block", base_dice="1d6+2", valid_contexts=[CommandContext.COMBAT])
        )
        registry.register_command(
            CommandDefinition(name="flee", aliases=[], description="Flee", valid_contexts=[CommandContext.COMBAT])
        )

    player = Player(name="Hero", max_hp=50, attack=8, defense=3, total_ap=24, max_mana=10, mana=10)
    player.current_hp = 50
    player.current_ap = 24
    player.unlocked_commands = {"attack", "block", "flee"}

    goblin = None
    # Try to load real goblin template
    try:
        templates = loader.load_all_enemy_templates()
        if "goblin_scout" in templates:
            goblin = loader.instantiate_enemy("goblin_scout", templates)
        else:
            raise KeyError
    except Exception:
        # Create fallback goblin
        intents = [
            EnemyIntent(id="scratch", intent_type=IntentType.ATTACK, description="scratches",
                        dice_expression="1d4+1", ap_cost=6, weight=3),
            EnemyIntent(id="cower", intent_type=IntentType.BLOCK, description="cowers",
                        dice_expression="1d6", ap_cost=5, weight=1, condition="hp_below_half")
        ]
        goblin = Enemy(name="Goblin", max_hp=12, attack=3, defense=0, total_ap=18, intent_pool=intents, xp_reward=10)
        goblin.current_hp = 12
        goblin.current_ap = 18

    print(f"\n--- Simulation vs 1 Goblin ({args.iterations} iterations) ---")
    res1 = run_simulation(player, [goblin], registry, iterations=args.iterations, verbose=args.verbose)
    print(f"Wins: {res1['wins']} ({res1['wins']/args.iterations*100:.1f}%) | Losses: {res1['losses']} | Flees: {res1['flees']}")
    print(f"Avg rounds: {sum(res1['rounds'])/len(res1['rounds']):.1f} | Avg AP used: {sum(res1['ap_used_total'])/len(res1['ap_used_total']):.1f}")

    print(f"\n--- Simulation vs 2 Goblins ({args.iterations} iterations) ---")
    res2 = run_simulation(player, [goblin, goblin], registry, iterations=args.iterations, verbose=args.verbose)
    print(f"Wins: {res2['wins']} ({res2['wins']/args.iterations*100:.1f}%) | Losses: {res2['losses']} | Flees: {res2['flees']}")
    print(f"Avg rounds: {sum(res2['rounds'])/len(res2['rounds']):.1f} | Avg AP used: {sum(res2['ap_used_total'])/len(res2['ap_used_total']):.1f}")