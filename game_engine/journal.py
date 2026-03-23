# game_engine/journal.py
"""
Journal / Codex — two sections:
  lore     : entries added from scrolls, puzzle solves, and NPC dialogue.
  bestiary : one record per enemy type encountered; tracks HP range,
             moves seen, and drops observed.

Serialises to plain dicts for save/load via SaveManager.
"""
from utils.helpers import print_slow


class Journal:
    def __init__(self):
        self.lore:     list  = []   # [{title, body}]
        self.bestiary: dict  = {}   # name → {hp_min, hp_max, atk, moves_seen, drops_seen}

    # ── Lore ──────────────────────────────────────────────────────────────────

    def add_lore(self, title: str, body: str) -> None:
        """Add a lore entry (deduplicates by title)."""
        if not any(e["title"] == title for e in self.lore):
            self.lore.append({"title": title, "body": body})

    # ── Bestiary ──────────────────────────────────────────────────────────────

    def record_enemy(self, enemy) -> None:
        """Register a defeated enemy (or update HP range if seen before)."""
        name = enemy.name
        if name not in self.bestiary:
            self.bestiary[name] = {
                "hp_min":      enemy.max_health,
                "hp_max":      enemy.max_health,
                "atk":         enemy.attack_power,
                "moves_seen":  [],
                "drops_seen":  [],
            }
        else:
            rec = self.bestiary[name]
            rec["hp_min"] = min(rec["hp_min"], enemy.max_health)
            rec["hp_max"] = max(rec["hp_max"], enemy.max_health)

    def record_move(self, enemy_name: str, move_name: str) -> None:
        """Record a move the player has seen an enemy use."""
        if enemy_name in self.bestiary:
            moves = self.bestiary[enemy_name]["moves_seen"]
            if move_name not in moves:
                moves.append(move_name)

    def record_drop(self, enemy_name: str, item_name: str) -> None:
        """Record an item dropped by a specific enemy type."""
        if enemy_name in self.bestiary:
            drops = self.bestiary[enemy_name]["drops_seen"]
            if item_name not in drops:
                drops.append(item_name)

    # ── Display ───────────────────────────────────────────────────────────────

    def show(self) -> None:
        print(f"\n  {'═'*50}")
        print_slow("  ║            JOURNAL / CODEX                  ║")
        print(f"  {'═'*50}")

        # Lore
        print_slow("\n  ── LORE ─────────────────────────────────────────")
        if not self.lore:
            print_slow("  No lore entries yet.")
        else:
            for i, entry in enumerate(self.lore, 1):
                print_slow(f"\n  [{i}] {entry['title']}")
                for line in entry["body"].splitlines():
                    print_slow(f"      {line}")

        # Bestiary
        print_slow("\n\n  ── BESTIARY ──────────────────────────────────────")
        if not self.bestiary:
            print_slow("  No enemies encountered yet.")
        else:
            for name, rec in self.bestiary.items():
                hp_str = (
                    f"{rec['hp_min']}"
                    if rec["hp_min"] == rec["hp_max"]
                    else f"{rec['hp_min']}–{rec['hp_max']}"
                )
                print_slow(f"\n  {name}")
                print_slow(f"    HP: {hp_str}  |  ATK: ~{rec['atk']}")
                if rec["moves_seen"]:
                    print_slow(f"    Moves seen  : {', '.join(rec['moves_seen'])}")
                if rec["drops_seen"]:
                    print_slow(f"    Drops seen  : {', '.join(rec['drops_seen'])}")

        print(f"\n  {'─'*50}")
        input("  Press Enter to close journal...")

    # ── Serialisation ─────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {"lore": self.lore, "bestiary": self.bestiary}

    @classmethod
    def from_dict(cls, data: dict) -> "Journal":
        j = cls()
        j.lore     = data.get("lore", [])
        j.bestiary = data.get("bestiary", {})
        return j