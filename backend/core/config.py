import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Adatbázis ─────────────────────────────────────────────────
DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/docuagent")

# ── AI ────────────────────────────────────────────────────────
OPENAI_API_KEY  = os.getenv("OPENAI_API_KEY", "")
CONF_THRESHOLD  = float(os.getenv("CONFIDENCE_THRESHOLD", "0.70"))

# ── Qdrant ────────────────────────────────────────────────────
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")

# ── n8n ───────────────────────────────────────────────────────
N8N_BASE_URL      = os.getenv("N8N_BASE_URL", "http://localhost:5678")
N8N_LABEL_WEBHOOK = os.getenv("N8N_LABEL_WEBHOOK", "")

# ── App ───────────────────────────────────────────────────────
COMPANY_NAME = os.getenv("COMPANY_NAME", "Agentify Kft.")
PORT         = int(os.getenv("PORT", "8000"))

# ── Biztonság ─────────────────────────────────────────────────
DASHBOARD_API_KEY = os.getenv("DASHBOARD_API_KEY", "")
ALLOWED_ORIGINS   = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",") if o.strip()]

# ── Fájlkezelés ───────────────────────────────────────────────
BASE_DIR     = Path(__file__).parent.parent
UPLOAD_DIR   = BASE_DIR / "uploads"
ALLOWED_EXTS = {".pdf", ".docx", ".doc", ".xlsx", ".xls", ".txt", ".csv", ".md"}

# ── RAG / Fallback (v3.3) ─────────────────────────────────────
# Ha a RAG confidence ez alá esik → sablon válasz megy ki
RAG_FALLBACK_THRESHOLD = float(os.getenv("RAG_FALLBACK_THRESHOLD", "0.45"))

# Sablon válasz (személyre szabható env-ből)
FALLBACK_REPLY_HU = os.getenv(
    "FALLBACK_REPLY_HU",
    "Köszönjük megkeresését! Utánanézünk és hamarosan visszajelzünk Önnek."
)
FALLBACK_REPLY_EN = os.getenv(
    "FALLBACK_REPLY_EN",
    "Thank you for reaching out! We will look into this and get back to you shortly."
)
FALLBACK_REPLY_DE = os.getenv(
    "FALLBACK_REPLY_DE",
    "Vielen Dank für Ihre Anfrage! Wir werden uns darum kümmern und uns bald bei Ihnen melden."
)

# ── Multi-collection Qdrant (v3.3) ────────────────────────────
# Tag → Qdrant collection neve
# Feltöltéskor a "tag" mező alapján kerül a dokumentum a megfelelő collection-be
COLLECTION_MAP: dict[str, str] = {
    "billing":    "billing",
    "support":    "support",
    "legal":      "legal",
    "hr":         "hr",
    "general":    "general",
}
DEFAULT_COLLECTION = "general"
