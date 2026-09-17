from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass


@dataclass(frozen=True)
class ToolCall:
    actor: str
    tool: str
    scope: str
    arguments: dict[str, str]
    external_content: bool = False


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str
    audit_id: str


def _audit_id(call: ToolCall) -> str:
    payload = json.dumps(
        {
            "actor": call.actor,
            "tool": call.tool,
            "scope": call.scope,
            "arguments": call.arguments,
            "external_content": call.external_content,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def authorize(
    call: ToolCall,
    *,
    allowed_tools: frozenset[str] = frozenset({"search", "retrieve", "create_draft"}),
    dangerous_keys: frozenset[str] = frozenset({"shell", "command", "eval", "sudo"}),
) -> Decision:
    audit_id = _audit_id(call)
    if not call.actor.strip() or not call.scope.strip():
        return Decision(False, "invalid_identity", audit_id)
    if call.tool not in allowed_tools:
        return Decision(False, "tool_not_allowlisted", audit_id)
    if call.external_content and call.tool == "create_draft":
        return Decision(False, "external_content_cannot_authorize_action", audit_id)
    if any(key.lower() in dangerous_keys for key in call.arguments):
        return Decision(False, "dangerous_argument", audit_id)
    return Decision(True, "allow_policy", audit_id)
