"""Mods mode mixin for MainWindow."""
# pylint: disable=broad-exception-caught
# Mod operations interact with servers via FTP/SFTP and the filesystem.
# Broad exception catches prevent GUI crashes from unexpected errors.

from __future__ import annotations

import tkinter as tk
from pathlib import Path

try:
    import tkinterdnd2
except ImportError:
    tkinterdnd2 = None  # type: ignore[assignment]

import customtkinter as ctk

from ..config.paths import GamePaths
from ..logging_config import get_logger
from .styles import FONTS, PADDING

logger = get_logger("mods_mixin")


class ModsMixin:
    """Mods management operations for MainWindow.

    Provides the full mod lifecycle for the Moria game:

    - **Installed Mods (left pane):** Lists the contents of the game's
      ``Moria/Content/Paks`` folder (local) or a remote server's Paks
      directory (via FTP/SFTP).  Users can move, organize, or remove
      individual mods from the installed location.

    - **Available Mods (right pane):** Lists mods stored in the local
      ``backup/mods`` directory.  Supports drag-and-drop import of
      ``.pak`` files, ``.zip`` archives, and directories.  Mods can be
      organized into named "Sets" (directories ending in " Set") for
      batch installation.

    - **Server sync:** When a server is selected instead of a local
      installation, most operations transparently redirect to
      FTP/SFTP equivalents (upload, delete, mkdir, list).

    Unreal Engine mods consist of up to three companion files
    (``.pak``, ``.ucas``, ``.utoc``).  This mixin always treats them
    as a unit -- copying, moving, or deleting all three together.

    This mixin is mixed into ``MainWindow`` and relies on attributes
    and helper methods defined there (e.g. ``current_installation``,
    ``current_server``, ``_server_*`` helpers, widget references).
    """

    # ---------------------------------------------------------------
    # Drag and Drop
    # ---------------------------------------------------------------

    def _setup_dnd_for_available_mods(self):
        """Set up drag and drop support for the Available Mods pane."""
        if not self._dnd_enabled:
            return

        try:
            # Register the versions pane as a drop target using tkinterdnd2
            # Use drop_target_register method from tkinterdnd2
            self.versions_pane.drop_target_register(tkinterdnd2.DND_FILES)
            self.versions_pane.dnd_bind('<<Drop>>', self._on_available_mods_drop)
            self.versions_pane.dnd_bind('<<DragEnter>>', self._on_available_mods_drag_enter)
            self.versions_pane.dnd_bind('<<DragLeave>>', self._on_available_mods_drag_leave)

            # Also register the scrollable frame
            self.versions_list_frame.drop_target_register(tkinterdnd2.DND_FILES)
            self.versions_list_frame.dnd_bind('<<Drop>>', self._on_available_mods_drop)
            self.versions_list_frame.dnd_bind('<<DragEnter>>', self._on_available_mods_drag_enter)
            self.versions_list_frame.dnd_bind('<<DragLeave>>', self._on_available_mods_drag_leave)

        except (RuntimeError, tk.TclError, AttributeError) as e:
            # DnD setup failed, continue without it
            logger.warning("Drag-and-drop setup failed: %s", e)
            self._dnd_enabled = False

    def _on_available_mods_drag_enter(self, event):
        """Handle drag enter on Available Mods pane."""
        if self.current_mode == "mods":
            self.versions_pane.configure(fg_color=("#4a4a4a", "#2a2a2a"))
        return event.action

    def _on_available_mods_drag_leave(self, event):
        """Handle drag leave on Available Mods pane."""
        self.versions_pane.configure(fg_color=("#3d3d3d", "#1a1a1a"))
        return event.action

    def _on_available_mods_drop(self, event):
        """Handle file drop on Available Mods pane."""
        # Reset pane color
        self.versions_pane.configure(fg_color=("#3d3d3d", "#1a1a1a"))

        # Only handle drops in mods mode
        if self.current_mode != "mods":
            self._set_status("Switch to Mods mode to add mods via drag and drop")
            return event.action

        # Get the dropped files
        # The data comes as a Tcl list string
        try:
            files_str = event.data
            # Parse the Tcl list format (handles spaces in paths with braces)
            files = self.tk.splitlist(files_str)
        except (tk.TclError, ValueError) as e:
            logger.debug("Could not parse Tcl list, using raw data: %s", e)
            files = [event.data] if event.data else []

        if not files:
            return event.action

        self._import_dropped_mod_files(files)
        return event.action

    # ---------------------------------------------------------------
    # Drag-and-Drop File Import
    # ---------------------------------------------------------------

    def _import_dropped_mod_files(self, files: list):
        """Import dropped files/folders to the Available Mods directory.

        Handles four source types:
        - Directories: copied wholesale into ``backup/mods``.
        - ``.zip`` archives: extracted; single top-level folders are
          preserved.
        - ``.pak`` files: all three companion files (``.pak``, ``.ucas``,
          ``.utoc``) are copied together from the source directory.
        - Other files: copied individually.

        Each import is validated for path safety before writing.
        """
        import shutil
        import zipfile
        from ..config.path_validator import is_safe_path, is_path_under_root, sanitize_filename

        backup_root = (
            self.config_manager.config.settings.backup_location
            or GamePaths.BACKUP_DEFAULT
        )
        mods_backup_path = backup_root / "mods"
        mods_backup_path.mkdir(parents=True, exist_ok=True)

        imported_count = 0
        skipped_count = 0

        for file_path_str in files:
            source_path = Path(file_path_str)

            if not source_path.exists():
                continue

            # Sanitize the filename to prevent path traversal
            safe_name = sanitize_filename(source_path.name)
            dest_path = mods_backup_path / safe_name

            # Validate destination path is safe and under backup root
            if (not is_safe_path(dest_path, allowed_roots=[backup_root])
                    or not is_path_under_root(dest_path, backup_root)):
                self._set_status(f"Skipped: Invalid destination path for '{source_path.name}'")
                skipped_count += 1
                continue

            try:
                if source_path.is_dir():
                    # Copy directory
                    if dest_path.exists():
                        # Ask to overwrite
                        choice = self._show_overwrite_skip_dialog(
                            "Folder Exists",
                            f"The folder '{source_path.name}' already "
                            "exists in Available Mods.\n\nOverwrite?"
                        )
                        if choice == "skip":
                            skipped_count += 1
                            continue
                        shutil.rmtree(str(dest_path))

                    shutil.copytree(str(source_path), str(dest_path))
                    imported_count += 1

                elif source_path.is_file() and source_path.suffix.lower() == ".zip":
                    # Handle zip files - extract contents to Available Mods
                    try:
                        with zipfile.ZipFile(str(source_path), 'r') as zip_ref:
                            # Get list of files in zip
                            zip_contents = zip_ref.namelist()

                            # Determine unique top-level entries in the archive so we can
                            # check for conflicts in the destination directory.
                            top_level_items = set()
                            for item in zip_contents:
                                top_item = item.split('/')[0]
                                if top_item:
                                    top_level_items.add(top_item)

                            # Check for existing files/folders
                            existing_items = []
                            for item in top_level_items:
                                check_path = mods_backup_path / item
                                if check_path.exists():
                                    existing_items.append(item)

                            if existing_items:
                                items_str = ", ".join(existing_items[:3])
                                if len(existing_items) > 3:
                                    items_str += f" (+{len(existing_items) - 3} more)"
                                choice = self._show_overwrite_skip_dialog(
                                    "Items Exist",
                                    f"Some items from '{source_path.name}'"
                                    f" already exist:\n{items_str}"
                                    "\n\nOverwrite?"
                                )
                                if choice == "skip":
                                    skipped_count += 1
                                    continue

                                # Remove existing items
                                for item in existing_items:
                                    item_path = mods_backup_path / item
                                    if item_path.is_dir():
                                        shutil.rmtree(str(item_path))
                                    elif item_path.is_file():
                                        item_path.unlink()

                            # Extract zip contents
                            zip_ref.extractall(str(mods_backup_path))
                            imported_count += 1
                            self._set_status(f"Extracted '{source_path.name}' to Available Mods")

                    except zipfile.BadZipFile:
                        self._set_status(f"Error: '{source_path.name}' is not a valid zip file")
                        continue

                elif source_path.is_file() and source_path.suffix.lower() == ".pak":
                    # UE mods ship as a trio: .pak (data), .ucas (content
                    # archive), .utoc (table of contents). Copy all three
                    # from the same source directory so the mod stays intact.
                    mod_name = source_path.stem
                    source_dir = source_path.parent
                    extensions = [".pak", ".ucas", ".utoc"]

                    # Check if any exist
                    any_exist = any(
                        (mods_backup_path / f"{mod_name}{ext}").exists()
                        for ext in extensions)
                    if any_exist:
                        choice = self._show_overwrite_skip_dialog(
                            "Mod Exists",
                            f"The mod '{mod_name}' already exists in Available Mods.\n\nOverwrite?"
                        )
                        if choice == "skip":
                            skipped_count += 1
                            continue

                    copied = 0
                    for ext in extensions:
                        src_file = source_dir / f"{mod_name}{ext}"
                        if src_file.exists():
                            dest_file = mods_backup_path / src_file.name
                            shutil.copy2(str(src_file), str(dest_file))
                            copied += 1

                    if copied > 0:
                        imported_count += 1

                elif source_path.is_file():
                    # Copy single file
                    if dest_path.exists():
                        choice = self._show_overwrite_skip_dialog(
                            "File Exists",
                            f"The file '{source_path.name}' already "
                            "exists in Available Mods.\n\nOverwrite?"
                        )
                        if choice == "skip":
                            skipped_count += 1
                            continue

                    shutil.copy2(str(source_path), str(dest_path))
                    imported_count += 1

            except (OSError, IOError, shutil.Error, zipfile.BadZipFile) as e:
                self._set_status(f"Error importing {source_path.name}: {e}")

        # Refresh and report
        self._refresh_available_mods()

        if imported_count > 0 and skipped_count > 0:
            self._set_status(f"Imported {imported_count} mod(s), skipped {skipped_count}")
        elif imported_count > 0:
            self._set_status(f"Imported {imported_count} mod(s) to Available Mods")
        elif skipped_count > 0:
            self._set_status(f"Skipped {skipped_count} mod(s) (already exist)")
        else:
            self._set_status("No mods imported")


    # ---------------------------------------------------------------
    # Installed Mods List (Local)
    # ---------------------------------------------------------------

    def _refresh_mods_list(self):
        """Refresh the mods list showing Paks folder contents.

        Delegates to ``_refresh_mods_list_from_server`` when a server
        is active; otherwise reads the local game directory.  Only
        ``.pak`` files are displayed (companion ``.ucas``/``.utoc``
        are hidden to keep the list clean).
        """
        # Check if we're working with a server
        if self.current_server:
            self._refresh_mods_list_from_server()
            return

        # Clear existing items in both panes
        for widget in self.item_list_frame.winfo_children():
            widget.destroy()
        for widget in self.versions_list_frame.winfo_children():
            widget.destroy()
        self.version_rows.clear()

        self.mods_items = []
        self.selected_mod_item = None

        if not self.current_installation:
            placeholder = ctk.CTkLabel(
                self.item_list_frame,
                text="Select an installation",
                font=FONTS["body"],
                text_color="gray"
            )
            placeholder.pack(pady=PADDING["large"])
            self._refresh_available_mods()
            return

        if not self.current_installation.game_path:
            placeholder = ctk.CTkLabel(
                self.item_list_frame,
                text="No game path configured\nfor this installation",
                font=FONTS["body"],
                text_color="gray",
                justify="center"
            )
            placeholder.pack(pady=PADDING["large"])
            self._refresh_available_mods()
            return

        # Build Paks folder path
        paks_path = self.current_installation.game_path / "Moria" / "Content" / "Paks"

        if not paks_path.exists():
            placeholder = ctk.CTkLabel(
                self.item_list_frame,
                text=f"Paks folder not found:\n{paks_path}",
                font=FONTS["body"],
                text_color="orange",
                justify="center"
            )
            placeholder.pack(pady=PADDING["large"])
            self._refresh_available_mods()
            return

        # List Paks contents, filtering out base-game shipping files
        # (defined in _excluded_game_files on MainWindow).  Only .pak
        # files are shown; .ucas/.utoc companions are hidden since the
        # user interacts with mods at the .pak level.
        try:
            items = []
            for item in paks_path.iterdir():
                if item.name in self._excluded_game_files:
                    continue
                if item.is_file():
                    # Only show .pak files
                    if item.suffix.lower() == ".pak":
                        items.append(item)
                else:
                    # Show all directories
                    items.append(item)

            # Sort: directories first, then files, alphabetically
            items.sort(key=lambda x: (not x.is_dir(), x.name.lower()))
            self.mods_items = items
        except (OSError, IOError) as e:
            placeholder = ctk.CTkLabel(
                self.item_list_frame,
                text=f"Error reading Paks:\n{e}",
                font=FONTS["body"],
                text_color="red",
                justify="center"
            )
            placeholder.pack(pady=PADDING["large"])
            self._refresh_available_mods()
            return

        # Update count label
        self.item_count_label.configure(text=f"({len(self.mods_items)} items)")

        if not self.mods_items:
            placeholder = ctk.CTkLabel(
                self.item_list_frame,
                text="No mods installed",
                font=FONTS["body"],
                text_color="gray"
            )
            placeholder.pack(pady=PADDING["large"])
            self._refresh_available_mods()
            return

        # Create row for each item
        for item in self.mods_items:
            self._create_mod_item_row(item)

        # Reset scroll to top if few items
        self._reset_scroll_if_few_items(self.item_list_frame)

        # Clear right pane
        self._refresh_available_mods()

    # ---------------------------------------------------------------
    # Installed Mods List (Server)
    # ---------------------------------------------------------------

    def _refresh_mods_list_from_server(self):
        """Refresh the mods list from a remote server's Paks folder.

        Connects via FTP/SFTP, lists the remote Paks directory, filters
        out base-game assets (``Moria-Windows*``, ``global.*``), and
        creates local cache Path objects so the rest of the UI can
        operate uniformly on Path-like items.
        """
        import os

        server = self.current_server

        # Clear existing items in both panes
        for widget in self.item_list_frame.winfo_children():
            widget.destroy()
        for widget in self.versions_list_frame.winfo_children():
            widget.destroy()
        self.version_rows.clear()

        self.mods_items = []
        self.selected_mod_item = None

        if not server:
            placeholder = ctk.CTkLabel(
                self.item_list_frame,
                text="No server selected",
                font=FONTS["body"],
                text_color="gray"
            )
            placeholder.pack(pady=PADDING["large"])
            self._refresh_available_mods()
            return

        # Get pak_path from server config
        pak_path = server.get("pak_path", "")
        server_name = server.get("name", "Unknown")
        protocol = server.get("protocol", "FTP")

        logger.debug(
            "_refresh_mods_list_from_server: server=%s, protocol=%s, pak_path='%s'",
            server_name, protocol, pak_path
        )

        if not pak_path:
            placeholder = ctk.CTkLabel(
                self.item_list_frame,
                text="No Paks path configured\nfor this server",
                font=FONTS["body"],
                text_color="gray",
                justify="center"
            )
            placeholder.pack(pady=PADDING["large"])
            self._refresh_available_mods()
            return

        # Ensure connected to server
        if not self._server_ensure_connected(server):
            placeholder = ctk.CTkLabel(
                self.item_list_frame,
                text="Failed to connect to server",
                font=FONTS["body"],
                text_color="red"
            )
            placeholder.pack(pady=PADDING["large"])
            self._refresh_available_mods()
            return

        self._set_status(f"Loading mods from {server_name}...")

        # Create a local cache directory per server so Path objects can be
        # constructed for remote entries.  Uses %APPDATA% on Windows with a
        # fallback to ~/.moria_manager on other platforms.
        try:
            appdata = os.environ.get("APPDATA", "")
            if appdata:
                cache_base = Path(appdata) / "MoriaManager" / "server_mods_cache" / server_name
            else:
                cache_base = Path.home() / ".moria_manager" / "server_mods_cache" / server_name
            cache_base.mkdir(parents=True, exist_ok=True)
            self._server_temp_mods_path = cache_base
        except Exception as e:
            logger.error("Failed to create mods cache directory: %s", e)
            placeholder = ctk.CTkLabel(
                self.item_list_frame,
                text=f"Failed to create cache:\n{e}",
                font=FONTS["body"],
                text_color="red",
                justify="center"
            )
            placeholder.pack(pady=PADDING["large"])
            self._refresh_available_mods()
            return

        # List entries (files and directories) from server Paks folder
        try:
            all_entries = self._server_list_entries(server, pak_path)
        except Exception as e:
            logger.error("Failed to list entries from server Paks: %s", e)
            placeholder = ctk.CTkLabel(
                self.item_list_frame,
                text=f"Failed to list server mods:\n{e}",
                font=FONTS["body"],
                text_color="red",
                justify="center"
            )
            placeholder.pack(pady=PADDING["large"])
            self._refresh_available_mods()
            return

        if not all_entries:
            placeholder = ctk.CTkLabel(
                self.item_list_frame,
                text="No mods on server",
                font=FONTS["body"],
                text_color="gray"
            )
            placeholder.pack(pady=PADDING["large"])
            self._refresh_available_mods()
            return

        # Filter server entries to just user-installed mods.
        # Base-game assets are excluded by exact name (_excluded_game_files)
        # and by known prefixes so only third-party mods appear in the UI.
        mod_items = []
        for name, is_dir in all_entries:
            if name in self._excluded_game_files:
                continue
            # Skip base-game shipping pak chunks and global shader cache
            if name.startswith("Moria-Windows"):
                continue
            if name.startswith("global."):
                continue

            if is_dir:
                # Include directories
                mod_items.append((name, True))
            elif name.lower().endswith(".pak"):
                # Include .pak files (hide .ucas and .utoc)
                mod_items.append((name, False))

        # Wrap remote entries as local cache Paths so the UI row-creation
        # code can work with Path objects uniformly (local and server).
        # The files are not actually downloaded here -- these are just
        # placeholder Paths used for display and name-based lookups.
        downloaded_items = []
        for name, is_dir in mod_items:
            local_path = self._server_temp_mods_path / name
            downloaded_items.append((local_path, is_dir))

        # Sort: directories first, then alphabetically
        downloaded_items.sort(key=lambda x: (not x[1], x[0].name.lower()))
        self.mods_items = [item[0] for item in downloaded_items]
        # _server_mod_is_dir tracks directory status since the cache Paths
        # may not exist on disk and Path.is_dir() would return False.
        self._server_mod_is_dir = {item[0].name: item[1] for item in downloaded_items}

        # Update count label
        self.item_count_label.configure(text=f"({len(self.mods_items)} items)")
        self._set_status(f"Found {len(self.mods_items)} mod(s) on {server_name}")

        if not self.mods_items:
            placeholder = ctk.CTkLabel(
                self.item_list_frame,
                text="No mods on server",
                font=FONTS["body"],
                text_color="gray"
            )
            placeholder.pack(pady=PADDING["large"])
            self._refresh_available_mods()
            return

        # Create row for each item (using Path objects pointing to cache)
        for item in self.mods_items:
            is_dir = self._server_mod_is_dir.get(item.name, False)
            self._create_mod_item_row_server(item, is_dir)

        # Reset scroll to top if few items
        self._reset_scroll_if_few_items(self.item_list_frame)

        # Refresh available mods pane
        self._refresh_available_mods()

    # ---------------------------------------------------------------
    # Server Mod Row UI
    # ---------------------------------------------------------------

    def _create_mod_item_row_server(self, item_path: Path, is_dir: bool = False):
        """Create a clickable row for a server mod file or directory.

        Similar to ``_create_mod_item_row`` for local mods but includes
        a trash button that triggers remote deletion via FTP/SFTP.
        """
        row = ctk.CTkFrame(self.item_list_frame, cursor="hand2")
        row.pack(fill="x", pady=1)

        # Make row clickable
        row.bind("<Button-1>", lambda e, p=item_path: self._on_mod_item_selected(p))

        # Icon indicator - different for files and directories
        if is_dir:
            icon_text = "\U0001F4C1"  # Folder icon
            icon_color = ("#FFD700", "#FFD700")  # Yellow/gold
            tooltip_text = "Server mod directory"
        else:
            icon_text = "\U0001F4C4"  # File icon
            icon_color = ("white", "white")
            tooltip_text = "Server mod file"

        icon_label = ctk.CTkLabel(
            row, text=icon_text,
            font=("Segoe UI Emoji", 14),
            text_color=icon_color,
            width=24
        )
        icon_label.pack(side="left", padx=(PADDING["small"], 2))
        icon_label.bind("<Button-1>", lambda e, p=item_path: self._on_mod_item_selected(p))
        self._create_tooltip(icon_label, tooltip_text)

        # Display name (show .pak name without extension for files, full name for directories)
        display_name = item_path.name if is_dir else item_path.stem
        name_label = ctk.CTkLabel(row, text=display_name, font=FONTS["body"], anchor="w")
        name_label.pack(
            side="left", fill="x", expand=True,
            padx=PADDING["small"], pady=PADDING["small"])
        name_label.bind("<Button-1>", lambda e, p=item_path: self._on_mod_item_selected(p))

        # Add trash button for deletion
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
                command=lambda p=item_path, d=is_dir: self._delete_mod_from_server(p, d)
            )
            trash_btn.pack(side="right", padx=PADDING["small"])
            self._create_tooltip(trash_btn, "Remove from server")

    # ---------------------------------------------------------------
    # Server Mod Deletion
    # ---------------------------------------------------------------

    def _delete_mod_from_server(self, item_path: Path, is_dir: bool = False):
        """Delete a mod file or directory from the server (including .ucas and .utoc).

        For directories, all contained files are deleted first, then the
        directory itself is removed.  For files, all three companion
        extensions are deleted.  The local cache copy is also cleaned up.
        """
        if not self.current_server:
            return

        server = self.current_server
        pak_path = server.get("pak_path", "")
        protocol = server.get("protocol", "FTP")
        server_name = server.get("name", "Unknown")
        mod_name = item_path.stem if not is_dir else item_path.name  # Directories use full name

        logger.debug(
            "_delete_mod_from_server: server=%s, protocol=%s, pak_path='%s', mod_name='%s', is_dir=%s",
            server_name, protocol, pak_path, mod_name, is_dir
        )

        if not pak_path:
            self._set_status("No Paks path configured for server")
            return

        # Confirm deletion
        from tkinter import messagebox
        item_type = "directory" if is_dir else "mod"
        if not messagebox.askyesno(
            "Confirm Deletion",
            f"Delete {item_type} '{mod_name}' from server?"
            "\n\nThis will remove .pak, .ucas, and .utoc files."
            "\nThis cannot be undone.",
            parent=self
        ):
            return

        deleted_count = 0

        try:
            if is_dir:
                # Delete directory and all its contents.
                # FTP/SFTP cannot delete non-empty directories, so files
                # must be removed first, then the empty directory itself.
                sep = "" if pak_path.endswith("/") else "/"
                remote_dir = f"{pak_path}{sep}{mod_name}"

                # First, try to delete all files in the directory
                self._set_status(f"Deleting files from directory {mod_name}...")
                try:
                    # Get all entries in the directory
                    entries = self._server_list_entries(server, remote_dir)
                    for entry_name, entry_is_dir in entries:
                        if not entry_is_dir:  # Only delete files, not subdirectories
                            remote_file = f"{remote_dir}/{entry_name}"
                            if self._server_delete_file(server, remote_file):
                                deleted_count += 1
                                logger.info("Deleted from server: %s", remote_file)
                except Exception as e:
                    logger.error("Error deleting files from directory: %s", e)

                # Now try to remove the directory itself
                if self._server_rmdir(server, remote_dir):
                    logger.info("Deleted directory from server: %s", remote_dir)
                    self._set_status(
                        f"Deleted directory {mod_name}"
                        f" ({deleted_count} files) from server")
                else:
                    self._set_status(
                        f"Deleted {deleted_count} files but "
                        "could not remove directory")

                # Clean up local cache directory
                if item_path.exists() and item_path.is_dir():
                    import shutil
                    shutil.rmtree(item_path, ignore_errors=True)
            else:
                # Delete individual mod files (.pak, .ucas, .utoc)
                extensions = [".pak", ".ucas", ".utoc"]

                for ext in extensions:
                    sep = "" if pak_path.endswith("/") else "/"
                    remote_file = f"{pak_path}{sep}{mod_name}{ext}"

                    if self._server_delete_file(server, remote_file):
                        deleted_count += 1
                        logger.info("Deleted from server: %s", remote_file)

                        # Also delete from local cache if exists
                        local_file = item_path.parent / f"{mod_name}{ext}"
                        if local_file.exists():
                            local_file.unlink()

                if deleted_count > 0:
                    self._set_status(f"Deleted {mod_name} ({deleted_count} files) from server")
                else:
                    self._set_status(f"No files deleted for {mod_name}")

            # Refresh the list
            self._refresh_mods_list()

        except Exception as e:
            logger.error("Failed to delete mod from server: %s", e)
            self._set_status(f"Delete failed: {e}")

    # ---------------------------------------------------------------
    # Local Mod Row UI and Selection
    # ---------------------------------------------------------------

    def _create_mod_item_row(self, item_path: Path):
        """Create a clickable row for a local mod file or directory in the left pane."""
        row = ctk.CTkFrame(self.item_list_frame, cursor="hand2")
        row.pack(fill="x", pady=1)

        # Make row clickable
        row.bind("<Button-1>", lambda e, p=item_path: self._on_mod_item_selected(p))

        # Icon indicator - use unicode symbols with colors
        if item_path.is_dir():
            icon_text = "\U0001F4C1"  # Folder icon
            icon_color = ("#FFD700", "#FFD700")  # Yellow/gold
            tooltip_text = "Directory"
        else:
            icon_text = "\U0001F4C4"  # File icon
            icon_color = ("white", "white")
            tooltip_text = "File"

        icon_label = ctk.CTkLabel(
            row, text=icon_text,
            font=("Segoe UI Emoji", 14),
            text_color=icon_color,
            width=30
        )
        icon_label.pack(side="left", padx=(PADDING["small"], 5))
        icon_label.bind("<Button-1>", lambda e, p=item_path: self._on_mod_item_selected(p))
        self._create_tooltip(icon_label, tooltip_text)

        # Name label (show .pak name without extension for cleaner look)
        display_name = item_path.stem if item_path.is_file() else item_path.name
        name_label = ctk.CTkLabel(
            row, text=display_name,
            font=FONTS["body"], anchor="w"
        )
        name_label.pack(
            side="left", fill="x", expand=True,
            padx=(0, PADDING["small"]),
            pady=PADDING["small"])
        name_label.bind("<Button-1>", lambda e, p=item_path: self._on_mod_item_selected(p))

        # Store reference for highlighting
        self.version_rows[item_path.name] = row

    def _on_mod_item_selected(self, item_path: Path):
        """Handle mod item selection in the Installed Mods (left) pane.

        Highlights the selected row and dynamically adds context-sensitive
        action buttons:
        - Arrow (move to Available) or X (remove from Installed) depending
          on whether the mod already exists in backup.
        - Folder button to reorganize loose ``.pak`` files into a subdirectory.
        """
        self.selected_mod_item = item_path

        # Update highlighting on all rows and add/remove action buttons
        for name, row in self.version_rows.items():
            # Remove old action buttons if present
            for child in row.winfo_children():
                if isinstance(child, ctk.CTkButton):
                    child.destroy()

            is_selected = name == item_path.name
            row.configure(fg_color=("gray85", "gray25") if is_selected else ("gray95", "gray17"))

            # Add action buttons for selected item
            if is_selected:
                backup_root = (
                    self.config_manager.config.settings.backup_location
                    or GamePaths.BACKUP_DEFAULT
                )

                if item_path.is_dir():
                    # Directory selected - show move/remove button
                    mods_backup_path = backup_root / "mods" / item_path.name

                    if mods_backup_path.exists():
                        # Mod already in backup - show remove from Installed option
                        action_btn = ctk.CTkButton(
                            row, text="\u2717", width=28, height=24,  # X mark
                            font=("Segoe UI", 14, "bold"),
                            text_color="red",
                            fg_color="transparent", hover_color=("gray80", "gray30"),
                            command=lambda p=item_path: self._prompt_remove_installed_mod_dir(p)
                        )
                        action_btn.pack(side="right", padx=PADDING["small"])
                        self._create_tooltip(action_btn, "Remove from Installed Mods")
                    else:
                        # Mod not in backup - show move option
                        action_btn = ctk.CTkButton(
                            row, text="\u27A4", width=28, height=24,  # Bold right arrow
                            font=("Segoe UI", 14, "bold"),
                            text_color=("gray10", "gray90"),
                            fg_color="transparent", hover_color=("gray80", "gray30"),
                            command=lambda p=item_path: self._move_mod_to_available(p)
                        )
                        action_btn.pack(side="right", padx=PADDING["small"])
                        self._create_tooltip(action_btn, "Move to Available Mods")
                else:
                    # File selected (.pak) - show folder button and optionally arrow/X button
                    mod_name = item_path.stem  # Filename without extension
                    mods_backup_path = backup_root / "mods"

                    # Check if files already exist in backup/mods
                    files_exist_in_backup = (
                        (mods_backup_path / f"{mod_name}.pak").exists() or
                        (mods_backup_path / mod_name).exists()
                    )

                    if files_exist_in_backup:
                        # Files already exist in backup - show remove from Installed option
                        action_btn = ctk.CTkButton(
                            row, text="\u2717", width=28, height=24,  # X mark
                            font=("Segoe UI", 14, "bold"),
                            text_color="red",
                            fg_color="transparent", hover_color=("gray80", "gray30"),
                            command=lambda p=item_path: self._prompt_remove_installed_mod_files(p)
                        )
                        action_btn.pack(side="right", padx=2)
                        self._create_tooltip(action_btn, "Remove from Installed Mods")
                    else:
                        # Arrow button - move files to Available Mods
                        arrow_btn = ctk.CTkButton(
                            row, text="\u27A4", width=28, height=24,  # Bold right arrow
                            font=("Segoe UI", 14, "bold"),
                            text_color=("gray10", "gray90"),
                            fg_color="transparent", hover_color=("gray80", "gray30"),
                            command=lambda p=item_path: self._move_mod_files_to_available(p)
                        )
                        arrow_btn.pack(side="right", padx=2)
                        self._create_tooltip(arrow_btn, "Move files to Available Mods")

                    # Folder button - ALWAYS show for files so user can organize into folder
                    folder_btn = ctk.CTkButton(
                        row, text="\U0001F4C1", width=28, height=24,  # Folder icon
                        font=("Segoe UI Emoji", 12),
                        text_color=("#FFD700", "#FFD700"),
                        fg_color="transparent", hover_color=("gray80", "gray30"),
                        command=lambda p=item_path: self._create_folder_for_mod_files(p)
                    )
                    folder_btn.pack(side="right", padx=2)
                    self._create_tooltip(folder_btn, "Create folder and organize files")

        self._refresh_available_mods()
        self._set_status(f"Selected: {item_path.name}")

    # ---------------------------------------------------------------
    # Local Mod Move / Remove Operations
    # ---------------------------------------------------------------

    def _move_mod_to_available(self, item_path: Path):
        """Move a mod directory from Installed (Paks) to Available (backup/mods)."""
        import shutil
        from ..config.path_validator import is_safe_path, is_path_under_root, sanitize_filename

        backup_root = (
            self.config_manager.config.settings.backup_location
            or GamePaths.BACKUP_DEFAULT
        )
        mods_backup_path = backup_root / "mods"

        # Ensure mods directory exists
        mods_backup_path.mkdir(parents=True, exist_ok=True)

        # Sanitize filename and validate destination
        safe_name = sanitize_filename(item_path.name)
        dest_path = mods_backup_path / safe_name

        # Validate destination is safe
        if (not is_safe_path(dest_path, allowed_roots=[backup_root])
                or not is_path_under_root(dest_path, backup_root)):
            self._set_status("Invalid destination path")
            return

        try:
            shutil.move(str(item_path), str(dest_path))
            self._set_status(f"Moved '{item_path.name}' to Available Mods")
            # Refresh both panes
            self._refresh_mods_list()
        except (OSError, IOError, shutil.Error) as e:
            self._set_status(f"Failed to move mod: {e}")

    def _prompt_remove_installed_mod_dir(self, item_path: Path):
        """Prompt to remove a mod directory from Installed Mods (game's Paks folder).

        Uses a multi-retry strategy with read-only attribute clearing to
        handle Windows file-locking issues that can prevent immediate
        deletion of game asset directories.
        """
        import time
        import os
        import stat
        from ..config.path_validator import is_safe_path, is_path_under_root

        # Check if deletion is enabled
        if not self.config_manager.config.settings.enable_deletion:
            self._set_status("Deletion is disabled. Enable it in Settings.")
            return

        # Ensure path is under game installation
        if not self.current_installation or not self.current_installation.game_path:
            self._set_status("Cannot remove: no game installation configured")
            return

        if not is_path_under_root(item_path, self.current_installation.game_path):
            self._set_status("Cannot remove: path is outside game installation")
            return

        # Validate path is safe to delete (with game path as allowed root)
        if not is_safe_path(item_path, allowed_roots=[self.current_installation.game_path]):
            self._set_status("Cannot remove: path is in a protected directory")
            return

        message = (
            f"The mod '{item_path.name}' is already in "
            "Available Mods.\n\nWould you like to remove it "
            "from Installed Mods?")

        def remove_readonly(func, path, _excinfo):
            """Error handler for shutil.rmtree to handle read-only files."""
            os.chmod(path, stat.S_IWRITE)
            func(path)

        def clear_readonly_recursive(path: Path):
            """Clear read-only attribute from directory and all contents."""
            try:
                os.chmod(str(path), stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)
                if path.is_dir():
                    for item in path.iterdir():
                        clear_readonly_recursive(item)
            except OSError as e:
                logger.debug("Could not clear read-only on %s: %s", path, e)

        if self._show_confirm_dialog("Remove from Installed?", message):
            import shutil
            errors_log = []
            try:
                if item_path.is_dir():
                    # First, clear read-only attributes from all files/folders
                    try:
                        clear_readonly_recursive(item_path)
                        errors_log.append("Cleared read-only attributes")
                    except OSError as e:
                        errors_log.append(f"Could not clear read-only: {e}")

                    # First attempt with onerror handler
                    try:
                        shutil.rmtree(str(item_path), onexc=remove_readonly)
                        errors_log.append("Attempt 1: shutil.rmtree completed")
                    except (OSError, shutil.Error) as e:
                        errors_log.append(f"Attempt 1: shutil.rmtree failed - {e}")

                    # Retry mechanism: Windows often holds transient file handles on
                    # game assets.  A short delay and re-attempt usually succeeds.
                    max_retries = 3
                    for attempt in range(max_retries):
                        if not item_path.exists():
                            errors_log.append(
                                "Directory removed successfully"
                                f" after attempt {attempt + 1}")
                            break

                        # Check what's left in the directory
                        try:
                            remaining = (
                                list(item_path.iterdir())
                                if item_path.is_dir() else [])
                            errors_log.append(
                                f"Retry {attempt + 1}: "
                                "Directory still exists, "
                                f"{len(remaining)} items "
                                "remaining")
                        except OSError as e:
                            errors_log.append(
                                f"Retry {attempt + 1}: Could "
                                f"not list directory - {e}")

                        # Small delay before retry (Windows file handles may need time to release)
                        time.sleep(0.2)

                        # Clear read-only again before retry
                        try:
                            clear_readonly_recursive(item_path)
                        except OSError as e:
                            logger.debug("Retry clear read-only failed: %s", e)

                        try:
                            if item_path.is_dir():
                                # Try removing with os.rmdir if empty
                                try:
                                    os.chmod(
                                        str(item_path),
                                        stat.S_IWRITE
                                        | stat.S_IREAD
                                        | stat.S_IEXEC)
                                    os.rmdir(str(item_path))
                                    errors_log.append(
                                        f"Retry {attempt + 1}"
                                        ": os.rmdir succeeded")
                                except OSError as rmdir_err:
                                    errors_log.append(
                                        f"Retry {attempt + 1}"
                                        ": os.rmdir failed - "
                                        f"{rmdir_err}")
                                    # If rmdir fails, try
                                    # shutil.rmtree again
                                    shutil.rmtree(
                                        str(item_path),
                                        onexc=remove_readonly)
                                    errors_log.append(
                                        f"Retry {attempt + 1}"
                                        ": shutil.rmtree "
                                        "succeeded")
                            elif item_path.exists():
                                os.chmod(str(item_path), stat.S_IWRITE)
                                item_path.unlink()
                                errors_log.append(f"Retry {attempt + 1}: unlink succeeded")
                        except (OSError, shutil.Error) as retry_err:
                            errors_log.append(f"Retry {attempt + 1}: Failed - {retry_err}")

                    if item_path.exists():
                        # Show error popup with details
                        error_details = "\n".join(errors_log)
                        self._show_info_dialog(
                            "Directory Removal Failed",
                            f"Could not fully remove "
                            f"'{item_path.name}'.\n\n"
                            f"Details:\n{error_details}"
                        )
                        self._set_status(f"Warning: Could not fully remove '{item_path.name}'")
                    else:
                        self._set_status(f"Removed folder '{item_path.name}' from Installed Mods")
                elif item_path.is_file():
                    # If somehow a file was passed, delete the file and related files
                    mod_name = item_path.stem
                    containing_dir = item_path.parent
                    extensions = [".pak", ".ucas", ".utoc"]
                    for ext in extensions:
                        file_path = containing_dir / f"{mod_name}{ext}"
                        if file_path.exists():
                            file_path.unlink()
                    self._set_status(f"Removed '{item_path.name}' from Installed Mods")
                else:
                    self._set_status(f"Path does not exist: {item_path}")
                # Refresh to update the mods list
                self._refresh_mods_list()
            except (OSError, IOError, shutil.Error) as e:
                self._show_info_dialog(
                    "Removal Error",
                    f"Failed to remove mod: {e}\n\nLog:\n"
                    + "\n".join(errors_log))
                self._set_status(f"Failed to remove mod: {e}")

    # ---------------------------------------------------------------
    # Mod File Organization (Installed Mods)
    # ---------------------------------------------------------------

    def _create_folder_for_mod_files(self, item_path: Path):
        """Create a folder with the mod name and move all 3 files into it.

        Takes a .pak file, creates a directory with the mod name (no extension),
        and moves the .pak, .ucas, and .utoc files into that directory.
        This keeps the Paks folder tidy by grouping related mod assets.
        """
        import shutil

        mod_name = item_path.stem  # Filename without extension
        paks_dir = item_path.parent  # The Paks directory

        # Create the new folder in the Paks directory
        folder_path = paks_dir / mod_name

        try:
            folder_path.mkdir(exist_ok=True)

            # Find and move all 3 files
            extensions = [".pak", ".ucas", ".utoc"]
            moved_count = 0
            for ext in extensions:
                source_file = paks_dir / f"{mod_name}{ext}"
                if source_file.exists():
                    dest_file = folder_path / source_file.name
                    shutil.move(str(source_file), str(dest_file))
                    moved_count += 1

            self._set_status(f"Created folder '{mod_name}' with {moved_count} files")
            # Refresh the mods list
            self._refresh_mods_list()
        except (OSError, IOError, shutil.Error) as e:
            self._set_status(f"Failed to create folder: {e}")

    def _move_mod_files_to_available(self, item_path: Path):
        """Move all 3 mod files (.pak, .ucas, .utoc) to backup/mods directory."""
        import shutil

        mod_name = item_path.stem  # Filename without extension
        paks_dir = item_path.parent  # The Paks directory

        backup_root = (
            self.config_manager.config.settings.backup_location
            or GamePaths.BACKUP_DEFAULT
        )
        mods_backup_path = backup_root / "mods"

        # Ensure mods directory exists
        mods_backup_path.mkdir(parents=True, exist_ok=True)

        try:
            # Find and move all 3 files
            extensions = [".pak", ".ucas", ".utoc"]
            moved_count = 0
            for ext in extensions:
                source_file = paks_dir / f"{mod_name}{ext}"
                if source_file.exists():
                    dest_file = mods_backup_path / source_file.name
                    shutil.move(str(source_file), str(dest_file))
                    moved_count += 1

            self._set_status(f"Moved {moved_count} files for '{mod_name}' to Available Mods")
            # Refresh the mods list
            self._refresh_mods_list()
        except (OSError, IOError, shutil.Error) as e:
            self._set_status(f"Failed to move mod files: {e}")

    def _prompt_remove_installed_mod_files(self, item_path: Path):
        """Prompt to remove mod files from Installed Mods (game's Paks folder)."""
        # Check if deletion is enabled
        if not self.config_manager.config.settings.enable_deletion:
            self._set_status("Deletion is disabled. Enable it in Settings.")
            return

        mod_name = item_path.stem  # Filename without extension
        containing_dir = item_path.parent  # The directory containing the files

        message = (
            f"The mod '{mod_name}' is already in "
            "Available Mods.\n\nWould you like to remove it "
            "from Installed Mods?")

        if self._show_confirm_dialog("Remove from Installed?", message):
            try:
                # Delete all 3 files if they exist
                extensions = [".pak", ".ucas", ".utoc"]
                deleted_count = 0
                for ext in extensions:
                    file_path = containing_dir / f"{mod_name}{ext}"
                    if file_path.exists():
                        file_path.unlink()
                        deleted_count += 1

                # Clean up the parent directory if it was a per-mod
                # subfolder (not the top-level Paks dir) and is now empty.
                if containing_dir.exists() and containing_dir.name != "Paks":
                    try:
                        # Check if directory is empty
                        remaining_files = list(containing_dir.iterdir())
                        if not remaining_files:
                            containing_dir.rmdir()
                            self._set_status(
                                f"Removed '{mod_name}' and "
                                "empty folder from "
                                "Installed Mods")
                        else:
                            self._set_status(
                                f"Removed '{mod_name}' from "
                                "Installed Mods "
                                f"({deleted_count} files)")
                    except OSError:
                        self._set_status(
                            f"Removed '{mod_name}' from "
                            "Installed Mods "
                            f"({deleted_count} files)")
                else:
                    self._set_status(
                        f"Removed '{mod_name}' from "
                        "Installed Mods "
                        f"({deleted_count} files)")

                # Refresh the mods list
                self._refresh_mods_list()
            except OSError as e:
                self._set_status(f"Failed to remove mod files: {e}")

    # ---------------------------------------------------------------
    # Available Mods List (Right Pane)
    # ---------------------------------------------------------------

    def _refresh_available_mods(self):
        """Refresh the right pane with available mods from backup/mods directory.

        Mod Sets (directories ending in " Set") are listed first with a
        visual separator, followed by regular directories and ``.pak``
        files sorted alphabetically.
        """
        # Clear existing items
        for widget in self.versions_list_frame.winfo_children():
            widget.destroy()

        self.available_mod_rows.clear()
        self.selected_available_mod = None
        self.versions_count_label.configure(text="")

        # Get backup root from config
        backup_root = (
            self.config_manager.config.settings.backup_location
            or GamePaths.BACKUP_DEFAULT
        )
        mods_path = backup_root / "mods"

        if not mods_path.exists():
            # Create the mods directory if it doesn't exist
            try:
                mods_path.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                logger.warning("Could not create mods directory %s: %s", mods_path, e)

            placeholder = ctk.CTkLabel(
                self.versions_list_frame,
                text="No available mods\n\nAdd mod files to:\n" + str(mods_path),
                font=FONTS["body"],
                text_color="gray",
                justify="center"
            )
            placeholder.pack(pady=PADDING["large"])
            return

        # Get all mod files and directories (only .pak files for files)
        try:
            items = []
            for item in mods_path.iterdir():
                if item.is_file():
                    if item.suffix.lower() == ".pak":
                        items.append(item)
                else:
                    items.append(item)

            # Directories whose name ends with " Set" are treated as curated
            # mod collections.  They get special UI treatment (green icon,
            # Install-All button) and are listed above regular mods.
            sets = [item for item in items if item.is_dir() and item.name.endswith(" Set")]
            other_items = [
                item for item in items
                if not (item.is_dir()
                        and item.name.endswith(" Set"))]

            # Sort Sets alphabetically
            sets.sort(key=lambda x: x.name.lower())

            # Sort other items: directories first, then files, alphabetically
            other_items.sort(key=lambda x: (not x.is_dir(), x.name.lower()))

            self.available_mods_items = sets + other_items
        except OSError as e:
            placeholder = ctk.CTkLabel(
                self.versions_list_frame,
                text=f"Error reading mods:\n{e}",
                font=FONTS["body"],
                text_color="red",
                justify="center"
            )
            placeholder.pack(pady=PADDING["large"])
            return

        self.versions_count_label.configure(text=f"({len(items)})")

        if not items:
            placeholder = ctk.CTkLabel(
                self.versions_list_frame,
                text="No available mods\n\nAdd mod files to:\n" + str(mods_path),
                font=FONTS["body"],
                text_color="gray",
                justify="center"
            )
            placeholder.pack(pady=PADDING["large"])
            return

        # Create rows for Sets first
        for item in sets:
            self._create_available_mod_row(item)

        # Add separator line if there are Sets and other items
        if sets and other_items:
            separator = ctk.CTkFrame(
                self.versions_list_frame, height=2,
                fg_color=("gray60", "gray40"))
            separator.pack(fill="x", pady=5)

        # Create rows for other mods
        for item in other_items:
            self._create_available_mod_row(item)

        # Reset scroll to top if few items
        self._reset_scroll_if_few_items(self.versions_list_frame)

    def _create_available_mod_row(self, item_path: Path):
        """Create a row for an available mod in the right pane."""
        row = ctk.CTkFrame(self.versions_list_frame, cursor="hand2")
        row.pack(fill="x", pady=1)

        # Check if this is a Set directory (ends with " Set")
        is_set_dir = item_path.is_dir() and item_path.name.endswith(" Set")

        # Make row clickable - all items select on click
        row.bind("<Button-1>", lambda e, p=item_path: self._on_available_mod_selected(p))

        # Store reference for highlighting
        self.available_mod_rows[item_path.name] = row

        # Icon indicator
        if item_path.is_dir():
            icon_text = "\U0001F4C1"  # Folder icon
            if is_set_dir:
                icon_color = ("#00CC00", "#00CC00")  # Green for Set directories
                tooltip_text = "Mod Set (right-click for options)"
            else:
                icon_color = ("#FFD700", "#FFD700")  # Yellow/gold for regular directories
                tooltip_text = "Directory"
        else:
            icon_text = "\U0001F4C4"  # File icon
            icon_color = ("white", "white")
            tooltip_text = "File"

        icon_label = ctk.CTkLabel(
            row, text=icon_text,
            font=("Segoe UI Emoji", 14),
            text_color=icon_color,
            width=30
        )
        icon_label.pack(side="left", padx=(PADDING["small"], 5))
        icon_label.bind("<Button-1>", lambda e, p=item_path: self._on_available_mod_selected(p))
        self._create_tooltip(icon_label, tooltip_text)

        # Name label
        display_name = item_path.stem if item_path.is_file() else item_path.name
        name_label = ctk.CTkLabel(
            row, text=display_name,
            font=FONTS["body"], anchor="w"
        )
        name_label.pack(
            side="left", fill="x", expand=True,
            padx=(0, PADDING["small"]),
            pady=PADDING["small"])
        name_label.bind("<Button-1>", lambda e, p=item_path: self._on_available_mod_selected(p))

    def _on_available_mod_selected(self, item_path: Path):
        """Handle available mod item selection in the right pane.

        Highlights the row and shows context-sensitive action buttons:
        - Install arrow (copy to game/server).
        - Copy-to-Set triangle.
        - Trash button (delete from Available Mods).
        - Folder-organize button (for loose ``.pak`` files).
        - For Sets: Install-All, Open, and Rename buttons.
        """
        self.selected_available_mod = item_path

        # Update highlighting on all rows and add/remove action buttons
        for name, row in self.available_mod_rows.items():
            # Remove old action buttons if present
            for child in row.winfo_children():
                if isinstance(child, ctk.CTkButton):
                    child.destroy()

            is_selected = name == item_path.name
            row.configure(fg_color=("gray85", "gray25") if is_selected else ("gray95", "gray17"))

            # Add action buttons for selected item
            if is_selected:
                # Check if this is a Set directory
                is_set_dir = item_path.is_dir() and item_path.name.endswith(" Set")

                # Red trash can button to delete (always visible)
                trash_image = self._load_icon("icons/trash.png", size=(16, 16))
                if trash_image:
                    trash_btn = ctk.CTkButton(
                        row, image=trash_image, text="", width=24, height=24,
                        fg_color="transparent", hover_color=("#ffcccc", "#4a1a1a"),
                        command=lambda p=item_path: self._prompt_delete_available_mod(p)
                    )
                else:
                    trash_btn = ctk.CTkButton(
                        row, text="🗑", width=24, height=24,
                        font=FONTS["small"], text_color="red",
                        fg_color="transparent", hover_color=("#ffcccc", "#4a1a1a"),
                        command=lambda p=item_path: self._prompt_delete_available_mod(p)
                    )
                trash_btn.pack(side="right", padx=2)
                self._create_tooltip(trash_btn, "Delete mod")

                # Left arrow button to install (not for Sets)
                if not is_set_dir:
                    action_btn = ctk.CTkButton(
                        row, text="\u276E", width=28, height=24,  # Bold left arrow
                        font=("Segoe UI", 14, "bold"),
                        text_color=("gray10", "gray90"),
                        fg_color="transparent", hover_color=("gray80", "gray30"),
                        command=lambda p=item_path: self._install_mod_from_available(p)
                    )
                    action_btn.pack(side="right", padx=PADDING["small"])
                    self._create_tooltip(action_btn, "Install to Game")

                    # Copy to Set button (up arrow) - only for non-Set items
                    copy_to_set_btn = ctk.CTkButton(
                        row, text="\u25B2", width=28, height=24,  # Bold up-pointing triangle
                        font=("Segoe UI", 14, "bold"),
                        text_color=("#00CC00", "#00FF00"),  # Green color
                        fg_color="transparent", hover_color=("gray80", "gray30"),
                        command=lambda p=item_path: self._copy_mod_to_set_dialog(p)
                    )
                    copy_to_set_btn.pack(side="right", padx=2)
                    self._create_tooltip(copy_to_set_btn, "Copy to Set")
                else:
                    # Set-specific buttons: Install All, Open, and Rename
                    # Left arrow - install all mods from Set to game
                    install_all_btn = ctk.CTkButton(
                        row, text="\u276E", width=28, height=24,  # Bold left arrow
                        font=("Segoe UI", 14, "bold"),
                        text_color=("gray10", "gray90"),
                        fg_color="transparent", hover_color=("gray80", "gray30"),
                        command=lambda p=item_path: self._install_all_from_set(p)
                    )
                    install_all_btn.pack(side="right", padx=PADDING["small"])
                    self._create_tooltip(install_all_btn, "Install All to Game")

                    # Open button - open Set contents window
                    open_btn = ctk.CTkButton(
                        row, text="\u2750", width=28, height=24,  # Open folder symbol
                        font=("Segoe UI", 14, "bold"),
                        text_color=("#00CC00", "#00FF00"),  # Green color
                        fg_color="transparent", hover_color=("gray80", "gray30"),
                        command=lambda p=item_path: self._show_set_contents_window(p)
                    )
                    open_btn.pack(side="right", padx=2)
                    self._create_tooltip(open_btn, "Open Set")

                    # Rename button - rename the Set
                    rename_btn = ctk.CTkButton(
                        row, text="\u270E", width=28, height=24,  # Pencil icon
                        font=("Segoe UI", 14, "bold"),
                        text_color=("gray10", "gray90"),
                        fg_color="transparent", hover_color=("gray80", "gray30"),
                        command=lambda p=item_path: self._rename_mod_set(p)
                    )
                    rename_btn.pack(side="right", padx=2)
                    self._create_tooltip(rename_btn, "Rename Set")

                # For files, add folder button to organize into directory
                if item_path.is_file():
                    folder_btn = ctk.CTkButton(
                        row, text="\U0001F4C1", width=28, height=24,  # Folder icon
                        font=("Segoe UI", 12),
                        text_color=("#D4A017", "#FFD700"),  # Yellow/gold color
                        fg_color="transparent", hover_color=("gray80", "gray30"),
                        command=lambda p=item_path: self._organize_available_mod_files(p)
                    )
                    folder_btn.pack(side="right", padx=2)
                    self._create_tooltip(folder_btn, "Organize into folder")

        self._set_status(f"Selected available mod: {item_path.name}")

    # ---------------------------------------------------------------
    # Mod Sets (Create, Rename, Delete, Context Menu)
    # ---------------------------------------------------------------

    def _add_mod_set(self):
        """Prompt user for a name and create a new mod Set directory.

        The " Set" suffix is automatically appended to the user-provided
        name so the directory is recognized as a Set elsewhere in the UI.
        """
        dialog = ctk.CTkInputDialog(
            text="Enter a name for the new mod set:",
            title="Add Mod Set"
        )
        name = dialog.get_input()

        if not name or not name.strip():
            return  # User cancelled or entered empty name

        # Append " Set" to the name
        set_name = f"{name.strip()} Set"

        # Get the mods directory path
        backup_root = (
            self.config_manager.config.settings.backup_location
            or GamePaths.BACKUP_DEFAULT
        )
        mods_path = backup_root / "mods"
        set_path = mods_path / set_name

        # Check if already exists
        if set_path.exists():
            from tkinter import messagebox
            messagebox.showwarning(
                "Set Exists",
                f"A mod set named '{set_name}' already exists.",
                parent=self
            )
            return

        # Create the directory
        try:
            set_path.mkdir(parents=True, exist_ok=True)
            self._set_status(f"Created mod set: {set_name}")
            self._refresh_available_mods()
        except OSError as e:
            logger.error("Failed to create mod set %s: %s", set_name, e)
            self._set_status(f"Failed to create mod set: {e}")

    def _show_set_context_menu(self, event, set_path: Path):
        """Show context menu for a Set directory."""
        # Create context menu with larger font
        context_menu = tk.Menu(self, tearoff=0, font=("Segoe UI", 12))
        context_menu.add_command(
            label="Rename",
            command=lambda: self._rename_mod_set(set_path)
        )
        context_menu.add_command(
            label="Delete",
            command=lambda: self._delete_mod_set(set_path)
        )

        # Show the menu at cursor position
        try:
            context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            context_menu.grab_release()

    def _rename_mod_set(self, set_path: Path):
        """Prompt user for a new name and rename the Set directory."""
        # Get current name without " Set" suffix
        current_name = set_path.name
        if current_name.endswith(" Set"):
            current_base_name = current_name[:-4]  # Remove " Set"
        else:
            current_base_name = current_name

        # Create custom dialog with pre-filled entry
        dialog = ctk.CTkToplevel(self)
        dialog.title("Rename Mod Set")
        dialog.geometry("350x180")
        dialog.transient(self)
        dialog.grab_set()
        self._set_dialog_icon(dialog)

        # Center on parent
        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 350) // 2
        y = self.winfo_y() + (self.winfo_height() - 180) // 2
        dialog.geometry(f"+{x}+{y}")

        # Label
        label = ctk.CTkLabel(
            dialog,
            text=f"Enter a new name for '{current_name}':",
            font=FONTS["body"])
        label.pack(pady=(PADDING["medium"], PADDING["small"]))

        # Entry with pre-filled value
        entry = ctk.CTkEntry(dialog, width=280, font=FONTS["body"])
        entry.pack(pady=PADDING["small"])
        entry.insert(0, current_base_name)
        entry.select_range(0, tk.END)
        entry.focus_set()

        # Mutable container lets the nested callbacks share state with the
        # outer scope (wait_window blocks until dialog.destroy is called).
        result = [None]

        def on_ok():
            result[0] = entry.get()
            dialog.destroy()

        def on_cancel():
            dialog.destroy()

        # Bind Enter key
        entry.bind("<Return>", lambda e: on_ok())
        dialog.bind("<Escape>", lambda e: on_cancel())

        # Buttons
        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=PADDING["medium"])

        cancel_btn = ctk.CTkButton(
            btn_frame, text="Cancel", width=80,
            fg_color=("gray70", "gray40"), command=on_cancel)
        cancel_btn.pack(side="left", padx=PADDING["small"])

        ok_btn = ctk.CTkButton(btn_frame, text="OK", width=80, command=on_ok)
        ok_btn.pack(side="left", padx=PADDING["small"])

        # Wait for dialog to close
        dialog.wait_window()

        new_name = result[0]
        if not new_name or not new_name.strip():
            return  # User cancelled or entered empty name

        # Append " Set" to the new name
        new_set_name = f"{new_name.strip()} Set"

        # Check if same name
        if new_set_name == current_name:
            return  # No change needed

        # Get the new path
        new_path = set_path.parent / new_set_name

        # Check if already exists
        if new_path.exists():
            from tkinter import messagebox
            messagebox.showwarning(
                "Set Exists",
                f"A mod set named '{new_set_name}' already exists.",
                parent=self
            )
            return

        # Rename the directory
        try:
            set_path.rename(new_path)
            self._set_status(f"Renamed mod set to: {new_set_name}")
            self._refresh_available_mods()
        except OSError as e:
            logger.error("Failed to rename mod set %s to %s: %s", current_name, new_set_name, e)
            self._set_status(f"Failed to rename mod set: {e}")

    def _delete_mod_set(self, set_path: Path):
        """Prompt for confirmation and delete the Set directory and all contents."""
        import shutil
        from tkinter import messagebox

        # Count contents
        try:
            contents = list(set_path.iterdir())
            file_count = len([f for f in contents if f.is_file()])
            dir_count = len([d for d in contents if d.is_dir()])
        except OSError:
            file_count = 0
            dir_count = 0

        # Build confirmation message
        if file_count > 0 or dir_count > 0:
            content_msg = f"\n\nThis set contains {file_count} file(s) and {dir_count} folder(s)."
        else:
            content_msg = "\n\nThis set is empty."

        result = messagebox.askyesno(
            "Delete Mod Set",
            f"Are you sure you want to delete "
            f"'{set_path.name}'?{content_msg}"
            "\n\nThis action cannot be undone.",
            parent=self
        )

        if not result:
            return  # User cancelled

        # Delete the directory and all contents
        try:
            shutil.rmtree(set_path)
            self._set_status(f"Deleted mod set: {set_path.name}")
            self._refresh_available_mods()
        except OSError as e:
            logger.error("Failed to delete mod set %s: %s", set_path.name, e)
            self._set_status(f"Failed to delete mod set: {e}")

    # ---------------------------------------------------------------
    # Copy Mod to Set
    # ---------------------------------------------------------------

    def _copy_mod_to_set_dialog(self, mod_path: Path):
        """Show dialog to select a Set and copy the mod into it.

        Lists all existing Sets as clickable buttons.  Selecting one
        immediately copies the mod and closes the dialog.
        """
        # Get list of available Sets
        backup_root = (
            self.config_manager.config.settings.backup_location
            or GamePaths.BACKUP_DEFAULT
        )
        mods_path = backup_root / "mods"

        try:
            sets = [item for item in mods_path.iterdir()
                    if item.is_dir() and item.name.endswith(" Set")]
            sets.sort(key=lambda x: x.name.lower())
        except OSError:
            sets = []

        if not sets:
            from tkinter import messagebox
            messagebox.showinfo(
                "No Sets Available",
                "There are no mod sets available.\n\nUse the 'Add Set' button to create one first.",
                parent=self
            )
            return

        # Create selection dialog
        dialog = ctk.CTkToplevel(self)
        dialog.title("Copy to Set")
        dialog.geometry("400x400")
        dialog.transient(self)
        dialog.grab_set()
        self._set_dialog_icon(dialog)

        # Center on parent
        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 400) // 2
        y = self.winfo_y() + (self.winfo_height() - 400) // 2
        dialog.geometry(f"+{x}+{y}")

        # Header
        header = ctk.CTkLabel(
            dialog, text=f"Copy '{mod_path.name}' to:",
            font=FONTS["heading"]
        )
        header.pack(pady=PADDING["medium"])

        # List of Sets
        list_frame = ctk.CTkScrollableFrame(dialog)
        list_frame.pack(fill="both", expand=True, padx=PADDING["medium"], pady=PADDING["small"])

        selected_set = [None]  # Use list to allow modification in nested function

        def on_set_click(set_path):
            selected_set[0] = set_path
            dialog.destroy()
            self._copy_mod_to_set(mod_path, set_path)

        for set_item in sets:
            set_btn = ctk.CTkButton(
                list_frame,
                text=set_item.name,
                font=FONTS["body"],
                fg_color=("gray80", "gray30"),
                hover_color=("#00CC00", "#008800"),
                text_color=("gray10", "gray90"),
                anchor="w",
                command=lambda s=set_item: on_set_click(s)
            )
            set_btn.pack(fill="x", pady=2)

        # Cancel button
        cancel_btn = ctk.CTkButton(
            dialog, text="Cancel", width=100,
            fg_color=("gray70", "gray40"),
            command=dialog.destroy
        )
        cancel_btn.pack(pady=PADDING["medium"])

    def _copy_mod_to_set(self, mod_path: Path, set_path: Path):
        """Copy a mod file or directory into a Set."""
        import shutil

        try:
            dest_path = set_path / mod_path.name

            if dest_path.exists():
                from tkinter import messagebox
                result = messagebox.askyesno(
                    "Mod Exists",
                    f"'{mod_path.name}' already exists in '{set_path.name}'.\n\nOverwrite?",
                    parent=self
                )
                if not result:
                    return

                # Remove existing
                if dest_path.is_dir():
                    shutil.rmtree(dest_path)
                else:
                    dest_path.unlink()

            # Copy the mod
            if mod_path.is_dir():
                shutil.copytree(mod_path, dest_path)
            else:
                shutil.copy2(mod_path, dest_path)

            self._set_status(f"Copied '{mod_path.name}' to '{set_path.name}'")

        except OSError as e:
            logger.error("Failed to copy mod to set: %s", e)
            self._set_status(f"Failed to copy mod: {e}")

    # ---------------------------------------------------------------
    # Set Contents Popup
    # ---------------------------------------------------------------

    def _show_set_contents_window(self, set_path: Path):
        """Show a modal popup window displaying the contents of a Set.

        Items can be deleted from the Set directly within this popup.
        The list auto-refreshes after each deletion.
        """
        import shutil

        # Create popup window (modal)
        popup = ctk.CTkToplevel(self)
        popup.title(set_path.name)
        popup.geometry("500x400")
        popup.transient(self)
        popup.grab_set()  # Make modal - prevent interaction with main window
        self._set_dialog_icon(popup)

        # Center on parent
        popup.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 500) // 2
        y = self.winfo_y() + (self.winfo_height() - 400) // 2
        popup.geometry(f"+{x}+{y}")

        # Header with Set name
        header_frame = ctk.CTkFrame(popup, fg_color="transparent")
        header_frame.pack(fill="x", padx=PADDING["medium"], pady=PADDING["medium"])

        header = ctk.CTkLabel(
            header_frame, text=set_path.name,
            font=FONTS["heading"],
            text_color=("#00CC00", "#00FF00")
        )
        header.pack(side="left")

        # Scrollable content list
        list_frame = ctk.CTkScrollableFrame(popup, fg_color=("#3d3d3d", "#1a1a1a"))
        list_frame.pack(
            fill="both", expand=True,
            padx=PADDING["medium"],
            pady=(0, PADDING["medium"]))

        # Track rows for this popup
        popup_rows = {}

        def refresh_set_contents():
            """Refresh the contents list."""
            # Clear existing
            for widget in list_frame.winfo_children():
                widget.destroy()
            popup_rows.clear()

            try:
                items = list(set_path.iterdir())
                # Show only .pak files for files
                items = [item for item in items if item.is_dir() or item.suffix.lower() == ".pak"]
                items.sort(key=lambda x: (not x.is_dir(), x.name.lower()))
            except OSError:
                items = []

            if not items:
                placeholder = ctk.CTkLabel(
                    list_frame, text="This set is empty",
                    font=FONTS["body"], text_color="gray"
                )
                placeholder.pack(pady=PADDING["large"])
                return

            for item in items:
                create_item_row(item)

        def create_item_row(item_path: Path):
            """Create a row for an item in the Set."""
            row = ctk.CTkFrame(list_frame)
            row.pack(fill="x", pady=1)

            popup_rows[item_path.name] = row

            # Icon
            if item_path.is_dir():
                icon_text = "\U0001F4C1"
                icon_color = ("#FFD700", "#FFD700")
            else:
                icon_text = "\U0001F4C4"
                icon_color = ("white", "white")

            icon_label = ctk.CTkLabel(
                row, text=icon_text,
                font=("Segoe UI Emoji", 14),
                text_color=icon_color,
                width=30
            )
            icon_label.pack(side="left", padx=(PADDING["small"], 5))

            # Name
            display_name = item_path.stem if item_path.is_file() else item_path.name
            name_label = ctk.CTkLabel(
                row, text=display_name,
                font=FONTS["body"], anchor="w"
            )
            name_label.pack(
            side="left", fill="x", expand=True,
            padx=(0, PADDING["small"]),
            pady=PADDING["small"])

            # Delete button
            trash_image = self._load_icon("icons/trash.png", size=(16, 16))
            if trash_image:
                trash_btn = ctk.CTkButton(
                    row, image=trash_image, text="", width=24, height=24,
                    fg_color="transparent", hover_color=("#ffcccc", "#4a1a1a"),
                    command=lambda p=item_path: delete_from_set(p)
                )
            else:
                trash_btn = ctk.CTkButton(
                    row, text="🗑", width=24, height=24,
                    font=FONTS["small"], text_color="red",
                    fg_color="transparent", hover_color=("#ffcccc", "#4a1a1a"),
                    command=lambda p=item_path: delete_from_set(p)
                )
            trash_btn.pack(side="right", padx=PADDING["small"])
            self._create_tooltip(trash_btn, "Delete from set")

        def delete_from_set(item_path: Path):
            """Delete an item from the Set."""
            from tkinter import messagebox

            result = messagebox.askyesno(
                "Delete from Set",
                f"Delete '{item_path.name}' from '{set_path.name}'?",
                parent=popup
            )

            if not result:
                return

            try:
                if item_path.is_dir():
                    shutil.rmtree(item_path)
                else:
                    item_path.unlink()

                self._set_status(f"Deleted '{item_path.name}' from '{set_path.name}'")
                refresh_set_contents()

            except OSError as e:
                logger.error("Failed to delete from set: %s", e)
                self._set_status(f"Failed to delete: {e}")

        # Initial population
        refresh_set_contents()

        # Close button
        close_btn = ctk.CTkButton(
            popup, text="Close", width=100,
            command=popup.destroy
        )
        close_btn.pack(pady=PADDING["medium"])

    # ---------------------------------------------------------------
    # Install Mods (Available -> Installed / Server)
    # ---------------------------------------------------------------

    def _install_all_from_set(self, set_path: Path):
        """Install all mods from a Set to the game's Paks folder or server.

        Delegates to ``_install_all_from_set_to_server`` when a server
        is selected.  For local installs, existing mods are silently
        skipped rather than overwritten.
        """
        import shutil

        logger.info("_install_all_from_set called with: %s", set_path)
        logger.info("current_server: %s", self.current_server)

        # Check if we're installing to a server
        if self.current_server:
            logger.info("Redirecting to _install_all_from_set_to_server")
            self._install_all_from_set_to_server(set_path)
            return

        if not self.current_installation or not self.current_installation.game_path:
            self._set_status("No game installation selected")
            return

        paks_dir = self.current_installation.game_path / "Moria" / "Content" / "Paks"

        if not paks_dir.exists():
            self._set_status("Paks folder does not exist")
            return

        try:
            # Get all mod files in the Set
            items = list(set_path.iterdir())
            # Filter to .pak files and directories
            items = [item for item in items if item.is_dir() or item.suffix.lower() == ".pak"]

            if not items:
                self._set_status(f"'{set_path.name}' is empty")
                return

            installed_count = 0
            skipped_count = 0

            for item in items:
                dest = paks_dir / item.name

                # Check if exists
                if dest.exists():
                    skipped_count += 1
                    continue

                # Copy
                if item.is_dir():
                    shutil.copytree(item, dest)
                else:
                    shutil.copy2(item, dest)

                installed_count += 1

            # Refresh installed mods
            self._refresh_mods_list()

            # Status message
            if skipped_count > 0:
                self._set_status(
                    f"Installed {installed_count} mod(s) from "
                    f"'{set_path.name}' ({skipped_count} "
                    "already existed)")
            else:
                self._set_status(f"Installed {installed_count} mod(s) from '{set_path.name}'")

        except OSError as e:
            logger.error("Failed to install mods from set %s: %s", set_path.name, e)
            self._set_status(f"Failed to install: {e}")

    def _install_mod_from_available(self, item_path: Path):
        """Copy a mod from Available Mods to Installed Mods (game's Paks folder or server).

        Directories are copied with ``shutil.copytree``; for ``.pak`` files
        all three companion files are copied together.  Offers an
        overwrite prompt when the destination already exists.  Delegates
        to ``_install_mod_to_server`` when a server is selected.
        """
        import shutil

        logger.info("_install_mod_from_available called with: %s", item_path)
        logger.info("current_server: %s", self.current_server)

        # Check if we're installing to a server
        if self.current_server:
            logger.info("Redirecting to _install_mod_to_server")
            self._install_mod_to_server(item_path)
            return

        if not self.current_installation or not self.current_installation.game_path:
            self._set_status("No game installation selected")
            return

        paks_dir = self.current_installation.game_path / "Moria" / "Content" / "Paks"

        if not paks_dir.exists():
            self._set_status("Paks folder does not exist")
            return

        mod_name = item_path.stem if item_path.is_file() else item_path.name

        try:
            if item_path.is_dir():
                # Check if directory already exists
                dest_path = paks_dir / item_path.name
                if dest_path.exists():
                    choice = self._show_overwrite_skip_dialog(
                        "Already Installed",
                        f"The mod '{item_path.name}' is already "
                        "installed.\n\nWould you like to "
                        "overwrite it?"
                    )
                    if choice == "skip":
                        return
                    # Overwrite: remove existing directory first
                    shutil.rmtree(str(dest_path))

                # Copy directory
                shutil.copytree(str(item_path), str(dest_path))
                self._set_status(f"Installed '{item_path.name}' to game")
            else:
                # File (.pak) - check if any of the 3 files already exist
                extensions = [".pak", ".ucas", ".utoc"]
                existing_files = []
                for ext in extensions:
                    dest_file = paks_dir / f"{mod_name}{ext}"
                    if dest_file.exists():
                        existing_files.append(dest_file.name)

                if existing_files:
                    choice = self._show_overwrite_skip_dialog(
                        "Already Installed",
                        f"The mod '{mod_name}' is already "
                        "installed.\n\nWould you like to "
                        "overwrite it?"
                    )
                    if choice == "skip":
                        return
                    # Overwrite: remove existing files first
                    for ext in extensions:
                        dest_file = paks_dir / f"{mod_name}{ext}"
                        if dest_file.exists():
                            dest_file.unlink()

                # Copy all 3 files
                backup_root = (
                    self.config_manager.config.settings.backup_location
                    or GamePaths.BACKUP_DEFAULT
                )
                mods_backup_path = backup_root / "mods"

                copied_count = 0
                for ext in extensions:
                    source_file = mods_backup_path / f"{mod_name}{ext}"
                    if source_file.exists():
                        dest_file = paks_dir / source_file.name
                        shutil.copy2(str(source_file), str(dest_file))
                        copied_count += 1

                self._set_status(f"Installed '{mod_name}' ({copied_count} files) to game")

            # Refresh the installed mods list
            self._refresh_mods_list()

        except (OSError, IOError, shutil.Error) as e:
            self._set_status(f"Failed to install mod: {e}")

    # ---------------------------------------------------------------
    # Server Upload (Install to Server)
    # ---------------------------------------------------------------

    def _install_mod_to_server(self, item_path: Path):
        """Upload a mod from Available Mods to the server's Paks folder.

        For directory mods, a remote directory is created first, then
        every ``.pak``/``.ucas``/``.utoc`` inside it is uploaded.
        For loose ``.pak`` mods, the three companion files are uploaded
        directly into the server's Paks root.
        """
        if not self.current_server:
            self._set_status("No server selected")
            return

        server = self.current_server
        pak_path = server.get("pak_path", "")
        server_name = server.get("name", "Unknown")
        protocol = server.get("protocol", "FTP")

        logger.debug(
            "_install_mod_to_server: server=%s, protocol=%s, pak_path='%s', item_path='%s'",
            server_name, protocol, pak_path, item_path
        )

        if not pak_path:
            self._set_status("No Paks path configured for server")
            return

        # Ensure connected
        if not self._server_ensure_connected(server):
            self._set_status("Failed to connect to server")
            return

        mod_name = item_path.stem if item_path.is_file() else item_path.name

        try:
            extensions = [".pak", ".ucas", ".utoc"]
            uploaded_count = 0

            if item_path.is_dir():
                # Directory mod - create directory on server and upload files into it
                logger.info("Processing directory mod: %s", item_path.name)

                # Create the directory on the server
                sep = "" if pak_path.endswith("/") else "/"
                remote_dir = f"{pak_path}{sep}{item_path.name}"
                self._set_status(
                    f"Creating directory {item_path.name}...")
                if not self._server_mkdir(server, remote_dir):
                    self._set_status("Failed to create directory on server")
                    return

                # Find all .pak files in the directory
                pak_files = list(item_path.glob("*.pak"))
                logger.info("Found %d .pak files in directory", len(pak_files))

                if not pak_files:
                    self._set_status(f"No .pak files found in '{item_path.name}'")
                    return

                for pak_file in pak_files:
                    pak_name = pak_file.stem
                    # Upload all 3 files for this mod into the remote directory
                    for ext in extensions:
                        source_file = item_path / f"{pak_name}{ext}"
                        if source_file.exists():
                            remote_file = f"{remote_dir}/{source_file.name}"

                            logger.info("Uploading %s to %s", source_file.name, remote_file)
                            self._set_status(f"Uploading {source_file.name}...")
                            if self._server_upload_file(server, str(source_file), remote_file):
                                uploaded_count += 1
                                logger.info("Uploaded mod to server: %s", remote_file)
                            else:
                                logger.warning("Failed to upload: %s", source_file.name)
            else:
                # File (.pak) - upload all 3 files (.pak, .ucas, .utoc) directly to Paks
                # Get source directory from the item_path's parent
                source_dir = item_path.parent

                for ext in extensions:
                    source_file = source_dir / f"{mod_name}{ext}"
                    if source_file.exists():
                        sep = ("" if pak_path.endswith("/")
                               else "/")
                        remote_file = (
                            f"{pak_path}{sep}"
                            f"{source_file.name}")

                        logger.info(
                            "Uploading %s to %s",
                            source_file.name, remote_file)
                        self._set_status(
                            f"Uploading {source_file.name}...")
                        if self._server_upload_file(server, str(source_file), remote_file):
                            uploaded_count += 1
                            logger.info("Uploaded mod to server: %s", remote_file)
                        else:
                            logger.warning("Failed to upload: %s", source_file.name)

            if uploaded_count > 0:
                self._set_status(
                    f"Installed '{mod_name}' "
                    f"({uploaded_count} files) to "
                    f"{server_name}")
            else:
                self._set_status(f"No files found to upload for '{mod_name}'")

            # Refresh the installed mods list
            self._refresh_mods_list()

        except Exception as e:
            logger.error("Failed to install mod to server: %s", e)
            self._set_status(f"Failed to install mod: {e}")

    def _install_all_from_set_to_server(self, set_path: Path):
        """Install all mods from a Set to the server's Paks folder.

        Processes both direct ``.pak`` files in the Set and subdirectory
        mods (directories containing ``.pak`` files).  Each subdirectory
        is recreated on the remote server before uploading its contents.
        """
        logger.info("_install_all_from_set_to_server called with: %s", set_path)

        if not self.current_server:
            self._set_status("No server selected")
            return

        server = self.current_server
        pak_path = server.get("pak_path", "")
        server_name = server.get("name", "Unknown")

        logger.info("Server: %s, pak_path: %s", server_name, pak_path)

        if not pak_path:
            self._set_status("No Paks path configured for server")
            return

        # Ensure connected
        logger.info("Checking connection...")
        if not self._server_ensure_connected(server):
            self._set_status("Failed to connect to server")
            return

        logger.info("Connected, listing files in set...")

        try:
            # Get all items in the Set
            items = list(set_path.iterdir())
            logger.info("Found %d items in set", len(items))

            uploaded_count = 0
            extensions = [".pak", ".ucas", ".utoc"]

            # First, look for direct .pak files in the set
            pak_files = [item for item in items if item.is_file() and item.suffix.lower() == ".pak"]
            logger.info("Found %d direct .pak files", len(pak_files))

            # Also look for subdirectories that contain .pak files (mod directories inside set)
            mod_dirs = [item for item in items if item.is_dir()]
            logger.info("Found %d subdirectories", len(mod_dirs))

            # Process direct .pak files
            for pak_file in pak_files:
                mod_name = pak_file.stem
                logger.info("Processing direct mod: %s", mod_name)

                for ext in extensions:
                    source_file = set_path / f"{mod_name}{ext}"
                    if source_file.exists():
                        sep = ("" if pak_path.endswith("/")
                               else "/")
                        remote_file = (
                            f"{pak_path}{sep}"
                            f"{source_file.name}")

                        logger.info(
                            "Uploading %s to %s",
                            source_file.name, remote_file)
                        self._set_status(f"Uploading {source_file.name}...")
                        if self._server_upload_file(server, str(source_file), remote_file):
                            uploaded_count += 1
                            logger.info("Uploaded mod to server: %s", remote_file)
                        else:
                            logger.warning("Failed to upload: %s", source_file.name)

            # Process subdirectories (mod directories) - create dir on server and upload into it
            for mod_dir in mod_dirs:
                # Find .pak files in this subdirectory
                sub_pak_files = list(mod_dir.glob("*.pak"))
                logger.info("Directory %s has %d .pak files", mod_dir.name, len(sub_pak_files))

                if not sub_pak_files:
                    continue

                # Create the directory on the server
                sep = "" if pak_path.endswith("/") else "/"
                remote_dir = f"{pak_path}{sep}{mod_dir.name}"
                self._set_status(
                    f"Creating directory {mod_dir.name}...")
                if not self._server_mkdir(server, remote_dir):
                    logger.warning("Failed to create directory: %s", remote_dir)
                    continue

                for pak_file in sub_pak_files:
                    mod_name = pak_file.stem

                    for ext in extensions:
                        source_file = mod_dir / f"{mod_name}{ext}"
                        if source_file.exists():
                            remote_file = f"{remote_dir}/{source_file.name}"

                            logger.info("Uploading %s to %s", source_file.name, remote_file)
                            self._set_status(f"Uploading {source_file.name}...")
                            if self._server_upload_file(server, str(source_file), remote_file):
                                uploaded_count += 1
                                logger.info("Uploaded mod to server: %s", remote_file)
                            else:
                                logger.warning("Failed to upload: %s", source_file.name)

            logger.info("Upload complete, uploaded %d files", uploaded_count)

            if uploaded_count == 0:
                self._set_status(f"'{set_path.name}' has no .pak files to upload")
            else:
                self._set_status(
                    f"Installed {uploaded_count} file(s) from "
                    f"'{set_path.name}' to {server_name}")

            # Refresh installed mods
            self._refresh_mods_list()

        except Exception as e:
            logger.error("Failed to install mods from set to server %s: %s", set_path.name, e)
            self._set_status(f"Failed to install: {e}")

    # ---------------------------------------------------------------
    # Available Mod File Organization and Deletion
    # ---------------------------------------------------------------

    def _organize_available_mod_files(self, item_path: Path):
        """Organize mod files into a folder in Available Mods, or delete if folder exists.

        If a directory with the mod name doesn't exist:
            - Create a directory with the mod name
            - Move all 3 files (.pak, .ucas, .utoc) into it

        If a directory with the mod name already exists:
            - Delete the 3 files (since they're duplicates of what's in the folder)
        """
        import shutil

        mod_name = item_path.stem  # Filename without extension
        mods_dir = item_path.parent  # The mods backup directory

        folder_path = mods_dir / mod_name

        try:
            if folder_path.exists() and folder_path.is_dir():
                # A folder with this mod's name already exists, so the
                # loose .pak/.ucas/.utoc are duplicates -- remove them.
                extensions = [".pak", ".ucas", ".utoc"]
                deleted_count = 0
                for ext in extensions:
                    file_path = mods_dir / f"{mod_name}{ext}"
                    if file_path.exists():
                        file_path.unlink()
                        deleted_count += 1

                self._set_status(f"Deleted {deleted_count} duplicate files (folder already exists)")
            else:
                # Create folder and move files into it
                folder_path.mkdir(exist_ok=True)

                extensions = [".pak", ".ucas", ".utoc"]
                moved_count = 0
                for ext in extensions:
                    source_file = mods_dir / f"{mod_name}{ext}"
                    if source_file.exists():
                        dest_file = folder_path / source_file.name
                        shutil.move(str(source_file), str(dest_file))
                        moved_count += 1

                self._set_status(f"Created folder '{mod_name}' with {moved_count} files")

            # Refresh the available mods list
            self._refresh_available_mods()

        except (OSError, IOError, shutil.Error) as e:
            self._set_status(f"Failed to organize mod files: {e}")

    def _prompt_delete_available_mod(self, item_path: Path):
        """Prompt to delete a mod from the Available Mods directory."""
        import os
        import shutil
        import stat

        mod_name = item_path.name

        # Available Mods deletion is always allowed -- the "enable_deletion"
        # setting only guards removal of files inside the game installation.
        if not self._show_delete_confirm_dialog(mod_name, "mod"):
            return

        def remove_readonly(func, path, _excinfo):
            """shutil.rmtree onexc callback: strip read-only and retry."""
            os.chmod(path, stat.S_IWRITE)
            func(path)

        def clear_readonly_recursive(path: Path):
            """Clear read-only attribute from all files in a directory.

            Unreal Engine pak files are often marked read-only after
            extraction; this must be undone before deletion on Windows.
            """
            try:
                for root, dirs, files in os.walk(str(path)):
                    for name in files:
                        file_path = os.path.join(root, name)
                        os.chmod(file_path, stat.S_IWRITE | stat.S_IREAD)
                    for name in dirs:
                        dir_path = os.path.join(root, name)
                        os.chmod(dir_path, stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)
                # Also clear on the root path itself
                os.chmod(str(path), stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)
            except OSError as e:
                logger.warning("Could not clear read-only attributes: %s", e)

        try:
            if item_path.exists():
                if item_path.is_dir():
                    # Clear read-only attributes first, then delete with error handler
                    clear_readonly_recursive(item_path)
                    shutil.rmtree(item_path, onexc=remove_readonly)
                else:
                    # Clear read-only on single file before deletion
                    os.chmod(str(item_path), stat.S_IWRITE | stat.S_IREAD)
                    item_path.unlink()
                logger.info("Deleted mod: %s", item_path)
                self._set_status(f"Deleted mod '{mod_name}'")
            else:
                self._set_status(f"Mod not found: '{mod_name}'")

            # Clear selection and refresh the available mods list
            self.selected_available_mod = None
            self._refresh_available_mods()

        except (OSError, IOError) as e:
            logger.error("Error deleting mod %s: %s", mod_name, e)
            self._set_status(f"Error deleting mod: {e}")
