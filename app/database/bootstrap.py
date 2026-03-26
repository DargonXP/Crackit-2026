import asyncpg

from app.database.pool import get_pool


async def run_safe_bootstrap() -> None:
    """
    Applies lightweight, idempotent adjustments required by the MVP API contract.
    """
    stmts = [
        """
        ALTER TABLE users
          ADD COLUMN IF NOT EXISTS name VARCHAR(255);
        """,
        """
        ALTER TABLE messages
          ADD COLUMN IF NOT EXISTS is_read BOOLEAN DEFAULT FALSE;
        """,
    ]
    pool = get_pool()
    async with pool.acquire() as conn:
        for stmt in stmts:
            try:
                await conn.execute(stmt)
            except asyncpg.UndefinedTableError:
                # Allows booting before schema is applied.
                continue
