# game_engine/game_state.py
"""
GameState — pure data container, single source of truth for mutable game data.
No business logic, no I/O, no imports from game sub-systems.
"""
from __future__ import annotations
from dataclasses import dataclass
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
    player:     "Player"
    room:       "Room"
    start_room: "Room"
    mode:       GameMode = GameMode.EXPLORE
    running:    bool     = True

    @property
    def is_explore(self) -> bool:
        return self.mode == GameMode.EXPLORE

    @property
    def is_combat(self) -> bool:
        return self.mode == GameMode.COMBAT

    @property
    def is_over(self) -> bool:
        return self.mode == GameMode.OVER or not self.player.is_alive()

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