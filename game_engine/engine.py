# game_engine/engine.py

class GameEngine:
    """
    Central state holder for the game session.

    Attributes
    ----------
    player      : Player
    start_room  : Room — root node; used by the map renderer and SaveManager BFS.
    running     : bool
    """
    def __init__(self, player):
        self.player     = player
        self.start_room = None   # set by Game.setup() after rooms are built
        self.running    = True

    def stop(self):
        self.running = False