import sys
from pathlib import Path
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parent.parent))

import ctypes
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

is_admin = bool(ctypes.windll.shell32.IsUserAnAdmin())
print(f"Process Admin Elevation: {is_admin}", flush=True)

cfg = AgentConfig.load()
db = Database(cfg.storage.db_path)
ss = SessionStore(db)
aud = AuditStore(db)
prov = create_provider(cfg.provider)
reg = ToolRegistry()
register_windows_tools(reg)

def approval_cb(tool_name: str, tool_call: ToolCall, level: PermissionLevel) -> bool:
    print(f"\n[APPROVAL REQUIRED] Tool: {tool_name} | Args: {tool_call.arguments} -> Confirmed (y)", flush=True)
    return True

orch = AgentOrchestrator(
    config=cfg,
    provider=prov,
    session_store=ss,
    audit_store=aud,
    tool_registry=reg,
    approval_callback=approval_cb,
)

sess = ss.create_session("Tier 3 Elevated Agent Live Run")

def status_cb(desc, state):
    print(f"[{state.value}] {desc}", flush=True)

def run_prompt(prompt: str):
    print(f"\n❯ {prompt}", flush=True)
    resp = orch.process_message(sess.id, prompt, status_callback=status_cb)
    print(f"Agent: {resp.content}\n", flush=True)

# 1. Status Before
run_prompt("what's the status of the Print Spooler service")

# 2. Restart Service
run_prompt("restart the print spooler service")

# 3. Status After
run_prompt("what's the status of the Print Spooler service")
