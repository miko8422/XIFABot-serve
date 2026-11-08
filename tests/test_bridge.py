"""Agent -> receiver -> device, all real servers over real HTTP and MCP on loopback, with a fake PC."""

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

from xifabot_serve import device, receiver
from xifabot_serve.config import Device, DeviceConfig, ReceiverConfig, init_device, init_receiver, load_receiver
from xifabot_serve.device.platform import Foreground
from xifabot_serve.device.services import screen


class FakePC:
    foreground = staticmethod(lambda: Foreground("game.exe", "A Game"))
    idle_seconds = staticmethod(lambda: 3.0)
    is_locked = staticmethod(lambda app: False)


def noise(_monitor):
    return Image.effect_noise((2000, 1000), 80).convert("RGB")


def port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Serve:
    def __init__(self, app):
        self.app, self.port = app, port()

    async def __aenter__(self):
        self.server = uvicorn.Server(uvicorn.Config(self.app, host="127.0.0.1", port=self.port, log_level="error"))
        self.task = asyncio.create_task(self.server.serve())
        while not self.server.started:
            await asyncio.sleep(0.01)
        return f"http://127.0.0.1:{self.port}"

    async def __aexit__(self, *_):
        self.server.should_exit = True
        await self.task


def pc(grabber=noise):
    cfg = DeviceConfig(token="pc-token", name="windows")
    return device.build_app(cfg, {"screen": lambda c: screen.build(c, grabber, FakePC)})


def bridge(pc_url, pc_token="pc-token", timeout_s=3.0):
    cfg = ReceiverConfig(token="agent-token", timeout_s=timeout_s, devices={"windows": Device("windows", pc_url, pc_token)})
    return receiver.build_app(cfg)


async def agent_call(url, tool, args=None, token="agent-token"):
    async with httpx2.AsyncClient(headers={"Authorization": f"Bearer {token}"}, trust_env=False) as h, \
            Client(streamable_http_client(f"{url}/mcp", http_client=h)) as c:
        return await c.call_tool(tool, args or {})


def text(result):
    return " ".join(x.text for x in result.content if x.type == "text")


@pytest.mark.asyncio
async def test_status_and_snapshot_pass_through_unchanged():
    async with Serve(pc()) as pc_url, Serve(bridge(pc_url)) as url:
        status = await agent_call(url, "call", {"device": "windows", "service": "screen", "tool": "status"})
        assert not status.is_error and json.loads(text(status))["app"] == "game.exe"
        shot = await agent_call(url, "call", {"device": "windows", "service": "screen", "tool": "snapshot",
                                              "arguments": {"max_width": 2000}})
        image = base64.b64decode(next(x.data for x in shot.content if x.type == "image"))
        assert image[:2] == b"\xff\xd8" and len(image) > 1_000_000
        assert json.loads(next(x.text for x in shot.content if x.type == "text"))["black"] is False


@pytest.mark.asyncio
async def test_devices_says_who_answers_now():
    async with Serve(pc()) as pc_url, Serve(bridge(pc_url)) as url:
        d = json.loads(text(await agent_call(url, "devices")))["devices"]
        assert d == [{"device": "windows", "online": True, "services": ["screen"]}]
    async with Serve(bridge(f"http://127.0.0.1:{port()}")) as url:
        d = json.loads(text(await agent_call(url, "devices")))["devices"]
        assert d[0]["online"] is False


@pytest.mark.asyncio
async def test_failures_are_errors_with_a_reason():
    async with Serve(pc()) as pc_url, Serve(bridge(pc_url, pc_token="wrong")) as url:
        r = await agent_call(url, "call", {"device": "windows", "service": "screen", "tool": "status"})
        assert r.is_error and "token was refused" in text(r)
    async with Serve(bridge(f"http://127.0.0.1:{port()}", timeout_s=2.0)) as url:
        r = await agent_call(url, "call", {"device": "windows", "service": "screen", "tool": "status"})
        assert r.is_error and "windows: " in text(r) and "connect" in text(r).casefold()
        r = await agent_call(url, "call", {"device": "ipad", "service": "screen", "tool": "status"})
        assert r.is_error and "unknown device" in text(r)


@pytest.mark.asyncio
async def test_the_agent_needs_the_receiver_token_and_never_sees_the_pc_token():
    async with Serve(pc()) as pc_url, Serve(bridge(pc_url)) as url:
        async with httpx2.AsyncClient(trust_env=False) as h:
            assert (await h.get(f"{url}/health")).json() == {"ok": True, "devices": ["windows"]}
            assert (await h.post(f"{url}/mcp", json={})).status_code == 401
        d = text(await agent_call(url, "devices"))
        assert "pc-token" not in d and "127.0.0.1" not in d


@pytest.mark.asyncio
async def test_the_pc_offers_only_its_services():
    async with Serve(pc()) as pc_url, httpx2.AsyncClient(headers={"Authorization": "Bearer pc-token"}, trust_env=False) as h, \
            Client(streamable_http_client(f"{pc_url}/screen", http_client=h)) as c:
        assert sorted(t.name for t in (await c.list_tools()).tools) == ["snapshot", "status"]
        assert (await h.get(f"{pc_url}/health")).json()["services"] == ["screen"]


@pytest.mark.asyncio
async def test_a_black_capture_is_flagged():
    async with Serve(pc(lambda _m: Image.new("RGB", (64, 36)))) as pc_url, Serve(bridge(pc_url)) as url:
        r = await agent_call(url, "call", {"device": "windows", "service": "screen", "tool": "snapshot"})
        assert json.loads(next(x.text for x in r.content if x.type == "text"))["black"] is True


def test_configs_keep_tokens_and_round_trip_devices(tmp_path):
    d = init_device(tmp_path / "device.toml")
    assert len(d.token) > 30 and init_device(tmp_path / "device.toml").token == d.token
    r = init_receiver(tmp_path / "receiver.toml")
    r.devices["windows"] = Device("windows", "http://192.168.5.30:8770", 'to"ken')
    r.save(tmp_path / "receiver.toml")
    back = load_receiver(tmp_path / "receiver.toml")
    assert back.token == r.token and back.devices["windows"].token == 'to"ken' and back.host == "127.0.0.1"


@pytest.mark.asyncio
async def test_a_failing_capture_reaches_the_agent_with_its_reason(capsys):
    def broken(_m):
        raise OSError("no display")

    async with Serve(pc(broken)) as pc_url, Serve(bridge(pc_url)) as url:
        r = await agent_call(url, "call", {"device": "windows", "service": "screen", "tool": "snapshot"})
        assert r.is_error and "screen capture failed: OSError: no display" in text(r)
        from xifabot_serve.receiver.check import run_check
        cfg = ReceiverConfig(token="x", devices={"windows": Device("windows", pc_url, "pc-token")})
        assert await run_check(cfg, tries=1) is False
        assert "no display" in capsys.readouterr().out
