"""Tests for moria_manager.core.trade_data module."""

import pytest

from moria_manager.core.trade_data import Merchant, Order, load_merchants


class TestOrder:
    """Tests for Order dataclass."""

    def test_defaults(self):
        order = Order(raw_name="Test_Order", display_name="Test")
        assert order.checked is False
        assert order.quantity == 0

    def test_with_values(self):
        order = Order(raw_name="Test_Order", display_name="Test", checked=True, quantity=5)
        assert order.checked is True
        assert order.quantity == 5


class TestMerchant:
    """Tests for Merchant dataclass."""

    def test_defaults(self):
        merchant = Merchant(raw_name="TestMerchant", display_name="Test", orders=[])
        assert merchant.expanded is False
        assert merchant.orders == []


class TestLoadMerchants:
    """Tests for load_merchants()."""

    def test_returns_non_empty_list(self):
        merchants = load_merchants()
        assert isinstance(merchants, list)
        assert len(merchants) > 0

    def test_all_items_are_merchants(self):
        merchants = load_merchants()
        for m in merchants:
            assert isinstance(m, Merchant)

    def test_merchants_have_required_fields(self):
        merchants = load_merchants()
        for m in merchants:
            assert m.raw_name
            assert m.display_name
            assert isinstance(m.orders, list)
            assert len(m.orders) > 0

    def test_orders_are_order_instances(self):
        merchants = load_merchants()
        for m in merchants:
            for order in m.orders:
                assert isinstance(order, Order)
                assert order.raw_name
                assert order.display_name

    def test_no_duplicate_merchant_raw_names(self):
        merchants = load_merchants()
        raw_names = [m.raw_name for m in merchants]
        assert len(raw_names) == len(set(raw_names))

    def test_known_merchant_exists(self):
        merchants = load_merchants()
        names = {m.display_name for m in merchants}
        assert "Arnor" in names

    def test_orders_default_unchecked(self):
        merchants = load_merchants()
        for m in merchants:
            for order in m.orders:
                assert order.checked is False

    def test_merchants_default_collapsed(self):
        merchants = load_merchants()
        for m in merchants:
            assert m.expanded is False

    def test_no_empty_display_names(self):
        merchants = load_merchants()
        for m in merchants:
            assert m.display_name.strip() != ""
            for order in m.orders:
                assert order.display_name.strip() != ""
