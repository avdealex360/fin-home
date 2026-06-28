import secrets
from base64 import b64decode

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.config import get_settings


class BasicAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path.startswith("/static"):
            return await call_next(request)
        if request.url.path == "/telegram/webhook":
            return await call_next(request)

        settings = get_settings()
        auth = request.headers.get("Authorization")
        if not auth or not auth.startswith("Basic "):
            return Response(
                status_code=401,
                headers={"WWW-Authenticate": 'Basic realm="Family Budget"'},
                content="Unauthorized",
            )

        try:
            decoded = b64decode(auth[6:]).decode("utf-8")
            username, _, password = decoded.partition(":")
        except Exception:
            return Response(status_code=401, content="Unauthorized")

        valid_user = secrets.compare_digest(username, settings.app_user)
        valid_pass = secrets.compare_digest(password, settings.app_password)
        if not (valid_user and valid_pass):
            return Response(status_code=401, content="Unauthorized")

        return await call_next(request)
