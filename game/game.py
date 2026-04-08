# game/game.py
import json
from enum import Enum, auto
from pathlib import Path

from game.commands import CommandRegistry, UnlockTable
from game.combat import CombatController, CombatOutcome
from game.exploration import ExplorationController
from game.loader import AssetLoader
from game.parser import CommandParser
from game.entities import Player, Enemy
from game.world import WorldMap
from game.window import window

class GameState(Enum):
    EXPLORING = auto(); COMBAT = auto(); LEVEL_UP = auto(); GAME_OVER = auto(); WIN = auto()

class TextAdventureGame:
    ASSETS_ROOT = Path("assets")
    def __init__(self, debug: bool = False):
        self.debug = debug
        self.loader = AssetLoader(self.ASSETS_ROOT)
        self.registry = CommandRegistry()
        self.unlock_table = UnlockTable()
        self.parser = None
        self.item_catalog = {}
        self.enemy_templates = {}
        self.class_catalog = {}
        self.world = None
        self.player = None
        self.exploration = None
        self.combat = None
        self.state = GameState.EXPLORING
        self._pending_level_up_choices = []
        self.world_flags = {}

    def initialise(self):
        self._load_assets()
        self._build_subsystems()

    def _load_assets(self):
        self.item_catalog = self.loader.load_all_items()
        self.enemy_templates = self.loader.load_all_enemy_templates()
        self.class_catalog = self.loader.load_all_classes()
        wf_path = self.ASSETS_ROOT / "world_states.json"
        if wf_path.exists():
            self.world_flags = json.loads(wf_path.read_text(encoding="utf-8")).get("flags", {})
        else: self.world_flags = {}
        cmd_path = self.ASSETS_ROOT / "commands" / "commands.json"
        if cmd_path.exists():
            try: self.registry.load_from_dict(json.loads(cmd_path.read_text(encoding="utf-8")))
            except Exception as e: window.append_log(f"ERROR loading commands: {e}")

    def _build_subsystems(self):
        try: self.parser = CommandParser(self.registry)
        except Exception as e: window.append_log(f"Warning: Could not create parser: {e}"); self.parser = None
        if self.parser:
            try:
                self.world = self.loader.build_world_map(self.enemy_templates)
                self.world.global_flags = dict(self.world_flags)
                window.append_log(f"[DEBUG] Built world with {len(self.world.rooms)} rooms using asset loader")
            except Exception as e: window.append_log(f"Warning: Could not build world map from loader: {e}"); self.world = None
        self.exploration = None; self.combat = None

    def select_class(self):
        classes = list(self.class_catalog.values())
        if not classes: raise RuntimeError("No class definitions found in assets/classes.")
        window.append_log("Choose a class:")
        for i, c in enumerate(classes,1): window.append_log(f"  {i}. {c.name}\n     {c.description}")
        selected = classes[0]
        while True:
            raw = window.get_input("Class number > ").strip()
            if not raw: break
            if raw.isdigit() and 1 <= int(raw) <= len(classes): selected = classes[int(raw)-1]; break
            window.append_log("Invalid choice. Enter a number from the list.")
        self.player = self._build_player(selected.id)

    def _build_player(self, class_id: str) -> Player:
        char_class = self.class_catalog.get(class_id)
        if char_class is None: raise ValueError(f"Unknown class: {class_id}")
        base = char_class.base_stats
        player = Player(name="Hero", max_hp=int(base.get("hp",30)), attack=int(base.get("attack",5)),
                        defense=int(base.get("defense",1)), total_ap=int(base.get("ap",20)), max_mana=int(base.get("mana",0)), mana=int(base.get("mana",0)))
        player.current_hp = player.max_hp; player.current_ap = player.total_ap
        player.char_class = char_class
        player.unlocked_commands = set(char_class.level_unlocks.get(1, []))
        setattr(player, "char_class_name", char_class.name)
        setattr(player, "gold", 0); setattr(player, "relics", [])
        for item_id in char_class.starting_items:
            if item_id in self.item_catalog: player.inventory.append(self.item_catalog[item_id])
        return player

    def run(self):
        window.run_game(self._run_loop)

    def _run_loop(self):
        self.initialise()
        self.select_class()
        if self.world and self.parser:
            self.exploration = ExplorationController(self.parser, self.registry, self.player, self.world,
                                                     puzzle_flags=dict(self.world.global_flags), item_catalog=self.item_catalog)
            self.exploration.game = self   # <-- ADD THIS LINE (needed for save/load)
            start_room = self.world.current_room()
            if start_room:
                start_room.visited = True
                window.set_explore(self.player, start_room)
                window.append_log(start_room.get_description(verbose=True, turn_number=self.world.turn_counter if self.world else 0))
        elif self.world is None: window.append_log("No world loaded. Exiting."); self.state = GameState.GAME_OVER

        while self.state not in (GameState.GAME_OVER, GameState.WIN):
            try: raw = window.get_input(self._prompt())
            except (EOFError, KeyboardInterrupt): break
            if self.state == GameState.EXPLORING:
                if not self.exploration: window.append_log("Exploration system unavailable."); self.state = GameState.GAME_OVER; continue
                result = self.exploration.player_input(raw)
                for line in result.lines: window.append_log(line)
                if result.combat_triggered: self._enter_combat(result.aggressors)
                if self.world and self.player:
                    cur_room = self.world.current_room()
                    if cur_room:
                        if self.state == GameState.COMBAT and self.combat: window.set_combat(self.player, cur_room, self.combat.enemies)
                        else: window.set_explore(self.player, cur_room)
            elif self.state == GameState.COMBAT:
                if not self.combat:
                    if raw.strip().lower() in {"flee","run"}: self._on_combat_fled()
                    else: window.append_log("Combat scaffolding is not yet implemented; type 'flee' to leave combat.")
                else:
                    result = self.combat.player_input(raw)
                    for line in result.lines: window.append_log(line)
                    if self.world and self.player and self.combat:
                        cur_room = self.world.current_room()
                        if cur_room: window.set_combat(self.player, cur_room, self.combat.enemies)
                    if result.outcome == CombatOutcome.PLAYER_WON: self._on_combat_won()
                    elif result.outcome == CombatOutcome.PLAYER_FLED: self._on_combat_fled()
                    elif result.outcome == CombatOutcome.PLAYER_DEFEATED: self.state = GameState.GAME_OVER
            elif self.state == GameState.LEVEL_UP: self._handle_level_up_choice(raw)
        self._print_end_screen()

    def _enter_combat(self, aggressors: list[Enemy]):
        if not self.world or not self.parser: window.append_log("Combat system not available."); return
        for e in aggressors:
            rid = getattr(e, "combat_room_id", self.world.current_room_id)
            room = self.world.get_room(rid)
            if room and e not in room.enemies: room.add_enemy(e)
        self.combat = CombatController(self.parser, self.registry, self.player, aggressors,
                                       self.world, self.world.current_room_id, self.exploration.puzzle_flags if self.exploration else {}, debug=self.debug)
        window.append_log(self.combat.start_encounter())
        self.state = GameState.COMBAT
        cur_room = self.world.current_room()
        if cur_room: window.set_combat(self.player, cur_room, self.combat.enemies)

    def _on_combat_won(self):
        window.append_log("You won the encounter.")
        total_xp = 0
        for enemy in self.combat.enemies:
            if not enemy.is_alive:
                total_xp += enemy.xp_reward
                # ---- LOOT DROPS ----
                loot_ids = enemy.roll_loot()
                for item_id in loot_ids:
                    if item_id in self.item_catalog:
                        item = self.item_catalog[item_id]
                        self.player.pick_up(item)
                        window.append_log(f"Looted: {item.name}")
        lines, choices = self.player.gain_xp(total_xp)
        for line in lines: window.append_log(line)
        if choices:
            self._pending_level_up_choices = choices
            self.state = GameState.LEVEL_UP
            window.append_log("You have new abilities to choose from! (type number)")
            self._print_choices()
        else:
            self.combat = None; self.state = GameState.EXPLORING
            if self.world and self.exploration:
                self.exploration.world = self.world
                room = self.world.current_room()
                if room:
                    room.update_after_combat()
                    window.set_explore(self.player, room)

    def _on_combat_fled(self):
        window.append_log("You fled combat.")
        self.combat = None; self.state = GameState.EXPLORING
        if self.world and self.player:
            cur_room = self.world.current_room()
            if cur_room: window.set_explore(self.player, cur_room)

    def _prompt(self) -> str:
        if self.state == GameState.COMBAT: return "combat> "
        if self.state == GameState.LEVEL_UP: return "level-up> "
        return "explore> "

    def _print_choices(self):
        if not self._pending_level_up_choices: return
        for group in self._pending_level_up_choices:
            window.append_log("Choose one of:")
            for i, opt in enumerate(group,1): window.append_log(f"  {i}. {opt}")

    def _handle_level_up_choice(self, raw: str):
        if not self._pending_level_up_choices: self.state = GameState.EXPLORING; return
        group = self._pending_level_up_choices[0]
        if raw.strip().isdigit() and 1 <= int(raw.strip()) <= len(group):
            choice = group[int(raw.strip())-1]
            self.player.unlock_command(choice)
            window.append_log(f"Unlocked: {choice}")
            self._pending_level_up_choices.pop(0)
        else:
            window.append_log("Invalid choice. Enter a number from the list.")
            for i, opt in enumerate(group,1): window.append_log(f"  {i}. {opt}")
            return
        if self._pending_level_up_choices: self._print_choices()
        else: self.state = GameState.EXPLORING; window.append_log("Level‑up complete. You continue your journey.")

    def _print_end_screen(self):
        if self.state == GameState.WIN: window.append_log("\n*** VICTORY ***")
        else: window.append_log("\n*** GAME OVER ***")

    def save(self, slot=0):
        if self.state == GameState.COMBAT:
            window.append_log("Cannot save during combat.")
            return
        save_dir = Path("saves"); save_dir.mkdir(parents=True, exist_ok=True)
        payload = {"player": self._serialise_player(), "room_id": self.world.current_room_id if self.world else None,
                   "state": self.state.name}
        if self.world: payload["world"] = self.world.snapshot()
        (save_dir / f"slot_{slot}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        window.append_log(f"Saved to slot {slot}.")

    def load(self, slot=0):
        data = json.loads((Path("saves") / f"slot_{slot}.json").read_text(encoding="utf-8"))
        self.player = self._deserialise_player(data.get("player", {}))
        if self.world: self.world.current_room_id = data.get("room_id", self.world.current_room_id)
        self.state = GameState[data.get("state", "EXPLORING")]
        if self.world and "world" in data: self.world.restore_snapshot(data["world"])
        if self.exploration: self.exploration.player = self.player; self.exploration.world = self.world

    def _serialise_player(self) -> dict:
        if not self.player: return {}
        return {
            "name": self.player.name, "max_hp": self.player.max_hp, "attack": self.player.attack, "defense": self.player.defense,
            "current_hp": self.player.current_hp, "total_ap": self.player.total_ap, "current_ap": self.player.current_ap,
            "max_mana": self.player.max_mana, "mana": self.player.mana, "level": self.player.level, "xp": self.player.xp,
            "unlocked_commands": sorted(self.player.unlocked_commands), "char_class_name": getattr(self.player, "char_class_name", "Adventurer"),
            "inventory": [item.id for item in self.player.inventory], "equipped": {slot: item.id for slot, item in self.player.equipped.items()}
        }

    def _deserialise_player(self, data: dict) -> Player:
        p = Player(name=data.get("name","Hero"), max_hp=int(data.get("max_hp",30)), attack=int(data.get("attack",5)),
                   defense=int(data.get("defense",1)), total_ap=int(data.get("total_ap",20)), max_mana=int(data.get("max_mana",0)), mana=int(data.get("mana",0)))
        p.current_hp = int(data.get("current_hp", p.max_hp)); p.current_ap = int(data.get("current_ap", p.total_ap))
        p.level = int(data.get("level",1)); p.xp = int(data.get("xp",0)); p.unlocked_commands = set(data.get("unlocked_commands",[]))
        setattr(p, "char_class_name", data.get("char_class_name", "Adventurer"))
        for item_id in data.get("inventory", []):
            if item_id in self.item_catalog: p.inventory.append(self.item_catalog[item_id])
        for slot, item_id in data.get("equipped", {}).items():
            if item_id in self.item_catalog: p.equipped[slot] = self.item_catalog[item_id]
        return p