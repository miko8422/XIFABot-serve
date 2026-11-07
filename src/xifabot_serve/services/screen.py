"""The screen service: what is in front of the user on this PC, and a snapshot of it."""

from __future__ import annotations

import asyncio
import io
import json
import time
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.utilities.types import Image as McpImage
from PIL import Image

from ..config import Config
from ..platforms import current

BLACK_LEVEL = 16  # no pixel brighter than this: the capture failed, usually an exclusive-fullscreen game


def grab(monitor: int) -> Image.Image:
    import mss
    with mss.MSS() as s:
        shot = s.grab(s.monitors[monitor])
    return Image.frombytes("RGB", shot.size, shot.rgb)


def is_black(image: Image.Image) -> bool:
    return max(image.convert("L").getextrema()) <= BLACK_LEVEL


def read_status(cfg: Config, plat) -> dict[str, Any]:
    fg = plat.foreground()
    return {"machine": cfg.machine, "app": fg.app, "title": fg.title, "idle_s": round(plat.idle_seconds(), 1),
            "locked": plat.is_locked(fg.app), "time": time.time()}


def encode(image: Image.Image, max_width: int, quality: int) -> tuple[bytes, dict[str, Any]]:
    black = is_black(image)
    if image.width > max_width:
        image = image.resize((max_width, round(image.height * max_width / image.width)))
    buf = io.BytesIO()
    image.convert("RGB").save(buf, "JPEG", quality=quality)
    return buf.getvalue(), {"width": image.width, "height": image.height, "black": black}


def build(cfg: Config, grabber=grab, plat=None) -> MCPServer:
    plat = plat or current()
    server = MCPServer(f"xifabot-serve-screen-{cfg.machine}", instructions="Read-only: front app, idle time and screen.")

    @server.tool()
    def status() -> dict[str, Any]:
        """The front app and its window title, seconds since the last input, and whether this machine is locked."""
        return read_status(cfg, plat)

    @server.tool()
    async def snapshot(max_width: int = 1600) -> list:
        """A JPEG of the main display, plus the status and whether the capture came back black."""
        image = await asyncio.to_thread(grabber, cfg.monitor)
        data, info = await asyncio.to_thread(encode, image, max_width, cfg.jpeg_quality)
        return [json.dumps({**read_status(cfg, plat), **info}, ensure_ascii=False), McpImage(data=data, format="jpeg")]

    return server
