# rooms/room.py
"""
Room — the fundamental unit of the world.

Attributes added vs original:
  visit_count     : int — incremented by Game on every entry; used by
                    map renderer (0 = unexplored) and for triggered events
                    (e.g. stranger appears on 2nd visit).
  env_objects     : list[EnvObject] — interactive room hazards.
                    See EnvObject below for the contract.
  _originally_locked : set — directions that started locked; used by
                    SaveManager to track which locks have been opened.
"""
import random

# ── Sensory hint tables ───────────────────────────────────────────────────────

_ENEMY_SOUNDS = [
    (["rat", "rodent", "swarm"],       "frenzied scratching and high-pitched squeaking"),
    (["goblin"],                        "crude weapons clashing and guttural bickering"),
    (["skeleton", "bone", "servant"],  "the dry clatter of old bones"),
    (["zombie", "undead"],              "slow shuffling and a low, hollow moan"),
    (["wraith", "ghost", "spirit"],     "an eerie whisper, like breath through a keyhole"),
    (["warden", "knight"],              "heavy armoured footsteps and a resonant growl"),
    (["guard"],                         "the clank of patrolling armour"),
    (["archer"],                        "the periodic creak of a taut bowstring"),
]

_ITEM_SCENTS = {
    "torch":      "the smell of burning pitch seeps under the door",
    "crypt key":  "a cold metallic resonance hums faintly",
    "key":        "a faint metallic chime",
    "apple":      "the sweet smell of fruit drifts through",
    "bread":      "a warm, yeasty scent lingers",
    "mushroom":   "a damp, earthy perfume",
    "gold coin":  "something glimmers at the edge of your perception",
    "scroll":     "a dry rustle of parchment",
    "old scroll": "a dry rustle of parchment",
}

_OPPOSITES = {
    "north": "south", "south": "north",
    "east":  "west",  "west":  "east",
}


def _enemy_hint(enemy_name):
    name = enemy_name.lower()
    for keywords, sound in _ENEMY_SOUNDS:
        if any(k in name for k in keywords):
            return sound
    return "an unsettling presence"


# ── EnvObject ─────────────────────────────────────────────────────────────────

class EnvObject:
    """
    An interactive environmental hazard or prop.

    use_fn  : callable(player, room, enemies) -> str
              Called when the player types 'use <name>' in combat (or exploration).
              Should return a message string describing what happened.
    uses    : int — number of times this object can be activated (1 = one-shot).
    combat_only : bool — if True, only activatable mid-combat.
    """
    def __init__(self, name: str, use_fn, uses: int = 1,
                 combat_only: bool = False):
        self.name        = name
        self.use_fn      = use_fn
        self.uses        = uses
        self.combat_only = combat_only
        self._uses_left  = uses

    def can_use(self, in_combat: bool = False) -> bool:
        if self._uses_left <= 0:
            return False
        if self.combat_only and not in_combat:
            return False
        return True

    def activate(self, player, room, enemies=None) -> str:
        if self._uses_left <= 0:
            return f"  The {self.name} has already been used."
        self._uses_left -= 1
        return self.use_fn(player, room, enemies or [])


# ── Room ──────────────────────────────────────────────────────────────────────

class Room:
    def __init__(self, name, description, items=None, relics=None, ambient=None):
        self.name               = name
        self.description        = description
        self.items              = list(items or [])
        self.relics             = list(relics or [])
        self.enemies            = []
        self.connections        = {}     # {direction: Room}
        self.locked_connections = {}     # {direction: required_item_name}
        self.puzzle             = None
        self.ambient            = list(ambient or [])
        self.event              = None   # Event | Merchant | None
        self.env_objects        = []     # list[EnvObject]

        # Tracking
        self.visit_count          = 0    # incremented by Game on entry
        self._originally_locked   = set()  # filled by lock(); used by SaveManager
    # ── Connection helpers ────────────────────────────────────────────────────

    def add_connection(self, direction, room):
        """One-way connection."""
        self.connections[direction] = room

    def link(self, direction, other, reverse=None):
        """
        Bidirectional connection by default.
        reverse=None  → infer opposite cardinal.
        reverse="dir" → explicit return direction.
        reverse=False → one-way only.
        """
        self.connections[direction] = other
        if reverse is False:
            return
        back = reverse if reverse else _OPPOSITES.get(direction)
        if back:
            other.connections[back] = self

    def lock(self, direction, required_item):
        """Mark an outgoing exit as locked; track it for SaveManager."""
        self.locked_connections[direction] = required_item
        self._originally_locked.add(direction)

    def reveal_connection(self, direction: str, other_room: "Room"):
        """
        Reveal a hidden connection to another room.
        If the connection already exists, does nothing.
        Otherwise, links this room to the new room.
        """
        if direction in self.connections:
            return False  # Already revealed
        self.link(direction, other_room)
        return True

    # ── Env objects ───────────────────────────────────────────────────────────

    def get_env_object(self, name: str) -> "EnvObject | None":
        """Find an EnvObject by partial name match."""
        name = name.lower()
        return next((o for o in self.env_objects if name in o.name.lower()), None)

    # ── State queries ─────────────────────────────────────────────────────────

    @property
    def alive_enemies(self):
        return [e for e in self.enemies if e.health > 0]

    @property
    def has_enemies(self):
        return bool(self.alive_enemies)

    @property
    def is_safe(self):
        return not self.has_enemies

    def is_locked(self, direction):
        return direction in self.locked_connections

    def required_key(self, direction):
        return self.locked_connections.get(direction)

    # ── Ambient ───────────────────────────────────────────────────────────────

    def ambient_line(self):
        return random.choice(self.ambient) if self.ambient else ""

    # ── Listen ────────────────────────────────────────────────────────────────

    def listen_hints(self):
        results = []
        for direction, other in self.connections.items():
            parts = []
            alive = other.alive_enemies
            if alive:
                sounds, seen = [], set()
                for e in alive:
                    h = _enemy_hint(e.name)
                    if h not in seen:
                        sounds.append(h)
                        seen.add(h)
                parts.append("You hear " + "; and ".join(sounds))
            if other.relics:
                parts.append("a faint magical aura pulses from within")
            if other.puzzle and not other.puzzle.solved:
                parts.append("the soft grind of ancient stone, as if something waits")
            for item in other.items:
                scent = _ITEM_SCENTS.get(item.lower())
                if scent:
                    parts.append(scent)
                    break
            locked = self.is_locked(direction)
            base = ". ".join(p[0].upper() + p[1:] for p in parts) if parts else "Silence"
            if locked:
                base += " — the way is locked"
            results.append((direction, base + "."))
        return results

    # ── on_enter hook ─────────────────────────────────────────────────────────

    def on_enter(self, player):
        """Called each time the player enters. Override per-room for story beats."""
        pass

    def __repr__(self):
        return f"<Room '{self.name}'>"