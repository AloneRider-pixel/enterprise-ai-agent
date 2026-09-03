"""
RAG evaluation engine.
Runs evaluation suite measuring faithfulness, relevance, recall, and cost.
"""
import logging
import time
from typing import Dict, List

from app.agents.graph import agent_graph
from app.agents.state import AgentState
from app.evaluation.dataset import get_dataset
from app.evaluation.metrics import (
    compute_answer_relevance,
    compute_context_recall,
    compute_faithfulness,
)
from app.services.cost_tracker import cost_tracker

logger = logging.getLogger(__name__)


async def evaluate_rag(
    dataset_name: str = "default",
    metrics: List[str] = None,
) -> Dict:
    """
    Run full RAG evaluation on a dataset.
    
    For each sample:
    1. Run the query through the RAG pipeline
    2. Measure faithfulness, relevance, recall
    3. Track latency and cost
    
    Returns aggregated metrics.
    """
    if metrics is None:
        metrics = ["faithfulness", "answer_relevance", "context_recall"]
    
    dataset = get_dataset(dataset_name)
    num_samples = len(dataset)
    
    logger.info(f"Starting evaluation: dataset={dataset_name}, samples={num_samples}")
    
    results = []
    latencies = []
    total_cost = 0.0
    
    for i, sample in enumerate(dataset):
        start_time = time.time()
        
        try:
            # Run query through agent
            state: AgentState = {
                "messages": [],
                "session_id": f"eval-{i}",
                "user_id": "eval-system",
                "query": sample["question"],
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
            
            final_state = await agent_graph.ainvoke(state)
            response = final_state.get("response", "")
            chunks = final_state.get("reranked_chunks", final_state.get("retrieved_chunks", []))
            
            latency = (time.time() - start_time) * 1000
            latencies.append(latency)
            
            # Calculate cost
            tokens = final_state.get("token_usage", {})
            sample_cost = tokens.get("input", 0) * 0.00000015 + tokens.get("output", 0) * 0.0000006
            total_cost += sample_cost
            
            # Compute metrics for this sample
            sample_result = {
                "question": sample["question"],
                "ground_truth": sample["ground_truth"],
                "generated_answer": response,
                "latency_ms": round(latency, 2),
                "cost_usd": round(sample_cost, 6),
            }
            
            if "faithfulness" in metrics:
                sample_result["faithfulness"] = compute_faithfulness(
                    response, sample.get("context", "")
                )
            
            if "answer_relevance" in metrics:
                sample_result["answer_relevance"] = compute_answer_relevance(
                    sample["question"], response
                )
            
            if "context_recall" in metrics:
                sample_result["context_recall"] = compute_context_recall(
                    sample["ground_truth"],
                    " ".join(c.get("content", "") for c in chunks[:4]) if chunks else "",
                )
            
            results.append(sample_result)
            logger.info(f"Eval sample {i + 1}/{num_samples}: latency={latency:.0f}ms")
        
        except Exception as e:
            logger.error(f"Eval sample {i} failed: {e}")
            results.append({
                "question": sample["question"],
                "error": str(e),
            })
    
    # Aggregate metrics
    agg_metrics = {}
    
    if "faithfulness" in metrics:
        scores = [r.get("faithfulness", 0) for r in results if "faithfulness" in r]
        agg_metrics["faithfulness"] = round(sum(scores) / len(scores), 4) if scores else 0
    
    if "answer_relevance" in metrics:
        scores = [r.get("answer_relevance", 0) for r in results if "answer_relevance" in r]
        agg_metrics["answer_relevance"] = round(sum(scores) / len(scores), 4) if scores else 0
    
    if "context_recall" in metrics:
        scores = [r.get("context_recall", 0) for r in results if "context_recall" in r]
        agg_metrics["context_recall"] = round(sum(scores) / len(scores), 4) if scores else 0
    
    # Latency stats
    latencies.sort()
    latency_stats = {}
    if latencies:
        n = len(latencies)
        latency_stats = {
            "count": n,
            "avg": round(sum(latencies) / n, 2),
            "p50": round(latencies[n // 2], 2),
            "p95": round(latencies[min(int(n * 0.95), n - 1)], 2),
            "p99": round(latencies[min(int(n * 0.99), n - 1)], 2),
            "min": round(latencies[0], 2),
            "max": round(latencies[-1], 2),
        }
    
    logger.info(
        f"Evaluation complete: {num_samples} samples, "
        f"metrics={agg_metrics}, latency_p50={latency_stats.get('p50', 0):.0f}ms"
    )
    
    return {
        "dataset_name": dataset_name,
        "num_samples": num_samples,
        "metrics": agg_metrics,
        "latency_stats": latency_stats,
        "cost_usd": round(total_cost, 6),
        "results": results,
    }
