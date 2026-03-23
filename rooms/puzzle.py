# rooms/puzzle.py
"""
Puzzle — a room object the player can examine and solve.

Supports:
- Standard puzzles
- Mini puzzles (mini=True)
"""

from utils.helpers import print_slow


class Puzzle:
    def __init__(
        self,
        name,
        description,
        clues=None,
        solution="",
        reward_fn=None,
        mini=False,          # ✅ NEW
    ):
        self.name        = name
        self.description = description
        self.clues       = clues or []
        self.solution    = solution.lower().strip()
        self.solved      = False
        self.reward_fn   = reward_fn
        self.mini        = mini   # ✅ store it

    def examine(self):
        print()

        # Mini puzzles get smaller header
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

        print_slow("\n  Type 'solve <your answer>' to attempt a solution.")

    def attempt(self, player, room, raw_answer):
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