# entities/player.py
from utils.constants import MAX_HEALTH, MAX_AP, MAX_MANA, XP_PER_LEVEL


class Player:
    def __init__(self, name):
        self.name        = name
        self.health      = MAX_HEALTH
        self.max_health  = MAX_HEALTH
        self.current_ap  = MAX_AP
        self.mana        = MAX_MANA
        self.max_mana    = MAX_MANA
        self.inventory   = []
        self.statuses    = {}
        self.relics      = []
        self.defending   = False
        self._block_reduction = 0.5
        self.xp          = 0
        self.level       = 1
        self.level_ups   = []

    def heal(self, amount):
        self.health = min(self.health + amount, self.max_health)

    def take_damage(self, amount):
        self.health = max(0, self.health - amount)

    def gain_xp(self, amount):
        self.xp += amount
        while self.xp >= self.level * XP_PER_LEVEL:
            self.xp -= self.level * XP_PER_LEVEL
            self.level += 1
            self.level_ups.append(self.level)  # stats applied in show_levelup

    def is_alive(self):
        return self.health > 0

    # ── Relic helpers ─────────────────────────────────────────────────────────

    def add_relic(self, relic):
        self.relics.append(relic)

    def has_relic(self, name):
        return any(r.name.lower() == name.lower() for r in self.relics)

    def trigger_relics(self, event, enemy, ctx):
        """Fire all relics for a given trigger event."""
        for relic in self.relics:
            relic.trigger(event, self, enemy, ctx)