"""
CONSTITUTIONAL AI: Safety Layer

Checks all tasks against constitutional principles before processing.
Blocks harmful, dangerous, or unethical tasks.
"""
import re
from datetime import datetime

BLOCKED_PATTERNS = [
    r"how to (make|build|create) (a )?(bomb|weapon|explosive|poison)",
    r"hack(ing)? (into|someone|system|account)",
    r"(steal|fraud|scam|phish)",
    r"(child|minor).*(exploit|abuse|harm)",
    r"(terror|extremist|violent).*(attack|plan|method)",
]

REDACTION_PATTERNS = [
    (r"\b\d{3}-\d{2}-\d{4}\b", "[SSN_REDACTED]"),
    (r"\b\d{16}\b", "[CARD_REDACTED]"),
    (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "[EMAIL_REDACTED]"),
]


class ConstitutionalAI:
    """Constitutional AI: Safety layer for all SOV processing."""

    def __init__(self):
        self.principles = [
            "Do no harm",
            "Respect privacy",
            "Be truthful",
            "Be helpful",
            "Follow the law",
        ]
        self.check_count = 0
        self.block_count = 0

    def check(self, task):
        """Check task against constitutional principles."""
        self.check_count += 1
        desc = task if isinstance(task, str) else task.get("description", str(task))
        desc_lower = desc.lower()

        # Check blocked patterns
        for pattern in BLOCKED_PATTERNS:
            if re.search(pattern, desc_lower):
                self.block_count += 1
                return {
                    "safe": False,
                    "reason": f"Blocked by constitutional principle: {pattern}",
                    "principle_violated": "Do no harm",
                }

        # Redact sensitive data
        redacted = desc
        for pattern, replacement in REDACTION_PATTERNS:
            redacted = re.sub(pattern, replacement, redacted)

        return {
            "safe": True,
            "redacted": redacted != desc,
            "principles_checked": self.principles,
            "timestamp": datetime.now().isoformat(),
        }

    def get_status(self):
        return {
            "checks": self.check_count,
            "blocks": self.block_count,
            "block_rate": self.block_count / max(self.check_count, 1),
            "principles": self.principles,
        }
