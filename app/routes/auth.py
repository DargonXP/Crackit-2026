import asyncpg
from fastapi import APIRouter, Depends

from app.database.pool import get_pool
from app.models.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterCompanyRequest,
    RegisterRequest,
)
from app.middleware.auth import get_current_user
from app.utils.errors import ApiException
from app.utils.response import ok
from app.utils.security import (
    create_access_token,
    create_refresh_token,
    generate_invite_code,
    hash_password,
    verify_password,
    decode_refresh_token,
)

router = APIRouter()


def _normalize_role(role: str) -> str:
    if role not in {"newcomer", "experienced"}:
        raise ApiException(400, "Invalid role", "INVALID_ROLE")
    return role


@router.post("/register")
async def register(body: RegisterRequest):
    pool = get_pool()
    role = _normalize_role(body.role)
    password_hash = hash_password(body.password)
    invite_code = body.invite_code.upper()

    async with pool.acquire() as conn:
        company = await conn.fetchrow(
            "SELECT id FROM companies WHERE invite_code = $1",
            invite_code,
        )
        if not company:
            raise ApiException(400, "Invalid invite_code", "INVALID_INVITE_CODE")

        try:
            user = await conn.fetchrow(
                """
                INSERT INTO users (company_id, role, position, email, password_hash, name)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id, email, role, name
                """,
                company["id"],
                role,
                body.position,
                body.email,
                password_hash,
                body.name,
            )
        except asyncpg.UniqueViolationError:
            raise ApiException(400, "Email already exists", "EMAIL_EXISTS")

    access_token = create_access_token(
        user_id=user["id"],
        company_id=company["id"],
        role=user["role"],
    )
    refresh_token = create_refresh_token(user_id=user["id"])
    return ok(
        {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user": dict(user),
        }
    )


@router.post("/register-company")
async def register_company(body: RegisterCompanyRequest):
    pool = get_pool()
    password_hash = hash_password(body.password)

    async with pool.acquire() as conn:
        company_id: int | None = None
        invite_code: str | None = None

        # Retry invite_code generation on collision.
        for _ in range(8):
            candidate = generate_invite_code(8)
            try:
                row = await conn.fetchrow(
                    """
                    INSERT INTO companies (name, invite_code, system_prompt)
                    VALUES ($1, $2, $3)
                    RETURNING id, invite_code
                    """,
                    body.company_name,
                    candidate,
                    None,
                )
                company_id = row["id"]
                invite_code = row["invite_code"]
                break
            except asyncpg.UniqueViolationError:
                continue

        if company_id is None or invite_code is None:
            raise ApiException(500, "Failed to generate invite_code", "INVITE_CODE_GENERATION_FAILED")

        try:
            user = await conn.fetchrow(
                """
                INSERT INTO users (company_id, role, position, email, password_hash, name)
                VALUES ($1, 'experienced', $2, $3, $4, $5)
                RETURNING id, email, role, name, position
                """,
                company_id,
                body.position,
                body.email,
                password_hash,
                body.name,
            )
        except asyncpg.UniqueViolationError:
            raise ApiException(400, "Email already exists", "EMAIL_EXISTS")

    access_token = create_access_token(
        user_id=user["id"],
        company_id=company_id,
        role=user["role"],
    )
    refresh_token = create_refresh_token(user_id=user["id"])

    return ok(
        {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "invite_code": invite_code,
            "user": dict(user),
        }
    )


@router.post("/login")
async def login(body: LoginRequest):
    pool = get_pool()
    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            """
            SELECT id, company_id, role, email, password_hash, name
            FROM users
            WHERE email = $1
            """,
            body.email,
        )
        if not user:
            raise ApiException(401, "Invalid credentials", "INVALID_CREDENTIALS")
        if not verify_password(body.password, user["password_hash"]):
            raise ApiException(401, "Invalid credentials", "INVALID_CREDENTIALS")

    access_token = create_access_token(
        user_id=user["id"],
        company_id=user["company_id"],
        role=user["role"],
    )
    refresh_token = create_refresh_token(user_id=user["id"])
    return ok(
        {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user": {
                "id": user["id"],
                "email": user["email"],
                "name": user["name"],
                "role": user["role"],
            },
        }
    )


@router.post("/refresh")
async def refresh(body: RefreshRequest):
    pool = get_pool()

    try:
        payload = decode_refresh_token(body.refresh_token)
        user_id = int(payload.get("sub"))
    except Exception:
        raise ApiException(401, "Invalid refresh token", "INVALID_REFRESH_TOKEN")

    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT id, company_id, role FROM users WHERE id = $1",
            user_id,
        )
        if not user:
            raise ApiException(401, "Invalid refresh token", "INVALID_REFRESH_TOKEN")

    access_token = create_access_token(
        user_id=user["id"],
        company_id=user["company_id"],
        role=user["role"],
    )
    return ok({"access_token": access_token})


@router.get("/me")
async def me(current_user=Depends(get_current_user)):
    return ok(
        {
            "id": current_user["id"],
            "email": current_user["email"],
            "name": current_user.get("name"),
            "role": current_user["role"],
        }
    )

