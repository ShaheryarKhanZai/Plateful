"""One error shape for the whole API:
{"error": {"code": "...", "message": "...", "fields": [...optional...]}}
Messages are written for users and never include internals."""
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("app")


class AppError(Exception):
    def __init__(self, status: int, code: str, message: str, headers: dict[str, str] | None = None):
        self.status, self.code, self.message, self.headers = status, code, message, headers


def _body(code: str, message: str, fields: list[dict] | None = None) -> dict:
    err: dict = {"code": code, "message": message}
    if fields is not None:
        err["fields"] = fields
    return {"error": err}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error(_: Request, exc: AppError):
        return JSONResponse(_body(exc.code, exc.message), exc.status, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError):
        # Only field path + message. We never echo the submitted value
        # (it could be a password).
        fields = [
            {"field": ".".join(str(p) for p in e["loc"][1:]) or str(e["loc"][0]),
             "message": str(e["msg"]).removeprefix("Value error, ")}
            for e in exc.errors()
        ]
        return JSONResponse(_body("validation_error", "Some fields are invalid.", fields), 422)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException):
        messages = {404: "Not found.", 405: "Method not allowed.", 401: "Not authenticated."}
        return JSONResponse(
            _body("http_error", messages.get(exc.status_code, "Request failed.")),
            exc.status_code, headers=getattr(exc, "headers", None))

    @app.exception_handler(Exception)
    async def unexpected(request: Request, exc: Exception):
        # Full details go to the server log only. The user sees a generic message.
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(_body("server_error", "Something went wrong. Please try again."), 500)
