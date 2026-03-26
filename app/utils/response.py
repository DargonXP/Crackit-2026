from fastapi.responses import JSONResponse


def ok(data, message: str = "ok") -> dict:
    return {"data": data, "message": message}


def error_response(status_code: int, error: str, code: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": error, "code": code})
