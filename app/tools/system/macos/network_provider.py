"""
macOS Network Adapters, IP Addresses, and Routing Provider
"""

import os
from pathlib import Path
import re
import subprocess
from typing import Any, Dict, List
from app.platform.contracts import NetworkInfoProvider


class MacOSNetworkInfoProvider(NetworkInfoProvider):
    """macOS implementation for network adapters, IPv4/v6, and DNS configuration."""

    def get_network_info(self) -> Dict[str, Any]:
        adapters = self._get_adapters()
        dns_servers = self._get_dns_servers()
        default_gateway = self._get_default_gateway()

        return {
            "adapter_count": len(adapters),
            "adapters": adapters,
            "dns_servers": dns_servers,
            "default_gateway": default_gateway,
        }

    def _get_adapters(self) -> List[Dict[str, Any]]:
        adapters: List[Dict[str, Any]] = []
        try:
            res = subprocess.run(["ifconfig"], capture_output=True, text=True, timeout=3)
            if res.returncode == 0 and res.stdout.strip():
                blocks = re.split(r"\n(?=[a-zA-Z0-9]+:)", res.stdout.strip())
                for b in blocks:
                    lines = b.splitlines()
                    if not lines:
                        continue
                    name = lines[0].split(":")[0].strip()
                    ipv4 = None
                    mac = None
                    is_up = "UP" in lines[0]

                    for line in lines[1:]:
                        clean = line.strip()
                        if clean.startswith("inet ") and not clean.startswith("inet 127."):
                            parts = clean.split()
                            if len(parts) >= 2:
                                ipv4 = parts[1]
                        elif clean.startswith("ether "):
                            mac = clean.split()[1]

                    if ipv4 or name.startswith("en") or name == "lo0":
                        adapters.append({
                            "name": name,
                            "description": f"macOS Interface {name}",
                            "ipv4_address": ipv4 or "0.0.0.0",
                            "mac_address": mac or "00:00:00:00:00:00",
                            "status": "Up" if is_up else "Down",
                        })
        except Exception:
            pass

        if not adapters:
            adapters.append({
                "name": "en0",
                "description": "macOS Wi-Fi/Ethernet",
                "ipv4_address": "127.0.0.1",
                "mac_address": "00:00:00:00:00:00",
                "status": "Up",
            })
        return adapters

    def _get_dns_servers(self) -> List[str]:
        servers: List[str] = []
        # Check /etc/resolv.conf
        resolv_path = Path("/etc/resolv.conf")
        if resolv_path.exists():
            try:
                with open(resolv_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        if line.startswith("nameserver"):
                            parts = line.split()
                            if len(parts) >= 2:
                                servers.append(parts[1].strip())
            except Exception:
                pass

        if not servers:
            try:
                res = subprocess.run(["scutil", "--dns"], capture_output=True, text=True, timeout=2)
                if res.returncode == 0:
                    for line in res.stdout.splitlines():
                        if "nameserver[" in line:
                            parts = line.split(":")
                            if len(parts) >= 2:
                                ns = parts[1].strip()
                                if ns and ns not in servers:
                                    servers.append(ns)
            except Exception:
                pass

        return servers or ["8.8.8.8"]

    def _get_default_gateway(self) -> str:
        try:
            res = subprocess.run(["route", "-n", "get", "default"], capture_output=True, text=True, timeout=2)
            if res.returncode == 0:
                for line in res.stdout.splitlines():
                    if "gateway:" in line:
                        return line.split(":")[1].strip()
        except Exception:
            pass
        return "192.168.1.1"
