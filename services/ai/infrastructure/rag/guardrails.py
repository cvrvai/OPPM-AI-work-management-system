"""
Input and output guardrails for the AI pipeline.

Input guardrails:
- Length cap
- Prompt injection pattern detection

Output guardrails:
- Strip accidentally leaked secrets/tokens from LLM responses
"""

import re
import logging

logger = logging.getLogger(__name__)

# ── Input limits ────────────────────────────────────────────────────────────

MAX_INPUT_LENGTH = 4000

# Patterns that strongly signal prompt injection attempts
_INJECTION_PATTERNS: list[re.Pattern] = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions?", re.I),
    re.compile(r"disregard\s+(all\s+)?previous", re.I),
    re.compile(r"###\s*system\s*###", re.I),
    re.compile(r"<\|.{1,30}\|>"),            # special-token injection: <|im_start|> etc.
    re.compile(r"\[INST\]", re.I),           # Llama instruction tokens
    re.compile(r"<</SYS>>", re.I),
    re.compile(r"you are now (a |an )?(different|new|jailbroken|unrestricted)", re.I),
    re.compile(r"act as (a |an )?(different|new|alternative|unrestricted) (AI|assistant|model)", re.I),
    re.compile(r"pretend (you are|to be) (a |an )?(different|evil|unrestricted)", re.I),
    re.compile(r"(system|assistant)\s*:\s*you (are|must|should|will)", re.I),
    re.compile(r"reveal (your|the) (system |)prompt", re.I),
    re.compile(r"print (your|the) (system |)instructions?", re.I),
]

# ── Output patterns to redact ────────────────────────────────────────────────

_SENSITIVE_OUTPUT_PATTERNS: list[tuple[re.Pattern, str]] = [
    # API keys / tokens
    (re.compile(r"(api[_\-]?key|apikey)\s*[:=]\s*\S+", re.I), "[API_KEY_REDACTED]"),
    (re.compile(r"(password|passwd|secret)\s*[:=]\s*\S+", re.I), "[SECRET_REDACTED]"),
    # JWT bearer tokens
    (re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]{20,}=*"), "[TOKEN_REDACTED]"),
    # Environment variable patterns (KEY=value)
    (re.compile(r"\b[A-Z_]{4,}_(?:KEY|SECRET|TOKEN|PASSWORD)\s*=\s*\S+"), "[ENV_REDACTED]"),
]


# ── Public API ───────────────────────────────────────────────────────────────

def check_input(text: str) -> tuple[bool, str]:
    """Validate user input before it enters the pipeline.

    Returns:
        (is_safe: bool, reason: str) — reason is empty string when safe.
    """
    if not text or not text.strip():
        return False, "Input is empty"

    if len(text) > MAX_INPUT_LENGTH:
        return False, f"Input exceeds {MAX_INPUT_LENGTH} characters. Please shorten your message."

    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            logger.warning("Potential prompt injection detected: %.120s", text)
            return False, "Input contains disallowed content"

    return True, ""


# Think block fields that should never appear in user-facing output
_THINK_FIELD_PATTERN = re.compile(
    r"^\s*(?:what_i_know|what_i_need|confidence|next_action):\s*.*$",
    re.IGNORECASE | re.MULTILINE,
)

# Tagged think blocks
_THINK_BLOCK_PATTERN = re.compile(r"<think>.*?</think>\s*", re.DOTALL | re.IGNORECASE)


def sanitize_output(text: str) -> str:
    """Scrub sensitive data patterns and internal reasoning from LLM output."""
    # Strip tagged think blocks
    text = _THINK_BLOCK_PATTERN.sub("", text)
    # Strip naked think fields
    text = _THINK_FIELD_PATTERN.sub("", text)
    # Clean up excessive blank lines left behind
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    # Redact sensitive data
    for pattern, replacement in _SENSITIVE_OUTPUT_PATTERNS:
        text = pattern.sub(replacement, text)
    return text
