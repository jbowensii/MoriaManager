"""Main application entry point and orchestrator"""

import sys

import customtkinter as ctk

from .config.manager import ConfigurationManager
# from .core.backup_service import BackupService  # Not currently used
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
        # self.backup_service: BackupService | None = None  # Not currently used
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
        else:
            self.config_manager.load()

        # Initialize backup service (not currently used)
        # self.backup_service = BackupService(self.config_manager)

        # Create main window
        self.main_window = MainWindow(self.config_manager)

        # If first run, show config dialog immediately after main window renders
        if is_first_run:
            self.main_window.after(100, self._show_first_run_config)

        # Start the main loop
        self.main_window.mainloop()

    def _handle_first_run(self):
        """Handle first-run setup."""
        # Auto-detect game installations
        detector = GameDetector()
        installations = detector.detect_all()

        # Create default configuration with detected installations
        self.config_manager.create_default(installations)

    def _show_first_run_config(self):
        """Show the configuration dialog for first-run setup."""
        if self.main_window is None:
            return

        dialog = ConfigDialog(
            self.main_window,
            self.config_manager,
            first_run=True
        )

        # Wait for dialog to close
        self.main_window.wait_window(dialog)

        # If user closed without saving (shouldn't happen with first_run=True modal)
        # but handle it gracefully
        if not self.config_manager.config.settings.first_run_complete:
            # Save anyway to prevent repeated first-run prompts
            self.config_manager.config.settings.first_run_complete = True
            self.config_manager.save()

        # Refresh main window to show configured installations
        self.main_window._refresh_ui()


def main():
    """Application entry point."""
    # Initialize logging first
    logger = setup_logging(debug="--debug" in sys.argv)
    logger.info(f"Starting Moria Manager v{__version__}")

    try:
        app = MoriaManagerApp()
        app.run()
    except Exception as e:
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
