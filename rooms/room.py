# rooms/room.py

class Room:
    def __init__(self, name, description, items=None, relics=None):
        self.name = name
        self.description = description
        self.items = items or []
        self.relics = relics or []
        self.enemies = []
        self.connections = {}  # {"north": <Room>, "south": <Room>, ...}

    def add_connection(self, direction, room):
        self.connections[direction] = room

    def link(self, direction, other_room):
        opposites = {"north": "south", "south": "north", "east": "west", "west": "east"}
        self.connections[direction] = other_room
        if direction in opposites:
            other_room.connections[opposites[direction]] = self