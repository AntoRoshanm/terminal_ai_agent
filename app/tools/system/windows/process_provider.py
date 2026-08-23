"""
Windows Process Information Provider
"""

import subprocess
from typing import Any, Dict, List, Optional
from app.platform.contracts import ProcessProvider


class WindowsProcessProvider(ProcessProvider):
    """Windows implementation for process management and queries."""

    def get_process_info(
        self, query: Optional[str] = None, limit: int = 20, sort_by: str = "memory"
    ) -> List[Dict[str, Any]]:
        processes = []
        sort_property = "CPU" if sort_by.lower() == "cpu" else "WorkingSet64"

        cmd = [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            f"Get-Process | Sort-Object -Descending -Property {sort_property} | Select-Object -First {limit * 2} -Property Id, ProcessName, WorkingSet64, CPU, MainWindowTitle | ConvertTo-Json -Compress",
        ]

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if res.returncode == 0 and res.stdout.strip():
                import json
                data = json.loads(res.stdout.strip())
                if isinstance(data, dict):
                    data = [data]

                for p in data:
                    name = str(p.get("ProcessName", "Unknown"))
                    if query and query.lower() not in name.lower():
                        continue

                    mem_bytes = p.get("WorkingSet64") or 0
                    cpu_seconds = p.get("CPU") or 0.0

                    processes.append({
                        "pid": p.get("Id", 0),
                        "name": name,
                        "memory_mb": round(mem_bytes / (1024 * 1024), 2),
                        "cpu_time_s": round(float(cpu_seconds), 2),
                        "window_title": p.get("MainWindowTitle") or "",
                    })

                    if len(processes) >= limit:
                        break
        except Exception:
            pass

        return processes
