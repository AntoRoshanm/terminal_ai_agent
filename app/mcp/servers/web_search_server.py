"""
DuckDuckGo Web Search & Web Content Fetcher MCP Server (Stdio JSON-RPC 2.0)
"""

import json
import sys
from typing import Any, Dict, List, Optional
import httpx

# Ensure UTF-8 I/O on Windows when available
if sys.platform == "win32":
    if hasattr(sys.stdin, "reconfigure"):
        try:
            sys.stdin.reconfigure(encoding="utf-8")
        except Exception:
            pass
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    if hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass


def log_debug(msg: str) -> None:
    try:
        sys.stderr.write(f"[MCP WebSearch] {msg}\n")
        sys.stderr.flush()
    except Exception:
        pass


def search_duckduckgo(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """Perform a web search using ddgs / duckduckgo_search with fallback."""
    results = []
    
    # 1. Try ddgs
    try:
        from ddgs import DDGS
        with DDGS() as ddgs:
            raw_results = list(ddgs.text(query, max_results=max_results))
            for r in raw_results:
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("href") or r.get("link", ""),
                    "snippet": r.get("body") or r.get("snippet", ""),
                })
        if results:
            return results
    except Exception as e:
        log_debug(f"ddgs package search error: {e}")

    # 2. Try duckduckgo_search fallback
    try:
        from duckduckgo_search import DDGS as OldDDGS
        with OldDDGS() as ddgs:
            raw_results = list(ddgs.text(query, max_results=max_results))
            for r in raw_results:
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("href") or r.get("link", ""),
                    "snippet": r.get("body") or r.get("snippet", ""),
                })
        if results:
            return results
    except Exception as e:
        log_debug(f"duckduckgo_search fallback error: {e}")

    # 3. Direct HTML / Lite search fallback via httpx
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        with httpx.Client(timeout=10.0, follow_redirects=True, headers=headers) as client:
            resp = client.get(f"https://html.duckduckgo.com/html/?q={httpx.URL(query).raw_path.decode('utf-8', errors='ignore')}")
            if resp.status_code == 200:
                # Basic text extraction from HTML
                text = resp.text
                import re
                snippets = re.findall(r'<a class="result__snippet[^>]*>(.*?)</a>', text, re.DOTALL)
                titles = re.findall(r'<a class="result__url[^>]*>(.*?)</a>', text, re.DOTALL)
                for i in range(min(len(snippets), max_results)):
                    clean_s = re.sub(r"<[^>]+>", "", snippets[i]).strip()
                    clean_t = re.sub(r"<[^>]+>", "", titles[i]).strip() if i < len(titles) else "Search Result"
                    if clean_s:
                        results.append({"title": clean_t, "url": f"https://duckduckgo.com/?q={query}", "snippet": clean_s})
    except Exception as e:
        log_debug(f"HTTP fallback error: {e}")

    return results


def fetch_url_content(url: str, max_chars: int = 4000) -> str:
    """Fetch webpage and extract clean text."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        with httpx.Client(timeout=15.0, follow_redirects=True, headers=headers) as client:
            resp = client.get(url)
            resp.raise_for_status()
            import re
            body = re.sub(r"<script.*?</script>", "", resp.text, flags=re.DOTALL | re.IGNORECASE)
            body = re.sub(r"<style.*?</style>", "", body, flags=re.DOTALL | re.IGNORECASE)
            clean_text = re.sub(r"<[^>]+>", " ", body)
            clean_text = re.sub(r"\s+", " ", clean_text).strip()
            return clean_text[:max_chars]
    except Exception as e:
        return f"Error fetching {url}: {e}"


TOOLS_DEFINITION = [
    {
        "name": "web_search",
        "description": "Search the live web using DuckDuckGo to obtain up-to-date information, news, current events, product prices, and documentation.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search keywords or query (e.g. 'iPhone 17 price today', 'latest Python release')",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of search results to return (default: 5)",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "fetch_web_content",
        "description": "Fetch and extract readable text content from a web URL.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL of the webpage to fetch",
                },
            },
            "required": ["url"],
        },
    },
]


def handle_request(req: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Process incoming JSON-RPC 2.0 request."""
    method = req.get("method")
    req_id = req.get("id")
    params = req.get("params", {})

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {"listChanged": False},
                },
                "serverInfo": {
                    "name": "duckduckgo-web-search",
                    "version": "1.0.0",
                },
            },
        }

    elif method in ("notifications/initialized", "initialized"):
        return None

    elif method == "ping":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}

    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": TOOLS_DEFINITION,
            },
        }

    elif method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if tool_name == "web_search":
            query = arguments.get("query", "")
            max_results = int(arguments.get("max_results", 5))
            results = search_duckduckgo(query, max_results=max_results)

            if results:
                formatted = []
                for idx, r in enumerate(results, 1):
                    formatted.append(f"{idx}. {r['title']}\n   URL: {r['url']}\n   Summary: {r['snippet']}")
                output_text = "\n\n".join(formatted)
            else:
                output_text = f"No web search results found for query: '{query}'."

            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": output_text,
                        }
                    ],
                    "isError": False,
                },
            }

        elif tool_name == "fetch_web_content":
            url = arguments.get("url", "")
            content = fetch_url_content(url)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": content,
                        }
                    ],
                    "isError": False,
                },
            }

        else:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": f"Unknown tool '{tool_name}'",
                },
            }

    else:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": -32601,
                "message": f"Method '{method}' not found",
            },
        }


def main():
    log_debug("DuckDuckGo Web Search MCP Server started over stdio.")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            resp = handle_request(req)
            if resp is not None:
                sys.stdout.write(json.dumps(resp) + "\n")
                sys.stdout.flush()
        except Exception as e:
            log_debug(f"Error handling request: {e}")
            err_resp = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Parse error: {e}"},
            }
            sys.stdout.write(json.dumps(err_resp) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
