"""
Pydantic adatmodellek.

v3.2 változás: az ai_decision JSONB mező mostantól típusos
AiDecision modellel van kezelve, nem nyers dict-tel.
Az email státuszok és kategóriák enum-ként vannak definiálva,
így a frontend nem tud érvénytelen értéket küldeni.
"""
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, field_validator


# ── Enumerációk ───────────────────────────────────────────────

class EmailStatus(str, Enum):
    NEW              = "NEW"
    AI_ANSWERED      = "AI_ANSWERED"
    NEEDS_ATTENTION  = "NEEDS_ATTENTION"
    CLOSED           = "CLOSED"


class EmailCategory(str, Enum):
    COMPLAINT  = "complaint"
    INQUIRY    = "inquiry"
    OTHER      = "other"


# ── AI döntés (tipizált JSONB) ────────────────────────────────

class AiDecision(BaseModel):
    """Az ai_decision JSONB mező típusos reprezentációja."""
    can_answer:       bool
    confidence:       float = Field(ge=0.0, le=1.0)
    reason:           str   = ""
    learned_override: bool  = False


# ── Request modellek ──────────────────────────────────────────

class ClassifyRequest(BaseModel):
    email_id: Optional[str] = None
    subject:  str
    body:     str
    sender:   Optional[str] = ""

    @field_validator("subject", "body")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Nem lehet üres")
        return v


class ReplyRequest(BaseModel):
    email_id: Optional[str]          = None
    subject:  str
    body:     str
    category: EmailCategory          = EmailCategory.OTHER
    language: Optional[str]          = None   # ha None → auto-detect


class FeedbackRequest(BaseModel):
    email_id:            str
    original_ai_decision: str
    new_status:          EmailStatus
    note:                Optional[str] = ""


class StatusUpdateRequest(BaseModel):
    status: EmailStatus
    note:   Optional[str] = ""


class RagRequest(BaseModel):
    query: str

    @field_validator("query")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("A keresési kifejezés nem lehet üres")
        return v


# ── Response modellek ─────────────────────────────────────────

class ClassifyResponse(BaseModel):
    can_answer:       bool
    confidence:       float
    category:         EmailCategory
    reason:           str
    status:           EmailStatus
    learned_override: bool = False


# ── RAG request bővítés (v3.3) ────────────────────────────────

class RagQueryRequest(BaseModel):
    """Bővített RAG kérés email_id-vel és nyelvi beállítással."""
    query:    str
    email_id: Optional[str] = None
    language: Optional[str] = None   # HU / EN / DE, ha None → auto-detect

    @field_validator("query")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("A keresési kifejezés nem lehet üres")
        return v


class SourceDoc(BaseModel):
    """Egy találat forrás-dokumentum adatai."""
    filename:   str
    score:      float
    collection: str


class RagResponse(BaseModel):
    """RAG végpont tipizált válasza."""
    found:      bool
    answer:     Optional[str]
    fallback:   bool = False
    confidence: float = 0.0
    sources:    list[SourceDoc] = []
    latency_ms: int = 0
