"""Requests from the Mac to one device, with clear reasons when they fail.

Every request opens a short HTTP exchange; nothing is kept open and nothing is polled. A connection error is retried
once, because a VPN reconnecting or Wi-Fi waking up often fails exactly one attempt.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from mcp_types import CallToolResult

from ..config import Device


class DeviceUnavailable(RuntimeError):
    """The device can't be reached or refused; the message says why."""


class DeviceClient:
    def __init__(self, device: Device, timeout_s: float = 8.0) -> None:
        self.device, self.timeout_s = device, timeout_s

    def _http(self, token: str | None = None) -> httpx2.AsyncClient:
        # trust_env off: a system proxy or a VPN's proxy settings must not carry home-network traffic
        return httpx2.AsyncClient(headers={"Authorization": f"Bearer {token or self.device.token}"},
                                  timeout=self.timeout_s, trust_env=False)

    async def health(self) -> dict[str, Any]:
        async with self._http() as http:
            r = await http.get(f"{self.device.url}/health")
            r.raise_for_status()
            return r.json()

    async def call(self, service: str, tool: str, arguments: dict[str, Any] | None = None) -> CallToolResult:
        for attempt in (1, 2):
            try:
                return await asyncio.wait_for(self._call(service, tool, arguments or {}), self.timeout_s)
            except TimeoutError:
                raise DeviceUnavailable(f"{self.device.name}: no answer within {self.timeout_s:g} s") from None
            except Exception as e:  # noqa: BLE001 - anyio wraps transport errors in exception groups
                reason = await self._reason(e)
                if attempt == 2 or "token" in reason or "connect" not in reason.casefold():
                    raise DeviceUnavailable(f"{self.device.name}: {reason}") from e
                await asyncio.sleep(0.5)
        raise AssertionError("unreachable")

    async def _call(self, service: str, tool: str, arguments: dict[str, Any]) -> CallToolResult:
        async with self._http() as http, Client(streamable_http_client(f"{self.device.url}/{service}", http_client=http)) as c:
            return await c.call_tool(tool, arguments)

    async def _reason(self, e: BaseException) -> str:
        """The MCP client hides HTTP status codes, so ask the device whether the token is the problem."""
        try:
            async with self._http() as http:
                if (await http.get(f"{self.device.url}/token")).status_code == 401:
                    return "the token was refused"
        except Exception:  # noqa: BLE001 - unreachable: the original error says more
            pass
        leaves = list(_leaves(e))
        return "; ".join(f"{type(x).__name__}: {x}" for x in leaves[:2])[:200]


def _leaves(e: BaseException):
    if isinstance(e, BaseExceptionGroup):
        for sub in e.exceptions:
            yield from _leaves(sub)
    else:
        yield e
