from portfolio_hardening.tool_policy import ToolCall, authorize


def test_safe_retrieval_is_allowed() -> None:
    decision = authorize(ToolCall("agent", "retrieve", "documents", {"query": "policy"}))
    assert decision.allowed is True
    assert decision.reason == "allow_policy"


def test_unknown_tool_is_denied() -> None:
    decision = authorize(ToolCall("agent", "shell", "system", {}))
    assert decision.allowed is False
    assert decision.reason == "tool_not_allowlisted"


def test_external_content_cannot_authorize_action() -> None:
    decision = authorize(
        ToolCall("agent", "create_draft", "repo", {"title": "change"}, external_content=True)
    )
    assert decision.allowed is False


def test_dangerous_argument_is_denied() -> None:
    decision = authorize(ToolCall("agent", "search", "repo", {"command": "rm -rf /"}))
    assert decision.allowed is False
    assert decision.reason == "dangerous_argument"
