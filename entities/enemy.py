# entities/enemy.py

class Enemy:
    def __init__(self, name, health, attack_power, xp_reward=10):
        self.name = name
        self.health = health
        self.max_health = health
        self.attack_power = attack_power
        self.xp_reward = xp_reward
        self.statuses = {}

    def take_damage(self, amount):
        self.health = max(0, self.health - amount)

    def is_alive(self):
        return self.health > 0
