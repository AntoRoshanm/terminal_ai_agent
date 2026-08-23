"""
macOS GUI Automation, AppleScript Window Management, and TCC Privacy Protection Provider
"""

import os
from pathlib import Path
import shutil
import subprocess
from typing import Any, Dict, List, Optional, Tuple
from app.platform.contracts import GUIProvider


class MacOSGUIProvider(GUIProvider):
    """macOS implementation with AppleScript System Events and explicit TCC privacy degradation."""

    def list_windows(
        self, title_filter: Optional[str] = None, include_hidden: bool = False
    ) -> List[Dict[str, Any]]:
        windows: List[Dict[str, Any]] = []
        script = """
        tell application "System Events"
            set procList to every application process where background only is false
            set outList to {}
            repeat with p in procList
                set pName to name of p
                set pId to unix id of p
                copy (pName & "|" & (pId as string)) to end of outList
            end repeat
            return outList
        end tell
        """
        try:
            res = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=4)
            if res.returncode == 0 and res.stdout.strip():
                # Format: "Safari|1234, Finder|5678"
                items = res.stdout.strip().split(", ")
                for it in items:
                    if "|" in it:
                        name, pid_str = it.split("|", 1)
                        name = name.strip()
                        pid = int(pid_str.strip()) if pid_str.strip().isdigit() else 0
                        if title_filter and title_filter.lower() not in name.lower():
                            continue
                        windows.append({
                            "hwnd": pid,
                            "title": name,
                            "pid": pid,
                            "is_visible": True,
                        })
        except Exception:
            pass

        return windows

    def focus_window(self, title: Optional[str] = None, hwnd: Optional[int] = None) -> Dict[str, Any]:
        target = title
        if not target and hwnd:
            target = str(hwnd)

        if not target:
            return {"success": False, "error": "Missing target application title or PID to focus."}

        script = f'tell application "{target}" to activate'
        try:
            res = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=4)
            if res.returncode == 0:
                return {"success": True, "target": target}
            if "-1743" in res.stderr:
                return {
                    "success": False,
                    "error": "Capability degraded: TCC permission not granted for Accessibility/Automation; ask user to enable it in System Settings → Privacy & Security → Accessibility.",
                }
            return {"success": False, "error": res.stderr.strip() or "Window focus failed"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def launch_app(self, target: str, args: Optional[List[str]] = None) -> Dict[str, Any]:
        try:
            if target.startswith("http://") or target.startswith("https://") or target.startswith("file://") or os.path.exists(target):
                cmd = ["open", target]
            else:
                cmd = ["open", "-a", target]
                if args:
                    cmd.extend(["--args"] + args)
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                # Find PID
                pid = None
                try:
                    p_res = subprocess.run(["pgrep", "-f", target], capture_output=True, text=True, timeout=2)
                    if p_res.returncode == 0 and p_res.stdout.strip():
                        pid = int(p_res.stdout.splitlines()[0])
                except Exception:
                    pass
                return {"success": True, "target": target, "pid": pid}
            return {"success": False, "target": target, "error": res.stderr.strip()}
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
                        mem_out = subprocess.run(["ps", "-p", str(pid), "-o", "rss="], capture_output=True, text=True, timeout=2)
                        rss_kb = int(mem_out.stdout.strip() or 0)
                        total_mem = round(rss_kb / 1024.0, 2)
                    except Exception:
                        pass
                return {
                    "running": running,
                    "pid": pid,
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
                        ps_out = subprocess.run(["ps", "-p", ",".join(pids), "-o", "rss="], capture_output=True, text=True, timeout=2)
                        rss_total = sum(int(r.strip()) for r in ps_out.stdout.strip().splitlines() if r.strip().isdigit())
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
        return {"running": False, "target": process_name or pid, "process_count": 0, "total_memory_mb": 0.0}

    def close_app(
        self, process_name: Optional[str] = None, pid: Optional[int] = None, force: bool = False
    ) -> Dict[str, Any]:
        sig = "-9" if force else "-15"
        try:
            if pid:
                res = subprocess.run(["kill", sig, str(pid)], capture_output=True, text=True)
                return {"success": res.returncode == 0, "pid": pid}
            elif process_name:
                # Try AppleScript graceful quit first if not force
                if not force:
                    script = f'tell application "{process_name}" to quit'
                    res_apple = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=3)
                    if res_apple.returncode == 0:
                        return {"success": True, "process_name": process_name}
                res = subprocess.run(["pkill", sig, "-f", process_name], capture_output=True, text=True)
                return {"success": res.returncode == 0, "process_name": process_name}
        except Exception as e:
            return {"success": False, "error": str(e)}
        return {"success": False, "error": "Missing target process name or PID"}

    def capture_screenshot(
        self, output_path: Optional[str] = None, region: Optional[Tuple[int, int, int, int]] = None
    ) -> Dict[str, Any]:
        out = output_path or "/tmp/screenshot.png"
        try:
            cmd = ["screencapture", "-x", out]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if res.returncode == 0 and os.path.exists(out):
                return {
                    "success": True,
                    "output_path": out,
                    "file_size_bytes": os.path.getsize(out),
                }
            if "-1743" in res.stderr or "not permitted" in res.stderr.lower():
                return {
                    "success": False,
                    "error": "Capability degraded: TCC permission not granted for Screen Recording; ask user to enable it in System Settings → Privacy & Security → Screen Recording.",
                }
        except Exception:
            pass

        return {
            "success": False,
            "error": "Capability degraded: macOS screencapture requires Screen Recording TCC permission. In headless CI runners, TCC permission cannot be granted non-interactively.",
        }

    def send_input(
        self, keys: Optional[str] = None, text: Optional[str] = None, click_coords: Optional[Tuple[int, int]] = None
    ) -> Dict[str, Any]:
        # Synthetic input on macOS requires Accessibility TCC permission
        if text:
            script = f'tell application "System Events" to keystroke "{text}"'
        elif keys:
            script = f'tell application "System Events" to key code {keys}'
        elif click_coords:
            x, y = click_coords
            if shutil.which("cliclick"):
                try:
                    res = subprocess.run(["cliclick", f"c:{x},{y}"], capture_output=True, text=True, timeout=3)
                    return {"success": res.returncode == 0, "input_sent": True}
                except Exception:
                    pass
            script = f'tell application "System Events" to click at {{{x}, {y}}}'
        else:
            return {"success": False, "error": "No input keys, text, or coordinates provided"}

        try:
            res = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=4)
            if res.returncode == 0:
                return {"success": True, "input_sent": True}
            if "-1743" in res.stderr or "not allowed" in res.stderr.lower():
                return {
                    "success": False,
                    "error": "Capability degraded: TCC permission not granted for Accessibility/System Events; ask user to enable it in System Settings → Privacy & Security → Accessibility.",
                }
            return {"success": False, "error": res.stderr.strip() or "Input simulation failed"}
        except Exception as e:
            return {
                "success": False,
                "error": f"Capability degraded: Synthetic input simulation failed ({e}). Requires Accessibility TCC permission.",
            }
