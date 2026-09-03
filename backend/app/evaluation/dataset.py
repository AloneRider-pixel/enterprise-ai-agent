"""
Evaluation dataset for RAG quality measurement.
Contains ground-truth question-answer-context triplets.
"""

# Sample evaluation dataset
# Each entry contains: question, ground_truth answer, relevant context, and expected citations
EVAL_DATASETS = {
    "default": [
        {
            "question": "What is the refund policy for orders?",
            "ground_truth": "We offer a 30-day refund policy for all subscription plans. Orders must be in 'delivered' or 'shipped' status to be eligible. Digital items are non-refundable after activation.",
            "context": "Our refund policy allows customers to request a full refund within 30 days of purchase. Eligible order statuses are 'delivered' and 'shipped'. Digital items that have been activated cannot be refunded. Refunds are processed within 5 business days.",
            "metadata": {"category": "policy", "difficulty": "easy"},
        },
        {
            "question": "How do I track my order ORD-002?",
            "ground_truth": "Order ORD-002 has been shipped via express method. The tracking number is TRK-987654321. The order total was $2,499.95 for 5 Enterprise Licenses.",
            "context": "Order ORD-002: Status is shipped. Shipping method is express. Tracking number is TRK-987654321. Items: Enterprise License x5 at $499.99 each. Total: $2,499.95.",
            "metadata": {"category": "order", "difficulty": "easy"},
        },
        {
            "question": "What are the API rate limits?",
            "ground_truth": "The default API rate limits are 100 requests per minute for standard plans and 1000 requests per minute for enterprise plans. You can request higher limits by contacting support.",
            "context": "API Rate Limits: Standard plan: 100 requests/minute. Enterprise plan: 1000 requests/minute. Rate limit headers are included in every response. To request higher limits, contact support@company.com or use the support portal.",
            "metadata": {"category": "technical", "difficulty": "medium"},
        },
        {
            "question": "What subscription plans do you offer?",
            "ground_truth": "We offer three plans: Starter at $29.99/month, Pro at $99.99/month, and Enterprise at $499.99/month per license.",
            "context": "Subscription Plans: Starter Plan - $29.99/month, includes basic features and email support. Pro Plan - $99.99/month, includes advanced features and priority support. Enterprise Plan - $499.99/month per license, includes all features, dedicated support, and custom integrations.",
            "metadata": {"category": "billing", "difficulty": "easy"},
        },
        {
            "question": "How do I reset my account password?",
            "ground_truth": "To reset your password, go to the login page and click 'Forgot Password'. Enter your registered email address and follow the instructions in the reset email. The reset link expires after 24 hours.",
            "context": "Password Reset Guide: 1. Navigate to the login page. 2. Click 'Forgot Password' link. 3. Enter your registered email address. 4. Check your email for a reset link. 5. Click the link and create a new password. Note: Reset links expire after 24 hours for security.",
            "metadata": {"category": "technical", "difficulty": "easy"},
        },
        {
            "question": "Can I upgrade my plan mid-billing cycle?",
            "ground_truth": "Yes, you can upgrade your plan at any time. The cost will be prorated for the remaining billing period. Downgrades take effect at the start of the next billing cycle.",
            "context": "Plan Changes: Upgrades can be made at any time and are prorated for the remaining billing period. Downgrades take effect at the start of the next billing cycle. No refunds are provided for partial months on downgrades.",
            "metadata": {"category": "billing", "difficulty": "medium"},
        },
        {
            "question": "What payment methods are accepted?",
            "ground_truth": "We accept all major credit cards (Visa, Mastercard, American Express), PayPal, and bank transfers for enterprise accounts.",
            "context": "Payment Methods: We accept Visa, Mastercard, American Express, and Discover credit cards. PayPal is also available for all plans. Enterprise customers can pay via bank transfer or purchase order. All prices are in USD.",
            "metadata": {"category": "billing", "difficulty": "easy"},
        },
        {
            "question": "How do I contact support?",
            "ground_truth": "You can reach support via email at support@company.com, through the in-app chat widget, or by creating a ticket in the support portal. Enterprise customers have access to a dedicated support line.",
            "context": "Contact Support: Email: support@company.com (response within 24 hours). In-app chat: Available 24/7 for Pro and Enterprise plans. Support portal: Create a ticket at help.company.com. Enterprise dedicated line: +1-800-SUPPORT (Enterprise plan only).",
            "metadata": {"category": "general", "difficulty": "easy"},
        },
        {
            "question": "What happens to my data if I cancel my subscription?",
            "ground_truth": "After cancellation, your data is retained for 30 days. During this period, you can export your data or reactivate your account. After 30 days, all data is permanently deleted.",
            "context": "Data Retention After Cancellation: Your data is retained for 30 days after subscription cancellation. During the 30-day grace period, you can export all data or reactivate your account without data loss. After 30 days, all account data is permanently and irreversibly deleted from our servers.",
            "metadata": {"category": "policy", "difficulty": "medium"},
        },
        {
            "question": "Is there an SLA for uptime?",
            "ground_truth": "We guarantee 99.9% uptime for Pro and Enterprise plans, and 99.5% for Starter plans. SLA credits are provided for any downtime that exceeds these thresholds.",
            "context": "Service Level Agreement: Starter Plan: 99.5% uptime guarantee. Pro Plan: 99.9% uptime guarantee. Enterprise Plan: 99.9% uptime guarantee with custom SLA options. SLA credits: 10% credit for each 0.1% below the guaranteed threshold, up to 30% of monthly fees.",
            "metadata": {"category": "policy", "difficulty": "medium"},
        },
    ],
}


def get_dataset(name: str = "default") -> list:
    """Get evaluation dataset by name."""
    return EVAL_DATASETS.get(name, EVAL_DATASETS["default"])


def get_all_dataset_names() -> list:
    """Get all available dataset names."""
    return list(EVAL_DATASETS.keys())
