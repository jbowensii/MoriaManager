"""Trade Manager mixin providing all trade-related UI methods for MainWindow."""

from __future__ import annotations

from typing import Optional
import tkinter as tk

import customtkinter as ctk

from ..logging_config import get_logger
from .styles import FONTS, PADDING, THEME_COLORS

logger = get_logger("trade_mixin")


class TradeMixin:
    """Mixin providing the Trade Manager tab for MainWindow.

    The Trade Manager displays an interactive, scrollable grid of in-game
    merchants and their available trade orders.  Each order has a checkbox
    (to mark it as desired) and a quantity spinbox.  The UI is organized
    into collapsible merchant sections distributed across a responsive
    multi-column layout that reflows when the window is resized.

    Key features:
        - Lazy initialization: the pane container is created at startup but
          merchant data and widgets are only built the first time the user
          switches to the Trade tab, keeping startup fast.
        - Responsive columns: column count (1-3) adapts to pane width with
          a 100 ms debounce to avoid excessive rebuilds during live resize.
        - Persistent state: checkbox and quantity values are saved to / loaded
          from an XML config file so selections survive across sessions.
        - Bulk actions: Show All / Hide All toggle every merchant section;
          Clear All resets all checkboxes and quantities to zero.

    Expected attributes provided by the host MainWindow:
        content_frame   -- Parent frame for mode panes
        after()         -- Tk scheduler for debounced callbacks
        _create_tooltip() -- Tooltip helper for icon buttons
    """

    # --- Pane Initialization & Lazy Loading ---

    def _create_trade_pane(self):
        """Create the trade manager pane container (lazy loading - data loaded on first use)."""
        self.trade_pane = ctk.CTkFrame(self.content_frame, fg_color=THEME_COLORS["bg_pane_content"])
        # Don't grid initially - only shown in trade mode

        # Store merchant data and UI references (initialized empty)
        self.trade_merchants: list = []
        self.trade_merchant_frames: dict = {}
        self.trade_order_checkboxes: dict = {}
        self.trade_column_frames: list = []
        self.trade_current_columns: int = 0
        self.trade_initialized: bool = False  # Track if trade UI has been built
        self.trade_resize_pending: bool = False  # Debounce resize events
        self.trade_scroll_frame: Optional[ctk.CTkScrollableFrame] = None

    def _initialize_trade_ui(self):
        """Initialize the trade manager UI (called on first use for lazy loading)."""
        if self.trade_initialized:
            return

        self.trade_initialized = True

        # Header
        header_frame = ctk.CTkFrame(self.trade_pane, fg_color="transparent")
        header_frame.pack(fill="x", padx=PADDING["small"], pady=PADDING["small"])

        header_label = ctk.CTkLabel(header_frame, text="Trade Manager", font=FONTS["heading"], text_color=THEME_COLORS["text"])
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
            text="\u229e",  # Boxed plus - expand all
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
            text="\u229f",  # Boxed minus - collapse all
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
            text="\u2610",  # Empty checkbox - clear all
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
        self.trade_scroll_frame.pack(
            fill="both", expand=True,
            padx=PADDING["small"], pady=PADDING["small"]
        )

        # Load merchant data
        self._load_trade_data()

        # Bind resize event to reflow columns (with debounce)
        self.trade_pane.bind("<Configure>", self._on_trade_pane_resize)

    def _load_trade_data(self):
        """Load merchant and order data from embedded data."""
        from ..core.trade_data import load_merchants

        try:
            self.trade_merchants = load_merchants()
            self._load_trade_config()  # Load saved checkbox state
            self._build_trade_ui()
        except (KeyError, ValueError) as e:
            error_label = ctk.CTkLabel(
                self.trade_scroll_frame,
                text=f"Error loading trade data:\n\n{e}",
                font=FONTS["body"],
                text_color="red",
                justify="center"
            )
            error_label.pack(expand=True, pady=PADDING["large"])

    # --- Responsive Column Layout ---

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
            if width < 1000:
                return 2
            return 3
        except tk.TclError:
            return 2  # Default to 2 columns

    def _on_trade_pane_resize(self, _event=None):
        """Handle trade pane resize to adjust column count.

        Uses a boolean flag + 100 ms ``after()`` delay to debounce rapid
        <Configure> events that fire during live window dragging.
        """
        if not self.trade_merchants:
            return

        new_columns = self._calculate_trade_columns()
        if new_columns != self.trade_current_columns:
            if self.trade_resize_pending:
                return  # A rebuild is already scheduled; let it handle it
            self.trade_resize_pending = True
            self.after(100, self._do_trade_resize_rebuild)

    def _do_trade_resize_rebuild(self):
        """Perform the actual column rebuild after debounce delay."""
        self.trade_resize_pending = False
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

        # Round-robin distribution keeps columns roughly equal height
        for idx, merchant in enumerate(self.trade_merchants):
            col_idx = idx % num_columns
            self._create_merchant_section(merchant, column_frames[col_idx])

    # --- Merchant Section Widgets ---

    def _create_merchant_section(self, merchant, parent=None):
        """Create a collapsible section for a single merchant.

        Each section consists of a clickable header row (arrow + name + order
        count) and a hidden-by-default orders frame that is packed or
        forgotten according to ``merchant.expanded``.
        """
        if parent is None:
            parent = self.trade_scroll_frame

        # Container for the merchant section
        section_frame = ctk.CTkFrame(parent, fg_color=THEME_COLORS["bg_dropdown"])
        section_frame.pack(fill="x", pady=(0, PADDING["small"]))

        # Header row (clickable to expand/collapse)
        header_frame = ctk.CTkFrame(section_frame, fg_color="transparent")
        header_frame.pack(fill="x", padx=PADDING["small"], pady=PADDING["small"])

        # Expand/collapse arrow
        arrow_label = ctk.CTkLabel(
            header_frame,
            text="\u25bc" if merchant.expanded else "\u25b6",
            font=FONTS["body_bold"],
            text_color=THEME_COLORS["text"],
            width=20
        )
        arrow_label.pack(side="left")

        # Merchant name
        name_label = ctk.CTkLabel(
            header_frame,
            text=merchant.display_name,
            font=FONTS["heading"],
            text_color=THEME_COLORS["text"]
        )
        name_label.pack(side="left", padx=(5, 0))

        # Order count
        count_label = ctk.CTkLabel(
            header_frame,
            text=f"({len(merchant.orders)} orders)",
            font=FONTS["small_bold"],
            text_color=THEME_COLORS["text_secondary"]
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
        """Create a checkbox row with quantity spinbox for a single order.

        Layout per row:  [checkbox label] ............. [v] [qty] [^]
        The checkbox tracks whether the order is desired; the spinbox
        tracks how many units the player wants to buy/sell (0-9999).
        """
        # Container for the row
        row_frame = ctk.CTkFrame(parent, fg_color="transparent")
        row_frame.pack(fill="x", pady=2)

        # Checkbox
        var = ctk.BooleanVar(value=order.checked)
        checkbox = ctk.CTkCheckBox(
            row_frame,
            text=order.display_name,
            variable=var,
            font=FONTS["body_bold"],
            text_color=THEME_COLORS["text"],
            command=lambda: self._on_order_toggle(merchant, order, var.get())
        )
        checkbox.pack(side="left", anchor="w")

        # Quantity spinbox container (on the right)
        qty_frame = ctk.CTkFrame(row_frame, fg_color="transparent")
        qty_frame.pack(side="right", padx=(10, 0))

        # Down arrow button
        down_btn = ctk.CTkButton(
            qty_frame,
            text="\u25bc",
            width=20,
            height=20,
            font=("Segoe UI", 8),
            fg_color="transparent",
            hover_color=("gray80", "gray30"),
            command=lambda: self._on_quantity_change(merchant, order, qty_var, -1)
        )
        down_btn.pack(side="left")
        self._create_tooltip(down_btn, "Decrease quantity")

        # Quantity entry (4 digits, 0-9999)
        qty_var = ctk.StringVar(value=str(order.quantity))
        qty_entry = ctk.CTkEntry(
            qty_frame,
            textvariable=qty_var,
            width=45,
            height=22,
            font=FONTS["small"],
            justify="center"
        )
        qty_entry.pack(side="left", padx=2)
        qty_entry.bind("<FocusOut>", lambda e: self._on_quantity_entry(merchant, order, qty_var))
        qty_entry.bind("<Return>", lambda e: self._on_quantity_entry(merchant, order, qty_var))

        # Up arrow button
        up_btn = ctk.CTkButton(
            qty_frame,
            text="\u25b2",
            width=20,
            height=20,
            font=("Segoe UI", 8),
            fg_color="transparent",
            hover_color=("gray80", "gray30"),
            command=lambda: self._on_quantity_change(merchant, order, qty_var, 1)
        )
        up_btn.pack(side="left")
        self._create_tooltip(up_btn, "Increase quantity")

        self.trade_order_checkboxes[merchant.raw_name][order.raw_name] = {
            "checkbox": checkbox,
            "var": var,
            "qty_var": qty_var,
            "order": order
        }

    # --- Order & Quantity Event Handlers ---

    def _on_quantity_change(self, _merchant, order, qty_var, delta: int):
        """Handle quantity up/down button click, clamping to 0-9999."""
        try:
            current = int(qty_var.get())
        except ValueError:
            current = 0

        new_val = max(0, min(9999, current + delta))
        qty_var.set(str(new_val))
        order.quantity = new_val
        self._save_trade_config()

    def _on_quantity_entry(self, _merchant, order, qty_var):
        """Validate and apply a manually typed quantity on focus-out or Enter."""
        try:
            val = int(qty_var.get())
            val = max(0, min(9999, val))
        except ValueError:
            val = 0

        qty_var.set(str(val))
        order.quantity = val
        self._save_trade_config()

    # --- Expand / Collapse & Bulk Actions ---

    def _toggle_merchant_section(self, merchant):
        """Toggle the expanded/collapsed state of a merchant section."""
        merchant.expanded = not merchant.expanded

        frame_data = self.trade_merchant_frames.get(merchant.raw_name)
        if not frame_data:
            return

        arrow_label = frame_data["arrow"]
        orders_frame = frame_data["orders_frame"]

        if merchant.expanded:
            arrow_label.configure(text="\u25bc")
            orders_frame.pack(fill="x", padx=PADDING["medium"], pady=(0, PADDING["small"]))
        else:
            arrow_label.configure(text="\u25b6")
            orders_frame.pack_forget()

    def _on_order_toggle(self, _merchant, order, checked: bool):
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
                    frame_data["arrow"].configure(text="\u25bc")
                    frame_data["orders_frame"].pack(
                        fill="x", padx=PADDING["medium"],
                        pady=(0, PADDING["small"])
                    )

    def _trade_hide_all(self):
        """Collapse all merchant sections."""
        for merchant in self.trade_merchants:
            if merchant.expanded:
                merchant.expanded = False
                frame_data = self.trade_merchant_frames.get(merchant.raw_name)
                if frame_data:
                    frame_data["arrow"].configure(text="\u25b6")
                    frame_data["orders_frame"].pack_forget()

    def _trade_clear_all(self):
        """Clear all order checkmarks and quantities."""
        for merchant in self.trade_merchants:
            for order in merchant.orders:
                order.checked = False
                order.quantity = 0
            # Update UI checkboxes and quantities
            merchant_checkboxes = self.trade_order_checkboxes.get(merchant.raw_name, {})
            for order_data in merchant_checkboxes.values():
                order_data["var"].set(False)
                if "qty_var" in order_data:
                    order_data["qty_var"].set("0")
        # Save state
        self._save_trade_config()

    # --- Config Persistence (XML) ---

    def _save_trade_config(self):
        """Save trade manager checkbox and quantity state to XML file.

        Only orders that are checked or have a non-zero quantity are written,
        keeping the file compact.  The XML is pretty-printed for readability.
        """
        import xml.etree.ElementTree as ET
        from xml.dom import minidom
        from ..config.paths import GamePaths

        GamePaths.ensure_config_dir()

        root = ET.Element("TradeManager", version="1.1")

        for merchant in self.trade_merchants:
            merchant_elem = ET.SubElement(root, "Merchant", name=merchant.raw_name)
            for order in merchant.orders:
                # Save order if checked or has a quantity > 0
                if order.checked or order.quantity > 0:
                    ET.SubElement(
                        merchant_elem, "Order",
                        name=order.raw_name,
                        checked="true" if order.checked else "false",
                        quantity=str(order.quantity)
                    )

        # minidom adds a blank XML declaration line; strip empty lines to
        # keep the output tidy while retaining indentation
        raw_xml = ET.tostring(root, encoding="unicode")
        xml_str = minidom.parseString(raw_xml).toprettyxml(
            indent="  "
        )
        lines = [line for line in xml_str.split('\n') if line.strip()]
        xml_str = '\n'.join(lines)

        GamePaths.TRADE_CONFIG_FILE.write_text(xml_str, encoding="utf-8")

    def _load_trade_config(self):
        """Load trade manager checkbox and quantity state from XML file.

        Builds a fast lookup dict of (merchant_name, order_name) -> (checked,
        quantity) and applies it to the in-memory merchant/order objects.
        Merchants with at least one checked order are auto-expanded.  If the
        config file is missing or corrupt, all orders default to unchecked / 0.
        """
        import xml.etree.ElementTree as ET
        from ..config.paths import GamePaths

        if not GamePaths.TRADE_CONFIG_FILE.exists():
            return

        try:
            tree = ET.parse(GamePaths.TRADE_CONFIG_FILE)
            root = tree.getroot()

            # Flat lookup avoids nested iteration when applying to merchants
            order_data = {}
            for merchant_elem in root.findall("Merchant"):
                merchant_name = merchant_elem.get("name", "")
                for order_elem in merchant_elem.findall("Order"):
                    order_name = order_elem.get("name", "")
                    checked = order_elem.get("checked", "").lower() == "true"
                    try:
                        quantity = int(order_elem.get("quantity", "0"))
                    except ValueError:
                        quantity = 0
                    order_data[(merchant_name, order_name)] = (checked, quantity)

            # Apply to current merchants
            for merchant in self.trade_merchants:
                has_checked = False
                for order in merchant.orders:
                    key = (merchant.raw_name, order.raw_name)
                    if key in order_data:
                        order.checked, order.quantity = order_data[key]
                        if order.checked:
                            has_checked = True
                    else:
                        order.checked = False
                        order.quantity = 0
                # Expand merchant only if it has at least one checked order
                merchant.expanded = has_checked

        except (OSError, ET.ParseError, KeyError) as e:
            # If file is corrupted, just continue with defaults
            logger.debug("Could not load trade config: %s", e)

    # --- UI State Helpers ---

    def _reset_trade_expanded_state(self):
        """Reset merchant expanded state so only merchants with checked orders are open.

        Called after external state changes (e.g., Clear All) to keep the
        visual state consistent with the underlying data model.
        """
        for merchant in self.trade_merchants:
            # Check if any order is checked
            has_checked = any(order.checked for order in merchant.orders)
            merchant.expanded = has_checked

            # Update UI if frame exists
            frame_data = self.trade_merchant_frames.get(merchant.raw_name)
            if frame_data:
                arrow_label = frame_data["arrow"]
                orders_frame = frame_data["orders_frame"]

                if merchant.expanded:
                    arrow_label.configure(text="\u25bc")
                    orders_frame.pack(fill="x", padx=PADDING["medium"], pady=(0, PADDING["small"]))
                else:
                    arrow_label.configure(text="\u25b6")
                    orders_frame.pack_forget()
