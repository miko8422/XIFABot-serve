"""One process and one port for every service, each as its own MCP endpoint: /screen, later /steam and so on.

The token is checked before anything reaches a service. /health needs no token and says nothing about this machine, so
the Maid can tell "the network is broken" from "the token is wrong".
"""

from __future__ import annotations

import hmac
from collections.abc import Callable
from contextlib import AsyncExitStack, asynccontextmanager

import uvicorn
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from .config import Config
from .services import SERVICES

PUBLIC = ("/health",)


class TokenGate:
    def __init__(self, app, token: str) -> None:
        self.app, self.expected = app, f"Bearer {token}".encode()

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] == "http" and scope["path"] not in PUBLIC:
            given = dict(scope["headers"]).get(b"authorization", b"")
            if not hmac.compare_digest(given, self.expected):
                await JSONResponse({"error": "bad token"}, status_code=401)(scope, receive, send)
                return
        await self.app(scope, receive, send)


def build_app(cfg: Config, services: dict[str, Callable[[Config], MCPServer]] | None = None) -> TokenGate:
    built = {name: make(cfg) for name, make in (SERVICES if services is None else services).items()}

    async def health(_request) -> JSONResponse:
        return JSONResponse({"ok": True, "services": sorted(built)})

    async def token_ok(_request) -> JSONResponse:  # behind the gate: lets the Maid tell a bad token from other failures
        return JSONResponse({"ok": True})

    routes = [Route("/health", health), Route("/token", token_ok)]
    for name, server in built.items():
        # the host header check guards local servers from browsers; here the token does that, and the LAN address varies
        routes += server.streamable_http_app(
            streamable_http_path=f"/{name}", json_response=True, stateless_http=True,
            transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False)).routes

    @asynccontextmanager
    async def lifespan(_app):
        async with AsyncExitStack() as stack:
            for server in built.values():
                await stack.enter_async_context(server.session_manager.run())
            yield

    return TokenGate(Starlette(routes=routes, lifespan=lifespan), cfg.token)


async def serve(cfg: Config) -> None:
    print(f"xifabot-serve ({cfg.machine}): {', '.join(SERVICES)} on {cfg.host}:{cfg.port} (Ctrl+C stops it)", flush=True)
    await uvicorn.Server(uvicorn.Config(build_app(cfg), host=cfg.host, port=cfg.port, log_level="warning")).serve()
