"""The device side: one process and one port; each service is its own MCP endpoint (/screen, later /game ...).

/health is open and only lists service names; /token answers 200 behind the gate, so the Mac can tell a wrong token
from a broken network.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import AsyncExitStack, asynccontextmanager

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from ..config import DeviceConfig, init_device, load_device
from ..gate import TokenGate
from .services import SERVICES


def build_app(cfg: DeviceConfig, services: dict[str, Callable[[DeviceConfig], MCPServer]] | None = None) -> TokenGate:
    built = {name: make(cfg) for name, make in (SERVICES if services is None else services).items()}

    async def health(_request) -> JSONResponse:
        return JSONResponse({"ok": True, "device": cfg.name, "services": sorted(built)})

    async def token_ok(_request) -> JSONResponse:
        return JSONResponse({"ok": True})

    routes = [Route("/health", health), Route("/token", token_ok)]
    for name, server in built.items():
        # the host-header check protects browser-reachable local servers; here the token does, and the address varies
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


def cli(args) -> None:
    if args.cmd == "init":
        from .doctor import add_command
        cfg = init_device(args.config)
        print(f"config: {args.config}\n\nOn the Mac, in XIFABot-serve, run:\n{add_command(cfg)}")
    elif args.cmd == "doctor":
        from .doctor import run_doctor
        raise SystemExit(0 if run_doctor(load_device(args.config) if args.config.exists() else DeviceConfig()) else 1)
    elif args.cmd == "serve":
        import uvicorn
        cfg = load_device(args.config)
        print(f"xifabot-serve device {cfg.name}: {', '.join(SERVICES)} on {cfg.host}:{cfg.port} (Ctrl+C stops it)", flush=True)
        asyncio.run(uvicorn.Server(uvicorn.Config(build_app(cfg), host=cfg.host, port=cfg.port, log_level="warning")).serve())
