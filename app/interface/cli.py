"""
Interactive Terminal Interface using Prompt Toolkit and Rich
"""

import os
import sys
from typing import Any, Optional
from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.styles import Style
from app.agent.orchestrator import AgentOrchestrator
from app.benchmarks.runner import BenchmarkRunner
from app.config import AgentConfig
from app.interface.display import (
    console,
    print_assistant_message,
    print_banner,
    print_error,
    print_help,
    print_sessions_table,
    print_status,
)
from app.mcp.manager import MCPManager
from app.memory.store import MemoryStore
from app.models.messages import ToolCall
from app.models.state import Session, TaskState
from app.models.tools import PermissionLevel
from app.storage.audit_store import AuditStore
from app.storage.session_store import SessionStore
from rich.table import Table


class CLIInterface:
    """Terminal Conversational CLI Interface."""

    def __init__(
        self,
        config: AgentConfig,
        orchestrator: AgentOrchestrator,
        session_store: SessionStore,
        audit_store: AuditStore,
        memory_store: Optional[MemoryStore] = None,
        mcp_manager: Optional[MCPManager] = None,
    ):
        self.config = config
        self.orchestrator = orchestrator
        self.session_store = session_store
        self.audit_store = audit_store
        self.memory_store = memory_store
        self.mcp_manager = mcp_manager
        self.active_session: Optional[Session] = None
        try:
            self.prompt_session = PromptSession(history=InMemoryHistory())
        except Exception:
            self.prompt_session = None

        # Bind approval callback to prompt user on terminal
        self.orchestrator.approval_callback = self._prompt_approval

    def _prompt_approval(
        self, tool_name: str, tool_call: ToolCall, level: Optional[PermissionLevel] = None
    ) -> bool:
        """Prompt user on terminal to approve or reject a tool execution."""
        if level in (PermissionLevel.LEVEL_0_READ_ONLY, PermissionLevel.LEVEL_1_LOW_RISK):
            return True

        console.print()
        lvl_val = level.value if level else 2
        console.print(
            f"[bold yellow]Approval Required[/bold yellow] "
            f"([bold red]Permission Level {lvl_val}[/bold red])"
        )
        console.print(f"[bold]Tool:[/bold] {tool_name}")
        console.print(f"[bold]Arguments:[/bold] {tool_call.arguments}")

        try:
            resp = input("Do you authorize this action? [y/N]: ").strip().lower()
            return resp in ("y", "yes")
        except (KeyboardInterrupt, EOFError):
            return False

    def _handle_command(self, cmd_text: str) -> bool:
        """Handle slash commands. Returns True if handled, False to continue."""
        parts = cmd_text.strip().split()
        cmd = parts[0].lower()
        args = parts[1:]

        if cmd in ("/exit", "/quit", "/q"):
            console.print("[dim]Goodbye![/dim]")
            return False

        elif cmd == "/help":
            print_help()

        elif cmd == "/clear":
            os.system("cls" if os.name == "nt" else "clear")
            print_banner()

        elif cmd == "/new":
            self.active_session = self.session_store.create_session(title="New Conversation")
            console.print(f"[green]Started new session:[/green] {self.active_session.id}")

        elif cmd == "/sessions":
            sessions = self.session_store.list_sessions()
            print_sessions_table(sessions)

        elif cmd == "/switch":
            if not args:
                print_error("Please provide a session ID: /switch <session_id>")
            else:
                target = self.session_store.get_session(args[0])
                if target:
                    self.active_session = target
                    console.print(f"[green]Switched to session:[/green] {target.id} ({target.title})")
                    msgs = self.session_store.get_messages(target.id)
                    console.print(f"[dim]Loaded {len(msgs)} previous message(s)[/dim]")
                else:
                    print_error(f"Session '{args[0]}' not found.")

        elif cmd == "/audit":
            if self.active_session:
                events = self.audit_store.get_events_for_session(self.active_session.id)
                console.print(f"[bold cyan]Audit trail for session {self.active_session.id}:[/bold cyan]")
                for ev in events:
                    console.print(f"[dim]{ev['timestamp']}[/dim] [bold]{ev['event_type']}[/bold]: {ev['payload']}")
            else:
                print_error("No active session.")

        elif cmd == "/model":
            console.print(
                f"[bold cyan]Current Provider:[/bold cyan] {self.config.provider.provider} "
                f"([bold green]{self.config.provider.model}[/bold green])"
            )

        elif cmd == "/memory":
            if not self.memory_store:
                print_error("Memory store not configured.")
                return True
            prefs = self.memory_store.list_preferences()
            knowledge = self.memory_store.search_knowledge("")
            table = Table(title="Stored User Preferences", show_header=True, header_style="bold magenta")
            table.add_column("Key", style="bold yellow")
            table.add_column("Value")
            table.add_column("Category", style="dim")
            for p in prefs:
                table.add_row(p.key, str(p.value), p.category)
            console.print(table)

            k_table = Table(title=f"Knowledge Items ({len(knowledge)})", show_header=True, header_style="bold cyan")
            k_table.add_column("ID", style="dim")
            k_table.add_column("Title", style="bold")
            k_table.add_column("Tags")
            for k in knowledge:
                k_table.add_row(k.id, k.title, ", ".join(k.tags))
            console.print(k_table)

        elif cmd == "/wipe-memory":
            if self.memory_store:
                self.memory_store.clear_all()
                console.print("[green]Memory wiped successfully.[/green]")

        elif cmd == "/mcp":
            if not self.mcp_manager or not self.mcp_manager.wrapped_tools:
                console.print("[dim]No external MCP tools registered. Add configs in configs/mcp_servers.json[/dim]")
            else:
                table = Table(title="Active MCP Tools", show_header=True, header_style="bold cyan")
                table.add_column("Server", style="bold magenta")
                table.add_column("Tool Name", style="bold yellow")
                table.add_column("Description")
                for t in self.mcp_manager.wrapped_tools:
                    table.add_row(t.server_name, t.name, t.description)
                console.print(table)

        elif cmd == "/benchmark":
            console.print("[dim]Running evaluation benchmark on active LLM provider...[/dim]")
            runner = BenchmarkRunner(self.orchestrator.provider)
            res = runner.run_benchmarks()
            table = Table(title=f"Benchmark Results: {res.provider_name} ({res.model_name})", show_header=True, header_style="bold green")
            table.add_column("Metric", style="bold cyan")
            table.add_column("Value", justify="right")
            table.add_row("Total Scenarios", str(res.total_tests))
            table.add_row("Passed Scenarios", f"{res.passed_tests} / {res.total_tests}")
            table.add_row("Tool Calling Accuracy", f"{res.tool_calling_accuracy}%")
            table.add_row("Intent Detection Accuracy", f"{res.intent_detection_accuracy}%")
            table.add_row("Average Latency", f"{res.avg_latency_ms} ms")
            console.print(table)

        else:
            print_error(f"Unknown command '{cmd}'. Type /help for a list of commands.")

        return True

    def execute_prompt(self, user_text: str, session_id: Optional[str] = None) -> Any:
        """Shared execution engine for both interactive REPL and headless -p mode."""
        if session_id:
            self.active_session = self.session_store.get_session(session_id)
        if not self.active_session:
            self.active_session = self.session_store.create_session(title=f"Session: {user_text[:30]}")

        def status_cb(text: str, state: TaskState):
            print_status(f"[{state.value}] {text}")

        response = self.orchestrator.process_message(
            session_id=self.active_session.id,
            user_text=user_text,
            status_callback=status_cb,
        )

        print_assistant_message(response.content)
        return response

    def run(self, initial_session_id: Optional[str] = None) -> None:
        """Run the main interactive REPL loop."""
        print_banner()

        # Initialize or resume session
        if initial_session_id:
            self.active_session = self.session_store.get_session(initial_session_id)

        if not self.active_session:
            self.active_session = self.session_store.create_session(title="Interactive Session")

        console.print(
            f"[dim]Active Session: [bold]{self.active_session.id}[/bold] | "
            f"Provider: [bold]{self.config.provider.provider} ({self.config.provider.model})[/bold][/dim]\n"
        )

        while True:
            try:
                if self.prompt_session and sys.stdin.isatty():
                    user_input = self.prompt_session.prompt(
                        "\n❯ ",
                        style=Style.from_dict({"prompt": "ansicyan bold"}),
                    ).strip()
                else:
                    try:
                        user_input = input("\n❯ ").strip()
                    except (EOFError, KeyboardInterrupt):
                        break

                if not user_input:
                    continue

                if user_input.startswith("/"):
                    keep_running = self._handle_command(user_input)
                    if not keep_running:
                        break
                    continue

                # Process message via shared execute_prompt
                self.execute_prompt(user_input)

            except KeyboardInterrupt:
                console.print("\n[dim]Press Ctrl+D or type /exit to quit.[/dim]")
            except EOFError:
                console.print("\n[dim]Exiting...[/dim]")
                break
            except Exception as e:
                print_error(f"An unexpected error occurred: {e}")
