from __future__ import annotations

import json
import random
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

    def __init__(self, debug: bool = False) -> None:
        self.debug = debug
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
        self.world_flags: dict[str, bool] = {}

    def _debug(self, msg: str) -> None:
        if self.debug:
            print(f"[DEBUG] {msg}")

    def initialise(self) -> None:
        self._debug("initialise()")
        self._load_assets()
        self._build_subsystems()

    def _load_assets(self) -> None:
        self._debug("_load_assets()")
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
        world_flags_file = self.ASSETS_ROOT / "world_states.json"
        if world_flags_file.exists():
            self.world_flags = json.loads(world_flags_file.read_text(encoding="utf-8")).get("flags", {})
        else:
            self.world_flags = {}

        cmd_file = self.ASSETS_ROOT / "commands" / "commands.json"
        if cmd_file.exists():
            try:
                self.registry.load_from_dict(json.loads(cmd_file.read_text(encoding="utf-8")))
            except Exception as e:
                window.append_log(f"ERROR loading commands: {e}")

        starts = [rid for rid, r in self._rooms_raw.items() if r.get("is_start")]
        self._room_id = starts[0] if starts else (next(iter(self._rooms_raw), None))

    def _build_subsystems(self) -> None:
        self._debug("_build_subsystems()")
        try:
            self.parser = CommandParser(self.registry)
        except Exception as e:
            window.append_log(f"Warning: Could not create parser: {e}")
            self.parser = None

        # Always try to build world from asset loader if rooms exist
        if self._rooms_raw and self.parser:
            try:
                # Load all rooms properly using the loader's world builder
                self.world = self.loader.build_world_map(self.enemy_templates)
                self.world.global_flags = dict(self.world_flags)
                window.append_log(f"[DEBUG] Built world with {len(self.world.rooms)} rooms using asset loader")
            except Exception as e:
                window.append_log(f"Warning: Could not build world map from loader: {e}")
                self.world = None

        # Fallback: build a minimal world from raw JSON (no objects)
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
                # Note: objects are NOT loaded in fallback – this is why you saw empty objects
                self.world.add_room(room)
                window.append_log(f"[DEBUG] Fallback room added: {room_id} (no objects)")
            if self.world.start_room_id:
                self.world.current_room_id = self.world.start_room_id
            else:
                self.world.current_room_id = next(iter(self._rooms_raw.keys()), None)
            self.world.global_flags = dict(self.world_flags)

        self.exploration = None
        self.combat = None

    def select_class(self) -> None:
        self._debug("select_class()")
        classes = list(self.class_catalog.values())
        if not classes:
            raise RuntimeError("No class definitions found in assets/classes.")

        window.append_log("Choose a class:")
        for i, c in enumerate(classes, start=1):
            window.append_log(f"  {i}. {c.name}")
            if c.description:
                window.append_log(f"     {c.description}")

        selected = classes[0]
        while True:
            raw = window.get_input("Class number > ").strip()
            if not raw:
                break
            if raw.isdigit() and 1 <= int(raw) <= len(classes):
                selected = classes[int(raw) - 1]
                break
            window.append_log("Invalid choice. Enter a number from the list.")

        self.player = self._build_player(selected.id)

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
        self._debug("run()")
        window.run_game(self._run_loop)

    def _run_loop(self) -> None:
        self._debug("_run_loop()")
        self.initialise()
        self.select_class()

        if self.world and self.parser:
            self.exploration = ExplorationController(
                self.parser, self.registry, self.player, self.world,
                puzzle_flags=dict(self.world.global_flags), item_catalog=self.item_catalog
            )
            start_room = self.world.current_room()
            if start_room:
                start_room.visited = True
                window.set_explore(self.player, start_room)
                window.append_log(start_room.get_description(verbose=True))
        else:
            self._print_room()

        while self.state not in (GameState.GAME_OVER, GameState.WIN):
            try:
                raw = window.get_input(self._prompt())
            except (EOFError, KeyboardInterrupt):
                break

            if self.state == GameState.EXPLORING:
                if not self.exploration:
                    self._handle_exploration_fallback(raw)
                else:
                    result = self.exploration.player_input(raw)
                    for line in result.lines:
                        window.append_log(line)
                    if result.combat_triggered:
                        self._enter_combat(result.aggressors)

                    if self.world and self.player:
                        current_room = self.world.current_room()
                        if current_room:
                            if self.state == GameState.COMBAT and self.combat:
                                window.set_combat(self.player, current_room, self.combat.enemies)
                            else:
                                window.set_explore(self.player, current_room)
            elif self.state == GameState.COMBAT:
                if not self.combat:
                    if raw.strip().lower() in {"flee", "run"}:
                        self._on_combat_fled()
                    else:
                        window.append_log("Combat scaffolding is not yet implemented; type 'flee' to leave combat.")
                else:
                    result = self.combat.player_input(raw)
                    for line in result.lines:
                        window.append_log(line)

                    if self.world and self.player and self.combat:
                        current_room = self.world.current_room()
                        if current_room:
                            window.set_combat(self.player, current_room, self.combat.enemies)

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
        self._debug("_handle_exploration_fallback()")
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
            window.append_log("Commands: look, go <direction>, where, win, quit")
            return
        if cmd == "where":
            window.append_log(f"Current room: {self._room_id}")
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
                window.append_log("You cannot go that way.")
                return
            self._prev_room_id = self._room_id
            self._room_id = next_room
            self._print_room()
            return
        window.append_log("Unknown command. Type 'help'.")

    def _enter_combat(self, aggressors: list[Enemy]) -> None:
        self._debug("_enter_combat()")
        if not self.world or not self.parser:
            window.append_log("Combat system not available.")
            return
        for enemy in aggressors:
            room_id = getattr(enemy, "combat_room_id", self.world.current_room_id)
            room = self.world.get_room(room_id)
            if room and enemy not in room.enemies:
                room.add_enemy(enemy)

        self.combat = CombatController(
            self.parser, self.registry, self.player, aggressors,
            self.world, self.world.current_room_id, self.exploration.puzzle_flags if self.exploration else {},
            debug=self.debug
        )
        window.append_log(self.combat.start_encounter())
        self.state = GameState.COMBAT

        current_room = self.world.current_room()
        if current_room:
            window.set_combat(self.player, current_room, self.combat.enemies)

    def _on_combat_won(self) -> None:
        self._debug("_on_combat_won()")
        window.append_log("You won the encounter.")

        total_xp = sum(e.xp_reward for e in self.combat.enemies if not e.is_alive)
        lines, choice_groups = self.player.gain_xp(total_xp)
        for line in lines:
            window.append_log(line)
        if choice_groups:
            self._pending_level_up_choices = choice_groups
            self.state = GameState.LEVEL_UP
            window.append_log("You have new abilities to choose from! (type number)")
            self._print_choices()
        else:
            self.combat = None
            self.state = GameState.EXPLORING
            if self.world and self.exploration:
                self.exploration.world = self.world
                room = self.world.current_room()
                if room:
                    room.update_after_combat()
                    # Force refresh of the room description
                    window.set_explore(self.player, room)
                    window.append_log(room.get_description(verbose=True))

    def _on_combat_fled(self) -> None:
        self._debug("_on_combat_fled()")
        if self._prev_room_id:
            self._room_id, self._prev_room_id = self._prev_room_id, self._room_id
        window.append_log("You fled combat.")
        self.combat = None
        self.state = GameState.EXPLORING

        if self.world and self.player:
            current_room = self.world.current_room()
            if current_room:
                window.set_explore(self.player, current_room)

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
            window.append_log("Choose one of:")
            for i, opt in enumerate(group, start=1):
                window.append_log(f"  {i}. {opt}")

    def _handle_level_up_choice(self, raw: str) -> None:
        self._debug("_handle_level_up_choice()")
        if not self._pending_level_up_choices:
            self.state = GameState.EXPLORING
            return
        group = self._pending_level_up_choices[0]
        if raw.strip().isdigit() and 1 <= int(raw.strip()) <= len(group):
            choice = group[int(raw.strip()) - 1]
            if self.player is not None:
                self.player.unlock_command(choice)
            window.append_log(f"Unlocked: {choice}")
            self._pending_level_up_choices.pop(0)
        else:
            window.append_log("Invalid choice. Enter a number from the list.")
            for i, opt in enumerate(group, start=1):
                window.append_log(f"  {i}. {opt}")
            return
        if self._pending_level_up_choices:
            self._print_choices()
        else:
            self.state = GameState.EXPLORING
            window.append_log("Level‑up complete. You continue your journey.")

    def _print_room(self) -> None:
        room = self._rooms_raw.get(self._room_id or "")
        if not room:
            window.append_log("No room loaded.")
            return
        window.append_log(f"\n== {room.get('name', self._room_id)} ==")
        window.append_log(room.get("description", ""))
        exits = room.get("exits", {})

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
            window.append_log("\n*** VICTORY ***")
        else:
            window.append_log("\n*** GAME OVER ***")

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
        window.append_log(f"Saved to slot {slot}.")

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

        for item_id in data.get("inventory", []):
            if item_id in self.item_catalog:
                p.inventory.append(self.item_catalog[item_id])

        for slot, item_id in data.get("equipped", {}).items():
            if item_id in self.item_catalog:
                p.equipped[slot] = self.item_catalog[item_id]

        return p
