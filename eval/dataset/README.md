# Evaluation dataset

This folder holds the ground-truth JSON for all 320 evaluation documents
plus `_manifest.json`, which records each document's degradation and its
tune/holdout split assignment.

The rendered PNG images are **not** committed, because they are large and
fully reproducible. `generate_dataset.py` is seeded (`SEED = 20261111`), so

    python3 generate_dataset.py

regenerates byte-identical images and the identical ground truth, manifest
and splits. Run it once before `run_eval.py`.
