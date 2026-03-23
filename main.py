# main.py
import os
import sys

BASE_PATH = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))

# ── Command history (readline where available) ────────────────────────────────
def _enable_history():
    try:
        import readline
        readline.set_history_length(20)
    except ImportError:
        try:
            import pyreadline3  # noqa: F401
        except ImportError:
            pass

_enable_history()

# ── Project imports ───────────────────────────────────────────────────────────
from entities.player     import Player
from entities.class_data import CLASS_RELIC_NAMES
from rooms.map_data      import setup_rooms
from game_engine.engine  import GameEngine
from game_engine.parser  import parse_command
from game_engine.save_manager import SaveManager
from utils.helpers  import print_slow, print_status, RARITY_COLORS, RESET
from utils.display  import (
    show_intro, show_room, show_help, show_combat_enter,
    show_class_selection, show_relics, show_map, show_journal,
)
from utils.actions  import (
    do_move, do_take_relic, do_drop, do_inventory,
    do_rest, do_listen, do_examine, do_solve,
    do_interact, use_item,
)
from utils.combat   import combat_loop
from utils.relics   import get_relic
from utils.ui       import ui


# ── CommandRouter ─────────────────────────────────────────────────────────────

class CommandRouter:
    def __init__(self, game):
        self.game = game
        self._table: dict = {}
        self._build()

    def _build(self):
        g = self.game
        t = self._table

        for alias in ["move", "go", "walk"]:
            t[alias] = lambda g, a: g._travel(a)
        for d in ["north", "south", "east", "west", "up", "down"]:
            t[d] = lambda g, a, _d=d: g._travel([_d])

        for alias in ["take", "pick", "grab", "get"]:
            t[alias] = lambda g, a: do_take_relic(g.player, g.room, a)
        t["drop"]                     = lambda g, a: do_drop(g.player, g.room, a)
        t["inventory"] = t["inv"]     = lambda g, a: do_inventory(g.player)
        t["relics"]    = t["relic"]   = lambda g, a: show_relics(g.player)
        t["use"]                      = lambda g, a: use_item(g.player, g.room, a)

        t["listen"]   = t["hear"]     = lambda g, a: do_listen(g.player, g.room)
        t["interact"] = t["talk"]     = lambda g, a: do_interact(g.player, g.room)
        t["examine"]  = t["inspect"]  = lambda g, a: do_examine(g.player, g.room, a)
        t["solve"]                    = lambda g, a: do_solve(g.player, g.room, a)
        t["rest"]                     = lambda g, a: do_rest(g.player, g.room)
        t["look"]     = t["l"]        = lambda g, a: show_room(g.room)
        t["help"]     = t["?"]        = lambda g, a: (
            show_help(g.player), input("  Press Enter to continue...")
        )

        t["map"]                      = lambda g, a: show_map(g.start_room, g.room)
        t["journal"]                  = lambda g, a: show_journal(g.player)

    def dispatch(self, command, args):
        handler = self._table.get(command)
        if handler:
            result = handler(self.game, args)
            from rooms.room import Room
            if isinstance(result, Room):
                self.game.room = result
        else:
            print_slow(
                f"  Unknown command '{command}'. Type 'help' for a list of commands."
            )


# ── Game ──────────────────────────────────────────────────────────────────────

class Game:
    def __init__(self):
        self.player     = None
        self.room       = None
        self.start_room = None
        self.router     = None
        self.engine     = None
        self.save_mgr   = SaveManager()

    # ── Setup ─────────────────────────────────────────────────────────────────

    def setup(self):
        show_intro()   # shown BEFORE UI is active (classic text mode)

        saved_state = self.save_mgr.load()
        if saved_state:
            print_slow("\n  A save was found:")
            print_slow(f"    {self.save_mgr.summary(saved_state)}")
            print()
            while True:
                choice = input("  [1] Continue  [2] New game: ").strip()
                if choice == "1":
                    self._load_game(saved_state)
                    return
                if choice == "2":
                    self.save_mgr.delete()
                    break
                print("  Please enter 1 or 2.")

        name       = input("\nEnter your character's name: ").strip() or "Hero"
        char_class = show_class_selection()

        self.player = Player(name, char_class)
        self._give_starter_relic(char_class)

        self.start_room = setup_rooms()
        self.room       = self.start_room
        self.engine     = GameEngine(self.player)
        self.engine.start_room = self.start_room
        self.router     = CommandRouter(self)

        self.room.visit_count += 1
        self.room.on_enter(self.player)

        print(f"\nWelcome, {self.player.name} the {char_class.capitalize()}!"
              f" Your adventure begins...\n")

        # ── Activate the UI now that player + room exist ───────────────────
        ui.set_explore(self.player, self.room)
        ui.enable()

    def _load_game(self, state):
        name       = state["player"]["name"]
        char_class = state["player"]["char_class"]

        self.player     = Player(name, char_class)
        self.start_room = setup_rooms()
        self.engine     = GameEngine(self.player)
        self.engine.start_room = self.start_room
        self.router     = CommandRouter(self)

        self.save_mgr.apply(self, state)

        print_slow(f"\n  Welcome back, {self.player.name}!")
        print_slow(f"  You are in: {self.room.name}\n")

        # ── Activate UI after state is restored ───────────────────────────
        ui.set_explore(self.player, self.room)
        ui.enable()

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
                self.save_mgr.delete()
                break

            if self.room.has_enemies:
                # Switch to combat mode in the UI
                ui.set_combat(self.player, self.room, self.room.alive_enemies)
                input("\n  Press Enter to continue...")
                show_combat_enter([e.name for e in self.room.alive_enemies])
                combat_loop(self.player, self.room)
                if self.player.health <= 0:
                    continue
                # Back to explore mode after combat
                ui.set_explore(self.player, self.room)
                self._autosave()

            # Refresh explore state before showing the room
            ui.set_explore(self.player, self.room)
            show_room(self.room)
            print_status(self.player)

            raw = input("\n> ").lower().strip()
            if not raw:
                continue
            if raw in ["quit", "exit"]:
                print_slow("\n  Thanks for playing! Goodbye!")
                self._autosave()
                break

            command, args = parse_command(raw)
            self.router.dispatch(command, args)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _travel(self, args):
        new_room = do_move(self.player, self.room, args)
        if new_room is not self.room:
            new_room.visit_count += 1
            new_room.on_enter(self.player)
            # Update UI with the new room immediately
            ui.set_explore(self.player, new_room)
            self._autosave()
        return new_room

    def _autosave(self):
        try:
            self.save_mgr.save(self)
        except Exception:
            pass


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    game = Game()
    game.setup()
    if game.player:
        game.run()


if __name__ == "__main__":
    main()