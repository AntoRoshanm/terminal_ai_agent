import sys
from pathlib import Path
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import AgentConfig
from app.providers.factory import create_provider
from app.storage.database import Database
from app.storage.session_store import SessionStore
from app.tools.registry import ToolRegistry
from app.tools.windows import register_windows_tools
from app.tools.filesystem import register_filesystem_tools
from app.models.messages import ChatMessage, Role

cfg = AgentConfig.load()
db = Database(cfg.storage.db_path)
ss = SessionStore(db)
prov = create_provider(cfg.provider)
reg = ToolRegistry()
register_windows_tools(reg)
register_filesystem_tools(reg)
tools = reg.get_definitions()

# Let's test with mid-dialogue system message vs clean reminder
p = "create a file test_log.txt on Desktop with 'test 123'"

# Test A: Mid-dialogue System message
msgs_a = [
    ChatMessage(role=Role.SYSTEM, content=cfg.system_prompt),
    ChatMessage(role=Role.USER, content=p),
    ChatMessage(role=Role.ASSISTANT, content="I'm sorry, but I can't directly create files or directories."),
    ChatMessage(role=Role.SYSTEM, content="POLICY VIOLATION: You are equipped with autonomous tools to perform this operation directly. You MUST emit the actual tool call now."),
]
res_a = prov.generate(messages=msgs_a, tools=tools)
print("=== TEST A (Mid-dialogue System) ===")
print("Content:", res_a.content)
print("Tool calls:", res_a.tool_calls)

# Test B: User Reminder instead of mid-dialogue system message
msgs_b = [
    ChatMessage(role=Role.SYSTEM, content=cfg.system_prompt),
    ChatMessage(role=Role.USER, content=p),
    ChatMessage(role=Role.ASSISTANT, content="I'm sorry, but I can't directly create files or directories."),
    ChatMessage(role=Role.USER, content="Please execute this action using your file_write tool now."),
]
res_b = prov.generate(messages=msgs_b, tools=tools)
print("\n=== TEST B (User Reminder) ===")
print("Content:", res_b.content)
print("Tool calls:", res_b.tool_calls)
