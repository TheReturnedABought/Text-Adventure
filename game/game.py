from __future__ import annotations

from enum import Enum, auto
from pathlib import Path

from game.commands import CommandRegistry, UnlockTable
from game.combat import CombatController, CombatOutcome
from game.exploration import ExplorationController
from game.loader import AssetLoader
from game.parser import CommandParser
from game.entities import Player, Enemy
from game.world import WorldMap


class GameState(Enum):
    EXPLORING = auto()
    COMBAT = auto()
    LEVEL_UP = auto()    # paused waiting for player to choose unlock
    GAME_OVER = auto()
    WIN = auto()


class TextAdventureGame:
    """Top-level orchestrator. Owns all subsystems and the main run loop.

    Startup sequence:
        1. Load all assets via AssetLoader.
        2. Build CommandRegistry from assets/commands/commands.json.
        3. Build WorldMap from assets/rooms/*.json.
        4. Load all enemy templates.
        5. Load all items and classes.
        6. Prompt player to choose a class → build Player.
        7. Enter main run loop.
    """

    ASSETS_ROOT = Path("assets")

    def __init__(self) -> None:
        # ── Sub-systems ───────────────────────────────────────────────────
        self.loader = AssetLoader(self.ASSETS_ROOT)
        self.registry = CommandRegistry()
        self.unlock_table = UnlockTable()
        self.parser: CommandParser | None = None

        # ── Game data ─────────────────────────────────────────────────────
        self.item_catalog: dict = {}
        self.enemy_templates: dict = {}
        self.class_catalog: dict = {}
        self.world: WorldMap | None = None
        self.player: Player | None = None

        # ── Controllers ───────────────────────────────────────────────────
        self.exploration: ExplorationController | None = None
        self.combat: CombatController | None = None

        # ── State ─────────────────────────────────────────────────────────
        self.state: GameState = GameState.EXPLORING
        self._pending_level_up_choices: list[list[str]] = []

    # ══════════════════════════════════════════════════════════════════════
    # Startup
    # ══════════════════════════════════════════════════════════════════════

    def initialise(self) -> None:
        """Load all assets and wire subsystems. Must be called before run()."""
        self._load_assets()
        self._build_subsystems()

    def _load_assets(self) -> None:
        """Load JSON data for items, enemies, classes, commands, and world."""
        ...

    def _build_subsystems(self) -> None:
        """Instantiate CommandParser, ExplorationController with loaded data."""
        ...

    def select_class(self) -> None:
        """Present class options to the player, wait for selection, build Player."""
        ...

    def _build_player(self, class_id: str) -> Player:
        """Construct a Player from the chosen CharacterClass.

        Sets HP, AP, stats from class base_stats.
        Adds starting items to inventory and equips the default one.
        Populates unlocked_commands from level 0/1 entries in unlock_table.
        """
        ...

    # ══════════════════════════════════════════════════════════════════════
    # Main loop
    # ══════════════════════════════════════════════════════════════════════

    def run(self) -> None:
        """Block until the game ends. Handles state transitions."""
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
        """Return the input prompt string for the current state."""
        ...

    # ══════════════════════════════════════════════════════════════════════
    # State handlers
    # ══════════════════════════════════════════════════════════════════════

    def _handle_exploration(self, raw: str) -> None:
        """Route raw input to ExplorationController.

        After the action:
        1. Check exploration result for combat_triggered.
        2. If triggered → _enter_combat(aggressors).
        """
        ...

    def _handle_combat(self, raw: str) -> None:
        """Route raw input to CombatController.

        After the action:
        1. Check TurnResult.outcome.
        2. PLAYER_WON  → _on_combat_won().
        3. PLAYER_FLED → _on_combat_fled().
        4. PLAYER_DEFEATED → state = GAME_OVER.
        """
        ...

    def _handle_level_up_choice(self, raw: str) -> None:
        """Present pending command choices and process player selection.

        After all choices resolved → return to EXPLORING or COMBAT.
        """
        ...

    # ══════════════════════════════════════════════════════════════════════
    # State transitions
    # ══════════════════════════════════════════════════════════════════════

    def _enter_combat(self, aggressors: list[Enemy]) -> None:
        """Transition to COMBAT state.

        1. Create a new CombatController with these enemies.
        2. Call combat.start_encounter() → print opening narration.
        3. Set state = COMBAT.
        """
        ...

    def _exit_combat(self) -> None:
        """Tear down CombatController and return to EXPLORING."""
        ...

    def _on_combat_won(self) -> None:
        """Handle post-combat cleanup after all enemies defeated.

        Steps:
        1. Roll loot for each defeated enemy → place in room.
        2. Distribute XP to player.
        3. Check for level-up → queue choices if needed.
        4. Print summary.
        5. _exit_combat().
        """
        ...

    def _on_combat_fled(self) -> None:
        """Move player one room back along their entry direction and exit combat."""
        ...

    def _on_level_up(self, new_level: int) -> None:
        """Triggered by player.level_up().

        If there are choice_unlocks → set state = LEVEL_UP and queue choices.
        Otherwise stay in current state (auto-unlocks already applied).
        """
        ...

    # ══════════════════════════════════════════════════════════════════════
    # Display helpers
    # ══════════════════════════════════════════════════════════════════════

    def _print_room(self) -> None:
        """Print the current room description."""
        ...

    def _print_end_screen(self) -> None:
        """Print GAME OVER or victory screen."""
        ...

    # ══════════════════════════════════════════════════════════════════════
    # Save / Load
    # ══════════════════════════════════════════════════════════════════════

    def save(self, slot: int = 0) -> None:
        """Serialise full game state (player + world snapshot) to a JSON file.

        Save file location: saves/slot_{slot}.json
        """
        ...

    def load(self, slot: int = 0) -> None:
        """Restore full game state from a save file."""
        ...

    def _serialise_player(self) -> dict:
        """Convert Player to a JSON-serialisable dict."""
        ...

    def _deserialise_player(self, data: dict) -> Player:
        """Reconstruct a Player from a saved dict."""
        ...