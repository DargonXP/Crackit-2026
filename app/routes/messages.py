import asyncpg
from fastapi import APIRouter, Depends, Query, Path

from app.database.pool import get_pool
from app.middleware.auth import get_current_user
from app.models.messages import SendMessageRequest
from app.utils.errors import ApiException
from app.utils.response import ok

router = APIRouter()


@router.post("/messages")
async def send_message(
    body: SendMessageRequest,
    current_user=Depends(get_current_user),
):
    pool = get_pool()
    sender_id = int(current_user["id"])
    company_id = int(current_user["company_id"])

    async with pool.acquire() as conn:
        receiver = await conn.fetchrow(
            "SELECT id, company_id FROM users WHERE id = $1",
            body.receiver_id,
        )
        if not receiver:
            raise ApiException(404, "Receiver not found", "RECEIVER_NOT_FOUND")
        if int(receiver["company_id"]) != company_id:
            raise ApiException(403, "Receiver is not in your company", "FORBIDDEN")

        if body.task_id is not None:
            task = await conn.fetchrow(
                "SELECT id, company_id FROM tasks WHERE id = $1",
                body.task_id,
            )
            if not task:
                raise ApiException(404, "Task not found", "TASK_NOT_FOUND")
            if int(task["company_id"]) != company_id:
                raise ApiException(403, "Task is not in your company", "FORBIDDEN")

        try:
            message = await conn.fetchrow(
                """
                INSERT INTO messages (sender_id, receiver_id, task_id, text)
                VALUES ($1, $2, $3, $4)
                RETURNING id, sender_id, receiver_id, task_id, text, created_at, is_read
                """,
                sender_id,
                body.receiver_id,
                body.task_id,
                body.text,
            )
        except Exception:
            raise ApiException(500, "Failed to send message", "MESSAGE_CREATE_FAILED")

    return ok({"message": dict(message)})


@router.get("/messages/conversation/{user_id}")
async def conversation(
    user_id: int = Path(..., ge=1),
    task_id: int | None = Query(default=None),
    current_user=Depends(get_current_user),
):
    pool = get_pool()
    me_id = int(current_user["id"])
    company_id = int(current_user["company_id"])

    async with pool.acquire() as conn:
        other = await conn.fetchrow(
            "SELECT id, company_id FROM users WHERE id = $1",
            user_id,
        )
        if not other:
            raise ApiException(404, "User not found", "USER_NOT_FOUND")
        if int(other["company_id"]) != company_id:
            raise ApiException(403, "User is not in your company", "FORBIDDEN")

        if task_id is not None:
            messages = await conn.fetch(
                """
                SELECT id, sender_id, receiver_id, task_id, text, created_at, is_read
                FROM messages
                WHERE (
                    (sender_id = $1 AND receiver_id = $2) OR
                    (sender_id = $2 AND receiver_id = $1)
                )
                AND task_id = $3
                ORDER BY created_at ASC
                """,
                me_id,
                user_id,
                task_id,
            )
        else:
            messages = await conn.fetch(
                """
                SELECT id, sender_id, receiver_id, task_id, text, created_at, is_read
                FROM messages
                WHERE (
                    (sender_id = $1 AND receiver_id = $2) OR
                    (sender_id = $2 AND receiver_id = $1)
                )
                ORDER BY created_at ASC
                """,
                me_id,
                user_id,
            )

    return ok({"messages": [dict(m) for m in messages]})


@router.get("/messages/inbox")
async def inbox(current_user=Depends(get_current_user)):
    pool = get_pool()
    me_id = int(current_user["id"])

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            WITH ranked AS (
                SELECT
                    CASE
                        WHEN m.sender_id = $1 THEN m.receiver_id
                        ELSE m.sender_id
                    END AS partner_id,
                    m.sender_id,
                    m.receiver_id,
                    m.task_id,
                    m.text,
                    m.created_at,
                    m.is_read,
                    ROW_NUMBER() OVER (
                        PARTITION BY
                            CASE
                                WHEN m.sender_id = $1 THEN m.receiver_id
                                ELSE m.sender_id
                            END
                        ORDER BY m.created_at DESC, m.id DESC
                    ) AS rn
                FROM messages m
                WHERE m.sender_id = $1 OR m.receiver_id = $1
            )
            SELECT
                r.partner_id,
                s.id AS sender_info_id,
                s.email AS sender_email,
                s.name AS sender_name,
                s.role AS sender_role,
                r.text AS last_message_text,
                r.task_id,
                r.created_at AS last_message_created_at
            FROM ranked r
            JOIN users s ON s.id = r.sender_id
            WHERE r.rn = 1
            ORDER BY last_message_created_at DESC
            """,
            me_id,
        )

    return ok({"conversations": [dict(r) for r in rows]})


@router.get("/messages/unread-count")
async def unread_count(current_user=Depends(get_current_user)):
    pool = get_pool()
    me_id = int(current_user["id"])

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT COUNT(*)::int AS unread_count
            FROM messages
            WHERE receiver_id = $1 AND is_read = FALSE
            """,
            me_id,
        )
    return ok({"unread_count": row["unread_count"]})

