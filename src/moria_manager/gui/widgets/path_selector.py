"""Reusable path selection widget"""

from pathlib import Path
from tkinter import filedialog
from typing import Callable, Optional

import customtkinter as ctk


class PathSelector(ctk.CTkFrame):
    """A widget for selecting file or directory paths.

    Combines a text entry field with a browse button that opens
    a file dialog for path selection.
    """

    def __init__(
        self,
        master,
        label: str = "Path:",
        initial_path: Optional[Path] = None,
        directory: bool = True,
        on_change: Optional[Callable[[Path], None]] = None,
        **kwargs
    ):
        """Initialize the path selector widget.

        Args:
            master: Parent widget
            label: Label text to display
            initial_path: Initial path value
            directory: If True, select directories; if False, select files
            on_change: Callback function when path changes
            **kwargs: Additional arguments for CTkFrame
        """
        super().__init__(master, **kwargs)

        self.directory = directory
        self.on_change = on_change

        # Configure grid
        self.grid_columnconfigure(1, weight=1)

        # Label
        self.label = ctk.CTkLabel(self, text=label)
        self.label.grid(row=0, column=0, padx=(0, 10), sticky="w")

        # Path entry
        self.path_var = ctk.StringVar(value=str(initial_path) if initial_path else "")
        self.entry = ctk.CTkEntry(
            self,
            textvariable=self.path_var,
            width=350,
        )
        self.entry.grid(row=0, column=1, padx=(0, 10), sticky="ew")

        # Bind entry changes
        self.path_var.trace_add("write", self._on_entry_change)

        # Browse button
        self.browse_btn = ctk.CTkButton(
            self,
            text="Browse",
            width=80,
            command=self._browse,
        )
        self.browse_btn.grid(row=0, column=2, sticky="e")

        # Status indicator
        self.status_label = ctk.CTkLabel(self, text="", width=20)
        self.status_label.grid(row=0, column=3, padx=(5, 0))

        # Update status for initial path
        self._update_status()

    def _browse(self):
        """Open file dialog to select path."""
        initial_dir = None
        current_path = self.get_path()
        if current_path and current_path.exists():
            initial_dir = str(current_path if current_path.is_dir() else current_path.parent)

        if self.directory:
            selected = filedialog.askdirectory(
                initialdir=initial_dir,
                title="Select Directory",
            )
        else:
            selected = filedialog.askopenfilename(
                initialdir=initial_dir,
                title="Select File",
            )

        if selected:
            self.set_path(Path(selected))

    def _on_entry_change(self, *args):
        """Handle entry text changes."""
        self._update_status()
        if self.on_change:
            path = self.get_path()
            if path:
                self.on_change(path)

    def _update_status(self):
        """Update the status indicator based on path validity."""
        path = self.get_path()
        if path and path.exists():
            self.status_label.configure(text="OK", text_color="green")
        elif path:
            self.status_label.configure(text="?", text_color="orange")
        else:
            self.status_label.configure(text="", text_color="gray")

    def get_path(self) -> Optional[Path]:
        """Get the current path value.

        Returns:
            Path object or None if empty
        """
        value = self.path_var.get().strip()
        return Path(value) if value else None

    def set_path(self, path: Optional[Path]):
        """Set the path value.

        Args:
            path: Path to set, or None to clear
        """
        self.path_var.set(str(path) if path else "")
        self._update_status()

    def set_enabled(self, enabled: bool):
        """Enable or disable the widget.

        Args:
            enabled: True to enable, False to disable
        """
        state = "normal" if enabled else "disabled"
        self.entry.configure(state=state)
        self.browse_btn.configure(state=state)
