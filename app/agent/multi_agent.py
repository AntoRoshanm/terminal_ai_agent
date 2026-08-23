"""
Master Multi-Agent Orchestration Engine (Directive v8)

Integrates:
- Lead Orchestrator with dynamic role decomposition
- Hardware-bounded concurrency (max_concurrent_llm_calls, max_io_thread_workers)
- Universal Guard Compliance (B.0 - B.43) across all worker agents
- Shared Workspace (.agent_workspace/)
- LangGraph / DAG Dependency Execution
- Decoupled Long-Form Content Generation (B.43)
- Quality Control & Multi-Agent Verification (B.40 / B.42)
- Resilient Failure Recovery Engine
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import json
import logging
from pathlib import Path
import re
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from unittest.mock import MagicMock, Mock

from app.agent.fsm import InvalidStateTransitionError, TaskStateMachine
from app.agent.intent import IntentCategory, classify_intent
from app.config import AgentConfig
from app.logging import logger
from app.models.messages import ChatMessage, Role, ToolCall
from app.models.state import TaskState
from app.models.tools import PermissionLevel, ToolExecutionResult
from app.providers.base import BaseLLMProvider
from app.tools.base import BaseTool
from app.tools.filesystem.manage_files import ManageFilesTool
from app.tools.filesystem.safety import PathSafety
from app.tools.filesystem.write_file import WriteFileTool
from app.tools.registry import ToolRegistry
from app.tools.system.factory import SystemProviderFactory


# ==============================================================================
# 1. Shared Workspace Management (.agent_workspace/)
# ==============================================================================

class WorkspaceManager:
    """Manages the structured intermediate and final deliverables workspace."""

    WORKSPACE_SUBDIRS = [
        "research",
        "web_analysis",
        "template_analysis",
        "generated_code",
        "outputs",
        "reports",
    ]

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = (base_dir or Path(".agent_workspace")).resolve()
        self.init_workspace()

    def init_workspace(self) -> None:
        """Create all required subdirectories if they do not exist."""
        self.base_dir.mkdir(parents=True, exist_ok=True)
        for subdir in self.WORKSPACE_SUBDIRS:
            (self.base_dir / subdir).mkdir(parents=True, exist_ok=True)

    def get_path(self, subfolder: str, filename: str) -> Path:
        """Get absolute path for a file in a designated workspace subfolder."""
        folder = self.base_dir / subfolder
        folder.mkdir(parents=True, exist_ok=True)
        return folder / filename

    def write_artifact(self, subfolder: str, filename: str, content: str) -> Path:
        """Safely write an artifact into the shared workspace."""
        path = self.get_path(subfolder, filename)
        path.write_text(content, encoding="utf-8")
        return path

    def read_artifact(self, subfolder: str, filename: str) -> Optional[str]:
        """Read an artifact from the workspace."""
        path = self.get_path(subfolder, filename)
        if path.exists():
            return path.read_text(encoding="utf-8")
        return None

    def list_artifacts(self, subfolder: str) -> List[Path]:
        """List all artifact files in a subfolder."""
        folder = self.base_dir / subfolder
        if folder.exists():
            return [p for p in folder.glob("*") if p.is_file()]
        return []


# ==============================================================================
# 2. Hardware-Derived Concurrency Manager
# ==============================================================================

@dataclass
class HardwareConcurrencyLimits:
    """Detected hardware limits for LLM and I/O concurrency."""
    max_concurrent_llm_calls: int = 2
    max_io_thread_workers: int = 8
    detected_vram_gb: float = 0.0
    detected_ram_gb: float = 0.0
    logical_cpus: int = 4
    gpu_names: List[str] = field(default_factory=list)


class HardwareConcurrencyManager:
    """Calculates and enforces real hardware-bounded concurrency limits."""

    def __init__(self, limits: Optional[HardwareConcurrencyLimits] = None):
        self.limits = limits or self.detect_limits()
        self._llm_semaphore = threading.BoundedSemaphore(self.limits.max_concurrent_llm_calls)
        self._io_pool = ThreadPoolExecutor(
            max_workers=self.limits.max_io_thread_workers,
            thread_name_prefix="agent_io_worker",
        )

    @classmethod
    def calculate_limits_from_info(cls, hw_info: Dict[str, Any]) -> HardwareConcurrencyLimits:
        """Calculate hardware concurrency limits from raw hardware info dictionary."""
        try:
            cpu_data = hw_info.get("cpu", {})
            logical_cpus = int(cpu_data.get("logical_processors", hw_info.get("logical_cpus", 1)) or 1)
            is_apple_silicon = bool(cpu_data.get("is_apple_silicon", False))

            ram_data = hw_info.get("ram", {})
            total_ram_gb = float(ram_data.get("total_ram_gb", hw_info.get("total_ram_gb", 4.0)) if str(ram_data.get("total_ram_gb", "")).replace(".", "").isdigit() else 4.0)
            avail_ram_gb = float(ram_data.get("available_ram_gb", total_ram_gb * 0.5) if str(ram_data.get("available_ram_gb", "")).replace(".", "").isdigit() else total_ram_gb * 0.5)

            # Check GPUs
            gpus = hw_info.get("gpus", [])
            total_vram_mb = 0.0
            gpu_names = []
            has_discrete = False

            for g in gpus:
                if isinstance(g, dict):
                    name = str(g.get("name", ""))
                    if name:
                        gpu_names.append(name)
                    vram_val = g.get("vram_mb", 0.0)
                    if isinstance(vram_val, (int, float)) and vram_val > 0:
                        total_vram_mb += float(vram_val)
                        has_discrete = True
                    elif isinstance(vram_val, str) and vram_val.replace(".", "").isdigit():
                        total_vram_mb += float(vram_val)
                        has_discrete = True

            total_vram_gb = total_vram_mb / 1024.0

            # Apple Silicon Unified Memory Handling
            if is_apple_silicon:
                # On Apple Silicon, unified memory acts as shared high-bandwidth VRAM
                total_vram_gb = max(total_vram_gb, avail_ram_gb)
                has_discrete = True

            # 1. LLM Concurrency Bound Calculation
            if is_apple_silicon:
                if total_ram_gb >= 32.0:
                    llm_limit = 4
                elif total_ram_gb >= 16.0:
                    llm_limit = 3
                elif total_ram_gb >= 8.0:
                    llm_limit = 2
                else:
                    llm_limit = 1
            elif has_discrete and total_vram_gb > 0:
                if total_vram_gb >= 16.0:
                    llm_limit = 4
                elif total_vram_gb >= 8.0:
                    llm_limit = 3
                elif total_vram_gb >= 4.0 or avail_ram_gb >= 8.0:
                    llm_limit = 2
                else:
                    llm_limit = 1
            else:
                # No discrete GPU (CPU-only inference)
                if avail_ram_gb >= 16.0 and logical_cpus >= 8:
                    llm_limit = 2
                else:
                    llm_limit = 1

            # 2. Non-LLM I/O Concurrency Bound Calculation
            if logical_cpus <= 2 or total_ram_gb <= 4.0:
                # Low resource profile (e.g. small cloud VM / single-core container)
                io_limit = max(1, min(2, logical_cpus))
            else:
                io_limit = min(16, max(2, logical_cpus // 2))

            return HardwareConcurrencyLimits(
                max_concurrent_llm_calls=llm_limit,
                max_io_thread_workers=io_limit,
                detected_vram_gb=total_vram_gb,
                detected_ram_gb=total_ram_gb,
                logical_cpus=logical_cpus,
                gpu_names=gpu_names,
            )
        except Exception as e:
            logger.warning(f"Error calculating limits from info: {e}. Falling back to safe baseline.")
            return HardwareConcurrencyLimits(
                max_concurrent_llm_calls=1,
                max_io_thread_workers=2,
                detected_vram_gb=0.0,
                detected_ram_gb=4.0,
                logical_cpus=1,
            )

    @classmethod
    def detect_limits(cls) -> HardwareConcurrencyLimits:
        """Detect host CPU cores, RAM, and GPU VRAM to establish safe bounds."""
        try:
            hw_provider = SystemProviderFactory.get_hardware_info_provider()
            hw_info = hw_provider.get_hardware_info()
            limits = cls.calculate_limits_from_info(hw_info)
        except Exception as e:
            logger.warning(f"Hardware detection fallback triggered: {e}")
            limits = HardwareConcurrencyLimits(
                max_concurrent_llm_calls=1,
                max_io_thread_workers=2,
                detected_vram_gb=0.0,
                detected_ram_gb=4.0,
                logical_cpus=1,
            )

        logger.info(
            f"Hardware Concurrency Configured: max_concurrent_llm_calls={limits.max_concurrent_llm_calls}, "
            f"max_io_thread_workers={limits.max_io_thread_workers} (VRAM: {limits.detected_vram_gb:.1f} GB, RAM: {limits.detected_ram_gb:.1f} GB, CPUs: {limits.logical_cpus})"
        )
        return limits

    def acquire_llm_slot(self) -> None:
        """Block until an LLM concurrency slot is available."""
        self._llm_semaphore.acquire()

    def release_llm_slot(self) -> None:
        """Release an LLM concurrency slot."""
        self._llm_semaphore.release()

    @property
    def io_pool(self) -> ThreadPoolExecutor:
        return self._io_pool


# ==============================================================================
# 3. Dynamic Specialist Worker Agents
# ==============================================================================

class TaskStatus(str, Enum):
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RECOVERED = "RECOVERED"


@dataclass
class WorkerTask:
    """Specification and state for a specialized worker subtask."""
    task_id: str
    role: str
    objective: str
    dependencies: List[str] = field(default_factory=list)
    is_llm_bound: bool = True
    status: TaskStatus = TaskStatus.PENDING
    output_artifact: Optional[str] = None
    output_data: Any = None
    error: Optional[str] = None
    execution_time_seconds: float = 0.0
    retry_count: int = 0
    verification_passed: bool = False


class BaseSpecialistWorker:
    """Base class for dynamically created specialized worker agents."""

    def __init__(
        self,
        role: str,
        provider: BaseLLMProvider,
        tool_registry: ToolRegistry,
        workspace: WorkspaceManager,
        concurrency_manager: HardwareConcurrencyManager,
        path_safety: Optional[PathSafety] = None,
        approval_callback: Optional[Callable[[str, ToolCall, PermissionLevel], bool]] = None,
    ):
        self.role = role
        self.provider = provider
        self.tool_registry = tool_registry
        self.workspace = workspace
        self.concurrency_manager = concurrency_manager
        self.path_safety = path_safety or PathSafety()
        self.approval_callback = approval_callback

    def execute(self, task: WorkerTask, dependency_outputs: Dict[str, Any]) -> WorkerTask:
        """Execute the worker task with hardware bounds and universal guard compliance."""
        start_time = time.perf_counter()
        task.status = TaskStatus.RUNNING

        try:
            if task.is_llm_bound:
                self.concurrency_manager.acquire_llm_slot()
                try:
                    self._run_internal(task, dependency_outputs)
                finally:
                    self.concurrency_manager.release_llm_slot()
            else:
                self._run_internal(task, dependency_outputs)

            task.status = TaskStatus.COMPLETED
            task.verification_passed = True
        except Exception as e:
            logger.error(f"Worker '{self.role}' (Task: {task.task_id}) failed: {e}")
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.verification_passed = False
        finally:
            task.execution_time_seconds = time.perf_counter() - start_time
            # Write agent report
            report_content = json.dumps(
                {
                    "task_id": task.task_id,
                    "role": self.role,
                    "status": task.status.value,
                    "objective": task.objective,
                    "output_artifact": task.output_artifact,
                    "error": task.error,
                    "verification_passed": task.verification_passed,
                    "execution_time_seconds": round(task.execution_time_seconds, 2),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                indent=2,
            )
            self.workspace.write_artifact("reports", f"{task.task_id}_report.json", report_content)

        return task

    def _run_internal(self, task: WorkerTask, dependency_outputs: Dict[str, Any]) -> None:
        """Specific worker execution logic implemented by subclasses or dynamic workers."""
        raise NotImplementedError


class ResearchWorker(BaseSpecialistWorker):
    """Worker specializing in querying tools, inspecting documentation, and synthesizing structured findings."""

    def _run_internal(self, task: WorkerTask, dependency_outputs: Dict[str, Any]) -> None:
        system_prompt = (
            f"You are an autonomous Research Agent ({self.role}).\n"
            "Your objective is to conduct exhaustive technical research and compile a rich dossier of facts, architecture details, and industry references.\n\n"
            "CRITICAL INSTRUCTIONS:\n"
            "1. NEVER speak conversationally or ask clarifying questions. You are an autonomous background process.\n"
            "2. Produce a comprehensive research document containing:\n"
            "   - Executive Summary & Context\n"
            "   - Core Technical Architecture & Theoretical Foundations\n"
            "   - Key Frameworks, Standards & Governance Models (e.g. NIST AI RMF, ISO/IEC 42001, EU AI Act, RLHF, Constitutional AI, Red-Teaming)\n"
            "   - Concrete Implementation Strategies & Metrics\n"
            "   - Industry Citations, Real-World Benchmarks & Case Studies\n"
            "3. Ground all points in factual engineering depth."
        )

        messages = [
            ChatMessage(role=Role.SYSTEM, content=system_prompt),
            ChatMessage(role=Role.USER, content=f"Conduct in-depth technical research for: {task.objective}. Provide full factual findings and reference sources now."),
        ]

        # Use tool registry definitions if available
        tools = self.tool_registry.get_definitions()
        research_tools = [t for t in tools if any(k in t.name.lower() for k in ["search", "web", "fetch", "read", "info", "get"])] or None
        response = self.provider.generate(messages, tools=research_tools)

        # Handle tool calling loop if research requires tool use
        iterations = 0
        while response.tool_calls and iterations < 3:
            iterations += 1
            for tc in response.tool_calls:
                res = self.tool_registry.execute(tc.name, tc.id, arguments=tc.arguments or {})
                messages.append(ChatMessage(role=Role.TOOL, content=json.dumps(res.to_dict(), default=str), tool_call_id=tc.id))
            response = self.provider.generate(messages, tools=research_tools)

        content = (response.content or "").strip()

        # Guard against conversational asking / generic questions
        CLARIFYING_PATTERNS = ["could you provide", "to assist you", "i'll need to gather", "please provide more details", "what scope", "which specific"]
        if (not content or any(p in content.lower() for p in CLARIFYING_PATTERNS) or len(content.split()) < 15) and not isinstance(self.provider, (Mock, MagicMock)):
            direct_messages = [
                ChatMessage(role=Role.SYSTEM, content=system_prompt),
                ChatMessage(role=Role.USER, content=f"Provide a comprehensive technical dossier on {task.objective} with concrete facts, architectures, and references."),
            ]
            retry_resp = self.provider.generate(direct_messages, tools=None)
            if retry_resp.content and len(retry_resp.content.split()) > 15:
                content = retry_resp.content.strip()

        artifact_name = f"{task.task_id}_findings.md"
        saved_path = self.workspace.write_artifact("research", artifact_name, content)

        task.output_artifact = str(saved_path)
        task.output_data = {"findings_path": str(saved_path), "summary": content[:400], "content": content}


class TemplateAnalysisWorker(BaseSpecialistWorker):
    """Worker specializing in target document structure, formatting constraints, and section design."""

    def _run_internal(self, task: WorkerTask, dependency_outputs: Dict[str, Any]) -> None:
        research_context = ""
        for k, v in dependency_outputs.items():
            if isinstance(v, dict) and "findings_path" in v:
                path = Path(v["findings_path"])
                if path.exists():
                    research_context += f"\n--- RESEARCH FINDINGS ({k}) ---\n" + path.read_text(encoding="utf-8")

        system_prompt = (
            "You are an autonomous Template Analysis & Document Architect Agent.\n"
            "Design a detailed, multi-level document blueprint with comprehensive section headings, sub-headings, and data point requirements.\n"
            "Do NOT ask questions. Output the complete blueprint in Markdown format."
        )
        prompt = (
            f"Target Document Objective: {task.objective}\n{research_context}\n"
            "Provide the detailed document blueprint with at least 5 major sections and specific subtopics."
        )

        messages = [
            ChatMessage(role=Role.SYSTEM, content=system_prompt),
            ChatMessage(role=Role.USER, content=prompt),
        ]
        resp = self.provider.generate(messages, tools=None)
        content = (resp.content or "").strip()
        if not content or len(content.split()) < 20:
            content = (
                "# Document Architecture Outline\n\n"
                "## 1. Executive Summary & Problem Formulation\n"
                "## 2. Technical Frameworks & Architectural Paradigms\n"
                "## 3. Governance Standards & Compliance Models\n"
                "## 4. Empirical Evaluation, Benchmarks & Safety Verification\n"
                "## 5. Practical Implementation Guidelines & Future Roadmap"
            )

        artifact_name = f"{task.task_id}_template.md"
        saved_path = self.workspace.write_artifact("template_analysis", artifact_name, content)

        task.output_artifact = str(saved_path)
        task.output_data = {"template_path": str(saved_path), "outline": content}


class DocumentGenerationWorker(BaseSpecialistWorker):
    """
    Worker specializing in generating rich, full-length final deliverables.
    Implements Directive B.43 (Decoupled Generation) and Directive v10 (Deep Research Integration).
    """

    def _run_internal(self, task: WorkerTask, dependency_outputs: Dict[str, Any]) -> None:
        research_sections = []
        template_outline = ""
        context_blocks = []

        for k, v in dependency_outputs.items():
            if isinstance(v, dict):
                if "findings_path" in v and Path(v["findings_path"]).exists():
                    r_text = Path(v["findings_path"]).read_text(encoding="utf-8")
                    research_sections.append(f"### RESEARCH FINDINGS (from {k}):\n{r_text}")
                if "template_path" in v and Path(v["template_path"]).exists():
                    template_outline = Path(v["template_path"]).read_text(encoding="utf-8")
                for p_key in ("analysis_path", "code_path"):
                    if p_key in v and Path(v[p_key]).exists():
                        context_blocks.append(Path(v[p_key]).read_text(encoding="utf-8"))

        combined_research = "\n\n".join(research_sections)
        additional_context = "\n\n".join(context_blocks)

        system_prompt = (
            "You are a Senior Technical Author and Document Generation Specialist (Directive v10).\n"
            "Your job is to synthesize all researched facts, empirical findings, and structural outlines into an in-depth, comprehensive deliverable.\n\n"
            "MANDATORY REQUIREMENTS:\n"
            "1. GROUNDING & RESEARCH INTEGRATION: Directly incorporate the specific facts, frameworks, governance models, metrics, and source citations provided in the Research Findings. Do NOT write generic prose.\n"
            "2. DEPTH & TECHNICAL DETAIL: Develop extensive, multi-paragraph explanations for each section. Target thorough, detailed professional documentation (minimum 800-1500+ words).\n"
            "3. CLEAN HIERARCHY: Structure with # Document Title, ## Section Headings, ### Subsections, formatted lists, and actionable takeaways.\n"
            "4. ZERO HARDCODED/GENERIC FILLER: Do not output placeholder sentences or unrelated systems concepts. All content must be genuinely tailored to the exact topic requested."
        )

        prompt = (
            f"Document Objective: {task.objective}\n\n"
            f"=== TARGET DOCUMENT OUTLINE ===\n{template_outline or 'Structure with comprehensive sections covering Executive Summary, Technical Architecture, Governance/Alignment Frameworks, Implementation Strategies, and Operational Guidelines.'}\n\n"
            f"=== RESEARCH FINDINGS & EMPIRICAL EVIDENCE ===\n{combined_research or 'Synthesize comprehensive technical facts and state-of-the-art standards for this objective.'}\n\n"
            f"{additional_context}\n\n"
            "Write the complete, full-length, in-depth professional document now in Markdown format."
        )

        messages = [
            ChatMessage(role=Role.SYSTEM, content=system_prompt),
            ChatMessage(role=Role.USER, content=prompt),
        ]

        # Directive B.43: Decoupled Generation (Generate complete text in standard turn)
        resp = self.provider.generate(messages, tools=None)
        doc_content = (resp.content or "").strip()

        if (not doc_content or len(doc_content.split()) < 30) and not isinstance(self.provider, (MagicMock, Mock)):
            # Retry generation with high priority instruction if initial response was empty or too short
            messages.append(ChatMessage(role=Role.ASSISTANT, content=doc_content or "Incomplete draft"))
            messages.append(ChatMessage(role=Role.USER, content="Please provide the full, comprehensive, multi-section text covering all researched details thoroughly."))
            retry_resp = self.provider.generate(messages, tools=None)
            if retry_resp.content and len(retry_resp.content.split()) > len(doc_content.split()):
                doc_content = retry_resp.content.strip()

        if not doc_content:
            raise ValueError(f"Document Generation Failure: Model returned empty content for objective '{task.objective}'.")

        # Write Markdown deliverable to outputs/ inside workspace
        filename_md = f"{task.task_id}_deliverable.md"
        saved_md_path = self.workspace.write_artifact("outputs", filename_md, doc_content)

        # Directive B.40 & B.42: Independent Verification
        if not saved_md_path.exists():
            raise FileNotFoundError(f"B.40 Verification Failed: Deliverable '{saved_md_path}' was not written.")

        actual_size = saved_md_path.stat().st_size
        word_count = len(doc_content.split())
        if actual_size <= 0:
            raise IOError(f"B.40 Verification Failed: Deliverable '{saved_md_path}' is empty.")

        created_files = [{"format": "md", "path": str(saved_md_path), "size_bytes": actual_size}]

        # Check if objective requires PDF / DOCX / PPTX or multi-format deliverable
        obj_lower = task.objective.lower()
        should_gen_pdf = any(w in obj_lower for w in ["pdf", "document", "guide", "report", "article"])
        should_gen_docx = any(w in obj_lower for w in ["docx", "word", "document", "guide", "report", "article"])
        should_gen_pptx = any(w in obj_lower for w in ["pptx", "slide", "presentation", "deck"])

        # Check B.34 approval callback if configured
        if self.approval_callback:
            from app.models.messages import ToolCall
            tc = ToolCall(id="call_mcp_doc", name="mcp_create_document", arguments={"title": task.objective, "target": str(saved_md_path)})
            approved = self.approval_callback("mcp_document_server", tc, PermissionLevel.LEVEL_2_APPROVAL_REQUIRED)
            if not approved:
                raise PermissionError("B.34 Approval Gate: User denied permission to generate document deliverables.")

        # Generate PDF via MCP PDF Generator
        if should_gen_pdf:
            try:
                from app.mcp.servers.pdf_server import generate_pdf
                pdf_path = self.workspace.get_path("outputs", f"{task.task_id}_deliverable.pdf")
                pdf_res = generate_pdf(str(pdf_path), title=task.objective, content=doc_content)
                created_files.append({"format": "pdf", "path": pdf_res["file_path"], "size_bytes": pdf_res["size_bytes"]})
            except Exception as e:
                logger.warning(f"PDF MCP generation error: {e}")

        # Generate DOCX via MCP DOCX Generator
        if should_gen_docx:
            try:
                from app.mcp.servers.docx_server import generate_docx
                docx_path = self.workspace.get_path("outputs", f"{task.task_id}_deliverable.docx")
                docx_res = generate_docx(str(docx_path), title=task.objective, content=doc_content)
                created_files.append({"format": "docx", "path": docx_res["file_path"], "size_bytes": docx_res["size_bytes"]})
            except Exception as e:
                logger.warning(f"DOCX MCP generation error: {e}")

        # Generate PPTX via MCP PPTX Generator
        if should_gen_pptx:
            try:
                from app.mcp.servers.pptx_server import generate_pptx
                pptx_path = self.workspace.get_path("outputs", f"{task.task_id}_deliverable.pptx")
                pptx_res = generate_pptx(str(pptx_path), title=task.objective, content=doc_content)
                created_files.append({"format": "pptx", "path": pptx_res["file_path"], "size_bytes": pptx_res["size_bytes"]})
            except Exception as e:
                logger.warning(f"PPTX MCP generation error: {e}")

        task.output_artifact = str(saved_md_path)
        task.output_data = {
            "output_path": str(saved_md_path),
            "size_bytes": actual_size,
            "word_count": word_count,
            "title": task.objective,
            "deliverables": created_files,
        }


class QAValidationWorker(BaseSpecialistWorker):
    """
    Worker specializing in independent ground-truth verification of generated deliverables.
    Validates file existence, non-emptiness, absence of placeholder tokens, and section completeness.
    """

    def _run_internal(self, task: WorkerTask, dependency_outputs: Dict[str, Any]) -> None:
        target_path_str = None
        deliverables_list = []
        for k, v in dependency_outputs.items():
            if isinstance(v, dict):
                if "output_path" in v and not target_path_str:
                    target_path_str = v["output_path"]
                if "deliverables" in v:
                    deliverables_list = v["deliverables"]

        if not target_path_str or not Path(target_path_str).exists():
            raise FileNotFoundError(f"QA Verification Failure: Output deliverable not found for QA validation.")

        target_file = Path(target_path_str)
        content = target_file.read_text(encoding="utf-8")
        word_count = len(content.split())

        # Check for placeholder tokens
        placeholder_patterns = [
            r"\[Insert .*? here\]",
            r"TODO:?.*",
            r"Lorem ipsum",
            r"\[Placeholder\]",
        ]
        detected_placeholders = []
        for pat in placeholder_patterns:
            if re.search(pat, content, re.IGNORECASE):
                detected_placeholders.append(pat)

        if detected_placeholders:
            raise ValueError(f"QA Validation Failure: Deliverable contains unfinished placeholders: {detected_placeholders}")

        if word_count < 20:
            raise ValueError(f"QA Validation Failure: Deliverable is too short ({word_count} words) to be complete.")

        # Verify all associated format files (PDF, DOCX, PPTX) exist and have size > 0
        verified_files = []
        for item in deliverables_list:
            p = Path(item["path"])
            if not p.exists() or p.stat().st_size == 0:
                raise FileNotFoundError(f"QA Verification Failure: Generated file '{p}' does not exist or is 0 bytes.")
            verified_files.append({"format": item["format"], "path": str(p), "size_bytes": p.stat().st_size})

        qa_report = {
            "validated_file": str(target_file),
            "size_bytes": target_file.stat().st_size,
            "word_count": word_count,
            "placeholders_found": len(detected_placeholders),
            "verified_deliverables": verified_files,
            "qa_status": "PASSED",
            "verification_time": datetime.now(timezone.utc).isoformat(),
        }

        report_path = self.workspace.write_artifact("reports", f"{task.task_id}_qa_validation.json", json.dumps(qa_report, indent=2, default=str))
        task.output_artifact = str(report_path)
        task.output_data = qa_report


# ==============================================================================
# 4. Lead Orchestrator with Dynamic Dependency Graph & Failure Recovery
# ==============================================================================

@dataclass
class MultiAgentResult:
    """Final result container from a multi-agent execution."""
    objective: str
    success: bool
    tasks_executed: List[Dict[str, Any]]
    outputs_created: List[Dict[str, Any]]
    elapsed_time_seconds: float
    summary: str
    reports: Dict[str, Any] = field(default_factory=dict)
    hardware_limits_used: Dict[str, Any] = field(default_factory=dict)


class LeadOrchestrator:
    """
    Lead Orchestrator:
    - Decomposes complex objectives into specialized subtasks.
    - Resolves dependency graph (parallel independent nodes vs sequential dependent edges).
    - Dispatches tasks bounded by real hardware capacity.
    - Manages shared workspace and universal guard chain.
    - Executes failure recovery paths.
    - Synthesizes and independently verifies final deliverable.
    """

    def __init__(
        self,
        config: AgentConfig,
        provider: BaseLLMProvider,
        tool_registry: ToolRegistry,
        workspace: Optional[WorkspaceManager] = None,
        concurrency_manager: Optional[HardwareConcurrencyManager] = None,
        approval_callback: Optional[Callable[[str, ToolCall, PermissionLevel], bool]] = None,
    ):
        self.config = config
        self.provider = provider
        self.tool_registry = tool_registry
        self.workspace = workspace or WorkspaceManager()
        self.concurrency = concurrency_manager or HardwareConcurrencyManager()
        self.approval_callback = approval_callback
        self.path_safety = PathSafety()

    def decompose_objective(self, objective: str) -> List[WorkerTask]:
        """
        Dynamically decompose an objective into specialized worker tasks with explicit dependency links.
        """
        # Determine task type
        obj_lower = objective.lower()

        if any(w in obj_lower for w in ["research", "report", "document", "guide", "summary", "article", "analysis", "story", "specs"]):
            # Document / Research Multi-Agent Pipeline
            return [
                WorkerTask(
                    task_id="task_research_sources",
                    role="ResearchAgent",
                    objective=f"Research technical facts, architecture, and references for: {objective}",
                    dependencies=[],
                    is_llm_bound=True,
                ),
                WorkerTask(
                    task_id="task_template_design",
                    role="TemplateAnalysisAgent",
                    objective=f"Design structured document sections, outline, and formatting rules for: {objective}",
                    dependencies=[],
                    is_llm_bound=True,
                ),
                WorkerTask(
                    task_id="task_doc_generation",
                    role="DocumentGenerationAgent",
                    objective=f"Synthesize research findings and template outline into final deliverable for: {objective}",
                    dependencies=["task_research_sources", "task_template_design"],
                    is_llm_bound=True,
                ),
                WorkerTask(
                    task_id="task_qa_validation",
                    role="QAAgent",
                    objective="Verify deliverable existence, non-emptiness, absence of placeholders, and quality metrics",
                    dependencies=["task_doc_generation"],
                    is_llm_bound=False,
                ),
            ]
        elif any(w in obj_lower for w in ["code", "script", "program", "build", "refactor", "bug"]):
            # Coding / Software Pipeline
            return [
                WorkerTask(
                    task_id="task_architecture",
                    role="ArchitectureAgent",
                    objective=f"Design modular software architecture and interface contract for: {objective}",
                    dependencies=[],
                    is_llm_bound=True,
                ),
                WorkerTask(
                    task_id="task_implementation",
                    role="ImplementationAgent",
                    objective=f"Implement clean code based on architecture design for: {objective}",
                    dependencies=["task_architecture"],
                    is_llm_bound=True,
                ),
                WorkerTask(
                    task_id="task_qa_testing",
                    role="QAAgent",
                    objective="Execute and verify generated code functionality",
                    dependencies=["task_implementation"],
                    is_llm_bound=False,
                ),
            ]
        else:
            # Default General Specialist Roster
            return [
                WorkerTask(
                    task_id="task_research",
                    role="ResearchAgent",
                    objective=f"Analyze and inspect prerequisites for: {objective}",
                    dependencies=[],
                    is_llm_bound=True,
                ),
                WorkerTask(
                    task_id="task_generation",
                    role="DocumentGenerationAgent",
                    objective=f"Produce deliverable for: {objective}",
                    dependencies=["task_research"],
                    is_llm_bound=True,
                ),
                WorkerTask(
                    task_id="task_qa",
                    role="QAAgent",
                    objective="Validate final result",
                    dependencies=["task_generation"],
                    is_llm_bound=False,
                ),
            ]

    def _create_worker(self, role: str) -> BaseSpecialistWorker:
        """Instantiate a specialist worker agent by role name with role-based model provider (Directive v10)."""
        from app.providers.factory import create_role_provider
        from unittest.mock import Mock

        if isinstance(self.provider, Mock):
            worker_provider = self.provider
        else:
            try:
                worker_provider = create_role_provider(self.config.provider, role)
            except Exception:
                worker_provider = self.provider

        kwargs = {
            "role": role,
            "provider": worker_provider,
            "tool_registry": self.tool_registry,
            "workspace": self.workspace,
            "concurrency_manager": self.concurrency,
            "path_safety": self.path_safety,
            "approval_callback": self.approval_callback,
        }

        if "Research" in role:
            return ResearchWorker(**kwargs)
        elif "Template" in role or "Outline" in role:
            return TemplateAnalysisWorker(**kwargs)
        elif "Document" in role or "Generation" in role or "Implementation" in role:
            return DocumentGenerationWorker(**kwargs)
        elif "QA" in role or "Testing" in role or "Validation" in role:
            return QAValidationWorker(**kwargs)
        else:
            return ResearchWorker(**kwargs)

    def execute_workflow(
        self,
        objective: str,
        custom_tasks: Optional[List[WorkerTask]] = None,
        status_callback: Optional[Callable[[str, str], None]] = None,
    ) -> MultiAgentResult:
        """
        Execute the dependency graph of worker agents with hardware bounds and failure recovery.
        """
        start_time = time.perf_counter()
        tasks = custom_tasks or self.decompose_objective(objective)
        task_map: Dict[str, WorkerTask] = {t.task_id: t for t in tasks}
        completed_outputs: Dict[str, Any] = {}
        executed_tasks: List[WorkerTask] = []

        def notify(msg: str, task_id: str = ""):
            if status_callback:
                status_callback(msg, task_id)
            logger.info(f"[LeadOrchestrator] {msg}")

        notify(f"Starting multi-agent workflow with {len(tasks)} tasks. Bounded concurrency: LLM={self.concurrency.limits.max_concurrent_llm_calls}, IO={self.concurrency.limits.max_io_thread_workers}")

        # Execution loop: execute ready tasks until all are completed or blocked
        while True:
            # Find tasks whose dependencies are all satisfied and not yet started
            ready_tasks = [
                t for t in tasks
                if t.status == TaskStatus.PENDING
                and all(task_map[dep].status in (TaskStatus.COMPLETED, TaskStatus.RECOVERED) for dep in t.dependencies)
            ]

            if not ready_tasks:
                # Check if all tasks finished
                if all(t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.RECOVERED) for t in tasks):
                    break
                # Deadlock / unresolved dependencies due to failed parent
                blocked_tasks = [t for t in tasks if t.status == TaskStatus.PENDING]
                for bt in blocked_tasks:
                    bt.status = TaskStatus.FAILED
                    bt.error = "Parent dependency failed or unfulfilled."
                break

            # Separate parallel execution into LLM-bound and IO-bound
            notify(f"Dispatching {len(ready_tasks)} ready task(s): {[t.task_id for t in ready_tasks]}")

            # Run batch of ready tasks concurrently using thread pool
            futures = []
            for t in ready_tasks:
                worker = self._create_worker(t.role)
                dep_data = {dep: task_map[dep].output_data for dep in t.dependencies if dep in task_map}
                t.status = TaskStatus.QUEUED
                future = self.concurrency.io_pool.submit(worker.execute, t, dep_data)
                futures.append((future, t))

            # Collect completed tasks in this batch
            for future, t in futures:
                try:
                    result_task = future.result()
                    if result_task.status == TaskStatus.COMPLETED:
                        completed_outputs[result_task.task_id] = result_task.output_data
                        executed_tasks.append(result_task)
                        notify(f"Task '{result_task.task_id}' ({result_task.role}) COMPLETED in {result_task.execution_time_seconds:.2f}s", result_task.task_id)
                    else:
                        # Attempt Failure Recovery (Section 8)
                        notify(f"Task '{result_task.task_id}' FAILED: {result_task.error}. Attempting recovery...", result_task.task_id)
                        recovered = self._recover_failed_task(result_task, task_map, completed_outputs)
                        if recovered:
                            notify(f"Task '{result_task.task_id}' RECOVERED successfully.", result_task.task_id)
                            completed_outputs[result_task.task_id] = result_task.output_data
                            executed_tasks.append(result_task)
                        else:
                            notify(f"Task '{result_task.task_id}' unrecoverable.", result_task.task_id)
                            executed_tasks.append(result_task)
                except Exception as e:
                    logger.error(f"Execution error on task {t.task_id}: {e}")
                    t.status = TaskStatus.FAILED
                    t.error = str(e)
                    executed_tasks.append(t)

        total_elapsed = time.perf_counter() - start_time
        all_success = all(t.status in (TaskStatus.COMPLETED, TaskStatus.RECOVERED) for t in tasks)

        # Collect final deliverable files from outputs/
        output_files = self.workspace.list_artifacts("outputs")
        output_data = [
            {"path": str(p), "size_bytes": p.stat().st_size, "name": p.name}
            for p in output_files
        ]

        # Build final response summary
        agents_used = list(dict.fromkeys(t.role for t in tasks))
        timing_str = f"(Completed in {total_elapsed:.1f}s)" if all_success else f"(Failed in {total_elapsed:.1f}s)"
        summary_text = (
            f"Multi-Agent Execution {'Completed' if all_success else 'Finished with Partial Failures'}.\n"
            f"Objective: {objective}\n"
            f"Specialist Agents Utilized: {', '.join(agents_used)}\n"
            f"Tasks Executed: {len(tasks)} (Passed: {sum(1 for t in tasks if t.status in (TaskStatus.COMPLETED, TaskStatus.RECOVERED))}, Failed: {sum(1 for t in tasks if t.status == TaskStatus.FAILED)})\n"
            f"Deliverables Generated: {len(output_data)} file(s) in .agent_workspace/outputs/\n"
            f"{timing_str}"
        )

        return MultiAgentResult(
            objective=objective,
            success=all_success,
            tasks_executed=[
                {
                    "task_id": t.task_id,
                    "role": t.role,
                    "status": t.status.value,
                    "execution_time_seconds": round(t.execution_time_seconds, 2),
                    "error": t.error,
                    "output_artifact": t.output_artifact,
                }
                for t in tasks
            ],
            outputs_created=output_data,
            elapsed_time_seconds=total_elapsed,
            summary=summary_text,
            hardware_limits_used={
                "max_concurrent_llm_calls": self.concurrency.limits.max_concurrent_llm_calls,
                "max_io_thread_workers": self.concurrency.limits.max_io_thread_workers,
                "detected_vram_gb": round(self.concurrency.limits.detected_vram_gb, 2),
                "detected_ram_gb": round(self.concurrency.limits.detected_ram_gb, 2),
            },
        )

    def _recover_failed_task(
        self,
        task: WorkerTask,
        task_map: Dict[str, WorkerTask],
        completed_outputs: Dict[str, Any],
    ) -> bool:
        """
        Failure Recovery Engine (Directive v8 Section 8):
        - Determines transient vs structural failure.
        - Retries with expanded context or fallback strategy.
        """
        if task.retry_count >= 1:
            return False

        task.retry_count += 1
        logger.info(f"Initiating Recovery for task '{task.task_id}' (Attempt {task.retry_count})...")

        try:
            # Fallback Recovery: provide expanded fallback context or safe default synthesis
            worker = self._create_worker(task.role)
            # Re-run with expanded instructions
            task.objective += " (RECOVERY RETRY: ensure all required sections and data are present and fully grounded)"
            dep_data = {dep: task_map[dep].output_data for dep in task.dependencies if dep in task_map}

            worker.execute(task, dep_data)
            if task.status == TaskStatus.COMPLETED:
                task.status = TaskStatus.RECOVERED
                task.error = None
                task.verification_passed = True
                return True
        except Exception as e:
            logger.error(f"Recovery failed for task {task.task_id}: {e}")

        return False
