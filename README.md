# Windows AI Agent

An autonomous AI agent for Windows that runs completely offline with **local Qwen / Ollama (No API Key Required)** or with cloud AI providers (OpenAI, Claude, Gemini).

---

## Quick Start (2 Steps)

### 1. Activate Virtual Environment
Open PowerShell in this folder and run:
```powershell
.\.venv\Scripts\Activate.ps1
```
*(If you see a script execution policy message, run: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process`)*

### 2. Start the Agent
Make sure Ollama is running (`ollama serve`), then start:
```powershell
python main.py
```
*No API key needed! The agent automatically runs your local **Qwen model (`qwen2.5:3b` / `qwen3.5:9b`)** with GPU acceleration.*

---

## Tool-First Rule

Whenever you ask about your computer, system state, software, files, processes, or ports:
- The agent **never gives generic instructions** (e.g. it will never tell you *"You can run python --version"*).
- The agent **executes the real Windows tool**, verifies the outcome, and reports the verified facts.

---

## (Optional) Use Cloud Models Instead

If you want to use cloud providers instead of local Ollama, set your API key:
```powershell
# For OpenAI / OpenRouter:
$env:OPENAI_API_KEY="sk-..."
$env:AI_PROVIDER="openai"

# For Anthropic Claude:
$env:ANTHROPIC_API_KEY="sk-ant-..."
$env:AI_PROVIDER="anthropic"

# For Google Gemini:
$env:GEMINI_API_KEY="..."
$env:AI_PROVIDER="gemini"
```

---

## Example Things You Can Ask the Agent

- **System Diagnostics:** *"What is my operating system, CPU load, and total RAM?"*
- **Python & Environment:** *"Can you check my Python version and active executable?"*
- **Disk & Storage:** *"Can you check my disk storage and free space?"*
- **Desktop Apps:** *"List all open windows on my desktop"*
- **Persistent Memory:** *"Remember my preferred editor is VS Code and my project directory is C:\Projects"*
- **Developer Workflow:** *"Check git status for this repository and run all tests"*

---

## Chat Commands

- `/new` — Start a fresh conversation
- `/sessions` — List past sessions
- `/switch <id>` — Switch to a previous session
- `/model` — View or change current model / provider
- `/memory` — Inspect stored user preferences & knowledge base
- `/wipe-memory` — Erase all stored user preferences and memory
- `/mcp` — List active Model Context Protocol (MCP) tool servers
- `/benchmark` — Run AI reasoning & tool-calling evaluation benchmark
- `/audit` — View the action audit trail
- `/help` — Show all commands
- `/exit` — Quit the application

---

## Run Automated Tests

```powershell
python -m pytest tests/
```
