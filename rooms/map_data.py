# rooms/map_data.py
"""
World coordinator — imports individual area setup functions and chains them.
Add future areas here (setup_area2, etc.) and link their return rooms together.
"""
from rooms.area1 import setup_area1


def setup_rooms():
    """Build the full world and return the player's starting room."""
    starting_room = setup_area1()
    # Future: area2_entrance = setup_area2(); link here
    return starting_room