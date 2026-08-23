"""
macOS Hardware Specifications and Resource Provider
"""

import subprocess
from typing import Any, Dict
from app.platform.contracts import HardwareInfoProvider
from app.platform.detect import get_platform_info


class MacOSHardwareInfoProvider(HardwareInfoProvider):
    """macOS implementation for CPU, RAM, and GPU hardware metrics."""

    def get_hardware_info(self) -> Dict[str, Any]:
        info = get_platform_info()
        cpu_data = self._get_cpu_info(info)
        ram_data = self._get_ram_info()
        gpu_data = self._get_gpu_info()

        return {
            "cpu": cpu_data,
            "ram": ram_data,
            "gpus": gpu_data,
        }

    def _get_cpu_info(self, platform_info) -> Dict[str, Any]:
        cpu_name = "Apple Silicon" if platform_info.is_apple_silicon else "Intel Mac"
        cores_logical = 0
        cores_physical = 0

        try:
            brand_res = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True, timeout=2)
            if brand_res.returncode == 0 and brand_res.stdout.strip():
                cpu_name = brand_res.stdout.strip()
        except Exception:
            pass

        try:
            ncpu_res = subprocess.run(["sysctl", "-n", "hw.ncpu"], capture_output=True, text=True, timeout=2)
            if ncpu_res.returncode == 0 and ncpu_res.stdout.strip().isdigit():
                cores_logical = int(ncpu_res.stdout.strip())
        except Exception:
            pass

        try:
            phys_res = subprocess.run(["sysctl", "-n", "hw.physicalcpu"], capture_output=True, text=True, timeout=2)
            if phys_res.returncode == 0 and phys_res.stdout.strip().isdigit():
                cores_physical = int(phys_res.stdout.strip())
        except Exception:
            pass

        return {
            "name": cpu_name,
            "cores_physical": cores_physical or cores_logical,
            "cores_logical": cores_logical or cores_physical,
            "architecture": platform_info.architecture,
            "is_apple_silicon": platform_info.is_apple_silicon,
        }

    def _get_ram_info(self) -> Dict[str, Any]:
        total_ram_gb = 0.0
        available_ram_gb = 0.0

        try:
            mem_res = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=2)
            if mem_res.returncode == 0 and mem_res.stdout.strip().isdigit():
                total_bytes = int(mem_res.stdout.strip())
                total_ram_gb = round(total_bytes / (1024**3), 2)
        except Exception:
            pass

        # Estimate free RAM using vm_stat
        try:
            vm_res = subprocess.run(["vm_stat"], capture_output=True, text=True, timeout=2)
            if vm_res.returncode == 0:
                pages_free = 0
                pages_inactive = 0
                page_size = 4096  # default 4KB, could be 16KB on Apple Silicon

                for line in vm_res.stdout.splitlines():
                    if "page size of" in line:
                        parts = line.split("page size of")
                        if len(parts) > 1:
                            size_str = parts[1].split("bytes")[0].strip()
                            if size_str.isdigit():
                                page_size = int(size_str)
                    elif "Pages free:" in line:
                        pages_free = int(line.split(":")[1].strip().rstrip("."))
                    elif "Pages inactive:" in line:
                        pages_inactive = int(line.split(":")[1].strip().rstrip("."))

                free_bytes = (pages_free + pages_inactive) * page_size
                available_ram_gb = round(free_bytes / (1024**3), 2)
        except Exception:
            available_ram_gb = total_ram_gb * 0.5  # fallback estimate

        return {
            "total_ram_gb": total_ram_gb,
            "available_ram_gb": available_ram_gb,
            "used_ram_gb": round(max(0.0, total_ram_gb - available_ram_gb), 2),
        }

    def _get_gpu_info(self) -> list[Dict[str, Any]]:
        gpus = []
        try:
            res = subprocess.run(["system_profiler", "SPDisplaysDataType"], capture_output=True, text=True, timeout=4)
            if res.returncode == 0:
                chip_name = None
                for line in res.stdout.splitlines():
                    clean = line.strip()
                    if clean.startswith("Chipset Model:") or clean.startswith("Chipset:"):
                        chip_name = clean.split(":", 1)[1].strip()
                        gpus.append({"name": chip_name, "driver_version": "Apple Metal"})
        except Exception:
            pass

        if not gpus:
            gpus.append({"name": "Integrated Apple / Intel Graphics", "driver_version": "Metal"})
        return gpus
