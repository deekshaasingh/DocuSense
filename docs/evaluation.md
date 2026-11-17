# How we test, and why

The Build Manual calls this part "not optional": *"If you are short on
time... Do not cut the evaluation harness. That is the project."*

## The test set

`eval/dataset/` holds 320 documents plus one ground-truth JSON each, written
independently of anything the extractor produces. `eval/generate_dataset.py`
builds it from a fixed seed, so the whole set is reproducible.

Each document is rendered from randomly generated but internally consistent
invoice data: line items that really sum to the subtotal, tax at a fixed
18% rate, dates in a plausible range, and syntactically valid GSTINs. Most
documents are then deliberately degraded (rotation, Gaussian blur, pixel
noise, flattened contrast, or rotation and blur together) to stand in for a
crooked phone photo or a poor scan. `eval/dataset/_manifest.json` records
the degradation and the split for every document, so failures can be sliced
by cause.

### Tune and holdout splits

The manual's rule 2 is "never test on documents you tuned with." The
manifest assigns roughly 40% of documents to a `tune` split and the rest to
a sealed `holdout` split. `eval/tune_thresholds.py` only ever reads the tune
split; every headline number is reported for all three views (full set, tune,
holdout) so the difference is visible rather than hidden.

### Why synthetic, and what that costs

There is no live business generating real paperwork for this project, and
real invoices carry vendor and GSTIN data that cannot be redistributed. The
synthetic set exists to exercise the *pipeline* end to end with numbers
attached, and to give the confidence-routing logic genuine failure cases to
catch.

It is **not** a claim that accuracy on real scanned invoices matches these
figures. Real documents have layout diversity, logos, stamps, handwriting
and multi-column tables this generator does not produce. Before trusting the
system on real documents, rebuild `eval/dataset/` from 100+ real invoices
with human-typed ground truth.

## What gets measured

`eval/run_eval.py` imports the pipeline modules directly rather than going
through the API, so a full run needs no Postgres, Redis or Celery. The first
run caches every document's raw evidence (token certainties, second-opinion
agreement, rule outcomes) to `.eval_cache.pkl`; every later experiment
re-scores from that cache instead of re-running OCR, which is what makes the
ablation and threshold tuning cheap enough to iterate on.

- **Precision and recall per field**, for each of the seven scalar fields.
  Exact match after whitespace and case normalisation for text, and a
  tolerance of 0.02 for currency. Note that precision equals recall here by
  construction: the extractor never abstains, so the count of returned values
  always equals the count of expected values. Abstention is expressed through
  the confidence score and the routing policy, not through a null prediction.
- **Line items**, via Hungarian assignment (`eval/metrics.py`). v1 excluded
  these from scoring because comparing variable-length lists of structured
  rows needs an alignment step. That step is now implemented: build a
  similarity matrix over description text (40%) and the three numbers (60%),
  solve the optimal assignment with `scipy.optimize.linear_sum_assignment`,
  and count a pair as matched only when similarity clears 0.75.
- **Straight-through rate**, the share of documents auto-approved with zero
  flagged fields, i.e. needing no human at all.
- **Calibration**, as a binned reliability table plus Expected Calibration
  Error: the N-weighted mean gap between each bin's observed accuracy and its
  midpoint.
- **AUROC**, how well the confidence score separates correct extractions
  from incorrect ones. ECE and AUROC answer different questions: a score can
  be well calibrated and useless at ranking, or a good ranker that is
  systematically over-confident.
- **Error capture against random sampling (ECARB-style)**, at review budgets
  of 10%, 20% and 30%. Straight-through rate counts the documents that needed
  no human; it says nothing about whether the documents sent for review were
  the ones that were actually wrong. This metric does: it reports how many
  more errors a confidence-guided reviewer catches than one sampling the same
  number of documents at random. A ratio of 1.0 means confidence added
  nothing. The definition follows ConfBench (arXiv:2608.01792).
- **Latency**, wall-clock seconds per document through the full pipeline.

Every run appends to `eval/RESULTS.md` with a UTC timestamp. Old runs are
never deleted, so regressions stay visible.

## The metrics themselves are tested

`backend/tests/test_eval_metrics.py` checks the measuring instruments, not
just the system: a perfectly calibrated input must give ECE near zero, an
inverted one must give a large ECE, AUROC must be 1.0 on perfect separation
and undefined on a single-class input, error capture must return 1.0 when
confidence is uninformative, and the line-item matcher must align rows that
arrive out of order while rejecting rows whose numbers are wrong. A wrong
metric is worse than no metric, because it looks like evidence.

## Threshold tuning

`config.AUTO_APPROVE_THRESHOLD` (0.90) and `FLAG_THRESHOLD` (0.70) are the
manual's starting guesses. `eval/tune_thresholds.py` replaces them with
per-field bars fitted on the tune split: for each field it picks the lowest
auto-approve threshold whose precision among auto-approved values reaches
99%, then sets the flag bar 0.20 below it. Fields that cannot reach the
target at any threshold are marked never-auto-approve rather than given a
bar that would let errors through.

The output is written to `backend/thresholds.json` and picked up
automatically by `pipeline/confidence.py`. A missing or malformed file falls
back to the global thresholds, so the pipeline cannot be taken down by a bad
tuning run.

The rule that matters: thresholds are never tuned downward to make the
straight-through rate look better. A higher automation rate bought by
relaxing the bar is exactly the failure this project exists to prevent.
