"""
Cross-Platform Mouse and Keyboard Input Automation Tools
"""

from typing import Any, Dict, Optional, Tuple
from app.models.tools import PermissionLevel
from app.tools.base import BaseTool
from app.tools.system.factory import SystemProviderFactory


class MouseClickTool(BaseTool):
    """Tool to move the mouse cursor and perform click actions."""

    name = "gui_mouse_click"
    description = "Move mouse cursor to (x, y) coordinates and perform a left, right, or double click."
    category = "gui"
    permission_level = PermissionLevel.LEVEL_1_LOW_RISK

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "x": {
                    "type": "integer",
                    "description": "X coordinate in screen pixels",
                },
                "y": {
                    "type": "integer",
                    "description": "Y coordinate in screen pixels",
                },
                "button": {
                    "type": "string",
                    "description": "Mouse button: 'left', 'right', or 'middle' (default: 'left')",
                    "enum": ["left", "right", "middle"],
                    "default": "left",
                },
                "click_type": {
                    "type": "string",
                    "description": "Click type: 'single' or 'double' (default: 'single')",
                    "enum": ["single", "double"],
                    "default": "single",
                },
            },
            "required": ["x", "y"],
            "additionalProperties": False,
        }

    def _run(
        self,
        x: int,
        y: int,
        button: str = "left",
        click_type: str = "single",
    ) -> Dict[str, Any]:
        return SystemProviderFactory.get_gui_provider().send_input(
            click_coords=(x, y)
        )


class MouseScrollTool(BaseTool):
    """Tool to scroll the vertical mouse wheel."""

    name = "gui_mouse_scroll"
    description = "Scroll the mouse wheel at current cursor position."
    category = "gui"
    permission_level = PermissionLevel.LEVEL_1_LOW_RISK

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "delta": {
                    "type": "integer",
                    "description": "Scroll wheel delta (positive = up, negative = down)",
                    "default": -120,
                },
                "x": {
                    "type": "integer",
                    "description": "Optional X coordinate to move cursor before scrolling",
                },
                "y": {
                    "type": "integer",
                    "description": "Optional Y coordinate to move cursor before scrolling",
                },
            },
            "additionalProperties": False,
        }

    def _run(
        self,
        delta: int = -120,
        x: Optional[int] = None,
        y: Optional[int] = None,
    ) -> Dict[str, Any]:
        coords = (x, y) if x is not None and y is not None else None
        return SystemProviderFactory.get_gui_provider().send_input(
            click_coords=coords
        )


class KeyboardTypeTool(BaseTool):
    """Tool to type text or send keystrokes to the active window."""

    name = "gui_keyboard_type"
    description = "Type text characters or send special keystrokes to the active foreground window."
    category = "gui"
    permission_level = PermissionLevel.LEVEL_1_LOW_RISK

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Text characters to type into the active window",
                },
                "special_key": {
                    "type": "string",
                    "description": "Special key combination (e.g. '{ENTER}', '{TAB}', '{ESC}', '^s' for Ctrl+S)",
                },
            },
            "additionalProperties": False,
        }

    def _run(
        self,
        text: Optional[str] = None,
        special_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not text and not special_key:
            raise ValueError("Must provide either 'text' to type or 'special_key' to send.")

        return SystemProviderFactory.get_gui_provider().send_input(
            text=text, keys=special_key
        )


class GUISendInputTool(BaseTool):
    """Unified tool for synthetic keyboard and mouse input (Directive A.3/A.4/gui_send_input)."""

    name = "gui_send_input"
    description = "Send synthetic mouse clicks, key combinations, or typed text to the active desktop window."
    category = "gui"
    permission_level = PermissionLevel.LEVEL_1_LOW_RISK

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Text to type",
                },
                "keys": {
                    "type": "string",
                    "description": "Key combo to press (e.g. 'Return', 'ctrl+s')",
                },
                "x": {
                    "type": "integer",
                    "description": "Optional X coordinate for mouse click",
                },
                "y": {
                    "type": "integer",
                    "description": "Optional Y coordinate for mouse click",
                },
            },
            "additionalProperties": False,
        }

    def _run(
        self,
        text: Optional[str] = None,
        keys: Optional[str] = None,
        x: Optional[int] = None,
        y: Optional[int] = None,
    ) -> Dict[str, Any]:
        coords = (x, y) if x is not None and y is not None else None
        return SystemProviderFactory.get_gui_provider().send_input(
            text=text, keys=keys, click_coords=coords
        )
