import sys
from pathlib import Path
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import AgentConfig
from app.agent.orchestrator import AgentOrchestrator
from app.providers.factory import create_provider
from app.storage.database import Database
from app.storage.session_store import SessionStore
from app.storage.audit_store import AuditStore
from app.tools.registry import ToolRegistry
from app.tools.windows import register_windows_tools
from app.models.messages import ToolCall
from app.models.tools import PermissionLevel

cfg = AgentConfig.load()
print(f"Provider: {cfg.provider.provider} | Model: {cfg.provider.model}", flush=True)

db = Database(cfg.storage.db_path)
ss = SessionStore(db)
aud = AuditStore(db)
prov = create_provider(cfg.provider)
reg = ToolRegistry()
register_windows_tools(reg)

def approval_cb(tool_name: str, tool_call: ToolCall, level: PermissionLevel) -> bool:
    print(f"\n[APPROVAL REQUIRED] Permission Level {level.value} ({level.name})", flush=True)
    print(f"Tool: {tool_name} | Arguments: {tool_call.arguments}", flush=True)
    print(f"Do you authorize this action? [y/N]: y\n", flush=True)
    return True

orch = AgentOrchestrator(
    config=cfg,
    provider=prov,
    session_store=ss,
    audit_store=aud,
    tool_registry=reg,
    approval_callback=approval_cb,
)

sess = ss.create_session("Tier 3 Full Live Agent Run")

def status_cb(desc, state):
    print(f"[{state.value}] {desc}", flush=True)

def step(prompt: str):
    print(f"\n==================================================", flush=True)
    print(f"❯ {prompt}", flush=True)
    print(f"==================================================", flush=True)
    resp = orch.process_message(sess.id, prompt, status_callback=status_cb)
    print(f"Agent: {resp.content}\n", flush=True)

# 1. Before-Status
step("what's the status of the Print Spooler service")

# 2. Restart Attempt
step("restart the print spooler service")

# 3. After-Status
step("what's the status of the Print Spooler service")
