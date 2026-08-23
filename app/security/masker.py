"""
Secret and Credential Masking Engine
"""

import re
from typing import Any, Dict, List, Union


class SecretMasker:
    """Sanitizes strings and data structures to prevent leaking API keys, tokens, and passwords."""

    # Patterns matching sensitive keys, tokens, and passwords (ordered most specific first)
    PATTERNS = [
        # SSH Private Key block
        (re.compile(r"-----BEGIN (RSA|OPENSSH|EC|DSA|PGP) PRIVATE KEY-----[\s\S]*?-----END (RSA|OPENSSH|EC|DSA|PGP) PRIVATE KEY-----", re.IGNORECASE), "-----BEGIN PRIVATE KEY-----\n***[REDACTED PRIVATE KEY]***\n-----END PRIVATE KEY-----"),
        # AWS Access Key ID
        (re.compile(r"\b(AKIA|ABIA|ACCA|ASIA)[0-9A-Z]{16}\b"), "AKIA***[REDACTED]***"),
        # Anthropic keys (sk-ant-...)
        (re.compile(r"sk-ant-[a-zA-Z0-9_\-]{15,}", re.IGNORECASE), "sk-ant-***[REDACTED]***"),
        # OpenAI / OpenRouter keys (sk-...)
        (re.compile(r"sk-[a-zA-Z0-9_\-]{20,}", re.IGNORECASE), "sk-***[REDACTED]***"),
        # Google Gemini / Cloud API keys (AIza...)
        (re.compile(r"AIza[0-9A-Za-z-_]{35}", re.IGNORECASE), "AIza***[REDACTED]***"),
        # GitHub Personal Access Tokens (ghp_...)
        (re.compile(r"gh[pousr]_[a-zA-Z0-9]{36,}", re.IGNORECASE), "ghp_***[REDACTED]***"),
        # Generic Bearer Tokens
        (re.compile(r"Bearer\s+([a-zA-Z0-9_\-\.]{20,})", re.IGNORECASE), "Bearer ***[REDACTED]***"),
        # Passwords / secrets in JSON/YAML or command line
        (re.compile(r'("password"|"secret"|"token"|"api_key"|"auth_token")\s*:\s*"([^"]+)"', re.IGNORECASE), r'\1: "***[REDACTED]***"'),
    ]

    @classmethod
    def mask_text(cls, text: str) -> str:
        """Redact sensitive credentials from a text string."""
        if not text or not isinstance(text, str):
            return text

        masked = text
        for pattern, replacement in cls.PATTERNS:
            masked = pattern.sub(replacement, masked)
        return masked

    @classmethod
    def mask_dict(cls, data: Union[Dict[str, Any], List[Any], Any]) -> Any:
        """Recursively redact secrets in dictionaries or lists."""
        if isinstance(data, dict):
            return {
                k: "***[REDACTED]***" if any(s in k.lower() for s in ("password", "secret", "token", "api_key", "auth"))
                else cls.mask_dict(v)
                for k, v in data.items()
            }
        elif isinstance(data, list):
            return [cls.mask_dict(item) for item in data]
        elif isinstance(data, str):
            return cls.mask_text(data)
        return data
