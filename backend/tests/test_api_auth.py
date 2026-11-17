"""API-key auth: writes require a key, reads stay open, misconfiguration fails closed."""
import pytest
from fastapi.testclient import TestClient

import main
from config import settings
from database import Base, engine


@pytest.fixture
def client(monkeypatch):
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(main.process_document, "delay", lambda doc_id: None)
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)
    monkeypatch.setattr(settings, "API_KEYS", ["good-key"])
    with TestClient(main.app) as c:
        yield c


def test_upload_without_key_rejected(client):
    r = client.post("/documents", files={"file": ("invoice.png", b"bytes", "image/png")})
    assert r.status_code == 401


def test_upload_with_wrong_key_rejected(client):
    r = client.post("/documents", files={"file": ("invoice.png", b"bytes", "image/png")},
                    headers={"X-API-Key": "wrong-key"})
    assert r.status_code == 401


def test_upload_with_correct_key_accepted(client):
    r = client.post("/documents", files={"file": ("invoice.png", b"bytes", "image/png")},
                    headers={"X-API-Key": "good-key"})
    assert r.status_code == 201


def test_corrections_without_key_rejected(client):
    r = client.post("/documents/1/corrections",
                    json={"field_name": "total_amount", "corrected_value": "100.00"})
    assert r.status_code == 401


def test_read_routes_stay_open_without_key(client):
    assert client.get("/documents").status_code == 200
    assert client.get("/metrics").status_code == 200


def test_auth_enabled_with_no_keys_configured_fails_closed(client, monkeypatch):
    monkeypatch.setattr(settings, "API_KEYS", [])
    r = client.post("/documents", files={"file": ("invoice.png", b"bytes", "image/png")},
                    headers={"X-API-Key": "anything"})
    assert r.status_code == 500
