"""Mixin class providing import/backup-import functionality for MainWindow."""

from __future__ import annotations

import os
import re
import shutil
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from ..config.paths import GamePaths
from ..core.backup_index import BackupIndexManager
from ..logging_config import get_logger
from .styles import COLORS, FONTS, PADDING, THEME_COLORS

logger = get_logger("import_mixin")

# Regex pattern to match Windows copy suffixes like " (2)", " (3)", etc.
_WINDOWS_COPY_SUFFIX_PATTERN = re.compile(r" \(\d+\)$")


def _strip_windows_copy_suffix(filename: str) -> str:
    """Strip Windows copy suffixes like ' (2)', ' (3)' from filenames.

    When Windows copies a file, it appends ' (2)', ' (3)', etc.
    This function removes those suffixes to get the original filename.

    Args:
        filename: Filename (without extension) to clean

    Returns:
        Filename with Windows copy suffix removed

    Examples:
        >>> _strip_windows_copy_suffix("MC_12345678 (2)")
        'MC_12345678'
        >>> _strip_windows_copy_suffix("MW_ABCD1234")
        'MW_ABCD1234'
    """
    return _WINDOWS_COPY_SUFFIX_PATTERN.sub("", filename)


class ImportMixin:
    """Mixin providing import/backup-import methods for MainWindow.

    Allows users to bulk-import archived Moria save files from an arbitrary
    directory on disk into the application's managed backup structure.  The
    workflow is:

        1. User selects a source directory via the Import dialog.
        2. The directory is recursively scanned for world (MW_*.sav) and
           character (MC_*.sav) save files, with a progress overlay.
        3. Duplicate files (same filename + modification timestamp rounded to
           the minute) are detected and logged to a dedicated log file.
        4. A sortable preview dialog displays all unique files found.
        5. On confirmation the files are copied into the backup tree using the
           same folder hierarchy as the normal Backup All operation, keyed by
           the file's own modification timestamp so that re-imports are
           idempotent.

    Expected attributes provided by the host MainWindow:
        parser              -- SaveParser instance for reading save metadata
        config_manager      -- ConfigManager with backup_location setting
        current_mode        -- Currently selected sidebar mode string
        _set_status()       -- Status bar update helper
        _set_dialog_icon()  -- Apply the app icon to a Toplevel
        _refresh_restore_list() -- Reload the restore-mode file listing
    """

    # --- Directory Scanning & Progress UI ---

    def _show_import_dialog(self):
        """Show the import dialog for archived save files.

        Prompts user to select a directory, then recursively scans for
        world (MW_*.sav) and character (MC_*.sav) files, displaying
        results in a preview dialog. Detects and logs duplicates.
        """
        # Show directory selector
        selected_dir = filedialog.askdirectory(
            parent=self,
            title="Select Directory with Archived Save Files",
            mustexist=True
        )

        if not selected_dir:
            return  # User cancelled

        selected_path = Path(selected_dir)

        # Create progress dialog
        progress_dialog = ctk.CTkToplevel(self)
        progress_dialog.title("Scanning Files")
        progress_dialog.geometry("400x150")
        progress_dialog.resizable(False, False)
        progress_dialog.transient(self)
        progress_dialog.grab_set()
        self._set_dialog_icon(progress_dialog)

        # Center on parent
        progress_dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 400) // 2
        y = self.winfo_y() + (self.winfo_height() - 150) // 2
        progress_dialog.geometry(f"+{x}+{y}")

        # Progress UI
        progress_frame = ctk.CTkFrame(progress_dialog)
        progress_frame.pack(
            fill="both", expand=True,
            padx=PADDING["medium"],
            pady=PADDING["medium"])

        status_label = ctk.CTkLabel(
            progress_frame,
            text=f"Scanning: {selected_path.name}",
            font=FONTS["heading"]
        )
        status_label.pack(pady=(PADDING["small"], PADDING["medium"]))

        progress_label = ctk.CTkLabel(
            progress_frame,
            text="Counting files...",
            font=FONTS["body"]
        )
        progress_label.pack(pady=PADDING["small"])

        files_found_label = ctk.CTkLabel(
            progress_frame,
            text="Save files found: 0",
            font=FONTS["small"],
            text_color="gray"
        )
        files_found_label.pack(pady=PADDING["small"])

        # Mutable dict used as cancel flag so the nested closure can modify it
        scan_cancelled = {"value": False}

        def cancel_scan():
            scan_cancelled["value"] = True
            progress_dialog.destroy()

        cancel_btn = ctk.CTkButton(
            progress_frame,
            text="Cancel",
            width=80,
            fg_color=COLORS["danger"],
            hover_color=COLORS["danger_hover"],
            command=cancel_scan
        )
        cancel_btn.pack(pady=PADDING["small"])

        progress_dialog.protocol("WM_DELETE_WINDOW", cancel_scan)
        progress_dialog.update()

        # Scan recursively for save files
        all_files = []
        seen_keys = {}  # Track (filename, modified_timestamp) -> first file info
        duplicates = []  # Track duplicate files for logging
        files_processed = 0
        update_interval = 50  # Update UI every N files

        for root, _dirs, files in os.walk(selected_path):
            if scan_cancelled["value"]:
                break

            root_path = Path(root)
            for filename in files:
                if scan_cancelled["value"]:
                    break

                files_processed += 1

                # Update progress periodically
                if files_processed % update_interval == 0:
                    progress_label.configure(text=f"Processed {files_processed:,} files...")
                    files_found_label.configure(text=f"Save files found: {len(all_files):,}")
                    progress_dialog.update()

                file_path = root_path / filename

                # Check for world files (MW_*.sav); exclude backup
                # suffixes like ".sav.bak" via the ".sav." guard
                if (filename.startswith("MW_")
                        and filename.endswith(".sav")
                        and ".sav." not in filename):
                    info = self.parser.parse_world_save(file_path)
                    if info:
                        try:
                            stat = file_path.stat()
                            modified = datetime.fromtimestamp(stat.st_mtime)
                        except OSError:
                            modified = None
                        file_info = {
                            "path": file_path,
                            "filename": filename,
                            "type": "World",
                            "name": info.world_name,
                            "modified": modified,
                        }
                        all_files.append(file_info)

                # Check for character files (MC_*.sav)
                elif (filename.startswith("MC_")
                        and filename.endswith(".sav")
                        and ".sav." not in filename):
                    info = self.parser.parse_character_save(file_path)
                    if info:
                        try:
                            stat = file_path.stat()
                            modified = datetime.fromtimestamp(stat.st_mtime)
                        except OSError:
                            modified = None
                        file_info = {
                            "path": file_path,
                            "filename": filename,
                            "type": "Character",
                            "name": info.display_name,
                            "modified": modified,
                        }
                        all_files.append(file_info)

        # Close progress dialog if not cancelled
        if not scan_cancelled["value"]:
            progress_dialog.destroy()
        else:
            self._set_status("Import cancelled")
            return

        # Deduplicate: two files are considered identical when they share the
        # same filename and the same modification timestamp (to the minute).
        # This catches Windows Explorer copy-paste duplicates and copies
        # spread across multiple subdirectories.
        found_files = []
        for file_info in all_files:
            if file_info["modified"]:
                time_key = file_info["modified"].strftime("%Y-%m-%d %H:%M")
            else:
                time_key = "Unknown"
            dup_key = (file_info["filename"], time_key)

            if dup_key in seen_keys:
                # This is a duplicate
                duplicates.append({
                    "duplicate": file_info,
                    "original": seen_keys[dup_key]
                })
            else:
                seen_keys[dup_key] = file_info
                found_files.append(file_info)

        # Log duplicates if any were found
        duplicate_count = len(duplicates)
        if duplicates:
            self._write_duplicate_import_log(duplicates, selected_path)

        self._set_status("Ready")

        # Show results dialog
        self._show_import_preview_dialog(
            found_files, source_dir=selected_path,
            duplicate_count=duplicate_count)

    # --- Duplicate Logging ---

    def _write_duplicate_import_log(self, duplicates: list, source_dir: Path):
        """Write duplicate import information to a log file.

        Args:
            duplicates: List of dicts with 'duplicate' and 'original' file info
            source_dir: The directory that was scanned
        """
        log_path = GamePaths.CONFIG_DIR / "Duplicate imports.log"

        try:
            GamePaths.ensure_config_dir()

            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"\n{'='*60}\n")
                f.write(f"Import Scan: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Source Directory: {source_dir}\n")
                f.write(f"Duplicates Found: {len(duplicates)}\n")
                f.write(f"{'='*60}\n\n")

                for i, dup_info in enumerate(duplicates, 1):
                    dup = dup_info["duplicate"]
                    orig = dup_info["original"]

                    f.write(f"Duplicate #{i}:\n")
                    f.write(f"  Filename: {dup['filename']}\n")
                    f.write(f"  Type: {dup['type']}\n")
                    f.write(f"  Name: {dup['name']}\n")
                    if dup["modified"]:
                        f.write(f"  Modified: {dup['modified'].strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"  Duplicate Path: {dup['path']}\n")
                    f.write(f"  Original Path: {orig['path']}\n")
                    f.write("\n")

            logger.info("Wrote %d duplicate entries to %s", len(duplicates), log_path)
        except (OSError, IOError) as e:
            logger.error("Failed to write duplicate import log: %s", e)

    # --- Import Preview Dialog ---

    def _show_import_preview_dialog(
        self, found_files: list,
        source_dir: Path, duplicate_count: int = 0
    ):
        """Show preview dialog with found save files and sorting capability.

        Args:
            found_files: List of dicts with file info (duplicates already removed)
            source_dir: The directory that was scanned
            duplicate_count: Number of duplicate files that were skipped
        """
        dialog = ctk.CTkToplevel(self)
        dialog.title("Import Preview")
        dialog.geometry("750x550")
        dialog.resizable(True, True)
        dialog.transient(self)
        dialog.grab_set()
        self._set_dialog_icon(dialog)

        # Center on parent
        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 750) // 2
        y = self.winfo_y() + (self.winfo_height() - 550) // 2
        dialog.geometry(f"+{x}+{y}")

        # Container
        container = ctk.CTkFrame(dialog)
        container.pack(fill="both", expand=True, padx=PADDING["medium"], pady=PADDING["medium"])

        # Top button row (Cancel on left, Import All on right)
        top_btn_frame = ctk.CTkFrame(container, fg_color="transparent")
        top_btn_frame.pack(fill="x", pady=(0, PADDING["small"]))

        # Cancel button (red with white text) - top left
        cancel_btn = ctk.CTkButton(
            top_btn_frame,
            text="Cancel",
            width=100,
            fg_color=COLORS["danger"],
            hover_color=COLORS["danger_hover"],
            text_color="white",
            command=dialog.destroy
        )
        cancel_btn.pack(side="left")

        # Import All button (green with white text) - top right (only if files found)
        if found_files:
            def do_import_all():
                dialog.destroy()
                self._import_all_files(found_files)

            import_all_btn = ctk.CTkButton(
                top_btn_frame,
                text="Import All",
                width=100,
                fg_color=COLORS["success"],
                hover_color=COLORS["success_hover"],
                text_color="white",
                command=do_import_all
            )
            import_all_btn.pack(side="right")

        # Force buttons to render immediately
        dialog.update()

        # Header
        header_text = f"Found {len(found_files)} unique save file(s) in:"
        header_label = ctk.CTkLabel(
            container,
            text=header_text,
            font=FONTS["heading"]
        )
        header_label.pack(pady=(PADDING["small"], 0))

        # Source directory
        source_label = ctk.CTkLabel(
            container,
            text=str(source_dir),
            font=FONTS["small"],
            text_color="gray"
        )
        source_label.pack(pady=(0, PADDING["small"]))

        if not found_files:
            # No files found
            no_files_label = ctk.CTkLabel(
                container,
                text=(
                    "No world or character save files found."
                    "\n\nLooking for files matching:"
                    "\n- MW_*.sav (World saves)"
                    "\n- MC_*.sav (Character saves)"),
                font=FONTS["body"],
                justify="center"
            )
            no_files_label.pack(expand=True)
        else:
            # Sorting state
            sort_state = {"column": "type", "reverse": False}
            files_list = list(found_files)  # Make a copy for sorting

            # Scrollable list frame (will be rebuilt on sort)
            list_container = ctk.CTkFrame(container, fg_color="transparent")
            list_container.pack(fill="both", expand=True, pady=PADDING["small"])

            def sort_files(column: str):
                """Sort files by the specified column."""
                # Toggle direction if same column clicked again
                if sort_state["column"] == column:
                    sort_state["reverse"] = not sort_state["reverse"]
                else:
                    sort_state["column"] = column
                    sort_state["reverse"] = False

                # Sort the list
                if column == "type":
                    files_list.sort(key=lambda f: f["type"], reverse=sort_state["reverse"])
                elif column == "name":
                    files_list.sort(
                        key=lambda f: (f["name"] or "").lower(),
                        reverse=sort_state["reverse"])
                elif column == "filename":
                    files_list.sort(
                        key=lambda f: f["filename"].lower(),
                        reverse=sort_state["reverse"])
                elif column == "modified":
                    files_list.sort(
                        key=lambda f: f["modified"] or datetime.min,
                        reverse=sort_state["reverse"]
                    )

                rebuild_list()

            def rebuild_list():
                """Rebuild the file list display."""
                # Clear existing list
                for widget in list_container.winfo_children():
                    widget.destroy()

                list_frame = ctk.CTkScrollableFrame(list_container, fg_color=THEME_COLORS["bg_pane_content"])
                list_frame.pack(fill="both", expand=True)

                # Column headers (clickable for sorting)
                header_row = ctk.CTkFrame(list_frame, fg_color="transparent")
                header_row.pack(fill="x", padx=PADDING["small"], pady=(0, PADDING["small"]))

                def make_header(text: str, column: str, width: int):
                    """Create a clickable column header."""
                    arrow = ""
                    if sort_state["column"] == column:
                        arrow = " \u25bc" if sort_state["reverse"] else " \u25b2"
                    btn = ctk.CTkButton(
                        header_row, text=text + arrow, font=FONTS["small_bold"],
                        width=width, anchor="w", fg_color="transparent",
                        hover_color=("gray70", "gray40"), text_color=COLORS["primary"],
                        command=lambda c=column: sort_files(c)
                    )
                    btn.pack(side="left", padx=(0, PADDING["small"]))

                make_header("Type", "type", 80)
                make_header("Name", "name", 180)
                make_header("Filename", "filename", 160)
                make_header("Modified", "modified", 140)

                # Separator
                sep = ctk.CTkFrame(list_frame, height=1, fg_color="gray50")
                sep.pack(fill="x", padx=PADDING["small"], pady=2)

                # Update to show headers before building rows
                dialog.update_idletasks()

                # File rows - update UI periodically to prevent freezing
                update_interval = 100
                for i, file_info in enumerate(files_list):
                    try:
                        # Check if dialog still exists
                        if not dialog.winfo_exists():
                            return

                        row = ctk.CTkFrame(list_frame, fg_color="transparent")
                        row.pack(fill="x", padx=PADDING["small"], pady=1)

                        # Type (with color coding)
                        type_color = (
                            COLORS["primary"]
                            if file_info["type"] == "World"
                            else COLORS["success"])
                        ctk.CTkLabel(
                            row, text=file_info["type"], font=FONTS["small"],
                            width=80, anchor="w", text_color=type_color
                        ).pack(side="left")

                        # Name
                        ctk.CTkLabel(
                            row, text=file_info["name"] or "Unknown", font=FONTS["small"],
                            width=180, anchor="w"
                        ).pack(side="left", padx=PADDING["small"])

                        # Filename
                        ctk.CTkLabel(
                            row, text=file_info["filename"], font=FONTS["small"],
                            width=160, anchor="w", text_color="gray"
                        ).pack(side="left", padx=PADDING["small"])

                        # Modified date
                        if file_info["modified"]:
                            date_str = file_info["modified"].strftime("%Y-%m-%d %H:%M")
                        else:
                            date_str = "Unknown"
                        ctk.CTkLabel(
                            row, text=date_str, font=FONTS["small"],
                            width=140, anchor="w", text_color="gray"
                        ).pack(side="left", padx=PADDING["small"])

                        # Update UI periodically to keep it responsive
                        if (i + 1) % update_interval == 0:
                            dialog.update_idletasks()
                    except tk.TclError:
                        # Dialog was closed during list building
                        return

            # Initial sort by type
            sort_files("type")

            # Summary by type
            worlds = sum(1 for f in found_files if f["type"] == "World")
            chars = sum(1 for f in found_files if f["type"] == "Character")
            summary_text = f"Worlds: {worlds}  |  Characters: {chars}"
            if duplicate_count > 0:
                summary_text += f"  |  Duplicates skipped: {duplicate_count}"
            summary_label = ctk.CTkLabel(
                container,
                text=summary_text,
                font=FONTS["small"],
                text_color="gray"
            )
            summary_label.pack(pady=(PADDING["small"], PADDING["medium"]))

        # Handle window close
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)

        # Wait for dialog to close
        dialog.wait_window()

    # --- File Import Execution ---

    def _import_all_files(self, files_to_import: list):
        """Import all scanned files using the same backup structure as Backup All.

        Creates backups in the configured backup location:
            backup_location/
                worlds/
                    World Name/
                        2026-01-16_143052/
                            MW_12345678.sav
                characters/
                    Character Name/
                        2026-01-16_143052/
                            MC_12345678.sav

        Args:
            files_to_import: List of dicts with file info from scan
        """
        if not files_to_import:
            self._set_status("No files to import")
            return

        try:
            # Get backup root from config, or use default
            backup_root = (
                self.config_manager.config.settings.backup_location
                or GamePaths.BACKUP_DEFAULT
            )

            imported_worlds = 0
            imported_chars = 0
            skipped = 0

            for file_info in files_to_import:
                file_path = file_info["path"]
                item_name = file_info["name"] or "Unknown"
                file_type = file_info["type"]
                modified = file_info["modified"]

                # Determine category based on type
                category = "worlds" if file_type == "World" else "characters"

                # Get or create the backup directory using the index manager
                index_manager = BackupIndexManager(backup_root, category)
                # Strip Windows copy suffixes like " (2)" from filenames
                base_filename = _strip_windows_copy_suffix(file_path.stem)  # e.g., "MW_12345678"
                item_backup_dir = index_manager.get_backup_directory(base_filename, item_name)

                # Get the file's modification timestamp (not current time)
                if modified:
                    timestamp_dir_name = modified.strftime("%Y-%m-%d_%H%M%S")
                else:
                    # Fallback to current time if no modification time
                    timestamp_dir_name = datetime.now().strftime("%Y-%m-%d_%H%M%S")

                # Create timestamp subdirectory
                timestamp_dir = item_backup_dir / timestamp_dir_name
                timestamp_dir.mkdir(parents=True, exist_ok=True)

                # Backup filename uses the clean base filename (without copy suffixes)
                backup_path = timestamp_dir / f"{base_filename}.sav"

                # Idempotency: skip if the same timestamp slot already has a file
                if backup_path.exists():
                    skipped += 1
                    continue

                # copy2 preserves the original file metadata (timestamps, etc.)
                shutil.copy2(file_path, backup_path)

                if file_type == "World":
                    imported_worlds += 1
                else:
                    imported_chars += 1

            # Build status message
            parts = []
            if imported_worlds > 0:
                parts.append(f"{imported_worlds} world(s)")
            if imported_chars > 0:
                parts.append(f"{imported_chars} character(s)")
            if skipped > 0:
                parts.append(f"{skipped} skipped (already exist)")

            if parts:
                self._set_status(f"Imported: {', '.join(parts)}")
            else:
                self._set_status("No new files imported (all already exist)")

            # Refresh the restore list if in restore mode
            if self.current_mode == "restore":
                self._refresh_restore_list()

        except (OSError, IOError, shutil.Error) as e:
            logger.error("Import error: %s", e)
            self._set_status(f"Import failed: {e}")
