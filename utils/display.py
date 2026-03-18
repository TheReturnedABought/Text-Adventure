# utils/display.py
from utils.helpers import print_slow, print_status


def show_intro():
    print_slow("=" * 50)
    print_slow("     Welcome to the Text Adventure Game!")
    print_slow("=" * 50)


def show_room(room):
    alive = [e for e in room.enemies if e.health > 0]
    print(f"\n{'=' * 50}")
    print_slow(f"  {room.name}")
    print(f"{'=' * 50}")
    print(room.description)
    print()
    if room.items:
        print(f"  Items  : {', '.join(room.items)}")
    if alive:
        print(f"  Enemies: {', '.join([f'{e.name} (HP:{e.health})' for e in alive])}")
    print(f"  Exits  : {', '.join(room.connections.keys())}")


def show_help():
    lines = [
        "",
        "  Exploration:",
        "    north/south/east/west  - Move in a direction",
        "    take <item>            - Pick up an item",
        "    drop <item>            - Drop an item",
        "    inventory              - Show your items",
        "    look                   - Describe the room again",
        "    rest                   - Restore HP (only when safe)",
        "    quit                   - Exit the game",
        "",
        "  Combat (AP resets to full each turn):",
        "    attack  (6 AP)         - Strike the enemy",
        "    heal    (4 AP)         - Restore some HP",
        "    block   (5 AP)         - Halve the next hit",
        "    end                    - End your turn (enemy attacks)",
        "",
    ]
    for line in lines:
        print(line)


def show_levelup(player):
    """Full-screen level-up pause. Applies stat boosts and drains the level_ups queue."""
    while player.level_ups:
        lvl = player.level_ups.pop(0)
        player.max_health += 10
        player.health = player.max_health
        print()
        print_slow("  ╔══════════════════════════════╗")
        print_slow(f"  ║   ✦  LEVEL UP  —  LVL {lvl:<2}   ✦  ║")
        print_slow("  ║                              ║")
        print_slow(f"  ║  Max HP increased to {player.max_health:<3}      ║")
        print_slow(f"  ║  HP fully restored!          ║")
        print_slow("  ╚══════════════════════════════╝")
        print()
        print_status(player)
        input("\n  Press Enter to continue...")


def show_combat_enter(enemy_names):
    print()
    print_slow(f"  ⚠  You are confronted by: {', '.join(enemy_names)}!")
    print_slow("  There is no escape. Prepare to fight.")
    print()