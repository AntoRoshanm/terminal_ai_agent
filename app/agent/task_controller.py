"""
Multi-Step Task Execution Controller with Dynamic Recovery Loop
"""

from datetime import datetime, timezone
import logging
from typing import Callable, Optional
from app.agent.fsm import TaskStateMachine
from app.models.messages import ToolCall
from app.models.state import TaskExecutionRecord, TaskState, TaskStep
from app.models.tools import PermissionLevel, ToolExecutionResult
from app.storage.audit_store import AuditStore
from app.storage.session_store import SessionStore
from app.tools.registry import ToolRegistry

logger = logging.getLogger("windows_ai_agent.controller")


class TaskController:
    """Oversees sequential step execution, observation, verification, and recovery."""

    def __init__(
        self,
        tool_registry: ToolRegistry,
        session_store: SessionStore,
        audit_store: AuditStore,
        approval_callback: Optional[Callable[[str, ToolCall, PermissionLevel], bool]] = None,
        max_retries_per_step: int = 2,
    ):
        self.tools = tool_registry
        self.session_store = session_store
        self.audit_store = audit_store
        self.approval_callback = approval_callback
        self.max_retries = max_retries_per_step

    def _verify_step(self, step: TaskStep, result: ToolExecutionResult) -> bool:
        """Ground-truth evaluation of a step's result."""
        if not result.success:
            return False

        rule = (step.verification_rule or "").lower().strip()
        if not rule:
            return result.success

        if "exit_code == 0" in rule:
            if isinstance(result.data, dict) and "exit_code" in result.data:
                return result.data["exit_code"] == 0
            return result.success

        if "verified == true" in rule:
            if isinstance(result.data, dict) and "verified" in result.data:
                return bool(result.data["verified"])

        return result.success

    def execute_task(
        self,
        task: TaskExecutionRecord,
        step_callback: Optional[Callable[[TaskStep, str], None]] = None,
    ) -> TaskExecutionRecord:
        """Run the task through its planned steps."""
        task.state = TaskState.EXECUTING
        self.session_store.save_task(task)

        for idx, step in enumerate(task.steps):
            task.current_step_index = idx
            step.state = TaskState.EXECUTING
            if step_callback:
                step_callback(step, f"Starting step {step.step_number}: {step.description}")

            retries = 0
            step_success = False

            while retries <= self.max_retries and not step_success:
                if not step.tool_name:
                    # Informational / conceptual step with no tool
                    step.state = TaskState.COMPLETED
                    step.verified = True
                    step_success = True
                    break

                tool = self.tools.get(step.tool_name)
                if not tool:
                    step.state = TaskState.FAILED
                    step.error = f"Tool '{step.tool_name}' not found in registry"
                    break

                # Permission check
                level = tool.permission_level
                if level >= PermissionLevel.LEVEL_2_APPROVAL_REQUIRED:
                    if self.approval_callback:
                        tc = ToolCall(name=step.tool_name, arguments=step.parameters)
                        approved = self.approval_callback(step.tool_name, tc, level)
                        if not approved:
                            step.state = TaskState.FAILED
                            step.error = f"User denied authorization for '{step.tool_name}'"
                            break

                # Execute step tool
                exec_result: ToolExecutionResult = self.tools.execute(
                    name=step.tool_name,
                    tool_call_id=f"step_{step.step_number}_try_{retries}",
                    arguments=step.parameters,
                )

                # Record audit log
                self.audit_store.record_event(
                    session_id=task.session_id,
                    task_id=task.id,
                    event_type="TASK_STEP_EXECUTION",
                    payload={
                        "step_number": step.step_number,
                        "description": step.description,
                        "tool": step.tool_name,
                        "parameters": step.parameters,
                        "success": exec_result.success,
                        "duration_ms": exec_result.duration_ms,
                    },
                )

                # Observe & Verify
                step.state = TaskState.VERIFYING
                if step_callback:
                    step_callback(step, f"Verifying step {step.step_number}...")

                is_verified = self._verify_step(step, exec_result)

                if is_verified:
                    step.state = TaskState.COMPLETED
                    step.verified = True
                    step.result = exec_result.output_text
                    step_success = True
                    if step_callback:
                        step_callback(step, f"Step {step.step_number} completed and verified.")
                else:
                    retries += 1
                    if retries <= self.max_retries:
                        step.state = TaskState.RECOVERING
                        if step_callback:
                            step_callback(step, f"Step {step.step_number} failed verification. Retrying ({retries}/{self.max_retries})...")
                    else:
                        step.state = TaskState.FAILED
                        step.error = exec_result.error or "Verification check failed."
                        if step_callback:
                            step_callback(step, f"Step {step.step_number} failed after {self.max_retries} retries.")

            self.session_store.save_task(task)

            # If a critical step failed, halt task
            if step.state == TaskState.FAILED:
                task.state = TaskState.FAILED
                task.error_summary = f"Step {step.step_number} ('{step.description}') failed: {step.error}"
                self.session_store.save_task(task)
                return task

        task.state = TaskState.COMPLETED
        task.completed_at = datetime.now(timezone.utc)
        self.session_store.save_task(task)
        return task
