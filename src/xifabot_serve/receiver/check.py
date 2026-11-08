"""The first test from the Mac: can it reach each device, and how fast? Stops per device at the first failed step."""

from __future__ import annotations

import base64
import json
import time
from urllib.parse import urlparse

from .. import net
from ..config import ROOT, ReceiverConfig
from .client import DeviceClient, DeviceUnavailable

SNAPSHOT = ROOT / "check_snapshot.jpg"


def _text(result) -> str:
    return " ".join(x.text for x in result.content if x.type == "text")


def _p(ok: bool | None, step: str, detail: str) -> bool:
    print(f"[{'ok' if ok else 'note' if ok is None else 'FAIL'}] {step}: {detail}", flush=True)
    return ok is not False


async def run_check(cfg: ReceiverConfig, tries: int = 5) -> bool:
    if not cfg.devices:
        return _p(False, "devices", "none yet: run the `receiver add` command that `device init` printed")
    ok = True
    for d in cfg.devices.values():
        print(f"\n== {d.name} ({d.url})")
        ok = await _check_one(DeviceClient(d, cfg.timeout_s), tries) and ok
    return ok


async def _check_one(c: DeviceClient, tries: int) -> bool:
    host = urlparse(c.device.url).hostname or ""
    if not host.replace(".", "").isdigit():
        _p(None, "address", f"{host} is a name; use the IP, because a VPN's DNS may answer with a fake address")
    elif not net.is_home_address(host):
        _p(None, "address", f"{host} is not a home-network address; is it the PC's VPN address?")
    if via := net.route_interface(host):
        if not _p(not net.looks_like_vpn(via), "route", f"traffic to {host} leaves by {via}" + (
                " (a VPN on this Mac is capturing home-network traffic: turn on its LAN bypass / allow-LAN option, "
                "or exclude 192.168.0.0/16)" if net.looks_like_vpn(via) else "")):
            return False
    t0 = time.monotonic()
    try:
        h = await c.health()
    except Exception as e:  # noqa: BLE001
        return _p(False, "reach", f"{type(e).__name__}: {e}\n       Is `device serve` running on the PC? Is the IP right? "
                  "Is the PC's network Private and the firewall rule there? Is a VPN on the PC blocking the local "
                  "network (look for allow-LAN or split tunnelling)? Is the Mac on a guest Wi-Fi?")
    _p(True, "reach", f"{(time.monotonic() - t0) * 1000:.0f} ms, device {h.get('device')}, services {', '.join(h['services'])}")
    try:
        r = await c.call("screen", "status")
    except DeviceUnavailable as e:
        return _p(False, "status", f"{e}" + ("\n       Run `device init` on the PC again and copy the command it prints."
                                              if "token" in str(e) else ""))
    if r.is_error:
        return _p(False, "status", _text(r))
    st = r.structured_content or json.loads(r.content[0].text)
    st = st.get("result", st)
    _p(True, "status", f"front app {st.get('app') or 'unknown'}, idle {st.get('idle_s')} s, locked {st.get('locked')}")
    times, size, meta, data = [], 0, {}, b""
    for _ in range(tries):
        t0 = time.monotonic()
        try:
            r = await c.call("screen", "snapshot")
        except DeviceUnavailable as e:
            return _p(False, "snapshot", str(e))
        if r.is_error:
            return _p(False, "snapshot", _text(r) + "\n       Run `device doctor` on the PC: it tests the capture directly.")
        times.append((time.monotonic() - t0) * 1000)
        meta = json.loads(next(x.text for x in r.content if x.type == "text"))
        data = base64.b64decode(next(x.data for x in r.content if x.type == "image"))
        size = len(data)
    SNAPSHOT.write_bytes(data)
    times.sort()
    _p(True, "snapshot", f"x{tries}: {meta.get('width')}x{meta.get('height')}, {size // 1024} KB, median {times[len(times) // 2]:.0f} ms, "
       f"worst {times[-1]:.0f} ms, saved to {SNAPSHOT}")
    if meta.get("black"):
        return _p(False, "picture", "black: the PC can't capture this screen (usually an exclusive-fullscreen game)")
    return True
