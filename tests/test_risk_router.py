from fastapi.testclient import TestClient


def test_list_risk_levels(client: TestClient):
    """Test GET /config/risk-levels returns default risk levels."""
    response = client.get("/api/v1/config/risk-levels")
    assert response.status_code == 200
    data = response.json()
    assert "risk_levels" in data
    assert "count" in data
    assert data["count"] == 3
    assert any(rl["name"] == "Low Risk" for rl in data["risk_levels"])
    assert any(rl["name"] == "Medium Risk" for rl in data["risk_levels"])
    assert any(rl["name"] == "High Risk" for rl in data["risk_levels"])


def test_add_risk_level(client: TestClient):
    """Test POST /config/risk-levels adds a new risk level."""
    response = client.post(
        "/api/v1/config/risk-levels",
        json={
            "name": "Critical Risk",
            "degree": 100,
            "description": "Executive approval only"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["risk_level"]["name"] == "Critical Risk"
    assert data["risk_level"]["degree"] == 100
    assert "id" in data
    assert isinstance(data["id"], int)


def test_add_duplicate_risk_level(client: TestClient):
    """Test POST /config/risk-levels rejects duplicate risk level."""
    client.post(
        "/api/v1/config/risk-levels",
        json={"name": "DUPLICATE_RISK", "degree": 50}
    )
    response = client.post(
        "/api/v1/config/risk-levels",
        json={"name": "DUPLICATE_RISK", "degree": 75}
    )
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


def test_remove_risk_level(client: TestClient):
    """Test DELETE /config/risk-levels/{name} removes risk level."""
    # Add a risk level first
    client.post(
        "/api/v1/config/risk-levels",
        json={"name": "Temporary Risk", "degree": 25}
    )
    # Remove it
    response = client.delete("/api/v1/config/risk-levels/Temporary Risk")
    assert response.status_code == 200
    data = response.json()
    assert not any(rl["name"] == "Temporary Risk" for rl in data["risk_levels"])


def test_remove_nonexistent_risk_level(client: TestClient):
    """Test DELETE /config/risk-levels/{name} returns 404 for non-existent."""
    response = client.delete("/api/v1/config/risk-levels/Nonexistent Risk")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_add_decision_with_risk_level_and_justification(client: TestClient):
    """Test POST /config/decisions with risk_level_id and justification."""
    # Use a known valid risk_level_id (1 should be Low Risk from fixtures)
    response = client.post(
        "/api/v1/config/decisions",
        json={
            "name": "DECIDE WITH RISK",
            "description": "Test decision with risk",
            "risk_level_id": 1,
            "justification": "Business requirement"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["decision"]["name"] == "DECIDE WITH RISK"
    assert data["decision"]["risk_level_id"] == 1
    assert data["decision"]["justification"] == "Business requirement"


def test_list_decisions_includes_risk_info(client: TestClient):
    """Test GET /config/decisions includes risk_level_id and justification."""
    response = client.get("/api/v1/config/decisions")
    assert response.status_code == 200
    data = response.json()
    assert "decisions" in data
    # Default decisions should have risk_level_id set
    for decision in data["decisions"]:
        assert "risk_level_id" in decision
        assert "justification" in decision
