# game_engine/save_manager.py
"""
SaveManager — auto-save and load the full game state as JSON.

Save captures:
  • Player  : name, class, stats, inventory, relic names, known_commands,
              xp, level, pending_combat_effects, statuses, journal
  • World   : per-room state — enemies_defeated, items, relics, puzzle_solved,
              event_resolved, visit_count, unlocked exits
  • Meta    : current_room_name

Auto-save triggers (called from Game):
  • On every successful room transition
  • After every combat victory
  • After every puzzle solve or event resolution

Usage
-----
    from game_engine.save_manager import SaveManager
    sm = SaveManager("save_data/save.json")
    sm.save(game)          # write
    state = sm.load()      # returns dict or None if no save
    sm.delete()            # wipe save
    sm.summary(state)      # one-line string for "continue?" prompt
"""
import json
import os
from collections import deque


SAVE_DIR  = "save_data"
SAVE_FILE = os.path.join(SAVE_DIR, "save.json")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _all_rooms(start_room):
    """BFS from start_room; return list of all reachable Room objects."""
    seen, queue, result = {id(start_room)}, deque([start_room]), []
    while queue:
        room = queue.popleft()
        result.append(room)
        for nb in room.connections.values():
            if id(nb) not in seen:
                seen.add(id(nb))
                queue.append(nb)
    return result


def _find_room(start_room, name):
    """Walk the graph and return the Room whose .name == name, or None."""
    for room in _all_rooms(start_room):
        if room.name == name:
            return room
    return None


# ── SaveManager ───────────────────────────────────────────────────────────────

class SaveManager:

    def __init__(self, path: str = SAVE_FILE):
        self.path = path

    # ── Public API ────────────────────────────────────────────────────────────

    def save(self, game) -> None:
        """Serialise the current game state and write to disk."""
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        data = {
            "player":       self._serialise_player(game.player),
            "current_room": game.room.name,
            "rooms":        self._serialise_rooms(game.start_room),
        }
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def load(self) -> dict | None:
        """Return the saved state dict, or None if no save exists."""
        if not os.path.exists(self.path):
            return None
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

    def delete(self) -> None:
        if os.path.exists(self.path):
            os.remove(self.path)

    def summary(self, state: dict) -> str:
        """One-line string for the 'continue?' prompt."""
        p    = state["player"]
        room = state.get("current_room", "???")
        return (f"{p['name']} the {p['char_class'].capitalize()}  "
                f"— Lvl {p['level']}  —  {room}")

    # ── Apply state to a freshly-built game ───────────────────────────────────

    def apply(self, game, state: dict) -> None:
        """Restore a saved state onto a freshly initialised Game object."""
        self._restore_player(game.player, state["player"])
        self._restore_rooms(game.start_room, state.get("rooms", {}))
        # Move player to saved room
        room = _find_room(game.start_room, state.get("current_room", ""))
        if room:
            game.room = room

    # ── Player serialisation ──────────────────────────────────────────────────

    @staticmethod
    def _serialise_player(p) -> dict:
        return {
            "name":                   p.name,
            "char_class":             p.char_class,
            "health":                 p.health,
            "max_health":             p.max_health,
            "mana":                   p.mana,
            "max_mana":               p.max_mana,
            "xp":                     p.xp,
            "level":                  p.level,
            "inventory":              list(p.inventory),
            "relics":                 [r.name for r in p.relics],
            "known_commands":         list(p.known_commands),
            "statuses":               dict(p.statuses),
            "pending_combat_effects": [list(e) for e in p.pending_combat_effects],
            "journal":                p.journal.to_dict(),
        }

    @staticmethod
    def _restore_player(player, data: dict) -> None:
        from utils.relics import get_relic
        from game_engine.journal import Journal

        player.name       = data["name"]
        player.char_class = data["char_class"]
        player.health     = data["health"]
        player.max_health = data["max_health"]
        player.mana       = data["mana"]
        player.max_mana   = data["max_mana"]
        player.xp         = data["xp"]
        player.level      = data["level"]
        player.inventory  = list(data["inventory"])
        player.statuses   = dict(data.get("statuses", {}))
        player.known_commands = set(data.get("known_commands", []))
        player.pending_combat_effects = [
            tuple(e) for e in data.get("pending_combat_effects", [])
        ]
        player.relics = []
        for rname in data.get("relics", []):
            r = get_relic(rname)
            if r:
                player.relics.append(r)
        player.journal = Journal.from_dict(data.get("journal", {}))

    # ── Room serialisation ────────────────────────────────────────────────────

    @staticmethod
    def _serialise_rooms(start_room) -> dict:
        states = {}
        for room in _all_rooms(start_room):
            states[room.name] = {
                "visit_count":       room.visit_count,
                "enemies_defeated":  all(e.health <= 0 for e in room.enemies),
                "items":             list(room.items),
                "relics":            [r.name for r in room.relics],
                "puzzle_solved":     room.puzzle.solved if room.puzzle else False,
                "event_resolved":    room.event.resolved if room.event else False,
                "unlocked_exits":    [
                    d for d in room.connections
                    if d not in room.locked_connections
                    and d in getattr(room, "_originally_locked", set())
                ],
            }
        return states

    @staticmethod
    def _restore_rooms(start_room, room_states: dict) -> None:
        from utils.relics import get_relic
        for room in _all_rooms(start_room):
            state = room_states.get(room.name)
            if not state:
                continue
            room.visit_count = state.get("visit_count", 0)
            room.items        = list(state.get("items", room.items))
            # Restore relics by name
            relic_names = state.get("relics", None)
            if relic_names is not None:
                room.relics = [r for r in (get_relic(n) for n in relic_names) if r]
            # Defeat enemies
            if state.get("enemies_defeated"):
                for e in room.enemies:
                    e.health = 0
            # Puzzle
            if room.puzzle:
                room.puzzle.solved = state.get("puzzle_solved", False)
            # Event
            if room.event:
                room.event.resolved = state.get("event_resolved", False)
            # Locked exits: restore unlocked state
            for direction in state.get("unlocked_exits", []):
                room.locked_connections.pop(direction, None)