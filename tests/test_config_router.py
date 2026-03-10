from fastapi.testclient import TestClient


def test_list_decisions(client: TestClient):
    """Test GET /config/decisions returns default decisions."""
    response = client.get("/api/v1/config/decisions")
    assert response.status_code == 200
    data = response.json()
    assert "decisions" in data
    assert "count" in data
    assert data["count"] == 3


def test_add_decision(client: TestClient):
    """Test POST /config/decisions adds a new decision."""
    response = client.post(
        "/api/v1/config/decisions",
        json={"name": "NEW_DECISION", "description": "Test decision"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["decision"]["name"] == "NEW_DECISION"


def test_add_duplicate_decision(client: TestClient):
    """Test POST /config/decisions rejects duplicate decision."""
    client.post(
        "/api/v1/config/decisions",
        json={"name": "DUPLICATE", "description": "First"}
    )
    response = client.post(
        "/api/v1/config/decisions",
        json={"name": "DUPLICATE", "description": "Duplicate"}
    )
    assert response.status_code == 400


def test_add_to_blacklist(client: TestClient):
    """Test POST /config/blacklist adds to blacklist."""
    response = client.post(
        "/api/v1/config/blacklist",
        json={"name": "ALLOCATE X", "reason": "Test reason"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["entry"]["name"] == "ALLOCATE X"


def test_add_to_blacklist_nonexistent_decision(client: TestClient):
    """Test POST /config/blacklist rejects non-existent decision."""
    response = client.post(
        "/api/v1/config/blacklist",
        json={"name": "NONEXISTENT", "reason": "Test"}
    )
    assert response.status_code == 400


def test_remove_decision_also_removes_from_blacklist(client: TestClient):
    """Test DELETE /config/decisions/{name} also removes from blacklist."""
    # Add to blacklist first
    client.post(
        "/api/v1/config/blacklist",
        json={"name": "ALLOCATE X", "reason": "Test"}
    )
    # Remove decision
    response = client.delete("/api/v1/config/decisions/ALLOCATE X")
    assert response.status_code == 200
    # Verify blacklist is empty
    blacklist_response = client.get("/api/v1/config/blacklist")
    assert blacklist_response.json()["blacklist"] == []


def test_remove_from_blacklist(client: TestClient):
    """Test DELETE /config/blacklist/{name} removes entry."""
    client.post(
        "/api/v1/config/blacklist",
        json={"name": "ALLOCATE X", "reason": "Test"}
    )
    response = client.delete("/api/v1/config/blacklist/ALLOCATE X")
    assert response.status_code == 200


def test_health_endpoint(client: TestClient):
    """Test GET /health returns healthy status."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
