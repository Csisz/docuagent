"""
DocuAgent v3.2 — FastAPI Backend
=================================
v3.2 changes:
  - Moduláris struktúra: routers/, services/, db/, models/, core/
  - API key autentikáció (X-API-Key header)
  - CORS env változóból (ALLOWED_ORIGINS)
  - Embedding-alapú feedback matching
  - Többnyelvű válaszgenerálás
  - Típusos Pydantic modellek (enum státuszok, AiDecision)
  - Duplikált route-ok eltávolítva
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from core.config import PORT, ALLOWED_ORIGINS, UPLOAD_DIR
import db.database as database
from routers import classify, emails, documents, dashboard, sla

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s"
)
log = logging.getLogger("docuagent")

_BASE = Path(__file__).parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    UPLOAD_DIR.mkdir(exist_ok=True)
    await database.init_pool()
    yield
    await database.close_pool()


app = FastAPI(title="DocuAgent API", version="3.2", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routerek regisztrálása ────────────────────────────────────
app.include_router(classify.router)
app.include_router(emails.router)
app.include_router(documents.router)
app.include_router(dashboard.router)
app.include_router(sla.router)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def serve():
    for p in [_BASE / "dashboard.html", _BASE.parent / "dashboard" / "index.html"]:
        if p.exists():
            return HTMLResponse(p.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>DocuAgent v3.2</h1><p><a href='/docs'>API Docs →</a></p>")


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=True)
