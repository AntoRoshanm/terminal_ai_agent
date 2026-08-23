"""
Screen Geometry, Monitor Metrics, and Foreground Window Analysis Tool
"""

import sys
import ctypes
from typing import Any, Dict
from app.models.tools import PermissionLevel
from app.tools.base import BaseTool

SM_CXSCREEN = 0
SM_CYSCREEN = 1
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79

# Only import Windows-specific ctypes on Windows — importing at module level crashes Linux.
if sys.platform == "win32":
    from ctypes import wintypes

    class RECT(ctypes.Structure):
        _fields_ = [
            ("left", wintypes.LONG),
            ("top", wintypes.LONG),
            ("right", wintypes.LONG),
            ("bottom", wintypes.LONG),
        ]

    class POINT(ctypes.Structure):
        _fields_ = [
            ("x", wintypes.LONG),
            ("y", wintypes.LONG),
        ]


class AnalyzeScreenStateTool(BaseTool):
    """Tool to get screen geometry, cursor position, and foreground window info."""

    name = "gui_analyze_screen"
    description = "Analyze the current screen state: resolution, virtual desktop bounds, and foreground window title."
    category = "gui"
    permission_level = PermissionLevel.LEVEL_0_READ_ONLY

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        }

    def _run(self, **kwargs: Any) -> Dict[str, Any]:
        if sys.platform != "win32":
            return self._linux_screen_state()
        return self._windows_screen_state()

    def _windows_screen_state(self) -> Dict[str, Any]:
        try:
            user32 = ctypes.windll.user32
            from ctypes import wintypes

            primary_w = user32.GetSystemMetrics(SM_CXSCREEN)
            primary_h = user32.GetSystemMetrics(SM_CYSCREEN)
            virtual_w = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
            virtual_h = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)

            cursor_pos = POINT()  # type: ignore[name-defined]
            user32.GetCursorPos(ctypes.byref(cursor_pos))

            hwnd = user32.GetForegroundWindow()
            buf = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, buf, 256)
            foreground_title = buf.value.strip() or ""

            rect = RECT()  # type: ignore[name-defined]
            user32.GetWindowRect(hwnd, ctypes.byref(rect))

            return {
                "primary_screen": {"width": primary_w, "height": primary_h},
                "virtual_desktop": {"width": virtual_w, "height": virtual_h},
                "cursor_position": {"x": cursor_pos.x, "y": cursor_pos.y},
                "foreground_window": {
                    "title": foreground_title,
                    "bounds": {"left": rect.left, "top": rect.top, "right": rect.right, "bottom": rect.bottom},
                },
            }
        except Exception as e:
            return {"error": str(e), "primary_screen": {"width": 0, "height": 0}, "cursor_position": {"x": 0, "y": 0}}

    def _linux_screen_state(self) -> Dict[str, Any]:
        import os
        import subprocess
        import shutil

        result: Dict[str, Any] = {
            "primary_screen": {"width": 0, "height": 0},
            "virtual_desktop": {"width": 0, "height": 0},
            "cursor_position": {"x": 0, "y": 0},
            "foreground_window": {"title": ""},
        }

        display = os.environ.get("DISPLAY", "")
        if not display:
            result["error"] = "DISPLAY not set — no X11 session"
            return result

        # xdpyinfo for screen resolution
        if shutil.which("xdpyinfo"):
            try:
                out = subprocess.run(
                    ["xdpyinfo"], capture_output=True, text=True, timeout=3
                ).stdout
                for line in out.splitlines():
                    if "dimensions:" in line and "pixels" in line:
                        parts = line.strip().split()
                        if parts:
                            dims = parts[1].split("x")
                            if len(dims) == 2:
                                result["primary_screen"] = {"width": int(dims[0]), "height": int(dims[1])}
                                result["virtual_desktop"] = result["primary_screen"].copy()
                        break
            except Exception:
                pass

        # xdotool for cursor
        if shutil.which("xdotool"):
            try:
                pos_out = subprocess.run(
                    ["xdotool", "getmouselocation"], capture_output=True, text=True, timeout=3
                ).stdout
                for part in pos_out.strip().split():
                    if part.startswith("x:"):
                        result["cursor_position"]["x"] = int(part[2:])
                    elif part.startswith("y:"):
                        result["cursor_position"]["y"] = int(part[2:])
            except Exception:
                pass

            try:
                wid = subprocess.run(
                    ["xdotool", "getactivewindow"], capture_output=True, text=True, timeout=3
                ).stdout.strip()
                if wid:
                    name_out = subprocess.run(
                        ["xdotool", "getwindowname", wid], capture_output=True, text=True, timeout=3
                    ).stdout.strip()
                    result["foreground_window"]["title"] = name_out
            except Exception:
                pass

        return result
