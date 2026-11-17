"""
Pydantic models that pin down exactly what DocuSense extracts from an invoice.

Passed straight to Ollama's `format` parameter (Invoice.model_json_schema())
so the model is *forced* to answer in this exact shape (Build Manual, Step 4/5).
"""
from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class LineItem(BaseModel):
    description: str
    quantity: float
    unit_price: float
    amount: float


class Invoice(BaseModel):
    invoice_number: str
    invoice_date: date
    vendor_name: str
    vendor_gstin: Optional[str] = None
    subtotal: float
    tax_amount: float
    total_amount: float
    line_items: list[LineItem]


# The seven scalar fields scored individually everywhere in the project.
SCALAR_FIELDS = (
    "invoice_number", "invoice_date", "vendor_name", "vendor_gstin",
    "subtotal", "tax_amount", "total_amount",
)


# ---- API request/response shapes -----------------------------------------

class DocumentOut(BaseModel):
    id: int
    filename: str
    status: str
    doc_type: str
    uploaded_at: str

    model_config = ConfigDict(from_attributes=True)


class FieldOut(BaseModel):
    field_name: str
    value: str
    confidence: float
    model_name: str

    model_config = ConfigDict(from_attributes=True)


class RunOut(BaseModel):
    duration_ms: int
    model_name: str
    pages: Optional[int] = None
    tokens_used: Optional[int] = None
    cost_usd: Optional[float] = None
    created_at: str

    model_config = ConfigDict(from_attributes=True)


class DocumentDetailOut(BaseModel):
    id: int
    filename: str
    status: str
    doc_type: str
    uploaded_at: str
    fields: list[FieldOut] = Field(default_factory=list)
    flagged_fields: list[str] = Field(default_factory=list)
    error: Optional[str] = None
    runs: list[RunOut] = Field(default_factory=list)


class CorrectionIn(BaseModel):
    field_name: str
    corrected_value: str
    reviewer: str = "anonymous"


class CorrectionOut(BaseModel):
    id: int
    extraction_id: int
    original_value: str
    corrected_value: str
    reviewer: str
    corrected_at: str

    model_config = ConfigDict(from_attributes=True)


# ---- Observability ---------------------------------------------------------

class StatusCounts(BaseModel):
    pending: int = 0
    processing: int = 0
    approved: int = 0
    needs_review: int = 0
    failed: int = 0


class MetricsOut(BaseModel):
    total_documents: int
    by_status: StatusCounts
    straight_through_rate: Optional[float] = None
    avg_confidence: Optional[float] = None
    avg_latency_ms: Optional[float] = None
    p95_latency_ms: Optional[float] = None
    total_cost_usd: Optional[float] = None
    avg_cost_usd_per_doc: Optional[float] = None
    corrections_logged: int = 0
    runs_counted: int = 0
    window: str = "all_time"
