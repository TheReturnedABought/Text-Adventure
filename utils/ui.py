# utils/ui.py
"""
Compatibility shim — all existing `from utils.ui import ui` calls still work.
Everything delegates to the GameWindow singleton in utils/window.py.
"""
from utils.window import window as ui  # noqa: F401
__all__ = ['ui']