# XIFABot-serve

Read-only information services for the [Maid Agent](https://github.com/miko8422/XIFABot). The same code runs on the Mac and on the Windows PC, each with its own environment. The Maid reads them over MCP. Nothing here can change anything on the machine.

```text
Windows PC  xifabot-serve ──home network──┐
                                          ├─► Maid Agent (Mac)
Mac         xifabot-serve ──localhost─────┘
```

| Machine | Listens on | Reached by |
| --- | --- | --- |
| Windows | `0.0.0.0:8770` | the Maid, over the home network |
| Mac | `127.0.0.1:8771` | the Maid, on the same Mac only |

## Services

| Service | Endpoint | Tools |
| --- | --- | --- |
| `screen` | `/screen` | `status`: front app, window title, idle time, locked. `snapshot`: a JPEG of the main display |

`/health` needs no token and says nothing about the machine. Everything else needs `Authorization: Bearer <token>`.

## Install

Needs Python 3.12 or newer and [uv](https://docs.astral.sh/uv/). On each machine:

```bash
git clone https://github.com/miko8422/XIFABot-serve.git
cd XIFABot-serve
uv sync
uv run xifabot-serve init      # makes config.toml, prints two lines for the Maid's .env
uv run xifabot-serve doctor    # checks capture, front app, idle time and the network
uv run xifabot-serve serve     # keep this running
```

Add the two lines to `.env` in the Maid's repo on the Mac, then check from there:

```bash
uv run maid-agent serve-check            # the Windows PC
uv run maid-agent serve-check --mac      # this Mac
```

## If something fails

- **Can't connect to Windows:** set the network to Private in Windows settings, and allow the port. `doctor` prints the command. The Mac must not be on a guest Wi-Fi.
- **The address changed:** reserve a fixed IP for the PC in your router.
- **Black screenshots on Windows:** usually an exclusive-fullscreen game. Try borderless windowed mode, then run `doctor` with the game in front.
- **Black screenshots on the Mac:** allow Screen Recording for your terminal in System Settings.
- **Several displays:** set `monitor` in `config.toml`. 1 is the primary display.

## Running it

It must run in your desktop session. A true Windows Service can't capture the desktop. To start it at login on Windows, put a shortcut in `shell:startup` that runs `uv run xifabot-serve serve` in this folder.

## Security

Windows traffic is plain HTTP on your home network, protected by the token in `config.toml`, which is never committed. Keep it off guest networks, and don't forward this port on your router.

## Adding a service

Write `src/xifabot_serve/services/<name>.py` with `build(cfg) -> MCPServer`, and add it to `SERVICES` in `services/__init__.py`. Anything that differs per machine goes in `platforms/`. Services only give information.
