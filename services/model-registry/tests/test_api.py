"""
Tests for Model Registry Service
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.database import get_db_session
from app.models import Base

# Test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create test database
Base.metadata.create_all(bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db_session] = override_get_db

client = TestClient(app)


class TestModels:
    """Test model CRUD operations"""
    
    def test_create_model(self):
        """Test creating a new model"""
        response = client.post("/api/v1/models/", json={
            "name": "Test Model",
            "description": "Test description",
            "group_id": 1,
            "architecture_type": "CNN",
            "dataset_type": "CIFAR-10",
            "version": "1.0.0"
        })
        
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Model"
        assert data["state"] == "uploading"
        assert "id" in data
    
    def test_get_model(self):
        """Test retrieving a model"""
        # Create model first
        create_response = client.post("/api/v1/models/", json={
            "name": "Test Model 2",
            "group_id": 1
        })
        model_id = create_response.json()["id"]
        
        # Get model
        response = client.get(f"/api/v1/models/{model_id}")
        assert response.status_code == 200
        assert response.json()["name"] == "Test Model 2"
    
    def test_get_nonexistent_model(self):
        """Test getting a model that doesn't exist"""
        response = client.get("/api/v1/models/99999")
        assert response.status_code == 404


class TestSearch:
    """Test model search functionality"""
    
    def test_search_models(self):
        """Test basic model search"""
        response = client.get("/api/v1/search/models")
        assert response.status_code == 200
        data = response.json()
        assert "models" in data
        assert "total" in data
        assert "page" in data
    
    def test_search_with_filters(self):
        """Test search with filters"""
        response = client.get("/api/v1/search/models", params={
            "architecture_type": "CNN",
            "page": 1,
            "page_size": 10
        })
        assert response.status_code == 200
    
    def test_get_architecture_types(self):
        """Test getting architecture types"""
        response = client.get("/api/v1/search/architecture-types")
        assert response.status_code == 200
        assert "architecture_types" in response.json()


class TestLifecycle:
    """Test lifecycle management"""
    
    def test_get_available_states(self):
        """Test getting available states"""
        response = client.get("/api/v1/lifecycle/states")
        assert response.status_code == 200
        data = response.json()
        assert "states" in data
        assert "transitions" in data
        assert "uploading" in data["states"]
    
    def test_invalid_state_transition(self):
        """Test invalid state transition"""
        # Create model
        create_response = client.post("/api/v1/models/", json={
            "name": "Test Model 3",
            "group_id": 1
        })
        model_id = create_response.json()["id"]
        
        # Try invalid transition (UPLOADING -> READY, should be UPLOADING -> VALIDATING)
        response = client.post(f"/api/v1/lifecycle/{model_id}/mark-ready")
        assert response.status_code == 400


class TestVersioning:
    """Test version management"""
    
    def test_increment_version(self):
        """Test version increment utility"""
        response = client.post("/api/v1/versions/increment", params={
            "current_version": "1.0.0",
            "part": "minor"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["new_version"] == "1.1.0"
    
    def test_increment_version_patch(self):
        """Test patch increment"""
        response = client.post("/api/v1/versions/increment", params={
            "current_version": "1.2.3",
            "part": "patch"
        })
        assert response.status_code == 200
        assert response.json()["new_version"] == "1.2.4"
    
    def test_invalid_version_format(self):
        """Test invalid version format"""
        response = client.post("/api/v1/versions/increment", params={
            "current_version": "invalid",
            "part": "patch"
        })
        assert response.status_code == 400


class TestHealth:
    """Test health and system endpoints"""
    
    def test_root(self):
        """Test root endpoint"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "MeshML Model Registry"
    
    def test_health_check(self):
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "model-registry"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
