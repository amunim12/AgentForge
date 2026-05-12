"""Security response headers."""

from collections.abc import Awaitable, Callable

from fastapi import Request
from starlette.responses import Response

_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    # Swagger UI (cdn.jsdelivr.net) needs script/style/img; API-only responses are unaffected.
    "Content-Security-Policy": (
        "default-src 'none'; "
        "script-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
        "style-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
        "img-src 'self' data: https://cdn.jsdelivr.net; "
        "font-src 'self' https://cdn.jsdelivr.net; "
        "connect-src 'self'; "
        "frame-ancestors 'none'"
    ),
}

# Only sent over real HTTPS — never on plain HTTP (would poison browser HSTS cache for localhost)
_HTTPS_ONLY_HEADERS: dict[str, str] = {
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
}


async def add_security_headers(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    response = await call_next(request)
    for header, value in _HEADERS.items():
        response.headers.setdefault(header, value)
    if request.url.scheme == "https":
        for header, value in _HTTPS_ONLY_HEADERS.items():
            response.headers.setdefault(header, value)
    return response
