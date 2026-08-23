"""
State, Platform, and Lifecycle Data Models
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
import uuid
from pydantic import BaseModel, Field


class IntentCategory(str, Enum):
    """Discrete request classification taxonomy according to Master Directive B.12."""
    NORMAL_CHAT = "NORMAL_CHAT"
    LOCAL_INFORMATION = "LOCAL_INFORMATION"
    LOCAL_ACTION = "LOCAL_ACTION"
    TROUBLESHOOTING = "TROUBLESHOOTING"
    WEB_INFORMATION = "WEB_INFORMATION"
    WEB_RESEARCH = "WEB_RESEARCH"
    MULTI_TOOL = "MULTI_TOOL"


class VerificationResult(BaseModel):
    """Observed post-condition verification record."""
    verified: bool
    check_type: str
    observed_value: Any = None
    expected_condition: str = ""
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PlatformInfo(BaseModel):
    """Cached platform identification metadata and hardware capacity metrics."""
    os_family: Literal["windows", "linux", "macos"]
    os_name: str
    os_version: str
    kernel_version: Optional[str] = None
    architecture: str
    is_apple_silicon: Optional[bool] = None
    is_rosetta_translated: Optional[bool] = None
    shell_default: str
    package_managers: List[str] = Field(default_factory=list)
    display_server: Optional[str] = None
    sip_enabled: Optional[bool] = None
    is_admin_or_root: bool = False
    is_wsl: bool = False
    logical_cpus: int = 1
    total_ram_gb: float = 0.0
    available_ram_gb: float = 0.0
    total_vram_gb: float = 0.0
    has_discrete_gpu: bool = False
    max_concurrent_llm_calls: int = 1
    max_io_thread_workers: int = 2


class TaskState(str, Enum):
    """Lifecycle states for a task according to the blueprint."""
    NEW = "NEW"
    UNDERSTANDING = "UNDERSTANDING"
    PLANNING = "PLANNING"
    WAITING_FOR_USER = "WAITING_FOR_USER"
    EXECUTING = "EXECUTING"
    OBSERVING = "OBSERVING"
    VERIFYING = "VERIFYING"
    RECOVERING = "RECOVERING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class TaskStep(BaseModel):
    """An individual step in a generated task plan."""
    id: str = Field(default_factory=lambda: f"step_{uuid.uuid4().hex[:6]}")
    step_number: int
    description: str
    tool_name: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    state: TaskState = TaskState.NEW
    result: Optional[str] = None
    verification_rule: Optional[str] = None
    verified: bool = False
    error: Optional[str] = None


class TaskExecutionRecord(BaseModel):
    """Record of a task's full plan and execution history."""
    id: str = Field(default_factory=lambda: f"task_{uuid.uuid4().hex[:8]}")
    session_id: str
    goal: str
    intent: IntentCategory = IntentCategory.NORMAL_CHAT
    state: TaskState = TaskState.NEW
    steps: List[TaskStep] = Field(default_factory=list)
    current_step_index: int = 0
    verification_results: List[VerificationResult] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    error_summary: Optional[str] = None


class ExecutionState(BaseModel):
    """Runtime active execution state for the agent orchestrator."""
    session_id: str
    active_task: Optional[TaskExecutionRecord] = None
    current_state: TaskState = TaskState.NEW
    intent: IntentCategory = IntentCategory.NORMAL_CHAT
    execution_trace: List[Dict[str, Any]] = Field(default_factory=list)
    verification_result: Optional[VerificationResult] = None
    waiting_reason: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Session(BaseModel):
    """A conversational session record."""
    id: str = Field(default_factory=lambda: f"session_{uuid.uuid4().hex[:8]}")
    title: str = "New Session"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    message_count: int = 0
    active_task_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
