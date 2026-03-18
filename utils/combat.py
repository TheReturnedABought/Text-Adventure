# utils/combat.py
import random
from utils.helpers import print_slow, print_status
from utils.actions import get_alive_enemies, spend_ap
from utils.constants import MAX_AP
from game_engine.parser import parse_command


COMBAT_COMMANDS = ["attack", "heal", "block"]
BLOCK_REDUCTION = 0.5


def do_attack(player, enemy):
    dmg = random.randint(8, 18)
    enemy.take_damage(dmg)
    print_slow(f"  > You strike {enemy.name} for {dmg} damage! (Enemy HP: {max(enemy.health, 0)})")
    if enemy.health <= 0:
        print_slow(f"  > You defeated {enemy.name}! +{enemy.xp_reward} XP")
        player.gain_xp(enemy.xp_reward)


def do_heal(player):
    heal_amt = random.randint(8, 15)
    player.heal(heal_amt)
    print_slow(f"  > You heal for {heal_amt} HP! (Your HP: {player.health})")


def do_block(player):
    player.defending = True
    reduced_by = int(BLOCK_REDUCTION * 100)
    print_slow(f"  > You raise your guard — incoming damage reduced by {reduced_by}%!")


def enemy_counter(player, enemy):
    raw_dmg = random.randint(4, enemy.attack_power)
    if player.defending:
        actual_dmg = max(1, int(raw_dmg * BLOCK_REDUCTION))
        blocked = raw_dmg - actual_dmg
        player.defending = False
        player.take_damage(actual_dmg)
        print_slow(f"  {enemy.name} attacks for {raw_dmg} — you block {blocked}, taking {actual_dmg}! (Your HP: {player.health})")
    else:
        player.take_damage(raw_dmg)
        print_slow(f"  {enemy.name} hits you for {raw_dmg} damage! (Your HP: {player.health})")


def regen_ap(player):
    """Restore AP to full at the start of each player turn."""
    player.current_ap = MAX_AP


def show_combat_status(player, enemy):
    print(f"\n  {'─' * 46}")
    print_slow(f"  ⚔  {enemy.name}  —  HP: {enemy.health}/{enemy.max_health}")
    print(f"  {'─' * 46}")
    print_status(player)
    cost_str = "  attack(6) | heal(4) | block(5) | end — end turn"
    print(f"\n  {cost_str}")


def check_levelup(player):
    """Show level-up screen if any are queued. Called after killing an enemy."""
    if player.level_ups:
        from utils.display import show_levelup
        show_levelup(player)


def player_turn(player, enemy):
    """
    Player spends AP freely, types 'end' to finish or runs out of AP.
    Returns True if enemy is still alive after the turn.
    """
    regen_ap(player)
    show_combat_status(player, enemy)

    while True:
        if enemy.health <= 0:
            return False

        raw = input("\n⚔ > ").lower().strip()
        if not raw:
            continue

        command, _ = parse_command(raw)

        if command in ["end", "done", "pass", "endturn"]:
            print_slow("  You end your turn.")
            return True

        if command in ["move", "go", "north", "south", "east", "west", "flee", "run", "escape"]:
            print_slow("  You cannot flee! Fight or die!")
            continue

        if command in ["inventory", "inv", "i"]:
            from utils.actions import do_inventory
            do_inventory(player)
            continue

        if command in ["look", "l"]:
            print_slow(f"  You are fighting {enemy.name}. There is no escape.")
            continue

        if command in ["help", "?"]:
            print_slow("  attack(6 AP) | heal(4 AP) | block(5 AP) | end — end turn")
            continue

        if command not in COMBAT_COMMANDS:
            print_slow(f"  Unknown action. Use: attack, heal, block, or end.")
            continue

        if not spend_ap(player, command):
            print_slow("  Not enough AP — type 'end' to end your turn.")
            continue

        if command == "attack":
            do_attack(player, enemy)
        elif command == "heal":
            do_heal(player)
        elif command == "block":
            do_block(player)

        print_status(player)

        if player.current_ap == 0:
            print_slow("  No AP remaining — ending your turn.")
            return enemy.health > 0


def combat_loop(player, room):
    """
    Turn-based combat. Player acts freely each turn, then enemy attacks once.
    AP resets to full at the start of each player turn.
    """
    while True:
        alive = get_alive_enemies(room)
        if not alive:
            print()
            print_slow("  ✦ All enemies defeated! ✦")
            regen_ap(player)
            if player.level_ups:
                input("\n  Press Enter to continue...")
                from utils.display import show_levelup
                show_levelup(player)
            else:
                input("\n  Press Enter to continue...")
            break

        enemy = alive[0]
        enemy_alive = player_turn(player, enemy)

        if player.health <= 0:
            break

        if not enemy_alive:
            continue

        # Enemy attacks once at end of turn
        print(f"\n  {'─' * 46}")
        print_slow(f"  {enemy.name}'s turn")
        print(f"  {'─' * 46}")
        enemy_counter(player, enemy)
        print()

        if player.health <= 0:
            break