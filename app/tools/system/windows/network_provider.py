"""
Windows Network Information Provider with Strict IPv4 Validation & Sanitization (B.33)
"""

import re
import socket
import subprocess
from typing import Any, Dict, List, Optional
from app.platform.contracts import NetworkInfoProvider

IPV4_PATTERN = re.compile(r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$")


def is_valid_ipv4(ip: str) -> bool:
    """Validate that a string is a strictly formatted IPv4 dotted-quad address."""
    if not ip or not isinstance(ip, str):
        return False
    clean = ip.strip()
    return bool(IPV4_PATTERN.match(clean))


class WindowsNetworkInfoProvider(NetworkInfoProvider):
    """Windows implementation for network adapter and IP configuration with B.33 validation."""

    def _get_ipconfig_details(self) -> Dict[str, Dict[str, Any]]:
        """Parse ipconfig /all for default gateways and DNS servers."""
        details: Dict[str, Dict[str, Any]] = {}
        try:
            res = subprocess.run(
                ["ipconfig", "/all"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if res.returncode == 0:
                current_adapter: Optional[str] = None
                for line in res.stdout.splitlines():
                    # Adapter section headers, e.g. "Wireless LAN adapter Wi-Fi:" or "Ethernet adapter Ethernet:"
                    adapter_match = re.match(r"^[A-Za-z0-9\s\*\-]+adapter\s+([^:]+):", line)
                    if adapter_match:
                        current_adapter = adapter_match.group(1).strip()
                        details[current_adapter] = {"gateway": "None", "dns": []}
                        continue

                    if current_adapter and current_adapter in details:
                        # Gateway
                        if "Default Gateway" in line:
                            gw_match = re.search(r":\s*([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)", line)
                            if gw_match and is_valid_ipv4(gw_match.group(1)):
                                details[current_adapter]["gateway"] = gw_match.group(1)
                        # DNS Servers
                        elif "DNS Servers" in line:
                            dns_match = re.search(r":\s*([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)", line)
                            if dns_match and is_valid_ipv4(dns_match.group(1)):
                                details[current_adapter]["dns"].append(dns_match.group(1))
                        elif details[current_adapter]["dns"] and line.startswith("   ") and re.match(r"^\s+([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)", line):
                            extra_dns = re.search(r"([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)", line)
                            if extra_dns and is_valid_ipv4(extra_dns.group(1)):
                                details[current_adapter]["dns"].append(extra_dns.group(1))
        except Exception:
            pass
        return details

    def get_network_info(self) -> Dict[str, Any]:
        """Collect network adapters with guaranteed IPv4 formatting."""
        adapters: List[Dict[str, Any]] = []
        ipconfig_details = self._get_ipconfig_details()
        primary_ipv4: Optional[str] = None

        # 1. Native psutil inspection
        try:
            import psutil
            addrs = psutil.net_if_addrs()
            stats = psutil.net_if_stats()

            for iface_name, addr_list in addrs.items():
                ipv4_addrs = []
                ipv6_addrs = []
                mac_addr = ""

                for a in addr_list:
                    # AF_INET (IPv4)
                    if a.family == socket.AF_INET:
                        if is_valid_ipv4(a.address):
                            ipv4_addrs.append(a.address)
                    elif hasattr(socket, "AF_INET6") and a.family == socket.AF_INET6:
                        ipv6_addrs.append(a.address.split("%")[0])
                    elif a.family == -1 or "AF_LINK" in str(a.family):
                        mac_addr = a.address

                is_up = stats[iface_name].isup if iface_name in stats else True

                # Lookup gateways & DNS from parsed ipconfig details
                gw = "None"
                dns_servers = []
                for k, v in ipconfig_details.items():
                    if k.lower() in iface_name.lower() or iface_name.lower() in k.lower():
                        gw = v.get("gateway", "None")
                        dns_servers = v.get("dns", [])
                        break

                formatted_ipv4 = ", ".join(ipv4_addrs) if ipv4_addrs else "Not Configured"

                # Check if this is the active routable primary adapter
                if is_up and ipv4_addrs:
                    for ip in ipv4_addrs:
                        if not ip.startswith("127.") and not ip.startswith("169.254."):
                            if not primary_ipv4 or gw != "None":
                                primary_ipv4 = ip

                adapters.append({
                    "alias": iface_name,
                    "description": iface_name,
                    "ipv4_address": formatted_ipv4,
                    "ipv4_list": ipv4_addrs,
                    "ipv6_address": ", ".join(ipv6_addrs) if ipv6_addrs else "None",
                    "mac_address": mac_addr or "None",
                    "is_up": is_up,
                    "gateway": gw,
                    "dns_servers": dns_servers,
                })
        except Exception:
            # Fallback to standard socket inspection
            try:
                hostname = socket.gethostname()
                host_ip = socket.gethostbyname(hostname)
                if is_valid_ipv4(host_ip):
                    primary_ipv4 = host_ip
                    adapters.append({
                        "alias": "Default Adapter",
                        "description": "System Network Interface",
                        "ipv4_address": host_ip,
                        "ipv4_list": [host_ip],
                        "ipv6_address": "None",
                        "mac_address": "None",
                        "is_up": True,
                        "gateway": "None",
                        "dns_servers": [],
                    })
            except Exception:
                pass

        # Fallback primary_ipv4 if still not set
        if not primary_ipv4:
            for ad in adapters:
                if ad.get("ipv4_list"):
                    for ip in ad["ipv4_list"]:
                        if not ip.startswith("127."):
                            primary_ipv4 = ip
                            break

        return {
            "primary_ipv4": primary_ipv4 or "127.0.0.1",
            "adapter_count": len(adapters),
            "adapters": adapters,
        }
