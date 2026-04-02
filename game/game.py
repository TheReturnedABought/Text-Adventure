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
    LEVEL_UP = auto()
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
        """Load JSON assets recursively from subfolders."""

        def _load_folder(folder_name: str) -> dict[str, dict]:
            data: dict[str, dict] = {}
            base = self.ASSETS_ROOT / folder_name
            if not base.exists():
                return data
            for path in sorted(base.rglob("*.json")):
                if path.name.startswith("_"):
                    continue
                obj = json.loads(path.read_text(encoding="utf-8"))
                obj_id = obj.get("id", path.stem)
                data[obj_id] = obj
            return data

        self.item_catalog = self.loader.load_all_items()
        self.enemy_templates = self.loader.load_all_enemy_templates()
        self.class_catalog = self.loader.load_all_classes()
        self._rooms_raw = _load_folder("rooms")

        # best-effort registry load
        cmd_file = self.ASSETS_ROOT / "commands" / "commands.json"
        if cmd_file.exists():
            try:
                self.registry.load_from_dict(json.loads(cmd_file.read_text(encoding="utf-8")))
            except Exception:
                pass

        # determine start room from raw rooms (fallback, but world map will override later)
        starts = [rid for rid, r in self._rooms_raw.items() if r.get("is_start")]
        self._room_id = starts[0] if starts else (next(iter(self._rooms_raw), None))

    def _build_subsystems(self) -> None:
        """Construct parser and world map from loaded assets."""
        try:
            self.parser = CommandParser(self.registry)
        except Exception as e:
            print(f"Warning: Could not create parser: {e}")
            self.parser = None

        # Build world map using enemy templates if available
        if self.enemy_templates and self.parser:
            try:
                self.world = self.loader.build_world_map(self.enemy_templates)
            except Exception as e:
                print(f"Warning: Could not build world map from templates: {e}")
                self.world = None

        # Fallback: create a world from raw rooms if the above failed
        if self.world is None and self._rooms_raw:
            from game.world import WorldMap, Room, Material
            self.world = WorldMap()
            for room_id, room_data in self._rooms_raw.items():
                material = Material(room_data.get("material", "stone"))
                room = Room(
                    id=room_id,
                    name=room_data.get("name", room_id),
                    description=room_data.get("description", ""),
                    material=material,
                    is_outdoor=room_data.get("is_outdoor", False),
                    light_level=room_data.get("light_level", 10),
                    exits=room_data.get("exits", {}),
                    line_of_sight=room_data.get("line_of_sight", []),
                    ambient=room_data.get("ambient", ""),
                    is_start=room_data.get("is_start", False),
                )
                self.world.add_room(room)
            if self.world.start_room_id:
                self.world.current_room_id = self.world.start_room_id
            else:
                # fallback to first room
                self.world.current_room_id = next(iter(self._rooms_raw.keys()), None)

        self.exploration = None
        self.combat = None

    def select_class(self) -> None:
        classes = list(self.class_catalog.values())
        if not classes:
            raise RuntimeError("No class definitions found in assets/classes.")

        print("Choose a class:")
        for i, c in enumerate(classes, start=1):
            # FIX: c is a CharacterClass object, not a dict
            print(f"  {i}. {c.name}")
            if c.description:
                print(f"     {c.description}")

        selected = classes[0]
        while True:
            raw = input("Class number > ").strip()
            if not raw:
                break
            if raw.isdigit() and 1 <= int(raw) <= len(classes):
                selected = classes[int(raw) - 1]
                break
            print("Invalid choice. Enter a number from the list.")

        self.player = self._build_player(selected.id)
        print(f"You are now a {self.player.char_class_name}.")

    def _build_player(self, class_id: str) -> Player:
        char_class = self.class_catalog.get(class_id)
        if char_class is None:
            raise ValueError(f"Unknown class: {class_id}")

        base = char_class.base_stats
        hp = int(base.get("hp", 30))
        atk = int(base.get("attack", 5))
        defense = int(base.get("defense", 1))
        ap = int(base.get("ap", 20))
        mana = int(base.get("mana", 0))

        player = Player(name="Hero", max_hp=hp, attack=atk, defense=defense, total_ap=ap, max_mana=mana, mana=mana)
        player.current_hp = hp
        player.current_ap = ap
        player.char_class = char_class
        player.unlocked_commands = set(char_class.level_unlocks.get(1, []))
        setattr(player, "char_class_name", char_class.name)
        setattr(player, "gold", 0)
        setattr(player, "relics", [])

        for item_id in char_class.starting_items:
            if item_id in self.item_catalog:
                player.inventory.append(self.item_catalog[item_id])

        return player

    def run(self) -> None:
        window.run_game(self._run_loop)

    def _run_loop(self) -> None:
        self.initialise()
        self.select_class()

        # Set up exploration controller if world and parser are ready
        if self.world and self.parser:
            self.exploration = ExplorationController(
                self.parser, self.registry, self.player, self.world,
                puzzle_flags={}, item_catalog=self.item_catalog
            )
            # Set initial room
            start_room = self.world.current_room()
            if start_room:
                start_room.visited = True
                window.set_explore(self.player, start_room)
                print(start_room.get_description(verbose=True))
        else:
            # Fallback to minimal world
            self._print_room()

        while self.state not in (GameState.GAME_OVER, GameState.WIN):
            try:
                raw = input(self._prompt())
            except (EOFError, KeyboardInterrupt):
                break

            if self.state == GameState.EXPLORING:
                if not self.exploration:
                    self._handle_exploration_fallback(raw)
                else:
                    result = self.exploration.player_input(raw)
                    for line in result.lines:
                        print(line)
                    if result.combat_triggered:
                        self._enter_combat(result.aggressors)
            elif self.state == GameState.COMBAT:
                if not self.combat:
                    if raw.strip().lower() in {"flee", "run"}:
                        self._on_combat_fled()
                    else:
                        print("Combat scaffolding is not yet implemented; type 'flee' to leave combat.")
                else:
                    result = self.combat.player_input(raw)
                    for line in result.lines:
                        print(line)
                    if result.outcome == CombatOutcome.PLAYER_WON:
                        self._on_combat_won()
                    elif result.outcome == CombatOutcome.PLAYER_FLED:
                        self._on_combat_fled()
                    elif result.outcome == CombatOutcome.PLAYER_DEFEATED:
                        self.state = GameState.GAME_OVER
            elif self.state == GameState.LEVEL_UP:
                self._handle_level_up_choice(raw)

        self._print_end_screen()

    def _handle_exploration_fallback(self, raw: str) -> None:
        """Minimal fallback when exploration controller isn't available."""
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

    def _enter_combat(self, aggressors: list[Enemy]) -> None:
        if not self.world or not self.parser:
            print("Combat system not available.")
            return
        # Keep enemies in their current rooms
        for enemy in aggressors:
            room_id = getattr(enemy, "combat_room_id", self.world.current_room_id)
            room = self.world.get_room(room_id)
            if room and enemy not in room.enemies:
                room.add_enemy(enemy)

        self.combat = CombatController(
            self.parser, self.registry, self.player, aggressors,
            self.world, self.world.current_room_id, self.exploration.puzzle_flags if self.exploration else {}
        )
        print(self.combat.start_encounter())
        self.state = GameState.COMBAT

    def _on_combat_won(self) -> None:
        print("You won the encounter.")

        # Award XP and handle level‑up choices
        total_xp = sum(e.xp_reward for e in self.combat.enemies if not e.is_alive)
        lines, choice_groups = self.player.gain_xp(total_xp)
        for line in lines:
            print(line)
        if choice_groups:
            self._pending_level_up_choices = choice_groups
            self.state = GameState.LEVEL_UP
            print("You have new abilities to choose from! (type number)")
            self._print_choices()
        else:
            self.combat = None
            self.state = GameState.EXPLORING
            if self.world and self.exploration:
                self.exploration.world = self.world

    def _on_combat_fled(self) -> None:
        if self._prev_room_id:
            self._room_id, self._prev_room_id = self._prev_room_id, self._room_id
        print("You fled combat.")
        self.combat = None
        self.state = GameState.EXPLORING

    def _prompt(self) -> str:
        if self.state == GameState.COMBAT:
            return "combat> "
        if self.state == GameState.LEVEL_UP:
            return "level-up> "
        return "explore> "

    def _print_choices(self) -> None:
        if not self._pending_level_up_choices:
            return
        for group in self._pending_level_up_choices:
            print("Choose one of:")
            for i, opt in enumerate(group, start=1):
                print(f"  {i}. {opt}")

    def _handle_level_up_choice(self, raw: str) -> None:
        if not self._pending_level_up_choices:
            self.state = GameState.EXPLORING
            return
        # Current group is the first one
        group = self._pending_level_up_choices[0]
        if raw.strip().isdigit() and 1 <= int(raw.strip()) <= len(group):
            choice = group[int(raw.strip()) - 1]
            if self.player is not None:
                self.player.unlock_command(choice)
            print(f"Unlocked: {choice}")
            self._pending_level_up_choices.pop(0)
        else:
            print("Invalid choice. Enter a number from the list.")
            for i, opt in enumerate(group, start=1):
                print(f"  {i}. {opt}")
            return
        # If there are more groups, continue level‑up state; else back to exploring
        if self._pending_level_up_choices:
            self._print_choices()
        else:
            self.state = GameState.EXPLORING
            print("Level‑up complete. You continue your journey.")

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
        }
        if self.world:
            payload["world"] = self.world.snapshot()
        (save_dir / f"slot_{slot}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"Saved to slot {slot}.")

    def load(self, slot: int = 0) -> None:
        path = Path("saves") / f"slot_{slot}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        self.player = self._deserialise_player(data.get("player", {}))
        self._room_id = data.get("room_id", self._room_id)
        self.state = GameState[data.get("state", "EXPLORING")]
        if self.world and "world" in data:
            self.world.restore_snapshot(data["world"])
        if self.exploration:
            self.exploration.player = self.player
            self.exploration.world = self.world

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
            "max_mana": self.player.max_mana,
            "mana": self.player.mana,
            "level": self.player.level,
            "xp": self.player.xp,
            "unlocked_commands": sorted(self.player.unlocked_commands),
            "char_class_name": getattr(self.player, "char_class_name", "Adventurer"),
            "inventory": [item.id for item in self.player.inventory],
            "equipped": {slot: item.id for slot, item in self.player.equipped.items()},
        }

    def _deserialise_player(self, data: dict) -> Player:
        p = Player(
            name=data.get("name", "Hero"),
            max_hp=int(data.get("max_hp", 30)),
            attack=int(data.get("attack", 5)),
            defense=int(data.get("defense", 1)),
            total_ap=int(data.get("total_ap", 20)),
            max_mana=int(data.get("max_mana", 0)),
            mana=int(data.get("mana", 0)),
        )
        p.current_hp = int(data.get("current_hp", p.max_hp))
        p.current_ap = int(data.get("current_ap", p.total_ap))
        p.level = int(data.get("level", 1))
        p.xp = int(data.get("xp", 0))
        p.unlocked_commands = set(data.get("unlocked_commands", []))
        setattr(p, "char_class_name", data.get("char_class_name", "Adventurer"))

        # Restore inventory
        for item_id in data.get("inventory", []):
            if item_id in self.item_catalog:
                p.inventory.append(self.item_catalog[item_id])

        # Restore equipped
        for slot, item_id in data.get("equipped", {}).items():
            if item_id in self.item_catalog:
                p.equipped[slot] = self.item_catalog[item_id]

        return p