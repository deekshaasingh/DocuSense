# Guardrails and observability

The security and reliability controls that sit on top of the extraction
pipeline, why each exists, and how each maps to the
[OWASP Top 10 for LLM Applications](https://owasp.org/www-project-top-10-for-large-language-model-applications/).

Pipeline-level guardrails (schema validation, arithmetic and format rules)
are covered in `docs/evaluation.md`. This document is specifically the
request-layer and operational controls.

## 1. Authentication (`backend/auth.py`)

A static `X-API-Key` allowlist guards every route that writes data or spends
inference budget: `POST /documents` and `POST /documents/{id}/corrections`.
Read routes stay open, on the assumption that visibility into the review
queue is safe to share but spending compute and writing data is not.

- `AUTH_ENABLED` (default `true` in code, `false` in the single-user local
  compose file) fails **closed**: if it is on and `API_KEYS` is empty, every
  request gets a 500 explaining why, rather than silently accepting traffic.
- `API_KEYS` is a comma-separated allowlist.

This is deliberately not a user and session system. There is one actor type
(the reviewer) and no multi-tenant requirement yet, so a static key is the
right amount of auth; building more would solve a problem the project does
not have.

**OWASP:** LLM08, excessive agency. Without it, anyone who can reach the API
can trigger unlimited inference and write arbitrary corrections into the
data that `docs/evaluation.md` treats as future training signal.

## 2. Upload validation (`backend/main.py`)

Before a byte reaches disk, OCR or a model call:

- **Type allowlist**, `.pdf`, `.png`, `.jpg`, `.jpeg` only. Anything else is
  a 415 before the file is saved.
- **Size cap**, `MAX_UPLOAD_MB` (default 15). A 413 past that.
- **Empty-file rejection**, a 400, rather than a pipeline run that fails
  three stages later with a confusing stack trace.

**OWASP:** LLM04, model denial of service. An unbounded upload is exactly
how one request ties up a worker for minutes, since the deskew search in
`pipeline/preprocess.py` is not cheap on a large image.

## 3. Rate limiting

`POST /documents` is capped at `UPLOAD_RATE_LIMIT` (default `20/minute`) per
source IP via slowapi. Size caps stop one request from being too expensive;
rate limiting stops many cheap ones from adding up to the same thing. It is
scoped to the upload route only, because read routes are not
inference-expensive and limiting them would just make the review UI feel
slow for no security benefit.

**OWASP:** LLM04, model denial of service.

## 4. Kill switch (`MAINTENANCE_MODE`)

`MAINTENANCE_MODE=true` makes `POST /documents` return 503 immediately, with
no redeploy, and `GET /health` reports the flag so a load balancer or status
page can reflect it. Review of already-processed documents keeps working,
so taking ingestion down does not take the reviewers down with it.

## 5. Prompt injection posture

**OWASP:** LLM01, prompt injection.

The extraction prompt is deliberately narrow ("copy values exactly as
printed, do not calculate or guess"), and model output is **always** passed
through `Invoice.model_validate_json` against a fixed Pydantic schema before
anything downstream sees it. Nothing from the document, including text
printed on the page specifically to manipulate the model, can reach the
validation rules, the scoring function or the routing logic except as data
in one of those typed fields.

The bound is structural rather than instructional: there is no code path
where extracted text is interpreted as an instruction, executed, or used to
change auth, routing or maintenance state. A malicious document can make the
*extraction* wrong, which confidence scoring and human review already exist
to catch, but it cannot make the *system* do something it was not built to
do.

## 6. Observability and cost tracking

- **`GET /metrics`** aggregates real rows from `documents` and `runs`
  (optionally `?hours=N`): status counts, straight-through rate, average
  confidence, average and p95 latency, corrections logged, and cost.
  `backend/tests/test_api_metrics.py` writes rows and asserts the
  aggregation against them, so the endpoint is tested against data rather
  than trusted.
- **Cost is illustrative, not billed usage.** There is no paid model API
  behind this build, so `Run.cost_usd` is `tokens_used *
  COST_PER_1K_TOKENS_USD / 1000` with a configurable placeholder price.
  `tokens_used` itself is real: for `EXTRACTOR_MODE=ollama` it is the
  per-token logprob count from the model response, and for the OCR path it
  is the count of word confidences the scoring function actually consumed,
  used as a cost proxy. Substituting a real provider's per-token price turns
  the same arithmetic into real spend tracking.
- **Structured logs** (`backend/obslog.py`), one JSON object per line to
  stdout for every upload, correction, processed document and failure, so an
  operator can grep or jq for "what happened to document 482" without a
  tracing backend. This project's scale does not justify a full tracing
  stack.

## What is still out of scope

Stated plainly for whoever picks this up:

- **Multi-tenant auth.** "Reviewer" is a free-text field on a correction,
  not an authenticated identity. Fine for one team, wrong for multiple
  customers sharing a deployment.
- **Secrets management.** API keys and database credentials are plain
  environment variables, appropriate at this size; a production rollout
  wants a secrets manager rather than compose defaults.
- **PII handling.** Invoices carry names, addresses and tax identifiers.
  `docs/deployment.md`'s storage guidance needs an explicit retention and
  redaction policy before this handles real customer documents at scale.
