"""
Shared evaluation machinery.

Running the pipeline over 320 documents costs several seconds each, so every
experiment (headline metrics, the aggregation ablation, threshold tuning)
reads from one cached pass instead of re-running OCR. The cache stores the
raw per-field evidence -- token certainties, second-opinion agreement, rule
outcomes -- so any scoring variant can be recomputed from it exactly.

Imported by run_eval.py, ablation.py and tune_thresholds.py.
"""
from __future__ import annotations

import json
import os
import pickle
import sys
import time
from dataclasses import dataclass, field
from datetime import date

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "backend"))

from pipeline.preprocess import clean                      # noqa: E402
from pipeline.extract import extract_local_ocr, get_second_opinion  # noqa: E402
from pipeline.validate import check                        # noqa: E402
from pipeline.confidence import (                          # noqa: E402
    MODEL_WEIGHT, AGREEMENT_WEIGHT, RULES_WEIGHT, _FIELD_RULE_MAP,
    aggregate_logprobs,
)
from schemas import Invoice, SCALAR_FIELDS                 # noqa: E402

DATASET = os.path.join(HERE, "dataset")
CACHE = os.path.join(HERE, ".eval_cache.pkl")

MONEY_TOLERANCE = 0.02


@dataclass
class DocResult:
    doc_id: str
    split: str
    degradation: str
    latency_s: float
    token_confs: list[float]
    predicted: dict[str, str]
    truth: dict[str, str]
    agrees: dict[str, bool]
    rules_ok: dict[str, bool]
    pred_items: list[dict] = field(default_factory=list)
    truth_items: list[dict] = field(default_factory=list)


def _norm_text(v) -> str:
    return " ".join(str(v).strip().lower().split()) if v is not None else ""


def field_correct(name: str, predicted: str, truth: str) -> bool:
    """Exact match after normalisation for text, +/- 0.02 for currency."""
    if name in ("subtotal", "tax_amount", "total_amount"):
        try:
            return abs(float(predicted) - float(truth)) <= MONEY_TOLERANCE
        except (TypeError, ValueError):
            return False
    return _norm_text(predicted) == _norm_text(truth)


def _as_str(value) -> str:
    if value is None:
        return ""
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def run_document(png_path: str, truth: dict) -> tuple[DocResult, float]:
    started = time.time()
    img = cv2.imread(png_path)
    cleaned = clean(img)
    invoice, token_confs = extract_local_ocr(cleaned)
    second = get_second_opinion(png_path, img=cleaned)
    latency = time.time() - started

    problems = check(invoice)
    agrees, rules_ok, predicted, truth_vals = {}, {}, {}, {}
    for name in SCALAR_FIELDS:
        pred_value = getattr(invoice, name, None)
        predicted[name] = _as_str(pred_value)
        truth_vals[name] = _as_str(truth.get(name))
        rules_ok[name] = not any(p in problems for p in _FIELD_RULE_MAP.get(name, []))
        agrees[name] = (
            True if second is None else getattr(invoice, name, None) == getattr(second, name, None)
        )

    # line items, kept raw so the matcher in run_eval.py can align them
    pred_items = [i.model_dump() for i in invoice.line_items]
    truth_items = [dict(i) for i in truth.get("line_items", [])]

    return DocResult(
        doc_id="", split="", degradation="", latency_s=latency,
        token_confs=token_confs, predicted=predicted, truth=truth_vals,
        agrees=agrees, rules_ok=rules_ok,
        pred_items=pred_items, truth_items=truth_items,
    ), latency


def build_cache(limit: int | None = None, verbose: bool = True) -> list[DocResult]:
    with open(os.path.join(DATASET, "_manifest.json")) as fh:
        manifest = json.load(fh)
    if limit:
        manifest = manifest[:limit]

    results: list[DocResult] = []
    for n, entry in enumerate(manifest, 1):
        stem = entry["id"]
        png = os.path.join(DATASET, f"{stem}.png")
        with open(os.path.join(DATASET, f"{stem}.json")) as fh:
            truth = json.load(fh)
        res, _ = run_document(png, truth)
        res.doc_id = stem
        res.split = entry.get("split", "holdout")
        res.degradation = entry.get("degradation", "none")
        results.append(res)
        if verbose and n % 25 == 0:
            print(f"  processed {n}/{len(manifest)}", flush=True)

    with open(CACHE, "wb") as fh:
        pickle.dump(results, fh)
    return results


def load_cache(rebuild: bool = False, limit: int | None = None) -> list[DocResult]:
    if not rebuild and os.path.exists(CACHE):
        with open(CACHE, "rb") as fh:
            return pickle.load(fh)
    return build_cache(limit=limit)


def score_fields(res: DocResult, mode: str) -> dict[str, float]:
    """Recompute per-field confidence from cached evidence under `mode`."""
    p_model = aggregate_logprobs(res.token_confs, mode)
    return {
        name: round(
            MODEL_WEIGHT * p_model
            + AGREEMENT_WEIGHT * float(res.agrees[name])
            + RULES_WEIGHT * float(res.rules_ok[name]),
            4,
        )
        for name in SCALAR_FIELDS
    }


def correctness(res: DocResult) -> dict[str, bool]:
    return {
        name: field_correct(name, res.predicted[name], res.truth[name])
        for name in SCALAR_FIELDS
    }
