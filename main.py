# main.py
import os
import sys

from entities.player import Player
from rooms.map_data import setup_rooms
from game_engine.engine import GameEngine
from game_engine.parser import parse_command
from utils.helpers import print_slow, print_status
from utils.display import show_intro, show_room, show_help, show_combat_enter
from utils.actions import do_move, do_take, do_take_relic, do_drop, do_inventory, do_rest, get_alive_enemies
from utils.combat import combat_loop

BASE_PATH = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))


def handle_command(command, args, player, room):
    if command in ["move", "go", "walk"]:
        return do_move(player, room, args)
    if command in ["north", "south", "east", "west", "up", "down"]:
        return do_move(player, room, [command])
    if command in ["take", "pick", "grab"]:
        do_take_relic(player, room, args)
    elif command == "drop":
        do_drop(player, room, args)
    elif command in ["inventory", "inv", "i"]:
        do_inventory(player)
    elif command in ["relics", "relic"]:
        if player.relics:
            for r in player.relics:
                print_slow(f"  • {r}")
        else:
            print_slow("  You carry no relics.")
    elif command == "rest":
        do_rest(player, room)
    elif command in ["look", "l", "examine"]:
        show_room(room)
    elif command in ["help", "?"]:
        show_help()
    else:
        print(f"  Unknown command '{command}'. Type 'help' for a list of commands.")
    return room


def game_loop(player, room):
    while True:
        if player.health <= 0:
            print_slow("\n  You have died. Game over.")
            break

        show_room(room)
        print_status(player)

        if get_alive_enemies(room):
            input("\n  Press Enter to continue...")
            show_combat_enter([e.name for e in get_alive_enemies(room)])
            combat_loop(player, room)
            continue

        raw = input("\n> ").lower().strip()
        if not raw:
            continue
        if raw in ["quit", "exit"]:
            print_slow("\n  Thanks for playing! Goodbye!")
            break

        command, args = parse_command(raw)
        room = handle_command(command, args, player, room)


def main():
    show_intro()
    name = input("\nEnter your character's name: ")
    player = Player(name)
    starting_room = setup_rooms()
    GameEngine(player)
    print(f"\nWelcome, {player.name}! Your adventure begins...\n")
    game_loop(player, starting_room)


if __name__ == "__main__":
    main()