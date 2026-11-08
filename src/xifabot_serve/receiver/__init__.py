"""The receiver side, on the Mac: one MCP endpoint on 127.0.0.1 for local agents, forwarding each request to a device.

Tools:
  devices()                                  {"devices": [...]}: configured devices, each checked now
  call(device, service, tool, arguments)     a device's answer, passed through unchanged (text, images, errors)

Agents never see device addresses or tokens, and a new device service needs no change here.
"""

from __future__ import annotations

import asyncio
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from mcp_types import CallToolResult
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from ..config import Device, ReceiverConfig, init_receiver, load_receiver
from ..gate import TokenGate
from .client import DeviceClient, DeviceUnavailable


def device_url(url: str) -> str:
    """http://IP:PORT, whatever path or slash was pasted after it."""
    from urllib.parse import urlparse
    u = urlparse(url if "://" in url else f"http://{url}")
    return f"{u.scheme}://{u.netloc}"


def build_server(cfg: ReceiverConfig) -> MCPServer:
    server = MCPServer("xifabot-serve", instructions="Information from the user's other devices. Read devices() first.")
    clients = {name: DeviceClient(d, cfg.timeout_s) for name, d in cfg.devices.items()}

    @server.tool()
    async def devices() -> dict[str, list[dict[str, Any]]]:
        """Every configured device: whether it answers right now, and its services."""
        async def one(name: str, c: DeviceClient) -> dict[str, Any]:
            try:
                h = await asyncio.wait_for(c.health(), min(3.0, cfg.timeout_s))
                return {"device": name, "online": True, "services": h.get("services", [])}
            except Exception as e:  # noqa: BLE001
                return {"device": name, "online": False, "error": f"{type(e).__name__}: {e}"[:160]}
        return {"devices": list(await asyncio.gather(*(one(n, c) for n, c in clients.items())))}

    @server.tool()
    async def call(device: str, service: str, tool: str, arguments: dict[str, Any] | None = None) -> CallToolResult:
        """Send a request to one service on one device and return its answer."""
        client = clients.get(device)
        if client is None:
            raise ToolError(f"unknown device {device!r}; known: {', '.join(clients) or 'none'}")
        try:
            return await client.call(service, tool, arguments)
        except DeviceUnavailable as e:
            raise ToolError(str(e)) from None

    return server


def build_app(cfg: ReceiverConfig) -> TokenGate:
    server = build_server(cfg)

    async def health(_request) -> JSONResponse:
        return JSONResponse({"ok": True, "devices": sorted(cfg.devices)})

    async def token_ok(_request) -> JSONResponse:
        return JSONResponse({"ok": True})

    app = Starlette(routes=[Route("/health", health), Route("/token", token_ok), *server.streamable_http_app(
        streamable_http_path="/mcp", json_response=True, stateless_http=True,
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False)).routes],
        lifespan=lambda _app: server.session_manager.run())
    return TokenGate(app, cfg.token)


def cli(args) -> None:
    if args.cmd == "init":
        cfg = init_receiver(args.config)
        print(f"config: {args.config}\n\nAdd these lines to your agent's .env (for the Maid: the XIFABot repo root):\n"
              f"XIFABOT_SERVE_URL=http://{cfg.host}:{cfg.port}/mcp\nXIFABOT_SERVE_TOKEN={cfg.token}")
    elif args.cmd == "add":
        cfg = load_receiver(args.config)
        if args.token == cfg.token:
            raise SystemExit("that is this receiver's own token (it goes in your agent's .env). Use the token that "
                             "`xifabot-serve device init` printed on the PC.")
        url = device_url(args.url)
        if url != args.url.rstrip("/"):
            print(f"note: using {url} (a device URL is just http://IP:PORT)")
        cfg.devices[args.name] = Device(args.name, url, args.token)
        cfg.save(args.config)
        print(f"{args.name}: {url} saved. Next: `uv run xifabot-serve receiver check`")
    elif args.cmd == "check":
        from .check import run_check
        raise SystemExit(0 if asyncio.run(run_check(load_receiver(args.config))) else 1)
    elif args.cmd == "serve":
        import uvicorn
        cfg = load_receiver(args.config)
        if cfg.host not in ("127.0.0.1", "localhost", "::1"):
            raise SystemExit("the receiver serves local agents only: set host to 127.0.0.1 in receiver.toml")
        print(f"xifabot-serve receiver: {', '.join(cfg.devices) or 'no devices yet'} on http://{cfg.host}:{cfg.port}/mcp",
              flush=True)
        asyncio.run(uvicorn.Server(uvicorn.Config(build_app(cfg), host=cfg.host, port=cfg.port, log_level="warning")).serve())
