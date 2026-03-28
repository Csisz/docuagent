"""
Minden SQL lekérdezés egy helyen.
A router/service réteg csak ezeket a függvényeket hívja,
soha nem ír nyers SQL-t.
"""
import json
from typing import Optional
from datetime import datetime, timezone
import db.database as db


# ══════════════════════════════════════════════════════════════
# EMAILS
# ══════════════════════════════════════════════════════════════

async def get_email_by_id(email_id: str):
    return await db.fetchrow(
        "SELECT * FROM emails WHERE id=$1", email_id
    )


async def get_email_by_message_id(message_id: str):
    return await db.fetchrow(
        "SELECT id FROM emails WHERE message_id=$1", message_id
    )


async def insert_email(email_id: str, message_id: str, subject: str,
                       sender: str, body: str, category: str,
                       urgent: bool, ai_reply: Optional[str]):
    return await db.execute(
        """INSERT INTO emails
           (id, message_id, subject, sender, body, category,
            status, urgent, ai_response, confidence, created_at)
           VALUES ($1,$2,$3,$4,$5,$6,'NEW',$7,$8,0.0,NOW())""",
        email_id, message_id, subject, sender, body, category,
        urgent, ai_reply or None
    )


async def update_email_classification(email_id: str, category: str,
                                       status: str, ai_decision: dict,
                                       confidence: float, urgent: bool = False):
    return await db.execute(
        "UPDATE emails SET category=$1, status=$2, ai_decision=$3, confidence=$4, urgent=$5 WHERE id=$6",
        category, status, json.dumps(ai_decision), confidence, urgent, email_id
    )


async def update_email_reply(email_id: str, reply: str):
    return await db.execute(
        "UPDATE emails SET ai_response=$1, status='AI_ANSWERED' WHERE id=$2",
        reply, email_id
    )


async def update_email_status(email_id: str, status: str):
    return await db.execute(
        "UPDATE emails SET status=$1 WHERE id=$2", status, email_id
    )


async def list_emails(status: Optional[str], limit: int, offset: int):
    fields = """id, subject, sender, body, category, status,
                urgent, confidence, ai_response, ai_decision, created_at"""
    if status:
        rows = await db.fetch(
            f"SELECT {fields} FROM emails WHERE status=$1 ORDER BY created_at DESC LIMIT $2 OFFSET $3",
            status, limit, offset
        )
        total = await db.fetchrow("SELECT COUNT(*) FROM emails WHERE status=$1", status)
    else:
        rows = await db.fetch(
            f"SELECT {fields} FROM emails ORDER BY created_at DESC LIMIT $1 OFFSET $2",
            limit, offset
        )
        total = await db.fetchrow("SELECT COUNT(*) FROM emails")
    return rows, (total["count"] if total else 0)


async def delete_email_by_id(email_id: str):
    await db.execute("DELETE FROM feedback WHERE email_id=$1", email_id)
    return await db.execute("DELETE FROM emails WHERE id=$1", email_id)


# ══════════════════════════════════════════════════════════════
# FEEDBACK
# ══════════════════════════════════════════════════════════════

async def insert_feedback(email_id: str, ai_decision: str,
                           user_decision: str, note: str):
    return await db.execute(
        "INSERT INTO feedback(email_id, ai_decision, user_decision, note) VALUES($1,$2,$3,$4)",
        email_id, ai_decision, user_decision, note
    )


async def get_recent_feedback(limit: int = 30):
    """Visszaadja a legutóbbi feedback sorokat az emailek adataival együtt."""
    return await db.fetch(
        """SELECT e.subject, e.body, e.category, f.user_decision, f.ai_decision
           FROM feedback f JOIN emails e ON e.id = f.email_id
           ORDER BY f.created_at DESC LIMIT $1""",
        limit
    )


async def get_feedback_for_prompt(limit: int = 10):
    """Rövid lista a prompt kontextushoz."""
    return await db.fetch(
        """SELECT f.ai_decision, f.user_decision, e.subject, e.category
           FROM feedback f JOIN emails e ON e.id = f.email_id
           ORDER BY f.created_at DESC LIMIT $1""",
        limit
    )


async def get_feedback_count():
    return await db.fetchrow("SELECT COUNT(*) FROM feedback")


# ══════════════════════════════════════════════════════════════
# DOCUMENTS
# ══════════════════════════════════════════════════════════════

async def insert_document(doc_id: str, filename: str, uploader: str,
                           uploader_email: str, tag: str, department: str,
                           access_level: str, size_kb: int, lang: str,
                           qdrant_ok: bool):
    return await db.execute(
        """INSERT INTO documents
           (id, filename, uploader, uploader_email, tag, department,
            access_level, size_kb, lang, qdrant_ok)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)""",
        doc_id, filename, uploader, uploader_email, tag, department,
        access_level, size_kb, lang, qdrant_ok
    )


async def list_documents(limit: int = 10):
    return await db.fetch(
        "SELECT id, filename, uploader, size_kb, lang, created_at, tag FROM documents ORDER BY created_at DESC LIMIT $1",
        limit
    )


# ══════════════════════════════════════════════════════════════
# DASHBOARD / STATS
# ══════════════════════════════════════════════════════════════

async def get_status_stats(days: int):
    return await db.fetch(
        f"""SELECT status, COUNT(*) AS cnt,
                   COUNT(*) FILTER(WHERE urgent) AS urg,
                   AVG(confidence) AS avg_conf
            FROM emails WHERE created_at > NOW() - INTERVAL '{days} days'
            GROUP BY status"""
    )


async def get_avg_confidence(days: int):
    return await db.fetchrow(
        f"SELECT AVG(confidence)*100 AS v FROM emails WHERE created_at > NOW() - INTERVAL '{days} days'"
    )


async def get_timeline(days: int = 7):
    return await db.fetch(
        f"""SELECT DATE(created_at)::text AS day, COUNT(*) AS cnt,
                   COUNT(*) FILTER(WHERE status='NEEDS_ATTENTION') AS needs
            FROM emails WHERE created_at > NOW() - INTERVAL '{days} days'
            GROUP BY day ORDER BY day"""
    )


async def get_category_breakdown(days: int):
    return await db.fetch(
        f"""SELECT COALESCE(category,'other') AS cat, COUNT(*) AS cnt
            FROM emails WHERE created_at > NOW() - INTERVAL '{days} days'
            GROUP BY cat"""
    )


async def get_recent_activity(limit: int = 8):
    return await db.fetch(
        "SELECT subject, sender, status, confidence, created_at FROM emails ORDER BY created_at DESC LIMIT $1",
        limit
    )


async def get_insights_stats():
    """AI insights oldalhoz - státusz + kategória bontás."""
    stats = await db.fetch(
        "SELECT status, COUNT(*) AS c, AVG(confidence) AS ac FROM emails WHERE created_at > NOW() - INTERVAL '7 days' GROUP BY status"
    )
    cats = await db.fetch(
        "SELECT COALESCE(category,'other') AS cat, COUNT(*) AS c FROM emails WHERE created_at > NOW() - INTERVAL '7 days' GROUP BY cat ORDER BY c DESC"
    )
    return stats, cats


# ══════════════════════════════════════════════════════════════
# RAG LOGS  (v3.3)
# ══════════════════════════════════════════════════════════════

async def insert_rag_log(email_id: Optional[str], query: str, answer: Optional[str],
                          fallback_used: bool, confidence: float,
                          source_docs: list, collection: str,
                          lang: str, latency_ms: int):
    import json as _json
    return await db.execute(
        """INSERT INTO rag_logs
           (email_id, query, answer, fallback_used, confidence,
            sources_count, source_docs, collection, lang, latency_ms)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)""",
        email_id, query, answer, fallback_used, confidence,
        len(source_docs), _json.dumps(source_docs), collection, lang, latency_ms
    )


async def get_rag_stats(days: int = 7):
    return await db.fetch(
        f"""SELECT DATE(created_at) AS day, COUNT(*) AS total,
                   COUNT(*) FILTER (WHERE fallback_used) AS fallbacks,
                   ROUND(AVG(confidence)::numeric, 2) AS avg_conf,
                   ROUND(AVG(latency_ms)::numeric) AS avg_ms
            FROM rag_logs
            WHERE created_at > NOW() - INTERVAL '{days} days'
            GROUP BY day ORDER BY day DESC"""
    )


# ══════════════════════════════════════════════════════════════
# SYSTEM CONFIG  (v3.4)
# ══════════════════════════════════════════════════════════════

async def get_config(key: str) -> Optional[str]:
    row = await db.fetchrow("SELECT value FROM system_config WHERE key=$1", key)
    return row["value"] if row else None


async def set_config(key: str, value: str):
    return await db.execute(
        """INSERT INTO system_config (key, value, updated_at)
           VALUES ($1, $2, NOW())
           ON CONFLICT (key) DO UPDATE SET value=$2, updated_at=NOW()""",
        key, value
    )


# ══════════════════════════════════════════════════════════════
# SLA  (v3.4)
# ══════════════════════════════════════════════════════════════

async def get_sla_emails(warning_hours: float, breach_hours: float):
    """Visszaadja a nyitott emaileket SLA státusszal."""
    return await db.fetch(
        """SELECT id, subject, sender, status, urgent, created_at,
                  EXTRACT(EPOCH FROM (NOW() - created_at))/3600 AS age_hours
           FROM emails
           WHERE status IN ('NEW', 'NEEDS_ATTENTION')
           ORDER BY created_at ASC"""
    )


async def get_sla_summary(warning_hours: float, breach_hours: float):
    """SLA összesítő: ok / warning / breach számok."""
    return await db.fetchrow(
        """SELECT
               COUNT(*) FILTER (
                   WHERE status IN ('NEW','NEEDS_ATTENTION')
                   AND EXTRACT(EPOCH FROM (NOW()-created_at))/3600 < $1
               ) AS ok_count,
               COUNT(*) FILTER (
                   WHERE status IN ('NEW','NEEDS_ATTENTION')
                   AND EXTRACT(EPOCH FROM (NOW()-created_at))/3600 >= $1
                   AND EXTRACT(EPOCH FROM (NOW()-created_at))/3600 < $2
               ) AS warning_count,
               COUNT(*) FILTER (
                   WHERE status IN ('NEW','NEEDS_ATTENTION')
                   AND EXTRACT(EPOCH FROM (NOW()-created_at))/3600 >= $2
               ) AS breach_count
           FROM emails""",
        warning_hours, breach_hours
    )
