"""
Step 10 of the Build Manual: prove it works with numbers.

Reports, per split (tune / holdout / all):
  * precision and recall for each of the seven scalar fields
  * line-item precision, recall and F1 via Hungarian matching
  * straight-through rate under the active routing thresholds
  * calibration table and Expected Calibration Error
  * AUROC, how well confidence separates right from wrong
  * ECARB-style error capture against random sampling at 10/20/30% budgets
  * latency

Appends every run to RESULTS.md with a UTC timestamp. Old runs are never
deleted (Manual, Section 10).

    python3 run_eval.py [--rebuild] [--limit N] [--mode mean|first|min]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "backend"))

from metrics import (  # noqa: E402
    auroc, error_capture, expected_calibration_error, match_line_items, prf,
    reliability_table,
)
from runner import correctness, load_cache, score_fields  # noqa: E402
from schemas import SCALAR_FIELDS  # noqa: E402
from pipeline.confidence import route, load_field_thresholds  # noqa: E402
from config import settings  # noqa: E402

RESULTS = os.path.join(HERE, "RESULTS.md")
BUDGETS = (0.10, 0.20, 0.30)


def evaluate(results, mode: str, field_thresholds=None) -> dict:
    field_thresholds = field_thresholds or {}

    per_field = {f: {"correct": 0, "n": 0} for f in SCALAR_FIELDS}
    all_scores: list[float] = []
    all_correct: list[bool] = []
    doc_scores: list[float] = []
    doc_errors: list[int] = []
    straight_through = 0
    latencies: list[float] = []
    items = {"matched": 0, "predicted": 0, "expected": 0}
    auto_fields = auto_fields_correct = total_fields = 0

    for res in results:
        scores = score_fields(res, mode)
        correct = correctness(res)
        latencies.append(res.latency_s)

        for name in SCALAR_FIELDS:
            per_field[name]["n"] += 1
            per_field[name]["correct"] += int(correct[name])
            all_scores.append(scores[name])
            all_correct.append(correct[name])

        status, flagged = route(
            scores, settings.AUTO_APPROVE_THRESHOLD, settings.FLAG_THRESHOLD, field_thresholds
        )
        if status == "approved" and not flagged:
            straight_through += 1

        # Field-level automation: every field not flagged is accepted without
        # a human looking at it. This is the number that tracks reviewer
        # workload, and it stays meaningful when one weak field would
        # otherwise veto every document.
        for name in SCALAR_FIELDS:
            total_fields += 1
            if name not in flagged:
                auto_fields += 1
                auto_fields_correct += int(correct[name])

        doc_scores.append(min(scores.values()))
        doc_errors.append(sum(1 for name in SCALAR_FIELDS if not correct[name]))

        m = match_line_items(res.pred_items, res.truth_items)
        for k in items:
            items[k] += m[k]

    ip, ir, if1 = prf(items["matched"], items["predicted"], items["expected"])

    return {
        "n_documents": len(results),
        "mode": mode,
        "per_field": {
            f: {
                "precision": v["correct"] / v["n"] if v["n"] else 0.0,
                "recall": v["correct"] / v["n"] if v["n"] else 0.0,
                "n": v["n"],
            }
            for f, v in per_field.items()
        },
        "line_items": {"precision": ip, "recall": ir, "f1": if1, **items},
        "straight_through_rate": straight_through / len(results) if results else 0.0,
        "field_automation": auto_fields / total_fields if total_fields else 0.0,
        "auto_field_precision": (auto_fields_correct / auto_fields) if auto_fields else None,
        "ece": expected_calibration_error(all_scores, all_correct),
        "auroc": auroc(all_scores, all_correct),
        "reliability": reliability_table(all_scores, all_correct),
        "budgets": [error_capture(doc_scores, doc_errors, b) for b in BUDGETS],
        "latency_mean": sum(latencies) / len(latencies) if latencies else 0.0,
        "latency_p95": sorted(latencies)[max(0, int(len(latencies) * 0.95) - 1)] if latencies else 0.0,
        "field_thresholds_used": bool(field_thresholds),
    }


def render(report: dict, title: str) -> str:
    out = [f"\n### {title}\n"]
    out.append(f"- Documents: {report['n_documents']}")
    out.append(f"- Aggregation: `{report['mode']}`"
               + (" , per-field thresholds applied" if report["field_thresholds_used"] else ""))
    out.append(f"- Document straight-through rate: {report['straight_through_rate'] * 100:.1f}%")
    afp = report["auto_field_precision"]
    out.append(
        f"- Field automation: {report['field_automation'] * 100:.1f}% of values accepted without review"
        + (f", {afp * 100:.1f}% of them correct" if afp is not None else "")
    )
    out.append(f"- Expected Calibration Error (ECE): {report['ece']:.3f}")
    auc = report["auroc"]
    out.append(f"- AUROC: {auc:.3f}" if auc is not None else "- AUROC: n/a")
    out.append(f"- Latency: mean {report['latency_mean']:.3f}s, p95 {report['latency_p95']:.3f}s\n")

    out.append("| Field | Precision | Recall | N |")
    out.append("|---|---|---|---|")
    for f, v in report["per_field"].items():
        out.append(f"| {f} | {v['precision'] * 100:.1f}% | {v['recall'] * 100:.1f}% | {v['n']} |")

    li = report["line_items"]
    out.append("\n| Line items | Precision | Recall | F1 | Matched | Predicted | Expected |")
    out.append("|---|---|---|---|---|---|---|")
    out.append(
        f"| Hungarian matching | {li['precision'] * 100:.1f}% | {li['recall'] * 100:.1f}% | "
        f"{li['f1'] * 100:.1f}% | {li['matched']} | {li['predicted']} | {li['expected']} |"
    )

    out.append("\n| Confidence bin | N | Empirical accuracy | Calibration gap |")
    out.append("|---|---|---|---|")
    for r in report["reliability"]:
        out.append(f"| {r['bin']} | {r['n']} | {r['accuracy'] * 100:.1f}% | {r['gap'] * 100:.1f}% |")

    out.append("\n| Review budget | Docs reviewed | Errors caught (guided) | Expected (random) | ECARB | Error recall |")
    out.append("|---|---|---|---|---|---|")
    for b in report["budgets"]:
        out.append(
            f"| {b['budget'] * 100:.0f}% | {b['documents_reviewed']} | {b['errors_caught_guided']} | "
            f"{b['errors_caught_random_expected']} | {b['ecarb']}x | {b['recall_of_errors'] * 100:.1f}% |"
        )
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild", action="store_true", help="re-run the pipeline instead of using the cache")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--mode", default=settings.CONFIDENCE_AGGREGATION)
    ap.add_argument("--no-write", action="store_true")
    args = ap.parse_args()

    results = load_cache(rebuild=args.rebuild, limit=args.limit)
    thresholds = load_field_thresholds()

    sections = []
    for split in ("all", "tune", "holdout"):
        subset = results if split == "all" else [r for r in results if r.split == split]
        if not subset:
            continue
        label = {"all": "Full set", "tune": "Tune split", "holdout": "Holdout split (sealed)"}[split]
        sections.append(render(evaluate(subset, args.mode, thresholds), f"{label} ({len(subset)} documents)"))

    stamp = datetime.now(timezone.utc).isoformat()
    header = (
        f"\n## Run {stamp}\n\n"
        f"- Extractor: local OCR (Tesseract), `EXTRACTOR_MODE={settings.EXTRACTOR_MODE}`\n"
        f"- Aggregation: `{args.mode}`\n"
        f"- Per-field thresholds: {'yes' if thresholds else 'no (global 0.90 / 0.70)'}\n"
    )
    body = header + "\n".join(sections) + "\n"

    print(body)
    if not args.no_write:
        with open(RESULTS, "a") as fh:
            fh.write(body)
        print(f"appended to {RESULTS}")


if __name__ == "__main__":
    main()
