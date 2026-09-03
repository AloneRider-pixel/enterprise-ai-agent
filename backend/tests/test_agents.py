"""Tests for the LangGraph agent components."""
import pytest
import json
from app.agents.tools import (
    lookup_order,
    process_refund,
    search_knowledge_base,
    escalate_to_human,
)


class TestAgentTools:
    """Tests for agent tool functions."""

    def test_lookup_order_found(self):
        result = json.loads(lookup_order.invoke({"order_id": "ORD-001"}))
        assert result["success"] is True
        assert result["order"]["order_id"] == "ORD-001"
        assert result["order"]["status"] == "delivered"

    def test_lookup_order_not_found(self):
        result = json.loads(lookup_order.invoke({"order_id": "ORD-999"}))
        assert result["success"] is False
        assert "not found" in result["error"]

    def test_lookup_order_case_insensitive(self):
        result = json.loads(lookup_order.invoke({"order_id": "ord-002"}))
        assert result["success"] is True

    def test_process_refund_eligible(self):
        result = json.loads(process_refund.invoke({
            "order_id": "ORD-001",
            "reason": "Changed my mind",
        }))
        assert result["success"] is True
        assert result["eligible"] is True
        assert "refund_id" in result

    def test_process_refund_not_found(self):
        result = json.loads(process_refund.invoke({
            "order_id": "ORD-999",
            "reason": "Defective product",
        }))
        assert result["success"] is False

    def test_search_knowledge_base(self):
        result = json.loads(search_knowledge_base.invoke({
            "query": "password reset",
            "category": "all",
        }))
        assert result["success"] is True
        assert isinstance(result["results"], list)

    def test_search_knowledge_base_category(self):
        result = json.loads(search_knowledge_base.invoke({
            "query": "billing payment",
            "category": "billing",
        }))
        assert result["success"] is True

    def test_escalate_to_human(self):
        result = json.loads(escalate_to_human.invoke({
            "reason": "Complex issue",
            "priority": "high",
        }))
        assert result["success"] is True
        assert "ticket_id" in result
        assert result["priority"] == "high"

    def test_escalate_default_priority(self):
        result = json.loads(escalate_to_human.invoke({
            "reason": "Need help",
            "priority": "normal",
        }))
        assert result["success"] is True
        assert result["estimated_wait_minutes"] == 15
