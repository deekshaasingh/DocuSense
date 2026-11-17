"""
Metric definitions used by every experiment in eval/.

Four groups:
  * per-field precision / recall
  * line-item matching (Hungarian assignment), which v1 left out of scoring
  * calibration: binned reliability table and Expected Calibration Error
  * discrimination and review economics: AUROC, and an ECARB-style
    error-capture ratio against random sampling at a fixed review budget

ECARB follows the definition used by ConfBench (arXiv:2608.01792): how many
more errors a confidence-guided reviewer catches than a reviewer sampling the
same number of documents at random. A ratio of 1.0 means confidence added
nothing; 2.0 means twice the errors caught for the same effort.
"""
from __future__ import annotations

import difflib

import numpy as np
from scipy.optimize import linear_sum_assignment
from sklearn.metrics import roc_auc_score

N_BINS = 10
MONEY_TOLERANCE = 0.02


# --------------------------------------------------------------- calibration

def reliability_table(scores: list[float], correct: list[bool], n_bins: int = N_BINS):
    """Bin predictions by confidence; report count, accuracy and gap per bin."""
    rows = []
    for b in range(n_bins):
        lo, hi = b / n_bins, (b + 1) / n_bins
        idx = [i for i, s in enumerate(scores) if (s >= lo and (s < hi or (b == n_bins - 1 and s <= hi)))]
        if not idx:
            continue
        acc = sum(correct[i] for i in idx) / len(idx)
        mid = (lo + hi) / 2
        rows.append({
            "bin": f"{lo:.1f} to {hi:.1f}",
            "n": len(idx),
            "accuracy": acc,
            "midpoint": mid,
            "gap": abs(acc - mid),
        })
    return rows


def expected_calibration_error(scores: list[float], correct: list[bool], n_bins: int = N_BINS) -> float:
    rows = reliability_table(scores, correct, n_bins)
    total = sum(r["n"] for r in rows)
    if not total:
        return 0.0
    return sum(r["n"] / total * r["gap"] for r in rows)


# ------------------------------------------------- discrimination / economics

def auroc(scores: list[float], correct: list[bool]) -> float | None:
    """Can the confidence score separate correct from incorrect extractions?"""
    labels = [1 if c else 0 for c in correct]
    if len(set(labels)) < 2:
        return None
    return float(roc_auc_score(labels, scores))


def error_capture(doc_scores: list[float], doc_errors: list[int], budget: float) -> dict:
    """ECARB-style review-budget metric at a given budget fraction.

    Reviewers inspect `budget` of the documents. Confidence-guided review
    takes the lowest scoring documents first; random review is the expected
    value of sampling uniformly, which is simply budget * total errors.
    """
    n = len(doc_scores)
    total_errors = sum(doc_errors)
    k = max(1, int(round(budget * n)))
    order = np.argsort(np.array(doc_scores, dtype=float))  # lowest confidence first
    guided = int(sum(doc_errors[i] for i in order[:k]))
    expected_random = budget * total_errors
    ratio = (guided / expected_random) if expected_random > 0 else None
    return {
        "budget": budget,
        "documents_reviewed": k,
        "errors_total": total_errors,
        "errors_caught_guided": guided,
        "errors_caught_random_expected": round(expected_random, 1),
        "ecarb": round(ratio, 3) if ratio is not None else None,
        "recall_of_errors": round(guided / total_errors, 4) if total_errors else None,
    }


# --------------------------------------------------------------- line items

def _item_similarity(pred: dict, truth: dict) -> float:
    """0..1 similarity combining description text and the three numbers."""
    desc = difflib.SequenceMatcher(
        None, str(pred.get("description", "")).lower(), str(truth.get("description", "")).lower()
    ).ratio()

    numeric = 0.0
    for key in ("quantity", "unit_price", "amount"):
        try:
            p, t = float(pred.get(key, 0)), float(truth.get(key, 0))
        except (TypeError, ValueError):
            continue
        if abs(p - t) <= MONEY_TOLERANCE:
            numeric += 1.0
        elif t:
            numeric += max(0.0, 1.0 - abs(p - t) / abs(t))
    numeric /= 3.0

    return 0.4 * desc + 0.6 * numeric


def match_line_items(pred_items: list[dict], truth_items: list[dict], threshold: float = 0.75):
    """Hungarian assignment between predicted and true rows.

    v1 of this project excluded line items from scoring because comparing
    variable-length lists of structured rows needs an alignment step. This is
    that step: build a similarity matrix, solve the optimal assignment, and
    count a pair as matched only when similarity clears `threshold`.
    """
    if not pred_items and not truth_items:
        return {"matched": 0, "predicted": 0, "expected": 0}
    if not pred_items or not truth_items:
        return {"matched": 0, "predicted": len(pred_items), "expected": len(truth_items)}

    cost = np.zeros((len(pred_items), len(truth_items)))
    for i, p in enumerate(pred_items):
        for j, t in enumerate(truth_items):
            cost[i, j] = 1.0 - _item_similarity(p, t)

    rows, cols = linear_sum_assignment(cost)
    matched = sum(1 for r, c in zip(rows, cols) if (1.0 - cost[r, c]) >= threshold)
    return {"matched": matched, "predicted": len(pred_items), "expected": len(truth_items)}


def prf(matched: int, predicted: int, expected: int) -> tuple[float, float, float]:
    precision = matched / predicted if predicted else 0.0
    recall = matched / expected if expected else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return precision, recall, f1
