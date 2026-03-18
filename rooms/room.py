# rooms/room.py
"""
Room — the fundamental unit of the world.

Key design:
  link(dir, other, reverse=None)
    Bidirectional by default (reverse inferred from cardinal opposites).
    Pass reverse="west" (or any direction) to override the return path,
    e.g. for the curved arrow in the diagram:
        puzzle_room.link("south", ratssss, reverse="west")
    Pass reverse=False for a strictly one-way connection.
"""
import random

# ── Sensory hint tables ───────────────────────────────────────────────────────

_ENEMY_SOUNDS = [
    (["rat", "rodent", "swarm"],      "frenzied scratching and high-pitched squeaking"),
    (["goblin"],                       "crude weapons clashing and guttural bickering"),
    (["skeleton", "bone", "servant"], "the dry clatter of old bones"),
    (["zombie", "undead"],             "slow shuffling and a low, hollow moan"),
    (["wraith", "ghost", "spirit"],    "an eerie whisper, like breath through a keyhole"),
    (["warden", "knight"],             "heavy armoured footsteps and a resonant growl"),
    (["guard"],                        "the clank of patrolling armour"),
    (["archer"],                       "the periodic creak of a taut bowstring"),
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


# ── Room ──────────────────────────────────────────────────────────────────────

class Room:
    def __init__(self, name, description, items=None, relics=None, ambient=None):
        self.name               = name
        self.description        = description
        self.items              = list(items or [])
        self.relics             = list(relics or [])
        self.enemies            = []
        self.connections        = {}   # {direction: Room}
        self.locked_connections = {}   # {direction: required_item_name}
        self.puzzle             = None
        self.ambient            = list(ambient or [])

    # ── Connection helpers ────────────────────────────────────────────────────

    def add_connection(self, direction, room):
        """One-way connection."""
        self.connections[direction] = room

    def link(self, direction, other, reverse=None):
        """
        Connect self → other in `direction`.

        reverse:
          None (default) — infer the opposite cardinal direction and link back.
          str            — use this specific direction for the return path.
          False          — one-way; other gets no return connection.

        Examples:
          hall.link("south", kitchen)
            → hall["south"] = kitchen, kitchen["north"] = hall

          puzzle_room.link("south", ratssss, reverse="west")
            → puzzle_room["south"] = ratssss, ratssss["west"] = puzzle_room

          trapdoor.link("down", dungeon, reverse=False)
            → trapdoor["down"] = dungeon  (no return)
        """
        self.connections[direction] = other
        if reverse is False:
            return
        back = reverse if reverse else _OPPOSITES.get(direction)
        if back:
            other.connections[back] = self

    def lock(self, direction, required_item):
        """Mark an outgoing exit as locked, requiring the named item."""
        self.locked_connections[direction] = required_item

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
        """Return one random ambient string, or empty string if none defined."""
        return random.choice(self.ambient) if self.ambient else ""

    # ── Listen ────────────────────────────────────────────────────────────────

    def listen_hints(self):
        """
        Return list of (direction, hint_str) for every connected room.
        """
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
        """
        Called by the Game when the player moves into this room.
        Override in subclasses or assign a lambda for one-off room events.
        Default: nothing.
        """
        pass

    def __repr__(self):
        return f"<Room '{self.name}'>"