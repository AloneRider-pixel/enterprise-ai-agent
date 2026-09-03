"""
Admin API routes for metrics, evaluation, and system management.
"""
import logging
import time
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_admin_user, get_current_user
from app.database import get_db
from app.models.database import Document, QueryLog, EvaluationRun
from app.models.schemas import EvalRequest, EvalResult, SystemMetrics, HealthResponse
from app.redis_client import redis_client
from app.services.cost_tracker import cost_tracker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Admin & Evaluation"])


# ─── Health Check ───

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """System health check for all dependencies."""
    health = {
        "status": "healthy",
        "version": "1.0.0",
        "database": "unknown",
        "redis": "unknown",
        "openai": "unknown",
    }
    
    # Check PostgreSQL
    try:
        from app.database import engine
        async with engine.connect() as conn:
            await conn.execute(func.now())
        health["database"] = "healthy"
    except Exception as e:
        health["database"] = f"unhealthy: {str(e)[:50]}"
        health["status"] = "degraded"
    
    # Check Redis
    try:
        await redis_client.client.ping()
        health["redis"] = "healthy"
    except Exception as e:
        health["redis"] = f"unhealthy: {str(e)[:50]}"
        health["status"] = "degraded"
    
    # Check OpenAI (simple model list)
    try:
        from openai import AsyncOpenAI
        from app.config import settings
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        await client.models.list()
        health["openai"] = "healthy"
    except Exception as e:
        health["openai"] = f"unhealthy: {str(e)[:50]}"
        health["status"] = "degraded"
    
    return HealthResponse(**health)


# ─── System Metrics ───

@router.get("/admin/metrics", response_model=SystemMetrics)
async def get_metrics(
    admin_user: dict = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Get system-wide metrics and statistics."""
    # Document stats
    doc_count = await db.execute(select(func.count(Document.id)))
    total_documents = doc_count.scalar() or 0
    
    chunk_count = await db.execute(select(func.sum(Document.chunk_count)))
    total_chunks = chunk_count.scalar() or 0
    
    # Query stats
    query_count = await db.execute(select(func.count(QueryLog.id)))
    total_queries = query_count.scalar() or 0
    
    # Latency stats
    avg_latency = await db.execute(
        select(func.avg(QueryLog.latency_ms)).where(QueryLog.latency_ms.isnot(None))
    )
    avg_latency_ms = float(avg_latency.scalar() or 0)
    
    # Redis metrics
    total_cost = await cost_tracker.get_total_cost()
    total_tokens = await cost_tracker.get_total_tokens()
    
    # Active sessions (approximate)
    active_sessions = await redis_client.get_counter("active_sessions")
    
    return SystemMetrics(
        total_documents=total_documents,
        total_chunks=total_chunks,
        total_queries=total_queries,
        avg_latency_ms=round(avg_latency_ms, 2),
        total_cost_usd=round(total_cost, 4),
        active_sessions=active_sessions,
    )


# ─── Evaluation ───

@router.post("/evaluation/run", response_model=EvalResult)
async def run_evaluation(
    request: EvalRequest,
    admin_user: dict = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Run RAG evaluation suite.
    Measures faithfulness, relevance, recall, and latency.
    """
    from app.evaluation.evaluator import evaluate_rag
    
    start_time = time.time()
    
    # Run evaluation
    results = await evaluate_rag(
        dataset_name=request.dataset_name,
        metrics=[m.value for m in request.metrics],
    )
    
    total_latency = (time.time() - start_time) * 1000
    
    # Store results
    eval_run = EvaluationRun(
        id=uuid.uuid4(),
        dataset_name=request.dataset_name,
        num_samples=results.get("num_samples", 0),
        faithfulness=results.get("metrics", {}).get("faithfulness"),
        answer_relevance=results.get("metrics", {}).get("answer_relevance"),
        context_recall=results.get("metrics", {}).get("context_recall"),
        context_precision=results.get("metrics", {}).get("context_precision"),
        avg_latency_ms=results.get("latency_stats", {}).get("avg"),
        total_cost_usd=results.get("cost_usd", 0),
        results=results,
    )
    db.add(eval_run)
    await db.commit()
    
    return EvalResult(
        dataset_name=request.dataset_name,
        metrics=results.get("metrics", {}),
        num_samples=results.get("num_samples", 0),
        latency_stats=results.get("latency_stats", {}),
        cost_usd=results.get("cost_usd", 0),
        timestamp=datetime.utcnow(),
    )


@router.get("/evaluation/results")
async def get_evaluation_results(
    limit: int = 10,
    admin_user: dict = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Get recent evaluation run results."""
    result = await db.execute(
        select(EvaluationRun).order_by(EvaluationRun.created_at.desc()).limit(limit)
    )
    runs = result.scalars().all()
    
    return {
        "runs": [
            {
                "id": str(run.id),
                "dataset_name": run.dataset_name,
                "num_samples": run.num_samples,
                "faithfulness": run.faithfulness,
                "answer_relevance": run.answer_relevance,
                "context_recall": run.context_recall,
                "avg_latency_ms": run.avg_latency_ms,
                "total_cost_usd": run.total_cost_usd,
                "created_at": run.created_at.isoformat() if run.created_at else None,
            }
            for run in runs
        ]
    }


# ─── Query Logs ───

@router.get("/admin/queries")
async def get_query_logs(
    limit: int = 50,
    offset: int = 0,
    admin_user: dict = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Get recent query logs for debugging and analysis."""
    result = await db.execute(
        select(QueryLog)
        .order_by(QueryLog.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    logs = result.scalars().all()
    
    return {
        "logs": [
            {
                "id": str(log.id),
                "session_id": log.session_id,
                "query": log.query[:200],
                "response_preview": (log.response or "")[:200],
                "retrieval_method": log.retrieval_method,
                "chunks_retrieved": log.chunks_retrieved,
                "latency_ms": log.latency_ms,
                "input_tokens": log.input_tokens,
                "output_tokens": log.output_tokens,
                "cost_usd": log.cost_usd,
                "hallucination_score": log.hallucination_score,
                "injection_detected": log.injection_detected,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ],
        "total": len(logs),
    }
