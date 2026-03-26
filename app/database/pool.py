import asyncpg
from app.config import settings

pool: asyncpg.Pool | None = None


async def init_pool() -> None:
    global pool
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is not set")
    pool = await asyncpg.create_pool(dsn=settings.database_url, min_size=1, max_size=10)


async def close_pool() -> None:
    global pool
    if pool:
        await pool.close()
        pool = None


def get_pool() -> asyncpg.Pool:
    if pool is None:
        raise RuntimeError("Database pool is not initialized")
    return pool
