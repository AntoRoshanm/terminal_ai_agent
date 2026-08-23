"""
Integration and Unit tests for Phase 8 Browser and Web Control Tools.
"""

from app.models.tools import PermissionLevel
from app.tools.browser import (
    DownloadFileTool,
    FetchPageTool,
    OpenBrowserTool,
    WebSearchTool,
    register_browser_tools,
)
from app.tools.browser.fetch_page import HTMLTextExtractor
from app.tools.registry import ToolRegistry


def test_html_text_extractor():
    sample_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Python Documentation</title>
        <style>body { color: red; }</style>
        <script>alert('hidden');</script>
    </head>
    <body>
        <h1>Welcome to Python 3</h1>
        <p>Python is an easy to learn, powerful programming language.</p>
        <a href="https://docs.python.org/tutorial/">Tutorial Link</a>
    </body>
    </html>
    """

    extractor = HTMLTextExtractor()
    extractor.feed(sample_html)

    assert extractor.title == "Python Documentation"
    clean_text = extractor.get_clean_text()
    assert "Welcome to Python 3" in clean_text
    assert "hidden" not in clean_text
    assert len(extractor.links) == 1
    assert extractor.links[0]["url"] == "https://docs.python.org/tutorial/"


def test_browser_tools_schemas():
    fetch_tool = FetchPageTool()
    assert fetch_tool.permission_level == PermissionLevel.LEVEL_0_READ_ONLY
    f_schema = fetch_tool.get_parameters_schema()
    assert "url" in f_schema["properties"]

    search_tool = WebSearchTool()
    assert search_tool.permission_level == PermissionLevel.LEVEL_0_READ_ONLY
    s_schema = search_tool.get_parameters_schema()
    assert "query" in s_schema["properties"]

    open_tool = OpenBrowserTool()
    assert open_tool.permission_level == PermissionLevel.LEVEL_1_LOW_RISK
    o_schema = open_tool.get_parameters_schema()
    assert "url" in o_schema["properties"]

    dl_tool = DownloadFileTool()
    assert dl_tool.permission_level == PermissionLevel.LEVEL_1_LOW_RISK
    d_schema = dl_tool.get_parameters_schema()
    assert "url" in d_schema["properties"]


def test_download_file_filename_parsing():
    dl_tool = DownloadFileTool()
    assert dl_tool._get_filename_from_url("https://example.com/files/setup.exe") == "setup.exe"
    assert dl_tool._get_filename_from_url("https://example.com/archive.zip?v=1") == "archive.zip"


def test_register_browser_tools():
    registry = ToolRegistry()
    register_browser_tools(registry)
    tools = registry.list_tools()
    assert len(tools) == 4
    names = {t.name for t in tools}
    assert names == {
        "browser_fetch_page",
        "browser_web_search",
        "browser_open",
        "browser_download_file",
    }
