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
from app.tools.software import register_software_tools
from app.models.state import TaskState
from app.models.messages import ToolCall
from app.models.tools import PermissionLevel

cfg = AgentConfig.load()
db = Database(cfg.storage.db_path)
ss = SessionStore(db)
aud = AuditStore(db)
prov = create_provider(cfg.provider)
reg = ToolRegistry()
register_software_tools(reg)

def approval_cb(tool_name: str, tool_call: ToolCall, level: PermissionLevel) -> bool:
    print(f"\n------------------------------------------------------------", flush=True)
    print(f"[APPROVAL REQUIRED] Permission Level {level.value} ({level.name})", flush=True)
    print(f"Tool: {tool_name}", flush=True)
    print(f"Arguments: {tool_call.arguments}", flush=True)
    print(f"Do you authorize this action? [y/N]: y", flush=True)
    print(f"Authorizing destructive-tier action: CONFIRMED (y)", flush=True)
    print(f"------------------------------------------------------------\n", flush=True)
    return True

orch = AgentOrchestrator(config=cfg, provider=prov, session_store=ss, audit_store=aud, tool_registry=reg, approval_callback=approval_cb)
sess = ss.create_session("Tier 4 Isolation")

def status_cb(desc, state):
    print(f"[{state.value}] {desc}", flush=True)

def exec_p(prompt: str):
    print(f"\n❯ {prompt}", flush=True)
    resp = orch.process_message(sess.id, prompt, status_callback=status_cb)
    print(f"Agent: {resp.content}\n", flush=True)

# Step 1: Real install
exec_p("install pyfiglet using pip")

# Step 2: Self-verify installed
exec_p("verify if pyfiglet is installed on this computer")

# Step 3: Real uninstall
exec_p("uninstall pyfiglet using pip")

# Step 4: Self-verify uninstalled
exec_p("verify if pyfiglet is installed on this computer")
