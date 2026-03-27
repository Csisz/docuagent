import logging
from typing import Optional
import asyncpg
from core.config import DB_URL

log = logging.getLogger("docuagent")

pool: Optional[asyncpg.Pool] = None


async def init_pool():
    global pool
    try:
        pool = await asyncpg.create_pool(DB_URL, min_size=2, max_size=10)
        log.info("PostgreSQL connected")
    except Exception as e:
        log.warning(f"PostgreSQL unavailable ({e})")
        pool = None


async def close_pool():
    global pool
    if pool:
        await pool.close()


async def fetch(q: str, *args):
    if not pool:
        return []
    async with pool.acquire() as conn:
        return await conn.fetch(q, *args)


async def fetchrow(q: str, *args):
    if not pool:
        return None
    async with pool.acquire() as conn:
        return await conn.fetchrow(q, *args)


async def execute(q: str, *args):
    if not pool:
        return None
    async with pool.acquire() as conn:
        return await conn.execute(q, *args)


def is_connected() -> bool:
    return pool is not None
