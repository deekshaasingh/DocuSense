# Load test results

Run against the live DocuSense stack (FastAPI + Celery worker at
concurrency 2 + PostgreSQL 16 + Redis), verified natively in the build
sandbox for the reason described in `docs/failures.md` (the container
registry is not reachable from here). The API, worker and database are the
exact code that ships in `backend/`; only the container runtime differs.

## Run: 2026-11-11, 15 users, 90 s, ramp 2 users/sec, guardrails ENABLED

This run differs from earlier ones in one important way: **authentication
and rate limiting were switched on**. Previous load tests measured an open
API, so they could not say whether the guardrails themselves cost anything.

```bash
AUTH_ENABLED=true API_KEYS=demo-key-1 UPLOAD_RATE_LIMIT=600/minute
API_KEY=demo-key-1 locust -f loadtest/locustfile.py \
    --host http://localhost:8000 --headless -u 15 -r 2 -t 90s --csv results
```

The upload limit was raised to 600/minute for the duration so that the test
measured throughput rather than the limiter; the limiter itself is verified
separately below.

| Endpoint | Requests | Failures | Median | 95th pct | Max | Req/s |
|---|---|---|---|---|---|---|
| `GET /documents?status=needs_review` | 372 | 0 | 7 ms | 16 ms | 31 ms | 4.18 |
| `GET /documents` | 267 | 0 | 7 ms | 16 ms | 27 ms | 3.00 |
| `POST /documents` (upload) | 137 | 0 | 20 ms | 47 ms | 66 ms | 1.54 |
| `GET /metrics` | 128 | 0 | 12 ms | 23 ms | 197 ms | 1.44 |
| `GET /health` | 127 | 0 | 2 ms | 7 ms | 12 ms | 1.43 |
| **Aggregated** | **1031** | **0 (0.00%)** | **8 ms** | **25 ms** | **197 ms** | **11.58** |

**Zero failed requests across all 1031 requests, with auth and rate limiting
active.** Authentication adds a dictionary lookup per request and does not
appear in the latency distribution. The `/metrics` endpoint is the slowest
read because it aggregates over every row in `documents` and `runs`; its
197 ms maximum is a full-table scan on a growing table, and it is the one
endpoint that would need an index or a cached rollup at larger volumes.

## The rate limiter was verified separately

Throughput testing deliberately raises the limit, so the limiter was checked
on its own by restarting the API with `UPLOAD_RATE_LIMIT=5/minute` and
sending seven uploads from one client:

```
req 1: 201    req 5: 201
req 2: 201    req 6: 429
req 3: 201    req 7: 429
req 4: 201
```

Five accepted, the rest rejected with 429. This closes the gap left by the
previous round, in which the limiter shipped without ever being exercised
under traffic.

## What the queue depth revealed

`POST /documents` returning in 20 ms does not mean the *document* was
processed in 20 ms. It means the upload was accepted, validated and handed
to Celery. With one worker at concurrency 2 receiving uploads faster than
two OCR passes can finish, a real backlog built up: immediately after the
90-second test, **57 documents were still `pending` and 2 `processing`**,
out of 139 total.

That is the expected, correct behaviour of an asynchronous pipeline under
load. The alternative, blocking each upload until OCR finished, would have
produced multi-second request latencies and eventual timeouts. Mean
end-to-end processing time was 2.4 s per document during the test, up from
1.7 s when idle, which is queueing delay rather than slower extraction.

**Practical takeaway:** worker concurrency is the capacity knob, not the
API. `docker-compose.yml`'s `worker` service scales horizontally
(`docker compose up -d --scale worker=4`) or takes a higher `--concurrency`.
Nothing in this test suggests the API layer is the bottleneck at this load.

## Reproducing this

```bash
pip install -r loadtest/requirements.txt
# start the stack first (docker compose up -d, or natively)
API_KEY=<your key> locust -f loadtest/locustfile.py \
    --host http://localhost:8000 --headless -u 15 -r 2 -t 90s --csv results
```
