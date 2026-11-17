"""
Step 5 of the Build Manual: image in, valid JSON out, every time.

Two extractors live here behind one interface (`extract`), chosen by
config.settings.EXTRACTOR_MODE:

  "ollama" -- extract_ollama(): the real thing. Calls a local Ollama server
      running a vision-language model (Qwen2.5-VL 7B by default), exactly as
      specified in the manual: `format` forces valid JSON, `temperature: 0`
      makes it reproducible, `logprobs`/`top_logprobs` give per-token
      certainty for Step 7's confidence score. Requires `ollama pull
      qwen2.5vl:7b` on a machine with ~5GB RAM to spare (see docs/deployment.md).

  "mock" -- extract_local_ocr(): what this repo runs by default, in CI, and
      for the eval harness in this sandbox (no GPU, no multi-GB model
      download available here). It is NOT a stub that echoes ground truth --
      it runs real Tesseract OCR over the preprocessed page, then parses
      fields out of the OCR text with the same kind of regex/heuristic rules
      a first extraction pass would use before an LLM was involved. It makes
      real mistakes (misreads, missed fields) and Tesseract's own per-word
      confidence stands in for the VLM's logprobs. That is what lets Step 7's
      confidence scoring and Step 10's evaluation harness mean something on
      a laptop with no model server. Swapping to the real model later is a
      one-line config change (EXTRACTOR_MODE=ollama); nothing else in the
      pipeline (validate.py, confidence.py, tasks.py) has to change, because
      both extractors return the same (Invoice, token_confidences) shape.
"""
from __future__ import annotations

import base64
import math
import re
from datetime import date

import cv2
import numpy as np
import requests

from config import settings
from schemas import Invoice, LineItem

PROMPT = """Read this invoice and extract the fields.
Copy values exactly as printed. Do not calculate or guess.
If a field is not visible, leave it empty."""


# ---------------------------------------------------------------------------
# Real extractor -- exact approach from Build Manual Step 5.
# ---------------------------------------------------------------------------

def extract_ollama(image_path: str) -> tuple[Invoice, list[float]]:
    img_b64 = base64.b64encode(open(image_path, "rb").read()).decode()
    r = requests.post(settings.OLLAMA_URL, json={
        "model": settings.OLLAMA_MODEL,
        "messages": [{"role": "user", "content": PROMPT, "images": [img_b64]}],
        "format": Invoice.model_json_schema(),   # forces valid JSON
        "options": {"temperature": 0},           # same input, same output
        "logprobs": True,                        # needed for Step 7
        "top_logprobs": 3,
        "stream": False,
    }, timeout=300).json()

    invoice = Invoice.model_validate_json(r["message"]["content"])
    token_logprobs = r.get("logprobs", [])
    return invoice, token_logprobs


def second_opinion_ollama(image_path: str) -> Invoice | None:
    """Run the smaller second model for the 'does a different model agree' signal."""
    try:
        img_b64 = base64.b64encode(open(image_path, "rb").read()).decode()
        r = requests.post(settings.OLLAMA_URL, json={
            "model": settings.OLLAMA_SECOND_MODEL,
            "messages": [{"role": "user", "content": PROMPT, "images": [img_b64]}],
            "format": Invoice.model_json_schema(),
            "options": {"temperature": 0},
            "stream": False,
        }, timeout=300).json()
        return Invoice.model_validate_json(r["message"]["content"])
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Local extractor -- real Tesseract OCR + heuristic field parsing.
# Used when no model server is available (EXTRACTOR_MODE=mock, the default).
# ---------------------------------------------------------------------------

_MONEY_RE = re.compile(r"[-+]?\d[\d,]*\.\d{2}")
_DATE_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_GSTIN_RE = re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z]\d[A-Z\d]{2}\b")
# Invoice numbers are found in two passes, in this order.
#
# First, a code that looks like one in its own right. Requiring a digit
# straight after "INV" is what stops this pattern matching the first three
# letters of the word "Invoice" itself: the old single pattern used
# `INV[-\s]?` with IGNORECASE, so on any page where OCR misread the "No"
# label it matched "Inv" inside "Invoice" and returned "oice" as the invoice
# number. It also dropped the prefix from a bare "INV-9001", returning
# "9001". See docs/failures.md section 10.
_INVOICE_CODE_RE = re.compile(r"\bINV[-\s]?\d[A-Z0-9\-/]*", re.I)

# Second, whatever follows an "Invoice number" style label, for documents
# whose numbering scheme is not INV-prefixed at all.
_INVOICE_LABEL_RE = re.compile(
    # The capture must contain a digit, otherwise the word "invoice" sitting
    # in ordinary prose matches and the next word is returned as a number.
    r"\bInvoice\s*(?:#|No\.?|Number)?\s*[:\-]?\s*([A-Z0-9][A-Z0-9\-/]*\d[A-Z0-9\-/]*)", re.I
)


def find_invoice_number(text: str) -> str:
    """Pull the invoice number out of OCR text, tolerating a misread label."""
    m = _INVOICE_CODE_RE.search(text)
    if m:
        return m.group(0).upper().replace(" ", "-")
    m = _INVOICE_LABEL_RE.search(text)
    if m:
        return m.group(1)
    return "UNKNOWN"


def _to_float(s: str) -> float:
    return float(s.replace(",", ""))


def _ocr(img: np.ndarray):
    import pytesseract
    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    text = pytesseract.image_to_string(img)
    return text, data


def extract_local_ocr(img: np.ndarray) -> tuple[Invoice, list[float]]:
    """
    Real OCR + regex/heuristic parsing. Deliberately simple (no ML field
    classifier) -- it plays the role of 'a decent first pass' so that
    confidence scoring and human review have real work to do, same as the
    manual describes for the VLM path.
    """
    text, data = _ocr(img)
    lines = [l for l in text.splitlines() if l.strip()]

    # word-level OCR confidences (0-100, -1 for non-text boxes) -> 0..1,
    # then into log-space so confidence.py can apply the manual's exact
    # exp(mean(logprobs)) formula uniformly, same as the real model's output.
    word_confs = [
        math.log(max(c / 100.0, 1e-6))
        for c in data.get("conf", [])
        if isinstance(c, (int, float)) and c >= 0
    ]

    invoice_number = find_invoice_number(text)

    date_m = _DATE_RE.search(text)
    invoice_date = date(int(date_m.group(1)), int(date_m.group(2)), int(date_m.group(3))) if date_m else date.today()

    gstin_m = _GSTIN_RE.search(text)
    vendor_gstin = gstin_m.group(0) if gstin_m else None

    vendor_name = lines[0].strip() if lines else "UNKNOWN VENDOR"

    money_vals = [_to_float(m) for m in _MONEY_RE.findall(text)]

    def _find_labeled(label: str) -> float | None:
        # \b word-boundary so "total" doesn't match inside "subtotal" --
        # the bug this replaced: label-substring matching silently returned
        # the subtotal line's value whenever it searched for "total"
        # (caught by eval/RESULTS.md showing 0% precision on total_amount;
        # see docs/failures.md).
        pattern = re.compile(rf"\b{re.escape(label)}\b", re.I)
        for line in lines:
            if pattern.search(line):
                m = _MONEY_RE.search(line)
                if m:
                    return _to_float(m.group(0))
        return None

    subtotal = _find_labeled("subtotal")
    tax_amount = _find_labeled("tax")
    total_amount = _find_labeled("total")
    if total_amount is not None and subtotal is not None and total_amount == subtotal:
        # Both labels matched the same line (e.g. OCR merged rows) --
        # discard the ambiguous read rather than silently keep a wrong one.
        total_amount = None

    # Fallback: if labels weren't matched (OCR noise), guess from the money
    # values seen (largest = total). This is exactly the kind of soft guess
    # Step 6's validation rules exist to catch.
    if total_amount is None and money_vals:
        total_amount = max(money_vals)
    if subtotal is None:
        subtotal = total_amount or 0.0
    if tax_amount is None:
        tax_amount = round((total_amount or 0.0) - subtotal, 2)

    # Line items: look for "description qty unit_price amount" style rows
    line_items: list[LineItem] = []
    item_row_re = re.compile(
        r"^(?P<desc>[A-Za-z][A-Za-z0-9 \-/]+?)\s+(?P<qty>\d+(?:\.\d+)?)\s+"
        r"(?P<unit>\d[\d,]*\.\d{2})\s+(?P<amt>\d[\d,]*\.\d{2})\s*$"
    )
    for line in lines:
        m = item_row_re.match(line.strip())
        if m:
            line_items.append(LineItem(
                description=m.group("desc").strip(),
                quantity=float(m.group("qty")),
                unit_price=_to_float(m.group("unit")),
                amount=_to_float(m.group("amt")),
            ))

    if not line_items and total_amount is not None:
        # last-resort single synthetic line so the schema is satisfiable
        line_items.append(LineItem(description="(unparsed items)", quantity=1, unit_price=total_amount, amount=total_amount))

    invoice = Invoice(
        invoice_number=invoice_number,
        invoice_date=invoice_date,
        vendor_name=vendor_name,
        vendor_gstin=vendor_gstin,
        subtotal=round(subtotal, 2),
        tax_amount=round(tax_amount, 2),
        total_amount=round(total_amount or 0.0, 2),
        line_items=line_items,
    )
    return invoice, word_confs


# ---------------------------------------------------------------------------
# Unified entry point used by tasks.py -- this is the only function the rest
# of the pipeline calls, so swapping EXTRACTOR_MODE doesn't touch anything else.
# ---------------------------------------------------------------------------

def extract(image_path: str, img: np.ndarray | None = None) -> tuple[Invoice, list[float]]:
    if settings.EXTRACTOR_MODE == "ollama":
        return extract_ollama(image_path)
    if img is None:
        img = cv2.imread(image_path)
    return extract_local_ocr(img)


def get_second_opinion(image_path: str, img: np.ndarray | None = None) -> Invoice | None:
    """Second-model cross-check for the confidence 'agreement' signal (Step 7)."""
    if settings.EXTRACTOR_MODE == "ollama":
        return second_opinion_ollama(image_path)
    # Local fallback: re-run OCR against a lightly perturbed copy of the same
    # image as a cheap stand-in for "a different model reads it". Real
    # disagreement, not a fixed answer.
    if img is None:
        img = cv2.imread(image_path)
    try:
        perturbed = cv2.GaussianBlur(img, (3, 3), 0)
        alt_invoice, _ = extract_local_ocr(perturbed)
        return alt_invoice
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Multi-page handling (Build Manual, Section 11: "process page by page, merge
# after. Do not send 10 pages at once").
# ---------------------------------------------------------------------------

def merge_pages(results: list[tuple[Invoice, list[float]]]) -> tuple[Invoice, list[float]]:
    """Merge per-page extractions into one record.

    Policy, chosen to match how multi-page invoices actually read:
      * header fields (number, date, vendor, GSTIN) come from the first page
        that produced a non-placeholder value, because they are printed on
        page one and repeated or omitted later;
      * totals come from the LAST page that carries them, because that is
        where an invoice's summary block sits;
      * line items concatenate across pages in page order.
    Token certainties are pooled across pages so the confidence score reflects
    the whole document rather than one page of it.
    """
    if not results:
        raise ValueError("no pages to merge")
    if len(results) == 1:
        return results[0]

    first, _ = results[0]
    merged = first.model_copy(deep=True)
    pooled: list[float] = []

    placeholder = {"UNKNOWN", "UNKNOWN VENDOR", None, ""}
    for inv, confs in results:
        pooled.extend(confs)
        for field in ("invoice_number", "vendor_name", "vendor_gstin"):
            if getattr(merged, field) in placeholder and getattr(inv, field) not in placeholder:
                setattr(merged, field, getattr(inv, field))

    # totals from the last page that has a non-zero total
    for inv, _ in reversed(results):
        if inv.total_amount:
            merged.subtotal = inv.subtotal
            merged.tax_amount = inv.tax_amount
            merged.total_amount = inv.total_amount
            break

    items: list[LineItem] = []
    for inv, _ in results:
        for it in inv.line_items:
            if it.description != "(unparsed items)":
                items.append(it)
    if items:
        merged.line_items = items

    return merged, pooled


def extract_pages(image_path: str, pages: list[np.ndarray]) -> tuple[Invoice, list[float], Invoice | None]:
    """Run extraction over every page and merge, returning the second opinion too."""
    per_page = [extract(image_path, img=p) for p in pages]
    invoice, token_conf = merge_pages(per_page)

    second_pages = [get_second_opinion(image_path, img=p) for p in pages]
    seconds = [(s, []) for s in second_pages if s is not None]
    second_opinion = merge_pages(seconds)[0] if seconds else None

    return invoice, token_conf, second_opinion
