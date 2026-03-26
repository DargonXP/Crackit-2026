from fastapi import Header
from app.database.pool import get_pool
from app.utils.errors import ApiException
from app.utils.security import decode_access_token


async def get_current_user(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise ApiException(401, "Missing or invalid Authorization header", "UNAUTHORIZED")

    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_access_token(token)
        user_id = int(payload.get("sub"))
    except Exception:
        raise ApiException(401, "Invalid or expired access token", "UNAUTHORIZED")

    pool = get_pool()
    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            """
            SELECT id, company_id, role, position, email, name, created_at
            FROM users
            WHERE id = $1
            """,
            user_id,
        )
    if not user:
        raise ApiException(401, "User not found", "UNAUTHORIZED")
    return dict(user)
