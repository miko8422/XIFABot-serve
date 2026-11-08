"""Bearer-token check in front of an ASGI app. Paths in `public` are open and must say nothing about the machine."""

from __future__ import annotations

import hmac

from starlette.responses import JSONResponse


class TokenGate:
    def __init__(self, app, token: str, public: tuple[str, ...] = ("/health",)) -> None:
        self.app, self.expected, self.public = app, f"Bearer {token}".encode(), public

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] == "http" and scope["path"] not in self.public:
            given = dict(scope["headers"]).get(b"authorization", b"")
            if not hmac.compare_digest(given, self.expected):
                await JSONResponse({"error": "bad token"}, status_code=401)(scope, receive, send)
                return
        await self.app(scope, receive, send)
