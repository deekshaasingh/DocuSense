"""
Central config, read from environment variables (12-factor style).

EXTRACTOR_MODE is the one flag that matters for anyone picking this project
back up: "mock" runs entirely offline with no model server (what this repo
ships with, and what CI/eval run against by default); "ollama" calls a real
Ollama server per the Build Manual (Step 5). Flip it once you have a GPU box
or are willing to wait out CPU inference (~20-40s/page per the manual).
"""
import os


def _flag(name: str, default: str) -> bool:
    return os.getenv(name, default).lower() in ("1", "true", "yes")


class Settings:
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "postgresql+psycopg2://docusense:docusense@localhost:5432/docusense"
    )
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    STORAGE_DIR: str = os.getenv("STORAGE_DIR", "/data/storage")

    EXTRACTOR_MODE: str = os.getenv("EXTRACTOR_MODE", "mock")  # "mock" | "ollama"
    OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen2.5vl:7b")
    OLLAMA_SECOND_MODEL: str = os.getenv("OLLAMA_SECOND_MODEL", "gemma3:4b")

    # --- Confidence scoring ------------------------------------------------
    # How the per-token certainties are collapsed into one number.
    #   "mean"   exp(mean(logprobs))   -- the Build Manual's formula (Step 7)
    #   "first"  exp(logprob of the first token)
    #   "min"    exp(min(logprobs))    -- the weakest token in the field
    #   "margin" p(top-1) - p(top-2)   -- needs top_logprobs, ollama mode only
    # ConfBench (arXiv:2608.01792) reports first-token aggregation as the most
    # consistent predictor of correctness; eval/ablation.py measures all of
    # them on this project's own data instead of taking that on faith.
    CONFIDENCE_AGGREGATION: str = os.getenv("CONFIDENCE_AGGREGATION", "mean")

    # Document-level routing thresholds. Starting guesses per the manual
    # (Step 7), re-measured in Step 10. eval/tune_thresholds.py fits per-field
    # thresholds on a tune split and writes them to thresholds.json; if that
    # file is present it overrides the global values below for the fields it
    # covers (see pipeline/confidence.py::load_field_thresholds).
    AUTO_APPROVE_THRESHOLD: float = float(os.getenv("AUTO_APPROVE_THRESHOLD", "0.90"))
    FLAG_THRESHOLD: float = float(os.getenv("FLAG_THRESHOLD", "0.70"))
    FIELD_THRESHOLDS_PATH: str = os.getenv(
        "FIELD_THRESHOLDS_PATH",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "thresholds.json"),
    )

    # --- Guardrails (see docs/guardrails.md) -------------------------------
    # Auth: a comma-separated allowlist of API keys checked against the
    # X-API-Key header on every mutating/admin route. AUTH_ENABLED defaults
    # to True so a misconfigured deployment fails closed, not open; tests
    # and local `docker compose up` both set AUTH_ENABLED=false explicitly
    # rather than relying on a default that could silently ship open.
    AUTH_ENABLED: bool = _flag("AUTH_ENABLED", "true")
    API_KEYS: list[str] = [k.strip() for k in os.getenv("API_KEYS", "").split(",") if k.strip()]

    # Kill switch: flips the upload route to 503 instantly, no redeploy
    # needed, for "stop taking traffic right now" incidents.
    MAINTENANCE_MODE: bool = _flag("MAINTENANCE_MODE", "false")

    # Upload validation: reject anything that isn't a document before it
    # ever reaches OCR/VLM inference.
    MAX_UPLOAD_MB: float = float(os.getenv("MAX_UPLOAD_MB", "15"))
    ALLOWED_UPLOAD_EXTENSIONS: tuple[str, ...] = (".pdf", ".png", ".jpg", ".jpeg")

    # Rate limiting on the upload route (slowapi/limits syntax), per client IP.
    UPLOAD_RATE_LIMIT: str = os.getenv("UPLOAD_RATE_LIMIT", "20/minute")

    # Cost tracking is illustrative, not billed usage: there is no live model
    # API account behind this build, so COST_PER_1K_TOKENS_USD is a
    # configurable placeholder (default set near typical hosted small-VLM
    # pricing) meant to be overridden with the real per-token price of
    # whatever model is actually deployed. tokens_used itself IS real --
    # it's the token/word count the confidence formula scored (see tasks.py).
    COST_PER_1K_TOKENS_USD: float = float(os.getenv("COST_PER_1K_TOKENS_USD", "0.01"))

    # Multi-page handling (Build Manual, Section 11): pages are processed one
    # at a time and merged, never sent to the model as one batch.
    MAX_PAGES: int = int(os.getenv("MAX_PAGES", "10"))


settings = Settings()
