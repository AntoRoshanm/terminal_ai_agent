"""
Windows Storage Information Provider
"""

import os
import shutil
import subprocess
from typing import Any, Dict, List
from app.platform.contracts import StorageInfoProvider


class WindowsStorageInfoProvider(StorageInfoProvider):
    """Windows implementation for drive and volume inspection."""

    def get_storage_info(self) -> List[Dict[str, Any]]:
        drives = []
        try:
            cmd = ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", "Get-CimInstance Win32_LogicalDisk | Select-Object DeviceID, VolumeName, FileSystem, DriveType, Size, FreeSpace | ConvertTo-Json -Compress"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if res.returncode == 0 and res.stdout.strip():
                import json
                data = json.loads(res.stdout.strip())
                if isinstance(data, dict):
                    data = [data]

                drive_type_map = {
                    2: "Removable Disk",
                    3: "Fixed Disk",
                    4: "Network Drive",
                    5: "CD/DVD-ROM",
                }

                for item in data:
                    size_b = item.get("Size") or 0
                    free_b = item.get("FreeSpace") or 0
                    used_b = size_b - free_b if size_b >= free_b else 0
                    tot_gb = round(size_b / (1024**3), 2) if size_b else 0
                    used_gb = round(used_b / (1024**3), 2) if size_b else 0
                    free_gb = round(free_b / (1024**3), 2) if free_b else 0

                    drives.append({
                        "device_id": item.get("DeviceID", "Unknown"),
                        "volume_name": item.get("VolumeName") or "OS",
                        "filesystem": item.get("FileSystem", "NTFS"),
                        "drive_type": drive_type_map.get(item.get("DriveType"), "Unknown"),
                        "total_space_gb": tot_gb,
                        "used_space_gb": used_gb,
                        "free_space_gb": free_gb,
                        "total_gb": tot_gb,
                        "used_gb": used_gb,
                        "free_gb": free_gb,
                        "free_percent": round((free_b / size_b) * 100, 1) if size_b > 0 else 0,
                    })
        except Exception:
            pass

        if not drives and os.path.exists("C:\\"):
            total, used, free = shutil.disk_usage("C:\\")
            tot_gb = round(total / (1024**3), 2)
            used_gb = round(used / (1024**3), 2)
            free_gb = round(free / (1024**3), 2)
            drives.append({
                "device_id": "C:",
                "volume_name": "OS",
                "filesystem": "NTFS",
                "drive_type": "Fixed Disk",
                "total_space_gb": tot_gb,
                "used_space_gb": used_gb,
                "free_space_gb": free_gb,
                "total_gb": tot_gb,
                "used_gb": used_gb,
                "free_gb": free_gb,
                "free_percent": round((free / total) * 100, 1) if total > 0 else 0,
            })

        return drives
