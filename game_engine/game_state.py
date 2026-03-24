# game_engine/game_state.py
"""
GameState — single source of truth for all mutable game data.

Pure data container: no business logic, no I/O.
Every part of the game that needs to read or write game state does so
through a GameState instance, making state portable and serialisable.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from entities.player import Player
    from rooms.room import Room


class GameMode(str, Enum):
    EXPLORE = "explore"
    COMBAT  = "combat"
    MENU    = "menu"
    OVER    = "over"


@dataclass
class GameState:
    """
    All mutable game state in one place.

    player      : The player character.
    room        : The room the player is currently in.
    start_room  : Root room for the map renderer and SaveManager BFS.
    mode        : Current game phase.
    running     : Set False to exit the main loop.
    """
    player:     "Player"
    room:       "Room"
    start_room: "Room"
    mode:       GameMode = GameMode.EXPLORE
    running:    bool     = True

    # ── Convenience properties ────────────────────────────────────────────────

    @property
    def is_explore(self) -> bool:
        return self.mode == GameMode.EXPLORE

    @property
    def is_combat(self) -> bool:
        return self.mode == GameMode.COMBAT

    @property
    def is_over(self) -> bool:
        return self.mode == GameMode.OVER or not self.player.is_alive()

    # ── Transition helpers ────────────────────────────────────────────────────

    def enter_room(self, room: "Room"):
        self.room = room
        self.mode = GameMode.EXPLORE

    def start_combat(self):
        self.mode = GameMode.COMBAT

    def end_combat(self):
        self.mode = GameMode.EXPLORE

    def game_over(self):
        self.mode    = GameMode.OVER
        self.running = False