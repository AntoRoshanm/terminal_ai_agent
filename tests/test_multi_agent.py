"""
Unit Tests for Master Multi-Agent Orchestration Engine (Directive v8)
"""

from pathlib import Path
import pytest
from unittest.mock import MagicMock

from app.agent.multi_agent import (
    DocumentGenerationWorker,
    HardwareConcurrencyLimits,
    HardwareConcurrencyManager,
    LeadOrchestrator,
    MultiAgentResult,
    QAValidationWorker,
    ResearchWorker,
    TaskStatus,
    TemplateAnalysisWorker,
    WorkerTask,
    WorkspaceManager,
)
from app.config import AgentConfig
from app.models.messages import ChatMessage, Role
from app.tools.filesystem.write_file import WriteFileTool
from app.tools.registry import ToolRegistry


def test_workspace_initialization_and_artifacts(tmp_path):
    """Verify shared workspace directory structure and artifact read/write."""
    ws = WorkspaceManager(base_dir=tmp_path / "test_workspace")
    for subdir in ["research", "web_analysis", "template_analysis", "generated_code", "outputs", "reports"]:
        assert (ws.base_dir / subdir).is_dir()

    # Write and read artifact
    saved = ws.write_artifact("research", "findings_1.md", "# Findings\nKey facts here.")
    assert saved.exists()
    content = ws.read_artifact("research", "findings_1.md")
    assert content == "# Findings\nKey facts here."

    artifacts = ws.list_artifacts("research")
    assert len(artifacts) == 1
    assert artifacts[0].name == "findings_1.md"


def test_hardware_concurrency_manager_bounds():
    """Verify hardware limits calculation and concurrency controls."""
    limits = HardwareConcurrencyLimits(
        max_concurrent_llm_calls=2,
        max_io_thread_workers=6,
        detected_vram_gb=4.0,
        detected_ram_gb=16.0,
        logical_cpus=12,
    )
    cm = HardwareConcurrencyManager(limits=limits)
    assert cm.limits.max_concurrent_llm_calls == 2
    assert cm.limits.max_io_thread_workers == 6

    # Test semaphore acquire & release
    cm.acquire_llm_slot()
    cm.acquire_llm_slot()
    cm.release_llm_slot()
    cm.release_llm_slot()


def test_dynamic_role_decomposition():
    """Verify dynamic task decomposition into specialist worker roles with dependency graph."""
    cfg = AgentConfig()
    mock_prov = MagicMock()
    reg = ToolRegistry()
    orch = LeadOrchestrator(config=cfg, provider=mock_prov, tool_registry=reg)

    # 1. Research / Document goal
    tasks_doc = orch.decompose_objective("Research and generate technical report on quantum computing algorithms")
    assert len(tasks_doc) >= 4
    roles = [t.role for t in tasks_doc]
    assert "ResearchAgent" in roles
    assert "TemplateAnalysisAgent" in roles
    assert "DocumentGenerationAgent" in roles
    assert "QAAgent" in roles

    # Assert dependency structure
    doc_gen_task = next(t for t in tasks_doc if t.role == "DocumentGenerationAgent")
    assert "task_research_sources" in doc_gen_task.dependencies
    assert "task_template_design" in doc_gen_task.dependencies

    qa_task = next(t for t in tasks_doc if t.role == "QAAgent")
    assert "task_doc_generation" in qa_task.dependencies

    # 2. Coding goal
    tasks_code = orch.decompose_objective("Build and test a python REST API for user authentication")
    roles_code = [t.role for t in tasks_code]
    assert "ArchitectureAgent" in roles_code
    assert "ImplementationAgent" in roles_code
    assert "QAAgent" in roles_code


def test_multi_agent_execution_workflow_and_b43_decoupled(tmp_path):
    """Verify end-to-end multi-agent execution pipeline with B.43 decoupled generation and B.40 QA verification."""
    ws = WorkspaceManager(base_dir=tmp_path / "agent_ws")
    cm = HardwareConcurrencyManager(limits=HardwareConcurrencyLimits(max_concurrent_llm_calls=2, max_io_thread_workers=4))
    reg = ToolRegistry()
    reg.register(WriteFileTool())

    mock_prov = MagicMock()
    # Return realistic mock responses for Research, Template, and Document Generation
    mock_prov.generate.side_effect = [
        ChatMessage(role=Role.ASSISTANT, content="# Research Findings\n- Point A: Quantum supremacy verified.\n- Point B: Qubits coherence."),
        ChatMessage(role=Role.ASSISTANT, content="# Outline\n## 1. Executive Summary\n## 2. Technical Architecture\n## 3. Results"),
        ChatMessage(role=Role.ASSISTANT, content="# Quantum Computing Technical Report\n\n## 1. Executive Summary\nQuantum computing leverages superposition and entanglement to execute complex computations exponentially faster than classical computers.\n\n## 2. Technical Architecture\nSuperconducting qubits maintain coherence at cryogenic temperatures.\n\n## 3. Results\nBenchmarking results demonstrate significant throughput gains."),
    ]

    cfg = AgentConfig()
    orch = LeadOrchestrator(
        config=cfg,
        provider=mock_prov,
        tool_registry=reg,
        workspace=ws,
        concurrency_manager=cm,
    )

    result = orch.execute_workflow("Generate technical report on Quantum Computing")

    assert result.success is True
    assert len(result.tasks_executed) == 4
    assert len(result.outputs_created) >= 1
    assert "Completed in" in result.summary

    # Assert deliverable was written to outputs/ and verified
    output_file = ws.base_dir / "outputs" / "task_doc_generation_deliverable.md"
    assert output_file.exists()
    content = output_file.read_text(encoding="utf-8")
    assert "Quantum Computing Technical Report" in content
    assert len(content.split()) > 25

    # Assert QA report was written to reports/
    qa_report = ws.base_dir / "reports" / "task_qa_validation_qa_validation.json"
    assert qa_report.exists()


def test_multi_agent_failure_recovery(tmp_path):
    """Verify resilient failure recovery path when a worker encounters an error."""
    ws = WorkspaceManager(base_dir=tmp_path / "recovery_ws")
    cm = HardwareConcurrencyManager(limits=HardwareConcurrencyLimits(max_concurrent_llm_calls=2, max_io_thread_workers=4))
    reg = ToolRegistry()

    mock_prov = MagicMock()
    # First call fails (simulating transient LLM error), second call (recovery retry) succeeds
    mock_prov.generate.side_effect = [
        Exception("Temporary API timeout during generation"),
        ChatMessage(role=Role.ASSISTANT, content="# Recovered Findings\nKey facts collected after retry with comprehensive research data."),
        ChatMessage(role=Role.ASSISTANT, content="# Outline\n## 1. Overview\n## 2. Details\n## 3. Conclusion"),
        ChatMessage(role=Role.ASSISTANT, content="# Final Deliverable: AI Safety Mechanisms\n\n## 1. Overview\nAI safety mechanisms provide robust alignment, input validation, and execution guardrails.\n\n## 2. Details\nMulti-layered defense-in-depth ensures resilient execution across distributed systems.\n\n## 3. Conclusion\nContinuous verification maintains safe operation."),
    ]

    cfg = AgentConfig()
    orch = LeadOrchestrator(
        config=cfg,
        provider=mock_prov,
        tool_registry=reg,
        workspace=ws,
        concurrency_manager=cm,
    )

    result = orch.execute_workflow("Research and summarize AI safety mechanisms")

    assert result.success is True
    # The recovered task must have status RECOVERED
    research_task_record = next(t for t in result.tasks_executed if t["role"] == "ResearchAgent")
    assert research_task_record["status"] == TaskStatus.RECOVERED.value
