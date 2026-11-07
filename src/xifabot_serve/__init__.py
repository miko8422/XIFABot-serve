"""xifabot-serve: read-only information services for the Maid Agent. The same code runs on the Mac and the Windows PC.

  xifabot-serve init     make config.toml with a new token, print the lines for the Maid's .env
  xifabot-serve doctor   check capture, front app, idle time and the network on this machine
  xifabot-serve serve    run the services
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from .config import CONFIG_PATH, Config, create_config, load_config


def main() -> None:
    ap = argparse.ArgumentParser(prog="xifabot-serve")
    ap.add_argument("--config", type=Path, default=CONFIG_PATH)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init", help="create config.toml with a new token")
    sub.add_parser("doctor", help="check that this machine can provide its information")
    sub.add_parser("serve", help="run the services (keep this running in your desktop session)")
    args = ap.parse_args()
    if args.cmd == "init":
        from .doctor import maid_lines
        cfg = create_config(args.config)
        print(f"config: {args.config}\n\nAdd these lines to .env in the Maid's repo on the Mac:\n{maid_lines(cfg)}")
    elif args.cmd == "doctor":
        from .doctor import run_doctor
        raise SystemExit(0 if run_doctor(load_config(args.config) if args.config.exists() else Config()) else 1)
    elif args.cmd == "serve":
        from .host import serve
        asyncio.run(serve(load_config(args.config)))
