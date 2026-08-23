"""
macOS Process Information Provider
"""

import subprocess
from typing import Any, Dict, List, Optional
from app.platform.contracts import ProcessProvider


class MacOSProcessProvider(ProcessProvider):
    """macOS implementation for process inspection matching the cross-platform contract."""

    def get_process_info(
        self, query: Optional[str] = None, limit: int = 20, sort_by: str = "memory"
    ) -> List[Dict[str, Any]]:
        processes: List[Dict[str, Any]] = []

        # Try psutil first if installed
        try:
            import psutil
            for p in psutil.process_iter(['pid', 'name', 'memory_info', 'cpu_percent', 'cmdline']):
                try:
                    pinfo = p.info
                    name = pinfo.get('name') or "Unknown"
                    cmdline = " ".join(pinfo.get('cmdline') or [name])
                    if query and query.lower() not in name.lower() and query.lower() not in cmdline.lower():
                        continue
                    mem_info = pinfo.get('memory_info')
                    rss_bytes = mem_info.rss if mem_info else 0
                    cpu_pct = pinfo.get('cpu_percent') or 0.0
                    processes.append({
                        "pid": pinfo.get('pid', 0),
                        "name": name,
                        "memory_mb": round(rss_bytes / (1024 * 1024), 2),
                        "cpu_time_s": float(cpu_pct),
                        "window_title": cmdline[:120],
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            if sort_by.lower() == "cpu":
                processes.sort(key=lambda x: x.get("cpu_time_s", 0.0), reverse=True)
            else:
                processes.sort(key=lambda x: x.get("memory_mb", 0.0), reverse=True)

            return processes[:limit]
        except ImportError:
            pass

        # Fallback to POSIX ps on Darwin
        try:
            cmd = ["ps", "-eo", "pid,comm,rss,%cpu,args", "-m"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=4)
            if res.returncode == 0 and res.stdout.strip():
                lines = res.stdout.strip().split("\n")
                for line in lines[1:]:
                    parts = line.split(None, 4)
                    if len(parts) >= 4:
                        pid = int(parts[0]) if parts[0].isdigit() else 0
                        comm = parts[1].split("/")[-1]
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
