"""Trade data module with embedded merchant/order data.

The trade data is pre-parsed and embedded in trade_data_embedded.py,
eliminating the need for the DT_OrderDecks.json file at runtime.
"""

from dataclasses import dataclass

from .trade_data_embedded import MERCHANTS_DATA


@dataclass
class Order:
    """A single order/item that a merchant wants to buy."""
    raw_name: str  # e.g., "CarvedMuralSections_Order_Default"
    display_name: str  # e.g., "Carved Mural Sections"
    checked: bool = False
    quantity: int = 0  # Quantity field (0-9999)


@dataclass
class Merchant:
    """A merchant with their list of orders."""
    raw_name: str  # e.g., "ArnorOrders_Default"
    display_name: str  # e.g., "Arnor"
    orders: list[Order]
    expanded: bool = False  # Default collapsed, expand only if has checked orders


def load_merchants() -> list[Merchant]:
    """Load the embedded merchant and order data.

    Returns:
        List of Merchant objects with their orders
    """
    merchants = []

    for raw_name, display_name, orders_data in MERCHANTS_DATA:
        orders = [
            Order(raw_name=order_raw, display_name=order_display)
            for order_raw, order_display in orders_data
        ]
        merchants.append(Merchant(
            raw_name=raw_name,
            display_name=display_name,
            orders=orders
        ))

    return merchants
