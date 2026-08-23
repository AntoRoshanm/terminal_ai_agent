"""
Windows AI Agent - Main Application Entrypoint
"""

import argparse
import sys
from pathlib import Path
from app import __version__
from app.agent.orchestrator import AgentOrchestrator
from app.config import AgentConfig
from app.interface.cli import CLIInterface
from app.interface.display import (
    console,
    print_assistant_message,
    print_error,
    print_sessions_table,
    print_status,
)
from app.logging import AuditLogger, setup_logger
from app.mcp.manager import MCPManager
from app.memory import MemoryStore, register_memory_tools
from app.models.state import TaskState
from app.providers.factory import create_provider
from app.storage.audit_store import AuditStore
from app.storage.database import Database
from app.storage.session_store import SessionStore
from app.tools.applications import register_application_tools
from app.tools.browser import register_browser_tools
from app.tools.developer import register_developer_tools
from app.tools.diagnostics import register_diagnostics_tools
from app.tools.filesystem import register_filesystem_tools
from app.tools.gui import register_gui_tools
from app.tools.registry import ToolRegistry
from app.tools.software import register_software_tools
from app.tools.terminal import register_terminal_tools
from app.tools.windows import register_windows_tools


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Windows AI Agent - Autonomous System Operator and Assistant"
    )
    parser.add_argument(
        "-p", "--prompt",
        type=str,
        help="Execute a single natural language prompt and exit",
    )
    parser.add_argument(
        "-s", "--session",
        type=str,
        help="Resume an existing session by ID",
    )
    parser.add_argument(
        "-c", "--config",
        type=Path,
        help="Path to custom config.yaml file",
    )
    parser.add_argument(
        "--list-sessions",
        action="store_true",
        help="List all saved sessions and exit",
    )
    parser.add_argument(
        "-v", "--version",
        action="version",
        version=f"Windows AI Agent v{__version__}",
    )
    return parser.parse_args()


def main() -> None:
    """Initialize system and launch agent."""
    args = parse_args()

    # Load configuration
    try:
        config = AgentConfig.load(args.config)
    except Exception as e:
        print(f"Failed to load configuration: {e}", file=sys.stderr)
        sys.exit(1)

    # Initialize logging & persistence
    setup_logger("windows_ai_agent", logs_dir=config.storage.logs_dir)
    db = Database(config.storage.db_path)
    session_store = SessionStore(db)
    audit_store = AuditStore(db)
    memory_store = MemoryStore(db)

    # Handle --list-sessions
    if args.list_sessions:
        sessions = session_store.list_sessions()
        print_sessions_table(sessions)
        return

    # Initialize provider & tool registry
    try:
        provider = create_provider(config.provider)
    except Exception as e:
        print_error(f"Failed to initialize AI provider: {e}")
        sys.exit(1)

    tool_registry = ToolRegistry()
    register_windows_tools(tool_registry)
    register_terminal_tools(tool_registry)
    register_filesystem_tools(tool_registry)
    register_software_tools(tool_registry)
    register_application_tools(tool_registry)
    register_browser_tools(tool_registry)
    register_gui_tools(tool_registry)
    register_diagnostics_tools(tool_registry)
    register_developer_tools(tool_registry)
    register_memory_tools(tool_registry, memory_store)

    # Initialize MCP Manager
    mcp_manager = MCPManager(Path("configs/mcp_servers.json"))
    mcp_manager.start_all(tool_registry)

    # Initialize orchestrator
    orchestrator = AgentOrchestrator(
        config=config,
        provider=provider,
        session_store=session_store,
        audit_store=audit_store,
        tool_registry=tool_registry,
    )

    # Initialize CLI interface
    cli = CLIInterface(
        config=config,
        orchestrator=orchestrator,
        session_store=session_store,
        audit_store=audit_store,
        memory_store=memory_store,
        mcp_manager=mcp_manager,
    )

    # Handle one-off prompt via unified execute_prompt
    if args.prompt:
        cli.execute_prompt(args.prompt, session_id=args.session)
        return

    # Run interactive CLI
    cli.run(initial_session_id=args.session)


if __name__ == "__main__":
    main()
