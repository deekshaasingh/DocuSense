"""
Step 1/2/9 of the Build Manual: the API. Routes match Section 9 exactly,
plus the guardrail/observability additions documented in docs/guardrails.md
(auth, upload validation, rate limiting, kill switch, /metrics).
"""
import os
from datetime import datetime, timedelta

from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import func
from sqlalchemy.orm import Session

from auth import require_api_key
from config import settings
from database import Base, engine, get_db
from models import Document, Extraction, Correction, Run
from obslog import get_logger, log_event
from schemas import (
    DocumentOut, DocumentDetailOut, FieldOut, CorrectionIn, CorrectionOut,
    RunOut, MetricsOut, StatusCounts,
)
from storage import save_upload
from tasks import process_document

_log = get_logger("docusense.api")

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="DocuSense", version="1.2.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    log_event(
        _log, "startup",
        auth_enabled=settings.AUTH_ENABLED, maintenance_mode=settings.MAINTENANCE_MODE,
        extractor_mode=settings.EXTRACTOR_MODE,
        aggregation=settings.CONFIDENCE_AGGREGATION,
    )


@app.get("/health")
def health():
    return {"status": "ok", "maintenance_mode": settings.MAINTENANCE_MODE}


@app.post("/documents", response_model=DocumentOut, status_code=201, dependencies=[Depends(require_api_key)])
@limiter.limit(settings.UPLOAD_RATE_LIMIT)
def upload_document(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db)):
    if settings.MAINTENANCE_MODE:
        raise HTTPException(503, "DocuSense is in maintenance mode; uploads are paused")

    # --- Guardrails: validate before anything is written to disk or queued
    # for inference (docs/guardrails.md, "input validation"). -------------
    filename = file.filename or ""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in settings.ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(
            415,
            f"unsupported file type '{ext or '(none)'}'; allowed: {', '.join(settings.ALLOWED_UPLOAD_EXTENSIONS)}",
        )

    data = file.file.read()
    size_mb = len(data) / (1024 * 1024)
    if size_mb > settings.MAX_UPLOAD_MB:
        raise HTTPException(413, f"file is {size_mb:.1f} MB; max allowed is {settings.MAX_UPLOAD_MB} MB")
    if len(data) == 0:
        raise HTTPException(400, "uploaded file is empty")

    path = save_upload(filename, data)
    doc = Document(filename=filename, storage_path=path, status="pending")
    db.add(doc)
    db.commit()
    db.refresh(doc)

    process_document.delay(doc.id)
    log_event(_log, "document uploaded", document_id=doc.id, filename=filename, size_mb=round(size_mb, 3))

    return DocumentOut(
        id=doc.id, filename=doc.filename, status=doc.status,
        doc_type=doc.doc_type, uploaded_at=doc.uploaded_at.isoformat(),
    )


@app.get("/documents", response_model=list[DocumentOut])
def list_documents(status: str | None = Query(default=None), db: Session = Depends(get_db)):
    q = db.query(Document)
    if status:
        q = q.filter(Document.status == status)
    docs = q.order_by(Document.uploaded_at.desc()).all()
    return [
        DocumentOut(id=d.id, filename=d.filename, status=d.status, doc_type=d.doc_type,
                    uploaded_at=d.uploaded_at.isoformat())
        for d in docs
    ]


@app.get("/documents/{doc_id}", response_model=DocumentDetailOut)
def get_document(doc_id: int, db: Session = Depends(get_db)):
    doc = db.get(Document, doc_id)
    if doc is None:
        raise HTTPException(404, "not found")
    fields = [
        FieldOut(field_name=e.field_name, value=e.value, confidence=e.confidence, model_name=e.model_name)
        for e in doc.extractions
    ]
    runs = [
        RunOut(duration_ms=r.duration_ms, model_name=r.model_name, pages=r.pages,
               tokens_used=r.tokens_used, cost_usd=r.cost_usd, created_at=r.created_at.isoformat())
        for r in doc.runs
    ]
    return DocumentDetailOut(
        id=doc.id, filename=doc.filename, status=doc.status, doc_type=doc.doc_type,
        uploaded_at=doc.uploaded_at.isoformat(), fields=fields,
        flagged_fields=(doc.flagged_fields.split(",") if doc.flagged_fields else []),
        error=doc.error, runs=runs,
    )


@app.get("/documents/{doc_id}/file")
def get_document_file(doc_id: int, db: Session = Depends(get_db)):
    doc = db.get(Document, doc_id)
    if doc is None:
        raise HTTPException(404, "not found")
    return FileResponse(doc.storage_path, filename=doc.filename)


@app.post("/documents/{doc_id}/corrections", response_model=CorrectionOut, dependencies=[Depends(require_api_key)])
def correct_field(doc_id: int, body: CorrectionIn, db: Session = Depends(get_db)):
    extraction = (
        db.query(Extraction)
        .filter(Extraction.document_id == doc_id, Extraction.field_name == body.field_name)
        .order_by(Extraction.created_at.desc())
        .first()
    )
    if extraction is None:
        raise HTTPException(404, f"no extraction for field '{body.field_name}' on document {doc_id}")

    correction = Correction(
        extraction_id=extraction.id,
        original_value=extraction.value,   # never overwrite the original (Manual, Section 10 rule 4)
        corrected_value=body.corrected_value,
        reviewer=body.reviewer,
    )
    db.add(correction)
    db.commit()
    db.refresh(correction)
    log_event(
        _log, "field corrected", document_id=doc_id, field_name=body.field_name,
        reviewer=body.reviewer,
    )

    return CorrectionOut(
        id=correction.id, extraction_id=correction.extraction_id,
        original_value=correction.original_value, corrected_value=correction.corrected_value,
        reviewer=correction.reviewer, corrected_at=correction.corrected_at.isoformat(),
    )


@app.get("/metrics", response_model=MetricsOut)
def metrics(
    hours: int | None = Query(default=None, description="restrict to the last N hours; omit for all time"),
    db: Session = Depends(get_db),
):
    """
    Observability/cost-tracking endpoint (docs/guardrails.md). Everything
    here is computed from what tasks.py actually wrote to `documents` and
    `runs` -- no synthetic numbers.
    """
    doc_q = db.query(Document)
    run_q = db.query(Run)
    window = "all_time"
    if hours:
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        doc_q = doc_q.filter(Document.uploaded_at >= cutoff)
        run_q = run_q.filter(Run.created_at >= cutoff)
        window = f"last_{hours}h"

    docs = doc_q.all()
    total = len(docs)
    counts = StatusCounts()
    for d in docs:
        if hasattr(counts, d.status):
            setattr(counts, d.status, getattr(counts, d.status) + 1)

    completed = [d for d in docs if d.status in ("approved", "needs_review")]
    straight_through = None
    if completed:
        clean = sum(1 for d in completed if d.status == "approved" and not d.flagged_fields)
        straight_through = round(clean / len(completed), 4)

    avg_confidence = None
    if docs:
        avg_confidence = (
            db.query(func.avg(Extraction.confidence))
            .filter(Extraction.document_id.in_([d.id for d in docs]))
            .scalar()
        )

    runs = run_q.all()
    durations = [r.duration_ms for r in runs if r.duration_ms is not None]
    costs = [r.cost_usd for r in runs if r.cost_usd is not None]

    avg_latency = round(sum(durations) / len(durations), 1) if durations else None
    p95_latency = None
    if durations:
        s = sorted(durations)
        idx = max(0, int(len(s) * 0.95) - 1)
        p95_latency = float(s[idx])

    total_cost = round(sum(costs), 6) if costs else None
    avg_cost = round(sum(costs) / len(costs), 6) if costs else None

    return MetricsOut(
        total_documents=total,
        by_status=counts,
        straight_through_rate=straight_through,
        avg_confidence=round(avg_confidence, 4) if avg_confidence is not None else None,
        avg_latency_ms=avg_latency,
        p95_latency_ms=p95_latency,
        total_cost_usd=total_cost,
        avg_cost_usd_per_doc=avg_cost,
        corrections_logged=db.query(func.count(Correction.id)).scalar() or 0,
        runs_counted=len(runs),
        window=window,
    )
