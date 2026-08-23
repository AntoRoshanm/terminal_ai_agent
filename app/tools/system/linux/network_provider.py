"""
Linux Network Information Provider
"""

import os
import subprocess
from typing import Any, Dict, List
from app.platform.contracts import NetworkInfoProvider


class LinuxNetworkInfoProvider(NetworkInfoProvider):
    """Linux implementation for network adapters and routing."""

    def get_network_info(self) -> Dict[str, Any]:
        adapters: List[Dict[str, Any]] = []
        dns_servers: List[str] = []
        gateway = "None"

        # 1. Parse /etc/resolv.conf for DNS
        if os.path.exists("/etc/resolv.conf"):
            try:
                with open("/etc/resolv.conf", "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        if line.startswith("nameserver"):
                            parts = line.split()
                            if len(parts) >= 2:
                                dns_servers.append(parts[1])
            except Exception:
                pass

        # 2. Parse default gateway via ip route
        try:
            res = subprocess.run(["ip", "route"], capture_output=True, text=True, timeout=3)
            if res.returncode == 0 and res.stdout.strip():
                for line in res.stdout.strip().split("\n"):
                    if line.startswith("default via"):
                        parts = line.split()
                        if len(parts) >= 3:
                            gateway = parts[2]
                            break
        except Exception:
            pass

        # 3. Parse ip addr
        try:
            res = subprocess.run(["ip", "-o", "addr"], capture_output=True, text=True, timeout=3)
            if res.returncode == 0 and res.stdout.strip():
                for line in res.stdout.strip().split("\n"):
                    parts = line.split()
                    if len(parts) >= 4:
                        iface = parts[1]
                        family = parts[2]
                        ip_mask = parts[3]
                        if family == "inet":
                            adapters.append({
                                "name": iface,
                                "alias": iface,
                                "description": f"Linux Network Interface ({iface})",
                                "ipv4_address": ip_mask.split("/")[0],
                                "is_up": True,
                                "gateway": gateway if iface != "lo" else "None",
                                "dns_servers": dns_servers if iface != "lo" else [],
                            })
        except Exception:
            pass

        # Determine primary IPv4 (first non-loopback with valid IPv4, or first available)
        primary_ipv4 = "127.0.0.1"
        for a in adapters:
            ip = a.get("ipv4_address", "")
            if ip and not ip.startswith("127.") and not ip.startswith("169.254."):
                primary_ipv4 = ip
                break
        else:
            if adapters:
                primary_ipv4 = adapters[0].get("ipv4_address", "127.0.0.1")

        return {
            "adapter_count": len(adapters),
            "primary_ipv4": primary_ipv4,
            "adapters": adapters,
        }
