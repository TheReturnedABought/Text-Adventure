# utils/display.py
from utils.helpers import print_slow, print_status, rarity_colored, RARITY_COLORS, RESET, BLUE
from utils.constants import (
    BASE_COMMANDS, BASE_ATTACK_MIN, BASE_ATTACK_MAX,
    BASE_HEAL_MIN, BASE_HEAL_MAX, BASE_BLOCK, HEAL_MP_COST,
)


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
    exits   = list(room.connections.keys())
    locked  = room.locked_connections
    exit_strs = [f"{d}🔒" if d in locked else d for d in exits]
    print(f"  Exits  : {', '.join(exit_strs)}")
    if room.env_objects:
        usable = [o.name for o in room.env_objects if o._uses_left > 0]
        if usable:
            print(f"  Objects: {', '.join(usable)}")


def show_help(player=None):
    """
    Print all commands. Base command costs come from constants.BASE_COMMANDS;
    class command costs come from class_data.cmd_ap_cost().
    Changing either source propagates here automatically.
    """
    atk_ap   = BASE_COMMANDS["attack"]["ap_cost"]
    heal_ap  = BASE_COMMANDS["heal"]["ap_cost"]
    blk_ap   = BASE_COMMANDS["block"]["ap_cost"]

    lines = [
        "",
        "  Exploration:",
        "    north/south/east/west  - Move in a direction  (🔒 = locked)",
        "    take <item/relic>      - Pick up an item or relic",
        "    drop <item>            - Drop an item",
        "    use <item>             - Use a consumable",
        "    inventory              - Show your items",
        "    relics                 - Show your relics and effects",
        "    interact               - Interact with an event or NPC",
        "    listen                 - Hear clues about nearby rooms",
        "    examine                - Examine a puzzle or object",
        "    solve <answer>         - Attempt a puzzle solution",
        "    look                   - Describe the room again",
        "    rest                   - Restore AP (safe rooms only)",
        "    map                    - Show ASCII map of explored rooms",
        "    journal                - Open codex: lore and enemy records",
        "    quit                   - Exit the game",
        "",
        "  Combat (AP resets each turn — cost = letters in command):",
        f"    attack  ({atk_ap} AP)         - Deal {BASE_ATTACK_MIN}–{BASE_ATTACK_MAX} damage to a target",
        f"    heal    ({heal_ap} AP +{HEAL_MP_COST} MP)  - Restore {BASE_HEAL_MIN}–{BASE_HEAL_MAX} HP",
        f"    block   ({blk_ap} AP)         - Gain {BASE_BLOCK} Block this turn",
        "    end                    - End your turn (no confirm)",
        "    relics                 - Show your relics mid-combat",
        "    Enemy planned moves are shown in the combat HUD each turn.",
    ]
    if player and player.known_commands:
        from entities.class_data import CLASS_COMMANDS, cmd_ap_cost, get_command_def
        lines.append("")
        lines.append("  Class commands (unlocked):")
        for name in sorted(player.known_commands):
            cmd_def = get_command_def(player.char_class, name)
            ap      = cmd_ap_cost(cmd_def) if cmd_def else len(name)
            mp      = cmd_def.get("mp_cost", 0) if cmd_def else 0
            mp_str  = f" +{mp} MP" if mp else ""
            desc    = cmd_def["desc"] if cmd_def else ""
            lines.append(f"    {name:<14} ({ap} AP{mp_str})  - {desc}")
    else:
        lines.append("    [class commands]       - Unlocked on level-up")
    lines.append("")
    for line in lines:
        print(line)


def show_class_selection():
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
        if choice in ["1", "soldier"]:  return "soldier"
        if choice in ["2", "rogue"]:    return "rogue"
        if choice in ["3", "mage"]:     return "mage"
        print("  Please enter 1, 2, or 3.")


def show_levelup(player):
    """Stat boosts, auto-unlocked commands, and pending choice menus.
    AP costs read from CommandDef so they stay in sync with class_data."""
    from entities.class_data import cmd_ap_cost, cmd_mp_cost

    while player.level_ups:
        lvl = player.level_ups.pop(0)
        player.max_health += 10
        player.health += 10
        print()
        print_slow("  ╔══════════════════════════════════════╗")
        print_slow(f"  ║   ✦  LEVEL UP  —  LVL {lvl:<2}            ✦  ║")
        print_slow("  ║                                      ║")
        print_slow(f"  ║  Max HP increased to {player.max_health:<3}             ║")
        print_slow("  ╚══════════════════════════════════════╝")
        print()
        print_status(player)

    while player.auto_unlocked_commands:
        name, desc = player.auto_unlocked_commands.pop(0)
        from entities.class_data import get_command_def
        cmd_def = get_command_def(player.char_class, name)
        ap = cmd_ap_cost(cmd_def) if cmd_def else len(name)
        print()
        print_slow(f"  ✦ New command unlocked: [{name.upper()}]")
        print_slow(f"    {desc}")
        print_slow(f"    AP cost: {ap}")

    while player.pending_command_choices:
        level, choices = player.pending_command_choices.pop(0)
        print()
        print_slow(f"  ╔══════════════════════════════════════╗")
        print_slow(f"  ║   Choose a new command  (Lvl {level:<2})      ║")
        print_slow(f"  ╚══════════════════════════════════════╝")
        print()
        for i, cmd in enumerate(choices, 1):
            ap     = cmd_ap_cost(cmd)
            mp     = cmd_mp_cost(cmd)
            mp_str = f" +{mp} MP" if mp else ""
            print_slow(f"  [{i}] {cmd['name'].upper():<14} ({ap} AP{mp_str})")
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


# ── Map renderer ──────────────────────────────────────────────────────────────

def show_map(start_room, current_room):
    """
    Render an ASCII map of all explored rooms (visit_count > 0).
    Unexplored neighbours of visited rooms show as [???].
    The current room is marked with *.
    """
    from collections import deque

    DIRS = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}

    # BFS to assign grid coordinates
    grid = {}   # (col, row) -> Room
    inv  = {}   # id(room)   -> (col, row)
    q    = deque([(start_room, 0, 0)])
    seen = {id(start_room)}

    while q:
        room, col, row = q.popleft()
        if (col, row) not in grid:
            grid[(col, row)] = room
            inv[id(room)]    = (col, row)
        for d, nb in room.connections.items():
            if id(nb) not in seen and d in DIRS:
                dc, dr   = DIRS[d]
                nc, nr   = col + dc, row + dr
                if (nc, nr) not in grid:
                    seen.add(id(nb))
                    q.append((nb, nc, nr))

    if not grid:
        print_slow("  No map data available.")
        return

    cols_all  = [c for c, r in grid]
    rows_all  = [r for c, r in grid]
    min_c, max_c = min(cols_all), max(cols_all)
    min_r, max_r = min(rows_all), max(rows_all)

    CELL = 18   # character width per grid column

    def cell_str(room):
        if room is current_room:
            label = f"*{room.name[:CELL - 4]}*"
        elif room.visit_count == 0:
            label = "???"
        else:
            label = room.name[:CELL - 2]
        return f"[{label}]".center(CELL)

    def has_conn(a, b):
        """True if a direct connection exists between two rooms."""
        return b in a.connections.values() or a in b.connections.values()

    def is_locked_between(a, b):
        for d, nb in a.connections.items():
            if nb is b and d in a.locked_connections:
                return True
        return False

    print(f"\n  MAP {'─' * 48}")

    for r in range(min_r, max_r + 1):
        # ── Room row ──────────────────────────────────────────────────────────
        line = "  "
        for c in range(min_c, max_c + 1):
            room = grid.get((c, r))
            line += cell_str(room) if room else " " * CELL
            # Horizontal connector to east neighbour
            if c < max_c:
                er = grid.get((c + 1, r))
                if room and er and has_conn(room, er):
                    line += "🔒" if is_locked_between(room, er) else "──"
                else:
                    line += "  "
        print(line)

        # ── Vertical connector row ────────────────────────────────────────────
        if r < max_r:
            vline = "  "
            for c in range(min_c, max_c + 1):
                room = grid.get((c, r))
                sr   = grid.get((c, r + 1))
                if room and sr and has_conn(room, sr):
                    vline += (" " * (CELL // 2 - 1)) + " | " + (" " * (CELL - CELL // 2 - 2))
                else:
                    vline += " " * CELL
                if c < max_c:
                    vline += "  "
            print(vline)

    print(f"  {'─' * 52}")
    print("  [*Name] = you are here  |  [???] = unexplored")
    print()


# ── Journal display delegated to Journal.show() ──────────────────────────────

def show_journal(player):
    player.journal.show()