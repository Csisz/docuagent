"""
Tanulási rendszer: embedding-alapú feedback matching.

v3.2 változás: a korábbi bag-of-words Jaccard-hasonlóság helyett
OpenAI embedding vektorokat használ. Ez szemantikailag hasonló
emaileket is helyesen párosít, még akkor is, ha más szavakat
használnak (pl. "nem működik a termék" ↔ "hibás az áru").

Fallback: ha az OpenAI nem elérhető, visszaesik a szöveg-alapú
hasonlóságra, hogy a rendszer offline is működjön.
"""
import re
import logging
import numpy as np
from typing import Optional

import db.queries as q
from services.openai_service import embed
from core.config import OPENAI_API_KEY

log = logging.getLogger("docuagent")

# Embedding-alapú override küszöb
EMBED_OVERRIDE_THRESHOLD = 0.82   # koszinusz hasonlóság (0-1)
EMBED_HINT_THRESHOLD     = 0.55   # prompt kontextushoz

# Fallback szöveg-alapú küszöb (ha nincs OpenAI)
TEXT_OVERRIDE_THRESHOLD  = 0.60
TEXT_HINT_THRESHOLD      = 0.35


# ── Szöveg-alapú hasonlóság (fallback) ────────────────────────

def _normalize(t: str) -> str:
    t = t.lower()
    t = re.sub(r"[^\w\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _jaccard(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    stop = {"a", "az", "és", "is", "nem", "de", "the", "and", "to", "of", "in", "for"}
    sa = set(_normalize(a).split()) - stop
    sb = set(_normalize(b).split()) - stop
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


# ── Koszinusz hasonlóság ──────────────────────────────────────

def _cosine(a: list[float], b: list[float]) -> float:
    va, vb = np.array(a), np.array(b)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)


# ── Fő függvény ───────────────────────────────────────────────

async def get_feedback_context(subject: str, body: str) -> tuple[str, Optional[str], float]:
    """
    Visszaad: (prompt_kontextus, forced_status_vagy_None, hasonlóság_score)

    1. Lekéri az utolsó 30 feedback bejegyzést
    2. Embedding-alapú (vagy fallback: szöveg-alapú) hasonlóságot számol
    3. Ha elég magas a match → forced override
    4. Prompt kontextust épít a GPT számára
    """
    rows = await q.get_recent_feedback(limit=30)
    if not rows:
        return "", None, 0.0

    combined = f"{subject} {(body or '')[:500]}"
    best_match, best_score = None, 0.0
    override_threshold = TEXT_OVERRIDE_THRESHOLD
    hint_threshold     = TEXT_HINT_THRESHOLD

    # ── Embedding-alapú útvonal ────────────────────────────────
    if OPENAI_API_KEY:
        try:
            query_vec = await embed(combined)
            for row in rows:
                row_text = f"{row['subject']} {(row['body'] or '')[:500]}"
                row_vec  = await embed(row_text)
                score    = _cosine(query_vec, row_vec)
                if score > best_score:
                    best_score = score
                    best_match = row
            override_threshold = EMBED_OVERRIDE_THRESHOLD
            hint_threshold     = EMBED_HINT_THRESHOLD
            log.debug(f"Embedding matching: best_score={best_score:.3f}")
        except Exception as e:
            log.warning(f"Embedding matching failed, falling back to text: {e}")
            best_match, best_score = None, 0.0  # újra próbáljuk szöveggel

    # ── Fallback: szöveg-alapú ─────────────────────────────────
    if best_score == 0.0:
        for row in rows:
            row_text = f"{row['subject']} {(row['body'] or '')[:500]}"
            score    = _jaccard(combined, row_text)
            if score > best_score:
                best_score = score
                best_match = row

    # ── Override döntés ────────────────────────────────────────
    forced = None
    if best_match and best_score >= override_threshold:
        forced = best_match["user_decision"]
        log.info(f"Learning override (score={best_score:.3f}): → {forced}")

    # ── Prompt kontextus építése ───────────────────────────────
    recent = await q.get_feedback_for_prompt(limit=10)
    lines  = []

    if recent:
        lines.append("\nPast human corrections (learn from these):")
        for r in recent:
            lines.append(f"  Subject: '{r['subject']}'  AI: {r['ai_decision']} -> Human: {r['user_decision']}")

    if best_match and best_score >= hint_threshold:
        lines.append(
            f"\nNOTE: Current email is {best_score:.0%} similar to "
            f"'{best_match['subject']}' → corrected to {best_match['user_decision']}. "
            f"Weight this heavily."
        )

    return "\n".join(lines), forced, best_score
