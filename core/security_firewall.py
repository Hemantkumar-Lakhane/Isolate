"""
core/security_firewall.py
==========================
Intelligent AI Agent Security Firewall & Abuse Protection Layer for SMBFlow.

Protects against:
  1. Prompt injection & jailbreak attacks ("ignore previous instructions", DAN mode, system prompt dumps)
  2. Malicious code / exploit generation (scam bots, malware payloads, python scrapers/exploit scripts)
  3. Non-SMB domain resource drain / token bloat attacks
  4. Cost escalation & bill shocks from malicious automated prompt stuffing

Integrates seamlessly into LLMRouter, PromptEnhancer, and Workflow dispatchers.
"""

from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union
import structlog

log = structlog.get_logger()


class SecurityViolationError(ValueError):
    """Raised when an AI prompt violates SMBFlow security policies."""
    def __init__(self, reason: str, category: str, pattern: Optional[str] = None):
        self.reason = reason
        self.category = category
        self.pattern = pattern
        super().__init__(f"SECURITY_VIOLATION [{category}]: {reason}")


@dataclass
class SecurityEvaluation:
    is_safe: bool
    category: Optional[str] = None
    reason: Optional[str] = None
    matched_pattern: Optional[str] = None
    sanitized_prompt: Optional[str] = None
    risk_score: float = 0.0  # 0.0 to 1.0


# ── High-Risk Malicious Patterns (Zero Tolerance) ──────────────────────────────
EXPLOIT_PATTERNS = [
    (r"(?i)\b(write|create|generate|code|script)\b.*\b(keylogger|ransomware|trojan|botnet|exploit|payload|rootkit|backdoor|malware)\b", "MALICIOUS_CODE_PAYLOAD"),
    (r"(?i)\b(ddos|dos attack|syn flood|brute force|port scanner|sql injection tool|sqlmap)\b", "NETWORK_EXPLOIT_TOOL"),
    (r"(?i)\b(bypass|disable)\b.*\b(antivirus|edr|firewall|defender|security controls|waf)\b", "SECURITY_EVASION"),
    (r"(?i)\b(steal|harvest|dump|phish)\b.*\b(credentials|passwords|cookies|session tokens|private keys|credit cards)\b", "CREDENTIAL_HARVESTING"),
    (r"(?i)\b(crypto miner|cryptomining script|monero miner|stratum mining)\b", "UNAUTHORIZED_CRYPTO_MINING"),
    (r"(?i)\b(scam email|phishing template|fake invoice scam|wire fraud script)\b", "FRAUD_AND_SCAM"),
]

# ── Prompt Injection & Jailbreak Patterns ─────────────────────────────────────
JAILBREAK_PATTERNS = [
    (r"(?i)\b(ignore|disregard|forget|override)\s+(all\s+)?(previous|prior|above)\s+(instructions|rules|prompts|system prompts|constraints)\b", "PROMPT_INJECTION_OVERRIDE"),
    (r"(?i)\b(you are now in|switch to|enter)\s+(dan|developer|god|unrestricted|jailbreak|chaos|unfiltered)\s+(mode|state)\b", "JAILBREAK_MODE_SWITCH"),
    (r"(?i)\b(print|reveal|output|display|show|leak)\s+(your\s+)?(system\s+prompt|initial\s+prompt|hidden\s+rules|internal\s+instructions)\b", "SYSTEM_PROMPT_LEAK"),
    (r"(?i)\b(act as|pretend to be|roleplay as)\s+(an evil|an unfiltered|a malicious|a black hat|a rogue|a dark web)\b", "MALICIOUS_ROLEPLAY"),
    (r"(?i)\[SYSTEM\s+OVERRIDE\]|\[ADMIN\s+PROMPT\]|\<\<SYS\>\>|\<\|im_start\|\>system", "SYSTEM_DELIMITER_INJECTION"),
    (r"(?i)\b(jailbreaked|evil confidant|aim mode|do anything now)\b", "POPULAR_JAILBREAK_HEURISTIC"),
]

# ── Token Bloat / High-Cost Drain Patterns ─────────────────────────────────────
MAX_PROMPT_CHARS = 120_000  # Prevent extreme token stuffing attacks
REPETITIVE_CHAR_LIMIT = 500


class AgentSecurityFirewall:
    """
    Real-time security and cost protection guard for AI agents.
    Scans incoming requests before LLM dispatch to block malicious misuse,
    preventing massive API billing spikes and malicious code generation.
    """

    @classmethod
    def evaluate(
        cls,
        input_data: Union[str, List[Dict[str, Any]], Dict[str, Any]],
        agent_name: str = "agent",
        strict: bool = False,
    ) -> SecurityEvaluation:
        """
        Evaluate input text or message payload for prompt injection, exploits, or abuse.
        """
        text = cls._extract_text(input_data)
        if not text:
            return SecurityEvaluation(is_safe=True, risk_score=0.0)

        # 1. Check prompt length bounds (Token Bloat Protection)
        if len(text) > MAX_PROMPT_CHARS:
            msg = f"Input exceeds maximum allowed safety threshold ({len(text)} > {MAX_PROMPT_CHARS} characters)"
            log.warning("SecurityFirewall: prompt length violation", agent=agent_name, length=len(text))
            return SecurityEvaluation(
                is_safe=False,
                category="TOKEN_BLOAT_ATTACK",
                reason=msg,
                risk_score=1.0,
            )

        # Check repetitive character flooding (e.g. AAAAA... 10k times)
        rep_match = re.search(r"(.)\1{" + str(REPETITIVE_CHAR_LIMIT) + r",}", text)
        if rep_match:
            return SecurityEvaluation(
                is_safe=False,
                category="REPETITIVE_TOKEN_FLOOD",
                reason="Excessive repetitive character sequence detected",
                matched_pattern=rep_match.group(0)[:30] + "...",
                risk_score=0.9,
            )

        # 2. Check Exploit & Malicious Code Generation
        for pattern, cat in EXPLOIT_PATTERNS:
            match = re.search(pattern, text)
            if match:
                log.error("SecurityFirewall: malicious exploit request blocked", agent=agent_name, category=cat, match=match.group(0)[:60])
                return SecurityEvaluation(
                    is_safe=False,
                    category=cat,
                    reason=f"Request contains disallowed exploit or malicious code generation intent: '{match.group(0)[:40]}'",
                    matched_pattern=match.group(0),
                    risk_score=1.0,
                )

        # 3. Check Prompt Injections & Jailbreaks
        for pattern, cat in JAILBREAK_PATTERNS:
            match = re.search(pattern, text)
            if match:
                log.warning("SecurityFirewall: prompt injection attempt blocked", agent=agent_name, category=cat, match=match.group(0)[:60])
                return SecurityEvaluation(
                    is_safe=False,
                    category=cat,
                    reason=f"Adversarial prompt injection pattern detected: '{match.group(0)[:40]}'",
                    matched_pattern=match.group(0),
                    risk_score=0.95,
                )

        return SecurityEvaluation(
            is_safe=True,
            risk_score=0.0,
            sanitized_prompt=text,
        )

    @classmethod
    def assert_safe(
        cls,
        input_data: Union[str, List[Dict[str, Any]], Dict[str, Any]],
        agent_name: str = "agent",
    ) -> None:
        """
        Evaluate and raise SecurityViolationError immediately if unsafe.
        """
        eval_res = cls.evaluate(input_data, agent_name=agent_name)
        if not eval_res.is_safe:
            raise SecurityViolationError(
                reason=eval_res.reason or "Blocked by AI Security Firewall",
                category=eval_res.category or "SECURITY_VIOLATION",
                pattern=eval_res.matched_pattern,
            )

    @staticmethod
    def _extract_text(input_data: Union[str, List[Dict[str, Any]], Dict[str, Any]]) -> str:
        """Helper to extract flat textual content from strings, dicts, or message lists."""
        if isinstance(input_data, str):
            return input_data
        if isinstance(input_data, list):
            parts = []
            for item in input_data:
                if isinstance(item, dict):
                    parts.append(str(item.get("content", "")))
                elif isinstance(item, str):
                    parts.append(item)
            return " ".join(parts)
        if isinstance(input_data, dict):
            return " ".join(str(v) for v in input_data.values() if isinstance(v, (str, int, float)))
        return str(input_data)
