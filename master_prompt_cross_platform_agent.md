# MASTER COMPLETION DIRECTIVE (v2)
# Cross-Platform (Windows + Linux) Build + Strict Autonomous Execution Enforcement

> This file replaces the earlier "MASTER COMPLETION DIRECTIVE" (v1). Discard that one — this is the current, complete version.

## 0. HOW TO USE THIS DOCUMENT

Give Antigravity, in this order:

1. `MASTER SPECIFICATION` (original behavioral spec — FSM, verification loop, security model, MCP architecture).
2. `Windows AI Agent — Complete Technical Architecture & Codebase Blueprint` (the existing codebase inventory).
3. **This document.**

This document is the authoritative completion directive. Where it conflicts with documents 1 or 2, this one wins. Everywhere else, documents 1 and 2 remain in force — **do not re-derive or replace the FSM, security model, MCP architecture, memory system, provider abstraction, or existing tools.** Extend them; don't rebuild them.

This document has two parts:

- **Part A — What to build:** completes the codebase into a real cross-platform (Windows + Linux) agent.
- **Part B — How it must behave:** closes the gap between "the agent has a tool for this" and "the agent actually, always, uses it." Part A gives the agent hands. Part B makes sure it uses them instead of describing what it would do.

Both parts are equally mandatory. Part A without Part B produces a capable agent that still sometimes says "you can run this command." Part B without Part A produces a strict agent with no Linux hands to enforce with. Ship both together.

---

# PART A — CROSS-PLATFORM COMPLETION

## A.1 Platform Detection Layer (NEW)

Add a single, early, cached detection step the entire system depends on.

```
app/platform/
├── __init__.py
├── detect.py          # OS + distro + shell + display-server detection, cached at startup
├── capabilities.py     # Per-OS capability matrix (available / degraded / absent)
└── contracts.py         # Abstract base classes every OS-specific provider must implement
```

`detect.py` runs once at startup and is exposed as part of `AgentState`:

```python
class PlatformInfo:
    os_family: Literal["windows", "linux"]
    os_name: str                # e.g. "Windows 11 Pro", "Ubuntu 24.04 LTS"
    os_version: str
    kernel_version: str | None  # Linux only
    architecture: str
    shell_default: str          # "powershell", "cmd", "bash", "zsh", "sh"
    package_managers: list[str] # winget/choco/scoop OR apt/dnf/pacman/snap/flatpak
    display_server: str | None  # Linux only: "x11", "wayland", "none"
    is_admin_or_root: bool
    is_wsl: bool
```

Detection must be evidence-based:
- Windows: `platform.system()`, `sys.getwindowsversion()`, registry `CurrentVersion` keys.
- Linux: parse `/etc/os-release`, `platform.release()` for kernel, detect package managers via `shutil.which`, detect Wayland/X11 via `$XDG_SESSION_TYPE`/`$WAYLAND_DISPLAY`.
- WSL: check `/proc/version` for "microsoft"/"WSL" — if true, filesystem/terminal tools work against the Linux side, but GUI/process/service tools targeting the Windows host are out of scope unless an interop bridge is explicitly configured; detect and say so.

Every OS-specific tool reads `PlatformInfo` from agent state and dispatches accordingly — never re-detect per call.

## A.2 Provider Contract Pattern (NEW)

One abstract interface per tool category in `app/platform/contracts.py`, one concrete implementation per OS, selected once at startup via a factory — same pattern as the existing `LLM Provider` abstraction.

```
app/tools/system/
├── contracts.py     # SystemInfoProvider, ProcessProvider, ServiceProvider,
│                     # PackageManagerProvider, GUIProvider, NetworkProvider, EventLogProvider
├── windows/          # existing logic, moved here unchanged
├── linux/             # NEW implementations
└── factory.py        # returns the right provider based on PlatformInfo
```

Tool names and schemas exposed to the LLM **do not change** — they become thin wrappers calling `factory.get_provider().method()`. This preserves every prompt/tool-calling behavior already tuned in the base spec.

Conditionally import OS-only libraries (`pywin32`, `win32gui`, `win32evtlog`) only inside Windows provider modules, so the package still imports cleanly on Linux, and vice versa.

## A.3 Windows ↔ Linux Tool Parity Map

| Tool (unchanged name) | Windows (existing) | Linux (NEW — build this) |
|---|---|---|
| `get_os_info` | `sys.getwindowsversion`, registry | `/etc/os-release`, `platform.uname()`, `uptime` |
| `get_hardware_info` | Win32 `GlobalMemoryStatusEx`, WMI | `/proc/meminfo`, `/proc/cpuinfo`, `lscpu`; GPU via `nvidia-smi` or `lspci` |
| `get_storage_info` | WMI volumes | `psutil.disk_partitions/usage`, cross-check `df -h` |
| `get_network_info` | WMI adapters, `ipconfig` | `ip addr`, `ip route`, `/etc/resolv.conf`, `nmcli` if present |
| `get_installed_software` | 64/32-bit registry `Uninstall` keys | merge `dpkg -l`/`rpm -qa`/`pacman -Q` + `snap list` + `flatpak list` |
| `get_process_info` | `psutil` | same `psutil` path — verify parity |
| `get_service_info` | Windows SCM via `pywin32` | `systemctl list-units --type=service --all` (fallback `service --status-all`) |
| `get_environment_info` | `os.environ`, registry PATH | `os.environ` + `~/.bashrc`/`~/.profile`/`/etc/environment` |
| `terminal_exec` | PowerShell/CMD | detect login shell (`$SHELL`), run via `bash -lc`/`sh -c`, same result contract |
| `software_detect_managers` | winget, choco, scoop | apt, dnf, pacman, zypper, snap, flatpak — detect all present |
| `software_install_package` | `winget install` | package-manager-appropriate install; sudo handling per A.5.D |
| `software_configure_env` | registry/`setx` | `~/.bashrc` or `/etc/environment` depending on scope |
| `dev_manage_service` | `sc.exe`/`pywin32` | `systemctl start/stop/restart <unit>` |
| `diagnostics_query_event_log` | `win32evtlog` | `journalctl` (fallback `/var/log/syslog`/`/var/log/messages`) |
| `diagnostics_check_updates` | Windows Update query | `apt list --upgradable`/`dnf check-update`/`pacman -Qu` |
| `app_list_windows`/`app_focus`/`app_close` | `win32gui`, `win32process` | X11: `wmctrl`/`python-xlib`; Wayland: degrade explicitly (A.5.F) |
| `app_launch` | `os.startfile` | `xdg-open` for URIs/files, direct exec for binaries |
| `gui_capture_screenshot` | Win32 GDI/`mss` | `mss` on X11; Wayland needs portal/`grim` — degrade explicitly if unavailable |
| `gui_send_input` | Win32 `SendInput` | X11: `pyautogui`/`xdotool`; Wayland: degrade explicitly |
| `mcp_web-search_*` | n/a | no change needed — already OS-agnostic |

Any row without true parity (mainly Wayland GUI) must:
1. Detect the condition correctly.
2. Return a structured "capability degraded: `<reason>`" result — never a silent no-op or fabricated success.
3. Have a test asserting the degraded-capability response, not a skipped test.

## A.4 Updated Directory Structure

```
app/
├── platform/                    # NEW — detection + capability matrix + contracts
├── tools/
│   ├── system/                  # RENAMED from tools/windows/, now OS-dispatching
│   │   ├── contracts.py / factory.py / windows/ / linux/
│   ├── filesystem/               # audit for Windows-only path assumptions
│   ├── terminal/                 # shell-detect instead of hardcoding PowerShell
│   ├── software/                 # extend package-manager list, tool names unchanged
│   ├── diagnostics/               # split Windows/Linux backends behind factory
│   ├── applications/              # split Windows/Linux(X11/Wayland) backends behind factory
│   ├── gui/                       # split Windows/Linux(X11/Wayland) backends behind factory
│   └── browser/, developer/        # audit only, likely unchanged
├── config.py                     # add `platform_overrides` section
└── ...                           # agent/, mcp/, memory/, providers/, security/, storage/,
                                    # interface/ — structure unchanged
```

## A.5 Cross-Platform Edge Cases

**A.** Path handling — audit filesystem tools for hardcoded `\\`/drive-letter assumptions; use `pathlib.Path` throughout.
**B.** Line endings — normalize CRLF/LF in `file_read`/`file_write`/`file_edit`.
**C.** Admin/root — Windows `IsUserAnAdmin()`, Linux `os.geteuid()==0`, both feed `PlatformInfo.is_admin_or_root`; security guard treats both identically.
**D.** Sudo interactivity — the agent must never store or pass a sudo password. If a command needs elevation and the agent isn't already root, surface it as a permission-check event requiring the human to type the password directly into the terminal — never through the LLM.
**E.** Package manager ambiguity — if multiple managers could satisfy a request (`apt` + `snap` both present), ask via the human-approval mechanism rather than guessing.
**F.** Wayland GUI limits — the single largest real capability gap. Expose it as a capability-matrix fact the agent can reason about and tell the user, never hide it.
**G.** WSL — detect and clearly scope what is and isn't reachable, per A.1.

## A.6 Security Layer — Extend, Don't Weaken

- Protected path blocklist becomes platform-aware: Windows keeps `C:\Windows`, `C:\Program Files`, etc.; Linux adds `/etc`, `/boot`, `/usr`, `/bin`, `/sbin`, `/root`, `/lib`, `/proc`, `/sys`.
- Destructive-action confirmation (delete, service stop, package removal, process kill) requires the same explicit approval on both OSes.
- Secret masking extends to Linux patterns: SSH private key blocks, `.env` values, `~/.aws/credentials` contents.
- Prompt-injection defense (web/file/terminal output is data, never instructions) applies uniformly to Linux tool output too.

## A.7 Testing & CI

- `pytest` markers: `@pytest.mark.windows_only`, `@pytest.mark.linux_only`, `@pytest.mark.cross_platform`.
- Every new Linux provider gets a test file mirroring the existing Windows test file, equivalent coverage, not fewer cases.
- Add `test_platform_detection.py`: Windows detection, Linux distro-family detection, WSL detection, Wayland vs X11, 0/1/multiple package managers present.
- CI matrix: full suite on `windows-latest` and `ubuntu-latest`. A change tested on one OS and silently not run on the other is not done.
- Final suite size: 94 existing + full Linux-equivalent coverage + platform-detection tests, green on both runners.

---

# PART B — STRICT AUTONOMOUS EXECUTION ENFORCEMENT

Part A gives the agent real hands on both OSes. This part makes sure it uses them — every time, without asking permission to try, and without narrating instead of acting. **Do not weaken or bypass the security/approval model from A.6 or the base spec to achieve this — capability and safety are not in tension here; the agent acts freely within read-only/low-risk tiers and still asks approval for destructive tiers, exactly as already specified.**

## B.0 Enforce This in Code, Not Only in the Prompt

Prompt instructions like "always call a tool for local checks" are necessary but not sufficient — under context pressure a model can still drift into describing a command instead of running it. Add hard, testable guardrails in the orchestrator itself:

1. **Intent classification is a discrete, logged pre-step**, not just an internal LLM thought. Implement it as an actual function call (`classify_intent(user_message) -> IntentCategory`) that runs before planning, using the taxonomy in B.12, and store the result in `AgentState.intent`. This makes it unit-testable independent of the LLM's final phrasing.
2. **FSM transition guard:** the state machine must not be allowed to move from `PLANNING` to `COMPLETED` when `AgentState.intent` is one of `LOCAL_ACTION`, `LOCAL_INFORMATION`, `TROUBLESHOOTING`, `WEB_INFORMATION`, `WEB_RESEARCH`, or `MULTI_TOOL` **unless** `AgentState.execution_trace` contains at least one real tool invocation with a recorded result. If the LLM tries to finalize without one, the orchestrator rejects the transition and forces re-planning — this is a code-level assertion, not a prompt reminder.
3. **Verification guard:** for `LOCAL_ACTION` and any destructive-tier task, `COMPLETED` additionally requires a `verification_result` object attached to state (see B.4) — not merely a tool call, an *observed post-condition check*.
4. **Response-text guard (defense in depth):** before sending the final answer, scan it for command-suggestion patterns ("you can run", "try this command", "here's how to check") when `AgentState.intent` indicates an actionable request and no corresponding tool call exists in the trace. If matched, treat as a policy violation and force the orchestrator back into `PLANNING` rather than emitting the response. This is a safety net, not the primary mechanism — B.0.2 is.

## B.1 Tool Execution Is Absolute

```
User Request
    ↓
Does this require real computer state/action?
    ↓ YES
MUST CALL TOOL → OBSERVE ACTUAL RESULT → VERIFY → RESPOND
```

A plan is not an execution. A generated command is not an execution. A textual explanation is not an execution. Selecting a tool without calling it is not an execution.

## B.2 Ban "How To Do It" Responses For Agent Tasks

If the user asks the agent to check, inspect, find, list, identify, diagnose, open, install, configure, modify, run, fix, or control something, and the capability exists, the agent performs the operation. It does not respond with "You can run…", "Try this command…", "Here's how to check…" — unless the user explicitly asks *"how do I do this manually?"*

Example — `What Python version do I have?`
Wrong: `You can run: python --version`
Correct: locate Python → execute version check → observe result → verify executable/environment → answer.

## B.3 Terminal Is a Real Execution Tool

`terminal_exec` actually executes commands on the OS-appropriate shell (per A.3) and returns structured results:

```
command, shell, working_directory, stdout, stderr, exit_code, duration, timed_out
```

The LLM reasons from that structured result. It never prints a command as its final response in place of running it.

## B.4 Verification Must Represent a Real Observation

Never allow `[VERIFYING] Verified successfully` without an actual check having run. Examples:

- **Python check:** find executable → version check → verify executable path.
- **Software install:** installed version → executable → service/process → operational test.
- **App launch:** launch → process/window detection → verify state.
- **File creation:** create → verify path exists → verify expected content/metadata.
- **Web search:** search → results received → source relevance checked → answer grounded in results.

## B.5 Web Search Is Automatic

Keywords like *current, today, latest, recent, newest, price, news, release, availability, online, search, research* signal that current external information is required. The agent does not ask "Would you like me to search?" — the question itself is sufficient authorization for an ordinary (non-destructive) web search.

Example — `What is the current iPhone 17 price?`
Wrong: "I don't have real-time pricing." / "Would you like me to search?" / "You can check Apple's website."
Correct: understand → select web-search capability → execute → observe results → verify relevance/recency/source → answer.

## B.6 Web Search Capability Discovery

The agent must know, at any time, whether web search is actually usable — not merely configured:

```
NOT_CONFIGURED → STARTING → CONNECTED → AVAILABLE → FAILED → UNAVAILABLE
```

Verified via real MCP server connection → tool discovery → tool registration → a callable tool. A config file existing is not evidence of availability.

## B.7 Web Search Fallback Chain

Preferred provider → fallback provider (per the base spec's configured priority) is selected automatically at the infrastructure layer. The agent never asks the user to manually pick a provider.

## B.8 Web Search Is a First-Class Registry Tool

Registered in the same unified tool registry as local system/filesystem/terminal/application/GUI/developer/diagnostics tools — not a separate conversational path:

```
Tool Registry
 ├── system tools (Windows+Linux, via A.2 factory)
 ├── filesystem / terminal / software / application / GUI / developer / diagnostics tools
 └── web-search tools (MCP)
```

## B.9 Local vs. Web Routing

- `What Python version do I have?` → local tool only.
- `What is the latest Python release?` → web search only.
- `What Python version do I have, and what's the latest release?` → local tool + web search, combined in one answer.

This routing is automatic and comes directly out of B.0.1's intent classification.

## B.10 Never Fabricate Current Information

For current price / latest release / today's news / current version / current availability, the agent either (1) retrieves it via web search, or (2) explicitly reports the web capability is unavailable (per B.6's real status, not a guess). It never invents an answer from model memory.

## B.11 Web Result Grounding

Preserve at minimum `title, url, domain, snippet/content, publication date (if available), retrieval timestamp` in agent state. The final answer is built from retrieved information only; nothing claimed that wasn't present in results. Favor recent, authoritative sources for time-sensitive questions.

## B.12 Request Classification Taxonomy

```
NORMAL_CHAT          "hello"
LOCAL_INFORMATION    "what Python version do I have?"
LOCAL_ACTION         "open VS Code"
TROUBLESHOOTING      "why is Docker failing?"
WEB_INFORMATION      "what's today's iPhone price?"
WEB_RESEARCH         "research latest PostgreSQL deployment practices"
MULTI_TOOL           "check my Python version and compare to the latest release"
```

Implemented as the discrete `classify_intent` function from B.0.1, not left implicit in free-form reasoning.

## B.13 Multi-Tool Reasoning

Example — `Find the latest PostgreSQL version, check my installed version, and tell me whether I should upgrade.`
Required: web search + local software inspection + reasoning + final comparison. The agent does not stop after the first tool result when the request implies more.

## B.14 Autonomous Failure Recovery

```
ERROR → INTERPRET → DIAGNOSE → SAFE ALTERNATIVE → RETRY → VERIFY
```

Example: software inventory tool fails → diagnose → try an alternate supported inventory source (per A.3's multi-source merge, e.g. `dpkg` + `snap` + `flatpak`) → merge/deduplicate → verify → return result. Only surface the failure to the user when recovery genuinely requires human input (credentials, ambiguous choice, destructive-tier approval).

## B.15 Never Stop After Planning

Not acceptable for an actionable request: `UNDERSTANDING → PLAN → COMPLETED`. Minimum valid sequence: `UNDERSTAND → PLAN → EXECUTE → OBSERVE → VERIFY → COMPLETE`. Enforced by the B.0.2 FSM guard, not just instructed.

## B.16 Never Stop After a Single Unverified Tool Call

Example — `Install PostgreSQL.` A successful installer exit code alone is insufficient. Continue: version → executable → service → port → connectivity, then complete. Enforced by the B.0.3 verification guard for actionable/destructive tasks.

## B.17 Capability-Driven, Not Hard-Coded

The agent reasons from the available capability set (system, process, service, network, filesystem, terminal, software, application, browser, GUI, diagnostics, developer, MCP/web search) rather than a hard-coded list of "special" applications it knows how to handle.

## B.18 Inspection Verbs Trigger Real Inspection

*check, find, list, tell me, show me, identify, inspect, verify, detect* — when referring to the user's environment, these trigger a real tool call, not a description of one.

## B.19 Action Verbs Trigger Real Actions

*install, open, create, run, configure, modify, move, rename, download, start, stop, restart, fix* — treated as operations to perform, not topics for a tutorial.

## B.20 Troubleshooting Is Evidence-Based

For "why is X not working?", inspect actual state (process, service, config, network, files, logs, dependencies, permissions) before concluding. The final diagnosis distinguishes observed fact, inference, probable cause, and verified root cause — never presents speculation as fact.

## B.21 The LLM Is a Reasoning Layer, Not the System of Record

The LLM owns: intent understanding, planning, tool selection, parameter generation, interpretation, diagnosis, recovery, final synthesis. The LLM never invents system state, tool results, web results, versions, prices, processes, services, or files.

## B.22 Model Layer

Keep the existing provider abstraction. Local model family: Qwen, configurable rather than hard-coded, benchmarked on tool calling, instruction following, planning, parameter accuracy, multi-step execution, failure recovery, web-search routing, latency, and context requirements.

## B.23 One Agent Loop for Local + Web + MCP

```
                 USER
                   ↓
             AGENT CORE
                   ↓
              INTENT ROUTER (B.0.1)
                   ↓
      ┌────────────┼────────────┐
      ↓            ↓            ↓
   LOCAL          WEB        NORMAL
   TOOLS        MCP/WEB        LLM
   (Part A)                     
      └────────────┼────────────┘
                   ↓
     OBSERVE → VERIFY → RECOVER/RETRY → COMPLETE
```

Web search is not a separate conversational path — it's one branch of the same loop, gated by the same FSM guards.

## B.24 Security Boundary Preserved

```
LLM → tool request → security guard → permission/risk classification → execution
```

Full autonomy within read-only/low-risk tiers; the same human-approval gate as always for modifying/destructive tiers (per A.6). Capability and safety are not traded off against each other here.

## B.25 MCP Diagnostics

Add a diagnostic capability exposing:

```
MCP servers configured
MCP servers connected
MCP tools discovered
Web search available
Web search provider (active/fallback)
Last connection error
```

So web-search failures are diagnosable rather than silent.

## B.26 Test Real Runtime Behavior, Not Just Configuration

A feature is not complete because the prompt says to use a tool, or the MCP config file exists, or unit tests pass in isolation. The regression suite in Part C must demonstrate the *real* agent invoking the *correct* tools end-to-end.

---

# PART C — CONSOLIDATED REGRESSION TEST SUITE

## C.1 Cross-Platform Dispatch (Part A)

1. **Windows dispatch** — `What Python version do I have?` on Windows → Windows `system_info` provider invoked, correct result.
2. **Linux dispatch** — same input on Linux → Linux provider invoked, identical response schema to (1).
3. **Package manager ambiguity** — `Install Docker.` on Linux with both `apt` and `snap` present → agent surfaces the choice for approval rather than guessing.
4. **Wayland GUI degradation** — `Take a screenshot.` on Linux/Wayland → successful portal-based capture, or an explicit "not supported under this Wayland session because `<reason>`" — never silent failure or fabricated success.
5. **Cross-OS parity** — `Check what's using port 8080.` → OS-appropriate mechanism on each platform, same final answer shape.

## C.2 Autonomous Behavior (Part B)

6. **Local-only routing** — `What Python version do I have?` → local tool invoked. NOT web search.
7. **Web-only routing** — `What is the latest Python version?` → web-search tool invoked. NOT local-only.
8. **Mandatory automatic search** — `What is the current iPhone 17 price?` → web-search MCP invoked automatically. Must NOT: claim no real-time access; ask permission to search; guess a price; explain how to search manually.
9. **Combined routing** — `What Python version do I have, and what is the latest Python version?` → local tool + web-search tool, combined answer.
10. **Fallback on partial failure** — `List all installed software.` → inventory tool invoked; if the primary source fails, diagnose → fallback source → merge → verify → answer (not a raw error).
11. **Full action + verify chain** — `Install PostgreSQL and verify that it works.` → inspect → plan → approval where required → install → version check → service/process check → port check → connectivity check → completion. Not complete after installer exit code alone.
12. **No premature completion** — any `LOCAL_ACTION`/`TROUBLESHOOTING`/`MULTI_TOOL` request must fail the B.0.2 FSM guard test if the trace contains zero tool invocations before `COMPLETED`.
13. **No unverified completion** — any destructive/actionable task must fail the B.0.3 verification guard test if `COMPLETED` is reached without a `verification_result`.

---

# PART D — HOW ANTIGRAVITY SHOULD EXECUTE THIS

1. Inspect the current codebase as it actually exists (not just as documented) — confirm what's real vs. aspirational in the blueprint.
2. Write a short implementation plan mapping Parts A and B to concrete file changes before writing code.
3. Build Part A first, in this order: A.1 platform detection → A.2 provider contracts → migrate existing Windows logic behind those contracts unchanged → A.3 Linux providers one category at a time, test-then-next → A.6 security extension in lockstep → A.7 CI matrix.
4. Build Part B on top of a working Part A: B.0.1 discrete intent classifier → B.0.2 FSM completion guard → B.0.3 verification guard → B.0.4 response-text safety net → B.25 MCP diagnostics.
5. Run the full suite (existing 94 + new Linux tests + platform-detection tests + Part C regression suite) on both `windows-latest` and `ubuntu-latest`. Nothing is reported complete until green on the OS(es) it targets.
6. Report back: what changed, what's now cross-platform, what remains OS-limited and why (Wayland GUI, WSL boundary), and confirmation that every Part C test passes on both OSes.

---

# PART E — DEFINITION OF DONE

- Agent starts on both Windows and Linux with zero code changes, detects its OS correctly, logs `PlatformInfo`.
- Every tool in the A.3 parity map works identically in name/schema on both OSes, OS-appropriate execution behind it; genuine gaps (Wayland GUI) are explicit, tested, and honestly reported — never faked.
- Security guard enforces identical permission levels and human-approval gates on both OSes; capability increases (Part B) never came at the cost of weakening this.
- The FSM cannot reach `COMPLETED` for an actionable/destructive request without a recorded tool execution and, where required, a recorded verification result — enforced in code (B.0.2/B.0.3), not only in prompt text.
- Web search fires automatically on any current-information request, with real availability status (not assumed from config) and grounded, sourced answers.
- Full test suite — existing 94 + new Linux coverage + platform-detection tests + all 13 Part C regression tests — passes on both `windows-latest` and `ubuntu-latest` in CI.
- All invariant behavior from the original `MASTER SPECIFICATION` (verification-before-completion, prompt-injection handling, tool-first rule) is unchanged and still passes its existing tests.
