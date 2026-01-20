"""Trade data parser for DT_OrderDecks.json"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class Order:
    """A single order/item that a merchant wants to buy."""
    raw_name: str  # e.g., "CarvedMuralSections_Order_Default"
    display_name: str  # e.g., "Carved Mural Sections"
    checked: bool = False
    quantity: int = 0  # Quantity field (0-99)


@dataclass
class Merchant:
    """A merchant with their list of orders."""
    raw_name: str  # e.g., "ArnorOrders_Default"
    display_name: str  # e.g., "Arnor"
    orders: list[Order]
    expanded: bool = False  # Default collapsed, expand only if has checked orders


def parse_order_name(raw_name: str) -> str:
    """Convert raw order name to display name.

    e.g., "CarvedMuralSections_Order_Default" -> "Carved Mural Sections"
    """
    # Remove "_Order_Default" suffix
    name = raw_name.replace("_Order_Default", "")

    # Split on capital letters and join with spaces
    result = []
    for char in name:
        if char.isupper() and result:
            result.append(' ')
        result.append(char)

    return ''.join(result)


def parse_merchant_name(raw_name: str) -> str:
    """Convert raw merchant name to display name.

    e.g., "ArnorOrders_Default" -> "Arnor"
    e.g., "BlueMountainOrders_Default" -> "Blue Mountain"
    """
    # Remove "Orders_Default" suffix
    name = raw_name.replace("Orders_Default", "")

    # Split on capital letters and join with spaces
    result = []
    for char in name:
        if char.isupper() and result:
            result.append(' ')
        result.append(char)

    return ''.join(result).strip()


def load_order_decks(json_path: Path) -> list[Merchant]:
    """Load and parse the DT_OrderDecks.json file.

    Args:
        json_path: Path to the DT_OrderDecks.json file

    Returns:
        List of Merchant objects with their orders
    """
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    merchants = []

    # Navigate to the Exports section where the data tables are
    exports = data.get("Exports", [])

    for export in exports:
        # Look for the Table property which contains the Data array
        table = export.get("Table", {})
        if isinstance(table, dict):
            rows = table.get("Data", [])
        else:
            rows = []

        for row in rows:
            # Each row is a merchant
            row_name = row.get("Name", "")

            # Skip if not an Orders entry
            if not row_name.endswith("Orders_Default"):
                continue

            # Get the Value array which contains the properties
            value_array = row.get("Value", [])

            orders = []

            # Find the Orders array property
            for prop in value_array:
                if prop.get("Name") == "Orders":
                    # This is the orders array
                    orders_data = prop.get("Value", [])

                    for order_entry in orders_data:
                        # Each order entry has a Value array with RowName
                        order_values = order_entry.get("Value", [])

                        for order_prop in order_values:
                            if order_prop.get("Name") == "RowName":
                                order_raw_name = order_prop.get("Value", "")
                                if order_raw_name:
                                    orders.append(Order(
                                        raw_name=order_raw_name,
                                        display_name=parse_order_name(order_raw_name)
                                    ))
                    break

            if orders:
                merchants.append(Merchant(
                    raw_name=row_name,
                    display_name=parse_merchant_name(row_name),
                    orders=orders
                ))

    # Sort merchants alphabetically by display name
    merchants.sort(key=lambda m: m.display_name)

    return merchants


def get_default_order_decks_path() -> Optional[Path]:
    """Get the default path to DT_OrderDecks.json in the gamesource directory.

    Works in both development mode and when packaged with PyInstaller.
    """
    import sys

    if getattr(sys, 'frozen', False):
        # Running as compiled executable (PyInstaller)
        gamesource_path = Path(sys._MEIPASS) / "gamesource" / "DT_OrderDecks.json"
    else:
        # Running in development - look relative to package
        import moria_manager
        package_dir = Path(moria_manager.__file__).parent.parent.parent
        gamesource_path = package_dir / "gamesource" / "DT_OrderDecks.json"

    if gamesource_path.exists():
        return gamesource_path

    return None
