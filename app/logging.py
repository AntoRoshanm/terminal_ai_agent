"""
Structured Logging and Audit Trail
"""

from datetime import datetime, timezone
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("windows_ai_agent")


def setup_logger(
    name: str = "windows_ai_agent",
    logs_dir: Optional[Path] = None,
    level: int = logging.INFO,
    console: bool = False,
) -> logging.Logger:
    """Set up structured rotating file logger."""
    log = logging.getLogger(name)
    log.setLevel(level)

    # Avoid duplicate handlers
    if log.handlers:
        return log

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s"
    )

    if logs_dir:
        logs_dir.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            logs_dir / "agent.log",
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        log.addHandler(file_handler)

    if console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        log.addHandler(console_handler)

    return log


class AuditLogger:
    """Audit logger for recording system actions and decisions."""

    def __init__(self, logs_dir: Path):
        self.logs_dir = logs_dir
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.audit_file = self.logs_dir / "audit.jsonl"

    def log_event(
        self,
        event_type: str,
        session_id: str,
        task_id: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Write an immutable audit log entry in JSONL format."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "session_id": session_id,
            "task_id": task_id,
            "data": data or {},
        }
        try:
            with open(self.audit_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")
