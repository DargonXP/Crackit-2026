import asyncpg
from fastapi import APIRouter, Depends, Path
from app.database.pool import get_pool
from app.middleware.auth import get_current_user
from app.models.progress import UpdateProgressRequest
from app.utils.errors import ApiException
from app.utils.response import ok

router = APIRouter()

VALID_STATUSES = {"not_started", "in_progress", "solved"}


@router.get("/progress/my")
async def my_progress(current_user=Depends(get_current_user)):
    pool = get_pool()
    user_id = int(current_user["id"])
    company_id = int(current_user["company_id"])

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                utp.user_id,
                utp.task_id,
                utp.status,
                utp.attempt_text,
                utp.score,
                utp.updated_at,
                t.position AS task_title,
                t.description AS task_description,
                t.difficulty,
                t.id AS task_pk
            FROM user_task_progress utp
            JOIN tasks t ON t.id = utp.task_id
            WHERE utp.user_id = $1 AND t.company_id = $2
            ORDER BY utp.updated_at DESC
            """,
            user_id,
            company_id,
        )

    items = [dict(r) for r in rows]
    summary = {
        "total": len(items),
        "solved": sum(1 for r in items if r["status"] == "solved"),
        "in_progress": sum(1 for r in items if r["status"] == "in_progress"),
        "not_started": sum(1 for r in items if r["status"] == "not_started"),
    }
    return ok({"items": items, "summary": summary})


@router.put("/progress/{task_id}")
async def upsert_progress(
    task_id: int = Path(..., ge=1),
    body: UpdateProgressRequest | None = None,
    current_user=Depends(get_current_user),
):
    if body is None:
        raise ApiException(400, "Missing request body", "VALIDATION_ERROR")

    pool = get_pool()
    user_id = int(current_user["id"])
    company_id = int(current_user["company_id"])

    status_value = body.status
    attempt_text_value = body.attempt_text

    status_provided = status_value is not None
    attempt_text_provided = attempt_text_value is not None

    if not status_provided and not attempt_text_provided:
        raise ApiException(400, "Provide at least one field: status or attempt_text", "NO_FIELDS")

    if status_provided and status_value not in VALID_STATUSES:
        raise ApiException(400, "Invalid status", "INVALID_STATUS")

    async with pool.acquire() as conn:
        task = await conn.fetchrow(
            "SELECT id, company_id FROM tasks WHERE id = $1",
            task_id,
        )
        if not task:
            raise ApiException(404, "Task not found", "TASK_NOT_FOUND")
        if int(task["company_id"]) != company_id:
            raise ApiException(403, "Task is not in your company", "FORBIDDEN")

        # Upsert with "auto" transition:
        # - if attempt_text is provided and the previous status was not_started => in_progress
        sql = """
        INSERT INTO user_task_progress (user_id, task_id, status, attempt_text, updated_at)
        VALUES (
            $1,
            $2,
            CASE
                WHEN $5 THEN $3
                WHEN $6 THEN 'in_progress'
                ELSE 'not_started'
            END,
            CASE WHEN $6 THEN $4 ELSE NULL END,
            NOW()
        )
        ON CONFLICT (user_id, task_id) DO UPDATE
        SET
            status = CASE
                WHEN $5 THEN $3
                WHEN $6 AND user_task_progress.status = 'not_started' THEN 'in_progress'
                ELSE user_task_progress.status
            END,
            attempt_text = CASE
                WHEN $6 THEN $4
                ELSE user_task_progress.attempt_text
            END,
            updated_at = NOW()
        RETURNING
            user_id,
            task_id,
            status,
            attempt_text,
            score,
            updated_at
        """
        try:
            progress_row = await conn.fetchrow(
                sql,
                user_id,
                task_id,
                status_value,
                attempt_text_value,
                status_provided,
                attempt_text_provided,
            )
        except asyncpg.PostgresError:
            raise ApiException(500, "Failed to update progress", "PROGRESS_UPDATE_FAILED")

        task_info = await conn.fetchrow(
            """
            SELECT id AS task_id, position AS task_title, description AS task_description, difficulty
            FROM tasks
            WHERE id = $1
            """,
            task_id,
        )

    return ok({"progress": {**dict(progress_row), "task": dict(task_info)}})


@router.get("/progress/leaderboard")
async def leaderboard(current_user=Depends(get_current_user)):
    pool = get_pool()
    user_id = int(current_user["id"])
    company_id = int(current_user["company_id"])
    position = current_user.get("position")

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            WITH current AS (
                SELECT $1::int AS company_id, $2::text AS position
            ),
            users_filtered AS (
                SELECT u.id
                FROM users u
                JOIN current c ON u.company_id = c.company_id
                WHERE u.position IS NOT DISTINCT FROM c.position
            ),
            solved AS (
                SELECT
                    uf.id AS user_id,
                    COUNT(*) FILTER (
                        WHERE utp.status = 'solved' AND t.id IS NOT NULL
                    )::int AS solved_count
                FROM users_filtered uf
                LEFT JOIN user_task_progress utp
                  ON utp.user_id = uf.id
                LEFT JOIN tasks t
                  ON t.id = utp.task_id AND t.company_id = $1::int
                GROUP BY uf.id
            )
            SELECT
                RANK() OVER (ORDER BY s.solved_count DESC) AS rank,
                s.solved_count,
                (s.user_id = $3::int) AS is_current_user
            FROM solved s
            ORDER BY rank ASC;
            """,
            company_id,
            position,
            user_id,
        )

    # No names/emails of other users exposed.
    return ok({"leaderboard": [dict(r) for r in rows]})


@router.get("/progress/task/{task_id}")
async def task_progress(
    task_id: int = Path(..., ge=1),
    current_user=Depends(get_current_user),
):
    pool = get_pool()
    user_id = int(current_user["id"])
    company_id = int(current_user["company_id"])

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                t.id AS task_id,
                t.position AS task_title,
                t.description AS task_description,
                t.difficulty,
                COALESCE(utp.status, 'not_started') AS status,
                utp.attempt_text,
                utp.score,
                utp.updated_at
            FROM tasks t
            LEFT JOIN user_task_progress utp
              ON utp.task_id = t.id AND utp.user_id = $1
            WHERE t.id = $2 AND t.company_id = $3
            """,
            user_id,
            task_id,
            company_id,
        )
        if not row:
            raise ApiException(404, "Task not found", "TASK_NOT_FOUND")

    return ok({"progress": dict(row)})

