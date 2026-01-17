"""Theme and style constants for the GUI.

This module defines the visual styling constants used throughout the application.
All GUI components should reference these constants to maintain consistent styling.

Constants:
    COLORS: Color palette for buttons, text, and UI elements
    FONTS: Font family, size, and weight configurations
    PADDING: Spacing values for margins and padding
    WINDOW_SIZES: Default and minimum window dimensions
"""

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

# Font configurations - tuple format: (family, size, weight)
FONTS = {
    "title": ("Segoe UI", 18, "bold"),   # Window titles, major headings
    "heading": ("Segoe UI", 14, "bold"), # Section headers
    "body": ("Segoe UI", 12),            # Standard body text
    "small": ("Segoe UI", 10),           # Captions, status text
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
    "config_dialog": (750, 650), # Configuration dialog size
    "min_main": (700, 500),      # Minimum main window size
}
