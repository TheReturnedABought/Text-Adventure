# entities/relic.py

# Trigger constants — used by combat.py to fire the right hooks
TRIGGER_ON_ACTION  = "on_action"   # any combat command
TRIGGER_ON_ATTACK  = "on_attack"   # only 'attack'
TRIGGER_ON_HEAL    = "on_heal"     # only 'heal'
TRIGGER_ON_BLOCK   = "on_block"    # only 'block'
TRIGGER_ON_HIT     = "on_hit"      # player takes damage
TRIGGER_TURN_END   = "on_turn_end" # after player ends turn
TRIGGER_TURN_START = "on_turn_start"


class Relic:
    """
    Base class for all relics.
    Subclasses override trigger() and check the event string.
    """
    name        = "Unknown Relic"
    description = "No description."

    def trigger(self, event, player, enemy, ctx):
        """Called for every combat event. Check `event` and act accordingly."""
        pass

    def on_combat_start(self, player, enemy):
        """Called once when entering a new fight."""
        pass

    def __str__(self):
        return f"{self.name}: {self.description}"