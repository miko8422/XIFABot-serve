# XIFABot-serve

A read-only bridge from your other devices to agents on your Mac. It was built for the [XIFABot Maid Agent](https://github.com/miko8422/XIFABot), but any MCP client can use it.

```text
Windows PC                         Mac
┌──────────────────┐  home   ┌─────────────────────┐ localhost ┌────────────┐
│ device side      │ network │ receiver side       │   MCP     │ your agent │
│ services answer  │◄───────►│ forwards requests,  │◄─────────►│            │
│ requests         │         │ holds the tokens    │           │            │
└──────────────────┘         └─────────────────────┘           └────────────┘
```

- **Request driven.** The agent asks, the receiver forwards the request to a service on the PC, and the answer comes back. Nothing is polled.
- **Services, not remote control.** A service answers about its own app or area. Nothing runs arbitrary commands on the PC.
- **Home network only.** Plain HTTP with a token on each hop. Nothing is reachable from the internet unless you forward a port, so don't.

| Device service | Tools |
| --- | --- |
| `screen` | `status`: front app, window title, idle time, locked. `snapshot`: a JPEG of the main display, flagged if it came back black |

The receiver gives agents two tools: `devices()` (which devices answer right now) and `call(device, service, tool, arguments)` (a service's answer, passed through unchanged). Agents never see device addresses or tokens.

## Setup

Needs [Git](https://git-scm.com/) and [uv](https://docs.astral.sh/uv/) on both machines. uv installs Python itself.

### 1. Windows PC

Install uv in PowerShell, then open a new terminal:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Then:

```powershell
git clone https://github.com/miko8422/XIFABot-serve.git
cd XIFABot-serve
uv sync
uv run xifabot-serve device init      # prints a `receiver add …` command: copy it
uv run xifabot-serve device doctor    # fix any FAIL, see "Windows settings"
uv run xifabot-serve device serve     # keep this running
```

### 2. Mac

```bash
git clone https://github.com/miko8422/XIFABot-serve.git
cd XIFABot-serve
uv sync
uv run xifabot-serve receiver init    # prints two lines for your agent's .env
uv run xifabot-serve receiver add windows --url http://… --token …   # the command from the PC
uv run xifabot-serve receiver check   # tests the network, VPN routes, token, status and snapshot timing
uv run xifabot-serve receiver serve   # keep this running
```

For the Maid, put the two lines in `.env` at the XIFABot repo root, then run `uv run maid-agent serve-check` there.

## Windows settings

`device doctor` checks most of these.

| Setting | Why | Where |
| --- | --- | --- |
| Network profile: **Private** | On Public, Windows blocks incoming connections | Settings › Network & internet › Ethernet (or Wi-Fi) › Network profile type |
| Firewall rule for port 8770 | Lets the Mac in, on the Private network only | Administrator terminal: `netsh advfirewall firewall add rule name="XIFABot serve" dir=in action=allow protocol=TCP localport=8770 profile=private`. If Windows shows an "allow access" prompt instead, tick **Private** only |
| A fixed IP for the PC | Otherwise the address can change after a reboot | In your router: DHCP reservation for the PC. If it changes anyway, run `device init` again and repeat `receiver add` |
| Don't sleep | A sleeping PC can't answer. A turned-off display is fine | Settings › System › Power › Screen, sleep & hibernate timeouts › sleep: Never |
| Run it in your desktop session | A real Windows Service can't capture the desktop | To start it at login: Win+R → `shell:startup` → new shortcut to `cmd /k "cd /d C:\path\to\XIFABot-serve && uv run xifabot-serve device serve"` |
| Games: borderless or windowed mode | Exclusive fullscreen often captures as black | In the game's display settings. `doctor` with the game in front tells you |
| Several displays | The snapshot uses the primary display | `monitor` in `device.toml` (1 = primary) |

No administrator rights are needed to run it, only to add the firewall rule.

## VPNs

Both machines can use a VPN, as long as it leaves the home network alone.

- **On the PC:** turn on the VPN's **allow LAN**, **local network sharing** or **split tunnelling** option. A **kill switch** often blocks the LAN too. Your home IP stays the same; `doctor` lists every interface and marks VPN ones.
- **On the Mac:** the same, often called **bypass LAN** or "exclude private addresses". In TUN mode (Clash and similar), make sure `192.168.0.0/16` and `10.0.0.0/8` are bypassed. `receiver check` shows which interface the traffic leaves by and says when a VPN is capturing it.
- **Always use the PC's IP, not its name.** A VPN's DNS may answer names with fake addresses. `device init` prints the IP for this reason.
- **Proxies are ignored.** The bridge never sends home-network traffic through a system or environment proxy.
- **Reconnects:** a request that fails to connect is retried once, because a VPN reconnecting often fails exactly one attempt.

## If something fails

Run `receiver check` on the Mac. It stops at the first failed step and says what to look at.

| Step fails | Usually |
| --- | --- |
| route | A VPN on the Mac is capturing home-network traffic |
| reach | `device serve` isn't running, wrong IP, network set to Public, no firewall rule, a VPN on the PC blocking the LAN, or the Mac is on a guest Wi-Fi |
| status | The token: run `device init` again and repeat the `receiver add` it prints |
| snapshot | The capture: run `device doctor` on the PC |

## Adding a service

Write `src/xifabot_serve/device/services/<name>.py` with `build(cfg) -> MCPServer`, and add it to `SERVICES` in `device/services/__init__.py`. It gets its own endpoint on the PC, and the receiver forwards it with no change. Anything Windows-specific goes in `device/platform_windows.py`.

## License

MIT
