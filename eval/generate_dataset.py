"""
Builds the evaluation set: synthetic invoices rendered to PNG, each with a
ground-truth JSON written independently of anything the extractor produces.

Why synthetic: there is no live business generating real paperwork for this
project, and real invoices carry vendor and GSTIN data that cannot be
redistributed. See docs/evaluation.md for what this does and does not prove.

Every document is internally consistent (line items really sum to the
subtotal, tax is a fixed rate, GSTINs are syntactically valid), and most are
deliberately degraded so the pipeline has genuine failure cases to catch.
`_manifest.json` records the degradation and the split for every document.
"""
import json
import os
import random
import sys
from datetime import date, timedelta

import cv2
import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))
from textfont import load_font, font_in_use  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "dataset")

N_DOCS = 320
TUNE_SHARE = 0.4          # 40% tune / 60% sealed holdout (Manual, Section 10 rule 2)
SEED = 20261111

VENDORS = [
    "Everline Stationers", "Nandan Traders", "Shivam Electricals", "Kaveri Paper Mills",
    "Orion Hardware", "Bluewave Logistics", "Pragati Metals", "Suncrest Packaging",
    "Meridian Office Supply", "Anand Textiles", "Vertex Components", "Trimurti Chemicals",
]
ITEMS = [
    "A4 paper ream", "Ball pen box", "Stapler", "Printer toner", "USB cable",
    "Desk lamp", "File folder", "Whiteboard marker", "Extension board", "Notebook pack",
    "Mouse pad", "Copier paper", "Ink cartridge", "Document tray", "Label roll",
]
STATE_CODES = ["07", "09", "24", "27", "29", "33", "36"]
LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
DEGRADATIONS = ["none", "rotate", "rotate+blur", "blur", "noise", "contrast"]


def _gstin(rng: random.Random) -> str:
    return (
        rng.choice(STATE_CODES)
        + "".join(rng.choice(LETTERS) for _ in range(5))
        + "".join(str(rng.randint(0, 9)) for _ in range(4))
        + rng.choice(LETTERS)
        + str(rng.randint(1, 9))
        + "Z"
        + rng.choice(LETTERS + "0123456789")
    )


def _font(size: int):
    """A readable TrueType font, or a clear error.

    Previously this looked only in Linux font directories and fell back to
    PIL's bitmap font everywhere else, which silently rendered a dataset
    Tesseract could not read. See docs/failures.md sections 3 and 11.
    """
    return load_font(size)


def make_invoice(idx: int, rng: random.Random) -> dict:
    vendor = rng.choice(VENDORS)
    n_items = rng.randint(2, 5)
    items = []
    for _ in range(n_items):
        qty = rng.randint(1, 12)
        unit = round(rng.uniform(25, 950), 2)
        items.append({
            "description": rng.choice(ITEMS),
            "quantity": float(qty),
            "unit_price": unit,
            "amount": round(qty * unit, 2),
        })
    subtotal = round(sum(i["amount"] for i in items), 2)
    tax = round(subtotal * 0.18, 2)
    total = round(subtotal + tax, 2)
    inv_date = date(2025, 1, 1) + timedelta(days=rng.randint(0, 600))

    return {
        "invoice_number": f"INV-{4000 + idx}",
        "invoice_date": inv_date.isoformat(),
        "vendor_name": vendor,
        "vendor_gstin": _gstin(rng),
        "subtotal": subtotal,
        "tax_amount": tax,
        "total_amount": total,
        "line_items": items,
    }


def render(truth: dict) -> np.ndarray:
    W, H = 1240, 1754  # A4 at ~150 DPI
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    big, mid, small = _font(34), _font(24), _font(22)

    y = 70
    d.text((70, y), truth["vendor_name"], font=big, fill="black"); y += 56
    d.text((70, y), f"GSTIN: {truth['vendor_gstin']}", font=small, fill="black"); y += 40
    d.text((70, y), f"Invoice No: {truth['invoice_number']}", font=mid, fill="black"); y += 36
    d.text((70, y), f"Date: {truth['invoice_date']}", font=mid, fill="black"); y += 60

    d.line([(70, y), (W - 70, y)], fill="black", width=2); y += 24
    d.text((70, y), "Description", font=small, fill="black")
    d.text((640, y), "Qty", font=small, fill="black")
    d.text((780, y), "Rate", font=small, fill="black")
    d.text((980, y), "Amount", font=small, fill="black")
    y += 34
    d.line([(70, y), (W - 70, y)], fill="black", width=1); y += 20

    for it in truth["line_items"]:
        d.text((70, y), it["description"], font=small, fill="black")
        d.text((640, y), f"{int(it['quantity'])}", font=small, fill="black")
        d.text((780, y), f"{it['unit_price']:.2f}", font=small, fill="black")
        d.text((980, y), f"{it['amount']:.2f}", font=small, fill="black")
        y += 36

    y += 20
    d.line([(640, y), (W - 70, y)], fill="black", width=1); y += 22
    for label, value in (
        ("Subtotal", truth["subtotal"]),
        ("Tax", truth["tax_amount"]),
        ("Total", truth["total_amount"]),
    ):
        d.text((700, y), label, font=mid, fill="black")
        d.text((980, y), f"{value:.2f}", font=mid, fill="black")
        y += 40

    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def degrade(img: np.ndarray, kind: str, rng: random.Random) -> np.ndarray:
    out = img
    if "rotate" in kind:
        angle = rng.uniform(-6.5, 6.5)
        h, w = out.shape[:2]
        M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
        out = cv2.warpAffine(out, M, (w, h), flags=cv2.INTER_CUBIC,
                             borderMode=cv2.BORDER_REPLICATE)
    if "blur" in kind:
        out = cv2.GaussianBlur(out, (3, 3), rng.uniform(0.4, 1.0))
    if "noise" in kind:
        noise = rng.gauss  # keep determinism through the seeded rng
        n = np.array([[noise(0, 9) for _ in range(out.shape[1])] for _ in range(32)])
        tile = np.resize(n, out.shape[:2])[..., None].astype(np.float32)
        out = np.clip(out.astype(np.float32) + tile, 0, 255).astype(np.uint8)
    if "contrast" in kind:
        out = np.clip(out.astype(np.float32) * 0.72 + 42, 0, 255).astype(np.uint8)
    return out


def main() -> None:
    rng = random.Random(SEED)
    os.makedirs(OUT, exist_ok=True)
    manifest = []

    for i in range(1, N_DOCS + 1):
        truth = make_invoice(i, rng)
        img = render(truth)
        kind = rng.choice(DEGRADATIONS)
        img = degrade(img, kind, rng)

        stem = f"{i:04d}"
        cv2.imwrite(os.path.join(OUT, f"{stem}.png"), img)
        with open(os.path.join(OUT, f"{stem}.json"), "w") as fh:
            json.dump(truth, fh, indent=2)

        manifest.append({
            "id": stem,
            "degradation": kind,
            "split": "tune" if rng.random() < TUNE_SHARE else "holdout",
        })

    with open(os.path.join(OUT, "_manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=2)

    tune = sum(1 for m in manifest if m["split"] == "tune")
    print(f"wrote {len(manifest)} documents to {OUT}")
    print(f"  rendered with:  {font_in_use()}")
    print(f"  tune split:    {tune}")
    print(f"  holdout split: {len(manifest) - tune}")


if __name__ == "__main__":
    main()
