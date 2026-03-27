"""
Qdrant vektoros adatbázis service.

v3.3 változások:
  - Multi-collection: tag alapján különböző collection-ökbe kerülnek a dok.
  - Forrás-visszaadás: search() visszaadja a dokumentum nevét és score-ját
  - ensure_collection(): automatikusan létrehozza a collection-t ha nem létezik
  - search_multi(): több collection-ben keres egyszerre
"""
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

import httpx
from core.config import QDRANT_URL, OPENAI_API_KEY, COLLECTION_MAP, DEFAULT_COLLECTION
from services.openai_service import embed

log = logging.getLogger("docuagent")
VECTOR_SIZE = 1536   # text-embedding-3-small


# ── Collection kezelés ────────────────────────────────────────

async def ensure_collection(name: str) -> bool:
    """Létrehozza a collection-t ha még nem létezik."""
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{QDRANT_URL}/collections/{name}")
            if r.status_code == 200:
                return True
            # Nem létezik → létrehozzuk
            r2 = await c.put(
                f"{QDRANT_URL}/collections/{name}",
                json={"vectors": {"size": VECTOR_SIZE, "distance": "Cosine"}},
            )
            ok = r2.status_code in (200, 201)
            if ok:
                log.info(f"Qdrant collection létrehozva: '{name}'")
            return ok
    except Exception as e:
        log.warning(f"ensure_collection({name}) hiba: {e}")
        return False


def tag_to_collection(tag: str) -> str:
    """Tag → Qdrant collection neve."""
    return COLLECTION_MAP.get(tag.lower(), DEFAULT_COLLECTION)


async def count_vectors(collection: str = DEFAULT_COLLECTION) -> int:
    """Vektorok száma egy collection-ben, vagy -1 ha nem elérhető."""
    try:
        async with httpx.AsyncClient(timeout=4) as c:
            r = await c.get(f"{QDRANT_URL}/collections/{collection}")
            return r.json().get("result", {}).get("points_count", 0)
    except Exception:
        return -1


async def count_all_vectors() -> dict[str, int]:
    """Összes collection vektor-száma."""
    totals = {}
    for name in set(COLLECTION_MAP.values()):
        totals[name] = await count_vectors(name)
    return totals


# ── Tárolás ───────────────────────────────────────────────────

async def store_document(doc_id: str, filename: str, text: str,
                          tag: str, department: str,
                          access_level: str, uploader: str) -> tuple[bool, str]:
    """
    Darabolja és vektorizálja a dokumentumot, feltölti a megfelelő Qdrant collection-be.
    Visszaad: (sikeres, collection_neve)
    """
    collection = tag_to_collection(tag)
    await ensure_collection(collection)

    try:
        chunks = [text[i:i+1400] for i in range(0, min(len(text), 12000), 1400)]
        points = []

        async with httpx.AsyncClient(timeout=60) as client:
            for i, chunk in enumerate(chunks):
                vector = await embed(chunk)
                points.append({
                    "id": str(uuid.uuid4()),
                    "vector": vector,
                    "payload": {
                        "filename":     filename,
                        "text":         chunk,
                        "tag":          tag,
                        "collection":   collection,
                        "department":   department,
                        "access_level": access_level,
                        "uploader":     uploader,
                        "doc_id":       doc_id,
                        "chunk_index":  i,
                        "total_chunks": len(chunks),
                        "upload_time":  datetime.now(timezone.utc).isoformat(),
                    },
                })

            r = await client.put(
                f"{QDRANT_URL}/collections/{collection}/points",
                json={"points": points},
            )
            ok = r.status_code == 200
            log.info(f"Qdrant store: {filename} → '{collection}' ({len(chunks)} chunk, ok={ok})")
            return ok, collection

    except Exception as e:
        log.warning(f"Qdrant store_document hiba: {e}")
        return False, collection


# ── Keresés ───────────────────────────────────────────────────

async def search(query_text: str, collection: str = DEFAULT_COLLECTION,
                 limit: int = 3, score_threshold: float = 0.35) -> list[dict]:
    """
    Szemantikus keresés egy collection-ben.
    Visszaad strukturált találati listát forrás-adatokkal.
    """
    vector = await embed(query_text)

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{QDRANT_URL}/collections/{collection}/points/search",
            json={"vector": vector, "limit": limit, "with_payload": True},
        )
        raw = r.json().get("result", [])

    results = []
    for item in raw:
        score = item.get("score", 0)
        if score < score_threshold:
            continue
        payload = item.get("payload", {})
        results.append({
            "score":      round(score, 3),
            "text":       payload.get("text", ""),
            "filename":   payload.get("filename", "ismeretlen"),
            "collection": payload.get("collection", collection),
            "tag":        payload.get("tag", ""),
            "doc_id":     payload.get("doc_id", ""),
            "chunk_index": payload.get("chunk_index", 0),
        })

    return results


async def search_multi(query_text: str, collections: Optional[list[str]] = None,
                       limit_per: int = 2, score_threshold: float = 0.35) -> list[dict]:
    """
    Több collection-ben keres egyszerre, összefésüli és score szerint rendezi.
    Ha collections=None → az összes ismert collection-ben keres.
    """
    if collections is None:
        collections = list(set(COLLECTION_MAP.values()))

    all_results = []
    for col in collections:
        try:
            results = await search(query_text, collection=col,
                                   limit=limit_per, score_threshold=score_threshold)
            all_results.extend(results)
        except Exception as e:
            log.warning(f"search_multi hiba ({col}): {e}")

    # Score szerint csökkentő sorrendbe rendezés
    all_results.sort(key=lambda x: x["score"], reverse=True)
    return all_results[:limit_per * 2]
