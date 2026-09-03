"""
Seed script to populate the knowledge base with sample documents.
Run this after starting the application to have data available for RAG queries.
"""
import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.database import vector_store, init_database
from app.rag.chunking import text_chunker
from app.rag.embeddings import embedding_service


SAMPLE_DOCUMENTS = [
    {
        "document_id": "seed-001",
        "filename": "refund_policy.txt",
        "content": """
Refund Policy - Effective January 2024

Our refund policy allows customers to request a full refund within 30 days of purchase. 
To be eligible for a refund, your order must be in 'delivered' or 'shipped' status.

Refund Processing:
- Refunds are processed within 5 business days of approval
- Refunds are issued to the original payment method
- Digital items are non-refundable after activation
- Restock fees do not apply to software subscriptions

To request a refund:
1. Log into your account at portal.company.com
2. Navigate to Orders > Your Order
3. Click 'Request Refund'
4. Provide a reason for the refund
5. Submit your request

You will receive a confirmation email within 24 hours.

Contact support@company.com for refund inquiries.
""",
    },
    {
        "document_id": "seed-002",
        "filename": "subscription_plans.txt",
        "content": """
Subscription Plans and Pricing

We offer three subscription tiers to meet your needs:

STARTER PLAN - $29.99/month
- Up to 5 users
- 10 GB storage
- Email support (48-hour response)
- Basic API access (100 requests/minute)
- Community forum access

PRO PLAN - $99.99/month
- Up to 25 users
- 100 GB storage
- Priority email support (24-hour response)
- Full API access (1000 requests/minute)
- Advanced analytics dashboard
- Custom integrations

ENTERPRISE PLAN - $499.99/month per license
- Unlimited users
- 1 TB storage
- Dedicated account manager
- Phone support (4-hour response SLA)
- Unlimited API access
- Custom SLA options
- On-premise deployment option
- SOC 2 compliance documentation

All plans include:
- 99.9% uptime SLA (Pro and Enterprise)
- SSL encryption
- Daily backups
- GDPR compliance

Upgrade or downgrade at any time. Prorated billing applies.
Annual plans receive a 20% discount.
""",
    },
    {
        "document_id": "seed-003",
        "filename": "api_documentation.txt",
        "content": """
API Documentation - REST API v2

Base URL: https://api.company.com/v2

Authentication:
All API requests require a Bearer token in the Authorization header.
Generate your API key in Settings > API Keys.

Rate Limits:
- Starter Plan: 100 requests per minute
- Pro Plan: 1,000 requests per minute
- Enterprise: Custom limits

Response Headers:
- X-RateLimit-Limit: Maximum requests per window
- X-RateLimit-Remaining: Requests remaining in current window
- X-RateLimit-Reset: Unix timestamp when the window resets

Endpoints:

GET /users - List all users
POST /users - Create a new user
GET /users/{id} - Get user details
PUT /users/{id} - Update user
DELETE /users/{id} - Delete user

GET /orders - List orders
POST /orders - Create order
GET /orders/{id} - Get order details
POST /orders/{id}/refund - Request refund

GET /products - List products
GET /products/{id} - Product details

Error Codes:
- 400: Bad Request - Invalid parameters
- 401: Unauthorized - Missing or invalid token
- 403: Forbidden - Insufficient permissions
- 404: Not Found - Resource doesn't exist
- 429: Too Many Requests - Rate limit exceeded
- 500: Internal Server Error

For API support, email api-support@company.com
""",
    },
    {
        "document_id": "seed-004",
        "filename": "password_reset_guide.txt",
        "content": """
Password Reset Guide

If you've forgotten your password or need to reset it for security reasons, follow these steps:

Step 1: Request a Password Reset
1. Go to the login page at portal.company.com/login
2. Click the "Forgot Password?" link below the login form
3. Enter your registered email address
4. Click "Send Reset Link"

Step 2: Check Your Email
- You'll receive an email within 5 minutes
- Check your spam/junk folder if you don't see it
- The email comes from noreply@company.com

Step 3: Create New Password
1. Click the reset link in the email
2. The link expires after 24 hours
3. Enter your new password (minimum 12 characters)
4. Password must include: uppercase, lowercase, number, and special character
5. Click "Update Password"

Step 4: Login
- Use your new password to log in
- All other active sessions will be logged out

Troubleshooting:
- If the reset link doesn't work, request a new one
- Contact support@company.com if you continue to have issues
- For enterprise accounts, contact your system administrator

Security Best Practices:
- Use a unique password for each service
- Enable two-factor authentication (2FA) in Settings > Security
- Never share your password via email or chat
""",
    },
    {
        "document_id": "seed-005",
        "filename": "troubleshooting_faq.txt",
        "content": """
Troubleshooting & FAQ

Q: I can't log in to my account
A: First, try resetting your password. If that doesn't work, check if your account is locked (5 failed attempts = 15 minute lockout). Contact support if issues persist.

Q: My API calls are returning 429 errors
A: You've exceeded your rate limit. Check your plan limits in the API documentation. Consider upgrading your plan or implementing request queuing.

Q: How do I cancel my subscription?
A: Go to Settings > Subscription > Cancel. Your access continues until the end of the current billing period. No partial refunds for unused time.

Q: Can I get a refund?
A: We offer 30-day refunds for eligible orders. See the Refund Policy for details. Contact support@company.com to initiate.

Q: My data export is stuck at 0%
A: Large exports can take several hours. Try again during off-peak hours (2-6 AM EST). If the issue persists, contact support.

Q: How do I add team members?
A: Admin users can invite team members from Settings > Team > Invite Member. Enter their email and select their role.

Q: Is my data backed up?
A: Yes, we perform daily automated backups with 30-day retention. Enterprise plans include point-in-time recovery.

Q: Do you offer a discount for nonprofits?
A: Yes! We offer 50% off all plans for registered nonprofits. Contact sales@company.com with your nonprofit documentation.

Q: What's your uptime SLA?
A: Starter: 99.5%. Pro: 99.9%. Enterprise: 99.9% with custom options. SLA credits are automatically applied for any downtime exceeding the guarantee.
""",
    },
]


async def seed():
    """Seed the database with sample documents."""
    print("🌱 Starting document seeding...")
    
    # Connect to vector store
    await vector_store.connect()
    print("✓ Connected to pgvector")
    
    for doc in SAMPLE_DOCUMENTS:
        print(f"\n📄 Processing: {doc['filename']}")
        
        # Chunk the document
        chunks = text_chunker.chunk_text(
            doc["content"],
            metadata={
                "document_id": doc["document_id"],
                "filename": doc["filename"],
                "source": "seed",
            },
        )
        print(f"  → {len(chunks)} chunks created")
        
        # Generate embeddings
        texts = [chunk["content"] for chunk in chunks]
        embeddings = await embedding_service.embed_batch(texts)
        print(f"  → {len(embeddings)} embeddings generated")
        
        # Store in pgvector
        for chunk, embedding in zip(chunks, embeddings):
            await vector_store.store_embedding(
                chunk_id=chunk["chunk_id"],
                document_id=doc["document_id"],
                content=chunk["content"],
                embedding=embedding,
                metadata=chunk["metadata"],
            )
        print(f"  ✓ Stored in pgvector")
    
    print(f"\n✅ Seeding complete! {len(SAMPLE_DOCUMENTS)} documents indexed.")


if __name__ == "__main__":
    asyncio.run(seed())
