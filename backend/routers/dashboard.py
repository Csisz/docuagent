"""
Dashboard KPI adatok, AI insights, health check.
"""
import json
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Security
import httpx

import db.queries as q
import db.database as db
from services import openai_service, qdrant_service
from core.config import OPENAI_API_KEY, COMPANY_NAME, N8N_BASE_URL
from core.security import require_api_key

router = APIRouter(prefix="/api", tags=["Dashboard"])
log    = logging.getLogger("docuagent")


@router.get("/dashboard")
async def dashboard_data(days: int = 7, _auth=Security(require_api_key)):
    vectors = await qdrant_service.count_vectors()
    n8n_ok  = await _check_n8n()

    rows    = await q.get_status_stats(days)
    sm      = {r["status"]: r for r in (rows or [])}
    total   = sum(r["cnt"] for r in (rows or []))
    ai_ans  = sm.get("AI_ANSWERED",     {}).get("cnt", 0)
    needs   = sm.get("NEEDS_ATTENTION", {}).get("cnt", 0)
    closed  = sm.get("CLOSED",          {}).get("cnt", 0)
    new_cnt = sm.get("NEW",             {}).get("cnt", 0)
    urgent  = sum(r.get("urg", 0) for r in (rows or []))

    avg_c   = await q.get_avg_confidence(days)
    fb_cnt  = await q.get_feedback_count()
    timeline = await q.get_timeline(days)
    cats     = await q.get_category_breakdown(days)
    cat_map  = {r["cat"]: r["cnt"] for r in (cats or [])}

    act_rows = await q.get_recent_activity()
    activity = [
        {
            "type":       "alert" if r["status"] == "NEEDS_ATTENTION" else "ok" if r["status"] == "AI_ANSWERED" else "email",
            "title":      (r["subject"] or "")[:60],
            "meta":       f"{(r['sender'] or '')[:30]} · {r['status']} · {r['created_at'].strftime('%m-%d %H:%M') if r['created_at'] else ''}",
            "confidence": round(float(r["confidence"] or 0) * 100),
        }
        for r in (act_rows or [])
    ]

    doc_rows = await q.list_documents(limit=10)
    docs = [
        {
            "id":       str(r["id"]),
            "filename": r["filename"],
            "uploader": r["uploader"] or "—",
            "size_kb":  r["size_kb"],
            "lang":     r["lang"],
            "date":     r["created_at"].strftime("%Y-%m-%d") if r["created_at"] else "",
            "ext":      r["filename"].rsplit(".", 1)[-1] if "." in (r["filename"] or "") else "?",
            "tag":      r["tag"],
        }
        for r in (doc_rows or [])
    ]

    alerts = []
    needs_rate = round(needs / max(total, 1) * 100)
    urg_rate   = round(urgent / max(total, 1) * 100)
    if needs_rate >= 30:
        alerts.append({"type": "warn", "message": f"<b>Figyelem:</b> NEEDS_ATTENTION arány {needs_rate}%."})
    if urg_rate >= 40:
        alerts.append({"type": "warn", "message": f"<b>Urgent:</b> Sürgős emailek {urg_rate}%."})

    return {
        "meta": {
            "generated_at":  datetime.now(timezone.utc).isoformat(),
            "range_days":    days,
            "n8n_status":    "active" if n8n_ok else "offline",
            "qdrant_vectors": vectors,
            "openai_model":  "gpt-4o-mini",
            "company":       COMPANY_NAME,
            "db_ok":         db.is_connected(),
        },
        "kpis": {
            "emails":          {"value": total},
            "ai_answered":     {"value": ai_ans},
            "needs_attention": {"value": needs},
            "documents":       {"value": len(docs)},
            "avg_confidence":  {"value": round(float(avg_c["v"] or 0)) if avg_c else 0},
            "feedback_total":  {"value": fb_cnt["count"] if fb_cnt else 0},
        },
        "status_breakdown": {
            "NEW": new_cnt, "AI_ANSWERED": ai_ans,
            "NEEDS_ATTENTION": needs, "CLOSED": closed,
        },
        "charts": {
            "timeline": {
                "labels":     [r["day"]  for r in (timeline or [])],
                "emails":     [r["cnt"]  for r in (timeline or [])],
                "complaints": [r["needs"] for r in (timeline or [])],
            },
            "category": {
                "complaint": cat_map.get("complaint", 0),
                "inquiry":   cat_map.get("inquiry",   0),
                "other":     cat_map.get("other",     0),
            },
        },
        "activity":  activity,
        "uploaders": [],
        "documents": docs,
        "alerts":    alerts,
    }


@router.get("/ai-insights")
async def ai_insights(_auth=Security(require_api_key)):
    if not OPENAI_API_KEY:
        return {
            "ai": {
                "problems":        ["OpenAI nem konfigurált"],
                "trends":          ["—"],
                "recommendations": ["Állítsd be az OPENAI_API_KEY-t"],
            },
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    stats, cats = await q.get_insights_stats()
    fb          = await q.get_feedback_count()
    total       = sum(r["c"] for r in (stats or []))

    sl = [f"  {r['status']}: {r['c']} db ({round(float(r['ac'] or 0)*100)}% conf)" for r in (stats or [])]
    cl = [f"  {r['cat']}: {r['c']}" for r in (cats or [])]

    prompt = (
        f"Analyze email data for {COMPANY_NAME}, return JSON insights in Hungarian.\n"
        f"Stats last 7 days: {chr(10).join(sl) or 'No data'}\n"
        f"Categories: {chr(10).join(cl) or 'No data'}\n"
        f"Total: {total}, Feedback corrections: {fb['count'] if fb else 0}\n"
        f'Return ONLY: {{"problems":["..."],"trends":["..."],"recommendations":["..."]}}'
    )
    try:
        raw  = await openai_service.chat([{"role": "user", "content": prompt}],
                                          max_tokens=400, json_mode=True)
        data = json.loads(raw)
        return {"ai": data, "generated_at": datetime.now(timezone.utc).isoformat()}
    except Exception as e:
        return {
            "ai": {"problems": [f"Hiba: {str(e)[:80]}"], "trends": [], "recommendations": []},
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


@router.get("/health")
async def health():
    from core.config import QDRANT_URL
    qok, nok, v = False, False, -1
    try:
        async with httpx.AsyncClient(timeout=3) as c:
            r = await c.get(f"{QDRANT_URL}/healthz")
            qok = r.status_code == 200
            if qok:
                v = await qdrant_service.count_vectors()
    except Exception:
        pass
    nok = await _check_n8n()
    return {
        "status":  "ok",
        "db":      {"ok": db.is_connected()},
        "qdrant":  {"ok": qok, "vectors": v},
        "n8n":     {"ok": nok},
        "openai":  {"configured": bool(OPENAI_API_KEY)},
        "company": COMPANY_NAME,
        "version": "3.2",
    }


async def _check_n8n() -> bool:
    try:
        async with httpx.AsyncClient(timeout=3) as c:
            r = await c.get(f"{N8N_BASE_URL}/healthz")
            return r.status_code < 500
    except Exception:
        return False


@router.get("/rag-stats")
async def rag_stats(days: int = 7, _auth=Security(require_api_key)):
    """RAG lekérdezések statisztikái: fallback arány, átlagos latency, confidence."""
    rows = await q.get_rag_stats(days)
    total     = sum(r["total"]    for r in (rows or []))
    fallbacks = sum(r["fallbacks"] for r in (rows or []))
    return {
        "summary": {
            "total_queries":    total,
            "fallback_count":   fallbacks,
            "fallback_rate_pct": round(fallbacks / max(total, 1) * 100),
            "days":             days,
        },
        "daily": [
            {
                "day":        str(r["day"]),
                "total":      r["total"],
                "fallbacks":  r["fallbacks"],
                "avg_conf":   float(r["avg_conf"] or 0),
                "avg_ms":     int(r["avg_ms"] or 0),
            }
            for r in (rows or [])
        ],
    }
