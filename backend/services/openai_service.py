"""
OpenAI API hívások egy helyen.
Chat completions + embedding generálás.
"""
import logging
import httpx
from core.config import OPENAI_API_KEY

log = logging.getLogger("docuagent")

CHAT_URL      = "https://api.openai.com/v1/chat/completions"
EMBEDDING_URL = "https://api.openai.com/v1/embeddings"
CHAT_MODEL    = "gpt-4o-mini"
EMBED_MODEL   = "text-embedding-3-small"


def _auth_headers() -> dict:
    return {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }


async def chat(messages: list, max_tokens: int = 800, json_mode: bool = False) -> str:
    """Chat completion. Visszaadja a szöveges választ."""
    body = {
        "model": CHAT_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(CHAT_URL, headers=_auth_headers(), json=body)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


async def embed(text: str) -> list[float]:
    """Szöveg embedding vektorrá alakítása (text-embedding-3-small, 1536 dim)."""
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            EMBEDDING_URL,
            headers=_auth_headers(),
            json={"model": EMBED_MODEL, "input": text[:8000]},
        )
        r.raise_for_status()
        return r.json()["data"][0]["embedding"]
