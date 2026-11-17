# Evaluation results

Every run appends here with a UTC timestamp. Old runs are never deleted
(Build Manual, Section 10). Sections below, in reading order: the headline
evaluation, the confidence aggregation ablation, and the per-field threshold
tuning.

## Run 2026-11-11T16:32:57.294713+00:00

- Extractor: local OCR (Tesseract), `EXTRACTOR_MODE=mock`
- Aggregation: `mean`
- Per-field thresholds: yes

### Full set (320 documents)

- Documents: 320
- Aggregation: `mean` , per-field thresholds applied
- Document straight-through rate: 0.0%
- Field automation: 81.2% of values accepted without review, 95.4% of them correct
- Expected Calibration Error (ECE): 0.058
- AUROC: 0.711
- Latency: mean 1.713s, p95 1.908s

| Field | Precision | Recall | N |
|---|---|---|---|
| invoice_number | 99.1% | 99.1% | 320 |
| invoice_date | 100.0% | 100.0% | 320 |
| vendor_name | 94.1% | 94.1% | 320 |
| vendor_gstin | 54.7% | 54.7% | 320 |
| subtotal | 84.4% | 84.4% | 320 |
| tax_amount | 97.2% | 97.2% | 320 |
| total_amount | 80.9% | 80.9% | 320 |

| Line items | Precision | Recall | F1 | Matched | Predicted | Expected |
|---|---|---|---|---|---|---|
| Hungarian matching | 99.2% | 89.4% | 94.1% | 1005 | 1013 | 1124 |

| Confidence bin | N | Empirical accuracy | Calibration gap |
|---|---|---|---|
| 0.1 to 0.2 | 3 | 33.3% | 18.3% |
| 0.2 to 0.3 | 30 | 33.3% | 8.3% |
| 0.3 to 0.4 | 9 | 44.4% | 9.4% |
| 0.4 to 0.5 | 61 | 50.8% | 5.8% |
| 0.5 to 0.6 | 125 | 68.8% | 13.8% |
| 0.6 to 0.7 | 139 | 82.0% | 17.0% |
| 0.7 to 0.8 | 348 | 86.2% | 11.2% |
| 0.8 to 0.9 | 65 | 90.8% | 5.8% |
| 0.9 to 1.0 | 1460 | 92.3% | 2.7% |

| Review budget | Docs reviewed | Errors caught (guided) | Expected (random) | ECARB | Error recall |
|---|---|---|---|---|---|
| 10% | 32 | 54 | 28.7 | 1.882x | 18.8% |
| 20% | 64 | 100 | 57.4 | 1.742x | 34.8% |
| 30% | 96 | 147 | 86.1 | 1.707x | 51.2% |

### Tune split (124 documents)

- Documents: 124
- Aggregation: `mean` , per-field thresholds applied
- Document straight-through rate: 0.0%
- Field automation: 81.1% of values accepted without review, 95.2% of them correct
- Expected Calibration Error (ECE): 0.054
- AUROC: 0.739
- Latency: mean 1.708s, p95 1.875s

| Field | Precision | Recall | N |
|---|---|---|---|
| invoice_number | 99.2% | 99.2% | 124 |
| invoice_date | 100.0% | 100.0% | 124 |
| vendor_name | 93.5% | 93.5% | 124 |
| vendor_gstin | 55.6% | 55.6% | 124 |
| subtotal | 82.3% | 82.3% | 124 |
| tax_amount | 96.0% | 96.0% | 124 |
| total_amount | 83.1% | 83.1% | 124 |

| Line items | Precision | Recall | F1 | Matched | Predicted | Expected |
|---|---|---|---|---|---|---|
| Hungarian matching | 98.7% | 88.4% | 93.3% | 387 | 392 | 438 |

| Confidence bin | N | Empirical accuracy | Calibration gap |
|---|---|---|---|
| 0.1 to 0.2 | 3 | 33.3% | 18.3% |
| 0.2 to 0.3 | 12 | 41.7% | 16.7% |
| 0.3 to 0.4 | 5 | 40.0% | 5.0% |
| 0.4 to 0.5 | 25 | 44.0% | 1.0% |
| 0.5 to 0.6 | 42 | 69.0% | 14.0% |
| 0.6 to 0.7 | 71 | 81.7% | 16.7% |
| 0.7 to 0.8 | 132 | 86.4% | 11.4% |
| 0.8 to 0.9 | 29 | 86.2% | 1.2% |
| 0.9 to 1.0 | 549 | 93.1% | 1.9% |

| Review budget | Docs reviewed | Errors caught (guided) | Expected (random) | ECARB | Error recall |
|---|---|---|---|---|---|
| 10% | 12 | 20 | 11.2 | 1.786x | 17.9% |
| 20% | 25 | 43 | 22.4 | 1.92x | 38.4% |
| 30% | 37 | 60 | 33.6 | 1.786x | 53.6% |

### Holdout split (sealed) (196 documents)

- Documents: 196
- Aggregation: `mean` , per-field thresholds applied
- Document straight-through rate: 0.0%
- Field automation: 81.3% of values accepted without review, 95.6% of them correct
- Expected Calibration Error (ECE): 0.061
- AUROC: 0.693
- Latency: mean 1.715s, p95 1.908s

| Field | Precision | Recall | N |
|---|---|---|---|
| invoice_number | 99.0% | 99.0% | 196 |
| invoice_date | 100.0% | 100.0% | 196 |
| vendor_name | 94.4% | 94.4% | 196 |
| vendor_gstin | 54.1% | 54.1% | 196 |
| subtotal | 85.7% | 85.7% | 196 |
| tax_amount | 98.0% | 98.0% | 196 |
| total_amount | 79.6% | 79.6% | 196 |

| Line items | Precision | Recall | F1 | Matched | Predicted | Expected |
|---|---|---|---|---|---|---|
| Hungarian matching | 99.5% | 90.1% | 94.6% | 618 | 621 | 686 |

| Confidence bin | N | Empirical accuracy | Calibration gap |
|---|---|---|---|
| 0.2 to 0.3 | 18 | 27.8% | 2.8% |
| 0.3 to 0.4 | 4 | 50.0% | 15.0% |
| 0.4 to 0.5 | 36 | 55.6% | 10.6% |
| 0.5 to 0.6 | 83 | 68.7% | 13.7% |
| 0.6 to 0.7 | 68 | 82.4% | 17.4% |
| 0.7 to 0.8 | 216 | 86.1% | 11.1% |
| 0.8 to 0.9 | 36 | 94.4% | 9.4% |
| 0.9 to 1.0 | 911 | 91.9% | 3.1% |

| Review budget | Docs reviewed | Errors caught (guided) | Expected (random) | ECARB | Error recall |
|---|---|---|---|---|---|
| 10% | 20 | 31 | 17.5 | 1.771x | 17.7% |
| 20% | 39 | 56 | 35.0 | 1.6x | 32.0% |
| 30% | 59 | 87 | 52.5 | 1.657x | 49.7% |
## Aggregation ablation 2026-11-11T16:30:29.017431+00:00

Holdout split, 196 documents, 1372 field predictions. Only the aggregator changes; weights, thresholds and extractions are identical.

| Aggregation | ECE (lower better) | AUROC (higher better) | Mean confidence | Straight-through |
|---|---|---|---|---|
| `mean` | 0.061 | 0.693 | 0.862 | 39.8% |
| `first` | 0.045 | 0.637 | 0.911 | 39.8% |
| `min` | 0.195 | 0.692 | 0.665 | 11.2% |

Best calibration: `first` (ECE 0.045). Best discrimination: `mean` (AUROC 0.693).

`margin` is not measurable with the OCR extractor, which exposes no alternative tokens; `min` is reported in its place. See the module docstring.

## Per-field threshold tuning 2026-11-11T16:32:27.136143+00:00

Fitted on the tune split (124 documents), evaluated on the sealed holdout (196 documents). Aggregation `mean`.

Two granularities are reported. Document straight-through counts documents needing no human at all, and document precision is the share of those in which every field is correct. Field automation counts individual values accepted without review, and its precision is the silent-error rate a reviewer actually lives with.

| Policy | Doc straight-through | Doc precision | Field automation | Precision of auto-accepted fields | Never auto-approved |
|---|---|---|---|---|---|
| Global 0.90 / 0.70 (baseline) | 39.8% | 48.7% | 66.4% | 91.9% | none |
| Per-field, target 90% | 0.0% | n/a | 81.3% | 95.6% | vendor_gstin |
| Per-field, target 93% | 0.0% | n/a | 78.5% | 96.1% | vendor_gstin |
| Per-field, target 95% | 0.0% | n/a | 77.0% | 96.9% | vendor_gstin |
| Per-field, target 97% | 0.0% | n/a | 73.0% | 97.5% | vendor_gstin |
| Per-field, target 99% | 0.0% | n/a | 41.8% | 98.1% | vendor_gstin, subtotal, tax_amount |

**Shipped:** per-field thresholds at target 90%, written to `backend/thresholds.json` and loaded automatically by the pipeline.

| Field | Auto-approve | Flag |
|---|---|---|
| invoice_number | 0.40 | 0.20 |
| invoice_date | 0.40 | 0.20 |
| vendor_name | 0.40 | 0.20 |
| vendor_gstin | never | 0.81 |
| subtotal | 0.56 | 0.36 |
| tax_amount | 0.40 | 0.20 |
| total_amount | 0.47 | 0.27 |

On the holdout this accepts 81.3% of field values without review (baseline 66.4%) at 95.6% precision among those accepted (baseline 91.9%). The weak fields are routed to a human by name instead of vetoing the whole document.


## Run 2026-11-17T11:07:31.861868+00:00

- Extractor: local OCR (Tesseract), `EXTRACTOR_MODE=mock`
- Aggregation: `mean`
- Per-field thresholds: yes

### Full set (320 documents)

- Documents: 320
- Aggregation: `mean` , per-field thresholds applied
- Document straight-through rate: 0.0%
- Field automation: 81.2% of values accepted without review, 95.6% of them correct
- Expected Calibration Error (ECE): 0.058
- AUROC: 0.710
- Latency: mean 2.196s, p95 2.521s

| Field | Precision | Recall | N |
|---|---|---|---|
| invoice_number | 100.0% | 100.0% | 320 |
| invoice_date | 100.0% | 100.0% | 320 |
| vendor_name | 94.1% | 94.1% | 320 |
| vendor_gstin | 54.7% | 54.7% | 320 |
| subtotal | 84.4% | 84.4% | 320 |
| tax_amount | 97.2% | 97.2% | 320 |
| total_amount | 80.9% | 80.9% | 320 |

| Line items | Precision | Recall | F1 | Matched | Predicted | Expected |
|---|---|---|---|---|---|---|
| Hungarian matching | 99.2% | 89.4% | 94.1% | 1005 | 1013 | 1124 |

| Confidence bin | N | Empirical accuracy | Calibration gap |
|---|---|---|---|
| 0.1 to 0.2 | 3 | 33.3% | 18.3% |
| 0.2 to 0.3 | 30 | 33.3% | 8.3% |
| 0.3 to 0.4 | 9 | 44.4% | 9.4% |
| 0.4 to 0.5 | 61 | 50.8% | 5.8% |
| 0.5 to 0.6 | 124 | 69.4% | 14.4% |
| 0.6 to 0.7 | 139 | 82.7% | 17.7% |
| 0.7 to 0.8 | 348 | 86.2% | 11.2% |
| 0.8 to 0.9 | 66 | 90.9% | 5.9% |
| 0.9 to 1.0 | 1460 | 92.4% | 2.6% |

| Review budget | Docs reviewed | Errors caught (guided) | Expected (random) | ECARB | Error recall |
|---|---|---|---|---|---|
| 10% | 32 | 53 | 28.4 | 1.866x | 18.7% |
| 20% | 64 | 99 | 56.8 | 1.743x | 34.9% |
| 30% | 96 | 145 | 85.2 | 1.702x | 51.1% |

### Tune split (124 documents)

- Documents: 124
- Aggregation: `mean` , per-field thresholds applied
- Document straight-through rate: 0.0%
- Field automation: 81.1% of values accepted without review, 95.3% of them correct
- Expected Calibration Error (ECE): 0.055
- AUROC: 0.737
- Latency: mean 2.192s, p95 2.480s

| Field | Precision | Recall | N |
|---|---|---|---|
| invoice_number | 100.0% | 100.0% | 124 |
| invoice_date | 100.0% | 100.0% | 124 |
| vendor_name | 93.5% | 93.5% | 124 |
| vendor_gstin | 55.6% | 55.6% | 124 |
| subtotal | 82.3% | 82.3% | 124 |
| tax_amount | 96.0% | 96.0% | 124 |
| total_amount | 83.1% | 83.1% | 124 |

| Line items | Precision | Recall | F1 | Matched | Predicted | Expected |
|---|---|---|---|---|---|---|
| Hungarian matching | 98.7% | 88.4% | 93.3% | 387 | 392 | 438 |

| Confidence bin | N | Empirical accuracy | Calibration gap |
|---|---|---|---|
| 0.1 to 0.2 | 3 | 33.3% | 18.3% |
| 0.2 to 0.3 | 12 | 41.7% | 16.7% |
| 0.3 to 0.4 | 5 | 40.0% | 5.0% |
| 0.4 to 0.5 | 25 | 44.0% | 1.0% |
| 0.5 to 0.6 | 42 | 69.0% | 14.0% |
| 0.6 to 0.7 | 71 | 83.1% | 18.1% |
| 0.7 to 0.8 | 132 | 86.4% | 11.4% |
| 0.8 to 0.9 | 29 | 86.2% | 1.2% |
| 0.9 to 1.0 | 549 | 93.1% | 1.9% |

| Review budget | Docs reviewed | Errors caught (guided) | Expected (random) | ECARB | Error recall |
|---|---|---|---|---|---|
| 10% | 12 | 20 | 11.1 | 1.802x | 18.0% |
| 20% | 25 | 42 | 22.2 | 1.892x | 37.8% |
| 30% | 37 | 59 | 33.3 | 1.772x | 53.1% |

### Holdout split (sealed) (196 documents)

- Documents: 196
- Aggregation: `mean` , per-field thresholds applied
- Document straight-through rate: 0.0%
- Field automation: 81.3% of values accepted without review, 95.8% of them correct
- Expected Calibration Error (ECE): 0.061
- AUROC: 0.692
- Latency: mean 2.199s, p95 2.523s

| Field | Precision | Recall | N |
|---|---|---|---|
| invoice_number | 100.0% | 100.0% | 196 |
| invoice_date | 100.0% | 100.0% | 196 |
| vendor_name | 94.4% | 94.4% | 196 |
| vendor_gstin | 54.1% | 54.1% | 196 |
| subtotal | 85.7% | 85.7% | 196 |
| tax_amount | 98.0% | 98.0% | 196 |
| total_amount | 79.6% | 79.6% | 196 |

| Line items | Precision | Recall | F1 | Matched | Predicted | Expected |
|---|---|---|---|---|---|---|
| Hungarian matching | 99.5% | 90.1% | 94.6% | 618 | 621 | 686 |

| Confidence bin | N | Empirical accuracy | Calibration gap |
|---|---|---|---|
| 0.2 to 0.3 | 18 | 27.8% | 2.8% |
| 0.3 to 0.4 | 4 | 50.0% | 15.0% |
| 0.4 to 0.5 | 36 | 55.6% | 10.6% |
| 0.5 to 0.6 | 82 | 69.5% | 14.5% |
| 0.6 to 0.7 | 68 | 82.4% | 17.4% |
| 0.7 to 0.8 | 216 | 86.1% | 11.1% |
| 0.8 to 0.9 | 37 | 94.6% | 9.6% |
| 0.9 to 1.0 | 911 | 92.0% | 3.0% |

| Review budget | Docs reviewed | Errors caught (guided) | Expected (random) | ECARB | Error recall |
|---|---|---|---|---|---|
| 10% | 20 | 31 | 17.3 | 1.792x | 17.9% |
| 20% | 39 | 56 | 34.6 | 1.618x | 32.4% |
| 30% | 59 | 86 | 51.9 | 1.657x | 49.7% |

## Aggregation ablation 2026-11-17T11:07:37.902630+00:00

Holdout split, 196 documents, 1372 field predictions. Only the aggregator changes; weights, thresholds and extractions are identical.

| Aggregation | ECE (lower better) | AUROC (higher better) | Mean confidence | Straight-through |
|---|---|---|---|---|
| `mean` | 0.061 | 0.692 | 0.862 | 39.8% |
| `first` | 0.045 | 0.637 | 0.911 | 39.8% |
| `min` | 0.196 | 0.691 | 0.665 | 11.2% |

Best calibration: `first` (ECE 0.045). Best discrimination: `mean` (AUROC 0.692).

`margin` is not measurable with the OCR extractor, which exposes no alternative tokens; `min` is reported in its place. See the module docstring.

## Per-field threshold tuning 2026-11-17T11:07:38.719301+00:00

Fitted on the tune split (124 documents), evaluated on the sealed holdout (196 documents). Aggregation `mean`.

Two granularities are reported. Document straight-through counts documents needing no human at all, and document precision is the share of those in which every field is correct. Field automation counts individual values accepted without review, and its precision is the silent-error rate a reviewer actually lives with.

| Policy | Doc straight-through | Doc precision | Field automation | Precision of auto-accepted fields | Never auto-approved |
|---|---|---|---|---|---|
| Global 0.90 / 0.70 (baseline) | 39.8% | 48.7% | 66.4% | 92.0% | none |
| Per-field, target 90% | 0.0% | n/a | 81.3% | 95.8% | vendor_gstin |
| Per-field, target 93% | 0.0% | n/a | 78.5% | 96.3% | vendor_gstin |
| Per-field, target 95% | 0.0% | n/a | 77.0% | 97.1% | vendor_gstin |
| Per-field, target 97% | 0.0% | n/a | 73.0% | 97.7% | vendor_gstin |
| Per-field, target 99% | 0.0% | n/a | 41.8% | 98.4% | vendor_gstin, subtotal, tax_amount |

**Shipped:** per-field thresholds at target 90%, written to `backend/thresholds.json` and loaded automatically by the pipeline.

| Field | Auto-approve | Flag |
|---|---|---|
| invoice_number | 0.40 | 0.20 |
| invoice_date | 0.40 | 0.20 |
| vendor_name | 0.40 | 0.20 |
| vendor_gstin | never | 0.81 |
| subtotal | 0.56 | 0.36 |
| tax_amount | 0.40 | 0.20 |
| total_amount | 0.47 | 0.27 |

On the holdout this accepts 81.3% of field values without review (baseline 66.4%) at 95.8% precision among those accepted (baseline 92.0%). The weak fields are routed to a human by name instead of vetoing the whole document.

## Run 2026-11-17T11:48:03.450296+00:00

- Extractor: local OCR (Tesseract), `EXTRACTOR_MODE=mock`
- Aggregation: `mean`
- Per-field thresholds: yes

### Full set (320 documents)

- Documents: 320
- Aggregation: `mean` , per-field thresholds applied
- Document straight-through rate: 0.0%
- Field automation: 83.1% of values accepted without review, 97.8% of them correct
- Expected Calibration Error (ECE): 0.069
- AUROC: 0.615
- Latency: mean 3.850s, p95 5.029s

| Field | Precision | Recall | N |
|---|---|---|---|
| invoice_number | 95.0% | 95.0% | 320 |
| invoice_date | 100.0% | 100.0% | 320 |
| vendor_name | 96.2% | 96.2% | 320 |
| vendor_gstin | 35.9% | 35.9% | 320 |
| subtotal | 95.9% | 95.9% | 320 |
| tax_amount | 98.1% | 98.1% | 320 |
| total_amount | 93.1% | 93.1% | 320 |

| Line items | Precision | Recall | F1 | Matched | Predicted | Expected |
|---|---|---|---|---|---|---|
| Hungarian matching | 97.4% | 81.5% | 88.8% | 916 | 940 | 1124 |

| Confidence bin | N | Empirical accuracy | Calibration gap |
|---|---|---|---|
| 0.2 to 0.3 | 9 | 33.3% | 8.3% |
| 0.3 to 0.4 | 8 | 25.0% | 10.0% |
| 0.4 to 0.5 | 52 | 57.7% | 12.7% |
| 0.5 to 0.6 | 19 | 68.4% | 13.4% |
| 0.6 to 0.7 | 170 | 77.6% | 12.6% |
| 0.7 to 0.8 | 184 | 92.9% | 17.9% |
| 0.8 to 0.9 | 82 | 87.8% | 2.8% |
| 0.9 to 1.0 | 1716 | 89.9% | 5.1% |

| Review budget | Docs reviewed | Errors caught (guided) | Expected (random) | ECARB | Error recall |
|---|---|---|---|---|---|
| 10% | 32 | 52 | 27.4 | 1.898x | 19.0% |
| 20% | 64 | 86 | 54.8 | 1.569x | 31.4% |
| 30% | 96 | 115 | 82.2 | 1.399x | 42.0% |

### Tune split (124 documents)

- Documents: 124
- Aggregation: `mean` , per-field thresholds applied
- Document straight-through rate: 0.0%
- Field automation: 82.6% of values accepted without review, 97.6% of them correct
- Expected Calibration Error (ECE): 0.078
- AUROC: 0.605
- Latency: mean 3.857s, p95 5.031s

| Field | Precision | Recall | N |
|---|---|---|---|
| invoice_number | 96.0% | 96.0% | 124 |
| invoice_date | 100.0% | 100.0% | 124 |
| vendor_name | 95.2% | 95.2% | 124 |
| vendor_gstin | 36.3% | 36.3% | 124 |
| subtotal | 93.5% | 93.5% | 124 |
| tax_amount | 98.4% | 98.4% | 124 |
| total_amount | 92.7% | 92.7% | 124 |

| Line items | Precision | Recall | F1 | Matched | Predicted | Expected |
|---|---|---|---|---|---|---|
| Hungarian matching | 97.3% | 80.8% | 88.3% | 354 | 364 | 438 |

| Confidence bin | N | Empirical accuracy | Calibration gap |
|---|---|---|---|
| 0.2 to 0.3 | 3 | 33.3% | 8.3% |
| 0.3 to 0.4 | 3 | 66.7% | 31.7% |
| 0.4 to 0.5 | 27 | 59.3% | 14.3% |
| 0.5 to 0.6 | 6 | 66.7% | 11.7% |
| 0.6 to 0.7 | 64 | 81.2% | 16.3% |
| 0.7 to 0.8 | 87 | 90.8% | 15.8% |
| 0.8 to 0.9 | 22 | 86.4% | 1.4% |
| 0.9 to 1.0 | 656 | 89.3% | 5.7% |

| Review budget | Docs reviewed | Errors caught (guided) | Expected (random) | ECARB | Error recall |
|---|---|---|---|---|---|
| 10% | 12 | 19 | 10.9 | 1.743x | 17.4% |
| 20% | 25 | 37 | 21.8 | 1.697x | 33.9% |
| 30% | 37 | 47 | 32.7 | 1.437x | 43.1% |

### Holdout split (sealed) (196 documents)

- Documents: 196
- Aggregation: `mean` , per-field thresholds applied
- Document straight-through rate: 0.0%
- Field automation: 83.4% of values accepted without review, 97.9% of them correct
- Expected Calibration Error (ECE): 0.065
- AUROC: 0.621
- Latency: mean 3.847s, p95 4.872s

| Field | Precision | Recall | N |
|---|---|---|---|
| invoice_number | 94.4% | 94.4% | 196 |
| invoice_date | 100.0% | 100.0% | 196 |
| vendor_name | 96.9% | 96.9% | 196 |
| vendor_gstin | 35.7% | 35.7% | 196 |
| subtotal | 97.4% | 97.4% | 196 |
| tax_amount | 98.0% | 98.0% | 196 |
| total_amount | 93.4% | 93.4% | 196 |

| Line items | Precision | Recall | F1 | Matched | Predicted | Expected |
|---|---|---|---|---|---|---|
| Hungarian matching | 97.6% | 81.9% | 89.1% | 562 | 576 | 686 |

| Confidence bin | N | Empirical accuracy | Calibration gap |
|---|---|---|---|
| 0.2 to 0.3 | 6 | 33.3% | 8.3% |
| 0.3 to 0.4 | 5 | 0.0% | 35.0% |
| 0.4 to 0.5 | 25 | 56.0% | 11.0% |
| 0.5 to 0.6 | 13 | 69.2% | 14.2% |
| 0.6 to 0.7 | 106 | 75.5% | 10.5% |
| 0.7 to 0.8 | 97 | 94.8% | 19.8% |
| 0.8 to 0.9 | 60 | 88.3% | 3.3% |
| 0.9 to 1.0 | 1060 | 90.3% | 4.7% |

| Review budget | Docs reviewed | Errors caught (guided) | Expected (random) | ECARB | Error recall |
|---|---|---|---|---|---|
| 10% | 20 | 31 | 16.5 | 1.879x | 18.8% |
| 20% | 39 | 48 | 33.0 | 1.455x | 29.1% |
| 30% | 59 | 67 | 49.5 | 1.354x | 40.6% |

## Aggregation ablation 2026-11-17T11:49:49.678225+00:00

Holdout split, 196 documents, 1372 field predictions. Only the aggregator changes; weights, thresholds and extractions are identical.

| Aggregation | ECE (lower better) | AUROC (higher better) | Mean confidence | Straight-through |
|---|---|---|---|---|
| `mean` | 0.065 | 0.621 | 0.897 | 35.7% |
| `first` | 0.062 | 0.595 | 0.919 | 35.7% |
| `min` | 0.182 | 0.622 | 0.692 | 3.6% |

Best calibration: `first` (ECE 0.062). Best discrimination: `min` (AUROC 0.622).

`margin` is not measurable with the OCR extractor, which exposes no alternative tokens; `min` is reported in its place. See the module docstring.

## Per-field threshold tuning 2026-11-17T11:49:59.060494+00:00

Fitted on the tune split (124 documents), evaluated on the sealed holdout (196 documents). Aggregation `mean`.

Two granularities are reported. Document straight-through counts documents needing no human at all, and document precision is the share of those in which every field is correct. Field automation counts individual values accepted without review, and its precision is the silent-error rate a reviewer actually lives with.

| Policy | Doc straight-through | Doc precision | Field automation | Precision of auto-accepted fields | Never auto-approved |
|---|---|---|---|---|---|
| Global 0.90 / 0.70 (baseline) | 35.7% | 27.1% | 77.3% | 90.3% | none |
| Per-field, target 90% | 0.0% | n/a | 84.9% | 97.4% | vendor_gstin |
| Per-field, target 93% | 0.0% | n/a | 84.9% | 97.4% | vendor_gstin |
| Per-field, target 95% | 0.0% | n/a | 84.8% | 97.6% | vendor_gstin |
| Per-field, target 97% | 0.0% | n/a | 83.5% | 98.3% | vendor_gstin |
| Per-field, target 99% | 0.0% | n/a | 66.6% | 99.3% | vendor_gstin |

**Shipped:** per-field thresholds at target 90%, written to `backend/thresholds.json` and loaded automatically by the pipeline.

| Field | Auto-approve | Flag |
|---|---|---|
| invoice_number | 0.40 | 0.20 |
| invoice_date | 0.40 | 0.20 |
| vendor_name | 0.40 | 0.20 |
| vendor_gstin | never | 0.81 |
| subtotal | 0.40 | 0.20 |
| tax_amount | 0.40 | 0.20 |
| total_amount | 0.40 | 0.20 |

On the holdout this accepts 84.9% of field values without review (baseline 77.3%) at 97.4% precision among those accepted (baseline 90.3%). The weak fields are routed to a human by name instead of vetoing the whole document.

## Run 2026-11-17T11:56:04.765906+00:00

- Extractor: local OCR (Tesseract), `EXTRACTOR_MODE=mock`
- Aggregation: `mean`
- Per-field thresholds: yes

### Full set (320 documents)

- Documents: 320
- Aggregation: `mean` , per-field thresholds applied
- Document straight-through rate: 0.0%
- Field automation: 85.0% of values accepted without review, 97.0% of them correct
- Expected Calibration Error (ECE): 0.069
- AUROC: 0.615
- Latency: mean 3.850s, p95 5.029s

| Field | Precision | Recall | N |
|---|---|---|---|
| invoice_number | 95.0% | 95.0% | 320 |
| invoice_date | 100.0% | 100.0% | 320 |
| vendor_name | 96.2% | 96.2% | 320 |
| vendor_gstin | 35.9% | 35.9% | 320 |
| subtotal | 95.9% | 95.9% | 320 |
| tax_amount | 98.1% | 98.1% | 320 |
| total_amount | 93.1% | 93.1% | 320 |

| Line items | Precision | Recall | F1 | Matched | Predicted | Expected |
|---|---|---|---|---|---|---|
| Hungarian matching | 97.4% | 81.5% | 88.8% | 916 | 940 | 1124 |

| Confidence bin | N | Empirical accuracy | Calibration gap |
|---|---|---|---|
| 0.2 to 0.3 | 9 | 33.3% | 8.3% |
| 0.3 to 0.4 | 8 | 25.0% | 10.0% |
| 0.4 to 0.5 | 52 | 57.7% | 12.7% |
| 0.5 to 0.6 | 19 | 68.4% | 13.4% |
| 0.6 to 0.7 | 170 | 77.6% | 12.6% |
| 0.7 to 0.8 | 184 | 92.9% | 17.9% |
| 0.8 to 0.9 | 82 | 87.8% | 2.8% |
| 0.9 to 1.0 | 1716 | 89.9% | 5.1% |

| Review budget | Docs reviewed | Errors caught (guided) | Expected (random) | ECARB | Error recall |
|---|---|---|---|---|---|
| 10% | 32 | 52 | 27.4 | 1.898x | 19.0% |
| 20% | 64 | 86 | 54.8 | 1.569x | 31.4% |
| 30% | 96 | 115 | 82.2 | 1.399x | 42.0% |

### Tune split (124 documents)

- Documents: 124
- Aggregation: `mean` , per-field thresholds applied
- Document straight-through rate: 0.0%
- Field automation: 85.0% of values accepted without review, 96.3% of them correct
- Expected Calibration Error (ECE): 0.078
- AUROC: 0.605
- Latency: mean 3.857s, p95 5.031s

| Field | Precision | Recall | N |
|---|---|---|---|
| invoice_number | 96.0% | 96.0% | 124 |
| invoice_date | 100.0% | 100.0% | 124 |
| vendor_name | 95.2% | 95.2% | 124 |
| vendor_gstin | 36.3% | 36.3% | 124 |
| subtotal | 93.5% | 93.5% | 124 |
| tax_amount | 98.4% | 98.4% | 124 |
| total_amount | 92.7% | 92.7% | 124 |

| Line items | Precision | Recall | F1 | Matched | Predicted | Expected |
|---|---|---|---|---|---|---|
| Hungarian matching | 97.3% | 80.8% | 88.3% | 354 | 364 | 438 |

| Confidence bin | N | Empirical accuracy | Calibration gap |
|---|---|---|---|
| 0.2 to 0.3 | 3 | 33.3% | 8.3% |
| 0.3 to 0.4 | 3 | 66.7% | 31.7% |
| 0.4 to 0.5 | 27 | 59.3% | 14.3% |
| 0.5 to 0.6 | 6 | 66.7% | 11.7% |
| 0.6 to 0.7 | 64 | 81.2% | 16.3% |
| 0.7 to 0.8 | 87 | 90.8% | 15.8% |
| 0.8 to 0.9 | 22 | 86.4% | 1.4% |
| 0.9 to 1.0 | 656 | 89.3% | 5.7% |

| Review budget | Docs reviewed | Errors caught (guided) | Expected (random) | ECARB | Error recall |
|---|---|---|---|---|---|
| 10% | 12 | 19 | 10.9 | 1.743x | 17.4% |
| 20% | 25 | 37 | 21.8 | 1.697x | 33.9% |
| 30% | 37 | 47 | 32.7 | 1.437x | 43.1% |

### Holdout split (sealed) (196 documents)

- Documents: 196
- Aggregation: `mean` , per-field thresholds applied
- Document straight-through rate: 0.0%
- Field automation: 84.9% of values accepted without review, 97.4% of them correct
- Expected Calibration Error (ECE): 0.065
- AUROC: 0.621
- Latency: mean 3.847s, p95 4.872s

| Field | Precision | Recall | N |
|---|---|---|---|
| invoice_number | 94.4% | 94.4% | 196 |
| invoice_date | 100.0% | 100.0% | 196 |
| vendor_name | 96.9% | 96.9% | 196 |
| vendor_gstin | 35.7% | 35.7% | 196 |
| subtotal | 97.4% | 97.4% | 196 |
| tax_amount | 98.0% | 98.0% | 196 |
| total_amount | 93.4% | 93.4% | 196 |

| Line items | Precision | Recall | F1 | Matched | Predicted | Expected |
|---|---|---|---|---|---|---|
| Hungarian matching | 97.6% | 81.9% | 89.1% | 562 | 576 | 686 |

| Confidence bin | N | Empirical accuracy | Calibration gap |
|---|---|---|---|
| 0.2 to 0.3 | 6 | 33.3% | 8.3% |
| 0.3 to 0.4 | 5 | 0.0% | 35.0% |
| 0.4 to 0.5 | 25 | 56.0% | 11.0% |
| 0.5 to 0.6 | 13 | 69.2% | 14.2% |
| 0.6 to 0.7 | 106 | 75.5% | 10.5% |
| 0.7 to 0.8 | 97 | 94.8% | 19.8% |
| 0.8 to 0.9 | 60 | 88.3% | 3.3% |
| 0.9 to 1.0 | 1060 | 90.3% | 4.7% |

| Review budget | Docs reviewed | Errors caught (guided) | Expected (random) | ECARB | Error recall |
|---|---|---|---|---|---|
| 10% | 20 | 31 | 16.5 | 1.879x | 18.8% |
| 20% | 39 | 48 | 33.0 | 1.455x | 29.1% |
| 30% | 59 | 67 | 49.5 | 1.354x | 40.6% |
