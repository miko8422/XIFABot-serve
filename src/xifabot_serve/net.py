"""Network facts for both sides: which address is the home network, and whether a VPN is in the way.

Home networks use private ranges. VPNs and proxy tunnels add their own interfaces (Clash and similar tools often use
198.18.0.0/15, Tailscale 100.64.0.0/10), and the default route may go through them. So the home address is picked
from the interfaces, never from the default route, and devices are always addressed by IP: a VPN's DNS may answer
a host name with a fake address.
"""

from __future__ import annotations

import ipaddress
import json
import re
import subprocess
import sys

VPN_WORDS = ("vpn", "tap", "tun", "wintun", "wireguard", "wg", "clash", "mihomo", "meta", "tailscale", "zerotier",
             "openvpn", "nord", "express", "proton", "surfshark", "astrill", "cisco", "anyconnect", "fortinet", "ipsec",
             "ppp", "utun", "virtual", "vethernet", "hyper-v", "vmware", "virtualbox", "loopback")
VPN_NETS = [ipaddress.ip_network(n) for n in ("198.18.0.0/15", "100.64.0.0/10", "169.254.0.0/16", "127.0.0.0/8")]


def is_home_address(ip: str) -> bool:
    a = ipaddress.ip_address(ip)
    return a.version == 4 and a.is_private and not any(a in n for n in VPN_NETS)


def looks_like_vpn(interface: str) -> bool:
    name = interface.casefold()
    return any(re.search(rf"(^|[^a-z]){w}", name) for w in VPN_WORDS)


def interfaces() -> list[tuple[str, str]]:
    """(interface name, IPv4 address) for every interface that is up."""
    if sys.platform == "win32":
        out = subprocess.run(["powershell", "-NoProfile", "-Command",
                              "Get-NetIPAddress -AddressFamily IPv4 | Select-Object InterfaceAlias,IPAddress | ConvertTo-Json"],
                             capture_output=True, text=True, timeout=20).stdout
        rows = json.loads(out or "[]")
        rows = rows if isinstance(rows, list) else [rows]
        return [(r["InterfaceAlias"], r["IPAddress"]) for r in rows]
    out = subprocess.run(["ifconfig"], capture_output=True, text=True, timeout=10).stdout
    found, name = [], ""
    for line in out.splitlines():
        if line and not line[0].isspace():
            name = line.split(":")[0]
        elif m := re.search(r"inet (\d+\.\d+\.\d+\.\d+)", line):
            found.append((name, m.group(1)))
    return found


def home_addresses(found: list[tuple[str, str]] | None = None) -> list[tuple[str, str]]:
    """Best first: private addresses on interfaces that don't look like a VPN."""
    found = interfaces() if found is None else found
    return [(n, ip) for n, ip in found if is_home_address(ip) and not looks_like_vpn(n)]


def route_interface(ip: str) -> str:
    """The interface traffic to `ip` leaves by, on the Mac. "" if unknown."""
    if sys.platform != "darwin":
        return ""
    out = subprocess.run(["route", "-n", "get", ip], capture_output=True, text=True, timeout=10).stdout
    m = re.search(r"interface:\s*(\S+)", out)
    return m.group(1) if m else ""
