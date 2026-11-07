"""Checks on this machine, each one printed with what to do if it fails."""

from __future__ import annotations

import socket
import subprocess
from pathlib import Path

from .config import ON_WINDOWS, Config
from .platforms import current
from .services.screen import encode, grab

SNAPSHOT = Path(__file__).resolve().parents[2] / "doctor_snapshot.jpg"


def lan_address() -> str:
    """The address this machine uses on the home network. Connecting a UDP socket sends nothing."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("192.168.0.1", 9))
            return s.getsockname()[0]
        except OSError:
            return "127.0.0.1"


def maid_lines(cfg: Config) -> str:
    prefix = cfg.machine.upper()
    address = lan_address() if cfg.host == "0.0.0.0" else cfg.host
    return f"{prefix}_SERVE_URL=http://{address}:{cfg.port}\n{prefix}_SERVE_TOKEN={cfg.token}"


def _line(ok: bool, name: str, detail: str) -> bool:
    print(f"[{'ok' if ok else 'FAIL'}] {name}: {detail}", flush=True)
    return ok


def run_doctor(cfg: Config) -> bool:
    plat = current()
    fg = plat.foreground()
    results = [_line(bool(fg.app), "front app", f"{fg.app or 'none'} / {fg.title[:60]}"),
               _line(True, "idle time", f"{plat.idle_seconds():.1f} s")]
    try:
        data, info = encode(grab(cfg.monitor), 1600, cfg.jpeg_quality)
        SNAPSHOT.write_bytes(data)
        results.append(_line(not info["black"], "screen capture", f"{info['width']}x{info['height']}, {len(data) // 1024} KB, "
                             f"saved to {SNAPSHOT}" + (" (BLACK: on Windows, run this again with the game in front; "
                                                       "on the Mac, allow Screen Recording for this terminal)" if info["black"] else "")))
    except Exception as e:  # noqa: BLE001 - doctor reports, it doesn't stop
        results.append(_line(False, "screen capture", f"{type(e).__name__}: {e}"))
    if ON_WINDOWS:
        address = lan_address()
        results.append(_line(not address.startswith("127."), "network address", address))
        out = subprocess.run(["powershell", "-NoProfile", "-Command", "(Get-NetConnectionProfile).NetworkCategory"],
                             capture_output=True, text=True, timeout=20).stdout.split()
        results.append(_line("Public" not in out, "network profile",
                             f"{', '.join(out) or 'unknown'}" + (" (set it to Private in Windows settings)" if "Public" in out else "")))
        print(f"\nIf the Maid can't connect, allow the port once, in an administrator terminal:\n"
              f'netsh advfirewall firewall add rule name="XIFABot serve" dir=in action=allow protocol=TCP '
              f"localport={cfg.port} profile=private")
    return all(results)
