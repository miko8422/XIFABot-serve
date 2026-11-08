"""Checks on the PC, each one printed with what to do if it fails."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from .. import net
from ..config import ROOT, DeviceConfig
from .platform import current

SNAPSHOT = ROOT / "doctor_snapshot.jpg"


def add_command(cfg: DeviceConfig) -> str:
    home = net.home_addresses()
    ip = home[0][1] if home else "<this PC's home-network IP>"
    return f"uv run xifabot-serve receiver add {cfg.name} --url http://{ip}:{cfg.port} --token {cfg.token}"


def _line(ok: bool | None, name: str, detail: str) -> bool:
    print(f"[{'ok' if ok else 'note' if ok is None else 'FAIL'}] {name}: {detail}", flush=True)
    return ok is not False


def run_doctor(cfg: DeviceConfig) -> bool:
    plat = current()
    results = [_line(sys.platform == "win32", "windows", sys.platform)]
    fg = plat.foreground()
    results.append(_line(bool(fg.app), "front app", f"{fg.app or 'none'} / {fg.title[:60]}"))
    results.append(_line(None, "idle time", f"{plat.idle_seconds():.1f} s (game controllers may not count as input)"))
    try:
        from .services.screen import encode, grab
        data, info = encode(grab(cfg.monitor), 1600, cfg.jpeg_quality)
        SNAPSHOT.write_bytes(data)
        results.append(_line(not info["black"], "screen capture", f"{info['width']}x{info['height']}, {len(data) // 1024} KB, "
                             f"saved to {SNAPSHOT}" + (" (BLACK: see README, fullscreen games)" if info["black"] else "")))
    except Exception as e:  # noqa: BLE001 - doctor reports, it doesn't stop
        results.append(_line(False, "screen capture", f"{type(e).__name__}: {e}"))

    found = net.interfaces()
    home = net.home_addresses(found)
    for name, ip in found:
        kind = "home network" if (name, ip) in home else "VPN or virtual, not used" if net.looks_like_vpn(name) else "other"
        _line(None, "interface", f"{name}: {ip} ({kind})")
    results.append(_line(bool(home), "home address", home[0][1] if home else "none found: is the PC on the home network?"))
    if len(home) > 1:
        _line(None, "home address", f"{len(home)} candidates; if the Mac can't connect, try the others")

    if sys.platform == "win32":
        out = subprocess.run(["powershell", "-NoProfile", "-Command",
                              "Get-NetConnectionProfile | ForEach-Object { $_.InterfaceAlias + '=' + $_.NetworkCategory }"],
                             capture_output=True, text=True, timeout=20).stdout.split("\n")
        profiles = dict(line.strip().split("=", 1) for line in out if "=" in line)
        home_names = {n for n, _ in home}
        for alias, category in profiles.items():
            if alias in home_names:
                results.append(_line(category != "Public", "network profile", f"{alias}: {category}"
                                     + (" (set it to Private: Settings > Network & internet > your connection)" if category == "Public" else "")))
        rule = subprocess.run(["netsh", "advfirewall", "firewall", "show", "rule", "name=XIFABot serve"],
                              capture_output=True, text=True, timeout=20).stdout
        results.append(_line("XIFABot serve" in rule, "firewall rule", "present" if "XIFABot serve" in rule else
                             "missing. In an administrator terminal:\n       netsh advfirewall firewall add rule "
                             f'name="XIFABot serve" dir=in action=allow protocol=TCP localport={cfg.port} profile=private'))
    return all(results)
