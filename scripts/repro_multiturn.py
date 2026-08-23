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

sess = ss.create_session("Multi-turn Repro")

def status_cb(desc, state):
    print(f"[{state.value}] {desc}", flush=True)

print("--- STEP 1 ---", flush=True)
orch.process_message(sess.id, "show me how much ram memory is free right now", status_callback=status_cb)

print("\n--- STEP 2 ---", flush=True)
orch.process_message(sess.id, "clean up my system", status_callback=status_cb)

print("\n--- STEP 3 ---", flush=True)
orch.process_message(sess.id, "can you help me check if python is installed", status_callback=status_cb)

print("\n--- STEP 4 ---", flush=True)
r4 = orch.process_message(sess.id, "create a file test_log.txt on Desktop with 'test 123'", status_callback=status_cb)
print("Turn 4 Content:", r4.content, flush=True)

# Also test the prior phrasing
print("\n--- STEP 5 (Prior working phrase) ---", flush=True)
r5 = orch.process_message(sess.id, 'create a file called testing.txt on Desktop with the text "hello world"', status_callback=status_cb)
print("Turn 5 Content:", r5.content, flush=True)
