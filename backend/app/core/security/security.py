"""Security Engine (M06) — permissions, policies, audit log.

Single-user system, so auth is a shared secret token (optional);
the real value is the audit trail + policy enforcement on risky tools.
"""
from __future__ import annotations

import hashlib
import hmac
import os

from app.core.memory.store import new_id, now_iso, store

AUDIT_COLLECTION = "audit"

# Which tools each permission level may use.
ROLE_TOOLS = {
    "user": {"web_search", "memory_search", "create_task", "save_memory"},
    "system": {"web_search", "memory_search", "create_task", "save_memory"},
}

# Tools that ALWAYS require explicit approval regardless of agent.
ALWAYS_APPROVAL_TOOLS: set[str] = set()


class Permissions:
    @staticmethod
    def can_use_tool(role: str, tool: str) -> bool:
        return tool in ROLE_TOOLS.get(role, set())

    @staticmethod
    def needs_approval(tool: str) -> bool:
        return tool in ALWAYS_APPROVAL_TOOLS


class Audit:
    @staticmethod
    def log(actor: str, action: str, detail: dict | None = None) -> str:
        entry_id = new_id()
        store.put(AUDIT_COLLECTION, entry_id, {
            "actor": actor, "action": action, "detail": detail or {},
            "created_at": now_iso(),
        })
        return entry_id

    @staticmethod
    def recent(limit: int = 50) -> list[dict]:
        return store.list(AUDIT_COLLECTION, limit=limit)

    @staticmethod
    def tail(limit: int = 10) -> list[dict]:
        return Audit.recent(limit)


class Auth:
    """Shared-secret auth. If APP_TOKEN is unset, all requests are allowed (local dev)."""

    @staticmethod
    def _expected() -> str | None:
        return os.environ.get("APP_TOKEN") or None

    @classmethod
    def check(cls, token: str | None) -> bool:
        expected = cls._expected()
        if expected is None:
            return True
        return bool(token) and hmac.compare_digest(hashlib.sha256(token.encode()).hexdigest(),
                                                   hashlib.sha256(expected.encode()).hexdigest())


permissions = Permissions()
audit = Audit()
auth = Auth()
