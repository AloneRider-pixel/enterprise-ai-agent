"""
LangGraph agent graph definition.
Defines the state machine flow for the Enterprise AI Support Agent.

Flow:
  Input → Input Guard → Tool Router → [Tool Path | RAG Path] → Response → Hallucination Check → Save
"""
import logging
from typing import Dict

from langgraph.graph import END, START, StateGraph

from app.agents.nodes import (
    generate_node,
    hallucination_check_node,
    input_guard_node,
    retrieval_node,
    save_state_node,
    tool_execution_node,
    tool_response_node,
    tool_router_node,
    should_inject_block,
    should_use_tool,
)
from app.agents.state import AgentState

logger = logging.getLogger(__name__)


# ─── Blocked Response for Injection ───

async def injection_response_node(state: AgentState) -> Dict:
    """Return a safe response when injection is detected."""
    return {
        "response": (
            "I'm sorry, but I detected an unusual request pattern. "
            "For security purposes, I can only respond to standard support queries. "
            "If you need help, please describe your issue and I'll do my best to assist."
        ),
        "citations": [],
        "needs_human": False,
    }


# ─── Build the Graph ───

def build_agent_graph() -> StateGraph:
    """
    Construct the LangGraph state machine.
    
    Graph topology:
    
    START
      → input_guard
        → [injection detected] → injection_response → END
        → [clean] → tool_router
          → [needs tool] → tool_execution → tool_response → save_state → END
          → [no tool] → retrieval → generate → hallucination_check → save_state → END
    """
    
    graph = StateGraph(AgentState)
    
    # ─── Add Nodes ───
    graph.add_node("input_guard", input_guard_node)
    graph.add_node("injection_response", injection_response_node)
    graph.add_node("tool_router", tool_router_node)
    graph.add_node("tool_execution", tool_execution_node)
    graph.add_node("tool_response", tool_response_node)
    graph.add_node("retrieval", retrieval_node)
    graph.add_node("generate", generate_node)
    graph.add_node("hallucination_check", hallucination_check_node)
    graph.add_node("save_state", save_state_node)
    
    # ─── Edges ───
    
    # START → input_guard
    graph.add_edge(START, "input_guard")
    
    # input_guard → conditional routing
    graph.add_conditional_edges(
        "input_guard",
        should_inject_block,
        {
            "injection_response": "injection_response",
            "route_or_retrieve": "tool_router",
        },
    )
    
    # injection_response → END
    graph.add_edge("injection_response", END)
    
    # tool_router → conditional routing
    graph.add_conditional_edges(
        "tool_router",
        should_use_tool,
        {
            "execute_tool": "tool_execution",
            "retrieve": "retrieval",
        },
    )
    
    # Tool path: execution → response → save → END
    graph.add_edge("tool_execution", "tool_response")
    graph.add_edge("tool_response", "save_state")
    graph.add_edge("save_state", END)
    
    # RAG path: retrieval → generate → hallucination check → save → END
    graph.add_edge("retrieval", "generate")
    graph.add_edge("generate", "hallucination_check")
    graph.add_edge("hallucination_check", "save_state")
    
    # Compile the graph
    compiled = graph.compile()
    logger.info("Agent graph compiled successfully")
    
    return compiled


# Singleton compiled graph
agent_graph = build_agent_graph()
