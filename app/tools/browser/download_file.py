"""
Web File Download Tool with Path Safety
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional
import urllib.parse
import httpx
from app.models.tools import PermissionLevel
from app.tools.base import BaseTool
from app.tools.filesystem.safety import PathSafety


class DownloadFileTool(BaseTool):
    """Tool to download a file from a URL to local storage."""

    name = "browser_download_file"
    description = "Download a file or installer from a URL to the local computer with size verification."
    category = "browser"
    permission_level = PermissionLevel.LEVEL_1_LOW_RISK
    timeout_seconds = 180  # 3 minutes for larger downloads

    def __init__(self, safety: Optional[PathSafety] = None):
        self.safety = safety or PathSafety()

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "Direct HTTP/HTTPS download URL",
                },
                "destination_path": {
                    "type": "string",
                    "description": "Optional destination file path or directory (default: user Downloads folder)",
                },
                "overwrite": {
                    "type": "boolean",
                    "description": "Whether to overwrite existing file if present (default: true)",
                    "default": True,
                },
            },
            "required": ["url"],
            "additionalProperties": False,
        }

    def _get_filename_from_url(self, url: str) -> str:
        """Extract filename from URL path."""
        path = urllib.parse.urlparse(url).path
        name = os.path.basename(path)
        return name if name else "downloaded_file.bin"

    def _run(
        self,
        url: str,
        destination_path: Optional[str] = None,
        overwrite: bool = True,
    ) -> Dict[str, Any]:
        target_url = url.strip()
        if not target_url.startswith(("http://", "https://")):
            target_url = "https://" + target_url

        # Determine target file location
        if destination_path:
            dest = self.safety.check_safe_write(destination_path)
            if dest.is_dir():
                dest = dest / self._get_filename_from_url(target_url)
        else:
            downloads_dir = Path.home() / "Downloads"
            downloads_dir.mkdir(parents=True, exist_ok=True)
            dest = downloads_dir / self._get_filename_from_url(target_url)
            self.safety.check_safe_write(str(dest))

        if dest.exists() and not overwrite:
            raise FileExistsError(f"File '{dest}' already exists and overwrite is set to False.")

        dest.parent.mkdir(parents=True, exist_ok=True)

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            )
        }

        total_bytes = 0
        with httpx.Client(timeout=self.timeout_seconds, follow_redirects=True) as client:
            with client.stream("GET", target_url, headers=headers) as response:
                response.raise_for_status()
                with open(dest, "wb") as f:
                    for chunk in response.iter_bytes(chunk_size=65536):
                        f.write(chunk)
                        total_bytes += len(chunk)

        return {
            "url": target_url,
            "saved_to": str(dest),
            "file_size_bytes": total_bytes,
            "status": "downloaded",
        }
