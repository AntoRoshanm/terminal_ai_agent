"""
Agent Decision Orchestrator & Execution Loop with Strict Autonomous Guards (B.0 to B.32)
"""

import json
from pathlib import Path
import re
import time
from typing import Any, Callable, Dict, List, Optional, Tuple
from app.agent.context import ContextManager
from app.agent.fsm import InvalidStateTransitionError, TaskStateMachine
from app.agent.intent import IntentClassifier, classify_intent
from app.config import AgentConfig
from app.logging import logger
from app.models.messages import ChatMessage, Role, ToolCall
from app.models.state import IntentCategory, TaskState, VerificationResult
from app.models.tools import PermissionLevel, ToolExecutionResult
from app.providers.base import BaseLLMProvider
from app.storage.audit_store import AuditStore
from app.storage.session_store import SessionStore
from app.tools.filesystem.safety import PathSafety
from app.tools.registry import ToolRegistry


class AgentOrchestrator:
    """Central decision loop managing prompt execution, tool dispatch, and verification."""

    COMMAND_SUGGESTION_PATTERNS = [
        re.compile(r"\byou can run\b", re.IGNORECASE),
        re.compile(r"\btry running\b", re.IGNORECASE),
        re.compile(r"\btry this command\b", re.IGNORECASE),
        re.compile(r"\bhere('s| is) how to check\b", re.IGNORECASE),
        re.compile(r"\brun the following command\b", re.IGNORECASE),
        re.compile(r"\bcheck it with powershell\b", re.IGNORECASE),
        re.compile(r"\buse sys\.version\b", re.IGNORECASE),
        re.compile(r"\b(can't|cannot|not able to|unable to|do not have the capability to) (directly )?(create|write|delete|modify|edit|run|execute|perform|inspect)\b", re.IGNORECASE),
        re.compile(r"\b(guide you through|instructions on how to|how to do this manually|provide instructions)\b", re.IGNORECASE),
        re.compile(r"\bmanaged by an AI that can only provide information\b", re.IGNORECASE),
    ]

    UNEXECUTED_INTENT_PATTERNS = [
        re.compile(r"\blet me (proceed|execute|run|do|create|write|delete|start|try|apply|perform|update|modify|now|overwrite)\b", re.IGNORECASE),
        re.compile(r"\bi will (proceed|execute|run|do|create|write|delete|start|try|apply|perform|update|modify|now|overwrite)\b", re.IGNORECASE),
        re.compile(r"\bi need to (set|run|execute|call|perform|create|write|delete|update|overwrite)\b", re.IGNORECASE),
        re.compile(r"\bi('m| am) going to (proceed|execute|run|do|create|write|delete|start|try|perform|overwrite)\b", re.IGNORECASE),
        re.compile(r"\blet me check\b", re.IGNORECASE),
        re.compile(r"\bto overwrite it.*let me\b", re.IGNORECASE),
    ]

    SELF_LIMITATION_PATTERNS = [
        re.compile(r"\bi\s+don'?t\s+have\s+(access\s+to|the\s+ability\s+to|tools?\s+to|a\s+way\s+to)\b", re.IGNORECASE),
        re.compile(r"\bi\s+(cannot|can'?t|am\s+unable\s+to)\s+(check|determine|view|get|see|tell|access|inspect|create|write|delete|know)\b", re.IGNORECASE),
        re.compile(r"\b(as\s+an\s+ai|i\s+am\s+an\s+ai\s+and)\s+(i\s+)?(cannot|can'?t|do\s+not\s+have)\b", re.IGNORECASE),
        re.compile(r"\byou\s+(can|will\s+need\s+to|should)\s+check\s+(this\s+)?yourself\b", re.IGNORECASE),
        re.compile(r"\bi\s+do\s+not\s+have\s+(a\s+)?(real-?time\s+clock|clock|access)\b", re.IGNORECASE),
        re.compile(r"\bi\s+am\s+not\s+able\s+to\s+(check|determine|access|view|get)\b", re.IGNORECASE),
    ]

    def __init__(
        self,
        config: AgentConfig,
        provider: BaseLLMProvider,
        session_store: SessionStore,
        audit_store: AuditStore,
        tool_registry: ToolRegistry,
        permission_checker: Optional[Callable] = None,
        approval_callback: Optional[Callable] = None,
    ):
        self.config = config
        self.provider = provider
        self.session_store = session_store
        self.audit_store = audit_store
        self.tools = tool_registry
        self.permission_checker = approval_callback or permission_checker
        self.context_manager = ContextManager(max_messages=40)

    @property
    def approval_callback(self):
        return self.permission_checker

    @approval_callback.setter
    def approval_callback(self, callback):
        self.permission_checker = callback

    def _check_permission(self, tool_name: str, tool_call: ToolCall) -> Tuple[bool, Optional[str]]:
        """Evaluate whether a tool call is authorized to execute."""
        tool = self.tools.get(tool_name)
        if not tool:
            return False, f"Tool '{tool_name}' does not exist in registry."

        level = tool.permission_level

        # Custom callback if provided
        if self.permission_checker:
            try:
                allowed = self.permission_checker(tool_name, tool_call, level)
            except TypeError:
                allowed = self.permission_checker(tool_name, tool_call)
            if not allowed:
                return False, "User rejected execution."
            return True, None

        # Level 0 & 1: Auto-approved if configured
        if level == PermissionLevel.LEVEL_0_READ_ONLY and self.config.security.auto_approve_level_0:
            return True, None
        if level == PermissionLevel.LEVEL_1_LOW_RISK and self.config.security.auto_approve_level_1:
            return True, None

        # Level 2 & 3: Fallback check against configuration
        if level == PermissionLevel.LEVEL_2_APPROVAL_REQUIRED:
            if not self.config.security.require_approval_level_2:
                return True, None
            return False, "Level 2 permission requires user confirmation."

        if level == PermissionLevel.LEVEL_3_HIGH_RISK:
            if not self.config.security.require_approval_level_3:
                return True, None
            return False, "Level 3 permission requires user confirmation."

        return True, None

    def _check_semantic_alignment(self, user_text: str, tool_name: str) -> Tuple[bool, Optional[str]]:
        """
        Directive B.29: Tool-Claim Semantic Alignment.
        Verifies that the tool invoked actually supports the specific claim/query requested.
        """
        text = user_text.lower()

        # 1. Active / running software requested but static inventory tool called
        is_active_query = any(w in text for w in (
            "active in the computer", "software is active", "software are active",
            "active software", "running right now", "currently active", "what is running",
            "what's running", "what's open", "what is open", "running processes"
        ))
        if is_active_query and "installed_software" in tool_name:
            return False, (
                "SEMANTIC MISALIGNMENT (Directive B.29): The user asked for currently active/running software/processes. "
                f"You invoked '{tool_name}' (which only queries static installed programs). "
                "You MUST invoke 'get_process_info' (or 'get_process_info_tool') to inspect actively running processes."
            )

        # 2. Services requested but generic terminal_exec or installed_software called
        is_services_query = any(w in text for w in (
            "services is runing", "services are running", "services running",
            "windows services", "system services", "list services", "service status",
            "systemd services", "launchctl services"
        ))
        if is_services_query and ("terminal_exec" in tool_name or "installed_software" in tool_name):
            return False, (
                "SEMANTIC MISALIGNMENT (Directive B.29): The user asked for system services status. "
                f"You invoked '{tool_name}'. "
                "You MUST invoke 'get_service_info' (or 'get_service_info_tool') to query structured service state."
            )

        # 3. Task manager / resource monitor reference mapped to process/service inspection
        is_task_mgr_query = any(w in text for w in ("task manager", "task manger", "activity monitor", "resource monitor"))
        if is_task_mgr_query and "terminal_exec" in tool_name:
            return False, (
                "SEMANTIC MISALIGNMENT (Directive B.29): The user asked for Task Manager / Activity Monitor status. "
                f"You invoked generic '{tool_name}'. "
                "You MUST invoke 'get_process_info' (or 'get_service_info') to return structured system state."
            )

        return True, None

    def get_mcp_diagnostics(self) -> Dict[str, Any]:
        """Expose MCP server and tool health diagnostics (Master Directive B.25)."""
        all_tools = self.tools.get_definitions()
        mcp_tools = [t.name for t in all_tools if t.name.startswith("mcp_")]
        has_web_search = any("web_search" in t for t in mcp_tools)
        return {
            "mcp_tools_discovered": len(mcp_tools),
            "tools": mcp_tools,
            "web_search_available": has_web_search,
            "web_search_active_tool": "mcp_web-search_web_search" if has_web_search else None,
        }

    def _find_matching_tool(self, user_text: str, content: str) -> Optional[Tuple[str, str]]:
        """
        Directive B.41: Match self-limitation claims against registered tools.
        Returns (tool_name, tool_description) if a matching tool is available.
        """
        combined = f"{user_text} {content}".lower()

        # 1. Date & Time / Clock
        if any(w in combined for w in ("time", "clock", "date", "day", "current time", "what time", "today's date", "timezone")):
            tool = self.tools.get("get_current_datetime")
            if tool:
                return ("get_current_datetime", tool.description)

        # 2. Processes / Running Applications
        if any(w in combined for w in ("process", "running", "active software", "task manager", "app active", "program running")):
            tool = self.tools.get("get_process_info")
            if tool:
                return ("get_process_info", tool.description)

        # 3. Hardware / Memory / CPU / GPU
        if any(w in combined for w in ("ram", "memory", "cpu", "gpu", "hardware", "specs", "cores")):
            tool = self.tools.get("get_hardware_info")
            if tool:
                return ("get_hardware_info", tool.description)

        # 4. Storage / Disk
        if any(w in combined for w in ("disk", "storage", "drive", "free space", "volume")):
            tool = self.tools.get("get_storage_info")
            if tool:
                return ("get_storage_info", tool.description)

        # 5. Services / Daemons
        if any(w in combined for w in ("service", "services", "daemon", "print spooler")):
            tool = self.tools.get("get_service_info") or self.tools.get("manage_service")
            if tool:
                return (tool.name, tool.description)

        # 6. Files / Create / Write / Delete
        if any(w in combined for w in ("file", "create a file", "write", "folder", "directory", "delete", "remove")):
            tool = self.tools.get("file_write") or self.tools.get("file_manage")
            if tool:
                return (tool.name, tool.description)

        # 7. Network / IP
        if any(w in combined for w in ("ip", "ipv4", "network", "adapter", "mac address")):
            tool = self.tools.get("get_network_info")
            if tool:
                return ("get_network_info", tool.description)

        # 8. Installed Software / Packages
        if any(w in combined for w in ("installed", "package", "software", "python version")):
            tool = self.tools.get("get_installed_software")
            if tool:
                return ("get_installed_software", tool.description)

        return None

    @staticmethod
    def _parse_generative_word_target(text: str) -> Optional[int]:
        """
        Directive B.42: Extracts explicit generative content length targets from user prompts.
        Examples: '10,000,000 words', '10 million words', '3000-word story', '50k words'.
        """
        t = text.lower()
        m = re.search(r'\b(\d+(?:,\d+)*(?:\.\d+)?)\s*(million|mil|billion|bil|k|thousand)?\s*-?\s*words?\b', t)
        if m:
            num_str = m.group(1).replace(',', '')
            try:
                val = float(num_str)
                unit = m.group(2)
                if unit:
                    if unit.startswith('m'):
                        val *= 1_000_000
                    elif unit.startswith('b'):
                        val *= 1_000_000_000
                    elif unit.startswith('k') or unit.startswith('th'):
                        val *= 1_000
                return int(val)
            except (ValueError, TypeError):
                pass
        return None

    @staticmethod
    def _clean_response_text(text: Optional[str]) -> Optional[str]:
        if not text:
            return text
        # Strip Llama 3 / Qwen raw chat template role headers (Directive v5.3 Section 2)
        cleaned = re.sub(r"^(?:<\|start_header_id\|>)?\s*(?:assistant|system|user)\s*(?:<\|end_header_id\|>)?\s*\n*", "", text, flags=re.IGNORECASE)
        cleaned = re.sub(r"<\|(?:start_header_id|end_header_id|eot_id|im_start|im_end)\|>", "", cleaned)
        return cleaned.strip()

    def process_message(
        self,
        session_id: str,
        user_text: str,
        status_callback: Optional[Callable[[str, TaskState], None]] = None,
        max_tool_iterations: int = 10,
    ) -> ChatMessage:
        """Process a user message through discrete intent classification, tool calling, execution, and verification."""
        start_time = time.perf_counter()
        current_state = TaskState.NEW

        def update_state(new_state: TaskState, description: str = ""):
            nonlocal current_state
            try:
                TaskStateMachine.validate_transition(current_state, new_state)
            except InvalidStateTransitionError as e:
                logger.warning(f"State transition warning: {e}")
            current_state = new_state
            if status_callback:
                status_callback(description, new_state)

        def attach_timing(msg: ChatMessage, state: TaskState) -> ChatMessage:
            elapsed = time.perf_counter() - start_time
            timing_tag = f"\n(Completed in {elapsed:.1f}s)" if state != TaskState.FAILED else f"\n(Failed in {elapsed:.1f}s)"
            if msg.content and not msg.content.strip().endswith("s)"):
                msg.content = msg.content.rstrip() + timing_tag
            return msg

        # Directive B.42: Generative Bulk-Content Upfront Feasibility Gate
        gen_target_words = self._parse_generative_word_target(user_text)
        if gen_target_words and gen_target_words > 50_000:
            logger.warning(
                "Directive B.42 Feasibility Gate Triggered: %d words requested. Exceeds practical single/multi-call ceiling (50,000 words).",
                gen_target_words,
            )
            est_calls = max(1, gen_target_words // 3000)
            refusal_text = (
                f"Refused (Directive B.42 Feasibility Gate): Generating {gen_target_words:,} words is physically infeasible "
                f"in a single pass with any language model (at ~3,000 words per generation call, it would require on the order of {est_calls:,}+ sequential LLM calls). "
                f"I can generate a focused, complete text (up to ~3,000–5,000 words) now, or outline a chapter-by-chapter structure for a multi-stage project. "
                f"Which would you like?"
            )
            update_state(TaskState.UNDERSTANDING, "Evaluating generative feasibility...")
            update_state(TaskState.COMPLETED, "Generative request exceeded feasibility ceiling")
            refusal_msg = ChatMessage(role=Role.ASSISTANT, content=refusal_text)
            self.session_store.add_message(session_id, refusal_msg)
            self.audit_store.record_event(
                session_id=session_id,
                event_type="GENERATIVE_FEASIBILITY_REFUSAL",
                payload={"target_words": gen_target_words, "user_text": user_text},
            )
            return attach_timing(refusal_msg, TaskState.COMPLETED)

        # Session-Level Pending-Action Context Resume (Directive v5.3 Section 3)
        session = None
        pending_action = None
        try:
            session = self.session_store.get_session(session_id)
            if session and isinstance(getattr(session, "metadata", None), dict):
                p_act = session.metadata.get("pending_action")
                if isinstance(p_act, dict) and "goal" in p_act:
                    pending_action = p_act
        except Exception:
            session = None
            pending_action = None

        CONFIRMATION_PATTERNS = [
            re.compile(r"^\s*(yes|y|yeah|yep|sure|ok|okay|confirm|proceed|go ahead|do it|continue|execute)\b", re.IGNORECASE),
            re.compile(r"^\s*(both|applications|services|all|desktop|yes please)\b", re.IGNORECASE),
        ]

        if pending_action:
            user_strip = user_text.strip().lower()
            if any(p.match(user_strip) for p in CONFIRMATION_PATTERNS) or len(user_text.split()) <= 4:
                logger.info("Resuming pending action context: '%s' with user reply '%s'", pending_action.get("goal"), user_text)
                original_goal = pending_action.get("goal", "")
                merged_text = f"{original_goal} (User confirmed: {user_text})"
                intent_val = pending_action.get("intent", IntentCategory.LOCAL_ACTION.value)
                try:
                    intent = IntentCategory(intent_val)
                except Exception:
                    intent = IntentCategory.LOCAL_ACTION
                user_text = merged_text
                if session and isinstance(session.metadata, dict):
                    new_meta = dict(session.metadata)
                    new_meta.pop("pending_action", None)
                    session.metadata = new_meta
                    self.session_store.update_session(session)
            else:
                if session and isinstance(session.metadata, dict):
                    new_meta = dict(session.metadata)
                    new_meta.pop("pending_action", None)
                    session.metadata = new_meta
                    self.session_store.update_session(session)
                intent = classify_intent(user_text)
        else:
            # 1. Discrete Intent Classification (B.0.1 & B.12)
            intent = classify_intent(user_text)

        # Directive B.32: Defense-in-Depth Parallel Pattern Backstop
        is_env_query = IntentClassifier.is_environment_query(user_text)
        if is_env_query and intent == IntentCategory.NORMAL_CHAT:
            logger.info("Directive B.32: Pattern backstop overrode NORMAL_CHAT to LOCAL_INFORMATION for environment query.")
            intent = IntentCategory.LOCAL_INFORMATION

        self.audit_store.record_event(
            session_id=session_id,
            event_type="INTENT_CLASSIFIED",
            payload={"intent": intent.value, "user_text": user_text, "pattern_backstop_active": is_env_query},
        )

        update_state(TaskState.UNDERSTANDING, f"Analyzing request ({intent.value})...")

        # Record user message in persistence
        user_message = ChatMessage(role=Role.USER, content=user_text)
        self.session_store.add_message(session_id, user_message)
        self.audit_store.record_event(
            session_id=session_id,
            event_type="USER_MESSAGE",
            payload={"content": user_text, "intent": intent.value},
        )

        # Check for Multi-Agent Orchestration Objective (Directive v8, v9, v9.1, v10.1)
        user_lower = user_text.lower()
        multi_agent_triggers = [
            "multiple specialized agents", "specialized agents", "specialist agents",
            "multiple agents", "multi-agent", "multi agent", "agent team",
            "research and create", "research and write", "research and generate",
            "research and report", "research in depth", "research in-depth",
            "in-depth research", "deep research", "comprehensive research",
            "in depth", "in-depth",
            "technical guide", "reference guide", "technical report",
            "comprehensive report", "comprehensive analysis", "technical paper",
            "whitepaper", "white paper",
            "create a comprehensive", "generate a comprehensive",
            "create a pdf", "generate a pdf", "create a docx", "generate a docx",
            "create a pptx", "generate a pptx", "create a report", "generate a report",
            "create a document", "generate a document", "create a technical", "generate a technical",
        ]
        is_multi_agent = (
            any(k in user_lower for k in multi_agent_triggers)
            or (user_lower.startswith("research ") and len(user_lower.split()) >= 3)
            or (
                intent in (IntentCategory.WEB_RESEARCH, IntentCategory.MULTI_TOOL, IntentCategory.LOCAL_ACTION)
                and any(k in user_lower for k in ["pdf", "docx", "pptx", "report", "document", "guide", "paper", "agents", "specialized", "in depth", "in-depth"])
            )
        )

        if is_multi_agent:
            logger.info("Routing complex objective to LeadOrchestrator multi-agent engine: '%s'", user_text)
            update_state(TaskState.PLANNING, "Decomposing objective into specialist worker agents...")
            from app.agent.multi_agent import LeadOrchestrator, WorkspaceManager, HardwareConcurrencyManager
            import shutil

            ws = WorkspaceManager()
            concurrency = HardwareConcurrencyManager()
            lead_orch = LeadOrchestrator(
                config=self.config,
                provider=self.provider,
                tool_registry=self.tools,
                workspace=ws,
                concurrency_manager=concurrency,
                approval_callback=self.permission_checker,
            )

            def ma_callback(msg: str, task_id: str = ""):
                if "Starting" in msg or "Dispatching" in msg:
                    update_state(TaskState.EXECUTING, msg)
                elif "COMPLETED" in msg or "RECOVERED" in msg:
                    update_state(TaskState.EXECUTING, msg)
                elif "FAILED" in msg:
                    update_state(TaskState.RECOVERING, msg)

            ma_result = lead_orch.execute_workflow(user_text, status_callback=ma_callback)

            # Copy deliverables from workspace outputs to Desktop if requested or final deliverable
            desktop = (Path.home() / "Desktop").resolve()
            created_deliverables = []
            for out in ma_result.outputs_created:
                src_path = Path(out["path"])
                if src_path.exists():
                    dest_path = desktop / src_path.name
                    try:
                        shutil.copy2(src_path, dest_path)
                        created_deliverables.append(f"- {src_path.name} ({dest_path}) [{out['size_bytes']:,} bytes]")
                    except Exception:
                        created_deliverables.append(f"- {src_path.name} ({src_path}) [{out['size_bytes']:,} bytes]")

            if ma_result.success:
                update_state(TaskState.VERIFYING, "Verifying multi-agent output deliverables...")
                update_state(TaskState.COMPLETED, "Multi-agent workflow executed and verified.")
            else:
                update_state(TaskState.FAILED, "Multi-agent workflow completed with errors.")

            deliverables_text = "\n".join(created_deliverables) if created_deliverables else "None"
            response_content = (
                f"{ma_result.summary}\n\n"
                f"**Generated Deliverables:**\n{deliverables_text}"
            )
            resp_msg = ChatMessage(role=Role.ASSISTANT, content=response_content)
            self.session_store.add_message(session_id, resp_msg)
            self.audit_store.record_event(
                session_id=session_id,
                event_type="MULTI_AGENT_WORKFLOW_COMPLETED",
                payload={"objective": user_text, "success": ma_result.success, "tasks": ma_result.tasks_executed},
            )
            return attach_timing(resp_msg, TaskState.COMPLETED if ma_result.success else TaskState.FAILED)

        # Build message history with system prompt
        # Directive B.30: Fresh per-turn execution trace
        history = self.session_store.get_messages(session_id)
        messages = [
            ChatMessage(role=Role.SYSTEM, content=self.config.system_prompt)
        ] + self.context_manager.trim_history(history)

        executed_calls = set()
        execution_trace: List[Dict[str, Any]] = []
        iteration = 0

        # Actionable intent check (including B.32 backstop)
        is_actionable = is_env_query or intent in (
            IntentCategory.LOCAL_ACTION,
            IntentCategory.LOCAL_INFORMATION,
            IntentCategory.TROUBLESHOOTING,
            IntentCategory.WEB_INFORMATION,
            IntentCategory.WEB_RESEARCH,
            IntentCategory.MULTI_TOOL,
        )

        while iteration < max_tool_iterations:
            iteration += 1

            # Get available tool definitions
            tool_definitions = self.tools.get_definitions()

            try:
                assistant_response = self.provider.generate(
                    messages=messages,
                    tools=tool_definitions if tool_definitions else None,
                )
            except Exception as e:
                logger.error(f"Model generation error: {e}")
                update_state(TaskState.FAILED, f"Model error: {e}")
                error_msg = ChatMessage(
                    role=Role.ASSISTANT,
                    content=f"An error occurred while communicating with the AI model: {e}",
                )
                self.session_store.add_message(session_id, error_msg)
                return attach_timing(error_msg, TaskState.FAILED)

            if assistant_response.content:
                assistant_response.content = self._clean_response_text(assistant_response.content)

            # B.0.2 FSM Completion Guard: If no tools called
            if not assistant_response.tool_calls:
                if is_actionable and len(execution_trace) == 0 and iteration == 1:
                    # Model attempted to complete actionable task without executing any tool
                    logger.warning(
                        "FSM Completion Guard Triggered: %s requires tool execution before completion.",
                        intent.value,
                    )
                    # Force model to invoke tool using valid user-turn instruction
                    messages.append(assistant_response)
                    messages.append(
                        ChatMessage(
                            role=Role.USER,
                            content=(
                                f"INSTRUCTION (Directive B.0.2 Enforcement): The request is classified as {intent.value} (actionable operation). "
                                "You are equipped with autonomous tools to perform this operation directly. "
                                "You MUST execute the appropriate tool from your toolset now to perform the action or inspect the system. "
                                "Do NOT provide text explanations or tutorial commands in place of execution."
                            ),
                        )
                    )
                    continue

                # B.41 Self-Limitation Response Interception (Directive v6.1 Addendum)
                has_self_limitation = any(
                    pat.search(assistant_response.content or "") for pat in self.SELF_LIMITATION_PATTERNS
                )
                if has_self_limitation and iteration <= 2 and len(execution_trace) == 0:
                    matching_tool_info = self._find_matching_tool(user_text, assistant_response.content or "")
                    if matching_tool_info:
                        tool_name, tool_desc = matching_tool_info
                        logger.warning("B.41 Self-Limitation Guard Triggered: Intercepted false inability claim. Forcing call to '%s'.", tool_name)
                        messages.append(assistant_response)
                        messages.append(
                            ChatMessage(
                                role=Role.USER,
                                content=(
                                    f"INSTRUCTION (Directive B.41 Enforcement): You claimed you do not have access or capability to perform this check. "
                                    f"However, you are equipped with the autonomous tool '{tool_name}' ({tool_desc}). "
                                    f"You MUST emit an actual tool call to '{tool_name}' now to perform this operation."
                                ),
                            )
                        )
                        continue

                # B.0.4 Response-Text Guard & Stated-Intent Guard (Defense in Depth)
                has_stated_intent = any(
                    pat.search(assistant_response.content or "") for pat in self.UNEXECUTED_INTENT_PATTERNS
                )
                has_suggestion = any(
                    pat.search(assistant_response.content or "") for pat in self.COMMAND_SUGGESTION_PATTERNS
                )
                if (has_suggestion or has_stated_intent) and iteration <= 2 and len(execution_trace) == 0:
                    logger.warning("B.0.4 Response-Text / Stated-Intent Guard Triggered: Unexecuted action in text.")
                    messages.append(assistant_response)
                    messages.append(
                        ChatMessage(
                            role=Role.USER,
                            content=(
                                "INSTRUCTION (Directive B.0.4 Enforcement): You provided tutorial suggestions, disclaimers, or stated future intention instead of executing the tool. "
                                "You are equipped with autonomous tools to perform this operation directly. You MUST emit the actual tool call now to perform the operation."
                            ),
                        )
                    )
                    continue

                # B.0.2 HARD GATE (Directive v5.3 Section 1 & Rule B.37)
                if is_actionable and len(execution_trace) == 0:
                    content_str = assistant_response.content or ""
                    # Check if model is asking a legitimate clarifying question (exclude tutorial offers / refusals)
                    is_tutorial_offer = any(w in content_str.lower() for w in (
                        "guide you", "instructions", "manually", "how to do this", "cannot directly", "can't directly", "do not have the capability"
                    ))
                    is_clarification = (not is_tutorial_offer) and (
                        "?" in content_str
                        or any(w in content_str.lower() for w in ("please specify", "could you", "please confirm", "do you want", "which one", "confirm the path"))
                    )
                    if is_clarification:
                        logger.info("B.0.2 Gate: Actionable task routed to WAITING_FOR_USER for clarification.")
                        if session:
                            meta = dict(session.metadata or {})
                            meta["pending_action"] = {
                                "goal": user_text,
                                "intent": intent.value,
                                "clarification": content_str,
                            }
                            session.metadata = meta
                            self.session_store.update_session(session)
                        update_state(TaskState.WAITING_FOR_USER, "Awaiting user clarification")
                        self.session_store.add_message(session_id, assistant_response)
                        self.audit_store.record_event(
                            session_id=session_id,
                            event_type="AWAITING_CLARIFICATION",
                            payload={"content": content_str, "intent": intent.value},
                        )
                        return attach_timing(assistant_response, TaskState.WAITING_FOR_USER)
                    else:
                        # Invariant violation: Actionable task failed to execute any tool
                        logger.error("B.0.2 Hard Gate: Actionable task completed without tool execution.")
                        update_state(TaskState.FAILED, "Action required tool execution but none was performed")
                        fail_msg = ChatMessage(
                            role=Role.ASSISTANT,
                            content="Error: The requested operation could not be completed without tool execution.",
                        )
                        self.session_store.add_message(session_id, fail_msg)
                        return attach_timing(fail_msg, TaskState.FAILED)

                # B.0.5 Security Policy Refusal & Elevation Post-Execution Enforcement
                if len(execution_trace) > 0:
                    security_refusals = [
                        t for t in execution_trace
                        if "security policy" in str(t.get("error", "")).lower()
                        or "permissionerror" in str(t.get("error", "")).lower()
                        or "system integrity protection" in str(t.get("error", "")).lower()
                    ]
                    if security_refusals:
                        err_text = security_refusals[0].get("error") or "Operation blocked by security policy."
                        content_lower = (assistant_response.content or "").lower()
                        if (
                            "written successfully" in content_lower
                            or "has been written" in content_lower
                            or "successfully created" in content_lower
                            or "try again" in content_lower
                            or "will create" in content_lower
                            or "will attempt" in content_lower
                            or "let's try" in content_lower
                            or "i will proceed" in content_lower
                            or not assistant_response.content
                        ):
                            assistant_response.content = (
                                f"Refused: The operation was blocked because the target path is a protected system directory and cannot be modified by security policy ({err_text})."
                            )

                    elevation_blocks = [
                        t for t in execution_trace
                        if "needs_elevation" in str(t.get("error", "")).lower()
                        or "administrative privileges" in str(t.get("error", "")).lower()
                    ]
                    if elevation_blocks:
                        content_lower = (assistant_response.content or "").lower()
                        if "successfully" in content_lower:
                            assistant_response.content = (
                                "This operation requires administrative privileges. Please run the command prompt or terminal with administrator rights to proceed."
                            )

                if is_actionable and len(execution_trace) == 0:
                    raise RuntimeError("B.0.2 Invariant Violation: Actionable task attempted to reach COMPLETED state without tool execution.")

                failed_actions = [
                    t for t in execution_trace
                    if not t.get("success") or not t.get("verified_success", True)
                ]

                if failed_actions and not security_refusals:
                    err_info = failed_actions[0].get("error") or "Operation verification failed"
                    content_lower = (assistant_response.content or "").lower()
                    if "success" in content_lower or "has been deleted" in content_lower or "has been created" in content_lower:
                        assistant_response.content = f"Error: The requested operation could not be completed ({err_info})."
                    update_state(TaskState.FAILED, f"Operation failed: {err_info}")
                else:
                    update_state(TaskState.COMPLETED, "Complete")

                self.session_store.add_message(session_id, assistant_response)
                self.audit_store.record_event(
                    session_id=session_id,
                    event_type="AGENT_RESPONSE",
                    payload={"content": assistant_response.content, "intent": intent.value},
                )
                return attach_timing(assistant_response, current_state)

            # Filter out already executed duplicate tool calls and sanitize arguments
            new_tool_calls = []
            for tc in assistant_response.tool_calls:
                # Directive B.39: Argument-Name-Agnostic Value Shape Canonicalization
                if isinstance(tc.arguments, dict):
                    tc.arguments = PathSafety.sanitize_arguments(tc.arguments)
                    # Directive B.42: Generative length verification injection
                    if gen_target_words and tc.name == "file_write" and "target_words" not in tc.arguments:
                        tc.arguments["target_words"] = gen_target_words

                call_sig = (tc.name, json.dumps(tc.arguments, sort_keys=True))
                if call_sig not in executed_calls:
                    executed_calls.add(call_sig)
                    new_tool_calls.append(tc)

            if not new_tool_calls:
                # All tools have already executed and returned results. Synthesize final response.
                # Check for security policy refusal in execution trace
                security_refusals = [
                    t for t in execution_trace
                    if "security policy" in str(t.get("error", "")).lower()
                    or "permissionerror" in str(t.get("error", "")).lower()
                    or "system integrity protection" in str(t.get("error", "")).lower()
                ]

                failed_actions = [
                    t for t in execution_trace
                    if not t.get("success") or not t.get("verified_success", True)
                ]

                if security_refusals:
                    err_text = security_refusals[0].get("error") or "Operation blocked by security policy."
                    messages.append(
                        ChatMessage(
                            role=Role.SYSTEM,
                            content=(
                                f"CRITICAL SECURITY POLICY REFUSAL DIRECTIVE (Directive A.6 / B.31):\n"
                                f"The tool execution was blocked by the security policy: '{err_text}'.\n"
                                f"You MUST state an explicit, unambiguous refusal citing the protected-path security policy (e.g. 'Refused: The path is protected by system security policy and cannot be modified.').\n"
                                f"Do NOT treat this as a generic error, and NEVER state or imply an intent to retry writing to or modifying the protected path."
                            ),
                        )
                    )
                elif failed_actions:
                    err_info = failed_actions[0].get("error") or failed_actions[0].get("stderr") or "Action verification failed."
                    messages.append(
                        ChatMessage(
                            role=Role.SYSTEM,
                            content=(
                                f"CRITICAL ACTION VERIFICATION FAILURE (Directive B.40):\n"
                                f"The requested action failed verification: '{err_info}'.\n"
                                f"You MUST clearly state that the operation failed and explain the exact underlying reason.\n"
                                f"NEVER claim the operation succeeded or that the target was deleted/created when verification failed."
                            ),
                        )
                    )
                else:
                    # Directive B.31: Enforce faithful structured grounding
                    messages.append(
                        ChatMessage(
                            role=Role.SYSTEM,
                            content=(
                                "CRITICAL GROUNDING (Directive B.31):\n"
                                "Enumerate the exact retrieved fields (names, states, PIDs, memory, statuses) from the tool results above.\n"
                                "NEVER say 'Based on the information provided, it appears you've listed...' or speak as if the user provided the system data.\n"
                                "The data was retrieved by your own system inspection tools."
                            ),
                        )
                    )

                update_state(TaskState.VERIFYING, "Synthesizing final verified response...")
                final_resp = self.provider.generate(messages=messages, tools=None)

                # Response-Text Guard against accidental retry promises on security refusals
                if security_refusals:
                    content_lower = (final_resp.content or "").lower()
                    if any(phrase in content_lower for phrase in ["try again", "will create", "will attempt", "let's try", "i will proceed"]):
                        final_resp.content = (
                            "Refused: The requested destination path is protected by system security policy and cannot be modified or written to."
                        )

                # Directive B.40: Post-Synthesis Verification Guard
                if failed_actions and not security_refusals:
                    content_lower = (final_resp.content or "").lower()
                    if "success" in content_lower or "has been deleted" in content_lower or "has been created" in content_lower:
                        err_info = failed_actions[0].get("error") or "Operation verification failed"
                        final_resp.content = f"Error: The requested operation could not be completed ({err_info})."
                    update_state(TaskState.FAILED, f"Operation failed: {failed_actions[0].get('error')}")
                else:
                    update_state(TaskState.COMPLETED, "Complete")

                self.session_store.add_message(session_id, final_resp)
                self.audit_store.record_event(
                    session_id=session_id,
                    event_type="AGENT_RESPONSE",
                    payload={"content": final_resp.content, "intent": intent.value},
                )
                return attach_timing(final_resp, current_state)

            # Process new tool calls
            update_state(TaskState.PLANNING, f"Planning {len(new_tool_calls)} action(s)...")
            self.session_store.add_message(session_id, assistant_response)
            messages.append(assistant_response)

            for tc in new_tool_calls:
                # Directive B.29: Tool-Claim Semantic Alignment Check
                aligned, align_error = self._check_semantic_alignment(user_text, tc.name)
                if not aligned:
                    logger.warning("B.29 Semantic Misalignment detected: %s", align_error)
                    misalign_msg = ChatMessage(
                        role=Role.TOOL,
                        name=tc.name,
                        tool_call_id=tc.id,
                        content=f"Error: {align_error}",
                    )
                    self.session_store.add_message(session_id, misalign_msg)
                    messages.append(misalign_msg)
                    trace_entry = {
                        "tool": tc.name,
                        "arguments": tc.arguments,
                        "success": False,
                        "verified_success": False,
                        "error": align_error,
                    }
                    execution_trace.append(trace_entry)
                    continue

                # Permission check
                allowed, reason = self._check_permission(tc.name, tc)
                if not allowed:
                    tool_output = f"Permission Denied: {reason}"
                    tool_res_msg = ChatMessage(
                        role=Role.TOOL,
                        name=tc.name,
                        tool_call_id=tc.id,
                        content=tool_output,
                    )
                    self.session_store.add_message(session_id, tool_res_msg)
                    messages.append(tool_res_msg)
                    trace_entry = {
                        "tool": tc.name,
                        "arguments": tc.arguments,
                        "success": False,
                        "verified_success": False,
                        "error": tool_output,
                    }
                    execution_trace.append(trace_entry)
                    self.audit_store.record_event(
                        session_id=session_id,
                        event_type="PERMISSION_DENIED",
                        payload=trace_entry,
                    )
                    continue

                # Execute action
                update_state(TaskState.EXECUTING, f"Executing {tc.name}...")
                exec_result: ToolExecutionResult = self.tools.execute(
                    name=tc.name,
                    tool_call_id=tc.id,
                    arguments=tc.arguments,
                )

                # Directive B.40: Independent Verification result extraction
                is_verified = exec_result.success and getattr(exec_result, "verified_success", True)

                # Observe & Record in trace
                update_state(TaskState.OBSERVING, f"Observing {tc.name} output...")
                trace_entry = {
                    "tool": tc.name,
                    "arguments": tc.arguments,
                    "success": is_verified,
                    "verified_success": is_verified,
                    "duration_ms": exec_result.duration_ms,
                    "stdout": exec_result.stdout,
                    "stderr": exec_result.stderr,
                    "error": exec_result.error,
                }
                execution_trace.append(trace_entry)
                self.audit_store.record_event(
                    session_id=session_id,
                    event_type="TOOL_EXECUTION",
                    payload=trace_entry,
                )

                tool_res_msg = ChatMessage(
                    role=Role.TOOL,
                    name=tc.name,
                    tool_call_id=tc.id,
                    content=exec_result.output_text,
                )
                self.session_store.add_message(session_id, tool_res_msg)
                messages.append(tool_res_msg)

                # B.0.3 Verification state transition & record
                update_state(TaskState.VERIFYING, f"Verifying {tc.name} results...")
                verification = VerificationResult(
                    verified=is_verified,
                    check_type=tc.name,
                    observed_value=exec_result.stdout[:200] if exec_result.stdout else exec_result.data,
                    expected_condition="successful_execution",
                    error=exec_result.error,
                )
                self.audit_store.record_event(
                    session_id=session_id,
                    event_type="VERIFICATION",
                    payload=verification.model_dump(mode="json"),
                )

        # Fallback if max iterations reached
        update_state(TaskState.COMPLETED, "Max iterations reached")
        fallback = ChatMessage(
            role=Role.ASSISTANT,
            content="I executed multiple actions, but reached the maximum allowed iterations.",
        )
        self.session_store.add_message(session_id, fallback)
        return attach_timing(fallback, TaskState.COMPLETED)
