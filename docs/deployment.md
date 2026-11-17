# Deployment

## Option A, one machine with Docker Compose

```bash
git clone <your repo> docusense && cd docusense
docker compose up -d --build
open http://localhost:5173          # review UI
curl localhost:8000/health          # {"status":"ok","maintenance_mode":false}
```

That brings up Postgres, Redis, the API, the Celery worker and the review
UI. For a public URL, put the machine behind a reverse proxy with TLS
(Caddy does this in about four lines) or expose it through a tunnel such as
`cloudflared tunnel --url http://localhost:5173`.

**The moment this is reachable from outside your own machine**, set
`AUTH_ENABLED=true` and a real `API_KEYS` value on the `api` service. The
compose file ships auth off so that `docker compose up` works with zero
setup, which is the wrong default the instant the URL is public. See
`docs/guardrails.md` for every guardrail environment variable.

## Option B, Render or Railway

Both build directly from a Dockerfile per service:

1. Create managed **Postgres** and **Redis** instances.
2. Create a **Web Service** from `backend/Dockerfile`. Set `DATABASE_URL`,
   `REDIS_URL`, `AUTH_ENABLED=true` and `API_KEYS`. Expose port 8000.
3. Create a **Background Worker** (Railway) or a second Web Service with no
   public port (Render) from `backend/Dockerfile.worker`, same environment.
4. Create a **Static Site** from `frontend/` (`npm run build`, publish
   `dist/`), or a Web Service from `frontend/Dockerfile`. Point its `/api`
   proxy (see `frontend/nginx.conf`) at the backend service URL.

Both give a public HTTPS URL immediately, which is the fastest path to the
manual's "deployed somewhere with a public URL" checkbox.

## Option C, Kubernetes

`docker-compose.yml` is a reasonable base for a `kompose convert` pass if
you already have a cluster. Not necessary at this size; listed for
completeness.

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | local Postgres | SQLAlchemy connection string |
| `REDIS_URL` | `redis://localhost:6379/0` | Celery broker and backend |
| `STORAGE_DIR` | `/data/storage` | Where uploaded files land |
| `EXTRACTOR_MODE` | `mock` | `mock` (Tesseract) or `ollama` (real VLM) |
| `OLLAMA_URL` / `OLLAMA_MODEL` | local / `qwen2.5vl:7b` | VLM endpoint and model |
| `CONFIDENCE_AGGREGATION` | `mean` | `mean`, `first` or `min` (see `eval/ablation.py`) |
| `AUTO_APPROVE_THRESHOLD` | `0.90` | Global auto-approve bar |
| `FLAG_THRESHOLD` | `0.70` | Global flag bar |
| `FIELD_THRESHOLDS_PATH` | `backend/thresholds.json` | Per-field bars from tuning |
| `AUTH_ENABLED` / `API_KEYS` | `true` / empty | API key auth, fails closed |
| `MAINTENANCE_MODE` | `false` | Kill switch for uploads |
| `MAX_UPLOAD_MB` | `15` | Upload size cap |
| `UPLOAD_RATE_LIMIT` | `20/minute` | Per-IP upload limit |
| `COST_PER_1K_TOKENS_USD` | `0.01` | Illustrative cost model |
| `MAX_PAGES` | `10` | Page cap for multi-page PDFs |

## Switching on the real vision-language model

The repo defaults to `EXTRACTOR_MODE=mock`, which runs a real (not stubbed)
Tesseract-based extractor entirely on CPU with no model download. Switching
to the VLM from the Build Manual is one flag:

```bash
docker compose --profile real up -d --build    # also starts the `ollama` service
docker compose exec ollama ollama pull qwen2.5vl:7b
EXTRACTOR_MODE=ollama docker compose up -d api worker
```

Nothing else changes. `extract()` and `get_second_opinion()` are the only
functions `tasks.py` calls and both branch on `EXTRACTOR_MODE`, returning
the same `(Invoice, token_confidences)` shape either way.

Budget roughly 5 GB of RAM for the 7B model and 20 to 40 seconds per page on
CPU. That latency is why the pipeline is queued rather than synchronous.

After switching, re-run `python3 eval/run_eval.py --rebuild`. The harness is
extractor-agnostic, so the same protocol produces directly comparable
numbers and `eval/RESULTS.md` will hold both runs side by side.

## A note on this build environment

Both the Docker Hub registry and the Ollama model registry are blocked by
the outbound network allowlist of the sandbox this project was built in, so
`docker compose up` and `ollama pull` could not be executed here. See
`docs/failures.md` for exactly what was done instead and what that does and
does not verify. The compose file itself is validated (`docker compose
config` parses it), and every service it would start was installed natively
and exercised for real.
