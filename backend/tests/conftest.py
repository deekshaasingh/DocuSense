import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ.setdefault("EXTRACTOR_MODE", "mock")
# API-level tests (test_api_*.py) exercise the real FastAPI app end to end,
# so they need a real DB engine -- a sqlite file DB stands in for Postgres
# here, same spirit as EXTRACTOR_MODE=mock standing in for a model server
# (see config.py). Auth defaults ON in production; tests that want the 401
# path switch it on themselves per-test.
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_docusense.db")
os.environ.setdefault("AUTH_ENABLED", "false")
os.environ.setdefault("API_KEYS", "test-key-123")
