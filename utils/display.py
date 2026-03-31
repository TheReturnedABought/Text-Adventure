# utils/display.py
from utils.helpers import print_slow, print_status, rarity_colored, RARITY_COLORS, RESET
from utils.constants import (
    BASE_COMMANDS, BASE_ATTACK_MIN, BASE_ATTACK_MAX,
    BASE_HEAL_MIN, BASE_HEAL_MAX, BASE_BLOCK, HEAL_MP_COST,
)
from collections import Counter


def _stacked_items(items):
    counts = Counter(items)
    return [f"{count} x {name}" if count > 1 else name for name, count in counts.items()]


def show_intro():
    print_slow("=" * 52)
    print_slow("       Welcome to the Text Adventure Game!")
    print_slow("=" * 52)
    print()
    lore = [
        "The sky was bruised with the last light of dusk when you crossed the shattered threshold of the old castle.",
        "Stone archways cracked with age framed corridors dark as forgotten secrets.",
        "Somewhere deep within, a distant howl echoed — not quite animal, not quite nightmare.",
        "Yet with every step, a faint warmth pulsed in your chest, as if the walls themselves whispered something only you could hear.",
        "",
        "Here, in this broken place, the tyranny that swallowed the kingdom still clung to life.",
        "Monsters skulked in the shadows, remnants of a power gone terribly wrong.",
        "And above it all, the throne room lay empty — the seat once held by the good king, now claimed by silence and fear.",
        "",
        "But long ago, when hope still clung to the world like dew on morning grass, the king summoned the greatest minds, warriors, and dreamers to his hall.",
        "He spoke not of swords or shields, but of something deeper — something that could change the fate of all living things.",
        "",
        "“Words have power.",
        "True power.",
        "Speak them with courage, and you can shape the world.",
        "Speak them with purpose, and you can turn back the darkness.",
        "Guard this truth, for it is the hope of all.”",
        "",
        "In this land, those were not empty platitudes — they were law.",
        "Every word wielded bore magic.",
        "A command could cleave shadow like steel, fortify weary hearts, or mend what was broken.",
        "But every utterance carried a price, and the mightiest words demanded the greatest toll.",
        "",
        "You feel the old king’s words as a spark within you now — a promise and a burden.",
        "Darkness stretches long across these halls, but somewhere beyond, the first dawn waits.",
        "",
        "And so, with the echo of hope in your mind and a choice in your heart, you take your first step forward, into the destiny that you will write."
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
    visible_objects = [o.name for o in room.env_objects if o.visible and o._uses_left > 0]
    room_objects = _stacked_items(room.items) + visible_objects
    if room_objects:
        print(f"  Objects: {', '.join(room_objects)}")
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
        "    take [n] <item/relic>  - Pick up 1..n matching items/relics",
        "    drop [n] <item>        - Drop 1..n matching items",
        "    use [n] <item>         - Use 1..n consumables",
        "    inventory              - Show your items",
        "    relics                 - Show your relics and effects",
        "    interact <>             - Interact with an event or NPC",
        "    listen                 - Hear clues about nearby rooms",
        "    examine <obj>          - Examine a puzzle or object",
        "    solve <answer>         - Attempt a puzzle solution",
        "    look                   - Describe the room again",
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
        from entities.class_data import cmd_ap_cost, get_command_def
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
        print_slow("  ╔══════════════════════════════════════╗")
        print_slow(f"  ║   Choose a new command  (Lvl {level:<2})      ║")
        print_slow("  ╚══════════════════════════════════════╝")
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
    Render a non-Euclidean ASCII map of all explored rooms (visit_count > 0).
    Unexplored neighbours of visited rooms show as [???].
    The current room is marked with *.
    """
    from collections import deque, defaultdict

    # BFS to discover all rooms
    q = deque([start_room])
    seen = {id(start_room)}
    room_graph = defaultdict(list)  # room -> list of (direction, neighbor)
    room_names = {}  # room -> display name

    while q:
        room = q.popleft()
        room_names[room] = room.name if room.visit_count > 0 else "???"
        for direction, neighbor in room.connections.items():
            room_graph[room].append((direction, neighbor))
            if id(neighbor) not in seen:
                seen.add(id(neighbor))
                q.append(neighbor)

    # Dynamic position assignment for ASCII layout
    positions = {}  # room -> (x, y)
    spacing_x, spacing_y = 12, 4
    visited = set()

    def assign_pos(room, x, y):
        if room in visited:
            return
        visited.add(room)
        positions[room] = (x, y)
        children = room_graph.get(room, [])
        for i, (_, nbr) in enumerate(children):
            dx = (i - len(children) // 2) * spacing_x
            dy = spacing_y
            assign_pos(nbr, x + dx, y + dy)

    assign_pos(start_room, 0, 0)

    if not positions:
        print("  No map data available.")
        return

    # Prepare canvas
    xs = [x for x, y in positions.values()]
    ys = [y for x, y in positions.values()]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    width  = max_x - min_x + spacing_x
    height = max_y - min_y + spacing_y
    canvas = [[" "] * width for _ in range(height)]

    def put_text(cx, cy, text):
        x0, y0 = cx - min_x, cy - min_y
        for i, ch in enumerate(text):
            if 0 <= x0 + i < width and 0 <= y0 < height:
                canvas[y0][x0 + i] = ch

    # Draw rooms
    for room, (x, y) in positions.items():
        name   = room_names[room]
        marker = "*" if room == current_room else ""
        put_text(x, y, f"[{name}{marker}]")

    # Draw connections
    for room, links in room_graph.items():
        x0, y0 = positions[room]
        for _, nbr in links:
            if nbr not in positions:
                continue
            x1, y1 = positions[nbr]
            if x0 == x1:
                for y_line in range(min(y0, y1) + 1, max(y0, y1)):
                    put_text(x0, y_line, "|")
            elif y0 == y1:
                for x_line in range(min(x0, x1) + 1, max(x0, x1)):
                    put_text(x_line, y0, "-")
            else:
                dx = 1 if x1 > x0 else -1
                dy = 1 if y1 > y0 else -1
                xi, yi = x0, y0
                while xi != x1 or yi != y1:
                    if xi != x1: xi += dx
                    if yi != y1: yi += dy
                    put_text(xi, yi, "/")

    # Print canvas
    for row in canvas:
        print("".join(row))
    print(f"  {'─' * 52}")
    print("  [*Name] = you are here  |  [???] = unexplored")
    print()


# ── Journal display delegated to Journal.show() ──────────────────────────────

def show_journal(player):
    player.journal.show()
