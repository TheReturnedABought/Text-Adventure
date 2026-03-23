# rooms/events.py
"""
Event system — room events the player can interact with.

Public API used by area files
──────────────────────────────
Event(name, description, options=[])
    Room event. Shown when the player types 'interact'.
    Has a `resolved` flag; once resolved it can't be triggered again.

opt(label, action, requires=None, consumes=False)
    Create one clickable option for an Event.
    label    : str  — shown in the menu
    action   : callable(player, room) -> None  — what happens when chosen
    requires : str | None  — item name that must be in inventory
    consumes : bool        — remove the required item on use

narrate(text)
    Returns an action callable that prints `text` with print_slow.

queue_effect(effect_name, value)
    Returns an action callable that appends (effect_name, value) to
    player.pending_combat_effects (takes effect at next combat start).

chain(*actions)
    Returns an action callable that runs each sub-action in order.

give_relic(relic_name)
    Returns an action callable(player, room) -> str that grants the named
    relic and returns a short confirmation string.
    Used as a reward_fn inside puzzle callbacks.
"""
from utils.helpers import print_slow


# ── Action builders ───────────────────────────────────────────────────────────

def narrate(text: str):
    """Print text (with print_slow) when the action fires."""
    def _action(player, room):
        for line in text.splitlines():
            print_slow(f"  {line}")
    return _action


def queue_effect(effect_name: str, value):
    """Append a pending combat effect that triggers at the next combat start."""
    def _action(player, room):
        player.pending_combat_effects.append((effect_name, value))
        print_slow(f"  Something stirs — the effect will manifest when next you fight.")
    return _action


def chain(*actions):
    """Run multiple action callables in sequence."""
    def _action(player, room):
        for act in actions:
            act(player, room)
    return _action


def give_relic(relic_name: str):
    """
    Return a callable(player, room) -> str that grants the named relic.
    Used both as a standalone action and as a reward_fn in puzzles.
    """
    def _action(player, room):
        from utils.relics import get_relic
        from utils.ascii_art import RELIC_ART, print_art
        from utils.helpers import RARITY_COLORS, RESET
        r = get_relic(relic_name)
        if r is None:
            return f"(relic '{relic_name}' not found)"
        player.add_relic(r)
        art = RELIC_ART.get(r.name)
        if art:
            print_art(art, indent=10)
        color  = RARITY_COLORS.get(getattr(r, "rarity", "Common"), "")
        rarity = getattr(r, "rarity", "Common")
        msg = f"{color}{r.name}{RESET}  [{rarity}] — {r.description}"
        return msg
    return _action


# ── Option ────────────────────────────────────────────────────────────────────

class _Option:
    """One interactive choice within an Event."""

    def __init__(self, label: str, action, requires: str | None = None,
                 consumes: bool = False):
        self.label    = label
        self.action   = action   # callable(player, room) -> None | str
        self.requires = requires
        self.consumes = consumes

    def can_use(self, player) -> bool:
        if self.requires is None:
            return True
        return any(self.requires.lower() in i.lower() for i in player.inventory)

    def execute(self, player, room):
        if self.requires and self.consumes:
            match = next(
                (i for i in player.inventory if self.requires.lower() in i.lower()),
                None,
            )
            if match:
                player.inventory.remove(match)
                print_slow(f"  (You use your {match}.)")
        self.action(player, room)


def opt(label: str, action, requires: str | None = None,
        consumes: bool = False) -> _Option:
    """Factory for Event options (mirrors the call-site API in area files)."""
    return _Option(label, action, requires=requires, consumes=consumes)


# ── Event ─────────────────────────────────────────────────────────────────────

class Event:
    """
    A room event triggered by 'interact'.

    Attributes
    ----------
    name        : str
    description : str  — shown every time (even after resolved)
    options     : list[_Option]
    resolved    : bool — True after the event fires once; prevents replay
    """

    def __init__(self, name: str, description: str, options=None):
        self.name        = name
        self.description = description
        self.options     = list(options or [])
        self.resolved    = False

    def show(self, player, room):
        print()
        print_slow(f"  ── {self.name} ──")
        for line in self.description.splitlines():
            print_slow(f"  {line}")

        if self.resolved:
            print_slow("\n  (You have already acted here.)")
            return

        # Filter options to those the player can currently use
        available = [o for o in self.options if o.can_use(player)]
        locked    = [o for o in self.options if not o.can_use(player)]

        if not available and not locked:
            # Description-only event
            self.resolved = True
            return

        print()
        idx = 1
        option_map = {}
        for o in available:
            print_slow(f"  [{idx}] {o.label}")
            option_map[str(idx)] = o
            idx += 1
        for o in locked:
            req = f"(requires: {o.requires})"
            print_slow(f"  [–] {o.label}  {req}")

        if not available:
            print_slow("\n  You lack what is needed to act here.")
            return

        print_slow(f"  [0] Leave")
        print()

        while True:
            raw = input("  Choose: ").strip()
            if raw == "0" or raw.lower() in ("", "leave", "back"):
                print_slow("  You step back.")
                return
            if raw in option_map:
                chosen = option_map[raw]
                print()
                chosen.execute(player, room)
                self.resolved = True
                return
            print("  Invalid choice.")


# ── Merchant (stub — extend as needed) ───────────────────────────────────────

class Merchant:
    """
    A simple shop NPC. Not yet wired to any area; included so
    save_manager.py's `room.event.resolved` check works if a Merchant
    is ever placed in a room.
    """

    def __init__(self, name: str, inventory: list):
        self.name      = name
        self.inventory = list(inventory)   # [(item_name, price), ...]
        self.resolved  = False             # merchants never permanently resolve

    def show(self, player, room):
        print_slow(f"\n  {self.name} eyes you carefully.")
        if not self.inventory:
            print_slow("  \"Nothing left for sale.\"")
            return
        print_slow("  Wares for sale:")
        for item, price in self.inventory:
            print_slow(f"    {item:<20} — {price} gold coin(s)")
        print_slow("\n  (Merchant purchasing not yet implemented.)")