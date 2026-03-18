# utils/actions.py
from utils.helpers import print_slow
from utils.constants import MAX_AP


def get_alive_enemies(room):
    return [e for e in room.enemies if e.health > 0]


def spend_ap(player, command):
    cost = len(command)
    if player.current_ap < cost:
        print_slow(f"  Not enough AP! '{command}' costs {cost} AP, you have {player.current_ap}.")
        return False
    player.current_ap -= cost
    return True


def do_move(player, room, args):
    direction = args[0] if args else ""
    if direction in room.connections:
        # Locked door check
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
    """Pick up a relic or item by partial name match (handles multi-word names)."""
    query = " ".join(args).lower() if args else ""
    if not query:
        print_slow("  Take what?")
        return

    # Relic match first
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

    # Item partial match
    item_match = next((i for i in room.items if query in i.lower()), None)
    if item_match:
        player.inventory.append(item_match)
        room.items.remove(item_match)
        print_slow(f"  You pick up: {item_match}")
        return

    print_slow(f"  Nothing here matches '{query}'.")


def do_drop(player, room, args):
    query = " ".join(args).lower() if args else ""
    match = next((i for i in player.inventory if query in i.lower()), None)
    if match:
        player.inventory.remove(match)
        room.items.append(match)
        print_slow(f"  You drop: {match}")
    else:
        print_slow("  You don't have that.")


def do_inventory(player):
    if player.inventory:
        print_slow("  Inventory: " + ", ".join(player.inventory))
    else:
        print_slow("  Your inventory is empty.")


def do_rest(player, room):
    if get_alive_enemies(room):
        print_slow("  You can't rest while enemies are nearby!")
    else:
        player.current_ap = MAX_AP
        print_slow(f"  You rest and restore your AP to {MAX_AP}.")


def do_listen(player, room):
    """Print directional sensory hints about each connected room."""
    hints = room.listen_hints()
    if not hints:
        print_slow("  You hear nothing — there are no exits to listen at.")
        return
    print_slow("\n  You press your ear to the walls and listen carefully...")
    for direction, hint in hints:
        print_slow(f"  {direction.capitalize():<6}: {hint}")


def do_examine(player, room, args):
    """Examine the room puzzle (or note there is nothing to examine)."""
    if room.puzzle:
        room.puzzle.examine()
    else:
        print_slow("  There is nothing of particular note to examine here.")


def do_solve(player, room, args):
    """Attempt to solve the room puzzle with the given answer."""
    if not room.puzzle:
        print_slow("  There is no puzzle here to solve.")
        return
    if not args:
        print_slow("  Usage: solve <your answer>")
        return
    room.puzzle.attempt(player, room, " ".join(args))