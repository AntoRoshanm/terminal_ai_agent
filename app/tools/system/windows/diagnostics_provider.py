"""
Windows Diagnostics, Health, and Log Provider
"""

import json
import os
from pathlib import Path
import subprocess
import time
from typing import Any, Dict, List, Optional
from app.platform.contracts import DiagnosticsProvider


class WindowsDiagnosticsProvider(DiagnosticsProvider):
    """Windows implementation for health metrics, Event Log, and updates."""

    def get_system_health(self) -> Dict[str, Any]:
        health_data = {
            "status": "Healthy",
            "score": 100,
            "issues": [],
            "metrics": {},
            "ram": {},
            "cpu_load_percent": 0.0,
            "top_memory_consumers": [],
            "unresponsive_processes": [],
        }

        ps_script = """
        # CPU
        $cpu = (Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average

        # RAM
        $os = Get-CimInstance Win32_OperatingSystem
        $totalRamMb = [math]::Round($os.TotalVisibleMemorySize / 1KB, 2)
        $freeRamMb = [math]::Round($os.FreePhysicalMemory / 1KB, 2)
        $usedRamMb = [math]::Round($totalRamMb - $freeRamMb, 2)
        $ramPercent = if ($totalRamMb -gt 0) { [math]::Round(($usedRamMb / $totalRamMb) * 100, 1) } else { 0 }

        # Top 5 Memory Processes
        $topMem = Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 5 -Property Id, ProcessName, @{Name='MemoryMB';Expression={[math]::Round($_.WorkingSet64 / 1MB, 1)}}

        # Hung processes
        $hung = Get-Process | Where-Object { $_.Responding -eq $false } | Select-Object -Property Id, ProcessName

        @{
            cpu_load_percent = $cpu
            ram = @{
                total_mb = $totalRamMb
                used_mb = $usedRamMb
                free_mb = $freeRamMb
                used_percent = $ramPercent
                load_percent = $ramPercent
            }
            top_memory_consumers = $topMem
            unresponsive_processes = $hung
        } | ConvertTo-Json -Compress -Depth 3
        """

        try:
            cmd = ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps_script]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if res.returncode == 0 and res.stdout.strip():
                parsed = json.loads(res.stdout.strip())
                health_data["metrics"] = parsed
                health_data["ram"] = parsed.get("ram", {})
                health_data["cpu_load_percent"] = parsed.get("cpu_load_percent", 0.0)
                health_data["top_memory_consumers"] = parsed.get("top_memory_consumers", [])
                health_data["unresponsive_processes"] = parsed.get("unresponsive_processes", [])
        except Exception:
            pass

        return health_data

    def query_event_log(
        self, channel: str = "System", limit: int = 20, level: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        level_map = {"critical": 1, "error": 2, "warning": 3}
        lvl_num = level_map.get(str(level).lower(), 2) if level else 2

        ps_script = f"""
        $filter = @{{
            LogName = '{channel}'
            Level = {lvl_num}
        }}
        try {{
            $events = Get-WinEvent -FilterHashtable $filter -MaxEvents {limit} -ErrorAction Stop
            $events | Select-Object -Property TimeCreated, Id, ProviderName, Message | ConvertTo-Json -Compress
        }} catch {{
            Write-Output "[]"
        }}
        """

        try:
            cmd = ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps_script]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if res.returncode == 0 and res.stdout.strip():
                parsed = json.loads(res.stdout.strip())
                if isinstance(parsed, dict):
                    parsed = [parsed]
                return [
                    {
                        "time": item.get("TimeCreated"),
                        "event_id": item.get("Id"),
                        "level": level or "Error",
                        "message": (item.get("Message") or "").strip()[:500],
                    }
                    for item in parsed
                ]
        except Exception:
            pass
        return []

    def check_updates(self) -> Dict[str, Any]:
        ps_script = """
        try {
            $hotfixes = Get-HotFix -ErrorAction SilentlyContinue | Sort-Object InstalledOn -Descending | Select-Object -First 10 -Property HotFixID, Description, InstalledOn
            $hotfixes | ConvertTo-Json -Compress
        } catch {
            Write-Output "[]"
        }
        """
        try:
            cmd = ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps_script]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if res.returncode == 0 and res.stdout.strip():
                parsed = json.loads(res.stdout.strip())
                if isinstance(parsed, dict):
                    parsed = [parsed]
                return {
                    "pending_updates_count": len(parsed),
                    "updates": [{"Title": f"{item.get('HotFixID')}: {item.get('Description')}"} for item in parsed],
                }
        except Exception:
            pass
        return {"pending_updates_count": 0, "updates": []}

    def clean_temp(self, dry_run: bool = True) -> Dict[str, Any]:
        temp_dir = Path(os.environ.get("TEMP", Path.home() / "AppData" / "Local" / "Temp"))
        if not temp_dir.exists():
            return {"dry_run": dry_run, "items_inspected": 0, "found_mb": 0, "cleaned_mb": 0, "total_files_scanned": 0}

        cutoff_time = time.time() - 86400  # 1 day
        total_scanned = 0
        total_bytes = 0
        deleted_count = 0
        deleted_bytes = 0
        failed_count = 0

        for root, _, files in os.walk(temp_dir):
            for f in files:
                p = Path(root) / f
                try:
                    stat = p.stat()
                    total_scanned += 1
                    total_bytes += stat.st_size
                    if stat.st_mtime < cutoff_time and not dry_run:
                        try:
                            p.unlink()
                            deleted_bytes += stat.st_size
                        except Exception:
                            pass
                except Exception:
                    continue

        return {
            "target_directory": str(temp_dir),
            "dry_run": dry_run,
            "items_inspected": total_scanned,
            "total_files_scanned": total_scanned,
            "total_temp_size_mb": round(total_bytes / (1024 * 1024), 2),
            "found_mb": round(total_bytes / (1024 * 1024), 2),
            "cleaned_mb": round(deleted_bytes / (1024 * 1024), 2) if not dry_run else 0,
            "deleted_files_count": deleted_count if not dry_run else 0,
            "reclaimed_mb": round(deleted_bytes / (1024 * 1024), 2) if not dry_run else round(total_bytes / (1024 * 1024), 2),
            "locked_files_skipped": failed_count,
        }
