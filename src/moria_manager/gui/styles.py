"""Theme and style constants for the GUI.

This module defines the visual styling constants used throughout the application.
All GUI components should reference these constants to maintain consistent styling.

Constants:
    COLORS: Color palette for buttons, text, and UI elements
    FONTS: Font family, size, and weight configurations
    PADDING: Spacing values for margins and padding
    WINDOW_SIZES: Default and minimum window dimensions

Classes:
    DialogIconMixin: Shared icon setup for dialog windows
"""

import tkinter as tk

from ..assets.loader import get_asset_path

# Color palette - semantic color names for consistent theming
COLORS = {
    "primary": "#1f538d",        # Main action buttons (blue)
    "primary_hover": "#14375e",  # Primary button hover state
    "success": "#2d8a4e",        # Success/confirm actions (green)
    "success_hover": "#1e5c34",  # Success button hover state
    "danger": "#dc3545",         # Destructive/cancel actions (red)
    "danger_hover": "#a71d2a",   # Danger button hover state
    "warning": "#ffc107",        # Warning indicators (yellow)
    "muted": "#6c757d",          # Disabled/secondary text (gray)
}

# Theme-aware colors (light mode, dark mode)
# Format: ("light_color", "dark_color")
THEME_COLORS = {
    "bg_main": ("#f5f5f5", "#1a1a1a"),       # Main window/bars background (off-white/dark)
    "bg_pane": ("#f5f5f5", "#1a1a1a"),       # Left pane background (off-white/dark)
    "bg_pane_content": ("#d0d0d0", "#1a1a1a"),  # Content panes (light grey/dark)
    "bg_tab_selected": ("#a0a0a0", "gray35"),  # Selected tab highlight (medium grey/dark)
    "bg_tab_hover": ("#b8b8b8", "gray30"),   # Tab hover color
    "bg_dropdown": ("#b0b0b0", "#2a2a2a"),   # Dropdown/column background (medium grey for light mode)
    "text": ("#000000", "gray90"),           # Text color (black/white)
    "text_bold": ("#000000", "gray90"),      # Bold text color (black/white)
    "text_secondary": ("#000000", "gray60"),  # Secondary text (black in light, grey in dark)
    "separator": ("gray50", "gray40"),       # Separator lines
    "checkbox": ("#000000", "gray90"),       # Checkbox color (black/white)
    "server_disconnected": ("#1a5fb4", "#1a5fb4"),  # Blue for disconnected servers
    "server_connected": ("#00AA00", "#00AA00"),     # Green for connected servers
    "server_error": ("#c01c28", "#c01c28"),         # Red for failed servers
    "folder_yellow": ("#B8860B", "#FFD700"),        # Dark goldenrod / bright gold
    "folder_green": ("#228B22", "#00FF00"),         # Forest green / lime
    "button_outline": ("#555555", "#333333"),  # Button outline (visible in light, subtle in dark)
    "button_import_bg": ("#e6e0f0", "#2a2a2a"),  # Light lavender / dark grey
    "button_add_server_bg": ("#ffe6cc", "#2a2a2a"),  # Light orange / dark grey
    "list_row_selected": ("#ffffff", "gray25"),  # Selected row (white in light mode)
    "list_row_default": ("#dcdcdc", "gray17"),   # Default row background (gainsboro in light mode)
    "icon_color": ("#000000", "#ffffff"),        # Icon color (black in light, white in dark)
}

# Font configurations - tuple format: (family, size, weight)
FONTS = {
    "title": ("Segoe UI", 18, "bold"),   # Window titles, major headings
    "heading": ("Segoe UI", 14, "bold"), # Section headers
    "body": ("Segoe UI", 12),            # Standard body text
    "body_bold": ("Segoe UI", 12, "bold"),  # Bold body text
    "small": ("Segoe UI", 10),           # Captions, status text
    "small_bold": ("Segoe UI", 10, "bold"),  # Bold captions, column headers
}

# Padding and spacing values in pixels
PADDING = {
    "small": 10,   # Tight spacing (between related elements)
    "medium": 18,  # Standard spacing (between sections)
    "large": 30,   # Wide spacing (window margins)
}

# Window sizes - tuple format: (width, height)
WINDOW_SIZES = {
    "main": (900, 600),          # Main window default size
    "config_dialog": (750, 720), # Configuration dialog size
    "min_main": (700, 500),      # Minimum main window size
}


class DialogIconMixin:  # pylint: disable=too-few-public-methods
    """Mixin providing shared dialog icon setup."""

    def _set_dialog_icon(self):
        """Set the application icon on this dialog."""
        try:
            icon_path = get_asset_path("icons/app_icon.ico")
            if icon_path.exists():
                self.after(
                    200, lambda: self._apply_icon(str(icon_path))
                )
        except (OSError, tk.TclError):
            pass

    def _apply_icon(self, icon_path: str):
        """Apply the icon after delay."""
        try:
            if self.winfo_exists():
                self.iconbitmap(icon_path)
        except (OSError, tk.TclError):
            pass
