"""The Mac, through AppKit and Quartz. Read-only."""

from __future__ import annotations

import Quartz
from AppKit import NSWorkspace

from . import Foreground


def foreground() -> Foreground:
    app = NSWorkspace.sharedWorkspace().frontmostApplication()
    return Foreground(str(app.localizedName() or "") if app else "", "")


def idle_seconds() -> float:
    """Seconds since the last keyboard or mouse input."""
    return float(Quartz.CGEventSourceSecondsSinceLastEventType(
        Quartz.kCGEventSourceStateCombinedSessionState, Quartz.kCGAnyInputEventType))


def is_locked(_app: str) -> bool:
    session = Quartz.CGSessionCopyCurrentDictionary() or {}
    return bool(session.get("CGSSessionScreenIsLocked", False))
