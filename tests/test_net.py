from xifabot_serve.net import home_addresses, is_home_address, looks_like_vpn


def test_vpn_and_proxy_ranges_are_not_home():
    assert is_home_address("192.168.5.24") and is_home_address("10.0.0.7") and is_home_address("172.20.1.2")
    for ip in ("198.18.0.1", "100.101.1.1", "169.254.3.3", "127.0.0.1", "8.8.8.8"):
        assert not is_home_address(ip)


def test_vpn_interfaces_are_recognised_but_ethernet_and_wifi_are_not():
    for name in ("utun8", "Clash", "Mihomo", "Wintun Userspace Tunnel", "WireGuard Tunnel", "NordLynx VPN", "Tailscale",
                 "vEthernet (WSL)", "OpenVPN TAP-Windows6", "Loopback Pseudo-Interface 1"):
        assert looks_like_vpn(name), name
    for name in ("Ethernet", "Ethernet 2", "Wi-Fi", "en0", "WLAN", "以太网"):
        assert not looks_like_vpn(name), name


def test_home_address_skips_vpn_even_with_a_private_ip():
    found = [("Clash", "198.18.0.1"), ("OpenVPN TAP-Windows6", "10.8.0.2"), ("Ethernet", "192.168.5.30"),
             ("vEthernet (WSL)", "172.28.0.1")]
    assert home_addresses(found) == [("Ethernet", "192.168.5.30")]
