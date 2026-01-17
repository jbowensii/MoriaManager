"""Main application window with vertical tabs and split panes."""

from typing import Optional
import tkinter as tk

import customtkinter as ctk
from PIL import Image, ImageTk, ImageEnhance, ImageDraw

from ..logging_config import get_logger

logger = get_logger("main_window")

# Try to import tkinterdnd2 for drag and drop support
try:
    import tkinterdnd2
    HAS_DND = True
except ImportError:
    HAS_DND = False

from .. import __app_name__, __version__
from ..assets.loader import get_asset_path
from ..config.manager import ConfigurationManager
from ..config.schema import Installation
# from ..core.backup_service import BackupService  # Not currently used
from ..core.backup_index import BackupIndexManager, BackupIndexEntry
from ..core.save_parser import (
    MoriaSaveParser, WorldWithVersions, CharacterWithVersions, SaveFileVersion
)
from ..config.paths import GamePaths
from pathlib import Path
from datetime import datetime
from .config_dialog import ConfigDialog
from .styles import COLORS, FONTS, PADDING, WINDOW_SIZES


class MainWindow(ctk.CTk):
    """Main application window with vertical tabs and split panes.

    Layout:
    - Left side: Vertical tabs for Steam/Epic/Custom
    - Right side (when tab selected):
      - Left pane: List of worlds (name + filename)
      - Right pane: File versions for selected world
    """

    def __init__(
        self,
        config_manager: ConfigurationManager,
        # backup_service: BackupService,  # Not currently used
    ):
        super().__init__()

        self.config_manager = config_manager
        # self.backup_service = backup_service  # Not currently used
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
        self.available_mod_rows: dict[str, ctk.CTkFrame] = {}  # Track available mod rows for highlighting
        # Internal game files to exclude from mods list
        self._excluded_game_files = {
            "global.ucas", "global.utoc",
            "Moria-WindowsNoEditor.pak", "Moria-WindowsNoEditor.ucas", "Moria-WindowsNoEditor.utoc"
        }

        # Server list mode data
        self.server_password_visible = False

        # Background image references
        self.bg_image_original: Optional[Image.Image] = None
        self.bg_image_tk: Optional[ImageTk.PhotoImage] = None
        self.bg_canvas: Optional[tk.Canvas] = None
        self._overlay_rects: dict[str, int] = {}  # Track overlay rectangles on canvas

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
                tkdnd_path = tkinterdnd2.TkinterDnD._require(self)
                self._dnd_enabled = True
            except Exception as e:
                logger.debug(f"tkdnd not available: {e}")

        self._set_app_icon()

        # Store overlay images to prevent garbage collection
        self._overlay_images = []

        self._create_ui()

        # Initialize mode UI (ensure backup mode is properly shown on startup)
        self._update_toolbar_button_states()
        self._update_pane_headers_for_mode()

        # Select first tab if available
        self._select_first_tab()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _set_app_icon(self):
        try:
            icon_path = get_asset_path("icons/app_icon.ico")
            if icon_path.exists():
                self.iconbitmap(str(icon_path))
        except Exception as e:
            logger.debug(f"Could not set app icon: {e}")

    def _setup_background(self):
        """Set up the faded background image."""
        try:
            # Try webp first, then jpg
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
        except Exception as e:
            logger.warning(f"Could not load background image: {e}")

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
        except Exception as e:
            logger.debug(f"Could not lower canvas: {e}")

    def _draw_pane_overlays(self, composite: Image.Image, width: int, height: int):
        """Draw semi-transparent overlays on the background for each pane area.

        Note: This is now only used for visual effect in the gaps between panes.
        The panes themselves use opaque dark colors for proper widget rendering.
        """
        # No overlays needed - background shows in gaps, panes are opaque
        pass

    def _on_window_resize(self, event):
        """Handle window resize to update background."""
        if event.widget == self:
            self._update_background()

    def _create_transparent_overlay(self, width: int, height: int, color: tuple = (0, 0, 0), alpha: int = 128) -> ImageTk.PhotoImage:
        """Create a semi-transparent overlay image.

        Args:
            width: Width in pixels
            height: Height in pixels
            color: RGB tuple (default black)
            alpha: Transparency 0-255 (0=transparent, 255=opaque). Default 128 = 50%
        """
        overlay = Image.new('RGBA', (width, height), (*color, alpha))
        return ImageTk.PhotoImage(overlay)

    def _create_ui(self):
        """Create the main UI layout with background image."""
        # Load and set up background image
        self._setup_background()

        # Top toolbar
        self._create_toolbar()

        # Main content area - transparent to show background
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True, padx=PADDING["medium"], pady=(0, PADDING["medium"]))

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

        title = ctk.CTkLabel(toolbar, text=__app_name__, font=FONTS["title"])
        title.pack(side="left", padx=PADDING["medium"], pady=PADDING["small"])

        version = ctk.CTkLabel(toolbar, text=f"v{__version__}", font=FONTS["small"], text_color="gray")
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
                font=("Segoe UI Emoji", 16), fg_color="transparent", hover_color=("gray80", "gray30"),
                command=self._on_toolbar_trade,
            )
        self.toolbar_trade_btn.pack(side="left", padx=2)
        self._create_tooltip(self.toolbar_trade_btn, "Trade Manager")

        # Gear icon button (settings - on the right, light blue)
        gear_image = self._load_icon("icons/gear.png", size=(24, 24))
        if gear_image:
            self.settings_btn = ctk.CTkButton(
                toolbar, image=gear_image, text="", width=40, height=40,
                fg_color="transparent", hover_color=("gray80", "gray30"),
                command=self._open_settings,
            )
        else:
            # Fallback: gear symbol with light blue color
            self.settings_btn = ctk.CTkButton(
                toolbar, text="⚙", width=40, height=40,
                font=("Segoe UI", 18), text_color="#5dade2",
                fg_color="transparent", hover_color=("gray80", "gray30"),
                command=self._open_settings,
            )
        self.settings_btn.pack(side="right", padx=PADDING["medium"])
        self._create_tooltip(self.settings_btn, "Settings")

    def _create_vertical_tabs(self):
        """Create vertical tab buttons on the left side with semi-transparent dark appearance."""
        self.tabs_frame = ctk.CTkFrame(self.main_container, width=135, fg_color=("#3d3d3d", "#1a1a1a"))
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

    def _create_trade_pane(self):
        """Create the trade manager pane (hidden by default)."""
        self.trade_pane = ctk.CTkFrame(self.content_frame, fg_color=("#3d3d3d", "#1a1a1a"))
        # Don't grid initially - only shown in trade mode

        # Header
        header_frame = ctk.CTkFrame(self.trade_pane, fg_color="transparent")
        header_frame.pack(fill="x", padx=PADDING["small"], pady=PADDING["small"])

        header_label = ctk.CTkLabel(header_frame, text="Trade Manager", font=FONTS["heading"])
        header_label.pack(side="left")

        # Centered button container for Show All / Hide All
        button_container = ctk.CTkFrame(self.trade_pane, fg_color="transparent")
        button_container.pack(fill="x", pady=(0, PADDING["small"]))

        # Center the buttons
        button_frame = ctk.CTkFrame(button_container, fg_color="transparent")
        button_frame.pack(anchor="center")

        # Show All button (expand symbol)
        show_all_btn = ctk.CTkButton(
            button_frame,
            text="⊞",  # Boxed plus - expand all
            width=40,
            height=32,
            font=("Segoe UI", 16),
            fg_color="transparent",
            hover_color=("gray80", "gray30"),
            command=self._trade_show_all
        )
        show_all_btn.pack(side="left", padx=5)
        self._create_tooltip(show_all_btn, "Show All")

        # Hide All button (collapse symbol)
        hide_all_btn = ctk.CTkButton(
            button_frame,
            text="⊟",  # Boxed minus - collapse all
            width=40,
            height=32,
            font=("Segoe UI", 16),
            fg_color="transparent",
            hover_color=("gray80", "gray30"),
            command=self._trade_hide_all
        )
        hide_all_btn.pack(side="left", padx=5)
        self._create_tooltip(hide_all_btn, "Hide All")

        # Clear All button (empty checkbox symbol)
        clear_all_btn = ctk.CTkButton(
            button_frame,
            text="☐",  # Empty checkbox - clear all
            width=40,
            height=32,
            font=("Segoe UI", 16),
            fg_color="transparent",
            hover_color=("gray80", "gray30"),
            command=self._trade_clear_all
        )
        clear_all_btn.pack(side="left", padx=5)
        self._create_tooltip(clear_all_btn, "Clear All")

        # Scrollable content area for merchants
        self.trade_scroll_frame = ctk.CTkScrollableFrame(self.trade_pane, fg_color="transparent")
        self.trade_scroll_frame.pack(fill="both", expand=True, padx=PADDING["small"], pady=PADDING["small"])

        # Store merchant data and UI references
        self.trade_merchants: list = []
        self.trade_merchant_frames: dict = {}
        self.trade_order_checkboxes: dict = {}
        self.trade_column_frames: list = []
        self.trade_current_columns: int = 0

        # Load merchant data
        self._load_trade_data()

        # Bind resize event to reflow columns
        self.trade_pane.bind("<Configure>", self._on_trade_pane_resize)

    def _load_trade_data(self):
        """Load merchant and order data from DT_OrderDecks.json."""
        from ..core.trade_data import load_order_decks, get_default_order_decks_path

        json_path = get_default_order_decks_path()
        if not json_path or not json_path.exists():
            # Show error message if file not found
            error_label = ctk.CTkLabel(
                self.trade_scroll_frame,
                text="Could not find DT_OrderDecks.json\n\nPlace the file in the gamesource directory.",
                font=FONTS["body"],
                text_color="orange",
                justify="center"
            )
            error_label.pack(expand=True, pady=PADDING["large"])
            return

        try:
            self.trade_merchants = load_order_decks(json_path)
            self._load_trade_config()  # Load saved checkbox state
            self._build_trade_ui()
        except Exception as e:
            error_label = ctk.CTkLabel(
                self.trade_scroll_frame,
                text=f"Error loading trade data:\n\n{e}",
                font=FONTS["body"],
                text_color="red",
                justify="center"
            )
            error_label.pack(expand=True, pady=PADDING["large"])

    def _build_trade_ui(self):
        """Build the trade manager UI with merchant dropdowns in columns."""
        # Initial build with default column count
        self._rebuild_trade_columns(self._calculate_trade_columns())

    def _calculate_trade_columns(self) -> int:
        """Calculate the number of columns based on pane width."""
        try:
            width = self.trade_pane.winfo_width()
            if width < 600:
                return 1
            elif width < 1000:
                return 2
            else:
                return 3
        except Exception:
            return 2  # Default to 2 columns

    def _on_trade_pane_resize(self, event=None):
        """Handle trade pane resize to adjust column count."""
        if not self.trade_merchants:
            return

        new_columns = self._calculate_trade_columns()
        if new_columns != self.trade_current_columns:
            self._rebuild_trade_columns(new_columns)

    def _rebuild_trade_columns(self, num_columns: int):
        """Rebuild the trade UI with the specified number of columns."""
        self.trade_current_columns = num_columns

        # Clear existing column frames
        for frame in self.trade_column_frames:
            frame.destroy()
        self.trade_column_frames.clear()
        self.trade_merchant_frames.clear()
        self.trade_order_checkboxes.clear()

        # Create column container
        columns_container = ctk.CTkFrame(self.trade_scroll_frame, fg_color="transparent")
        columns_container.pack(fill="both", expand=True)

        # Configure grid columns with equal weight
        for i in range(num_columns):
            columns_container.grid_columnconfigure(i, weight=1, uniform="trade_col")
        columns_container.grid_rowconfigure(0, weight=1)

        # Create column frames
        column_frames = []
        for i in range(num_columns):
            col_frame = ctk.CTkFrame(columns_container, fg_color="transparent")
            col_frame.grid(row=0, column=i, sticky="nsew", padx=2)
            column_frames.append(col_frame)
            self.trade_column_frames.append(columns_container)  # Store container for cleanup

        # Distribute merchants across columns
        for idx, merchant in enumerate(self.trade_merchants):
            col_idx = idx % num_columns
            self._create_merchant_section(merchant, column_frames[col_idx])

    def _create_merchant_section(self, merchant, parent=None):
        """Create a collapsible section for a merchant."""
        if parent is None:
            parent = self.trade_scroll_frame

        # Container for the merchant section
        section_frame = ctk.CTkFrame(parent, fg_color=("#2d2d2d", "#252525"))
        section_frame.pack(fill="x", pady=(0, PADDING["small"]))

        # Header row (clickable to expand/collapse)
        header_frame = ctk.CTkFrame(section_frame, fg_color="transparent")
        header_frame.pack(fill="x", padx=PADDING["small"], pady=PADDING["small"])

        # Expand/collapse arrow
        arrow_label = ctk.CTkLabel(
            header_frame,
            text="▼" if merchant.expanded else "▶",
            font=FONTS["body"],
            width=20
        )
        arrow_label.pack(side="left")

        # Merchant name
        name_label = ctk.CTkLabel(
            header_frame,
            text=merchant.display_name,
            font=FONTS["heading"]
        )
        name_label.pack(side="left", padx=(5, 0))

        # Order count
        count_label = ctk.CTkLabel(
            header_frame,
            text=f"({len(merchant.orders)} orders)",
            font=FONTS["small"],
            text_color="gray"
        )
        count_label.pack(side="left", padx=(10, 0))

        # Orders container (collapsible)
        orders_frame = ctk.CTkFrame(section_frame, fg_color="transparent")
        if merchant.expanded:
            orders_frame.pack(fill="x", padx=PADDING["medium"], pady=(0, PADDING["small"]))

        # Store references
        self.trade_merchant_frames[merchant.raw_name] = {
            "section": section_frame,
            "arrow": arrow_label,
            "orders_frame": orders_frame,
            "merchant": merchant
        }

        # Create order checkboxes
        self.trade_order_checkboxes[merchant.raw_name] = {}

        for order in merchant.orders:
            self._create_order_checkbox(orders_frame, merchant, order)

        # Make header clickable
        for widget in [header_frame, arrow_label, name_label, count_label]:
            widget.bind("<Button-1>", lambda e, m=merchant: self._toggle_merchant_section(m))
            widget.configure(cursor="hand2")

    def _create_order_checkbox(self, parent, merchant, order):
        """Create a checkbox for a single order."""
        var = ctk.BooleanVar(value=order.checked)

        checkbox = ctk.CTkCheckBox(
            parent,
            text=order.display_name,
            variable=var,
            font=FONTS["body"],
            command=lambda: self._on_order_toggle(merchant, order, var.get())
        )
        checkbox.pack(anchor="w", pady=2)

        self.trade_order_checkboxes[merchant.raw_name][order.raw_name] = {
            "checkbox": checkbox,
            "var": var,
            "order": order
        }

    def _toggle_merchant_section(self, merchant):
        """Toggle the expanded/collapsed state of a merchant section."""
        merchant.expanded = not merchant.expanded

        frame_data = self.trade_merchant_frames.get(merchant.raw_name)
        if not frame_data:
            return

        arrow_label = frame_data["arrow"]
        orders_frame = frame_data["orders_frame"]

        if merchant.expanded:
            arrow_label.configure(text="▼")
            orders_frame.pack(fill="x", padx=PADDING["medium"], pady=(0, PADDING["small"]))
        else:
            arrow_label.configure(text="▶")
            orders_frame.pack_forget()

    def _on_order_toggle(self, merchant, order, checked: bool):
        """Handle order checkbox toggle."""
        order.checked = checked
        self._save_trade_config()

    def _trade_show_all(self):
        """Expand all merchant sections."""
        for merchant in self.trade_merchants:
            if not merchant.expanded:
                merchant.expanded = True
                frame_data = self.trade_merchant_frames.get(merchant.raw_name)
                if frame_data:
                    frame_data["arrow"].configure(text="▼")
                    frame_data["orders_frame"].pack(fill="x", padx=PADDING["medium"], pady=(0, PADDING["small"]))

    def _trade_hide_all(self):
        """Collapse all merchant sections."""
        for merchant in self.trade_merchants:
            if merchant.expanded:
                merchant.expanded = False
                frame_data = self.trade_merchant_frames.get(merchant.raw_name)
                if frame_data:
                    frame_data["arrow"].configure(text="▶")
                    frame_data["orders_frame"].pack_forget()

    def _trade_clear_all(self):
        """Clear all order checkmarks."""
        for merchant in self.trade_merchants:
            for order in merchant.orders:
                order.checked = False
            # Update UI checkboxes
            merchant_checkboxes = self.trade_order_checkboxes.get(merchant.raw_name, {})
            for order_data in merchant_checkboxes.values():
                order_data["var"].set(False)
        # Save state
        self._save_trade_config()

    def _save_trade_config(self):
        """Save trade manager checkbox state to XML file."""
        import xml.etree.ElementTree as ET
        from xml.dom import minidom
        from ..config.paths import GamePaths

        GamePaths.ensure_config_dir()

        root = ET.Element("TradeManager", version="1.0")

        for merchant in self.trade_merchants:
            merchant_elem = ET.SubElement(root, "Merchant", name=merchant.raw_name)
            for order in merchant.orders:
                if order.checked:
                    ET.SubElement(merchant_elem, "Order", name=order.raw_name, checked="true")

        # Write pretty-printed XML
        xml_str = minidom.parseString(ET.tostring(root, encoding="unicode")).toprettyxml(indent="  ")
        lines = [line for line in xml_str.split('\n') if line.strip()]
        xml_str = '\n'.join(lines)

        GamePaths.TRADE_CONFIG_FILE.write_text(xml_str, encoding="utf-8")

    def _load_trade_config(self):
        """Load trade manager checkbox state from XML file."""
        import xml.etree.ElementTree as ET
        from ..config.paths import GamePaths

        if not GamePaths.TRADE_CONFIG_FILE.exists():
            return

        try:
            tree = ET.parse(GamePaths.TRADE_CONFIG_FILE)
            root = tree.getroot()

            # Build a set of checked orders for fast lookup
            checked_orders = set()
            for merchant_elem in root.findall("Merchant"):
                merchant_name = merchant_elem.get("name", "")
                for order_elem in merchant_elem.findall("Order"):
                    order_name = order_elem.get("name", "")
                    if order_elem.get("checked", "").lower() == "true":
                        checked_orders.add((merchant_name, order_name))

            # Apply to current merchants
            for merchant in self.trade_merchants:
                for order in merchant.orders:
                    order.checked = (merchant.raw_name, order.raw_name) in checked_orders

        except Exception as e:
            # If file is corrupted, just continue with defaults
            pass

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

        self.item_count_label = ctk.CTkLabel(header_frame, text="(0)", font=FONTS["small"], text_color="gray")
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
        self.item_list_frame = ctk.CTkScrollableFrame(self.world_pane, fg_color=("#3d3d3d", "#1a1a1a"))
        self.item_list_frame.pack(fill="both", expand=True, padx=PADDING["small"], pady=(0, PADDING["small"]))

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

        self.versions_header = ctk.CTkLabel(header_frame, text="File Versions", font=FONTS["heading"])
        self.versions_header.pack(side="left")

        self.versions_count_label = ctk.CTkLabel(header_frame, text="(0)", font=FONTS["small"], text_color="gray")
        self.versions_count_label.pack(side="left", padx=(5, 0))

        # Refresh button for Available Mods (hidden by default, shown in mods mode)
        self.available_mods_refresh_btn = ctk.CTkButton(
            header_frame, text="↻", width=28, height=28,
            font=FONTS["body"], command=self._refresh_available_mods
        )
        # Don't pack initially - only shown in mods mode

        # Scrollable list
        self.versions_list_frame = ctk.CTkScrollableFrame(self.versions_pane, fg_color=("#3d3d3d", "#1a1a1a"))
        self.versions_list_frame.pack(fill="both", expand=True, padx=PADDING["small"], pady=(0, PADDING["small"]))

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

    def _create_server_pane(self):
        """Create the server list pane (hidden by default, uses left tabs for installation selection)."""
        # Server pane spans both columns
        self.server_pane = ctk.CTkFrame(self.content_frame, fg_color=("#3d3d3d", "#1a1a1a"))
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
        self.server_content_frame.pack(fill="both", expand=True, padx=PADDING["small"], pady=PADDING["small"])

        # Header row with column titles
        self.server_header_frame = ctk.CTkFrame(self.server_content_frame, fg_color=("#2d2d2d", "#252525"))
        self.server_header_frame.pack(fill="x", pady=(0, 0))

        # Configure grid columns for spreadsheet layout
        self.server_header_frame.grid_columnconfigure(0, weight=2, minsize=120)  # Name
        self.server_header_frame.grid_columnconfigure(1, weight=2, minsize=150)  # Address
        self.server_header_frame.grid_columnconfigure(2, weight=1, minsize=100)  # Password
        self.server_header_frame.grid_columnconfigure(3, weight=3, minsize=200)  # Notes
        self.server_header_frame.grid_columnconfigure(4, weight=0, minsize=80)   # Actions

        # Column headers
        name_header = ctk.CTkLabel(self.server_header_frame, text="Name", font=FONTS["heading"], anchor="w")
        name_header.grid(row=0, column=0, sticky="w", padx=(PADDING["small"], 5), pady=5)

        address_header = ctk.CTkLabel(self.server_header_frame, text="Address", font=FONTS["heading"], anchor="w")
        address_header.grid(row=0, column=1, sticky="w", padx=5, pady=5)

        password_header = ctk.CTkLabel(self.server_header_frame, text="Password", font=FONTS["heading"], anchor="w")
        password_header.grid(row=0, column=2, sticky="w", padx=5, pady=5)

        notes_header = ctk.CTkLabel(self.server_header_frame, text="Notes", font=FONTS["heading"], anchor="w")
        notes_header.grid(row=0, column=3, sticky="w", padx=5, pady=5)

        actions_header = ctk.CTkLabel(self.server_header_frame, text="", font=FONTS["heading"], anchor="center")
        actions_header.grid(row=0, column=4, sticky="ew", padx=5, pady=5)

        # Scrollable frame for server rows
        self.server_list_frame = ctk.CTkScrollableFrame(self.server_content_frame, fg_color=("#3d3d3d", "#1a1a1a"))
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
        name_entry = ctk.CTkEntry(row_frame, font=FONTS["body"], height=28)
        name_entry.insert(0, data.get("name", ""))
        name_entry.grid(row=0, column=0, sticky="ew", padx=(PADDING["small"], 5), pady=2)
        name_entry.bind("<FocusOut>", lambda e, iid=install_id, idx=row_index: self._on_server_field_change(iid, idx))
        name_entry.bind("<KeyRelease>", lambda e, iid=install_id, idx=row_index: self._schedule_server_save(iid, idx))

        # Address entry with copy button
        address_frame = ctk.CTkFrame(row_frame, fg_color="transparent")
        address_frame.grid(row=0, column=1, sticky="ew", padx=5, pady=2)
        address_frame.grid_columnconfigure(0, weight=1)

        address_entry = ctk.CTkEntry(address_frame, font=FONTS["body"], height=28)
        address_entry.insert(0, data.get("address", ""))
        address_entry.grid(row=0, column=0, sticky="ew")
        address_entry.bind("<FocusOut>", lambda e, iid=install_id, idx=row_index: self._on_server_field_change(iid, idx))
        address_entry.bind("<KeyRelease>", lambda e, iid=install_id, idx=row_index: self._schedule_server_save(iid, idx))

        address_copy_btn = ctk.CTkButton(
            address_frame, text="\U0001F4CB", width=24, height=24,
            font=("Segoe UI", 10),
            fg_color="transparent", hover_color=("gray80", "gray30"),
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
        password_entry.bind("<FocusOut>", lambda e, iid=install_id, idx=row_index: self._on_server_field_change(iid, idx))
        password_entry.bind("<KeyRelease>", lambda e, iid=install_id, idx=row_index: self._schedule_server_save(iid, idx))

        # Store password visibility state per row
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
            command=toggle_password
        )
        eye_btn.grid(row=0, column=1, padx=(2, 0))

        password_copy_btn = ctk.CTkButton(
            password_frame, text="\U0001F4CB", width=24, height=24,
            font=("Segoe UI", 10),
            fg_color="transparent", hover_color=("gray80", "gray30"),
            command=lambda: self._copy_to_clipboard(password_entry.get(), "Password")
        )
        password_copy_btn.grid(row=0, column=2, padx=(2, 0))

        # Notes entry
        notes_entry = ctk.CTkEntry(row_frame, font=FONTS["body"], height=28)
        notes_entry.insert(0, data.get("notes", ""))
        notes_entry.grid(row=0, column=3, sticky="ew", padx=5, pady=2)
        notes_entry.bind("<FocusOut>", lambda e, iid=install_id, idx=row_index: self._on_server_field_change(iid, idx))
        notes_entry.bind("<KeyRelease>", lambda e, iid=install_id, idx=row_index: self._schedule_server_save(iid, idx))

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

    def _on_server_field_change(self, install_id: str, row_index: int):
        """Handle field change - update data and save."""
        # Find the widgets for this install_id and row_index
        for widgets in self.server_row_widgets:
            if widgets.get("install_id") == install_id:
                # Find the correct row by counting
                entries = self.server_entries_by_install.get(install_id, [])
                if row_index < len(entries):
                    # Update the data from the widgets
                    # We need to find the correct widget for this row
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
        """Schedule a save after typing (debounced)."""
        # Cancel any existing scheduled save
        if hasattr(self, "_server_save_timer") and self._server_save_timer:
            self.after_cancel(self._server_save_timer)

        # Schedule save after 1 second of no typing
        self._server_save_timer = self.after(1000, lambda: self._on_server_field_change(install_id, row_index))

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
            ET.SubElement(server_elem, "Password").text = entry.get("password", "")
            ET.SubElement(server_elem, "Notes").text = entry.get("notes", "")

        # Write pretty-printed XML
        xml_str = minidom.parseString(ET.tostring(root, encoding="unicode")).toprettyxml(indent="  ")
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
                    "password": self._get_elem_text(server_elem, "Password"),
                    "notes": self._get_elem_text(server_elem, "Notes"),
                }
                self.server_entries_by_install[install_id].append(entry)

        except Exception as e:
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

        except Exception as e:
            # DnD setup failed, continue without it
            logger.warning(f"Drag-and-drop setup failed: {e}")
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
        except Exception as e:
            logger.debug(f"Could not parse Tcl list, using raw data: {e}")
            files = [event.data] if event.data else []

        if not files:
            return event.action

        self._import_dropped_mod_files(files)
        return event.action

    def _import_dropped_mod_files(self, files: list):
        """Import dropped files/folders to the Available Mods directory."""
        import shutil
        import zipfile

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

            dest_path = mods_backup_path / source_path.name

            try:
                if source_path.is_dir():
                    # Copy directory
                    if dest_path.exists():
                        # Ask to overwrite
                        choice = self._show_overwrite_skip_dialog(
                            "Folder Exists",
                            f"The folder '{source_path.name}' already exists in Available Mods.\n\nOverwrite?"
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

                            # Check if the zip contains a single top-level folder
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
                                    f"Some items from '{source_path.name}' already exist:\n{items_str}\n\nOverwrite?"
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
                    # For .pak files, copy all 3 related files
                    mod_name = source_path.stem
                    source_dir = source_path.parent
                    extensions = [".pak", ".ucas", ".utoc"]

                    # Check if any exist
                    any_exist = any((mods_backup_path / f"{mod_name}{ext}").exists() for ext in extensions)
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
                            f"The file '{source_path.name}' already exists in Available Mods.\n\nOverwrite?"
                        )
                        if choice == "skip":
                            skipped_count += 1
                            continue

                    shutil.copy2(str(source_path), str(dest_path))
                    imported_count += 1

            except Exception as e:
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

    def _create_status_bar(self):
        """Create the bottom status bar with semi-transparent dark appearance."""
        self.status_bar = ctk.CTkFrame(self, height=30, fg_color=("#3d3d3d", "#1a1a1a"))
        self.status_bar.pack(fill="x", side="bottom")
        self.status_bar.pack_propagate(False)

        self.status_label = ctk.CTkLabel(self.status_bar, text="Ready", font=FONTS["small"], text_color=("#cccccc", "#999999"))
        self.status_label.pack(side="left", padx=PADDING["medium"], pady=PADDING["small"])

    def _select_first_tab(self):
        """Select the first available tab on startup."""
        enabled = self.config_manager.config.get_enabled_installations()
        if enabled:
            self._on_tab_selected(enabled[0])

    def _on_tab_selected(self, installation: Installation):
        """Handle tab selection."""
        self.current_installation = installation

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

    def _refresh_item_list(self):
        """Refresh the world/character list for the current installation."""
        # Clear existing items
        for widget in self.item_list_frame.winfo_children():
            widget.destroy()

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
            self.worlds_data = self.parser.get_worlds_with_versions(self.current_installation.save_path)
            items = self.worlds_data
            empty_message = "No world saves found"
        else:
            self.characters_data = self.parser.get_characters_with_versions(self.current_installation.save_path)
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

    def _create_item_row(self, item: WorldWithVersions | CharacterWithVersions):
        """Create a clickable row for a world or character."""
        row = ctk.CTkFrame(self.item_list_frame, cursor="hand2")
        row.pack(fill="x", pady=2)

        # Make the whole row clickable
        row.bind("<Button-1>", lambda e, i=item: self._on_item_selected(i))

        # Display name (world_name for worlds, display_name for characters)
        if isinstance(item, WorldWithVersions):
            display_name = item.world_name
        else:
            display_name = item.display_name

        name_label = ctk.CTkLabel(row, text=display_name, font=FONTS["body"], anchor="w")
        name_label.pack(fill="x", padx=PADDING["small"], pady=(PADDING["small"], 0))
        name_label.bind("<Button-1>", lambda e, i=item: self._on_item_selected(i))

        # Filename (smaller, gray)
        filename_label = ctk.CTkLabel(
            row, text=item.base_name,
            font=FONTS["small"], text_color="gray", anchor="w"
        )
        filename_label.pack(fill="x", padx=PADDING["small"], pady=(0, PADDING["small"]))
        filename_label.bind("<Button-1>", lambda e, i=item: self._on_item_selected(i))

        # Version count badge
        version_count = len(item.versions)
        badge = ctk.CTkLabel(
            row, text=f"{version_count} files",
            font=FONTS["small"], text_color="gray"
        )
        badge.place(relx=1.0, rely=0.5, anchor="e", x=-PADDING["small"])
        badge.bind("<Button-1>", lambda e, i=item: self._on_item_selected(i))

    def _on_item_selected(self, item: WorldWithVersions | CharacterWithVersions):
        """Handle world/character selection."""
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
                widget.configure(fg_color=("gray85", "gray25") if is_selected
                               else ("gray95", "gray17"))

        # Update button states
        self._update_backup_button_states()

        # Refresh versions pane
        self._refresh_versions_list()

        self._set_status(f"Selected: {display_name}")

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

        # Sort versions: main first, then fresh, then backups by number
        sorted_versions = []
        if self.selected_item.main_file:
            sorted_versions.append(self.selected_item.main_file)
        if self.selected_item.fresh_file:
            sorted_versions.append(self.selected_item.fresh_file)
        sorted_versions.extend(self.selected_item.backup_files)

        # Create row for each version
        for version in sorted_versions:
            self._create_version_row(version)

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
            font=FONTS["body"], anchor="w"
        )
        name_label.pack(side="left", fill="x", expand=True, padx=PADDING["small"], pady=PADDING["small"])
        name_label.bind("<Button-1>", lambda e, v=version: self._on_version_selected(v))

    def _on_version_selected(self, version: SaveFileVersion):
        """Handle version selection - highlight and show restore/mark bad buttons."""
        self.selected_version = version

        # Check if there's a main .sav file for this item
        has_main_file = self.selected_item and self.selected_item.main_file is not None

        # Update highlighting on all rows
        for filename, row in self.version_rows.items():
            # Remove old buttons if present
            for child in row.winfo_children():
                if isinstance(child, ctk.CTkButton):
                    child.destroy()

            is_selected = (filename == version.filename)
            row.configure(fg_color=("gray85", "gray25") if is_selected else ("gray95", "gray17"))

            if is_selected:
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
                        # Fallback: red circle with slash (🚫)
                        mark_bad_btn = ctk.CTkButton(
                            row, text="🚫", width=24, height=24,
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
                        # Fallback: green recycle symbol (♻)
                        restore_btn = ctk.CTkButton(
                            row, text="♻", width=24, height=24,
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
                            row, text="↩", width=24, height=24,
                            font=FONTS["small"],
                            command=lambda v=version: self._restore_version(v)
                        )
                    restore_btn.pack(side="right", padx=PADDING["small"])
                    self._create_tooltip(restore_btn, "Make this file the current save")

        self._set_status(f"Selected version: {version.display_name}")

    def _restore_version(self, version: SaveFileVersion):
        """Restore the selected version as the current save (copies over existing main file)."""
        if not self.current_installation or not self.selected_item:
            self._set_status("No item selected")
            return

        try:
            # Get the main save file path
            main_file = self.selected_item.main_file
            if not main_file:
                self._set_status("No main save file found")
                return

            import shutil
            # Backup current save first
            backup_path = main_file.file_path.with_suffix(".sav.backup")
            shutil.copy2(main_file.file_path, backup_path)

            # Copy selected version to main save
            shutil.copy2(version.file_path, main_file.file_path)

            self._set_status(f"Restored {version.display_name} as current save")
            self._refresh_versions_list()
        except Exception as e:
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

            # Rename the file
            version.file_path.rename(new_path)
            self._set_status(f"Restored: {new_path.name}")

            # Refresh the lists to reflect the change
            self._refresh_item_list()
            # Re-select the item if possible
            if self.selected_item:
                # Find the item again by base_name
                items = self.worlds_data if self.current_view_type == "Worlds" else self.characters_data
                for item in items:
                    if item.base_name == base_name:
                        self._on_item_selected(item)
                        return
            self._refresh_versions_list()
        except Exception as e:
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
            # Find an unused .XX.bad suffix
            for i in range(100):
                bad_path = version.file_path.parent / f"{version.file_path.name}.{i:02d}.bad"
                if not bad_path.exists():
                    # Rename the file
                    version.file_path.rename(bad_path)
                    self._set_status(f"Marked as bad: {bad_path.name}")

                    # Refresh the lists to reflect the change
                    self._refresh_item_list()
                    self.selected_item = None
                    self._refresh_versions_list()
                    return

            self._set_status("Could not mark as bad: too many bad files")
        except Exception as e:
            self._set_status(f"Mark bad failed: {e}")

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

    def _backup_selected_item(self):
        """Backup the currently selected world/character only."""
        if not self.current_installation:
            self._set_status("No installation selected")
            return

        if not self.selected_item:
            self._set_status("No item selected")
            return

        try:
            if isinstance(self.selected_item, WorldWithVersions):
                item_name = self.selected_item.world_name
                # Get main file for this world
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
        except Exception as e:
            self._set_status(f"Backup failed: {e}")

    def _backup_all_items(self):
        """Backup all worlds or characters for current installation."""
        if not self.current_installation:
            self._set_status("No installation selected")
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
        except Exception as e:
            self._set_status(f"Backup failed: {e}")

    def _create_single_item_backup(self, main_file, item_name: str):
        """Create a backup of a single save file using the index-based structure.

        Backups are stored in the user's configured backup location with structure:
            backup_location/
                worlds/
                    index.xml
                    World Name/
                        2026-01-16_143052/
                            MW_12345678.sav
                characters/
                    index.xml
                    Character Name/
                        2026-01-16_143052/
                            MC_12345678.sav

        The timestamp subdirectory is based on the source file's modification time,
        not the current time.

        Args:
            main_file: The SaveFileVersion for the main save file
            item_name: Display name (world name or character name)

        Returns:
            Path to backup file if successful, None otherwise
        """
        import shutil
        from datetime import datetime

        if not self.current_installation:
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

            # Get the file's modification timestamp (not current time)
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
        except Exception as e:
            logger.error(f"Backup error for {item_name}: {e}")
            return None

    def _create_tooltip(self, widget, text: str):
        """Create a hover tooltip for a widget (displays above cursor)."""
        tooltip = None

        def show_tooltip(event):
            nonlocal tooltip
            # Position tooltip above the widget
            x = widget.winfo_rootx()
            y = widget.winfo_rooty() - 30  # Above the widget

            tooltip = ctk.CTkToplevel(widget)
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{x}+{y}")

            label = ctk.CTkLabel(
                tooltip, text=text,
                font=FONTS["small"],
                fg_color=("gray90", "gray20"),
                corner_radius=4,
                padx=8, pady=4
            )
            label.pack()

        def hide_tooltip(event):
            nonlocal tooltip
            if tooltip:
                tooltip.destroy()
                tooltip = None

        widget.bind("<Enter>", show_tooltip)
        widget.bind("<Leave>", hide_tooltip)

    def _load_icon(self, relative_path: str, size: tuple[int, int] = (24, 24)) -> Optional[ctk.CTkImage]:
        try:
            icon_path = get_asset_path(relative_path)
            if icon_path.exists():
                image = Image.open(icon_path)
                return ctk.CTkImage(light_image=image, dark_image=image, size=size)
        except Exception as e:
            logger.debug(f"Could not load icon {relative_path}: {e}")
        return None

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
        """Show the standard two-pane view and hide server/trade panes."""
        # Hide special panes
        self.server_pane.grid_forget()
        self.trade_pane.grid_forget()

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
            # Hide available mods refresh button
            self.available_mods_refresh_btn.pack_forget()
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
            # Hide available mods refresh button
            self.available_mods_refresh_btn.pack_forget()
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
            # Show available mods refresh button
            self.available_mods_refresh_btn.pack(side="right", padx=2)
            self._create_tooltip(self.available_mods_refresh_btn, "Refresh Available Mods")

    def _refresh_restore_list(self):
        """Refresh the world/character list from backup index for restore mode."""
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
            self.restore_entries = index_manager.list_entries()
        except Exception as e:
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
            empty_message = "No world backups found" if category == "worlds" else "No character backups found"
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
            self._create_restore_entry_row(entry)

    def _create_restore_entry_row(self, entry: BackupIndexEntry):
        """Create a clickable row for a backup index entry in restore mode."""
        row = ctk.CTkFrame(self.item_list_frame, cursor="hand2")
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

    def _on_restore_entry_selected(self, entry: BackupIndexEntry):
        """Handle backup entry selection in restore mode."""
        self.selected_restore_entry = entry

        # Highlight selected item
        for widget in self.item_list_frame.winfo_children():
            if isinstance(widget, ctk.CTkFrame):
                is_selected = (widget.winfo_children() and
                               widget.winfo_children()[0].cget("text") == entry.display_name)
                widget.configure(fg_color=("gray85", "gray25") if is_selected
                               else ("gray95", "gray17"))

        # Refresh timestamps pane
        self._refresh_restore_timestamps()

        self._set_status(f"Selected backup: {entry.display_name}")

    def _refresh_restore_timestamps(self):
        """Refresh the timestamp list for the selected backup entry."""
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
            self.restore_timestamps = index_manager.get_backup_timestamps(self.selected_restore_entry)
        except Exception as e:
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

    def _create_restore_timestamp_row(self, timestamp_dir: Path):
        """Create a clickable row for a backup timestamp directory."""
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
        name_label.pack(side="left", fill="x", expand=True, padx=PADDING["small"], pady=PADDING["small"])
        name_label.bind("<Button-1>", lambda e, ts=timestamp_dir: self._on_restore_timestamp_selected(ts))

    def _on_restore_timestamp_selected(self, timestamp_dir: Path):
        """Handle timestamp selection in restore mode - show restore button."""
        self.selected_restore_timestamp = timestamp_dir

        # Update highlighting on all rows
        for dirname, row in self.version_rows.items():
            # Remove old buttons if present
            for child in row.winfo_children():
                if isinstance(child, ctk.CTkButton):
                    child.destroy()

            is_selected = (dirname == timestamp_dir.name)
            row.configure(fg_color=("gray85", "gray25") if is_selected else ("gray95", "gray17"))

            if is_selected:
                # Add restore button
                restore_image = self._load_icon("icons/restore_green.png", size=(16, 16))
                if restore_image:
                    restore_btn = ctk.CTkButton(
                        row, image=restore_image, text="", width=24, height=24,
                        fg_color="transparent", hover_color=("gray80", "gray30"),
                        command=lambda ts=timestamp_dir: self._restore_from_backup(ts)
                    )
                else:
                    restore_btn = ctk.CTkButton(
                        row, text="♻", width=24, height=24,
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

    def _restore_from_backup(self, timestamp_dir: Path):
        """Restore a backup from the backup location to the game save directory."""
        if not self.current_installation or not self.current_installation.save_path:
            self._set_status("No installation selected")
            return

        if not self.selected_restore_entry:
            self._set_status("No backup selected")
            return

        try:
            import shutil

            # Get backup root
            backup_root = (
                self.config_manager.config.settings.backup_location
                or GamePaths.BACKUP_DEFAULT
            )

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
                    message = f"The file '{existing_files[0]}' already exists.\n\nDo you want to overwrite it?"
                else:
                    file_list = "\n".join(f"  - {f}" for f in existing_files[:5])
                    if len(existing_files) > 5:
                        file_list += f"\n  ... and {len(existing_files) - 5} more"
                    message = f"The following files already exist:\n{file_list}\n\nDo you want to overwrite them?"

                if not self._show_confirm_dialog("Confirm Overwrite", message):
                    self._set_status("Restore cancelled")
                    return

            # Restore each file
            restored_count = 0
            for backup_file in backup_files:
                # Destination is the game's save directory
                dest_path = self.current_installation.save_path / backup_file.name

                # If destination exists, back it up first
                if dest_path.exists():
                    backup_dest = dest_path.with_suffix(".sav.pre_restore")
                    shutil.copy2(dest_path, backup_dest)

                # Copy the backup file to the save directory
                shutil.copy2(backup_file, dest_path)
                restored_count += 1

            self._set_status(f"Restored {restored_count} file(s) from backup")

            # Refresh to show the restored files
            self._refresh_restore_timestamps()

        except Exception as e:
            self._set_status(f"Restore failed: {e}")

    def _refresh_mods_list(self):
        """Refresh the mods list showing Paks folder contents."""
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

        # Get all files and directories, excluding internal game files
        # For files, only show .pak (hide .ucas and .utoc as they work together with .pak)
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
        except Exception as e:
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

        # Clear right pane
        self._refresh_available_mods()

    def _create_mod_item_row(self, item_path: Path):
        """Create a clickable row for a mod file or directory."""
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
        name_label.pack(side="left", fill="x", expand=True, padx=(0, PADDING["small"]), pady=PADDING["small"])
        name_label.bind("<Button-1>", lambda e, p=item_path: self._on_mod_item_selected(p))

        # Store reference for highlighting
        self.version_rows[item_path.name] = row

    def _on_mod_item_selected(self, item_path: Path):
        """Handle mod item selection."""
        self.selected_mod_item = item_path

        # Update highlighting on all rows and add/remove action buttons
        for name, row in self.version_rows.items():
            # Remove old action buttons if present
            for child in row.winfo_children():
                if isinstance(child, ctk.CTkButton):
                    child.destroy()

            is_selected = (name == item_path.name)
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

    def _move_mod_to_available(self, item_path: Path):
        """Move a mod directory to the backup/mods directory."""
        import shutil

        backup_root = (
            self.config_manager.config.settings.backup_location
            or GamePaths.BACKUP_DEFAULT
        )
        mods_backup_path = backup_root / "mods"

        # Ensure mods directory exists
        mods_backup_path.mkdir(parents=True, exist_ok=True)

        dest_path = mods_backup_path / item_path.name

        try:
            shutil.move(str(item_path), str(dest_path))
            self._set_status(f"Moved '{item_path.name}' to Available Mods")
            # Refresh both panes
            self._refresh_mods_list()
        except Exception as e:
            self._set_status(f"Failed to move mod: {e}")

    def _prompt_remove_installed_mod_dir(self, item_path: Path):
        """Prompt to remove a mod directory from Installed Mods (game's Paks folder)."""
        import time
        import os
        import stat
        message = f"The mod '{item_path.name}' is already in Available Mods.\n\nWould you like to remove it from Installed Mods?"

        def remove_readonly(func, path, excinfo):
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
            except Exception as e:
                logger.debug(f"Could not clear read-only on {path}: {e}")

        if self._show_confirm_dialog("Remove from Installed?", message):
            import shutil
            errors_log = []
            try:
                if item_path.is_dir():
                    # First, clear read-only attributes from all files/folders
                    try:
                        clear_readonly_recursive(item_path)
                        errors_log.append("Cleared read-only attributes")
                    except Exception as e:
                        errors_log.append(f"Could not clear read-only: {e}")

                    # First attempt with onerror handler
                    try:
                        shutil.rmtree(str(item_path), onerror=remove_readonly)
                        errors_log.append(f"Attempt 1: shutil.rmtree completed")
                    except Exception as e:
                        errors_log.append(f"Attempt 1: shutil.rmtree failed - {e}")

                    # Retry mechanism: check if directory still exists and try again
                    max_retries = 3
                    for attempt in range(max_retries):
                        if not item_path.exists():
                            errors_log.append(f"Directory removed successfully after attempt {attempt + 1}")
                            break

                        # Check what's left in the directory
                        try:
                            remaining = list(item_path.iterdir()) if item_path.is_dir() else []
                            errors_log.append(f"Retry {attempt + 1}: Directory still exists, {len(remaining)} items remaining")
                        except Exception as e:
                            errors_log.append(f"Retry {attempt + 1}: Could not list directory - {e}")

                        # Small delay before retry (Windows file handles may need time to release)
                        time.sleep(0.2)

                        # Clear read-only again before retry
                        try:
                            clear_readonly_recursive(item_path)
                        except Exception as e:
                            logger.debug(f"Retry clear read-only failed: {e}")

                        try:
                            if item_path.is_dir():
                                # Try removing with os.rmdir if empty
                                try:
                                    os.chmod(str(item_path), stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)
                                    os.rmdir(str(item_path))
                                    errors_log.append(f"Retry {attempt + 1}: os.rmdir succeeded")
                                except OSError as rmdir_err:
                                    errors_log.append(f"Retry {attempt + 1}: os.rmdir failed - {rmdir_err}")
                                    # If rmdir fails, try shutil.rmtree again
                                    shutil.rmtree(str(item_path), onerror=remove_readonly)
                                    errors_log.append(f"Retry {attempt + 1}: shutil.rmtree succeeded")
                            elif item_path.exists():
                                os.chmod(str(item_path), stat.S_IWRITE)
                                item_path.unlink()
                                errors_log.append(f"Retry {attempt + 1}: unlink succeeded")
                        except Exception as retry_err:
                            errors_log.append(f"Retry {attempt + 1}: Failed - {retry_err}")

                    if item_path.exists():
                        # Show error popup with details
                        error_details = "\n".join(errors_log)
                        self._show_info_dialog(
                            "Directory Removal Failed",
                            f"Could not fully remove '{item_path.name}'.\n\nDetails:\n{error_details}"
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
            except Exception as e:
                self._show_info_dialog("Removal Error", f"Failed to remove mod: {e}\n\nLog:\n" + "\n".join(errors_log))
                self._set_status(f"Failed to remove mod: {e}")

    def _create_folder_for_mod_files(self, item_path: Path):
        """Create a folder with the mod name and move all 3 files into it.

        Takes a .pak file, creates a directory with the mod name (no extension),
        and moves the .pak, .ucas, and .utoc files into that directory.
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
        except Exception as e:
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
        except Exception as e:
            self._set_status(f"Failed to move mod files: {e}")

    def _prompt_remove_installed_mod_files(self, item_path: Path):
        """Prompt to remove mod files from Installed Mods (game's Paks folder)."""
        mod_name = item_path.stem  # Filename without extension
        containing_dir = item_path.parent  # The directory containing the files

        message = f"The mod '{mod_name}' is already in Available Mods.\n\nWould you like to remove it from Installed Mods?"

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

                # If the containing directory is now empty and it's a mod subdirectory
                # (not the main Paks folder), remove it too
                if containing_dir.exists() and containing_dir.name != "Paks":
                    try:
                        # Check if directory is empty
                        remaining_files = list(containing_dir.iterdir())
                        if not remaining_files:
                            containing_dir.rmdir()
                            self._set_status(f"Removed '{mod_name}' and empty folder from Installed Mods")
                        else:
                            self._set_status(f"Removed '{mod_name}' from Installed Mods ({deleted_count} files)")
                    except OSError:
                        self._set_status(f"Removed '{mod_name}' from Installed Mods ({deleted_count} files)")
                else:
                    self._set_status(f"Removed '{mod_name}' from Installed Mods ({deleted_count} files)")

                # Refresh the mods list
                self._refresh_mods_list()
            except Exception as e:
                self._set_status(f"Failed to remove mod files: {e}")

    def _refresh_available_mods(self):
        """Refresh the right pane with available mods from backup/mods directory."""
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
            except Exception as e:
                logger.warning(f"Could not create mods directory {mods_path}: {e}")

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

            # Sort: directories first, then files, alphabetically
            items.sort(key=lambda x: (not x.is_dir(), x.name.lower()))
            self.available_mods_items = items
        except Exception as e:
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

        # Create row for each available mod
        for item in items:
            self._create_available_mod_row(item)

    def _create_available_mod_row(self, item_path: Path):
        """Create a row for an available mod in the right pane."""
        row = ctk.CTkFrame(self.versions_list_frame, cursor="hand2")
        row.pack(fill="x", pady=1)

        # Make row clickable
        row.bind("<Button-1>", lambda e, p=item_path: self._on_available_mod_selected(p))

        # Store reference for highlighting
        self.available_mod_rows[item_path.name] = row

        # Icon indicator
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
        icon_label.bind("<Button-1>", lambda e, p=item_path: self._on_available_mod_selected(p))
        self._create_tooltip(icon_label, tooltip_text)

        # Name label
        display_name = item_path.stem if item_path.is_file() else item_path.name
        name_label = ctk.CTkLabel(
            row, text=display_name,
            font=FONTS["body"], anchor="w"
        )
        name_label.pack(side="left", fill="x", expand=True, padx=(0, PADDING["small"]), pady=PADDING["small"])
        name_label.bind("<Button-1>", lambda e, p=item_path: self._on_available_mod_selected(p))

    def _on_available_mod_selected(self, item_path: Path):
        """Handle available mod item selection."""
        self.selected_available_mod = item_path

        # Update highlighting on all rows and add/remove action buttons
        for name, row in self.available_mod_rows.items():
            # Remove old action buttons if present
            for child in row.winfo_children():
                if isinstance(child, ctk.CTkButton):
                    child.destroy()

            is_selected = (name == item_path.name)
            row.configure(fg_color=("gray85", "gray25") if is_selected else ("gray95", "gray17"))

            # Add action buttons for selected item
            if is_selected:
                # Left arrow button to install
                action_btn = ctk.CTkButton(
                    row, text="\u276E", width=28, height=24,  # Bold left arrow
                    font=("Segoe UI", 14, "bold"),
                    text_color=("gray10", "gray90"),
                    fg_color="transparent", hover_color=("gray80", "gray30"),
                    command=lambda p=item_path: self._install_mod_from_available(p)
                )
                action_btn.pack(side="right", padx=PADDING["small"])
                self._create_tooltip(action_btn, "Install to Game")

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

    def _install_mod_from_available(self, item_path: Path):
        """Copy a mod from Available Mods to Installed Mods (game's Paks folder)."""
        import shutil

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
                        f"The mod '{item_path.name}' is already installed.\n\nWould you like to overwrite it?"
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
                        f"The mod '{mod_name}' is already installed.\n\nWould you like to overwrite it?"
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

        except Exception as e:
            self._set_status(f"Failed to install mod: {e}")

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
                # Directory already exists - delete the loose files
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

        except Exception as e:
            self._set_status(f"Failed to organize mod files: {e}")

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

        # Hide the two-pane view and trade pane, show server pane
        self.world_pane.grid_forget()
        self.versions_pane.grid_forget()
        self.trade_pane.grid_forget()

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

        # Hide the left tabs
        self.tabs_frame.grid_forget()

        # Hide all other panes
        self.world_pane.grid_forget()
        self.versions_pane.grid_forget()
        self.server_pane.grid_forget()

        # Reconfigure content frame to span full width (no tabs column)
        self.content_frame.grid(row=0, column=0, columnspan=2, sticky="nsew")

        # Show trade pane spanning both columns
        self.trade_pane.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=PADDING["medium"])

        self._set_status("Switched to Trade Manager")

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

    def _on_close(self):
        """Handle window close event."""
        self.destroy()
