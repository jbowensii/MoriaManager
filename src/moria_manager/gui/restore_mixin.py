"""Restore mode mixin for MainWindow."""
# pylint: disable=broad-exception-caught
# Restore operations interact with servers via FTP/SFTP and the filesystem.
# Broad exception catches prevent GUI crashes from unexpected errors.

from __future__ import annotations

import shutil
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

import customtkinter as ctk

from ..config.paths import GamePaths
from ..core.backup_index import BackupIndexManager, BackupIndexEntry
from ..logging_config import get_logger
from .styles import FONTS, PADDING

logger = get_logger("restore_mixin")


class RestoreMixin:
    """Mixin that adds backup restore functionality to MainWindow.

    Provides a two-pane restore interface:
      - Left pane: lists backed-up worlds or characters read from the backup index.
      - Right pane: shows timestamped backup versions for the selected entry,
        with buttons to restore or delete individual snapshots.

    Restore targets can be either a local game installation or a remote server
    (via FTP/SFTP). When restoring locally, existing save files are preserved
    with a '.sav.pre_restore' suffix before being overwritten.

    Depends on attributes and methods provided by MainWindow and other mixins,
    including config_manager, current_installation, current_server,
    _server_ensure_connected, _server_upload_file, _show_confirm_dialog,
    _show_delete_confirm_dialog, _load_icon, _create_tooltip, _set_status,
    and _reset_scroll_if_few_items.
    """

    # --- Backup Entry List (Left Pane) ---

    def _refresh_restore_list(self):
        """Refresh the world/character list from backup index for restore mode.

        Reads the backup index for the current category (worlds or characters),
        removes stale entries pointing to missing directories, and populates
        the left pane with a sorted list of clickable entry rows.
        """
        # Clear existing items
        for widget in self.item_list_frame.winfo_children():
            widget.destroy()

        # Get backup root from config
        backup_root = (
            self.config_manager.config.settings.backup_location
            or GamePaths.BACKUP_DEFAULT
        )

        if not backup_root.exists():
            self.item_placeholder = ctk.CTkLabel(
                self.item_list_frame,
                text="Backup location does not exist",
                font=FONTS["body"],
                text_color="orange"
            )
            self.item_placeholder.pack(pady=PADDING["large"])
            self.item_count_label.configure(text="(0)")
            return

        # Determine category based on view type
        category = "worlds" if self.current_view_type == "Worlds" else "characters"

        # Get index entries
        try:
            index_manager = BackupIndexManager(backup_root, category)
            # Clean up stale entries (missing or empty directories) before listing
            index_manager.cleanup_stale_entries()
            self.restore_entries = index_manager.list_entries()
        except (OSError, ET.ParseError, ValueError) as e:
            self.item_placeholder = ctk.CTkLabel(
                self.item_list_frame,
                text=f"Error reading backups: {e}",
                font=FONTS["body"],
                text_color="red"
            )
            self.item_placeholder.pack(pady=PADDING["large"])
            self.item_count_label.configure(text="(0)")
            return

        self.item_count_label.configure(text=f"({len(self.restore_entries)})")

        if not self.restore_entries:
            empty_message = (
                "No world backups found"
                if category == "worlds"
                else "No character backups found")
            self.item_placeholder = ctk.CTkLabel(
                self.item_list_frame,
                text=empty_message,
                font=FONTS["body"],
                text_color="gray"
            )
            self.item_placeholder.pack(pady=PADDING["large"])
            return

        # Create row for each entry
        for entry in sorted(self.restore_entries, key=lambda e: e.display_name.lower()):
            self._create_restore_entry_row(entry, index_manager)

        # Reset scroll to top if few items
        self._reset_scroll_if_few_items(self.item_list_frame)

    def _create_restore_entry_row(
        self, entry: BackupIndexEntry,
        index_manager: 'BackupIndexManager' = None
    ):
        """Create a clickable row for a backup index entry in restore mode.

        Each row shows the display name and filename. Entries with zero
        remaining backup snapshots get a yellow warning border. If deletion
        is enabled in settings, a trash icon is placed on the right side.
        """
        # Check if entry has any backups
        has_backups = True
        if index_manager:
            timestamps = index_manager.get_backup_timestamps(entry)
            has_backups = len(timestamps) > 0

        # Yellow (#ffc107) border visually warns that the index entry exists
        # but all backup snapshots have been deleted
        if has_backups:
            row = ctk.CTkFrame(self.item_list_frame, cursor="hand2")
        else:
            row = ctk.CTkFrame(self.item_list_frame, cursor="hand2",
                              border_width=2, border_color="#ffc107")
        row.pack(fill="x", pady=2)

        # Make the whole row clickable
        row.bind("<Button-1>", lambda e, ent=entry: self._on_restore_entry_selected(ent))

        # Display name
        name_label = ctk.CTkLabel(row, text=entry.display_name, font=FONTS["body"], anchor="w")
        name_label.pack(fill="x", padx=PADDING["small"], pady=(PADDING["small"], 0))
        name_label.bind("<Button-1>", lambda e, ent=entry: self._on_restore_entry_selected(ent))

        # Filename (smaller, gray)
        filename_label = ctk.CTkLabel(
            row, text=entry.filename,
            font=FONTS["small"], text_color="gray", anchor="w"
        )
        filename_label.pack(fill="x", padx=PADDING["small"], pady=(0, PADDING["small"]))
        filename_label.bind("<Button-1>", lambda e, ent=entry: self._on_restore_entry_selected(ent))

        # Add tooltip for entries with no backups
        if not has_backups:
            self._create_tooltip(row, "No backups remaining")

        # Trash button is only shown when the user has opted into deletion via settings
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
                    command=lambda ent=entry: self._prompt_delete_restore_entry(ent)
                )
                trash_btn.place(relx=1.0, rely=0.5, anchor="e", x=-PADDING["small"])
                self._create_tooltip(trash_btn, "Delete All Backups")

    # --- Entry Selection Handlers ---

    def _on_restore_entry_selected(self, entry: BackupIndexEntry):
        """Handle backup entry selection in restore mode.

        Highlights the selected row in the left pane by matching both
        display_name and filename (since different files can share the
        same display name), then refreshes the right-pane timestamp list.
        """
        self.selected_restore_entry = entry

        # Highlight selected item - use both display_name and filename for unique matching
        for widget in self.item_list_frame.winfo_children():
            if isinstance(widget, ctk.CTkFrame):
                children = widget.winfo_children()
                # Check both display_name (first label) and filename
                # (second label) to handle duplicates
                if len(children) >= 2:
                    display_name_match = children[0].cget("text") == entry.display_name
                    filename_match = children[1].cget("text") == entry.filename
                    is_selected = display_name_match and filename_match
                else:
                    is_selected = False
                # Color tuples are (light_mode, dark_mode) theme values
                widget.configure(fg_color=("gray85", "gray25") if is_selected
                               else ("gray95", "gray17"))

        # Refresh timestamps pane
        self._refresh_restore_timestamps()

        self._set_status(f"Selected backup: {entry.display_name} ({entry.filename})")

    # --- Backup Timestamp List (Right Pane) ---

    def _refresh_restore_timestamps(self):
        """Refresh the timestamp list for the selected backup entry.

        Populates the right pane with one row per timestamped backup snapshot
        for the currently selected world/character entry. Each timestamp
        directory follows the naming convention YYYY-MM-DD_HHMMSS.
        """
        # Clear existing items
        for widget in self.versions_list_frame.winfo_children():
            widget.destroy()
        self.version_rows.clear()
        self.selected_restore_timestamp = None

        item_type = "world" if self.current_view_type == "Worlds" else "character"

        if not self.selected_restore_entry:
            self.versions_placeholder = ctk.CTkLabel(
                self.versions_list_frame,
                text=f"Select a {item_type}\nfrom the left",
                font=FONTS["body"],
                text_color="gray",
                justify="center"
            )
            self.versions_placeholder.pack(pady=PADDING["large"])
            self.versions_header.configure(text="Backup Versions")
            self.versions_count_label.configure(text="(0)")
            return

        # Get backup root from config
        backup_root = (
            self.config_manager.config.settings.backup_location
            or GamePaths.BACKUP_DEFAULT
        )

        category = "worlds" if self.current_view_type == "Worlds" else "characters"

        try:
            index_manager = BackupIndexManager(backup_root, category)
            self.restore_timestamps = (
                index_manager.get_backup_timestamps(
                    self.selected_restore_entry))
        except (OSError, ET.ParseError, ValueError) as e:
            self.versions_placeholder = ctk.CTkLabel(
                self.versions_list_frame,
                text=f"Error: {e}",
                font=FONTS["body"],
                text_color="red"
            )
            self.versions_placeholder.pack(pady=PADDING["large"])
            return

        # Update header
        self.versions_header.configure(text=self.selected_restore_entry.display_name)
        self.versions_count_label.configure(text=f"({len(self.restore_timestamps)} backups)")

        if not self.restore_timestamps:
            self.versions_placeholder = ctk.CTkLabel(
                self.versions_list_frame,
                text="No backups found",
                font=FONTS["body"],
                text_color="gray"
            )
            self.versions_placeholder.pack(pady=PADDING["large"])
            return

        # Create row for each timestamp
        for timestamp_dir in self.restore_timestamps:
            self._create_restore_timestamp_row(timestamp_dir)

        # Reset scroll to top if few items
        self._reset_scroll_if_few_items(self.versions_list_frame)

    def _create_restore_timestamp_row(self, timestamp_dir: Path):
        """Create a clickable row for a backup timestamp directory.

        Converts the directory name from YYYY-MM-DD_HHMMSS format into a
        human-readable date/time string for display. Falls back to the raw
        directory name if parsing fails.
        """
        row = ctk.CTkFrame(self.versions_list_frame, cursor="hand2")
        row.pack(fill="x", pady=1)

        # Store reference for highlighting
        self.version_rows[timestamp_dir.name] = row

        # Make row clickable
        row.bind("<Button-1>", lambda e, ts=timestamp_dir: self._on_restore_timestamp_selected(ts))

        # Parse timestamp from directory name (format: YYYY-MM-DD_HHMMSS)
        try:
            dt = datetime.strptime(timestamp_dir.name, "%Y-%m-%d_%H%M%S")
            display_text = dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            display_text = timestamp_dir.name

        # Timestamp label
        name_label = ctk.CTkLabel(
            row, text=display_text,
            font=FONTS["body"], anchor="w"
        )
        name_label.pack(
            side="left", fill="x", expand=True,
            padx=PADDING["small"], pady=PADDING["small"])
        name_label.bind(
            "<Button-1>",
            lambda e, ts=timestamp_dir:
            self._on_restore_timestamp_selected(ts))

    def _on_restore_timestamp_selected(self, timestamp_dir: Path):
        """Handle timestamp selection in restore mode.

        Highlights the selected row and dynamically adds action buttons
        (restore and optionally delete) to it. Previously added buttons on
        other rows are destroyed first to keep only one set visible at a time.
        """
        self.selected_restore_timestamp = timestamp_dir

        # Update highlighting on all rows
        for dirname, row in self.version_rows.items():
            # Remove old action buttons so only the selected row has them
            for child in row.winfo_children():
                if isinstance(child, ctk.CTkButton):
                    child.destroy()

            is_selected = dirname == timestamp_dir.name
            row.configure(fg_color=("gray85", "gray25") if is_selected else ("gray95", "gray17"))

            if is_selected:
                # Add delete button if deletion is enabled
                if self.config_manager.config.settings.enable_deletion:
                    trash_image = self._load_icon("icons/trash.png", size=(16, 16))
                    if trash_image:
                        delete_btn = ctk.CTkButton(
                            row, image=trash_image, text="",
                            width=24, height=24,
                            fg_color="transparent",
                            hover_color=("#ffcccc", "#4a1a1a"),
                            command=lambda ts=timestamp_dir:
                            self._prompt_delete_backup_timestamp(ts)
                        )
                    else:
                        # Unicode fallback when icon image fails to load
                        delete_btn = ctk.CTkButton(
                            row, text="\U0001f5d1", width=24,
                            height=24, font=FONTS["small"],
                            text_color="red",
                            fg_color="transparent",
                            hover_color=("#ffcccc", "#4a1a1a"),
                            command=lambda ts=timestamp_dir:
                            self._prompt_delete_backup_timestamp(ts)
                        )
                    delete_btn.pack(side="right", padx=(0, PADDING["small"]))
                    self._create_tooltip(delete_btn, "Delete Backup")

                # Add restore button
                restore_image = self._load_icon("icons/restore_green.png", size=(16, 16))
                if restore_image:
                    restore_btn = ctk.CTkButton(
                        row, image=restore_image, text="", width=24, height=24,
                        fg_color="transparent", hover_color=("gray80", "gray30"),
                        command=lambda ts=timestamp_dir: self._restore_from_backup(ts)
                    )
                else:
                    # Unicode recycle symbol fallback when icon image fails to load
                    restore_btn = ctk.CTkButton(
                        row, text="\u267b", width=24, height=24,
                        font=FONTS["small"], text_color="green",
                        fg_color="transparent", hover_color=("gray80", "gray30"),
                        command=lambda ts=timestamp_dir: self._restore_from_backup(ts)
                    )
                restore_btn.pack(side="right", padx=PADDING["small"])
                self._create_tooltip(restore_btn, "Restore this backup")

        # Parse timestamp for status
        try:
            dt = datetime.strptime(timestamp_dir.name, "%Y-%m-%d_%H%M%S")
            display_text = dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            display_text = timestamp_dir.name

        self._set_status(f"Selected backup from {display_text}")

    # --- Restore Operations ---

    def _restore_from_backup(self, timestamp_dir: Path):
        """Restore a backup from the selected timestamp to the game save directory or server.

        Dispatches to _restore_from_backup_to_server when a server is active.
        For local restores, validates paths, prompts for overwrite confirmation
        when files already exist, creates .sav.pre_restore safety copies of
        existing saves, then copies the backup files into the save directory.
        """
        from ..config.path_validator import is_path_under_root, validate_save_path

        # Handle server restore
        if self.current_server:
            self._restore_from_backup_to_server(timestamp_dir)
            return

        if not self.current_installation or not self.current_installation.save_path:
            self._set_status("No installation selected")
            return

        if not self.selected_restore_entry:
            self._set_status("No backup selected")
            return

        # Validate save path before proceeding
        save_path = self.current_installation.save_path
        is_valid, error_msg = validate_save_path(save_path)
        if not is_valid:
            self._set_status(f"Invalid save path: {error_msg}")
            return

        try:
            # Get backup root
            backup_root = (
                self.config_manager.config.settings.backup_location
                or GamePaths.BACKUP_DEFAULT
            )

            # Validate backup directory is under backup root
            if not is_path_under_root(timestamp_dir, backup_root):
                self._set_status("Invalid backup directory")
                return

            category = "worlds" if self.current_view_type == "Worlds" else "characters"
            index_manager = BackupIndexManager(backup_root, category)

            # Get the backup files
            backup_files = index_manager.get_backup_files(timestamp_dir)

            if not backup_files:
                self._set_status("No backup files found in this directory")
                return

            # Check if any files already exist
            existing_files = []
            for backup_file in backup_files:
                dest_path = self.current_installation.save_path / backup_file.name
                if dest_path.exists():
                    existing_files.append(backup_file.name)

            # If files exist, ask for confirmation
            if existing_files:
                if len(existing_files) == 1:
                    message = (
                        f"The file '{existing_files[0]}' already "
                        "exists.\n\nDo you want to overwrite it?")
                else:
                    # Show at most 5 filenames to keep the dialog manageable
                    file_list = "\n".join(f"  - {f}" for f in existing_files[:5])
                    if len(existing_files) > 5:
                        file_list += f"\n  ... and {len(existing_files) - 5} more"
                    message = (
                        "The following files already exist:"
                        f"\n{file_list}\n\nDo you want to "
                        "overwrite them?")

                if not self._show_confirm_dialog("Confirm Overwrite", message):
                    self._set_status("Restore cancelled")
                    return

            # Restore each file
            restored_count = 0
            for backup_file in backup_files:
                # Destination is the game's save directory
                dest_path = self.current_installation.save_path / backup_file.name

                # Safety copy: preserve existing save so the user can recover
                # if the restored version turns out to be wrong
                if dest_path.exists():
                    backup_dest = dest_path.with_suffix(".sav.pre_restore")
                    shutil.copy2(dest_path, backup_dest)

                # Copy the backup file to the save directory
                shutil.copy2(backup_file, dest_path)
                restored_count += 1

            self._set_status(f"Restored {restored_count} file(s) from backup")

            # Refresh to show the restored files
            self._refresh_restore_timestamps()

        except (OSError, IOError, shutil.Error) as e:
            self._set_status(f"Restore failed: {e}")

    def _restore_from_backup_to_server(self, timestamp_dir: Path):
        """Restore a backup by uploading files to a remote server via FTP/SFTP.

        Validates the connection, uploads each backup file to the server's
        configured save path, and mirrors the files into the local server
        cache directory (if one exists) to keep it in sync.
        """
        from ..config.path_validator import is_path_under_root

        server = self.current_server
        server_name = server["name"]
        save_path = server.get("save_path", "")

        if not save_path:
            self._set_status("No server save path configured")
            return

        if not self.selected_restore_entry:
            self._set_status("No backup selected")
            return

        # Ensure connected
        if not self._server_ensure_connected(server):
            self._set_status(f"Cannot restore: not connected to {server_name}")
            return

        try:
            # Get backup root
            backup_root = (
                self.config_manager.config.settings.backup_location
                or GamePaths.BACKUP_DEFAULT
            )

            # Validate backup directory is under backup root
            if not is_path_under_root(timestamp_dir, backup_root):
                self._set_status("Invalid backup directory")
                return

            category = "worlds" if self.current_view_type == "Worlds" else "characters"
            index_manager = BackupIndexManager(backup_root, category)

            # Get the backup files
            backup_files = index_manager.get_backup_files(timestamp_dir)

            if not backup_files:
                self._set_status("No backup files found in this directory")
                return

            # Ask for confirmation
            if len(backup_files) == 1:
                message = f"Restore '{backup_files[0].name}' to server '{server_name}'?"
            else:
                message = f"Restore {len(backup_files)} file(s) to server '{server_name}'?"

            if not self._show_confirm_dialog("Confirm Server Restore", message):
                self._set_status("Restore cancelled")
                return

            self._set_status(f"Uploading to {server_name}...")
            self.update()

            # Upload each file to server
            restored_count = 0
            for backup_file in backup_files:
                # Build remote path, avoiding double slash if save_path already ends with /
                sep = "" if save_path.endswith("/") else "/"
                remote_path = (
                    f"{save_path}{sep}{backup_file.name}")

                if self._server_upload_file(server, str(backup_file), remote_path):
                    restored_count += 1
                    logger.info("Uploaded to server: %s", remote_path)

                    # Mirror to local cache so future reads don't re-download
                    if self._server_temp_save_path:
                        local_cache = self._server_temp_save_path / backup_file.name
                        shutil.copy2(backup_file, local_cache)

            self._set_status(f"Restored {restored_count} file(s) to {server_name}")

            # Refresh to show the restored files
            self._refresh_restore_timestamps()

        except Exception as e:
            logger.error("Restore to server failed: %s", e)
            self._set_status(f"Restore to server failed: {e}")

    # --- Deletion Operations ---

    def _prompt_delete_restore_entry(self, entry: BackupIndexEntry):
        """Prompt the user and, if confirmed, delete all backups for a world/character.

        Removes the entire backup directory tree for the entry and also
        removes its record from the backup index XML file. Both panes
        are refreshed afterward.
        """
        display_name = entry.display_name
        item_type = "world" if self.current_view_type == "Worlds" else "character"

        # Show confirmation dialog
        if not self._show_delete_confirm_dialog(
                f"all backups for '{display_name}'",
                f"{item_type} backups"):
            return

        # Get backup root from config
        backup_root = (
            self.config_manager.config.settings.backup_location
            or GamePaths.BACKUP_DEFAULT
        )

        category = "worlds" if self.current_view_type == "Worlds" else "characters"

        try:
            index_manager = BackupIndexManager(backup_root, category)
            # Derive the on-disk directory name from the display name using the
            # same sanitization the index manager used when creating it
            safe_name = index_manager._sanitize_dirname(entry.display_name)
            item_dir = index_manager.category_dir / safe_name

            if item_dir.exists():
                shutil.rmtree(item_dir)
                logger.info("Deleted backup directory: %s", item_dir)

                # Remove from index
                if entry.filename in index_manager._entries:
                    del index_manager._entries[entry.filename]
                    index_manager._save_index()

                self._set_status(f"Deleted all backups for '{display_name}'")
            else:
                self._set_status(f"Backup directory not found for '{display_name}'")

            # Refresh both panes - left (entries) and right (timestamps)
            self.selected_restore_entry = None
            self._refresh_restore_list()
            self._refresh_restore_timestamps()

        except (OSError, IOError) as e:
            logger.error("Error deleting backups for %s: %s", display_name, e)
            self._set_status(f"Error deleting backups: {e}")

    def _prompt_delete_backup_timestamp(self, timestamp_dir: Path):
        """Prompt the user and, if confirmed, delete a single backup snapshot.

        After deletion, refreshes both panes so the timestamp disappears
        from the right pane and the left pane updates its yellow-border
        status if the entry now has zero remaining backups.
        """
        # Parse timestamp for display
        try:
            dt = datetime.strptime(timestamp_dir.name, "%Y-%m-%d_%H%M%S")
            display_text = dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            display_text = timestamp_dir.name

        # Show confirmation dialog
        if not self._show_delete_confirm_dialog(f"backup from {display_text}", "backup"):
            return

        try:
            if timestamp_dir.exists():
                shutil.rmtree(timestamp_dir)
                logger.info("Deleted backup timestamp: %s", timestamp_dir)
                self._set_status(f"Deleted backup from {display_text}")
            else:
                self._set_status(f"Backup not found: {display_text}")

            # Refresh the timestamps list, keeping the current entry selected
            self._refresh_restore_timestamps()

            # Refresh the left pane too so yellow-border status updates
            # if this was the last backup for the entry. Save and restore
            # the current selection so the user stays on the same entry.
            current_entry = self.selected_restore_entry
            self._refresh_restore_list()
            if current_entry:
                self._on_restore_entry_selected(current_entry)

        except (OSError, IOError) as e:
            logger.error("Error deleting backup %s: %s", timestamp_dir, e)
            self._set_status(f"Error deleting backup: {e}")
