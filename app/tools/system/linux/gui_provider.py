"""
Linux GUI Automation and Window Control Provider (X11 & Wayland)
"""

import os
import shutil
import subprocess
from typing import Any, Dict, List, Optional, Tuple
from app.platform.contracts import GUIProvider
from app.platform.detect import get_platform_info


class LinuxGUIProvider(GUIProvider):
    """Linux implementation with explicit X11 / Wayland degradation awareness."""

    def list_windows(
        self, title_filter: Optional[str] = None, include_hidden: bool = False
    ) -> List[Dict[str, Any]]:
        info = get_platform_info()
        if info.display_server == "wayland":
            return []  # Wayland security isolates window lists

        windows: List[Dict[str, Any]] = []
        if shutil.which("wmctrl"):
            try:
                res = subprocess.run(["wmctrl", "-l", "-p"], capture_output=True, text=True, timeout=4)
                if res.returncode == 0 and res.stdout.strip():
                    for line in res.stdout.strip().split("\n"):
                        parts = line.split(None, 4)
                        if len(parts) >= 5:
                            hwnd_hex = parts[0]
                            pid = int(parts[2]) if parts[2].isdigit() else 0
                            title = parts[4]
                            if title_filter and title_filter.lower() not in title.lower():
                                continue
                            windows.append({
                                "hwnd": int(hwnd_hex, 16) if hwnd_hex.startswith("0x") else 0,
                                "title": title,
                                "pid": pid,
                                "is_visible": True,
                            })
            except Exception:
                pass
        return windows

    def focus_window(self, title: Optional[str] = None, hwnd: Optional[int] = None) -> Dict[str, Any]:
        info = get_platform_info()
        if info.display_server == "wayland":
            return {"success": False, "error": "Window focus is restricted under Wayland compositor security policy."}

        if shutil.which("wmctrl"):
            try:
                if title:
                    res = subprocess.run(["wmctrl", "-a", title], capture_output=True, text=True, timeout=4)
                    return {"success": res.returncode == 0}
                elif hwnd:
                    hex_id = hex(hwnd)
                    res = subprocess.run(["wmctrl", "-i", "-a", hex_id], capture_output=True, text=True, timeout=4)
                    return {"success": res.returncode == 0}
            except Exception as e:
                return {"success": False, "error": str(e)}
        return {"success": False, "error": "wmctrl not available or unsupported display server"}

    def launch_app(self, target: str, args: Optional[List[str]] = None) -> Dict[str, Any]:
        try:
            if shutil.which("xdg-open") and (target.startswith("http") or target.startswith("file:") or os.path.exists(target)):
                cmd = ["xdg-open", target]
            else:
                cmd = [target] + (args or [])
            proc = subprocess.Popen(cmd, start_new_session=True)
            return {"success": True, "target": target, "pid": proc.pid}
        except Exception as e:
            return {"success": False, "target": target, "error": str(e)}

    def get_app_status(self, process_name: Optional[str] = None, pid: Optional[int] = None) -> Dict[str, Any]:
        try:
            if pid:
                res = subprocess.run(["kill", "-0", str(pid)], capture_output=True, text=True)
                running = res.returncode == 0
                total_mem = 0.0
                if running:
                    try:
                        mem_out = subprocess.run(
                            ["ps", "-p", str(pid), "-o", "rss="],
                            capture_output=True, text=True, timeout=3
                        )
                        rss_kb = int(mem_out.stdout.strip() or 0)
                        total_mem = round(rss_kb / 1024.0, 2)
                    except Exception:
                        pass
                return {
                    "running": running, "pid": pid,
                    "process_count": 1 if running else 0,
                    "total_memory_mb": total_mem,
                }
            elif process_name:
                pgrep = subprocess.run(["pgrep", "-f", process_name], capture_output=True, text=True)
                pids = [p.strip() for p in pgrep.stdout.strip().splitlines() if p.strip()]
                running = pgrep.returncode == 0 and len(pids) > 0
                total_mem = 0.0
                if running:
                    try:
                        ps_out = subprocess.run(
                            ["ps", "-p", ",".join(pids), "-o", "rss="],
                            capture_output=True, text=True, timeout=3
                        )
                        rss_total = sum(
                            int(r.strip()) for r in ps_out.stdout.strip().splitlines() if r.strip().isdigit()
                        )
                        total_mem = round(rss_total / 1024.0, 2)
                    except Exception:
                        pass
                return {
                    "running": running,
                    "process_name": process_name,
                    "process_count": len(pids),
                    "total_memory_mb": total_mem,
                    "pids": [int(p) for p in pids],
                }
        except Exception:
            pass
        return {
            "running": False, "target": process_name or pid,
            "process_count": 0, "total_memory_mb": 0.0,
        }

    def close_app(
        self, process_name: Optional[str] = None, pid: Optional[int] = None, force: bool = False
    ) -> Dict[str, Any]:
        sig = "-9" if force else "-15"
        try:
            if pid:
                res = subprocess.run(["kill", sig, str(pid)], capture_output=True, text=True)
                return {"success": res.returncode == 0, "pid": pid}
            elif process_name:
                res = subprocess.run(["pkill", sig, "-f", process_name], capture_output=True, text=True)
                return {"success": res.returncode == 0, "process_name": process_name}
        except Exception as e:
            return {"success": False, "error": str(e)}
        return {"success": False, "error": "Missing target process name or PID"}

    def capture_screenshot(
        self, output_path: Optional[str] = None, region: Optional[Tuple[int, int, int, int]] = None
    ) -> Dict[str, Any]:
        out = output_path or "/tmp/screenshot.png"
        info = get_platform_info()

        # Wayland: try grim
        if info.display_server == "wayland":
            if shutil.which("grim"):
                try:
                    res = subprocess.run(["grim", out], capture_output=True, text=True, timeout=5)
                    if res.returncode == 0 and os.path.exists(out):
                        return {
                            "success": True,
                            "output_path": out,
                            "file_size_bytes": os.path.getsize(out),
                        }
                except Exception:
                    pass
            return {
                "success": False,
                "error": "Capability degraded: Wayland requires xdg-desktop-portal or grim for screenshot capture.",
            }

        # X11: try import or scrot
        if shutil.which("scrot"):
            try:
                res = subprocess.run(["scrot", out], capture_output=True, text=True, timeout=5)
                if res.returncode == 0 and os.path.exists(out):
                    return {
                        "success": True,
                        "output_path": out,
                        "file_size_bytes": os.path.getsize(out),
                    }
            except Exception:
                pass
        elif shutil.which("import"):  # ImageMagick
            try:
                res = subprocess.run(["import", "-window", "root", out], capture_output=True, text=True, timeout=5)
                if res.returncode == 0 and os.path.exists(out):
                    return {
                        "success": True,
                        "output_path": out,
                        "file_size_bytes": os.path.getsize(out),
                    }
            except Exception:
                pass

        return {"success": False, "error": "Capability degraded: No X11 screenshot utility (scrot/import) found in PATH."}

    def send_input(
        self, keys: Optional[str] = None, text: Optional[str] = None, click_coords: Optional[Tuple[int, int]] = None
    ) -> Dict[str, Any]:
        info = get_platform_info()
        if info.display_server == "wayland":
            return {"success": False, "error": "Capability degraded: Synthetic input injection is restricted by Wayland security policy."}

        if shutil.which("xdotool"):
            try:
                if text:
                    subprocess.run(["xdotool", "type", text], capture_output=True, timeout=4)
                elif keys:
                    subprocess.run(["xdotool", "key", keys], capture_output=True, timeout=4)
                if click_coords:
                    x, y = click_coords
                    subprocess.run(["xdotool", "mousemove", str(x), str(y), "click", "1"], capture_output=True, timeout=4)
                return {"success": True, "input_sent": True}
            except Exception as e:
                return {"success": False, "error": str(e)}

        return {"success": False, "error": "Capability degraded: xdotool is required for X11 synthetic input injection."}
