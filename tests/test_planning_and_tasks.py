"""
Integration and Unit tests for Phase 6 Autonomous Multi-Step Planning and Execution.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
import pytest
from app.agent.planning import Planner
from app.agent.task_controller import TaskController
from app.models.messages import ChatMessage, Role
from app.models.state import TaskExecutionRecord, TaskState, TaskStep
from app.models.tools import PermissionLevel, ToolDefinition, ToolExecutionResult
from app.providers.base import BaseLLMProvider
from app.storage.audit_store import AuditStore
from app.storage.database import Database
from app.storage.session_store import SessionStore
from app.tools.base import BaseTool
from app.tools.registry import ToolRegistry


class MockPlanLLM(BaseLLMProvider):
    def __init__(self, plan_json_response: str):
        super().__init__()
        self.response = plan_json_response

    def generate(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: Optional[float] = None,
    ) -> ChatMessage:
        return ChatMessage(role=Role.ASSISTANT, content=self.response)


class StepOneTool(BaseTool):
    name = "step_one_tool"
    description = "Step 1"
    permission_level = PermissionLevel.LEVEL_0_READ_ONLY

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {"type": "object", "properties": {}}

    def _run(self) -> Dict[str, Any]:
        return {"status": "ok", "exit_code": 0}


class StepTwoTool(BaseTool):
    name = "step_two_tool"
    description = "Step 2"
    permission_level = PermissionLevel.LEVEL_1_LOW_RISK

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {"type": "object", "properties": {"filename": {"type": "string"}}}

    def _run(self, filename: str) -> str:
        return f"Created {filename}"


class FlakyTool(BaseTool):
    name = "flaky_tool"
    description = "Fails once then succeeds"
    permission_level = PermissionLevel.LEVEL_0_READ_ONLY

    def __init__(self):
        super().__init__()
        self.attempts = 0

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {"type": "object", "properties": {}}

    def _run(self) -> Dict[str, Any]:
        self.attempts += 1
        if self.attempts == 1:
            raise RuntimeError("Transient connection failure")
        return {"status": "recovered", "exit_code": 0}


@pytest.fixture
def controller_setup(tmp_path: Path):
    db = Database(tmp_path / "test_tasks.db")
    session_store = SessionStore(db)
    audit_store = AuditStore(db)
    registry = ToolRegistry()
    registry.register(StepOneTool())
    registry.register(StepTwoTool())
    registry.register(FlakyTool())

    controller = TaskController(
        tool_registry=registry,
        session_store=session_store,
        audit_store=audit_store,
    )
    return db, session_store, audit_store, registry, controller


def test_planner_decomposition():
    plan_json = """[
        {
            "step_number": 1,
            "description": "Inspect environment",
            "tool_name": "step_one_tool",
            "parameters": {},
            "verification_rule": "exit_code == 0"
        },
        {
            "step_number": 2,
            "description": "Generate configuration",
            "tool_name": "step_two_tool",
            "parameters": {"filename": "config.json"},
            "verification_rule": "success"
        }
    ]"""

    planner = Planner(provider=MockPlanLLM(plan_json))
    tool_defs = [StepOneTool().definition, StepTwoTool().definition]

    task = planner.create_plan(
        session_id="session_test",
        goal="Initialize configuration",
        available_tools=tool_defs,
    )

    assert task.goal == "Initialize configuration"
    assert len(task.steps) == 2
    assert task.steps[0].tool_name == "step_one_tool"
    assert task.steps[1].parameters["filename"] == "config.json"


def test_task_controller_sequential_execution(controller_setup):
    db, session_store, audit_store, registry, controller = controller_setup
    session = session_store.create_session()

    task = TaskExecutionRecord(
        session_id=session.id,
        goal="Run sequential multi-step task",
        steps=[
            TaskStep(
                step_number=1,
                description="Run step 1",
                tool_name="step_one_tool",
                parameters={},
                verification_rule="exit_code == 0",
            ),
            TaskStep(
                step_number=2,
                description="Run step 2",
                tool_name="step_two_tool",
                parameters={"filename": "output.txt"},
            ),
        ],
    )

    completed_task = controller.execute_task(task)
    assert completed_task.state == TaskState.COMPLETED
    assert completed_task.completed_at is not None
    assert completed_task.steps[0].verified is True
    assert completed_task.steps[1].verified is True

    # Verify state saved in SQLite
    saved_task = session_store.get_task(task.id)
    assert saved_task is not None
    assert saved_task.state == TaskState.COMPLETED


def test_task_controller_recovery_loop(controller_setup):
    db, session_store, audit_store, registry, controller = controller_setup
    session = session_store.create_session()

    task = TaskExecutionRecord(
        session_id=session.id,
        goal="Test recovery retry mechanism",
        steps=[
            TaskStep(
                step_number=1,
                description="Run flaky tool with retry",
                tool_name="flaky_tool",
                parameters={},
                verification_rule="exit_code == 0",
            )
        ],
    )

    completed_task = controller.execute_task(task)
    # FlakyTool fails on try 1, succeeds on try 2 (within max_retries=2)
    assert completed_task.state == TaskState.COMPLETED
    assert completed_task.steps[0].verified is True
    assert "recovered" in completed_task.steps[0].result
