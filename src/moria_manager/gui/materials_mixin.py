"""Materials Calculator mixin providing crafting materials UI for MainWindow."""

from __future__ import annotations

import customtkinter as ctk

from ..core.recipes_data_embedded import get_recipes_data
from ..logging_config import get_logger
from .styles import FONTS, PADDING

logger = get_logger("materials_mixin")


# pylint: disable=too-many-instance-attributes,too-few-public-methods
class MaterialsMixin:
    """Mixin providing the Materials Calculator tab for MainWindow.

    The Materials Calculator displays craftable weapons and armor with
    checkboxes to select items. Based on selections, it calculates the
    total materials needed for crafting.

    Features:
        - Two-column layout with Weapons and Armor lists
        - Checkboxes for each item
        - Dwarf count dropdown (1-8)
        - Game type dropdown (Campaign/Sandbox) - filters items by available recipes
        - Green "Gather" button to calculate total materials
        - Alphabetically sorted items

    Expected attributes provided by the host MainWindow:
        content_frame   -- Parent frame for mode panes
        _create_tooltip() -- Tooltip helper for icon buttons
    """

    # --- Pane Initialization ---

    def _create_materials_pane(self):
        """Create the materials calculator pane container."""
        self.materials_pane = ctk.CTkFrame(self.content_frame, fg_color=("#3d3d3d", "#1a1a1a"))
        # Don't grid initially - only shown in materials mode

        # Store data and UI references
        self.materials_weapons: list = []
        self.materials_armor: list = []
        self.materials_weapon_checkboxes: dict = {}
        self.materials_armor_checkboxes: dict = {}
        self.materials_weapon_widgets: list = []  # Store checkbox widgets for clearing
        self.materials_armor_widgets: list = []  # Store checkbox widgets for clearing
        self.materials_initialized: bool = False

    # pylint: disable=too-many-locals,too-many-statements
    def _initialize_materials_ui(self):
        """Initialize the materials calculator UI (called on first use for lazy loading)."""
        if self.materials_initialized:
            return

        self.materials_initialized = True

        # Load recipe data
        self._load_recipes_data()

        # Header with title
        header_frame = ctk.CTkFrame(self.materials_pane, fg_color="transparent")
        header_frame.pack(fill="x", padx=PADDING["small"], pady=PADDING["small"])

        header_label = ctk.CTkLabel(
            header_frame, text="Materials Calculator", font=FONTS["heading"]
        )
        header_label.pack(side="left")

        # Options row: Dwarves and Game Type
        options_frame = ctk.CTkFrame(self.materials_pane, fg_color="transparent")
        options_frame.pack(fill="x", padx=PADDING["medium"], pady=(0, PADDING["small"]))

        # Dwarves dropdown
        dwarves_label = ctk.CTkLabel(options_frame, text="Dwarves:", font=FONTS["body"])
        dwarves_label.pack(side="left", padx=(0, 5))

        self.materials_dwarves_var = ctk.StringVar(value="1")
        dwarves_dropdown = ctk.CTkOptionMenu(
            options_frame,
            values=["1", "2", "3", "4", "5", "6", "7", "8"],
            variable=self.materials_dwarves_var,
            width=60,
            height=28,
            font=FONTS["body"]
        )
        dwarves_dropdown.pack(side="left", padx=(0, 20))

        # Game Type dropdown
        game_type_label = ctk.CTkLabel(options_frame, text="Game Type:", font=FONTS["body"])
        game_type_label.pack(side="left", padx=(0, 5))

        self.materials_game_type_var = ctk.StringVar(value="Campaign")
        game_type_dropdown = ctk.CTkOptionMenu(
            options_frame,
            values=["Campaign", "Sandbox"],
            variable=self.materials_game_type_var,
            width=100,
            height=28,
            font=FONTS["body"],
            command=self._on_game_type_changed
        )
        game_type_dropdown.pack(side="left", padx=(0, 20))

        # Gather button (green with white text)
        gather_btn = ctk.CTkButton(
            options_frame,
            text="Gather",
            width=80,
            height=28,
            font=FONTS["body"],
            fg_color="#28a745",
            hover_color="#218838",
            text_color="white",
            command=self._on_gather_materials
        )
        gather_btn.pack(side="left")

        # Separator line
        separator = ctk.CTkFrame(self.materials_pane, height=2, fg_color=("gray60", "gray40"))
        separator.pack(fill="x", padx=PADDING["medium"], pady=PADDING["small"])

        # Three-column container
        columns_frame = ctk.CTkFrame(self.materials_pane, fg_color="transparent")
        columns_frame.pack(fill="both", expand=True, padx=PADDING["small"], pady=PADDING["small"])
        columns_frame.grid_columnconfigure(0, weight=1)
        columns_frame.grid_columnconfigure(1, weight=1)
        columns_frame.grid_columnconfigure(2, weight=1)
        columns_frame.grid_rowconfigure(0, weight=1)

        # Left column: Weapons
        weapons_frame = ctk.CTkFrame(columns_frame, fg_color=("#4a4a4a", "#252525"))
        weapons_frame.grid(row=0, column=0, sticky="nsew", padx=(0, PADDING["small"]))

        weapons_header = ctk.CTkLabel(weapons_frame, text="Weapons", font=FONTS["heading"])
        weapons_header.pack(pady=PADDING["small"])

        # Scrollable frame for weapons
        self.weapons_scroll = ctk.CTkScrollableFrame(
            weapons_frame,
            fg_color="transparent",
            scrollbar_button_color=("gray50", "gray60"),
            scrollbar_button_hover_color=("gray40", "gray50")
        )
        self.weapons_scroll.pack(
            fill="both", expand=True,
            padx=PADDING["small"], pady=(0, PADDING["small"])
        )

        # Middle column: Armor
        armor_frame = ctk.CTkFrame(columns_frame, fg_color=("#4a4a4a", "#252525"))
        armor_frame.grid(row=0, column=1, sticky="nsew", padx=PADDING["small"])

        armor_header = ctk.CTkLabel(armor_frame, text="Armor", font=FONTS["heading"])
        armor_header.pack(pady=PADDING["small"])

        # Scrollable frame for armor
        self.armor_scroll = ctk.CTkScrollableFrame(
            armor_frame,
            fg_color="transparent",
            scrollbar_button_color=("gray50", "gray60"),
            scrollbar_button_hover_color=("gray40", "gray50")
        )
        self.armor_scroll.pack(
            fill="both", expand=True,
            padx=PADDING["small"], pady=(0, PADDING["small"])
        )

        # Right column: Materials
        materials_frame = ctk.CTkFrame(columns_frame, fg_color=("#4a4a4a", "#252525"))
        materials_frame.grid(row=0, column=2, sticky="nsew", padx=(PADDING["small"], 0))

        materials_header = ctk.CTkLabel(
            materials_frame, text="Materials Needed", font=FONTS["heading"]
        )
        materials_header.pack(pady=PADDING["small"])

        # Scrollable frame for materials results
        self.materials_results_scroll = ctk.CTkScrollableFrame(
            materials_frame,
            fg_color="transparent",
            scrollbar_button_color=("gray50", "gray60"),
            scrollbar_button_hover_color=("gray40", "gray50")
        )
        self.materials_results_scroll.pack(
            fill="both", expand=True,
            padx=PADDING["small"], pady=(0, PADDING["small"])
        )

        # Label to show results (will be updated by Gather)
        self.materials_results_label = ctk.CTkLabel(
            self.materials_results_scroll,
            text="Select items and click Gather",
            font=("Segoe UI", 16),
            justify="left",
            anchor="nw"
        )
        self.materials_results_label.pack(anchor="nw", fill="x")

        # Populate the lists
        self._populate_weapons_list()
        self._populate_armor_list()

    def _load_recipes_data(self):
        """Load weapon and armor recipes from embedded data."""
        data = get_recipes_data()
        self.materials_weapons = data.get("weapons", [])
        self.materials_armor = data.get("armor", [])
        logger.info(
            "Loaded %d weapons and %d armor pieces",
            len(self.materials_weapons),
            len(self.materials_armor),
        )

    def _populate_weapons_list(self):
        """Populate the weapons list with checkboxes based on game type."""
        # Clear existing widgets
        for widget in self.materials_weapon_widgets:
            widget.destroy()
        self.materials_weapon_widgets.clear()
        self.materials_weapon_checkboxes.clear()

        game_type = self.materials_game_type_var.get().lower()
        materials_key = "default_materials" if game_type == "campaign" else "sandbox_materials"

        # Filter weapons - only show items with recipes for this game type
        filtered_weapons = [
            w for w in self.materials_weapons
            if w.get(materials_key) and len(w.get(materials_key, [])) > 0
        ]

        # Deduplicate by display_name - group all variants together
        weapons_by_name: dict[str, list] = {}
        for weapon in filtered_weapons:
            display_name = weapon.get("display_name", "Unknown")
            if display_name not in weapons_by_name:
                weapons_by_name[display_name] = []
            weapons_by_name[display_name].append(weapon)

        # Sort by display name
        sorted_names = sorted(weapons_by_name.keys(), key=str.lower)

        for display_name in sorted_names:
            variants = weapons_by_name[display_name]

            # Create checkbox variable
            var = ctk.BooleanVar(value=False)
            self.materials_weapon_checkboxes[display_name] = {
                "var": var,
                "variants": variants  # Store all variants
            }

            # Create checkbox with 16pt font
            checkbox = ctk.CTkCheckBox(
                self.weapons_scroll,
                text=display_name,
                font=("Segoe UI", 16),
                variable=var,
                hover_color=("gray70", "gray40"),
                fg_color=("#5dade2", "#3498db"),
                text_color=("gray10", "gray90")
            )
            checkbox.pack(anchor="w", pady=2)
            self.materials_weapon_widgets.append(checkbox)

    def _populate_armor_list(self):
        """Populate the armor list with checkboxes based on game type."""
        # Clear existing widgets
        for widget in self.materials_armor_widgets:
            widget.destroy()
        self.materials_armor_widgets.clear()
        self.materials_armor_checkboxes.clear()

        game_type = self.materials_game_type_var.get().lower()
        materials_key = "default_materials" if game_type == "campaign" else "sandbox_materials"

        # Filter armor - only show items with recipes for this game type
        filtered_armor = [
            a for a in self.materials_armor
            if a.get(materials_key) and len(a.get(materials_key, [])) > 0
        ]

        # Deduplicate by display_name - group all variants together
        armor_by_name: dict[str, list] = {}
        for armor in filtered_armor:
            display_name = armor.get("display_name", "Unknown")
            if display_name not in armor_by_name:
                armor_by_name[display_name] = []
            armor_by_name[display_name].append(armor)

        # Sort by display name
        sorted_names = sorted(armor_by_name.keys(), key=str.lower)

        for display_name in sorted_names:
            variants = armor_by_name[display_name]

            # Create checkbox variable
            var = ctk.BooleanVar(value=False)
            self.materials_armor_checkboxes[display_name] = {
                "var": var,
                "variants": variants  # Store all variants
            }

            # Create checkbox with 16pt font
            checkbox = ctk.CTkCheckBox(
                self.armor_scroll,
                text=display_name,
                font=("Segoe UI", 16),
                variable=var,
                hover_color=("gray70", "gray40"),
                fg_color=("#5dade2", "#3498db"),
                text_color=("gray10", "gray90")
            )
            checkbox.pack(anchor="w", pady=2)
            self.materials_armor_widgets.append(checkbox)

    def _on_game_type_changed(self, _value=None):
        """Handle changes to game type - repopulate lists with filtered items."""
        self._populate_weapons_list()
        self._populate_armor_list()
        # Clear results when game type changes
        self._clear_results()

    def _on_gather_materials(self):
        """Handle Gather button click - calculate and display total materials."""
        self._calculate_materials()

    def _clear_results(self):
        """Clear the results display."""
        self.materials_results_label.configure(text="Select items and click Gather")

    def _calculate_materials(self):
        """Calculate total materials needed for selected items and display results."""
        dwarves = int(self.materials_dwarves_var.get())
        game_type = self.materials_game_type_var.get().lower()

        # Determine which materials list to use
        materials_key = "default_materials" if game_type == "campaign" else "sandbox_materials"

        # Collect all materials from all variants of selected items
        total_materials: dict[str, int] = {}

        # Process weapons - sum materials from ALL variants of each selected weapon
        for _, checkbox_data in self.materials_weapon_checkboxes.items():
            if checkbox_data["var"].get():
                for variant in checkbox_data["variants"]:
                    materials = variant.get(materials_key, [])
                    for mat in materials:
                        mat_name = mat.get("display", mat.get("internal", "Unknown"))
                        quantity = mat.get("quantity", 0) * dwarves
                        total_materials[mat_name] = total_materials.get(mat_name, 0) + quantity

        # Process armor - sum materials from ALL variants of each selected armor
        for _, checkbox_data in self.materials_armor_checkboxes.items():
            if checkbox_data["var"].get():
                for variant in checkbox_data["variants"]:
                    materials = variant.get(materials_key, [])
                    for mat in materials:
                        mat_name = mat.get("display", mat.get("internal", "Unknown"))
                        quantity = mat.get("quantity", 0) * dwarves
                        total_materials[mat_name] = total_materials.get(mat_name, 0) + quantity

        # Display results in label
        if total_materials:
            # Sort materials alphabetically and format output
            sorted_materials = sorted(total_materials.items(), key=lambda x: x[0].lower())
            result_lines = [f"{name}: {qty}" for name, qty in sorted_materials]
            self.materials_results_label.configure(text="\n".join(result_lines))
        else:
            self.materials_results_label.configure(text="Select items and click Gather")
