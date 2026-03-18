# entities/enemy.py
import random


class EnemyMove:
    """
    A single action an enemy can take on their turn.
    weight   - relative probability of being chosen (higher = more likely)
    effect   - fn(enemy, player) that performs the action
    cooldown - turns before this move can be used again (0 = no cooldown)
    """
    def __init__(self, name, weight, effect, cooldown=0):
        self.name     = name
        self.weight   = weight
        self.effect   = effect
        self.cooldown = cooldown
        self._cd_remaining = 0   # turns until usable again

    def is_ready(self):
        return self._cd_remaining <= 0

    def use(self, enemy, player):
        self.effect(enemy, player)
        self._cd_remaining = self.cooldown

    def tick_cooldown(self):
        if self._cd_remaining > 0:
            self._cd_remaining -= 1


class Enemy:
    def __init__(self, name, health, attack_power, xp_reward=10, moves=None):
        self.name         = name
        self.health       = health
        self.max_health   = health
        self.attack_power = attack_power
        self.xp_reward    = xp_reward
        self.statuses     = {}
        self.moves        = moves or []   # list of EnemyMove; empty = basic attack only
        self._turn        = 0             # tracks turn count for pattern-based moves

    def choose_move(self):
        """Weighted random selection from ready moves. Falls back to basic attack."""
        ready = [m for m in self.moves if m.is_ready()]
        if not ready:
            return None   # caller uses basic attack
        weights = [m.weight for m in ready]
        return random.choices(ready, weights=weights, k=1)[0]

    def tick_move_cooldowns(self):
        for m in self.moves:
            m.tick_cooldown()

    def take_damage(self, amount):
        self.health = max(0, self.health - amount)

    def is_alive(self):
        return self.health > 0