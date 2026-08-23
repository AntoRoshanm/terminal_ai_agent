"""
Goal Decomposition and Task Plan Generation Engine
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional
from app.models.messages import ChatMessage, Role
from app.models.state import TaskExecutionRecord, TaskState, TaskStep
from app.models.tools import ToolDefinition
from app.providers.base import BaseLLMProvider

logger = logging.getLogger("windows_ai_agent.planning")

PLANNER_SYSTEM_PROMPT = """You are the Planning Engine of Windows AI Agent.
Given a user's goal, available tools, and current environment context, break down the goal into a sequential, actionable execution plan.

Each step MUST be clear, minimal, safe, and verifiable.

Output your plan strictly in JSON format as a list of steps matching this schema:
[
  {
    "step_number": 1,
    "description": "Inspect repository structure to detect project type",
    "tool_name": "dir_inspect",
    "parameters": {"directory_path": "."},
    "verification_rule": "detected_projects is not empty"
  },
  {
    "step_number": 2,
    "description": "Run unit test suite",
    "tool_name": "terminal_exec",
    "parameters": {"command": "python -m pytest"},
    "verification_rule": "exit_code == 0"
  }
]

Do not include extra conversational text outside the JSON block.
"""


class Planner:
    """Generates structured execution plans for multi-step tasks."""

    def __init__(self, provider: BaseLLMProvider):
        self.provider = provider

    def _extract_json(self, text: str) -> Optional[List[Dict[str, Any]]]:
        """Extract and parse JSON array from model output."""
        if not text:
            return None

        # 1. Try direct json parse
        try:
            parsed = json.loads(text.strip())
            if isinstance(parsed, list):
                return parsed
        except Exception:
            pass

        # 2. Extract from markdown ```json ``` code block
        match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(1))
                if isinstance(parsed, list):
                    return parsed
            except Exception:
                pass

        # 3. Find any bracketed array
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1 and end > start:
            try:
                parsed = json.loads(text[start : end + 1])
                if isinstance(parsed, list):
                    return parsed
            except Exception:
                pass

        return None

    def create_plan(
        self,
        session_id: str,
        goal: str,
        available_tools: List[ToolDefinition],
        context_notes: Optional[str] = None,
    ) -> TaskExecutionRecord:
        """Decompose a user goal into a TaskExecutionRecord with sequential steps."""
        tool_descriptions = "\n".join(
            [f"- {t.name}: {t.description} (Params: {list(t.parameters.get('properties', {}).keys())})" for t in available_tools]
        )

        user_content = f"Goal: {goal}\n\nAvailable Tools:\n{tool_descriptions}"
        if context_notes:
            user_content += f"\n\nContext Notes:\n{context_notes}"

        messages = [
            ChatMessage(role=Role.SYSTEM, content=PLANNER_SYSTEM_PROMPT),
            ChatMessage(role=Role.USER, content=user_content),
        ]

        try:
            response = self.provider.generate(messages=messages, temperature=0.1)
            raw_content = response.content or ""
            steps_data = self._extract_json(raw_content)

            task = TaskExecutionRecord(
                session_id=session_id,
                goal=goal,
                state=TaskState.PLANNING,
            )

            if steps_data:
                for idx, item in enumerate(steps_data, start=1):
                    task.steps.append(
                        TaskStep(
                            step_number=item.get("step_number", idx),
                            description=item.get("description", f"Step {idx}"),
                            tool_name=item.get("tool_name"),
                            parameters=item.get("parameters", {}),
                            verification_rule=item.get("verification_rule"),
                            state=TaskState.NEW,
                        )
                    )
            else:
                # Fallback single step
                task.steps.append(
                    TaskStep(
                        step_number=1,
                        description=f"Execute goal: {goal}",
                        tool_name="terminal_exec",
                        parameters={"command": goal},
                        state=TaskState.NEW,
                    )
                )

            return task

        except Exception as e:
            logger.error(f"Failed to generate task plan: {e}")
            # Return single fallback step
            return TaskExecutionRecord(
                session_id=session_id,
                goal=goal,
                state=TaskState.PLANNING,
                steps=[
                    TaskStep(
                        step_number=1,
                        description=f"Execute goal: {goal}",
                        state=TaskState.NEW,
                    )
                ],
                error_summary=str(e),
            )
