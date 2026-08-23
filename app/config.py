"""
Configuration Management for Windows AI Agent
"""

from pathlib import Path
from typing import Any, Dict, Optional
import os
import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator

# Load environment variables from .env if present
load_dotenv()

DEFAULT_STRICT_SYSTEM_PROMPT = (
    "You are the primary autonomous AI operator of a computer system.\n"
    "You are NOT merely a chatbot. You are NOT a command-explanation assistant or tutorial generator.\n"
    "Your job is to understand the user's request and ACTUALLY OPERATE THE USER'S COMPUTER using your available tools.\n\n"
    "You have two roles:\n"
    "1. Conversational AI (answering general knowledge, definitions, and concepts without tools)\n"
    "2. Autonomous Computer Operator (operating, inspecting, troubleshooting, configuring, managing the computer)\n\n"
    "1. ABSOLUTE CORE PRINCIPLE: THE USER'S COMPUTER IS YOUR OPERATING ENVIRONMENT\n"
    "When the user asks about the actual computer, you must inspect or operate the actual computer.\n"
    "The available computer tools are your source of truth. The LLM's internal knowledge is NOT the source of truth for the user's machine.\n\n"
    "2. TAXONOMY & TOOL SELECTION RULES (Directive v4 Section 2 / B.29):\n"
    "• Installed Software / Programs ('installed', 'do I have', 'what software do I have', 'software I am having')\n"
    "  -> MUST call `get_installed_software` (or `get_installed_software_tool`). NEVER use this tool to answer what is active or running.\n"
    "• Actively Running Software / Processes ('active in the computer', 'running right now', 'currently active', 'what's open', 'using CPU/memory', 'active software')\n"
    "  -> MUST call `get_process_info` (or `get_process_info_tool`). NEVER substitute with `get_installed_software`.\n"
    "• System Services / Background Daemons ('services', 'services is runing', 'windows services', 'systemd/launchd status')\n"
    "  -> MUST call `get_service_info` (or `get_service_info_tool`). NEVER substitute with generic shell execution.\n"
    "• Files & Filesystem Operations ('create file', 'make a file', 'write', 'save', 'read file', 'delete file', 'modify file')\n"
    "  -> MUST call `file_write`, `file_read`, `file_edit`, or `manage_files`. NEVER claim you cannot create files or offer manual instructions.\n"
    "• Task Manager / Resource Monitor / Activity Monitor (named reference UI)\n"
    "  -> MUST call `get_process_info` (or `get_service_info` if services mentioned) with structured resource fields. Do NOT use raw shell.\n"
    "• Network / IP Address ('my ip', 'ipv4 address', 'network info')\n"
    "  -> MUST call `get_network_info` (or `get_network_info_tool`).\n\n"
    "3. FAITHFUL STRUCTURED PRESENTATION & GROUNDING (Directive B.31):\n"
    "• Always enumerate actual returned data fields (process names, states, PIDs, memory/CPU usage, service names, statuses).\n"
    "• NEVER say 'Based on the information provided, it appears you've listed...' or speak as if the user provided the system data.\n"
    "  The data was retrieved by your own system inspection tools.\n"
    "• NEVER relabel static installed inventory as active/running processes.\n\n"
    "4. 'CHECK' / 'TELL ME' / 'FIND' / 'IS IT RUNNING' RULE\n"
    "Whenever the user says check, tell me, find, identify, inspect, verify, detect, show me, list, see whether, do I have, is it running, where is:\n"
    "AUTOMATICALLY CALL THE RELEVANT TOOL. Do not respond with instructions or command descriptions.\n\n"
    "5. 'DO THIS' ACTION RULE\n"
    "Whenever the user says install, open, create, modify, delete, move, rename, configure, run, start, stop, restart, fix, deploy, download:\n"
    "Treat this as an ACTION REQUEST. Actively perform the operation using the appropriate tools.\n\n"
    "6. UNIVERSAL EXECUTION & MULTI-STEP LOOP\n"
    "UNDERSTAND → CLASSIFY → PLAN → SELECT TOOL → PERMISSION CHECK → EXECUTE → OBSERVE → ANALYZE → VERIFY → COMPLETE.\n\n"
    "7. MANDATORY VERIFICATION & EVIDENCE\n"
    "Never declare [COMPLETED] without real evidence from verified tool results. Never assume success without checking."
)


class ProviderConfig(BaseModel):
    """LLM Provider settings with Role-Based Multi-Model Architecture (Directive v10)."""
    provider: str = Field(
        default="ollama",
        description="Active provider: 'ollama', 'gemini', 'openai', 'anthropic', or 'local'"
    )
    model: str = Field(default="llama3-groq-tool-use:8b", description="Default model identifier")
    orchestration_model: str = Field(
        default="llama3-groq-tool-use:8b",
        description="Fast model specialized for orchestration, routing, tool selection, and system operations",
    )
    content_generation_model: str = Field(
        default="qwen3:8b",
        description="High-capacity model specialized for in-depth long-form writing, document generation, and synthesis",
    )
    api_key: Optional[str] = Field(default=None, description="API key (optional for local Ollama)")
    base_url: Optional[str] = Field(default="http://localhost:11434/v1", description="Custom API endpoint")
    temperature: float = Field(default=0.2, description="Sampling temperature")
    max_tokens: int = Field(default=8192, description="Max output tokens")
    timeout_seconds: int = Field(default=180, description="Network timeout in seconds")


class SecurityConfig(BaseModel):
    """Security and permission policies."""
    auto_approve_level_0: bool = Field(default=True, description="Auto-approve read-only tools")
    auto_approve_level_1: bool = Field(default=True, description="Auto-approve low-risk tools")
    require_approval_level_2: bool = Field(default=True, description="Require prompt for level 2")
    require_approval_level_3: bool = Field(default=True, description="Require prompt for high risk")
    protected_paths: list[str] = Field(
        default_factory=lambda: [
            "C:\\Windows",
            "C:\\Windows\\System32",
            "C:\\Program Files",
            "C:\\Program Files (x86)",
        ],
        description="System directories protected from arbitrary deletion or overwrite",
    )


class StorageConfig(BaseModel):
    """Persistence settings."""
    db_path: Path = Field(
        default_factory=lambda: Path.home() / ".windows_ai_agent" / "agent.db",
        description="Path to SQLite database",
    )
    logs_dir: Path = Field(
        default_factory=lambda: Path.home() / ".windows_ai_agent" / "logs",
        description="Directory for structured log files",
    )

    @field_validator("db_path", "logs_dir", mode="before")
    @classmethod
    def expand_paths(cls, v: Any) -> Path:
        if isinstance(v, (str, Path)):
            return Path(os.path.expanduser(str(v)))
        return v


class AgentConfig(BaseModel):
    """Global Application Configuration."""
    provider: ProviderConfig = Field(default_factory=ProviderConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    system_prompt: str = Field(
        default=DEFAULT_STRICT_SYSTEM_PROMPT,
        description="System instructions for the agent",
    )

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "AgentConfig":
        """Load configuration from YAML file or environment defaults."""
        config_data: Dict[str, Any] = {}

        # 1. Try specified or default config file
        search_paths = [
            config_path,
            Path("configs/config.yaml"),
            Path.home() / ".windows_ai_agent" / "config.yaml",
        ]

        for path in search_paths:
            if path and path.is_file():
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        loaded = yaml.safe_load(f)
                        if isinstance(loaded, dict):
                            config_data.update(loaded)
                    break
                except Exception as e:
                    print(f"Warning: Failed to parse config file {path}: {e}")

        # 2. Override with environment variables
        provider_type = os.getenv("AI_PROVIDER") or config_data.get("provider", {}).get("provider")
        
        # If not explicitly specified, auto-detect based on available API keys or default to local Ollama
        if not provider_type:
            if os.getenv("GEMINI_API_KEY"):
                provider_type = "gemini"
            elif os.getenv("OPENAI_API_KEY"):
                provider_type = "openai"
            elif os.getenv("ANTHROPIC_API_KEY"):
                provider_type = "anthropic"
            else:
                provider_type = "ollama"

        provider_data = config_data.get("provider", {})
        provider_data["provider"] = provider_type

        if os.getenv("AI_MODEL"):
            provider_data["model"] = os.getenv("AI_MODEL")
        elif provider_type == "openai" and "model" not in provider_data:
            provider_data["model"] = "gpt-4o"
        elif provider_type == "anthropic" and "model" not in provider_data:
            provider_data["model"] = "claude-3-5-sonnet-20241022"
        elif provider_type == "gemini" and "model" not in provider_data:
            provider_data["model"] = "gemini-2.5-flash"
        elif provider_type in ("ollama", "local") and "model" not in provider_data:
            provider_data["model"] = "llama3-groq-tool-use:8b"

        # Role-based models (Directive v10)
        if os.getenv("ORCHESTRATION_MODEL"):
            provider_data["orchestration_model"] = os.getenv("ORCHESTRATION_MODEL")
        elif "orchestration_model" not in provider_data:
            provider_data["orchestration_model"] = provider_data.get("model", "llama3-groq-tool-use:8b")

        if os.getenv("CONTENT_GENERATION_MODEL"):
            provider_data["content_generation_model"] = os.getenv("CONTENT_GENERATION_MODEL")
        elif "content_generation_model" not in provider_data:
            if provider_type in ("ollama", "local"):
                provider_data["content_generation_model"] = "qwen2.5:14b"
            else:
                provider_data["content_generation_model"] = provider_data.get("model", "llama3-groq-tool-use:8b")

        # Resolve API keys from env
        if provider_type == "openai" and os.getenv("OPENAI_API_KEY"):
            provider_data["api_key"] = os.getenv("OPENAI_API_KEY")
        elif provider_type == "anthropic" and os.getenv("ANTHROPIC_API_KEY"):
            provider_data["api_key"] = os.getenv("ANTHROPIC_API_KEY")
        elif provider_type == "gemini" and os.getenv("GEMINI_API_KEY"):
            provider_data["api_key"] = os.getenv("GEMINI_API_KEY")
        elif provider_type in ("ollama", "local"):
            provider_data["api_key"] = "ollama"

        if os.getenv("AI_BASE_URL"):
            provider_data["base_url"] = os.getenv("AI_BASE_URL")
        elif provider_type in ("ollama", "local") and not provider_data.get("base_url"):
            provider_data["base_url"] = "http://localhost:11434/v1"

        config_data["provider"] = provider_data

        # Ensure directories exist
        instance = cls(**config_data)
        instance.storage.db_path.parent.mkdir(parents=True, exist_ok=True)
        instance.storage.logs_dir.mkdir(parents=True, exist_ok=True)

        return instance
