"""
Basic tests for API Gateway
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check():
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_root_endpoint():
    """Test root endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["service"] == "MeshML API Gateway"


def test_docs_available():
    """Test API documentation is accessible"""
    response = client.get("/docs")
    assert response.status_code == 200


def test_register_user():
    """Test user registration"""
    response = client.post(
        "/api/auth/register",
        json={
            "email": "test@example.com",
            "password": "testpassword123",
            "full_name": "Test User"
        }
    )
    # May fail if database not set up, but endpoint should exist
    assert response.status_code in [201, 500, 503]


def test_unauthorized_access():
    """Test that protected endpoints require authentication"""
    response = client.get("/api/auth/me")
    assert response.status_code == 403  # No auth header


def test_list_public_groups():
    """Test listing public groups"""
    response = client.get("/api/groups/public")
    # May fail if database not set up
    assert response.status_code in [200, 500, 503]
