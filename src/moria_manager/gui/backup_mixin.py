"""Backup mode mixin for MainWindow."""
# pylint: disable=broad-exception-caught
# Backup operations interact with servers via FTP/SFTP and the filesystem.
# Broad exception catches prevent GUI crashes from unexpected errors.

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

import customtkinter as ctk

from ..config.paths import GamePaths
from ..core.backup_index import BackupIndexManager
from ..core.save_parser import WorldWithVersions, CharacterWithVersions, SaveFileVersion
from ..logging_config import get_logger
from .styles import COLORS, FONTS, PADDING, THEME_COLORS

logger = get_logger("backup_mixin")


class BackupMixin:
    """Backup mode operations for MainWindow.

    Provides the Backup tab functionality: listing worlds/characters from
    local installations or remote servers, displaying file versions,
    and performing backup/restore/delete operations on save files.

    The left pane shows worlds or characters; selecting one populates the
    right pane with all file versions (main .sav, .fresh, .bak, .bad).
    """

    # --- Item List (Left Pane) ---

    def _refresh_item_list(self):
        """Refresh the world/character list for the current installation or server."""
        # Clear existing items
        for widget in self.item_list_frame.winfo_children():
            widget.destroy()

        # Check if a server is selected
        if self.current_server:
            self._refresh_item_list_from_server()
            return

        if not self.current_installation or not self.current_installation.save_path:
            self.item_placeholder = ctk.CTkLabel(
                self.item_list_frame,
                text="No save path configured",
                font=FONTS["body"],
                text_color="gray"
            )
            self.item_placeholder.pack(pady=PADDING["large"])
            self.item_count_label.configure(text="(0)")
            self._update_backup_button_states()
            return

        if not self.current_installation.save_path.exists():
            self.item_placeholder = ctk.CTkLabel(
                self.item_list_frame,
                text="Save path does not exist",
                font=FONTS["body"],
                text_color="orange"
            )
            self.item_placeholder.pack(pady=PADDING["large"])
            self.item_count_label.configure(text="(0)")
            self._update_backup_button_states()
            return

        # Get data based on view type
        if self.current_view_type == "Worlds":
            self.worlds_data = self.parser.get_worlds_with_versions(
                self.current_installation.save_path)
            items = self.worlds_data
            empty_message = "No world saves found"
        else:
            self.characters_data = (
                self.parser.get_characters_with_versions(
                    self.current_installation.save_path))
            items = self.characters_data
            empty_message = "No character saves found"

        self.item_count_label.configure(text=f"({len(items)})")

        if not items:
            self.item_placeholder = ctk.CTkLabel(
                self.item_list_frame,
                text=empty_message,
                font=FONTS["body"],
                text_color="gray"
            )
            self.item_placeholder.pack(pady=PADDING["large"])
            self._update_backup_button_states()
            return

        # Create row for each item
        for item in items:
            self._create_item_row(item)

        # Update button states after loading items
        self._update_backup_button_states()

        # Reset scroll to top if few items
        self._reset_scroll_if_few_items(self.item_list_frame)

    def _refresh_item_list_from_server(self):
        """Refresh the world/character list from a remote server."""
        import os

        server = self.current_server
        server_name = server["name"]
        save_path = server.get("save_path", "")
        protocol = server.get("protocol", "FTP")

        logger.debug(
            "_refresh_item_list_from_server: server=%s, protocol=%s, save_path='%s'",
            server_name, protocol, save_path
        )

        # Check for save path
        if not save_path:
            self.item_placeholder = ctk.CTkLabel(
                self.item_list_frame,
                text="No Save File Location configured for server",
                font=FONTS["body"],
                text_color="orange"
            )
            self.item_placeholder.pack(pady=PADDING["large"])
            self.item_count_label.configure(text="(0)")
            self._update_backup_button_states()
            return

        # Ensure server is connected
        if not self._server_ensure_connected(server):
            self.item_placeholder = ctk.CTkLabel(
                self.item_list_frame,
                text=f"Cannot connect to {server_name}",
                font=FONTS["body"],
                text_color="red"
            )
            self.item_placeholder.pack(pady=PADDING["large"])
            self.item_count_label.configure(text="(0)")
            self._update_backup_button_states()
            return

        # Create/use temp directory in APPDATA for server saves
        appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
        temp_dir = Path(appdata) / "MoriaManager" / "server_cache" / server_name
        temp_dir.mkdir(parents=True, exist_ok=True)

        # Clear old files in temp dir
        for f in temp_dir.iterdir():
            try:
                if f.is_file():
                    f.unlink()
            except OSError:
                pass

        self._set_status(f"Downloading saves from {server_name}...")
        self.update()  # Force UI update

        # List and download ALL files from save directory
        try:
            all_files = self._server_list_files(server, save_path, "*")

            if not all_files:
                self.item_placeholder = ctk.CTkLabel(
                    self.item_list_frame,
                    text="No files found on server",
                    font=FONTS["body"],
                    text_color="gray"
                )
                self.item_placeholder.pack(pady=PADDING["large"])
                self.item_count_label.configure(text="(0)")
                self._set_status(f"No files found on {server_name}")
                self._update_backup_button_states()
                return

            # Download each file
            downloaded = 0
            for filename in all_files:
                sep = "" if save_path.endswith("/") else "/"
                remote_file = f"{save_path}{sep}{filename}"
                local_file = str(temp_dir / filename)
                if self._server_download_file(server, remote_file, local_file):
                    downloaded += 1

            self._set_status(f"Downloaded {downloaded} files from {server_name}")

        except Exception as e:
            logger.error("Error downloading from server %s: %s", server_name, e)
            self.item_placeholder = ctk.CTkLabel(
                self.item_list_frame,
                text=f"Error: {e}",
                font=FONTS["body"],
                text_color="red"
            )
            self.item_placeholder.pack(pady=PADDING["large"])
            self.item_count_label.configure(text="(0)")
            self._update_backup_button_states()
            return

        # Store the temp path for later operations (backup/restore)
        self._server_temp_save_path = temp_dir

        # Parse and display - use temp_dir as save path
        if self.current_view_type == "Worlds":
            self.worlds_data = self.parser.get_worlds_with_versions(temp_dir)
            items = self.worlds_data
            empty_message = "No world saves found"
        else:
            self.characters_data = self.parser.get_characters_with_versions(temp_dir)
            items = self.characters_data
            empty_message = "No character saves found"

        self.item_count_label.configure(text=f"({len(items)})")

        if not items:
            self.item_placeholder = ctk.CTkLabel(
                self.item_list_frame,
                text=empty_message,
                font=FONTS["body"],
                text_color="gray"
            )
            self.item_placeholder.pack(pady=PADDING["large"])
            self._update_backup_button_states()
            return

        # Create row for each item
        for item in items:
            self._create_item_row(item)

        # Update button states after loading items
        self._update_backup_button_states()

        # Reset scroll to top if few items
        self._reset_scroll_if_few_items(self.item_list_frame)

    # --- Item Row Creation ---

    def _create_item_row(self, item: WorldWithVersions | CharacterWithVersions):
        """Create a clickable row for a world or character in the left pane."""
        # Check if this world/character has a main .sav file
        has_main_file = item.main_file is not None

        # Yellow border for items without a .sav file
        if not has_main_file:
            row = ctk.CTkFrame(
                self.item_list_frame,
                cursor="hand2",
                border_width=2,
                border_color=COLORS["warning"]
            )
        else:
            row = ctk.CTkFrame(self.item_list_frame, cursor="hand2")
        row.pack(fill="x", pady=2)

        # Add tooltip for items without main SAV file
        if not has_main_file:
            self._create_tooltip(row, "This file has no main SAV file")

        # Make the whole row clickable
        row.bind("<Button-1>", lambda e, i=item: self._on_item_selected(i))

        # Display name (world_name for worlds, display_name for characters)
        if isinstance(item, WorldWithVersions):
            display_name = item.world_name
        else:
            display_name = item.display_name

        name_label = ctk.CTkLabel(row, text=display_name, font=FONTS["body_bold"], anchor="w", text_color=THEME_COLORS["text"])
        name_label.pack(fill="x", padx=PADDING["small"], pady=(PADDING["small"], 0))
        name_label.bind("<Button-1>", lambda e, i=item: self._on_item_selected(i))

        # Filename (smaller, black in light mode)
        filename_label = ctk.CTkLabel(
            row, text=item.base_name,
            font=FONTS["small"], text_color=THEME_COLORS["text_secondary"], anchor="w"
        )
        filename_label.pack(fill="x", padx=PADDING["small"], pady=(0, PADDING["small"]))
        filename_label.bind("<Button-1>", lambda e, i=item: self._on_item_selected(i))

        # Version count badge - position depends on whether trash icon is shown
        version_count = len(item.versions)
        badge_x_offset = -PADDING["small"]

        # Add trash icon if deletion is enabled
        if self.config_manager.config.settings.enable_deletion:
            trash_image = self._load_icon("icons/trash.png", size=(18, 18))
            if trash_image:
                trash_btn = ctk.CTkButton(
                    row,
                    image=trash_image,
                    text="",
                    width=24,
                    height=24,
                    fg_color="transparent",
                    hover_color=("#ffcccc", "#4a1a1a"),
                    command=lambda i=item: self._prompt_delete_world(i)
                )
                trash_btn.place(relx=1.0, rely=0.5, anchor="e", x=-PADDING["small"])
                self._create_tooltip(trash_btn, "Delete All")
                # Move badge left to make room for trash icon
                badge_x_offset = -PADDING["small"] - 28

        badge = ctk.CTkLabel(
            row, text=f"{version_count} files",
            font=FONTS["small"], text_color="gray"
        )
        badge.place(relx=1.0, rely=0.5, anchor="e", x=badge_x_offset)
        badge.bind("<Button-1>", lambda e, i=item: self._on_item_selected(i))

    # --- Item Selection ---

    def _on_item_selected(self, item: WorldWithVersions | CharacterWithVersions):
        """Handle world/character selection — highlight row and populate versions pane."""
        self.selected_item = item

        # Get display name for status
        if isinstance(item, WorldWithVersions):
            display_name = item.world_name
        else:
            display_name = item.display_name

        # Highlight selected item (update background colors)
        for widget in self.item_list_frame.winfo_children():
            if isinstance(widget, ctk.CTkFrame):
                is_selected = (widget.winfo_children() and
                               widget.winfo_children()[0].cget("text") == display_name)
                widget.configure(fg_color=THEME_COLORS["list_row_selected"] if is_selected
                               else THEME_COLORS["list_row_default"])

        # Update button states
        self._update_backup_button_states()

        # Refresh versions pane
        self._refresh_versions_list()

        self._set_status(f"Selected: {display_name}")

    def _restore_selection_by_base_name(self, base_name: str):
        """Try to restore selection to an item with the given base name after refresh."""
        # Get the current items list
        if self.current_view_type == "Worlds":
            items = self.worlds_data
        else:
            items = self.characters_data

        # Find the item with matching base_name
        for item in items:
            if item.base_name == base_name:
                self._on_item_selected(item)
                return

        # If not found (world was completely deleted), clear selection
        self.selected_item = None
        self._refresh_versions_list()

    # --- Version List (Right Pane) ---

    def _refresh_versions_list(self):
        """Refresh the file versions list for the selected world/character."""
        # Clear existing items and tracking
        for widget in self.versions_list_frame.winfo_children():
            widget.destroy()
        self.version_rows.clear()
        self.selected_version = None

        item_type = "world" if self.current_view_type == "Worlds" else "character"

        if not self.selected_item:
            self.versions_placeholder = ctk.CTkLabel(
                self.versions_list_frame,
                text=f"Select a {item_type}\nfrom the left",
                font=FONTS["body"],
                text_color="gray",
                justify="center"
            )
            self.versions_placeholder.pack(pady=PADDING["large"])
            self.versions_header.configure(text="File Versions")
            self.versions_count_label.configure(text="(0)")
            return

        # Get display name
        if isinstance(self.selected_item, WorldWithVersions):
            display_name = self.selected_item.world_name
        else:
            display_name = self.selected_item.display_name

        # Update header
        self.versions_header.configure(text=display_name)
        self.versions_count_label.configure(text=f"({len(self.selected_item.versions)} files)")

        # Sort versions: main first, then fresh, then backups by number, then bad files
        sorted_versions = []
        if self.selected_item.main_file:
            sorted_versions.append(self.selected_item.main_file)
        if self.selected_item.fresh_file:
            sorted_versions.append(self.selected_item.fresh_file)
        sorted_versions.extend(self.selected_item.backup_files)

        # Add any "bad" or other files that aren't already included
        for version in self.selected_item.versions:
            if version not in sorted_versions:
                sorted_versions.append(version)

        # Create row for each version
        for version in sorted_versions:
            self._create_version_row(version)

        # Reset scroll to top if few items
        self._reset_scroll_if_few_items(self.versions_list_frame)

    def _create_version_row(self, version: SaveFileVersion):
        """Create a clickable row for a file version with restore button."""
        row = ctk.CTkFrame(self.versions_list_frame, cursor="hand2")
        row.pack(fill="x", pady=1)

        # Store reference for highlighting
        self.version_rows[version.filename] = row

        # Make row clickable
        row.bind("<Button-1>", lambda e, v=version: self._on_version_selected(v))

        # Version type/name
        name_label = ctk.CTkLabel(
            row, text=version.display_name,
            font=FONTS["body_bold"], anchor="w",
            text_color=THEME_COLORS["text"]
        )
        name_label.pack(
            side="left", fill="x", expand=True,
            padx=PADDING["small"], pady=PADDING["small"])
        name_label.bind("<Button-1>", lambda e, v=version: self._on_version_selected(v))

    def _on_version_selected(self, version: SaveFileVersion):
        """Handle version selection — highlight row and show action buttons.

        Action buttons shown depend on the file type:
        - Main .sav: "Mark Bad" button (renames to .XX.bad)
        - No main file: green "Restore" button (renames selected to .sav)
        - Other files: normal "Restore" button (copies over main .sav)
        - All files: "Delete" button (if deletion is enabled in settings)
        """
        self.selected_version = version

        # Check if there's a main .sav file for this item
        has_main_file = self.selected_item and self.selected_item.main_file is not None

        # Update highlighting on all rows
        for filename, row in self.version_rows.items():
            # Remove old buttons if present
            for child in row.winfo_children():
                if isinstance(child, ctk.CTkButton):
                    child.destroy()

            is_selected = filename == version.filename
            row.configure(fg_color=THEME_COLORS["list_row_selected"] if is_selected else THEME_COLORS["list_row_default"])

            if is_selected:
                # Add delete button if deletion is enabled (for any file type)
                if self.config_manager.config.settings.enable_deletion:
                    trash_image = self._load_icon("icons/trash.png", size=(16, 16))
                    if trash_image:
                        delete_btn = ctk.CTkButton(
                            row, image=trash_image, text="", width=24, height=24,
                            fg_color="transparent", hover_color=("#ffcccc", "#4a1a1a"),
                            command=lambda v=version: self._prompt_delete_single_file(v)
                        )
                    else:
                        delete_btn = ctk.CTkButton(
                            row, text="\U0001f5d1", width=24, height=24,
                            font=FONTS["small"], text_color="red",
                            fg_color="transparent", hover_color=("#ffcccc", "#4a1a1a"),
                            command=lambda v=version: self._prompt_delete_single_file(v)
                        )
                    delete_btn.pack(side="right", padx=(0, PADDING["small"]))
                    self._create_tooltip(delete_btn, "Delete File")

                if version.version_type == "main":
                    # Add "Mark Bad" button for main save file
                    mark_bad_image = self._load_icon("icons/mark_bad.png", size=(16, 16))
                    if mark_bad_image:
                        mark_bad_btn = ctk.CTkButton(
                            row, image=mark_bad_image, text="", width=24, height=24,
                            fg_color="transparent", hover_color=("gray80", "gray30"),
                            command=lambda v=version: self._mark_version_bad(v)
                        )
                    else:
                        # Fallback: red circle with slash
                        mark_bad_btn = ctk.CTkButton(
                            row, text="\U0001f6ab", width=24, height=24,
                            font=FONTS["small"], text_color="red",
                            fg_color="transparent", hover_color=("gray80", "gray30"),
                            command=lambda v=version: self._mark_version_bad(v)
                        )
                    mark_bad_btn.pack(side="right", padx=PADDING["small"])
                    self._create_tooltip(mark_bad_btn, "Mark Bad")
                elif not has_main_file:
                    # No main file exists - show green restore button to rename this file as .sav
                    restore_image = self._load_icon("icons/restore_green.png", size=(16, 16))
                    if restore_image:
                        restore_btn = ctk.CTkButton(
                            row, image=restore_image, text="", width=24, height=24,
                            fg_color="transparent", hover_color=("gray80", "gray30"),
                            command=lambda v=version: self._restore_as_main(v)
                        )
                    else:
                        # Fallback: green recycle symbol
                        restore_btn = ctk.CTkButton(
                            row, text="\u267b", width=24, height=24,
                            font=FONTS["small"], text_color="green",
                            fg_color="transparent", hover_color=("gray80", "gray30"),
                            command=lambda v=version: self._restore_as_main(v)
                        )
                    restore_btn.pack(side="right", padx=PADDING["small"])
                    self._create_tooltip(restore_btn, "Restore")
                else:
                    # Main file exists - show normal restore button (copy over main)
                    restore_image = self._load_icon("icons/restore.png", size=(16, 16))
                    if restore_image:
                        restore_btn = ctk.CTkButton(
                            row, image=restore_image, text="", width=24, height=24,
                            fg_color="transparent", hover_color=("gray80", "gray30"),
                            command=lambda v=version: self._restore_version(v)
                        )
                    else:
                        restore_btn = ctk.CTkButton(
                            row, text="\u21a9", width=24, height=24,
                            font=FONTS["small"],
                            command=lambda v=version: self._restore_version(v)
                        )
                    restore_btn.pack(side="right", padx=PADDING["small"])
                    self._create_tooltip(restore_btn, "Make this file the current save")

        self._set_status(f"Selected version: {version.display_name}")

    # --- File Operations (Restore / Mark Bad) ---

    def _restore_version(self, version: SaveFileVersion):
        """Restore the selected version as the current save (copies over existing main file).

        Creates a .sav.backup of the current main file first, then overwrites
        it with the selected version.
        """
        from ..config.path_validator import is_safe_path, is_path_under_root

        if not self.current_installation or not self.selected_item:
            self._set_status("No item selected")
            return

        try:
            # Get the main save file path
            main_file = self.selected_item.main_file
            if not main_file:
                self._set_status("No main save file found")
                return

            # Validate paths are safe
            save_path = self.current_installation.save_path
            if not save_path or not is_path_under_root(main_file.file_path, save_path):
                self._set_status("Invalid save path configuration")
                return

            if not is_safe_path(main_file.file_path, allowed_roots=[save_path]):
                self._set_status("Cannot operate on protected path")
                return

            # Backup current save first
            backup_path = main_file.file_path.with_suffix(".sav.backup")
            shutil.copy2(main_file.file_path, backup_path)

            # Copy selected version to main save
            shutil.copy2(version.file_path, main_file.file_path)

            self._set_status(f"Restored {version.display_name} as current save")
            self._refresh_versions_list()
        except (OSError, IOError, shutil.Error) as e:
            self._set_status(f"Restore failed: {e}")

    def _restore_as_main(self, version: SaveFileVersion):
        """Restore a file as the main save by renaming it to .sav.

        This is used when there's no main .sav file (e.g., after marking it bad).
        The file is renamed by removing everything after the first '.' and appending 'sav'.

        Example: MW_12345678.sav.00.bad -> MW_12345678.sav
        Example: MW_12345678.00.bak -> MW_12345678.sav
        """
        if not version.file_path.exists():
            self._set_status("File not found")
            return

        try:
            # Get base name by taking everything before the first '.'
            filename = version.file_path.name
            base_name = filename.split('.')[0]  # e.g., "MW_12345678"

            # Create the new .sav path
            new_path = version.file_path.parent / f"{base_name}.sav"

            # Check if target already exists (shouldn't happen, but be safe)
            if new_path.exists():
                self._set_status(f"Cannot restore: {new_path.name} already exists")
                return

            # Handle server rename
            if self.current_server:
                server = self.current_server
                save_path = server.get("save_path", "")
                if save_path:
                    sep = "" if save_path.endswith("/") else "/"
                    old_remote = f"{save_path}{sep}{filename}"
                    new_remote = (
                        f"{save_path}{sep}{base_name}.sav")

                    logger.debug(
                        "_restore_as_main: server=%s, old_remote='%s', new_remote='%s'",
                        server.get("name"), old_remote, new_remote
                    )

                    if self._server_rename_file(server, old_remote, new_remote):
                        # Also rename locally
                        version.file_path.rename(new_path)
                        self._set_status(f"Restored on server: {new_path.name}")
                    else:
                        self._set_status("Failed to restore on server")
                        return
            else:
                # Rename the file locally
                version.file_path.rename(new_path)
                self._set_status(f"Restored: {new_path.name}")

            # Refresh the lists to reflect the change
            self._refresh_item_list()
            # Re-select the item if possible
            if self.selected_item:
                # Find the item again by base_name
                items = (
                    self.worlds_data
                    if self.current_view_type == "Worlds"
                    else self.characters_data)
                for item in items:
                    if item.base_name == base_name:
                        self._on_item_selected(item)
                        return
            self._refresh_versions_list()
        except (OSError, IOError) as e:
            self._set_status(f"Restore failed: {e}")

    def _mark_version_bad(self, version: SaveFileVersion):
        """Mark the current save as bad by renaming it with .XX.bad suffix.

        The XX is a two-digit number starting at 00, incrementing until
        an unused filename is found.
        """
        if not version.file_path.exists():
            self._set_status("File not found")
            return

        try:
            filename = version.file_path.name

            # Find an unused .XX.bad suffix
            for i in range(100):
                bad_path = version.file_path.parent / f"{filename}.{i:02d}.bad"
                if not bad_path.exists():
                    # Handle server rename
                    if self.current_server:
                        server = self.current_server
                        save_path = server.get("save_path", "")
                        if save_path:
                            sep = ("" if save_path.endswith("/")
                                   else "/")
                            old_remote = (
                                f"{save_path}{sep}{filename}")
                            new_remote = (
                                f"{save_path}{sep}{filename}"
                                f".{i:02d}.bad")

                            if self._server_rename_file(server, old_remote, new_remote):
                                # Also rename locally
                                version.file_path.rename(bad_path)
                                self._set_status(f"Marked as bad on server: {bad_path.name}")
                            else:
                                self._set_status("Failed to mark as bad on server")
                                return
                    else:
                        # Rename the file locally
                        version.file_path.rename(bad_path)
                        self._set_status(f"Marked as bad: {bad_path.name}")

                    # Refresh the lists to reflect the change
                    self._refresh_item_list()
                    self.selected_item = None
                    self._refresh_versions_list()
                    return

            self._set_status("Could not mark as bad: too many bad files")
        except (OSError, IOError) as e:
            self._set_status(f"Mark bad failed: {e}")

    # --- Button State Management ---

    def _update_backup_button_states(self):
        """Update the enabled/disabled state of backup buttons based on selection."""
        has_items = bool(
            (self.current_view_type == "Worlds" and self.worlds_data) or
            (self.current_view_type == "Characters" and self.characters_data)
        )
        has_selection = self.selected_item is not None

        # Backup button: only enabled if an item is selected
        if has_selection:
            self.backup_btn.configure(state="normal")
        else:
            self.backup_btn.configure(state="disabled")

        # Backup All button: enabled if there are any items to backup
        if has_items:
            self.backup_all_btn.configure(state="normal")
        else:
            self.backup_all_btn.configure(state="disabled")

    # --- Backup Operations ---

    def _backup_selected_item(self):
        """Backup the currently selected world/character's main .sav file."""
        # Check for either installation or server
        if not self.current_installation and not self.current_server:
            self._set_status("No installation or server selected")
            return

        if not self.selected_item:
            self._set_status("No item selected")
            return

        try:
            if isinstance(self.selected_item, WorldWithVersions):
                item_name = self.selected_item.world_name
                main_file = self.selected_item.main_file
            else:
                item_name = self.selected_item.display_name
                main_file = self.selected_item.main_file

            if not main_file:
                self._set_status(f"No main save file found for {item_name}")
                return

            # Create backup of just this one item
            backup_path = self._create_single_item_backup(main_file, item_name)
            if backup_path:
                self._set_status(f"Backup created: {backup_path.name}")
            else:
                self._set_status(f"Backup failed for {item_name}")
        except (OSError, IOError, shutil.Error) as e:
            self._set_status(f"Backup failed: {e}")

    def _backup_all_items(self):
        """Backup all worlds or characters for current installation or server."""
        # Check for either installation or server
        if not self.current_installation and not self.current_server:
            self._set_status("No installation or server selected")
            return

        try:
            # Get all items based on view type
            if self.current_view_type == "Worlds":
                items = self.worlds_data
                item_type = "worlds"
            else:
                items = self.characters_data
                item_type = "characters"

            if not items:
                self._set_status(f"No {item_type} to backup")
                return

            # Backup each item
            backed_up = 0
            for item in items:
                if isinstance(item, WorldWithVersions):
                    item_name = item.world_name
                else:
                    item_name = item.display_name

                main_file = item.main_file
                if main_file:
                    backup_path = self._create_single_item_backup(main_file, item_name)
                    if backup_path:
                        backed_up += 1

            self._set_status(f"Backed up {backed_up} of {len(items)} {item_type}")
        except (OSError, IOError, shutil.Error) as e:
            self._set_status(f"Backup failed: {e}")

    def _create_single_item_backup(self, main_file, item_name: str):
        """Create a backup of a single save file using the index-based structure.

        Args:
            main_file: The SaveFileVersion for the main save file
            item_name: Display name (world name or character name)

        Returns:
            Path to backup file if successful, None otherwise
        """
        # Must have either installation or server selected
        if not self.current_installation and not self.current_server:
            return None

        try:
            # Get backup root from config, or use default
            backup_root = (
                self.config_manager.config.settings.backup_location
                or GamePaths.BACKUP_DEFAULT
            )

            # Determine category based on view type
            category = "worlds" if self.current_view_type == "Worlds" else "characters"

            # Get or create the backup directory using the index manager
            index_manager = BackupIndexManager(backup_root, category)
            base_filename = main_file.file_path.stem  # e.g., "MW_12345678"
            item_backup_dir = index_manager.get_backup_directory(base_filename, item_name)

            # Use the file's modification timestamp (not wall clock) so duplicate
            # backups of the same unmodified file are detected and skipped
            file_mtime = main_file.file_path.stat().st_mtime
            file_datetime = datetime.fromtimestamp(file_mtime)
            timestamp_dir_name = file_datetime.strftime("%Y-%m-%d_%H%M%S")

            # Create timestamp subdirectory
            timestamp_dir = item_backup_dir / timestamp_dir_name
            timestamp_dir.mkdir(parents=True, exist_ok=True)

            # Backup filename is just the original filename
            backup_path = timestamp_dir / main_file.file_path.name

            # Check if this exact backup already exists
            if backup_path.exists():
                self._set_status(f"Backup already exists for {item_name} at {timestamp_dir_name}")
                return backup_path

            # Copy the file
            shutil.copy2(main_file.file_path, backup_path)
            return backup_path
        except (OSError, IOError, shutil.Error) as e:
            logger.error("Backup error for %s: %s", item_name, e)
            return None

    # --- Delete Operations ---

    def _prompt_delete_world(self, item: 'WorldWithVersions | CharacterWithVersions'):
        """Prompt to delete a world/character and ALL of its files (all versions)."""
        # Get display name and item type
        if isinstance(item, WorldWithVersions):
            display_name = item.world_name
            item_type = "world"
        else:
            display_name = item.display_name
            item_type = "character"

        # Show confirmation dialog
        if not self._show_delete_confirm_dialog(display_name, item_type):
            return

        # Handle server deletion
        if self.current_server:
            self._delete_world_on_server(item, display_name)
            return

        # Get the save directory for local installation
        if not self.current_installation or not self.current_installation.save_path:
            self._set_status("Cannot delete: no save path configured")
            return

        save_dir = self.current_installation.save_path
        base_name = item.base_name  # e.g., "MW_ABC123" or "MC_DEF456"

        # Find and delete all files matching the base name with any extension
        deleted_count = 0
        try:
            for file_path in save_dir.iterdir():
                if file_path.is_file() and file_path.name.startswith(base_name):
                    file_path.unlink()
                    deleted_count += 1
                    logger.info("Deleted: %s", file_path)

            if deleted_count > 0:
                self._set_status(f"Deleted {deleted_count} files for '{display_name}'")
            else:
                self._set_status(f"No files found to delete for '{display_name}'")

            # Clear selection and refresh both panes
            self.selected_item = None
            self._refresh_item_list()
            self._refresh_versions_list()

        except (OSError, IOError) as e:
            logger.error("Error deleting files for %s: %s", display_name, e)
            self._set_status(f"Error deleting files: {e}")

    def _delete_world_on_server(
        self,
        item: 'WorldWithVersions | CharacterWithVersions',
        display_name: str
    ):
        """Delete a world/character and all its files on the remote server."""
        server = self.current_server
        server_name = server["name"]
        save_path = server.get("save_path", "")
        base_name = item.base_name
        protocol = server.get("protocol", "FTP")

        logger.debug(
            "_delete_world_on_server: server=%s, protocol=%s, save_path='%s', base_name='%s'",
            server_name, protocol, save_path, base_name
        )

        if not save_path:
            self._set_status("Cannot delete: no server save path configured")
            return

        # Ensure connected
        if not self._server_ensure_connected(server):
            self._set_status(f"Cannot delete: not connected to {server_name}")
            return

        self._set_status(f"Deleting files on {server_name}...")
        self.update()

        # List all files on server and delete matching ones
        try:
            all_files = self._server_list_files(server, save_path, "*")
            deleted_count = 0

            for filename in all_files:
                if filename.startswith(base_name):
                    sep = ("" if save_path.endswith("/")
                           else "/")
                    remote_file = (
                        f"{save_path}{sep}{filename}")
                    if self._server_delete_file(server, remote_file):
                        deleted_count += 1
                        logger.info(
                            "Deleted on server: %s",
                            remote_file)

                    # Also delete from local cache
                    if self._server_temp_save_path:
                        local_file = self._server_temp_save_path / filename
                        if local_file.exists():
                            local_file.unlink()

            if deleted_count > 0:
                self._set_status(
                    f"Deleted {deleted_count} files for "
                    f"'{display_name}' on {server_name}")
            else:
                self._set_status(f"No files found to delete for '{display_name}'")

            # Clear selection and refresh both panes
            self.selected_item = None
            self._refresh_item_list()
            self._refresh_versions_list()

        except Exception as e:
            logger.error("Error deleting files on server for %s: %s", display_name, e)
            self._set_status(f"Error deleting on server: {e}")

    def _prompt_delete_single_file(self, version: 'SaveFileVersion'):
        """Prompt to delete a single file from the versions pane."""
        filename = version.filename

        # Show confirmation dialog
        if not self._show_delete_confirm_dialog(filename, "file"):
            return

        # Remember the current selection to restore it after refresh
        current_item_base_name = self.selected_item.base_name if self.selected_item else None

        # Handle server deletion
        if self.current_server:
            self._delete_single_file_on_server(version, filename, current_item_base_name)
            return

        # Delete the file locally
        try:
            if version.file_path.exists():
                version.file_path.unlink()
                logger.info("Deleted: %s", version.file_path)
                self._set_status(f"Deleted '{filename}'")

                # Refresh the lists and restore selection
                self._refresh_item_list()

                # Try to restore selection to the same world/character
                if current_item_base_name:
                    self._restore_selection_by_base_name(current_item_base_name)
            else:
                self._set_status(f"File not found: '{filename}'")

        except (OSError, IOError) as e:
            logger.error("Error deleting file %s: %s", filename, e)
            self._set_status(f"Error deleting file: {e}")

    def _delete_single_file_on_server(
        self, version: 'SaveFileVersion',
        filename: str, current_item_base_name: str
    ):
        """Delete a single file on the remote server."""
        server = self.current_server
        server_name = server["name"]
        save_path = server.get("save_path", "")

        if not save_path:
            self._set_status("Cannot delete: no server save path configured")
            return

        # Ensure connected
        if not self._server_ensure_connected(server):
            self._set_status(f"Cannot delete: not connected to {server_name}")
            return

        try:
            # Build remote path
            sep = "" if save_path.endswith("/") else "/"
            remote_file = f"{save_path}{sep}{filename}"

            if self._server_delete_file(server, remote_file):
                logger.info("Deleted on server: %s", remote_file)
                self._set_status(f"Deleted '{filename}' on {server_name}")

                # Also delete from local cache
                if version.file_path.exists():
                    version.file_path.unlink()

                # Refresh the lists and restore selection
                self._refresh_item_list()

                if current_item_base_name:
                    self._restore_selection_by_base_name(current_item_base_name)
            else:
                self._set_status(f"Failed to delete '{filename}' on server")

        except Exception as e:
            logger.error("Error deleting file on server %s: %s", filename, e)
            self._set_status(f"Error deleting on server: {e}")
