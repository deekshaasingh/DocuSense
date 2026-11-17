"""Step 5: the local OCR extractor runs against a real rendered image."""
import cv2
import numpy as np
from PIL import Image, ImageDraw

import pytest

from pipeline.extract import extract_local_ocr, merge_pages, find_invoice_number
from pipeline.extract import _DATE_RE, _MONEY_RE
from textfont import load_font
from schemas import Invoice, LineItem
from datetime import date


def _font(size):
    """A readable font on any platform, see backend/textfont.py."""
    return load_font(size)


def _render() -> np.ndarray:
    img = Image.new("RGB", (1000, 700), "white")
    d = ImageDraw.Draw(img)
    f = _font(26)
    d.text((60, 50), "Northwind Supplies", font=f, fill="black")
    d.text((60, 100), "GSTIN: 07ABCDE1234F1Z5", font=f, fill="black")
    d.text((60, 150), "Invoice No: INV-9001", font=f, fill="black")
    d.text((60, 200), "Date: 2025-06-15", font=f, fill="black")
    d.text((60, 300), "Subtotal 1000.00", font=f, fill="black")
    d.text((60, 350), "Tax 180.00", font=f, fill="black")
    d.text((60, 400), "Total 1180.00", font=f, fill="black")
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def test_extractor_returns_a_valid_invoice_and_confidences():
    invoice, confs = extract_local_ocr(_render())
    assert isinstance(invoice, Invoice)
    assert confs and all(c <= 0 for c in confs)  # log space


def test_extractor_reads_the_obvious_fields():
    """End to end OCR check.

    Tesseract versions differ between platforms and occasionally misread a
    label, so this asserts the values the parser is responsible for rather
    than demanding a perfect character-level read of every word. The parsing
    rules themselves are pinned deterministically in the tests below, which
    do not involve OCR at all.
    """
    invoice, _ = extract_local_ocr(_render())
    # A number was found rather than defaulted
    assert invoice.invoice_number != "UNKNOWN"
    # A date was read off the page rather than falling back to today
    assert invoice.invoice_date.year == 2025
    # Money was found and is in the right order of magnitude. An exact
    # amount is not asserted, because a single digit misread by a different
    # Tesseract build would fail a test that has nothing to do with our code.
    assert 100.0 < invoice.total_amount < 10000.0
    assert invoice.subtotal > 0


def test_total_does_not_capture_the_subtotal_line():
    """Regression guard for the substring bug in docs/failures.md."""
    invoice, _ = extract_local_ocr(_render())
    assert abs(invoice.total_amount - invoice.subtotal) > 0.02


def _inv(number, total, items):
    return Invoice(
        invoice_number=number, invoice_date=date(2025, 1, 1), vendor_name="Acme",
        vendor_gstin=None, subtotal=total, tax_amount=0.0, total_amount=total,
        line_items=items,
    )


def test_merge_pages_takes_header_from_first_and_totals_from_last():
    page1 = _inv("INV-1", 0.0, [LineItem(description="A", quantity=1, unit_price=10, amount=10)])
    page2 = _inv("UNKNOWN", 500.0, [LineItem(description="B", quantity=1, unit_price=20, amount=20)])
    merged, confs = merge_pages([(page1, [-0.1]), (page2, [-0.2])])
    assert merged.invoice_number == "INV-1"       # header from page one
    assert merged.total_amount == 500.0            # totals from the last page
    assert [i.description for i in merged.line_items] == ["A", "B"]
    assert confs == [-0.1, -0.2]                   # certainties pooled


def test_merge_pages_is_identity_for_single_page():
    page = _inv("INV-7", 100.0, [LineItem(description="A", quantity=1, unit_price=100, amount=100)])
    merged, confs = merge_pages([(page, [-0.5])])
    assert merged.invoice_number == "INV-7" and confs == [-0.5]


# ---------------------------------------------------------------------------
# Deterministic parser tests. No OCR, so these behave identically on every
# machine and are where the parsing rules are actually pinned down.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("Invoice No: INV-9001", "INV-9001"),
    ("Invoice #: INV-9001", "INV-9001"),
    ("Invoice Number INV-9001", "INV-9001"),
    ("INV-9001", "INV-9001"),            # bare code, prefix must survive
    ("INV 9001", "INV-9001"),            # separator normalised
    ("Invoice No: AB/2025/41", "AB/2025/41"),
])
def test_invoice_number_is_parsed(text, expected):
    assert find_invoice_number(text) == expected


@pytest.mark.parametrize("text", [
    "Invoice Ne: INV-9001",              # the "No" label misread
    "Invoice N0: INV-9001",
    "lnvoice No: INV-9001",              # leading letter misread
])
def test_invoice_number_survives_a_misread_label(text):
    """Regression guard for docs/failures.md section 10.

    The old pattern matched "Inv" inside the word "Invoice" and returned
    "oice" whenever the label next to it was misread.
    """
    assert find_invoice_number(text) == "INV-9001"


@pytest.mark.parametrize("text", [
    "Invoice",
    "no invoice here at all",            # prose must not yield a number
    "",
])
def test_invoice_number_absent_is_unknown(text):
    assert find_invoice_number(text) == "UNKNOWN"


@pytest.mark.parametrize("text,expected", [
    ("Date: 2025-06-15", "2025-06-15"),
    ("Invoice date 1999-01-02 printed", "1999-01-02"),
])
def test_date_pattern(text, expected):
    m = _DATE_RE.search(text)
    assert m and m.group(0) == expected


@pytest.mark.parametrize("text", ["Date: 15/06/2025", "no date here", ""])
def test_date_pattern_ignores_other_formats(text):
    assert _DATE_RE.search(text) is None


@pytest.mark.parametrize("text,expected", [
    ("Total 1180.00", ["1180.00"]),
    ("Subtotal 1,000.00 Tax 180.00", ["1,000.00", "180.00"]),
    ("Qty 5 Rate 677.97 Amount 3389.85", ["677.97", "3389.85"]),
])
def test_money_pattern(text, expected):
    assert _MONEY_RE.findall(text) == expected
