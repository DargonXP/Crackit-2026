from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette import status

from app.config import settings
from app.database.bootstrap import run_safe_bootstrap
from app.database.pool import init_pool, close_pool
from app.middleware.auth import get_current_user
from app.routes.auth import router as auth_router
from app.routes.messages import router as messages_router
from app.routes.progress import router as progress_router
from app.utils.errors import ApiException


def create_app() -> FastAPI:
    app = FastAPI(title="Crackit Onboarding API", version="0.1.0")

    # CORS for frontend dev + production.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(ApiException)
    async def api_exception_handler(_: Request, exc: ApiException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.message, "code": exc.code},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_: Request, exc: RequestValidationError):
        # Convert FastAPI's validation errors into the agreed contract.
        msg = exc.errors()[0].get("msg", "Invalid request") if exc.errors() else "Invalid request"
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": msg, "code": "VALIDATION_ERROR"},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_: Request, __: Exception):
        # Fails closed into the agreed response format.
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "Internal server error", "code": "INTERNAL_SERVER_ERROR"},
        )

    @app.get("/health")
    async def health():
        return {"data": {"status": "ok"}, "message": "ok"}

    app.include_router(auth_router, prefix="/auth", tags=["auth"])
    app.include_router(messages_router, prefix="", tags=["messages"])
    app.include_router(progress_router, prefix="", tags=["progress"])

    @app.on_event("startup")
    async def _startup() -> None:
        await init_pool()
        await run_safe_bootstrap()

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        await close_pool()

    # Silence unused warning; ensures dependency import works.
    _ = get_current_user

    return app


app = create_app()

