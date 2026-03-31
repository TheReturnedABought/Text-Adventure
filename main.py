# main.py
import os
import sys

BASE_PATH = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))


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

from entities.player        import Player
from entities.class_data    import CLASS_RELIC_NAMES
from rooms.map_data         import setup_rooms
from rooms.room             import Room
from game_engine.engine     import GameEngine
from game_engine.parser     import parse_command
from game_engine.game_state import GameState, GameMode
from game_engine.save_manager import SaveManager
from utils.helpers  import print_slow, print_status, RARITY_COLORS, RESET
from utils.display  import (
    show_intro, show_room, show_help, show_combat_enter,
    show_class_selection, show_relics, show_map, show_journal,
)
from utils.actions  import (
    do_move, do_take_relic, do_drop, do_inventory,
    do_listen, do_examine, do_solve,
    do_interact, use_item,
)
from utils.combat   import combat_loop
from utils.relics   import get_relic
from utils.window   import window


# ══════════════════════════════════════════════════════════════════════════════
#  CommandRouter
# ══════════════════════════════════════════════════════════════════════════════

class CommandRouter:
    def __init__(self, game: "Game"):
        self._game  = game
        self._table: dict = {}
        self._build()

    def _build(self):
        g = self._game
        t = self._table

        for alias in ("move", "go", "walk"):
            t[alias] = lambda g, a: g._travel(a)
        for d in ("north", "south", "east", "west", "up", "down"):
            t[d] = lambda g, a, _d=d: g._travel([_d])

        for alias in ("take", "pick", "grab", "get"):
            t[alias] = lambda g, a: do_take_relic(g.player, g.room, a)
        t["drop"]                     = lambda g, a: do_drop(g.player, g.room, a)
        t["inventory"] = t["inv"]     = lambda g, a: do_inventory(g.player)
        t["relics"]    = t["relic"]   = lambda g, a: show_relics(g.player)
        t["use"]                      = lambda g, a: use_item(g.player, g.room, a)
        t["listen"]   = t["hear"]     = lambda g, a: do_listen(g.player, g.room)
        t["interact"] = t["talk"]     = lambda g, a: do_interact(g.player, g.room)
        t["examine"]  = t["inspect"]  = lambda g, a: do_examine(g.player, g.room, a)
        t["solve"]                    = lambda g, a: do_solve(g.player, g.room, a)
        t["look"]     = t["l"]        = lambda g, a: show_room(g.room)
        t["help"]     = t["?"]        = lambda g, a: (
            show_help(g.player), input("  Press Enter to continue...")
        )
        t["map"]                      = lambda g, a: show_map(g.start_room, g.room)
        t["journal"]                  = lambda g, a: show_journal(g.player)

    def dispatch(self, command: str, args: list) -> bool:
        handler = self._table.get(command)
        if handler:
            result = handler(self._game, args)
            if isinstance(result, Room):
                self._game.state.room = result
            return True
        else:
            print_slow(
                f"  Unknown command '{command}'. Type 'help' for a list of commands."
            )
            return False


# ══════════════════════════════════════════════════════════════════════════════
#  Game
# ══════════════════════════════════════════════════════════════════════════════

class Game:
    def __init__(self):
        self.state:    "GameState | None" = None
        self.router:   "CommandRouter | None" = None
        self.save_mgr: SaveManager = SaveManager()
        self._show_room_on_next_turn = True

    @property
    def player(self) -> Player:
        return self.state.player

    @property
    def room(self) -> Room:
        return self.state.room

    @room.setter
    def room(self, value: Room):
        """Setter keeps save_manager.apply() working without changes."""
        self.state.room = value

    @property
    def start_room(self) -> Room:
        return self.state.start_room

    def main(self):
        self.setup()
        if self.state and self.state.player:
            self.run()

    # ── Setup ─────────────────────────────────────────────────────────────────

    def setup(self):
        show_intro()

        saved = self.save_mgr.load()
        if saved:
            print_slow("\n  A save was found:")
            print_slow(f"    {self.save_mgr.summary(saved)}")
            print()
            while True:
                choice = input("  [1] Continue  [2] New game: ").strip()
                if choice == "1":
                    self._load_game(saved)
                    return
                if choice == "2":
                    self.save_mgr.delete()
                    break
                print("  Please enter 1 or 2.")

        self._new_game()

    def _new_game(self):
        name       = input("\nEnter your character's name: ").strip() or "Hero"
        char_class = show_class_selection()
        player     = Player(name, char_class)

        self._give_starter_relic(player, char_class)

        start_room = setup_rooms()
        self.state  = GameState(
            player=player, room=start_room, start_room=start_room,
        )
        self.router = CommandRouter(self)
        self._wire_engine()

        self.state.room.visit_count += 1
        self.state.room.on_enter(player)

        print(f"\nWelcome, {player.name} the {char_class.capitalize()}!"
              " Your adventure begins...\n")

        window.set_explore(player, self.state.room)

    def _load_game(self, saved: dict):
        name       = saved["player"]["name"]
        char_class = saved["player"]["char_class"]
        player     = Player(name, char_class)
        start_room = setup_rooms()

        self.state  = GameState(
            player=player, room=start_room, start_room=start_room,
        )
        self.router = CommandRouter(self)
        self._wire_engine()
        self.save_mgr.apply(self, saved)

        print_slow(f"\n  Welcome back, {player.name}!")
        print_slow(f"  You are in: {self.room.name}\n")

        window.set_explore(player, self.room)

    def _wire_engine(self):
        engine            = GameEngine(self.player)
        engine.start_room = self.start_room
        self._engine      = engine

    @staticmethod
    def _give_starter_relic(player: Player, char_class: str):
        starter = get_relic(CLASS_RELIC_NAMES[char_class])
        if not starter:
            return
        player.add_relic(starter)
        color  = RARITY_COLORS.get(getattr(starter, "rarity", "Common"), "")
        rarity = getattr(starter, "rarity", "Common")
        print()
        print_slow(f"  ✦ Starting relic: {color}{starter.name}{RESET}  [{rarity}]")
        print_slow(f"    {starter.description}")
        input("\n  Press Enter to begin your adventure...")

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self):
        while self.state.running:
            if not self.player.is_alive():
                self._handle_death()
                break

            if self.room.has_enemies:
                self._run_combat()
                if not self.player.is_alive():
                    continue
            else:
                self._run_explore_turn()

    def _run_combat(self):
        self.state.start_combat()
        window.set_combat(self.player, self.room, self.room.alive_enemies)

        input("\n  Press Enter to continue...")
        show_combat_enter([e.name for e in self.room.alive_enemies])
        combat_loop(self.player, self.room)

        self.state.end_combat()
        window.set_explore(self.player, self.room)
        self._autosave()

    def _run_explore_turn(self):
        window.set_explore(self.player, self.room)
        if self._show_room_on_next_turn:
            self._show_room_on_next_turn = False
            show_room(self.room)
        else:
            if self.room.ambient:
                print()
                print_slow(f"  {self.room.ambient_line()}")

        raw = input("\n> ").lower().strip()
        if not raw:
            return
        if raw in ("quit", "exit"):
            print_slow("\n  Thanks for playing! Goodbye!")
            self._autosave()
            self.state.running = False
            return

        command, args = parse_command(raw)
        handled = self.router.dispatch(command, args)
        if not handled:
            return

    def _handle_death(self):
        print_slow("\n  You have died. Game over.")
        self.save_mgr.delete()
        self.state.game_over()

    def _travel(self, args: list) -> Room:
        new_room = do_move(self.player, self.room, args)
        if new_room is not self.room:
            new_room.visit_count += 1
            if new_room.visit_count == 1:
                new_room.on_enter(self.player)
            self.state.enter_room(new_room)
            self._show_room_on_next_turn = True
            window.set_explore(self.player, new_room)
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
    window.run_game(game.main)


if __name__ == "__main__":
    main()
