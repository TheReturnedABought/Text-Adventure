# game_engine/engine.py

class GameEngine:
    def __init__(self, player):
        self.player = player
        self.running = True

    def stop(self):
        self.running = False
