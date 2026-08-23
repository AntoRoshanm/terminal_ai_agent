"""
Web Page Content Fetching and Text Extraction Tool
"""

from html.parser import HTMLParser
import re
from typing import Any, Dict, List, Optional
import httpx
from app.models.tools import PermissionLevel
from app.tools.base import BaseTool


class HTMLTextExtractor(HTMLParser):
    """Simple, fast HTML parser to extract clean markdown-like text and links."""

    def __init__(self):
        super().__init__()
        self.title = ""
        self.text_chunks: List[str] = []
        self.links: List[Dict[str, str]] = []
        self._in_title = False
        self._in_script_or_style = False
        self._current_href = None
        self._link_text = ""

    def handle_starttag(self, tag: str, attrs: list):
        tag_lower = tag.lower()
        if tag_lower == "title":
            self._in_title = True
        elif tag_lower in ("script", "style", "noscript", "svg"):
            self._in_script_or_style = True
        elif tag_lower == "a":
            attrs_dict = dict(attrs)
            self._current_href = attrs_dict.get("href")
            self._link_text = ""
        elif tag_lower in ("p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "br"):
            self.text_chunks.append("\n")

    def handle_endtag(self, tag: str):
        tag_lower = tag.lower()
        if tag_lower == "title":
            self._in_title = False
        elif tag_lower in ("script", "style", "noscript", "svg"):
            self._in_script_or_style = False
        elif tag_lower == "a":
            if self._current_href and self._link_text:
                self.links.append({"text": self._link_text.strip(), "url": self._current_href})
            self._current_href = None
            self._link_text = ""

    def handle_data(self, data: str):
        if self._in_script_or_style:
            return
        if self._in_title:
            self.title += data
        else:
            text = data.strip()
            if text:
                self.text_chunks.append(data)
            if self._current_href:
                self._link_text += data

    def get_clean_text(self) -> str:
        raw = "".join(self.text_chunks)
        # Collapse multiple blank lines
        clean = re.sub(r"\n\s*\n+", "\n\n", raw).strip()
        return clean


class FetchPageTool(BaseTool):
    """Tool to fetch web page content and extract readable markdown text."""

    name = "browser_fetch_page"
    description = "Fetch a web page by URL, extract its title, readable text, and main links without running JavaScript."
    category = "browser"
    permission_level = PermissionLevel.LEVEL_0_READ_ONLY
    timeout_seconds = 20

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "Full HTTP or HTTPS URL to fetch (e.g. 'https://docs.python.org/3/')",
                },
                "max_length": {
                    "type": "integer",
                    "description": "Maximum characters of text content to return (default: 8000)",
                    "default": 8000,
                },
            },
            "required": ["url"],
            "additionalProperties": False,
        }

    def _run(self, url: str, max_length: int = 8000) -> Dict[str, Any]:
        target_url = url.strip()
        if not target_url.startswith(("http://", "https://")):
            target_url = "https://" + target_url

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            )
        }

        with httpx.Client(timeout=self.timeout_seconds, follow_redirects=True) as client:
            response = client.get(target_url, headers=headers)
            response.raise_for_status()
            html_content = response.text

        extractor = HTMLTextExtractor()
        extractor.feed(html_content)

        clean_text = extractor.get_clean_text()
        truncated = len(clean_text) > max_length

        return {
            "url": str(response.url),
            "status_code": response.status_code,
            "title": extractor.title.strip() or "Untitled",
            "content": clean_text[:max_length],
            "truncated": truncated,
            "total_characters": len(clean_text),
            "links": extractor.links[:20],
        }
