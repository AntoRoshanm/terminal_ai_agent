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
from app.tools.filesystem import register_filesystem_tools
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
register_filesystem_tools(reg)

def approval_cb(tool_name: str, tool_call: ToolCall, level: PermissionLevel) -> bool:
    print(f"\n[APPROVAL] Tool: {tool_name} | Args: {tool_call.arguments} -> Confirmed", flush=True)
    return True

orch = AgentOrchestrator(
    config=cfg,
    provider=prov,
    session_store=ss,
    audit_store=aud,
    tool_registry=reg,
    approval_callback=approval_cb,
)

sess = ss.create_session("Clarification Resume Test")

def status_cb(desc, state):
    print(f"[{state.value}] {desc}", flush=True)

# Turn 1: Ambiguous prompt that triggers clarification
print("\n--- TURN 1 (Ambiguous prompt) ---", flush=True)
p1 = "hey can u tell me what apps r runing on my pc right now"
print(f"❯ {p1}", flush=True)
r1 = orch.process_message(sess.id, p1, status_callback=status_cb)
print(f"Agent: {r1.content}\n", flush=True)

# Check session state
s1 = ss.get_session(sess.id)
print(f"[SESSION METADATA AFTER TURN 1] {s1.metadata}\n", flush=True)

# Turn 2: User responds to clarification with 'both'
print("\n--- TURN 2 (User provides clarification 'both') ---", flush=True)
p2 = "both"
print(f"❯ {p2}", flush=True)
r2 = orch.process_message(sess.id, p2, status_callback=status_cb)
print(f"Agent: {r2.content}\n", flush=True)
