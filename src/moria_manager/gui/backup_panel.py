"""Backup panel widget for managing backups of a single installation

NOTE: This module is not currently used. The main_window.py uses BackupIndexManager
for individual .sav file backups instead of zip-based backups.
"""

# """Backup panel widget for managing backups of a single installation"""
#
# from datetime import datetime
# from tkinter import messagebox
# from typing import Callable, Optional
#
# import customtkinter as ctk
#
# from ..config.schema import BackupRecord, Installation
# from ..core.backup_service import BackupError, BackupService, RestoreError
# from .styles import COLORS, FONTS, PADDING
#
#
# class BackupPanel(ctk.CTkFrame):
#     """Panel for managing backups of a single game installation.
#
#     Displays a list of backups with options to create new backups,
#     restore from backups, and delete backups.
#     """
#
#     def __init__(
#         self,
#         master,
#         installation: Installation,
#         backup_service: BackupService,
#         on_status_change: Optional[Callable[[str], None]] = None,
#         **kwargs
#     ):
#         """Initialize the backup panel.
#
#         Args:
#             master: Parent widget
#             installation: The installation this panel manages
#             backup_service: Backup service instance
#             on_status_change: Callback for status updates
#             **kwargs: Additional arguments for CTkFrame
#         """
#         super().__init__(master, **kwargs)
#
#         self.installation = installation
#         self.backup_service = backup_service
#         self.on_status_change = on_status_change
#
#         self._create_ui()
#         self._refresh_backup_list()
#
#     def _create_ui(self):
#         """Create the panel UI."""
#         # Header section
#         header = ctk.CTkFrame(self, fg_color="transparent")
#         header.pack(fill="x", padx=PADDING["medium"], pady=PADDING["medium"])
#
#         # Save path display
#         path_frame = ctk.CTkFrame(header, fg_color="transparent")
#         path_frame.pack(fill="x")
#
#         path_label = ctk.CTkLabel(path_frame, text="Save Location:", font=FONTS["body"])
#         path_label.pack(side="left")
#
#         path_value = ctk.CTkLabel(
#             path_frame,
#             text=str(self.installation.save_path) if self.installation.save_path else "Not configured",
#             font=FONTS["small"],
#             text_color="gray"
#         )
#         path_value.pack(side="left", padx=(10, 0))
#
#         # Status indicator
#         if self.installation.save_path and self.installation.save_path.exists():
#             status = ctk.CTkLabel(path_frame, text="OK", text_color="green", font=FONTS["small"])
#         else:
#             status = ctk.CTkLabel(path_frame, text="Not Found", text_color="orange", font=FONTS["small"])
#         status.pack(side="right")
#
#         # Backup controls
#         controls = ctk.CTkFrame(self, fg_color="transparent")
#         controls.pack(fill="x", padx=PADDING["medium"], pady=(0, PADDING["medium"]))
#
#         # Description entry for new backup
#         self.description_var = ctk.StringVar()
#         self.description_entry = ctk.CTkEntry(
#             controls,
#             placeholder_text="Backup description (optional)",
#             textvariable=self.description_var,
#             width=300,
#         )
#         self.description_entry.pack(side="left")
#
#         # New backup button
#         self.backup_btn = ctk.CTkButton(
#             controls,
#             text="Create Backup",
#             width=120,
#             command=self._create_backup,
#         )
#         self.backup_btn.pack(side="left", padx=(PADDING["medium"], 0))
#
#         # Backup list section
#         list_header = ctk.CTkFrame(self, fg_color="transparent")
#         list_header.pack(fill="x", padx=PADDING["medium"])
#
#         list_label = ctk.CTkLabel(list_header, text="Backups", font=FONTS["heading"])
#         list_label.pack(side="left")
#
#         self.backup_count_label = ctk.CTkLabel(list_header, text="(0)", font=FONTS["small"], text_color="gray")
#         self.backup_count_label.pack(side="left", padx=(5, 0))
#
#         # Refresh button
#         refresh_btn = ctk.CTkButton(
#             list_header,
#             text="Refresh",
#             width=70,
#             height=24,
#             font=FONTS["small"],
#             command=self._refresh_backup_list,
#         )
#         refresh_btn.pack(side="right")
#
#         # Scrollable backup list
#         self.backup_list = ctk.CTkScrollableFrame(self, height=300)
#         self.backup_list.pack(fill="both", expand=True, padx=PADDING["medium"], pady=PADDING["small"])
#
#         # No backups message (shown when list is empty)
#         self.no_backups_label = ctk.CTkLabel(
#             self.backup_list,
#             text="No backups yet. Create your first backup above!",
#             font=FONTS["body"],
#             text_color="gray"
#         )
#
#     def _create_backup(self):
#         """Create a new backup."""
#         if not self.installation.save_path or not self.installation.save_path.exists():
#             messagebox.showerror("Error", "Save path does not exist. Please check your configuration.")
#             return
#
#         description = self.description_var.get().strip()
#
#         try:
#             self.backup_btn.configure(state="disabled", text="Backing up...")
#             self.update()
#
#             backup = self.backup_service.create_backup(self.installation, description)
#
#             self._set_status(f"Backup created: {backup.description}")
#             self.description_var.set("")  # Clear description
#             self._refresh_backup_list()
#
#         except BackupError as e:
#             messagebox.showerror("Backup Error", str(e))
#             self._set_status(f"Backup failed: {e}")
#
#         finally:
#             self.backup_btn.configure(state="normal", text="Create Backup")
#
#     def _restore_backup(self, backup: BackupRecord):
#         """Restore a backup."""
#         result = messagebox.askyesno(
#             "Confirm Restore",
#             f"Are you sure you want to restore this backup?\n\n"
#             f"Date: {backup.timestamp.strftime('%Y-%m-%d %H:%M')}\n"
#             f"Description: {backup.description}\n\n"
#             f"Your current saves will be backed up first for safety."
#         )
#
#         if not result:
#             return
#
#         try:
#             self._set_status("Restoring backup...")
#             self.update()
#
#             self.backup_service.restore_backup(backup)
#
#             messagebox.showinfo("Success", "Backup restored successfully!")
#             self._set_status("Backup restored successfully")
#             self._refresh_backup_list()  # Refresh to show safety backup
#
#         except RestoreError as e:
#             messagebox.showerror("Restore Error", str(e))
#             self._set_status(f"Restore failed: {e}")
#
#     def _delete_backup(self, backup: BackupRecord):
#         """Delete a backup."""
#         result = messagebox.askyesno(
#             "Confirm Delete",
#             f"Are you sure you want to delete this backup?\n\n"
#             f"Date: {backup.timestamp.strftime('%Y-%m-%d %H:%M')}\n"
#             f"Description: {backup.description}\n\n"
#             f"This action cannot be undone."
#         )
#
#         if not result:
#             return
#
#         try:
#             self.backup_service.delete_backup(backup)
#             self._set_status("Backup deleted")
#             self._refresh_backup_list()
#
#         except Exception as e:
#             messagebox.showerror("Delete Error", str(e))
#             self._set_status(f"Delete failed: {e}")
#
#     def _refresh_backup_list(self):
#         """Refresh the backup list display."""
#         # Clear existing items
#         for widget in self.backup_list.winfo_children():
#             widget.destroy()
#
#         # Get backups for this installation
#         backups = self.backup_service.config.get_backups_for_installation(self.installation.id)
#
#         # Update count
#         self.backup_count_label.configure(text=f"({len(backups)})")
#
#         if not backups:
#             self.no_backups_label = ctk.CTkLabel(
#                 self.backup_list,
#                 text="No backups yet. Create your first backup above!",
#                 font=FONTS["body"],
#                 text_color="gray"
#             )
#             self.no_backups_label.pack(pady=PADDING["large"])
#             return
#
#         # Create row for each backup
#         for backup in backups:
#             self._create_backup_row(backup)
#
#     def _create_backup_row(self, backup: BackupRecord):
#         """Create a row for a single backup."""
#         row = ctk.CTkFrame(self.backup_list)
#         row.pack(fill="x", pady=2)
#
#         # Info section
#         info_frame = ctk.CTkFrame(row, fg_color="transparent")
#         info_frame.pack(side="left", fill="x", expand=True, padx=PADDING["small"], pady=PADDING["small"])
#
#         # Date and time
#         date_str = backup.timestamp.strftime("%Y-%m-%d %H:%M")
#         date_label = ctk.CTkLabel(info_frame, text=date_str, font=FONTS["body"])
#         date_label.pack(anchor="w")
#
#         # Description
#         desc_label = ctk.CTkLabel(
#             info_frame,
#             text=backup.description or "No description",
#             font=FONTS["small"],
#             text_color="gray"
#         )
#         desc_label.pack(anchor="w")
#
#         # Size
#         size_mb = backup.get_size_mb()
#         size_text = f"{size_mb:.1f} MB" if backup.exists() else "File missing"
#         size_color = "gray" if backup.exists() else "red"
#         size_label = ctk.CTkLabel(info_frame, text=size_text, font=FONTS["small"], text_color=size_color)
#         size_label.pack(anchor="w")
#
#         # Buttons section
#         btn_frame = ctk.CTkFrame(row, fg_color="transparent")
#         btn_frame.pack(side="right", padx=PADDING["small"], pady=PADDING["small"])
#
#         # Restore button
#         restore_btn = ctk.CTkButton(
#             btn_frame,
#             text="Restore",
#             width=70,
#             height=28,
#             fg_color=COLORS["success"],
#             hover_color=COLORS["success_hover"],
#             command=lambda b=backup: self._restore_backup(b),
#         )
#         restore_btn.pack(side="left", padx=(0, 5))
#
#         # Delete button
#         delete_btn = ctk.CTkButton(
#             btn_frame,
#             text="Delete",
#             width=70,
#             height=28,
#             fg_color=COLORS["danger"],
#             hover_color=COLORS["danger_hover"],
#             command=lambda b=backup: self._delete_backup(b),
#         )
#         delete_btn.pack(side="left")
#
#         # Disable restore if file doesn't exist
#         if not backup.exists():
#             restore_btn.configure(state="disabled")
#
#     def _set_status(self, message: str):
#         """Update the status bar."""
#         if self.on_status_change:
#             self.on_status_change(message)
