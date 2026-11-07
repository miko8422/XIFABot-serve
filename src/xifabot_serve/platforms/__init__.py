"""Everything that differs between machines. A platform module has foreground(), idle_seconds() and is_locked(app)."""

from __future__ import annotations

import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class Foreground:
    app: str
    title: str


def current():
    if sys.platform == "win32":
        from . import windows
        return windows
    if sys.platform == "darwin":
        from . import mac
        return mac
    raise SystemExit(f"no platform support for {sys.platform}")
