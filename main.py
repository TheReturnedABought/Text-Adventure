import sys
import traceback
from functools import wraps
from game import TextAdventureGame

DEBUG = True

def debug_trace(func):
    """Decorator to print function entry/exit when DEBUG is True."""
    if not DEBUG:
        return func
    @wraps(func)
    def wrapper(*args, **kwargs):
        print(f"[DEBUG] Entering {func.__qualname__}")
        try:
            result = func(*args, **kwargs)
            print(f"[DEBUG] Exiting {func.__qualname__}")
            return result
        except Exception as e:
            tb = traceback.extract_tb(sys.exc_info()[2])
            last_frame = tb[-1]
            print(
                f"[DEBUG] Exception in {func.__qualname__}: {e}\n"
                f"        File: {last_frame.filename}, Line {last_frame.lineno}: {last_frame.line}"
            )
            raise
    return wrapper

def main() -> None:
    game = TextAdventureGame(debug=DEBUG)
    game.run()

if __name__ == "__main__":
    main()