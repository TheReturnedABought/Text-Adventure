# entities/player.py
from utils.constants import MAX_HEALTH, MAX_AP, XP_PER_LEVEL, CHARACTER_CLASS

class Player:
    def __init__(self, name):
        self.name = name
        self.cclass = CHARACTER_CLASS
        self.health = MAX_HEALTH
        self.max_health = MAX_HEALTH
        self.current_ap = MAX_AP
        self.inventory = []
        self.defending = False
        self.xp = 0
        self.level = 1
        self.level_ups = []  # Stores pending level-up messages for display

    def heal(self, amount):
        self.health = min(self.health + amount, self.max_health)

    def take_damage(self, amount):
        self.health = max(0, self.health - amount)

    def gain_xp(self, amount):
        self.xp += amount
        while self.xp >= self.level * XP_PER_LEVEL:
            self.xp -= self.level * XP_PER_LEVEL
            self.level += 1
            self.level_ups.append(self.level)  # Queue — stats applied on display

    def is_alive(self):
        return self.health > 0
