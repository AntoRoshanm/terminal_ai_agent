"""
Stateful Graph Orchestration Engine (LangGraph-style Agent State Machine)
"""

from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, Field
from app.logging import logger
from app.models.messages import ChatMessage, Role, ToolCall
from app.models.state import TaskExecutionRecord, TaskState, TaskStep
from app.models.tools import PermissionLevel, ToolExecutionResult
from app.providers.base import BaseLLMProvider
from app.tools.registry import ToolRegistry


class GraphState(BaseModel):
    """Execution state container passed between graph nodes."""
    session_id: str
    messages: List[ChatMessage] = Field(default_factory=list)
    objective: str = ""
    current_node: str = "UNDERSTAND"
    plan: Optional[TaskExecutionRecord] = None
    current_step_idx: int = 0
    selected_tool: Optional[str] = None
    tool_arguments: Dict[str, Any] = Field(default_factory=dict)
    last_result: Optional[ToolExecutionResult] = None
    error_count: int = 0
    max_retries: int = 3
    final_output: Optional[str] = None
    completed: bool = False


class AgentStateGraph:
    """Stateful Execution Graph coordinating the entire agent lifecycle."""

    def __init__(
        self,
        provider: BaseLLMProvider,
        registry: ToolRegistry,
        status_callback: Optional[Callable[[str, TaskState], None]] = None,
    ):
        self.provider = provider
        self.registry = registry
        self.status_callback = status_callback

    def _notify(self, text: str, state: TaskState) -> None:
        if self.status_callback:
            self.status_callback(text, state)

    def run(self, state: GraphState, max_steps: int = 15) -> GraphState:
        """Execute graph steps until completion, terminal state, or max_steps reached."""
        step_count = 0
        while not state.completed and step_count < max_steps:
            step_count += 1
            node_name = state.current_node

            if node_name == "UNDERSTAND":
                state = self._node_understand(state)
            elif node_name == "PLAN":
                state = self._node_plan(state)
            elif node_name == "SELECT_TOOL":
                state = self._node_select_tool(state)
            elif node_name == "PERMISSION_CHECK":
                state = self._node_permission_check(state)
            elif node_name == "EXECUTE":
                state = self._node_execute(state)
            elif node_name == "OBSERVE":
                state = self._node_observe(state)
            elif node_name == "VERIFY":
                state = self._node_verify(state)
            elif node_name == "DIAGNOSE_RECOVER":
                state = self._node_diagnose_recover(state)
            elif node_name == "COMPLETE":
                state = self._node_complete(state)
            else:
                logger.error("Unknown graph node '%s'", node_name)
                state.completed = True
                break

        return state

    def _node_understand(self, state: GraphState) -> GraphState:
        self._notify("Understanding request...", TaskState.UNDERSTANDING)
        tools = self.registry.get_definitions()
        response = self.provider.generate(state.messages, tools=tools)

        if not response.tool_calls:
            state.final_output = response.content
            state.current_node = "COMPLETE"
        else:
            first_call = response.tool_calls[0]
            state.selected_tool = first_call.name
            state.tool_arguments = first_call.arguments
            state.current_node = "PERMISSION_CHECK"
        return state

    def _node_plan(self, state: GraphState) -> GraphState:
        self._notify("Generating execution plan...", TaskState.PLANNING)
        state.current_node = "SELECT_TOOL"
        return state

    def _node_select_tool(self, state: GraphState) -> GraphState:
        state.current_node = "PERMISSION_CHECK"
        return state

    def _node_permission_check(self, state: GraphState) -> GraphState:
        tool = self.registry.get(state.selected_tool) if state.selected_tool else None
        if not tool:
            state.last_result = ToolExecutionResult(
                tool_call_id="call_err",
                tool_name=state.selected_tool or "unknown",
                success=False,
                error=f"Tool '{state.selected_tool}' not found in registry.",
            )
            state.current_node = "DIAGNOSE_RECOVER"
            return state

        state.current_node = "EXECUTE"
        return state

    def _node_execute(self, state: GraphState) -> GraphState:
        self._notify(f"Executing {state.selected_tool}...", TaskState.EXECUTING)
        tool_call_id = f"call_{state.selected_tool}"
        result = self.registry.execute(
            name=state.selected_tool or "",
            arguments=state.tool_arguments,
            tool_call_id=tool_call_id,
        )
        state.last_result = result
        state.current_node = "OBSERVE"
        return state

    def _node_observe(self, state: GraphState) -> GraphState:
        self._notify("Observing tool output...", TaskState.OBSERVING)
        if state.last_result and not state.last_result.success:
            state.current_node = "DIAGNOSE_RECOVER"
        else:
            state.current_node = "VERIFY"
        return state

    def _node_verify(self, state: GraphState) -> GraphState:
        self._notify("Verifying results...", TaskState.VERIFYING)
        tool_call_id = state.last_result.tool_call_id if state.last_result else f"call_{state.selected_tool}"
        assistant_msg = ChatMessage(
            role=Role.ASSISTANT,
            content=None,
            tool_calls=[ToolCall(id=tool_call_id, name=state.selected_tool or "", arguments=state.tool_arguments)],
        )
        tool_output_str = state.last_result.output_text if state.last_result else ""
        tool_msg = ChatMessage(
            role=Role.TOOL,
            content=tool_output_str,
            tool_call_id=tool_call_id,
            name=state.selected_tool,
        )
        state.messages.extend([assistant_msg, tool_msg])

        # Generate final explanation based on verified tool output
        final_resp = self.provider.generate(state.messages)
        state.final_output = final_resp.content
        state.current_node = "COMPLETE"
        return state

    def _node_diagnose_recover(self, state: GraphState) -> GraphState:
        self._notify("Diagnosing failure and recovering...", TaskState.RECOVERING)
        state.error_count += 1
        if state.error_count > state.max_retries:
            state.final_output = f"Task failed after {state.error_count} attempts: {state.last_result.error if state.last_result else 'Unknown error'}"
            state.current_node = "COMPLETE"
        else:
            state.current_node = "UNDERSTAND"
        return state

    def _node_complete(self, state: GraphState) -> GraphState:
        self._notify("Complete", TaskState.COMPLETED)
        state.completed = True
        return state
