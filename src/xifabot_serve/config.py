"""device.toml (on the PC) and receiver.toml (on the Mac), at the repo root and git-ignored: they hold tokens."""

from __future__ import annotations

import secrets
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEVICE_PATH = ROOT / "device.toml"
RECEIVER_PATH = ROOT / "receiver.toml"


def _q(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


@dataclass
class DeviceConfig:
    token: str = ""
    name: str = "windows"
    host: str = "0.0.0.0"   # every interface; the firewall rule lets in the Private network only
    port: int = 8770
    monitor: int = 1        # mss numbering: 1 is the primary display
    jpeg_quality: int = 80

    def save(self, path: Path) -> None:
        path.write_text(f"token = {_q(self.token)}\nname = {_q(self.name)}\nhost = {_q(self.host)}\nport = {self.port}\n"
                        f"monitor = {self.monitor}\njpeg_quality = {self.jpeg_quality}\n", encoding="utf-8")


@dataclass
class Device:
    name: str
    url: str
    token: str


@dataclass
class ReceiverConfig:
    token: str = ""
    host: str = "127.0.0.1"  # local agents only
    port: int = 8771
    timeout_s: float = 8.0
    devices: dict[str, Device] = field(default_factory=dict)

    def save(self, path: Path) -> None:
        lines = [f"token = {_q(self.token)}", f"host = {_q(self.host)}", f"port = {self.port}", f"timeout_s = {self.timeout_s}"]
        for d in self.devices.values():
            lines += ["", f"[devices.{d.name}]", f"url = {_q(d.url)}", f"token = {_q(d.token)}"]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _load(path: Path, side: str) -> dict:
    if not path.exists():
        raise SystemExit(f"no {path}: run `xifabot-serve {side} init` first")
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    if not raw.get("token"):
        raise SystemExit(f"{path} has no token: delete it and run `xifabot-serve {side} init`")
    return raw


def load_device(path: Path = DEVICE_PATH) -> DeviceConfig:
    raw = _load(path, "device")
    return DeviceConfig(**{k: raw[k] for k in DeviceConfig.__dataclass_fields__ if k in raw})


def load_receiver(path: Path = RECEIVER_PATH) -> ReceiverConfig:
    raw = _load(path, "receiver")
    devices = {n: Device(n, d["url"].rstrip("/"), d["token"]) for n, d in raw.get("devices", {}).items()}
    keys = [k for k in ReceiverConfig.__dataclass_fields__ if k in raw and k != "devices"]
    return ReceiverConfig(**{k: raw[k] for k in keys}, devices=devices)


def init_device(path: Path = DEVICE_PATH) -> DeviceConfig:
    """Keeps an existing token, so running init twice doesn't disconnect the Mac."""
    cfg = load_device(path) if path.exists() else DeviceConfig(token=secrets.token_urlsafe(32))
    cfg.save(path)
    return cfg


def init_receiver(path: Path = RECEIVER_PATH) -> ReceiverConfig:
    cfg = load_receiver(path) if path.exists() else ReceiverConfig(token=secrets.token_urlsafe(32))
    cfg.save(path)
    return cfg
