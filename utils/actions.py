# utils/actions.py
from utils.helpers import print_slow
from utils.constants import MAX_AP


def get_alive_enemies(room):
    return [e for e in room.enemies if e.health > 0]


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
    query = " ".join(args).lower() if args else ""
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


def do_listen(player, room):
    hints = room.listen_hints()
    if not hints:
        print_slow("  You hear nothing — there are no exits to listen at.")
        return
    print_slow("\n  You press your ear to the walls and listen carefully...")
    for direction, hint in hints:
        print_slow(f"  {direction.capitalize():<6}: {hint}")


def do_examine(player, room, args):
    target = "room" if not args else args[0]

    # Use existing get_env_object for partial matching
    obj = room.get_env_object(target)

    # If nothing found, check room-level events (like "room")
    if obj is None:
        if target == "room" and hasattr(room, "event") and room.event and room.event.trigger == "examine":
            room.event.show(player, room)
            return
        # fallback
        print_slow("  There is nothing of particular note to examine here.")
        return

    # Puzzle object
    if isinstance(obj, Puzzle):
        obj.examine()
        return

    # EnvObject (hazard or interactable)
    if isinstance(obj, EnvObject):
        print_slow(f"  You inspect the {obj.name}. Nothing unusual happens.")
        return

    # Fallback
    print_slow(f"  You examine the {target}. Nothing remarkable happens.")

def do_solve(player, room, args):
    if not room.puzzle:
        print_slow("  There is no puzzle here to solve.")
        return
    if not args:
        print_slow("  Usage: solve <your answer>")
        return
    room.puzzle.attempt(player, room, " ".join(args))


def do_interact(player, room):
    if room.event:
        room.event.show(player, room)
    else:
        print_slow("  There is nothing to interact with here.")


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
    query = " ".join(args).lower() if args else ""
    if not query:
        print_slow("  Use what?")
        return
    match = next((i for i in player.inventory if query in i.lower()), None)
    if not match:
        print_slow(f"  You don't have '{query}'.")
        return
    name_lower = match.lower()

    # Food
    for food, hp in FOOD_ITEMS.items():
        if food in name_lower:
            player.inventory.remove(match)
            player.heal(hp)
            print_slow(f"  You eat the {match}. (+{hp} HP → {player.health}/{player.max_health})")
            return

    # Mushroom
    if "mushroom" in name_lower:
        player.inventory.remove(match)
        effect = MUSHROOM_EFFECTS.get(name_lower)
        if effect is None:
            effect = random.choice(_GENERIC_MUSHROOM_POOL)
        player.pending_combat_effects.append(effect)
        print_slow(f"  You eat the {match}.")
        print_slow("  Something stirs in your blood — the effect will manifest when next you fight.")
        return

    print_slow(f"  You can't use the {match} here.")