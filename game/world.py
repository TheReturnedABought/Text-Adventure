from __future__ import annotations

from dataclasses import dataclass, field

from game.entities import Enemy


@dataclass
class Room:
    name: str
    description: str
    exits: dict[str, str] = field(default_factory=dict)
    enemies: list[Enemy] = field(default_factory=list)


class WorldMap:
    """Data-only room graph for navigation outside combat."""

    def __init__(self) -> None:
        self.rooms: dict[str, Room] = {}

    def add_room(self, room_id: str, room: Room) -> None:
        self.rooms[room_id] = room

    def get_room(self, room_id: str) -> Room:
        return self.rooms[room_id]
