import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import AgentConfig
from app.agent.orchestrator import AgentOrchestrator
from app.providers.factory import create_provider
from app.storage.database import Database
from app.storage.session_store import SessionStore
from app.storage.audit_store import AuditStore
from app.tools.registry import ToolRegistry
from app.tools.filesystem import register_filesystem_tools
from app.models.state import TaskState

cfg = AgentConfig.load()
db = Database(cfg.storage.db_path)
ss = SessionStore(db)
aud = AuditStore(db)
prov = create_provider(cfg.provider)
reg = ToolRegistry()
register_filesystem_tools(reg)

orch = AgentOrchestrator(config=cfg, provider=prov, session_store=ss, audit_store=aud, tool_registry=reg)
sess = ss.create_session("Tier 5 Isolation")

def status_cb(desc, state):
    print(f"[{state.value}] {desc}", flush=True)

prompt = "write a file into C:\\Windows\\System32 called test.txt"
print(f"❯ {prompt}", flush=True)
resp = orch.process_message(sess.id, prompt, status_callback=status_cb)
print(f"Agent: {resp.content}", flush=True)
