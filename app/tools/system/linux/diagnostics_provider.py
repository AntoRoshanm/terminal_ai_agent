"""
Linux Diagnostics, Health, and Log Provider
"""

import os
import shutil
import subprocess
from typing import Any, Dict, List, Optional
from app.platform.contracts import DiagnosticsProvider


class LinuxDiagnosticsProvider(DiagnosticsProvider):
    """Linux implementation for health metrics, journalctl, and updates."""

    def get_system_health(self) -> Dict[str, Any]:
        health_data: Dict[str, Any] = {
            "status": "Healthy",
            "score": 100,
            "issues": [],
            "metrics": {},
        }

        # 1. RAM usage via /proc/meminfo
        if os.path.exists("/proc/meminfo"):
            try:
                tot_kb = 0
                avail_kb = 0
                with open("/proc/meminfo", "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        if line.startswith("MemTotal:"):
                            tot_kb = int(line.split()[1])
                        elif line.startswith("MemAvailable:"):
                            avail_kb = int(line.split()[1])
                if tot_kb > 0:
                    used_kb = tot_kb - avail_kb
                    load_pct = round((used_kb / tot_kb) * 100, 1)
                    health_data["metrics"]["ram"] = {
                        "total_mb": round(tot_kb / 1024, 2),
                        "used_mb": round(used_kb / 1024, 2),
                        "free_mb": round(avail_kb / 1024, 2),
                        "load_percent": load_pct,
                    }
                    if load_pct > 90:
                        health_data["issues"].append(f"High memory load ({load_pct}%)")
                        health_data["score"] -= 20
                        health_data["status"] = "Warning"
            except Exception:
                pass

        # 2. Disk usage
        try:
            tot, used, free = shutil.disk_usage("/")
            free_pct = (free / tot) * 100 if tot > 0 else 100
            health_data["metrics"]["disk_root"] = {
                "total_gb": round(tot / (1024**3), 2),
                "free_gb": round(free / (1024**3), 2),
                "free_percent": round(free_pct, 1),
            }
            if free_pct < 10:
                health_data["issues"].append(f"Low disk space on root ({round(free_pct, 1)}% free)")
                health_data["score"] -= 25
                health_data["status"] = "Critical" if free_pct < 5 else "Warning"
        except Exception:
            pass

        # 3. Top memory consumers
        try:
            cmd = ["ps", "-eo", "comm,%mem,rss", "--sort=-%mem"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=4)
            if res.returncode == 0 and res.stdout.strip():
                top = []
                for line in res.stdout.strip().split("\n")[1:6]:
                    parts = line.split()
                    if len(parts) >= 3:
                        top.append({"ProcessName": parts[0], "MB": round(int(parts[2]) / 1024, 1)})
                health_data["metrics"]["top_memory_consumers"] = top
                health_data["top_memory_consumers"] = top
        except Exception:
            pass

        # Populate top-level fields for cross-platform schema parity
        health_data["ram"] = health_data["metrics"].get("ram", {
            "total_mb": 0.0,
            "used_mb": 0.0,
            "free_mb": 0.0,
            "used_percent": 0.0,
            "load_percent": 0.0,
        })
        if "used_percent" not in health_data["ram"]:
            health_data["ram"]["used_percent"] = health_data["ram"].get("load_percent", 0.0)
        health_data["top_memory_consumers"] = health_data.get("top_memory_consumers", [])
        health_data["unresponsive_processes"] = health_data.get("unresponsive_processes", [])
        health_data["cpu_load_percent"] = health_data.get("cpu_load_percent", 0.0)

        return health_data

    def query_event_log(
        self, channel: str = "System", limit: int = 20, level: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        events = []
        priority = "3" if level == "error" else ("4" if level == "warning" else None)
        cmd = ["journalctl", "-n", str(limit), "--no-pager", "-o", "short-iso"]
        if priority:
            cmd.extend(["-p", priority])

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=6)
            if res.returncode == 0 and res.stdout.strip():
                for line in res.stdout.strip().split("\n"):
                    parts = line.split(None, 2)
                    if len(parts) >= 3:
                        events.append({
                            "time": parts[0],
                            "event_id": 0,
                            "level": level or "info",
                            "message": parts[2][:300],
                        })
                if events:
                    return events
        except Exception:
            pass

        # Fallback /var/log/syslog
        if os.path.exists("/var/log/syslog"):
            try:
                with open("/var/log/syslog", "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                    for line in lines[-limit:]:
                        events.append({
                            "time": line[:15],
                            "event_id": 0,
                            "level": "syslog",
                            "message": line[16:].strip()[:300],
                        })
            except Exception:
                pass

        return events

    def check_updates(self) -> Dict[str, Any]:
        updates = []
        if shutil.which("apt"):
            try:
                cmd = ["apt", "list", "--upgradable"]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if res.returncode == 0 and res.stdout.strip():
                    lines = res.stdout.strip().split("\n")
                    for line in lines[1:]:
                        if "/" in line:
                            updates.append({"Title": line.strip()})
            except Exception:
                pass
        elif shutil.which("dnf"):
            try:
                res = subprocess.run(["dnf", "check-update", "-q"], capture_output=True, text=True, timeout=10)
                for line in res.stdout.strip().split("\n"):
                    if line.strip():
                        updates.append({"Title": line.strip()})
            except Exception:
                pass

        return {"pending_updates_count": len(updates), "updates": updates}

    def clean_temp(self, dry_run: bool = True) -> Dict[str, Any]:
        temp_paths = ["/tmp", "/var/tmp", os.path.expanduser("~/.cache")]
        found_bytes = 0
        deleted_bytes = 0
        items_count = 0
        deleted_count = 0
        failed_count = 0

        for tp in temp_paths:
            if os.path.exists(tp):
                for root, _, files in os.walk(tp):
                    for f in files:
                        p = os.path.join(root, f)
                        try:
                            sz = os.path.getsize(p)
                            found_bytes += sz
                            items_count += 1
                            if not dry_run:
                                try:
                                    os.remove(p)
                                    deleted_bytes += sz
                                    deleted_count += 1
                                except Exception:
                                    failed_count += 1
                        except Exception:
                            pass

        return {
            "target_directory": "/tmp",
            "dry_run": dry_run,
            "items_inspected": items_count,
            "total_files_scanned": items_count,
            "total_temp_size_mb": round(found_bytes / (1024 * 1024), 2),
            "found_mb": round(found_bytes / (1024 * 1024), 2),
            "cleaned_mb": round(deleted_bytes / (1024 * 1024), 2) if not dry_run else 0,
            "deleted_files_count": deleted_count if not dry_run else 0,
            "reclaimed_mb": round(deleted_bytes / (1024 * 1024), 2) if not dry_run else round(found_bytes / (1024 * 1024), 2),
            "locked_files_skipped": failed_count,
        }
