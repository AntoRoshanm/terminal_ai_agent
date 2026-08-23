"""
Linux Storage Information Provider
"""

import os
import shutil
import subprocess
from typing import Any, Dict, List
from app.platform.contracts import StorageInfoProvider


class LinuxStorageInfoProvider(StorageInfoProvider):
    """Linux implementation for disk mounts and storage capacity."""

    def get_storage_info(self) -> List[Dict[str, Any]]:
        mounts: List[Dict[str, Any]] = []

        # Parse df -Pk
        try:
            res = subprocess.run(["df", "-Pk"], capture_output=True, text=True, timeout=4)
            if res.returncode == 0 and res.stdout.strip():
                lines = res.stdout.strip().split("\n")
                for line in lines[1:]:
                    parts = line.split()
                    if len(parts) >= 6:
                        dev = parts[0]
                        total_kb = int(parts[1])
                        used_kb = int(parts[2])
                        free_kb = int(parts[3])
                        pct = parts[4].rstrip("%")
                        mount_pt = parts[5]

                        # Skip virtual mounts
                        if dev.startswith("/dev/") or mount_pt == "/":
                            mounts.append({
                                "device_id": dev,
                                "volume_name": mount_pt,
                                "filesystem": "ext4/xfs",
                                "drive_type": "Mount Point",
                                "total_space_gb": round(total_kb / (1024 * 1024), 2),
                                "used_space_gb": round(used_kb / (1024 * 1024), 2),
                                "free_space_gb": round(free_kb / (1024 * 1024), 2),
                                "free_percent": round(100.0 - float(pct), 1) if pct.isdigit() else 0.0,
                            })
        except Exception:
            pass

        if not mounts and os.path.exists("/"):
            try:
                tot, used, free = shutil.disk_usage("/")
                mounts.append({
                    "device_id": "/dev/root",
                    "volume_name": "/",
                    "filesystem": "ext4",
                    "drive_type": "Root Filesystem",
                    "total_space_gb": round(tot / (1024**3), 2),
                    "used_space_gb": round(used / (1024**3), 2),
                    "free_space_gb": round(free / (1024**3), 2),
                    "free_percent": round((free / tot) * 100, 1) if tot > 0 else 0.0,
                })
            except Exception:
                pass

        return mounts
