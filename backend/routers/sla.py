"""
SLA monitor: válaszidő tracking és konfiguráció.

v3.4 — új modul
  - GET  /api/sla/status   → nyitott emailek SLA státusszal
  - GET  /api/sla/summary  → összesítő (ok/warning/breach számok)
  - GET  /api/sla/config   → aktuális SLA határok
  - POST /api/sla/config   → SLA határok mentése
"""
import logging
from fastapi import APIRouter, Security
from pydantic import BaseModel, Field

import db.queries as q
from core.security import require_api_key

router = APIRouter(prefix="/api/sla", tags=["SLA"])
log    = logging.getLogger("docuagent")

_DEFAULT_WARNING = 4.0
_DEFAULT_BREACH  = 24.0


class SlaConfig(BaseModel):
    warning_hours: float = Field(gt=0, le=168, description="Figyelmeztetés határideje (óra)")
    breach_hours:  float = Field(gt=0, le=168, description="SLA megsértés határideje (óra)")


def _sla_level(age_hours: float, warning: float, breach: float) -> str:
    if age_hours >= breach:
        return "breach"
    if age_hours >= warning:
        return "warning"
    return "ok"


async def _get_thresholds() -> tuple[float, float]:
    w = await q.get_config("sla_warning_hours")
    b = await q.get_config("sla_breach_hours")
    return (
        float(w) if w else _DEFAULT_WARNING,
        float(b) if b else _DEFAULT_BREACH,
    )


@router.get("/config")
async def get_sla_config(_auth=Security(require_api_key)):
    warning, breach = await _get_thresholds()
    return {"warning_hours": warning, "breach_hours": breach}


@router.post("/config")
async def set_sla_config(cfg: SlaConfig, _auth=Security(require_api_key)):
    if cfg.warning_hours >= cfg.breach_hours:
        from fastapi import HTTPException
        raise HTTPException(400, "A warning határnak kisebbnek kell lennie a breach határnál")
    await q.set_config("sla_warning_hours", str(cfg.warning_hours))
    await q.set_config("sla_breach_hours",  str(cfg.breach_hours))
    log.info(f"SLA config frissítve: warning={cfg.warning_hours}h breach={cfg.breach_hours}h")
    return {"status": "ok", "warning_hours": cfg.warning_hours, "breach_hours": cfg.breach_hours}


@router.get("/summary")
async def get_sla_summary(_auth=Security(require_api_key)):
    warning, breach = await _get_thresholds()
    row = await q.get_sla_summary(warning, breach)
    return {
        "warning_hours": warning,
        "breach_hours":  breach,
        "ok_count":      int(row["ok_count"]      or 0),
        "warning_count": int(row["warning_count"] or 0),
        "breach_count":  int(row["breach_count"]  or 0),
    }


@router.get("/status")
async def get_sla_status(_auth=Security(require_api_key)):
    warning, breach = await _get_thresholds()
    rows = await q.get_sla_emails(warning, breach)
    emails = []
    for r in (rows or []):
        age = round(float(r["age_hours"]), 1)
        emails.append({
            "id":         str(r["id"]),
            "subject":    r["subject"] or "",
            "sender":     r["sender"]  or "",
            "status":     r["status"],
            "urgent":     r["urgent"],
            "age_hours":  age,
            "sla_level":  _sla_level(age, warning, breach),
            "created_at": r["created_at"].isoformat() if r["created_at"] else "",
        })
    return {
        "warning_hours": warning,
        "breach_hours":  breach,
        "emails":        emails,
        "total":         len(emails),
    }
