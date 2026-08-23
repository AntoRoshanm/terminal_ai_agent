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

sess = ss.create_session("Pending Context Multi-Turn Test")

def status_cb(desc, state):
    print(f"[{state.value}] {desc}", flush=True)

# Turn 1: Multi-step prompt that triggers clarification
print("\n--- TURN 1 ---", flush=True)
p1 = "make a file named notes.txt on my Desktop with 'meeting at 3pm' and then read it back"
print(f"❯ {p1}", flush=True)
r1 = orch.process_message(sess.id, p1, status_callback=status_cb)
print(f"Agent: {r1.content}\n", flush=True)

# Turn 2: User gives bare confirmation 'yes'
print("\n--- TURN 2 (Confirmation) ---", flush=True)
p2 = "yes"
print(f"❯ {p2}", flush=True)
r2 = orch.process_message(sess.id, p2, status_callback=status_cb)
print(f"Agent: {r2.content}\n", flush=True)

# Verify Desktop\notes.txt
desktop_notes = Path.home() / "Desktop" / "notes.txt"
if desktop_notes.exists():
    print(f"[GROUND TRUTH] {desktop_notes} exists with content: {desktop_notes.read_text().strip()}", flush=True)
    desktop_notes.unlink()
    print(f"[GROUND TRUTH] Cleaned up {desktop_notes}", flush=True)
else:
    print(f"[GROUND TRUTH] {desktop_notes} does not exist", flush=True)
