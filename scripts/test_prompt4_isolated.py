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

sess = ss.create_session("Isolated Prompt 4 Test")

def status_cb(desc, state):
    print(f"[{state.value}] {desc}", flush=True)

prompt = "create a file test_log.txt on Desktop with 'test 123'"
print(f"\n❯ {prompt}", flush=True)
resp = orch.process_message(sess.id, prompt, status_callback=status_cb)
print(f"Agent: {resp.content}\n", flush=True)

# Ground truth check
f = Path.home() / "Desktop" / "test_log.txt"
if f.exists():
    print(f"[GROUND TRUTH] {f} exists with content: {f.read_text().strip()}", flush=True)
    f.unlink()
    print(f"[GROUND TRUTH] Cleaned up {f}", flush=True)
else:
    print(f"[GROUND TRUTH] {f} does not exist", flush=True)
