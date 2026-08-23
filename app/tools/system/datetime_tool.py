"""
Local System Date & Time Inspection Tool (Directive v6.1 Addendum)
"""

from datetime import datetime, timezone as dt_timezone
import os
import time
from typing import Any, Dict, Optional
try:
    import zoneinfo
except ImportError:
    from backports import zoneinfo  # type: ignore

from app.models.tools import PermissionLevel
from app.tools.base import BaseTool


class GetCurrentDateTimeTool(BaseTool):
    """Tool to query local system clock and timezone-aware date/time without network requests."""

    name = "get_current_datetime"
    description = "Get the current local system date, time, day of the week, timezone, and ISO timestamp. Also supports optional timezone conversion (e.g. 'UTC', 'America/New_York', 'Asia/Tokyo')."
    category = "system"
    permission_level = PermissionLevel.LEVEL_0_READ_ONLY

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "timezone": {
                    "type": "string",
                    "description": "Optional IANA timezone name (e.g., 'UTC', 'America/New_York', 'Asia/Tokyo', 'Europe/London'). If omitted, uses local system timezone.",
                }
            },
            "additionalProperties": False,
        }

    def _run(self, timezone: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        now_local = datetime.now().astimezone()
        target_tz = now_local.tzinfo
        tz_name = str(now_local.tzname() or "Local")

        if timezone and timezone.strip():
            tz_str = timezone.strip()
            if tz_str.upper() in ("UTC", "GMT", "Z"):
                target_tz = dt_timezone.utc
                tz_name = "UTC"
            else:
                try:
                    target_tz = zoneinfo.ZoneInfo(tz_str)
                    tz_name = tz_str
                except Exception:
                    # Fallback to local time if unresolvable timezone
                    target_tz = now_local.tzinfo
                    tz_name = str(now_local.tzname() or "Local")

        now = datetime.now(target_tz)

        return {
            "datetime_iso": now.isoformat(),
            "date": now.strftime("%Y-%m-%d"),
            "time_12h": now.strftime("%I:%M:%S %p"),
            "time_24h": now.strftime("%H:%M:%S"),
            "day_of_week": now.strftime("%A"),
            "formatted": now.strftime("%A, %B %d, %Y at %I:%M:%S %p %Z"),
            "timezone": tz_name,
            "utc_offset": now.strftime("%z"),
            "timestamp_epoch": int(now.timestamp()),
        }
