# rooms/map_data.py
"""
World coordinator — imports area setup functions and chains them.
Exposes `setup_rooms()` which returns the starting room.

`start_room` is also the root node for:
  - The ASCII map renderer (show_map in display.py)
  - The SaveManager BFS (to find all rooms)

Add future areas here by importing their setup function, calling it,
and linking the returned entrance room to the appropriate exit of the
previous area.
"""
from rooms.area1 import setup_area1


def setup_rooms():
    """Build the full world and return the player's starting room."""
    starting_room = setup_area1()
    # Future: area2_entrance = setup_area2()
    #         crypt_gate.link("east", area2_entrance)
    return starting_room