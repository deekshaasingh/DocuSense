"""GET /metrics aggregates real rows, not a canned response."""
import pytest
from fastapi.testclient import TestClient

import main
from database import Base, engine, SessionLocal
from models import Document, Extraction, Run, Correction


@pytest.fixture
def client(monkeypatch):
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(main.process_document, "delay", lambda doc_id: None)
    db = SessionLocal()
    try:
        db.query(Correction).delete()
        db.query(Run).delete()
        db.query(Extraction).delete()
        db.query(Document).delete()
        db.commit()
    finally:
        db.close()
    with TestClient(main.app) as c:
        yield c


def test_metrics_on_empty_db(client):
    body = client.get("/metrics").json()
    assert body["total_documents"] == 0
    assert body["straight_through_rate"] is None
    assert body["avg_latency_ms"] is None


def test_metrics_aggregates_real_rows(client):
    db = SessionLocal()
    try:
        clean = Document(filename="a.png", storage_path="/tmp/a.png", status="approved", flagged_fields=None)
        flagged = Document(filename="b.png", storage_path="/tmp/b.png", status="approved", flagged_fields="vendor_gstin")
        review = Document(filename="c.png", storage_path="/tmp/c.png", status="needs_review", flagged_fields="total_amount")
        db.add_all([clean, flagged, review])
        db.commit()
        for d in (clean, flagged, review):
            db.refresh(d)
        db.add_all([
            Extraction(document_id=clean.id, field_name="total_amount", value="10.00", confidence=0.95, model_name="m"),
            Extraction(document_id=flagged.id, field_name="total_amount", value="20.00", confidence=0.80, model_name="m"),
            Extraction(document_id=review.id, field_name="total_amount", value="30.00", confidence=0.40, model_name="m"),
        ])
        db.add_all([
            Run(document_id=clean.id, duration_ms=100, model_name="m", pages=1, tokens_used=10, cost_usd=0.0001),
            Run(document_id=flagged.id, duration_ms=200, model_name="m", pages=1, tokens_used=20, cost_usd=0.0002),
            Run(document_id=review.id, duration_ms=300, model_name="m", pages=2, tokens_used=30, cost_usd=0.0003),
        ])
        db.commit()
    finally:
        db.close()

    body = client.get("/metrics").json()
    assert body["total_documents"] == 3
    assert body["by_status"]["approved"] == 2
    assert body["by_status"]["needs_review"] == 1
    assert body["straight_through_rate"] == pytest.approx(1 / 3, rel=1e-3)
    assert body["avg_latency_ms"] == pytest.approx(200.0)
    assert body["runs_counted"] == 3
    assert body["total_cost_usd"] == pytest.approx(0.0006, rel=1e-3)
    assert body["avg_confidence"] == pytest.approx((0.95 + 0.80 + 0.40) / 3, rel=1e-3)
