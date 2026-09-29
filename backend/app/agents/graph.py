"""Deterministic agent orchestration for the support workflow.

The current topology is a fixed conditional DAG, so a small explicit runner is
more transparent and reproducible than a heavyweight orchestration dependency.
The public ``ainvoke`` API is retained for compatibility with the evaluator.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from app.agents.nodes import (
    generate_node,
    hallucination_check_node,
    injection_response_node,
    input_guard_node,
    retrieval_node,
    save_state_node,
    tool_execution_node,
    tool_response_node,
    tool_router_node,
)
from app.agents.state import AgentState

logger = logging.getLogger(__name__)


class CompiledAgentGraph:
    """Execute the documented support-agent state machine."""

    async def ainvoke(self, state: AgentState) -> Dict[str, Any]:
        current = dict(state)

        current.update(await input_guard_node(current))
        if current.get("injection_detected"):
            current.update(await injection_response_node(current))
            await save_state_node(current)
            return current

        current.update(await tool_router_node(current))
        if current.get("active_tool"):
            current.update(await tool_execution_node(current))
            current.update(await tool_response_node(current))
            await save_state_node(current)
            return current

        current.update(await retrieval_node(current))
        current.update(await generate_node(current))
        current.update(await hallucination_check_node(current))
        await save_state_node(current)
        return current


def build_agent_graph() -> CompiledAgentGraph:
    """Construct the deterministic support-agent runner."""
    graph = CompiledAgentGraph()
    logger.info("Agent graph compiled successfully")
    return graph


agent_graph = build_agent_graph()
