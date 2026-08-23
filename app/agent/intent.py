"""
Discrete Intent Classification Engine & Defense-in-Depth Safety Backstop (Master Directive B.0.1, B.12, B.32)
"""

import re
from typing import List, Tuple
from app.models.state import IntentCategory


class IntentClassifier:
    """Classifies user requests into actionable/informational/chat taxonomy."""

    # Keywords signaling web information & real-time search
    WEB_SIGNALS = [
        "today", "latest", "current", "recent", "newest", "price", "news",
        "release", "availability", "online", "search web", "look up online",
        "compare with latest", "newest version of", "market price",
    ]

    # Specific signals for local system inspection
    LOCAL_INFO_SIGNALS = [
        # Process & Activity signals (B.12 / B.29)
        "active in the computer", "software is active", "software are active",
        "what software is active", "active software", "what is active", "running right now",
        "currently active", "what is running", "what's running", "running processes",
        "what's open", "what is open", "using cpu", "using memory", "using ram",
        # Installed software signals (B.12 / B.29)
        "software i am having", "software do i have", "what software do i have",
        "what apps do i have", "installed software", "installed programs", "what programs",
        "installed packages", "what packages", "do i have installed",
        # Services & Daemons signals (B.12 / B.29)
        "services is runing", "services are running", "services on my window",
        "services running", "windows services", "system services", "list services",
        "service status", "systemd services", "launchctl services",
        # Task manager / Monitor signals (B.12)
        "task manager", "task manger", "activity monitor", "resource monitor",
        # Network & IP signals
        "my ipv4", "ipv4 address", "my ip address", "what is my ip", "what is my ipv4",
        "ip address", "network adapters", "network info",
        # Date & Time signals (Directive v6.1 Addendum)
        "time now", "current time", "what time is it", "what is the time", "what's the time",
        "today's date", "current date", "what date is it", "what is the date", "what day is today",
        "what day is it", "system clock", "system time", "local time", "date and time",
        # Hardware & Storage signals
        "my python", "my os", "my computer", "my laptop", "my pc", "my ram", "my cpu",
        "my gpu", "my disk", "my storage", "my environment", "my path",
        "how much ram", "what gpu do i have", "what port is", "which process",
        "is docker running", "is notepad running", "do i have", "am i using",
        "what is my", "check my", "tell me my", "list my", "show my",
        "git status", "git log", "git diff",
    ]

    # Action verbs targeting computer operations & local state modifications
    ACTION_VERBS = [
        "install", "uninstall", "open", "launch", "close", "kill", "terminate", "create",
        "write", "rewrite", "overwrite", "edit", "modify", "update", "change", "replace",
        "repeat", "delete", "remove", "rename", "move", "append", "insert", "substitute", "truncate",
        "copy", "clean", "cleanup", "configure", "run", "start", "stop",
        "restart", "enable", "disable", "fix", "deploy", "build", "format", "wipe", "focus",
        "click", "type", "press", "scroll", "applescript", "screenshot",
    ]

    # Troubleshooting queries
    TROUBLESHOOT_SIGNALS = [
        "why is my", "troubleshoot", "why can't i", "fix my", "error running",
        "fails to", "not working", "why is", "diagnose", "fix the error",
        "resolve issue", "crash", "hung", "why isn't", "why cannot",
        "error in", "why does not", "failed to", "failing",
    ]

    # Defense-in-Depth Patterns for Environment Queries & State Modifications (Directive B.32)
    ENV_QUERY_PATTERNS = [
        re.compile(r"\b(software|program|application|package)s?\s+(is|are)?\s*(active|running|installed|open)\b", re.IGNORECASE),
        re.compile(r"\b(active|running)\s+(software|processes?|programs?|apps?)\b", re.IGNORECASE),
        re.compile(r"\b(services?|daemons?)\s+(is|are)?\s*(runing|running|active|stopped)\b", re.IGNORECASE),
        re.compile(r"\b(status\s+of\s+.*(service|daemon|process|app))\b", re.IGNORECASE),
        re.compile(r"\b(task\s*man[ag]{2}er|activity\s*monitor|resource\s*monitor)\b", re.IGNORECASE),
        re.compile(r"\b(ip\s*v?4|ip\s*address|mac\s*address|gateway|dns)\b", re.IGNORECASE),
        re.compile(r"\b(cpu|ram|memory|gpu|disk|storage|uptime|ports?)\b", re.IGNORECASE),
        re.compile(r"\b(what\s+(is\s+)?(the\s+)?time|what\s+time\s+is\s+it|current\s+time|time\s+now|today'?s?\s+date|what\s+(is\s+)?(the\s+)?date|current\s+date|what\s+day\s+is\s+(it|today)|system\s+clock|system\s+time|local\s+time)\b", re.IGNORECASE),
        re.compile(r"\b(in|on)\s+(the|my|this)\s+(computer|pc|laptop|windows|linux|mac|machine|system|window|operating\s+system|os)\b", re.IGNORECASE),
        re.compile(r"\b(this|the|my)\s+(operating\s+system|os\b|windows\s+version|linux\s+distro|macos\s+version)\b", re.IGNORECASE),
        re.compile(r"\b(operating\s+system|os)\s+(version|name|build|type|architecture)\b", re.IGNORECASE),
        re.compile(r"\b(check|see|verify|test|find)\s+(if|whether)\s+.*\s+(is\s+)?(installed|running|active|present|available)\b", re.IGNORECASE),
        re.compile(r"\b(what|tell me|show me)\s+(is\s+)?(the\s+)?(name|version|build|architecture|specs|specifications)\s+(of\s+)?(this|the|my|current)\b", re.IGNORECASE),
        re.compile(r"\b(rewrite|overwrite|replace\s+(the\s+)?text|modify|edit|update|change|append|insert)\b", re.IGNORECASE),
        re.compile(r"\b(file|folder|directory|script|document)\b", re.IGNORECASE),
    ]

    @classmethod
    def is_environment_query(cls, text: str) -> bool:
        """
        Directive B.32: Deterministic pattern-based defense-in-depth check.
        Returns True if the text references the user's local operating environment.
        """
        lower = text.strip().lower()
        if not lower:
            return False
        return any(pat.search(lower) for pat in cls.ENV_QUERY_PATTERNS)

    @classmethod
    def classify(cls, message: str) -> IntentCategory:
        """Classify a user message into a discrete IntentCategory."""
        text = message.strip().lower()
        if not text:
            return IntentCategory.NORMAL_CHAT

        is_time_query = bool(re.search(r"\b(time\s+now|what\s+time|current\s+time|today'?s?\s+date|current\s+date|what\s+(is\s+)?(the\s+)?date|system\s+clock|what\s+day\s+is)\b", text))
        if is_time_query:
            return IntentCategory.LOCAL_INFORMATION

        has_troubleshoot = any(sig in text for sig in cls.TROUBLESHOOT_SIGNALS)
        if has_troubleshoot:
            return IntentCategory.TROUBLESHOOTING

        has_web = any(sig in text for sig in cls.WEB_SIGNALS)
        has_local_info = any(sig in text for sig in cls.LOCAL_INFO_SIGNALS) or any(
            text.startswith(v) for v in ("check ", "inspect ", "find ", "detect ", "verify ", "list ")
        )
        has_action = any(re.search(rf"\b{verb}\b", text) for verb in cls.ACTION_VERBS)
        is_env = cls.is_environment_query(text)

        # 1. Multi-tool combination (e.g. local inspection + web comparison)
        if (has_local_info or has_action or is_env) and has_web:
            return IntentCategory.MULTI_TOOL

        # 2. Web research vs Web info
        if has_web:
            if any(w in text for w in ("research", "guide", "best practices", "deep dive", "documentation on")):
                return IntentCategory.WEB_RESEARCH
            return IntentCategory.WEB_INFORMATION

        # 3. Local Action vs Local Information
        if has_action:
            return IntentCategory.LOCAL_ACTION

        if has_local_info or is_env:
            return IntentCategory.LOCAL_INFORMATION

        # 5. Normal Chat (greetings, general concept explanations)
        # E.g. "hello", "what is docker", "explain operating systems"
        if text in ("hello", "hi", "hey", "help", "who are you"):
            return IntentCategory.NORMAL_CHAT

        if text.startswith("what is ") or text.startswith("explain ") or text.startswith("tell me about "):
            if not any(k in text for k in ("my", "this computer", "in the computer", "local", "pc", "laptop", "window")):
                return IntentCategory.NORMAL_CHAT

        return IntentCategory.NORMAL_CHAT


def classify_intent(user_message: str) -> IntentCategory:
    """Public helper function for discrete intent classification."""
    return IntentClassifier.classify(user_message)
