"""Servers mode mixin for MainWindow."""
# pylint: disable=broad-exception-caught
# Network operations (FTP/SFTP) can fail with many exception types from
# ftplib, paramiko, socket, etc. Broad catches are intentional to prevent
# the GUI from crashing and to display user-friendly error messages.

from __future__ import annotations

import re
from pathlib import Path

import customtkinter as ctk

from ..config.paths import GamePaths
from ..config.security import decrypt_password, encrypt_password
from ..logging_config import get_logger
from .styles import COLORS, FONTS, PADDING, THEME_COLORS

logger = get_logger("servers_mixin")


class ServersMixin:
    """Server management mixin providing remote server connectivity for MainWindow.

    This mixin adds FTP and SFTP support for managing Moria game servers,
    including:
    - A per-installation server list pane with inline-editable entries
      (name, address, password, notes) stored in XML files.
    - A server configuration system (myservers.ini) for remote servers
      with connection credentials, protocol selection, and remote paths
      for config files, pak files, and save files.
    - Protocol-agnostic file operations (list, download, upload, delete,
      rename, mkdir, rmdir, navigate) that dispatch to either FTP (ftplib)
      or SFTP (paramiko) based on the server's configured protocol.
    - Connection lifecycle management: background-threaded connect,
      keepalive verification, graceful disconnect, and temp cache cleanup.
    - A minimal terminal popup for interactive directory browsing on
      connected servers (pwd, ls, cd commands).
    - Add/edit/delete server dialogs with password visibility toggle and
      clipboard copy support.

    Connection state for each server is tracked in
    ``self.server_connection_states`` as one of: "disconnected",
    "connecting", "connected", or "error".

    Passwords are encrypted at rest via ``config.security.encrypt_password``
    and decrypted on load.
    """

    # =========================================================================
    # Server List Pane UI Construction
    # =========================================================================

    def _create_server_pane(self):
        """Create the server list pane (hidden by default,
        uses left tabs for installation selection)."""
        # Server pane spans both columns
        self.server_pane = ctk.CTkFrame(self.content_frame, fg_color=THEME_COLORS["bg_pane_content"])
        # Don't grid initially - only shown in servers mode

        # Data storage for server entries per installation
        # Key is installation id (e.g., "steam", "epic", "custom")
        self.server_entries_by_install: dict[str, list[dict]] = {}
        self.server_row_widgets: list[dict] = []

        # Store references for the single server list content area
        self.server_list_frame: ctk.CTkScrollableFrame | None = None
        self.server_add_button: ctk.CTkButton | None = None
        self.server_header_frame: ctk.CTkFrame | None = None
        self.server_content_frame: ctk.CTkFrame | None = None

        # Create the server content area (single view, switches based on left tab)
        self._create_server_content()

    def _create_server_content(self):
        """Create the server list content area."""
        # Content container
        self.server_content_frame = ctk.CTkFrame(self.server_pane, fg_color="transparent")
        self.server_content_frame.pack(
            fill="both", expand=True,
            padx=PADDING["small"], pady=PADDING["small"]
        )

        # Header row with column titles
        self.server_header_frame = ctk.CTkFrame(
            self.server_content_frame,
            fg_color=THEME_COLORS["bg_main"]
        )
        self.server_header_frame.pack(fill="x", pady=(0, 0))

        # Column weights control how extra horizontal space is distributed.
        # Minsize values guarantee columns stay readable when the window is
        # narrow. These same weights/minsizes are replicated in the row
        # frames and the scrollable list frame so columns stay aligned.
        self.server_header_frame.grid_columnconfigure(0, weight=2, minsize=120)  # Name
        self.server_header_frame.grid_columnconfigure(1, weight=2, minsize=150)  # Address
        self.server_header_frame.grid_columnconfigure(2, weight=1, minsize=100)  # Password
        self.server_header_frame.grid_columnconfigure(3, weight=3, minsize=200)  # Notes
        self.server_header_frame.grid_columnconfigure(4, weight=0, minsize=80)   # Actions

        # Column headers
        name_header = ctk.CTkLabel(
            self.server_header_frame, text="Name",
            font=FONTS["heading"], anchor="w",
            text_color=THEME_COLORS["text"]
        )
        name_header.grid(row=0, column=0, sticky="w", padx=(PADDING["small"], 5), pady=5)

        address_header = ctk.CTkLabel(
            self.server_header_frame, text="Address",
            font=FONTS["heading"], anchor="w",
            text_color=THEME_COLORS["text"]
        )
        address_header.grid(row=0, column=1, sticky="w", padx=5, pady=5)

        password_header = ctk.CTkLabel(
            self.server_header_frame, text="Password",
            font=FONTS["heading"], anchor="w",
            text_color=THEME_COLORS["text"]
        )
        password_header.grid(row=0, column=2, sticky="w", padx=5, pady=5)

        notes_header = ctk.CTkLabel(
            self.server_header_frame, text="Notes",
            font=FONTS["heading"], anchor="w",
            text_color=THEME_COLORS["text"]
        )
        notes_header.grid(row=0, column=3, sticky="w", padx=5, pady=5)

        actions_header = ctk.CTkLabel(
            self.server_header_frame, text="",
            font=FONTS["heading"], anchor="center"
        )
        actions_header.grid(row=0, column=4, sticky="ew", padx=5, pady=5)

        # Scrollable frame for server rows
        self.server_list_frame = ctk.CTkScrollableFrame(
            self.server_content_frame,
            fg_color=THEME_COLORS["bg_pane_content"]
        )
        self.server_list_frame.pack(fill="both", expand=True, pady=(0, PADDING["small"]))

        # Configure grid columns to match header
        self.server_list_frame.grid_columnconfigure(0, weight=2, minsize=120)
        self.server_list_frame.grid_columnconfigure(1, weight=2, minsize=150)
        self.server_list_frame.grid_columnconfigure(2, weight=1, minsize=100)
        self.server_list_frame.grid_columnconfigure(3, weight=3, minsize=200)
        self.server_list_frame.grid_columnconfigure(4, weight=0, minsize=80)

        # Add new server button at bottom
        add_frame = ctk.CTkFrame(self.server_content_frame, fg_color="transparent")
        add_frame.pack(fill="x", pady=PADDING["small"])

        self.server_add_button = ctk.CTkButton(
            add_frame, text="+ Add Server", width=120,
            command=self._add_server_entry_current
        )
        self.server_add_button.pack(side="left")

    # =========================================================================
    # Server Entry Management (per-installation inline list)
    # =========================================================================

    def _add_server_entry_current(self):
        """Add a server entry for the current installation."""
        if self.current_installation:
            self._add_server_entry(self.current_installation.id.value)

    def _refresh_server_list(self):
        """Refresh the server list for the current installation."""
        if not self.current_installation:
            return

        install_id = self.current_installation.id.value

        # Load server data for this installation if not already loaded
        if install_id not in self.server_entries_by_install:
            self._load_server_list(install_id)

        # Rebuild the UI
        self._rebuild_server_list_current()

    def _create_server_row(self, install_id: str, row_index: int, data: dict = None):
        """Create a single server row with editable fields."""
        if data is None:
            data = {"name": "", "address": "", "password": "", "notes": ""}

        if not self.server_list_frame:
            return None

        row_frame = ctk.CTkFrame(self.server_list_frame, fg_color="transparent")

        # Name entry
        # Each field binds FocusOut for immediate save and KeyRelease for
        # debounced save (1s delay), so data is persisted whether the user
        # tabs away or pauses typing.
        name_entry = ctk.CTkEntry(row_frame, font=FONTS["body"], height=28)
        name_entry.insert(0, data.get("name", ""))
        name_entry.grid(row=0, column=0, sticky="ew", padx=(PADDING["small"], 5), pady=2)
        name_entry.bind(
            "<FocusOut>",
            lambda e, iid=install_id, idx=row_index:
                self._on_server_field_change(iid, idx))
        name_entry.bind(
            "<KeyRelease>",
            lambda e, iid=install_id, idx=row_index:
                self._schedule_server_save(iid, idx))

        # Address entry with copy button
        address_frame = ctk.CTkFrame(row_frame, fg_color="transparent")
        address_frame.grid(row=0, column=1, sticky="ew", padx=5, pady=2)
        address_frame.grid_columnconfigure(0, weight=1)

        address_entry = ctk.CTkEntry(address_frame, font=FONTS["body"], height=28)
        address_entry.insert(0, data.get("address", ""))
        address_entry.grid(row=0, column=0, sticky="ew")
        address_entry.bind(
            "<FocusOut>",
            lambda e, iid=install_id, idx=row_index:
                self._on_server_field_change(iid, idx))
        address_entry.bind(
            "<KeyRelease>",
            lambda e, iid=install_id, idx=row_index:
                self._schedule_server_save(iid, idx))

        address_copy_btn = ctk.CTkButton(
            address_frame, text="\U0001F4CB", width=24, height=24,
            font=("Segoe UI", 10),
            fg_color="transparent", hover_color=("gray80", "gray30"),
            text_color=THEME_COLORS["icon_color"],
            command=lambda: self._copy_to_clipboard(address_entry.get(), "Address")
        )
        address_copy_btn.grid(row=0, column=1, padx=(2, 0))

        # Password entry with eye and copy buttons
        password_frame = ctk.CTkFrame(row_frame, fg_color="transparent")
        password_frame.grid(row=0, column=2, sticky="ew", padx=5, pady=2)
        password_frame.grid_columnconfigure(0, weight=1)

        password_entry = ctk.CTkEntry(password_frame, font=FONTS["body"], height=28, show="*")
        password_entry.insert(0, data.get("password", ""))
        password_entry.grid(row=0, column=0, sticky="ew")
        password_entry.bind(
            "<FocusOut>",
            lambda e, iid=install_id, idx=row_index:
            self._on_server_field_change(iid, idx))
        password_entry.bind(
            "<KeyRelease>",
            lambda e, iid=install_id, idx=row_index:
            self._schedule_server_save(iid, idx))

        # Store password visibility state per row.
        # Uses a mutable dict so the nested toggle_password closure can
        # modify the flag without needing nonlocal (works across rows).
        password_visible = {"visible": False}

        def toggle_password():
            password_visible["visible"] = not password_visible["visible"]
            if password_visible["visible"]:
                password_entry.configure(show="")
                eye_btn.configure(text="\U0001F576")
            else:
                password_entry.configure(show="*")
                eye_btn.configure(text="\U0001F441")

        eye_btn = ctk.CTkButton(
            password_frame, text="\U0001F441", width=24, height=24,
            font=("Segoe UI", 10),
            fg_color="transparent", hover_color=("gray80", "gray30"),
            text_color=THEME_COLORS["icon_color"],
            command=toggle_password
        )
        eye_btn.grid(row=0, column=1, padx=(2, 0))

        password_copy_btn = ctk.CTkButton(
            password_frame, text="\U0001F4CB", width=24, height=24,
            font=("Segoe UI", 10),
            fg_color="transparent", hover_color=("gray80", "gray30"),
            text_color=THEME_COLORS["icon_color"],
            command=lambda: self._copy_to_clipboard(password_entry.get(), "Password")
        )
        password_copy_btn.grid(row=0, column=2, padx=(2, 0))

        # Notes entry
        notes_entry = ctk.CTkEntry(row_frame, font=FONTS["body"], height=28)
        notes_entry.insert(0, data.get("notes", ""))
        notes_entry.grid(row=0, column=3, sticky="ew", padx=5, pady=2)
        notes_entry.bind(
            "<FocusOut>",
            lambda e, iid=install_id, idx=row_index:
            self._on_server_field_change(iid, idx))
        notes_entry.bind(
            "<KeyRelease>",
            lambda e, iid=install_id, idx=row_index:
            self._schedule_server_save(iid, idx))

        # Delete button
        delete_btn = ctk.CTkButton(
            row_frame, text="\u2717", width=28, height=24,
            font=("Segoe UI", 12),
            fg_color=COLORS["danger"], hover_color=COLORS["danger_hover"],
            command=lambda iid=install_id, idx=row_index: self._delete_server_entry(iid, idx)
        )
        delete_btn.grid(row=0, column=4, padx=5, pady=2)
        self._create_tooltip(delete_btn, "Delete server")

        # Configure row grid
        row_frame.grid_columnconfigure(0, weight=2, minsize=120)
        row_frame.grid_columnconfigure(1, weight=2, minsize=150)
        row_frame.grid_columnconfigure(2, weight=1, minsize=100)
        row_frame.grid_columnconfigure(3, weight=3, minsize=200)
        row_frame.grid_columnconfigure(4, weight=0, minsize=80)

        row_frame.pack(fill="x", pady=1)

        # Store widget references
        widgets = {
            "frame": row_frame,
            "name": name_entry,
            "address": address_entry,
            "password": password_entry,
            "notes": notes_entry,
            "install_id": install_id,
        }

        return widgets

    def _add_server_entry(self, install_id: str):
        """Add a new empty server entry row for a specific installation."""
        if install_id not in self.server_entries_by_install:
            self.server_entries_by_install[install_id] = []

        new_data = {"name": "", "address": "", "password": "", "notes": ""}
        self.server_entries_by_install[install_id].append(new_data)
        row_index = len(self.server_entries_by_install[install_id]) - 1
        widgets = self._create_server_row(install_id, row_index, new_data)
        if widgets:
            self.server_row_widgets.append(widgets)
        self._save_server_list(install_id)

    def _delete_server_entry(self, install_id: str, row_index: int):
        """Delete a server entry from a specific installation."""
        if install_id in self.server_entries_by_install:
            entries = self.server_entries_by_install[install_id]
            if row_index < len(entries):
                # Remove from data
                entries.pop(row_index)

                # Rebuild the list for this installation
                self._rebuild_server_list(install_id)
                self._save_server_list(install_id)

    def _rebuild_server_list(self, install_id: str = None):
        """Rebuild the server list UI from data for a specific installation."""
        if install_id:
            # Rebuild just one installation's list
            self._rebuild_server_list_for_install(install_id)

    def _rebuild_server_list_current(self):
        """Rebuild the server list for the current installation."""
        if not self.current_installation:
            return
        self._rebuild_server_list_for_install(self.current_installation.id.value)

    def _rebuild_server_list_for_install(self, install_id: str):
        """Rebuild the server list UI for a specific installation."""
        # Clear ALL existing widgets (single list frame now)
        for widgets in self.server_row_widgets:
            widgets["frame"].destroy()
        self.server_row_widgets.clear()

        # Recreate all rows for this installation
        entries = self.server_entries_by_install.get(install_id, [])
        for idx, data in enumerate(entries):
            widgets = self._create_server_row(install_id, idx, data)
            if widgets:
                self.server_row_widgets.append(widgets)

        # Reset scroll to top if few items
        if self.server_list_frame:
            self._reset_scroll_if_few_items(self.server_list_frame)

    def _on_server_field_change(self, install_id: str, row_index: int):
        """Handle field change - update data dict from widget values and save.

        Because server_row_widgets is a flat list containing rows from
        potentially multiple installations, we must filter by install_id
        and count to the target row_index within that subset.
        """
        for widgets in self.server_row_widgets:
            if widgets.get("install_id") == install_id:
                entries = self.server_entries_by_install.get(install_id, [])
                if row_index < len(entries):
                    # Walk the flat widget list, counting only rows that
                    # belong to this install_id, to locate the Nth row.
                    count = 0
                    for w in self.server_row_widgets:
                        if w.get("install_id") == install_id:
                            if count == row_index:
                                entries[row_index] = {
                                    "name": w["name"].get(),
                                    "address": w["address"].get(),
                                    "password": w["password"].get(),
                                    "notes": w["notes"].get(),
                                }
                                break
                            count += 1
                break

        self._save_server_list(install_id)

    def _schedule_server_save(self, install_id: str, row_index: int):
        """Schedule a debounced save after typing.

        Each keystroke resets the 1-second timer so the XML file is only
        written once the user stops typing, avoiding excessive disk I/O.
        """
        if self._server_save_timer:
            self.after_cancel(self._server_save_timer)

        self._server_save_timer = self.after(
            1000,  # 1-second debounce delay
            lambda: self._on_server_field_change(
                install_id, row_index))

    # =========================================================================
    # Server List Persistence (XML per installation)
    # =========================================================================

    def _get_server_list_path(self, install_id: str) -> Path:
        """Get the path to the serverinfo.xml file for a specific installation.

        Server info files are stored in %APPDATA%/MoriaManager/servers/
        """
        server_dir = GamePaths.SERVER_INFO_DIR
        server_dir.mkdir(parents=True, exist_ok=True)
        # Use installation-specific filename: serverinfo_steam.xml, serverinfo_epic.xml, etc.
        return server_dir / f"serverinfo_{install_id}.xml"

    def _save_server_list(self, install_id: str):
        """Save server list to XML file for a specific installation."""
        import xml.etree.ElementTree as ET
        from xml.dom import minidom

        root = ET.Element("ServerList", version="1.0", installation=install_id)

        entries = self.server_entries_by_install.get(install_id, [])
        for entry in entries:
            server_elem = ET.SubElement(root, "Server")
            ET.SubElement(server_elem, "Name").text = entry.get("name", "")
            ET.SubElement(server_elem, "Address").text = entry.get("address", "")
            # Passwords are encrypted before writing to disk
            ET.SubElement(server_elem, "Password").text = (
                encrypt_password(entry.get("password", "")))
            ET.SubElement(server_elem, "Notes").text = entry.get("notes", "")

        # Pretty-print via minidom; strip blank lines that toprettyxml
        # inserts between elements to keep the file compact.
        xml_str = minidom.parseString(
            ET.tostring(root, encoding="unicode")
        ).toprettyxml(indent="  ")
        lines = [line for line in xml_str.split('\n') if line.strip()]
        xml_str = '\n'.join(lines)

        server_file = self._get_server_list_path(install_id)
        server_file.write_text(xml_str, encoding="utf-8")
        self._set_status(f"Server list saved ({install_id})")

    def _load_server_list(self, install_id: str):
        """Load server list from XML file for a specific installation."""
        import xml.etree.ElementTree as ET

        if install_id not in self.server_entries_by_install:
            self.server_entries_by_install[install_id] = []
        else:
            self.server_entries_by_install[install_id].clear()

        server_file = self._get_server_list_path(install_id)
        if not server_file.exists():
            return

        try:
            tree = ET.parse(server_file)
            root = tree.getroot()

            for server_elem in root.findall("Server"):
                entry = {
                    "name": self._get_elem_text(server_elem, "Name"),
                    "address": self._get_elem_text(server_elem, "Address"),
                    "password": decrypt_password(self._get_elem_text(server_elem, "Password")),
                    "notes": self._get_elem_text(server_elem, "Notes"),
                }
                self.server_entries_by_install[install_id].append(entry)

        except (OSError, ET.ParseError, KeyError) as e:
            self._set_status(f"Error loading server list ({install_id}): {e}")

    def _get_elem_text(self, parent, tag: str) -> str:
        """Get text content of a child element."""
        elem = parent.find(tag)
        return elem.text if elem is not None and elem.text else ""

    def _copy_to_clipboard(self, text: str, field_name: str):
        """Copy text to the Windows clipboard."""
        if text:
            self.clipboard_clear()
            self.clipboard_append(text)
            self._set_status(f"{field_name} copied to clipboard")
        else:
            self._set_status(f"No {field_name.lower()} to copy")


    # =========================================================================
    # Add / Edit / Delete Server Dialogs
    # =========================================================================

    def _show_add_server_dialog(self):
        """Show dialog to add a new remote server installation."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Add Server")
        dialog.geometry("750x450")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        # Center on parent
        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 750) // 2
        y = self.winfo_y() + (self.winfo_height() - 450) // 2
        dialog.geometry(f"+{x}+{y}")
        self._set_dialog_icon(dialog)

        # Main container
        container = ctk.CTkFrame(dialog, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=PADDING["medium"], pady=PADDING["medium"])

        # Two-column frame
        columns_frame = ctk.CTkFrame(container, fg_color="transparent")
        columns_frame.pack(fill="both", expand=True)

        # Left column - Connection Info
        left_col = ctk.CTkFrame(columns_frame, fg_color="transparent")
        left_col.pack(side="left", fill="both", expand=True, padx=(0, PADDING["medium"]))

        conn_label = ctk.CTkLabel(
            left_col, text="Connection Info",
            font=FONTS["heading"], anchor="w")
        conn_label.pack(fill="x", pady=(0, 8))

        # Name field
        name_label = ctk.CTkLabel(left_col, text="Name:", font=FONTS["body"], anchor="w")
        name_label.pack(fill="x", pady=(0, 2))
        name_entry = ctk.CTkEntry(left_col, font=FONTS["body"], height=28)
        name_entry.pack(fill="x", pady=(0, 8))

        # Host field
        host_label = ctk.CTkLabel(left_col, text="Host:", font=FONTS["body"], anchor="w")
        host_label.pack(fill="x", pady=(0, 2))
        host_entry = ctk.CTkEntry(left_col, font=FONTS["body"], height=28)
        host_entry.pack(fill="x", pady=(0, 8))

        # Port and Protocol frame
        port_proto_frame = ctk.CTkFrame(left_col, fg_color="transparent")
        port_proto_frame.pack(fill="x", pady=(0, 8))

        port_label = ctk.CTkLabel(port_proto_frame, text="Port:", font=FONTS["body"], anchor="w")
        port_label.pack(side="left", padx=(0, 5))
        # Default port 21 (FTP); user should change to 22 when SFTP is selected
        port_entry = ctk.CTkEntry(port_proto_frame, font=FONTS["body"], height=28, width=70)
        port_entry.insert(0, "21")
        port_entry.pack(side="left", padx=(0, 15))

        proto_label = ctk.CTkLabel(
            port_proto_frame, text="Protocol:",
            font=FONTS["body"], anchor="w")
        proto_label.pack(side="left", padx=(0, 5))
        protocol_var = ctk.StringVar(value="FTP")
        protocol_dropdown = ctk.CTkOptionMenu(
            port_proto_frame, values=["FTP", "SFTP"], variable=protocol_var,
            width=90, height=28, font=FONTS["body"]
        )
        protocol_dropdown.pack(side="left")

        # Username field
        user_label = ctk.CTkLabel(left_col, text="Username:", font=FONTS["body"], anchor="w")
        user_label.pack(fill="x", pady=(0, 2))
        user_entry = ctk.CTkEntry(left_col, font=FONTS["body"], height=28)
        user_entry.pack(fill="x", pady=(0, 8))

        # Password field with visibility toggle
        pass_label = ctk.CTkLabel(left_col, text="Password:", font=FONTS["body"], anchor="w")
        pass_label.pack(fill="x", pady=(0, 2))

        pass_frame = ctk.CTkFrame(left_col, fg_color="transparent")
        pass_frame.pack(fill="x", pady=(0, 8))

        pass_entry = ctk.CTkEntry(pass_frame, font=FONTS["body"], height=28, show="*")
        pass_entry.pack(side="left", fill="x", expand=True)

        password_visible = {"visible": False}

        def toggle_password():
            password_visible["visible"] = not password_visible["visible"]
            pass_entry.configure(show="" if password_visible["visible"] else "*")

        eye_btn = ctk.CTkButton(
            pass_frame, text="\U0001F441", width=28, height=28,
            font=FONTS["body"], fg_color="transparent",
            hover_color=("gray80", "gray30"),
            command=toggle_password
        )
        eye_btn.pack(side="right", padx=(5, 0))

        # Vertical separator
        separator = ctk.CTkFrame(columns_frame, width=2, fg_color="gray50")
        separator.pack(side="left", fill="y", padx=PADDING["small"])

        # Right column - Server Paths
        right_col = ctk.CTkFrame(columns_frame, fg_color="transparent")
        right_col.pack(
            side="left", fill="both", expand=True,
            padx=(PADDING["medium"], 0))

        paths_label = ctk.CTkLabel(
            right_col, text="Server Paths",
            font=FONTS["heading"], anchor="w")
        paths_label.pack(fill="x", pady=(0, 8))

        # MoriaServerConfig.ini path
        config_path_label = ctk.CTkLabel(
            right_col, text="MoriaServerConfig.ini:",
            font=FONTS["body"], anchor="w")
        config_path_label.pack(fill="x", pady=(0, 2))
        config_path_entry = ctk.CTkEntry(right_col, font=FONTS["body"], height=28)
        config_path_entry.pack(fill="x", pady=(0, 8))

        # Pak file location path
        pak_path_label = ctk.CTkLabel(
            right_col, text="Pak File Location:",
            font=FONTS["body"], anchor="w")
        pak_path_label.pack(fill="x", pady=(0, 2))
        pak_path_entry = ctk.CTkEntry(right_col, font=FONTS["body"], height=28)
        pak_path_entry.pack(fill="x", pady=(0, 8))

        # Save File Location path
        save_path_label = ctk.CTkLabel(
            right_col, text="Save File Location:",
            font=FONTS["body"], anchor="w")
        save_path_label.pack(fill="x", pady=(0, 2))
        save_path_entry = ctk.CTkEntry(right_col, font=FONTS["body"], height=28)
        save_path_entry.pack(fill="x", pady=(0, 8))

        # Bottom button frame
        btn_frame = ctk.CTkFrame(container, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(PADDING["medium"], 0))

        def on_cancel():
            dialog.destroy()

        def on_ok():
            name = name_entry.get().strip()
            host = host_entry.get().strip()
            port = port_entry.get().strip()
            protocol = protocol_var.get()
            username = user_entry.get().strip()
            password = pass_entry.get()
            config_path = config_path_entry.get().strip()
            pak_path = pak_path_entry.get().strip()
            save_path = save_path_entry.get().strip()

            if not name:
                from tkinter import messagebox
                messagebox.showwarning(
                    "Missing Field",
                    "Please enter a name for this server.",
                    parent=dialog)
                return

            if not host:
                from tkinter import messagebox
                messagebox.showwarning("Missing Field", "Please enter a host.", parent=dialog)
                return

            if not port:
                # Standard ports: FTP=21, SFTP(SSH)=22
                port = "21" if protocol == "FTP" else "22"

            self._save_server_to_ini(
                name, host, port, protocol,
                username, password, config_path,
                pak_path, save_path)
            dialog.destroy()
            self._refresh_tabs()
            self._set_status(f"Server '{name}' added successfully")

        cancel_btn = ctk.CTkButton(
            btn_frame, text="Cancel", width=100,
            fg_color="gray50", hover_color="gray40",
            text_color="white",
            command=on_cancel
        )
        cancel_btn.pack(side="left")

        apply_btn = ctk.CTkButton(
            btn_frame, text="Apply", width=100,
            fg_color="#1a5fb4", hover_color="#1c4a8a",
            text_color="white",
            command=on_ok
        )
        apply_btn.pack(side="right")

        dialog.protocol("WM_DELETE_WINDOW", on_cancel)
        name_entry.focus_set()
        dialog.wait_window()

    # =========================================================================
    # Server INI Persistence (myservers.ini for remote server configs)
    # =========================================================================

    def _save_server_to_ini(
        self, name: str, host: str, port: str,
        protocol: str, username: str,
        password: str, config_path: str = "",
        pak_path: str = "", save_path: str = ""
    ):
        """Save a server entry to myservers.ini with encrypted password."""
        from configparser import ConfigParser

        ini_path = GamePaths.CONFIG_DIR / "myservers.ini"
        GamePaths.ensure_config_dir()

        config = ConfigParser()

        # Read existing file if it exists
        if ini_path.exists():
            try:
                config.read(ini_path, encoding="utf-8")
            except Exception as e:
                logger.warning("Failed to read myservers.ini: %s", e)

        # INI section names cannot contain brackets; replace with parens
        section_name = name.replace("[", "(").replace("]", ")")

        if not config.has_section(section_name):
            config.add_section(section_name)

        config.set(section_name, "host", host)
        config.set(section_name, "port", port)
        config.set(section_name, "protocol", protocol)
        config.set(section_name, "username", username)
        config.set(section_name, "password", encrypt_password(password))
        config.set(section_name, "config_path", config_path)
        config.set(section_name, "pak_path", pak_path)
        config.set(section_name, "save_path", save_path)

        try:
            with open(ini_path, "w", encoding="utf-8") as f:
                config.write(f)
            logger.info("Saved server '%s' to myservers.ini", name)
        except Exception as e:
            logger.error("Failed to save myservers.ini: %s", e)

    def _load_servers_from_ini(self) -> list:
        """Load server entries from myservers.ini.

        Returns:
            List of dicts with keys: name, host, port, protocol, username, password
        """
        from configparser import ConfigParser

        ini_path = GamePaths.CONFIG_DIR / "myservers.ini"
        servers = []

        if not ini_path.exists():
            return servers

        config = ConfigParser()
        try:
            config.read(ini_path, encoding="utf-8")
        except Exception as e:
            logger.warning("Failed to read myservers.ini: %s", e)
            return servers

        for section in config.sections():
            server = {
                "name": section,
                "host": config.get(section, "host", fallback=""),
                "port": config.get(section, "port", fallback="21"),
                "protocol": config.get(section, "protocol", fallback="FTP"),
                "username": config.get(section, "username", fallback=""),
                "password": decrypt_password(config.get(section, "password", fallback="")),
                "config_path": config.get(section, "config_path", fallback=""),
                "pak_path": config.get(section, "pak_path", fallback=""),
                "save_path": config.get(section, "save_path", fallback=""),
            }
            servers.append(server)

        return servers

    # ============================================================================
    # UNIVERSAL SERVER FILE OPERATIONS
    # ============================================================================

    def _server_ensure_connected(self, server: dict) -> bool:
        """Ensure server connection is active. Connect if not already connected.

        Args:
            server: Server dict with connection details

        Returns:
            True if connected (or connection established), False on error
        """
        server_name = server["name"]
        conn_state = self.server_connection_states.get(server_name, "disconnected")

        if conn_state == "connected":
            # Keepalive probe: issue a cheap command to verify the socket
            # is still alive. FTP uses PWD, SFTP uses getcwd(). If either
            # raises, the connection has been dropped (timeout, server
            # restart, etc.) and we fall through to reconnect.
            protocol = server.get("protocol", "FTP")
            try:
                if protocol == "FTP":
                    ftp = self.ftp_connections.get(server_name)
                    if ftp:
                        ftp.pwd()
                        return True
                else:  # SFTP
                    sftp = self.sftp_connections.get(server_name)
                    if sftp:
                        sftp.getcwd()
                        return True
            except Exception:
                # Connection lost, need to reconnect
                self.server_connection_states[server_name] = "disconnected"
                conn_state = "disconnected"

        if conn_state != "connected":
            # Need to connect synchronously for backup operations
            return self._server_connect_sync(server)

        return False

    def _server_connect_sync(self, server: dict) -> bool:
        """Synchronously connect to a server (blocking).

        Unlike _connect_server (which runs in a background thread for
        interactive use), this method blocks the calling thread and is
        used by file-operation methods that need the connection to be
        ready before proceeding.

        Args:
            server: Server dict with connection details

        Returns:
            True if connected, False on error
        """
        server_name = server["name"]
        host = server.get("host", "")
        port = int(server.get("port", 21))
        protocol = server.get("protocol", "FTP")
        username = server.get("username", "")
        password = server.get("password", "")

        if not host or not username:
            self._set_status(f"Missing host or username for {server_name}")
            return False

        self._set_status(f"Connecting to {server_name}...")
        self.update()  # Force UI update

        try:
            if protocol == "FTP":
                from ftplib import FTP

                ftp = FTP()
                ftp.connect(host, port, timeout=15)
                ftp.login(username, password)

                self.ftp_connections[server_name] = ftp
                self.server_connection_states[server_name] = "connected"
                self._set_status(f"Connected to {server_name}")
                self._refresh_tabs()
                return True
            # SFTP
            import paramiko

            transport = paramiko.Transport((host, port))
            transport.connect(username=username, password=password)

            sftp = paramiko.SFTPClient.from_transport(transport)

            self.sftp_transports[server_name] = transport
            self.sftp_connections[server_name] = sftp
            self.server_connection_states[server_name] = "connected"
            self._set_status(f"Connected to {server_name}")
            self._refresh_tabs()
            return True

        except Exception as e:
            logger.error("Connection error for %s: %s", server_name, e)
            self.server_connection_states[server_name] = "error"
            self._set_status(f"Connection failed: {e}")
            self._refresh_tabs()
            return False

    def _server_list_files(
        self, server: dict, remote_path: str,
        pattern: str = "*.sav"
    ) -> list[str]:
        """List files in a remote directory matching a pattern.

        Args:
            server: Server dict with connection details
            remote_path: Remote directory path
            pattern: Glob pattern to match (default *.sav)

        Returns:
            List of filenames (not full paths) matching the pattern
        """
        import fnmatch

        server_name = server["name"]
        protocol = server.get("protocol", "FTP")
        files = []

        logger.debug(
            "_server_list_files: server=%s, protocol=%s, remote_path='%s', pattern='%s'",
            server_name, protocol, remote_path, pattern
        )

        try:
            if protocol == "FTP":
                ftp = self.ftp_connections.get(server_name)
                if not ftp:
                    return []

                # Change to directory and list files
                ftp.cwd(remote_path)
                all_files = ftp.nlst()

                # Filter by pattern
                for f in all_files:
                    if fnmatch.fnmatch(f.lower(), pattern.lower()):
                        files.append(f)
            else:  # SFTP
                sftp = self.sftp_connections.get(server_name)
                if not sftp:
                    logger.debug("_server_list_files: No SFTP connection for %s", server_name)
                    return []

                # List directory and filter
                logger.debug("_server_list_files: Calling sftp.listdir('%s')", remote_path)
                all_files = sftp.listdir(remote_path)
                logger.debug("_server_list_files: sftp.listdir returned %d entries", len(all_files))
                for f in all_files:
                    if fnmatch.fnmatch(f.lower(), pattern.lower()):
                        files.append(f)

        except Exception as e:
            logger.error("Error listing files on %s: %s", server_name, e)
            logger.debug("_server_list_files: Exception details - type=%s, args=%s", type(e).__name__, e.args)
            self._set_status(f"Error listing files: {e}")

        logger.debug("_server_list_files: Returning %d files matching pattern", len(files))
        return files

    def _server_list_entries(self, server: dict, remote_path: str) -> list[tuple[str, bool]]:
        """List all entries (files and directories) in a remote directory.

        Args:
            server: Server dict with connection details
            remote_path: Remote directory path

        Returns:
            List of tuples (name, is_directory)
        """
        import stat

        server_name = server["name"]
        protocol = server.get("protocol", "FTP")
        entries = []

        logger.debug(
            "_server_list_entries: server=%s, protocol=%s, remote_path='%s'",
            server_name, protocol, remote_path
        )

        try:
            if protocol == "FTP":
                ftp = self.ftp_connections.get(server_name)
                if not ftp:
                    return []

                # MLSD (RFC 3659) returns structured metadata including
                # entry type. Not all FTP servers support it, so we fall
                # back to NLST + trial cwd to distinguish dirs from files.
                try:
                    ftp.cwd(remote_path)
                    for name, facts in ftp.mlsd():
                        if name in (".", ".."):
                            continue
                        is_dir = facts.get("type", "").lower() == "dir"
                        entries.append((name, is_dir))
                except Exception:
                    # Fallback: NLST gives bare filenames with no metadata.
                    # We probe each entry with cwd to detect directories
                    # (slow but universally supported).
                    ftp.cwd(remote_path)
                    all_names = ftp.nlst()
                    for name in all_names:
                        if name in (".", ".."):
                            continue
                        is_dir = False
                        try:
                            ftp.cwd(name)
                            ftp.cwd("..")
                            is_dir = True
                        except Exception:
                            pass
                        entries.append((name, is_dir))
            else:  # SFTP
                sftp = self.sftp_connections.get(server_name)
                if not sftp:
                    logger.debug("_server_list_entries: No SFTP connection for %s", server_name)
                    return []

                # SFTP's listdir_attr returns SFTPAttributes with st_mode,
                # letting us check the directory bit without extra round trips.
                logger.debug("_server_list_entries: Calling sftp.listdir_attr('%s')", remote_path)
                for attr in sftp.listdir_attr(remote_path):
                    name = attr.filename
                    if name in (".", ".."):
                        continue
                    is_dir = stat.S_ISDIR(attr.st_mode)
                    entries.append((name, is_dir))
                logger.debug("_server_list_entries: Found %d entries", len(entries))

        except Exception as e:
            logger.error("Error listing entries on %s: %s", server_name, e)
            logger.debug("_server_list_entries: Exception details - type=%s, args=%s", type(e).__name__, e.args)
            self._set_status(f"Error listing entries: {e}")

        return entries

    def _server_download_file(self, server: dict, remote_path: str, local_path: str) -> bool:
        """Download a file from the server.

        Args:
            server: Server dict with connection details
            remote_path: Full remote file path
            local_path: Local destination path

        Returns:
            True if successful, False on error
        """
        server_name = server["name"]
        protocol = server.get("protocol", "FTP")

        logger.debug(
            "_server_download_file: server=%s, protocol=%s, remote_path='%s', local_path='%s'",
            server_name, protocol, remote_path, local_path
        )

        try:
            if protocol == "FTP":
                ftp = self.ftp_connections.get(server_name)
                if not ftp:
                    logger.debug("_server_download_file: No FTP connection for %s", server_name)
                    return False

                # FTP binary download via RETR command; writes chunks
                # to local file through the callback.
                with open(local_path, 'wb') as f:
                    ftp.retrbinary(f'RETR {remote_path}', f.write)
                logger.debug("_server_download_file: FTP download successful")
                return True
            # SFTP transfers the entire file in one call
            sftp = self.sftp_connections.get(server_name)
            if not sftp:
                logger.debug("_server_download_file: No SFTP connection for %s", server_name)
                return False

            logger.debug("_server_download_file: Calling sftp.get('%s', '%s')", remote_path, local_path)
            sftp.get(remote_path, local_path)
            logger.debug("_server_download_file: SFTP download successful")
            return True

        except Exception as e:
            logger.error("Error downloading from %s: %s", server_name, e)
            logger.debug("_server_download_file: Exception details - type=%s, args=%s", type(e).__name__, e.args)
            self._set_status(f"Download failed: {e}")
            return False

    def _server_upload_file(self, server: dict, local_path: str, remote_path: str) -> bool:
        """Upload a file to the server.

        Args:
            server: Server dict with connection details
            local_path: Local source file path
            remote_path: Full remote destination path

        Returns:
            True if successful, False on error
        """
        server_name = server["name"]
        protocol = server.get("protocol", "FTP")

        logger.debug(
            "_server_upload_file: server=%s, protocol=%s, local_path='%s', remote_path='%s'",
            server_name, protocol, local_path, remote_path
        )

        try:
            if protocol == "FTP":
                ftp = self.ftp_connections.get(server_name)
                if not ftp:
                    logger.debug("_server_upload_file: No FTP connection for %s", server_name)
                    return False

                # FTP binary upload via STOR command
                with open(local_path, 'rb') as f:
                    ftp.storbinary(f'STOR {remote_path}', f)
                logger.debug("_server_upload_file: FTP upload successful")
                return True
            # SFTP upload is a single put() call
            sftp = self.sftp_connections.get(server_name)
            if not sftp:
                logger.debug("_server_upload_file: No SFTP connection for %s", server_name)
                return False

            logger.debug("_server_upload_file: Calling sftp.put('%s', '%s')", local_path, remote_path)
            sftp.put(local_path, remote_path)
            logger.debug("_server_upload_file: SFTP upload successful")
            return True

        except Exception as e:
            logger.error("Error uploading to %s: %s", server_name, e)
            logger.debug("_server_upload_file: Exception details - type=%s, args=%s", type(e).__name__, e.args)
            self._set_status(f"Upload failed: {e}")
            return False

    def _server_delete_file(self, server: dict, remote_path: str) -> bool:
        """Delete a file on the server.

        Args:
            server: Server dict with connection details
            remote_path: Full remote file path to delete

        Returns:
            True if successful, False on error
        """
        server_name = server["name"]
        protocol = server.get("protocol", "FTP")

        logger.debug(
            "_server_delete_file: server=%s, protocol=%s, remote_path='%s'",
            server_name, protocol, remote_path
        )

        try:
            if protocol == "FTP":
                ftp = self.ftp_connections.get(server_name)
                if not ftp:
                    logger.debug("_server_delete_file: No FTP connection for %s", server_name)
                    return False

                ftp.delete(remote_path)
                logger.debug("_server_delete_file: FTP delete successful")
                return True
            # SFTP
            sftp = self.sftp_connections.get(server_name)
            if not sftp:
                logger.debug("_server_delete_file: No SFTP connection for %s", server_name)
                return False

            logger.debug("_server_delete_file: Calling sftp.remove('%s')", remote_path)
            sftp.remove(remote_path)
            logger.debug("_server_delete_file: SFTP delete successful")
            return True

        except Exception as e:
            logger.error("Error deleting on %s: %s", server_name, e)
            logger.debug("_server_delete_file: Exception details - type=%s, args=%s", type(e).__name__, e.args)
            self._set_status(f"Delete failed: {e}")
            return False

    def _server_rename_file(self, server: dict, old_remote_path: str, new_remote_path: str) -> bool:
        """Rename a file on the server.

        Args:
            server: Server dict with connection details
            old_remote_path: Current remote file path
            new_remote_path: New remote file path

        Returns:
            True if successful, False on error
        """
        server_name = server["name"]
        protocol = server.get("protocol", "FTP")

        logger.debug(
            "_server_rename_file: server=%s, protocol=%s, old='%s', new='%s'",
            server_name, protocol, old_remote_path, new_remote_path
        )

        try:
            if protocol == "FTP":
                ftp = self.ftp_connections.get(server_name)
                if not ftp:
                    logger.debug("_server_rename_file: No FTP connection for %s", server_name)
                    return False

                ftp.rename(old_remote_path, new_remote_path)
                logger.debug("_server_rename_file: FTP rename successful")
                return True
            # SFTP
            sftp = self.sftp_connections.get(server_name)
            if not sftp:
                logger.debug("_server_rename_file: No SFTP connection for %s", server_name)
                return False

            logger.debug("_server_rename_file: Calling sftp.rename('%s', '%s')", old_remote_path, new_remote_path)
            sftp.rename(old_remote_path, new_remote_path)
            logger.debug("_server_rename_file: SFTP rename successful")
            return True

        except Exception as e:
            logger.error("Error renaming on %s: %s", server_name, e)
            logger.debug("_server_rename_file: Exception details - type=%s, args=%s", type(e).__name__, e.args)
            self._set_status(f"Rename failed: {e}")
            return False

    def _server_mkdir(self, server: dict, remote_path: str) -> bool:
        """Create a directory on the server.

        Args:
            server: Server dict with connection details
            remote_path: Remote directory path to create

        Returns:
            True if successful or already exists, False on error
        """
        server_name = server["name"]
        protocol = server.get("protocol", "FTP")

        logger.debug(
            "_server_mkdir: server=%s, protocol=%s, remote_path='%s'",
            server_name, protocol, remote_path
        )

        try:
            if protocol == "FTP":
                ftp = self.ftp_connections.get(server_name)
                if not ftp:
                    logger.debug("_server_mkdir: No FTP connection for %s", server_name)
                    return False

                try:
                    ftp.mkd(remote_path)
                    logger.info("Created directory on server: %s", remote_path)
                except Exception as e:
                    # FTP 550 is the standard reply for "directory exists"
                    # or "action not taken"; also check the text for safety.
                    if "exists" in str(e).lower() or "550" in str(e):
                        logger.debug("Directory already exists: %s", remote_path)
                        return True
                    raise
                return True
            # SFTP
            sftp = self.sftp_connections.get(server_name)
            if not sftp:
                return False

            try:
                sftp.mkdir(remote_path)
                logger.info("Created directory on server: %s", remote_path)
            except IOError as e:
                # SFTP raises IOError; errno 17 is POSIX EEXIST
                if "exists" in str(e).lower() or e.errno == 17:
                    logger.debug("Directory already exists: %s", remote_path)
                    return True
                raise
            return True

        except Exception as e:
            logger.error("Error creating directory on %s: %s", server_name, e)
            self._set_status(f"Failed to create directory: {e}")
            return False

    def _server_rmdir(self, server: dict, remote_path: str) -> bool:
        """Remove a directory from the server.

        Args:
            server: Server dict with connection details
            remote_path: Remote directory path to remove

        Returns:
            True if successful, False on error
        """
        server_name = server["name"]
        protocol = server.get("protocol", "FTP")

        try:
            if protocol == "FTP":
                ftp = self.ftp_connections.get(server_name)
                if not ftp:
                    return False

                try:
                    ftp.rmd(remote_path)
                    logger.info("Removed directory from server: %s", remote_path)
                except Exception as e:
                    # Directory might not exist or not be empty
                    logger.error("Error removing directory: %s", e)
                    return False
                return True
            # SFTP
            sftp = self.sftp_connections.get(server_name)
            if not sftp:
                return False

            try:
                sftp.rmdir(remote_path)
                logger.info("Removed directory from server: %s", remote_path)
            except IOError as e:
                logger.error("Error removing directory: %s", e)
                return False
            return True

        except Exception as e:
            logger.error("Error removing directory on %s: %s", server_name, e)
            return False

    def _server_navigate(self, server: dict, remote_path: str) -> bool:
        """Change current directory on the server.

        Args:
            server: Server dict with connection details
            remote_path: Remote directory to navigate to

        Returns:
            True if successful, False on error
        """
        server_name = server["name"]
        protocol = server.get("protocol", "FTP")

        try:
            if protocol == "FTP":
                ftp = self.ftp_connections.get(server_name)
                if not ftp:
                    return False

                ftp.cwd(remote_path)
                return True
            # SFTP
            sftp = self.sftp_connections.get(server_name)
            if not sftp:
                return False

            sftp.chdir(remote_path)
            return True

        except Exception as e:
            logger.error("Error navigating on %s: %s", server_name, e)
            self._set_status(f"Navigation failed: {e}")
            return False

    def _server_get_current_dir(self, server: dict) -> str:
        """Get current working directory on the server.

        Args:
            server: Server dict with connection details

        Returns:
            Current directory path or "/" on error
        """
        server_name = server["name"]
        protocol = server.get("protocol", "FTP")

        try:
            if protocol == "FTP":
                ftp = self.ftp_connections.get(server_name)
                if ftp:
                    return ftp.pwd()
            else:  # SFTP
                sftp = self.sftp_connections.get(server_name)
                if sftp:
                    return sftp.getcwd() or "/"
        except Exception as e:
            logger.debug("Error getting current dir on %s: %s", server_name, e)

        return "/"

    # =========================================================================
    # Cache Cleanup and Utility Helpers
    # =========================================================================

    def _cleanup_server_cache(self):
        """Clean up the temporary server cache directories."""
        import shutil

        # Clean up saves cache
        if self._server_temp_save_path and self._server_temp_save_path.exists():
            try:
                # Remove all files in the cache directory
                for f in self._server_temp_save_path.iterdir():
                    try:
                        if f.is_file():
                            f.unlink()
                        elif f.is_dir():
                            shutil.rmtree(f)
                    except Exception:
                        pass
                logger.debug("Cleaned up server saves cache: %s", self._server_temp_save_path)
            except Exception as e:
                logger.debug("Error cleaning server saves cache: %s", e)

        self._server_temp_save_path = None

        # Clean up mods cache
        if self._server_temp_mods_path and self._server_temp_mods_path.exists():
            try:
                # Remove all files in the cache directory
                for f in self._server_temp_mods_path.iterdir():
                    try:
                        if f.is_file():
                            f.unlink()
                        elif f.is_dir():
                            shutil.rmtree(f)
                    except Exception:
                        pass
                logger.debug("Cleaned up server mods cache: %s", self._server_temp_mods_path)
            except Exception as e:
                logger.debug("Error cleaning server mods cache: %s", e)

        self._server_temp_mods_path = None

    def _parse_sftp_connection_string(self, connection: str) -> tuple:
        """Parse an SFTP connection string like sftp://user@host:port.

        Returns:
            Tuple of (host, port, user_from_url) or (None, None, None) if invalid
        """
        # Regex groups: (1) optional user, (2) host, (3) optional port
        # e.g. "sftp://admin@192.168.1.1:2222" -> ("admin", "192.168.1.1", 2222)
        pattern = r'^sftp://(?:([^@]+)@)?([^:]+)(?::(\d+))?$'
        match = re.match(pattern, connection)

        if not match:
            return None, None, None

        user_from_url = match.group(1)  # May be None if no user@ prefix
        host = match.group(2)
        port = int(match.group(3)) if match.group(3) else 22  # SSH default

        return host, port, user_from_url

    # =========================================================================
    # Server Tab Event Handlers
    # =========================================================================

    def _show_server_context_menu(self, _event, server: dict):
        """Handle right-click on server tab - open configuration dialog."""
        self._edit_server_dialog(server)

    def _open_server_terminal(self, server: dict):
        """Open terminal for a server, connecting if not already connected."""
        server_name = server["name"]
        conn_state = self.server_connection_states.get(server_name, "disconnected")

        if conn_state == "connected":
            # Already connected, just open terminal
            protocol = server.get("protocol", "FTP")
            if protocol == "FTP":
                ftp = self.ftp_connections.get(server_name)
                if ftp:
                    try:
                        current_dir = ftp.pwd()
                    except Exception:
                        current_dir = "/"
                    self._show_terminal_popup(server, current_dir)
            else:  # SFTP
                sftp = self.sftp_connections.get(server_name)
                if sftp:
                    try:
                        current_dir = sftp.getcwd() or "/"
                    except Exception:
                        current_dir = "/"
                    self._show_terminal_popup(server, current_dir)
        else:
            # Not connected - connect first (terminal will open after connection)
            self._connect_server(server)

    def _on_server_tab_selected(self, server: dict):
        """Handle selection of a server tab.

        Acts as a toggle: clicking a connected server disconnects it;
        clicking a disconnected/error server initiates a new connection.
        While a connection attempt is in progress ("connecting"), clicks
        are ignored.
        """
        server_name = server["name"]
        conn_state = self.server_connection_states.get(server_name, "disconnected")

        if conn_state == "connected":
            # Toggle off: disconnect and deselect
            self._disconnect_server(server)
            self.current_server = None
        elif conn_state in ("error", "disconnected"):
            if not self._show_server_warning():
                return  # User cancelled the safety warning

            self.current_server = server
            # Selecting a server clears the local installation selection
            self.current_installation = None

            # Force backup mode since server interaction is save-centric
            self.current_mode = "backup"
            self._update_toolbar_button_states()
            self._update_pane_headers_for_mode()

            self._connect_server(server)
            # Stagger list refreshes to give the background connection
            # thread time to finish before we query remote files.
            self.after(500, self._refresh_item_list)
            self.after(600, self._refresh_versions_list)
        # If "connecting", do nothing - wait for connection to complete

        # Update button highlighting
        self._refresh_tabs()

    # =========================================================================
    # Connection Lifecycle (connect, disconnect, keepalive)
    # =========================================================================

    def _show_server_warning(self) -> bool:
        """Show warning dialog before connecting to server.

        Returns:
            True if user wants to proceed, False if cancelled
        """
        # Mutable container lets the nested on_ok closure communicate the
        # user's choice back to the caller after wait_window returns.
        result = [False]

        dialog = ctk.CTkToplevel(self)
        dialog.title("Server Connection Warning")
        dialog.geometry("450x260")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        # Center on parent
        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 450) // 2
        y = self.winfo_y() + (self.winfo_height() - 260) // 2
        dialog.geometry(f"+{x}+{y}")
        self._set_dialog_icon(dialog)

        # Warning icon and message
        content = ctk.CTkFrame(dialog, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=PADDING["large"], pady=PADDING["large"])

        # Warning label with icon
        warning_label = ctk.CTkLabel(
            content,
            text="\u26A0  Warning",
            font=FONTS["heading"],
            text_color="#f39c12"
        )
        warning_label.pack(pady=(0, PADDING["medium"]))

        # Message
        message = ctk.CTkLabel(
            content,
            text="Before modifying files on a remote server, it is HIGHLY\n"
                 "recommended that you stop the game server first.\n\n"
                 "Modifying save files while the server is running may\n"
                 "cause data corruption or loss.",
            font=FONTS["body"],
            justify="center"
        )
        message.pack(pady=(0, PADDING["large"]))

        # Buttons
        btn_frame = ctk.CTkFrame(content, fg_color="transparent")
        btn_frame.pack(fill="x")

        def on_ok():
            result[0] = True
            dialog.destroy()

        ok_btn = ctk.CTkButton(
            btn_frame, text="OK", width=100,
            fg_color="#1a5fb4", hover_color="#1a4f8f",
            command=on_ok
        )
        ok_btn.pack(pady=5)

        dialog.wait_window()
        return result[0]

    def _disconnect_server(self, server: dict):
        """Disconnect from a server."""
        server_name = server["name"]
        protocol = server.get("protocol", "FTP")

        try:
            if protocol == "FTP":
                # FTP: quit() sends the QUIT command and closes the socket.
                if server_name in self.ftp_connections:
                    try:
                        self.ftp_connections[server_name].quit()
                    except Exception:
                        pass  # Connection may already be closed
                    del self.ftp_connections[server_name]
            else:  # SFTP
                # SFTP requires closing both the SFTPClient and the
                # underlying SSH Transport (two separate resources).
                if server_name in self.sftp_connections:
                    try:
                        self.sftp_connections[server_name].close()
                    except Exception:
                        pass
                    del self.sftp_connections[server_name]
                if server_name in self.sftp_transports:
                    try:
                        self.sftp_transports[server_name].close()
                    except Exception:
                        pass
                    del self.sftp_transports[server_name]

            self.server_connection_states[server_name] = "disconnected"
            self._set_status(f"Disconnected from {server_name}")

            # Clean up server cache
            self._cleanup_server_cache()

            self._refresh_tabs()

        except Exception as e:
            logger.error("Error disconnecting from %s: %s", server_name, e)
            self.server_connection_states[server_name] = "disconnected"
            self._cleanup_server_cache()
            self._refresh_tabs()

    def _connect_server(self, server: dict):
        """Establish FTP or SFTP connection to a server in a background thread."""
        import threading

        server_name = server["name"]

        # If already connected, just select it
        if self.server_connection_states.get(server_name) == "connected":
            self._set_status(f"Already connected to {server_name}")
            return

        # Get connection details from server dict
        host = server.get("host", "")
        port = int(server.get("port", 21))
        protocol = server.get("protocol", "FTP")
        username = server.get("username", "")
        password = server.get("password", "")

        if not host:
            self._set_status(f"No host specified for {server_name}")
            self.server_connection_states[server_name] = "error"
            self._refresh_tabs()
            return

        if not username:
            self._set_status(f"No username specified for {server_name}")
            self.server_connection_states[server_name] = "error"
            self._refresh_tabs()
            return

        # Update status
        self.server_connection_states[server_name] = "connecting"
        self._set_status(f"Connecting to {server_name} via {protocol}...")
        self._refresh_tabs()

        def connect_thread():
            # Runs on a daemon thread to avoid blocking the GUI during
            # the TCP handshake and authentication exchange. All UI
            # updates are dispatched back to the main thread via after().
            try:
                if protocol == "FTP":
                    from ftplib import FTP

                    ftp = FTP()
                    ftp.connect(host, port, timeout=10)
                    ftp.login(username, password)

                    current_dir = ftp.pwd()

                    self.ftp_connections[server_name] = ftp
                    self.server_connection_states[server_name] = "connected"

                    # Schedule UI update on tkinter main thread
                    self.after(
                        0,
                        lambda: self._set_status(
                            f"Connected to {server_name}"
                            f" - Path: {current_dir}"))
                    self.after(0, self._refresh_tabs)

                else:  # SFTP
                    import paramiko

                    # paramiko uses a Transport (SSH channel) as the
                    # underlying connection, then layers SFTP on top.
                    transport = paramiko.Transport((host, port))
                    transport.connect(username=username, password=password)

                    # Create SFTP client
                    sftp = paramiko.SFTPClient.from_transport(transport)

                    # Get current directory
                    current_dir = sftp.getcwd() or "/"

                    # Store connection
                    self.sftp_transports[server_name] = transport
                    self.sftp_connections[server_name] = sftp
                    self.server_connection_states[server_name] = "connected"

                    # Update UI from main thread
                    self.after(
                        0,
                        lambda: self._set_status(
                            f"Connected to {server_name}"
                            f" - Path: {current_dir}"))
                    self.after(0, self._refresh_tabs)

            except Exception as e:
                logger.error("%s connection error for %s: %s", protocol, server_name, e)
                self.server_connection_states[server_name] = "error"
                self.after(0, lambda: self._set_status(f"Connection failed: {e}"))
                self.after(0, self._refresh_tabs)

        # Run connection in background thread
        thread = threading.Thread(target=connect_thread, daemon=True)
        thread.start()

    # =========================================================================
    # Server Terminal (interactive directory browser popup)
    # =========================================================================

    def _show_terminal_popup(self, server: dict, current_dir: str):
        """Show a terminal-like popup for interacting with the server."""
        server_name = server["name"]
        protocol = server.get("protocol", "FTP")

        dialog = ctk.CTkToplevel(self)
        dialog.title(f"{protocol} Terminal - {server_name}")
        dialog.geometry("700x500")
        dialog.transient(self)

        # Center on parent
        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 700) // 2
        y = self.winfo_y() + (self.winfo_height() - 500) // 2
        dialog.geometry(f"+{x}+{y}")
        self._set_dialog_icon(dialog)

        # Container
        container = ctk.CTkFrame(dialog, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=PADDING["medium"], pady=PADDING["medium"])

        # Output area styled as a classic terminal (green text on dark bg)
        output_text = ctk.CTkTextbox(
            container, font=("Consolas", 12), height=350,
            fg_color="#1e1e1e", text_color="#00ff00"
        )
        output_text.pack(fill="both", expand=True, pady=(0, PADDING["small"]))

        # Initial output
        output_text.insert("end", f"Connected to {server_name} via {protocol}\n")
        output_text.insert("end", f"Current directory: {current_dir}\n")
        output_text.insert("end", "-" * 50 + "\n")

        # List initial directory
        self._terminal_list_dir(server, output_text)

        # Command input frame
        input_frame = ctk.CTkFrame(container, fg_color="transparent")
        input_frame.pack(fill="x", pady=(0, PADDING["small"]))

        prompt_label = ctk.CTkLabel(input_frame, text=">", font=("Consolas", 12))
        prompt_label.pack(side="left", padx=(0, 5))

        cmd_entry = ctk.CTkEntry(input_frame, font=("Consolas", 12), height=28)
        cmd_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))

        def execute_command():
            cmd = cmd_entry.get().strip()
            if not cmd:
                return
            cmd_entry.delete(0, "end")
            output_text.insert("end", f"> {cmd}\n")
            self._execute_terminal_command(server, cmd, output_text)
            output_text.see("end")

        cmd_entry.bind("<Return>", lambda e: execute_command())

        send_btn = ctk.CTkButton(
            input_frame, text="Send", width=60,
            command=execute_command
        )
        send_btn.pack(side="right")

        # Button frame
        btn_frame = ctk.CTkFrame(container, fg_color="transparent")
        btn_frame.pack(fill="x")

        # Quick action buttons
        def do_pwd():
            output_text.insert("end", "> pwd\n")
            self._execute_terminal_command(server, "pwd", output_text)
            output_text.see("end")

        def do_ls():
            output_text.insert("end", "> ls\n")
            self._execute_terminal_command(server, "ls", output_text)
            output_text.see("end")

        pwd_btn = ctk.CTkButton(btn_frame, text="PWD", width=60, command=do_pwd)
        pwd_btn.pack(side="left", padx=(0, 5))

        ls_btn = ctk.CTkButton(btn_frame, text="LS", width=60, command=do_ls)
        ls_btn.pack(side="left", padx=(0, 5))

        close_btn = ctk.CTkButton(
            btn_frame, text="Close", width=80,
            fg_color="#c01c28", hover_color="#a01020",
            command=dialog.destroy
        )
        close_btn.pack(side="right")

        # Focus command entry
        cmd_entry.focus_set()

    def _terminal_list_dir(self, server: dict, output_text):
        """List directory contents in terminal output."""
        server_name = server["name"]
        protocol = server.get("protocol", "FTP")

        try:
            if protocol == "FTP":
                ftp = self.ftp_connections.get(server_name)
                if ftp:
                    files = ftp.nlst()
                    output_text.insert("end", "Directory listing:\n")
                    for f in files:
                        output_text.insert("end", f"  {f}\n")
            else:  # SFTP
                sftp = self.sftp_connections.get(server_name)
                if sftp:
                    files = sftp.listdir()
                    output_text.insert("end", "Directory listing:\n")
                    for f in files:
                        output_text.insert("end", f"  {f}\n")
        except Exception as e:
            output_text.insert("end", f"Error listing directory: {e}\n")

    def _execute_terminal_command(self, server: dict, cmd: str, output_text):
        """Execute a command on the server and display output."""
        server_name = server["name"]
        protocol = server.get("protocol", "FTP")

        try:
            parts = cmd.split()
            if not parts:
                return

            command = parts[0].lower()
            args = parts[1:] if len(parts) > 1 else []

            if protocol == "FTP":
                ftp = self.ftp_connections.get(server_name)
                if not ftp:
                    output_text.insert("end", "Error: Not connected\n")
                    return

                if command == "pwd":
                    result = ftp.pwd()
                    output_text.insert("end", f"{result}\n")
                elif command in ("ls", "dir"):
                    files = ftp.nlst()
                    for f in files:
                        output_text.insert("end", f"  {f}\n")
                elif command == "cd":
                    if args:
                        ftp.cwd(args[0])
                        output_text.insert("end", f"Changed to: {ftp.pwd()}\n")
                    else:
                        output_text.insert("end", "Usage: cd <directory>\n")
                elif command == "help":
                    output_text.insert("end", "Available commands:\n")
                    output_text.insert("end", "  pwd       - Print current directory\n")
                    output_text.insert("end", "  ls/dir    - List directory contents\n")
                    output_text.insert("end", "  cd <dir>  - Change directory\n")
                    output_text.insert("end", "  help      - Show this help\n")
                else:
                    output_text.insert(
                        "end",
                        f"Unknown command: {command}. "
                        "Type 'help' for available "
                        "commands.\n")

            else:  # SFTP
                sftp = self.sftp_connections.get(server_name)
                if not sftp:
                    output_text.insert("end", "Error: Not connected\n")
                    return

                if command == "pwd":
                    result = sftp.getcwd() or "/"
                    output_text.insert("end", f"{result}\n")
                elif command in ("ls", "dir"):
                    files = sftp.listdir()
                    for f in files:
                        output_text.insert("end", f"  {f}\n")
                elif command == "cd":
                    if args:
                        sftp.chdir(args[0])
                        output_text.insert("end", f"Changed to: {sftp.getcwd()}\n")
                    else:
                        output_text.insert("end", "Usage: cd <directory>\n")
                elif command == "help":
                    output_text.insert("end", "Available commands:\n")
                    output_text.insert("end", "  pwd       - Print current directory\n")
                    output_text.insert("end", "  ls/dir    - List directory contents\n")
                    output_text.insert("end", "  cd <dir>  - Change directory\n")
                    output_text.insert("end", "  help      - Show this help\n")
                else:
                    output_text.insert(
                        "end",
                        f"Unknown command: {command}. "
                        "Type 'help' for available "
                        "commands.\n")

        except Exception as e:
            output_text.insert("end", f"Error: {e}\n")

    # =========================================================================
    # INI Editor
    # =========================================================================

    def _show_ini_editor(self, server: dict, config_path: str, parent_dialog):
        """Show the INI Editor dialog for MoriaServerConfig.ini."""
        import tempfile

        server_name = server["name"]

        # Validate the config path
        if not config_path or not config_path.strip():
            self._show_info_dialog(
                "Missing Path",
                "Please enter the path to MoriaServerConfig.ini first.")
            return

        # Automatically append filename if path is just a directory
        config_path = config_path.strip()
        if not config_path.lower().endswith('.ini'):
            # It's a directory path, append the filename
            if config_path.endswith('/'):
                config_path = config_path + "MoriaServerConfig.ini"
            else:
                config_path = config_path + "/MoriaServerConfig.ini"
            logger.debug("INI Editor: Appended filename, full path: %s", config_path)

        # Check if connected
        conn_state = self.server_connection_states.get(server_name, "disconnected")
        protocol = server.get("protocol", "FTP")

        # Debug info for connection check
        logger.debug("INI Editor: server=%s, protocol=%s, conn_state=%s", server_name, protocol, conn_state)
        logger.debug("INI Editor: config_path=%s", config_path)
        logger.debug("INI Editor: sftp_connections keys=%s", list(self.sftp_connections.keys()))
        logger.debug("INI Editor: ftp_connections keys=%s", list(self.ftp_connections.keys()))

        if conn_state != "connected":
            self._show_info_dialog(
                "Not Connected",
                f"Please connect to the server first before editing the INI file.\n\n"
                f"Current state: {conn_state}")
            return

        # Download the INI file
        try:
            if protocol == "SFTP":
                sftp = self.sftp_connections.get(server_name)
                if not sftp:
                    raise RuntimeError(f"SFTP connection object not found for '{server_name}'")
                # Download to temp file
                temp_file = tempfile.NamedTemporaryFile(
                    mode='w', suffix='.ini', delete=False, encoding='utf-8')
                temp_path = temp_file.name
                temp_file.close()
                logger.debug("INI Editor: Downloading via SFTP from %s to %s", config_path, temp_path)
                sftp.get(config_path, temp_path)
            else:
                ftp = self.ftp_connections.get(server_name)
                if not ftp:
                    raise RuntimeError(f"FTP connection object not found for '{server_name}'")
                temp_file = tempfile.NamedTemporaryFile(
                    mode='wb', suffix='.ini', delete=False)
                temp_path = temp_file.name
                logger.debug("INI Editor: Downloading via FTP from %s to %s", config_path, temp_path)
                ftp.retrbinary(f"RETR {config_path}", temp_file.write)
                temp_file.close()

            # Read the file content
            with open(temp_path, 'r', encoding='utf-8') as f:
                ini_content = f.read()

        except Exception as e:
            logger.error("INI Editor download failed: %s", e, exc_info=True)
            self._show_info_dialog(
                "Download Error",
                f"Failed to download INI file from:\n{config_path}\n\nError: {e}")
            return

        # Parse INI (with multi-line handling)
        ini_data = self._parse_ini_content(ini_content)

        # Create the editor dialog
        dialog = ctk.CTkToplevel(parent_dialog)
        dialog.title(f"INI Editor - {server_name}")
        dialog.geometry("700x700")
        dialog.resizable(True, True)
        dialog.transient(parent_dialog)
        dialog.grab_set()

        # Center on screen
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() - 700) // 2
        y = (dialog.winfo_screenheight() - 700) // 2
        dialog.geometry(f"+{x}+{y}")
        self._set_dialog_icon(dialog)

        # Main container
        container = ctk.CTkFrame(dialog, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=PADDING["medium"], pady=PADDING["medium"])

        # Title
        title_label = ctk.CTkLabel(
            container, text="Server Configuration Editor",
            font=FONTS["title"], anchor="w")
        title_label.pack(fill="x", pady=(0, PADDING["small"]))

        # Scrollable content area
        scroll_frame = ctk.CTkScrollableFrame(container, fg_color=("#e8e8e8", "#2a2a2a"))
        scroll_frame.pack(fill="both", expand=True, pady=(0, PADDING["medium"]))

        # Store widget references for reading values
        field_widgets = {}

        # Define field configurations
        field_config = {
            "Host": {
                "ListenPort": {"type": "entry", "label": "Listen Port"},
                "ListenAddress": {"type": "entry", "label": "Listen Address"},
                "AdvertiseAddress": {"type": "entry", "label": "Advertise Address"},
                "AdvertisePort": {"type": "entry", "label": "Advertise Port"},
                "InitialConnectionRetryTime": {"type": "entry", "label": "Initial Retry Time (sec)"},
                "AfterDisconnectionRetryTime": {"type": "entry", "label": "After Disconnect Retry Time (sec)"},
            },
            "Main": {
                "OptionalPassword": {"type": "entry", "label": "Server Password"},
            },
            "World": {
                "Name": {"type": "entry", "label": "World Name"},
                "OptionalWorldFilename": {"type": "entry", "label": "World Filename"},
            },
            "World.Create": {
                "Type": {"type": "dropdown", "label": "World Type",
                         "values": ["campaign", "sandbox"]},
                "Seed": {"type": "entry", "label": "Seed"},
                "Difficulty.Preset": {"type": "dropdown", "label": "Difficulty Preset",
                                      "values": ["story", "solo", "normal", "hard", "custom"]},
                "Difficulty.Custom.CombatDifficulty": {"type": "dropdown", "label": "Combat Difficulty",
                                                       "values": ["verylow", "low", "default", "high", "veryhigh"]},
                "Difficulty.Custom.EnemyAggression": {"type": "dropdown", "label": "Enemy Aggression",
                                                      "values": ["low", "default", "high", "veryhigh"]},
                "Difficulty.Custom.SurvivalDifficulty": {"type": "dropdown", "label": "Survival Difficulty",
                                                         "values": ["verylow", "low", "default", "high"]},
                "Difficulty.Custom.MiningDrops": {"type": "dropdown", "label": "Mining Drops",
                                                   "values": ["verylow", "low", "default", "high"]},
                "Difficulty.Custom.WorldDrops": {"type": "dropdown", "label": "World Drops",
                                                  "values": ["verylow", "low", "default", "high"]},
                "Difficulty.Custom.HordeFrequency": {"type": "dropdown", "label": "Horde Frequency",
                                                      "values": ["verylow", "low", "default", "high", "veryhigh"]},
                "Difficulty.Custom.SiegeFrequency": {"type": "dropdown", "label": "Siege Frequency",
                                                      "values": ["verylow", "low", "default", "high", "veryhigh"]},
                "Difficulty.Custom.PatrolFrequency": {"type": "dropdown", "label": "Patrol Frequency",
                                                       "values": ["verylow", "low", "default", "high", "veryhigh"]},
                "UpgradeOptionalDLC.Array": {"type": "entry", "label": "Upgrade DLC Array"},
                "OptionalDLC.Array": {"type": "entry", "label": "Optional DLC Array"},
            },
            "Console": {
                "Enabled": {"type": "dropdown", "label": "Console Enabled",
                            "values": ["true", "false"]},
            },
            "Performance": {
                "ServerFPS": {"type": "dropdown", "label": "Server FPS",
                              "values": ["30", "60"]},
                "LoadedAreaLimit": {"type": "slider", "label": "Loaded Area Limit",
                                    "min": 4, "max": 32},
            },
        }

        # Create sections
        for section_name, fields in field_config.items():
            # Section header
            section_frame = ctk.CTkFrame(scroll_frame, fg_color=("#d0d0d0", "#3a3a3a"))
            section_frame.pack(fill="x", padx=5, pady=(10, 5))

            section_label = ctk.CTkLabel(
                section_frame, text=f"[{section_name}]",
                font=FONTS["heading"], anchor="w",
                text_color=("#1a5fb4", "#5b9bd5"))
            section_label.pack(fill="x", padx=10, pady=5)

            # Fields container
            fields_frame = ctk.CTkFrame(scroll_frame, fg_color="transparent")
            fields_frame.pack(fill="x", padx=15, pady=(0, 5))

            for key, config in fields.items():
                # Get current value from parsed INI
                current_value = ini_data.get(section_name, {}).get(key, "")

                # Field row
                row_frame = ctk.CTkFrame(fields_frame, fg_color="transparent")
                row_frame.pack(fill="x", pady=3)

                label = ctk.CTkLabel(
                    row_frame, text=config["label"] + ":",
                    font=FONTS["body"], anchor="w", width=180)
                label.pack(side="left", padx=(0, 10))

                widget_key = f"{section_name}.{key}"

                if config["type"] == "entry":
                    widget = ctk.CTkEntry(row_frame, font=FONTS["body"], height=28, width=300)
                    widget.insert(0, current_value)
                    widget.pack(side="left", fill="x", expand=True)
                    field_widgets[widget_key] = ("entry", widget)

                elif config["type"] == "dropdown":
                    var = ctk.StringVar(value=current_value if current_value else config["values"][0])
                    widget = ctk.CTkOptionMenu(
                        row_frame, values=config["values"], variable=var,
                        width=200, height=28, font=FONTS["body"])
                    widget.pack(side="left")
                    field_widgets[widget_key] = ("dropdown", var)

                elif config["type"] == "combobox":
                    # Combobox allows both dropdown and freeform entry
                    var = ctk.StringVar(value=current_value if current_value else "")
                    widget = ctk.CTkComboBox(
                        row_frame, values=config["values"], variable=var,
                        width=200, height=28, font=FONTS["body"])
                    widget.pack(side="left")
                    field_widgets[widget_key] = ("combobox", var)

                elif config["type"] == "slider":
                    # Slider with label showing value
                    slider_frame = ctk.CTkFrame(row_frame, fg_color="transparent")
                    slider_frame.pack(side="left", fill="x", expand=True)

                    try:
                        init_val = int(float(current_value)) if current_value else config["min"]
                    except ValueError:
                        init_val = config["min"]
                    init_val = max(config["min"], min(config["max"], init_val))

                    value_label = ctk.CTkLabel(slider_frame, text=str(init_val), font=FONTS["body"], width=40)
                    value_label.pack(side="right", padx=(10, 0))

                    def make_slider_callback(lbl):
                        def callback(val):
                            lbl.configure(text=str(int(val)))
                        return callback

                    widget = ctk.CTkSlider(
                        slider_frame, from_=config["min"], to=config["max"],
                        number_of_steps=config["max"] - config["min"],
                        width=200, command=make_slider_callback(value_label))
                    widget.set(init_val)
                    widget.pack(side="left")
                    field_widgets[widget_key] = ("slider", widget)

        # Bottom button frame
        btn_frame = ctk.CTkFrame(container, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(PADDING["small"], 0))

        def on_cancel():
            # Clean up temp file
            try:
                import os
                os.unlink(temp_path)
            except Exception:
                pass
            dialog.destroy()

        def on_save():
            logger.debug("INI Editor: Save button clicked")
            # Collect all values
            new_ini_data = {}
            for widget_key, (widget_type, widget) in field_widgets.items():
                section, key = widget_key.split(".", 1)
                if section not in new_ini_data:
                    new_ini_data[section] = {}

                if widget_type == "entry":
                    value = widget.get()
                elif widget_type in ("dropdown", "combobox"):
                    value = widget.get()
                elif widget_type == "slider":
                    value = str(int(widget.get()))
                else:
                    value = ""

                new_ini_data[section][key] = value

            # Generate INI content
            new_content = self._generate_ini_content(new_ini_data)
            logger.debug("INI Editor: Generated new content (%d bytes)", len(new_content))

            # Write to temp file
            try:
                with open(temp_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                logger.debug("INI Editor: Wrote to temp file: %s", temp_path)
            except Exception as e:
                logger.error("INI Editor: Failed to write temp file: %s", e)
                self._show_info_dialog("Save Error", f"Failed to write temp file:\n{e}")
                return

            # Upload back to server
            try:
                protocol = server.get("protocol", "FTP")
                logger.debug("INI Editor: Uploading via %s to %s", protocol, config_path)
                if protocol == "SFTP":
                    sftp = self.sftp_connections.get(server_name)
                    if sftp:
                        sftp.put(temp_path, config_path)
                        logger.info("INI Editor: Successfully uploaded via SFTP to %s", config_path)
                    else:
                        raise RuntimeError("SFTP connection lost")
                else:
                    ftp = self.ftp_connections.get(server_name)
                    if ftp:
                        with open(temp_path, 'rb') as f:
                            ftp.storbinary(f"STOR {config_path}", f)
                        logger.info("INI Editor: Successfully uploaded via FTP to %s", config_path)
                    else:
                        raise RuntimeError("FTP connection lost")

                # Delete temp file after successful upload
                try:
                    import os
                    os.unlink(temp_path)
                    logger.debug("INI Editor: Deleted temp file after upload")
                except Exception:
                    pass

                self._show_info_dialog(
                    "Saved",
                    "Configuration saved successfully!\n\nNote: Server restart may be required for changes to take effect.")
                dialog.destroy()

            except Exception as e:
                logger.error("INI Editor: Upload failed: %s", e, exc_info=True)
                self._show_info_dialog("Upload Error", f"Failed to upload INI file:\n{e}")

        cancel_btn = ctk.CTkButton(
            btn_frame, text="Cancel", width=100,
            fg_color="gray50", hover_color="gray40",
            text_color="white",
            command=on_cancel)
        cancel_btn.pack(side="left")

        save_btn = ctk.CTkButton(
            btn_frame, text="Save", width=100,
            fg_color="#2d8a4e", hover_color="#1e5c34",
            text_color="white",
            command=on_save)
        save_btn.pack(side="right")

        dialog.protocol("WM_DELETE_WINDOW", on_cancel)
        dialog.wait_window()

    def _parse_ini_content(self, content: str) -> dict:
        """Parse INI content into a nested dict structure."""
        result = {}
        current_section = None

        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith(';') or line.startswith('#'):
                continue

            if line.startswith('[') and line.endswith(']'):
                current_section = line[1:-1]
                if current_section not in result:
                    result[current_section] = {}
            elif '=' in line and current_section:
                key, _, value = line.partition('=')
                key = key.strip()
                value = value.strip()
                # Remove quotes if present
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                result[current_section][key] = value

        return result

    def _generate_ini_content(self, data: dict) -> str:
        """Generate INI content from a nested dict structure."""
        lines = []

        # Define section order
        section_order = ["Host", "Main", "World", "World.Create", "Console", "Performance"]

        for section in section_order:
            if section not in data:
                continue
            lines.append(f"[{section}]")
            for key, value in data[section].items():
                # Quote values with spaces
                if ' ' in value or not value:
                    lines.append(f'{key} = "{value}"')
                else:
                    lines.append(f'{key} = {value}')
            lines.append("")  # Blank line between sections

        return "\n".join(lines)

    # =========================================================================
    # Server Edit / Delete Dialogs
    # =========================================================================

    def _edit_server_dialog(self, server: dict):
        """Show dialog to edit an existing server."""
        dialog = ctk.CTkToplevel(self)
        dialog.title(f"Server Configuration - {server['name']}")
        dialog.geometry("750x500")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        # Center on parent
        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 750) // 2
        y = self.winfo_y() + (self.winfo_height() - 500) // 2
        dialog.geometry(f"+{x}+{y}")
        self._set_dialog_icon(dialog)

        # Main container
        container = ctk.CTkFrame(dialog, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=PADDING["medium"], pady=PADDING["medium"])

        original_name = server["name"]
        server_name = server["name"]

        # Get current connection state
        conn_state = self.server_connection_states.get(server_name, "disconnected")

        # Top action bar with Connect/Disconnect, Terminal (left) and Delete (right)
        action_bar = ctk.CTkFrame(container, fg_color="transparent")
        action_bar.pack(fill="x", pady=(0, PADDING["small"]))

        def update_conn_buttons():
            """Update button states based on connection."""
            nonlocal conn_state
            conn_state = self.server_connection_states.get(server_name, "disconnected")
            if conn_state == "connected":
                connect_btn.configure(state="disabled")
                disconnect_btn.configure(state="normal")
                conn_state_label.configure(text="Connected", text_color="#00AA00")
            elif conn_state == "connecting":
                connect_btn.configure(state="disabled")
                disconnect_btn.configure(state="disabled")
                conn_state_label.configure(text="Connecting...", text_color="orange")
            else:
                connect_btn.configure(state="normal")
                disconnect_btn.configure(state="disabled")
                state_text = "Error" if conn_state == "error" else "Disconnected"
                state_color = "red" if conn_state == "error" else "gray"
                conn_state_label.configure(text=state_text, text_color=state_color)

        def on_connect():
            dialog.destroy()
            self._on_server_tab_selected(server)

        def on_disconnect():
            self._disconnect_server(server)
            update_conn_buttons()

        def on_terminal():
            dialog.destroy()
            self._open_server_terminal(server)

        def on_delete():
            from tkinter import messagebox
            result = messagebox.askyesno(
                "Delete Server",
                f"Are you sure you want to delete the server '{original_name}'?",
                parent=dialog
            )
            if result:
                self._delete_server_from_ini(original_name)
                dialog.destroy()
                self._refresh_tabs()
                self._set_status(f"Server '{original_name}' deleted")

        # Connect button
        connect_btn = ctk.CTkButton(
            action_bar, text="Connect", width=80,
            fg_color="#1a5fb4", hover_color="#1a4f8f",
            text_color="white",
            command=on_connect
        )
        connect_btn.pack(side="left", padx=(0, 5))

        # Disconnect button
        disconnect_btn = ctk.CTkButton(
            action_bar, text="Disconnect", width=90,
            fg_color="#6c757d", hover_color="#5a6268",
            text_color="white",
            command=on_disconnect
        )
        disconnect_btn.pack(side="left", padx=(0, 10))

        terminal_btn = ctk.CTkButton(
            action_bar, text="Terminal", width=100,
            fg_color="#7c3aed", hover_color="#6d28d9",
            text_color="white",
            command=on_terminal
        )
        terminal_btn.pack(side="left")

        delete_btn = ctk.CTkButton(
            action_bar, text="\U0001F5D1", width=40,
            font=("Segoe UI", 16),
            fg_color="#c01c28", hover_color="#a01020",
            text_color="white",
            command=on_delete
        )
        delete_btn.pack(side="right")

        # Separator after action bar
        sep1 = ctk.CTkFrame(container, height=2, fg_color="gray50")
        sep1.pack(fill="x", pady=(0, PADDING["small"]))

        # Two-column frame
        columns_frame = ctk.CTkFrame(container, fg_color="transparent")
        columns_frame.pack(fill="both", expand=True)

        # Left column - Connection Info
        left_col = ctk.CTkFrame(columns_frame, fg_color="transparent")
        left_col.pack(side="left", fill="both", expand=True, padx=(0, PADDING["medium"]))

        # Connection info header with state
        conn_header_frame = ctk.CTkFrame(left_col, fg_color="transparent")
        conn_header_frame.pack(fill="x", pady=(0, 8))

        conn_label = ctk.CTkLabel(
            conn_header_frame, text="Connection Info",
            font=FONTS["heading"], anchor="w")
        conn_label.pack(side="left")

        # Connection state label
        conn_state_label = ctk.CTkLabel(conn_header_frame, text="", font=FONTS["body"], anchor="e")
        conn_state_label.pack(side="right")

        # Initialize button states
        update_conn_buttons()

        # Name field
        name_label = ctk.CTkLabel(left_col, text="Name:", font=FONTS["body"], anchor="w")
        name_label.pack(fill="x", pady=(0, 2))
        name_entry = ctk.CTkEntry(left_col, font=FONTS["body"], height=28)
        name_entry.insert(0, server["name"])
        name_entry.pack(fill="x", pady=(0, 8))

        # Host field
        host_label = ctk.CTkLabel(left_col, text="Host:", font=FONTS["body"], anchor="w")
        host_label.pack(fill="x", pady=(0, 2))
        host_entry = ctk.CTkEntry(left_col, font=FONTS["body"], height=28)
        host_entry.insert(0, server.get("host", ""))
        host_entry.pack(fill="x", pady=(0, 8))

        # Port and Protocol frame
        port_proto_frame = ctk.CTkFrame(left_col, fg_color="transparent")
        port_proto_frame.pack(fill="x", pady=(0, 8))

        port_label = ctk.CTkLabel(port_proto_frame, text="Port:", font=FONTS["body"], anchor="w")
        port_label.pack(side="left", padx=(0, 5))
        port_entry = ctk.CTkEntry(port_proto_frame, font=FONTS["body"], height=28, width=70)
        port_entry.insert(0, server.get("port", "21"))
        port_entry.pack(side="left", padx=(0, 15))

        proto_label = ctk.CTkLabel(
            port_proto_frame, text="Protocol:",
            font=FONTS["body"], anchor="w")
        proto_label.pack(side="left", padx=(0, 5))
        protocol_var = ctk.StringVar(value=server.get("protocol", "FTP"))
        protocol_dropdown = ctk.CTkOptionMenu(
            port_proto_frame, values=["FTP", "SFTP"], variable=protocol_var,
            width=90, height=28, font=FONTS["body"]
        )
        protocol_dropdown.pack(side="left")

        # Username field
        user_label = ctk.CTkLabel(left_col, text="Username:", font=FONTS["body"], anchor="w")
        user_label.pack(fill="x", pady=(0, 2))
        user_entry = ctk.CTkEntry(left_col, font=FONTS["body"], height=28)
        user_entry.insert(0, server["username"])
        user_entry.pack(fill="x", pady=(0, 8))

        # Password field
        pass_label = ctk.CTkLabel(left_col, text="Password:", font=FONTS["body"], anchor="w")
        pass_label.pack(fill="x", pady=(0, 2))

        pass_frame = ctk.CTkFrame(left_col, fg_color="transparent")
        pass_frame.pack(fill="x", pady=(0, 8))

        pass_entry = ctk.CTkEntry(pass_frame, font=FONTS["body"], height=28, show="*")
        pass_entry.insert(0, server["password"])
        pass_entry.pack(side="left", fill="x", expand=True)

        password_visible = {"visible": False}

        def toggle_password():
            password_visible["visible"] = not password_visible["visible"]
            pass_entry.configure(show="" if password_visible["visible"] else "*")

        eye_btn = ctk.CTkButton(
            pass_frame, text="\U0001F441", width=28, height=28,
            font=FONTS["body"], fg_color="transparent",
            hover_color=("gray80", "gray30"),
            command=toggle_password
        )
        eye_btn.pack(side="right", padx=(5, 0))

        # Vertical separator
        separator = ctk.CTkFrame(columns_frame, width=2, fg_color="gray50")
        separator.pack(side="left", fill="y", padx=PADDING["small"])

        # Right column - Server Paths
        right_col = ctk.CTkFrame(columns_frame, fg_color="transparent")
        right_col.pack(
            side="left", fill="both", expand=True,
            padx=(PADDING["medium"], 0))

        paths_label = ctk.CTkLabel(
            right_col, text="Server Paths",
            font=FONTS["heading"], anchor="w")
        paths_label.pack(fill="x", pady=(0, 8))

        # MoriaServerConfig.ini path with INI Editor button
        config_path_label = ctk.CTkLabel(
            right_col, text="MoriaServerConfig.ini:",
            font=FONTS["body"], anchor="w")
        config_path_label.pack(fill="x", pady=(0, 2))

        config_path_frame = ctk.CTkFrame(right_col, fg_color="transparent")
        config_path_frame.pack(fill="x", pady=(0, 8))

        config_path_entry = ctk.CTkEntry(config_path_frame, font=FONTS["body"], height=28)
        config_path_entry.insert(0, server.get("config_path", ""))
        config_path_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))

        def on_ini_editor():
            config_path = config_path_entry.get().strip()
            if not config_path:
                from tkinter import messagebox
                messagebox.showwarning(
                    "Missing Path",
                    "Please enter the MoriaServerConfig.ini path first.",
                    parent=dialog)
                return
            self._show_ini_editor(server, config_path, dialog)

        ini_editor_btn = ctk.CTkButton(
            config_path_frame, text="INI Editor", width=90,
            fg_color="#e65100", hover_color="#bf360c",
            text_color="white", font=FONTS["body"],
            command=on_ini_editor
        )
        ini_editor_btn.pack(side="right")

        # Pak file location path
        pak_path_label = ctk.CTkLabel(
            right_col, text="Pak File Location:",
            font=FONTS["body"], anchor="w")
        pak_path_label.pack(fill="x", pady=(0, 2))
        pak_path_entry = ctk.CTkEntry(right_col, font=FONTS["body"], height=28)
        pak_path_entry.insert(0, server.get("pak_path", ""))
        pak_path_entry.pack(fill="x", pady=(0, 8))

        # Save File Location path
        save_path_label = ctk.CTkLabel(
            right_col, text="Save File Location:",
            font=FONTS["body"], anchor="w")
        save_path_label.pack(fill="x", pady=(0, 2))
        save_path_entry = ctk.CTkEntry(right_col, font=FONTS["body"], height=28)
        save_path_entry.insert(0, server.get("save_path", ""))
        save_path_entry.pack(fill="x", pady=(0, 8))

        # Bottom button frame
        btn_frame = ctk.CTkFrame(container, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(PADDING["medium"], 0))

        def on_cancel():
            dialog.destroy()

        def on_apply():
            new_name = name_entry.get().strip()
            host = host_entry.get().strip()
            port = port_entry.get().strip()
            protocol = protocol_var.get()
            username = user_entry.get().strip()
            password = pass_entry.get()
            config_path = config_path_entry.get().strip()
            pak_path = pak_path_entry.get().strip()
            save_path = save_path_entry.get().strip()

            if not new_name:
                from tkinter import messagebox
                messagebox.showwarning(
                    "Missing Field",
                    "Please enter a name for this server.",
                    parent=dialog)
                return

            if not host:
                from tkinter import messagebox
                messagebox.showwarning("Missing Field", "Please enter a host.", parent=dialog)
                return

            if not port:
                port = "21" if protocol == "FTP" else "22"

            # If the server was renamed, remove the old INI section first
            # (the section key is the server name).
            if new_name != original_name:
                self._delete_server_from_ini(original_name)

            self._save_server_to_ini(
                new_name, host, port, protocol,
                username, password, config_path,
                pak_path, save_path)

            # Update current_server if this is the server being edited
            if self.current_server and self.current_server.get("name") == original_name:
                self.current_server["name"] = new_name
                self.current_server["host"] = host
                self.current_server["port"] = port
                self.current_server["protocol"] = protocol
                self.current_server["username"] = username
                self.current_server["password"] = password
                self.current_server["config_path"] = config_path
                self.current_server["pak_path"] = pak_path
                self.current_server["save_path"] = save_path

            dialog.destroy()
            self._refresh_tabs()
            self._set_status(f"Server '{new_name}' updated successfully")

        cancel_btn = ctk.CTkButton(
            btn_frame, text="Cancel", width=100,
            fg_color="gray50", hover_color="gray40",
            text_color="white",
            command=on_cancel
        )
        cancel_btn.pack(side="left")

        apply_btn = ctk.CTkButton(
            btn_frame, text="Apply", width=100,
            fg_color="#1a5fb4", hover_color="#1c4a8a",
            text_color="white",
            command=on_apply
        )
        apply_btn.pack(side="right")

        dialog.protocol("WM_DELETE_WINDOW", on_cancel)
        name_entry.focus_set()
        dialog.wait_window()

    def _delete_server(self, server: dict):
        """Delete a server after confirmation."""
        from tkinter import messagebox

        result = messagebox.askyesno(
            "Delete Server",
            f"Are you sure you want to delete the server '{server['name']}'?",
            parent=self
        )

        if result:
            self._delete_server_from_ini(server["name"])
            self._refresh_tabs()
            self._set_status(f"Server '{server['name']}' deleted")

    def _delete_server_from_ini(self, server_name: str):
        """Remove a server entry from myservers.ini."""
        from configparser import ConfigParser

        ini_path = GamePaths.CONFIG_DIR / "myservers.ini"

        if not ini_path.exists():
            return

        config = ConfigParser()
        try:
            config.read(ini_path, encoding="utf-8")
        except Exception as e:
            logger.warning("Failed to read myservers.ini: %s", e)
            return

        # Sanitize section name the same way as when saving
        section_name = server_name.replace("[", "(").replace("]", ")")

        if config.has_section(section_name):
            config.remove_section(section_name)
            try:
                with open(ini_path, "w", encoding="utf-8") as f:
                    config.write(f)
                logger.info("Deleted server '%s' from myservers.ini", server_name)
            except Exception as e:
                logger.error("Failed to save myservers.ini: %s", e)
