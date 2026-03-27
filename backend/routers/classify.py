"""
Email osztályozás és válaszgenerálás.

v3.3 változások:
  - Email-specifikus prompt optimalizálás: ügyfélszolgálati kontextus,
    pontosabb kategóriák, hangnem szabályok
  - generate_reply logol a rag_logs táblába (latency, lang, confidence)
  - Fallback logika: ha alacsony confidence → NEEDS_ATTENTION marad,
    nem generál gyenge választ
"""
import time
import json
import logging
from fastapi import APIRouter
from services import openai_service, learning_service
from services.file_service import detect_language
import db.queries as q
from models.schemas import (
    ClassifyRequest, ClassifyResponse, ReplyRequest,
    EmailCategory, EmailStatus, AiDecision
)
from core.config import OPENAI_API_KEY, CONF_THRESHOLD, COMPANY_NAME

router = APIRouter(prefix="/api", tags=["AI"])
log    = logging.getLogger("docuagent")

# ── Nyelv → hangnem utasítás ──────────────────────────────────
_LANG_INSTRUCTION = {
    "HU": (
        "Válaszolj magyarul. Legyen udvarias, empatikus és szakmai az üzenet. "
        "Szólítsd meg az ügyfelet tegező helyett magázva. "
        "Kerüld a túl formális vagy bürokratikus fogalmazást."
    ),
    "EN": (
        "Reply in English. Be polite, empathetic and professional. "
        "Use a warm but formal tone. Address the customer respectfully."
    ),
    "DE": (
        "Antworte auf Deutsch. Sei höflich, einfühlsam und professionell. "
        "Verwende die Sie-Form. Vermeide bürokratische Formulierungen."
    ),
}

# ── Osztályozó system prompt (optimalizált) ───────────────────
_CLASSIFY_SYSTEM = """You are an expert email classifier for a customer service team.

Classify the incoming email and respond ONLY with valid JSON:
{{"can_answer": true/false, "confidence": 0.0-1.0, "category": "complaint|inquiry|other", "reason": "1 sentence"}}

Category rules:
- "complaint": customer expresses dissatisfaction, reports a problem, requests refund/compensation
- "inquiry":   customer asks a question, requests information, needs help or guidance
- "other":     newsletter, spam, internal, out-of-scope

Decision rules:
- can_answer=true ONLY IF: confidence >= {threshold} AND category != "complaint"
- Complaints always → can_answer=false (need human empathy)
- Uncertainty or ambiguity → lower confidence, can_answer=false
- Short/vague emails → confidence max 0.65{feedback_ctx}"""

# ── Válasz-generáló system prompt (optimalizált) ─────────────
_REPLY_SYSTEM = """{COMPANY_NAME} ügyfélszolgálati asszisztense vagy.

{lang_instruction}

Fontos szabályok:
- Légy tömör: max 3-4 bekezdés
- Kezdd köszönettel a megkereséséért
- Válaszolj közvetlenül a feltett kérdésre
- Ha konkrét lépéseket kell tenni, sorold fel pontokba
- Fejezd be biztatással vagy következő lépés ajánlásával
- NE írj tárgyat, aláírást vagy "Üdvözlettel" sort – ezt a rendszer hozzáadja
- NE találj ki adatokat, amiről nem vagy biztos"""


@router.post("/classify", response_model=ClassifyResponse)
async def classify_email(req: ClassifyRequest):
    if not OPENAI_API_KEY:
        return ClassifyResponse(
            can_answer=False, confidence=0.0,
            category=EmailCategory.OTHER, reason="No API key",
            status=EmailStatus.NEEDS_ATTENTION
        )

    feedback_ctx, forced, sim = await learning_service.get_feedback_context(req.subject, req.body)

    # ── Tanult override ────────────────────────────────────────
    if forced and sim >= learning_service.EMBED_OVERRIDE_THRESHOLD:
        conf     = round(0.50 + sim * 0.45, 2)
        can      = forced == EmailStatus.AI_ANSWERED.value
        cat      = EmailCategory.COMPLAINT if forced == EmailStatus.NEEDS_ATTENTION.value else EmailCategory.INQUIRY
        status   = EmailStatus(forced)
        decision = AiDecision(can_answer=can, confidence=conf,
                              reason=f"learned sim={sim:.2f}", learned_override=True)
        if req.email_id:
            await q.update_email_classification(
                req.email_id, cat.value, status.value, decision.model_dump(), conf
            )
        log.info(f"Classify LEARNED: {req.subject[:40]} → {status} sim={sim:.3f}")
        return ClassifyResponse(can_answer=can, confidence=conf, category=cat,
                                reason=f"Tanult egyezés ({sim:.0%})",
                                status=status, learned_override=True)

    # ── GPT osztályozás ────────────────────────────────────────
    sys_prompt = _CLASSIFY_SYSTEM.format(
        threshold=CONF_THRESHOLD,
        feedback_ctx=feedback_ctx
    )
    try:
        raw    = await openai_service.chat(
            [{"role": "system", "content": sys_prompt},
             {"role": "user",   "content": f"Subject: {req.subject}\n\n{req.body[:3000]}"}],
            max_tokens=300, json_mode=True
        )
        p      = json.loads(raw)
        can    = bool(p.get("can_answer", False))
        conf   = round(float(p.get("confidence", 0.0)), 2)
        cat    = EmailCategory(p.get("category", "other"))
        reason = p.get("reason", "")
        status = EmailStatus.AI_ANSWERED if (can and conf >= CONF_THRESHOLD) else EmailStatus.NEEDS_ATTENTION

        decision = AiDecision(can_answer=can, confidence=conf, reason=reason)
        if req.email_id:
            await q.update_email_classification(
                req.email_id, cat.value, status.value, decision.model_dump(), conf
            )

        log.info(f"Classify GPT: '{req.subject[:40]}' → {status.value} conf={conf}")
        return ClassifyResponse(can_answer=can, confidence=conf, category=cat,
                                reason=reason, status=status)

    except Exception as e:
        log.error(f"Classify error: {e}")
        return ClassifyResponse(
            can_answer=False, confidence=0.0, category=EmailCategory.OTHER,
            reason=str(e), status=EmailStatus.NEEDS_ATTENTION
        )


@router.post("/generate-reply")
async def generate_reply(req: ReplyRequest):
    if not OPENAI_API_KEY:
        from fastapi import HTTPException
        raise HTTPException(503, "No API key")

    t_start  = time.monotonic()
    lang     = req.language or detect_language(req.body or req.subject)
    lang_instr = _LANG_INSTRUCTION.get(lang, _LANG_INSTRUCTION["HU"])

    sys_prompt = _REPLY_SYSTEM.format(
        COMPANY_NAME=COMPANY_NAME,
        lang_instruction=lang_instr
    )

    try:
        reply = await openai_service.chat(
            [{"role": "system", "content": sys_prompt},
             {"role": "user",   "content": (
                 f"Kategória: {req.category.value}\n"
                 f"Tárgy: {req.subject}\n\n"
                 f"{req.body[:3000]}"
             )}],
            max_tokens=600
        )
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(500, str(e))

    latency_ms = int((time.monotonic() - t_start) * 1000)

    if req.email_id:
        await q.update_email_reply(req.email_id, reply)

    # Logolás rag_logs-ba (email válasz is naplózva)
    await q.insert_rag_log(
        email_id=req.email_id,
        query=f"{req.subject}\n\n{(req.body or '')[:500]}",
        answer=reply,
        fallback_used=False,
        confidence=1.0,   # generate-reply mindig fut, nincs threshold
        source_docs=[],
        collection="email-reply",
        lang=lang,
        latency_ms=latency_ms
    )

    log.info(f"Reply generated [{lang}] {latency_ms}ms: '{req.subject[:50]}'")
    return {"reply": reply, "email_id": req.email_id, "language": lang, "latency_ms": latency_ms}
