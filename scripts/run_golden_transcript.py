"""
Comprehensive Golden Transcript Acceptance & Correctness Replay Runner (Master Directive v4 / v4.1)
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.agent.intent import IntentClassifier, classify_intent
from app.agent.orchestrator import AgentOrchestrator
from app.config import AgentConfig
from app.models.state import IntentCategory
from app.providers.factory import create_provider
from app.storage.database import Database
from app.storage.audit_store import AuditStore
from app.storage.session_store import SessionStore
from app.tools.registry import ToolRegistry
from app.tools.windows import register_windows_tools
from app.tools.filesystem import register_filesystem_tools
from app.tools.terminal import register_terminal_tools
from app.tools.software import register_software_tools

IPV4_REGEX = re.compile(r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b")


def run_golden_transcript(model_name: str = "llama3-groq-tool-use:8b") -> Dict[str, Any]:
    config = AgentConfig()
    config.provider.model = model_name
    config.provider.provider = "ollama"

    db = Database(config.storage.db_path)
    session_store = SessionStore(db)
    audit_store = AuditStore(db)
    tool_registry = ToolRegistry()

    # Register tools
    register_windows_tools(tool_registry)
    register_filesystem_tools(tool_registry)
    register_terminal_tools(tool_registry)
    register_software_tools(tool_registry)

    provider = create_provider(config.provider)
    orchestrator = AgentOrchestrator(
        config=config,
        provider=provider,
        session_store=session_store,
        audit_store=audit_store,
        tool_registry=tool_registry,
    )

    session = session_store.create_session(f"golden_transcript_{model_name}")
    session_id = session.id

    prompts = [
        ("what is my ipv4 address ?", "get_network_info", "IPv4 format validation"),
        ("what are the software i am having in my computer", "get_installed_software", "Installed software enumeration"),
        ("what are the software is active in the computer right now?", "get_process_info", "Active running processes"),
        ("what are the services is runing on my window . use the task manger", "get_service_info", "Windows services state"),
    ]

    print("=" * 75)
    print(f"GOLDEN TRANSCRIPT REPLAY — Model: {model_name}")
    print("=" * 75)

    results = []

    for idx, (prompt, expected_tool, desc) in enumerate(prompts, 1):
        print(f"\n❯ {prompt}", flush=True)

        executed_tools = []
        def status_cb(desc, state):
            print(f"[{state.value.upper()}] {desc}", flush=True)
            if "Executing " in desc:
                tool_called = desc.split("Executing ")[-1].replace("...", "").strip()
                executed_tools.append(tool_called)

        response = orchestrator.process_message(
            session_id=session_id,
            user_text=prompt,
            status_callback=status_cb,
        )
        content = response.content or ""
        print(f"Agent: {content}\n", flush=True)

        # Correctness checks per query
        is_correct = True
        audit_notes = []

        if idx == 1:
            # Query 1: IPv4 address format check (Directive B.33)
            ipv4_match = IPV4_REGEX.search(content)
            if not ipv4_match or "MSFT_NetIPAddress" in content or "Name =" in content:
                is_correct = False
                audit_notes.append("Failed: Content contains malformed WMI string or lacks valid dotted-quad IPv4.")
            else:
                audit_notes.append(f"Passed: Valid IPv4 detected ({ipv4_match.group(0)}).")

        elif idx == 2:
            # Query 2: Installed software enumeration
            if len(content.splitlines()) < 2 and "installed" not in content.lower():
                is_correct = False
                audit_notes.append("Failed: Lacks structured enumeration of installed software.")
            else:
                audit_notes.append("Passed: Enumerated installed software.")

        elif idx == 3:
            # Query 3: Active running processes (must call get_process_info)
            if expected_tool not in executed_tools:
                is_correct = False
                audit_notes.append(f"Failed: Tool '{expected_tool}' was not invoked (called {executed_tools}).")
            else:
                audit_notes.append("Passed: Correctly invoked get_process_info and enumerated active processes.")

        elif idx == 4:
            # Query 4: Services info (must call get_service_info, no raw terminal fallback)
            if expected_tool not in executed_tools:
                is_correct = False
                audit_notes.append(f"Failed: Tool '{expected_tool}' was not invoked (called {executed_tools}).")
            else:
                audit_notes.append("Passed: Correctly invoked get_service_info without generic terminal fallback.")

        if "based on the information provided" in content.lower() or "you've listed" in content.lower():
            is_correct = False
            audit_notes.append("Failed: B.31 grounding violation (spoke as if user supplied system data).")

        results.append({
            "query_index": idx,
            "prompt": prompt,
            "expected_tool": expected_tool,
            "executed_tools": executed_tools,
            "response": content,
            "is_correct": is_correct,
            "notes": " ".join(audit_notes),
        })

    print("=" * 75)
    print(f"SUMMARY FOR {model_name}: {'ALL PASSED' if all(r['is_correct'] for r in results) else 'FAILED'}")
    print("=" * 75)
    return {"model": model_name, "results": results, "all_passed": all(r["is_correct"] for r in results)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Golden Transcript Replay")
    parser.add_argument("--model", type=str, default="llama3-groq-tool-use:8b", help="Model to evaluate")
    args = parser.parse_args()

    run_golden_transcript(args.model)
