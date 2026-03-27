"""
Dokumentum feltöltés és RAG keresés.

v3.3 változások:
  - Confidence scoring: ha top_score < RAG_FALLBACK_THRESHOLD → sablon válasz
  - Forrás-visszaadás: response tartalmazza [{filename, score, collection}]
  - Logolás: minden rag/query hívás bekerül a rag_logs táblába
  - Multi-collection: tag alapján kerül a megfelelő Qdrant collection-be
  - Optimalizált prompt: ügyfélszolgálati hangnem, pontosabb kontextus
"""
import time
import uuid
import logging
from pathlib import Path
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, Security

import db.queries as q
from models.schemas import RagRequest
from services import openai_service, qdrant_service, file_service
from core.config import (
    OPENAI_API_KEY, UPLOAD_DIR, ALLOWED_EXTS, COMPANY_NAME,
    RAG_FALLBACK_THRESHOLD,
    FALLBACK_REPLY_HU, FALLBACK_REPLY_EN, FALLBACK_REPLY_DE
)
from core.security import require_api_key

router = APIRouter(prefix="/api", tags=["Documents"])
log    = logging.getLogger("docuagent")

_FALLBACK_BY_LANG = {"HU": FALLBACK_REPLY_HU, "EN": FALLBACK_REPLY_EN, "DE": FALLBACK_REPLY_DE}

# ── Optimalizált RAG system prompt ────────────────────────────
_RAG_SYSTEM_PROMPT = f"""Te a(z) {COMPANY_NAME} ügyfélszolgálati asszisztense vagy.

Feladatod: az alábbi belső dokumentumok alapján válaszolj az ügyfél kérdésére.

Szabályok:
- Csak a megadott dokumentumok tartalmára támaszkodj
- Ha nincs elegendő információ, mondd: "Sajnos erre a kérdésre nem találok pontos választ dokumentumainkban."
- Légy tömör, udvarias és szakszerű
- Ne találj ki adatokat, árakat, határidőket
- A válasz nyelvét igazítsd a kérdés nyelvéhez
- Ne hivatkozz a dokumentumok nevére vagy belső azonosítójára"""


@router.post("/upload")
async def upload_doc(
    file:           UploadFile = File(...),
    uploader_name:  str = Form("Demo"),
    uploader_email: str = Form("demo@agentify.hu"),
    tag:            str = Form("general"),
    department:     str = Form("General"),
    access_level:   str = Form("employee"),
    _auth=Security(require_api_key)
):
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTS:
        raise HTTPException(400, f"Nem támogatott formátum: {ext}")

    content  = await file.read()
    size_kb  = round(len(content) / 1024)
    dest     = UPLOAD_DIR / f"{uuid.uuid4().hex[:8]}_{file.filename}"
    dest.write_bytes(content)

    text       = file_service.extract_text(dest)
    lang       = file_service.detect_language(text)
    doc_id     = str(uuid.uuid4())
    qdrant_ok  = False
    collection = "general"

    if OPENAI_API_KEY:
        qdrant_ok, collection = await qdrant_service.store_document(
            doc_id, file.filename, text, tag, department, access_level, uploader_email
        )

    await q.insert_document(
        doc_id, file.filename, uploader_name, uploader_email,
        tag, department, access_level, size_kb, lang, qdrant_ok
    )

    log.info(f"Uploaded: {file.filename} ({size_kb}KB, lang={lang}, collection={collection}, qdrant={qdrant_ok})")
    return {
        "status":     "ok",
        "id":         doc_id,
        "filename":   file.filename,
        "size_kb":    size_kb,
        "lang":       lang,
        "collection": collection,
        "qdrant":     qdrant_ok,
    }


@router.post("/rag/query")
async def rag_query(req: RagRequest):
    """
    RAG keresés dokumentumokban.

    Response:
      found        – volt-e elég biztos találat
      answer       – AI válasz VAGY sablon (ha found=False)
      fallback     – True ha sablon válasz ment ki
      confidence   – legjobb találat score-ja (0-1)
      sources      – [{filename, score, collection}] lista
      latency_ms   – válaszidő
    """
    if not OPENAI_API_KEY:
        return {"found": False, "answer": None, "error": "No API key"}

    t_start     = time.monotonic()
    email_id    = getattr(req, "email_id", None)
    lang        = getattr(req, "language", "HU") or "HU"

    # ── 1. Keresés (multi-collection) ─────────────────────────
    try:
        results = await qdrant_service.search_multi(req.query)
    except Exception as e:
        log.warning(f"Qdrant query hiba: {e}")
        return {"found": False, "answer": None, "error": str(e)}

    top_score    = results[0]["score"] if results else 0.0
    fallback_used = (not results) or (top_score < RAG_FALLBACK_THRESHOLD)

    # ── 2. Forrás-lista összeállítása ─────────────────────────
    source_docs = [
        {"filename": r["filename"], "score": r["score"], "collection": r["collection"]}
        for r in results
    ]

    # ── 3a. Fallback: nincs elég biztos találat ───────────────
    if fallback_used:
        fallback_answer = _FALLBACK_BY_LANG.get(lang, FALLBACK_REPLY_HU)
        latency_ms = int((time.monotonic() - t_start) * 1000)

        await q.insert_rag_log(
            email_id=email_id, query=req.query, answer=fallback_answer,
            fallback_used=True, confidence=top_score,
            source_docs=source_docs, collection="—", lang=lang,
            latency_ms=latency_ms
        )
        log.info(f"RAG FALLBACK (score={top_score:.2f} < {RAG_FALLBACK_THRESHOLD}): '{req.query[:50]}'")
        return {
            "found":      False,
            "answer":     fallback_answer,
            "fallback":   True,
            "confidence": round(top_score, 3),
            "sources":    source_docs,
            "latency_ms": latency_ms,
        }

    # ── 3b. AI válasz a dokumentumok alapján ─────────────────
    context_parts = []
    for r in results[:4]:
        context_parts.append(
            f"[Forrás: {r['filename']} | relevancia: {r['score']:.0%}]\n{r['text']}"
        )
    context_text = "\n\n---\n\n".join(context_parts)

    user_prompt = (
        f"DOKUMENTUMOK:\n{context_text}\n\n"
        f"ÜGYFÉL KÉRDÉSE:\n{req.query}"
    )

    try:
        answer = await openai_service.chat(
            [{"role": "system", "content": _RAG_SYSTEM_PROMPT},
             {"role": "user",   "content": user_prompt}],
            max_tokens=600
        )
    except Exception as e:
        log.warning(f"RAG chat hiba: {e}")
        return {"found": False, "answer": None, "error": str(e)}

    latency_ms = int((time.monotonic() - t_start) * 1000)
    top_collection = results[0]["collection"] if results else "general"

    # ── 4. Logolás ────────────────────────────────────────────
    await q.insert_rag_log(
        email_id=email_id, query=req.query, answer=answer,
        fallback_used=False, confidence=top_score,
        source_docs=source_docs, collection=top_collection,
        lang=lang, latency_ms=latency_ms
    )

    log.info(
        f"RAG OK: '{req.query[:50]}' | "
        f"score={top_score:.2f} | sources={len(results)} | {latency_ms}ms"
    )

    return {
        "found":      True,
        "answer":     answer,
        "fallback":   False,
        "confidence": round(top_score, 3),
        "sources":    source_docs,
        "latency_ms": latency_ms,
    }
