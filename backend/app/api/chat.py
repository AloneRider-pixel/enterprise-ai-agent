"""
Chat API routes.
Handles streaming and non-streaming chat with the AI agent.
"""
import asyncio
import json
import logging
import time
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.graph import agent_graph
from app.agents.state import AgentState
from app.auth.dependencies import get_current_user
from app.database import get_db

from app.models.database import ChatSession, QueryLog
from app.models.schemas import ChatMessage, ChatResponse, ConversationHistory
from app.redis_client import redis_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["Chat"])


@router.post("")
async def chat(
    message: ChatMessage,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Send a message to the AI agent.
    
    Supports both streaming (SSE) and non-streaming responses.
    Returns real-time token-by-token output when streaming is enabled.
    """
    start_time = time.time()
    session_id = message.session_id
    
    # Check rate limit
    rate_limit = await redis_client.check_rate_limit(current_user["user_id"])
    if not rate_limit["allowed"]:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Try again in {int(rate_limit['reset_at'] - time.time())}s",
            headers={"X-RateLimit-Remaining": "0"},
        )
    
    # Initialize agent state
    initial_state: AgentState = {
        "messages": [],
        "session_id": session_id,
        "user_id": current_user["user_id"],
        "query": message.message,
        "retrieved_chunks": [],
        "retrieval_method": "",
        "reranked_chunks": [],
        "tool_calls": [],
        "tool_results": [],
        "active_tool": None,
        "response": "",
        "citations": [],
        "confidence": 0.0,
        "injection_detected": False,
        "hallucination_score": 0.0,
        "token_usage": {},
        "cost_usd": 0.0,
        "latency_ms": 0.0,
        "metadata": {},
        "route": "",
        "needs_human": False,
        "max_iterations": 3,
        "iteration": 0,
    }
    
    if message.stream:
        # Streaming response via SSE
        return StreamingResponse(
            _stream_response(initial_state, session_id, current_user, db),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    else:
        # Non-streaming response
        final_state = await agent_graph.ainvoke(initial_state)
        
        latency = (time.time() - start_time) * 1000
        
        # Log query
        await _log_query(
            db=db,
            session_id=session_id,
            user_id=current_user["user_id"],
            query=message.message,
            response=final_state.get("response", ""),
            retrieval_method=final_state.get("retrieval_method", ""),
            chunks_retrieved=len(final_state.get("retrieved_chunks", [])),
            tools_called=final_state.get("tool_calls", []),
            citations=final_state.get("citations", []),
            latency_ms=latency,
            token_usage=final_state.get("token_usage", {}),
            cost_usd=final_state.get("cost_usd", 0),
            hallucination_score=final_state.get("hallucination_score", 0),
            injection_detected=final_state.get("injection_detected", False),
        )
        
        return ChatResponse(
            session_id=session_id,
            message=final_state.get("response", ""),
            citations=final_state.get("citations", []),
            tool_calls=final_state.get("tool_calls", []),
            metadata={
                "latency_ms": latency,
                "retrieval_method": final_state.get("retrieval_method", ""),
                "chunks_retrieved": len(final_state.get("retrieved_chunks", [])),
                "hallucination_score": final_state.get("hallucination_score", 0),
                "cost_usd": final_state.get("cost_usd", 0),
            },
        )


async def _stream_response(initial_state, session_id, current_user, db):
    """Generate SSE streaming response from the agent."""
    start_time = time.time()
    full_response = []
    
    try:
        # Run the agent graph
        final_state = await agent_graph.ainvoke(initial_state)
        response_text = final_state.get("response", "")
        
        # Stream the response character by character for SSE effect
        for char in response_text:
            full_response.append(char)
            event_data = json.dumps({
                "event": "token",
                "content": char,
            })
            yield f"data: {event_data}\n\n"
            await asyncio.sleep(0.01)  # Small delay for streaming effect
        
        # Send citations
        citations = final_state.get("citations", [])
        yield f"data: {json.dumps({'event': 'citations', 'sources': citations})}\n\n"
        
        # Send tool calls info
        tool_calls = final_state.get("tool_calls", [])
        if tool_calls:
            yield f"data: {json.dumps({'event': 'tool_calls', 'calls': tool_calls})}\n\n"
        
        # Send done event with metadata
        latency = (time.time() - start_time) * 1000
        yield f"data: {json.dumps({'event': 'done', 'metadata': {'latency_ms': latency}})}\n\n"
        
        # Log query
        await _log_query(
            db=db,
            session_id=session_id,
            user_id=current_user["user_id"],
            query=initial_state["query"],
            response=response_text,
            retrieval_method=final_state.get("retrieval_method", ""),
            chunks_retrieved=len(final_state.get("retrieved_chunks", [])),
            tools_called=tool_calls,
            citations=citations,
            latency_ms=latency,
            token_usage=final_state.get("token_usage", {}),
            cost_usd=final_state.get("cost_usd", 0),
            hallucination_score=final_state.get("hallucination_score", 0),
            injection_detected=final_state.get("injection_detected", False),
        )
    
    except Exception as e:
        logger.error(f"Streaming error: {e}")
        yield f"data: {json.dumps({'event': 'error', 'message': str(e)})}\n\n"


async def _log_query(
    db: AsyncSession,
    session_id: str,
    user_id: str,
    query: str,
    response: str,
    retrieval_method: str,
    chunks_retrieved: int,
    tools_called: list,
    citations: list,
    latency_ms: float,
    token_usage: dict,
    cost_usd: float,
    hallucination_score: float,
    injection_detected: bool,
):
    """Log query to database for observability."""
    try:
        log_entry = QueryLog(
            id=uuid.uuid4(),
            session_id=session_id,
            user_id=uuid.UUID(user_id) if isinstance(user_id, str) and len(user_id) == 36 else user_id,
            query=query,
            response=response,
            retrieval_method=retrieval_method,
            chunks_retrieved=chunks_retrieved,
            tools_called=tools_called,
            citations=citations,
            latency_ms=latency_ms,
            input_tokens=token_usage.get("input", 0),
            output_tokens=token_usage.get("output", 0),
            cost_usd=cost_usd,
            hallucination_score=hallucination_score,
            injection_detected=injection_detected,
        )
        db.add(log_entry)
        
        # Update or create chat session
        result = await db.execute(
            select(ChatSession).where(ChatSession.id == session_id)
        )
        session = result.scalar_one_or_none()
        
        if not session:
            session = ChatSession(
                id=session_id,
                user_id=uuid.UUID(user_id) if isinstance(user_id, str) and len(user_id) == 36 else user_id,
                message_count=1,
                total_tokens=token_usage.get("total", 0),
                total_cost=cost_usd,
            )
            db.add(session)
        else:
            session.message_count += 1
            session.total_tokens += token_usage.get("total", 0)
            session.total_cost += cost_usd
        
        await db.commit()
    except Exception as e:
        logger.error(f"Failed to log query: {e}")
        await db.rollback()


@router.get("/history/{session_id}", response_model=ConversationHistory)
async def get_history(
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get conversation history for a session."""
    messages = await redis_client.get_messages(session_id, limit=50)
    
    return ConversationHistory(
        session_id=session_id,
        messages=messages,
    )


@router.delete("/history/{session_id}")
async def clear_history(
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Clear conversation history for a session."""
    await redis_client.clear_session(session_id)
    return {"status": "cleared", "session_id": session_id}
