"""The real host over real HTTP and MCP on loopback, with a fake machine."""

import asyncio
import base64
import json
import socket

import httpx2
import pytest
import uvicorn
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from PIL import Image

from xifabot_serve.config import Config, create_config
from xifabot_serve.doctor import maid_lines
from xifabot_serve.host import build_app
from xifabot_serve.platforms import Foreground
from xifabot_serve.services import screen

TOKEN = "test-token"


class FakePlatform:
    foreground = staticmethod(lambda: Foreground("game.exe", "A Game"))
    idle_seconds = staticmethod(lambda: 3.0)
    is_locked = staticmethod(lambda app: False)


def noise(_monitor):
    return Image.effect_noise((2000, 1000), 80).convert("RGB")


class Running:
    def __init__(self, grabber=noise):
        self.grabber = grabber

    async def __aenter__(self):
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        app = build_app(Config(token=TOKEN, machine="pc"), {"screen": lambda c: screen.build(c, self.grabber, FakePlatform)})
        self.server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
        self.task = asyncio.create_task(self.server.serve())
        while not self.server.started:
            await asyncio.sleep(0.01)
        return f"http://127.0.0.1:{port}"

    async def __aexit__(self, *_):
        self.server.should_exit = True
        await self.task


def http(token=TOKEN):
    return httpx2.AsyncClient(headers={"Authorization": f"Bearer {token}"}, trust_env=False)


async def call(url, tool, args=None):
    async with http() as h, Client(streamable_http_client(f"{url}/screen", http_client=h)) as c:
        return await c.call_tool(tool, args or {})


@pytest.mark.asyncio
async def test_status_and_snapshot():
    async with Running() as url:
        status = (await call(url, "status")).structured_content
        assert status["app"] == "game.exe" and status["idle_s"] == 3.0 and status["machine"] == "pc"
        result = await call(url, "snapshot", {"max_width": 1000})
        meta = json.loads(next(c.text for c in result.content if c.type == "text"))
        image = base64.b64decode(next(c.data for c in result.content if c.type == "image"))
        assert meta["width"] == 1000 and meta["black"] is False and image[:2] == b"\xff\xd8"


@pytest.mark.asyncio
async def test_only_health_is_open_without_the_token():
    async with Running() as url, http("wrong") as h:
        assert (await h.get(f"{url}/health")).json() == {"ok": True, "services": ["screen"]}
        assert (await h.get(f"{url}/token")).status_code == 401
        assert (await h.post(f"{url}/screen", json={})).status_code == 401


@pytest.mark.asyncio
async def test_a_black_capture_is_flagged():
    async with Running(lambda _m: Image.new("RGB", (64, 36))) as url:
        result = await call(url, "snapshot")
        assert json.loads(next(c.text for c in result.content if c.type == "text"))["black"] is True


@pytest.mark.asyncio
async def test_services_are_read_only():
    async with Running() as url, http() as h, Client(streamable_http_client(f"{url}/screen", http_client=h)) as c:
        assert sorted(t.name for t in (await c.list_tools()).tools) == ["snapshot", "status"]


def test_init_keeps_the_token_and_prints_lines_for_each_machine(tmp_path):
    path = tmp_path / "config.toml"
    first = create_config(path)
    assert len(first.token) > 30 and create_config(path).token == first.token
    mac = Config(token="t", host="127.0.0.1", port=8771, machine="mac")
    assert maid_lines(mac) == "MAC_SERVE_URL=http://127.0.0.1:8771\nMAC_SERVE_TOKEN=t"
    assert maid_lines(Config(token="t", host="0.0.0.0", port=8770, machine="windows")).startswith("WINDOWS_SERVE_URL=http://")
