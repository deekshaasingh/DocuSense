"""Step 6: the arithmetic and format rules must catch deliberately broken data."""
from datetime import date, timedelta

from schemas import Invoice, LineItem
from pipeline.validate import check


def _good() -> Invoice:
    items = [LineItem(description="Paper", quantity=2, unit_price=100.0, amount=200.0)]
    return Invoice(
        invoice_number="INV-1",
        invoice_date=date(2025, 5, 1),
        vendor_name="Acme",
        vendor_gstin="07ABCDE1234F1Z5",
        subtotal=200.0,
        tax_amount=36.0,
        total_amount=236.0,
        line_items=items,
    )


def test_clean_invoice_has_no_problems():
    assert check(_good()) == []


def test_line_items_not_summing_is_caught():
    inv = _good()
    inv.line_items[0].amount = 150.0
    assert "line items do not add up to subtotal" in check(inv)


def test_total_mismatch_is_caught():
    inv = _good()
    inv.total_amount = 999.0
    assert "subtotal + tax does not equal total" in check(inv)


def test_future_date_is_caught():
    inv = _good()
    inv.invoice_date = date.today() + timedelta(days=5)
    assert "date is in the future" in check(inv)


def test_bad_gstin_is_caught():
    inv = _good()
    inv.vendor_gstin = "NOTAGSTIN"
    assert "GSTIN format is wrong" in check(inv)


def test_tolerance_allows_rounding_noise():
    inv = _good()
    inv.total_amount = 236.01  # within the 0.02 tolerance
    assert "subtotal + tax does not equal total" not in check(inv)
