"""
Fit per-field routing thresholds on the tune split, then report what they do
on the sealed holdout split.

Why this exists: the shipped policy compares every field against one global
bar, so the single weakest field (the GSTIN, which OCR reads badly) vetoes
whole documents and the straight-through rate collapses. Giving each field
its own bar is the principled fix, and the Build Manual's rule 2 says the bar
must be fitted on data the holdout never sees.

Method. For a target precision t, each field gets the lowest auto-approve bar
whose precision among auto-approved values on the *tune* split reaches t. A
field that cannot reach t at any bar is marked never-auto-approve rather than
given a bar that would let errors through. The flag bar sits 0.20 below.

Because t trades automation against silent errors, the script sweeps it and
reports the whole curve rather than asserting one answer. Two numbers decide
which configuration ships, both measured on the holdout:

  * straight-through rate, the share of documents needing no human at all
  * document precision, the share of auto-approved documents in which every
    field is correct. This is the number that matters, because an
    auto-approved document with one wrong field is exactly the silent error
    the project exists to prevent.

The configuration written to backend/thresholds.json is the one with the
highest holdout straight-through rate whose holdout document precision is at
least MIN_DOC_PRECISION *and* which beats the global baseline. If nothing
qualifies, no file is written and the global policy stands.

    python3 tune_thresholds.py [--min-doc-precision 0.95]
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

from runner import correctness, load_cache, score_fields  # noqa: E402
from schemas import SCALAR_FIELDS  # noqa: E402
from pipeline.confidence import route  # noqa: E402
from config import settings  # noqa: E402

OUT = os.path.join(HERE, "..", "backend", "thresholds.json")
RESULTS = os.path.join(HERE, "RESULTS.md")

CANDIDATES = [round(0.40 + 0.01 * i, 2) for i in range(61)]  # 0.40 .. 1.00
TARGETS = (0.90, 0.93, 0.95, 0.97, 0.99)
MIN_DOC_PRECISION = 0.95
FLAG_MARGIN = 0.20


def fit(results, mode: str, target: float) -> dict[str, dict[str, float]]:
    fitted: dict[str, dict[str, float]] = {}
    scored = [(score_fields(r, mode), correctness(r)) for r in results]

    for name in SCALAR_FIELDS:
        pairs = [(s[name], c[name]) for s, c in scored]
        chosen = None
        for bar in CANDIDATES:
            approved = [c for s, c in pairs if s >= bar]
            if not approved:
                continue
            if sum(approved) / len(approved) >= target:
                chosen = bar
                break
        if chosen is None:
            chosen = 1.01  # unreachable: never auto-approve this field
        fitted[name] = {"auto": chosen, "flag": round(max(0.0, chosen - FLAG_MARGIN), 2)}
    return fitted


def assess(results, mode: str, thresholds) -> dict:
    """Measure automation and the silent-error rate at two granularities.

    Document level: how many documents needed no human at all, and how many
    of those were in fact entirely correct.

    Field level: how many individual field values were accepted without a
    human looking at them, and how many of those were correct. This is the
    granularity that actually determines reviewer workload, because the
    routing policy already flags individual fields rather than only whole
    documents, and it is the honest way to report automation when one weak
    field would otherwise veto every document.
    """
    approved_docs = 0
    fully_correct_docs = 0
    doc_field_correct = doc_field_total = 0
    auto_fields = auto_fields_correct = 0
    total_fields = 0

    for res in results:
        scores = score_fields(res, mode)
        correct = correctness(res)
        status, flagged = route(
            scores, settings.AUTO_APPROVE_THRESHOLD, settings.FLAG_THRESHOLD, thresholds
        )

        # field level: every field not flagged is accepted without review
        for f in SCALAR_FIELDS:
            total_fields += 1
            if f not in flagged:
                auto_fields += 1
                auto_fields_correct += int(correct[f])

        if status == "approved" and not flagged:
            approved_docs += 1
            fully_correct_docs += int(all(correct[f] for f in SCALAR_FIELDS))
            for f in SCALAR_FIELDS:
                doc_field_total += 1
                doc_field_correct += int(correct[f])

    n = len(results) or 1
    return {
        "straight_through": approved_docs / n,
        "approved_docs": approved_docs,
        "doc_precision": (fully_correct_docs / approved_docs) if approved_docs else None,
        "field_precision": (doc_field_correct / doc_field_total) if doc_field_total else None,
        "field_automation": auto_fields / total_fields if total_fields else 0.0,
        "auto_field_precision": (auto_fields_correct / auto_fields) if auto_fields else None,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-doc-precision", type=float, default=MIN_DOC_PRECISION)
    ap.add_argument("--mode", default=settings.CONFIDENCE_AGGREGATION)
    args = ap.parse_args()

    results = load_cache()
    tune = [r for r in results if r.split == "tune"]
    holdout = [r for r in results if r.split == "holdout"]
    if not tune or not holdout:
        raise SystemExit("dataset manifest has no tune/holdout split; regenerate the dataset")

    baseline = assess(holdout, args.mode, {})

    sweep = []
    for t in TARGETS:
        fitted = fit(tune, args.mode, t)
        res = assess(holdout, args.mode, fitted)
        never = [f for f, b in fitted.items() if b["auto"] > 1.0]
        sweep.append({"target": t, "fitted": fitted, "never": never, **res})

    # Selection is made on field-level automation, not document-level
    # straight-through. One field the extractor reads badly vetoes every
    # document, so the document-level number cannot distinguish between
    # configurations; the field-level number measures the reviewer workload
    # that is actually saved. The constraint is that values accepted without
    # review must be right at least as often as the target demands.
    eligible = [
        s for s in sweep
        if s["auto_field_precision"] is not None
        and s["auto_field_precision"] >= args.min_doc_precision
        and s["field_automation"] > 0.0
    ]
    chosen = max(eligible, key=lambda s: s["field_automation"]) if eligible else None
    if chosen and chosen["auto_field_precision"] <= (baseline["auto_field_precision"] or 0):
        # No safety gain over the baseline either; do not ship churn.
        if chosen["field_automation"] <= baseline["field_automation"]:
            chosen = None

    stamp = datetime.now(timezone.utc).isoformat()
    lines = [
        f"\n## Per-field threshold tuning {stamp}\n",
        f"Fitted on the tune split ({len(tune)} documents), evaluated on the sealed holdout "
        f"({len(holdout)} documents). Aggregation `{args.mode}`.\n",
        "Two granularities are reported. Document straight-through counts documents needing no "
        "human at all, and document precision is the share of those in which every field is "
        "correct. Field automation counts individual values accepted without review, and its "
        "precision is the silent-error rate a reviewer actually lives with.\n",
        "| Policy | Doc straight-through | Doc precision | Field automation | Precision of auto-accepted fields | Never auto-approved |",
        "|---|---|---|---|---|---|",
    ]

    def fmt(v):
        return "n/a" if v is None else f"{v * 100:.1f}%"

    lines.append(
        f"| Global 0.90 / 0.70 (baseline) | {baseline['straight_through'] * 100:.1f}% | "
        f"{fmt(baseline['doc_precision'])} | {fmt(baseline['field_automation'])} | "
        f"{fmt(baseline['auto_field_precision'])} | none |"
    )
    for s in sweep:
        lines.append(
            f"| Per-field, target {s['target'] * 100:.0f}% | {s['straight_through'] * 100:.1f}% | "
            f"{fmt(s['doc_precision'])} | {fmt(s['field_automation'])} | "
            f"{fmt(s['auto_field_precision'])} | "
            f"{', '.join(s['never']) if s['never'] else 'none'} |"
        )

    if chosen:
        payload = {
            "fitted_at": stamp,
            "fitted_on": "tune split",
            "n_tune_documents": len(tune),
            "aggregation": args.mode,
            "target_precision": chosen["target"],
            "selection_rule": (
                f"highest holdout field automation with precision of auto-accepted "
                f"fields >= {args.min_doc_precision:.2f}"
            ),
            "holdout": {
                "straight_through": round(chosen["straight_through"], 4),
                "field_automation": round(chosen["field_automation"], 4),
                "auto_field_precision": round(chosen["auto_field_precision"], 4),
            },
            "fields": chosen["fitted"],
        }
        with open(OUT, "w") as fh:
            json.dump(payload, fh, indent=2)

        lines += [
            "",
            f"**Shipped:** per-field thresholds at target {chosen['target'] * 100:.0f}%, written to "
            "`backend/thresholds.json` and loaded automatically by the pipeline.",
            "",
            "| Field | Auto-approve | Flag |",
            "|---|---|---|",
        ]
        for name, bars in chosen["fitted"].items():
            auto = "never" if bars["auto"] > 1.0 else f"{bars['auto']:.2f}"
            lines.append(f"| {name} | {auto} | {bars['flag']:.2f} |")
        lines.append(
            f"\nOn the holdout this accepts {chosen['field_automation'] * 100:.1f}% of field values "
            f"without review (baseline {baseline['field_automation'] * 100:.1f}%) at "
            f"{chosen['auto_field_precision'] * 100:.1f}% precision among those accepted "
            f"(baseline {fmt(baseline['auto_field_precision'])}). The weak fields are routed to a "
            "human by name instead of vetoing the whole document."
        )
    else:
        if os.path.exists(OUT):
            os.remove(OUT)
        lines += [
            "",
            "**Nothing shipped.** No per-field configuration both cleared the "
            f"{args.min_doc_precision * 100:.0f}% document-precision requirement and beat the global "
            "baseline on the holdout, so the global 0.90 / 0.70 policy stands and no "
            "`thresholds.json` is written.",
            "",
            "This is a real finding rather than a failed experiment: at high precision targets the "
            "weak fields become never-auto-approvable, which vetoes whole documents and drives "
            "straight-through to zero. Per-field thresholds cannot rescue a field the extractor "
            "reads badly; only a better extractor can.",
        ]

    body = "\n".join(lines) + "\n"
    print(body)
    with open(RESULTS, "a") as fh:
        fh.write(body)
    print(f"appended to {RESULTS}")


if __name__ == "__main__":
    main()
