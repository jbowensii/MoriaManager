"""Configuration/Settings dialog"""

from typing import Optional

import customtkinter as ctk

from ..config.manager import ConfigurationManager
from ..config.paths import GamePaths
from ..config.schema import InstallationType
from .styles import FONTS, PADDING, WINDOW_SIZES
from .widgets.path_selector import PathSelector


class ConfigDialog(ctk.CTkToplevel):
    """Configuration/Settings dialog with installation and backup settings.

    This dialog is shown automatically on first run and can be accessed
    anytime via the gear icon in the main window.
    """

    def __init__(
        self,
        parent,
        config_manager: ConfigurationManager,
        first_run: bool = False,
    ):
        """Initialize the configuration dialog.

        Args:
            parent: Parent window
            config_manager: Configuration manager instance
            first_run: If True, shows first-run specific messaging
        """
        super().__init__(parent)

        self.config_manager = config_manager
        self.config_changed = False
        self.first_run = first_run

        # Window setup
        self.title("Initial Setup" if first_run else "Settings")
        width, height = WINDOW_SIZES["config_dialog"]
        self.geometry(f"{width}x{height}")
        self.resizable(False, False)

        # Center on parent
        self.transient(parent)
        self.grab_set()

        # Store widget references for saving
        self.installation_vars: dict[InstallationType, ctk.BooleanVar] = {}
        self.path_selectors: dict[InstallationType, PathSelector] = {}

        self._create_ui()

        # Focus this window
        self.focus_force()

    def _create_ui(self):
        """Create the dialog UI."""
        # Main container with padding
        container = ctk.CTkFrame(self)
        container.pack(fill="both", expand=True, padx=PADDING["large"], pady=PADDING["large"])

        # Title
        if self.first_run:
            title_text = "Welcome to Moria Manager"
            subtitle_text = "Let's configure your game installations"
        else:
            title_text = "Settings"
            subtitle_text = "Configure your installations and backup preferences"

        title = ctk.CTkLabel(container, text=title_text, font=FONTS["title"])
        title.pack(anchor="w", pady=(0, 5))

        subtitle = ctk.CTkLabel(container, text=subtitle_text, font=FONTS["body"], text_color="gray")
        subtitle.pack(anchor="w", pady=(0, PADDING["large"]))

        # Scrollable frame for content
        scroll_frame = ctk.CTkScrollableFrame(container, height=350)
        scroll_frame.pack(fill="both", expand=True, pady=(0, PADDING["medium"]))

        self._create_installation_section(scroll_frame)
        self._create_backup_settings_section(scroll_frame)

        # Buttons
        self._create_buttons(container)

    def _create_installation_section(self, parent):
        """Create the game installations section."""
        section = ctk.CTkFrame(parent)
        section.pack(fill="x", pady=(0, PADDING["large"]))

        header = ctk.CTkLabel(section, text="Game Installations", font=FONTS["heading"])
        header.pack(anchor="w", padx=PADDING["medium"], pady=PADDING["small"])

        desc = ctk.CTkLabel(
            section,
            text="Select which game versions you have installed:",
            font=FONTS["small"],
            text_color="gray"
        )
        desc.pack(anchor="w", padx=PADDING["medium"], pady=(0, PADDING["small"]))

        # Create row for each installation type
        for installation in self.config_manager.config.installations:
            self._create_installation_row(section, installation)

    def _create_installation_row(self, parent, installation):
        """Create a row for a single installation type."""
        row = ctk.CTkFrame(parent)
        row.pack(fill="x", padx=PADDING["medium"], pady=PADDING["small"])

        # Checkbox for enabling
        var = ctk.BooleanVar(value=installation.enabled)
        self.installation_vars[installation.id] = var

        cb = ctk.CTkCheckBox(
            row,
            text=installation.display_name,
            variable=var,
            font=FONTS["body"],
            command=lambda inst=installation: self._on_installation_toggle(inst.id),
        )
        cb.pack(anchor="w")

        # Path selector for save path
        path_frame = ctk.CTkFrame(row, fg_color="transparent")
        path_frame.pack(fill="x", padx=(25, 0), pady=(5, 0))

        path_selector = PathSelector(
            path_frame,
            label="Save Path:",
            initial_path=installation.save_path,
            directory=True,
        )
        path_selector.pack(fill="x")
        self.path_selectors[installation.id] = path_selector

        # Status message
        if installation.id != InstallationType.CUSTOM:
            if installation.save_path and installation.save_path.exists():
                status_text = "Detected at default location"
                status_color = "green"
            else:
                status_text = "Not found at default location"
                status_color = "orange"

            status = ctk.CTkLabel(
                path_frame,
                text=status_text,
                font=FONTS["small"],
                text_color=status_color
            )
            status.pack(anchor="w", pady=(2, 0))

        # Enable/disable path selector based on checkbox
        path_selector.set_enabled(var.get())

    def _on_installation_toggle(self, inst_type: InstallationType):
        """Handle installation checkbox toggle."""
        enabled = self.installation_vars[inst_type].get()
        self.path_selectors[inst_type].set_enabled(enabled)

    def _create_backup_settings_section(self, parent):
        """Create the backup settings section."""
        section = ctk.CTkFrame(parent)
        section.pack(fill="x", pady=(0, PADDING["large"]))

        header = ctk.CTkLabel(section, text="Backup Settings", font=FONTS["heading"])
        header.pack(anchor="w", padx=PADDING["medium"], pady=PADDING["small"])

        # Backup location
        backup_frame = ctk.CTkFrame(section, fg_color="transparent")
        backup_frame.pack(fill="x", padx=PADDING["medium"], pady=PADDING["small"])

        self.backup_path_selector = PathSelector(
            backup_frame,
            label="Backup Location:",
            initial_path=self.config_manager.config.settings.backup_location or GamePaths.BACKUP_DEFAULT,
            directory=True,
        )
        self.backup_path_selector.pack(fill="x")

        # Max backups
        max_frame = ctk.CTkFrame(section, fg_color="transparent")
        max_frame.pack(fill="x", padx=PADDING["medium"], pady=PADDING["small"])

        max_label = ctk.CTkLabel(max_frame, text="Max Backups per Installation:", font=FONTS["body"])
        max_label.pack(side="left")

        self.max_backups_var = ctk.IntVar(value=self.config_manager.config.settings.max_backups_per_installation)
        self.max_backups_label = ctk.CTkLabel(max_frame, text=str(self.max_backups_var.get()), width=30)
        self.max_backups_label.pack(side="right", padx=(10, 0))

        self.max_backups_slider = ctk.CTkSlider(
            max_frame,
            from_=1,
            to=50,
            number_of_steps=49,
            variable=self.max_backups_var,
            command=self._on_slider_change,
        )
        self.max_backups_slider.pack(side="right", padx=10)

    def _on_slider_change(self, value):
        """Update the max backups label when slider changes."""
        self.max_backups_label.configure(text=str(int(value)))

    def _create_buttons(self, parent):
        """Create the dialog buttons."""
        button_frame = ctk.CTkFrame(parent, fg_color="transparent")
        button_frame.pack(fill="x", pady=(PADDING["medium"], 0))

        # Cancel button (not shown on first run)
        if not self.first_run:
            cancel_btn = ctk.CTkButton(
                button_frame,
                text="Cancel",
                width=100,
                fg_color="transparent",
                border_width=1,
                text_color=("gray10", "gray90"),
                command=self.destroy,
            )
            cancel_btn.pack(side="left")

        # Save button
        save_text = "Get Started" if self.first_run else "Save"
        save_btn = ctk.CTkButton(
            button_frame,
            text=save_text,
            width=120,
            command=self._save_and_close,
        )
        save_btn.pack(side="right")

    def _save_and_close(self):
        """Save configuration and close dialog."""
        # Update installation settings
        for installation in self.config_manager.config.installations:
            installation.enabled = self.installation_vars[installation.id].get()
            path = self.path_selectors[installation.id].get_path()
            if path:
                installation.save_path = path

        # Update backup settings
        backup_path = self.backup_path_selector.get_path()
        if backup_path:
            self.config_manager.config.settings.backup_location = backup_path

        self.config_manager.config.settings.max_backups_per_installation = int(self.max_backups_var.get())

        # Mark first run complete
        self.config_manager.config.settings.first_run_complete = True

        # Save to file
        self.config_manager.save()

        self.config_changed = True
        self.destroy()
