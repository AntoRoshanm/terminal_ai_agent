"""
Linux Process Information Provider
"""

import subprocess
from typing import Any, Dict, List, Optional
from app.platform.contracts import ProcessProvider


class LinuxProcessProvider(ProcessProvider):
    """Linux implementation for process inspection."""

    def get_process_info(
        self, query: Optional[str] = None, limit: int = 20, sort_by: str = "memory"
    ) -> List[Dict[str, Any]]:
        processes: List[Dict[str, Any]] = []
        sort_flag = "--sort=-%mem" if sort_by.lower() == "memory" else "--sort=-%cpu"

        try:
            cmd = ["ps", "-eo", "pid,comm,rss,%cpu,args", sort_flag]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=4)
            if res.returncode == 0 and res.stdout.strip():
                lines = res.stdout.strip().split("\n")
                for line in lines[1:]:
                    parts = line.split(None, 4)
                    if len(parts) >= 4:
                        pid = int(parts[0]) if parts[0].isdigit() else 0
                        comm = parts[1]
                        rss_kb = int(parts[2]) if parts[2].isdigit() else 0
                        cpu_pct = float(parts[3]) if parts[3].replace(".", "", 1).isdigit() else 0.0
                        args = parts[4] if len(parts) >= 5 else comm

                        if query and query.lower() not in comm.lower() and query.lower() not in args.lower():
                            continue

                        processes.append({
                            "pid": pid,
                            "name": comm,
                            "memory_mb": round(rss_kb / 1024, 2),
                            "cpu_time_s": cpu_pct,
                            "window_title": args[:120],
                        })

                        if len(processes) >= limit:
                            break
        except Exception:
            pass

        return processes
