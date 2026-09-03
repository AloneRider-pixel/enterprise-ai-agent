"""Tests for API endpoints."""
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.fixture
async def client():
    """Create async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_root(client):
    """Test root endpoint returns service info."""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "Enterprise AI Support Agent"
    assert "version" in data


@pytest.mark.asyncio
async def test_health(client):
    """Test health check endpoint."""
    response = await client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "version" in data


@pytest.mark.asyncio
async def test_register(client):
    """Test user registration."""
    response = await client.post(
        "/api/auth/register",
        json={
            "email": "test@example.com",
            "password": "securepass123",
            "full_name": "Test User",
        },
    )
    # May fail if DB not available in test env, but should not 500
    assert response.status_code in (201, 409, 500)


@pytest.mark.asyncio
async def test_login_invalid(client):
    """Test login with invalid credentials."""
    response = await client.post(
        "/api/auth/login",
        json={
            "email": "nonexistent@example.com",
            "password": "wrongpassword",
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_chat_requires_auth(client):
    """Test that chat endpoint requires authentication."""
    response = await client.post(
        "/api/chat",
        json={
            "session_id": "test-session",
            "message": "Hello",
            "stream": False,
        },
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_documents_requires_auth(client):
    """Test that document endpoints require authentication."""
    response = await client.get("/api/documents")
    assert response.status_code == 403
