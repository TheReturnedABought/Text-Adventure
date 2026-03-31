# utils/actions.py
from utils.helpers import print_slow
from collections import Counter
from rooms.room import Puzzle


def get_alive_enemies(room):
    return [e for e in room.enemies if e.health > 0]


def _stacked_items(items):
    counts = Counter(items)
    out = []
    for name, count in counts.items():
        out.append(f"{count} x {name}" if count > 1 else name)
    return out


def _parse_amount_and_query(args):
    if not args:
        return None, ""

    amount = None
    parts = list(args)

    if parts[0].isdigit():
        amount = max(1, int(parts[0]))
        parts = parts[1:]
    elif parts[-1].isdigit():
        amount = max(1, int(parts[-1]))
        parts = parts[:-1]

    return amount, " ".join(parts).strip().lower()


def _ask_amount(action, item_name, max_count):
    while True:
        raw = input(f"  How many {item_name} to {action}? (1-{max_count}): ").strip()
        if raw.isdigit():
            val = int(raw)
            if 1 <= val <= max_count:
                return val
        print_slow(f"  Enter a number between 1 and {max_count}.")


def do_move(player, room, args):
    direction = args[0] if args else ""
    if direction in room.connections:
        required = room.locked_connections.get(direction)
        if required:
            held = [i.lower() for i in player.inventory]
            if required.lower() in held:
                print_slow(f"  You use the {required} to unlock the way {direction}.")
                del room.locked_connections[direction]
            else:
                print_slow(f"  The way {direction} is locked. You need: {required}.")
                return room
        print_slow(f"  You move {direction}...")
        return room.connections[direction]
    print_slow("  You can't go that way.")
    return room


def do_take_relic(player, room, args):
    amount, query = _parse_amount_and_query(args)
    if not query:
        print_slow("  Take what?")
        return
    relic_match = next((r for r in room.relics if query in r.name.lower()), None)
    if relic_match:
        room.relics.remove(relic_match)
        player.add_relic(relic_match)
        from utils.helpers import RARITY_COLORS, RESET
        from utils.ascii_art import RELIC_ART, print_art
        color  = RARITY_COLORS.get(getattr(relic_match, "rarity", "Common"), "")
        rarity = getattr(relic_match, "rarity", "Common")
        print()
        art = RELIC_ART.get(relic_match.name)
        if art:
            print_art(art, indent=10)
        print_slow(f"  ✦ You obtain the {color}{relic_match.name}{RESET}!")
        print_slow(f"    [{rarity}] {relic_match.description}")
        input("\n  Press Enter to continue...")
        return
    item_matches = [i for i in room.items if query in i.lower()]
    if item_matches:
        if amount is None:
            amount = _ask_amount("pick up", item_matches[0], len(item_matches)) if len(item_matches) > 1 else 1
        amount = min(amount, len(item_matches))
        picked = item_matches[:amount]
        for item in picked:
            room.items.remove(item)

        gold_taken = sum(1 for i in picked if "gold coin" in i.lower())
        normal_items = [i for i in picked if "gold coin" not in i.lower()]
        if gold_taken:
            player.gold = getattr(player, "gold", 0) + gold_taken
            print_slow(f"  You collect {gold_taken} gold coin(s). (Gold: {player.gold})")
        if normal_items:
            player.inventory.extend(normal_items)
            stacked = ", ".join(_stacked_items(normal_items))
            print_slow(f"  You pick up: {stacked}")
        return
    print_slow(f"  Nothing here matches '{query}'.")


def do_drop(player, room, args):
    amount, query = _parse_amount_and_query(args)
    if not query:
        print_slow("  Drop what?")
        return
    matches = [i for i in player.inventory if query in i.lower()]
    if not matches:
        print_slow("  You don't have that.")
        return

    if amount is None:
        amount = _ask_amount("drop", matches[0], len(matches)) if len(matches) > 1 else 1
    amount = min(amount, len(matches))
    dropped = matches[:amount]
    for item in dropped:
        player.inventory.remove(item)
        room.items.append(item)
    print_slow(f"  You drop: {', '.join(_stacked_items(dropped))}")


def do_inventory(player):
    if player.inventory:
        print_slow("  Inventory: " + ", ".join(_stacked_items(player.inventory)))
    else:
        print_slow("  Your inventory is empty.")
    print_slow(f"  Gold: {getattr(player, 'gold', 0)}")


def do_listen(player, room):
    hints = room.listen_hints()
    if not hints:
        print_slow("  You hear nothing — there are no exits to listen at.")
        return
    print_slow("\n  You press your ear to the walls and listen carefully...")
    for direction, hint in hints:
        print_slow(f"  {direction.capitalize():<6}: {hint}")


def do_examine(player, room, args):
    target = "room" if not args else " ".join(args).lower()
    obj = room.get_env_object(target)

    if obj is None:
        print_slow("  There is nothing of particular note to examine here.")
        return

    obj.examine(player, room)

def do_solve(player, room, args):
    if not args:
        print_slow("  Usage: solve <puzzle answer>")
        return

    answer = " ".join(args).lower()
    puzzle = next((o for o in room.env_objects if isinstance(o, Puzzle) and o.visible), None)
    if not puzzle:
        print_slow("  There is no puzzle here to solve.")
        return

    puzzle.attempt(player, room, answer)


def do_interact(player, room, args):
    target = "room" if not args else " ".join(args).lower()
    obj = room.get_env_object(target)

    if obj is None:
        print_slow("  There is nothing to interact with here.")
        return

    if hasattr(obj, "activate"):
        result = obj.activate(player, room, room.alive_enemies)
        if isinstance(result, str) and result:
            print_slow(result)
        return

    print_slow("  That cannot be interacted with.")


def do_map(game):
    """Show the ASCII map. Requires game.start_room to be set."""
    from utils.display import show_map
    start = getattr(game, "start_room", None)
    if start is None:
        print_slow("  No map available yet.")
        return
    show_map(start, game.room)


def do_journal(player):
    from utils.display import show_journal
    show_journal(player)


# ── Mushroom / food tables ─────────────────────────────────────────────────────

MUSHROOM_EFFECTS = {
    "red mushroom":  ("rage",   2),
    "blue mushroom": ("regen",  4),
    "gold mushroom": ("block",  10),
    "dark mushroom": ("poison", 3),
    "mushroom":      None,
}

_GENERIC_MUSHROOM_POOL = [
    ("rage",   2),
    ("regen",  4),
    ("poison", 2),
]

FOOD_ITEMS = {"apple": 15, "bread": 20}


def use_item(player, room, args):
    import random
    amount, query = _parse_amount_and_query(args)
    if not query:
        print_slow("  Use what?")
        return
    matches = [i for i in player.inventory if query in i.lower()]
    if not matches:
        print_slow(f"  You don't have '{query}'.")
        return
    if amount is None:
        amount = _ask_amount("use", matches[0], len(matches)) if len(matches) > 1 else 1
    amount = min(amount, len(matches))
    used = matches[:amount]
    name_lower = used[0].lower()

    # Food
    for food, hp in FOOD_ITEMS.items():
        if food in name_lower:
            for item in used:
                player.inventory.remove(item)
            total_heal = hp * amount
            player.heal(total_heal)
            print_slow(f"  You eat {amount} x {food}. (+{total_heal} HP → {player.health}/{player.max_health})")
            return

    # Mushroom
    if "mushroom" in name_lower:
        for item in used:
            player.inventory.remove(item)
            effect = MUSHROOM_EFFECTS.get(item.lower())
            if effect is None:
                effect = random.choice(_GENERIC_MUSHROOM_POOL)
            player.pending_combat_effects.append(effect)
        print_slow(f"  You eat {', '.join(_stacked_items(used))}.")
        print_slow("  Something stirs in your blood — the effect(s) will manifest when next you fight.")
        return

    print_slow(f"  You can't use the {used[0]} here.")
