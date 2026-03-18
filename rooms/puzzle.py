# rooms/puzzle.py
"""
Puzzle — a room object the player can examine and solve.

Usage in area files:
    room.puzzle = Puzzle(
        name        = "The Dais Inscription",
        description = "...",
        clues       = ["Hint: ..."],
        solution    = "silence",
        reward_fn   = lambda player, room: ...,
    )
"""
from utils.helpers import print_slow


class Puzzle:
    def __init__(self, name, description, clues=None, solution="", reward_fn=None):
        self.name        = name
        self.description = description
        self.clues       = clues or []
        self.solution    = solution.lower().strip()
        self.solved      = False
        self.reward_fn   = reward_fn

    def examine(self):
        print()
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
            print_slow("\n  ✦ The mechanism clicks — correct!")
            if self.reward_fn:
                self.reward_fn(player, room)
            else:
                print_slow("  (The puzzle is solved, but the reward awaits.)")
            return True
        print_slow("  ✗ Nothing happens. Try again.")
        return False