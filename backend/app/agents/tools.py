"""
Agent tools for function calling.
Implements Order Lookup, Refund Processing, Search, and Human Escalation.
"""
import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


# ─── Mock Data (replace with real DB/API calls in production) ───

MOCK_ORDERS = {
    "ORD-001": {
        "order_id": "ORD-001",
        "customer_email": "john@example.com",
        "status": "delivered",
        "items": [{"name": "Pro Plan Subscription", "quantity": 1, "price": 99.99}],
        "total": 99.99,
        "created_at": "2024-01-15T10:30:00Z",
        "shipping": {"method": "digital", "tracking": None},
    },
    "ORD-002": {
        "order_id": "ORD-002",
        "customer_email": "jane@example.com",
        "status": "shipped",
        "items": [{"name": "Enterprise License", "quantity": 5, "price": 499.99}],
        "total": 2499.95,
        "created_at": "2024-02-20T14:15:00Z",
        "shipping": {"method": "express", "tracking": "TRK-987654321"},
    },
    "ORD-003": {
        "order_id": "ORD-003",
        "customer_email": "bob@example.com",
        "status": "processing",
        "items": [{"name": "Starter Plan", "quantity": 1, "price": 29.99}],
        "total": 29.99,
        "created_at": "2024-03-01T09:00:00Z",
        "shipping": {"method": "digital", "tracking": None},
    },
}

MOCK_REFUND_POLICY = {
    "eligible_statuses": ["delivered", "shipped"],
    "refund_window_days": 30,
    "restock_fee_percent": 0,
    "digital_items": "non_refundable_after_activation",
}


# ─── Tool Definitions ───

@tool
def lookup_order(order_id: str) -> str:
    """
    Look up order details by order ID.
    Use this when the customer asks about their order status, 
    tracking information, or order details.
    
    Args:
        order_id: The order identifier (e.g., "ORD-001")
    
    Returns:
        JSON string with order details including status, items, and tracking.
    """
    logger.info(f"Tool call: lookup_order({order_id})")
    
    order = MOCK_ORDERS.get(order_id.upper())
    if not order:
        return json.dumps({
            "success": False,
            "error": f"Order {order_id} not found. Please verify the order ID.",
        })
    
    return json.dumps({
        "success": True,
        "order": order,
    })


@tool
def process_refund(order_id: str, reason: str) -> str:
    """
    Check refund eligibility and initiate refund process.
    Use this when the customer requests a refund.
    
    Args:
        order_id: The order identifier
        reason: Reason for the refund request
    
    Returns:
        JSON string with refund eligibility and status.
    """
    logger.info(f"Tool call: process_refund({order_id}, reason={reason})")
    
    order = MOCK_ORDERS.get(order_id.upper())
    if not order:
        return json.dumps({
            "success": False,
            "error": f"Order {order_id} not found.",
        })
    
    # Check eligibility
    order_date = datetime.fromisoformat(order["created_at"].replace("Z", "+00:00"))
    days_since_order = (datetime.now(order_date.tzinfo) - order_date).days
    
    is_eligible = (
        order["status"] in MOCK_REFUND_POLICY["eligible_statuses"]
        and days_since_order <= MOCK_REFUND_POLICY["refund_window_days"]
    )
    
    if not is_eligible:
        return json.dumps({
            "success": False,
            "eligible": False,
            "reason": (
                f"Refund not available. Order status: {order['status']}, "
                f"days since purchase: {days_since_order} "
                f"(window: {MOCK_REFUND_POLICY['refund_window_days']} days)"
            ),
        })
    
    # Process refund
    refund_id = f"REF-{uuid.uuid4().hex[:8].upper()}"
    
    return json.dumps({
        "success": True,
        "eligible": True,
        "refund_id": refund_id,
        "refund_amount": order["total"],
        "original_order": order_id,
        "reason": reason,
        "estimated_processing_days": 5,
        "status": "refund_initiated",
    })


@tool
def search_knowledge_base(query: str, category: str = "all") -> str:
    """
    Search the knowledge base for relevant articles and documentation.
    Use this for general information queries about products, policies, or procedures.
    
    Args:
        query: Search query text
        category: Category filter ("all", "billing", "technical", "policy", "faq")
    
    Returns:
        JSON string with matching articles.
    """
    logger.info(f"Tool call: search_knowledge_base(query={query}, category={category})")
    
    # Mock knowledge base articles
    articles = [
        {
            "id": "KB-001",
            "title": "How to Reset Your Password",
            "category": "technical",
            "summary": "Step-by-step guide to resetting your account password.",
            "url": "/help/password-reset",
        },
        {
            "id": "KB-002",
            "title": "Billing FAQ",
            "category": "billing",
            "summary": "Common billing questions including payment methods and invoicing.",
            "url": "/help/billing-faq",
        },
        {
            "id": "KB-003",
            "title": "Refund Policy",
            "category": "policy",
            "summary": "Our 30-day refund policy for all subscription plans.",
            "url": "/help/refund-policy",
        },
        {
            "id": "KB-004",
            "title": "API Rate Limits",
            "category": "technical",
            "summary": "Information about API rate limits and how to request increases.",
            "url": "/help/api-limits",
        },
    ]
    
    # Simple keyword matching for mock
    query_lower = query.lower()
    results = [
        a for a in articles
        if category == "all" or a["category"] == category
    ]
    
    # Filter by keyword relevance
    if results:
        scored = []
        for article in results:
            score = sum(1 for word in query_lower.split() if word in article["title"].lower() or word in article["summary"].lower())
            if score > 0:
                scored.append({**article, "relevance_score": score})
        scored.sort(key=lambda x: x["relevance_score"], reverse=True)
        results = scored[:3] if scored else results[:3]
    
    return json.dumps({
        "success": True,
        "query": query,
        "category": category,
        "results": results,
        "total_found": len(results),
    })


@tool
def escalate_to_human(reason: str, priority: str = "normal") -> str:
    """
    Escalate the conversation to a human support agent.
    Use this when the customer's issue requires human intervention,
    is too complex for AI, or the customer explicitly requests it.
    
    Args:
        reason: Reason for escalation
        priority: Priority level ("low", "normal", "high", "urgent")
    
    Returns:
        JSON string with escalation ticket details.
    """
    logger.info(f"Tool call: escalate_to_human(reason={reason}, priority={priority})")
    
    ticket_id = f"TKT-{uuid.uuid4().hex[:8].upper()}"
    
    return json.dumps({
        "success": True,
        "ticket_id": ticket_id,
        "reason": reason,
        "priority": priority,
        "estimated_wait_minutes": 15 if priority == "normal" else 5,
        "status": "queued",
        "message": "Your request has been escalated to a human agent. They will be with you shortly.",
    })


# ─── Tool Registry ───

AGENT_TOOLS = [
    lookup_order,
    process_refund,
    search_knowledge_base,
    escalate_to_human,
]

TOOL_MAP = {
    "lookup_order": lookup_order,
    "process_refund": process_refund,
    "search_knowledge_base": search_knowledge_base,
    "escalate_to_human": escalate_to_human,
}
