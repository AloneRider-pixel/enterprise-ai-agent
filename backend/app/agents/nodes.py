"""
LangGraph agent nodes.
Each node is a function that processes the agent state and returns updates.
"""
import json
import logging
import re
import time
from typing import Any, Dict, List

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from app.agents.state import AgentState
from app.agents.tools import TOOL_MAP
from app.config import settings
from app.rag.generator import rag_generator
from app.rag.retrieval import retrieval_service
from app.rag.reranking import reranker_service
from app.redis_client import redis_client
from app.services.hallucination import hallucination_detector
from app.services.cost_tracker import cost_tracker

logger = logging.getLogger(__name__)


# ─── Node: Input Guard ───

async def input_guard_node(state: AgentState) -> Dict:
    """
    Check for prompt injection attempts.
    Sets injection_detected flag if malicious input is found.
    """
    query = state.get("query", "")
    
    # Prompt injection detection patterns
    injection_patterns = [
        r"ignore\s+(all\s+)?(previous|above|prior)\s+(instructions?|prompts?)",
        r"you\s+are\s+(now\s+)?a",
        r"disregard\s+(your|all|the)\s+(instructions?|rules?|guidelines?)",
        r"new\s+instructions?:",
        r"system\s*:",
        r"assistant\s*:",
        r"forget\s+(everything|all|your)",
        r"pretend\s+you\s+(are|have|can)",
        r"act\s+as\s+(if\s+)?(you\s+are|a|an)",
        r"what\s+were\s+you\s+(told|instructed|programmed)",
        r"reveal\s+your\s+(system\s+)?(prompt|instructions?)",
        r"do\s+not\s+follow\s+(your\s+)?(rules?|instructions?)",
    ]
    
    query_lower = query.lower()
    detected = False
    for pattern in injection_patterns:
        if re.search(pattern, query_lower):
            detected = True
            logger.warning(f"Prompt injection detected: pattern={pattern}")
            break
    
    return {
        "injection_detected": detected,
        "iteration": state.get("iteration", 0) + 1,
    }


# ─── Node: Retrieval ───

async def retrieval_node(state: AgentState) -> Dict:
    """
    Retrieve relevant context from the knowledge base.
    Uses hybrid search (vector + keyword) then reranks results.
    """
    start_time = time.time()
    query = state.get("query", "")
    
    # Check Redis cache first
    cache_key = f"retrieval:{hash(query)}"
    cached = await redis_client.cache_get(cache_key)
    if cached:
        logger.info("Retrieval cache HIT")
        return {
            "retrieved_chunks": cached["chunks"],
            "reranked_chunks": cached["chunks"],
            "retrieval_method": cached["method"],
        }
    
    # Hybrid retrieval
    retrieval_result = await retrieval_service.retrieve(query, method="hybrid")
    chunks = retrieval_result["chunks"]
    
    # Rerank
    reranked = await reranker_service.rerank(query, chunks)
    
    # Cache results
    await redis_client.cache_set(
        cache_key,
        {"chunks": reranked, "method": "hybrid"},
        ttl=300,  # 5 minutes
    )
    
    latency = (time.time() - start_time) * 1000
    logger.info(f"Retrieval complete: {len(reranked)} chunks in {latency:.0f}ms")
    
    return {
        "retrieved_chunks": chunks,
        "reranked_chunks": reranked,
        "retrieval_method": retrieval_result["retrieval_method"],
    }


# ─── Node: Generate Response ───

async def generate_node(state: AgentState) -> Dict:
    """
    Generate response using RAG with retrieved context.
    Includes citation tracking and token usage.
    """
    start_time = time.time()
    query = state.get("query", "")
    chunks = state.get("reranked_chunks", state.get("retrieved_chunks", []))
    
    # Get conversation history from Redis
    session_id = state.get("session_id", "")
    history = await redis_client.get_messages(session_id, limit=6)
    
    # Generate response
    result = await rag_generator.generate(query, chunks, history)
    
    # Calculate cost
    tokens = result.get("tokens", {})
    cost = rag_generator.calculate_cost(
        tokens.get("input", 0),
        tokens.get("output", 0),
    )
    
    latency = (time.time() - start_time) * 1000
    
    return {
        "response": result["response"],
        "citations": result.get("citations", []),
        "token_usage": tokens,
        "cost_usd": state.get("cost_usd", 0) + cost,
        "latency_ms": state.get("latency_ms", 0) + latency,
    }


# ─── Node: Hallucination Check ───

async def hallucination_check_node(state: AgentState) -> Dict:
    """
    Verify response faithfulness using NLI-based hallucination detection.
    """
    response = state.get("response", "")
    chunks = state.get("reranked_chunks", [])
    
    if not response or not chunks:
        return {"hallucination_score": 0.0}
    
    # Build context from chunks
    context = " ".join(chunk["content"] for chunk in chunks[:4])
    
    # Detect hallucination
    score = await hallucination_detector.detect(response, context)
    
    if score > settings.hallucination_threshold:
        logger.warning(f"High hallucination score: {score:.3f}")
    
    return {"hallucination_score": score}


# ─── Node: Tool Router ───

async def tool_router_node(state: AgentState) -> Dict:
    """
    Determine if a tool needs to be called.
    Routes to appropriate tool based on query intent.
    """
    query = state.get("query", "").lower()
    
    # Intent classification patterns
    tool_intents = {
        "lookup_order": [
            "order status", "track order", "where is my order",
            "order details", "check order", "order id",
        ],
        "process_refund": [
            "refund", "money back", "return", "cancel order",
            "charge back", "want my money",
        ],
        "search_knowledge_base": [
            "how to", "what is", "help with", "guide",
            "documentation", "tutorial", "explain",
        ],
        "escalate_to_human": [
            "talk to human", "speak to agent", "real person",
            "transfer me", "escalate", "manager",
        ],
    }
    
    for tool_name, patterns in tool_intents.items():
        for pattern in patterns:
            if pattern in query:
                return {"active_tool": tool_name, "route": "execute_tool"}
    
    return {"active_tool": None, "route": "generate"}


# ─── Node: Tool Execution ───

async def tool_execution_node(state: AgentState) -> Dict:
    """
    Execute the selected tool and store results.
    """
    tool_name = state.get("active_tool")
    query = state.get("query", "")
    
    if not tool_name or tool_name not in TOOL_MAP:
        return {"tool_results": [], "route": "generate"}
    
    tool_fn = TOOL_MAP[tool_name]
    
    try:
        # Execute tool with appropriate arguments
        if tool_name == "lookup_order":
            # Extract order ID from query
            import re
            order_match = re.search(r"ORD-\d+", query, re.IGNORECASE)
            order_id = order_match.group(0).upper() if order_match else "ORD-001"
            result = tool_fn.invoke({"order_id": order_id})
        
        elif tool_name == "process_refund":
            import re
            order_match = re.search(r"ORD-\d+", query, re.IGNORECASE)
            order_id = order_match.group(0).upper() if order_match else "ORD-001"
            result = tool_fn.invoke({"order_id": order_id, "reason": query})
        
        elif tool_name == "search_knowledge_base":
            result = tool_fn.invoke({"query": query})
        
        elif tool_name == "escalate_to_human":
            result = tool_fn.invoke({"reason": query, "priority": "normal"})
        
        else:
            result = tool_fn.invoke({})
        
        logger.info(f"Tool {tool_name} executed successfully")
        
        return {
            "tool_results": [{
                "tool": tool_name,
                "result": result,
                "success": True,
            }],
            "tool_calls": state.get("tool_calls", []) + [{"tool": tool_name, "query": query}],
        }
    
    except Exception as e:
        logger.error(f"Tool execution error: {e}")
        return {
            "tool_results": [{
                "tool": tool_name,
                "error": str(e),
                "success": False,
            }],
        }


# ─── Node: Response with Tool Results ───

async def tool_response_node(state: AgentState) -> Dict:
    """
    Generate final response incorporating tool results.
    """
    tool_results = state.get("tool_results", [])
    query = state.get("query", "")
    
    if not tool_results:
        return {"response": "I couldn't process your request. Please try again."}
    
    # Build response from tool results
    result_data = tool_results[0]
    tool_name = result_data.get("tool", "unknown")
    
    try:
        result_json = json.loads(result_data.get("result", "{}"))
    except (json.JSONDecodeError, TypeError):
        result_json = {"raw": result_data.get("result", "")}
    
    # Format response based on tool
    if tool_name == "lookup_order":
        if result_json.get("success"):
            order = result_json["order"]
            response = (
                f"I found your order **{order['order_id']}**.\n\n"
                f"**Status:** {order['status'].title()}\n"
                f"**Total:** ${order['total']:.2f}\n"
                f"**Items:** {', '.join(item['name'] for item in order['items'])}\n"
            )
            if order.get("shipping", {}).get("tracking"):
                response += f"**Tracking:** {order['shipping']['tracking']}\n"
        else:
            response = f"Sorry, {result_json.get('error', 'Order not found.')} Would you like me to look up a different order?"
    
    elif tool_name == "process_refund":
        if result_json.get("eligible"):
            response = (
                f"Good news! Your refund has been initiated.\n\n"
                f"**Refund ID:** {result_json['refund_id']}\n"
                f"**Amount:** ${result_json['refund_amount']:.2f}\n"
                f"**Processing time:** {result_json['estimated_processing_days']} business days\n\n"
                "You'll receive a confirmation email shortly."
            )
        else:
            response = f"Unfortunately, {result_json.get('reason', 'this order is not eligible for a refund.')} Would you like to speak with a human agent about your situation?"
    
    elif tool_name == "escalate_to_human":
        response = (
            f"I've escalated your request to a human agent.\n\n"
            f"**Ticket ID:** {result_json.get('ticket_id', 'N/A')}\n"
            f"**Priority:** {result_json.get('priority', 'normal')}\n"
            f"**Estimated wait:** ~{result_json.get('estimated_wait_minutes', 15)} minutes\n\n"
            "A support specialist will be with you shortly. Is there anything else I can help with in the meantime?"
        )
    
    elif tool_name == "search_knowledge_base":
        results = result_json.get("results", [])
        if results:
            response = "Here are some helpful resources:\n\n"
            for article in results[:3]:
                response += f"• **{article['title']}** - {article['summary']}\n"
            response += "\nWould you like more details on any of these?"
        else:
            response = "I couldn't find specific articles for your query. Let me try to answer directly or connect you with a human agent."
    
    else:
        response = f"I processed your request using the {tool_name} tool. Here are the results: {str(result_json)}"
    
    return {"response": response, "needs_human": tool_name == "escalate_to_human"}


# ─── Node: Save State ───

async def save_state_node(state: AgentState) -> Dict:
    """
    Save conversation state to Redis and log query metrics.
    """
    session_id = state.get("session_id", "")
    
    # Store messages in Redis
    if state.get("query"):
        await redis_client.store_message(session_id, "user", state["query"])
    if state.get("response"):
        await redis_client.store_message(
            session_id, "assistant", state["response"],
            metadata={
                "citations": state.get("citations", []),
                "tool_calls": state.get("tool_calls", []),
            },
        )
    
    # Update metrics
    await redis_client.increment_counter("total_queries")
    if state.get("cost_usd", 0) > 0:
        await redis_client.increment_counter("total_cost_millis", int(state["cost_usd"] * 10000))
    
    # Store latency
    if state.get("latency_ms", 0) > 0:
        await redis_client.store_latency("chat", state["latency_ms"])
    
    return {}


# ─── Routing Functions ───

def should_inject_block(state: AgentState) -> str:
    """Route after injection check."""
    if state.get("injection_detected"):
        return "injection_response"
    return "route_or_retrieve"


def should_use_tool(state: AgentState) -> str:
    """Route after tool routing."""
    if state.get("active_tool"):
        return "execute_tool"
    return "retrieve"
