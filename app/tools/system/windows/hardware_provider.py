"""
Windows Hardware Information Provider
"""

import os
import platform
import subprocess
import sys
from typing import Any, Dict
from app.platform.contracts import HardwareInfoProvider


class WindowsHardwareInfoProvider(HardwareInfoProvider):
    """Windows implementation for CPU, RAM, and GPU inspection."""

    def _get_ram_info(self) -> Dict[str, Any]:
        if sys.platform == "win32":
            try:
                import ctypes
                from ctypes import wintypes

                class MEMORYSTATUSEX(ctypes.Structure):
                    _fields_ = [
                        ("dwLength", wintypes.DWORD),
                        ("dwMemoryLoad", wintypes.DWORD),
                        ("ullTotalPhys", ctypes.c_uint64),
                        ("ullAvailPhys", ctypes.c_uint64),
                        ("ullTotalPageFile", ctypes.c_uint64),
                        ("ullAvailPageFile", ctypes.c_uint64),
                        ("ullTotalVirtual", ctypes.c_uint64),
                        ("ullAvailVirtual", ctypes.c_uint64),
                        ("sullAvailExtendedVirtual", ctypes.c_uint64),
                    ]

                stat = MEMORYSTATUSEX()
                stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
                if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                    tot = stat.ullTotalPhys
                    avail = stat.ullAvailPhys
                    used = tot - avail
                    return {
                        "total_ram_gb": round(tot / (1024**3), 2),
                        "available_ram_gb": round(avail / (1024**3), 2),
                        "used_ram_gb": round(used / (1024**3), 2),
                        "memory_load_percent": stat.dwMemoryLoad,
                    }
            except Exception:
                pass

        # Fallback via PowerShell
        try:
            cmd = ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", "(Get-CimInstance Win32_OperatingSystem).TotalVisibleMemorySize"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=4)
            if res.returncode == 0 and res.stdout.strip().isdigit():
                tot_kb = int(res.stdout.strip())
                return {"total_ram_gb": round(tot_kb / (1024**2), 2)}
        except Exception:
            pass

        return {"total_ram_gb": "Unknown"}

    def _get_cpu_info(self) -> Dict[str, Any]:
        cpu_info = {
            "name": platform.processor() or "AMD/Intel x86_64 Processor",
            "architecture": platform.machine(),
            "cores": os.cpu_count() or 1,
            "logical_processors": os.cpu_count() or 1,
            "max_clock_speed_mhz": "Unknown",
        }
        try:
            cmd = ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", "Get-CimInstance Win32_Processor | Select-Object Name, NumberOfCores, NumberOfLogicalProcessors, MaxClockSpeed | ConvertTo-Json -Compress"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=4)
            if res.returncode == 0 and res.stdout.strip():
                import json
                data = json.loads(res.stdout.strip())
                if isinstance(data, list):
                    data = data[0]
                cpu_info["name"] = data.get("Name", cpu_info["name"])
                cpu_info["cores"] = data.get("NumberOfCores", cpu_info["cores"])
                cpu_info["logical_processors"] = data.get("NumberOfLogicalProcessors", cpu_info["logical_processors"])
                cpu_info["max_clock_speed_mhz"] = data.get("MaxClockSpeed", "Unknown")
        except Exception:
            pass
        return cpu_info

    def _get_gpu_info(self) -> list[Dict[str, Any]]:
        gpus = []
        try:
            cmd = ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", "Get-CimInstance Win32_VideoController | Select-Object Name, AdapterRAM, DriverVersion, Status | ConvertTo-Json -Compress"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=4)
            if res.returncode == 0 and res.stdout.strip():
                import json
                data = json.loads(res.stdout.strip())
                if isinstance(data, dict):
                    data = [data]
                for item in data:
                    ram_bytes = item.get("AdapterRAM") or 0
                    gpus.append({
                        "name": item.get("Name", "Unknown GPU"),
                        "driver_version": item.get("DriverVersion", "Unknown"),
                        "vram_mb": round(ram_bytes / (1024**2), 2) if isinstance(ram_bytes, (int, float)) and ram_bytes > 0 else "Dynamic/Shared",
                        "status": item.get("Status", "OK"),
                    })
        except Exception:
            pass
        return gpus

    def get_hardware_info(self) -> Dict[str, Any]:
        ram = self._get_ram_info()
        cpu = self._get_cpu_info()
        gpus = self._get_gpu_info()
        return {
            "ram": ram,
            "cpu": cpu,
            "gpus": gpus,
            # Top-level aliases for backward compatibility
            "total_ram_gb": ram.get("total_ram_gb", "Unknown"),
            "logical_cpus": cpu.get("logical_processors", os.cpu_count() or 1),
            "cpu_count": cpu.get("cores", os.cpu_count() or 1),
            "architecture": cpu.get("architecture", platform.machine()),
        }
