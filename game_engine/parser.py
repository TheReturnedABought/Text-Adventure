# game_engine/parser.py

ALIASES = {
    "n": "north",
    "s": "south",
    "e": "east",
    "w": "west",
    "i": "inventory",
    "l": "look",
    "h": "help",
    "g": "go",
}

def parse_command(user_input):
    """
    Takes raw user input and returns (command, args).
    Applies single-letter aliases.
    """
    parts = user_input.strip().lower().split()
    if not parts:
        return "", []

    cmd = parts[0]
    args = parts[1:]

    # Expand single-letter aliases
    cmd = ALIASES.get(cmd, cmd)

    return cmd, args
