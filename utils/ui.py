# utils/ui.py
"""
Compatibility shim.

All existing code that does:
    from utils.ui import ui
    ui.set_explore(...)
    ui.set_combat(...)
    ui.log(...)
    ui._active
    ui.refresh()

continues to work unchanged — everything delegates to the GameWindow
singleton in utils/window.py.
"""
from utils.window import window as ui   # noqa: F401
__all__ = ['ui']