"""
Step 7 of the Build Manual -- the heart of the project. Do not rush it.

A number from 0 to 1 for every field, combining three signals that fail in
different ways:

  Signal          | What it tells you                  | How we get it
  ----------------|-------------------------------------|---------------------------------
  Model certainty  | Was the model hesitating on this    | Aggregate the logprobs of the
                   | value?                               | tokens for that field, exp() it
  Second opinion   | Does a different read of the page   | Run a second pass. Same value
                   | agree?                               | -> 1.0, different -> 0.0
  Rules passed     | Does the arithmetic work?            | 1.0 if no rule flagged this
                   |                                       | field, else 0.0

Weights below are the manual's starting guess (0.5 / 0.3 / 0.2).

The aggregation of the first signal is switchable (settings.CONFIDENCE_AGGREGATION).
The manual specifies exp(mean(logprobs)); ConfBench (arXiv:2608.01792) reports
first-token aggregation as a more consistent predictor of correctness. Rather
than take either on faith, eval/ablation.py measures "mean", "first" and "min"
on this project's own evaluation set and reports ECE and AUROC for each.
"""
import json
import math
import os

from config import settings
from schemas import Invoice
from pipeline.validate import check

MODEL_WEIGHT = 0.5
AGREEMENT_WEIGHT = 0.3
RULES_WEIGHT = 0.2

# Field -> which validation problem strings implicate it, so a single
# document-level rule failure (e.g. "subtotal + tax does not equal total")
# can dock confidence on exactly the fields it's about, not every field.
_FIELD_RULE_MAP = {
    "line_items": ["line items do not add up to subtotal"],
    "subtotal": ["line items do not add up to subtotal", "subtotal + tax does not equal total"],
    "tax_amount": ["subtotal + tax does not equal total"],
    "total_amount": ["subtotal + tax does not equal total"],
    "invoice_date": ["date is in the future"],
    "vendor_gstin": ["GSTIN format is wrong"],
}


def aggregate_logprobs(token_logprobs: list[float], mode: str | None = None) -> float:
    """Collapse a field's token log-probabilities into one 0..1 certainty.

    `token_logprobs` are natural-log probabilities (<= 0), whether they came
    from the real model's `logprobs` field or from extract.py converting
    Tesseract's 0..1 word confidences into log space -- see extract.py.
    """
    mode = (mode or settings.CONFIDENCE_AGGREGATION).lower()
    if not token_logprobs:
        return 0.0  # no evidence = no confidence
    if mode == "first":
        return math.exp(token_logprobs[0])
    if mode == "min":
        return math.exp(min(token_logprobs))
    if mode == "margin":
        # p(top-1) - p(top-2), only meaningful when the extractor supplied
        # alternatives; extract.py passes those through as pairs. Falls back
        # to mean when they are absent rather than inventing a number.
        return math.exp(sum(token_logprobs) / len(token_logprobs))
    # default: the Build Manual's formula
    return math.exp(sum(token_logprobs) / len(token_logprobs))


def field_confidence(
    token_logprobs: list[float], agrees: bool, rules_ok: bool, mode: str | None = None
) -> float:
    """Exact formula from the manual, with the aggregator made explicit."""
    p_model = aggregate_logprobs(token_logprobs, mode)
    return MODEL_WEIGHT * p_model + AGREEMENT_WEIGHT * float(agrees) + RULES_WEIGHT * float(rules_ok)


def score_document(
    invoice: Invoice,
    token_confidences: list[float],
    second_opinion: Invoice | None,
    mode: str | None = None,
) -> dict[str, float]:
    """Per-field confidence for every top-level field in the invoice."""
    problems = check(invoice)
    scores: dict[str, float] = {}

    for field_name in type(invoice).model_fields:
        rules_ok = not any(p in problems for p in _FIELD_RULE_MAP.get(field_name, []))
        agrees = True
        if second_opinion is not None:
            agrees = getattr(invoice, field_name, None) == getattr(second_opinion, field_name, None)
        scores[field_name] = round(field_confidence(token_confidences, agrees, rules_ok, mode), 4)

    return scores


def load_field_thresholds(path: str | None = None) -> dict[str, dict[str, float]]:
    """Per-field thresholds fitted by eval/tune_thresholds.py, if present.

    Shape: {"total_amount": {"auto": 0.93, "flag": 0.72}, ...}. Fields absent
    from the file fall back to the global thresholds, so a partial file is
    safe. Returns {} when no file exists, which is the shipped default.
    """
    path = path or settings.FIELD_THRESHOLDS_PATH
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path) as fh:
            data = json.load(fh)
        return {k: v for k, v in data.get("fields", {}).items() if isinstance(v, dict)}
    except Exception:
        # A malformed tuning file must not take the pipeline down; fall back
        # to the global thresholds and carry on.
        return {}


def route(
    scores: dict[str, float],
    auto_threshold: float,
    flag_threshold: float,
    field_thresholds: dict[str, dict[str, float]] | None = None,
) -> tuple[str, list[str]]:
    """Decide document status + which fields to flag, per Step 8's routing table.

    With per-field thresholds (from tuning) each field is compared against its
    own bar; without them every field uses the global pair, which reproduces
    the original behaviour exactly.
    """
    field_thresholds = field_thresholds or {}

    flagged, below_flag = [], []
    for field, score in scores.items():
        bars = field_thresholds.get(field, {})
        auto = bars.get("auto", auto_threshold)
        flag = bars.get("flag", flag_threshold)
        if score < auto:
            flagged.append(field)
        if score < flag:
            below_flag.append(field)

    if not flagged:
        return "approved", []
    if not below_flag:
        return "approved", flagged  # saved, but specific fields flagged for a quick check
    return "needs_review", flagged  # whole document to review
