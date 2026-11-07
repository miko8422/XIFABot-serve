"""config.toml at the repo root, git-ignored: it holds the token."""

from __future__ import annotations

import secrets
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.toml"
ON_WINDOWS = sys.platform == "win32"


@dataclass
class Config:
    token: str = ""
    # the Mac serves the Maid on the same machine; the PC serves her over the home network
    host: str = field(default_factory=lambda: "0.0.0.0" if ON_WINDOWS else "127.0.0.1")
    port: int = field(default_factory=lambda: 8770 if ON_WINDOWS else 8771)
    machine: str = field(default_factory=lambda: "windows" if ON_WINDOWS else "mac")
    monitor: int = 1        # mss numbering: 1 is the primary display
    jpeg_quality: int = 80


def load_config(path: Path = CONFIG_PATH) -> Config:
    if not path.exists():
        raise SystemExit(f"no {path}: run `xifabot-serve init` first")
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    cfg = Config(**{k: raw[k] for k in Config.__dataclass_fields__ if k in raw})
    if not cfg.token:
        raise SystemExit(f"{path} has no token: delete it and run `xifabot-serve init`")
    return cfg


def create_config(path: Path = CONFIG_PATH) -> Config:
    """Keeps an existing token, so running init twice doesn't disconnect the Maid."""
    cfg = load_config(path) if path.exists() else Config(token=secrets.token_urlsafe(32))
    path.write_text(
        f'token = "{cfg.token}"\nhost = "{cfg.host}"\nport = {cfg.port}\nmachine = "{cfg.machine}"\n'
        f"monitor = {cfg.monitor}\njpeg_quality = {cfg.jpeg_quality}\n", encoding="utf-8")
    return cfg
