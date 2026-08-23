"""
macOS Diagnostics, Health Metrics, Unified Logging, and Maintenance Provider
"""

import os
from pathlib import Path
import shutil
import subprocess
import time
from typing import Any, Dict, List, Optional
from app.platform.contracts import DiagnosticsProvider


class MacOSDiagnosticsProvider(DiagnosticsProvider):
    """macOS implementation for health metrics, unified logs, and system updates."""

    def get_system_health(self) -> Dict[str, Any]:
        health_data: Dict[str, Any] = {
            "status": "Healthy",
            "score": 100,
            "issues": [],
            "metrics": {},
            "ram": {
                "total_mb": 0.0,
                "used_mb": 0.0,
                "free_mb": 0.0,
                "used_percent": 0.0,
                "load_percent": 0.0,
            },
            "cpu_load_percent": 0.0,
            "top_memory_consumers": [],
            "unresponsive_processes": [],
        }

        # 1. RAM via sysctl & vm_stat
        try:
            mem_res = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=2)
            if mem_res.returncode == 0 and mem_res.stdout.strip().isdigit():
                tot_bytes = int(mem_res.stdout.strip())
                tot_mb = round(tot_bytes / (1024 * 1024), 2)
                health_data["ram"]["total_mb"] = tot_mb

                vm_res = subprocess.run(["vm_stat"], capture_output=True, text=True, timeout=2)
                if vm_res.returncode == 0:
                    pages_free = 0
                    pages_inactive = 0
                    page_size = 4096
                    for line in vm_res.stdout.splitlines():
                        if "page size of" in line:
                            parts = line.split("page size of")
                            if len(parts) > 1:
                                sz = parts[1].split("bytes")[0].strip()
                                if sz.isdigit():
                                    page_size = int(sz)
                        elif "Pages free:" in line:
                            pages_free = int(line.split(":")[1].strip().rstrip("."))
                        elif "Pages inactive:" in line:
                            pages_inactive = int(line.split(":")[1].strip().rstrip("."))
                    free_bytes = (pages_free + pages_inactive) * page_size
                    free_mb = round(free_bytes / (1024 * 1024), 2)
                    used_mb = round(max(0.0, tot_mb - free_mb), 2)
                    load_pct = round((used_mb / tot_mb) * 100, 1) if tot_mb > 0 else 0.0

                    health_data["ram"]["free_mb"] = free_mb
                    health_data["ram"]["used_mb"] = used_mb
                    health_data["ram"]["used_percent"] = load_pct
                    health_data["ram"]["load_percent"] = load_pct

                    if load_pct > 90:
                        health_data["issues"].append(f"High memory pressure ({load_pct}%)")
                        health_data["score"] -= 20
                        health_data["status"] = "Warning"
        except Exception:
            pass

        # 2. CPU load average via sysctl
        try:
            load_res = subprocess.run(["sysctl", "-n", "vm.loadavg"], capture_output=True, text=True, timeout=2)
            if load_res.returncode == 0 and "{" in load_res.stdout:
                # Format: { 1.50 1.20 1.10 }
                parts = load_res.stdout.replace("{", "").replace("}", "").strip().split()
                if parts:
                    health_data["cpu_load_percent"] = float(parts[0]) * 10.0
        except Exception:
            pass

        # 3. Top memory consumers via ps
        try:
            cmd = ["ps", "-eo", "comm,rss,%mem", "-m"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
            if res.returncode == 0 and res.stdout.strip():
                top = []
                for line in res.stdout.strip().split("\n")[1:6]:
                    parts = line.split()
                    if len(parts) >= 2:
                        rss_kb = int(parts[1]) if parts[1].isdigit() else 0
                        top.append({"ProcessName": parts[0].split("/")[-1], "MB": round(rss_kb / 1024, 1)})
                health_data["top_memory_consumers"] = top
                health_data["metrics"]["top_memory_consumers"] = top
        except Exception:
            pass

        return health_data

    def query_event_log(
        self, channel: str = "System", limit: int = 20, level: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        events = []
        try:
            # macOS Unified Logging
            predicate = 'messageType == error' if (level and level.lower() == "error") else 'messageType >= default'
            cmd = ["log", "show", "--predicate", predicate, "--last", "1h", "--style", "ndjson"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=6)
            if res.returncode == 0 and res.stdout.strip():
                import json
                for line in res.stdout.strip().splitlines()[:limit]:
                    try:
                        record = json.loads(line)
                        events.append({
                            "time": record.get("timestamp"),
                            "event_id": 0,
                            "level": level or "info",
                            "message": record.get("eventMessage", "")[:400],
                        })
                    except Exception:
                        pass
                if events:
                    return events
        except Exception:
            pass

        # Fallback to /var/log/system.log
        if os.path.exists("/var/log/system.log"):
            try:
                with open("/var/log/system.log", "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                    for line in lines[-limit:]:
                        events.append({
                            "time": line[:15],
                            "event_id": 0,
                            "level": "system.log",
                            "message": line[16:].strip()[:400],
                        })
            except Exception:
                pass

        return events

    def check_updates(self) -> Dict[str, Any]:
        updates = []
        try:
            res = subprocess.run(["softwareupdate", "-l"], capture_output=True, text=True, timeout=10)
            if res.returncode == 0 and res.stdout.strip():
                for line in res.stdout.splitlines():
                    clean = line.strip()
                    if clean.startswith("* ") or clean.startswith("Title:"):
                        updates.append({"Title": clean.lstrip("* Title:").strip()})
        except Exception:
            pass

        if shutil.which("brew"):
            try:
                brew_res = subprocess.run(["brew", "outdated"], capture_output=True, text=True, timeout=6)
                if brew_res.returncode == 0 and brew_res.stdout.strip():
                    for line in brew_res.stdout.splitlines():
                        if line.strip():
                            updates.append({"Title": f"Homebrew: {line.strip()}"})
            except Exception:
                pass

        return {"pending_updates_count": len(updates), "updates": updates}

    def clean_temp(self, dry_run: bool = True) -> Dict[str, Any]:
        temp_paths = [
            Path("/tmp"),
            Path("/var/tmp"),
            Path.home() / "Library" / "Caches",
        ]
        found_bytes = 0
        deleted_bytes = 0
        total_scanned = 0
        deleted_count = 0
        failed_count = 0
        cutoff_time = time.time() - 86400

        for tp in temp_paths:
            if tp.exists():
                for root, _, files in os.walk(tp):
                    for f in files:
                        p = Path(root) / f
                        try:
                            st = p.stat()
                            total_scanned += 1
                            found_bytes += st.st_size
                            if st.st_mtime < cutoff_time and not dry_run:
                                try:
                                    p.unlink()
                                    deleted_bytes += st.st_size
                                    deleted_count += 1
                                except Exception:
                                    failed_count += 1
                        except Exception:
                            continue

        return {
            "target_directory": str(Path.home() / "Library" / "Caches"),
            "dry_run": dry_run,
            "items_inspected": total_scanned,
            "total_files_scanned": total_scanned,
            "total_temp_size_mb": round(found_bytes / (1024 * 1024), 2),
            "found_mb": round(found_bytes / (1024 * 1024), 2),
            "cleaned_mb": round(deleted_bytes / (1024 * 1024), 2) if not dry_run else 0,
            "deleted_files_count": deleted_count if not dry_run else 0,
            "reclaimed_mb": round(deleted_bytes / (1024 * 1024), 2) if not dry_run else round(found_bytes / (1024 * 1024), 2),
            "locked_files_skipped": failed_count,
        }
