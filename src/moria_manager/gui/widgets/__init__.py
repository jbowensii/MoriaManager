"""Reusable GUI widgets for the application.

This module contains custom widget components that can be reused across
different parts of the GUI.

Widgets:
    PathSelector: A compound widget combining a label, text entry, and browse
                  button for file/directory path selection. Includes visual
                  status indicator showing if the path exists.
"""

from .path_selector import PathSelector

__all__ = [
    "PathSelector",
]
