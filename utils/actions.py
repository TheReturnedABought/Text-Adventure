# utils/actions.py
from utils.helpers import print_slow
from utils.constants import MAX_AP


def get_alive_enemies(room):
    return [e for e in room.enemies if e.health > 0]


def spend_ap(player, command):
    cost = len(command)
    if player.current_ap < cost:
        print_slow(f"Not enough AP! '{command}' costs {cost} AP, you have {player.current_ap}.")
        return False
    player.current_ap -= cost
    return True


def do_move(player, room, args):
    direction = args[0] if args else ""
    if direction in room.connections:
        print_slow(f"You move {direction}...")
        return room.connections[direction]
    print_slow("You can't go that way.")
    return room


def do_take(player, room, args):
    item = args[0] if args else ""
    if item in room.items:
        player.inventory.append(item)
        room.items.remove(item)
        print_slow(f"You picked up: {item}")
    else:
        print_slow("No such item here.")


def do_take_relic(player, room, args):
    """Pick up a relic by partial name match."""
    query = " ".join(args).lower() if args else ""
    match = next((r for r in room.relics if query in r.name.lower()), None)
    if match:
        room.relics.remove(match)
        player.add_relic(match)
        print_slow(f"  ✦ You obtain the {match.name}!")
        print_slow(f"    {match.description}")
    else:
        # Fall through to normal item take
        do_take(player, room, args)


def do_drop(player, room, args):
    item = args[0] if args else ""
    if item in player.inventory:
        player.inventory.remove(item)
        room.items.append(item)
        print_slow(f"You dropped: {item}")
    else:
        print_slow("You don't have that.")


def do_inventory(player):
    if player.inventory:
        print_slow("Inventory: " + ", ".join(player.inventory))
    else:
        print_slow("Your inventory is empty.")


def do_rest(player, room):
    if get_alive_enemies(room):
        print_slow("You can't rest while enemies are nearby!")
    else:
        player.current_ap = MAX_AP
        print_slow(f"You rest and restore your AP to {MAX_AP}.")