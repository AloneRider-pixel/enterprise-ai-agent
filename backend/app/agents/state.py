"""
LangGraph agent state definition.
Defines the state schema that flows through the agent graph.
"""
from typing import Annotated, Any, Dict, List, Optional, TypedDict

from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """
    State for the Enterprise AI Support Agent.
    
    This state flows through the LangGraph state machine,
    with each node reading/writing specific fields.
    """
    # ─── Conversation ───
    messages: Annotated[list, add_messages]  # Message history (LangGraph managed)
    session_id: str                          # Session identifier
    user_id: str                             # User identifier
    query: str                               # Current user query
    
    # ─── RAG Retrieval ───
    retrieved_chunks: List[Dict[str, Any]]   # Chunks from retrieval
    retrieval_method: str                    # "vector", "keyword", "hybrid"
    reranked_chunks: List[Dict[str, Any]]    # Chunks after reranking
    
    # ─── Tool Calling ───
    tool_calls: List[Dict[str, Any]]         # Tool invocations made
    tool_results: List[Dict[str, Any]]       # Results from tools
    active_tool: Optional[str]               # Currently executing tool
    
    # ─── Response ───
    response: str                            # Final response text
    citations: List[Dict[str, Any]]          # Source citations
    confidence: float                        # Response confidence score
    
    # ─── Safety ───
    injection_detected: bool                 # Prompt injection flag
    hallucination_score: float               # NLI hallucination score
    
    # ─── Observability ───
    token_usage: Dict[str, int]              # Token counts
    cost_usd: float                          # Estimated cost
    latency_ms: float                        # Total latency
    metadata: Dict[str, Any]                 # Additional metadata
    
    # ─── Control Flow ───
    route: str                               # Next node to visit
    needs_human: bool                        # Escalation flag
    max_iterations: int                      # Prevent infinite loops
    iteration: int                           # Current iteration count
