"""
Aggregation ablation.

The Build Manual (Step 7) specifies exp(mean(logprobs)) for the model
certainty term. ConfBench (arXiv:2608.01792) reports that first-token
aggregation is a more consistent predictor of correctness than mean-token or
margin aggregation across the vision-language models it benchmarks.

This script tests that claim on this project's own data. It re-scores the
cached evaluation pass under each aggregator, changing nothing else, and
reports ECE, AUROC and straight-through rate for each.

Note on "margin": ConfBench's third aggregator is p(top-1) - p(top-2), which
needs the model's alternative tokens. The local OCR extractor does not expose
alternatives, so it is not measurable here and "min" (the weakest token in
the field) is reported in its place. That substitution is a limitation of
this environment, not a redefinition of ConfBench's metric.

    python3 ablation.py
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "backend"))

from metrics import auroc, expected_calibration_error  # noqa: E402
from runner import correctness, load_cache, score_fields  # noqa: E402
from schemas import SCALAR_FIELDS  # noqa: E402
from pipeline.confidence import route  # noqa: E402
from config import settings  # noqa: E402

RESULTS = os.path.join(HERE, "RESULTS.md")
MODES = ("mean", "first", "min")


def measure(results, mode: str) -> dict:
    scores_flat, correct_flat = [], []
    straight_through = 0

    for res in results:
        scores = score_fields(res, mode)
        correct = correctness(res)
        for name in SCALAR_FIELDS:
            scores_flat.append(scores[name])
            correct_flat.append(correct[name])
        status, flagged = route(scores, settings.AUTO_APPROVE_THRESHOLD, settings.FLAG_THRESHOLD)
        if status == "approved" and not flagged:
            straight_through += 1

    return {
        "mode": mode,
        "ece": expected_calibration_error(scores_flat, correct_flat),
        "auroc": auroc(scores_flat, correct_flat),
        "straight_through": straight_through / len(results) if results else 0.0,
        "mean_confidence": sum(scores_flat) / len(scores_flat) if scores_flat else 0.0,
    }


def main() -> None:
    results = load_cache()
    holdout = [r for r in results if r.split == "holdout"] or results

    rows = [measure(holdout, m) for m in MODES]
    best_ece = min(rows, key=lambda r: r["ece"])
    best_auc = max(rows, key=lambda r: (r["auroc"] or 0))

    lines = [
        f"\n## Aggregation ablation {datetime.now(timezone.utc).isoformat()}\n",
        f"Holdout split, {len(holdout)} documents, {len(holdout) * len(SCALAR_FIELDS)} field predictions. "
        "Only the aggregator changes; weights, thresholds and extractions are identical.\n",
        "| Aggregation | ECE (lower better) | AUROC (higher better) | Mean confidence | Straight-through |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        auc = f"{r['auroc']:.3f}" if r["auroc"] is not None else "n/a"
        lines.append(
            f"| `{r['mode']}` | {r['ece']:.3f} | {auc} | {r['mean_confidence']:.3f} | "
            f"{r['straight_through'] * 100:.1f}% |"
        )
    lines.append(
        f"\nBest calibration: `{best_ece['mode']}` (ECE {best_ece['ece']:.3f}). "
        f"Best discrimination: `{best_auc['mode']}` "
        f"(AUROC {best_auc['auroc']:.3f})." if best_auc["auroc"] is not None else ""
    )
    lines.append(
        "\n`margin` is not measurable with the OCR extractor, which exposes no alternative "
        "tokens; `min` is reported in its place. See the module docstring."
    )

    body = "\n".join(lines) + "\n"
    print(body)
    with open(RESULTS, "a") as fh:
        fh.write(body)
    print(f"appended to {RESULTS}")


if __name__ == "__main__":
    main()
