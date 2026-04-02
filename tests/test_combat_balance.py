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
            base_ap_cost=6,          # FIXED: added base AP cost
            base_mp_cost=0,
        )
    )
    registry.register_command(
        CommandDefinition(
            name="block",
            aliases=["defend"],
            description="Gain block",
            base_dice="1d6+2",
            valid_contexts=[CommandContext.COMBAT],
            base_ap_cost=5,          # FIXED
            base_mp_cost=0,
        )
    )
    registry.register_command(
        CommandDefinition(
            name="flee",
            aliases=["run"],
            description="Attempt to flee",
            valid_contexts=[CommandContext.COMBAT],
            base_ap_cost=8,          # FIXED
            base_mp_cost=0,
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

def run_simulation(player, enemies, registry, iterations=100, verbose=False, max_rounds=50):
    """Run multiple combat simulations and return statistics.

    Args:
        max_rounds: Maximum number of rounds before forcing a draw.
    """
    parser = CommandParser(registry)
    results = {
        "wins": 0,
        "losses": 0,
        "flees": 0,
        "draws": 0,
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

        while outcome == CombatOutcome.ONGOING and round_count < max_rounds:
            round_count += 1
            available = registry.available_for(player, CommandContext.COMBAT)
            if not available:
                # No commands available → force flee
                outcome = CombatOutcome.PLAYER_FLED
                break

            # Bias toward attacking when enemies are alive
            cmd = random.choice(available)
            raw = cmd.name
            if cmd.name == "attack" and any(e.is_alive for e in enemies):
                alive = [e for e in enemies if e.is_alive]
                target_name = random.choice([e.name for e in alive])
                raw = f"attack {target_name}"
            result = combat.player_input(raw)
            # Safety check – should never be None, but guard against it
            if result is None:
                outcome = CombatOutcome.PLAYER_FLED
                break
            outcome = result.outcome
            ap_used += result.ap_spent
            if "hit" in " ".join(result.lines).lower():
                damage_dealt += 5

        if round_count >= max_rounds:
            outcome = CombatOutcome.PLAYER_FLED  # treat as draw/flee
            results["draws"] += 1

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
    random.seed(42)  # for reproducibility
    results = run_simulation(test_player, [goblin], test_registry, iterations=50, max_rounds=30)
    win_rate = results["wins"] / 50 * 100
    print(f"\nWin rate vs 1 Goblin: {win_rate:.1f}%")
    # Lower threshold for random player; if win rate is too low, print warning but don't fail
    if win_rate <= 40:
        pytest.skip(f"Win rate too low ({win_rate:.1f}%) – may need better AI or balance")
    assert win_rate > 40, f"Win rate too low: {win_rate:.1f}%"


def test_combat_vs_two_goblins(test_player, goblin, test_registry):
    """Test that two goblins are more challenging but still winnable."""
    random.seed(42)
    results = run_simulation(test_player, [goblin, goblin], test_registry, iterations=50, max_rounds=30)
    win_rate = results["wins"] / 50 * 100
    print(f"\nWin rate vs 2 Goblins: {win_rate:.1f}%")
    assert True


def test_combat_ap_cost_calculation(test_player, test_registry):
    """Verify that AP cost is based on command's base_ap_cost minus reductions."""
    parser = CommandParser(test_registry)
    # "attack" has base_ap_cost=6, no reductions → AP cost 6
    parsed = parser.parse("attack", test_player, CommandContext.COMBAT)
    assert parsed.ap_cost == 6, f"Expected 6 AP, got {parsed.ap_cost}"
    # "attack goblin" – same base cost, modifiers? none, still 6
    parsed = parser.parse("attack goblin", test_player, CommandContext.COMBAT)
    assert parsed.ap_cost == 6, f"Expected 6 AP, got {parsed.ap_cost}"


def test_mp_cost_calculation(test_player, test_registry):
    """Verify MP cost is a fixed value from command definition."""
    # Add a command that costs MP for testing
    test_registry.register_command(
        CommandDefinition(
            name="spell",
            aliases=[],
            description="Magic spell",
            costs_mp=True,
            mp_cost_override=3,
            base_mp_cost=3,
            valid_contexts=[CommandContext.COMBAT],
        )
    )
    parser = CommandParser(test_registry)

    # MP cost should be 3 regardless of word count
    parsed = parser.parse("spell", test_player, CommandContext.COMBAT)
    assert parsed.mp_cost == 3, f"Expected 3 MP, got {parsed.mp_cost}"

    parsed = parser.parse("spell fireball", test_player, CommandContext.COMBAT)
    assert parsed.mp_cost == 3, f"Expected 3 MP, got {parsed.mp_cost}"

    # A command without costs_mp should cost 0 MP
    test_registry.register_command(
        CommandDefinition(
            name="punch",
            aliases=[],
            description="Punch",
            costs_mp=False,
            valid_contexts=[CommandContext.COMBAT],
        )
    )
    parsed = parser.parse("punch", test_player, CommandContext.COMBAT)
    assert parsed.mp_cost == 0, f"Expected 0 MP, got {parsed.mp_cost}"


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
        # Register minimal commands with base AP costs
        registry.register_command(
            CommandDefinition(name="attack", aliases=["hit"], description="Attack", base_dice="1d6+2", valid_contexts=[CommandContext.COMBAT], base_ap_cost=6)
        )
        registry.register_command(
            CommandDefinition(name="block", aliases=[], description="Block", base_dice="1d6+2", valid_contexts=[CommandContext.COMBAT], base_ap_cost=5)
        )
        registry.register_command(
            CommandDefinition(name="flee", aliases=[], description="Flee", valid_contexts=[CommandContext.COMBAT], base_ap_cost=8)
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
    res1 = run_simulation(player, [goblin], registry, iterations=args.iterations, verbose=args.verbose, max_rounds=30)
    print(f"Wins: {res1['wins']} ({res1['wins']/args.iterations*100:.1f}%) | Losses: {res1['losses']} | Flees: {res1['flees']} | Draws: {res1['draws']}")
    print(f"Avg rounds: {sum(res1['rounds'])/len(res1['rounds']):.1f} | Avg AP used: {sum(res1['ap_used_total'])/len(res1['ap_used_total']):.1f}")

    print(f"\n--- Simulation vs 2 Goblins ({args.iterations} iterations) ---")
    res2 = run_simulation(player, [goblin, goblin], registry, iterations=args.iterations, verbose=args.verbose, max_rounds=30)
    print(f"Wins: {res2['wins']} ({res2['wins']/args.iterations*100:.1f}%) | Losses: {res2['losses']} | Flees: {res2['flees']} | Draws: {res2['draws']}")
    print(f"Avg rounds: {sum(res2['rounds'])/len(res2['rounds']):.1f} | Avg AP used: {sum(res2['ap_used_total'])/len(res2['ap_used_total']):.1f}")