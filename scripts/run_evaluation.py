"""
Evaluation runner script.
Runs the RAG evaluation suite and prints results.
"""
import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.evaluation.evaluator import evaluate_rag


async def main():
    print("=" * 60)
    print("  RAG EVALUATION SUITE")
    print("=" * 60)
    
    # Run evaluation
    results = await evaluate_rag(
        dataset_name="default",
        metrics=["faithfulness", "answer_relevance", "context_recall"],
    )
    
    # Print summary
    print("\n" + "=" * 60)
    print("  RESULTS SUMMARY")
    print("=" * 60)
    
    print(f"\n  Dataset: {results['dataset_name']}")
    print(f"  Samples: {results['num_samples']}")
    print(f"  Total Cost: ${results['cost_usd']:.6f}")
    
    print("\n  Metrics:")
    for metric, score in results["metrics"].items():
        bar = "█" * int(score * 20) + "░" * (20 - int(score * 20))
        print(f"    {metric:25s} {bar} {score:.4f}")
    
    print("\n  Latency:")
    for stat, value in results.get("latency_stats", {}).items():
        print(f"    {stat:10s} {value:.0f}ms")
    
    # Print per-sample results
    print("\n" + "-" * 60)
    print("  PER-SAMPLE RESULTS")
    print("-" * 60)
    
    for i, sample in enumerate(results.get("results", [])):
        print(f"\n  [{i+1}] {sample.get('question', 'N/A')[:60]}")
        if "error" in sample:
            print(f"      Error: {sample['error']}")
        else:
            metrics_str = ", ".join(
                f"{k}={v:.3f}" for k, v in sample.items()
                if isinstance(v, float)
            )
            print(f"      {metrics_str}")
            print(f"      Latency: {sample.get('latency_ms', 0):.0f}ms")
    
    print("\n" + "=" * 60)
    
    # Save results to file
    os.makedirs("../evaluation", exist_ok=True)
    with open("../evaluation/results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    
    print("\n✅ Results saved to evaluation/results.json")


if __name__ == "__main__":
    asyncio.run(main())
