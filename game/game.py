from __future__ import annotations

import json
from enum import Enum, auto
from pathlib import Path
from types import SimpleNamespace

from game.commands import CommandRegistry, UnlockTable
from game.combat import CombatController, CombatOutcome
from game.exploration import ExplorationController
from game.loader import AssetLoader
from game.parser import CommandParser
from game.entities import Player, Enemy
from game.world import WorldMap
from game.window import window


class GameState(Enum):
    EXPLORING = auto()
    COMBAT = auto()
    LEVEL_UP = auto()    # paused waiting for player to choose unlock
    GAME_OVER = auto()
    WIN = auto()


class TextAdventureGame:
    """Top-level orchestrator. Owns all subsystems and the main run loop."""

    ASSETS_ROOT = Path("assets")

    def __init__(self) -> None:
        self.loader = AssetLoader(self.ASSETS_ROOT)
        self.registry = CommandRegistry()
        self.unlock_table = UnlockTable()
        self.parser: CommandParser | None = None

        self.item_catalog: dict = {}
        self.enemy_templates: dict = {}
        self.class_catalog: dict = {}
        self.world: WorldMap | None = None
        self.player: Player | None = None

        self.exploration: ExplorationController | None = None
        self.combat: CombatController | None = None

        self.state: GameState = GameState.EXPLORING
        self._pending_level_up_choices: list[list[str]] = []

        # Lightweight fallback runtime state for partially implemented subsystems.
        self._rooms_raw: dict[str, dict] = {}
        self._room_id: str | None = None
        self._prev_room_id: str | None = None

    def initialise(self) -> None:
        self._load_assets()
        self._build_subsystems()

    def _load_assets(self) -> None:
        """Load JSON assets directly as a robust fallback."""
        def _load_folder(folder: str) -> dict[str, dict]:
            data: dict[str, dict] = {}
            base = self.ASSETS_ROOT / folder
            if not base.exists():
                return data
            for path in sorted(base.glob("*.json")):
                if path.name.startswith("_"):
                    continue
                obj = json.loads(path.read_text(encoding="utf-8"))
                obj_id = obj.get("id", path.stem)
                data[obj_id] = obj
            return data

        self.item_catalog = _load_folder("items")
        self.enemy_templates = _load_folder("enemies")
        self.class_catalog = _load_folder("classes")
        self._rooms_raw = _load_folder("rooms")

        # best-effort registry load; ignore while commands module is scaffolded
        cmd_file = self.ASSETS_ROOT / "commands" / "commands.json"
        if cmd_file.exists():
            try:
                self.registry.load_from_dict(json.loads(cmd_file.read_text(encoding="utf-8")))
            except Exception:
                pass

        # determine start room
        starts = [rid for rid, r in self._rooms_raw.items() if r.get("is_start")]
        self._room_id = starts[0] if starts else (next(iter(self._rooms_raw), None))

    def _build_subsystems(self) -> None:
        """Construct parser/controller objects when possible."""
        try:
            self.parser = CommandParser(self.registry)
        except Exception:
            self.parser = None

        # world/controller classes are still scaffolded; retain None when unavailable
        self.world = None
        self.exploration = None

    def select_class(self) -> None:
        classes = list(self.class_catalog.values())
        if not classes:
            raise RuntimeError("No class definitions found in assets/classes.")

        print("Choose a class:")
        for i, c in enumerate(classes, start=1):
            print(f"  {i}. {c.get('name', c.get('id', f'class-{i}'))}")
            desc = c.get("description")
            if desc:
                print(f"     {desc}")

        selected = classes[0]
        while True:
            raw = input("Class number > ").strip()
            if not raw:
                break
            if raw.isdigit() and 1 <= int(raw) <= len(classes):
                selected = classes[int(raw) - 1]
                break
            print("Invalid choice. Enter a number from the list.")

        self.player = self._build_player(selected.get("id", "adventurer"))
        print(f"You are now a {getattr(self.player, 'char_class_name', 'Adventurer')}.")

    def _build_player(self, class_id: str) -> Player:
        class_data = self.class_catalog.get(class_id, {})
        base = class_data.get("base_stats", {})
        hp = int(base.get("hp", 30))
        atk = int(base.get("attack", 5))
        defense = int(base.get("defense", 1))
        ap = int(base.get("ap", 20))

        # Player methods are scaffolded, but raw fields are usable.
        player = Player(name="Hero", max_hp=hp, attack=atk, defense=defense, total_ap=ap)
        player.current_hp = hp
        player.current_ap = ap
        player.unlocked_commands = set(class_data.get("level_unlocks", {}).get("1", []))
        setattr(player, "char_class_name", class_data.get("name", class_id))
        setattr(player, "max_mana", int(base.get("mana", 0)))
        setattr(player, "mana", int(base.get("mana", 0)))
        setattr(player, "gold", 0)
        setattr(player, "relics", [])
        return player

    def run(self) -> None:
        # all output/input is routed through GameWindow by design
        window.run_game(self._run_loop)

    def _run_loop(self) -> None:
        self.initialise()
        self.select_class()
        self._print_room()

        while self.state not in (GameState.GAME_OVER, GameState.WIN):
            try:
                raw = input(self._prompt())
            except (EOFError, KeyboardInterrupt):
                break

            if self.state == GameState.EXPLORING:
                self._handle_exploration(raw)
            elif self.state == GameState.COMBAT:
                self._handle_combat(raw)
            elif self.state == GameState.LEVEL_UP:
                self._handle_level_up_choice(raw)

        self._print_end_screen()

    def _prompt(self) -> str:
        if self.state == GameState.COMBAT:
            return "combat> "
        if self.state == GameState.LEVEL_UP:
            return "level-up> "
        return "explore> "

    def _handle_exploration(self, raw: str) -> None:
        cmd = raw.strip().lower()
        if not cmd:
            return

        if cmd in {"quit", "exit"}:
            self.state = GameState.GAME_OVER
            return
        if cmd in {"look", "l"}:
            self._print_room()
            return
        if cmd == "help":
            print("Commands: look, go <direction>, where, win, quit")
            return
        if cmd == "where":
            print(f"Current room: {self._room_id}")
            return
        if cmd in {"win", "victory"}:
            self.state = GameState.WIN
            return

        if cmd.startswith("go "):
            direction = cmd[3:].strip()
            room = self._rooms_raw.get(self._room_id or "", {})
            exits = room.get("exits", {})
            next_room = exits.get(direction)
            if not next_room:
                print("You cannot go that way.")
                return
            self._prev_room_id = self._room_id
            self._room_id = next_room
            self._print_room()
            return

        print("Unknown command. Type 'help'.")

    def _handle_combat(self, raw: str) -> None:
        if raw.strip().lower() in {"flee", "run"}:
            self._on_combat_fled()
            return
        print("Combat scaffolding is not yet implemented; type 'flee' to leave combat.")

    def _handle_level_up_choice(self, raw: str) -> None:
        if not self._pending_level_up_choices:
            self.state = GameState.EXPLORING
            return
        options = self._pending_level_up_choices[0]
        if raw.strip().isdigit() and 1 <= int(raw.strip()) <= len(options):
            choice = options[int(raw.strip()) - 1]
            if self.player is not None:
                self.player.unlocked_commands.add(choice)
            print(f"Unlocked: {choice}")
            self._pending_level_up_choices.pop(0)
        else:
            for i, opt in enumerate(options, start=1):
                print(f"  {i}. {opt}")
            print("Choose by number.")
        if not self._pending_level_up_choices:
            self.state = GameState.EXPLORING

    def _enter_combat(self, aggressors: list[Enemy]) -> None:
        self.state = GameState.COMBAT
        names = ", ".join(getattr(a, "name", "enemy") for a in aggressors) or "enemies"
        print(f"Combat started against {names}.")

    def _exit_combat(self) -> None:
        self.combat = None
        self.state = GameState.EXPLORING

    def _on_combat_won(self) -> None:
        print("You won the encounter.")
        self._exit_combat()

    def _on_combat_fled(self) -> None:
        if self._prev_room_id:
            self._room_id, self._prev_room_id = self._prev_room_id, self._room_id
        print("You fled combat.")
        self._exit_combat()

    def _on_level_up(self, new_level: int) -> None:
        class_id = (self.class_catalog.get(getattr(self.player, "char_class_name", ""), {})
                    .get("id", ""))
        _ = class_id, new_level
        self.state = GameState.LEVEL_UP if self._pending_level_up_choices else self.state

    def _print_room(self) -> None:
        room = self._rooms_raw.get(self._room_id or "")
        if not room:
            print("No room loaded.")
            return
        print(f"\n== {room.get('name', self._room_id)} ==")
        print(room.get("description", ""))
        exits = room.get("exits", {})
        if exits:
            print("Exits:", ", ".join(exits.keys()))

        # keep window panels in sync
        if self.player is not None:
            dummy_room = SimpleNamespace(
                name=room.get("name", self._room_id),
                description=room.get("description", ""),
                enemies=[], relics=[], items=[], connections=exits,
                locked_connections=set(), event=None, puzzle=None,
            )
            window.set_explore(self.player, dummy_room)

    def _print_end_screen(self) -> None:
        if self.state == GameState.WIN:
            print("\n*** VICTORY ***")
        else:
            print("\n*** GAME OVER ***")

    def save(self, slot: int = 0) -> None:
        save_dir = Path("saves")
        save_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "player": self._serialise_player(),
            "room_id": self._room_id,
            "state": self.state.name,
            "moves": self.world.moves
        }
        (save_dir / f"slot_{slot}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"Saved to slot {slot}.")

    def load(self, slot: int = 0) -> None:
        path = Path("saves") / f"slot_{slot}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        self.player = self._deserialise_player(data.get("player", {}))
        self._room_id = data.get("room_id", self._room_id)
        self.state = GameState[data.get("state", "EXPLORING")]
        self.world.moves = data.get("moves", self.world.moves)

    def _serialise_player(self) -> dict:
        if self.player is None:
            return {}
        return {
            "name": self.player.name,
            "max_hp": self.player.max_hp,
            "attack": self.player.attack,
            "defense": self.player.defense,
            "current_hp": self.player.current_hp,
            "total_ap": self.player.total_ap,
            "current_ap": self.player.current_ap,
            "level": self.player.level,
            "xp": self.player.xp,
            "unlocked_commands": sorted(self.player.unlocked_commands),
            "char_class_name": getattr(self.player, "char_class_name", "Adventurer"),
        }

    def _deserialise_player(self, data: dict) -> Player:
        p = Player(
            name=data.get("name", "Hero"),
            max_hp=int(data.get("max_hp", 30)),
            attack=int(data.get("attack", 5)),
            defense=int(data.get("defense", 1)),
            total_ap=int(data.get("total_ap", 20)),
        )
        p.current_hp = int(data.get("current_hp", p.max_hp))
        p.current_ap = int(data.get("current_ap", p.total_ap))
        p.level = int(data.get("level", 1))
        p.xp = int(data.get("xp", 0))
        p.unlocked_commands = set(data.get("unlocked_commands", []))
        setattr(p, "char_class_name", data.get("char_class_name", "Adventurer"))
        return p
