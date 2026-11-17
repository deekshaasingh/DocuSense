"""
Step 6 of the Build Manual: catch errors using arithmetic and format rules,
not AI. The model can produce valid JSON that is still wrong -- rules catch
a surprising amount of it.
"""
import re
from datetime import date

from schemas import Invoice

_GSTIN_RE = re.compile(r"\d{2}[A-Z]{5}\d{4}[A-Z]\d[A-Z\d]{2}")


def check(inv: Invoice) -> list[str]:
    problems = []
    if abs(sum(i.amount for i in inv.line_items) - inv.subtotal) > 0.02:
        problems.append("line items do not add up to subtotal")
    if abs(inv.subtotal + inv.tax_amount - inv.total_amount) > 0.02:
        problems.append("subtotal + tax does not equal total")
    if inv.invoice_date > date.today():
        problems.append("date is in the future")
    if inv.vendor_gstin and not _GSTIN_RE.fullmatch(inv.vendor_gstin):
        problems.append("GSTIN format is wrong")
    return problems
