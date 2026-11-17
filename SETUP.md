# Setup and run guide

Everything in this file was executed from a clean unzip of the project
before being written down. Commands are grouped by what you want to do, so
you can stop after the part you need.

If you only have ten minutes, do **Level 1**. It proves the project works
and needs no database, no Redis and no internet.

---

## What you need installed

| Tool | Version | Needed for | Check with |
|---|---|---|---|
| Python | 3.11, 3.12 or 3.13 (**not 3.14**) | Everything | `python3 --version` |
| Tesseract OCR | any recent | Reading documents | `tesseract --version` |
| Node.js | 20 or newer | The review screen | `node --version` |
| PostgreSQL | 14 or newer | Running the full app | `psql --version` |
| Redis | 6 or newer | Running the full app | `redis-server --version` |

Docker is an alternative to installing PostgreSQL and Redis yourself. See
the Docker section near the end.

### A warning about the Python version

Use Python 3.12 or 3.13. **Python 3.14 does not work**, and the failure is
confusing rather than obvious: OpenCV and PyMuPDF publish no Windows build
for 3.14, so pip tries to compile them from source and stops with errors
about missing compilers or `pg_config`. Nothing is wrong with the project
when this happens, the libraries simply have not been released for that
Python yet.

Check before you start:

```bash
python3 --version          # Windows: python --version
```

If it reports 3.14 or later, install 3.12 from python.org alongside what you
already have. You do not need to uninstall anything. On Windows the `py`
launcher then lets you pick the version explicitly:

```powershell
py -3.12 -m venv .venv
```

On macOS or Linux, use `python3.12 -m venv .venv` once it is installed.

### Installing Tesseract

Tesseract is the only dependency that is not a normal package install.

- **Windows:** download the installer from
  `https://github.com/UB-Mannheim/tesseract/wiki`, install it, then add the
  install folder (usually `C:\Program Files\Tesseract-OCR`) to your PATH.
  Close and reopen the terminal afterwards.
- **macOS:** `brew install tesseract`
- **Ubuntu or Debian:** `sudo apt install tesseract-ocr`

Confirm with `tesseract --version` before going further. If that command is
not found, every extraction will fail with a confusing error later.

---

## Level 1. Run the tests (about 5 minutes)

This needs nothing running. The tests use a temporary SQLite file instead of
PostgreSQL and never contact Redis.

```bash
cd docusense/backend

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -r requirements.txt
pytest -q
```

Expected final line:

```
73 passed
```

That covers deskew recovery on known angles, the invoice-number parsing rules, the four validation rules, the
confidence formula and all three of its aggregators, the OCR extractor,
multi-page merging, authentication, upload limits, the metrics endpoint, and
the evaluation metrics themselves.

Useful variations:

```bash
pytest -v                          # list every test by name
pytest tests/test_confidence.py    # one file
pytest -k threshold                # tests whose name mentions "threshold"
```

---

## Level 2. Reproduce the results (about 25 minutes)

Still no database or Redis needed. The evaluation harness imports the
pipeline directly.

The document images are not in the zip, because the generator is seeded and
recreates them exactly. Generate them first.

```bash
cd ../eval
python3 generate_dataset.py        # about 10 seconds, writes 320 images
```

Then the headline evaluation. The first run reads all 320 documents through
OCR, which takes roughly fifteen to twenty minutes on a laptop. It caches
everything afterwards, so later experiments take seconds.

```bash
python3 run_eval.py
```

This appends to `RESULTS.md` and prints per-field precision, line-item F1,
calibration, AUROC, review-budget error capture and latency, for the full
set and for the tune and holdout splits separately.

With the cache built, the other two experiments are quick:

```bash
python3 ablation.py                # compares the three confidence aggregators
python3 tune_thresholds.py         # fits per-field thresholds, writes backend/thresholds.json
```

Useful flags:

```bash
python3 run_eval.py --limit 20 --rebuild --no-write    # quick smoke run, nothing written
python3 run_eval.py --rebuild                          # after changing pipeline code
python3 run_eval.py --mode first                       # score with a different aggregator
```

**One gotcha:** `--limit` builds a cache containing only that many
documents, and later runs reuse it. After any `--limit` run, use `--rebuild`
to get back to the full 320.

---

## Level 3. Run the whole application

Now you need PostgreSQL and Redis. Four things run at once, so use four
terminals.

### First, one-time database setup

```bash
# start the services (Linux examples; on macOS use `brew services start ...`)
sudo service postgresql start
redis-server --daemonize yes

# create the user and database
sudo -u postgres psql -c "CREATE USER docusense WITH PASSWORD 'docusense' SUPERUSER;"
sudo -u postgres createdb -O docusense docusense
```

Check it worked:

```bash
PGPASSWORD=docusense psql -h localhost -U docusense -d docusense -c "SELECT 1;"
```

The tables are created automatically the first time the API starts.

### Terminal 1, the API

```bash
cd docusense/backend
source .venv/bin/activate

export DATABASE_URL="postgresql+psycopg2://docusense:docusense@localhost:5432/docusense"
export REDIS_URL="redis://localhost:6379/0"
export STORAGE_DIR="$HOME/docusense-storage"
export EXTRACTOR_MODE=mock
export AUTH_ENABLED=false          # see the note below before exposing this

mkdir -p "$STORAGE_DIR"
uvicorn main:app --reload --port 8000
```

On Windows PowerShell, use `$env:DATABASE_URL="..."` instead of `export`.

### Terminal 2, the worker

This is what actually reads the documents. Without it, uploads stay
`pending` forever.

```bash
cd docusense/backend
source .venv/bin/activate
# same five environment variables as above
celery -A tasks.celery_app worker --loglevel=INFO --concurrency=2
```

### Terminal 3, the review screen

```bash
cd docusense/frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

### Terminal 4, trying it

```bash
curl localhost:8000/health
curl -X POST localhost:8000/documents -F "file=@../eval/dataset/0001.png"
curl localhost:8000/documents/1
curl localhost:8000/metrics
```

Or just upload through the web page and watch the status change from
`pending` to `approved` or `needs_review` after a few seconds.

`http://localhost:8000/docs` gives an interactive page listing every API
route, generated automatically, which is a good thing to show in a viva.

### Turning authentication on

`AUTH_ENABLED=false` above is for local use only. To run with it on:

```bash
export AUTH_ENABLED=true
export API_KEYS="pick-a-long-random-string"
```

Then uploads need the key:

```bash
curl -X POST localhost:8000/documents \
     -H "X-API-Key: pick-a-long-random-string" \
     -F "file=@../eval/dataset/0001.png"
```

Without the key you get 401, with a wrong key 401, with a file type that is
not allowed 415. Those three are quick things to demonstrate.

---

## Level 4. The load test

With the stack from Level 3 running:

```bash
cd docusense/loadtest
pip install -r requirements.txt

API_KEY=<your key, or omit if auth is off> \
locust -f locustfile.py --host http://localhost:8000 \
       --headless -u 15 -r 2 -t 90s --csv results
```

Raise `UPLOAD_RATE_LIMIT` on the API first, otherwise you are measuring the
rate limiter rather than the system:

```bash
export UPLOAD_RATE_LIMIT=600/minute
```

To demonstrate the rate limiter instead, restart the API with
`UPLOAD_RATE_LIMIT=5/minute` and send seven uploads. The sixth and seventh
come back 429.

---

## The Docker route

If you have Docker Desktop, this replaces all of Level 3:

```bash
cd docusense
docker compose up -d --build
```

Then `http://localhost:5173` for the UI and `http://localhost:8000/health`
for the API. Stop it with `docker compose down`.

Note that this was never executed during development, because the machine
the project was built on could not reach the container registry. The compose
file is validated (`docker compose config` parses it) and the Dockerfiles are
standard, but if you have a working Docker setup you will be the first to
confirm the build end to end. See `docs/failures.md` section 4.

---

## Switching on the real AI model

Everything above uses `EXTRACTOR_MODE=mock`, which is real Tesseract OCR,
not a fake. To use the vision-language model instead you need roughly 5 GB
of free RAM and a normal internet connection:

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5vl:7b

export EXTRACTOR_MODE=ollama
# restart the API and the worker, then:
cd eval && python3 run_eval.py --rebuild
```

Expect 20 to 40 seconds per page on a CPU, against about 1.7 seconds for
OCR. The evaluation harness does not change, so the two runs sit side by
side in `RESULTS.md` and can be compared directly. This has never been run,
so there is no claim attached to it yet; `docs/failures.md` section 5
explains why.

---

## If something goes wrong

| What you see | What it means | Fix |
|---|---|---|
| `tesseract is not installed or it's not in your PATH` | Tesseract missing | Install it, reopen the terminal, check `tesseract --version` |
| Uploads stay `pending` forever | The worker is not running | Start Terminal 2. Check its output for errors |
| `connection refused` on port 5432 | PostgreSQL is not running | `sudo service postgresql start` |
| `Error 111 connecting to localhost:6379` | Redis is not running | `redis-server --daemonize yes` |
| `VersionMismatch: Redis transport requires redis-py 6.1.0 or later` | Old `redis` package | `pip install -r requirements.txt` again, the pin was corrected |
| pip tries to compile numpy and fails | Old numpy on Python 3.13+ | `pip install -r requirements.txt` again, the pin now selects a prebuilt wheel |
| `Error: pg_config executable not found` | You are on Python 3.14, which has no prebuilt libraries yet | Make the virtual environment with Python 3.12 instead: `py -3.12 -m venv .venv` |
| `Access is denied: 'C:\\WINDOWS\\system32\\.venv'` | PowerShell opened as administrator, in the wrong folder | `cd` into the project's `backend` folder first, and use a normal (non-administrator) terminal |
| `source : The term 'source' is not recognized` | That command is Linux and Mac only | On PowerShell use `.\\.venv\\Scripts\\Activate.ps1` |
| `running scripts is disabled on this system` | PowerShell blocks the activation script | `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, then activate again |
| `500` with `AUTH_ENABLED=true but no API_KEYS configured` | Auth on, no key set | Set `API_KEYS`, or set `AUTH_ENABLED=false` for local use |
| `429 Too Many Requests` | Rate limiter working as intended | Wait a minute or raise `UPLOAD_RATE_LIMIT` |
| `run_eval.py` reports far fewer than 320 documents | A `--limit` cache is in use | Re-run with `--rebuild` |
| `FileNotFoundError` on a dataset image | Images not generated yet | `python3 eval/generate_dataset.py` |
| `No TrueType font could be found on this machine` | PIL cannot see your system fonts | On Linux `sudo apt install fonts-dejavu`. Elsewhere this is unusual; report it, do not work around it, because an unreadable dataset invalidates every number |

---

## A ten minute demonstration

If you need to show this to someone, this order works well:

1. `pytest -q` in `backend`, showing 73 tests passing.
2. The review screen, uploading one document and watching the status change.
3. The same document's fields, pointing at the confidence colours and the
   flagged field name.
4. The Observability tab, which is computing its numbers live from the
   database.
5. `eval/RESULTS.md`, specifically the threshold tuning table where
   automation goes from 66.4 to 81.3 percent and precision from 92.0 to 95.8
   at the same time.
6. `docs/failures.md`, which lists everything that went wrong during the
   build. Volunteering this tends to earn more credit than hiding it.
