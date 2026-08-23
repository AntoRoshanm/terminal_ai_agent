"""
Rich Terminal Output and Display Formatting
"""

import sys
from typing import Any, Dict, Optional
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from app.models.state import TaskExecutionRecord, TaskStep
from app.models.tools import PermissionLevel

# Ensure UTF-8 console output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

console = Console(force_terminal=True, legacy_windows=False)


def print_banner() -> None:
    """Print the startup application banner."""
    banner_text = Text()
    banner_text.append("Windows AI Agent", style="bold cyan")
    banner_text.append(" — ", style="dim")
    banner_text.append("Autonomous System Operator\n", style="bold green")
    banner_text.append("Type your request, or ", style="dim")
    banner_text.append("/help", style="bold yellow")
    banner_text.append(" for available commands. Press Ctrl+C or type /exit to quit.", style="dim")

    panel = Panel(
        banner_text,
        title="[bold blue]Windows AI Agent[/bold blue]",
        subtitle="[dim]Foundation & Operator v0.1.0[/dim]",
        border_style="cyan",
        padding=(1, 2),
    )
    console.print(panel)


def print_user_message(content: str) -> None:
    """Format and display user input."""
    console.print()
    console.print(f"[bold green]User:[/bold green] {content}")


def print_assistant_message(content: Optional[str]) -> None:
    """Format and display assistant markdown message."""
    console.print()
    console.print("[bold cyan]Agent:[/bold cyan]")
    if content:
        console.print(Markdown(content))
    else:
        console.print("[dim](No textual output)[/dim]")


def print_status(status_text: str) -> None:
    """Print an inline status indicator."""
    console.print(f"[dim]* {status_text}[/dim]")


def print_tool_execution(tool_name: str, arguments: Dict[str, Any], level: PermissionLevel) -> None:
    """Display tool invocation details."""
    level_color = (
        "green"
        if level == PermissionLevel.LEVEL_0_READ_ONLY
        else "yellow"
        if level == PermissionLevel.LEVEL_1_LOW_RISK
        else "bold red"
    )
    console.print(
        f"[dim][Tool Call][/dim] [bold]{tool_name}[/bold] "
        f"[{level_color}](Level {level.value})[/{level_color}]"
    )


def print_task_plan(task: TaskExecutionRecord) -> None:
    """Render a visual table for a generated multi-step plan."""
    table = Table(
        title=f"Execution Plan: {task.goal}",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Step", style="dim", width=6)
    table.add_column("Description", style="bold")
    table.add_column("Tool", style="yellow")
    table.add_column("Verification Criteria", style="dim")

    for s in task.steps:
        table.add_row(
            str(s.step_number),
            s.description,
            s.tool_name or "N/A",
            s.verification_rule or "success",
        )
    console.print()
    console.print(table)


def print_step_progress(step: TaskStep, status_msg: str) -> None:
    """Print progress status for a specific task step."""
    icon = "[OK]" if step.verified else "[..]" if step.state.value in ("EXECUTING", "VERIFYING") else "[X]" if step.state.value == "FAILED" else "[*]"
    color = "green" if step.verified else "yellow" if step.state.value in ("EXECUTING", "VERIFYING") else "red" if step.state.value == "FAILED" else "dim"
    console.print(f"[{color}]{icon} [Step {step.step_number}][/{color}] {status_msg}")


def print_sessions_table(sessions: list) -> None:
    """Render a table of saved sessions."""
    table = Table(title="Saved Sessions", show_header=True, header_style="bold magenta")
    table.add_column("Session ID", style="dim", width=18)
    table.add_column("Title", style="bold")
    table.add_column("Messages", justify="right")
    table.add_column("Last Updated", style="dim")

    for s in sessions:
        table.add_row(
            s.id,
            s.title,
            str(s.message_count),
            s.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
        )
    console.print(table)


def print_error(message: str) -> None:
    """Display an error banner."""
    console.print(f"[bold red]Error:[/bold red] {message}")


def print_help() -> None:
    """Display CLI commands help."""
    table = Table(title="Available Commands", show_header=True, header_style="bold cyan")
    table.add_column("Command", style="bold yellow")
    table.add_row("/new", "Start a new conversation session")
    table.add_row("/sessions", "List all past conversation sessions")
    table.add_row("/switch <id>", "Switch to an existing session by ID")
    table.add_row("/model", "View or change current AI provider/model")
    table.add_row("/memory", "Inspect persistent user preferences & knowledge base")
    table.add_row("/wipe-memory", "Erase all stored user preferences and memory")
    table.add_row("/mcp", "List active Model Context Protocol (MCP) tool servers")
    table.add_row("/benchmark", "Run AI reasoning & tool-calling evaluation benchmark")
    table.add_row("/audit", "View audit trail for the active session")
    table.add_row("/clear", "Clear the terminal screen")
    table.add_row("/help", "Show this help message")
    table.add_row("/exit", "Exit the application")

    console.print(table)

