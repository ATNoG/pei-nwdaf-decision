from datetime import datetime, timezone


def test_list_decisions_empty(client):
    """Returns empty list when no decision results exist."""
    response = client.get("/api/v1/decisions")
    assert response.status_code == 200
    assert response.json() == []


def test_list_decisions_with_results(client, seed_decision_results):
    """Returns all decision results ordered by most recent first."""
    response = client.get("/api/v1/decisions")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    # Most recent first
    assert data[0]["decision_name"] == "SUBVERT Y"
    assert data[1]["decision_name"] == "ALLOCATE X"


def test_list_decisions_pagination(client, seed_decision_results):
    """Respects skip and limit query parameters."""
    response = client.get("/api/v1/decisions?limit=1")
    data = response.json()
    assert len(data) == 1
    assert data[0]["decision_name"] == "SUBVERT Y"

    response = client.get("/api/v1/decisions?skip=1&limit=1")
    data = response.json()
    assert len(data) == 1
    assert data[0]["decision_name"] == "ALLOCATE X"


def test_list_decisions_filter_by_name(client, seed_decision_results):
    """Filters results by decision_name."""
    response = client.get("/api/v1/decisions?decision_name=ALLOCATE X")
    data = response.json()
    assert len(data) == 1
    assert data[0]["decision_name"] == "ALLOCATE X"


def test_list_decisions_filter_no_match(client, seed_decision_results):
    """Returns empty list when filter matches nothing."""
    response = client.get("/api/v1/decisions?decision_name=NONEXISTENT")
    assert response.status_code == 200
    assert response.json() == []


def test_get_decision_result_by_id(client, seed_decision_results):
    """Returns a specific decision result by ID."""
    response = client.get("/api/v1/decisions/1")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["decision_name"] == "ALLOCATE X"
    assert data["status"] == "applied"
    assert data["confidence"] == 0.85
    assert data["details"] == {"reason": "high traffic detected"}


def test_get_decision_result_not_found(client):
    """Returns 404 for non-existent decision result."""
    response = client.get("/api/v1/decisions/999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Decision result not found"


def test_get_latest_decision_result(client, seed_decision_results):
    """Returns the most recent decision result."""
    response = client.get("/api/v1/decisions/latest")
    assert response.status_code == 200
    data = response.json()
    assert data["decision_name"] == "SUBVERT Y"


def test_get_latest_decision_result_empty(client):
    """Returns 404 when no decision results exist."""
    response = client.get("/api/v1/decisions/latest")
    assert response.status_code == 404
    assert response.json()["detail"] == "No decision results found"
