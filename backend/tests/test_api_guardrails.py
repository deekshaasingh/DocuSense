"""Upload guardrails: type allowlist, size limit, empty-file rejection, kill switch."""
import pytest
from fastapi.testclient import TestClient

import main
from config import settings
from database import Base, engine


@pytest.fixture
def client(monkeypatch):
    Base.metadata.create_all(bind=engine)
    # Upload validation happens before the job is queued, so Celery/Redis are
    # irrelevant here and queueing is stubbed out.
    monkeypatch.setattr(main.process_document, "delay", lambda doc_id: None)
    with TestClient(main.app) as c:
        yield c


def test_rejects_disallowed_extension(client):
    r = client.post("/documents", files={"file": ("malware.exe", b"not a document", "application/octet-stream")})
    assert r.status_code == 415


def test_rejects_oversized_file(client, monkeypatch):
    monkeypatch.setattr(settings, "MAX_UPLOAD_MB", 0.001)  # ~1KB cap
    r = client.post("/documents", files={"file": ("invoice.png", b"0" * 2048, "image/png")})
    assert r.status_code == 413


def test_rejects_empty_file(client):
    r = client.post("/documents", files={"file": ("invoice.png", b"", "image/png")})
    assert r.status_code == 400


def test_accepts_allowed_type_within_size(client):
    r = client.post("/documents", files={"file": ("invoice.png", b"\x89PNG fake bytes", "image/png")})
    assert r.status_code == 201
    assert r.json()["filename"] == "invoice.png"


def test_maintenance_mode_blocks_uploads(client, monkeypatch):
    monkeypatch.setattr(settings, "MAINTENANCE_MODE", True)
    r = client.post("/documents", files={"file": ("invoice.png", b"bytes", "image/png")})
    assert r.status_code == 503


def test_health_reports_maintenance_mode(client, monkeypatch):
    monkeypatch.setattr(settings, "MAINTENANCE_MODE", True)
    assert client.get("/health").json()["maintenance_mode"] is True
