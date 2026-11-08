"""xifabot-serve: a read-only bridge from your other devices to agents on your Mac.

On the Windows PC (the device):
  xifabot-serve device init      make device.toml with a token, print the command to run on the Mac
  xifabot-serve device doctor    check capture, front app, network and VPN on this PC
  xifabot-serve device serve     answer requests from the Mac

On the Mac (the receiver):
  xifabot-serve receiver init    make receiver.toml with a token, print the lines for your agent's .env
  xifabot-serve receiver add     remember a device (the command `device init` printed)
  xifabot-serve receiver check   test every device: network, VPN routes, token, status, snapshot timing
  xifabot-serve receiver serve   serve every device to local agents on 127.0.0.1
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from .config import DEVICE_PATH, RECEIVER_PATH


def main() -> None:
    ap = argparse.ArgumentParser(prog="xifabot-serve")
    side = ap.add_subparsers(dest="side", required=True)

    dev = side.add_parser("device", help="the device side (Windows PC)")
    dev.add_argument("--config", type=Path, default=DEVICE_PATH)
    dcmd = dev.add_subparsers(dest="cmd", required=True)
    dcmd.add_parser("init", help="create device.toml with a new token")
    dcmd.add_parser("doctor", help="check that this PC can answer")
    dcmd.add_parser("serve", help="answer requests (keep it running in your desktop session)")

    rec = side.add_parser("receiver", help="the receiver side (Mac)")
    rec.add_argument("--config", type=Path, default=RECEIVER_PATH)
    rcmd = rec.add_subparsers(dest="cmd", required=True)
    rcmd.add_parser("init", help="create receiver.toml with a new token")
    add = rcmd.add_parser("add", help="add or update a device")
    add.add_argument("name")
    add.add_argument("--url", required=True)
    add.add_argument("--token", required=True)
    rcmd.add_parser("check", help="test every device")
    rcmd.add_parser("serve", help="serve every device on 127.0.0.1")

    args = ap.parse_args()
    if args.side == "device":
        from . import device
        device.cli(args)
    else:
        from . import receiver
        receiver.cli(args)
