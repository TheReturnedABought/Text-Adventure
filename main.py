# main.py
import os
import sys

BASE_PATH = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))

from entities.player import Player
from entities.class_data import CLASS_RELIC_NAMES
from rooms.map_data import setup_rooms
from game_engine.engine import GameEngine
from game_engine.parser import parse_command
from utils.helpers import print_slow, print_status, RARITY_COLORS, RESET
from utils.display import (
    show_intro, show_room, show_help, show_combat_enter,
    show_class_selection, show_relics,
)
from utils.actions import (
    do_move, do_take_relic, do_drop, do_inventory,
    do_rest, do_listen, do_examine, do_solve,
)
from utils.combat import combat_loop
from utils.relics import get_relic


# ── CommandRouter ─────────────────────────────────────────────────────────────

class CommandRouter:
    """
    Maps command strings to handler callables.

    Handlers have signature:  fn(game, args) -> None
    Movement handlers return the new Room; all others return None (game.room
    is only updated when the handler explicitly returns a Room).
    """

    def __init__(self, game):
        self.game = game
        self._table = {}
        self._build()

    def _build(self):
        g = self.game
        t = self._table

        # Movement — returns new room
        for alias in ["move", "go", "walk"]:
            t[alias] = lambda g, a: g._travel(a)
        for d in ["north", "south", "east", "west", "up", "down"]:
            t[d] = lambda g, a, _d=d: g._travel([_d])

        # Items / relics
        for alias in ["take", "pick", "grab", "get"]:
            t[alias] = lambda g, a: do_take_relic(g.player, g.room, a)
        t["drop"]                    = lambda g, a: do_drop(g.player, g.room, a)
        t["inventory"] = t["inv"]    = lambda g, a: do_inventory(g.player)
        t["relics"] = t["relic"]     = lambda g, a: show_relics(g.player)

        # Exploration
        t["listen"] = t["hear"]      = lambda g, a: do_listen(g.player, g.room)
        t["examine"] = t["inspect"]  = lambda g, a: do_examine(g.player, g.room, a)
        t["solve"]                   = lambda g, a: do_solve(g.player, g.room, a)
        t["rest"]                    = lambda g, a: do_rest(g.player, g.room)
        t["look"] = t["l"]           = lambda g, a: show_room(g.room)
        t["help"] = t["?"]           = lambda g, a: (show_help(g.player), input("  Press Enter to continue..."))

    def dispatch(self, command, args):
        handler = self._table.get(command)
        if handler:
            result = handler(self.game, args)
            # Movement handlers return a Room
            from rooms.room import Room
            if isinstance(result, Room):
                self.game.room = result
        else:
            print_slow(f"  Unknown command '{command}'. Type 'help' for a list of commands.")


# ── Game ──────────────────────────────────────────────────────────────────────

class Game:
    """
    Top-level game object. Owns player, current room, and the main loop.
    """

    def __init__(self):
        self.player = None
        self.room   = None
        self.router = None
        self.engine = None

    # ── Setup ─────────────────────────────────────────────────────────────────

    def setup(self):
        show_intro()

        name       = input("\nEnter your character's name: ").strip() or "Hero"
        char_class = show_class_selection()

        self.player = Player(name, char_class)
        self._give_starter_relic(char_class)

        self.room   = setup_rooms()
        self.engine = GameEngine(self.player)
        self.router = CommandRouter(self)

        # Fire on_enter for the starting room — player spawns here, doesn't travel in
        self.room.on_enter(self.player)

        print(f"\nWelcome, {self.player.name} the {char_class.capitalize()}!"
              f" Your adventure begins...\n")

    def _give_starter_relic(self, char_class):
        starter = get_relic(CLASS_RELIC_NAMES[char_class])
        if not starter:
            return
        self.player.add_relic(starter)
        color  = RARITY_COLORS.get(getattr(starter, "rarity", "Common"), "")
        rarity = getattr(starter, "rarity", "Common")
        print()
        print_slow(f"  ✦ Starting relic: {color}{starter.name}{RESET}  [{rarity}]")
        print_slow(f"    {starter.description}")
        input("\n  Press Enter to begin your adventure...")

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self):
        while True:
            if self.player.health <= 0:
                print_slow("\n  You have died. Game over.")
                break

            # If enemies are present, go straight to combat without showing room first.
            # on_enter already printed dialogue when we entered the room.
            if self.room.has_enemies:
                input("\n  Press Enter to continue...")
                show_combat_enter([e.name for e in self.room.alive_enemies])
                combat_loop(self.player, self.room)
                if self.player.health <= 0:
                    continue   # let the death check handle it

            # Show room — either post-combat or on peaceful entry
            show_room(self.room)
            print_status(self.player)

            raw = input("\n> ").lower().strip()
            if not raw:
                continue
            if raw in ["quit", "exit"]:
                print_slow("\n  Thanks for playing! Goodbye!")
                break

            command, args = parse_command(raw)
            self.router.dispatch(command, args)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _travel(self, args):
        """Move the player; returns the new Room (or current if blocked)."""
        new_room = do_move(self.player, self.room, args)
        if new_room is not self.room:
            new_room.on_enter(self.player)
        return new_room


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    game = Game()
    game.setup()
    game.run()


if __name__ == "__main__":
    main()