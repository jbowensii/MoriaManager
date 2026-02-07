"""Main application window with vertical tabs and split panes."""

from pathlib import Path
from typing import Optional
import tkinter as tk

import customtkinter as ctk
from PIL import Image, ImageTk, ImageEnhance

from .. import __app_name__, __version__
from ..assets.loader import get_asset_path
from ..config.manager import ConfigurationManager
from ..config.schema import Installation
from ..core.backup_index import BackupIndexEntry
from ..core.save_parser import (
    MoriaSaveParser, WorldWithVersions, CharacterWithVersions, SaveFileVersion
)
from ..logging_config import get_logger
from .config_dialog import ConfigDialog
from .styles import COLORS, FONTS, PADDING, WINDOW_SIZES
from .backup_mixin import BackupMixin
from .import_mixin import ImportMixin
from .materials_mixin import MaterialsMixin
from .mods_mixin import ModsMixin
from .restore_mixin import RestoreMixin
from .servers_mixin import ServersMixin
from .trade_mixin import TradeMixin

logger = get_logger("main_window")

# Try to import tkinterdnd2 for drag and drop support
try:
    import tkinterdnd2
    HAS_DND = True
except ImportError:
    HAS_DND = False


# pylint: disable=too-many-instance-attributes,too-many-public-methods
class MainWindow(
    ServersMixin, ModsMixin, BackupMixin, RestoreMixin,
    ImportMixin, TradeMixin, MaterialsMixin, ctk.CTk
):
    """Main application window — the central hub of MoriaManager.

    Inherits from 6 mixins that provide mode-specific functionality:
      - BackupMixin:  Backing up game saves (local + remote)
      - RestoreMixin: Restoring previously backed-up saves
      - ModsMixin:    Installing/managing mods in the Paks folder
      - ServersMixin: FTP/SFTP server connections and file operations
      - ImportMixin:  Importing archived save files from other sources
      - TradeMixin:   Tracking merchant trade orders

    Layout:
      +---+-------------------------------------+
      | T |  [Toolbar: Backup|Restore|Mods|...] |
      | A |  +------------+  +-----------+      |
      | B |  | Left Pane  |  | Right Pane|      |
      | S |  | (items)    |  | (versions)|      |
      |   |  +------------+  +-----------+      |
      +---+-------------------------------------+
      |  Status Bar                              |
      +------------------------------------------+

    The left tabs list installations (Steam/Epic/Custom) and connected
    servers. The two content panes change meaning based on the active mode.
    """

    # --- Initialization ---

    def __init__(
        self,
        config_manager: ConfigurationManager,
    ):
        super().__init__()

        self.config_manager = config_manager
        self.parser = MoriaSaveParser()

        # Data storage
        self.current_installation: Optional[Installation] = None
        self.current_view_type: str = "Worlds"  # "Worlds" or "Characters"
        self.current_mode: str = "backup"  # "backup", "restore", or "mods"
        self.worlds_data: list[WorldWithVersions] = []
        self.characters_data: list[CharacterWithVersions] = []
        self.selected_item: Optional[WorldWithVersions | CharacterWithVersions] = None
        self.selected_version: Optional[SaveFileVersion] = None
        self.version_rows: dict[str, ctk.CTkFrame] = {}  # Track version rows for highlighting

        # Restore mode data
        self.restore_entries: list[BackupIndexEntry] = []
        self.selected_restore_entry: Optional[BackupIndexEntry] = None
        self.restore_timestamps: list[Path] = []
        self.selected_restore_timestamp: Optional[Path] = None

        # Mods mode data
        self.mods_items: list[Path] = []  # Files and directories in Paks folder
        self.selected_mod_item: Optional[Path] = None
        self.available_mods_items: list[Path] = []  # Files and directories in backup/mods
        self.selected_available_mod: Optional[Path] = None
        # Track available mod rows for highlighting
        self.available_mod_rows: dict[str, ctk.CTkFrame] = {}
        # Internal game files to exclude from mods list
        self._excluded_game_files = {
            "global.ucas", "global.utoc",
            "Moria-WindowsNoEditor.pak", "Moria-WindowsNoEditor.ucas", "Moria-WindowsNoEditor.utoc",
            "Moria-WindowsServer.pak", "Moria-WindowsServer.ucas", "Moria-WindowsServer.utoc"
        }

        # Server list mode data
        self.server_password_visible = False
        self.server_tab_widgets: list = []
        self._server_save_timer = None

        # FTP/SFTP server connections
        # tracks state: "disconnected", "connecting",
        # "connected", "error"
        self.ftp_connections: dict[str, any] = {}  # server_name -> FTP object
        self.sftp_connections: dict[str, any] = {}  # server_name -> paramiko.SFTPClient
        self.sftp_transports: dict[str, any] = {}  # server_name -> paramiko.Transport
        self.server_connection_states: dict[str, str] = {}  # server_name -> state string
        # Currently selected server for backup operations
        self.current_server: Optional[dict] = None
        self._server_temp_save_path: Optional[Path] = None  # Temp dir for downloaded server saves
        self._server_temp_mods_path: Optional[Path] = None  # Temp dir for downloaded server mods

        # Background image references
        self.bg_image_original: Optional[Image.Image] = None
        self.bg_image_tk: Optional[ImageTk.PhotoImage] = None
        self.bg_canvas: Optional[tk.Canvas] = None
        self._overlay_rects: dict[str, int] = {}  # Track overlay rectangles on canvas

        # UI widget references (initialized in _create_ui)
        self._logo_image = None
        self.toolbar_backup_btn = None
        self.toolbar_restore_btn = None
        self.toolbar_mods_btn = None
        self.toolbar_servers_btn = None
        self.toolbar_trade_btn = None
        self.toolbar_materials_btn = None
        self.help_btn = None
        self.settings_btn = None
        self.tabs_frame = None
        self.tab_buttons_frame = None
        self.tab_buttons = []
        self.content_frame = None
        self.world_pane = None
        self.view_type_var = None
        self.view_type_dropdown = None
        self.mode_header_label = None
        self.items_header = None
        self.item_count_label = None
        self.installed_refresh_btn = None
        self.backup_all_btn = None
        self.backup_btn = None
        self.item_list_frame = None
        self.item_placeholder = None
        self.versions_pane = None
        self.versions_header = None
        self.versions_count_label = None
        self.available_mods_refresh_btn = None
        self.add_set_btn = None
        self.versions_list_frame = None
        self.versions_placeholder = None
        self.status_bar = None
        self.import_btn = None
        self.add_server_btn = None
        self.status_label = None

        # Window setup
        self.title(f"{__app_name__} v{__version__}")
        width, height = WINDOW_SIZES["main"]
        min_width, min_height = WINDOW_SIZES["min_main"]
        self.geometry(f"{width}x{height}")
        self.minsize(min_width, min_height)

        # Initialize drag and drop support
        self._dnd_enabled = False
        if HAS_DND:
            try:
                # tkinterdnd2 needs to initialize its Tcl library
                tkinterdnd2.TkinterDnD._require(self)
                self._dnd_enabled = True
            except (RuntimeError, OSError, tk.TclError) as e:
                logger.debug("tkdnd not available: %s", e)

        # Store overlay images to prevent garbage collection
        self._overlay_images = []

        self._create_ui()

        # Set app icon after UI is created to ensure window is fully ready
        self._set_app_icon()

        # Initialize mode UI (ensure backup mode is properly shown on startup)
        self._update_toolbar_button_states()
        self._update_pane_headers_for_mode()

        # Select first tab if available
        self._select_first_tab()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # --- Icon and Image Helpers ---

    def _set_app_icon(self):
        """Set the application icon on the main window title bar."""
        try:
            icon_path = get_asset_path("icons/app_icon.ico")
            logger.debug("Setting app icon from: %s (exists=%s)", icon_path, icon_path.exists())
            if icon_path.exists():
                icon_path_str = str(icon_path)
                # Set icon using wm_iconbitmap with default=True for better Windows support
                self.wm_iconbitmap(default=icon_path_str)
                self.iconbitmap(icon_path_str)
                # Also set it again after a delay to ensure it persists
                self.after(100, lambda: self._apply_icon_safe(icon_path_str))
                logger.debug("App icon set successfully")
        except (OSError, tk.TclError) as e:
            logger.debug("Could not set app icon: %s", e)

    def _apply_icon_safe(self, icon_path_str: str):
        """Apply icon after window is fully initialized."""
        try:
            if self.winfo_exists():
                self.iconbitmap(icon_path_str)
        except (OSError, tk.TclError):
            pass

    def _set_dialog_icon(self, dialog):
        """Set the application icon on a dialog window."""
        try:
            icon_path = get_asset_path("icons/app_icon.ico")
            if icon_path.exists():
                icon_path_str = str(icon_path)
                # Use after with delay to ensure window is fully initialized
                def apply_icon():
                    try:
                        if dialog.winfo_exists():
                            dialog.iconbitmap(icon_path_str)
                    except (OSError, tk.TclError):
                        pass
                dialog.after(200, apply_icon)
        except (OSError, tk.TclError) as e:
            logger.debug("Could not set dialog icon: %s", e)

    def _reset_scroll_if_few_items(
        self, scrollable_frame: ctk.CTkScrollableFrame,
        threshold: int = 10
    ):
        """Reset scroll position to top if there are few items in the frame.

        Args:
            scrollable_frame: The CTkScrollableFrame to reset
            threshold: Maximum number of items before keeping scroll position
        """
        try:
            item_count = len(scrollable_frame.winfo_children())
            if item_count < threshold:
                # Access the internal canvas and scroll to top
                if hasattr(scrollable_frame, '_parent_canvas'):
                    scrollable_frame._parent_canvas.yview_moveto(0)
        except (tk.TclError, AttributeError) as e:
            logger.debug("Could not reset scroll position: %s", e)

    # --- Background Image ---

    def _setup_background(self):
        """Set up the faded background image behind all UI panes."""
        try:
            # Try png first, then webp, then jpg
            bg_path = get_asset_path("background.png")
            if not bg_path.exists():
                bg_path = get_asset_path("background.webp")
            if not bg_path.exists():
                bg_path = get_asset_path("background.jpg")

            if bg_path.exists():
                # Load and darken/fade the image
                self.bg_image_original = Image.open(bg_path)

                # Darken the image slightly for contrast with UI elements
                enhancer = ImageEnhance.Brightness(self.bg_image_original)
                self.bg_image_original = enhancer.enhance(0.6)  # 60% brightness (brighter)

                # Create canvas for background - use black as fallback
                self.bg_canvas = tk.Canvas(self, highlightthickness=0, bg="#1a1a1a")
                self.bg_canvas.place(x=0, y=0, relwidth=1, relheight=1)

                # Initial background render (delayed to ensure window is ready)
                self.after(100, self._update_background)

                # Bind resize event
                self.bind("<Configure>", self._on_window_resize)
        except (OSError, IOError, ValueError) as e:
            logger.warning("Could not load background image: %s", e)

    def _update_background(self):
        """Update background image to fit window size."""
        if not self.bg_image_original or not self.bg_canvas:
            return

        # Get current window size
        width = self.winfo_width()
        height = self.winfo_height()

        if width < 10 or height < 10:  # Window not yet rendered
            return

        # Resize image to cover window (maintain aspect ratio, crop excess)
        img_ratio = self.bg_image_original.width / self.bg_image_original.height
        win_ratio = width / height

        if win_ratio > img_ratio:
            # Window is wider than image - fit width
            new_width = width
            new_height = int(width / img_ratio)
        else:
            # Window is taller than image - fit height
            new_height = height
            new_width = int(height * img_ratio)

        # Resize and crop to center
        resized = self.bg_image_original.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # Crop to window size (centered)
        left = (new_width - width) // 2
        top = (new_height - height) // 2
        cropped = resized.crop((left, top, left + width, top + height))

        # Create a composite image with semi-transparent overlays baked in
        # This is the only way to achieve true transparency in tkinter
        composite = cropped.convert('RGBA')

        # Draw semi-transparent overlays for UI panes
        self._draw_pane_overlays(composite, width, height)

        # Convert to PhotoImage and display
        self.bg_image_tk = ImageTk.PhotoImage(composite)
        self.bg_canvas.delete("all")
        self.bg_canvas.create_image(0, 0, anchor="nw", image=self.bg_image_tk)

        # Ensure canvas stays behind other widgets
        try:
            self.bg_canvas.tk.call('lower', self.bg_canvas._w)
        except tk.TclError as e:
            logger.debug("Could not lower canvas: %s", e)

    def _draw_pane_overlays(self, composite: Image.Image, width: int, height: int):
        """Draw semi-transparent overlays on the background for each pane area.

        Note: This is now only used for visual effect in the gaps between panes.
        The panes themselves use opaque dark colors for proper widget rendering.
        """
        # No overlays needed - background shows in gaps, panes are opaque

    def _on_window_resize(self, event):
        """Handle window resize to update background."""
        if event.widget == self:
            self._update_background()

    def _create_transparent_overlay(
        self, width: int, height: int,
        color: tuple = (0, 0, 0), alpha: int = 128
    ) -> ImageTk.PhotoImage:
        """Create a semi-transparent overlay image.

        Args:
            width: Width in pixels
            height: Height in pixels
            color: RGB tuple (default black)
            alpha: Transparency 0-255 (0=transparent, 255=opaque). Default 128 = 50%
        """
        overlay = Image.new('RGBA', (width, height), (*color, alpha))
        return ImageTk.PhotoImage(overlay)

    # --- UI Construction ---

    def _create_ui(self):
        """Create the main UI layout: toolbar, tabs, content panes, and status bar."""
        # Load and set up background image
        self._setup_background()

        # Top toolbar
        self._create_toolbar()

        # Main content area - transparent to show background
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.pack(
            fill="both", expand=True,
            padx=PADDING["medium"], pady=(0, PADDING["medium"])
        )

        # Configure grid: tabs on left, content on right
        self.main_container.grid_columnconfigure(0, weight=0, minsize=135)  # Tabs column
        self.main_container.grid_columnconfigure(1, weight=1)  # Content column
        self.main_container.grid_rowconfigure(0, weight=1)

        # Left side: Vertical tabs
        self._create_vertical_tabs()

        # Right side: Content area (will be populated when tab is selected)
        self._create_content_area()

        # Status bar
        self._create_status_bar()

    def _create_toolbar(self):
        """Create the top toolbar with semi-transparent dark appearance."""
        # Use a dark color with some transparency appearance
        toolbar = ctk.CTkFrame(self, height=50, fg_color=("#3d3d3d", "#1a1a1a"))
        toolbar.pack(fill="x", padx=PADDING["medium"], pady=PADDING["medium"])
        toolbar.pack_propagate(False)

        # Logo image before title
        logo_image = self._load_icon("icons/logo.png", size=(32, 32))
        if logo_image:
            logo_label = ctk.CTkLabel(toolbar, image=logo_image, text="")
            logo_label.pack(side="left", padx=(PADDING["medium"], 5), pady=PADDING["small"])
            # Keep reference to prevent garbage collection
            self._logo_image = logo_image

        title = ctk.CTkLabel(toolbar, text=__app_name__, font=FONTS["title"])
        pad_left = 0 if logo_image else PADDING["medium"]
        title.pack(
            side="left",
            padx=(pad_left, PADDING["medium"]),
            pady=PADDING["small"]
        )

        version = ctk.CTkLabel(
            toolbar, text=f"v{__version__}",
            font=FONTS["small"], text_color="gray"
        )
        version.pack(side="left", pady=PADDING["small"])

        # Main toolbar buttons (after title/version, before settings)
        toolbar_buttons_frame = ctk.CTkFrame(toolbar, fg_color="transparent")
        toolbar_buttons_frame.pack(side="left", padx=PADDING["large"])

        # Backup button (funnel with up arrow)
        backup_image = self._load_icon("icons/toolbar_backup.png", size=(24, 24))
        if backup_image:
            self.toolbar_backup_btn = ctk.CTkButton(
                toolbar_buttons_frame, image=backup_image, text="", width=40, height=40,
                fg_color="transparent", hover_color=("gray80", "gray30"),
                command=self._on_toolbar_backup,
            )
        else:
            # Fallback: up arrow symbol
            self.toolbar_backup_btn = ctk.CTkButton(
                toolbar_buttons_frame, text="⬆", width=40, height=40,
                font=("Segoe UI", 16), fg_color="transparent", hover_color=("gray80", "gray30"),
                command=self._on_toolbar_backup,
            )
        self.toolbar_backup_btn.pack(side="left", padx=2)
        self._create_tooltip(self.toolbar_backup_btn, "Backup")

        # Restore button (funnel with down arrow)
        restore_image = self._load_icon("icons/toolbar_restore.png", size=(24, 24))
        if restore_image:
            self.toolbar_restore_btn = ctk.CTkButton(
                toolbar_buttons_frame, image=restore_image, text="", width=40, height=40,
                fg_color="transparent", hover_color=("gray80", "gray30"),
                command=self._on_toolbar_restore,
            )
        else:
            # Fallback: down arrow symbol
            self.toolbar_restore_btn = ctk.CTkButton(
                toolbar_buttons_frame, text="⬇", width=40, height=40,
                font=("Segoe UI", 16), fg_color="transparent", hover_color=("gray80", "gray30"),
                command=self._on_toolbar_restore,
            )
        self.toolbar_restore_btn.pack(side="left", padx=2)
        self._create_tooltip(self.toolbar_restore_btn, "Restore")

        # Mods button (starburst)
        mods_image = self._load_icon("icons/toolbar_mods.png", size=(24, 24))
        if mods_image:
            self.toolbar_mods_btn = ctk.CTkButton(
                toolbar_buttons_frame, image=mods_image, text="", width=40, height=40,
                fg_color="transparent", hover_color=("gray80", "gray30"),
                command=self._on_toolbar_mods,
            )
        else:
            # Fallback: star/sparkle symbol
            self.toolbar_mods_btn = ctk.CTkButton(
                toolbar_buttons_frame, text="✦", width=40, height=40,
                font=("Segoe UI", 16), fg_color="transparent", hover_color=("gray80", "gray30"),
                command=self._on_toolbar_mods,
            )
        self.toolbar_mods_btn.pack(side="left", padx=2)
        self._create_tooltip(self.toolbar_mods_btn, "Mods")

        # Server List button (notebook with lines)
        servers_image = self._load_icon("icons/toolbar_servers.png", size=(24, 24))
        if servers_image:
            self.toolbar_servers_btn = ctk.CTkButton(
                toolbar_buttons_frame, image=servers_image, text="", width=40, height=40,
                fg_color="transparent", hover_color=("gray80", "gray30"),
                command=self._on_toolbar_servers,
            )
        else:
            # Fallback: notebook symbol
            self.toolbar_servers_btn = ctk.CTkButton(
                toolbar_buttons_frame, text="☰", width=40, height=40,
                font=("Segoe UI", 16), fg_color="transparent", hover_color=("gray80", "gray30"),
                command=self._on_toolbar_servers,
            )
        self.toolbar_servers_btn.pack(side="left", padx=2)
        self._create_tooltip(self.toolbar_servers_btn, "Server List")

        # Trade Manager button (handshake)
        trade_image = self._load_icon("icons/toolbar_trade.png", size=(24, 24))
        if trade_image:
            self.toolbar_trade_btn = ctk.CTkButton(
                toolbar_buttons_frame, image=trade_image, text="", width=40, height=40,
                fg_color="transparent", hover_color=("gray80", "gray30"),
                command=self._on_toolbar_trade,
            )
        else:
            # Fallback: handshake symbol
            self.toolbar_trade_btn = ctk.CTkButton(
                toolbar_buttons_frame, text="🤝", width=40, height=40,
                font=("Segoe UI Emoji", 16),
                fg_color="transparent",
                hover_color=("gray80", "gray30"),
                command=self._on_toolbar_trade,
            )
        self.toolbar_trade_btn.pack(side="left", padx=2)
        self._create_tooltip(self.toolbar_trade_btn, "Trade Manager")

        # Materials Calculator button (shopping bag)
        materials_image = self._load_icon("icons/toolbar_materials.png", size=(24, 24))
        if materials_image:
            self.toolbar_materials_btn = ctk.CTkButton(
                toolbar_buttons_frame, image=materials_image, text="", width=40, height=40,
                fg_color="transparent", hover_color=("gray80", "gray30"),
                command=self._on_toolbar_materials,
            )
        else:
            # Fallback: shopping bag symbol
            self.toolbar_materials_btn = ctk.CTkButton(
                toolbar_buttons_frame, text="🛒", width=40, height=40,
                font=("Segoe UI Emoji", 16),
                fg_color="transparent",
                hover_color=("gray80", "gray30"),
                command=self._on_toolbar_materials,
            )
        self.toolbar_materials_btn.pack(side="left", padx=2)
        self._create_tooltip(self.toolbar_materials_btn, "Materials Calculator")

        # Help icon button (about - on the right)
        help_image = self._load_icon("icons/help.png", size=(24, 24))
        if help_image:
            self.help_btn = ctk.CTkButton(
                toolbar, image=help_image, text="", width=40, height=40,
                fg_color="transparent", hover_color=("gray80", "gray30"),
                command=self._show_about_dialog,
            )
        else:
            # Fallback: question mark symbol
            self.help_btn = ctk.CTkButton(
                toolbar, text="?", width=40, height=40,
                font=("Segoe UI", 18), text_color="#5dade2",
                fg_color="transparent", hover_color=("gray80", "gray30"),
                command=self._show_about_dialog,
            )
        self.help_btn.pack(side="right", padx=(0, PADDING["small"]))
        self._create_tooltip(self.help_btn, "About")

        # Gear icon button (settings - on the right)
        gear_image = self._load_icon("icons/gear.png", size=(24, 24))
        if gear_image:
            self.settings_btn = ctk.CTkButton(
                toolbar, image=gear_image, text="", width=40, height=40,
                fg_color="transparent", hover_color=("gray80", "gray30"),
                command=self._open_settings,
            )
        else:
            # Fallback: gear symbol
            self.settings_btn = ctk.CTkButton(
                toolbar, text="⚙", width=40, height=40,
                font=("Segoe UI", 18), text_color="#5dade2",
                fg_color="transparent", hover_color=("gray80", "gray30"),
                command=self._open_settings,
            )
        self.settings_btn.pack(side="right", padx=(0, PADDING["small"]))
        self._create_tooltip(self.settings_btn, "Settings")

    def _create_vertical_tabs(self):
        """Create vertical tab buttons on the left side with semi-transparent dark appearance."""
        self.tabs_frame = ctk.CTkFrame(
            self.main_container, width=135,
            fg_color=("#3d3d3d", "#1a1a1a")
        )
        self.tabs_frame.grid(row=0, column=0, sticky="ns", padx=(0, PADDING["medium"]))
        self.tabs_frame.grid_propagate(False)

        # Header
        header = ctk.CTkLabel(self.tabs_frame, text="Installations", font=FONTS["heading"])
        header.pack(padx=PADDING["small"], pady=PADDING["medium"])

        # Tab buttons container
        self.tab_buttons_frame = ctk.CTkFrame(self.tabs_frame, fg_color="transparent")
        self.tab_buttons_frame.pack(fill="both", expand=True, padx=PADDING["small"])

        self.tab_buttons: dict[str, ctk.CTkButton] = {}
        self._refresh_tabs()

    def _refresh_tabs(self):
        """Refresh the vertical tab buttons based on enabled installations."""
        # Clear existing buttons
        for btn in self.tab_buttons.values():
            btn.destroy()
        self.tab_buttons.clear()

        # Clear server tab widgets if they exist
        for widget in self.server_tab_widgets:
            widget.destroy()
        self.server_tab_widgets = []

        # Create button for each enabled installation
        enabled = self.config_manager.config.get_enabled_installations()

        if not enabled:
            no_inst_label = ctk.CTkLabel(
                self.tab_buttons_frame,
                text="No installations\nconfigured.\n\nClick the gear\nicon to set up.",
                font=FONTS["small"],
                text_color="gray",
                justify="center"
            )
            no_inst_label.pack(pady=PADDING["large"])
            return

        for installation in enabled:
            btn = ctk.CTkButton(
                self.tab_buttons_frame,
                text=installation.display_name,
                font=FONTS["body"],
                anchor="w",
                fg_color="transparent",
                text_color=("gray10", "gray90"),
                hover_color=("gray80", "gray30"),
                height=40,
                command=lambda inst=installation: self._on_tab_selected(inst),
            )
            btn.pack(fill="x", pady=2)
            self.tab_buttons[installation.id.value] = btn

        # Load servers from ini and create server tabs
        servers = self._load_servers_from_ini()
        if servers:
            # Add separator line
            separator = ctk.CTkFrame(
                self.tab_buttons_frame, height=2,
                fg_color=("gray60", "gray40")
            )
            separator.pack(fill="x", pady=PADDING["medium"])
            self.server_tab_widgets.append(separator)

            # Create scrollable frame for servers if needed
            for server in servers:
                server_frame = ctk.CTkFrame(self.tab_buttons_frame, fg_color="transparent")
                server_frame.pack(fill="x", pady=2)
                self.server_tab_widgets.append(server_frame)

                # Determine button color based on connection state
                server_name = server["name"]
                conn_state = self.server_connection_states.get(server_name, "disconnected")
                if conn_state == "connected":
                    btn_fg_color = "#00AA00"  # Green
                    btn_text_color = "white"
                elif conn_state == "error":
                    btn_fg_color = "#c01c28"  # Red
                    btn_text_color = "white"
                else:  # disconnected or connecting
                    btn_fg_color = "#1a5fb4"  # Blue
                    btn_text_color = "white"

                # Server name button (no icons - use right-click for menu)
                server_btn = ctk.CTkButton(
                    server_frame,
                    text=server["name"],
                    font=FONTS["body"],
                    anchor="w",
                    fg_color=btn_fg_color,
                    text_color=btn_text_color,
                    hover_color=("gray80", "gray30"),
                    height=40,
                    command=lambda s=server: self._on_server_tab_selected(s),
                )
                server_btn.pack(side="left", fill="x", expand=True)

                # Bind right-click to show context menu
                server_btn.bind(
                    "<Button-3>",
                    lambda e, s=server:
                        self._show_server_context_menu(e, s)
                )

                # Store reference to button for highlighting
                self.tab_buttons[f"server_{server['name']}"] = server_btn

    def _create_content_area(self):
        """Create the right side content area with two panes."""
        self.content_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.content_frame.grid(row=0, column=1, sticky="nsew")

        # Configure for two panes side by side
        self.content_frame.grid_columnconfigure(0, weight=1)  # World list pane
        self.content_frame.grid_columnconfigure(1, weight=1)  # Versions pane
        self.content_frame.grid_rowconfigure(0, weight=1)

        # Left pane: World list
        self._create_world_list_pane()

        # Right pane: File versions
        self._create_versions_pane()

        # Server pane (hidden by default, shown in servers mode)
        self._create_server_pane()

        # Trade pane (hidden by default, shown in trade mode)
        self._create_trade_pane()

        # Materials pane (hidden by default, shown in materials mode)
        self._create_materials_pane()

    def _create_world_list_pane(self):
        """Create the left pane showing world/character names and filenames."""
        self.world_pane = ctk.CTkFrame(self.content_frame, fg_color=("#3d3d3d", "#1a1a1a"))
        self.world_pane.grid(row=0, column=0, sticky="nsew", padx=(0, PADDING["medium"]))

        # Header with dropdown
        header_frame = ctk.CTkFrame(self.world_pane, fg_color="transparent")
        header_frame.pack(fill="x", padx=PADDING["small"], pady=PADDING["small"])

        # Dropdown for Worlds/Characters
        self.view_type_var = ctk.StringVar(value="Worlds")
        self.view_type_dropdown = ctk.CTkOptionMenu(
            header_frame,
            values=["Worlds", "Characters"],
            variable=self.view_type_var,
            command=self._on_view_type_changed,
            width=120,
            height=28,
            font=FONTS["body"],
        )
        # Don't pack dropdown initially - controlled by _update_pane_headers_for_mode

        # Mode label for backup/restore modes (hidden by default, shown before dropdown)
        self.mode_header_label = ctk.CTkLabel(header_frame, text="Backup", font=FONTS["heading"])
        # Don't pack initially - only shown in backup/restore modes

        # Header label for mods mode (hidden by default)
        self.items_header = ctk.CTkLabel(header_frame, text="Installed Mods", font=FONTS["heading"])
        # Don't pack initially - only shown in mods mode

        self.item_count_label = ctk.CTkLabel(
            header_frame, text="(0)",
            font=FONTS["small"], text_color="gray"
        )
        # Don't pack initially - pack after header labels in _update_pane_headers_for_mode

        # Button frame for icons (right side) - order: Backup, Backup All, Refresh
        btn_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        btn_frame.pack(side="right")

        # Refresh button (rightmost) - command changes based on mode
        self.installed_refresh_btn = ctk.CTkButton(
            btn_frame, text="↻", width=28, height=28,
            font=FONTS["body"], command=self._on_installed_refresh
        )
        self.installed_refresh_btn.pack(side="right", padx=2)
        self._create_tooltip(self.installed_refresh_btn, "Refresh")

        # Backup All button (middle)
        backup_all_image = self._load_icon("icons/backup_all.png", size=(20, 20))
        if backup_all_image:
            self.backup_all_btn = ctk.CTkButton(
                btn_frame, image=backup_all_image, text="", width=28, height=28,
                fg_color="transparent", hover_color=("gray80", "gray30"),
                command=self._backup_all_items
            )
        else:
            self.backup_all_btn = ctk.CTkButton(
                btn_frame, text="All", width=40, height=28,
                font=FONTS["small"], command=self._backup_all_items
            )
        self.backup_all_btn.pack(side="right", padx=2)
        self._create_tooltip(self.backup_all_btn, "Backup All")

        # Backup button (leftmost)
        backup_image = self._load_icon("icons/backup.png", size=(18, 18))
        if backup_image:
            self.backup_btn = ctk.CTkButton(
                btn_frame, image=backup_image, text="", width=28, height=28,
                fg_color="transparent", hover_color=("gray80", "gray30"),
                command=self._backup_selected_item
            )
        else:
            self.backup_btn = ctk.CTkButton(
                btn_frame, text="Backup", width=60, height=28,
                font=FONTS["small"], command=self._backup_selected_item
            )
        self.backup_btn.pack(side="right", padx=2)
        self._create_tooltip(self.backup_btn, "Backup")

        # Scrollable list
        self.item_list_frame = ctk.CTkScrollableFrame(
            self.world_pane,
            fg_color=("#3d3d3d", "#1a1a1a")
        )
        self.item_list_frame.pack(
            fill="both", expand=True,
            padx=PADDING["small"], pady=(0, PADDING["small"])
        )

        # Placeholder
        self.item_placeholder = ctk.CTkLabel(
            self.item_list_frame,
            text="Select an installation\nfrom the left",
            font=FONTS["body"],
            text_color="gray",
            justify="center"
        )
        self.item_placeholder.pack(pady=PADDING["large"])

    def _create_versions_pane(self):
        """Create the right pane showing file versions for selected world."""
        self.versions_pane = ctk.CTkFrame(self.content_frame, fg_color=("#3d3d3d", "#1a1a1a"))
        self.versions_pane.grid(row=0, column=1, sticky="nsew")

        # Header
        header_frame = ctk.CTkFrame(self.versions_pane, fg_color="transparent")
        header_frame.pack(fill="x", padx=PADDING["small"], pady=PADDING["small"])

        self.versions_header = ctk.CTkLabel(
            header_frame, text="File Versions",
            font=FONTS["heading"]
        )
        self.versions_header.pack(side="left")

        self.versions_count_label = ctk.CTkLabel(
            header_frame, text="(0)",
            font=FONTS["small"], text_color="gray"
        )
        self.versions_count_label.pack(side="left", padx=(5, 0))

        # Refresh button for Available Mods (hidden by default, shown in mods mode)
        self.available_mods_refresh_btn = ctk.CTkButton(
            header_frame, text="↻", width=28, height=28,
            font=FONTS["body"], command=self._refresh_available_mods
        )
        # Don't pack initially - only shown in mods mode

        # Add Set button for Available Mods (hidden by default, shown in mods mode)
        self.add_set_btn = ctk.CTkButton(
            header_frame, text="Add Set", width=70, height=28,
            font=FONTS["small"], fg_color="#00AA00", hover_color="#008800",
            text_color="white", command=self._add_mod_set
        )
        # Don't pack initially - only shown in mods mode

        # Scrollable list
        self.versions_list_frame = ctk.CTkScrollableFrame(
            self.versions_pane,
            fg_color=("#3d3d3d", "#1a1a1a")
        )
        self.versions_list_frame.pack(
            fill="both", expand=True,
            padx=PADDING["small"], pady=(0, PADDING["small"])
        )

        # Placeholder
        self.versions_placeholder = ctk.CTkLabel(
            self.versions_list_frame,
            text="Select a world\nfrom the left",
            font=FONTS["body"],
            text_color="gray",
            justify="center"
        )
        self.versions_placeholder.pack(pady=PADDING["large"])

        # Set up drag and drop for Available Mods
        self._setup_dnd_for_available_mods()

    def _create_status_bar(self):
        """Create the bottom status bar with semi-transparent dark appearance."""
        self.status_bar = ctk.CTkFrame(self, height=30, fg_color=("#3d3d3d", "#1a1a1a"))
        self.status_bar.pack(fill="x", side="bottom")
        self.status_bar.pack_propagate(False)

        # Import button on the left
        import_image = self._load_icon("icons/import.png", size=(20, 20))
        if import_image:
            self.import_btn = ctk.CTkButton(
                self.status_bar, image=import_image,
                text="Import Old Backups", width=140, height=24,
                font=FONTS["small"], fg_color="transparent", hover_color=("gray80", "gray30"),
                command=self._show_import_dialog,
            )
        else:
            self.import_btn = ctk.CTkButton(
                self.status_bar, text="Import Old Backups", width=140, height=24,
                font=FONTS["small"], fg_color="transparent", hover_color=("gray80", "gray30"),
                command=self._show_import_dialog,
            )
        self.import_btn.pack(side="left", padx=PADDING["small"], pady=2)
        self._create_tooltip(self.import_btn, "Import archived save files")

        # Add Server button
        self.add_server_btn = ctk.CTkButton(
            self.status_bar, text="Add Server", width=100, height=24,
            font=FONTS["small"], fg_color="transparent", hover_color=("gray80", "gray30"),
            command=self._show_add_server_dialog,
        )
        self.add_server_btn.pack(side="left", padx=PADDING["small"], pady=2)
        self._create_tooltip(self.add_server_btn, "Add a remote server installation")

        self.status_label = ctk.CTkLabel(
            self.status_bar, text="Ready", font=FONTS["small"],
            text_color=("#cccccc", "#999999"))
        self.status_label.pack(side="left", padx=PADDING["medium"], pady=PADDING["small"])

    # --- Tab Selection and Mode Switching ---

    def _select_first_tab(self):
        """Select the first available tab on startup."""
        enabled = self.config_manager.config.get_enabled_installations()
        if enabled:
            self._on_tab_selected(enabled[0])

    def _on_tab_selected(self, installation: Installation):
        """Handle tab selection."""
        # Clean up server cache when switching away from a server
        if self.current_server:
            self._cleanup_server_cache()

        self.current_installation = installation
        self.current_server = None  # Clear server when local installation selected

        # Update button states (highlight selected)
        for inst_id, btn in self.tab_buttons.items():
            if inst_id == installation.id.value:
                btn.configure(fg_color=("gray75", "gray35"))
            else:
                btn.configure(fg_color="transparent")

        # Load items based on current mode
        if self.current_mode == "backup":
            self._refresh_item_list()
            self.selected_item = None
            self._refresh_versions_list()
        elif self.current_mode == "restore":
            self._refresh_restore_list()
            self.selected_restore_entry = None
            self._refresh_restore_timestamps()
        elif self.current_mode == "mods":
            self._refresh_mods_list()
        elif self.current_mode == "servers":
            self._refresh_server_list()

        self._set_status(f"Loaded {installation.display_name}")

    def _on_view_type_changed(self, choice: str):
        """Handle dropdown change between Worlds and Characters."""
        self.current_view_type = choice
        self.selected_item = None
        self.selected_restore_entry = None

        if self.current_mode == "backup":
            self._refresh_item_list()
            self._refresh_versions_list()
        else:
            self._refresh_restore_list()
            self._refresh_restore_timestamps()

    def _on_installed_refresh(self):
        """Handle refresh button click - calls appropriate refresh based on mode."""
        if self.current_mode == "backup":
            self._refresh_item_list()
        elif self.current_mode == "restore":
            self._refresh_restore_list()
        elif self.current_mode == "mods":
            self._refresh_mods_list()

    # --- Tooltip and Utility Widgets ---

    def _create_tooltip(self, widget, text: str):
        """Create a hover tooltip for a widget (displays above cursor after 200ms delay)."""
        tooltip = None
        after_id = None
        cursor_pos = {"x": 0, "y": 0}

        def show_tooltip(event):
            nonlocal tooltip, after_id
            # Store cursor position at hover time
            cursor_pos["x"] = event.x_root
            cursor_pos["y"] = event.y_root
            # Cancel any pending show
            if after_id:
                widget.after_cancel(after_id)
                after_id = None
            # Hide any existing tooltip first
            hide_tooltip(None)

            # Small delay before showing tooltip
            def create_tooltip():
                nonlocal tooltip
                try:
                    if not widget.winfo_exists():
                        return
                    # Position tooltip above the cursor (offset by 25 pixels up)
                    x = cursor_pos["x"] + 10  # Slightly to the right of cursor
                    y = cursor_pos["y"] - 30  # Above the cursor

                    tooltip = ctk.CTkToplevel(widget)
                    tooltip.wm_overrideredirect(True)
                    tooltip.wm_geometry(f"+{x}+{y}")
                    tooltip.wm_attributes("-topmost", True)

                    label = ctk.CTkLabel(
                        tooltip, text=text,
                        font=FONTS["small"],
                        fg_color=("gray90", "gray20"),
                        corner_radius=4,
                        padx=8, pady=4
                    )
                    label.pack()

                    # Auto-hide after 3 seconds as failsafe
                    tooltip.after(3000, lambda: hide_tooltip(None))
                except (tk.TclError, RuntimeError):
                    pass  # Widget was destroyed

            after_id = widget.after(200, create_tooltip)

        def hide_tooltip(_event):
            nonlocal tooltip, after_id
            # Cancel any pending show
            if after_id:
                try:
                    widget.after_cancel(after_id)
                except (tk.TclError, RuntimeError):
                    pass
                after_id = None
            # Destroy tooltip if it exists
            if tooltip:
                try:
                    tooltip.destroy()
                except (tk.TclError, RuntimeError):
                    pass  # Already destroyed
                tooltip = None

        widget.bind("<Enter>", show_tooltip)
        widget.bind("<Leave>", hide_tooltip)
        widget.bind("<Button-1>", hide_tooltip)  # Hide on click
        widget.bind("<Destroy>", hide_tooltip)  # Cleanup when widget destroyed

    def _load_icon(
        self, relative_path: str,
        size: tuple[int, int] = (24, 24)
    ) -> Optional[ctk.CTkImage]:
        """Load a PNG icon from the assets directory, returning None on failure."""
        try:
            icon_path = get_asset_path(relative_path)
            if icon_path.exists():
                image = Image.open(icon_path)
                return ctk.CTkImage(light_image=image, dark_image=image, size=size)
        except (OSError, IOError, ValueError) as e:
            logger.debug("Could not load icon %s: %s", relative_path, e)
        return None

    # --- Settings and Status ---

    def _open_settings(self):
        """Open the settings dialog."""
        dialog = ConfigDialog(self, self.config_manager, first_run=False)
        self.wait_window(dialog)

        if dialog.config_changed:
            self._refresh_ui()

    def _refresh_ui(self):
        """Refresh the entire UI after configuration changes."""
        self._refresh_tabs()
        self._select_first_tab()
        self._set_status("Configuration updated")

    def _set_status(self, message: str):
        """Update the status bar message."""
        self.status_label.configure(text=message)

    def _show_two_pane_view(self):
        """Show the standard two-pane view and hide server/trade/materials panes."""
        # Hide special panes
        self.server_pane.grid_forget()
        self.trade_pane.grid_forget()
        self.materials_pane.grid_forget()

        # Restore left tabs if hidden
        self.tabs_frame.grid(row=0, column=0, sticky="ns", padx=(0, PADDING["medium"]))

        # Restore content frame to normal position (column 1, not spanning)
        self.content_frame.grid(row=0, column=1, sticky="nsew")

        # Show the two panes
        self.world_pane.grid(row=0, column=0, sticky="nsew", padx=(0, PADDING["medium"]))
        self.versions_pane.grid(row=0, column=1, sticky="nsew")

    def _on_toolbar_backup(self):
        """Handle toolbar Backup button click.

        Switches to backup mode - shows game saves that can be backed up.
        """
        if self.current_mode == "backup":
            # Already in backup mode, just refresh
            self._refresh_item_list()
            self._set_status("Backup view refreshed")
            return

        self.current_mode = "backup"
        self._update_toolbar_button_states()
        self._update_pane_headers_for_mode()
        self._show_two_pane_view()
        self._refresh_item_list()
        self._refresh_versions_list()
        self._set_status("Switched to Backup mode")

    def _on_toolbar_restore(self):
        """Handle toolbar Restore button click.

        Switches to restore mode - shows backups that can be restored to the game.
        """
        if self.current_mode == "restore":
            # Already in restore mode, just refresh
            self._refresh_restore_list()
            self._set_status("Restore view refreshed")
            return

        self.current_mode = "restore"
        self._update_toolbar_button_states()
        self._update_pane_headers_for_mode()
        self._show_two_pane_view()
        self._refresh_restore_list()
        self._refresh_restore_timestamps()
        self._set_status("Switched to Restore mode")

    def _update_toolbar_button_states(self):
        """Update toolbar button visual states to show current mode."""
        # Reset all buttons to transparent
        self.toolbar_backup_btn.configure(fg_color="transparent")
        self.toolbar_restore_btn.configure(fg_color="transparent")
        self.toolbar_mods_btn.configure(fg_color="transparent")
        self.toolbar_servers_btn.configure(fg_color="transparent")
        self.toolbar_trade_btn.configure(fg_color="transparent")
        self.toolbar_materials_btn.configure(fg_color="transparent")

        # Highlight active mode button
        if self.current_mode == "backup":
            self.toolbar_backup_btn.configure(fg_color=("gray75", "gray35"))
        elif self.current_mode == "restore":
            self.toolbar_restore_btn.configure(fg_color=("gray75", "gray35"))
        elif self.current_mode == "mods":
            self.toolbar_mods_btn.configure(fg_color=("gray75", "gray35"))
        elif self.current_mode == "servers":
            self.toolbar_servers_btn.configure(fg_color=("gray75", "gray35"))
        elif self.current_mode == "trade":
            self.toolbar_trade_btn.configure(fg_color=("gray75", "gray35"))
        elif self.current_mode == "materials":
            self.toolbar_materials_btn.configure(fg_color=("gray75", "gray35"))

    def _update_pane_headers_for_mode(self):
        """Update pane headers and buttons based on current mode."""
        # Hide/show backup buttons based on mode
        if self.current_mode == "backup":
            self.backup_btn.pack(side="right", padx=2)
            self.backup_all_btn.pack(side="right", padx=2)
            # Show mode label + dropdown for Worlds/Characters, hide mods header
            self.items_header.pack_forget()
            self.item_count_label.pack_forget()
            self.mode_header_label.configure(text="Backup")
            self.mode_header_label.pack(side="left")
            self.item_count_label.pack(side="left", padx=(5, 0))
            self.view_type_dropdown.pack(side="left", padx=(40, 0))  # 5 char spacing (~40px)
            # Update right pane header
            self.versions_header.configure(text="File Versions")
            # Hide available mods refresh button and Add Set button
            self.available_mods_refresh_btn.pack_forget()
            self.add_set_btn.pack_forget()
        elif self.current_mode == "restore":
            self.backup_btn.pack_forget()
            self.backup_all_btn.pack_forget()
            # Show mode label + dropdown for Worlds/Characters, hide mods header
            self.items_header.pack_forget()
            self.item_count_label.pack_forget()
            self.mode_header_label.configure(text="Restore")
            self.mode_header_label.pack(side="left")
            self.item_count_label.pack(side="left", padx=(5, 0))
            self.view_type_dropdown.pack(side="left", padx=(40, 0))  # 5 char spacing (~40px)
            # Update right pane header
            self.versions_header.configure(text="Backup Versions")
            # Hide available mods refresh button and Add Set button
            self.available_mods_refresh_btn.pack_forget()
            self.add_set_btn.pack_forget()
        elif self.current_mode == "mods":
            self.backup_btn.pack_forget()
            self.backup_all_btn.pack_forget()
            # Hide dropdown and mode label, show mods header
            self.view_type_dropdown.pack_forget()
            self.mode_header_label.pack_forget()
            self.item_count_label.pack_forget()
            self.items_header.configure(text="Installed Mods")
            self.items_header.pack(side="left")
            self.item_count_label.pack(side="left", padx=(5, 0))
            # Update right pane header
            self.versions_header.configure(text="Available Mods")
            # Show available mods refresh button and Add Set button
            # Pack refresh first (far right), then Add Set (centered between header and refresh)
            self.available_mods_refresh_btn.pack(side="right", padx=2)
            self._create_tooltip(self.available_mods_refresh_btn, "Refresh Available Mods")
            self.add_set_btn.pack(side="right", padx=2)
            self._create_tooltip(self.add_set_btn, "Create a new mod set folder")

    # --- Modal Dialogs ---

    def _show_info_dialog(self, title: str, message: str):
        """Show a themed information dialog with OK button only.

        Args:
            title: Dialog title
            message: Message to display
        """
        dialog = ctk.CTkToplevel(self)
        dialog.title(title)
        dialog.geometry("400x180")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        self._set_dialog_icon(dialog)

        # Center on parent
        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 400) // 2
        y = self.winfo_y() + (self.winfo_height() - 180) // 2
        dialog.geometry(f"+{x}+{y}")

        # Container
        container = ctk.CTkFrame(dialog)
        container.pack(fill="both", expand=True, padx=PADDING["medium"], pady=PADDING["medium"])

        # Info icon and title row
        title_frame = ctk.CTkFrame(container, fg_color="transparent")
        title_frame.pack(fill="x", pady=(0, PADDING["small"]))

        title_label = ctk.CTkLabel(
            title_frame,
            text="Information",
            font=FONTS["heading"],
            text_color=COLORS["primary"]
        )
        title_label.pack(anchor="w")

        # Message
        message_label = ctk.CTkLabel(
            container,
            text=message,
            font=FONTS["body"],
            wraplength=350,
            justify="left"
        )
        message_label.pack(fill="x", expand=True, pady=PADDING["small"])

        # OK button
        button_frame = ctk.CTkFrame(container, fg_color="transparent")
        button_frame.pack(fill="x", pady=(PADDING["small"], 0))

        ok_btn = ctk.CTkButton(
            button_frame,
            text="OK",
            width=100,
            command=dialog.destroy
        )
        ok_btn.pack(side="right")

        # Handle window close
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)

        # Wait for dialog to close
        dialog.wait_window()

    def _show_about_dialog(self):
        """Show the About dialog with version and compatibility information."""
        from .about_dialog import show_about_dialog
        show_about_dialog(self)

    def _show_overwrite_skip_dialog(self, title: str, message: str) -> str:
        """Show a themed dialog with Overwrite and Skip buttons.

        Args:
            title: Dialog title
            message: Message to display

        Returns:
            "overwrite" if Overwrite was clicked, "skip" if Skip was clicked or dialog closed
        """
        result = {"choice": "skip"}  # Default to skip

        dialog = ctk.CTkToplevel(self)
        dialog.title(title)
        dialog.geometry("400x180")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        self._set_dialog_icon(dialog)

        # Center on parent
        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 400) // 2
        y = self.winfo_y() + (self.winfo_height() - 180) // 2
        dialog.geometry(f"+{x}+{y}")

        # Container
        container = ctk.CTkFrame(dialog)
        container.pack(fill="both", expand=True, padx=PADDING["medium"], pady=PADDING["medium"])

        # Info icon and title row
        title_frame = ctk.CTkFrame(container, fg_color="transparent")
        title_frame.pack(fill="x", pady=(0, PADDING["small"]))

        title_label = ctk.CTkLabel(
            title_frame,
            text="Already Installed",
            font=FONTS["heading"],
            text_color=COLORS["warning"]
        )
        title_label.pack(anchor="w")

        # Message
        message_label = ctk.CTkLabel(
            container,
            text=message,
            font=FONTS["body"],
            wraplength=350,
            justify="left"
        )
        message_label.pack(fill="x", expand=True, pady=PADDING["small"])

        # Button frame
        button_frame = ctk.CTkFrame(container, fg_color="transparent")
        button_frame.pack(fill="x", pady=(PADDING["small"], 0))

        def on_overwrite():
            result["choice"] = "overwrite"
            dialog.destroy()

        def on_skip():
            result["choice"] = "skip"
            dialog.destroy()

        # Overwrite button (left side)
        overwrite_btn = ctk.CTkButton(
            button_frame,
            text="Overwrite",
            width=100,
            fg_color=COLORS["warning"],
            hover_color="#cc9900",
            command=on_overwrite
        )
        overwrite_btn.pack(side="left")

        # Skip button (right side, default focus)
        skip_btn = ctk.CTkButton(
            button_frame,
            text="Skip",
            width=100,
            command=on_skip
        )
        skip_btn.pack(side="right")
        skip_btn.focus_set()  # Set as default selection

        # Handle window close as Skip
        dialog.protocol("WM_DELETE_WINDOW", on_skip)

        # Bind Enter key to Skip (default action)
        dialog.bind("<Return>", lambda e: on_skip())

        # Wait for dialog to close
        dialog.wait_window()

        return result["choice"]

    def _on_toolbar_mods(self):
        """Handle toolbar Mods button click.

        Opens a mod management interface showing Paks folder contents.
        """
        if self.current_mode == "mods":
            # Already in mods mode, just refresh
            self._refresh_mods_list()
            self._set_status("Mods view refreshed")
            return

        self.current_mode = "mods"
        self._update_toolbar_button_states()
        self._update_pane_headers_for_mode()
        self._show_two_pane_view()
        self._refresh_mods_list()
        self._set_status("Switched to Mods mode")

    def _on_toolbar_servers(self):
        """Handle toolbar Server List button click.

        Opens a server list management interface.
        """
        if self.current_mode == "servers":
            # Already in servers mode
            return

        self.current_mode = "servers"
        self._update_toolbar_button_states()
        self._update_pane_headers_for_mode()

        # Hide the two-pane view and trade/materials pane, show server pane
        self.world_pane.grid_forget()
        self.versions_pane.grid_forget()
        self.trade_pane.grid_forget()
        self.materials_pane.grid_forget()

        # Restore left tabs if hidden (from trade mode)
        self.tabs_frame.grid(row=0, column=0, sticky="ns", padx=(0, PADDING["medium"]))

        # Restore content frame to normal position
        self.content_frame.grid(row=0, column=1, sticky="nsew")

        self.server_pane.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=PADDING["medium"])

        # Load server list for current installation
        if self.current_installation:
            install_id = self.current_installation.id.value
            if install_id not in self.server_entries_by_install:
                self._load_server_list(install_id)
            self._rebuild_server_list_current()

        self._set_status("Switched to Server List mode")

    def _on_toolbar_trade(self):
        """Handle toolbar Trade Manager button click.

        Opens the trade manager interface.
        """
        if self.current_mode == "trade":
            # Already in trade mode
            return

        self.current_mode = "trade"
        self._update_toolbar_button_states()

        # Lazy initialize trade UI on first use
        if not self.trade_initialized:
            self._initialize_trade_ui()

        # Reset expanded state based on checked orders
        self._reset_trade_expanded_state()

        # Hide the left tabs
        self.tabs_frame.grid_forget()

        # Hide all other panes
        self.world_pane.grid_forget()
        self.versions_pane.grid_forget()
        self.server_pane.grid_forget()
        self.materials_pane.grid_forget()

        # Reconfigure content frame to span full width (no tabs column)
        self.content_frame.grid(row=0, column=0, columnspan=2, sticky="nsew")

        # Show trade pane spanning both columns
        self.trade_pane.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=PADDING["medium"])

        self._set_status("Switched to Trade Manager")

    def _on_toolbar_materials(self):
        """Handle toolbar Materials Calculator button click.

        Opens the materials calculator interface.
        """
        if self.current_mode == "materials":
            # Already in materials mode
            return

        self.current_mode = "materials"
        self._update_toolbar_button_states()

        # Lazy initialize materials UI on first use
        if not self.materials_initialized:
            self._initialize_materials_ui()

        # Hide the left tabs
        self.tabs_frame.grid_forget()

        # Hide all other panes
        self.world_pane.grid_forget()
        self.versions_pane.grid_forget()
        self.server_pane.grid_forget()
        self.trade_pane.grid_forget()

        # Reconfigure content frame to span full width (no tabs column)
        self.content_frame.grid(row=0, column=0, columnspan=2, sticky="nsew")

        # Show materials pane spanning both columns
        self.materials_pane.grid(
            row=0, column=0, columnspan=2, sticky="nsew", padx=PADDING["medium"]
        )

        self._set_status("Switched to Materials Calculator")

    def _show_confirm_dialog(self, title: str, message: str) -> bool:
        """Show a themed confirmation dialog.

        Args:
            title: Dialog title
            message: Message to display

        Returns:
            True if user clicked Yes, False otherwise
        """
        result = [False]  # Use list to allow modification in nested function

        dialog = ctk.CTkToplevel(self)
        dialog.title(title)
        dialog.geometry("400x200")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        self._set_dialog_icon(dialog)

        # Center on parent
        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 400) // 2
        y = self.winfo_y() + (self.winfo_height() - 200) // 2
        dialog.geometry(f"+{x}+{y}")

        # Container
        container = ctk.CTkFrame(dialog)
        container.pack(fill="both", expand=True, padx=PADDING["medium"], pady=PADDING["medium"])

        # Warning icon and title row
        title_frame = ctk.CTkFrame(container, fg_color="transparent")
        title_frame.pack(fill="x", pady=(0, PADDING["small"]))

        title_label = ctk.CTkLabel(
            title_frame,
            text="Warning",
            font=FONTS["heading"],
            text_color=COLORS["warning"]
        )
        title_label.pack(anchor="w")

        # Message
        message_label = ctk.CTkLabel(
            container,
            text=message,
            font=FONTS["body"],
            wraplength=350,
            justify="left"
        )
        message_label.pack(fill="x", expand=True, pady=PADDING["small"])

        # Buttons
        button_frame = ctk.CTkFrame(container, fg_color="transparent")
        button_frame.pack(fill="x", pady=(PADDING["small"], 0))

        def on_yes():
            result[0] = True
            dialog.destroy()

        def on_no():
            result[0] = False
            dialog.destroy()

        no_btn = ctk.CTkButton(
            button_frame,
            text="No",
            width=100,
            fg_color="transparent",
            border_width=1,
            text_color=("gray10", "gray90"),
            command=on_no
        )
        no_btn.pack(side="left", padx=(0, PADDING["small"]))

        yes_btn = ctk.CTkButton(
            button_frame,
            text="Yes",
            width=100,
            fg_color=COLORS["warning"],
            hover_color="#d4a106",
            text_color="black",
            command=on_yes
        )
        yes_btn.pack(side="right")

        # Handle window close
        dialog.protocol("WM_DELETE_WINDOW", on_no)

        # Wait for dialog to close
        dialog.wait_window()

        return result[0]

    def _show_delete_confirm_dialog(self, item_name: str, item_type: str = "world") -> bool:
        """Show a delete confirmation dialog with red Cancel and green Yes buttons.

        Args:
            item_name: Name of the item to delete
            item_type: Type of item ("world", "character", "mod", "backup", etc.)

        Returns:
            True if user clicked Yes, False otherwise
        """
        result = [False]

        dialog = ctk.CTkToplevel(self)
        dialog.title("Confirm Delete")
        dialog.geometry("450x230")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        self._set_dialog_icon(dialog)

        # Center on parent
        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 450) // 2
        y = self.winfo_y() + (self.winfo_height() - 230) // 2
        dialog.geometry(f"+{x}+{y}")

        # Container
        container = ctk.CTkFrame(dialog)
        container.pack(fill="both", expand=True, padx=PADDING["medium"], pady=PADDING["medium"])

        # Warning title - capitalize item type for display
        title_text = f"Delete {item_type.title()}"
        title_label = ctk.CTkLabel(
            container,
            text=title_text,
            font=FONTS["heading"],
            text_color=COLORS["danger"]
        )
        title_label.pack(anchor="w", pady=(0, PADDING["small"]))

        # Message
        message_label = ctk.CTkLabel(
            container,
            text=(
                f"Are you sure you want to delete "
                f"'{item_name}'?\n\nThis will delete ALL "
                f"files for this {item_type} and cannot "
                "be undone."),
            font=FONTS["body"],
            wraplength=400,
            justify="left"
        )
        message_label.pack(fill="x", expand=True, pady=PADDING["small"])

        # Buttons
        button_frame = ctk.CTkFrame(container, fg_color="transparent")
        button_frame.pack(fill="x", pady=(PADDING["small"], 0))

        def on_yes():
            result[0] = True
            dialog.destroy()

        def on_cancel():
            result[0] = False
            dialog.destroy()

        # Red Cancel button on the left
        cancel_btn = ctk.CTkButton(
            button_frame,
            text="Cancel",
            width=120,
            fg_color=COLORS["danger"],
            hover_color=COLORS["danger_hover"],
            text_color="white",
            command=on_cancel
        )
        cancel_btn.pack(side="left")

        # Green Yes button on the right
        yes_btn = ctk.CTkButton(
            button_frame,
            text="Yes",
            width=120,
            fg_color=COLORS["success"],
            hover_color=COLORS["success_hover"],
            text_color="white",
            command=on_yes
        )
        yes_btn.pack(side="right")

        # Handle window close
        dialog.protocol("WM_DELETE_WINDOW", on_cancel)

        # Wait for dialog to close
        dialog.wait_window()

        return result[0]


    # --- Shutdown ---

    def _on_close(self):
        """Handle window close — cleanly close all FTP/SFTP connections before exit."""
        # Close all FTP connections
        for server_name, ftp in list(self.ftp_connections.items()):
            try:
                ftp.quit()
                logger.debug("Closed FTP connection to %s", server_name)
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.debug("Error closing FTP connection to %s: %s", server_name, e)
        self.ftp_connections.clear()

        # Close all SFTP connections
        for server_name, sftp in list(self.sftp_connections.items()):
            try:
                sftp.close()
                logger.debug("Closed SFTP connection to %s", server_name)
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.debug("Error closing SFTP connection to %s: %s", server_name, e)
        self.sftp_connections.clear()

        # Close all SFTP transports
        for server_name, transport in list(self.sftp_transports.items()):
            try:
                transport.close()
                logger.debug("Closed SFTP transport to %s", server_name)
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.debug("Error closing SFTP transport to %s: %s", server_name, e)
        self.sftp_transports.clear()

        self.server_connection_states.clear()

        self.destroy()
