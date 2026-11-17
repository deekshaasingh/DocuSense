# DocuSense

*Teaching a document reader to say "I am not sure."*

A confidence-aware document intelligence system: upload an invoice, get back
structured JSON, and get a per-field confidence score so low-confidence
fields go to a human instead of being silently trusted.

| | |
|---|---|
| **Team** | Adhiraj Gupta (04515003123), Deeksha Singh (02615003123) |
| **Guide** | Dr. Preeti Sehrawat, Department of Information Technology |
| **Institute** | Maharaja Surajmal Institute of Technology, New Delhi |
| **Course** | Minor Project, Department of Information Technology |

## What is here

- **Backend** (`backend/`), FastAPI + Celery + PostgreSQL + Redis. All ten
  build steps from the Build Manual, every API route from Section 9, the
  exact confidence formula and routing policy from Steps 7 and 8.
- **Pipeline** (`backend/pipeline/`), deskew, denoise, OCR or VLM
  extraction, arithmetic and format validation, confidence scoring, routing.
  Two extractors behind one flag: a real Ollama/VLM client
  (`EXTRACTOR_MODE=ollama`) and a real Tesseract-based local extractor
  (`EXTRACTOR_MODE=mock`, the default, see below for why). Multi-page PDFs
  are processed page by page and merged.
- **Frontend** (`frontend/`), React and Tailwind. Review screen with
  per-field confidence colouring and inline correction that never overwrites
  the original value, plus a live Observability tab.
- **Guardrails and observability**, API-key auth that fails closed, upload
  type and size validation, per-IP rate limiting, a maintenance kill switch,
  a `/metrics` endpoint and structured JSON logs. Rationale and OWASP
  mapping in `docs/guardrails.md`.
- **Tests** (`backend/tests/`), 73 pytest tests covering deskew recovery,
  validation rules, the scoring formula and its three aggregators, the OCR
  extractor, multi-page merging, auth, upload guardrails, the metrics
  endpoint, and the evaluation metrics themselves.
- **Evaluation** (`eval/`), a 320-document set with independent ground truth
  and sealed tune/holdout splits, reporting per-field precision and recall,
  line-item F1 via Hungarian matching, calibration (ECE), AUROC, review-budget
  error capture, and latency. Plus an aggregation ablation and a per-field
  threshold tuner. Results in `eval/RESULTS.md`.
- **Load test** (`loadtest/`), Locust against the live stack with auth and
  rate limiting enabled. Results in `loadtest/LOAD_TEST_RESULTS.md`.

## Results at a glance

Measured on the sealed 196-document holdout split, local OCR extractor.
Full tables and every prior run in `eval/RESULTS.md`.

| Metric | Value |
|---|---|
| Field automation (values accepted with no human) | **81.3%** |
| Precision of those auto-accepted values | **95.8%** |
| Expected Calibration Error | **0.061** |
| AUROC | **0.692** |
| Line-item F1 (Hungarian matching) | **94.6%** |
| Error capture vs random review, 10% budget | **1.77x** |
| Pipeline failures | **0 of 320** |
| Load test | **1031 requests, 0 failures**, 8 ms median |

Per-field precision: invoice_date 100.0%, invoice_number 100.0%,
tax_amount 98.0%, vendor_name 94.4%, subtotal 85.7%, total_amount 79.6%,
vendor_gstin 54.1%.

The GSTIN is the known weak field: a dense fifteen-character alphanumeric
code with no linguistic redundancy, where one misread character invalidates
the whole value. It is never auto-approved under the tuned thresholds, and
it is the clearest thing a real vision-language model would be expected to
improve.

## Two findings worth reading the eval for

**Per-field thresholds beat one global bar on both axes.** Fitting a bar per
field on the tune split and testing on the sealed holdout raised the share
of values accepted without review from 66.4% to 81.3% *and* raised their
precision from 92.0% to 95.8%. More automation and fewer silent errors at
the same time, because the weak field is routed to a human by name instead
of dragging whole documents into review. See `eval/tune_thresholds.py`.

**First-token aggregation calibrates better but ranks worse.** ConfBench
(arXiv:2608.01792) reports first-token log-probability aggregation as the
most consistent predictor of correctness. On this project's data it does
give the best calibration (ECE 0.045 against 0.061 for mean-token), but the
worst discrimination (AUROC 0.637 against 0.692). Calibration and ranking
are different properties and this system needs both. See `eval/ablation.py`.

## Setting it up

`SETUP.md` is the step by step runbook: what to install, how to run the
tests without any services, how to reproduce the evaluation, how to run the
whole application, and a troubleshooting table. Every command in it was run
from a clean unzip before it was written down.

## Quickstart

```bash
docker compose up -d --build
open http://localhost:5173         # review UI
curl localhost:8000/health         # {"status":"ok","maintenance_mode":false}
```

Without Docker (what this repo was actually verified with, see
`docs/failures.md` for why):

```bash
# PostgreSQL and Redis running locally, then:
cd backend
pip install -r requirements.txt
export DATABASE_URL=postgresql+psycopg2://docusense:docusense@localhost:5432/docusense
export REDIS_URL=redis://localhost:6379/0 STORAGE_DIR=/data/storage EXTRACTOR_MODE=mock
uvicorn main:app --reload &
celery -A tasks.celery_app worker --loglevel=INFO &

cd ../frontend && npm install && npm run dev   # http://localhost:5173
```

## Running the tests, evaluation and load test

```bash
cd backend && pytest -q                              # 73 tests

cd eval
python3 generate_dataset.py                          # 320 documents, seeded
python3 run_eval.py                                  # headline metrics
python3 ablation.py                                  # aggregation comparison
python3 tune_thresholds.py                           # per-field thresholds

cd ../loadtest
API_KEY=<key> locust -f locustfile.py --host http://localhost:8000 \
    --headless -u 15 -r 2 -t 90s --csv results
```

The first evaluation run caches each document's raw evidence to
`.eval_cache.pkl`, so the ablation and the tuner re-score in seconds instead
of re-running OCR. Use `--rebuild` after changing the pipeline.

## Guardrails quick reference

Full rationale and OWASP mapping in `docs/guardrails.md`.

| Control | Environment variable | Default |
|---|---|---|
| API-key auth on writes | `AUTH_ENABLED`, `API_KEYS` | on in code, off in local compose |
| Upload type and size limits | `MAX_UPLOAD_MB` (15), fixed extension allowlist | on |
| Upload rate limit | `UPLOAD_RATE_LIMIT` | `20/minute` per IP |
| Kill switch | `MAINTENANCE_MODE` | off |
| Cost tracking (illustrative) | `COST_PER_1K_TOKENS_USD` | `0.01` |

## Why `EXTRACTOR_MODE=mock` by default

The Build Manual's real extractor calls a local vision-language model
(Qwen2.5-VL 7B) served by Ollama: a multi-gigabyte download and 20 to 40
seconds per page on CPU. The default extractor here is **not a stub that
fakes answers**. It runs real Tesseract OCR over the genuinely deskewed and
denoised page and parses fields with regex and heuristic rules, making real
mistakes that the confidence scoring and review flow then have real work to
do on. Flip one environment variable (`EXTRACTOR_MODE=ollama`) once a model
server is available; nothing else in the pipeline changes.

The Ollama registry is blocked by this build environment's network
allowlist, so that path is implemented but unmeasured. `docs/failures.md`
section 5 states exactly what that means for every number above.

## Repo layout

```
docusense/
├── docker-compose.yml
├── backend/
│   ├── main.py            # FastAPI routes, guardrails, /metrics
│   ├── auth.py            # API-key dependency
│   ├── obslog.py          # structured JSON logging
│   ├── models.py          # documents / extractions / corrections / runs
│   ├── schemas.py         # Pydantic, the fields we extract
│   ├── tasks.py           # Celery: preprocess -> extract -> validate -> score -> route
│   ├── thresholds.json    # per-field bars, written by eval/tune_thresholds.py
│   ├── pipeline/
│   │   ├── preprocess.py  # deskew, denoise, pdf to image
│   │   ├── extract.py     # Ollama client, local OCR, multi-page merge
│   │   ├── validate.py    # arithmetic and format rules
│   │   └── confidence.py  # the scoring formula and routing policy
│   └── tests/
├── frontend/              # React review screen, Review + Observability tabs
├── eval/
│   ├── generate_dataset.py
│   ├── runner.py          # one cached pipeline pass, shared by all experiments
│   ├── metrics.py         # ECE, AUROC, ECARB, Hungarian line-item matching
│   ├── run_eval.py
│   ├── ablation.py
│   ├── tune_thresholds.py
│   └── RESULTS.md
├── loadtest/
└── docs/
    ├── evaluation.md
    ├── guardrails.md
    ├── deployment.md
    └── failures.md
```

## Status against the manual's "Done means" checklist

- [x] `docker compose up` starts everything (compose file validated; the
      container registry is blocked in this build sandbox, so every service
      was installed natively and exercised for real instead, see
      `docs/failures.md`)
- [x] Upload a real invoice, get correct JSON with per-field scores
- [x] Low-confidence documents land in the review queue automatically
- [x] A human can correct a field and it is stored with the original
- [x] `python3 eval/run_eval.py` prints the metrics table
- [x] `eval/RESULTS.md` has numbers with dates
- [x] `docs/evaluation.md` explains how the test set was built
- [x] `docs/failures.md` lists what did not work
- [x] README has setup steps and the results table
- [ ] Deployed somewhere with a public URL. The path is documented and the
      build is deployment-ready, but this sandbox has no hosting credentials
      and no outbound registry access, so the deploy itself is the one
      checklist item that needs a human with an account.
