"""
SQLAlchemy tables. One row per field in `extractions`, not per document --
that's what makes per-field precision/recall possible later (Manual, Section 8).
"""
from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey, Text
)
from sqlalchemy.orm import relationship

from database import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True)
    filename = Column(String, nullable=False)
    storage_path = Column(String, nullable=False)
    doc_type = Column(String, default="invoice")
    status = Column(String, default="pending", index=True)
    # pending -> processing -> approved | needs_review | failed
    error = Column(Text, nullable=True)
    flagged_fields = Column(Text, nullable=True)  # comma-separated field names
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    extractions = relationship("Extraction", back_populates="document", cascade="all, delete-orphan")
    runs = relationship("Run", back_populates="document", cascade="all, delete-orphan")


class Extraction(Base):
    __tablename__ = "extractions"

    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    field_name = Column(String, nullable=False)
    value = Column(Text)
    confidence = Column(Float, nullable=False)
    model_name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="extractions")
    corrections = relationship("Correction", back_populates="extraction", cascade="all, delete-orphan")


class Correction(Base):
    __tablename__ = "corrections"

    id = Column(Integer, primary_key=True)
    extraction_id = Column(Integer, ForeignKey("extractions.id"), nullable=False)
    original_value = Column(Text)
    corrected_value = Column(Text)
    reviewer = Column(String, default="anonymous")
    corrected_at = Column(DateTime, default=datetime.utcnow)

    extraction = relationship("Extraction", back_populates="corrections")


class Run(Base):
    __tablename__ = "runs"

    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    duration_ms = Column(Integer)
    model_name = Column(String)
    pages = Column(Integer, nullable=True)
    tokens_used = Column(Integer, nullable=True)
    # Illustrative cost estimate (tokens_used * settings.COST_PER_1K_TOKENS_USD
    # / 1000), computed at write time -- see config.py's COST_PER_1K_TOKENS_USD
    # docstring for why this is a configurable placeholder, not billed usage.
    cost_usd = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="runs")
