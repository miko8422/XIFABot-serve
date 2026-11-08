"""What differs per device. Only Windows is supported; any other platform gets empty values, for development."""

from __future__ import annotations

import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class Foreground:
    app: str
    title: str


class _Unsupported:
    name = sys.platform

    @staticmethod
    def foreground() -> Foreground:
        return Foreground("", "")

    @staticmethod
    def idle_seconds() -> float:
        return 0.0

    @staticmethod
    def is_locked(_app: str) -> bool:
        return False


def current():
    if sys.platform == "win32":
        from . import platform_windows
        return platform_windows
    return _Unsupported
