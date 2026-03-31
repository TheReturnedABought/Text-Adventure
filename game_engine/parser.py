# game_engine/parser.py

ALIASES = {
    "n":  "north",
    "s":  "south",
    "e":  "east",
    "w":  "west",
    "i":  "inventory",
    "l":  "look",
    "h":  "help",
    "g":  "go",
    "j":  "journal",
    "m":  "map",
    "open": "interact",
}


def parse_command(user_input):
    """
    Takes raw user input and returns (command, args).
    Applies single-letter aliases.
    """
    parts = user_input.strip().lower().split()
    if not parts:
        return "", []
    cmd  = ALIASES.get(parts[0], parts[0])
    args = parts[1:]
    return cmd, args
