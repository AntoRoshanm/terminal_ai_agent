"""
Linux Hardware Information Provider
"""

import os
import platform
import subprocess
from typing import Any, Dict, List
from app.platform.contracts import HardwareInfoProvider


class LinuxHardwareInfoProvider(HardwareInfoProvider):
    """Linux implementation for CPU, RAM, and GPU inspection."""

    def _get_ram_info(self) -> Dict[str, Any]:
        tot_kb = 0
        avail_kb = 0
        if os.path.exists("/proc/meminfo"):
            try:
                with open("/proc/meminfo", "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        if line.startswith("MemTotal:"):
                            tot_kb = int(line.split()[1])
                        elif line.startswith("MemAvailable:"):
                            avail_kb = int(line.split()[1])
                if tot_kb > 0:
                    used_kb = tot_kb - avail_kb
                    return {
                        "total_ram_gb": round(tot_kb / (1024 * 1024), 2),
                        "available_ram_gb": round(avail_kb / (1024 * 1024), 2),
                        "used_ram_gb": round(used_kb / (1024 * 1024), 2),
                        "memory_load_percent": round((used_kb / tot_kb) * 100, 1),
                    }
            except Exception:
                pass
        return {"total_ram_gb": "Unknown"}

    def _get_cpu_info(self) -> Dict[str, Any]:
        model_name = platform.processor() or "Linux Processor"
        cores = os.cpu_count() or 1
        mhz = "Unknown"

        if os.path.exists("/proc/cpuinfo"):
            try:
                with open("/proc/cpuinfo", "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        if "model name" in line:
                            model_name = line.split(":", 1)[1].strip()
                        elif "cpu MHz" in line and mhz == "Unknown":
                            mhz = line.split(":", 1)[1].strip()
            except Exception:
                pass

        return {
            "name": model_name,
            "architecture": platform.machine(),
            "cores": cores,
            "logical_processors": cores,
            "max_clock_speed_mhz": mhz,
        }

    def _get_gpu_info(self) -> List[Dict[str, Any]]:
        gpus: List[Dict[str, Any]] = []
        # Try nvidia-smi
        try:
            res = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            if res.returncode == 0 and res.stdout.strip():
                for line in res.stdout.strip().split("\n"):
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 3:
                        gpus.append({
                            "name": parts[0],
                            "driver_version": parts[1],
                            "vram_mb": parts[2],
                            "status": "OK",
                        })
                if gpus:
                    return gpus
        except Exception:
            pass

        # Try lspci fallback
        try:
            res = subprocess.run(["lspci"], capture_output=True, text=True, timeout=3)
            if res.returncode == 0 and res.stdout.strip():
                for line in res.stdout.strip().split("\n"):
                    if "VGA" in line or "3D" in line or "Display" in line:
                        gpus.append({
                            "name": line.split(":", 2)[-1].strip(),
                            "driver_version": "Unknown",
                            "vram_mb": "Dynamic/Shared",
                            "status": "OK",
                        })
        except Exception:
            pass

        return gpus

    def get_hardware_info(self) -> Dict[str, Any]:
        return {
            "ram": self._get_ram_info(),
            "cpu": self._get_cpu_info(),
            "gpus": self._get_gpu_info(),
        }
