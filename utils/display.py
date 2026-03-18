# utils/display.py
from utils.helpers import print_slow, print_status, rarity_colored, RARITY_COLORS, RESET


def show_intro():
    print_slow("=" * 52)
    print_slow("       Welcome to the Text Adventure Game!")
    print_slow("=" * 52)
    print()
    lore = [
        "This is an ancient world.",
        "",
        "Forever ago the good king ruled from the mighty castle complex —",
        "a fortress that allowed him to project power and to protect",
        "his subjects. But some sought to take this power for themselves.",
        "They deposed the good king, and as monsters swarmed the castle,",
        "the start of a new tyranny began.",
        "",
        "The old scholars had a saying that was more than metaphor:",
        "  words have power.",
        "",
        "In this world, they meant it literally. The right word, spoken",
        "with intent, can wound, shield, or shatter. Every command you",
        "give costs something — and the longer the word, the heavier",
        "the toll. Choose carefully. Speak with purpose.",
        "",
        "You have entered the castle complex. The good king is gone.",
        "What happens next is up to you.",
    ]
    for line in lore:
        if line == "":
            print()
        else:
            print_slow(f"  {line}")
    print()
    input("  Press Enter to continue...")
    print()


def show_room(room):
    import random
    alive = [e for e in room.enemies if e.health > 0]
    print(f"\n{'=' * 52}")
    print_slow(f"  {room.name}")
    print(f"{'=' * 52}")
    print(room.description)
    print()
    # Ambient flavour — one random line per visit
    if room.ambient:
        print_slow(f"  {random.choice(room.ambient)}")
        print()
    if room.items:
        print(f"  Items  : {', '.join(room.items)}")
    if room.relics:
        relic_strs = [rarity_colored(r) for r in room.relics]
        print(f"  Relics : {', '.join(relic_strs)}")
    if room.puzzle:
        status = "SOLVED ✦" if room.puzzle.solved else "unsolved"
        print(f"  Puzzle : {room.puzzle.name} [{status}]")
    if alive:
        enemy_str = ", ".join(
            f"[{i+1}] {e.name} (HP:{e.health})" for i, e in enumerate(alive)
        )
        print(f"  Enemies: {enemy_str}")
    exits = list(room.connections.keys())
    locked = room.locked_connections
    exit_strs = [f"{d}🔒" if d in locked else d for d in exits]
    print(f"  Exits  : {', '.join(exit_strs)}")


def show_help(player=None):
    lines = [
        "",
        "  Exploration:",
        "    north/south/east/west  - Move in a direction  (🔒 = locked)",
        "    take <item/relic>      - Pick up an item or relic",
        "    drop <item>            - Drop an item",
        "    inventory              - Show your items",
        "    relics                 - Show your relics and effects",
        "    listen                 - Listen for clues about nearby rooms",
        "    examine                - Examine a puzzle in this room",
        "    solve <answer>         - Attempt a puzzle solution",
        "    look                   - Describe the room again",
        "    rest                   - Restore AP (only when safe)",
        "    quit                   - Exit the game",
        "",
        "  Combat (AP resets each turn — cost = letters in command):",
        "    attack  (6 AP)         - Deal 8–18 damage to a target",
        "    heal    (4 AP + 1 MP)  - Restore 8–15 HP",
        "    block   (5 AP)         - Gain 7 Block this turn",
        "    end                    - End your turn (no confirm)",
        "    relics                 - Show your relics mid-combat",
    ]
    if player and player.known_commands:
        from entities.class_data import CLASS_COMMANDS
        cmd_descs = {}
        for tier in CLASS_COMMANDS.get(player.char_class, {}).values():
            for c in tier:
                cmd_descs[c["name"]] = c["desc"]
        lines.append("")
        lines.append("  Class commands (unlocked):")
        for name in sorted(player.known_commands):
            desc = cmd_descs.get(name, "")
            lines.append(f"    {name:<14} ({len(name)} AP)  - {desc}")
    else:
        lines.append("    [class commands]       - Unlocked on level-up")
    lines.append("")
    for line in lines:
        print(line)


def show_class_selection():
    """Display class options and return the chosen class string."""
    from entities.class_data import CLASS_DESCRIPTIONS
    print()
    print_slow("  ╔══════════════════════════════════════════════════╗")
    print_slow("  ║              Choose Your Class                   ║")
    print_slow("  ╚══════════════════════════════════════════════════╝")
    print()
    classes = ["soldier", "rogue", "mage"]
    for i, cls in enumerate(classes, 1):
        print(f"  [{i}] {CLASS_DESCRIPTIONS[cls]}")
        print()
    while True:
        choice = input("  Enter class (1/2/3) or name: ").lower().strip()
        if choice in ["1", "soldier"]:
            return "soldier"
        if choice in ["2", "rogue"]:
            return "rogue"
        if choice in ["3", "mage"]:
            return "mage"
        print("  Please enter 1, 2, or 3.")


def show_levelup(player):
    """Stat boosts, auto-unlocked commands, and pending choice menus."""
    while player.level_ups:
        lvl = player.level_ups.pop(0)
        player.max_health += 10
        player.health = player.max_health
        print()
        print_slow("  ╔══════════════════════════════════════╗")
        print_slow(f"  ║   ✦  LEVEL UP  —  LVL {lvl:<2}            ✦  ║")
        print_slow("  ║                                      ║")
        print_slow(f"  ║  Max HP increased to {player.max_health:<3}             ║")
        print_slow(f"  ║  HP fully restored!                  ║")
        print_slow("  ╚══════════════════════════════════════╝")
        print()
        print_status(player)

    while player.auto_unlocked_commands:
        name, desc = player.auto_unlocked_commands.pop(0)
        print()
        print_slow(f"  ✦ New command unlocked: [{name.upper()}]")
        print_slow(f"    {desc}")
        print_slow(f"    AP cost: {len(name)}")

    while player.pending_command_choices:
        level, choices = player.pending_command_choices.pop(0)
        print()
        print_slow(f"  ╔══════════════════════════════════════╗")
        print_slow(f"  ║   Choose a new command  (Lvl {level:<2})      ║")
        print_slow(f"  ╚══════════════════════════════════════╝")
        print()
        for i, cmd in enumerate(choices, 1):
            print_slow(f"  [{i}] {cmd['name'].upper():<14} (AP: {len(cmd['name'])})")
            print_slow(f"       {cmd['desc']}")
            print()
        while True:
            pick = input(f"  Choose (1-{len(choices)}): ").strip()
            if pick.isdigit() and 1 <= int(pick) <= len(choices):
                chosen = choices[int(pick) - 1]
                player.known_commands.add(chosen["name"])
                print_slow(f"\n  ✦ [{chosen['name'].upper()}] added to your repertoire!")
                print_slow(f"    {chosen['desc']}")
                break
            print("  Invalid choice.")

    input("\n  Press Enter to continue...")


def show_combat_enter(enemy_names):
    print()
    print_slow(f"  ⚠  Enemies confront you: {', '.join(enemy_names)}!")
    print_slow("  There is no escape. Prepare to fight.")
    print()


def show_relics(player):
    """Print all of the player's relics with art, rarity colour and description."""
    from utils.ascii_art import RELIC_ART, print_art
    if not player.relics:
        print_slow("  You carry no relics.")
        return
    print()
    for r in player.relics:
        color  = RARITY_COLORS.get(getattr(r, "rarity", "Common"), "")
        rarity = getattr(r, "rarity", "Common")
        art = RELIC_ART.get(r.name)
        if art:
            print_art(art, indent=10)
        print_slow(f"  ✦ {color}{r.name}{RESET}  [{rarity}]")
        print_slow(f"    {r.description}")
        print()