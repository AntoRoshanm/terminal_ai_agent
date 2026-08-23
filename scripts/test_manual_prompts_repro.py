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
from app.tools.filesystem import register_filesystem_tools
from app.models.messages import ToolCall
from app.models.tools import PermissionLevel

cfg = AgentConfig.load()
print(f"Loaded Provider: {cfg.provider.provider} | Model: {cfg.provider.model}")

db = Database(cfg.storage.db_path)
ss = SessionStore(db)
aud = AuditStore(db)
prov = create_provider(cfg.provider)
reg = ToolRegistry()
register_filesystem_tools(reg)

def approval_cb(tool_name: str, tool_call: ToolCall, level: PermissionLevel) -> bool:
    print(f"\n------------------------------------------------------------", flush=True)
    print(f"[APPROVAL REQUIRED] Permission Level {level.value} ({level.name})", flush=True)
    print(f"Tool: {tool_name}", flush=True)
    print(f"Arguments: {tool_call.arguments}", flush=True)
    print(f"Do you authorize this action? [y/N]: y", flush=True)
    print(f"------------------------------------------------------------\n", flush=True)
    return True

orch = AgentOrchestrator(
    config=cfg,
    provider=prov,
    session_store=ss,
    audit_store=aud,
    tool_registry=reg,
    approval_callback=approval_cb,
)

sess = ss.create_session("Manual Prompt Reproduction Test")

def status_cb(desc, state):
    print(f"[{state.value}] {desc}", flush=True)

desktop_path = str(Path.home() / "Desktop" / "testing.txt")

print(f"\n--- PROMPT 1 ---", flush=True)
p1 = f'create a file called testing.txt on Desktop with the text "hello world"'
print(f"❯ {p1}", flush=True)
r1 = orch.process_message(sess.id, p1, status_callback=status_cb)
print(f"Agent: {r1.content}\n", flush=True)

print(f"\n--- PROMPT 2 ---", flush=True)
p2 = f'same file rewrite the text "hello world" 1000000 times'
print(f"❯ {p2}", flush=True)
r2 = orch.process_message(sess.id, p2, status_callback=status_cb)
print(f"Agent: {r2.content}\n", flush=True)
