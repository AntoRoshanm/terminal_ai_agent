"""
Web Search Tool for Information Lookup
"""

import re
from typing import Any, Dict, List, Optional
import urllib.parse
import httpx
from app.models.tools import PermissionLevel
from app.tools.base import BaseTool


class WebSearchTool(BaseTool):
    """Tool to search the web and return structured search results."""

    name = "browser_web_search"
    description = "Search the web for technical documentation, errors, packages, or general information."
    category = "browser"
    permission_level = PermissionLevel.LEVEL_0_READ_ONLY
    timeout_seconds = 20

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query string (e.g. 'python 3.12 release notes', 'windows port in use fix')",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of search results to return (default: 5)",
                    "default": 5,
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        }

    def _run(self, query: str, limit: int = 5) -> Dict[str, Any]:
        q = query.strip()
        encoded_q = urllib.parse.quote_plus(q)

        # Query DuckDuckGo HTML endpoint
        url = f"https://html.duckduckgo.com/html/?q={encoded_q}"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            )
        }

        results: List[Dict[str, str]] = []
        try:
            with httpx.Client(timeout=self.timeout_seconds, follow_redirects=True) as client:
                response = client.post(url, headers=headers)
                response.raise_for_status()
                html = response.text

            # Parse results with regex extraction for speed and zero external dependencies
            # Matches <a class="result__url" href="..."> and <a class="result__snippet" ...>
            result_blocks = re.findall(
                r'<div class="result__body"[^>]*>(.*?)</div>\s*</div>',
                html,
                re.DOTALL,
            )

            for block in result_blocks:
                title_match = re.search(r'<a class="result__snippet[^>]*>(.*?)</a>', block, re.DOTALL) or re.search(
                    r'<a class="result__url[^>]*>(.*?)</a>', block, re.DOTALL
                )
                link_match = re.search(r'href="([^"]+)"', block)
                snippet_match = re.search(r'<a class="result__snippet[^>]*>(.*?)</a>', block, re.DOTALL)

                if link_match:
                    raw_href = link_match.group(1)
                    # Extract actual target url from DuckDuckGo redirect
                    if "uddg=" in raw_href:
                        parsed_qs = urllib.parse.parse_qs(urllib.parse.urlparse(raw_href).query)
                        target_url = parsed_qs.get("uddg", [raw_href])[0]
                    else:
                        target_url = raw_href

                    # Clean tags from snippet
                    snippet_text = ""
                    if snippet_match:
                        snippet_text = re.sub(r"<[^>]+>", "", snippet_match.group(1)).strip()

                    title_text = re.sub(r"<[^>]+>", "", block).strip()[:100]

                    results.append(
                        {
                            "title": title_text.splitlines()[0] if title_text else "Search Result",
                            "url": target_url,
                            "snippet": snippet_text or "No snippet available",
                        }
                    )

                if len(results) >= limit:
                    break

        except Exception as e:
            return {
                "query": query,
                "results_count": 0,
                "results": [],
                "error": f"Search request failed: {str(e)}",
            }

        return {
            "query": query,
            "results_count": len(results),
            "results": results,
        }
