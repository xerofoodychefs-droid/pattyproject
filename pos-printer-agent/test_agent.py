"""
Automated Test Suite for NetumScan NS-8360LW POS Print Agent
"""

import unittest
from agent import (
    build_escpos_receipt, wrap_text, format_row, LINE_WIDTH,
    PARTIAL_CUT, INIT, print_raw_bytes_winspool
)

class TestPosPrintAgent(unittest.TestCase):
    def test_line_width_is_48_columns(self):
        self.assertEqual(LINE_WIDTH, 48)

    def test_text_wrapping(self):
        long_text = "The Double Bacon Avocado Smash Burger with Truffle Mayo and Extra Crispy Shallots"
        wrapped = wrap_text(long_text, 30)
        for line in wrapped:
            self.assertLessEqual(len(line), 30)
        self.assertEqual(" ".join(wrapped), long_text)

    def test_format_row_alignment(self):
        left = "1  The Classic Smash"
        right = "£12.50"
        row = format_row(left, right, LINE_WIDTH)
        self.assertEqual(len(row), LINE_WIDTH)
        self.assertTrue(row.startswith("1  The Classic Smash"))
        self.assertTrue(row.endswith("£12.50"))

    def test_short_order_escpos_generation(self):
        order = {
            "order_number": "PP1001",
            "order_type": "COLLECTION",
            "customer_name": "Alice Smith",
            "customer_phone": "+447700900111",
            "subtotal": 8.99,
            "discount_amount": 0.0,
            "total_amount": 8.99,
            "vat_amount": 1.50,
            "items": [
                {
                    "quantity": 1,
                    "product_name": "Classic Burger",
                    "total_price": 8.99
                }
            ]
        }
        raw_bytes = build_escpos_receipt(order)
        self.assertTrue(raw_bytes.startswith(INIT))
        self.assertTrue(raw_bytes.endswith(PARTIAL_CUT))
        self.assertIn(b"PATTY PROJECT", raw_bytes)
        self.assertIn(b"PP1001", raw_bytes)
        self.assertIn(b"Alice Smith", raw_bytes)
        self.assertIn(b"Classic Burger", raw_bytes)
        self.assertIn(b"VAT NO: 525 5772 74", raw_bytes)

    def test_long_delivery_order_with_modifiers(self):
        order = {
            "order_number": "PP4775",
            "order_type": "DELIVERY",
            "customer_name": "Tamanna Rahman",
            "customer_phone": "+44 7417 521128",
            "delivery_address": {
                "address_line1": "Flat 4B, St. Paul's Court",
                "address_line2": "Church Street, Edmonton",
                "city": "London",
                "postcode": "N9 9HF",
                "country": "United Kingdom"
            },
            "subtotal": 34.50,
            "discount_amount": 3.45,
            "coupon_code": "SAVE10",
            "total_amount": 31.05,
            "vat_amount": 5.18,
            "items": [
                {
                    "quantity": 2,
                    "product_name": "The Double Smash Special Burger",
                    "total_price": 22.00,
                    "selected_options": {
                        "addons": [{"label": "Extra Cheddar", "price": 1.50}, {"label": "Bacon Jam", "price": 2.00}],
                        "removals": [{"label": "No Onions"}, {"label": "No Mustard"}],
                        "selections": [{"label": "Well Done"}]
                    }
                },
                {
                    "quantity": 2,
                    "product_name": "Rosemary Salt Loaded Fries",
                    "total_price": 9.00
                },
                {
                    "quantity": 1,
                    "product_name": "Vanilla Bean Thick Shake",
                    "total_price": 3.50
                }
            ]
        }
        raw_bytes = build_escpos_receipt(order)
        self.assertTrue(raw_bytes.startswith(INIT))
        self.assertTrue(raw_bytes.endswith(PARTIAL_CUT))
        self.assertIn(b"DELIVERY", raw_bytes)
        self.assertIn(b"Flat 4B, St. Paul's Court", raw_bytes)
        self.assertIn(b"N9 9HF", raw_bytes)
        self.assertIn(b"Extra Cheddar", raw_bytes)
        self.assertIn(b"No Onions", raw_bytes)
        self.assertIn(b"SAVE10", raw_bytes)

    def test_pound_encoding_and_formatting(self):
        order = {
            "order_number": "PP2002",
            "subtotal": 15.50,
            "total_amount": 15.50,
            "vat_amount": 2.58,
            "items": [{"quantity": 1, "product_name": "Truffle Burger", "total_price": 15.50}]
        }
        raw_bytes = build_escpos_receipt(order)
        # Latin-1 encoded pound symbol £
        self.assertIn(b"\xa315.50", raw_bytes)

    def test_winspool_callable(self):
        # Verify winspool entry point is callable and returns boolean
        res = print_raw_bytes_winspool("TestNonExistentPrinter", b"TEST RAW BYTES")
        self.assertIsInstance(res, bool)

if __name__ == '__main__':
    unittest.main()
