"""
Step 8 of the Build Manual: wrap Steps 3-7 in a Celery task so the API
returns instantly and the 10-30s of model/OCR inference happens off the
request thread.
"""
import time

from celery import Celery
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config import settings
from models import Document, Extraction, Run
from obslog import get_logger, log_event
from pipeline.preprocess import preprocess_file
from pipeline.extract import extract_pages
from pipeline.confidence import score_document, route, load_field_thresholds

celery_app = Celery("docusense", broker=settings.REDIS_URL, backend=settings.REDIS_URL)

_engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
_Session = sessionmaker(bind=_engine)
_log = get_logger("docusense.tasks")


@celery_app.task(name="process_document")
def process_document(document_id: int) -> str:
    db = _Session()
    started = time.time()
    try:
        doc = db.get(Document, document_id)
        if doc is None:
            log_event(_log, "document missing at task start", document_id=document_id)
            return "missing"
        doc.status = "processing"
        db.commit()

        # Multi-page documents are processed page by page and merged, per the
        # manual's Section 11 note; single-page inputs take the same path with
        # a one element list.
        pages = preprocess_file(doc.storage_path)
        invoice, token_conf, second_opinion = extract_pages(doc.storage_path, pages)

        scores = score_document(invoice, token_conf, second_opinion)
        status, flagged = route(
            scores,
            settings.AUTO_APPROVE_THRESHOLD,
            settings.FLAG_THRESHOLD,
            load_field_thresholds(),
        )

        model_name = "ollama:" + settings.OLLAMA_MODEL if settings.EXTRACTOR_MODE == "ollama" else "local-ocr:tesseract"

        for field_name in type(invoice).model_fields:
            value = getattr(invoice, field_name)
            db.add(Extraction(
                document_id=doc.id,
                field_name=field_name,
                value=str(value),
                confidence=scores[field_name],
                model_name=model_name,
            ))

        doc.status = status
        doc.flagged_fields = ",".join(flagged)

        # Token count: real for "ollama" mode (one logprob per generated
        # token); for "mock" mode it's the count of OCR word-confidences
        # scored, used as a cost *proxy* since there's no model token stream
        # to count. See config.py's COST_PER_1K_TOKENS_USD docstring --
        # the resulting cost_usd is illustrative, not billed usage.
        tokens_used = len(token_conf) if token_conf else None
        cost_usd = (
            round((tokens_used / 1000.0) * settings.COST_PER_1K_TOKENS_USD, 6)
            if tokens_used else None
        )

        db.add(Run(
            document_id=doc.id,
            duration_ms=int((time.time() - started) * 1000),
            model_name=model_name,
            pages=len(pages),
            tokens_used=tokens_used,
            cost_usd=cost_usd,
        ))
        db.commit()
        log_event(
            _log, "document processed",
            document_id=doc.id, status=status, pages=len(pages),
            duration_ms=int((time.time() - started) * 1000),
            model_name=model_name, tokens_used=tokens_used, cost_usd=cost_usd,
            flagged_fields=flagged,
        )
        return status
    except Exception as exc:  # Manual Section 10, rule 6: record failures.
        db.rollback()
        doc = db.get(Document, document_id)
        if doc:
            doc.status = "failed"
            doc.error = str(exc)
            db.commit()
        log_event(
            _log, "document processing failed",
            document_id=document_id, error=str(exc),
            duration_ms=int((time.time() - started) * 1000),
        )
        raise
    finally:
        db.close()
