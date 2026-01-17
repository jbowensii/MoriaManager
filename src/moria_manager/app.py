"""Main application entry point and orchestrator.

This module contains the MoriaManagerApp class which coordinates:
    - Application initialization and configuration loading
    - First-run setup with auto-detection of game installations
    - Main window creation and event loop management

The main() function serves as the entry point, handling:
    - Logging setup (file-based, with optional console output via --debug)
    - Error handling with user-friendly error dialogs
    - Clean shutdown with logging

Usage:
    python -m moria_manager [--debug]

    --debug: Enable console logging for troubleshooting
"""

import sys

import customtkinter as ctk

from .config.manager import ConfigurationManager
from .core.game_detector import GameDetector
from .gui.config_dialog import ConfigDialog
from .gui.main_window import MainWindow
from .logging_config import setup_logging, get_logger
from . import __version__


class MoriaManagerApp:
    """Main application orchestrator.

    Handles initialization, first-run detection, and application lifecycle.
    """

    def __init__(self):
        self.config_manager = ConfigurationManager()
        self.main_window: MainWindow | None = None

    def run(self):
        """Run the application."""
        # Set appearance mode to follow system
        ctk.set_appearance_mode("system")
        ctk.set_default_color_theme("blue")

        # Handle first run or load existing config
        is_first_run = self.config_manager.is_first_run()

        if is_first_run:
            self._handle_first_run()
            # Show first-run config dialog before main window
            self._show_first_run_config_standalone()
        else:
            self.config_manager.load()

        # Create main window
        self.main_window = MainWindow(self.config_manager)

        # Start the main loop
        self.main_window.mainloop()

    def _show_first_run_config_standalone(self):
        """Show first-run config dialog as a standalone window."""
        # Create a hidden root window for the dialog
        root = ctk.CTk()
        root.withdraw()

        dialog = ConfigDialog(
            root,
            self.config_manager,
            first_run=True
        )

        # Wait for dialog to close
        root.wait_window(dialog)

        # Check if user cancelled (didn't save)
        if not self.config_manager.config.settings.first_run_complete:
            # User cancelled - exit the application
            root.destroy()
            sys.exit(0)

        # Destroy the temporary root
        root.destroy()

    def _handle_first_run(self):
        """Handle first-run setup."""
        # Auto-detect game installations
        detector = GameDetector()
        installations = detector.detect_all()

        # Create default configuration with detected installations
        self.config_manager.create_default(installations)


def main():
    """Application entry point."""
    # Initialize logging first
    logger = setup_logging(debug="--debug" in sys.argv)
    logger.info(f"Starting Moria Manager v{__version__}")

    try:
        app = MoriaManagerApp()
        app.run()
    except SystemExit:
        # Clean exit requested (e.g., user cancelled first-run setup)
        logger.info("Application exit requested")
        raise
    except (OSError, IOError, RuntimeError, ValueError) as e:
        logger.exception("Fatal error during startup")
        # Show error dialog if something goes wrong during startup
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Startup Error",
            f"Failed to start Moria Manager:\n\n{e}"
        )
        root.destroy()
        sys.exit(1)
    finally:
        logger.info("Moria Manager shutting down")


if __name__ == "__main__":
    main()
