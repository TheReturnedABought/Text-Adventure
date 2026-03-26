# entities/player.py
from utils.constants import MAX_HEALTH, MAX_AP, MAX_MANA, XP_PER_LEVEL, UNBREAKABLE_CAP
from game_engine.journal import Journal


class Player:
    def __init__(self, name, char_class="soldier"):
        self.name       = name
        self.char_class = char_class.lower()

        # ── Stats ─────────────────────────────────────────────────────────────
        self.health     = MAX_HEALTH
        self.max_health = MAX_HEALTH
        self.current_ap = MAX_AP
        self.mana       = MAX_MANA
        self.max_mana   = MAX_MANA

        # ── Progression ───────────────────────────────────────────────────────
        self.xp          = 0
        self.level       = 1
        self.level_ups   = []               # queue of new levels for show_levelup
        self.pending_command_choices = []   # [(level, [cmd_dict, ...])]
        self.auto_unlocked_commands  = []   # [(cmd_name, desc)]
        self.known_commands          = set()
        self.actions_this_combat     = 0    # reset at combat start

        # ── Inventory / relics ────────────────────────────────────────────────
        self.inventory    = []
        self.relics       = []
        self.statuses     = {}
        self.combat_flags = {}

        # ── Pending combat-start effects ──────────────────────────────────────
        # Each entry: (effect_name: str, value: int)
        self.pending_combat_effects = []

        # ── Journal / Codex ───────────────────────────────────────────────────
        self.journal = Journal()

    # ── Healing / damage ──────────────────────────────────────────────────────

    def heal(self, amount):
        self.health = min(self.health + amount, self.max_health)

    def mp_restore(self,amount):
        self.mana = min(self.mana + amount, MAX_MANA)

    def take_damage(self, amount):
        if self.combat_flags.get("unbreakable"):
            amount = min(amount, UNBREAKABLE_CAP)
        self.health = max(0, self.health - amount)

    def is_alive(self):
        return self.health > 0

    # ── XP / levelling ────────────────────────────────────────────────────────

    def gain_xp(self, amount):
        self.xp += amount
        while self.xp >= self.level * XP_PER_LEVEL:
            self.xp -= self.level * XP_PER_LEVEL
            self.level += 1
            self.level_ups.append(self.level)
            self._check_command_unlock(self.level)

    def _check_command_unlock(self, new_level):
        from entities.class_data import CLASS_COMMANDS
        tiers = CLASS_COMMANDS.get(self.char_class, {})
        if new_level not in tiers:
            return
        choices = tiers[new_level]
        if len(choices) == 1:
            cmd = choices[0]
            self.known_commands.add(cmd["name"])
            self.auto_unlocked_commands.append((cmd["name"], cmd["desc"]))
        else:
            self.pending_command_choices.append((new_level, choices))

    # ── Relic helpers ─────────────────────────────────────────────────────────

    def add_relic(self, relic):
        self.relics.append(relic)

    def has_relic(self, name):
        return any(r.name.lower() == name.lower() for r in self.relics)

    def trigger_relics(self, event, enemy, ctx):
        for relic in self.relics:
            relic.trigger(event, self, enemy, ctx)

    # ── Combat helpers ────────────────────────────────────────────────────────

    def reset_combat_state(self):
        """Call at the start of each new combat."""
        self.combat_flags        = {}
        self.actions_this_combat = 0
