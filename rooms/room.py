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
from utils.helpers import print_slow

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
    Anything the player can examine or interact with.
    """

    def __init__(self, name: str, examine_fn=None, use_fn=None, uses: int = 1, combat_only: bool = False,
                 visible: bool = True):
        self.name = name
        self.examine_fn = examine_fn
        self.use_fn = use_fn
        self.uses = uses
        self.combat_only = combat_only
        self.visible = visible
        self._uses_left = uses
        # New option system attributes
        self._options = None
        self._resolved_options = set()
        self._examine_text = None

    def add_options(self, description: str, options: list):
        """
        Add multiple interactive options after examine.
        options: list of dicts like [
            {'label': 'Light it', 'requires': None, 'consumes': False, 'action': some_callable},
            {'label': 'Move on', 'requires': None, 'action': some_callable}
        ]
        """
        self._examine_text = description
        self._options = options

    def can_use(self, in_combat: bool = False) -> bool:
        if not self.visible:
            return False
        if self._uses_left <= 0:
            return False
        if self.combat_only and not in_combat:
            return False
        return True

    def examine(self, player, room):
        if not self.visible:
            print_slow("  You see nothing unusual.")
            return

        print_slow(f"  You examine the {self.name}.")

        # Print examine text if defined by add_options, else use examine_fn or default
        if self._examine_text:
            for line in self._examine_text.splitlines():
                print_slow(f"  {line}")
        elif self.examine_fn:
            self.examine_fn(player, room)
        else:
            print_slow("  Nothing stands out.")

        # Show options if defined
        if self._options:
            print_slow("\n  What do you do?")
            available = []
            locked = []
            option_map = {}
            idx = 1

            for opt in self._options:
                if idx in self._resolved_options:
                    continue
                if opt.get('requires'):
                    has_req = any(opt['requires'].lower() in i.lower() for i in player.inventory)
                    if has_req:
                        available.append((idx, opt))
                    else:
                        locked.append((idx, opt))
                else:
                    available.append((idx, opt))
                option_map[str(idx)] = opt
                idx += 1

            # Show available options
            for i, opt in available:
                print_slow(f"  [{i}] {opt['label']}")
            # Show locked options
            for i, opt in locked:
                req = f"(requires: {opt['requires']})"
                print_slow(f"  [–] {opt['label']} {req}")

            if available:
                print_slow("  [0] Leave")
                print()

                while True:
                    raw = input("  Choose: ").strip()
                    if raw == "0" or raw.lower() in ("", "leave", "back"):
                        print_slow("  You step back.")
                        return
                    if raw in option_map:
                        chosen = option_map[raw]
                        self._resolved_options.add(int(raw))

                        # Handle item consumption
                        if chosen.get('requires') and chosen.get('consumes', False):
                            match = next((i for i in player.inventory if chosen['requires'].lower() in i.lower()), None)
                            if match:
                                player.inventory.remove(match)
                                print_slow(f"  (You use your {match}.)")

                        # Execute action
                        chosen['action'](player, room)
                        return
                    print("  Invalid choice.")
            else:
                print_slow("  You lack what is needed to act here.")

    def activate(self, player, room, enemies=None):
        if not self.can_use():
            return f"  The {self.name} has already been used."
        self._uses_left -= 1
        if self.use_fn:
            return self.use_fn(player, room, enemies or [])
        return f"  Nothing happens when you use the {self.name}."

class RevealObject(EnvObject):
    """
    Special EnvObject that reveals a hidden connection when activated.
    """

    def __init__(self, name: str, direction: str, target_room: 'Room', reveal_fn=None, use_fn=None, **kwargs):
        super().__init__(name=name, use_fn=use_fn or self._default_reveal, **kwargs)
        self.direction = direction
        self.target_room = target_room
        self.reveal_fn = reveal_fn
        self._revealed = False

    def _default_reveal(self, player, room):
        if self._revealed:
            return f"  The passage to the {self.direction} is already revealed."

        room.reveal_connection(self.direction, self.target_room)
        self._revealed = True

        if self.reveal_fn:
            self.reveal_fn(player, room)
        else:
            print_slow(f"  A hidden passage opens to the {self.direction}, revealing a new room!")

        # Hide this object after revealing
        self.visible = False

class Puzzle(EnvObject):
    """
    An examinable object that can be solved.
    """
    def __init__(self, name: str, description: str, clues=None, solution: str = "", reward_fn=None, mini: bool = False, visible: bool = True):
        super().__init__(name=name, visible=visible)
        self.description = description
        self.clues = list(clues or [])
        self.solution = solution.lower().strip()
        self.reward_fn = reward_fn
        self.mini = mini
        self.solved = False

    def examine(self, player, room):
        print()
        if self.mini:
            print_slow(f"  ── {self.name} ──")
        else:
            print_slow(f"  ╔══  {self.name}  ══╗")

        for line in self.description.splitlines():
            print_slow(f"  {line}")

        if self.solved:
            print_slow("\n  [SOLVED ✦]")
            return

        for clue in self.clues:
            print_slow(f"  {clue}")

        print_slow("\n  Type your answer directly to attempt a solution.")

    def attempt(self, player, room, raw_answer: str):
        if self.solved:
            print_slow("  You have already solved this puzzle.")
            return True

        if raw_answer.lower().strip() == self.solution:
            self.solved = True

            if self.mini:
                print_slow("\n  ✓ Click — solved!")
            else:
                print_slow("\n  ✦ The mechanism clicks — correct!")

            if self.reward_fn:
                self.reward_fn(player, room)
            else:
                print_slow("  (The puzzle is solved, but the reward awaits.)")

            return True

        print_slow("  ✗ Nothing happens. Try again.")
        return False

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
        self.env_objects        = []

        # Tracking
        self.visit_count          = 0    # incremented by Game on entry
        self._originally_locked   = set()  # filled by lock(); used by SaveManager

    def add_env_object(self, obj: EnvObject):
        self.env_objects.append(obj)

    def add_relic(self, relic):
        self.relics.append(relic)

    def add_item(self, item):
        self.items.append(item)

    def describe(self):
        print(f"\n{self.name}")
        print("-" * len(self.name))
        print(self.description)

        visible_objects = [o.name for o in self.env_objects if o.visible]
        if visible_objects:
            print("\nYou notice:")
            for obj in visible_objects:
                print(f"  - {obj}")

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

    def remove_connection(self, direction: str):
        if direction in self.connections:
            del self.connections[direction]

    def reveal_connection(self, direction: str, room):
        if direction not in self.connections:
            self.connections[direction] = room

    # ── Env objects ───────────────────────────────────────────────────────────

    def get_env_object(self, name: str) -> "EnvObject | None":
        """Find a *visible* EnvObject by exact/partial name match."""
        query = name.lower().strip()
        visible = [o for o in self.env_objects if o.visible]
        if not query:
            return visible[0] if visible else None

        # 1) exact name match
        exact = next((o for o in visible if o.name.lower() == query), None)
        if exact:
            return exact

        # 2) partial contains match
        contains = next((o for o in visible if query in o.name.lower()), None)
        if contains:
            return contains

        # 3) reverse contains (helps commands like "inspect wall" -> "alcove walls")
        return next((o for o in visible if o.name.lower() in query), None)

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
