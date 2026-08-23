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
from app.models.messages import ChatMessage, Role

cfg = AgentConfig.load()
db = Database(cfg.storage.db_path)
ss = SessionStore(db)
aud = AuditStore(db)
prov = create_provider(cfg.provider)
reg = ToolRegistry()
register_windows_tools(reg)
register_filesystem_tools(reg)

tools = reg.get_definitions()

user_prompt = "create a file test_log.txt on Desktop with 'test 123'"

messages = [
    ChatMessage(role=Role.SYSTEM, content=cfg.system_prompt),
    ChatMessage(role=Role.USER, content=user_prompt)
]

print("=== RAW GENERATION 1 ===")
res1 = prov.generate(messages=messages, tools=tools)
print("Role:", res1.role)
print("Content:", repr(res1.content))
print("Tool Calls:", res1.tool_calls)

if not res1.tool_calls:
    messages.append(res1)
    messages.append(
        ChatMessage(
            role=Role.SYSTEM,
            content="ENFORCEMENT: The user request is classified as LOCAL_ACTION (actionable operation). "
                    "You MUST execute the appropriate tool from your toolset to obtain real facts or perform the action. "
                    "Do NOT provide a textual explanation or tutorial command in place of execution."
        )
    )
    print("\n=== RAW GENERATION 2 (After Enforcement) ===")
    res2 = prov.generate(messages=messages, tools=tools)
    print("Role:", res2.role)
    print("Content:", repr(res2.content))
    print("Tool Calls:", res2.tool_calls)
