"""
Browser and Web Tools Subsystem
"""

from app.tools.browser.download_file import DownloadFileTool
from app.tools.browser.fetch_page import FetchPageTool
from app.tools.browser.navigate import OpenBrowserTool
from app.tools.browser.web_search import WebSearchTool
from app.tools.filesystem.safety import PathSafety
from app.tools.registry import ToolRegistry

__all__ = [
    "FetchPageTool",
    "WebSearchTool",
    "OpenBrowserTool",
    "DownloadFileTool",
    "register_browser_tools",
]


def register_browser_tools(registry: ToolRegistry) -> None:
    """Register browser and web tools into the registry."""
    safety = PathSafety()
    registry.register(FetchPageTool())
    registry.register(WebSearchTool())
    registry.register(OpenBrowserTool())
    registry.register(DownloadFileTool(safety))
